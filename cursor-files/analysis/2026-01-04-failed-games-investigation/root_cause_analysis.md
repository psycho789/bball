# Root Cause Analysis: Games 401810277 and 401810250

**Date**: 2026-01-04  
**Games**: `401810277`, `401810250`  
**Status**: Still failing after time alignment fix

---

## Critical Finding

**ESPN first snapshot occurs 3+ hours AFTER game start, but alignment shifts it to game start, creating a mismatch with Kalshi data.**

### The Problem

**Game 401810250**:
- **Game start**: `2025-12-20 19:30:00-08` (scheduled tip-off)
- **ESPN first RAW**: `2025-12-20 22:40:00-08` (3h 10m AFTER game start)
- **ESPN last RAW**: `2025-12-21 01:25:00-08`
- **ESPN duration**: ~2h 45m
- **Kalshi window** (after alignment): `19:30:00-08` to `22:15:00-08` (2h 45m)
- **Kalshi data**: `2025-12-19 16:00:00-08` to `2025-12-20 22:01:00-08`

**What happens**:
1. Materialized view calculates `game_duration_seconds` = `MAX(espn_last_raw) - MIN(espn_first_raw)` = ~2h 45m
2. Kalshi window is set to: `[game_start, game_start + 2h 45m]` = `[19:30:00, 22:15:00]`
3. Kalshi data ends at `22:01:00-08` (14 minutes BEFORE window end)
4. ESPN snapshots are aligned to start at `19:30:00-08` (game start)
5. **BUT**: Kalshi candlesticks stop at `22:01:00-08`, and ESPN aligned snapshots go until `22:15:00-08`
6. **Result**: Many ESPN snapshots (after 22:01:00) have no matching Kalshi data

**Game 401810277**:
- **Game start**: `2025-12-23 19:30:00-08`
- **ESPN first RAW**: `2025-12-23 22:42:00-08` (3h 12m AFTER game start)
- **ESPN last RAW**: `2025-12-24 01:00:00-08`
- **ESPN duration**: ~2h 18m
- **Kalshi window**: `19:30:00-08` to `21:48:00-08` (2h 18m)
- **Kalshi data**: `2025-12-22 16:00:00-08` to `2025-12-23 22:01:00-08`

**What happens**:
1. Kalshi window ends at `21:48:00-08` (based on ESPN duration)
2. Kalshi data ends at `22:01:00-08` (13 minutes AFTER window end)
3. **BUT**: Kalshi data starts BEFORE window start (pre-game data)
4. **Result**: Kalshi data exists outside the calculated window, but LATERAL JOIN filters it out

---

## Root Cause

**The Kalshi window calculation is incorrect when ESPN starts recording AFTER game start.**

### Current Logic (WRONG):
```sql
game_duration_seconds = MAX(espn_last_raw) - MIN(espn_first_raw)
kalshi_window_end = game_start + game_duration_seconds
```

**Problem**: This assumes ESPN recording window matches the game window, but ESPN may start recording hours after game start.

### Correct Logic (per README):
The README says:
> "Calculate game duration: `MAX(last_modified_utc) - MIN(last_modified_utc)` from ESPN data. This represents how long ESPN was recording probabilities (typically 2-3 hours for a full game)."

**But**: The Kalshi window should be based on **when the game actually happened**, not when ESPN recorded it.

---

## The Real Issue

**These games may have been delayed or ESPN started recording late.**

Looking at the data:
- Game 401810250: Scheduled `19:30:00`, ESPN starts `22:40:00` (3h 10m delay)
- Game 401810277: Scheduled `19:30:00`, ESPN starts `22:42:00` (3h 12m delay)

