# ALIGN_DATA Warning Fix - Implementation

**Date**: 2026-01-26  
**Status**: ✅ **FIX IMPLEMENTED**

---

## Summary

Fixed false positive warnings in `scripts/trade/simulate_trading_strategy.py` by improving the warning logic to handle balanced market edge cases.

---

## Problem

The warning logic was triggering false positives when markets were balanced (~50/50):
- When both home and away are correctly converted to ~0.5, they sum to ~1.0
- The old logic assumed: "if `home + away ≈ 1.0`, then away is not converted"
- This is incorrect when markets are balanced

---

## Solution

Updated the warning logic to require **both conditions**:
1. `sum_check < 0.05` (home + away ≈ 1.0)
2. `diff_check > 0.10` (home ≠ away, clear indication of non-conversion)

This ensures we only warn when there's a **clear indication of non-conversion**, not when markets are just balanced.

---

## Code Changes

### File: `scripts/trade/simulate_trading_strategy.py`

**Lines 437-466**: Updated warning logic

**Before**:
```python
if diff_check < 0.05:
    pass  # No warning
elif sum_check < 0.05:
    # WARNING: This suggests canonical dataset switched to raw away-space
    logger.warning(...)
```

**After**:
```python
if diff_check < 0.05:
    # Current expected behavior: away is already converted, so home ≈ away
    # This is correct, no warning needed (even if sum ≈ 1.0 due to balanced markets)
    pass
elif sum_check < 0.05 and diff_check > 0.10:
    # WARNING: home + away ≈ 1.0 AND they're NOT close (diff > 0.10)
    # This suggests canonical dataset switched to raw away-space (away not converted)
    logger.warning(...)
```

### Key Changes

1. **Added condition**: `diff_check > 0.10` to the warning trigger
2. **Added documentation**: Explained the balanced market edge case
3. **Improved warning message**: Now includes both `sum_diff` and `diff` values for clarity

---

## Expected Impact

### Before Fix
- **False positives**: ~40 warnings per game (8.6% of snapshots)
- **10+ games affected** with 20-30% of snapshots triggering warnings
- **Warning noise**: Makes it hard to detect real issues

### After Fix
- **False positives**: Should be eliminated for balanced markets
- **Real issues**: Still detected when `home + away ≈ 1.0` AND `home ≠ away`
- **Warning clarity**: Only triggers when there's a clear conversion issue

---

## Testing Recommendations

1. **Re-run grid search** to verify warnings are reduced
2. **Check logs** for remaining warnings (should be minimal)
3. **Verify** that real conversion issues are still detected (if any exist)

---

## Verification

To verify the fix works:

```bash
# Re-run grid search and check for reduced warnings
python scripts/trade/grid_search_hyperparameters.py ...

# Check log file for [ALIGN_DATA] warnings
grep "\[ALIGN_DATA\]" grid_search.log | wc -l
```

**Expected**: Significantly fewer warnings (ideally zero for balanced markets)

---

## Related Documents

- `root_cause_analysis.md` - Detailed root cause analysis
- `final_analysis.md` - Final analysis with recommended fixes
- `query_analysis.md` - SQL query analysis and verification

---

**Status**: ✅ Fix implemented and ready for testing
