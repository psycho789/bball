# v2 Win Probability Models - Technical Documentation

**Date**: 2026-01-25  
**Audience**: Data Scientists  
**Purpose**: Comprehensive technical documentation for all v2 CatBoost win probability models

---

## Overview

The v2 model suite consists of 8 CatBoost-based win probability models trained on NBA game data from ESPN. These models predict the probability that the home team will win the game at any point during the game, using in-game state features and optionally pre-game betting odds.

### Model Naming Convention

Models follow the pattern: `catboost_{baseline|odds}_{no_interaction_}{platt|isotonic}_v2`

- **`baseline`**: Models trained without opening odds features (only in-game state)
- **`odds`**: Models trained with opening odds features (in-game state + pre-game betting odds)
- **`no_interaction`**: Models without interaction terms (simpler feature set)
- **`platt`**: Models calibrated using Platt scaling (parametric calibration)
- **`isotonic`**: Models calibrated using Isotonic regression (non-parametric calibration)
- **`v2`**: Version 2 (fixed data splits, corrected baseline usage, updated feature set)

---

## Model Inventory

### Baseline Models (Without Opening Odds)

1. **`catboost_baseline_platt_v2`**
   - Features: 13 (5 base + 8 interaction terms)
   - Calibration: Platt scaling
   - Opening odds: None

2. **`catboost_baseline_isotonic_v2`**
   - Features: 13 (5 base + 8 interaction terms)
   - Calibration: Isotonic regression
   - Opening odds: None

3. **`catboost_baseline_no_interaction_platt_v2`**
   - Features: 5 (base only, no interaction terms)
   - Calibration: Platt scaling
   - Opening odds: None

4. **`catboost_baseline_no_interaction_isotonic_v2`**
   - Features: 5 (base only, no interaction terms)
   - Calibration: Isotonic regression
   - Opening odds: None

### Odds-Enabled Models (With Opening Odds)

5. **`catboost_odds_platt_v2`**
   - Features: 15 (5 base + 8 interaction + 1 opening odds)
   - Calibration: Platt scaling
   - Opening odds: Features + baseline

6. **`catboost_odds_isotonic_v2`**
   - Features: 15 (5 base + 8 interaction + 1 opening odds)
   - Calibration: Isotonic regression
   - Opening odds: Features + baseline

7. **`catboost_odds_no_interaction_platt_v2`**
   - Features: 7 (5 base + 1 opening odds, no interaction terms)
   - Calibration: Platt scaling
   - Opening odds: Features + baseline

8. **`catboost_odds_no_interaction_isotonic_v2`**
   - Features: 7 (5 base + 1 opening odds, no interaction terms)
   - Calibration: Isotonic regression
   - Opening odds: Features + baseline

---

## Training Process

### Data Splits

All v2 models use a fixed, leak-proof data splitting strategy:

- **Training Set**: Seasons 2017-2022 (`season_start <= 2022`)
- **Calibration Set**: Season 2023 (`season_start == 2023`)
- **Test Set**: Season 2024 (`season_start == 2024`)

**Critical Design Decision**: The calibration season (2023) is explicitly excluded from training to prevent data leakage. This ensures that calibration parameters are learned on data the model has never seen during training.

### Data Source

Training data consists of:
- Historical win probability snapshots from ESPN's proprietary model
- Game state information (score differential, time remaining, possession)
- Final game outcomes (which team won)
- Opening betting odds from sportsbooks (for odds-enabled models)

### Label Definition

The target variable is binary:
- **1** if the home team won the game
- **0** if the away team won the game

Only snapshots from completed games with known outcomes are used for training.

### CatBoost Configuration

All models use identical CatBoost hyperparameters:

