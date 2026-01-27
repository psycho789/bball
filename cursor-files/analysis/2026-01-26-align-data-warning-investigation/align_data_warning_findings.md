# ALIGN_DATA Warning Investigation - Findings

**Date**: 2026-01-26  
**Status**: 🔴 **SYSTEMIC ISSUE CONFIRMED**

---

## Executive Summary

**Critical Finding**: This is **NOT** an isolated issue. The investigation reveals that **multiple games** (at least 10) have the `home + away ≈ 1.0` pattern, with some games having **20-30% of snapshots** affected.

**Severity**: 🔴 **HIGH** - This is a systemic data quality issue that affects simulation accuracy.

---

## Investigation Results

### Query 1: Game 401809981 Sample Data

**Result**: Most snapshots show correct conversion (`home ≈ away`), but **8.6% have the warning pattern**.

**Sample Data**:
- Most snapshots: `home=0.785, away=0.775` → `diff=0.01` ✓ (correct)
- Some snapshots: `home + away ≈ 1.0` ⚠️ (needs investigation)

**Key Finding**: The issue is **intermittent** - not all snapshots are affected.

### Query 2: Warning Count for Game 401809981

**Result**:
- Total snapshots with both prices: **464**
- Snapshots with warning pattern: **40**
- Warning percentage: **8.6%**

### Query 3: Other Games with Same Pattern

**🔴 CRITICAL FINDING**: This pattern appears in **at least 10 other games**:

| Game ID | Total Snapshots | Warning Count | Warning % |
|---------|----------------|---------------|-----------|
| 401810128 | 499 | 156 | **31.3%** |
| 401809809 | 543 | 150 | **27.6%** |
| 401836806 | 511 | 140 | **27.4%** |
| 401812701 | 516 | 136 | **26.4%** |
| 401810099 | 499 | 133 | **26.7%** |
| 401839699 | 541 | 131 | **24.2%** |
| 401809794 | 512 | 121 | **23.6%** |
| 401836803 | 482 | 119 | **24.7%** |
| 401810064 | 470 | 118 | **25.1%** |
| 401809963 | 502 | 116 | **23.1%** |

**Analysis**:
- **10+ games** affected
- **20-30% of snapshots** in affected games have the issue
- This is **NOT isolated** to game 401809981
- This is a **systemic issue** requiring immediate attention

---

## Root Cause Hypothesis

### Hypothesis 1: View Definition Issue (Most Likely)

**Theory**: The SQL view might have conditional logic that doesn't convert away prices in certain scenarios.

**Possible Scenarios**:
1. **Missing away market data**: When away market data is missing, the view might be using raw home prices for both
2. **Conditional conversion**: The view might only convert away prices when certain conditions are met
3. **JOIN issue**: The LATERAL JOIN for away markets might not be matching correctly in some cases

### Hypothesis 2: Data Quality Issue

**Theory**: The raw Kalshi data might be stored incorrectly for some games/markets.

**Possible Scenarios**:
1. **Market mapping issue**: `kalshi.markets_with_games` might have incorrect mappings
2. **Ticker format**: Away market tickers might not match expected pattern
3. **Data loading issue**: Away market data might not be loaded correctly

### Hypothesis 3: View Refresh Issue

**Theory**: The materialized view might be stale or not refreshed after data changes.

**Check**: Verify when the view was last refreshed and if it needs updating.

---

## Next Steps

### Immediate Actions (High Priority)

1. **✅ Fix SQL Query Error**
   - Update query to use `ticker` instead of `market_ticker`
   - Re-run investigation queries

2. **🔍 Investigate Problematic Snapshots**
   - Query snapshots where `sum ≈ 1.0` to see the actual values
   - Compare with raw Kalshi data to understand the pattern

3. **🔍 Check View Definition**
   - Verify the actual view definition in the database
   - Check if conversion logic is conditional or always applied

4. **🔍 Check Raw Kalshi Data**
   - Query raw candlestick data for affected games
   - Verify market mappings in `kalshi.markets_with_games`

### Analysis Actions

5. **📊 Pattern Analysis**
   - Determine if the issue is time-based (certain periods of games)
   - Check if it's market-based (certain markets)
   - Identify common characteristics of affected snapshots

6. **🔧 Fix Implementation**
   - Once root cause identified, fix the view definition
   - Refresh materialized view
   - Verify fix with investigation queries

### Verification Actions

7. **✅ Verify Fix**
   - Re-run grid search to confirm warnings are reduced
   - Check that affected games now show correct conversion
   - Monitor for any remaining issues

---

## Impact Assessment

### Current Impact

**🔴 HIGH SEVERITY**:
- **10+ games** affected
- **20-30% of snapshots** in affected games have incorrect data
- **Simulation accuracy compromised** for affected games
- **Grid search results may be biased** by incorrect price data

### Potential Impact if Not Fixed

- **Incorrect divergence calculations**: Prices that should be converted aren't
- **Biased trading signals**: Simulations using wrong price data
- **Inaccurate performance metrics**: Grid search results based on bad data
- **Cascading errors**: Model training and evaluation affected

---

## SQL Queries for Further Investigation

### Query: Show Problematic Snapshots

```sql
-- Show actual problematic snapshots (where sum ≈ 1.0)
SELECT 
    sequence_number,
    snapshot_ts,
    kalshi_home_mid_price,
    kalshi_away_mid_price,
    (kalshi_home_mid_price + kalshi_away_mid_price) AS sum_home_away,
    ABS(kalshi_home_mid_price - kalshi_away_mid_price) AS diff_home_away
FROM derived.snapshot_features_v1
WHERE game_id = '401809981'
  AND season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
  AND ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
ORDER BY sequence_number
LIMIT 20;
```

### Query: Check View Definition

```sql
-- Get the actual view definition
SELECT pg_get_viewdef('derived.snapshot_features_v1', true);
```

### Query: Check Raw Kalshi Data

```sql
-- Check raw candlestick data for affected game
SELECT DISTINCT
    c.ticker,
    c.yes_bid_close,
    c.yes_ask_close,
    (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0 AS raw_mid_price,
    mwg.kalshi_team_side
FROM kalshi.candlesticks c
JOIN kalshi.markets_with_games mwg ON c.ticker = mwg.ticker
WHERE mwg.espn_event_id = '401809981'
ORDER BY c.ticker, c.period_ts
LIMIT 20;
```

---

## Recommendations

### Priority 1: Immediate Investigation

1. **Run fixed SQL queries** to see problematic snapshots
2. **Check view definition** to understand conversion logic
3. **Compare raw data** with view output to identify discrepancy

### Priority 2: Root Cause Fix

1. **Fix view definition** once root cause identified
2. **Refresh materialized view**: `REFRESH MATERIALIZED VIEW derived.snapshot_features_v1;`
3. **Verify fix** with investigation queries

### Priority 3: Monitoring

1. **Add validation** to detect this pattern automatically
2. **Monitor** for similar issues in future data loads
3. **Document** the fix and prevention measures

---

## Status

- ✅ **Investigation queries created**
- ✅ **Systemic issue confirmed**
- ⏳ **Root cause analysis in progress**
- ⏳ **Fix implementation pending**
- ⏳ **Verification pending**

---

**Next Action**: Run fixed SQL queries to investigate problematic snapshots and identify root cause.
