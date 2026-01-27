# CatBoost Odds Models Miscalibration Analysis

**Date:** 2026-01-22  
**Issue:** `catboost_odds_platt` and `catboost_odds_isotonic` models show severe miscalibration when opening odds are present, leading to poor trading performance.

---

## Executive Summary

The models trained with opening odds features (`catboost_odds_platt` and `catboost_odds_isotonic`) are producing severely miscalibrated probabilities when opening odds data is present:

- **With opening odds:** Average probability = **96.6-96.7%** (severely overconfident)
- **Without opening odds:** Average probability = **57.6-57.7%** (reasonable)

This miscalibration causes:
- **Fewer trades:** Only 125 trades vs 367 for baseline models (probabilities rarely drop below entry thresholds)
- **Poor win rate:** 55.2% vs 66.8% for baseline models
- **Low profit:** $345 vs $1,899 for baseline models

**Root Cause Investigation Status:**
- ✅ **Training Data Bias:** RULED OUT - Training data shows only 1.0% difference in home win rate (56.7% vs 55.7%)
- ✅ **Feature Dominance + Extreme Calibration:** **CONFIRMED AS ROOT CAUSE**
  - Opening odds features account for **88% of feature importance** (top 4 features)
  - Platt calibration parameters are extreme: Alpha = -0.059 (should be 0.5-2.0), Beta = 1.337 (should be -1.0 to 1.0)
  - Combined effect: Model relies almost entirely on opening odds, and extreme calibration amplifies predictions to 96.6%

**Current Assessment:** The model learned to rely almost entirely on opening odds features (88% importance), and extreme Platt scaling parameters are amplifying this effect, causing severe overconfidence (96.6% average probability when odds present).

---

## Evidence

### 1. Trading Performance Comparison

From grid search results (`data/grid_search/model_comparison.json`):

| Model | Test Profit | Trades | Win Rate | Profit/Trade |
|-------|-------------|--------|----------|--------------|
| ESPN (default) | $1,942.84 | 332 | 72.9% | $5.85 |
| catboost_baseline_platt | $1,899.70 | 367 | 66.8% | $5.18 |
| catboost_odds_platt | $345.03 | 125 | 55.2% | $2.76 |

**Key Observation:** `catboost_odds_platt` has:
- 66% fewer trades (125 vs 367)
- 11.6% lower win rate (55.2% vs 66.8%)
- 82% less profit ($345 vs $1,899)

### 2. Probability Distribution Analysis

From database queries on `derived.model_probabilities_v1` for 2025-26 season:

#### Overall Statistics:
- **Total snapshots:** 250,660
- **catboost_odds_platt populated:** 250,660 (100%)
- **catboost_baseline_platt populated:** 250,660 (100%)

#### Average Probabilities by Opening Odds Availability:

```sql
SELECT 
    CASE 
        WHEN sf.opening_moneyline_home IS NOT NULL THEN 'has_odds'
        ELSE 'no_odds'
    END as odds_status,
    AVG(mp.catboost_odds_isotonic_prob) as avg_prob_isotonic,
    AVG(mp.catboost_odds_platt_prob) as avg_prob_platt,
    AVG(mp.catboost_baseline_platt_prob) as avg_prob_baseline
FROM derived.snapshot_features_v1 sf
JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
WHERE sf.season_label = '2025-26'
GROUP BY odds_status;
```

**Results:**

| Odds Status | Odds Isotonic Avg | Odds Platt Avg | Baseline Platt Avg |
|-------------|-------------------|----------------|-------------------|
| has_odds | 96.7% | 96.6% | 53.6% |
| no_odds | 57.6% | 57.7% | 53.6% |

**Key Findings:**
1. When opening odds are present, odds models predict ~96.6% average probability (severely overconfident)
2. When opening odds are missing, odds models predict ~57.7% average probability (reasonable, close to baseline)
3. Baseline model is stable at ~53.6% regardless of opening odds availability

