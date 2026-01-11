# Sprint 1: snapshot_features_trade_v1 Query Optimization

**Date**: Wed Jan  7 14:18:20 PST 2026  
**Updated**: Wed Jan  7 14:18:20 PST 2026 (removed EXPLAIN ANALYZE requirements - takes hours, replaced with EXPLAIN and timing validation)  
**Sprint Duration**: 3 days (8-10 hours total)  
**Sprint Goal**: Optimize materialized view `derived.snapshot_features_trade_v1` query execution time from 31.45 seconds to <15 seconds (52% improvement) by enabling HashAggregate with 2GB work_mem, eliminating redundant trade scans in `kalshi_window_info`, and validating query correctness  
**Current Status**: Materialized view query executes in 31.45 seconds with trade_agg_core CTE consuming 46.34 seconds (73% of total) using GroupAggregate on 3.1M groups. HashAggregate disabled due to memory concerns. kalshi_window_info redundantly scans 7.9M trades.  
**Target Status**: Materialized view query executes in <15 seconds with trade_agg_core completing in <20 seconds using HashAggregate (no disk spills), kalshi_window_info computed from trade_agg_core output (eliminating redundant scan), and query correctness validated  
**Team Size**: 1  
**Sprint Lead**: AI Assistant  

**IMPORTANT NOTE**: This sprint plan uses `EXPLAIN` (without ANALYZE) for execution plan validation instead of `EXPLAIN ANALYZE` because ANALYZE executes the full query and takes hours with 7.9M trades. Validation uses: (1) `EXPLAIN` to verify execution plan shows correct optimizations, (2) `time` command to measure actual materialized view creation, and (3) test queries on single game subset for fast correctness validation.  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline

- **Test Results**: No automated tests exist for materialized view creation. Manual validation via EXPLAIN ANALYZE and result comparison.
- **QC Results**: N/A (no QC checks for materialized views)
- **Code Coverage**: N/A (SQL migration files)
- **Build Status**: Migration file syntax valid, materialized view creates successfully

**Purpose**: This baseline ensures we maintain query correctness throughout optimization and provides historical reference for performance metrics.

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO modify database** - CREATE MATERIALIZED VIEW is part of sprint plan
- **DO NOT modify existing views** - only optimize the query
- **Query operations allowed** - EXPLAIN ANALYZE, SELECT statements for validation

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

**Git Usage Rules**:
- **NO git commands** unless explicitly mentioned in sprint plan
- **NO git operations** unless explicitly mentioned in analysis
- **NO version control** unless explicitly mentioned in prompt by prompter
- **NO commits, pushes, pulls, or branches** unless explicitly directed

**Exception**: Git usage is only allowed when explicitly mentioned in the prompt by the prompter that git can be used.

## Sprint Overview

### Business Context
- **Business Driver**: Materialized view refresh takes 31.45 seconds, limiting refresh frequency and increasing data staleness risk. Users need faster access to updated simulation data for 1-second resolution trading.
- **Success Criteria**: Materialized view refresh completes in <15 seconds (52% improvement), enabling more frequent refreshes and reducing data staleness.
- **Stakeholders**: Data analysts and simulation users who depend on timely updated materialized view data
- **Timeline Constraints**: None (optimization sprint)

### Technical Context
- **Current System State**: Migration file `033_derived_snapshot_features_trade_v1.sql` contains query with 20 CTEs. HashAggregate disabled (`enable_hashagg=off`), work_mem set to 1GB. Query processes 7.9M trades into 3.1M groups.
- **Target System State**: Same migration file with HashAggregate enabled, work_mem increased to 2GB, kalshi_window_info refactored to eliminate redundant scan. Query executes in <15 seconds.
- **Architecture Impact**: No architectural changes, only query optimization within existing materialized view
- **Integration Points**: Materialized view is used by simulation endpoints and analysis scripts

### Sprint Scope
- **In Scope**: 
  - Enable HashAggregate with 2GB work_mem
  - Refactor kalshi_window_info to compute from trade_agg_core
  - Performance testing and validation
  - Documentation updates
- **Out of Scope**: 
  - Optimizing trade_open/trade_close CTEs (deferred to future sprint)
  - Materializing intermediate CTEs as temporary tables (deferred to future sprint)
  - Application code changes
- **Assumptions**: 
  - Server has sufficient memory for 2GB work_mem
  - PostgreSQL version supports HashAggregate
  - Query correctness can be validated via result comparison
- **Constraints**: 
  - Must maintain query correctness (same output as original)
  - Must not break existing materialized view dependencies

## Sprint Phases

### Phase 1: High-Priority Optimizations (Duration: 4-6 hours)
**Objective**: Implement high-impact optimizations with low risk
**Dependencies**: None
**Deliverables**: Optimized query with HashAggregate enabled and kalshi_window_info refactored

