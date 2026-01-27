#!/usr/bin/env python3
"""
Pre-compute model probabilities for all snapshots in derived.snapshot_features_v1.

This script scores all snapshots with all 4 win probability models and stores
the results in derived.model_probabilities_v1 for fast grid search queries.

Design Pattern: Batch Processing Pattern
Algorithm: Vectorized Model Scoring
Big O: O(n * m) where n = snapshots, m = models (4)
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import psycopg

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    WinProbArtifact,
    load_artifact,
    build_design_matrix,
    predict_proba,
    compute_opening_odds_features,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def create_table(conn: psycopg.Connection) -> None:
    """Create derived.model_probabilities_v1 table if it doesn't exist."""
    logger.info("Creating derived.model_probabilities_v1 table...")
    
    create_sql = """
    CREATE TABLE IF NOT EXISTS derived.model_probabilities_v1 (
        season_label TEXT NOT NULL,
        game_id TEXT NOT NULL,
        sequence_number INTEGER NOT NULL,
        snapshot_ts TIMESTAMPTZ NOT NULL,
        logreg_platt_prob DOUBLE PRECISION,
        logreg_isotonic_prob DOUBLE PRECISION,
        catboost_platt_prob DOUBLE PRECISION,
        catboost_isotonic_prob DOUBLE PRECISION,
        catboost_baseline_platt_prob DOUBLE PRECISION,
        catboost_baseline_isotonic_prob DOUBLE PRECISION,
        catboost_odds_platt_prob DOUBLE PRECISION,
        catboost_odds_isotonic_prob DOUBLE PRECISION,
        catboost_baseline_no_interaction_platt_prob DOUBLE PRECISION,
        catboost_baseline_no_interaction_isotonic_prob DOUBLE PRECISION,
        catboost_odds_no_interaction_platt_prob DOUBLE PRECISION,
        catboost_odds_no_interaction_isotonic_prob DOUBLE PRECISION,
        -- v2 models (with updated feature set and uses_opening_odds_baseline flag)
        catboost_baseline_platt_v2_prob DOUBLE PRECISION,
        catboost_baseline_isotonic_v2_prob DOUBLE PRECISION,
        catboost_odds_platt_v2_prob DOUBLE PRECISION,
        catboost_odds_isotonic_v2_prob DOUBLE PRECISION,
        catboost_baseline_no_interaction_platt_v2_prob DOUBLE PRECISION,
        catboost_baseline_no_interaction_isotonic_v2_prob DOUBLE PRECISION,
        catboost_odds_no_interaction_platt_v2_prob DOUBLE PRECISION,
        catboost_odds_no_interaction_isotonic_v2_prob DOUBLE PRECISION,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (season_label, game_id, sequence_number, snapshot_ts)
    );
    
    -- Add new columns if table already exists (for migration)
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_platt_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_platt_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_isotonic_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_isotonic_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_platt_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_platt_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_isotonic_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_isotonic_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_no_interaction_platt_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_no_interaction_platt_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_no_interaction_isotonic_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_no_interaction_isotonic_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_no_interaction_platt_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_no_interaction_platt_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_no_interaction_isotonic_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_no_interaction_isotonic_prob DOUBLE PRECISION;
        END IF;
        
        -- Add v2 model columns if they don't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_platt_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_platt_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_isotonic_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_isotonic_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_platt_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_platt_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_isotonic_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_isotonic_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_no_interaction_platt_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_no_interaction_platt_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_baseline_no_interaction_isotonic_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_baseline_no_interaction_isotonic_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_no_interaction_platt_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_no_interaction_platt_v2_prob DOUBLE PRECISION;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'derived'
            AND table_name = 'model_probabilities_v1'
            AND column_name = 'catboost_odds_no_interaction_isotonic_v2_prob'
        ) THEN
            ALTER TABLE derived.model_probabilities_v1
            ADD COLUMN catboost_odds_no_interaction_isotonic_v2_prob DOUBLE PRECISION;
        END IF;
    END $$;
    
    CREATE INDEX IF NOT EXISTS model_probabilities_lookup_idx 
        ON derived.model_probabilities_v1 (season_label, game_id, sequence_number, snapshot_ts);
    """
    
    conn.execute(create_sql)
    conn.commit()
    logger.info("✅ Table created")


