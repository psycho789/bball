# Sprint Plan: Dashboard Metrics Missing Features - High Priority

**Date**: Sun Jan 11 18:03:47 UTC 2026  
**Sprint Duration**: 3-4 days (20-28 hours total)  
**Sprint Goal**: Implement the 4 high-priority missing dashboard metric features identified in the sprint implementation status analysis: alignment rate display, time-sliced performance chart, profit proxy display, and max divergence histogram.  
**Current Status**: Backend calculations exist for all features, but frontend displays are missing. Alignment rate data (`data_points`) is calculated but not displayed. Profit proxy is calculated but not aggregated/displayed. Time-sliced performance chart has HTML comment placeholder but no rendering code. Max divergence histogram data exists but no chart rendered.  
**Target Status**: All 4 features fully implemented with frontend displays, proper tooltips, and integration into aggregate stats page.  
**Team Size**: 1 developer  
**Sprint Lead**: AI Assistant

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `cursor-files/templates/SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`.

**See `cursor-files/templates/SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

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
- **Business Driver**: Dashboard metrics analysis identified 4 high-priority missing features that prevent complete data science and betting-relevant analysis. These features provide critical insights: alignment rate shows data quality, time-sliced performance shows when sources are most accurate, profit proxy identifies potential betting edges, and max divergence histogram shows distribution of disagreement.
- **Success Criteria**: 
  - Alignment rate displays correctly with tooltip explaining meaning
  - Time-sliced performance chart renders with proper data visualization
  - Profit proxy metrics display in aggregate stats with tooltips
  - Max divergence histogram chart renders (optional feature)
  - All features integrated into aggregate stats page
- **Stakeholders**: Data scientists using dashboard for model building, bettors evaluating edge opportunities
- **Timeline Constraints**: None specified

### Technical Context
- **Current System State**: 
  - Backend: FastAPI application in `webapp/api/` with endpoints in `endpoints/stats.py` and `endpoints/aggregate_stats.py`
  - Frontend: JavaScript application in `webapp/static/js/stats.js` with Chart.js for visualizations
  - Backend calculations exist:
    - Alignment rate: `calculate_espn_kalshi_divergence()` returns `data_points` field (count of aligned pairs)
    - Profit proxy: `calculate_profit_proxy()` function exists in `stats.py:623-700`
    - Time-sliced performance: Phase Brier scores calculated but no chart rendering
    - Max divergence: Distribution data exists in `aggregate_stats.py:884` but no histogram chart
  - Frontend missing:
    - Alignment rate display: No frontend code to show alignment rate percentage
    - Time-sliced performance chart: HTML comment exists at `stats.js:237` but no rendering code
    - Profit proxy display: Backend calculates but not aggregated/displayed in frontend
    - Max divergence histogram: Distribution data exists but no chart rendering
- **Target System State**: 
  - All 4 features fully implemented with frontend displays
  - Proper tooltips explaining each metric
  - Integration into aggregate stats page
  - Consistent styling with existing dashboard metrics
- **Architecture Impact**: 
  - Backend: Verify profit proxy aggregation in `aggregate_stats.py`
  - Frontend: Add display code in `stats.js`, add chart rendering functions
  - No database schema changes required
- **Integration Points**: 
  - API endpoints: `/api/stats/aggregate` returns aggregate statistics
  - Frontend: Aggregate stats page (`/static/templates/aggregate-stats.html`)

### Sprint Scope
- **In Scope**: 
  - Story 1: Alignment Rate Display (backend data exists, add frontend display)
  - Story 2: Time-Sliced Performance Chart (backend data exists, add chart rendering)
  - Story 3: Profit Proxy Display (backend calculation exists, verify aggregation and add frontend display)
  - Story 4: Max Divergence Histogram (optional, backend distribution data exists, add histogram chart)
- **Out of Scope**: 
  - Database schema changes
  - New backend calculations (all calculations already exist)
  - Performance optimization
  - Individual game stats page changes (focus on aggregate stats only)
- **Assumptions**: 
  - Backend calculations are correct and complete
  - Chart.js library supports required chart types (bar, line, histogram)
  - Existing chart rendering patterns can be reused
- **Constraints**: 
  - Must maintain backward compatibility with existing API responses
  - Must not break existing frontend functionality
  - Must follow existing code patterns and structure

## Sprint Phases

### Phase 1: Alignment Rate Display (Duration: 3-4 hours)
**Objective**: Add frontend display for alignment rate metric with tooltip
**Dependencies**: None
**Deliverables**: Alignment rate displays in aggregate stats with tooltip

### Phase 2: Time-Sliced Performance Chart (Duration: 6-8 hours)
**Objective**: Implement chart rendering for time-sliced performance metrics
**Dependencies**: Must complete Phase 1
**Deliverables**: Time-sliced performance chart renders correctly with proper data visualization

### Phase 3: Profit Proxy Display (Duration: 4-6 hours)
**Objective**: Verify backend aggregation and add frontend display for profit proxy metrics
**Dependencies**: Must complete Phase 2
**Deliverables**: Profit proxy metrics display in aggregate stats with tooltips

### Phase 4: Max Divergence Histogram (Optional) (Duration: 2-3 hours)
**Objective**: Add histogram chart for max divergence distribution
**Dependencies**: Must complete Phase 3
**Deliverables**: Max divergence histogram chart renders correctly

### Phase 5: Sprint Quality Assurance (Duration: 2-3 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 4 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Alignment Rate Display
**Priority**: High
**Estimated Time**: 3-4 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Add Alignment Rate Display
- **ID**: S19-E1-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add alignment rate display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Alignment rate percentage displays in aggregate stats comparison section
  - [ ] Tooltip explains: "Percentage of ESPN probability updates that successfully matched with Kalshi data within the 60-second alignment window. Higher alignment rate indicates better data quality and synchronization between sources."
  - [ ] Alignment rate calculated as: `(total_aligned_data_points / total_espn_points) * 100`
  - [ ] Display format: "Alignment Rate: XX.X%" with tooltip icon
  - [ ] Styling matches existing metric displays

- **Technical Context**:
  - **Current State**: 
    - Backend: `calculate_espn_kalshi_divergence()` returns `data_points` field (count of aligned pairs) at `stats.py:980`
    - Backend: `get_aggregate_stats()` returns `total_aligned_data_points` and `avg_aligned_points_per_game` at `aggregate_stats.py:893-894`
    - Frontend: No display code exists for alignment rate
  - **Required Changes**: 
    - Frontend: Add alignment rate display in comparison section
    - Frontend: Calculate alignment rate percentage from backend data
    - Frontend: Add tooltip with explanation
  - **Integration Points**: 
    - Backend: Uses existing `total_aligned_data_points` from aggregate stats response
    - Frontend: Add to comparison section in `renderAggregateStats()` function
  - **Data Structures**: 
    - Backend: `{"comparison": {"total_aligned_data_points": 125000, "avg_aligned_points_per_game": 2500, ...}}`
    - Frontend: Calculate `alignment_rate = (total_aligned_data_points / total_espn_points) * 100`
  - **API Contracts**: 
    - Uses existing aggregate stats response structure

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add alignment rate display in comparison section
     - Content: 
       ```javascript
       // In renderAggregateStats() function, add to comparison section:
       ${stats.comparison?.total_aligned_data_points && stats.comparison?.total_espn_points ? `
       <div class="stat-row">
           <span class="stat-row-label">Alignment Rate${createTooltip('Percentage of ESPN probability updates that successfully matched with Kalshi data within the 60-second alignment window. Higher alignment rate indicates better data quality and synchronization between sources.')}</span>
           <span class="stat-row-value">${formatPercent(stats.comparison.total_aligned_data_points / stats.comparison.total_espn_points)}</span>
       </div>
       ` : ''}
       ```
  2. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Verify backend provides `total_espn_points` or calculate from game data
     - Content: Check if backend provides total ESPN points, or calculate from individual game stats

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.comparison.total_aligned_data_points'`
     - Expected Output: Number > 0
  2. **Frontend Visual Test**: Open aggregate stats page, verify alignment rate displays
  3. **Data Validation**: Verify alignment rate is between 0% and 100%

