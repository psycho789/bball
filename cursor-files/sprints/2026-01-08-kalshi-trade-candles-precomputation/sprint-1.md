# Sprint 1: Kalshi Trade Candles Precomputation for MV Performance

**Date**: Thu Jan  8 03:03:00 UTC 2026  
**Sprint Duration**: 5-7 days (20-25 hours total)  
**Sprint Goal**: Optimize materialized view `derived.snapshot_features_trade_v1` refresh performance by precomputing Kalshi trade candles into a physical fact table (`derived.kalshi_trade_candles`), enabling MV refresh to complete in single-digit seconds (target: <10 seconds for 10-game test set) instead of re-aggregating raw trades each refresh  
**Current Status**: MV query re-aggregates ~470,655 raw trades from `kalshi.trades` into per-second candles during each refresh, causing slow refresh times. Timeline-based as-of join logic processes large intermediate datasets with significant "Rows Removed by Join Filter" overhead  
**Target Status**: MV query reads precomputed candles from `derived.kalshi_trade_candles` fact table via indexed lookups, eliminating raw trade scans. Incremental refresh function updates candles using watermark tracking. MV refresh completes in <10 seconds for 10-game test set  
**Team Size**: 1  
**Sprint Lead**: AI Assistant  

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
- **DO modify database** - CREATE TABLE, CREATE FUNCTION, CREATE MATERIALIZED VIEW are part of sprint plan
- **DO NOT modify existing views** - only refactor MV query to read from new fact table
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
- **Business Driver**: Materialized view refresh currently re-aggregates raw trades each refresh, causing slow refresh times that limit refresh frequency and increase data staleness risk. Users need faster access to updated simulation data for 1-second resolution trading.
- **Success Criteria**: MV refresh completes in <10 seconds for 10-game test set (down from current ~30+ seconds), enabling frequent refreshes and reducing data staleness. Precomputed candles enable incremental updates via watermark tracking.
- **Stakeholders**: Data analysts and simulation users who depend on timely updated materialized view data
- **Timeline Constraints**: None (optimization sprint)

### Technical Context
- **Current System State**: Migration file `033_derived_snapshot_features_trade_v1.sql` contains query that scans `kalshi.trades` table (~470,655 rows for 10 games) and aggregates into per-second candles during each MV refresh. Timeline-based as-of join processes large intermediate datasets.
- **Target System State**: New fact table `derived.kalshi_trade_candles` stores precomputed candles with incremental refresh via `derived.refresh_kalshi_trade_candles()` function. Watermark table `derived.kalshi_trade_watermarks` tracks incremental ingestion. MV query refactored to read from fact table instead of raw trades. MV refresh completes in <10 seconds.
- **Architecture Impact**: New fact table and refresh function added. MV query refactored but output columns and semantics unchanged.
- **Integration Points**: Materialized view is used by simulation endpoints and analysis scripts. Refresh function must be called before MV refresh.

### Sprint Scope
- **In Scope**: 
  - Create `derived.kalshi_trade_candles` fact table with indexes
  - Create `derived.kalshi_trade_watermarks` watermark table
  - Create `derived.refresh_kalshi_trade_candles()` refresh function with incremental logic
  - Refactor MV query to read from fact table
  - Create verification scripts with EXPLAIN ANALYZE
  - Performance testing and validation
  - Documentation updates
- **Out of Scope**: 
  - Optional spread fact table (`derived.kalshi_spread_1m`) - deferred unless evidence shows it's needed
  - Application code changes
  - Changes to existing trade aggregation logic semantics
- **Assumptions**: 
  - Server has sufficient storage for fact table (estimated ~10-50MB per game)
  - PostgreSQL version supports required features (window functions, ON CONFLICT)
  - Query correctness can be validated via result comparison
  - Season label can be derived via game_id join if not on trades table
- **Constraints**: 
  - Must maintain query correctness (same output as original)
  - Must not break existing materialized view dependencies
  - Must preserve deterministic open/close ordering using (created_time, trade_id)

## Sprint Phases

### Phase 1: Schema Inspection and Fact Table Design (Duration: 3-4 hours)
**Objective**: Inspect existing schema to understand data types and relationships, then design and create fact table and watermark table with proper indexes
**Dependencies**: None
**Deliverables**: Fact table and watermark table created with indexes, schema documentation

### Phase 2: Refresh Function Implementation (Duration: 6-8 hours)
**Objective**: Implement incremental refresh function with watermark tracking, deterministic OHLCV computation, and proper bucket assignment
**Dependencies**: Must complete Phase 1 successfully
**Deliverables**: Refresh function created and tested on 10-game set

### Phase 3: MV Query Refactoring (Duration: 4-5 hours)
**Objective**: Refactor MV query to read from fact table instead of raw trades, maintaining all output columns and semantics
**Dependencies**: Must complete Phase 2 successfully
**Deliverables**: Refactored MV query that reads from fact table

### Phase 4: Validation and Performance Testing (Duration: 3-4 hours)
**Objective**: Validate correctness, measure performance improvements, and create verification scripts
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Performance test results, verification scripts, before/after comparison