- **Algorithm**: Gradient Boosting (CatBoost)
- **Iterations**: 1000 trees
- **Tree Depth**: 4 (reduced from default 6 for regularization)
- **Learning Rate**: 0.1
- **Loss Function**: Logloss (binary cross-entropy)
- **Evaluation Metric**: AUC
- **Regularization**:
  - `l2_leaf_reg = 10.0` (L2 regularization on leaf values)
  - `subsample = 0.8` (80% of data per tree)
  - `random_strength = 1.0` (randomization strength)
  - `bagging_temperature = 1.0` (bagging temperature)
- **Random Seed**: 42 (for reproducibility)
- **Thread Count**: All available CPU cores

### Baseline Usage (Odds-Enabled Models)

For odds-enabled models, CatBoost uses a **baseline** (prior) derived from opening odds:

- **Baseline Value**: `logit(opening_prob_home_fair)` when opening odds are available
- **Baseline Value**: `0.0` (logit(0.5) = 0, representing 50/50 prior) when opening odds are missing

**Important**: The baseline is incorporated into the CatBoost model training process. CatBoost learns residuals from this baseline, effectively allowing the model to learn deviations from the market's pre-game assessment.

**Baseline vs Feature Distinction**:
- `opening_prob_home_fair` is used as a **baseline** (prior), not as a feature
- This prevents the model from simply memorizing the opening odds
- The model learns how in-game state modifies the pre-game probability

### Calibration Process

After training, models are calibrated on the calibration set (2023 season) to ensure predicted probabilities match observed frequencies.

#### Platt Scaling (Parametric)

Platt scaling fits a logistic regression to the model's raw predictions:

```
P_calibrated = sigmoid(alpha + beta * logit(P_raw))
```

Where:
- `alpha` and `beta` are learned parameters
- `P_raw` is the uncalibrated probability from CatBoost
- `logit(P_raw)` converts probability to log-odds space

**Fitting Method**: For CatBoost models, Platt scaling is fitted on logits (log-odds) rather than probabilities, which is more appropriate for gradient boosting models that output logits.

#### Isotonic Regression (Non-Parametric)

Isotonic regression learns a piecewise linear, monotonically increasing function:

```
P_calibrated = isotonic_transform(P_raw)
```

Where `isotonic_transform` is learned non-parametrically to ensure:
- Monotonicity: If `P_raw_1 < P_raw_2`, then `P_calibrated_1 <= P_calibrated_2`
- Calibration: Predicted probabilities match observed frequencies in bins

**Implementation**: Uses piecewise linear interpolation to ensure monotonicity and proper calibration.

### Model Artifacts

Each trained model consists of:
- Model metadata (version, training dates, data splits)
- Feature names and preprocessing parameters (normalization statistics)
- Calibration parameters (Platt or Isotonic)
- Trained gradient boosting trees
- Configuration indicating whether opening odds baseline was used during training

---

## Feature Engineering

### Base Features (Always Included)

All models include 5 base features:

1. **`point_differential_scaled`**: `(score_diff - mean) / std`
   - Raw: `score_diff = home_score - away_score`
   - Normalized using training set statistics

2. **`time_remaining_regulation_scaled`**: `(time_remaining - mean) / std`
   - Raw: `time_remaining` in seconds (0-2880 for regulation)
   - Normalized using training set statistics

3. **`possession_home`**: Binary (1 if home team has possession, 0 otherwise)
4. **`possession_away`**: Binary (1 if away team has possession, 0 otherwise)
5. **`possession_unknown`**: Binary (1 if possession is unknown/missing, 0 otherwise)

**Note**: Possession is one-hot encoded. Most snapshots have `possession = "unknown"` since ESPN data doesn't reliably track possession.

### Interaction Terms (If Enabled)

Models with interaction terms include 8 additional features:

1. **`score_diff_div_sqrt_time_remaining_scaled`**: `(score_diff / sqrt(time_remaining) - mean) / std`
   - Captures how score differential's importance changes with time remaining
   - Normalized using training set statistics

