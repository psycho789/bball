# Model Comparison Script - Analysis

**Date**: 2026-01-26  
**Audience**: Non-data-scientist  
**Purpose**: Analyze what a model comparison script could compare and why it would be useful

---

## Current State

You already have several comparison mechanisms:

1. **Grid Search Comparison** (`compare_grid_search_models.py`)
   - Compares models based on **trading strategy performance**
   - Metrics: Profit, trades, win rate, entry/exit thresholds, profit factor, drawdown
   - Focus: Which model makes the most money when used for trading

2. **Model Evaluation Reports** (`evaluate_winprob_model.py`)
   - Evaluates models based on **prediction accuracy**
   - Metrics: Logloss, Brier score, ROC-AUC, Expected Calibration Error (ECE)
   - Focus: How well models predict win probabilities

3. **Web API Endpoint** (`/stats/model-comparison`)
   - Serves evaluation metrics for frontend visualization
   - Focus: Displaying model performance in the web app

---

## What a Model Comparison Script Could Do

A standalone model comparison script could provide **comprehensive analysis** that combines and extends what you already have. Here's what it could compare:

### 1. **Prediction Accuracy Comparison** (From Evaluation Reports)

**What**: Compare how well each model predicts win probabilities

**Metrics to Compare**:
- **Logloss** (lower is better): Penalizes confident wrong predictions
- **Brier Score** (lower is better): Measures overall prediction quality
- **ROC-AUC** (higher is better): Measures how well models rank games (discrimination)
- **Expected Calibration Error (ECE)** (lower is better): Measures if probabilities are accurate (calibration)

**Why Useful**: 
- Shows which models are best at predicting probabilities
- Helps identify if a model is overconfident or underconfident
- Can reveal if trading performance differences are due to prediction quality or strategy optimization

**Example Output**:
```
Prediction Accuracy Comparison (2024 Season)
===========================================
Model                              Logloss    Brier     ROC-AUC   ECE
---------------------------------------------------------------------
catboost_baseline_platt_v2         0.4537     0.1521    0.8592    0.0118
catboost_baseline_isotonic_v2       0.4542     0.1523    0.8589    0.0121
catboost_odds_platt_v2              0.4512     0.1518    0.8612    0.0109
...
```

### 2. **Trading Performance Comparison** (From Grid Search Results)

**What**: Compare how profitable each model is when used for trading

**Metrics to Compare**:
- **Test Profit**: Total profit on test set
- **Profit Factor**: Ratio of gross profit to gross loss
- **Win Rate**: Percentage of profitable trades
- **Max Drawdown**: Largest peak-to-trough decline
- **Average Profit per Trade**: Profitability per trade
- **Number of Trades**: Trading frequency

**Why Useful**:
- Shows which models actually make money in practice
- Reveals trade-offs between profit and trade frequency
- Helps identify models with better risk-adjusted returns

**Example Output**:
```
Trading Performance Comparison (2024 Season)
============================================
Model                              Profit     Trades    Win Rate  Profit Factor
-------------------------------------------------------------------------------
ESPN (default)                      $1,942.84   332      72.9%     7.62
catboost_baseline_platt             $1,899.70   367      66.8%     6.12
catboost_baseline_isotonic          $1,826.54   321      71.0%     6.43
...
```

### 3. **Combined Analysis** (Prediction + Trading)

**What**: Compare both prediction accuracy AND trading performance side-by-side

**Why Useful**:
- Reveals if better predictions lead to better trading results
- Identifies models that predict well but trade poorly (or vice versa)
- Helps understand the relationship between model quality and profitability

**Example Output**:
```
Combined Model Comparison (2024 Season)
=======================================
Model                              Prediction Quality          Trading Performance
                                   Logloss  ROC-AUC  ECE       Profit   Win Rate
-------------------------------------------------------------------------------
catboost_baseline_platt_v2          0.4537   0.8592  0.0118   $1,776   66.5%
catboost_odds_platt_v2              0.4512   0.8612  0.0109   $776     57.9%
...
```

**Key Insight**: You might find that `catboost_odds_platt_v2` has better prediction metrics but worse trading performance. This could indicate:
- The model is overfitting to prediction metrics
- The trading strategy thresholds aren't optimized for this model
- The model's predictions don't align well with profitable trading opportunities

