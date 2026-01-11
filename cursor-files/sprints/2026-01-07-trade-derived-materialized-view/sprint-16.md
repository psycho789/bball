# Sprint 16: Trade-Derived Materialized View - 1-Second Resolution

**Date**: Wed Jan  7 03:56:48 PST 2026  
**Sprint Duration**: 1 day (24 hours total)  
**Sprint Goal**: Create materialized view `derived.snapshot_features_trade_v1` that aggregates trades into 1-second candles with bid/ask estimation, enabling 1-second resolution simulation with fast queries (<100ms per game)  
**Current Status**: Simulation uses `derived.snapshot_features_v1` (1-minute candlestick resolution). Trade data exists in `kalshi.trades` table (7M+ records) but not used in simulation.  
**Target Status**: New materialized view `derived.snapshot_features_trade_v1` created with 1-second trade aggregation, bid/ask estimation, indexes for fast queries. Simulation can optionally use trade view for 1-second resolution.  
**Team Size**: 1  
**Sprint Lead**: AI Assistant  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence (commands + verbatim output, code refs, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, exact data sources analyzed
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: PostgreSQL via `DATABASE_URL`

## Pre-Sprint Code Quality Baseline
- **Test Results**: N/A (no tests for materialized views)
- **QC Results**: N/A
- **Code Coverage**: N/A
- **Build Status**: Migration scripts execute successfully

## Database Evidence Template
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`).
- **DO modify database** - CREATE MATERIALIZED VIEW is part of sprint plan
- **DO NOT modify existing views** - only create new view

## Git Usage Restrictions
**CRITICAL RESTRICTION**: No git commands unless explicitly directed.

## Sprint Overview

### Business Context
- **Business Driver**: Simulation currently limited to 1-minute resolution, missing optimal entry/exit timing. Trade data provides 1-second resolution but requires aggregation. User requested materialized view modification for trade data.
- **Success Criteria**: 
  - Trade-derived view created and refreshable in <30 minutes
  - Query performance <100ms per game
  - Simulation can use 1-second resolution when enabled
- **Stakeholders**: Simulation users, data analysts
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - `derived.snapshot_features_v1` uses `kalshi.candlesticks` (1-minute resolution)
  - `kalshi.trades` table has 7M+ records with microsecond precision
  - `get_aligned_data()` queries canonical view
  - Trade aggregation utilities exist in `webapp/api/utils/trade_candles.py`
- **Target System State**: 
  - New view `derived.snapshot_features_trade_v1` with 1-second trade aggregation
  - Bid/ask estimation using spread model
  - Indexes for fast queries
  - `get_aligned_data()` can optionally use trade view
- **Architecture Impact**: Adds new materialized view, maintains separation from candlestick view
- **Integration Points**: `scripts/simulate_trading_strategy.py`, `webapp/api/endpoints/simulation.py`

### Sprint Scope
- **In Scope**: 
  - Create `derived.snapshot_features_trade_v1` materialized view
  - Implement 1-second trade aggregation
  - Implement bid/ask estimation using spread model
  - Create indexes for performance
  - Update `get_aligned_data()` to optionally use trade view
  - Update simulation endpoint to accept trade view parameter
- **Out of Scope**: 
  - Modifying existing `snapshot_features_v1` view
  - Real-time trade data processing
  - Advanced spread models (using simple conservative model)
- **Assumptions**: 
  - Trade data coverage is ~50% of seconds (sparse but acceptable)
  - Spread model can estimate bid/ask from execution prices
  - Refresh time <30 minutes is acceptable
- **Constraints**: 
  - Must maintain backward compatibility (existing code uses candlestick view)
  - Must follow existing materialized view pattern

## Sprint Phases

### Phase 1: Create Trade-Derived Materialized View (Duration: 12 hours)
**Objective**: Create new materialized view `derived.snapshot_features_trade_v1` with 1-second trade aggregation and bid/ask estimation
**Dependencies**: `kalshi.trades` table, existing `snapshot_features_v1` structure for reference
**Deliverables**: Migration file `db/migrations/033_derived_snapshot_features_trade_v1.sql` with complete view definition

### Phase 2: Create Indexes and Optimize (Duration: 4 hours)
**Objective**: Create indexes for fast queries and optimize view performance
**Dependencies**: Phase 1 complete
**Deliverables**: Indexed view with query performance <100ms per game

### Phase 3: Update Simulation to Use Trade View (Duration: 4 hours)
**Objective**: Modify `get_aligned_data()` to optionally use trade-derived view
**Dependencies**: Phase 2 complete
**Deliverables**: Simulation can use trade view when enabled

### Phase 4: Testing and Validation (Duration: 4 hours)
**Objective**: Validate accuracy, performance, and refresh time
**Dependencies**: Phase 3 complete
**Deliverables**: Tested, validated implementation with documentation

## Sprint Backlog

### Epic 1: Create Trade-Derived Materialized View
**Priority**: Critical
**Estimated Time**: 12 hours
**Dependencies**: `kalshi.trades` table, existing view structure
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Design View Structure and ESPN Alignment
- **ID**: S16-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Create**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Dependencies**: PostgreSQL, `kalshi.trades` table, existing `snapshot_features_v1` structure

- **Acceptance Criteria**:
  - [ ] Migration file created at `db/migrations/033_derived_snapshot_features_trade_v1.sql`
  - [ ] ESPN alignment CTEs implemented (reuse from existing view)
  - [ ] View structure matches `snapshot_features_v1` pattern
  - [ ] SQL syntax valid (can be parsed by PostgreSQL)

- **Technical Context**:
  - **Current State**: No trade-derived view exists
  - **Required Changes**: Create new materialized view following existing pattern
  - **Integration Points**: Will be queried by `get_aligned_data()` function
  - **Data Structures**: Same as `snapshot_features_v1` (season_label, game_id, sequence_number, snapshot_ts)

- **Implementation Steps**:
  1. Create migration file `db/migrations/033_derived_snapshot_features_trade_v1.sql`
  2. Copy ESPN alignment CTEs from `snapshot_features_v1` (games_with_kalshi, game_time_info, espn_base, etc.)
  3. Ensure alignment logic matches existing view

- **Validation Steps**:
  - Run `psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql` (should parse without errors)

### Story 1.2: Implement Trade Aggregation CTE
- **ID**: S16-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4 hours
- **Phase**: Phase 1
- **Prerequisites**: S16-E1-S1
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Dependencies**: `kalshi.trades` table

- **Acceptance Criteria**:
  - [ ] Trade aggregation CTE groups trades by 1-second intervals
  - [ ] Calculates OHLC (Open, High, Low, Close) per interval
  - [ ] Handles sparse coverage (NULLs for intervals without trades)
  - [ ] Aggregation query executes without errors

- **Technical Context**:
  - **Current State**: Trades stored individually in `kalshi.trades` table
  - **Required Changes**: Aggregate trades into 1-second candles
  - **Integration Points**: Joins with ESPN alignment CTEs
  - **Data Structures**: Trade aggregation produces (period_ts, yes_price_ohlc, volume, etc.)

- **Implementation Steps**:
  1. Create `trade_aggregated` CTE that:
     - Groups trades by `DATE_TRUNC('second', created_time)`
     - Calculates OHLC from `yes_price` column
     - Handles NULL values (intervals without trades)
  2. Join with ESPN alignment CTEs using same logic as candlestick view

- **Validation Steps**:
  - Test aggregation query on sample game: `SELECT * FROM trade_aggregated WHERE game_id = '401812702' LIMIT 10;`
  - Verify OHLC values are calculated correctly

### Story 1.3: Implement Bid/Ask Estimation
- **ID**: S16-E1-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3 hours
- **Phase**: Phase 1
- **Prerequisites**: S16-E1-S2
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Dependencies**: `kalshi.candlesticks` table (for spread calculation)

- **Acceptance Criteria**:
  - [ ] Bid/ask estimation implemented using spread model
  - [ ] Spread calculated from candlestick data for same ticker/time
  - [ ] Estimation formula: `bid = execution_price - spread/2`, `ask = execution_price + spread/2`
  - [ ] Handles edge cases (no candlestick data, extreme spreads)

- **Technical Context**:
  - **Current State**: Trade data has execution prices only, no bid/ask
  - **Required Changes**: Estimate bid/ask from execution prices + spread
  - **Integration Points**: Uses candlestick spreads for calibration
  - **Data Structures**: Adds `kalshi_trade_bid`, `kalshi_trade_ask` columns

- **Implementation Steps**:
  1. Calculate average spread from candlesticks for same ticker/time window
  2. Apply spread model: `bid = yes_price - spread/2`, `ask = yes_price + spread/2`
  3. Clamp bid/ask to [0, 1] range
  4. Handle NULLs (no candlestick data available)

- **Validation Steps**:
  - Compare estimated bid/ask vs candlestick bid/ask for same time periods
  - Verify spread model produces reasonable estimates (<2 cents error target)

### Story 1.4: Complete View Definition and Test Creation
- **ID**: S16-E1-S4
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2 hours
- **Phase**: Phase 1
- **Prerequisites**: S16-E1-S3
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Dependencies**: All CTEs complete

- **Acceptance Criteria**:
  - [ ] Complete view definition with all CTEs joined
  - [ ] View can be created: `CREATE MATERIALIZED VIEW derived.snapshot_features_trade_v1 AS ...`
  - [ ] View creation completes without errors
  - [ ] View contains expected columns (matching `snapshot_features_v1` structure)

- **Technical Context**:
  - **Current State**: All CTEs implemented separately
  - **Required Changes**: Join all CTEs into final SELECT statement
  - **Integration Points**: Final view structure

- **Implementation Steps**:
  1. Join all CTEs (ESPN alignment + trade aggregation + bid/ask estimation)
  2. Select final columns matching `snapshot_features_v1` structure
  3. Add ORDER BY for consistent ordering
  4. Test view creation

- **Validation Steps**:
  - Run migration: `psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql`
  - Verify view created: `\d+ derived.snapshot_features_trade_v1`
  - Query sample data: `SELECT * FROM derived.snapshot_features_trade_v1 WHERE game_id = '401812702' LIMIT 5;`

### Epic 2: Create Indexes and Optimize
**Priority**: High
**Estimated Time**: 4 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Create Indexes for Query Performance
- **ID**: S16-E2-S1
- **Type**: Configuration
- **Priority**: High
- **Estimate**: 2 hours
- **Phase**: Phase 2
- **Prerequisites**: S16-E1-S4
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Dependencies**: View must exist

- **Acceptance Criteria**:
  - [ ] Unique index on (season_label, game_id, sequence_number, snapshot_ts)
  - [ ] Index on (game_id, sequence_number) for game queries
  - [ ] Index on (season_label, game_id) for season/game queries
  - [ ] All indexes created successfully

- **Technical Context**:
  - **Current State**: View exists but no indexes
  - **Required Changes**: Create indexes matching `snapshot_features_v1` pattern
  - **Integration Points**: Query performance optimization

- **Implementation Steps**:
  1. Add CREATE INDEX statements to migration file
  2. Create unique index for primary key
  3. Create indexes for common query patterns

- **Validation Steps**:
  - Verify indexes created: `\d+ derived.snapshot_features_trade_v1`
  - Test query performance: `EXPLAIN ANALYZE SELECT * FROM derived.snapshot_features_trade_v1 WHERE game_id = '401812702';`

### Story 2.2: Test and Optimize Query Performance
- **ID**: S16-E2-S2
- **Type**: Optimization
- **Priority**: High
- **Estimate**: 2 hours
- **Phase**: Phase 2
- **Prerequisites**: S16-E2-S1
- **Files to Modify**: Migration file (if optimization needed)
- **Dependencies**: Indexes created

- **Acceptance Criteria**:
  - [ ] Single game query completes in <100ms
  - [ ] Season query completes in <500ms
  - [ ] EXPLAIN ANALYZE shows index usage
  - [ ] Query performance meets targets

- **Technical Context**:
  - **Current State**: Indexes created, performance unknown
  - **Required Changes**: Optimize aggregation query if needed
  - **Integration Points**: Query performance

- **Implementation Steps**:
  1. Run EXPLAIN ANALYZE on sample queries
  2. Identify performance bottlenecks
  3. Optimize aggregation query if needed (add filters, optimize CTEs)
  4. Re-test performance

- **Validation Steps**:
  - Run performance tests: `EXPLAIN ANALYZE SELECT * FROM derived.snapshot_features_trade_v1 WHERE game_id = '401812702' ORDER BY sequence_number;`
  - Verify query time <100ms

### Epic 3: Update Simulation to Use Trade View
**Priority**: High
**Estimated Time**: 4 hours
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Add use_trade_view Parameter to get_aligned_data()
- **ID**: S16-E3-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S16-E2-S2
- **Files to Modify**: `scripts/simulate_trading_strategy.py`
- **Dependencies**: Trade view exists and indexed

- **Acceptance Criteria**:
  - [ ] `get_aligned_data()` function accepts `use_trade_view` parameter
  - [ ] Parameter defaults to `False` (backward compatible)
  - [ ] Function signature updated correctly

- **Technical Context**:
  - **Current State**: `get_aligned_data()` only queries `snapshot_features_v1`
  - **Required Changes**: Add optional parameter to choose view
  - **Integration Points**: Called by simulation functions

- **Implementation Steps**:
  1. Add `use_trade_view: bool = False` parameter to `get_aligned_data()` function
  2. Update function docstring
  3. Add parameter validation

- **Validation Steps**:
  - Verify function signature: `help(get_aligned_data)`
  - Test with `use_trade_view=False` (should work as before)

### Story 3.2: Implement Trade View Query Logic
- **ID**: S16-E3-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2 hours
- **Phase**: Phase 3
- **Prerequisites**: S16-E3-S1
- **Files to Modify**: `scripts/simulate_trading_strategy.py`
- **Dependencies**: Trade view exists

- **Acceptance Criteria**:
  - [ ] When `use_trade_view=True`, queries `derived.snapshot_features_trade_v1`
  - [ ] Falls back to `snapshot_features_v1` if trade view unavailable
  - [ ] Handles NULL values (sparse coverage)
  - [ ] Returns same data structure as before

- **Technical Context**:
  - **Current State**: Function queries candlestick view only
  - **Required Changes**: Add conditional query logic
  - **Integration Points**: Returns aligned_data for simulation

- **Implementation Steps**:
  1. Add conditional SQL query based on `use_trade_view` parameter
  2. Query `derived.snapshot_features_trade_v1` when enabled
  3. Handle NULL values in trade data (sparse coverage)
  4. Ensure return format matches existing structure

- **Validation Steps**:
  - Test with `use_trade_view=True`: `get_aligned_data(conn, '401812702', use_trade_view=True)`
  - Verify data structure matches expected format
  - Test fallback when trade view unavailable

### Story 3.3: Update Simulation Endpoint
- **ID**: S16-E3-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S16-E3-S2
- **Files to Modify**: `webapp/api/endpoints/simulation.py`
- **Dependencies**: Updated `get_aligned_data()` function

- **Acceptance Criteria**:
  - [ ] Simulation endpoint accepts `use_trade_view` query parameter
  - [ ] Parameter passed to `get_aligned_data()` function
  - [ ] Defaults to `False` (backward compatible)
  - [ ] API documentation updated

- **Technical Context**:
  - **Current State**: Endpoint doesn't expose trade view option
  - **Required Changes**: Add query parameter and pass to function
  - **Integration Points**: API endpoint, frontend (future)

- **Implementation Steps**:
  1. Add `use_trade_view: bool = False` parameter to endpoint functions
  2. Pass parameter to `get_aligned_data()` calls
  3. Update endpoint docstrings

- **Validation Steps**:
  - Test API endpoint: `curl 'http://localhost:8000/api/simulation/401812702?use_trade_view=true'`
  - Verify parameter is accepted and used

### Epic 4: Testing and Validation
**Priority**: Critical
**Estimated Time**: 4 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Test Refresh Time and Performance
- **ID**: S16-E4-S1
- **Type**: Testing
- **Priority**: Critical
- **Estimate**: 2 hours
- **Phase**: Phase 4
- **Prerequisites**: S16-E3-S3
- **Files to Create**: Test queries/scripts
- **Dependencies**: View exists and indexed

- **Acceptance Criteria**:
  - [ ] Refresh time measured and documented (<30 minutes target)
  - [ ] CONCURRENT refresh tested and works
  - [ ] Query performance validated (<100ms per game)
  - [ ] Performance metrics documented

- **Technical Context**:
  - **Current State**: View created but refresh time unknown
  - **Required Changes**: Test refresh and document results
  - **Integration Points**: Refresh strategy

- **Implementation Steps**:
  1. Test refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_trade_v1;`
  2. Measure refresh time
  3. Test query performance on sample games
  4. Document results

- **Validation Steps**:
  - Run refresh and measure time: `time psql "$DATABASE_URL" -c "REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_trade_v1;"`
  - Verify refresh completes successfully
  - Test queries and measure performance

### Story 4.2: Validate Bid/Ask Estimation Accuracy
- **ID**: S16-E4-S2
- **Type**: Testing
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: S16-E4-S1
- **Files to Create**: Validation queries
- **Dependencies**: View populated with data

- **Acceptance Criteria**:
  - [ ] Estimated bid/ask compared to candlestick bid/ask
  - [ ] Average error <2 cents
  - [ ] Validation results documented
  - [ ] Spread model accuracy confirmed

- **Technical Context**:
  - **Current State**: Bid/ask estimation implemented but not validated
  - **Required Changes**: Compare estimates vs real values
  - **Integration Points**: Spread model validation

- **Implementation Steps**:
  1. Query trade view and candlestick view for same game/time
  2. Compare estimated bid/ask vs candlestick bid/ask
  3. Calculate average error
  4. Document results

- **Validation Steps**:
  - Run comparison query: `SELECT AVG(ABS(trade_bid - candlestick_bid)) FROM ...`
  - Verify average error <2 cents
  - Document validation results

### Story 4.3: Documentation and Refresh Strategy
- **ID**: S16-E4-S3
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: S16-E4-S2
- **Files to Modify**: Migration file, README (if needed)
- **Dependencies**: All testing complete

- **Acceptance Criteria**:
  - [ ] View structure documented in migration file
  - [ ] Refresh commands documented
  - [ ] Bid/ask estimation logic documented
  - [ ] Usage examples provided

- **Technical Context**:
  - **Current State**: Implementation complete but not documented
  - **Required Changes**: Add comments and documentation
  - **Integration Points**: Future maintenance

- **Implementation Steps**:
  1. Add comprehensive comments to migration file
  2. Document refresh strategy
  3. Document bid/ask estimation logic
  4. Add usage examples

- **Validation Steps**:
  - Review migration file for completeness
  - Verify documentation is clear and accurate

## MANDATORY FINAL STORIES

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: S16-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] Migration file fully documented
  - [ ] README updated if needed
  - [ ] Usage examples provided

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: S16-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria**:
  - [ ] Migration SQL syntax valid (parses without errors)
  - [ ] View creation successful
  - [ ] Indexes created successfully
  - [ ] Query performance meets targets
  - [ ] All acceptance criteria from previous stories verified

