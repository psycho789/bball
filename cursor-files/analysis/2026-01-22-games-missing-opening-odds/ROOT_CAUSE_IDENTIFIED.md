# Root Cause: Why Games Have NULL espn_game_id

**Date**: 2026-01-22  
**Status**: ✅ **IDENTIFIED**

## Summary

**Root Cause**: Team abbreviation mismatch between normalized names and ESPN database abbreviations.

**Impact**: 4,850 opening line records (13.0% of all records) have NULL espn_game_id, preventing them from being used by the training script.

## The Problem

The `load_sportsbook_odds.py` script inserts records into the database, but ESPN game mapping fails because team abbreviations don't match.

## Evidence

### Database Statistics
```sql
SELECT COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) 
FROM external.sportsbook_odds_snapshots;
```
**Result**: 4,850 records with NULL espn_game_id

### ESPN Games Exist But Mapping Fails

**Sample Game 1**: 2025-10-22 "Cleveland Cavaliers @ New York Knicks"
- ESPN game exists: `401809234`
- ESPN stores: `away_team_abbrev = 'CLE'`, `home_team_abbrev = 'NY'`
- Script normalizes to: `away_team_espn = 'CLE'`, `home_team_espn = 'NYK'`
- Mapping query looks for: `home_team_abbrev = 'NYK'` ❌
- ESPN has: `home_team_abbrev = 'NY'` ✓
- **Result**: No match → `espn_game_id` stays NULL

**Sample Game 2**: 2025-10-22 "Washington Wizards @ Milwaukee Bucks"
- ESPN game exists: `401809939`
- ESPN stores: `away_team_abbrev = 'WSH'`, `home_team_abbrev = 'MIL'`
- Script normalizes to: `away_team_espn = 'WAS'`, `home_team_espn = 'MIL'`
- Mapping query looks for: `away_team_abbrev = 'WAS'` ❌
- ESPN has: `away_team_abbrev = 'WSH'` ✓
- **Result**: No match → `espn_game_id` stays NULL

## The Bug

**File**: `scripts/lib/team_name_mapping.py`

**Line 144**: `"New York Knicks": "NYK"` → Should be `"NY"`
**Line 207**: `"Washington Wizards": "WAS"` → Should be `"WSH"`

The normalization function converts team names to abbreviations that **don't match** what ESPN actually uses in their database.

## Solution

1. **Fix team_name_mapping.py**:
   - Change "New York Knicks" → "NY" (not "NYK")
   - Change "Washington Wizards" → "WSH" (not "WAS")
   - Verify all other team abbreviations match ESPN's actual abbreviations

2. **Verify ESPN abbreviations**:
   ```sql
   SELECT DISTINCT home_team_abbrev, away_team_abbrev 
   FROM espn.scoreboard_games 
   ORDER BY home_team_abbrev;
   ```

3. **Backfill existing NULL records**:
   - Re-run mapping with corrected abbreviations
   - Update `espn_game_id` for records where games exist

## Verification Commands

```bash
# Check current NULL count
psql $DATABASE_URL -c "
SELECT COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) 
FROM external.sportsbook_odds_snapshots;
"

# Check ESPN abbreviations
psql $DATABASE_URL -c "
SELECT DISTINCT home_team_abbrev 
FROM espn.scoreboard_games 
WHERE home_team_abbrev IN ('NY', 'NYK', 'WSH', 'WAS')
ORDER BY home_team_abbrev;
"
```

## Next Steps

1. ✅ Root cause identified
2. ⏳ Fix `team_name_mapping.py` abbreviations
3. ⏳ Verify all team abbreviations match ESPN
4. ⏳ Re-run load script or create backfill script
5. ⏳ Verify training script can now find opening odds