### Phase 5: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 4 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Schema Inspection and Fact Table Creation
**Priority**: Critical (business justification: Foundation for all other work)
**Estimated Time**: 3-4 hours (1 hour inspection + 2-3 hours table creation)
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Inspect Existing Schema
- **ID**: S1-E1-S1
- **Type**: Research
- **Priority**: Critical (must understand schema before creating tables)
- **Estimate**: 1 hour (30 min inspection + 30 min documentation)
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: None
- **Files to Create**: `db/logs/033_schema_inspection.txt` (inspection results)
- **Dependencies**: PostgreSQL database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `\d+ kalshi.trades` output saved to `db/logs/033_schema_inspection.txt` showing column names, types, constraints
  - [ ] `\d+ kalshi.markets_with_games` output saved showing structure and relationships
  - [ ] `\d+ espn.probabilities_raw_items` output saved showing structure
  - [ ] `\d+ espn.scoreboard_games` output saved showing structure
  - [ ] Query executed to confirm `trade_id` type: `SELECT pg_typeof(trade_id) FROM kalshi.trades LIMIT 1;`
  - [ ] Query executed to confirm `created_time` type: `SELECT pg_typeof(created_time) FROM kalshi.trades LIMIT 1;`
  - [ ] Query executed to check if `season_label` exists on `kalshi.trades`: `SELECT column_name FROM information_schema.columns WHERE table_schema='kalshi' AND table_name='trades' AND column_name='season_label';`
  - [ ] Sample row from `kalshi.trades` examined to understand price_cents derivation logic
  - [ ] Documentation created summarizing schema findings

- **Technical Context**:
  - **Current State**: Need to understand exact schema before creating fact table
  - **Required Changes**: Inspect schema and document findings
  - **Integration Points**: Schema inspection informs fact table design
  - **Data Structures**: Understanding existing tables
  - **API Contracts**: N/A

- **Implementation Steps**:
  1. Connect to database and inspect schema:
     ```bash
     source .env
     psql "$DATABASE_URL" -c "\d+ kalshi.trades" > db/logs/033_schema_inspection.txt 2>&1
     psql "$DATABASE_URL" -c "\d+ kalshi.markets_with_games" >> db/logs/033_schema_inspection.txt 2>&1
     psql "$DATABASE_URL" -c "\d+ espn.probabilities_raw_items" >> db/logs/033_schema_inspection.txt 2>&1
     psql "$DATABASE_URL" -c "\d+ espn.scoreboard_games" >> db/logs/033_schema_inspection.txt 2>&1
     ```
  2. Check data types:
     ```bash
     psql "$DATABASE_URL" -c "SELECT pg_typeof(trade_id) FROM kalshi.trades LIMIT 1;" >> db/logs/033_schema_inspection.txt 2>&1
     psql "$DATABASE_URL" -c "SELECT pg_typeof(created_time) FROM kalshi.trades LIMIT 1;" >> db/logs/033_schema_inspection.txt 2>&1
     ```
  3. Check for season_label:
     ```bash
     psql "$DATABASE_URL" -c "SELECT column_name FROM information_schema.columns WHERE table_schema='kalshi' AND table_name='trades' AND column_name='season_label';" >> db/logs/033_schema_inspection.txt 2>&1
     ```
  4. Examine sample row:
     ```bash
     psql "$DATABASE_URL" -c "SELECT trade_id, ticker, created_time, yes_price, no_price, count FROM kalshi.trades LIMIT 5;" >> db/logs/033_schema_inspection.txt 2>&1
     ```

- **Validation Steps**:
  1. Verify inspection file contains all required outputs
  2. Verify data types are documented
  3. Verify season_label existence is documented
  4. Verify sample data is documented

- **Definition of Done**: 
  - [ ] All schema inspection outputs saved to log file
  - [ ] Data types confirmed and documented
  - [ ] Season label derivation path confirmed
  - [ ] Sample data examined and documented

- **Rollback Plan**: N/A (inspection only)

- **Risk Assessment**: 
  - **Risk**: Schema differs from assumptions
  - **Probability**: Medium
  - **Mitigation**: Inspect actual schema before proceeding

- **Success Metrics**:
  - **Quality**: Complete schema documentation
  - **Functionality**: All required schema information gathered

#### Story 1.2: Create Fact Table and Watermark Table
- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: Critical (foundation for all other work)
- **Estimate**: 2-3 hours (1 hour design + 1-2 hours implementation)
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1 completed
- **Files to Modify**: None
- **Files to Create**: `db/migrations/034_kalshi_trade_candles_fact_table.sql` (fact table, watermark table, indexes)
- **Dependencies**: Schema inspection results

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Migration file `db/migrations/034_kalshi_trade_candles_fact_table.sql` exists
  - [ ] Fact table `derived.kalshi_trade_candles` created with all required columns:
    - `season_label TEXT`
    - `game_id TEXT`
    - `ticker TEXT`
    - `kalshi_team_side TEXT CHECK (kalshi_team_side IN ('home','away'))`
    - `bucket_seconds INT NOT NULL`
    - `bucket_ts TIMESTAMPTZ NOT NULL`
    - `bucket_minute_ts TIMESTAMPTZ NOT NULL`
    - `price_open_cents NUMERIC`
    - `price_high_cents NUMERIC`
    - `price_low_cents NUMERIC`
    - `price_close_cents NUMERIC`
    - `price_mean_cents NUMERIC`
    - `volume BIGINT`
    - `first_trade_time TIMESTAMPTZ`
    - `last_trade_time TIMESTAMPTZ`
    - `last_trade_id` (type matches `kalshi.trades.trade_id`)
  - [ ] Primary key on `(season_label, game_id, ticker, kalshi_team_side, bucket_seconds, bucket_ts)`
  - [ ] Index on `(game_id, ticker, kalshi_team_side, bucket_seconds, bucket_ts)`
  - [ ] Index on `(game_id, ticker, kalshi_team_side, bucket_seconds, bucket_minute_ts)`
  - [ ] Index on `(ticker, bucket_ts)` for incremental loads
  - [ ] Watermark table `derived.kalshi_trade_watermarks` created with columns:
    - `season_label TEXT`
    - `ticker TEXT`
    - `last_seen_created_time TIMESTAMPTZ`
    - `last_seen_trade_id` (type matches `kalshi.trades.trade_id`)
    - `updated_at TIMESTAMPTZ DEFAULT now()`
  - [ ] Primary key on `(season_label, ticker)`
  - [ ] Migration applies cleanly: `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run`
  - [ ] Tables created successfully: `psql "$DATABASE_URL" -c "\d+ derived.kalshi_trade_candles"` and `psql "$DATABASE_URL" -c "\d+ derived.kalshi_trade_watermarks"`