2. **`espn_home_prob_scaled`**: `(espn_home_prob - mean) / std`
   - ESPN's own win probability estimate (from their proprietary model)
   - Normalized using training set statistics

3. **`espn_home_prob_lag_1_scaled`**: `(espn_home_prob_lag_1 - mean) / std`
   - ESPN probability from the previous snapshot
   - Captures momentum/trend information

4. **`espn_home_prob_delta_1_scaled`**: `(espn_home_prob_delta_1 - mean) / std`
   - Change in ESPN probability: `espn_home_prob - espn_home_prob_lag_1`
   - Captures rate of change

5-8. **`period_1`**, **`period_2`**, **`period_3`**, **`period_4`**: One-hot encoded period indicators
   - Period 1: `time_remaining > 2160` seconds (first quarter)
   - Period 2: `1440 < time_remaining <= 2160` seconds (second quarter)
   - Period 3: `720 < time_remaining <= 1440` seconds (third quarter)
   - Period 4: `time_remaining <= 720` seconds (fourth quarter)

### Opening Odds Features (Odds-Enabled Models Only)

Models with opening odds include 1 engineered feature:

1. **`opening_overround`**: Overround/vig amount
   - Computed as: `(1/odds_home + 1/odds_away) - 1.0`
   - Represents the bookmaker's margin
   - May be `NaN` if odds are missing (CatBoost handles NaNs natively)

**Note**: `has_opening_moneyline` was removed (v2.1) as it was perfectly redundant with `opening_overround` (both derived from the same underlying condition). `has_opening_spread` and `has_opening_total` were removed (v2.2) due to very low feature importance (0.36% and 0.07% respectively) compared to `opening_overround` (24.15%). The presence of `opening_overround` (not NaN) already indicates valid moneyline odds exist.

**Opening Odds Processing**:
- Raw odds are filtered to include only opening lines (pre-game odds)
- Decimal odds format is used (not American format)
- Fair probabilities are computed via de-vigging: `p_home_fair = (1/odds_home) / (1/odds_home + 1/odds_away)`
- The fair opening probability is used as CatBoost baseline (not as a feature)

**Removed Features** (v2 changes):
- Fair opening probability removed from features (used as baseline only)
- Opening spread removed (redundant with moneyline)
- Opening total removed (redundant with moneyline)
- Time-weighted opening probability removed (prevented double-feeding odds signal)
- `has_opening_moneyline` removed (v2.1 - perfectly redundant with `opening_overround`)
- `has_opening_spread` removed (v2.2 - very low importance: 0.36%)
- `has_opening_total` removed (v2.2 - very low importance: 0.07%)

### Feature Normalization

All continuous features are normalized using training set statistics:
- Mean and standard deviation computed from training data only
- Test/calibration sets use training statistics (no data leakage)
- Missing values handled appropriately:
  - Interaction terms: Filled with 0.0 (missingness captured by other features)
  - Opening odds: Kept as missing values for CatBoost (missingness is treated as a signal)

---

## Evaluation Methodology

### Evaluation Metrics

Models are evaluated using standard binary classification metrics:

1. **Brier Score**: `mean((predicted_prob - actual_outcome)^2)`
   - Lower is better (perfect = 0.0)
   - Measures calibration and discrimination

2. **Log Loss**: `-mean(y * log(p) + (1-y) * log(1-p))`
   - Lower is better (perfect = 0.0)
   - Penalizes confident wrong predictions heavily

3. **ROC-AUC**: Area under the ROC curve
   - Higher is better (perfect = 1.0)
   - Measures discrimination ability (ranking quality)

4. **Expected Calibration Error (ECE)**: `mean(|predicted_prob - observed_rate|)` in bins
   - Lower is better (perfect = 0.0)
   - Measures calibration quality (probability accuracy)

### Evaluation Data

Models are evaluated on the test set (2024 season), which was held out during training and calibration.

### Per-Bucket Evaluation

