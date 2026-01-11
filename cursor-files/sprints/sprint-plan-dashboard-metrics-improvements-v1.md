# Sprint Plan: Dashboard Metrics Improvements - Data Science & Betting Relevance

**Date**: 2025-12-24  
**Sprint Duration**: 5-7 days (40-56 hours total)  
**Sprint Goal**: Transform the ESPN vs Kalshi dashboard metrics to be defensible to data scientists and betting-relevant by fixing misleading labels, adding calibration views, implementing time-sliced and decision-weighted scoring, and adding diagnostic counters that point to edge opportunities.  
**Current Status**: Dashboard has basic metrics (Brier score, log loss, volatility, correlation, MAE) with some time-sliced and decision-weighted metrics already partially implemented. Labels need correction, new metrics need to be added, and charts need enhancement.  
**Target Status**: All metrics correctly labeled, all new metrics implemented, all charts enhanced with proper tooltips and visualizations, and all betting-relevant scoring added.  
**Team Size**: 1 developer  
**Sprint Lead**: AI Assistant

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline

- **Test Results**: No formal test suite exists; manual testing only
- **QC Results**: No automated QC checks; manual validation
- **Code Coverage**: Not measured
- **Build Status**: Application runs successfully; FastAPI server starts without errors

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
- **Business Driver**: The current dashboard metrics have misleading labels and lack betting-relevant scoring. Data scientists need defensible metrics with clear semantics, and bettors need metrics that reflect when money is actually at stake. The dashboard must answer: "Who is more accurate when it matters?" not just "Who is more accurate on average?"
- **Success Criteria**: 
  - All metric labels are semantically correct and defensible
  - Calibration views (reliability curves) are available for both ESPN and Kalshi
  - Time-sliced and decision-weighted metrics are implemented and displayed
  - Diagnostic counters (sign flips, max divergence, extreme probability rates) are available
  - All charts have proper tooltips explaining metrics in plain language
- **Stakeholders**: Data scientists using the dashboard for model building, bettors evaluating edge opportunities
- **Timeline Constraints**: None specified

### Technical Context
- **Current System State**: 
  - Backend: FastAPI application in `webapp/api/` with endpoints in `endpoints/stats.py` and `endpoints/aggregate_stats.py`
  - Frontend: JavaScript application in `webapp/static/js/stats.js` with Chart.js for visualizations
  - Metrics currently implemented:
    - Brier score (labeled as "Brier Score" - needs renaming)
    - Log loss (with clipping already implemented)
    - Volatility, standard deviation, variance, MAD, CV
    - Correlation (time-sliced already implemented)
    - Mean Absolute Difference (already renamed from MAE in some places)
    - Time-sliced Brier scores (Q1, Halftime, Q4, Final 2 minutes) - already implemented
    - Reliability curves - already implemented but need verification against spec
    - Decision-weighted metrics - already implemented but need verification against spec
  - Database: PostgreSQL with `espn.*` and `kalshi.*` schemas
- **Target System State**: 
  - All metrics correctly labeled per specification
  - All new metrics (median points/game, max divergence, sign flips, extreme probability rates) implemented
  - All charts enhanced (reliability curves with diagonal line, time-sliced performance chart, improved volatility scatter, disagreement vs outcome chart)
  - All decision-weighted Brier variants implemented (confidence-weighted and market-actionable)
  - Profit proxy metrics implemented (optional)
- **Architecture Impact**: 
  - Backend: New calculation functions in `stats.py`, updates to `aggregate_stats.py`
  - Frontend: New chart rendering functions in `stats.js`, updated labels and tooltips
  - No database schema changes required
- **Integration Points**: 
  - API endpoints: `/api/games/{game_id}/stats` and `/api/stats/aggregate`
  - Frontend: Aggregate stats page (`/static/templates/aggregate-stats.html`)

### Sprint Scope
- **In Scope**: 
  - Renaming all metric labels per specification (A1, A2, A3)
  - Adding new number metrics (B1, B2, B3, B4)
  - Adding/upgrading charts (C1, C2, C3, C4)
  - Adding decision-weighted scoring (D1, D2)
  - Implementing alignment window logic (E2)
  - Adding tooltips and info icons (E4)
- **Out of Scope**: 
  - Database schema changes
  - Real backtesting system (profit proxy is a sanity check only)
  - Live data integration (separate feature)
  - Performance optimization beyond current batch query approach
- **Assumptions**: 
  - Current alignment logic (nearest timestamp within window) is acceptable
  - Chart.js library supports all required chart types
  - Existing reliability curve and decision-weighted implementations can be adapted to match spec
- **Constraints**: 
  - Must maintain backward compatibility with existing API responses (add new fields, don't remove old ones)
  - Must not break existing frontend functionality
  - Must follow existing code patterns and structure

## Sprint Phases

### Phase 1: Label and Semantics Fixes (Duration: 8-10 hours)
**Objective**: Rename all misleading metric labels to be semantically correct and defensible
**Dependencies**: None
**Deliverables**: All metric labels renamed in backend and frontend, tooltips added for correlation

### Phase 2: New Number Metrics (Duration: 12-16 hours)
**Objective**: Implement all new number metrics (median points/game, max divergence, sign flips, extreme probability rates)
**Dependencies**: Must complete Phase 1
**Deliverables**: All new metrics calculated and displayed in aggregate stats

### Phase 3: Chart Enhancements (Duration: 16-20 hours)
**Objective**: Add/upgrade all charts (reliability curves, time-sliced performance, volatility scatter improvements, disagreement vs outcome)
**Dependencies**: Must complete Phase 2
**Deliverables**: All charts implemented with proper tooltips and visualizations

### Phase 4: Decision-Weighted Scoring and Final Polish (Duration: 8-12 hours)
**Objective**: Implement decision-weighted Brier variants, profit proxy (optional), alignment window logic, and final UI polish
**Dependencies**: Must complete Phase 3
**Deliverables**: All decision-weighted metrics implemented, profit proxy added (if time), alignment logic documented, all tooltips added

### Phase 5: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 4 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Label and Semantics Fixes
**Priority**: Critical (misleading labels are a fundamental issue)
**Estimated Time**: 8-10 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Rename "Brier Score" to "Time-Averaged In-Game Brier Error"
- **ID**: S1-E1-S1
- **Type**: Refactor
- **Priority**: Critical
- **Estimate**: 4-5 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (function names, docstrings, return dict keys)
  - `webapp/api/endpoints/aggregate_stats.py` (dict keys, logging messages)
  - `webapp/static/js/stats.js` (all references to "Brier Score" in labels, tooltips, chart titles)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] All occurrences of "Brier Score" renamed to "Time-Averaged In-Game Brier Error" in backend code
  - [ ] All occurrences of "Brier Score" renamed in frontend code
  - [ ] Chart title "ESPN Brier Score Distribution" changed to "ESPN Time-Averaged In-Game Brier Error Distribution"
  - [ ] All tooltips updated to say: "Computed by averaging (p_t - outcome)^2 over all probability updates within the game."
  - [ ] API responses maintain backward compatibility (old keys still present, new keys added)
  - [ ] All aggregate stats labels updated (Mean, Median, Std Dev, P25, P75, P90, P95, etc.)

- **Technical Context**:
  - **Current State**: 
    - Backend: `calculate_brier_score()` function exists, returns `brier_score` in dicts
    - Frontend: Displays "Brier Score (Mean)", "Brier Score (Median)", etc.
    - Chart: Title is "ESPN Brier Score Distribution"
  - **Required Changes**: 
    - Backend: Add new dict keys like `time_averaged_in_game_brier_error` alongside `brier_score` for backward compatibility
    - Frontend: Update all display labels and tooltips
    - Chart: Update chart title and tooltip
  - **Integration Points**: 
    - API endpoint `/api/games/{game_id}/stats` returns `espn_stats["brier_score"]`
    - API endpoint `/api/stats/aggregate` returns `espn["brier_score"]` and `kalshi["brier_score"]`
    - Frontend `stats.js` renders these values in cards and charts
  - **Data Structures**: 
    - Backend dicts: `{"brier_score": 0.15, ...}` → `{"brier_score": 0.15, "time_averaged_in_game_brier_error": 0.15, ...}`
    - Frontend: No data structure changes, only display labels
  - **API Contracts**: 
    - Maintain backward compatibility: old keys still present
    - New keys added for new naming

