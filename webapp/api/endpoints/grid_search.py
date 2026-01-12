"""
Grid search hyperparameter optimization endpoint.

Design Pattern: Service Pattern + Background Task Pattern + Function Import Pattern
Algorithm: Exhaustive Grid Search with Train/Valid/Test Splits
Big O: O(k × n × m / p) where k = parameter combinations, n = games, m = data points per game, p = workers
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
import sys
import os
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import uuid
import time
from datetime import datetime, timezone
import asyncio
import json

import pandas as pd
import numpy as np

from ..db import get_db_connection
from ..logging_config import get_logger
from ..cache import SimpleCache
import hashlib
import json as json_lib


def _convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    
    FastAPI/Pydantic cannot serialize numpy types (numpy.bool_, numpy.int64, etc.),
    so we need to convert them to native Python types before returning.
    
    Design Pattern: Visitor Pattern for type conversion
    Algorithm: Recursive type checking and conversion
    Big O: O(n) where n = number of values in nested structure
    """
    if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                        np.int16, np.int32, np.int64, np.uint8, np.uint16,
                        np.uint32, np.uint64)):
        return int(obj)
    # NumPy 2.0 compatibility: np.float_ was removed, use np.float64 instead
    # Build float_types tuple based on NumPy version
    float_types = [np.floating, np.float16, np.float32, np.float64]
    # Only include np.float_ if it exists (NumPy < 2.0)
    if hasattr(np, 'float_'):
        float_types.append(np.float_)
    float_types = tuple(float_types)
    
    if isinstance(obj, float_types):
        return float(obj)
    elif isinstance(obj, (np.bool_, np.bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_numpy_types(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj

# Import simulation functions (reuse from simulation endpoint)
script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/trade/simulate_trading_strategy.py')
spec = importlib.util.spec_from_file_location("simulate_trading_strategy", script_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load simulation module from {script_path}")
simulate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulate_module)

get_aligned_data = simulate_module.get_aligned_data
simulate_trading_strategy = simulate_module.simulate_trading_strategy

# Import grid search functions
grid_search_script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/trade/grid_search_hyperparameters.py')
grid_search_spec = importlib.util.spec_from_file_location("grid_search_hyperparameters", grid_search_script_path)
if grid_search_spec is None or grid_search_spec.loader is None:
    raise RuntimeError(f"Failed to load grid search module from {grid_search_script_path}")
grid_search_module = importlib.util.module_from_spec(grid_search_spec)
grid_search_spec.loader.exec_module(grid_search_module)

GridSearchConfig = grid_search_module.GridSearchConfig
generate_grid = grid_search_module.generate_grid
get_game_ids_from_season = grid_search_module.get_game_ids_from_season
split_games = grid_search_module.split_games
run_simulation_for_games = grid_search_module.run_simulation_for_games
process_combination = grid_search_module.process_combination
load_model_artifact = grid_search_module.load_model_artifact

# Import db_lib connect function (needed by process_combination)
db_lib_path = os.path.join(os.path.dirname(__file__), '../../../scripts/lib/_db_lib.py')
db_lib_spec = importlib.util.spec_from_file_location("scripts.lib._db_lib", db_lib_path)
if db_lib_spec is None or db_lib_spec.loader is None:
    raise RuntimeError(f"Failed to load db_lib module from {db_lib_path}")
db_lib_module = importlib.util.module_from_spec(db_lib_spec)
# Register module in sys.modules before executing (required for dataclass decorator)
sys.modules["scripts.lib._db_lib"] = db_lib_module
db_lib_spec.loader.exec_module(db_lib_module)
connect = db_lib_module.connect

# Import analysis functions
analyze_script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/trade/analyze_grid_search_results.py')
analyze_spec = importlib.util.spec_from_file_location("analyze_grid_search_results", analyze_script_path)
if analyze_spec is None or analyze_spec.loader is None:
    raise RuntimeError(f"Failed to load analysis module from {analyze_script_path}")
analyze_module = importlib.util.module_from_spec(analyze_spec)
analyze_spec.loader.exec_module(analyze_module)

detect_patterns = analyze_module.detect_patterns

router = APIRouter()
logger = get_logger(__name__)

# In-memory progress tracking (thread-safe)
_grid_search_progress: dict[str, dict] = {}
_grid_search_lock = threading.Lock()

# Cache for grid search results (persists across server reloads)
# Cache version: Increment when grid search logic changes (invalidates old cached results)
GRID_SEARCH_CACHE_VERSION = 1
_grid_search_cache = SimpleCache(ttl_seconds=86400 * 30, cache_file="grid_search_results.cache")  # 30 day TTL
_grid_search_cache_lock = threading.Lock()  # Thread-safe cache access

# WebSocket connections registry for event-driven updates (no polling!)
# request_id -> set of WebSocket connections
# Using weakref to avoid memory leaks
import weakref
from typing import Set
from collections import defaultdict
_grid_search_websockets: dict[str, Set[weakref.ref]] = {}
_websocket_lock = threading.Lock()
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None

# Throttling for WebSocket updates to avoid overwhelming the system
# Track last update time and count per request_id
_last_websocket_update: dict[str, dict] = defaultdict(lambda: {"time": 0, "count": 0})
_websocket_update_lock = threading.Lock()
# Throttle: send update every N games OR every X milliseconds
WEBSOCKET_UPDATE_INTERVAL_GAMES = 2000  # Send update every 2000 games
WEBSOCKET_UPDATE_INTERVAL_MS = 4000  # OR every 4000ms, whichever comes first

# Progress counter batch size - update shared counter every N games to reduce lock contention
# Larger values = less lock contention but less granular progress updates
# Set to 250 to update counter every 250 games (easy to change)
PROGRESS_COUNTER_BATCH_SIZE = 250


def process_combination_with_pool(
    combination: tuple[float, float],
    game_splits: dict[str, list[str]],
    config: GridSearchConfig,
    progress: Optional[Any] = None,
    task_id: Optional[int] = None
) -> dict[str, Any]:
    """
    Wrapper around process_combination that uses connection pool instead of creating new connections.
    
    This significantly improves performance by reusing database connections across combinations.
    Each thread reuses connections from the pool instead of creating/closing connections for each combination.
    
    Design Pattern: Adapter Pattern + Object Pool Pattern
    Algorithm: Reuse connections from pool instead of creating new ones
    Big O: O(1) connection acquisition vs O(n) connection creation overhead
    
    Args:
        combination: (entry_threshold, exit_threshold) tuple
        game_splits: Dictionary with 'train', 'valid', 'test' keys containing game ID lists
        config: Grid search configuration
        progress: Progress object for tracking (optional)
        task_id: Task ID for progress tracking (optional)
    
    Returns:
        Dictionary with results for all splits
    """
    entry_threshold, exit_threshold = combination
    
    # Load model artifact once per combination (not per game)
    model_artifact = load_model_artifact(config.model_name) if config.model_name else None
    
    results = {
        'entry_threshold': entry_threshold,
        'exit_threshold': exit_threshold,
    }
    
    # Use connection pool instead of creating new connection
    # This reuses connections, significantly reducing overhead
    with get_db_connection() as conn:
        for split_name in ['train', 'valid', 'test']:
            game_ids = game_splits[split_name]
            split_results = run_simulation_for_games(
                conn,
                game_ids,
                entry_threshold,
                exit_threshold,
                config,
                model_artifact=model_artifact,
                progress=progress,
                task_id=task_id
            )
            results[split_name] = split_results
    
    return results


def _push_progress_update(request_id: str, progress_data: dict, force: bool = False) -> None:
    """
    Push progress update to all WebSocket connections for a request_id.
    Called from background thread - bridges to async event loop.
    
    Design Pattern: Event-Driven Pattern + Thread-to-Async Bridge + Throttling Pattern
    Algorithm: Throttled push on progress change (every N games OR every X ms)
    Big O: O(n) where n = number of connected WebSockets
    
    Args:
        request_id: Grid search request ID
        progress_data: Progress data dictionary
        force: If True, bypass throttling and send immediately
    """
    current_count = progress_data.get("current", 0)
    current_time_ms = int(time.time() * 1000)
    
    # Check throttling (unless forced)
    if not force:
        with _websocket_update_lock:
            last_update = _last_websocket_update[request_id]
            games_since_update = current_count - last_update["count"]
            time_since_update_ms = current_time_ms - last_update["time"]
            
            # Throttle: only send if enough games OR enough time has passed
            if (games_since_update < WEBSOCKET_UPDATE_INTERVAL_GAMES and 
                time_since_update_ms < WEBSOCKET_UPDATE_INTERVAL_MS):
                return  # Skip this update, throttled
            
            # Update last update tracking
            _last_websocket_update[request_id] = {
                "time": current_time_ms,
                "count": current_count
            }
    
    # Get current WebSocket connections for this request_id
    with _websocket_lock:
        websocket_refs = list(_grid_search_websockets.get(request_id, set()))
    
    if not websocket_refs:
        return
    
    # Prepare progress message
    current_combo_raw = progress_data.get("current_combo")
    current_combo_str = "" if current_combo_raw is None else str(current_combo_raw)
    
    progress_message = {
        "type": "progress",
        "progress": {
            "status": progress_data.get("status", "unknown"),
            "current": progress_data.get("current", 0),
            "total": progress_data.get("total", 0),
            "current_combo": current_combo_str
        }
    }
    
    # Push to all WebSocket connections via event loop
    # Get the main event loop (set when first WebSocket connects)
    global _main_event_loop
    if _main_event_loop is None:
        # Try to get the event loop from the current thread (won't work in background thread)
        try:
            _main_event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop in this thread - need to get it from the main thread
            # Try to get it from the default event loop policy
            try:
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    _main_event_loop = loop
                else:
                    logger.warning(f"No running event loop available for WebSocket push: {request_id}")
                    return
            except RuntimeError:
                logger.warning(f"No event loop available for WebSocket push: {request_id}")
                return
    
    # Schedule async send to all WebSocket connections
    sent_count = 0
    for ws_ref in websocket_refs:
        ws = ws_ref()
        if ws is None:
            # WebSocket was garbage collected, will be cleaned up
            continue
        
        try:
            # Schedule coroutine in event loop (from background thread to async context)
            asyncio.run_coroutine_threadsafe(
                _send_progress_update_safe(ws, progress_message),
                _main_event_loop
            )
            sent_count += 1
        except Exception as e:
            logger.debug(f"Failed to schedule WebSocket update for {request_id}: {e}")


async def _send_progress_update_safe(websocket: WebSocket, message: dict) -> None:
    """Helper function to safely send progress update via WebSocket."""
    try:
        await websocket.send_json(message)
    except Exception as e:
        logger.debug(f"Failed to send WebSocket progress update: {e}")
        # Connection might be closed, will be cleaned up on disconnect


def _cleanup_websocket_ref(request_id: str, ws_ref: weakref.ref) -> None:
    """Clean up WebSocket reference when connection is closed."""
    with _websocket_lock:
        if request_id in _grid_search_websockets:
            _grid_search_websockets[request_id].discard(ws_ref)
            if not _grid_search_websockets[request_id]:
                del _grid_search_websockets[request_id]


def _run_grid_search_background(
    request_id: str,
    season: str,
    entry_min: float,
    entry_max: float,
    entry_step: float,
    exit_min: float,
    exit_max: float,
    exit_step: float,
    bet_amount: float,
    enable_fees: bool,
    slippage_rate: float,
    exclude_first_seconds: int,
    exclude_last_seconds: int,
    use_trade_data: bool,
    train_ratio: float,
    valid_ratio: float,
    test_ratio: float,
    top_n: int,
    min_trade_count: int,
    max_games: Optional[int],
    workers: int,
    seed: int,
    dsn: str,
    model_name: Optional[str] = None
):
    """Background task to run grid search."""
    try:
        with _grid_search_lock:
            # Preserve cache_key if it exists (set before background thread started)
            existing_cache_key = _grid_search_progress.get(request_id, {}).get("_cache_key")
            _grid_search_progress[request_id] = {
                "status": "running",
                "current": 0,
                "total": 0,
                "current_combo": None,
                "error": None
            }
            # Restore cache_key if it was set
            if existing_cache_key:
                _grid_search_progress[request_id]["_cache_key"] = existing_cache_key
            initial_progress = _grid_search_progress[request_id].copy()
        
        # Force initial update to notify WebSocket clients
        _push_progress_update(request_id, initial_progress, force=True)
        
        # Create config
        from pathlib import Path
        config = GridSearchConfig(
            entry_min=entry_min,
            entry_max=entry_max,
            entry_step=entry_step,
            exit_min=exit_min,
            exit_max=exit_max,
            exit_step=exit_step,
            workers=workers,
            seed=seed,
            enable_fees=enable_fees,
            slippage_rate=slippage_rate,
            min_trade_count=min_trade_count,
            output_dir=Path("/tmp"),  # Not used, but required
            train_ratio=train_ratio,
            valid_ratio=valid_ratio,
            test_ratio=test_ratio,
            top_n=top_n,
            bet_amount=bet_amount,
            use_trade_data=use_trade_data,
            exclude_first_seconds=exclude_first_seconds,
            exclude_last_seconds=exclude_last_seconds,
            model_name=model_name
        )
        
        # Get game IDs
        with get_db_connection() as conn:
            game_ids = get_game_ids_from_season(conn, season)
        
        if not game_ids:
            raise ValueError(f"No games found for season {season}")
        
        # Limit games if max_games is specified (for faster testing)
        if max_games is not None and len(game_ids) > max_games:
            logger.info(f"Limiting to {max_games} games for testing (from {len(game_ids)} total)")
            game_ids = game_ids[:max_games]
        
        # Split games
        train_games, valid_games, test_games = split_games(game_ids, config)
        game_splits = {
            'train': train_games,
            'valid': valid_games,
            'test': test_games
        }
        
        # Generate grid
        combinations = generate_grid(config)
        
        # Calculate total work (combinations × games per combination)
        total_games_per_combo = len(train_games) + len(valid_games) + len(test_games)
        total_work = len(combinations) * total_games_per_combo
        
        with _grid_search_lock:
            _grid_search_progress[request_id]["total"] = total_work
            _grid_search_progress[request_id]["current"] = 0
        
        logger.info(f"Grid search {request_id}: Processing {len(combinations)} combinations × {total_games_per_combo} games = {total_work} total simulations")
        
        # Process combinations in parallel
        all_results = []
        # Use a thread-safe counter for progress tracking
        # Optimized: batch updates to reduce lock contention
        completed_lock = threading.Lock()
        completed_counter = [0]  # Use list to allow modification in nested function
        per_thread_counters = {}  # Track per-thread counts to batch updates
        
        # Create a progress callback that updates per game (not per combination)
        # Optimized to minimize lock contention - batch counter updates
        last_logged_count = [0]  # Track last logged count to avoid redundant calculations
        last_update_time_ms = [0]  # Track last update time for time-based throttling
        
        def update_progress_callback():
            """Callback to update progress after each game is processed - EVENT-DRIVEN PUSH."""
            thread_id = threading.get_ident()
            
            # Fast path: increment per-thread counter (no lock needed)
            if thread_id not in per_thread_counters:
                per_thread_counters[thread_id] = 0
            per_thread_counters[thread_id] += 1
            thread_count = per_thread_counters[thread_id]
            
            # Check time threshold BEFORE checking batch size
            # This ensures we update even if games are slow
            current_time_ms = int(time.time() * 1000)
            time_threshold_met = (current_time_ms - last_update_time_ms[0] >= WEBSOCKET_UPDATE_INTERVAL_MS)
            
            # Only update shared counter every N games to reduce lock contention
            # BUT: force update if time threshold is met (even if batch size not reached)
            should_update = (thread_count % PROGRESS_COUNTER_BATCH_SIZE == 0) or time_threshold_met
            
            if should_update:
                # Batch update: add all pending games from this thread
                with completed_lock:
                    completed_counter[0] += thread_count
                    current_completed = completed_counter[0]
                    per_thread_counters[thread_id] = 0  # Reset after batch update
            else:
                # Fast path: no lock acquisition, just track locally
                # We'll update on next batch boundary
                return
            
            # Check if we should push update: every N games OR every X milliseconds
            games_threshold_met = (current_completed % WEBSOCKET_UPDATE_INTERVAL_GAMES == 0)
            should_push_update = (games_threshold_met or time_threshold_met or current_completed >= total_work)
            
            # Only do expensive operations periodically (every batch or when needed)
            if should_push_update:
                # Update progress under main lock (only when needed)
                with _grid_search_lock:
                    if request_id in _grid_search_progress:
                        _grid_search_progress[request_id]["current"] = current_completed
                        progress_data = _grid_search_progress[request_id].copy()
                
                # Push update to WebSocket connections (throttled check happens inside)
                _push_progress_update(request_id, progress_data, force=False)
                last_update_time_ms[0] = current_time_ms  # Update time tracking
                
                # Log progress periodically (every 100 games, every 1%, or at completion)
                percent = (current_completed * 100) // total_work if total_work > 0 else 0
                last_percent = (last_logged_count[0] * 100) // total_work if total_work > 0 else 0
                
                # Log every 100 games OR every 1% change OR at completion
                if (current_completed % 100 == 0 or 
                    percent != last_percent or 
                    current_completed >= total_work):
                    remaining = total_work - current_completed
                    logger.info(f"Grid search {request_id}: Progress {current_completed}/{total_work} ({percent}%) - {remaining} remaining")
                    last_logged_count[0] = current_completed
            else:
                # Fast path: just update counter in progress dict without copying
                if current_completed % PROGRESS_COUNTER_BATCH_SIZE == 0:
                    with _grid_search_lock:
                        if request_id in _grid_search_progress:
                            _grid_search_progress[request_id]["current"] = current_completed
        
        def flush_remaining_progress():
            """Flush any remaining per-thread counters to ensure final count is accurate."""
            with completed_lock:
                for thread_id, count in per_thread_counters.items():
                    if count > 0:
                        completed_counter[0] += count
                        per_thread_counters[thread_id] = 0
                return completed_counter[0]
        
        def process_with_progress(combo):
            entry, exit_val = combo
            thread_id = threading.get_ident()
            logger.debug(f"Grid search {request_id}: Thread {thread_id} starting combination entry={entry:.3f} exit={exit_val:.3f}")
            start_time = time.time()
            
            # Create a simple progress object that calls our callback
            class SimpleProgress:
                def __init__(self, callback):
                    self.callback = callback
                    self.task_id = 1  # Dummy task_id
                
                def advance(self, task_id, increment):
                    """Called by run_simulation_for_games after each game."""
                    for _ in range(increment):
                        self.callback()
                
                def update(self, task_id, current=None):
                    """Called by run_simulation_for_games to update status."""
                    # Update current_combo when starting a new game
                    if current and "entry=" in str(current):
                        with _grid_search_lock:
                            if request_id in _grid_search_progress:
                                _grid_search_progress[request_id]["current_combo"] = str(current)
            
            # Create progress object with callback
            progress_obj = SimpleProgress(update_progress_callback)
            
            # Use connection pool wrapper instead of creating new connections
            # This reuses connections from the pool, significantly improving performance
            result = process_combination_with_pool(combo, game_splits, config, progress=progress_obj, task_id=progress_obj.task_id)
            
            elapsed = time.time() - start_time
            logger.debug(f"Grid search {request_id}: Thread {thread_id} completed combination entry={entry:.3f} exit={exit_val:.3f} in {elapsed:.1f}s")
            
            return result
        
        logger.info(f"Grid search {request_id}: Starting with {workers} worker threads for {len(combinations)} combinations")
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_combo = {executor.submit(process_with_progress, combo): combo for combo in combinations}
            
            completed_combos = 0
            for future in as_completed(future_to_combo):
                try:
                    result = future.result()
                    all_results.append(result)
                    completed_combos += 1
                    if completed_combos % 10 == 0 or completed_combos == len(combinations):
                        logger.info(f"Grid search {request_id}: Completed {completed_combos}/{len(combinations)} combinations")
                except Exception as e:
                    logger.error(f"Error processing combination: {e}", exc_info=True)
        
        # Flush any remaining per-thread counters to ensure final count is accurate
        final_count = flush_remaining_progress()
        with _grid_search_lock:
            if request_id in _grid_search_progress:
                _grid_search_progress[request_id]["current"] = final_count
                final_progress = _grid_search_progress[request_id].copy()
        
        # Force final progress update
        _push_progress_update(request_id, final_progress, force=True)
        
        # Aggregate results by split
        train_results = []
        valid_results = []
        test_results = []
        
        for result in all_results:
            if 'train' in result:
                train_results.append({
                    'entry_threshold': result['entry_threshold'],
                    'exit_threshold': result['exit_threshold'],
                    **result['train']
                })
            if 'valid' in result:
                valid_results.append({
                    'entry_threshold': result['entry_threshold'],
                    'exit_threshold': result['exit_threshold'],
                    **result['valid']
                })
            if 'test' in result:
                test_results.append({
                    'entry_threshold': result['entry_threshold'],
                    'exit_threshold': result['exit_threshold'],
                    **result['test']
                })
        
        # Filter training results to top N
        train_df = pd.DataFrame(train_results)
        train_df = train_df.sort_values('net_profit_dollars', ascending=False)
        top_n_train = [_convert_numpy_types(r) for r in train_df.head(top_n).to_dict('records')]
        
        # Select best combination
        # Get top N train combos
        top_n_combos = [(r['entry_threshold'], r['exit_threshold']) for r in top_n_train]
        
        # Find best on valid from top N
        valid_df = pd.DataFrame(valid_results)
        best_valid = None
        best_valid_profit = float('-inf')
        
        for entry, exit_val in top_n_combos:
            valid_match = valid_df[
                (valid_df['entry_threshold'] == entry) & 
                (valid_df['exit_threshold'] == exit_val)
            ]
            if not valid_match.empty:
                profit = valid_match.iloc[0]['net_profit_dollars']
                if profit > best_valid_profit:
                    best_valid_profit = profit
                    best_valid = _convert_numpy_types(valid_match.iloc[0].to_dict())
        
        if best_valid is None:
            # Fallback: use top train combo
            best_valid = top_n_train[0]
        
        # Find test result for best combo
        test_df = pd.DataFrame(test_results)
        test_match = test_df[
            (test_df['entry_threshold'] == best_valid['entry_threshold']) &
            (test_df['exit_threshold'] == best_valid['exit_threshold'])
        ]
        
        final_selection = {
            'chosen_params': {
                'entry_threshold': best_valid['entry_threshold'],
                'exit_threshold': best_valid['exit_threshold']
            },
            'train_metrics': next((r for r in top_n_train if r['entry_threshold'] == best_valid['entry_threshold'] and r['exit_threshold'] == best_valid['exit_threshold']), None),
            'valid_metrics': best_valid,
            'test_metrics': _convert_numpy_types(test_match.iloc[0].to_dict()) if not test_match.empty else None
        }
        
        # Transform data for visualization
        # Verify train_results and valid_results are different (sanity check)
        logger.debug(f"[VIZ_DATA] Before transform: train_results has {len(train_results)} items, valid_results has {len(valid_results)} items")
        if len(train_results) > 0 and len(valid_results) > 0:
            # Check if first entries are different (quick sanity check)
            train_first = train_results[0]
            valid_first = valid_results[0]
            if train_first.get('net_profit_dollars') == valid_first.get('net_profit_dollars') and train_first.get('entry_threshold') == valid_first.get('entry_threshold'):
                logger.warning(f"[VIZ_DATA] WARNING: First train and valid results appear identical! This may indicate a bug.")
        visualization_data = _transform_visualization_data(train_results, valid_results, final_selection)
        
        # Detect patterns
        pattern_detection = {}
        try:
            train_df_for_patterns = pd.DataFrame(top_n_train)
            valid_df_for_patterns = pd.DataFrame(valid_results)
            pattern_detection = detect_patterns(train_df_for_patterns, valid_df_for_patterns)
        except Exception as e:
            logger.warning(f"Error detecting patterns: {e}", exc_info=True)
            pattern_detection = {"error": str(e)}
        
        # Convert numpy types in results before storing
        validation_results_clean = [_convert_numpy_types(r) for r in valid_results]
        test_results_clean = [_convert_numpy_types(r) for r in test_results]
        
        # Store results
        with _grid_search_lock:
            _grid_search_progress[request_id].update({
                "status": "complete",
                "current": _grid_search_progress[request_id]["total"],  # Ensure current equals total
                "final_selection": _convert_numpy_types(final_selection),
                "training_results": top_n_train,
                "validation_results": validation_results_clean,
                "test_results": test_results_clean,
                "pattern_detection": _convert_numpy_types(pattern_detection),
                "visualization_data": _convert_numpy_types(visualization_data),
                "metadata": {
                    "num_games": {
                        "train": len(train_games),
                        "valid": len(valid_games),
                        "test": len(test_games)
                    },
                    "num_combinations": len(combinations),
                    "search_space": {
                        "entry_range": [entry_min, entry_max, entry_step],
                        "exit_range": [exit_min, exit_max, exit_step]
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            })
            final_progress = _grid_search_progress[request_id].copy()
            
            # Cache the results for future requests
            cache_key = final_progress.get("_cache_key")
            logger.debug(f"Grid search {request_id}: Attempting to cache results, cache_key present: {cache_key is not None}")
            if cache_key:
                # Remove internal cache_key from stored result before caching
                cache_data = final_progress.copy()
                cache_data.pop("_cache_key", None)
                with _grid_search_cache_lock:
                    _grid_search_cache.set(cache_key, cache_data)
                    _grid_search_cache.save()  # Force immediate save to disk
                    logger.info(f"Grid search results cached with key: {cache_key[:32]}... (cache size: {len(_grid_search_cache.cache)})")
                
                # Also save results to standardized file location for future use
                try:
                    from pathlib import Path
                    import json as json_lib
                    # Get repo root for consistent path resolution
                    repo_root = Path(__file__).parent.parent.parent.parent
                    output_dir = repo_root / "data" / "grid_search" / cache_key
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Write final_selection.json
                    final_selection = final_progress.get("final_selection", {})
                    if final_selection:
                        with open(output_dir / "final_selection.json", 'w') as f:
                            json_lib.dump(final_selection, f, indent=2)
                    
                    # Write split results
                    for split_name, results_key in [
                        ('train', 'training_results'),
                        ('valid', 'validation_results'),
                        ('test', 'test_results')
                    ]:
                        results_list = final_progress.get(results_key, [])
                        if results_list:
                            json_path = output_dir / f"grid_results_{split_name}.json"
                            json_data = {
                                'metadata': final_progress.get('metadata', {}),
                                'results': results_list
                            }
                            with open(json_path, 'w') as f:
                                json_lib.dump(json_data, f, indent=2)
                    
                    logger.info(f"Grid search results saved to: {output_dir}")
                except Exception as e:
                    logger.warning(f"Error saving grid search results to files: {e}")
            else:
                logger.warning(f"Grid search {request_id}: No cache_key found in final_progress, skipping cache. Keys in final_progress: {list(final_progress.keys())[:10]}")
        
        # Force final update to notify WebSocket clients
        _push_progress_update(request_id, final_progress, force=True)
    
    except Exception as e:
        logger.error(f"Error in grid search background task: {e}", exc_info=True)
        with _grid_search_lock:
            if request_id in _grid_search_progress:
                _grid_search_progress[request_id].update({
                    "status": "error",
                    "error": str(e)
                })
                error_progress = _grid_search_progress[request_id].copy()
        
        # Push error update (event-driven, force to ensure it's sent)
        _push_progress_update(request_id, error_progress, force=True)


def _generate_grid_search_cache_key(
    season: str,
    entry_min: float,
    entry_max: float,
    entry_step: float,
    exit_min: float,
    exit_max: float,
    exit_step: float,
    bet_amount: float,
    enable_fees: bool,
    slippage_rate: float,
    exclude_first_seconds: int,
    exclude_last_seconds: int,
    use_trade_data: bool,
    train_ratio: float,
    valid_ratio: float,
    test_ratio: float,
    top_n: int,
    min_trade_count: int,
    max_games: Optional[int] = None,
    seed: int = 42,
    model_name: Optional[str] = None
) -> str:
    """
    Generate a cache key for grid search results.
    
    Includes all parameters that affect the results, plus a cache version.
    """
    cache_params = {
        "version": GRID_SEARCH_CACHE_VERSION,
        "season": season,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "entry_step": entry_step,
        "exit_min": exit_min,
        "exit_max": exit_max,
        "exit_step": exit_step,
        "bet_amount": bet_amount,
        "enable_fees": enable_fees,
        "slippage_rate": slippage_rate,
        "exclude_first_seconds": exclude_first_seconds,
        "exclude_last_seconds": exclude_last_seconds,
        "use_trade_data": use_trade_data,
        "train_ratio": train_ratio,
        "valid_ratio": valid_ratio,
        "test_ratio": test_ratio,
        "top_n": top_n,
        "min_trade_count": min_trade_count,
        "max_games": max_games,
        "seed": seed,
        "model_name": model_name
    }
    # Create deterministic JSON string and hash it
    params_json = json_lib.dumps(cache_params, sort_keys=True)
    cache_key = f"grid_search_{hashlib.sha256(params_json.encode()).hexdigest()}"
    return cache_key


def _transform_visualization_data(train_results: list[dict], validation_results: list[dict], final_selection: dict) -> dict[str, Any]:
    """Transform results data for client-side Chart.js rendering."""
    try:
        # Validate inputs
        if not final_selection or 'chosen_params' not in final_selection:
            logger.error(f"[VIZ_DATA] final_selection missing or invalid: {final_selection}")
            raise ValueError("final_selection must contain 'chosen_params'")
        
        chosen_params = final_selection['chosen_params']
        if 'entry_threshold' not in chosen_params or 'exit_threshold' not in chosen_params:
            logger.error(f"[VIZ_DATA] chosen_params missing required fields: {chosen_params}")
            raise ValueError("chosen_params must contain 'entry_threshold' and 'exit_threshold'")
        
        # Sanity check: ensure train_results and validation_results are different objects
        if train_results is validation_results:
            logger.error("[VIZ_DATA] CRITICAL BUG: train_results and validation_results are the same object!")
            raise ValueError("train_results and validation_results must be different lists")
        
        # Create copies to avoid any potential mutation issues
        train_results_copy = [dict(r) for r in train_results]  # Deep copy each dict
        validation_results_copy = [dict(r) for r in validation_results]  # Deep copy each dict
        
        # Check if results are empty
        if not train_results_copy:
            logger.warning(f"[VIZ_DATA] train_results is empty, returning empty visualization data")
            return {}
        if not validation_results_copy:
            logger.warning(f"[VIZ_DATA] validation_results is empty, returning empty visualization data")
            return {}
        
        df_train = pd.DataFrame(train_results_copy)
        df_valid = pd.DataFrame(validation_results_copy)
        
        # Log data summary for debugging
        logger.info(f"[VIZ_DATA] Train results: {len(train_results)} rows, columns: {list(df_train.columns) if not df_train.empty else 'empty'}")
        logger.info(f"[VIZ_DATA] Valid results: {len(validation_results)} rows, columns: {list(df_valid.columns) if not df_valid.empty else 'empty'}")
        if not df_train.empty and 'net_profit_dollars' in df_train.columns:
            logger.info(f"[VIZ_DATA] Train profit range: {df_train['net_profit_dollars'].min():.2f} to {df_train['net_profit_dollars'].max():.2f}")
        if not df_valid.empty:
            if 'net_profit_dollars' in df_valid.columns:
                logger.info(f"[VIZ_DATA] Valid profit range: {df_valid['net_profit_dollars'].min():.2f} to {df_valid['net_profit_dollars'].max():.2f}")
            if 'profit_factor' in df_valid.columns:
                logger.info(f"[VIZ_DATA] Valid profit_factor range: {df_valid['profit_factor'].min():.2f} to {df_valid['profit_factor'].max():.2f}")
        
        # Verify dataframes are different
        if not df_train.empty and not df_valid.empty:
            if len(df_train) == len(df_valid):
                # Check if first few rows are identical (quick sanity check)
                train_sample = df_train.head(3)[['entry_threshold', 'exit_threshold', 'net_profit_dollars']].values.tolist()
                valid_sample = df_valid.head(3)[['entry_threshold', 'exit_threshold', 'net_profit_dollars']].values.tolist()
                if train_sample == valid_sample:
                    logger.warning(f"[VIZ_DATA] WARNING: First 3 rows of train and valid are identical! This may indicate a bug.")
        
        # Extract chosen params (already validated above)
        chosen_entry = chosen_params['entry_threshold']
        chosen_exit = chosen_params['exit_threshold']
        
        # Helper function to create heatmap data
        def create_heatmap_data(df, value_col):
            if df.empty:
                logger.warning(f"[VIZ_DATA] Empty dataframe for {value_col}")
                return {
                    'entry_thresholds': [],
                    'exit_thresholds': [],
                    'matrix': [],
                    'chosen_entry': chosen_entry,
                    'chosen_exit': chosen_exit
                }
            # Create pivot (same as analysis script)
            pivot = df.pivot(index='exit_threshold', columns='entry_threshold', values=value_col)
            
            # Sort index and columns in-place (doesn't create NaN values like reindex does)
            # This matches the analysis script behavior while ensuring consistent ordering
            pivot = pivot.sort_index(axis=0).sort_index(axis=1)
            
            entry_thresholds = list(pivot.columns)
            exit_thresholds = list(pivot.index)
            # Use pivot.values directly (no reindex) - matches analysis script behavior
            # Convert NaN to None for JSON serialization (pandas uses NaN, JSON uses null)
            matrix = [[None if pd.isna(val) else float(val) for val in row] for row in pivot.values]
            
            # Log matrix summary for debugging
            matrix_flat = [val for row in matrix for val in row if val is not None]
            if matrix_flat:
                logger.debug(f"[VIZ_DATA] {value_col} matrix: {len(matrix)} rows × {len(matrix[0]) if matrix else 0} cols, value range: {min(matrix_flat):.2f} to {max(matrix_flat):.2f}")
            
            return {
                'entry_thresholds': entry_thresholds,
                'exit_thresholds': exit_thresholds,
                'matrix': matrix,
                'chosen_entry': chosen_entry,
                'chosen_exit': chosen_exit
            }
        
        # 1. Profit heatmap (TRAIN) - uses TRAIN data with net_profit_dollars
        profit_heatmap_train = create_heatmap_data(df_train, 'net_profit_dollars')
        
        # 2. Profit heatmap (VALID) - uses VALID data with net_profit_dollars
        profit_heatmap_valid = create_heatmap_data(df_valid, 'net_profit_dollars')
        
        # 3. Profit factor heatmap (VALID) - uses VALID data with profit_factor
        profit_factor_heatmap_valid = create_heatmap_data(df_valid, 'profit_factor')
        
        # Marginal effects
        entry_marginal = df_valid.groupby('entry_threshold')['net_profit_dollars'].agg(['mean', 'std']).reset_index()
        exit_marginal = df_valid.groupby('exit_threshold')['net_profit_dollars'].agg(['mean', 'std']).reset_index()
        
        # Tradeoff scatter
        tradeoff_data = {
            'num_trades': df_valid['num_trades'].tolist(),
            'net_profit': df_valid['net_profit_dollars'].tolist(),
            'entry_threshold': df_valid['entry_threshold'].tolist()
        }
        
        # Verify the three heatmaps are different (sanity check)
        train_matrix_sample = profit_heatmap_train['matrix'][0][0] if profit_heatmap_train['matrix'] and profit_heatmap_train['matrix'][0] else None
        valid_matrix_sample = profit_heatmap_valid['matrix'][0][0] if profit_heatmap_valid['matrix'] and profit_heatmap_valid['matrix'][0] else None
        factor_matrix_sample = profit_factor_heatmap_valid['matrix'][0][0] if profit_factor_heatmap_valid['matrix'] and profit_factor_heatmap_valid['matrix'][0] else None
        
        logger.info(f"[VIZ_DATA] Sample values - Train profit: {train_matrix_sample}, Valid profit: {valid_matrix_sample}, Valid profit_factor: {factor_matrix_sample}")
        
        # Check if train and valid profit heatmaps are identical (they shouldn't be!)
        if train_matrix_sample == valid_matrix_sample and train_matrix_sample is not None:
            logger.error(f"[VIZ_DATA] ERROR: Train and Valid profit heatmaps have identical sample values! This is a bug.")
            # Check if entire matrices are identical
            if profit_heatmap_train['matrix'] == profit_heatmap_valid['matrix']:
                logger.error(f"[VIZ_DATA] ERROR: Train and Valid profit matrices are completely identical! This is a critical bug.")
        
        # Check if valid profit and profit_factor are identical (they definitely shouldn't be!)
        if valid_matrix_sample == factor_matrix_sample and valid_matrix_sample is not None:
            logger.error(f"[VIZ_DATA] ERROR: Valid profit and profit_factor heatmaps have identical sample values! This is a bug.")
            if profit_heatmap_valid['matrix'] == profit_factor_heatmap_valid['matrix']:
                logger.error(f"[VIZ_DATA] ERROR: Valid profit and profit_factor matrices are completely identical! This is a critical bug.")
        
        result = {
            'profit_heatmap_train': profit_heatmap_train,
            'profit_heatmap_valid': profit_heatmap_valid,
            'profit_factor_heatmap_valid': profit_factor_heatmap_valid,
            'marginal_effects': {
                'entry': {
                    'thresholds': entry_marginal['entry_threshold'].tolist(),
                    'mean': entry_marginal['mean'].tolist(),
                    'std': entry_marginal['std'].fillna(0).tolist()
                },
                'exit': {
                    'thresholds': exit_marginal['exit_threshold'].tolist(),
                    'mean': exit_marginal['mean'].tolist(),
                    'std': exit_marginal['std'].fillna(0).tolist()
                }
            },
            'tradeoff_scatter': tradeoff_data
        }
        
        # Convert numpy types to native Python types
        converted_result = _convert_numpy_types(result)
        
        # Final verification after conversion
        if 'profit_heatmap_train' in converted_result and 'profit_heatmap_valid' in converted_result:
            train_id = id(converted_result['profit_heatmap_train'])
            valid_id = id(converted_result['profit_heatmap_valid'])
            factor_id = id(converted_result['profit_factor_heatmap_valid'])
            logger.debug(f"[VIZ_DATA] Object IDs after conversion - Train: {train_id}, Valid: {valid_id}, Factor: {factor_id}")
            if train_id == valid_id or train_id == factor_id or valid_id == factor_id:
                logger.error(f"[VIZ_DATA] ERROR: Heatmap objects share the same memory address! This is a bug.")
        
        return converted_result
    except Exception as e:
        logger.error(f"Error transforming visualization data: {e}", exc_info=True)
        return {}


@router.post("/api/grid-search/run")
def run_grid_search(
    season: str = Query(..., description="Season label (e.g., '2025-26')"),
    entry_min: float = Query(0.02, description="Minimum entry threshold"),
    entry_max: float = Query(0.10, description="Maximum entry threshold"),
    entry_step: float = Query(0.01, description="Entry threshold step size"),
    exit_min: float = Query(0.00, description="Minimum exit threshold"),
    exit_max: float = Query(0.05, description="Maximum exit threshold"),
    exit_step: float = Query(0.005, description="Exit threshold step size"),
    bet_amount: float = Query(20.0, description="Bet amount in dollars per trade"),
    enable_fees: bool = Query(True, description="Enable Kalshi trading fees"),
    slippage_rate: float = Query(0.0, description="Slippage rate as decimal"),
    exclude_first_seconds: int = Query(60, description="Exclude first N seconds of game"),
    exclude_last_seconds: int = Query(60, description="Exclude last N seconds of game"),
    use_trade_data: bool = Query(True, description="Use trade-derived data vs candlesticks"),
    train_ratio: float = Query(0.70, description="Training set ratio"),
    valid_ratio: float = Query(0.15, description="Validation set ratio"),
    test_ratio: float = Query(0.15, description="Test set ratio"),
    top_n: int = Query(10, description="Top N train combos to consider for selection"),
    min_trade_count: int = Query(200, description="Minimum trades required for valid combo"),
    max_games: Optional[int] = Query(None, description="Limit number of games for testing (default: no limit)"),
    model_name: Optional[str] = Query(None, description="Model name: 'logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic', or None for ESPN probabilities"),
) -> dict[str, Any]:
    """
    Start a grid search hyperparameter optimization.
    
    Checks cache first. If cached results exist, returns them immediately.
    Otherwise, starts background task and returns request_id.
    
    Returns request_id immediately. Use progress endpoint to check status.
    """
    # Validate parameters
    if abs(train_ratio + valid_ratio + test_ratio - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail=f"Split ratios must sum to 1.0 (got {train_ratio + valid_ratio + test_ratio})"
        )
    
    if entry_min <= 0:
        raise HTTPException(status_code=400, detail="entry_min must be > 0")
    
    if entry_min >= entry_max:
        raise HTTPException(status_code=400, detail="entry_min must be < entry_max")
    
    if exit_min < 0:
        raise HTTPException(status_code=400, detail="exit_min must be >= 0")
    
    if exit_min >= exit_max:
        raise HTTPException(status_code=400, detail="exit_min must be < exit_max")
    
    if entry_step <= 0 or exit_step <= 0:
        raise HTTPException(status_code=400, detail="Step sizes must be > 0")
    
    # Auto-set internal parameters
    import multiprocessing
    workers = min(8, multiprocessing.cpu_count() or 1)
    seed = 42
    
    # Generate cache key
    cache_key = _generate_grid_search_cache_key(
        season=season,
        entry_min=entry_min,
        entry_max=entry_max,
        entry_step=entry_step,
        exit_min=exit_min,
        exit_max=exit_max,
        exit_step=exit_step,
        bet_amount=bet_amount,
        enable_fees=enable_fees,
        slippage_rate=slippage_rate,
        exclude_first_seconds=exclude_first_seconds,
        exclude_last_seconds=exclude_last_seconds,
        use_trade_data=use_trade_data,
        train_ratio=train_ratio,
        valid_ratio=valid_ratio,
        test_ratio=test_ratio,
        top_n=top_n,
        min_trade_count=min_trade_count,
        max_games=max_games,
        seed=seed,
        model_name=model_name
    )
    
    # Priority 1: Check for existing output files in standardized location (source of truth)
    # Files have ALL data, so we can compute visualization_data correctly
    from pathlib import Path
    # Get repo root (webapp/api/endpoints/grid_search.py -> repo root)
    repo_root = Path(__file__).parent.parent.parent.parent
    output_dir = repo_root / "data" / "grid_search" / cache_key
    final_selection_path = output_dir / "final_selection.json"
    
    logger.info(f"[FILE_CHECK] Checking for files at: {output_dir}")
    logger.info(f"[FILE_CHECK] Cache key: {cache_key}")
    logger.info(f"[FILE_CHECK] final_selection_path exists: {final_selection_path.exists()}")
    
    if final_selection_path.exists():
        logger.info(f"Grid search files found at {output_dir}, loading from disk...")
        try:
            # Load results from files
            import json as json_lib
            with open(final_selection_path, 'r') as f:
                final_selection = json_lib.load(f)
            
            # Load split results
            training_results = []
            validation_results = []
            test_results = []
            
            for split_name in ['train', 'valid', 'test']:
                json_path = output_dir / f"grid_results_{split_name}.json"
                if json_path.exists():
                    with open(json_path, 'r') as f:
                        split_data = json_lib.load(f)
                        results = split_data.get('results', [])
                        if split_name == 'train':
                            # Load ALL training results for visualization (top N is only for selection logic)
                            training_results = results
                        elif split_name == 'valid':
                            validation_results = results
                        elif split_name == 'test':
                            test_results = results
            
            # Compute pattern_detection and visualization_data from loaded results
            import pandas as pd
            pattern_detection = {}
            try:
                train_df = pd.DataFrame(training_results)
                valid_df = pd.DataFrame(validation_results)
                pattern_detection = detect_patterns(train_df, valid_df)
            except Exception as e:
                logger.warning(f"Error detecting patterns from file: {e}")
                pattern_detection = {"error": str(e)}
            
            visualization_data = {}
            try:
                # Validate inputs before transformation
                if not training_results:
                    logger.warning(f"[VIZ_DATA] training_results is empty, cannot generate visualization data")
                elif not validation_results:
                    logger.warning(f"[VIZ_DATA] validation_results is empty, cannot generate visualization data")
                elif not final_selection or not final_selection.get('chosen_params'):
                    logger.warning(f"[VIZ_DATA] final_selection missing or invalid, cannot generate visualization data")
                else:
                    logger.info(f"[VIZ_DATA] Transforming visualization data: {len(training_results)} train results, {len(validation_results)} valid results")
                    visualization_data = _transform_visualization_data(training_results, validation_results, final_selection)
                    if not visualization_data:
                        logger.warning(f"[VIZ_DATA] _transform_visualization_data returned empty dict")
                    else:
                        logger.info(f"[VIZ_DATA] Successfully generated visualization data with keys: {list(visualization_data.keys())}")
            except Exception as e:
                logger.error(f"Error transforming vizsualization data from file: {e}", exc_info=True)
                visualization_data = {}
            
            # Load metadata if available
            metadata = {}
            train_json_path = output_dir / "grid_results_train.json"
            if train_json_path.exists():
                with open(train_json_path, 'r') as f:
                    train_data = json_lib.load(f)
                    metadata = train_data.get('metadata', {})
            
            # Filter training results to top N for table display (visualization already uses all results)
            training_results_sorted = sorted(training_results, key=lambda x: x.get('net_profit_dollars', 0), reverse=True)
            top_n_training_results = [_convert_numpy_types(r) for r in training_results_sorted[:top_n]]
            
            # Store in progress tracking
            request_id = str(uuid.uuid4())
            with _grid_search_lock:
                _grid_search_progress[request_id] = {
                    "status": "complete",
                    "current": metadata.get('num_combinations', 0),
                    "total": metadata.get('num_combinations', 0),
                    "final_selection": _convert_numpy_types(final_selection),
                    "training_results": top_n_training_results,  # Top N for table display
                    "validation_results": [_convert_numpy_types(r) for r in validation_results],
                    "test_results": [_convert_numpy_types(r) for r in test_results],
                    "pattern_detection": _convert_numpy_types(pattern_detection),
                    "visualization_data": _convert_numpy_types(visualization_data),  # Uses ALL training_results
                    "metadata": _convert_numpy_types(metadata)
                }
            
            # Also store in cache for future use
            with _grid_search_cache_lock:
                _grid_search_cache.set(cache_key, _grid_search_progress[request_id])
            
            logger.info(f"Grid search loaded from files: {output_dir}")
            return {
                "request_id": request_id,
                "status": "complete",
                "cached": False,
                "source": "files"
            }
        except Exception as e:
            logger.warning(f"Error loading grid search from files: {e}, will check cache or run grid search")
    
    # Priority 2: Check cache (only if files don't exist)
    # But first, double-check if files exist (maybe final_selection.json check failed but files are there)
    # Also check if visualization_data needs recomputation
    train_json_path = output_dir / "grid_results_train.json"
    valid_json_path = output_dir / "grid_results_valid.json"
    files_exist = train_json_path.exists() and valid_json_path.exists() and final_selection_path.exists()
    
    if files_exist:
        logger.warning(f"Files exist at {output_dir} but were not loaded in Priority 1 check. This should not happen. Attempting to load now...")
        # This is a fallback - files should have been loaded in Priority 1
        # But if we get here, try to load them anyway
        try:
            import json as json_lib
            with open(final_selection_path, 'r') as f:
                final_selection = json_lib.load(f)
            
            training_results = []
            validation_results = []
            test_results = []
            
            for split_name in ['train', 'valid', 'test']:
                json_path = output_dir / f"grid_results_{split_name}.json"
                if json_path.exists():
                    with open(json_path, 'r') as f:
                        split_data = json_lib.load(f)
                        results = split_data.get('results', [])
                        if split_name == 'train':
                            training_results = results
                        elif split_name == 'valid':
                            validation_results = results
                        elif split_name == 'test':
                            test_results = results
            
            # Compute visualization_data
            import pandas as pd
            visualization_data = {}
            try:
                if training_results and validation_results and final_selection:
                    logger.info(f"[VIZ_DATA] Computing visualization_data from files: {len(training_results)} train, {len(validation_results)} valid")
                    visualization_data = _transform_visualization_data(training_results, validation_results, final_selection)
                    if visualization_data:
                        logger.info(f"[VIZ_DATA] Successfully computed visualization_data with keys: {list(visualization_data.keys())}")
            except Exception as e:
                logger.error(f"Error computing visualization_data from files: {e}", exc_info=True)
                visualization_data = {}
            
            # Load metadata
            metadata = {}
            if train_json_path.exists():
                with open(train_json_path, 'r') as f:
                    train_data = json_lib.load(f)
                    metadata = train_data.get('metadata', {})
            
            # Filter training results to top N for table
            training_results_sorted = sorted(training_results, key=lambda x: x.get('net_profit_dollars', 0), reverse=True)
            top_n_training_results = [_convert_numpy_types(r) for r in training_results_sorted[:top_n]]
            
            # Store in progress tracking
            request_id = str(uuid.uuid4())
            with _grid_search_lock:
                _grid_search_progress[request_id] = {
                    "status": "complete",
                    "current": metadata.get('num_combinations', 0),
                    "total": metadata.get('num_combinations', 0),
                    "final_selection": _convert_numpy_types(final_selection),
                    "training_results": top_n_training_results,
                    "validation_results": [_convert_numpy_types(r) for r in validation_results],
                    "test_results": [_convert_numpy_types(r) for r in test_results],
                    "pattern_detection": {},
                    "visualization_data": _convert_numpy_types(visualization_data),
                    "metadata": _convert_numpy_types(metadata)
                }
            
            logger.info(f"Grid search loaded from files (fallback): {output_dir}")
            return {
                "request_id": request_id,
                "status": "complete",
                "cached": False,
                "source": "files"
            }
        except Exception as e:
            logger.error(f"Error loading files in fallback: {e}", exc_info=True)
    
    # Check cache (files don't exist, or files exist but cache was hit first)
    with _grid_search_cache_lock:
        cached_result = _grid_search_cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Grid search cache HIT for key: {cache_key[:32]}...")
            
            # ALWAYS ensure visualization_data is present - compute if missing
            visualization_data = cached_result.get("visualization_data", {})
            needs_recompute = not visualization_data or not visualization_data.get("profit_heatmap_train")
            
            if needs_recompute:
                logger.info(f"[VIZ_DATA] Cached result missing visualization_data, attempting to recompute...")
                
                # First, try to load from files (best case - complete data)
                final_selection = cached_result.get("final_selection", {})
                training_results = []
                validation_results = []
                
                if train_json_path.exists() and valid_json_path.exists() and final_selection_path.exists():
                    try:
                        import json as json_lib
                        logger.info(f"[VIZ_DATA] Loading from files for recomputation...")
                        with open(train_json_path, 'r') as f:
                            train_data = json_lib.load(f)
                            training_results = train_data.get('results', [])
                        with open(valid_json_path, 'r') as f:
                            valid_data = json_lib.load(f)
                            validation_results = valid_data.get('results', [])
                        with open(final_selection_path, 'r') as f:
                            final_selection = json_lib.load(f)
                        logger.info(f"[VIZ_DATA] Loaded {len(training_results)} train, {len(validation_results)} valid from files")
                    except Exception as e:
                        logger.warning(f"[VIZ_DATA] Error loading from files: {e}, will try cached data")
                
                # If files didn't work, try to use cached training_results and validation_results
                if not training_results or not validation_results:
                    logger.info(f"[VIZ_DATA] Files not available, attempting to use cached results...")
                    training_results = cached_result.get("training_results", [])
                    validation_results = cached_result.get("validation_results", [])
                    # Note: cached results might only be top N, so heatmaps may be incomplete
                    if training_results and validation_results:
                        logger.info(f"[VIZ_DATA] Using cached results: {len(training_results)} train, {len(validation_results)} valid (may be top N only)")
                
                # Compute visualization_data if we have the required data
                if training_results and validation_results and final_selection and final_selection.get('chosen_params'):
                    try:
                        logger.info(f"[VIZ_DATA] Computing visualization_data: {len(training_results)} train, {len(validation_results)} valid")
                        visualization_data = _transform_visualization_data(training_results, validation_results, final_selection)
                        if visualization_data:
                            logger.info(f"[VIZ_DATA] Successfully computed visualization_data with keys: {list(visualization_data.keys())}")
                            cached_result["visualization_data"] = _convert_numpy_types(visualization_data)
                            # Update cache with computed visualization_data
                            _grid_search_cache.set(cache_key, cached_result)
                            _grid_search_cache.save()
                        else:
                            logger.warning(f"[VIZ_DATA] _transform_visualization_data returned empty dict")
                    except Exception as e:
                        logger.error(f"[VIZ_DATA] Error computing visualization_data: {e}", exc_info=True)
                        # Set empty dict to prevent errors downstream
                        visualization_data = {}
                else:
                    logger.warning(f"[VIZ_DATA] Cannot compute: training_results={len(training_results) if training_results else 0}, validation_results={len(validation_results) if validation_results else 0}, final_selection={'present' if final_selection.get('chosen_params') else 'missing'}")
                    visualization_data = {}
            
            # Ensure visualization_data is in cached_result
            if not cached_result.get("visualization_data"):
                cached_result["visualization_data"] = visualization_data
            
            # Create a new request_id for this cached result
            request_id = str(uuid.uuid4())
            # Store cached result in progress tracking (so it can be retrieved via progress endpoint)
            with _grid_search_lock:
                _grid_search_progress[request_id] = cached_result.copy()
            return {
                "request_id": request_id,
                "status": "complete",
                "cached": True,
                "source": "cache"
            }
    
    # Priority 3: Files and cache don't exist - start new grid search
    logger.info(f"Grid search files and cache MISS for key: {cache_key[:32]}..., starting background task")
    
    # Generate unique request_id
    request_id = str(uuid.uuid4())
    
    # Get DSN from environment
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=500, detail="DATABASE_URL environment variable not set")
    
    # Store cache_key in progress for later use when storing results
    with _grid_search_lock:
        if request_id not in _grid_search_progress:
            _grid_search_progress[request_id] = {}
        _grid_search_progress[request_id]["_cache_key"] = cache_key
    
    # Start background task
    thread = threading.Thread(
        target=_run_grid_search_background,
        args=(
            request_id,
            season,
            entry_min,
            entry_max,
            entry_step,
            exit_min,
            exit_max,
            exit_step,
            bet_amount,
            enable_fees,
            slippage_rate,
            exclude_first_seconds,
            exclude_last_seconds,
            use_trade_data,
            train_ratio,
            valid_ratio,
            test_ratio,
            top_n,
            min_trade_count,
            max_games,
            workers,
            seed,
            model_name,
            dsn
        ),
        daemon=True
    )
    thread.start()
    
    return {
        "request_id": request_id,
        "status": "started",
        "cached": False
    }


@router.get("/api/grid-search/progress/{request_id}")
def get_grid_search_progress(request_id: str) -> dict[str, Any]:
    """
    Get progress for a running grid search.
    
    Maintained for backward compatibility and initial status checks.
    For real-time updates, use WebSocket endpoint at /ws/grid-search/{request_id}
    """
    with _grid_search_lock:
        if request_id not in _grid_search_progress:
            raise HTTPException(status_code=404, detail="Request ID not found")
        
        progress = _grid_search_progress[request_id].copy()
        return {
            "status": progress.get("status", "unknown"),
            "current": progress.get("current", 0),
            "total": progress.get("total", 0),
            "current_combo": progress.get("current_combo")
        }


@router.websocket("/ws/grid-search/{request_id}")
async def websocket_grid_search_progress(websocket: WebSocket, request_id: str):
    """
    WebSocket endpoint for streaming grid search progress in real-time.
    
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
                "current_combo": str,
                ...
            }
        }
    
    Connection closes automatically when grid search completes or errors.
    """
    client_ip = None
    if websocket.client:
        client_ip = websocket.client.host
    
    logger.info(f"WebSocket grid search progress connection attempt: request_id={request_id}, client_ip={client_ip}")
    
    # Validate request_id exists or will exist soon
    with _grid_search_lock:
        if request_id not in _grid_search_progress:
            # Request might not exist yet if grid search just started
            # Allow connection but will send initial state when available
            initial_status = {
                "status": "not_found",
                "current": 0,
                "total": 0,
                "current_combo": ""
            }
        else:
            progress = _grid_search_progress[request_id].copy()
            initial_status = {
                "status": progress.get("status", "unknown"),
                "current": progress.get("current", 0),
                "total": progress.get("total", 0),
                "current_combo": progress.get("current_combo", "")
            }
    
    # Store main event loop for thread-to-async bridge
    global _main_event_loop
    try:
        _main_event_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass  # Will be set when WebSocket connects
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket grid search progress connection accepted: request_id={request_id}, client_ip={client_ip}")
        
        # Register this WebSocket connection for event-driven updates (no polling!)
        ws_ref = weakref.ref(websocket, lambda ref: _cleanup_websocket_ref(request_id, ref))
        with _websocket_lock:
            if request_id not in _grid_search_websockets:
                _grid_search_websockets[request_id] = set()
            _grid_search_websockets[request_id].add(ws_ref)
        
        # Send initial progress state
        await websocket.send_json({
            "type": "progress",
            "progress": initial_status
        })
        
        # EVENT-DRIVEN: Wait for messages and handle disconnection
        # Progress updates are pushed immediately when they occur via _push_progress_update()
        # No polling loop - updates come as events!
        try:
            while True:
                try:
                    # Wait for incoming messages (ping/pong) or disconnection
                    # Progress updates come via event-driven push from background task
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
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
                    # No message received, check if task is complete (only check periodically)
                    with _grid_search_lock:
                        if request_id in _grid_search_progress:
                            status = _grid_search_progress[request_id].get("status", "unknown")
                            if status == "complete" or status == "error":
                                logger.info(f"Grid search {request_id} finished with status {status}, closing WebSocket connection")
                                await websocket.close(code=1000, reason=f"Grid search {status}")
                                break
                    # Continue waiting for updates (they come via events, not polling)
                    continue
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket grid search progress connection disconnected: request_id={request_id}")
        except Exception as e:
            logger.error(f"Error in grid search progress WebSocket: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                })
            except Exception:
                pass
        finally:
            # Unregister WebSocket connection
            _cleanup_websocket_ref(request_id, ws_ref)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket grid search progress connection closed normally: request_id={request_id}")
    except Exception as e:
        logger.error(f"WebSocket grid search progress error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except Exception:
            pass


@router.get("/api/grid-search/results/{request_id}")
def get_grid_search_results(request_id: str) -> dict[str, Any]:
    """Get results for a completed grid search."""
    with _grid_search_lock:
        if request_id not in _grid_search_progress:
            raise HTTPException(status_code=404, detail="Request ID not found")
        
        progress = _grid_search_progress[request_id]
        status = progress.get("status")
        
        if status == "running":
            raise HTTPException(status_code=202, detail="Grid search still running. Check progress endpoint.")
        
        if status == "error":
            error = progress.get("error", "Unknown error")
            raise HTTPException(status_code=500, detail=f"Grid search failed: {error}")
        
        if status != "complete":
            raise HTTPException(status_code=400, detail=f"Unexpected status: {status}")
        
        # Convert numpy types to native Python types for JSON serialization
        results = {
            "final_selection": progress.get("final_selection"),
            "training_results": progress.get("training_results", []),
            "validation_results": progress.get("validation_results", []),
            "test_results": progress.get("test_results", []),
            "pattern_detection": progress.get("pattern_detection", {}),
            "visualization_data": progress.get("visualization_data", {}),
            "metadata": progress.get("metadata", {})
        }
        
        return _convert_numpy_types(results)


@router.get("/api/grid-search/comparison")
def get_grid_search_comparison() -> dict[str, Any]:
    """
    Get comparison data for all grid search models.
    
    Reads model_comparison.json and loads visualization data from each model's result directory.
    Returns unified format with metrics and visualization data for all models.
    
    Design Pattern: Facade Pattern - provides unified interface to multiple data sources
    Algorithm: O(n × m) where n = models (5), m = data files per model (2-3)
    Big O: O(n × m) - linear in number of models and files
    """
    from pathlib import Path
    
    logger = get_logger(__name__)
    
    # Get repository root (assuming we're in webapp/api/endpoints/)
    repo_root = Path(__file__).parent.parent.parent.parent
    grid_search_dir = repo_root / "data" / "grid_search"
    comparison_json_path = grid_search_dir / "model_comparison.json"
    
    # Check if comparison file exists
    if not comparison_json_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Comparison data not found. Please run the comparison script first: python3 scripts/trade/compare_grid_search_models.py"
        )
    
    try:
        # Load comparison JSON
        with open(comparison_json_path, 'r') as f:
            comparison_data = json_lib.load(f)
        
        models = comparison_data.get('models', [])
        if not models:
            raise HTTPException(
                status_code=404,
                detail="No models found in comparison data"
            )
        
        # Load visualization data for each model
        visualization_data_by_model = {}
        
        for model in models:
            model_name = model.get('model_name', 'Unknown')
            result_dir_name = model.get('result_dir', '')
            
            if not result_dir_name:
                logger.warning(f"Model {model_name} has no result_dir, skipping visualization data")
                continue
            
            result_dir = grid_search_dir / result_dir_name
            
            # Load train and valid results
            train_json_path = result_dir / "grid_results_train.json"
            valid_json_path = result_dir / "grid_results_valid.json"
            
            train_results = []
            valid_results = []
            
            if train_json_path.exists():
                with open(train_json_path, 'r') as f:
                    train_data = json_lib.load(f)
                    train_results = train_data.get('results', [])
            
            if valid_json_path.exists():
                with open(valid_json_path, 'r') as f:
                    valid_data = json_lib.load(f)
                    valid_results = valid_data.get('results', [])
            
            # Construct final_selection from model data (comparison JSON structure)
            # The comparison JSON has chosen_params, test_metrics, valid_metrics, train_metrics at model level
            final_selection = {
                'chosen_params': model.get('chosen_params', {}),
                'test_metrics': model.get('test_metrics', {}),
                'valid_metrics': model.get('valid_metrics', {}),
                'train_metrics': model.get('train_metrics', {})
            }
            
            # Transform to visualization data using existing function
            if train_results and valid_results and final_selection.get('chosen_params'):
                try:
                    viz_data = _transform_visualization_data(
                        train_results,
                        valid_results,
                        final_selection
                    )
                    visualization_data_by_model[model_name] = _convert_numpy_types(viz_data)
                except Exception as e:
                    logger.warning(f"Error transforming visualization data for {model_name}: {e}")
                    visualization_data_by_model[model_name] = {}
            else:
                logger.warning(f"Insufficient data for {model_name} visualization")
                visualization_data_by_model[model_name] = {}
        
        # Build unified response
        response = {
            "models": models,
            "visualization_data": visualization_data_by_model,
            "comparison_timestamp": comparison_data.get('comparison_timestamp')
        }
        
        return _convert_numpy_types(response)
        
    except json_lib.JSONDecodeError as e:
        logger.error(f"Error parsing comparison JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in comparison file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error loading comparison data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading comparison data: {str(e)}"
        )

