# Sprint 15: Fix Canonical View Alignment Regression

**Date**: Mon Jan  5 05:00:47 PST 2026  
**Sprint Duration**: 1 day (6-8 hours total)  
**Sprint Goal**: Fix correctness regression in `get_aligned_data()` that causes games to be skipped and produces incorrect P&L calculations when using the canonical view `derived.snapshot_features_v1`. Success criteria: (1) Previously skipped games now have aligned_data > 0, (2) P&L values are within expected ranges (not wildly off), (3) All range checks pass with proper normalization.  
**Current Status**: `get_aligned_data()` in `scripts/simulate_trading_strategy.py` only queries home Kalshi fields (`kalshi_home_mid_price`, `kalshi_home_bid`, `kalshi_home_ask`) and skips rows where `kalshi_home_mid_price IS NULL`, causing games with only away market data to be skipped. No normalization/range safety exists, allowing 0-100 scaled values to cause incorrect divergence calculations and P&L.  
**Target Status**: `get_aligned_data()` queries both home and away Kalshi fields, converts away→home when home is missing (with correct bid/ask swap), normalizes all values to 0-1 range, enforces strict range checks, and provides detailed debug counters. `simulate_trading_strategy()` adds runtime guards before divergence calculations.  
**Team Size**: 1 developer  
**Sprint Lead**: AI Assistant

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline
- **Test Results**: No automated test suite exists for simulation code
- **QC Results**: N/A (code change, not data ingestion)
- **Code Coverage**: N/A (no test coverage metrics)
- **Build Status**: Python scripts execute successfully

**Purpose**: This baseline ensures we maintain or improve code quality throughout the sprint and provides historical reference for quality metrics.

## Database Evidence Template
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database** - no INSERT, UPDATE, ALTER, TRUNCATE, DELETE unless part of sprint plan
- **DO NOT modify database users** - no user management or system changes

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

**Git Usage Rules**:
- **NO git commands** unless explicitly mentioned in sprint plan
- **NO git operations** unless explicitly mentioned in analysis
- **NO version control** unless explicitly mentioned in prompt by prompter
- **NO commits, pushes, pulls, or branches** unless explicitly directed
- **NO git status, git log, or git diff** unless explicitly mentioned in sprint plan

**Exception**: Git usage is only allowed when:
1. Explicitly mentioned in the analysis document
2. Explicitly mentioned in the sprint plan
3. Explicitly mentioned in the prompt by the prompter that git can be used

## Sprint Overview

### Business Context
- **Business Driver**: Trading simulation produces incorrect results and skips valid games, leading to unreliable P&L analysis and missed trading opportunities. This regression was introduced when optimizing `get_aligned_data()` to use the canonical view for performance.
- **Success Criteria**: (1) All previously skipped games now process successfully with aligned_data > 0, (2) P&L calculations are accurate (within expected ranges), (3) No games are incorrectly skipped due to home-only data filtering
- **Stakeholders**: Trading strategy analysis users, simulation accuracy requirements
- **Timeline Constraints**: Fix must be completed before next trading analysis cycle

### Technical Context
- **Current System State**: `scripts/simulate_trading_strategy.py::get_aligned_data()` queries canonical view `derived.snapshot_features_v1` but only selects home Kalshi fields (`kalshi_home_mid_price`, `kalshi_home_bid`, `kalshi_home_ask`). Rows where `kalshi_home_mid_price IS NULL` are skipped, causing games with only away market data to be reported as "No aligned data". No normalization exists, so if canonical view returns 0-100 scaled values, divergence calculations explode and P&L becomes incorrect.
- **Target System State**: `get_aligned_data()` queries both home and away Kalshi fields, converts away→home probability space when home is missing (with correct bid/ask swap: `home_bid = 1 - away_ask`, `home_ask = 1 - away_bid`), normalizes all values to 0-1 range via `_norm01()` helper, enforces strict [0,1] range checks, and provides detailed debug counters. `simulate_trading_strategy()` adds runtime guards before divergence calculations.
- **Architecture Impact**: No architectural changes - fixes are contained within existing functions
- **Integration Points**: Canonical view `derived.snapshot_features_v1` (read-only), simulation endpoint `webapp/api/endpoints/simulation.py` (uses `get_aligned_data()`)

### Sprint Scope
- **In Scope**: 
  - Fix `get_aligned_data()` to query both home and away fields
  - Implement away→home conversion with bid/ask swap
  - Add normalization helper `_norm01()` and apply to all probability/price fields
  - Add strict range checks [0,1] with warnings for out-of-range values
  - Add detailed debug counters (filtered_missing_espn, filtered_missing_kalshi, filtered_out_of_range, filtered_by_time_window)
  - Add runtime guards in `simulate_trading_strategy()` before divergence calculations
  - Improve logging with summary statistics
- **Out of Scope**: 
  - Changes to canonical view definition (read-only)
  - Changes to trading strategy logic (only guards added)
  - Performance optimizations (focus on correctness)
  - Test suite creation (manual validation only)
- **Assumptions**: 
  - Canonical view `derived.snapshot_features_v1` contains both `kalshi_home_*` and `kalshi_away_*` columns (verified in `cursor-files/docs/fix_time_alignment_materialized_view.md`)
  - ESPN probabilities and Kalshi prices should be in 0-1 range, but defensive normalization handles 0-100 case
  - Old implementation used "home if available else convert away→home" logic (assumed from requirements)
- **Constraints**: 
  - Must maintain backward compatibility with existing simulation endpoint API
  - Must not modify canonical view (read-only)
  - Must preserve existing function signatures

## Sprint Phases

