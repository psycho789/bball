# Grid Search Warning Log Improvements

**Date**: 2026-01-26  
**Purpose**: Identify areas in grid search code that could benefit from warning logs to ensure correctness

---

## Summary

After analyzing the grid search code, here are areas where additional warning logs would help detect issues early and ensure correctness:

1. **Grid Generation Validation** - Warn if no/few combinations generated
2. **Game Split Validation** - Warn if splits are too small or unbalanced
3. **Result Validation** - Warn if results look suspicious or inconsistent
4. **Selection Validation** - Warn if selection logic encounters edge cases
5. **Data Quality Thresholds** - Warn if skip rates are unusually high
6. **Performance Anomalies** - Warn if processing is unusually slow
7. **Model Validation** - Warn if model predictions seem off

---

## 1. Grid Generation Validation

### Current State
- `generate_grid()` only logs DEBUG message with count
- No validation if combinations list is empty or very small

### Recommended Warnings

**Location**: `generate_grid()` function (line ~237)

```python
# After generating combinations
if len(combinations) == 0:
    logger.warning(f"[GRID] No valid combinations generated! "
                   f"Entry range: [{config.entry_min}, {config.entry_max}], "
                   f"Exit range: [{config.exit_min}, {config.exit_max}]. "
                   f"Check that exit < entry constraint is satisfied.")

if len(combinations) < 10:
    logger.warning(f"[GRID] Very few combinations generated: {len(combinations)}. "
                   f"This may indicate grid parameters are too restrictive.")

# Warn if entry/exit ranges seem inverted
if config.entry_max <= config.exit_min:
    logger.warning(f"[GRID] Entry max ({config.entry_max}) <= Exit min ({config.exit_min}). "
                   f"No valid combinations possible (exit must be < entry).")
```

**Why**: Helps catch configuration errors early before running expensive simulations.

---

## 2. Game Split Validation

### Current State
- `split_games()` logs DEBUG with counts
- No validation of split sizes or balance

### Recommended Warnings

**Location**: `split_games()` function (line ~325)

```python
# After splitting
total = len(shuffled)
train_pct = len(train_games) / total * 100 if total > 0 else 0
valid_pct = len(valid_games) / total * 100 if total > 0 else 0
test_pct = len(test_games) / total * 100 if total > 0 else 0

# Warn if splits are too small
min_split_size = 10
if len(train_games) < min_split_size:
    logger.warning(f"[SPLIT] Train split is very small: {len(train_games)} games ({train_pct:.1f}%). "
                   f"Results may be unreliable. Minimum recommended: {min_split_size}")

if len(valid_games) < min_split_size:
    logger.warning(f"[SPLIT] Validation split is very small: {len(valid_games)} games ({valid_pct:.1f}%). "
                   f"Selection may be unreliable. Minimum recommended: {min_split_size}")

if len(test_games) < min_split_size:
    logger.warning(f"[SPLIT] Test split is very small: {len(test_games)} games ({test_pct:.1f}%). "
                   f"Final evaluation may be unreliable. Minimum recommended: {min_split_size}")

# Warn if splits are very unbalanced
expected_train_pct = config.train_ratio * 100
if abs(train_pct - expected_train_pct) > 5.0:
    logger.warning(f"[SPLIT] Train split differs significantly from expected: "
                   f"{train_pct:.1f}% actual vs {expected_train_pct:.1f}% expected. "
                   f"This may indicate rounding issues with small game counts.")
```

**Why**: Small or unbalanced splits can lead to unreliable results. Better to warn than silently proceed.

---

## 3. Result Validation

### Current State
- Results are aggregated without validation
- No checks for suspicious values (all zeros, extreme values, missing data)

### Recommended Warnings

**Location**: `run_simulation_for_games()` function (after aggregation, line ~496)

