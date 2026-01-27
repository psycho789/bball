# Sprint Implementation Review: Pre-Game Odds Model Integration

**Date**: 2026-01-15  
**Sprint**: S1 - Pre-Game Odds Model Integration  
**Status**: In Progress (Phases 1-2 Complete, Phase 3 Partial)

## Executive Summary

**Progress**: ~40% Complete

- ✅ **Phase 1**: Parity Validation - COMPLETE
- ✅ **Phase 2**: Feature Engineering - COMPLETE  
- 🔄 **Phase 3**: Design Matrix and Training Integration - IN PROGRESS (Story 3.1 complete, 3.2-3.3 pending)
- ⏳ **Phase 4**: Model Evaluation - PENDING
- ⏳ **Phase 5**: Quality Assurance - PENDING

**Key Finding**: Parity validation revealed canonical dataset only contains 2024-2025 seasons (94.8% data loss). Implemented **Option B** approach: join ESPN tables with opening odds to preserve all training data.

---

## Phase 1: Parity Validation ✅ COMPLETE

### Files Created
- `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md`

### Key Findings

**ESPN-Direct Training Data** (2017-2025):
- Total games: 11,243
- Total snapshots: 5,346,888
- Coverage: All seasons 2017-2025

**Canonical Dataset** (`derived.snapshot_features_v1`):
- Total games: 589 (only 2024-2025)
- Total snapshots: 290,800
- **Data Loss**: 94.8% of games, 94.6% of snapshots

**Decision**: **NO-GO** - Cannot switch to canonical dataset without losing 7 seasons of training data.

**Solution**: **Option B** - Keep ESPN-direct query and LEFT JOIN with `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`.