### Phase 1: Fix get_aligned_data() Query and Away→Home Conversion (Duration: 2-3 hours)
**Objective**: Update `canonical_sql` to query both home and away Kalshi fields, implement away→home conversion logic with correct bid/ask swap when home data is missing
**Dependencies**: Access to `scripts/simulate_trading_strategy.py`, understanding of canonical view schema
**Deliverables**: Updated `get_aligned_data()` function with dual-field query and conversion logic

### Phase 2: Add Normalization and Range Safety (Duration: 2 hours)
**Objective**: Implement `_norm01()` helper function, apply normalization to all probability/price fields, add strict [0,1] range checks with warnings
**Dependencies**: Must complete Phase 1
**Deliverables**: Normalization helper and range checks integrated into `get_aligned_data()`

### Phase 3: Improve Debug Counters and Logging (Duration: 1 hour)
**Objective**: Add explicit counters for filtered rows (missing_espn, missing_kalshi, out_of_range, time_window), add summary logging with percentages
**Dependencies**: Must complete Phase 2
**Deliverables**: Enhanced logging with detailed counters and summary statistics

### Phase 4: Add Runtime Guards in simulate_trading_strategy() (Duration: 1 hour)
**Objective**: Add strict range checks in `simulate_trading_strategy()` before divergence calculations to prevent bad-scaled data from entering trades
**Dependencies**: Must complete Phase 3
**Deliverables**: Runtime guards added to `simulate_trading_strategy()` function

### Phase 5: Sprint Quality Assurance (Duration: 1-2 hours) [MANDATORY]
**Objective**: Validate all changes, test with previously skipped games, verify P&L accuracy, update documentation, ensure quality gates pass
**Dependencies**: Must complete Phase 4 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, validation test results

## Sprint Backlog

### Epic 1: Fix get_aligned_data() Home-Only Regression
**Priority**: Critical (correctness regression causing skipped games)
**Estimated Time**: 3-4 hours (2-3 hours Phase 1, 1 hour Phase 3)
**Dependencies**: `scripts/simulate_trading_strategy.py`, canonical view `derived.snapshot_features_v1`
**Status**: Not Started
**Phase Assignment**: Phases 1 and 3

#### Story 1.1: Query Both Home and Away Kalshi Fields
- **ID**: S15-E1-S1
- **Type**: Bug Fix
- **Priority**: Critical (games are skipped without this)
- **Estimate**: 1 hour (30 min query update, 30 min testing)
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`, lines 178-190)
- **Files to Create**: None
- **Dependencies**: PostgreSQL connection via `DATABASE_URL`, canonical view `derived.snapshot_features_v1`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `canonical_sql` query includes `kalshi_away_mid_price`, `kalshi_away_bid`, `kalshi_away_ask` columns
  - [ ] Query executes successfully: `psql "$DATABASE_URL" -c "SELECT kalshi_home_mid_price, kalshi_away_mid_price FROM derived.snapshot_features_v1 WHERE game_id = '401810277' LIMIT 1"`
  - [ ] Row processing loop accesses away fields: `row[5]`, `row[6]`, `row[7]` (or appropriate indices)
  - [ ] Function signature unchanged: `get_aligned_data(conn, game_id, exclude_first_seconds=0, exclude_last_seconds=0, use_trade_data=False)`

- **Technical Context**:
  - **Current State**: 
    ```python
    canonical_sql = """
    SELECT 
        snapshot_ts,
        espn_home_prob,
        kalshi_home_mid_price,
        kalshi_home_bid,
        kalshi_home_ask,
        time_remaining
    FROM derived.snapshot_features_v1
    WHERE game_id = %s 
      AND season_label = '2025-26'
    ORDER BY sequence_number, snapshot_ts
    """
    ```
  - **Required Changes**: Add `kalshi_away_mid_price`, `kalshi_away_bid`, `kalshi_away_ask` to SELECT clause. Update row unpacking to include away fields.
  - **Integration Points**: Connects to canonical view `derived.snapshot_features_v1` (read-only)
  - **Data Structures**: Row tuple indices change: `row[0]`=snapshot_ts, `row[1]`=espn_home_prob, `row[2]`=kalshi_home_mid_price, `row[3]`=kalshi_home_bid, `row[4]`=kalshi_home_ask, `row[5]`=time_remaining (current). After change: `row[5]`=kalshi_away_mid_price, `row[6]`=kalshi_away_bid, `row[7]`=kalshi_away_ask, `row[8]`=time_remaining
  - **API Contracts**: No API changes - internal function only

- **Implementation Steps**:
  1. **Update canonical_sql SELECT clause**: Add `kalshi_away_mid_price`, `kalshi_away_bid`, `kalshi_away_ask` after `kalshi_home_ask`
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify lines 178-190
     - Content: Add three columns to SELECT list
  2. **Update row unpacking**: Extract away fields from row tuple
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify lines 214-220
     - Content: Add `kalshi_away_mid_price = row[5]`, `kalshi_away_bid = row[6]`, `kalshi_away_ask = row[7]`, update `time_remaining = row[8]`

- **Validation Steps**:
  1. **Verify query syntax**: `source .env && psql "$DATABASE_URL" -c "SELECT snapshot_ts, espn_home_prob, kalshi_home_mid_price, kalshi_home_bid, kalshi_home_ask, kalshi_away_mid_price, kalshi_away_bid, kalshi_away_ask, time_remaining FROM derived.snapshot_features_v1 WHERE game_id = '401810277' AND season_label = '2025-26' LIMIT 1"`
     - Expected Output: Query executes without error, returns 1 row with 9 columns
  2. **Test function call**: `python -c "from scripts.simulate_trading_strategy import get_aligned_data; from scripts._db_lib import connect; conn = connect(); data, start, dur, outcome = get_aligned_data(conn, '401810277'); print(f'Aligned points: {len(data)}')"`
     - Expected Output: Function executes without IndexError, aligned points >= 0

- **Definition of Done**:
  - [ ] `canonical_sql` includes all 9 columns (snapshot_ts, espn_home_prob, kalshi_home_mid_price, kalshi_home_bid, kalshi_home_ask, kalshi_away_mid_price, kalshi_away_bid, kalshi_away_ask, time_remaining)
  - [ ] Row unpacking correctly extracts all 9 values
  - [ ] Function executes without IndexError
  - [ ] Query validation step passes

- **Rollback Plan**: Revert SELECT clause to original 6 columns, revert row unpacking to original indices
- **Risk Assessment**: Low risk - read-only query change, no data modification
- **Success Metrics**: Query executes successfully, function runs without errors

#### Story 1.2: Implement Away→Home Conversion with Bid/Ask Swap
- **ID**: S15-E1-S2
- **Type**: Bug Fix
- **Priority**: Critical (enables processing games with only away market data)
- **Estimate**: 1.5 hours (1 hour implementation, 30 min testing)
- **Phase**: Phase 1
- **Prerequisites**: S15-E1-S1 (must have away fields available)
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`, lines 250-254)
- **Files to Create**: None
- **Dependencies**: Away fields from Story 1.1

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] When `kalshi_home_mid_price IS NULL` and `kalshi_away_mid_price IS NOT NULL`, conversion occurs: `kalshi_price = 1 - kalshi_away_mid_price`
  - [ ] Bid/ask swap is correct: `kalshi_bid = 1 - kalshi_away_ask`, `kalshi_ask = 1 - kalshi_away_bid`
  - [ ] When home data exists, it is used directly (no conversion)
  - [ ] Games with only away data now produce aligned_data > 0 (previously skipped games)

