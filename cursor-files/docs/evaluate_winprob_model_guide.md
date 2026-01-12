# Model Evaluation Script Guide: `evaluate_winprob_model.py`

## Overview

`evaluate_winprob_model.py` evaluates a trained win-probability model artifact on a held-out season. It calculates performance metrics, generates calibration plots, and produces detailed evaluation reports.

## Purpose

This script is **essential** for:
- **Model Validation**: Testing model performance on unseen data
- **Calibration Assessment**: Evaluating how well-calibrated probabilities are
- **Model Monitoring**: Tracking model performance over time (drift detection)
- **Production Readiness**: Verifying model quality before deployment

## What It Does

1. **Loads Model Artifact**: Reads a trained model JSON file (created by `train_winprob_logreg.py`)
2. **Loads Evaluation Data**: Queries ESPN tables for a specific seasoncompari
3. **Makes Predictions**: Generates win probabilities for all game snapshots
4. **Calculates Metrics**: Computes overall and per-bucket performance metrics:
   - **Log Loss**: Negative log-likelihood (lower is better)
   - **Brier Score**: Mean squared error (lower is better)
   - **ECE (Expected Calibration Error)**: Calibration quality (lower is better, target < 0.01)
   - **AUC (Area Under ROC Curve)**: Discrimination ability (higher is better, 0.5-1.0)
5. **Generates Reports**: Creates JSON report and optional SVG calibration plots

## How It Works

### Data Flow

```
Model Artifact (JSON)
    ↓
Load Artifact (weights, preprocess params, Platt calibration)
    ↓
Query ESPN Tables (season_start filter)
    ↓
Build Design Matrix (scale features, add interaction terms)
    ↓
Make Predictions (logistic regression + Platt calibration)
    ↓
Calculate Metrics (overall + per time-bucket)
    ↓
Generate Reports (JSON + optional SVG plots)
```

### Key Differences from Training Script

| Aspect | `train_winprob_logreg.py` | `evaluate_winprob_model.py` |
|--------|---------------------------|-----------------------------|
| **Purpose** | Create new model | Test existing model |
| **Input** | Raw data from database | Pre-trained artifact JSON |
| **Output** | Model artifact JSON | Evaluation report JSON + plots |
| **Hyperparameters** | Many (l2-lambda, max-iter, etc.) | None (already in artifact) |
| **Interaction Terms** | Configurable (--use-interaction-terms) | Auto-detected from artifact |
| **Calibration** | Can enable/disable | Uses what's in artifact |
| **Metrics** | Training metrics | Evaluation metrics (ECE, AUC, etc.) |

**Key Insight**: The evaluation script is **significantly different** from the training script. They serve complementary purposes:
- **Train**: Creates models from scratch
- **Evaluate**: Tests existing models

## Usage

### Basic Usage

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --dsn "$DATABASE_URL"
```

### With Calibration Plots

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

### With Verbose Logging

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --verbose \
  --dsn "$DATABASE_URL"
```

### With Parallel Processing (for large datasets)

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --workers 4 \
  --dsn "$DATABASE_URL"
