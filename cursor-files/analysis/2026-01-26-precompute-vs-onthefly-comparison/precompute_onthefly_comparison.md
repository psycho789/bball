# Pre-Compute vs On-The-Fly Computation: Method Comparison

**Date:** 2026-01-26  
**Purpose:** Verify that pre-computed probabilities and on-the-fly computation use identical methods and produce identical results

## Executive Summary

**⚠️ CRITICAL FINDINGS:** There are **several differences** between the two methods that could lead to **different results**:

1. **Interaction Terms Logic:** Pre-compute uses a `use_interaction_terms` flag; on-the-fly checks features individually
2. **score_diff_div_sqrt Handling:** Different default/calculation logic
3. **Opening Odds Array Shape:** Different array construction methods
4. **ESPN Prob Check:** Different pattern matching (substring vs exact match)
5. **Period Check:** Different pattern matching (`period_` vs `period`)

**Status:** ⚠️ **METHODS ARE NOT IDENTICAL - VERIFICATION NEEDED**

## Detailed Comparison

### 1. Interaction Terms Logic

**Pre-Compute (precompute_model_probabilities.py:383):**
```python
use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in artifact.feature_names)
if use_interaction_terms:
    # Add interaction terms
```

**On-The-Fly (simulate_trading_strategy.py:597-635):**
```python
# No use_interaction_terms flag - directly checks each feature individually
if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
    # Add score_diff_div_sqrt
if any(fn == "espn_home_prob_scaled" for fn in model_artifact.feature_names):
    # Add espn_home_prob
if any("espn_home_prob_lag_1" in fn for fn in model_artifact.feature_names):
    # Add lag_1
if any("period" in fn for fn in model_artifact.feature_names):
    # Add period
```

**Difference:** Pre-compute requires BOTH "scaled" AND one of the interaction terms. On-the-fly checks each feature independently.

**Impact:** For models with interaction terms, both should work, but the logic is different.

### 2. ESPN Prob Check

**Pre-Compute (line 387):**
```python
if any("espn_home_prob_scaled" in fn and "lag" not in fn and "delta" not in fn for fn in artifact.feature_names):
    build_kwargs["espn_home_prob"] = np.array([espn_home_prob])
```

**On-The-Fly (line 609):**
```python
if any(fn == "espn_home_prob_scaled" for fn in model_artifact.feature_names):
    espn_prob_arr = np.array([float(espn_home_prob)])
```

**Difference:** Pre-compute uses substring match with exclusions; on-the-fly uses exact match.

**Impact:** Both should work for `espn_home_prob_scaled`, but pre-compute is more defensive (excludes lag/delta variants).

### 3. Period Feature Check

**Pre-Compute (line 393):**
```python
if any("period_" in fn for fn in artifact.feature_names):
    build_kwargs["period"] = np.array([period])
```

**On-The-Fly (line 630):**
```python
if any("period" in fn for fn in model_artifact.feature_names):
    period_arr = [int(period_val)]
```

**Difference:** Pre-compute checks for `period_` (with underscore); on-the-fly checks for `period` (without underscore).

**Impact:** Both match `period_1`, `period_2`, etc., but pre-compute is more specific. However, if there were a feature named just `period`, on-the-fly would match it but pre-compute wouldn't.

### 4. score_diff_div_sqrt Handling

**Pre-Compute (line 352):**
```python
if score_diff_div_sqrt is None:
    score_diff_div_sqrt = 0.0  # Default to 0.0
# Later (line 386):
build_kwargs["score_diff_div_sqrt_time_remaining"] = np.array([score_diff_div_sqrt])
```

**On-The-Fly (lines 598-605):**
```python
if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
    if score_diff_div_sqrt_time_remaining is not None:
        score_diff_div_sqrt_arr = np.array([float(score_diff_div_sqrt_time_remaining)])
    else:
        # Calculate from score_diff and time_remaining
        if score_diff is not None and time_remaining is not None:
            import math
            score_diff_div_sqrt_arr = np.array([float(score_diff) / math.sqrt(float(time_remaining) + 1)])
```

