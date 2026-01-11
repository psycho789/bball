# Kalshi Data Coverage Analysis: Why Games Are Being Skipped

**Date**: Sun Jan  4 21:08:47 PST 2026  
**Author**: Analysis  
**Purpose**: Investigate why certain games are being filtered out due to missing Kalshi data

---

## Executive Summary

During bulk simulation runs, several games are being skipped because they have **zero aligned data points** after filtering. The primary cause is **missing Kalshi market data** - ESPN probability snapshots exist, but corresponding Kalshi candlestick data is not available within the 60-second alignment window.

**Affected Games** (from logs):
- `401812701`: 516 canonical rows → 0 aligned points (507 filtered by missing Kalshi)
- `401812702`: 549 canonical rows → 0 aligned points (542 filtered by missing Kalshi)
- `401812711`: 84 aligned points (but 542 snapshots filtered by missing Kalshi)

**Impact**: These games cannot be simulated, reducing the effective dataset size and potentially introducing selection bias.

---

## Problem Statement

### Current Behavior

The `get_aligned_data()` function in `scripts/simulate_trading_strategy.py` filters out snapshots where `kalshi_home_mid_price` is `NULL`. This happens when:

1. **No Kalshi market exists** for the ESPN game (no mapping in `kalshi.markets_with_games`)
2. **Kalshi market exists but no candlesticks** were generated during the game window
3. **Candlesticks exist but outside the 60-second alignment window** from ESPN snapshots

### Filtering Logic

```python
# From get_aligned_data() - lines 255-260
if kalshi_price is None:
    filtered_by_kalshi += 1
    logger.debug(f"[ALIGN_DATA] Game {game_id}: Snapshot {snapshot_ts} has no Kalshi data - skipping")
    continue  # Skip this row - can't calculate divergence without Kalshi price
```

**Design Pattern**: Defensive filtering with explicit NULL checks  
**Algorithm**: Linear scan with early termination (O(n) where n = canonical rows)  
**Big O Complexity**: O(n) for filtering operation

---

## Root Cause Analysis

### Hypothesis 1: Kalshi Markets Don't Exist for These Games

**Investigation Query**:
```sql
-- Check if Kalshi markets exist for these games
SELECT 
    sg.event_id,
    sg.event_date,
    sg.home_team_abbrev,
    sg.away_team_abbrev,
    COUNT(DISTINCT kmw.ticker) as market_count,
    COUNT(DISTINCT kc.ticker) as candlestick_count
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
LEFT JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
WHERE sg.event_id IN ('401812701', '401812702', '401812711')
GROUP BY sg.event_id, sg.event_date, sg.home_team_abbrev, sg.away_team_abbrev;
```

**Expected Findings**:
- If `market_count = 0`: No Kalshi markets were created for these games
- If `market_count > 0` but `candlestick_count = 0`: Markets exist but no trading activity
- If `candlestick_count > 0`: Markets and candlesticks exist, but alignment window is too strict

### Hypothesis 2: Alignment Window Too Strict (60 seconds)

**Investigation Query**:
```sql
-- Check alignment window coverage for these games
WITH espn_snapshots AS (
    SELECT 
        game_id,
        snapshot_ts,
        espn_home_prob
    FROM derived.snapshot_features_v1
    WHERE game_id IN ('401812701', '401812702', '401812711')
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
    WHERE kmw.espn_event_id IN ('401812701', '401812702', '401812711')
      AND kmw.kalshi_team_side = 'home'
)
SELECT 
    es.game_id,
    COUNT(*) as espn_snapshots,
    COUNT(kc.period_ts) as aligned_within_60s,
    COUNT(*) - COUNT(kc.period_ts) as not_aligned,
    MIN(ABS(EXTRACT(EPOCH FROM (es.snapshot_ts - kc.period_ts)))) as min_time_diff_seconds,
    MAX(ABS(EXTRACT(EPOCH FROM (es.snapshot_ts - kc.period_ts)))) as max_time_diff_seconds
FROM espn_snapshots es
LEFT JOIN kalshi_candles kc ON es.game_id = kc.game_id
    AND ABS(EXTRACT(EPOCH FROM (es.snapshot_ts - kc.period_ts))) <= 60
GROUP BY es.game_id;
```

**Expected Findings**:
- If `min_time_diff_seconds > 60`: All Kalshi candlesticks are outside the 60-second window
- If `aligned_within_60s = 0` but candlesticks exist: Window is too strict
- If `not_aligned` is high: Many snapshots can't be aligned

### Hypothesis 3: Market Mapping Issue (espn_event_id Mismatch)

**Investigation Query**:
```sql
-- Check market mapping for these games
SELECT 
    sg.event_id,
    sg.event_date,
    sg.home_team_abbrev,
    sg.away_team_abbrev,
    kmw.ticker,
    kmw.event_ticker,
    kmw.kalshi_team_side,
    kmw.yes_sub_title,
    COUNT(DISTINCT kc.period_ts) as candlestick_count
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
LEFT JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
WHERE sg.event_id IN ('401812701', '401812702', '401812711')
GROUP BY sg.event_id, sg.event_date, sg.home_team_abbrev, sg.away_team_abbrev,
         kmw.ticker, kmw.event_ticker, kmw.kalshi_team_side, kmw.yes_sub_title
ORDER BY sg.event_id, kmw.ticker;
```

**Expected Findings**:
- If no rows returned: No markets mapped to these games
- If `kalshi_team_side IS NULL`: Market exists but team side couldn't be determined
- If `candlestick_count = 0`: Market exists but no trading activity

---

## Data Collection Plan

### Step 1: Identify Game Metadata

