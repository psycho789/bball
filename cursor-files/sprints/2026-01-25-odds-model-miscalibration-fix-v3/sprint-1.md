# Sprint Plan: Odds Model Miscalibration Fix - Stronger Regularization

**Date**: Sun Jan 25 03:23:19 UTC 2026  
**Sprint Duration**: 4-5 days (24-30 hours total)  
**Sprint Goal**: Fix odds model miscalibration by increasing regularization, reducing feature importance from 69.19% to <50%, normalizing calibration parameters, and improving trading performance from $776.85 to >$1,000  
**Current Status**: v2 models have partial regularization (l2_leaf_reg=10.0, depth=4) but still show 69.19% feature importance from opening odds (target <50%) and extreme calibration parameters (Alpha: -0.0228, Beta: 1.209). Trading performance is poor ($776.85 vs $1,776.10 for baseline).  
**Target Status**: All 4 odds models retrained with stronger regularization (l2_leaf_reg=20.0, depth=3), feature importance <50% from opening odds, calibration parameters in normal ranges (Alpha: 0.5-2.0, Beta: -1.0 to 1.0), trading performance >$1,000 with >200 trades and >60% win rate.  
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

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified - run test suite before starting]
- **QC Results**: [To be verified - run linting/type checking]
- **Code Coverage**: [To be verified - check coverage if available]
- **Build Status**: [To be verified - ensure codebase builds successfully]

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

## Sprint Overview

### Business Context

- **Business Driver**: Odds-enabled models (`catboost_odds_platt_v2`, `catboost_odds_isotonic_v2`, etc.) are severely underperforming in trading strategy ($776.85 vs $1,776.10 for baseline models). This represents a 56% profit loss and makes odds models unusable for production trading. The root cause is miscalibration: models produce 96.6% average probability when opening odds are present (severely overconfident), leading to fewer trades (259 vs 331) and lower win rate (57.9% vs 66.5%).
- **Success Criteria**: 
  - Feature importance <50% from opening odds (currently 69.19%)
  - Calibration parameters in normal ranges (Alpha: 0.5-2.0, Beta: -1.0 to 1.0)
  - Trading performance >$1,000 profit, >200 trades, >60% win rate
  - Average probability when odds present: 50-65% (not 96.6%)
- **Stakeholders**: Data science team, trading strategy developers, model users
- **Timeline Constraints**: None - can be completed in single sprint

### Technical Context

- **Current System State**: 
  - v2 odds models trained with partial regularization:
    - `l2_leaf_reg`: 10.0 (increased from default 3.0)
    - `depth`: 4 (reduced from default 6)
    - `subsample`: 0.8
    - `random_strength`: 1.0
    - `bagging_temperature`: 1.0
  - Feature importance: 69.19% from opening odds (target <50%)
  - Calibration parameters: Alpha = -0.0228 (extreme), Beta = 1.209 (extreme)
  - Trading performance: $776.85 profit, 259 trades, 57.9% win rate
  - File: `scripts/model/train_winprob_catboost.py:879-893` (current regularization parameters)
- **Target System State**: 
  - Stronger regularization:
    - `l2_leaf_reg`: 20.0 (increased from 10.0)
    - `depth`: 3 (reduced from 4)
    - `subsample`: 0.8 (unchanged)
    - `random_strength`: 1.0 (unchanged)
    - `bagging_temperature`: 1.0 (unchanged)
  - Feature importance: <50% from opening odds
  - Calibration parameters: Alpha 0.5-2.0, Beta -1.0 to 1.0
  - Trading performance: >$1,000 profit, >200 trades, >60% win rate
  - Feature importance validation after training (warn if >50%)
  - Calibration parameter validation after calibration (warn if outside normal ranges)
- **Architecture Impact**: No architectural changes - only training configuration and validation improvements
- **Integration Points**: 
  - Model training pipeline (`train_winprob_catboost.py`)
  - Model evaluation pipeline (`evaluate_winprob_model.py`)
  - Probability precomputation (`precompute_model_probabilities.py`)
  - Trading strategy simulation (`simulate_trading_strategy.py`)
  - Grid search hyperparameter optimization (uses precomputed probabilities)

### Sprint Scope

- **In Scope**: 
  - Increase regularization parameters (l2_leaf_reg: 10.0 → 20.0, depth: 4 → 3)
  - Add feature importance validation (warn if opening odds >50%)
  - Add calibration parameter validation (warn if outside normal ranges)
  - Retrain all 4 odds-enabled v2 models with stronger regularization
  - Evaluate retrained models on test set
  - Extract feature importance from retrained models
  - Verify calibration parameters are in normal ranges
  - Precompute probabilities for retrained models
  - Run grid search to verify trading performance improvement
  - Update documentation
