# Odds Interaction Terms Analysis

**Date**: 2026-01-22  
**Context**: Data scientist friend's advice on adding odds/time interaction terms

## Friend's Advice Summary

From Discord conversation (1/13/26):

1. **"add the odds data as a parameter"** - Add odds as a column/feature in the model
2. **"we may need interaction terms bc we're really interested in the relation between the terms"** - Need interaction terms
3. **"like the odds mean very little with 2 minutes in the game"** - Odds become less informative as time progresses
4. **"something like odds divided by time or score divided by time"** - Explicit interaction terms like `odds/time_remaining`, `score/time_remaining`
5. **"drop the logistic there's no real point in running it until we add interaction terms"** - Don't use logistic regression until interaction terms are added
6. **"catboost will still improve once we add interaction terms but it can figure some of it out"** - CatBoost can find some interactions automatically but explicit ones help

## Current Implementation Status

### ✅ What We're Already Doing

1. **Odds Data IS Included**:
   - `opening_moneyline_home`, `opening_moneyline_away` (raw decimal odds)
   - `opening_spread`, `opening_total` (spread and total lines)
   - Engineered features: `opening_prob_home_fair`, `opening_overround`
   - Presence flags: `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`

   **Location**: `scripts/model/train_winprob_catboost.py` lines 195-198, 223-226, 337-349

2. **Score/Time Interaction EXISTS**:
   - `score_diff_div_sqrt_time_remaining` = `score_diff / sqrt(time_remaining + 1)`
   - This captures how score differential matters more as time runs out
   
   **Location**: `scripts/model/train_winprob_catboost.py` line 184

3. **CatBoost IS Being Used**:
   - Primary model is CatBoost (not logistic regression)
   - CatBoost can automatically discover some interaction terms through tree splits
   
   **Location**: `scripts/model/train_winprob_catboost.py` lines 618-628

4. **Interaction Terms Feature Flag**:
   - `--use-interaction-terms` flag exists (default: True)
   - Can enable/disable interaction terms
   
   **Location**: `scripts/model/train_winprob_catboost.py` line 88

### ❌ What's Missing

1. **NO Odds/Time Interaction Terms**:
   - We have `opening_prob_home_fair` but no `opening_prob_home_fair / time_remaining`
   - We have `opening_spread` but no `opening_spread / time_remaining`
   - We have `opening_total` but no `opening_total / time_remaining`
   
   **Why This Matters**: Opening odds are most informative at the start of the game. With 2 minutes left, the current score matters much more than pre-game odds. An interaction term like `odds / time_remaining` would decay the importance of odds as time progresses.

2. **Logistic Regression Still Exists**:
   - `scripts/model/train_winprob_logreg.py` still exists
   - Friend says to drop it until interaction terms are added
   - **However**: We're using CatBoost as primary model, so this is less critical

## The Gap: Missing Odds/Time Interactions

### Current Feature Set

**Base Features**:
- `point_differential` (score_diff)
- `time_remaining_regulation`
- `possession` (one-hot encoded)

**Existing Interaction Terms**:
- `score_diff_div_sqrt_time_remaining` = `score_diff / sqrt(time_remaining + 1)`

**Odds Features** (NO time interactions):
- `opening_prob_home_fair`
- `opening_overround`
- `opening_spread`
- `opening_total`
- `has_opening_moneyline`
- `has_opening_spread`
- `has_opening_total`

### What We Should Add

**Proposed Odds/Time Interaction Terms**:

1. **`opening_prob_home_fair_div_time_remaining`** = `opening_prob_home_fair / (time_remaining + 1)`
   - Decays odds importance as time progresses
   - Higher value early in game, approaches 0 as time runs out

2. **`opening_spread_div_time_remaining`** = `opening_spread / (time_remaining + 1)`
   - Spread matters more early in game
   - Less relevant with 2 minutes left

3. **`opening_total_div_time_remaining`** = `opening_total / (time_remaining + 1)`
   - Total matters more early in game

