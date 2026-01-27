# Sprint Model Evaluation Commands

## Evidence: How Older Models Were Evaluated

### 1. Evaluation File Pattern

**Evidence from existing evaluation files:**
```bash
$ ls -la data/models/evaluations/*.json
-rw-r--r--  winprob_eval_catboost_isotonic_2017-2023_calib_2023_on_2024.json
-rw-r--r--  winprob_eval_catboost_platt_2017-2023_calib_2023_on_2024.json
-rw-r--r--  winprob_eval_logreg_isotonic_2017-2023_calib_2023_on_2024.json
-rw-r--r--  winprob_eval_logreg_platt_2017-2023_calib_2023_on_2024.json
```

**Pattern:** `winprob_eval_{model_type}_{train_range}_calib_{calib_season}_on_{test_season}.json`

### 2. Command Pattern from Documentation

**Evidence from `cursor-files/docs/train_model_quick_guide.md` (lines 69-77):**
```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_2017-2023_calib_2023_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Evidence from `cursor-files/sprints/2026-01-12-2x2-model-matrix-implementation/sprint-18-2x2-model-matrix.md` (lines 626-636):**
```bash
for artifact in artifacts/winprob_*_2017-2023_*.json; do
  name=$(basename $artifact .json)
  ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
    --artifact "$artifact" \
    --season-start 2024 \
    --out "data/models/evaluations/${name}_on_2024.json" \
    --plot-calibration \
    --dsn "$DATABASE_URL"
done
```

### 3. Evaluation Script Arguments

**Evidence from `scripts/model/evaluate_winprob_model.py` (lines 59-73):**
```python
p.add_argument("--artifact", required=True, help="Artifact JSON path.")
p.add_argument("--dsn", help="Database connection string (or use DATABASE_URL env var)")
p.add_argument("--season-start", type=int, required=True, help="Season_start to evaluate (e.g. 2024).")
p.add_argument("--out", required=True, help="Output JSON report path.")
p.add_argument("--bins", type=int, default=20, help="Bins for ECE/reliability (default: 20).")
p.add_argument("--plot-calibration", action="store_true", help="Write an SVG reliability diagram next to the JSON report.")
p.add_argument("--verbose", action="store_true", help="Enable verbose logging with detailed progress information.")
p.add_argument("--disable-calibration", action="store_true", help="Evaluate model without Platt calibration (for comparison).")
```

### 4. Sprint Model Artifacts Metadata

**Evidence from artifact inspection:**
```python
# Baseline model
Artifact: winprob_catboost_baseline_sprint1.json
  Model type: catboost
  Train season max: 2022
  Calib season: 2023
  Test season: 2024
  Has opening odds features: False
  Total features: 13

# Odds-enabled model
Artifact: winprob_catboost_odds_sprint1.json
  Model type: catboost
  Train season max: 2022
  Calib season: 2023
  Test season: 2024
  Has opening odds features: True
  Total features: 20
```

## ⚠️ CRITICAL ISSUE: Evaluation Script Doesn't Support Opening Odds

**Evidence from `scripts/model/evaluate_winprob_model.py`:**

1. **`_load_evaluation_data()` function (lines 382-485)** does NOT join `external.sportsbook_odds_snapshots`
2. **`build_design_matrix()` call (lines 556-581)** does NOT pass opening odds features
3. **No opening odds support:** The script only loads ESPN data and interaction terms

**This means:**
- ✅ **Baseline model** (`catboost_baseline_sprint1`) can be evaluated as-is
- ❌ **Odds-enabled model** (`catboost_odds_sprint1`) **CANNOT** be evaluated with current script

## Required Fix: Update Evaluation Script

The `evaluate_winprob_model.py` script needs to be updated to:
1. Join `external.sportsbook_odds_snapshots` in `_load_evaluation_data()` (similar to `train_winprob_catboost.py`)
2. Call `compute_opening_odds_features()` after loading data
3. Pass opening odds features to `build_design_matrix()` if present in artifact

**Evidence from `scripts/model/train_winprob_catboost.py` (lines 156-167, 254-265):**
```python
opening_odds AS (
    -- Pivot opening odds by market_type and side
    SELECT 
        espn_game_id,
        MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'home') AS opening_moneyline_home,
        MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'away') AS opening_moneyline_away,
        MAX(line_value) FILTER (WHERE market_type = 'spread' AND side = 'home') AS opening_spread,
        MAX(line_value) FILTER (WHERE market_type = 'total' AND side = 'over') AS opening_total
    FROM external.sportsbook_odds_snapshots
    WHERE is_opening_line = TRUE
        AND espn_game_id IS NOT NULL
    GROUP BY espn_game_id
)
```

## Commands (After Fixing Evaluation Script)

### Command 1: Evaluate Baseline Model

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_baseline_sprint1.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_baseline_sprint1_calib_2023_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Expected output:**
- `data/models/evaluations/winprob_eval_catboost_baseline_sprint1_calib_2023_on_2024.json`
- `data/models/evaluations/winprob_eval_catboost_baseline_sprint1_calib_2023_on_2024_calibration.svg`
- `data/models/evaluations/winprob_eval_catboost_baseline_sprint1_calib_2023_on_2024_calibration_context.svg`

### Command 2: Evaluate Odds-Enabled Model (Requires Script Fix)

```bash
./.venv/bin/python scripts/model/evaluate_winprob_model.py \
  --artifact artifacts/winprob_catboost_odds_sprint1.json \
  --season-start 2024 \
  --out data/models/evaluations/winprob_eval_catboost_odds_sprint1_calib_2023_on_2024.json \
  --plot-calibration \
  --dsn "$DATABASE_URL"
```

**Expected output:**
- `data/models/evaluations/winprob_eval_catboost_odds_sprint1_calib_2023_on_2024.json`
- `data/models/evaluations/winprob_eval_catboost_odds_sprint1_calib_2023_on_2024_calibration.svg`
- `data/models/evaluations/winprob_eval_catboost_odds_sprint1_calib_2023_on_2024_calibration_context.svg`

### Verification Commands

```bash
# Verify evaluation files exist
ls -la data/models/evaluations/winprob_eval_catboost_*_sprint1*.json

# Verify JSON structure
python3 << 'EOF'
import json
from pathlib import Path

for eval_file in Path("data/models/evaluations").glob("winprob_eval_catboost_*_sprint1*.json"):
    with open(eval_file) as f:
        data = json.load(f)
    assert 'eval' in data
    assert 'overall' in data['eval']
    assert 'calibration_bins' in data['eval']
    print(f"✓ {eval_file.name} is valid")
EOF
```

## Summary

1. **Baseline model** can be evaluated immediately with the current script
2. **Odds-enabled model** requires updating `evaluate_winprob_model.py` to support opening odds
3. **Evaluation format** matches older models: `winprob_eval_{model_name}_calib_{calib}_on_{test}.json`
4. **Test season** is `2024` (2024-25 season) as specified in artifact metadata
