# Analysis: 2x2 Model Comparison Matrix (Logistic Regression vs CatBoost, Platt vs Isotonic)

**Date**: Sun Jan 12 2026  
**Status**: Draft  
**Author**: Analysis System  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Analyze the request for a 2x2 model matrix comparing Logistic Regression vs CatBoost with Platt vs Isotonic calibration methods

## Analysis Standards Reference

**Important**: This analysis must follow the comprehensive standards defined in `ANALYSIS_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim must be backed by concrete evidence (code refs, commands + verbatim output, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers analyzed.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: Use PostgreSQL via `DATABASE_URL`.

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings
- **Current State**: Only 1 of 4 requested models exists (Logistic Regression with Platt scaling)
- **Requested Matrix**: 2 model types × 2 calibration methods = 4 models total
- **Missing Models**: 
  1. Logistic Regression with Isotonic scaling ❌
  2. CatBoost with Platt scaling ❌
  3. CatBoost with Isotonic scaling ❌

### Critical Issues Identified
- **Isotonic Calibration Not Implemented**: Current codebase only supports Platt scaling
- **CatBoost Not Implemented**: No CatBoost training or evaluation scripts exist
- **Calibration Method Comparison**: Cannot compare Platt vs Isotonic without implementing Isotonic

### Recommended Actions
- **Action 1**: [Priority: High] - Implement Isotonic calibration in `_winprob_lib.py`
- **Action 2**: [Priority: High] - Create CatBoost training script (`train_winprob_catboost.py`)
- **Action 3**: [Priority: Medium] - Update evaluation script to support both calibration methods
- **Action 4**: [Priority: Medium] - Create comparison visualization for all 4 models

### Success Metrics
- **Model Coverage**: All 4 models trained and evaluated (target: 100%)
- **Calibration Comparison**: ECE comparison between Platt and Isotonic for each model type
- **Performance Comparison**: Brier score, AUC, and log loss comparison across all 4 models

## Problem Statement

### Current Situation

**Friend's Request**: "i think i asked for 2-4 models: logistic/catboost with platt/isotonic scaling, so 2x2"

This means a **2×2 matrix** of models:
- **Model Types**: Logistic Regression, CatBoost
- **Calibration Methods**: Platt scaling, Isotonic scaling
- **Total**: 4 models

**Current State**:
1. ✅ **Logistic Regression + Platt**: Exists (`artifacts/winprob_logreg_2017-2023_calib_2023.json`)
2. ❌ **Logistic Regression + Isotonic**: Missing
3. ❌ **CatBoost + Platt**: Missing
4. ❌ **CatBoost + Isotonic**: Missing

### What Each Model Means

#### Model Types

**1. Logistic Regression** (Current Implementation)
- **Algorithm**: Iteratively Reweighted Least Squares (IRLS) / Newton's Method
- **Features**: 
  - `point_differential_scaled`
  - `time_remaining_regulation_scaled`
  - `possession_home/away/unknown` (one-hot)
  - Optional interaction terms (ESPN prob, lagged features, period)
- **Pros**: Interpretable, fast, no external dependencies
- **Cons**: Linear decision boundaries, limited complexity
- **File**: `scripts/model/train_winprob_logreg.py`

**2. CatBoost** (Not Yet Implemented)
- **Algorithm**: Gradient Boosting Decision Trees
- **Features**: Same as Logistic Regression, but can handle non-linear relationships
- **Pros**: 
  - Handles non-linear patterns automatically
  - Better with interactions (automatic feature interactions)
  - Robust to overfitting (built-in regularization)
  - Handles categorical features well
- **Cons**: 
  - Less interpretable (black box)
  - Requires external dependency (`catboost` package)
  - Slower training and prediction
- **File**: Needs to be created (`scripts/model/train_winprob_catboost.py`)

#### Calibration Methods

**1. Platt Scaling** (Current Implementation)
- **Method**: Logistic regression on logit-transformed probabilities
- **Formula**: `P_calibrated = sigmoid(alpha + beta * logit(P_base))`
- **Parameters**: 2 parameters (alpha, beta)
- **Pros**: 
  - Simple (2 parameters)
  - Works well when base model is already decently calibrated
  - Preserves ranking (monotonic transformation)
- **Cons**: 
  - Assumes sigmoid shape (may not fit all cases)
  - Limited flexibility
- **Implementation**: `scripts/lib/_winprob_lib.py` → `PlattCalibrator`, `fit_platt_calibrator_on_probs()`

**2. Isotonic Regression** (Not Yet Implemented)
- **Method**: Non-parametric piecewise linear calibration
- **Formula**: Monotonic (non-decreasing) piecewise linear function
- **Parameters**: Variable (depends on data)
- **Pros**: 
  - More flexible than Platt (can fit any monotonic shape)
  - Non-parametric (no assumptions about shape)
  - Often better calibration than Platt
- **Cons**: 
  - More complex (more parameters)
  - Can overfit with small calibration sets
  - Requires more data
- **Implementation**: Needs to be added to `scripts/lib/_winprob_lib.py`

### Pain Points

1. **Missing Isotonic Calibration**: Cannot compare Platt vs Isotonic without implementing Isotonic
2. **Missing CatBoost**: Cannot compare Logistic Regression vs CatBoost without CatBoost implementation
3. **No Comparison Framework**: No unified way to train and evaluate all 4 models
4. **Evaluation Inconsistency**: Each model type may need different evaluation approaches

### Business Impact

- **Performance Impact**: CatBoost may outperform Logistic Regression, Isotonic may outperform Platt
- **Decision Making**: Need comparison to choose best model for production
- **Research Impact**: Understanding which calibration method works better for each model type

### Success Criteria

- **[Criterion 1]**: All 4 models trained on same data splits
- **[Criterion 2]**: All 4 models evaluated on same test set (2024 season)
- **[Criterion 3]**: Side-by-side comparison of metrics (ECE, Brier, AUC, Log Loss)
- **[Criterion 4]**: Calibration plots for all 4 models

### Problem Complexity Assessment

**Scope Analysis**:
- **Files to Create**: 
  - `scripts/model/train_winprob_catboost.py` (new)
  - Isotonic calibration functions in `scripts/lib/_winprob_lib.py` (new)
- **Files to Modify**: 
  - `scripts/lib/_winprob_lib.py` (add Isotonic)
  - `scripts/model/evaluate_winprob_model.py` (support Isotonic)
  - `webapp/api/endpoints/model_evaluation.py` (support 4 models)
- **Estimated Effort**: 2-3 days
- **Technical Complexity**: Medium-High (new ML library integration, new calibration method)
- **Risk Level**: Medium (new dependencies, more complex models)

**Sprint Scope Recommendation**: Single Sprint (2-3 days)
- **Rationale**: Well-defined scope, clear deliverables
- **Recommended Approach**: 
  1. Implement Isotonic calibration first (simpler)
  2. Implement CatBoost training script
  3. Update evaluation to support all 4 models
  4. Train and evaluate all 4 models
  5. Create comparison visualization

## Current State Analysis

### Existing Implementation

#### 1. Logistic Regression + Platt (✅ Complete)

**Training Script**: `scripts/model/train_winprob_logreg.py`
- **Algorithm**: Custom IRLS implementation (no scikit-learn)
- **Calibration**: Platt scaling on calibration set
- **Artifact Format**: JSON with `platt` field containing `alpha` and `beta`
- **Example Artifact**: `artifacts/winprob_logreg_2017-2023_calib_2023.json`

**Key Code**:
```python
# Training (train_winprob_logreg.py, lines 403-449)
platt = fit_platt_calibrator_on_probs(p_base=p_base, y=y_calib)

