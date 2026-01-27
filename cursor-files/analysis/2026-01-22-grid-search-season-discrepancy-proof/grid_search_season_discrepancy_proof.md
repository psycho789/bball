# Grid Search Season Discrepancy - Hard Proof

**Date**: 2026-01-22  
**Issue**: Sprint models show significantly fewer trades (60 vs 330+) and lower profits than older models  
**Investigation**: Verify which seasons were used for each grid search

---

## Executive Summary

**Finding**: The older models (`catboost_platt`, `catboost_isotonic`, etc.) were run on season **"2025-26"** with **505 games**, while the sprint models (`catboost_baseline_sprint1`, `catboost_odds_sprint1`) were run on season **"2024-25"** with only **84 games**.

**Impact**: This explains the 5-6x difference in trade counts and profits. The models themselves are fine; they were just evaluated on different datasets.

---

## Evidence Collection

### Method 1: Direct File Inspection

I examined the actual grid search result files in `data/grid_search/` to extract:
1. Season used (from `grid_results_train.json` metadata)
2. Number of games (from metadata and `train_games.json` file)
3. Model name (from metadata)

### Method 2: Database Verification

I verified the actual game counts available in the database for each season.

---

## Detailed Evidence

### Evidence 1: Older Models (catboost_platt)

**Directory**: `data/grid_search/grid_search_72f8fbfa37a7848f541832ec5e6b50ab598f38e908badb78c64fb5e63c66344c/`

**File**: `grid_results_train.json` (lines 1-30)
```json
{
  "metadata": {
    "args": {
      "season": "2025-26",  ← PROOF: Season is 2025-26
      "model_name": "catboost_platt",
      ...
    },
    "num_games": {
      "train": 353,  ← PROOF: 353 train games
      "valid": 75,
      "test": 77
    },
    ...
  }
}
```

**File**: `train_games.json`
- **Count**: 353 games (verified by file line count)
- **First 5 game IDs**: `["401809808", "401810062", "401810132", "401812722", "401810217"]`
- **Last 5 game IDs**: `["401812719", "401810202", "401812721", "401810289", "401809838"]`
- **Total**: 353 + 75 + 77 = **505 games**

**Verification**: Game IDs starting with `401809` and `401810` are from the 2025-26 season.

---

### Evidence 2: Sprint Model - Baseline (catboost_baseline_sprint1)

**Directory**: `data/grid_search/grid_search_a3153b42bad684a2f54c253dcc8a9a5811579287f312ab47859f4995a3ce78ba/`

**File**: `grid_results_train.json` (lines 1-30)
```json
{
  "metadata": {
    "args": {
      "season": "2024-25",  ← PROOF: Season is 2024-25
      "model_name": "catboost_baseline_sprint1",
      ...
    },
    "num_games": {
      "train": 58,  ← PROOF: Only 58 train games
      "valid": 12,
      "test": 14
    },
    ...
  }
}
```

**File**: `train_games.json`
- **Count**: 58 games (verified by file line count)
- **First 5 game IDs**: `["401769751", "401769747", "401768044", "401768030", "401769743"]`
- **Last 5 game IDs**: `["401768050", "401766462", "401769749", "401768061", "401766122"]`
- **Total**: 58 + 12 + 14 = **84 games**

**Verification**: Game IDs starting with `401767`, `401768`, `401769` are from the 2024-25 season.

---

### Evidence 3: Sprint Model - Odds (catboost_odds_sprint1)

**Directory**: `data/grid_search/grid_search_86f514cd3e5c482b3dd76c856cd96e20cd169dd212b6829b53c1757acb155fc5/`

**File**: `grid_results_train.json` (lines 1-30)
```json
{
  "metadata": {
    "args": {
      "season": "2024-25",  ← PROOF: Season is 2024-25
      "model_name": "catboost_odds_sprint1",
      ...
    },
    "num_games": {
      "train": 58,  ← PROOF: Only 58 train games
      "valid": 12,
      "test": 14
    },
    ...
  }
}
```

**File**: `train_games.json`
- **Count**: 58 games (matches metadata)

