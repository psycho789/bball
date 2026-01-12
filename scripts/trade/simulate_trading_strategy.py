#!/usr/bin/env python3
"""
Simulate trading strategy: Buy/sell when ESPN odds diverge from Kalshi betting odds.

Strategy:
- Long ESPN: Buy when ESPN probability > Kalshi price + entry_threshold (e.g., 5 cents)
- Short ESPN: Sell when ESPN probability < Kalshi price - entry_threshold
- Exit: Close position when divergence converges to < exit_threshold (e.g., 1 cent)

Design Pattern: State Machine Pattern for trading simulation
Algorithm: Divergence Threshold Trading Simulation
Big O: O(n) where n = aligned data points per game
"""

import argparse
import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

import psycopg
import numpy as np

# Add project root to path to import from scripts and webapp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import WinProbArtifact, build_design_matrix, predict_proba

# Set up logger - use same logger as webapp for consistency
try:
    from webapp.api.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    # Fallback if webapp not available (e.g., running as standalone script)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: int  # Unix timestamp
    exit_time: Optional[int]  # None if still open
    position_type: str  # "long_espn" or "short_espn"
    entry_espn_prob: float
    entry_kalshi_price: float
    entry_kalshi_bid: Optional[float]  # For selling
    entry_kalshi_ask: Optional[float]  # For buying
    exit_espn_prob: Optional[float]
    exit_kalshi_price: Optional[float]
    exit_kalshi_bid: Optional[float]  # For buying back (short exit) or selling (long exit)
    exit_kalshi_ask: Optional[float]  # For buying back (short exit) or selling (long exit)
    profit_cents: Optional[float]  # Calculated after exit (gross profit)
    net_profit_cents: Optional[float]  # Net profit after costs
    actual_outcome: Optional[int]  # 1 if home won, 0 if away won (for display/logging only, not used in P&L)
    game_phase: Optional[str] = None  # "Q1", "Q2-Q3", or "Q4" (calculated from entry time)
    entry_used_price_penalty: bool = False  # True if entry used fallback/forced slippage price penalty
    exit_used_price_penalty: bool = False  # True if exit used fallback/forced slippage price penalty


@dataclass
class SimulationState:
    """Tracks current simulation state."""
    open_position: Optional[str] = None  # None, "long_espn", or "short_espn"
    entry_espn_prob: Optional[float] = None
    entry_kalshi_price: Optional[float] = None
    entry_kalshi_bid: Optional[float] = None
    entry_kalshi_ask: Optional[float] = None
    entry_timestamp: Optional[int] = None
    prev_divergence_prob: Optional[float] = None  # Previous divergence (for hysteresis and direction confirmation)
    prev_abs_divergence_prob: Optional[float] = None  # Previous absolute divergence (for hysteresis exit)
    trades: list[Trade] = None

    def __post_init__(self):
        if self.trades is None:
            self.trades = []