### 4. **Per-Time-Bucket Comparison**

**What**: Compare model performance at different game stages (early, mid, late game)

**Metrics**: Same as above, but broken down by time remaining (e.g., 0-5 min, 5-10 min, etc.)

**Why Useful**:
- Identifies which models perform best in different game situations
- Reveals if some models are better at early game vs. late game predictions
- Helps optimize trading strategies for different game stages

**Example Output**:
```
Per-Time-Bucket Comparison
==========================
Time Remaining: 0-5 minutes
Model                              Logloss    ROC-AUC   Profit
---------------------------------------------------------------------
catboost_baseline_platt_v2         0.4123     0.8912    $450
catboost_odds_platt_v2              0.4101     0.8923    $380
...

Time Remaining: 5-10 minutes
Model                              Logloss    ROC-AUC   Profit
---------------------------------------------------------------------
catboost_baseline_platt_v2         0.4456     0.8654    $320
...
```

### 5. **Calibration Quality Comparison**

**What**: Compare how well-calibrated each model's probabilities are

**Metrics**:
- **Calibration plots**: Visual comparison of predicted vs. observed probabilities
- **ECE by probability range**: How well-calibrated models are at different probability levels
- **Overconfidence/Underconfidence**: Whether models are systematically too confident or not confident enough

**Why Useful**:
- Well-calibrated models give you accurate probabilities (e.g., when model says 70%, it wins 70% of the time)
- Poorly calibrated models can mislead trading decisions
- Helps identify if Platt scaling vs. Isotonic regression makes a difference

**Example Output**:
```
Calibration Quality Comparison
==============================
Model                              ECE      Overconfident?  Underconfident?
----------------------------------------------------------------------------
catboost_baseline_platt_v2         0.0118   No             No
catboost_baseline_isotonic_v2      0.0121   No             No
catboost_odds_platt_v2              0.0109   No             No
...
```

### 6. **Statistical Significance Testing**

**What**: Determine if differences between models are statistically significant or just noise

**Tests**:
- **Paired t-tests**: Compare prediction errors between models
- **Bootstrap confidence intervals**: Estimate uncertainty in profit differences
- **Significance levels**: p-values indicating if differences are real

**Why Useful**:
- Prevents choosing a model based on random variation
- Helps identify if small differences are meaningful
- Provides confidence in model selection decisions

**Example Output**:
```
Statistical Significance Tests
===============================
Comparison: catboost_baseline_platt_v2 vs ESPN (default)
- Logloss difference: -0.0023 (p-value: 0.023) ✓ Significant
- Profit difference: -$166.74 (p-value: 0.15) ✗ Not significant
- Win rate difference: -6.4% (p-value: 0.08) ✗ Not significant
```

### 7. **Model Characteristics Comparison**

**What**: Compare model features, training data, and configuration

**Metrics**:
- **Feature count**: Number of features used
- **Training seasons**: Which seasons were used for training
- **Calibration method**: Platt vs. Isotonic
- **Opening odds**: Whether model uses pre-game odds
- **Interaction terms**: Whether model uses interaction features

**Why Useful**:
- Helps understand why models perform differently
- Identifies which features/configurations contribute to performance
- Guides future model development

**Example Output**:
```
Model Characteristics Comparison
===============================
Model                              Features  Training    Calibration  Opening Odds
-------------------------------------------------------------------------------
catboost_baseline_platt_v2         13        2017-2022   Platt        No
catboost_odds_platt_v2             15        2017-2022   Platt        Yes
catboost_baseline_no_interaction_platt_v2  5  2017-2022   Platt        No
...
```

### 8. **Ranking and Recommendations**

**What**: Provide overall rankings and recommendations based on multiple criteria

**Rankings**:
- **Best for prediction accuracy**: Top models by logloss/Brier/ROC-AUC
- **Best for trading**: Top models by profit/profit factor
- **Best overall**: Balanced score considering both prediction and trading
- **Most reliable**: Models with consistent performance across metrics

**Why Useful**:
- Provides clear guidance on which models to use
- Helps prioritize model development efforts
- Identifies models that excel in specific use cases

