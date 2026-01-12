#!/usr/bin/env python3
"""
Grid search hyperparameter optimization for trading strategy entry/exit thresholds.

Design Pattern: Map-Reduce Pattern for parallel execution
Algorithm: Exhaustive Grid Search with Train/Valid/Test Splits
Big O: O(k × n × m / p) where k = parameter combinations, n = games, m = data points per game, p = workers

This script systematically tests entry/exit threshold combinations across train/valid/test splits
to identify optimal trading strategy parameters.
"""

import argparse
import json
import logging
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

# Add project root to path to import from scripts and webapp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect

# Import simulation functions
from scripts.trade.simulate_trading_strategy import get_aligned_data, simulate_trading_strategy

# Import model loading
from scripts.lib._winprob_lib import load_artifact, WinProbArtifact

# Import cache utilities for shared caching with webapp
try:
    from webapp.api.cache import SimpleCache
    from webapp.api.endpoints.grid_search import _generate_grid_search_cache_key, GRID_SEARCH_CACHE_VERSION
    CACHE_AVAILABLE = True
except ImportError:
    # Fallback if webapp not available
    CACHE_AVAILABLE = False
    # Logger not yet defined, will log warning later if needed

# Set up Rich console and logging
# Force terminal mode and redirect stdout/stderr to keep progress bar sticky
console = Console(stderr=True, force_terminal=True)

# Configure logging to use RichHandler for clean rendering under progress bar
# Use force=True to override any existing logging configuration
# This ensures ALL loggers go through RichHandler, preventing "raw" output that breaks the progress bar
try:
    from webapp.api.logging_config import get_logger
    # First, force basicConfig to override any existing handlers
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(
            console=console, 
            rich_tracebacks=True, 
            markup=False,
            show_path=False,
            show_time=False
        )],
        force=True  # Override any existing logging config
    )
    # Now get logger - it will use the root handler we just set
    logger = get_logger(__name__)
    # Ensure this logger propagates to root and uses root's RichHandler
    logger.propagate = True
    logger.handlers.clear()  # Remove any handlers that get_logger might have added
except ImportError:
    # Fallback if webapp not available
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(
            console=console, 
            rich_tracebacks=True, 
            markup=False,
            show_path=False,
            show_time=False
        )],
        force=True  # Override any existing logging config
    )
    logger = logging.getLogger(__name__)


@dataclass
class GridSearchConfig:
    """Configuration for grid search."""
    entry_min: float
    entry_max: float
    entry_step: float
    exit_min: float
    exit_max: float
    exit_step: float
    workers: int
    seed: int
    enable_fees: bool
    slippage_rate: float
    min_trade_count: int
    output_dir: Path
    train_ratio: float
    valid_ratio: float
    test_ratio: float
    top_n: int
    bet_amount: float = 20.0
    use_trade_data: bool = True
    exclude_first_seconds: int = 60
    exclude_last_seconds: int = 60
    model_name: Optional[str] = None  # Model name: 'logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic', or None for ESPN


def load_model_artifact(model_name: Optional[str]) -> Optional[WinProbArtifact]:
    """
    Load model artifact by name. Returns None if model_name is None.
    
    Args:
        model_name: Model name ('logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic') or None
    
    Returns:
        WinProbArtifact object or None if model_name is None
    
    Raises:
        ValueError: If model_name is not recognized
        FileNotFoundError: If model file does not exist
    """
    if model_name is None:
        return None
    
    model_file_map = {
        "logreg_platt": "data/models/winprob_logreg_platt_2017-2023.json",
        "logreg_isotonic": "data/models/winprob_logreg_isotonic_2017-2023.json",
        "catboost_platt": "data/models/winprob_catboost_platt_2017-2023.json",
        "catboost_isotonic": "data/models/winprob_catboost_isotonic_2017-2023.json",
    }
    
    if model_name not in model_file_map:
        raise ValueError(f"Unknown model name: {model_name}. Valid options: {list(model_file_map.keys())}")
    
    model_path = Path(model_file_map[model_name])
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    return load_artifact(model_path)