- **Technical Context**:
  - **Current State**:
    ```python
    # Use Kalshi home market data (preferred) or fall back to away market if needed
    # Canonical dataset already handles home/away market selection
    kalshi_price = kalshi_home_mid_price
    kalshi_bid = kalshi_home_bid
    kalshi_ask = kalshi_home_ask
    ```
  - **Required Changes**: Add conditional logic: if home mid is None and away mid is not None, convert away→home with bid/ask swap. Otherwise use home directly.
  - **Integration Points**: Used by row processing loop to populate `aligned_data` dict
  - **Data Structures**: Probability values in 0-1 range (before normalization)
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. **Replace direct assignment with conditional logic**: Check if home mid is None, if so check away mid
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify lines 250-254
     - Content:
       ```python
       # Prefer home fields when present
       # Else if away mid is present: convert away → home probability space
       # AND swap bid/ask correctly: home_bid = 1 - away_ask, home_ask = 1 - away_bid
       if kalshi_home_mid_price is not None:
           kalshi_price = kalshi_home_mid_price
           kalshi_bid = kalshi_home_bid
           kalshi_ask = kalshi_home_ask
       elif kalshi_away_mid_price is not None:
           kalshi_price = 1 - kalshi_away_mid_price
           kalshi_bid = 1 - kalshi_away_ask if kalshi_away_ask is not None else None
           kalshi_ask = 1 - kalshi_away_bid if kalshi_away_bid is not None else None
       else:
           kalshi_price = None
           kalshi_bid = None
           kalshi_ask = None
       ```

- **Validation Steps**:
  1. **Test with home-only game**: `python -c "from scripts.simulate_trading_strategy import get_aligned_data; from scripts._db_lib import connect; conn = connect(); data, start, dur, outcome = get_aligned_data(conn, '401810277'); print(f'Home-only game aligned points: {len(data)}')"`
     - Expected Output: If game has home data, aligned points > 0, kalshi_price matches home mid
  2. **Test with away-only game**: Find game with `kalshi_home_mid_price IS NULL` and `kalshi_away_mid_price IS NOT NULL`, run same test
     - Expected Output: aligned points > 0 (previously would be 0), kalshi_price = 1 - away_mid
  3. **Verify bid/ask swap**: Check logs or add debug print: `print(f'bid={kalshi_bid}, ask={kalshi_ask}, away_bid={kalshi_away_bid}, away_ask={kalshi_away_ask}')`
     - Expected Output: When using away data, `kalshi_bid = 1 - kalshi_away_ask` and `kalshi_ask = 1 - kalshi_away_bid`

- **Definition of Done**:
  - [ ] Conditional logic implemented with home preference
  - [ ] Away→home conversion formula correct: `price = 1 - away_price`
  - [ ] Bid/ask swap correct: `bid = 1 - away_ask`, `ask = 1 - away_bid`
  - [ ] Previously skipped games (away-only) now have aligned_data > 0
  - [ ] Validation steps pass

- **Rollback Plan**: Revert to direct home assignment: `kalshi_price = kalshi_home_mid_price`
- **Risk Assessment**: Medium risk - logic must be correct or P&L will be inverted. Mitigation: Test with known games, verify conversion math.
- **Success Metrics**: Away-only games process successfully, conversion math verified correct