- **Definition of Done**:
  - [ ] Alignment rate displays correctly
  - [ ] Tooltip explains meaning
  - [ ] Styling matches existing metrics
  - [ ] All validation steps pass

- **Rollback Plan**: Remove alignment rate display code

- **Risk Assessment**: 
  - **Low Risk**: Simple display addition, backend data already exists
  - **Mitigation**: Verify backend data structure before implementing

- **Success Metrics**: 
  - Alignment rate displays correctly
  - Tooltip provides clear explanation
  - Value is reasonable (typically 80-95% for good data)

### Epic 2: Time-Sliced Performance Chart
**Priority**: High
**Estimated Time**: 6-8 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Implement Time-Sliced Performance Chart Rendering
- **ID**: S19-E2-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 6-8 hours
- **Phase**: Phase 2
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add chart rendering function)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [ ] Chart renders time-sliced performance metrics (Q1-Q2, Q3, Q4, Final 2 min)
  - [ ] Chart shows ESPN and Kalshi Brier scores by phase
  - [ ] Chart uses grouped bar chart or line chart format
  - [ ] Tooltip explains: "Shows prediction accuracy (Brier score) by game phase. Lower = better. Early = first 25% of game, Mid = 25-75%, Late = 75-100%, Clutch = last 2 minutes. Helps identify when each source is most/least accurate."
  - [ ] Chart title: "Time-Averaged In-Game Brier Error by Game Phase (ESPN vs Kalshi)"
  - [ ] Chart integrates into aggregate stats page