def generate_grid(config: GridSearchConfig) -> list[tuple[float, float]]:
    """
    Generate grid of (entry_threshold, exit_threshold) combinations.
    
    Constraints:
    - entry > 0
    - exit >= 0
    - exit < entry
    
    Args:
        config: Grid search configuration
    
    Returns:
        List of (entry_threshold, exit_threshold) tuples
    """
    combinations = []
    
    # Generate entry thresholds
    entry_values = []
    entry = config.entry_min
    while entry <= config.entry_max:
        if entry > 0:  # Constraint: entry > 0
            entry_values.append(entry)
        entry += config.entry_step
    
    # Generate exit thresholds
    exit_values = []
    exit = config.exit_min
    while exit <= config.exit_max:
        if exit >= 0:  # Constraint: exit >= 0
            exit_values.append(exit)
        exit += config.exit_step
    
    # Generate combinations with constraint: exit < entry
    for entry_threshold in entry_values:
        for exit_threshold in exit_values:
            if exit_threshold < entry_threshold:  # Constraint: exit < entry
                combinations.append((entry_threshold, exit_threshold))
    
    logger.debug(f"Generated {len(combinations)} valid combinations from {len(entry_values)} entry values and {len(exit_values)} exit values")
    return combinations


def get_game_ids_from_season(conn: psycopg.Connection, season: str) -> list[str]:
    """
    Get game IDs with both ESPN and Kalshi data for a season.
    
    Args:
        conn: Database connection
        season: Season label (e.g., "2025-26")
    
    Returns:
        List of game IDs
    """
    sql = """
    WITH kalshi_games AS MATERIALIZED (
        SELECT DISTINCT km.espn_event_id
        FROM kalshi.markets km
        WHERE km.espn_event_id IS NOT NULL
    )
    SELECT DISTINCT p.game_id
    FROM espn.probabilities_raw_items p
    JOIN kalshi_games kg ON kg.espn_event_id = p.game_id
    WHERE p.season_label = %s
    GROUP BY p.game_id
    HAVING COUNT(*) > 100
    ORDER BY p.game_id
    """
    
    rows = conn.execute(sql, (season,)).fetchall()
    game_ids = [str(row[0]) for row in rows]
    logger.debug(f"Found {len(game_ids)} games with both ESPN and Kalshi data for season {season}")
    return game_ids


