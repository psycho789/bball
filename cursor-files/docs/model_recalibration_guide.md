# Model Re-calibration Guide

This guide explains when and how to re-calibrate the win-probability model using Platt scaling.

## When to Re-calibrate

Re-calibration should be considered in the following scenarios:

1. **Model Drift**: Model performance degrades over time (e.g., ECE increases on recent data)
2. **New Season Data**: New season data becomes available and you want to update calibration
3. **Distribution Shift**: Game characteristics change significantly (e.g., rule changes, style changes)
4. **Regular Maintenance**: Periodic re-calibration as part of model maintenance (e.g., annually)

**Note**: Re-calibration does NOT retrain the base model weights. It only updates the Platt scaling parameters (alpha, beta) to better match observed win rates.

## Re-calibration Process Overview

The re-calibration process involves:

1. **Select Calibration Dataset**: Choose a season or time period for calibration
2. **Train Model** (if needed): Train new model or use existing model artifact
3. **Extract Base Probabilities**: Get model predictions without Platt calibration
4. **Fit Platt Calibrator**: Fit Platt scaling parameters on calibration dataset
5. **Update Artifact**: Save updated artifact with new Platt parameters
6. **Evaluate**: Evaluate calibration quality on test data

## Step-by-Step Re-calibration Instructions

### Step 1: Prepare Calibration Dataset

Decide which season to use for calibration. Common choices:
- **Recent season**: Use most recent complete season (e.g., 2024 for 2025 calibration)
- **Hold-out season**: Use a season not used for training or testing
- **Multiple seasons**: Combine multiple seasons for larger calibration set

**Requirements**:
- Calibration dataset should have at least 5 samples (preferably many more)
- Should be representative of future data distribution
- Should not overlap with training or test datasets

### Step 2: Train Model (if needed)

If you need to train a new model, use the training script:

```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v5.json \
  --train-season-start-max 2023 \
  --calib-season-start 2024 \
  --test-season-start 2025 \
  --dsn "$DATABASE_URL"
```

**Key Parameters**:
- `--train-season-start-max`: Maximum season for training data
- `--calib-season-start`: Season to use for Platt calibration
- `--test-season-start`: Season to hold out for testing
- `--disable-calibration`: Use this flag to train model WITHOUT calibration (for manual calibration)

### Step 3: Re-calibrate Existing Model

If you want to re-calibrate an existing model on new data, you have two options:

#### Option A: Use Training Script with New Calibration Season

```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v4_recalibrated.json \
  --train-season-start-max 2023 \
  --calib-season-start 2024 \
  --test-season-start 2025 \
  --dsn "$DATABASE_URL"
```

This will:
1. Load existing model weights (or train new ones)
2. Extract base probabilities on calibration season (2024)
3. Fit new Platt calibrator
4. Save updated artifact

#### Option B: Manual Re-calibration (Python Script)

Create a custom script to re-calibrate:

```python
from scripts.lib._winprob_lib import (
    load_artifact,
    build_design_matrix,
    predict_proba,
    fit_platt_calibrator_on_probs,
    save_artifact,
    WinProbArtifact,
)
from scripts.model.evaluate_winprob_model import _load_evaluation_data
from scripts.lib._db_lib import connect, get_dsn
from pathlib import Path
import numpy as np

# Load existing artifact
artifact = load_artifact(Path("artifacts/winprob_logreg_v4_historical.json"))

# Load calibration data
dsn = get_dsn()
calib_season = 2024
with connect(dsn) as conn:
    df = _load_evaluation_data(conn, calib_season, artifact)

df = df[df["final_winning_team"].notna()].copy()
y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)

# Build design matrix
build_matrix_kwargs = {
    "point_differential": df["point_differential"].to_numpy(),
    "time_remaining_regulation": df["time_remaining_regulation"].to_numpy(),
    "possession": df["possession"].astype(str).tolist(),
    "preprocess": artifact.preprocess,
}
# Add interaction terms if needed
# ... (see training script for full implementation)

X = build_design_matrix(**build_matrix_kwargs)

# Get base probabilities (without Platt calibration)
# Create temporary artifact without Platt
art_base = WinProbArtifact(
    created_at_utc=artifact.created_at_utc,
    version=artifact.version,
    train_season_start_max=artifact.train_season_start_max,
    calib_season_start=calib_season,  # Update calibration season
    test_season_start=artifact.test_season_start,
    buckets_seconds_remaining=artifact.buckets_seconds_remaining,
    preprocess=artifact.preprocess,
    feature_names=artifact.feature_names,
    model=artifact.model,
    platt=None,  # No Platt calibration
)
p_base = predict_proba(art_base, X=X)

# Fit new Platt calibrator
platt_new = fit_platt_calibrator_on_probs(p_base=p_base, y=y)

# Create updated artifact
artifact_new = WinProbArtifact(
    created_at_utc=artifact.created_at_utc,  # Keep original creation time or update
    version=artifact.version,  # Or increment version
    train_season_start_max=artifact.train_season_start_max,
    calib_season_start=calib_season,  # New calibration season
    test_season_start=artifact.test_season_start,
    buckets_seconds_remaining=artifact.buckets_seconds_remaining,
    preprocess=artifact.preprocess,
    feature_names=artifact.feature_names,
    model=artifact.model,  # Keep same model weights
    platt=platt_new,  # New Platt calibrator
)

# Save updated artifact
save_artifact(Path("artifacts/winprob_logreg_v4_recalibrated.json"), artifact_new)
```

