# ALIGN_DATA Warning Investigation

**Date**: 2026-01-26  
**Issue**: Multiple games show `[ALIGN_DATA]` warnings where `home + away prices sum to ~1.0`  
**Warning Count**: 4,575 instances for game 401809981, **10+ other games affected**  
**Severity**: 🔴 **HIGH** - **SYSTEMIC ISSUE CONFIRMED** (20-30% of snapshots in affected games)

---

## Executive Summary

The `[ALIGN_DATA]` warning indicates that for game 401809981, the Kalshi home and away prices sum to approximately 1.0, which suggests the away price might not be converted to home probability space as expected.

**Expected Behavior**:
- `kalshi_home_mid_price` + `kalshi_away_mid_price` should be close to each other (both in home probability space)
- Example: home=0.50, away=0.50 (both represent 50% home win probability)

**Observed Behavior**:
- `kalshi_home_mid_price` + `kalshi_away_mid_price` ≈ 1.0
- Example: home=0.4850, away=0.5500, sum=1.0350 ≈ 1.0
- This suggests away price is still in "raw away space" (not converted)

---

## Root Cause Analysis

### Expected Conversion Logic

According to the SQL view definition (`derived.snapshot_features_v1`), away prices should be converted to home probability space:

```sql
-- Away market: "Will away team win?" (0-100)
-- Home market: "Will home team win?" (0-100)
-- Conversion: home_prob = 1 - away_prob
kalshi_away_mid_price = 1.0 - ((ka.yes_bid_close + ka.yes_ask_close) / 200.0)
```

**Example**:
- Raw away market: 55% away wins → `yes_bid=54, yes_ask=56` → `raw_mid=0.55`
- Converted: `kalshi_away_mid_price = 1.0 - 0.55 = 0.45` (45% home wins)
- Expected result: `home_mid ≈ away_mid` (both ≈ 0.45)

### What the Warning Detects

The Python code checks for two patterns:

```python
diff_check = abs(home_norm - away_norm)  # Should be small if away is converted
sum_check = abs((home_norm + away_norm) - 1.0)  # Would be small if away is raw

if diff_check < 0.05:
    # Correct: away is already converted, home ≈ away
    pass
elif sum_check < 0.05:
    # WARNING: away might still be in raw away space (home + away ≈ 1.0)
    logger.warning("[ALIGN_DATA] Game {game_id}: WARNING - home + away prices sum to ~1.0...")
```

**Pattern 1 (Correct)**: `home ≈ away` (both converted to home space)
- Example: home=0.50, away=0.50 → diff=0.00 ✓

**Pattern 2 (Warning)**: `home + away ≈ 1.0` (away still in raw space)
- Example: home=0.4850, away=0.5500 → sum=1.0350 ≈ 1.0 ⚠️

---

## Investigation Steps

### Step 1: Query the Canonical View

Run the SQL query to check the actual data:

```sql
-- Check game 401809981 data
SELECT 
    sequence_number,
    kalshi_home_mid_price,
    kalshi_away_mid_price,
    (kalshi_home_mid_price + kalshi_away_mid_price) AS sum_home_away,
    ABS(kalshi_home_mid_price - kalshi_away_mid_price) AS diff_home_away,
    ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) AS sum_minus_one
FROM derived.snapshot_features_v1
WHERE game_id = '401809981'
  AND season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
ORDER BY sequence_number
LIMIT 20;
```

**Expected Findings**:
- `sum_home_away` should be close to 1.0 (indicating away price not converted)
- `diff_home_away` should be large (not close to 0)
- `sum_minus_one` should be small (< 0.05)

### Step 2: Check Raw Kalshi Data

Query the raw candlestick data to see what's actually stored:

```sql
SELECT DISTINCT
    c.market_ticker,
    c.yes_bid_close,
    c.yes_ask_close,
    (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0 AS raw_mid_price,
    CASE 
        WHEN c.market_ticker LIKE '%HOME%' OR c.market_ticker LIKE '%home%' THEN 'HOME'
        WHEN c.market_ticker LIKE '%AWAY%' OR c.market_ticker LIKE '%away%' THEN 'AWAY'
        ELSE 'UNKNOWN'
    END AS market_type
FROM kalshi.candlesticks c
WHERE c.game_id = '401809981'
ORDER BY c.market_ticker, c.timestamp_utc
LIMIT 20;
```

**Expected Findings**:
- Raw away market prices (e.g., 0.55 = 55% away wins)
- If view conversion is working: `kalshi_away_mid_price` should be `1.0 - raw_away_mid`
- If view conversion is NOT working: `kalshi_away_mid_price` might equal `raw_away_mid`

### Step 3: Check View Definition

Verify the actual view definition in the database:

```sql
-- Get the view definition
SELECT pg_get_viewdef('derived.snapshot_features_v1', true);
```

**Check for**:
- Conversion formula: `1.0 - ((ka.yes_bid_close + ka.yes_ask_close) / 200.0)`
- Ensure away prices are being converted correctly

### Step 4: Check Other Games

Determine if this is isolated to one game or a systemic issue:

