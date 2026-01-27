# Story 1.3: Closing Line / Pre-Tip Line Data Availability Analysis

**Date**: Sat Jan 24 2026  
**Status**: ✅ **COMPLETED**

## Summary

Analysis of timestamped odds data availability for closing/pre-tip line alternative shows **very limited coverage** compared to opening odds. Only 394 games (3.5% of total games) have timestamped closing/pre-tip odds data, making this alternative **not viable** for current training needs.

## Query Executed

**File**: `closing_line_analysis.sql`  
**Date**: Sat Jan 24 2026  
**Database**: PostgreSQL via `DATABASE_URL`

## Results

### Coverage Statistics

| Metric | Count | Percentage of Total Games |
|--------|-------|--------------------------|
| **Total completed games** | 11,381 | 100% |
| **Games with opening odds** | 10,742 | 94.4% |
| **Games with timestamped closing/pre-tip odds** | 394 | 3.5% |
| **Games within 5 minutes** | 58 | 0.5% |
| **Games within 15 minutes** | 70 | 0.6% |
| **Games within 60 minutes** | 147 | 1.3% |

### Detailed Results

```
total_games_with_timestamped_odds: 394
games_within_5_minutes: 58
games_within_15_minutes: 70
games_within_60_minutes: 147
games_with_pre_tip_odds: 394 (all have pre-tip odds)
avg_minutes_before_start: -231 minutes (~3.85 hours before game)
earliest_minutes_before_start: -1721 minutes (~28.7 hours before game)
```

### Coverage Analysis

**5-minute window**:
- Coverage: 58 games (0.5% of total games)
- **Verdict**: ❌ **Insufficient** - Too few games for training

**15-minute window**:
- Coverage: 70 games (0.6% of total games)
- **Verdict**: ❌ **Insufficient** - Too few games for training

**60-minute window**:
- Coverage: 147 games (1.3% of total games)
- **Verdict**: ❌ **Insufficient** - Too few games for training

**All pre-tip odds** (any time before game start):
- Coverage: 394 games (3.5% of total games)
- **Verdict**: ❌ **Insufficient** - Less than 4% coverage

## Comparison: Opening Odds vs. Closing/Pre-Tip Odds

| Data Source | Games Available | Coverage | Status |
|-------------|----------------|----------|--------|
| **Opening odds** | 10,742 | 94.4% | ✅ **Viable** - Sufficient for training |
| **Closing/pre-tip odds (60 min)** | 147 | 1.3% | ❌ **Not viable** - Insufficient coverage |
| **Closing/pre-tip odds (all)** | 394 | 3.5% | ❌ **Not viable** - Insufficient coverage |

## Key Findings

1. **Very Limited Coverage**: 
   - Only 394 games (3.5%) have timestamped closing/pre-tip odds
   - Even the most lenient window (60 minutes) only covers 147 games (1.3%)
   - This is far below the 10,742 games (94.4%) available with opening odds

2. **Timing Patterns**:
   - Average snapshot is ~231 minutes (3.85 hours) before game start
   - Earliest snapshot is ~1721 minutes (28.7 hours) before game start
   - Most closing/pre-tip odds are actually captured hours before the game, not minutes

3. **Data Availability Gap**:
   - Opening odds: 10,742 games (94.4% coverage) ✅
   - Closing/pre-tip odds: 394 games (3.5% coverage) ❌
   - **Gap**: 10,348 games difference (91% of games missing closing/pre-tip data)

## Recommendations

### ❌ **NOT RECOMMENDED** for Current Implementation

**Rationale**:
- Coverage is too low (3.5% vs 94.4% for opening odds)
- Insufficient data for model training (need thousands of games, not hundreds)
- Would require significant data collection improvements

### ✅ **RECOMMENDED** Actions

1. **Continue using opening odds** for current models:
   - 94.4% coverage provides sufficient training data
   - Well-established data pipeline
   - Proven performance

2. **Future consideration** (if data collection improves):
   - Monitor closing/pre-tip odds data collection
   - Re-evaluate when coverage exceeds 50% of games
   - Consider hybrid approach (opening odds + closing odds when available)

3. **Data collection improvements** (if closing/pre-tip odds desired):
   - Increase frequency of odds snapshots near game time
   - Ensure `snapshot_timestamp` is populated for all odds snapshots
   - Target: Capture odds within 15-60 minutes of game start for >80% of games

## Impact on Current Sprint

**No impact** - This analysis confirms that:
- ✅ Removing redundant `has_opening_moneyline` feature is correct approach
- ✅ Continuing with opening odds is the right choice
- ✅ No need to switch to closing/pre-tip odds (insufficient data)

## Future Work

If closing/pre-tip odds become available with better coverage:
1. Re-run this analysis to check updated coverage
2. Evaluate performance improvement (closing odds may be more predictive)
3. Consider implementing as optional feature (use when available, fallback to opening odds)

---

**Story 1.3 Status**: ✅ **COMPLETE** - Analysis shows closing/pre-tip odds not viable due to insufficient coverage (3.5% vs 94.4% for opening odds)
