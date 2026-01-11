# Phase 3: Materialized View Creation Commands

## Step 1: Drop Existing View and Create Materialized View

```bash
cd /Users/adamvoliva/Code/bball
source .env
```

```sql
-- Drop view if exists
DROP VIEW IF EXISTS derived.snapshot_features_v1 CASCADE;

-- Create materialized view (pre-computed, much faster)
CREATE MATERIALIZED VIEW derived.snapshot_features_v1 AS
WITH espn_base AS (
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
espn_with_lags AS (
    SELECT 
        *,
        LAG(espn_home_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number
        ) AS espn_home_prob_lag_1,
        LAG(espn_away_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number
        ) AS espn_away_prob_lag_1,
        espn_home_prob - LAG(espn_home_prob) OVER (
            PARTITION BY season_label, game_id 
            ORDER BY sequence_number
        ) AS espn_home_prob_delta_1
    FROM espn_with_interactions
),
kalshi_home_markets AS (
    SELECT DISTINCT ON (mwg.espn_event_id, c.period_ts)
        mwg.espn_event_id AS game_id,
        c.period_ts,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL THEN c.yes_bid_close::NUMERIC / 100.0
            ELSE NULL
        END AS kalshi_home_bid,
        CASE 
            WHEN c.yes_ask_close IS NOT NULL THEN c.yes_ask_close::NUMERIC / 100.0
            ELSE NULL
        END AS kalshi_home_ask,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL THEN
                (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 2.0 / 100.0
            ELSE NULL
        END AS kalshi_home_mid_price,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL THEN
                (c.yes_ask_close::NUMERIC - c.yes_bid_close::NUMERIC) / 100.0
            ELSE NULL
        END AS kalshi_home_spread
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON mwg.ticker = c.ticker
    WHERE mwg.kalshi_team_side = 'home'
        AND mwg.espn_event_id IS NOT NULL
        AND c.yes_bid_close IS NOT NULL
        AND c.yes_ask_close IS NOT NULL
    ORDER BY mwg.espn_event_id, c.period_ts, c.candlestick_id DESC
),
kalshi_away_markets AS (
    SELECT DISTINCT ON (mwg.espn_event_id, c.period_ts)
        mwg.espn_event_id AS game_id,
        c.period_ts,
        CASE 
            WHEN c.yes_ask_close IS NOT NULL THEN (100.0 - c.yes_ask_close::NUMERIC) / 100.0
            ELSE NULL
        END AS kalshi_away_bid,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL THEN (100.0 - c.yes_bid_close::NUMERIC) / 100.0
            ELSE NULL
        END AS kalshi_away_ask,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL THEN
                (100.0 - (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 2.0) / 100.0
            ELSE NULL
        END AS kalshi_away_mid_price,
        CASE 
            WHEN c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL THEN
                (c.yes_ask_close::NUMERIC - c.yes_bid_close::NUMERIC) / 100.0
            ELSE NULL
        END AS kalshi_away_spread
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON mwg.ticker = c.ticker
    WHERE mwg.kalshi_team_side = 'away'
        AND mwg.espn_event_id IS NOT NULL
        AND c.yes_bid_close IS NOT NULL
        AND c.yes_ask_close IS NOT NULL
    ORDER BY mwg.espn_event_id, c.period_ts, c.candlestick_id DESC
),
kalshi_aligned AS (
    SELECT 
        e.season_label,
        e.game_id,
        e.sequence_number,
        e.snapshot_ts,
        COALESCE(kh.kalshi_home_bid, ka.kalshi_away_bid) AS kalshi_home_bid,
        COALESCE(kh.kalshi_home_ask, ka.kalshi_away_ask) AS kalshi_home_ask,
        COALESCE(kh.kalshi_home_mid_price, ka.kalshi_away_mid_price) AS kalshi_home_mid_price,
        COALESCE(kh.kalshi_home_spread, ka.kalshi_away_spread) AS kalshi_home_spread,
        ka.kalshi_away_bid,
        ka.kalshi_away_ask,
        ka.kalshi_away_mid_price,
        ka.kalshi_away_spread
    FROM espn_with_lags e
    LEFT JOIN LATERAL (
        SELECT *
        FROM kalshi_home_markets kh
        WHERE kh.game_id = e.game_id
            AND ABS(EXTRACT(EPOCH FROM (kh.period_ts - e.snapshot_ts))) <= 60
        ORDER BY ABS(EXTRACT(EPOCH FROM (kh.period_ts - e.snapshot_ts)))
        LIMIT 1
    ) kh ON true
    LEFT JOIN LATERAL (
        SELECT *
        FROM kalshi_away_markets ka
        WHERE ka.game_id = e.game_id
            AND ABS(EXTRACT(EPOCH FROM (ka.period_ts - e.snapshot_ts))) <= 60
        ORDER BY ABS(EXTRACT(EPOCH FROM (ka.period_ts - e.snapshot_ts)))
        LIMIT 1
    ) ka ON true
)
SELECT 
    e.season_label,
    e.game_id,
    e.sequence_number,
    e.snapshot_ts,
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
FROM espn_with_lags e
LEFT JOIN kalshi_aligned k 
    ON e.season_label = k.season_label
    AND e.game_id = k.game_id
    AND e.sequence_number = k.sequence_number
    AND e.snapshot_ts = k.snapshot_ts;
```

**Note**: This will take several minutes to build (5.3M rows). Run it and let it complete.

## Step 2: Create Indexes (After Materialized View is Built)

```sql
-- Unique index on primary key
CREATE UNIQUE INDEX idx_snapshot_features_v1_pk 
    ON derived.snapshot_features_v1(season_label, game_id, sequence_number, snapshot_ts);

-- Index for game queries
CREATE INDEX idx_snapshot_features_v1_game 
    ON derived.snapshot_features_v1(game_id, sequence_number);

-- Index for season/game queries
CREATE INDEX idx_snapshot_features_v1_season_game 
    ON derived.snapshot_features_v1(season_label, game_id);
```

## Step 3: Fast Validation Queries (Run After Indexes Created)

```sql
-- Quick row count
SELECT COUNT(*) FROM derived.snapshot_features_v1 WHERE season_label = '2025-26';

-- Sample rows (should be fast with indexes)
SELECT * FROM derived.snapshot_features_v1 
WHERE season_label = '2025-26' AND game_id = '401810095' 
ORDER BY sequence_number LIMIT 5;

-- Check uniqueness (should return 0 rows)
SELECT season_label, game_id, sequence_number, snapshot_ts, COUNT(*) as cnt
FROM derived.snapshot_features_v1
GROUP BY season_label, game_id, sequence_number, snapshot_ts
HAVING COUNT(*) > 1
LIMIT 10;

-- Check sequence_number ordering for one game
SELECT game_id, sequence_number, 
       LAG(sequence_number) OVER (PARTITION BY game_id ORDER BY sequence_number) as prev_seq
FROM derived.snapshot_features_v1
WHERE season_label = '2025-26' AND game_id = '401810095'
ORDER BY sequence_number
LIMIT 10;
```

## Step 4: Update Migration File

After confirming it works, update `db/migrations/032_derived_snapshot_features_v1.sql` to use `CREATE MATERIALIZED VIEW` instead of `CREATE VIEW`.

## Refresh Command (For Future Updates)

```sql
-- Refresh materialized view (run after new data is ingested)
REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;
```

**Note**: `CONCURRENTLY` allows queries during refresh but requires unique index.