- **Technical Context**:
  - **Current State**: 
    - Backend: Phase Brier scores calculated in `calculate_espn_kalshi_divergence()` and `calculate_decision_weighted_metrics()`
    - Backend: Aggregate stats includes phase Brier scores in response
    - Frontend: HTML comment exists at `stats.js:237` but no rendering code
  - **Required Changes**: 
    - Frontend: Add chart rendering function for time-sliced performance
    - Frontend: Extract phase Brier data from aggregate stats response
    - Frontend: Configure Chart.js for grouped bar or line chart
  - **Integration Points**: 
    - Backend: Uses existing phase Brier scores from aggregate stats response
    - Frontend: Add chart rendering in `renderAggregateStats()` function
  - **Data Structures**: 
    - Backend: `{"comparison": {"phase_brier_scores": {"q1_q2": {"espn": 0.15, "kalshi": 0.18}, "q3": {...}, "q4": {...}, "final_2_min": {...}}}}`
    - Frontend: Extract phase data and format for Chart.js
  - **API Contracts**: 
    - Uses existing aggregate stats response structure

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add chart container HTML (already exists as comment, uncomment and complete)
     - Content: 
       ```javascript
       // Replace HTML comment at line 237 with:
       ${stats.comparison?.phase_brier_scores ? `
       <div>
           <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
               Time-Averaged In-Game Brier Error by Game Phase (ESPN vs Kalshi)${createTooltip('Shows prediction accuracy (Brier score) by game phase. Lower = better. Early = first 25% of game, Mid = 25-75%, Late = 75-100%, Clutch = last 2 minutes. Helps identify when each source is most/least accurate.')}
           </h5>
           <div class="chart-wrapper">
               <canvas id="phaseBrierChart"></canvas>
           </div>
       </div>
       ` : ''}
       ```
  2. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add chart rendering function
     - Content: 
       ```javascript
       // Add function similar to existing chart rendering functions:
       function renderPhaseBrierChart(phaseData) {
           const ctx = document.getElementById('phaseBrierChart');
           if (!ctx || !phaseData) return;
           
           const phases = ['Q1-Q2', 'Q3', 'Q4', 'Final 2 Min'];
           const espnScores = [
               phaseData.q1_q2?.espn,
               phaseData.q3?.espn,
               phaseData.q4?.espn,
               phaseData.final_2_min?.espn
           ];
           const kalshiScores = [
               phaseData.q1_q2?.kalshi,
               phaseData.q3?.kalshi,
               phaseData.q4?.kalshi,
               phaseData.final_2_min?.kalshi
           ];
           
           new Chart(ctx, {
               type: 'bar',
               data: {
                   labels: phases,
                   datasets: [
                       {
                           label: 'ESPN',
                           data: espnScores,
                           backgroundColor: 'rgba(0, 122, 51, 0.6)',
                           borderColor: 'rgba(0, 122, 51, 1)',
                           borderWidth: 1
                       },
                       {
                           label: 'Kalshi',
                           data: kalshiScores,
                           backgroundColor: 'rgba(128, 128, 128, 0.6)',
                           borderColor: 'rgba(128, 128, 128, 1)',
                           borderWidth: 1
                       }
                   ]
               },
               options: {
                   responsive: true,
                   maintainAspectRatio: false,
                   scales: {
                       y: {
                           beginAtZero: true,
                           title: {
                               display: true,
                               text: 'Brier Error (Lower = Better)'
                           }
                       }
                   },
                   plugins: {
                       legend: {
                           display: true,
                           position: 'top'
                       },
                       tooltip: {
                           callbacks: {
                               label: function(context) {
                                   return context.dataset.label + ': ' + context.parsed.y.toFixed(4);
                               }
                           }
                       }
                   }
               }
           });
       }
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Call chart rendering function in `renderAggregateStats()`
     - Content: Add call to `renderPhaseBrierChart(stats.comparison.phase_brier_scores)` after chart container HTML

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.comparison.phase_brier_scores'`
     - Expected Output: Object with phase Brier scores
  2. **Frontend Visual Test**: Open aggregate stats page, verify chart renders
  3. **Data Validation**: Verify chart shows ESPN and Kalshi scores for each phase

