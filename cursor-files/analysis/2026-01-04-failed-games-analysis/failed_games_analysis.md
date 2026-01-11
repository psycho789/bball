# Failed Games Analysis: Why These Games Failed in Simulation

**Date**: Sun Jan  4 22:27:54 PST 2026  
**Author**: Analysis  
**Purpose**: Investigate why specific games failed during bulk simulation runs

---

## Failed Game IDs

```
401810286, 401810294, 401810293, 401810287, 401810288, 401810292, 401810291, 401810289, 401810285, 401810283
```

---

## Investigation Plan

### Step 1: Check Game Metadata

**Query**:
```sql
SELECT 
    event_id,
    event_date,
    home_team_abbrev,
    away_team_abbrev,
    home_score,
    away_score
FROM espn.scoreboard_games
WHERE event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
ORDER BY event_id;
```

**Purpose**: Understand what these games are (teams, dates, outcomes)

### Step 2: Check ESPN Probability Data Coverage

**Query**:
```sql
SELECT 
    game_id,
    COUNT(*) as prob_count,
    MIN(last_modified_utc) as first_prob,
    MAX(last_modified_utc) as last_prob,
    COUNT(DISTINCT sequence_number) as unique_sequences
FROM espn.probabilities_raw_items
WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY game_id
ORDER BY game_id;
```

**Purpose**: Determine if ESPN probability data exists for these games

### Step 3: Check Kalshi Market Coverage

**Query**:
```sql
SELECT 
    sg.event_id,
    COUNT(DISTINCT km.ticker) as market_count,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'home' THEN kmw.ticker END) as home_markets,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'away' THEN kmw.ticker END) as away_markets
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets km ON sg.event_id = km.espn_event_id
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY sg.event_id
ORDER BY sg.event_id;
```

**Purpose**: Determine if Kalshi markets exist for these games

### Step 4: Check Kalshi Candlestick Coverage

**Query**:
```sql
SELECT 
    sg.event_id,
    kmw.ticker,
    kmw.kalshi_team_side,
    COUNT(DISTINCT kc.period_ts) as candlestick_count,
    MIN(kc.period_ts) as first_candle,
    MAX(kc.period_ts) as last_candle,
    COUNT(DISTINCT CASE WHEN kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL THEN kc.period_ts END) as candles_with_bid_ask
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
LEFT JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY sg.event_id, kmw.ticker, kmw.kalshi_team_side
ORDER BY sg.event_id, kmw.ticker;
```

**Purpose**: Determine if candlesticks exist and have bid/ask data

### Step 5: Check Canonical Dataset Coverage

**Query**:
```sql
SELECT 
    game_id,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT sequence_number) as unique_sequences,
    COUNT(CASE WHEN kalshi_home_mid_price IS NOT NULL THEN 1 END) as snapshots_with_kalshi,
    COUNT(CASE WHEN espn_home_prob IS NOT NULL THEN 1 END) as snapshots_with_espn,
    MIN(snapshot_ts) as first_snapshot,
    MAX(snapshot_ts) as last_snapshot
FROM derived.snapshot_features_v1
WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY game_id
ORDER BY game_id;
```

**Purpose**: Check if these games are in the canonical dataset and how many snapshots have Kalshi data

### Step 6: Check Alignment Window Coverage

**Query**:
```sql
-- For each failed game, check how many ESPN snapshots can be aligned with Kalshi candlesticks
WITH espn_snapshots AS (
    SELECT 
        game_id,
        snapshot_ts,
        sequence_number,
        espn_home_prob
    FROM derived.snapshot_features_v1
    WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
      AND espn_home_prob IS NOT NULL
),
kalshi_candles AS (
    SELECT DISTINCT ON (kmw.espn_event_id, kc.period_ts)
        kmw.espn_event_id as game_id,
        kc.period_ts,
        kc.yes_bid_close,
        kc.yes_ask_close
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
    WHERE kmw.espn_event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
      AND kmw.kalshi_team_side = 'home'
      AND kc.yes_bid_close IS NOT NULL
      AND kc.yes_ask_close IS NOT NULL
)
SELECT 
    es.game_id,
    COUNT(*) as total_espn_snapshots,
    COUNT(kc.period_ts) as aligned_within_60s,
    COUNT(*) - COUNT(kc.period_ts) as not_aligned,
    ROUND(100.0 * COUNT(kc.period_ts) / COUNT(*), 2) as alignment_percentage
FROM espn_snapshots es
LEFT JOIN kalshi_candles kc ON es.game_id = kc.game_id
    AND ABS(EXTRACT(EPOCH FROM (es.snapshot_ts - kc.period_ts))) <= 60
GROUP BY es.game_id
ORDER BY es.game_id;
```