### Story [FINAL]: Sprint Completion and Archive
- **ID**: S16-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created
  - [ ] All files organized
  - [ ] Sprint marked as completed

## Technical Decisions

### Design Pattern: Materialized View Pattern
- **Category**: Architectural
- **Intent**: Pre-compute expensive trade aggregation for fast queries
- **Implementation**: Separate materialized view following existing `snapshot_features_v1` pattern
- **Benefits**: Fast queries (<100ms), pre-computed aggregation, independent refresh
- **Trade-offs**: Refresh time (20-30 min), storage (~500MB-1GB)
- **Rationale**: Follows existing architecture, provides fast queries, maintains separation

### Algorithm: Time-Window OHLC Aggregation
- **Type**: Time-Series Aggregation
- **Complexity**: Time O(n log n) during refresh, Space O(n)
- **Description**: Groups trades by 1-second intervals, calculates OHLC per interval
- **Use Case**: Convert individual trades into candlestick format
- **Performance**: Pre-computed during refresh, O(log n) queries with indexes

## Testing Strategy
- **Unit Tests**: N/A (SQL migration)
- **Integration Tests**: Test view creation and query performance
- **E2E Tests**: Test simulation using trade view
- **Performance Tests**: Measure refresh time and query performance

## Deployment Plan
- **Pre-Deployment**: Verify `kalshi.trades` table has data
- **Deployment Steps**: Run migration: `psql "$DATABASE_URL" -f db/migrations/033_derived_snapshot_features_trade_v1.sql`
- **Post-Deployment**: Test view creation, verify indexes, test queries
- **Rollback Plan**: `DROP MATERIALIZED VIEW IF EXISTS derived.snapshot_features_trade_v1 CASCADE;`

## Risk Assessment
- **Technical Risks**: 
  - Refresh time too long - Mitigation: Optimize aggregation query, use CONCURRENT refresh
  - Bid/ask estimation accuracy - Mitigation: Conservative spread model, validate against candlestick data
- **Business Risks**: None
- **Resource Risks**: Storage growth - Mitigation: Monitor storage, consider partitioning

## Success Metrics
- **Technical**: View refresh <30 minutes, query <100ms per game, bid/ask error <2 cents
- **Business**: Simulation can use 1-second resolution
- **Sprint**: All stories completed, quality gates pass

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] Migration file created and tested
- [ ] Indexes created and validated
- [ ] Simulation updated to use trade view
- [ ] Testing and validation complete
- [ ] Documentation updated
- [ ] Quality gates pass



