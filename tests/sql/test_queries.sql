-- ============================================
-- EXACT QUERIES FROM get_aligned_data() 
-- Game ID: 401810267
-- Copy and paste these directly into psql
-- ============================================

-- Query 1: ESPN Check
SELECT COUNT(*) 
FROM espn.probabilities_raw_items 
WHERE game_id = '401810267';

-- Query 2: Game Info (with JOINs)
SELECT 
    sg.event_date as game_start,
    EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as duration_seconds,
    MAX(pe.final_winning_team) as winner,
    MAX(pe.home_score) as final_home_score,
    MAX(pe.away_score) as final_away_score
FROM espn.probabilities_raw_items p
LEFT JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
LEFT JOIN espn.prob_event_state pe ON p.game_id = pe.game_id
WHERE p.game_id = '401810267'
GROUP BY sg.event_date;

-- Query 3: ESPN Data
SELECT 
    p.last_modified_utc,
    p.home_win_percentage,
    p.away_win_percentage
FROM espn.probabilities_raw_items p
WHERE p.game_id = '401810267'
ORDER BY p.last_modified_utc;

-- Query 4: Kalshi Candlestick Data (OPTIMIZED - bounds computed first, then join)
WITH p_bounds AS (
    SELECT
        game_id,
        MIN(last_modified_utc) AS min_ts,
        MAX(last_modified_utc) AS max_ts
    FROM espn.probabilities_raw_items
    WHERE game_id = '401810267'
    GROUP BY game_id
),
espn_game_info AS (
    SELECT
        pb.game_id,
        COALESCE(sg.event_date, pb.min_ts) AS game_start,
        EXTRACT(EPOCH FROM (pb.max_ts - pb.min_ts))::INTEGER AS espn_duration_seconds
    FROM p_bounds pb
    LEFT JOIN espn.scoreboard_games sg ON sg.event_id = pb.game_id
),
game_markets AS (
    SELECT DISTINCT ON (kmw.ticker)
        kmw.ticker,
        kmw.kalshi_team_side,
        egi.game_start,
        egi.espn_duration_seconds
    FROM kalshi.markets_with_games kmw
    CROSS JOIN espn_game_info egi
    WHERE kmw.espn_event_id = '401810267'
      AND kmw.kalshi_team_side IS NOT NULL
    ORDER BY kmw.ticker, kmw.snapshot_id DESC
)
SELECT 
    gm.kalshi_team_side,
    c.period_ts,
    c.price_close,
    c.yes_bid_close,
    c.yes_ask_close
FROM kalshi.candlesticks c
JOIN game_markets gm ON c.ticker = gm.ticker
WHERE (
    c.price_close IS NOT NULL 
    OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL)
)
AND c.period_ts >= gm.game_start
AND c.period_ts <= (gm.game_start + (gm.espn_duration_seconds || ' seconds')::INTERVAL)
ORDER BY gm.kalshi_team_side, c.period_ts;

-- Query 5: Markets Query (if using trade data)
SELECT DISTINCT ON (kmw.ticker)
    kmw.ticker,
    kmw.kalshi_team_side
FROM kalshi.markets_with_games kmw
WHERE kmw.espn_event_id = '401810267'
  AND kmw.kalshi_team_side IS NOT NULL
ORDER BY kmw.ticker, kmw.snapshot_id DESC;

-- Query 6: Trades Fetch (if using trade data)
-- NOTE: Replace TICKER_VALUE with actual ticker from Query 5
-- Replace TIMESTAMP values with actual game start/end times
-- Example:
-- SELECT 
--     created_time,
--     yes_price,
--     no_price,
--     count,
--     price,
--     taker_side,
--     trade_id
-- FROM kalshi.trades
-- WHERE ticker = 'KXNBAGAME-25NOV30OKCPOR-POR'
--   AND created_time >= '2025-11-30 00:00:00+00'::timestamptz
--   AND created_time < '2025-11-30 03:00:00+00'::timestamptz
-- ORDER BY created_time ASC;

-- ============================================
-- EXPLAIN ANALYZE VERSIONS (to see query plan)
-- ============================================

-- EXPLAIN ANALYZE for Query 4 (OPTIMIZED):
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH p_bounds AS (
    SELECT
        game_id,
        MIN(last_modified_utc) AS min_ts,
        MAX(last_modified_utc) AS max_ts
    FROM espn.probabilities_raw_items
    WHERE game_id = '401810267'
    GROUP BY game_id
),
espn_game_info AS (
    SELECT
        pb.game_id,
        COALESCE(sg.event_date, pb.min_ts) AS game_start,
        EXTRACT(EPOCH FROM (pb.max_ts - pb.min_ts))::INTEGER AS espn_duration_seconds
    FROM p_bounds pb
    LEFT JOIN espn.scoreboard_games sg ON sg.event_id = pb.game_id
),
game_markets AS (
    SELECT DISTINCT ON (kmw.ticker)
        kmw.ticker,
        kmw.kalshi_team_side,
        egi.game_start,
        egi.espn_duration_seconds
    FROM kalshi.markets_with_games kmw
    CROSS JOIN espn_game_info egi
    WHERE kmw.espn_event_id = '401810267'
      AND kmw.kalshi_team_side IS NOT NULL
    ORDER BY kmw.ticker, kmw.snapshot_id DESC
)
SELECT 
    gm.kalshi_team_side,
    c.period_ts,
    c.price_close,
    c.yes_bid_close,
    c.yes_ask_close
FROM kalshi.candlesticks c
JOIN game_markets gm ON c.ticker = gm.ticker
WHERE (
    c.price_close IS NOT NULL 
    OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL)
)
AND c.period_ts >= gm.game_start
AND c.period_ts <= (gm.game_start + (gm.espn_duration_seconds || ' seconds')::INTERVAL)
ORDER BY gm.kalshi_team_side, c.period_ts;

