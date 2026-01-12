# Sprint 18: 2×2 Model Matrix Implementation (Logistic Regression vs CatBoost, Platt vs Isotonic)

**Date**: Sun Jan 11 18:05:32 PST 2026  
**Sprint Duration**: 3-4 days (28-32 hours total)  
**Sprint Goal**: Implement and train all 4 models in the 2×2 matrix (Logistic Regression vs CatBoost, Platt vs Isotonic calibration) and evaluate their performance on the 2024 test season  
**Current Status**: Only 1 of 4 models exists (Logistic Regression + Platt). Missing: Logistic Regression + Isotonic, CatBoost + Platt, CatBoost + Isotonic  
**Target Status**: All 4 models trained, evaluated, and compared with side-by-side metrics and calibration plots  
**Team Size**: 1 developer  
**Sprint Lead**: Development Team  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline
- **Test Results**: TBD (to be measured before sprint start)
- **QC Results**: TBD (to be measured before sprint start)
- **Code Coverage**: TBD (to be measured before sprint start)
- **Build Status**: TBD (to be measured before sprint start)

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

## Sprint Overview

### Business Context
- **Business Driver**: Friend requested 2×2 model comparison matrix to determine best model type (Logistic Regression vs CatBoost) and best calibration method (Platt vs Isotonic) for win probability prediction
- **Success Criteria**: 
  - All 4 models trained on same data splits (2017-2023 train, 2023 calibrate, 2024 test)
  - All 4 models evaluated with same metrics (ECE, Brier, AUC, Log Loss)
  - Side-by-side comparison visualization created
  - Clear recommendation on best model/calibration combination
- **Stakeholders**: Data science team, trading simulation users
- **Timeline Constraints**: None (research sprint)

### Technical Context
- **Current System State**: 
  - Logistic Regression training exists: `scripts/model/train_winprob_logreg.py`
  - Platt calibration exists: `scripts/lib/_winprob_lib.py` → `PlattCalibrator`, `fit_platt_calibrator_on_probs()`
  - Evaluation script exists: `scripts/model/evaluate_winprob_model.py`
  - One trained model: `artifacts/winprob_logreg_2017-2023_calib_2023.json` (Logistic Regression + Platt)
- **Target System State**: 
  - Isotonic calibration implemented in `_winprob_lib.py`
  - CatBoost training script created: `scripts/model/train_winprob_catboost.py`
  - All 4 models trained and saved as artifacts
  - All 4 models evaluated on 2024 season
  - Comparison report generated
- **Architecture Impact**: Adds new ML library dependency (catboost), extends calibration support
- **Integration Points**: Evaluation script, artifact loading/saving, frontend visualization

### Sprint Scope
- **In Scope**: 
  - Implement Isotonic calibration
  - Implement CatBoost training script
  - Train all 4 models
  - Evaluate all 4 models
  - Create comparison visualization
- **Out of Scope**: 
  - Hyperparameter tuning for CatBoost (use defaults)
  - Feature engineering changes (use same features as Logistic Regression)
  - Production deployment (research sprint only)
- **Assumptions**: 
  - scikit-learn available for IsotonicRegression
  - catboost package can be installed
  - Same data splits work for all models
- **Constraints**: 
  - Must use same training/calibration/test splits for fair comparison
  - Must maintain backward compatibility with existing artifacts

## Sprint Phases

### Phase 1: Implement Isotonic Calibration (Duration: 4-6 hours)
**Objective**: Add Isotonic calibration support to `_winprob_lib.py` and update artifact format
**Dependencies**: scikit-learn package (check if available, install if needed)
**Deliverables**: 
- `IsotonicCalibrator` class in `_winprob_lib.py`
- `fit_isotonic_calibrator_on_probs()` function
- Updated `WinProbArtifact` to support both `platt` and `isotonic` fields
- Updated `save_artifact()` and `load_artifact()` to handle isotonic
- Updated `predict_proba()` to apply isotonic if present

### Phase 2: Implement CatBoost Training (Duration: 8-12 hours)
**Objective**: Create CatBoost training script similar to Logistic Regression training
**Dependencies**: catboost package (install if needed), Phase 1 complete
**Deliverables**: 
- `scripts/model/train_winprob_catboost.py` script
- Support for both Platt and Isotonic calibration
- CatBoost artifact format compatible with evaluation script
- Training script tests successfully

### Phase 3: Train and Evaluate All 4 Models (Duration: 4-6 hours)
**Objective**: Train all 4 models and evaluate on 2024 season
**Dependencies**: Phase 1 and Phase 2 complete
**Deliverables**: 
- 4 trained model artifacts:
  - `artifacts/winprob_logreg_2017-2023_platt.json` (already exists, verify)
  - `artifacts/winprob_logreg_2017-2023_isotonic.json` (new)
  - `artifacts/winprob_catboost_2017-2023_platt.json` (new)
  - `artifacts/winprob_catboost_2017-2023_isotonic.json` (new)
- 4 evaluation reports in `data/models/evaluations/`
- 4 calibration plots (SVG files)

### Phase 4: Comparison and Documentation (Duration: 3-4 hours)
**Objective**: Create comparison visualization and document findings
**Dependencies**: Phase 3 complete
**Deliverables**: 
- Comparison script showing all 4 models side-by-side
- Comparison visualization (metrics table, calibration plots)
- Documentation of findings and recommendations

## Sprint Backlog

