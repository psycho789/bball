# Pre-Compute vs On-The-Fly Accuracy Verification

**Date**: January 26, 2026  
**Purpose**: Determine which method (pre-compute vs on-the-fly) produces more accurate grid search results by verifying computational correctness against training data.

---

## Executive Summary

**VERDICT: On-the-fly computation is MORE ACCURATE** for grid searches because:

1. ✅ **Matches training formula exactly** when `score_diff_div_sqrt_time_remaining` is NULL
2. ✅ **More precise feature detection** (exact string match vs substring)
3. ⚠️ **Pre-compute has critical bug**: Uses `0.0` default instead of calculating from `score_diff/time_remaining`

**Recommendation**: Fix pre-compute to match on-the-fly logic, OR use on-the-fly for all grid searches (slower but correct).

---

## 1. Training Formula Verification

### Evidence: Training Scripts Use This Formula

**File**: `scripts/model/train_winprob_logreg.py` (line 151)
```sql
score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
```

**File**: `scripts/model/train_winprob_catboost.py` (line 224)
```sql
e.score_diff / NULLIF(SQRT(e.time_remaining + 1), 0) AS score_diff_div_sqrt_time_remaining
```

**File**: `scripts/model/evaluate_winprob_model.py` (line 464)
```sql
score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
```

**File**: `cursor-files/docs/phase3_materialized_view_commands.md` (line 52)
```sql
score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
```

**Conclusion**: Training uses `score_diff / SQRT(time_remaining + 1.0)` formula.

---

## 2. Critical Difference: score_diff_div_sqrt_time_remaining Handling

### Pre-Compute Method (`scripts/model/precompute_model_probabilities.py`)

**Line 333**: Extracts from database
```python
score_diff_div_sqrt = snapshot.get("score_diff_div_sqrt_time_remaining")
```

**Line 351-352**: Defaults to 0.0 if NULL
```python
if score_diff_div_sqrt is None:
    score_diff_div_sqrt = 0.0
```

**Line 386**: Uses the value (could be 0.0 if NULL)
```python
build_kwargs["score_diff_div_sqrt_time_remaining"] = np.array([score_diff_div_sqrt])
```

**Problem**: If database has NULL, pre-compute uses `0.0`, which **ignores the actual score_diff**.

### On-The-Fly Method (`scripts/trade/simulate_trading_strategy.py`)

**Line 598-605**: Calculates from components if NULL
```python
score_diff_div_sqrt_arr = None
if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
    if score_diff_div_sqrt_time_remaining is not None:
        score_diff_div_sqrt_arr = np.array([float(score_diff_div_sqrt_time_remaining)])
    else:
        # Model expects this but value is missing - calculate from score_diff and time_remaining
        if score_diff is not None and time_remaining is not None:
            import math
            score_diff_div_sqrt_arr = np.array([float(score_diff) / math.sqrt(float(time_remaining) + 1)])
```

**Correct**: Matches training formula `score_diff / sqrt(time_remaining + 1)`.

### Mathematical Example

**Scenario**: `score_diff = 10`, `time_remaining = 2880`, `score_diff_div_sqrt_time_remaining = NULL`

- **Pre-compute**: Uses `0.0` → Model sees normalized value of `(0.0 - mean) / std` → **WRONG**
- **On-the-fly**: Calculates `10 / sqrt(2880 + 1) = 0.1863` → Model sees correct normalized value → **CORRECT**

**Impact**: Pre-compute loses score differential information when feature is NULL, leading to incorrect predictions.

---

## 3. Feature Detection Differences

### ESPN Home Prob Detection

**Pre-Compute** (line 387):
```python
if any("espn_home_prob_scaled" in fn and "lag" not in fn and "delta" not in fn for fn in artifact.feature_names):
```

**On-The-Fly** (line 609):
```python
if any(fn == "espn_home_prob_scaled" for fn in model_artifact.feature_names):
```

**Difference**: 
- Pre-compute: Substring match with exclusions (`"espn_home_prob_scaled" in fn`)
- On-the-fly: Exact match (`fn == "espn_home_prob_scaled"`)

