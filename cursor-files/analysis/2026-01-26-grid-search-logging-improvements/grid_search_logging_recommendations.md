# Grid Search Logging Improvements - Recommendations

**Date**: 2026-01-26  
**Status**: 📋 Recommendations for implementation

---

## Executive Summary

This document outlines recommendations for enhancing logging in the grid search process, including:
1. **Additional areas to log** for better observability and debugging
2. **Enhanced verbose logging** for the `--verbose` flag
3. **Performance metrics** to track execution efficiency
4. **Data quality metrics** to identify systemic issues

---

## Current Logging State

### What's Currently Logged

**Grid Search Level**:
- ✅ Basic progress (combinations completed)
- ✅ Final results summary
- ✅ Cache hit/miss
- ✅ Error messages for failed combinations
- ⚠️ Limited per-combination metrics
- ⚠️ No timing/performance metrics
- ⚠️ No aggregated data quality stats

**Simulation Level** (suppressed unless `--verbose`):
- ✅ Data quality warnings (`[ALIGN_DATA]`, `[P&L]`, `[SIMULATION]`, `[END_OF_GAME]`)
- ✅ Debug logs for entry/exit decisions
- ⚠️ Timing logs are commented out
- ⚠️ No aggregated metrics per game/split

---

## Recommended Additional Logging Areas

### 1. Performance & Timing Metrics

**Why**: Understand bottlenecks, optimize worker count, estimate completion times

**What to Log**:
- **Per-combination timing**: Time to process each combination (all 3 splits)
- **Per-split timing**: Time for train/valid/test splits separately
- **Per-game timing**: Average time per game (for capacity planning)
- **Query timing**: Database query times (currently commented out)
- **Model scoring timing**: Time spent on model predictions (if using model)
- **Total elapsed time**: With breakdown by phase

**Implementation**:
```python
# In process_combination()
combo_start = time.time()
# ... process splits ...
combo_elapsed = time.time() - combo_start
logger.debug(f"[PERF] Combination entry={entry:.3f} exit={exit:.3f}: {combo_elapsed:.2f}s "
             f"(train={train_time:.2f}s, valid={valid_time:.2f}s, test={test_time:.2f}s)")

# In run_simulation_for_games()
game_times = []
for game_id in game_ids:
    game_start = time.time()
    # ... process game ...
    game_elapsed = time.time() - game_start
    game_times.append(game_elapsed)
    if args.verbose:
        logger.debug(f"[PERF] Game {game_id[:8]}: {game_elapsed:.2f}s, {len(aligned_data)} points, {len(results.get('trades', []))} trades")

avg_game_time = sum(game_times) / len(game_times) if game_times else 0
logger.debug(f"[PERF] Split {split_name}: {len(game_ids)} games, avg {avg_game_time:.2f}s/game, total {sum(game_times):.2f}s")
```

**Verbose Mode**: Log per-game timing, per-query timing

---

### 2. Data Quality Aggregation

**Why**: Identify systemic data issues across games, not just individual warnings

**What to Log**:
- **Games skipped**: Count and percentage of games with no aligned data
- **Data quality summary**: Aggregated counts of warnings per split
  - `[ALIGN_DATA]` warnings count
  - `[P&L]` invalid prices count
  - `[END_OF_GAME]` forced closes count
  - `[SIMULATION]` no trades count
- **Average data points per game**: Track data completeness
- **Price source usage**: Aggregate `used_home_prices` vs `used_away_fallback_prices`
- **Model fallback rate**: How often model predictions fail and ESPN prob is used

**Implementation**:
```python
# In run_simulation_for_games()
split_stats = {
    'games_processed': 0,
    'games_skipped': 0,
    'total_trades': 0,
    'total_data_points': 0,
    'align_data_warnings': 0,
    'pl_warnings': 0,
    'end_of_game_warnings': 0,
    'no_trades_count': 0,
    'used_home_prices': 0,
    'used_away_prices': 0,
}

for game_id in game_ids:
    # ... process game ...
    split_stats['games_processed'] += 1
    split_stats['total_data_points'] += len(aligned_data)
    split_stats['total_trades'] += len(results.get('trades', []))
    # ... collect warnings from results or log parsing ...

# At end of split
logger.info(f"[DATA_QUALITY] Split {split_name}: "
            f"{split_stats['games_processed']} games, "
            f"{split_stats['games_skipped']} skipped, "
            f"{split_stats['total_data_points']} data points, "
            f"{split_stats['total_trades']} trades, "
            f"{split_stats['align_data_warnings']} align warnings, "
            f"{split_stats['pl_warnings']} P&L warnings")
```

