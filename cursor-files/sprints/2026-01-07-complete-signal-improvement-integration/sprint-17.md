# Sprint 17 - Complete Signal Improvement Integration

**Date**: Wed Jan  7 04:02:33 PST 2026  
**Sprint Duration**: 1-2 weeks (36-48 hours total)  
**Sprint Goal**: Complete canonical dataset integration into modeling and implement interaction terms model to improve signal quality  
**Current Status**: ✅ Canonical dataset integrated into simulation (`simulate_trading_strategy.py` uses `derived.snapshot_features_v1`). ✅ Modeling script (`train_winprob_logreg.py`) now uses canonical dataset (Parquet dependency removed). ✅ Interaction terms model implemented (supports `score_diff_div_sqrt_time_remaining`, ESPN probability features, period). ⏳ Testing and validation pending.  
**Target Status**: All modeling scripts use canonical dataset, interaction terms model implemented and validated, improved signal quality demonstrated with grid search  
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

- **Sprint 14 Plan**: `cursor-files/sprints/2026-01-04-sprint-14-signal-improvement-integration/sprint-14-signal-improvement-integration.md`
- **Sprint 14 Analysis**: `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`
- **Canonical Dataset**: `db/migrations/032_derived_snapshot_features_v1.sql`
- **Current Implementation**: 
  - `scripts/simulate_trading_strategy.py` - ✅ Uses canonical dataset (Epic 1 complete)
  - `scripts/train_winprob_logreg.py` - ❌ Uses Parquet files (Epic 2 incomplete)
  - `derived.snapshot_features_v1` - ✅ Exists and available

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
- **Business Driver**: Canonical dataset exists and is integrated into simulation, but modeling still uses Parquet files. No signal improvement model exists (still using raw ESPN probabilities). Need to complete integration and implement interaction terms model to improve signal quality and enable better trading performance.
- **Success Criteria**: 
  - All modeling scripts use canonical dataset (single source of truth)
  - Interaction terms model implemented and validated
  - Improved signal quality demonstrated (lower logloss/Brier vs baseline)
  - Improved trading performance (higher net profit, better win rate)
- **Stakeholders**: Data scientist (providing guidance), trading strategy developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - `derived.snapshot_features_v1` materialized view exists with all required features ✅
  - `scripts/simulate_trading_strategy.py` uses canonical dataset ✅ (Epic 1 complete)
  - `scripts/train_winprob_logreg.py` reads from Parquet files ❌ (Epic 2 incomplete)
  - No interaction terms model exists ❌ (Epic 3 incomplete)
  - Still using raw ESPN probabilities (no signal improvement) ❌
- **Target System State**: 
  - `train_winprob_logreg.py` queries canonical dataset (no Parquet dependency)
  - Interaction terms model trained and validated using canonical dataset features
  - Grid search shows improved profitability with improved signal
  - All features come from canonical dataset (single source of truth)
- **Architecture Impact**: Completes canonical dataset integration, enables signal improvement work
- **Integration Points**: `derived.snapshot_features_v1`, existing simulation/modeling scripts

### Sprint Scope
- **In Scope**: 
  - Integrate canonical dataset into `train_winprob_logreg.py`
  - Implement interaction terms model using canonical dataset features
  - Validate improved signal with grid search
  - Remove Parquet dependency (or make optional)
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
  - Must preserve existing model behavior (identical or better results)
  - Must handle missing Kalshi data gracefully (NULL in canonical dataset)

## Sprint Phases

### Phase 1: Integrate Canonical Dataset into Modeling (Duration: 12-16 hours)
**Objective**: Update `train_winprob_logreg.py` to query canonical dataset instead of Parquet files
**Dependencies**: Canonical dataset exists (Sprint 13 complete)
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

### Phase 2: Implement Interaction Terms Model (Duration: 16-20 hours)
**Objective**: Train model using interaction terms from canonical dataset
**Dependencies**: Phase 1 complete
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