**Alternative Formulations** (to test):
- `opening_prob_home_fair * time_remaining` (multiplicative, grows over time - probably wrong direction)
- `opening_prob_home_fair / sqrt(time_remaining + 1)` (similar to score_diff interaction)
- `opening_prob_home_fair * log(time_remaining + 1)` (logarithmic decay)

## Implementation Plan (VERIFIED)

### Data Flow Verification

**Order of Operations** (verified from code):
1. SQL query loads raw data: `opening_moneyline_home`, `opening_spread`, `opening_total`, `time_remaining_regulation` (lines 195-198, 223-226)
2. Python computes engineered odds features: `opening_prob_home_fair`, `opening_overround`, etc. (lines 337-349)
3. **NEW**: Compute odds/time interactions AFTER odds engineering (must happen here)
4. Normalize interaction terms and store params (lines 510-539)
5. Build design matrix with normalized features (lines 550-587)
6. Train model

### Step 1: Compute Odds/Time Interactions in Python (After Odds Engineering)

**File**: `scripts/model/train_winprob_catboost.py`

**Location**: After line 349 (where `opening_prob_home_fair`, `opening_overround`, etc. are added to DataFrame)

**VERIFIED**: This is the correct location because:
- `opening_prob_home_fair` is computed from raw odds in Python (line 345)
- `time_remaining_regulation` already exists from SQL query (line 213)
- Must compute interactions AFTER odds features exist

**Add**:
```python
# Compute odds/time interaction terms (after odds features are engineered)
if use_interaction_terms:
    if 'opening_prob_home_fair' in df.columns and 'time_remaining_regulation' in df.columns:
        # Handle NaN: if odds missing or time missing, set to 0
        df['opening_prob_home_fair_div_time_remaining'] = (
            df['opening_prob_home_fair'] / (df['time_remaining_regulation'] + 1)
        )
        df['opening_prob_home_fair_div_time_remaining'] = df['opening_prob_home_fair_div_time_remaining'].fillna(0.0)
    
    if 'opening_spread' in df.columns and 'time_remaining_regulation' in df.columns:
        df['opening_spread_div_time_remaining'] = (
            df['opening_spread'] / (df['time_remaining_regulation'] + 1)
        )
        df['opening_spread_div_time_remaining'] = df['opening_spread_div_time_remaining'].fillna(0.0)
    
    if 'opening_total' in df.columns and 'time_remaining_regulation' in df.columns:
        df['opening_total_div_time_remaining'] = (
            df['opening_total'] / (df['time_remaining_regulation'] + 1)
        )
        df['opening_total_div_time_remaining'] = df['opening_total_div_time_remaining'].fillna(0.0)
```

**Note**: Only compute if `use_interaction_terms` is True (matches pattern of other interaction terms)

### Step 2: Add Normalization Parameters for Interaction Terms

**File**: `scripts/model/train_winprob_catboost.py`

**Location**: Lines 510-539 (where other interaction terms are normalized)

**VERIFIED**: This follows the exact same pattern as `score_diff_div_sqrt_time_remaining` normalization

**Add** (after line 539, before `preprocess = PreprocessParams(...)`):
```python
        # Normalize odds/time interaction terms (only if use_interaction_terms is True)
        if "opening_prob_home_fair_div_time_remaining" in df.columns:
            opht_train = df.loc[train_mask, "opening_prob_home_fair_div_time_remaining"].astype(float).to_numpy()
            opht_train = opht_train[~np.isnan(opht_train)]  # Filter NaNs (shouldn't be any after fillna, but safe)
            if len(opht_train) > 0:
                interaction_params["opening_prob_home_fair_div_time_rem_mean"] = float(np.mean(opht_train))
                interaction_params["opening_prob_home_fair_div_time_rem_std"] = float(np.std(opht_train, ddof=0)) or 1.0
        
        if "opening_spread_div_time_remaining" in df.columns:
            ost_train = df.loc[train_mask, "opening_spread_div_time_remaining"].astype(float).to_numpy()
            ost_train = ost_train[~np.isnan(ost_train)]
            if len(ost_train) > 0:
                interaction_params["opening_spread_div_time_rem_mean"] = float(np.mean(ost_train))
                interaction_params["opening_spread_div_time_rem_std"] = float(np.std(ost_train, ddof=0)) or 1.0
        
        if "opening_total_div_time_remaining" in df.columns:
            ott_train = df.loc[train_mask, "opening_total_div_time_remaining"].astype(float).to_numpy()
            ott_train = ott_train[~np.isnan(ott_train)]
            if len(ott_train) > 0:
                interaction_params["opening_total_div_time_rem_mean"] = float(np.mean(ott_train))
                interaction_params["opening_total_div_time_rem_std"] = float(np.std(ott_train, ddof=0)) or 1.0
```

