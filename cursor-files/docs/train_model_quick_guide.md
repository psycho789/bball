# Quick Guide: Training Win-Probability Models

**For Non-Data Scientists** - Simple copy-paste commands

## What You're Doing

You're training two types of models:
1. **With Platt Calibration**: Better probability estimates (recommended)
2. **Without Platt Calibration**: Base model only (for comparison)

## Important Note

**You probably want Platt calibration** - it makes probabilities more accurate. Only skip it if you want to compare or if you have a specific reason.

## Setup (One-Time)

Make sure you have:
- Database running with ESPN data
- `DATABASE_URL` set in `.env` file (or pass `--dsn` flag)

## What "2024" Means

**Important**: When we say "train for 2024", we mean:
- **Train on**: Historical data (2017-2023) 
- **Calibrate on**: 2023 season
- **Predict**: 2024 season (the future!)

You CANNOT train a model using only 2024 data - you need:
1. Training data (old seasons)
2. Calibration data (recent season, different from training)
3. Test data (future season, to evaluate)

## Training Commands - Copy and Paste These

### For Predicting 2024 Season - USE THIS ✅

**Honest answer: Train on ALL historical data (2017-2023).**

**With Platt Calibration** (use this - recommended):
```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --dsn "$DATABASE_URL"
```
**What this does**:  
- Trains on: All seasons <= 2023 (2017, 2018, 2019, 2020, 2021, 2022, 2023)  
- Calibrates on: 2023 only  
- Predicts: 2024

**Without Platt Calibration** (if you want to compare):
```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_no_platt.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --disable-calibration \
  --dsn "$DATABASE_URL"
```
**Same training data, just skips Platt calibration.**

## Evaluating These Models

After training, evaluate both models on the 2024 season:

**Evaluate Model WITH Platt Calibration**:
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_2017-2023_calib_2023_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Evaluate Model WITHOUT Platt Calibration**:
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-2023_no_platt.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_2017-2023_no_platt_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Compare Results**:
```bash
python3 << 'PYEOF'
import json

with_platt = json.load(open('data/models/evaluations/winprob_eval_2017-2023_calib_2023_on_2024.json'))
without_platt = json.load(open('data/models/evaluations/winprob_eval_2017-2023_no_platt_on_2024.json'))

w = with_platt['eval']['overall']
wo = without_platt['eval']['overall']

print("=" * 70)
print("COMPARISON: With Platt vs Without Platt")
print("=" * 70)
print()
print(f"{'Metric':<20} {'With Platt':<20} {'Without Platt':<20} {'Winner'}")
print("-" * 70)
print(f"{'ECE (lower=better)':<20} {w['ece_binned']:<20.6f} {wo['ece_binned']:<20.6f} {'With' if w['ece_binned'] < wo['ece_binned'] else 'Without'}")
print(f"{'Brier (lower=better)':<20} {w['brier']:<20.6f} {wo['brier']:<20.6f} {'With' if w['brier'] < wo['brier'] else 'Without'}")
print(f"{'Log Loss (lower=better)':<20} {w['logloss']:<20.6f} {wo['logloss']:<20.6f} {'With' if w['logloss'] < wo['logloss'] else 'Without'}")
print(f"{'AUC (higher=better)':<20} {w['roc_auc']:<20.6f} {wo['roc_auc']:<20.6f} {'With' if w['roc_auc'] > wo['roc_auc'] else 'Without'}")
print(f"{'N samples':<20} {w['n']:<20} {wo['n']:<20}")
PYEOF
```

### Why Train Only on 2017? (You Probably Shouldn't)

**Short answer: There's no good reason to train only on 2017.** 

The only reasons you might do this:
1. **Data quality issues**: Older data (2017) is bad/incomplete
2. **Distribution shift**: Game style changed so much that 2017-2022 data hurts performance
3. **Matching old artifacts**: You want to recreate your existing `winprob_logreg_2017-to-2024.json` for comparison
4. **Testing**: You want to see what happens with less data

**For non-Platt training on 2024, use ALL seasons:**
```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_no_platt.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --disable-calibration \
  --dsn "$DATABASE_URL"
```

**Why use all seasons?**
- More data = better model (generally)
- More diverse game situations
- Better generalization
- Standard practice

**Why NOT use all seasons?**
- If older data is low quality (probably not the case)
- If game rules changed dramatically (NBA rules are relatively stable)
- If you're testing something specific

**Bottom line**: Use all available historical data (2017-2023). There's no good reason not to unless you have a specific problem with the older data.

