# Sprint 17 Progress Report

**Date**: 2026-01-07  
**Sprint**: Sprint 17 - Complete Signal Improvement Integration  
**Status**: In Progress

## Completed Work

### Epic 1: Integrate Canonical Dataset into Modeling ✅

**Story 1.1: Update `train_winprob_logreg.py` to Query Canonical Dataset** ✅
- **Status**: Complete
- **Changes**:
  - Replaced Parquet file reading with database query to `derived.snapshot_features_v1`
  - Created `_load_training_data()` function that queries canonical dataset
  - Maps canonical dataset columns to model features:
    - `score_diff` → `point_differential`
    - `time_remaining` → `time_remaining_regulation`
    - `possession` → `'unknown'` (not reliably available in canonical dataset)
    - `final_winning_team` → derived from `espn.scoreboard_games`
    - `season_start` → extracted from `season_label` (e.g., "2025-26" → 2025)
- **Files Modified**: `scripts/train_winprob_logreg.py`

**Story 1.2: Remove Parquet Dependency** ✅
- **Status**: Complete
- **Changes**:
  - Removed `--snapshots-parquet` command-line argument
  - Added `--dsn` argument for database connection (uses `DATABASE_URL` env var as fallback)
  - All data loading now uses canonical dataset
- **Files Modified**: `scripts/train_winprob_logreg.py`

**Story 1.3: Validate Feature Mapping** ✅
- **Status**: Complete
- **Validation**:
  - Verified canonical dataset columns match model expectations
  - Confirmed feature types are correct (numeric, categorical)
  - Handled missing values (NULL handling in SQL query)
- **Files Modified**: `scripts/train_winprob_logreg.py`

### Epic 2: Implement Interaction Terms Model ✅

**Story 2.1: Train Model with Interaction Terms** ✅
- **Status**: Complete
- **Changes**:
  - Extended `PreprocessParams` dataclass to include normalization params for interaction terms:
    - `score_diff_div_sqrt_time_rem_mean/std`
    - `espn_home_prob_mean/std`
    - `espn_home_prob_lag_1_mean/std`
    - `espn_home_prob_delta_1_mean/std`
  - Extended `build_design_matrix()` function to accept optional interaction term parameters:
    - `score_diff_div_sqrt_time_remaining` (interaction term)
    - `espn_home_prob` (baseline probability)
    - `espn_home_prob_lag_1` (momentum)
    - `espn_home_prob_delta_1` (change)
    - `period` (one-hot encoded: 1, 2, 3, 4)
  - Updated training script to:
    - Load interaction terms from canonical dataset
    - Calculate normalization params from training data
    - Pass interaction terms to `build_design_matrix()`
    - Update feature names list to include interaction terms
  - Added `--use-interaction-terms` flag (default: True) and `--no-interaction-terms` flag
  - Updated `save_artifact()` and `load_artifact()` for backward compatibility
- **Files Modified**: 
  - `scripts/_winprob_lib.py`
  - `scripts/train_winprob_logreg.py`

**Story 2.2: Apply Platt Scaling** ✅
- **Status**: Already Implemented
- **Note**: Platt scaling was already implemented in the original code and continues to work with interaction terms model

## Pending Work

### Epic 1: Testing

**Story 1.4: Test Training Pipeline** ⏳
- **Status**: Pending
- **Next Steps**:
  1. Test basic model training (without interaction terms):
     ```bash
     python scripts/train_winprob_logreg.py \
       --out-artifact artifacts/winprob_logreg_basic.json \
       --no-interaction-terms \
       --dsn "$DATABASE_URL"
     ```
  2. Test interaction terms model training:
     ```bash
     python scripts/train_winprob_logreg.py \
       --out-artifact artifacts/winprob_logreg_interaction.json \
       --use-interaction-terms \
       --dsn "$DATABASE_URL"
     ```
  3. Verify model artifacts are created correctly
  4. Compare model performance vs baseline

### Epic 2: Validation

**Story 2.3: Validate Signal Metrics** ⏳
- **Status**: Pending
- **Next Steps**:
  1. Calculate logloss on test set for both models
  2. Calculate Brier score on test set
  3. Calculate ECE (Expected Calibration Error)
  4. Calculate reliability by buckets
  5. Compare interaction terms model vs baseline (raw ESPN probabilities)