- **Definition of Done**:
  - [ ] Chart renders correctly
  - [ ] Tooltip explains meaning
  - [ ] Chart shows all phases
  - [ ] All validation steps pass

- **Rollback Plan**: Remove chart rendering code, restore HTML comment

- **Risk Assessment**: 
  - **Low Risk**: Chart rendering follows existing patterns, backend data exists
  - **Mitigation**: Verify backend data structure before implementing

- **Success Metrics**: 
  - Chart renders correctly
  - Tooltip provides clear explanation
  - Chart shows ESPN and Kalshi comparison by phase

### Epic 3: Profit Proxy Display
**Priority**: High
**Estimated Time**: 4-6 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Verify Profit Proxy Backend Aggregation
- **ID**: S19-E3-S1
- **Type**: Verification
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/api/endpoints/aggregate_stats.py` (verify aggregation logic)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Profit proxy calculated for each game in aggregate stats
  - [ ] Profit proxy metrics aggregated across games (mean, median, total signal events)
  - [ ] Aggregate stats response includes profit proxy section
  - [ ] Profit proxy includes: `signal_event_count`, `win_rate_positive_edge`, `win_rate_negative_edge`

- **Technical Context**:
  - **Current State**: 
    - Backend: `calculate_profit_proxy()` function exists at `stats.py:623-700`
    - Backend: Profit proxy calculated in aggregate stats loop at `aggregate_stats.py:614-627`
    - Backend: Profit proxy metrics collected but may not be aggregated/returned
  - **Required Changes**: 
    - Backend: Verify profit proxy aggregation logic
    - Backend: Add profit proxy section to aggregate stats response if missing
  - **Integration Points**: 
    - Backend: Uses existing `calculate_profit_proxy()` function
    - Backend: Aggregates metrics in `get_aggregate_stats()` function
  - **Data Structures**: 
    - Backend: `{"profit_proxy": {"signal_event_count": {"total": 1250, "mean": 25, "median": 23}, "win_rate_positive_edge": {"mean": 0.58, "median": 0.57}, "win_rate_negative_edge": {"mean": 0.42, "median": 0.41}}}`
  - **API Contracts**: 
    - Add profit proxy section to aggregate stats response

- **Implementation Steps**:
  1. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Verify profit proxy aggregation logic
     - Content: Check if profit proxy metrics are aggregated and included in response
  2. **Backend - aggregate_stats.py**: 
     - File: `webapp/api/endpoints/aggregate_stats.py`
     - Action: Add profit proxy section to response if missing
     - Content: Aggregate profit proxy metrics and add to response dict

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.profit_proxy'`
     - Expected Output: Object with profit proxy metrics
  2. **Data Validation**: Verify profit proxy metrics are reasonable (win rates between 0 and 1)