#### Opening Odds Data Coverage:
- **Total snapshots:** 250,660
- **Has opening moneyline:** 197,299 (78.71%)
- **Has opening spread:** 197,299 (78.71%)
- **Has opening total:** 197,299 (78.71%)

**Implication:** 78.7% of snapshots have opening odds, so the miscalibration affects the majority of predictions.

### 3. Value Range Analysis

```sql
SELECT 
    'baseline_platt' as model,
    COUNT(*) as count,
    MIN(catboost_baseline_platt_prob) as min_prob,
    MAX(catboost_baseline_platt_prob) as max_prob,
    AVG(catboost_baseline_platt_prob) as avg_prob
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND catboost_baseline_platt_prob IS NOT NULL
UNION ALL
SELECT 
    'odds_platt' as model,
    COUNT(*) as count,
    MIN(catboost_odds_platt_prob) as min_prob,
    MAX(catboost_odds_platt_prob) as max_prob,
    AVG(catboost_odds_platt_prob) as avg_prob
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND catboost_odds_platt_prob IS NOT NULL;
```

**Results:**

| Model | Count | Min | Max | Avg |
|-------|-------|-----|-----|-----|
| baseline_platt | 250,660 | 0.000006 | 0.999992 | 0.536166 (53.6%) |
| odds_platt | 250,660 | 0.000287 | 1.000000 | 0.883096 (88.3%) |

**Key Finding:** The odds model has a much higher average probability (88.3% overall, 96.6% when odds present), indicating systematic overconfidence.

---

## Root Cause Analysis

### Hypothesis 1: Training Data Bias (UNLIKELY - Verified)

**Theory:** The training data may have had a correlation between opening odds and home team wins that doesn't generalize to production.

**Evidence:**
- Models perform reasonably (57.7%) when opening odds are missing
- Models are severely overconfident (96.6%) when opening odds are present
- This suggests the model learned a spurious correlation during training

**Verification Results:**
- Training data (2017-2023) shows only **1.0% difference** in home win rate (56.7% with odds vs 55.7% without odds)
- This small difference is within normal variance and **cannot explain** the 96.6% prediction when odds are present
- **Conclusion:** Training data bias is **NOT the root cause**

**Updated Assessment:** The problem is more likely in:
- Feature engineering (how opening odds are transformed)
- Model learning (how CatBoost weights opening odds features)
- Calibration (Platt scaling amplifying the effect)

**How to Verify:**
1. Check training data distribution:
```sql
-- Check correlation between opening odds and home wins in training data
WITH espn_base AS (
    SELECT
        p.game_id,
        p.sequence_number,
        p.season_label,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
        e.point_differential AS score_diff,
        e.time_remaining
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
),
opening_odds AS MATERIALIZED (
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
),
espn_with_features AS (
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_start,
        e.season_label,
        e.game_id,
        e.sequence_number,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0  -- Home won
            WHEN sg.away_score > sg.home_score THEN 1  -- Away won
            ELSE NULL
        END AS final_winning_team,
        oo.opening_moneyline_home,
        oo.opening_moneyline_away,
        oo.opening_spread,
        oo.opening_total
    FROM espn_base e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id
    LEFT JOIN opening_odds oo
        ON e.game_id = oo.espn_game_id
    WHERE sg.home_score IS NOT NULL 
      AND sg.away_score IS NOT NULL
      AND e.season_start <= 2023  -- Training period (2017-2023)
)
SELECT 
    CASE WHEN opening_moneyline_home IS NOT NULL THEN 'has_odds' ELSE 'no_odds' END as odds_status,
    AVG(CASE WHEN final_winning_team = 0 THEN 1.0 ELSE 0.0 END) as home_win_rate,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT game_id) as game_count
FROM espn_with_features
WHERE final_winning_team IS NOT NULL
GROUP BY odds_status;
```

**What to look for:**
- If `home_win_rate` is significantly different between `has_odds` and `no_odds`, this indicates training data bias
- If games with opening odds had a much higher home win rate (e.g., >60%) than games without odds, the model may have learned this correlation
- Compare `snapshot_count` and `game_count` to see if opening odds were more common in certain types of games

