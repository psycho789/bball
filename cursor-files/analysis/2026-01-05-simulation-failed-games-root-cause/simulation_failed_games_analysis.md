# Simulation Failed Games Root Cause Analysis

**Date**: January 5, 2026  
**Analysis Type**: Data Investigation  
**Issue**: 62 games failing to return simulation data from bulk simulation endpoint

---

## Executive Summary

**Root Cause Identified**: The materialized view (`derived.snapshot_features_v1`) uses **RAW timestamps** for matching ESPN and Kalshi data, but `probabilities.py` uses **ALIGNED timestamps**. ESPN's `last_modified_utc` is recorded ~3 hours after `game_start`, while Kalshi's `period_ts` is actual wall-clock game time. The MV's 60-second matching window fails because these raw timestamps are hours apart.

**Impact**: Games from Dec 20-27, 2025 (56 regular season) and Oct 10-11, 2025 (6 preseason) cannot be simulated because the canonical dataset has zero Kalshi price data aligned despite both data sources having complete data.

**Fix Required**: Update the materialized view to use **aligned timestamps** like `probabilities.py`:
```sql
-- WRONG (current MV): Uses raw ESPN timestamp
c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds' AND ewd.snapshot_ts + INTERVAL '60 seconds'

-- CORRECT (probabilities.py logic): Align ESPN to game_start first
-- aligned_ts = game_start + (last_modified_utc - first_last_modified_utc)
c.period_ts BETWEEN ewd.aligned_snapshot_ts - INTERVAL '60 seconds' AND ewd.aligned_snapshot_ts + INTERVAL '60 seconds'
```

---

## Failed Game IDs (62 total)

### Regular Season Games (56 games)
```
Dec 20-27, 2025:
401810241, 401810242, 401810243, 401810244, 401810245, 401810246, 401810247, 401810248,
401810249, 401810250, 401810251, 401810252, 401810253, 401810254, 401810255, 401810256,
401810257, 401810258, 401810259, 401810260, 401810261, 401810262, 401810263, 401810264,
401810265, 401810266, 401810267, 401810268, 401810269, 401810270, 401810271, 401810272,
401810273, 401810274, 401810275, 401810276, 401810277, 401810278, 401810279, 401810281,
401810282, 401810283, 401810284, 401810285, 401810286, 401810287, 401810288, 401810289,
401810291, 401810292, 401810293, 401810294

Dec 25 (Christmas Day):
401809238, 401809239, 401809240, 401809241
```

### Preseason Games (6 games)
```
Oct 10-11, 2025:
401812697, 401812698, 401812699, 401812700, 401812701, 401812702
```

---

## Investigation Methodology

### Data Pipeline Verification

Verified each stage of the data pipeline to locate the failure point:

| Stage | Table/View | Status | Evidence |
|-------|------------|--------|----------|
| 1. ESPN Scoreboard | `espn.scoreboard_games` | ✅ PASS | All 62 games exist |
| 2. ESPN Probability Data | `espn.probabilities_raw_items` | ✅ PASS | All 62 games have 400-570 probability points |
| 3. Kalshi Market Records | `kalshi.markets_with_games` | ✅ PASS | All 62 games have 2 market tickers (home/away) |
| 4. Kalshi Candlestick Data | `kalshi.candlesticks` | ✅ PASS | All 62 games have 400-2500+ candlesticks |
| 5. Canonical Dataset | `derived.snapshot_features_v1` | ❌ **FAIL** | All 62 games have 0 Kalshi data aligned |

**Design Pattern**: Sequential verification following data flow  
**Algorithm**: Stage-by-stage validation  
**Big O Complexity**: O(1) per stage - direct query verification

---

## Root Cause Analysis

### The Problem: Timestamp Alignment Mismatch

The canonical dataset (`derived.snapshot_features_v1`) and `probabilities.py` use **DIFFERENT** timestamp alignment strategies. The MV's approach is **incorrect** for matching ESPN and Kalshi data.

### Two Different Alignment Strategies

#### 1. probabilities.py (CORRECT approach for visualization AND matching)
```python
# Shifts ESPN timestamps to synthetic game timeline starting at game_start
aligned_timestamp = game_start_timestamp + (espn_recording_timestamp - first_espn_timestamp)
```
- ESPN's first record maps to `game_start`
- Subsequent records maintain relative timing
- Kalshi is filtered to game window (uses actual `period_ts`)
- **Both end up on the same timeline!**

