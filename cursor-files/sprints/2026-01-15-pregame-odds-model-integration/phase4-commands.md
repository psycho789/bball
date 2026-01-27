# Phase 4: Model Training and Evaluation Commands

**Date**: 2026-01-15  
**Sprint**: S1-E4 - Model Evaluation and Comparison

This document provides copy-pastable commands for training baseline and odds-enabled models, and evaluating their performance.

## Prerequisites

1. **Database Connection**: Ensure `DATABASE_URL` is set in your environment
   ```bash
   source .env
   echo $DATABASE_URL  # Verify it's set
   ```

2. **Python Environment**: Ensure you have required packages installed
   ```bash
   # Check if you have a virtual environment
   # If using venv:
   source .venv/bin/activate  # or your venv path
   ```

## Story 4.1: Train Baseline and Odds-Enabled Models

### Step 1: Train Baseline Model (Without Opening Odds)

**Command**:
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

**Expected Output**:
- Model artifact: `artifacts/winprob_catboost_baseline_sprint1.json`
- Model file: `artifacts/winprob_catboost_baseline_sprint1.cbm`
- Split file: `artifacts/splits/sprint1_split_game_ids.json`

**Notes**:
- `--disable-opening-odds` flag ensures baseline model doesn't use opening odds
- `--save-split-file` persists the train/test/calib split for reproducibility
- Training uses seasons 2017-2022, calibration uses 2023, test uses 2024

### Step 2: Train Odds-Enabled Model (With Opening Odds)

**Command**:
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

**Expected Output**:
- Model artifact: `artifacts/winprob_catboost_odds_sprint1.json`
- Model file: `artifacts/winprob_catboost_odds_sprint1.cbm`
- Split file: `artifacts/splits/sprint1_split_game_ids.json` (should match baseline)

**Notes**:
- **No `--disable-opening-odds` flag** - model will use opening odds if available
- Uses same split file as baseline (ensures identical train/test/calib splits)
- Same training parameters as baseline for fair comparison

### Step 3: Verify Split Reproducibility

**Command**:
```bash
# Check that both models used the same split
diff artifacts/splits/sprint1_split_game_ids.json artifacts/splits/sprint1_split_game_ids.json
# Should show no differences (or compare manually)
```

**Manual Verification**:
```bash
# View split file
cat artifacts/splits/sprint1_split_game_ids.json | python -m json.tool
```

**Expected**: Both training runs should produce identical split files (same game_ids in train/test/calib).

## Story 4.2: Evaluate Model Performance with Time-Bucketed Metrics

### Step 1: Run Time-Bucketed Evaluation

**Command**:
```bash
python scripts/model/evaluate_winprob_time_buckets.py \
  --baseline-artifact artifacts/winprob_catboost_baseline_sprint1.json \
  --odds-artifact artifacts/winprob_catboost_odds_sprint1.json \
  --dsn "$DATABASE_URL" \
  --test-season-start 2024 \
  --out-results cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.json
```

**Expected Output**:
- Console output with overall and time-bucketed metrics
- Results file: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.json`

**Output Format**:
```
================================================================================
EVALUATION RESULTS
================================================================================

Overall Metrics:
  Baseline - Brier: 0.XXXXXX, Log-Loss: 0.XXXXXX
  Odds-Enabled - Brier: 0.XXXXXX, Log-Loss: 0.XXXXXX
  Improvement - Brier: +X.XX%, Log-Loss: +X.XX%

Time-Bucketed Metrics:
Bucket          Baseline Brier  Odds Brier      Brier Δ%      Count    
--------------------------------------------------------------------------------
2880-2400       0.XXXXXX        0.XXXXXX        +X.XX%        XXXXX    
2400-1800       0.XXXXXX        0.XXXXXX        +X.XX%        XXXXX    
...
```

### Step 2: Review Results

**Command**:
```bash
# View results JSON
cat cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.json | python -m json.tool
```

**Expected Results**:
- Overall Brier score and log-loss for both models
- Per-bucket metrics (Brier, log-loss, snapshot counts)
- Improvement percentages

## Alternative: Quick Test Run (Smaller Dataset)

If you want to test with a smaller dataset first:

**Baseline (Quick Test)**:
```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_test.json \
  --dsn "$DATABASE_URL" \
  --train-season-start-max 2021 \
  --test-season-start 2022 \
  --calib-season-start 2022 \
  --iterations 100 \
  --disable-opening-odds \
  --save-split-file artifacts/splits/test_split.json \
  --use-interaction-terms
```

**Odds-Enabled (Quick Test)**:
```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_test.json \
  --dsn "$DATABASE_URL" \
  --train-season-start-max 2021 \
  --test-season-start 2022 \
  --calib-season-start 2022 \
  --iterations 100 \
  --save-split-file artifacts/splits/test_split.json \
  --use-interaction-terms
```

**Evaluation (Quick Test)**:
```bash
python scripts/model/evaluate_winprob_time_buckets.py \
  --baseline-artifact artifacts/winprob_catboost_baseline_test.json \
  --odds-artifact artifacts/winprob_catboost_odds_test.json \
  --dsn "$DATABASE_URL" \
  --test-season-start 2022 \
  --out-results cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results-test.json
