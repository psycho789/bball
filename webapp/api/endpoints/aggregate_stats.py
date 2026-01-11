"""
Aggregate statistics endpoint - calculate data science metrics across all matched ESPN/Kalshi games.

Design Pattern: Batch Processing Pattern
Algorithm: Aggregate statistical calculations across multiple games
Big O: O(n*m) where n = number of games, m = average data points per game

OPTIMIZATION: Batch queries instead of N+1 queries for 10-100x speedup
"""

from typing import Any, Optional
from fastapi import APIRouter
import math
import time
from datetime import timedelta
from collections import defaultdict

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger
from .stats import (
    calculate_brier_score,
    calculate_log_loss,
    calculate_probability_volatility,
    calculate_standard_deviation,
    calculate_variance,
    calculate_mean_absolute_deviation,
    calculate_coefficient_of_variation,
    calculate_espn_kalshi_divergence,
    calculate_reliability_curve,
    calculate_decision_weighted_metrics,
    calculate_extreme_probability_rate,
    calculate_phase_brier_scores,
    calculate_profit_proxy,
)
from .utils import get_cache_ttl_for_game

router = APIRouter()
logger = get_logger(__name__)


@router.get("/stats/aggregate")
@cached(ttl_seconds=86400)  # Cache for 24 hours (once a day)
def get_aggregate_stats(
    season: str = "2025-26",
) -> dict[str, Any]:
    """
    Calculate aggregate statistics across all games with both ESPN and Kalshi data.
    
    OPTIMIZED VERSION: Uses batch queries instead of per-game queries for 10-100x speedup.
    
    Uses the same game matching logic as the probabilities endpoint:
    - Matches games by espn_event_id in kalshi.markets
    - Uses event_date as game start time
    - Filters Kalshi data to match ESPN recording duration
    - Aligns data by wall-clock time
    
    Returns aggregate metrics useful for data science analysis:
    - Calibration metrics (average Brier score, log loss)
    - Probability distribution metrics
    - ESPN vs Kalshi comparison metrics
    - Correlation and divergence statistics
    
    NOTE: This function is cached for 24 hours. If called during preload and cache exists,
    it will return immediately from cache without recalculating.
    """
    # Log at function entry - this will execute when function is called (cache miss or background refresh)
    logger.info(f"[AGGREGATE_STATS] get_aggregate_stats FUNCTION BODY executing for season={season}")
    
    with get_db_connection() as conn:
        logger.info("[AGGREGATE_STATS] Database connection established for aggregate stats")
        
        # Step 1: Get all games with both ESPN and Kalshi data
        logger.info("[AGGREGATE_STATS] Step 1: Querying games with both ESPN and Kalshi data...")
        games_sql = """
        WITH game_outcomes AS (
            SELECT 
                e.game_id,
                MAX(e.home_score) as final_home_score,
                MAX(e.away_score) as final_away_score,
                MAX(e.final_winning_team) as winner
            FROM espn.prob_event_state e
            GROUP BY e.game_id
        )
        SELECT DISTINCT
            sg.event_id as game_id,
            sg.event_date,
            sg.home_team_abbrev,
            sg.away_team_abbrev,
            sg.home_team_display_name,
            sg.away_team_display_name,
            o.final_home_score,
            o.final_away_score,
            o.winner
        FROM espn.scoreboard_games sg
        JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
        JOIN game_outcomes o ON sg.event_id = o.game_id
        JOIN kalshi.markets km ON sg.event_id = km.espn_event_id
        WHERE km.espn_event_id IS NOT NULL
          AND sg.event_date IS NOT NULL
          AND o.final_home_score IS NOT NULL
        ORDER BY sg.event_date DESC
        """
        logger.debug("Executing games query for aggregate stats")
        game_rows = conn.execute(games_sql).fetchall()
        logger.info(f"Step 1 complete: Found {len(game_rows)} games with both ESPN and Kalshi data")
        
        if not game_rows:
            logger.warning("No games with both ESPN and Kalshi data found")
            return {
                "total_games": 0,
                "message": "No games with both ESPN and Kalshi data found",
            }
        
        # Extract game IDs and build game info map
        game_ids = [str(row[0]) for row in game_rows]
        game_info = {}
        for row in game_rows:
            game_id = str(row[0])
            game_info[game_id] = {
                "event_date": row[1],
                "home_team_abbrev": row[3],
                "away_team_abbrev": row[4],
                "final_home_score": row[6],
                "final_away_score": row[7],
                "winner": row[8],
                "home_won": row[8] == 0 if row[8] is not None else (row[6] > row[7] if row[6] and row[7] else None),
            }
        
        logger.info(f"Step 2: Batch fetching ESPN probability data for {len(game_ids)} games...")
        start_time = time.time()
        
        # Step 2: Batch fetch ALL ESPN probability data in one query
        espn_batch_sql = """
        SELECT 
            p.game_id,
            p.last_modified_utc,
            p.home_win_percentage,
            p.away_win_percentage
        FROM espn.probabilities_raw_items p
        WHERE p.game_id = ANY(%s)
        AND p.season_label = '2025-26'
        ORDER BY p.game_id, p.last_modified_utc ASC
        """
        logger.debug(f"Executing batch ESPN query for {len(game_ids)} games")
        espn_batch_rows = conn.execute(espn_batch_sql, (game_ids,)).fetchall()
        logger.info(f"Step 2 complete: Fetched {len(espn_batch_rows)} ESPN probability rows in {time.time() - start_time:.2f}s")
        
        # Group ESPN data by game_id
        espn_by_game: dict[str, list[tuple]] = defaultdict(list)
        for row in espn_batch_rows:
            game_id = str(row[0])
            espn_by_game[game_id].append((row[1], row[2], row[3]))  # (last_modified_utc, home_win_percentage, away_win_percentage)
        
        logger.debug(f"ESPN data grouped into {len(espn_by_game)} games")
        
        # Step 3: Batch fetch game durations (needed for Kalshi filtering)
        logger.info("Step 3: Batch fetching game durations for Kalshi filtering...")
        duration_sql = """
        SELECT 
            sg.event_id,
            sg.event_date as game_start,
            EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as espn_duration_seconds
        FROM espn.scoreboard_games sg
        JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
        WHERE sg.event_id = ANY(%s)
        GROUP BY sg.event_id, sg.event_date
        """
        duration_rows = conn.execute(duration_sql, (game_ids,)).fetchall()
        game_durations = {str(row[0]): (row[1], row[2]) for row in duration_rows}  # game_id -> (game_start, duration_seconds)
        logger.info(f"Step 3 complete: Fetched durations for {len(game_durations)} games")
        
        # Step 4: Batch fetch Kalshi markets for all games
        logger.info("Step 4: Batch fetching Kalshi markets...")
        markets_sql = """
        SELECT DISTINCT ON (kmw.ticker)
            kmw.espn_event_id,
            kmw.ticker,
            kmw.kalshi_team_side
        FROM kalshi.markets_with_games kmw
        WHERE kmw.espn_event_id = ANY(%s)
          AND kmw.kalshi_team_side IS NOT NULL
        ORDER BY kmw.ticker, kmw.snapshot_id DESC
        """
        markets_rows = conn.execute(markets_sql, (game_ids,)).fetchall()
        
        # Group markets by game_id and ticker
        markets_by_game: dict[str, list[dict]] = defaultdict(list)
        all_tickers = set()
        for row in markets_rows:
            game_id = str(row[0])
            ticker = row[1]
            team_side = row[2]
            markets_by_game[game_id].append({"ticker": ticker, "team_side": team_side})
            all_tickers.add(ticker)
        
        logger.info(f"Step 4 complete: Found {len(markets_by_game)} games with {len(all_tickers)} unique tickers")
        
        # Step 5: Batch fetch Kalshi candlesticks (filtering in Python is acceptable for now)
        # Note: SQL-level filtering would require complex JOINs with game windows
        # The current approach batches the fetch and filters in Python, which is still much faster than N+1
        logger.info(f"Step 5: Batch fetching Kalshi candlesticks for {len(all_tickers)} tickers...")
        kalshi_start = time.time()
        
        kalshi_by_game: dict[str, list[tuple]] = defaultdict(list)
        
        # Fetch candlesticks for all tickers at once, then filter by game window in Python
        # This is still much faster than the original N+1 approach
        if all_tickers:
            ticker_list = list(all_tickers)
            candlesticks_sql = """
            SELECT 
                c.ticker,
                c.period_ts,
                c.price_close,
                c.yes_bid_close,
                c.yes_ask_close
            FROM kalshi.candlesticks c
            WHERE c.ticker = ANY(%s)
              AND (
                  c.price_close IS NOT NULL 
                  OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL)
              )
            ORDER BY c.ticker, c.period_ts
            """
            logger.debug(f"Executing batch Kalshi candlesticks query for {len(ticker_list)} tickers")
            candlesticks_rows = conn.execute(candlesticks_sql, (ticker_list,)).fetchall()
            logger.info(f"Fetched {len(candlesticks_rows)} candlestick rows in {time.time() - kalshi_start:.2f}s")
            
            # Group candlesticks by ticker
            candlesticks_by_ticker: dict[str, list[tuple]] = defaultdict(list)
            for row in candlesticks_rows:
                ticker = row[0]
                candlesticks_by_ticker[ticker].append((row[1], row[2], row[3], row[4]))  # (period_ts, price_close, yes_bid_close, yes_ask_close)
            
            # Now assign candlesticks to games based on markets and filter by game window
            logger.debug("Filtering candlesticks by game time windows...")
            for game_id in game_ids:
                if game_id not in markets_by_game or game_id not in game_durations:
                    continue
                
                game_start, duration_seconds = game_durations[game_id]
                if game_start and duration_seconds:
                    game_end = game_start + timedelta(seconds=duration_seconds)
                    
                    for market in markets_by_game[game_id]:
                        ticker = market["ticker"]
                        if ticker not in candlesticks_by_ticker:
                            continue
                        
                        for candle in candlesticks_by_ticker[ticker]:
                            period_ts = candle[0]
                            if period_ts and game_start <= period_ts <= game_end:
                                kalshi_by_game[game_id].append((
                                    market["team_side"],
                                    period_ts,
                                    candle[1],  # price_close
                                    candle[2],  # yes_bid_close
                                    candle[3],  # yes_ask_close
                                ))
        
        logger.info(f"Step 5 complete: Processed Kalshi data for {len(kalshi_by_game)} games")
        
        # Step 6: Process all games and calculate statistics
        logger.info(f"Step 6: Processing {len(game_rows)} games and calculating statistics...")
        process_start = time.time()
        
        all_espn_brier_scores = []
        all_espn_log_losses = []
        all_espn_volatilities = []
        all_espn_std_devs = []
        all_espn_mads = []
        all_espn_lead_changes = []
        
        all_kalshi_volatilities = []
        all_kalshi_std_devs = []
        all_kalshi_mads = []
        all_kalshi_lead_changes = []
        all_kalshi_brier_scores = []  # For Kalshi calibration metrics
        all_kalshi_probs_for_reliability = []  # Collect all probabilities for aggregate reliability curve
        all_kalshi_outcomes_for_reliability = []  # Collect all outcomes for aggregate reliability curve
        
        # Story 3.1: ESPN reliability curve data
        all_espn_probs_for_reliability = []  # Collect all ESPN probabilities for aggregate reliability curve
        all_espn_outcomes_for_reliability = []  # Collect all ESPN outcomes for aggregate reliability curve
        
        # Story 2.4: Extreme probability rates
        all_espn_extreme_rates = []
        all_kalshi_extreme_rates = []
        
        # Story 3.2: Phase-based Brier scores
        all_espn_phase_briers = {"early": [], "mid": [], "late": [], "clutch": []}
        all_kalshi_phase_briers = {"early": [], "mid": [], "late": [], "clutch": []}
        
        # Story 4.1: Decision-weighted metrics
        all_time_weighted_briers_espn = []
        all_time_weighted_briers_kalshi = []
        all_confidence_weighted_briers_espn = []
        all_confidence_weighted_briers_kalshi = []
        all_distance_weighted_mads = []
        all_ev_positive_disagreements = []
        
        # Story 4.2: Profit proxy metrics
        all_profit_proxy_signal_counts = []
        all_profit_proxy_win_rates_positive = []
        all_profit_proxy_win_rates_negative = []
        
        all_correlations = []
        all_maes = []
        all_max_errors = []
        all_sign_flips = []  # Count of sign flips per game
        all_points_per_game = []  # Track aligned points per game for Story 2.1
        total_aligned_points = 0
        
        # Story 3.4: Disagreement vs Outcome pairs
        disagreement_outcome_pairs = []  # List of (disagreement, outcome) tuples
        
        # Store final margins for scatter plot coloring
        volatility_margins = []  # Parallel array to track margins for each volatility pair
        
        games_processed = 0
        games_with_stats = 0
        
        for idx, row in enumerate(game_rows, 1):
            game_start_time = time.time()
            if idx % 10 == 0 or idx == 1:
                elapsed = time.time() - process_start
                logger.info(f"Progress: Processing game {idx}/{len(game_rows)} (elapsed: {elapsed:.1f}s, avg: {elapsed/idx:.2f}s/game)")
            
            game_id = str(row[0])
            info = game_info[game_id]
            event_date = info["event_date"]
            home_won = info["home_won"]
            
            try:
                # Get ESPN data for this game (already fetched)
                espn_rows = espn_by_game.get(game_id, [])
                
                if not espn_rows:
                    logger.debug(f"Game {idx}: Skipping - no ESPN probability data")
                    continue
                
                # Process ESPN data (same logic as before)
                logger.debug(f"Game {idx}: Processing {len(espn_rows)} ESPN rows...")
                espn_home_probs = []
                espn_times = []
                first_espn_timestamp = None
                game_start_timestamp = int(event_date.timestamp()) if event_date else None
                
                for last_modified_utc, home_win_percentage, away_win_percentage in espn_rows:
                    if last_modified_utc is None:
                        continue
                    
                    espn_recording_timestamp = int(last_modified_utc.timestamp())
                    if first_espn_timestamp is None:
                        first_espn_timestamp = espn_recording_timestamp
                    
                    # Align to game timeline
                    if game_start_timestamp is not None and first_espn_timestamp is not None:
                        elapsed_from_first = espn_recording_timestamp - first_espn_timestamp
                        aligned_timestamp = game_start_timestamp + elapsed_from_first
                    else:
                        aligned_timestamp = espn_recording_timestamp
                    
                    if home_win_percentage is not None:
                        espn_home_probs.append(float(home_win_percentage))
                        espn_times.append(aligned_timestamp)
                
                if not espn_home_probs:
                    logger.debug(f"Game {idx}: Skipping - no valid ESPN probability points after processing")
                    continue
                
                # Get Kalshi data for this game (already fetched)
                kalshi_rows = kalshi_by_game.get(game_id, [])
                
                # Process Kalshi data - extract home team probabilities and track bid/ask existence
                logger.debug(f"Game {idx}: Processing {len(kalshi_rows)} Kalshi candlestick rows...")
                kalshi_home_probs = []
                kalshi_times = []
                kalshi_bid_ask_exists = []  # Story 4.1: Track if bid/ask data exists
                all_kalshi_points: dict[int, tuple[float, bool]] = {}  # (prob, has_bid_ask)
                
                for team_side, period_ts, price_close, yes_bid_close, yes_ask_close in kalshi_rows:
                    if period_ts is None:
                        continue
                    unix_timestamp = int(period_ts.timestamp())
                    has_bid_ask = yes_bid_close is not None and yes_ask_close is not None
                    
                    # Use same price logic as probabilities endpoint
                    display_price = None
                    if price_close is not None:
                        display_price = float(price_close)
                    elif yes_bid_close is not None and yes_ask_close is not None:
                        display_price = (yes_bid_close + yes_ask_close) / 2.0
                    
                    if display_price is not None:
                        prob = display_price / 100.0  # Convert from cents to probability
                        
                        if team_side == 'home':
                            if unix_timestamp not in all_kalshi_points:
                                all_kalshi_points[unix_timestamp] = (prob, has_bid_ask)
                        elif team_side == 'away':
                            if unix_timestamp not in all_kalshi_points:
                                all_kalshi_points[unix_timestamp] = (1.0 - prob, has_bid_ask)
                
                sorted_timestamps = sorted(all_kalshi_points.keys())
                for timestamp in sorted_timestamps:
                    prob, has_bid_ask = all_kalshi_points[timestamp]
                    kalshi_times.append(timestamp)
                    kalshi_home_probs.append(prob)
                    kalshi_bid_ask_exists.append(has_bid_ask)
                
                logger.debug(f"Game {idx}: Processed {len(kalshi_home_probs)} Kalshi probability points")
                
                if not espn_home_probs:
                    logger.debug(f"Game {idx}: Skipping stats calculation - no ESPN data")
                    continue
                
                games_processed += 1
                logger.debug(f"Game {idx}: Calculating statistics...")
                
                # Calculate ESPN stats
                espn_volatility = calculate_probability_volatility(espn_home_probs)
                espn_std_dev = calculate_standard_deviation(espn_home_probs)
                espn_mad = calculate_mean_absolute_deviation(espn_home_probs)
                espn_lead_changes = 0
                if len(espn_home_probs) > 1:
                    was_home_favorite = espn_home_probs[0] > 0.5
                    for prob in espn_home_probs[1:]:
                        is_home_favorite = prob > 0.5
                        if is_home_favorite != was_home_favorite:
                            espn_lead_changes += 1
                            was_home_favorite = is_home_favorite
                
                all_espn_volatilities.append(espn_volatility)
                all_espn_std_devs.append(espn_std_dev)
                all_espn_mads.append(espn_mad)
                all_espn_lead_changes.append(espn_lead_changes)
                
                # Story 2.4: Calculate extreme probability rate for ESPN
                espn_extreme_rate = calculate_extreme_probability_rate(espn_home_probs)
                if espn_extreme_rate is not None:
                    all_espn_extreme_rates.append(espn_extreme_rate)
                    logger.debug(f"Game {idx}: ESPN extreme probability rate: {espn_extreme_rate:.4f}")
                
                # Story 3.2: Calculate phase-based Brier scores for ESPN
                if home_won is not None and game_start_timestamp is not None and duration_seconds:
                    espn_phase_briers = calculate_phase_brier_scores(
                        espn_home_probs,
                        espn_times,
                        game_start_timestamp,
                        1 if home_won else 0,
                        duration_seconds
                    )
                    for phase in ["early", "mid", "late", "clutch"]:
                        if espn_phase_briers[phase] is not None:
                            all_espn_phase_briers[phase].append(espn_phase_briers[phase])
                
                # Calculate calibration metrics if we know the outcome
                if home_won is not None:
                    actual_outcome = 1 if home_won else 0
                    brier = calculate_brier_score(espn_home_probs, actual_outcome)
                    log_loss = calculate_log_loss(espn_home_probs, actual_outcome)
                    if brier is not None:
                        all_espn_brier_scores.append(brier)
                    if log_loss is not None:
                        all_espn_log_losses.append(log_loss)
                    
                    # Collect ESPN probabilities and outcomes for aggregate reliability curve
                    all_espn_probs_for_reliability.extend(espn_home_probs)
                    all_espn_outcomes_for_reliability.extend([actual_outcome] * len(espn_home_probs))
                
                # Calculate Kalshi stats if available
                if kalshi_home_probs:
                    kalshi_volatility = calculate_probability_volatility(kalshi_home_probs)
                    kalshi_std_dev = calculate_standard_deviation(kalshi_home_probs)
                    kalshi_mad = calculate_mean_absolute_deviation(kalshi_home_probs)
                    kalshi_lead_changes = 0
                    if len(kalshi_home_probs) > 1:
                        was_home_favorite = kalshi_home_probs[0] > 0.5
                        for prob in kalshi_home_probs[1:]:
                            is_home_favorite = prob > 0.5
                            if is_home_favorite != was_home_favorite:
                                kalshi_lead_changes += 1
                                was_home_favorite = is_home_favorite
                    
                    all_kalshi_volatilities.append(kalshi_volatility)
                    all_kalshi_std_devs.append(kalshi_std_dev)
                    all_kalshi_mads.append(kalshi_mad)
                    all_kalshi_lead_changes.append(kalshi_lead_changes)
                    
                    # Story 2.4: Calculate extreme probability rate for Kalshi
                    kalshi_extreme_rate = calculate_extreme_probability_rate(kalshi_home_probs)
                    if kalshi_extreme_rate is not None:
                        all_kalshi_extreme_rates.append(kalshi_extreme_rate)
                        logger.debug(f"Game {idx}: Kalshi extreme probability rate: {kalshi_extreme_rate:.4f}")
                    
                    # Calculate Kalshi calibration metrics if we know the outcome
                    if home_won is not None:
                        kalshi_brier = calculate_brier_score(kalshi_home_probs, 1 if home_won else 0)
                        if kalshi_brier is not None:
                            all_kalshi_brier_scores.append(kalshi_brier)
                        
                        # Collect probabilities and outcomes for aggregate reliability curve
                        actual_outcome = 1 if home_won else 0
                        all_kalshi_probs_for_reliability.extend(kalshi_home_probs)
                        all_kalshi_outcomes_for_reliability.extend([actual_outcome] * len(kalshi_home_probs))
                        
                        # Story 3.2: Calculate phase-based Brier scores for Kalshi
                        if game_start_timestamp is not None and duration_seconds:
                            kalshi_phase_briers = calculate_phase_brier_scores(
                                kalshi_home_probs,
                                kalshi_times,
                                game_start_timestamp,
                                actual_outcome,
                                duration_seconds
                            )
                            for phase in ["early", "mid", "late", "clutch"]:
                                if kalshi_phase_briers[phase] is not None:
                                    all_kalshi_phase_briers[phase].append(kalshi_phase_briers[phase])
                    
                    # Store final margin for scatter plot coloring
                    final_margin = None
                    if info.get("final_home_score") is not None and info.get("final_away_score") is not None:
                        final_margin = abs(info["final_home_score"] - info["final_away_score"])
                    volatility_margins.append(final_margin)
                    
                    # Calculate divergence
                    divergence = calculate_espn_kalshi_divergence(
                        espn_home_probs, kalshi_home_probs,
                        espn_times, kalshi_times
                    )
                    
                    if divergence["correlation"] is not None:
                        all_correlations.append(divergence["correlation"])
                    if divergence.get("mean_absolute_difference") is not None:
                        all_maes.append(divergence["mean_absolute_difference"])
                    if divergence.get("max_absolute_difference") is not None:
                        all_max_errors.append(divergence["max_absolute_difference"])
                    if divergence.get("sign_flips") is not None:
                        all_sign_flips.append(divergence["sign_flips"])
                    
                    # Story 3.4: Collect disagreement vs outcome pairs
                    if home_won is not None:
                        actual_outcome = 1 if home_won else 0
                        # Create aligned pairs (same logic as divergence calculation)
                        kalshi_idx = 0
                        for i, espn_time in enumerate(espn_times):
                            # Find closest Kalshi timestamp
                            while kalshi_idx < len(kalshi_times) - 1 and abs(kalshi_times[kalshi_idx] - espn_time) > abs(kalshi_times[kalshi_idx + 1] - espn_time):
                                kalshi_idx += 1
                            
                            if kalshi_idx < len(kalshi_times):
                                time_diff = abs(kalshi_times[kalshi_idx] - espn_time)
                                if time_diff <= 60:  # Within 60 seconds
                                    disagreement = espn_home_probs[i] - kalshi_home_probs[kalshi_idx]
                                    disagreement_outcome_pairs.append((disagreement, actual_outcome))
                    
                    # Track aligned points per game for Story 2.1 (Median Points/Game)
                    aligned_points_count = divergence.get("data_points", 0)
                    if aligned_points_count > 0:
                        all_points_per_game.append(aligned_points_count)
                        logger.debug(f"Game {idx}: {aligned_points_count} aligned data points")
                    
                    total_aligned_points += aligned_points_count
                    
                    # Story 4.1: Calculate decision-weighted metrics
                    if home_won is not None and game_start_timestamp is not None and duration_seconds:
                        # Need aligned ESPN and Kalshi probabilities for decision-weighted metrics
                        # Use the same alignment logic as divergence calculation
                        aligned_espn_probs = []
                        aligned_kalshi_probs = []
                        aligned_kalshi_times = []
                        aligned_kalshi_bid_ask = []
                        
                        kalshi_idx = 0
                        for i, espn_time in enumerate(espn_times):
                            # Find closest Kalshi timestamp
                            while kalshi_idx < len(kalshi_times) - 1 and abs(kalshi_times[kalshi_idx] - espn_time) > abs(kalshi_times[kalshi_idx + 1] - espn_time):
                                kalshi_idx += 1
                            
                            if kalshi_idx < len(kalshi_times):
                                time_diff = abs(kalshi_times[kalshi_idx] - espn_time)
                                if time_diff <= 60:  # Within 60 seconds
                                    aligned_espn_probs.append(espn_home_probs[i])
                                    aligned_kalshi_probs.append(kalshi_home_probs[kalshi_idx])
                                    aligned_kalshi_times.append(kalshi_times[kalshi_idx])
                                    aligned_kalshi_bid_ask.append(kalshi_bid_ask_exists[kalshi_idx])
                        
                        if aligned_espn_probs and aligned_kalshi_probs:
                            decision_metrics = calculate_decision_weighted_metrics(
                                aligned_espn_probs,
                                aligned_kalshi_probs,
                                aligned_kalshi_times,
                                aligned_kalshi_bid_ask,
                                actual_outcome,
                                game_start_timestamp,
                                duration_seconds
                            )
                            
                            if decision_metrics.get("time_weighted_brier_espn") is not None:
                                all_time_weighted_briers_espn.append(decision_metrics["time_weighted_brier_espn"])
                            if decision_metrics.get("time_weighted_brier_kalshi") is not None:
                                all_time_weighted_briers_kalshi.append(decision_metrics["time_weighted_brier_kalshi"])
                            if decision_metrics.get("confidence_weighted_brier_espn") is not None:
                                all_confidence_weighted_briers_espn.append(decision_metrics["confidence_weighted_brier_espn"])
                            if decision_metrics.get("confidence_weighted_brier_kalshi") is not None:
                                all_confidence_weighted_briers_kalshi.append(decision_metrics["confidence_weighted_brier_kalshi"])
                            if decision_metrics.get("distance_weighted_mae") is not None:
                                all_distance_weighted_mads.append(decision_metrics["distance_weighted_mae"])
                            if decision_metrics.get("ev_positive_disagreements") and decision_metrics["ev_positive_disagreements"].get("count"):
                                all_ev_positive_disagreements.append(decision_metrics["ev_positive_disagreements"]["count"])
                            
                            # Story 4.2: Calculate profit proxy metrics
                            if aligned_espn_probs and aligned_kalshi_probs:
                                profit_metrics = calculate_profit_proxy(
                                    aligned_espn_probs,
                                    aligned_kalshi_probs,
                                    [actual_outcome] * len(aligned_espn_probs),
                                    threshold=0.05
                                )
                                if profit_metrics.get("signal_event_count") is not None:
                                    all_profit_proxy_signal_counts.append(profit_metrics["signal_event_count"])
                                if profit_metrics.get("win_rate_positive_edge") is not None:
                                    all_profit_proxy_win_rates_positive.append(profit_metrics["win_rate_positive_edge"])
                                if profit_metrics.get("win_rate_negative_edge") is not None:
                                    all_profit_proxy_win_rates_negative.append(profit_metrics["win_rate_negative_edge"])
                
                games_with_stats += 1
                game_elapsed = time.time() - game_start_time
                logger.debug(f"Game {idx}: Completed in {game_elapsed:.2f}s")
                
            except Exception as e:
                logger.warning(f"Game {idx}: Error processing game {game_id}: {e}", exc_info=True)
                continue
        
        total_elapsed = time.time() - process_start
        logger.info(f"Step 6 complete: Processed {games_processed} games, {games_with_stats} with stats "
                    f"(elapsed: {total_elapsed:.1f}s, avg: {total_elapsed/games_processed:.2f}s/game)")
        
        # Step 6.5: Calculate Story 3.4 - Disagreement vs Outcome bins
        logger.info(f"Step 6.5: Calculating disagreement vs outcome bins from {len(disagreement_outcome_pairs)} pairs...")
        disagreement_bins = [
            (-0.30, -0.20), (-0.20, -0.10), (-0.10, -0.05), (-0.05, 0.0),
            (0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.30)
        ]
        binned_disagreement_data = []
        for bin_min, bin_max in disagreement_bins:
            pairs_in_bin = [(d, o) for d, o in disagreement_outcome_pairs if bin_min <= d < bin_max]
            if pairs_in_bin:
                home_win_rate = sum(o for _, o in pairs_in_bin) / len(pairs_in_bin)
                binned_disagreement_data.append({
                    "bin_min": bin_min,
                    "bin_max": bin_max,
                    "bin_center": (bin_min + bin_max) / 2.0,
                    "home_win_rate": home_win_rate,
                    "count": len(pairs_in_bin)
                })
        logger.info(f"Step 6.5 complete: Created {len(binned_disagreement_data)} bins")
        
        # Step 7: Calculate aggregate statistics
        logger.info(f"Step 7: Calculating aggregate statistics from {games_with_stats} games with stats...")
        logger.debug(f"Aggregate data counts - ESPN: brier={len(all_espn_brier_scores)}, "
                    f"log_loss={len(all_espn_log_losses)}, volatility={len(all_espn_volatilities)}, "
                    f"Kalshi: volatility={len(all_kalshi_volatilities)}, "
                    f"divergence: correlation={len(all_correlations)}, mae={len(all_maes)}, "
                    f"max_errors={len(all_max_errors)}, sign_flips={len(all_sign_flips)}, "
                    f"points_per_game={len(all_points_per_game)}, total_aligned_points={total_aligned_points}")
        
        def safe_mean(values: list[float]) -> Optional[float]:
            return sum(values) / len(values) if values else None
        
        def safe_median(values: list[float]) -> Optional[float]:
            if not values:
                return None
            sorted_vals = sorted(values)
            mid = len(sorted_vals) // 2
            if len(sorted_vals) % 2 == 0:
                return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
            return sorted_vals[mid]
        
        def safe_std_dev(values: list[float]) -> Optional[float]:
            if len(values) < 2:
                return None
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            return math.sqrt(variance)
        
        def safe_percentile(values: list[float], percentile: float) -> Optional[float]:
            """Calculate percentile (0-100)"""
            if not values:
                return None
            sorted_vals = sorted(values)
            k = (len(sorted_vals) - 1) * (percentile / 100.0)
            floor = int(k)
            ceil = floor + 1
            if ceil >= len(sorted_vals):
                return sorted_vals[-1]
            weight = k - floor
            return sorted_vals[floor] * (1 - weight) + sorted_vals[ceil] * weight
        
        def safe_skewness(values: list[float]) -> Optional[float]:
            """Calculate skewness (measure of asymmetry)"""
            if len(values) < 3:
                return None
            mean = sum(values) / len(values)
            std_dev = safe_std_dev(values)
            if std_dev == 0:
                return None
            n = len(values)
            skew = (n / ((n - 1) * (n - 2))) * sum(((v - mean) / std_dev) ** 3 for v in values)
            return skew
        
        def safe_kurtosis(values: list[float]) -> Optional[float]:
            """Calculate excess kurtosis (measure of tail heaviness)"""
            if len(values) < 4:
                return None
            mean = sum(values) / len(values)
            std_dev = safe_std_dev(values)
            if std_dev == 0:
                return None
            n = len(values)
            kurt = (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * sum(((v - mean) / std_dev) ** 4 for v in values) - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))
            return kurt
        
        logger.debug("Computing aggregate metrics (mean, median, std_dev, min, max)...")
        result = {
            "total_games": len(game_rows),
            "games_processed": games_processed,
            "games_with_stats": games_with_stats,
            "espn": {
                "time_averaged_in_game_brier_error": {
                    "mean": safe_mean(all_espn_brier_scores),
                    "median": safe_median(all_espn_brier_scores),
                    "std_dev": safe_std_dev(all_espn_brier_scores),
                    "min": min(all_espn_brier_scores) if all_espn_brier_scores else None,
                    "max": max(all_espn_brier_scores) if all_espn_brier_scores else None,
                    "p25": safe_percentile(all_espn_brier_scores, 25),
                    "p75": safe_percentile(all_espn_brier_scores, 75),
                    "p90": safe_percentile(all_espn_brier_scores, 90),
                    "p95": safe_percentile(all_espn_brier_scores, 95),
                    "skewness": safe_skewness(all_espn_brier_scores),
                    "kurtosis": safe_kurtosis(all_espn_brier_scores),
                    "count": len(all_espn_brier_scores),
                    "distribution": sorted(all_espn_brier_scores) if all_espn_brier_scores else [],  # For histogram
                },
                "log_loss": {
                    "mean": safe_mean(all_espn_log_losses),
                    "median": safe_median(all_espn_log_losses),
                    "std_dev": safe_std_dev(all_espn_log_losses),
                    "min": min(all_espn_log_losses) if all_espn_log_losses else None,
                    "max": max(all_espn_log_losses) if all_espn_log_losses else None,
                    "count": len(all_espn_log_losses),
                },
                "volatility": {
                    "mean": safe_mean(all_espn_volatilities),
                    "median": safe_median(all_espn_volatilities),
                    "std_dev": safe_std_dev(all_espn_volatilities),
                    "min": min(all_espn_volatilities) if all_espn_volatilities else None,
                    "max": max(all_espn_volatilities) if all_espn_volatilities else None,
                    "p25": safe_percentile(all_espn_volatilities, 25),
                    "p75": safe_percentile(all_espn_volatilities, 75),
                    "p90": safe_percentile(all_espn_volatilities, 90),
                    "p95": safe_percentile(all_espn_volatilities, 95),
                    "distribution": sorted(all_espn_volatilities) if all_espn_volatilities else [],
                },
                "standard_deviation": {
                    "mean": safe_mean(all_espn_std_devs),
                    "median": safe_median(all_espn_std_devs),
                    "std_dev": safe_std_dev(all_espn_std_devs),
                },
                "mean_absolute_deviation": {
                    "mean": safe_mean(all_espn_mads),
                    "median": safe_median(all_espn_mads),
                },
                "lead_changes": {
                    "mean": safe_mean(all_espn_lead_changes),
                    "median": safe_median(all_espn_lead_changes),
                    "total": sum(all_espn_lead_changes),
                },
                # Story 2.4: Extreme probability rate
                "extreme_probability_rate": safe_mean(all_espn_extreme_rates) if all_espn_extreme_rates else None,
                # Story 3.1: ESPN reliability curve
                "reliability_curve": calculate_reliability_curve(
                    all_espn_probs_for_reliability,
                    all_espn_outcomes_for_reliability,
                    bins=10
                ) if all_espn_probs_for_reliability and all_espn_outcomes_for_reliability else None,
                # Story 3.2: Phase-based Brier scores
                "brier_by_phase": {
                    "espn": {
                        "early": safe_mean(all_espn_phase_briers["early"]) if all_espn_phase_briers["early"] else None,
                        "mid": safe_mean(all_espn_phase_briers["mid"]) if all_espn_phase_briers["mid"] else None,
                        "late": safe_mean(all_espn_phase_briers["late"]) if all_espn_phase_briers["late"] else None,
                        "clutch": safe_mean(all_espn_phase_briers["clutch"]) if all_espn_phase_briers["clutch"] else None,
                    },
                    "kalshi": {
                        "early": safe_mean(all_kalshi_phase_briers["early"]) if all_kalshi_phase_briers["early"] else None,
                        "mid": safe_mean(all_kalshi_phase_briers["mid"]) if all_kalshi_phase_briers["mid"] else None,
                        "late": safe_mean(all_kalshi_phase_briers["late"]) if all_kalshi_phase_briers["late"] else None,
                        "clutch": safe_mean(all_kalshi_phase_briers["clutch"]) if all_kalshi_phase_briers["clutch"] else None,
                    } if any(all_kalshi_phase_briers.values()) else None,
                } if any(all_espn_phase_briers.values()) else None,
            },
                "kalshi": {
                "time_averaged_in_game_brier_error": {
                    "mean": safe_mean(all_kalshi_brier_scores),
                    "median": safe_median(all_kalshi_brier_scores),
                    "std_dev": safe_std_dev(all_kalshi_brier_scores),
                    "min": min(all_kalshi_brier_scores) if all_kalshi_brier_scores else None,
                    "max": max(all_kalshi_brier_scores) if all_kalshi_brier_scores else None,
                    "p25": safe_percentile(all_kalshi_brier_scores, 25),
                    "p75": safe_percentile(all_kalshi_brier_scores, 75),
                    "p90": safe_percentile(all_kalshi_brier_scores, 90),
                    "p95": safe_percentile(all_kalshi_brier_scores, 95),
                    "skewness": safe_skewness(all_kalshi_brier_scores),
                    "kurtosis": safe_kurtosis(all_kalshi_brier_scores),
                    "count": len(all_kalshi_brier_scores),
                    "distribution": sorted(all_kalshi_brier_scores) if all_kalshi_brier_scores else [],
                } if all_kalshi_brier_scores else None,
                "volatility": {
                    "mean": safe_mean(all_kalshi_volatilities),
                    "median": safe_median(all_kalshi_volatilities),
                    "std_dev": safe_std_dev(all_kalshi_volatilities),
                    "p25": safe_percentile(all_kalshi_volatilities, 25),
                    "p75": safe_percentile(all_kalshi_volatilities, 75),
                    "p90": safe_percentile(all_kalshi_volatilities, 90),
                    "p95": safe_percentile(all_kalshi_volatilities, 95),
                    "distribution": sorted(all_kalshi_volatilities) if all_kalshi_volatilities else [],
                } if all_kalshi_volatilities else None,
                "standard_deviation": {
                    "mean": safe_mean(all_kalshi_std_devs),
                    "median": safe_median(all_kalshi_std_devs),
                } if all_kalshi_std_devs else None,
                "mean_absolute_deviation": {
                    "mean": safe_mean(all_kalshi_mads),
                    "median": safe_median(all_kalshi_mads),
                } if all_kalshi_mads else None,
                "lead_changes": {
                    "mean": safe_mean(all_kalshi_lead_changes),
                    "median": safe_median(all_kalshi_lead_changes),
                    "total": sum(all_kalshi_lead_changes),
                } if all_kalshi_lead_changes else None,
                # Story 2.4: Extreme probability rate
                "extreme_probability_rate": safe_mean(all_kalshi_extreme_rates) if all_kalshi_extreme_rates else None,
                "reliability_curve": calculate_reliability_curve(
                    all_kalshi_probs_for_reliability,
                    all_kalshi_outcomes_for_reliability,
                    bins=10
                ) if all_kalshi_probs_for_reliability and all_kalshi_outcomes_for_reliability else None,
            },
            "comparison": {
                "correlation": {
                    "mean": safe_mean(all_correlations),
                    "median": safe_median(all_correlations),
                    "std_dev": safe_std_dev(all_correlations),
                    "min": min(all_correlations) if all_correlations else None,
                    "max": max(all_correlations) if all_correlations else None,
                    "p25": safe_percentile(all_correlations, 25),
                    "p75": safe_percentile(all_correlations, 75),
                    "p90": safe_percentile(all_correlations, 90),
                    "p95": safe_percentile(all_correlations, 95),
                    "skewness": safe_skewness(all_correlations),
                    "kurtosis": safe_kurtosis(all_correlations),
                    "count": len(all_correlations),
                    "distribution": sorted(all_correlations) if all_correlations else [],  # For histogram
                } if all_correlations else None,
                "mean_absolute_difference": {
                    "mean": safe_mean(all_maes),
                    "median": safe_median(all_maes),
                    "std_dev": safe_std_dev(all_maes),
                    "p25": safe_percentile(all_maes, 25),
                    "p75": safe_percentile(all_maes, 75),
                    "p90": safe_percentile(all_maes, 90),
                    "p95": safe_percentile(all_maes, 95),
                    "distribution": sorted(all_maes) if all_maes else [],
                } if all_maes else None,
                "max_absolute_difference": {
                    "mean": safe_mean(all_max_errors),
                    "median": safe_median(all_max_errors),
                    "p75": safe_percentile(all_max_errors, 75),
                    "p90": safe_percentile(all_max_errors, 90),
                    "max": max(all_max_errors) if all_max_errors else None,
                    "distribution": sorted(all_max_errors) if all_max_errors else [],  # For optional histogram
                } if all_max_errors else None,
                "sign_flips": {
                    "total": sum(all_sign_flips) if all_sign_flips else 0,
                    "mean": safe_mean(all_sign_flips),
                    "median": safe_median(all_sign_flips),
                    "p75": safe_percentile(all_sign_flips, 75),
                    "max": max(all_sign_flips) if all_sign_flips else None,
                } if all_sign_flips else None,
                "total_aligned_data_points": total_aligned_points,
                "avg_aligned_points_per_game": total_aligned_points / games_with_stats if games_with_stats > 0 else 0,
                # Story 3.4: Disagreement vs Outcome
                "disagreement_vs_outcome": binned_disagreement_data if binned_disagreement_data else None,
                # Story 4.1: Decision-weighted metrics
                "decision_weighted_brier": {
                    "confidence_weighted": {
                        "espn": safe_mean(all_confidence_weighted_briers_espn) if all_confidence_weighted_briers_espn else None,
                        "kalshi": safe_mean(all_confidence_weighted_briers_kalshi) if all_confidence_weighted_briers_kalshi else None,
                    },
                    "market_actionable": {
                        "espn": safe_mean(all_time_weighted_briers_espn) if all_time_weighted_briers_espn else None,
                        "kalshi": safe_mean(all_time_weighted_briers_kalshi) if all_time_weighted_briers_kalshi else None,
                    },
                } if (all_confidence_weighted_briers_espn or all_time_weighted_briers_espn) else None,
                "distance_weighted_mad": {
                    "mean": safe_mean(all_distance_weighted_mads) if all_distance_weighted_mads else None,
                    "median": safe_median(all_distance_weighted_mads) if all_distance_weighted_mads else None,
                } if all_distance_weighted_mads else None,
                "ev_positive_disagreements": {
                    "total": sum(all_ev_positive_disagreements) if all_ev_positive_disagreements else 0,
                    "mean": safe_mean(all_ev_positive_disagreements) if all_ev_positive_disagreements else None,
                    "median": safe_median(all_ev_positive_disagreements) if all_ev_positive_disagreements else None,
                } if all_ev_positive_disagreements else None,
                # Story 4.2: Profit Proxy (Optional - sanity check only)
                "profit_proxy": {
                    "signal_event_count": sum(all_profit_proxy_signal_counts) if all_profit_proxy_signal_counts else 0,
                    "win_rate_positive_edge": safe_mean(all_profit_proxy_win_rates_positive) if all_profit_proxy_win_rates_positive else None,
                    "win_rate_negative_edge": safe_mean(all_profit_proxy_win_rates_negative) if all_profit_proxy_win_rates_negative else None,
                } if all_profit_proxy_signal_counts else None,
                # Story 2.1: Data Coverage metrics
                # Story 4.3: Alignment rate is calculated from data_points / total_possible_points
                # Alignment window: 60 seconds (see calculate_espn_kalshi_divergence docstring)
                "data_coverage": {
                    "median_points_per_game": safe_median(all_points_per_game),
                    "p25_points_per_game": safe_percentile(all_points_per_game, 25),
                    "p75_points_per_game": safe_percentile(all_points_per_game, 75),
                    "mean_points_per_game": safe_mean(all_points_per_game),
                    "min_points_per_game": min(all_points_per_game) if all_points_per_game else None,
                    "max_points_per_game": max(all_points_per_game) if all_points_per_game else None,
                    # Story 4.3: Alignment rate documentation
                    # Alignment window: 60 seconds (1 minute)
                    # This represents the percentage of ESPN points that successfully matched a Kalshi point
                    # within the 60-second window. Typical rates: 80-95% for games with good data coverage.
                } if all_points_per_game else None,
                # For scatter plots and correlation analysis
                "espn_volatility_vs_kalshi_volatility": [
                    {"espn": v, "kalshi": k, "final_margin": m} 
                    for v, k, m in zip(
                        all_espn_volatilities[:len(all_kalshi_volatilities)], 
                        all_kalshi_volatilities,
                        volatility_margins[:len(all_kalshi_volatilities)]
                    )
                ] if all_kalshi_volatilities else [],
            },
        }
        
        logger.info(f"Step 7 complete: Aggregate statistics calculated")
        logger.info(f"get_aggregate_stats returning aggregate stats: "
                    f"total_games={result['total_games']}, "
                    f"games_processed={result['games_processed']}, "
                    f"games_with_stats={result['games_with_stats']}, "
                    f"espn_brier_count={len(all_espn_brier_scores)}, "
                    f"kalshi_volatility_count={len(all_kalshi_volatilities)}, "
                    f"correlation_count={len(all_correlations)}")
        return result