### Phase 2: Validation and Testing (Duration: 2-3 hours)
**Objective**: Verify optimizations don't break correctness and measure performance improvements
**Dependencies**: Must complete Phase 1 successfully
**Deliverables**: Performance test results and validation report

### Phase 3: Documentation and Quality Assurance (Duration: 1-2 hours)
**Objective**: Update documentation and validate all sprint work meets quality standards
**Dependencies**: Must complete Phase 2 successfully
**Deliverables**: Updated migration file comments and sprint completion report

## Sprint Backlog

### Epic 1: Enable HashAggregate Optimization
**Priority**: Critical (business justification: 57% performance improvement)
**Estimated Time**: 2 hours (1 hour implementation + 1 hour testing)
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Enable HashAggregate with 2GB work_mem
- **ID**: S1-E1-S1
- **Type**: Performance Optimization
- **Priority**: Critical (57% performance improvement)
- **Estimate**: 1 hour (30 min implementation + 30 min testing)
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql:107-108`
- **Files to Create**: None
- **Dependencies**: PostgreSQL with sufficient memory for 2GB work_mem

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `db/migrations/033_derived_snapshot_features_trade_v1.sql:107` contains `SET work_mem = '2GB';`
  - [ ] `db/migrations/033_derived_snapshot_features_trade_v1.sql:108` does NOT contain `SET enable_hashagg = off;` (HashAggregate enabled by default)
  - [ ] EXPLAIN (without ANALYZE) shows HashAggregate (not GroupAggregate) in trade_agg_core CTE execution plan
  - [ ] Execution plan shows batches = 1 (no disk spills expected)
  - [ ] Materialized view creation completes successfully (measured with `time` command)
  - [ ] Total execution time < 15 seconds (measured with `time` command, not EXPLAIN ANALYZE)

- **Technical Context**:
  - **Current State**: 
    ```sql
    SET work_mem = '1GB';
    SET enable_hashagg = off;
    ```
    HashAggregate disabled causes GroupAggregate to process 3.1M groups sequentially, taking 46 seconds.
  - **Required Changes**: 
    ```sql
    SET work_mem = '2GB';
    -- Remove: SET enable_hashagg = off;
    ```
    Enable HashAggregate with sufficient memory to avoid disk spills.
  - **Integration Points**: Changes affect trade_agg_core CTE execution plan
  - **Data Structures**: No changes to data structures
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. Open `db/migrations/033_derived_snapshot_features_trade_v1.sql`
  2. Change line 107 from `SET work_mem = '1GB';` to `SET work_mem = '2GB';`
  3. Remove or comment out line 108: `SET enable_hashagg = off;`
  4. Save file

- **Validation Steps**:
  1. Validate execution plan shows HashAggregate (without executing full query):
     ```bash
     source .env
     # Extract CREATE MATERIALIZED VIEW query and run EXPLAIN (not ANALYZE)
     # This shows the plan without executing
     psql "$DATABASE_URL" -c "EXPLAIN (FORMAT JSON) $(grep -A 10000 'CREATE MATERIALIZED VIEW' db/migrations/033_derived_snapshot_features_trade_v1.sql | head -n -10 | tail -n +2)" > /tmp/execution_plan.json 2>&1
     ```
  2. Verify HashAggregate in execution plan:
     ```bash
     grep -i "HashAggregate" /tmp/execution_plan.json
     grep -i "trade_agg_core" /tmp/execution_plan.json | grep -i "HashAggregate"
     ```
  3. Verify batches = 1 in execution plan (or not present, meaning no spills expected)
  4. Create materialized view and measure time (this will execute but we need the view anyway):
     ```bash
     source .env
     time psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql > /tmp/mv_creation.log 2>&1
     ```
  5. Verify materialized view created successfully (check for errors):
     ```bash
     grep -i "error" /tmp/mv_creation.log
     psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM derived.snapshot_features_trade_v1 LIMIT 1;"
     ```
  6. Verify execution time < 15 seconds (from `time` command output)

- **Definition of Done**: 
  - [ ] Migration file updated with 2GB work_mem
  - [ ] HashAggregate enabled (enable_hashagg setting removed)
  - [ ] EXPLAIN (without ANALYZE) confirms HashAggregate usage in execution plan
  - [ ] Execution plan shows batches = 1 (no disk spills expected)
  - [ ] Materialized view created successfully
  - [ ] Total execution time < 15 seconds (from `time` command)

- **Rollback Plan**: 
  - Revert to `SET work_mem = '1GB';` and `SET enable_hashagg = off;` if memory issues occur
  - Document memory requirements for future reference

- **Risk Assessment**: 
  - **Risk**: Memory usage exceeds available memory
  - **Probability**: Low (2GB work_mem is reasonable)
  - **Mitigation**: Test with 2GB first, monitor memory usage, fall back to GroupAggregate if needed

- **Success Metrics**:
  - **Performance**: trade_agg_core execution time: 46s → <20s (57% improvement)
  - **Quality**: No disk spills (batches = 1)
  - **Functionality**: Query produces identical results

### Epic 2: Eliminate Redundant Trade Scan
**Priority**: High (business justification: 91% improvement in kalshi_window_info, 17% total improvement)
**Estimated Time**: 3 hours (2 hours implementation + 1 hour testing)
**Dependencies**: Epic 1 (trade_agg_core must exist)
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 2.1: Refactor kalshi_window_info to compute from trade_agg_core
- **ID**: S1-E2-S1
- **Type**: Performance Optimization
- **Priority**: High (91% improvement in kalshi_window_info)
- **Estimate**: 2 hours (1 hour implementation + 1 hour testing)
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1 (trade_agg_core must exist)
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql:200-216`
- **Files to Create**: None
- **Dependencies**: trade_agg_core CTE must be computed before kalshi_window_info (already the case)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `db/migrations/033_derived_snapshot_features_trade_v1.sql:200-216` contains kalshi_window_info CTE that queries trade_agg_core (not kalshi.trades)
  - [ ] kalshi_window_info CTE uses `MIN(tac.first_ct)` and `MAX(tac.last_ct)` from trade_agg_core
  - [ ] EXPLAIN (without ANALYZE) shows kalshi_window_info does NOT scan kalshi.trades table (validated via execution plan)
  - [ ] Window boundaries match original computation (validation query passes on test game)
  - [ ] kalshi_window_info execution time acceptable (validated via full materialized view creation timing)

