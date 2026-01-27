# V2 Model Retraining Results Analysis

**Date**: 2026-01-22  
**Model**: `catboost_odds_platt_v2`  
**Training Time**: 8.13 minutes (487.71 seconds)  
**Status**: Partial Improvement - Regularization helped but target not met

---

## Executive Summary

The retrained `catboost_odds_platt_v2` model shows **partial improvement** but still does not meet all success criteria:

### Key Results

**Feature Importance**:
- **Current**: 69.19% from opening odds (down from 88% in v1)
- **Target**: < 50%
- **Status**: ⚠️ **IMPROVED BUT STILL ABOVE TARGET** (19% reduction, but 19% above target)

**Calibration Parameters**:
- **Alpha**: -0.0228 (normal: 0.5-2.0) ⚠️ **STILL EXTREME**
- **Beta**: 1.209 (normal: -1.0 to 1.0) ⚠️ **STILL EXTREME**
- **Status**: ⚠️ **NO IMPROVEMENT** (still outside normal ranges)

**Feature Importance Distribution**:
- Top 5 features: 4 opening odds features (68.45% combined)
- Top 10 features: 5 opening odds features
- In-game features improved: `score_diff_div_sqrt_time_remaining_scaled` now #3 (17.88% importance)

### Assessment

**Progress Made**:
- ✅ Feature importance reduced from 88% to 69.19% (21% relative reduction)
- ✅ In-game features gained importance (`score_diff_div_sqrt_time_remaining_scaled` is now #3)
- ✅ Model training completed successfully with regularization

**Remaining Issues**:
- ⚠️ Feature importance still 19% above target (69.19% vs < 50%)
- ⚠️ Calibration parameters still extreme (no improvement)
- ⚠️ Opening odds features still dominate top 5 positions

---

## Detailed Results

### Feature Importance Analysis

**Top 15 Features** (from inspection script output):

| Rank | Feature Name | Importance | Type | % of Total |
|------|--------------|------------|------|------------|
| 1 | opening_total | 24.02 | 🔴 Odds | 24.02% |
| 2 | opening_prob_home_fair | 19.60 | 🔴 Odds | 19.60% |
| 3 | score_diff_div_sqrt_time_remaining_scaled | 17.88 | Other | 17.88% |
| 4 | opening_overround | 13.57 | 🔴 Odds | 13.57% |
| 5 | opening_spread | 11.26 | 🔴 Odds | 11.26% |
| 6 | espn_home_prob_scaled | 6.42 | Other | 6.42% |
| 7 | espn_home_prob_lag_1_scaled | 5.70 | Other | 5.70% |
| 8 | opening_spread_div_time_remaining_scaled | 0.61 | 🔴 Odds | 0.61% |
| 9 | time_remaining_regulation_scaled | 0.53 | Other | 0.53% |
| 10 | point_differential_scaled | 0.18 | Other | 0.18% |

**Opening Odds Features Summary**:
- **Top 5**: 4 opening odds features (68.45% combined)
- **Top 10**: 5 opening odds features (69.19% total)
- **All opening odds features**: 69.19% of total importance

**Comparison to V1**:
- **V1**: Top 4 features were ALL opening odds (88% combined)
- **V2**: Top 4 features include 1 in-game feature (#3: score_diff_div_sqrt_time_remaining_scaled)
- **Improvement**: In-game features gained importance, but opening odds still dominate

### Calibration Parameters

**Platt Scaling Parameters**:
- **Alpha (slope)**: -0.02284868513856536
  - Normal range: 0.5-2.0
  - Status: ⚠️ **EXTREME** (way below normal range)
  - V1 comparison: -0.059 (slightly improved but still extreme)

- **Beta (intercept)**: 1.2091212583929944
  - Normal range: -1.0 to 1.0
  - Status: ⚠️ **EXTREME** (slightly above normal range)
  - V1 comparison: 1.337 (slightly improved but still extreme)

**Assessment**: Calibration parameters improved slightly but remain outside normal ranges, indicating the model is still producing extreme predictions that require extreme calibration adjustments.

### Training Configuration Used

**Regularization Parameters** (from training log):
- `depth`: 4 (reduced from 6)
- `l2_leaf_reg`: 10.0 (increased from default 3.0)
- `subsample`: 0.8 (80% of data per tree)
- `random_strength`: 1.0
- `bagging_temperature`: 1.0
- `iterations`: 1000
- `learning_rate`: 0.1

**Training Performance**:
- Training time: 5.12 minutes (307 seconds)
- Best test AUC: 0.8989 (at iteration 999)
- Model file size: 0.38 MB

---

## Root Cause Analysis

### Why Feature Importance Still Above Target

**Hypothesis 1: Regularization Insufficient**
- **Evidence**: Feature importance reduced from 88% to 69.19% (21% relative reduction), but still 19% above target
- **Assessment**: Regularization helped but may need to be stronger
- **Recommendation**: Increase `l2_leaf_reg` from 10.0 to 15.0-20.0, or reduce `depth` from 4 to 3

**Hypothesis 2: Opening Odds Features Are Legitimately Very Predictive**
- **Evidence**: Opening odds features are pre-game predictions that are inherently predictive of game outcomes
- **Assessment**: Opening odds are legitimately important features, but shouldn't dominate to this extent
- **Recommendation**: Consider feature engineering changes (e.g., log transform, normalization) to reduce their raw predictive power

**Hypothesis 3: In-Game Features Need More Representation**
- **Evidence**: In-game features (`score_diff_div_sqrt_time_remaining_scaled`, `espn_home_prob_scaled`) gained importance but still low compared to opening odds
- **Assessment**: In-game features may need different engineering or weighting
- **Recommendation**: Consider adding more in-game interaction terms or feature transformations

### Why Calibration Parameters Still Extreme

**Hypothesis 1: Model Still Producing Extreme Predictions**
- **Evidence**: Calibration parameters are extreme, suggesting base model probabilities are still extreme
- **Assessment**: Base model probabilities likely still skewed (need to verify with actual probability distribution)
- **Recommendation**: Check average probability on calibration set - if still extreme (e.g., > 80% or < 20%), need stronger regularization

**Hypothesis 2: Calibration Set May Have Bias**
- **Evidence**: Calibration parameters improved slightly but remain extreme
- **Assessment**: Calibration set (2023 season) may have different distribution than training set
- **Recommendation**: Verify calibration set distribution (check if opening odds coverage differs from training set)

---

## Recommendations

### Immediate Actions (Priority: High)

**Option 1: Increase Regularization Further**
- **Action**: Increase `l2_leaf_reg` from 10.0 to 20.0, reduce `depth` from 4 to 3
- **Rationale**: Current regularization helped but didn't reach target - stronger regularization needed
- **Risk**: May reduce model performance (AUC), but should improve feature balance
- **Expected Outcome**: Feature importance < 50%, calibration parameters closer to normal

**Option 2: Feature Engineering Changes**
- **Action**: Apply log transform or normalization to opening odds features to reduce their raw predictive power
- **Rationale**: Opening odds are legitimately predictive but shouldn't dominate - transform to reduce dominance
- **Risk**: May reduce model accuracy if opening odds are truly the best predictors
- **Expected Outcome**: More balanced feature importance, opening odds still important but not dominating

**Option 3: Hybrid Approach (RECOMMENDED)**
- **Action**: Increase regularization (l2_leaf_reg=20.0, depth=3) AND apply feature transformations to opening odds
- **Rationale**: Combines regularization with feature engineering for robust solution
- **Risk**: Medium (may need iteration to find optimal balance)
- **Expected Outcome**: Feature importance < 50%, calibration parameters normal, model still performs well

### Verification Steps

Before retraining with stronger regularization:

1. **Check Average Probability on Calibration Set**:
   ```sql
   -- Get base model probabilities (before calibration) for calibration set
   -- This will show if model is still producing extreme predictions
   SELECT 
       MIN(p_base) as min_prob,
       MAX(p_base) as max_prob,
       AVG(p_base) as avg_prob,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p_base) as median_prob
   FROM (
       -- Need to run model.predict_proba() on calibration set
       -- This requires Python script or precomputed probabilities
   );
   ```

2. **Check Calibration Set Distribution**:
   ```sql
   -- Verify calibration set has similar opening odds coverage as training set
   SELECT 
       CASE WHEN opening_moneyline_home IS NOT NULL THEN 'has_odds' ELSE 'no_odds' END as odds_status,
       COUNT(*) as count,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as pct
   FROM derived.snapshot_features_v1
   WHERE season_label LIKE '2023-%'
   GROUP BY odds_status;
   ```

3. **Compare V1 vs V2 Feature Importance**:
   - V1: 88% from opening odds (top 4 features)
   - V2: 69.19% from opening odds (top 5 features include 1 in-game)
   - **Progress**: 19% reduction, but need 19% more reduction to reach < 50%

---

## Next Steps

### Recommended Approach: Iterative Regularization Increase

1. **Retrain with Stronger Regularization**:
   - Increase `l2_leaf_reg` to 20.0 (from 10.0)
   - Reduce `depth` to 3 (from 4)
   - Keep other parameters the same
   - Expected: Feature importance should drop further (target: < 50%)

2. **If Still Above Target**:
   - Consider feature engineering (log transform opening odds)
   - Or increase regularization further (l2_leaf_reg=30.0, depth=2)

3. **Verify Trading Performance**:
   - Once feature importance < 50%, precompute probabilities
   - Run grid search to verify trading performance improves
   - Target: > $1,000 profit, > 200 trades, > 60% win rate

### Success Criteria (Updated)

Based on v2 results, updated targets:
- **Feature Importance**: < 50% from opening odds (currently 69.19%, need 19% more reduction)
- **Calibration Parameters**: Alpha 0.5-2.0, Beta -1.0 to 1.0 (currently both extreme)
- **Trading Performance**: > $1,000 profit, > 200 trades, > 60% win rate (not yet tested)

---

## Conclusion

The v2 model shows **significant progress** (feature importance reduced from 88% to 69.19%) but **does not meet the < 50% target**. Regularization helped but needs to be stronger. Calibration parameters remain extreme, suggesting the model is still producing extreme predictions.

**Recommendation**: Retrain with stronger regularization (`l2_leaf_reg=20.0`, `depth=3`) and verify results. If still above target, consider feature engineering changes or further regularization increases.