- **Implementation Steps**:
  1. **Backend - stats.py**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Modify `get_game_stats()` function
     - Content: Add `time_averaged_in_game_brier_error` key alongside `brier_score` in return dicts
     - Update docstrings to use new terminology
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Modify `get_aggregate_stats()` function
     - Content: Add `time_averaged_in_game_brier_error` key in `espn` and `kalshi` sections
     - Update variable names from `all_espn_brier_scores` to `all_espn_time_averaged_brier_errors` (for clarity, but keep old for now)
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Update all display labels
     - Content: Replace "Brier Score" with "Time-Averaged In-Game Brier Error" in:
       - Stat row labels (lines ~239, ~243, ~247, etc.)
       - Chart titles (line ~172)
       - Tooltip text
  4. **Frontend - stats.js chart rendering**: 
     - File: `webapp/static/js/stats.js`
     - Action: Update chart title
     - Content: Change "ESPN Brier Score Distribution" to "ESPN Time-Averaged In-Game Brier Error Distribution"

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/games/401810151/stats | jq '.espn_stats.time_averaged_in_game_brier_error'`
     - Expected Output: Numeric value (same as `brier_score`)
  2. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.espn.time_averaged_in_game_brier_error.mean'`
     - Expected Output: Numeric value
  3. **Frontend Visual Test**: Open aggregate stats page, verify all labels show "Time-Averaged In-Game Brier Error"
  4. **Frontend Chart Test**: Verify chart title shows new name
  5. **Tooltip Test**: Hover over metric, verify tooltip explains averaging over all updates

- **Definition of Done**:
  - [ ] All backend functions updated with new key names
  - [ ] All frontend labels updated
  - [ ] Chart titles updated
  - [ ] Tooltips updated with correct explanation
  - [ ] Backward compatibility maintained (old keys still work)
  - [ ] All validation steps pass

- **Rollback Plan**: 
  - Revert changes to `stats.py`, `aggregate_stats.py`, and `stats.js`
  - Old keys remain functional, so no data loss

- **Risk Assessment**: 
  - **Low Risk**: This is a labeling change, not a calculation change
  - **Mitigation**: Maintain backward compatibility with old keys

- **Success Metrics**: 
  - All labels updated correctly
  - No broken functionality
  - Tooltips provide clear explanations

#### Story 1.2: Rename "MAE" to "Mean Absolute Difference" (Complete)
- **ID**: S1-E1-S2
- **Type**: Refactor
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (already done - `mean_absolute_difference` exists)
  - `webapp/api/endpoints/aggregate_stats.py` (verify all references)
  - `webapp/static/js/stats.js` (verify all labels use correct name)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] All references to "Mean Absolute Error" or "MAE" changed to "Mean Absolute Difference (ESPN vs Kalshi)" - VERIFIED: Backend uses `mean_absolute_difference` (stats.py line 975), frontend uses full name (stats.js lines 404, 637, 944)
  - [x] Chart title "Mean Absolute Error Distribution" changed to "Absolute Difference Distribution (ESPN vs Kalshi)" - VERIFIED: Chart title updated (stats.js line 387 mentions "Absolute Difference Distribution")
  - [x] Tooltip explains: "Measures disagreement magnitude between sources, not correctness." - VERIFIED: Tooltip includes this explanation (stats.js line 637)
  - [x] All aggregate stats labels updated (Mean, Median, P25, P75, etc.) - VERIFIED: Labels use correct name (stats.js line 637)

- **Technical Context**:
  - **Current State**: 
    - Backend: Already uses `mean_absolute_difference` in `calculate_espn_kalshi_divergence()`
    - Frontend: May still have some "MAE" references
  - **Required Changes**: 
    - Verify all frontend labels use full name
    - Update chart title
    - Add/update tooltip
  - **Integration Points**: Same as Story 1.1
  - **Data Structures**: No changes needed
  - **API Contracts**: No changes needed

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Search for "MAE" or "Mean Absolute Error"
     - Content: Replace with "Mean Absolute Difference (ESPN vs Kalshi)"
  2. **Frontend - stats.js chart**: 
     - File: `webapp/static/js/stats.js`
     - Action: Update chart title
     - Content: Change to "Absolute Difference Distribution (ESPN vs Kalshi)"
  3. **Frontend - stats.js tooltip**: 
     - File: `webapp/static/js/stats.js`
     - Action: Update tooltip text
     - Content: Add explanation about disagreement, not correctness

- **Validation Steps**:
  1. **Frontend Visual Test**: Open aggregate stats page, verify all labels show full name
  2. **Frontend Chart Test**: Verify chart title shows new name
  3. **Tooltip Test**: Hover over metric, verify tooltip explains disagreement

- **Definition of Done**:
  - [ ] All frontend labels updated
  - [ ] Chart title updated
  - [ ] Tooltip updated
  - [ ] All validation steps pass

- **Rollback Plan**: Revert frontend changes only

- **Risk Assessment**: 
  - **Low Risk**: Labeling change only
  - **Mitigation**: Verify no broken references

- **Success Metrics**: 
  - All labels use correct terminology
  - Tooltip clearly explains the metric

#### Story 1.3: Add Correlation Tooltip
- **ID**: S1-E1-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add tooltip to correlation display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Tooltip added next to correlation metric - VERIFIED: Tooltips exist (stats.js lines 381, 599, 601)
  - [x] Tooltip text: "Correlation measures agreement in movement, not accuracy or betting edge." - VERIFIED: Tooltip includes this exact text (stats.js lines 381, 599, 601)

- **Technical Context**:
  - **Current State**: Correlation is displayed but may not have a tooltip
  - **Required Changes**: Add tooltip icon and content
  - **Integration Points**: Frontend display only
  - **Data Structures**: No changes
  - **API Contracts**: No changes

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Find correlation display location
     - Content: Add tooltip using `createTooltip()` function with specified text

- **Validation Steps**:
  1. **Frontend Visual Test**: Open aggregate stats page, verify tooltip appears next to correlation
  2. **Tooltip Test**: Hover over tooltip, verify correct text displays

- **Definition of Done**:
  - [ ] Tooltip added and displays correctly
  - [ ] Tooltip text matches specification

- **Rollback Plan**: Remove tooltip addition

- **Risk Assessment**: 
  - **Very Low Risk**: UI addition only
  - **Mitigation**: None needed

- **Success Metrics**: 
  - Tooltip displays correctly
  - Text is clear and helpful

### Epic 2: New Number Metrics
**Priority**: High (adds valuable diagnostic information)
**Estimated Time**: 12-16 hours
**Dependencies**: Must complete Epic 1
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Add Median Points/Game Metrics
- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1, S1-E1-S2, S1-E1-S3
- **Files to Modify**: 
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation logic)
  - `webapp/static/js/stats.js` (add display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Backend calculates median, P25, P75, and mean of aligned points per game - VERIFIED: Calculated in aggregate_stats.py (lines 924-929) with min/max also included
  - [x] Frontend displays these metrics in a "Data Coverage" section - VERIFIED: Displayed in summary cards and stats section (stats.js lines 302-307, 480+)
  - [x] Metrics show: "Median points/game", "P25 points/game", "P75 points/game", "Mean points/game" - VERIFIED: All metrics displayed with correct labels (stats.js lines 302-307, 480+)

- **Technical Context**:
  - **Current State**: 
    - Alignment happens in `get_aggregate_stats()` but point counts are not aggregated
    - Need to count aligned points per game, then compute statistics
  - **Required Changes**: 
    - Backend: Count aligned points for each game, store in list, compute median/P25/P75/mean
    - Frontend: Add new "Data Coverage" section with these metrics
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page display
  - **Data Structures**: 
    - Backend: `{"data_coverage": {"median_points_per_game": 450, "p25_points_per_game": 380, "p75_points_per_game": 520, "mean_points_per_game": 465}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Add point counting logic in game processing loop
     - Content: 
       ```python
       all_points_per_game = []
       # In game loop:
       aligned_count = len(aligned_data)  # Count aligned points
       all_points_per_game.append(aligned_count)
       # After loop:
       data_coverage = {
           "median_points_per_game": safe_median(all_points_per_game),
           "p25_points_per_game": safe_percentile(all_points_per_game, 25),
           "p75_points_per_game": safe_percentile(all_points_per_game, 75),
           "mean_points_per_game": safe_mean(all_points_per_game),
       }
       ```
  2. **Backend - aggregate_stats.py return dict**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Add `data_coverage` to return dict
     - Content: Include in top-level return dict
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add "Data Coverage" section
     - Content: Display median, P25, P75, mean with tooltips

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.data_coverage'`
     - Expected Output: Object with median, p25, p75, mean values
  2. **Frontend Visual Test**: Open aggregate stats page, verify "Data Coverage" section appears with correct values
  3. **Data Validation**: Verify median is between P25 and P75

- **Definition of Done**:
  - [ ] Backend calculates all metrics correctly
  - [ ] Frontend displays all metrics
  - [ ] Tooltips explain what each metric means
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and display code

- **Risk Assessment**: 
  - **Low Risk**: New metrics, doesn't affect existing functionality
  - **Mitigation**: Verify calculations with known data

- **Success Metrics**: 
  - Metrics display correctly
  - Values are reasonable (e.g., median between P25 and P75)

#### Story 2.2: Add Max Divergence Metrics
- **ID**: S1-E2-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (add calculation helper)
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation and aggregation)
  - `webapp/static/js/stats.js` (add display and optional chart)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Backend calculates max divergence per game (max_t abs(ESPN_p_t - Kalshi_p_t)) - VERIFIED: Calculated via `calculate_espn_kalshi_divergence()` which returns `max_absolute_difference` (stats.py line 975)
  - [x] Backend aggregates: mean, median, P75, P90 of max_divergence across games - VERIFIED: Aggregated in aggregate_stats.py (lines 875-882) with distribution included
  - [x] Frontend displays these metrics in numbers section - VERIFIED: Displayed in comparison section (stats.js lines 654-678)
  - [ ] Optional: Frontend displays histogram of max_divergence across games - NOT IMPLEMENTED: Distribution exists in backend but no histogram chart rendered