def get_aligned_data(
    conn: psycopg.Connection,
    game_id: str,
    exclude_first_seconds: int = 0,
    exclude_last_seconds: int = 0,
    use_trade_data: bool = False,
    model_artifact: Optional[WinProbArtifact] = None,
    model_name: Optional[str] = None
) -> tuple[list[dict[str, Any]], Optional[int], Optional[int], Optional[int]]:
    """
    Get aligned ESPN and Kalshi data for a game from canonical dataset.
    
    **UPDATED**: Now uses `derived.snapshot_features_v1` canonical dataset instead of manual joins.
    This provides a single source of truth with pre-computed features and aligned timestamps.
    
    **Data Processing**:
    - Queries both home and away Kalshi fields from canonical view
    - Uses away fields as fallback when home data is missing
    - **IMPORTANT**: In `derived.snapshot_features_v1`, `kalshi_away_*` columns are ALREADY stored in 
      home probability space (converted by the SQL view). Python code uses them directly without inversion.
    - Normalizes all probability/price values to 0-1 range (handles both 0-1 and 0-100 formats via `_norm01()` helper)
    - Enforces strict [0,1] range checks with warnings for out-of-range values
    - Provides detailed debug counters for filtered rows (missing_espn, missing_kalshi, out_of_range, time_window)
    - Tracks usage: `used_home_prices` and `used_away_fallback_prices` counters
    
    **Canonical View Expected Format**:
    - Values should be in 0-1 range, but defensive normalization handles 0-100 case
    - ESPN probabilities: 0-1 range (home team win probability)
    - Kalshi prices: 0-1 range (home team win probability)
    - **kalshi_away_* fields**: Already converted to home probability space by SQL view (do NOT invert in Python)
    
    Args:
        conn: Database connection
        game_id: ESPN game_id
        exclude_first_seconds: Exclude first N seconds of game
        exclude_last_seconds: Exclude last N seconds of game
        use_trade_data: **DEPRECATED** - Canonical dataset uses candlestick data. This parameter is ignored.
        model_artifact: Optional WinProbArtifact for model-based probability generation. If None, uses ESPN probabilities.
        model_name: Optional model name ('logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic'). 
                    If provided, will query pre-computed probabilities from derived.model_probabilities_v1 first.
    
    Returns:
        (aligned_data, game_start_timestamp, game_duration_seconds, actual_outcome)
        aligned_data: List of dicts with keys: timestamp, espn_prob, kalshi_price, kalshi_bid, kalshi_ask
        game_start_timestamp: Unix timestamp of game start (int)
        game_duration_seconds: Game duration in seconds (int)
        actual_outcome: 1 if home won, 0 if away won, None if unknown
    """
    import time
    start_time = time.time()
    
    if use_trade_data:
        logger.warning(f"[ALIGN_DATA] Game {game_id}: use_trade_data=True is deprecated. Canonical dataset uses candlestick data.")
    
    # Get game start time and outcome from scoreboard_games
    game_info_sql = """
    SELECT 
        sg.event_date as game_start,
        sg.home_score as final_home_score,
        sg.away_score as final_away_score
    FROM espn.scoreboard_games sg
    WHERE sg.event_id = %s
    LIMIT 1
    """
    query_start = time.time()
    game_row = conn.execute(game_info_sql, (game_id,)).fetchone()
    query_elapsed = time.time() - query_start
    # logger.info(f"[TIMING] get_aligned_data({game_id}) - game_info_sql: {query_elapsed:.3f}s")
    
    if not game_row or game_row[0] is None:
        # Fallback: try to get from canonical dataset (use first snapshot_ts as proxy)
        fallback_sql = """
        SELECT 
            MIN(snapshot_ts) as first_ts,
            MAX(snapshot_ts) as last_ts
        FROM derived.snapshot_features_v1
        WHERE game_id = %s AND season_label = '2025-26'
        """
        query_start = time.time()
        fallback_row = conn.execute(fallback_sql, (game_id,)).fetchone()
        query_elapsed = time.time() - query_start
        # logger.info(f"[TIMING] get_aligned_data({game_id}) - fallback_sql: {query_elapsed:.3f}s")
        
        if not fallback_row or fallback_row[0] is None:
            raise ValueError(f"No data found for game {game_id}. Make sure the game has ESPN data loaded.")
        
        game_start = fallback_row[0]  # Use first snapshot_ts as proxy for game start
        duration_seconds = int((fallback_row[1] - fallback_row[0]).total_seconds()) if fallback_row[1] else None
        final_home_score = None
        final_away_score = None
    else:
        game_start = game_row[0]
        final_home_score = game_row[1]
        final_away_score = game_row[2]
        
        # Calculate duration from canonical dataset
        duration_sql = """
        SELECT 
            EXTRACT(EPOCH FROM (MAX(snapshot_ts) - MIN(snapshot_ts)))::INTEGER as duration_seconds
        FROM derived.snapshot_features_v1
        WHERE game_id = %s AND season_label = '2025-26'
        """
        query_start = time.time()
        duration_row = conn.execute(duration_sql, (game_id,)).fetchone()
        query_elapsed = time.time() - query_start
        # logger.info(f"[TIMING] get_aligned_data({game_id}) - duration_sql: {query_elapsed:.3f}s")
        duration_seconds = duration_row[0] if duration_row and duration_row[0] is not None else None
    
    game_start_timestamp = int(game_start.timestamp()) if game_start else None
    
    # Calculate actual outcome
    actual_outcome = None
    if final_home_score is not None and final_away_score is not None:
        actual_outcome = 1 if final_home_score > final_away_score else 0
    
    # Query canonical dataset - single query gets everything we need
    # Query both home and away Kalshi fields to enable away→home conversion when home data is missing
    # If model provided, also query game state features needed for model scoring
    base_columns = [
        "sf.snapshot_ts",
        "sf.espn_home_prob",
        "sf.kalshi_home_mid_price",
        "sf.kalshi_home_bid",
        "sf.kalshi_home_ask",
        "sf.kalshi_away_mid_price",
        "sf.kalshi_away_bid",
        "sf.kalshi_away_ask",
        "sf.time_remaining"
    ]
    
    # Map model_name to pre-computed probability column
    model_prob_column = None
    model_prob_col_idx = None
    if model_name:
        model_prob_map = {
            "logreg_platt": "mp.logreg_platt_prob",
            "logreg_isotonic": "mp.logreg_isotonic_prob",
            "catboost_platt": "mp.catboost_platt_prob",
            "catboost_isotonic": "mp.catboost_isotonic_prob",
        }
        if model_name in model_prob_map:
            model_prob_column = model_prob_map[model_name]
            # Store the index where we'll add this column (after base columns, before model features)
            model_prob_col_idx = len(base_columns)
            base_columns.append(model_prob_column)
    
    # Add model features if model is provided (needed for fallback on-the-fly scoring)
    if model_artifact is not None:
        base_columns.append("sf.score_diff")  # Required for point_differential
        # Add interaction terms if model uses them
        if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
            base_columns.append("sf.score_diff_div_sqrt_time_remaining")
        if any("espn_home_prob_lag_1" in fn for fn in model_artifact.feature_names):
            base_columns.append("sf.espn_home_prob_lag_1")
        if any("espn_home_prob_delta_1" in fn for fn in model_artifact.feature_names):
            base_columns.append("sf.espn_home_prob_delta_1")
        if any("period" in fn for fn in model_artifact.feature_names):
            base_columns.append("sf.period")
    
    # Build SQL query - join with pre-computed probabilities if model_name provided
    if model_name and model_prob_column:
        canonical_sql = f"""
    SELECT 
            {", ".join(base_columns)}
        FROM derived.snapshot_features_v1 sf
        LEFT JOIN derived.model_probabilities_v1 mp
            ON sf.season_label = mp.season_label
            AND sf.game_id = mp.game_id
            AND sf.sequence_number = mp.sequence_number
            AND sf.snapshot_ts = mp.snapshot_ts
        WHERE sf.game_id = %s 
          AND sf.season_label = '2025-26'
        ORDER BY sf.sequence_number, sf.snapshot_ts
        """
    else:
        canonical_sql = f"""
        SELECT 
            {", ".join(base_columns)}
        FROM derived.snapshot_features_v1 sf
        WHERE sf.game_id = %s 
          AND sf.season_label = '2025-26'
        ORDER BY sf.sequence_number, sf.snapshot_ts
    """
    
    query_start = time.time()
    canonical_rows = conn.execute(canonical_sql, (game_id,)).fetchall()
    query_elapsed = time.time() - query_start
    # logger.info(f"[TIMING] get_aligned_data({game_id}) - canonical_sql: {query_elapsed:.3f}s - rows={len(canonical_rows)}")
    
    if not canonical_rows:
        logger.warning(f"[ALIGN_DATA] Game {game_id}: ❌ No data found in canonical dataset")
        return [], game_start_timestamp, duration_seconds, actual_outcome
    
    logger.debug(f"[ALIGN_DATA] Game {game_id}: Found {len(canonical_rows)} rows in canonical dataset")
    
    # Process canonical dataset rows into aligned_data format
    aligned_data = []
    filtered_by_time_window = 0
    filtered_missing_espn = 0
    filtered_missing_kalshi = 0
    filtered_out_of_range = 0
    
    # Track home/away presence for diagnostic logging
    rows_with_home_mid = 0
    rows_with_away_mid = 0
    
    # Track which price source was used (for debugging)
    used_home_prices = 0
    used_away_fallback_prices = 0
    
    # Normalization helper: convert values > 1.0 to 0-1 range (handles 0-100 format)
    def _norm01(x):
        """Normalize value to 0-1 range. Handles None, 0-1, and 0-100 formats."""
        if x is None:
            return None
        x = float(x)
        # Guard: if canonical view accidentally returns 0-100, normalize
        if 1.0 < x <= 100.0:
            x /= 100.0
        return x
    
    # Calculate elapsed time from game start for each snapshot
    # Canonical dataset snapshot_ts is the ESPN recording timestamp (last_modified_utc)
    # We need to align it to game timeline: game_start + (snapshot_ts - first_snapshot_ts)
    # FIX: Use MIN(snapshot_ts) from all rows, not just first ordered row
    # This ensures we anchor to the actual earliest timestamp, not just the first row
    first_snapshot_ts = min(r[0] for r in canonical_rows if r[0] is not None) if canonical_rows else None
    first_snapshot_timestamp = int(first_snapshot_ts.timestamp()) if first_snapshot_ts else None
    
    for row in canonical_rows:
        snapshot_ts = row[0]  # TIMESTAMPTZ (ESPN recording timestamp)
        espn_home_prob = row[1]  # May be 0-1 or 0-100 format (will normalize)
        kalshi_home_mid_price = row[2]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        kalshi_home_bid = row[3]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        kalshi_home_ask = row[4]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        kalshi_away_mid_price = row[5]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        kalshi_away_bid = row[6]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        kalshi_away_ask = row[7]  # May be 0-1 or 0-100 format (will normalize), can be NULL
        time_remaining = row[8]  # Seconds remaining in game
        
        # Track home/away presence
        if kalshi_home_mid_price is not None:
            rows_with_home_mid += 1
        if kalshi_away_mid_price is not None:
            rows_with_away_mid += 1
        
        if snapshot_ts is None:
            continue
        
        # Convert snapshot_ts to Unix timestamp
        snapshot_timestamp = int(snapshot_ts.timestamp())
        
        # Align to game timeline: match original behavior
        # Calculate elapsed time from first snapshot to this snapshot
        # Then map to game timeline: game_start + elapsed time
        if game_start_timestamp is not None and first_snapshot_timestamp is not None:
            # Calculate elapsed time from first snapshot to this snapshot
            elapsed_from_first = snapshot_timestamp - first_snapshot_timestamp
            # Map to game timeline: game_start + elapsed time (matches original behavior)
            aligned_timestamp = game_start_timestamp + elapsed_from_first
        else:
            # Fallback: use snapshot timestamp directly
            aligned_timestamp = snapshot_timestamp
        
        # Apply time filtering (exclude_first_seconds, exclude_last_seconds)
        if game_start_timestamp is not None and duration_seconds is not None:
            elapsed = aligned_timestamp - game_start_timestamp
            if elapsed < exclude_first_seconds:
                filtered_by_time_window += 1
                continue
            if elapsed > (duration_seconds - exclude_last_seconds):
                filtered_by_time_window += 1
                continue
        
        # Fix 4: Prefer price source based on bid/ask availability
        # IMPORTANT: In derived.snapshot_features_v1, kalshi_away_* values are ALREADY
        # converted into HOME probability space by the SQL view (1 - away_market_price, with bid/ask swap).
        # Therefore we must NOT invert again here - use away fields directly as fallback.
        # 
        # Selection logic: Prefer source with BOTH bid and ask if available.
        # Else prefer source with more complete data (both bid/ask > one > mid-only).
        # This ensures we maximize entry/exit opportunities.
        home_has_both = (kalshi_home_bid is not None and kalshi_home_ask is not None)
        home_has_one = (kalshi_home_bid is not None or kalshi_home_ask is not None)
        away_has_both = (kalshi_away_bid is not None and kalshi_away_ask is not None)
        away_has_one = (kalshi_away_bid is not None or kalshi_away_ask is not None)
        
        # Determine which source yields best usable bid/ask
        if kalshi_home_mid_price is not None and kalshi_away_mid_price is not None:
            # Both available: prefer source with both bid/ask, else prefer more complete
            if home_has_both and not away_has_both:
                kalshi_price = kalshi_home_mid_price
                kalshi_bid = kalshi_home_bid
                kalshi_ask = kalshi_home_ask
                used_home_prices += 1
            elif away_has_both and not home_has_both:
                kalshi_price = kalshi_away_mid_price
                kalshi_bid = kalshi_away_bid
                kalshi_ask = kalshi_away_ask
                used_away_fallback_prices += 1
            elif home_has_one and not away_has_one:
                kalshi_price = kalshi_home_mid_price
                kalshi_bid = kalshi_home_bid
                kalshi_ask = kalshi_home_ask
                used_home_prices += 1
            elif away_has_one and not home_has_one:
                kalshi_price = kalshi_away_mid_price
                kalshi_bid = kalshi_away_bid
                kalshi_ask = kalshi_away_ask
                used_away_fallback_prices += 1
            else:
                # Both have same completeness, prefer home
                kalshi_price = kalshi_home_mid_price
                kalshi_bid = kalshi_home_bid
                kalshi_ask = kalshi_home_ask
                used_home_prices += 1
            
            # Sanity guard: Future-proofing check for canonical dataset format changes
            # Current behavior: away is already in home-space, so home ≈ away (not complementary)
            # If canonical dataset switches to raw away-space, home + away would sum to ~1.0
            # Normalize values first (handle 0-100 format) and convert to float to avoid Decimal/float mixing
            home_norm_val = float(kalshi_home_mid_price)
            away_norm_val = float(kalshi_away_mid_price)
            home_norm = home_norm_val if home_norm_val <= 1.0 else home_norm_val / 100.0
            away_norm = away_norm_val if away_norm_val <= 1.0 else away_norm_val / 100.0
            
            diff_check = abs(home_norm - away_norm)  # Should be small if away is already converted
            sum_check = abs((home_norm + away_norm) - 1.0)  # Would be small if away is raw
            
            if diff_check < 0.05:
                # Current expected behavior: away is already converted, so home ≈ away
                pass  # This is correct, no warning needed
            elif sum_check < 0.05:
                # WARNING: This suggests canonical dataset switched to raw away-space
                logger.warning(f"[ALIGN_DATA] Game {game_id}: WARNING - home + away prices sum to ~1.0 (diff: {sum_check:.4f}). "
                             f"This suggests canonical dataset may have switched to raw away-space. "
                             f"home={home_norm:.4f}, away={away_norm:.4f}. "
                             f"Python code should convert away→home if this becomes the norm.")
            # Else: large difference and don't sum to 1 - shrug, might be data quality issue
        elif kalshi_home_mid_price is not None:
            kalshi_price = kalshi_home_mid_price
            kalshi_bid = kalshi_home_bid
            kalshi_ask = kalshi_home_ask
            used_home_prices += 1
        elif kalshi_away_mid_price is not None:
            # Use away fields directly - they're already in home probability space from SQL view
            kalshi_price = kalshi_away_mid_price
            kalshi_bid = kalshi_away_bid
            kalshi_ask = kalshi_away_ask
            used_away_fallback_prices += 1
        else:
            kalshi_price = None
            kalshi_bid = None
            kalshi_ask = None
        
        # Normalize all probability/price fields to 0-1 range (handles 0-100 format)
        espn_home_prob = _norm01(espn_home_prob)
        kalshi_price = _norm01(kalshi_price)
        kalshi_bid = _norm01(kalshi_bid)
        kalshi_ask = _norm01(kalshi_ask)
        
        # Filter out rows without required data - simulation requires both espn_prob and kalshi_price
        # Skip rows where espn_prob is NULL (no ESPN probability data available)
        if espn_home_prob is None:
            filtered_missing_espn += 1
            logger.debug(f"[ALIGN_DATA] Game {game_id}: Snapshot {snapshot_ts} has no ESPN probability data - skipping")
            continue  # Skip this row - can't calculate divergence without ESPN probability
        
        # Skip rows where kalshi_price is NULL (no Kalshi market data available)
        if kalshi_price is None:
            filtered_missing_kalshi += 1
            logger.debug(f"[ALIGN_DATA] Game {game_id}: Snapshot {snapshot_ts} has no Kalshi data - skipping")
            continue  # Skip this row - can't calculate divergence without Kalshi price
        
        # Range checks: ensure values are in [0,1] after normalization
        if espn_home_prob < 0.0 or espn_home_prob > 1.0:
            logger.warning(f"[ALIGN_DATA] Game {game_id}: ESPN prob out of range: {espn_home_prob}, skipping point")
            filtered_out_of_range += 1
            continue
        
        if kalshi_price < 0.0 or kalshi_price > 1.0:
            logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi price out of range: {kalshi_price}, skipping point")
            filtered_out_of_range += 1
            continue
        
        # Set bid/ask to None if out of range (don't fail the point)
        if kalshi_bid is not None and (kalshi_bid < 0.0 or kalshi_bid > 1.0):
            logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi bid out of range: {kalshi_bid}, setting to None")
            kalshi_bid = None
        if kalshi_ask is not None and (kalshi_ask < 0.0 or kalshi_ask > 1.0):
            logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi ask out of range: {kalshi_ask}, setting to None")
            kalshi_ask = None
        
        # If model provided, use model probability instead of ESPN
        # First try pre-computed probability if model_name provided, else fall back to on-the-fly scoring
        final_prob = float(espn_home_prob)  # Default to ESPN probability
        
        # Check for pre-computed probability first (if model_name provided)
        precomputed_prob = None
        if model_name and model_prob_col_idx is not None:
            # Use the stored index for the pre-computed probability column
            if len(row) > model_prob_col_idx:
                precomputed_prob = row[model_prob_col_idx]
        
        if precomputed_prob is not None:
            # Use pre-computed probability
            final_prob = float(precomputed_prob)
            # Validate range
            if final_prob < 0.0 or final_prob > 1.0:
                logger.warning(f"[ALIGN_DATA] Game {game_id}: Pre-computed prob out of range: {final_prob}, using ESPN prob")
                final_prob = float(espn_home_prob)
        elif model_artifact is not None:
            try:
                # Extract model features from row
                # Row indices: 0=snapshot_ts, 1=espn_home_prob, 2-7=kalshi, 8=time_remaining
                # If model_name provided: 9=precomputed_prob
                # If model_artifact provided: 9 or 10=score_diff (depending on whether precomputed_prob exists), then optional features
                # Note: Column order must match SQL query order exactly
                if len(row) < 9:
                    logger.warning(f"[ALIGN_DATA] Game {game_id}: Row has insufficient columns ({len(row)} < 9), using ESPN prob")
                    final_prob = float(espn_home_prob)
                    continue
                
                # Start after base columns (0-8) and pre-computed prob (if present)
                row_idx = 9  # Base columns end at 8
                if model_prob_col_idx is not None:
                    row_idx += 1  # Skip pre-computed prob column
                
                score_diff = row[row_idx] if len(row) > row_idx else None
                row_idx += 1
                
                # Extract optional features if present
                score_diff_div_sqrt_time_remaining = None
                espn_home_prob_lag_1 = None
                espn_home_prob_delta_1 = None
                period_val = None
                
                if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
                    score_diff_div_sqrt_time_remaining = row[row_idx] if len(row) > row_idx else None
                    row_idx += 1
                if any("espn_home_prob_lag_1" in fn for fn in model_artifact.feature_names):
                    espn_home_prob_lag_1 = row[row_idx] if len(row) > row_idx else None
                    row_idx += 1
                if any("espn_home_prob_delta_1" in fn for fn in model_artifact.feature_names):
                    espn_home_prob_delta_1 = row[row_idx] if len(row) > row_idx else None
                    row_idx += 1
                if any("period" in fn for fn in model_artifact.feature_names):
                    period_val = row[row_idx] if len(row) > row_idx else None
                    row_idx += 1
                
                # Validate required features
                if score_diff is None or time_remaining is None:
                    logger.warning(f"[ALIGN_DATA] Game {game_id}: Missing required model features (score_diff or time_remaining), using ESPN prob")
                else:
                    # Build design matrix for single snapshot
                    point_differential = np.array([float(score_diff)])
                    time_remaining_regulation = np.array([float(time_remaining)])
                    possession = ["unknown"]  # Canonical dataset doesn't have possession, default to unknown
                    
                    # Build optional arrays - must pass if model uses them, even if value is None
                    # build_design_matrix will only add features if they're not None, so we need to provide defaults
                    score_diff_div_sqrt_arr = None
                    if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
                        if score_diff_div_sqrt_time_remaining is not None:
                            score_diff_div_sqrt_arr = np.array([float(score_diff_div_sqrt_time_remaining)])
                        else:
                            # Model expects this but value is missing - calculate from score_diff and time_remaining
                            if score_diff is not None and time_remaining is not None:
                                import math
                                score_diff_div_sqrt_arr = np.array([float(score_diff) / math.sqrt(float(time_remaining) + 1)])
                    
                    espn_prob_arr = None
                    # Check specifically for "espn_home_prob_scaled" (not lag_1 or delta_1)
                    if any(fn == "espn_home_prob_scaled" for fn in model_artifact.feature_names):
                        # espn_home_prob is always available (it's in base columns)
                        espn_prob_arr = np.array([float(espn_home_prob)])
                    
                    espn_prob_lag_1_arr = None
                    if any("espn_home_prob_lag_1" in fn for fn in model_artifact.feature_names):
                        if espn_home_prob_lag_1 is not None:
                            espn_prob_lag_1_arr = np.array([float(espn_home_prob_lag_1)])
                        else:
                            # Model expects this but value is missing - use current espn_home_prob as fallback
                            espn_prob_lag_1_arr = np.array([float(espn_home_prob)])
                    
                    espn_prob_delta_1_arr = None
                    if any("espn_home_prob_delta_1" in fn for fn in model_artifact.feature_names):
                        if espn_home_prob_delta_1 is not None:
                            espn_prob_delta_1_arr = np.array([float(espn_home_prob_delta_1)])
                        else:
                            # Model expects this but value is missing - use 0 as fallback (no change)
                            espn_prob_delta_1_arr = np.array([0.0])
                    
                    period_arr = None
                    if any("period" in fn for fn in model_artifact.feature_names):
                        if period_val is not None:
                            period_arr = [int(period_val)]
                        else:
                            # Model expects period but value is missing - default to 1 (first period)
                            period_arr = [1]
                    
                    # Build design matrix
                    X = build_design_matrix(
                        point_differential=point_differential,
                        time_remaining_regulation=time_remaining_regulation,
                        possession=possession,
                        preprocess=model_artifact.preprocess,
                        score_diff_div_sqrt_time_remaining=score_diff_div_sqrt_arr,
                        espn_home_prob=espn_prob_arr,
                        espn_home_prob_lag_1=espn_prob_lag_1_arr,
                        espn_home_prob_delta_1=espn_prob_delta_1_arr,
                        period=period_arr
                    )
                    
                    # Validate design matrix shape matches model expectations BEFORE prediction
                    expected_features = len(model_artifact.feature_names)
                    actual_features = X.shape[1] if X.ndim == 2 else X.shape[0]
                    if actual_features != expected_features:
                        logger.warning(
                            f"[ALIGN_DATA] Game {game_id}: Design matrix feature mismatch: "
                            f"expected {expected_features} features, got {actual_features}. "
                            f"Model features: {model_artifact.feature_names}. "
                            f"Design matrix shape: {X.shape}. Using ESPN prob instead."
                        )
                        final_prob = float(espn_home_prob)
                    else:
                        # Predict probability
                        try:
                            prob_array = predict_proba(model_artifact, X=X)
                            final_prob = float(prob_array[0])
                        except Exception as pred_error:
                            logger.warning(
                                f"[ALIGN_DATA] Game {game_id}: Prediction error: {pred_error}. "
                                f"X shape: {X.shape}, model weights: {len(model_artifact.model.weights)}. "
                                f"Using ESPN prob instead."
                            )
                            final_prob = float(espn_home_prob)
                    
                    # Validate model probability is in [0,1]
                    if final_prob < 0.0 or final_prob > 1.0:
                        logger.warning(f"[ALIGN_DATA] Game {game_id}: Model prob out of range: {final_prob}, using ESPN prob")
                        final_prob = float(espn_home_prob)
            except Exception as e:
                logger.warning(f"[ALIGN_DATA] Game {game_id}: Error scoring model: {e}, using ESPN prob")
                final_prob = float(espn_home_prob)
        
        aligned_data.append({
            "timestamp": aligned_timestamp,
            "espn_prob": final_prob,  # May be model probability if model provided
            "kalshi_price": float(kalshi_price),  # Already checked for None above
            "kalshi_bid": float(kalshi_bid) if kalshi_bid is not None else None,
            "kalshi_ask": float(kalshi_ask) if kalshi_ask is not None else None,
        })
    
    logger.debug(f"[ALIGN_DATA] Game {game_id}: Processed {len(aligned_data)} aligned data points")
    logger.debug(f"[ALIGN_DATA] Game {game_id}: Filtered out - {filtered_by_time_window} by time window, {filtered_missing_espn} missing ESPN, {filtered_missing_kalshi} missing Kalshi, {filtered_out_of_range} out of range")
    logger.debug(f"[ALIGN_DATA] Game {game_id}: Price source usage - used_home_prices={used_home_prices}, used_away_fallback_prices={used_away_fallback_prices}")
    
    if not aligned_data:
        pct_home = (rows_with_home_mid / len(canonical_rows) * 100) if canonical_rows else 0.0
        pct_away = (rows_with_away_mid / len(canonical_rows) * 100) if canonical_rows else 0.0
        logger.warning(f"[ALIGN_DATA] Game {game_id}: ❌ No aligned data found after processing")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Canonical dataset rows: {len(canonical_rows)}")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Rows with home mid: {rows_with_home_mid} ({pct_home:.1f}%)")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Rows with away mid: {rows_with_away_mid} ({pct_away:.1f}%)")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by time window: {filtered_by_time_window}")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by missing ESPN: {filtered_missing_espn}")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by missing Kalshi: {filtered_missing_kalshi}")
        logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by out of range: {filtered_out_of_range}")
    
    # FIX: Sort aligned_data by timestamp to ensure chronological order
    # This restores the "time moves forward" assumption required by simulation
    aligned_data.sort(key=lambda p: p["timestamp"])
    
    elapsed = time.time() - start_time
    # logger.info(f"[TIMING] get_aligned_data({game_id}) - TOTAL: {elapsed:.3f}s - aligned_points={len(aligned_data)}, use_trade_data={use_trade_data} (deprecated)")
    return aligned_data, game_start_timestamp, duration_seconds, actual_outcome


