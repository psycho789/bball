# ESPN Baseline Model Implementation Verification

**Date:** 2026-01-26  
**Author:** Analysis  
**Purpose:** Verify ESPN baseline model is correctly implemented and using the right data source

## Executive Summary

The ESPN baseline model correctly uses ESPN's raw win probability directly from the database without any model predictions or calibration. This is the intended behavior - ESPN baseline serves as a baseline comparison to evaluate whether ML models improve upon ESPN's native probabilities.

## Implementation Analysis

### 1. Data Source

**Location:** `scripts/trade/simulate_trading_strategy.py`

**Query (lines 200-210):**
```python
base_columns = [
    "sf.snapshot_ts",
    "sf.espn_home_prob",  # ← ESPN's raw win probability
    "sf.kalshi_home_mid_price",
    "sf.kalshi_home_bid",
    "sf.kalshi_home_ask",
    ...
]
```

**Source:** `derived.snapshot_features_v1` canonical dataset
- `espn_home_prob` comes directly from ESPN's probability feed
- No model predictions or transformations applied
- Normalized to 0-1 range via `_norm01()` helper (line 476)

### 2. Probability Assignment Logic

**Location:** `scripts/trade/simulate_trading_strategy.py:515`

```python
final_prob = float(espn_home_prob)  # Default to ESPN probability

# Check for pre-computed probability first (if model_name provided)
precomputed_prob = None
if model_name and model_prob_col_idx is not None:
    # Use pre-computed probability
    ...
elif model_artifact is not None:
    # Use model prediction
    ...
# If neither model_name nor model_artifact provided, final_prob stays as ESPN
```