### Step 3: Add Fields to PreprocessParams Dataclass

**File**: `scripts/lib/_winprob_lib.py`

**Location**: Lines 104-121 (PreprocessParams dataclass definition)

**VERIFIED**: This is a frozen dataclass, so fields must be added with default None values (like other interaction terms)

**Add** (after line 118, before closing parenthesis):
```python
    opening_prob_home_fair_div_time_rem_mean: float | None = None
    opening_prob_home_fair_div_time_rem_std: float | None = None
    opening_spread_div_time_rem_mean: float | None = None
    opening_spread_div_time_rem_std: float | None = None
    opening_total_div_time_rem_mean: float | None = None
    opening_total_div_time_rem_std: float | None = None
```

### Step 4: Add Parameters to build_design_matrix Function

**File**: `scripts/lib/_winprob_lib.py`

**Location**: Lines 321-341 (function signature)

**VERIFIED**: Must add as optional parameters (like other interaction terms)

**Add** (after line 332, in the interaction terms section):
```python
    # Odds/time interaction terms (optional)
    opening_prob_home_fair_div_time_remaining: np.ndarray | None = None,
    opening_spread_div_time_remaining: np.ndarray | None = None,
    opening_total_div_time_remaining: np.ndarray | None = None,
```

### Step 5: Add Normalization Logic in build_design_matrix

**File**: `scripts/lib/_winprob_lib.py`

**Location**: Lines 377-418 (where interaction terms are normalized and added to features)

**VERIFIED**: Follows exact same pattern as `score_diff_div_sqrt_time_remaining` (lines 378-385)

**Add** (after line 418, before odds features section):
```python
    # Add odds/time interaction terms if provided
    if opening_prob_home_fair_div_time_remaining is not None:
        if preprocess.opening_prob_home_fair_div_time_rem_mean is None or preprocess.opening_prob_home_fair_div_time_rem_std is None:
            raise ValueError("opening_prob_home_fair_div_time_remaining provided but normalization params missing")
        std = preprocess.opening_prob_home_fair_div_time_rem_std if preprocess.opening_prob_home_fair_div_time_rem_std != 0.0 else 1.0
        scaled = (opening_prob_home_fair_div_time_remaining.astype(np.float64) - preprocess.opening_prob_home_fair_div_time_rem_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if opening_spread_div_time_remaining is not None:
        if preprocess.opening_spread_div_time_rem_mean is None or preprocess.opening_spread_div_time_rem_std is None:
            raise ValueError("opening_spread_div_time_remaining provided but normalization params missing")
        std = preprocess.opening_spread_div_time_rem_std if preprocess.opening_spread_div_time_rem_std != 0.0 else 1.0
        scaled = (opening_spread_div_time_remaining.astype(np.float64) - preprocess.opening_spread_div_time_rem_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if opening_total_div_time_remaining is not None:
        if preprocess.opening_total_div_time_rem_mean is None or preprocess.opening_total_div_time_rem_std is None:
            raise ValueError("opening_total_div_time_remaining provided but normalization params missing")
        std = preprocess.opening_total_div_time_rem_std if preprocess.opening_total_div_time_rem_std != 0.0 else 1.0
        scaled = (opening_total_div_time_remaining.astype(np.float64) - preprocess.opening_total_div_time_rem_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
```

### Step 6: Add to Training Matrix Building

**File**: `scripts/model/train_winprob_catboost.py`

**Location**: Lines 557-568 (where interaction terms are added to build_matrix_kwargs)