**Purpose**: Understand alignment coverage for these games

### Step 7: Check for Specific Error Patterns

**Query**:
```sql
-- Check if games are missing from games_with_kalshi filter
SELECT 
    sg.event_id,
    CASE 
        WHEN EXISTS (
            SELECT 1
            FROM kalshi.markets_with_games mwg
            WHERE mwg.espn_event_id = sg.event_id
              AND EXISTS (
                SELECT 1
                FROM kalshi.candlesticks c
                WHERE c.ticker = mwg.ticker
                  AND c.yes_bid_close IS NOT NULL
                  AND c.yes_ask_close IS NOT NULL
              )
        ) THEN 'HAS_KALSHI'
        ELSE 'NO_KALSHI'
    END as kalshi_status
FROM espn.scoreboard_games sg
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
ORDER BY sg.event_id;
```

**Purpose**: Check if these games would pass the `games_with_kalshi` filter

---

## SQL Investigation Queries

**To run the investigation**, execute these queries in order:

### Step 1: Game Metadata
```sql
SELECT 
    event_id,
    event_date,
    home_team_abbrev,
    away_team_abbrev,
    home_score,
    away_score
FROM espn.scoreboard_games
WHERE event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
ORDER BY event_id;
```

### Step 2: ESPN Probability Coverage
```sql
SELECT 
    game_id,
    COUNT(*) as prob_count,
    MIN(last_modified_utc) as first_prob,
    MAX(last_modified_utc) as last_prob,
    COUNT(DISTINCT sequence_number) as unique_sequences
FROM espn.probabilities_raw_items
WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY game_id
ORDER BY game_id;
```

### Step 3: Kalshi Market Coverage
```sql
SELECT 
    sg.event_id,
    COUNT(DISTINCT km.ticker) as market_count,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'home' THEN kmw.ticker END) as home_markets,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'away' THEN kmw.ticker END) as away_markets
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets km ON sg.event_id = km.espn_event_id
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY sg.event_id
ORDER BY sg.event_id;
```

### Step 4: Kalshi Candlestick Coverage
```sql
SELECT 
    sg.event_id,
    kmw.ticker,
    kmw.kalshi_team_side,
    COUNT(DISTINCT kc.period_ts) as candlestick_count,
    COUNT(DISTINCT CASE WHEN kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL THEN kc.period_ts END) as candles_with_bid_ask
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
LEFT JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY sg.event_id, kmw.ticker, kmw.kalshi_team_side
ORDER BY sg.event_id, kmw.ticker;
```

### Step 5: Check games_with_kalshi Filter Status
```sql
SELECT 
    sg.event_id,
    CASE 
        WHEN EXISTS (
            SELECT 1
            FROM kalshi.markets_with_games mwg
            WHERE mwg.espn_event_id = sg.event_id
              AND EXISTS (
                SELECT 1
                FROM kalshi.candlesticks c
                WHERE c.ticker = mwg.ticker
                  AND c.yes_bid_close IS NOT NULL
                  AND c.yes_ask_close IS NOT NULL
              )
        ) THEN 'HAS_KALSHI'
        ELSE 'NO_KALSHI'
    END as kalshi_status
FROM espn.scoreboard_games sg
WHERE sg.event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
ORDER BY sg.event_id;
```

### Step 6: Canonical Dataset Coverage
```sql
SELECT 
    game_id,
    COUNT(*) as snapshot_count,
    COUNT(DISTINCT sequence_number) as unique_sequences,
    COUNT(CASE WHEN kalshi_home_mid_price IS NOT NULL THEN 1 END) as snapshots_with_kalshi,
    COUNT(CASE WHEN espn_home_prob IS NOT NULL THEN 1 END) as snapshots_with_espn,
    MIN(snapshot_ts) as first_snapshot,
    MAX(snapshot_ts) as last_snapshot
FROM derived.snapshot_features_v1
WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY game_id
ORDER BY game_id;
```

