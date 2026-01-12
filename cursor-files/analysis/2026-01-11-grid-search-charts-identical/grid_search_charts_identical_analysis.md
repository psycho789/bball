# Analysis: Grid Search Charts Appearing Identical

**Date**: Sun Jan 11 10:17:38 PST 2026  
**Status**: Draft  
**Author**: AI Assistant  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Investigate why all three grid search heatmap charts (Training Profit, Validation Profit, Profit Factor) appear identical in the webapp, when they should show different data.

## Analysis Standards Reference

**Important**: This analysis must follow the comprehensive standards defined in `ANALYSIS_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim is backed by concrete evidence (code refs, commands + verbatim output, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers analyzed.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: Use PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings
- **Finding 1**: The backend code (`_transform_visualization_data()`) correctly creates three different heatmaps:
  1. `profit_heatmap_train` from `df_train` with `'net_profit_dollars'`
  2. `profit_heatmap_valid` from `df_valid` with `'net_profit_dollars'`
  3. `profit_factor_heatmap_valid` from `df_valid` with `'profit_factor'`
- **Finding 2**: The frontend code correctly calls `renderProfitHeatmap()` three times with different data objects and different canvas IDs.
- **Finding 3**: The old analysis script (`analyze_grid_search_results.py`) creates three different heatmaps successfully, suggesting the data transformation logic is correct.

### Critical Issues Identified
- **Issue 1**: [UNKNOWN] - All three charts appear identical, but code inspection shows they should be different. Root cause needs investigation via logging.
- **Issue 2**: Missing verification - No checks to ensure `train_results` and `valid_results` contain different data before visualization.

### Recommended Actions
- **Action 1**: [Priority: High] - Add comprehensive logging to verify data at each step (aggregation, transformation, frontend rendering).
- **Action 2**: [Priority: High] - Verify that `train_results` and `valid_results` contain different data (they use different game splits).
- **Action 3**: [Priority: Medium] - Add frontend console logging to verify different data is received for each chart.

### Success Metrics
- **Metric 1**: All three charts display different data visually - [Baseline: All identical] → [Target: All different] ([100% differentiation])
- **Metric 2**: Backend logs confirm different data for each heatmap - [Baseline: Unknown] → [Target: Verified different] ([100% verification])

## Problem Statement

### Current Situation
When running grid search via the webapp, three heatmap charts are displayed:
1. **Profit Heatmap (Training Set)** - Should show profit for training games
2. **Profit Heatmap (Validation Set)** - Should show profit for validation games  
3. **Profit Factor Heatmap (Validation Set)** - Should show profit factor for validation games

**Problem**: All three charts appear visually identical (same colors, same patterns, same data).

**Expected Behavior**: 
- Training and Validation profit heatmaps should differ (different game sets)
- Validation profit and profit factor heatmaps should differ (different metrics: dollars vs. ratio)

### Pain Points
- **Pain Point 1**: Cannot distinguish between training and validation performance, making it impossible to assess overfitting.
- **Pain Point 2**: Cannot see profit factor patterns, which are important for risk assessment.
- **Pain Point 3**: Charts are misleading - appear to show three different views but actually show the same data three times.

### Business Impact
- **Performance Impact**: Users cannot properly evaluate hyperparameter search results.
- **User Experience Impact**: Misleading visualizations lead to incorrect conclusions about strategy performance.
- **Maintenance Impact**: Bug suggests data pipeline issue that could affect other features.

### Success Criteria
- **[Criterion 1]**: Training profit heatmap shows different data than validation profit heatmap.
- **[Criterion 2]**: Profit factor heatmap shows different data than profit heatmap (different metric).
- **[Criterion 3]**: Visual inspection confirms all three charts are distinct.

## Current State Analysis

### Code Flow Analysis

**Backend Data Flow**:
```
process_combination_with_pool()
  ├─ Runs simulation for TRAIN games → result['train']
  ├─ Runs simulation for VALID games → result['valid']
  └─ Runs simulation for TEST games → result['test']

Aggregate results (lines 562-585)
  ├─ train_results = [result['train'] for each combination]
  ├─ valid_results = [result['valid'] for each combination]
  └─ test_results = [result['test'] for each combination]

