# Sprint 14 - Signal Improvement Integration

**Date**: Sun Jan  4 20:12:59 PST 2026  
**Sprint Duration**: 1-2 weeks (44-60 hours total)  
**Sprint Goal**: Integrate canonical dataset into modeling/simulation and implement interaction terms model to improve signal quality  
**Current Status**: Canonical dataset `derived.snapshot_features_v1` exists but is not used by any scripts  
**Target Status**: All modeling/simulation scripts use canonical dataset, interaction terms model implemented and validated, improved signal quality demonstrated  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`
- **Sprint 13 Completion**: `cursor-files/docs/sprint_13_completion_report.md`
- **Canonical Dataset**: `db/migrations/032_derived_snapshot_features_v1.sql`
- **Current Implementation**: 
  - `scripts/simulate_trading_strategy.py` - Trading simulation (uses manual joins)
  - `scripts/train_winprob_logreg.py` - Model training (uses Parquet files)
  - `derived.snapshot_features_v1` - Canonical dataset (exists, not used)

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified]
- **QC Results**: [To be verified]
- **Code Coverage**: [To be verified]
- **Build Status**: [To be verified]

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify raw ingest tables** - no INSERT, UPDATE, TRUNCATE, DELETE on `espn.*`, `kalshi.*`, `nba.*` tables unless part of sprint plan or tests
- **Schema changes allowed** - Reading from `derived.snapshot_features_v1` is the primary operation
- **Read database access** - Reading from `derived.snapshot_features_v1`, `espn.probabilities_raw_items`, `kalshi.candlesticks` for comparison/validation

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
- **Business Driver**: Canonical dataset exists but is not integrated. Current scripts use duplicate logic and raw tables, creating inconsistency risk and maintenance burden. Signal quality needs improvement (still using raw ESPN probabilities). Need to integrate canonical dataset and implement interaction terms model to improve signal quality and enable better trading performance.
- **Success Criteria**: 
  - All modeling/simulation scripts use canonical dataset (single source of truth)
  - Interaction terms model implemented and validated
  - Improved signal quality demonstrated (lower logloss/Brier vs baseline)
  - Improved trading performance (higher net profit, better win rate)
  - No duplicate alignment logic remains
- **Stakeholders**: Data scientist (providing guidance), trading strategy developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - `derived.snapshot_features_v1` materialized view exists with all required features
  - `scripts/simulate_trading_strategy.py` manually joins `espn.probabilities_raw_items` + `kalshi.candlesticks` (~200 lines of duplicate alignment logic)
  - `scripts/train_winprob_logreg.py` reads from Parquet files (`build_winprob_snapshots_parquet.py`)
  - No scripts use canonical dataset yet
  - Still using raw ESPN probabilities (no signal improvement)
- **Target System State**: 
  - `simulate_trading_strategy.py` queries canonical dataset (single query, no manual joins)
  - `train_winprob_logreg.py` queries canonical dataset (no Parquet dependency)
  - Interaction terms model trained and validated
  - Grid search shows improved profitability with improved signal
  - All features come from canonical dataset (single source of truth)
- **Architecture Impact**: Replaces duplicate logic with canonical dataset queries, enables signal improvement work
- **Integration Points**: `derived.snapshot_features_v1`, existing simulation/modeling scripts

### Sprint Scope
- **In Scope**: 
  - Integrate canonical dataset into `simulate_trading_strategy.py`
  - Integrate canonical dataset into `train_winprob_logreg.py`
  - Implement interaction terms model using canonical dataset features
  - Validate improved signal with grid search
  - Remove duplicate alignment logic
- **Out of Scope**: 
  - CatBoost model (deferred to future sprint)
  - Additional features beyond interaction terms (deferred)
  - External sportsbook odds integration (deferred)
- **Assumptions**: 
  - Canonical dataset has sufficient data quality
  - Canonical dataset performance is acceptable (< 100ms per game query)
  - Interaction terms will improve signal quality
- **Constraints**: 
  - Must maintain backward compatibility (regression tests)
  - Must preserve existing simulation behavior (identical results)
  - Must handle missing Kalshi data gracefully (NULL in canonical dataset)

## Sprint Phases

### Phase 1: Integrate Canonical Dataset into Simulation (Duration: 8-12 hours)
**Objective**: Update `simulate_trading_strategy.py` to use `derived.snapshot_features_v1` instead of manual joins
**Dependencies**: Canonical dataset exists (Sprint 13 complete)
**Deliverables**: 
- `simulate_trading_strategy.py` queries canonical dataset
- Duplicate alignment logic removed
- Regression test passes (identical simulation results)
- Performance validation (< 100ms per game)

**Evidence to Capture**:
- Before/after code comparison: (PASTE CODE DIFF HERE)
- Query performance: `EXPLAIN ANALYZE` output for canonical dataset query
- Regression test results: (PASTE TEST OUTPUT HERE)
- Performance metrics: Query time for 10 games (PASTE TIMINGS HERE)

### Phase 2: Integrate Canonical Dataset into Modeling (Duration: 12-16 hours)
**Objective**: Update `train_winprob_logreg.py` to query canonical dataset instead of Parquet files
**Dependencies**: Phase 1 complete (can proceed in parallel)
**Deliverables**: 
- `train_winprob_logreg.py` queries canonical dataset
- Parquet dependency removed (or made optional)
- Feature mapping validated
- Training pipeline tested

**Evidence to Capture**:
- Before/after code comparison: (PASTE CODE DIFF HERE)
- Feature mapping validation: (PASTE FEATURE COMPARISON HERE)
- Training pipeline test: (PASTE TRAINING OUTPUT HERE)
- Data loading performance: Time to load full season (PASTE TIMINGS HERE)

### Phase 3: Implement Interaction Terms Model (Duration: 16-20 hours)
**Objective**: Train model using interaction terms from canonical dataset
**Dependencies**: Phase 2 complete
**Deliverables**: 
- Interaction terms model trained
- Platt scaling applied
- Signal metrics validated (logloss, Brier, ECE)
- Comparison vs baseline documented

**Evidence to Capture**:
- Model training output: (PASTE TRAINING LOGS HERE)
- Signal metrics comparison: Baseline vs improved (PASTE METRICS HERE)
- Calibration curve: (PASTE PLOT/MEASUREMENTS HERE)
- Feature importance: (PASTE FEATURE IMPORTANCE HERE)

### Phase 4: Validate Improved Signal (Duration: 8-12 hours)
**Objective**: Run grid search with improved signal and compare vs baseline
**Dependencies**: Phase 3 complete
**Deliverables**: 
- Grid search run with improved signal
- Trading metrics compared vs baseline
- Findings documented

**Evidence to Capture**:
- Grid search results: (PASTE RESULTS HERE)
- Trading metrics comparison: Baseline vs improved (PASTE METRICS HERE)
- Profitability analysis: (PASTE ANALYSIS HERE)
- Documentation: Updated analysis document with findings

## Sprint Backlog

### Epic 1: Integrate Canonical Dataset into Simulation

**Priority**: High (foundation for all other work)
**Estimated Time**: 8-12 hours
**Dependencies**: Canonical dataset exists
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Update `get_aligned_data()` to Query Canonical Dataset

- **ID**: S14-E1-S1
- **Type**: Refactoring
- **Priority**: Critical
- **Estimate**: 4-6 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function `get_aligned_data()`)

- **Acceptance Criteria**:
  - [ ] `get_aligned_data()` queries `derived.snapshot_features_v1` (single query)
  - [ ] Removed manual joins of `espn.probabilities_raw_items` + `kalshi.candlesticks`
  - [ ] Removed timestamp alignment logic (canonical dataset already aligned)
  - [ ] Function returns identical data structure (backward compatible)
  - [ ] Query performance < 100ms per game (validated with EXPLAIN ANALYZE)

- **Tasks**:
  - [ ] T1.1.1: Review current `get_aligned_data()` implementation: `scripts/simulate_trading_strategy.py:82-400`
  - [ ] T1.1.2: Review canonical dataset schema: `\d+ derived.snapshot_features_v1`
  - [ ] T1.1.3: Write new query to canonical dataset
  - [ ] T1.1.4: Map canonical dataset columns to simulation data structure
  - [ ] T1.1.5: Handle NULL Kalshi data gracefully (already handled in canonical dataset)
  - [ ] T1.1.6: Test query performance: `EXPLAIN ANALYZE SELECT * FROM derived.snapshot_features_v1 WHERE game_id = '401810095';`
  - [ ] T1.1.7: Replace `get_aligned_data()` implementation
  - [ ] T1.1.8: Remove old alignment logic (keep as comment for reference initially)

- **Test Cases**:
  - [ ] Test query returns expected columns
  - [ ] Test query handles NULL Kalshi data
  - [ ] Test query performance < 100ms for single game
  - [ ] Test data structure matches simulation expectations

- **Evidence to Capture**:
  - Current implementation: (PASTE CODE HERE)
  - New implementation: (PASTE CODE HERE)
  - Query performance: (PASTE EXPLAIN ANALYZE OUTPUT HERE)
  - Column mapping: (PASTE MAPPING TABLE HERE)

#### Story 1.2: Remove Duplicate Alignment Logic

- **ID**: S14-E1-S2
- **Type**: Refactoring
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.1 complete

- **Acceptance Criteria**:
  - [ ] Removed `_get_kalshi_candlestick_data()` function (if no longer needed)
  - [ ] Removed `_get_kalshi_trade_data()` function (if no longer needed)
  - [ ] Removed timestamp alignment logic
  - [ ] Removed manual ESPN/Kalshi join logic
  - [ ] Code is cleaner (fewer lines, single source of truth)

- **Tasks**:
  - [ ] T1.2.1: Identify all duplicate alignment logic
  - [ ] T1.2.2: Verify canonical dataset handles all cases
  - [ ] T1.2.3: Remove duplicate functions
  - [ ] T1.2.4: Remove duplicate alignment logic
  - [ ] T1.2.5: Update comments/documentation

- **Evidence to Capture**:
  - Removed code: (PASTE CODE HERE)
  - Line count reduction: (PASTE BEFORE/AFTER HERE)

#### Story 1.3: Regression Test (Verify Identical Results)

- **ID**: S14-E1-S3
- **Type**: Testing
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.2 complete

- **Acceptance Criteria**:
  - [ ] Simulation produces identical results (same trades, same P&L)
  - [ ] Test on 10 games with both old and new code
  - [ ] All trade results match exactly
  - [ ] All P&L calculations match exactly
  - [ ] Regression test script created

- **Tasks**:
  - [ ] T1.3.1: Create regression test script
  - [ ] T1.3.2: Run simulation on 10 games with old code (save results)
  - [ ] T1.3.3: Run simulation on same 10 games with new code
  - [ ] T1.3.4: Compare results (trades, P&L, timestamps)
  - [ ] T1.3.5: Document any differences (should be none)

- **Test Cases**:
  - [ ] Test 10 games with Kalshi data
  - [ ] Test 5 games without Kalshi data
  - [ ] Test games with different time periods
  - [ ] Verify trade counts match
  - [ ] Verify P&L matches (within rounding tolerance)

- **Evidence to Capture**:
  - Regression test script: (PASTE SCRIPT HERE)
  - Test results: (PASTE RESULTS HERE)
  - Comparison output: (PASTE COMPARISON HERE)

### Epic 2: Integrate Canonical Dataset into Modeling

**Priority**: High (enables signal improvement)
**Estimated Time**: 12-16 hours
**Dependencies**: Can proceed in parallel with Epic 1
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Update `train_winprob_logreg.py` to Query Canonical Dataset

- **ID**: S14-E2-S1
- **Type**: Refactoring
- **Priority**: Critical
- **Estimate**: 6-8 hours
- **Phase**: Phase 2
- **Prerequisites**: None (can proceed in parallel with Epic 1)
- **Files to Modify**: 
  - `scripts/train_winprob_logreg.py`

- **Acceptance Criteria**:
  - [ ] Training script queries `derived.snapshot_features_v1` directly
  - [ ] Removed Parquet file dependency (or made optional)
  - [ ] Features loaded from canonical dataset
  - [ ] Train/validation/test splits handled correctly (by game, not by snapshot)
  - [ ] Training produces identical or better results

- **Tasks**:
  - [ ] T2.1.1: Review current training script: `scripts/train_winprob_logreg.py:74-100`
  - [ ] T2.1.2: Review canonical dataset schema: `\d+ derived.snapshot_features_v1`
  - [ ] T2.1.3: Create `load_training_data()` function to query canonical dataset
  - [ ] T2.1.4: Map canonical dataset columns to model features
  - [ ] T2.1.5: Handle train/validation/test splits (by game, not by snapshot)
  - [ ] T2.1.6: Replace Parquet reading with database query
  - [ ] T2.1.7: Test training pipeline

- **Test Cases**:
  - [ ] Test query returns expected features
  - [ ] Test train/validation/test splits (verify no data leakage)
  - [ ] Test training produces model artifact
  - [ ] Test model performance matches or exceeds baseline

- **Evidence to Capture**:
  - Current implementation: (PASTE CODE HERE)
  - New implementation: (PASTE CODE HERE)
  - Feature mapping: (PASTE MAPPING TABLE HERE)
  - Training output: (PASTE LOGS HERE)

#### Story 2.2: Remove Parquet Dependency (or Make Optional)

- **ID**: S14-E2-S2
- **Type**: Refactoring
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.1 complete

- **Acceptance Criteria**:
  - [ ] Parquet file reading removed (or made optional fallback)
  - [ ] All features come from canonical dataset
  - [ ] Script works without Parquet files
  - [ ] Documentation updated

- **Tasks**:
  - [ ] T2.2.1: Remove Parquet file reading code
  - [ ] T2.2.2: Update command-line arguments (remove `--snapshots-parquet` or make optional)
  - [ ] T2.2.3: Update documentation/comments
  - [ ] T2.2.4: Test script without Parquet files

- **Evidence to Capture**:
  - Removed code: (PASTE CODE HERE)
  - Updated arguments: (PASTE ARGUMENT PARSING HERE)

#### Story 2.3: Validate Feature Mapping

- **ID**: S14-E2-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.1 complete

- **Acceptance Criteria**:
  - [ ] All required features available in canonical dataset
  - [ ] Feature names match model expectations
  - [ ] Feature types correct (numeric, categorical, etc.)
  - [ ] Missing values handled correctly

- **Tasks**:
  - [ ] T2.3.1: List required features for model
  - [ ] T2.3.2: Verify all features exist in canonical dataset
  - [ ] T2.3.3: Verify feature types match expectations
  - [ ] T2.3.4: Test feature loading and validation
  - [ ] T2.3.5: Document feature mapping

- **Evidence to Capture**:
  - Required features list: (PASTE LIST HERE)
  - Canonical dataset features: (PASTE SCHEMA HERE)
  - Feature mapping table: (PASTE TABLE HERE)

#### Story 2.4: Test Training Pipeline

- **ID**: S14-E2-S4
- **Type**: Testing
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.3 complete

- **Acceptance Criteria**:
  - [ ] Training pipeline runs successfully
  - [ ] Model artifact created
  - [ ] Model performance matches or exceeds baseline
  - [ ] Training time acceptable (< 5 minutes for full season)

- **Tasks**:
  - [ ] T2.4.1: Run full training pipeline
  - [ ] T2.4.2: Verify model artifact created
  - [ ] T2.4.3: Compare model performance vs baseline
  - [ ] T2.4.4: Measure training time
  - [ ] T2.4.5: Document results

- **Evidence to Capture**:
  - Training command: (PASTE COMMAND HERE)
  - Training output: (PASTE LOGS HERE)
  - Model performance: (PASTE METRICS HERE)
  - Training time: (PASTE TIMINGS HERE)

### Epic 3: Implement Interaction Terms Model

**Priority**: High (core signal improvement)
**Estimated Time**: 16-20 hours
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Train Model with Interaction Terms

- **ID**: S14-E3-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 8-10 hours
- **Phase**: Phase 3
- **Prerequisites**: Epic 2 complete
- **Files to Create/Modify**: 
  - `scripts/train_winprob_logreg.py` (or new script)

- **Acceptance Criteria**:
  - [ ] Model uses `score_diff_div_sqrt_time_remaining` feature
  - [ ] Model uses additional features: `time_remaining`, `period`, `espn_home_prob_lag_1`, `espn_home_prob_delta_1`
  - [ ] Model trained on canonical dataset
  - [ ] Model artifact saved
  - [ ] Training logs documented

- **Tasks**:
  - [ ] T3.1.1: Review canonical dataset features available
  - [ ] T3.1.2: Select features for interaction terms model
  - [ ] T3.1.3: Update model training code to use interaction terms
  - [ ] T3.1.4: Train model on canonical dataset
  - [ ] T3.1.5: Save model artifact
  - [ ] T3.1.6: Document model architecture

- **Test Cases**:
  - [ ] Test model training completes successfully
  - [ ] Test model uses interaction terms
  - [ ] Test model artifact saved correctly
  - [ ] Test model can make predictions

- **Evidence to Capture**:
  - Model architecture: (PASTE ARCHITECTURE HERE)
  - Features used: (PASTE FEATURE LIST HERE)
  - Training command: (PASTE COMMAND HERE)
  - Training output: (PASTE LOGS HERE)

#### Story 3.2: Apply Platt Scaling

- **ID**: S14-E3-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] Platt scaling applied on validation set
  - [ ] Calibrated probabilities produced
  - [ ] Calibration curve improved
  - [ ] ECE (Expected Calibration Error) reduced

- **Tasks**:
  - [ ] T3.2.1: Review existing Platt scaling code: `scripts/_winprob_lib.py`
  - [ ] T3.2.2: Apply Platt scaling on validation set
  - [ ] T3.2.3: Generate calibration curve
  - [ ] T3.2.4: Calculate ECE
  - [ ] T3.2.5: Compare calibrated vs uncalibrated

- **Evidence to Capture**:
  - Calibration curve: (PASTE PLOT/MEASUREMENTS HERE)
  - ECE before/after: (PASTE METRICS HERE)
  - Platt scaling parameters: (PASTE PARAMETERS HERE)

#### Story 3.3: Validate Signal Metrics

- **ID**: S14-E3-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.2 complete

- **Acceptance Criteria**:
  - [ ] Logloss calculated and compared vs baseline
  - [ ] Brier score calculated and compared vs baseline
  - [ ] ECE calculated and compared vs baseline
  - [ ] Reliability by buckets calculated
  - [ ] Signal metrics improved vs baseline

- **Tasks**:
  - [ ] T3.3.1: Calculate logloss on test set
  - [ ] T3.3.2: Calculate Brier score on test set
  - [ ] T3.3.3: Calculate ECE on test set
  - [ ] T3.3.4: Calculate reliability by buckets
  - [ ] T3.3.5: Compare vs baseline (raw ESPN probabilities)
  - [ ] T3.3.6: Document findings

- **Evidence to Capture**:
  - Signal metrics: (PASTE METRICS TABLE HERE)
  - Baseline comparison: (PASTE COMPARISON HERE)
  - Reliability buckets: (PASTE BUCKETS HERE)

#### Story 3.4: Compare vs Baseline

- **ID**: S14-E3-S4
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.3 complete

- **Acceptance Criteria**:
  - [ ] Baseline model performance documented
  - [ ] Improved model performance documented
  - [ ] Comparison analysis completed
  - [ ] Findings documented

- **Tasks**:
  - [ ] T3.4.1: Load baseline model (raw ESPN probabilities)
  - [ ] T3.4.2: Evaluate baseline on test set
  - [ ] T3.4.3: Evaluate improved model on test set
  - [ ] T3.4.4: Compare metrics (logloss, Brier, ECE)
  - [ ] T3.4.5: Document comparison

- **Evidence to Capture**:
  - Baseline metrics: (PASTE METRICS HERE)
  - Improved metrics: (PASTE METRICS HERE)
  - Comparison analysis: (PASTE ANALYSIS HERE)

### Epic 4: Validate Improved Signal

**Priority**: High (confirms signal improvement)
**Estimated Time**: 8-12 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Run Grid Search with Improved Signal

- **ID**: S14-E4-S1
- **Type**: Validation
- **Priority**: Critical
- **Estimate**: 4-6 hours
- **Phase**: Phase 4
- **Prerequisites**: Epic 3 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py` (or create new script)