### Validation Queries Executed
- ✅ Q3a: ESPN-direct game/snapshot counts per season
- ✅ Q3b: Canonical dataset game/snapshot counts per season
- ✅ Time bucket distribution comparison
- ✅ Sample feature parity check (partial - game universes don't overlap sufficiently)

---

## Phase 2: Feature Engineering ✅ COMPLETE

### Files Created
- `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md`

### Files Modified
- `scripts/lib/_winprob_lib.py` - Added `compute_opening_odds_features()` helper function
- `scripts/model/train_winprob_catboost.py` - Updated `_load_training_data()` to join opening odds and compute engineered features

### Story 2.1: Odds Format Validation ✅

**Format Determined**: **DECIMAL ODDS**

**Evidence**:
- Sample values: 1.335, 1.833, 2.09, 3.57 (typical decimal range)
- Value range: 1.053 - 12.68 (decimal format)
- No negative values (would indicate American odds)
- No values > 100 (American underdog odds are positive > 100)

**Conversion Formula**: `p = 1 / odds` (decimal format)

**Example Calculation**:
- Home: 1.833, Away: 2.09
- Raw probs: 0.5455, 0.4785
- Overround: 0.0240 (2.4% vig)
- Fair probs: 0.5323, 0.4677 ✓

### Story 2.2: Shared De-Vigging Helper ✅

**Function**: `compute_opening_odds_features()` in `scripts/lib/_winprob_lib.py`

**Features**:
- ✅ Accepts scalar or array inputs
- ✅ Uses decimal odds conversion (`p = 1 / odds`)
- ✅ Safety checks: only computes if both odds present and > 1.0
- ✅ Returns NaNs for missing/invalid odds (CatBoost handles natively)
- ✅ Returns engineered features: `opening_prob_home_fair`, `opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`

**Code Location**: `scripts/lib/_winprob_lib.py` lines 183-315

### Story 2.3: Training Data Loading Integration ✅

**Changes to `train_winprob_catboost.py`**:

1. **SQL Query Updated** (lines 107-228):
   - Added `opening_odds` CTE to pivot opening odds by market_type and side
   - LEFT JOIN with `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`
   - Join on `espn_game_id` (ESPN `event_id` = `external.espn_game_id`)
   - Extracts: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`

2. **Feature Engineering** (lines 256-280):
   - Calls `compute_opening_odds_features()` helper function (vectorized)
   - Adds engineered features to DataFrame:
     - `opening_prob_home_fair`
     - `opening_overround`
     - `has_opening_moneyline`
     - `has_opening_spread`
     - `has_opening_total`

**Implementation Pattern**: Option B (ESPN-direct + opening odds join)

---

## Phase 3: Design Matrix and Training Integration 🔄 IN PROGRESS

### Story 3.1: Design Matrix Integration ✅ COMPLETE

**Files Modified**:
- `scripts/lib/_winprob_lib.py`

**Changes**:

1. **Canonical Feature List** (line 172):
   ```python
   ODDS_FEATURES = [
       'opening_prob_home_fair',
       'opening_overround',
       'opening_spread',
       'opening_total',
       'has_opening_moneyline',
       'has_opening_spread',
       'has_opening_total',
   ]
   ```

2. **Function Signature Extended** (lines 318-337):
   - Added 7 optional opening odds parameters to `build_design_matrix()`
   - All parameters default to `None` (backward compatible)

3. **Feature Addition Logic** (lines 413-461):
   - If any opening odds feature provided, adds all 7 features in canonical order
   - Missing features filled with NaNs (for probability features) or zeros (for flags)
   - Maintains stable design matrix shape

**Code Location**: `scripts/lib/_winprob_lib.py` lines 172, 318-463

### Story 3.2: Training Script Integration ⏳ PENDING

**Status**: Not yet implemented

**Required Changes**:
- Update `build_matrix_kwargs` dictionary to include opening odds features (training set)
- Update `calib_matrix_kwargs` dictionary to include opening odds features (calibration set)
- Update `feature_names` list using `ODDS_FEATURES` constant

**File**: `scripts/model/train_winprob_catboost.py`

### Story 3.3: Pre-Computation Script Integration ⏳ PENDING

**Status**: Not yet implemented

**Required Changes**:
- Update SQL query to include opening odds columns
- Call `compute_opening_odds_features()` helper in `score_snapshot()` function
- Pass opening odds features to `build_design_matrix()`

**File**: `scripts/model/precompute_model_probabilities.py`

---

## Phase 4: Model Evaluation ⏳ PENDING

### Story 4.1: Train Baseline and Odds-Enabled Models
- **Status**: Not started
- **Requires**: Story 3.2 complete

### Story 4.2: Time-Bucketed Evaluation
- **Status**: Not started
- **Requires**: Story 4.1 complete

---

## Phase 5: Quality Assurance ⏳ PENDING

### Stories 5.1-5.3
- **Status**: Not started
- **Requires**: All development stories complete

---

## Code Quality

### Linting Status
- ✅ `scripts/lib/_winprob_lib.py` - No linting errors
- ✅ `scripts/model/train_winprob_catboost.py` - No linting errors

### Testing Status
- ⚠️ Helper function not yet tested (numpy not available in test environment)
- ⚠️ Training data loading not yet tested end-to-end

---

## Key Design Decisions

### 1. Option B Implementation (ESPN-Direct + Opening Odds Join)
**Rationale**: Canonical dataset excludes 94.8% of training data (2017-2023 seasons missing).  
**Implementation**: LEFT JOIN with `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`.

### 2. Shared Helper Function
**Rationale**: Prevents code duplication between training and pre-computation scripts.  
**Location**: `scripts/lib/_winprob_lib.py::compute_opening_odds_features()`

### 3. Canonical Feature List
**Rationale**: Ensures consistent feature ordering across training, calibration, and scoring.  
**Location**: `scripts/lib/_winprob_lib.py::ODDS_FEATURES` constant

### 4. Decimal Odds Format
**Rationale**: Validated database values are in decimal format (1.0-12.68 range).  
**Conversion**: `p = 1 / odds` (NOT American format)

### 5. Missing Value Handling
**Rationale**: CatBoost handles NaNs natively, no imputation needed.  
**Implementation**: Return NaNs for missing/invalid odds, add missingness indicator flags.

---

## Next Steps

### Immediate (Phase 3 Completion)
1. **Story 3.2**: Update `train_winprob_catboost.py` to pass opening odds to `build_design_matrix()`
   - Add opening odds to `build_matrix_kwargs` (training set)
   - Add opening odds to `calib_matrix_kwargs` (calibration set)
   - Update `feature_names` using `ODDS_FEATURES` constant

2. **Story 3.3**: Update `precompute_model_probabilities.py`
   - Add opening odds columns to SQL query
   - Call `compute_opening_odds_features()` in `score_snapshot()`
   - Pass opening odds to `build_design_matrix()`

### Short-Term (Phase 4)
3. **Story 4.1**: Train baseline and odds-enabled models
   - Set fixed random seed for split reproducibility
   - Persist split keys to file
   - Train both models with same split

4. **Story 4.2**: Time-bucketed evaluation
   - Create evaluation script
   - Compute metrics by time bucket
   - Compare baseline vs odds-enabled

### Long-Term (Phase 5)
5. **Stories 5.1-5.3**: Quality assurance
   - Documentation updates
   - Quality gate validation
   - Sprint completion

---

## Files Modified Summary

### Created
1. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md`
2. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md`
3. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/sprint-implementation-review.md` (this file)

### Modified
1. `scripts/lib/_winprob_lib.py`
   - Added `ODDS_FEATURES` constant (line 172)
   - Added `compute_opening_odds_features()` function (lines 183-315)
   - Extended `build_design_matrix()` signature (lines 318-337)
   - Added opening odds feature logic (lines 413-461)

2. `scripts/model/train_winprob_catboost.py`
   - Updated `_load_training_data()` docstring (lines 91-104)
   - Added `opening_odds` CTE to SQL query (lines 139-150)
   - Added opening odds columns to SELECT (lines 217-221)
   - Added feature engineering using helper function (lines 256-280)

### Pending Modifications
1. `scripts/model/train_winprob_catboost.py` - Story 3.2 (pass opening odds to build_design_matrix)
2. `scripts/model/precompute_model_probabilities.py` - Story 3.3 (add opening odds support)

---

## Validation Evidence

### Parity Validation
- ✅ Q3a query executed: 11,243 games, 5,346,888 snapshots (2017-2025)
- ✅ Q3b query executed: 589 games, 290,800 snapshots (2024-2025 only)
- ✅ Parity report created with detailed comparison

### Odds Format Validation
- ✅ Sample query executed: 20 random rows inspected
- ✅ Range query executed: min=1.053, max=12.68 (decimal format confirmed)
- ✅ Validation report created with conversion formulas

### Code Validation
- ✅ Helper function created with proper signature
- ✅ Design matrix function extended with opening odds parameters
- ✅ Training data loading updated with opening odds join
- ✅ No linting errors

---

## Risks and Mitigations

### Risk 1: Parity Failure (RESOLVED)
- **Risk**: Canonical dataset excludes training data
- **Mitigation**: Implemented Option B (ESPN-direct + opening odds join)
- **Status**: ✅ Resolved

### Risk 2: Wrong Odds Format (RESOLVED)
- **Risk**: Using wrong conversion formula (decimal vs American)
- **Mitigation**: Validated format before implementation (decimal confirmed)
- **Status**: ✅ Resolved

### Risk 3: Code Duplication (RESOLVED)
- **Risk**: De-vigging logic duplicated in multiple files
- **Mitigation**: Created shared helper function
- **Status**: ✅ Resolved

### Risk 4: Feature Ordering Inconsistencies (RESOLVED)
- **Risk**: Features added in different orders causing bugs
- **Mitigation**: Defined `ODDS_FEATURES` constant, always use canonical order
- **Status**: ✅ Resolved

### Risk 5: Train/Test Split Differences (PENDING)
- **Risk**: Baseline and odds-enabled models use different splits
- **Mitigation**: Fixed random seed + split file persistence (Story 4.1)
- **Status**: ⏳ Pending implementation

---

## Questions for Review

1. **Option B Implementation**: Is the ESPN-direct + opening odds join approach acceptable? (Preserves all training data but more complex query)

2. **Feature Engineering**: Should we add any additional opening odds features beyond the 7 canonical features?

3. **Testing**: Should we test the helper function and training data loading before proceeding to Story 3.2?

4. **Split Reproducibility**: Should we implement split file persistence now (Story 4.1) or wait until model training?

5. **Pre-Computation**: Is `precompute_model_probabilities.py` critical for this sprint, or can it be deferred?

---

## Summary

**Completed Work**: ~40% of sprint (Phases 1-2 complete, Phase 3 Story 3.1 complete)

**Key Achievements**:
- ✅ Validated parity and documented Option B approach
- ✅ Validated odds format (decimal) and documented conversion
- ✅ Created shared de-vigging helper function
- ✅ Integrated opening odds into training data loading
- ✅ Extended design matrix with opening odds support
- ✅ Defined canonical feature list

**Remaining Work**: ~60% of sprint
- Story 3.2: Update training script to pass opening odds
- Story 3.3: Update pre-computation script
- Phase 4: Model training and evaluation
- Phase 5: Quality assurance

**Blockers**: None - all remaining work can proceed

**Recommendation**: Continue with Story 3.2 (training script integration) as it's the next logical step and unblocks model training.