def get_game_ids_from_file(game_list_path: str) -> list[str]:
    """
    Get game IDs from JSON file.
    
    Args:
        game_list_path: Path to JSON file containing list of game IDs
    
    Returns:
        List of game IDs
    """
    with open(game_list_path, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        game_ids = [str(gid) for gid in data]
    elif isinstance(data, dict) and 'game_ids' in data:
        game_ids = [str(gid) for gid in data['game_ids']]
    else:
        raise ValueError(f"Invalid game list format in {game_list_path}. Expected list or dict with 'game_ids' key.")
    
    logger.debug(f"Loaded {len(game_ids)} game IDs from {game_list_path}")
    return game_ids


def split_games(game_ids: list[str], config: GridSearchConfig) -> tuple[list[str], list[str], list[str]]:
    """
    Split game IDs into train/valid/test sets deterministically.
    
    Args:
        game_ids: List of game IDs
        config: Grid search configuration
    
    Returns:
        Tuple of (train_games, valid_games, test_games)
    """
    # Sort for deterministic order
    sorted_game_ids = sorted(set(game_ids))
    
    # Shuffle with seed for reproducibility
    rng = random.Random(config.seed)
    shuffled = sorted_game_ids.copy()
    rng.shuffle(shuffled)
    
    # Calculate split indices
    total = len(shuffled)
    train_end = int(total * config.train_ratio)
    valid_end = train_end + int(total * config.valid_ratio)
    
    train_games = shuffled[:train_end]
    valid_games = shuffled[train_end:valid_end]
    test_games = shuffled[valid_end:]
    
    logger.debug(f"Split {total} games: train={len(train_games)}, valid={len(valid_games)}, test={len(test_games)}")
    
    return train_games, valid_games, test_games


def run_simulation_for_games(
    conn: psycopg.Connection,
    game_ids: list[str],
    entry_threshold: float,
    exit_threshold: float,
    config: GridSearchConfig,
    model_artifact: Optional[WinProbArtifact] = None,
    progress: Optional[Any] = None,
    task_id: Optional[int] = None
) -> dict[str, Any]:
    """
    Run simulation for a list of games and aggregate metrics.
    
    Args:
        conn: Database connection
        game_ids: List of game IDs to simulate
        entry_threshold: Entry threshold
        exit_threshold: Exit threshold
        config: Grid search configuration
    
    Returns:
        Dictionary with aggregated metrics
    """
    all_trades = []
    total_net_profit_cents = 0.0
    total_gross_profit_cents = 0.0
    total_fees_cents = 0.0
    total_hold_time_seconds = 0.0
    
    # Suppress verbose logging during batch processing (already done at higher level)
    for game_id in game_ids:
        try:
            # Update progress to show current game
            if progress is not None and task_id is not None:
                progress.update(task_id, current=f"game {game_id[:8]}... entry={entry_threshold:.3f} exit={exit_threshold:.3f}")
            
            # Get aligned data
            aligned_data, game_start, duration, actual_outcome = get_aligned_data(
                conn,
                game_id,
                exclude_first_seconds=config.exclude_first_seconds,
                exclude_last_seconds=config.exclude_last_seconds,
                use_trade_data=config.use_trade_data,
                model_artifact=model_artifact,
                model_name=config.model_name
            )
            
            if not aligned_data:
                logger.debug(f"Skipping game {game_id}: no aligned data")
                # Still advance progress even if skipped
                if progress is not None and task_id is not None:
                    progress.advance(task_id, 1)
                continue
            
            # Run simulation
            results = simulate_trading_strategy(
                aligned_data,
                entry_threshold,
                exit_threshold,
                actual_outcome,
                bet_amount_dollars=config.bet_amount,
                slippage_rate=config.slippage_rate,
                min_hold_seconds=30,
                game_start_timestamp=game_start,
                game_duration_seconds=duration,
                enable_fees=config.enable_fees
            )
            
            # Aggregate metrics
            all_trades.extend(results.get('trades', []))
            total_net_profit_cents += results.get('total_profit_cents', 0.0)
            total_gross_profit_cents += results.get('total_gross_profit_cents', 0.0)
            
            # Calculate fees from trades
            for trade in results.get('trades', []):
                # Fees are embedded in net_profit vs gross_profit difference
                gross_profit_cents = trade.get('profit_cents', 0.0) or 0.0
                net_profit_cents = trade.get('net_profit_cents', 0.0) or 0.0
                total_fees_cents += (gross_profit_cents - net_profit_cents)
                
                # Calculate hold time
                entry_time = trade.get('entry_time')
                exit_time = trade.get('exit_time')
                if entry_time and exit_time:
                    total_hold_time_seconds += (exit_time - entry_time)
            
            # Update progress bar after each game
            if progress is not None and task_id is not None:
                progress.advance(task_id, 1)
        
        except Exception as e:
            logger.warning(f"Error processing game {game_id}: {e}")
            # Still advance progress even on error
            if progress is not None and task_id is not None:
                progress.advance(task_id, 1)
            continue
    
    # Calculate aggregated metrics
    num_trades = len(all_trades)
    net_profit_dollars = total_net_profit_cents / 100.0
    total_fees_dollars = total_fees_cents / 100.0
    
    # Win rate
    winning_trades = [t for t in all_trades if (t.get('net_profit_cents') or 0) > 0]
    win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0.0
    
    # Average metrics
    avg_net_profit_per_trade = net_profit_dollars / num_trades if num_trades > 0 else 0.0
    avg_hold_time = total_hold_time_seconds / num_trades if num_trades > 0 else 0.0
    
    # Profit factor
    gross_profits = sum(t.get('profit_cents', 0.0) or 0.0 for t in winning_trades) / 100.0
    gross_losses = abs(sum(t.get('profit_cents', 0.0) or 0.0 for t in all_trades if (t.get('net_profit_cents') or 0) < 0)) / 100.0
    profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 0.0)
    
    # Max drawdown
    cumulative_profits = []
    running_total = 0.0
    for trade in all_trades:
        profit_dollars = (trade.get('net_profit_cents', 0.0) or 0.0) / 100.0
        running_total += profit_dollars
        cumulative_profits.append(running_total)
    
    peak = 0.0
    max_drawdown = 0.0
    for equity in cumulative_profits:
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Check if valid (meets min_trade_count)
    is_valid = num_trades >= config.min_trade_count
    
    return {
        'entry_threshold': entry_threshold,
        'exit_threshold': exit_threshold,
        'net_profit_dollars': net_profit_dollars,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'avg_net_profit_per_trade': avg_net_profit_per_trade,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'total_fees': total_fees_dollars,
        'avg_hold_time': avg_hold_time,
        'is_valid': is_valid
    }