Models are also evaluated across time buckets (e.g., every 60 seconds remaining) to assess performance at different game stages:
- Early game (high time remaining)
- Mid game
- Late game (low time remaining)

This helps identify if models perform differently at different game stages.

### Calibration Plots

Calibration quality is visualized using reliability diagrams:
- X-axis: Predicted probability (binned)
- Y-axis: Observed home win rate in each bin
- Perfect calibration: Points lie on the diagonal line (y = x)

---

## Model Differences Summary

### Baseline vs Odds-Enabled Models

| Aspect | Baseline Models | Odds-Enabled Models |
|--------|----------------|---------------------|
| **Features** | 5 or 13 | 7 or 15 |
| **Opening Odds** | None | 1 feature + baseline |
| **Baseline** | Zero (50/50 prior) | Logit of fair opening probability |
| **Use Case** | When odds unavailable | When odds available |

### With vs Without Interaction Terms

| Aspect | With Interactions | Without Interactions |
|--------|-------------------|---------------------|
| **Features** | 13 or 15 | 5 or 7 |
| **Interaction Terms** | 8 terms included | None |
| **Complexity** | Higher (more parameters) | Lower (fewer parameters) |
| **Use Case** | Capture complex patterns | Simpler, more interpretable |

### Platt vs Isotonic Calibration

| Aspect | Platt Scaling | Isotonic Regression |
|--------|---------------|---------------------|
| **Type** | Parametric (2 parameters) | Non-parametric (piecewise linear) |
| **Assumptions** | Monotonic relationship | Monotonic relationship |
| **Flexibility** | Less flexible | More flexible |
| **Overfitting Risk** | Lower | Higher (with small calibration sets) |
| **Use Case** | General-purpose | When Platt is insufficient |

---

## Key Design Decisions

### Why CatBoost?

- **Handles Missing Values**: CatBoost treats missing values as a signal, which is useful for opening odds features
- **Automatic Feature Interactions**: Gradient boosting can learn complex interactions automatically
- **Baseline Support**: CatBoost's baseline parameter allows incorporating market priors
- **Robust to Overfitting**: Regularization parameters help prevent overfitting

### Why Separate Baseline and Features?

- **Prevents Double-Feeding**: Using `opening_prob_home_fair` as both baseline and feature would allow the model to simply memorize opening odds
- **Residual Learning**: The model learns deviations from the market's pre-game assessment, which is more interpretable
- **Market Efficiency**: The baseline captures market-implied probabilities, while features capture in-game dynamics

### Why Fixed Data Splits?

- **Reproducibility**: Fixed splits ensure consistent evaluation across model versions
- **No Data Leakage**: Calibration season explicitly excluded from training
- **Fair Comparison**: All models evaluated on the same test set (2024 season)

### Why Two Calibration Methods?

- **Platt Scaling**: Fast, parametric, works well in most cases
- **Isotonic Regression**: More flexible, can handle non-linear calibration curves, useful when Platt is insufficient

---

## Usage Notes

### Prediction Requirements

When making predictions with odds-enabled models:

1. **Required**: Fair opening probability must be provided (used as baseline)
2. **Features**: Opening odds feature (overround) must be provided

**Baseline Inference**: The presence of valid opening odds is automatically inferred from whether `opening_prob_home_fair` is NaN or not. If NaN, baseline defaults to 0.0 (50/50 prior). If not NaN, baseline is computed as `logit(opening_prob_home_fair)`.

**Error Handling**: If a model was trained with baseline but the fair opening probability is missing at prediction time, the model will indicate an error condition rather than silently degrading performance.

### Precomputed Probabilities

For performance optimization, model probabilities can be precomputed and stored for faster access:
- Precomputation runs once and scores all historical snapshots
- Applications can use precomputed values when available
- Falls back to on-the-fly prediction if precomputed values are missing

### Model Versioning

- **v1**: Original models (different data splits, different baseline handling)
- **v2**: Current models (fixed splits, corrected baseline usage, updated feature set)

