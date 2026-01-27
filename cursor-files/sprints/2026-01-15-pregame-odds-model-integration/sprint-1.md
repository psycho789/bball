# Sprint 1: Pre-Game Odds Model Integration - CatBoost Implementation

**Date**: Thu Jan 15 06:23:31 PST 2026  
**Sprint Duration**: 5 days (13-15 hours total)  
**Sprint Goal**: Integrate opening sportsbook odds into CatBoost win-probability model training pipeline, enabling models to leverage pre-game market consensus for improved prediction accuracy. Success criteria: (1) Opening odds features added to `build_design_matrix()` and training scripts, (2) Models train successfully with opening odds (handling NULL values), (3) Time-bucketed evaluation shows improved performance in early-game buckets, (4) Feature importance shows opening odds contribute meaningfully.  
**Current Status**: Opening odds are available in `derived.snapshot_features_v1` (migration 039 completed) but not used in model training. Training scripts (`train_winprob_catboost.py`, `train_winprob_logreg.py`) query ESPN tables directly, bypassing canonical dataset. `build_design_matrix()` function in `scripts/lib/_winprob_lib.py` does not accept opening odds parameters.  
**Target Status**: CatBoost model training pipeline includes opening odds features (de-vigged fair probabilities, overround, spread, total, missingness indicators). Models train successfully with opening odds, showing improved Brier score and log-loss on test set, especially in early-game time buckets (2880-2400s, 2400-1800s). Feature importance analysis shows opening odds features in top 50% of feature importance.  
**Team Size**: 1 developer  
**Sprint Lead**: Adam  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline
- **Test Results**: [TODO: Run test suite and record pass rate]
- **QC Results**: [TODO: Run QC checks and record results]
- **Code Coverage**: [TODO: Run coverage analysis]
- **Build Status**: [TODO: Verify build status]

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
- **Business Driver**: Opening odds represent pre-game market consensus (sportsbooks' best estimate before the game starts), but this valuable signal is currently ignored by models. Integrating opening odds should improve win probability predictions, especially early in games, leading to better trading decisions and improved grid search results.
- **Success Criteria**: (1) Models with opening odds show 5-10% improvement in Brier score / log-loss globally, (2) Early-game buckets (2880-2400s, 2400-1800s) show 10-15% improvement, (3) Opening odds features in top 50% of CatBoost feature importance, (4) Grid search results show improved expected value or win rate.
- **Stakeholders**: Data scientist (dta) - provided recommendations, Adam - implementing sprint
- **Timeline Constraints**: None (no hard deadlines)

### Technical Context
- **Current System State**: 
  - Opening odds available in `derived.snapshot_features_v1` via columns: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total` (migration 039 completed)
  - Training scripts (`scripts/model/train_winprob_catboost.py`, `scripts/model/train_winprob_logreg.py`) query ESPN tables directly, not canonical dataset
  - `build_design_matrix()` function in `scripts/lib/_winprob_lib.py` does not accept opening odds parameters
  - Current features: `point_differential`, `time_remaining_regulation`, `possession`, plus optional interaction terms
- **Target System State**: 
  - `build_design_matrix()` accepts opening odds parameters: `opening_prob_home_fair`, `opening_overround`, `opening_spread`, `opening_total`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - `train_winprob_catboost.py` loads opening odds from canonical dataset (after parity validation), converts to fair probabilities with safety checks, passes to `build_design_matrix()`
  - Models train successfully with opening odds (CatBoost handles NaNs natively)
  - Time-bucketed evaluation shows improved performance in early-game buckets
- **Architecture Impact**: Minimal - adds features to existing pipeline, backward compatible (opening odds can be NULL)
- **Integration Points**: 
  - `scripts/lib/_winprob_lib.py` (design matrix construction)
  - `scripts/model/train_winprob_catboost.py` (training data loading, training set design matrix, calibration set design matrix, feature_names list)
  - `scripts/model/precompute_model_probabilities.py` (model scoring for grid search - SQL query, score_snapshot function)
  - `derived.snapshot_features_v1` (canonical dataset with opening odds)

### Sprint Scope
- **In Scope**: 
  - Parity validation (ESPN-direct vs canonical dataset)
  - Opening odds feature engineering (de-vigging with safety checks)
  - CatBoost model integration (add opening odds to training pipeline: build_design_matrix, training set, calibration set, feature_names)
  - Pre-computation script integration (add opening odds to scoring pipeline for grid search compatibility)
  - Model training and evaluation (with/without opening odds comparison)
  - Time-bucketed evaluation (Brier score, log-loss by time bucket)
- **Out of Scope**: 
  - Logistic Regression integration (deferred per data scientist recommendation)
  - Decay-weighted interaction terms for Logistic Regression (not needed for CatBoost)
  - Grid search integration (deferred to future sprint)
  - Evaluation script (`evaluate_winprob_model.py`) updates (deferred - evaluation script loads from ESPN tables directly, would need to switch to canonical dataset or add opening odds to ESPN query; can be done as follow-up if needed for evaluating models trained with opening odds)
- **Assumptions**: 
  - Parity validation passes (canonical dataset contains equivalent universe to ESPN-direct)
  - Opening odds coverage is sufficient (80%+ of games) for meaningful model improvement
  - CatBoost can discover optimal interactions automatically (no manual interaction engineering needed)
- **Constraints**: 
  - Must validate parity before switching to canonical dataset
  - Must handle NULL opening odds gracefully (CatBoost handles missing natively)
  - Must maintain backward compatibility (existing models without opening odds still work)

## Sprint Phases

### Phase 1: Parity Validation (Duration: 1-2 hours)
**Objective**: Validate that `derived.snapshot_features_v1` contains equivalent universe of games and snapshots as ESPN-direct training query before switching data sources.
**Dependencies**: Database access via `DATABASE_URL`, understanding of ESPN-direct training query structure
**Deliverables**: Parity validation report with game/snapshot counts per season, distribution comparison, and go/no-go decision

### Phase 2: Feature Engineering Implementation (Duration: 3-4 hours)
**Objective**: Validate odds format, create shared de-vigging helper function, and implement opening odds feature engineering in training data loading function.
**Dependencies**: Phase 1 complete (parity validated), understanding of opening odds data structure
**Deliverables**: Odds format validation report, shared `compute_opening_odds_features()` helper function, modified `_load_training_data()` function using helper

### Phase 3: Design Matrix and Training Integration (Duration: 4-5 hours)
**Objective**: Integrate opening odds features into `build_design_matrix()`, CatBoost training pipeline, and pre-computation script.
**Dependencies**: Phase 2 complete
**Deliverables**: Modified `build_design_matrix()` with opening odds parameters, updated training script (training and calibration sets), updated pre-computation script, successful model training with opening odds

### Phase 4: Model Evaluation and Comparison (Duration: 2-3 hours)
**Objective**: Train models with and without opening odds, compare performance using time-bucketed evaluation metrics.
**Dependencies**: Phase 3 complete
**Deliverables**: Trained models (baseline and odds-enabled), performance comparison results (global and time-bucketed), feature importance analysis

### Phase 5: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 4 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Parity Validation (CRITICAL PREREQUISITE)
**Priority**: Critical (blocking - must validate before switching data sources)
**Estimated Time**: 1-2 hours (1 hour for queries, 1 hour for analysis)
**Dependencies**: Database access, understanding of ESPN-direct training query structure
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Validate Training Data Source Parity
- **ID**: S1-E1-S1
- **Type**: Research/Validation
- **Priority**: Critical (blocking - cannot proceed without parity validation)
- **Estimate**: 1-2 hours (30 min queries, 30 min analysis, 30 min documentation)
- **Phase**: Phase 1
- **Prerequisites**: None (first story in sprint)
- **Files to Modify**: None (validation only)
- **Files to Create**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md` (validation results)
- **Dependencies**: Database access via `DATABASE_URL`, PostgreSQL client

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Q3a query (ESPN-direct) executes successfully and returns game/snapshot counts per season
  - [ ] Q3b query (canonical dataset) executes successfully and returns game/snapshot counts per season
  - [ ] Parity validation report created with exact counts from both queries
  - [ ] Game count parity verified (within 5% difference per season)
  - [ ] Snapshot count parity verified (within 5% difference per season)
  - [ ] Time bucket distribution comparison shows similar distributions
  - [ ] **Label parity verified**: Random sample of 100+ snapshots shows `home_win` label matches between sources (100% match required)
  - [ ] **Feature parity verified**: Random sample shows core features match within tolerance (`point_differential` ±1, `time_remaining` ±1 second, `possession` exact match)
  - [ ] Go/no-go decision documented with rationale

- **Technical Context**:
  - **Current State**: Training scripts query ESPN tables directly. Canonical dataset (`derived.snapshot_features_v1`) filters to games with Kalshi data (for simulation), which may exclude games needed for training.
  - **Required Changes**: Execute parity validation queries (Q3a, Q3b from analysis Command Appendix), compare results, document decision.
  - **Integration Points**: Results inform whether to switch to canonical dataset (Option A) or join ESPN tables with opening odds (Option B)
  - **Data Structures**: Query results: `season_start`, `game_count`, `unique_snapshot_count`, `snapshot_count`
  - **API Contracts**: N/A (SQL queries only)

- **Implementation Steps**:
  1. **Connect to Database**: `source .env && ./scripts/psql.sh`
  2. **Execute Q3a Query**: Run ESPN-direct game/snapshot count query from analysis Command Appendix (Q3a)
     - File: Execute in psql session
     - Action: Copy-paste Q3a SQL query
     - Expected: Returns game_count, unique_snapshot_count, snapshot_count per season_start
  3. **Execute Q3b Query**: Run canonical dataset game/snapshot count query from analysis Command Appendix (Q3b)
     - File: Execute in psql session
     - Action: Copy-paste Q3b SQL query
     - Expected: Returns game_count, unique_snapshot_count, snapshot_count per season_start
  4. **Compare Results**: Calculate percentage differences per season
     - File: Create `parity-validation-report.md`
     - Action: Document exact counts and percentage differences
     - Content: Table comparing Q3a vs Q3b results
  5. **Execute Time Bucket Distribution Query**: Run time bucket distribution comparison (from analysis Q3)
     - File: Execute in psql session
     - Action: Run distribution queries for both data sources
     - Expected: Similar distributions across time buckets
  6. **Verify Label Parity**: Sample random snapshots and compare labels
     - File: Execute in psql session
     - Action: Query 100+ random snapshots from both sources, join on `(game_id, sequence_number, snapshot_timestamp)` or equivalent, compare `home_win` labels
     - Expected: 100% label match (all sampled snapshots have identical `home_win` values)
  7. **Verify Feature Parity**: Sample random snapshots and compare core features
     - File: Execute in psql session
     - Action: Query same random snapshots, compare `point_differential`, `time_remaining`, `possession`
     - Expected: `point_differential` matches within ±1, `time_remaining` matches within ±1 second, `possession` exact match
  8. **Document Decision**: Create parity validation report with go/no-go decision
     - File: `parity-validation-report.md`
     - Action: Document decision and rationale, include label/feature parity results
     - Content: If parity passes (>95% match on counts, 100% label match, feature match within tolerance), proceed with Option A (canonical dataset). If parity fails, use Option B (join ESPN tables with opening odds).

- **Validation Steps**:
  1. **Verify Queries Execute**: `source .env && psql "$DATABASE_URL" -c "[Q3a query]"` - Expected: No errors, returns results
  2. **Verify Parity Report Exists**: `test -f cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md` - Expected: File exists
  3. **Verify Decision Documented**: `grep -q "GO\|NO-GO" cursor-files/sprints/2026-01-15-pregame-odds-model-integration/parity-validation-report.md` - Expected: Decision clearly stated

- **Definition of Done**:
  - [ ] All parity validation queries executed successfully
  - [ ] Parity validation report created with exact counts and percentage differences
  - [ ] Label parity verified (100% match on sampled snapshots)
  - [ ] Feature parity verified (core features match within tolerance)
  - [ ] Go/no-go decision documented with clear rationale
  - [ ] If parity passes, proceed to Phase 2. If parity fails, document Option B approach.

- **Rollback Plan**: N/A (validation only, no code changes)

- **Risk Assessment**: 
  - **Risk**: Parity fails (canonical dataset excludes games needed for training)
  - **Mitigation**: Document Option B approach (join ESPN tables with opening odds by game_id and date)
  - **Contingency**: Proceed with Option B if parity fails (more complex but preserves training data coverage)

- **Success Metrics**:
  - **Completeness**: Parity validation report contains exact counts from both queries
  - **Accuracy**: Percentage differences calculated correctly
  - **Decision Quality**: Go/no-go decision clearly documented with rationale

### Epic 2: Opening Odds Feature Engineering
**Priority**: High (core functionality)
**Estimated Time**: 3-4 hours (1 hour odds format validation, 1 hour design review, 1-2 hours implementation)
**Dependencies**: Epic 1 complete (parity validated)
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Validate Opening Odds Format and Document Conversion Logic
- **ID**: S1-E2-S1
- **Type**: Research/Validation
- **Priority**: Critical (blocking - must validate odds format before implementing de-vigging)
- **Estimate**: 1 hour (30 min database query, 30 min documentation)
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1 (parity validation complete)
- **Files to Modify**: None (validation only)
- **Files to Create**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md` (validation results)
- **Dependencies**: Database access via `DATABASE_URL`, understanding of odds formats

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Database query executed to inspect `opening_moneyline_home` and `opening_moneyline_away` values
  - [ ] Odds format determined (decimal vs American)
  - [ ] Sample values documented (e.g., decimal: 1.85, 2.10 vs American: +120, -140)
  - [ ] Conversion logic documented (decimal: `p = 1/odds` vs American: `p = 100/(odds+100)` for positive, `p = |odds|/(|odds|+100)` for negative)
  - [ ] Validation report created with format determination and conversion formulas

- **Technical Context**:
  - **Current State**: Column names say "moneyline" which often implies American odds, but de-vigging math assumes decimal odds (`p = 1/odds`). This is a critical bug risk.
  - **Required Changes**: Query database to inspect actual values, determine format, document conversion logic.
  - **Integration Points**: Results inform de-vigging implementation (S1-E2-S2)
  - **Data Structures**: Query results showing sample odds values
  - **API Contracts**: N/A (validation only)

- **Implementation Steps**:
  1. **Query Database for Sample Odds**: Inspect actual values in database
     - File: Execute in psql session
     - Action: `SELECT opening_moneyline_home, opening_moneyline_away FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL LIMIT 100;`
     - Expected: Returns sample odds values
  2. **Determine Format**: Analyze sample values
     - File: Analysis of query results
     - Action: Check if values are decimal (1.0-10.0 range, e.g., 1.85, 2.10) or American (typically -200 to +200 range, e.g., -140, +120)
     - Expected: Format clearly identified
  3. **Document Conversion Logic**: Write conversion formulas
     - File: `odds-format-validation.md`
     - Action: Document format determination and conversion formulas
     - Content: If decimal: `p = 1/odds`. If American: positive odds `p = 100/(odds+100)`, negative odds `p = |odds|/(|odds|+100)`
  4. **Create Validation Report**: Document findings
     - File: `odds-format-validation.md`
     - Action: Create report with format determination, sample values, conversion formulas
     - Content: Format determination, sample values, conversion logic, implementation notes

- **Validation Steps**:
  1. **Verify Query Executes**: `source .env && psql "$DATABASE_URL" -c "SELECT opening_moneyline_home, opening_moneyline_away FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL LIMIT 10;"` - Expected: Returns sample values
  2. **Verify Validation Report Exists**: `test -f cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md` - Expected: File exists
  3. **Verify Format Determined**: `grep -q "decimal\|American" cursor-files/sprints/2026-01-15-pregame-odds-model-integration/odds-format-validation.md` - Expected: Format clearly stated

- **Definition of Done**:
  - [ ] Database query executed and sample values inspected
  - [ ] Odds format determined (decimal or American)
  - [ ] Conversion logic documented
  - [ ] Validation report created
  - [ ] All validation steps pass

- **Rollback Plan**: N/A (validation only, no code changes)

- **Risk Assessment**: 
  - **Risk**: Odds are American format but de-vigging uses decimal conversion (would silently train wrong)
  - **Mitigation**: Validate format before implementing de-vigging, use correct conversion formula
  - **Contingency**: If American format, update all de-vigging logic to use American conversion

- **Success Metrics**:
  - **Completeness**: Format clearly determined and documented
  - **Accuracy**: Conversion formulas correct for determined format
  - **Clarity**: Validation report provides clear guidance for implementation

#### Story 2.2: Create Shared De-Vigging Helper Function
- **ID**: S1-E2-S2
- **Type**: Feature
- **Priority**: High (core functionality - prevents code duplication)
- **Estimate**: 1 hour (30 min implementation, 30 min testing)
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1 (odds format validated)
- **Files to Modify**: `scripts/lib/_winprob_lib.py` (add `compute_opening_odds_features()` helper function)
- **Files to Create**: None
- **Dependencies**: S1-E2-S1 (odds format validation), numpy

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `compute_opening_odds_features()` function created in `scripts/lib/_winprob_lib.py`
  - [ ] Function accepts opening odds (moneyline_home, moneyline_away, spread, total) as inputs
  - [ ] Function returns engineered features: `opening_prob_home_fair`, `opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - [ ] Function uses correct odds conversion (decimal or American based on S1-E2-S1 validation)
  - [ ] Function includes safety checks (only compute if both odds present and valid)
  - [ ] Function handles NULL values gracefully (returns NaNs for missing values)
  - [ ] Function tested with known odds values (verifies de-vigging math)

- **Technical Context**:
  - **Current State**: De-vigging logic planned to be duplicated in `train_winprob_catboost.py` and `precompute_model_probabilities.py`.
  - **Required Changes**: Create shared helper function in `scripts/lib/_winprob_lib.py` to prevent code drift.
  - **Integration Points**: Called by training script (S1-E3-S2) and pre-computation script (S1-E3-S3)
  - **Data Structures**: Input: scalar or array values for odds. Output: dictionary or tuple of engineered features
  - **API Contracts**: Function signature: `compute_opening_odds_features(opening_moneyline_home, opening_moneyline_away, opening_spread=None, opening_total=None) -> dict`

- **Implementation Steps**:
  1. **Review Odds Format Validation**: Check format determination from S1-E2-S1
     - File: `odds-format-validation.md`
     - Action: Read format determination and conversion formulas
     - Content: Use correct conversion based on format (decimal vs American)
  2. **Create Helper Function**: Implement `compute_opening_odds_features()` in `_winprob_lib.py`
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Add function with de-vigging logic and safety checks
     - Content: Function accepts odds, returns engineered features with proper conversion
  3. **Add Unit Tests**: Test function with known odds values
     - File: Test script or unit test
     - Action: Test with known decimal odds (e.g., 1.85, 2.10) or American odds (e.g., -140, +120)
     - Expected: De-vigged probabilities match expected values

- **Validation Steps**:
  1. **Verify Function Exists**: `python -c "from scripts.lib._winprob_lib import compute_opening_odds_features; print(compute_opening_odds_features)"` - Expected: Function exists
  2. **Verify Function Signature**: `python -c "from scripts.lib._winprob_lib import compute_opening_odds_features; import inspect; print(inspect.signature(compute_opening_odds_features))"` - Expected: Function signature matches expected
  3. **Verify De-Vigging Math**: Test with known odds values - Expected: De-vigged probabilities correct

- **Definition of Done**:
  - [ ] Helper function created in `_winprob_lib.py`
  - [ ] Function uses correct odds conversion (based on format validation)
  - [ ] Function includes safety checks
  - [ ] Function tested with known values
  - [ ] All validation steps pass

- **Rollback Plan**: Revert changes to `_winprob_lib.py` if errors occur

- **Risk Assessment**: 
  - **Risk**: Wrong odds conversion formula used
  - **Mitigation**: Use format validation from S1-E2-S1, test with known values
  - **Contingency**: Fix conversion formula if tests fail

- **Success Metrics**:
  - **Functionality**: Function correctly computes de-vigged features
  - **Correctness**: De-vigging math verified with known values
  - **Reusability**: Function can be called from both training and pre-computation scripts

#### Story 2.3: Implement Opening Odds Feature Engineering in Training Data Loading
- **ID**: S1-E2-S3
- **Type**: Feature
- **Priority**: High (core functionality - required for model integration)
- **Estimate**: 1-2 hours (30 min implementation, 30 min testing)
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S2 (shared helper function created)
- **Files to Modify**: `scripts/model/train_winprob_catboost.py` (modify `_load_training_data()` function to call helper)
- **Files to Create**: None
- **Dependencies**: S1-E2-S2 (shared helper function), numpy, pandas

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `_load_training_data()` function loads opening odds from canonical dataset (or joins with opening odds if Option B)
  - [ ] Function calls `compute_opening_odds_features()` helper (from S1-E2-S2) for each row or vectorized
  - [ ] `opening_prob_home_fair` column created (de-vigged fair probability, may contain NaNs)
  - [ ] `opening_overround` column created (vig amount, may contain NaNs)
  - [ ] Missingness indicator flags created: `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - [ ] `has_opening_moneyline` matches `valid_ml` condition (both sides present and valid)
  - [ ] Function returns DataFrame with opening odds features included
  - [ ] No errors when opening odds are NULL (handles missing values gracefully)

- **Technical Context**:
  - **Current State**: `_load_training_data()` in `scripts/model/train_winprob_catboost.py` queries ESPN tables directly, does not include opening odds.
  - **Required Changes**: 
    - If parity passes: Modify query to use `derived.snapshot_features_v1` instead of ESPN tables directly
    - If parity fails: Join ESPN tables with `external.sportsbook_odds_snapshots` by `game_id` and date
    - Call `compute_opening_odds_features()` helper (from S1-E2-S2) to compute engineered features
  - **Integration Points**: Output DataFrame feeds into `build_design_matrix()` (Phase 3), uses helper function from S1-E2-S2
  - **Data Structures**: DataFrame columns: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total` (from canonical dataset), plus engineered features: `opening_prob_home_fair`, `opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - **API Contracts**: Function signature unchanged, returns DataFrame with additional columns

- **Implementation Steps**:
  1. **Import Helper Function**: Import `compute_opening_odds_features()` from `_winprob_lib`
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Add import statement
     - Content: `from scripts.lib._winprob_lib import compute_opening_odds_features`
  2. **Modify Data Loading Query**: Update `_load_training_data()` to include opening odds
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Modify SQL query or DataFrame join to include opening odds columns
     - Content: If Option A (parity passed): Query `derived.snapshot_features_v1`. If Option B (parity failed): Join ESPN tables with `external.sportsbook_odds_snapshots` filtered for `is_opening_line = TRUE`
  3. **Call Helper Function**: Apply `compute_opening_odds_features()` to compute engineered features
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Call helper function (vectorized or row-wise) after data loading
     - Content: Apply helper function to compute `opening_prob_home_fair`, `opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  4. **Test with Sample Data**: Verify function works with NULL opening odds
     - File: Test script or interactive Python session
     - Action: Call `_load_training_data()` with sample parameters
     - Expected: Returns DataFrame with opening odds features, handles NULL values without errors

- **Validation Steps**:
  1. **Verify Function Executes**: `python -c "from scripts.model.train_winprob_catboost import _load_training_data; import psycopg; conn = psycopg.connect('$DATABASE_URL'); df = _load_training_data(conn, 2022, 2024, None, True); print(df.columns.tolist())"` - Expected: DataFrame includes `opening_prob_home_fair`, `opening_overround`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  2. **Verify De-Vigging Logic**: Check that `opening_prob_home_fair` values are between 0 and 1 for valid odds - Expected: All values in [0, 1] range
  3. **Verify Safety Checks**: Check that `opening_prob_home_fair` is NaN when odds are missing or invalid - Expected: NaN for rows without valid odds
  4. **Verify Missingness Flags**: Check that `has_opening_moneyline` is 1 when valid_ml is True, 0 otherwise - Expected: Binary flags match valid_ml condition

- **Definition of Done**:
  - [ ] `_load_training_data()` modified to include opening odds
  - [ ] Helper function `compute_opening_odds_features()` called (from S1-E2-S2)
  - [ ] Opening odds features added to DataFrame
  - [ ] Function returns DataFrame with opening odds features
  - [ ] No errors when opening odds are NULL
  - [ ] All validation steps pass

- **Rollback Plan**: Revert changes to `train_winprob_catboost.py` if errors occur, restore original `_load_training_data()` function

- **Risk Assessment**: 
  - **Risk**: Helper function not called correctly
  - **Mitigation**: Use helper function from S1-E2-S2 (already tested), verify function call
  - **Contingency**: Debug helper function call if errors occur

- **Success Metrics**:
  - **Functionality**: Function successfully loads opening odds and creates engineered features using helper
  - **Correctness**: De-vigging produces fair probabilities in [0, 1] range (verified by helper function)
  - **Robustness**: Handles NULL values without errors

### Epic 3: Design Matrix and Training Integration
**Priority**: High (core functionality)
**Estimated Time**: 4-5 hours (1 hour design matrix + canonical feature list, 2-3 hours training script, 1 hour testing)
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Add Opening Odds Parameters to build_design_matrix() and Define Canonical Feature List
- **ID**: S1-E3-S1
- **Type**: Feature
- **Priority**: High (required for model training)
- **Estimate**: 1 hour (30 min implementation, 30 min testing)
- **Phase**: Phase 3
- **Prerequisites**: S1-E2-S3 (feature engineering complete)
- **Files to Modify**: `scripts/lib/_winprob_lib.py` (modify `build_design_matrix()` function)
- **Files to Create**: None
- **Dependencies**: numpy, existing `build_design_matrix()` function

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `ODDS_FEATURES` constant defined in `_winprob_lib.py` with canonical feature list: `['opening_prob_home_fair', 'opening_overround', 'opening_spread', 'opening_total', 'has_opening_moneyline', 'has_opening_spread', 'has_opening_total']`
  - [ ] `build_design_matrix()` function signature includes opening odds parameters (all optional, default None)
  - [ ] Function accepts: `opening_prob_home_fair`, `opening_overround`, `opening_spread`, `opening_total`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - [ ] Function includes opening odds features in design matrix when provided (always in same order as `ODDS_FEATURES`)
  - [ ] Function handles NaNs correctly (CatBoost will handle missing values)
  - [ ] Function maintains backward compatibility (works without opening odds parameters)
  - [ ] Feature names included in `feature_names` list in canonical order (for interpretability)

- **Technical Context**:
  - **Current State**: `build_design_matrix()` in `scripts/lib/_winprob_lib.py` accepts base features and optional interaction terms, does not include opening odds.
  - **Required Changes**: Add opening odds parameters to function signature, include in design matrix construction, add to feature names list.
  - **Integration Points**: Called by `train_winprob_catboost.py` to build training design matrix
  - **Data Structures**: Input: numpy arrays (may contain NaNs). Output: numpy array (design matrix)
  - **API Contracts**: Function signature extended with optional opening odds parameters

- **Implementation Steps**:
  1. **Read Current Function**: Review `build_design_matrix()` implementation
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Read function (lines 183-210 from analysis)
     - Content: Understand current structure, feature scaling, feature names
  2. **Define Canonical Feature List**: Create `ODDS_FEATURES` constant
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Define constant at module level
     - Content:
       ```python
       # Canonical opening odds feature names (always in this order)
       ODDS_FEATURES = [
           'opening_prob_home_fair',
           'opening_overround',
           'opening_spread',
           'opening_total',
           'has_opening_moneyline',
           'has_opening_spread',
           'has_opening_total',
       ]
       ```
  3. **Add Opening Odds Parameters**: Extend function signature
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Add optional parameters to function signature
     - Content:
       ```python
       def build_design_matrix(
           *,
           point_differential: np.ndarray,
           time_remaining_regulation: np.ndarray,
           possession: Iterable[str],
           preprocess: PreprocessParams,
           # Existing interaction terms...
           # NEW: Opening odds features (canonical naming)
           opening_prob_home_fair: np.ndarray | None = None,
           opening_overround: np.ndarray | None = None,
           opening_spread: np.ndarray | None = None,
           opening_total: np.ndarray | None = None,
           has_opening_moneyline: np.ndarray | None = None,
           has_opening_spread: np.ndarray | None = None,
           has_opening_total: np.ndarray | None = None,
       ) -> np.ndarray:
       ```
  4. **Add Opening Odds to Design Matrix**: Include features when provided (in canonical order)
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Add opening odds features to design matrix construction, always in `ODDS_FEATURES` order
     - Content: Append opening odds features to design matrix in canonical order (no scaling needed for CatBoost, but can normalize if desired). If any odds feature is provided, add all of them (with NaNs if missing) to maintain stable shape.
  5. **Update Feature Names**: Add opening odds feature names to list in canonical order
     - File: `scripts/lib/_winprob_lib.py`
     - Action: Update `feature_names` list (if maintained), use `ODDS_FEATURES` constant
     - Content: Add features from `ODDS_FEATURES` constant in canonical order
  5. **Test Backward Compatibility**: Verify function works without opening odds
     - File: Test script
     - Action: Call `build_design_matrix()` without opening odds parameters
     - Expected: Function works as before, returns design matrix with original features

- **Validation Steps**:
  1. **Verify Function Signature**: `python -c "from scripts.lib._winprob_lib import build_design_matrix; import inspect; print(inspect.signature(build_design_matrix))"` - Expected: Function signature includes opening odds parameters
  2. **Verify Design Matrix Shape**: Test with opening odds parameters - Expected: Design matrix has additional columns for opening odds features
  3. **Verify Backward Compatibility**: Test without opening odds parameters - Expected: Design matrix shape unchanged, function works as before

- **Definition of Done**:
  - [ ] `ODDS_FEATURES` constant defined with canonical feature list
  - [ ] Function signature includes opening odds parameters
  - [ ] Opening odds features included in design matrix when provided (in canonical order)
  - [ ] Feature names updated (using `ODDS_FEATURES` constant)
  - [ ] Backward compatibility maintained
  - [ ] All validation steps pass

- **Rollback Plan**: Revert changes to `_winprob_lib.py` if errors occur

- **Risk Assessment**: 
  - **Risk**: Breaking change affects existing models
  - **Mitigation**: All opening odds parameters are optional (default None), maintains backward compatibility
  - **Contingency**: Test thoroughly with existing code paths

- **Success Metrics**:
  - **Functionality**: Function accepts opening odds parameters and includes in design matrix
  - **Compatibility**: Backward compatibility maintained (works without opening odds)
  - **Correctness**: Design matrix shape correct, feature names accurate

#### Story 3.2: Update CatBoost Training Script to Use Opening Odds
- **ID**: S1-E3-S2
- **Type**: Feature
- **Priority**: High (required for model training with opening odds)
- **Estimate**: 2-3 hours (1.5 hours implementation, 1 hour testing)
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1 (build_design_matrix updated, ODDS_FEATURES constant defined)
- **Files to Modify**: `scripts/model/train_winprob_catboost.py` (modify training function to pass opening odds to build_design_matrix, update feature_names list using ODDS_FEATURES constant, update calibration set building)
- **Files to Create**: None
- **Dependencies**: S1-E2-S3 (feature engineering complete), S1-E3-S1 (build_design_matrix updated, ODDS_FEATURES constant)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Training function passes opening odds features to `build_design_matrix()` for training set
  - [ ] Calibration set building passes opening odds features to `build_design_matrix()` (if calibration season exists)
  - [ ] `feature_names` list includes opening odds feature names: `opening_prob_home_fair`, `opening_overround`, `opening_spread`, `opening_total`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
  - [ ] Model trains successfully with opening odds features
  - [ ] Model artifact saved successfully with correct feature_names
  - [ ] Feature importance includes opening odds features
  - [ ] Training completes without errors when opening odds are NULL for some games

- **Technical Context**:
  - **Current State**: Training function in `train_winprob_catboost.py` uses `build_matrix_kwargs` dictionary pattern (lines 369-389) and `calib_matrix_kwargs` for calibration set (lines 430-450). Calls `build_design_matrix()` without opening odds parameters. `feature_names` list (lines 393-412) does not include opening odds.
  - **Required Changes**: 
    - Add opening odds to `build_matrix_kwargs` dictionary (training set)
    - Add opening odds to `calib_matrix_kwargs` dictionary (calibration set, if exists)
    - Add opening odds feature names to `feature_names` list
  - **Integration Points**: Uses `_load_training_data()` output (from S1-E2-S1), calls `build_design_matrix()` (from S1-E3-S1)
  - **Data Structures**: DataFrame columns: `opening_prob_home_fair`, `opening_overround`, `opening_spread`, `opening_total`, `has_opening_moneyline`, `has_opening_spread`, `has_opening_total` (may contain NaNs)
  - **API Contracts**: Dictionary pattern (`build_matrix_kwargs`) extended with opening odds keys

- **Implementation Steps**:
  1. **Locate build_matrix_kwargs Construction**: Find where `build_matrix_kwargs` dictionary is built (around line 369)
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Locate dictionary construction for training set
     - Content: Identify where interaction terms are conditionally added
  2. **Add Opening Odds to Training build_matrix_kwargs**: Add opening odds to dictionary after interaction terms
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Add opening odds features to `build_matrix_kwargs` dictionary (after line 387, before `X_train = build_design_matrix(**build_matrix_kwargs)`)
     - Content:
       ```python
       # Add opening odds features if available
       if "opening_prob_home_fair" in df.columns:
           build_matrix_kwargs["opening_prob_home_fair"] = df.loc[train_mask, "opening_prob_home_fair"].astype(float).to_numpy()
       if "opening_overround" in df.columns:
           build_matrix_kwargs["opening_overround"] = df.loc[train_mask, "opening_overround"].astype(float).to_numpy()
       if "opening_spread" in df.columns:
           build_matrix_kwargs["opening_spread"] = df.loc[train_mask, "opening_spread"].astype(float).to_numpy()
       if "opening_total" in df.columns:
           build_matrix_kwargs["opening_total"] = df.loc[train_mask, "opening_total"].astype(float).to_numpy()
       if "has_opening_moneyline" in df.columns:
           build_matrix_kwargs["has_opening_moneyline"] = df.loc[train_mask, "has_opening_moneyline"].astype(int).to_numpy()
       if "has_opening_spread" in df.columns:
           build_matrix_kwargs["has_opening_spread"] = df.loc[train_mask, "has_opening_spread"].astype(int).to_numpy()
       if "has_opening_total" in df.columns:
           build_matrix_kwargs["has_opening_total"] = df.loc[train_mask, "has_opening_total"].astype(int).to_numpy()
       ```
  3. **Add Opening Odds to Calibration build_matrix_kwargs**: Add opening odds to calibration set dictionary (if calibration season exists)
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Add opening odds features to `calib_matrix_kwargs` dictionary (after line 448, before `X_calib = build_design_matrix(**calib_matrix_kwargs)`)
     - Content: Same pattern as step 2, but using `calib_mask` instead of `train_mask`
  4. **Update feature_names List**: Add opening odds feature names using `ODDS_FEATURES` constant
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Import `ODDS_FEATURES` from `_winprob_lib`, add feature names in canonical order (after line 412)
     - Content:
       ```python
       from scripts.lib._winprob_lib import ODDS_FEATURES
       
       # Add opening odds feature names if any odds column exists (use canonical order)
       if any(col in df.columns for col in ODDS_FEATURES):
           feature_names.extend(ODDS_FEATURES)  # Always add all features in canonical order
       ```
  5. **Test Model Training**: Run training script with opening odds
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Execute training script
     - Expected: Model trains successfully, artifact saved, feature_names includes opening odds

- **Validation Steps**:
  1. **Verify Training Completes**: `python scripts/model/train_winprob_catboost.py --out-artifact artifacts/test.json --dsn "$DATABASE_URL"` - Expected: Training completes without errors
  2. **Verify Model Artifact**: Check that model artifact file exists and contains feature_names - Expected: `.cbm` file created, artifact JSON contains opening odds in feature_names
  3. **Verify Feature Names**: Load artifact and check `feature_names` list - Expected: Opening odds feature names present in list
  4. **Verify Feature Importance**: Check CatBoost feature importance output - Expected: Opening odds features appear in feature importance list

- **Definition of Done**:
  - [ ] Training set passes opening odds to `build_design_matrix()` via `build_matrix_kwargs`
  - [ ] Calibration set passes opening odds to `build_design_matrix()` via `calib_matrix_kwargs` (if calibration season exists)
  - [ ] `feature_names` list includes opening odds feature names
  - [ ] Model trains successfully with opening odds
  - [ ] Model artifact saved with correct feature_names
  - [ ] Feature importance includes opening odds features
  - [ ] All validation steps pass

- **Rollback Plan**: Revert changes to training script if errors occur

- **Risk Assessment**: 
  - **Risk**: CatBoost fails to train with NaNs
  - **Mitigation**: CatBoost handles missing values natively, but verify with test run
  - **Contingency**: Add explicit NaN handling if needed

- **Success Metrics**:
  - **Functionality**: Model trains successfully with opening odds
  - **Correctness**: Feature names list includes opening odds, feature importance shows opening odds features
  - **Robustness**: Handles NULL opening odds without errors

#### Story 3.3: Update precompute_model_probabilities.py to Include Opening Odds
- **ID**: S1-E3-S3
- **Type**: Feature
- **Priority**: High (required for grid search compatibility - models with opening odds need opening odds when scoring)
- **Estimate**: 1-2 hours (1 hour implementation, 30 min testing)
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1 (build_design_matrix updated), S1-E3-S2 (training script updated)
- **Files to Modify**: `scripts/model/precompute_model_probabilities.py` (update SQL query to include opening odds, update score_snapshot() to call compute_opening_odds_features() helper and pass opening odds)
- **Files to Create**: None
- **Dependencies**: S1-E2-S2 (shared helper function), S1-E3-S1 (build_design_matrix updated)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] SQL query in `precompute_all()` includes opening odds columns: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`
  - [ ] `score_snapshot()` function calls `compute_opening_odds_features()` helper (from S1-E2-S2)
  - [ ] `score_snapshot()` passes opening odds features to `build_design_matrix()`
  - [ ] Pre-computation script executes successfully with models trained with opening odds
  - [ ] Pre-computation handles NULL opening odds gracefully (no errors)

- **Technical Context**:
  - **Current State**: `precompute_model_probabilities.py` queries `derived.snapshot_features_v1` but does not include opening odds columns (lines 176-191). `score_snapshot()` function calls `build_design_matrix()` without opening odds (lines 133-143).
  - **Required Changes**: 
    - Add opening odds columns to SQL query in `precompute_all()` function
    - Add de-vigging logic to `score_snapshot()` function (same as training script)
    - Pass opening odds features to `build_design_matrix()` in `score_snapshot()`
  - **Integration Points**: Uses canonical dataset (`derived.snapshot_features_v1`), calls `build_design_matrix()` (from S1-E3-S1)
  - **Data Structures**: Snapshot dictionary includes opening odds columns, de-vigged features computed in `score_snapshot()`
  - **API Contracts**: `score_snapshot()` function signature unchanged, internally computes and passes opening odds

- **Implementation Steps**:
  1. **Update SQL Query**: Add opening odds columns to SELECT statement
     - File: `scripts/model/precompute_model_probabilities.py`
     - Action: Modify SQL query in `precompute_all()` function (around line 176)
     - Content: Add `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total` to SELECT list
  2. **Update Snapshot Dictionary**: Include opening odds in snapshot dict
     - File: `scripts/model/precompute_model_probabilities.py`
     - Action: Update snapshot dictionary construction (around line 227)
     - Content: Add opening odds columns from query results to snapshot dict
  3. **Call Helper Function in score_snapshot()**: Use `compute_opening_odds_features()` helper
     - File: `scripts/model/precompute_model_probabilities.py`
     - Action: Import and call helper function in `score_snapshot()` function (before calling `build_design_matrix()`)
     - Content:
       ```python
       from scripts.lib._winprob_lib import compute_opening_odds_features
       
       # Extract opening odds from snapshot
       opening_moneyline_home = snapshot.get("opening_moneyline_home")
       opening_moneyline_away = snapshot.get("opening_moneyline_away")
       opening_spread = snapshot.get("opening_spread")
       opening_total = snapshot.get("opening_total")
       
       # Compute engineered features using shared helper (prevents code drift)
       odds_features = compute_opening_odds_features(
           opening_moneyline_home=opening_moneyline_home,
           opening_moneyline_away=opening_moneyline_away,
           opening_spread=opening_spread,
           opening_total=opening_total,
       )
       ```
  4. **Pass Opening Odds to build_design_matrix()**: Include opening odds in function call
     - File: `scripts/model/precompute_model_probabilities.py`
     - Action: Update `build_design_matrix()` call in `score_snapshot()` (around line 133)
     - Content: Add opening odds parameters to function call (may be None/NaN)
  5. **Test Pre-Computation**: Run pre-computation script with models trained with opening odds
     - File: `scripts/model/precompute_model_probabilities.py`
     - Action: Execute pre-computation script
     - Expected: Pre-computation completes successfully, probabilities computed for all snapshots

- **Validation Steps**:
  1. **Verify SQL Query Includes Opening Odds**: Check query in `precompute_all()` function - Expected: SELECT includes `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`
  2. **Verify De-Vigging Logic**: Check `score_snapshot()` function - Expected: De-vigging logic present with safety checks
  3. **Verify Pre-Computation Executes**: `python scripts/model/precompute_model_probabilities.py --dsn "$DATABASE_URL"` - Expected: Pre-computation completes without errors
  4. **Verify Probabilities Computed**: Check `derived.model_probabilities_v1` table - Expected: Probabilities computed for snapshots with and without opening odds

- **Definition of Done**:
  - [ ] SQL query includes opening odds columns
  - [ ] `score_snapshot()` calls `compute_opening_odds_features()` helper (from S1-E2-S2)
  - [ ] `score_snapshot()` passes opening odds to `build_design_matrix()`
  - [ ] Pre-computation script executes successfully
  - [ ] Handles NULL opening odds without errors
  - [ ] All validation steps pass

- **Rollback Plan**: Revert changes to `precompute_model_probabilities.py` if errors occur

- **Risk Assessment**: 
  - **Risk**: Pre-computation fails when models require opening odds but snapshot doesn't have them
  - **Mitigation**: Models handle missing values natively (CatBoost), de-vigging logic handles NULL gracefully
  - **Contingency**: Add explicit NULL handling if needed

- **Success Metrics**:
  - **Functionality**: Pre-computation script executes successfully with models trained with opening odds
  - **Correctness**: De-vigging logic matches training script logic
  - **Robustness**: Handles NULL opening odds without errors

### Epic 4: Model Evaluation and Comparison
**Priority**: High (validation)
**Estimated Time**: 2-3 hours (1 hour training, 1 hour evaluation, 30 min comparison)
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Train Baseline and Odds-Enabled Models
- **ID**: S1-E4-S1
- **Type**: Feature/Validation
- **Priority**: High (required for performance comparison)
- **Estimate**: 1-2 hours (30 min baseline training, 30 min odds-enabled training, 30 min artifact verification)
- **Phase**: Phase 4
- **Prerequisites**: S1-E3-S2 (training script updated)
- **Files to Modify**: None (training only)
- **Files to Create**: Model artifacts (baseline and odds-enabled)
- **Dependencies**: Training scripts, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Fixed random seed set for train/test split reproducibility
  - [ ] Split keys (game_ids) persisted to file: `artifacts/splits/sprint1_split_game_ids.json` (or similar)
  - [ ] Baseline model trained (without opening odds) - can use existing model or retrain
  - [ ] Odds-enabled model trained (with opening odds)
  - [ ] Both model artifacts saved successfully
  - [ ] Both models use same train/test split for fair comparison (verified by split file or same random seed)
  - [ ] Training parameters identical except for opening odds features

- **Technical Context**:
  - **Current State**: No models trained with opening odds yet.
  - **Required Changes**: Train two models (baseline without opening odds, odds-enabled with opening odds) using identical train/test splits.
  - **Integration Points**: Model artifacts used for evaluation (S1-E4-S2)
  - **Data Structures**: Model artifacts (`.cbm` files), training logs
  - **API Contracts**: Standard CatBoost model training

- **Implementation Steps**:
  1. **Set Fixed Random Seed**: Ensure train/test split reproducibility
     - File: `scripts/model/train_winprob_catboost.py` or training script
     - Action: Set `np.random.seed(42)` or equivalent before train/test split
     - Expected: Same split generated on each run
  2. **Persist Split Keys**: Save game_ids for train/test split to file
     - File: Create `artifacts/splits/sprint1_split_game_ids.json`
     - Action: After train/test split, save `{'train_game_ids': [...], 'test_game_ids': [...]}` to JSON file
     - Expected: Split file created with game_ids
  3. **Train Baseline Model**: Train model without opening odds (or use existing baseline)
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Run training script without opening odds (or use existing model), using same random seed
     - Expected: Baseline model artifact saved, split file created
  4. **Train Odds-Enabled Model**: Train model with opening odds using same split
     - File: `scripts/model/train_winprob_catboost.py`
     - Action: Run training script with opening odds (using updated code from S1-E3-S2), using same random seed or load split file
     - Expected: Odds-enabled model artifact saved, same train/test split used
  5. **Verify Split Reproducibility**: Check that both models used same split
     - File: Compare split files or verify same random seed used
     - Action: Verify train/test game_ids match between baseline and odds-enabled models
     - Expected: Same game_ids in train/test sets for both models
  6. **Verify Artifacts**: Check that both model artifacts exist
     - File: Artifact directory
     - Action: List model artifact files
     - Expected: Both `.cbm` files present

- **Validation Steps**:
  1. **Verify Baseline Model Exists**: `test -f artifacts/winprob_catboost_baseline.cbm` (or existing baseline) - Expected: File exists
  2. **Verify Odds-Enabled Model Exists**: `test -f artifacts/winprob_catboost_odds.cbm` - Expected: File exists
  3. **Verify Training Logs**: Check training logs for errors - Expected: No errors in training logs

- **Definition of Done**:
  - [ ] Fixed random seed set for split reproducibility
  - [ ] Split keys persisted to file (or same random seed used for both models)
  - [ ] Baseline model trained (or existing baseline identified)
  - [ ] Odds-enabled model trained
  - [ ] Both models use same train/test split (verified)
  - [ ] Both model artifacts saved
  - [ ] Training parameters documented
  - [ ] All validation steps pass

- **Rollback Plan**: N/A (training only, no code changes)

- **Risk Assessment**: 
  - **Risk**: Training fails due to data issues
  - **Mitigation**: Validate data loading before training, check for NULL handling
  - **Contingency**: Debug data loading issues, fix feature engineering if needed

- **Success Metrics**:
  - **Completeness**: Both models trained successfully
  - **Consistency**: Same train/test split used for both models
  - **Quality**: Training completes without errors

#### Story 4.2: Evaluate Model Performance with Time-Bucketed Metrics
- **ID**: S1-E4-S2
- **Type**: Validation/Research
- **Priority**: High (required for success criteria)
- **Estimate**: 1-2 hours (30 min evaluation script, 30 min time-bucketed analysis, 30 min results documentation)
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S1 (both models trained)
- **Files to Modify**: None (evaluation only)
- **Files to Create**: `cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.md` (evaluation results)
- **Dependencies**: Trained models, test set data, sklearn metrics

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Evaluation script computes global Brier score and log-loss for both models
  - [ ] Evaluation script computes time-bucketed metrics (Brier score, log-loss by time bucket)
  - [ ] Time buckets: [2880-2400, 2400-1800, 1800-1200, 1200-600, 600-120, 120-0]
  - [ ] Results table created comparing baseline vs odds-enabled model
  - [ ] Feature importance extracted for odds-enabled model
  - [ ] Results document created with exact metrics and interpretation

- **Technical Context**:
  - **Current State**: No evaluation script for time-bucketed metrics.
  - **Required Changes**: Create evaluation script following analysis "Time-Bucketed Evaluation Procedure" (lines 1482-1607), compute metrics for both models, compare results.
  - **Integration Points**: Uses trained models (S1-E4-S1), test set data from canonical dataset
  - **Data Structures**: Test set DataFrame with `time_remaining`, predictions (numpy arrays), results table
  - **API Contracts**: Standard sklearn metrics (brier_score_loss, log_loss)

- **Implementation Steps**:
  1. **Create Evaluation Script**: Implement time-bucketed evaluation procedure
     - File: Create evaluation script (Python)
     - Action: Implement evaluation logic from analysis (lines 1492-1585)
     - Content: Load test set, generate predictions from both models, assign time buckets, compute metrics per bucket
  2. **Run Evaluation**: Execute evaluation script
     - File: Evaluation script
     - Action: Run script with both model artifacts
     - Expected: Results table with metrics per time bucket
  3. **Extract Feature Importance**: Get feature importance from odds-enabled model
     - File: Evaluation script
     - Action: Extract CatBoost feature importance
     - Expected: Feature importance list with opening odds features
  4. **Document Results**: Create results document
     - File: `model-evaluation-results.md`
     - Action: Document exact metrics, comparison table, interpretation
     - Content: Results table, feature importance, interpretation (early-game improvements expected)

- **Validation Steps**:
  1. **Verify Evaluation Script Executes**: `python evaluation_script.py` - Expected: No errors, results table printed
  2. **Verify Results Document Exists**: `test -f cursor-files/sprints/2026-01-15-pregame-odds-model-integration/model-evaluation-results.md` - Expected: File exists
  3. **Verify Metrics Calculated**: Check results document for Brier score and log-loss - Expected: Metrics present for all time buckets

- **Definition of Done**:
  - [ ] Evaluation script created and executed
  - [ ] Global metrics computed (Brier score, log-loss)
  - [ ] Time-bucketed metrics computed (all 6 buckets)
  - [ ] Results table created comparing baseline vs odds-enabled
  - [ ] Feature importance extracted
  - [ ] Results document created with interpretation
  - [ ] All validation steps pass

- **Rollback Plan**: N/A (evaluation only, no code changes)

- **Risk Assessment**: 
  - **Risk**: Evaluation script has bugs
  - **Mitigation**: Follow analysis procedure exactly, test with known values
  - **Contingency**: Debug evaluation script, verify metric calculations

- **Success Metrics**:
  - **Completeness**: All metrics computed (global and time-bucketed)
  - **Accuracy**: Metrics calculated correctly (verify with known values)
  - **Interpretability**: Results clearly show improvement (or lack thereof) in early-game buckets

### Epic 5: Sprint Quality Assurance (MANDATORY)
**Priority**: Critical (required for sprint completion)
**Estimated Time**: 3-4 hours (1-2 hours documentation, 1-2 hours quality gates)
**Dependencies**: All development epics complete
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 5.1: Documentation Update
- **ID**: S1-E5-S1 (SPRINT-DOC-UPDATE)
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed (S1-E1-S1, S1-E2-S1, S1-E2-S2, S1-E2-S3, S1-E3-S1, S1-E3-S2, S1-E3-S3, S1-E4-S1, S1-E4-S2)

- **Acceptance Criteria**:
  - [ ] **Code documentation** updated if code changes were made (docstrings, comments)
  - [ ] **Architecture documentation** updated if architectural changes were made
  - [ ] **User documentation** updated if user-facing features were changed
  - [ ] **Analysis document** cross-referenced if analysis was used
  - [ ] **Sprint completion report** created with summary of changes

- **Technical Context**:
  - **Current State**: Documentation may be outdated after code changes.
  - **Required Changes**: Update relevant documentation to reflect opening odds integration.
  - **Integration Points**: Code changes in `_winprob_lib.py`, `train_winprob_catboost.py`, `precompute_model_probabilities.py`

- **Implementation Steps**:
  1. **Update Code Documentation**: Review and update docstrings/comments in modified files
  2. **Update Architecture Documentation**: Document opening odds feature engineering approach
  3. **Create Sprint Completion Report**: Summarize changes, results, and outcomes

- **Validation Steps**:
  1. **Verify Documentation Updated**: Check that relevant documentation files reflect changes
  2. **Verify Completion Report Exists**: Check for sprint completion report

- **Definition of Done**:
  - [ ] All relevant documentation updated
  - [ ] Sprint completion report created
  - [ ] All validation steps pass

- **Rollback Plan**: N/A (documentation only)

- **Risk Assessment**: Low (documentation only)

- **Success Metrics**: Documentation completeness, accuracy

#### Story 5.2: Quality Gate Validation
- **ID**: S1-E5-S2 (SPRINT-QG-VALIDATION)
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (MUST be 100% pass):
  - [ ] **Linting**: All linting checks pass with zero errors and zero warnings
  - [ ] **Type Checking**: All type checking passes with zero errors
  - [ ] **Unit Tests**: All unit tests pass (100% pass rate required)
  - [ ] **Integration Tests**: All integration tests pass (100% pass rate required)
  - [ ] **Build Process**: Build process completes without errors
  - [ ] **Code Formatting**: Code formatting is consistent
  - [ ] **Security**: No security vulnerabilities detected
  - [ ] **All acceptance criteria from previous stories verified as complete**

- **Technical Context**:
  - **Current State**: Code changes made, need to verify quality gates pass.
  - **Required Changes**: Run quality checks, fix any issues.
  - **Integration Points**: All modified files

- **Implementation Steps**:
  1. **Run Linting**: Execute linting checks on modified files
  2. **Run Type Checking**: Execute type checking
  3. **Run Tests**: Execute unit and integration tests
  4. **Fix Issues**: Address any quality gate failures
  5. **Re-run Checks**: Verify all checks pass

- **Validation Steps**:
  1. **Verify Linting Passes**: `[linting command]` - Expected: Zero errors, zero warnings
  2. **Verify Tests Pass**: `[test command]` - Expected: 100% pass rate
  3. **Verify Build Completes**: `[build command]` - Expected: No errors

- **Definition of Done**:
  - [ ] All quality gates pass (100% pass rate)
  - [ ] All previous story acceptance criteria verified
  - [ ] All validation steps pass

- **Rollback Plan**: Fix issues until quality gates pass

- **Risk Assessment**: 
  - **Risk**: Quality gates fail
  - **Mitigation**: Run checks incrementally, fix issues as they arise
  - **Contingency**: Address failures systematically

- **Success Metrics**: 100% pass rate on all quality gates

#### Story 5.3: Sprint Completion and Archive
- **ID**: S1-E5-S3 (SPRINT-COMPLETION)
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] `completion-report.md` created with comprehensive sprint summary
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Sprint marked as completed
  - [ ] Any cross-references updated

- **Technical Context**:
  - **Current State**: Sprint work complete, need to finalize and archive.
  - **Required Changes**: Create completion report, organize files.
  - **Integration Points**: Sprint directory, analysis document

- **Implementation Steps**:
  1. **Create Completion Report**: Document sprint summary, results, outcomes
  2. **Organize Files**: Ensure all sprint files are in sprint directory
  3. **Mark Sprint Complete**: Update sprint status

- **Validation Steps**:
  1. **Verify Completion Report Exists**: `test -f cursor-files/sprints/2026-01-15-pregame-odds-model-integration/completion-report.md` - Expected: File exists
  2. **Verify Sprint Files Organized**: List sprint directory - Expected: All files present

- **Definition of Done**:
  - [ ] Completion report created
  - [ ] Sprint files organized
  - [ ] Sprint marked as completed
  - [ ] All validation steps pass

- **Rollback Plan**: N/A (completion only)

- **Risk Assessment**: Low (completion only)

- **Success Metrics**: Sprint completion, documentation completeness

## Technical Decisions

### Design Pattern Analysis

#### Design Pattern: Feature Engineering Pattern
- **Category**: Data Processing
- **Intent**: Transform raw data (opening odds) into model-ready features (implied probabilities, interaction terms)
- **Implementation**: 
  - Raw Data: Opening odds (decimal format: 1.85, 2.10)
  - Transformation 1: Convert to raw implied probabilities (`p_home_raw = 1 / opening_moneyline_home`)
  - Transformation 2: Calculate overround (`overround = (p_home_raw + p_away_raw) - 1`)
  - Transformation 3: De-vig to fair probabilities (`p_home_fair = p_home_raw / (p_home_raw + p_away_raw)`)
  - Output: Features ready for `build_design_matrix()`
- **Benefits**: Converts odds to probability space, maintains interpretability
- **Trade-offs**: Requires domain knowledge, NULL handling needed
- **Rationale**: Standard approach in sports analytics - convert market odds to probabilities

### Algorithm Analysis

#### Algorithm: CatBoost Gradient Boosting
- **Type**: Gradient Boosting (ensemble learning)
- **Complexity**: Training: O(n × m × d × iterations), Prediction: O(iterations × d) per sample
- **Description**: Ensemble of decision trees trained sequentially, handles categorical features natively, can automatically discover feature interactions
- **Use Case**: Win probability prediction from game state + opening odds
- **Performance**: Linear in dataset size, handles missing values natively
- **Rationale**: Data scientist recommendation ("just use catboost"), can discover interactions automatically, handles missing values

### Design Decision Analysis

#### Design Decision: Direct Features vs. Decay-Weighted Interactions for CatBoost
- **Problem**: How to incorporate opening odds into CatBoost model (direct features vs. manual interaction terms)
- **Context**: Data scientist recommends CatBoost for automatic interaction discovery. Opening odds information value decays over time.
- **Project Scope**: Single sprint, focused on CatBoost implementation
- **Options**: 
  1. Direct features only (let CatBoost discover interactions)
  2. Decay-weighted interaction terms (manual engineering)
- **Selected**: Option 1 (Direct Features) - CHOSEN
  - **Design Pattern**: Feature Engineering Pattern
  - **Algorithm**: Direct feature addition (O(n))
  - **Implementation Complexity**: Low (2-3 hours)
  - **Maintenance Overhead**: Low (no manual interaction terms to maintain)
  - **Scalability**: Good (linear in dataset size)
  - **Cost-Benefit**: Low cost, High benefit (simpler implementation, CatBoost discovers optimal interactions)
  - **Over-Engineering Risk**: None (matches problem complexity)
  - **Selected**: Simplest approach, matches data scientist recommendation, CatBoost can discover interactions automatically

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 2-3 hours (straightforward feature addition)
- **Learning Curve**: Minimal (standard feature engineering)
- **Configuration Effort**: None (uses existing infrastructure)

**Maintenance Cost**:
- **Monitoring**: None (standard model training pipeline)
- **Updates**: None (opening odds pre-computed in canonical dataset)
- **Debugging**: Low (straightforward feature addition)

**Performance Benefit**:
- **Model Accuracy**: Expected improvement in Brier score / log-loss (to be measured)
- **Grid Search Performance**: Expected improvement in expected value / win rate (to be measured)

**Maintainability Benefit**:
- **Code Quality**: Minimal change (adds features to existing pipeline)
- **Developer Productivity**: Standard feature engineering approach
- **System Reliability**: No change (backward compatible)

**Risk Cost**:
- **Risk 1**: Opening odds not available for all games - Mitigated by CatBoost handling missing values natively
- **Risk 2**: Model performance doesn't improve - Mitigated by evaluation and comparison

**Over-Engineering Prevention**:
- **Problem Complexity**: Low-Medium (feature addition)
- **Solution Complexity**: Low (direct features)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Standard approach, scalable to additional features

**Chosen Solution**: Direct features with CatBoost automatic interaction discovery. Simplest implementation, matches data scientist recommendation, maintains code simplicity.

## Testing Strategy

### Testing Approach
- **Unit Tests**: Test de-vigging logic with known odds values, test missingness flags
- **Integration Tests**: Test model training with opening odds, test evaluation script
- **E2E Tests**: Train model end-to-end, evaluate performance
- **Performance Tests**: Verify training time not significantly increased

## Deployment Plan
- **Pre-Deployment**: Verify parity validation passed, verify model training successful
- **Deployment Steps**: N/A (code changes only, no deployment needed)
- **Post-Deployment**: Monitor model performance, verify feature importance
- **Rollback Plan**: Revert code changes if issues arise

## Risk Assessment
- **Technical Risks**: 
  - **CRITICAL**: Wrong odds format conversion (decimal vs American) - Mitigated by Story 2.1 (odds format validation before implementation)
  - Opening odds not available for all games (NULL values) - Mitigated by CatBoost handling missing natively
  - Model performance doesn't improve - Mitigated by evaluation and comparison
  - Parity validation fails - Mitigated by Option B approach (join ESPN tables)
  - Code drift in de-vigging logic - Mitigated by Story 2.2 (shared helper function)
  - Feature name ordering inconsistencies - Mitigated by Story 3.1 (ODDS_FEATURES constant)
  - Train/test split differences between models - Mitigated by Story 4.1 (fixed random seed and split file persistence)
- **Business Risks**: 
  - Time investment doesn't yield model improvement - Mitigated by data scientist recommendation suggests it will help
- **Resource Risks**: 
  - Training time increases - Mitigated by minimal feature addition (4-6 features)

## Success Metrics
- **Technical**: 
  - Model trains successfully with opening odds (100% success rate)
  - Feature importance shows opening odds in top 50%
  - Time-bucketed evaluation shows improvement in early-game buckets
- **Business**: 
  - Brier score improvement: 5-10% globally, 10-15% in early-game buckets
  - Log-loss improvement: 5-10% globally, 10-15% in early-game buckets
- **Sprint**: 
  - All stories completed according to acceptance criteria
  - All quality gates pass (100% pass rate)

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)

### Post-Sprint Quality Comparison
- **Test Results**: [TODO: Record pass rate and quality change]
- **Linting Results**: [TODO: Record error/warning counts and quality change]
- **Code Coverage**: [TODO: Record coverage percentage and quality change]
- **Build Status**: [TODO: Record build success and quality change]
- **Overall Assessment**: [TODO: Assess overall quality impact of sprint]

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.
