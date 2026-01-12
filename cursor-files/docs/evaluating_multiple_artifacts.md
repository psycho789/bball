# Evaluating Multiple Model Artifacts

## Your Two Artifacts

### Artifact 1: `winprob_logreg_2017-to-2024.json`
- **Training Data**: season_start <= 2017 (2017-2023, ~7 seasons of data)
- **Calibration Data**: season_start == 2023
- **Test Season**: season_start == 2024
- **Platt Calibration**: alpha=-0.091337, beta=1.033578
- **Use Case**: Model trained on extensive historical data

### Artifact 2: `winprob_logreg_2023-to-2024.json`
- **Training Data**: season_start <= 2023 (2023 only, 1 season)
- **Calibration Data**: season_start == 2023
- **Test Season**: season_start == 2024
- **Platt Calibration**: alpha=-0.051459, beta=1.046934
- **Use Case**: Model trained on recent data only

## Which One to Use?

**Evaluate BOTH separately** to compare their performance! This will tell you:

1. **Does more historical data help or hurt?** (2017-2024 vs 2023-2024)
2. **Which model generalizes better to future data?** (test on 2024 or later)
3. **Which Platt calibration performs better?**

## Evaluation Strategy

### Step 1: Evaluate Both on Test Season (2024)

```bash
# Evaluate 2017-2024 model
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-to-2024.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2017-2024_model_on_2024.json \
  --plot-calibration \
  --verbose

# Evaluate 2023-2024 model
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2023-to-2024.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2023-2024_model_on_2024.json \
  --plot-calibration \
  --verbose
```

### Step 2: Compare Metrics

```bash
python3 << 'PYEOF'
import json

m1 = json.load(open('data/reports/winprob_eval_2017-2024_model_on_2024.json'))
m2 = json.load(open('data/reports/winprob_eval_2023-2024_model_on_2024.json'))

print("=" * 70)
print("MODEL COMPARISON ON SEASON 2024")
print("=" * 70)
print()
print(f"{'Metric':<20} {'2017-2024 Model':<20} {'2023-2024 Model':<20} {'Winner'}")
print("-" * 70)
e1 = m1['eval']['overall']
e2 = m2['eval']['overall']

metrics = [
    ('ECE', 'ece_binned', 'lower'),
    ('Brier Score', 'brier', 'lower'),
    ('Log Loss', 'logloss', 'lower'),
    ('AUC', 'roc_auc', 'higher'),
]

for name, key, better in metrics:
    v1 = e1[key]
    v2 = e2[key]
    if better == 'lower':
        winner = '2017-2024' if v1 < v2 else '2023-2024'
    else:
        winner = '2017-2024' if v1 > v2 else '2023-2024'
    print(f"{name:<20} {v1:<20.6f} {v2:<20.6f} {winner}")

print()
print(f"{'N samples':<20} {e1['n']:<20} {e2['n']:<20}")
PYEOF
```

### Step 3: Evaluate on Future Season (if available)

If you have data for 2025, evaluate both on that to see which generalizes better:

```bash
# Evaluate on 2025 (forward-time evaluation)
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-to-2024.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2017-2024_model_on_2025.json \
  --plot-calibration \
  --verbose

./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2023-to-2024.json \
  --season-start 2025 \
  --out data/reports/winprob_eval_2023-2024_model_on_2025.json \
  --plot-calibration \
  --verbose
```

## Expected Findings

### Model 1 (2017-2024): Historical Data Model
- **Pros**: 
  - More training data → potentially better generalization
  - Sees more diverse game situations
  - May be more stable
- **Cons**:
  - May be influenced by older game styles/rules
  - Could be less adapted to recent trends

### Model 2 (2023-2024): Recent Data Model
- **Pros**:
  - Focused on recent game style/rules
  - More relevant to current season
  - May adapt better to recent trends
- **Cons**:
  - Less training data → potential overfitting risk
  - May not generalize as well

## Recommendations

1. **Evaluate both on 2024** (their intended test season)
2. **Compare metrics** side-by-side
3. **Evaluate on 2025** (forward-time) to see which generalizes better
4. **Use the better-performing model** based on:
   - Lower ECE (better calibration)
   - Lower Brier Score (better accuracy)
   - Higher AUC (better discrimination)
   - Better forward-time performance (generalization)

## Quick Evaluation Command

Run both evaluations in sequence:

```bash
# Evaluate 2017-2024 model
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-to-2024.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2017-2024_model_on_2024.json \
  --plot-calibration

# Evaluate 2023-2024 model  
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2023-to-2024.json \
  --season-start 2024 \
  --out data/reports/winprob_eval_2023-2024_model_on_2024.json \
  --plot-calibration

# Compare results
python3 << 'PYEOF'
import json
m1 = json.load(open('data/reports/winprob_eval_2017-2024_model_on_2024.json'))
m2 = json.load(open('data/reports/winprob_eval_2023-2024_model_on_2024.json'))
e1 = m1['eval']['overall']
e2 = m2['eval']['overall']
print(f"2017-2024 Model: ECE={e1['ece_binned']:.6f}, Brier={e1['brier']:.6f}, AUC={e1['roc_auc']:.6f}")
print(f"2023-2024 Model: ECE={e2['ece_binned']:.6f}, Brier={e2['brier']:.6f}, AUC={e2['roc_auc']:.6f}")
PYEOF
```

## Summary

**For Platt calibration evaluation**: Evaluate **both artifacts separately** to see:
- Which model performs better overall
- Which Platt calibration parameters work better
- Whether historical data helps or hurts performance

Both artifacts have Platt calibration built-in, so the evaluation will show you the calibrated performance of each.