- **Technical Context**:
  - **Current State**: 
    ```sql
    kalshi_window_info AS (
        SELECT
            md.espn_event_id AS game_id,
            MIN(kt.created_time) AS kalshi_window_start,
            MAX(kt.created_time) AS kalshi_window_end
        FROM game_time_info gti
        JOIN markets_dedup md ON md.espn_event_id = gti.game_id
        JOIN kalshi.trades kt
          ON kt.ticker = md.ticker
         AND kt.created_time IS NOT NULL
         AND kt.created_time >= gti.game_start
         AND (kt.yes_price IS NOT NULL OR kt.no_price IS NOT NULL)
        GROUP BY md.espn_event_id
    ),
    ```
    Scans all 7.9M trades again to compute MIN/MAX, duplicating work from trade_base.
  - **Required Changes**: 
    ```sql
    kalshi_window_info AS (
        SELECT
            tac.game_id,
            MIN(tac.first_ct) AS kalshi_window_start,
            MAX(tac.last_ct) AS kalshi_window_end
        FROM trade_agg_core tac
        GROUP BY tac.game_id
    ),
    ```
    Compute window boundaries from trade_agg_core output instead of scanning trades again.
  - **Integration Points**: kalshi_window_info is used by game_time_with_kalshi CTE
  - **Data Structures**: No changes to data structures
  - **API Contracts**: No API changes

- **Implementation Steps**:
  1. Open `db/migrations/033_derived_snapshot_features_trade_v1.sql`
  2. Locate kalshi_window_info CTE (lines 200-216)
  3. Replace CTE definition with new version that queries trade_agg_core
  4. Ensure trade_agg_core is defined before kalshi_window_info (already the case)
  5. Save file

- **Validation Steps**:
  1. Validate execution plan shows kalshi_window_info queries trade_agg_core (not kalshi.trades):
     ```bash
     # Extract just the kalshi_window_info CTE for plan validation
     source .env
     psql "$DATABASE_URL" -c "EXPLAIN (FORMAT JSON) WITH trade_agg_core AS (SELECT game_id, first_ct, last_ct FROM (SELECT 1) x), kalshi_window_info AS (SELECT tac.game_id, MIN(tac.first_ct) AS kalshi_window_start, MAX(tac.last_ct) AS kalshi_window_end FROM trade_agg_core tac GROUP BY tac.game_id) SELECT * FROM kalshi_window_info LIMIT 1;" | grep -i "trade_agg_core"
     ```
  2. Create test query for single game to validate window boundaries:
     ```sql
     -- Test query: Compare window boundaries for single game
     -- Run optimized query on test game and check window boundaries
     ```
  3. Verify window boundaries match expected values for test game
  4. Verify execution plan shows no kalshi.trades scan in kalshi_window_info

- **Definition of Done**: 
  - [ ] kalshi_window_info CTE refactored to query trade_agg_core
  - [ ] EXPLAIN (without ANALYZE) confirms no kalshi.trades scan in kalshi_window_info (validated via execution plan)
  - [ ] Window boundaries match expected values for test game (100% match)
  - [ ] Code changes complete and tested on subset

- **Rollback Plan**: 
  - Revert to original kalshi_window_info CTE if window boundaries don't match
  - Document discrepancy for investigation

- **Risk Assessment**: 
  - **Risk**: Window boundaries differ from original computation
  - **Probability**: Low (logic should be identical)
  - **Mitigation**: Compare window boundaries before/after, test with sample games first

