# Opening Odds Features Collinearity Analysis

**Date**: Sat Jan 24 01:17:06 PST 2026  
**Status**: Draft  
**Author**: Analysis based on data scientist feedback  
**Version**: v1.0  
**Purpose**: Analyze collinearity concerns with 4 opening odds features and evaluate alternatives

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (code refs, commands + verbatim output, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and exact artifacts analyzed
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: Use PostgreSQL via `DATABASE_URL` for data analysis

---

## Executive Summary

### Key Findings

- **Finding 1**: Current implementation uses 4 opening odds features: `opening_overround` (continuous), `has_opening_moneyline`, `has_opening_spread`, `has_opening_total` (binary flags)
- **Finding 2**: ✅ **VERIFIED**: `has_opening_moneyline` is **perfectly redundant** with `opening_overround` - both are set based on the same `valid_ml` condition (code: `scripts/lib/_winprob_lib.py:392-396`)
- **Finding 3**: Data scientist identified potential collinearity risk: the three `has_*` binary flags are likely highly correlated (if moneyline exists, spread/total likely exist too) - **needs data verification**

### Critical Issues Identified

- **Issue 1**: ✅ **CONFIRMED**: **Perfect Redundancy** - `has_opening_moneyline` is perfectly redundant with `opening_overround` (both derived from same `valid_ml` condition). This feature adds zero information and should be removed immediately.
- **Issue 2**: **Potential Multicollinearity** - The remaining `has_opening_spread` and `has_opening_total` binary flags may be highly correlated with each other and with odds availability patterns, introducing collinearity that can destabilize model coefficients

### Recommended Actions

- **Action 1**: **Priority: Critical** - **Remove `has_opening_moneyline` immediately** - Verified as perfectly redundant with `opening_overround` (zero information content)
- **Action 2**: **Priority: High** - Analyze actual correlation patterns between `has_opening_spread` and `has_opening_total` in training data
- **Action 3**: **Priority: High** - Evaluate alternatives: single feature (`opening_overround` only), or reduced set (`opening_overround` + one `has_*` flag)
- **Action 4**: **Priority: Medium** - Consider "closing line / pre-tip line" as alternative to opening odds (requires data availability verification for multiple time windows)

### Success Metrics

- **Metric 1**: Correlation matrix showing relationships between the 4 features
- **Metric 2**: Model performance comparison (current 4 features vs. alternatives)
- **Metric 3**: Feature importance analysis to identify which feature(s) are most predictive

### What the Data Scientist Means

**"Why did you add 4 opening odds?"**
- Concerned about feature count and potential redundancy

**"Using 1 or averaging the 4 would be best"**
- Suggests reducing to single feature or creating composite
- **Note**: Literal averaging doesn't make statistical sense (mixing binary 0/1 with continuous overround), but the intent is clear: reduce feature count

**"Use the best one or average"**
- Recommends selecting most predictive feature or creating meaningful composite

**"Using 4 introduces collinearity which can be very bad"**
- **Correct concern**: Multicollinearity can destabilize models
- **Verified**: At least one feature (`has_opening_moneyline`) is perfectly redundant

**"Maybe use median"**
- Alternative suggestion, but same issue as averaging (mixing binary and continuous)

**"Also we might want to use 'odds last minute' instead of opening odds"**
- Suggests using more recent odds (right before game) instead of stale opening odds
- Requires timestamped odds data (needs verification)

---

---

## Problem Statement

### Current Situation

The v2 odds-enabled models use **4 opening odds features**:

1. **`opening_overround`**: Continuous value representing bookmaker margin
   - Computed as: `(1/odds_home + 1/odds_away) - 1.0`
   - Only exists when both moneyline odds are present and valid (> 1.0)
   - May be `NaN` if odds are missing

2. **`has_opening_moneyline`**: Binary flag (1 if valid moneyline odds exist, 0 otherwise)
   - Set to 1 when both `opening_moneyline_home` and `opening_moneyline_away` are present and > 1.0

3. **`has_opening_spread`**: Binary flag (1 if spread line exists, 0 otherwise)
   - Set to 1 when `opening_spread` is not `NaN`

4. **`has_opening_total`**: Binary flag (1 if total/over-under exists, 0 otherwise)
   - Set to 1 when `opening_total` is not `NaN`

**Current Implementation**:
- **File**: `scripts/lib/_winprob_lib.py:306-427` (`compute_opening_odds_features()`)
- **File**: `scripts/lib/_winprob_lib.py:430-593` (`build_design_matrix()`)
- All 4 features are added to the design matrix when opening odds are enabled

### Data Scientist Feedback

**Concern**: "using 4 introduces collinearity which can be very bad"

**Suggestions**:
1. Use 1 feature instead of 4
2. Average the 4 features
3. Use the best one
4. Use median
5. Consider "closing line / pre-tip line" instead of opening odds (test multiple time windows: 5/15/60 minutes)

### Pain Points

- **Multicollinearity Risk**: Highly correlated features can cause:
  - Unstable coefficient estimates
  - Reduced model interpretability
  - Increased variance in predictions
  - Difficulty determining individual feature importance

- **Redundancy**: `has_opening_moneyline` may be redundant with `opening_overround`:
  - If `opening_overround` is not `NaN`, then `has_opening_moneyline` must be 1
  - The flag adds no new information beyond what overround already conveys

- **Binary Flag Correlation**: The three `has_*` flags are likely correlated:
  - If a game has opening odds, it likely has all three markets (moneyline, spread, total)
  - This creates a pattern where flags are often all 0 or all 1 together

### Business Impact

- **Model Performance Impact**: Collinearity may reduce model generalization and increase overfitting risk
- **Interpretability Impact**: Difficult to understand which odds features are actually predictive
- **Maintenance Impact**: More features increase complexity without clear benefit

### Success Criteria

- **Criterion 1**: Quantify actual correlation between the 4 features in training data
- **Criterion 2**: Identify which feature(s) are most predictive (feature importance analysis)
- **Criterion 3**: Evaluate alternatives (single feature, averaged, median) and compare performance
- **Criterion 4**: Assess feasibility of "odds last minute" alternative

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 
  - `scripts/lib/_winprob_lib.py` (feature computation and design matrix)
  - `scripts/model/train_winprob_catboost.py` (training script)
  - Model artifacts (retraining required)
- **Estimated Effort**: 8-16 hours (data analysis + code changes + retraining + evaluation)
- **Technical Complexity**: Medium (requires data analysis, code refactoring, model retraining)
- **Risk Level**: Medium (changes to feature set require model retraining and validation)

**Sprint Scope Recommendation**: Single Sprint
- **Rationale**: Well-defined scope (analyze collinearity, implement alternative, retrain, evaluate)
- **Recommended Approach**: 
  - Phase 1: Data analysis (correlation, feature importance)
  - Phase 2: Implement alternative feature set
  - Phase 3: Retrain models and evaluate performance

**Dependency Analysis**:
- Requires access to training data for correlation analysis
- Model retraining required (30-60 minutes per model)
- Evaluation on test set required

---

## Understanding the Data Scientist's Feedback

### What "Collinearity" Means

**Collinearity** (or multicollinearity) occurs when two or more features are highly correlated. This causes problems:

1. **Unstable Coefficients**: Small changes in data can cause large changes in feature weights
2. **Reduced Interpretability**: Hard to determine which feature is actually predictive
3. **Increased Variance**: Model predictions become less reliable
4. **Overfitting Risk**: Model may memorize noise instead of learning signal

### Why "4 Opening Odds" is Problematic

The data scientist is concerned because:
- **4 features** may contain redundant information
- **Binary flags** (`has_*`) are likely correlated (if one market exists, others likely exist too)
- **Redundancy** wastes model capacity and increases overfitting risk

### What "Use 1 or Average the 4" Means

**Option 1: Use 1 Feature**
- Pick the most predictive feature (likely `opening_overround`)
- Eliminates collinearity completely
- Simplest solution

**Option 2: Average the 4**
- **Problem**: This doesn't make statistical sense
  - `opening_overround` is continuous (e.g., 0.05)
  - `has_*` flags are binary (0 or 1)
  - Averaging binary flags with continuous values is not meaningful
- **Better Alternative**: Count of available markets (sum of `has_*` flags) or just use `opening_overround`

**Option 3: Use Median**
- **Problem**: Same issue as averaging - mixing binary and continuous
- **Better Alternative**: Use `opening_overround` only (median of 1 value is just that value)

**Option 4: Use the Best One**
- **Recommended**: This is the most sensible approach
- Use `opening_overround` (most informative, continuous feature)
- Remove redundant `has_opening_moneyline` (confirmed redundant)
- Evaluate if `has_opening_spread` and `has_opening_total` add value

### What "Closing Line / Pre-Tip Line" Means

**Current**: Using opening odds (set days/weeks before game)  
**Alternative**: Use odds right before game starts (closing line / pre-tip line within N minutes of tip-off)

**Rationale**:
- Closing/pre-tip odds reflect latest information (injuries, lineups, late-breaking news)
- May be more predictive than stale opening odds
- Requires timestamped odds data (may not be available for all historical games)

**Window Selection**:
- **Avoid overly strict windows**: "Within 1 minute" is extremely strict and may not have sufficient coverage
- **Test multiple windows**: Check coverage for 5, 15, and 60 minute windows before game start
- **Select smallest with acceptable coverage**: Choose the smallest window that provides sufficient data for training

---

## Current State Analysis

### Feature Engineering Implementation

**File**: `scripts/lib/_winprob_lib.py:306-427` (`compute_opening_odds_features()`)

**Current Logic**:
```python
# Opening overround computed from moneyline odds
if opening_moneyline_home is not None and opening_moneyline_away is not None:
    valid_ml = (
        ~np.isnan(ml_home)
        & ~np.isnan(ml_away)
        & (ml_home > 1.0)
        & (ml_away > 1.0)
    )
    if np.any(valid_ml):
        opening_overround[valid_ml] = den - 1.0
    has_opening_moneyline = valid_ml.astype(np.float64)

# Spread and total flags computed independently
has_opening_spread = (~np.isnan(opening_spread)).astype(np.float64)
has_opening_total = (~np.isnan(opening_total)).astype(np.float64)
```

**Key Observations**:
1. `has_opening_moneyline` is set based on the same `valid_ml` condition used to compute `opening_overround`
2. This means: `has_opening_moneyline == 1` if and only if `opening_overround` is not `NaN`
3. `has_opening_spread` and `has_opening_total` are computed independently, but likely correlated with `has_opening_moneyline`

### Expected Correlation Patterns

**Hypothesis 1**: `has_opening_moneyline` is redundant with `opening_overround` ✅ **VERIFIED**
- **Reasoning**: Code analysis shows `opening_overround` is only computed when `valid_ml` is True, and `has_opening_moneyline` is set to 1 when `valid_ml` is True
- **Code Evidence**: `scripts/lib/_winprob_lib.py:392-396`
  - Line 392: `opening_overround[valid_ml] = den - 1.0` (only set when valid_ml is True)
  - Line 396: `has_opening_moneyline = valid_ml.astype(np.float64)` (set to 1 when valid_ml is True)
- **Expected Correlation**: **Perfect correlation (1.0)** - they are functionally identical
- **Impact**: `has_opening_moneyline` adds **zero information** beyond what `opening_overround` already conveys (via NaN presence)

**Hypothesis 2**: The three `has_*` flags are highly correlated
- **Reasoning**: If a game has opening odds data, it likely has all three markets (moneyline, spread, total)
- **Expected Correlation**: High correlation (0.7-0.9+) between `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
- **Impact**: Multicollinearity risk - model may struggle to determine which flag is actually predictive

**Hypothesis 3**: `opening_overround` may be weakly correlated with `has_opening_spread` and `has_opening_total`
- **Reasoning**: Overround is computed from moneyline only, spread/total flags are independent
- **Expected Correlation**: Low to moderate correlation (0.0-0.5)
- **Impact**: Less concerning, but still contributes to overall feature redundancy

### Data Availability Analysis

**Current Data Source**: `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`

**"Closing Line / Pre-Tip Line" Alternative**:
- **Definition**: Odds right before game starts (within N minutes of tip-off, where N is determined by coverage analysis - typically 5/15/60 minutes)
- **Data Availability**: Requires `snapshot_timestamp` to be populated and filtered for pre-game window
- **Current Status**: `snapshot_timestamp` exists in schema but may be NULL for historical data
- **Feasibility**: Needs verification - check coverage for multiple windows (5/15/60 minutes) and select smallest with acceptable coverage

---

## Technical Assessment

### Collinearity Analysis Framework

**Multicollinearity Detection Methods**:
1. **Correlation Matrix**: Pairwise correlations between features
2. **Variance Inflation Factor (VIF)**: Measures how much variance of a coefficient increases due to collinearity
3. **Feature Importance**: CatBoost feature importance to identify redundant features
4. **Conditional Independence**: Check if features provide independent information

### Alternative Feature Sets to Evaluate

**Option 1: Single Best Feature**
- **Approach**: Use only the most predictive feature (determined by feature importance)
- **Pros**: Eliminates collinearity, simplest model
- **Cons**: May lose information from other features

**Option 2: Averaged Features**
- **Approach**: Average the 4 features (normalize binary flags to 0-1, then average)
- **Pros**: Combines information from all features
- **Cons**: **Not statistically meaningful** - averaging binary flags (0/1) with continuous overround (e.g., 0.05) doesn't produce interpretable values. The data scientist's suggestion may have been shorthand for "use a single composite feature" rather than literal averaging.
- **Better Alternative**: Use `opening_overround` only, or create a count feature (sum of `has_*` flags) if market availability patterns matter

**Option 3: Median Aggregation**
- **Approach**: Use median of the 4 features
- **Pros**: Robust to outliers
- **Cons**: **Same issue as averaging** - mixing binary (0/1) and continuous (overround) values. Median of [0, 1, 0.05, 1] = 0.5 or 1 (depending on implementation), which is not meaningful.
- **Better Alternative**: Use `opening_overround` only (median of 1 value is just that value)

**Option 4: Single Composite Feature**
- **Approach**: Create one feature that captures odds availability (e.g., count of available markets, or just `opening_overround` with missingness handled)
- **Pros**: Single feature eliminates collinearity, interpretable
- **Cons**: May lose granular information

**Option 5: Reduced Feature Set**
- **Approach**: Keep `opening_overround` (most informative) and one `has_*` flag (e.g., `has_opening_moneyline` removed as redundant)
- **Pros**: Reduces collinearity while preserving some information
- **Cons**: Still has some correlation risk

### "Closing Line / Pre-Tip Line" Alternative

**Concept**: Use odds right before game starts (closing line / pre-tip line) instead of opening odds

**Rationale**:
- Opening odds may be set days/weeks before game
- Closing/pre-tip odds reflect latest information (injuries, lineups, late-breaking news)
- May be more predictive than stale opening odds

**Window Selection Strategy**:
- **Avoid overly strict windows**: "Within 1 minute" is extremely strict and may not have sufficient coverage in real sportsbook feeds
- **Test multiple windows**: Check coverage for 5, 15, and 60 minute windows before game start
- **Select smallest window with acceptable coverage**: Choose the smallest window that provides sufficient data for training (2017-2022 seasons)

**Implementation Requirements**:
1. Filter `external.sportsbook_odds_snapshots` for `snapshot_timestamp` within N minutes before game start (where N is determined by coverage analysis)
2. Use same feature engineering (overround, has_* flags) but from closing/pre-tip odds
3. Requires `snapshot_timestamp` to be populated (may not be available for all historical data)

**Data Availability Check Needed**:
- Query: Count games with `snapshot_timestamp` within multiple windows (5, 15, 60 minutes) before game start
- Verify sufficient coverage for training (2017-2022 seasons)
- Select smallest window with acceptable coverage

---

## Evidence and Proof

### MANDATORY: File Content Verification

**File**: `scripts/lib/_winprob_lib.py:306-427` (`compute_opening_odds_features()`)

**Evidence**:
- **Lines 372-396**: `has_opening_moneyline` is computed from same `valid_ml` condition used for `opening_overround`
- **Lines 400-409**: `has_opening_spread` and `has_opening_total` computed independently
- **Conclusion**: `has_opening_moneyline` is redundant with `opening_overround` (perfect correlation expected)

**File**: `scripts/lib/_winprob_lib.py:430-593` (`build_design_matrix()`)

**Evidence**:
- **Lines 445-448**: All 4 features accepted as parameters
- **Lines 551-583**: All 4 features added to design matrix when provided
- **Conclusion**: Current implementation includes all 4 features in model

### Database Evidence Template (PostgreSQL)

**IMPORTANT**: The engineered features (`opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`) are **NOT stored in the database**. They are computed in Python using `compute_opening_odds_features()`. The database only contains raw opening odds columns (`opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`).

**Correlation Analysis Query** (to be executed):
```sql
-- Analyze correlation patterns in training data
-- This query computes engineered features in SQL (replicating Python logic) for correlation analysis

WITH training_data AS (
    SELECT 
        opening_moneyline_home,
        opening_moneyline_away,
        opening_spread,
        opening_total,
        -- Compute opening_overround (replicating Python logic)
        CASE 
            WHEN opening_moneyline_home IS NOT NULL 
                 AND opening_moneyline_away IS NOT NULL
                 AND opening_moneyline_home > 1.0 
                 AND opening_moneyline_away > 1.0
            THEN (1.0 / opening_moneyline_home + 1.0 / opening_moneyline_away) - 1.0
            ELSE NULL
        END AS opening_overround,
        -- Compute has_opening_moneyline (replicating Python logic)
        CASE 
            WHEN opening_moneyline_home IS NOT NULL 
                 AND opening_moneyline_away IS NOT NULL
                 AND opening_moneyline_home > 1.0 
                 AND opening_moneyline_away > 1.0
            THEN 1.0
            ELSE 0.0
        END AS has_opening_moneyline,
        -- Compute has_opening_spread
        CASE WHEN opening_spread IS NOT NULL THEN 1.0 ELSE 0.0 END AS has_opening_spread,
        -- Compute has_opening_total
        CASE WHEN opening_total IS NOT NULL THEN 1.0 ELSE 0.0 END AS has_opening_total
    FROM derived.snapshot_features_v1
    WHERE season_label LIKE '2017-%' 
       OR season_label LIKE '2018-%'
       OR season_label LIKE '2019-%'
       OR season_label LIKE '2020-%'
       OR season_label LIKE '2021-%'
       OR season_label LIKE '2022-%'
    LIMIT 100000  -- Sample for performance
)
SELECT 
    -- Correlation: has_opening_moneyline vs opening_overround
    -- Expected: Perfect correlation (1.0) since both derived from same condition
    CORR(
        CASE WHEN opening_overround IS NOT NULL THEN 1.0 ELSE 0.0 END,
        has_opening_moneyline
    ) AS corr_overround_has_ml,
    
    -- Correlation: has_opening_moneyline vs has_opening_spread
    CORR(has_opening_moneyline, has_opening_spread) AS corr_ml_spread,
    
    -- Correlation: has_opening_moneyline vs has_opening_total
    CORR(has_opening_moneyline, has_opening_total) AS corr_ml_total,
    
    -- Correlation: has_opening_spread vs has_opening_total
    CORR(has_opening_spread, has_opening_total) AS corr_spread_total,
    
    -- Count patterns to verify redundancy
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_spread = 1 AND has_opening_total = 1) AS all_three,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_spread = 0) AS ml_without_spread,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_total = 0) AS ml_without_total,
    -- These should be 0 if redundancy is perfect
    COUNT(*) FILTER (WHERE opening_overround IS NOT NULL AND has_opening_moneyline = 0) AS overround_without_flag,
    COUNT(*) FILTER (WHERE opening_overround IS NULL AND has_opening_moneyline = 1) AS flag_without_overround,
    -- Total counts
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1) AS rows_with_moneyline,
    COUNT(*) FILTER (WHERE opening_overround IS NOT NULL) AS rows_with_overround