#### 2. Materialized View (INCORRECT approach)
```sql
-- Uses RAW ESPN timestamp (last_modified_utc) - NOT aligned!
AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                    AND ewd.snapshot_ts + INTERVAL '60 seconds'
```
- ESPN `snapshot_ts` = raw `last_modified_utc` (when ESPN's server recorded it)
- Kalshi `period_ts` = actual wall-clock game time
- **These timestamps are ~3 hours apart!**

### Why This Is Wrong

ESPN's `last_modified_utc` is NOT the actual game time - it's when ESPN's system recorded the probability update. The data shows a consistent ~188-193 minute offset between `game_start` and `last_modified_utc`:

| game_id | game_start | ESPN raw start | ESPN offset | Kalshi end | Raw gap |
|---------|------------|----------------|-------------|------------|---------|
| 401809238 | 09:00 | 12:08 | 188 min | 11:51 | 17 min |
| 401810277 | 19:30 | 22:42 | 192 min | 22:01 | 41 min |
| 401810286 | 19:00 | 22:13 | 193 min | 21:41 | 32 min |
| 401810294 | 17:00 | 20:11 | 191 min | 19:26 | 45 min |
| 401812697 | 16:00 | 19:13 | 193 min | 16:51 | 142 min |

### The Smoking Gun Evidence

For game 401809238:
```
ESPN raw last_modified_utc starts at: 12:08 PM
Kalshi candlesticks end at:          11:51 AM
Gap between them:                     17 minutes

MV tries to match within 60 seconds → NO MATCH POSSIBLE

IF ESPN were aligned to game_start (09:00):
  ESPN aligned would start at:        09:00 AM
  Kalshi data exists:                 09:00 AM - 11:51 AM
  → THEY WOULD OVERLAP for ~2.8 hours!
```

**Conclusion**: The materialized view's raw timestamp matching is fundamentally broken. It should align ESPN timestamps to `game_start` before matching with Kalshi, exactly like `probabilities.py` does.

### Visual Representation: The Timestamp Alignment Bug

```
Timeline for Game 401809238 (CLE vs NYK, Dec 25):

                            ACTUAL GAME TIME
                            ===============
Game Start:                 09:00 AM
                              │
Kalshi period_ts:             ├──────────────────────────────┤
(actual wall-clock)           │  Kalshi has data 09:00-11:51 │
                              │  (2h 51m of game coverage)   │
                              └──────────────────────────────┘
                                                        11:51 AM

                            ESPN RAW TIMESTAMPS (wrong timeline!)
                            =====================================
                                                              12:08 PM
                                                                │
ESPN last_modified_utc:                                         ├────────────────────────┤
(server recording time)                                         │ ESPN raw: 12:08-14:46  │
                                                                │ (2h 38m of data)       │
                                                                └────────────────────────┘
                                                                          14:46 PM

                            ↑                                   ↑
                            │       17-minute GAP               │
                            │   (MV sees NO OVERLAP)            │
                            └───────────────────────────────────┘

BUT IF ESPN IS ALIGNED TO GAME_START (probabilities.py logic):
=============================================================
Game Start:                 09:00 AM
                              │
Kalshi period_ts:             ├──────────────────────────────┤
                              │  Kalshi: 09:00-11:51         │
                              └──────────────────────────────┘
                                        │
ESPN ALIGNED:                 ├──────────────────────────────┤
(shifted to game_start)       │  ESPN: 09:00-11:38           │
                              │  (first record → game_start)  │
                              └──────────────────────────────┘
                                        │
                              ←── 2h 38m OVERLAP! ──→

```

### Root Cause Explained

**The fundamental misunderstanding**: The MV comments claim "Both are wall-clock timestamps, so we match directly" - but this is **WRONG**.

1. **Kalshi `period_ts`**: Actual wall-clock time when the market price was observed during the game (e.g., 09:00-11:51)

2. **ESPN `last_modified_utc`**: Wall-clock time when ESPN's **server** recorded the probability - NOT when the game event happened (e.g., 12:08-14:46, ~3 hours after game started)

3. **The ~3 hour offset**: ESPN's system records probabilities with a consistent ~188-193 minute delay from `game_start`. This is likely:
   - Server-side processing delay
   - Batch recording
   - Time zone handling
   - Or ESPN's internal data pipeline timing

4. **Why probabilities.py works**: It normalizes ESPN timestamps:
   ```python
   aligned = game_start + (last_modified - first_last_modified)
   ```
   This maps ESPN's first record to `game_start`, then all subsequent records maintain their relative timing.

**Design Pattern**: Temporal Data Alignment  
**Algorithm**: Timestamp normalization with anchor point (`game_start`)  
**Big O Complexity**: O(n) where n = number of ESPN records to align

---

## Game Categories

### Category 1: Regular Season Games with Misaligned Timestamps (56 games)

**Dates**: December 20-27, 2025

**Characteristics**:
- Games were played (ESPN probability data exists - 400-570 points each)
- Kalshi markets existed and had trading activity
- **Kalshi has full game coverage** (candlesticks from game_start onwards)
- **MV fails to match** because it uses raw ESPN timestamps vs Kalshi's actual game time

**Sample Analysis**:
```sql
-- Game 401809238 (CLE vs NYK, Dec 25)
ESPN probability points: 486
Kalshi candlestick count: 4,822 (across 2 tickers)
Kalshi data (actual game time): Dec 25 09:00 - Dec 25 11:51 (2h 51m coverage)
ESPN raw last_modified:         Dec 25 12:08 - Dec 25 14:46 (3h offset from game_start!)
ESPN aligned (should be):       Dec 25 09:00 - Dec 25 11:38 (game timeline)
ACTUAL OVERLAP (if aligned):    2h 38m of data could be matched!
MV RAW MATCHING:                0 rows (timestamps 17 minutes apart)
```

### Category 2: Preseason Games (6 games)

**Dates**: October 10-11, 2025

**Characteristics**:
- Preseason games (season_type = 1)
- Games were played and completed (STATUS_FINAL)
- Kalshi markets existed for preseason games (surprisingly)
- Same time gap issue as regular season games

**Note**: Preseason games having Kalshi markets is unexpected - Kalshi typically focuses on regular season. These markets may have had low liquidity.

---

## Verification Queries

### Query 1: Verify Games Exist in ESPN Scoreboard
```sql
SELECT COUNT(*) FROM espn.scoreboard_games 
WHERE event_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700');
-- Result: 62 games found
```

### Query 2: Verify ESPN Probability Data Exists
```sql
SELECT game_id, COUNT(*) as prob_count
FROM espn.probabilities_raw_items
WHERE game_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700')
GROUP BY game_id;
-- Result: All 62 games have 400-570 probability points
```

### Query 3: Verify Kalshi Market Records Exist
```sql
SELECT espn_event_id, COUNT(DISTINCT ticker) as market_count
FROM kalshi.markets_with_games
WHERE espn_event_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700')
GROUP BY espn_event_id;
-- Result: All 62 games have 2 market tickers
```

### Query 4: Verify Kalshi Candlestick Data Exists
```sql
SELECT kmw.espn_event_id, COUNT(c.period_ts) as candlestick_count
FROM kalshi.candlesticks c
JOIN kalshi.markets_with_games kmw ON c.ticker = kmw.ticker
WHERE kmw.espn_event_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700')
GROUP BY kmw.espn_event_id;
-- Result: All 62 games have candlestick data (400-2500+ per game)
```

### Query 5: Verify Canonical Dataset Has No Kalshi Data
```sql
SELECT game_id, 
       COUNT(*) as total_rows,
       COUNT(kalshi_home_mid_price) as rows_with_kalshi
FROM derived.snapshot_features_v1
WHERE game_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700')
GROUP BY game_id;
-- Result: All 62 games have 0 rows_with_kalshi (despite having total_rows)
```

### Query 6: Time Gap Analysis (Matching Materialized View Logic)

**Critical**: This query mirrors the materialized view's logic:
1. Filter Kalshi candlesticks to `period_ts >= game_start` (game window filter)
2. Require `yes_bid_close IS NOT NULL AND yes_ask_close IS NOT NULL` (bid/ask filter)
3. Check if Kalshi data overlaps with ESPN recording timestamps

The materialized view's LATERAL JOIN requires Kalshi timestamps to be within 60 seconds of raw ESPN timestamps (`last_modified_utc`). If there's no overlap at all, no matching can occur.

```sql
WITH game_info AS (
    SELECT 
        sg.event_id as game_id,
        sg.event_date as game_start,
        MIN(p.last_modified_utc) as espn_start,
        MAX(p.last_modified_utc) as espn_end
    FROM espn.scoreboard_games sg
    JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
    WHERE sg.event_id IN ('401810294', '401810286', '401810293', '401810287', '401810289', '401810292', '401810288', '401810291', '401810285', '401810283', '401810278', '401810282', '401810281', '401810279', '401810284', '401809241', '401809238', '401810277', '401809239', '401809240', '401810275', '401810276', '401810274', '401810270', '401810273', '401810269', '401810272', '401810271', '401810267', '401810268', '401810266', '401810265', '401810260', '401810261', '401810264', '401810262', '401810263', '401810259', '401810258', '401810257', '401810252', '401810255', '401810253', '401810256', '401810254', '401810250', '401810251', '401810242', '401810249', '401810243', '401810246', '401810244', '401810245', '401810247', '401810248', '401810241', '401812701', '401812702', '401812697', '401812698', '401812699', '401812700', '401810238')
    GROUP BY sg.event_id, sg.event_date
),
kalshi_in_game_window AS (
    -- Kalshi data filtered to game window (period_ts >= game_start) with bid/ask
    -- This matches the materialized view's filtering logic
    SELECT 
        gi.game_id,
        gi.game_start,
        gi.espn_start,
        MAX(c.period_ts) as kalshi_window_end
    FROM game_info gi
    JOIN kalshi.markets_with_games kmw ON kmw.espn_event_id = gi.game_id
    JOIN kalshi.candlesticks c ON c.ticker = kmw.ticker
    WHERE c.period_ts >= gi.game_start  -- Key filter from materialized view
      AND c.yes_bid_close IS NOT NULL   -- Required by materialized view
      AND c.yes_ask_close IS NOT NULL   -- Required by materialized view
    GROUP BY gi.game_id, gi.game_start, gi.espn_start
)
SELECT 
    game_id,
    CASE 
        WHEN kalshi_window_end >= espn_start THEN 'OVERLAP'
        ELSE 'NO OVERLAP - Kalshi ends before ESPN starts'
    END as status,
    EXTRACT(EPOCH FROM (espn_start - kalshi_window_end)) / 60 as gap_minutes
FROM kalshi_in_game_window;
-- Result: All 62 games show NO OVERLAP with gaps of 9-165 minutes
```

**Sample results showing the gap:**
| Game ID | Kalshi Window End | ESPN Start | Gap (minutes) |
|---------|-------------------|------------|---------------|
| 401809238 | 11:51 | 12:08 | 17 |
| 401810294 | 19:26 | 20:11 | 45 |
| 401812697 | 16:51 | 19:13 | 142 |

**Key Insight**: Kalshi candlestick data EXISTS from game_start onwards, but STOPS before ESPN begins recording probabilities. Even though Kalshi has 300-1500+ candlesticks in the game window, they all end before ESPN's first data point.

---

## Recommendations

### Immediate Fix: Update Materialized View Timestamp Alignment

**Priority**: CRITICAL  
**Effort**: MEDIUM (SQL modification)

The materialized view must align ESPN timestamps to `game_start` before matching with Kalshi, mirroring the logic in `probabilities.py`:

```sql
-- Step 1: Add first_espn_ts to game_time_info CTE (already exists)
-- Step 2: Calculate aligned timestamp in espn_base or kalshi_aligned CTE

-- In kalshi_aligned, change the matching logic from:
AND c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds'
                    AND ewd.snapshot_ts + INTERVAL '60 seconds'

-- To (aligned version):
AND c.period_ts BETWEEN 
    (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) - INTERVAL '60 seconds'
    AND 
    (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) + INTERVAL '60 seconds'
```

**Full fix steps:**
1. Add `first_espn_ts` column to `game_time_with_kalshi` CTE (already present as `first_espn_ts`)
2. Update `espn_base` to include `first_espn_ts` 
3. Update `kalshi_aligned` LATERAL JOIN to use aligned timestamps
4. Rebuild and refresh materialized view:
```sql
DROP MATERIALIZED VIEW IF EXISTS derived.snapshot_features_v1 CASCADE;
-- Recreate with fixed SQL
REFRESH MATERIALIZED VIEW derived.snapshot_features_v1;
```

### Alternative: Expand Kalshi Matching Window

**Priority**: LOW  
**Effort**: LOW

If aligning timestamps is too complex, expand the Kalshi matching window to account for the ~3 hour offset:

```sql
-- Expand window to 4 hours (covers the ~3 hour ESPN offset plus game duration)
AND c.period_ts BETWEEN ewd.game_start AND ewd.game_start + INTERVAL '4 hours'
```

**Cons**:
- Less precise matching (could match wrong Kalshi timestamps)
- Not recommended for production simulation

### Monitoring: Add Data Quality Alerts

**Priority**: MEDIUM  
**Effort**: LOW

Add monitoring query to detect games with ESPN data but no Kalshi overlap:

```sql
-- Alert: Games with ESPN data but no Kalshi coverage
SELECT game_id
FROM derived.snapshot_features_v1
WHERE espn_home_prob IS NOT NULL
GROUP BY game_id
HAVING COUNT(kalshi_home_mid_price) = 0;
```

---

## Decision Trade-offs

### Why the 60-Second Matching Window Is Appropriate (Once Alignment Is Fixed)

**Pros**:
- Ensures high confidence that ESPN probability and Kalshi price are from the same game moment
- Reduces noise from stale Kalshi quotes
- Maintains simulation accuracy

**Cons**:
- Requires timestamps to be on the same timeline (which the current MV doesn't do!)

**The window size is not the problem** - 60 seconds is fine once ESPN timestamps are properly aligned to `game_start`.

### Why the MV Has a Bug (Not a Design Decision)

The MV comments state:
```sql
-- Match RAW ESPN timestamp to Kalshi timestamp within 60 seconds
-- Both are wall-clock timestamps, so we match directly (no alignment needed here)
```

**This comment is incorrect.** ESPN's `last_modified_utc` is NOT actual game time - it's server recording time ~3 hours after game events. The comment should say:

```sql
-- Match ALIGNED ESPN timestamp (normalized to game_start) to Kalshi timestamp
-- ESPN timestamps must be shifted: aligned_ts = game_start + (snapshot_ts - first_espn_ts)
```

### Why Games Aren't Excluded Earlier in Pipeline

The current design passes games through multiple validation stages:
1. `games_with_kalshi` CTE - verifies market records AND candlestick existence ✅
2. Time window filtering - filters Kalshi to `period_ts >= game_start` ✅
3. LATERAL JOIN alignment - matches timestamps ❌ **BROKEN**

The games pass stages 1-2 but fail stage 3 because ESPN's raw timestamps are ~3 hours off from Kalshi's timestamps.

**Recommendation**: Fix the timestamp alignment in step 3, then games will match correctly.

---

## Appendix: Related Files

- Simulation endpoint: `webapp/api/endpoints/simulation.py`
- Aligned data function: `scripts/simulate_trading_strategy.py::get_aligned_data()`
- Canonical dataset view: `derived.snapshot_features_v1` (materialized view)
- Kalshi backfill script: `scripts/load_kalshi_candlesticks.py`
- Games endpoint filter: `webapp/api/endpoints/games.py::list_games()`

---

## Conclusion

The 62 failed games are not due to:
- ❌ Missing ESPN data (all games have 400-570 probability points)
- ❌ Missing Kalshi market records (all games have 2 tickers)
- ❌ Missing Kalshi candlestick data (all games have 400-2500+ candlesticks during game time)
- ❌ Kalshi backfill timing (data exists for game duration)
- ❌ Database schema issues
- ❌ Simulation code bugs

**The failure is due to:**
- ✅ **Materialized view uses WRONG timestamp alignment** - it matches raw ESPN `last_modified_utc` to Kalshi `period_ts`, but these timestamps are ~3 hours apart
- ✅ **probabilities.py aligns correctly** - it shifts ESPN timestamps to start at `game_start`

**Resolution**: Update the materialized view's `kalshi_aligned` CTE to use aligned timestamps:
```sql
-- Change from raw timestamp matching:
c.period_ts BETWEEN ewd.snapshot_ts - INTERVAL '60 seconds' AND ...

-- To aligned timestamp matching:
c.period_ts BETWEEN (ewd.game_start + (ewd.snapshot_ts - ewd.first_espn_ts)) - INTERVAL '60 seconds' AND ...
```

This will allow the ~2.8 hours of overlapping ESPN and Kalshi data to be properly matched.