- **Technical Context**:
  - **Current State**: 
    - `calculate_espn_kalshi_divergence()` already calculates divergence at each timestamp
    - Need to extract max divergence per game
  - **Required Changes**: 
    - Backend: Add helper function to calculate max divergence from aligned data
    - Backend: Aggregate max divergences across games
    - Frontend: Display metrics and optional histogram
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"max_divergence": {"mean": 0.25, "median": 0.22, "p75": 0.30, "p90": 0.35, "distribution": [...]}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py helper**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add helper function
     - Content: 
       ```python
       def calculate_max_divergence(espn_probs: list[float], kalshi_probs: list[float]) -> float:
           """Calculate maximum absolute difference between ESPN and Kalshi probabilities."""
           if not espn_probs or not kalshi_probs or len(espn_probs) != len(kalshi_probs):
               return None
           return max(abs(espn - kalshi) for espn, kalshi in zip(espn_probs, kalshi_probs))
       ```
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate max divergence per game and aggregate
     - Content: 
       ```python
       all_max_divergences = []
       # In game loop:
       max_div = calculate_max_divergence(espn_home_probs, kalshi_home_probs)
       if max_div is not None:
           all_max_divergences.append(max_div)
       # After loop:
       max_divergence_stats = {
           "mean": safe_mean(all_max_divergences),
           "median": safe_median(all_max_divergences),
           "p75": safe_percentile(all_max_divergences, 75),
           "p90": safe_percentile(all_max_divergences, 90),
           "distribution": sorted(all_max_divergences) if all_max_divergences else [],
       }
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add display section
     - Content: Display mean, median, P75, P90 with tooltips
  4. **Frontend - stats.js (optional histogram)**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add histogram chart
     - Content: Use `createHistogram()` to display distribution

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.max_divergence'`
     - Expected Output: Object with mean, median, p75, p90, distribution
  2. **Frontend Visual Test**: Open aggregate stats page, verify metrics display
  3. **Data Validation**: Verify max divergence values are between 0 and 1

- **Definition of Done**:
  - [ ] Backend calculates max divergence correctly
  - [ ] Frontend displays all metrics
  - [ ] Optional histogram displays (if implemented)
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and display code

- **Risk Assessment**: 
  - **Low Risk**: New metric, doesn't affect existing functionality
  - **Mitigation**: Verify calculation logic with test data

- **Success Metrics**: 
  - Metrics display correctly
  - Values are reasonable (0-1 range)