FROM training_data;
```

**Alternative Python-based Analysis** (recommended for accuracy):
Since the engineered features are computed in Python, a more accurate approach is to:
1. Load training data using the same logic as `train_winprob_catboost.py`
2. Compute features using `compute_opening_odds_features()` (ensures exact match with model)
3. Use pandas/numpy to compute correlations
4. This ensures the analysis uses the exact same feature computation logic as the model

**"Closing Line / Pre-Tip Line" Data Availability Query**:
```sql
-- Check availability of timestamped odds data for closing/pre-tip line alternative
-- Test multiple windows (5, 15, 60 minutes) to find smallest with acceptable coverage

WITH game_starts AS (
    SELECT 
        event_id AS espn_game_id,
        event_date AS game_start_time
    FROM espn.scoreboard_games
    WHERE status_completed = TRUE
),
odds_with_timestamps AS (
    SELECT 
        s.espn_game_id,
        s.snapshot_timestamp,
        gs.game_start_time,
        -- Calculate time difference before game start (negative = before, positive = after)
        EXTRACT(EPOCH FROM (s.snapshot_timestamp - gs.game_start_time)) / 60.0 AS minutes_before_start
    FROM external.sportsbook_odds_snapshots s
    LEFT JOIN game_starts gs ON s.espn_game_id = gs.espn_game_id
    WHERE s.espn_game_id IS NOT NULL
      AND s.is_opening_line = FALSE  -- Check non-opening lines for closing/pre-tip
      AND s.snapshot_timestamp IS NOT NULL
      AND gs.game_start_time IS NOT NULL
)
SELECT 
    COUNT(DISTINCT espn_game_id) AS total_games_with_timestamped_odds,
    -- Coverage for 5-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -5 AND minutes_before_start <= 0
    ) AS games_within_5_minutes,
    -- Coverage for 15-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -15 AND minutes_before_start <= 0
    ) AS games_within_15_minutes,
    -- Coverage for 60-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -60 AND minutes_before_start <= 0
    ) AS games_within_60_minutes,
    -- Overall stats
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start < 0
    ) AS games_with_pre_tip_odds,
    AVG(minutes_before_start) FILTER (WHERE minutes_before_start < 0) AS avg_minutes_before_start,
    MIN(minutes_before_start) AS earliest_minutes_before_start
