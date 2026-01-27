# Model Comparison and Grid Search Explained

**Date**: 2026-01-22  
**Audience**: Technical but non-data-scientist  
**Purpose**: Explain model differences, training process, and grid search methodology

## Overview

This document explains:
1. The models in the system and their differences
2. How models are trained
3. What CatBoost and calibration methods are
4. How grid searches work and why results differ

## Models Overview

### Model Types

**Logistic Regression Models:**
- `logreg_platt` - Logistic Regression with Platt calibration
- `logreg_isotonic` - Logistic Regression with Isotonic calibration

**CatBoost Models (with interaction terms):**
- `catboost_platt` - CatBoost with Platt calibration
- `catboost_isotonic` - CatBoost with Isotonic calibration
- `catboost_baseline_platt` - CatBoost with Platt calibration (no opening odds)
- `catboost_baseline_isotonic` - CatBoost with Isotonic calibration (no opening odds)
- `catboost_odds_platt` - CatBoost with Platt calibration (with opening odds)
- `catboost_odds_isotonic` - CatBoost with Isotonic calibration (with opening odds)

**CatBoost Models (without interaction terms):**
- `catboost_baseline_no_interaction_platt` - CatBoost with Platt calibration (no opening odds, no interactions)
- `catboost_baseline_no_interaction_isotonic` - CatBoost with Isotonic calibration (no opening odds, no interactions)
- `catboost_odds_no_interaction_platt` - CatBoost with Platt calibration (with opening odds, no interactions)
- `catboost_odds_no_interaction_isotonic` - CatBoost with Isotonic calibration (with opening odds, no interactions)

### Key Differences

| Model | Algorithm | Calibration | Features | Opening Odds | Interaction Terms | Training Seasons |
|-------|-----------|-------------|----------|--------------|------------------|-------------------|
| `logreg_platt` | Logistic Regression | Platt | 13 | No | Yes | 2017-2023 |
| `logreg_isotonic` | Logistic Regression | Isotonic | 13 | No | Yes | 2017-2023 |
| `catboost_platt` | CatBoost | Platt | 13 | No | Yes | 2017-2023 |
| `catboost_isotonic` | CatBoost | Isotonic | 13 | No | Yes | 2017-2023 |
| `catboost_baseline_platt` | CatBoost | Platt | 13 | No | Yes | 2017-2023 |
| `catboost_baseline_isotonic` | CatBoost | Isotonic | 13 | No | Yes | 2017-2023 |
| `catboost_odds_platt` | CatBoost | Platt | 17 | Yes | Yes | 2017-2023 |
| `catboost_odds_isotonic` | CatBoost | Isotonic | 17 | Yes | Yes | 2017-2023 |
| `catboost_baseline_no_interaction_platt` | CatBoost | Platt | 5 | No | No | 2017-2023 |
| `catboost_baseline_no_interaction_isotonic` | CatBoost | Isotonic | 5 | No | No | 2017-2023 |
| `catboost_odds_no_interaction_platt` | CatBoost | Platt | 9 | Yes | No | 2017-2023 |
| `catboost_odds_no_interaction_isotonic` | CatBoost | Isotonic | 9 | Yes | No | 2017-2023 |

## Features Used by Models

### Base Features (All Models - 5 features)

1. **`point_differential_scaled`** - Normalized point difference (home score - away score)
2. **`time_remaining_regulation_scaled`** - Normalized time remaining in regulation (seconds)
3. **`possession_home`** - Binary flag (1 if home team has possession, 0 otherwise)
4. **`possession_away`** - Binary flag (1 if away team has possession, 0 otherwise)
5. **`possession_unknown`** - Binary flag (1 if possession unknown, 0 otherwise)

### Interaction Features (All Models - 8 features)

These capture relationships between base features:

1. **`score_diff_div_sqrt_time_remaining_scaled`** - Point differential divided by square root of time remaining (captures game urgency)
2. **`espn_home_prob_scaled`** - ESPN's win probability (normalized)
3. **`espn_home_prob_lag_1_scaled`** - Previous snapshot's ESPN probability (momentum)
4. **`espn_home_prob_delta_1_scaled`** - Change in ESPN probability from previous snapshot
5. **`period_1`** - Binary flag for Q1 (first 12 minutes)
6. **`period_2`** - Binary flag for Q2 (minutes 12-24)
7. **`period_3`** - Binary flag for Q3 (minutes 24-36)
8. **`period_4`** - Binary flag for Q4 (final 12 minutes)

### Opening Odds Features (Only odds-enabled models - 4 features)

1. **`opening_overround`** - Sportsbook's overround/vig amount (may be NaN)
2. **`has_opening_moneyline`** - Binary flag (1 if valid moneyline odds, 0 otherwise)
3. **`has_opening_spread`** - Binary flag (1 if spread present, 0 otherwise)
4. **`has_opening_total`** - Binary flag (1 if total present, 0 otherwise)

**Note**: `opening_prob_home_fair` is used as CatBoost baseline (not a feature). `opening_spread` and `opening_total` were removed as redundant features.

**Total Features:**
- Models without opening odds, with interactions: 5 base + 8 interaction = **13 features**
- Models with opening odds, with interactions: 5 base + 8 interaction + 4 opening odds = **17 features**
- Models without opening odds, without interactions: **5 features** (base only)
- Models with opening odds, without interactions: 5 base + 4 opening odds = **9 features**

