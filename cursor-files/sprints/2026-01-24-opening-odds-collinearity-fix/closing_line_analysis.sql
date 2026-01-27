-- Check availability of timestamped odds data for closing/pre-tip line alternative
-- Test multiple windows (5, 15, 60 minutes) to find smallest with acceptable coverage

WITH game_starts AS (
    SELECT 
        event_id AS espn_game_id,
        event_date AS game_start_time
    FROM espn.scoreboard_games
    WHERE status_completed = TRUE
),
odds_with_timestamps AS (
    SELECT 
        s.espn_game_id,
        s.snapshot_timestamp,
        gs.game_start_time,
        -- Calculate time difference before game start (negative = before, positive = after)
        EXTRACT(EPOCH FROM (s.snapshot_timestamp - gs.game_start_time)) / 60.0 AS minutes_before_start
    FROM external.sportsbook_odds_snapshots s
    LEFT JOIN game_starts gs ON s.espn_game_id = gs.espn_game_id
    WHERE s.espn_game_id IS NOT NULL
      AND s.is_opening_line = FALSE  -- Check non-opening lines for closing/pre-tip
      AND s.snapshot_timestamp IS NOT NULL
      AND gs.game_start_time IS NOT NULL
)
SELECT 
    COUNT(DISTINCT espn_game_id) AS total_games_with_timestamped_odds,
    -- Coverage for 5-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -5 AND minutes_before_start <= 0
    ) AS games_within_5_minutes,
    -- Coverage for 15-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -15 AND minutes_before_start <= 0
    ) AS games_within_15_minutes,
    -- Coverage for 60-minute window
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start >= -60 AND minutes_before_start <= 0
    ) AS games_within_60_minutes,
    -- Overall stats
    COUNT(DISTINCT espn_game_id) FILTER (
        WHERE minutes_before_start < 0
    ) AS games_with_pre_tip_odds,
    AVG(minutes_before_start) FILTER (WHERE minutes_before_start < 0) AS avg_minutes_before_start,
    MIN(minutes_before_start) AS earliest_minutes_before_start
FROM odds_with_timestamps;