- **Technical Context**:
  - **Current State**: No fact table exists
  - **Required Changes**: Create fact table and watermark table with proper schema
  - **Integration Points**: Fact table will be used by MV query and refresh function
  - **Data Structures**: New tables with specific schema
  - **API Contracts**: N/A

- **Implementation Steps**:
  1. Create migration file with fact table:
     ```sql
     CREATE TABLE derived.kalshi_trade_candles (
         season_label TEXT NOT NULL,
         game_id TEXT NOT NULL,
         ticker TEXT NOT NULL,
         kalshi_team_side TEXT NOT NULL CHECK (kalshi_team_side IN ('home','away')),
         bucket_seconds INT NOT NULL,
         bucket_ts TIMESTAMPTZ NOT NULL,
         bucket_minute_ts TIMESTAMPTZ NOT NULL,
         price_open_cents NUMERIC,
         price_high_cents NUMERIC,
         price_low_cents NUMERIC,
         price_close_cents NUMERIC,
         price_mean_cents NUMERIC,
         volume BIGINT,
         first_trade_time TIMESTAMPTZ,
         last_trade_time TIMESTAMPTZ,
         last_trade_id TEXT,  -- Type will be confirmed from inspection
         PRIMARY KEY (season_label, game_id, ticker, kalshi_team_side, bucket_seconds, bucket_ts)
     );
     ```
  2. Create indexes:
     ```sql
     CREATE INDEX idx_kalshi_trade_candles_game_ticker_side_bucket_ts 
         ON derived.kalshi_trade_candles (game_id, ticker, kalshi_team_side, bucket_seconds, bucket_ts);
     
     CREATE INDEX idx_kalshi_trade_candles_game_ticker_side_bucket_minute_ts 
         ON derived.kalshi_trade_candles (game_id, ticker, kalshi_team_side, bucket_seconds, bucket_minute_ts);
     
     CREATE INDEX idx_kalshi_trade_candles_ticker_bucket_ts 
         ON derived.kalshi_trade_candles (ticker, bucket_ts);
     ```
  3. Create watermark table:
     ```sql
     CREATE TABLE derived.kalshi_trade_watermarks (
         season_label TEXT NOT NULL,
         ticker TEXT NOT NULL,
         last_seen_created_time TIMESTAMPTZ NOT NULL,
         last_seen_trade_id TEXT NOT NULL,  -- Type will be confirmed from inspection
         updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
         PRIMARY KEY (season_label, ticker)
     );
     ```
  4. Test migration:
     ```bash
     source .env
     python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run
     ```

- **Validation Steps**:
  1. Verify migration file syntax is valid
  2. Verify tables created successfully
  3. Verify indexes created successfully
  4. Verify constraints applied correctly

- **Definition of Done**: 
  - [ ] Migration file created with complete schema
  - [ ] Tables created successfully
  - [ ] Indexes created successfully
  - [ ] Constraints applied correctly
  - [ ] Migration applies cleanly

- **Rollback Plan**: 
  - Drop tables if issues found: `DROP TABLE IF EXISTS derived.kalshi_trade_candles CASCADE; DROP TABLE IF EXISTS derived.kalshi_trade_watermarks CASCADE;`
  - Fix migration file and reapply

- **Risk Assessment**: 
  - **Risk**: Data types don't match existing schema
  - **Probability**: Medium
  - **Mitigation**: Use schema inspection results to confirm types

- **Success Metrics**:
  - **Quality**: Tables created with correct schema
  - **Functionality**: Migration applies cleanly

### Epic 2: Refresh Function Implementation
**Priority**: Critical (business justification: Enables incremental updates and precomputation)
**Estimated Time**: 6-8 hours (4-5 hours implementation + 2-3 hours testing)
**Dependencies**: Epic 1
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Implement Refresh Function with Incremental Logic
- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: Critical (core functionality)
- **Estimate**: 4-5 hours (3 hours implementation + 1-2 hours testing)
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S2 completed
- **Files to Modify**: None
- **Files to Create**: `db/migrations/035_refresh_kalshi_trade_candles_function.sql` (refresh function)
- **Dependencies**: Fact table and watermark table must exist

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Function `derived.refresh_kalshi_trade_candles(season_label TEXT, bucket_seconds INT, game_ids TEXT[] DEFAULT NULL)` created
  - [ ] Function implements incremental logic:
    - Reads watermark for each ticker
    - Pulls only trades where `(created_time, trade_id) > (watermark.last_seen_created_time, watermark.last_seen_trade_id)`
    - If `game_ids` provided, restricts to those games/tickers only
  - [ ] Function correctly derives `price_cents`:
    - `yes_price` → `yes_price`
    - `no_price` → `(100 - no_price)`
    - Ignores rows where both are null
  - [ ] Function correctly assigns buckets:
    - For 1 second: `bucket_ts = date_trunc('second', created_time)`
    - For N seconds: `bucket_ts = to_timestamp(floor(extract(epoch from created_time)/N)*N) at time zone 'UTC'`
  - [ ] Function computes OHLCV deterministically:
    - `open` = first by `(created_time ASC, trade_id ASC)`
    - `close` = last by `(created_time DESC, trade_id DESC)`
    - `high/low` = max/min `price_cents`
    - `volume` = sum(`count`)
    - `mean` = sum(`price_cents*count`)/sum(`count`)
  - [ ] Function upserts into candles table using `INSERT ... ON CONFLICT ... DO UPDATE`
  - [ ] Function updates watermark after successful upsert
  - [ ] Function handles season_label derivation if not on trades table (via game_id join)
  - [ ] Function tested on 10-game set: `SELECT derived.refresh_kalshi_trade_candles('2025-26', 1, ARRAY['401809234','401809235',...]);`
  - [ ] Function completes successfully without errors
  - [ ] Candle counts verified: `SELECT COUNT(*) FROM derived.kalshi_trade_candles WHERE season_label='2025-26' AND bucket_seconds=1;`

