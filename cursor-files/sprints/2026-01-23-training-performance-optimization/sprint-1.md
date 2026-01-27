# Sprint: Training Performance Optimization

**Date**: Fri Jan 23 10:30:39 PST 2026  
**Sprint Duration**: 1 day (6-8 hours)  
**Sprint Goal**: Reduce CatBoost training script execution time by 50%+ through SQL query optimization, Python vectorization, and eliminating redundant computations  
**Current Status**: Training takes ~70+ seconds for SQL query, builds design matrix 3x separately, uses O(n·k) debug loops  
**Target Status**: SQL query under 30 seconds, design matrix built once, vectorized possession encoding  
**Team Size**: 1 developer  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence
- **File Verification**: Verify file contents directly before making claims
- **No Database Modifications**: Read-only unless explicitly required

## Sprint Overview

### Business Context
- **Business Driver**: Model retraining iteration time is too slow (~3+ minutes), slowing down experimentation and development velocity
- **Success Criteria**: Total training time reduced by 50%+ (SQL + Python overhead)
- **Stakeholders**: ML engineering team
- **Timeline Constraints**: None (quality over speed)

### Technical Context
- **Current System State**: 
  - SQL query scans full `opening_odds` and `scoreboard_final` tables (~68s execution)
  - Design matrix built 3 times (train, calib, test) with repeated possession encoding, scaling
  - Debug loops use O(n·k) DataFrame scans for season counts
  - Possession encoding uses Python loop with `vstack`
- **Target System State**:
  - SQL CTEs scoped to only needed games (reduced scan size)
  - Design matrix built once, sliced by masks
  - Debug loops use single-pass `value_counts()`
  - Vectorized possession encoding with numpy broadcasting
- **Architecture Impact**: No changes to model output or data semantics
- **Integration Points**: `train_winprob_catboost.py`, `_winprob_lib.py`

### Sprint Scope
- **In Scope**: SQL optimization, Python vectorization, redundant computation elimination
- **Out of Scope**: CatBoost hyperparameter tuning, GPU acceleration, schema changes
- **Assumptions**: Results must be bit-for-bit identical (no model output changes)
- **Constraints**: Cannot add new database indexes (separate operation)

## Sprint Phases

### Phase 1: SQL Query Optimization (Duration: 2 hours)
**Objective**: Reduce SQL query execution time by scoping CTEs to only needed games
**Dependencies**: None
**Deliverables**: Optimized SQL query in `train_winprob_catboost.py`

### Phase 2: Python Vectorization (Duration: 2 hours)
**Objective**: Eliminate Python loops and repeated DataFrame operations
**Dependencies**: Phase 1 complete
**Deliverables**: Vectorized possession encoding, single-pass debug loops

### Phase 3: Build Design Matrix Once (Duration: 2 hours)
**Objective**: Build X_all once and slice by masks instead of 3 separate builds
**Dependencies**: Phase 2 complete
**Deliverables**: Refactored matrix building code, baseline computation once

### Phase 4: Sprint Quality Assurance (Duration: 1-2 hours)
**Objective**: Validate all changes, run tests, verify identical outputs
**Dependencies**: Phase 3 complete
**Deliverables**: Validated optimizations, documented performance gains

---

## Sprint Backlog

### Epic 1: SQL Query Optimization
**Priority**: High (biggest time savings)
**Estimated Time**: 2 hours
**Dependencies**: `scripts/model/train_winprob_catboost.py` lines 140-370
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Convert LEFT JOIN to INNER JOIN
- **ID**: S1-E1-S1
- **Type**: Performance Optimization
- **Priority**: Medium
- **Estimate**: 15 minutes
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `LEFT JOIN espn.prob_event_state` changed to `JOIN espn.prob_event_state`
  - [ ] Query returns identical row count
  - [ ] Query executes successfully