#### Story 2.3: Add Sign Flip Count Metrics
- **ID**: S1-E2-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S2
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (add calculation helper)
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation and aggregation)
  - `webapp/static/js/stats.js` (add display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Backend calculates sign flip count per game (count of timestamps where ESPN and Kalshi move in opposite directions) - VERIFIED: Calculated in `calculate_espn_kalshi_divergence()` (stats.py lines 891-904) with epsilon threshold
  - [x] Uses epsilon threshold (0.005 or configurable) to filter noise - VERIFIED: Epsilon threshold of 0.005 used (stats.py line 894)
  - [x] Backend aggregates: mean, median, P75 across games - VERIFIED: Aggregated in aggregate_stats.py (lines 883-889) with total and max also included
  - [x] Frontend displays these metrics - VERIFIED: Displayed in comparison section (stats.js lines 660-680)

- **Technical Context**:
  - **Current State**: 
    - Alignment logic exists but doesn't track direction changes
    - Need to calculate deltas and compare signs
  - **Required Changes**: 
    - Backend: Add helper function to calculate sign flips
    - Backend: Aggregate sign flip counts
    - Frontend: Display metrics
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"sign_flips": {"mean": 12.5, "median": 11, "p75": 15, ...}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py helper**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add helper function
     - Content: 
       ```python
       def calculate_sign_flips(
           espn_probs: list[float], 
           kalshi_probs: list[float],
           epsilon: float = 0.005
       ) -> int:
           """Count sign flips: times when ESPN and Kalshi move in opposite directions."""
           if len(espn_probs) < 2 or len(kalshi_probs) < 2:
               return 0
           
           sign_flip_count = 0
           for i in range(1, len(espn_probs)):
               espn_delta = espn_probs[i] - espn_probs[i-1]
               kalshi_delta = kalshi_probs[i] - kalshi_probs[i-1]
               
               # Only count if both deltas exceed epsilon (filter noise)
               if abs(espn_delta) > epsilon and abs(kalshi_delta) > epsilon:
                   # Check if signs are opposite
                   if (espn_delta > 0 and kalshi_delta < 0) or (espn_delta < 0 and kalshi_delta > 0):
                       sign_flip_count += 1
           
           return sign_flip_count
       ```
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate sign flips per game and aggregate
     - Content: 
       ```python
       all_sign_flip_counts = []
       # In game loop:
       sign_flips = calculate_sign_flips(espn_home_probs, kalshi_home_probs)
       all_sign_flip_counts.append(sign_flips)
       # After loop:
       sign_flip_stats = {
           "mean": safe_mean(all_sign_flip_counts),
           "median": safe_median(all_sign_flip_counts),
           "p75": safe_percentile(all_sign_flip_counts, 75),
       }
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add display section
     - Content: Display mean, median, P75 with tooltips explaining sign flips

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.sign_flips'`
     - Expected Output: Object with mean, median, p75 values
  2. **Frontend Visual Test**: Open aggregate stats page, verify metrics display
  3. **Data Validation**: Verify sign flip counts are non-negative integers

- **Definition of Done**:
  - [ ] Backend calculates sign flips correctly
  - [ ] Epsilon threshold filters noise appropriately
  - [ ] Frontend displays all metrics
  - [ ] Tooltips explain what sign flips mean
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and display code

- **Risk Assessment**: 
  - **Medium Risk**: Logic for detecting sign flips needs careful testing
  - **Mitigation**: Test with known data where sign flips are obvious

- **Success Metrics**: 
  - Metrics display correctly
  - Sign flip detection works as expected

#### Story 2.4: Add Extreme Probability Rate Metrics
- **ID**: S1-E2-S4
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S3
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (add calculation helper)
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation and aggregation)
  - `webapp/static/js/stats.js` (add display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Backend calculates % of timestamps where p >= 0.95 or p <= 0.05 for ESPN - VERIFIED: Calculated via `calculate_extreme_probability_rate()` (aggregate_stats.py line 475)
  - [x] Backend calculates % of timestamps where p >= 0.95 or p <= 0.05 for Kalshi - VERIFIED: Calculated via `calculate_extreme_probability_rate()` (aggregate_stats.py line 522)
  - [x] Frontend displays both metrics with tooltips - VERIFIED: Displayed for ESPN (stats.js lines 537-540) and Kalshi (stats.js lines 577-580) with tooltips

- **Technical Context**:
  - **Current State**: 
    - Probability data is available but extreme rate is not calculated
  - **Required Changes**: 
    - Backend: Add helper function to calculate extreme probability rate
    - Backend: Calculate for ESPN and Kalshi separately
    - Frontend: Display both rates
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"extreme_probability_rate": {"espn": 0.15, "kalshi": 0.12}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py helper**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add helper function
     - Content: 
       ```python
       def calculate_extreme_probability_rate(probabilities: list[float]) -> float:
           """Calculate % of timestamps where p >= 0.95 or p <= 0.05."""
           if not probabilities:
               return None
           extreme_count = sum(1 for p in probabilities if p >= 0.95 or p <= 0.05)
           return extreme_count / len(probabilities)
       ```
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate extreme rates for ESPN and Kalshi
     - Content: 
       ```python
       # Aggregate across all games
       all_espn_extreme_rates = []
       all_kalshi_extreme_rates = []
       # In game loop:
       espn_extreme_rate = calculate_extreme_probability_rate(espn_home_probs)
       kalshi_extreme_rate = calculate_extreme_probability_rate(kalshi_home_probs)
       if espn_extreme_rate is not None:
           all_espn_extreme_rates.append(espn_extreme_rate)
       if kalshi_extreme_rate is not None:
           all_kalshi_extreme_rates.append(kalshi_extreme_rate)
       # After loop:
       extreme_probability_rate = {
           "espn": {
               "mean": safe_mean(all_espn_extreme_rates) if all_espn_extreme_rates else None,
               "median": safe_median(all_espn_extreme_rates) if all_espn_extreme_rates else None,
           },
           "kalshi": {
               "mean": safe_mean(all_kalshi_extreme_rates) if all_kalshi_extreme_rates else None,
               "median": safe_median(all_kalshi_extreme_rates) if all_kalshi_extreme_rates else None,
           }
       }
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add display section
     - Content: Display ESPN and Kalshi extreme rates with tooltips

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.extreme_probability_rate'`
     - Expected Output: Object with espn and kalshi values (0-1 range)
  2. **Frontend Visual Test**: Open aggregate stats page, verify metrics display
  3. **Data Validation**: Verify rates are between 0 and 1

- **Definition of Done**:
  - [ ] Backend calculates extreme rates correctly
  - [ ] Frontend displays both metrics
  - [ ] Tooltips explain what extreme probability rate means
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and display code

- **Risk Assessment**: 
  - **Low Risk**: Simple calculation
  - **Mitigation**: Verify with test data

- **Success Metrics**: 
  - Metrics display correctly
  - Values are reasonable (0-1 range)

### Epic 3: Chart Enhancements
**Priority**: High (visualizations are critical for understanding)
**Estimated Time**: 16-20 hours
**Dependencies**: Must complete Epic 2
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Verify and Enhance Reliability Curves
- **ID**: S1-E3-S1
- **Type**: Feature/Refactor
- **Priority**: Critical
- **Estimate**: 5-6 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E2-S4
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (verify `calculate_reliability_curve` matches spec)
  - `webapp/api/endpoints/aggregate_stats.py` (verify aggregation logic)
  - `webapp/static/js/stats.js` (add chart rendering if not present)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [x] Reliability curve uses exactly 10 bins (0-0.1, 0.1-0.2, ..., 0.9-1.0) - VERIFIED: `calculate_reliability_curve()` uses `bins=10` (stats.py line 379, aggregate_stats.py lines 769, 846)
  - [x] Each bin has: x = mean predicted probability, y = empirical win rate, n = count - VERIFIED: Returns `predicted_prob`, `actual_freq`, `count` (stats.py lines 427-429)
  - [ ] Chart includes diagonal y=x reference line - NOT IMPLEMENTED: Chart rendering code missing - only HTML canvas elements exist (stats.js lines 323, 333), no `renderChart` calls found
  - [ ] Chart displays for ESPN and Kalshi separately - NOT IMPLEMENTED: Chart rendering code missing
  - [ ] Tooltip per bin shows: predicted_mean, actual_rate, n - NOT IMPLEMENTED: Chart rendering code missing
  - [x] Chart title: "ESPN Reliability Curve (All In-Game Updates)" and "Kalshi Reliability Curve (All In-Game Updates)" - VERIFIED: Titles exist in HTML (stats.js lines 320, 330)

- **Technical Context**:
  - **Current State**: 
    - `calculate_reliability_curve()` exists in `stats.py` and appears to match spec (10 bins)
    - Need to verify it's being used correctly in aggregate stats
    - Need to verify frontend chart rendering
  - **Required Changes**: 
    - Verify backend calculation matches spec exactly
    - Ensure frontend renders charts with diagonal line
    - Add tooltips
  - **Integration Points**: 
    - Backend: `get_aggregate_stats()` should call `calculate_reliability_curve()` for ESPN and Kalshi
    - Frontend: Render charts from reliability curve data
  - **Data Structures**: 
    - Backend: `{"bins": [{"bin_min": 0.0, "bin_max": 0.1, "predicted_prob": 0.05, "actual_freq": 0.06, "count": 150, ...}, ...]}`
  - **API Contracts**: 
    - Reliability curve data in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py verification**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Verify `calculate_reliability_curve()` matches spec
     - Content: Check that it uses 10 bins, calculates mean predicted prob and actual freq correctly
  2. **Backend - aggregate_stats.py verification**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Verify reliability curve is calculated for ESPN and Kalshi
     - Content: Check that all (probability, outcome) pairs are collected and passed to `calculate_reliability_curve()`
  3. **Frontend - stats.js chart rendering**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add/verify chart rendering for reliability curves
     - Content: 
       - Create scatter plot with bins as points
       - Add diagonal y=x line
       - Add tooltips showing predicted_mean, actual_rate, count
  4. **Frontend - stats.js chart titles**: 
     - File: `webapp/static/js/stats.js`
     - Action: Set chart titles
     - Content: "ESPN Reliability Curve (All In-Game Updates)" and "Kalshi Reliability Curve (All In-Game Updates)"

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.espn.reliability_curve.bins | length'`
     - Expected Output: 10
  2. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.espn.reliability_curve.bins[0]'`
     - Expected Output: Object with bin_min, bin_max, predicted_prob, actual_freq, count
  3. **Frontend Visual Test**: Open aggregate stats page, verify charts display with diagonal line
  4. **Frontend Tooltip Test**: Hover over chart points, verify tooltips show correct data

- **Definition of Done**:
  - [ ] Backend calculation matches spec exactly
  - [ ] Frontend charts render correctly
  - [ ] Diagonal reference line displays
  - [ ] Tooltips show correct data
  - [ ] Chart titles match specification
  - [ ] All validation steps pass

- **Rollback Plan**: Revert chart rendering changes

- **Risk Assessment**: 
  - **Medium Risk**: Chart rendering may have issues with Chart.js
  - **Mitigation**: Test with sample data first

- **Success Metrics**: 
  - Charts display correctly
  - Diagonal line is visible
  - Tooltips provide useful information

#### Story 3.2: Add Time-Sliced Performance Chart
- **ID**: S1-E3-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S1
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (verify `calculate_time_sliced_brier_scores` can be used for phases)
  - `webapp/api/endpoints/aggregate_stats.py` (add aggregation for time-sliced Brier)
  - `webapp/static/js/stats.js` (add chart rendering)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [x] Backend calculates time-averaged Brier for phases: Early (0-25%), Mid (25-75%), Late (75-100%), Clutch (last 2 minutes) - VERIFIED: `calculate_phase_brier_scores()` implements all phases (stats.py lines 121-201)
  - [x] Backend aggregates these across all games for ESPN and Kalshi - VERIFIED: Aggregated in aggregate_stats.py (lines 772-785)
  - [ ] Frontend displays line chart or grouped bar chart showing ESPN vs Kalshi by phase - NOT IMPLEMENTED: Chart rendering code missing - only HTML canvas element exists (stats.js line 344), no `renderChart` call found
  - [x] Chart title: "Brier by Game Phase (ESPN vs Kalshi)" - VERIFIED: Title exists in HTML (stats.js line 341)

- **Technical Context**:
  - **Current State**: 
    - `calculate_time_sliced_brier_scores()` exists but uses Q1/Halftime/Q4/Final2min
    - Need to adapt for Early/Mid/Late/Clutch phases
  - **Required Changes**: 
    - Backend: Add helper to calculate phase-based Brier (or adapt existing)
    - Backend: Aggregate phase Brier scores across games
    - Frontend: Render chart comparing ESPN vs Kalshi by phase
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add chart to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"brier_by_phase": {"espn": {"early": 0.15, "mid": 0.12, "late": 0.10, "clutch": 0.08}, "kalshi": {...}}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py helper**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add helper function for phase-based Brier
     - Content: 
       ```python
       def calculate_phase_brier_scores(
           probabilities: list[float],
           timestamps: list[int],
           game_start_timestamp: int,
           actual_outcome: int,
           game_duration_seconds: int
       ) -> dict[str, float]:
           """Calculate Brier for Early/Mid/Late/Clutch phases."""
           # Early: 0-25% of game
           # Mid: 25-75% of game
           # Late: 75-100% of game
           # Clutch: last 2 minutes
       ```
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate and aggregate phase Brier scores
     - Content: Calculate for each game, aggregate across games
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add chart rendering
     - Content: Line chart or grouped bar chart with phases on x-axis, Brier scores on y-axis, ESPN and Kalshi as separate series

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.brier_by_phase'`
     - Expected Output: Object with espn and kalshi, each with early, mid, late, clutch values
  2. **Frontend Visual Test**: Open aggregate stats page, verify chart displays
  3. **Data Validation**: Verify Brier scores are in 0-1 range

- **Definition of Done**:
  - [ ] Backend calculates phase Brier scores correctly
  - [ ] Frontend chart displays correctly
  - [ ] Chart title matches specification
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and chart rendering code

- **Risk Assessment**: 
  - **Medium Risk**: Phase calculation logic needs careful testing
  - **Mitigation**: Test with known game data

- **Success Metrics**: 
  - Chart displays correctly
  - Phase boundaries are correct
  - ESPN and Kalshi are clearly distinguished

#### Story 3.3: Improve Volatility Scatter Plot
- **ID**: S1-E3-S3
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 3-4 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S2
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (enhance scatter plot)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [x] Diagonal reference line (y=x) is displayed (already done per recent change) - VERIFIED: Diagonal line exists (stats.js lines 875-889)
  - [x] Points are colored by final margin buckets: 0-5 pts, 6-10, 11-20, 21+ - VERIFIED: Points grouped by margin buckets with different colors (stats.js lines 809-874)
  - [ ] Optional: Marginal histograms if Chart.js supports it - NOT IMPLEMENTED: Marginal histograms not added
  - [x] Chart remains interpretable - VERIFIED: Chart code shows proper legend and tooltips (stats.js lines 911-936)

- **Technical Context**:
  - **Current State**: 
    - Volatility scatter plot exists
    - Diagonal line was recently added
    - Points are currently dark purple (per user request)
  - **Required Changes**: 
    - Add color coding by final margin buckets
    - Optional: Add marginal histograms
  - **Integration Points**: 
    - Frontend: Modify chart rendering in `stats.js`
  - **Data Structures**: 
    - Backend: Already provides `final_margin` in scatter data
    - Frontend: Use `final_margin` to determine color
  - **API Contracts**: 
    - No changes needed (final_margin already in data)

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add color coding by margin buckets
     - Content: 
       ```javascript
       const getMarginColor = (margin) => {
           if (margin <= 5) return 'rgba(0, 100, 255, 0.6)'; // Blue: close game
           if (margin <= 10) return 'rgba(100, 150, 255, 0.6)'; // Light blue
           if (margin <= 20) return 'rgba(255, 150, 100, 0.6)'; // Orange
           return 'rgba(255, 50, 50, 0.6)'; // Red: blowout
       };
       ```
  2. **Frontend - stats.js (optional histograms)**: 
     - File: `webapp/static/js/stats.js`
     - Action: Research Chart.js support for marginal histograms
     - Content: If supported, add marginal histograms; if not, skip

- **Validation Steps**:
  1. **Frontend Visual Test**: Open aggregate stats page, verify scatter plot has colored points
  2. **Frontend Visual Test**: Verify diagonal line is still visible
  3. **Data Validation**: Verify colors match margin buckets

- **Definition of Done**:
  - [ ] Points are colored by margin buckets
  - [ ] Diagonal line is visible
  - [ ] Chart is interpretable
  - [ ] All validation steps pass

- **Rollback Plan**: Revert color coding changes

- **Risk Assessment**: 
  - **Low Risk**: Visual enhancement only
  - **Mitigation**: Test with sample data

- **Success Metrics**: 
  - Chart displays correctly
  - Colors help interpret the data
  - Diagonal line is clear

#### Story 3.4: Add Disagreement vs Outcome Chart
- **ID**: S1-E3-S4
- **Type**: Feature
- **Priority**: High
- **Estimate**: 4-5 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E3-S3
- **Files to Modify**: 
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation logic)
  - `webapp/static/js/stats.js` (add chart rendering)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [x] Backend calculates signed difference d_t = ESPN_p_t - Kalshi_p_t for each aligned observation - VERIFIED: Calculated in aggregate_stats.py (line 585)
  - [x] Backend bins d_t into buckets (e.g., [-0.30,-0.20), ..., [0.20,0.30]) - VERIFIED: Binned in Step 6.5 (aggregate_stats.py lines 608-626)
  - [x] For each bin, backend calculates home_win_rate and count - VERIFIED: Calculated for each bin (aggregate_stats.py lines 619-625)
  - [ ] Frontend displays chart: x-axis = signed difference bin, y-axis = actual home win rate - NOT IMPLEMENTED: Chart rendering code missing - only HTML canvas element exists (stats.js line 355), no `renderChart` call found
  - [x] Chart title: "Outcome Rate vs ESPN–Kalshi Disagreement" - VERIFIED: Title exists in HTML (stats.js line 352)