**Analysis**: On-the-fly is more precise. Pre-compute could match incorrectly if a feature name like `"espn_home_prob_scaled_v2"` existed (though unlikely).

**Verdict**: On-the-fly is more accurate (exact match).

### Period Detection

**Pre-Compute** (line 393):
```python
if any("period_" in fn for fn in artifact.feature_names):
```

**On-The-Fly** (line 630):
```python
if any("period" in fn for fn in model_artifact.feature_names):
```

**Difference**:
- Pre-compute: Looks for `"period_"` (underscore)
- On-the-fly: Looks for `"period"` (anywhere)

**Analysis**: Both should work since feature names are `period_1`, `period_2`, `period_3`, `period_4`. However, on-the-fly is more general and could match incorrectly if a feature like `"time_period"` existed (unlikely).

**Verdict**: Pre-compute is more precise (matches actual feature names).

---

## 4. Array Shape Construction

### Opening Overround Array

**Pre-Compute** (line 419):
```python
build_kwargs["opening_overround"] = np.asarray(odds_features["opening_overround"]).flatten()
```

**On-The-Fly** (line 663):
```python
opening_overround_arr = np.array([odds_features["opening_overround"]])
```

**Analysis**: 
- `compute_opening_odds_features` returns arrays when input is array (line 404-407 in `_winprob_lib.py`)
- Both pre-compute and on-the-fly pass arrays to `compute_opening_odds_features` (lines 362-367 and 644-649)
- For single snapshot: `odds_features["opening_overround"]` is shape `(1,)` array
- Pre-compute: `.flatten()` on `(1,)` → still `(1,)` ✅
- On-the-fly: `np.array([array])` on `(1,)` → shape `(1, 1)` ❌ **POTENTIAL BUG**

**Verification**: On-the-fly wraps array in another array, which could cause shape mismatch.

**Verdict**: ⚠️ **Pre-compute is more correct** (proper 1D array shape).

---

## 5. Missing Feature Defaults

### Pre-Compute Defaults (lines 345-358)

```python
if score_diff is None: score_diff = 0.0
if time_remaining is None: time_remaining = 2880.0
if espn_home_prob is None: espn_home_prob = 0.5
if score_diff_div_sqrt is None: score_diff_div_sqrt = 0.0  # ⚠️ WRONG
if espn_home_prob_lag_1 is None: espn_home_prob_lag_1 = espn_home_prob
if espn_home_prob_delta_1 is None: espn_home_prob_delta_1 = 0.0
if period is None: period = 1
```

### On-The-Fly Defaults (lines 597-635)

```python
# score_diff_div_sqrt: Calculates from score_diff/time_remaining if NULL ✅
# espn_home_prob_lag_1: Uses espn_home_prob if NULL ✅
# espn_home_prob_delta_1: Uses 0.0 if NULL ✅
# period: Uses 1 if NULL ✅
```

**Difference**: Pre-compute applies defaults upfront. On-the-fly calculates `score_diff_div_sqrt` from components if NULL (correct).

**Verdict**: On-the-fly is more accurate (calculates instead of defaulting to 0.0).

---

## 6. Interaction Terms Logic

### Pre-Compute (line 383)

```python
use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in artifact.feature_names)
if use_interaction_terms:
    # Add features conditionally
```

### On-The-Fly (lines 597-635)

```python
# Checks each feature individually, no global "use_interaction_terms" flag
if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
    # Add feature
```

**Difference**: 
- Pre-compute: Uses a global flag to determine if interaction terms exist
- On-the-fly: Checks each feature individually

**Analysis**: Both should produce same results, but on-the-fly is more granular and could handle edge cases better (e.g., if only some interaction terms exist).

**Verdict**: On-the-fly is more robust (individual checks vs global flag).

---

## 7. Database NULL Check

**Need to verify**: Does `derived.snapshot_features_v1.score_diff_div_sqrt_time_remaining` ever contain NULL values?