- **Technical Context**:
  - **Current State** (lines 162-167):
    ```sql
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
    ```
  - **Required Changes**:
    ```sql
    FROM espn.probabilities_raw_items p
    JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
    ```
  - **Rationale**: The `WHERE e.* IS NOT NULL` clause makes LEFT JOIN behave like INNER JOIN anyway. Explicit INNER JOIN is faster.

- **Implementation Steps**:
  1. Replace `LEFT JOIN espn.prob_event_state` with `JOIN espn.prob_event_state` in both query variants (interaction and no-interaction)

- **Validation Steps**:
  1. Run training script with `--cache-parquet` to verify query executes
  2. Verify row count matches previous runs

#### Story 1.2: Scope opening_odds CTE to Needed Games Only
- **ID**: S1-E1-S2
- **Type**: Performance Optimization
- **Priority**: High (major speedup)
- **Estimate**: 30 minutes
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `opening_odds` CTE joins to `espn_base_filtered` game_ids
  - [ ] Query returns identical data
  - [ ] Query execution time reduced

- **Technical Context**:
  - **Current State** (lines 191-203):
    ```sql
    opening_odds AS MATERIALIZED (
        SELECT 
            espn_game_id,
            MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'home') AS opening_moneyline_home,
            ...
        FROM external.sportsbook_odds_snapshots
        WHERE is_opening_line = TRUE
            AND espn_game_id IS NOT NULL
        GROUP BY espn_game_id
    )
    ```
  - **Required Changes**:
    ```sql
    opening_odds AS MATERIALIZED (
        SELECT 
            s.espn_game_id,
            MAX(s.odds_decimal) FILTER (WHERE s.market_type = 'moneyline' AND s.side = 'home') AS opening_moneyline_home,
            ...
        FROM external.sportsbook_odds_snapshots s
        JOIN (SELECT DISTINCT game_id FROM espn_base_filtered) g
            ON g.game_id = s.espn_game_id
        WHERE s.is_opening_line = TRUE
        GROUP BY s.espn_game_id
    )
    ```
  - **Rationale**: Only aggregate odds for games that appear in filtered ESPN slice, not entire table.

- **Implementation Steps**:
  1. Add subquery join to `opening_odds` CTE
  2. Update both query variants (interaction and no-interaction)

- **Validation Steps**:
  1. Run `EXPLAIN ANALYZE` to verify reduced scan size
  2. Verify data matches previous output

#### Story 1.3: Scope scoreboard_final CTE to Needed Games Only
- **ID**: S1-E1-S3
- **Type**: Performance Optimization
- **Priority**: High
- **Estimate**: 30 minutes
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S2
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `scoreboard_final` CTE joins to `espn_base_filtered` game_ids
  - [ ] Query returns identical data
  - [ ] Query execution time reduced

- **Technical Context**:
  - **Current State** (lines 182-190):
    ```sql
    scoreboard_final AS MATERIALIZED (
        SELECT DISTINCT ON (event_id)
            event_id,
            home_score,
            away_score
        FROM espn.scoreboard_games
        WHERE status_completed = TRUE
        ORDER BY event_id, scoreboard_date DESC
    )
    ```
  - **Required Changes**:
    ```sql
    scoreboard_final AS MATERIALIZED (
        SELECT DISTINCT ON (sg.event_id)
            sg.event_id,
            sg.home_score,
            sg.away_score
        FROM espn.scoreboard_games sg
        JOIN (SELECT DISTINCT game_id FROM espn_base_filtered) g
            ON g.game_id = sg.event_id
        WHERE sg.status_completed = TRUE
        ORDER BY sg.event_id, sg.scoreboard_date DESC
    )
    ```

- **Implementation Steps**:
  1. Add subquery join to `scoreboard_final` CTE
  2. Update both query variants

- **Validation Steps**:
  1. Verify data matches previous output
  2. Verify query execution time reduced

---