- **Success Metrics**:
  - **Performance**: kalshi_window_info execution time: 5.4s → <0.5s (91% improvement)
  - **Quality**: Window boundaries match original (100% match)
  - **Functionality**: Query produces identical results

### Epic 3: Performance Validation
**Priority**: Critical (business justification: Ensure optimizations work correctly)
**Estimated Time**: 3 hours (2 hours testing + 1 hour analysis)
**Dependencies**: Epic 1 and Epic 2
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 3.1: Validate execution plan and measure performance improvements
- **ID**: S1-E3-S1
- **Type**: Testing
- **Priority**: Critical (validate optimizations)
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1, S1-E2-S1 completed
- **Files to Modify**: None
- **Files to Create**: `db/logs/033_optimized_execution_plan.txt` (execution plan), `db/logs/033_optimized_material_view_timing.txt` (timing log)
- **Dependencies**: Optimized migration file

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] EXPLAIN (without ANALYZE) output saved to `db/logs/033_optimized_execution_plan.txt`
  - [ ] Execution plan shows HashAggregate (not GroupAggregate) in trade_agg_core CTE
  - [ ] Execution plan shows kalshi_window_info queries trade_agg_core (not kalshi.trades)
  - [ ] Materialized view creation completes successfully (measured with `time` command)
  - [ ] Total execution time < 15 seconds (measured with `time` command, not EXPLAIN ANALYZE)
  - [ ] No disk spills indicated in execution plan (batches = 1 for HashAggregate)

- **Technical Context**:
  - **Current State**: Performance baseline from previous analysis: 31.45s total, 46.34s trade_agg_core, 5.42s kalshi_window_info
  - **Required Changes**: Validate execution plan and measure actual creation time (not EXPLAIN ANALYZE which takes hours)
  - **Integration Points**: Performance metrics feed into validation report
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Validate execution plan without executing (EXPLAIN only):
     ```bash
     source .env
     # Extract just the CREATE MATERIALIZED VIEW query for plan validation
     # Create a test file with just the query (not the full migration)
     psql "$DATABASE_URL" -c "EXPLAIN (FORMAT JSON) $(cat db/migrations/033_derived_snapshot_features_trade_v1.sql | grep -A 10000 'CREATE MATERIALIZED VIEW' | head -n -10)" > db/logs/033_optimized_execution_plan.txt 2>&1
     ```
  2. Validate execution plan shows correct optimizations:
     ```bash
     # Check for HashAggregate in trade_agg_core
     grep -A 20 "trade_agg_core" db/logs/033_optimized_execution_plan.txt | grep -i "HashAggregate"
     
     # Check kalshi_window_info queries trade_agg_core
     grep -A 10 "kalshi_window_info" db/logs/033_optimized_execution_plan.txt | grep -i "trade_agg_core"
     
     # Check for no disk spills (batches = 1)
     grep "batches" db/logs/033_optimized_execution_plan.txt
     ```
  3. Measure actual materialized view creation time (without EXPLAIN ANALYZE):
     ```bash
     # Time the actual creation (this will execute the query but we need the materialized view anyway)
     source .env
     time psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql > db/logs/033_optimized_material_view_timing.txt 2>&1
     ```
  4. Extract timing from output:
     ```bash
     # The `time` command output will show real/user/sys time
     tail -5 db/logs/033_optimized_material_view_timing.txt
     ```

- **Validation Steps**:
  1. Verify execution plan shows HashAggregate (not GroupAggregate)
  2. Verify kalshi_window_info queries trade_agg_core (not kalshi.trades)
  3. Verify materialized view created successfully (check for errors in log)
  4. Verify total execution time < 15 seconds (from `time` command output)
  5. Verify no errors in creation log

- **Definition of Done**: 
  - [ ] Execution plan validated (EXPLAIN output saved)
  - [ ] HashAggregate confirmed in execution plan
  - [ ] kalshi_window_info confirmed to query trade_agg_core
  - [ ] Materialized view created successfully
  - [ ] Execution time < 15 seconds (from `time` command)
  - [ ] Performance improvement documented

- **Rollback Plan**: N/A (testing only)

- **Risk Assessment**: 
  - **Risk**: Performance improvements don't meet targets
  - **Probability**: Low (optimizations are well-understood)
  - **Mitigation**: Investigate if targets not met, consider additional optimizations
  - **Risk**: Materialized view creation still takes hours
  - **Probability**: Medium (7.9M trades is large dataset)
  - **Mitigation**: Use execution plan validation (EXPLAIN) to verify optimizations without full execution, then run actual creation once

- **Success Metrics**:
  - **Performance**: Total execution time: 31.45s → <15s (52% improvement) - measured with `time` command
  - **Quality**: Execution plan shows correct optimizations (HashAggregate, no redundant scans)
  - **Functionality**: Query executes successfully and creates materialized view