### Step 7: Time Overlap Analysis (Critical)
```sql
-- Check if ESPN snapshots and Kalshi candlesticks have time overlap
WITH espn_time_range AS (
    SELECT 
        game_id,
        MIN(last_modified_utc) as espn_start,
        MAX(last_modified_utc) as espn_end
    FROM espn.probabilities_raw_items
    WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
    GROUP BY game_id
),
kalshi_time_range AS (
    SELECT 
        kmw.espn_event_id as game_id,
        MIN(kc.period_ts) as kalshi_start,
        MAX(kc.period_ts) as kalshi_end
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
    WHERE kmw.espn_event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
      AND kc.yes_bid_close IS NOT NULL
      AND kc.yes_ask_close IS NOT NULL
    GROUP BY kmw.espn_event_id
)
SELECT 
    etr.game_id,
    etr.espn_start,
    etr.espn_end,
    ktr.kalshi_start,
    ktr.kalshi_end,
    CASE 
        WHEN etr.espn_start <= ktr.kalshi_end + INTERVAL '60 seconds' 
         AND etr.espn_end >= ktr.kalshi_start - INTERVAL '60 seconds'
        THEN 'OVERLAP'
        ELSE 'NO_OVERLAP'
    END as overlap_status,
    EXTRACT(EPOCH FROM (etr.espn_start - ktr.kalshi_end)) as gap_seconds_espn_after_kalshi,
    EXTRACT(EPOCH FROM (ktr.kalshi_start - etr.espn_end)) as gap_seconds_kalshi_after_espn
FROM espn_time_range etr
LEFT JOIN kalshi_time_range ktr ON etr.game_id = ktr.game_id
ORDER BY etr.game_id;
```

### Step 8: Trade Data Coverage (Individual Trades)
```sql
-- Check if we have individual trade records (not just candlesticks) for these games
SELECT 
    kmw.espn_event_id as game_id,
    kmw.ticker,
    kmw.kalshi_team_side,
    COUNT(DISTINCT kt.trade_id) as trade_count,
    MIN(kt.created_time) as first_trade,
    MAX(kt.created_time) as last_trade,
    COUNT(DISTINCT DATE_TRUNC('minute', kt.created_time)) as unique_minutes_with_trades
FROM kalshi.markets_with_games kmw
LEFT JOIN kalshi.trades kt ON kmw.ticker = kt.ticker
WHERE kmw.espn_event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
GROUP BY kmw.espn_event_id, kmw.ticker, kmw.kalshi_team_side
ORDER BY kmw.espn_event_id, kmw.ticker;
```

### Step 9: Trade Data Time Overlap with ESPN
```sql
-- Check if trade data overlaps with ESPN snapshot times
WITH espn_time_range AS (
    SELECT 
        game_id,
        MIN(last_modified_utc) as espn_start,
        MAX(last_modified_utc) as espn_end
    FROM espn.probabilities_raw_items
    WHERE game_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
    GROUP BY game_id
),
trade_time_range AS (
    SELECT 
        kmw.espn_event_id as game_id,
        MIN(kt.created_time) as trade_start,
        MAX(kt.created_time) as trade_end,
        COUNT(DISTINCT kt.trade_id) as total_trades
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.trades kt ON kmw.ticker = kt.ticker
    WHERE kmw.espn_event_id IN ('401810286', '401810294', '401810293', '401810287', '401810288', '401810292', '401810291', '401810289', '401810285', '401810283')
    GROUP BY kmw.espn_event_id
)
SELECT 
    etr.game_id,
    etr.espn_start,
    etr.espn_end,
    ttr.trade_start,
    ttr.trade_end,
    ttr.total_trades,
    CASE 
        WHEN ttr.trade_start IS NULL THEN 'NO_TRADE_DATA'
        WHEN etr.espn_start <= ttr.trade_end + INTERVAL '60 seconds' 
         AND etr.espn_end >= ttr.trade_start - INTERVAL '60 seconds'
        THEN 'OVERLAP'
        ELSE 'NO_OVERLAP'
    END as overlap_status,
    CASE 
        WHEN ttr.trade_start IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (etr.espn_start - ttr.trade_end))
    END as gap_seconds_espn_after_trades,
    CASE 
        WHEN ttr.trade_start IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (ttr.trade_start - etr.espn_end))
    END as gap_seconds_trades_after_espn
FROM espn_time_range etr
LEFT JOIN trade_time_range ttr ON etr.game_id = ttr.game_id
ORDER BY etr.game_id;
```