### Epic 2: Python Debug Loop Optimization
**Priority**: Medium
**Estimated Time**: 30 minutes
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Replace O(n·k) Season Count Loops with value_counts()
- **ID**: S1-E2-S1
- **Type**: Performance Optimization
- **Priority**: Medium
- **Estimate**: 30 minutes
- **Phase**: Phase 2
- **Prerequisites**: None
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] Both "BEFORE" and "AFTER" debug loops use `value_counts()`
  - [ ] Same output format preserved
  - [ ] Single DataFrame pass instead of one per season

- **Technical Context**:
  - **Current State** (lines 566-570, 596-600):
    ```python
    for season in available_seasons:
        season_count = len(df[df["season_start"] == season])
        print(f"  Season {season}: {season_count} rows", file=sys.stderr)
    ```
  - **Required Changes**:
    ```python
    counts = df["season_start"].value_counts(dropna=False).sort_index()
    for season, cnt in counts.items():
        print(f"  Season {season}: {cnt} rows", file=sys.stderr)
    ```

- **Implementation Steps**:
  1. Replace both loop instances with `value_counts()` approach
  2. Preserve output format

- **Validation Steps**:
  1. Run script and verify identical debug output
  2. Confirm performance improvement for large datasets

---

### Epic 3: Vectorized Possession Encoding
**Priority**: High (major Python speedup)
**Estimated Time**: 1 hour
**Dependencies**: `scripts/lib/_winprob_lib.py` lines 455
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 3.1: Replace Python Loop with Numpy Broadcasting
- **ID**: S1-E3-S1
- **Type**: Performance Optimization
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: None
- **Files to Modify**: `scripts/lib/_winprob_lib.py`

- **Acceptance Criteria**:
  - [ ] `encode_possession` loop replaced with vectorized numpy code
  - [ ] Output shape and values identical
  - [ ] Performance improved for large arrays

- **Technical Context**:
  - **Current State** (line 455):
    ```python
    poss_rows = np.vstack([encode_possession(p) for p in possession])
    ```
  - **Required Changes**:
    ```python
    # Vectorized possession encoding (replaces slow Python loop)
    pos = np.asarray(list(possession), dtype="U")
    pos = np.char.strip(np.char.lower(pos))
    pos = np.where((pos == "home") | (pos == "away"), pos, "unknown")
    
    poss_rows = np.zeros((len(pos), 3), dtype=np.float64)
    poss_rows[:, 0] = (pos == "home")
    poss_rows[:, 1] = (pos == "away")
    poss_rows[:, 2] = (pos == "unknown")
    ```

- **Implementation Steps**:
  1. Add vectorized possession encoding after existing imports
  2. Replace loop with numpy broadcasting
  3. Keep `encode_possession()` function for single-value use cases

- **Validation Steps**:
  1. Create test case comparing old vs new output
  2. Verify identical output for edge cases (None, empty, mixed case)
  3. Time comparison for large arrays (1M+ rows)

---

### Epic 4: Build Design Matrix Once
**Priority**: High (eliminates repeated work)
**Estimated Time**: 2 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 4.1: Build X_all Once and Slice by Masks
- **ID**: S1-E4-S1
- **Type**: Refactor
- **Priority**: High
- **Estimate**: 1.5 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `build_design_matrix()` called once with full DataFrame
  - [ ] `X_train`, `X_calib`, `X_test` obtained via array slicing
  - [ ] Identical model output

- **Technical Context**:
  - **Current State**: Builds matrix 3 times (lines 750-794, 877-920, 1090-1130)
    ```python
    # Train matrix
    build_matrix_kwargs = {...}
    X_train = build_design_matrix(**build_matrix_kwargs)
    
    # Calib matrix (repeated construction)
    calib_matrix_kwargs = {...}
    X_calib = build_design_matrix(**calib_matrix_kwargs)
    
    # Test matrix (if needed, repeated again)
    test_matrix_kwargs = {...}
    X_test = build_design_matrix(**test_matrix_kwargs)
    ```
  - **Required Changes**:
    ```python
    # Build once with full data
    all_matrix_kwargs = {
        "point_differential": df["point_differential"].to_numpy(),
        "time_remaining_regulation": df["time_remaining_regulation"].to_numpy(),
        "possession": df["possession"].to_numpy(),  # pass array, not list
        "preprocess": preprocess,
        ...
    }
    X_all = build_design_matrix(**all_matrix_kwargs)
    
    # Slice by masks
    X_train = X_all[train_mask]
    X_calib = X_all[calib_mask]
    X_test = X_all[test_mask]
    ```