- **Out of Scope**: 
  - Feature engineering changes (log transforms, normalization changes) - deferred to future sprint if regularization alone doesn't work
  - Changes to baseline models (they don't use opening odds)
  - Changes to v1 models (legacy, not actively maintained)
  - Changes to model architecture (only configuration changes)
- **Assumptions**: 
  - Stronger regularization will reduce feature importance to <50% without requiring feature engineering
  - Database access available for model retraining and evaluation
  - Training data available (2017-2022 seasons)
  - Existing model artifacts can be overwritten
- **Constraints**: 
  - Model retraining requires 30-60 minutes per model (4 models = 2-4 hours total)
  - Must maintain backward compatibility with artifact loading (old artifacts may still exist)
  - Must update precomputed probabilities after retraining
  - Grid search requires precomputed probabilities (must complete precomputation first)

## Sprint Phases

### Phase 1: Code Changes - Increase Regularization and Add Validation (Duration: 4-6 hours)
**Objective**: Update training script with stronger regularization parameters and add validation functions

**Dependencies**: None (code changes only)

**Deliverables**: 
- Updated `train_winprob_catboost.py` with stronger regularization (l2_leaf_reg=20.0, depth=3)
- Feature importance validation function (warns if opening odds >50%)
- Calibration parameter validation function (warns if outside normal ranges)
- All code changes tested and verified

### Phase 2: Model Retraining (Duration: 4-6 hours)
**Objective**: Retrain all 4 odds-enabled v2 models with stronger regularization

**Dependencies**: Must complete Phase 1 (code changes)

**Deliverables**: 
- 4 retrained v2 odds-enabled model artifacts
- Feature importance analysis showing <50% from opening odds
- Calibration parameter analysis showing normal ranges
- Training logs documenting regularization parameters used

### Phase 3: Evaluation and Verification (Duration: 4-6 hours)
**Objective**: Evaluate retrained models and verify improvements

**Dependencies**: Must complete Phase 2 (model retraining)

**Deliverables**: 
- Performance evaluation on test set (2024 season)
- Feature importance extraction from all 4 models
- Calibration parameter verification (all in normal ranges)
- Average probability analysis (should be 50-65% when odds present, not 96.6%)
- Updated precomputed probabilities
- Grid search results showing improved trading performance

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint

**Dependencies**: Must complete Phase 3 successfully

**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Code Changes - Regularization and Validation
**Priority**: Critical (must update code before retraining)
**Estimated Time**: 4-6 hours (2 hours regularization update, 2 hours validation functions, 1-2 hours testing)
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Increase Regularization Parameters
- **ID**: S1-E1-S1
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `CatBoostClassifier` instantiation updated with `l2_leaf_reg=20.0` (changed from 10.0)
  - [ ] `CatBoostClassifier` instantiation updated with `depth=3` (changed from 4)
  - [ ] `subsample=0.8` remains unchanged
  - [ ] `random_strength=1.0` remains unchanged
  - [ ] `bagging_temperature=1.0` remains unchanged
  - [ ] Training script runs without errors with new parameters
  - [ ] Training logs show correct regularization parameters (l2_leaf_reg=20.0, depth=3)

- **Technical Context**:
  - **Current State**: 
    ```python
    # scripts/model/train_winprob_catboost.py:879-893
    model = CatBoostClassifier(
        iterations=int(args.iterations),
        depth=4,  # REDUCE from args.depth (default 6) to 4 for regularization
        learning_rate=float(args.learning_rate),
        l2_leaf_reg=10.0,  # ADD: Increase from default 3.0 for regularization
        subsample=0.8,  # ADD: Use 80% of data per tree for regularization
        random_strength=1.0,  # ADD: Regularization
        bagging_temperature=1.0,  # ADD: Regularization
        loss_function='Logloss',
        eval_metric='AUC',
        verbose=500,
        random_seed=42,
        allow_writing_files=False,
        thread_count=-1,
    )
    ```
  - **Required Changes**: 
    ```python
    # After implementation
    model = CatBoostClassifier(
        iterations=int(args.iterations),
        depth=3,  # REDUCE from 4 to 3 for stronger regularization
        learning_rate=float(args.learning_rate),
        l2_leaf_reg=20.0,  # INCREASE from 10.0 to 20.0 for stronger regularization
        subsample=0.8,  # Keep unchanged
        random_strength=1.0,  # Keep unchanged
        bagging_temperature=1.0,  # Keep unchanged
        loss_function='Logloss',
        eval_metric='AUC',
        verbose=500,
        random_seed=42,
        allow_writing_files=False,
        thread_count=-1,
    )
    ```
  - **Integration Points**: Used by all odds-enabled model training
  - **Data Structures**: CatBoost model configuration

- **Implementation Steps**: 
  1. Read `scripts/model/train_winprob_catboost.py` to verify current state (lines 879-893)
  2. Update `depth` parameter: Change `depth=4` to `depth=3`
  3. Update `l2_leaf_reg` parameter: Change `l2_leaf_reg=10.0` to `l2_leaf_reg=20.0`
  4. Update log message (line 876): Change "Depth: 4" to "Depth: 3"
  5. Update log message (line 878): Change "l2_leaf_reg=10.0" to "l2_leaf_reg=20.0"
  6. Verify no other regularization parameters need changes
  7. Test training script syntax: `python -m py_compile scripts/model/train_winprob_catboost.py`

- **Validation Steps**: 
  - Execute: `grep -n "l2_leaf_reg\|depth=" scripts/model/train_winprob_catboost.py | grep -v "^#"`
  - Expected Output: Shows `l2_leaf_reg=20.0` and `depth=3` in CatBoostClassifier instantiation
  - Execute: `python -c "import sys; sys.path.insert(0, '.'); from scripts.model.train_winprob_catboost import main; print('Import successful')"`
  - Expected Output: No import errors
  - Execute: Check training logs after retraining (in Phase 2) - should show "l2_leaf_reg=20.0, depth=3"

- **Definition of Done**: Regularization parameters updated, code verified, training script runs without errors

- **Rollback Plan**: 
  1. Restore `depth=4` and `l2_leaf_reg=10.0` if issues found
  2. Restore log messages to original values
  3. Verify with grep that parameters restored

- **Risk Assessment**: 
  - **Risk**: Stronger regularization may reduce model performance (AUC)
  - **Mitigation**: Monitor AUC during training, can adjust if needed
  - **Contingency**: If AUC drops significantly (<0.85), try intermediate values (l2_leaf_reg=15.0, depth=3.5)

- **Success Metrics**: 
  - **Performance**: Training script runs without errors
  - **Quality**: Code passes linting
  - **Functionality**: Correct regularization parameters used in training

### Story 1.2: Add Feature Importance Validation
- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2 hours
- **Phase**: Phase 1
- **Prerequisites**: None (can run in parallel with S1-E1-S1)
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`
- **Files to Create**: None
- **Dependencies**: CatBoost library (already imported)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Function `_validate_feature_importance()` created and called after model training
  - [ ] Function extracts feature importance from trained CatBoost model
  - [ ] Function identifies opening odds features (features containing 'opening', 'odds', 'moneyline', 'spread', 'total', 'overround' in name)
  - [ ] Function calculates percentage of total importance from opening odds features
  - [ ] Function warns if opening odds features >50% of total importance
  - [ ] Warning message includes exact percentage and list of opening odds features
  - [ ] Function returns True if validation passes (<50%), False if fails (>50%)
  - [ ] Validation runs automatically after each model training

- **Technical Context**:
  - **Current State**: No feature importance validation exists after training
  - **Required Changes**: Add validation function that checks feature importance distribution
  - **Integration Points**: Called after model training, before calibration
  - **Data Structures**: CatBoost model object, feature names list, feature importance array

- **Implementation Steps**: 
  1. Read `scripts/model/train_winprob_catboost.py` to find where model training completes (after `model.fit()`)
  2. Create function `_validate_feature_importance(model, feature_names, threshold=0.5)`:
     ```python
     def _validate_feature_importance(model, feature_names, threshold=0.5):
         """Validate that opening odds features don't dominate feature importance.
         
         Args:
             model: Trained CatBoostClassifier
             feature_names: List of feature names
             threshold: Maximum allowed percentage from opening odds (default 0.5 = 50%)
         
         Returns:
             bool: True if validation passes (<threshold), False if fails (>threshold)
         """
         importance = model.get_feature_importance()
         total_importance = sum(importance)
         
         # Identify opening odds features
         odds_keywords = ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround']
         odds_indices = [
             i for i, name in enumerate(feature_names)
             if any(keyword in name.lower() for keyword in odds_keywords)
         ]
         
         # Calculate percentage from opening odds
         odds_importance = sum(importance[i] for i in odds_indices)
         odds_percentage = (odds_importance / total_importance * 100) if total_importance > 0 else 0.0
         
         # Warn if above threshold
         if odds_percentage > threshold * 100:
             odds_features = [feature_names[i] for i in odds_indices]
             print(
                 f"\n⚠️  WARNING: Opening odds features account for {odds_percentage:.2f}% of feature importance "
                 f"(threshold: {threshold*100:.0f}%)",
                 file=sys.stderr
             )
             print(f"  Opening odds features: {odds_features}", file=sys.stderr)
             print(f"  Consider increasing regularization or applying feature engineering.", file=sys.stderr)
             return False
         else:
             print(
                 f"\n✅ Feature importance validation passed: {odds_percentage:.2f}% from opening odds "
                 f"(threshold: {threshold*100:.0f}%)",
                 file=sys.stderr
             )
             return True
     ```
  3. Call function after model training: `_validate_feature_importance(model, feature_names, threshold=0.5)`
  4. Test function with sample model (if available) or verify syntax

- **Validation Steps**: 
  - Execute: `grep -n "_validate_feature_importance" scripts/model/train_winprob_catboost.py`
  - Expected Output: Function definition and at least one call site
  - Execute: `python -c "import sys; sys.path.insert(0, '.'); from scripts.model.train_winprob_catboost import _validate_feature_importance; print('Function imported successfully')"`
  - Expected Output: No import errors
  - Execute: After retraining (Phase 2), check training logs for validation output

- **Definition of Done**: Function created, called after training, warns if opening odds >50%

- **Rollback Plan**: Remove function call if issues found (function can remain but not called)

- **Risk Assessment**: 
  - **Risk**: Function may incorrectly identify opening odds features
  - **Mitigation**: Test with known feature names, verify keyword matching logic
  - **Contingency**: Adjust keyword list if needed

- **Success Metrics**: 
  - **Performance**: Function executes in <1 second
  - **Quality**: Correctly identifies opening odds features
  - **Functionality**: Warns when threshold exceeded

### Story 1.3: Add Calibration Parameter Validation
- **ID**: S1-E1-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: None (can run in parallel with S1-E1-S1 and S1-E1-S2)
- **Files to Modify**: `scripts/model/train_winprob_catboost.py`
- **Files to Create**: None
- **Dependencies**: Calibration library (already imported)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Function `_validate_calibration_parameters()` created and called after calibration
  - [ ] Function validates Platt scaling parameters (alpha and beta)
  - [ ] Function checks alpha is in range 0.5-2.0 (normal range)
  - [ ] Function checks beta is in range -1.0 to 1.0 (normal range)
  - [ ] Function warns if parameters outside normal ranges
  - [ ] Warning message includes exact parameter values and normal ranges
  - [ ] Function returns True if validation passes (all parameters in range), False if fails
  - [ ] Validation runs automatically after each calibration

- **Technical Context**:
  - **Current State**: No calibration parameter validation exists after calibration
  - **Required Changes**: Add validation function that checks Platt scaling parameters
  - **Integration Points**: Called after Platt calibration, before model artifact saving
  - **Data Structures**: Platt calibration object with `alpha_` and `beta_` attributes

- **Implementation Steps**: 
  1. Read `scripts/model/train_winprob_catboost.py` to find where Platt calibration completes (after `platt_scaler.fit()`)
  2. Create function `_validate_calibration_parameters(calibrator, method='platt')`:
     ```python
     def _validate_calibration_parameters(calibrator, method='platt'):
         """Validate that calibration parameters are in normal ranges.
         
         Args:
             calibrator: Trained calibration object (PlattScaler or IsotonicRegressor)
             method: Calibration method ('platt' or 'isotonic')
         
         Returns:
             bool: True if validation passes (parameters in normal ranges), False if fails
         """
         if method == 'platt':
             alpha = calibrator.alpha_
             beta = calibrator.beta_
             
             alpha_normal = 0.5 <= alpha <= 2.0
             beta_normal = -1.0 <= beta <= 1.0
             
             if not alpha_normal or not beta_normal:
                 print(
                     f"\n⚠️  WARNING: Platt calibration parameters outside normal ranges:",
                     file=sys.stderr
                 )
                 print(f"  Alpha: {alpha:.4f} (normal: 0.5-2.0) {'✅' if alpha_normal else '❌'}", file=sys.stderr)
                 print(f"  Beta: {beta:.4f} (normal: -1.0 to 1.0) {'✅' if beta_normal else '❌'}", file=sys.stderr)
                 print(f"  This suggests the model is producing extreme predictions.", file=sys.stderr)
                 print(f"  Consider increasing regularization or checking feature importance.", file=sys.stderr)
                 return False
             else:
                 print(
                     f"\n✅ Calibration parameter validation passed:",
                     file=sys.stderr
                 )
                 print(f"  Alpha: {alpha:.4f} (normal: 0.5-2.0) ✅", file=sys.stderr)
                 print(f"  Beta: {beta:.4f} (normal: -1.0 to 1.0) ✅", file=sys.stderr)
                 return True
         else:
             # Isotonic calibration doesn't have simple parameter ranges
             # Just log that validation was skipped
             print(f"\n✅ Calibration parameter validation skipped for {method} (no simple parameter ranges)", file=sys.stderr)
             return True
     ```
  3. Call function after Platt calibration: `_validate_calibration_parameters(platt_scaler, method='platt')`
  4. Test function with sample calibrator (if available) or verify syntax

- **Validation Steps**: 
  - Execute: `grep -n "_validate_calibration_parameters" scripts/model/train_winprob_catboost.py`
  - Expected Output: Function definition and at least one call site
  - Execute: `python -c "import sys; sys.path.insert(0, '.'); from scripts.model.train_winprob_catboost import _validate_calibration_parameters; print('Function imported successfully')"`
  - Expected Output: No import errors
  - Execute: After retraining (Phase 2), check training logs for validation output

- **Definition of Done**: Function created, called after calibration, warns if parameters outside normal ranges

- **Rollback Plan**: Remove function call if issues found (function can remain but not called)

- **Risk Assessment**: 
  - **Risk**: Function may incorrectly access calibration parameters
  - **Mitigation**: Test with known calibrator object, verify attribute names
  - **Contingency**: Adjust attribute access if needed (may be `alpha`/`beta` vs `alpha_`/`beta_`)

- **Success Metrics**: 
  - **Performance**: Function executes in <1 second
  - **Quality**: Correctly validates parameter ranges
  - **Functionality**: Warns when parameters outside normal ranges

### Epic 2: Model Retraining
**Priority**: Critical (core sprint work)
**Estimated Time**: 4-6 hours (1-1.5 hours per model × 4 models)
**Dependencies**: Must complete Epic 1 (code changes)
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Retrain catboost_odds_platt_v2
- **ID**: S1-E2-S1
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 1-1.5 hours (30-60 minutes training + 30 minutes verification)
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1, S1-E1-S2, S1-E1-S3 (code changes complete)
- **Files to Modify**: None (uses updated training script)
- **Files to Create**: New model artifact (overwrites existing)
- **Dependencies**: Updated training script, database access, training data

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Model artifact created at `artifacts/winprob_catboost_odds_platt_v2.json`
  - [ ] Training completes without errors
  - [ ] Training logs show `l2_leaf_reg=20.0` and `depth=3`
  - [ ] Feature importance validation runs and shows <50% from opening odds
  - [ ] Calibration parameter validation runs and shows parameters in normal ranges
  - [ ] Model artifact contains correct feature count (16 features: 5 base + 8 interaction + 3 opening odds)
  - [ ] Model artifact excludes `has_opening_moneyline` from feature names (removed in previous sprint)

- **Technical Context**:
  - **Current State**: Existing model artifact with 69.19% feature importance from opening odds
  - **Required Changes**: Retrain with stronger regularization (l2_leaf_reg=20.0, depth=3)
  - **Integration Points**: Uses updated `train_winprob_catboost.py`, creates artifact for precomputation and evaluation
  - **Data Structures**: Model artifact (JSON + .cbm file), feature names list

- **Implementation Steps**: 
  1. Verify training script updated (from Epic 1) - ✅ Should be complete
  2. Verify database access: `echo $DATABASE_URL` (should show PostgreSQL connection string)
  3. Retrain model:
     ```bash
     python scripts/model/train_winprob_catboost.py \
       --out-artifact artifacts/winprob_catboost_odds_platt_v2.json \
       --dsn "$DATABASE_URL" \
       --iterations 1000 \
       --learning-rate 0.1 \
       --train-season-start-max 2022 \
       --calib-season-start 2023 \
       --test-season-start 2024
     ```
  4. Monitor training logs for:
     - Regularization parameters: "l2_leaf_reg=20.0, depth=3"
     - Feature importance validation: Should show <50% from opening odds
     - Calibration parameter validation: Should show parameters in normal ranges
  5. Verify artifact created:
     ```bash
     python -c "from scripts.lib._winprob_lib import load_artifact; art = load_artifact('artifacts/winprob_catboost_odds_platt_v2.json'); print(f'Features: {len(art.feature_names)}'); print(f'Opening odds features: {[f for f in art.feature_names if \"opening\" in f.lower()]}')"
     ```
  6. Extract feature importance:
     ```bash
     python scripts/analysis/extract_feature_importance.py | grep -A 10 "catboost_odds_platt_v2"
     ```

- **Validation Steps**: 
  - Execute: Training command above
  - Expected Output: Training completes successfully, artifact created
  - Execute: Feature importance extraction command
  - Expected Output: Shows opening odds features with <50% total importance
  - Execute: Check training logs for validation messages
  - Expected Output: Feature importance validation shows <50%, calibration validation shows parameters in normal ranges
  - Execute: Verify artifact file exists: `ls -la artifacts/winprob_catboost_odds_platt_v2.json`
  - Expected Output: File exists and is recent (just created)

- **Definition of Done**: Model retrained, artifact created, feature importance <50%, calibration parameters normal

- **Rollback Plan**: Keep old artifact as backup (rename before retraining), restore if new model performs worse

- **Risk Assessment**: 
  - **Risk**: Training fails due to code errors
  - **Mitigation**: Test training script with small dataset first (if possible)
  - **Contingency**: Fix code errors, retry training
  - **Risk**: Training takes longer than estimated
  - **Mitigation**: Run training in background, monitor progress
  - **Contingency**: Extend sprint timeline if needed

- **Success Metrics**: 
  - **Performance**: Training completes in <60 minutes
  - **Quality**: Feature importance <50% from opening odds
  - **Functionality**: Calibration parameters in normal ranges

### Story 2.2: Retrain catboost_odds_isotonic_v2
- **ID**: S1-E2-S2
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 1-1.5 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1 (first model retrained, can verify approach)
- **Files to Modify**: None
- **Files to Create**: New model artifact
- **Dependencies**: Updated training script, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Model artifact created at `artifacts/winprob_catboost_odds_isotonic_v2.json`
  - [ ] Training completes without errors
  - [ ] Training logs show `l2_leaf_reg=20.0` and `depth=3`
  - [ ] Feature importance validation runs and shows <50% from opening odds
  - [ ] Model artifact contains correct feature count (16 features)

- **Implementation Steps**: 
  1. Retrain model:
     ```bash
     python scripts/model/train_winprob_catboost.py \
       --out-artifact artifacts/winprob_catboost_odds_isotonic_v2.json \
       --dsn "$DATABASE_URL" \
       --iterations 1000 \
       --learning-rate 0.1 \
       --calibration isotonic \
       --train-season-start-max 2022 \
       --calib-season-start 2023 \
       --test-season-start 2024
     ```
  2. Verify artifact created and feature importance <50%

- **Validation Steps**: Same as Story 2.1 (different artifact path)

- **Definition of Done**: Model retrained, artifact created, feature importance <50%

- **Rollback Plan**: Keep old artifact as backup

- **Risk Assessment**: Same as Story 2.1

- **Success Metrics**: Same as Story 2.1

### Story 2.3: Retrain catboost_odds_no_interaction_platt_v2
- **ID**: S1-E2-S3
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 1-1.5 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1 (can run in parallel with S1-E2-S2)
- **Files to Modify**: None
- **Files to Create**: New model artifact
- **Dependencies**: Updated training script, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Model artifact created at `artifacts/winprob_catboost_odds_no_interaction_platt_v2.json`
  - [ ] Training completes without errors
  - [ ] Feature importance validation shows <50% from opening odds
  - [ ] Model artifact contains correct feature count (9 features: 5 base + 3 opening odds + 1 possession)

- **Implementation Steps**: 
  1. Retrain model:
     ```bash
     python scripts/model/train_winprob_catboost.py \
       --out-artifact artifacts/winprob_catboost_odds_no_interaction_platt_v2.json \
       --dsn "$DATABASE_URL" \
       --iterations 1000 \
       --learning-rate 0.1 \
       --disable-interaction-terms \
       --train-season-start-max 2022 \
       --calib-season-start 2023 \
       --test-season-start 2024
     ```
  2. Verify artifact created and feature importance <50%

- **Validation Steps**: Same as Story 2.1 (different artifact path, different feature count)

- **Definition of Done**: Model retrained, artifact created, feature importance <50%

- **Rollback Plan**: Keep old artifact as backup

- **Risk Assessment**: Same as Story 2.1

- **Success Metrics**: Same as Story 2.1

### Story 2.4: Retrain catboost_odds_no_interaction_isotonic_v2
- **ID**: S1-E2-S4
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 1-1.5 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S3 (can run in parallel with S1-E2-S2)
- **Files to Modify**: None
- **Files to Create**: New model artifact
- **Dependencies**: Updated training script, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Model artifact created at `artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json`
  - [ ] Training completes without errors
  - [ ] Feature importance validation shows <50% from opening odds
  - [ ] Model artifact contains correct feature count (9 features)

- **Implementation Steps**: 
  1. Retrain model:
     ```bash
     python scripts/model/train_winprob_catboost.py \
       --out-artifact artifacts/winprob_catboost_odds_no_interaction_isotonic_v2.json \
       --dsn "$DATABASE_URL" \
       --iterations 1000 \
       --learning-rate 0.1 \
       --disable-interaction-terms \
       --calibration isotonic \
       --train-season-start-max 2022 \
       --calib-season-start 2023 \
       --test-season-start 2024
     ```
  2. Verify artifact created and feature importance <50%

- **Validation Steps**: Same as Story 2.1 (different artifact path, different feature count)

- **Definition of Done**: Model retrained, artifact created, feature importance <50%

- **Rollback Plan**: Keep old artifact as backup

- **Risk Assessment**: Same as Story 2.1

- **Success Metrics**: Same as Story 2.1

### Epic 3: Evaluation and Verification
**Priority**: Critical (must verify improvements)
**Estimated Time**: 4-6 hours (1-2 hours evaluation, 1-2 hours feature importance extraction, 1-2 hours precomputation and grid search)
**Dependencies**: Must complete Epic 2 (model retraining)
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Evaluate Retrained Models
- **ID**: S1-E3-S1
- **Type**: Testing
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E2-S1, S1-E2-S2, S1-E2-S3, S1-E2-S4 (all models retrained)
- **Files to Modify**: None (uses existing evaluation script)
- **Files to Create**: Evaluation results files
- **Dependencies**: Retrained model artifacts, updated evaluation scripts

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] All 4 retrained models evaluated on test set (2024 season)
  - [ ] Evaluation metrics computed: Brier score, log loss, ROC-AUC
  - [ ] Evaluation results saved to files or printed
  - [ ] Evaluation completes without errors
  - [ ] Metrics show performance maintained or improved (compared to v2 baseline)

- **Technical Context**:
  - **Current State**: Evaluation scripts exist and work with v2 models
  - **Required Changes**: Run evaluation on retrained models
  - **Integration Points**: Uses `evaluate_winprob_model.py`, retrained artifacts
  - **Data Structures**: Evaluation metrics dictionaries, JSON results

- **Implementation Steps**: 
  1. Evaluate each retrained model:
     ```bash
     python scripts/model/evaluate_winprob_model.py \
       --artifact artifacts/winprob_catboost_odds_platt_v2.json \
       --dsn "$DATABASE_URL" \
       --season-start 2024
     ```
  2. Repeat for all 4 models (change `--artifact` path)
  3. Collect and document results
  4. Compare with previous v2 results (if available)

- **Validation Steps**: 
  - Execute: Evaluation commands for all 4 models
  - Expected Output: All evaluations complete successfully, metrics printed
  - Execute: Compare metrics with previous v2 results
  - Expected Output: Performance maintained or improved (Brier score, log loss, ROC-AUC)

- **Definition of Done**: All models evaluated, metrics documented, performance verified

- **Rollback Plan**: Use old models if new models perform worse

- **Risk Assessment**: 
  - **Risk**: Models perform worse than before
  - **Mitigation**: Compare metrics, investigate if degradation significant
  - **Contingency**: Keep old models if performance degrades significantly (>10% worse)

- **Success Metrics**: 
  - **Performance**: Evaluation completes in <30 minutes per model
  - **Quality**: Metrics computed accurately
  - **Functionality**: Performance maintained or improved

### Story 3.2: Extract Feature Importance from Retrained Models
- **ID**: S1-E3-S2
- **Type**: Research
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1 (models evaluated, can run in parallel)
- **Files to Modify**: None (uses existing script)
- **Files to Create**: Feature importance results file
- **Dependencies**: Retrained model artifacts, `scripts/analysis/extract_feature_importance.py`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Feature importance extracted from all 4 retrained models
  - [ ] Opening odds feature importance calculated and documented
  - [ ] All models show <50% feature importance from opening odds
  - [ ] Results saved to file or printed
  - [ ] Comparison with previous v2 results documented

- **Implementation Steps**: 
  1. Run feature importance extraction:
     ```bash
     python scripts/analysis/extract_feature_importance.py > feature_importance_v3_results.txt
     ```
  2. Parse results and verify <50% from opening odds for all models
  3. Document findings

- **Validation Steps**: 
  - Execute: Feature importance extraction command
  - Expected Output: Shows opening odds features with <50% total importance for all 4 models
  - Execute: `grep -A 5 "opening" feature_importance_v3_results.txt | head -20`
  - Expected Output: Shows opening odds feature importance percentages, all <50%

- **Definition of Done**: Feature importance extracted, all models <50% from opening odds

- **Rollback Plan**: N/A (analysis only)

- **Risk Assessment**: 
  - **Risk**: Feature importance still >50% after retraining
  - **Mitigation**: If >50%, retrain with even stronger regularization (l2_leaf_reg=30.0, depth=2)
  - **Contingency**: Document findings and plan next steps

- **Success Metrics**: 
  - **Performance**: Extraction completes in <5 minutes
  - **Quality**: All models show <50% from opening odds
  - **Functionality**: Results documented clearly

### Story 3.3: Verify Calibration Parameters
- **ID**: S1-E3-S3
- **Type**: Testing
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1 (models evaluated, can run in parallel with S1-E3-S2)
- **Files to Modify**: None (uses existing inspection script)
- **Files to Create**: Calibration parameter results file
- **Dependencies**: Retrained model artifacts, `scripts/analysis/inspect_odds_model_artifact.py`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Calibration parameters extracted from all retrained models (Platt models only)
  - [ ] Alpha values in range 0.5-2.0 (normal range)
  - [ ] Beta values in range -1.0 to 1.0 (normal range)
  - [ ] Results documented
  - [ ] Comparison with previous v2 results documented

- **Implementation Steps**: 
  1. Inspect each Platt model artifact:
     ```bash
     python scripts/analysis/inspect_odds_model_artifact.py \
       artifacts/winprob_catboost_odds_platt_v2.json
     ```
  2. Extract calibration parameters (alpha, beta) from output
  3. Verify all parameters in normal ranges
  4. Document findings

- **Validation Steps**: 
  - Execute: Inspection commands for Platt models (2 models)
  - Expected Output: Shows calibration parameters in normal ranges
  - Execute: Check if parameters are in ranges: alpha 0.5-2.0, beta -1.0 to 1.0
  - Expected Output: All parameters in normal ranges

- **Definition of Done**: Calibration parameters verified, all in normal ranges

- **Rollback Plan**: N/A (verification only)

- **Risk Assessment**: 
  - **Risk**: Calibration parameters still extreme after retraining
  - **Mitigation**: If extreme, check feature importance - may need even stronger regularization
  - **Contingency**: Document findings and plan next steps

- **Success Metrics**: 
  - **Performance**: Inspection completes in <5 minutes per model
  - **Quality**: All parameters in normal ranges
  - **Functionality**: Results documented clearly

### Story 3.4: Update Precomputed Probabilities
- **ID**: S1-E3-S4
- **Type**: Configuration
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1, S1-E3-S2, S1-E3-S3 (models evaluated and verified)
- **Files to Modify**: None (uses existing precomputation script)
- **Files to Create**: Updated precomputed probabilities in database
- **Dependencies**: Retrained model artifacts, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Precomputed probabilities updated for all 4 retrained models
  - [ ] Precomputation completes without errors
  - [ ] Database records updated (verify with SQL query)
  - [ ] Precomputation logs show all 4 models processed

- **Implementation Steps**: 
  1. Update precomputed probabilities:
     ```bash
     python scripts/model/precompute_model_probabilities.py \
       --dsn "$DATABASE_URL" \
       --models catboost_odds_platt_v2,catboost_odds_isotonic_v2,catboost_odds_no_interaction_platt_v2,catboost_odds_no_interaction_isotonic_v2
     ```
  2. Verify precomputation completed:
     ```sql
     SELECT model_name, COUNT(*) as probability_count 
     FROM derived.model_probabilities_v1 
     WHERE model_name IN ('catboost_odds_platt_v2', 'catboost_odds_isotonic_v2', 'catboost_odds_no_interaction_platt_v2', 'catboost_odds_no_interaction_isotonic_v2')
     GROUP BY model_name;
     ```

- **Validation Steps**: 
  - Execute: Precomputation command
  - Expected Output: Precomputation completes without errors, progress logs show all 4 models processed
  - Execute: SQL query to verify database records
  - Expected Output: All 4 models have probability records (count > 0 for each)

- **Definition of Done**: Precomputation updated, database records verified

- **Rollback Plan**: Restore old precomputed probabilities if needed (requires database backup)

- **Risk Assessment**: 
  - **Risk**: Precomputation takes long time
  - **Mitigation**: Run in background, monitor progress
  - **Contingency**: Extend timeline if needed

- **Success Metrics**: 
  - **Performance**: Precomputation completes in <2 hours
  - **Quality**: All probabilities updated correctly
  - **Functionality**: Database records verified

### Story 3.5: Verify Trading Performance Improvement
- **ID**: S1-E3-S5
- **Type**: Testing
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S4 (precomputed probabilities updated)
- **Files to Modify**: None (uses existing grid search script)
- **Files to Create**: Grid search results file
- **Dependencies**: Updated precomputed probabilities, `scripts/trade/grid_search_hyperparameters.py`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Grid search run for all 4 retrained odds models
  - [ ] Trading performance metrics computed: profit, trades, win rate
  - [ ] All models show >$1,000 profit (target)
  - [ ] All models show >200 trades (target)
  - [ ] All models show >60% win rate (target)
  - [ ] Performance improved compared to previous v2 results ($776.85 → >$1,000)
  - [ ] Results documented in comparison table

- **Implementation Steps**: 
  1. Run grid search for retrained models:
     ```bash
     python scripts/trade/grid_search_hyperparameters.py \
       --dsn "$DATABASE_URL" \
       --models catboost_odds_platt_v2,catboost_odds_isotonic_v2,catboost_odds_no_interaction_platt_v2,catboost_odds_no_interaction_isotonic_v2
     ```
  2. Compare results with previous v2 results (from `data/grid_search/model_comparison.json`)
  3. Document performance improvement
  4. Verify all models meet success criteria (>$1,000 profit, >200 trades, >60% win rate)

- **Validation Steps**: 
  - Execute: Grid search command
  - Expected Output: Grid search completes successfully, results saved
  - Execute: Compare results with previous v2 results
  - Expected Output: Performance improved (profit >$1,000 vs $776.85)
  - Execute: Verify success criteria met
  - Expected Output: All models show >$1,000 profit, >200 trades, >60% win rate

- **Definition of Done**: Grid search completed, performance improved, success criteria met

- **Rollback Plan**: Use old models if new models perform worse

- **Risk Assessment**: 
  - **Risk**: Trading performance doesn't improve despite feature importance reduction
  - **Mitigation**: Investigate other factors (threshold selection, calibration quality)
  - **Contingency**: Document findings and plan next steps (may need feature engineering)

- **Success Metrics**: 
  - **Performance**: Grid search completes in <2 hours
  - **Quality**: All models meet success criteria
  - **Functionality**: Performance improved compared to v2 baseline

### Story 3.6: Verify Average Probability Improvement
- **ID**: S1-E3-S6
- **Type**: Testing
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S4 (precomputed probabilities updated)
- **Files to Modify**: None (SQL query only)
- **Files to Create**: Average probability analysis results
- **Dependencies**: Updated precomputed probabilities, database access

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Average probability computed for retrained models when opening odds present
  - [ ] Average probability in range 50-65% (target, not 96.6%)
  - [ ] Average probability computed when opening odds missing
  - [ ] Results documented and compared with previous v2 results

- **Implementation Steps**: 
  1. Query average probabilities:
     ```sql
     SELECT 
         CASE 
             WHEN sf.opening_moneyline_home IS NOT NULL THEN 'has_odds'
             ELSE 'no_odds'
         END as odds_status,
         AVG(mp.catboost_odds_platt_v2_prob) as avg_prob_platt_v2,
         AVG(mp.catboost_odds_isotonic_v2_prob) as avg_prob_isotonic_v2,
         COUNT(*) as snapshot_count
     FROM derived.snapshot_features_v1 sf
     JOIN derived.model_probabilities_v1 mp
         ON sf.season_label = mp.season_label
         AND sf.game_id = mp.game_id
         AND sf.sequence_number = mp.sequence_number
         AND sf.snapshot_ts = mp.snapshot_ts
     WHERE sf.season_label LIKE '2024-%'  -- Test set
     GROUP BY odds_status;
     ```
  2. Verify average probability when odds present is 50-65% (not 96.6%)
  3. Document results

- **Validation Steps**: 
  - Execute: SQL query above
  - Expected Output: Average probability when odds present is 50-65% (not 96.6%)
  - Execute: Compare with previous v2 results
  - Expected Output: Average probability reduced from 96.6% to 50-65%

- **Definition of Done**: Average probability verified, in target range 50-65%

- **Rollback Plan**: N/A (verification only)

- **Risk Assessment**: 
  - **Risk**: Average probability still extreme (>80%) after retraining
  - **Mitigation**: Check feature importance - may need even stronger regularization
  - **Contingency**: Document findings and plan next steps

- **Success Metrics**: 
  - **Performance**: Query completes in <1 minute
  - **Quality**: Average probability in target range
  - **Functionality**: Results documented clearly

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story 4.1: Documentation Update
- **ID**: SPRINT-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed (S1-E1-S1 through S1-E3-S6)

- **Acceptance Criteria**: 
  - [ ] Model documentation (`cursor-files/models/README.md`) updated with new regularization parameters
  - [ ] Analysis documents updated with v3 results (feature importance, calibration parameters, trading performance)
  - [ ] Sprint completion report created
  - [ ] All relevant documentation updated

- **Technical Context**: 
  - **Current State**: Documentation reflects v2 regularization parameters
  - **Required Changes**: Update with v3 parameters and results

- **Implementation Steps**: 
  1. Update `cursor-files/models/README.md` with new regularization parameters (l2_leaf_reg=20.0, depth=3)
  2. Create analysis document with v3 results (feature importance, calibration parameters, trading performance)
  3. Create sprint completion report
  4. Update any other relevant documentation

- **Validation Steps**: 
  - Verify: Documentation updated with correct parameters
  - Verify: Analysis documents created with v3 results
  - Verify: Sprint report created

### Story 4.2: Quality Gate Validation
- **ID**: SPRINT-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All tests pass (100% pass rate required)
  - [ ] Build process completes without errors
  - [ ] Code quality maintained or improved
  - [ ] All previous story acceptance criteria verified

- **Technical Context**:
  - **Current State**: Code changes made to training script
  - **Required Changes**: Run quality checks, fix any issues

- **Implementation Steps**: 
  1. Run linting: `ruff check scripts/` (or equivalent)
  2. Run type checking: `mypy scripts/` (or equivalent)
  3. Run tests: `pytest tests/` (or equivalent)
  4. Fix any issues found
  5. Re-run checks until all pass

- **Validation Steps**: 
  - Execute: Linting command
  - Verify: Zero errors and warnings
  - Execute: Type checking command
  - Verify: No type errors
  - Execute: Test suite
  - Verify: 100% pass rate

### Story 4.3: Sprint Completion and Archive
- **ID**: SPRINT-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**: 
  - [ ] Sprint completion report created
  - [ ] All files organized in sprint directory
  - [ ] Sprint marked as completed
  - [ ] Post-sprint quality comparison documented

- **Technical Context**: 
  - **Current State**: Sprint work completed
  - **Required Changes**: Create report, organize files, archive

- **Implementation Steps**: 
  1. Create sprint completion report
  2. Organize all sprint files
  3. Document post-sprint quality metrics
  4. Mark sprint as completed

- **Validation Steps**: 
  - Verify: Report created
  - Verify: Files organized
  - Verify: Sprint marked complete

## Technical Decisions

### Design Decision: Stronger Regularization Approach

**Problem Statement**:
- v2 models have 69.19% feature importance from opening odds (target <50%)
- Calibration parameters are extreme (Alpha: -0.0228, Beta: 1.209)
- Trading performance is poor ($776.85 vs $1,776.10 for baseline)

**Multiple Solution Analysis**:

**Option 1: Increase Regularization Only**
- **Design Pattern**: None (configuration change)
- **Algorithm**: CatBoost gradient boosting (unchanged)
- **Implementation Complexity**: Low (2-3 hours) - just parameter changes
- **Maintenance Overhead**: Low (no code changes, just configuration)
- **Scalability**: Good (same training time)
- **Cost-Benefit**: Low cost, Medium-High benefit
- **Over-Engineering Risk**: None (minimal change)
- **Selected**: ✅ **CHOSEN** - Simplest approach, addresses root cause directly

**Option 2: Feature Engineering Changes**
- **Design Pattern**: None (feature transformation)
- **Algorithm**: CatBoost gradient boosting (unchanged)
- **Implementation Complexity**: Medium (4-6 hours) - need to modify feature computation
- **Maintenance Overhead**: Medium (more complex feature engineering)
- **Scalability**: Good (same training time)
- **Cost-Benefit**: Medium cost, Medium benefit
- **Over-Engineering Risk**: Low (but unnecessary if regularization works)
- **Rejected**: Defer to future sprint if regularization alone doesn't work

**Option 3: Hybrid Approach (Regularization + Feature Engineering)**
- **Design Pattern**: None (combination)
- **Algorithm**: CatBoost gradient boosting (unchanged)
- **Implementation Complexity**: High (6-8 hours) - both regularization and feature changes
- **Maintenance Overhead**: High (more complex)
- **Scalability**: Good (same training time)
- **Cost-Benefit**: High cost, High benefit
- **Over-Engineering Risk**: Medium (may be unnecessary)
- **Rejected**: Start with simpler approach (regularization only), add feature engineering if needed

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 2-3 hours (parameter changes only)
- **Learning Curve**: 0 hours (team already familiar with CatBoost)
- **Configuration Effort**: 1 hour (testing and verification)

**Maintenance Cost**:
- **Monitoring**: 0 hours/month (no ongoing monitoring needed)
- **Updates**: 0 hours/month (configuration is stable)
- **Debugging**: 1 hour/incident (simple configuration, easy to debug)

**Performance Benefit**:
- **Feature Importance**: 69.19% → <50% (19%+ reduction)
- **Calibration Quality**: Extreme → Normal (parameters in ranges)
- **Trading Performance**: $776.85 → >$1,000 (29%+ improvement target)

**Maintainability Benefit**:
- **Code Quality**: No code changes (configuration only)
- **Developer Productivity**: Simpler configuration, easier to understand
- **System Reliability**: More stable model behavior

**Risk Cost**:
- **Risk 1**: Regularization may reduce model performance (AUC) - Low risk, mitigated by monitoring AUC during training
- **Risk 2**: Feature importance may still be >50% - Medium risk, mitigated by validation function and iterative approach

**Over-Engineering Prevention**:
- **Problem Complexity**: Medium (configuration tuning)
- **Solution Complexity**: Low (parameter changes)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Configuration can be adjusted further if needed

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Low complexity for medium project
- **Team Capability**: ✅ Team familiar with CatBoost regularization
- **Timeline Constraints**: ✅ Fits within single sprint
- **Future Growth**: ✅ Can adjust further if needed
- **Technical Debt**: ✅ Reduces technical debt (fixes miscalibration)

**Chosen Solution**: Increase regularization parameters (l2_leaf_reg: 10.0 → 20.0, depth: 4 → 3) and add validation functions to monitor feature importance and calibration parameters.

**Pros and Cons Analysis**:

**Pros**:
- **Simplicity**: Minimal code changes, just parameter updates
- **Effectiveness**: Addresses root cause directly (insufficient regularization)
- **Low Risk**: Configuration change, easy to revert if needed
- **Fast Implementation**: Can be done in single sprint
- **Maintainability**: No complex code changes, easier to maintain

**Cons**:
- **May Not Be Enough**: If feature importance still >50%, may need feature engineering
- **Performance Risk**: Stronger regularization may reduce AUC slightly
- **Iteration May Be Needed**: May need to adjust parameters further

**Risk Assessment**:
- **Risk 1**: Feature importance still >50% after retraining
  - **Mitigation**: Add validation function to warn if >50%, plan iterative approach
  - **Contingency**: If >50%, retrain with even stronger regularization (l2_leaf_reg=30.0, depth=2) or add feature engineering
- **Risk 2**: Model performance (AUC) degrades significantly
  - **Mitigation**: Monitor AUC during training, can adjust parameters if needed
  - **Contingency**: Try intermediate values (l2_leaf_reg=15.0, depth=3.5) if AUC drops too much

**Trade-off Analysis**:
- **Sacrificed**: Slight potential reduction in AUC (may drop from 0.8989 to 0.88-0.89)
- **Gained**: Balanced feature importance, normal calibration, improved trading performance
- **Net Benefit**: Significant improvement in trading performance ($776.85 → >$1,000) outweighs potential small AUC reduction

## Testing Strategy

### Testing Approach
- **Unit Tests**: Verify validation functions work correctly (feature importance calculation, calibration parameter checking)
- **Integration Tests**: Verify training pipeline produces correct artifacts with new parameters
- **E2E Tests**: Verify end-to-end workflow (training → evaluation → precomputation → grid search)
- **Performance Tests**: Compare model performance metrics (Brier score, log loss, ROC-AUC, trading performance)

## Deployment Plan

- **Pre-Deployment**: 
  - [ ] All code changes verified
  - [ ] All models retrained
  - [ ] All tests passing
  - [ ] Documentation updated
- **Deployment Steps**: 
  - [ ] Deploy updated training script
  - [ ] Deploy retrained model artifacts
  - [ ] Update precomputed probabilities
  - [ ] Verify grid search uses new models
- **Post-Deployment**: 
  - [ ] Verify models work correctly in production
  - [ ] Monitor trading performance metrics
  - [ ] Verify precomputed probabilities used correctly

## Risk Assessment

- **Technical Risks**: 
  - **Risk**: Feature importance still >50% after stronger regularization
    - **Probability**: Medium
    - **Impact**: High (target not met)
    - **Mitigation**: Add validation function, plan iterative approach (l2_leaf_reg=30.0, depth=2 if needed)
  - **Risk**: Model performance (AUC) degrades significantly
    - **Probability**: Low
    - **Impact**: Medium (worse predictions)
    - **Mitigation**: Monitor AUC during training, can adjust parameters if needed
- **Business Risks**: 
  - **Risk**: Trading performance doesn't improve despite feature importance reduction
    - **Probability**: Low
    - **Impact**: High (sprint goal not met)
    - **Mitigation**: Investigate other factors (threshold selection, calibration quality), plan feature engineering if needed
- **Resource Risks**: 
  - **Risk**: Model retraining takes longer than estimated
    - **Probability**: Medium
    - **Impact**: Low (delays completion)
    - **Mitigation**: Run training in background, monitor progress

## Success Metrics

- **Technical**: 
  - Feature importance <50% from opening odds (currently 69.19%)
  - Calibration parameters in normal ranges (Alpha: 0.5-2.0, Beta: -1.0 to 1.0)
  - Model performance maintained or improved (Brier score, log loss, ROC-AUC)
- **Business**: 
  - Trading performance >$1,000 profit (currently $776.85)
  - Trading performance >200 trades (currently 259)
  - Trading performance >60% win rate (currently 57.9%)
  - Average probability when odds present: 50-65% (currently 96.6%)
- **Sprint**: 
  - All stories completed
  - Quality gates passed
  - Documentation updated

## Sprint Completion Checklist

- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)

### Post-Sprint Quality Comparison

- **Test Results**: [To be filled after sprint]
- **Linting Results**: [To be filled after sprint]
- **Code Coverage**: [To be filled after sprint]
- **Build Status**: [To be filled after sprint]
- **Overall Assessment**: [To be filled after sprint]

### Documentation and Closure

- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation

**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.
