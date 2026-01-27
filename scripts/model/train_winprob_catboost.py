#!/usr/bin/env python3
"""
Train a CatBoost win-probability model from ESPN historical tables, and save a full pipeline artifact.

This script uses CatBoost for gradient boosting, which can automatically find interaction terms.

Inputs:
- ESPN tables: espn.probabilities_raw_items, espn.prob_event_state, espn.scoreboard_games
- Opening odds (optional): external.sportsbook_odds_snapshots

Split policy (leak-proof, game-level by season_start):
- train seasons: season_start <= --train-season-start-max (default 2022)
- calibration season: season_start == --calib-season-start (default 2023), optional
- test season: season_start == --test-season-start (default 2024), not used in training

Features (prediction-time):
- point_differential (home - away)
- time_remaining_regulation
- possession ("home"|"away"|"unknown")
- Optional interaction terms

Label:
- y_home_win = 1 if final_winning_team == 0 else 0

Performance Optimizations:
- Parquet caching: Use --cache-parquet to save/load training data (saves ~60s on subsequent runs)
- work_mem: Configurable via --work-mem (default 4GB) to avoid disk spills
- ORDER BY removed from SQL queries (saves ~15s)

Recommended database indexes (run once):
    CREATE INDEX CONCURRENTLY ix_prob_event_state_game_event 
    ON espn.prob_event_state (game_id, event_id);
    
    CREATE INDEX CONCURRENTLY ix_sportsbook_odds_opening
    ON external.sportsbook_odds_snapshots (espn_game_id)
    WHERE is_opening_line = TRUE;

Usage:
  ./.venv/bin/python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_v1.json \
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    PreprocessParams,
    ModelParams,  # Still needed for artifact structure, but won't be used for prediction
    WinProbArtifact,
    PlattCalibrator,  # Needed for calibration parameter validation
    build_design_matrix,
    fit_platt_calibrator_on_probs,
    fit_platt_calibrator_on_raw_margins,  # For fitting Platt on raw CatBoost margins (better practice)
    fit_isotonic_calibrator_on_probs,
    load_artifact,
    predict_proba,
    save_artifact,
    utc_now_iso_compact,
    ODDS_FEATURES,  # Canonical opening odds feature list
    logit,  # For CatBoost baseline computation
    brier,  # For calibration quality metrics
    logloss,  # For calibration quality metrics
    ece_binned,  # For calibration quality metrics
)


def _calculate_buckets(time_remaining: pd.Series, step_seconds: int) -> list[int]:
    """
    Calculate bucket anchors from time_remaining values.
    
    Creates buckets from max to 0 in steps of step_seconds.
    """
    max_time = int(time_remaining.max()) if len(time_remaining) > 0 else 2880
    # Round max_time up to nearest step
    max_bucket = ((max_time + step_seconds - 1) // step_seconds) * step_seconds
    buckets = list(range(max_bucket, -1, -step_seconds))
    return buckets


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train a leak-proof CatBoost win-probability model.")
    p.add_argument("--out-artifact", required=True, help="Output artifact JSON path.")
    p.add_argument("--dsn", help="Database connection string (or use DATABASE_URL env var)")
    p.add_argument("--version", default="v1", help="Artifact version string (default: v1).")
    p.add_argument("--train-season-start-max", type=int, default=2022, help="Max season_start included in training (default: 2022).")
    p.add_argument("--calib-season-start", type=int, default=2023, help="Season_start used for calibration (default: 2023).")
    p.add_argument("--calibration-method", choices=["platt", "isotonic"], default="platt", help="Calibration method: 'platt' or 'isotonic' (default: platt).")
    p.add_argument("--disable-calibration", action="store_true", help="Disable calibration even if calibration season exists.")
    p.add_argument("--test-season-start", type=int, default=2024, help="Held-out test season_start (default: 2024).")
    p.add_argument("--iterations", type=int, default=1000, help="CatBoost iterations (default: 1000).")
    p.add_argument("--depth", type=int, default=6, help="CatBoost tree depth (default: 6).")
    p.add_argument("--learning-rate", type=float, default=0.1, help="CatBoost learning rate (default: 0.1).")
    p.add_argument("--min-train-rows", type=int, default=1000, help="Minimum training rows required (default: 1000).")
    p.add_argument("--bucket-step-seconds", type=int, default=60, help="Bucket step in seconds for artifact metadata (default: 60).")
    p.add_argument("--no-interaction-terms", dest="use_interaction_terms", action="store_false", default=True, help="Disable interaction terms. Default: enabled.")
    p.add_argument("--save-split-file", type=str, default=None, help="Path to save train/test/calib split file (JSON format) for reproducibility.")
    p.add_argument("--disable-opening-odds", action="store_true", help="Disable opening odds features (for baseline model training).")
    p.add_argument("--cache-parquet", type=str, default=None, help="Path to cache training data as Parquet (saves ~60s on subsequent runs).")
    p.add_argument("--work-mem", type=str, default="4GB", help="PostgreSQL work_mem setting for query optimization (default: 4GB).")
    return p.parse_args()


def _load_training_data(conn, train_season_start_max: int, test_season_start: int, calib_season_start: int | None, use_interaction_terms: bool = True) -> pd.DataFrame:
    """
    Load training data directly from ESPN tables with opening odds join (Option B approach).
    
    **Why ESPN tables directly?**
    - Training doesn't need Kalshi data (only needed for simulation)
    - ESPN has historical data back to 2017, Kalshi only has 2025-26
    - Canonical dataset is optimized for simulation (ESPN + Kalshi join) and excludes 94% of training data
    
    **Opening Odds Integration (Option B)**:
    - LEFT JOIN with external.sportsbook_odds_snapshots filtered for is_opening_line = TRUE
    - Join on espn_game_id (ESPN event_id = external.espn_game_id)
    - Pivots opening odds: moneyline (home/away), spread (home), total (over)
    
    Maps ESPN columns to model features:
    - score_diff -> point_differential
    - time_remaining -> time_remaining_regulation
    - possession -> 'unknown' (not reliably available)
    - opening_moneyline_home, opening_moneyline_away, opening_spread, opening_total -> engineered features
    """
    print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Building SQL query...", file=sys.stderr)
    print(f"      Interaction terms: {'enabled' if use_interaction_terms else 'disabled'}", file=sys.stderr)
    # Use the same query structure as train_winprob_logreg.py
    if use_interaction_terms:
        query = """
        WITH espn_base AS (
            SELECT
                p.game_id,
                p.sequence_number,
                p.season_label,
                CAST(LEFT(p.season_label, 4) AS INTEGER) AS season_start,
                e.point_differential AS score_diff,
                e.time_remaining,
                CASE 
                    WHEN e.time_remaining IS NULL THEN NULL
                    WHEN e.time_remaining > 2160 THEN 1
                    WHEN e.time_remaining > 1440 THEN 2
                    WHEN e.time_remaining > 720 THEN 3
                    ELSE 4
                END AS period,
                CASE 
                    WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0
                    ELSE p.home_win_percentage
                END AS espn_home_prob
        FROM espn.probabilities_raw_items p
        JOIN espn.prob_event_state e  -- INNER JOIN (WHERE filters make LEFT JOIN equivalent)
            ON p.game_id = e.game_id 
            AND p.event_id = e.event_id
        WHERE e.time_remaining IS NOT NULL
            AND e.point_differential IS NOT NULL
        ),
        espn_base_filtered AS (
            SELECT *
            FROM espn_base
            WHERE season_start <= {train_season_start_max}
               OR season_start = {test_season_start}
               OR (season_start = {calib_season_start} AND {calib_season_start} IS NOT NULL)
        ),
        -- Extract distinct game_ids for scoping downstream CTEs
        needed_games AS (
            SELECT DISTINCT game_id FROM espn_base_filtered
        ),
        espn_with_lag AS (
            SELECT
                *,
                LAG(espn_home_prob, 1) OVER (PARTITION BY game_id ORDER BY sequence_number) AS espn_home_prob_lag_1
            FROM espn_base_filtered
        ),
        scoreboard_final AS MATERIALIZED (
            -- Scoped to only needed games (massive speedup)
            SELECT DISTINCT ON (sg.event_id)
                sg.event_id,
                sg.home_score,
                sg.away_score
            FROM espn.scoreboard_games sg
            JOIN needed_games g ON g.game_id = sg.event_id
            WHERE sg.status_completed = TRUE
            ORDER BY sg.event_id, sg.scoreboard_date DESC
        ),
        opening_odds AS MATERIALIZED (
            -- Pivot opening odds by market_type and side (scoped to needed games)
            SELECT 
                s.espn_game_id,
                MAX(s.odds_decimal) FILTER (WHERE s.market_type = 'moneyline' AND s.side = 'home') AS opening_moneyline_home,
                MAX(s.odds_decimal) FILTER (WHERE s.market_type = 'moneyline' AND s.side = 'away') AS opening_moneyline_away,
                MAX(s.line_value) FILTER (WHERE s.market_type = 'spread' AND s.side = 'home') AS opening_spread,
                MAX(s.line_value) FILTER (WHERE s.market_type = 'total' AND s.side = 'over') AS opening_total
            FROM external.sportsbook_odds_snapshots s
            JOIN needed_games g ON g.game_id = s.espn_game_id
            WHERE s.is_opening_line = TRUE
            GROUP BY s.espn_game_id
        ),
        espn_with_features AS (
            SELECT
                e.season_start,
                e.season_label,
                e.game_id,
                e.sequence_number,
                e.score_diff AS point_differential,
                e.time_remaining AS time_remaining_regulation,
                'unknown' AS possession,
                CASE 
                    WHEN sg.home_score > sg.away_score THEN 0
                    WHEN sg.away_score > sg.home_score THEN 1
                    ELSE NULL
                END AS final_winning_team,
                e.score_diff / NULLIF(SQRT(e.time_remaining + 1), 0) AS score_diff_div_sqrt_time_remaining,
                e.espn_home_prob,
                e.espn_home_prob_lag_1,
                e.espn_home_prob - e.espn_home_prob_lag_1 AS espn_home_prob_delta_1,
                e.period,
                CASE 
                    WHEN e.time_remaining IS NOT NULL THEN
                        (FLOOR(e.time_remaining / 60.0) * 60)::INTEGER
                    ELSE NULL
                END AS bucket_seconds_remaining,
                -- Opening odds from external.sportsbook_odds_snapshots (Option B)
                oo.opening_moneyline_home,
                oo.opening_moneyline_away,
                oo.opening_spread,
                oo.opening_total
            FROM espn_with_lag e
            LEFT JOIN scoreboard_final sg 
                ON e.game_id = sg.event_id
            LEFT JOIN opening_odds oo
                ON e.game_id = oo.espn_game_id
            WHERE sg.home_score IS NOT NULL 
              AND sg.away_score IS NOT NULL
        )
        SELECT
            e.season_start,
            e.season_label,
            e.game_id,
            e.sequence_number,
            e.point_differential,
            e.time_remaining_regulation,
            e.possession,
            e.final_winning_team,
            e.score_diff_div_sqrt_time_remaining,
            e.espn_home_prob,
            e.espn_home_prob_lag_1,
            e.espn_home_prob_delta_1,
            e.period,
            e.bucket_seconds_remaining,
            -- Opening odds columns (raw, will be engineered after loading)
            e.opening_moneyline_home,
            e.opening_moneyline_away,
            e.opening_spread,
            e.opening_total
        FROM espn_with_features e
        -- REMOVED ORDER BY: saves ~15s and 600MB disk spill (not needed for training)
        """.format(
            train_season_start_max=train_season_start_max,
            test_season_start=test_season_start,
            calib_season_start=calib_season_start if calib_season_start is not None else 'NULL'
        )
    else:
        # No interaction terms - simpler query structure
        query = """
        WITH espn_base AS (
            SELECT
                p.game_id,
                p.sequence_number,
                p.season_label,
                CAST(LEFT(p.season_label, 4) AS INTEGER) AS season_start,
                e.point_differential AS score_diff,
                e.time_remaining
        FROM espn.probabilities_raw_items p
        JOIN espn.prob_event_state e  -- INNER JOIN (WHERE filters make LEFT JOIN equivalent)
            ON p.game_id = e.game_id 
            AND p.event_id = e.event_id
        WHERE e.time_remaining IS NOT NULL
            AND e.point_differential IS NOT NULL
        ),
        espn_base_filtered AS (
            SELECT *
            FROM espn_base
            WHERE season_start <= {train_season_start_max}
               OR season_start = {test_season_start}
               OR (season_start = {calib_season_start} AND {calib_season_start} IS NOT NULL)
        ),
        -- Extract distinct game_ids for scoping downstream CTEs
        needed_games AS (
            SELECT DISTINCT game_id FROM espn_base_filtered
        ),
        scoreboard_final AS MATERIALIZED (
            -- Scoped to only needed games (massive speedup)
            SELECT DISTINCT ON (sg.event_id)
                sg.event_id,
                sg.home_score,
                sg.away_score
            FROM espn.scoreboard_games sg
            JOIN needed_games g ON g.game_id = sg.event_id
            WHERE sg.status_completed = TRUE
            ORDER BY sg.event_id, sg.scoreboard_date DESC
        ),
        opening_odds AS MATERIALIZED (
            -- Pivot opening odds by market_type and side (scoped to needed games)
            SELECT 
                s.espn_game_id,
                MAX(s.odds_decimal) FILTER (WHERE s.market_type = 'moneyline' AND s.side = 'home') AS opening_moneyline_home,
                MAX(s.odds_decimal) FILTER (WHERE s.market_type = 'moneyline' AND s.side = 'away') AS opening_moneyline_away,
                MAX(s.line_value) FILTER (WHERE s.market_type = 'spread' AND s.side = 'home') AS opening_spread,
                MAX(s.line_value) FILTER (WHERE s.market_type = 'total' AND s.side = 'over') AS opening_total
            FROM external.sportsbook_odds_snapshots s
            JOIN needed_games g ON g.game_id = s.espn_game_id
            WHERE s.is_opening_line = TRUE
            GROUP BY s.espn_game_id
        ),
        espn_with_features AS (
            SELECT
                e.season_start,
                e.season_label,
                e.game_id,
                e.sequence_number,
                e.score_diff AS point_differential,
                e.time_remaining AS time_remaining_regulation,
                'unknown' AS possession,
                CASE 
                    WHEN sg.home_score > sg.away_score THEN 0
                    WHEN sg.away_score > sg.home_score THEN 1
                    ELSE NULL
                END AS final_winning_team,
                CASE 
                    WHEN e.time_remaining IS NOT NULL THEN
                        (FLOOR(e.time_remaining / 60.0) * 60)::INTEGER
                    ELSE NULL
                END AS bucket_seconds_remaining,
                -- Opening odds from external.sportsbook_odds_snapshots (Option B)
                oo.opening_moneyline_home,
                oo.opening_moneyline_away,
                oo.opening_spread,
                oo.opening_total
            FROM espn_base_filtered e
            LEFT JOIN scoreboard_final sg 
                ON e.game_id = sg.event_id
            LEFT JOIN opening_odds oo
                ON e.game_id = oo.espn_game_id
            WHERE sg.home_score IS NOT NULL 
              AND sg.away_score IS NOT NULL
        )
        SELECT
            e.season_start,
            e.season_label,
            e.game_id,
            e.sequence_number,
            e.point_differential,
            e.time_remaining_regulation,
            e.possession,
            e.final_winning_team,
            e.bucket_seconds_remaining,
            -- Opening odds columns (raw, will be engineered after loading)
            e.opening_moneyline_home,
            e.opening_moneyline_away,
            e.opening_spread,
            e.opening_total
        FROM espn_with_features e
        -- REMOVED ORDER BY: saves ~15s and 600MB disk spill (not needed for training)
        """.format(
            train_season_start_max=train_season_start_max,
            test_season_start=test_season_start,
            calib_season_start=calib_season_start if calib_season_start is not None else 'NULL'
        )
    
    # Suppress pandas warning about psycopg connection (it works fine, just not officially supported)
    print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing SQL query (this may take several minutes)...", file=sys.stderr)
    query_start = time.time()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy.*")
        df = pd.read_sql(query, conn)
    query_time = time.time() - query_start
    print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SQL query completed in {query_time:.2f} seconds", file=sys.stderr)
    print(f"      Rows returned: {len(df):,}", file=sys.stderr)
    
    # Compute opening odds engineered features using shared helper function
    print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing opening odds engineered features...", file=sys.stderr)
    from scripts.lib._winprob_lib import compute_opening_odds_features
    
    # Apply helper function vectorized (handles arrays natively)
    if len(df) > 0:
        odds_start = time.time()
        odds_features = compute_opening_odds_features(
            opening_moneyline_home=df['opening_moneyline_home'].to_numpy() if 'opening_moneyline_home' in df.columns else None,
            opening_moneyline_away=df['opening_moneyline_away'].to_numpy() if 'opening_moneyline_away' in df.columns else None,
            opening_spread=df['opening_spread'].to_numpy() if 'opening_spread' in df.columns else None,
            opening_total=df['opening_total'].to_numpy() if 'opening_total' in df.columns else None,
        )
        
        # Add engineered features to DataFrame
        df['opening_prob_home_fair'] = odds_features['opening_prob_home_fair']
        df['opening_overround'] = odds_features['opening_overround']
        odds_time = time.time() - odds_start
        # Count rows with opening odds (use opening_overround to infer, since has_opening_moneyline removed)
        odds_count = (~df['opening_overround'].isna()).sum() if 'opening_overround' in df.columns else 0
        print(f"      Opening odds features computed in {odds_time:.2f} seconds", file=sys.stderr)
        print(f"      Snapshots with opening odds: {odds_count:,} ({100.0 * odds_count / len(df):.1f}%)", file=sys.stderr)
    else:
        # Empty DataFrame - add columns with empty arrays
        df['opening_prob_home_fair'] = pd.Series(dtype=float)
        df['opening_overround'] = pd.Series(dtype=float)
    
    # REMOVED: opening_prob_home_fair_time_weighted (double-feeding odds)
    # We already use opening_prob_home_fair as CatBoost baseline, so adding it as a feature
    # allows the model to reconstruct the baseline, defeating the purpose.
    # If we want time-weighted odds, we should use a residual-style feature instead.
    if use_interaction_terms:
        print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipping odds/time interaction terms (removed to prevent double-feeding)", file=sys.stderr)
        print(f"      Note: opening_prob_home_fair is used as CatBoost baseline, not as a feature", file=sys.stderr)
    else:
        print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipping odds/time interaction terms (interaction terms disabled)", file=sys.stderr)
    
    print(f"    [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data loading function completed", file=sys.stderr)
    return df


def _validate_feature_importance(model: CatBoostClassifier, artifact: WinProbArtifact, threshold: float = 0.5) -> bool:
    """Validate that opening odds features don't dominate model.
    
    Args:
        model: Trained CatBoostClassifier
        artifact: WinProbArtifact with feature names
        threshold: Maximum allowed percentage from opening odds (default 0.5 = 50%)
    
    Returns:
        bool: True if validation passes (<threshold), False if fails (>threshold)
    """
    importance = model.get_feature_importance()
    feature_names = artifact.feature_names
    
    # Pair features with importance
    feat_importance = list(zip(feature_names, importance))
    feat_importance.sort(key=lambda x: x[1], reverse=True)
    
    # Count opening odds features in top 10
    odds_in_top10 = sum(1 for feat, _ in feat_importance[:10] 
                       if any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround']))
    
    # Calculate total importance from opening odds features
    total_importance = sum(imp for _, imp in feat_importance)
    odds_importance = sum(imp for feat, imp in feat_importance 
                         if any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround']))
    odds_pct = (odds_importance / total_importance * 100) if total_importance > 0 else 0
    
    print(f"\nFeature importance validation:", file=sys.stderr)
    print(f"  Opening odds features in top 10: {odds_in_top10}/10", file=sys.stderr)
    print(f"  Opening odds total importance: {odds_pct:.2f}%", file=sys.stderr)
    
    if odds_pct > threshold * 100:
        odds_features = [feat for feat, _ in feat_importance 
                        if any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround'])]
        print(f"  ⚠️  WARNING: Opening odds features account for {odds_pct:.2f}% of feature importance (threshold: {threshold*100:.0f}%)", file=sys.stderr)
        print(f"  Opening odds features: {odds_features}", file=sys.stderr)
        print(f"  Consider increasing regularization or applying feature engineering.", file=sys.stderr)
        return False
    else:
        print(f"  ✅ Feature importance validation passed: {odds_pct:.2f}% from opening odds (threshold: {threshold*100:.0f}%)", file=sys.stderr)
        return True


def _validate_calibration_parameters(calibrator: PlattCalibrator | None, method: str = 'platt') -> bool:
    """Validate that calibration parameters are in normal ranges.
    
    Args:
        calibrator: Trained calibration object (PlattCalibrator or IsotonicCalibrator)
        method: Calibration method ('platt' or 'isotonic')
    
    Returns:
        bool: True if validation passes (parameters in normal ranges), False if fails
    """
    if method == 'platt' and calibrator is not None:
        alpha = calibrator.alpha
        beta = calibrator.beta
        
        alpha_normal = 0.5 <= alpha <= 2.0
        beta_normal = -1.0 <= beta <= 1.0
        
        print(f"\nCalibration parameter validation:", file=sys.stderr)
        if not alpha_normal or not beta_normal:
            print(f"  ⚠️  WARNING: Platt calibration parameters outside normal ranges:", file=sys.stderr)
            print(f"    Alpha: {alpha:.4f} (normal: 0.5-2.0) {'✅' if alpha_normal else '❌'}", file=sys.stderr)
            print(f"    Beta: {beta:.4f} (normal: -1.0 to 1.0) {'✅' if beta_normal else '❌'}", file=sys.stderr)
            print(f"    This suggests the model is producing extreme predictions.", file=sys.stderr)
            print(f"    Consider increasing regularization or checking feature importance.", file=sys.stderr)
            return False
        else:
            print(f"  ✅ Calibration parameter validation passed:", file=sys.stderr)
            print(f"    Alpha: {alpha:.4f} (normal: 0.5-2.0) ✅", file=sys.stderr)
            print(f"    Beta: {beta:.4f} (normal: -1.0 to 1.0) ✅", file=sys.stderr)
            return True
    else:
        # Isotonic calibration doesn't have simple parameter ranges
        # Just log that validation was skipped
        print(f"\nCalibration parameter validation skipped for {method} (no simple parameter ranges)", file=sys.stderr)
        return True


def _validate_calibration_quality(
    platt: PlattCalibrator | None,
    p_base: np.ndarray,
    p_calibrated: np.ndarray,
    y: np.ndarray,
    brier_base: float,
    logloss_base: float,
    ece_base: float | None,
) -> None:
    """Validate calibration quality using monotonicity and improvement checks (not arbitrary ranges)."""
    if platt is None:
        print("  Calibration: None (no validation needed)", file=sys.stderr)
        return
    
    print(f"Calibration quality validation:", file=sys.stderr)
    print(f"  Platt parameters: alpha={platt.alpha:.6f}, beta={platt.beta:.6f}", file=sys.stderr)
    
    # Check A) Monotonicity: sorted p_base should produce non-decreasing p_calibrated
    sort_idx = np.argsort(p_base)
    p_base_sorted = p_base[sort_idx]
    p_calibrated_sorted = p_calibrated[sort_idx]
    # Check if p_calibrated is non-decreasing (allow small numerical errors)
    diffs = np.diff(p_calibrated_sorted)
    monotonic_ok = np.all(diffs >= -1e-10)  # Allow tiny numerical errors
    if not monotonic_ok:
        violations = np.sum(diffs < -1e-10)
        print(f"  ⚠️  WARNING: Calibration violates monotonicity ({violations} violations)", file=sys.stderr)
        print(f"      This suggests the Platt formula/apply method may be incorrect", file=sys.stderr)
    else:
        print(f"  ✅ Calibration is monotonic", file=sys.stderr)
    
    # Check B) Calibration actually improved metrics
    brier_calibrated = brier(p_calibrated, y)
    logloss_calibrated = logloss(p_calibrated, y)
    ece_calibrated = ece_binned(p_calibrated, y, bins=10)
    
    brier_improved = brier_calibrated < brier_base
    logloss_improved = logloss_calibrated < logloss_base
    ece_improved = (ece_calibrated is not None and ece_base is not None and ece_calibrated < ece_base) if ece_calibrated is not None else None
    
    print(f"  Metric improvements:", file=sys.stderr)
    print(f"    Brier: {brier_base:.6f} → {brier_calibrated:.6f} ({'✅ improved' if brier_improved else '❌ worse'})", file=sys.stderr)
    print(f"    Log loss: {logloss_base:.6f} → {logloss_calibrated:.6f} ({'✅ improved' if logloss_improved else '❌ worse'})", file=sys.stderr)
    if ece_calibrated is not None and ece_base is not None:
        print(f"    ECE: {ece_base:.6f} → {ece_calibrated:.6f} ({'✅ improved' if ece_improved else '❌ worse'})", file=sys.stderr)
    
    if not (brier_improved or logloss_improved):
        print(f"  ⚠️  WARNING: Calibration did not improve metrics - consider using isotonic or fixing fit input", file=sys.stderr)


def main() -> int:
    start_time = time.time()
    args = parse_args()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting CatBoost model training...", file=sys.stderr)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Output artifact: {args.out_artifact}", file=sys.stderr)
    out_path = Path(args.out_artifact)
    dsn = get_dsn(args.dsn)

    # Load data from ESPN historical tables (Option B: direct ESPN + odds join)
    # Supports Parquet caching for faster iteration (--cache-parquet)
    calib_season_start = int(args.calib_season_start) if args.calib_season_start is not None else None
    
    # Check if we can load from Parquet cache
    cache_path = Path(args.cache_parquet) if args.cache_parquet else None
    if cache_path and cache_path.exists():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Loading training data from Parquet cache: {cache_path}", file=sys.stderr)
        load_start = time.time()
        df = pd.read_parquet(cache_path)
        load_time = time.time() - load_start
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Parquet cache loaded in {load_time:.2f} seconds ({len(df):,} rows)", file=sys.stderr)
    else:
        # Load from database
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connecting to database...", file=sys.stderr)
        with connect(dsn) as conn:
            # Set work_mem for this session (larger hash tables, sorts) - Optimization 4.1
            # Higher work_mem avoids disk spills during sorts/joins (default 4GB, configurable via --work-mem)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Setting work_mem to {args.work_mem} for query optimization...", file=sys.stderr)
            conn.execute(f"SET work_mem = '{args.work_mem}'")
            try:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Loading training data from database...", file=sys.stderr)
                print(f"  Train season max: {args.train_season_start_max}", file=sys.stderr)
                print(f"  Test season: {args.test_season_start}", file=sys.stderr)
                print(f"  Calib season: {calib_season_start}", file=sys.stderr)
                print(f"  Use interaction terms: {args.use_interaction_terms}", file=sys.stderr)
                print(f"  Disable opening odds: {args.disable_opening_odds}", file=sys.stderr)
                load_start = time.time()
                df = _load_training_data(
                    conn,
                    train_season_start_max=int(args.train_season_start_max),
                    test_season_start=int(args.test_season_start),
                    calib_season_start=calib_season_start,
                    use_interaction_terms=bool(args.use_interaction_terms),
                )
                load_time = time.time() - load_start
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data loading completed in {load_time:.2f} seconds", file=sys.stderr)
            finally:
                # Reset to default (optional)
                conn.execute("RESET work_mem")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reset work_mem to default", file=sys.stderr)
        
        # Save to Parquet cache if requested
        if cache_path:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saving training data to Parquet cache: {cache_path}", file=sys.stderr)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_path, index=False, compression="snappy")  # Snappy: fastest read/write
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Parquet cache saved ({cache_path.stat().st_size / 1024 / 1024:.1f} MB)", file=sys.stderr)

    # Debug: Print available seasons and row counts BEFORE filtering
    print(f"Total rows loaded from ESPN tables: {len(df)}", file=sys.stderr)
    if "season_start" in df.columns:
        # Use value_counts() for O(n) single-pass instead of O(n·k) per-season scans
        season_counts = df["season_start"].value_counts(dropna=False).sort_index()
        available_seasons = sorted(season_counts.index.tolist())  # Keep for error messages
        print(f"Available seasons BEFORE filtering: {available_seasons}", file=sys.stderr)
        for season, cnt in season_counts.items():
            print(f"  Season {season}: {cnt} rows", file=sys.stderr)
    else:
        print(f"Warning: season_start column not found. Total rows: {len(df)}", file=sys.stderr)
    
    # Check how many rows have final_winning_team before filtering
    rows_with_label = df["final_winning_team"].notna().sum() if "final_winning_team" in df.columns else 0
    rows_without_label = len(df) - rows_with_label
    print(f"Rows with final_winning_team: {rows_with_label}, without: {rows_without_label}", file=sys.stderr)
    
    if len(df) == 0:
        raise SystemExit("No data loaded from canonical dataset. Check database connection and data availability.")
    
    # Filter out rows without labels (defensive) - Optimization 3.1 & 3.2: Only copy if needed, combine filters
    # Check if we need to filter and if copy is necessary
    has_null_labels = df["final_winning_team"].isna().any() if "final_winning_team" in df.columns else False
    if has_null_labels:
        # Only copy if we're going to modify the dataframe
        df = df[df["final_winning_team"].notna()].copy()
    else:
        # No nulls, no need to filter or copy
        pass
    
    print(f"Rows after filtering for final_winning_team: {len(df)}", file=sys.stderr)
    
    # Debug: Print available seasons AFTER filtering
    if "season_start" in df.columns and len(df) > 0:
        # Use value_counts() for O(n) single-pass instead of O(n·k) per-season scans
        season_counts_after = df["season_start"].value_counts(dropna=False).sort_index()
        print(f"Available seasons AFTER filtering: {sorted(season_counts_after.index.tolist())}", file=sys.stderr)
        for season, cnt in season_counts_after.items():
            print(f"  Season {season}: {cnt} rows", file=sys.stderr)

    # Set fixed random seed for reproducibility (if any randomness is introduced later)
    np.random.seed(42)
    
    # Build y_home_win
    y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)

    season = df["season_start"].astype(int).to_numpy()
    # FIXED: Always respect --train-season-start-max, AND exclude calibration season if enabled
    # This ensures --train-season-start-max 2021 --calib-season-start 2023 doesn't accidentally include 2022
    train_mask = season <= int(args.train_season_start_max)
    if args.calib_season_start is not None and not bool(args.disable_calibration):
        # Also exclude calibration season from training to prevent data leakage
        train_mask = train_mask & (season != int(args.calib_season_start))
        print(f"  Training: season <= {args.train_season_start_max} AND season != {args.calib_season_start}", file=sys.stderr)
    else:
        print(f"  Training: season <= {args.train_season_start_max} (no calibration exclusion)", file=sys.stderr)
    test_mask = season == int(args.test_season_start)
    calib_mask = (season == int(args.calib_season_start)) if args.calib_season_start is not None else np.zeros(len(season), dtype=bool)
    
    # Persist split keys (game_ids) to file for reproducibility verification
    if args.save_split_file:
        split_file_path = Path(args.save_split_file)
        split_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract unique game_ids for each split
        train_game_ids = sorted(df.loc[train_mask, "game_id"].unique().tolist())
        test_game_ids = sorted(df.loc[test_mask, "game_id"].unique().tolist())
        calib_game_ids = sorted(df.loc[calib_mask, "game_id"].unique().tolist()) if args.calib_season_start is not None else []
        
        split_data = {
            "train_season_start_max": int(args.train_season_start_max),
            "test_season_start": int(args.test_season_start),
            "calib_season_start": int(args.calib_season_start) if args.calib_season_start is not None else None,
            "train_game_ids": train_game_ids,
            "test_game_ids": test_game_ids,
            "calib_game_ids": calib_game_ids,
            "train_game_count": len(train_game_ids),
            "test_game_count": len(test_game_ids),
            "calib_game_count": len(calib_game_ids),
            "train_snapshot_count": int(np.sum(train_mask)),
            "test_snapshot_count": int(np.sum(test_mask)),
            "calib_snapshot_count": int(np.sum(calib_mask)),
        }
        
        split_file_path.write_text(json.dumps(split_data, indent=2) + "\n", encoding="utf-8")
        print(f"Saved split file to {split_file_path}", file=sys.stderr)
        print(f"  Train: {len(train_game_ids)} games, {int(np.sum(train_mask))} snapshots", file=sys.stderr)
        print(f"  Test: {len(test_game_ids)} games, {int(np.sum(test_mask))} snapshots", file=sys.stderr)
        if args.calib_season_start is not None:
            print(f"  Calib: {len(calib_game_ids)} games, {int(np.sum(calib_mask))} snapshots", file=sys.stderr)

    min_train = max(5, int(args.min_train_rows))
    train_rows = int(np.sum(train_mask))
    test_rows = int(np.sum(test_mask))
    calib_rows = int(np.sum(calib_mask))
    
    print(f"\nSplit summary:", file=sys.stderr)
    print(f"  Training (season_start <= {args.train_season_start_max}): {train_rows} rows", file=sys.stderr)
    if args.calib_season_start is not None:
        print(f"  Calibration (season_start == {args.calib_season_start}): {calib_rows} rows", file=sys.stderr)
    else:
        print(f"  Calibration: disabled (no --calib-season-start specified)", file=sys.stderr)
    print(f"  Test (season_start == {args.test_season_start}): {test_rows} rows", file=sys.stderr)
    
    if train_rows < min_train:
        available_seasons_str = ", ".join(map(str, available_seasons)) if "season_start" in df.columns else "unknown"
        raise SystemExit(
            f"\nERROR: Training set has < {min_train} rows after filtering (got {train_rows}).\n"
            f"Available seasons: {available_seasons_str}\n"
            f"Current filter: season_start <= {args.train_season_start_max}\n"
            f"Suggestions:\n"
            f"  - Adjust --train-season-start-max to match available seasons (e.g., --train-season-start-max {max(available_seasons) if available_seasons else 2025})\n"
            f"  - Or reduce --min-train-rows (current: {min_train})"
        )
    if test_rows <= 0:
        available_seasons_str = ", ".join(map(str, available_seasons)) if "season_start" in df.columns else "unknown"
        raise SystemExit(
            f"\nERROR: Test season ({args.test_season_start}) has 0 rows in ESPN tables.\n"
            f"Available seasons: {available_seasons_str}\n"
            f"Suggestions:\n"
            f"  - Adjust --test-season-start to match available seasons (e.g., --test-season-start {max(available_seasons) if available_seasons else 2025})"
        )

    # Preprocess params computed from train rows only.
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing preprocessing parameters from training data...", file=sys.stderr)
    pd_train = df.loc[train_mask, "point_differential"].astype(float).to_numpy()
    tr_train = df.loc[train_mask, "time_remaining_regulation"].astype(float).to_numpy()
    pd_mean = float(np.mean(pd_train))
    pd_std = float(np.std(pd_train, ddof=0))
    tr_mean = float(np.mean(tr_train))
    tr_std = float(np.std(tr_train, ddof=0))
    if pd_std == 0.0:
        pd_std = 1.0
    if tr_std == 0.0:
        tr_std = 1.0
    print(f"  Point diff: mean={pd_mean:.4f}, std={pd_std:.4f}", file=sys.stderr)
    print(f"  Time remaining: mean={tr_mean:.4f}, std={tr_std:.4f}", file=sys.stderr)
    
    # Calculate normalization params for interaction terms if enabled
    use_interaction_terms = bool(args.use_interaction_terms)
    interaction_params = {}
    if use_interaction_terms:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing interaction term normalization parameters...", file=sys.stderr)
        if "score_diff_div_sqrt_time_remaining" in df.columns:
            sddst_train = df.loc[train_mask, "score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
            sddst_train = sddst_train[~np.isnan(sddst_train)]
            if len(sddst_train) > 0:
                interaction_params["score_diff_div_sqrt_time_rem_mean"] = float(np.mean(sddst_train))
                interaction_params["score_diff_div_sqrt_time_rem_std"] = float(np.std(sddst_train, ddof=0)) or 1.0
        
        if "espn_home_prob" in df.columns:
            ehp_train = df.loc[train_mask, "espn_home_prob"].astype(float).to_numpy()
            ehp_train = ehp_train[~np.isnan(ehp_train)]
            if len(ehp_train) > 0:
                interaction_params["espn_home_prob_mean"] = float(np.mean(ehp_train))
                interaction_params["espn_home_prob_std"] = float(np.std(ehp_train, ddof=0)) or 1.0
        
        if "espn_home_prob_lag_1" in df.columns:
            ehpl1_train = df.loc[train_mask, "espn_home_prob_lag_1"].astype(float).to_numpy()
            ehpl1_train = ehpl1_train[~np.isnan(ehpl1_train)]
            if len(ehpl1_train) > 0:
                interaction_params["espn_home_prob_lag_1_mean"] = float(np.mean(ehpl1_train))
                interaction_params["espn_home_prob_lag_1_std"] = float(np.std(ehpl1_train, ddof=0)) or 1.0
        
        if "espn_home_prob_delta_1" in df.columns:
            ehpd1_train = df.loc[train_mask, "espn_home_prob_delta_1"].astype(float).to_numpy()
            ehpd1_train = ehpd1_train[~np.isnan(ehpd1_train)]
            if len(ehpd1_train) > 0:
                interaction_params["espn_home_prob_delta_1_mean"] = float(np.mean(ehpd1_train))
                interaction_params["espn_home_prob_delta_1_std"] = float(np.std(ehpd1_train, ddof=0)) or 1.0
        
        # REMOVED: opening_prob_home_fair_time_weighted normalization (feature removed to prevent double-feeding)
        # NOTE: Removed opening_spread and opening_total time interactions (redundant features)
        print(f"  Computed {len(interaction_params)} interaction term parameters", file=sys.stderr)
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Interaction terms disabled, skipping normalization", file=sys.stderr)
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Creating PreprocessParams object...", file=sys.stderr)
    preprocess = PreprocessParams(
        point_diff_mean=pd_mean,
        point_diff_std=pd_std,
        time_rem_mean=tr_mean,
        time_rem_std=tr_std,
        **interaction_params
    )

    # ============================================================================
    # OPTIMIZATION: Build X_all ONCE and slice by masks (eliminates 3x repeated work)
    # ============================================================================
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Building design matrix for ALL data (build once, slice later)...", file=sys.stderr)
    print(f"  Total samples: {len(df):,} (train: {train_rows:,}, calib: {calib_rows:,}, test: {test_rows:,})", file=sys.stderr)
    
    # Extract column arrays ONCE (avoid repeated .to_numpy() calls)
    point_diff_all = df["point_differential"].to_numpy(dtype=np.float64)
    time_rem_all = df["time_remaining_regulation"].to_numpy(dtype=np.float64)
    possession_all = df["possession"].to_numpy()  # Pass as array, vectorized encoding handles it
    
    build_matrix_kwargs = {
        "point_differential": point_diff_all,
        "time_remaining_regulation": time_rem_all,
        "possession": possession_all,
        "preprocess": preprocess,
    }
    
    # Add interaction terms if enabled
    if use_interaction_terms:
        if "score_diff_div_sqrt_time_remaining" in df.columns:
            build_matrix_kwargs["score_diff_div_sqrt_time_remaining"] = df["score_diff_div_sqrt_time_remaining"].to_numpy(dtype=np.float64)
        if "espn_home_prob" in df.columns:
            build_matrix_kwargs["espn_home_prob"] = df["espn_home_prob"].to_numpy(dtype=np.float64)
        if "espn_home_prob_lag_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_lag_1"] = df["espn_home_prob_lag_1"].to_numpy(dtype=np.float64)
        if "espn_home_prob_delta_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_delta_1"] = df["espn_home_prob_delta_1"].to_numpy(dtype=np.float64)
        if "period" in df.columns:
            # Pass as numpy array - _safe_int_or_zero handles NaN/None robustly
            build_matrix_kwargs["period"] = df["period"].to_numpy()
        
        # REMOVED: opening_prob_home_fair_time_weighted (double-feeding odds - baseline already provides this signal)
        # NOTE: Removed opening_spread and opening_total time interactions (redundant features)
    
    # Add opening odds features if available and not disabled
    # FIXED: Removed opening_prob_home_fair (used as baseline instead), removed opening_spread and opening_total (redundant)
    # Keep only opening_overround (has_opening_spread and has_opening_total removed)
    if not args.disable_opening_odds:
        if "opening_overround" in df.columns:
            build_matrix_kwargs["opening_overround"] = df["opening_overround"].to_numpy(dtype=np.float64)
        # CatBoost can use NaN as signal, so keep them (default changed to "zero" for logreg safety)
        build_matrix_kwargs["odds_nan_policy"] = "keep"
        print(f"  Added {len([k for k in build_matrix_kwargs.keys() if 'opening' in k.lower()])} opening odds features (opening_prob_home_fair used as baseline, opening_spread/total removed)", file=sys.stderr)
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Constructing design matrix...", file=sys.stderr)
    matrix_start = time.time()
    X_all = build_design_matrix(**build_matrix_kwargs)
    matrix_time = time.time() - matrix_start
    print(f"  Design matrix shape: {X_all.shape}", file=sys.stderr)
    print(f"  Design matrix construction took {matrix_time:.2f} seconds", file=sys.stderr)
    
    # Slice X_all by masks (views, not copies - very fast)
    X_train = X_all[train_mask]
    y_train = y[train_mask]
    print(f"  X_train shape: {X_train.shape}", file=sys.stderr)

    # Feature ordering by contract (base + optional interaction terms + opening odds)
    # IMPORTANT: Build feature_names BEFORE asserting (avoid UnboundLocalError)
    feature_names = [
        "point_differential_scaled",
        "time_remaining_regulation_scaled",
        "possession_home",
        "possession_away",
        "possession_unknown",
    ]
    
    # Add interaction term feature names if enabled
    if use_interaction_terms:
        if "score_diff_div_sqrt_time_remaining" in df.columns:
            feature_names.append("score_diff_div_sqrt_time_remaining_scaled")
        if "espn_home_prob" in df.columns:
            feature_names.append("espn_home_prob_scaled")
        if "espn_home_prob_lag_1" in df.columns:
            feature_names.append("espn_home_prob_lag_1_scaled")
        if "espn_home_prob_delta_1" in df.columns:
            feature_names.append("espn_home_prob_delta_1_scaled")
        if "period" in df.columns:
            feature_names.extend(["period_1", "period_2", "period_3", "period_4"])
    
    # Add opening odds feature names if available and not disabled
    # NOTE: opening_prob_home_fair used as baseline (not a feature)
    # NOTE: opening_spread and opening_total removed (redundant)
    # NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
    if not args.disable_opening_odds:
        if "opening_overround" in df.columns:
            feature_names.append("opening_overround")
    
    # CRITICAL: Assert feature count matches design matrix columns (after building feature_names)
    if X_train.shape[1] != len(feature_names):
        raise RuntimeError(
            f"Feature mismatch: X_train has {X_train.shape[1]} columns, but feature_names has {len(feature_names)} features.\n"
            f"This indicates a bug in feature_names construction or build_design_matrix()."
        )
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Feature summary:", file=sys.stderr)
    print(f"  Total features: {len(feature_names)}", file=sys.stderr)
    print(f"  Base features: 5 (point_diff, time_rem, possession)", file=sys.stderr)
    if use_interaction_terms:
        interaction_count = len([f for f in feature_names if 'scaled' in f and 'opening' not in f.lower()])
        print(f"  Interaction features: {interaction_count}", file=sys.stderr)
    odds_feature_count = len([f for f in feature_names if any(term in f.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround'])])
    if odds_feature_count > 0:
        print(f"  Opening odds features: {odds_feature_count}", file=sys.stderr)

    # Train CatBoost model
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initializing CatBoost model...", file=sys.stderr)
    print(f"  Iterations: {args.iterations}", file=sys.stderr)
    print(f"  Depth: 3 (reduced from {args.depth} for stronger regularization)", file=sys.stderr)
    print(f"  Learning rate: {args.learning_rate}", file=sys.stderr)
    print(f"  Regularization: l2_leaf_reg=20.0, subsample=0.8, random_strength=1.0, bagging_temperature=1.0", file=sys.stderr)
    model = CatBoostClassifier(
        iterations=int(args.iterations),
        depth=3,  # REDUCE from 4 to 3 for stronger regularization
        learning_rate=float(args.learning_rate),
        l2_leaf_reg=20.0,  # INCREASE from 10.0 to 20.0 for stronger regularization
        subsample=0.8,  # ADD: Use 80% of data per tree for regularization
        random_strength=1.0,  # ADD: Regularization
        bagging_temperature=1.0,  # ADD: Regularization
        loss_function='Logloss',
        eval_metric='AUC',
        verbose=500,  # Optimization 2.1: Reduced verbosity (was 100)
        random_seed=42,
        allow_writing_files=False,  # Don't write temp files
        thread_count=-1,  # Optimization 2.2: Use all available CPU cores
    )
    
    # ============================================================================
    # OPTIMIZATION: Compute baseline_all ONCE and slice by masks
    # ============================================================================
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing CatBoost baseline from opening odds (build once, slice later)...", file=sys.stderr)
    baseline_all = np.zeros(len(df), dtype=np.float64)
    uses_opening_odds_baseline = False  # Track if baseline was actually used in TRAINING (not just CLI flag)
    if not args.disable_opening_odds and "opening_prob_home_fair" in df.columns:
        p0_all = df["opening_prob_home_fair"].to_numpy(dtype=np.float64)
        # Check if any rows have opening odds (use opening_overround to infer)
        has_odds_all = (~df["opening_overround"].isna()).to_numpy() if "opening_overround" in df.columns else np.zeros(len(df), dtype=bool)
        # Set baseline to logit(opening_prob_home_fair) when odds available, else 0.0 (50/50 prior)
        baseline_all[has_odds_all] = logit(p0_all[has_odds_all])
        odds_baseline_count = int(np.sum(has_odds_all))
        print(f"  Baseline set from opening_prob_home_fair for {odds_baseline_count:,} samples ({100.0 * odds_baseline_count / len(df):.1f}%)", file=sys.stderr)
        print(f"  Baseline stats: min={baseline_all.min():.4f}, max={baseline_all.max():.4f}, mean={baseline_all.mean():.4f}", file=sys.stderr)
    else:
        print(f"  No opening odds available, using zero baseline (50/50 prior)", file=sys.stderr)
    
    # Slice baseline by masks
    baseline_train = baseline_all[train_mask]
    baseline_calib = baseline_all[calib_mask]
    baseline_test = baseline_all[test_mask]
    
    # CRITICAL: Flag must be based on TRAINING data only (not test/calib)
    # If only test/calib has odds but train has none, model wasn't trained with baseline
    if not args.disable_opening_odds and "opening_prob_home_fair" in df.columns:
        # Infer has_odds from opening_prob_home_fair (not NaN = has odds) or opening_overround
        p0_train = df.loc[train_mask, "opening_prob_home_fair"].to_numpy(dtype=np.float64)
        has_odds_train = ~np.isnan(p0_train) if "opening_prob_home_fair" in df.columns else (~df.loc[train_mask, "opening_overround"].isna()).to_numpy() if "opening_overround" in df.columns else np.zeros(train_mask.sum(), dtype=bool)
        odds_baseline_count_train = int(np.sum(has_odds_train))
        uses_opening_odds_baseline = odds_baseline_count_train > 0
        if uses_opening_odds_baseline:
            print(f"  Baseline used in training: {odds_baseline_count_train:,} training samples ({100.0 * odds_baseline_count_train / train_rows:.1f}%)", file=sys.stderr)
        else:
            print(f"  WARNING: Opening odds enabled but no TRAINING samples had valid odds - baseline effectively zero for training", file=sys.stderr)
    
    # Prepare calibration set if available (slice from X_all, don't rebuild)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Preparing calibration set...", file=sys.stderr)
    eval_set = None
    X_calib = None
    y_calib = None
    if calib_season_start is not None and int(np.sum(calib_mask)) >= 5:
        # Slice from X_all (already built)
        X_calib = X_all[calib_mask]
        y_calib = y[calib_mask]
        print(f"  X_calib shape: {X_calib.shape} (sliced from X_all)", file=sys.stderr)
        eval_set = (X_calib, y_calib)
    else:
        print(f"  No calibration set (calib_season_start={calib_season_start}, calib_samples={int(np.sum(calib_mask))})", file=sys.stderr)
    
    # Create Pool objects with baseline for training and evaluation
    train_pool = Pool(X_train, y_train, baseline=baseline_train)
    eval_pool = None
    if eval_set is not None:
        eval_pool = Pool(eval_set[0], eval_set[1], baseline=baseline_calib)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting CatBoost model training...", file=sys.stderr)
    print(f"  This may take 30-60 minutes depending on data size and iterations...", file=sys.stderr)
    train_start = time.time()
    model.fit(train_pool, eval_set=eval_pool)
    train_time = time.time() - train_start
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CatBoost training completed in {train_time/60:.2f} minutes ({train_time:.2f} seconds)", file=sys.stderr)

    # Validate feature importance before creating artifact
    # Create temporary artifact for validation (will be recreated properly later)
    temp_artifact = WinProbArtifact(
        created_at_utc=utc_now_iso_compact(),
        version=str(args.version),
        train_season_start_max=int(args.train_season_start_max),
        calib_season_start=(None if bool(args.disable_calibration) else calib_season_start),
        test_season_start=int(args.test_season_start),
        buckets_seconds_remaining=_calculate_buckets(df["time_remaining_regulation"], args.bucket_step_seconds),
        preprocess=preprocess,
        feature_names=feature_names,
        model=ModelParams(weights=[0.0] * len(feature_names), intercept=0.0, l2_lambda=0.0, max_iter=0, tol=0.0),
        platt=None,
        isotonic=None,
        model_type="catboost",
        catboost_model_path=None,
        uses_opening_odds_baseline=uses_opening_odds_baseline,  # Based on actual baseline usage, not CLI flag
    )
    _validate_feature_importance(model, temp_artifact)

    # Save CatBoost model to .cbm file
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saving CatBoost model to disk...", file=sys.stderr)
    catboost_model_path = out_path.with_suffix(".cbm")
    save_start = time.time()
    model.save_model(str(catboost_model_path))
    save_time = time.time() - save_start
    print(f"  Saved CatBoost model to {catboost_model_path} ({save_time:.2f} seconds)", file=sys.stderr)
    print(f"  Model file size: {catboost_model_path.stat().st_size / (1024*1024):.2f} MB", file=sys.stderr)
    
    # Store relative path in artifact
    catboost_model_path_rel = catboost_model_path.name  # Just the filename, assume same directory

    # Optional calibration on calibration season (Platt or Isotonic).
    platt = None
    isotonic = None
    if not bool(args.disable_calibration) and calib_season_start is not None and int(np.sum(calib_mask)) >= 5:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting calibration...", file=sys.stderr)
        print(f"  Method: {args.calibration_method}", file=sys.stderr)
        print(f"  Calibration samples: {len(y_calib):,}", file=sys.stderr)
        
        # Get base model probabilities and raw margins for calibration
        # FIXED: Must use Pool with baseline for calibration prediction to match training
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing base model probabilities for calibration...", file=sys.stderr)
        calib_pred_start = time.time()
        # Compute baseline for calibration set (same as eval_pool baseline)
        baseline_calib = np.zeros(len(X_calib), dtype=np.float64)
        if not args.disable_opening_odds and "opening_prob_home_fair" in df.columns:
            p0_calib = df.loc[calib_mask, "opening_prob_home_fair"].to_numpy(dtype=np.float64)
            # Check if any rows have opening odds in calibration set (use opening_overround to infer)
            has_odds_calib = (~df.loc[calib_mask, "opening_overround"].isna()).to_numpy() if "opening_overround" in df.columns else np.zeros(calib_mask.sum(), dtype=bool)
            baseline_calib[has_odds_calib] = logit(p0_calib[has_odds_calib])
        # Use Pool with baseline to match training
        calib_pool = Pool(X_calib, baseline=baseline_calib)
        p_base = model.predict_proba(calib_pool)[:, 1].astype(np.float64)
        # Compute total logits for Platt fitting
        # SIMPLIFIED: logit(p_base) is always the correct input for Platt fitting
        # Whether baseline was used or not, logit(p_base) equals what Platt.apply() uses internally
        # This avoids branching and the NameError risk when has_odds_calib isn't defined
        total_logits = logit(p_base)
        y_calib = y[calib_mask]
        calib_pred_time = time.time() - calib_pred_start
        print(f"  Base probability computation took {calib_pred_time:.2f} seconds", file=sys.stderr)
        print(f"  Base probability stats: min={p_base.min():.4f}, max={p_base.max():.4f}, mean={p_base.mean():.4f}", file=sys.stderr)
        
        # Calculate calibration quality metrics BEFORE calibration
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing calibration quality metrics (before calibration)...", file=sys.stderr)
        brier_base_calib = brier(p_base, y_calib)
        logloss_base_calib = logloss(p_base, y_calib)
        ece_base_calib = ece_binned(p_base, y_calib, bins=10)
        print(f"  Calibration set (before):", file=sys.stderr)
        print(f"    Brier score: {brier_base_calib:.6f}", file=sys.stderr)
        print(f"    Log loss: {logloss_base_calib:.6f}", file=sys.stderr)
        print(f"    ECE (10 bins): {ece_base_calib:.6f}" if ece_base_calib is not None else "    ECE (10 bins): N/A", file=sys.stderr)
        
        # Fit calibration based on method
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fitting {args.calibration_method} calibrator...", file=sys.stderr)
        calib_fit_start = time.time()
        if args.calibration_method == "isotonic":
            isotonic = fit_isotonic_calibrator_on_probs(p_base=p_base, y=y_calib)
            print(f"  Isotonic calibration completed in {time.time() - calib_fit_start:.2f} seconds", file=sys.stderr)
            # Apply calibration and compute metrics
            p_calibrated = isotonic.apply(p_base)
            brier_calibrated_calib = brier(p_calibrated, y_calib)
            logloss_calibrated_calib = logloss(p_calibrated, y_calib)
            ece_calibrated_calib = ece_binned(p_calibrated, y_calib, bins=10)
        else:  # default to platt
            # Fit Platt on total_logits (= baseline + raw_margin when baseline used, or raw_margin otherwise)
            # This is consistent with apply() which uses logit(p_base) = total_logits
            platt = fit_platt_calibrator_on_raw_margins(raw_margins=total_logits, y=y_calib)
            calib_fit_time = time.time() - calib_fit_start
            print(f"  Platt calibration completed in {calib_fit_time:.2f} seconds", file=sys.stderr)
            # Apply calibration first to get p_calibrated for validation
            p_calibrated = platt.apply(p_base)
            # Validate calibration parameters (check if in normal ranges)
            _validate_calibration_parameters(platt, method='platt')
            # Validate calibration (monotonicity and improvement checks instead of arbitrary ranges)
            _validate_calibration_quality(platt, p_base, p_calibrated, y_calib, brier_base_calib, logloss_base_calib, ece_base_calib)
            # Recompute metrics after validation (p_calibrated already computed above)
            brier_calibrated_calib = brier(p_calibrated, y_calib)
            logloss_calibrated_calib = logloss(p_calibrated, y_calib)
            ece_calibrated_calib = ece_binned(p_calibrated, y_calib, bins=10)
        
        # Print calibration quality metrics AFTER calibration
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Calibration quality metrics (after calibration):", file=sys.stderr)
        print(f"  Calibration set (after):", file=sys.stderr)
        print(f"    Brier score: {brier_calibrated_calib:.6f} (improvement: {brier_base_calib - brier_calibrated_calib:+.6f})", file=sys.stderr)
        print(f"    Log loss: {logloss_calibrated_calib:.6f} (improvement: {logloss_base_calib - logloss_calibrated_calib:+.6f})", file=sys.stderr)
        print(f"    ECE (10 bins): {ece_calibrated_calib:.6f}" if ece_calibrated_calib is not None else "    ECE (10 bins): N/A", file=sys.stderr)
        if ece_base_calib is not None and ece_calibrated_calib is not None:
            print(f"      (ECE improvement: {ece_base_calib - ece_calibrated_calib:+.6f})", file=sys.stderr)
        
        # Also evaluate on test set if available
        if int(np.sum(test_mask)) >= 5:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Evaluating calibration on test set...", file=sys.stderr)
            # Slice test set from X_all (already built)
            X_test = X_all[test_mask]
            y_test = y[test_mask]
            print(f"  X_test shape: {X_test.shape} (sliced from X_all)", file=sys.stderr)
            
            # Assert feature count matches (test uses same feature_names as training)
            if X_test.shape[1] != len(feature_names):
                raise RuntimeError(
                    f"Feature mismatch: X_test has {X_test.shape[1]} columns, but feature_names has {len(feature_names)} features.\n"
                    f"This indicates a bug in feature_names construction or build_design_matrix()."
                )
            
            # Baseline already sliced above (baseline_test = baseline_all[test_mask])
            
            # Get base probabilities and raw margins
            test_pool = Pool(X_test, baseline=baseline_test)
            p_base_test = model.predict_proba(test_pool)[:, 1].astype(np.float64)
            # Note: Raw margins not needed for test evaluation (calibration already fitted)
            
            # Compute metrics before calibration
            brier_base_test = brier(p_base_test, y_test)
            logloss_base_test = logloss(p_base_test, y_test)
            ece_base_test = ece_binned(p_base_test, y_test, bins=10)
            
            # Apply calibration
            if args.calibration_method == "isotonic":
                p_calibrated_test = isotonic.apply(p_base_test)
            else:
                p_calibrated_test = platt.apply(p_base_test)
            
            # Compute metrics after calibration
            brier_calibrated_test = brier(p_calibrated_test, y_test)
            logloss_calibrated_test = logloss(p_calibrated_test, y_test)
            ece_calibrated_test = ece_binned(p_calibrated_test, y_test, bins=10)
            
            # Print test set metrics
            print(f"  Test set (before calibration):", file=sys.stderr)
            print(f"    Brier score: {brier_base_test:.6f}", file=sys.stderr)
            print(f"    Log loss: {logloss_base_test:.6f}", file=sys.stderr)
            print(f"    ECE (10 bins): {ece_base_test:.6f}" if ece_base_test is not None else "    ECE (10 bins): N/A", file=sys.stderr)
            print(f"  Test set (after calibration):", file=sys.stderr)
            print(f"    Brier score: {brier_calibrated_test:.6f} (improvement: {brier_base_test - brier_calibrated_test:+.6f})", file=sys.stderr)
            print(f"    Log loss: {logloss_calibrated_test:.6f} (improvement: {logloss_base_test - logloss_calibrated_test:+.6f})", file=sys.stderr)
            print(f"    ECE (10 bins): {ece_calibrated_test:.6f}" if ece_calibrated_test is not None else "    ECE (10 bins): N/A", file=sys.stderr)
            if ece_base_test is not None and ece_calibrated_test is not None:
                print(f"      (ECE improvement: {ece_base_test - ece_calibrated_test:+.6f})", file=sys.stderr)
    else:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Calibration skipped (disabled or insufficient data)", file=sys.stderr)

    # Create dummy ModelParams for artifact structure (not used for CatBoost prediction)
    model_params = ModelParams(
        weights=[0.0] * len(feature_names),  # Dummy weights
        intercept=0.0,  # Dummy intercept
        l2_lambda=0.0,
        max_iter=0,
        tol=0.0,
    )

    artifact = WinProbArtifact(
        created_at_utc=utc_now_iso_compact(),
        version=str(args.version),
        train_season_start_max=int(args.train_season_start_max),
        calib_season_start=(None if bool(args.disable_calibration) else calib_season_start),
        test_season_start=int(args.test_season_start),
        buckets_seconds_remaining=_calculate_buckets(df["time_remaining_regulation"], args.bucket_step_seconds),
        preprocess=preprocess,
        feature_names=feature_names,
        model=model_params,  # Dummy, not used for CatBoost
        platt=platt,
        isotonic=isotonic,
        model_type="catboost",
        catboost_model_path=catboost_model_path_rel,
        uses_opening_odds_baseline=uses_opening_odds_baseline,  # Based on actual baseline usage, not CLI flag
    )

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Creating and saving artifact...", file=sys.stderr)
    artifact_start = time.time()
    save_artifact(out_path, artifact)
    artifact_save_time = time.time() - artifact_start
    print(f"  Artifact saved in {artifact_save_time:.2f} seconds", file=sys.stderr)
    
    # Reload roundtrip sanity.
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verifying artifact (roundtrip test)...", file=sys.stderr)
    verify_start = time.time()
    _ = load_artifact(out_path)
    verify_time = time.time() - verify_start
    print(f"  Artifact verification passed in {verify_time:.2f} seconds", file=sys.stderr)
    
    total_time = time.time() - start_time
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Model training completed successfully!", file=sys.stderr)
    print(f"  Total time: {total_time/60:.2f} minutes ({total_time:.2f} seconds)", file=sys.stderr)
    print(f"  Artifact: {out_path}", file=sys.stderr)
    print(f"  Model file: {catboost_model_path}", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