**VERIFIED**: Must add here, inside the `if use_interaction_terms:` block

**Add** (after line 568, before closing the interaction terms block):
```python
        # Add odds/time interaction terms
        if "opening_prob_home_fair_div_time_remaining" in df.columns:
            build_matrix_kwargs["opening_prob_home_fair_div_time_remaining"] = df.loc[train_mask, "opening_prob_home_fair_div_time_remaining"].astype(float).to_numpy()
        if "opening_spread_div_time_remaining" in df.columns:
            build_matrix_kwargs["opening_spread_div_time_remaining"] = df.loc[train_mask, "opening_spread_div_time_remaining"].astype(float).to_numpy()
        if "opening_total_div_time_remaining" in df.columns:
            build_matrix_kwargs["opening_total_div_time_remaining"] = df.loc[train_mask, "opening_total_div_time_remaining"].astype(float).to_numpy()
```

### Step 7: Add to Calibration Matrix Building

**File**: `scripts/model/train_winprob_catboost.py`

**Location**: Lines 640-651 (where interaction terms are added to calib_matrix_kwargs)

**VERIFIED**: Must add here for calibration set, same pattern as training set

**Add** (after line 651, before closing the interaction terms block):
```python
            # Add odds/time interaction terms for calibration
            if "opening_prob_home_fair_div_time_remaining" in df.columns:
                calib_matrix_kwargs["opening_prob_home_fair_div_time_remaining"] = df.loc[calib_mask, "opening_prob_home_fair_div_time_remaining"].astype(float).to_numpy()
            if "opening_spread_div_time_remaining" in df.columns:
                calib_matrix_kwargs["opening_spread_div_time_remaining"] = df.loc[calib_mask, "opening_spread_div_time_remaining"].astype(float).to_numpy()
            if "opening_total_div_time_remaining" in df.columns:
                calib_matrix_kwargs["opening_total_div_time_remaining"] = df.loc[calib_mask, "opening_total_div_time_remaining"].astype(float).to_numpy()
```

### Step 8: Add Feature Names

**File**: `scripts/model/train_winprob_catboost.py`

**Location**: Lines 599-610 (where interaction term feature names are added)

**VERIFIED**: Must add here, inside the `if use_interaction_terms:` block

**Add** (after line 610, before closing the interaction terms block):
```python
        # Add odds/time interaction term feature names
        if "opening_prob_home_fair_div_time_remaining" in df.columns:
            feature_names.append("opening_prob_home_fair_div_time_remaining_scaled")
        if "opening_spread_div_time_remaining" in df.columns:
            feature_names.append("opening_spread_div_time_remaining_scaled")
        if "opening_total_div_time_remaining" in df.columns:
            feature_names.append("opening_total_div_time_remaining_scaled")
```

## Critical Verification Points

✅ **Order of operations verified**: Odds features computed first (line 345), then interactions can be computed  
✅ **Normalization pattern verified**: Follows exact same pattern as `score_diff_div_sqrt_time_remaining`  
✅ **NaN handling verified**: Uses `fillna(0.0)` and `np.nan_to_num()` like other interaction terms  
✅ **Conditional logic verified**: Only computed if `use_interaction_terms` is True  
✅ **Calibration set verified**: Must add to both training and calibration matrix building  
✅ **Feature names verified**: Must match the scaled feature names used in design matrix

## Expected Impact

### Why This Should Help

1. **Temporal Decay**: Opening odds become less relevant as the game progresses. A 10-point spread matters a lot with 40 minutes left, but very little with 2 minutes left.

2. **Explicit Signal**: While CatBoost can discover some interactions, explicit odds/time terms give the model a clear signal about how odds importance should decay over time.

3. **Better Calibration**: The model should better understand when to rely on odds vs. current game state.

### Potential Issues to Watch

1. **Division by Zero**: Need to handle `time_remaining = 0` cases (use `time_remaining + 1`)

2. **NaN Handling**: Odds might be missing for some games - need to fill appropriately

3. **Feature Scaling**: These interaction terms will have different scales - need proper normalization

4. **Overfitting Risk**: Adding more features increases model complexity - monitor validation performance