## What is CatBoost?

**CatBoost** (Categorical Boosting) is a gradient boosting machine learning algorithm.

### How It Works

1. **Gradient Boosting**: Builds an ensemble of decision trees sequentially, where each tree corrects errors from previous trees
2. **Automatic Feature Interactions**: Discovers relationships between features without explicit engineering
3. **Handles Missing Values**: Can work with NaN values natively (unlike logistic regression)
4. **Categorical Features**: Optimized for handling categorical data (like `possession`)

### CatBoost vs Logistic Regression

| Aspect | Logistic Regression | CatBoost |
|--------|---------------------|----------|
| **Complexity** | Linear model | Non-linear (tree-based) |
| **Feature Interactions** | Must be explicitly engineered | Automatically discovers |
| **Missing Values** | Must be handled (filled/imputed) | Handles natively |
| **Interpretability** | High (coefficients show feature importance) | Lower (black box) |
| **Training Speed** | Fast | Slower (but still reasonable) |
| **Overfitting Risk** | Lower (with regularization) | Higher (requires careful tuning) |

### Why Use CatBoost?

- **Better Performance**: Can capture non-linear relationships and complex interactions
- **Less Feature Engineering**: Automatically finds feature interactions
- **Handles Missing Data**: Opening odds features often have NaNs (missing for some games)

## What is Calibration?

**Calibration** adjusts raw model probabilities to match observed outcomes.

### The Problem

Models often output probabilities that don't match reality:
- Model says "70% chance home wins" but home actually wins 60% of the time
- This is called **miscalibration**

### Calibration Methods

#### Platt Calibration

**What it does**: Applies a sigmoid transformation to raw probabilities

**Formula**: `P_calibrated = 1 / (1 + exp(-(alpha + beta * logit(P_raw))))`

**Parameters**:
- `alpha` - Intercept term (shifts probabilities)
- `beta` - Slope term (stretches/compresses probabilities)

**Characteristics**:
- Simple, fast
- Assumes probabilities are already well-ordered (monotonic)
- Works well when model is already somewhat calibrated

#### Isotonic Calibration

**What it does**: Fits a piecewise constant, monotonically increasing function

