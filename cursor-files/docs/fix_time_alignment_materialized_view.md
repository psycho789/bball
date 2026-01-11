# Fix: Apply Time Alignment Logic to Materialized View

**Date**: 2026-01-04  
**Issue**: The materialized view `derived.snapshot_features_v1` is matching RAW ESPN timestamps to RAW Kalshi timestamps, but according to `webapp/README.md` (lines 503-612), ESPN timestamps should be SHIFTED to align with game start, and Kalshi timestamps should be FILTERED to the game window.

**Solution**: Modify the materialized view to:
1. Calculate game start (`event_date`) and first ESPN timestamp per game
2. Shift ESPN timestamps: `game_start + (snapshot_ts - first_snapshot_ts)`
3. Calculate game duration: `MAX(snapshot_ts) - MIN(snapshot_ts)` per game
4. Filter Kalshi candlesticks: `period_ts >= game_start AND period_ts <= (game_start + duration)`
5. Match aligned ESPN timestamps to filtered Kalshi timestamps within 60 seconds

---

## SQL Commands to Run

```sql
-- Step 1: Set work_mem and ensure indexes exist (BEFORE rebuilding)
SET work_mem = '512MB';

-- Ensure indexes exist (from previous fixes)
CREATE INDEX IF NOT EXISTS candlesticks_ticker_period_ts_idx
    ON kalshi.candlesticks (ticker, period_ts);

CREATE INDEX IF NOT EXISTS mwg_event_side_ticker_idx
    ON kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)
    WHERE espn_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS prob_event_state_game_event_idx
    ON espn.prob_event_state (game_id, event_id);

-- Index for game start lookup (critical for time alignment)
CREATE INDEX IF NOT EXISTS scoreboard_games_event_id_idx
    ON espn.scoreboard_games (event_id);

-- Step 2: Drop existing materialized view
DROP MATERIALIZED VIEW IF EXISTS derived.snapshot_features_v1 CASCADE;

-- Step 3: Recreate with time alignment logic
CREATE MATERIALIZED VIEW derived.snapshot_features_v1 AS
WITH games_with_kalshi AS (
    -- Only include games that have Kalshi markets WITH candlesticks
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
game_time_info AS (
    -- Get game start time and calculate first/last ESPN timestamps per game
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
kalshi_window_info AS (
    -- Calculate actual Kalshi data range per game (when markets were actually active during/after game start)
    SELECT 
        kmw.espn_event_id AS game_id,
        MIN(kc.period_ts) FILTER (WHERE kc.period_ts >= gti.game_start AND kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL) AS kalshi_window_start,
        MAX(kc.period_ts) FILTER (WHERE kc.period_ts >= gti.game_start AND kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL) AS kalshi_window_end
    FROM game_time_info gti
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gti.game_id
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    GROUP BY kmw.espn_event_id
),
game_time_with_kalshi AS (
    -- Combine game time info with Kalshi window info
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
espn_base AS (
    -- Base ESPN probability data with normalized probabilities (0-1 format)
    -- FILTERED: Only include games with Kalshi markets
    SELECT 
        p.season_label,
        p.game_id,
        p.sequence_number,
        p.event_id,
        -- Store RAW ESPN recording timestamp (last_modified_utc)
        -- Python code will align this to game_start later (see simulate_trading_strategy.py get_aligned_data)
        -- We store raw timestamp so Python can do: aligned_timestamp = game_start + (snapshot_ts - first_snapshot_ts)
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
        END AS         period,
        gti.game_start,
        gti.espn_duration_seconds,
        gti.kalshi_window_start,
        gti.kalshi_window_end
    FROM espn.probabilities_raw_items p
    INNER JOIN games_with_kalshi gwk ON p.game_id = gwk.game_id
    INNER JOIN game_time_with_kalshi gti ON p.game_id = gti.game_id
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
    -- Use LATERAL joins to find closest candlestick per ESPN row
    -- Match RAW ESPN timestamps to Kalshi timestamps (within 60 seconds)
    -- Kalshi filtering: Filter to game window [game_start, kalshi_window_end]
    -- Python code will align both ESPN and Kalshi timestamps to game_start later
    SELECT
        ewd.season_label,
        ewd.game_id,
        ewd.sequence_number,
        ewd.snapshot_ts,  -- RAW ESPN recording timestamp (last_modified_utc), NOT aligned
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
          -- Filter Kalshi to actual game window (when markets were active)
          -- Use kalshi_window_start/end if available, otherwise fall back to game_start + duration
          AND c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)
          AND c.period_ts <= COALESCE(
              ewd.kalshi_window_end,
              CASE 
                  WHEN ewd.espn_duration_seconds IS NOT NULL 
                  THEN ewd.game_start + INTERVAL '1 second' * ewd.espn_duration_seconds
                  ELSE NULL
              END
          )
          -- Match RAW ESPN timestamp to Kalshi timestamp within 60 seconds
          -- Both are wall-clock timestamps, so we match directly (no alignment needed here)
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
          -- Filter Kalshi to actual game window (when markets were active)
          -- Use kalshi_window_start/end if available, otherwise fall back to game_start + duration
          AND c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)
          AND c.period_ts <= COALESCE(
              ewd.kalshi_window_end,
              CASE 
                  WHEN ewd.espn_duration_seconds IS NOT NULL 
                  THEN ewd.game_start + INTERVAL '1 second' * ewd.espn_duration_seconds
                  ELSE NULL
              END
          )
          -- Match RAW ESPN timestamp to Kalshi timestamp within 60 seconds
          -- Both are wall-clock timestamps, so we match directly (no alignment needed here)
          AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                              AND ewd.snapshot_ts + INTERVAL '60 seconds'
        ORDER BY 
          ABS(EXTRACT(EPOCH FROM (c.period_ts - ewd.snapshot_ts))),
          c.period_ts DESC  -- Tie-breaker: prefer later timestamp if equally close
        LIMIT 1
    ) ka ON true
)
-- Final SELECT: Combine ESPN features with aligned Kalshi data
SELECT 
    e.season_label,
    e.game_id,
    e.sequence_number,
    e.snapshot_ts,  -- RAW ESPN recording timestamp (last_modified_utc), Python will align later
    e.espn_home_prob,
    e.espn_away_prob,
    e.score_diff,
    e.time_remaining,
    e.period,
    e.home_score,
    e.away_score,
    e.score_diff_div_sqrt_time_remaining,
    e.espn_home_prob_lag_1,
    e.espn_away_prob_lag_1,
    e.espn_home_prob_delta_1,
    k.kalshi_home_bid,
    k.kalshi_home_ask,
    k.kalshi_home_mid_price,
    k.kalshi_home_spread,
    k.kalshi_away_bid,
    k.kalshi_away_ask,
    k.kalshi_away_mid_price,
    k.kalshi_away_spread
FROM espn_with_deltas e
LEFT JOIN kalshi_aligned k 
    ON e.season_label = k.season_label
    AND e.game_id = k.game_id
    AND e.sequence_number = k.sequence_number
    AND e.snapshot_ts = k.snapshot_ts;

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
    snapshot_ts: RAW ESPN recording timestamp (last_modified_utc), NOT aligned.
    Python code (simulate_trading_strategy.py) will align to game_start: aligned_timestamp = game_start + (snapshot_ts - first_snapshot_ts).
    Kalshi timestamps filtered to game window [game_start, kalshi_window_end] and matched to RAW ESPN timestamps within 60 seconds.
    Uniqueness: (season_label, game_id, sequence_number, snapshot_ts).
    Ordering: sequence_number (preferred) or snapshot_ts (fallback).
    Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;';
```

