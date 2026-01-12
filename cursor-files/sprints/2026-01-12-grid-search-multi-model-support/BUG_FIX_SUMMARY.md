# Bug Fix Summary - Model Scoring Dimension Mismatch

**Date**: January 12, 2026  
**Issue**: Model scoring fails with dimension mismatch error  
**Status**: ⚠️ **PARTIALLY FIXED** - Need to verify fix works

## Error Observed

```
WARNING | [ALIGN_DATA] Game 401809237: Error scoring model: matmul: Input operand 1 has a mismatch in its core dimension 0, with gufunc signature (n?,k),(k,m?)->(n?,m?) (size 13 is different from 12), using ESPN prob
```

**Interpretation**: Design matrix X has 13 columns, but model weights w has 12 elements (or vice versa).

## Root Cause Analysis

The model has **13 features** and **13 weights** (verified). The issue is that `build_design_matrix()` only adds optional features if they're provided (not None). 

**Problem**: If a model expects a feature but the value is None (missing from database), we don't pass it to `build_design_matrix()`, so it doesn't get added, resulting in fewer columns than expected.

**Example**:
- Model expects: 13 features (including `espn_home_prob_lag_1_scaled`)
- Database has: `espn_home_prob_lag_1 = None` (missing)
- We pass: `espn_home_prob_lag_1_arr = None` to `build_design_matrix()`
- `build_design_matrix()` doesn't add it (because it's None)
- Result: Design matrix has 12 columns, but model expects 13 → ERROR

## Fix Applied

**File**: `scripts/trade/simulate_trading_strategy.py`

**Changes**:
1. Added default values when model expects features but database values are None:
   - `espn_home_prob_lag_1`: Use current `espn_home_prob` as fallback
   - `espn_home_prob_delta_1`: Use 0.0 as fallback (no change)
   - `period`: Use 1 (first period) as fallback
   - `score_diff_div_sqrt_time_remaining`: Calculate from `score_diff` and `time_remaining` if missing

2. Fixed feature detection for `espn_home_prob`:
   - Changed from: `if any("espn_home_prob" in fn for fn in model_artifact.feature_names)`
   - Changed to: `if any(fn == "espn_home_prob_scaled" for fn in model_artifact.feature_names)`
   - This prevents matching `espn_home_prob_lag_1_scaled` and `espn_home_prob_delta_1_scaled`

3. Added validation before prediction:
   - Check design matrix shape matches expected feature count
   - Provide detailed error messages if mismatch
   - Fall back to ESPN probability on errors

## Code Changes

```python
# Before: Only passed features if not None
espn_prob_lag_1_arr = None
if espn_home_prob_lag_1 is not None:
    espn_prob_lag_1_arr = np.array([float(espn_home_prob_lag_1)])

# After: Always provide value if model expects it
espn_prob_lag_1_arr = None
if any("espn_home_prob_lag_1" in fn for fn in model_artifact.feature_names):
    if espn_home_prob_lag_1 is not None:
        espn_prob_lag_1_arr = np.array([float(espn_home_prob_lag_1)])
    else:
        # Model expects this but value is missing - use current espn_home_prob as fallback
        espn_prob_lag_1_arr = np.array([float(espn_home_prob)])
```

## Testing Required

After this fix, the grid search should:
1. ✅ Complete without dimension mismatch errors
2. ✅ Use model probabilities instead of ESPN probabilities
3. ✅ Handle missing features gracefully with defaults

**Next Steps**:
1. Re-run the grid search command that failed
2. Verify no dimension mismatch errors
3. Check that model probabilities are being used (not ESPN fallback)

## Additional Fixes Made

1. **Cache Key Bug**: Fixed missing `model_name` in CLI cache key generation
2. **API Path Bug**: Fixed missing model loading in `process_combination_with_pool()`
3. **Testing Checklist**: Updated to use correct file paths (`final_selection.json` instead of `results.json`)

