"""
Trading simulation endpoint - simulate trading strategy based on ESPN-Kalshi divergence.

Design Pattern: Service Pattern for simulation calculations
Algorithm: Divergence Threshold Trading Simulation
Big O: O(n) where n = aligned data points per game
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
import sys
import os
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import hashlib
import json
import copy
import asyncio

# Import simulation logic from scripts directory
script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/trade/simulate_trading_strategy.py')
spec = importlib.util.spec_from_file_location("simulate_trading_strategy", script_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load simulation module from {script_path}. Check file exists and is readable.")
simulate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulate_module)

from ..db import get_db_connection
from ..logging_config import get_logger
from ..cache import SimpleCache
from . import games

# Import functions from the module
get_aligned_data = simulate_module.get_aligned_data
simulate_trading_strategy = simulate_module.simulate_trading_strategy

router = APIRouter()
logger = get_logger(__name__)

# In-memory progress tracking (simple approach for now)
# In production, consider using Redis or a proper cache
_simulation_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()  # Thread-safe progress updates

# Cache for simulation results (per-game, per-parameters)
# TTL: 1 year for completed games (deterministic), 5 minutes for in-progress
_simulation_cache = SimpleCache(ttl_seconds=86400 * 365, cache_file="simulation_results.cache")
_simulation_cache_lock = threading.Lock()  # Thread-safe cache access


@router.get("/api/games/{game_id}/simulation")
def get_simulation_results(
    game_id: str,
    entry_threshold: float = Query(0.05, description="Divergence threshold to enter position (default: 0.05 = 5 cents)"),
    exit_threshold: float = Query(0.01, description="Divergence threshold to exit position (default: 0.01 = 1 cent)"),
    exclude_first_seconds: int = Query(0, description="Exclude first N seconds of game (default: 0)"),
    exclude_last_seconds: int = Query(0, description="Exclude last N seconds of game (default: 0)"),
    bet_amount: float = Query(20.0, description="Bet amount in dollars per trade (default: 20.0)"),
    slippage_rate: float = Query(0.0, description="Optional slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled). This is a conservative assumption, not a precise model."),
    min_hold_seconds: int = Query(30, description="Minimum holding period in seconds before allowing exit (default: 30). Prevents noise trading."),
    use_trade_data: bool = Query(False, description="DEPRECATED: Ignored. Canonical dataset uses candlestick data."),
    enable_fees: bool = Query(False, description="Enable Kalshi trading fees (7% formula). Default: False (fees disabled)."),
) -> dict[str, Any]:
    """
    Simulate trading strategy for a specific game.
    
    Strategy:
    - Long ESPN: Buy when ESPN probability > Kalshi price + entry_threshold
    - Short ESPN: Sell when ESPN probability < Kalshi price - entry_threshold
    - Exit: Close position when divergence converges to < exit_threshold
    
    Returns simulation results including:
    - Total profit/loss
    - Number of trades
    - Win rate
    - Individual trade details
    """
    import time
    endpoint_start = time.time()
    try:
        with get_db_connection() as conn:
            # Get aligned data
            align_start = time.time()
            aligned_data, game_start, duration, actual_outcome = get_aligned_data(
                conn,
                game_id,
                exclude_first_seconds=exclude_first_seconds,
                exclude_last_seconds=exclude_last_seconds
            )
            align_elapsed = time.time() - align_start
            logger.info(f"[TIMING] get_simulation_results({game_id}) - get_aligned_data: {align_elapsed:.3f}s")
            
            if not aligned_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"No aligned data found for game {game_id}. Make sure the game has both ESPN and Kalshi data."
                )
            
            # Run simulation
            sim_start = time.time()
            results = simulate_trading_strategy(
                aligned_data,
                entry_threshold,
                exit_threshold,
                actual_outcome,
                bet_amount_dollars=bet_amount,
                slippage_rate=slippage_rate,
                min_hold_seconds=min_hold_seconds,
                game_start_timestamp=game_start,
                game_duration_seconds=duration,
                enable_fees=enable_fees
            )
            sim_elapsed = time.time() - sim_start
            logger.info(f"[TIMING] get_simulation_results({game_id}) - simulate_trading_strategy: {sim_elapsed:.3f}s")
            
            # Add metadata
            results["game_id"] = game_id
            results["entry_threshold"] = entry_threshold
            results["exit_threshold"] = exit_threshold
            results["exclude_first_seconds"] = exclude_first_seconds
            results["exclude_last_seconds"] = exclude_last_seconds
            results["num_data_points"] = len(aligned_data)
            results["data_source"] = "official-candlesticks"
            results["actual_outcome"] = "home_won" if actual_outcome == 1 else "away_won" if actual_outcome == 0 else "unknown"
            
            total_elapsed = time.time() - endpoint_start
            logger.info(f"[TIMING] get_simulation_results({game_id}) - TOTAL: {total_elapsed:.3f}s (align={align_elapsed:.3f}s, sim={sim_elapsed:.3f}s)")
            
            return results
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error running simulation for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error running simulation: {str(e)}")


@router.get("/api/simulation/bulk")
def get_bulk_simulation_results(
    num_games: int = Query(..., ge=1, le=500, description="Number of most recent games to simulate"),
    entry_threshold: float = Query(0.05, description="Divergence threshold to enter position (default: 0.05 = 5 cents)"),
    exit_threshold: float = Query(0.01, description="Divergence threshold to exit position (default: 0.01 = 1 cent)"),
    exclude_first_seconds: int = Query(0, description="Exclude first N seconds of game (default: 0)"),
    exclude_last_seconds: int = Query(0, description="Exclude last N seconds of game (default: 0)"),
    bet_amount: float = Query(20.0, description="Bet amount in dollars per trade (default: 20.0)"),
    slippage_rate: float = Query(0.0, description="Optional slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled). This is a conservative assumption, not a precise model."),
    min_hold_seconds: int = Query(30, description="Minimum holding period in seconds before allowing exit (default: 30). Prevents noise trading."),
    use_trade_data: bool = Query(False, description="DEPRECATED: Ignored. Canonical dataset uses candlestick data."),
    enable_fees: bool = Query(False, description="Enable Kalshi trading fees (7% formula). Default: False (fees disabled)."),
    request_id: Optional[str] = Query(None, description="Request ID for progress tracking"),
) -> dict[str, Any]:
    """
    Simulate trading strategy across multiple games.
    
    Runs simulation against the last N games (ordered by date, most recent first)
    that have both ESPN and Kalshi data. Aggregates results across all games.
    
    Strategy:
    - Long ESPN: Buy when ESPN probability > Kalshi price + entry_threshold
    - Short ESPN: Sell when ESPN probability < Kalshi price - entry_threshold
    - Exit: Close position when divergence converges to < exit_threshold
    
    Returns aggregated simulation results including:
    - Total profit/loss across all games
    - Total number of trades
    - Win rate across all trades
    - Individual game results
    - Trade details from all games
    
    Design Pattern: Map-Reduce Pattern for bulk simulation
    Algorithm: Divergence Threshold Trading Simulation applied to multiple games
    Big O: O(n * m) where n = number of games, m = average aligned data points per game
    """
    try:
        logger.info(f"Starting bulk simulation: num_games={num_games}, entry_threshold={entry_threshold}, "
                   f"exit_threshold={exit_threshold}, bet_amount={bet_amount}")
        
        # Get last N games with both ESPN and Kalshi data using the games endpoint logic
        # This ensures consistency with how games are filtered and sorted elsewhere
        # Note: has_kalshi=True filters for games with both market records AND candlestick data
        # IMPORTANT: Clear cache before fetching to ensure we get fresh data with the updated filter
        logger.info(f"Fetching {num_games} games with both ESPN and Kalshi data...")
        # Clear the games cache to ensure fresh data with updated has_kalshi filter
        if hasattr(games.list_games, '_cache_instance'):
            games.list_games._cache_instance.clear()
            logger.info("Cleared games endpoint cache to ensure fresh data")
        # Also delete the cache file directly to be absolutely sure
        from pathlib import Path
        cache_file = Path("webapp/.cache/list_games.cache")
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"Deleted cache file: {cache_file}")
        
        # Fetch games in batches, replacing skipped games until we have exactly num_games successful games
        games_list = []
        seen_game_ids = set()  # Track games we've already tried to avoid duplicates
        offset = 0
        batch_size = max(num_games, 100)  # Fetch in batches of at least 100
        
        logger.info(f"Fetching games to get exactly {num_games} successful simulations...")
        
        while len(games_list) < num_games:
            games_result = games.list_games(
                season="2025-26",  # Default season
                limit=batch_size,
                offset=offset,
                has_kalshi=True,  # Only games with Kalshi market AND candlestick data
                sort_by="date",
                sort_order="desc"
            )
            
            batch_games = games_result.get("games", [])
            if not batch_games:
                # No more games available
                logger.warning(f"Only found {len(games_list)} games with Kalshi data (requested {num_games})")
                break
            
            # Add games we haven't seen yet
            for game in batch_games:
                game_id = game.get("game_id")
                if game_id and game_id not in seen_game_ids:
                    games_list.append(game)
                    seen_game_ids.add(game_id)
                    if len(games_list) >= num_games:
                        break
            
            offset += batch_size
            
            # Safety check: if we've fetched many batches and still don't have enough, stop
            if offset > num_games * 2:
                logger.warning(f"Fetched {offset} games but only found {len(games_list)} unique games (requested {num_games})")
                break
        
        # Trim to exactly num_games (or as many as we have)
        games_list = games_list[:num_games]
        logger.info(f"Found {len(games_list)} games to simulate (requested {num_games})")
        
        if not games_list:
            raise HTTPException(
                status_code=404,
                detail=f"No games found with both ESPN and Kalshi data"
            )
        
        # Initialize progress tracking (thread-safe)
        if request_id:
            with _progress_lock:
                _simulation_progress[request_id] = {
                    "current": 0,
                    "total": len(games_list),
                    "status": "running"
                }
        
        def _is_game_completed(conn, game_id: str) -> bool:
            """Check if a game is completed (has final scores)."""
            check_sql = """
            SELECT MAX(e.home_score) as final_home_score, MAX(e.away_score) as final_away_score
            FROM espn.prob_event_state e
            WHERE e.game_id = %s
            """
            row = conn.execute(check_sql, (game_id,)).fetchone()
            return row and row[0] is not None and row[1] is not None
        
        def _generate_cache_key(game_id: str, entry_threshold: float, exit_threshold: float, 
                                bet_amount: float, exclude_first: int, exclude_last: int, slippage_rate: float, min_hold_seconds: int = 30, enable_fees: bool = False) -> str:
            """Generate a cache key for simulation results."""
            # Cache version: Increment when simulation logic changes (invalidates old cached results)
            # Version 4: Added enable_fees to cache key to separate fee-enabled vs fee-disabled results
            CACHE_VERSION = 4
            # Create a deterministic key from all parameters including version
            key_data = {
                "version": CACHE_VERSION,  # Include version to invalidate old cache
                "game_id": game_id,
                "entry_threshold": entry_threshold,
                "exit_threshold": exit_threshold,
                "bet_amount": bet_amount,
                "exclude_first_seconds": exclude_first,
                "exclude_last_seconds": exclude_last,
                "slippage_rate": slippage_rate,
                "min_hold_seconds": min_hold_seconds,  # Include min_hold_seconds in cache key
                "enable_fees": enable_fees  # Include enable_fees to separate fee-enabled vs fee-disabled results
            }
            # Use JSON to ensure consistent ordering, then hash for shorter key
            key_str = json.dumps(key_data, sort_keys=True)
            return hashlib.sha256(key_str.encode()).hexdigest()[:16]  # Use first 16 chars
        
        # Worker function to process a single game (runs in parallel)
        def process_game(game_data: dict, game_index: int) -> tuple[dict | None, dict | None]:
            """
            Process a single game and return (result_dict, error_dict).
            Each thread gets its own database connection.
            Checks cache first for completed games.
            """
            game_id = game_data.get("game_id")
            game_date_str = game_data.get("game_date")
            home_team = game_data.get("home_team_abbr", "HOME")
            away_team = game_data.get("away_team_abbr", "AWAY")
            
            logger.info(f"[Game {game_index}/{len(games_list)}] Processing game {game_id} ({away_team} @ {home_team}, {game_date_str})...")
            
            try:
                # Each thread gets its own DB connection from the pool
                with get_db_connection() as conn:
                    # Check if game is completed
                    is_completed = _is_game_completed(conn, game_id)
                    
                    # Generate cache key
                    cache_key = _generate_cache_key(
                        game_id, entry_threshold, exit_threshold, 
                        bet_amount, exclude_first_seconds, exclude_last_seconds, slippage_rate, min_hold_seconds, enable_fees
                    )
                    
                    # Check cache for completed games
                    if is_completed:
                        with _simulation_cache_lock:
                            cached_result = _simulation_cache.get(cache_key)
                            if cached_result is not None:
                                logger.info(f"  [Game {game_index}] Game {game_id}: Using cached result")
                                # Deep copy to avoid mutating the cached object
                                cached_result = copy.deepcopy(cached_result)
                                # Add game metadata (cache doesn't store this)
                                cached_result["game_id"] = game_id
                                cached_result["game_date"] = game_date_str
                                # Add game_id to each trade
                                for trade in cached_result.get("trades", []):
                                    trade["game_id"] = game_id
                                    trade["game_date"] = game_date_str
                                return cached_result, None
                    
                    # Get aligned data
                    import time
                    game_start_time = time.time()
                    logger.debug(f"  [Game {game_index}] Fetching aligned data for game {game_id}...")
                    aligned_data, game_start, duration, actual_outcome = get_aligned_data(
                        conn,
                        game_id,
                        exclude_first_seconds=exclude_first_seconds,
                        exclude_last_seconds=exclude_last_seconds
                    )
                    
                    if not aligned_data:
                        logger.warning(f"  [Game {game_index}] Game {game_id}: No aligned data found")
                        return None, {"game_id": game_id, "reason": "No aligned data"}
                    
                    logger.debug(f"  [Game {game_index}] Game {game_id}: Found {len(aligned_data)} aligned data points")
                    
                    # Run simulation
                    logger.debug(f"  [Game {game_index}] Running simulation for game {game_id}...")
                    results = simulate_trading_strategy(
                        aligned_data,
                        entry_threshold,
                        exit_threshold,
                        actual_outcome,
                        bet_amount_dollars=bet_amount,
                        slippage_rate=slippage_rate,
                        min_hold_seconds=min_hold_seconds,
                        game_start_timestamp=game_start,
                        game_duration_seconds=duration,
                        enable_fees=enable_fees
                    )
                    
                    game_elapsed = time.time() - game_start_time
                    logger.info(f"  [Game {game_index}] Game {game_id}: Completed in {game_elapsed:.3f}s")
                    
                    game_trades = results.get("num_trades", 0)
                    game_profit = results.get("total_profit_cents", 0.0) / 100.0
                    
                    logger.info(f"  [Game {game_index}] Game {game_id}: {game_trades} trades, ${game_profit:.2f} net profit")
                    
                    # Cache result for completed games (with very long TTL)
                    if is_completed:
                        # Store a deep copy without game metadata (metadata added on retrieval)
                        # MUST use deepcopy to prevent mutation when we add game_id/game_date to results later
                        cache_result = copy.deepcopy(results)
                        # Remove game-specific metadata that we'll add back on retrieval
                        cache_result.pop("game_id", None)
                        cache_result.pop("game_date", None)
                        # Remove game_id from trades (will add back on retrieval)
                        for trade in cache_result.get("trades", []):
                            trade.pop("game_id", None)
                            trade.pop("game_date", None)
                        
                        # Cache with 1 year TTL for completed games
                        with _simulation_cache_lock:
                            _simulation_cache.set(cache_key, cache_result, ttl=86400 * 365)
                            logger.debug(f"  [Game {game_index}] Game {game_id}: Cached result (key: {cache_key[:8]}...)")
                    
                    # Add game metadata
                    results["game_id"] = game_id
                    results["game_date"] = game_date_str
                    
                    # Add game_id to each trade for tracking
                    for trade in results.get("trades", []):
                        trade["game_id"] = game_id
                        trade["game_date"] = game_date_str
                    
                    return results, None
                    
            except Exception as e:
                logger.error(f"  [Game {game_index}] Game {game_id}: Error - {e}", exc_info=True)
                return None, {"game_id": game_id, "reason": str(e)}
        
        # Run simulations in parallel using ThreadPoolExecutor
        # Replace skipped games with new ones until we have exactly num_games successful games
        max_workers = min(8, len(games_list))
        logger.info(f"Starting parallel simulation. Will process games until we have {num_games} successful simulations...")
        
        import time
        bulk_start_time = time.time()
        
        game_results = []
        failed_games = []
        completed_count = 0
        current_offset = len(games_list)  # Track where we are in fetching more games
        
        # Use ThreadPoolExecutor for parallel processing
        # Keep processing batches until we have exactly num_games successful games
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            games_to_process = games_list.copy()
            
            while len(game_results) < num_games:
                # If we need more games, fetch them
                if not games_to_process:
                    needed = num_games - len(game_results)
                    logger.info(f"Have {len(game_results)} successful games, need {needed} more. Fetching additional games...")
                    more_games_result = games.list_games(
                        season="2025-26",
                        limit=max(needed * 2, 100),  # Fetch extra to account for failures
                        offset=current_offset,
                        has_kalshi=True,
                        sort_by="date",
                        sort_order="desc"
                    )
                    more_games = more_games_result.get("games", [])
                    if not more_games:
                        logger.warning(f"No more games available. Have {len(game_results)} successful games (requested {num_games})")
                        break
                    
                    # Filter out games we've already seen
                    new_games = [g for g in more_games if g.get("game_id") not in seen_game_ids]
                    for game in new_games:
                        seen_game_ids.add(game.get("game_id"))
                    games_to_process.extend(new_games)
                    current_offset += len(more_games)
                    
                    if not games_to_process:
                        logger.warning(f"No new games available. Have {len(game_results)} successful games (requested {num_games})")
                        break
                
                # Process a batch (enough to potentially get num_games successful)
                batch_size = min(len(games_to_process), (num_games - len(game_results)) * 2, max_workers * 3)
                batch = games_to_process[:batch_size]
                games_to_process = games_to_process[batch_size:]
                
                # Submit batch to thread pool
                future_to_game = {
                    executor.submit(process_game, game_data, completed_count + idx + 1): (completed_count + idx + 1, game_data)
                    for idx, game_data in enumerate(batch)
                }
                
                # Process completed futures as they finish
                batch_results = []
                batch_failed = []
                for future in as_completed(future_to_game):
                    game_index, game_data = future_to_game[future]
                    completed_count += 1
                    
                    # Update progress thread-safely
                    if request_id:
                        with _progress_lock:
                            _simulation_progress[request_id]["current"] = completed_count
                            _simulation_progress[request_id]["total"] = num_games  # Update total to requested number
                    
                    try:
                        result, error = future.result()
                        if result:
                            batch_results.append(result)
                        else:
                            batch_failed.append(error)
                    except Exception as e:
                        game_id = game_data.get("game_id", "unknown")
                        logger.error(f"Unexpected error processing game {game_id}: {e}", exc_info=True)
                        batch_failed.append({"game_id": game_id, "reason": f"Unexpected error: {str(e)}"})
                
                # Add successful results
                game_results.extend(batch_results)
                failed_games.extend(batch_failed)
                
                logger.info(f"Batch complete: {len(batch_results)} successful, {len(batch_failed)} failed. Total: {len(game_results)}/{num_games} successful games")
                
                # Stop if we have enough successful games
                if len(game_results) >= num_games:
                    logger.info(f"Reached {num_games} successful games. Stopping simulation.")
                    break
        
        # Trim to exactly num_games (take first num_games successful)
        game_results = game_results[:num_games]
        
        # Mark progress as complete
        if request_id:
            with _progress_lock:
                _simulation_progress[request_id]["status"] = "complete"
        
        # Aggregate results from all games
        all_trades = []
        # IMPORTANT: total_profit_cents is profit/loss (can be negative), NOT total money after.
        # Example: If you spent $20 and got $10 back, profit = -$10 (a loss)
        total_profit_cents = 0.0  # This is already net profit from simulate_trading_strategy
        total_trades = 0
        successful_games = len(game_results)
        
        for results in game_results:
            # Aggregate stats (total_profit_cents is already net profit after costs, can be negative)
            total_profit_cents += results.get("total_profit_cents", 0.0)
            total_trades += results.get("num_trades", 0)
            
            # Collect all trades
            for trade in results.get("trades", []):
                all_trades.append(trade)
        
        # Sort trades chronologically before computing metrics that depend on order
        # This ensures deterministic equity curve and accurate drawdown calculation
        # (Trades come back in non-deterministic order due to parallel thread completion)
        all_trades.sort(key=lambda t: (
            t.get("game_date", "") or "",
            t.get("exit_time") or t.get("entry_time") or 0
        ))
        
        # Calculate aggregated statistics (after all games processed)
        # Use net_profit_cents for all metrics (after costs)
        bulk_elapsed = time.time() - bulk_start_time
        avg_time_per_game = bulk_elapsed / len(games_list) if games_list else 0
        logger.info(f"[TIMING] Bulk simulation complete - TOTAL: {bulk_elapsed:.3f}s for {successful_games} successful games ({avg_time_per_game:.3f}s avg per game)")
        logger.info(f"Simulation complete. Successful: {successful_games} (requested {num_games}), Failed: {len(failed_games)}, Total trades: {total_trades}")
        winning_trades = [t for t in all_trades if (t.get("net_profit_cents") or 0) > 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        avg_profit_per_trade_cents = total_profit_cents / total_trades if total_trades > 0 else 0.0
        
        # Calculate additional metrics
        import statistics
        from typing import List
        
        # 1. ROI percentage
        # ROI = profit / (total_trades * bet_amount)
        # NOTE: This is profit divided by total per-trade notional deployed.
        # This is NOT account-level or portfolio ROI.
        total_capital_deployed = total_trades * bet_amount * 100  # in cents
        roi_percentage = (total_profit_cents / total_capital_deployed * 100.0) if total_capital_deployed > 0 else 0.0
        
        # 2. Position type breakdown (using net profit after costs)
        long_trades = [t for t in all_trades if t.get("position_type") == "long_espn"]
        short_trades = [t for t in all_trades if t.get("position_type") == "short_espn"]
        long_profit_cents = sum(t.get("net_profit_cents", 0) or 0 for t in long_trades)
        short_profit_cents = sum(t.get("net_profit_cents", 0) or 0 for t in short_trades)
        long_win_rate = len([t for t in long_trades if (t.get("net_profit_cents") or 0) > 0]) / len(long_trades) if long_trades else 0.0
        short_win_rate = len([t for t in short_trades if (t.get("net_profit_cents") or 0) > 0]) / len(short_trades) if short_trades else 0.0
        long_avg_profit = long_profit_cents / len(long_trades) if long_trades else 0.0
        short_avg_profit = short_profit_cents / len(short_trades) if short_trades else 0.0
        
        # 3. Risk metrics (max loss, max win, std dev) - using net profit after costs
        trade_profits = [(t.get("net_profit_cents") or 0) / 100.0 for t in all_trades]  # Convert to dollars
        max_loss = min(trade_profits) if trade_profits else 0.0
        max_win = max(trade_profits) if trade_profits else 0.0
        std_dev = statistics.stdev(trade_profits) if len(trade_profits) > 1 else 0.0
        
        # 4. Median profit (using net profit after costs)
        median_profit_cents = statistics.median([t.get("net_profit_cents") or 0 for t in all_trades]) if all_trades else 0.0
        
        # 5. Trades per game
        trades_per_game = total_trades / successful_games if successful_games > 0 else 0.0
        
        # 6. Average trade duration
        trade_durations = []
        for t in all_trades:
            if t.get("entry_time") is not None and t.get("exit_time") is not None:
                duration = t.get("exit_time") - t.get("entry_time")
                trade_durations.append(duration)
        avg_trade_duration_seconds = statistics.mean(trade_durations) if trade_durations else 0.0
        avg_trade_duration_minutes = avg_trade_duration_seconds / 60.0
        
        # 7. Per-game summary (already have game_results, just need to format)
        per_game_summary = [
            {
                "game_id": gr.get("game_id"),
                "game_date": gr.get("game_date"),
                "num_trades": gr.get("num_trades", 0),
                "profit_dollars": gr.get("total_profit_cents", 0) / 100.0,
                "win_rate": gr.get("win_rate", 0.0),
            }
            for gr in game_results
        ]
        
        # 8. Sharpe ratio (risk-adjusted return)
        # Sharpe = mean(returns) / stdev(returns) where returns = net_profit / bet_amount
        # Risk-free rate = 0
        # Must use returns (not raw dollars) to avoid bet-size inflation
        if len(all_trades) < 2:
            sharpe_ratio = 0.0
        else:
            # Calculate per-trade returns: return_i = net_profit_dollars / bet_amount_dollars
            trade_returns = [(t.get("net_profit_cents") or 0) / 100.0 / bet_amount for t in all_trades]
            mean_return = statistics.mean(trade_returns)
            std_dev_return = statistics.stdev(trade_returns) if len(trade_returns) > 1 else 0.0
            sharpe_ratio = mean_return / std_dev_return if std_dev_return > 0 else 0.0
        
        # 9. Distribution quartiles
        sorted_profits = sorted(trade_profits)
        if sorted_profits and len(sorted_profits) > 1:
            # Calculate quartiles manually for compatibility
            n = len(sorted_profits)
            q1_idx = int(n * 0.25)
            q2_idx = int(n * 0.5)  # median
            q3_idx = int(n * 0.75)
            q1 = sorted_profits[q1_idx]
            q2 = statistics.median(sorted_profits)  # median
            q3 = sorted_profits[q3_idx]
        elif sorted_profits:
            q1 = q2 = q3 = sorted_profits[0]
        else:
            q1 = q2 = q3 = 0.0
        
        # 10. Divergence at entry/exit
        entry_divergences = []
        exit_divergences = []
        for t in all_trades:
            entry_espn = t.get("entry_espn_prob")
            entry_kalshi = t.get("entry_kalshi_price")
            if entry_espn is not None and entry_kalshi is not None:
                entry_div = abs(entry_espn - entry_kalshi) * 100  # Convert to cents
                entry_divergences.append(entry_div)
            
            exit_espn = t.get("exit_espn_prob")
            exit_kalshi = t.get("exit_kalshi_price")
            if exit_espn is not None and exit_kalshi is not None:
                exit_div = abs(exit_espn - exit_kalshi) * 100  # Convert to cents
                exit_divergences.append(exit_div)
        
        avg_entry_divergence = statistics.mean(entry_divergences) if entry_divergences else 0.0
        avg_exit_divergence = statistics.mean(exit_divergences) if exit_divergences else 0.0
        
        # 11. Expectancy (EV per trade) = (WinRate × AvgWin) - (LossRate × AvgLoss) - using net profit after costs
        winning_trade_profits = [t.get("net_profit_cents", 0) / 100.0 for t in all_trades if (t.get("net_profit_cents") or 0) > 0]
        losing_trade_profits = [t.get("net_profit_cents", 0) / 100.0 for t in all_trades if (t.get("net_profit_cents") or 0) < 0]
        avg_win = statistics.mean(winning_trade_profits) if winning_trade_profits else 0.0
        avg_loss = abs(statistics.mean(losing_trade_profits)) if losing_trade_profits else 0.0
        loss_rate = len(losing_trade_profits) / total_trades if total_trades > 0 else 0.0
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        # 12. Profit Factor = Net Profits / Net Losses (after costs)
        net_profits = sum(winning_trade_profits) if winning_trade_profits else 0.0
        net_losses = abs(sum(losing_trade_profits)) if losing_trade_profits else 0.0
        profit_factor = net_profits / net_losses if net_losses > 0 else (net_profits if net_profits > 0 else 0.0)
        
        # 13. Maximum Drawdown (dollar and percentage)
        # Calculate running cumulative P&L (equity curve)
        cumulative_profits = []
        running_total = 0.0
        for profit in trade_profits:
            running_total += profit
            cumulative_profits.append(running_total)
        
        # Find maximum drawdown
        # Use initial capital (total capital deployed) as baseline for percentage calculation
        total_capital_deployed = total_trades * bet_amount if total_trades > 0 else bet_amount
        peak = 0.0
        max_drawdown_dollars = 0.0
        max_drawdown_percent = 0.0
        for equity in cumulative_profits:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown_dollars:
                max_drawdown_dollars = drawdown
                # Calculate percentage based on peak equity, or use capital deployed if peak is 0 or negative
                if peak > 0:
                    max_drawdown_percent = (drawdown / peak) * 100.0
                elif total_capital_deployed > 0:
                    # If we haven't reached a positive peak yet, use capital deployed as denominator
                    max_drawdown_percent = (drawdown / total_capital_deployed) * 100.0
                else:
                    # Fallback: if no capital deployed, just show dollar amount (percentage = N/A)
                    max_drawdown_percent = 0.0
        
        # 14. Equity curve data (for charting)
        equity_curve = [
            {"trade_number": i + 1, "cumulative_profit_dollars": cp}
            for i, cp in enumerate(cumulative_profits)
        ]
        
        # 15. Sample size indicator
        sample_size_n = total_trades
        
        # 16. Game phase stratification
        phase_trades = {
            "Q1": [t for t in all_trades if t.get("game_phase") == "Q1"],
            "Q2-Q3": [t for t in all_trades if t.get("game_phase") == "Q2-Q3"],
            "Q4": [t for t in all_trades if t.get("game_phase") == "Q4"],
        }
        phase_breakdown = {}
        for phase, trades_in_phase in phase_trades.items():
            if trades_in_phase:
                phase_profit_cents = sum(t.get("net_profit_cents", 0) or 0 for t in trades_in_phase)
                phase_win_rate = len([t for t in trades_in_phase if (t.get("net_profit_cents") or 0) > 0]) / len(trades_in_phase)
                phase_breakdown[phase] = {
                    "count": len(trades_in_phase),
                    "profit_dollars": phase_profit_cents / 100.0,
                    "win_rate": phase_win_rate,
                    "avg_profit_dollars": (phase_profit_cents / len(trades_in_phase)) / 100.0 if trades_in_phase else 0.0,
                }
            else:
                phase_breakdown[phase] = {
                    "count": 0,
                    "profit_dollars": 0.0,
                    "win_rate": 0.0,
                    "avg_profit_dollars": 0.0,
                }
        
        total_profit_dollars = total_profit_cents / 100.0
        logger.info(f"Final results: Total profit=${total_profit_dollars:.2f}, Win rate={win_rate*100:.1f}%, Avg profit/trade=${avg_profit_per_trade_cents/100.0:.2f}, ROI={roi_percentage:.2f}%")
        
        if failed_games:
            # Log ALL failed games without truncation
            failed_game_ids = [fg['game_id'] for fg in failed_games]
            logger.warning(f"Failed games ({len(failed_games)} total): {failed_game_ids}")
            # Also log reasons for debugging
            for fg in failed_games:
                logger.debug(f"  Game {fg['game_id']}: {fg.get('reason', 'Unknown reason')}")
        
        return {
            "total_profit_cents": total_profit_cents,
            "total_profit_dollars": total_profit_cents / 100.0,
            "num_trades": total_trades,
            "win_rate": win_rate,
            "avg_profit_per_trade_cents": avg_profit_per_trade_cents,
            "avg_profit_per_trade_dollars": avg_profit_per_trade_cents / 100.0,
            "num_games": successful_games,
            "num_games_requested": num_games,
            "num_games_failed": len(failed_games),
            "failed_game_ids": [fg['game_id'] for fg in failed_games],  # Include all failed game IDs in response
            "failed_games": failed_games,
            "entry_threshold": entry_threshold,
            "exit_threshold": exit_threshold,
            "exclude_first_seconds": exclude_first_seconds,
            "exclude_last_seconds": exclude_last_seconds,
            "bet_amount_dollars": bet_amount,
            "data_source": "official-candlesticks",
            "game_results": game_results,
            "trades": all_trades,
            # New metrics
            "roi_percentage": roi_percentage,
            "roi_note": "ROI is calculated as profit divided by total per-trade notional deployed. This is NOT account-level or portfolio ROI.",
            "position_breakdown": {
                "long": {
                    "count": len(long_trades),
                    "profit_dollars": long_profit_cents / 100.0,
                    "win_rate": long_win_rate,
                    "avg_profit_dollars": long_avg_profit / 100.0,
                },
                "short": {
                    "count": len(short_trades),
                    "profit_dollars": short_profit_cents / 100.0,
                    "win_rate": short_win_rate,
                    "avg_profit_dollars": short_avg_profit / 100.0,
                },
            },
            "risk_metrics": {
                "max_loss_dollars": max_loss,
                "max_win_dollars": max_win,
                "std_dev_dollars": std_dev,
            },
            "median_profit_cents": median_profit_cents,
            "median_profit_dollars": median_profit_cents / 100.0,
            "trades_per_game": trades_per_game,
            "avg_trade_duration_seconds": avg_trade_duration_seconds,
            "avg_trade_duration_minutes": avg_trade_duration_minutes,
            "per_game_summary": per_game_summary,
            "sharpe_ratio": sharpe_ratio,
            "distribution_quartiles": {
                "q1_dollars": q1,
                "q2_dollars": q2,  # median
                "q3_dollars": q3,
                "min_dollars": min(trade_profits) if trade_profits else 0.0,
                "max_dollars": max(trade_profits) if trade_profits else 0.0,
            },
            "divergence_metrics": {
                "avg_entry_divergence_cents": avg_entry_divergence,
                "avg_exit_divergence_cents": avg_exit_divergence,
            },
            # New metrics for data scientists
            "expectancy_dollars": expectancy,
            "profit_factor": profit_factor,
            "max_drawdown_dollars": max_drawdown_dollars,
            "max_drawdown_percent": max_drawdown_percent,
            "equity_curve": equity_curve,
            "sample_size_n": sample_size_n,
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running bulk simulation: {e}", exc_info=True)
        if request_id:
            with _progress_lock:
                if request_id in _simulation_progress:
                    _simulation_progress[request_id]["status"] = "error"
        raise HTTPException(status_code=500, detail=f"Error running bulk simulation: {str(e)}")


@router.get("/api/simulation/progress/{request_id}")
def get_simulation_progress(request_id: str) -> dict[str, Any]:
    """
    Get progress for a running simulation (thread-safe).
    
    Maintained for backward compatibility and initial status checks.
    For real-time updates, use WebSocket endpoint at /ws/simulation/{request_id}
    """
    with _progress_lock:
        if request_id not in _simulation_progress:
            return {"status": "not_found", "current": 0, "total": 0}
        
        return _simulation_progress[request_id].copy()  # Return copy to avoid race conditions


@router.websocket("/ws/simulation/{request_id}")
async def websocket_simulation_progress(websocket: WebSocket, request_id: str):
    """
    WebSocket endpoint for streaming simulation progress in real-time.
    
    Design Pattern: WebSocket Handler Pattern + Observer Pattern
    Algorithm: File monitoring with polling + broadcast to connected clients
    Big O: O(1) per connection, O(1) per progress update
    
    Message format sent to client:
        {
            "type": "progress",
            "progress": {
                "status": "running" | "complete" | "error",
                "current": int,
                "total": int,
                ...
            }
        }
    
    Connection closes automatically when simulation completes or errors.
    """
    client_ip = None
    if websocket.client:
        client_ip = websocket.client.host
    
    logger.info(f"WebSocket simulation progress connection attempt: request_id={request_id}, client_ip={client_ip}")
    
    # Validate request_id exists or will exist soon
    with _progress_lock:
        if request_id not in _simulation_progress:
            # Request might not exist yet if simulation just started
            # Allow connection but will send initial state when available
            initial_status = {"status": "not_found", "current": 0, "total": 0}
        else:
            initial_status = _simulation_progress[request_id].copy()
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket simulation progress connection accepted: request_id={request_id}, client_ip={client_ip}")
        
        # Send initial progress state
        await websocket.send_json({
            "type": "progress",
            "progress": initial_status
        })
        
        # Track last sent progress to detect changes
        last_progress = initial_status.copy()
        
        # Monitor progress for changes
        while True:
            try:
                # Check for progress updates every 100ms
                await asyncio.sleep(0.1)
                
                with _progress_lock:
                    if request_id not in _simulation_progress:
                        # Simulation not found or hasn't started yet
                        # Keep connection alive for a bit in case it starts soon
                        continue
                    
                    current_progress = _simulation_progress[request_id].copy()
                
                # Check if progress has changed
                if current_progress != last_progress:
                    # Progress changed, send update
                    await websocket.send_json({
                        "type": "progress",
                        "progress": current_progress
                    })
                    last_progress = current_progress
                    
                    # Close connection if simulation is complete or errored
                    status = current_progress.get("status", "unknown")
                    if status == "complete" or status == "error":
                        logger.info(f"Simulation {request_id} finished with status {status}, closing WebSocket connection")
                        await websocket.close(code=1000, reason=f"Simulation {status}")
                        break
                
                # Handle incoming messages (ping/pong for connection health)
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                    try:
                        data = json.loads(message)
                        if data.get("type") == "ping":
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": asyncio.get_event_loop().time()
                            })
                    except json.JSONDecodeError:
                        pass
                except asyncio.TimeoutError:
                    # No message received, continue monitoring
                    continue
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket simulation progress connection disconnected: request_id={request_id}")
                break
            except Exception as e:
                logger.error(f"Error in simulation progress WebSocket: {e}", exc_info=True)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error: {str(e)}"
                    })
                except Exception:
                    pass
                await asyncio.sleep(1)  # Wait before retrying
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket simulation progress connection closed normally: request_id={request_id}")
    except Exception as e:
        logger.error(f"WebSocket simulation progress error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except Exception:
            pass


@router.post("/api/simulation/clear-cache")
def clear_simulation_cache() -> dict[str, Any]:
    """
    Clear the simulation results cache.
    
    Useful for forcing recalculation of cached simulation results.
    """
    logger.info("[SIMULATION_CACHE] Clearing simulation results cache")
    
    try:
        with _simulation_cache_lock:
            cache_size_before = len(_simulation_cache.cache)
            _simulation_cache.clear()
            
        return {
            "status": "success",
            "message": f"Simulation cache cleared ({cache_size_before} entries removed)",
            "entries_removed": cache_size_before
        }
    except Exception as e:
        logger.error(f"[SIMULATION_CACHE] Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing simulation cache: {str(e)}")