- **Technical Context**:
  - **Current State**: 
    - Alignment data exists but disagreement vs outcome is not calculated
  - **Required Changes**: 
    - Backend: Add calculation logic for binned disagreement and outcome rates
    - Frontend: Render chart
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add chart to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"disagreement_vs_outcome": [{"bin_min": -0.30, "bin_max": -0.20, "home_win_rate": 0.45, "count": 120, ...}, ...]}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Add calculation logic
     - Content: 
       ```python
       # Collect all (disagreement, outcome) pairs
       disagreement_outcome_pairs = []
       # In game loop:
       for espn_p, kalshi_p, outcome in zip(espn_home_probs, kalshi_home_probs, outcomes):
           disagreement = espn_p - kalshi_p  # Signed difference
           disagreement_outcome_pairs.append((disagreement, outcome))
       
       # Bin disagreements and calculate win rates
       bins = [(-0.30, -0.20), (-0.20, -0.10), ..., (0.20, 0.30)]
       binned_data = []
       for bin_min, bin_max in bins:
           pairs_in_bin = [(d, o) for d, o in disagreement_outcome_pairs if bin_min <= d < bin_max]
           if pairs_in_bin:
               home_win_rate = sum(o for _, o in pairs_in_bin) / len(pairs_in_bin)
               binned_data.append({"bin_min": bin_min, "bin_max": bin_max, "home_win_rate": home_win_rate, "count": len(pairs_in_bin)})
       ```
  2. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add chart rendering
     - Content: Bar chart or line chart with bins on x-axis, home_win_rate on y-axis

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.disagreement_vs_outcome'`
     - Expected Output: Array of bin objects with home_win_rate and count
  2. **Frontend Visual Test**: Open aggregate stats page, verify chart displays
  3. **Data Validation**: Verify home_win_rate values are between 0 and 1

- **Definition of Done**:
  - [ ] Backend calculates binned data correctly
  - [ ] Frontend chart displays correctly
  - [ ] Chart title matches specification
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and chart rendering code

- **Risk Assessment**: 
  - **Medium Risk**: Binning logic needs careful testing
  - **Mitigation**: Test with known data

- **Success Metrics**: 
  - Chart displays correctly
  - Bins are reasonable
  - Home win rates are calculated correctly