**For ESPN Baseline:**
- `model_name` = `None` (not provided)
- `model_artifact` = `None` (not provided)
- Result: `final_prob = espn_home_prob` (ESPN's raw probability)

### 3. Trading Simulation Usage

**Location:** `scripts/trade/simulate_trading_strategy.py:1216`

```python
# Calculate divergence (in probability units, 0-1 range)
divergence_prob = espn_prob - kalshi_price
```

**For ESPN Baseline:**
- `espn_prob` = ESPN's raw win probability (from database)
- `kalshi_price` = Kalshi market price (from database)
- `divergence_prob` = ESPN raw prob - Kalshi price

**For ML Models:**
- `espn_prob` = ML model's predicted probability (may use ESPN as a feature)
- `kalshi_price` = Kalshi market price (from database)
- `divergence_prob` = Model prob - Kalshi price

### Where ML Model Predicted Probabilities Come From

ML models have **two sources** for their predicted probabilities:

#### 1. **Pre-Computed Probabilities (Preferred/Fast Path)**

**Database Table:** `derived.model_probabilities_v1`

**Columns:**
- `catboost_baseline_platt_v2_prob`
- `catboost_baseline_isotonic_v2_prob`
- `catboost_odds_platt_v2_prob`
- `catboost_odds_isotonic_v2_prob`
- `catboost_baseline_no_interaction_platt_v2_prob`
- `catboost_baseline_no_interaction_isotonic_v2_prob`
- `catboost_odds_no_interaction_platt_v2_prob`
- `catboost_odds_no_interaction_isotonic_v2_prob`
- (and v1 model columns)

**How They're Generated:**
- Script: `scripts/model/precompute_model_probabilities.py`
- Process: Loads model artifacts → Scores all snapshots → Stores results in database
- When: Run after training new models or when models are updated
- Performance: **Much faster** - grid search just reads pre-computed values (like ESPN)

**Query (lines 285-293):**
```python
LEFT JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
```

**Usage (lines 518-530):**
```python
if model_name and model_prob_col_idx is not None:
    precomputed_prob = row[model_prob_col_idx]  # Read from database
    
if precomputed_prob is not None:
    final_prob = float(precomputed_prob)  # Use pre-computed value
```

#### 2. **On-The-Fly Computation (Fallback)**

**When Used:**
- Pre-computed probability is `NULL` or missing
- `model_name` not provided but `model_artifact` is provided

**Process (lines 531-710):**
1. Extract features from database row (score_diff, time_remaining, ESPN prob, opening odds, etc.)
2. Build design matrix using `build_design_matrix()` function
3. Score model using `predict_proba()` function with the model artifact
4. Apply calibration (Platt Scaling or Isotonic Regression) if model uses it

**Code Flow:**
```python
elif model_artifact is not None:
    # Extract features from row
    score_diff = row[row_idx]
    time_remaining = row[8]
    espn_home_prob = row[1]
    # ... extract other features
    
    # Build design matrix
    X = build_design_matrix(
        point_differential=point_differential,
        time_remaining_regulation=time_remaining_regulation,
        espn_home_prob=espn_prob_arr,
        # ... other features
    )
    
    # Predict probability
    prob_array = predict_proba(
        model_artifact, 
        X=X,
        opening_prob_home_fair=opening_prob_home_fair_arr,
    )
    final_prob = float(prob_array[0])  # Model's predicted probability
```

**Performance:** Slower - requires feature extraction and model scoring for each snapshot

### How to Access ML Model Probabilities

**Option 1: Query Database Directly**
```sql
SELECT 
    game_id,
    snapshot_ts,
    catboost_baseline_platt_v2_prob,
    catboost_odds_platt_v2_prob,
    -- ... other model columns
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND game_id = '401585401'
ORDER BY snapshot_ts;
```

**Option 2: Use Precompute Script**
```bash
python scripts/model/precompute_model_probabilities.py --dsn "$DATABASE_URL"
```

**Option 3: Query via Code**
```python
from scripts.trade.simulate_trading_strategy import get_aligned_data
aligned_data, ... = get_aligned_data(
    conn, game_id,
    model_name="catboost_baseline_platt_v2"  # Uses pre-computed probabilities
)
# aligned_data[0]['espn_prob'] contains the model's predicted probability
```

## Verification: Is This Correct?

### ✅ Correct Implementation

**Yes, the implementation is correct.** Here's why:

1. **ESPN Baseline Purpose:** ESPN baseline serves as a baseline comparison to evaluate whether ML models improve trading performance. It should use ESPN's raw probability as-is, without any modifications.

2. **Data Consistency:** Both ESPN baseline and ML models use the same:
   - Data source (`derived.snapshot_features_v1`)
   - Kalshi prices (for comparison)
   - Trading logic (same entry/exit thresholds)
   - The only difference is the probability source (ESPN raw vs. ML prediction)

3. **Fair Comparison:** Using ESPN's raw probability ensures a fair comparison - if ML models can't beat ESPN's native probabilities with optimized thresholds, they're not adding value.

### Expected Behavior

**ESPN Baseline should:**
- Use ESPN's raw win probability directly
- Not apply any calibration or adjustments
- Serve as a baseline for comparison
- Use the same trading logic as ML models

**ESPN Baseline should NOT:**
- Use model predictions
- Apply calibration (Platt/Isotonic)
- Transform or adjust ESPN probabilities
- Use pre-computed model probabilities

## Comparison with ML Models

### ESPN Baseline vs. ML Models

| Aspect | ESPN Baseline | ML Models |
|--------|---------------|-----------|
| **Probability Source** | ESPN raw (`espn_home_prob`) | ML model prediction |
| **Features Used** | None | Score diff, time remaining, ESPN prob (as feature), opening odds, etc. |
| **Calibration** | None | Platt Scaling or Isotonic Regression |
| **Pre-computation** | N/A | Optional (from `derived.model_probabilities_v1`) |
| **Trading Logic** | Same | Same |
| **Kalshi Prices** | Same | Same |

### Performance Comparison

From grid search results (2025-26 season, test set):

| Model | Test Profit | Trades | Win Rate | Entry | Exit |
|-------|-------------|--------|----------|-------|------|
| **ESPN (default)** | **$1,942.84** | 332 | 72.9% | 0.19 | 0.015 |
| catboost_baseline_platt_v2 | $1,776.10 | 331 | 66.5% | 0.19 | 0.015 |
| catboost_baseline_isotonic_v2 | $1,755.45 | 336 | 70.5% | 0.18 | 0.015 |
| catboost_odds_platt_v2 | $776.85 | 259 | 57.9% | 0.17 | 0.015 |

**Observation:** ESPN baseline outperforms all v2 models on test set. This suggests:
- ESPN's native probabilities are already well-calibrated
- ML models may be overfitting or not capturing additional signal
- The trading strategy works well with ESPN's probabilities

## Code Flow Verification

### ESPN Baseline Execution Path

1. **Grid Search Call:**
   ```python
   # grid_search_hyperparameters.py
   model_artifact = load_model_artifact(config.model_name) if config.model_name else None
   # For ESPN: config.model_name = None → model_artifact = None
   ```

2. **Data Retrieval:**
   ```python
   # simulate_trading_strategy.py:get_aligned_data()
   aligned_data, ... = get_aligned_data(
       conn, game_id,
       model_artifact=None,  # ← None for ESPN baseline
       model_name=None        # ← None for ESPN baseline
   )
   ```

3. **Probability Assignment:**
   ```python
   # simulate_trading_strategy.py:515
   final_prob = float(espn_home_prob)  # ← Uses ESPN raw probability
   # No model_name check passes (model_name is None)
   # No model_artifact check passes (model_artifact is None)
   # final_prob remains as ESPN probability
   ```

4. **Trading Simulation:**
   ```python
   # simulate_trading_strategy.py:1216
   divergence_prob = espn_prob - kalshi_price
   # espn_prob = ESPN raw probability (for baseline)
   ```

## Potential Issues & Edge Cases

### ✅ Handled Correctly

1. **Missing ESPN Data:** Line 483-486 filters out rows without ESPN probability
2. **Out of Range Values:** Line 495-498 validates ESPN probability is in [0,1] range
3. **Normalization:** Line 476 normalizes ESPN probability to 0-1 range (handles both 0-1 and 0-100 formats)

### ⚠️ Considerations

1. **ESPN Probability Quality:** ESPN probabilities are assumed to be well-calibrated. If ESPN's probabilities are systematically biased, the baseline comparison may be unfair.

2. **Temporal Consistency:** ESPN probabilities may have changed over time (algorithm updates, data quality improvements). The baseline uses whatever ESPN probability was recorded at the time.

3. **Calibration:** ESPN probabilities are not calibrated (no Platt/Isotonic). If ESPN probabilities are miscalibrated, the baseline may underperform compared to calibrated ML models.

## Recommendations

### ✅ No Changes Needed

The ESPN baseline implementation is **correct and should not be changed**. It correctly:
- Uses ESPN's raw probability directly
- Provides a fair baseline for comparison
- Uses the same trading logic as ML models

### 📊 Analysis Suggestions

1. **Calibration Analysis:** Compare ESPN probability calibration vs. ML model calibration to understand why ESPN baseline performs well.

2. **Feature Importance:** Analyze which features ML models use most (ESPN prob as feature, score diff, etc.) to understand what signal they're capturing.

3. **Temporal Analysis:** Check if ESPN baseline performance is consistent across different time periods (early season vs. late season, different years).

## Conclusion

**The ESPN baseline model is correctly implemented.** It uses ESPN's raw win probability directly from the database without any model predictions or calibration, which is the intended behavior for a baseline comparison. The implementation is consistent, handles edge cases properly, and provides a fair comparison point for evaluating ML model performance.

**Status:** ✅ **VERIFIED - Implementation is Correct**