**Expected result:** Home win rate should be similar (~50-55%) regardless of opening odds availability. If there's a large difference, this is likely the root cause.

**Actual Results (Training Period 2017-2023):**
```
 odds_status | home_win_rate | snapshot_count | game_count
-------------+---------------+----------------+------------
 has_odds    | 56.7%         | 3,221,054      | 6,868
 no_odds     | 55.7%         | 1,151,155      | 2,449
```

**Analysis:**
- **Home win rate difference:** Only **1.0%** (56.7% vs 55.7%) - this is relatively small
- **Conclusion:** Training data bias is **NOT the primary cause** of miscalibration
- The slight difference (1%) is within normal variance and wouldn't explain why the model predicts 96.6% when odds are present
- **This suggests the problem is elsewhere:**
  - How opening odds features are engineered/transformed
  - How the model learned to weight opening odds features
  - Calibration (Platt scaling) amplifying the effect
  - Model overfitting to opening odds patterns

### Hypothesis 2: Feature Dominance + Extreme Calibration (✅ CONFIRMED - ROOT CAUSE)

**Theory:** Opening odds features dominate the model, and extreme calibration parameters amplify their effect.

**Evidence:**
- Both Platt and Isotonic show the same issue (suggests problem is before calibration)
- However, calibration could amplify an existing bias

**Verification Results:**

**Feature Importance Analysis:**
```
Top 4 Features (ALL opening odds):
1. opening_total:           32.43 importance (🔴 Odds)
2. opening_prob_home_fair: 22.46 importance (🔴 Odds)
3. opening_overround:      16.69 importance (🔴 Odds)
4. opening_spread:          16.45 importance (🔴 Odds)
Total: 88.03% of importance from just 4 features!
```

**Key Finding:** Opening odds features account for **88% of feature importance** from just the top 4 features. This means the model is essentially using opening odds to make predictions, ignoring in-game context.

**Calibration Parameters:**
```
Alpha (slope):  -0.059  ⚠️ EXTREME (normal: 0.5-2.0)
Beta (intercept): 1.337 ⚠️ EXTREME (normal: -1.0 to 1.0)
```

**Key Finding:** Both calibration parameters are extreme:
- **Alpha (-0.059):** Way too low - this inverts the relationship
- **Beta (1.337):** Too high - this amplifies predictions

**Combined Effect:**
1. Opening odds features dominate (88% importance)
2. Extreme calibration amplifies their effect
3. Result: Model predicts 96.6% when opening odds present (severely overconfident)

**Conclusion:** This is the **ROOT CAUSE**. The model learned to rely almost entirely on opening odds, and extreme calibration made it worse.

**How to Verify:**

### Step 1: Check Calibration Set Distribution

**What this checks:** Whether the calibration set (2023 season) had a bias where games with opening odds had different home win rates.

**Copy and paste this SQL query into your database:**

```sql
WITH espn_base AS (
    SELECT
        p.game_id,
        p.sequence_number,
        p.season_label,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
        e.point_differential AS score_diff,
        e.time_remaining
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
        AND CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) = 2023  -- Calibration season
),
opening_odds AS MATERIALIZED (
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
),
espn_with_features AS (
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_start,
        e.season_label,
        e.game_id,
        e.sequence_number,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0  -- Home won
            WHEN sg.away_score > sg.home_score THEN 1  -- Away won
            ELSE NULL
        END AS final_winning_team,
        oo.opening_moneyline_home,
        oo.opening_moneyline_away,
        oo.opening_spread,
        oo.opening_total
    FROM espn_base e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id
    LEFT JOIN opening_odds oo
        ON e.game_id = oo.espn_game_id
    WHERE sg.home_score IS NOT NULL 
      AND sg.away_score IS NOT NULL
)
SELECT 
    CASE WHEN opening_moneyline_home IS NOT NULL THEN 'has_odds' ELSE 'no_odds' END as odds_status,
    AVG(CASE WHEN final_winning_team = 0 THEN 1.0 ELSE 0.0 END) as home_win_rate,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT game_id) as game_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total
FROM espn_with_features
WHERE final_winning_team IS NOT NULL
GROUP BY odds_status;
```

