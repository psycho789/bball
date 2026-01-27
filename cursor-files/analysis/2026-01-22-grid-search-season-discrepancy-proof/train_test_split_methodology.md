# Train/Test Split Methodology for Grid Search

**Date**: 2026-01-22  
**Question**: Should grid searches use the same season as model training, or does it matter?

---

## Executive Summary

**Answer**: Grid searches should use the **test season** that matches the model's training configuration, OR use the **same season for all models** for fair comparison.

**Key Principle**: For time-series data, you must use **future data** (never past data) for evaluation. The test season should be **equal to or later than** the test season used during training.

---

## Model Training Configuration

### Sprint Models (catboost_baseline_sprint1, catboost_odds_sprint1)

**Training Command** (from `phase4-commands.md`):
```bash
--train-season-start-max 2022  # Train on seasons 2017-2022
--test-season-start 2024       # Test on season 2024 (2024-25)
--calib-season-start 2023      # Calibrate on season 2023
```

**Training Split**:
- **Train**: Seasons 2017-2022 (historical data)
- **Calibration**: Season 2023 (for Platt/Isotonic scaling)
- **Test**: Season 2024 (2024-25 season) - **NOT used in training**

**Grid Search Used**: Season **2024-25** ✅ (matches test season from training)

---

### Older Models (catboost_platt, catboost_isotonic, logreg_platt, logreg_isotonic)

**Training Configuration** (inferred from filenames `*_2017-2023.json`):
- **Train**: Seasons 2017-2023 (historical data)
- **Test**: Season 2024 (2024-25 season) - **NOT used in training**

**Grid Search Used**: Season **2025-26** ⚠️ (different from test season)

---

## The Methodology Question

### Option A: Use Test Season from Training (2024-25)

**Pros**:
- ✅ Matches the model's intended evaluation setup
- ✅ Reproduces the training/test split exactly
- ✅ Scientifically correct - evaluates on the same data the model was designed for

**Cons**:
- ❌ Can't compare directly with older models that were evaluated on 2025-26
- ❌ Less "real-world" if you want to see performance on the most recent season

**When to Use**: When you want to evaluate the model exactly as it was trained.

---

### Option B: Use Same Season for All Models (2025-26)

**Pros**:
- ✅ Fair comparison across all models
- ✅ Tests on most recent complete season
- ✅ More "real-world" - simulates using models on new data

**Cons**:
- ⚠️ Different from the test season used during training
- ⚠️ May not match the model's calibration setup

**When to Use**: When you want to compare models head-to-head on the same dataset.

---

### Option C: Use Future Season (2025-26 for models trained with test=2024)

**Pros**:
- ✅ Tests generalization to truly unseen data
- ✅ Most realistic for production deployment

**Cons**:
- ⚠️ May show worse performance due to distribution shift
- ⚠️ Not directly comparable to training metrics

**When to Use**: When you want to test how well models generalize to future seasons.

---

## Recommendation

**For Fair Comparison**: Use **2025-26** for all models (Option B)

**Reasoning**:
1. The older models were already evaluated on 2025-26
2. For fair comparison, all models should use the same season
3. 2025-26 is a future season relative to training (2024), so it's valid for evaluation
4. This tests generalization to new data, which is realistic for production

**For Scientific Accuracy**: Use **2024-25** for sprint models (Option A)

**Reasoning**:
1. Matches the exact test season from training configuration
2. Reproduces the intended evaluation setup
3. Scientifically correct methodology

**Best Practice**: Do both, but label clearly:
- "Evaluation on test season (2024-25)" - matches training
- "Evaluation on future season (2025-26)" - tests generalization

---

## What NOT to Do

❌ **Never use past seasons** (e.g., 2023-24 for models trained with test=2024)
- This would be data leakage (evaluating on training data)

❌ **Never use training seasons** (e.g., 2022-23 for models trained on 2017-2022)
- This would be evaluating on seen data, not a true test

---

## Current Situation

| Model | Training Test Season | Grid Search Season | Status |
|-------|---------------------|-------------------|--------|
| Sprint models | 2024-25 | 2024-25 | ✅ Matches training |
| Older models | 2024-25 (inferred) | 2025-26 | ⚠️ Different season |

**Issue**: Models are being compared on different seasons, making comparison unfair.

**Solution**: Re-run sprint model grid searches on **2025-26** to match older models for fair comparison.

---

## Commands to Fix

```bash
# Re-run sprint models on 2025-26 for fair comparison
python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_baseline_sprint1

python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_sprint1
```

This will give you:
- ✅ Fair comparison (all models on same season)
- ✅ Tests generalization (future season)
- ✅ Matches older model evaluation setup

---

## Summary

**Does it matter?** Yes, it matters for:
1. **Fair comparison**: All models should use the same evaluation season
2. **Scientific accuracy**: Should match the test season from training
3. **Generalization testing**: Future seasons test real-world performance

**Best approach**: Use **2025-26** for all models to enable fair comparison, even though sprint models were trained with test=2024-25. This is valid because 2025-26 is a future season (not past), so it's a legitimate generalization test.