**Verbose Mode**: Log per-game data quality metrics

---

### 3. Worker Utilization & Load Balancing

**Why**: Optimize parallel execution, identify bottlenecks

**What to Log**:
- **Worker idle time**: Track when workers are waiting
- **Combination processing distribution**: Which combinations take longest
- **Per-worker throughput**: Trades/games processed per worker
- **Load imbalance**: Variance in worker completion times

**Implementation**:
```python
# In main() after ThreadPoolExecutor
worker_stats = {}
for future in as_completed(futures):
    worker_id = future._thread_id if hasattr(future, '_thread_id') else 'unknown'
    if worker_id not in worker_stats:
        worker_stats[worker_id] = {'combinations': 0, 'total_time': 0.0}
    worker_stats[worker_id]['combinations'] += 1
    # ... track timing ...

# At end
logger.debug(f"[WORKERS] Worker utilization: {len(worker_stats)} workers, "
             f"avg {sum(s['combinations'] for s in worker_stats.values()) / len(worker_stats):.1f} combos/worker")
```

**Verbose Mode**: Log per-worker stats

---

### 4. Cache Performance

**Why**: Understand cache effectiveness, optimize cache strategy

**What to Log**:
- **Cache hit rate**: Percentage of cache hits vs misses
- **Cache key generation time**: Overhead of cache operations
- **Cache size**: Memory footprint of cached results
- **Cache save time**: Time to write cache to disk

**Implementation**:
```python
cache_stats = {'hits': 0, 'misses': 0, 'saves': 0}

# In load_from_cache()
if cached_data:
    cache_stats['hits'] += 1
    logger.debug(f"[CACHE] HIT: {cache_key[:32]}... (load time: {load_time:.3f}s)")
else:
    cache_stats['misses'] += 1
    logger.debug(f"[CACHE] MISS: {cache_key[:32]}...")

# In save_to_cache()
cache_stats['saves'] += 1
logger.debug(f"[CACHE] SAVE: {cache_key[:32]}... (save time: {save_time:.3f}s)")

# At end
total = cache_stats['hits'] + cache_stats['misses']
hit_rate = cache_stats['hits'] / total * 100 if total > 0 else 0
logger.info(f"[CACHE] Performance: {cache_stats['hits']} hits, {cache_stats['misses']} misses ({hit_rate:.1f}% hit rate)")
```

**Verbose Mode**: Log every cache operation with timing

---

### 5. Model Usage Statistics

**Why**: Track model performance, identify model-related issues

**What to Log** (when using models):
- **Model load time**: Time to load artifact
- **Model scoring time**: Total time spent on predictions
- **Model fallback rate**: How often ESPN prob is used instead
- **Model prediction distribution**: Min/max/avg predicted probabilities
- **Model errors**: Count of prediction errors

**Implementation**:
```python
model_stats = {
    'load_time': 0.0,
    'total_scoring_time': 0.0,
    'predictions_made': 0,
    'fallbacks_to_espn': 0,
    'errors': 0,
}

# In load_model_artifact()
load_start = time.time()
artifact = load_artifact(model_path)
model_stats['load_time'] = time.time() - load_start
logger.debug(f"[MODEL] Loaded {model_name} in {model_stats['load_time']:.2f}s")

# In get_aligned_data() when scoring
scoring_start = time.time()
try:
    prediction = model_artifact.predict(...)
    model_stats['predictions_made'] += 1
except Exception as e:
    model_stats['errors'] += 1
    model_stats['fallbacks_to_espn'] += 1
model_stats['total_scoring_time'] += time.time() - scoring_start

# At end
if model_stats['predictions_made'] > 0:
    avg_time = model_stats['total_scoring_time'] / model_stats['predictions_made']
    logger.info(f"[MODEL] Stats: {model_stats['predictions_made']} predictions, "
                f"{model_stats['fallbacks_to_espn']} fallbacks, "
                f"{model_stats['errors']} errors, "
                f"avg {avg_time*1000:.1f}ms/prediction")
```

**Verbose Mode**: Log per-prediction timing and fallback reasons

---

### 6. Progress Milestones

**Why**: Better visibility into long-running grid searches

**What to Log**:
- **Every N combinations**: Progress update with ETA
- **Every N games**: Progress update for large game sets
- **Phase transitions**: When moving from train → valid → test
- **Checkpoint saves**: When intermediate results are saved