```sql
-- Count games with this pattern
SELECT 
    game_id,
    COUNT(*) AS snapshot_count,
    COUNT(CASE 
        WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
        THEN 1 
    END) AS warning_count
FROM derived.snapshot_features_v1
WHERE season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND kalshi_away_mid_price IS NOT NULL
GROUP BY game_id
HAVING COUNT(CASE 
    WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
    THEN 1 
END) > 0
ORDER BY warning_count DESC
LIMIT 10;
```

**Expected Findings**:
- If only game 401809981: Isolated data quality issue
- If many games: Systemic issue with view definition or data

---

## Possible Causes

### 1. View Definition Bug (Most Likely)

**Hypothesis**: The SQL view might not be converting away prices correctly for this game.

**Check**: Verify the view definition includes the conversion formula:
```sql
(1.0 - ((ka.yes_bid_close::NUMERIC + ka.yes_ask_close::NUMERIC) / 200.0)) AS kalshi_away_mid_price
```

**Fix**: If missing, update the view definition and refresh the materialized view.

### 2. Data Quality Issue (Possible)

**Hypothesis**: The raw Kalshi data for this game might be in an unexpected format.

**Check**: Query raw candlestick data to see if away market prices are stored differently.

**Fix**: If data is correct, ensure view handles this format correctly.

### 3. View Not Refreshed (Possible)

**Hypothesis**: The materialized view might be stale and needs to be refreshed.

**Check**: Check when the view was last refreshed:
```sql
SELECT schemaname, matviewname, last_refresh
FROM pg_matviews
WHERE matviewname = 'snapshot_features_v1';
```

**Fix**: Refresh the materialized view:
```sql
REFRESH MATERIALIZED VIEW derived.snapshot_features_v1;
```

### 4. Edge Case in View Logic (Less Likely)

**Hypothesis**: The view might have conditional logic that doesn't convert away prices in certain cases.

**Check**: Review the full view definition for any CASE statements or conditions that might skip conversion.

**Fix**: Update view logic to ensure conversion always happens.

---

## Impact Assessment

### Current Impact

**Low-Medium Severity**:
- ✅ Only affects **one game** (401809981)
- ✅ Code has **fallback handling** (uses home prices when available)
- ✅ **4,575 warnings** out of many thousands of snapshots (small percentage)
- ⚠️ Could affect simulation accuracy for this specific game

### Potential Impact if Systemic

**If this pattern appears in many games**:
- 🔴 **High severity**: Would affect simulation accuracy across multiple games
- 🔴 Would require immediate view definition fix
- 🔴 Would require refreshing materialized view

---

## Recommended Actions

### Immediate Actions

1. **Run Investigation Queries**
   - Execute the SQL queries in `scripts/analysis/investigate_align_data_warning.sql`
   - Document findings

2. **Check View Definition**
   - Verify the view includes away price conversion
   - Check if view needs to be refreshed

3. **Check Other Games**
   - Determine if this is isolated or systemic
   - If systemic, prioritize fixing view definition

### If Isolated (One Game)

**Action**: Monitor and document
- ✅ Low priority fix
- ✅ Code handles it gracefully with fallback
- ✅ No immediate action needed

### If Systemic (Many Games)

**Action**: Fix view definition immediately
1. Update view definition to ensure away price conversion
2. Refresh materialized view: `REFRESH MATERIALIZED VIEW derived.snapshot_features_v1;`
3. Re-run grid search to verify fix
4. Monitor for warnings in future runs

---

## SQL Investigation Script

A SQL script has been created at:
`scripts/analysis/investigate_align_data_warning.sql`

This script contains all the queries needed to investigate the issue.

**To run**:
```bash
psql $DATABASE_URL -f scripts/analysis/investigate_align_data_warning.sql
```

---

## Next Steps

1. ✅ **Investigation queries run** - Results documented in `align_data_warning_findings.md`
2. ✅ **Systemic issue confirmed** - 10+ games affected, 20-30% of snapshots
3. ⏳ **Investigate root cause** - Check view definition and raw data
4. ⏳ **Fix view definition** - Ensure away price conversion always happens
5. ⏳ **Verify fix** - Re-run queries and grid search

---

## References

- **Code Location**: `scripts/trade/simulate_trading_strategy.py` lines 446-457
- **View Documentation**: `cursor-files/docs/most-up-to-date-material-view.md`
- **Warning Explanation**: `cursor-files/analysis/2026-01-26-grid-search-warnings-explanation/grid_search_warnings_explanation.md`

---

**Status**: ✅ Investigation complete - **FALSE POSITIVE WARNINGS IDENTIFIED**  
**Priority**: 🟡 **MEDIUM** - Conversion working correctly, but warning logic has edge case  
**Root Cause**: False positives when markets are balanced (~50/50) where `home + away ≈ 1.0` even though both are correctly converted

**Key Finding**: Query 5 confirms conversion IS working correctly. The warnings are false positives due to balanced market edge case.

**See**: 
- `align_data_warning_findings.md` - Initial investigation results
- `root_cause_analysis.md` - Detailed root cause analysis
- `final_analysis.md` - Final analysis with recommended fixes
