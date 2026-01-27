# Future Sprints Analysis: Opening Odds Collinearity Fix

**Date**: Sun Jan 25 00:45:16 UTC 2026  
**Status**: Draft  
**Author**: Analysis based on sprint completion review  
**Version**: v1.0  
**Purpose**: Analyze completed sprint work and determine if future sprints are needed for opening odds collinearity improvements

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (code refs, commands + verbatim output, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and exact artifacts analyzed
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: Use PostgreSQL via `DATABASE_URL` for data analysis

---

## Executive Summary

### Key Findings

- **Finding 1**: ✅ **COMPLETED**: Sprint 1 successfully removed redundant `has_opening_moneyline` feature (4 → 3 features). Code changes verified across 6 files. Feature importance analysis confirmed redundancy (0.30% vs 24.15% importance).
- **Finding 2**: ⚠️ **PENDING**: Model retraining not yet completed (requires database access). This is the only remaining work from Sprint 1.
- **Finding 3**: 📊 **EVIDENCE-BASED**: Feature importance data shows `has_opening_spread` (0.36%) and `has_opening_total` (0.07%) also have very low importance compared to `opening_overround` (24.15%), suggesting potential for further reduction.

### Critical Issues Identified

- **Issue 1**: Model retraining pending - Sprint 1 is 80% complete but cannot be finalized without retraining 4 models (2-4 hours work, requires database access).
- **Issue 2**: Remaining binary flags have low importance - `has_opening_spread` (0.36%) and `has_opening_total` (0.07%) may be candidates for removal, but this requires validation via model retraining and performance comparison.

### Recommended Actions

- **Action 1**: **Priority: Critical** - **Complete Sprint 1** - Finish model retraining and evaluation (2-4 hours, requires database access). This is not a new sprint, just completion of existing work.
- **Action 2**: **Priority: Medium** - **Evaluate Single-Feature Alternative** - After Sprint 1 completion, test using only `opening_overround` (remove `has_opening_spread` and `has_opening_total`). Evidence suggests this may improve model simplicity without performance loss.
- **Action 3**: **Priority: Low** - **Monitor Closing Line Data** - Closing/pre-tip odds analysis completed and found insufficient coverage (3.5% vs 94.4%). No action needed unless data collection improves significantly.

### Success Metrics

- **Metric 1**: Sprint 1 completion: 4 models retrained with 3-feature set, performance maintained or improved
- **Metric 2**: Single-feature evaluation: Model performance comparison (3 features vs. 1 feature)
- **Metric 3**: Feature importance validation: Confirm low importance of remaining binary flags after retraining

---

## Problem Statement

### Current Situation

**Sprint 1 Status**: Opening Odds Collinearity Fix sprint is 80% complete:
- ✅ **COMPLETED**: Code changes removing `has_opening_moneyline` from all 6 files
- ✅ **COMPLETED**: Data analysis confirming redundancy (feature importance: 0.30% vs 24.15%)
- ✅ **COMPLETED**: Closing line analysis (found insufficient coverage: 3.5% vs 94.4%)
- ⚠️ **PENDING**: Model retraining (4 v2 odds-enabled models need retraining with 3-feature set)

**Current Feature Set**: 3 opening odds features:
1. `opening_overround` (continuous, 24.15% importance)
2. `has_opening_spread` (binary flag, 0.36% importance)
3. `has_opening_total` (binary flag, 0.07% importance)

**Feature Importance Evidence** (from `epic1_completion_report.md`):
| Feature | Importance | Percentage | Analysis |
|---------|------------|------------|----------|
| `opening_overround` | 24.1495 | 24.15% | **High importance** - primary predictive feature |
| `has_opening_moneyline` | 0.3002 | 0.30% | **Removed** - confirmed redundant |
| `has_opening_spread` | 0.3620 | 0.36% | Low importance |
| `has_opening_total` | 0.0725 | 0.07% | Very low importance |

### Pain Points

- **Sprint 1 Incomplete**: Cannot validate performance impact without model retraining
- **Potential Further Optimization**: Remaining binary flags (`has_opening_spread`, `has_opening_total`) have very low importance (combined 0.43% vs 24.15% for `opening_overround`)
- **Model Complexity**: 3 features may still have collinearity risk if binary flags are correlated with each other or with `opening_overround` NaN patterns

### Business Impact

- **Model Performance**: Cannot assess impact of feature removal without retraining
- **Model Interpretability**: Further reduction to single feature would improve interpretability
- **Maintenance Impact**: Fewer features reduce complexity and maintenance burden

### Success Criteria

- **Criterion 1**: Sprint 1 completed - 4 models retrained, performance validated
- **Criterion 2**: Single-feature alternative evaluated - Performance comparison (3 features vs. 1 feature)
- **Criterion 3**: Feature importance validated - Confirm low importance of binary flags after retraining

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 
  - Sprint 1 completion: None (uses existing updated code)
  - Future single-feature sprint: Same 6 files as Sprint 1 (`_winprob_lib.py`, `train_winprob_catboost.py`, `precompute_model_probabilities.py`, `simulate_trading_strategy.py`, `evaluate_winprob_model.py`, `evaluate_winprob_time_buckets.py`)
- **Estimated Effort**: 
  - Sprint 1 completion: 2-4 hours (model retraining only)
  - Future single-feature sprint: 6-8 hours (code changes + retraining + evaluation)
- **Technical Complexity**: Low-Medium (similar to Sprint 1, removing 2 more features)
- **Risk Level**: Low-Medium (removing low-importance features should not hurt performance, but requires validation)

**Sprint Scope Recommendation**: 
- **Sprint 1 Completion**: Not a new sprint - just finish existing work (2-4 hours)
- **Future Sprint 2**: Single-feature evaluation (if Sprint 1 shows acceptable performance) - Single Sprint (6-8 hours)

**Dependency Analysis**:
- Sprint 1 completion: No dependencies (code ready, just needs database access)
- Future Sprint 2: Must complete Sprint 1 first (need baseline performance with 3 features)

---

## Current State Analysis

### Sprint 1 Completion Status

**Evidence**: `verification_report.md` shows detailed completion status:

**✅ Completed Work**:
- Epic 1: Data Analysis and Verification (3 stories complete)
  - Story 1.1: Correlation analysis (query executed, results documented)
  - Story 1.2: Feature importance extraction (confirmed redundancy: 0.30% vs 24.15%)
  - Story 1.3: Closing line analysis (found insufficient coverage: 3.5% vs 94.4%)
- Epic 2: Code Changes (5 stories complete)
  - Story 2.1: Core library functions updated ✅
  - Story 2.2: Training script updated ✅
  - Story 2.3: Precomputation script updated ✅
  - Story 2.4: Trading strategy script updated ✅
  - Story 2.5: Evaluation scripts updated ✅
- Epic 4: Quality Assurance (partial)
  - Story 4.1: Documentation updated ✅
  - Story 4.2: Quality gates validated ✅

**❌ Pending Work**:
- Epic 3: Model Retraining and Evaluation (3 stories pending)
  - Story 3.1: Retrain 4 v2 odds-enabled models ❌ (requires database access, 2-4 hours)
  - Story 3.2: Evaluate retrained models ❌ (depends on 3.1)
  - Story 3.3: Performance comparison ❌ (depends on 3.1)

**Overall Sprint Status**: 80% complete (code changes done, model retraining pending)

### Feature Importance Evidence

**Source**: `epic1_completion_report.md` (lines 37-82)

**Model Analyzed**: `catboost_odds_platt_v2` (17 features total)

**Opening Odds Feature Importance**:
| Feature | Importance | Percentage | Ratio vs. opening_overround |
|---------|------------|------------|----------------------------|
| `opening_overround` | 24.1495 | 24.15% | 1.0000 (baseline) |
| `has_opening_moneyline` | 0.3002 | 0.30% | 0.0124 (removed) |
| `has_opening_spread` | 0.3620 | 0.36% | 0.0150 (low) |
| `has_opening_total` | 0.0725 | 0.07% | 0.0030 (very low) |

**Key Observations**:
- `opening_overround` dominates importance (24.15% vs combined 0.43% for binary flags)
- `has_opening_spread` and `has_opening_total` have very low importance (0.36% and 0.07%)
- Combined binary flags contribute only 1.8% of `opening_overround`'s importance (0.43% / 24.15% = 0.0178)

### Code State Verification

**Evidence**: `verification_report.md` shows all code changes verified:

**File**: `scripts/lib/_winprob_lib.py`
- ✅ `ODDS_MODEL_FEATURES` constant updated (lines 237-241): Only 3 features
- ✅ `compute_opening_odds_features()` updated: No `has_opening_moneyline` in return dict
- ✅ `build_design_matrix()` updated: No `has_opening_moneyline` parameter
- ✅ `predict_proba()` updated: No `has_opening_moneyline` parameter
- ✅ Grep verification: Only 6 comment/docstring references remain

**Files**: `train_winprob_catboost.py`, `precompute_model_probabilities.py`, `simulate_trading_strategy.py`, `evaluate_winprob_model.py`, `evaluate_winprob_time_buckets.py`
- ✅ All files verified: No functional references to `has_opening_moneyline`
- ✅ Linting checks passed: No errors found

---

## Technical Assessment

### Feature Importance Analysis

**Current Feature Set** (after Sprint 1):
- `opening_overround`: 24.15% importance (continuous, high value)
- `has_opening_spread`: 0.36% importance (binary flag, low value)
- `has_opening_total`: 0.07% importance (binary flag, very low value)

**Analysis**:
- `opening_overround` accounts for 98.2% of opening odds feature importance (24.15% / (24.15% + 0.36% + 0.07%) = 98.2%)
- Binary flags combined account for only 1.8% of opening odds feature importance
- This suggests `has_opening_spread` and `has_opening_total` may be redundant or add minimal value

**Hypothesis**: Removing `has_opening_spread` and `has_opening_total` may:
- Reduce model complexity without significant performance loss
- Eliminate potential collinearity between binary flags
- Improve model interpretability (single continuous feature vs. mixed types)

### Collinearity Risk Assessment

**Current Risk** (3 features):
- `opening_overround` vs. `has_opening_spread`: Low risk (continuous vs. binary, different information)
- `opening_overround` vs. `has_opening_total`: Low risk (continuous vs. binary, different information)
- `has_opening_spread` vs. `has_opening_total`: **Potential risk** (both binary flags, likely correlated if games with spread also have total)

**After Single-Feature Reduction** (1 feature):
- No collinearity risk (single feature)
- Maximum simplicity and interpretability

### Closing Line Analysis Results

**Source**: `story1.3_closing_line_analysis.md`

**Findings**:
- Only 394 games (3.5%) have timestamped closing/pre-tip odds
- Even 60-minute window only covers 147 games (1.3%)
- Opening odds: 10,742 games (94.4% coverage) ✅
- **Conclusion**: Closing/pre-tip odds not viable for current training needs

**Recommendation**: No future sprint needed for closing line implementation (insufficient data)

---

## Evidence and Proof

### MANDATORY: File Content Verification

**Sprint 1 Completion Status**:
- **File**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/verification_report.md`
- **Evidence**: Document shows 80% completion (Epic 1, Epic 2, Epic 4 partial complete; Epic 3 pending)
- **Status**: Code changes verified, model retraining pending

**Feature Importance Evidence**:
- **File**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/epic1_completion_report.md`
- **Evidence**: Feature importance values documented (lines 37-82)
- **Status**: `opening_overround` = 24.15%, `has_opening_spread` = 0.36%, `has_opening_total` = 0.07%

**Code State Evidence**:
- **File**: `scripts/lib/_winprob_lib.py`
- **Evidence**: Lines 237-241 show `ODDS_MODEL_FEATURES` with only 3 features
- **Status**: `has_opening_moneyline` removed, 3 features remain

**Closing Line Analysis Evidence**:
- **File**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/story1.3_closing_line_analysis.md`
- **Evidence**: Coverage statistics show 3.5% vs 94.4% for opening odds
- **Status**: Closing line not viable, no future sprint needed

---

## Recommendations

### Immediate Actions (Priority: Critical)

**Recommendation 1**: **Complete Sprint 1** - Finish model retraining and evaluation
- **Rationale**: Sprint 1 is 80% complete. Cannot validate performance impact without retraining.
- **Files to Modify**: None (code already updated)
- **Estimated Effort**: 2-4 hours (model retraining only, requires database access)
- **Risk Level**: Low (code changes verified, just needs execution)
- **Success Metrics**: 
  - 4 models retrained with 3-feature set
  - Performance maintained or improved (Brier score, log loss, ROC-AUC)
  - Feature counts verified (17 for odds+interactions, 9 for odds+no_interaction)

**Implementation Steps**:
1. Set up database connection: `export DATABASE_URL="postgresql://..."`
2. Retrain 4 v2 odds-enabled models (30-60 minutes each):
   - `catboost_odds_platt_v2`
   - `catboost_odds_isotonic_v2`
   - `catboost_odds_no_interaction_platt_v2`
   - `catboost_odds_no_interaction_isotonic_v2`
3. Evaluate retrained models on test set (2024 season)
4. Compare performance metrics (old vs. new feature set)
5. Update precomputed probabilities

### Short-term Improvements (Priority: Medium)

**Recommendation 2**: **Evaluate Single-Feature Alternative** - Test using only `opening_overround`
- **Rationale**: Feature importance shows binary flags (`has_opening_spread` 0.36%, `has_opening_total` 0.07%) have very low importance compared to `opening_overround` (24.15%). Combined binary flags contribute only 1.8% of `opening_overround`'s importance. Removing them may improve model simplicity without performance loss.
- **Prerequisites**: Must complete Sprint 1 first (need baseline performance with 3 features)
- **Files to Modify**: 
  - `scripts/lib/_winprob_lib.py` (remove `has_opening_spread` and `has_opening_total` from `ODDS_MODEL_FEATURES`, `compute_opening_odds_features()`, `build_design_matrix()`)
  - `scripts/model/train_winprob_catboost.py` (update feature names)
  - `scripts/model/precompute_model_probabilities.py` (update feature checks)
  - `scripts/trade/simulate_trading_strategy.py` (remove feature references)
  - `scripts/model/evaluate_winprob_model.py` (remove feature references)
  - `scripts/model/evaluate_winprob_time_buckets.py` (remove feature references)
- **Estimated Effort**: 6-8 hours (code changes + retraining + evaluation)
- **Risk Level**: Medium (requires model retraining and validation)
- **Success Metrics**: 
  - Model performance comparison (3 features vs. 1 feature)
  - Feature importance validation (confirm low importance of binary flags)
  - Performance maintained or improved (target: <5% degradation acceptable)

**Sprint Scope**: Single Sprint (6-8 hours)
- **Rationale**: Similar scope to Sprint 1 (removing 2 features instead of 1). Code changes follow same pattern. Estimated effort fits within single sprint.

**Implementation Plan**:
1. **Phase 1**: Code Changes (2-3 hours)
   - Remove `has_opening_spread` and `has_opening_total` from all 6 files
   - Update `ODDS_MODEL_FEATURES` to only include `opening_overround`
   - Verify no references remain (grep checks)
2. **Phase 2**: Model Retraining (2-4 hours)
   - Retrain 4 v2 odds-enabled models with single-feature set
   - Verify feature counts (16 for odds+interactions, 8 for odds+no_interaction)
3. **Phase 3**: Evaluation and Comparison (1-2 hours)
   - Evaluate retrained models on test set
   - Compare performance (3 features vs. 1 feature)
   - Extract feature importance from retrained models
   - Document findings

### Long-term Strategic Changes (Priority: Low)

**Recommendation 3**: **Monitor Closing Line Data** - No action needed unless data collection improves
- **Rationale**: Closing line analysis completed and found insufficient coverage (3.5% vs 94.4% for opening odds). No future sprint needed unless data collection improves significantly (>50% coverage).
- **Files to Modify**: None (monitoring only)
- **Estimated Effort**: 0 hours (no action needed)
- **Risk Level**: None (no action)
- **Success Metrics**: N/A (monitoring only)

**Future Consideration** (if data collection improves):
- Re-run closing line analysis when coverage exceeds 50%
- Evaluate performance improvement (closing odds may be more predictive)
- Consider implementing as optional feature (use when available, fallback to opening odds)

---

## Implementation Plan

### Sprint 1 Completion (Not a New Sprint)

**Duration**: 2-4 hours  
**Objective**: Complete model retraining and evaluation for Sprint 1

**Dependencies**: Database access via `DATABASE_URL`

**Deliverables**: 
- 4 retrained v2 odds-enabled model artifacts
- Performance evaluation on test set (2024 season)
- Performance comparison report (old 4-feature vs. new 3-feature set)
- Updated precomputed probabilities

**Tasks**:
1. Retrain 4 v2 odds-enabled models (30-60 minutes each)
2. Evaluate retrained models on test set
3. Compare performance metrics (old vs. new)
4. Update precomputed probabilities
5. Document results

### Future Sprint 2: Single-Feature Evaluation (If Recommended)

**Duration**: 6-8 hours  
**Objective**: Evaluate single-feature alternative (only `opening_overround`)

**Dependencies**: Must complete Sprint 1 first (need baseline performance)

**Deliverables**: 
- Code changes removing `has_opening_spread` and `has_opening_total`
- 4 retrained models with single-feature set
- Performance comparison (3 features vs. 1 feature)
- Feature importance validation

**Tasks**:
1. **Phase 1**: Code Changes (2-3 hours)
   - Remove `has_opening_spread` and `has_opening_total` from all 6 files
   - Update constants and function signatures
   - Verify changes (grep checks)
2. **Phase 2**: Model Retraining (2-4 hours)
   - Retrain 4 models with single-feature set
   - Verify feature counts
3. **Phase 3**: Evaluation (1-2 hours)
   - Evaluate models on test set
   - Compare performance (3 vs. 1 feature)
   - Extract feature importance
   - Document findings

---

## Risk Assessment

### Technical Risks

**Risk 1**: Removing binary flags reduces model performance
- **Probability**: Low-Medium (feature importance suggests low impact, but requires validation)
- **Impact**: Medium (worse predictions if binary flags add value)
- **Mitigation**: Compare performance before/after, keep 3-feature models as backup
- **Contingency**: Revert to 3 features if performance degrades significantly (>5%)

**Risk 2**: Sprint 1 retraining reveals performance issues
- **Probability**: Low (redundant feature removal should not hurt performance)
- **Impact**: Medium (may need to investigate if performance degrades)
- **Mitigation**: Compare metrics carefully, investigate if degradation significant
- **Contingency**: Keep old models if performance degrades significantly

### Business Risks

**Risk 1**: Model retraining delays deployment
- **Probability**: Medium (requires 2-4 hours for retraining)
- **Impact**: Low (no urgent deployment deadline mentioned)
- **Mitigation**: Plan retraining during low-activity period
- **Contingency**: Stagger retraining across models if needed

### Resource Risks

**Risk 1**: Database access not available for retraining
- **Probability**: Medium (mentioned as blocker in sprint status)
- **Impact**: High (blocks Sprint 1 completion)
- **Mitigation**: Verify database access before starting
- **Contingency**: Defer Sprint 1 completion until database access available

---

## Success Metrics and Monitoring

### Sprint 1 Completion Metrics

**Model Performance**:
- **Brier Score**: Compare old (4 features) vs. new (3 features) - target: maintain or improve
- **Log Loss**: Compare old vs. new - target: maintain or improve
- **ROC-AUC**: Compare old vs. new - target: maintain or improve

**Feature Metrics**:
- **Feature Count**: Reduced from 4 to 3 opening odds features ✅ (code verified)
- **Model Artifacts**: 4 retrained models with correct feature counts (pending)

### Future Sprint 2 Metrics (If Recommended)

**Model Performance**:
- **Brier Score**: Compare 3 features vs. 1 feature - target: <5% degradation acceptable
- **Log Loss**: Compare 3 features vs. 1 feature - target: <5% degradation acceptable
- **ROC-AUC**: Compare 3 features vs. 1 feature - target: maintain or improve

**Feature Metrics**:
- **Feature Count**: Reduced from 3 to 1 opening odds feature
- **Feature Importance**: Confirm low importance of binary flags after retraining
- **Model Simplicity**: Improved interpretability (single continuous feature)

---

## Appendices

### Appendix A: Sprint 1 Status Summary

**Source**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/verification_report.md`

**Completed**:
- Epic 1: Data Analysis and Verification ✅
- Epic 2: Code Changes ✅
- Epic 4: Quality Assurance (partial) ✅

**Pending**:
- Epic 3: Model Retraining and Evaluation ❌

**Overall**: 80% complete

### Appendix B: Feature Importance Evidence

**Source**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/epic1_completion_report.md`

**Model**: `catboost_odds_platt_v2`

**Feature Importance**:
- `opening_overround`: 24.15% (high)
- `has_opening_moneyline`: 0.30% (removed)
- `has_opening_spread`: 0.36% (low)
- `has_opening_total`: 0.07% (very low)

**Analysis**: Binary flags combined contribute only 1.8% of `opening_overround`'s importance.

### Appendix C: Closing Line Analysis Summary

**Source**: `cursor-files/sprints/2026-01-24-opening-odds-collinearity-fix/story1.3_closing_line_analysis.md`

**Findings**:
- Closing/pre-tip odds: 394 games (3.5% coverage)
- Opening odds: 10,742 games (94.4% coverage)
- **Conclusion**: Closing line not viable, no future sprint needed

---

## Document Validation

**IMPORTANT**: This analysis follows the comprehensive validation checklist in `ANALYSIS_STANDARDS.md`.

**Validation Status**:
- ✅ Evidence-based claims (code references, sprint documents, feature importance data)
- ✅ File content verification (sprint documents read and analyzed)
- ✅ Feature importance evidence documented (epic1_completion_report.md)
- ✅ Sprint status verified (verification_report.md)
- ✅ Closing line analysis reviewed (story1.3_closing_line_analysis.md)
- ✅ Code state verified (grep checks documented in verification_report.md)
- ✅ No assumptions made (all claims backed by evidence)
- ✅ Definitive language used (no vague terms)
- ✅ Concrete evidence provided (feature importance percentages, sprint completion percentages)

**Key Findings**:
1. Sprint 1 is 80% complete - only model retraining pending (2-4 hours, requires database access)
2. Feature importance suggests single-feature alternative may be viable (binary flags have very low importance)
3. Closing line analysis complete - no future sprint needed (insufficient data coverage)

**Recommendations**:
1. **Priority: Critical** - Complete Sprint 1 (finish model retraining)
2. **Priority: Medium** - Evaluate single-feature alternative (after Sprint 1 completion)
3. **Priority: Low** - Monitor closing line data (no action needed unless coverage improves)

---

**Analysis Status**: ✅ **COMPLETE** - Evidence-based analysis with concrete recommendations