### Epic 1: Isotonic Calibration Implementation
**Priority**: Critical (blocks other work)
**Estimated Time**: 4-6 hours
**Dependencies**: None (foundation work)
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Add IsotonicCalibrator Class
- **ID**: S18-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: `scripts/lib/_winprob_lib.py`
- **Files to Create**: None
- **Dependencies**: scikit-learn (IsotonicRegression)

- **Acceptance Criteria**:
  - [ ] `IsotonicCalibrator` dataclass exists in `_winprob_lib.py`
  - [ ] `IsotonicCalibrator` has `apply(p: np.ndarray) -> np.ndarray` method
  - [ ] `fit_isotonic_calibrator_on_probs(p_base, y)` function exists
  - [ ] Function returns `IsotonicCalibrator` instance or `None` if insufficient data
  - [ ] Unit test passes: `fit_isotonic_calibrator_on_probs()` with sample data returns valid calibrator

- **Technical Context**:
  - **Current State**: Only `PlattCalibrator` exists
  - **Required Changes**: Add `IsotonicCalibrator` class using `sklearn.isotonic.IsotonicRegression`
  - **Integration Points**: Must integrate with `WinProbArtifact` and `predict_proba()`
  - **Data Structures**: 
    ```python
    @dataclass(frozen=True)
    class IsotonicCalibrator:
        iso_reg: Any  # sklearn.isotonic.IsotonicRegression instance
        def apply(self, p: np.ndarray) -> np.ndarray: ...
    ```

- **Implementation Steps**:
  1. Add import: `from sklearn.isotonic import IsotonicRegression`
  2. Create `IsotonicCalibrator` dataclass
  3. Implement `fit_isotonic_calibrator_on_probs()` function
  4. Test with sample data

- **Validation Steps**:
  ```bash
  # Test isotonic calibration
  ./.venv/bin/python3 -c "
  from scripts.lib._winprob_lib import fit_isotonic_calibrator_on_probs
  import numpy as np
  p = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
  y = np.array([0, 0, 1, 1, 1])
  cal = fit_isotonic_calibrator_on_probs(p_base=p, y=y)
  assert cal is not None
  result = cal.apply(p)
  assert len(result) == len(p)
  print('Isotonic calibration test passed')
  "
  ```

- **Definition of Done**: IsotonicCalibrator class exists and can be instantiated and used
- **Rollback Plan**: Revert changes to `_winprob_lib.py` if issues arise
- **Risk Assessment**: Low risk - isolated feature addition
- **Success Metrics**: Function exists and passes unit test

### Story 1.2: Update WinProbArtifact to Support Isotonic
- **ID**: S18-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2 hours
- **Phase**: Phase 1
- **Prerequisites**: S18-E1-S1
- **Files to Modify**: `scripts/lib/_winprob_lib.py`
- **Files to Create**: None
- **Dependencies**: Story 1.1 complete

- **Acceptance Criteria**:
  - [ ] `WinProbArtifact` supports both `platt` and `isotonic` fields (mutually exclusive)
  - [ ] `save_artifact()` serializes isotonic calibrator to JSON
  - [ ] `load_artifact()` deserializes isotonic calibrator from JSON
  - [ ] `predict_proba()` applies isotonic if `artifact.isotonic` is not None
  - [ ] Backward compatibility: existing artifacts with only `platt` still load correctly
  - [ ] Test: Save and load artifact with isotonic calibration

- **Technical Context**:
  - **Current State**: `WinProbArtifact` only has `platt` field
  - **Required Changes**: 
    - Add `isotonic: IsotonicCalibrator | None` field to `WinProbArtifact`
    - Update `save_artifact()` to serialize isotonic (store breakpoints or use pickle)
    - Update `load_artifact()` to deserialize isotonic
    - Update `predict_proba()` to check `artifact.isotonic` before `artifact.platt`

- **Implementation Steps**:
  1. Add `isotonic` field to `WinProbArtifact` dataclass
  2. Update `save_artifact()` to handle isotonic (serialize IsotonicRegression model)
  3. Update `load_artifact()` to handle isotonic (deserialize IsotonicRegression model)
  4. Update `predict_proba()` to apply isotonic if present
  5. Test save/load roundtrip

- **Validation Steps**:
  ```bash
  # Test artifact save/load with isotonic
  ./.venv/bin/python3 << 'PYEOF'
  from scripts.lib._winprob_lib import (
      WinProbArtifact, IsotonicCalibrator, fit_isotonic_calibrator_on_probs,
      save_artifact, load_artifact, predict_proba
  )
  from pathlib import Path
  import numpy as np
  from sklearn.isotonic import IsotonicRegression
  
  # Create test artifact with isotonic
  iso_reg = IsotonicRegression(out_of_bounds='clip')
  iso_reg.fit([0.1, 0.3, 0.5, 0.7, 0.9], [0, 0, 1, 1, 1])
  isotonic = IsotonicCalibrator(iso_reg)
  
  # Create minimal artifact (simplified for test)
  # ... test save/load ...
  print('Isotonic artifact save/load test passed')
  PYEOF
  ```

- **Definition of Done**: Artifacts can be saved and loaded with isotonic calibration
- **Rollback Plan**: Revert changes if backward compatibility breaks
- **Risk Assessment**: Medium risk - artifact format changes could break existing code
- **Success Metrics**: Save/load roundtrip test passes, backward compatibility maintained

### Story 1.3: Update Training Script to Support Isotonic
- **ID**: S18-E1-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: S18-E1-S1, S18-E1-S2
- **Files to Modify**: `scripts/model/train_winprob_logreg.py`
- **Files to Create**: None
- **Dependencies**: Stories 1.1 and 1.2 complete