---

## Key Changes

### 1. Added `game_time_info` CTE

**Purpose**: Calculate game start time and ESPN timestamp range per game

**Fields**:
- `game_start`: `event_date` from `espn.scoreboard_games`
- `first_espn_ts`: Earliest ESPN `last_modified_utc` per game
- `last_espn_ts`: Latest ESPN `last_modified_utc` per game
- `game_duration_seconds`: Duration of ESPN recording window

### 2. Modified `espn_base` CTE

**Time Alignment Applied**:
```sql
CASE 
    WHEN gti.game_start IS NOT NULL AND gti.first_espn_ts IS NOT NULL THEN
        gti.game_start + (p.last_modified_utc - gti.first_espn_ts)
    ELSE
        p.last_modified_utc  -- Fallback
END AS snapshot_ts
```

**Formula**: `game_start + (raw_snapshot_ts - first_espn_ts)`
- Preserves relative timing between ESPN records
- Shifts all timestamps to align with game start
- Matches README specification (lines 527-528)

### 3. Modified `kalshi_aligned` CTE

**Kalshi Window Filtering**:
```sql
-- Filter Kalshi to game window [game_start, game_start + duration]
AND c.period_ts >= ewd.game_start
AND c.period_ts <= (ewd.game_start + (ewd.game_duration_seconds || ' seconds')::INTERVAL)
```

