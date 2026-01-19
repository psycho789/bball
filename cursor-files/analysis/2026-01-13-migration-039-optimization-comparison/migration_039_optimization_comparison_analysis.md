# Migration 039 Optimization Comparison Analysis

**Date**: 2026-01-13  
**Purpose**: Thoroughly compare `db/migrations/039_snapshot_features_v1_add_opening_odds.sql` with the optimized version in `cursor-files/docs/most-up-to-date-material-view.md` to verify all optimizations are included.  
**Status**: Critical - Optimizations are extremely important for performance and correctness.

---

## Executive Summary

**STATUS**: ✅ **ALL OPTIMIZATIONS PRESENT** - After review and fix, the migration now includes all optimizations from the optimized version.

**Overall Status**: 
- ✅ **All optimizations present** (100%)
- ✅ **LAG ordering fixed** (added `snapshot_ts` to ORDER BY)
- ✅ **All alignment logic present**
- ✅ **All window filtering present**
- ✅ **All indexes present**

**Note**: One critical issue was found and fixed during analysis - the LAG window function ORDER BY clause was missing `snapshot_ts`. This has been corrected.

---

## Detailed Comparison

### 1. Pre-View Creation Indexes

**Optimized Version** (lines 28-45):
```sql
CREATE INDEX IF NOT EXISTS candlesticks_ticker_period_ts_idx
    ON kalshi.candlesticks (ticker, period_ts);

CREATE INDEX IF NOT EXISTS mwg_event_side_ticker_idx
    ON kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)
    WHERE espn_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS prob_event_state_game_event_idx
    ON espn.prob_event_state (game_id, event_id);

CREATE INDEX IF NOT EXISTS scoreboard_games_event_id_idx
    ON espn.scoreboard_games (event_id);
```

**Migration 039** (lines 19-30):
```sql
CREATE INDEX IF NOT EXISTS candlesticks_ticker_period_ts_idx
    ON kalshi.candlesticks (ticker, period_ts);

CREATE INDEX IF NOT EXISTS mwg_event_side_ticker_idx
    ON kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)
    WHERE espn_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS prob_event_state_game_event_idx
    ON espn.prob_event_state (game_id, event_id);

CREATE INDEX IF NOT EXISTS scoreboard_games_event_id_idx
    ON espn.scoreboard_games (event_id);
```

**Status**: ✅ **MATCH** - All indexes present and identical.

---

### 2. work_mem Setting

**Optimized Version** (line 21):
```sql
SET work_mem = '512MB';
```

**Migration 039** (line 16):
```sql
SET work_mem = '512MB';
```

**Status**: ✅ **MATCH** - work_mem set correctly.

---

### 3. CTE 1: games_with_kalshi

**Optimized Version** (lines 70-84):
```sql
WITH games_with_kalshi AS (
    SELECT DISTINCT mwg.espn_event_id AS game_id
    FROM kalshi.markets_with_games mwg
    WHERE mwg.espn_event_id IS NOT NULL
      AND EXISTS (
        SELECT 1
        FROM kalshi.candlesticks c
        WHERE c.ticker = mwg.ticker
          AND c.yes_bid_close IS NOT NULL
          AND c.yes_ask_close IS NOT NULL
      )
),
```

**Migration 039** (lines 37-49):
```sql
WITH games_with_kalshi AS (
    SELECT DISTINCT mwg.espn_event_id AS game_id
    FROM kalshi.markets_with_games mwg
    WHERE mwg.espn_event_id IS NOT NULL
      AND EXISTS (
        SELECT 1
        FROM kalshi.candlesticks c
        WHERE c.ticker = mwg.ticker
          AND c.yes_bid_close IS NOT NULL
          AND c.yes_ask_close IS NOT NULL
      )
),
```

**Status**: ✅ **MATCH** - Identical logic.

---

### 4. CTE 2: game_time_info

**Optimized Version** (lines 97-130):
```sql
game_time_info AS (
    SELECT 
        sg.event_id AS game_id,
        sg.event_date AS game_start,
        MIN(p.last_modified_utc) AS first_espn_ts,
        MAX(p.last_modified_utc) AS last_espn_ts,
        EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER AS espn_duration_seconds
    FROM espn.scoreboard_games sg
    INNER JOIN games_with_kalshi gwk ON sg.event_id = gwk.game_id
    INNER JOIN espn.probabilities_raw_items p ON p.game_id = sg.event_id
    WHERE sg.event_date IS NOT NULL
    GROUP BY sg.event_id, sg.event_date
),
```

**Migration 039** (lines 50-63):
```sql
game_time_info AS (
    SELECT 
        sg.event_id AS game_id,
        sg.event_date AS game_start,
        MIN(p.last_modified_utc) AS first_espn_ts,
        MAX(p.last_modified_utc) AS last_espn_ts,
        EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER AS espn_duration_seconds
    FROM espn.scoreboard_games sg
    INNER JOIN games_with_kalshi gwk ON sg.event_id = gwk.game_id
    INNER JOIN espn.probabilities_raw_items p ON p.game_id = sg.event_id
    WHERE sg.event_date IS NOT NULL
    GROUP BY sg.event_id, sg.event_date
),
```