Model artifacts include configuration indicating whether baseline is required:
- Baseline required: Odds-enabled models
- Baseline not used: Baseline models

---

## Grid Search Hyperparameter Optimization

### Overview

Grid search is a **trading strategy optimization** technique used to find optimal entry/exit threshold combinations for trading applications. It systematically tests different parameter combinations to maximize trading performance metrics.

**Important**: Grid search methodology is **model-agnostic**—the same process applies regardless of which model you're using. The difference is that each model's predictions may lead to different optimal thresholds.

**Note**: This section describes how models are used in trading applications. For general model evaluation, see the "Evaluation Methodology" section above.

### What Grid Search Optimizes

Grid search optimizes **trading strategy parameters**, not model hyperparameters:

1. **Entry Threshold** (`entry_threshold`):
   - Range: 0.02 to 0.20 (default), step 0.01
   - Meaning: Minimum divergence between model probability and Kalshi market price to enter a trade
   - Example: `entry_threshold = 0.15` means enter when model prob differs from Kalshi price by at least 15 cents

2. **Exit Threshold** (`exit_threshold`):
   - Range: 0.00 to 0.05 (default), step 0.005
   - Meaning: Maximum divergence to exit a trade (take profit or cut loss)
   - Example: `exit_threshold = 0.01` means exit when divergence drops to 1 cent

**Constraint**: `exit_threshold < entry_threshold` (must exit at smaller divergence than entry)

### Grid Search Process

1. **Generate Parameter Combinations**:
   - Creates all valid (entry, exit) pairs satisfying constraints
   - Example: (0.02, 0.00), (0.02, 0.005), (0.03, 0.00), ..., (0.20, 0.045)
   - Typical grid: ~200-300 combinations

2. **Split Games** (deterministic, by random seed 42):
   - **Train**: 70% of games (used to identify top N combinations)
   - **Validation**: 15% of games (used to select final parameters from top N)
   - **Test**: 15% of games (final evaluation only, not used in selection)

3. **For Each Combination**:
   - Run trading simulation on all games in each split
   - Calculate metrics: net profit, number of trades, win rate, profit factor, max drawdown, etc.
   - Store results for all splits

4. **Select Best Parameters**:
   - Find top N combinations by profit on **train** set (default: top 10)
   - Among those top N, pick the one with best profit on **validation** set
   - Evaluate final choice on **test** set (reported metrics)

### Trading Strategy Execution

For each game snapshot:

1. **Get Model Probability**: Use model's predicted home win probability
2. **Get Market Price**: Current market price from prediction market exchange
3. **Calculate Divergence**: Absolute difference between model probability and market price
4. **Entry Decision**: Enter trade when divergence exceeds entry threshold
5. **Exit Decision**: Exit trade when divergence falls below exit threshold
6. **Calculate P&L**: Gross profit minus trading fees

**Trading Costs**:
- Kalshi fees: 7% × (price × (1 - price)) × bet_amount
- Highest at 50% probability (~1.75% of bet)
- Decreases toward probability extremes

### Why Different Models Have Different Optimal Thresholds

Each model produces different probability estimates, which leads to different optimal trading parameters:

- **Model Accuracy**: More accurate models can use tighter thresholds (more trades, higher profit)
- **Probability Distribution**: Models with different calibration may have different optimal entry/exit points
- **Feature Quality**: Models with better features may identify opportunities earlier or more accurately

**Example**:
- A model with opening odds and Platt calibration might find optimal thresholds: entry=0.15, exit=0.01
- A baseline model with Isotonic calibration might find optimal thresholds: entry=0.18, exit=0.015
- This reflects differences in how each model's predictions align with market prices

### Performance Optimization

**Precomputed Probabilities**:
- Grid search can use precomputed probabilities for faster execution
- **10x+ faster** than on-the-fly prediction (5-10 minutes vs 30-60+ minutes)
- Precomputation should be done before grid search for optimal performance