### Epic 4: Decision-Weighted Scoring and Final Polish
**Priority**: High (betting-relevant metrics are critical)
**Estimated Time**: 8-12 hours
**Dependencies**: Must complete Epic 3
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Implement Decision-Weighted Brier Variants
- **ID**: S1-E4-S1
- **Type**: Feature/Refactor
- **Priority**: Critical
- **Estimate**: 5-6 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E3-S4
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (verify/update `calculate_decision_weighted_metrics`)
  - `webapp/api/endpoints/aggregate_stats.py` (add aggregation)
  - `webapp/static/js/stats.js` (add display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Variant 1 (Confidence-weighted): w_t = abs(p_t - 0.5) implemented - VERIFIED: Implemented in `calculate_decision_weighted_metrics()` (stats.py lines 537-557)
  - [x] Variant 2 (Market-actionable): Only include timestamps where Kalshi bid/ask exists (already partially implemented) - VERIFIED: Filters to active points with bid/ask (stats.py lines 490-497)
  - [x] Backend calculates weighted Brier for ESPN and Kalshi for both variants - VERIFIED: Both variants calculated (stats.py lines 515-557)
  - [x] Backend aggregates across games - VERIFIED: Aggregated in aggregate_stats.py (lines 895-904)
  - [x] Frontend displays: "Decision-Weighted Brier (Confidence-Weighted)" and "Decision-Weighted Brier (Market-Actionable)" - VERIFIED: Displayed with correct labels (stats.js lines 707-728)
  - [x] Tooltips explain weighting exactly - VERIFIED: Tooltips explain both variants (stats.js lines 707-728)

- **Technical Context**:
  - **Current State**: 
    - `calculate_decision_weighted_metrics()` exists but may not match spec exactly
    - Need to verify and potentially refactor to match spec
  - **Required Changes**: 
    - Backend: Verify/update decision-weighted calculation to match spec
    - Backend: Add confidence-weighted variant
    - Backend: Ensure market-actionable variant only uses points with bid/ask
    - Frontend: Display both variants
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"decision_weighted_brier": {"confidence_weighted": {"espn": 0.12, "kalshi": 0.10}, "market_actionable": {"espn": 0.11, "kalshi": 0.09}}}`
  - **API Contracts**: 
    - New/updated section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py verification**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Verify `calculate_decision_weighted_metrics()` matches spec
     - Content: Check that it implements both variants correctly
  2. **Backend - stats.py update (if needed)**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add confidence-weighted variant if not present
     - Content: 
       ```python
       # Confidence-weighted: w_t = abs(p_t - 0.5)
       confidence_weights = [abs(p - 0.5) for p in probabilities]
       weighted_brier = sum(w * (p - outcome)**2 for w, p in zip(confidence_weights, probabilities)) / sum(confidence_weights)
       ```
  3. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate and aggregate decision-weighted Brier
     - Content: Calculate for each game, aggregate across games
  4. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add display section
     - Content: Display both variants with tooltips

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.decision_weighted_brier'`
     - Expected Output: Object with confidence_weighted and market_actionable, each with espn and kalshi
  2. **Frontend Visual Test**: Open aggregate stats page, verify metrics display
  3. **Data Validation**: Verify Brier scores are in 0-1 range

- **Definition of Done**:
  - [ ] Both variants are implemented correctly
  - [ ] Frontend displays both variants
  - [ ] Tooltips explain weighting
  - [ ] All validation steps pass

- **Rollback Plan**: Revert calculation and display code

- **Risk Assessment**: 
  - **Medium Risk**: Weighting logic needs careful verification
  - **Mitigation**: Test with known data

- **Success Metrics**: 
  - Metrics display correctly
  - Weighting logic is correct
  - Tooltips are clear

#### Story 4.2: Add Profit Proxy Metrics (Optional)
- **ID**: S1-E4-S2
- **Type**: Feature
- **Priority**: Low (optional if time permits)
- **Estimate**: 3-4 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S1
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (add calculation helper)
  - `webapp/api/endpoints/aggregate_stats.py` (add calculation)
  - `webapp/static/js/stats.js` (add display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Backend calculates signal events (abs(edge) >= threshold, e.g., 0.05) - VERIFIED: `calculate_profit_proxy()` implemented (stats.py lines 622-700) with threshold=0.05
  - [x] Backend tracks: count of signal events, win rate when edge > +threshold, win rate when edge < -threshold - VERIFIED: All three metrics calculated and aggregated (aggregate_stats.py lines 915-919)
  - [ ] Frontend displays these metrics - NOT IMPLEMENTED: No frontend display found - profit_proxy not displayed in stats.js
  - [ ] Tooltip explains this is a sanity check, not a full backtest - NOT IMPLEMENTED: Frontend display missing

- **Technical Context**:
  - **Current State**: 
    - Edge calculation is not implemented
  - **Required Changes**: 
    - Backend: Add profit proxy calculation
    - Frontend: Display metrics
  - **Integration Points**: 
    - Backend: Add to `get_aggregate_stats()` return dict
    - Frontend: Add to aggregate stats page
  - **Data Structures**: 
    - Backend: `{"profit_proxy": {"signal_event_count": 1250, "win_rate_positive_edge": 0.58, "win_rate_negative_edge": 0.42}}`
  - **API Contracts**: 
    - New section in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py helper**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add helper function
     - Content: 
       ```python
       def calculate_profit_proxy(
           espn_probs: list[float],
           kalshi_probs: list[float],
           outcomes: list[int],
           threshold: float = 0.05
       ) -> dict[str, Any]:
           """Calculate profit proxy metrics (sanity check, not full backtest)."""
           signal_events = []
           for espn, kalshi, outcome in zip(espn_probs, kalshi_probs, outcomes):
               edge = espn - kalshi
               if abs(edge) >= threshold:
                   signal_events.append((edge, outcome))
           
           positive_edge_events = [(e, o) for e, o in signal_events if e > 0]
           negative_edge_events = [(e, o) for e, o in signal_events if e < 0]
           
           return {
               "signal_event_count": len(signal_events),
               "win_rate_positive_edge": sum(o for _, o in positive_edge_events) / len(positive_edge_events) if positive_edge_events else None,
               "win_rate_negative_edge": sum(o for _, o in negative_edge_events) / len(negative_edge_events) if negative_edge_events else None,
           }
       ```
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate and aggregate profit proxy
     - Content: Calculate for each game, aggregate across games
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add display section
     - Content: Display metrics with tooltip explaining it's a sanity check

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.profit_proxy'`
     - Expected Output: Object with signal_event_count, win_rate_positive_edge, win_rate_negative_edge
  2. **Frontend Visual Test**: Open aggregate stats page, verify metrics display
  3. **Data Validation**: Verify win rates are between 0 and 1

- **Definition of Done**:
  - [ ] Backend calculates profit proxy correctly
  - [ ] Frontend displays metrics
  - [ ] Tooltip explains it's a sanity check
  - [ ] All validation steps pass

- **Rollback Plan**: Remove calculation and display code

- **Risk Assessment**: 
  - **Low Risk**: Optional feature, can be skipped if time is short
  - **Mitigation**: Mark as optional, implement only if time permits

- **Success Metrics**: 
  - Metrics display correctly
  - Tooltip is clear about limitations

#### Story 4.3: Document Alignment Window Logic
- **ID**: S1-E4-S3
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S2 (or skip if S1-E4-S2 is skipped)
- **Files to Modify**: 
  - `webapp/api/endpoints/stats.py` (add docstring)
  - `webapp/api/endpoints/aggregate_stats.py` (add docstring)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Alignment window logic is documented in code - VERIFIED: Comprehensive docstring in `calculate_espn_kalshi_divergence()` (stats.py lines 834-897) explaining 60-second window
  - [ ] Alignment rate (aligned_points / total_possible_points) is calculated and displayed - PARTIAL: Data coverage metrics exist (median_points_per_game, etc.) but no explicit "alignment_rate" field calculated or displayed
  - [x] Documentation explains the window size (e.g., 3-10 seconds) - VERIFIED: Docstring explains 60-second window (stats.py line 848)

- **Technical Context**:
  - **Current State**: 
    - Alignment logic exists but may not be well-documented
  - **Required Changes**: 
    - Add docstrings explaining alignment window
    - Calculate and display alignment rate
  - **Integration Points**: 
    - Backend: Add alignment rate to aggregate stats
    - Frontend: Display alignment rate
  - **Data Structures**: 
    - Backend: `{"alignment_rate": 0.95}` (95% of points aligned)
  - **API Contracts**: 
    - New field in aggregate stats response

- **Implementation Steps**:
  1. **Backend - stats.py/docstrings**: 
     - File: `webapp/api/endpoints/stats.py`
     - Action: Add docstring to alignment function
     - Content: Explain window size and matching logic
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Calculate alignment rate
     - Content: 
       ```python
       total_possible_points = len(espn_probs)  # Or sum of ESPN and Kalshi points
       aligned_points = len(aligned_data)
       alignment_rate = aligned_points / total_possible_points if total_possible_points > 0 else 0
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Display alignment rate
     - Content: Show as percentage with tooltip

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.alignment_rate'`
     - Expected Output: Number between 0 and 1
  2. **Frontend Visual Test**: Open aggregate stats page, verify alignment rate displays
  3. **Documentation Test**: Read docstrings, verify they explain alignment logic

- **Definition of Done**:
  - [ ] Alignment logic is documented
  - [ ] Alignment rate is calculated and displayed
  - [ ] Documentation is clear
  - [ ] All validation steps pass

- **Rollback Plan**: Remove alignment rate calculation

- **Risk Assessment**: 
  - **Very Low Risk**: Documentation and display only
  - **Mitigation**: None needed

- **Success Metrics**: 
  - Documentation is clear
  - Alignment rate displays correctly

#### Story 4.4: Add Info Icons and Tooltips
- **ID**: S1-E4-S4
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S3
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add info icons)
  - `webapp/static/css/styles.css` (add icon styles if needed)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [x] Info icons added next to: Time-Averaged In-Game Brier Error, Mean Absolute Difference, Reliability curves - VERIFIED: Tooltips exist using `createTooltip()` function throughout stats.js
  - [x] Tooltips provide clear explanations in plain language - VERIFIED: All tooltips use plain language explanations (e.g., stats.js lines 367, 637, 320, 330)
  - [x] Icons are visually consistent - VERIFIED: All use same `createTooltip()` function for consistency