#### Story 3.2: Validate query correctness on subset
- **ID**: S1-E3-S2
- **Type**: Testing
- **Priority**: Critical (ensure correctness)
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: S1-E3-S1 completed (execution plan validated)
- **Files to Modify**: None
- **Files to Create**: `db/migrations/033_test_single_game.sql` (test query for single game), validation queries
- **Dependencies**: Optimized migration file (but test on subset first)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Test query created that runs optimized CTEs on single game (fast validation)
  - [ ] Single game test completes in < 30 seconds
  - [ ] Window boundaries match expected values for test game
  - [ ] Trade aggregation produces correct OHLC candles for test game
  - [ ] All Kalshi price columns populated correctly for test game
  - [ ] All ESPN probability columns populated correctly for test game
  - [ ] Full materialized view creation completes successfully (after subset validation)

- **Technical Context**:
  - **Current State**: Original query produces correct results
  - **Required Changes**: Verify optimized query produces identical results on subset first, then full dataset
  - **Integration Points**: Validation ensures downstream systems continue to work
  - **Data Structures**: No changes
  - **API Contracts**: No changes
  - **Note**: Test on single game first to validate correctness quickly, then create full materialized view

- **Implementation Steps**:
  1. Create test query for single game (modify migration to filter to one game):
     ```sql
     -- Test query: Run optimized CTEs on single game
     -- Modify season_games CTE to filter to one test game
     WITH
     season_games AS (
         SELECT sg.event_id AS game_id, sg.event_date AS game_start
         FROM espn.scoreboard_games sg
         WHERE sg.event_id = '401810095'  -- Test game
           AND sg.event_date IS NOT NULL
           AND EXISTS (
             SELECT 1
             FROM espn.probabilities_raw_items p
             WHERE p.game_id = sg.event_id
               AND p.season_label = '2025-26'
           )
     ),
     -- ... rest of CTEs unchanged ...
     ```
  2. Run test query and validate results:
     ```bash
     source .env
     psql "$DATABASE_URL" -f db/migrations/033_test_single_game.sql > db/logs/033_single_game_test.txt 2>&1
     ```
  3. Validate test game results:
     ```sql
     -- Check row count for test game
     SELECT COUNT(*) FROM test_result WHERE game_id = '401810095';
     
     -- Check window boundaries
     SELECT game_id, kalshi_window_start, kalshi_window_end 
     FROM test_result 
     WHERE game_id = '401810095' 
     LIMIT 1;
     
     -- Check trade candles exist
     SELECT COUNT(*) FROM test_result 
     WHERE game_id = '401810095' 
       AND kalshi_home_mid_price IS NOT NULL;
     ```
  4. If test game validation passes, create full materialized view:
     ```bash
     source .env
     time psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql > db/logs/033_full_mv_creation.txt 2>&1
     ```

- **Validation Steps**:
  1. Verify test query completes in < 30 seconds
  2. Verify test game results match expected values
  3. Verify window boundaries correct for test game
  4. Verify trade aggregation correct for test game
  5. Verify full materialized view created successfully (if test passes)

- **Definition of Done**: 
  - [ ] Test query created for single game validation
  - [ ] Test game validation passes
  - [ ] Full materialized view created successfully (after test validation)
  - [ ] Results match expected (100% match for test game)
  - [ ] Correctness documented

- **Rollback Plan**: 
  - Revert optimizations if test game validation fails
  - Document issues for investigation
  - Do not create full materialized view if test fails

- **Risk Assessment**: 
  - **Risk**: Query produces incorrect results
  - **Probability**: Low (optimizations are performance-only)
  - **Mitigation**: Test on single game first (fast validation), then create full view
  - **Risk**: Full materialized view creation still takes hours
  - **Probability**: Medium (7.9M trades is large dataset)
  - **Mitigation**: Validate correctness on subset first, then create full view once (acceptable since it's one-time creation)

- **Success Metrics**:
  - **Quality**: 100% correctness match for test game
  - **Performance**: Test game validation completes in < 30 seconds
  - **Functionality**: Query produces identical results for test game, then full materialized view created successfully

### Epic 4: Documentation Update
**Priority**: High (business justification: Document optimizations for future reference)
**Estimated Time**: 1 hour
**Dependencies**: Epic 3
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 4.1: Update migration file comments
- **ID**: S1-E4-S1
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1, S1-E3-S2 completed
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Files to Create**: None
- **Dependencies**: Optimizations complete and validated

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Migration file header comments updated with optimization details
  - [ ] kalshi_window_info CTE comments explain it queries trade_agg_core
  - [ ] Session settings comments explain 2GB work_mem and HashAggregate usage
  - [ ] Performance characteristics documented in comments

- **Technical Context**:
  - **Current State**: Comments describe original implementation
  - **Required Changes**: Update comments to reflect optimizations
  - **Integration Points**: Comments help future developers understand optimizations
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Update header comments with optimization summary
  2. Update kalshi_window_info CTE comments
  3. Update session settings comments
  4. Add performance notes

- **Validation Steps**:
  1. Verify comments are accurate
  2. Verify comments are complete
  3. Verify comments are clear

- **Definition of Done**: 
  - [ ] All comments updated
  - [ ] Comments are accurate and complete
  - [ ] Comments are clear

- **Rollback Plan**: N/A (documentation only)

- **Risk Assessment**: Low risk (documentation only)

- **Success Metrics**:
  - **Quality**: Comments accurately document optimizations
  - **Functionality**: Documentation complete

### Epic 5: Quality Gate Validation
**Priority**: Critical (business justification: Ensure all work meets quality standards)
**Estimated Time**: 1-2 hours
**Dependencies**: All other epics
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 5.1: Quality Gate Validation
- **ID**: S1-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] Execution plan validated (HashAggregate confirmed, kalshi_window_info queries trade_agg_core)
  - [ ] Materialized view creation completes successfully (measured with `time` command)
  - [ ] Total execution time < 15 seconds (from `time` command, not EXPLAIN ANALYZE)
  - [ ] Query correctness validated on test game (100% match)
  - [ ] Full materialized view created successfully (after test validation)
  - [ ] Documentation updated
  - [ ] All previous story acceptance criteria verified