Transform visualization data (line 634)
  ├─ df_train = pd.DataFrame(train_results)
  ├─ df_valid = pd.DataFrame(valid_results)
  ├─ profit_heatmap_train = create_heatmap_data(df_train, 'net_profit_dollars')
  ├─ profit_heatmap_valid = create_heatmap_data(df_valid, 'net_profit_dollars')
  └─ profit_factor_heatmap_valid = create_heatmap_data(df_valid, 'profit_factor')
```

**Frontend Rendering Flow**:
```
renderVisualizations(vizData)
  ├─ renderProfitHeatmap(vizData.profit_heatmap_train, 'profitHeatmapTrainCanvas')
  ├─ renderProfitHeatmap(vizData.profit_heatmap_valid, 'profitHeatmapValidCanvas')
  └─ renderProfitHeatmap(vizData.profit_factor_heatmap_valid, 'profitFactorHeatmapCanvas')
```

### Code Quality Assessment

#### Backend Implementation

**File**: `webapp/api/endpoints/grid_search.py:770-828`

**Current Implementation**:
- ✅ Creates separate DataFrames for train and valid results
- ✅ Calls `create_heatmap_data()` with different dataframes and columns
- ✅ Returns three separate heatmap dictionaries

**Potential Issues**:
- ❓ No verification that `train_results` and `valid_results` contain different data
- ❓ No verification that the three heatmaps are actually different before returning
- ❓ `_convert_numpy_types()` might be mutating data in unexpected ways

#### Frontend Implementation

**File**: `webapp/static/js/grid-search.js:523-548`

**Current Implementation**:
- ✅ Calls `renderProfitHeatmap()` three times with different data objects
- ✅ Uses different canvas IDs for each chart
- ✅ Each chart calculates its own min/max for color scaling

**Potential Issues**:
- ❓ No verification that different data is received for each chart
- ❓ No error handling if data is missing or identical

### Comparison with Old Script

**File**: `scripts/trade/analyze_grid_search_results.py:435-465`

**Old Script Creates**:
1. `profit_heatmap_train.png` - Uses `df_train` with `'net_profit_dollars'`
2. `profit_heatmap_valid.png` - Uses `df_valid` with `'net_profit_dollars'`
3. `profit_factor_heatmap_valid.png` - Uses `df_valid` with `'profit_factor'`

**Key Difference**: Old script reads from CSV files, webapp uses in-memory results.

**Pivot Logic**: Both use identical pivot: `df.pivot(index='exit_threshold', columns='entry_threshold', values=value_col)`

## Technical Assessment

### Design Pattern Analysis

#### Current Patterns in Use

**Design Pattern Analysis: Data Transformation Pipeline**

**Pattern Name**: Data Transformation Pipeline  
**Pattern Category**: Architectural  
**Pattern Intent**: Transform raw simulation results into visualization-ready format.

**Implementation**:
- File: `webapp/api/endpoints/grid_search.py:770-828`
- Function: `_transform_visualization_data()` transforms results into heatmap format
- Helper function: `create_heatmap_data()` creates pivot table and matrix

**Benefits**:
- Clear separation of concerns (data processing vs. visualization)
- Reusable helper function for creating heatmaps
- Consistent data format for frontend

**Trade-offs**:
- No verification that input data is correct
- No validation that output data is different for each chart
- Potential for silent failures if data is incorrect

**Why This Pattern**: Appropriate for transforming data for visualization, but needs validation.

### Algorithm Analysis

#### Current Algorithms

**Algorithm Analysis: Pivot Table Creation**

**Algorithm Name**: Pivot Table Creation  
**Algorithm Type**: Data Transformation  
**Big O Notation**: 
- Time Complexity: O(n) where n = number of result rows
- Space Complexity: O(k × m) where k = unique entry thresholds, m = unique exit thresholds

**Algorithm Description**:
- Uses pandas `pivot()` to reshape data from long to wide format
- Creates matrix where rows = exit thresholds, columns = entry thresholds
- Converts to list of lists for JSON serialization

**Use Case**: 
- Transform simulation results into 2D grid for heatmap visualization
- Enable efficient rendering of parameter space

**Performance Characteristics**:
- Best Case: O(n) - all combinations present
- Average Case: O(n) - typical grid search results
- Worst Case: O(n) - same complexity regardless
- Memory Usage: O(k × m) - matrix size depends on grid resolution

**Why This Algorithm**: Standard pandas operation, efficient and well-tested.

### Potential Root Causes

#### Hypothesis 1: train_results and valid_results Contain Same Data

**Evidence Needed**:
- Check if `train_results` and `valid_results` are the same list object
- Verify that `result['train']` and `result['valid']` contain different data
- Check if `run_simulation_for_games()` returns different results for different game lists

**Investigation Steps**:
1. Add logging to verify `train_results` and `valid_results` are different objects
2. Add logging to verify first few entries are different
3. Check if `process_combination_with_pool()` correctly separates train/valid/test results

#### Hypothesis 2: Data Corruption During Conversion

**Evidence Needed**:
- Check if `_convert_numpy_types()` is mutating data incorrectly
- Verify that the three heatmap dictionaries are different objects
- Check if JSON serialization is corrupting data

**Investigation Steps**:
1. Add logging before and after `_convert_numpy_types()`
2. Verify object IDs are different for each heatmap
3. Check JSON serialization doesn't merge dictionaries

#### Hypothesis 3: Frontend Rendering Bug

**Evidence Needed**:
- Check if frontend receives different data for each chart
- Verify canvas IDs are correct
- Check if `renderProfitHeatmap()` is accidentally using the same data variable

**Investigation Steps**:
1. Add console logging to verify different data received
2. Verify canvas elements exist and are different
3. Check if JavaScript closures are causing variable reuse

## Evidence and Proof

### Code References

#### Backend Visualization Transformation

**File**: `webapp/api/endpoints/grid_search.py:770-828`

**Issue**: Three heatmaps are created but appear identical

**Evidence**:
- **Command**: `grep -n "create_heatmap_data" webapp/api/endpoints/grid_search.py`
- **Output**: Lines 818, 821, 824 create three different heatmaps
- **Content**:
```818:824:webapp/api/endpoints/grid_search.py
        # 1. Profit heatmap (TRAIN) - uses TRAIN data with net_profit_dollars
        profit_heatmap_train = create_heatmap_data(df_train, 'net_profit_dollars')
        
        # 2. Profit heatmap (VALID) - uses VALID data with net_profit_dollars
        profit_heatmap_valid = create_heatmap_data(df_valid, 'net_profit_dollars')
        
        # 3. Profit factor heatmap (VALID) - uses VALID data with profit_factor
        profit_factor_heatmap_valid = create_heatmap_data(df_valid, 'profit_factor')