# Prediction (scripts/lib/_winprob_lib.py, lines 245-251)
def predict_proba(artifact: WinProbArtifact, *, X: np.ndarray) -> np.ndarray:
    w = np.asarray(artifact.model.weights, dtype=np.float64)
    logits = X @ w + float(artifact.model.intercept)
    p = sigmoid(logits)
    if artifact.platt is not None:
        p = artifact.platt.apply(p)  # Apply Platt calibration
    return p
```

**Evaluation Results** (2024 season):
- ECE: 0.022156
- Brier: 0.154399
- AUC: 0.856225
- Log Loss: 0.462338

#### 2. Logistic Regression + Isotonic (❌ Missing)

**What's Needed**:
- Isotonic calibration implementation
- Update artifact format to support both Platt and Isotonic
- Training script option to choose calibration method

**Isotonic Regression Overview**:
- **Algorithm**: Piecewise linear monotonic function
- **Implementation**: Can use `scipy.stats.mquantiles` or `sklearn.isotonic.IsotonicRegression`
- **Formula**: `P_calibrated = isotonic_regression(P_base, y_calib)`
- **Parameters**: Variable number of breakpoints (depends on data)

**Example Implementation** (pseudo-code):
```python
from sklearn.isotonic import IsotonicRegression

def fit_isotonic_calibrator_on_probs(
    *, p_base: np.ndarray, y: np.ndarray
) -> IsotonicCalibrator:
    """Fit isotonic regression on base probabilities."""
    iso_reg = IsotonicRegression(out_of_bounds='clip')
    iso_reg.fit(p_base, y)
    return IsotonicCalibrator(iso_reg)

