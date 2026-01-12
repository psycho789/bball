# Train vs. Evaluate Script Comparison

## Quick Answer: Are They Different?

**YES, they are significantly different** - they serve complementary purposes:
- **`train_winprob_logreg.py`**: Creates models from scratch
- **`evaluate_winprob_model.py`**: Tests existing models

## Detailed Comparison

### Purpose

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `train_winprob_logreg.py` | Train a new model | Raw data from database | Model artifact JSON |
| `evaluate_winprob_model.py` | Evaluate existing model | Model artifact JSON | Evaluation report JSON + plots |

### Key Differences

#### 1. **Model Creation vs. Model Testing**

**Train Script**:
- Fits logistic regression weights from scratch
- Optionally fits Platt calibration parameters
- Creates a complete model artifact

**Evaluate Script**:
- Loads pre-trained model artifact
- Makes predictions using existing weights
- Calculates performance metrics

#### 2. **Arguments Comparison**

**Arguments from Train Script**:
- `--train-season-start-max`: ✅ **NOT NEEDED** - evaluation doesn't train
- `--calib-season-start`: ✅ **NOT NEEDED** - calibration already in artifact
- `--disable-calibration`: ✅ **ADDED** - useful for comparing calibrated vs. uncalibrated
- `--test-season-start`: ✅ **NOT NEEDED** - we specify season directly
- `--l2-lambda`: ✅ **NOT NEEDED** - already in artifact
- `--max-iter`: ✅ **NOT NEEDED** - already in artifact
- `--tol`: ✅ **NOT NEEDED** - already in artifact
- `--min-train-rows`: ✅ **NOT NEEDED** - we're not training
- `--bucket-step-seconds`: ✅ **NOT NEEDED** - already in artifact
- `--use-interaction-terms`: ✅ **NOT NEEDED** - auto-detected from artifact
- `--version`: ✅ **NOT NEEDED** - already in artifact

**Arguments in Evaluate Script**:
- `--artifact`: ✅ **NEEDED** - specifies which model to test
- `--season-start`: ✅ **NEEDED** - which season to evaluate
- `--out`: ✅ **NEEDED** - where to write report
- `--bins`: ✅ **NEEDED** - for ECE calculation (not in train)
- `--plot-calibration`: ✅ **NEEDED** - for visualization (not in train)
- `--verbose`: ✅ **ADDED** - for detailed logging
- `--workers`: ✅ **ADDED** - for parallel processing (not yet implemented)
- `--disable-calibration`: ✅ **ADDED** - for comparison

#### 3. **Data Loading**

**Train Script**:
- Loads data for training, calibration, and test seasons
- Filters by `train_season_start_max`, `calib_season_start`, `test_season_start`
- Calculates normalization parameters from training data

**Evaluate Script**:
- Loads data for single evaluation season
- Uses normalization parameters from artifact (already calculated)
- Auto-detects interaction terms from artifact feature names

#### 4. **Processing Steps**

**Train Script**:
1. Load data
2. Calculate normalization parameters
3. Build design matrix for training
4. Fit logistic regression (IRLS)
5. Optionally fit Platt calibrator
6. Save artifact

**Evaluate Script**:
1. Load artifact
2. Load evaluation data
3. Build design matrix (using artifact's normalization)
4. Make predictions
5. Calculate metrics
6. Generate reports

#### 5. **Output**

**Train Script**:
- Model artifact JSON (weights, preprocess params, Platt params)

**Evaluate Script**:
- Evaluation report JSON (metrics, calibration bins, per-bucket stats)
- Optional SVG calibration plots

## Why We Need Both Scripts

### Train Script is Needed For:
- Creating new models
- Updating models with new data
- Experimenting with hyperparameters
- Re-calibrating models

### Evaluate Script is Needed For:
- Validating model performance
- Monitoring model drift
- Comparing model versions
- Generating reports for stakeholders
- Assessing calibration quality

## When to Use Each

### Use `train_winprob_logreg.py` When:
- ✅ Creating a new model
- ✅ Retraining with new data
- ✅ Adjusting hyperparameters
- ✅ Re-calibrating on new season

### Use `evaluate_winprob_model.py` When:
- ✅ Testing model on held-out data
- ✅ Monitoring model performance over time
- ✅ Comparing model versions
- ✅ Generating evaluation reports
- ✅ Assessing calibration quality

## Summary

The scripts are **complementary but distinct**:
- **Train**: Creates models (one-time or periodic)
- **Evaluate**: Tests models (frequent, for monitoring)

Both are essential for a complete ML pipeline. The evaluation script is **significantly different** from the training script - it's not redundant, it's necessary for model validation and monitoring.

