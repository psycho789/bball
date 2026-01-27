#!/usr/bin/env python3
"""
Evaluate win probability models with time-bucketed metrics.

This script computes Brier score and log-loss overall and by time bucket
to assess model performance across different phases of the game.

Time Buckets:
- 2880-2400s: First 8 minutes (Q1 start)
- 2400-1800s: Q1 end to Q2 mid
- 1800-1200s: Q2 mid to Q3 mid
- 1200-600s: Q3 mid to Q4 mid
- 600-120s: Q4 mid to final 2 minutes
- 120-0s: Final 2 minutes

Usage:
  python scripts/model/evaluate_winprob_time_buckets.py \
    --baseline-artifact artifacts/winprob_catboost_baseline.json \
    --odds-artifact artifacts/winprob_catboost_odds.json \
    --dsn "$DATABASE_URL" \
    --test-season-start 2024
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

# Add project root to path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    WinProbArtifact,
    load_artifact,
    build_design_matrix,
    predict_proba,
    ODDS_FEATURES,
)


def assign_time_bucket(time_remaining: float) -> str:
    """Assign time bucket based on time_remaining."""
    if time_remaining > 2400:
        return "2880-2400"
    elif time_remaining > 1800:
        return "2400-1800"
    elif time_remaining > 1200:
        return "1800-1200"
    elif time_remaining > 600:
        return "1200-600"
    elif time_remaining > 120:
        return "600-120"
    else:
        return "120-0"


def load_test_data(conn, test_season_start: int, artifact: WinProbArtifact) -> pd.DataFrame:
    """Load test set data matching the artifact's feature requirements."""
    # Load from ESPN tables (same as training, but only test season)
    query = """
    WITH espn_base AS (
        SELECT
            p.game_id,
            p.sequence_number,
            p.season_label,
            CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) AS season_start,
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
        LEFT JOIN espn.prob_event_state e 
            ON p.game_id = e.game_id 
            AND p.event_id = e.event_id
        WHERE e.time_remaining IS NOT NULL
            AND e.point_differential IS NOT NULL
            AND CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = {test_season_start}
    ),
    espn_with_lag AS (
        SELECT
            *,
            LAG(espn_home_prob, 1) OVER (PARTITION BY game_id ORDER BY sequence_number) AS espn_home_prob_lag_1
        FROM espn_base
    ),
    opening_odds AS (
        SELECT 
            espn_game_id,
            MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'home') AS opening_moneyline_home,
            MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'away') AS opening_moneyline_away,
            MAX(line_value) FILTER (WHERE market_type = 'spread' AND side = 'home') AS opening_spread,
            MAX(line_value) FILTER (WHERE market_type = 'total' AND side = 'over') AS opening_total
        FROM external.sportsbook_odds_snapshots
        WHERE is_opening_line = TRUE
            AND espn_game_id IS NOT NULL
        GROUP BY espn_game_id
    ),
    espn_with_features AS (
        SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
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
            oo.opening_moneyline_home,
            oo.opening_moneyline_away,
            oo.opening_spread,
            oo.opening_total
        FROM espn_with_lag e
        LEFT JOIN espn.scoreboard_games sg 
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
        e.opening_moneyline_home,
        e.opening_moneyline_away,
        e.opening_spread,
        e.opening_total
    FROM espn_with_features e
    WHERE e.final_winning_team IS NOT NULL
    ORDER BY e.season_label, e.game_id, e.sequence_number
    """.format(test_season_start=test_season_start)
    
    df = pd.read_sql(query, conn)
    
    # Compute opening odds engineered features if needed
    if any(col in df.columns for col in ["opening_moneyline_home", "opening_moneyline_away"]):
        from scripts.lib._winprob_lib import compute_opening_odds_features
        
        if len(df) > 0:
            odds_features = compute_opening_odds_features(
                opening_moneyline_home=df['opening_moneyline_home'].to_numpy() if 'opening_moneyline_home' in df.columns else None,
                opening_moneyline_away=df['opening_moneyline_away'].to_numpy() if 'opening_moneyline_away' in df.columns else None,
                opening_spread=df['opening_spread'].to_numpy() if 'opening_spread' in df.columns else None,
                opening_total=df['opening_total'].to_numpy() if 'opening_total' in df.columns else None,
            )
            
            df['opening_prob_home_fair'] = odds_features['opening_prob_home_fair']
            df['opening_overround'] = odds_features['opening_overround']
    
    return df