### Step 10: Sample Trade Alignment Test
```sql
-- Test if trades exist during ESPN snapshot windows for one game
WITH sample_espn AS (
    SELECT 
        game_id,
        last_modified_utc as snapshot_ts,
        sequence_number
    FROM espn.probabilities_raw_items
    WHERE game_id = '401810286'
    ORDER BY sequence_number
    LIMIT 10
),
nearby_trades AS (
    SELECT 
        kmw.espn_event_id as game_id,
        kt.created_time as trade_ts,
        kt.yes_price,
        kt.count as trade_volume,
        ABS(EXTRACT(EPOCH FROM (kt.created_time - se.snapshot_ts))) as time_diff_seconds
    FROM sample_espn se
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = se.game_id
    JOIN kalshi.trades kt ON kmw.ticker = kt.ticker
    WHERE kmw.kalshi_team_side = 'home'
      AND kt.yes_price IS NOT NULL
      AND ABS(EXTRACT(EPOCH FROM (kt.created_time - se.snapshot_ts))) <= 300  -- Check within 5 minutes
    ORDER BY se.game_id, se.snapshot_ts, time_diff_seconds
    LIMIT 50
)
SELECT 
    se.game_id,
    se.snapshot_ts as espn_ts,
    nt.trade_ts,
    nt.yes_price,
    nt.trade_volume,
    nt.time_diff_seconds,
    CASE WHEN nt.time_diff_seconds <= 60 THEN 'WITHIN_60S' ELSE 'OUTSIDE_60S' END as alignment_status
FROM sample_espn se
LEFT JOIN nearby_trades nt ON se.game_id = nt.game_id
ORDER BY se.snapshot_ts, nt.time_diff_seconds;
```

## Evidence to Capture

### Query Results

**Step 1 - Game Metadata**:
```
All 10 games exist in espn.scoreboard_games
All have event_date, teams, but scores are 0 (likely pre-game or not completed)
```

**Step 2 - ESPN Probability Coverage**:
```
All 10 games have ESPN probability data:
- 401810283: 495 snapshots (2025-12-26 20:11:00-08 to 23:20:00-08)
- 401810285: 498 snapshots (2025-12-26 21:48:00-08 to 2025-12-27 00:03:00-08)
- 401810286: 437 snapshots (2025-12-26 22:13:00-08 to 2025-12-27 00:38:00-08)
- 401810287: 472 snapshots (2025-12-27 17:10:00-08 to 19:18:00-08)
- 401810288: 486 snapshots (2025-12-27 19:11:00-08 to 21:51:00-08)
- 401810289: 517 snapshots (2025-12-27 19:10:00-08 to 23:26:00-08)
- 401810291: 507 snapshots (2025-12-27 20:12:00-08 to 22:39:00-08)
- 401810292: 490 snapshots (2025-12-27 20:10:00-08 to 22:37:00-08)
- 401810293: 469 snapshots (2025-12-27 20:11:00-08 to 22:33:00-08)
- 401810294: 463 snapshots (2025-12-27 20:11:00-08 to 22:23:00-08)
```

**Step 3 - Kalshi Market Coverage**:
```
All 10 games have Kalshi markets:
- Each game has 2 markets (home + away)
- Game 401810286 has 1 home market but 0 away markets (NULL kalshi_team_side for one ticker)
```

**Step 4 - Kalshi Candlestick Coverage**:
```
All 10 games have extensive candlestick data with bid/ask:
- 401810283: 1482 home candles, 1522 away candles
- 401810285: 1596 home candles, 1616 away candles
- 401810286: 1618 home candles, 1636 candles (NULL side)
- ... (all have 1400-1600+ candlesticks per market)
- ALL candlesticks have yes_bid_close and yes_ask_close (100% coverage)
```

**Step 5 - games_with_kalshi Filter Status**:
```
✅ ALL 10 games PASS the filter (HAS_KALSHI status)
This confirms games are included in the materialized view, but alignment fails.
```

