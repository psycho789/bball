# Grid Search Warnings Explanation

**Date**: 2026-01-26  
**Context**: Warnings observed when running grid search hyperparameter optimization

---

## Summary

These are **expected warnings**, not errors. They indicate:

1. **`[END_OF_GAME]` warnings**: Normal behavior - positions that remain open at game end are being closed with a realistic slippage penalty
2. **`[ALIGN_DATA]` warnings**: Data quality check - detecting potential data format inconsistency for one specific game

Both warnings are **informational** and don't stop the grid search from completing successfully.

---

## Warning #1: `[END_OF_GAME] Forced close LONG/SHORT with 2.0 cent slippage penalty`

### What It Means

When a trading position remains open at the end of a game (because the divergence never dropped below the exit threshold), the simulation **forces it to close** using the final market prices.

**Why This Happens**:
- Your trading strategy enters positions when ESPN and Kalshi probabilities diverge significantly
- It exits when the divergence drops below the exit threshold
- Sometimes, the divergence stays above the exit threshold until the game ends
- These positions must be closed at game end (you can't hold positions after the game finishes)

### The Slippage Penalty

The code applies a **2 cent slippage penalty** to account for:

1. **Liquidity collapse**: As games approach the end, market makers pull their quotes
2. **Execution difficulty**: It becomes harder to execute trades in the final moments
3. **Realistic modeling**: In real trading, you'd face worse execution prices at game end

**Code Location**: `scripts/trade/simulate_trading_strategy.py` lines 1382-1392

```python
# Apply forced slippage penalty for end-of-game closes
forced_slippage_cents = 2.0  # Conservative estimate for late-game liquidity collapse
if state.open_position == "long_espn":
    final_kalshi_bid = final_kalshi_bid - (forced_slippage_cents / 100.0)
    logger.warning(f"[END_OF_GAME] Forced close LONG with {forced_slippage_cents} cent slippage penalty")
```

### Impact on Results

- **Reduces profit slightly**: Each forced close reduces profit by 2 cents per contract
- **More realistic**: Accounts for real-world execution difficulty
- **Expected behavior**: This is intentional and correct - it makes the simulation more realistic

### Is This a Problem?

**No, this is expected and correct behavior.** The warnings are just informational - they're telling you that some positions had to be force-closed at game end, which is normal.

**What to look for**:
- If you see **many** of these warnings, it might indicate your exit threshold is too high (positions aren't exiting naturally)
- If you see **few** of these warnings, your exit strategy is working well

---

## Warning #2: `[ALIGN_DATA] Game 401809981: WARNING - home + away prices sum to ~1.0`

### What It Means

This warning detects a potential data format inconsistency. It's checking whether Kalshi prices are stored correctly.

**Expected Behavior**:
- Kalshi markets can represent either the **home team** or **away team** winning
- The canonical dataset should convert away-team prices to home-team probability space
- If `home_price + away_price ≈ 1.0`, it suggests the away price might still be in "raw away space" (not converted)

**Example**:
- Home price: 0.4850 (48.5% chance home wins)
- Away price: 0.5500 (55% chance away wins)
- Sum: 0.4850 + 0.5500 = 1.0350 ≈ 1.0
- **Warning**: This suggests away price might not be converted to home space

### Why This Happens

The code checks for this pattern to detect if the database view (`derived.snapshot_features_v1`) has changed its data format:

```python
# Check if away is already converted (home ≈ away) or raw (home + away ≈ 1.0)
diff_check = abs(home_norm - away_norm)  # Should be small if converted
sum_check = abs((home_norm + away_norm) - 1.0)  # Would be small if raw

if sum_check < 0.05:
    # WARNING: This suggests canonical dataset switched to raw away-space
    logger.warning(f"[ALIGN_DATA] Game {game_id}: WARNING - home + away prices sum to ~1.0...")
```

**Code Location**: `scripts/trade/simulate_trading_strategy.py` lines 446-457

### Impact on Results

- **Limited impact**: This warning appears for **one specific game** (401809981)
- **Data quality check**: It's detecting a potential inconsistency, not causing incorrect calculations
- **Fallback handling**: The code has fallback logic to handle this case correctly

### Is This a Problem?

**Probably not a critical issue**, but worth investigating:

1. **If it's just one game**: Likely a data quality issue for that specific game, not a systemic problem
2. **If it's many games**: Could indicate the database view changed format and needs updating
3. **Current behavior**: The code handles this gracefully with fallback logic

**What to do**:
- Check if this warning appears for many games or just a few
- If just one game (like 401809981), it's likely fine - just a data quality issue
- If many games, investigate the `derived.snapshot_features_v1` view to ensure it's converting away prices correctly

---

## Overall Assessment

### Are These Errors?

**No, these are warnings, not errors.** The grid search will complete successfully.

### Should You Be Concerned?

**Minimal concern**:

1. **`[END_OF_GAME]` warnings**: **Expected and correct** - this is how the simulation handles positions that don't exit naturally
2. **`[ALIGN_DATA]` warnings**: **Informational** - detecting a potential data format issue for one game, but the code handles it correctly

### What to Monitor

1. **Frequency of `[END_OF_GAME]` warnings**:
   - Many warnings → Consider lowering exit threshold
   - Few warnings → Exit strategy is working well

2. **Frequency of `[ALIGN_DATA]` warnings**:
   - One game → Likely fine, just data quality issue
   - Many games → Investigate database view format

### Next Steps

1. **Let the grid search complete** - these warnings won't stop it
2. **Review results** - check if the forced closes are affecting your profit calculations significantly
3. **If needed**: Adjust exit thresholds if too many positions are force-closed at game end

---

## Technical Details

### End-of-Game Forced Close Logic

```python
# From simulate_trading_strategy.py:1382-1392
forced_slippage_cents = 2.0  # 2 cent penalty
if state.open_position == "long_espn":
    # Long position: sell at bid, so reduce bid price (worse execution)
    final_kalshi_bid = final_kalshi_bid - (forced_slippage_cents / 100.0)
elif state.open_position == "short_espn":
    # Short position: buy at ask, so increase ask price (worse execution)
    final_kalshi_ask = final_kalshi_ask + (forced_slippage_cents / 100.0)
```

**Why 2 cents?**:
- Conservative estimate for late-game liquidity collapse
- Accounts for market makers pulling quotes
- Makes simulation more realistic

### Data Alignment Check Logic

```python
# From simulate_trading_strategy.py:446-457
diff_check = abs(home_norm - away_norm)  # Should be small if converted
sum_check = abs((home_norm + away_norm) - 1.0)  # Would be small if raw

if diff_check < 0.05:
    # Correct: away is already converted to home space
    pass
elif sum_check < 0.05:
    # Warning: away might still be in raw away space
    logger.warning(...)
```

**Expected values**:
- **Converted**: `home_price ≈ away_price` (both in home space)
- **Raw**: `home_price + away_price ≈ 1.0` (complementary probabilities)

---

## Summary

| Warning | Type | Severity | Action Needed |
|---------|------|----------|---------------|
| `[END_OF_GAME]` | Expected behavior | Low | None - this is correct |
| `[ALIGN_DATA]` | Data quality check | Low-Medium | Monitor frequency, investigate if many games |

**Bottom line**: These warnings are **informational** and indicate the simulation is working as designed. The grid search will complete successfully.
