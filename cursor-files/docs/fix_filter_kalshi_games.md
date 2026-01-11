# Fix: Filter Canonical Dataset to Only Games with Kalshi Markets

**Date**: 2026-01-04  
**Issue**: The canonical dataset (`derived.snapshot_features_v1`) includes games without Kalshi markets, causing many rows to be filtered out later in Python. This matches the old behavior where only games with Kalshi markets were included.

**Solution**: Add a filter at the beginning of the view to only include games that have Kalshi markets.

**Note**: This fix incorporates corrections for:
1. ✅ Filtering to games with Kalshi markets (good change)
2. ✅ Using LATERAL joins to prevent row explosion (performance fix)
3. ✅ Preserving all sequence_numbers (correctness fix - no DISTINCT ON dropping rows)
4. ✅ Finding closest candlestick (ORDER BY ABS(time_diff), not DESC)
5. ✅ Tightening filter to only games with actual candlestick data (not just markets)
6. ✅ Deterministic tie-breaking (c.period_ts DESC if equally close)
7. ✅ Range queries for better index usage (BETWEEN instead of ABS() in WHERE)
8. ✅ EXISTS instead of JOIN in games_with_kalshi (more efficient)
9. ✅ Consistent verification query (EXISTS matches view filter)
10. ✅ Index for ESPN prob_event_state join (performance optimization)

---

## SQL Commands to Run