**Step 6 - Canonical Dataset Coverage**:
```
CRITICAL FINDING: All 10 games have 0% Kalshi alignment:
- 401810283: 495 snapshots, 0 with Kalshi data
- 401810285: 498 snapshots, 0 with Kalshi data
- 401810286: 437 snapshots, 0 with Kalshi data
- ... (all games: 0 snapshots_with_kalshi despite having candlestick data)
```

**Step 7 - Time Overlap Analysis**:
```
🚨 ROOT CAUSE CONFIRMED: ALL 10 games have NO_OVERLAP

Time Gap Analysis (ESPN starts AFTER Kalshi ends):
- 401810283: Kalshi ends 19:32:00-08, ESPN starts 20:11:00-08 (39 min gap = 2340 sec)
- 401810285: Kalshi ends 21:06:00-08, ESPN starts 21:48:00-08 (42 min gap = 2520 sec)
- 401810286: Kalshi ends 21:41:00-08, ESPN starts 22:13:00-08 (32 min gap = 1920 sec)
- 401810287: Kalshi ends 16:22:00-08, ESPN starts 17:10:00-08 (48 min gap = 2880 sec)
- 401810288: Kalshi ends 18:41:00-08, ESPN starts 19:11:00-08 (30 min gap = 1800 sec)
- 401810289: Kalshi ends 18:36:00-08, ESPN starts 19:10:00-08 (34 min gap = 2040 sec)
- 401810291: Kalshi ends 19:26:00-08, ESPN starts 20:12:00-08 (46 min gap = 2760 sec)
- 401810292: Kalshi ends 19:26:00-08, ESPN starts 20:10:00-08 (44 min gap = 2640 sec)
- 401810293: Kalshi ends 19:16:00-08, ESPN starts 20:11:00-08 (55 min gap = 3300 sec)
- 401810294: Kalshi ends 19:26:00-08, ESPN starts 20:11:00-08 (45 min gap = 2700 sec)

Pattern: Kalshi candlesticks stop 30-55 minutes BEFORE ESPN probability snapshots begin.
The 60-second alignment window cannot bridge these gaps.
```

**Step 8 - Trade Data Coverage**:
```
✅ ALL 10 games have trade data (individual trade records, not just candlesticks):
- 401810283: 10,890 trades (16:45:00-08 to 19:30:59-08)
- 401810285: 41,220 trades (18:15:07-08 to 20:59:59-08)
- 401810286: 35,614 trades (18:45:01-08 to 21:39:56-08)
- 401810287: 17,416 trades (13:45:02-08 to 16:21:32-08)
- 401810288: 33,894 trades (15:45:04-08 to 18:40:56-08)
- 401810289: 11,817 trades (15:45:00-08 to 18:35:17-08)
- 401810291: 4,593 trades (16:45:30-08 to 19:24:58-08)
- 401810292: 10,996 trades (16:45:02-08 to 19:25:19-08)
- 401810293: 4,158 trades (16:45:07-08 to 19:14:07-08)
- 401810294: 11,532 trades (16:45:17-08 to 19:25:20-08)
```

**Step 9 - Trade Data Time Overlap with ESPN**:
```
🚨 CRITICAL FINDING: Trade data has the SAME timing issue as candlesticks

ALL 10 games have NO_OVERLAP between trades and ESPN snapshots:
- 401810283: Trades end 19:30:59-08, ESPN starts 20:11:00-08 (40 min gap = 2400 sec)
- 401810285: Trades end 20:59:59-08, ESPN starts 21:48:00-08 (48 min gap = 2880 sec)
- 401810286: Trades end 21:39:56-08, ESPN starts 22:13:00-08 (33 min gap = 1984 sec)
- 401810287: Trades end 16:21:32-08, ESPN starts 17:10:00-08 (48 min gap = 2907 sec)
- 401810288: Trades end 18:40:56-08, ESPN starts 19:11:00-08 (30 min gap = 1803 sec)
- 401810289: Trades end 18:35:17-08, ESPN starts 19:10:00-08 (34 min gap = 2082 sec)
- 401810291: Trades end 19:24:58-08, ESPN starts 20:12:00-08 (47 min gap = 2821 sec)
- 401810292: Trades end 19:25:19-08, ESPN starts 20:10:00-08 (44 min gap = 2680 sec)
- 401810293: Trades end 19:14:07-08, ESPN starts 20:11:00-08 (57 min gap = 3412 sec)
- 401810294: Trades end 19:25:20-08, ESPN starts 20:11:00-08 (45 min gap = 2739 sec)

Pattern: Trades stop 30-57 minutes BEFORE ESPN probability snapshots begin.
Trade data does NOT solve the alignment problem - same timing issue as candlesticks.
```

