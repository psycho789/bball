# Evaluate WinProb Model Script Improvements

**Date**: 2026-01-11  
**Script**: `scripts/model/evaluate_winprob_model.py`

## Summary of Changes

Added three new command-line arguments and comprehensive verbose logging to improve usability and debugging capabilities.

## New Features

### 1. `--verbose` Flag ✅

**Purpose**: Enable detailed logging with progress information

**Usage**:
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --verbose
```

**What It Logs**:
- Script start/end times
- Artifact loading details (version, creation time)
- Data loading progress (row counts, timing)
- Design matrix building (shape, timing)
- Prediction statistics (mean, std, min, max)
- Metric calculation progress
- Per-bucket processing progress (every 10 buckets)
- Overall timing information

**Example Output**:
```
2026-01-11 16:38:49 [INFO] Starting evaluation: artifact=artifacts/winprob_logreg_v4_historical.json, season_start=2024
2026-01-11 16:38:49 [DEBUG] Loaded artifact: version=v1, created_at=20260111T152418Z
2026-01-11 16:38:49 [INFO] Loading evaluation data for season_start=2024
2026-01-11 16:40:26 [DEBUG] Loaded 660185 rows from database in 96.86s
2026-01-11 16:40:26 [DEBUG] Design matrix shape: (660185, 13), built in 1.52s
2026-01-11 16:40:28 [DEBUG] Prediction stats: mean=0.5453, std=0.3154, min=0.0000, max=1.0000
2026-01-11 16:40:31 [INFO] Evaluation completed in 101.36s
```

### 2. `--workers` Flag ⚠️

**Purpose**: Parallel processing for per-bucket metrics (currently not implemented)

**Status**: Flag added but functionality not yet implemented due to artifact pickling limitations

**Usage**:
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --workers 4
```

**Current Behavior**: 
- Flag accepted but generates warning
- Falls back to sequential processing
- Future implementation may use threading or alternative parallelization

**Why Not Implemented**:
- Artifact contains frozen dataclasses that don't pickle easily
- Would require refactoring artifact structure or using alternative parallelization (threading)
- Sequential processing is fast enough for current use cases (~2 seconds for 59 buckets)

### 3. `--disable-calibration` Flag ✅

**Purpose**: Evaluate model without Platt calibration for comparison

**Usage**:
```bash
# With calibration (default)
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_calibrated.json

# Without calibration (for comparison)
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_no_calib.json \
  --disable-calibration
```

**Use Cases**:
- Compare calibrated vs. uncalibrated performance
- Assess if Platt calibration improves or worsens metrics
- Debug calibration issues

**Example Comparison**:
```
With calibration:    ECE=0.022156, Brier=0.154399
Without calibration: ECE=0.019794, Brier=0.154190
```

**Implementation**: Creates temporary artifact with `platt=None` for evaluation

## Documentation Added

### 1. Usage Guide
**File**: `cursor-files/docs/evaluate_winprob_model_guide.md`

Comprehensive guide covering:
- Overview and purpose
- What the script does
- How it works (data flow)
- Usage examples
- Command-line arguments
- Output files
- Interpreting results
- Common use cases
- Troubleshooting

### 2. Train vs. Evaluate Comparison
**File**: `cursor-files/docs/train_vs_evaluate_comparison.md`

Detailed comparison explaining:
- Why both scripts are needed
- Key differences
- When to use each
- Arguments comparison

## Code Quality Improvements

### Logging Infrastructure
- Added `logging` module with configurable levels
- INFO level for major steps
- DEBUG level for detailed progress
- Timing information for performance analysis

### Error Handling
- Better error messages with context
- Progress tracking for long-running operations
- Clear warnings for unimplemented features

### Code Organization
- Separated logging setup into `_setup_logging()` function
- Added timing measurements throughout
- Improved code comments

## Testing Results

### Verbose Logging Test ✅
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_test.json \
  --verbose
```
**Result**: Works perfectly, provides detailed progress information

### Disable Calibration Test ✅
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_no_calib.json \
  --disable-calibration
```
**Result**: Successfully evaluates without Platt calibration, metrics differ as expected

### Workers Flag Test ✅
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_v4_historical.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024_test.json \
  --workers 4
```
**Result**: Accepts flag, warns about not being implemented, falls back to sequential

## Comparison with Train Script

### Arguments from Train Script: Do We Need Them?

| Argument | Needed? | Reason |
|----------|---------|--------|
| `--train-season-start-max` | ❌ NO | Evaluation doesn't train |
| `--calib-season-start` | ❌ NO | Calibration already in artifact |
| `--disable-calibration` | ✅ YES | **ADDED** - useful for comparison |
| `--test-season-start` | ❌ NO | We specify season directly |
| `--l2-lambda` | ❌ NO | Already in artifact |
| `--max-iter` | ❌ NO | Already in artifact |
| `--tol` | ❌ NO | Already in artifact |
| `--min-train-rows` | ❌ NO | We're not training |
| `--bucket-step-seconds` | ❌ NO | Already in artifact |
| `--use-interaction-terms` | ❌ NO | Auto-detected from artifact |
| `--version` | ❌ NO | Already in artifact |

**Conclusion**: Only `--disable-calibration` was useful from the train script arguments. The evaluation script correctly auto-detects model configuration from the artifact.

## Are the Scripts Different?

**YES, significantly different:**

| Aspect | Train Script | Evaluate Script |
|--------|-------------|-----------------|
| **Purpose** | Create models | Test models |
| **Input** | Raw database data | Model artifact |
| **Output** | Model artifact | Evaluation report |
| **Processing** | Fits weights, calibrates | Makes predictions, calculates metrics |
| **Arguments** | Many hyperparameters | Few evaluation-specific args |

**Verdict**: The scripts are **complementary but distinct**. Both are essential:
- **Train**: Creates models (one-time or periodic)
- **Evaluate**: Tests models (frequent, for monitoring)

## Future Improvements

### Potential Enhancements
1. **Implement Parallel Processing**: Use threading or refactor artifact for pickling
2. **Add More Metrics**: Per-game metrics, confusion matrices
3. **Add Export Options**: CSV export, different plot formats
4. **Add Comparison Mode**: Compare multiple artifacts side-by-side
5. **Add Drift Detection**: Automatic comparison with previous evaluations

## Summary

The evaluation script has been enhanced with:
- ✅ **Verbose logging** for detailed progress tracking
- ✅ **Disable calibration flag** for comparison
- ⚠️ **Workers flag** (placeholder, not yet implemented)
- ✅ **Comprehensive documentation** (usage guide + comparison)

The script is **significantly different** from the training script and serves a distinct, essential purpose in the ML pipeline.