def load_all_models() -> dict[str, WinProbArtifact]:
    """Load all model artifacts (4 original + 8 new models: baseline/odds × platt/isotonic × with/without interactions)."""
    logger.info("Loading model artifacts...")
    
    model_paths = {
        # v2 models (with updated feature set and uses_opening_odds_baseline flag)
        "catboost_baseline_platt_v2": Path("artifacts/winprob_catboost_baseline_platt_v2.json"),
        "catboost_baseline_isotonic_v2": Path("artifacts/winprob_catboost_baseline_isotonic_v2.json"),
        "catboost_odds_platt_v2": Path("artifacts/winprob_catboost_odds_platt_v2.json"),
        "catboost_odds_isotonic_v2": Path("artifacts/winprob_catboost_odds_isotonic_v2.json"),
        "catboost_baseline_no_interaction_platt_v2": Path("artifacts/winprob_catboost_baseline_no_interaction_platt_v2.json"),
        "catboost_baseline_no_interaction_isotonic_v2": Path("artifacts/winprob_catboost_baseline_no_interaction_isotonic_v2.json"),
        "catboost_odds_no_interaction_platt_v2": Path("artifacts/winprob_catboost_odds_no_interaction_platt_v2.json"),
        "catboost_odds_no_interaction_isotonic_v2": Path("artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json"),
        
        # v1 models (commented out by default, uncomment as needed)
        # "logreg_platt": Path("data/models/winprob_logreg_platt_2017-2023.json"),
        # "logreg_isotonic": Path("data/models/winprob_logreg_isotonic_2017-2023.json"),
        # "catboost_platt": Path("data/models/winprob_catboost_platt_2017-2023.json"),
        # "catboost_isotonic": Path("data/models/winprob_catboost_isotonic_2017-2023.json"),
        # "catboost_baseline_platt": Path("artifacts/winprob_catboost_baseline_platt.json"),
        # "catboost_baseline_isotonic": Path("artifacts/winprob_catboost_baseline_isotonic.json"),
        # "catboost_odds_platt": Path("artifacts/winprob_catboost_odds_platt.json"),
        # "catboost_odds_isotonic": Path("artifacts/winprob_catboost_odds_isotonic.json"),
        # "catboost_baseline_no_interaction_platt": Path("artifacts/winprob_catboost_baseline_no_interaction_platt.json"),
        # "catboost_baseline_no_interaction_isotonic": Path("artifacts/winprob_catboost_baseline_no_interaction_isotonic.json"),
        # "catboost_odds_no_interaction_platt": Path("artifacts/winprob_catboost_odds_no_interaction_platt.json"),
        # "catboost_odds_no_interaction_isotonic": Path("artifacts/winprob_catboost_odds_no_interaction_isotonic.json"),
    }
    
    models = {}
    for name, path in model_paths.items():
        if not path.exists():
            logger.warning(f"⚠️  Model file not found: {path}")
            continue
        try:
            models[name] = load_artifact(path)
            logger.info(f"✅ Loaded {name}: {len(models[name].feature_names)} features")
        except Exception as e:
            logger.error(f"❌ Failed to load {name}: {e}")
    
    if len(models) == 0:
        raise ValueError("No models loaded")
    
    logger.info(f"✅ Loaded {len(models)}/{len(model_paths)} models")
    return models