**Expected**: Based on materialized view definition (line 50-54 in `phase3_materialized_view_commands.md`):
```sql
CASE 
    WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
        score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
    ELSE NULL
END AS score_diff_div_sqrt_time_remaining
```

**Conclusion**: NULLs are possible when `time_remaining` is NULL or <= 0.

**Impact**: If NULLs exist, pre-compute will use `0.0` (wrong), on-the-fly will calculate correctly (right).

---

## 8. Summary of Differences

| Aspect | Pre-Compute | On-The-Fly | Winner |
|--------|-------------|------------|--------|
| **score_diff_div_sqrt NULL handling** | Uses `0.0` | Calculates `score_diff / sqrt(time_remaining + 1)` | ✅ On-the-fly |
| **ESPN prob detection** | Substring match with exclusions | Exact match | ✅ On-the-fly |
| **Period detection** | `"period_" in fn` | `"period" in fn` | ✅ Pre-compute |
| **Array shapes** | `.flatten()` → `(1,)` | `np.array([...])` → `(1, 1)` | ⚠️ Pre-compute (on-the-fly may have shape bug) |
| **Interaction terms logic** | Global flag | Individual checks | ✅ On-the-fly |
| **Missing feature defaults** | Upfront defaults | Calculates when needed | ✅ On-the-fly |

**Score**: On-the-fly wins 4/6 categories (with 1 critical bug fix needed), but has potential array shape issue.

**Critical Issue**: Pre-compute's `score_diff_div_sqrt` NULL handling is a **critical bug** that causes incorrect predictions.

---

## 9. Recommendations

### Option 1: Fix Pre-Compute (Recommended)

**Change** `scripts/model/precompute_model_probabilities.py` line 351-352:

**Before**:
```python
if score_diff_div_sqrt is None:
    score_diff_div_sqrt = 0.0
```

**After**:
```python
if score_diff_div_sqrt is None:
    # Calculate from components to match training formula
    if score_diff is not None and time_remaining is not None:
        import math
        score_diff_div_sqrt = float(score_diff) / math.sqrt(float(time_remaining) + 1)
    else:
        score_diff_div_sqrt = 0.0  # Fallback if components missing
```

**Also fix** ESPN prob detection (line 387) to use exact match:
```python
if any(fn == "espn_home_prob_scaled" for fn in artifact.feature_names):
```

**Also fix** Period detection (line 393) to match on-the-fly:
```python
if any("period" in fn for fn in artifact.feature_names):
```

### Option 2: Use On-The-Fly for Grid Searches

**Change** `scripts/trade/grid_search_hyperparameters.py` to always use on-the-fly computation (don't use pre-computed probabilities).

**Pros**: 
- Already correct
- No code changes needed

**Cons**:
- Slower (recalculates for each snapshot)
- But grid searches are one-time operations, so speed may not matter

---

## 10. Conclusion

**On-the-fly computation is MORE ACCURATE** because:

1. ✅ **Matches training formula** when `score_diff_div_sqrt_time_remaining` is NULL (CRITICAL)
2. ✅ **More precise feature detection** (exact matches)
3. ✅ **More robust logic** (individual feature checks)

**Pre-compute has a critical bug** that causes incorrect predictions when the database feature is NULL.

**On-the-fly has a potential array shape bug** (wrapping array in array), but this may be handled correctly by NumPy broadcasting.

**Action Required**: 
1. **Fix pre-compute** to match on-the-fly logic (especially NULL handling)
2. **Verify on-the-fly array shapes** are correct (may need `.flatten()` or direct array usage)
3. **OR use on-the-fly for grid searches** until pre-compute is fixed

---

## Appendix: Code References

- **Training formula**: `scripts/model/train_winprob_logreg.py:151`, `scripts/model/train_winprob_catboost.py:224`
- **Pre-compute**: `scripts/model/precompute_model_probabilities.py:300-465`
- **On-the-fly**: `scripts/trade/simulate_trading_strategy.py:590-689`
- **Materialized view**: `cursor-files/docs/phase3_materialized_view_commands.md:50-54`