**Implementation**:
```python
# In main() during grid search
milestone_interval = max(10, len(combinations) // 20)  # Log every 5% or every 10, whichever is larger

for future in as_completed(futures):
    completed += 1
    
    # Log milestone
    if completed % milestone_interval == 0 or completed == len(combinations):
        elapsed = time.time() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        remaining = (len(combinations) - completed) / rate if rate > 0 else 0
        logger.info(f"[PROGRESS] {completed}/{len(combinations)} combinations "
                    f"({completed/len(combinations)*100:.1f}%) - "
                    f"ETA: {remaining/60:.1f} minutes")
```

**Verbose Mode**: Log every combination completion

---

### 7. Error Aggregation

**Why**: Identify patterns in failures, not just individual errors

**What to Log**:
- **Error types**: Categorize errors (database, model, data quality, etc.)
- **Error frequency**: Count of each error type
- **Failed combinations**: List of combinations that failed
- **Failed games**: Games that consistently fail
- **Error recovery**: How many errors were handled gracefully

**Implementation**:
```python
error_stats = {
    'database_errors': 0,
    'model_errors': 0,
    'data_quality_errors': 0,
    'unknown_errors': 0,
    'failed_combinations': [],
    'failed_games': set(),
}

# In process_combination()
try:
    result = future.result()
except psycopg.Error as e:
    error_stats['database_errors'] += 1
    error_stats['failed_combinations'].append((entry, exit))
except ValueError as e:
    if 'model' in str(e).lower():
        error_stats['model_errors'] += 1
    else:
        error_stats['data_quality_errors'] += 1
except Exception as e:
    error_stats['unknown_errors'] += 1

# At end
logger.warning(f"[ERRORS] Summary: {sum(error_stats.values())} total errors - "
               f"DB: {error_stats['database_errors']}, "
               f"Model: {error_stats['model_errors']}, "
               f"Data: {error_stats['data_quality_errors']}, "
               f"Unknown: {error_stats['unknown_errors']}")
if error_stats['failed_combinations']:
    logger.warning(f"[ERRORS] Failed combinations: {error_stats['failed_combinations'][:10]}...")
```

**Verbose Mode**: Log every error with full traceback

---

### 8. Memory Usage (Optional)

**Why**: Identify memory leaks, optimize for large grid searches

**What to Log** (if memory is a concern):
- **Peak memory usage**: Maximum memory during execution
- **Memory per combination**: Track memory growth
- **Garbage collection stats**: If using GC monitoring

**Implementation** (requires `psutil`):
```python
import psutil
import os

process = psutil.Process(os.getpid())
peak_memory_mb = process.memory_info().rss / 1024 / 1024

logger.debug(f"[MEMORY] Peak memory usage: {peak_memory_mb:.1f} MB")
```

**Verbose Mode**: Log memory usage periodically

---

## Enhanced Verbose Mode Recommendations

### Current Verbose Mode Behavior