- **Acceptance Criteria**:
  - [ ] `train_winprob_logreg.py` accepts `--calibration-method` argument (platt/isotonic)
  - [ ] Training script uses isotonic when `--calibration-method isotonic` is specified
  - [ ] Artifact saved with isotonic calibration when isotonic is used
  - [ ] Test: Train model with `--calibration-method isotonic` produces valid artifact

- **Technical Context**:
  - **Current State**: Training script only supports Platt calibration
  - **Required Changes**: 
    - Add `--calibration-method` argument (default: 'platt' for backward compatibility)
    - Conditionally use `fit_isotonic_calibrator_on_probs()` or `fit_platt_calibrator_on_probs()`
    - Set appropriate field in artifact (`platt` or `isotonic`)

- **Implementation Steps**:
  1. Add `--calibration-method` argument to `parse_args()`
  2. Update calibration logic to choose between Platt and Isotonic
  3. Set artifact field based on calibration method
  4. Test training with both methods

- **Validation Steps**:
  ```bash
  # Train with isotonic calibration
  ./.venv/bin/python scripts/model/train_winprob_logreg.py \
    --out-artifact artifacts/winprob_logreg_2017-2023_isotonic_test.json \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --calibration-method isotonic \
    --dsn "$DATABASE_URL"
  
  # Verify artifact has isotonic field
  ./.venv/bin/python3 -c "
  from scripts.lib._winprob_lib import load_artifact
  from pathlib import Path
  art = load_artifact(Path('artifacts/winprob_logreg_2017-2023_isotonic_test.json'))
  assert art.isotonic is not None, 'Isotonic calibrator missing'
  assert art.platt is None, 'Platt should not be present'
  print('Isotonic training test passed')
  "
  ```

- **Definition of Done**: Training script can produce artifacts with isotonic calibration
- **Rollback Plan**: Revert argument addition if issues arise
- **Risk Assessment**: Low risk - additive change
- **Success Metrics**: Training script produces valid isotonic-calibrated artifact

### Epic 2: CatBoost Training Implementation
**Priority**: Critical (core sprint goal)
**Estimated Time**: 8-12 hours
**Dependencies**: Epic 1 complete (for calibration support)
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Create CatBoost Training Script
- **ID**: S18-E2-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 6-8 hours
- **Phase**: Phase 2
- **Prerequisites**: S18-E1-S1, S18-E1-S2 (need calibration support)
- **Files to Create**: `scripts/model/train_winprob_catboost.py`
- **Files to Modify**: None (new file)
- **Dependencies**: catboost package, Epic 1 complete

- **Acceptance Criteria**:
  - [ ] `train_winprob_catboost.py` script exists
  - [ ] Script loads same training data as Logistic Regression script
  - [ ] Script trains CatBoostClassifier on training set
  - [ ] Script supports `--calibration-method` argument (platt/isotonic)
  - [ ] Script saves artifact in compatible format
  - [ ] Artifact includes model type identifier (catboost vs logreg)
  - [ ] Test: Script trains model successfully and produces valid artifact
  - [ ] Test: Artifact can be loaded and used for prediction

- **Technical Context**:
  - **Current State**: No CatBoost training script exists
  - **Required Changes**: 
    - Create new training script based on `train_winprob_logreg.py`
    - Replace IRLS with CatBoostClassifier
    - Use same feature engineering and data loading
    - Support both calibration methods
    - Save artifact in format compatible with evaluation script
    - Include model type in artifact metadata

