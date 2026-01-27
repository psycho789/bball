# SQL Query Analysis - ALIGN_DATA Warning Investigation

**Date**: 2026-01-26  
**Purpose**: Document what each query does and ensure they use correct timestamp alignment

---

## Timestamp Alignment Formula

**From README.md and view definition**:
```
aligned_espn_ts = game_start + (snapshot_ts - first_espn_ts)
```

Where:
- `game_start` = `event_date` from `espn.scoreboard_games` (scheduled game start)
- `snapshot_ts` = raw ESPN `last_modified_utc` (stored in view as `snapshot_ts`)
- `first_espn_ts` = first ESPN `last_modified_utc` for that game

**Key Insight**: The view stores RAW `snapshot_ts` but uses ALIGNED timestamps internally to match Kalshi data.

---

## Query Descriptions

### Query 1: Sample Data Check
**Purpose**: Show first 20 snapshots to see the pattern  
**What it does**: 
- Shows `kalshi_home_mid_price` and `kalshi_away_mid_price`
- Calculates `sum_home_away` and `diff_home_away`
- Categorizes as "correct" (home≈away) or "warning" (sum≈1.0)

**Status**: ✅ Correct - no timestamp alignment needed (just viewing view output)

---

### Query 2: Warning Count Summary
**Purpose**: Count how many snapshots have the warning pattern  
**What it does**:
- Counts total snapshots with both home and away prices
- Counts snapshots where `home + away ≈ 1.0` (within 0.05)
- Calculates percentage

**Status**: ✅ Correct - no timestamp alignment needed

---

### Query 3: Raw Kalshi Data Sample
**Purpose**: See what raw candlestick data looks like  
**What it does**:
- Shows raw candlestick data for the game
- Shows `raw_mid_price` and `expected_converted_price` (for away markets)
- Uses `kalshi_team_side` from `markets_with_games` to identify home/away

**Status**: ✅ Correct - shows raw data, no alignment needed

---

### Query 3b: Problematic Snapshots
**Purpose**: Show the actual snapshots that trigger the warning  
**What it does**:
- Filters to snapshots where `home + away ≈ 1.0`
- Shows the actual values

**Status**: ✅ Correct - no timestamp alignment needed

---

### Query 4: Other Games with Same Pattern
**Purpose**: Check if this is systemic or isolated  
**What it does**:
- Groups by `game_id` and counts warning snapshots
- Shows top 10 games with most warnings

**Status**: ✅ Correct - no timestamp alignment needed

---

### Query 5: Compare View Output with Raw Data
**Purpose**: **CRITICAL** - Compare what the view shows vs. what raw data says  
**What it does**:
- Gets view's `kalshi_home_mid_price` and `kalshi_away_mid_price`
- Queries raw candlestick data using **ALIGNED timestamps** (matching view logic)
- Calculates expected converted away price: `1.0 - raw_away_mid`
- Compares view's away price with:
  - Expected converted price (if matches → conversion working)
  - Raw away price (if matches → conversion NOT working)

**Alignment Formula Used**:
```sql
aligned_ts = game_start + (snapshot_ts - first_espn_ts)
```

**LATERAL JOIN Logic** (matching view):
```sql
c.period_ts >= (aligned_ts - INTERVAL '60 seconds')
AND c.period_ts <= (aligned_ts + INTERVAL '60 seconds')
ORDER BY ABS(EXTRACT(EPOCH FROM (c.period_ts - aligned_ts)))
LIMIT 1
```

**Status**: ✅ **FIXED** - Now uses correct alignment formula

---

### Query 6: View Definition
**Purpose**: Get the actual SQL view definition  
**What it does**:
- Uses `pg_get_viewdef()` to get the full view SQL
- Saves to `/tmp/snapshot_features_v1_view_definition.sql`

**Status**: ✅ Correct

---

### Query 7: Check Candlestick Availability
**Purpose**: Verify if candlesticks exist near aligned timestamps  
**What it does**:
- Calculates aligned timestamp: `game_start + (snapshot_ts - first_espn_ts)`
- Counts candlesticks within 60 seconds of aligned timestamp (matching view's window)
- Shows if data exists for problematic snapshots

**Alignment Formula Used**:
```sql
aligned_ts = game_start + (snapshot_ts - first_espn_ts)
```

**Status**: ✅ **FIXED** - Now uses correct alignment formula

---

## Key Fixes Applied

### Before (WRONG):
```sql
-- Used raw snapshot_ts directly
c.period_ts >= sf.snapshot_ts - INTERVAL '60 seconds'
```

### After (CORRECT):
```sql
-- Use aligned timestamp (same as view)
aligned_ts = gti.game_start + (sf.snapshot_ts - gti.first_espn_ts)
c.period_ts >= (aligned_ts - INTERVAL '60 seconds')
```

---

## Expected Results

### Query 5 Should Show:
- `raw_home_mid`: Raw home market mid-price from candlesticks
- `raw_away_mid`: Raw away market mid-price from candlesticks
- `expected_away_converted`: `1.0 - raw_away_mid` (what away should be after conversion)
- `conversion_status`: 
  - `✓ Converted correctly` if view's away price matches expected converted
  - `⚠️ NOT CONVERTED` if view's away price matches raw away (conversion not happening)
  - `? Mismatch` if neither matches (data quality issue or different candlestick matched)

### Query 7 Should Show:
- `aligned_ts`: The aligned timestamp the view uses for matching
- `home_candles_near_aligned`: Count of home candlesticks within 60 seconds
- `away_candles_near_aligned`: Count of away candlesticks within 60 seconds

If counts are 0, it means no candlesticks exist near the aligned timestamp, which would explain why the view might be using fallback values or NULL handling.

---

## Next Steps After Running Queries

1. **If Query 5 shows "NOT CONVERTED"**:
   - Root cause: View is using raw away price instead of converting
   - Action: Check view definition for conditional logic that skips conversion

2. **If Query 5 shows "No raw data found"**:
   - Root cause: LATERAL JOINs aren't finding matching candlesticks
   - Action: Check Query 7 to see if candlesticks exist near aligned timestamps

3. **If Query 7 shows 0 candlesticks**:
   - Root cause: No candlestick data exists for those aligned timestamps
   - Action: Investigate why view is showing 0.495 values (might be fallback/default)

4. **If Query 7 shows candlesticks exist**:
   - Root cause: View is matching different candlesticks or using wrong conversion
   - Action: Compare view's matched candlestick with Query 5's matched candlestick

---

## References

- **Alignment Formula**: `webapp/README.md` lines 518-542
- **View Definition**: `/tmp/snapshot_features_v1_view_definition.sql`
- **Python Implementation**: `scripts/trade/simulate_trading_strategy.py` lines 372-382
- **View Documentation**: `cursor-files/docs/most-up-to-date-material-view.md`