- **Technical Context**:
  - **Current State**: No refresh function exists
  - **Required Changes**: Create function with incremental logic, deterministic OHLCV, watermark tracking
  - **Integration Points**: Function will be called before MV refresh
  - **Data Structures**: Function reads from `kalshi.trades`, writes to `derived.kalshi_trade_candles` and `derived.kalshi_trade_watermarks`
  - **API Contracts**: Function signature: `derived.refresh_kalshi_trade_candles(season_label TEXT, bucket_seconds INT, game_ids TEXT[] DEFAULT NULL)`

- **Implementation Steps**:
  1. Create function with incremental logic:
     ```sql
     CREATE OR REPLACE FUNCTION derived.refresh_kalshi_trade_candles(
         p_season_label TEXT,
         p_bucket_seconds INT,
         p_game_ids TEXT[] DEFAULT NULL
     )
     RETURNS TABLE(
         tickers_processed INT,
         candles_inserted BIGINT,
         candles_updated BIGINT
     )
     LANGUAGE plpgsql
     AS $$
     DECLARE
         v_ticker TEXT;
         v_watermark_record RECORD;
         v_candles_inserted BIGINT := 0;
         v_candles_updated BIGINT := 0;
         v_tickers_processed INT := 0;
     BEGIN
         -- Implementation with incremental logic, OHLCV computation, upsert, watermark update
     END;
     $$;
     ```
  2. Implement incremental trade selection logic
  3. Implement bucket assignment logic
  4. Implement deterministic OHLCV computation
  5. Implement upsert logic
  6. Implement watermark update logic
  7. Test on 10-game set

- **Validation Steps**:
  1. Verify function created successfully: `\df derived.refresh_kalshi_trade_candles`
  2. Run function on 10-game set and verify no errors
  3. Verify candle counts match expected values
  4. Verify watermark updated correctly
  5. Verify determinism: run function twice, verify same open/close values

- **Definition of Done**: 
  - [ ] Function created with correct signature
  - [ ] Incremental logic implemented correctly
  - [ ] OHLCV computation is deterministic
  - [ ] Function tested on 10-game set
  - [ ] Watermark tracking works correctly

- **Rollback Plan**: 
  - Drop function if issues: `DROP FUNCTION IF EXISTS derived.refresh_kalshi_trade_candles(TEXT, INT, TEXT[]);`
  - Fix function and recreate

- **Risk Assessment**: 
  - **Risk**: Incremental logic misses trades
  - **Probability**: Medium
  - **Mitigation**: Test watermark logic thoroughly, verify determinism
  - **Risk**: OHLCV computation not deterministic
  - **Probability**: Medium
  - **Mitigation**: Use explicit ordering with (created_time, trade_id)

- **Success Metrics**:
  - **Quality**: Function implements all required logic correctly
  - **Functionality**: Function completes successfully on 10-game set
  - **Performance**: Function completes in reasonable time (<5 minutes for 10 games)

#### Story 2.2: Populate Initial Candles for 10-Game Test Set
- **ID**: S1-E2-S2
- **Type**: Configuration
- **Priority**: High (needed for MV refactoring testing)
- **Estimate**: 1 hour (30 min execution + 30 min validation)
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1 completed
- **Files to Modify**: None
- **Files to Create**: `db/migrations/036_populate_initial_candles_10_games.sql` (initial population script)
- **Dependencies**: Refresh function must work correctly

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Script `db/migrations/036_populate_initial_candles_10_games.sql` exists
  - [ ] Script calls refresh function for 10-game set: `SELECT derived.refresh_kalshi_trade_candles('2025-26', 1, ARRAY['401809234','401809235',...]);`
  - [ ] Script executes successfully without errors
  - [ ] Candle counts verified: `SELECT COUNT(*) FROM derived.kalshi_trade_candles WHERE season_label='2025-26' AND bucket_seconds=1;`
  - [ ] Sample candles examined: `SELECT * FROM derived.kalshi_trade_candles WHERE season_label='2025-26' AND bucket_seconds=1 LIMIT 10;`
  - [ ] Watermarks verified: `SELECT COUNT(*) FROM derived.kalshi_trade_watermarks WHERE season_label='2025-26';`

- **Technical Context**:
  - **Current State**: Fact table empty
  - **Required Changes**: Populate initial candles for testing
  - **Integration Points**: Populated candles will be used by MV refactoring
  - **Data Structures**: N/A
  - **API Contracts**: N/A

- **Implementation Steps**:
  1. Create script that calls refresh function for 10-game set
  2. Execute script
  3. Verify candle counts
  4. Verify sample data

- **Validation Steps**:
  1. Verify script executes successfully
  2. Verify candle counts match expected values
  3. Verify sample data looks correct
  4. Verify watermarks created