## Testing Plan

1. **Baseline**: Train model with current features (no odds/time interactions)
2. **With Interactions**: Train model with odds/time interactions added
3. **Compare**:
   - Validation AUC
   - Calibration curves
   - Feature importance (CatBoost can show which features matter most)
   - Performance by time bucket (early game vs. late game)

## Verification Summary

### ✅ Code Flow Verified

1. **Data Loading Order**:
   - SQL query loads raw odds: `opening_moneyline_home`, `opening_spread`, `opening_total` (lines 195-198)
   - Python computes engineered features: `opening_prob_home_fair` (line 345)
   - **Interactions must be computed AFTER line 349** (when odds features exist)

2. **Normalization Pattern**:
   - Interaction terms normalized in lines 510-539
   - Stored in `interaction_params` dict
   - Passed to `PreprocessParams` dataclass (line 541)
   - **Follows exact same pattern as `score_diff_div_sqrt_time_remaining`**

3. **Design Matrix Building**:
   - Parameters added to function signature (lines 321-341)
   - Normalization applied in function body (lines 377-418)
   - Features stacked in canonical order (line 470)
   - **Must add normalization logic BEFORE odds features section**

4. **Training vs Calibration**:
   - Both training (lines 550-587) and calibration (lines 633-670) sets need updates
   - **Must add interaction terms to both `build_matrix_kwargs` and `calib_matrix_kwargs`**

5. **Feature Names**:
   - Added to `feature_names` list (lines 599-614)
   - Used in artifact metadata (line 716)
   - **Must match scaled feature names used in design matrix**

### ⚠️ Potential Issues Identified

1. **NaN Handling**: 
   - Odds may be missing (NaN) for some games
   - Time remaining should always exist (filtered in SQL)
   - **Solution**: Use `fillna(0.0)` after division, then `np.nan_to_num()` in normalization

2. **Division by Zero**:
   - `time_remaining` can be 0 (end of game)
   - **Solution**: Use `(time_remaining + 1)` to avoid division by zero

3. **Feature Ordering**:
   - Odds/time interactions should come AFTER other interaction terms but BEFORE odds features
   - **Verified**: Add after line 418 (other interactions) but before line 420 (odds features)

4. **Conditional Logic**:
   - Only compute if `use_interaction_terms` is True
   - **Verified**: Wrap in `if use_interaction_terms:` block (matches pattern)

5. **PreprocessParams Dataclass**:
   - Frozen dataclass - fields must have default values
   - **Verified**: Use `float | None = None` like other interaction terms

### ✅ Implementation Plan Verified

All 8 steps have been verified against actual code:
- ✅ Step 1: Correct location (after line 349)
- ✅ Step 2: Correct pattern (matches existing interaction normalization)
- ✅ Step 3: Correct dataclass structure (frozen with defaults)
- ✅ Step 4: Correct function signature (optional parameters)
- ✅ Step 5: Correct normalization logic (matches existing pattern)
- ✅ Step 6: Correct training matrix (inside interaction terms block)
- ✅ Step 7: Correct calibration matrix (same pattern as training)
- ✅ Step 8: Correct feature names (matches scaled names)

## Summary

**Current State**:
- ✅ Odds data included
- ✅ Score/time interaction exists (`score_diff_div_sqrt_time_remaining`)
- ✅ CatBoost being used
- ❌ **Missing odds/time interactions**

**Friend's Point**: 
- Odds matter less as time progresses
- Need explicit `odds / time_remaining` terms
- CatBoost can find some interactions but explicit ones help

**Action Required**:
- Add `opening_prob_home_fair / time_remaining` interaction terms
- Add `opening_spread / time_remaining` interaction terms  
- Add `opening_total / time_remaining` interaction terms
- Test impact on model performance

**Implementation Status**: ✅ **Plan verified and ready to implement**

**Note on Logistic Regression**: Friend says to drop it, but we're already using CatBoost as primary model. The logistic regression script (`train_winprob_logreg.py`) exists but isn't the main training path. We could deprecate it or keep it for baseline comparisons.
