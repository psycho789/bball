# Query Execution Locations

## Call Chain Overview

```
1. API Endpoint: webapp/api/endpoints/simulation.py
   └─> get_simulation_results() [line 51]
       └─> get_aligned_data() [line 83]
           └─> Multiple queries executed here
```

---

## Query 1: ESPN Check Query
**Location:** `scripts/simulate_trading_strategy.py:113`
```python
espn_count = conn.execute(espn_check_sql, (game_id,)).fetchone()[0]
```

**Called from:** `get_aligned_data()` function at line 82
**SQL:**
```sql
SELECT COUNT(*) 
FROM espn.probabilities_raw_items 
WHERE game_id = %s
```

---

## Query 2: Game Info Query
**Location:** `scripts/simulate_trading_strategy.py:143`
```python
game_row = conn.execute(game_info_sql, (game_id,)).fetchone()
```

**Called from:** `get_aligned_data()` function at line 82
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
GROUP BY sg.event_date
```

---

## Query 2b: Fallback Query (if game_info fails)
**Location:** `scripts/simulate_trading_strategy.py:154`
```python
fallback_row = conn.execute(fallback_sql, (game_id,)).fetchone()
```

**Called from:** `get_aligned_data()` function at line 82 (conditional fallback)
**SQL:**
```sql
SELECT 
    EXTRACT(EPOCH FROM (MAX(last_modified_utc) - MIN(last_modified_utc)))::INTEGER as duration_seconds,
    MIN(last_modified_utc) as first_timestamp
FROM espn.probabilities_raw_items
WHERE game_id = %s
```

---

## Query 2c: Outcome Query (if scores missing)
**Location:** `scripts/simulate_trading_strategy.py:177`
```python
outcome_row = conn.execute(outcome_sql, (game_id,)).fetchone()
```

**Called from:** `get_aligned_data()` function at line 82 (conditional fallback)
**SQL:**
```sql
SELECT 
    MAX(home_score) as final_home_score,
    MAX(away_score) as final_away_score
FROM espn.scoreboard_games
WHERE event_id = %s
```

---

## Query 3: ESPN Data Query
**Location:** `scripts/simulate_trading_strategy.py:193`
```python
espn_rows = conn.execute(espn_sql, (game_id,)).fetchall()
```

**Called from:** `get_aligned_data()` function at line 82
**SQL:**
```sql
SELECT 
    p.last_modified_utc,
    p.home_win_percentage,
    p.away_win_percentage
FROM espn.probabilities_raw_items p
WHERE p.game_id = %s
ORDER BY p.last_modified_utc
```

---

## Query 4: Kalshi Candlestick Data (THE SLOW ONE)
**Location:** `scripts/simulate_trading_strategy.py:427`
```python
kalshi_rows = conn.execute(kalshi_sql, (game_id, game_id)).fetchall()
```

**Called from:** `_get_kalshi_candlestick_data()` function at line 376
**Which is called from:** `get_aligned_data()` at line 202 (when `use_trade_data=False`)

**SQL:** (See Query 4 in test_queries.sql - the complex CTE query)

---

## Query 5: Markets Query (for trade data path)
**Location:** `scripts/simulate_trading_strategy.py:468`
```python
market_rows = conn.execute(markets_sql, (game_id,)).fetchall()
```

**Called from:** `_get_kalshi_trade_data()` function at line 431
**Which is called from:** `get_aligned_data()` at line 199 (when `use_trade_data=True`)

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

---

## Query 6: Trades Fetch Query (for trade data path)
**Location:** `webapp/api/utils/trade_candles.py:71`
```python
rows = conn.execute(sql, (ticker, start_dt, end_dt)).fetchall()
```

**Called from:** `fetch_trades()` function at line 23
**Which is called from:** `_get_kalshi_trade_data()` at line 488 (inside a loop for each ticker)
**Which is called from:** `get_aligned_data()` at line 199 (when `use_trade_data=True`)

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

**Note:** This query runs ONCE PER TICKER (typically 2 tickers per game: home and away markets)

---

## Entry Points

### Single Game Simulation
**File:** `webapp/api/endpoints/simulation.py`
**Function:** `get_simulation_results()` [line 51]
**Route:** `GET /api/games/{game_id}/simulation`
**Calls:** `get_aligned_data()` at line 83

### Bulk Simulation
**File:** `webapp/api/endpoints/simulation.py`
**Function:** `get_bulk_simulation_results()` [line 138]
**Route:** `GET /api/simulation/bulk`
**Calls:** `process_game()` at line 252, which calls `get_aligned_data()` at line 296

---

## Summary

**Total queries per game (candlestick path):**
1. ESPN check (line 113)
2. Game info (line 143)
3. ESPN data (line 193)
4. Kalshi candlestick (line 427) ← **LIKELY BOTTLENECK**

**Total queries per game (trade data path):**
1. ESPN check (line 113)
2. Game info (line 143)
3. ESPN data (line 193)
4. Markets query (line 468)
5. Trades fetch (line 71 in trade_candles.py) × N tickers (usually 2)

**Most likely bottleneck:** Query 4 (Kalshi candlestick) at line 427 in `_get_kalshi_candlestick_data()`