def evaluate_model(
    artifact: WinProbArtifact,
    df: pd.DataFrame,
    model_name: str
) -> dict[str, float]:
    """Evaluate model on test set and return metrics."""
    # Build design matrix
    build_kwargs = {
        "point_differential": df["point_differential"].astype(float).to_numpy(),
        "time_remaining_regulation": df["time_remaining_regulation"].astype(float).to_numpy(),
        "possession": df["possession"].astype(str).tolist(),
        "preprocess": artifact.preprocess,
    }
    
    # Add interaction terms if model expects them
    if "score_diff_div_sqrt_time_remaining_scaled" in artifact.feature_names:
        build_kwargs["score_diff_div_sqrt_time_remaining"] = df["score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
    if "espn_home_prob_scaled" in artifact.feature_names:
        build_kwargs["espn_home_prob"] = df["espn_home_prob"].astype(float).to_numpy()
    if "espn_home_prob_lag_1_scaled" in artifact.feature_names:
        build_kwargs["espn_home_prob_lag_1"] = df["espn_home_prob_lag_1"].astype(float).to_numpy()
    if "espn_home_prob_delta_1_scaled" in artifact.feature_names:
        build_kwargs["espn_home_prob_delta_1"] = df["espn_home_prob_delta_1"].astype(float).to_numpy()
    if "period_1" in artifact.feature_names:
        build_kwargs["period"] = df["period"].astype(int).tolist()
    
    # Add opening odds features if model expects them
    # Note: opening_prob_home_fair, opening_spread, opening_total are NOT features - they're baseline inputs
    if "opening_overround" in artifact.feature_names:
        if "opening_overround" in df.columns:
            build_kwargs["opening_overround"] = df["opening_overround"].astype(float).to_numpy()
        # Pass odds_nan_policy="keep" for CatBoost models
        build_kwargs["odds_nan_policy"] = "keep"
    
    X = build_design_matrix(**build_kwargs)
    
    # Get predictions - check if model uses baseline using the artifact flag
    uses_baseline = getattr(artifact, 'uses_opening_odds_baseline', None)
    if uses_baseline is None:
        # Fallback heuristic for older artifacts
        has_opening_odds_features = any("opening" in fn.lower() or "overround" in fn.lower() for fn in artifact.feature_names)
        opening_prob_not_a_feature = "opening_prob_home_fair" not in artifact.feature_names
        uses_baseline = has_opening_odds_features and opening_prob_not_a_feature
    
    if uses_baseline and "opening_prob_home_fair" in df.columns:
        y_pred = predict_proba(
            artifact, 
            X=X,
            opening_prob_home_fair=df["opening_prob_home_fair"].astype(float).to_numpy(),
        )
    else:
        y_pred = predict_proba(artifact, X=X)
    y_true = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy()
    
    # Assign time buckets
    df["time_bucket"] = df["time_remaining_regulation"].apply(assign_time_bucket)
    
    # Compute overall metrics
    brier_overall = float(brier_score_loss(y_true, y_pred))
    logloss_overall = float(log_loss(y_true, y_pred))
    
    # Compute per-bucket metrics
    bucket_metrics = {}
    for bucket in ["2880-2400", "2400-1800", "1800-1200", "1200-600", "600-120", "120-0"]:
        bucket_mask = df["time_bucket"] == bucket
        if np.sum(bucket_mask) > 0:
            y_bucket_true = y_true[bucket_mask]
            y_bucket_pred = y_pred[bucket_mask]
            bucket_metrics[f"brier_{bucket}"] = float(brier_score_loss(y_bucket_true, y_bucket_pred))
            bucket_metrics[f"logloss_{bucket}"] = float(log_loss(y_bucket_true, y_bucket_pred))
            bucket_metrics[f"count_{bucket}"] = int(np.sum(bucket_mask))
        else:
            bucket_metrics[f"brier_{bucket}"] = None
            bucket_metrics[f"logloss_{bucket}"] = None
            bucket_metrics[f"count_{bucket}"] = 0
    
    return {
        "model_name": model_name,
        "brier_overall": brier_overall,
        "logloss_overall": logloss_overall,
        "total_snapshots": len(df),
        **bucket_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate win probability models with time-bucketed metrics")
    parser.add_argument("--baseline-artifact", type=str, required=True, help="Path to baseline model artifact (without opening odds)")
    parser.add_argument("--odds-artifact", type=str, required=True, help="Path to odds-enabled model artifact (with opening odds)")
    parser.add_argument("--dsn", type=str, default=None, help="Database connection string (default: use DATABASE_URL env var)")
    parser.add_argument("--test-season-start", type=int, required=True, help="Test season_start to evaluate on")
    parser.add_argument("--out-results", type=str, default=None, help="Path to save results JSON file (optional)")
    args = parser.parse_args()
    
    # Load artifacts
    baseline_artifact = load_artifact(Path(args.baseline_artifact))
    odds_artifact = load_artifact(Path(args.odds_artifact))
    
    print(f"Loaded baseline artifact: {args.baseline_artifact}", file=sys.stderr)
    print(f"  Features: {len(baseline_artifact.feature_names)}", file=sys.stderr)
    print(f"Loaded odds artifact: {args.odds_artifact}", file=sys.stderr)
    print(f"  Features: {len(odds_artifact.feature_names)}", file=sys.stderr)
    
    # Connect to database and load test data
    dsn = get_dsn(args.dsn)
    with connect(dsn) as conn:
        # Load test data (use odds artifact to determine if opening odds needed)
        print(f"Loading test data for season {args.test_season_start}...", file=sys.stderr)
        df_test = load_test_data(conn, args.test_season_start, odds_artifact)
        print(f"Loaded {len(df_test)} test snapshots", file=sys.stderr)
    
    # Evaluate both models
    print("\nEvaluating baseline model...", file=sys.stderr)
    baseline_metrics = evaluate_model(baseline_artifact, df_test, "baseline")
    
    print("Evaluating odds-enabled model...", file=sys.stderr)
    odds_metrics = evaluate_model(odds_artifact, df_test, "odds_enabled")
    
    # Compute improvements
    brier_improvement = ((baseline_metrics["brier_overall"] - odds_metrics["brier_overall"]) / baseline_metrics["brier_overall"]) * 100
    logloss_improvement = ((baseline_metrics["logloss_overall"] - odds_metrics["logloss_overall"]) / baseline_metrics["logloss_overall"]) * 100
    
    # Print results
    print("\n" + "="*80, file=sys.stderr)
    print("EVALUATION RESULTS", file=sys.stderr)
    print("="*80, file=sys.stderr)
    print(f"\nOverall Metrics:", file=sys.stderr)
    print(f"  Baseline - Brier: {baseline_metrics['brier_overall']:.6f}, Log-Loss: {baseline_metrics['logloss_overall']:.6f}", file=sys.stderr)
    print(f"  Odds-Enabled - Brier: {odds_metrics['brier_overall']:.6f}, Log-Loss: {odds_metrics['logloss_overall']:.6f}", file=sys.stderr)
    print(f"  Improvement - Brier: {brier_improvement:+.2f}%, Log-Loss: {logloss_improvement:+.2f}%", file=sys.stderr)
    
    print(f"\nTime-Bucketed Metrics:", file=sys.stderr)
    print(f"{'Bucket':<15} {'Baseline Brier':<15} {'Odds Brier':<15} {'Brier Δ%':<12} {'Count':<10}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    for bucket in ["2880-2400", "2400-1800", "1800-1200", "1200-600", "600-120", "120-0"]:
        baseline_brier = baseline_metrics.get(f"brier_{bucket}")
        odds_brier = odds_metrics.get(f"brier_{bucket}")
        count = baseline_metrics.get(f"count_{bucket}", 0)
        
        if baseline_brier is not None and odds_brier is not None:
            brier_delta_pct = ((baseline_brier - odds_brier) / baseline_brier) * 100
            print(f"{bucket:<15} {baseline_brier:<15.6f} {odds_brier:<15.6f} {brier_delta_pct:+.2f}%      {count:<10}", file=sys.stderr)
        else:
            print(f"{bucket:<15} {'N/A':<15} {'N/A':<15} {'N/A':<12} {count:<10}", file=sys.stderr)
    
    # Save results if requested
    if args.out_results:
        results = {
            "test_season_start": args.test_season_start,
            "baseline_artifact": str(args.baseline_artifact),
            "odds_artifact": str(args.odds_artifact),
            "baseline_metrics": baseline_metrics,
            "odds_metrics": odds_metrics,
            "improvements": {
                "brier_overall_pct": float(brier_improvement),
                "logloss_overall_pct": float(logloss_improvement),
            },
        }
        
        results_path = Path(args.out_results)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved results to {results_path}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