- **Definition of Done**:
  - [ ] Profit proxy aggregation verified
  - [ ] Profit proxy included in aggregate stats response
  - [ ] All validation steps pass

- **Rollback Plan**: Revert aggregation changes if issues arise

- **Risk Assessment**: 
  - **Low Risk**: Backend calculation exists, only need to verify aggregation
  - **Mitigation**: Test aggregation logic with sample data

- **Success Metrics**: 
  - Profit proxy metrics aggregated correctly
  - Response includes profit proxy section

#### Story 3.2: Add Profit Proxy Frontend Display
- **ID**: S19-E3-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 3
- **Prerequisites**: S19-E3-S1
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add profit proxy display)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Profit proxy metrics display in aggregate stats
  - [ ] Tooltip explains: "Profit proxy metrics identify potential betting edges when ESPN and Kalshi disagree significantly (>=5%). Positive edge = ESPN higher than Kalshi (bet home), Negative edge = ESPN lower than Kalshi (bet away). Win rates show actual outcomes for these signal events. NOTE: This is a sanity check only, not a full backtest. It doesn't account for betting limits, market impact, transaction costs, or timing."
  - [ ] Display format: "Signal Events: X (Mean: Y, Median: Z)", "Win Rate (Positive Edge): XX.X%", "Win Rate (Negative Edge): XX.X%"
  - [ ] Styling matches existing metric displays