**Step 10 - Sample Trade Alignment Test**:
```
[NOT RUN - Step 9 confirms trades have same timing issue as candlesticks]
```

---

## Root Cause Analysis

### 🚨 CRITICAL DISCOVERY: Materialized View Time Alignment Issue

**Critical Discovery**: All 10 failed games have:
- ✅ ESPN probability snapshots (hundreds per game)
- ✅ Kalshi markets (2 per game)
- ✅ Kalshi candlesticks with bid/ask (thousands per game)
- ✅ Pass `games_with_kalshi` filter (included in materialized view)
- ❌ **0% alignment** due to **TIME ALIGNMENT MISMATCH**

### The Real Problem

**The materialized view `derived.snapshot_features_v1` is matching RAW timestamps, but according to `webapp/README.md` (lines 503-612), ESPN timestamps should be SHIFTED to align with game start.**

According to the README, the time alignment process should be:

1. **ESPN Data Alignment**: 
   - First ESPN record should align to `event_date` (game start)
   - Formula: `aligned_timestamp = game_start_timestamp + elapsed_from_first`
   - This SHIFTS ESPN timestamps to game timeline

2. **Kalshi Data Filtering**:
   - Filter candlesticks to game window: `period_ts >= game_start AND period_ts <= (game_start + duration)`
   - Kalshi timestamps are NOT shifted, just filtered

3. **Final Matching**:
   - Match aligned ESPN timestamps to filtered Kalshi timestamps within 60 seconds

**BUT**: The materialized view is currently matching RAW timestamps:
```sql
c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds' 
                 AND ewd.snapshot_ts + INTERVAL '60 seconds'
```

Where `ewd.snapshot_ts` is the RAW ESPN `last_modified_utc` timestamp (not aligned to game start).

### Why This Causes 0% Alignment

**Example (Game 401810286)**:
- **Raw ESPN timestamps**: `2025-12-26 22:13:00-08` to `2025-12-27 00:38:00-08`
- **Raw Kalshi timestamps**: `2025-12-25 16:00:00-08` to `2025-12-26 21:41:00-08`
- **Game start (`event_date`)**: `2025-12-26 19:00:00-08` (scheduled tip-off)

**Current Materialized View Logic** (WRONG):
- Tries to match raw ESPN `22:13:00-08` to raw Kalshi `21:41:00-08` (±60 seconds)
- Gap: 32 minutes → NO MATCH

**Correct Logic** (per README):
- **ESPN alignment**: First ESPN record (`22:13:00-08`) should align to game start (`19:00:00-08`)
- **Kalshi filtering**: Include only candlesticks where `period_ts >= 19:00:00-08 AND period_ts <= (19:00:00-08 + duration)`
- **Matching**: Match aligned ESPN timestamps to filtered Kalshi timestamps

**The Issue**: The materialized view doesn't apply ESPN timestamp shifting, so it's trying to match raw timestamps that don't overlap.

### Why This Happens

1. **Materialized view stores raw timestamps**: `snapshot_ts` = `last_modified_utc` (raw ESPN recording time)
2. **Materialized view matches raw timestamps**: LATERAL JOIN uses raw `snapshot_ts` for matching
3. **Alignment happens later**: `get_aligned_data()` applies alignment (lines 230-234), but by then Kalshi data is already NULL
4. **Trade data has same issue**: Individual trades also stop before game starts (confirmed in Step 9), but the real issue is the timestamp alignment logic

### Impact

- **10 games** (out of 100 tested) fail simulation due to this timing mismatch
- **All games pass the `games_with_kalshi` filter** (they have Kalshi data, just not aligned)
- **Simulation fails** because `get_aligned_data()` filters out rows with `kalshi_price IS NULL`
- **Materialized view includes these games** but with NULL Kalshi fields (0% alignment)
- **Trade data doesn't help**: Individual trades have the same timing issue (stop before game starts)