- **Acceptance Criteria**:
  - [ ] Grid search runs with improved signal (interaction terms model)
  - [ ] Grid search completes successfully
  - [ ] Results stored and documented
  - [ ] Performance metrics calculated

- **Tasks**:
  - [ ] T4.1.1: Update grid search to use improved signal
  - [ ] T4.1.2: Run grid search with improved signal
  - [ ] T4.1.3: Store results
  - [ ] T4.1.4: Calculate performance metrics
  - [ ] T4.1.5: Document results

- **Evidence to Capture**:
  - Grid search command: (PASTE COMMAND HERE)
  - Grid search results: (PASTE RESULTS HERE)
  - Performance metrics: (PASTE METRICS HERE)

#### Story 4.2: Compare Trading Metrics vs Baseline

- **ID**: S14-E4-S2
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: Story 4.1 complete

- **Acceptance Criteria**:
  - [ ] Baseline grid search results loaded
  - [ ] Improved grid search results loaded
  - [ ] Trading metrics compared (net profit, trade count, win rate)
  - [ ] Comparison analysis completed

- **Tasks**:
  - [ ] T4.2.1: Load baseline grid search results
  - [ ] T4.2.2: Load improved grid search results
  - [ ] T4.2.3: Compare net profit
  - [ ] T4.2.4: Compare trade count
  - [ ] T4.2.5: Compare win rate
  - [ ] T4.2.6: Document comparison

