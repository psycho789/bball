# Sprint 13 - Signal Improvement Foundation

**Date**: 2025-12-30  
**Sprint Duration**: 1-2 weeks (40-60 hours total)  
**Sprint Goal**: Build canonical snapshot dataset foundation and validate fee modeling correctness to enable signal improvement work  
**Current Status**: Planning Phase  
**Target Status**: Canonical snapshot dataset (`derived.snapshot_features_v1`) exists with all required features, fee modeling validated, ESPN odds inspected, and 2025-26 odds strategy decided  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/signal_improvement_next_steps_analysis.md`
- **Current Implementation**: 
  - `scripts/simulate_trading_strategy.py` - Trading simulation logic
  - `scripts/grid_search_hyperparameters.py` - Grid search infrastructure
  - `espn.prob_event_state` - Aligned game state with probabilities
  - `kalshi.candlesticks` - Kalshi market data

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified]
- **QC Results**: [To be verified]
- **Code Coverage**: [To be verified]
- **Build Status**: [To be verified]

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify raw ingest tables** - no INSERT, UPDATE, TRUNCATE, DELETE on `espn.*`, `kalshi.*`, `nba.*` tables unless part of sprint plan or tests
- **Schema changes allowed** - Creating new tables/views/materialized views in `derived` schema for canonical dataset is part of sprint scope
- **Read database access** - Reading from `espn.prob_event_state`, `kalshi.candlesticks`, `espn.probabilities_raw_items`, `kalshi.markets_with_games`

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git branching, rebasing, or force-push operations. Commits are allowed when explicitly stated in the sprint plan (e.g., for new features). The intent is to prevent destructive git operations while allowing normal development workflow.

## Sprint Overview

### Business Context
- **Business Driver**: Grid search validated that fees are the bottleneck and signal quality needs improvement. Current ESPN probabilities are raw and uncalibrated. Need foundation (canonical dataset) to enable signal improvement work (interaction terms, autoregressive features, CatBoost).
- **Success Criteria**: 
  - Canonical snapshot dataset (`derived.snapshot_features_v1`) exists with all required features
  - Fee modeling validated (rounding, contract conversion, maker/taker assumptions)
  - ESPN odds inspection complete (document findings)
  - 2025-26 odds strategy decision made (free options only: historical datasets for backfill, scraping for 2025-26 with risk acceptance, or defer)
  - All downstream work (modeling, simulation) can consume canonical dataset
- **Stakeholders**: Data scientist (providing guidance), trading strategy developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - `espn.prob_event_state` exists with aligned game state per probability snapshot
  - `kalshi.candlesticks` exists with bid/ask/spread data (not always aligned with ESPN timestamps)
  - `kalshi.markets_with_games` view exists with `kalshi_team_side` computed field ('home' or 'away')
  - Trading simulation uses raw `probabilities_raw_items` (doesn't use aligned game state)
  - No canonical feature dataset exists (features calculated ad-hoc in different places)
  - Fee modeling exists but not validated for correctness
- **Target System State**: 
  - `derived.snapshot_features_v1` view/table/materialized view with all features pre-computed
  - Fee modeling validated and documented
  - ESPN odds fields inspected and documented
  - Decision made on 2025-26 odds strategy
  - All modeling/simulation consumes canonical dataset (single source of truth)
- **Architecture Impact**: Adds new derived table/view, no changes to existing simulation logic (yet)
- **Integration Points**: Existing `espn.prob_event_state`, `kalshi.candlesticks`, `espn.probabilities_raw_items`, `kalshi.markets_with_games`

### Sprint Scope
- **In Scope**: 
  - Build canonical snapshot dataset (`derived.snapshot_features_v1`)
  - Validate fee modeling correctness
  - Inspect ESPN API for odds fields
  - Make decision on 2025-26 odds strategy
  - Document findings and decisions
- **Out of Scope**: 
  - Implementing signal improvement models (deferred to next sprint)
  - Adding external sportsbook odds (deferred until decision made)
  - Changing simulation logic to use canonical dataset (deferred to next sprint)
- **Assumptions**: 
  - `espn.prob_event_state` has sufficient data quality
  - `kalshi.candlesticks` can be aligned with ESPN timestamps
  - `kalshi.markets_with_games` correctly identifies home/away markets
  - Fee modeling code exists and can be inspected
- **Constraints**: 
  - Must ensure no data leakage (canonical dataset should be game-level split compatible)
  - Must handle missing Kalshi data gracefully (not all games have Kalshi markets)
  - Must preserve existing simulation behavior (validation only, no changes yet)
  - Free-only constraint: Paid APIs are NOT an option for 2025-26 odds

## Sprint Phases

### Phase 1: Fee Modeling Sanity Check (Duration: 4-6 hours)
**Objective**: Validate fee modeling correctness (rounding, contract conversion, maker/taker assumptions)
**Dependencies**: Existing fee modeling code in `simulate_trading_strategy.py`
**Deliverables**: 
- Fee modeling validation checklist completed
- Documented findings (correct or issues found)
- Fixes applied if issues found

**Evidence to Capture**:
- Exact file path + line refs for fee function: `scripts/simulate_trading_strategy.py:580-597` (`calculate_kalshi_fee`)
- Unit test command: `pytest scripts/test_simulate_trading_strategy.py::test_calculate_kalshi_fee -v`
- Test output: (PASTE OUTPUT HERE)
- Python snippet verifying rounding cases: (PASTE CODE + OUTPUT HERE)

### Phase 2: ESPN Odds Inspection (Duration: 2-4 hours)
**Objective**: Inspect ESPN API raw JSONB for odds fields
**Dependencies**: Database access to `espn.probabilities_raw_items`
**Deliverables**: 
- Inspection report (odds fields found or not found)
- Documentation of findings

**Evidence to Capture**:
- psql query to inspect raw_item keys:
  ```sql
  SELECT 
    event_id,
    jsonb_object_keys(raw_item) as key_name
  FROM espn.probabilities_raw_items
  LIMIT 100;
  ```
- Query results: (PASTE RESULTS HERE)
- Search for odds-related keys:
  ```sql
  SELECT DISTINCT jsonb_object_keys(raw_item) as key_name
  FROM espn.probabilities_raw_items
  WHERE jsonb_object_keys(raw_item) ILIKE '%odd%'
     OR jsonb_object_keys(raw_item) ILIKE '%moneyline%'
     OR jsonb_object_keys(raw_item) ILIKE '%line%'
     OR jsonb_object_keys(raw_item) ILIKE '%spread%'
     OR jsonb_object_keys(raw_item) ILIKE '%overUnder%'
     OR jsonb_object_keys(raw_item) ILIKE '%sportsbook%';
  ```
- Sample payload excerpts: (PASTE JSONB EXCERPTS HERE)

### Phase 3: Canonical Snapshot Dataset (Duration: 20-30 hours)
**Objective**: Build `derived.snapshot_features_v1` view/table/materialized view with all required features
**Dependencies**: Phase 1 and 2 complete (can proceed in parallel)
**Deliverables**: 
- `derived.snapshot_features_v1` table/view/materialized view created
- All required features included
- Indexes created for performance
- Data quality validation completed

**Evidence to Capture**:
- Schema definition: `\d+ derived.snapshot_features_v1`
- Schema output: (PASTE OUTPUT HERE)
- Row count: `SELECT COUNT(*) FROM derived.snapshot_features_v1;`
- Uniqueness check: 
  ```sql
  SELECT 
    season_label, game_id, sequence_number, snapshot_ts,
    COUNT(*) as cnt
  FROM derived.snapshot_features_v1
  GROUP BY season_label, game_id, sequence_number, snapshot_ts
  HAVING COUNT(*) > 1;
  ```
- Query performance (single game):
  ```sql
  EXPLAIN (ANALYZE, BUFFERS)
  SELECT *
  FROM derived.snapshot_features_v1
  WHERE game_id = '401585401'
  ORDER BY sequence_number;
  ```
- Query performance (season filter):
  ```sql
  EXPLAIN (ANALYZE, BUFFERS)
  SELECT *
  FROM derived.snapshot_features_v1
  WHERE season_label = '2025-26'
  LIMIT 1000;
  ```
- Sequence number monotonicity check:
  ```sql
  SELECT 
    game_id,
    sequence_number,
    LAG(sequence_number) OVER (PARTITION BY game_id ORDER BY sequence_number) as prev_seq,
    sequence_number - LAG(sequence_number) OVER (PARTITION BY game_id ORDER BY sequence_number) as seq_diff
  FROM derived.snapshot_features_v1
  WHERE game_id = '401585401'
  ORDER BY sequence_number
  LIMIT 20;
  ```
- Kalshi coverage: `SELECT COUNT(*) FILTER (WHERE kalshi_mid_price IS NOT NULL) * 100.0 / COUNT(*) as pct_with_kalshi FROM derived.snapshot_features_v1;`
- Time remaining sanity: `SELECT MIN(time_remaining), MAX(time_remaining) FROM derived.snapshot_features_v1 WHERE time_remaining IS NOT NULL;`
- Interaction term sanity: `SELECT COUNT(*) FILTER (WHERE score_diff_div_sqrt_time_remaining IS NULL OR NOT isfinite(score_diff_div_sqrt_time_remaining)) FROM derived.snapshot_features_v1;`

### Phase 4: 2025-26 Odds Strategy Decision (Duration: 2-4 hours)
**Objective**: Make explicit decision on external sportsbook odds strategy (free options only)
**Dependencies**: Phase 2 complete (ESPN odds inspection)
**Deliverables**: 
- Decision document (free options only: historical datasets for backfill, scraping for 2025-26 with risk acceptance, or defer)
- Rationale documented
- Next steps defined
- **Note**: Paid APIs are NOT an option - only free options considered

**Reality Check**: For 2025-26 real sportsbook line history (timestamped moves), there is effectively no truly-free, unlimited API. Free options are: (1) scraped sources (ToS/legal risk), (2) static historical datasets (Kaggle/GitHub) for prior seasons only, or (3) defer external odds.

**Evidence to Capture**:
- Decision record document: (PASTE DECISION + RATIONALE HERE)
- Risk acceptance statement (if scraping chosen): (PASTE STATEMENT HERE)
- Next step tasks: (PASTE TASKS HERE)

### Phase 5: Testing and Validation (Duration: 6-8 hours)
**Objective**: Validate canonical dataset quality, test feature calculations, verify alignment
**Dependencies**: Phase 3 complete
**Deliverables**: 
- Data quality report
- Feature calculation validation
- Alignment verification (ESPN/Kalshi timestamps)
- Sample queries demonstrating usage

**Evidence to Capture**:
- 10-game spot check checklist:
  - 5 games with Kalshi data: (PASTE SAMPLE ROWS HERE)
  - 5 games without Kalshi data: (PASTE SAMPLE ROWS HERE)
  - Timestamp delta verification (≤ 60s when Kalshi present): (PASTE QUERY RESULTS HERE)
  - LAG/delta validation for 2 games (manual row comparisons): (PASTE COMPARISON HERE)

### Phase 6: Documentation and Sprint Quality Assurance (Duration: 6-8 hours) [MANDATORY]
**Objective**: Document canonical dataset schema, usage patterns, and complete sprint
**Dependencies**: Must complete Phase 5 successfully
**Deliverables**: 
- Schema documentation
- Usage examples
- Migration script (if table/materialized view, not view)
- Updated analysis document
- 100% passing quality gates
- Sprint archive

**Evidence to Capture**:
- Schema doc location: `cursor-files/docs/schema/snapshot_features_v1.md`
- Usage examples location: `cursor-files/docs/examples/snapshot_features_v1_usage.md`
- Migration SQL path: `db/migrations/XXX_derived_snapshot_features_v1.sql`
- Analysis doc updates path: `cursor-files/analysis/signal_improvement_next_steps_analysis.md`

## Sprint Backlog

### Epic 1: Fee Modeling Validation

**Priority**: Critical (prerequisite for accurate simulation)
**Estimated Time**: 4-6 hours
**Dependencies**: Existing fee modeling code
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Fee Rounding Validation

- **ID**: S13-E1-S1
- **Type**: Validation
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Review**: 
  - `scripts/simulate_trading_strategy.py:580-597` (`calculate_kalshi_fee` function)

- **Acceptance Criteria**:
  - [ ] Verify fee calculation formula matches Kalshi: `fee_rate = 0.07 * (price * (1 - price))`
  - [ ] Verify fee rounds UP to the next cent ($0.01 minimum when raw fee > 0) - **NOTE**: Current implementation may not round; document actual behavior
  - [ ] Test edge cases: fee = 0, fee = 0.001, fee = 0.009, fee = 0.01, fee = 0.011
  - [ ] Document findings (correct or issues found)
  - [ ] Fix issues if found (add rounding if missing)

- **Tasks**:
  - [ ] T1.1.1: Locate fee calculation code: `scripts/simulate_trading_strategy.py:580-597`
  - [ ] T1.1.2: Review rounding logic (check if `math.ceil` or equivalent is used)
  - [ ] T1.1.3: Write test cases for edge cases
  - [ ] T1.1.4: Run tests and document results
  - [ ] T1.1.5: Fix if issues found (add rounding if missing)

- **Test Cases**:
  - [ ] Test fee = 0 → should be 0 (no rounding)
  - [ ] Test fee = 0.001 → should round to 0.01 (if rounding implemented)
  - [ ] Test fee = 0.009 → should round to 0.01 (if rounding implemented)
  - [ ] Test fee = 0.01 → should stay 0.01
  - [ ] Test fee = 0.011 → should round to 0.02 (if rounding implemented)

- **Evidence to Capture**:
  - File path + line refs: `scripts/simulate_trading_strategy.py:580-597`
  - Unit test command: `pytest scripts/test_simulate_trading_strategy.py::test_calculate_kalshi_fee -v` (create test file if missing)
  - Test output: (PASTE OUTPUT HERE)
  - Python snippet:
    ```python
    from scripts.simulate_trading_strategy import calculate_kalshi_fee
    # Test cases
    print(f"fee(0.50, 1.00) = {calculate_kalshi_fee(0.50, 1.00)}")
    print(f"fee(0.50, 0.001) = {calculate_kalshi_fee(0.50, 0.001)}")
    # ... more test cases
    ```
  - Output: (PASTE OUTPUT HERE)

#### Story 1.2: Contract vs Dollars Conversion Validation

- **ID**: S13-E1-S2
- **Type**: Validation
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.1 complete
- **Files to Review**: 
  - `scripts/simulate_trading_strategy.py` (position sizing, fee calculation)

- **Acceptance Criteria**:
  - [ ] Verify fee uses number of contracts (or correctly converts dollars→contracts if sim uses dollars)
  - [ ] Document contract size assumption (if applicable)
  - [ ] Verify conversion logic is correct
  - [ ] Document findings

- **Tasks**:
  - [ ] T1.2.1: Locate contract/dollar conversion code
  - [ ] T1.2.2: Review conversion logic
  - [ ] T1.2.3: Verify contract size assumptions
  - [ ] T1.2.4: Write test cases
  - [ ] T1.2.5: Document findings

- **Test Cases**:
  - [ ] Test fee calculation with known contract count
  - [ ] Test fee calculation with dollar amount (if applicable)
  - [ ] Verify conversion matches Kalshi API behavior

#### Story 1.3: Maker vs Taker Fee Assumptions

- **ID**: S13-E1-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.2 complete
- **Files to Review**: 
  - `scripts/simulate_trading_strategy.py:596` (fee rate constant: 0.07)

- **Acceptance Criteria**:
  - [ ] Confirm maker vs taker fee rate assumptions (if we're modeling either)
  - [ ] Document which fee rate we're using (maker or taker, or both)
  - [ ] Verify fee rate matches Kalshi API documentation (7% formula)
  - [ ] Document findings

- **Tasks**:
  - [ ] T1.3.1: Locate fee rate constants/assumptions: `scripts/simulate_trading_strategy.py:596`
  - [ ] T1.3.2: Review Kalshi API documentation for fee structure
  - [ ] T1.3.3: Verify our assumptions match reality
  - [ ] T1.3.4: Document findings

- **Test Cases**:
  - [ ] Verify fee rate matches Kalshi API (7% formula: `0.07 * (price * (1 - price))`)
  - [ ] Verify maker vs taker distinction (if applicable)

### Epic 2: ESPN Odds Inspection

**Priority**: Medium (informational, doesn't block other work)
**Estimated Time**: 2-4 hours
**Dependencies**: Database access
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Inspect Raw JSONB for Odds Fields

- **ID**: S13-E2-S1
- **Type**: Investigation
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 2
- **Prerequisites**: None
- **Files to Review**: 
  - `espn.probabilities_raw_items.raw_item` (JSONB column)

- **Acceptance Criteria**:
  - [ ] Sample multiple `raw_item` JSONB records
  - [ ] Search for odds-related fields (american_odds, decimal_odds, implied_probability, etc.)
  - [ ] Document findings (fields found or not found)
  - [ ] Create inspection report
  - [ ] **Acceptance**: Documented: odds present? Y/N; if present, exact JSON path(s) + example payload excerpts

- **Tasks**:
  - [ ] T2.1.1: Query sample records from `espn.probabilities_raw_items`
  - [ ] T2.1.2: Inspect `raw_item` JSONB structure
  - [ ] T2.1.3: Search for odds-related keys
  - [ ] T2.1.4: Document findings in inspection report

- **Test Cases**:
  - [ ] Sample 10-20 records from different games
  - [ ] Check for common odds field names
  - [ ] Document structure if odds found

- **Evidence to Capture**:
  - psql query to inspect keys:
    ```sql
    SELECT 
      event_id,
      jsonb_object_keys(raw_item) as key_name
    FROM espn.probabilities_raw_items
    LIMIT 100;
    ```
  - Query results: (PASTE RESULTS HERE)
  - Search for odds-related keys:
    ```sql
    SELECT DISTINCT jsonb_object_keys(raw_item) as key_name
    FROM espn.probabilities_raw_items
    WHERE jsonb_object_keys(raw_item) ILIKE '%odd%'
       OR jsonb_object_keys(raw_item) ILIKE '%moneyline%'
       OR jsonb_object_keys(raw_item) ILIKE '%line%'
       OR jsonb_object_keys(raw_item) ILIKE '%spread%'
       OR jsonb_object_keys(raw_item) ILIKE '%overUnder%'
       OR jsonb_object_keys(raw_item) ILIKE '%sportsbook%';
    ```
  - Sample payload excerpts: (PASTE JSONB EXCERPTS HERE)

#### Story 2.2: Check Scoreboard Endpoints for Odds

- **ID**: S13-E2-S2
- **Type**: Investigation
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.1 complete
- **Files to Review**: 
  - `espn.scoreboard_games` table
  - ESPN API endpoints (if accessible)

- **Acceptance Criteria**:
  - [ ] Check `espn.scoreboard_games` schema for odds fields
  - [ ] If ESPN API accessible, check scoreboard endpoint documentation
  - [ ] Document findings

- **Tasks**:
  - [ ] T2.2.1: Review `espn.scoreboard_games` schema: `\d espn.scoreboard_games`
  - [ ] T2.2.2: Check ESPN API documentation (if available)
  - [ ] T2.2.3: Document findings

### Epic 3: Canonical Snapshot Dataset

**Priority**: Critical (foundation for all signal improvement work)
**Estimated Time**: 20-30 hours
**Dependencies**: Can proceed in parallel with Epic 1 and 2
**Status**: Not Started
**Phase Assignment**: Phase 3

**Uniqueness Rule**: Canonical rows are unique on `(season_label, game_id, sequence_number, snapshot_ts)`. Prefer `sequence_number` for ordering (it should be strictly increasing per game). Fall back to `snapshot_ts` only if `sequence_number` is not strictly increasing (document exceptions).

#### Story 3.1: Design Schema and Create Table/View/Materialized View

- **ID**: S13-E3-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4-6 hours
- **Phase**: Phase 3
- **Prerequisites**: None
- **Files to Create**: 
  - Migration: `db/migrations/XXX_derived_snapshot_features_v1.sql`

- **Acceptance Criteria**:
  - [ ] Schema designed with required columns:
    - Keys: `season_label`, `game_id`, `sequence_number`, `snapshot_ts` (last_modified_utc)
    - ESPN: `espn_home_prob`, `espn_away_prob` (0-1 format)
    - Game state: `score_diff`, `time_remaining`, `period`/`quarter`
    - Interaction: `score_diff_div_sqrt_time_remaining` (score_diff / sqrt(time_remaining + eps))
    - Lagged: `espn_home_prob_lag_1`, `espn_away_prob_lag_1`
    - Delta: `espn_home_prob_delta_1` (current - lag_1)
    - Kalshi: `kalshi_home_mid_price`, `kalshi_away_mid_price`, `kalshi_home_bid`, `kalshi_home_ask`, `kalshi_away_bid`, `kalshi_away_ask`, `kalshi_home_spread`, `kalshi_away_spread` (if available)
  - [ ] **Decision Gate**: Start with VIEW for correctness iteration
  - [ ] If performance is slow, migrate to MATERIALIZED VIEW or TABLE with refresh
  - [ ] If materialized/table chosen, add refresh strategy (manual refresh command, when to run, expected runtime)
  - [ ] Table/view/materialized view created in `derived` schema
  - [ ] Migration script created and tested
  - [ ] Verify `sequence_number` strictly increasing per game (or document exceptions + chosen ordering)

- **Tasks**:
  - [ ] T3.1.1: Design schema (view vs materialized view vs table decision)
  - [ ] T3.1.2: Create migration script (start with VIEW)
  - [ ] T3.1.3: Test migration on dev database
  - [ ] T3.1.4: Test query performance (EXPLAIN ANALYZE)
  - [ ] T3.1.5: If slow, migrate to materialized view/table + add refresh strategy
  - [ ] T3.1.6: Document schema decisions

- **Test Cases**:
  - [ ] Migration runs successfully
  - [ ] Schema matches specification
  - [ ] Can query table/view/materialized view
  - [ ] Query performance acceptable (< 1s for single game, < 5s for season filter)

- **Refresh Strategy** (if materialized view/table):
  - Manual refresh command: `REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;`
  - When to run: After ESPN/Kalshi data ingestion
  - Expected runtime: (MEASURE AND DOCUMENT)

#### Story 3.2: Join ESPN and Kalshi Data with Timestamp Alignment

- **ID**: S13-E3-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 6-8 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.1 complete
- **Files to Modify**: 
  - Migration script or view definition

- **Acceptance Criteria**:
  - [ ] Join `espn.prob_event_state` with `kalshi.candlesticks` aligned by timestamp
  - [ ] Handle missing Kalshi data gracefully (NULL for Kalshi fields if no match)
  - [ ] Alignment window: match Kalshi candlestick within 60 seconds of ESPN timestamp
  - [ ] **Kalshi Market Selection Rule**: Determine which Kalshi market/ticker maps to "home win" vs "away win" probability
  - [ ] If both home and away markets exist, store BOTH:
    - `kalshi_home_*` and `kalshi_away_*` fields (separate columns)
    - OR store one canonical market (but document why)
  - [ ] Define `kalshi_home_mid_price` as `(kalshi_home_bid + kalshi_home_ask) / 2` only when both present; else NULL
  - [ ] Define `kalshi_away_mid_price` as `(kalshi_away_bid + kalshi_away_ask) / 2` only when both present; else NULL
  - [ ] Inspect `kalshi.markets_with_games` to verify mapping is correct per game
  - [ ] Use `kalshi_team_side` field from `kalshi.markets_with_games` to identify home vs away markets

- **Tasks**:
  - [ ] T3.2.1: Inspect `kalshi.markets_with_games` structure: `SELECT * FROM kalshi.markets_with_games LIMIT 10;`
  - [ ] T3.2.2: Verify `kalshi_team_side` field correctly identifies home/away markets
  - [ ] T3.2.3: Write JOIN logic for ESPN → Kalshi alignment (separate home/away markets)
  - [ ] T3.2.4: Implement timestamp matching (within 60 seconds)
  - [ ] T3.2.5: Handle multiple markets (home/away team markets) - store both
  - [ ] T3.2.6: Test alignment on sample games
  - [ ] T3.2.7: Verify NULL handling for missing Kalshi data

- **Test Cases**:
  - [ ] Test alignment on games with Kalshi data (both home and away markets)
  - [ ] Test alignment on games with only home market (away should be NULL)
  - [ ] Test alignment on games without Kalshi data (should have NULLs)
  - [ ] Test timestamp matching (within 60 seconds)
  - [ ] Test multiple markets per game (home/away)

- **Evidence to Capture**:
  - Kalshi markets inspection:
    ```sql
    SELECT 
      espn_event_id,
      ticker,
      kalshi_team_side,
      yes_sub_title,
      no_sub_title
    FROM kalshi.markets_with_games
    WHERE espn_event_id = '401585401'
    LIMIT 10;
    ```
  - Results: (PASTE RESULTS HERE)

#### Story 3.3: Calculate Interaction Terms

- **ID**: S13-E3-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.2 complete
- **Files to Modify**: 
  - Migration script or view definition

- **Acceptance Criteria**:
  - [ ] Calculate `score_diff_div_sqrt_time_remaining` = `score_diff / sqrt(time_remaining + eps)`
  - [ ] Handle edge cases: `time_remaining = 0` (use eps to avoid division by zero)
  - [ ] Calculate `period`/`quarter` from `time_remaining` (Q1, Q2-Q3, Q4)
  - [ ] All calculations in SQL (or view definition)
  - [ ] Verify no inf/NaN values (interaction term numeric sanity)

- **Tasks**:
  - [ ] T3.3.1: Implement `score_diff / sqrt(time_remaining + eps)` calculation
  - [ ] T3.3.2: Implement period/quarter calculation
  - [ ] T3.3.3: Test edge cases (time_remaining = 0)
  - [ ] T3.3.4: Verify calculations match expected values
  - [ ] T3.3.5: Verify no inf/NaN values

- **Test Cases**:
  - [ ] Test interaction term calculation on sample rows
  - [ ] Test time_remaining = 0 edge case
  - [ ] Test period calculation correctness
  - [ ] Verify no inf/NaN: `SELECT COUNT(*) FILTER (WHERE NOT isfinite(score_diff_div_sqrt_time_remaining)) FROM derived.snapshot_features_v1;`

#### Story 3.4: Calculate Lagged Features

- **ID**: S13-E3-S4
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4-6 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.3 complete
- **Files to Modify**: 
  - Migration script or view definition

- **Acceptance Criteria**:
  - [ ] Calculate `espn_home_prob_lag_1` (previous snapshot's home prob)
  - [ ] Calculate `espn_away_prob_lag_1` (previous snapshot's away prob)
  - [ ] Calculate `espn_home_prob_delta_1` (current - lag_1)
  - [ ] Handle first snapshot per game (lag_1 = NULL, delta_1 = NULL)
  - [ ] Use window functions (LAG) for efficiency
  - [ ] **Ordering**: Use `sequence_number` for LAG (prefer over `snapshot_ts`)
  - [ ] Verify `sequence_number` strictly increasing per game (or document exceptions)

- **Tasks**:
  - [ ] T3.4.1: Verify `sequence_number` ordering: `SELECT game_id, sequence_number, LAG(sequence_number) OVER (PARTITION BY game_id ORDER BY sequence_number) FROM derived.snapshot_features_v1 WHERE game_id = '401585401' LIMIT 20;`
  - [ ] T3.4.2: Implement LAG window functions for lagged features (ORDER BY sequence_number)
  - [ ] T3.4.3: Implement delta calculation (current - lag_1)
  - [ ] T3.4.4: Handle NULL for first snapshot per game
  - [ ] T3.4.5: Test lagged features on sample games
  - [ ] T3.4.6: Verify ordering (by sequence_number within game)

- **Test Cases**:
  - [ ] Test lag_1 on sample game (should have NULL for first row)
  - [ ] Test delta_1 calculation correctness
  - [ ] Test ordering (should be by sequence_number within game)
  - [ ] Verify sequence_number monotonicity per game

#### Story 3.5: Add Kalshi Market Data Fields

- **ID**: S13-E3-S5
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.2 complete
- **Files to Modify**: 
  - Migration script or view definition

- **Acceptance Criteria**:
  - [ ] Include `kalshi_home_mid_price` = `(kalshi_home_bid + kalshi_home_ask) / 2` (if both available)
  - [ ] Include `kalshi_away_mid_price` = `(kalshi_away_bid + kalshi_away_ask) / 2` (if both available)
  - [ ] Include `kalshi_home_bid`, `kalshi_home_ask` (from candlesticks for home market)
  - [ ] Include `kalshi_away_bid`, `kalshi_away_ask` (from candlesticks for away market)
  - [ ] Include `kalshi_home_spread` = `kalshi_home_ask - kalshi_home_bid` (if both available)
  - [ ] Include `kalshi_away_spread` = `kalshi_away_ask - kalshi_away_bid` (if both available)
  - [ ] Handle NULL when Kalshi data not available

- **Tasks**:
  - [ ] T3.5.1: Add Kalshi fields to schema (separate home/away columns)
  - [ ] T3.5.2: Calculate mid_price and spread in SQL (for both home and away)
  - [ ] T3.5.3: Test on games with/without Kalshi data
  - [ ] T3.5.4: Verify NULL handling

- **Test Cases**:
  - [ ] Test home mid_price calculation (should be NULL if bid/ask missing)
  - [ ] Test away mid_price calculation (should be NULL if bid/ask missing)
  - [ ] Test spread calculation (both home and away)
  - [ ] Test NULL handling for games without Kalshi

#### Story 3.6: Create Indexes and Validate Performance

- **ID**: S13-E3-S6
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-4 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.5 complete
- **Files to Modify**: 
  - Migration script

- **Acceptance Criteria**:
  - [ ] Create index on `(game_id, snapshot_ts)` for fast queries
  - [ ] Create index on `(season_label, game_id)` if needed
  - [ ] Create unique index on `(season_label, game_id, sequence_number, snapshot_ts)` to enforce uniqueness
  - [ ] Test query performance on sample queries
  - [ ] Document index strategy

- **Tasks**:
  - [ ] T3.6.1: Create primary index on `(game_id, snapshot_ts)`
  - [ ] T3.6.2: Create unique index on `(season_label, game_id, sequence_number, snapshot_ts)`
  - [ ] T3.6.3: Create secondary indexes if needed
  - [ ] T3.6.4: Test query performance (EXPLAIN ANALYZE)
  - [ ] T3.6.5: Document index strategy

- **Test Cases**:
  - [ ] Test query performance on single game
  - [ ] Test query performance on season filter
  - [ ] Verify indexes are used (EXPLAIN output)

- **Evidence to Capture**:
  - EXPLAIN ANALYZE for single game query: (PASTE OUTPUT HERE)
  - EXPLAIN ANALYZE for season filter query: (PASTE OUTPUT HERE)

### Epic 4: 2025-26 Odds Strategy Decision

**Priority**: Medium (decision gate, doesn't block canonical dataset)
**Estimated Time**: 2-4 hours
**Dependencies**: Epic 2 complete (ESPN odds inspection)
**Status**: Not Started
**Phase Assignment**: Phase 4

**Reality Check**: For 2025-26 real sportsbook line history (timestamped moves), there is effectively no truly-free, unlimited API. Free options are: (1) scraped sources (ToS/legal risk), (2) static historical datasets (Kaggle/GitHub) for prior seasons only, or (3) defer external odds.

#### Story 4.1: Evaluate Options and Make Decision

- **ID**: S13-E4-S1
- **Type**: Decision
- **Priority**: Medium
- **Estimate**: 2-4 hours
- **Phase**: Phase 4
- **Prerequisites**: Epic 2 complete

- **Acceptance Criteria**:
  - [ ] Evaluate free options only (paid APIs are NOT an option):
    - **(a)** Use free historical datasets (Kaggle/GitHub) for PAST seasons (backfill only) + defer 2025-26 line history, OR
    - **(b)** Pursue scraping for 2025-26 (explicit risk acceptance required), OR
    - **(c)** Defer external odds entirely and proceed with ESPN/Kalshi-only signal improvements
  - [ ] Document decision with rationale
  - [ ] Define next steps based on decision
  - [ ] **Note**: Paid APIs explicitly excluded from consideration
  - [ ] If scraping chosen, document explicit risk acceptance statement

- **Tasks**:
  - [ ] T4.1.1: Review analysis document (Section 1.5) for free options only
  - [ ] T4.1.2: Evaluate free Kaggle datasets (coverage, quality, format) - **NOTE**: These are for PAST seasons only
  - [ ] T4.1.3: Evaluate GitHub scraper datasets (ToS risk, data quality, legal concerns) - **NOTE**: Only option for 2025-26 if we want external odds
  - [ ] T4.1.4: Evaluate need for external odds (can we proceed with ESPN/Kalshi only?)
  - [ ] T4.1.5: Make decision and document rationale (free options only)
  - [ ] T4.1.6: Define next steps based on decision
  - [ ] T4.1.7: If scraping chosen, document explicit risk acceptance statement

- **Decision Criteria**:
  - Do we need external sportsbook odds for signal improvement, or can we proceed with ESPN/Kalshi only?
  - What's the risk tolerance for scraping-based datasets (ToS/legal concerns)?
  - Can we validate signal improvement using historical Kaggle datasets first?
  - **Constraint**: Paid APIs are NOT an option - only free options considered
  - **Reality**: Kaggle/GitHub datasets are for PAST seasons only, not 2025-26 in-season

- **Evidence to Capture**:
  - Decision record: (PASTE DECISION + RATIONALE HERE)
  - Risk acceptance statement (if scraping chosen): (PASTE STATEMENT HERE)
  - Next step tasks: (PASTE TASKS HERE)

- **Odds Sources Summary**:
  - **TRULY FREE (download)**: Kaggle / GitHub datasets for PAST seasons (often closing lines / limited movement)
  - **NOT FREE AT OUR SCALE**: request-limited odds APIs (credits/caps)
  - **2025-26**: only 'free' path is scraping/polling (ToS/legal + reliability risk)

### Epic 5: Data Quality Validation

**Priority**: High (ensures correctness)
**Estimated Time**: 6-8 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 5.1: Validate Feature Calculations

- **ID**: S13-E5-S1
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 5
- **Prerequisites**: Epic 3 complete

- **Acceptance Criteria**:
  - [ ] Validate interaction term calculation on sample rows
  - [ ] Validate lagged features (lag_1, delta_1) on sample games
  - [ ] Validate Kalshi fields (mid_price, spread) on sample games
  - [ ] Document validation results

- **Tasks**:
  - [ ] T5.1.1: Sample 5-10 games from canonical dataset
  - [ ] T5.1.2: Manually verify interaction term calculations
  - [ ] T5.1.3: Manually verify lagged features
  - [ ] T5.1.4: Manually verify Kalshi fields
  - [ ] T5.1.5: Document validation results

#### Story 5.2: Validate Timestamp Alignment

- **ID**: S13-E5-S2
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 5
- **Prerequisites**: Story 5.1 complete

- **Acceptance Criteria**:
  - [ ] Verify ESPN and Kalshi timestamps are aligned (within 60 seconds)
  - [ ] Spot-check alignment on 5-10 games
  - [ ] Verify no misalignment issues
  - [ ] Document validation results

- **Tasks**:
  - [ ] T5.2.1: Query sample games with Kalshi data
  - [ ] T5.2.2: Compare ESPN and Kalshi timestamps
  - [ ] T5.2.3: Verify alignment window (60 seconds)
  - [ ] T5.2.4: Document validation results

#### Story 5.3: Validate Data Completeness

- **ID**: S13-E5-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 5
- **Prerequisites**: Story 5.2 complete

- **Acceptance Criteria**:
  - [ ] Verify all games with ESPN data appear in canonical dataset
  - [ ] Verify games without Kalshi data have NULL for Kalshi fields
  - [ ] Verify no duplicate rows (game_id + sequence_number + snapshot_ts should be unique)
  - [ ] Document completeness metrics

- **Tasks**:
  - [ ] T5.3.1: Count games in ESPN vs canonical dataset
  - [ ] T5.3.2: Verify NULL handling for missing Kalshi data
  - [ ] T5.3.3: Check for duplicate rows
  - [ ] T5.3.4: Document completeness metrics

- **Evidence to Capture**:
  - 10-game spot check checklist:
    - 5 games with Kalshi data: (PASTE SAMPLE ROWS HERE)
    - 5 games without Kalshi data: (PASTE SAMPLE ROWS HERE)
    - Timestamp delta verification (≤ 60s when Kalshi present):
      ```sql
      SELECT 
        game_id,
        snapshot_ts,
        ABS(EXTRACT(EPOCH FROM (snapshot_ts - kalshi_timestamp))) as delta_seconds
      FROM derived.snapshot_features_v1
      WHERE kalshi_home_mid_price IS NOT NULL
      LIMIT 10;
      ```
    - Results: (PASTE RESULTS HERE)
    - LAG/delta validation for 2 games (manual row comparisons): (PASTE COMPARISON HERE)

### Epic 6: Documentation

**Priority**: High (required for usability)
**Estimated Time**: 6-8 hours
**Dependencies**: Epic 5 complete
**Status**: Not Started
**Phase Assignment**: Phase 6

#### Story 6.1: Schema Documentation

- **ID**: S13-E6-S1
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 6
- **Prerequisites**: Epic 5 complete

- **Acceptance Criteria**:
  - [ ] Document canonical dataset schema (all columns, types, constraints)
  - [ ] Document data sources (which tables joined)
  - [ ] Document feature calculation formulas
  - [ ] Document NULL handling rules
  - [ ] Document uniqueness rule: `(season_label, game_id, sequence_number, snapshot_ts)`
  - [ ] Document ordering: `sequence_number` (preferred) vs `snapshot_ts` (fallback)

- **Tasks**:
  - [ ] T6.1.1: Create schema documentation: `cursor-files/docs/schema/snapshot_features_v1.md`
  - [ ] T6.1.2: Document data sources and joins
  - [ ] T6.1.3: Document feature calculations
  - [ ] T6.1.4: Document NULL handling
  - [ ] T6.1.5: Document uniqueness and ordering rules

#### Story 6.2: Usage Examples

- **ID**: S13-E6-S2
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 6
- **Prerequisites**: Story 6.1 complete

- **Acceptance Criteria**:
  - [ ] Provide example queries for common use cases
  - [ ] Document how to use canonical dataset in modeling
  - [ ] Document how to use canonical dataset in simulation
  - [ ] Provide sample code snippets

- **Tasks**:
  - [ ] T6.2.1: Write example queries (get features for game, get features for season)
  - [ ] T6.2.2: Document modeling usage patterns
  - [ ] T6.2.3: Document simulation usage patterns
  - [ ] T6.2.4: Add code snippets
  - [ ] T6.2.5: Save to: `cursor-files/docs/examples/snapshot_features_v1_usage.md`

#### Story 6.3: Update Analysis Document

- **ID**: S13-E6-S3
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 6
- **Prerequisites**: Story 6.2 complete

- **Acceptance Criteria**:
  - [ ] Update analysis document with canonical dataset completion status
  - [ ] Document fee modeling validation results
  - [ ] Document ESPN odds inspection findings
  - [ ] Document 2025-26 odds strategy decision

- **Tasks**:
  - [ ] T6.3.1: Update analysis document: `cursor-files/analysis/signal_improvement_next_steps_analysis.md`
  - [ ] T6.3.2: Add canonical dataset section
  - [ ] T6.3.3: Document validation results
  - [ ] T6.3.4: Document decisions made

#### Story 6.4: Migration Script Documentation

- **ID**: S13-E6-S4
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 6
- **Prerequisites**: Story 6.3 complete

- **Acceptance Criteria**:
  - [ ] Document migration script path: `db/migrations/XXX_derived_snapshot_features_v1.sql`
  - [ ] Document refresh strategy (if materialized view/table)
  - [ ] Document expected runtime for refresh

- **Tasks**:
  - [ ] T6.4.1: Document migration script location
  - [ ] T6.4.2: Document refresh command (if applicable)
  - [ ] T6.4.3: Document refresh timing and runtime

## Risk Management

### Technical Risks

1. **Risk**: Timestamp alignment between ESPN and Kalshi is complex
   - **Mitigation**: Use window functions, test on sample games, document alignment logic
   - **Contingency**: Adjust alignment window if needed, handle edge cases

2. **Risk**: Lagged features require careful ordering
   - **Mitigation**: Use window functions with PARTITION BY game_id, ORDER BY sequence_number
   - **Contingency**: Verify ordering, test on sample games, document if sequence_number not strictly increasing

3. **Risk**: Missing Kalshi data for many games
   - **Mitigation**: Handle NULL gracefully, document data availability
   - **Contingency**: Consider fallback strategies if needed

4. **Risk**: Kalshi home/away market ambiguity
   - **Mitigation**: Use `kalshi.markets_with_games.kalshi_team_side` to identify markets, store both home and away separately
   - **Contingency**: Document mapping logic, verify on sample games

5. **Risk**: View performance is slow
   - **Mitigation**: Start with VIEW, migrate to materialized view/table if needed
   - **Contingency**: Add indexes, implement refresh strategy

### Data Risks

1. **Risk**: Fee modeling has bugs that affect grid search results
   - **Mitigation**: Validate fee modeling early (Phase 1), fix issues before proceeding
   - **Contingency**: Re-run grid search if major issues found

2. **Risk**: Canonical dataset performance is slow
   - **Mitigation**: Create appropriate indexes, use view if table is too slow, migrate to materialized view if needed
   - **Contingency**: Consider materialized view or table refresh strategy

3. **Risk**: Sequence_number not strictly increasing
   - **Mitigation**: Verify sequence_number ordering, document exceptions
   - **Contingency**: Fall back to snapshot_ts ordering if needed

## Success Metrics

- [ ] Canonical snapshot dataset created with all required features
- [ ] Fee modeling validated (all checks pass or issues documented)
- [ ] ESPN odds inspection complete (findings documented)
- [ ] 2025-26 odds strategy decision made and documented
- [ ] Data quality validation passes (feature calculations correct, alignment verified)
- [ ] Documentation complete (schema, usage examples, decisions)
- [ ] All downstream work can consume canonical dataset (ready for next sprint)

## Definition of Done

- [ ] All stories completed and tested
- [ ] Canonical dataset exists and is queryable
- [ ] Fee modeling validation complete
- [ ] ESPN odds inspection complete
- [ ] 2025-26 odds strategy decision made
- [ ] Data quality validation passes
- [ ] Documentation is complete
- [ ] Code follows project standards
- [ ] All tests pass
- [ ] Sprint review completed

## Post-Sprint Follow-up

- Next sprint: Implement interaction terms model using canonical dataset
- Next sprint: Update simulation to use canonical dataset (if beneficial)
- Future: Add external sportsbook odds using free options only (if decision was to pursue Kaggle/GitHub datasets for historical backfill)
- Future: Backfill pipeline using Kaggle dataset (proof of concept for free historical data)