**Parallelization**:
- Grid search can parallelize across parameter combinations
- Each combination runs independently

### Grid Search Output

Grid search produces:
1. **Results File**: Detailed metrics for all combinations on train/valid/test splits
2. **Final Selection**: File with chosen parameters and metrics
3. **Visualizations** (optional):
   - Profit heatmaps (entry vs exit thresholds)
   - Marginal effect plots
   - Tradeoff scatter plots
   - Profit factor heatmaps

### Relationship to Models

Grid search is **independent of model training**:
- Models are trained first (creates model artifacts)
- Grid search uses model predictions (from artifacts or precomputed values)
- Grid search optimizes trading parameters, not model parameters
- Same grid search methodology applies to all models

**Typical Workflow**:
1. Train models → Create model artifacts
2. Precompute probabilities → Store for faster access (optional but recommended)
3. Run grid search → Optimize trading thresholds for each model
4. Compare results → Select best model + threshold combination

---

## Performance Characteristics

### Training Time

- **Data Loading**: ~60-120 seconds
- **Feature Engineering**: ~5-10 seconds
- **CatBoost Training**: ~30-60 minutes (depends on data size and iterations)
- **Calibration**: ~1-5 seconds
- **Total**: ~30-60 minutes per model

### Prediction Time

- **Precomputed**: < 1ms per snapshot (when using precomputed values)
- **On-the-Fly**: ~1-5ms per snapshot (model loading + prediction)
- **Batch Prediction**: Faster per-sample (model loaded once)

### Model Size

- **JSON Artifact**: ~10-50 KB
- **CatBoost Model (.cbm)**: ~1-5 MB (depends on iterations and depth)

---

## Limitations and Considerations

### Data Availability

- **Opening Odds**: Not all games have opening odds available
  - Baseline models can be used when odds are missing
  - Odds-enabled models require odds for optimal performance

### Missing Values

- **Missing Values**: CatBoost handles missing values natively (treats as signal)
- **Interaction Terms**: Missing values filled with 0.0 (missingness captured by other features)
- **Possession**: Often "unknown" in ESPN data (captured by possession_unknown feature)

### Calibration Quality

- Calibration improves probability estimates but doesn't necessarily improve discrimination (AUC)
- Poor calibration can be fixed with recalibration, but poor discrimination requires retraining

### Overfitting Risk

- Regularization parameters help prevent overfitting
- Test set evaluation provides unbiased performance estimates
- Calibration set is separate from training set (no leakage)

---

## References

- **CatBoost Documentation**: https://catboost.ai/
- **Platt Scaling**: Platt, J. (1999). "Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods"
- **Isotonic Regression**: Zadrozny, B. & Elkan, C. (2002). "Transforming classifier scores into accurate multiclass probability estimates"

---

## Appendix: Feature Counts by Model

| Model | Base | Interactions | Opening Odds | Total |
|-------|------|-------------|--------------|-------|
| `catboost_baseline_platt_v2` | 5 | 8 | 0 | 13 |
| `catboost_baseline_isotonic_v2` | 5 | 8 | 0 | 13 |
| `catboost_baseline_no_interaction_platt_v2` | 5 | 0 | 0 | 5 |
| `catboost_baseline_no_interaction_isotonic_v2` | 5 | 0 | 0 | 5 |
| `catboost_odds_platt_v2` | 5 | 8 | 1 | 15 |
| `catboost_odds_isotonic_v2` | 5 | 8 | 1 | 15 |
| `catboost_odds_no_interaction_platt_v2` | 5 | 0 | 1 | 7 |
| `catboost_odds_no_interaction_isotonic_v2` | 5 | 0 | 1 | 7 |

**Note**: Baseline models use zero baseline (no opening odds). Odds-enabled models use the logit of the fair opening probability as baseline (not counted as a feature).
