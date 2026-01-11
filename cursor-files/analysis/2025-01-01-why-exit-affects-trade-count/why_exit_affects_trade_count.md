# Why Exit Threshold Affects Trade Count

## Your Friend's Question:
> "Why does the exit affect the number of trades? The ENTER determines number of trades you take, right?"

**Short answer:** Your friend is mostly right - entry threshold is the PRIMARY driver. But exit threshold affects trade count SECONDARILY because you can only have ONE position open at a time, so exiting earlier allows you to re-enter more times per game.

---

## How The Simulation Works:

### Key Constraint:
- **Only ONE open position at a time** (state machine)
- You must exit before you can enter again

### Entry Logic:
- Enter when: `|ESPN_prob - Kalshi_price| > entry_threshold` AND divergence is widening
- Entry threshold = PRIMARY driver of trade count

### Exit Logic:
- Exit when: `|ESPN_prob - Kalshi_price| < exit_threshold` (divergence converges)
- Exit threshold = SECONDARY driver (affects round trips per game)

---

## Why Exit Threshold Matters:

### Scenario: Same Entry Threshold (0.15), Different Exit Thresholds

**Game Example:** ESPN and Kalshi diverge multiple times during a game:
- Minute 5: Divergence = 16% → **ENTER** (meets 15% entry threshold)
- Minute 10: Divergence = 8% → **EXIT** (if exit=5%) OR **HOLD** (if exit=0%)
- Minute 15: Divergence = 17% → **RE-ENTER** (if you exited at minute 10) OR **CAN'T ENTER** (if still holding)

### With Exit Threshold = 0.05 (5%):
1. Enter at minute 5 (divergence = 16%)
2. Exit at minute 10 (divergence = 8% < 5% threshold) ✅
3. **Re-enter at minute 15** (divergence = 17% again) ✅
4. **Result: 2 trades** (or more if it happens again)

### With Exit Threshold = 0.00 (0%):
1. Enter at minute 5 (divergence = 16%)
2. **Still holding at minute 10** (divergence = 8% > 0% threshold)
3. **Still holding at minute 15** (can't enter, already in position)
4. **Result: 1 trade** (or 0 if divergence never fully converges)

---

## The Data Shows This:

From your test at entry=0.15:
- Exit 0.00: **7 trades** (very few exits, mostly held to end of game)
- Exit 0.01: **44 trades** (exits early, allows re-entries)
- Exit 0.05: **70 trades** (exits very early, maximum re-entries)

**Pattern:** Lower exit threshold = more exits = more opportunities to re-enter = more trades

---

## But Your Friend Is Right:

**Entry threshold is still the PRIMARY driver:**
- Entry 0.02: ~500+ trades (enters on small divergences)
- Entry 0.10: ~200 trades (enters on larger divergences)
- Entry 0.15: ~50 trades (enters on very large divergences)

**Exit threshold is SECONDARY:**
- It only affects how many **round trips** you can make per game
- It doesn't change whether you CAN enter (that's entry threshold)
- It changes whether you can **re-enter** after exiting

---

## Analogy:

Think of it like parking spots:
- **Entry threshold** = How far you're willing to walk (determines if you park at all)
- **Exit threshold** = How quickly you leave (determines if you can grab a better spot later)

If you exit quickly (low exit threshold), you can:
- Leave your spot
- Grab a better spot if one opens up
- Make multiple round trips

If you exit slowly (high exit threshold), you:
- Stay in your spot longer
- Miss opportunities to grab better spots
- Make fewer round trips

---

## Bottom Line:

Your friend is correct that **entry threshold is the main driver**. Exit threshold is a secondary effect that affects:
1. **How many round trips** you can make per game
2. **Whether you can re-enter** if divergence widens again
3. **Position turnover rate**

But the fundamental question of "do I enter at all?" is determined by entry threshold.

