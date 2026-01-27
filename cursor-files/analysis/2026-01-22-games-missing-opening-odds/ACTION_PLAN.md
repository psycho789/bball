# Action Plan: Fix NULL espn_game_id Issue

**Date**: 2026-01-22  
**Status**: Ready to execute

## ✅ Step 1: Fix Team Name Mapping (COMPLETED)

**File**: `scripts/lib/team_name_mapping.py`

**Changes Made**:
- Line 141-145: Changed "New York Knicks" → "NY" (was "NYK")
- Line 204-208: Changed "Washington Wizards" → "WSH" (was "WAS")

**Verification**: ESPN database uses "NY" and "WSH" (confirmed via SQL query)

## ⏳ Step 2: Verify All Team Abbreviations Match ESPN

**Command**:
```bash
source .env
psql "$DATABASE_URL" -c "
SELECT DISTINCT home_team_abbrev 
FROM espn.scoreboard_games 
WHERE home_team_abbrev NOT IN ('EAST', 'WEST', 'TBD', 'USA', 'REAL', 'GIA', 'CHK', 'DUR', 'LEB', 'SHQ', 'STE')
ORDER BY home_team_abbrev;
"
```

**Compare with**: `scripts/lib/team_name_mapping.py` values

**Expected**: All NBA team abbreviations should match (except special teams like "EAST", "WEST", etc.)

## ⏳ Step 3: Choose Fix Strategy

You have two options:

### Option A: Re-run Load Script (Recommended for New Data)

**Pros**: 
- Clean, fresh data with correct mappings
- No risk of corrupting existing data

**Cons**:
- Takes time to re-process all CSV files
- May create duplicate records (but ON CONFLICT should handle this)

**Command**:
```bash
# Re-run load script for each CSV file
python scripts/load/load_sportsbook_odds.py \
  --source nba_2008_2025 \
  --csv-file data/stats-csv/nba_2008-2025.csv \
  --dsn "$DATABASE_URL"

python scripts/load/load_sportsbook_odds.py \
  --source nba_main_lines \
  --csv-file data/stats-csv/nba_main_lines.csv \
  --dsn "$DATABASE_URL"
```

### Option B: Backfill Existing NULL Records (Faster)

**Pros**:
- Faster - only updates existing NULL records
- Doesn't re-process all data

**Cons**:
- More complex script needed
- Risk of partial updates if script fails

**Action**: Create backfill script (see Step 4)

## ⏳ Step 4: Create Backfill Script (If Using Option B)

**Script**: `scripts/load/backfill_espn_game_ids.py`

**Purpose**: 
- Find all records with `espn_game_id IS NULL` and `is_opening_line = TRUE`
- Extract team names from `raw_data` JSONB
- Re-normalize with fixed team mapping
- Re-attempt ESPN game mapping
- Update `espn_game_id` where matches found

**Key Logic**:
```python
# 1. Query NULL records
# 2. Extract teams from raw_data->>'team1', raw_data->>'team2' or raw_data->>'away', raw_data->>'home'
# 3. Normalize with fixed team_name_mapping
# 4. Use map_to_espn_game_ids_batch() with corrected abbreviations
# 5. UPDATE records with new espn_game_id
```

## ⏳ Step 5: Verify Fix Works

**Command**:
```bash
# Check NULL count before fix
psql "$DATABASE_URL" -c "
SELECT COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) 
FROM external.sportsbook_odds_snapshots;
"

# After fix, check again
# Should see significant reduction in NULL count
```

**Expected Result**: 
- Before: 4,850 NULL records
- After: Should be much lower (only games that genuinely don't exist in ESPN)

## ⏳ Step 6: Verify Training Script Can Find Opening Odds

**Command**:
```bash
# Test that training script can now find opening odds
python scripts/model/train_winprob_catboost.py --dry-run
```

**Check**: Training script should find more games with opening odds now

## Summary

1. ✅ **Fixed** `team_name_mapping.py` (NY and WSH corrections)
2. ⏳ **Verify** all team abbreviations match ESPN
3. ⏳ **Choose** fix strategy (re-run vs backfill)
4. ⏳ **Execute** chosen strategy
5. ⏳ **Verify** NULL count reduced
6. ⏳ **Test** training script works

## Quick Start (Recommended)

```bash
# 1. Verify team abbreviations
source .env
psql "$DATABASE_URL" -c "SELECT DISTINCT home_team_abbrev FROM espn.scoreboard_games WHERE home_team_abbrev NOT IN ('EAST', 'WEST', 'TBD', 'USA', 'REAL', 'GIA', 'CHK', 'DUR', 'LEB', 'SHQ', 'STE') ORDER BY home_team_abbrev;"

# 2. Re-run load script (if you want fresh data)
python scripts/load/load_sportsbook_odds.py --source nba_main_lines --csv-file data/stats-csv/nba_main_lines.csv --dsn "$DATABASE_URL"

# 3. Check results
psql "$DATABASE_URL" -c "SELECT COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) FROM external.sportsbook_odds_snapshots;"
```