FROM odds_with_timestamps;
```

### Feature Importance Analysis

**Method**: Extract feature importance from trained CatBoost models

**Implementation**:
1. Load trained model artifacts (e.g., `artifacts/winprob_catboost_baseline_isotonic_v2.json`)
2. Extract feature importance using CatBoost's `get_feature_importance()` method
3. Identify which opening odds features have highest/lowest importance
4. Compare importance of `has_opening_moneyline` vs `opening_overround` (should show redundancy)

**Expected Findings**:
- `opening_overround` likely has highest importance (continuous, informative)
- `has_opening_moneyline` likely has low/zero importance (redundant with overround)
- `has_opening_spread` and `has_opening_total` importance depends on actual predictive value

**Python Code Template**:
```python
from scripts.lib._winprob_lib import load_artifact
from catboost import CatBoostClassifier
import json

# Load artifact
artifact = load_artifact(Path("artifacts/winprob_catboost_baseline_isotonic_v2.json"))

# Load CatBoost model
model = CatBoostClassifier()
model.load_model(artifact.model_path)

# Get feature importance
importance = model.get_feature_importance()
feature_names = artifact.feature_names

# Find opening odds feature importance
odds_features = ['opening_overround', 'has_opening_moneyline', 'has_opening_spread', 'has_opening_total']
for feat in odds_features:
    if feat in feature_names:
        idx = feature_names.index(feat)
        print(f"{feat}: {importance[idx]:.4f}")
