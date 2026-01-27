# Parity Validation Report: ESPN-Direct vs Canonical Dataset

**Date**: 2026-01-15  
**Sprint**: S1-E1-S1  
**Purpose**: Validate that `derived.snapshot_features_v1` contains equivalent universe of games and snapshots as ESPN-direct training query before switching data sources.

## Executive Summary

**DECISION: NO-GO - Parity FAILS**

The canonical dataset (`derived.snapshot_features_v1`) only contains data for 2024 and 2025 seasons, while ESPN-direct training query has data from 2017-2025. This represents a **77.8% loss of training data** (7 out of 9 seasons missing).

**Recommendation**: Proceed with **Option B** - Keep ESPN-direct query and join with `external.sportsbook_odds_snapshots` by `game_id` and date. This preserves all historical training data while still enabling opening odds integration.

## Q3a: ESPN-Direct Game/Snapshot Counts

**Query**: ESPN-direct training query (what current training uses)

**Results**:

| season_start | game_count | unique_snapshot_count | snapshot_count |
|--------------|------------|----------------------|----------------|
| 2017 | 1,325 | 606,904 | 606,904 |
| 2018 | 1,390 | 662,287 | 662,287 |
| 2019 | 1,176 | 564,674 | 564,674 |
| 2020 | 1,261 | 588,189 | 588,189 |
| 2021 | 1,389 | 648,919 | 648,919 |
| 2022 | 1,385 | 652,258 | 652,258 |
| 2023 | 1,391 | 648,978 | 648,978 |
| 2024 | 1,394 | 660,185 | 660,185 |
| 2025 | 532 | 264,494 | 264,494 |
| **TOTAL** | **11,243** | **5,346,888** | **5,346,888** |

**Note**: `unique_snapshot_count` equals `snapshot_count` for all seasons, confirming no duplicate snapshots.

## Q3b: Canonical Dataset Game/Snapshot Counts

