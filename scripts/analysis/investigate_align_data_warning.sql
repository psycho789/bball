-- Investigate ALIGN_DATA warning for game 401809981
-- This query checks why home + away prices sum to ~1.0, suggesting away price might not be converted

-- 1. Check the canonical view data for the problematic game
SELECT 
    sequence_number,
    snapshot_ts,
    kalshi_home_mid_price,
    kalshi_away_mid_price,
    (kalshi_home_mid_price + kalshi_away_mid_price) AS sum_home_away,
    ABS(kalshi_home_mid_price - kalshi_away_mid_price) AS diff_home_away,
    ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) AS sum_minus_one,
    CASE 
        WHEN ABS(kalshi_home_mid_price - kalshi_away_mid_price) < 0.05 THEN '✓ Home≈Away (correct)'
        WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05 THEN '⚠️ WARNING: Sum≈1.0 (away not converted?)'
        ELSE '? Other pattern'
    END AS status
FROM derived.snapshot_features_v1
WHERE game_id = '401809981'
  AND season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
ORDER BY sequence_number
LIMIT 20;

-- 2. Count how many snapshots have the warning pattern
SELECT 
    COUNT(*) AS total_snapshots,
    COUNT(CASE WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05 THEN 1 END) AS warning_count,
    ROUND(100.0 * COUNT(CASE WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05 THEN 1 END) / COUNT(*), 1) AS warning_percentage
FROM derived.snapshot_features_v1
WHERE game_id = '401809981'
  AND season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL;

-- 3. Check raw Kalshi candlestick data to see what's actually stored
SELECT 
    c.ticker,
    mwg.kalshi_team_side,
    c.period_ts,
    c.yes_bid_close,
    c.yes_ask_close,
    (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0 AS raw_mid_price,
    CASE 
        WHEN mwg.kalshi_team_side = 'home' THEN (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0
        WHEN mwg.kalshi_team_side = 'away' THEN 1.0 - ((c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0)
        ELSE NULL
    END AS expected_converted_price
FROM kalshi.candlesticks c
JOIN kalshi.markets_with_games mwg ON c.ticker = mwg.ticker
WHERE mwg.espn_event_id = '401809981'
ORDER BY mwg.kalshi_team_side, c.period_ts
LIMIT 20;

-- 3b. Show the actual problematic snapshots (where sum ≈ 1.0)
SELECT 
    sequence_number,
    snapshot_ts,
    kalshi_home_mid_price,
    kalshi_away_mid_price,
    (kalshi_home_mid_price + kalshi_away_mid_price) AS sum_home_away,
    ABS(kalshi_home_mid_price - kalshi_away_mid_price) AS diff_home_away,
    ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) AS sum_minus_one
FROM derived.snapshot_features_v1
WHERE game_id = '401809981'
  AND season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
  AND ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
ORDER BY sequence_number
LIMIT 20;

-- 4. Check if this pattern appears in other games
SELECT 
    game_id,
    COUNT(*) AS snapshot_count,
    COUNT(CASE 
        WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
        THEN 1 
    END) AS warning_count,
    ROUND(100.0 * COUNT(CASE 
        WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
        THEN 1 
    END) / COUNT(*), 1) AS warning_percentage
FROM derived.snapshot_features_v1
WHERE season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
GROUP BY game_id
HAVING COUNT(CASE 
    WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
    THEN 1 
END) > 0
ORDER BY warning_count DESC
LIMIT 10;

-- 5. Compare view output with raw data for problematic snapshots
-- This will show if the view is correctly converting away prices
-- IMPORTANT: Uses the same alignment formula as the view: aligned_ts = game_start + (snapshot_ts - first_espn_ts)
SELECT 
    sf.sequence_number,
    sf.snapshot_ts AS raw_snapshot_ts,
    gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) AS aligned_ts,
    sf.kalshi_home_mid_price AS view_home,
    sf.kalshi_away_mid_price AS view_away,
    (sf.kalshi_home_mid_price + sf.kalshi_away_mid_price) AS view_sum,
    -- Get raw home market data (using ALIGNED timestamp, matching view logic)
    (kh.yes_bid_close::NUMERIC + kh.yes_ask_close::NUMERIC) / 200.0 AS raw_home_mid,
    -- Get raw away market data and expected conversion
    (ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0 AS raw_away_mid,
    1.0 - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0) AS expected_away_converted,
    -- Check if view matches expected
    CASE 
        WHEN ka.yes_bid_close IS NULL OR ka.yes_ask_close IS NULL THEN '❌ No raw data found'
        WHEN ABS(sf.kalshi_away_mid_price - (1.0 - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0))) < 0.01 
        THEN '✓ Converted correctly'
        WHEN ABS(sf.kalshi_away_mid_price - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0)) < 0.01
        THEN '⚠️ NOT CONVERTED (using raw away)'
        ELSE '? Mismatch'
    END AS conversion_status
