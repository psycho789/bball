# Sprint Implementation Summary: Pre-Game Odds Model Integration

**Date**: 2026-01-15  
**Sprint**: S1 - Pre-Game Odds Model Integration  
**Status**: Phases 1-4 Complete, Phase 5 Pending

## Implementation Complete ✅

All development work for Phases 1-4 is complete. The code is ready for testing and evaluation.

---

## Phase 1: Parity Validation ✅

**Status**: Complete

**Deliverables**:
- ✅ Parity validation report documenting 94.8% data loss in canonical dataset
- ✅ Decision: Option B (ESPN-direct + opening odds join)

**Files Created**:
- `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md`

**Key Finding**: Canonical dataset only has 2024-2025 seasons, excluding 7 seasons of training data (2017-2023).

---

## Phase 2: Feature Engineering ✅

**Status**: Complete

**Deliverables**:
- ✅ Odds format validation (decimal format confirmed)
- ✅ Shared de-vigging helper function
- ✅ Opening odds feature engineering in training data loading

**Files Created**:
- `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md`

**Files Modified**:
- `scripts/lib/_winprob_lib.py` - Added `compute_opening_odds_features()` helper
- `scripts/model/train_winprob_catboost.py` - Updated `_load_training_data()` to join opening odds

**Key Features**:
- Decimal odds conversion: `p = 1 / odds`
- De-vigging with safety checks (only if both odds present and > 1.0)
- Missingness indicator flags for CatBoost

---

## Phase 3: Design Matrix and Training Integration ✅

**Status**: Complete

**Deliverables**:
- ✅ Canonical feature list (`ODDS_FEATURES` constant)
- ✅ Extended `build_design_matrix()` with opening odds parameters
- ✅ Updated training script to pass opening odds
- ✅ Updated pre-computation script to use opening odds

**Files Modified**:
- `scripts/lib/_winprob_lib.py` - Added `ODDS_FEATURES` constant, extended `build_design_matrix()`
- `scripts/model/train_winprob_catboost.py` - Added opening odds to training and calibration sets
- `scripts/model/precompute_model_probabilities.py` - Added opening odds support

**Key Features**:
- Canonical feature ordering (prevents bugs from inconsistent ordering)
- Backward compatible (opening odds are optional parameters)
- Automatic feature detection (checks if model expects opening odds)

---

## Phase 4: Model Training and Evaluation ✅

**Status**: Complete (Infrastructure Ready)

**Deliverables**:
- ✅ Split reproducibility infrastructure (fixed random seed + split file persistence)
- ✅ Time-bucketed evaluation script
- ✅ Commands document for training and evaluation

**Files Created**:
- `scripts/model/evaluate_winprob_time_buckets.py` - Time-bucketed evaluation script
- `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/phase4-commands.md` - Commands guide

**Files Modified**:
- `scripts/model/train_winprob_catboost.py` - Added `--disable-opening-odds` flag and `--save-split-file` option

**Ready for Execution**: All code is ready. User needs to run training and evaluation commands (see `phase4-commands.md`).

---

## Commands to Run

### 1. Train Baseline Model (Without Opening Odds)

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_sprint1.json \
  --dsn "$DATABASE_URL" \
  --train-season-start-max 2022 \
  --test-season-start 2024 \
  --calib-season-start 2023 \
  --calibration-method platt \
  --iterations 1000 \
  --depth 6 \
  --learning-rate 0.1 \
  --disable-opening-odds \
  --save-split-file artifacts/splits/sprint1_split_game_ids.json \
  --use-interaction-terms
```

### 2. Train Odds-Enabled Model (With Opening Odds)

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_sprint1.json \
  --dsn "$DATABASE_URL" \
  --train-season-start-max 2022 \
  --test-season-start 2024 \
  --calib-season-start 2023 \
  --calibration-method platt \
  --iterations 1000 \
  --depth 6 \
  --learning-rate 0.1 \
  --save-split-file artifacts/splits/sprint1_split_game_ids.json \
  --use-interaction-terms
```

**Note**: Both commands use the same `--save-split-file` path to ensure identical splits.

### 3. Evaluate Models (Time-Bucketed Metrics)

