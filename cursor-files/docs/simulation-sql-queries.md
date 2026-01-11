# SQL Queries Executed When Clicking "Simulate" Button

This document contains all SQL queries that run when you click the "Simulate" button on the simulation page, with real data values ready to copy and paste.

## Query Execution Flow

1. **Fetch Games List** - Gets list of games with Kalshi data
2. **For Each Game** (in parallel):
   - Check if game is completed
   - Get game info (start time, scores)
   - Get game duration
   - Query canonical dataset for aligned data

---

## 1. Fetch Games List Query

**Purpose**: Get list of games with both ESPN and Kalshi data, ordered by date (most recent first)

**Executed**: Once at the start, may be called multiple times in batches

```sql
WITH kalshi_games AS MATERIALIZED (
  SELECT DISTINCT km.espn_event_id
  FROM kalshi.markets km
  WHERE km.espn_event_id IS NOT NULL
),
game_stats AS MATERIALIZED (
  SELECT
      p.game_id,
      p.season_label,
      COUNT(*) as prob_count,
      MAX(p.created_at) as last_updated,
      MIN(p.home_win_percentage) as min_prob,
      MAX(p.home_win_percentage) as max_prob,
      AVG(p.home_win_percentage) as mean_prob,
      STDDEV(p.home_win_percentage) as std_dev,
      MAX(p.home_win_percentage) - MIN(p.home_win_percentage) as prob_range
  FROM espn.probabilities_raw_items p
  JOIN kalshi_games kg
    ON kg.espn_event_id = p.game_id
  WHERE p.season_label = '2025-26'
  GROUP BY p.game_id, p.season_label
  HAVING COUNT(*) > 100
),
game_outcomes AS MATERIALIZED (
  SELECT
      COALESCE(pe.game_id, sg.event_id) AS game_id,
      COALESCE(pe.final_home_score, sg.home_score) AS final_home_score,
      COALESCE(pe.final_away_score, sg.away_score) AS final_away_score,
      COALESCE(
        pe.winner,
        CASE
          WHEN sg.home_score > sg.away_score THEN 1
          WHEN sg.away_score > sg.home_score THEN 0
          ELSE NULL
        END
      ) AS winner
  FROM (
      SELECT
          e.game_id,
          MAX(e.home_score) AS final_home_score,
          MAX(e.away_score) AS final_away_score,
          MAX(e.final_winning_team) AS winner
      FROM espn.prob_event_state e
      GROUP BY e.game_id
  ) pe
  FULL OUTER JOIN espn.scoreboard_games sg
    ON pe.game_id = sg.event_id
)
SELECT
    g.game_id,
    g.season_label,
    g.prob_count,
    g.last_updated,
    o.final_home_score,
    o.final_away_score,
    o.winner,
    sg.home_team_abbrev,
    sg.away_team_abbrev,
    sg.home_team_display_name,
    sg.away_team_display_name,
    sg.event_date,
    true AS has_kalshi,
    g.min_prob,
    g.max_prob,
    g.mean_prob,
    g.std_dev,
    g.prob_range
FROM game_stats g
LEFT JOIN game_outcomes o
  ON g.game_id = o.game_id
LEFT JOIN espn.scoreboard_games sg
  ON g.game_id = sg.event_id
WHERE 1=1
  AND (
    (o.final_home_score IS NOT NULL
     AND (o.final_home_score > 0 OR o.final_away_score > 0))
    OR sg.event_id IS NOT NULL
  )
ORDER BY sg.event_date DESC
LIMIT 100
OFFSET 0;
```

**Example Result**: Returns games like `401705759`, `401705760`, `401705761`, etc.

---

## 2. Check if Game is Completed

**Purpose**: Check if a game has final scores (completed games can be cached)

**Executed**: Once per game, before running simulation

**Example Game ID**: `401705759`

```sql
SELECT MAX(e.home_score) as final_home_score, MAX(e.away_score) as final_away_score
FROM espn.prob_event_state e
WHERE e.game_id = '401705759';
```

**Expected Result**: 
- If completed: `(final_home_score, final_away_score)` e.g., `(110, 105)`
- If not completed: `(NULL, NULL)`

---

## 3. Get Game Info (Start Time and Scores)

**Purpose**: Get game start time and final scores from scoreboard

**Executed**: Once per game

**Example Game ID**: `401705759`

```sql
SELECT 
    sg.event_date as game_start,
    sg.home_score as final_home_score,
    sg.away_score as final_away_score
FROM espn.scoreboard_games sg
WHERE sg.event_id = '401705759'
LIMIT 1;
```

**Expected Result**: 
```
game_start: 2025-10-11 23:00:00+00
final_home_score: 110
final_away_score: 105
```

---