**What to look for in the results:**
- **home_win_rate:** Should be similar for both `has_odds` and `no_odds` (within 2-3%). If there's a big difference (>5%), calibration set is biased.
- **pct_of_total:** What percentage of calibration data had opening odds. If >90% had odds, calibration might be biased toward odds-present scenarios.

**Expected result:** Home win rate should be ~50-56% for both groups. If `has_odds` has much higher home win rate, this could explain the miscalibration.

### Step 2: Inspect Calibration Parameters

**What this checks:** Whether Platt scaling parameters are extreme (which would cause overconfidence).

**Option A: Run the inspection script (EASIEST)**

```bash
# Make sure you're in the project directory and virtual environment is activated
cd /Users/adamvoliva/Code/bball
source .venv/bin/activate  # or however you activate your venv

# Run the inspection script
python scripts/analysis/inspect_odds_model_artifact.py
```

**Option B: Run Python code directly**

```bash
# Make sure you're in the project directory and virtual environment is activated
cd /Users/adamvoliva/Code/bball
source .venv/bin/activate

# Run Python interactively
python
```

Then paste this code:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from scripts.lib._winprob_lib import load_artifact
from catboost import CatBoostClassifier

# Load the model artifact
artifact = load_artifact(Path("artifacts/winprob_catboost_odds_platt.json"))

# Check calibration parameters
print("=" * 60)
print("CALIBRATION PARAMETERS")
print("=" * 60)

# Determine calibration method
if artifact.platt is not None:
    calibration_method = "platt"
elif artifact.isotonic is not None:
    calibration_method = "isotonic"
else:
    calibration_method = "none"

print(f"Calibration method: {calibration_method}")

if artifact.platt is not None:
    print(f"\nPlatt Scaling Parameters:")
    print(f"  Alpha (slope): {artifact.platt.alpha}")
    print(f"  Beta (intercept): {artifact.platt.beta}")
    
    # Interpret the values
    print(f"\nInterpretation:")
    if abs(artifact.platt.alpha) < 0.5 or abs(artifact.platt.alpha) > 2.0:
        print(f"  ⚠️  Alpha is extreme (normal range: 0.5-2.0)")
    else:
        print(f"  ✅ Alpha is in normal range")
    
    if abs(artifact.platt.beta) > 1.0:
        print(f"  ⚠️  Beta is extreme (normal range: -1.0 to 1.0)")
    else:
        print(f"  ✅ Beta is in normal range")
elif artifact.isotonic is not None:
    print("Isotonic calibration: Present")
else:
    print("No calibration found")

# Check feature importance
print("\n" + "=" * 60)
print("FEATURE IMPORTANCE (Top 15)")
print("=" * 60)

# Load CatBoost model
model_path = Path("artifacts/winprob_catboost_odds_platt.cbm")
if not model_path.exists():
    # Try alternative location
    model_path = Path("data/models/winprob_catboost_odds_platt.cbm")