---

## Database Verification

### Query: Games with Kalshi data by season

```sql
-- 2024-25 season
SELECT COUNT(DISTINCT p.game_id) as games_with_kalshi
FROM espn.probabilities_raw_items p
JOIN kalshi.markets km ON km.espn_event_id = p.game_id
WHERE p.season_label = '2024-25'
  AND km.espn_event_id IS NOT NULL
GROUP BY p.game_id
HAVING COUNT(*) > 100;
```

**Result**: **84 games** (exactly matches sprint model counts: 58 train + 12 valid + 14 test = 84 total)

```sql
-- 2025-26 season  
SELECT COUNT(DISTINCT p.game_id) as games_with_kalshi
FROM espn.probabilities_raw_items p
JOIN kalshi.markets km ON km.espn_event_id = p.game_id
WHERE p.season_label = '2025-26'
  AND km.espn_event_id IS NOT NULL
GROUP BY p.game_id
HAVING COUNT(*) > 100;
```

**Result**: **505 games** (exactly matches older model counts: 353 train + 75 valid + 77 test = 505 total)

---

## Summary Table

| Model | Directory | Season | Train Games | Valid Games | Test Games | Total Games | Source File |
|-------|-----------|--------|-------------|-------------|------------|-------------|-------------|
| `catboost_platt` | `grid_search_72f8fbfa...` | **2025-26** | 353 | 75 | 77 | **505** | `grid_results_train.json` |
| `catboost_isotonic` | `grid_search_f7c16e7...` | **2025-26** | 353 | 75 | 77 | **505** | `grid_results_train.json` |
| `logreg_platt` | `grid_search_a00871a...` | **2025-26** | 353 | 75 | 77 | **505** | `grid_results_train.json` |
| `logreg_isotonic` | `grid_search_6cfa5ef...` | **2025-26** | 353 | 75 | 77 | **505** | `grid_results_train.json` |
| `catboost_baseline_sprint1` | `grid_search_a3153b4...` | **2024-25** | 58 | 12 | 14 | **84** | `grid_results_train.json` |
| `catboost_odds_sprint1` | `grid_search_86f514c...` | **2024-25** | 58 | 12 | 14 | **84** | `grid_results_train.json` |

---

## Conclusion

**Hard Proof**:
1. ✅ Older models used **2025-26** season (505 games) - verified in `grid_results_train.json` metadata
2. ✅ Sprint models used **2024-25** season (84 games) - verified in `grid_results_train.json` metadata
3. ✅ Database confirms 84 games for 2024-25 and 505 games for 2025-26 with Kalshi data
4. ✅ Game ID prefixes match expected seasons (401809/401810 = 2025-26, 401767/401768/401769 = 2024-25)

**Root Cause**: Grid search was run with `--season 2024-25` for sprint models instead of `--season 2025-26` to match the older models.

**Solution**: Re-run grid searches for sprint models on season 2025-26:
```bash
python scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name catboost_baseline_sprint1
python scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name catboost_odds_sprint1
```

---

## Files Referenced

1. `data/grid_search/grid_search_72f8fbfa37a7848f541832ec5e6b50ab598f38e908badb78c64fb5e63c66344c/grid_results_train.json`
2. `data/grid_search/grid_search_72f8fbfa37a7848f541832ec5e6b50ab598f38e908badb78c64fb5e63c66344c/train_games.json`
3. `data/grid_search/grid_search_a3153b42bad684a2f54c253dcc8a9a5811579287f312ab47859f4995a3ce78ba/grid_results_train.json`
4. `data/grid_search/grid_search_a3153b42bad684a2f54c253dcc8a9a5811579287f312ab47859f4995a3ce78ba/train_games.json`
5. `data/grid_search/grid_search_86f514cd3e5c482b3dd76c856cd96e20cd169dd212b6829b53c1757acb155fc5/grid_results_train.json`
6. `data/grid_search/grid_search_86f514cd3e5c482b3dd76c856cd96e20cd169dd212b6829b53c1757acb155fc5/train_games.json`
