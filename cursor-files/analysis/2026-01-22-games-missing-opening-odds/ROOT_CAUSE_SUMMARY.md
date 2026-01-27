# Root Cause Summary: Why Games Have NULL espn_game_id

**Date**: 2026-01-22  
**Status**: **PARTIALLY IDENTIFIED** - Need database verification to confirm

## What We KNOW (Verified from Code)

### ✓ The Mechanism

1. **Records ARE inserted** even with `espn_game_id = NULL`
   - Code: `load_sportsbook_odds.py:656` - inserts records regardless of mapping success
   - Evidence: Code shows `row.get('espn_game_id')` can be None, and record is still appended

2. **Training script filters them out**
   - Code: `train_winprob_catboost.py:166` - requires `espn_game_id IS NOT NULL`
   - Evidence: Query explicitly filters out NULL values

3. **Team normalization WORKS**
   - Code: `load_sportsbook_odds.py:175-176, 310-311` - normalizes before mapping
   - Evidence: Tested 44 CSV team names, all normalized correctly (including "NY"→"NYK", "WSH"→"WAS")

4. **Mapping function logic**
   - Code: `load_sportsbook_odds.py:537-606` - uses ±1 day window, exact team match
   - Evidence: Function returns `None` if no match found

## What We DON'T KNOW (Needs Database Verification)

### ❓ The Root Cause

We know **HOW** it fails (mapping returns None), but we don't know **WHY** it fails. Possible reasons:

1. **ESPN games don't exist** in `espn.scoreboard_games` table
   - Some games might genuinely be missing from ESPN database
   - Preseason, international, or very old games

2. **Team abbreviation mismatch** (even after normalization)
   - Example: CSV normalizes to "CHA" but ESPN uses "CHO" for Charlotte
   - Need to check: What abbreviations are in NULL records vs what ESPN actually uses

3. **Date mismatch** beyond ±1 day window
   - ESPN game date might be more than 1 day off from CSV date
   - Timezone issues causing date to be 2+ days off

4. **Mapping logic bug**
   - The SQL query might have a subtle bug
   - Need to verify: Do ESPN games exist but mapping still fails?

## To Find the Root Cause

Run these SQL queries to get **actual evidence**:

```sql
-- Query 1: Check if ESPN games exist for NULL records
WITH sample_null AS (
    SELECT DISTINCT ON (game_date, away_team_espn, home_team_espn)
        game_date,
        away_team_espn,
        home_team_espn
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id IS NULL
      AND is_opening_line = TRUE
    LIMIT 20
)
SELECT 
    sn.game_date,
    sn.away_team_espn as odds_away,
    sn.home_team_espn as odds_home,
    sg.event_id as espn_game_id,
    sg.away_team_abbrev as espn_away,
    sg.home_team_abbrev as espn_home,
    CASE 
        WHEN sg.event_id IS NOT NULL THEN 'FOUND - Mapping should work!'
        ELSE 'NOT FOUND - Game missing or team mismatch'
    END as diagnosis
FROM sample_null sn
LEFT JOIN LATERAL (
    SELECT event_id, event_date, home_team_abbrev, away_team_abbrev
    FROM espn.scoreboard_games
    WHERE DATE(event_date) BETWEEN sn.game_date - INTERVAL '1 day' AND sn.game_date + INTERVAL '1 day'
      AND (
        (home_team_abbrev = sn.home_team_espn AND away_team_abbrev = sn.away_team_espn)
        OR (home_team_abbrev = sn.away_team_espn AND away_team_abbrev = sn.home_team_espn)
      )
    ORDER BY ABS(EXTRACT(EPOCH FROM (event_date - sn.game_date)))
    LIMIT 1
) sg ON true
ORDER BY sn.game_date;
```

**This query will tell us:**
- If ESPN games exist → Mapping logic has a bug
- If ESPN games don't exist → Games are missing from ESPN database
- If teams don't match → Team abbreviation issue

## Bottom Line

**We know WHAT happens** (records inserted with NULL, training filters them out)  
**We know HOW it happens** (mapping function returns None)  
**We DON'T know WHY it happens** (need database query results)

The SQL query above will give us the answer.
