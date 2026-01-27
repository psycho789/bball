# Frontend & Grid Search Integration Plan

**Date**: 2026-01-15  
**Purpose**: Get new baseline and odds-enabled models into grid searches and visible on frontend comparison pages

## Current Situation

### ✅ What We Have
1. **New Models Trained**:
   - `artifacts/winprob_catboost_baseline_sprint1.json` (13 features, no opening odds)
   - `artifacts/winprob_catboost_odds_sprint1.json` (20 features, with opening odds)
   - Both models trained and ready to use

2. **Pre-computation Script Updated**: 
   - `precompute_model_probabilities.py` can handle opening odds
   - But it's hardcoded to use the 4 existing models

3. **Grid Search System**:
   - Uses hardcoded model map: `logreg_platt`, `logreg_isotonic`, `catboost_platt`, `catboost_isotonic`
   - Can use precomputed probabilities from `derived.model_probabilities_v1` OR load model artifacts directly

### ❌ What's Missing
1. **Grid Search**: New models not in grid search system
2. **Pre-computation**: New models not precomputed in `model_probabilities_v1`
3. **Frontend**: New models not visible on comparison pages

---

## Integration Options

### Option A: Add New Models to Grid Search System (Recommended)

**Approach**: Extend grid search to support new models by:
1. Adding new model names to `load_model_artifact()` function
2. Running grid searches with new models
3. Running comparison script to generate frontend data

**Pros**:
- Quick to implement (just update model map)
- Can run grid searches immediately
- Frontend will automatically show results

**Cons**:
- Need to run grid searches (takes time)
- Need to update comparison script if it filters models

**Steps**:
1. Update `scripts/trade/grid_search_hyperparameters.py`:
   - Add `catboost_baseline_sprint1` and `catboost_odds_sprint1` to model map
   - Point to `artifacts/winprob_catboost_baseline_sprint1.json` and `artifacts/winprob_catboost_odds_sprint1.json`

2. Run grid searches:
   ```bash
   # Baseline model
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2024 \
     --model-name catboost_baseline_sprint1 \
     --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
     --exit-min 0.05 --exit-max 0.50 --exit-step 0.05
   
   # Odds-enabled model
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2024 \
     --model-name catboost_odds_sprint1 \
     --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
     --exit-min 0.05 --exit-max 0.50 --exit-step 0.05
   ```

3. Run comparison script:
   ```bash
   python scripts/trade/compare_grid_search_models.py
   ```

4. Frontend will automatically show results (reads from `data/grid_search/`)

---

### Option B: Pre-compute Probabilities for New Models

**Approach**: Update `precompute_model_probabilities.py` to include new models, then grid search uses precomputed probabilities

**Pros**:
- Faster grid searches (uses precomputed probabilities)
- Consistent with existing approach

**Cons**:
- Need to modify precompute script
- Need to run precompute for new models
- Still need to run grid searches

**Steps**:
1. Update `scripts/model/precompute_model_probabilities.py`:
   - Add new models to `load_all_models()` function
   - Add new probability columns to `derived.model_probabilities_v1` table

2. Run pre-computation:
   ```bash
   python scripts/model/precompute_model_probabilities.py --dsn "$DATABASE_URL"
   ```

3. Grid searches will automatically use precomputed probabilities (if available)

---

## Recommended Approach: Option A (Simpler)

**Why**: 
- Minimal code changes (just update model map)
- No database schema changes needed
- Can run immediately

**Implementation**:

### Step 1: Update Grid Search Model Map

**File**: `scripts/trade/grid_search_hyperparameters.py`

**Change** (around line 148):
```python
model_file_map = {
    "logreg_platt": "data/models/winprob_logreg_platt_2017-2023.json",
    "logreg_isotonic": "data/models/winprob_logreg_isotonic_2017-2023.json",
    "catboost_platt": "data/models/winprob_catboost_platt_2017-2023.json",
    "catboost_isotonic": "data/models/winprob_catboost_isotonic_2017-2023.json",
    # NEW: Sprint 1 models
    "catboost_baseline_sprint1": "artifacts/winprob_catboost_baseline_sprint1.json",
    "catboost_odds_sprint1": "artifacts/winprob_catboost_odds_sprint1.json",
}
```

### Step 2: Run Grid Searches

**Commands**:
```bash
# Baseline model grid search
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024 \
  --model-name catboost_baseline_sprint1 \
  --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
  --exit-min 0.05 --exit-max 0.50 --exit-step 0.05 \
  --workers 4 \
  --output-dir data/grid_search/catboost_baseline_sprint1_2024

# Odds-enabled model grid search
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024 \
  --model-name catboost_odds_sprint1 \
  --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
  --exit-min 0.05 --exit-max 0.50 --exit-step 0.05 \
  --workers 4 \
  --output-dir data/grid_search/catboost_odds_sprint1_2024
```

**Note**: Grid searches can take 30-60 minutes depending on number of games and parameter combinations.

### Step 3: Run Comparison Script

**Command**:
```bash
python scripts/trade/compare_grid_search_models.py
```

**Output**: Creates comparison JSON that frontend reads from `data/grid_search/`

### Step 4: View on Frontend

**URL**: Navigate to Grid Search Comparison page in webapp

**What You'll See**:
- ESPN (baseline)
- 4 existing ML models (logreg/catboost × platt/isotonic)
- **NEW**: `catboost_baseline_sprint1` and `catboost_odds_sprint1` models
- Comparison table showing profit, win rate, trades, etc.

---

## Model Comparison Page (Separate Issue)

**Current State**: Model Comparison page reads from `data/models/evaluations/` with hardcoded 4 files

**To Add New Models**:
1. Run evaluation script for new models (create evaluation reports in same format)
2. Update `webapp/api/endpoints/model_comparison.py` to load additional reports
3. Update frontend to display additional models

**This is a separate task** - grid search comparison is easier and more immediately useful.

---

## Quick Start Commands

**1. Update grid search model map** (one-time code change)

**2. Run grid searches** (30-60 min each):
```bash
# Baseline
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024 --model-name catboost_baseline_sprint1 \
  --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
  --exit-min 0.05 --exit-max 0.50 --exit-step 0.05

# Odds-enabled
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024 --model-name catboost_odds_sprint1 \
  --entry-min 0.05 --entry-max 0.50 --entry-step 0.05 \
  --exit-min 0.05 --exit-max 0.50 --exit-step 0.05
```

**3. Run comparison** (1-2 min):
```bash
python scripts/trade/compare_grid_search_models.py
```

**4. View on frontend**: Navigate to Grid Search Comparison page

---

## Summary

**To see new models on frontend**:
1. ✅ Update grid search model map (5 min)
2. ⏳ Run grid searches for new models (1-2 hours)
3. ✅ Run comparison script (2 min)
4. ✅ View on frontend (automatic)

**Total time**: ~2 hours (mostly waiting for grid searches to complete)

**Result**: New models will appear in Grid Search Comparison page alongside existing models, showing profit, win rate, and other metrics.