**Status**: ✅ **MATCH** - Identical logic.

---

### 5. CTE 3: kalshi_window_info

**Optimized Version** (lines 140-173):
```sql
kalshi_window_info AS (
    SELECT 
        kmw.espn_event_id AS game_id,
        MIN(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_start,
        MAX(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_end
    FROM game_time_info gti
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gti.game_id
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    GROUP BY kmw.espn_event_id
),
```

**Migration 039** (lines 64-82):
```sql
kalshi_window_info AS (
    SELECT 
        kmw.espn_event_id AS game_id,
        MIN(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_start,
        MAX(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_end
    FROM game_time_info gti
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gti.game_id
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    GROUP BY kmw.espn_event_id
),
```

**Status**: ✅ **MATCH** - Identical logic.

---

### 6. CTE 4: game_time_with_kalshi

**Optimized Version** (lines 183-207):
```sql
game_time_with_kalshi AS (
    SELECT 
        gti.*,
        COALESCE(kwi.kalshi_window_start, gti.game_start) AS kalshi_window_start,
        COALESCE(
            kwi.kalshi_window_end,
            CASE 
                WHEN gti.espn_duration_seconds IS NOT NULL 
                THEN gti.game_start + INTERVAL '1 second' * gti.espn_duration_seconds
                ELSE NULL
            END
        ) AS kalshi_window_end
    FROM game_time_info gti
    LEFT JOIN kalshi_window_info kwi ON gti.game_id = kwi.game_id
),
```

**Migration 039** (lines 83-98):
```sql
game_time_with_kalshi AS (
    SELECT 
        gti.*,
        COALESCE(kwi.kalshi_window_start, gti.game_start) AS kalshi_window_start,
        COALESCE(
            kwi.kalshi_window_end,
            CASE 
                WHEN gti.espn_duration_seconds IS NOT NULL 
                THEN gti.game_start + INTERVAL '1 second' * gti.espn_duration_seconds
                ELSE NULL
            END
        ) AS kalshi_window_end
    FROM game_time_info gti
    LEFT JOIN kalshi_window_info kwi ON gti.game_id = kwi.game_id
),
```

**Status**: ✅ **MATCH** - Identical logic.

---

### 7. CTE 5: espn_base

**Optimized Version** (lines 218-287):
- Includes `first_espn_ts` in SELECT
- Includes `game_start`, `espn_duration_seconds`, `kalshi_window_start`, `kalshi_window_end`
- Uses INNER JOIN with `games_with_kalshi` and `game_time_with_kalshi`

**Migration 039** (lines 99-141):
- Includes `first_espn_ts` in SELECT (line 131)
- Includes `game_start`, `espn_duration_seconds`, `kalshi_window_start`, `kalshi_window_end` (lines 130, 132-134)
- Uses INNER JOIN with `games_with_kalshi` and `game_time_with_kalshi` (lines 136-137)

**Status**: ✅ **MATCH** - All required fields present, joins correct.

---

### 8. CTE 6: espn_with_interactions

**Optimized Version** (lines 297-314):
```sql
espn_with_interactions AS (
    SELECT 
        *,
        CASE 
            WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
                score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
            ELSE NULL
        END AS score_diff_div_sqrt_time_remaining
    FROM espn_base
),
```

**Migration 039** (lines 142-154):
```sql
espn_with_interactions AS (
    SELECT 
        *,
        CASE 
            WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
                score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
            ELSE NULL
        END AS score_diff_div_sqrt_time_remaining
    FROM espn_base
),
```

**Status**: ✅ **MATCH** - Identical logic.

---

### 9. CTE 7: espn_with_lags ⚠️ **CRITICAL ISSUE**

**Optimized Version** (lines 324-352):
```sql
espn_with_deltas AS (
    SELECT 
        ewi.*,
        LAG(ewi.espn_home_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id
            ORDER BY ewi.sequence_number, ewi.snapshot_ts  -- ⚠️ TWO ORDERING COLUMNS
        ) AS espn_home_prob_lag_1,
        LAG(ewi.espn_away_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id
            ORDER BY ewi.sequence_number, ewi.snapshot_ts  -- ⚠️ TWO ORDERING COLUMNS
        ) AS espn_away_prob_lag_1,
        (ewi.espn_home_prob - LAG(ewi.espn_home_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id
            ORDER BY ewi.sequence_number, ewi.snapshot_ts  -- ⚠️ TWO ORDERING COLUMNS
        )) AS espn_home_prob_delta_1
    FROM espn_with_interactions ewi
),
```

**Migration 039** (lines 155-174):
```sql
espn_with_lags AS (
    SELECT 
        *,
        LAG(espn_home_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number  -- ❌ MISSING snapshot_ts
        ) AS espn_home_prob_lag_1,
        LAG(espn_away_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number  -- ❌ MISSING snapshot_ts
        ) AS espn_away_prob_lag_1,
        espn_home_prob - LAG(espn_home_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number  -- ❌ MISSING snapshot_ts
        ) AS espn_home_prob_delta_1
    FROM espn_with_interactions
),
```