```

---

## Recommendations

### Immediate Actions (Priority: High)

**Recommendation 1**: **Quantify Collinearity** - Run correlation analysis on training data
- **Files to Modify**: None (analysis only)
- **Estimated Effort**: 2-4 hours (write queries, execute, analyze results)
- **Risk Level**: Low (read-only analysis)
- **Success Metrics**: Correlation matrix showing relationships, identification of redundant features

**Recommendation 2**: **Remove Redundant Feature** - ✅ **CONFIRMED**: Remove `has_opening_moneyline` (perfectly redundant)
- **Files to Modify**: 
  - `scripts/lib/_winprob_lib.py`:
    - Remove `has_opening_moneyline` from `ODDS_MODEL_FEATURES` constant (line 239)
    - Remove from `compute_opening_odds_features()` return dictionary (lines 416, 424)
    - Remove from `build_design_matrix()` function signature (line 446) and implementation (lines 566-569)
    - Remove from `predict_proba()` baseline parameter (line 601) and usage (lines 690-712)
  - `scripts/model/train_winprob_catboost.py`:
    - Remove from feature names list (line 854-855)
    - Remove from `build_matrix_kwargs` (line 802-803)
    - Remove from baseline usage (lines 908, 925, 1008)
  - `scripts/model/precompute_model_probabilities.py`:
    - Remove from feature check (line 412)
    - Remove from `build_kwargs` (line 417)
    - Remove from baseline parameter (line 440)
  - `scripts/trade/simulate_trading_strategy.py`:
    - Remove from feature check (line 267-268, 664-665, 702-703)
    - Remove from feature extraction (lines 646, 677)
    - Remove from `build_matrix_kwargs` (line 706)
    - Remove from baseline parameter (line 684, 731)
  - `scripts/model/evaluate_winprob_model.py`:
    - Remove from DataFrame assignment (line 541)
    - Remove from `build_matrix_kwargs` (lines 641-642, 749-750)
    - Remove from baseline parameter (lines 668, 772)
  - `scripts/model/evaluate_winprob_time_buckets.py`:
    - Remove from DataFrame assignment (line 184)
    - Remove from `build_kwargs` (line 222-223)
    - Remove from baseline parameter (line 246)
- **Estimated Effort**: 4-6 hours (code changes + retraining)
- **Risk Level**: Low-Medium (redundant feature removal should not hurt performance, but requires retraining)
- **Success Metrics**: Model performance maintained or improved, feature count reduced from 4 to 3

### Short-term Improvements (Priority: Medium)

**Recommendation 3**: **Evaluate Single Feature Alternative** - Test using only `opening_overround` (after removing `has_opening_moneyline`)
- **Rationale**: `opening_overround` is the most informative feature (continuous, captures bookmaker margin). The `has_*` flags may add little value beyond what overround's NaN pattern already conveys.
- **Files to Modify**: 
  - `scripts/lib/_winprob_lib.py` (modify feature computation to return only `opening_overround`)
  - `scripts/model/train_winprob_catboost.py` (update feature names)
- **Estimated Effort**: 4-6 hours (code changes + retraining + evaluation)
- **Risk Level**: Medium (requires model retraining and validation)
- **Success Metrics**: Model performance comparison (3 features vs. 1 feature after removing redundant flag)

**Recommendation 4**: **Investigate "Closing Line / Pre-Tip Line"** - Assess feasibility and data availability
- **Files to Modify**: None initially (analysis only)
- **Estimated Effort**: 2-4 hours (data availability check, feasibility analysis)
- **Risk Level**: Low (exploratory)
- **Success Metrics**: Data availability report, coverage analysis

### Long-term Strategic Changes (Priority: Low)

**Recommendation 5**: **Implement "Closing Line / Pre-Tip Line" Alternative** - If data is available and shows promise
- **Files to Modify**: 
  - `scripts/model/train_winprob_catboost.py` (modify SQL query to filter for closing/pre-tip odds within selected window)
  - `scripts/lib/_winprob_lib.py` (update feature names/computation if needed)
- **Estimated Effort**: 8-12 hours (code changes + retraining + evaluation)
- **Risk Level**: Medium-High (significant change, requires validation)
- **Success Metrics**: Model performance comparison (opening odds vs. closing/pre-tip odds)

---

## Implementation Plan

### Phase 1: Data Analysis (Duration: 4-6 hours)
**Objective**: Quantify collinearity and identify redundant features

**Dependencies**: Access to training data via `DATABASE_URL`

**Deliverables**: 
- Correlation matrix for the 4 features
- Feature importance analysis from existing models
- Identification of redundant features

#### Tasks
- **Task 1**: Write and execute correlation analysis query
  - **Files**: New analysis script or SQL query
  - **Effort**: 2 hours
  - **Prerequisites**: Database access

- **Task 2**: Extract feature importance from trained models
  - **Files**: Analysis script to load model artifacts and extract importance
  - **Effort**: 2 hours
  - **Prerequisites**: Trained model artifacts available

- **Task 3**: Analyze "odds last minute" data availability
  - **Files**: SQL query to check timestamp coverage
  - **Effort**: 2 hours
  - **Prerequisites**: Database access

### Phase 2: Code Changes (Duration: 4-6 hours)
**Objective**: Implement reduced feature set based on analysis findings

**Dependencies**: Must complete Phase 1 (know which features to remove/keep)

**Deliverables**: 
- Updated feature computation logic
- Updated design matrix construction
- Updated training script

#### Tasks
- **Task 1**: Remove redundant features from `compute_opening_odds_features()`
  - **Files**: `scripts/lib/_winprob_lib.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Phase 1 findings