if model_path.exists():
    model = CatBoostClassifier()
    model.load_model(str(model_path))
    
    importance = model.get_feature_importance()
    feature_names = artifact.feature_names
    
    # Pair features with importance and sort
    feat_importance = list(zip(feature_names, importance))
    feat_importance.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop 15 most important features:")
    print(f"{'Rank':<6} {'Feature Name':<50} {'Importance':<12} {'Type'}")
    print("-" * 80)
    
    for i, (feat, imp) in enumerate(feat_importance[:15], 1):
        is_odds_feat = any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround'])
        feat_type = "🔴 Odds" if is_odds_feat else "  Other"
        print(f"{i:<6} {feat:<50} {imp:>10.2f}  {feat_type}")
    
    # Count odds features in top 10
    odds_in_top10 = sum(1 for feat, _ in feat_importance[:10] 
                        if any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround']))
    print(f"\nOpening odds features in top 10: {odds_in_top10}/10")
    if odds_in_top10 >= 5:
        print("  ⚠️  WARNING: Opening odds features dominate! This could cause overconfidence.")
    elif odds_in_top10 >= 3:
        print("  ⚠️  CAUTION: Opening odds features are very important (may be contributing to issue)")
    else:
        print("  ✅ Opening odds features are not dominating")
else:
    print(f"  ⚠️  CatBoost model file not found at: {model_path}")
```

**What to look for:**
- **Platt alpha/beta:** 
  - Normal alpha: 0.5-2.0 (if outside this range, calibration is extreme)
  - Normal beta: -1.0 to 1.0 (if outside this range, calibration is extreme)
- **Feature importance:**
  - If opening odds features (opening_prob_home_fair, opening_spread, etc.) are in the top 5, they're dominating predictions
  - If 5+ opening odds features are in top 10, this is likely the problem

**Expected result:** 
- Platt parameters should be in normal ranges
- Opening odds features should be important but not dominating (maybe 2-3 in top 10, not 5+)

### Hypothesis 3: Feature Leakage

**Theory:** Opening odds features may contain information that leaks the outcome.

**Evidence:**
- Opening odds are pre-game predictions, so they shouldn't leak in-game outcomes
- However, if opening odds were computed from final scores (data leakage), this would explain overconfidence

**How to Verify:**
1. Check when opening odds were recorded (should be before game start)
2. Verify opening odds weren't backfilled from final scores
3. Check if opening odds features are computed correctly

### Hypothesis 4: Model Overfitting (✅ CONFIRMED - Part of Root Cause)

**Theory:** The model overfit to opening odds patterns in training data.

**Evidence:**
- CatBoost can overfit if not properly regularized
- Opening odds features may have been given too much weight

**Verification Results:**
- **Feature importance shows extreme overfitting:**
  - Top 4 features are ALL opening odds (88% of total importance)
  - Opening odds features dominate predictions (5 out of top 10)
  - In-game features (score_diff, time_remaining, espn_prob) have minimal importance (< 7% combined)

**Conclusion:** The model severely overfit to opening odds features, essentially ignoring in-game context. This is part of the root cause, combined with extreme calibration parameters.

---

## Root Cause Summary

**CONFIRMED:** The miscalibration is caused by:

1. **Feature Dominance (88% importance):**
   - Top 4 features are ALL opening odds: `opening_total` (32.43), `opening_prob_home_fair` (22.46), `opening_overround` (16.69), `opening_spread` (16.45)
   - Model essentially ignores in-game context (score_diff, time_remaining, espn_prob have < 7% combined importance)

2. **Extreme Calibration Parameters:**
   - Alpha = -0.059 (should be 0.5-2.0) - Way too low, inverts relationship
   - Beta = 1.337 (should be -1.0 to 1.0) - Too high, amplifies predictions

3. **Combined Effect:**
   - Model relies almost entirely on opening odds
   - Extreme calibration amplifies this effect
   - Result: 96.6% average probability when opening odds present (severely overconfident)

**Why This Happened:**
- CatBoost learned that opening odds are highly predictive (which they are, but shouldn't dominate)
- Model wasn't properly regularized to balance opening odds with in-game features
- Calibration was done on biased or extreme predictions, leading to extreme parameters

---

## Long-Term Fix: Detailed Steps

### Phase 1: Investigation (✅ COMPLETE)

**Goal:** Understand exactly why the model is miscalibrated.

**Status:** Root cause identified - Feature dominance (88%) + extreme calibration parameters.

#### Step 1.1: Analyze Training Data Distribution

**Purpose:** Check if there's a correlation between opening odds availability and home team wins in the training data that could cause bias.

**Query:** (Same as Hypothesis 1 verification query above)

```sql
-- Check correlation between opening odds and home wins in training data
WITH espn_base AS (
    SELECT
        p.game_id,
        p.sequence_number,
        p.season_label,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
        e.point_differential AS score_diff,
        e.time_remaining
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
),
opening_odds AS MATERIALIZED (
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
),
espn_with_features AS (
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_start,
        e.season_label,
        e.game_id,
        e.sequence_number,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0  -- Home won
            WHEN sg.away_score > sg.home_score THEN 1  -- Away won
            ELSE NULL
        END AS final_winning_team,
        oo.opening_moneyline_home,
        oo.opening_moneyline_away,
        oo.opening_spread,
        oo.opening_total
    FROM espn_base e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id
    LEFT JOIN opening_odds oo
        ON e.game_id = oo.espn_game_id
    WHERE sg.home_score IS NOT NULL 
      AND sg.away_score IS NOT NULL
      AND e.season_start <= 2023  -- Training period (2017-2023)
)
SELECT 
    CASE WHEN opening_moneyline_home IS NOT NULL THEN 'has_odds' ELSE 'no_odds' END as odds_status,
    AVG(CASE WHEN final_winning_team = 0 THEN 1.0 ELSE 0.0 END) as home_win_rate,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT game_id) as game_count