- **Technical Context**:
  - **Current State**: All optimizations implemented and tested
  - **Required Changes**: Final validation of all quality gates
  - **Integration Points**: Quality gates ensure production readiness
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Verify execution plan shows correct optimizations (HashAggregate, no redundant scans)
  2. Verify materialized view creation completed successfully (check log for errors)
  3. Verify execution time < 15 seconds (from `time` command output)
  4. Verify test game correctness validation passed
  5. Verify documentation complete

- **Validation Steps**:
  1. Execution plan validated (no EXPLAIN ANALYZE needed)
  2. Materialized view created successfully
  3. Execution time acceptable (<15s from `time` command)
  4. Test game correctness validated
  5. All acceptance criteria met
  6. Ready for production

- **Definition of Done**: 
  - [ ] All quality gates pass
  - [ ] All acceptance criteria met
  - [ ] Ready for production

- **Rollback Plan**: Address any failing quality gates before completion

- **Risk Assessment**: Low risk (final validation)

- **Success Metrics**:
  - **Quality**: 100% quality gate pass rate
  - **Functionality**: All optimizations working correctly

### Epic 6: Sprint Completion and Archive
**Priority**: Critical (business justification: Complete sprint properly)
**Estimated Time**: 1 hour
**Dependencies**: Quality Gate Validation
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 6.1: Sprint Completion and Archive
- **ID**: S1-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created with performance improvements documented
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Performance metrics compared: baseline vs. optimized
  - [ ] Lessons learned documented
  - [ ] Sprint marked as completed

- **Technical Context**:
  - **Current State**: Sprint work complete
  - **Required Changes**: Create completion report
  - **Integration Points**: Completion report feeds into project documentation
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Create completion report with performance metrics
  2. Document lessons learned
  3. Organize sprint files
  4. Mark sprint as completed

- **Validation Steps**:
  1. Completion report created
  2. All metrics documented
  3. Sprint files organized

- **Definition of Done**: 
  - [ ] Completion report created
  - [ ] Sprint files organized
  - [ ] Sprint marked as completed

- **Rollback Plan**: N/A (completion only)

- **Risk Assessment**: Low risk (completion only)

- **Success Metrics**:
  - **Quality**: Completion report complete
  - **Functionality**: Sprint properly closed

## Technical Decisions

### Design Pattern Analysis

#### Design Pattern: Pipeline Pattern (Maintained)

**Pattern Name**: Pipeline Pattern  
**Category**: Architectural  
**Intent**: Processes data through sequential stages (CTEs), each transforming the output of the previous stage

**Implementation**: 
- **File**: `db/migrations/033_derived_snapshot_features_trade_v1.sql:109-771`
- **Code**: 20 CTEs chained together, each consuming output from previous CTEs
- **Changes**: No architectural changes, only optimization of individual CTEs

**Benefits**:
- Clear separation of concerns maintained
- Easy to understand data flow
- Allows incremental optimization of individual CTEs

**Trade-offs**:
- Performance cost of CTE materialization remains
- Memory cost of multiple CTEs remains
- Optimization limited to individual CTEs (not cross-CTE)

**Why This Pattern**: Maintains existing architecture while optimizing performance

### Algorithm Analysis

#### Algorithm: HashAggregate (Enabled)

**Algorithm Name**: HashAggregate  
**Algorithm Type**: Aggregation Algorithm  
**Big O Notation**: 
- Time Complexity: O(n) average case
- Space Complexity: O(g) where g = number of groups

**Algorithm Description**:
- Builds hash table of groups
- Processes input rows once, updating hash table entries
- Faster than GroupAggregate for large numbers of groups