- **Task 2**: Update `build_design_matrix()` to use reduced feature set
  - **Files**: `scripts/lib/_winprob_lib.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Task 1

- **Task 3**: Update training script feature names
  - **Files**: `scripts/model/train_winprob_catboost.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Task 2

### Phase 3: Model Retraining and Evaluation (Duration: 6-8 hours)
**Objective**: Retrain models with new feature set and evaluate performance

**Dependencies**: Must complete Phase 2 (code changes)

**Deliverables**: 
- Retrained model artifacts
- Performance comparison (old vs. new feature set)
- Evaluation report

#### Tasks
- **Task 1**: Retrain odds-enabled v2 models with new feature set
  - **Files**: `scripts/model/train_winprob_catboost.py`
  - **Effort**: 4-6 hours (model training time)
  - **Prerequisites**: Phase 2 complete

- **Task 2**: Evaluate models on test set
  - **Files**: `scripts/model/evaluate_winprob_model.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Task 1

- **Task 3**: Compare performance (old vs. new)
  - **Files**: Analysis script or manual comparison
  - **Effort**: 1 hour
  - **Prerequisites**: Task 2

---

## Risk Assessment

### Technical Risks

**Risk 1**: Removing features reduces model performance
- **Probability**: Medium
- **Impact**: High (worse predictions)
- **Mitigation**: Compare performance before/after, keep old models as backup
- **Contingency**: Revert to 4 features if performance degrades significantly

**Risk 2**: Correlation analysis shows features are not redundant
- **Probability**: Low
- **Impact**: Low (no changes needed)
- **Mitigation**: Analysis will reveal actual relationships
- **Contingency**: Keep current implementation if features are not redundant

**Risk 3**: "Closing line / pre-tip line" data not available for sufficient games
- **Probability**: Medium
- **Impact**: Medium (alternative not viable)
- **Mitigation**: Check data availability for multiple windows (5/15/60 minutes) before implementing, select smallest window with acceptable coverage
- **Contingency**: Stick with opening odds if closing/pre-tip data insufficient for any reasonable window

### Business Risks

**Risk 1**: Model retraining requires significant time
- **Probability**: High
- **Impact**: Medium (delays deployment)
- **Mitigation**: Plan retraining during low-activity period
- **Contingency**: Stagger retraining across models

### Resource Risks

**Risk 1**: Database query performance for correlation analysis
- **Probability**: Medium
- **Impact**: Low (can use sampling)
- **Mitigation**: Use LIMIT clause for sampling, run during off-peak hours
- **Contingency**: Use smaller sample if query is too slow

---

## Success Metrics and Monitoring

### Performance Metrics

**Model Performance**:
- **Brier Score**: Compare old vs. new feature set (target: maintain or improve)
- **Log Loss**: Compare old vs. new feature set (target: maintain or improve)
- **ROC-AUC**: Compare old vs. new feature set (target: maintain or improve)

**Feature Metrics**:
- **Feature Count**: Reduce from 4 to 1-3 features
- **Correlation**: Maximum pairwise correlation < 0.7 (target)
- **Feature Importance**: Identify which feature(s) are most predictive

### Quality Metrics

**Code Quality**:
- **Feature Redundancy**: Eliminate redundant features
- **Code Complexity**: Reduce feature computation complexity
- **Maintainability**: Simpler feature set improves maintainability

### Monitoring Strategy

**Post-Implementation**:
- Monitor model performance on test set
- Track feature importance in production
- Compare predictions between old and new models

---

## Appendices

### Appendix A: Current Feature Computation Logic

**File**: `scripts/lib/_winprob_lib.py:306-427`

**Key Code Sections**:
- Lines 372-396: `has_opening_moneyline` computation (uses same `valid_ml` as `opening_overround`)
- Lines 400-409: `has_opening_spread` and `has_opening_total` computation (independent)

### Appendix B: Feature Usage in Design Matrix

**File**: `scripts/lib/_winprob_lib.py:430-593`

**Key Code Sections**:
- Lines 445-448: Feature parameters
- Lines 551-583: Feature addition to design matrix

### Appendix C: Data Scientist Feedback

**Original Feedback**:
```
dta — 1:11 AM
why did u add 4 opening odds