def score_snapshot(
    snapshot: dict[str, Any],
    models: dict[str, WinProbArtifact]
) -> dict[str, float | None]:
    """Score a single snapshot with all models."""
    results = {
        "logreg_platt_prob": None,
        "logreg_isotonic_prob": None,
        "catboost_platt_prob": None,
        "catboost_isotonic_prob": None,
        "catboost_baseline_platt_prob": None,
        "catboost_baseline_isotonic_prob": None,
        "catboost_odds_platt_prob": None,
        "catboost_odds_isotonic_prob": None,
        "catboost_baseline_no_interaction_platt_prob": None,
        "catboost_baseline_no_interaction_isotonic_prob": None,
        "catboost_odds_no_interaction_platt_prob": None,
        "catboost_odds_no_interaction_isotonic_prob": None,
        # v2 models
        "catboost_baseline_platt_v2_prob": None,
        "catboost_baseline_isotonic_v2_prob": None,
        "catboost_odds_platt_v2_prob": None,
        "catboost_odds_isotonic_v2_prob": None,
        "catboost_baseline_no_interaction_platt_v2_prob": None,
        "catboost_baseline_no_interaction_isotonic_v2_prob": None,
        "catboost_odds_no_interaction_platt_v2_prob": None,
        "catboost_odds_no_interaction_isotonic_v2_prob": None,
    }
    
    # Extract features
    score_diff = snapshot.get("score_diff")
    time_remaining = snapshot.get("time_remaining")
    espn_home_prob = snapshot.get("espn_home_prob")
    score_diff_div_sqrt = snapshot.get("score_diff_div_sqrt_time_remaining")
    espn_home_prob_lag_1 = snapshot.get("espn_home_prob_lag_1")
    espn_home_prob_delta_1 = snapshot.get("espn_home_prob_delta_1")
    period = snapshot.get("period")
    
    # Extract opening odds (raw, will be engineered)
    opening_moneyline_home = snapshot.get("opening_moneyline_home")
    opening_moneyline_away = snapshot.get("opening_moneyline_away")
    opening_spread = snapshot.get("opening_spread")
    opening_total = snapshot.get("opening_total")
    
    # Handle missing features with defaults
    if score_diff is None:
        score_diff = 0.0
    if time_remaining is None:
        time_remaining = 2880.0  # Default to full game
    if espn_home_prob is None:
        espn_home_prob = 0.5  # Default to 50%
    # CRITICAL FIX: Calculate score_diff_div_sqrt from components if NULL (matches training formula)
    # This ensures consistency with on-the-fly computation and training data
    if score_diff_div_sqrt is None:
        if score_diff is not None and time_remaining is not None:
            import math
            score_diff_div_sqrt = float(score_diff) / math.sqrt(float(time_remaining) + 1)
        else:
            score_diff_div_sqrt = 0.0  # Fallback if components missing
    if espn_home_prob_lag_1 is None:
        espn_home_prob_lag_1 = espn_home_prob  # Use current if lag missing
    if espn_home_prob_delta_1 is None:
        espn_home_prob_delta_1 = 0.0
    if period is None:
        period = 1
    
    # Compute opening odds engineered features using shared helper (prevents code drift)
    # Convert scalar inputs to arrays to ensure consistent return type
    odds_features = compute_opening_odds_features(
        opening_moneyline_home=np.array([opening_moneyline_home]) if opening_moneyline_home is not None else None,
        opening_moneyline_away=np.array([opening_moneyline_away]) if opening_moneyline_away is not None else None,
        opening_spread=np.array([opening_spread]) if opening_spread is not None else None,
        opening_total=np.array([opening_total]) if opening_total is not None else None,
    )
    
    # Score each model
    for model_name, artifact in models.items():
        try:
            # Build design matrix - all parameters must be numpy arrays (or None)
            # Opening odds features may be NaNs (CatBoost handles natively)
            build_kwargs = {
                "point_differential": np.array([float(score_diff)]),
                "time_remaining_regulation": np.array([float(time_remaining)]),
                "possession": ["unknown"],  # Default possession (not used by current models)
                "preprocess": artifact.preprocess,
            }
            
            # Add interaction terms if present in artifact (check feature_names)
            # Models trained with --no-interaction-terms won't have these features
            use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in artifact.feature_names)
            if use_interaction_terms:
                if any("score_diff_div_sqrt" in fn for fn in artifact.feature_names):
                    build_kwargs["score_diff_div_sqrt_time_remaining"] = np.array([score_diff_div_sqrt])
                # FIX: Use exact match for espn_home_prob_scaled (matches on-the-fly logic)
                if any(fn == "espn_home_prob_scaled" for fn in artifact.feature_names):
                    build_kwargs["espn_home_prob"] = np.array([espn_home_prob])
                if any("espn_home_prob_lag_1" in fn for fn in artifact.feature_names):
                    build_kwargs["espn_home_prob_lag_1"] = np.array([espn_home_prob_lag_1])
                if any("espn_home_prob_delta_1" in fn for fn in artifact.feature_names):
                    build_kwargs["espn_home_prob_delta_1"] = np.array([espn_home_prob_delta_1])
                # FIX: Use "period" substring match (matches on-the-fly logic, more general)
                # Note: Feature names are period_1, period_2, period_3, period_4, so "period" in fn works
                if any("period" in fn for fn in artifact.feature_names):
                    build_kwargs["period"] = np.array([period])
            
            # Add opening odds features if model expects them (check if any odds feature in artifact)
            # NOTE: opening_prob_home_fair is used as baseline (NOT a feature), opening_spread/total removed (redundant)
            # Only check for features that actually exist: opening_overround, has_opening_*
            # Skip old artifacts that have removed features (opening_prob_home_fair as feature, or old interaction terms)
            has_old_features = (
                "opening_prob_home_fair" in artifact.feature_names or
                any("opening_prob_home_fair_div_time_remaining_scaled" in fn for fn in artifact.feature_names) or
                any("opening_spread_div_time_remaining_scaled" in fn for fn in artifact.feature_names) or
                any("opening_total_div_time_remaining_scaled" in fn for fn in artifact.feature_names)
            )
            
            if has_old_features:
                # Old artifact with removed features - skip (incompatible with current build_design_matrix)
                logger.warning(f"Skipping {model_name}: artifact has removed features (opening_prob_home_fair as feature or old interaction terms)")
                continue
            
            if "opening_overround" in artifact.feature_names:
                # Use engineered features from helper (handles NaNs correctly)
                # NOTE: opening_prob_home_fair NOT passed to build_design_matrix (used as baseline only)
                # NOTE: opening_spread and opening_total removed (redundant features)
                # NOTE: has_opening_moneyline removed (perfectly redundant with opening_overround)
                # NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
                # odds_features already returns arrays (not scalars) since we passed arrays to compute_opening_odds_features
                build_kwargs["opening_overround"] = np.asarray(odds_features["opening_overround"]).flatten()
                
                # Backward compatibility: Check if old model artifact expects binary flags
                # Old models (trained before v2.2) may have has_opening_spread and has_opening_total in feature_names
                if "has_opening_spread" in artifact.feature_names:
                    # Old model expects has_opening_spread - compute it for backward compatibility
                    if opening_spread is not None:
                        has_opening_spread_val = 1.0 if not np.isnan(float(opening_spread)) else 0.0
                    else:
                        has_opening_spread_val = 0.0
                    build_kwargs["has_opening_spread"] = np.array([has_opening_spread_val], dtype=np.float64)
                
                if "has_opening_total" in artifact.feature_names:
                    # Old model expects has_opening_total - compute it for backward compatibility
                    if opening_total is not None:
                        has_opening_total_val = 1.0 if not np.isnan(float(opening_total)) else 0.0
                    else:
                        has_opening_total_val = 0.0
                    build_kwargs["has_opening_total"] = np.array([has_opening_total_val], dtype=np.float64)
                
                # CatBoost can use NaN as signal, so pass odds_nan_policy="keep"
                build_kwargs["odds_nan_policy"] = "keep"
            
            X = build_design_matrix(**build_kwargs)
            
            # Predict probability - pass baseline data if model uses it
            # Use explicit flag if available, fall back to heuristic for old artifacts
            uses_baseline = getattr(artifact, 'uses_opening_odds_baseline', None)
            if uses_baseline is None:
                # Fallback heuristic for older artifacts
                has_opening_odds_features = any("opening" in fn.lower() or "overround" in fn.lower() for fn in artifact.feature_names)
                opening_prob_not_a_feature = "opening_prob_home_fair" not in artifact.feature_names
                uses_baseline = has_opening_odds_features and opening_prob_not_a_feature
            
            if uses_baseline:
                # Model uses baseline - pass opening_prob_home_fair (has_opening_moneyline inferred from NaN pattern)
                # odds_features already returns arrays (not scalars) since we passed arrays to compute_opening_odds_features
                prob_array = predict_proba(
                    artifact, 
                    X=X,
                    opening_prob_home_fair=np.asarray(odds_features["opening_prob_home_fair"]).flatten(),
                )
            else:
                # Model doesn't use baseline
                prob_array = predict_proba(artifact, X=X)
            prob = float(prob_array[0])
            
            # Validate range
            if prob < 0.0 or prob > 1.0:
                logger.warning(f"Model {model_name} returned out-of-range prob: {prob}")
                prob = max(0.0, min(1.0, prob))
            
            # Map model name to column name
            if model_name == "logreg_platt":
                results["logreg_platt_prob"] = prob
            elif model_name == "logreg_isotonic":
                results["logreg_isotonic_prob"] = prob
            elif model_name == "catboost_platt":
                results["catboost_platt_prob"] = prob
            elif model_name == "catboost_isotonic":
                results["catboost_isotonic_prob"] = prob
            elif model_name == "catboost_baseline_platt":
                results["catboost_baseline_platt_prob"] = prob
            elif model_name == "catboost_baseline_isotonic":
                results["catboost_baseline_isotonic_prob"] = prob
            elif model_name == "catboost_odds_platt":
                results["catboost_odds_platt_prob"] = prob
            elif model_name == "catboost_odds_isotonic":
                results["catboost_odds_isotonic_prob"] = prob
            elif model_name == "catboost_baseline_no_interaction_platt":
                results["catboost_baseline_no_interaction_platt_prob"] = prob
            elif model_name == "catboost_baseline_no_interaction_isotonic":
                results["catboost_baseline_no_interaction_isotonic_prob"] = prob
            elif model_name == "catboost_odds_no_interaction_platt":
                results["catboost_odds_no_interaction_platt_prob"] = prob
            elif model_name == "catboost_odds_no_interaction_isotonic":
                results["catboost_odds_no_interaction_isotonic_prob"] = prob
            # v2 models
            elif model_name == "catboost_baseline_platt_v2":
                results["catboost_baseline_platt_v2_prob"] = prob
            elif model_name == "catboost_baseline_isotonic_v2":
                results["catboost_baseline_isotonic_v2_prob"] = prob
            elif model_name == "catboost_odds_platt_v2":
                results["catboost_odds_platt_v2_prob"] = prob
            elif model_name == "catboost_odds_isotonic_v2":
                results["catboost_odds_isotonic_v2_prob"] = prob
            elif model_name == "catboost_baseline_no_interaction_platt_v2":
                results["catboost_baseline_no_interaction_platt_v2_prob"] = prob
            elif model_name == "catboost_baseline_no_interaction_isotonic_v2":
                results["catboost_baseline_no_interaction_isotonic_v2_prob"] = prob
            elif model_name == "catboost_odds_no_interaction_platt_v2":
                results["catboost_odds_no_interaction_platt_v2_prob"] = prob
            elif model_name == "catboost_odds_no_interaction_isotonic_v2":
                results["catboost_odds_no_interaction_isotonic_v2_prob"] = prob
            
        except Exception as e:
            logger.warning(f"Failed to score {model_name} for snapshot: {e}")
            continue
    
    return results