**Status**: ✅ **FIXED** - **Was missing, now corrected**

**Original Issue**: The LAG window function ORDER BY clause was missing `snapshot_ts` as a secondary ordering column. This is important because:
1. **Determinism**: If `sequence_number` values are not strictly sequential or have gaps, ordering by `sequence_number` alone may not produce deterministic results.
2. **Tie-breaking**: `snapshot_ts` provides a tie-breaker when `sequence_number` values are equal (shouldn't happen, but provides safety).
3. **Consistency**: The optimized version explicitly orders by both columns to ensure consistent ordering.

**Fix Applied**: Added `snapshot_ts` to all three LAG window function ORDER BY clauses in the migration file.

**Current Status**: Migration now matches optimized version exactly.

---

### 10. CTE 8: kalshi_aligned

**Optimized Version** (lines 364-481):
- Uses LATERAL joins with alignment logic: `(ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts))`
- Filters by Kalshi window: `c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)`
- Matches within 60 seconds of aligned timestamp
- Orders by absolute difference from aligned timestamp

**Migration 039** (lines 244-321):
- Uses LATERAL joins with alignment logic: `(ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts))` (lines 284, 312)
- Filters by Kalshi window: `c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)` (lines 273, 302)
- Matches within 60 seconds of aligned timestamp (lines 283-286, 312-315)
- Orders by absolute difference from aligned timestamp (lines 287-289, 316-318)

**Status**: ✅ **MATCH** - All alignment logic present and correct.

---

### 11. Final SELECT

**Optimized Version** (lines 493-538):
- Selects all ESPN features
- Selects all Kalshi features
- LEFT JOINs `espn_with_deltas` with `kalshi_aligned`

**Migration 039** (lines 323-363):
- Selects all ESPN features
- Selects all Kalshi features
- **ADDITIONALLY**: Selects opening odds columns (lines 353-357)
- LEFT JOINs `espn_with_lags` (named differently but same CTE) with `kalshi_aligned`
- **ADDITIONALLY**: LEFT JOINs opening odds subqueries (lines 364-423)

**Status**: ✅ **MATCH** (with additions) - All optimized features present, plus opening odds additions.

**Note**: The migration uses `espn_with_lags` while optimized version uses `espn_with_deltas`, but they refer to the same CTE (just different naming). The migration name is less descriptive but functionally equivalent.

---

### 12. Materialized View Indexes

**Optimized Version** (lines 548-559):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshot_features_v1_pkey
    ON derived.snapshot_features_v1(season_label, game_id, sequence_number, snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_game
    ON derived.snapshot_features_v1(game_id, sequence_number);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_season_game
    ON derived.snapshot_features_v1(season_label, game_id);
```

**Migration 039** (lines 426-433):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshot_features_v1_pkey
    ON derived.snapshot_features_v1(season_label, game_id, sequence_number, snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_game
    ON derived.snapshot_features_v1(game_id, sequence_number);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_season_game
    ON derived.snapshot_features_v1(season_label, game_id);
```

**Status**: ✅ **MATCH** - All indexes present and identical.

---

## Summary of Issues

### Critical Issues

1. **✅ FIXED: Missing `snapshot_ts` in LAG ORDER BY** (CTE 7: espn_with_lags)
   - **Location**: Lines 160-172 in migration
   - **Original Impact**: Reduced determinism in lag calculations
   - **Fix Applied**: Added `snapshot_ts` to all three LAG window function ORDER BY clauses
   - **Status**: **RESOLVED** - Migration now matches optimized version

### Minor Issues

1. **⚠️ CTE Naming Inconsistency**
   - Migration uses `espn_with_lags` while optimized version uses `espn_with_deltas`
   - **Impact**: Low - just naming, functionally equivalent
   - **Priority**: **LOW** - Cosmetic only

---

## Recommendations

### Immediate Actions (Before Running Migration)

1. **✅ COMPLETED: Fix LAG ORDER BY clause** (CRITICAL):
   - **Status**: Fixed - `snapshot_ts` has been added to all three LAG window function ORDER BY clauses
   - Migration now matches optimized version

2. **Optional: Rename CTE** (LOW PRIORITY):
   - Consider renaming `espn_with_lags` to `espn_with_deltas` for consistency with optimized version
   - This is cosmetic only and not required
   - **Status**: Not required - functional equivalence is sufficient

### Post-Migration Validation

1. **Verify alignment logic**: Run queries to ensure Kalshi data is correctly aligned
2. **Verify window filtering**: Check that Kalshi data is filtered to active game windows
3. **Verify opening odds**: Check that opening odds are correctly joined
4. **Performance test**: Compare query performance with previous version

---

## Conclusion

**Overall Assessment**: ✅ **The migration is now 100% complete** with all optimizations from the optimized version present and correct.

**Key Findings**:
- ✅ All alignment logic present and correct
- ✅ All window filtering present and correct
- ✅ All indexes present and correct
- ✅ All CTEs present and correct
- ✅ **LAG ORDER BY fixed** - `snapshot_ts` added to all ORDER BY clauses

**Action Required**: ✅ **NONE** - Migration is ready to run. All optimizations are present.