```sql
-- Step 1: Set work_mem and create indexes (BEFORE rebuilding)
-- Set work_mem to prevent temp file spills (adjust for your system)
SET work_mem = '512MB';

-- Create indexes that make LATERAL joins fast (critical for performance)
CREATE INDEX IF NOT EXISTS candlesticks_ticker_period_ts_idx
    ON kalshi.candlesticks (ticker, period_ts);

CREATE INDEX IF NOT EXISTS mwg_event_side_ticker_idx
    ON kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)
    WHERE espn_event_id IS NOT NULL;

-- Index for ESPN prob_event_state join (happens on every row in espn_base)
CREATE INDEX IF NOT EXISTS prob_event_state_game_event_idx
    ON espn.prob_event_state (game_id, event_id);

-- Step 2: Drop existing materialized view
DROP MATERIALIZED VIEW IF EXISTS derived.snapshot_features_v1 CASCADE;

-- Step 3: Recreate with filter for games with Kalshi markets
CREATE MATERIALIZED VIEW derived.snapshot_features_v1 AS
WITH games_with_kalshi AS (
    -- Only include games that have Kalshi markets WITH candlesticks (matches old get_aligned_data behavior)
    -- Tightened: Only games that actually have candlestick data we can align
    -- Using EXISTS instead of JOIN avoids creating duplicate rows before DISTINCT (more efficient)
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
espn_base AS (
    -- Base ESPN probability data with normalized probabilities (0-1 format)
    -- FILTERED: Only include games with Kalshi markets
    SELECT 
        p.season_label,
        p.game_id,
        p.sequence_number,
        p.event_id,
        p.last_modified_utc AS snapshot_ts,
        CASE 
            WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0
            ELSE p.home_win_percentage
        END AS espn_home_prob,
        CASE 
            WHEN p.away_win_percentage > 1.0 THEN p.away_win_percentage / 100.0
            ELSE p.away_win_percentage
        END AS espn_away_prob,
        e.point_differential AS score_diff,
        e.time_remaining,
        e.home_score,
        e.away_score,
        CASE 
            WHEN e.time_remaining IS NULL THEN NULL
            WHEN e.time_remaining > 2160 THEN 1
            WHEN e.time_remaining > 1440 THEN 2
            WHEN e.time_remaining > 720 THEN 3
            ELSE 4
        END AS period
    FROM espn.probabilities_raw_items p
    INNER JOIN games_with_kalshi gwk ON p.game_id = gwk.game_id  -- FILTER: Only games with Kalshi markets
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
),
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
espn_with_deltas AS (
    SELECT 
        ewi.*,
        LAG(ewi.espn_home_prob, 1) OVER (PARTITION BY ewi.season_label, ewi.game_id ORDER BY ewi.sequence_number, ewi.snapshot_ts) AS espn_home_prob_lag_1,
        LAG(ewi.espn_away_prob, 1) OVER (PARTITION BY ewi.season_label, ewi.game_id ORDER BY ewi.sequence_number, ewi.snapshot_ts) AS espn_away_prob_lag_1,
        (ewi.espn_home_prob - LAG(ewi.espn_home_prob, 1) OVER (PARTITION BY ewi.season_label, ewi.game_id ORDER BY ewi.sequence_number, ewi.snapshot_ts)) AS espn_home_prob_delta_1
    FROM espn_with_interactions ewi
),
kalshi_aligned AS (
    -- Use LATERAL joins to find closest candlestick per ESPN row (avoids row explosion)
    -- This ensures we get exactly one candlestick per ESPN snapshot, ordered by closest time difference
    SELECT
        ewd.season_label,
        ewd.game_id,
        ewd.sequence_number,
        ewd.snapshot_ts,
        (kh.yes_bid_close::NUMERIC / 100.0) AS kalshi_home_bid,
        (kh.yes_ask_close::NUMERIC / 100.0) AS kalshi_home_ask,
        ((kh.yes_bid_close::NUMERIC + kh.yes_ask_close::NUMERIC) / 200.0) AS kalshi_home_mid_price,
        ((kh.yes_ask_close::NUMERIC - kh.yes_bid_close::NUMERIC) / 100.0) AS kalshi_home_spread,
        (1.0 - (ka.yes_ask_close::NUMERIC / 100.0)) AS kalshi_away_bid,
        (1.0 - (ka.yes_bid_close::NUMERIC / 100.0)) AS kalshi_away_ask,
        (1.0 - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0)) AS kalshi_away_mid_price,
        ((ka.yes_ask_close::NUMERIC - ka.yes_bid_close::NUMERIC) / 100.0) AS kalshi_away_spread
    FROM espn_with_deltas ewd
    LEFT JOIN LATERAL (
        SELECT c.*
        FROM kalshi.markets_with_games mwg
        JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
        WHERE mwg.espn_event_id = ewd.game_id
          AND mwg.kalshi_team_side = 'home'
          AND c.yes_bid_close IS NOT NULL
          AND c.yes_ask_close IS NOT NULL
          -- Use range query for better index usage (instead of ABS() which scans more rows)
          AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                              AND ewd.snapshot_ts + INTERVAL '60 seconds'
        ORDER BY 
          ABS(EXTRACT(EPOCH FROM (c.period_ts - ewd.snapshot_ts))),
          c.period_ts DESC  -- Tie-breaker: prefer later timestamp if equally close
        LIMIT 1
    ) kh ON true
    LEFT JOIN LATERAL (
        SELECT c.*
        FROM kalshi.markets_with_games mwg
        JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
        WHERE mwg.espn_event_id = ewd.game_id
          AND mwg.kalshi_team_side = 'away'
          AND c.yes_bid_close IS NOT NULL
          AND c.yes_ask_close IS NOT NULL
          -- Use range query for better index usage (instead of ABS() which scans more rows)
          AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                              AND ewd.snapshot_ts + INTERVAL '60 seconds'
        ORDER BY 
          ABS(EXTRACT(EPOCH FROM (c.period_ts - ewd.snapshot_ts))),
          c.period_ts DESC  -- Tie-breaker: prefer later timestamp if equally close
        LIMIT 1
    ) ka ON true
)
SELECT
    ewd.season_label,
    ewd.game_id,
    ewd.sequence_number,
    ewd.snapshot_ts,
    ewd.espn_home_prob,
    ewd.espn_away_prob,
    ewd.score_diff,
    ewd.time_remaining,
    ewd.period,
    ewd.home_score,
    ewd.away_score,
    ewd.score_diff_div_sqrt_time_remaining,
    ewd.espn_home_prob_lag_1,
    ewd.espn_away_prob_lag_1,
    ewd.espn_home_prob_delta_1,
    ka.kalshi_home_bid,
    ka.kalshi_home_ask,
    ka.kalshi_home_mid_price,
    ka.kalshi_home_spread,
    ka.kalshi_away_bid,
    ka.kalshi_away_ask,
    ka.kalshi_away_mid_price,
    ka.kalshi_away_spread
FROM espn_with_deltas ewd
LEFT JOIN kalshi_aligned ka ON ewd.game_id = ka.game_id AND ewd.snapshot_ts = ka.snapshot_ts AND ewd.sequence_number = ka.sequence_number;

-- Step 4: Recreate indexes on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshot_features_v1_pkey
    ON derived.snapshot_features_v1(season_label, game_id, sequence_number, snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_game
    ON derived.snapshot_features_v1(game_id, sequence_number);

CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_season_game
    ON derived.snapshot_features_v1(season_label, game_id);

-- Step 5: Update comment
COMMENT ON MATERIALIZED VIEW derived.snapshot_features_v1 IS
'Canonical snapshot dataset for signal improvement (MATERIALIZED VIEW for performance).
FILTERED: Only includes games with Kalshi markets that have candlestick data (matches old get_aligned_data behavior).
Uniqueness: (season_label, game_id, sequence_number, snapshot_ts).
Ordering: sequence_number (preferred) or snapshot_ts (fallback).
Kalshi data aligned within 60 seconds of ESPN timestamps using LATERAL joins (closest candlestick per snapshot).
Home and away markets stored separately (no fallback logic - use home market fields for home perspective).
Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;';
```

---

## Key Changes

### 1. Filter to Games with Kalshi Markets

**Before**: 
```sql
FROM espn.probabilities_raw_items p
LEFT JOIN espn.prob_event_state e ...
```