dta — 1:12 AM
ok i don't understand why it says 4

dta — 1:12 AM
using 1 or like averaging the 4 would be best

dta — 1:13 AM
use the best one or average
using 4 introduces collinearlity
which can be very bad
mb use median
also we might want to use "odds last minute" instead of opening odds
we'll see
```

**Note**: The data scientist's mention of "odds last minute" should be interpreted as "closing line / pre-tip line" with flexible time windows. A strict 1-minute window is likely too restrictive for real sportsbook feeds. The analysis tests multiple windows (5/15/60 minutes) to find the smallest window with acceptable coverage.

### Appendix D: Glossary

- **Collinearity**: Linear relationship between two or more features
- **Multicollinearity**: High correlation between multiple features in a regression model
- **Variance Inflation Factor (VIF)**: Measure of how much variance of a coefficient increases due to collinearity
- **Opening Odds**: Pre-game betting odds set when line first opens
- **Closing Line / Pre-Tip Line**: Betting odds right before game starts (within N minutes of tip-off, where N is determined by coverage analysis - typically 5/15/60 minutes)
- **Overround**: Bookmaker's margin/vig, computed as `(1/odds_home + 1/odds_away) - 1.0`

---

## Document Validation

**IMPORTANT**: This analysis follows the comprehensive validation checklist in `ANALYSIS_STANDARDS.md`.

**Validation Status**:
- ✅ Evidence-based claims (code references provided)
- ✅ File content verification (files read and analyzed)
- ✅ Code redundancy verified (has_opening_moneyline perfectly redundant with opening_overround)
- ✅ Database queries prepared (SQL queries ready to execute, Python alternative provided)
- ✅ Feature importance extraction method provided (Python code template)
- ✅ All affected files identified with specific line numbers
- ⚠️ Database queries not yet executed (pending execution)
- ⚠️ Feature importance not yet extracted (pending analysis)
- ⚠️ "Closing line / pre-tip line" data availability not yet verified (pending query execution for multiple windows)

**Important Notes**:
- **Constant Update Required**: `ODDS_MODEL_FEATURES` constant in `scripts/lib/_winprob_lib.py` (line 237-242) must be updated to remove `has_opening_moneyline`. The legacy `ODDS_FEATURES` alias (line 245) points to `ODDS_RAW_FIELDS` and does not need to be changed.
- **Database Schema**: Engineered features (`opening_overround`, `has_opening_moneyline`, etc.) are NOT stored in the database. They are computed in Python using `compute_opening_odds_features()`. The database only contains raw opening odds columns (`opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`).
- **No Test Updates Needed**: No test files reference these features (verified via grep).

**Next Steps**:
1. **Execute correlation analysis** - Run SQL query (or Python-based analysis) on training data to quantify correlations
2. **Extract feature importance** - Load trained model artifacts and extract CatBoost feature importance for opening odds features
3. **Verify "closing line / pre-tip line" data availability** - Run SQL query to check coverage for multiple windows (5/15/60 minutes) and select smallest with acceptable coverage
4. **Update analysis with actual findings** - Replace hypotheses with verified data
5. **Proceed with implementation** - Based on findings, implement recommended feature set changes

**Additional Verification Needed**:
- ✅ Code redundancy verified (has_opening_moneyline perfectly redundant with opening_overround)
- ⚠️ Data correlation not yet verified (SQL query prepared but not executed)
- ⚠️ Feature importance not yet extracted (method provided but not executed)
- ⚠️ "Closing line / pre-tip line" feasibility not yet verified (query prepared but not executed for multiple windows)