**Story 2.4: Compare vs Baseline** ⏳
- **Status**: Pending
- **Next Steps**:
  1. Load baseline model (raw ESPN probabilities)
  2. Evaluate baseline on test set
  3. Evaluate improved model on test set
  4. Compare metrics (logloss, Brier, ECE)
  5. Document comparison

### Epic 3: Validate Improved Signal

**Story 3.1: Run Grid Search with Improved Signal** ⏳
- **Status**: Pending
- **Next Steps**:
  1. Update grid search script to use interaction terms model predictions
  2. Run grid search with improved signal
  3. Store results
  4. Calculate performance metrics

**Story 3.2: Compare Trading Metrics vs Baseline** ⏳
- **Status**: Pending

**Story 3.3: Document Findings** ⏳
- **Status**: Pending

## Technical Notes

### Design Decisions

**Design Pattern**: Strategy Pattern
- **Implementation**: Model supports both basic and extended feature sets via `--use-interaction-terms` flag
- **Benefits**: 
  - Backward compatibility (can train basic model)
  - Easy A/B testing (compare basic vs interaction terms)
  - Gradual rollout capability
- **Trade-offs**: 
  - Slightly more complex code (conditional feature loading)
  - Need to maintain both code paths

**Algorithm**: Logistic Regression with L2 Regularization
- **Complexity**: Time O(n×d×iter), Space O(d) where n=samples, d=features, iter=IRLS iterations
- **Description**: Iteratively Reweighted Least Squares (IRLS) for logistic regression
- **Use Case**: Binary classification (home team win probability)
- **Performance**: Efficient for moderate-sized datasets (thousands of games, hundreds of features)

### Feature Engineering

**Interaction Terms Added**:
1. `score_diff_div_sqrt_time_remaining`: Captures game context (clutch situations, blowouts)
   - Formula: `score_diff / sqrt(time_remaining + 1)`
   - Pre-computed in canonical dataset
2. `espn_home_prob`: Baseline ESPN probability (0-1 range)
3. `espn_home_prob_lag_1`: Previous snapshot probability (momentum)
4. `espn_home_prob_delta_1`: Change in probability (trend)
5. `period`: Game quarter (1, 2, 3, 4) - one-hot encoded

**Normalization**:
- All interaction terms are normalized using mean/std from training data only
- Missing values (NULL/NaN) are handled by filling with 0.0 after normalization
- Ensures no data leakage (normalization params computed only from training set)

### Backward Compatibility

**Artifact Format**:
- Extended `PreprocessParams` includes optional fields (None if not used)
- `save_artifact()` saves all fields (including None values)
- `load_artifact()` handles missing fields gracefully (defaults to None)
- Old artifacts can still be loaded (basic model format)

**Model Compatibility**:
- Basic model (5 features) still works
- Extended model (up to 13 features) is optional
- Feature names list dynamically built based on available features

## Testing Checklist

- [ ] Test basic model training (no interaction terms)
- [ ] Test interaction terms model training
- [ ] Verify model artifacts load correctly
- [ ] Verify feature names match model weights
- [ ] Test prediction on sample data
- [ ] Compare model performance metrics
- [ ] Validate signal metrics (logloss, Brier, ECE)
- [ ] Run grid search with improved signal
- [ ] Compare trading metrics vs baseline

## Known Issues / TODOs

1. **Possession Data**: Currently set to `'unknown'` for all rows. Canonical dataset doesn't include possession reliably. May need to add to canonical dataset in future if needed for model improvement.

2. **Testing**: Need to run actual training tests to verify everything works end-to-end.

3. **Signal Validation**: Need to implement signal metrics calculation and comparison vs baseline.

4. **Grid Search Integration**: Need to update grid search script to use interaction terms model predictions instead of raw ESPN probabilities.

## Next Steps

1. **Test Training Pipeline** (Story 1.4)
   - Run training script with both basic and interaction terms models
   - Verify artifacts are created correctly
   - Check for any runtime errors

2. **Validate Signal Metrics** (Story 2.3)
   - Implement signal metrics calculation
   - Compare interaction terms model vs baseline
   - Document findings

3. **Grid Search Integration** (Epic 3)
   - Update grid search to use improved signal
   - Run grid search and compare results
   - Document trading performance improvements