- **Technical Context**:
  - **Current State**: 
    - Some tooltips exist but may not have icons
    - Need to ensure all specified metrics have tooltips
  - **Required Changes**: 
    - Add info icons next to specified metrics
    - Ensure tooltips are clear and helpful
  - **Integration Points**: 
    - Frontend: Add icons to aggregate stats page
  - **Data Structures**: 
    - No changes
  - **API Contracts**: 
    - No changes

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add info icons next to specified metrics
     - Content: Use existing `createTooltip()` function or add icons manually
  2. **Frontend - css/styles.css**: 
     - File: `webapp/static/css/styles.css`
     - Action: Add icon styles if needed
     - Content: Ensure icons are visible and consistent

- **Validation Steps**:
  1. **Frontend Visual Test**: Open aggregate stats page, verify info icons appear
  2. **Frontend Tooltip Test**: Hover over icons, verify tooltips display
  3. **Content Test**: Verify tooltip text is clear and helpful

- **Definition of Done**:
  - [ ] Info icons are added
  - [ ] Tooltips are clear and helpful
  - [ ] Icons are visually consistent
  - [ ] All validation steps pass

- **Rollback Plan**: Remove icon additions

- **Risk Assessment**: 
  - **Very Low Risk**: UI enhancement only
  - **Mitigation**: None needed

- **Success Metrics**: 
  - Icons display correctly
  - Tooltips are helpful
  - UI is consistent

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: SPRINT-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] **Backend documentation** updated if backend changes were made
  - [ ] **API documentation** updated if API changes were made
  - [ ] **Frontend documentation** updated if frontend changes were made
  - [ ] **Architecture documentation** updated if architectural changes were made
  - [ ] **User documentation** updated if user-facing features were changed

- **Technical Context**:
  - **Current State**: Documentation may be out of date
  - **Required Changes**: Update all relevant documentation
  - **Integration Points**: All documentation files

- **Implementation Steps**: Update documentation as needed

- **Validation Steps**: Verify documentation is complete and accurate

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: SPRINT-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [x] **Linting**: All linting checks pass with zero errors and zero warnings - VERIFIED: `read_lints` tool shows no errors
  - [ ] **Type Checking**: All type checking passes with zero errors - NOT VERIFIED: No type checking tool run
  - [ ] **Build Process**: Build process completes without errors - NOT VERIFIED: No build process run
  - [ ] **Code Formatting**: Code formatting is consistent - NOT VERIFIED: No formatting check run
  - [ ] **All acceptance criteria from previous stories verified as complete** - PARTIAL: See detailed verification above - some items incomplete

- **Technical Context**:
  - **Current State**: Code may have linting errors
  - **Required Changes**: Fix any linting/type errors
  - **Quality Gates**: Linting, type checking, build

- **Implementation Steps**: Run quality checks and fix any issues

- **Validation Steps**: Verify all quality gates pass

### Story [FINAL]: Sprint Completion and Archive
- **ID**: SPRINT-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 5 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created - IN PROGRESS: This verification document serves as partial completion report
  - [ ] All sprint files organized - NOT VERIFIED: File organization not checked
  - [ ] Sprint marked as completed - NOT COMPLETE: Some acceptance criteria incomplete (see summary below)

- **Technical Context**:
  - **Current State**: Sprint in progress
  - **Required Changes**: Create completion report and organize files

- **Implementation Steps**: Create report, organize files, mark sprint as completed

- **Validation Steps**: Verify sprint is complete and documented

## Technical Decisions

### Design Pattern Analysis

#### Design Pattern: Service Pattern for Statistical Calculations
- **Category**: Architectural
- **Intent**: Separate statistical calculation logic from API endpoint logic for reusability and testability
- **Implementation**: Calculation functions in `stats.py` are pure functions that can be called from multiple endpoints
- **Benefits**: 
  - Code reuse across individual game stats and aggregate stats
  - Easier testing of calculation logic in isolation
  - Clear separation of concerns
- **Trade-offs**: 
  - Slight overhead from function calls
  - Need to ensure consistent function signatures
- **Rationale**: Statistical calculations are complex and used in multiple places, so centralizing them improves maintainability

#### Design Pattern: Batch Processing Pattern
- **Category**: Architectural
- **Intent**: Process multiple games in batch queries instead of N+1 queries for performance
- **Implementation**: `aggregate_stats.py` fetches all ESPN and Kalshi data in large batch queries, then processes in memory
- **Benefits**: 
  - 10-100x performance improvement over N+1 queries
  - Reduced database load
  - Better scalability
- **Trade-offs**: 
  - Higher memory usage (loads all data at once)
  - More complex code
- **Rationale**: Aggregate stats need to process hundreds of games, so batch processing is essential for performance

### Algorithm Analysis

#### Algorithm: Reliability Curve Binning
- **Type**: Statistical Aggregation
- **Complexity**: Time O(n), Space O(b) where n = number of observations, b = number of bins (10)
- **Description**: Groups probability predictions into 10 bins (0-0.1, 0.1-0.2, ..., 0.9-1.0), calculates mean predicted probability and actual outcome frequency for each bin
- **Use Case**: Evaluates calibration of probability predictions (how well predicted probabilities match actual frequencies)
- **Performance**: Linear time complexity, efficient for large datasets

#### Algorithm: Sign Flip Detection
- **Type**: Time Series Analysis
- **Complexity**: Time O(n), Space O(1) where n = number of aligned data points
- **Description**: Compares consecutive deltas of ESPN and Kalshi probabilities, counts instances where they move in opposite directions (with noise threshold)
- **Use Case**: Identifies moments where ESPN and Kalshi disagree on direction, potentially indicating edge opportunities
- **Performance**: Single pass through data, very efficient

#### Algorithm: Decision-Weighted Brier
- **Type**: Weighted Statistical Aggregation
- **Complexity**: Time O(n), Space O(n) where n = number of data points
- **Description**: Calculates Brier score but weights each timestamp by a decision-relevant factor (confidence distance from 0.5, or market activity)
- **Use Case**: Evaluates prediction accuracy when "money is at stake" rather than on average
- **Performance**: Linear time complexity, requires storing weights

### Design Decision Analysis

#### Design Decision: Backward Compatibility for Metric Renames
- **Problem**: Renaming metrics (e.g., "Brier Score" to "Time-Averaged In-Game Brier Error") could break existing API consumers
- **Context**: Dashboard is actively used, and API responses are consumed by frontend
- **Project Scope**: Single developer, small user base, but want to avoid breaking changes
- **Options**: 
  1. **Replace old keys entirely** (breaking change)
  2. **Add new keys, keep old keys** (backward compatible)
  3. **Version API** (complex, overkill for this project)
- **Selected**: Option 2 - Add new keys alongside old keys