```python
# After calculating metrics, before returning
# Warn if no trades executed
if num_trades == 0:
    logger.warning(f"[RESULTS] No trades executed for entry={entry_threshold:.3f}, exit={exit_threshold:.3f}. "
                   f"Processed {games_processed} games with {total_data_points} data points. "
                   f"This may indicate thresholds are too restrictive.")

# Warn if all profits are zero (suspicious)
if num_trades > 0 and abs(net_profit_dollars) < 0.01:
    logger.warning(f"[RESULTS] All trades resulted in near-zero profit: ${net_profit_dollars:.2f} "
                   f"({num_trades} trades). This may indicate a calculation issue.")

# Warn if profit is extremely high (possible calculation error)
if abs(net_profit_dollars) > 10000:
    logger.warning(f"[RESULTS] Extremely high profit detected: ${net_profit_dollars:.2f} "
                   f"({num_trades} trades). Please verify calculation is correct.")

# Warn if win rate is suspicious
if num_trades > 10:
    if win_rate > 0.95:
        logger.warning(f"[RESULTS] Suspiciously high win rate: {win_rate:.1%} ({len(winning_trades)}/{num_trades}). "
                       f"This may indicate a calculation issue.")
    elif win_rate < 0.05:
        logger.warning(f"[RESULTS] Suspiciously low win rate: {win_rate:.1%} ({len(winning_trades)}/{num_trades}). "
                       f"This may indicate a calculation issue.")

# Warn if profit factor is extreme
if profit_factor > 100:
    logger.warning(f"[RESULTS] Extremely high profit factor: {profit_factor:.2f}. "
                   f"This may indicate a calculation issue.")
```

**Why**: Catches calculation errors, data issues, or unrealistic results early.

---

## 4. Selection Validation

### Current State
- Selection logic has one warning (line 1285) for missing valid combo
- No validation of final selection quality

### Recommended Warnings

**Location**: `main()` function, after selection (line ~1315)

```python
# After finding best_combo and results
# Warn if test result is missing
if test_combo_result is None:
    logger.warning(f"[SELECTION] Test result not found for selected combo "
                   f"(entry={best_combo['entry_threshold']:.3f}, exit={best_combo['exit_threshold']:.3f}). "
                   f"Cannot evaluate final performance.")

# Warn if train/valid/test results are inconsistent
if train_combo_result and valid_combo_result and test_combo_result:
    train_profit = train_combo_result['net_profit_dollars']
    valid_profit = valid_combo_result['net_profit_dollars']
    test_profit = test_combo_result['net_profit_dollars']
    
    # Check for large discrepancies (possible overfitting)
    train_valid_diff = abs(train_profit - valid_profit)
    valid_test_diff = abs(valid_profit - test_profit)
    
    if train_valid_diff > 1000:
        logger.warning(f"[SELECTION] Large train/valid discrepancy: "
                       f"Train=${train_profit:.2f}, Valid=${valid_profit:.2f} "
                       f"(diff=${train_valid_diff:.2f}). Possible overfitting.")
    
    if valid_test_diff > 1000:
        logger.warning(f"[SELECTION] Large valid/test discrepancy: "
                       f"Valid=${valid_profit:.2f}, Test=${test_profit:.2f} "
                       f"(diff=${valid_test_diff:.2f}). Selection may not generalize.")
    
    # Warn if test is much worse than train/valid
    if test_profit < train_profit * 0.5 and test_profit < valid_profit * 0.5:
        logger.warning(f"[SELECTION] Test performance is significantly worse than train/valid: "
                       f"Train=${train_profit:.2f}, Valid=${valid_profit:.2f}, Test=${test_profit:.2f}. "
                       f"Possible overfitting or data leakage.")

# Warn if selected combo has very few trades
if train_combo_result and train_combo_result.get('num_trades', 0) < config.min_trade_count:
    logger.warning(f"[SELECTION] Selected combo has fewer trades than minimum: "
                   f"{train_combo_result.get('num_trades', 0)} < {config.min_trade_count}. "
                   f"Results may be unreliable.")

# Warn if fallback was used (already exists, but could be more detailed)
if not best_combo:  # This case already has a warning, but could add:
    logger.warning(f"[SELECTION] Fallback to best train combo used. "
                   f"Top {config.top_n} train combos had no matching valid results. "
                   f"This may indicate a data consistency issue.")
```

**Why**: Detects overfitting, data leakage, or selection logic issues.

---