**Use Case**: Aggregating 7M trades into 3.1M groups (game_id, ticker, kalshi_team_side, period_ts)

**Performance Characteristics**:
- **Best Case**: O(n) with good hash distribution, ~10s estimated
- **Average Case**: O(n) with minimal collisions, ~15s estimated
- **Worst Case**: O(n²) with many hash collisions, ~30s estimated
- **Memory Usage**: O(g) = O(3.1M groups) = ~2GB hash table (requires 2GB work_mem)

**Why This Algorithm**: With 2GB work_mem, HashAggregate eliminates disk spills and provides 57% performance improvement (46s → <20s)

**Design Decision**: Enable HashAggregate with 2GB work_mem

**Problem Statement**:
- GroupAggregate processes 3.1M groups sequentially, taking 46 seconds
- HashAggregate would be faster but was disabled due to memory concerns with 1GB work_mem causing disk spills (5 batches)
- Need to optimize trade aggregation without breaking correctness

**Project Scope**: Single migration file optimization, no application code changes

**Sprint Scope Analysis**:
- **Complexity Assessment**: Low complexity (configuration change), 1 file affected, ~2 lines changed
- **Sprint Scope Determination**: Single Sprint
- **Scope Justification**: Simple configuration change, can be completed in single sprint
- **Timeline Considerations**: 1 hour implementation + 1 hour testing = 2 hours total

**Multiple Solution Analysis**:

**Option 1: Keep GroupAggregate with Pre-sorted Input**
- **Design Pattern**: None
- **Algorithm**: GroupAggregate with pre-sorted input
- **Implementation Complexity**: Low (1 hour)
- **Maintenance Overhead**: Low
- **Scalability**: Poor (sequential processing remains slow)
- **Cost-Benefit**: Low cost, low benefit (24% improvement vs 57%)
- **Over-Engineering Risk**: None
- **Rejected**: Only provides 24% improvement vs 57% with HashAggregate