def process_combination(
    combination: tuple[float, float],
    game_splits: dict[str, list[str]],
    config: GridSearchConfig,
    dsn: str,
    progress: Optional[Any] = None,
    task_id: Optional[int] = None
) -> dict[str, Any]:
    """
    Process a single parameter combination across all splits.
    
    Args:
        combination: (entry_threshold, exit_threshold) tuple
        game_splits: Dictionary with 'train', 'valid', 'test' keys containing game ID lists
        config: Grid search configuration
        dsn: Database connection string
    
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
    
    # Run simulation for each split
    with connect(dsn) as conn:
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


def get_git_hash() -> Optional[str]:
    """Get current git hash if available."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def load_from_cache(cache_key: str, output_dir: Path, season_or_list: str) -> bool:
    """
    Try to load grid search results from cache.
    
    Returns True if cache hit and files were written, False otherwise.
    """
    if not CACHE_AVAILABLE:
        return False
    
    try:
        cache = SimpleCache(ttl_seconds=86400 * 30, cache_file="grid_search_results.cache")
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            return False
        
        logger.info(f"Cache HIT! Loading results from cache (key: {cache_key[:32]}...)")
        
        # Extract results from cached data
        train_results = cached_data.get('training_results', [])
        valid_results = cached_data.get('validation_results', [])
        test_results = cached_data.get('test_results', [])
        final_selection = cached_data.get('final_selection', {})
        
        # Convert to the format expected by the rest of the script
        results_by_split = {
            'train': [],
            'valid': [],
            'test': []
        }
        
        # For train, we only have top N, so we need to reconstruct full results
        # We'll use valid_results structure as template since it has all combinations
        # Actually, cached data might not have all train results, only top N
        # So we'll write what we have
        
        # Write train results (top N only)
        for result in train_results:
            results_by_split['train'].append(result)
        
        # Write valid and test results (all combinations)
        for result in valid_results:
            results_by_split['valid'].append(result)
        
        for result in test_results:
            results_by_split['test'].append(result)
        
        # Write CSV files
        import csv
        for split_name in ['train', 'valid', 'test']:
            csv_path = output_dir / f'grid_results_{split_name}.csv'
            with open(csv_path, 'w', newline='') as f:
                if results_by_split[split_name]:
                    writer = csv.DictWriter(f, fieldnames=[
                        'entry_threshold', 'exit_threshold', 'net_profit_dollars', 'num_trades',
                        'win_rate', 'avg_net_profit_per_trade', 'profit_factor', 'max_drawdown',
                        'total_fees', 'avg_hold_time', 'is_valid'
                    ])
                    writer.writeheader()
                    for row in results_by_split[split_name]:
                        writer.writerow(row)
            logger.debug(f"Wrote {csv_path} from cache")
        
        # Write JSON files
        git_hash = get_git_hash()
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = cached_data.get('metadata', {})
        
        for split_name in ['train', 'valid', 'test']:
            json_path = output_dir / f'grid_results_{split_name}.json'
            json_data = {
                'metadata': {
                    **metadata,
                    'timestamp': timestamp,
                    'git_hash': git_hash,
                    'cached': True,
                    'cache_key': cache_key[:32] + '...'
                },
                'results': results_by_split[split_name]
            }
            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            logger.debug(f"Wrote {json_path} from cache")
        
        # Write final selection
        selection_path = output_dir / 'final_selection.json'
        with open(selection_path, 'w') as f:
            json.dump(final_selection, f, indent=2)
        logger.debug(f"Wrote {selection_path} from cache")
        
        # Write game splits if available in metadata
        num_games = metadata.get('num_games', {})
        if num_games:
            # We don't have the actual game IDs from cache, but we can create placeholder files
            # or skip this - the splits aren't critical for analysis
            pass
        
        logger.info("✓ Successfully loaded results from cache")
        return True
        
    except Exception as e:
        logger.warning(f"Error loading from cache: {e}. Will run grid search normally.")
        return False