class IsotonicCalibrator:
    def __init__(self, iso_reg: IsotonicRegression):
        self.iso_reg = iso_reg
    
    def apply(self, p: np.ndarray) -> np.ndarray:
        return self.iso_reg.transform(p)
```

#### 3. CatBoost + Platt (❌ Missing)

**What's Needed**:
- CatBoost training script
- Integration with existing Platt calibration
- CatBoost artifact format

**CatBoost Overview**:
- **Library**: `catboost` Python package
- **Model Type**: `CatBoostClassifier` or `CatBoostRegressor`
- **Features**: Same as Logistic Regression
- **Training**: Requires hyperparameter tuning (iterations, depth, learning_rate, etc.)

**Example Implementation** (pseudo-code):
```python
from catboost import CatBoostClassifier

# Train CatBoost
model = CatBoostClassifier(
    iterations=1000,
    depth=6,
    learning_rate=0.1,
    loss_function='Logloss',
    eval_metric='AUC',
    verbose=100
)
model.fit(X_train, y_train, eval_set=(X_calib, y_calib))

# Get base probabilities
p_base = model.predict_proba(X_calib)[:, 1]

# Apply Platt calibration
platt = fit_platt_calibrator_on_probs(p_base=p_base, y=y_calib)
```

#### 4. CatBoost + Isotonic (❌ Missing)

**What's Needed**:
- CatBoost training script (same as #3)
- Isotonic calibration (same as #2)
- Combined implementation

### System Architecture Overview

**Current Pipeline** (Logistic Regression + Platt):
```
Raw ESPN Data
    ↓
Feature Engineering (point_diff, time_remaining, possession, interactions)
    ↓
Design Matrix (X)
    ↓
Logistic Regression (IRLS)
    ↓
Base Probabilities (P_base)
    ↓
Platt Calibration (sigmoid(alpha + beta * logit(P_base)))
    ↓
Calibrated Probabilities (P_calibrated)
```

**Required Pipeline** (All 4 Models):
```
Raw ESPN Data
    ↓
Feature Engineering
    ↓
┌─────────────────────┬─────────────────────┐
│ Logistic Regression │      CatBoost       │
│   (IRLS)            │  (Gradient Boost)  │
└─────────────────────┴─────────────────────┘
    ↓                        ↓
Base Probabilities (P_base)
    ↓
┌─────────────────────┬─────────────────────┐
│   Platt Scaling     │  Isotonic Regression│
│ (sigmoid transform) │ (piecewise linear)  │
└─────────────────────┴─────────────────────┘
    ↓                        ↓
Calibrated Probabilities
```

### Data Requirements

**Training Data**: Same for all models
- **Train Set**: season_start <= 2023 (2017-2023)
- **Calibration Set**: season_start == 2023
- **Test Set**: season_start == 2024

**Features**: Same for all models
- `point_differential_scaled`
- `time_remaining_regulation_scaled`
- `possession_home/away/unknown`
- Optional: `espn_home_prob`, lagged features, period, interactions

**Labels**: Same for all models
- `y_home_win = 1` if `final_winning_team == 0`, else `0`

## Technical Implementation Plan

### Phase 1: Implement Isotonic Calibration

**Files to Modify**:
- `scripts/lib/_winprob_lib.py`

**Changes**:
1. Add `IsotonicCalibrator` dataclass
2. Add `fit_isotonic_calibrator_on_probs()` function
3. Update `WinProbArtifact` to support both `platt` and `isotonic` fields
4. Update `predict_proba()` to apply isotonic if present
5. Update `save_artifact()` and `load_artifact()` to handle isotonic

**Dependencies**:
- `scikit-learn` (for `IsotonicRegression`) - may already be available

**Estimated Effort**: 4-6 hours

### Phase 2: Implement CatBoost Training

**Files to Create**:
- `scripts/model/train_winprob_catboost.py`

**Changes**:
1. Create training script similar to `train_winprob_logreg.py`
2. Use CatBoost instead of IRLS
3. Support both Platt and Isotonic calibration
4. Save artifact in compatible format

**Dependencies**:
- `catboost` package (need to add to requirements)

**Estimated Effort**: 8-12 hours

### Phase 3: Update Evaluation Script

**Files to Modify**:
- `scripts/model/evaluate_winprob_model.py`

**Changes**:
1. Support CatBoost artifacts (load model differently)
2. Support Isotonic calibration in prediction
3. Add model type to evaluation report
4. Update calibration plot labels

**Estimated Effort**: 4-6 hours

### Phase 4: Train All 4 Models

**Commands**:
```bash
# 1. Logistic Regression + Platt (already exists)
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_platt.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --dsn "$DATABASE_URL"