**Difference:** 
- Pre-compute: Uses 0.0 as default if missing
- On-the-fly: Calculates from score_diff/time_remaining if missing, or leaves as None

**Impact:** ⚠️ **CRITICAL** - This could produce different results! If `score_diff_div_sqrt_time_remaining` is NULL in database:
- Pre-compute: Uses 0.0
- On-the-fly: Calculates `score_diff / sqrt(time_remaining + 1)`

### 5. Opening Odds Array Shape

**Pre-Compute (line 419):**
```python
build_kwargs["opening_overround"] = np.asarray(odds_features["opening_overround"]).flatten()
```

**On-The-Fly (line 663):**
```python
opening_overround_arr = np.array([odds_features["opening_overround"]])
```

**Difference:** Pre-compute uses `.flatten()`, on-the-fly wraps in `np.array([...])`.

**Impact:** Both should produce same shape for single value, but different construction methods.

### 6. Opening Prob Home Fair Array Shape

**Pre-Compute (line 459):**
```python
opening_prob_home_fair=np.asarray(odds_features["opening_prob_home_fair"]).flatten()
```

**On-The-Fly (line 667):**
```python
opening_prob_home_fair_arr = np.array([odds_features["opening_prob_home_fair"]])
```

**Difference:** Same as #5 - different array construction.

### 7. Missing Feature Defaults

**Pre-Compute (lines 345-358):**
```python
if score_diff is None: score_diff = 0.0
if time_remaining is None: time_remaining = 2880.0
if espn_home_prob is None: espn_home_prob = 0.5
if score_diff_div_sqrt is None: score_diff_div_sqrt = 0.0
if espn_home_prob_lag_1 is None: espn_home_prob_lag_1 = espn_home_prob
if espn_home_prob_delta_1 is None: espn_home_prob_delta_1 = 0.0
if period is None: period = 1
```

**On-The-Fly (lines 587-635):**
```python
# No defaults - uses None if missing, then calculates or uses fallbacks conditionally
if score_diff is None or time_remaining is None:
    logger.warning(...)  # Uses ESPN prob instead
# score_diff_div_sqrt: Calculates if missing (line 605)
# espn_prob_lag_1: Uses current espn_home_prob if missing (line 619)
# espn_prob_delta_1: Uses 0.0 if missing (line 627)
# period: Uses 1 if missing (line 635)
```

**Difference:** Pre-compute applies defaults upfront; on-the-fly handles missing values conditionally.

**Impact:** Could lead to different behavior when features are missing.

## Verification Test Needed

To verify if these differences matter, we need to:

1. **Run both methods on the same snapshot** and compare outputs
2. **Check if score_diff_div_sqrt is ever NULL** in the database
3. **Verify array shapes** are identical after construction
4. **Test with missing features** to see if defaults match

## Recommendations

### ⚠️ High Priority Fixes

1. **Align score_diff_div_sqrt handling:**
   - Both should use the same default/calculation logic
   - Recommendation: Use calculation method (on-the-fly) in both places

2. **Align interaction terms logic:**
   - Both should use the same feature detection method
   - Recommendation: Use individual feature checks (on-the-fly) in both places for clarity

3. **Align array construction:**
   - Both should use the same array construction method
   - Recommendation: Use consistent method (e.g., `np.asarray(...).flatten()`)

### 📊 Medium Priority

4. **Standardize feature name checks:**
   - Use consistent pattern matching (exact match vs substring)
   - Recommendation: Use exact match for clarity

5. **Document expected behavior:**
   - Clearly document what happens when features are missing
   - Ensure both methods handle missing features identically

## Conclusion

**The methods are NOT identical** and could produce different results, especially when:
- `score_diff_div_sqrt_time_remaining` is NULL in database
- Features are missing
- Array shapes differ

**Action Required:** Fix the differences to ensure both methods produce identical results, then verify with a test comparison.