**Option 2: Materialize Intermediate CTEs**
- **Design Pattern**: Materialization Pattern
- **Algorithm**: Same aggregation algorithms
- **Implementation Complexity**: High (8-12 hours)
- **Maintenance Overhead**: High (more complex code)
- **Scalability**: Good
- **Cost-Benefit**: High cost, medium benefit (36% improvement)
- **Over-Engineering Risk**: Medium (complexity doesn't match problem)
- **Rejected**: Too complex for problem, lower benefit than HashAggregate

**Option 3: Enable HashAggregate with 2GB work_mem (CHOSEN)**
- **Design Pattern**: None (algorithm selection)
- **Algorithm**: HashAggregate
- **Implementation Complexity**: Low (1 hour)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent (better performance as data grows)
- **Cost-Benefit**: Low cost, high benefit (57% improvement)
- **Over-Engineering Risk**: None
- **Selected**: Provides best performance improvement with minimal complexity

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 1 hour (low complexity)
- **Learning Curve**: 0 hours (standard PostgreSQL feature)
- **Configuration Effort**: 0.5 hours (change 2 lines)

**Maintenance Cost**:
- **Monitoring**: 0.5 hours/month (check memory usage)
- **Updates**: 0 hours (no updates needed)
- **Debugging**: 0.5 hours/incident (standard debugging)

**Performance Benefit**:
- **Execution Time**: 57% improvement (46s → <20s)
- **Throughput**: N/A (one-time materialized view creation)
- **Resource Efficiency**: Acceptable memory increase (1GB → 2GB)

**Maintainability Benefit**:
- **Code Quality**: No change (same code, different algorithm)
- **Developer Productivity**: No change
- **System Reliability**: Improved (faster execution reduces timeout risk)

**Risk Cost**:
- **Memory Risk**: Low risk, mitigated by testing with 2GB first
- **Correctness Risk**: None (algorithm change doesn't affect results)

**Over-Engineering Prevention**:
- **Problem Complexity**: Low (algorithm selection)
- **Solution Complexity**: Low (configuration change)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: HashAggregate scales better than GroupAggregate

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Low complexity for single file
- **Team Capability**: ✅ Standard PostgreSQL knowledge
- **Timeline Constraints**: ✅ Fits in single sprint
- **Future Growth**: ✅ Better scalability
- **Technical Debt**: ✅ Reduces technical debt (enables better algorithm)

**Chosen Solution**: Enable HashAggregate with 2GB work_mem
- Implementation: Change work_mem to 2GB, remove enable_hashagg=off
- Configuration: Standard PostgreSQL configuration
- Integration: No integration changes needed

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: 57% improvement in trade aggregation time (46s → <20s)
- **Simplicity**: Single configuration change
- **Reliability**: HashAggregate is well-tested PostgreSQL feature
- **Scalability**: Better performance as data grows

**Cons**:
- **Memory**: Increases memory requirement from 1GB to 2GB
- **Server Requirements**: Requires server with sufficient memory

**Risk Assessment**:
- **Memory Risk**: Low risk, mitigated by testing with 2GB first
- **Correctness Risk**: None (algorithm change doesn't affect results)

**Trade-off Analysis**:
- **Sacrificed**: 1GB additional memory
- **Gained**: 57% performance improvement, better scalability
- **Net Benefit**: Significant performance gain with minimal cost
- **Over-Engineering Risk**: None (appropriate solution)

## Testing Strategy

### Testing Approach
- **Unit Tests**: N/A (SQL migration file)
- **Integration Tests**: Materialized view creation and query execution
- **E2E Tests**: N/A (no end-to-end flow)
- **Performance Tests**: EXPLAIN ANALYZE with timing measurements

### Performance Testing
- **Load Test**: N/A (one-time materialized view creation)
- **Stress Test**: Test with 2GB work_mem to verify no memory issues
- **Memory Test**: Monitor memory usage during execution

### Correctness Testing
- **Row Count Validation**: Compare row counts before/after optimization
- **Sample Data Validation**: Compare random sample of rows
- **Window Boundary Validation**: Compare window boundaries computed from trade_agg_core vs original

## Deployment Plan
- **Pre-Deployment**: 
  - Verify server has sufficient memory for 2GB work_mem
  - Backup current materialized view (if exists)
  - Test optimizations in development environment
- **Deployment Steps**: 
  1. Run optimized migration file
  2. Monitor execution time and memory usage
  3. Validate results
- **Post-Deployment**: 
  - Verify materialized view created successfully
  - Verify performance improvements
  - Monitor for any issues
- **Rollback Plan**: 
  - Revert to original migration file if issues occur
  - Restore materialized view from backup if needed

## Risk Assessment

### Technical Risks
- **Risk 1**: HashAggregate memory usage exceeds available memory
  - **Probability**: Low (2GB work_mem is reasonable)
  - **Impact**: High (query fails or spills to disk)
  - **Mitigation**: Test with 2GB first, monitor memory usage, fall back to GroupAggregate if needed
  - **Contingency**: Keep GroupAggregate option with pre-sorted input

- **Risk 2**: kalshi_window_info refactoring changes window boundaries
  - **Probability**: Low (logic should be identical)
  - **Impact**: High (incorrect window boundaries affect downstream CTEs)
  - **Mitigation**: Compare window boundaries before/after, test with sample games first
  - **Contingency**: Revert to original kalshi_window_info if boundaries differ

- **Risk 3**: Query optimization breaks correctness
  - **Probability**: Low (optimizations are performance-only)
  - **Impact**: High (incorrect results in materialized view)
  - **Mitigation**: Thorough validation, compare sample data
  - **Contingency**: Revert optimizations if correctness issues found

### Business Risks
- **Risk 1**: Optimizations don't provide expected performance improvement
  - **Probability**: Medium (performance improvements are estimates)
  - **Impact**: Low (query still works, just not faster)
  - **Mitigation**: Set realistic expectations, measure baseline before optimizations
  - **Contingency**: Accept current performance if optimizations don't help

### Resource Risks
- **Risk 1**: Increased memory requirements unavailable on production server
  - **Probability**: Low (2GB work_mem is reasonable)
  - **Impact**: Medium (optimizations cannot be deployed)
  - **Mitigation**: Check server memory configuration before deployment
  - **Contingency**: Deploy optimizations that don't require increased memory

## Success Metrics

### Technical Metrics
- **Execution Time**: <15 seconds (52% improvement from 31.45s)
- **Trade Aggregation Time**: <20 seconds (57% improvement from 46.34s)
- **kalshi_window_info Time**: <0.5 seconds (91% improvement from 5.42s)
- **Memory Usage**: <2.5GB peak (acceptable increase)
- **Disk Spills**: 0 batches (no spills)

### Quality Metrics
- **Correctness**: 100% match with original query results
- **Code Quality**: No degradation (same code, optimized)
- **Documentation**: Complete and accurate

### Business Metrics
- **Refresh Frequency**: Can refresh more frequently (faster execution)
- **Data Staleness**: Reduced (faster refresh enables more frequent updates)
- **User Experience**: Faster access to updated simulation data

### Monitoring Strategy
- **Real-time Monitoring**: Log execution time for each materialized view refresh
- **Alert Thresholds**: 
  - Execution time > 20 seconds: Warning
  - Execution time > 30 seconds: Critical
  - Memory usage > 2.5GB: Warning
  - Disk spills detected: Warning
- **Reporting**: Weekly performance report comparing execution times

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (performance, correctness, memory)

### Post-Sprint Quality Comparison
- **Performance**: Baseline 31.45s → Target <15s (52% improvement)
- **Memory Usage**: Baseline 2.17GB → Target <2.5GB (acceptable increase)
- **Correctness**: 100% match maintained
- **Overall Assessment**: Performance significantly improved with maintained correctness

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation

**IMPORTANT**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