### Next Steps

1. ✅ **Root cause identified**: Time window mismatch confirmed
2. ⏳ **Compare with successful games**: Check if successful games have overlapping time windows
3. ⏳ **Consider solutions**:
   - Option A: Accept these games as "no Kalshi data" and skip them gracefully
   - Option B: Extend alignment window (but 30-55 min gaps are too large)
   - Option C: Use last available Kalshi price (pre-game closing price) as fallback
   - Option D: Filter out games where Kalshi ends before ESPN starts (tighter `games_with_kalshi` filter)

---

## Recommendations

### Immediate Fix: Graceful Handling

**Current behavior**: Simulation crashes with `TypeError` when `kalshi_price` is `None`

**Recommended fix**: Already implemented in `simulate_trading_strategy.py`:
- ✅ Skip rows where `kalshi_price` or `espn_prob` is `None`
- ✅ Log warnings for skipped data points
- ✅ Continue simulation with available data

**However**: If ALL snapshots are skipped (0% alignment), the simulation returns empty results, which may cause downstream errors.

### Long-term Solutions

#### Option D: Fix Materialized View Time Alignment (CRITICAL FIX REQUIRED)

**The materialized view needs to apply the time alignment logic described in the README.**

The materialized view should:
1. **Calculate game start and duration** from `espn.scoreboard_games`
2. **Shift ESPN timestamps** to align with game start (preserve relative timing)
3. **Filter Kalshi candlesticks** to game window `[game_start, game_start + duration]`
4. **Match aligned ESPN timestamps** to filtered Kalshi timestamps within 60 seconds

**Implementation**:
- Add CTE to calculate game start and first ESPN timestamp
- Shift `snapshot_ts` in `espn_base` CTE: `game_start + (snapshot_ts - first_snapshot_ts)`
- Filter Kalshi candlesticks in LATERAL JOIN: `period_ts >= game_start AND period_ts <= (game_start + duration)`
- Match using aligned timestamps

**Pros**:
- ✅ Fixes root cause (time alignment)
- ✅ Matches README specification
- ✅ Enables alignment for games with pre-game Kalshi markets
- ✅ Consistent with `get_aligned_data()` logic

**Cons**:
- Requires rebuilding materialized view
- More complex SQL (but necessary for correctness)

#### Option A: Tighter `games_with_kalshi` Filter (WORKAROUND - NOT RECOMMENDED)