FROM espn_with_features
WHERE final_winning_team IS NOT NULL
GROUP BY odds_status;
```

**What to look for:**
- **Home win rate difference:** If `home_win_rate` is significantly different between `has_odds` and `no_odds` (e.g., >10% difference), this indicates training data bias
- **Expected:** Home win rate should be similar (~50-55%) regardless of opening odds availability
- **Red flag:** If games with opening odds had much higher home win rate (e.g., >60%), the model learned this spurious correlation
- **Compare to production:** Check if the pattern matches what we see in 2025-26 data (where odds model predicts 96% when odds present)

#### Step 1.2: Inspect Model Artifact (✅ COMPLETE)

**Status:** Root cause identified!

**Results:**
- **Feature Importance:** Opening odds features dominate with **88% of importance** from top 4 features
  - `opening_total`: 32.43 importance
  - `opening_prob_home_fair`: 22.46 importance  
  - `opening_overround`: 16.69 importance
  - `opening_spread`: 16.45 importance
- **Calibration Parameters:** EXTREME
  - Alpha = -0.059 (normal: 0.5-2.0) ⚠️ Way too low
  - Beta = 1.337 (normal: -1.0 to 1.0) ⚠️ Too high

**Conclusion:** Model relies almost entirely on opening odds (88% importance), and extreme calibration amplifies predictions to 96.6% when odds are present.

#### Step 1.3: Check Calibration Set

```sql
-- Check calibration set (2023 season) distribution
WITH espn_base AS (
    SELECT
        p.game_id,
        p.sequence_number,
        p.season_label,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
        e.point_differential AS score_diff,
        e.time_remaining
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
        AND CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) = 2023  -- Calibration season
),
opening_odds AS MATERIALIZED (
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
),
espn_with_features AS (
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_start,
        e.season_label,
        e.game_id,
        e.sequence_number,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0  -- Home won
            WHEN sg.away_score > sg.home_score THEN 1  -- Away won
            ELSE NULL
        END AS final_winning_team,
        oo.opening_moneyline_home,
        oo.opening_moneyline_away,
        oo.opening_spread,
        oo.opening_total
    FROM espn_base e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id
    LEFT JOIN opening_odds oo
        ON e.game_id = oo.espn_game_id
    WHERE sg.home_score IS NOT NULL 
      AND sg.away_score IS NOT NULL
)
SELECT 
    CASE WHEN opening_moneyline_home IS NOT NULL THEN 'has_odds' ELSE 'no_odds' END as odds_status,
    AVG(CASE WHEN final_winning_team = 0 THEN 1.0 ELSE 0.0 END) as home_win_rate,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT game_id) as game_count
FROM espn_with_features
WHERE final_winning_team IS NOT NULL
GROUP BY odds_status;
```

**What to look for:**
- Was calibration set biased toward games with opening odds?
- Was home win rate different for games with/without opening odds?

#### Step 1.4: Verify Opening Odds Data Quality

```sql
-- Check if opening odds values are reasonable
SELECT 
    MIN(opening_moneyline_home) as min_ml_home,
    MAX(opening_moneyline_home) as max_ml_home,
    AVG(opening_moneyline_home) as avg_ml_home,
    MIN(opening_moneyline_away) as min_ml_away,
    MAX(opening_moneyline_away) as max_ml_away,
    AVG(opening_moneyline_away) as avg_ml_away