**Example Output**:
```
Model Rankings (2024 Season)
============================
Best Prediction Accuracy:
  1. catboost_odds_platt_v2 (Logloss: 0.4512, ROC-AUC: 0.8612)
  2. catboost_baseline_platt_v2 (Logloss: 0.4537, ROC-AUC: 0.8592)
  3. catboost_baseline_isotonic_v2 (Logloss: 0.4542, ROC-AUC: 0.8589)

Best Trading Performance:
  1. ESPN (default) (Profit: $1,942.84, Win Rate: 72.9%)
  2. catboost_baseline_platt (Profit: $1,899.70, Win Rate: 66.8%)
  3. catboost_baseline_isotonic (Profit: $1,826.54, Win Rate: 71.0%)

Best Overall (Balanced Score):
  1. catboost_baseline_platt_v2
  2. catboost_baseline_isotonic_v2
  3. catboost_odds_no_interaction_platt_v2
```

---

## Key Differences from Existing Tools

| Tool | Focus | What It Compares |
|------|-------|------------------|
| **Grid Search Comparison** | Trading performance | Profit, trades, win rate, thresholds |
| **Model Evaluation** | Prediction accuracy | Logloss, Brier, ROC-AUC, ECE (per model) |
| **Web API** | Frontend display | Serves evaluation metrics for visualization |
| **Model Comparison Script** | Comprehensive analysis | **All of the above + statistical tests + rankings + recommendations** |

---

## What Would Be Most Useful?

Based on your current setup, here are the **most valuable comparisons** a model comparison script could provide:

### High Value

1. **Combined Prediction + Trading Analysis**
   - Shows if better predictions = better trading (often they don't!)
   - Helps identify models that predict well but trade poorly

2. **Statistical Significance Testing**
   - Prevents choosing models based on random variation
   - Provides confidence in model selection

3. **Per-Time-Bucket Comparison**
   - Identifies which models work best at different game stages
   - Helps optimize trading strategies

### Medium Value

4. **Calibration Quality Comparison**
   - Helps understand if probabilities are trustworthy
   - Useful for understanding model behavior

5. **Rankings and Recommendations**
   - Provides clear guidance on model selection
   - Helps prioritize development efforts

### Lower Value (Already Covered)

6. **Prediction Accuracy Comparison** - Already in evaluation reports
7. **Trading Performance Comparison** - Already in grid search comparison
8. **Model Characteristics** - Already documented in model README

---

## Recommended Approach

A model comparison script should:

1. **Load data from both sources**:
   - Evaluation reports (`data/models/evaluations/*.json`)
   - Grid search results (`data/grid_search/*/final_selection.json`)

2. **Combine and analyze**:
   - Side-by-side prediction vs. trading metrics
   - Statistical significance tests
   - Per-time-bucket breakdowns
   - Rankings and recommendations

3. **Output formats**:
   - Console tables (like grid search comparison)
   - JSON export (for programmatic use)
   - Markdown report (for documentation)
   - Optional: HTML report with visualizations

4. **Key features**:
   - Compare all models or filter by model type
   - Compare across different seasons
   - Highlight significant differences
   - Provide actionable recommendations

---

## Example Use Cases

### Use Case 1: "Which model should I use for trading?"
**Answer**: Model comparison script shows:
- Trading performance rankings
- Statistical significance of profit differences
- Risk-adjusted metrics (profit factor, drawdown)
- Recommendation: Use model with best risk-adjusted returns

### Use Case 2: "Why does Model A predict better but trade worse?"
**Answer**: Model comparison script shows:
- Prediction metrics vs. trading metrics side-by-side
- Per-time-bucket breakdown (maybe Model A is worse in late game where trades happen)
- Calibration analysis (maybe Model A is poorly calibrated at probability ranges used for trading)
- Recommendation: Optimize trading thresholds for Model A, or use Model B

### Use Case 3: "Is the difference between models real or just noise?"
**Answer**: Model comparison script shows:
- Statistical significance tests
- Bootstrap confidence intervals
- Recommendation: Only use differences that are statistically significant

---

## Summary

A model comparison script would be valuable because it:

1. **Combines** prediction accuracy and trading performance in one place
2. **Tests** if differences are statistically significant
3. **Breaks down** performance by game stage (time buckets)
4. **Ranks** models and provides recommendations
5. **Explains** why models perform differently

The script would complement your existing tools by providing **comprehensive analysis** that helps you make informed decisions about which models to use and why.