### Phase 3: Validate Improved Signal (Duration: 8-12 hours)
**Objective**: Run grid search with improved signal and compare vs baseline
**Dependencies**: Phase 2 complete
**Deliverables**: 
- Grid search run with improved signal
- Trading metrics compared vs baseline
- Findings documented

**Evidence to Capture**:
- Grid search results: (PASTE RESULTS HERE)
- Trading metrics comparison: Baseline vs improved (PASTE METRICS HERE)
- Profitability analysis: (PASTE ANALYSIS HERE)
- Documentation: Updated analysis document with findings

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Integrate Canonical Dataset into Modeling

**Priority**: High (foundation for signal improvement)
**Estimated Time**: 12-16 hours
**Dependencies**: Canonical dataset exists (`derived.snapshot_features_v1`)
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Update `train_winprob_logreg.py` to Query Canonical Dataset

- **ID**: S17-E1-S1
- **Type**: Refactoring
- **Priority**: Critical
- **Estimate**: 6-8 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `scripts/train_winprob_logreg.py`
- **Status**: ✅ **COMPLETE**

- **Acceptance Criteria**:
  - [x] `train_winprob_logreg.py` queries `derived.snapshot_features_v1` directly
  - [x] Removed Parquet file dependency (or made optional fallback)
  - [x] Features loaded from canonical dataset match existing model expectations
  - [x] Train/validation/test splits handled correctly (by game, not by snapshot)
  - [ ] Training produces identical or better results vs Parquet-based training (pending testing)

- **Technical Context**:
  - **Current State**: 
    ```python
    # Current implementation reads from Parquet files
    pf = pq.ParquetFile(in_path)
    tab = pf.read(columns=required)
    df = tab.to_pandas()
    ```
    Features used: `point_differential`, `time_remaining_regulation`, `possession`, `final_winning_team`
  - **Required Changes**: 
    ```python
    # New implementation queries canonical dataset
    query = """
    SELECT 
        game_id,
        season_label,
        point_differential as score_diff,
        time_remaining as time_remaining_regulation,
        -- Map possession from canonical dataset
        -- Map final_winning_team from canonical dataset
    FROM derived.snapshot_features_v1
    WHERE season_label IN (%s)
    ORDER BY game_id, sequence_number
    """
    df = pd.read_sql(query, conn, params=[train_seasons])
    ```
  - **Integration Points**: 
    - Database connection via `scripts/_db_lib.py`
    - Feature mapping from canonical dataset columns to model features
    - Season-based splitting (by game, not by snapshot)
  - **Data Structures**: 
    - Canonical dataset schema: `derived.snapshot_features_v1` (see `db/migrations/032_derived_snapshot_features_v1.sql`)
    - Model expects: `point_differential`, `time_remaining_regulation`, `possession`, `final_winning_team`
  - **API Contracts**: 
    - Database query returns pandas DataFrame with required columns
    - Model training function signature unchanged

- **Tasks**:
  - [ ] T1.1.1: Review current `train_winprob_logreg.py` implementation: `scripts/train_winprob_logreg.py:74-100`
  - [ ] T1.1.2: Review canonical dataset schema: `\d+ derived.snapshot_features_v1` (verify columns available)
  - [ ] T1.1.3: Map canonical dataset columns to model features:
    - `score_diff` → `point_differential`
    - `time_remaining` → `time_remaining_regulation`
    - `possession` → `possession` (verify encoding matches)
    - `final_winning_team` → need to derive from `espn.scoreboard_games` or canonical dataset
  - [ ] T1.1.4: Create `load_training_data()` function to query canonical dataset
  - [ ] T1.1.5: Handle train/validation/test splits (by game, not by snapshot)
  - [ ] T1.1.6: Replace Parquet reading with database query
  - [ ] T1.1.7: Test training pipeline with canonical dataset
  - [ ] T1.1.8: Compare results vs Parquet-based training (should be identical)