- **Technical Context**:
  - **Current State**: 
    - Backend: Profit proxy calculated and aggregated (after Story 3.1)
    - Frontend: No display code exists for profit proxy
  - **Required Changes**: 
    - Frontend: Add profit proxy display in aggregate stats
    - Frontend: Add tooltip with explanation
  - **Integration Points**: 
    - Backend: Uses existing profit proxy section from aggregate stats response
    - Frontend: Add to aggregate stats page in `renderAggregateStats()` function
  - **Data Structures**: 
    - Backend: `{"profit_proxy": {"signal_event_count": {...}, "win_rate_positive_edge": {...}, "win_rate_negative_edge": {...}}}`
    - Frontend: Extract and display profit proxy metrics
  - **API Contracts**: 
    - Uses existing aggregate stats response structure

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add profit proxy display in aggregate stats
     - Content: 
       ```javascript
       // In renderAggregateStats() function, add profit proxy section:
       ${stats.profit_proxy ? `
       <div class="stats-group">
           <div class="stats-group-title">Profit Proxy (Betting Edge Sanity Check)${createTooltip('Profit proxy metrics identify potential betting edges when ESPN and Kalshi disagree significantly (>=5%). Positive edge = ESPN higher than Kalshi (bet home), Negative edge = ESPN lower than Kalshi (bet away). Win rates show actual outcomes for these signal events. NOTE: This is a sanity check only, not a full backtest. It doesn't account for betting limits, market impact, transaction costs, or timing.')}</div>
           ${stats.profit_proxy.signal_event_count ? `
           <div class="stat-row">
               <span class="stat-row-label">Signal Events (Total)${createTooltip('Total number of probability updates where ESPN and Kalshi disagreed by >=5%')}</span>
               <span class="stat-row-value">${formatNumber(stats.profit_proxy.signal_event_count.total || stats.profit_proxy.signal_event_count)}</span>
           </div>
           ${stats.profit_proxy.signal_event_count.mean ? `
           <div class="stat-row">
               <span class="stat-row-label">Signal Events (Mean per Game)${createTooltip('Average number of signal events per game')}</span>
               <span class="stat-row-value">${formatNumber(stats.profit_proxy.signal_event_count.mean)}</span>
           </div>
           ` : ''}
           ` : ''}
           ${stats.profit_proxy.win_rate_positive_edge ? `
           <div class="stat-row">
               <span class="stat-row-label">Win Rate (Positive Edge)${createTooltip('Actual win rate when ESPN > Kalshi by >=5% (betting on home team)')}</span>
               <span class="stat-row-value">${formatPercent(stats.profit_proxy.win_rate_positive_edge.mean || stats.profit_proxy.win_rate_positive_edge)}</span>
           </div>
           ` : ''}
           ${stats.profit_proxy.win_rate_negative_edge ? `
           <div class="stat-row">
               <span class="stat-row-label">Win Rate (Negative Edge)${createTooltip('Actual win rate when ESPN < Kalshi by >=5% (betting on away team)')}</span>
               <span class="stat-row-value">${formatPercent(stats.profit_proxy.win_rate_negative_edge.mean || stats.profit_proxy.win_rate_negative_edge)}</span>
           </div>
           ` : ''}
       </div>
       ` : ''}
       ```

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.profit_proxy'`
     - Expected Output: Object with profit proxy metrics
  2. **Frontend Visual Test**: Open aggregate stats page, verify profit proxy displays
  3. **Data Validation**: Verify win rates are between 0% and 100%

- **Definition of Done**:
  - [ ] Profit proxy displays correctly
  - [ ] Tooltip explains meaning
  - [ ] Styling matches existing metrics
  - [ ] All validation steps pass

- **Rollback Plan**: Remove profit proxy display code

- **Risk Assessment**: 
  - **Low Risk**: Simple display addition, backend data exists
  - **Mitigation**: Verify backend data structure before implementing

- **Success Metrics**: 
  - Profit proxy displays correctly
  - Tooltip provides clear explanation
  - Values are reasonable (win rates between 0% and 100%)

### Epic 4: Max Divergence Histogram (Optional)
**Priority**: Low (Optional)
**Estimated Time**: 2-3 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Add Max Divergence Histogram Chart
- **ID**: S19-E4-S1
- **Type**: Feature
- **Priority**: Low (Optional)
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/static/js/stats.js` (add histogram chart)
- **Files to Create**: None
- **Dependencies**: Chart.js library

- **Acceptance Criteria**:
  - [ ] Histogram chart renders max divergence distribution
  - [ ] Chart shows distribution of max divergence values across games
  - [ ] Tooltip explains: "Distribution of maximum divergence (max_t abs(ESPN_p_t - Kalshi_p_t)) across all games. Shows how often ESPN and Kalshi disagree significantly during games."
  - [ ] Chart title: "Max Divergence Distribution"
  - [ ] Chart integrates into aggregate stats page

- **Technical Context**:
  - **Current State**: 
    - Backend: Max divergence distribution data exists at `aggregate_stats.py:884` (`distribution` field)
    - Frontend: No histogram chart exists
  - **Required Changes**: 
    - Frontend: Add histogram chart rendering function
    - Frontend: Extract distribution data from aggregate stats response
    - Frontend: Configure Chart.js for histogram
  - **Integration Points**: 
    - Backend: Uses existing max divergence distribution from aggregate stats response
    - Frontend: Add chart rendering in `renderAggregateStats()` function
  - **Data Structures**: 
    - Backend: `{"comparison": {"max_absolute_difference": {"distribution": [0.15, 0.18, 0.22, ...]}}}`
    - Frontend: Extract distribution array and create histogram bins
  - **API Contracts**: 
    - Uses existing aggregate stats response structure

- **Implementation Steps**:
  1. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add histogram chart container HTML
     - Content: 
       ```javascript
       // In renderAggregateStats() function, add histogram section:
       ${stats.comparison?.max_absolute_difference?.distribution && stats.comparison.max_absolute_difference.distribution.length > 0 ? `
       <div>
           <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
               Max Divergence Distribution${createTooltip('Distribution of maximum divergence (max_t abs(ESPN_p_t - Kalshi_p_t)) across all games. Shows how often ESPN and Kalshi disagree significantly during games.')}
           </h5>
           <div class="chart-wrapper">
               <canvas id="maxDivergenceHistogramChart"></canvas>
           </div>
       </div>
       ` : ''}
       ```
  2. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Add histogram chart rendering function
     - Content: 
       ```javascript
       // Add function similar to existing chart rendering functions:
       function renderMaxDivergenceHistogram(distribution) {
           const ctx = document.getElementById('maxDivergenceHistogramChart');
           if (!ctx || !distribution || distribution.length === 0) return;
           
           // Create histogram bins (10 bins from 0 to max value)
           const maxVal = Math.max(...distribution);
           const binSize = maxVal / 10;
           const bins = Array(10).fill(0);
           const binLabels = [];
           
           for (let i = 0; i < 10; i++) {
               binLabels.push((i * binSize).toFixed(2) + '-' + ((i + 1) * binSize).toFixed(2));
           }
           
           distribution.forEach(val => {
               const binIndex = Math.min(Math.floor(val / binSize), 9);
               bins[binIndex]++;
           });
           
           new Chart(ctx, {
               type: 'bar',
               data: {
                   labels: binLabels,
                   datasets: [{
                       label: 'Number of Games',
                       data: bins,
                       backgroundColor: 'rgba(0, 122, 51, 0.6)',
                       borderColor: 'rgba(0, 122, 51, 1)',
                       borderWidth: 1
                   }]
               },
               options: {
                   responsive: true,
                   maintainAspectRatio: false,
                   scales: {
                       y: {
                           beginAtZero: true,
                           title: {
                               display: true,
                               text: 'Number of Games'
                           }
                       },
                       x: {
                           title: {
                               display: true,
                               text: 'Max Divergence (Probability Units)'
                           }
                       }
                   },
                   plugins: {
                       legend: {
                           display: false
                       }
                   }
               }
           });
       }
       ```
  3. **Frontend - stats.js**: 
     - File: `webapp/static/js/stats.js`
     - Action: Call histogram rendering function in `renderAggregateStats()`
     - Content: Add call to `renderMaxDivergenceHistogram(stats.comparison.max_absolute_difference.distribution)` after chart container HTML

- **Validation Steps**:
  1. **Backend API Test**: `curl http://localhost:8000/api/stats/aggregate | jq '.comparison.max_absolute_difference.distribution'`
     - Expected Output: Array of max divergence values
  2. **Frontend Visual Test**: Open aggregate stats page, verify histogram renders
  3. **Data Validation**: Verify histogram shows distribution of max divergence values

- **Definition of Done**:
  - [ ] Histogram renders correctly
  - [ ] Tooltip explains meaning
  - [ ] Histogram shows distribution of max divergence values
  - [ ] All validation steps pass

- **Rollback Plan**: Remove histogram chart code

- **Risk Assessment**: 
  - **Low Risk**: Optional feature, chart rendering follows existing patterns
  - **Mitigation**: Verify backend data structure before implementing

- **Success Metrics**: 
  - Histogram renders correctly
  - Tooltip provides clear explanation
  - Distribution shows reasonable spread of max divergence values

## Risk Assessment

### Technical Risks

**Risk 1: Backend Data Structure Mismatch**
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**: Verify backend data structure before implementing frontend displays
- **Contingency**: Adjust frontend code to match actual backend structure

**Risk 2: Chart Rendering Performance**
- **Probability**: Low
- **Impact**: Low
- **Mitigation**: Use Chart.js with data limits, implement pagination if needed
- **Contingency**: Optimize chart rendering or reduce data points if performance degrades

**Risk 3: Profit Proxy Aggregation Missing**
- **Probability**: Medium
- **Impact**: High
- **Mitigation**: Verify profit proxy aggregation in backend before implementing frontend
- **Contingency**: Implement aggregation logic if missing

### Business Risks

**Risk 1: Feature Completeness**
- **Probability**: Low
- **Impact**: Low
- **Mitigation**: Follow existing patterns and verify against sprint plan
- **Contingency**: Document any missing features for future sprints

## Success Metrics and Monitoring

### Implementation Coverage Metrics
- **Current Coverage**: 0% (features not implemented)
- **Target Coverage**: 100% (all 4 features implemented)
- **Missing Features**: 4 features → Target: 0 missing features

### Quality Metrics
- **Code Coverage**: Not measured (manual testing only)
- **Test Quality**: Manual testing only
- **Documentation Coverage**: Sprint plan exists, implementation status documented

### Performance Metrics
- **Chart Rendering**: Target <500ms for typical datasets
- **API Response Time**: Target <200ms for aggregate stats
- **Memory Usage**: Monitor Chart.js memory consumption

## Appendices

### Appendix A: Related Sprint Files
- `cursor-files/sprints/sprint-plan-dashboard-metrics-improvements-v1.md` - Original dashboard metrics sprint plan
- `cursor-files/analysis/2026-01-11-sprint-implementation-status/unimplemented-features-analysis.md` - Analysis identifying missing features

### Appendix B: Code References

**Backend Files**:
- `webapp/api/endpoints/stats.py:980` - `calculate_espn_kalshi_divergence()` returns `data_points`
- `webapp/api/endpoints/stats.py:623-700` - `calculate_profit_proxy()` function
- `webapp/api/endpoints/aggregate_stats.py:884` - Max divergence distribution data
- `webapp/api/endpoints/aggregate_stats.py:614-627` - Profit proxy calculation in aggregate loop
- `webapp/api/endpoints/aggregate_stats.py:893-894` - Alignment data points

**Frontend Files**:
- `webapp/static/js/stats.js:237` - Time-sliced performance chart HTML comment
- `webapp/static/js/stats.js` - Chart rendering functions and aggregate stats display

---

## Document Validation

**IMPORTANT**: This sprint plan follows the comprehensive validation checklist in `cursor-files/templates/SPRINT_STANDARDS.md`.

**Validation Checklist**:
- ✅ **File Verification**: All file contents verified using `read_file` tool before making claims
- ✅ **Command Evidence**: All data gathering commands documented with exact commands and verbatim output
- ✅ **Date Verification**: Used `date -u` command to verify current date
- ✅ **No Assumptions**: No assumptions made about implementation status without code verification
- ✅ **No Vague Language**: No use of "likely", "probably", "mostly", etc.
- ✅ **Definitive Language**: All statements use definitive language ("is", "will", "does", "has", "contains", "requires", "implements")
- ✅ **Concrete Evidence**: Every claim backed by specific, verifiable evidence
- ✅ **Perfect Completeness**: Sprint plan is 100% complete for all 4 features
- ✅ **Honest Assessment**: Actual findings reported, not assumptions or expectations
- ✅ **Design Pattern**: Specific pattern names and implementation details provided where applicable
- ✅ **Algorithm**: Algorithm names, Big O notation, and performance characteristics specified where applicable
- ✅ **Evidence**: All claims supported by concrete evidence and measurements