**Characteristics**:
- More flexible than Platt (can handle non-sigmoid shapes)
- Non-parametric (doesn't assume a specific curve shape)
- Can overfit with small calibration sets
- Better for severely miscalibrated models

### Why Both Methods Exist

Different models may need different calibration:
- **Platt**: Good default, works for most cases
- **Isotonic**: Better for models with severe miscalibration

Both methods use a **calibration set** (separate from training) to learn the adjustment.

## How Models Are Trained

### Training Process

1. **Data Split** (by season, game-level to prevent leakage):
   - **Train**: `season_start <= 2022` (2017-2022 seasons)
   - **Calibration**: `season_start == 2023` (2023-24 season)
   - **Test**: `season_start == 2024` (2024-25 season) - held out, not used in training

2. **Feature Engineering**:
   - Load raw data from ESPN tables
   - Calculate interaction terms (if enabled)
   - For odds-enabled models: Join opening odds and engineer features

3. **Model Training**:
   - **Logistic Regression**: Fits coefficients using IRLS (Iteratively Reweighted Least Squares)
   - **CatBoost**: Trains gradient boosting trees

4. **Calibration**:
   - Get raw probabilities on calibration set
   - Fit Platt or Isotonic calibrator
   - Store calibration parameters in artifact

5. **Save Artifact**:
   - Model weights/parameters
   - Feature names and preprocessing parameters
   - Calibration parameters
   - Metadata (training seasons, timestamps, etc.)

### Training Performance Options

The training script supports several performance optimizations:

| Option | Description | Savings |
|--------|-------------|---------|
| `--cache-parquet PATH` | Cache training data as Parquet file | ~60s on subsequent runs |
| `--work-mem SIZE` | PostgreSQL work_mem setting (default: 4GB) | Avoids disk spills |

**Parquet Caching**: First run queries the database and saves to Parquet. Subsequent runs load from cache:
```bash
# First run (queries DB, saves cache): ~70s
python scripts/model/train_winprob_catboost.py \
  --cache-parquet data/training_cache.parquet \
  ...

# Second run (loads from cache): ~3s
python scripts/model/train_winprob_catboost.py \
  --cache-parquet data/training_cache.parquet \
  ...
```

**Note**: Different feature configurations (baseline vs odds, with/without interactions) require separate cache files since they query different columns.

### Training Data Sources

**All Models**:
- Load from `espn.probabilities_raw_items` and `espn.prob_event_state` tables
- Historical data back to 2017-18 season

**Sprint Models (Opening Odds)**:
- Also join `external.sportsbook_odds_snapshots` table
- Filter for `is_opening_line = TRUE`
- Only games with opening odds get these features (others have NaNs)

## Grid Search Explained

### What is Grid Search?

**Grid search** systematically tests different parameter combinations to find optimal values.

### What Parameters Are Searched?

**Entry Threshold** (`entry_threshold`):
- Range: 0.02 to 0.20 (default)
- Step: 0.01
- Meaning: Minimum divergence between ESPN probability and Kalshi price to enter a trade
- Example: `entry_threshold = 0.15` means enter when ESPN prob is 15 cents different from Kalshi price

**Exit Threshold** (`exit_threshold`):
- Range: 0.00 to 0.05 (default)
- Step: 0.005
- Meaning: Maximum divergence to exit a trade (take profit/cut loss)
- Example: `exit_threshold = 0.01` means exit when divergence drops to 1 cent

**Constraint**: `exit_threshold < entry_threshold` (must exit at smaller divergence than entry)

### Grid Search Process

1. **Generate Combinations**:
   - Creates all valid (entry, exit) pairs
   - Example: (0.02, 0.00), (0.02, 0.005), (0.03, 0.00), ... (0.20, 0.045)
   - Typical grid: ~200-300 combinations

2. **Split Games** (deterministic, by random seed):
   - **Train**: 70% of games (used to find best parameters)
   - **Validation**: 15% of games (used to select final parameters)
   - **Test**: 15% of games (final evaluation, not used in selection)

3. **For Each Combination**:
   - Run trading simulation on all games in each split
   - Calculate metrics: profit, trades, win rate, profit factor, etc.
   - Store results

4. **Select Best Parameters**:
   - Find top N combinations by profit on **train** set
   - Among those, pick the one with best profit on **validation** set
   - Evaluate final choice on **test** set (reported metrics)

### What Data Does Grid Search Use?

**Input**: Game IDs from specified season (e.g., "2025-26")

**For Each Game**:
1. Load aligned data from `derived.snapshot_features_v1` (canonical dataset)
2. Get model probabilities (either from precomputed table or on-the-fly prediction)
3. Get Kalshi market prices (bid/ask)
4. Calculate divergence: `|model_prob - kalshi_price|`
5. Execute trading strategy:
   - **Enter**: When divergence > `entry_threshold`
   - **Exit**: When divergence < `exit_threshold`
6. Calculate P&L for each trade

**Model Probabilities**:
- **First**: Check for precomputed probabilities in `derived.model_probabilities_v1` (fast, requires running `precompute_model_probabilities.py` first)
- **Fallback**: Load model artifact and predict on-the-fly (slower, used if precomputed values are missing)

**Performance Note**: Grid search is much faster when precomputed probabilities are available. Always run `precompute_model_probabilities.py` BEFORE grid search.

### Why Grid Search Results Differ

#### 1. Model Differences

**Different Algorithms**:
- Logistic Regression: Linear, interpretable, faster
- CatBoost: Non-linear, can capture complex patterns, slower

**Different Features**:
- Most models: 13 features (with interactions)
- Odds-enabled models: 17 features (with interactions + opening odds)
- No-interaction models: 5 features (base only) or 9 features (base + opening odds)
- More features can help or hurt (depends on signal vs noise)

**Different Calibration**:
- Platt vs Isotonic can affect probability distributions
- Better calibration = better trading decisions

#### 2. Data Volume Differences

**Season Used**:
- **2025-26**: 505 games total, 353 train games → More stable results
- **2024-25**: 84 games total, 58 train games → Less stable, higher variance

**Impact**: More games = more trades = more reliable profit estimates

#### 3. Grid Search Parameters

**Same for All Models**:
- Entry range: 0.02-0.20, step 0.01
- Exit range: 0.00-0.05, step 0.005
- Same train/valid/test split ratios
- Same random seed (42) for reproducibility

**Different Optimal Thresholds**:
- Each model may find different optimal (entry, exit) pairs
- Example: `catboost_platt` might prefer (0.15, 0.01) while `logreg_platt` prefers (0.19, 0.015)

#### 4. Trading Strategy Execution

**Entry Logic**:
- Enter when `|model_prob - kalshi_price| > entry_threshold`
- Different models produce different probabilities → different entry points

**Exit Logic**:
- Exit when `|model_prob - kalshi_price| < exit_threshold`
- Model accuracy affects how quickly divergence converges

**Profit Calculation**:
- Gross profit: Difference between entry and exit prices
- Net profit: Gross profit - trading fees ($0.92 per trade)
- Models with more accurate probabilities → better entry/exit timing → higher profits

### Example: Why Results Differ

**Scenario**: ESPN says 60% home win, Kalshi price is 55 cents

**Model A** (accurate): Predicts 60% → Divergence = 5 cents → No trade (below 0.15 threshold)

**Model B** (less accurate): Predicts 65% → Divergence = 10 cents → Enters trade → May lose if model is wrong

**Model C** (with opening odds): Uses pre-game odds to adjust → Predicts 58% → Divergence = 3 cents → No trade (avoids bad trade)

## Model Performance Comparison

### Current Results (2025-26 Season)

| Model | Test Profit | Trades | Win Rate | Entry | Exit |
|-------|-------------|--------|----------|-------|------|
| ESPN (default) | $1,942.84 | 332 | 72.9% | 0.19 | 0.015 |
| catboost_platt | $1,899.70 | 367 | 66.8% | 0.15 | 0.01 |
| catboost_isotonic | $1,826.54 | 321 | 71.0% | 0.19 | 0.015 |
| catboost_baseline_platt | $1,787.42 | 350 | 63.1% | 0.15 | 0.01 |
| catboost_baseline_isotonic | TBD | TBD | TBD | TBD | TBD |
| catboost_odds_platt | $1,439.01 | 316 | 66.8% | 0.18 | 0.02 |
| catboost_odds_isotonic | TBD | TBD | TBD | TBD | TBD |
| logreg_platt | $1,411.99 | 327 | 65.4% | 0.19 | 0.015 |
| logreg_isotonic | $1,220.86 | 331 | 63.4% | 0.19 | 0.015 |

### Why ESPN (Default) Performs Best

**ESPN (default)** uses ESPN's own win probability directly (no ML model).

**Advantages**:
- No model error (uses source data directly)
- No calibration needed (already calibrated by ESPN)
- No feature engineering overhead

**Why ML Models Exist**:
- ESPN probabilities may not be optimal for trading
- ML models can learn patterns ESPN doesn't capture
- Opening odds can provide additional signal

### Why Opening Odds Models May Underperform

**Odds-enabled models** may have lower profit despite more features.

**Possible Reasons**:
1. **Overfitting**: More features (20 vs 13) may cause overfitting to training data
2. **Missing Data**: Opening odds only available for ~60% of games → Many NaNs
3. **Signal Quality**: Opening odds may not add predictive value beyond in-game features
4. **Threshold Selection**: Grid search may have found suboptimal thresholds

**Note**: This doesn't mean opening odds are useless - they may help in specific game phases or situations not captured by aggregate metrics.

## Grid Search Selection Process

### How Best Parameters Are Chosen

1. **Train Set**: Test all combinations, rank by profit
2. **Top N Selection**: Take top 10 combinations from train set
3. **Validation Set**: Among top 10, pick the one with best validation profit
4. **Test Set**: Evaluate final choice (reported in comparison table)

**Why This Process?**
- **Train**: Finds promising parameter ranges
- **Validation**: Prevents overfitting to train set
- **Test**: Final unbiased evaluation (not used in selection)

### Why Optimal Thresholds Differ

**Different Models → Different Probabilities → Different Optimal Thresholds**

**Example**:
- `catboost_platt`: More confident predictions → Lower entry threshold (0.15) works better
- `logreg_platt`: Less confident predictions → Higher entry threshold (0.19) needed to filter noise

**Entry Threshold Interpretation**:
- **Lower (0.15)**: More trades, requires model to be more accurate
- **Higher (0.19)**: Fewer trades, more conservative, less dependent on model accuracy

**Exit Threshold Interpretation**:
- **Lower (0.01)**: Exit quickly, lock in small profits
- **Higher (0.02)**: Hold longer, aim for larger profits (but risk reversals)

## Why Models with Same Algorithm Differ

Models using the same algorithm (e.g., CatBoost with Platt calibration) can produce different results due to:

### Training Data Split

**Older models** (e.g., `catboost_platt`):
- **Train**: Seasons 2017-2023 (`train_season_start_max: 2023`)
- **Calibration**: Season 2023
- **Test**: Season 2024

**Newer models** (e.g., `catboost_baseline_platt`):
- **Train**: Seasons 2017-2023 (`train_season_start_max: 2023`)
- **Calibration**: Season 2023
- **Test**: Season 2024

### Impact of Different Features

1. **Feature Set**: Models with different features (e.g., with/without opening odds, with/without interactions) learn different patterns
2. **Preprocessing**: Normalization parameters are computed from the training set, so they differ based on feature availability
3. **Model Weights**: CatBoost learns different tree structures and weights based on available features

### Why This Matters

Even with the same algorithm and calibration method, **the feature set and training data determine what the model learns**. Different features:
- Expose the model to different information
- Change the feature distributions (normalization parameters)
- Result in different learned patterns (tree structures)

**Note**: All models use the same CatBoost hyperparameters (iterations=1000, depth=6, learning_rate=0.1), so differences come from features and data splits.

## Summary

### Model Differences

1. **Algorithm**: Logistic Regression (linear) vs CatBoost (non-linear)
2. **Calibration**: Platt (sigmoid) vs Isotonic (flexible curve)
3. **Features**: 13 features (standard) vs 17 features (with opening odds)
4. **Training Data**: Different season splits (2017-2022 vs 2017-2023) → Different learned patterns

### Training Process

1. Split data by season (train/calib/test)
2. Engineer features (base + interactions + optional opening odds)
3. Train model (fit coefficients or trees)
4. Calibrate probabilities (Platt or Isotonic)
5. Save artifact for prediction

### Complete Workflow (Correct Order - CRITICAL)

**Follow this exact order for optimal performance:**

1. **Train models** → Create model artifacts (JSON files)
2. **Evaluate models** (optional but recommended) → Verify model quality on test set
3. **Precompute probabilities** → **MUST be done BEFORE grid search** → Scores all snapshots and stores in `derived.model_probabilities_v1` table
4. **Run grid search** → Uses precomputed probabilities for fast execution (falls back to on-the-fly prediction if precomputed missing)

**Why this order matters:**
- Grid search checks for precomputed probabilities first (fast)
- If precomputed probabilities don't exist, grid search falls back to on-the-fly prediction (slow)
- Precomputing once saves time when running multiple grid searches

### Grid Search Process

**Prerequisites**: Precomputed probabilities should exist in `derived.model_probabilities_v1` (run `precompute_model_probabilities.py` first)

1. Generate parameter combinations (entry/exit thresholds)
2. Split games (train/valid/test)
3. For each combination:
   - Load aligned data from `derived.snapshot_features_v1`
   - **Get model probabilities**: 
     - **First**: Check `derived.model_probabilities_v1` for precomputed values (fast)
     - **Fallback**: Predict on-the-fly using model artifact (slower)
   - Get Kalshi market prices (bid/ask)
   - Calculate divergence: `|model_prob - kalshi_price|`
   - Execute trading strategy (enter/exit based on thresholds)
   - Calculate metrics (profit, trades, win rate, etc.)
4. Select best combination based on train → validate → test

### Why Results Differ

1. **Model accuracy**: Better models → better probabilities → better trades
2. **Feature quality**: More features can help or hurt (signal vs noise)
3. **Calibration quality**: Better calibration → probabilities match reality
4. **Optimal thresholds**: Different models need different thresholds
5. **Data volume**: More games → more reliable estimates

### Key Takeaways

- **ESPN (default)** performs best because it uses source data directly
- **CatBoost models** can capture complex patterns but may overfit
- **Opening odds** add information but may not improve aggregate performance
- **Grid search** finds optimal trading parameters for each model
- **Results are comparable** when using same season (2025-26) and same grid search parameters

## Training All Models

**v2 Models** are trained on **2017-2022** (calibration on 2023, test on 2024) with fixed data splits and baseline usage. The training commands below create v2 models with consistent data splits.

### ⚠️ IMPORTANT: Correct Order of Operations

**Follow this exact sequence:**

1. ✅ **Train models** (create artifacts)
2. ✅ **Evaluate models** (optional - verify quality)
3. ✅ **Precompute probabilities** (REQUIRED before grid search)
4. ✅ **Run grid search** (uses precomputed probabilities)

**Why this order matters:**
- Grid search checks for precomputed probabilities first (fast database lookup)
- If precomputed probabilities don't exist, grid search falls back to on-the-fly prediction (slow, loads model for each snapshot)
- Precomputing once saves significant time when running multiple grid searches

### Commands to Train All Models (v2 - Fixed Split & Baseline)

**⚠️ IMPORTANT v2 Changes:**
- **Fixed train/calibration split**: Training now excludes calibration season (prevents data leakage)
- **Fixed baseline usage**: CatBoost models with opening odds now use baseline correctly
- **Fixed odds features**: Removed redundant features, fixed backwards time interaction
- **Training split**: Train on 2017-2022, calibrate on 2023, test on 2024

**Performance Optimizations (New):**
- `--cache-parquet`: Cache training data as Parquet file (saves ~60s on subsequent runs)
- `--work-mem`: PostgreSQL work_mem setting (default: 4GB, avoids disk spills)
- ORDER BY removed from SQL queries (saves ~15s)

**Recommended Database Indexes (run once in psql):**
```sql
-- Speed up prob_event_state lookups
CREATE INDEX CONCURRENTLY ix_prob_event_state_game_event 
ON espn.prob_event_state (game_id, event_id);

-- Speed up opening odds lookups
CREATE INDEX CONCURRENTLY ix_sportsbook_odds_opening
ON external.sportsbook_odds_snapshots (espn_game_id)
WHERE is_opening_line = TRUE;
```

**Baseline Model (without opening odds):**
```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --disable-opening-odds \
  --cache-parquet data/training_cache_baseline.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --disable-opening-odds \
  --cache-parquet data/training_cache_baseline.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_no_interaction_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --disable-opening-odds \
  --no-interaction-terms \
  --cache-parquet data/training_cache_baseline_no_interaction.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_no_interaction_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --disable-opening-odds \
  --no-interaction-terms \
  --cache-parquet data/training_cache_baseline_no_interaction.parquet \
  --dsn "$DATABASE_URL"
```

**Odds-Enabled Model (with opening odds - uses baseline):**
```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --cache-parquet data/training_cache_odds.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_no_interaction_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --no-interaction-terms \
  --cache-parquet data/training_cache_odds_no_interaction.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --cache-parquet data/training_cache_odds.parquet \
  --dsn "$DATABASE_URL"
```

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --no-interaction-terms \
  --cache-parquet data/training_cache_odds_no_interaction.parquet \
  --dsn "$DATABASE_URL"
```

### After Training - Correct Order of Operations

**IMPORTANT**: Follow this order for optimal performance:

1. **Train models** (create artifacts) - Already done above
2. **Evaluate models** on test season (2024) - Optional but recommended to verify model quality
3. **Precompute model probabilities** - MUST be done BEFORE grid search for performance
4. **Run grid searches** - Will use precomputed probabilities if available

---

### Step 1: Evaluate Models (Optional but Recommended)

Evaluate v2 models on test season (2024) to verify they work correctly:
   ```bash
   # Baseline models (v2)
   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_baseline_platt_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_baseline_platt_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --dsn "$DATABASE_URL"

   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_baseline_isotonic_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_baseline_isotonic_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   # Odds-enabled models (v2 - with baseline)
   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_odds_platt_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_odds_platt_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_odds_isotonic_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_odds_isotonic_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   # No-interaction baseline models (v2)
   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_baseline_no_interaction_platt_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_baseline_no_interaction_platt_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_baseline_no_interaction_isotonic_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_baseline_no_interaction_isotonic_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   # No-interaction odds-enabled models (v2 - with baseline)
   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_odds_no_interaction_platt_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_odds_no_interaction_platt_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"

   python scripts/model/evaluate_winprob_model.py \
     --artifact artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json \
     --season-start 2024 \
     --out data/models/evaluations/winprob_eval_catboost_odds_no_interaction_isotonic_v2_calib_2023_on_2024.json \
     --plot-calibration \
     --verbose \
     --dsn "$DATABASE_URL"
   ```

---

### Step 2: Precompute Model Probabilities (REQUIRED Before Grid Search)

**CRITICAL**: This must be run BEFORE grid search for optimal performance.

**Why**: Grid search will use precomputed probabilities from `derived.model_probabilities_v1` table, which is much faster than predicting on-the-fly for each snapshot.

**What it does**:
- Scores all snapshots in `derived.snapshot_features_v1` with all trained models
- Stores probabilities in `derived.model_probabilities_v1` table
- Grid search will automatically use these precomputed values

**Command**:
```bash
python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"
```

**Note**: This script automatically detects all available model artifacts and precomputes probabilities for each one. It will handle:
- All baseline models (with/without interactions)
- All odds-enabled models (with/without interactions)
- All calibration methods (Platt/Isotonic)

**After running**: Grid search will automatically use precomputed probabilities if available, falling back to on-the-fly prediction only if precomputed values are missing.

---

### Step 3: Run Grid Searches (v2 Models)

Run grid searches on 2025-26 season for v2 models:
   ```bash
   # Precompute probabilities for v2 models first
   python scripts/model/precompute_model_probabilities.py \
     --dsn "$DATABASE_URL"

   # Baseline models (v2)
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_baseline_platt_v2 \
     --dsn "$DATABASE_URL"

   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_baseline_isotonic_v2 \
     --dsn "$DATABASE_URL"

   # Odds-enabled models (v2)
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_odds_platt_v2 \
     --dsn "$DATABASE_URL"

   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_odds_isotonic_v2 \
     --dsn "$DATABASE_URL"

   # No-interaction baseline models (v2)
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_baseline_no_interaction_platt_v2 \
     --dsn "$DATABASE_URL"

   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_baseline_no_interaction_isotonic_v2 \
     --dsn "$DATABASE_URL"

   # No-interaction odds-enabled models (v2)
   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_odds_no_interaction_platt_v2 \
     --dsn "$DATABASE_URL"

   python scripts/trade/grid_search_hyperparameters.py \
     --season 2025-26 \
     --model-name catboost_odds_no_interaction_isotonic_v2 \
     --dsn "$DATABASE_URL"
   ```

---

### Step 4: Verification (After All Steps)

After training, verify the training seasons match:
```bash
python3 << 'EOF'
import json
from pathlib import Path

artifacts = {
    "catboost_platt": "data/models/winprob_catboost_platt_2017-2023.json",
    "catboost_baseline_platt": "artifacts/winprob_catboost_baseline_platt.json",
    "catboost_baseline_isotonic": "artifacts/winprob_catboost_baseline_isotonic.json",
    "catboost_odds_platt": "artifacts/winprob_catboost_odds_platt.json",
    "catboost_odds_isotonic": "artifacts/winprob_catboost_odds_isotonic.json",
    "catboost_baseline_no_interaction_platt": "artifacts/winprob_catboost_baseline_no_interaction_platt.json",
    "catboost_baseline_no_interaction_isotonic": "artifacts/winprob_catboost_baseline_no_interaction_isotonic.json",
    "catboost_odds_no_interaction_platt": "artifacts/winprob_catboost_odds_no_interaction_platt.json",
    "catboost_odds_no_interaction_isotonic": "artifacts/winprob_catboost_odds_no_interaction_isotonic.json",
}

for name, path_str in artifacts.items():
    path = Path(path_str)
    if path.exists():
        with open(path) as f:
            artifact = json.load(f)
        print(f"{name}: train_season_start_max = {artifact.get('train_season_start_max', 'N/A')}")
    else:
        print(f"{name}: File not found")
EOF
```

All v2 models should show `train_season_start_max = 2022` after training (calibration season 2023 is excluded from training).

## Files That Need Updates for All Models

To support all 8 new models (baseline/odds × platt/isotonic × with/without interactions), the following files need to be updated:

### 1. Model Training & Evaluation Scripts

**`scripts/model/train_winprob_catboost.py`**
- ✅ Already supports all models via command-line arguments
- Supported arguments:
  - `--calibration-method` (platt/isotonic)
  - `--disable-opening-odds` (for baseline models)
  - `--no-interaction-terms` (for simpler models)
  - `--cache-parquet PATH` (cache training data for faster iteration)
  - `--work-mem SIZE` (PostgreSQL memory setting, default 4GB)

**`scripts/model/evaluate_winprob_model.py`**
- ✅ Already supports opening odds detection and feature loading
- No changes needed (automatically detects features from artifact)

**`scripts/model/evaluate_winprob_time_buckets.py`**
- ✅ Already supports any model artifact
- No changes needed

### 2. Model Precomputation Script

**`scripts/model/precompute_model_probabilities.py`**
- **`create_table()` function** (lines 43-115):
  - Add 4 new columns for no-interaction models:
    - `catboost_baseline_no_interaction_platt_prob`
    - `catboost_baseline_no_interaction_isotonic_prob`
    - `catboost_odds_no_interaction_platt_prob`
    - `catboost_odds_no_interaction_isotonic_prob`
  - Add `DO $$ BEGIN ... END $$;` blocks for each new column (idempotent migration)
  
- **`load_all_models()` function** (lines 118-148):
  - Add 4 new model paths to `model_paths` dictionary:
    - `"catboost_baseline_no_interaction_platt": Path("artifacts/winprob_catboost_baseline_no_interaction_platt.json")`
    - `"catboost_baseline_no_interaction_isotonic": Path("artifacts/winprob_catboost_baseline_no_interaction_isotonic.json")`
    - `"catboost_odds_no_interaction_platt": Path("artifacts/winprob_catboost_odds_no_interaction_platt.json")`
    - `"catboost_odds_no_interaction_isotonic": Path("artifacts/winprob_catboost_odds_no_interaction_isotonic.json")`
  
- **`score_snapshot()` function** (lines 151-270):
  - Add 4 new keys to `results` dictionary (lines 156-165):
    - `"catboost_baseline_no_interaction_platt_prob": None`
    - `"catboost_baseline_no_interaction_isotonic_prob": None`
    - `"catboost_odds_no_interaction_platt_prob": None`
    - `"catboost_odds_no_interaction_isotonic_prob": None`
  - Add 4 new `elif` branches in model name mapping (after line 264):
    - `elif model_name == "catboost_baseline_no_interaction_platt": results["catboost_baseline_no_interaction_platt_prob"] = prob`
    - `elif model_name == "catboost_baseline_no_interaction_isotonic": results["catboost_baseline_no_interaction_isotonic_prob"] = prob`
    - `elif model_name == "catboost_odds_no_interaction_platt": results["catboost_odds_no_interaction_platt_prob"] = prob`
    - `elif model_name == "catboost_odds_no_interaction_isotonic": results["catboost_odds_no_interaction_isotonic_prob"] = prob`
  
- **`precompute_all()` function** (lines 273-432):
  - Update `INSERT` statement (around line 320) to include 4 new columns
  - Update `batch.append()` tuple (around line 330) to include 4 new probability values
  - Update `UPDATE` clause (around line 340) to include 4 new columns

### 3. Grid Search & Trading Simulation Scripts

**`scripts/trade/grid_search_hyperparameters.py`**
- **`load_model_artifact()` function** (lines 131-167):
  - Add 4 new entries to `model_file_map` dictionary (after line 157):
    - `"catboost_baseline_no_interaction_platt": "artifacts/winprob_catboost_baseline_no_interaction_platt.json"`
    - `"catboost_baseline_no_interaction_isotonic": "artifacts/winprob_catboost_baseline_no_interaction_isotonic.json"`
    - `"catboost_odds_no_interaction_platt": "artifacts/winprob_catboost_odds_no_interaction_platt.json"`
    - `"catboost_odds_no_interaction_isotonic": "artifacts/winprob_catboost_odds_no_interaction_isotonic.json"`
  - Update docstring (line 136) to list all 8 models

**`scripts/trade/simulate_trading_strategy.py`**
- **`get_aligned_data()` function** (lines 221-230):
  - Add 4 new entries to `model_prob_map` dictionary (after line 229):
    - `"catboost_baseline_no_interaction_platt": "mp.catboost_baseline_no_interaction_platt_prob"`
    - `"catboost_baseline_no_interaction_isotonic": "mp.catboost_baseline_no_interaction_isotonic_prob"`
    - `"catboost_odds_no_interaction_platt": "mp.catboost_odds_no_interaction_platt_prob"`
    - `"catboost_odds_no_interaction_isotonic": "mp.catboost_odds_no_interaction_isotonic_prob"`

**`scripts/trade/compare_grid_search_models.py`**
- ✅ Already dynamically loads all models from grid search results
- No changes needed (reads model names from JSON metadata)

### 4. Frontend API Endpoints

**`webapp/api/endpoints/model_comparison.py`**
- **`get_model_label()` function** (lines 25-44):
  - Add 4 new `elif` branches for no-interaction models (after line 42):
    - `elif "catboost_baseline_no_interaction_platt" in filename or ("baseline" in filename and "no_interaction" in filename and "platt" in filename): return "CatBoost Baseline (No Interactions) + Platt"`
    - `elif "catboost_baseline_no_interaction_isotonic" in filename or ("baseline" in filename and "no_interaction" in filename and "isotonic" in filename): return "CatBoost Baseline (No Interactions) + Isotonic"`
    - `elif "catboost_odds_no_interaction_platt" in filename or ("odds" in filename and "no_interaction" in filename and "platt" in filename): return "CatBoost + Opening Odds (No Interactions) + Platt"`
    - `elif "catboost_odds_no_interaction_isotonic" in filename or ("odds" in filename and "no_interaction" in filename and "isotonic" in filename): return "CatBoost + Opening Odds (No Interactions) + Isotonic"`
  
- **`get_model_color()` function** (lines 47-66):
  - Add 4 new `elif` branches for no-interaction models (after line 64):
    - `elif "Baseline (No Interactions) + Platt" in model_label: return "#dc2626"  # Red-600`
    - `elif "Baseline (No Interactions) + Isotonic" in model_label: return "#ea580c"  # Orange-600`
    - `elif "Opening Odds (No Interactions) + Platt" in model_label: return "#9333ea"  # Purple-600`
    - `elif "Opening Odds (No Interactions) + Isotonic" in model_label: return "#db2777"  # Pink-600`
  
- **`load_evaluation_reports()` function** (lines 69-107):
  - Add 4 new filenames to `model_files` list (after line 81):
    - `"winprob_eval_catboost_baseline_no_interaction_platt_calib_2023_on_2024.json"`
    - `"winprob_eval_catboost_baseline_no_interaction_isotonic_calib_2023_on_2024.json"`
    - `"winprob_eval_catboost_odds_no_interaction_platt_calib_2023_on_2024.json"`
    - `"winprob_eval_catboost_odds_no_interaction_isotonic_calib_2023_on_2024.json"`
  - Update docstring (line 70) to mention all 8 models

**`webapp/api/endpoints/grid_search.py`**
- **`_generate_grid_search_cache_key()` function** (if exists):
  - ✅ Already uses model_name in cache key generation
  - No changes needed
  
- **API endpoint docstrings** (lines 1019, etc.):
  - Update `model_name` parameter descriptions to list all 8 models

### 5. Frontend JavaScript Files (Optional - for UI display)

**`webapp/static/js/stats.js`**
- Currently hardcodes 4 models (logreg_platt, logreg_isotonic, catboost_platt, catboost_isotonic)
- **Optional**: Add support for displaying new models in aggregate stats page
- **Note**: Model comparison page (`model-comparison.js`) dynamically loads all models, so no changes needed there

**`webapp/static/js/model-comparison.js`**
- ✅ Already dynamically loads all models from API
- No changes needed

**`webapp/static/js/grid-search-comparison.js`**
- ✅ Already dynamically loads all models from grid search results
- No changes needed

### 6. Core Library Files

**`scripts/lib/_winprob_lib.py`**
- ✅ Already supports all models generically
- `build_design_matrix()` automatically handles optional features
- `predict_proba()` works with any CatBoost or Logistic Regression artifact
- No changes needed

### 7. Database Schema

**`scripts/model/precompute_model_probabilities.py`** (handles schema via `create_table()`)
- ✅ Schema updates handled in `create_table()` function
- Adds columns idempotently using `DO $$ BEGIN ... END $$;` blocks
- No separate migration file needed

### Summary

**Files Requiring Updates:**
1. ✅ `scripts/model/precompute_model_probabilities.py` - Add 4 no-interaction models (table schema, model loading, scoring, insertion)
2. ✅ `scripts/trade/grid_search_hyperparameters.py` - Add 4 no-interaction models to `load_model_artifact()`
3. ✅ `scripts/trade/simulate_trading_strategy.py` - Add 4 no-interaction models to `model_prob_map`
4. ✅ `webapp/api/endpoints/model_comparison.py` - Add 4 no-interaction models to label/color functions and evaluation file list
5. ⚠️ `webapp/api/endpoints/grid_search.py` - Update docstrings (optional, for clarity)

**Files Already Supporting All Models:**
- ✅ `scripts/model/train_winprob_catboost.py` - Uses command-line arguments
- ✅ `scripts/model/evaluate_winprob_model.py` - Auto-detects features
- ✅ `scripts/trade/compare_grid_search_models.py` - Dynamically loads from results
- ✅ `scripts/lib/_winprob_lib.py` - Generic model support
- ✅ `webapp/static/js/model-comparison.js` - Dynamically loads from API
- ✅ `webapp/static/js/grid-search-comparison.js` - Dynamically loads from results

**Total Files to Update: 4-5 files** (depending on whether grid_search.py docstrings are updated)

---

## Complete Command Reference (All Models)

### catboost_baseline_platt_v2

```bash
python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --disable-opening-odds \
  --cache-parquet data/training_cache_baseline.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_baseline_platt_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_baseline_platt_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_baseline_platt_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache


python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --disable-opening-odds \
  --cache-parquet data/training_cache_baseline.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_baseline_isotonic_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_baseline_isotonic_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_baseline_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --cache-parquet data/training_cache_odds.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_odds_platt_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_odds_platt_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_platt_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --cache-parquet data/training_cache_odds.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_odds_isotonic_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_odds_isotonic_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_no_interaction_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --disable-opening-odds \
  --no-interaction-terms \
  --cache-parquet data/training_cache_baseline_no_interaction.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_baseline_no_interaction_platt_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_baseline_no_interaction_platt_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_baseline_no_interaction_platt_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_baseline_no_interaction_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --disable-opening-odds \
  --no-interaction-terms \
  --cache-parquet data/training_cache_baseline_no_interaction.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_baseline_no_interaction_isotonic_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_baseline_no_interaction_isotonic_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_baseline_no_interaction_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_no_interaction_platt_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method platt \
  --no-interaction-terms \
  --cache-parquet data/training_cache_odds_no_interaction.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_odds_no_interaction_platt_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_odds_no_interaction_platt_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_no_interaction_platt_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache

python scripts/model/train_winprob_catboost.py \
  --out-artifact artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json \
  --train-season-start-max 2022 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --calibration-method isotonic \
  --no-interaction-terms \
  --cache-parquet data/training_cache_odds_no_interaction.parquet \
  --dsn "$DATABASE_URL"

python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_odds_no_interaction_isotonic_v2_calib_2023_on_2024.json \
  --plot-calibration \
  --verbose \
  --dsn "$DATABASE_URL"

python scripts/model/precompute_model_probabilities.py \
  --dsn "$DATABASE_URL"

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_no_interaction_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache
```