def precompute_all(conn: psycopg.Connection, models: dict[str, WinProbArtifact], batch_size: int = 1000) -> None:
    """Pre-compute probabilities for all snapshots."""
    logger.info("Querying all snapshots from derived.snapshot_features_v1...")
    
    # Query all snapshots with required features (including opening odds)
    query_sql = """
    SELECT 
        season_label,
        game_id,
        sequence_number,
        snapshot_ts,
        score_diff,
        time_remaining,
        espn_home_prob,
        score_diff_div_sqrt_time_remaining,
        espn_home_prob_lag_1,
        espn_home_prob_delta_1,
        period,
        -- Opening odds columns (raw, will be engineered in score_snapshot)
        opening_moneyline_home,
        opening_moneyline_away,
        opening_spread,
        opening_total
    FROM derived.snapshot_features_v1
    ORDER BY season_label, game_id, sequence_number, snapshot_ts
    """
    
    cursor = conn.execute(query_sql)
    all_rows = cursor.fetchall()
    logger.info(f"Found {len(all_rows)} snapshots to score")
    
    if not all_rows:
        logger.warning("No snapshots found in derived.snapshot_features_v1")
        return
    
    # Clear existing data if refresh requested
    logger.info("Clearing existing probabilities...")
    conn.execute("TRUNCATE TABLE derived.model_probabilities_v1")
    conn.commit()
    
    # Process in batches
    total = len(all_rows)
    processed = 0
    inserted = 0
    errors = 0
    
    insert_sql = """
    INSERT INTO derived.model_probabilities_v1 (
        season_label, game_id, sequence_number, snapshot_ts,
        logreg_platt_prob, logreg_isotonic_prob, catboost_platt_prob, catboost_isotonic_prob,
        catboost_baseline_platt_prob, catboost_baseline_isotonic_prob,
        catboost_odds_platt_prob, catboost_odds_isotonic_prob,
        catboost_baseline_no_interaction_platt_prob, catboost_baseline_no_interaction_isotonic_prob,
        catboost_odds_no_interaction_platt_prob, catboost_odds_no_interaction_isotonic_prob,
        catboost_baseline_platt_v2_prob, catboost_baseline_isotonic_v2_prob,
        catboost_odds_platt_v2_prob, catboost_odds_isotonic_v2_prob,
        catboost_baseline_no_interaction_platt_v2_prob, catboost_baseline_no_interaction_isotonic_v2_prob,
        catboost_odds_no_interaction_platt_v2_prob, catboost_odds_no_interaction_isotonic_v2_prob
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (season_label, game_id, sequence_number, snapshot_ts) 
    DO UPDATE SET
        logreg_platt_prob = EXCLUDED.logreg_platt_prob,
        logreg_isotonic_prob = EXCLUDED.logreg_isotonic_prob,
        catboost_platt_prob = EXCLUDED.catboost_platt_prob,
        catboost_isotonic_prob = EXCLUDED.catboost_isotonic_prob,
        catboost_baseline_platt_prob = EXCLUDED.catboost_baseline_platt_prob,
        catboost_baseline_isotonic_prob = EXCLUDED.catboost_baseline_isotonic_prob,
        catboost_odds_platt_prob = EXCLUDED.catboost_odds_platt_prob,
        catboost_odds_isotonic_prob = EXCLUDED.catboost_odds_isotonic_prob,
        catboost_baseline_no_interaction_platt_prob = EXCLUDED.catboost_baseline_no_interaction_platt_prob,
        catboost_baseline_no_interaction_isotonic_prob = EXCLUDED.catboost_baseline_no_interaction_isotonic_prob,
        catboost_odds_no_interaction_platt_prob = EXCLUDED.catboost_odds_no_interaction_platt_prob,
        catboost_odds_no_interaction_isotonic_prob = EXCLUDED.catboost_odds_no_interaction_isotonic_prob,
        catboost_baseline_platt_v2_prob = EXCLUDED.catboost_baseline_platt_v2_prob,
        catboost_baseline_isotonic_v2_prob = EXCLUDED.catboost_baseline_isotonic_v2_prob,
        catboost_odds_platt_v2_prob = EXCLUDED.catboost_odds_platt_v2_prob,
        catboost_odds_isotonic_v2_prob = EXCLUDED.catboost_odds_isotonic_v2_prob,
        catboost_baseline_no_interaction_platt_v2_prob = EXCLUDED.catboost_baseline_no_interaction_platt_v2_prob,
        catboost_baseline_no_interaction_isotonic_v2_prob = EXCLUDED.catboost_baseline_no_interaction_isotonic_v2_prob,
        catboost_odds_no_interaction_platt_v2_prob = EXCLUDED.catboost_odds_no_interaction_platt_v2_prob,
        catboost_odds_no_interaction_isotonic_v2_prob = EXCLUDED.catboost_odds_no_interaction_isotonic_v2_prob
    """
    
    batch = []
    for row in all_rows:
        snapshot = {
            "season_label": row[0],
            "game_id": row[1],
            "sequence_number": row[2],
            "snapshot_ts": row[3],
            "score_diff": row[4],
            "time_remaining": row[5],
            "espn_home_prob": row[6],
            "score_diff_div_sqrt_time_remaining": row[7],
            "espn_home_prob_lag_1": row[8],
            "espn_home_prob_delta_1": row[9],
            "period": row[10],
            # Opening odds columns (raw, will be engineered in score_snapshot)
            "opening_moneyline_home": row[11] if len(row) > 11 else None,
            "opening_moneyline_away": row[12] if len(row) > 12 else None,
            "opening_spread": row[13] if len(row) > 13 else None,
            "opening_total": row[14] if len(row) > 14 else None,
        }
        
        try:
            # Score snapshot with all models
            probs = score_snapshot(snapshot, models)
            
            # Add to batch (use None for missing models)
            batch.append((
                snapshot["season_label"],
                snapshot["game_id"],
                snapshot["sequence_number"],
                snapshot["snapshot_ts"],
                probs.get("logreg_platt_prob"),
                probs.get("logreg_isotonic_prob"),
                probs.get("catboost_platt_prob"),
                probs.get("catboost_isotonic_prob"),
                probs.get("catboost_baseline_platt_prob"),
                probs.get("catboost_baseline_isotonic_prob"),
                probs.get("catboost_odds_platt_prob"),
                probs.get("catboost_odds_isotonic_prob"),
                probs.get("catboost_baseline_no_interaction_platt_prob"),
                probs.get("catboost_baseline_no_interaction_isotonic_prob"),
                probs.get("catboost_odds_no_interaction_platt_prob"),
                probs.get("catboost_odds_no_interaction_isotonic_prob"),
                # v2 models
                probs.get("catboost_baseline_platt_v2_prob"),
                probs.get("catboost_baseline_isotonic_v2_prob"),
                probs.get("catboost_odds_platt_v2_prob"),
                probs.get("catboost_odds_isotonic_v2_prob"),
                probs.get("catboost_baseline_no_interaction_platt_v2_prob"),
                probs.get("catboost_baseline_no_interaction_isotonic_v2_prob"),
                probs.get("catboost_odds_no_interaction_platt_v2_prob"),
                probs.get("catboost_odds_no_interaction_isotonic_v2_prob"),
            ))
            
            processed += 1
            
            # Insert batch when full
            if len(batch) >= batch_size:
                with conn.cursor() as cur:
                    cur.executemany(insert_sql, batch)
                conn.commit()
                inserted += len(batch)
                logger.info(f"Processed {processed}/{total} snapshots ({inserted} inserted)")
                batch = []
        
        except Exception as e:
            errors += 1
            logger.warning(f"Error processing snapshot {snapshot['game_id']}:{snapshot['sequence_number']}: {e}")
            continue
    
    # Insert remaining batch
    if batch:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)
    
    logger.info(f"✅ Completed: {processed}/{total} processed, {inserted} inserted, {errors} errors")


def main():
    parser = argparse.ArgumentParser(description="Pre-compute model probabilities for all snapshots")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for inserts")
    parser.add_argument("--refresh", action="store_true", help="Clear existing data before recomputing")
    parser.add_argument("--dsn", type=str, default=None, help="Database connection string (default: use DATABASE_URL env var)")
    args = parser.parse_args()
    
    logger.info("Starting model probability pre-computation...")
    
    # Connect to database
    dsn = get_dsn(args.dsn)
    with connect(dsn) as conn:
        # Create table
        create_table(conn)
        
        # Load models
        models = load_all_models()
        
        # Pre-compute probabilities
        precompute_all(conn, models, batch_size=args.batch_size)
    
    logger.info("✅ Pre-computation complete!")


if __name__ == "__main__":
    main()