- **Implementation Steps**:
  1. Move matrix construction to single location after preprocess computation
  2. Pass full DataFrame columns (not masked)
  3. Slice X_all by masks for train/calib/test
  4. Remove duplicate build_matrix_kwargs construction

- **Validation Steps**:
  1. Compare X_train shape and first/last rows before/after
  2. Run full training and compare model metrics
  3. Verify calibration produces identical results

#### Story 4.2: Compute Baseline Array Once
- **ID**: S1-E4-S2
- **Type**: Refactor
- **Priority**: Medium
- **Estimate**: 30 minutes
- **Phase**: Phase 3
- **Prerequisites**: S1-E4-S1
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `baseline_all` computed once from full DataFrame
  - [ ] `baseline_train`, `baseline_calib`, `baseline_test` obtained via slicing
  - [ ] Identical CatBoost baseline values

- **Technical Context**:
  - **Current State**: Baseline computed multiple times (lines 928-950)
    ```python
    baseline_train = np.zeros(train_rows, dtype=np.float64)
    if not args.disable_opening_odds and "opening_prob_home_fair" in df.columns:
        p0 = df.loc[train_mask, "opening_prob_home_fair"].to_numpy(dtype=np.float64)
        has_odds = df.loc[train_mask, "has_opening_moneyline"].to_numpy(dtype=np.float64) > 0.5
        baseline_train[has_odds] = logit(p0[has_odds])
    
    # Later, repeated for eval set
    baseline_eval = np.zeros(len(eval_set[1]), dtype=np.float64)
    ...
    ```
  - **Required Changes**:
    ```python
    # Compute once
    baseline_all = np.zeros(len(df), dtype=np.float64)
    if not args.disable_opening_odds and "opening_prob_home_fair" in df.columns:
        p0 = df["opening_prob_home_fair"].to_numpy(dtype=np.float64)
        has_odds = df["has_opening_moneyline"].to_numpy(dtype=np.float64) > 0.5
        baseline_all[has_odds] = logit(p0[has_odds])
    
    # Slice
    baseline_train = baseline_all[train_mask]
    baseline_calib = baseline_all[calib_mask]
    baseline_test = baseline_all[test_mask]
    ```

- **Implementation Steps**:
  1. Move baseline computation to single location
  2. Compute from full DataFrame
  3. Slice by masks
  4. Remove duplicate baseline computation code

- **Validation Steps**:
  1. Compare baseline_train values before/after
  2. Verify CatBoost training produces identical model

---

### Epic 5: Minor Optimizations
**Priority**: Low
**Estimated Time**: 30 minutes
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 5.1: Use Snappy Compression for Parquet Cache
- **ID**: S1-E5-S1
- **Type**: Performance Optimization
- **Priority**: Low
- **Estimate**: 10 minutes
- **Phase**: Phase 3
- **Prerequisites**: None
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] `to_parquet()` uses `compression="snappy"`
  - [ ] Cache read/write faster

- **Technical Context**:
  - **Current State**:
    ```python
    df.to_parquet(cache_path, index=False)
    ```
  - **Required Changes**:
    ```python
    df.to_parquet(cache_path, index=False, compression="snappy")
    ```

- **Implementation Steps**:
  1. Add `compression="snappy"` to `to_parquet()` call

- **Validation Steps**:
  1. Verify cache file created successfully
  2. Verify read performance