- **Evidence to Capture**:
  - Baseline metrics: (PASTE METRICS HERE)
  - Improved metrics: (PASTE METRICS HERE)
  - Comparison table: (PASTE TABLE HERE)

#### Story 4.3: Document Findings

- **ID**: S14-E4-S3
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: Story 4.2 complete

- **Acceptance Criteria**:
  - [ ] Findings documented in analysis document
  - [ ] Signal improvement quantified
  - [ ] Trading performance improvement quantified
  - [ ] Next steps identified

- **Tasks**:
  - [ ] T4.3.1: Update analysis document with findings
  - [ ] T4.3.2: Document signal metrics improvement
  - [ ] T4.3.3: Document trading metrics improvement
  - [ ] T4.3.4: Identify next steps
  - [ ] T4.3.5: Create completion report

- **Evidence to Capture**:
  - Updated analysis document: (PASTE UPDATES HERE)
  - Completion report: (PASTE REPORT HERE)

## Risk Management

### Technical Risks

1. **Risk**: Data structure mismatch between canonical dataset and simulation expectations
   - **Mitigation**: Regression test to verify identical results
   - **Contingency**: Map canonical dataset columns to simulation structure

2. **Risk**: Performance regression (queries slower than expected)
   - **Mitigation**: Materialized view is pre-computed, should be fast
   - **Contingency**: Add more indexes if needed