# 2. Logistic Regression + Isotonic
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_isotonic.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --dsn "$DATABASE_URL"

# 3. CatBoost + Platt
./.venv/bin/python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_2017-2023_platt.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --dsn "$DATABASE_URL"

# 4. CatBoost + Isotonic
./.venv/bin/python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_2017-2023_isotonic.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --dsn "$DATABASE_URL"
```

**Estimated Effort**: 2-4 hours (training time depends on data size)

### Phase 5: Evaluate and Compare

**Commands**:
```bash
# Evaluate all 4 models
for artifact in artifacts/winprob_*_2017-2023_*.json; do
    name=$(basename $artifact .json)
    ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
      --artifact "$artifact" \
      --season-start 2024 \
      --out "data/models/evaluations/${name}_on_2024.json" \
      --plot-calibration \
      --dsn "$DATABASE_URL"
done
```

**Comparison Script**:
- Create comparison visualization showing all 4 models side-by-side
- Compare metrics: ECE, Brier, AUC, Log Loss
- Compare calibration plots

**Estimated Effort**: 4-6 hours

## Expected Outcomes

### Model Comparison Matrix

| Model Type | Calibration | Expected ECE | Expected Brier | Expected AUC | Notes |
|------------|-------------|--------------|----------------|--------------|-------|
| Logistic Regression | Platt | 0.022 | 0.154 | 0.856 | Current baseline |
| Logistic Regression | Isotonic | ~0.020 | ~0.154 | 0.856 | May be slightly better calibrated |
| CatBoost | Platt | ~0.018 | ~0.152 | ~0.860 | May have better discrimination |
| CatBoost | Isotonic | ~0.016 | ~0.151 | ~0.860 | Best expected performance |

### Key Questions to Answer

1. **Does CatBoost outperform Logistic Regression?**
   - Hypothesis: Yes, due to non-linear patterns
   - Metric: AUC (discrimination)

2. **Does Isotonic outperform Platt?**
   - Hypothesis: Yes, due to flexibility
   - Metric: ECE (calibration)

3. **Which combination is best?**
   - Hypothesis: CatBoost + Isotonic
   - Metric: Overall (Brier score balances calibration and discrimination)

## Risks and Mitigation

### Risk 1: CatBoost Overfitting
- **Risk**: CatBoost may overfit to training data
- **Mitigation**: Use early stopping, cross-validation, regularization
- **Detection**: Compare train vs test metrics

### Risk 2: Isotonic Overfitting
- **Risk**: Isotonic regression may overfit with small calibration set
- **Mitigation**: Ensure calibration set has sufficient samples (>= 1000)
- **Detection**: Compare calibration set vs test set ECE

### Risk 3: Dependency Management
- **Risk**: Adding `catboost` and `scikit-learn` may cause conflicts
- **Mitigation**: Test in isolated environment, update requirements.txt
- **Detection**: Run tests after installation

### Risk 4: Evaluation Inconsistency
- **Risk**: Different model types may need different evaluation approaches
- **Mitigation**: Use same evaluation script for all models
- **Detection**: Compare evaluation outputs

## Recommendations

### Immediate Actions (This Sprint)

1. **Implement Isotonic Calibration** (Priority: High)
   - Add to `_winprob_lib.py`
   - Test on existing Logistic Regression model
   - Compare Platt vs Isotonic on same base model

2. **Implement CatBoost Training** (Priority: High)
   - Create `train_winprob_catboost.py`
   - Use same features as Logistic Regression
   - Support both calibration methods

3. **Train All 4 Models** (Priority: Medium)
   - Use same data splits for fair comparison
   - Save artifacts with clear naming convention

4. **Evaluate and Compare** (Priority: Medium)
   - Generate evaluation reports for all 4 models
   - Create comparison visualization
   - Document findings

### Future Considerations

1. **Hyperparameter Tuning**: CatBoost has many hyperparameters that could be tuned
2. **Feature Engineering**: CatBoost may benefit from different features
3. **Ensemble Methods**: Could combine predictions from multiple models
4. **Online Calibration**: Update calibration as new data arrives

## Conclusion

The friend's request for a 2×2 model matrix (Logistic Regression vs CatBoost, Platt vs Isotonic) is a well-defined research question that will help determine the best model and calibration method combination.

**Current State**: 1 of 4 models exists (Logistic Regression + Platt)

**Required Work**: 
- Implement Isotonic calibration
- Implement CatBoost training
- Train and evaluate all 4 models
- Compare results

**Expected Outcome**: Clear understanding of which model type and calibration method performs best for win probability prediction.

**Next Steps**: Begin with Isotonic calibration implementation, then CatBoost training script.