**Option 2: Add New Keys, Keep Old Keys (CHOSEN)**
- **Design Pattern**: Adapter Pattern (providing both old and new interfaces)
- **Algorithm**: Simple key duplication in return dicts
- **Implementation Complexity**: Low (2-3 hours)
- **Maintenance Overhead**: Low (old keys can be deprecated later)
- **Scalability**: Good (doesn't affect performance)
- **Cost-Benefit**: Low cost, High benefit (no breaking changes)
- **Over-Engineering Risk**: None (simple solution)
- **Selected**: Maintains backward compatibility while allowing frontend to use new names

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 2-3 hours (adding new keys to return dicts)
- **Learning Curve**: 0 hours (straightforward)
- **Configuration Effort**: 0 hours (no configuration needed)

**Maintenance Cost**:
- **Monitoring**: 0 hours (no monitoring needed)
- **Updates**: 0 hours (no updates needed)
- **Debugging**: 0 hours (simple implementation)

**Performance Benefit**:
- **Response Time**: 0% change (no performance impact)
- **Throughput**: 0x change (no throughput impact)
- **Resource Efficiency**: No change (minimal memory overhead for duplicate keys)

**Maintainability Benefit**:
- **Code Quality**: Slight increase in dict size, but improves clarity
- **Developer Productivity**: No impact
- **System Reliability**: Prevents breaking changes

**Risk Cost**:
- **Risk 1**: Low risk - old keys remain functional, mitigated by keeping both
- **Risk 2**: None - no breaking changes

**Over-Engineering Prevention**:
- **Problem Complexity**: Low (simple rename)
- **Solution Complexity**: Low (key duplication)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Old keys can be deprecated in future if needed

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ (simple solution for small project)
- **Team Capability**: ✅ (straightforward implementation)
- **Timeline Constraints**: ✅ (quick to implement)
- **Future Growth**: ✅ (can deprecate old keys later)
- **Technical Debt**: ✅ (minimal, can clean up later)

**Chosen Solution**: Add new keys alongside old keys in API responses. Frontend will use new keys, but old keys remain for backward compatibility.

**Pros and Cons Analysis**:

**Pros**:
- **Reliability**: No breaking changes, existing consumers continue to work
- **Maintainability**: Clear migration path (frontend uses new keys, old keys deprecated later)
- **Scalability**: No performance impact
- **Reliability**: Prevents production issues from breaking changes

**Cons**:
- **Complexity**: Slight increase in response size (duplicate keys)
- **Learning Curve**: None
- **Migration Effort**: None (automatic)
- **Resource Usage**: Minimal memory overhead

**Risk Assessment**: 
- **Very Low Risk**: Simple key duplication, no logic changes
- **Mitigation**: None needed

**Trade-off Analysis**: 
- **Sacrificed**: Slight response size increase (minimal)
- **Gained**: Backward compatibility, no breaking changes, smooth migration path
- **Net Benefit**: High (maintains compatibility while allowing improvements)

## Testing Strategy

### Testing Approach
- **Unit Tests**: Not currently implemented; manual testing only
- **Integration Tests**: Not currently implemented; manual API testing
- **E2E Tests**: Not currently implemented; manual frontend testing
- **Performance Tests**: Not currently implemented; manual observation of aggregate stats calculation time

**Note**: This sprint focuses on implementing features. Testing will be manual validation of API responses and frontend displays.

## Deployment Plan
- **Pre-Deployment**: 
  - Verify all API endpoints return expected data
  - Verify frontend displays all new metrics and charts
  - Verify tooltips display correctly
- **Deployment Steps**: 
  - Deploy backend changes
  - Deploy frontend changes
  - Clear cache if needed
- **Post-Deployment**: 
  - Verify aggregate stats page loads correctly
  - Verify all new metrics display
  - Verify all charts render correctly
- **Rollback Plan**: 
  - Revert code changes
  - Clear cache
  - Verify old functionality still works

## Risk Assessment
- **Technical Risks**: 
  - **Risk 1**: Chart.js may not support all required chart types (e.g., marginal histograms)
    - **Mitigation**: Research Chart.js capabilities first, use alternatives if needed
  - **Risk 2**: Alignment window logic may need adjustment
    - **Mitigation**: Test with known data, document window size clearly
  - **Risk 3**: Decision-weighted calculation logic may be complex
    - **Mitigation**: Test thoroughly with known data, add detailed comments
- **Business Risks**: 
  - **Risk 1**: New metrics may be confusing to users
    - **Mitigation**: Add comprehensive tooltips explaining each metric
  - **Risk 2**: Performance may degrade with new calculations
    - **Mitigation**: Use batch queries, cache results, monitor performance
- **Resource Risks**: 
  - **Risk 1**: Time estimates may be optimistic
    - **Mitigation**: Mark optional features (profit proxy) as low priority, can skip if time is short

## Success Metrics
- **Technical**: 
  - All metric labels are semantically correct
  - All new metrics calculate correctly
  - All charts render without errors
  - API responses are valid JSON
  - Frontend displays all metrics and charts
- **Business**: 
  - Dashboard is defensible to data scientists
  - Metrics are betting-relevant
  - Tooltips provide clear explanations
  - Users can understand and use the dashboard effectively
- **Sprint**: 
  - All stories completed according to acceptance criteria
  - All quality gates pass
  - Documentation is updated

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)
- [ ] All API endpoints return expected data
- [ ] All frontend displays work correctly
- [ ] All tooltips display correctly
- [ ] All charts render correctly

### Post-Sprint Quality Comparison
- **Test Results**: Manual testing only (no automated tests)
- **Linting Results**: Will be measured during quality gate validation
- **Code Coverage**: Not measured
- **Build Status**: Will be verified during quality gate validation
- **Overall Assessment**: Will be completed after sprint

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Acceptance Criteria Verification Summary

**Date Verified**: 2025-01-XX  
**Verification Method**: Direct code inspection using grep, read_file, and codebase_search tools

### Overall Completion Status

**Phase 1 (Label and Semantics Fixes)**: ✅ **100% Complete**
- Story 1.1: All criteria met
- Story 1.2: All criteria met  
- Story 1.3: All criteria met

**Phase 2 (New Number Metrics)**: ✅ **95% Complete**
- Story 2.1: All criteria met
- Story 2.2: All criteria met (optional histogram not implemented)
- Story 2.3: All criteria met
- Story 2.4: All criteria met

**Phase 3 (Chart Enhancements)**: ⚠️ **50% Complete**
- Story 3.1: Backend complete, frontend chart rendering **MISSING**
- Story 3.2: Backend complete, frontend chart rendering **MISSING**
- Story 3.3: All criteria met (marginal histograms optional, not implemented)
- Story 3.4: Backend complete, frontend chart rendering **MISSING**

**Phase 4 (Decision-Weighted Scoring)**: ⚠️ **75% Complete**
- Story 4.1: All criteria met
- Story 4.2: Backend complete, frontend display **MISSING**
- Story 4.3: Documentation complete, alignment rate calculation/display **MISSING**
- Story 4.4: All criteria met

**Phase 5 (Quality Assurance)**: ⚠️ **Partial**
- Documentation: Partial (backend docstrings added, other docs not verified)
- Quality Gates: Linting passes, other checks not run
- Sprint Completion: In progress

### Critical Missing Items

1. **Chart Rendering Code Missing** (Story 3.1, 3.2, 3.4):
   - HTML canvas elements exist for:
     - `espnReliabilityChart` (line 323)
     - `kalshiReliabilityChart` (line 333)
     - `phaseBrierChart` (line 344)
     - `disagreementOutcomeChart` (line 355)
   - **NO `renderChart()` calls found** for these charts
   - Backend data is available and correct
   - Frontend rendering code needs to be added

2. **Profit Proxy Frontend Display Missing** (Story 4.2):
   - Backend calculation complete (aggregate_stats.py lines 915-919)
   - Frontend display code missing from stats.js
   - No references to `profit_proxy` in frontend

3. **Alignment Rate Display Missing** (Story 4.3):
   - Documentation complete (stats.py docstring)
   - Data coverage metrics exist (median_points_per_game, etc.)
   - No explicit "alignment_rate" field calculated or displayed
   - Spec requires: `alignment_rate = aligned_points / total_possible_points`

4. **Max Divergence Histogram Optional** (Story 2.2):
   - Distribution data exists in backend
   - Histogram chart not rendered (optional, so acceptable)

### Files Requiring Additional Work

1. **webapp/static/js/stats.js**:
   - Add `renderChart()` calls for reliability curves (lines ~960+)
   - Add `renderChart()` call for phase brier chart (lines ~960+)
   - Add `renderChart()` call for disagreement outcome chart (lines ~960+)
   - Add profit proxy display section (after line 750)
   - Consider adding `renderReliabilityCurve()` helper function

2. **webapp/api/endpoints/aggregate_stats.py**:
   - Add explicit `alignment_rate` calculation (if desired per spec)
   - Currently only has data_coverage metrics

### Verification Notes

- All backend calculations verified against code
- All frontend HTML structure verified
- Chart rendering code verified missing for 3 charts
- Profit proxy backend verified, frontend missing
- Tooltips and labels verified complete
- Backward compatibility verified maintained

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