## What These Commands Do (Simple Explanation)

- `--train-season-start-max 2023`: Uses data from seasons 2017-2023 for training (learns the model)
- `--calib-season-start 2023`: Uses 2023 season to fit Platt calibration (makes probabilities accurate)
- `--test-season-start 2024`: Sets 2024 as the test season (NOT used in training - just for reference)
- `--disable-calibration`: Skips Platt calibration (only use if you want to compare)
- `--out-artifact`: Where to save the trained model file

## After Training

After training completes, you'll see:
```
Wrote artifacts/winprob_logreg_2017-to-2024.json
```

This file contains your trained model. Use it with the evaluate script to test performance.

## Honest Answer: What Should You Actually Do?

### For 2024 Prediction - Use This Command:

```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --dsn "$DATABASE_URL"
```

**Why?**
- Uses ALL historical data (2017-2023) - more data = better model
- Platt calibration makes probabilities more accurate
- Standard practice in machine learning
- Works well

### For Non-Platt (If You Want to Compare):

```bash
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_no_platt.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --disable-calibration \
  --dsn "$DATABASE_URL"
```

**Same training data, just no Platt calibration.**

### Why Train Only on 2017? (Don't Do This Unless...)

**Honest answer: You probably shouldn't.**

Your existing `winprob_logreg_2017-to-2024.json` artifact trains on 2017 only because someone set `--train-season-start-max 2017`. That's less data, which is usually worse.

**Only train on 2017 if:**
- You want to match your existing artifact for comparison
- You suspect 2018-2023 data has quality issues
- You're testing how data size affects performance
- You have a specific reason

**Otherwise, use all available data (2017-2023).**

### Best Practice Summary

1. **Always use `--train-season-start-max 2023`** (uses all available historical data)
2. **Use Platt calibration** (unless comparing)
3. **Use `--calib-season-start 2023`** (recent season for calibration)
4. **Use `--test-season-start 2024`** (future season to predict)

**Bottom line**: More data = better model. Use all available seasons unless you have a specific reason not to.

## Common Mistakes

1. **Forgetting `--dsn` flag**: Use `--dsn "$DATABASE_URL"` or set it in `.env`
2. **Using same season for train/calib/test**: They must be different seasons
3. **Training on test data**: Test season should NOT be in training data

## Example: Full Workflow

```bash
# 1. Train model (takes a few minutes)
./.venv/bin/python scripts/model/train_winprob_logreg.py \
  --out-artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --train-season-start-max 2023 \
  --calib-season-start 2023 \
  --test-season-start 2024 \
  --dsn "$DATABASE_URL"

# 2. Test the model (takes a few minutes)
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"

# 3. Check results
cat data/reports/winprob_eval_2024.json | grep -A 5 '"overall"'
```

## Quick Reference Table

| Command | Trains On | Calibrates On | Has Platt? | When to Use |
|---------|-----------|---------------|------------|-------------|
| `--train-season-start-max 2023` | ALL seasons <= 2023 (2017-2023) | 2023 | Yes (if no `--disable-calibration`) | **Best option** - most data |
| `--train-season-start-max 2017` | Season 2017 only | 2023 | Yes (if no `--disable-calibration`) | Matches your existing artifact |
| Add `--disable-calibration` | Same as above | 2023 | No | Only if comparing |

## Understanding `--train-season-start-max` (Important!)

**This is the confusing part:**

- `--train-season-start-max 2023` = "Use all seasons where season_start <= 2023"
  - If database has: 2017, 2018, 2019, 2020, 2021, 2022, 2023 → uses ALL of them
  - If database only has: 2023 → uses just 2023
  - The script uses whatever is available up to that year

- `--train-season-start-max 2017` = "Use all seasons where season_start <= 2017"
  - Uses: 2017 only (or earlier if available)
  - Does NOT use: 2018, 2019, 2020, 2021, 2022, 2023

**You can't tell it "use exactly 2023 only"** - it always uses "everything up to that year".

## Need Help?

**If training fails**, the script will tell you what's wrong. Common issues:

1. **Database not connected**: Make sure `DATABASE_URL` is set in `.env` or use `--dsn` flag
2. **Not enough data**: Script needs at least 1,000 training rows
3. **Wrong seasons**: Make sure you have data for:
   - Training: seasons <= 2023 (2017-2023)
   - Calibration: season == 2023
   - Test: season == 2024 (just for reference, not used in training)

**The script will print helpful error messages** - read them and adjust the season numbers if needed.