# REMOVED: _get_kalshi_candlestick_data() and _get_kalshi_trade_data() functions
# These functions are no longer needed since get_aligned_data() now uses the canonical dataset
# (derived.snapshot_features_v1) which already has Kalshi data aligned with ESPN data.
# The canonical dataset provides a single source of truth with pre-computed features and aligned timestamps.
# 
# If you need to reference the old implementation for regression testing or comparison,
# see git history before Sprint 14 (commit before 2026-01-04).


def calculate_kalshi_fee(price: float, bet_amount: float) -> float:
    """
    Calculate Kalshi trading fee.
    
    Formula: 7% × (price × (1 - price)) × bet_amount
    Fees are highest at 50% probability, decrease toward extremes.
    
    Args:
        price: Contract price in 0-1 range (e.g., 0.50 = 50%)
        bet_amount: Bet amount in dollars
    
    Returns:
        Fee in dollars
    """
    # Defensive checks for edge cases
    if price is None or bet_amount is None:
        logger.warning(f"[FEE] Invalid input to calculate_kalshi_fee: price={price}, bet_amount={bet_amount}")
        return 0.0
    
    # Convert to float to handle Decimal types from database
    try:
        price = float(price)
        bet_amount = float(bet_amount)
    except (TypeError, ValueError) as e:
        logger.warning(f"[FEE] Failed to convert to float: price={price}, bet_amount={bet_amount}: {e}")
        return 0.0
    
    # Check for NaN or Inf
    if math.isnan(price) or math.isinf(price) or math.isnan(bet_amount) or math.isinf(bet_amount):
        logger.warning(f"[FEE] Invalid numeric value: price={price}, bet_amount={bet_amount}")
        return 0.0
    
    if price <= 0.0 or price >= 1.0:
        return 0.0
    fee_rate = 0.07 * (price * (1 - price))
    return fee_rate * bet_amount