def save_to_cache(cache_key: str, results_by_split: dict, final_selection: dict, 
                  train_games: list, valid_games: list, test_games: list,
                  combinations: list, config: GridSearchConfig, season_or_list: str):
    """Save grid search results to cache."""
    if not CACHE_AVAILABLE:
        return
    
    try:
        cache = SimpleCache(ttl_seconds=86400 * 30, cache_file="grid_search_results.cache")
        
        # Get top N train results
        train_results_sorted = sorted(results_by_split['train'], 
                                     key=lambda x: x['net_profit_dollars'], reverse=True)
        top_n_train = train_results_sorted[:config.top_n]
        
        # Prepare cache data in same format as webapp
        cache_data = {
            'status': 'complete',
            'final_selection': final_selection,
            'training_results': top_n_train,
            'validation_results': results_by_split['valid'],
            'test_results': results_by_split['test'],
            'metadata': {
                'num_games': {
                    'train': len(train_games),
                    'valid': len(valid_games),
                    'test': len(test_games)
                },
                'num_combinations': len(combinations),
                'search_space': {
                    'entry_range': [config.entry_min, config.entry_max, config.entry_step],
                    'exit_range': [config.exit_min, config.exit_max, config.exit_step]
                },
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'season_or_list': season_or_list
            }
        }
        
        cache.set(cache_key, cache_data)
        cache.save()
        logger.info(f"✓ Results cached (key: {cache_key[:32]}...)")
        
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Grid search hyperparameter optimization for trading strategy thresholds"
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--season', type=str, help='Season label (e.g., "2025-26")')
    input_group.add_argument('--game-list', type=str, help='Path to JSON file with game IDs')
    
    # Grid parameters
    parser.add_argument('--entry-min', type=float, default=0.02, help='Minimum entry threshold (default: 0.02)')
    parser.add_argument('--entry-max', type=float, default=0.20, help='Maximum entry threshold (default: 0.20)')
    parser.add_argument('--entry-step', type=float, default=0.01, help='Entry threshold step size (default: 0.01)')
    parser.add_argument('--exit-min', type=float, default=0.00, help='Minimum exit threshold (default: 0.00)')
    parser.add_argument('--exit-max', type=float, default=0.05, help='Maximum exit threshold (default: 0.05)')
    parser.add_argument('--exit-step', type=float, default=0.005, help='Exit threshold step size (default: 0.005)')
    
    # Execution parameters
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers (default: 8)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for deterministic splits (default: 42)')
    
    # Cost parameters
    parser.add_argument('--enable-fees', action='store_true', default=True, help='Enable trading fees (default: True)')
    parser.add_argument('--no-enable-fees', dest='enable_fees', action='store_false', help='Disable trading fees')
    parser.add_argument('--slippage-rate', type=float, default=0.0, help='Slippage rate as decimal (default: 0.0)')
    
    # Other parameters
    parser.add_argument('--min-trade-count', type=int, default=200, help='Minimum trades for valid combo (default: 200)')
    parser.add_argument('--output-dir', type=str, default=None, help='Output directory (default: data/grid_search/{cache_key}/ or grid_search_results if no cache)')
    parser.add_argument('--train-ratio', type=float, default=0.70, help='Train split ratio (default: 0.70)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed debug logs (default: False)')
    parser.add_argument('--valid-ratio', type=float, default=0.15, help='Validation split ratio (default: 0.15)')
    parser.add_argument('--test-ratio', type=float, default=0.15, help='Test split ratio (default: 0.15)')
    parser.add_argument('--top-n', type=int, default=10, help='Top N train combos to consider for selection (default: 10)')
    parser.add_argument('--bet-amount', type=float, default=20.0, help='Bet amount in dollars (default: 20.0)')
    parser.add_argument('--dsn', type=str, help='Database connection string (or use DATABASE_URL env var)')
    parser.add_argument('--use-trade-data', action='store_true', default=True, help='Use trade-derived data (default: True)')
    parser.add_argument('--no-use-trade-data', dest='use_trade_data', action='store_false', help='Use candlesticks instead')
    parser.add_argument('--exclude-first-seconds', type=int, default=60, help='Exclude first N seconds (default: 60)')
    parser.add_argument('--exclude-last-seconds', type=int, default=60, help='Exclude last N seconds (default: 60)')
    
    # Test mode parameters
    parser.add_argument('--max-games', type=int, help='Limit number of games for testing (default: no limit)')
    parser.add_argument('--max-combinations', type=int, help='Limit number of combinations for testing (default: no limit)')
    parser.add_argument('--no-cache', action='store_true', help='Skip cache check and force fresh run')
    
    # Model selection
    parser.add_argument('--model-name', type=str, default=None, 
                       help='Model name: "logreg_platt", "logreg_isotonic", "catboost_platt", "catboost_isotonic", or None for ESPN probabilities (default: None)')
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    log_level = logging.DEBUG if args.verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(log_level)
    # Update RichHandler level if it exists
    for handler in root.handlers:
        if isinstance(handler, RichHandler):
            handler.setLevel(log_level)
    
    # Validate split ratios
    total_ratio = args.train_ratio + args.valid_ratio + args.test_ratio
    if abs(total_ratio - 1.0) > 0.01:
        parser.error(f"Split ratios must sum to 1.0 (got {total_ratio})")
    
    # Generate cache key early to determine default output directory
    cache_key = None
    if args.season and CACHE_AVAILABLE and not args.no_cache:
        try:
            cache_key = _generate_grid_search_cache_key(
                season=args.season,
                entry_min=args.entry_min,
                entry_max=args.entry_max,
                entry_step=args.entry_step,
                exit_min=args.exit_min,
                exit_max=args.exit_max,
                exit_step=args.exit_step,
                bet_amount=args.bet_amount,
                enable_fees=args.enable_fees,
                slippage_rate=args.slippage_rate,
                exclude_first_seconds=args.exclude_first_seconds,
                exclude_last_seconds=args.exclude_last_seconds,
                use_trade_data=args.use_trade_data,
                train_ratio=args.train_ratio,
                valid_ratio=args.valid_ratio,
                test_ratio=args.test_ratio,
                top_n=args.top_n,
                min_trade_count=args.min_trade_count,
                max_games=args.max_games,
                seed=args.seed,
                model_name=args.model_name
            )
        except Exception as e:
            logger.debug(f"Cache key generation failed: {e}. Will use default output directory.")
    
    # Determine output directory
    if args.output_dir:
        # User specified output directory (override)
        output_dir = Path(args.output_dir)
    elif cache_key:
        # Use standardized location based on cache key
        output_dir = Path("data/grid_search") / cache_key
    else:
        # Fallback to old default
        output_dir = Path("grid_search_results")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # Create config
    config = GridSearchConfig(
        entry_min=args.entry_min,
        entry_max=args.entry_max,
        entry_step=args.entry_step,
        exit_min=args.exit_min,
        exit_max=args.exit_max,
        exit_step=args.exit_step,
        workers=args.workers,
        seed=args.seed,
        enable_fees=args.enable_fees,
        slippage_rate=args.slippage_rate,
        min_trade_count=args.min_trade_count,
        output_dir=output_dir,
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
        test_ratio=args.test_ratio,
        top_n=args.top_n,
        bet_amount=args.bet_amount,
        use_trade_data=args.use_trade_data,
        exclude_first_seconds=args.exclude_first_seconds,
        exclude_last_seconds=args.exclude_last_seconds,
        model_name=args.model_name
    )
    
    # Get database connection
    dsn = get_dsn(args.dsn)
    
    # Try to load from cache (cache_key already generated above)
    if cache_key and CACHE_AVAILABLE and not args.no_cache:
        try:
            # Try to load from cache
            if load_from_cache(cache_key, output_dir, args.season):
                logger.info("Grid search complete (loaded from cache).")
                return 0
        except Exception as e:
            logger.debug(f"Cache check failed: {e}. Will run grid search normally.")
    
    # Get game IDs
    with connect(dsn) as conn:
        if args.season:
            game_ids = get_game_ids_from_season(conn, args.season)
            season_or_list = args.season
        else:
            game_ids = get_game_ids_from_file(args.game_list)
            season_or_list = args.game_list
    
    if not game_ids:
        logger.error("No game IDs found")
        return 1
    
    # Limit games if testing
    if args.max_games and len(game_ids) > args.max_games:
        logger.debug(f"Limiting to {args.max_games} games for testing (from {len(game_ids)} total)")
        game_ids = game_ids[:args.max_games]
    
    # Split games
    train_games, valid_games, test_games = split_games(game_ids, config)
    
    # Write split lists to disk
    with open(output_dir / 'train_games.json', 'w') as f:
        json.dump(train_games, f, indent=2)
    with open(output_dir / 'valid_games.json', 'w') as f:
        json.dump(valid_games, f, indent=2)
    with open(output_dir / 'test_games.json', 'w') as f:
        json.dump(test_games, f, indent=2)
    
    logger.debug(f"Wrote split lists to {output_dir}")
    logger.debug(f"Game splits: train={len(train_games)}, valid={len(valid_games)}, test={len(test_games)}")
    
    # Generate grid
    combinations = generate_grid(config)
    
    # Limit combinations if testing
    if args.max_combinations and len(combinations) > args.max_combinations:
        logger.debug(f"Limiting to {args.max_combinations} combinations for testing (from {len(combinations)} total)")
        combinations = combinations[:args.max_combinations]
    
    logger.debug("=" * 80)
    logger.debug(f"GRID SEARCH SUMMARY")
    logger.debug("=" * 80)
    logger.debug(f"  Parameter combinations: {len(combinations)}")
    logger.debug(f"  Total simulations: {len(combinations)} combos × 3 splits = {len(combinations) * 3} runs")
    logger.debug(f"  Games: train={len(train_games)}, valid={len(valid_games)}, test={len(test_games)}")
    logger.debug(f"  Workers: {config.workers}")
    logger.debug(f"  Estimated time: ~{len(combinations) * 3 * 2.5 / 60 / config.workers:.1f} minutes")
    logger.debug("=" * 80)
    logger.debug("Starting grid search (simulation logs suppressed for clarity)...")
    logger.debug("")
    
    # Prepare game splits dict
    game_splits = {
        'train': train_games,
        'valid': valid_games,
        'test': test_games
    }
    
    # Run grid search in parallel
    all_results = []
    completed = 0
    start_time = time.time()
    last_log_time = start_time
    
    # Suppress verbose simulation logs during grid search (unless --verbose is enabled)
    root_logger = logging.getLogger()
    original_root_level = root_logger.level
    
    # Only suppress logs if NOT in verbose mode
    if not args.verbose:
        root_logger.setLevel(logging.WARNING)  # Only WARNING and ERROR will show
        
        # Also suppress specific loggers that produce verbose output
        sim_logger = logging.getLogger('scripts.simulate_trading_strategy')
        original_sim_level = sim_logger.level if sim_logger.level != logging.NOTSET else logging.INFO
        sim_logger.setLevel(logging.ERROR)  # Only show errors
        
        # Suppress ALL loggers that might produce simulation/alignment logs
        original_logger_levels = {}
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if any(x in logger_name.lower() for x in ['simulate', 'align', 'timing']):
                log = logging.getLogger(logger_name)
                original_logger_levels[logger_name] = log.level
                if log.level == logging.NOTSET or log.level <= logging.INFO:
                    log.setLevel(logging.ERROR)  # Only show errors
    else:
        # Verbose mode: keep all logs enabled, just store original levels for cleanup
        sim_logger = logging.getLogger('scripts.simulate_trading_strategy')
        original_sim_level = sim_logger.level if sim_logger.level != logging.NOTSET else logging.INFO
        original_logger_levels = {}
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if any(x in logger_name.lower() for x in ['simulate', 'align', 'timing']):
                log = logging.getLogger(logger_name)
                original_logger_levels[logger_name] = log.level
    
    # Calculate total work units: each combination processes all games across all splits
    total_games = len(train_games) + len(valid_games) + len(test_games)
    total_work_units = len(combinations) * total_games
    
    # Create Rich Progress object for sticky progress bar
    # redirect_stdout=True and redirect_stderr=True capture any prints/warnings
    # that don't go through RichHandler and re-render them above the progress bar
    # This is critical for keeping the progress bar "sticky" at the bottom
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Grid search[/bold blue]"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("•"),
        TextColumn("[dim]{task.fields[current]}[/dim]"),
        console=console,
        transient=False,  # Keep it visible at the end
        refresh_per_second=4,  # Update 4 times per second (smooth but not too frequent)
        redirect_stdout=True,  # Capture stdout (prints, etc.) and render above progress bar
        redirect_stderr=True,  # Capture stderr (warnings, etc.) and render above progress bar
    )
    
    task_id = progress.add_task(
        "grid",
        total=total_work_units,
        current="starting..."
    )
    
    try:
        with progress:
            with ThreadPoolExecutor(max_workers=config.workers) as executor:
                futures = {
                    executor.submit(process_combination, combo, game_splits, config, dsn, progress, task_id): combo
                    for combo in combinations
                }
                
                for future in as_completed(futures):
                    combo = futures[future]
                    entry, exit = combo
                    
                    # Update current combo field when combination completes
                    progress.update(task_id, current=f"completed: entry={entry:.3f} exit={exit:.3f}")
                    
                    try:
                        result = future.result()
                        all_results.append(result)
                        completed += 1
                    except Exception as e:
                        logger.error(f"Error processing combination entry={entry:.3f}, exit={exit:.3f}: {e}")
            
            # Mark as complete
            progress.update(task_id, current="complete")
        
        total_time = time.time() - start_time
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✓ Completed all {len(combinations)} combinations in {total_time/60:.1f} minutes")
        logger.info("=" * 80)
    finally:
        # Restore original log levels
        try:
            root_logger.setLevel(original_root_level)
            sim_logger.setLevel(original_sim_level)
            # Restore logger levels
            for logger_name, level in original_logger_levels.items():
                log = logging.getLogger(logger_name)
                log.setLevel(level)
        except:
            pass  # Ignore errors during cleanup
    
    # Organize results by split
    results_by_split = {
        'train': [],
        'valid': [],
        'test': []
    }
    
    for result in all_results:
        for split_name in ['train', 'valid', 'test']:
            split_result = result[split_name].copy()
            split_result['entry_threshold'] = result['entry_threshold']
            split_result['exit_threshold'] = result['exit_threshold']
            results_by_split[split_name].append(split_result)
    
    # Write CSV files
    import csv
    for split_name in ['train', 'valid', 'test']:
        csv_path = output_dir / f'grid_results_{split_name}.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'entry_threshold', 'exit_threshold', 'net_profit_dollars', 'num_trades',
                'win_rate', 'avg_net_profit_per_trade', 'profit_factor', 'max_drawdown',
                'total_fees', 'avg_hold_time', 'is_valid'
            ])
            writer.writeheader()
            for row in results_by_split[split_name]:
                writer.writerow(row)
        logger.debug(f"Wrote {csv_path}")
    
    # Write JSON files with metadata
    git_hash = get_git_hash()
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for split_name in ['train', 'valid', 'test']:
        json_path = output_dir / f'grid_results_{split_name}.json'
        json_data = {
            'metadata': {
                'args': vars(args),
                'timestamp': timestamp,
                'git_hash': git_hash,
                'num_games': {
                    'train': len(train_games),
                    'valid': len(valid_games),
                    'test': len(test_games)
                },
                'num_combinations': len(combinations),
                'search_space': {
                    'entry_range': [config.entry_min, config.entry_max, config.entry_step],
                    'exit_range': [config.exit_min, config.exit_max, config.exit_step]
                },
                'season_or_list': season_or_list
            },
            'results': results_by_split[split_name]
        }
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        logger.debug(f"Wrote {json_path}")
    
    # Selection logic: rank on train, select best on valid from top N
    train_results = results_by_split['train']
    valid_results = results_by_split['valid']
    test_results = results_by_split['test']
    
    # Sort train results by net_profit_dollars (descending)
    train_results_sorted = sorted(train_results, key=lambda x: x['net_profit_dollars'], reverse=True)
    
    # Get top N from train
    top_n_train = train_results_sorted[:config.top_n]
    
    # Find best on valid among top N train
    best_combo = None
    best_valid_profit = float('-inf')
    
    for train_combo in top_n_train:
        entry = train_combo['entry_threshold']
        exit = train_combo['exit_threshold']
        
        # Find matching valid result
        for valid_combo in valid_results:
            if (abs(valid_combo['entry_threshold'] - entry) < 1e-6 and
                abs(valid_combo['exit_threshold'] - exit) < 1e-6):
                if valid_combo['net_profit_dollars'] > best_valid_profit:
                    best_valid_profit = valid_combo['net_profit_dollars']
                    best_combo = {
                        'entry_threshold': entry,
                        'exit_threshold': exit
                    }
                break
    
    if not best_combo:
        logger.warning("No valid combination found in top N train combos")
        # Fallback: use best train combo
        best_combo = {
            'entry_threshold': train_results_sorted[0]['entry_threshold'],
            'exit_threshold': train_results_sorted[0]['exit_threshold']
        }
    
    # Evaluate on test (one-time evaluation)
    test_combo_result = None
    for test_combo in test_results:
        if (abs(test_combo['entry_threshold'] - best_combo['entry_threshold']) < 1e-6 and
            abs(test_combo['exit_threshold'] - best_combo['exit_threshold']) < 1e-6):
            test_combo_result = test_combo
            break
    
    # Find train and valid results for chosen combo
    train_combo_result = None
    valid_combo_result = None
    
    for combo in train_results:
        if (abs(combo['entry_threshold'] - best_combo['entry_threshold']) < 1e-6 and
            abs(combo['exit_threshold'] - best_combo['exit_threshold']) < 1e-6):
            train_combo_result = combo
            break
    
    for combo in valid_results:
        if (abs(combo['entry_threshold'] - best_combo['entry_threshold']) < 1e-6 and
            abs(combo['exit_threshold'] - best_combo['exit_threshold']) < 1e-6):
            valid_combo_result = combo
            break
    
    # Write final selection
    final_selection = {
        'chosen_params': best_combo,
        'train_metrics': train_combo_result or {},
        'valid_metrics': valid_combo_result or {},
        'test_metrics': test_combo_result or {},
        'selection_method': f'best_on_valid_among_top_{config.top_n}_train',
        'top_n': config.top_n
    }
    
    selection_path = output_dir / 'final_selection.json'
    with open(selection_path, 'w') as f:
        json.dump(final_selection, f, indent=2)
    logger.debug(f"Wrote {selection_path}")
    
    # Save to cache if applicable
    if cache_key and CACHE_AVAILABLE:
        save_to_cache(cache_key, results_by_split, final_selection, 
                     train_games, valid_games, test_games,
                     combinations, config, season_or_list)
    
    logger.info(f"Grid search complete. Selected: entry={best_combo['entry_threshold']:.3f}, exit={best_combo['exit_threshold']:.3f}")
    test_profit = test_combo_result['net_profit_dollars'] if test_combo_result else 0.0
    logger.info(f"Results: Train=${train_combo_result['net_profit_dollars']:.2f}, Valid=${valid_combo_result['net_profit_dollars']:.2f}, Test=${test_profit:.2f}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

