```sql

-- ============================================================================
-- MATERIALIZED VIEW: derived.snapshot_features_v1
-- ============================================================================
-- Purpose: Creates a canonical dataset that aligns ESPN win probability data
--          with Kalshi prediction market prices for trading simulation.
-- 
-- Key Innovation: Uses ALIGNED timestamps to match ESPN and Kalshi data
--                 on the same game timeline, not raw server timestamps.
--
-- Alignment Formula: aligned_espn_ts = game_start + (last_modified_utc - first_last_modified_utc)
--                    This shifts ESPN's server recording time to game time,
--                    matching how Kalshi timestamps work (game time).
-- ============================================================================

-- Step 1: Set work_mem and ensure indexes exist (BEFORE rebuilding)
-- ----------------------------------------------------------------------------
-- work_mem: Increases memory available for sorting/hashing operations during view creation
--           This helps with the complex CTEs and LATERAL joins that follow
SET work_mem = '512MB';

-- Ensure indexes exist (from previous fixes)
-- These indexes are critical for performance of the materialized view queries

-- Index on candlesticks: Speeds up lookups by ticker and timestamp
-- Used heavily in kalshi_aligned CTE when matching Kalshi data to ESPN snapshots
CREATE INDEX IF NOT EXISTS candlesticks_ticker_period_ts_idx
    ON kalshi.candlesticks (ticker, period_ts);

-- Index on markets_with_games: Speeds up finding Kalshi markets for ESPN games
-- Used to join markets to games and filter by team side (home/away)
CREATE INDEX IF NOT EXISTS mwg_event_side_ticker_idx
    ON kalshi.markets_with_games (espn_event_id, kalshi_team_side, ticker)
    WHERE espn_event_id IS NOT NULL;  -- Partial index: only index rows with espn_event_id

-- Index on prob_event_state: Speeds up joining ESPN probability events with game state
-- Used in espn_base CTE to get score, time_remaining, etc.
CREATE INDEX IF NOT EXISTS prob_event_state_game_event_idx
    ON espn.prob_event_state (game_id, event_id);

-- Index on scoreboard_games: Speeds up lookups by event_id
-- Used in game_time_info CTE to get game start times
CREATE INDEX IF NOT EXISTS scoreboard_games_event_id_idx
    ON espn.scoreboard_games (event_id);

-- Step 2: Drop existing materialized view
-- ----------------------------------------------------------------------------
-- CASCADE: Also drops any dependent objects (like indexes) automatically
-- This ensures a clean rebuild
DROP MATERIALIZED VIEW IF EXISTS derived.snapshot_features_v1 CASCADE;

-- Step 3: Recreate with FIXED time alignment logic
-- ----------------------------------------------------------------------------
-- KEY FIX: Match Kalshi period_ts to ALIGNED ESPN timestamps, not raw last_modified_utc
-- Alignment formula: aligned_ts = game_start + (last_modified_utc - first_last_modified_utc)
-- This matches the logic in probabilities.py

CREATE MATERIALIZED VIEW derived.snapshot_features_v1 AS

-- ============================================================================
-- CTE 1: games_with_kalshi
-- ============================================================================
-- Purpose: Filter to only games that have BOTH:
--          1. A Kalshi market mapped to the ESPN game
--          2. Actual candlestick data (not just market metadata)
--
-- Why: We only want games where we can actually match Kalshi prices to ESPN probabilities
--      Games without candlestick data can't be used for simulation
WITH games_with_kalshi AS (
    -- DISTINCT: Each game may have multiple markets (home/away), we only need game_id once
    SELECT DISTINCT mwg.espn_event_id AS game_id
    FROM kalshi.markets_with_games mwg
    WHERE mwg.espn_event_id IS NOT NULL  -- Only games mapped to ESPN
      -- EXISTS subquery: Check that this market actually has candlestick data
      -- This ensures we're not including games where markets exist but no price data was collected
      AND EXISTS (
        SELECT 1  -- EXISTS only cares if rows exist, not the values
        FROM kalshi.candlesticks c
        WHERE c.ticker = mwg.ticker  -- Match by ticker (market identifier)
          AND c.yes_bid_close IS NOT NULL   -- Must have bid price
          AND c.yes_ask_close IS NOT NULL   -- Must have ask price
      )
),

-- ============================================================================
-- CTE 2: game_time_info
-- ============================================================================
-- Purpose: Calculate timing metadata for each game:
--          - Game start time (from scoreboard)
--          - First ESPN recording timestamp (for alignment calculation)
--          - Last ESPN recording timestamp
--          - ESPN data duration (how long ESPN was recording)
--
-- Why: We need these to align ESPN timestamps to game time
--      The alignment formula uses first_espn_ts to shift all timestamps
game_time_info AS (
    SELECT 
        sg.event_id AS game_id,                    -- ESPN game identifier
        sg.event_date AS game_start,               -- Official game start time (this is our anchor point)
        
        -- MIN: Find the earliest ESPN probability recording timestamp for this game
        -- This is the "first_espn_ts" used in alignment: aligned_ts = game_start + (ts - first_espn_ts)
        MIN(p.last_modified_utc) AS first_espn_ts,
        
        -- MAX: Find the latest ESPN probability recording timestamp
        -- Used to understand the full span of ESPN data
        MAX(p.last_modified_utc) AS last_espn_ts,
        
        -- Calculate ESPN data duration in seconds
        -- EXTRACT(EPOCH FROM ...): Converts interval to seconds
        -- This tells us how long ESPN was recording probabilities for this game
        EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER AS espn_duration_seconds
    
    FROM espn.scoreboard_games sg
    
    -- INNER JOIN: Only include games that have Kalshi data (from CTE 1)
    -- This filters out games without Kalshi markets early in the pipeline
    INNER JOIN games_with_kalshi gwk ON sg.event_id = gwk.game_id
    
    -- INNER JOIN: Get all ESPN probability recordings for these games
    -- We need this to calculate MIN/MAX timestamps
    INNER JOIN espn.probabilities_raw_items p ON p.game_id = sg.event_id
    
    WHERE sg.event_date IS NOT NULL  -- Must have a game start time
    
    -- GROUP BY: Aggregate all probability recordings per game
    -- This gives us one row per game with timing metadata
    GROUP BY sg.event_id, sg.event_date
),

-- ============================================================================
-- CTE 3: kalshi_window_info
-- ============================================================================
-- Purpose: Calculate the actual time window when Kalshi markets were active
--          for each game (when candlestick data exists during/after game start)
--
-- Why: Kalshi markets might start before game time or end after game time
--      We want to know the actual data window to filter efficiently
kalshi_window_info AS (
    SELECT 
        kmw.espn_event_id AS game_id,
        
        -- MIN with FILTER: Find earliest Kalshi candlestick timestamp
        -- FILTER clause: Only consider candlesticks that:
        --   - Are at or after game start (period_ts >= game_start)
        --   - Have valid bid/ask data (not NULL)
        -- This gives us when Kalshi data actually starts for this game
        MIN(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_start,
        
        -- MAX with FILTER: Find latest Kalshi candlestick timestamp
        -- Same filters as above - when Kalshi data actually ends
        MAX(kc.period_ts) FILTER (
            WHERE kc.period_ts >= gti.game_start 
              AND kc.yes_bid_close IS NOT NULL 
              AND kc.yes_ask_close IS NOT NULL
        ) AS kalshi_window_end
    
    FROM game_time_info gti  -- Use game timing from previous CTE
    
    -- JOIN: Get all Kalshi markets for these games
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gti.game_id
    
    -- JOIN: Get all candlesticks for these markets
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    
    -- GROUP BY: Aggregate per game (one game may have multiple markets/tickers)
    GROUP BY kmw.espn_event_id
),

-- ============================================================================
-- CTE 4: game_time_with_kalshi
-- ============================================================================
-- Purpose: Combine game timing info with Kalshi window info
--          Provides fallback logic if Kalshi window is missing
--
-- Why: Some games might not have Kalshi window calculated (no data)
--      We provide sensible defaults based on game start and ESPN duration
game_time_with_kalshi AS (
    SELECT 
        gti.*,  -- Include all columns from game_time_info
        
        -- COALESCE: Use Kalshi window start if available, else fall back to game start
        -- This ensures we always have a window start time
        COALESCE(kwi.kalshi_window_start, gti.game_start) AS kalshi_window_start,
        
        -- COALESCE with nested CASE: Complex fallback logic for window end
        COALESCE(
            kwi.kalshi_window_end,  -- First choice: actual Kalshi window end
            -- Second choice: Calculate from game start + ESPN duration
            CASE 
                WHEN gti.espn_duration_seconds IS NOT NULL 
                THEN gti.game_start + INTERVAL '1 second' * gti.espn_duration_seconds
                ELSE NULL  -- Last resort: NULL if we can't calculate
            END
        ) AS kalshi_window_end
    
    FROM game_time_info gti
    
    -- LEFT JOIN: Keep all games even if Kalshi window info is missing
    -- This allows fallback logic above to work
    LEFT JOIN kalshi_window_info kwi ON gti.game_id = kwi.game_id
),

-- ============================================================================
-- CTE 5: espn_base
-- ============================================================================
-- Purpose: Extract and normalize ESPN probability data
--          Includes game state (scores, time remaining, period)
--          Filters to only games with Kalshi data
--
-- Why: This is the foundation for all ESPN features
--      Normalization ensures probabilities are always 0-1 format
espn_base AS (
    SELECT 
        -- Game identifiers
        p.season_label,        -- Season (e.g., '2025-26')
        p.game_id,             -- ESPN game identifier
        p.sequence_number,     -- Ordering within game (for sorting)
        p.event_id,            -- ESPN event identifier
        
        -- Timestamp: Store RAW ESPN recording timestamp
        -- This is the server time when ESPN recorded the probability
        -- We'll align this to game time later when matching with Kalshi
        p.last_modified_utc AS snapshot_ts,
        
        -- Alignment anchor: First ESPN timestamp for this game
        -- Used in alignment formula: aligned_ts = game_start + (snapshot_ts - first_espn_ts)
        gti.first_espn_ts,
        
        -- Normalize home win probability to 0-1 range
        -- ESPN sometimes provides 0-100 format, sometimes 0-1 format
        -- This CASE ensures we always get 0-1
        CASE 
            WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0  -- Convert 0-100 to 0-1
            ELSE p.home_win_percentage  -- Already 0-1, use as-is
        END AS espn_home_prob,
        
        -- Normalize away win probability to 0-1 range (same logic as home)
        CASE 
            WHEN p.away_win_percentage > 1.0 THEN p.away_win_percentage / 100.0
            ELSE p.away_win_percentage
        END AS espn_away_prob,
        
        -- Game state from prob_event_state (score, time, etc.)
        e.point_differential AS score_diff,  -- Home score - away score
        e.time_remaining,                    -- Seconds remaining in game
        e.home_score,                        -- Current home team score
        e.away_score,                        -- Current away team score
        
        -- Calculate period (quarter) from time_remaining
        -- NBA games: Q1 = 0-12 min (0-720s), Q2 = 12-24 min (720-1440s), etc.
        -- This CASE maps time_remaining to period number
        CASE 
            WHEN e.time_remaining IS NULL THEN NULL
            WHEN e.time_remaining > 2160 THEN 1  -- Q1: > 36 minutes remaining
            WHEN e.time_remaining > 1440 THEN 2  -- Q2: > 24 minutes remaining
            WHEN e.time_remaining > 720 THEN 3   -- Q3: > 12 minutes remaining
            ELSE 4                                -- Q4: <= 12 minutes remaining
        END AS period,
        
        -- Include timing metadata from game_time_with_kalshi
        -- These are used later for filtering and alignment
        gti.game_start,                    -- Official game start time
        gti.espn_duration_seconds,         -- How long ESPN recorded data
        gti.kalshi_window_start,           -- When Kalshi data starts
        gti.kalshi_window_end              -- When Kalshi data ends
    
    FROM espn.probabilities_raw_items p
    
    -- INNER JOIN: Only include games that have Kalshi markets
    -- This filters early to avoid processing games we can't use
    INNER JOIN games_with_kalshi gwk ON p.game_id = gwk.game_id
    
    -- INNER JOIN: Get timing metadata for these games
    INNER JOIN game_time_with_kalshi gti ON p.game_id = gti.game_id
    
    -- LEFT JOIN: Get game state (scores, time remaining)
    -- LEFT because not all probability recordings have corresponding game state
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id      -- Match by game
        AND p.event_id = e.event_id   -- Match by event (specific moment in game)
),

-- ============================================================================
-- CTE 6: espn_with_interactions
-- ============================================================================
-- Purpose: Add derived features that capture interactions between variables
--          Specifically: score differential normalized by time remaining
--
-- Why: This feature captures "clutch" situations - a 10-point lead with 1 minute left
--      is very different from a 10-point lead with 10 minutes left
espn_with_interactions AS (
    SELECT 
        *,  -- Include all columns from espn_base
        
        -- Feature: Score differential divided by square root of time remaining
        -- Purpose: Normalizes score differential by game situation
        --          Large score diff early in game = less significant
        --          Small score diff late in game = very significant
        -- Formula: score_diff / sqrt(time_remaining + 1)
        -- The +1 prevents division by zero
        CASE 
            WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
                score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
            ELSE NULL  -- Can't calculate if time_remaining is missing or zero
        END AS score_diff_div_sqrt_time_remaining
    
    FROM espn_base
),

-- ============================================================================
-- CTE 7: espn_with_deltas
-- ============================================================================
-- Purpose: Add lagged features (previous values) and delta features (changes)
--          Uses window functions to look back at previous snapshots
--
-- Why: Trading strategies often use momentum/trend signals
--      These features capture how probabilities are changing over time
espn_with_deltas AS (
    SELECT 
        ewi.*,  -- Include all columns from espn_with_interactions
        
        -- LAG window function: Get home probability from previous snapshot
        -- OVER clause: Partition by game (each game is separate), order by sequence
        -- This gives us the previous value in the time series
        LAG(ewi.espn_home_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id  -- Separate window per game
            ORDER BY ewi.sequence_number, ewi.snapshot_ts  -- Order by time
        ) AS espn_home_prob_lag_1,
        
        -- LAG: Get away probability from previous snapshot (same logic)
        LAG(ewi.espn_away_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id
            ORDER BY ewi.sequence_number, ewi.snapshot_ts
        ) AS espn_away_prob_lag_1,
        
        -- Delta: Calculate change in home probability from previous snapshot
        -- Formula: current_prob - previous_prob
        -- Positive = probability increased (home team more likely to win)
        -- Negative = probability decreased (home team less likely to win)
        (ewi.espn_home_prob - LAG(ewi.espn_home_prob, 1) OVER (
            PARTITION BY ewi.season_label, ewi.game_id
            ORDER BY ewi.sequence_number, ewi.snapshot_ts
        )) AS espn_home_prob_delta_1
    
    FROM espn_with_interactions ewi
),

-- ============================================================================
-- CTE 8: kalshi_aligned
-- ============================================================================
-- Purpose: Match Kalshi prediction market prices to ESPN snapshots
--          Uses LATERAL joins to find the closest Kalshi candlestick for each ESPN snapshot
--          KEY FIX: Matches using ALIGNED ESPN timestamps, not raw timestamps
--
-- Why LATERAL joins: For each ESPN row, we need to find the closest Kalshi row
--                    LATERAL allows the subquery to reference columns from the outer query
--                    This enables per-row matching logic
kalshi_aligned AS (
    SELECT
        -- Game identifiers (from ESPN data)
        ewd.season_label,
        ewd.game_id,
        ewd.sequence_number,
        ewd.snapshot_ts,  -- RAW ESPN recording timestamp (stored for reference)
        
        -- Home market prices (from Kalshi candlestick)
        -- Kalshi stores prices as 0-100, we convert to 0-1 to match ESPN format
        (kh.yes_bid_close::NUMERIC / 100.0) AS kalshi_home_bid,      -- Buy price for home team win
        (kh.yes_ask_close::NUMERIC / 100.0) AS kalshi_home_ask,      -- Sell price for home team win
        ((kh.yes_bid_close::NUMERIC + kh.yes_ask_close::NUMERIC) / 200.0) AS kalshi_home_mid_price,  -- Midpoint (average)
        ((kh.yes_ask_close::NUMERIC - kh.yes_bid_close::NUMERIC) / 100.0) AS kalshi_home_spread,     -- Bid-ask spread
        
        -- Away market prices (converted to home probability space)
        -- Away market: "Will away team win?" (0-100)
        -- Home market: "Will home team win?" (0-100)
        -- Conversion: home_prob = 1 - away_prob
        -- For bid/ask: home_bid = 1 - away_ask, home_ask = 1 - away_bid (swap needed!)
        (1.0 - (ka.yes_ask_close::NUMERIC / 100.0)) AS kalshi_away_bid,      -- Convert away ask to home bid
        (1.0 - (ka.yes_bid_close::NUMERIC / 100.0)) AS kalshi_away_ask,      -- Convert away bid to home ask
        (1.0 - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0)) AS kalshi_away_mid_price,  -- Convert away mid to home mid
        ((ka.yes_ask_close::NUMERIC - ka.yes_bid_close::NUMERIC) / 100.0) AS kalshi_away_spread  -- Spread is same (absolute value)
    
    FROM espn_with_deltas ewd
    
    -- LATERAL JOIN: Find closest home market candlestick for this ESPN snapshot
    -- LATERAL allows the subquery to reference ewd.* columns from the outer query
    -- This runs once per ESPN row, finding the best matching Kalshi row
    LEFT JOIN LATERAL (
        SELECT c.*  -- Get all candlestick columns
        FROM kalshi.markets_with_games mwg
        JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
        WHERE mwg.espn_event_id = ewd.game_id           -- Match to same game
          AND mwg.kalshi_team_side = 'home'             -- Only home market
          AND c.yes_bid_close IS NOT NULL                -- Must have bid
          AND c.yes_ask_close IS NOT NULL                -- Must have ask
          
          -- Filter Kalshi to actual game window (when markets were active)
          -- This prevents matching to pre-game or post-game data
          AND c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)
          AND c.period_ts <= COALESCE(
              ewd.kalshi_window_end,
              -- Fallback: Calculate end from game start + duration
              CASE 
                  WHEN ewd.espn_duration_seconds IS NOT NULL 
                  THEN ewd.game_start + INTERVAL '1 second' * ewd.espn_duration_seconds
                  ELSE NULL
              END
          )
          
          -- ====================================================================
          -- KEY FIX: Match Kalshi period_ts to ALIGNED ESPN timestamp
          -- ====================================================================
          -- Problem: ESPN timestamps are server recording times (could be hours after game start)
          --          Kalshi timestamps are game times (when the game event actually happened)
          --          We need to align them to the same timeline
          --
          -- Solution: Calculate aligned ESPN timestamp:
          --          aligned_espn_ts = game_start + (snapshot_ts - first_espn_ts)
          --          This shifts ESPN from server time to game time
          --
          -- Example:
          --   game_start = 2025-10-11 23:00:00
          --   first_espn_ts = 2025-10-11 23:15:00  (ESPN started recording 15 min after game start)
          --   snapshot_ts = 2025-10-11 23:30:00     (This ESPN snapshot was recorded 30 min after game start)
          --   aligned_espn_ts = 23:00:00 + (23:30:00 - 23:15:00) = 23:00:00 + 15 min = 23:15:00 game time
          --
          -- Then match Kalshi period_ts within 60 seconds of this aligned timestamp
          AND c.period_ts BETWEEN 
              (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) - INTERVAL '60 seconds'  -- 60 sec before aligned time
              AND 
              (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) + INTERVAL '60 seconds'  -- 60 sec after aligned time
        
        ORDER BY 
          -- Find the closest Kalshi timestamp to the aligned ESPN timestamp
          -- ABS(EXTRACT(EPOCH FROM ...)): Calculate absolute difference in seconds
          -- Smaller difference = closer match = better alignment
          ABS(EXTRACT(EPOCH FROM (c.period_ts - (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts))))),
          c.period_ts DESC  -- Tie-breaker: if equally close, prefer later timestamp
        
        LIMIT 1  -- Only get the single closest match
    ) kh ON true  -- LEFT JOIN: Keep ESPN row even if no Kalshi match found
    
    -- LATERAL JOIN: Find closest away market candlestick (same logic as home)
    LEFT JOIN LATERAL (
        SELECT c.*
        FROM kalshi.markets_with_games mwg
        JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
        WHERE mwg.espn_event_id = ewd.game_id
          AND mwg.kalshi_team_side = 'away'  -- Only away market (different from home join above)
          AND c.yes_bid_close IS NOT NULL
          AND c.yes_ask_close IS NOT NULL
          
          -- Same window filtering as home market
          AND c.period_ts >= COALESCE(ewd.kalshi_window_start, ewd.game_start)
          AND c.period_ts <= COALESCE(
              ewd.kalshi_window_end,
              CASE 
                  WHEN ewd.espn_duration_seconds IS NOT NULL 
                  THEN ewd.game_start + INTERVAL '1 second' * ewd.espn_duration_seconds
                  ELSE NULL
              END
          )
          
          -- Same alignment logic as home market
          AND c.period_ts BETWEEN 
              (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) - INTERVAL '60 seconds'
              AND 
              (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) + INTERVAL '60 seconds'
        
        ORDER BY 
          ABS(EXTRACT(EPOCH FROM (c.period_ts - (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts))))),
          c.period_ts DESC
        LIMIT 1
    ) ka ON true  -- LEFT JOIN: Keep ESPN row even if no away market match found
)

-- ============================================================================
-- Final SELECT: Combine ESPN features with aligned Kalshi data
-- ============================================================================
-- Purpose: Join ESPN features (from espn_with_deltas) with Kalshi prices (from kalshi_aligned)
--          Creates the final canonical dataset with one row per ESPN snapshot
--
-- Result: Each row contains:
--         - ESPN probability data (home/away probabilities, scores, time, etc.)
--         - Kalshi market prices (bid/ask/mid for home and away markets)
--         - Derived features (deltas, interactions, etc.)
SELECT 
    -- Game identifiers
    e.season_label,           -- Season (e.g., '2025-26')
    e.game_id,                 -- ESPN game identifier
    e.sequence_number,         -- Ordering within game
    e.snapshot_ts,             -- RAW ESPN recording timestamp (for reference)
    
    -- ESPN probabilities (normalized to 0-1)
    e.espn_home_prob,          -- ESPN's probability that home team wins (0-1)
    e.espn_away_prob,          -- ESPN's probability that away team wins (0-1)
    
    -- Game state
    e.score_diff,              -- Point differential (home - away)
    e.time_remaining,          -- Seconds remaining in game
    e.period,                  -- Quarter (1-4)
    e.home_score,              -- Current home team score
    e.away_score,              -- Current away team score
    
    -- Derived ESPN features
    e.score_diff_div_sqrt_time_remaining,  -- Score diff normalized by time remaining
    e.espn_home_prob_lag_1,               -- Previous snapshot's home probability
    e.espn_away_prob_lag_1,               -- Previous snapshot's away probability
    e.espn_home_prob_delta_1,            -- Change in home probability from previous snapshot
    
    -- Kalshi home market prices (0-1 format)
    k.kalshi_home_bid,         -- Buy price for "home team wins" (0-1)
    k.kalshi_home_ask,         -- Sell price for "home team wins" (0-1)
    k.kalshi_home_mid_price,   -- Midpoint price (average of bid/ask)
    k.kalshi_home_spread,      -- Bid-ask spread (ask - bid)
    
    -- Kalshi away market prices (converted to home probability space, 0-1 format)
    k.kalshi_away_bid,         -- Buy price (converted from away market)
    k.kalshi_away_ask,         -- Sell price (converted from away market)
    k.kalshi_away_mid_price,   -- Midpoint price (converted from away market)
    k.kalshi_away_spread       -- Bid-ask spread (same as away market spread)

FROM espn_with_deltas e

-- LEFT JOIN: Match Kalshi data to ESPN snapshots
-- LEFT because we want to keep ESPN rows even if no Kalshi match found
-- This allows games with partial Kalshi coverage
LEFT JOIN kalshi_aligned k 
    ON e.season_label = k.season_label      -- Match by season
    AND e.game_id = k.game_id               -- Match by game
    AND e.sequence_number = k.sequence_number  -- Match by sequence (same snapshot)
    AND e.snapshot_ts = k.snapshot_ts;      -- Match by timestamp (same moment)

-- ============================================================================
-- Step 4: Recreate indexes on materialized view
-- ============================================================================
-- Purpose: Create indexes to speed up queries against the materialized view
--          These are critical for performance when querying the view

-- Unique index: Ensures no duplicate rows and speeds up exact lookups
-- Used when querying specific snapshots: WHERE game_id = X AND sequence_number = Y
CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshot_features_v1_pkey
    ON derived.snapshot_features_v1(season_label, game_id, sequence_number, snapshot_ts);

-- Index on game: Speeds up queries filtering by game_id
-- Used when getting all snapshots for a game: WHERE game_id = X ORDER BY sequence_number
CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_game
    ON derived.snapshot_features_v1(game_id, sequence_number);

-- Index on season+game: Speeds up queries filtering by both season and game
-- Used when querying: WHERE season_label = '2025-26' AND game_id = X
CREATE INDEX IF NOT EXISTS idx_snapshot_features_v1_season_game
    ON derived.snapshot_features_v1(season_label, game_id);

-- ============================================================================
-- Step 5: Update comment
-- ============================================================================
-- Purpose: Document the materialized view for future reference
--          Explains the key fix and how to refresh the view
COMMENT ON MATERIALIZED VIEW derived.snapshot_features_v1 IS 
'Canonical snapshot dataset for trading simulation.
KEY FIX (2026-01-05): Now matches Kalshi period_ts to ALIGNED ESPN timestamps.
Alignment: aligned_espn_ts = game_start + (last_modified_utc - first_last_modified_utc)
This mirrors probabilities.py logic and ensures ESPN and Kalshi are on the same game timeline.
snapshot_ts column: Stores RAW ESPN last_modified_utc (for reference).
Kalshi matching: period_ts within 60 seconds of ALIGNED ESPN timestamp.
Uniqueness: (season_label, game_id, sequence_number, snapshot_ts).
Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;';

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- To refresh the materialized view after new data is loaded:
--   REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;
--
-- To query the view:
--   SELECT * FROM derived.snapshot_features_v1 
--   WHERE game_id = '401705759' AND season_label = '2025-26'
--   ORDER BY sequence_number;
--
-- The view contains one row per ESPN probability snapshot, with matched Kalshi prices.
-- If a snapshot has no matching Kalshi data, Kalshi columns will be NULL.
-- ============================================================================

```
