# Grid Search SQL Queries - With Example Values

This document lists all SQL queries executed during grid search, with example values so you can test them directly.

## Query Execution Flow

For each game, `get_aligned_data()` executes these queries in order:

1. **ESPN Check Query** - Verify ESPN data exists
2. **Game Info Query** - Get game start time and duration
3. **Outcome Query** (fallback) - Get final scores
4. **ESPN Data Query** - Get all ESPN probability records
5. **Kalshi Data Query** - Either candlestick OR trade data (depending on `use_trade_data` flag)

---

## Query 1: ESPN Check Query

**Location:** `scripts/simulate_trading_strategy.py:108-113`

**Purpose:** Verify ESPN probability data exists for the game

**SQL:**
```sql
SELECT COUNT(*) 
FROM espn.probabilities_raw_items 
WHERE game_id = %s AND season_label = '2025-26'
```

**Example with actual values:**
```sql
SELECT COUNT(*) 
FROM espn.probabilities_raw_items 
WHERE game_id = '401809236' AND season_label = '2025-26'
```

**Expected result:** Integer count (should be > 0)

---

## Query 2: Game Info Query

**Location:** `scripts/simulate_trading_strategy.py:121-134`

**Purpose:** Get game start time, duration, and outcome from joined tables

**SQL:**
```sql
SELECT 
    sg.event_date as game_start,
    EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as duration_seconds,
    MAX(pe.final_winning_team) as winner,
    MAX(pe.home_score) as final_home_score,
    MAX(pe.away_score) as final_away_score
FROM espn.probabilities_raw_items p
LEFT JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
LEFT JOIN espn.prob_event_state pe ON p.game_id = pe.game_id
WHERE p.game_id = %s 
AND p.season_label = '2025-26'
GROUP BY game_start
```

**Example with actual values:**
```sql
SELECT 
    sg.event_date as game_start,
    EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as duration_seconds,
    MAX(pe.final_winning_team) as winner,
    MAX(pe.home_score) as final_home_score,
    MAX(pe.away_score) as final_away_score
FROM espn.probabilities_raw_items p
LEFT JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
LEFT JOIN espn.prob_event_state pe ON p.game_id = pe.game_id
WHERE p.game_id = '401809236' 
AND p.season_label = '2025-26'
GROUP BY game_start
```

**Expected result:** One row with game_start (TIMESTAMPTZ), duration_seconds (INTEGER), winner, scores

---

## Query 2b: Fallback Duration Query

**Location:** `scripts/simulate_trading_strategy.py:148-155`

**Purpose:** Calculate duration from ESPN data if game_info query fails

**SQL:**
```sql
SELECT 
    EXTRACT(EPOCH FROM (MAX(last_modified_utc) - MIN(last_modified_utc)))::INTEGER as duration_seconds,
    MIN(last_modified_utc) as first_timestamp
FROM espn.probabilities_raw_items
WHERE game_id = %s
AND season_label = '2025-26'
```

**Example with actual values:**
```sql
SELECT 
    EXTRACT(EPOCH FROM (MAX(last_modified_utc) - MIN(last_modified_utc)))::INTEGER as duration_seconds,
    MIN(last_modified_utc) as first_timestamp
FROM espn.probabilities_raw_items
WHERE game_id = '401809236'
AND season_label = '2025-26'
```

---

## Query 3: Outcome Query (Fallback)

**Location:** `scripts/simulate_trading_strategy.py:137-143`

**Purpose:** Get final scores from scoreboard_games if not in game_info query

**SQL:**
```sql
SELECT 
    MAX(home_score) as final_home_score,
    MAX(away_score) as final_away_score
FROM espn.scoreboard_games
WHERE event_id = %s
```

**Example with actual values:**
```sql
SELECT 
    MAX(home_score) as final_home_score,
    MAX(away_score) as final_away_score
FROM espn.scoreboard_games
WHERE event_id = '401809236'
```

---

## Query 4: ESPN Data Query

**Location:** `scripts/simulate_trading_strategy.py:186-195`

**Purpose:** Get all ESPN probability records for the game

**SQL:**
```sql
SELECT 
    p.last_modified_utc,
    p.home_win_percentage,
    p.away_win_percentage
FROM espn.probabilities_raw_items p
WHERE p.game_id = %s 
AND p.season_label = '2025-26'
ORDER BY p.last_modified_utc
```

**Example with actual values:**
```sql
SELECT 
    p.last_modified_utc,
    p.home_win_percentage,
    p.away_win_percentage
FROM espn.probabilities_raw_items p
WHERE p.game_id = '401809236' 
AND p.season_label = '2025-26'
ORDER BY p.last_modified_utc
```

**Expected result:** Multiple rows (typically 100-500+ records per game)

**Performance note:** This query can be slow if there are many records and no index on `(game_id, season_label, last_modified_utc)`

---

## Query 5: Kalshi Candlestick Data Query (THE SLOW ONE)

**Location:** `scripts/simulate_trading_strategy.py:390-436`

**Purpose:** Get Kalshi candlestick data for all markets associated with the game

**SQL:**
```sql
WITH p_bounds AS (
    SELECT
        game_id,
        MIN(last_modified_utc) AS min_ts,
        MAX(last_modified_utc) AS max_ts
    FROM espn.probabilities_raw_items
    WHERE game_id = %s
    AND season_label = '2025-26'
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
    WHERE kmw.espn_event_id = %s
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
ORDER BY gm.kalshi_team_side, c.period_ts
```