3. **Risk**: Model training issues (interaction terms may not improve signal)
   - **Mitigation**: Validate on held-out games, compare to baseline
   - **Contingency**: Try different interaction terms or model architectures

### Data Risks

1. **Risk**: Canonical dataset refresh needed
   - **Mitigation**: Document refresh strategy
   - **Contingency**: Manual refresh command exists

2. **Risk**: Missing Kalshi data (NULL in canonical dataset)
   - **Mitigation**: Canonical dataset already handles NULL gracefully
   - **Contingency**: Simulation already handles missing Kalshi data

### Integration Risks

1. **Risk**: Backward compatibility issues
   - **Mitigation**: Regression tests, gradual migration
   - **Contingency**: Keep old code path as fallback initially

2. **Risk**: Feature mapping issues
   - **Mitigation**: Create mapping layer, validate feature names
   - **Contingency**: Add feature transformation layer if needed

## Success Metrics

- [ ] **Integration**: 100% of modeling/simulation scripts use canonical dataset
- [ ] **Signal Quality**: Improved logloss/Brier vs baseline (target: 5-10% improvement)
- [ ] **Performance**: Simulation queries < 100ms per game
- [ ] **Code Quality**: No duplicate alignment logic remains
- [ ] **Trading Performance**: Improved net profit vs baseline (target: 10-20% improvement)

## Definition of Done

- [ ] All stories completed and tested
- [ ] Canonical dataset integrated into simulation
- [ ] Canonical dataset integrated into modeling
- [ ] Interaction terms model implemented and validated
- [ ] Grid search shows improved profitability
- [ ] Regression tests pass
- [ ] Performance requirements met
- [ ] Documentation updated
- [ ] Code follows project standards
- [ ] Sprint review completed

## Post-Sprint Follow-up

- Next sprint: Consider CatBoost model if interaction terms show promise
- Future: Add more features (rolling statistics, additional interaction terms)
- Future: Automated canonical dataset refresh after data ingestion