## 4. Get Game Duration (Fallback Query)

**Purpose**: If game info query fails, get duration from canonical dataset

**Executed**: Only if Query #3 returns no results

**Example Game ID**: `401705759`

```sql
SELECT 
    MIN(snapshot_ts) as first_ts,
    MAX(snapshot_ts) as last_ts
FROM derived.snapshot_features_v1
WHERE game_id = '401705759' AND season_label = '2025-26';
```

**Expected Result**: 
```
first_ts: 2025-10-11 23:00:00+00
last_ts: 2025-10-12 01:30:00+00
```

---

## 5. Get Game Duration (Normal Query)

**Purpose**: Calculate game duration from canonical dataset

**Executed**: Once per game (if Query #3 succeeds)

**Example Game ID**: `401705759`

```sql
SELECT 
    EXTRACT(EPOCH FROM (MAX(snapshot_ts) - MIN(snapshot_ts)))::INTEGER as duration_seconds
FROM derived.snapshot_features_v1
WHERE game_id = '401705759' AND season_label = '2025-26';
```

**Expected Result**: 
```
duration_seconds: 5400  (90 minutes = 2.5 hours)
```

---

## 6. Main Canonical Dataset Query (Most Important!)

**Purpose**: Get all aligned ESPN and Kalshi data for simulation

**Executed**: Once per game - this is the core query that feeds the simulation

**Example Game ID**: `401705759`

```sql
SELECT 
    snapshot_ts,
    espn_home_prob,
    kalshi_home_mid_price,
    kalshi_home_bid,
    kalshi_home_ask,
    kalshi_away_mid_price,
    kalshi_away_bid,
    kalshi_away_ask,
    time_remaining
FROM derived.snapshot_features_v1
WHERE game_id = '401705759' 
  AND season_label = '2025-26'
ORDER BY sequence_number, snapshot_ts;
```

**Expected Result**: Returns rows like:
```
snapshot_ts: 2025-10-11 23:00:15+00
espn_home_prob: 0.52
kalshi_home_mid_price: 0.51
kalshi_home_bid: 0.50
kalshi_home_ask: 0.52
kalshi_away_mid_price: 0.49
kalshi_away_bid: 0.48
kalshi_away_ask: 0.50
time_remaining: 2700
```

**Note**: This query returns all aligned data points. The simulation then:
- Converts away→home when home data is missing
- Normalizes values to 0-1 range
- Filters by time windows (exclude_first_seconds, exclude_last_seconds)
- Calculates divergence and executes trades

---

## Complete Example: Testing All Queries for One Game

Here's a complete set of queries you can run to test the full flow for game `401705759`:

```sql
-- 1. Check if game is completed
SELECT MAX(e.home_score) as final_home_score, MAX(e.away_score) as final_away_score
FROM espn.prob_event_state e
WHERE e.game_id = '401705759';

-- 2. Get game info
SELECT 
    sg.event_date as game_start,
    sg.home_score as final_home_score,
    sg.away_score as final_away_score
FROM espn.scoreboard_games sg
WHERE sg.event_id = '401705759'
LIMIT 1;

-- 3. Get game duration
SELECT 
    EXTRACT(EPOCH FROM (MAX(snapshot_ts) - MIN(snapshot_ts)))::INTEGER as duration_seconds
FROM derived.snapshot_features_v1
WHERE game_id = '401705759' AND season_label = '2025-26';

-- 4. Get canonical dataset (main query)
SELECT 
    snapshot_ts,
    espn_home_prob,
    kalshi_home_mid_price,
    kalshi_home_bid,
    kalshi_home_ask,
    kalshi_away_mid_price,
    kalshi_away_bid,
    kalshi_away_ask,
    time_remaining
FROM derived.snapshot_features_v1
WHERE game_id = '401705759' 
  AND season_label = '2025-26'
ORDER BY sequence_number, snapshot_ts
LIMIT 10;  -- Just show first 10 rows
```

---

## Query Performance Notes

- **Games List Query**: Can be slow (uses MATERIALIZED CTEs) - typically 1-3 seconds
- **Canonical Dataset Query**: Fast (materialized view) - typically 0.1-0.5 seconds per game
- **Game Info Queries**: Very fast - typically < 0.01 seconds

## Testing Tips

1. **Test with a real game ID**: Use `401705759` or any game ID from the games list query
2. **Check data availability**: Make sure the game has data in `derived.snapshot_features_v1`
3. **Verify season_label**: Always use `'2025-26'` for current season
4. **Check row counts**: The canonical dataset query should return hundreds of rows per game

## Common Issues

- **No rows returned**: Game might not have data in canonical view
- **NULL values**: Some games might only have away market data (will be converted to home in code)
- **Missing scores**: Game might not be completed yet