```

## Command-Line Arguments

### Required Arguments

- `--artifact`: Path to model artifact JSON file (e.g., `artifacts/winprob_logreg_v4_historical.json`)
- `--season-start`: Season start year to evaluate (e.g., `2024`)
- `--out`: Output JSON report path (e.g., `data/reports/winprob_eval_2024.json`)

### Optional Arguments

- `--dsn`: Database connection string (default: uses `DATABASE_URL` environment variable)
- `--bins`: Number of bins for ECE/reliability calculation (default: `20`)
- `--plot-calibration`: Generate SVG calibration plots (default: `False`)
- `--verbose`: Enable verbose logging with detailed progress information (default: `False`)
- `--workers`: Number of parallel workers for per-bucket metrics (default: `1`, no parallelization)
- `--disable-calibration`: Evaluate model without Platt calibration (for comparison) (default: `False`)

## Output Files

### JSON Report (`--out`)

Contains:
- **Overall Metrics**: Log loss, Brier score, ECE, AUC, prevalence
- **Calibration Bins**: Per-bin calibration statistics
- **Per-Bucket Metrics**: Metrics broken down by time remaining (60-second buckets)
- **Artifact Metadata**: Model version, training info, Platt parameters

### SVG Plots (if `--plot-calibration`)

- **`<out>.calibration.svg`**: Simple reliability diagram
- **`<out>.calibration_context.svg`**: Reliability diagram with metrics panel

## Example Output

```
Wrote data/reports/winprob_eval_2024.json
overall logloss=0.462338 brier=0.154399 ece=0.022156 auc=0.856225
Wrote data/reports/winprob_eval_2024.calibration.svg
Wrote data/reports/winprob_eval_2024.calibration_context.svg
```

## Interpreting Results

### Good Model Performance

- **ECE < 0.01**: Well-calibrated probabilities
- **AUC > 0.85**: Excellent discrimination
- **Brier Score < 0.20**: Good overall accuracy
- **Log Loss < 0.50**: Good probability estimates

### Warning Signs

- **ECE > 0.05**: Poor calibration (probabilities don't match observed frequencies)
- **AUC < 0.70**: Poor discrimination (model can't distinguish classes well)
- **Brier Score > 0.25**: Poor overall accuracy

## Common Use Cases

### 1. Model Validation (After Training)

```bash
# Train model
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_v5.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024

# Evaluate on test season
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v5.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_2024.json \
  --plot-calibration
```

### 2. Model Drift Detection (Monitoring)

```bash
# Evaluate on current season
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2025 \
  --out data/models/evaluations/winprob_drift_2025.json \
  --plot-calibration

# Compare with previous evaluation
python3 -c "
import json
prev = json.load(open('data/reports/winprob_eval_2024.json'))
curr = json.load(open('data/reports/winprob_drift_2025.json'))
print(f'ECE change: {prev[\"eval\"][\"overall\"][\"ece_binned\"]:.4f} -> {curr[\"eval\"][\"overall\"][\"ece_binned\"]:.4f}')
"
```

### 3. Calibration Comparison

```bash
# Evaluate with calibration
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_calibrated.json

# Evaluate without calibration (requires artifact modification)
# See model_recalibration_guide.md for details
```

## Troubleshooting

### Issue: "No rows found for season_start=X"

**Cause**: No data available for that season in database

**Solution**: 
- Check available seasons: `SELECT DISTINCT season_start FROM espn.probabilities_raw_items`
- Use a season that exists in the database

### Issue: "Artifact file not found"

**Cause**: Artifact path is incorrect

**Solution**:
- Verify artifact exists: `ls -lh artifacts/winprob_logreg_*.json`
- Use correct path relative to repo root

### Issue: "Feature mismatch" errors

**Cause**: Artifact was trained with different features than evaluation expects

**Solution**:
- Ensure artifact and evaluation script are compatible
- Check artifact `feature_names` match expected features

## Performance Considerations

- **Large Datasets**: Use `--workers` for parallel processing of per-bucket metrics
- **Memory Usage**: Large seasons (600K+ rows) may require significant memory
- **Database Queries**: Evaluation queries can be slow; consider indexing `season_start` column

## Related Documentation

- **Model Training**: `scripts/model/train_winprob_logreg.py`
- **Probability Pipeline**: `cursor-files/docs/platt_espn_odds_probability_pipeline.md`
- **Re-calibration Guide**: `cursor-files/docs/model_recalibration_guide.md`
- **Core Library**: `scripts/lib/_winprob_lib.py`

## Summary

`evaluate_winprob_model.py` is a **critical tool** for model validation and monitoring. It's different from the training script (which creates models) - this script tests existing models. Use it to:
- Validate model performance after training
- Monitor model drift over time
- Assess calibration quality
- Generate reports for stakeholders

