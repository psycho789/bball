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
from scripts.lib._winprob_lib import WinProbArtifact, load_artifact, build_design_matrix, predict_proba

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
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (season_label, game_id, sequence_number, snapshot_ts)
    );
    
    CREATE INDEX IF NOT EXISTS model_probabilities_lookup_idx 
        ON derived.model_probabilities_v1 (season_label, game_id, sequence_number, snapshot_ts);
    """
    
    conn.execute(create_sql)
    conn.commit()
    logger.info("✅ Table created")


def load_all_models() -> dict[str, WinProbArtifact]:
    """Load all 4 model artifacts."""
    logger.info("Loading model artifacts...")
    
    model_paths = {
        "logreg_platt": Path("data/models/winprob_logreg_platt_2017-2023.json"),
        "logreg_isotonic": Path("data/models/winprob_logreg_isotonic_2017-2023.json"),
        "catboost_platt": Path("data/models/winprob_catboost_platt_2017-2023.json"),
        "catboost_isotonic": Path("data/models/winprob_catboost_isotonic_2017-2023.json"),
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
    
    if len(models) != 4:
        raise ValueError(f"Expected 4 models, loaded {len(models)}")
    
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
    }
    
    # Extract features
    score_diff = snapshot.get("score_diff")
    time_remaining = snapshot.get("time_remaining")
    espn_home_prob = snapshot.get("espn_home_prob")
    score_diff_div_sqrt = snapshot.get("score_diff_div_sqrt_time_remaining")
    espn_home_prob_lag_1 = snapshot.get("espn_home_prob_lag_1")
    espn_home_prob_delta_1 = snapshot.get("espn_home_prob_delta_1")
    period = snapshot.get("period")
    
    # Handle missing features with defaults
    if score_diff is None:
        score_diff = 0.0
    if time_remaining is None:
        time_remaining = 2880.0  # Default to full game
    if espn_home_prob is None:
        espn_home_prob = 0.5  # Default to 50%
    if score_diff_div_sqrt is None:
        score_diff_div_sqrt = 0.0
    if espn_home_prob_lag_1 is None:
        espn_home_prob_lag_1 = espn_home_prob  # Use current if lag missing
    if espn_home_prob_delta_1 is None:
        espn_home_prob_delta_1 = 0.0
    if period is None:
        period = 1
    
    # Score each model
    for model_name, artifact in models.items():
        try:
            # Build design matrix - all parameters must be numpy arrays (or None)
            X = build_design_matrix(
                point_differential=np.array([float(score_diff)]),
                time_remaining_regulation=np.array([float(time_remaining)]),
                possession=["unknown"],  # Default possession (not used by current models)
                preprocess=artifact.preprocess,
                score_diff_div_sqrt_time_remaining=np.array([score_diff_div_sqrt]),
                espn_home_prob=np.array([espn_home_prob]),
                espn_home_prob_lag_1=np.array([espn_home_prob_lag_1]),
                espn_home_prob_delta_1=np.array([espn_home_prob_delta_1]),
                period=np.array([period])
            )
            
            # Predict probability
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
            
        except Exception as e:
            logger.warning(f"Failed to score {model_name} for snapshot: {e}")
            continue
    
    return results


def precompute_all(conn: psycopg.Connection, models: dict[str, WinProbArtifact], batch_size: int = 1000) -> None:
    """Pre-compute probabilities for all snapshots."""
    logger.info("Querying all snapshots from derived.snapshot_features_v1...")
    
    # Query all snapshots with required features
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
        period
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
        logreg_platt_prob, logreg_isotonic_prob, catboost_platt_prob, catboost_isotonic_prob
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (season_label, game_id, sequence_number, snapshot_ts) 
    DO UPDATE SET
        logreg_platt_prob = EXCLUDED.logreg_platt_prob,
        logreg_isotonic_prob = EXCLUDED.logreg_isotonic_prob,
        catboost_platt_prob = EXCLUDED.catboost_platt_prob,
        catboost_isotonic_prob = EXCLUDED.catboost_isotonic_prob
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
        }
        
        try:
            # Score snapshot with all models
            probs = score_snapshot(snapshot, models)
            
            # Add to batch
            batch.append((
                snapshot["season_label"],
                snapshot["game_id"],
                snapshot["sequence_number"],
                snapshot["snapshot_ts"],
                probs["logreg_platt_prob"],
                probs["logreg_isotonic_prob"],
                probs["catboost_platt_prob"],
                probs["catboost_isotonic_prob"],
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