def calculate_slippage_cost(bet_amount: float, slippage_rate: float = 0.0) -> float:
    """
    Calculate slippage cost as a conservative execution penalty.
    
    **ASSUMPTION**: This is a configurable conservative estimate, not a precise model.
    Slippage represents execution cost beyond bid-ask spread (e.g., market impact).
    
    Args:
        bet_amount: Bet amount in dollars
        slippage_rate: Slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled)
    
    Returns:
        Slippage cost in dollars (0.0 if slippage_rate is 0.0)
    """
    if slippage_rate <= 0.0:
        return 0.0
    return slippage_rate * bet_amount


def calculate_trade_pnl(
    trade: Trade,
    bet_amount_dollars: float = 1.0,
    slippage_rate: float = 0.0,
    enable_fees: bool = False
) -> dict[str, float]:
    """
    Calculate trade P&L with costs.
    
    This function calculates P&L based on price movements, NOT final game outcome.
    Spread cost is already embedded in bid/ask execution prices (NOT double-counted).
    Only fees and optional slippage are added as costs.
    
    Fix 1: Fee model matches position sizing (contracts)
    - Fees are computed based on actual traded quantity (dollar_volume = num_contracts * execution_price)
    - This ensures fees scale with position size, not just risk budget
    
    Fix 2: Clamp prices to [0,1] range
    - All constructed bid/ask prices are clamped before use
    - Prevents invalid prices from causing calculation errors
    
    Fix 3: Avoid double-counting slippage
    - If a leg used price penalty (fallback/forced), do NOT add slippage_rate dollar cost
    - Price penalties and slippage_rate are mutually exclusive per leg
    
    Args:
        trade: Trade object with entry/exit information
        bet_amount_dollars: Amount bet per contract (default: $1.00)
        slippage_rate: Optional slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled)
        enable_fees: Enable Kalshi trading fees (7% formula). Default: False
    
    Returns dictionary with:
        - gross_profit: Gross profit in dollars (before costs)
        - net_profit: Net profit in dollars (after costs)
        - total_costs: Total costs in dollars
        - entry_fee: Entry fee in dollars
        - exit_fee: Exit fee in dollars
        - slippage_cost: Slippage cost in dollars (0.0 if disabled)
    
    Long positions: Buy at ask (entry), sell at bid (exit)
    Short positions: Sell at bid (entry), buy at ask (exit)
    
    Position Sizing:
    - Long: num_contracts = bet_amount / entry_price (max loss = entry_price per contract)
    - Short: num_contracts = bet_amount / (1 - entry_price) (max loss = 1-entry_price per contract)
    - Both positions have same maximum risk (bet_amount) for risk-neutral sizing
    
    Note: This is a trading simulator, not a betting simulator. P&L is calculated
    from price movements, not binary outcomes. The actual_outcome field is kept
    for display/logging purposes but is NOT used in P&L calculation.
    """
    # Fix 2: Helper to clamp prices to [0,1] range
    def clamp01(x: Optional[float]) -> Optional[float]:
        """Clamp price to [0,1] range, return None if input is None."""
        if x is None:
            return None
        return max(0.0, min(1.0, float(x)))
    
    # SANITY CHECKS (post-fix validation):
    # - Fees are contract-consistent: dollar_volume = num_contracts * execution_price ensures fees scale
    #   with actual traded quantity, not just risk budget. This matches how positions are sized.
    # - Clamping prevents invalid prices: All constructed bid/ask (fallback/forced) are clamped to [0,1]
    #   before use, preventing division by zero or out-of-range calculations.
    # - Slippage is not double-counted: Price penalties (fallback/forced) and slippage_rate dollar cost
    #   are mutually exclusive per leg. If trade.entry_used_price_penalty or trade.exit_used_price_penalty
    #   is True, we skip slippage_rate cost for that leg.
    
    # Fallback to mid-price if bid/ask unavailable (with warning)
    if trade.position_type == "long_espn":
        # Long: Buy at ask, sell at bid
        entry_price = trade.entry_kalshi_ask
        exit_price = trade.exit_kalshi_bid
        
        # Fallback to mid-price if bid/ask unavailable
        if entry_price is None:
            entry_price = trade.entry_kalshi_price
            logger.warning(f"[P&L] Missing entry_kalshi_ask, using mid-price {entry_price}")
        if exit_price is None:
            exit_price = trade.exit_kalshi_price
            logger.warning(f"[P&L] Missing exit_kalshi_bid, using mid-price {exit_price}")
        
        # Fix 2: Clamp prices before use
        entry_price = clamp01(entry_price)
        exit_price = clamp01(exit_price)
        
        if entry_price is None or exit_price is None or entry_price <= 0:
            logger.warning(f"[P&L] Invalid prices for long position: entry={entry_price}, exit={exit_price}")
            return {
                "gross_profit": 0.0,
                "net_profit": 0.0,
                "total_costs": 0.0,
                "entry_fee": 0.0,
                "exit_fee": 0.0,
                "slippage_cost": 0.0
            }
        
        # Calculate position size and gross profit
        # Defensive check: ensure entry_price is valid before division
        if entry_price <= 0 or not math.isfinite(entry_price):
            logger.warning(f"[P&L] Invalid entry_price for long position: {entry_price}")
            return {
                "gross_profit": 0.0,
                "net_profit": 0.0,
                "total_costs": 0.0,
                "entry_fee": 0.0,
                "exit_fee": 0.0,
                "slippage_cost": 0.0
            }
        
        num_contracts = bet_amount_dollars / entry_price
        price_movement = exit_price - entry_price
        gross_profit = num_contracts * price_movement
        
        # Fix 1: Calculate fees based on actual traded quantity (dollar_volume)
        # Entry leg: dollar_volume_entry = num_contracts * entry_price
        # Exit leg: dollar_volume_exit = num_contracts * exit_price
        dollar_volume_entry = num_contracts * entry_price
        dollar_volume_exit = num_contracts * exit_price
        
        # Fix 2: Ensure prices are valid for fee calculation
        entry_price_for_fee = clamp01(entry_price) or 0.0
        exit_price_for_fee = clamp01(exit_price) or 0.0
        
        # Fix 1: Calculate fees using dollar_volume (contract-consistent)
        entry_fee = calculate_kalshi_fee(entry_price_for_fee, dollar_volume_entry) if enable_fees else 0.0
        exit_fee = calculate_kalshi_fee(exit_price_for_fee, dollar_volume_exit) if enable_fees else 0.0
        
        # Fix 3: Avoid double-counting slippage - only add slippage_rate cost if price penalty was NOT used
        entry_slippage = 0.0 if trade.entry_used_price_penalty else calculate_slippage_cost(dollar_volume_entry, slippage_rate)
        exit_slippage = 0.0 if trade.exit_used_price_penalty else calculate_slippage_cost(dollar_volume_exit, slippage_rate)
        
        total_costs = entry_fee + exit_fee + entry_slippage + exit_slippage
        net_profit = gross_profit - total_costs
        
        # Final validation: ensure all values are finite
        result = {
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "total_costs": total_costs,
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "slippage_cost": entry_slippage + exit_slippage
        }
        
        # Replace NaN/Inf with 0.0
        for key, value in result.items():
            if not math.isfinite(value):
                logger.warning(f"[P&L] Non-finite value for {key} (long): {value}, replacing with 0.0")
                result[key] = 0.0
        
        return result
    
    elif trade.position_type == "short_espn":
        # Short: Sell at bid, buy at ask
        entry_price = trade.entry_kalshi_bid
        exit_price = trade.exit_kalshi_ask
        
        # Fallback to mid-price if bid/ask unavailable
        if entry_price is None:
            entry_price = trade.entry_kalshi_price
            logger.warning(f"[P&L] Missing entry_kalshi_bid, using mid-price {entry_price}")
        if exit_price is None:
            exit_price = trade.exit_kalshi_price
            logger.warning(f"[P&L] Missing exit_kalshi_ask, using mid-price {exit_price}")
        
        # Fix 2: Clamp prices before use
        entry_price = clamp01(entry_price)
        exit_price = clamp01(exit_price)
        
        if entry_price is None or exit_price is None or entry_price <= 0 or entry_price >= 1.0:
            logger.warning(f"[P&L] Invalid prices for short position: entry={entry_price}, exit={exit_price}")
            return {
                "gross_profit": 0.0,
                "net_profit": 0.0,
                "total_costs": 0.0,
                "entry_fee": 0.0,
                "exit_fee": 0.0,
                "slippage_cost": 0.0
            }
        
        # Calculate position size and gross profit
        # Risk-neutral sizing: Short positions have max loss = (1 - entry_price) per contract
        # To match long positions' max risk (bet_amount), use: num_contracts = bet_amount / (1 - entry_price)
        # Defensive check: ensure entry_price is valid before division
        if entry_price <= 0 or entry_price >= 1.0 or not math.isfinite(entry_price):
            logger.warning(f"[P&L] Invalid entry_price for short position: {entry_price}")
            return {
                "gross_profit": 0.0,
                "net_profit": 0.0,
                "total_costs": 0.0,
                "entry_fee": 0.0,
                "exit_fee": 0.0,
                "slippage_cost": 0.0
            }
        
        # Fix 2: Ensure exit_price is valid
        exit_price = clamp01(exit_price)
        if exit_price is None or not math.isfinite(exit_price):
            logger.warning(f"[P&L] Invalid exit_price for short position: {exit_price}, using 0.5")
            exit_price = 0.5
        
        num_contracts = bet_amount_dollars / (1 - entry_price)  # Risk-neutral sizing
        entry_premium = num_contracts * entry_price  # Premium received from selling
        exit_cost = num_contracts * exit_price  # Cost to buy back
        gross_profit = entry_premium - exit_cost
        
        # Fix 1: Calculate fees based on actual traded quantity (dollar_volume)
        # Entry leg: dollar_volume_entry = num_contracts * entry_price
        # Exit leg: dollar_volume_exit = num_contracts * exit_price
        dollar_volume_entry = num_contracts * entry_price
        dollar_volume_exit = num_contracts * exit_price
        
        # Fix 2: Ensure prices are valid for fee calculation
        entry_price_for_fee = clamp01(entry_price) or 0.0
        exit_price_for_fee = clamp01(exit_price) or 0.0
        
        # Fix 1: Calculate fees using dollar_volume (contract-consistent)
        entry_fee = calculate_kalshi_fee(entry_price_for_fee, dollar_volume_entry) if enable_fees else 0.0
        exit_fee = calculate_kalshi_fee(exit_price_for_fee, dollar_volume_exit) if enable_fees else 0.0
        
        # Fix 3: Avoid double-counting slippage - only add slippage_rate cost if price penalty was NOT used
        entry_slippage = 0.0 if trade.entry_used_price_penalty else calculate_slippage_cost(dollar_volume_entry, slippage_rate)
        exit_slippage = 0.0 if trade.exit_used_price_penalty else calculate_slippage_cost(dollar_volume_exit, slippage_rate)
        
        total_costs = entry_fee + exit_fee + entry_slippage + exit_slippage
        net_profit = gross_profit - total_costs
        
        # Final validation: ensure all values are finite
        result = {
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "total_costs": total_costs,
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "slippage_cost": entry_slippage + exit_slippage
        }
        
        # Replace NaN/Inf with 0.0
        for key, value in result.items():
            if not math.isfinite(value):
                logger.warning(f"[P&L] Non-finite value for {key} (short): {value}, replacing with 0.0")
                result[key] = 0.0
        
        return result
    
    return {
        "gross_profit": 0.0,
        "net_profit": 0.0,
        "total_costs": 0.0,
        "entry_fee": 0.0,
        "exit_fee": 0.0,
        "slippage_cost": 0.0
    }