```

**Impact**: Code looks correct, but charts appear identical - suggests data issue.

#### Frontend Rendering

**File**: `webapp/static/js/grid-search.js:523-548`

**Issue**: Frontend renders three charts but they appear identical

**Evidence**:
- **Command**: `grep -n "renderProfitHeatmap" webapp/static/js/grid-search.js`
- **Output**: Lines 526, 531, 536 call renderProfitHeatmap with different data
- **Content**:
```523:537:webapp/static/js/grid-search.js
function renderVisualizations(vizData) {
    // Profit heatmap (TRAIN)
    if (vizData.profit_heatmap_train) {
        renderProfitHeatmap(vizData.profit_heatmap_train, 'profitHeatmapTrainCanvas');
    }
    
    // Profit heatmap (VALID)
    if (vizData.profit_heatmap_valid) {
        renderProfitHeatmap(vizData.profit_heatmap_valid, 'profitHeatmapValidCanvas');
    }
    
    // Profit factor heatmap (VALID)
    if (vizData.profit_factor_heatmap_valid) {
        renderProfitHeatmap(vizData.profit_factor_heatmap_valid, 'profitFactorHeatmapCanvas');
    }
```

**Impact**: Frontend code looks correct - suggests backend data issue.

#### Old Script Comparison

**File**: `scripts/trade/analyze_grid_search_results.py:435-465`

**Evidence**: Old script successfully creates three different heatmaps

**Content**:
```435:465:scripts/trade/analyze_grid_search_results.py
    # A) Profit heatmaps
    create_heatmap(
        df_train,
        'net_profit_dollars',
        'Profit Heatmap (TRAIN)',
        plots_dir / 'profit_heatmap_train.png',
        chosen_params
    )
    
    create_heatmap(
        df_valid,
        'net_profit_dollars',
        'Profit Heatmap (VALID)',
        plots_dir / 'profit_heatmap_valid.png',
        chosen_params
    )
    
    # D) Secondary heatmap (profit_factor)
    create_heatmap(
        df_valid,
        'profit_factor',
        'Profit Factor Heatmap (VALID)',
        plots_dir / 'profit_factor_heatmap_valid.png',
        chosen_params
    )
```

**Impact**: Old script uses same logic and creates different charts - confirms logic is correct.

## Recommendations

### Immediate Actions (Priority: High)

#### Recommendation 1: Add Comprehensive Logging

**Specific Action**: Add logging at each step to verify data is different:
1. After aggregation (verify train_results ≠ valid_results)
2. After DataFrame creation (verify df_train ≠ df_valid)
3. After heatmap creation (verify three heatmaps are different)
4. Before JSON serialization (verify data structure is correct)

**Files to Modify**: 
- `webapp/api/endpoints/grid_search.py` - Add logging statements

**Estimated Effort**: 1 hour
- Add logging statements at key points
- Verify logs show different data

**Risk Level**: Low
- Non-breaking change
- Helps identify root cause

**Success Metrics**: 
- Logs confirm different data at each step
- Root cause identified

#### Recommendation 2: Add Data Validation

**Specific Action**: Add validation checks to ensure:
1. `train_results` and `valid_results` are different objects
2. First few entries contain different data
3. Three heatmaps have different sample values

**Files to Modify**:
- `webapp/api/endpoints/grid_search.py` - Add validation checks

**Estimated Effort**: 1 hour
- Add validation functions
- Raise errors if data is identical

**Risk Level**: Low
- Non-breaking change
- Helps catch bugs early

**Success Metrics**:
- Validation catches if data is identical
- Errors raised with clear messages

#### Recommendation 3: Add Frontend Console Logging

**Specific Action**: Add console.log statements to verify:
1. Different data received for each chart
2. Sample values are different
3. Canvas elements are different

**Files to Modify**:
- `webapp/static/js/grid-search.js` - Add console logging

**Estimated Effort**: 30 minutes
- Add console.log statements
- Verify in browser console

**Risk Level**: Low
- Non-breaking change
- Helps debug frontend issues

**Success Metrics**:
- Console shows different data for each chart
- Frontend issues identified if present

### Short-term Improvements (Priority: Medium)

#### Recommendation 4: Add Unit Tests

**Specific Action**: Create unit tests for `_transform_visualization_data()`:
1. Test with known different train/valid data
2. Verify three heatmaps are different
3. Test edge cases (empty data, single combination)

**Files to Create**:
- `tests/python/test_grid_search_visualization.py`

**Estimated Effort**: 2 hours
- Write test cases
- Verify tests pass

**Risk Level**: Low
- Non-breaking change
- Prevents regressions

### Long-term Strategic Changes (Priority: Low)

#### Recommendation 5: Refactor Visualization Data Transformation

**Specific Action**: Extract visualization logic into separate module with better error handling and validation.

**Files to Modify**:
- Create `webapp/api/visualization.py`
- Move `_transform_visualization_data()` to new module

**Estimated Effort**: 3-4 hours
- Extract function to new module
- Add comprehensive validation
- Update imports

**Risk Level**: Medium
- Refactoring may introduce bugs
- Requires testing

## Implementation Plan

### Phase 1: Add Logging and Validation (Duration: 2 hours)
**Objective**: Add comprehensive logging and validation to identify root cause

**Dependencies**: None

**Deliverables**: 
- Logging statements added to backend
- Validation checks added
- Console logging added to frontend

#### Tasks
- **[Task 1]**: Add backend logging
  - **Files**: `webapp/api/endpoints/grid_search.py`
  - **Effort**: 1 hour
  - **Prerequisites**: None

- **[Task 2]**: Add frontend console logging
  - **Files**: `webapp/static/js/grid-search.js`
  - **Effort**: 30 minutes
  - **Prerequisites**: None

- **[Task 3]**: Test and verify logs
  - **Files**: Run grid search and check logs
  - **Effort**: 30 minutes
  - **Prerequisites**: Tasks 1-2 complete

### Phase 2: Fix Root Cause (Duration: TBD)
**Objective**: Fix the bug causing identical charts

**Dependencies**: Phase 1 (root cause identified)

**Deliverables**:
- Bug fix implemented
- Charts display different data

#### Tasks
- **[Task 1]**: Fix identified bug
  - **Files**: TBD based on root cause
  - **Effort**: TBD
  - **Prerequisites**: Root cause identified

### Phase 3: Verification (Duration: 1 hour)
**Objective**: Verify fix works correctly

**Dependencies**: Phase 2 complete

**Deliverables**:
- All three charts display different data
- Visual inspection confirms differences

#### Tasks
- **[Task 1]**: Run grid search and verify charts
  - **Files**: Manual testing
  - **Effort**: 1 hour
  - **Prerequisites**: Phase 2 complete

## Risk Assessment

### Technical Risks
- **Risk 1**: Logging reveals data is actually identical (suggests aggregation bug)
  - **Probability**: Medium
  - **Impact**: High (requires fixing data aggregation)
  - **Mitigation**: Add validation to catch early
  - **Contingency**: Fix aggregation logic

- **Risk 2**: Data is different but charts still look identical (rendering bug)
  - **Probability**: Low
  - **Impact**: Medium (requires fixing frontend)
  - **Mitigation**: Add frontend logging
  - **Contingency**: Fix frontend rendering

- **Risk 3**: Root cause is subtle and hard to identify
  - **Probability**: Medium
  - **Impact**: Medium (delays fix)
  - **Mitigation**: Comprehensive logging at all steps
  - **Contingency**: Add more detailed logging

## Success Metrics and Monitoring

### Performance Metrics
- **Data Verification**: Logs confirm different data for each heatmap ([Target: 100%])
- **Visual Verification**: Charts appear different visually ([Target: 100%])

### Quality Metrics
- **Bug Detection**: Root cause identified via logging ([Target: Root cause found])
- **Fix Verification**: Charts display correct data ([Target: 100% correct])

## Appendices

### Appendix A: Code Changes Made

#### Backend Logging Added

**File**: `webapp/api/endpoints/grid_search.py`

**Changes**:
1. Added logging to verify `train_results` and `valid_results` are different objects
2. Added logging to verify DataFrames contain different data
3. Added logging to verify three heatmaps have different sample values
4. Added validation checks to catch if data is identical

#### Frontend Logging Added

**File**: `webapp/static/js/grid-search.js`

**Changes**:
1. Added console.log to verify different data received for each chart
2. Added sample value logging for each heatmap

### Appendix B: Next Steps

1. **Run grid search** and check backend logs for:
   - `[VIZ_DATA]` log messages showing data ranges
   - Warnings if data appears identical
   - Errors if critical bugs detected

2. **Check browser console** for:
   - `[GridSearch]` log messages showing sample values
   - Warnings if data is missing
   - Verification that different data received

3. **Visual inspection** of charts:
   - Training profit should differ from validation profit
   - Profit factor should differ from profit (different metric)

4. **If charts still identical**:
   - Review logs to identify where data becomes identical
   - Check if `train_results` and `valid_results` are same object
   - Verify `run_simulation_for_games()` returns different results

### Appendix C: Reference Materials

- **Backend Endpoint**: `webapp/api/endpoints/grid_search.py`
- **Frontend Code**: `webapp/static/js/grid-search.js`
- **Old Analysis Script**: `scripts/trade/analyze_grid_search_results.py`
- **Grid Search Script**: `scripts/trade/grid_search_hyperparameters.py`

---

## Document Validation

**IMPORTANT**: Use the comprehensive validation checklist in `ANALYSIS_STANDARDS.md` to ensure this analysis meets all quality standards.