**Query**:
```sql
SELECT 
    event_id,
    event_date,
    home_team_abbrev,
    away_team_abbrev,
    home_score,
    away_score,
    status
FROM espn.scoreboard_games
WHERE event_id IN ('401812701', '401812702', '401812711');
```

**Purpose**: Understand what these games are (teams, dates, outcomes)

### Step 2: Check Kalshi Market Coverage

**Query**:
```sql
SELECT 
    sg.event_id,
    COUNT(DISTINCT kmw.ticker) as market_count,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'home' THEN kmw.ticker END) as home_markets,
    COUNT(DISTINCT CASE WHEN kmw.kalshi_team_side = 'away' THEN kmw.ticker END) as away_markets
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
WHERE sg.event_id IN ('401812701', '401812702', '401812711')
GROUP BY sg.event_id;
```

**Purpose**: Determine if Kalshi markets exist for these games

### Step 3: Check Candlestick Coverage

**Query**:
```sql
SELECT 
    sg.event_id,
    kmw.ticker,
    kmw.kalshi_team_side,
    COUNT(DISTINCT kc.period_ts) as candlestick_count,
    MIN(kc.period_ts) as first_candle,
    MAX(kc.period_ts) as last_candle
FROM espn.scoreboard_games sg
LEFT JOIN kalshi.markets_with_games kmw ON sg.event_id = kmw.espn_event_id
LEFT JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
WHERE sg.event_id IN ('401812701', '401812702', '401812711')
  AND kmw.kalshi_team_side IS NOT NULL
GROUP BY sg.event_id, kmw.ticker, kmw.kalshi_team_side
ORDER BY sg.event_id, kmw.ticker;
```

**Purpose**: Determine if candlesticks exist and their time coverage

### Step 4: Analyze Alignment Window Coverage

**Query**:
```sql
-- For each game, count how many ESPN snapshots can be aligned
WITH game_windows AS (
    SELECT 
        game_id,
        MIN(snapshot_ts) as first_espn,
        MAX(snapshot_ts) as last_espn
    FROM derived.snapshot_features_v1
    WHERE game_id IN ('401812701', '401812702', '401812711')
      AND espn_home_prob IS NOT NULL
    GROUP BY game_id
),
kalshi_windows AS (
    SELECT DISTINCT ON (kmw.espn_event_id)
        kmw.espn_event_id as game_id,
        MIN(kc.period_ts) as first_kalshi,
        MAX(kc.period_ts) as last_kalshi
    FROM kalshi.markets_with_games kmw
    JOIN kalshi.candlesticks kc ON kmw.ticker = kc.ticker
    WHERE kmw.espn_event_id IN ('401812701', '401812702', '401812711')
      AND kmw.kalshi_team_side = 'home'
    GROUP BY kmw.espn_event_id
)
SELECT 
    gw.game_id,
    gw.first_espn,
    gw.last_espn,
    kw.first_kalshi,
    kw.last_kalshi,
    EXTRACT(EPOCH FROM (kw.first_kalshi - gw.first_espn)) as time_diff_first_seconds,
    EXTRACT(EPOCH FROM (kw.last_kalshi - gw.last_espn)) as time_diff_last_seconds
FROM game_windows gw
LEFT JOIN kalshi_windows kw ON gw.game_id = kw.game_id;
```

**Purpose**: Understand the time window overlap between ESPN and Kalshi data

---

## Recommendations

### Short-Term (Immediate)

1. **Run Investigation Queries**: Execute the queries above to understand the root cause
2. **Document Findings**: Update this analysis with actual results
3. **Handle Gracefully**: Ensure simulation continues even when games are skipped (current behavior is correct)

### Medium-Term (Next Sprint)

1. **Relax Alignment Window** (if Hypothesis 2 is confirmed):
   - Consider increasing from 60 seconds to 120 seconds
   - Or use nearest-neighbor matching without strict window
   - **Trade-off**: More aligned points vs. potential timing inaccuracy

2. **Improve Market Mapping** (if Hypothesis 3 is confirmed):
   - Review `kalshi.markets_with_games` view logic
   - Improve team name matching algorithm
   - Add manual mapping table for edge cases

3. **Data Quality Monitoring**:
   - Add metrics to track % of games with zero aligned points
   - Alert when coverage drops below threshold
   - Document known gaps in Kalshi coverage

### Long-Term (Future Sprints)

1. **Alternative Data Sources**:
   - Consider using ESPN-only simulations for games without Kalshi data
   - Or use historical Kalshi data from similar games as proxy
   - Document limitations clearly

2. **Data Collection Strategy**:
   - Ensure Kalshi markets are created for all NBA games
   - Monitor candlestick generation (requires trading activity)
   - Consider backfilling missing candlesticks if possible

---

## Evidence to Capture

### Query Results

**Paste results from investigation queries here:**

```sql
-- Game metadata
-- [PASTE RESULTS]

-- Market coverage
-- [PASTE RESULTS]

-- Candlestick coverage
-- [PASTE RESULTS]

-- Alignment window analysis
-- [PASTE RESULTS]
```

### Summary Statistics

- **Total games analyzed**: 3
- **Games with markets**: [TBD]
- **Games with candlesticks**: [TBD]
- **Games with aligned data**: [TBD]
- **Average alignment rate**: [TBD]%

---

## Next Steps

1. ✅ Create analysis document
2. ⏳ Run investigation queries
3. ⏳ Document findings
4. ⏳ Update recommendations based on findings
5. ⏳ Create follow-up sprint items if needed

---

## References

- `scripts/simulate_trading_strategy.py`: `get_aligned_data()` function (lines 82-287)
- `db/migrations/032_derived_snapshot_features_v1.sql`: Canonical dataset definition
- `kalshi.markets_with_games`: View for mapping Kalshi markets to ESPN games
- `kalshi.candlesticks`: Table storing Kalshi market candlestick data