## 5. Data Quality Thresholds

### Current State
- Data quality summary is logged at INFO level (line 1355)
- No warnings for high skip rates

### Recommended Warnings

**Location**: `main()` function, data quality summary (line ~1353)

```python
# After calculating skip_rate
if total_games_processed + total_games_skipped > 0:
    skip_rate = total_games_skipped / (total_games_processed + total_games_skipped) * 100
    
    # Warn if skip rate is high
    if skip_rate > 20.0:
        logger.warning(f"[DATA_QUALITY] High skip rate: {skip_rate:.1f}% "
                       f"({total_games_skipped} skipped / {total_games_processed + total_games_skipped} total). "
                       f"This may indicate data quality issues.")
    
    # Warn if very few games processed
    if total_games_processed < 50:
        logger.warning(f"[DATA_QUALITY] Very few games processed: {total_games_processed}. "
                       f"Results may be unreliable.")
    
    # Warn if no data points
    if total_data_points == 0:
        logger.warning(f"[DATA_QUALITY] No data points processed across all games. "
                       f"This indicates a serious data issue.")
    elif total_data_points < 1000:
        logger.warning(f"[DATA_QUALITY] Very few data points: {total_data_points}. "
                       f"Results may be unreliable.")
```

**Why**: High skip rates or low data volumes indicate potential data quality issues.

---

## 6. Performance Anomalies

### Current State
- Performance is logged at DEBUG level
- No warnings for unusually slow processing

### Recommended Warnings

**Location**: `run_simulation_for_games()` function (line ~456)

```python
# After calculating avg_game_time
if game_times:
    avg_game_time = sum(game_times) / len(game_times)
    max_game_time = max(game_times)
    
    # Warn if average is very slow
    if avg_game_time > 5.0:  # 5 seconds per game is slow
        logger.warning(f"[PERF] Slow average game processing: {avg_game_time:.2f}s/game. "
                       f"This may indicate database or model performance issues.")
    
    # Warn if any game is extremely slow
    if max_game_time > 10.0:
        logger.warning(f"[PERF] Some games took very long to process: max={max_game_time:.2f}s. "
                       f"This may indicate database query issues.")
```

**Location**: `main()` function, after completion (line ~1161)

```python
# After calculating total_time
expected_time_minutes = len(combinations) * 3 * 2.5 / 60 / config.workers
actual_time_minutes = total_time / 60

# Warn if much slower than expected
if actual_time_minutes > expected_time_minutes * 2:
    logger.warning(f"[PERF] Grid search took much longer than expected: "
                   f"{actual_time_minutes:.1f} min actual vs {expected_time_minutes:.1f} min expected. "
                   f"This may indicate performance issues.")
```

**Why**: Helps identify performance regressions or database issues.

---

## 7. Model Validation

### Current State
- Model loading raises exceptions on errors
- No validation of model predictions

### Recommended Warnings

**Location**: `load_model_artifact()` function (line ~195)

```python
# After loading artifact
if artifact:
    # Check if model file is very old (possible stale model)
    model_age_days = (time.time() - model_path.stat().st_mtime) / 86400
    if model_age_days > 90:
        logger.warning(f"[MODEL] Model file is old: {model_age_days:.0f} days. "
                       f"Consider retraining: {model_path}")
    
    # Validate artifact structure (if possible)
    if hasattr(artifact, 'model') and artifact.model is None:
        logger.warning(f"[MODEL] Model artifact loaded but model object is None. "
                       f"This may indicate a corrupted model file.")
```

**Location**: `run_simulation_for_games()` function, when using model (line ~384)

```python
# In the game processing loop, after getting aligned_data
if model_artifact and aligned_data:
    # Check if model predictions seem reasonable
    # (This would require checking predictions, which may be expensive)
    # Could sample a few predictions and check if they're in [0,1] range
    # This is optional and may be too expensive for verbose logging
    pass
```

**Why**: Detects stale or corrupted models before they affect results.

---

## 8. Result Consistency Checks

### Current State
- Results are written without consistency validation
- No checks across splits

### Recommended Warnings

**Location**: `main()` function, after organizing results (line ~1207)