**Query**: `derived.snapshot_features_v1` (what we'd switch to)

**Results**:

| season_start | game_count | unique_snapshot_count | snapshot_count |
|--------------|------------|----------------------|----------------|
| 2024 | 84 | 40,140 | 40,140 |
| 2025 | 505 | 250,660 | 250,660 |
| **TOTAL** | **589** | **290,800** | **290,800** |

**Note**: Canonical dataset only contains 2024 and 2025 seasons. Missing 2017-2023 seasons entirely.

## Parity Comparison

### Game Count Parity

| season_start | ESPN-direct | Canonical | Difference | % Difference |
|--------------|-------------|-----------|------------|--------------|
| 2017 | 1,325 | 0 | -1,325 | -100.0% |
| 2018 | 1,390 | 0 | -1,390 | -100.0% |
| 2019 | 1,176 | 0 | -1,176 | -100.0% |
| 2020 | 1,261 | 0 | -1,261 | -100.0% |
| 2021 | 1,389 | 0 | -1,389 | -100.0% |
| 2022 | 1,385 | 0 | -1,385 | -100.0% |
| 2023 | 1,391 | 0 | -1,391 | -100.0% |
| 2024 | 1,394 | 84 | -1,310 | -94.0% |
| 2025 | 532 | 505 | -27 | -5.1% |
| **TOTAL** | **11,243** | **589** | **-10,654** | **-94.8%** |

**Analysis**: 
- **7 seasons completely missing** (2017-2023): 100% data loss
- **2024 season**: 94.0% data loss (1,394 games → 84 games)
- **2025 season**: 5.1% data loss (532 games → 505 games) - within tolerance
- **Overall**: 94.8% data loss - **PARITY FAILS**

### Snapshot Count Parity

| season_start | ESPN-direct | Canonical | Difference | % Difference |
|--------------|-------------|-----------|------------|--------------|
| 2017 | 606,904 | 0 | -606,904 | -100.0% |
| 2018 | 662,287 | 0 | -662,287 | -100.0% |
| 2019 | 564,674 | 0 | -564,674 | -100.0% |
| 2020 | 588,189 | 0 | -588,189 | -100.0% |
| 2021 | 648,919 | 0 | -648,919 | -100.0% |
| 2022 | 652,258 | 0 | -652,258 | -100.0% |
| 2023 | 648,978 | 0 | -648,978 | -100.0% |
| 2024 | 660,185 | 40,140 | -620,045 | -93.9% |
| 2025 | 264,494 | 250,660 | -13,834 | -5.2% |
| **TOTAL** | **5,346,888** | **290,800** | **-5,056,088** | **-94.6%** |

**Analysis**:
- **7 seasons completely missing** (2017-2023): 100% snapshot loss
- **2024 season**: 93.9% snapshot loss (660,185 → 40,140)
- **2025 season**: 5.2% snapshot loss (264,494 → 250,660) - within tolerance
- **Overall**: 94.6% snapshot loss - **PARITY FAILS**

### Time Bucket Distribution (2024 Season)

**Canonical Dataset Distribution**:

| time_bucket | snapshot_count |
|-------------|----------------|
| 2880-2400 | 6,085 |
| 2400-1800 | 8,586 |
| 1800-1200 | 8,150 |
| 1200-600 | 8,368 |
| 600-120 | 6,556 |
| 120-0 | 2,395 |
| **TOTAL** | **40,140** |

**Note**: Distribution appears reasonable (more snapshots in middle buckets, fewer at start/end), but cannot compare directly to ESPN-direct without running equivalent query.

## Label Parity Check

**Status**: **NOT VERIFIED** (cannot verify without matching snapshots)

**Reason**: Canonical dataset has only 84 games in 2024 season vs 1,394 games in ESPN-direct. The canonical dataset filters to games with Kalshi data (for simulation), which excludes most games needed for training.

**Impact**: Cannot verify label parity because the game universes are fundamentally different.

## Feature Parity Check

**Status**: **PARTIALLY VERIFIED** (sample comparison shows similar feature ranges)

**Sample Comparison (100 random snapshots from 2024 season)**:

| Source | Sample Size | Unique Games | Avg Point Diff | Avg Time Remaining |
|--------|-------------|--------------|----------------|-------------------|
| ESPN Sample | 100 | 97 | 2.13 | 1,435.12 |
| Canonical Sample | 100 | 58 | 2.79 | 1,309.95 |

**Analysis**:
- Feature ranges are similar (point_diff: 2.13 vs 2.79, time_remaining: 1,435 vs 1,310)
- However, canonical dataset has fewer unique games per sample (58 vs 97), indicating it's a subset
- Cannot verify exact feature matching because game universes don't overlap sufficiently

## Root Cause Analysis

**Why does parity fail?**

The canonical dataset (`derived.snapshot_features_v1`) is designed for **simulation** (ESPN + Kalshi join), not training. It filters to only games that have:
1. ESPN probability data
2. **Kalshi market data** (for simulation)

Kalshi data is only available for:
- 2024-25 season (partial coverage)
- 2025-26 season (full coverage)

Historical seasons (2017-2023) have no Kalshi data, so they are excluded from the canonical dataset.

## Decision: Option B (Join ESPN Tables with Opening Odds)

**Selected Approach**: Keep ESPN-direct query and join with `external.sportsbook_odds_snapshots` by `game_id` and date.

**Rationale**:
1. **Preserves all training data**: 11,243 games (2017-2025) vs 589 games (2024-2025 only)
2. **Maintains historical coverage**: 7 additional seasons of training data
3. **Still enables opening odds**: Can join `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`
4. **No data loss**: All ESPN snapshots remain available for training

**Implementation Plan**:
- Modify `_load_training_data()` in `train_winprob_catboost.py` to:
  1. Keep existing ESPN-direct query
  2. LEFT JOIN with `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`
  3. Join on `game_id` (ESPN `event_id` = `external.espn_game_id`) and date (fuzzy match ±1 day)
  4. Extract opening odds columns: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`

**Trade-offs**:
- **Pros**: Preserves all training data, maintains historical coverage, enables opening odds
- **Cons**: More complex query (join instead of direct query), requires date matching logic

## Validation Criteria Summary

| Criterion | Status | Details |
|-----------|--------|---------|
| Game Count Parity | ❌ FAIL | 94.8% data loss (11,243 → 589 games) |
| Snapshot Count Parity | ❌ FAIL | 94.6% data loss (5,346,888 → 290,800 snapshots) |
| Time Bucket Distribution | ⚠️ PARTIAL | Distribution looks reasonable but cannot compare directly |
| Label Parity | ❌ NOT VERIFIED | Game universes don't overlap sufficiently |
| Feature Parity | ⚠️ PARTIAL | Feature ranges similar but cannot verify exact matching |

## Conclusion

**Parity validation FAILS**. The canonical dataset excludes 94.8% of training data (7 out of 9 seasons missing, plus 94% of 2024 season).

**Decision**: Proceed with **Option B** - Join ESPN-direct query with `external.sportsbook_odds_snapshots` to preserve all training data while enabling opening odds integration.

**Next Steps**:
1. Proceed to Phase 2: Feature Engineering
2. Implement Option B approach (join ESPN tables with opening odds)
3. Update `_load_training_data()` to use ESPN-direct + opening odds join

---

**Report Generated**: 2026-01-15  
**Validated By**: Sprint Implementation  
**Status**: COMPLETE - NO-GO Decision Documented
