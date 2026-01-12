#!/usr/bin/env python3
"""
Train a CatBoost win-probability model from canonical dataset, and save a full pipeline artifact.

This script uses CatBoost for gradient boosting, which can automatically find interaction terms.

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
- Optional interaction terms

Label:
- y_home_win = 1 if final_winning_team == 0 else 0

Usage:
  ./.venv/bin/python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_v1.json \
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    PreprocessParams,
    ModelParams,  # Still needed for artifact structure, but won't be used for prediction
    WinProbArtifact,
    build_design_matrix,
    fit_platt_calibrator_on_probs,
    fit_isotonic_calibrator_on_probs,
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
    """
    # Use the same query structure as train_winprob_logreg.py
    if use_interaction_terms:
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
            AND (CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) <= {train_season_start_max}
                 OR CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = {test_season_start}
                 OR (CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = {calib_season_start} AND {calib_season_start} IS NOT NULL))
              AND (CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) <= {train_season_start_max}
                   OR CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = {test_season_start}
                   OR (CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = {calib_season_start} AND {calib_season_start} IS NOT NULL))
        ),
        espn_with_lag AS (
            SELECT
                *,
                LAG(espn_home_prob, 1) OVER (PARTITION BY game_id ORDER BY sequence_number) AS espn_home_prob_lag_1
            FROM espn_base
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
                CASE 
                    WHEN e.time_remaining IS NOT NULL THEN
                        (FLOOR(e.time_remaining / 60.0) * 60)::INTEGER
                    ELSE NULL
                END AS bucket_seconds_remaining
            FROM espn_with_lag e
            LEFT JOIN espn.scoreboard_games sg 
                ON e.game_id = sg.event_id
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
            e.bucket_seconds_remaining
        FROM espn_with_features e
        ORDER BY e.season_label, e.game_id, e.sequence_number
        """.format(
            train_season_start_max=train_season_start_max,
            test_season_start=test_season_start,
            calib_season_start=calib_season_start if calib_season_start is not None else 'NULL'
        )
    else:
        query = base_query.format(
            train_season_start_max=train_season_start_max,
            test_season_start=test_season_start,
            calib_season_start=calib_season_start if calib_season_start is not None else 'NULL'
        ) + """
        SELECT
            e.season_start,
            e.season_label,
            e.game_id,
            e.sequence_number,
            e.point_differential,
            e.time_remaining_regulation,
            e.possession,
            e.final_winning_team,
            e.bucket_seconds_remaining
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

    # Train CatBoost model
    print("Training CatBoost model...", file=sys.stderr)
    model = CatBoostClassifier(
        iterations=int(args.iterations),
        depth=int(args.depth),
        learning_rate=float(args.learning_rate),
        loss_function='Logloss',
        eval_metric='AUC',
        verbose=100,
        random_seed=42,
        allow_writing_files=False,  # Don't write temp files
    )
    
    # Prepare calibration set if available
    eval_set = None
    if calib_season_start is not None and int(np.sum(calib_mask)) >= 5:
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
        y_calib = y[calib_mask]
        eval_set = (X_calib, y_calib)
    
    model.fit(X_train, y_train, eval_set=eval_set)
    print("CatBoost training completed.", file=sys.stderr)

    # Save CatBoost model to .cbm file
    catboost_model_path = out_path.with_suffix(".cbm")
    model.save_model(str(catboost_model_path))
    print(f"Saved CatBoost model to {catboost_model_path}", file=sys.stderr)
    
    # Store relative path in artifact
    catboost_model_path_rel = catboost_model_path.name  # Just the filename, assume same directory

    # Optional calibration on calibration season (Platt or Isotonic).
    platt = None
    isotonic = None
    if not bool(args.disable_calibration) and calib_season_start is not None and int(np.sum(calib_mask)) >= 5:
        # Get base model probabilities for calibration
        p_base = model.predict_proba(X_calib)[:, 1].astype(np.float64)
        y_calib = y[calib_mask]
        
        # Fit calibration based on method
        if args.calibration_method == "isotonic":
            isotonic = fit_isotonic_calibrator_on_probs(p_base=p_base, y=y_calib)
        else:  # default to platt
            platt = fit_platt_calibrator_on_probs(p_base=p_base, y=y_calib)

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
    )

    save_artifact(out_path, artifact)
    # Reload roundtrip sanity.
    _ = load_artifact(out_path)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