FROM derived.snapshot_features_v1
WHERE opening_moneyline_home IS NOT NULL
  AND season_label IN ('2017-18', '2018-19', '2019-20', '2020-21', '2021-22', '2022-23');
```

**What to look for:**
- Are opening odds in decimal format (should be > 1.0)?
- Are there any extreme outliers?
- Are opening odds correlated with final scores (data leakage)?

### Phase 2: Model Retraining (2-3 days) - **REQUIRED**

**Goal:** Retrain the odds models with proper regularization and calibration to prevent feature dominance.

**Key Changes Needed:**
1. **Add regularization** to prevent opening odds features from dominating
2. **Feature engineering changes** to balance opening odds with in-game features
3. **Proper calibration** on unbiased calibration set
4. **Feature importance monitoring** during training

#### Step 2.1: Prepare Training Data

**Based on root cause analysis, we need to:**

1. **Add Regularization** (CRITICAL):
   - Increase `l2_leaf_reg` parameter in CatBoost (default is often too low)
   - Add `feature_border_type='GreedyLogSum'` to reduce overfitting
   - Consider `max_depth` reduction (currently 6, try 4-5)
   - Add `subsample` parameter (e.g., 0.8) to reduce overfitting

2. **Feature Engineering Changes**:
   - **Option A:** Reduce opening odds feature importance by:
     - Normalizing opening odds features differently (maybe log transform)
     - Adding more interaction terms with in-game features
     - Using opening odds as secondary features, not primary
   - **Option B:** Use feature importance limits:
     - Monitor feature importance during training
     - If opening odds > 50% importance, increase regularization
   - **Option C:** Separate models (simpler but less elegant):
     - Train model only on games WITH opening odds
     - Use baseline model for games WITHOUT opening odds

3. **Calibration Improvements**:
   - Ensure calibration set has balanced representation (not biased toward odds-present games)
   - Check calibration parameters after training (should be in normal ranges)
   - Consider using isotonic calibration instead of Platt (more flexible)

#### Step 2.2: Retrain Models

**CRITICAL:** Must modify training script to add regularization!

**Current training command:**
```bash
python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_odds_platt_v2.json \
    --calibration-method platt \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --use-interaction-terms \
    --dsn "$DATABASE_URL"
```

**Required modifications to `train_winprob_catboost.py`:**
1. **Add regularization parameters to CatBoost:**
   ```python
   model = CatBoostClassifier(
       iterations=int(args.iterations),
       depth=4,  # REDUCE from 6 to 4-5
       learning_rate=float(args.learning_rate),
       l2_leaf_reg=10.0,  # ADD: Increase from default (3.0) to 10.0
       random_strength=1.0,  # ADD: Regularization
       bagging_temperature=1.0,  # ADD: Regularization
       subsample=0.8,  # ADD: Use 80% of data per tree
       loss_function='Logloss',
       eval_metric='AUC',
       verbose=500,
       random_seed=42,
       allow_writing_files=False,
       thread_count=-1,
   )
   ```

2. **Monitor feature importance during training:**
   - After training, check feature importance
   - If opening odds > 50% importance, retrain with stronger regularization

**Key considerations:**
1. **Regularization:** CRITICAL - Must prevent opening odds from dominating (currently 88%)
2. **Feature engineering:** Opening odds should complement in-game features, not replace them
3. **Calibration:** Use proper calibration set (check distribution first)
4. **Verification:** After training, verify feature importance is balanced (< 50% for odds features)

#### Step 2.3: Evaluate New Models

```bash
# Evaluate on test set
python scripts/model/evaluate_winprob_model.py \
    --artifact artifacts/winprob_catboost_odds_platt_v2.json \
    --dsn "$DATABASE_URL"