**Add time overlap check to filter**:
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
      -- NEW: Require time overlap with ESPN snapshots
      AND EXISTS (
        SELECT 1
        FROM espn.probabilities_raw_items p
        WHERE p.game_id = mwg.espn_event_id
          AND EXISTS (
            SELECT 1
            FROM kalshi.candlesticks c2
            WHERE c2.ticker = mwg.ticker
              AND c2.yes_bid_close IS NOT NULL
              AND c2.yes_ask_close IS NOT NULL
              AND c2.period_ts BETWEEN p.last_modified_utc - INTERVAL '60 seconds'
                                   AND p.last_modified_utc + INTERVAL '60 seconds'
          )
      )
)
```

**Pros**: 
- Only includes games with actual alignable data
- Prevents wasted computation on games that will fail

**Cons**:
- More complex filter (may be slower)
- Requires rebuilding materialized view

#### Option B: Use Last Available Kalshi Price (Fallback) - NOT RECOMMENDED

**Modify LATERAL JOIN** to use last pre-game price if no in-game alignment:
```sql
LEFT JOIN LATERAL (
    SELECT c.*
    FROM kalshi.markets_with_games mwg
    JOIN kalshi.candlesticks c ON c.ticker = mwg.ticker
    WHERE mwg.espn_event_id = ewd.game_id
      AND mwg.kalshi_team_side = 'home'
      AND c.yes_bid_close IS NOT NULL
      AND c.yes_ask_close IS NOT NULL
      AND (
        -- Try in-game alignment first (within 60 seconds)
        c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                         AND ewd.snapshot_ts + INTERVAL '60 seconds'
        OR
        -- Fallback: Use last pre-game price if no in-game match
        (c.period_ts < ewd.snapshot_ts AND NOT EXISTS (
          SELECT 1 FROM kalshi.candlesticks c2
          WHERE c2.ticker = mwg.ticker
            AND c2.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                                 AND ewd.snapshot_ts + INTERVAL '60 seconds'
        ))
      )
    ORDER BY 
      CASE WHEN c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                                   AND ewd.snapshot_ts + INTERVAL '60 seconds'
           THEN 0 ELSE 1 END,  -- Prefer in-game alignment
      ABS(EXTRACT(EPOCH FROM (c.period_ts - ewd.snapshot_ts))),
      c.period_ts DESC
    LIMIT 1
) kh ON true
```

**Pros**:
- Provides some Kalshi data even for pre-game markets
- May be useful for pre-game analysis

**Cons**:
- Pre-game prices may not reflect in-game probabilities (30-57 minute gap)
- Could introduce significant bias if pre-game prices are stale
- **Trade data confirms**: Pre-game prices stop 30-57 minutes before game starts
- **Not recommended**: Stale pre-game prices are not useful for in-game trading strategy

#### Option C: Accept and Document

**Document this limitation**:
- Some games have Kalshi pre-game markets but no in-game alignment
- These games are automatically skipped in simulation
- This is expected behavior, not a bug

**Pros**:
- No code changes needed
- Clear documentation of limitation

**Cons**:
- 10% of games fail (may be acceptable)

### Recommended Approach

**CRITICAL FIX REQUIRED**: The materialized view needs to apply the time alignment logic described in the README.

**Option D: Fix Materialized View Time Alignment** (RECOMMENDED):

The materialized view should:
1. **Calculate game start and duration** from `espn.scoreboard_games`
2. **Shift ESPN timestamps** to align with game start (preserve relative timing)
3. **Filter Kalshi candlesticks** to game window `[game_start, game_start + duration]`
4. **Match aligned ESPN timestamps** to filtered Kalshi timestamps within 60 seconds

**Implementation**:
- Add CTE to calculate game start and first ESPN timestamp
- Shift `snapshot_ts` in `espn_base` CTE: `game_start + (snapshot_ts - first_snapshot_ts)`
- Filter Kalshi candlesticks in LATERAL JOIN: `period_ts >= game_start AND period_ts <= (game_start + duration)`
- Match using aligned timestamps

**Pros**:
- ✅ Fixes root cause (time alignment)
- ✅ Matches README specification
- ✅ Enables alignment for games with pre-game Kalshi markets
- ✅ Consistent with `get_aligned_data()` logic

**Cons**:
- Requires rebuilding materialized view
- More complex SQL (but necessary for correctness)

**Short-term**: Option C (accept and document) - Current behavior is incorrect but documented

**Long-term**: Option D (fix time alignment) - Required for correctness

### Key Finding: Trade Data Doesn't Solve the Problem

**Question**: Do we have trade data (individual trades, not just candlesticks) for these games?

**Answer**: ✅ **Yes, we have trade data** (10,000-40,000 trades per game), but:
- ❌ **Trades have the same timing issue** as candlesticks (stop before game starts)
- ❌ **Trade data cannot bridge the gap** because there are no trades during the game
- ❌ **Pre-game trade prices are stale** (30-57 minutes old) and not useful for in-game trading

**However**: The real issue is **not** trade data availability. The real issue is that **the materialized view is not applying the time alignment logic described in the README**. Even if we had in-game trades, the materialized view wouldn't match them correctly because it's using raw timestamps instead of aligned timestamps.

**Conclusion**: The materialized view needs to be fixed to apply ESPN timestamp shifting and Kalshi window filtering as specified in the README.

### Next Steps

1. ✅ Root cause identified and documented
2. ⏳ Compare with successful games to confirm pattern
3. ⏳ Decide on solution (recommend Option A for long-term)
4. ⏳ Update `games_with_kalshi` filter if Option A chosen
5. ⏳ Rebuild materialized view if filter updated

---

## References

- `webapp/api/endpoints/simulation.py`: Bulk simulation endpoint (lines 141-450)
- `scripts/simulate_trading_strategy.py`: `get_aligned_data()` function (lines 82-287)
- `derived.snapshot_features_v1`: Canonical dataset materialized view
- `cursor-files/analysis/2026-01-04-kalshi-data-coverage-analysis/kalshi_data_coverage_analysis.md`: Previous analysis on missing Kalshi data