**Example with actual values:**
```sql
WITH p_bounds AS (
    SELECT
        game_id,
        MIN(last_modified_utc) AS min_ts,
        MAX(last_modified_utc) AS max_ts
    FROM espn.probabilities_raw_items
    WHERE game_id = '401809236'
    AND season_label = '2025-26'
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
    WHERE kmw.espn_event_id = '401809236'
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
ORDER BY gm.kalshi_team_side, c.period_ts
```

**Note:** This query uses `game_id` twice (once for p_bounds, once for game_markets WHERE clause)

**Performance issues:**
- **CROSS JOIN** between `espn_game_info` and `kalshi.markets_with_games` - can be expensive
- **DISTINCT ON** with `ORDER BY` requires sorting
- **JOIN** on `kalshi.candlesticks` with time range filter - needs index on `(ticker, period_ts)`
- **Time range filter** with interval arithmetic - PostgreSQL needs to evaluate this for each row

**Expected result:** Multiple rows (typically 100-200+ candlesticks per game, 2 markets = home + away)

---

## Query 6: Markets Query (for Trade Data Path)

**Location:** `scripts/simulate_trading_strategy.py:469-477`

**Purpose:** Get Kalshi market tickers for the game (used when `use_trade_data=True`)

**SQL:**
```sql
SELECT DISTINCT ON (kmw.ticker)
    kmw.ticker,
    kmw.kalshi_team_side
FROM kalshi.markets_with_games kmw
WHERE kmw.espn_event_id = %s
  AND kmw.kalshi_team_side IS NOT NULL
ORDER BY kmw.ticker, kmw.snapshot_id DESC
```

**Example with actual values:**
```sql
SELECT DISTINCT ON (kmw.ticker)
    kmw.ticker,
    kmw.kalshi_team_side
FROM kalshi.markets_with_games kmw
WHERE kmw.espn_event_id = '401809236'
  AND kmw.kalshi_team_side IS NOT NULL
ORDER BY kmw.ticker, kmw.snapshot_id DESC
```

**Expected result:** Typically 2 rows (one for 'home', one for 'away')

---

## Query 7: Trades Fetch Query (for Trade Data Path)

**Location:** `webapp/api/utils/trade_candles.py:55-69`

**Purpose:** Fetch trades for a specific ticker within a time window

**SQL:**
```sql
SELECT 
    created_time,
    yes_price,
    no_price,
    count,
    price,
    taker_side,
    trade_id
FROM kalshi.trades
WHERE ticker = %s
  AND created_time >= %s
  AND created_time < %s
ORDER BY created_time ASC
```

**Example with actual values:**
```sql
SELECT 
    created_time,
    yes_price,
    no_price,
    count,
    price,
    taker_side,
    trade_id
FROM kalshi.trades
WHERE ticker = 'KXNBAGAME-25NOV30OKCPOR-POR'
  AND created_time >= '2025-11-30 00:00:00+00'::timestamptz
  AND created_time < '2025-11-30 03:00:00+00'::timestamptz
ORDER BY created_time ASC
```

**Note:** This query is executed **once per ticker** (typically 2 times per game: home + away)

**Performance issues:**
- Needs index on `(ticker, created_time)` for fast lookups
- With 7M+ trades, this can be slow if index is missing or not optimal

**Expected result:** Variable (could be 0 to thousands of trades per ticker)

---

## Performance Analysis

### Slowest Queries (in order):

1. **Query 5 (Kalshi Candlestick)** - Complex CTE with CROSS JOIN, multiple joins, time range filtering
2. **Query 7 (Trades Fetch)** - Executed 2x per game (home + away tickers), needs good index
3. **Query 4 (ESPN Data)** - Can be slow if many records and no index

### Optimization Recommendations:

1. **Add indexes:**
   ```sql
   -- For Query 4 (ESPN data)
   CREATE INDEX IF NOT EXISTS idx_espn_prob_game_season_time 
   ON espn.probabilities_raw_items(game_id, season_label, last_modified_utc);
   
   -- For Query 5 (Kalshi candlesticks)
   CREATE INDEX IF NOT EXISTS idx_kalshi_candles_ticker_period 
   ON kalshi.candlesticks(ticker, period_ts);
   
   -- For Query 7 (Trades)
   CREATE INDEX IF NOT EXISTS idx_kalshi_trades_ticker_time 
   ON kalshi.trades(ticker, created_time);
   
   -- For Query 6 (Markets)
   CREATE INDEX IF NOT EXISTS idx_markets_with_games_espn_side 
   ON kalshi.markets_with_games(espn_event_id, kalshi_team_side, snapshot_id);
   ```

2. **Consider materialized views** for frequently accessed game-market relationships

3. **Batch queries** - Currently each game queries independently; could batch multiple games

4. **Cache results** - The grid search already caches simulation results, but could also cache aligned data

---

## Testing Individual Queries

To test a query, replace the example `game_id` ('401809236') with an actual game ID from your database:

```sql
-- Find a game ID to test with
SELECT event_id, event_date, home_team, away_team 
FROM espn.scoreboard_games 
WHERE season_label = '2025-26' 
ORDER BY event_date DESC 
LIMIT 10;
```

Then use one of those `event_id` values in the queries above.