**After**:
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
...
FROM espn.probabilities_raw_items p
INNER JOIN games_with_kalshi gwk ON p.game_id = gwk.game_id  -- FILTER: Only games with Kalshi markets
LEFT JOIN espn.prob_event_state e ...
```

**Benefits**:
- ✅ Only includes games with Kalshi markets **that have candlestick data**
- ✅ Uses EXISTS instead of JOIN (more efficient - stops at first match, avoids duplicate rows before DISTINCT)

### 2. Use LATERAL Joins for Kalshi Alignment (Performance Fix)

**Before** (WRONG - causes row explosion):
```sql
LEFT JOIN kalshi.candlesticks kh ON km_home.ticker = kh.ticker
    AND ABS(EXTRACT(EPOCH FROM (kh.period_ts - ewd.snapshot_ts))) <= 60
...
SELECT DISTINCT ON (game_id, snapshot_ts) ...  -- Drops sequence_numbers!
```

**After** (CORRECT - one row per ESPN snapshot):
```sql
LEFT JOIN LATERAL (
    SELECT c.*
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
    WHERE mwg.espn_event_id = ewd.game_id
      AND mwg.kalshi_team_side = 'home'
      AND c.yes_bid_close IS NOT NULL
      AND c.yes_ask_close IS NOT NULL
      -- Range query for better index usage (instead of ABS() which scans more rows)
      AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                          AND ewd.snapshot_ts + INTERVAL '60 seconds'
    ORDER BY 
      ABS(EXTRACT(EPOCH FROM (c.period_ts - ewd.snapshot_ts))),
      c.period_ts DESC  -- Tie-breaker: prefer later timestamp if equally close
    LIMIT 1
) kh ON true
```

**Benefits**:
- ✅ No row explosion (LATERAL + LIMIT 1 = one row per ESPN snapshot)
- ✅ Preserves all `sequence_number` values (no DISTINCT ON dropping rows)
- ✅ Finds closest candlestick (ORDER BY ABS(time_diff), not DESC)
- ✅ Deterministic tie-breaking (c.period_ts DESC if equally close)
- ✅ Better index usage (BETWEEN range query instead of ABS() in WHERE clause)
- ✅ Much faster (avoids temp file spills)
- ✅ Requires indexes on `(ticker, period_ts)` and `(espn_event_id, kalshi_team_side, ticker)` for performance

### 3. Add season_label to Window Partitions (Safety Fix)

**Before**:
```sql
PARTITION BY ewi.game_id
```

**After**:
```sql
PARTITION BY ewi.season_label, ewi.game_id
```

**Benefit**: Ensures deterministic lag calculations even if game_id could theoretically repeat across seasons.

### 4. Remove Unnecessary ORDER BY (Performance Fix)

**Before**:
```sql
ORDER BY ewd.season_label, ewd.game_id, ewd.sequence_number, ewd.snapshot_ts;
```

**After**: Removed (ORDER BY in CREATE MATERIALIZED VIEW doesn't guarantee storage order and adds unnecessary cost)

---

## Expected Impact

- **Before**: 
  - Games without Kalshi markets were included, then filtered out in Python (wasteful)
  - Row explosion from non-LATERAL joins caused temp file spills (20GB+)
  - DISTINCT ON dropped rows when multiple sequence_numbers had same timestamp
  
- **After**: 
  - Only games with Kalshi markets **that have candlestick data** are included
  - LATERAL joins prevent row explosion (one row per ESPN snapshot)
  - All sequence_numbers preserved (no data loss)
  - Closest candlestick selected (correct alignment)
  
- **Result**: 
  - Smaller dataset (only games we can actually use)
  - Much faster queries (no temp file spills, especially with work_mem set)
  - Correct alignment (no dropped rows, closest candlestick selected)
  - Proper indexing for LATERAL joins (fast lookups)
  - Matches old `get_aligned_data` behavior

## Important Notes

### Home/Away Market Behavior

The SQL stores home and away markets **separately** (no fallback logic). If you need "home preferred, away fallback" behavior, you would need to add COALESCE logic like:

```sql
COALESCE(kh.kalshi_home_mid_price, ka.kalshi_away_mid_price) AS kalshi_home_mid_price
```

The current implementation stores both independently, which gives you more flexibility but requires you to handle fallback in your application code if needed.

---

## Performance Optimization

**Step 1 includes critical performance optimizations**:
- `SET work_mem = '512MB'` - Prevents temp file spills (can turn 45-60 min builds into a few minutes)
- Indexes on `(ticker, period_ts)` and `(espn_event_id, kalshi_team_side, ticker)` - Makes LATERAL joins fast
- Index on `(game_id, event_id)` in `prob_event_state` - Speeds up ESPN join (happens on every row)

**Important**: Run Step 1 BEFORE Step 3 (CREATE MATERIALIZED VIEW) for best performance.

## Verification

After running the SQL, verify the fix:

```sql
-- Check that games without Kalshi markets are excluded
SELECT COUNT(DISTINCT game_id) 
FROM derived.snapshot_features_v1;

-- Should match (using same EXISTS filter as the view for consistency):
SELECT COUNT(DISTINCT mwg.espn_event_id)
FROM kalshi.markets_with_games mwg
WHERE mwg.espn_event_id IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM kalshi.candlesticks c
    WHERE c.ticker = mwg.ticker
      AND c.yes_bid_close IS NOT NULL
      AND c.yes_ask_close IS NOT NULL
  );
```