- **Implementation Steps**:
  1. Copy `train_winprob_logreg.py` as starting point
  2. Replace IRLS training with CatBoostClassifier
  3. Update artifact format to store CatBoost model (use CatBoost's save_model/load_model)
  4. Add `--calibration-method` argument
  5. Integrate with calibration functions from Epic 1
  6. Add model type field to artifact metadata
  7. Test training end-to-end

- **Validation Steps**:
  ```bash
  # Install catboost if needed
  ./.venv/bin/pip install catboost
  
  # Train CatBoost model
  ./.venv/bin/python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_2017-2023_platt_test.json \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --calibration-method platt \
    --dsn "$DATABASE_URL"
  
  # Verify artifact loads
  ./.venv/bin/python3 -c "
  from scripts.lib._winprob_lib import load_artifact
  from pathlib import Path
  art = load_artifact(Path('artifacts/winprob_catboost_2017-2023_platt_test.json'))
  assert art.model is not None, 'Model missing'
  # Check model type in metadata if stored
  print('CatBoost training test passed')
  "
  ```

- **Definition of Done**: CatBoost training script exists and produces valid artifacts
- **Rollback Plan**: Delete script if critical issues arise
- **Risk Assessment**: Medium-High risk - new ML library, more complex model
- **Success Metrics**: Script trains model and produces valid artifact that can be loaded and used

### Story 2.2: Add JPEG Generation to Evaluation Script
- **ID**: S18-E2-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: None (can be done in parallel with CatBoost work)
- **Files to Modify**: `scripts/model/evaluate_winprob_model.py`
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Evaluation script generates JPEG versions of SVG plots
  - [ ] Both `.calibration.svg` and `.calibration.jpg` are created
  - [ ] Both `.calibration_context.svg` and `.calibration_context.jpg` are created
  - [ ] JPEG files are valid image files
  - [ ] JPEG quality is reasonable (80-90% recommended)
  - [ ] Test: Evaluate model produces both SVG and JPEG files

- **Technical Context**:
  - **Current State**: Only SVG files are generated
  - **Required Changes**: 
    - Add SVG to JPEG conversion (use `cairosvg` or `PIL` + `svglib`)
    - Generate JPEG alongside SVG in `--plot-calibration` section
    - Handle both calibration.svg and calibration_context.svg

- **Implementation Steps**:
  1. Add dependency: `cairosvg` or `Pillow` + `svglib` (check what's available)
  2. Create helper function `_convert_svg_to_jpeg(svg_path: Path, jpeg_path: Path)`
  3. Call conversion function after each SVG is written
  4. Test with existing evaluation

- **Validation Steps**:
  ```bash
  # Evaluate model and verify both SVG and JPEG exist
  ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
    --artifact artifacts/winprob_logreg_2017-2023_calib_2023.json \
    --season-start 2024 \
    --out data/models/evaluations/test_eval.json \
    --plot-calibration \
    --dsn "$DATABASE_URL"
  
  # Verify all plot files exist
  test -f data/models/evaluations/test_eval.calibration.svg && echo "✓ SVG exists"
  test -f data/models/evaluations/test_eval.calibration.jpg && echo "✓ JPEG exists"
  test -f data/models/evaluations/test_eval.calibration_context.svg && echo "✓ Context SVG exists"
  test -f data/models/evaluations/test_eval.calibration_context.jpg && echo "✓ Context JPEG exists"
  
  # Verify JPEG is valid
  file data/models/evaluations/test_eval.calibration.jpg | grep -q "JPEG" && echo "✓ JPEG is valid"
  ```

- **Definition of Done**: Evaluation script generates both SVG and JPEG files
- **Rollback Plan**: Remove JPEG generation if conversion library issues arise
- **Risk Assessment**: Low-Medium risk - new dependency, but conversion is straightforward
- **Success Metrics**: Both SVG and JPEG files generated for each evaluation

### Story 2.3: Update Evaluation Script for CatBoost and Isotonic
- **ID**: S18-E2-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 2
- **Prerequisites**: S18-E2-S1, S18-E1-S2
- **Files to Modify**: `scripts/model/evaluate_winprob_model.py`, `scripts/lib/_winprob_lib.py`
- **Files to Create**: None
- **Dependencies**: Stories 2.1 and 1.2 complete

- **Acceptance Criteria**:
  - [ ] Evaluation script can load CatBoost artifacts
  - [ ] `predict_proba()` works with CatBoost artifacts
  - [ ] `predict_proba()` works with Isotonic calibration
  - [ ] Evaluation produces same metrics format for all model types
  - [ ] Context SVG summary includes isotonic info when present
  - [ ] Test: Evaluate CatBoost model produces valid report
  - [ ] Test: Evaluate Logistic Regression with Isotonic produces valid report

- **Technical Context**:
  - **Current State**: Evaluation script assumes Logistic Regression artifacts
  - **Required Changes**: 
    - Update `predict_proba()` to handle CatBoost models
    - May need to update artifact loading to deserialize CatBoost model
    - Ensure evaluation works for both model types

- **Implementation Steps**:
  1. Update `predict_proba()` to detect model type and use appropriate prediction method
  2. Update artifact loading if needed for CatBoost model deserialization
  3. Test evaluation with CatBoost artifact

- **Validation Steps**:
  ```bash
  # Evaluate CatBoost model
  ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
    --artifact artifacts/winprob_catboost_2017-2023_platt_test.json \
    --season-start 2024 \
    --out data/models/evaluations/winprob_catboost_2017-2023_platt_test_on_2024.json \
    --plot-calibration \
    --dsn "$DATABASE_URL"
  
  # Verify report exists and has metrics
  ./.venv/bin/python3 -c "
  import json
  with open('data/models/evaluations/winprob_catboost_2017-2023_platt_test_on_2024.json') as f:
    report = json.load(f)
  assert 'eval' in report
  assert 'overall' in report['eval']
  assert 'ece_binned' in report['eval']['overall']
  print('CatBoost evaluation test passed')
  "
  ```

- **Definition of Done**: Evaluation script works with CatBoost artifacts
- **Rollback Plan**: Revert changes if evaluation breaks
- **Risk Assessment**: Medium risk - evaluation script changes
- **Success Metrics**: CatBoost model evaluates successfully

### Epic 3: Train and Evaluate All 4 Models
**Priority**: High (sprint goal)
**Estimated Time**: 4-6 hours
**Dependencies**: Epic 1 and Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Train All 4 Models
- **ID**: S18-E3-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours (mostly waiting for training to complete)
- **Phase**: Phase 3
- **Prerequisites**: S18-E1-S3, S18-E2-S1, S18-E2-S2
- **Files to Create**: 4 model artifacts
- **Files to Modify**: None
- **Dependencies**: All previous stories complete

- **Acceptance Criteria**:
  - [ ] All 4 model artifacts exist:
    - `artifacts/winprob_logreg_2017-2023_platt.json` (verify or retrain)
    - `artifacts/winprob_logreg_2017-2023_isotonic.json` (new)
    - `artifacts/winprob_catboost_2017-2023_platt.json` (new)
    - `artifacts/winprob_catboost_2017-2023_isotonic.json` (new)
  - [ ] All artifacts use same data splits (2017-2023 train, 2023 calibrate, 2024 test)
  - [ ] All artifacts can be loaded successfully
  - [ ] All artifacts have appropriate calibration (platt or isotonic)

- **Technical Context**:
  - **Current State**: Only Logistic Regression + Platt exists
  - **Required Changes**: Train 3 new models using same data splits

- **Implementation Steps**:
  1. Verify existing Logistic Regression + Platt model
  2. Train Logistic Regression + Isotonic
  3. Train CatBoost + Platt
  4. Train CatBoost + Isotonic
  5. Verify all artifacts load correctly

- **Validation Steps**:
  ```bash
  # Train all 4 models
  # 1. Logistic Regression + Isotonic
  ./.venv/bin/python scripts/model/train_winprob_logreg.py \
    --out-artifact artifacts/winprob_logreg_2017-2023_isotonic.json \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --calibration-method isotonic \
    --dsn "$DATABASE_URL"
  
  # 2. CatBoost + Platt
  ./.venv/bin/python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_2017-2023_platt.json \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --calibration-method platt \
    --dsn "$DATABASE_URL"
  
  # 3. CatBoost + Isotonic
  ./.venv/bin/python scripts/model/train_winprob_catboost.py \
    --out-artifact artifacts/winprob_catboost_2017-2023_isotonic.json \
    --train-season-start-max 2023 \
    --calib-season-start 2023 \
    --test-season-start 2024 \
    --calibration-method isotonic \
    --dsn "$DATABASE_URL"
  
  # Verify all artifacts exist and load
  for artifact in artifacts/winprob_*_2017-2023_*.json; do
    ./.venv/bin/python3 -c "
    from scripts.lib._winprob_lib import load_artifact
    from pathlib import Path
    art = load_artifact(Path('$artifact'))
    print(f'✓ {artifact} loaded successfully')
    "
  done
  ```

- **Definition of Done**: All 4 model artifacts exist and are valid
- **Rollback Plan**: Delete invalid artifacts and retrain
- **Risk Assessment**: Low risk - training is straightforward once scripts work
- **Success Metrics**: All 4 artifacts exist and load successfully

### Story 3.2: Evaluate All 4 Models
- **ID**: S18-E3-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1-2 hours (mostly waiting for evaluation to complete)
- **Phase**: Phase 3
- **Prerequisites**: S18-E3-S1
- **Files to Create**: 4 evaluation reports + 16 plot files (8 SVG + 8 JPEG)
- **Files to Modify**: None
- **Dependencies**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] All 4 models evaluated on 2024 season
  - [ ] 4 evaluation JSON reports in `data/models/evaluations/`
  - [ ] 8 calibration SVG plots (2 per model: calibration.svg and calibration_context.svg)
  - [ ] 8 calibration JPEG plots (2 per model: calibration.jpg and calibration_context.jpg)
  - [ ] All reports have same metric structure (ECE, Brier, AUC, Log Loss)
  - [ ] All reports can be loaded and parsed
  - [ ] All SVG and JPEG files exist and are valid

- **Technical Context**:
  - **Current State**: Only 2 evaluations exist (Platt and no-Platt, both Logistic Regression)
  - **Required Changes**: Evaluate 4 models (2 new model types × 2 calibration methods)

- **Implementation Steps**:
  1. Evaluate Logistic Regression + Isotonic
  2. Evaluate CatBoost + Platt
  3. Evaluate CatBoost + Isotonic
  4. Verify all reports exist and are valid

- **Validation Steps**:
  ```bash
  # Evaluate all 4 models
  for artifact in artifacts/winprob_*_2017-2023_*.json; do
    name=$(basename $artifact .json)
    ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
      --artifact "$artifact" \
      --season-start 2024 \
      --out "data/models/evaluations/${name}_on_2024.json" \
      --plot-calibration \
      --dsn "$DATABASE_URL"
  done
  
  # Verify all reports exist
  ls -la data/models/evaluations/*_on_2024.json
  ls -la data/models/evaluations/*.svg
  
  # Verify reports are valid JSON
  for report in data/models/evaluations/*_on_2024.json; do
    ./.venv/bin/python3 -c "
    import json
    with open('$report') as f:
      data = json.load(f)
    assert 'eval' in data
    assert 'overall' in data['eval']
    print(f'✓ $report is valid')
    "
  done
  ```

- **Definition of Done**: All 4 models evaluated with reports and plots
- **Rollback Plan**: Re-evaluate if reports are invalid
- **Risk Assessment**: Low risk - evaluation script should work for all models
- **Success Metrics**: All 4 evaluation reports exist and are valid

### Epic 4: Frontend Integration and Comparison
**Priority**: High (sprint completion)
**Estimated Time**: 8-12 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Create Comparison Script
- **ID**: S18-E4-S1
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 2 hours
- **Phase**: Phase 4
- **Prerequisites**: S18-E3-S2
- **Files to Create**: `scripts/utils/compare_models.py` (or similar)
- **Files to Modify**: None
- **Dependencies**: Story 3.2 complete

- **Acceptance Criteria**:
  - [ ] Comparison script exists
  - [ ] Script loads all 4 evaluation reports
  - [ ] Script generates side-by-side metrics comparison
  - [ ] Script outputs comparison table (ECE, Brier, AUC, Log Loss)
  - [ ] Script identifies best model for each metric
  - [ ] Test: Script runs and produces comparison output

- **Technical Context**:
  - **Current State**: No comparison tool exists
  - **Required Changes**: Create script to load and compare evaluation reports

- **Implementation Steps**:
  1. Create comparison script
  2. Load all 4 evaluation reports
  3. Extract metrics (ECE, Brier, AUC, Log Loss)
  4. Generate comparison table
  5. Identify best model for each metric
  6. Output results (console and/or JSON)

- **Validation Steps**:
  ```bash
  # Run comparison script
  ./.venv/bin/python scripts/utils/compare_models.py \
    --reports-dir data/models/evaluations \
    --out data/models/evaluations/model_comparison.json
  
  # Verify comparison output
  ./.venv/bin/python3 -c "
  import json
  with open('data/models/evaluations/model_comparison.json') as f:
    comparison = json.load(f)
  assert 'models' in comparison
  assert len(comparison['models']) == 4
  print('Comparison script test passed')
  "
  ```

- **Definition of Done**: Comparison script exists and produces comparison output
- **Rollback Plan**: Delete script if issues arise
- **Risk Assessment**: Low risk - simple data aggregation
- **Success Metrics**: Comparison script produces valid comparison output

### Story 4.2: Update Model Evaluation Endpoint for All 4 Models
- **ID**: S18-E4-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 4
- **Prerequisites**: S18-E3-S2 (all models evaluated)
- **Files to Modify**: `webapp/api/endpoints/model_evaluation.py`
- **Files to Create**: None
- **Dependencies**: Story 3.2 complete

- **Acceptance Criteria**:
  - [ ] Endpoint can find and serve all 4 model types (logreg/catboost × platt/isotonic)
  - [ ] Endpoint returns all 4 models when `all_seasons=true` or no filter
  - [ ] Endpoint can filter by model type (`logreg`/`catboost`) and calibration (`platt`/`isotonic`/`no_platt`)
  - [ ] Model labels correctly identify all 4 model types:
    - "Logistic Regression + Platt (Training: 2017-2023)"
    - "Logistic Regression + Isotonic (Training: 2017-2023)"
    - "CatBoost + Platt (Training: 2017-2023)"
    - "CatBoost + Isotonic (Training: 2017-2023)"
  - [ ] Endpoint returns structured response with all 4 models when available
  - [ ] Test: API returns all 4 models with correct labels
  - [ ] Test: API filters correctly by model type and calibration method

- **Technical Context**:
  - **Current State**: Endpoint only distinguishes `platt` vs `no_platt`
  - **Required Changes**: 
    - Update `get_model_type_from_filename()` to detect logreg/catboost and platt/isotonic
    - Update `get_model_label()` to generate correct labels for all 4 models
    - Add model type detection (logreg vs catboost)
    - Add calibration method detection (platt vs isotonic)
    - Return all 4 models in structured format

- **Implementation Steps**:
  1. Update `get_model_type_from_filename()` to detect:
     - Model type: "logreg" (if "logreg" in filename) or "catboost" (if "catboost" in filename)
     - Calibration: "platt" (if "calib" or "platt" in filename), "isotonic" (if "isotonic" in filename), "no_platt" (if "no_platt" in filename)
  2. Update `get_model_label()` to generate labels for all 4 combinations:
     - "Logistic Regression + Platt (Training: {train_data})"
     - "Logistic Regression + Isotonic (Training: {train_data})"
     - "CatBoost + Platt (Training: {train_data})"
     - "CatBoost + Isotonic (Training: {train_data})"
  3. Update aggregation logic to group by both model type and calibration (4 groups)
  4. Update single-season logic to find correct model based on filters
  5. Return structured response: `{"models": {"logreg_platt": {...}, "logreg_isotonic": {...}, "catboost_platt": {...}, "catboost_isotonic": {...}}}`
  6. Test with all 4 evaluation reports

- **Validation Steps**:
  ```bash
  # Test endpoint with all models
  curl "http://localhost:8000/api/stats/model-evaluation?all_seasons=true" | jq '.models'
  
  # Test filtering by model type
  curl "http://localhost:8000/api/stats/model-evaluation?season_start=2024&model_type=logreg" | jq '.model_label'
  curl "http://localhost:8000/api/stats/model-evaluation?season_start=2024&model_type=catboost" | jq '.model_label'
  
  # Verify all 4 models are returned
  curl "http://localhost:8000/api/stats/model-evaluation?all_seasons=true" | jq '.model_types | length' # Should be 4
  ```

- **Definition of Done**: Endpoint correctly identifies and serves all 4 model types
- **Rollback Plan**: Revert changes if endpoint breaks
- **Risk Assessment**: Medium risk - endpoint changes affect frontend
- **Success Metrics**: All 4 models returned with correct labels

### Story 4.3: Add Plot File Serving to Endpoint
- **ID**: S18-E4-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: S18-E2-S2, S18-E4-S2
- **Files to Modify**: `webapp/api/endpoints/model_evaluation.py`
- **Files to Create**: None
- **Dependencies**: Stories 2.2 and 4.2 complete

- **Acceptance Criteria**:
  - [ ] New endpoint `/api/stats/model-evaluation/plot` serves SVG/JPEG files
  - [ ] Endpoint accepts `report_name` and `plot_type` (calibration/calibration_context) and `format` (svg/jpg)
  - [ ] Endpoint returns appropriate Content-Type headers
  - [ ] Endpoint handles missing files gracefully (404)
  - [ ] Test: Can fetch SVG and JPEG files via API

- **Technical Context**:
  - **Current State**: Plot files exist but not served via API
  - **Required Changes**: 
    - Add new endpoint for serving plot files
    - Return file contents with correct Content-Type
    - Handle file not found errors

- **Implementation Steps**:
  1. Add new endpoint `/api/stats/model-evaluation/plot`
  2. Accept parameters: `report_name`, `plot_type`, `format`
  3. Construct file path from parameters
  4. Return file with correct Content-Type (image/svg+xml or image/jpeg)
  5. Handle 404 for missing files

- **Validation Steps**:
  ```bash
  # Test SVG serving
  curl "http://localhost:8000/api/stats/model-evaluation/plot?report_name=winprob_eval_2017-2023_calib_2023_on_2024&plot_type=calibration&format=svg" \
    -o test_calibration.svg
  
  # Test JPEG serving
  curl "http://localhost:8000/api/stats/model-evaluation/plot?report_name=winprob_eval_2017-2023_calib_2023_on_2024&plot_type=calibration&format=jpg" \
    -o test_calibration.jpg
  
  # Verify files are valid
  file test_calibration.svg | grep -q "SVG" && echo "✓ SVG valid"
  file test_calibration.jpg | grep -q "JPEG" && echo "✓ JPEG valid"
  ```

- **Definition of Done**: Plot files can be served via API endpoint
- **Rollback Plan**: Remove endpoint if issues arise
- **Risk Assessment**: Low risk - simple file serving
- **Success Metrics**: SVG and JPEG files served correctly via API

### Story 4.4: Update Frontend to Display All 4 Models
- **ID**: S18-E4-S4
- **Type**: Feature
- **Priority**: High
- **Estimate**: 4-6 hours
- **Phase**: Phase 4
- **Prerequisites**: S18-E4-S2, S18-E4-S3
- **Files to Modify**: `webapp/static/js/stats.js`, `webapp/static/templates/aggregate-stats.html`
- **Files to Create**: None
- **Dependencies**: Stories 4.2 and 4.3 complete

- **Acceptance Criteria**:
  - [ ] Frontend fetches all 4 models from API (logreg+platt, logreg+isotonic, catboost+platt, catboost+isotonic)
  - [ ] Frontend displays 4 separate Chart.js charts (one per model)
  - [ ] Each chart is labeled correctly with full model description:
    - "Logistic Regression + Platt (Training: 2017-2023)"
    - "Logistic Regression + Isotonic (Training: 2017-2023)"
    - "CatBoost + Platt (Training: 2017-2023)"
    - "CatBoost + Isotonic (Training: 2017-2023)"
  - [ ] Charts use distinct colors to distinguish models (4 different colors)
  - [ ] Frontend optionally displays SVG/JPEG plots (embed or link to plot endpoint)
  - [ ] All 4 charts render correctly on stats page
  - [ ] Test: All 4 charts render on stats page with correct labels

- **Technical Context**:
  - **Current State**: Frontend only displays 2 charts (Platt and non-Platt, both Logistic Regression)
  - **Required Changes**: 
    - Update API calls to fetch all 4 models
    - Update HTML to have 4 chart containers
    - Update rendering to display all 4 charts
    - Update labels to show model type and calibration method

- **Implementation Steps**:
  1. Update `loadAggregateStats()` to fetch all 4 models separately:
     - `getModelEvaluation(2024, false, 'logreg_platt')`
     - `getModelEvaluation(2024, false, 'logreg_isotonic')`
     - `getModelEvaluation(2024, false, 'catboost_platt')`
     - `getModelEvaluation(2024, false, 'catboost_isotonic')`
  2. Update HTML template to have 4 chart containers with descriptive IDs
  3. Update `renderAggregateStats()` to render all 4 charts with proper labels
  4. Use distinct colors for each model:
     - Logistic Regression + Platt: Purple (#7c3aed)
     - Logistic Regression + Isotonic: Blue (#3b82f6)
     - CatBoost + Platt: Orange (#f7931a)
     - CatBoost + Isotonic: Green (#10b981)
  5. Update chart labels to show full model description from API
  6. Optionally add links to SVG/JPEG plots for each model

- **Validation Steps**:
  ```bash
  # Start webapp and verify all 4 charts appear
  # Open browser to stats page
  # Verify 4 calibration charts are displayed
  # Verify each chart has correct label
  ```

- **Definition of Done**: All 4 model charts displayed on frontend
- **Rollback Plan**: Revert frontend changes if issues arise
- **Risk Assessment**: Medium risk - frontend changes
- **Success Metrics**: All 4 charts render correctly with proper labels

### Story 4.5: Create Comparison Visualization
- **ID**: S18-E4-S5
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: S18-E4-S1
- **Files to Create**: Comparison visualization script and output
- **Files to Modify**: None
- **Dependencies**: Story 4.1 complete

- **Acceptance Criteria**:
  - [ ] Comparison visualization exists
  - [ ] Shows all 4 models side-by-side
  - [ ] Includes metrics table
  - [ ] Includes calibration plots (all 4 on same chart or side-by-side)
  - [ ] Identifies best model overall
  - [ ] Test: Visualization renders correctly

- **Technical Context**:
  - **Current State**: Individual calibration plots exist
  - **Required Changes**: Create combined visualization showing all 4 models

- **Implementation Steps**:
  1. Load all 4 evaluation reports
  2. Extract calibration points from each
  3. Create combined calibration plot (4 series on one chart)
  4. Create metrics comparison table
  5. Generate visualization (SVG, HTML, or markdown)

- **Validation Steps**:
  ```bash
  # Generate comparison visualization
  ./.venv/bin/python scripts/utils/visualize_model_comparison.py \
    --reports-dir data/models/evaluations \
    --out data/models/evaluations/model_comparison.html
  
  # Verify visualization file exists
  test -f data/models/evaluations/model_comparison.html && echo "Visualization created" || echo "Visualization missing"
  ```

- **Definition of Done**: Comparison visualization exists and shows all 4 models
- **Rollback Plan**: Delete visualization if issues arise
- **Risk Assessment**: Low risk - visualization only
- **Success Metrics**: Comparison visualization exists and renders correctly

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: S18-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] Update `cursor-files/docs/train_model_quick_guide.md` with new models
  - [ ] Document CatBoost training commands
  - [ ] Document isotonic calibration option
  - [ ] Update model comparison documentation
  - [ ] All documentation reflects new 2×2 matrix

- **Technical Context**:
  - **Current State**: Documentation only covers Logistic Regression + Platt
  - **Required Changes**: Add documentation for all 4 models

- **Implementation Steps**: Update relevant documentation files
- **Validation Steps**: Review documentation for completeness

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: S18-QG-VALIDATION
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
  - **Current State**: TBD (to be measured)
  - **Required Changes**: Fix any quality issues

- **Implementation Steps**: Run quality checks and fix any issues
- **Validation Steps**: Verify all quality gates pass

### Story [FINAL]: Sprint Completion and Archive
- **ID**: S18-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created
  - [ ] All deliverables documented
  - [ ] Sprint files organized
  - [ ] Sprint marked as completed

- **Technical Context**: Create completion report summarizing all work
- **Implementation Steps**: Create report, organize files, archive sprint
- **Validation Steps**: Verify archive and report completion

## Technical Decisions

### Design Pattern: Strategy Pattern for Calibration
- **Category**: Behavioral
- **Intent**: Allow interchangeable calibration methods (Platt vs Isotonic)
- **Implementation**: `PlattCalibrator` and `IsotonicCalibrator` both implement `apply(p)` method
- **Benefits**: Easy to add new calibration methods, clean separation of concerns
- **Trade-offs**: Slight complexity increase in artifact format
- **Rationale**: Supports multiple calibration methods without code duplication

### Algorithm: Isotonic Regression
- **Type**: Non-parametric regression
- **Complexity**: Time O(n log n) for fitting, O(n) for prediction
- **Description**: Piecewise linear monotonic function fitted to calibration data
- **Use Case**: More flexible calibration than Platt when base model is poorly calibrated
- **Performance**: Better calibration than Platt in many cases, but more parameters

### Design Decision: CatBoost Artifact Format
- **Problem**: CatBoost models are complex objects that need serialization
- **Context**: Must be compatible with existing artifact loading/saving infrastructure
- **Options**: 
  1. Pickle CatBoost model (simple, but less portable)
  2. Save CatBoost model separately, reference in artifact (more complex)
  3. Use CatBoost's built-in save/load (best practice)
- **Selected**: Option 3 - Use CatBoost's `save_model()` and `load_model()` methods, store path in artifact JSON

## Testing Strategy

### Testing Approach
- **Unit Tests**: Test calibration functions with sample data
- **Integration Tests**: Test full training → evaluation pipeline for each model type
- **E2E Tests**: Train all 4 models and verify they produce valid artifacts and evaluations
- **Performance Tests**: Compare training and evaluation times across model types

## Deployment Plan
- **Pre-Deployment**: N/A (research sprint, no production deployment)
- **Deployment Steps**: N/A
- **Post-Deployment**: N/A
- **Rollback Plan**: N/A

## Risk Assessment

### Technical Risks
- **Risk 1**: CatBoost dependency issues
  - **Probability**: Medium
  - **Impact**: High
  - **Mitigation**: Test installation early, use virtual environment
  - **Contingency**: Use alternative gradient boosting library if needed

- **Risk 2**: Isotonic calibration serialization complexity
  - **Probability**: Medium
  - **Impact**: Medium
  - **Mitigation**: Use scikit-learn's built-in serialization or pickle
  - **Contingency**: Store calibration parameters instead of full model

- **Risk 3**: CatBoost training time too long
  - **Probability**: Low
  - **Impact**: Medium
  - **Mitigation**: Use reasonable hyperparameters, early stopping
  - **Contingency**: Reduce training iterations if needed

### Business Risks
- **Risk 1**: No clear winner among 4 models
  - **Probability**: Medium
  - **Impact**: Low
  - **Mitigation**: Document findings, recommend based on use case
  - **Contingency**: All models can be kept for different use cases

### Resource Risks
- **Risk 1**: Training time exceeds sprint duration
  - **Probability**: Low
  - **Impact**: Medium
  - **Mitigation**: Start training early, use parallel execution if possible
  - **Contingency**: Extend sprint if needed

## Success Metrics

### Technical Metrics
- **Model Coverage**: 4/4 models trained (100%)
- **Evaluation Coverage**: 4/4 models evaluated (100%)
- **Plot Generation**: 16/16 plot files generated (8 SVG + 8 JPEG, 100%)
- **Endpoint Coverage**: All 4 models served via API (100%)
- **Frontend Coverage**: All 4 charts displayed on stats page (100%)
- **Code Quality**: Maintain or improve linting/test coverage
- **Artifact Validity**: 100% of artifacts load successfully

### Business Metrics
- **Comparison Completeness**: All 4 models compared side-by-side
- **Recommendation Clarity**: Clear recommendation on best model/calibration combination
- **Documentation Quality**: All new features documented

### Sprint Metrics
- **Velocity**: Complete all planned stories
- **Quality Gates**: 100% pass rate
- **Deliverables**: All artifacts, evaluations, and comparison materials created

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)
- [ ] All 4 models trained and evaluated
- [ ] Comparison visualization created
- [ ] Sprint completion report created

### Post-Sprint Quality Comparison
- **Test Results**: TBD (to be measured after sprint)
- **Linting Results**: TBD (to be measured after sprint)
- **Code Coverage**: TBD (to be measured after sprint)
- **Build Status**: TBD (to be measured after sprint)
- **Overall Assessment**: TBD (to be measured after sprint)

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

