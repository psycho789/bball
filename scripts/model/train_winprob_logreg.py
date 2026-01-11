#!/usr/bin/env python3
"""
Train a regularized logistic regression win-probability model from canonical dataset, and save a full pipeline artifact.

This script uses only the repo's existing dependencies (numpy/pandas), avoiding scikit-learn.

Inputs:
- Canonical dataset: derived.snapshot_features_v1 (via DATABASE_URL)

Split policy (leak-proof, game-level by season_start):
- train seasons: season_start <= --train-season-start-max (default 2022)
- calibration season: season_start == --calib-season-start (default 2023), optional
- test season: season_start == --test-season-start (default 2024), not used in training

Features (prediction-time):
- point_differential (home - away)
- time_remaining_regulation
- possession ("home"|"away"|"unknown")

Label:
- y_home_win = 1 if final_winning_team == 0 else 0

Usage:
  ./.venv/bin/python scripts/train_winprob_logreg.py \
    --out-artifact artifacts/winprob_logreg_v1.json \
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    PreprocessParams,
    ModelParams,
    WinProbArtifact,
    build_design_matrix,
    fit_logistic_regression_irls,
    fit_platt_calibrator_on_probs,
    load_artifact,
    predict_proba,
    save_artifact,
    utc_now_iso_compact,
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
    p = argparse.ArgumentParser(description="Train a leak-proof logistic regression win-probability model.")
    p.add_argument("--out-artifact", required=True, help="Output artifact JSON path.")
    p.add_argument("--dsn", help="Database connection string (or use DATABASE_URL env var)")
    p.add_argument("--version", default="v1", help="Artifact version string (default: v1).")
    p.add_argument("--train-season-start-max", type=int, default=2022, help="Max season_start included in training (default: 2022).")
    p.add_argument("--calib-season-start", type=int, default=2023, help="Season_start used for Platt calibration (default: 2023).")
    p.add_argument("--disable-calibration", action="store_true", help="Disable Platt calibration even if calibration season exists.")
    p.add_argument("--test-season-start", type=int, default=2024, help="Held-out test season_start (default: 2024).")
    p.add_argument("--l2-lambda", type=float, default=1.0, help="L2 regularization strength (lambda) (default: 1.0).")
    p.add_argument("--max-iter", type=int, default=50, help="IRLS max iterations (default: 50).")
    p.add_argument("--tol", type=float, default=1e-8, help="IRLS stopping tolerance (default: 1e-8).")
    p.add_argument("--min-train-rows", type=int, default=1000, help="Minimum training rows required (default: 1000).")
    p.add_argument("--bucket-step-seconds", type=int, default=60, help="Bucket step in seconds for artifact metadata (default: 60).")
    p.add_argument("--use-interaction-terms", action="store_true", default=True, help="Use interaction terms from canonical dataset (default: True).")
    p.add_argument("--no-interaction-terms", dest="use_interaction_terms", action="store_false", help="Disable interaction terms (use basic model only).")
    return p.parse_args()


def _load_training_data(conn, train_season_start_max: int, test_season_start: int, calib_season_start: int | None, use_interaction_terms: bool = True) -> pd.DataFrame:
    """
    Load training data directly from ESPN tables (bypasses canonical dataset).
    
    **Why ESPN tables directly?**
    - Training doesn't need Kalshi data (only needed for simulation)
    - ESPN has historical data back to 2017, Kalshi only has 2025-26
    - Canonical dataset is optimized for simulation (ESPN + Kalshi join)
    
    Maps ESPN columns to model features:
    - score_diff -> point_differential
    - time_remaining -> time_remaining_regulation
    - possession -> 'unknown' (not reliably available)
    - final_winning_team (from scoreboard_games join)
    - season_label -> season_start (extract year from "2025-26" -> 2025)
    
    If use_interaction_terms=True, also calculates:
    - score_diff_div_sqrt_time_remaining
    - espn_home_prob (normalized to 0-1)
    - espn_home_prob_lag_1 (using window function)
    - espn_home_prob_delta_1 (current - lag_1)
    - period (calculated from time_remaining)
    """
    # Base query: ESPN probabilities + game state
    base_query = """
    WITH espn_base AS (
        SELECT 
            p.season_label,
            p.game_id,
            p.sequence_number,
            -- Normalize probabilities to 0-1 format
            CASE 
                WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0
                ELSE p.home_win_percentage
            END AS espn_home_prob,
            -- Game state from prob_event_state
            e.point_differential AS score_diff,
            e.time_remaining,
            e.home_score,
            e.away_score,
            -- Calculate period from time_remaining
            CASE 
                WHEN e.time_remaining IS NULL THEN NULL
                WHEN e.time_remaining > 2160 THEN 1  -- Q1: 2160-2880 seconds
                WHEN e.time_remaining > 1440 THEN 2  -- Q2: 1440-2160 seconds
                WHEN e.time_remaining > 720 THEN 3   -- Q3: 720-1440 seconds
                ELSE 4                               -- Q4: 0-720 seconds
            END AS period
        FROM espn.probabilities_raw_items p
        LEFT JOIN espn.prob_event_state e 
            ON p.game_id = e.game_id 
            AND p.event_id = e.event_id
        WHERE e.time_remaining IS NOT NULL
            AND e.point_differential IS NOT NULL
    ),
    espn_with_features AS (
        SELECT 
            *,
            -- Interaction term: score_diff / sqrt(time_remaining + 1)
            CASE 
                WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
                    score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
                ELSE NULL
            END AS score_diff_div_sqrt_time_remaining,
            -- Lagged probabilities using window functions
            LAG(espn_home_prob) OVER (
                PARTITION BY season_label, game_id 
                ORDER BY sequence_number
            ) AS espn_home_prob_lag_1,
            -- Delta (current - lag_1)
            espn_home_prob - LAG(espn_home_prob) OVER (
                PARTITION BY season_label, game_id 
                ORDER BY sequence_number
            ) AS espn_home_prob_delta_1
        FROM espn_base
    )
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_label,
        e.game_id,
        e.sequence_number,
        e.score_diff AS point_differential,
        e.time_remaining AS time_remaining_regulation,
        e.home_score,
        e.away_score,
        'unknown' AS possession,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0
            WHEN sg.away_score > sg.home_score THEN 1
            ELSE NULL
        END AS final_winning_team,
        CAST(SUBSTRING(e.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start
    """
    
    # Add interaction terms if enabled
    if use_interaction_terms:
        interaction_select = """
        ,
        e.score_diff_div_sqrt_time_remaining,
        e.espn_home_prob,
        e.espn_home_prob_lag_1,
        e.espn_home_prob_delta_1,
        e.period
        """
    else:
        interaction_select = ""
    
    query = base_query + interaction_select + """
    FROM espn_with_features e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id
    ORDER BY e.season_label, e.game_id, e.sequence_number
    """
    
    # Suppress pandas warning about psycopg connection (it works fine, just not officially supported)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy.*")
        df = pd.read_sql(query, conn)
    
    return df


def main() -> int:
    args = parse_args()
    out_path = Path(args.out_artifact)
    dsn = get_dsn(args.dsn)

    # Load data from canonical dataset
    calib_season_start = int(args.calib_season_start) if args.calib_season_start is not None else None
    with connect(dsn) as conn:
        df = _load_training_data(
            conn,
            train_season_start_max=int(args.train_season_start_max),
            test_season_start=int(args.test_season_start),
            calib_season_start=calib_season_start,
            use_interaction_terms=bool(args.use_interaction_terms),
        )

    # Debug: Print available seasons and row counts BEFORE filtering
    print(f"Total rows loaded from ESPN tables: {len(df)}", file=sys.stderr)
    if "season_start" in df.columns:
        available_seasons = sorted(df["season_start"].unique().tolist())
        print(f"Available seasons BEFORE filtering: {available_seasons}", file=sys.stderr)
        for season in available_seasons:
            season_count = len(df[df["season_start"] == season])
            print(f"  Season {season}: {season_count} rows", file=sys.stderr)
    else:
        print(f"Warning: season_start column not found. Total rows: {len(df)}", file=sys.stderr)
    
    # Check how many rows have final_winning_team before filtering
    rows_with_label = df["final_winning_team"].notna().sum() if "final_winning_team" in df.columns else 0
    rows_without_label = len(df) - rows_with_label
    print(f"Rows with final_winning_team: {rows_with_label}, without: {rows_without_label}", file=sys.stderr)
    
    if len(df) == 0:
        raise SystemExit("No data loaded from canonical dataset. Check database connection and data availability.")
    
    # Filter out rows without labels (defensive)
    df = df[df["final_winning_team"].notna()].copy()
    
    print(f"Rows after filtering for final_winning_team: {len(df)}", file=sys.stderr)
    
    # Debug: Print available seasons AFTER filtering
    if "season_start" in df.columns and len(df) > 0:
        available_seasons_after = sorted(df["season_start"].unique().tolist())
        print(f"Available seasons AFTER filtering: {available_seasons_after}", file=sys.stderr)
        for season in available_seasons_after:
            season_count = len(df[df["season_start"] == season])
            print(f"  Season {season}: {season_count} rows", file=sys.stderr)

    # Build y_home_win
    y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)

    season = df["season_start"].astype(int).to_numpy()
    train_mask = season <= int(args.train_season_start_max)
    test_mask = season == int(args.test_season_start)
    calib_mask = (season == int(args.calib_season_start)) if args.calib_season_start is not None else np.zeros(len(season), dtype=bool)

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
            f"\nERROR: Test season ({args.test_season_start}) has 0 rows in canonical dataset.\n"
            f"Available seasons: {available_seasons_str}\n"
            f"Suggestions:\n"
            f"  - Adjust --test-season-start to match available seasons (e.g., --test-season-start {max(available_seasons) if available_seasons else 2025})"
        )

    # Preprocess params computed from train rows only.
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
    
    # Calculate normalization params for interaction terms if enabled
    use_interaction_terms = bool(args.use_interaction_terms)
    interaction_params = {}
    if use_interaction_terms:
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
    
    preprocess = PreprocessParams(
        point_diff_mean=pd_mean,
        point_diff_std=pd_std,
        time_rem_mean=tr_mean,
        time_rem_std=tr_std,
        **interaction_params
    )

    # Build X for train
    build_matrix_kwargs = {
        "point_differential": df.loc[train_mask, "point_differential"].to_numpy(),
        "time_remaining_regulation": df.loc[train_mask, "time_remaining_regulation"].to_numpy(),
        "possession": df.loc[train_mask, "possession"].astype(str).tolist(),
        "preprocess": preprocess,
    }
    
    # Add interaction terms if enabled
    if use_interaction_terms:
        if "score_diff_div_sqrt_time_remaining" in df.columns:
            build_matrix_kwargs["score_diff_div_sqrt_time_remaining"] = df.loc[train_mask, "score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
        if "espn_home_prob" in df.columns:
            build_matrix_kwargs["espn_home_prob"] = df.loc[train_mask, "espn_home_prob"].astype(float).to_numpy()
        if "espn_home_prob_lag_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_lag_1"] = df.loc[train_mask, "espn_home_prob_lag_1"].astype(float).to_numpy()
        if "espn_home_prob_delta_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_delta_1"] = df.loc[train_mask, "espn_home_prob_delta_1"].astype(float).to_numpy()
        if "period" in df.columns:
            build_matrix_kwargs["period"] = df.loc[train_mask, "period"].astype(int).tolist()
    
    X_train = build_design_matrix(**build_matrix_kwargs)
    y_train = y[train_mask]

    weights, intercept = fit_logistic_regression_irls(
        X=X_train,
        y=y_train,
        l2_lambda=float(args.l2_lambda),
        max_iter=int(args.max_iter),
        tol=float(args.tol),
    )

    # Feature ordering by contract (base + optional interaction terms)
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

    # Optional Platt calibration on calibration season.
    platt = None
    if not bool(args.disable_calibration) and calib_season_start is not None and int(np.sum(calib_mask)) >= 5:
        calib_matrix_kwargs = {
            "point_differential": df.loc[calib_mask, "point_differential"].to_numpy(),
            "time_remaining_regulation": df.loc[calib_mask, "time_remaining_regulation"].to_numpy(),
            "possession": df.loc[calib_mask, "possession"].astype(str).tolist(),
            "preprocess": preprocess,
        }
        
        # Add interaction terms for calibration if enabled
        if use_interaction_terms:
            if "score_diff_div_sqrt_time_remaining" in df.columns:
                calib_matrix_kwargs["score_diff_div_sqrt_time_remaining"] = df.loc[calib_mask, "score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
            if "espn_home_prob" in df.columns:
                calib_matrix_kwargs["espn_home_prob"] = df.loc[calib_mask, "espn_home_prob"].astype(float).to_numpy()
            if "espn_home_prob_lag_1" in df.columns:
                calib_matrix_kwargs["espn_home_prob_lag_1"] = df.loc[calib_mask, "espn_home_prob_lag_1"].astype(float).to_numpy()
            if "espn_home_prob_delta_1" in df.columns:
                calib_matrix_kwargs["espn_home_prob_delta_1"] = df.loc[calib_mask, "espn_home_prob_delta_1"].astype(float).to_numpy()
            if "period" in df.columns:
                calib_matrix_kwargs["period"] = df.loc[calib_mask, "period"].astype(int).tolist()
        
        X_calib = build_design_matrix(**calib_matrix_kwargs)
        # Base model probabilities (no calibration yet).
        base_model = ModelParams(
            weights=[float(x) for x in weights.tolist()],
            intercept=float(intercept),
            l2_lambda=float(args.l2_lambda),
            max_iter=int(args.max_iter),
            tol=float(args.tol),
        )
        tmp_art = WinProbArtifact(
            created_at_utc=utc_now_iso_compact(),
            version=str(args.version),
            train_season_start_max=int(args.train_season_start_max),
            calib_season_start=calib_season_start,
            test_season_start=int(args.test_season_start),
            buckets_seconds_remaining=_calculate_buckets(df["time_remaining_regulation"], args.bucket_step_seconds),
            preprocess=preprocess,
            feature_names=feature_names,
            model=base_model,
            platt=None,
        )
        p_base = predict_proba(tmp_art, X=X_calib)
        y_calib = y[calib_mask]
        platt = fit_platt_calibrator_on_probs(p_base=p_base, y=y_calib)

    model = ModelParams(
        weights=[float(x) for x in weights.tolist()],
        intercept=float(intercept),
        l2_lambda=float(args.l2_lambda),
        max_iter=int(args.max_iter),
        tol=float(args.tol),
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
        model=model,
        platt=platt,
    )

    save_artifact(out_path, artifact)
    # Reload roundtrip sanity.
    _ = load_artifact(out_path)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


