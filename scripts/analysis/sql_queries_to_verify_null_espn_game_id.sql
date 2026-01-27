-- SQL Queries to Verify NULL ESPN_GAME_ID Causes
-- Run these queries to get factual evidence about why games have NULL espn_game_id

-- 1. Statistics on NULL espn_game_id records
SELECT 
    source_dataset,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE espn_game_id IS NULL) as null_game_id_count,
    COUNT(*) FILTER (WHERE is_opening_line = TRUE) as opening_line_count,
    COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) as opening_null_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE espn_game_id IS NULL) / COUNT(*), 1) as null_percentage
FROM external.sportsbook_odds_snapshots
GROUP BY source_dataset
ORDER BY source_dataset;

-- 2. Sample records with NULL espn_game_id (opening lines)
SELECT DISTINCT ON (game_date, away_team_espn, home_team_espn)
    game_date,
    away_team_espn,
    home_team_espn,
    market_type,
    side,
    is_opening_line,
    source_dataset,
    snapshot_timestamp
FROM external.sportsbook_odds_snapshots
WHERE espn_game_id IS NULL
  AND is_opening_line = TRUE
ORDER BY game_date, away_team_espn, home_team_espn, snapshot_timestamp NULLS LAST
LIMIT 50;

-- 3. Check if ESPN games exist for sample NULL records
-- Replace the date and teams with values from query #2
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
    DATE(sg.event_date) as espn_date,
    CASE 
        WHEN sg.event_id IS NOT NULL THEN 'FOUND'
        ELSE 'NOT FOUND'
    END as match_status
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

-- 4. Check team name mismatches
-- Find cases where teams exist on the date but don't match
WITH sample_null AS (
    SELECT DISTINCT ON (game_date, away_team_espn, home_team_espn)
        game_date,
        away_team_espn,
        home_team_espn
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id IS NULL
      AND is_opening_line = TRUE
    LIMIT 20
),
espn_games_on_date AS (
    SELECT DISTINCT
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev
    FROM espn.scoreboard_games
)
SELECT 
    sn.game_date,
    sn.away_team_espn as odds_away,
    sn.home_team_espn as odds_home,
    -- Check if teams exist on this date
    COUNT(*) FILTER (WHERE eg.home_team_abbrev = sn.home_team_espn OR eg.away_team_abbrev = sn.home_team_espn) as home_team_found,
    COUNT(*) FILTER (WHERE eg.home_team_abbrev = sn.away_team_espn OR eg.away_team_abbrev = sn.away_team_espn) as away_team_found,
    COUNT(*) as total_espn_games_on_date
FROM sample_null sn
LEFT JOIN espn_games_on_date eg ON eg.game_date = sn.game_date
GROUP BY sn.game_date, sn.away_team_espn, sn.home_team_espn
ORDER BY sn.game_date;

-- 5. Check what ESPN games exist for specific dates with NULL records
-- This helps identify if games exist but team names don't match
SELECT 
    DATE(sg.event_date) as game_date,
    sg.event_id,
    sg.away_team_abbrev,
    sg.home_team_abbrev,
    sg.away_team_display_name,
    sg.home_team_display_name
FROM espn.scoreboard_games sg
WHERE DATE(sg.event_date) IN (
    SELECT DISTINCT game_date
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id IS NULL
      AND is_opening_line = TRUE
    LIMIT 5
)
ORDER BY DATE(sg.event_date), sg.event_date
LIMIT 50;

-- 6. Compare team abbreviations used in odds vs ESPN
SELECT DISTINCT
    sos.away_team_espn as odds_away_abbrev,
    sos.home_team_espn as odds_home_abbrev,
    COUNT(*) as record_count
FROM external.sportsbook_odds_snapshots sos
WHERE sos.espn_game_id IS NULL
  AND sos.is_opening_line = TRUE
GROUP BY sos.away_team_espn, sos.home_team_espn
ORDER BY record_count DESC
LIMIT 20;

-- 7. Check if there are any patterns in dates
SELECT 
    DATE_PART('year', game_date) as year,
    DATE_PART('month', game_date) as month,
    COUNT(*) as null_count
FROM external.sportsbook_odds_snapshots
WHERE espn_game_id IS NULL
  AND is_opening_line = TRUE
GROUP BY DATE_PART('year', game_date), DATE_PART('month', game_date)
ORDER BY year DESC, month DESC;