```python
# After organizing results_by_split
# Check that all splits have same number of combinations
train_count = len(results_by_split['train'])
valid_count = len(results_by_split['valid'])
test_count = len(results_by_split['test'])

if train_count != valid_count or valid_count != test_count:
    logger.warning(f"[CONSISTENCY] Mismatched result counts: "
                   f"train={train_count}, valid={valid_count}, test={test_count}. "
                   f"This may indicate some combinations failed to process.")

# Check for missing combinations
if train_count < len(combinations):
    missing = len(combinations) - train_count
    logger.warning(f"[CONSISTENCY] Missing {missing} train results out of {len(combinations)} combinations. "
                   f"Some combinations may have failed.")

# Check for duplicate combinations
train_combos = {(r['entry_threshold'], r['exit_threshold']) for r in results_by_split['train']}
if len(train_combos) < train_count:
    logger.warning(f"[CONSISTENCY] Duplicate combinations found in train results. "
                   f"Expected {train_count} unique, found {len(train_combos)}.")
```

**Why**: Detects processing failures or data consistency issues.

---

## 9. Cache Validation

### Current State
- Cache errors are logged as warnings (line 717, 766)
- No validation of cached data integrity

### Recommended Warnings

**Location**: `load_from_cache()` function (line ~622)

```python
# After loading cached_data
if cached_data:
    # Validate cached data structure
    required_keys = ['training_results', 'validation_results', 'test_results', 'final_selection']
    missing_keys = [k for k in required_keys if k not in cached_data]
    if missing_keys:
        logger.warning(f"[CACHE] Cached data missing required keys: {missing_keys}. "
                       f"Cache may be corrupted. Will run fresh grid search.")
        return False
    
    # Validate result counts match metadata
    metadata = cached_data.get('metadata', {})
    expected_combos = metadata.get('num_combinations', 0)
    actual_valid_combos = len(cached_data.get('validation_results', []))
    
    if expected_combos > 0 and actual_valid_combos != expected_combos:
        logger.warning(f"[CACHE] Cached result count mismatch: "
                       f"expected {expected_combos} combinations, found {actual_valid_combos} in validation results. "
                       f"Cache may be incomplete. Will run fresh grid search.")
        return False
```

**Why**: Detects corrupted or incomplete cache data.

---

## 10. Summary of Recommended Warnings

| Area | Current State | Recommended Warnings | Priority |
|------|---------------|---------------------|----------|
| Grid Generation | DEBUG only | Warn if no/few combos, inverted ranges | High |
| Game Splits | DEBUG only | Warn if splits too small/unbalanced | High |
| Result Validation | None | Warn on suspicious values (zeros, extremes) | High |
| Selection Logic | 1 warning | Warn on missing test, large discrepancies | High |
| Data Quality | INFO summary | Warn on high skip rates, low volumes | Medium |
| Performance | DEBUG only | Warn on unusually slow processing | Medium |
| Model Validation | Exceptions only | Warn on stale/corrupted models | Medium |
| Result Consistency | None | Warn on mismatched counts, duplicates | Medium |
| Cache Validation | Basic warnings | Warn on corrupted/incomplete cache | Low |

---

## Implementation Priority

### High Priority (Implement First)
1. **Grid Generation Validation** - Catches config errors early
2. **Game Split Validation** - Prevents unreliable results
3. **Result Validation** - Catches calculation errors
4. **Selection Validation** - Detects overfitting/data leakage

### Medium Priority
5. **Data Quality Thresholds** - Helps identify data issues
6. **Performance Anomalies** - Identifies performance regressions
7. **Model Validation** - Detects stale models

### Low Priority
8. **Result Consistency** - Nice to have, but errors should be rare
9. **Cache Validation** - Already has basic warnings

---

## Notes

- All warnings should use `logger.warning()` (not `logger.error()` or `logger.debug()`)
- Warnings should be actionable - tell the user what might be wrong and what to check
- Consider adding a `--strict` flag that treats warnings as errors (for CI/CD)
- Some warnings may be too verbose for production - consider making them conditional on `--verbose` flag

---

**Analysis Completed**: 2026-01-26