**Possible causes**:
1. **Game was delayed** (tip-off happened later than scheduled)
2. **ESPN API issue** (didn't start recording until later)
3. **Data collection gap** (missed early game data)

**But**: The Kalshi data shows:
- Game 401810250: Kalshi ends at `22:01:00-08` (matches game end time)
- Game 401810277: Kalshi ends at `22:01:00-08` (matches game end time)

**This suggests**: The games actually ended around `22:00:00-08`, which is ~2h 30m after scheduled start. This is normal for NBA games (they take ~2.5 hours).

---

## The Fix

**The `kalshi_window_info` CTE should correctly calculate the actual Kalshi data range, and the LATERAL JOIN must use it instead of ESPN duration.**

### Current Issue

Looking at the query results:
- **Game 401810250**: Kalshi ends at `22:01:00`, but window ends at `22:15:00` (based on ESPN duration)
- **Game 401810277**: Kalshi ends at `22:01:00`, but window ends at `21:48:00` (based on ESPN duration)

**Problem**: The `kalshi_window_info` CTE exists in the fix document, but either:
1. It's not calculating correctly (FILTER clause issue?)
2. The LATERAL JOIN is still using `espn_duration_seconds` instead of `kalshi_window_end`
3. The CTE isn't being joined correctly

### Diagnostic Query

Run this to check what `kalshi_window_info` actually calculates:

```sql
WITH game_time_info AS (
    SELECT 
        sg.event_id AS game_id,
        sg.event_date AS game_start
    FROM espn.scoreboard_games sg
    WHERE sg.event_id IN ('401810277', '401810250')
),
kalshi_window_info AS (
    SELECT 
        kmw.espn_event_id AS game_id,
        MIN(kc.period_ts) FILTER (WHERE kc.period_ts >= gti.game_start AND kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL) AS kalshi_window_start,
        MAX(kc.period_ts) FILTER (WHERE kc.period_ts >= gti.game_start AND kc.yes_bid_close IS NOT NULL AND kc.yes_ask_close IS NOT NULL) AS kalshi_window_end
    FROM game_time_info gti
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gti.game_id
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    GROUP BY kmw.espn_event_id
)
SELECT 
    game_id,
    kalshi_window_start,
    kalshi_window_end
FROM kalshi_window_info
ORDER BY game_id;
```

**Expected**: Should show `kalshi_window_end = 22:01:00-08` for both games (actual Kalshi data end time).

**ACTUAL RESULT**: ✅ `kalshi_window_info` calculates correctly:
- Game 401810250: `19:30:00-08` to `22:01:00-08`
- Game 401810277: `19:30:00-08` to `22:01:00-08`

**BUT**: The second diagnostic query returns **0 rows** - meaning NO Kalshi candlesticks are within 5 minutes of ANY aligned ESPN snapshot!

**This means**: The aligned ESPN timestamps and Kalshi timestamps are not overlapping, even though both exist in the correct time window.

---

## The Real Problem

**The alignment logic is shifting ESPN timestamps incorrectly, or the Kalshi candlesticks don't exist at the times we expect.**

### Hypothesis 1: ESPN Alignment Issue

ESPN snapshots are being aligned using:
```sql
snapshot_ts = game_start + (raw_snapshot_ts - first_espn_ts)
```

For Game 401810250:
- `game_start` = `19:30:00-08`
- `first_espn_ts` = `22:40:00-08` (3h 10m after game start)
- First aligned snapshot: `19:30:00 + (22:40:00 - 22:40:00)` = `19:30:00` ✅

But if ESPN was recording snapshots every ~1 minute starting at 22:40:00, and the game actually started at 19:30:00, then:
- The first ESPN snapshot (at 22:40:00) should align to `19:30:00 + 0` = `19:30:00`
- The second ESPN snapshot (at 22:41:00) should align to `19:30:00 + 1 minute` = `19:31:00`
- And so on...

**Problem**: If the game actually ended at ~22:00:00 (based on Kalshi data ending at 22:01:00), then ESPN snapshots starting at 22:40:00 are AFTER the game ended!

### Hypothesis 2: Kalshi Data Gap

Kalshi candlesticks might not exist at the exact times we're looking for. Let's check if Kalshi has data during the aligned ESPN snapshot times.

### Next Diagnostic Query

Check what the actual aligned ESPN snapshot timestamps are, and what Kalshi timestamps exist:

```sql
-- Check aligned ESPN snapshot timestamps vs available Kalshi timestamps
WITH aligned_espn AS (
    SELECT DISTINCT
        game_id,
        snapshot_ts as aligned_ts
    FROM derived.snapshot_features_v1
    WHERE game_id IN ('401810277', '401810250')
    ORDER BY game_id, aligned_ts
    LIMIT 20
),
available_kalshi AS (
    SELECT DISTINCT
        kmw.espn_event_id as game_id,
        kc.period_ts as kalshi_ts
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    WHERE kmw.espn_event_id IN ('401810277', '401810250')
      AND kmw.kalshi_team_side = 'home'
      AND kc.yes_bid_close IS NOT NULL
      AND kc.yes_ask_close IS NOT NULL
      AND kc.period_ts >= (
        SELECT event_date FROM espn.scoreboard_games WHERE event_id = kmw.espn_event_id LIMIT 1
      )
    ORDER BY kmw.espn_event_id, kc.period_ts
    LIMIT 20
)
SELECT 
    'ALIGNED_ESPN' as source,
    ae.game_id,
    ae.aligned_ts as timestamp
FROM aligned_espn ae
UNION ALL
SELECT 
    'KALSHI' as source,
    ak.game_id,
    ak.kalshi_ts as timestamp
FROM available_kalshi ak
ORDER BY game_id, timestamp;
```

This will show us if there's a time gap between aligned ESPN snapshots and available Kalshi candlesticks.

---

## Critical Discovery

**The aligned ESPN snapshots and Kalshi candlesticks are NOT overlapping in time!**

From the diagnostic queries:
- ✅ `kalshi_window_info` calculates correctly: `19:30:00-08` to `22:01:00-08`
- ❌ **0 Kalshi candlesticks are within 5 minutes of ANY aligned ESPN snapshot**

**This means**: Even though both ESPN and Kalshi data exist, they're not aligning because:
1. ESPN snapshots are being aligned to start at `game_start` (19:30:00)
2. But ESPN actually started recording at 22:40:00 (3h 10m AFTER game start)
3. So aligned ESPN snapshots span `[19:30:00, 22:15:00]` (shifted timeline)
4. Kalshi candlesticks span `[19:30:00, 22:01:00]` (actual game time)
5. **BUT**: The aligned ESPN snapshots at 19:30:00-19:31:00 etc. don't correspond to actual game events - ESPN wasn't recording then!

**The Problem**: When ESPN starts recording AFTER the game starts, aligning ESPN snapshots to `game_start` creates fake timestamps for periods when ESPN wasn't recording. Kalshi data exists at the actual game times, but there's no ESPN data to align with during those times.

**The Solution**: We need to check if ESPN snapshots actually overlap with Kalshi data in REAL time (not aligned time), and only align snapshots that have corresponding Kalshi data.

---

## Next Diagnostic Query

Run this to see what the actual aligned ESPN snapshot timestamps are vs available Kalshi timestamps:

```sql
-- Check aligned ESPN snapshot timestamps vs available Kalshi timestamps
WITH aligned_espn AS (
    SELECT DISTINCT
        game_id,
        snapshot_ts as aligned_ts
    FROM derived.snapshot_features_v1
    WHERE game_id IN ('401810277', '401810250')
    ORDER BY game_id, aligned_ts
    LIMIT 20
),
available_kalshi AS (
    SELECT DISTINCT
        kmw.espn_event_id as game_id,
        kc.period_ts as kalshi_ts
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.candlesticks kc ON kc.ticker = kmw.ticker
    WHERE kmw.espn_event_id IN ('401810277', '401810250')
      AND kmw.kalshi_team_side = 'home'
      AND kc.yes_bid_close IS NOT NULL
      AND kc.yes_ask_close IS NOT NULL
      AND kc.period_ts >= (
        SELECT event_date FROM espn.scoreboard_games WHERE event_id = kmw.espn_event_id LIMIT 1
      )
    ORDER BY kmw.espn_event_id, kc.period_ts
    LIMIT 20
)
SELECT 
    'ALIGNED_ESPN' as source,
    ae.game_id,
    ae.aligned_ts as timestamp
FROM aligned_espn ae
UNION ALL
SELECT 
    'KALSHI' as source,
    ak.game_id,
    ak.kalshi_ts as timestamp
FROM available_kalshi ak
ORDER BY game_id, timestamp;
```

This will show us if there's a time gap between aligned ESPN snapshots and available Kalshi candlesticks.

### Option 1: Use Kalshi data range to determine game window (RECOMMENDED)

Instead of using ESPN duration, use when Kalshi markets were actually active:

```sql
kalshi_window_start = game_start
kalshi_window_end = MAX(kalshi.period_ts) WHERE period_ts >= game_start
```

### Option 2: Extend Kalshi window to include all available data

```sql
kalshi_window_start = MIN(kalshi.period_ts)  -- Include pre-game
kalshi_window_end = MAX(kalshi.period_ts)    -- Include all available
```

### Option 3: Use a fixed game duration (2.5 hours typical)

```sql
kalshi_window_end = game_start + INTERVAL '2.5 hours'
```

---

## Recommended Solution

**Use Kalshi data to determine the actual game window**, since Kalshi markets close when the game ends:

```sql
-- In kalshi_aligned CTE, filter to actual Kalshi data range
AND c.period_ts >= ewd.game_start
AND c.period_ts <= (
    SELECT MAX(c2.period_ts)
    FROM kalshi.markets_with_games mwg2
    JOIN kalshi.candlesticks c2 ON c2.ticker = mwg2.ticker
    WHERE mwg2.espn_event_id = ewd.game_id
      AND c2.period_ts >= ewd.game_start
      AND c2.yes_bid_close IS NOT NULL
      AND c2.yes_ask_close IS NOT NULL
)
```

This ensures we use the actual game window (when Kalshi markets were active), not the ESPN recording window.