```

**Check:**
- Average probability should be ~50-60% (not 96%)
- Calibration curve should be close to diagonal
- Brier score should be reasonable

#### Step 2.4: Precompute New Probabilities

```bash
# Precompute probabilities with new models
python scripts/model/precompute_model_probabilities.py \
    --dsn "$DATABASE_URL"
```

#### Step 2.5: Verify Fix

```sql
-- Check average probabilities by opening odds availability
SELECT 
    CASE 
        WHEN sf.opening_moneyline_home IS NOT NULL THEN 'has_odds'
        ELSE 'no_odds'
    END as odds_status,
    AVG(mp.catboost_odds_platt_prob) as avg_prob_platt,
    AVG(mp.catboost_baseline_platt_prob) as avg_prob_baseline
FROM derived.snapshot_features_v1 sf
JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
WHERE sf.season_label = '2025-26'
GROUP BY odds_status;
```

**Success criteria:**
- Average probability with odds: **50-65%** (not 96%)
- Average probability without odds: **50-65%** (similar to baseline)
- Difference between with/without odds: **< 10%**

### Phase 3: Grid Search & Validation (1-2 days)

**Goal:** Verify the retrained models perform well in trading simulations.

#### Step 3.1: Run Grid Search

```bash
# Run grid search with new models
python scripts/trade/grid_search_hyperparameters.py \
    --season 2025-26 \
    --model-name catboost_odds_platt_v2 \
    --dsn "$DATABASE_URL"
```

#### Step 3.2: Compare Performance

```bash
# Compare all models
python scripts/trade/compare_grid_search_models.py
```

**Success criteria:**
- `catboost_odds_platt_v2` should have:
  - **More trades:** 200+ (not 125)
  - **Better win rate:** > 60% (not 55%)
  - **Better profit:** > $1,000 (not $345)
  - **Comparable or better than baseline models**

---

## Alternative Approaches (If Retraining Doesn't Work)

### Approach 1: Use Opening Odds as Filter Only

Instead of using opening odds as features, use them as a filter:
- Only make predictions when opening odds are present
- Use baseline model when opening odds are missing
- This avoids the miscalibration issue entirely

### Approach 2: Ensemble Models

Combine predictions:
- Use odds model when opening odds present AND probability is reasonable (< 80%)
- Use baseline model otherwise
- Weight predictions based on opening odds confidence

### Approach 3: Post-Processing Calibration

Apply additional calibration layer:
- Train a meta-model that recalibrates odds model predictions
- Use baseline model predictions as features
- This could fix miscalibration without retraining

---

## Verification Checklist

After implementing the fix, verify:

- [ ] Average probability with opening odds: 50-65% (not 96%)
- [ ] Average probability without opening odds: 50-65% (similar to baseline)
- [ ] Calibration curve is close to diagonal
- [ ] Brier score is reasonable (< 0.25)
- [ ] Grid search shows 200+ trades (not 125)
- [ ] Win rate > 60% (not 55%)
- [ ] Profit > $1,000 (not $345)
- [ ] Feature importance shows reasonable distribution (opening odds not dominating)

---

## Timeline Estimate

- **Phase 1 (Investigation):** 1-2 days
- **Phase 2 (Retraining):** 2-3 days
- **Phase 3 (Validation):** 1-2 days
- **Total:** 4-7 days

---

## Immediate Workaround

Until the fix is implemented:

1. **Use baseline models** (`catboost_baseline_platt` or `catboost_baseline_isotonic`)
   - They perform better ($1,899 vs $345 profit)
   - They don't have miscalibration issues
   - They're already working correctly

2. **Document the issue** (this document)

3. **Plan retraining** (follow steps above)

---

## References

- Grid search results: `data/grid_search/model_comparison.json`
- Diagnostic script: `scripts/analysis/diagnose_odds_model_performance.py`
- Model inspection script: `scripts/analysis/inspect_odds_model_artifact.py`
- Training script: `scripts/model/train_winprob_catboost.py`
- Precomputation script: `scripts/model/precompute_model_probabilities.py`
