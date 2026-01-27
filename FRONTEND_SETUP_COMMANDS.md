# Frontend Setup Commands - Pre-Game Odds Models

**Date**: 2026-01-21  
**Purpose**: Complete command list to get new baseline/odds-enabled models visible on frontend

## Prerequisites

```bash
# 1. Set up environment
source .env
echo $DATABASE_URL  # Verify it's set

# 2. Activate virtual environment (if using one)
source .venv/bin/activate  # or your venv path
```

## Step 1: Train Models

### Train Baseline Model (Without Opening Odds)

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
- `artifacts/winprob_catboost_baseline_sprint1.json`
- `artifacts/winprob_catboost_baseline_sprint1.cbm`
- `artifacts/splits/sprint1_split_game_ids.json`

### Train Odds-Enabled Model (With Opening Odds)

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
- `artifacts/winprob_catboost_odds_sprint1.json`
- `artifacts/winprob_catboost_odds_sprint1.cbm`

## Step 2: Pre-Compute Model Probabilities

**Note**: This populates `derived.model_probabilities_v1` so grid searches can use the models.

```bash
python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"
```

**What this does**: 
- Pre-computes probabilities for all 4 existing models (logreg_platt, logreg_isotonic, catboost_platt, catboost_isotonic)
- Processes **all snapshots** from `derived.snapshot_features_v1` (not filtered by season)
- Stores results in `derived.model_probabilities_v1`

**Note**: The new models (`catboost_baseline_sprint1`, `catboost_odds_sprint1`) are **NOT** included in this script. They will use on-the-fly prediction during grid search (which triggers the CatBoost loading performance issue).

## Step 3: Run Grid Searches

### Grid Search for Baseline Model

```bash
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024-25 \
  --model-name catboost_baseline_sprint1
```

**Expected Output**:
- Results in `data/grid_search/{cache_key}/`
- Includes `final_selection.json` and `grid_results_*.json`

### SQL Queries Executed by Grid Search

The grid search script runs the following SQL queries:

**1. Get Game IDs** (runs once at start):
```sql
WITH kalshi_games AS MATERIALIZED (
    SELECT DISTINCT km.espn_event_id
    FROM kalshi.markets km
    WHERE km.espn_event_id IS NOT NULL
)
SELECT DISTINCT p.game_id
FROM espn.probabilities_raw_items p
JOIN kalshi_games kg ON kg.espn_event_id = p.game_id
WHERE p.season_label = '2024-25'
GROUP BY p.game_id
HAVING COUNT(*) > 100
ORDER BY p.game_id
```

**2. Get Game Info** (runs once per game):
```sql
SELECT 
    sg.event_date as game_start,
    sg.home_score as final_home_score,
    sg.away_score as final_away_score
FROM espn.scoreboard_games sg
WHERE sg.event_id = %s
LIMIT 1
```

**3. Get Game Duration** (runs once per game, if game info found):
```sql
SELECT 
    EXTRACT(EPOCH FROM (MAX(snapshot_ts) - MIN(snapshot_ts)))::INTEGER as duration_seconds
FROM derived.snapshot_features_v1
WHERE game_id = %s
```

**4. Get Snapshot Data** (runs once per game, per parameter combination):
```sql
-- If using pre-computed model probabilities:
SELECT 
    sf.snapshot_ts,
    sf.espn_home_prob,
    sf.kalshi_home_mid_price,
    sf.kalshi_home_bid,
    sf.kalshi_home_ask,
    sf.kalshi_away_mid_price,
    sf.kalshi_away_bid,
    sf.kalshi_away_ask,
    sf.time_remaining,
    mp.catboost_baseline_sprint1_prob  -- or other model column
FROM derived.snapshot_features_v1 sf
LEFT JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
WHERE sf.game_id = %s
ORDER BY sf.sequence_number, sf.snapshot_ts

-- If NOT using pre-computed probabilities (ESPN only):
SELECT 
    sf.snapshot_ts,
    sf.espn_home_prob,
    sf.kalshi_home_mid_price,
    sf.kalshi_home_bid,
    sf.kalshi_home_ask,
    sf.kalshi_away_mid_price,
    sf.kalshi_away_bid,
    sf.kalshi_away_ask,
    sf.time_remaining
FROM derived.snapshot_features_v1 sf
WHERE sf.game_id = %s
ORDER BY sf.sequence_number, sf.snapshot_ts
```