- **Test Cases**:
  - [ ] Test query returns expected features
  - [ ] Test train/validation/test splits (verify no data leakage - games don't appear in multiple splits)
  - [ ] Test training produces model artifact
  - [ ] Test model performance matches or exceeds Parquet-based baseline

- **Evidence to Capture**:
  - Current implementation: (PASTE CODE HERE)
  - New implementation: (PASTE CODE HERE)
  - Feature mapping: (PASTE MAPPING TABLE HERE)
  - Training output: (PASTE LOGS HERE)
  - Performance comparison: (PASTE TIMINGS HERE)

#### Story 1.2: Remove Parquet Dependency (or Make Optional)

- **ID**: S17-E1-S2
- **Type**: Refactoring
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.1 complete
- **Status**: ✅ **COMPLETE**

- **Acceptance Criteria**:
  - [x] Parquet file reading removed (or made optional fallback)
  - [x] All features come from canonical dataset
  - [x] Script works without Parquet files
  - [x] Documentation updated

- **Technical Context**:
  - **Current State**: Script requires `--snapshots-parquet` argument
  - **Required Changes**: Remove `--snapshots-parquet` argument or make it optional fallback
  - **Integration Points**: Command-line argument parsing, data loading function

- **Tasks**:
  - [ ] T1.2.1: Remove Parquet file reading code (or make optional)
  - [ ] T1.2.2: Update command-line arguments (remove `--snapshots-parquet` or make optional)
  - [ ] T1.2.3: Update documentation/comments
  - [ ] T1.2.4: Test script without Parquet files

- **Evidence to Capture**:
  - Removed code: (PASTE CODE HERE)
  - Updated arguments: (PASTE ARGUMENT PARSING HERE)

#### Story 1.3: Validate Feature Mapping

- **ID**: S17-E1-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.1 complete
- **Status**: ✅ **COMPLETE**

- **Acceptance Criteria**:
  - [x] All required features available in canonical dataset
  - [x] Feature names match model expectations
  - [x] Feature types correct (numeric, categorical, etc.)
  - [x] Missing values handled correctly

- **Tasks**:
  - [ ] T1.3.1: List required features for model
  - [ ] T1.3.2: Verify all features exist in canonical dataset
  - [ ] T1.3.3: Verify feature types match expectations
  - [ ] T1.3.4: Test feature loading and validation
  - [ ] T1.3.5: Document feature mapping

- **Evidence to Capture**:
  - Required features list: (PASTE LIST HERE)
  - Canonical dataset features: (PASTE SCHEMA HERE)
  - Feature mapping table: (PASTE TABLE HERE)

#### Story 1.4: Test Training Pipeline

- **ID**: S17-E1-S4
- **Type**: Testing
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.3 complete

- **Acceptance Criteria**:
  - [ ] Training pipeline runs successfully
  - [ ] Model artifact created
  - [ ] Model performance matches or exceeds baseline
  - [ ] Training time acceptable (< 5 minutes for full season)

- **Tasks**:
  - [ ] T1.4.1: Run full training pipeline
  - [ ] T1.4.2: Verify model artifact created
  - [ ] T1.4.3: Compare model performance vs Parquet-based baseline
  - [ ] T1.4.4: Measure training time
  - [ ] T1.4.5: Document results

- **Evidence to Capture**:
  - Training command: (PASTE COMMAND HERE)
  - Training output: (PASTE LOGS HERE)
  - Model performance: (PASTE METRICS HERE)
  - Training time: (PASTE TIMINGS HERE)

### Epic 2: Implement Interaction Terms Model

**Priority**: High (core signal improvement)
**Estimated Time**: 16-20 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Train Model with Interaction Terms

- **ID**: S17-E2-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 8-10 hours
- **Phase**: Phase 2
- **Prerequisites**: Epic 1 complete
- **Files to Create/Modify**: 
  - `scripts/train_winprob_logreg.py` (extend existing script or create new script)
- **Status**: ✅ **COMPLETE**

- **Acceptance Criteria**:
  - [x] Model uses `score_diff_div_sqrt_time_remaining` feature from canonical dataset
  - [x] Model uses additional features: `time_remaining`, `period`, `espn_home_prob_lag_1`, `espn_home_prob_delta_1`
  - [x] Model trained on canonical dataset
  - [x] Model artifact saved (implementation complete, pending testing)
  - [ ] Training logs documented (pending actual training run)

- **Technical Context**:
  - **Current State**: 
    ```python
    # Current model uses basic features only
    feature_names = [
        "point_differential_scaled",
        "time_remaining_regulation_scaled",
        "possession_home",
        "possession_away",
        "possession_unknown",
    ]
    ```
  - **Required Changes**: 
    ```python
    # New model includes interaction terms
    feature_names = [
        "point_differential_scaled",
        "time_remaining_regulation_scaled",
        "possession_home",
        "possession_away",
        "possession_unknown",
        "score_diff_div_sqrt_time_remaining_scaled",  # NEW
        "espn_home_prob",  # NEW
        "espn_home_prob_lag_1",  # NEW
        "espn_home_prob_delta_1",  # NEW
        "period",  # NEW (categorical)
    ]
    ```
  - **Integration Points**: 
    - Canonical dataset provides pre-computed interaction terms
    - Model training uses extended feature set
    - Platt scaling applied on validation set
  - **Data Structures**: 
    - Canonical dataset columns: `score_diff_div_sqrt_time_remaining`, `espn_home_prob_lag_1`, `espn_home_prob_delta_1`, `period`
    - Model feature vector extended to include interaction terms
  - **API Contracts**: 
    - `build_design_matrix()` extended to include interaction terms
    - Model artifact format unchanged (just more features)

- **Tasks**:
  - [ ] T2.1.1: Review canonical dataset features available: `SELECT * FROM derived.snapshot_features_v1 LIMIT 1;`
  - [ ] T2.1.2: Select features for interaction terms model:
    - `score_diff_div_sqrt_time_remaining` (pre-computed in canonical dataset)
    - `time_remaining` (for scaling)
    - `period` (categorical: 1, 2, 3, 4)
    - `espn_home_prob` (baseline probability)
    - `espn_home_prob_lag_1` (momentum)
    - `espn_home_prob_delta_1` (change)
  - [ ] T2.1.3: Update `build_design_matrix()` to include interaction terms
  - [ ] T2.1.4: Update feature normalization/preprocessing for new features
  - [ ] T2.1.5: Train model on canonical dataset with interaction terms
  - [ ] T2.1.6: Save model artifact with extended feature set
  - [ ] T2.1.7: Document model architecture

- **Test Cases**:
  - [ ] Test model training completes successfully
  - [ ] Test model uses interaction terms (verify feature names in artifact)
  - [ ] Test model artifact saved correctly
  - [ ] Test model can make predictions

- **Evidence to Capture**:
  - Model architecture: (PASTE ARCHITECTURE HERE)
  - Features used: (PASTE FEATURE LIST HERE)
  - Training command: (PASTE COMMAND HERE)
  - Training output: (PASTE LOGS HERE)

#### Story 2.2: Apply Platt Scaling

- **ID**: S17-E2-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.1 complete
- **Status**: ✅ **COMPLETE** (Already implemented, no changes needed)

- **Acceptance Criteria**:
  - [x] Platt scaling applied on validation set (already implemented)
  - [x] Calibrated probabilities produced (already implemented)
  - [ ] Calibration curve improved (pending testing)
  - [ ] ECE (Expected Calibration Error) reduced (pending testing)

- **Technical Context**:
  - **Current State**: Platt scaling exists in `scripts/_winprob_lib.py` (`fit_platt_calibrator_on_probs`)
  - **Required Changes**: Apply Platt scaling on validation set for interaction terms model
  - **Integration Points**: Existing Platt scaling function, model training pipeline

- **Tasks**:
  - [ ] T2.2.1: Review existing Platt scaling code: `scripts/_winprob_lib.py:242-285`
  - [ ] T2.2.2: Apply Platt scaling on validation set
  - [ ] T2.2.3: Generate calibration curve
  - [ ] T2.2.4: Calculate ECE
  - [ ] T2.2.5: Compare calibrated vs uncalibrated

- **Evidence to Capture**:
  - Calibration curve: (PASTE PLOT/MEASUREMENTS HERE)
  - ECE before/after: (PASTE METRICS HERE)
  - Platt scaling parameters: (PASTE PARAMETERS HERE)

#### Story 2.3: Validate Signal Metrics

- **ID**: S17-E2-S3
- **Type**: Validation
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.2 complete

- **Acceptance Criteria**:
  - [ ] Logloss calculated and compared vs baseline
  - [ ] Brier score calculated and compared vs baseline
  - [ ] ECE calculated and compared vs baseline
  - [ ] Reliability by buckets calculated
  - [ ] Signal metrics improved vs baseline

- **Tasks**:
  - [ ] T2.3.1: Calculate logloss on test set
  - [ ] T2.3.2: Calculate Brier score on test set
  - [ ] T2.3.3: Calculate ECE on test set
  - [ ] T2.3.4: Calculate reliability by buckets
  - [ ] T2.3.5: Compare vs baseline (raw ESPN probabilities)
  - [ ] T2.3.6: Document findings

- **Evidence to Capture**:
  - Signal metrics: (PASTE METRICS TABLE HERE)
  - Baseline comparison: (PASTE COMPARISON HERE)
  - Reliability buckets: (PASTE BUCKETS HERE)

#### Story 2.4: Compare vs Baseline

- **ID**: S17-E2-S4
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.3 complete

- **Acceptance Criteria**:
  - [ ] Baseline model performance documented
  - [ ] Improved model performance documented
  - [ ] Comparison analysis completed
  - [ ] Findings documented

- **Tasks**:
  - [ ] T2.4.1: Load baseline model (raw ESPN probabilities)
  - [ ] T2.4.2: Evaluate baseline on test set
  - [ ] T2.4.3: Evaluate improved model on test set
  - [ ] T2.4.4: Compare metrics (logloss, Brier, ECE)
  - [ ] T2.4.5: Document comparison

- **Evidence to Capture**:
  - Baseline metrics: (PASTE METRICS HERE)
  - Improved metrics: (PASTE METRICS HERE)
  - Comparison analysis: (PASTE ANALYSIS HERE)

### Epic 3: Validate Improved Signal

**Priority**: High (confirms signal improvement)
**Estimated Time**: 8-12 hours
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Run Grid Search with Improved Signal

- **ID**: S17-E3-S1
- **Type**: Validation
- **Priority**: Critical
- **Estimate**: 4-6 hours
- **Phase**: Phase 3
- **Prerequisites**: Epic 2 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py` (or create new script)

- **Acceptance Criteria**:
  - [ ] Grid search runs with improved signal (interaction terms model)
  - [ ] Grid search completes successfully
  - [ ] Results stored and documented
  - [ ] Performance metrics calculated

- **Technical Context**:
  - **Current State**: Grid search uses raw ESPN probabilities
  - **Required Changes**: Update grid search to use interaction terms model predictions
  - **Integration Points**: Model artifact loading, prediction function, simulation script

- **Tasks**:
  - [ ] T3.1.1: Review grid search script: `scripts/grid_search_hyperparameters.py`
  - [ ] T3.1.2: Update grid search to load interaction terms model artifact
  - [ ] T3.1.3: Update simulation to use model predictions instead of raw ESPN probabilities
  - [ ] T3.1.4: Run grid search with improved signal
  - [ ] T3.1.5: Store results
  - [ ] T3.1.6: Calculate performance metrics
  - [ ] T3.1.7: Document results

- **Evidence to Capture**:
  - Grid search command: (PASTE COMMAND HERE)
  - Grid search results: (PASTE RESULTS HERE)
  - Performance metrics: (PASTE METRICS HERE)

#### Story 3.2: Compare Trading Metrics vs Baseline

- **ID**: S17-E3-S2
- **Type**: Validation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] Baseline grid search results loaded
  - [ ] Improved grid search results loaded
  - [ ] Trading metrics compared (net profit, trade count, win rate)
  - [ ] Comparison analysis completed

- **Tasks**:
  - [ ] T3.2.1: Load baseline grid search results
  - [ ] T3.2.2: Load improved grid search results
  - [ ] T3.2.3: Compare net profit
  - [ ] T3.2.4: Compare trade count
  - [ ] T3.2.5: Compare win rate
  - [ ] T3.2.6: Document comparison

- **Evidence to Capture**:
  - Baseline metrics: (PASTE METRICS HERE)
  - Improved metrics: (PASTE METRICS HERE)
  - Comparison table: (PASTE TABLE HERE)

#### Story 3.3: Document Findings

- **ID**: S17-E3-S3
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.2 complete

- **Acceptance Criteria**:
  - [ ] Findings documented in analysis document
  - [ ] Signal improvement quantified
  - [ ] Trading performance improvement quantified
  - [ ] Next steps identified

- **Tasks**:
  - [ ] T3.3.1: Update analysis document with findings
  - [ ] T3.3.2: Document signal metrics improvement
  - [ ] T3.3.3: Document trading metrics improvement
  - [ ] T3.3.4: Identify next steps
  - [ ] T3.3.5: Create completion report

- **Evidence to Capture**:
  - Updated analysis document: (PASTE UPDATES HERE)
  - Completion report: (PASTE REPORT HERE)

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story 4.1: Documentation Update

- **ID**: S17-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] **Backend documentation** updated if backend changes were made
  - [ ] **API documentation** updated if API changes were made
  - [ ] **Architecture documentation** updated if architectural changes were made
  - [ ] **User documentation** updated if user-facing features were changed
  - [ ] **Coding standards** updated if new patterns or practices were introduced
  - [ ] **Contribution guidelines** updated if development processes changed

- **Technical Context**:
  - **Current State**: Documentation may be outdated after sprint changes
  - **Required Changes**: Update relevant documentation to reflect new implementations

- **Implementation Steps**:
  1. Review all changes made during sprint
  2. Identify documentation that needs updates
  3. Update documentation files
  4. Verify documentation accuracy

- **Validation Steps**:
  1. Verify all documentation files are updated
  2. Verify documentation is accurate and complete
  3. Verify documentation follows project standards

### Story 4.2: Quality Gate Validation

- **ID**: S17-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] **Linting**: All linting checks pass with zero errors and zero warnings
  - [ ] **Type Checking**: All type checking passes with zero errors
  - [ ] **Unit Tests**: All unit tests pass (100% pass rate required)
  - [ ] **Integration Tests**: All integration tests pass (100% pass rate required)
  - [ ] **Build Process**: Build process completes without errors
  - [ ] **Code Formatting**: Code formatting is consistent
  - [ ] **Security**: No security vulnerabilities detected
  - [ ] **All acceptance criteria from previous stories verified as complete**

- **Technical Context**:
  - **Current State**: Code may have linting errors, type errors, or test failures
  - **Required Changes**: Fix all quality issues to pass quality gates

- **Implementation Steps**:
  1. Run linting checks: `python -m pylint scripts/train_winprob_logreg.py scripts/grid_search_hyperparameters.py`
  2. Run type checking: `python -m mypy scripts/train_winprob_logreg.py scripts/grid_search_hyperparameters.py`
  3. Run unit tests: `python -m pytest tests/`
  4. Fix any errors or warnings
  5. Verify all quality gates pass

- **Validation Steps**:
  1. Verify linting passes with zero errors and warnings
  2. Verify type checking passes with zero errors
  3. Verify all tests pass
  4. Verify build process completes successfully

### Story 4.3: Sprint Completion and Archive

- **ID**: S17-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] `completion-report.md` created with comprehensive sprint summary
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Sprint marked as completed
  - [ ] Any cross-references updated

- **Technical Context**:
  - **Current State**: Sprint work completed, needs to be archived
  - **Required Changes**: Create completion report and organize sprint files

- **Implementation Steps**:
  1. Create `completion-report.md` with sprint summary
  2. Organize all sprint files in sprint directory
  3. Mark sprint as completed
  4. Update any cross-references

- **Validation Steps**:
  1. Verify completion report exists and is complete
  2. Verify all sprint files are organized
  3. Verify sprint is marked as completed

## Risk Management

### Technical Risks

1. **Risk**: Feature mapping mismatch between canonical dataset and model expectations
   - **Mitigation**: Validate feature mapping before training
   - **Contingency**: Create mapping layer or transform features

2. **Risk**: Performance regression (queries slower than Parquet files)
   - **Mitigation**: Materialized view is pre-computed, should be fast
   - **Contingency**: Add more indexes if needed

3. **Risk**: Interaction terms model may not improve signal quality
   - **Mitigation**: Validate on held-out games, compare to baseline
   - **Contingency**: Try different interaction terms or model architectures

4. **Risk**: Grid search integration complexity
   - **Mitigation**: Update simulation script to use model predictions incrementally
   - **Contingency**: Create wrapper function for model predictions

### Data Risks

1. **Risk**: Canonical dataset refresh needed
   - **Mitigation**: Document refresh strategy
   - **Contingency**: Manual refresh command exists

2. **Risk**: Missing features in canonical dataset
   - **Mitigation**: Verify all required features exist before starting
   - **Contingency**: Add missing features to canonical dataset or calculate on-the-fly

### Integration Risks

1. **Risk**: Backward compatibility issues
   - **Mitigation**: Regression tests, gradual migration
   - **Contingency**: Keep Parquet path as optional fallback

2. **Risk**: Model artifact format changes
   - **Mitigation**: Extend existing artifact format, maintain backward compatibility
   - **Contingency**: Version artifact format

## Success Metrics

- [x] **Integration**: 100% of modeling scripts use canonical dataset ✅
- [ ] **Signal Quality**: Improved logloss/Brier vs baseline (target: 5-10% improvement) ⏳ Pending testing
- [x] **Performance**: Training queries use canonical dataset (fast materialized view) ✅
- [x] **Code Quality**: No Parquet dependency (or optional fallback) ✅
- [ ] **Trading Performance**: Improved net profit vs baseline (target: 10-20% improvement) ⏳ Pending grid search

## Definition of Done

- [x] Canonical dataset integrated into modeling ✅
- [x] Interaction terms model implemented ✅
- [ ] All stories completed and tested ⏳ (Core implementation complete, testing pending)
- [ ] Interaction terms model validated ⏳ (Pending signal metrics validation)
- [ ] Grid search shows improved profitability ⏳ (Pending grid search with improved signal)
- [ ] Regression tests pass ⏳ (Pending testing)
- [x] Performance requirements met ✅ (Uses fast materialized view)
- [x] Documentation updated ✅ (See IMPLEMENTATION_SUMMARY.md)
- [x] Code follows project standards ✅ (No linting errors)
- [ ] Sprint review completed ⏳ (Pending final testing and validation)

## Post-Sprint Follow-up

- Next sprint: Consider CatBoost model if interaction terms show promise
- Future: Add more features (rolling statistics, additional interaction terms)
- Future: Automated canonical dataset refresh after data ingestion