### Epic 2: Add Normalization and Range Safety
**Priority**: Critical (prevents incorrect P&L from scaled values)
**Estimated Time**: 2 hours (2 hours Phase 2)
**Dependencies**: Epic 1 completed
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Implement _norm01() Helper and Apply Normalization
- **ID**: S15-E2-S1
- **Type**: Bug Fix
- **Priority**: Critical (prevents divergence explosion from 0-100 scaled values)
- **Estimate**: 1 hour (30 min helper, 30 min application)
- **Phase**: Phase 2
- **Prerequisites**: S15-E1-S2 (must have conversion logic)
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`, add helper function, apply to fields)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `_norm01()` helper function exists inside `get_aligned_data()` (or module level)
  - [ ] `_norm01(None)` returns `None`
  - [ ] `_norm01(0.5)` returns `0.5` (already normalized)
  - [ ] `_norm01(50.0)` returns `0.5` (normalizes 0-100 to 0-1)
  - [ ] `_norm01()` applied to `espn_home_prob`, `kalshi_price`, `kalshi_bid`, `kalshi_ask` before use
  - [ ] Normalization happens after away→home conversion (if applicable)

- **Technical Context**:
  - **Current State**: No normalization exists. Values assumed to be 0-1 but canonical view may return 0-100.
  - **Required Changes**: Add helper function, apply to all probability/price fields before range checks and use.
  - **Integration Points**: Applied in row processing loop after field extraction/conversion
  - **Data Structures**: Input: float or None, Output: float (0-1) or None
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. **Add _norm01() helper function**: Inside `get_aligned_data()` function (before row processing loop)
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Add function definition around line 203
     - Content:
       ```python
       def _norm01(x):
           """Normalize value to 0-1 range. Handles None, 0-1, and 0-100 formats."""
           if x is None:
               return None
           x = float(x)
           # Guard: if canonical view accidentally returns 0-100, normalize
           if x > 1.0:
               x = x / 100.0
           return x
       ```
  2. **Apply normalization to espn_home_prob**: After extraction, before use
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify after line 216
     - Content: `espn_home_prob = _norm01(row[1])`
  3. **Apply normalization to Kalshi fields**: After away→home conversion
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify after conversion logic
     - Content: `kalshi_price = _norm01(kalshi_price)`, `kalshi_bid = _norm01(kalshi_bid)`, `kalshi_ask = _norm01(kalshi_ask)`

- **Validation Steps**:
  1. **Test helper function**: `python -c "def _norm01(x): return None if x is None else (float(x) / 100.0 if float(x) > 1.0 else float(x)); print(_norm01(50.0), _norm01(0.5), _norm01(None))"`
     - Expected Output: `0.5 0.5 None`
  2. **Test with game data**: Run `get_aligned_data()` on game with known values, check logs for normalization warnings (if values > 1.0 detected)
     - Expected Output: All values in aligned_data are in [0,1] range

- **Definition of Done**:
  - [ ] `_norm01()` helper function implemented
  - [ ] Applied to all probability/price fields (espn_home_prob, kalshi_price, kalshi_bid, kalshi_ask)
  - [ ] Helper function tests pass
  - [ ] No values > 1.0 in aligned_data (after normalization)

- **Rollback Plan**: Remove `_norm01()` calls, revert to direct field assignment
- **Risk Assessment**: Low risk - defensive normalization, no data loss
- **Success Metrics**: All values normalized to [0,1], no values > 1.0 in output

#### Story 2.2: Add Strict Range Checks [0,1] with Warnings
- **ID**: S15-E2-S2
- **Type**: Bug Fix
- **Priority**: Critical (prevents invalid data from entering simulation)
- **Estimate**: 1 hour (30 min implementation, 30 min testing)
- **Phase**: Phase 2
- **Prerequisites**: S15-E2-S1 (must have normalization)
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`, add range checks)
- **Files to Create**: None
- **Dependencies**: Normalization from Story 2.1

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] After normalization, if `espn_prob` or `kalshi_price` is None → skip point, increment `filtered_missing_espn` or `filtered_missing_kalshi`
  - [ ] After normalization, if `espn_prob` or `kalshi_price` outside [0,1] → log warning, skip point, increment `filtered_out_of_range`
  - [ ] If `kalshi_bid` or `kalshi_ask` outside [0,1] → set to None (don't fail the point), log warning
  - [ ] Range checks happen after normalization, before adding to aligned_data

- **Technical Context**:
  - **Current State**: Only None checks exist. No range validation.
  - **Required Changes**: Add [0,1] range checks with warnings, update counters, handle bid/ask gracefully (set to None if out of range).
  - **Integration Points**: Applied after normalization, before `aligned_data.append()`
  - **Data Structures**: Values are floats in [0,1] or None
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. **Add filtered_out_of_range counter**: Initialize with other counters
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify line 206
     - Content: Add `filtered_out_of_range = 0`
  2. **Add range check for espn_prob**: After normalization, before None check
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify after normalization
     - Content:
       ```python
       if espn_home_prob is None:
           filtered_missing_espn += 1
           continue
       if espn_home_prob < 0.0 or espn_home_prob > 1.0:
           logger.warning(f"[ALIGN_DATA] Game {game_id}: ESPN prob out of range: {espn_home_prob}, skipping point")
           filtered_out_of_range += 1
           continue
       ```
  3. **Add range check for kalshi_price**: After normalization
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify after kalshi_price normalization
     - Content:
       ```python
       if kalshi_price is None:
           filtered_missing_kalshi += 1
           continue
       if kalshi_price < 0.0 or kalshi_price > 1.0:
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi price out of range: {kalshi_price}, skipping point")
           filtered_out_of_range += 1
           continue
       ```
  4. **Add range check for bid/ask (set to None if out of range)**: After normalization
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify after bid/ask normalization
     - Content:
       ```python
       if kalshi_bid is not None and (kalshi_bid < 0.0 or kalshi_bid > 1.0):
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi bid out of range: {kalshi_bid}, setting to None")
           kalshi_bid = None
       if kalshi_ask is not None and (kalshi_ask < 0.0 or kalshi_ask > 1.0):
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Kalshi ask out of range: {kalshi_ask}, setting to None")
           kalshi_ask = None
       ```

- **Validation Steps**:
  1. **Test with valid data**: Run on game with known good data
     - Expected Output: No warnings, aligned_data populated
  2. **Test with out-of-range data**: If possible, inject test data with values > 1.0
     - Expected Output: Warnings logged, points skipped, filtered_out_of_range incremented
  3. **Verify counters**: Check final log output includes filtered_out_of_range count
     - Expected Output: Log shows all counter values

- **Definition of Done**:
  - [ ] Range checks implemented for espn_prob and kalshi_price (skip if out of range)
  - [ ] Range checks implemented for bid/ask (set to None if out of range)
  - [ ] Warnings logged for out-of-range values
  - [ ] Counters incremented correctly
  - [ ] Validation steps pass

- **Rollback Plan**: Remove range checks, revert to None-only checks
- **Risk Assessment**: Low risk - defensive checks, no data modification
- **Success Metrics**: Out-of-range values detected and handled, no invalid data in aligned_data

### Epic 3: Improve Debug Counters and Logging
**Priority**: High (enables quick diagnosis of data issues)
**Estimated Time**: 1 hour (1 hour Phase 3)
**Dependencies**: Epic 2 completed
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Add Detailed Debug Counters and Summary Logging
- **ID**: S15-E3-S1
- **Type**: Enhancement
- **Priority**: High (diagnostic value)
- **Estimate**: 1 hour (30 min counters, 30 min logging)
- **Phase**: Phase 3
- **Prerequisites**: S15-E2-S2 (must have range checks with counters)
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`, logging section)
- **Files to Create**: None
- **Dependencies**: Counters from Story 2.2

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Counter `filtered_missing_espn` exists and increments when espn_prob is None
  - [ ] Counter `filtered_missing_kalshi` exists and increments when kalshi_price is None (after home/away selection)
  - [ ] Counter `filtered_out_of_range` exists and increments when values outside [0,1]
  - [ ] Counter `filtered_by_time_window` exists (already exists, verify)
  - [ ] Final log includes: total canonical_rows, percent with home mid present, percent with away mid present
  - [ ] If aligned_data is empty, log warning with all counter values

- **Technical Context**:
  - **Current State**: Only `filtered_by_time_window` and `filtered_by_kalshi` counters exist. Logging is minimal.
  - **Required Changes**: Add explicit counters, calculate percentages, add summary warning if empty.
  - **Integration Points**: Used in final logging section (around line 277)
  - **Data Structures**: Counters are integers
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. **Initialize all counters**: At start of row processing loop
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify line 205-206
     - Content:
       ```python
       filtered_by_time_window = 0
       filtered_missing_espn = 0
       filtered_missing_kalshi = 0
       filtered_out_of_range = 0
       ```
  2. **Count home/away presence**: Track rows with home mid vs away mid
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Add counters before loop
     - Content:
       ```python
       rows_with_home_mid = 0
       rows_with_away_mid = 0
       ```
  3. **Increment counters in loop**: When home/away mid detected
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Add in loop after field extraction
     - Content:
       ```python
       if kalshi_home_mid_price is not None:
           rows_with_home_mid += 1
       if kalshi_away_mid_price is not None:
           rows_with_away_mid += 1
       ```
  4. **Update final logging**: Add summary with percentages and all counters
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify lines 277-281
     - Content:
       ```python
       logger.debug(f"[ALIGN_DATA] Game {game_id}: Processed {len(aligned_data)} aligned data points")
       logger.debug(f"[ALIGN_DATA] Game {game_id}: Filtered out - {filtered_by_time_window} by time window, {filtered_missing_espn} missing ESPN, {filtered_missing_kalshi} missing Kalshi, {filtered_out_of_range} out of range")
       
       if not aligned_data:
           pct_home = (rows_with_home_mid / len(canonical_rows) * 100) if canonical_rows else 0.0
           pct_away = (rows_with_away_mid / len(canonical_rows) * 100) if canonical_rows else 0.0
           logger.warning(f"[ALIGN_DATA] Game {game_id}: ❌ No aligned data found after processing")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Canonical dataset rows: {len(canonical_rows)}")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Rows with home mid: {rows_with_home_mid} ({pct_home:.1f}%)")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Rows with away mid: {rows_with_away_mid} ({pct_away:.1f}%)")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by time window: {filtered_by_time_window}")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by missing ESPN: {filtered_missing_espn}")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by missing Kalshi: {filtered_missing_kalshi}")
           logger.warning(f"[ALIGN_DATA] Game {game_id}: Filtered by out of range: {filtered_out_of_range}")
       ```

- **Validation Steps**:
  1. **Test with game that has data**: Run on game with aligned data
     - Expected Output: Log shows aligned points > 0, counters show breakdown
  2. **Test with skipped game**: Run on previously skipped game (e.g., '401810277')
     - Expected Output: If still empty, log shows percentages and all counter values, helps diagnose issue
  3. **Verify percentages**: Check math: `pct_home = (rows_with_home_mid / len(canonical_rows) * 100)`
     - Expected Output: Percentages between 0-100, sum may be > 100 (rows can have both)

- **Definition of Done**:
  - [ ] All counters initialized and incremented correctly
  - [ ] Home/away presence tracked
  - [ ] Summary logging includes percentages and all counters
  - [ ] Empty aligned_data warning includes diagnostic info
  - [ ] Validation steps pass

- **Rollback Plan**: Revert to original logging, remove new counters
- **Risk Assessment**: Low risk - logging only, no functional changes
- **Success Metrics**: Diagnostic info helps identify data issues quickly

### Epic 4: Add Runtime Guards in simulate_trading_strategy()
**Priority**: High (prevents bad data from entering trades)
**Estimated Time**: 1 hour (1 hour Phase 4)
**Dependencies**: Epic 3 completed
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Add Range Checks Before Divergence Calculations
- **ID**: S15-E4-S1
- **Type**: Bug Fix
- **Priority**: High (prevents incorrect P&L from bad-scaled data)
- **Estimate**: 1 hour (30 min implementation, 30 min testing)
- **Phase**: Phase 4
- **Prerequisites**: S15-E3-S1 (must have improved logging)
- **Files to Modify**: `scripts/simulate_trading_strategy.py` (function `simulate_trading_strategy()`, add guards before divergence)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Before calculating divergence, check if `espn_prob` or `kalshi_price` not in [0,1]
  - [ ] If out of range, log warning and `continue` (skip point)
  - [ ] If `kalshi_bid` or `kalshi_ask` not in [0,1], set to None (don't fail the point)
  - [ ] Guards happen before divergence calculation (around line 586-587)

- **Technical Context**:
  - **Current State**: No runtime guards. Divergence calculated directly from aligned_data values.
  - **Required Changes**: Add range checks in `simulate_trading_strategy()` loop before divergence calculation.
  - **Integration Points**: Applied in main simulation loop (around line 566-590)
  - **Data Structures**: Values should be floats in [0,1] or None
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. **Add range check for espn_prob and kalshi_price**: Before divergence calculation
     - File: `scripts/simulate_trading_strategy.py`
     - Action: Modify around line 574-577 (after extracting values, before divergence)
     - Content:
       ```python
       # Defensive check: skip if required data is missing (shouldn't happen after filtering, but be safe)
       if espn_prob is None or kalshi_price is None or timestamp is None:
           logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: missing required data (espn_prob={espn_prob}, kalshi_price={kalshi_price}, timestamp={timestamp})")
           continue
       
       # Ensure values are floats (defensive check)
       try:
           espn_prob = float(espn_prob)
           kalshi_price = float(kalshi_price)
       except (TypeError, ValueError) as e:
           logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: invalid data types (espn_prob={espn_prob}, kalshi_price={kalshi_price}): {e}")
           continue
       
       # Runtime guard: ensure values are in [0,1] range
       if espn_prob < 0.0 or espn_prob > 1.0:
           logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: ESPN prob out of range: {espn_prob}")
           continue
       if kalshi_price < 0.0 or kalshi_price > 1.0:
           logger.warning(f"[SIMULATION] Skipping point {point_idx+1}: Kalshi price out of range: {kalshi_price}")
           continue
       
       # Set bid/ask to None if out of range (don't fail the point)
       if kalshi_bid is not None and (kalshi_bid < 0.0 or kalshi_bid > 1.0):
           logger.warning(f"[SIMULATION] Point {point_idx+1}: Kalshi bid out of range: {kalshi_bid}, setting to None")
           kalshi_bid = None
       if kalshi_ask is not None and (kalshi_ask < 0.0 or kalshi_ask > 1.0):
           logger.warning(f"[SIMULATION] Point {point_idx+1}: Kalshi ask out of range: {kalshi_ask}, setting to None")
           kalshi_ask = None
       ```

- **Validation Steps**:
  1. **Test with valid data**: Run simulation on game with known good data
     - Expected Output: No warnings, simulation completes normally
  2. **Test with out-of-range data**: If possible, inject test data
     - Expected Output: Warnings logged, points skipped, simulation continues
  3. **Verify no trades on bad data**: Check that no trades are entered with invalid prices
     - Expected Output: No trades with entry/exit prices outside [0,1]

- **Definition of Done**:
  - [ ] Range checks implemented before divergence calculation
  - [ ] Warnings logged for out-of-range values
  - [ ] Points skipped if espn_prob or kalshi_price out of range
  - [ ] Bid/ask set to None if out of range (point not skipped)
  - [ ] Validation steps pass

- **Rollback Plan**: Remove range checks, revert to direct divergence calculation
- **Risk Assessment**: Low risk - defensive checks, no data modification
- **Success Metrics**: No invalid data enters trades, warnings help diagnose issues

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story 5.1: Documentation Update
- **ID**: S15-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed (S15-E1-S1, S15-E1-S2, S15-E2-S1, S15-E2-S2, S15-E3-S1, S15-E4-S1)

- **Acceptance Criteria**:
  - [ ] **Function docstring updated**: `get_aligned_data()` docstring documents away→home conversion and normalization
  - [ ] **Inline comments added**: Explain away→home conversion logic and bid/ask swap
  - [ ] **Canonical view documentation**: Add note near `canonical_sql` documenting expected column units (0-1) and why `_norm01()` exists
  - [ ] **README updated**: If `webapp/README.md` or `scripts/README.md` mention simulation, update with normalization info

- **Technical Context**:
  - **Current State**: Docstrings may not mention away→home conversion or normalization
  - **Required Changes**: Update docstrings and add inline comments explaining new logic
  - **Integration Points**: Documentation helps future developers understand the logic

- **Implementation Steps**:
  1. **Update get_aligned_data() docstring**: Add notes about away→home conversion and normalization
  2. **Add inline comments**: Explain conversion logic and bid/ask swap
  3. **Add canonical_sql comment**: Document expected units and normalization purpose

- **Validation Steps**:
  1. **Verify docstring**: Read function docstring, confirm it mentions conversion and normalization
  2. **Verify comments**: Check code has explanatory comments

- **Definition of Done**:
  - [ ] All documentation updated
  - [ ] Comments explain complex logic
  - [ ] Docstrings accurate

- **Rollback Plan**: Revert docstring changes
- **Risk Assessment**: None - documentation only
- **Success Metrics**: Documentation is complete and accurate

### Story 5.2: Quality Gate Validation
- **ID**: S15-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (MUST be 100% pass):
  - [ ] **Linting**: All linting checks pass with zero errors and zero warnings
  - [ ] **Type Checking**: All type checking passes with zero errors (if applicable)
  - [ ] **Functionality**: Previously skipped games now have aligned_data > 0
  - [ ] **Functionality**: P&L values are within expected ranges (not wildly off)
  - [ ] **Functionality**: Range checks prevent invalid data from entering simulation
  - [ ] **All acceptance criteria from previous stories verified as complete**

- **Technical Context**:
  - **Current State**: Code changes complete, needs validation
  - **Required Changes**: Run quality checks, test with previously skipped games, verify P&L accuracy
  - **Quality Gates**: Linting, manual testing with known games

- **Implementation Steps**:
  1. **Run linting**: `python -m pylint scripts/simulate_trading_strategy.py` (or appropriate linter)
  2. **Test with skipped game**: Run simulation on game '401810277' (or other previously skipped)
     - Command: `python -c "from scripts.simulate_trading_strategy import get_aligned_data; from scripts._db_lib import connect; conn = connect(); data, start, dur, outcome = get_aligned_data(conn, '401810277'); print(f'Aligned points: {len(data)}')"`
     - Expected: aligned_points > 0
  3. **Test with game that had "wildly off" P&L**: Run simulation, verify P&L is reasonable
     - Expected: No warnings about out-of-range values, P&L within expected range
  4. **Verify range checks**: Check logs for any out-of-range warnings
     - Expected: Warnings logged if invalid data detected, simulation continues

- **Validation Steps**:
  1. **Linting passes**: Zero errors, zero warnings
  2. **Skipped game processes**: Previously skipped game now has aligned_data > 0
  3. **P&L reasonable**: No wildly incorrect profit values
  4. **Range checks work**: Invalid data detected and handled

- **Definition of Done**:
  - [ ] All quality gates pass
  - [ ] Previously skipped games process successfully
  - [ ] P&L values are accurate
  - [ ] All acceptance criteria verified

- **Rollback Plan**: Revert all changes if quality gates fail
- **Risk Assessment**: Low risk - validation catches issues before deployment
- **Success Metrics**: 100% quality gate pass rate, all functionality verified

### Story 5.3: Sprint Completion and Archive
- **ID**: S15-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion summary created
  - [ ] All sprint files organized in sprint directory
  - [ ] Quick sanity check commands documented with results
  - [ ] Sprint marked as completed

- **Technical Context**:
  - **Current State**: All work complete, needs final organization
  - **Required Changes**: Create summary, document validation results

- **Implementation Steps**:
  1. **Create completion summary**: Document what was fixed, test results
  2. **Document sanity checks**: Include commands and results for previously skipped games
  3. **Organize files**: Ensure all sprint files are in correct directory

- **Validation Steps**:
  1. **Verify summary exists**: Check for completion summary document
  2. **Verify sanity checks documented**: Commands and results included

- **Definition of Done**:
  - [ ] Completion summary created
  - [ ] Sanity checks documented
  - [ ] Sprint organized and complete

- **Rollback Plan**: N/A (completion only)
- **Risk Assessment**: None
- **Success Metrics**: Sprint properly documented and organized

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: Defensive Programming Pattern
- **Category**: Behavioral
- **Intent**: Add multiple layers of validation to prevent invalid data from causing incorrect calculations
- **Implementation**: Normalization helper `_norm01()`, range checks in `get_aligned_data()`, runtime guards in `simulate_trading_strategy()`
- **Benefits**: Prevents incorrect P&L from bad-scaled data, enables processing games with only away market data, provides diagnostic information
- **Trade-offs**: Slight performance overhead from additional checks, but correctness is more important than micro-optimizations
- **Rationale**: Correctness regression must be fixed. Multiple validation layers ensure data quality at each stage.

### Algorithm Analysis

### Algorithm: Away→Home Probability Space Conversion
- **Type**: Data Transformation
- **Complexity**: Time O(1) per row, Space O(1)
- **Description**: Converts away market probability to home market probability space: `home_prob = 1 - away_prob`. For bid/ask: `home_bid = 1 - away_ask`, `home_ask = 1 - away_bid` (swap required because bid/ask are inverted in opposite market).
- **Use Case**: Enables processing games where canonical view only has away market data
- **Performance**: Negligible overhead - simple arithmetic operations

### Design Decision Analysis

### Design Decision: Normalization vs. Assumption
- **Problem**: Canonical view may return values in 0-100 format instead of 0-1, causing divergence calculations to explode
- **Context**: Need to handle both formats defensively without breaking existing correct data
- **Project Scope**: Single function fix, no architectural changes
- **Options**: 
  1. Assume canonical view always returns 0-1 (current broken state)
  2. Add normalization helper that detects and converts 0-100 to 0-1
  3. Fix canonical view to always return 0-1 (out of scope)

**Option 2: Add Normalization Helper (CHOSEN)**
- **Design Pattern**: Defensive Programming Pattern
- **Algorithm**: Simple conditional normalization: `if x > 1.0: x = x / 100.0`
- **Implementation Complexity**: Low (1 hour)
- **Maintenance Overhead**: Low (simple helper function)
- **Scalability**: Excellent (handles both formats)
- **Cost-Benefit**: Low cost, High benefit (prevents incorrect P&L)
- **Over-Engineering Risk**: None (minimal code, high value)
- **Selected**: Provides defense-in-depth without requiring canonical view changes

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 1 hour (simple helper function)
- **Learning Curve**: 0 hours (straightforward logic)
- **Configuration Effort**: 0 hours (no configuration)

**Maintenance Cost**:
- **Monitoring**: 0 hours (no monitoring needed)
- **Updates**: 0 hours (stable logic)
- **Debugging**: Low (simple conditional)

**Performance Benefit**:
- **Correctness**: 100% (prevents incorrect P&L from scaled values)
- **Data Coverage**: Enables processing games with away-only data

**Maintainability Benefit**:
- **Code Quality**: Improved (defensive checks)
- **Developer Productivity**: Improved (clear error messages)
- **System Reliability**: Improved (handles edge cases)

**Risk Cost**:
- **Risk 1**: Low risk - normalization is idempotent (0.5 stays 0.5, 50.0 becomes 0.5)
- **Risk 2**: Low risk - if canonical view is correct, normalization has no effect

**Over-Engineering Prevention**:
- **Problem Complexity**: Low (simple format conversion)
- **Solution Complexity**: Low (simple helper function)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Handles both current formats and potential future formats

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ (minimal change, high value)
- **Team Capability**: ✅ (straightforward implementation)
- **Timeline Constraints**: ✅ (quick to implement)
- **Future Growth**: ✅ (handles multiple formats)
- **Technical Debt**: ✅ (reduces debt by fixing regression)

**Chosen Solution**: Add `_norm01()` helper function that normalizes values > 1.0 to 0-1 range. Apply to all probability/price fields before use. This provides defense-in-depth without requiring canonical view changes.

**Pros and Cons Analysis**:

**Pros**:
- **Correctness**: Prevents incorrect P&L from 0-100 scaled values
- **Maintainability**: Simple, clear logic
- **Scalability**: Handles both formats
- **Reliability**: Defensive programming reduces failure modes

**Cons**:
- **Performance**: Minimal overhead (negligible for correctness benefit)
- **Complexity**: Slight increase (worth it for correctness)

**Risk Assessment**: Low risk - normalization is safe and idempotent
**Trade-off Analysis**: Minimal performance cost for significant correctness benefit - net positive

## Testing Strategy

### Testing Approach
- **Unit Tests**: Manual testing with known games (no automated test suite exists)
- **Integration Tests**: Test `get_aligned_data()` with real database queries
- **E2E Tests**: Run full simulation on previously skipped games, verify P&L accuracy
- **Performance Tests**: N/A (correctness focus, performance already optimized)

## Deployment Plan
- **Pre-Deployment**: Verify database connection, test with sample games
- **Deployment Steps**: Code changes are in Python scripts, no deployment needed (code execution)
- **Post-Deployment**: Run sanity checks on previously skipped games, verify P&L accuracy
- **Rollback Plan**: Revert code changes if issues detected

## Risk Assessment
- **Technical Risks**: 
  - **Risk**: Away→home conversion logic incorrect → Mitigation: Test with known games, verify math
  - **Risk**: Normalization breaks correct 0-1 data → Mitigation: Normalization is idempotent (0.5 stays 0.5)
  - **Risk**: Range checks too strict → Mitigation: Log warnings, allow graceful degradation
- **Business Risks**: 
  - **Risk**: Previously skipped games still fail → Mitigation: Detailed logging helps diagnose
  - **Risk**: P&L still incorrect → Mitigation: Multiple validation layers, runtime guards
- **Resource Risks**: 
  - **Risk**: Time estimate too low → Mitigation: Focus on critical fixes first, defer enhancements

## Success Metrics
- **Technical**: 
  - Previously skipped games now have aligned_data > 0 (target: 100% of test games)
  - P&L values within expected ranges (target: no "wildly off" values)
  - Range checks prevent invalid data (target: warnings logged for invalid data)
- **Business**: 
  - Trading simulation accuracy improved (target: P&L matches expected ranges)
  - No games incorrectly skipped (target: all games with data process successfully)
- **Sprint**: 
  - All stories completed (target: 100%)
  - Quality gates pass (target: 100%)
  - Documentation updated (target: 100%)

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing (manual validation)
- [ ] All documentation updated
- [ ] All quality gates pass (linting, functionality verification)

### Post-Sprint Quality Comparison
- **Test Results**: Manual validation with previously skipped games passes
- **Linting Results**: Zero errors, zero warnings
- **Code Coverage**: N/A (no automated tests)
- **Build Status**: Python scripts execute successfully
- **Overall Assessment**: Correctness regression fixed, defensive programming added

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion summary created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

## Quick Sanity Checks (Include Commands in Output)

After implementation, run these commands to validate the fix:

```bash
# Test with previously skipped game
source .env
python -c "
from scripts.simulate_trading_strategy import get_aligned_data
from scripts._db_lib import connect
conn = connect()
data, start, dur, outcome = get_aligned_data(conn, '401810277')
print(f'Aligned points: {len(data)}')
print(f'Expected: > 0 (previously was 0)')
"

# Test with game that had "wildly off" P&L
python -c "
from scripts.simulate_trading_strategy import get_aligned_data
from scripts._db_lib import connect
conn = connect()
# Use a game ID that had incorrect P&L
data, start, dur, outcome = get_aligned_data(conn, '401810250')
if data:
    print(f'Sample ESPN prob: {data[0][\"espn_prob\"]}')
    print(f'Sample Kalshi price: {data[0][\"kalshi_price\"]}')
    print(f'Both should be in [0,1] range')
    print(f'ESPN in range: {0 <= data[0][\"espn_prob\"] <= 1}')
    print(f'Kalshi in range: {0 <= data[0][\"kalshi_price\"] <= 1}')
"

# Verify canonical view has both home and away fields
psql "$DATABASE_URL" -c "
SELECT 
    COUNT(*) as total_rows,
    COUNT(kalshi_home_mid_price) as rows_with_home,
    COUNT(kalshi_away_mid_price) as rows_with_away
FROM derived.snapshot_features_v1
WHERE game_id = '401810277' AND season_label = '2025-26'
"
```

**Expected Results**:
- Previously skipped game now has aligned_points > 0
- All probability/price values in [0,1] range
- Canonical view has both home and away data available