- **Definition of Done**: 
  - [ ] Script created and executed
  - [ ] Candles populated for 10-game set
  - [ ] Data validated

- **Rollback Plan**: 
  - Truncate tables if issues: `TRUNCATE derived.kalshi_trade_candles; TRUNCATE derived.kalshi_trade_watermarks;`
  - Fix script and re-run

- **Risk Assessment**: Low risk (data population only)

- **Success Metrics**:
  - **Quality**: Candles populated correctly
  - **Functionality**: Data ready for MV refactoring

### Epic 3: MV Query Refactoring
**Priority**: Critical (business justification: Enables fast MV refresh)
**Estimated Time**: 4-5 hours (3 hours implementation + 1-2 hours testing)
**Dependencies**: Epic 2
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Refactor MV Query to Read from Fact Table
- **ID**: S1-E3-S1
- **Type**: Refactor
- **Priority**: Critical (core optimization)
- **Estimate**: 3 hours (2 hours implementation + 1 hour testing)
- **Phase**: Phase 3
- **Prerequisites**: S1-E2-S2 completed (candles populated)
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql` (refactor trade aggregation CTEs)
- **Files to Create**: None
- **Dependencies**: Fact table must be populated

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] MV query no longer scans `kalshi.trades` for trade aggregation (verified via EXPLAIN ANALYZE)
  - [ ] `candle_stream` CTE reads from `derived.kalshi_trade_candles` instead of aggregating raw trades
  - [ ] Join to spreads uses `bucket_minute_ts` for equality join (not join filter)
  - [ ] Existing "as-of / carry-forward" matching logic preserved
  - [ ] All output columns unchanged (verified via `SELECT * FROM derived.snapshot_features_trade_v1 LIMIT 1;`)
  - [ ] Column semantics unchanged (verified via comparison query)
  - [ ] EXPLAIN ANALYZE shows index scans on fact table (not sequential scans on trades)
  - [ ] EXPLAIN ANALYZE shows no massive "Rows Removed by Join Filter" explosions

- **Technical Context**:
  - **Current State**: MV query scans `kalshi.trades` and aggregates into candles
  - **Required Changes**: Refactor to read from `derived.kalshi_trade_candles`
  - **Integration Points**: MV is used by simulation endpoints
  - **Data Structures**: MV output unchanged
  - **API Contracts**: MV output unchanged

- **Implementation Steps**:
  1. Identify CTEs that scan `kalshi.trades` (likely `trade_base`, `trade_agg_core`, `trade_aggregated`)
  2. Refactor `candle_stream` (or equivalent) to read from `derived.kalshi_trade_candles`
  3. Update join conditions to use `bucket_minute_ts` for spread joins
  4. Preserve existing timeline-based as-of join logic
  5. Test on 10-game set

- **Validation Steps**:
  1. Verify EXPLAIN ANALYZE shows no `kalshi.trades` scans in trade aggregation
  2. Verify EXPLAIN ANALYZE shows index scans on fact table
  3. Verify output columns unchanged
  4. Verify output semantics unchanged (comparison query)

- **Definition of Done**: 
  - [ ] MV query refactored to read from fact table
  - [ ] No raw trade scans in MV query
  - [ ] Output columns and semantics unchanged
  - [ ] EXPLAIN ANALYZE shows correct execution plan

- **Rollback Plan**: 
  - Revert to original MV query if issues found
  - Document issues for investigation

- **Risk Assessment**: 
  - **Risk**: Output columns or semantics change
  - **Probability**: Medium
  - **Mitigation**: Careful refactoring, thorough testing, comparison queries

- **Success Metrics**:
  - **Performance**: MV refresh time: ~30s → <10s (67% improvement)
  - **Quality**: Output unchanged (100% match)
  - **Functionality**: MV works correctly

### Epic 4: Validation and Performance Testing
**Priority**: Critical (business justification: Ensure optimizations work correctly)
**Estimated Time**: 3-4 hours (2 hours testing + 1-2 hours analysis)
**Dependencies**: Epic 3
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Create Verification Scripts
- **ID**: S1-E4-S1
- **Type**: Testing
- **Priority**: Critical (validation)
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: S1-E3-S1 completed
- **Files to Modify**: None
- **Files to Create**: `db/migrations/037_verify_candles_performance.sql` (verification script)
- **Dependencies**: MV refactored and working

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Verification script `db/migrations/037_verify_candles_performance.sql` exists
  - [ ] Script includes row count queries:
    - `SELECT COUNT(*) FROM derived.kalshi_trade_candles WHERE season_label='2025-26' AND bucket_seconds=1;`
    - `SELECT COUNT(*) FROM derived.snapshot_features_trade_v1;`
  - [ ] Script includes sample query for 10 games
  - [ ] Script includes EXPLAIN (ANALYZE, BUFFERS, SETTINGS) for MV creation/refresh
  - [ ] Script includes sanity checks on determinism (same open/close on rerun)
  - [ ] Script executes successfully and produces output

- **Technical Context**:
  - **Current State**: Need verification scripts for validation
  - **Required Changes**: Create comprehensive verification script
  - **Integration Points**: Script validates sprint work
  - **Data Structures**: N/A
  - **API Contracts**: N/A

- **Implementation Steps**:
  1. Create verification script with row counts
  2. Add sample queries
  3. Add EXPLAIN ANALYZE queries
  4. Add determinism checks
  5. Test script execution

- **Validation Steps**:
  1. Verify script executes successfully
  2. Verify all queries produce output
  3. Verify EXPLAIN ANALYZE output is captured

- **Definition of Done**: 
  - [ ] Verification script created
  - [ ] All queries execute successfully
  - [ ] Output captured

- **Rollback Plan**: N/A (testing only)

- **Risk Assessment**: Low risk (testing only)

- **Success Metrics**:
  - **Quality**: Complete verification script
  - **Functionality**: Script validates sprint work

#### Story 4.2: Performance Testing and Comparison
- **ID**: S1-E4-S2
- **Type**: Testing
- **Priority**: Critical (validate performance improvements)
- **Estimate**: 2 hours (1 hour testing + 1 hour analysis)
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S1 completed
- **Files to Modify**: None
- **Files to Create**: `db/logs/037_performance_comparison.txt` (before/after comparison)
- **Dependencies**: Verification scripts and MV refactored

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Before performance baseline captured (if available) or documented as "N/A - new optimization"
  - [ ] After performance measured: MV refresh time for 10-game set
  - [ ] EXPLAIN ANALYZE output saved showing:
    - No scans of `kalshi.trades` inside MV query (except maybe tiny existence checks)
    - `candle_stream` reads from `derived.kalshi_trade_candles` via index scans
    - No massive "Rows Removed by Join Filter" explosions
  - [ ] Performance comparison table created:
    - Before: ~30+ seconds (or N/A)
    - After: <10 seconds (target)
  - [ ] Exact commands and verbatim outputs documented

- **Technical Context**:
  - **Current State**: Need to measure performance improvements
  - **Required Changes**: Run performance tests and document results
  - **Integration Points**: Performance metrics validate sprint success
  - **Data Structures**: N/A
  - **API Contracts**: N/A

- **Implementation Steps**:
  1. Run EXPLAIN ANALYZE on MV creation for 10-game set
  2. Measure execution time
  3. Analyze execution plan
  4. Create comparison table
  5. Document exact commands and outputs

- **Validation Steps**:
  1. Verify performance meets target (<10 seconds)
  2. Verify execution plan shows correct optimizations
  3. Verify no raw trade scans
  4. Verify index usage

- **Definition of Done**: 
  - [ ] Performance tested and documented
  - [ ] Execution plan analyzed
  - [ ] Comparison table created
  - [ ] Exact commands and outputs documented

- **Rollback Plan**: N/A (testing only)

- **Risk Assessment**: 
  - **Risk**: Performance doesn't meet target
  - **Probability**: Medium
  - **Mitigation**: Investigate bottlenecks, consider additional optimizations

- **Success Metrics**:
  - **Performance**: MV refresh time: ~30s → <10s (67% improvement)
  - **Quality**: Execution plan shows correct optimizations

### Epic 5: Documentation Update
**Priority**: High (business justification: Document optimizations for future reference)
**Estimated Time**: 1-2 hours
**Dependencies**: Epic 4
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 5.1: Update Migration File Comments
- **ID**: S1-E5-S1
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 5
- **Prerequisites**: S1-E4-S2 completed
- **Files to Modify**: `db/migrations/033_derived_snapshot_features_trade_v1.sql`, `db/migrations/034_kalshi_trade_candles_fact_table.sql`, `db/migrations/035_refresh_kalshi_trade_candles_function.sql`
- **Files to Create**: None
- **Dependencies**: All optimizations complete and validated

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Migration file header comments updated with optimization details
  - [ ] Fact table comments explain purpose and usage
  - [ ] Refresh function comments explain incremental logic and usage
  - [ ] MV query comments explain fact table usage
  - [ ] Performance characteristics documented in comments

- **Technical Context**:
  - **Current State**: Comments describe original implementation
  - **Required Changes**: Update comments to reflect optimizations
  - **Integration Points**: Comments help future developers understand optimizations
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Update header comments with optimization summary
  2. Update fact table comments
  3. Update refresh function comments
  4. Update MV query comments
  5. Add performance notes

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

### Epic 6: Quality Gate Validation
**Priority**: Critical (business justification: Ensure all work meets quality standards)
**Estimated Time**: 1-2 hours
**Dependencies**: All other epics
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 6.1: Quality Gate Validation
- **ID**: S1-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] Fact table and watermark table created successfully
  - [ ] Refresh function works correctly on 10-game set
  - [ ] MV query refactored to read from fact table
  - [ ] EXPLAIN ANALYZE shows no raw trade scans in MV query
  - [ ] MV refresh completes in <10 seconds for 10-game set
  - [ ] Output columns and semantics unchanged (100% match)
  - [ ] Documentation updated
  - [ ] All previous story acceptance criteria verified

- **Technical Context**:
  - **Current State**: All optimizations implemented and tested
  - **Required Changes**: Final validation of all quality gates
  - **Integration Points**: Quality gates ensure production readiness
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. Verify fact table and watermark table exist
  2. Verify refresh function works
  3. Verify MV query refactored correctly
  4. Verify performance meets target
  5. Verify output unchanged
  6. Verify documentation complete

- **Validation Steps**:
  1. All quality gates pass
  2. All acceptance criteria met
  3. Ready for production

- **Definition of Done**: 
  - [ ] All quality gates pass
  - [ ] All acceptance criteria met
  - [ ] Ready for production

- **Rollback Plan**: Address any failing quality gates before completion

- **Risk Assessment**: Low risk (final validation)

- **Success Metrics**:
  - **Quality**: 100% quality gate pass rate
  - **Functionality**: All optimizations working correctly

### Epic 7: Sprint Completion and Archive
**Priority**: Critical (business justification: Complete sprint properly)
**Estimated Time**: 1 hour
**Dependencies**: Quality Gate Validation
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 7.1: Sprint Completion and Archive
- **ID**: S1-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 5
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created with performance improvements documented
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Performance metrics compared: before vs. after
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

#### Design Pattern: Fact Table Pattern

**Pattern Name**: Fact Table Pattern (Star Schema)  
**Category**: Architectural  
**Intent**: Precompute aggregated data (candles) into a physical fact table to avoid re-aggregation during queries

**Implementation**: 
- **File**: `db/migrations/034_kalshi_trade_candles_fact_table.sql`
- **Code**: Fact table `derived.kalshi_trade_candles` stores precomputed OHLCV candles
- **Changes**: New fact table added, MV query refactored to read from fact table

**Benefits**:
- Eliminates re-aggregation overhead during MV refresh
- Enables incremental updates via watermark tracking
- Provides indexed access for fast lookups
- Reduces query complexity

**Trade-offs**:
- Additional storage required (~10-50MB per game)
- Requires refresh function to keep data current
- Adds complexity with watermark tracking

**Why This Pattern**: Precomputation eliminates the primary performance bottleneck (re-aggregating raw trades) while enabling incremental updates.

### Algorithm Analysis

#### Algorithm: Incremental Watermark-Based Refresh

**Algorithm Name**: Incremental Watermark-Based Refresh  
**Algorithm Type**: Data Processing Algorithm  
**Big O Notation**: 
- Time Complexity: O(n) where n = number of new trades since last refresh
- Space Complexity: O(1) watermark state + O(m) where m = new candles to insert/update

**Algorithm Description**:
- Tracks last processed trade per ticker using watermark table
- Selects only trades where `(created_time, trade_id) > (watermark.last_seen_created_time, watermark.last_seen_trade_id)`
- Aggregates new trades into candles
- Upserts candles into fact table
- Updates watermark after successful upsert

**Use Case**: Incrementally updating precomputed candles as new trades arrive

**Performance Characteristics**:
- **Best Case**: O(n) with small number of new trades, ~1-5 seconds for incremental refresh
- **Average Case**: O(n) with moderate number of new trades, ~5-10 seconds for incremental refresh
- **Worst Case**: O(n) with large number of new trades, ~10-30 seconds for incremental refresh
- **Memory Usage**: O(1) watermark state + O(m) new candles

**Why This Algorithm**: Enables efficient incremental updates without full re-aggregation, reducing refresh time from minutes to seconds.

**Design Decision**: Implement incremental refresh with watermark tracking

**Problem Statement**:
- Full re-aggregation of all trades is slow
- Most refreshes only need to process new trades since last refresh
- Need efficient way to track and process only new trades

**Project Scope**: Single sprint optimization, new fact table and refresh function

**Multiple Solution Analysis**:

**Option 1: Full Re-aggregation Each Refresh**
- **Design Pattern**: None
- **Algorithm**: Full table scan and aggregation
- **Implementation Complexity**: Low (current approach)
- **Maintenance Overhead**: Low
- **Scalability**: Poor (gets slower as data grows)
- **Cost-Benefit**: Low cost, low benefit (no improvement)
- **Over-Engineering Risk**: None
- **Rejected**: Doesn't solve performance problem

**Option 2: Incremental Refresh with Watermark Tracking (CHOSEN)**
- **Design Pattern**: Fact Table Pattern
- **Algorithm**: Incremental Watermark-Based Refresh
- **Implementation Complexity**: Medium (watermark tracking adds complexity)
- **Maintenance Overhead**: Medium (need to maintain watermarks)
- **Scalability**: Excellent (only processes new trades)
- **Cost-Benefit**: Medium cost, high benefit (67%+ improvement)
- **Over-Engineering Risk**: Low (appropriate for problem complexity)
- **Selected**: Provides best performance improvement with reasonable complexity

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 6-8 hours (medium complexity)
- **Learning Curve**: 1-2 hours (standard PostgreSQL patterns)
- **Configuration Effort**: 1 hour (table and function creation)

**Maintenance Cost**:
- **Monitoring**: 0.5 hours/month (check watermark correctness)
- **Updates**: 1 hour/month (function improvements if needed)
- **Debugging**: 1 hour/incident (standard debugging)

**Performance Benefit**:
- **Execution Time**: 67%+ improvement (30s → <10s)
- **Throughput**: N/A (one-time materialized view creation)
- **Resource Efficiency**: Reduced CPU usage, increased storage usage

**Maintainability Benefit**:
- **Code Quality**: Improved (separated concerns, fact table pattern)
- **Developer Productivity**: Improved (faster refresh enables more frequent updates)
- **System Reliability**: Improved (faster execution reduces timeout risk)

**Risk Cost**:
- **Watermark Risk**: Low risk, mitigated by thorough testing
- **Correctness Risk**: Medium risk, mitigated by comparison queries

**Over-Engineering Prevention**:
- **Problem Complexity**: Medium (performance optimization with correctness requirements)
- **Solution Complexity**: Medium (fact table + refresh function)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Fact table pattern scales well

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Medium complexity for single sprint
- **Team Capability**: ✅ Standard PostgreSQL knowledge
- **Timeline Constraints**: ✅ Fits in single sprint
- **Future Growth**: ✅ Better scalability
- **Technical Debt**: ✅ Reduces technical debt (enables better performance)

**Chosen Solution**: Incremental refresh with watermark tracking
- Implementation: Fact table + refresh function + watermark table
- Configuration: Standard PostgreSQL tables and functions
- Integration: MV query reads from fact table, refresh function called before MV refresh

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: 67%+ improvement in MV refresh time (30s → <10s)
- **Scalability**: Only processes new trades, scales well
- **Maintainability**: Separated concerns, fact table pattern
- **Reliability**: Faster execution reduces timeout risk

**Cons**:
- **Complexity**: Watermark tracking adds complexity
- **Storage**: Additional storage required for fact table
- **Maintenance**: Need to maintain refresh function and watermarks

**Risk Assessment**:
- **Watermark Risk**: Low risk, mitigated by thorough testing
- **Correctness Risk**: Medium risk, mitigated by comparison queries
- **Performance Risk**: Low risk, well-understood optimization

**Trade-off Analysis**:
- **Sacrificed**: Additional storage and complexity
- **Gained**: 67%+ performance improvement, better scalability
- **Net Benefit**: Significant performance gain with reasonable cost
- **Over-Engineering Risk**: Low (appropriate solution)

## Testing Strategy

### Testing Approach
- **Unit Tests**: N/A (SQL migration files)
- **Integration Tests**: Refresh function execution, MV creation and query execution
- **E2E Tests**: N/A (no end-to-end flow)
- **Performance Tests**: EXPLAIN ANALYZE with timing measurements

### Performance Testing
- **Load Test**: Test refresh function with 10-game set
- **Stress Test**: Test refresh function with full dataset
- **Memory Test**: Monitor memory usage during execution

### Correctness Testing
- **Row Count Validation**: Compare row counts before/after optimization
- **Sample Data Validation**: Compare random sample of rows
- **Determinism Validation**: Verify same open/close on rerun

## Deployment Plan
- **Pre-Deployment**: 
  - Verify server has sufficient storage for fact table
  - Backup current materialized view (if exists)
  - Test optimizations in development environment
- **Deployment Steps**: 
  1. Run fact table migration
  2. Run refresh function migration
  3. Populate initial candles
  4. Run MV refactoring migration
  5. Monitor execution time and resource usage
  6. Validate results
- **Post-Deployment**: 
  - Verify fact table populated correctly
  - Verify MV refresh completes in <10 seconds
  - Verify performance improvements
  - Monitor for any issues
- **Rollback Plan**: 
  - Revert to original MV query if issues occur
  - Drop fact table and watermark table if needed
  - Restore materialized view from backup if needed

## Risk Assessment

### Technical Risks
- **Risk 1**: Watermark logic misses trades or processes duplicates
  - **Probability**: Medium
  - **Impact**: High (incorrect candles)
  - **Mitigation**: Thorough testing, verify determinism, comparison queries
  - **Contingency**: Full re-aggregation fallback option

- **Risk 2**: OHLCV computation not deterministic
  - **Probability**: Medium
  - **Impact**: High (inconsistent results)
  - **Mitigation**: Explicit ordering with (created_time, trade_id), test determinism
  - **Contingency**: Fix ordering logic

- **Risk 3**: MV refactoring changes output columns or semantics
  - **Probability**: Medium
  - **Impact**: High (breaks downstream systems)
  - **Mitigation**: Careful refactoring, thorough testing, comparison queries
  - **Contingency**: Revert to original MV query

- **Risk 4**: Performance doesn't meet target (<10 seconds)
  - **Probability**: Medium
  - **Impact**: Medium (optimization doesn't achieve goal)
  - **Mitigation**: Investigate bottlenecks, consider additional optimizations
  - **Contingency**: Accept current performance or implement additional optimizations

### Business Risks
- **Risk 1**: Optimizations don't provide expected performance improvement
  - **Probability**: Medium
  - **Impact**: Low (query still works, just not faster)
  - **Mitigation**: Set realistic expectations, measure baseline before optimizations
  - **Contingency**: Accept current performance if optimizations don't help

### Resource Risks
- **Risk 1**: Insufficient storage for fact table
  - **Probability**: Low (estimated ~10-50MB per game)
  - **Impact**: Medium (optimizations cannot be deployed)
  - **Mitigation**: Estimate storage requirements, check server storage
  - **Contingency**: Implement data retention policy if needed

## Success Metrics

### Technical Metrics
- **Execution Time**: <10 seconds for 10-game set (67%+ improvement from ~30s)
- **Refresh Function Time**: <5 minutes for 10-game set initial population
- **Incremental Refresh Time**: <10 seconds for incremental updates
- **Storage Usage**: <100MB for 10-game set candles
- **Index Usage**: EXPLAIN ANALYZE shows index scans on fact table

### Quality Metrics
- **Correctness**: 100% match with original query results
- **Determinism**: Same open/close values on rerun (100% match)
- **Code Quality**: Fact table pattern, clear separation of concerns
- **Documentation**: Complete and accurate

### Business Metrics
- **Refresh Frequency**: Can refresh more frequently (faster execution)
- **Data Staleness**: Reduced (faster refresh enables more frequent updates)
- **User Experience**: Faster access to updated simulation data

### Monitoring Strategy
- **Real-time Monitoring**: Log execution time for each refresh function call and MV refresh
- **Alert Thresholds**: 
  - MV refresh time > 15 seconds: Warning
  - MV refresh time > 30 seconds: Critical
  - Refresh function time > 10 minutes: Warning
  - Watermark inconsistencies detected: Critical
- **Reporting**: Weekly performance report comparing execution times

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (performance, correctness, determinism)

### Post-Sprint Quality Comparison
- **Performance**: Baseline ~30s → Target <10s (67%+ improvement)
- **Storage Usage**: Baseline 0MB → Target <100MB for 10-game set (acceptable increase)
- **Correctness**: 100% match maintained
- **Determinism**: 100% match on rerun maintained
- **Overall Assessment**: Performance significantly improved with maintained correctness

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation

**IMPORTANT**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