def calculate_game_phase(entry_timestamp: int, game_start_timestamp: Optional[int], game_duration_seconds: Optional[int]) -> Optional[str]:
    """
    Calculate game phase (Q1, Q2-Q3, Q4) based on entry time.
    
    Args:
        entry_timestamp: Unix timestamp of trade entry
        game_start_timestamp: Unix timestamp of game start
        game_duration_seconds: Total game duration in seconds
    
    Returns:
        "Q1", "Q2-Q3", "Q4", or None if game timing unavailable
    """
    if game_start_timestamp is None or game_duration_seconds is None or game_duration_seconds <= 0:
        return None
    
    trade_time = entry_timestamp - game_start_timestamp
    phase_ratio = trade_time / game_duration_seconds
    
    if phase_ratio < 0.25:
        return "Q1"
    elif phase_ratio < 0.75:
        return "Q2-Q3"
    else:
        return "Q4"


def simulate_trading_strategy(
    aligned_data: list[dict[str, Any]],
    entry_threshold: float,
    exit_threshold: float,
    actual_outcome: Optional[int],
    bet_amount_dollars: float = 1.0,
    slippage_rate: float = 0.0,
    min_hold_seconds: int = 30,
    game_start_timestamp: Optional[int] = None,
    game_duration_seconds: Optional[int] = None,
    enable_fees: bool = False
) -> dict[str, Any]:
    """
    Simulate trading strategy on aligned ESPN-Kalshi data.
    
    **TRADING MODEL (NOT BETTING MODEL)**:
    - P&L is calculated based on entry/exit price differences, NOT final game outcome
    - Long positions: Buy at ask, sell at bid
    - Short positions: Sell at bid, buy at ask
    - Spread cost is already embedded in bid/ask execution prices (NOT double-counted)
    - Trading costs included: Kalshi fees (7% formula) + optional slippage
    
    Args:
        aligned_data: List of aligned (timestamp, espn_prob, kalshi_price, kalshi_bid, kalshi_ask)
        entry_threshold: Divergence threshold to enter position (probability units, e.g., 0.05 = 5 cents)
        exit_threshold: Divergence threshold to exit position (probability units, e.g., 0.01 = 1 cent)
        actual_outcome: 1 if home won, 0 if away won, None if unknown (for display/logging only, NOT used in P&L)
        bet_amount_dollars: Amount bet per trade (default: $1.00). Used for risk-neutral position sizing.
        slippage_rate: Optional slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled).
                      This is a conservative assumption, not a precise model.
        min_hold_seconds: Minimum holding period in seconds before allowing exit (default: 30). Prevents noise trading.
        game_start_timestamp: Unix timestamp of game start (optional, for game phase calculation)
        game_duration_seconds: Total game duration in seconds (optional, for game phase calculation)
    
    Returns:
        Dictionary with simulation results including:
        - total_profit_cents: NET profit after costs (for aggregation)
        - total_gross_profit_cents: Gross profit before costs (for reference)
        - num_trades: Number of trades executed
        - win_rate: Win rate based on net profit
        - trades: List of trade details (gross and net profit)
    """
    logger.debug(f"[SIMULATION] Starting simulation - {len(aligned_data)} aligned data points, entry_threshold={entry_threshold:.3f}, exit_threshold={exit_threshold:.3f}")
    
    # Fix 2: Helper to clamp prices to [0,1] range
    def clamp01(x: Optional[float]) -> Optional[float]:
        """Clamp price to [0,1] range, return None if input is None."""
        if x is None:
            return None
        return max(0.0, min(1.0, float(x)))
    
    state = SimulationState()
    entry_attempts_long = 0
    entry_attempts_short = 0
    entry_failed_divergence_long = 0
    entry_failed_divergence_short = 0
    entry_failed_bid_ask_long = 0
    entry_failed_bid_ask_short = 0
    successful_entries = 0
    exit_attempts = 0
    successful_exits = 0
    
    for point_idx, point in enumerate(aligned_data):
        timestamp = point.get("timestamp")
        espn_prob = point.get("espn_prob")
        kalshi_price = point.get("kalshi_price")
        kalshi_bid = point.get("kalshi_bid")
        kalshi_ask = point.get("kalshi_ask")
        
        # Defensive check: skip if required data is missing (shouldn't happen after filtering, but be safe)
        if espn_prob is None or kalshi_price is None or timestamp is None:
            # logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: missing required data (espn_prob={espn_prob}, kalshi_price={kalshi_price}, timestamp={timestamp})")
            continue
        
        # Ensure values are floats (defensive check)
        try:
            espn_prob = float(espn_prob)
            kalshi_price = float(kalshi_price)
        except (TypeError, ValueError) as e:
            # logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: invalid data types (espn_prob={espn_prob}, kalshi_price={kalshi_price}): {e}")
            continue
        
        # Runtime guard: ensure values are in [0,1] range
        if espn_prob < 0.0 or espn_prob > 1.0:
            # logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: ESPN prob out of range: {espn_prob}")
            continue
        if kalshi_price < 0.0 or kalshi_price > 1.0:
            # logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: Kalshi price out of range: {kalshi_price}")
            continue
        
        # Set bid/ask to None if out of range (don't fail the point)
        if kalshi_bid is not None:
            try:
                kalshi_bid = float(kalshi_bid)
                if kalshi_bid < 0.0 or kalshi_bid > 1.0:
                    # logger.warning(f"[SIMULATION] Point {point_idx+1}: Kalshi bid out of range: {kalshi_bid}, setting to None")
                    kalshi_bid = None
            except (TypeError, ValueError):
                kalshi_bid = None
        if kalshi_ask is not None:
            try:
                kalshi_ask = float(kalshi_ask)
                if kalshi_ask < 0.0 or kalshi_ask > 1.0:
                    # logger.warning(f"[SIMULATION] Point {point_idx+1}: Kalshi ask out of range: {kalshi_ask}, setting to None")
                    kalshi_ask = None
            except (TypeError, ValueError):
                kalshi_ask = None
        
        # Calculate divergence (in probability units, 0-1 range)
        divergence_prob = espn_prob - kalshi_price
        abs_divergence_prob = abs(divergence_prob)
        
        # Entry logic
        if state.open_position is None:
            # Long ESPN: ESPN > Kalshi + threshold AND divergence is widening (not shrinking)
            # Direction confirmation: Only enter when divergence is widening (prevents noise entries)
            if divergence_prob > entry_threshold:
                # Check direction confirmation: divergence must be widening
                is_widening = (state.prev_divergence_prob is None or divergence_prob > state.prev_divergence_prob)
                if not is_widening:
                    prev_div_str = f"{state.prev_divergence_prob*100:.2f}" if state.prev_divergence_prob is not None else "None"
                    logger.debug(f"[ENTRY] Entry blocked (LONG) - divergence is shrinking (prev: {prev_div_str} cents, current: {divergence_prob*100:.2f} cents)")
                else:
                    entry_attempts_long += 1
                    if kalshi_ask is not None:
                        state.open_position = "long_espn"
                        state.entry_espn_prob = espn_prob
                        state.entry_kalshi_price = kalshi_price
                        state.entry_kalshi_ask = kalshi_ask
                        state.entry_timestamp = timestamp
                        successful_entries += 1
                        # logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: ✓ ENTERED LONG - Divergence: {divergence_prob*100:.2f} cents (ESPN: {espn_prob*100:.1f}%, Kalshi: {kalshi_price*100:.1f}%)")
                    else:
                        # entry_failed_bid_ask_long += 1
                        logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: ✗ Entry failed (LONG) - Divergence sufficient ({divergence_prob*100:.2f} cents) but missing kalshi_ask")
            elif divergence_prob > 0:
                entry_failed_divergence_long += 1
            
            # Short ESPN: ESPN < Kalshi - threshold AND divergence is widening (not shrinking)
            # Direction confirmation: Only enter when divergence is widening (prevents noise entries)
            elif divergence_prob < -entry_threshold:
                # Check direction confirmation: divergence must be widening (more negative)
                is_widening = (state.prev_divergence_prob is None or divergence_prob < state.prev_divergence_prob)
                if not is_widening:
                    prev_div_str = f"{state.prev_divergence_prob*100:.2f}" if state.prev_divergence_prob is not None else "None"
                    logger.debug(f"[ENTRY] Entry blocked (SHORT) - divergence is shrinking (prev: {prev_div_str} cents, current: {divergence_prob*100:.2f} cents)")
                else:
                    entry_attempts_short += 1
                    if kalshi_bid is not None:
                        state.open_position = "short_espn"
                        state.entry_espn_prob = espn_prob
                        state.entry_kalshi_price = kalshi_price
                        state.entry_kalshi_bid = kalshi_bid
                        state.entry_timestamp = timestamp
                        successful_entries += 1
                        # logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: ✓ ENTERED SHORT - Divergence: {divergence_prob*100:.2f} cents (ESPN: {espn_prob*100:.1f}%, Kalshi: {kalshi_price*100:.1f}%)")
                    else:
                        entry_failed_bid_ask_short += 1
                        # logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: ✗ Entry failed (SHORT) - Divergence sufficient ({divergence_prob*100:.2f} cents) but missing kalshi_bid")
            elif divergence_prob < 0:
                entry_failed_divergence_short += 1
        
        # Exit logic
        elif state.open_position is not None:
            exit_attempts += 1
            # Exit on convergence (if minimum holding period met AND divergence crossed from outside to inside threshold)
            # Hysteresis: Only exit when divergence crosses FROM outside threshold TO inside threshold (prevents churn)
            # Timestamps are ints (Unix seconds), not datetime objects - no .total_seconds() needed
            time_held = (timestamp - state.entry_timestamp) if state.entry_timestamp else 0
            if abs_divergence_prob < exit_threshold:
                # Check hysteresis: divergence must have crossed from outside to inside threshold
                crossed_threshold = (state.prev_abs_divergence_prob is not None and 
                                    state.prev_abs_divergence_prob >= exit_threshold)
                if not crossed_threshold:
                    prev_abs_div_str = f"{state.prev_abs_divergence_prob*100:.2f}" if state.prev_abs_divergence_prob is not None else "None"
                    logger.debug(f"[EXIT] Exit blocked - divergence did not cross from outside threshold (prev: {prev_abs_div_str} cents, current: {abs_divergence_prob*100:.2f} cents)")
                elif time_held < min_hold_seconds:
                    logger.debug(f"[EXIT] Exit blocked - minimum holding period not met ({time_held:.1f}s < {min_hold_seconds}s)")
                else:
                    # Close position - capture bid/ask prices for exit
                    # Long positions exit by selling at bid, short positions exit by buying at ask
                    exit_kalshi_bid = kalshi_bid  # For long exit (sell at bid)
                    exit_kalshi_ask = kalshi_ask  # For short exit (buy at ask)
                    
                    # Fix 3: Track if exit used price penalty
                    exit_used_price_penalty = False
                    
                    # Fallback to mid-price with slippage penalty if bid/ask unavailable
                    # Slippage accounts for execution cost when using mid-price fallback
                    fallback_slippage_cents = 1.5  # Conservative estimate for execution cost
                    if exit_kalshi_bid is None:
                        exit_kalshi_bid = kalshi_price - (fallback_slippage_cents / 100.0)  # Penalty for long exit
                        exit_used_price_penalty = True
                        logger.warning(f"[EXIT] Using fallback bid with {fallback_slippage_cents} cent slippage penalty (mid-price: {kalshi_price:.3f}, adjusted: {exit_kalshi_bid:.3f})")
                    if exit_kalshi_ask is None:
                        exit_kalshi_ask = kalshi_price + (fallback_slippage_cents / 100.0)  # Penalty for short exit
                        exit_used_price_penalty = True
                        logger.warning(f"[EXIT] Using fallback ask with {fallback_slippage_cents} cent slippage penalty (mid-price: {kalshi_price:.3f}, adjusted: {exit_kalshi_ask:.3f})")
                    
                    # Fix 2: Clamp fallback prices to [0,1]
                    exit_kalshi_bid = clamp01(exit_kalshi_bid)
                    exit_kalshi_ask = clamp01(exit_kalshi_ask)
                    
                    # Calculate game phase
                    game_phase = calculate_game_phase(state.entry_timestamp, game_start_timestamp, game_duration_seconds)
                    
                    # Fix 3: Determine if entry used price penalty
                    # Entries only occur when bid/ask is available, so entry_used_price_penalty is False
                    # (We don't use fallback prices for entries - we skip the entry if bid/ask missing)
                    entry_used_price_penalty = False
                    
                    trade = Trade(
                        entry_time=state.entry_timestamp,
                        exit_time=timestamp,
                        position_type=state.open_position,
                        entry_espn_prob=state.entry_espn_prob,
                        entry_kalshi_price=state.entry_kalshi_price,
                        entry_kalshi_bid=state.entry_kalshi_bid,
                        entry_kalshi_ask=state.entry_kalshi_ask,
                        exit_espn_prob=espn_prob,
                        exit_kalshi_price=kalshi_price,
                        exit_kalshi_bid=exit_kalshi_bid,
                        exit_kalshi_ask=exit_kalshi_ask,
                        profit_cents=None,  # Will calculate after (gross profit)
                        net_profit_cents=None,  # Will calculate after (net profit after costs)
                        actual_outcome=actual_outcome,  # For display/logging only, not used in P&L
                        game_phase=game_phase,
                        entry_used_price_penalty=entry_used_price_penalty,
                        exit_used_price_penalty=exit_used_price_penalty
                    )
                    # Calculate P&L with costs
                    pnl_result = calculate_trade_pnl(trade, bet_amount_dollars, slippage_rate, enable_fees)
                    trade.profit_cents = pnl_result["gross_profit"] * 100  # Gross profit in cents
                    trade.net_profit_cents = pnl_result["net_profit"] * 100  # Net profit in cents
                    state.trades.append(trade)
                    successful_exits += 1
                    gross_profit_dollars = trade.profit_cents / 100.0
                    net_profit_dollars = trade.net_profit_cents / 100.0
                    # logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: ✓ EXITED {state.open_position.upper()} - Divergence converged to {abs_divergence_prob*100:.2f} cents, Gross: ${gross_profit_dollars:.2f}, Net: ${net_profit_dollars:.2f}")
                    
                    # Reset state
                    state.open_position = None
                    state.entry_espn_prob = None
                    state.entry_kalshi_price = None
                    state.entry_kalshi_bid = None
                    state.entry_kalshi_ask = None
                    state.entry_timestamp = None
            # else:
            #     logger.debug(f"[SIMULATION] Point {point_idx+1}/{len(aligned_data)}: Position open ({state.open_position}), divergence: {abs_divergence_prob*100:.2f} cents (need <{exit_threshold*100:.1f} to exit)")
        
        # Update previous divergence values for hysteresis and direction confirmation
        state.prev_divergence_prob = divergence_prob
        state.prev_abs_divergence_prob = abs_divergence_prob
    
    # Close any remaining open position at end of game using final market prices
    if state.open_position is not None and aligned_data:
        last_point = aligned_data[-1]
        final_divergence = abs(state.entry_espn_prob - last_point["kalshi_price"])
        
        # Capture final bid/ask prices (use market prices, not binary settlement)
        final_kalshi_bid = last_point.get("kalshi_bid")
        final_kalshi_ask = last_point.get("kalshi_ask")
        
        # Fix 3: Track if exit used price penalty (fallback or forced)
        exit_used_price_penalty = False
        
        # Fallback to mid-price with slippage penalty if bid/ask unavailable
        fallback_slippage_cents = 1.5  # Same as regular exit fallback
        if final_kalshi_bid is None:
            final_kalshi_bid = last_point["kalshi_price"] - (fallback_slippage_cents / 100.0)
            exit_used_price_penalty = True
        if final_kalshi_ask is None:
            final_kalshi_ask = last_point["kalshi_price"] + (fallback_slippage_cents / 100.0)
            exit_used_price_penalty = True
        
        # Apply forced slippage penalty for end-of-game closes (accounts for liquidity collapse)
        # Even if bid/ask available, late-game liquidity collapse makes execution more difficult
        forced_slippage_cents = 2.0  # Conservative estimate for late-game liquidity collapse
        if state.open_position == "long_espn":
            final_kalshi_bid = final_kalshi_bid - (forced_slippage_cents / 100.0)
            exit_used_price_penalty = True  # Always use price penalty for end-of-game
            logger.warning(f"[END_OF_GAME] Forced close LONG with {forced_slippage_cents} cent slippage penalty")
        elif state.open_position == "short_espn":
            final_kalshi_ask = final_kalshi_ask + (forced_slippage_cents / 100.0)
            exit_used_price_penalty = True  # Always use price penalty for end-of-game
            logger.warning(f"[END_OF_GAME] Forced close SHORT with {forced_slippage_cents} cent slippage penalty")
        
        # Fix 2: Clamp forced prices to [0,1]
        final_kalshi_bid = clamp01(final_kalshi_bid)
        final_kalshi_ask = clamp01(final_kalshi_ask)
        
        # Calculate game phase
        game_phase = calculate_game_phase(state.entry_timestamp, game_start_timestamp, game_duration_seconds)
        
        # Fix 3: Entry never uses price penalty (entries require bid/ask to be present)
        entry_used_price_penalty = False
        
        trade = Trade(
            entry_time=state.entry_timestamp,
            exit_time=last_point["timestamp"],
            position_type=state.open_position,
            entry_espn_prob=state.entry_espn_prob,
            entry_kalshi_price=state.entry_kalshi_price,
            entry_kalshi_bid=state.entry_kalshi_bid,
            entry_kalshi_ask=state.entry_kalshi_ask,
            exit_espn_prob=last_point["espn_prob"],
            exit_kalshi_price=last_point["kalshi_price"],
            exit_kalshi_bid=final_kalshi_bid,
            exit_kalshi_ask=final_kalshi_ask,
            profit_cents=None,  # Will calculate after (gross profit)
            net_profit_cents=None,  # Will calculate after (net profit after costs)
            actual_outcome=actual_outcome,  # For display/logging only, not used in P&L
            game_phase=game_phase,
            entry_used_price_penalty=entry_used_price_penalty,
            exit_used_price_penalty=exit_used_price_penalty
        )
        # Calculate P&L with costs
        pnl_result = calculate_trade_pnl(trade, bet_amount_dollars, slippage_rate, enable_fees)
        trade.profit_cents = pnl_result["gross_profit"] * 100  # Gross profit in cents
        trade.net_profit_cents = pnl_result["net_profit"] * 100  # Net profit in cents
        state.trades.append(trade)
        gross_profit_dollars = trade.profit_cents / 100.0
        net_profit_dollars = trade.net_profit_cents / 100.0
        # logger.debug(f"[SIMULATION] End of game: Closed remaining {state.open_position.upper()} position - Final divergence: {final_divergence*100:.2f} cents, Gross: ${gross_profit_dollars:.2f}, Net: ${net_profit_dollars:.2f} (using final market price, not binary settlement)")
    
    # Log summary statistics
    # logger.debug(f"[SIMULATION] Simulation complete - Total trades: {len(state.trades)}")
    if len(state.trades) == 0:
        logger.warning(f"[SIMULATION] ❌ No trades executed - Summary:")
        logger.warning(f"[SIMULATION]   - Entry attempts (LONG): {entry_attempts_long} (failed divergence: {entry_failed_divergence_long}, failed bid/ask: {entry_failed_bid_ask_long})")
        logger.warning(f"[SIMULATION]   - Entry attempts (SHORT): {entry_attempts_short} (failed divergence: {entry_failed_divergence_short}, failed bid/ask: {entry_failed_bid_ask_short})")
        logger.warning(f"[SIMULATION]   - Successful entries: {successful_entries}")
        # if entry_attempts_long == 0 and entry_attempts_short == 0:
        #     logger.warning(f"[SIMULATION]   - Reason: Divergence never exceeds entry threshold ({entry_threshold*100:.1f} cents)")
        # elif entry_failed_bid_ask_long > 0 or entry_failed_bid_ask_short > 0:
        #     logger.warning(f"[SIMULATION]   - Reason: Missing bid/ask data when divergence was sufficient")
        # else:
        #     logger.warning(f"[SIMULATION]   - Reason: Divergence never exceeds entry threshold")
    else:
        logger.debug(f"[SIMULATION] ✓ Successfully executed {len(state.trades)} trades")
        # logger.debug(f"[SIMULATION]   - Entry attempts (LONG): {entry_attempts_long}, (SHORT): {entry_attempts_short}")
        # logger.debug(f"[SIMULATION]   - Successful entries: {successful_entries}, Successful exits: {successful_exits}")
    
    # Calculate summary statistics using net profit (after costs)
    # Note: profit_cents is gross profit, net_profit_cents is net profit after costs
    # IMPORTANT: total_profit is profit/loss (can be negative), NOT total money after.
    # Example: If you spent $20 and got $10 back, profit = -$10 (a loss)
    total_gross_profit_cents = sum(t.profit_cents or 0 for t in state.trades)
    total_net_profit_cents = sum(t.net_profit_cents or 0 for t in state.trades)
    total_profit_dollars = total_net_profit_cents / 100.0  # Use net profit for summary (can be negative)
    num_trades = len(state.trades)
    winning_trades = [t for t in state.trades if (t.net_profit_cents or 0) > 0]  # Use net profit for win rate
    win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0.0
    avg_profit_per_trade_cents = total_net_profit_cents / num_trades if num_trades > 0 else 0.0
    avg_profit_per_trade_dollars = avg_profit_per_trade_cents / 100.0
    
    return {
        "total_profit_cents": total_net_profit_cents,  # Net profit after costs (for aggregation)
        "total_profit_dollars": total_net_profit_cents / 100.0,  # Net profit after costs
        "total_gross_profit_cents": total_gross_profit_cents,  # Gross profit before costs (for reference)
        "total_gross_profit_dollars": total_gross_profit_cents / 100.0,  # Gross profit before costs
        "num_trades": num_trades,
        "win_rate": win_rate,  # Based on net profit
        "avg_profit_per_trade_cents": avg_profit_per_trade_cents,  # Net profit per trade
        "avg_profit_per_trade_dollars": avg_profit_per_trade_dollars,  # Net profit per trade
        "bet_amount_dollars": bet_amount_dollars,
        "trades": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "position_type": t.position_type,
                "entry_espn_prob": t.entry_espn_prob,
                "entry_kalshi_price": t.entry_kalshi_price,
                "entry_kalshi_bid": t.entry_kalshi_bid,
                "entry_kalshi_ask": t.entry_kalshi_ask,
                "exit_espn_prob": t.exit_espn_prob,
                "exit_kalshi_price": t.exit_kalshi_price,
                "exit_kalshi_bid": t.exit_kalshi_bid,
                "exit_kalshi_ask": t.exit_kalshi_ask,
                "profit_cents": t.profit_cents,  # Gross profit
                "profit_dollars": (t.profit_cents or 0) / 100.0,  # Gross profit
                "net_profit_cents": t.net_profit_cents,  # Net profit after costs
                "net_profit_dollars": (t.net_profit_cents or 0) / 100.0,  # Net profit after costs
                "actual_outcome": t.actual_outcome,  # For display/logging only
                "game_phase": t.game_phase,  # Q1, Q2-Q3, or Q4 for stratification
            }
            for t in state.trades
        ]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Simulate trading strategy based on ESPN-Kalshi divergence"
    )
    parser.add_argument(
        "--game-id",
        required=True,
        help="ESPN game ID (e.g., 0022400196)"
    )
    parser.add_argument(
        "--entry-threshold",
        type=float,
        default=0.05,
        help="Divergence threshold to enter position (default: 0.05 = 5 cents)"
    )
    parser.add_argument(
        "--exit-threshold",
        type=float,
        default=0.01,
        help="Divergence threshold to exit position (default: 0.01 = 1 cent)"
    )
    parser.add_argument(
        "--exclude-first-seconds",
        type=int,
        default=0,
        help="Exclude first N seconds of game (default: 0)"
    )
    parser.add_argument(
        "--exclude-last-seconds",
        type=int,
        default=0,
        help="Exclude last N seconds of game (default: 0)"
    )
    parser.add_argument(
        "--bet-amount",
        type=float,
        default=1.0,
        help="Bet amount in dollars per trade (default: 1.0)"
    )
    parser.add_argument(
        "--enable-fees",
        action="store_true",
        help="Enable Kalshi trading fees (7% formula). Default: False (fees disabled)."
    )
    parser.add_argument(
        "--slippage-rate",
        type=float,
        default=0.0,
        help="Slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled)."
    )
    parser.add_argument(
        "--min-hold-seconds",
        type=int,
        default=30,
        help="Minimum holding period in seconds before allowing exit (default: 30). Prevents noise trading."
    )
    parser.add_argument(
        "--output",
        help="Output JSON file path (optional)"
    )
    parser.add_argument(
        "--dsn",
        help="Database connection string (or use DATABASE_URL env var)"
    )
    
    args = parser.parse_args()
    
    # Connect to database
    dsn = get_dsn(args.dsn)
    with connect(dsn) as conn:
        print(f"Running simulation for game {args.game_id}...", file=sys.stderr)
        print(f"  Entry threshold: {args.entry_threshold:.3f} ({args.entry_threshold*100:.1f} cents)", file=sys.stderr)
        print(f"  Exit threshold: {args.exit_threshold:.3f} ({args.exit_threshold*100:.1f} cents)", file=sys.stderr)
        print(f"  Bet amount: ${args.bet_amount:.2f}", file=sys.stderr)
        if args.enable_fees:
            print(f"  Fees: ENABLED (7% formula)", file=sys.stderr)
        if args.slippage_rate > 0:
            print(f"  Slippage rate: {args.slippage_rate*100:.2f}%", file=sys.stderr)
        if args.min_hold_seconds > 0:
            print(f"  Min hold period: {args.min_hold_seconds}s", file=sys.stderr)
        if args.exclude_first_seconds > 0 or args.exclude_last_seconds > 0:
            print(f"  Excluding first {args.exclude_first_seconds}s and last {args.exclude_last_seconds}s", file=sys.stderr)
        
        # Get aligned data
        aligned_data, game_start, duration, actual_outcome = get_aligned_data(
            conn,
            args.game_id,
            exclude_first_seconds=args.exclude_first_seconds,
            exclude_last_seconds=args.exclude_last_seconds
        )
        
        if not aligned_data:
            print(f"Error: No aligned data found for game {args.game_id}", file=sys.stderr)
            return 1
        
        print(f"  Found {len(aligned_data)} aligned data points", file=sys.stderr)
        
        # Run simulation
        results = simulate_trading_strategy(
            aligned_data,
            args.entry_threshold,
            args.exit_threshold,
            actual_outcome,
            bet_amount_dollars=args.bet_amount,
            slippage_rate=args.slippage_rate,
            min_hold_seconds=args.min_hold_seconds,
            game_start_timestamp=game_start,
            game_duration_seconds=duration,
            enable_fees=args.enable_fees
        )
        
        # Add metadata
        results["game_id"] = args.game_id
        results["entry_threshold"] = args.entry_threshold
        results["exit_threshold"] = args.exit_threshold
        results["exclude_first_seconds"] = args.exclude_first_seconds
        results["exclude_last_seconds"] = args.exclude_last_seconds
        results["num_data_points"] = len(aligned_data)
        results["actual_outcome"] = "home_won" if actual_outcome == 1 else "away_won" if actual_outcome == 0 else "unknown"
        
        # Print results
        print("\n=== Simulation Results ===", file=sys.stderr)
        print(f"Total Profit: ${results['total_profit_dollars']:.2f} ({results['total_profit_cents']:.1f} cents)", file=sys.stderr)
        print(f"Number of Trades: {results['num_trades']}", file=sys.stderr)
        print(f"Win Rate: {results['win_rate']:.1%}", file=sys.stderr)
        print(f"Average Profit per Trade: ${results['avg_profit_per_trade_dollars']:.2f}", file=sys.stderr)
        print(f"Actual Outcome: {results['actual_outcome']}", file=sys.stderr)
        
        if results['num_trades'] > 0:
            print("\n=== Trade Details ===", file=sys.stderr)
            costs_enabled = args.enable_fees or args.slippage_rate > 0
            for i, trade in enumerate(results['trades'], 1):
                if costs_enabled:
                    # Fix 5: Show both gross and net when costs are enabled
                    print(f"  Trade {i}: {trade['position_type']} | "
                          f"Gross: ${trade['profit_dollars']:.2f} | "
                          f"Net: ${trade.get('net_profit_dollars', trade['profit_dollars']):.2f} | "
                          f"Entry ESPN: {trade['entry_espn_prob']:.3f} | "
                          f"Entry Kalshi: {trade['entry_kalshi_price']:.3f}", file=sys.stderr)
                else:
                    print(f"  Trade {i}: {trade['position_type']} | "
                          f"Profit: ${trade['profit_dollars']:.2f} | "
                          f"Entry ESPN: {trade['entry_espn_prob']:.3f} | "
                          f"Entry Kalshi: {trade['entry_kalshi_price']:.3f}", file=sys.stderr)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}", file=sys.stderr)
        else:
            # Print JSON to stdout for piping
            print(json.dumps(results, indent=2))
        
        return 0


if __name__ == "__main__":
    sys.exit(main())