### Step 4: Disable Calibration (if needed)

To train a model WITHOUT Platt calibration (e.g., for comparison or manual calibration):

```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v5_no_calib.json \
  --train-season-start-max 2023 \
  --calib-season-start 2024 \
  --disable-calibration \
  --dsn "$DATABASE_URL"
```

This will create an artifact with `platt: null`, meaning no calibration is applied during prediction.

### Step 5: Evaluate Re-calibration

After re-calibrating, evaluate the model on test data:

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_recalibrated.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2025_recalibrated.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Key Metrics to Check**:
- **ECE (Expected Calibration Error)**: Should be lower than before (target: < 0.01)
- **Brier Score**: Should be lower or similar
- **AUC**: Should remain unchanged (calibration doesn't affect discrimination)
- **Log Loss**: Should be lower or similar

### Step 6: Compare Before/After

Compare calibration quality before and after re-calibration:

```bash
# Before re-calibration
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2025_before.json \
  --plot-calibration

# After re-calibration
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_recalibrated.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2025_after.json \
  --plot-calibration

# Compare metrics
python3 -c "
import json
before = json.load(open('data/reports/winprob_eval_2025_before.json'))
after = json.load(open('data/reports/winprob_eval_2025_after.json'))
print('Before ECE:', before['eval']['overall']['ece_binned'])
print('After ECE:', after['eval']['overall']['ece_binned'])
print('Improvement:', before['eval']['overall']['ece_binned'] - after['eval']['overall']['ece_binned'])
"
```

## Calibration Dataset Selection

### Best Practices

1. **Size**: Use at least 1,000 samples (preferably 10,000+)
2. **Representativeness**: Should match distribution of future data
3. **Temporal Order**: Use recent data for calibration if possible
4. **No Overlap**: Don't use same data for training and calibration

### Common Patterns

- **Annual Re-calibration**: Use previous season for calibration (e.g., calibrate 2025 model on 2024 data)
- **Rolling Window**: Use last N seasons for calibration
- **Single Season**: Use one complete season (e.g., 2024 season for 2025 calibration)

## Troubleshooting

### Issue: Calibration Fails (Returns None)

**Cause**: Insufficient calibration data (< 5 samples) or numerical issues

**Solution**:
- Ensure calibration dataset has at least 5 samples
- Check for NaN or invalid values in predictions
- Verify calibration data has both positive and negative examples

### Issue: Calibration Doesn't Improve ECE

**Possible Causes**:
- Base model is already well-calibrated (beta ≈ 1.0, alpha ≈ 0.0)
- Calibration dataset is too small
- Distribution mismatch between calibration and test data

**Solution**:
- Check Platt parameters (if beta ≈ 1.0 and alpha ≈ 0.0, model is already calibrated)
- Use larger calibration dataset
- Ensure calibration dataset matches test distribution

### Issue: Calibration Worsens Performance

**Possible Causes**:
- Overfitting on small calibration dataset
- Distribution shift between calibration and test data

**Solution**:
- Use larger calibration dataset
- Use cross-validation or hold-out validation
- Check for distribution shifts

## Example: Complete Re-calibration Workflow

```bash
# 1. Train model with calibration disabled (to get base model)
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v5_base.json \
  --train-season-start-max 2023 \
  --calib-season-start 2024 \
  --disable-calibration \
  --dsn "$DATABASE_URL"

# 2. Re-calibrate on new season (2024)
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v5_recalibrated.json \
  --train-season-start-max 2023 \
  --calib-season-start 2024 \
  --test-season-start 2025 \
  --dsn "$DATABASE_URL"

# 3. Evaluate on test season (2025)
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v5_recalibrated.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2025_recalibrated.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"

# 4. Check metrics
python3 -c "
import json
data = json.load(open('data/reports/winprob_eval_2025_recalibrated.json'))
print('ECE:', data['eval']['overall']['ece_binned'])
print('Brier:', data['eval']['overall']['brier'])
print('AUC:', data['eval']['overall']['roc_auc'])
"
```

## Related Documentation

- **Probability Pipeline**: See `cursor-files/docs/platt_espn_odds_probability_pipeline.md`
- **Model Training**: See `scripts/model/train_winprob_logreg.py`
- **Model Evaluation**: See `scripts/model/evaluate_winprob_model.py`
- **Core Library**: See `scripts/lib/_winprob_lib.py`

## Summary

Re-calibration is a straightforward process that updates Platt scaling parameters to improve probability calibration. The key steps are:

1. Select appropriate calibration dataset
2. Extract base model probabilities
3. Fit new Platt calibrator
4. Update artifact with new parameters
5. Evaluate on test data

Remember: Re-calibration only updates calibration parameters, not the base model weights. For best results, use a representative calibration dataset with sufficient samples.