- Sets logging level to `DEBUG`
- Keeps simulation logs enabled (doesn't suppress them)
- Still minimal detailed metrics

### Recommended Enhancements

1. **Per-Game Detailed Logging**:
   ```python
   if args.verbose:
       logger.debug(f"[GAME] {game_id}: {len(aligned_data)} points, "
                    f"{len(results['trades'])} trades, "
                    f"profit=${results['total_profit_cents']/100:.2f}, "
                    f"win_rate={results.get('win_rate', 0):.1%}")
   ```

2. **Per-Combination Summary**:
   ```python
   if args.verbose:
       logger.info(f"[COMBO] entry={entry:.3f} exit={exit:.3f}: "
                   f"train=${train_result['net_profit_dollars']:.2f} "
                   f"({train_result['num_trades']} trades), "
                   f"valid=${valid_result['net_profit_dollars']:.2f} "
                   f"({valid_result['num_trades']} trades), "
                   f"test=${test_result['net_profit_dollars']:.2f} "
                   f"({test_result['num_trades']} trades)")
   ```

3. **Query Timing Details**:
   ```python
   # Uncomment and enhance timing logs in get_aligned_data()
   if args.verbose:
       logger.debug(f"[TIMING] {game_id} - game_info_sql: {query_elapsed:.3f}s")
       logger.debug(f"[TIMING] {game_id} - canonical_sql: {query_elapsed:.3f}s, rows={len(canonical_rows)}")
   ```

4. **Entry/Exit Decision Details**:
   ```python
   # Already logged at DEBUG level, but ensure it's visible in verbose mode
   # Current: logger.debug(f"[ENTRY] Entry blocked...")
   # Keep as-is, just ensure verbose mode shows it
   ```

5. **Model Prediction Details** (if using models):
   ```python
   if args.verbose and model_artifact:
       logger.debug(f"[MODEL] {game_id} snapshot {snapshot_ts}: "
                    f"ESPN={espn_prob:.3f}, Model={model_prob:.3f}, "
                    f"Final={final_prob:.3f}, Features={feature_summary}")
   ```

6. **Data Quality Per Game**:
   ```python
   if args.verbose:
       logger.debug(f"[DATA] {game_id}: "
                    f"{rows_with_home_mid} home prices, "
                    f"{rows_with_away_mid} away prices, "
                    f"{filtered_missing_espn} missing ESPN, "
                    f"{filtered_missing_kalshi} missing Kalshi, "
                    f"{filtered_out_of_range} out of range")
   ```

---

## Implementation Priority

### High Priority (Immediate Value)

1. ✅ **Performance & Timing Metrics** - Essential for optimization
2. ✅ **Data Quality Aggregation** - Identifies systemic issues
3. ✅ **Progress Milestones** - Better UX for long runs
4. ✅ **Enhanced Verbose Mode** - Better debugging experience

### Medium Priority (Nice to Have)

5. ⚠️ **Cache Performance** - Useful for cache optimization
6. ⚠️ **Error Aggregation** - Helps identify patterns
7. ⚠️ **Model Usage Statistics** - Important when using models

### Low Priority (Optional)

8. ⚠️ **Worker Utilization** - Only if parallelization issues arise
9. ⚠️ **Memory Usage** - Only if memory is a concern

---

## Log Format Recommendations

### Structured Logging

Use consistent prefixes for easy filtering:
- `[PERF]` - Performance/timing metrics
- `[DATA_QUALITY]` - Data quality aggregations
- `[CACHE]` - Cache operations
- `[MODEL]` - Model-related metrics
- `[PROGRESS]` - Progress milestones
- `[ERRORS]` - Error aggregations
- `[WORKERS]` - Worker utilization
- `[MEMORY]` - Memory usage

### Log Levels

- **INFO**: Summary metrics, milestones, important events
- **DEBUG**: Detailed per-game/combination metrics (verbose mode)
- **WARNING**: Errors, data quality issues, performance concerns
- **ERROR**: Critical failures

---

## Example Enhanced Log Output

### Normal Mode (INFO)
```
[INFO] Output directory: data/grid_search/abc123...
[INFO] Logging to: data/grid_search/abc123.../grid_search.log
[INFO] Starting grid search...
[PROGRESS] 50/342 combinations (14.6%) - ETA: 12.3 minutes
[PROGRESS] 100/342 combinations (29.2%) - ETA: 10.1 minutes
[DATA_QUALITY] Split train: 245 games, 12 skipped, 125000 data points, 3420 trades, 45 align warnings
[INFO] ✓ Completed all 342 combinations in 15.2 minutes
[INFO] Grid search complete. Selected: entry=0.050, exit=0.010
```

### Verbose Mode (DEBUG)
```
[DEBUG] Generated 342 valid combinations from 19 entry values and 11 exit values
[DEBUG] Split 500 games: train=350, valid=75, test=75
[DEBUG] Loaded model artifact: catboost_odds_platt_v2 (shared across all 342 combinations)
[DEBUG] [PERF] Game 40180998: 0.45s, 487 points, 12 trades
[DEBUG] [PERF] Game 40180999: 0.52s, 512 points, 15 trades
[DEBUG] [DATA] 40180998: 487 home prices, 485 away prices, 2 missing ESPN, 0 missing Kalshi, 1 out of range
[DEBUG] [COMBO] entry=0.050 exit=0.010: train=$125.50 (342 trades), valid=$28.30 (75 trades), test=$31.20 (78 trades)
[DEBUG] [PERF] Combination entry=0.050 exit=0.010: 12.3s (train=8.1s, valid=2.1s, test=2.1s)
[INFO] [PROGRESS] 50/342 combinations (14.6%) - ETA: 12.3 minutes
```

---

## Next Steps

1. **Review recommendations** - Prioritize based on needs
2. **Implement high-priority items** - Start with performance and data quality
3. **Test verbose mode** - Ensure it provides useful debugging info
4. **Update documentation** - Document new log formats and what they mean
5. **Monitor log file sizes** - Ensure verbose mode doesn't create huge logs

---

**Status**: 📋 Ready for implementation  
**Priority**: High (improves observability and debugging significantly)
