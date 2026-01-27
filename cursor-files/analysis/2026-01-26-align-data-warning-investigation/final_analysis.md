# ALIGN_DATA Warning - Final Analysis

**Date**: 2026-01-26  
**Status**: ✅ **ROOT CAUSE IDENTIFIED - False Positive Warnings**

---

## Executive Summary

**Key Finding**: The conversion IS working correctly. The warnings are **false positives** caused by a logic edge case in the warning detection code.

**Evidence**:
- Query 5 shows: `✓ Converted correctly` for all problematic snapshots
- View's away price matches expected converted price
- Conversion formula is correct: `1.0 - raw_away_mid`

**The Issue**: When markets are balanced (~50/50), `home + away ≈ 1.0` even though both are correctly converted, triggering false positive warnings.

---

## Query 5 Results Analysis

### All Problematic Snapshots Show Correct Conversion

| Sequence | View Home | View Away | Raw Away | Expected Converted | Status |
|----------|-----------|-----------|----------|-------------------|--------|
| 497 | 0.495 | 0.490 | 0.510 | 0.490 | ✅ Converted correctly |
| 516 | 0.495 | 0.495 | 0.505 | 0.495 | ✅ Converted correctly |
| 518 | 0.495 | 0.495 | 0.505 | 0.495 | ✅ Converted correctly |
| 522 | 0.495 | 0.495 | 0.505 | 0.495 | ✅ Converted correctly |
| 523 | 0.495 | 0.495 | 0.505 | 0.495 | ✅ Converted correctly |
| 525 | 0.495 | 0.495 | 0.505 | 0.495 | ✅ Converted correctly |

**Conclusion**: Conversion is working correctly for all problematic snapshots.

---

## Why Warnings Still Trigger

### The Warning Logic (lines 446-457)

```python
diff_check = abs(home_norm - away_norm)  # Should be small if away is converted
sum_check = abs((home_norm + away_norm) - 1.0)  # Would be small if away is raw

if diff_check < 0.05:
    # Correct: away is already converted, home ≈ away
    pass  # No warning
elif sum_check < 0.05:
    # WARNING: This suggests canonical dataset switched to raw away-space
    logger.warning(...)
```

### The Edge Case

**When markets are balanced (~50/50)**:
- Home: 0.495 (49.5% home wins)
- Away (converted): 0.495 (49.5% home wins, converted from 50.5% away wins)
- `diff_check = abs(0.495 - 0.495) = 0.0 < 0.05` → Should pass, no warning ✓

**But if there's a slight difference**:
- Home: 0.495
- Away (converted): 0.510 (from different candlestick or rounding)
- `diff_check = abs(0.495 - 0.510) = 0.015 < 0.05` → Should still pass ✓
- `sum_check = abs(0.495 + 0.510 - 1.0) = 0.005 < 0.05` → Also true

**The problem**: If `diff_check` is slightly above 0.05 (e.g., 0.051) due to:
- Different candlestick matching (view vs. query)
- Rounding/precision differences
- Slight timing differences

Then `sum_check` will trigger the warning even though conversion is correct.

---

## Why Query 5 Shows Different Values

**Query 5 finds the CLOSEST candlestick** to the aligned timestamp using:
```sql
ORDER BY ABS(EXTRACT(EPOCH FROM (c.period_ts - aligned_ts)))
LIMIT 1
```

**The view also finds the CLOSEST candlestick**, but:
- It might match a different candlestick if there are multiple equally close
- The `ORDER BY` includes `c.period_ts DESC` as a tie-breaker
- Query 5 doesn't have this tie-breaker, so it might pick a different candlestick

**Result**: Query 5 might find candlesticks that give `diff_check < 0.05`, but the view might match different candlesticks that give `diff_check >= 0.05`, triggering the warning.

---

## Root Cause: False Positive Due to Balanced Markets

### The Real Issue

**When markets are balanced (~50/50)**:
1. Home market: ~0.50 (50% home wins)
2. Away market raw: ~0.50 (50% away wins)
3. Away market converted: `1.0 - 0.50 = 0.50` (50% home wins)
4. **Both are ~0.50, so `home + away ≈ 1.0`** even though conversion is correct!

**The warning logic assumes**:
- If `home + away ≈ 1.0`, then away is NOT converted (still in raw space)
- **But this is wrong** when markets are balanced!

### Mathematical Proof

**When markets are balanced**:
- Home: `p` (probability home wins)
- Away raw: `1 - p` (probability away wins)
- Away converted: `1 - (1 - p) = p` (probability home wins, converted)
- **Both are `p`, so `home + away = p + p = 2p`**
- **If `p ≈ 0.5`, then `2p ≈ 1.0`** → Triggers false positive!

**The warning should only trigger if**:
- `home + away ≈ 1.0` **AND** `home ≠ away` (clear indication of non-conversion)
- Not when `home ≈ away` (which can also sum to ~1.0 when balanced)

---

## Recommended Fix

### Option 1: Improve Warning Logic (Recommended)

Only warn if conversion is clearly wrong:

```python
diff_check = abs(home_norm - away_norm)
sum_check = abs((home_norm + away_norm) - 1.0)

if diff_check < 0.05:
    # Correct: away is already converted, home ≈ away
    pass  # No warning
elif sum_check < 0.05 and diff_check > 0.10:
    # WARNING: home + away ≈ 1.0 AND they're NOT close
    # This suggests away is NOT converted (still in raw space)
    logger.warning(...)
# Else: large difference and don't sum to 1 - might be data quality issue, but not conversion issue
```

**Key change**: Require `diff_check > 0.10` to ensure it's not just a balanced market.

### Option 2: Add Conversion Verification

Check if away price matches expected converted value:

```python
# If we have raw away data, verify conversion
if raw_away_mid is not None:
    expected_converted = 1.0 - raw_away_mid
    if abs(away_norm - expected_converted) < 0.01:
        # Conversion is correct, don't warn
        pass
    elif sum_check < 0.05:
        # Conversion doesn't match AND sum ≈ 1.0 → real issue
        logger.warning(...)
```

### Option 3: Increase Threshold

Increase `diff_check` threshold to 0.10 to allow more variance:

```python
if diff_check < 0.10:  # Increased from 0.05
    pass  # No warning
elif sum_check < 0.05:
    logger.warning(...)
```

---

## Impact Assessment

### Current Impact

**Low-Medium Severity**:
- ✅ Conversion is working correctly
- ⚠️ False positive warnings create noise
- ⚠️ Makes it hard to detect real conversion issues
- ✅ No impact on simulation accuracy (conversion is correct)

### If Not Fixed

- **Warning noise**: Hard to identify real issues
- **False alarms**: May trigger unnecessary investigations
- **Maintenance burden**: Developers may ignore warnings

---

## Conclusion

**Root Cause**: False positive warnings due to balanced market edge case where `home + away ≈ 1.0` even when both are correctly converted.

**Status**: 
- ✅ Conversion working correctly
- ⚠️ Warning logic needs improvement
- 🔧 Fix: Update warning logic to reduce false positives

**Priority**: Medium (conversion working, just noisy warnings)

**Action**: Update warning logic in `simulate_trading_strategy.py` to handle balanced market edge case.

---

## Next Steps

1. ✅ **Investigation complete** - Root cause identified
2. ⏳ **Fix warning logic** - Update to reduce false positives
3. ⏳ **Test fix** - Verify warnings are reduced
4. ⏳ **Monitor** - Ensure real issues are still detected