```bash
python scripts/model/evaluate_winprob_time_buckets.py \
  --baseline-artifact artifacts/winprob_catboost_baseline_sprint1.json \
  --odds-artifact artifacts/winprob_catboost_odds_sprint1.json \
  --dsn "$DATABASE_URL" \
  --test-season-start 2024 \
  --out-results cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.json
```

---

## Code Changes Summary

### New Files Created
1. `scripts/model/evaluate_winprob_time_buckets.py` - Time-bucketed evaluation script
2. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md`
3. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md`
4. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/phase4-commands.md`
5. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/implementation-summary.md` (this file)
6. `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/sprint-implementation-review.md`

### Files Modified
1. **`scripts/lib/_winprob_lib.py`**:
   - Added `ODDS_FEATURES` constant (line 172)
   - Added `compute_opening_odds_features()` helper function (lines 183-315)
   - Extended `build_design_matrix()` signature with 7 opening odds parameters (lines 318-337)
   - Added opening odds feature logic (lines 413-461)

2. **`scripts/model/train_winprob_catboost.py`**:
   - Updated `_load_training_data()` docstring (lines 91-104)
   - Added `opening_odds` CTE to SQL query (lines 153-162)
   - Added opening odds columns to SELECT (lines 217-221)
   - Added feature engineering using helper (lines 256-280)
   - Added `--disable-opening-odds` flag (line 89)
   - Added `--save-split-file` option (line 90)
   - Added split file persistence (lines 408-425)
   - Added opening odds to `build_matrix_kwargs` (lines 514-529)
   - Added opening odds to `calib_matrix_kwargs` (lines 596-611)
   - Updated `feature_names` to use `ODDS_FEATURES` constant (lines 556-558)

3. **`scripts/model/precompute_model_probabilities.py`**:
   - Added `compute_opening_odds_features` import (line 27)
   - Updated SQL query to include opening odds columns (lines 176-191)
   - Added opening odds to snapshot dict (lines 227-239)
   - Added opening odds feature engineering in `score_snapshot()` (lines 92-168)
   - Added opening odds to `build_design_matrix()` call (lines 130-160)

---

## Testing Checklist

Before running training commands, verify:

- [ ] Database connection works: `psql "$DATABASE_URL" -c "SELECT 1;"`
- [ ] Opening odds data exists: Check `external.sportsbook_odds_snapshots` table
- [ ] Python environment has required packages: `catboost`, `numpy`, `pandas`, `sklearn`, `psycopg`
- [ ] Artifacts directory exists: `mkdir -p artifacts/splits`

---

## Expected Outcomes

### Training
- Baseline model trains successfully without opening odds
- Odds-enabled model trains successfully with opening odds
- Both models use identical train/test/calib splits (verified by split file)
- Feature names include opening odds features (for odds-enabled model)

### Evaluation
- Overall Brier score improvement: 5-10% (target)
- Overall log-loss improvement: 5-10% (target)
- Early-game bucket improvements (2880-2400s, 2400-1800s): 10-15% (target)
- Feature importance shows opening odds in top 50%

---

## Next Steps

1. **Run Training Commands** (see `phase4-commands.md`):
   - Train baseline model
   - Train odds-enabled model
   - Verify split reproducibility

2. **Run Evaluation Command**:
   - Execute time-bucketed evaluation script
   - Review results JSON

3. **Phase 5: Quality Assurance**:
   - Update documentation
   - Run quality gates (linting, tests)
   - Create sprint completion report

---

## Files Reference

- **Commands Guide**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/phase4-commands.md`
- **Parity Report**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md`
- **Odds Format Report**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md`
- **Implementation Review**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/sprint-implementation-review.md`

---

## Frontend Visibility

**Will baseline/odds models or time-bucketed evaluation show up on the comparison pages?**  
**No.** The Model Comparison page reads from `data/models/evaluations/` (exactly 4 hardcoded reports with `eval.overall` / `eval.calibration_bins`). The Grid Search Comparison uses `derived.model_probabilities_v1`, populated by `precompute_model_probabilities.py` from the **existing** 4 model artifacts. The new sprint artifacts and `model-evaluation-results.json` are not wired into either pipeline. See **phase4-commands.md** → "Frontend Visibility" for details and what would need to change.

---

## Summary

**Progress**: ~80% Complete (Phases 1-4 done, Phase 5 pending)

**Ready for Testing**: ✅ Yes - All code is implemented and ready for execution.

**Blockers**: None - User can proceed with training and evaluation commands.