**Query Frequency**:
- Query #1: **1 time** (at start)
- Query #2: **N times** (once per game, where N = number of games in season)
- Query #3: **N times** (once per game)
- Query #4: **N × M times** (once per game × once per parameter combination)
  - Example: 84 games × 209 combinations = **17,556 queries** for a full grid search

**Performance Note**: The script uses connection pooling and parallel workers, so queries are executed concurrently. The canonical dataset (`derived.snapshot_features_v1`) is a materialized view, so it's pre-computed and fast to query.

### Grid Search for Odds-Enabled Model

```bash
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024-25 \
  --model-name catboost_odds_sprint1
```

**Expected Output**:
- Results in `data/grid_search/{cache_key}/`
- Includes `final_selection.json` and `grid_results_*.json`

## Step 4: Generate Comparison Data

This aggregates all grid search results into a single comparison file that the frontend reads:

```bash
python scripts/trade/compare_grid_search_models.py
```

**Expected Output**:
- `data/grid_search/model_comparison.json`
- Console output with comparison table

**What this does**: 
- Scans `data/grid_search/` for all model results
- Aggregates metrics (profit, trades, win rate, etc.)
- Exports to JSON that the frontend API reads

## Step 5: Verify Frontend Can See Results

The frontend Grid Search Comparison page (`/grid-search/comparison`) reads from:
- **API Endpoint**: `GET /api/grid-search/comparison`
- **Data Source**: `data/grid_search/model_comparison.json`

**Verify the file exists**:
```bash
ls -lh data/grid_search/model_comparison.json
cat data/grid_search/model_comparison.json | python -m json.tool | head -50
```

You should see entries for:
- `ESPN (default)`
- `logreg_platt`
- `logreg_isotonic`
- `catboost_platt`
- `catboost_isotonic`
- **NEW**: `catboost_baseline_sprint1`
- **NEW**: `catboost_odds_sprint1`

## Complete Command Sequence (Copy-Paste)

```bash
# Setup
source .env
source .venv/bin/activate  # if using venv

# Step 1: Train models
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

# Step 2: Pre-compute probabilities (for existing 4 models only)
python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

# Step 3: Run grid searches
python scripts/trade/grid_search_hyperparameters.py \
  --season 2024-25 \
  --model-name catboost_baseline_sprint1

python scripts/trade/grid_search_hyperparameters.py \
  --season 2024-25 \
  --model-name catboost_odds_sprint1

# Step 4: Generate comparison
python scripts/trade/compare_grid_search_models.py

# Step 5: Verify
ls -lh data/grid_search/model_comparison.json
```

## Expected Timeline

- **Model Training**: ~20-60 minutes total (10-30 min per model)
- **Pre-compute**: ~5-15 minutes
- **Grid Searches**: ~30-60 minutes each (depends on dataset size)
- **Comparison**: ~1 minute
- **Total**: ~2-3 hours

## Troubleshooting

### Issue: "No game IDs found" in grid search
**Solution**: Use correct season format (`2024-25`, not `2024`)

### Issue: Models not showing in comparison
**Solution**: 
1. Check that grid search completed successfully
2. Verify `data/grid_search/model_comparison.json` includes the new models
3. Restart frontend server if needed

### Issue: "Model artifact not found"
**Solution**: Verify model files exist:
```bash
ls -lh artifacts/winprob_catboost_*_sprint1.*
```

## What Shows Up on Frontend?

**Grid Search Comparison Page** (`/grid-search/comparison`):
- Shows all models with their grid search results
- Includes profit, trades, win rate, optimal thresholds
- **New models will appear here automatically** after running `compare_grid_search_models.py`

**Model Comparison Page** (`/stats` → Model Comparison):
- This page shows evaluation metrics (Brier, log-loss, calibration)
- **New models will NOT appear here** unless you also run evaluation scripts
- This is separate from grid search results