FROM derived.snapshot_features_v1 sf
-- Get game_start and first_espn_ts to calculate aligned timestamp (same as view does)
JOIN (
    SELECT DISTINCT 
        p.game_id,
        sg.event_date AS game_start,
        MIN(p.last_modified_utc) OVER (PARTITION BY p.game_id) AS first_espn_ts
    FROM espn.probabilities_raw_items p
    JOIN espn.scoreboard_games sg ON sg.event_id = p.game_id
    WHERE p.season_label = '2025-26'
) gti ON gti.game_id = sf.game_id
-- Get home market data using ALIGNED timestamp (matching view's LATERAL JOIN logic)
LEFT JOIN LATERAL (
    SELECT c.yes_bid_close, c.yes_ask_close
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
    WHERE mwg.espn_event_id = sf.game_id
      AND mwg.kalshi_team_side = 'home'
      AND c.yes_bid_close IS NOT NULL
      AND c.yes_ask_close IS NOT NULL
      -- Use ALIGNED timestamp (same formula as view): game_start + (snapshot_ts - first_espn_ts)
      AND c.period_ts >= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) - INTERVAL '60 seconds')
      AND c.period_ts <= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) + INTERVAL '60 seconds')
    ORDER BY ABS(EXTRACT(EPOCH FROM (c.period_ts - (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts)))))
    LIMIT 1
) kh ON true
-- Get away market data using ALIGNED timestamp (matching view's LATERAL JOIN logic)
LEFT JOIN LATERAL (
    SELECT c.yes_bid_close, c.yes_ask_close
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
    WHERE mwg.espn_event_id = sf.game_id
      AND mwg.kalshi_team_side = 'away'
      AND c.yes_bid_close IS NOT NULL
      AND c.yes_ask_close IS NOT NULL
      -- Use ALIGNED timestamp (same formula as view): game_start + (snapshot_ts - first_espn_ts)
      AND c.period_ts >= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) - INTERVAL '60 seconds')
      AND c.period_ts <= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) + INTERVAL '60 seconds')
    ORDER BY ABS(EXTRACT(EPOCH FROM (c.period_ts - (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts)))))
    LIMIT 1
) ka ON true
WHERE sf.game_id = '401809981'
  AND sf.season_label = '2025-26'
  AND sf.kalshi_home_mid_price IS NOT NULL
  AND sf.kalshi_away_mid_price IS NOT NULL
  AND ABS((sf.kalshi_home_mid_price + sf.kalshi_away_mid_price) - 1.0) < 0.05
ORDER BY sf.sequence_number
LIMIT 10;

-- 6. Get the actual view definition to see the conversion logic
-- Save to a file for easier inspection
\o /tmp/snapshot_features_v1_view_definition.sql
SELECT pg_get_viewdef('derived.snapshot_features_v1', true);
\o

-- 7. Check timestamp alignment - verify candlesticks exist near aligned timestamps
-- Uses the same alignment formula as the view: aligned_ts = game_start + (snapshot_ts - first_espn_ts)
SELECT 
    sf.sequence_number,
    sf.snapshot_ts AS raw_snapshot_ts,
    gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) AS aligned_ts,
    sf.kalshi_home_mid_price AS view_home,
    sf.kalshi_away_mid_price AS view_away,
    -- Count candlesticks near the ALIGNED timestamp (matching view's 60-second window)
    (SELECT COUNT(*) 
     FROM kalshi.markets_with_games mwg
     JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
     WHERE mwg.espn_event_id = sf.game_id
       AND mwg.kalshi_team_side = 'home'
       AND c.yes_bid_close IS NOT NULL
       AND c.yes_ask_close IS NOT NULL
       AND c.period_ts >= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) - INTERVAL '60 seconds')
       AND c.period_ts <= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) + INTERVAL '60 seconds')
    ) AS home_candles_near_aligned,
    (SELECT COUNT(*) 
     FROM kalshi.markets_with_games mwg
     JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
     WHERE mwg.espn_event_id = sf.game_id
       AND mwg.kalshi_team_side = 'away'
       AND c.yes_bid_close IS NOT NULL
       AND c.yes_ask_close IS NOT NULL
       AND c.period_ts >= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) - INTERVAL '60 seconds')
       AND c.period_ts <= (gti.game_start + (sf.snapshot_ts - gti.first_espn_ts) + INTERVAL '60 seconds')
    ) AS away_candles_near_aligned
FROM derived.snapshot_features_v1 sf
JOIN (
    SELECT DISTINCT 
        p.game_id,
        sg.event_date AS game_start,
        MIN(p.last_modified_utc) OVER (PARTITION BY p.game_id) AS first_espn_ts
    FROM espn.probabilities_raw_items p
    JOIN espn.scoreboard_games sg ON sg.event_id = p.game_id
    WHERE p.season_label = '2025-26'
) gti ON gti.game_id = sf.game_id
WHERE sf.game_id = '401809981'
  AND sf.season_label = '2025-26'
  AND sf.kalshi_home_mid_price IS NOT NULL
  AND sf.kalshi_away_mid_price IS NOT NULL
  AND ABS((sf.kalshi_home_mid_price + sf.kalshi_away_mid_price) - 1.0) < 0.05
ORDER BY sf.sequence_number
LIMIT 10;