```

## Troubleshooting

### Issue: "No data loaded from ESPN tables"
**Solution**: Check that `DATABASE_URL` is set and database is accessible:
```bash
source .env
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM espn.probabilities_raw_items LIMIT 1;"
```

### Issue: "Training set has < 1000 rows"
**Solution**: Adjust `--train-season-start-max` to match available data:
```bash
# Check available seasons
psql "$DATABASE_URL" -c "
SELECT DISTINCT CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start
FROM espn.probabilities_raw_items
ORDER BY season_start;
"
```

### Issue: "Test season has 0 rows"
**Solution**: Adjust `--test-season-start` to match available data (see query above).

### Issue: Opening odds not available
**Solution**: This is expected for some games. CatBoost handles NaNs natively. Check coverage:
```bash
psql "$DATABASE_URL" -c "
SELECT 
    COUNT(*) AS total_snapshots,
    COUNT(opening_moneyline_home) AS with_opening_odds,
    ROUND(100.0 * COUNT(opening_moneyline_home) / COUNT(*), 2) AS pct_coverage
FROM derived.snapshot_features_v1
WHERE CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) = 2024;
"
```

## Expected Training Times

- **Baseline Model**: ~10-30 minutes (depending on dataset size and iterations)
- **Odds-Enabled Model**: ~10-30 minutes (similar, opening odds add minimal overhead)
- **Evaluation**: ~1-5 minutes (depends on test set size)

## Success Criteria

**From Sprint Plan**:
- ✅ Models train successfully with opening odds (100% success rate)
- ✅ Feature importance shows opening odds in top 50%
- ✅ Time-bucketed evaluation shows improvement in early-game buckets
- ✅ Brier score improvement: 5-10% globally, 10-15% in early-game buckets
- ✅ Log-loss improvement: 5-10% globally, 10-15% in early-game buckets

**Verification**:
- Check evaluation results JSON for improvement percentages
- Review time-bucketed metrics (especially 2880-2400s and 2400-1800s buckets)
- Compare feature importance from CatBoost training logs

---

**Next Steps After Evaluation**:
1. Review results and document findings
2. Proceed to Phase 5: Quality Assurance
3. Create sprint completion report

---

## Frontend Visibility: Will This Data Show Up on Comparison Pages?

**Short answer: No.** The new baseline/odds-enabled models and time-bucketed evaluation results will **not** appear on the frontend comparison pages as currently implemented.

### Model Comparison Page (`/stats` → Model Comparison)

- **Data source**: `GET /api/stats/model-comparison` reads from `data/models/evaluations/`.
- **Expected format**: Exactly **4** evaluation reports with hardcoded filenames:
  - `winprob_eval_logreg_platt_2017-2023_calib_2023_on_2024.json`
  - `winprob_eval_logreg_isotonic_2017-2023_calib_2023_on_2024.json`
  - `winprob_eval_catboost_platt_2017-2023_calib_2023_on_2024.json`
  - `winprob_eval_catboost_isotonic_2017-2023_calib_2023_on_2024.json`
- **Expected structure**: Each report has `eval.overall` (logloss, brier, ece_binned, roc_auc, n) and `eval.calibration_bins`.
- **Sprint output**: `evaluate_winprob_time_buckets.py` writes to `cursor-files/.../model-evaluation-results.json` with a **different** structure (baseline vs odds, time-bucketed metrics). It does **not** produce the 4-model, calibration-style reports the API expects.

### Grid Search Comparison Page

- **Data source**: `GET /api/grid-search/comparison` uses output from `scripts/trade/compare_grid_search_models.py`.
- **Models used**: ESPN + the **existing** 4 ML models (LogReg/CatBoost × Platt/Isotonic), whose probabilities come from `derived.model_probabilities_v1`.
- **Precompute**: `precompute_model_probabilities.py` populates `model_probabilities_v1` using the **fixed** artifacts under `data/models/` (e.g. `winprob_catboost_platt_2017-2023.json`). The new baseline/odds artifacts (`artifacts/winprob_catboost_*_sprint1.json`) are **not** used.

### What Would Need to Change for Frontend Visibility?

1. **Model Comparison page**
   - Either: Run `evaluate_winprob_model` (or equivalent) for baseline + odds models and write reports in the **same** format as the existing 4 (with `eval.overall`, `eval.calibration_bins`), then extend the API to:
     - Load additional report files (e.g. baseline, odds-enabled), **or**
     - Replace/add a 2×2 “baseline vs odds” view that consumes the time-bucketed results.
   - Update `load_evaluation_reports` / `get_model_label` / `get_model_color` to support the new models and, if needed, the new report shape.

2. **Grid Search Comparison**
   - Add baseline and odds-enabled models to the grid search pipeline:
     - Include their artifacts in `precompute_model_probabilities.py` (or a variant) and store their probabilities (e.g. new columns or a new table).
     - Update `compare_grid_search_models.py` and the grid search API to include these models in the comparison.
   - Run grid search for the new models so comparison data exists.

Until those changes are made, baseline/odds models and time-bucketed evaluation remain **offline** (scripts + JSON results only), not reflected on the Model Comparison or Grid Search Comparison frontend.