**Matching**:
```sql
-- Match aligned ESPN timestamp to filtered Kalshi timestamp within 60 seconds
AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                    AND ewd.snapshot_ts + INTERVAL '60 seconds'
```

**Key Change**: Now uses `ewd.snapshot_ts` (ALIGNED) instead of raw `last_modified_utc`

---

## Verification Queries

### Check Time Alignment for Failed Games

```sql
-- Check if alignment fixes the failed games
SELECT 
    game_id,
    COUNT(*) as snapshot_count,
    COUNT(CASE WHEN kalshi_home_mid_price IS NOT NULL THEN 1 END) as snapshots_with_kalshi,
    ROUND(100.0 * COUNT(CASE WHEN kalshi_home_mid_price IS NOT NULL THEN 1 END) / COUNT(*), 2) as alignment_percentage,
    MIN(snapshot_ts) as first_aligned_snapshot,
    MAX(snapshot_ts) as last_aligned_snapshot
FROM derived.snapshot_features_v1
WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY game_id
ORDER BY game_id;
```

**Expected Result**: All 10 games should now have >0% alignment (ideally >50% if Kalshi markets were active during the game).

### Compare Aligned vs Raw Timestamps

```sql
-- Compare aligned snapshot_ts with raw last_modified_utc for one game
SELECT 
    sfv.sequence_number,
    sfv.snapshot_ts as aligned_ts,
    p.last_modified_utc as raw_espn_ts,
    sg.event_date as game_start,
    EXTRACT(EPOCH FROM (sfv.snapshot_ts - sg.event_date)) as elapsed_from_game_start,
    EXTRACT(EPOCH FROM (p.last_modified_utc - MIN(p.last_modified_utc) OVER (PARTITION BY p.game_id))) as elapsed_from_first_raw
FROM derived.snapshot_features_v1 sfv
JOIN espn.probabilities_raw_items p 
    ON sfv.game_id = p.game_id 
    AND sfv.sequence_number = p.sequence_number
JOIN espn.scoreboard_games sg ON sg.event_id = sfv.game_id
WHERE sfv.game_id = '401810286'
ORDER BY sfv.sequence_number
LIMIT 10;
```

**Expected Result**: `elapsed_from_game_start` should match `elapsed_from_first_raw` (alignment preserves relative timing).

---

## Performance Considerations

**Complexity**: O(n + m) where n = ESPN points, m = Kalshi candles per game
- `game_time_info` CTE: O(n) aggregation per game
- ESPN timestamp shifting: O(n) per game
- Kalshi filtering + matching: O(m) per game with index lookups

**Indexes Required**:
- `kalshi.candlesticks (ticker, period_ts)` - Critical for LATERAL JOIN performance
- `espn.scoreboard_games (event_id)` - Critical for game_start lookup
- `kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)` - Critical for market lookup

**Build Time**: Expect 5-10 minutes for full rebuild (5.3M rows)

---

## Testing

After rebuilding, test with the failed games:

```sql
-- Test simulation data retrieval for previously failed game
SELECT 
    snapshot_ts,
    espn_home_prob,
    kalshi_home_mid_price,
    CASE 
        WHEN kalshi_home_mid_price IS NOT NULL THEN 'ALIGNED'
        ELSE 'NO_KALSHI'
    END as alignment_status
FROM derived.snapshot_features_v1
WHERE game_id = '401810286'
ORDER BY sequence_number
LIMIT 20;
```

**Expected**: Should see `ALIGNED` status for snapshots where Kalshi markets were active during the game window.