#### Story 5.2: Remove Repeated .tolist() and .astype() Conversions
- **ID**: S1-E5-S2
- **Type**: Performance Optimization
- **Priority**: Low
- **Estimate**: 20 minutes
- **Phase**: Phase 3
- **Prerequisites**: S1-E4-S1
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`

- **Acceptance Criteria**:
  - [ ] Column arrays extracted once at start
  - [ ] Reused throughout script
  - [ ] No repeated `.astype(float).to_numpy()` on same columns

- **Technical Context**:
  - **Current State**: Repeated conversions throughout
    ```python
    df.loc[train_mask, "point_differential"].to_numpy()
    df.loc[calib_mask, "point_differential"].astype(float).to_numpy()
    ...
    ```
  - **Required Changes**: Extract once and reuse
    ```python
    # Extract once after loading
    point_diff_all = df["point_differential"].to_numpy(dtype=np.float64)
    time_rem_all = df["time_remaining_regulation"].to_numpy(dtype=np.float64)
    possession_all = df["possession"].to_numpy()
    ...
    ```

- **Implementation Steps**:
  1. Extract column arrays once after DataFrame loading
  2. Replace repeated conversions with sliced arrays

- **Validation Steps**:
  1. Verify identical results
  2. Profile memory usage (should be similar or lower)

---

### Epic 6: Sprint Quality Assurance
**Priority**: Critical
**Estimated Time**: 1-2 hours
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 6.1: Documentation Update
- **ID**: S1-E6-S1
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 30 minutes
- **Phase**: Phase 4
- **Prerequisites**: All development stories completed

- **Acceptance Criteria**:
  - [ ] Docstrings updated for modified functions
  - [ ] Performance notes added to training script header
  - [ ] `model_comparison_and_grid_search_explained.md` updated if needed

#### Story 6.2: Quality Gate Validation
- **ID**: S1-E6-S2
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 30 minutes
- **Phase**: Phase 4
- **Prerequisites**: All development stories completed

- **Acceptance Criteria**:
  - [ ] Training script runs without errors
  - [ ] Model output identical (compare artifact JSON)
  - [ ] Linter passes with no new errors
  - [ ] Performance improvement measured and documented

- **Validation Steps**:
  1. Run full training with both old and new code
  2. Compare model artifacts (JSON diff)
  3. Measure and document time improvement

#### Story 6.3: Sprint Completion
- **ID**: S1-E6-S3
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 30 minutes
- **Phase**: Phase 4
- **Prerequisites**: S1-E6-S2

- **Acceptance Criteria**:
  - [ ] Performance results documented
  - [ ] Sprint marked complete

---

## Technical Decisions

### Design Decision: Build X_all Once vs Multiple Builds
- **Problem**: Repeated design matrix construction is slow
- **Options**:
  1. Keep separate builds (current)
  2. Build once, slice by masks (proposed)
  3. Cache X matrices to disk (overkill)
- **Selected**: Option 2 - Build once, slice by masks
- **Rationale**: Eliminates repeated scaling, encoding, and array operations. Memory increase is minimal (masks are views, not copies).

### Design Decision: Vectorized Possession Encoding
- **Problem**: Python loop over millions of rows is slow
- **Options**:
  1. Keep Python loop (current)
  2. Numpy broadcasting (proposed)
  3. Numba JIT compilation (overkill)
- **Selected**: Option 2 - Numpy broadcasting
- **Rationale**: Native numpy operations are 10-100x faster than Python loops. No additional dependencies.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Output changes | Low | High | Compare model artifacts before/after |
| Memory increase | Low | Low | X_all is contiguous, masks are views |
| SQL semantic change | Low | High | Test on subset first, compare row counts |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| SQL query time | ~68s | <30s | EXPLAIN ANALYZE / script timing |
| Design matrix builds | 3 | 1 | Code inspection |
| Possession encoding | O(n) Python | O(n) numpy | Profile timing |
| Debug loop complexity | O(n·k) | O(n) | Code inspection |

---

## Sprint Completion Checklist

- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed
- [ ] Linter passes
- [ ] Model output identical to baseline
- [ ] Performance improvement documented
- [ ] Documentation updated
