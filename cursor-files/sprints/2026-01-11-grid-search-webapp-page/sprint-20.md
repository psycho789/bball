# Sprint Plan: Grid Search Hyperparameter Optimization Webapp Page

**Date**: Sun Jan 11 2026  
**Sprint Duration**: 4-5 days (19-27 hours total)  
**Sprint Goal**: Create a webapp page for running grid search hyperparameter optimization with all user-facing parameters, progress tracking, and client-side visualization rendering using Chart.js.  
**Current Status**: Grid search exists as CLI script only (`scripts/trade/grid_search_hyperparameters.py`). Visualization script exists (`scripts/trade/analyze_grid_search_results.py`). No web interface exists.  
**Target Status**: Fully functional webapp page with 17 user-facing parameters, async execution with progress tracking, results display, and interactive Chart.js visualizations.  
**Team Size**: 1 developer  
**Sprint Lead**: AI Assistant

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `cursor-files/templates/SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`).
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
- **Business Driver**: Grid search hyperparameter optimization is currently only accessible via CLI, limiting usability. Users must memorize complex parameter syntax and manually manage result files. A web interface will make this powerful feature accessible to all users with a clean, intuitive UI.
- **Success Criteria**: 
  - All 17 user-facing parameters accessible via web UI
  - Real-time progress tracking (updates every 500ms)
  - Results displayed in app style with tables and interactive charts
  - Client-side Chart.js visualizations (heatmaps, marginal effects, scatter plots)
  - Pattern detection summary displayed
  - Consistent UI/UX with existing simulation page
- **Stakeholders**: Data scientists and traders using grid search for strategy optimization
- **Timeline Constraints**: None specified

### Technical Context
- **Current System State**: 
  - Backend: Grid search script exists at `scripts/trade/grid_search_hyperparameters.py` (CLI only)
  - Visualization script exists at `scripts/trade/analyze_grid_search_results.py` (CLI only)
  - Simulation page exists at `webapp/static/templates/simulation.html` (reference implementation)
  - Simulation API endpoint exists at `webapp/api/endpoints/simulation.py` (reference for async pattern)
  - Chart.js already loaded in app (for visualization rendering)
- **Target System State**: 
  - New API endpoint: `/api/grid-search/run` (POST) - accepts parameters, returns request_id
  - New API endpoint: `/api/grid-search/progress/{request_id}` (GET) - returns progress
  - New API endpoint: `/api/grid-search/results/{request_id}` (GET) - returns results with visualization data (raw arrays for Chart.js)
  - New webapp page: `grid-search.html` with all 17 user-facing parameters
  - New JavaScript module: `grid-search.js` for UI logic and Chart.js rendering
  - Results displayed with tables, charts, and pattern detection summary
- **Architecture Impact**: 
  - Backend: New endpoint file `webapp/api/endpoints/grid_search.py`
  - Frontend: New template `webapp/static/templates/grid-search.html`, new JS `webapp/static/js/grid-search.js`
  - Routing: Add route in `webapp/static/js/routing.js`
  - No database schema changes required
- **Integration Points**: 
  - API endpoints: Import functions from grid search script (using `importlib.util` like simulation endpoint)
  - Frontend: Use Chart.js (already loaded) for visualizations
  - Progress tracking: Use same pattern as simulation progress (`_simulation_progress` dictionary)

### Sprint Scope
- **In Scope**: 
  - Story 1: Grid Search API Endpoint (async execution, progress tracking, data transformation)
  - Story 2: Grid Search HTML Template (17 user-facing parameters, form validation)
  - Story 3: Grid Search JavaScript Logic (progress polling, results rendering, Chart.js visualizations)
  - Story 4: Routing and Navigation Integration
- **Out of Scope**: 
  - Grid search history/comparison (future enhancement)
  - Plotly.js integration for advanced heatmaps (use Chart.js heatmap plugin or custom canvas - basic implementation)
  - File downloads (data returned in API response only)
  - Server-side PNG generation (all rendering client-side with Chart.js)

## User Stories

### Story 1: Grid Search API Endpoint
**As a** user  
**I want** to run grid search hyperparameter optimization through a web API  
**So that** I can optimize trading strategy parameters without using CLI

**Acceptance Criteria**:
- [ ] API endpoint `/api/grid-search/run` accepts all 17 user-facing parameters
- [ ] Endpoint returns `request_id` immediately (async execution)
- [ ] Endpoint imports functions directly from grid search script (not subprocess)
- [ ] Progress tracking endpoint `/api/grid-search/progress/{request_id}` returns current/total
- [ ] Results endpoint `/api/grid-search/results/{request_id}` returns optimized data:
  - Training results: Top N only (not all combinations)
  - Validation results: All combinations
  - Test results: All combinations
  - Final selection with metrics
  - Pattern detection summary
  - Visualization data (raw arrays for client-side Chart.js rendering):
    - Heatmap data: 2D array (entry × exit → profit)
    - Marginal effects: Arrays for line charts
    - Tradeoff scatter: Arrays for scatter plot
- [ ] Internal parameters (workers, seed, output_dir) auto-set by server
- [ ] Error handling for invalid parameters and failed executions

**Technical Details**:
- Import functions using `importlib.util` (same pattern as simulation endpoint)
- Use ThreadPoolExecutor for parallel execution
- Store progress in thread-safe dictionary
- Transform results data for client-side Chart.js rendering
- Call `detect_patterns()` function for pattern analysis

**Estimated Effort**: 6-8 hours

### Story 2: Grid Search HTML Template
**As a** user  
**I want** a web form with all grid search parameters  
**So that** I can easily configure and run grid searches

**Acceptance Criteria**:
- [ ] HTML template `grid-search.html` created with all 17 user-facing parameters
- [ ] Parameters grouped logically:
  - Input Selection: Season selector dropdown
  - Grid Search Range: Entry/exit min/max/step (6 inputs)
  - Trading Parameters: Bet amount, enable fees, slippage rate (3 inputs)
  - Data Filtering: Exclude first/last seconds, use trade data (3 inputs)
  - Data Split: Train/valid/test ratios (3 inputs, must sum to 1.0)
  - Selection Criteria: Top N, min trade count (2 inputs)
- [ ] Form validation (client-side):
  - Split ratios must sum to 1.0
  - Grid ranges valid (min < max, step > 0)
  - Entry/exit thresholds in valid range (0-1)
- [ ] Consistent styling with simulation page (`sim-input-group`, etc.)
- [ ] Loading indicator with progress text
- [ ] Results section (hidden until complete)
- [ ] Canvas elements for Chart.js visualizations

**Technical Details**:
- Follow simulation page structure (`webapp/static/templates/simulation.html`)
- Use same CSS classes for consistency
- Season selector populated via API call to `/api/games`
- Form validation using JavaScript

**Estimated Effort**: 3-4 hours

### Story 3: Grid Search JavaScript Logic
**As a** user  
**I want** to see progress updates and interactive visualizations  
**So that** I can monitor grid search execution and analyze results

**Acceptance Criteria**:
- [ ] JavaScript module `grid-search.js` created
- [ ] `runGridSearch()` function collects form parameters and calls API
- [ ] `pollGridSearchProgress()` function polls progress every 500ms
- [ ] Progress indicator shows: "Processing: X/Y combinations (Z%)"
- [ ] `renderGridSearchResults()` function displays:
  - Final selection prominently with metrics
  - Results tables (top N training, all validation/test)
  - Pattern detection summary as formatted cards
- [ ] Chart.js visualizations rendered:
  - Profit heatmaps (Chart.js heatmap plugin or custom canvas)
  - Marginal effects (line charts - Chart.js)
  - Tradeoff scatter (scatter plot - Chart.js)
- [ ] Charts highlight chosen parameters
- [ ] Error handling and user feedback

**Technical Details**:
- Follow simulation page JavaScript patterns (`webapp/static/js/simulation.js`)
- Use Chart.js (already loaded) for line and scatter charts
- Heatmaps: Use Chart.js heatmap plugin, Plotly.js, or custom canvas rendering
- Pattern detection displayed as formatted cards/sections
- Use same Chart.js styling as simulation page

**Estimated Effort**: 5-7 hours

### Story 4: Routing and Navigation Integration
**As a** user  
**I want** to access the grid search page from navigation  
**So that** I can easily find and use the feature

**Acceptance Criteria**:
- [ ] Route added in `routing.js`: `showGridSearchPageView()`
- [ ] Navigation link added to main navigation
- [ ] Page initializes properly after route renders
- [ ] Season selector populated on page load
- [ ] Form validation works correctly

**Technical Details**:
- Follow existing routing pattern (`webapp/static/js/routing.js`)
- Call `initializeGridSearchPage()` after template renders
- Add navigation link in main navigation HTML

**Estimated Effort**: 1-2 hours

## Task Breakdown

### Phase 1: API Endpoint Foundation (6-8 hours)

#### Task 1.1: Create Grid Search API Endpoint File
**Files**: `webapp/api/endpoints/grid_search.py` (new)  
**Effort**: 4-5 hours  
**Dependencies**: None

**Steps**:
1. Create new file `webapp/api/endpoints/grid_search.py`
2. Import FastAPI router and dependencies
3. Import grid search functions using `importlib.util`:
   - From `scripts/trade/grid_search_hyperparameters.py`: 
     - `GridSearchConfig` (dataclass)
     - `generate_grid(config)` - generates valid (entry, exit) combinations
     - `get_game_ids_from_season(conn, season)` - gets game IDs for season
     - `split_games(game_ids, config)` - splits games into train/valid/test
     - `run_simulation_for_games(conn, game_ids, entry_threshold, exit_threshold, config)` - runs simulation for game list
     - `process_combination(combination, game_splits, config, dsn)` - processes one combination across all splits
   - From `scripts/trade/analyze_grid_search_results.py`: 
     - `detect_patterns(df_train, df_valid)` - returns pattern detection analysis
   - Reuse `get_aligned_data()` and `simulate_trading_strategy()` from simulation endpoint (already imported)
4. Create progress tracking dictionary: `_grid_search_progress: dict[str, dict]`
5. Create thread lock: `_grid_search_lock = threading.Lock()`
6. Implement `/api/grid-search/run` endpoint (POST):
   - Accept all 17 user-facing parameters
   - Validate parameters (split ratios sum to 1.0, etc.)
   - Generate unique request_id
   - Auto-set internal parameters (workers, seed)
   - Start background task for grid search execution
   - Return request_id immediately
7. Implement background task function (using FastAPI BackgroundTasks or threading):
   - Get game IDs for season using `get_game_ids_from_season(conn, season)`
   - Split games using `split_games(game_ids, config)` → (train_games, valid_games, test_games)
   - Generate grid combinations using `generate_grid(config)` → list of (entry, exit) tuples
   - Initialize progress: `total = len(combinations) * (len(train_games) + len(valid_games) + len(test_games))`
   - Process combinations in parallel using ThreadPoolExecutor:
     - For each combination, call `process_combination()` which runs simulations for all splits
     - Update progress: `current += len(train_games) + len(valid_games) + len(test_games)`
     - Store current combination being processed for progress display
   - Aggregate results by split (train, valid, test)
   - Filter training results: Sort by `net_profit_dollars` descending, keep only top N
   - Select best combination: Rank on train (top N), select best on valid from top N, evaluate on test
   - Transform data for client-side visualization (see Task 1.3 details)
   - Call `detect_patterns()` with train/valid DataFrames (convert results to DataFrames)
   - Store all results in progress dictionary with status "complete"

**Acceptance Criteria**:
- Endpoint accepts all 17 user-facing parameters and returns request_id immediately
- Background task executes grid search correctly using imported functions
- Progress updates stored thread-safely
- Games split correctly into train/valid/test
- Grid combinations generated correctly with constraints (exit < entry)
- Results aggregated by split correctly
- Training results filtered to top N only

#### Task 1.2: Implement Progress Tracking Endpoint
**Files**: `webapp/api/endpoints/grid_search.py`  
**Effort**: 1 hour  
**Dependencies**: Task 1.1

**Steps**:
1. Implement `/api/grid-search/progress/{request_id}` endpoint (GET)
2. Return progress status: `{"status": "running|complete|error", "current": int, "total": int, "current_combo": str}`
3. Handle missing request_id gracefully
4. Use thread lock for safe access

**Acceptance Criteria**:
- Progress endpoint returns current status
- Thread-safe progress updates

#### Task 1.3: Implement Results Endpoint
**Files**: `webapp/api/endpoints/grid_search.py`  
**Effort**: 1-2 hours  
**Dependencies**: Task 1.2

**Steps**:
1. Implement `/api/grid-search/results/{request_id}` endpoint (GET)
2. Return optimized results:
   - Final selection with metrics
   - Training results (top N only)
   - Validation results (all combinations)
   - Test results (all combinations)
   - Pattern detection summary
   - Visualization data (transformed for Chart.js):
     - Heatmap data: 2D array (entry × exit → profit)
     - Marginal effects: Arrays for line charts
     - Tradeoff scatter: Arrays for scatter plot
3. Transform results data for client-side Chart.js rendering:
   - **Heatmap data**: 
     - Convert validation_results to pandas DataFrame: `df_valid = pd.DataFrame(validation_results)`
     - Pivot: `pivot = df_valid.pivot(index='exit_threshold', columns='entry_threshold', values='net_profit_dollars')`
     - Extract: 
       - `entry_thresholds`: `list(pivot.columns)` (sorted)
       - `exit_thresholds`: `list(pivot.index)` (sorted)
       - `profit_matrix`: `pivot.values.tolist()` (2D array, rows=exit, cols=entry)
     - Include chosen parameters: `chosen_entry`, `chosen_exit` from final_selection
   - **Marginal effects**:
     - Group validation_results by `entry_threshold`: calculate mean/std of `net_profit_dollars`
     - Group validation_results by `exit_threshold`: calculate mean/std of `net_profit_dollars`
     - Return arrays: `{entry: {thresholds: [], mean: [], std: []}, exit: {thresholds: [], mean: [], std: []}}`
   - **Tradeoff scatter**:
     - Extract from validation_results: `num_trades`, `net_profit_dollars`, `entry_threshold` arrays
     - Return: `{num_trades: [], net_profit: [], entry_threshold: []}`
4. Handle errors gracefully:
   - Request not found → 404 with clear message
   - Still running → 202 with status message
   - Error occurred → 500 with error details
   - Invalid request_id format → 400

**Acceptance Criteria**:
- Results endpoint returns all required data
- Data transformed for client-side rendering
- Training results filtered to top N only

### Phase 2: HTML Template (3-4 hours)

#### Task 2.1: Create Grid Search HTML Template
**Files**: `webapp/static/templates/grid-search.html` (new)  
**Effort**: 2-3 hours  
**Dependencies**: None (can be done in parallel with Phase 1)

**Steps**:
1. Create new file `webapp/static/templates/grid-search.html`
2. Copy structure from simulation page template (`webapp/static/templates/simulation.html`)
3. Include necessary script tags at bottom:
   - Chart.js (already included globally, but verify)
   - Grid search JavaScript: `<script src="/static/js/grid-search.js"></script>`
4. Add form inputs for all 17 parameters:
   - **Input Selection**: Season selector dropdown (populated via JavaScript)
   - **Grid Search Range**: 6 number inputs (entry/exit min/max/step)
   - **Trading Parameters**: Bet amount, enable fees checkbox, slippage rate
   - **Data Filtering**: Exclude first/last seconds, use trade data checkbox
   - **Data Split**: Train/valid/test ratios (3 inputs with validation)
   - **Selection Criteria**: Top N, min trade count
4. Add "Run Grid Search" button
5. Add loading indicator section (hidden initially)
6. Add results section (hidden initially):
   - Final selection display
   - Results tables containers
   - Pattern detection summary container
   - Canvas elements for Chart.js visualizations:
     - `profitHeatmapCanvas` (for profit heatmap)
     - `marginalEffectsCanvas` (for marginal effects)
     - `tradeoffScatterCanvas` (for tradeoff scatter)
7. Use same CSS classes as simulation page (`sim-input-group`, etc.)

**Acceptance Criteria**:
- All 17 parameters accessible via form inputs
- Consistent styling with simulation page
- Canvas elements present for visualizations

#### Task 2.2: Add Form Validation
**Files**: `webapp/static/templates/grid-search.html`  
**Effort**: 1 hour  
**Dependencies**: Task 2.1

**Steps**:
1. Add client-side validation JavaScript:
   - Split ratios must sum to 1.0 (show error if not)
   - Grid ranges valid (min < max, step > 0)
   - Entry/exit thresholds in valid range (0-1)
2. Add validation feedback UI (error messages)
3. Disable submit button if validation fails

**Acceptance Criteria**:
- Form validation works correctly
- User feedback for validation errors

### Phase 3: JavaScript Logic (5-7 hours)

#### Task 3.1: Create Grid Search JavaScript Module
**Files**: `webapp/static/js/grid-search.js` (new)  
**Effort**: 2 hours  
**Dependencies**: Phase 1 complete (API endpoints), Phase 2 complete (HTML template)

**Steps**:
1. Create new file `webapp/static/js/grid-search.js`
2. Implement `initializeSeasonSelector()` function:
   - Query `/api/games` to get available seasons
   - Populate season dropdown
   - Set default to most recent season
3. Implement `runGridSearch()` function:
   - Collect all form parameters
   - Validate parameters (client-side)
   - Call `/api/grid-search/run` endpoint
   - Get request_id from response
   - Start progress polling
   - Show loading indicator
4. Implement `pollGridSearchProgress()` function:
   - Poll `/api/grid-search/progress/{request_id}` every 500ms
   - Update progress indicator: "Processing: X/Y combinations (Z%)"
   - Show current combination being processed
   - Stop polling on `complete` or `error`
   - Fetch results when complete

**Acceptance Criteria**:
- API calls work correctly
- Progress polling updates every 500ms
- Season selector populated on page load

#### Task 3.2: Implement Results Rendering
**Files**: `webapp/static/js/grid-search.js`  
**Effort**: 2 hours  
**Dependencies**: Task 3.1

**Steps**:
1. Implement `renderGridSearchResults()` function:
   - Parse results JSON from API
   - Render final selection prominently:
     - Best combination (entry/exit thresholds)
     - Metrics for train/valid/test splits
   - Render results tables:
     - Top N training results
     - All validation results (sortable table)
     - All test results (sortable table)
   - Display pattern detection summary:
     - Profit-positive region boundary
     - Monotonicity analysis
     - Robustness assessment (plateau vs peak)
     - Stability check (with warnings if unstable)
     - Optimal region identification
2. Implement `renderPatternSummary()` function:
   - Format pattern detection results as cards/sections
   - Highlight key insights
   - Use app styling (consistent with simulation page)

**Acceptance Criteria**:
- Results displayed correctly in tables
- Pattern detection summary formatted nicely
- Final selection highlighted prominently

#### Task 3.3: Implement Chart.js Visualizations
**Files**: `webapp/static/js/grid-search.js`  
**Effort**: 3-4 hours  
**Dependencies**: Task 3.2

**Steps**:
1. Implement `renderProfitHeatmap()` function:
   - Use Chart.js heatmap plugin OR Plotly.js OR custom canvas rendering
   - Create 2D heatmap from profit_matrix data
   - Highlight chosen parameters with marker
   - Add color scale/legend
2. Implement `renderMarginalEffects()` function:
   - Render entry threshold marginal effect as line chart (Chart.js)
   - Render exit threshold marginal effect as line chart (Chart.js)
   - Add error bars (std) using fill between
   - Use same styling as simulation page charts
3. Implement `renderTradeoffScatter()` function:
   - Render scatter plot (Chart.js scatter type)
   - Color points by entry threshold
   - Add tooltips showing combination details
   - Use same styling as simulation page charts
4. Call visualization functions after results received
5. Handle chart rendering errors gracefully

**Acceptance Criteria**:
- All visualizations render correctly
- Charts are interactive (hover tooltips)
- Consistent styling with simulation page
- Chosen parameters highlighted on heatmaps

#### Task 3.4: Implement Page Initialization
**Files**: `webapp/static/js/grid-search.js`  
**Effort**: 1 hour  
**Dependencies**: All Task 3.x complete

**Steps**:
1. Implement `initializeGridSearchPage()` function:
   - Initialize season selector
   - Set up form validation
   - Attach event handlers:
     - Form submit → `runGridSearch()`
     - Validation on input change
   - Set default parameter values
2. Export function for use by routing

**Acceptance Criteria**:
- Page initializes correctly
- Form validation works
- Event handlers attached properly

### Phase 4: Routing and Integration (1-2 hours)

#### Task 4.1: Register Router in main.py
**Files**: `webapp/api/main.py`  
**Effort**: 15 minutes  
**Dependencies**: Task 1.1 complete (grid_search.py created)

**Steps**:
1. Import grid_search router: `from .endpoints import grid_search`
2. Register router: `app.include_router(grid_search.router, prefix="/api", tags=["grid_search"])`
3. Add after other router registrations (around line 143)
4. Verify server starts without errors

**Acceptance Criteria**:
- Router registered correctly
- Server starts without errors
- Endpoints accessible at `/api/grid-search/*`

#### Task 4.2: Add Route in Routing.js
**Files**: `webapp/static/js/routing.js`  
**Effort**: 30 minutes  
**Dependencies**: Phase 2 and Phase 3 complete

**Steps**:
1. Add `showGridSearchPageView()` function in `routing.js`
2. Follow same pattern as `showSimulationPageView()`
3. Load grid-search.html template using fetch or template loading mechanism
4. Insert template into main content area
5. Call `initializeGridSearchPage()` after template renders
6. Handle loading errors gracefully

**Acceptance Criteria**:
- Route works correctly
- Page initializes after route renders

#### Task 4.3: Add Navigation Link
**Files**: Navigation HTML template (main navigation)  
**Effort**: 30 minutes  
**Dependencies**: Task 4.2

**Steps**:
1. Add navigation link to grid search page
2. Use same styling as other navigation links
3. Test navigation works correctly

**Acceptance Criteria**:
- Navigation link present and styled correctly
- Clicking link navigates to grid search page

#### Task 4.4: End-to-End Testing
**Files**: All  
**Effort**: 1 hour  
**Dependencies**: All tasks complete

**Steps**:
1. Test full flow:
   - Navigate to grid search page
   - Fill in parameters
   - Submit form
   - Verify progress updates
   - Verify results display
   - Verify visualizations render
   - Verify pattern detection summary displays
2. Test error cases:
   - Invalid parameters
   - Network errors
   - Long-running searches
3. Test edge cases:
   - Small grid searches (few combinations)
   - Large grid searches (many combinations)
   - Different parameter combinations

**Acceptance Criteria**:
- Full flow works end-to-end
- Error handling works correctly
- Edge cases handled gracefully

## Testing Strategy

### Unit Testing
- **API Endpoint Tests**: Test parameter validation, progress tracking, results transformation
- **JavaScript Function Tests**: Test form validation, data transformation, chart rendering

### Integration Testing
- **API Integration**: Test full grid search execution flow
- **Frontend Integration**: Test UI interactions, progress polling, results display

### Manual Testing
- **User Flow**: Complete grid search from start to finish
- **Visual Testing**: Verify charts render correctly, styling consistent
- **Performance Testing**: Test with various grid sizes (small to large)

## Risk Mitigation

### Risk 1: Long-Running Grid Searches May Timeout
**Probability**: Medium  
**Impact**: High  
**Mitigation**: 
- Use background tasks (don't block request)
- Implement proper timeout handling
- Allow users to check progress and retrieve results later
- Consider implementing cancellation endpoint (future)

### Risk 2: Chart.js Heatmap Support
**Probability**: Medium  
**Impact**: Low  
**Mitigation**: 
- Use Chart.js for line/scatter (already supported)
- For heatmaps: Use Chart.js heatmap plugin OR Plotly.js OR custom canvas rendering
- Can start with basic implementation and enhance later

### Risk 3: Memory Usage for Large Grid Searches
**Probability**: Low  
**Impact**: Medium  
**Mitigation**: 
- Filter training results to top N only (reduces response size)
- Stream results if needed (future enhancement)
- Monitor memory usage during testing

### Risk 4: Data Transformation Complexity
**Probability**: Low  
**Impact**: Low  
**Mitigation**: 
- Transform data in backend (simpler than client-side)
- Use pandas for data manipulation (already available)
- Test transformation with various grid sizes

## Definition of Done

- [ ] All 4 user stories completed and tested
- [ ] Router registered in `webapp/api/main.py`
- [ ] API endpoints working correctly:
  - `/api/grid-search/run` (POST) - accepts parameters, returns request_id
  - `/api/grid-search/progress/{request_id}` (GET) - returns progress
  - `/api/grid-search/results/{request_id}` (GET) - returns results with visualization data
- [ ] HTML template created with all 17 parameters, form validation, canvas elements
- [ ] JavaScript logic implemented:
  - Season selector initialization
  - Progress polling (500ms intervals)
  - Results rendering (tables, pattern summary)
  - Chart.js visualizations (heatmaps, marginal effects, scatter)
- [ ] Chart.js visualizations rendering correctly:
  - Profit heatmaps (with chosen params highlighted)
  - Marginal effects (line charts with error bars)
  - Tradeoff scatter (scatter plot with color coding)
- [ ] Pattern detection summary displayed as formatted cards
- [ ] Routing and navigation integrated:
  - Route added in `routing.js`
  - Navigation link added
  - Page initializes correctly
- [ ] Consistent styling with simulation page
- [ ] Error handling implemented (invalid params, network errors, timeouts)
- [ ] Training results filtered to top N only (optimization)
- [ ] Data transformation working (heatmap, marginal effects, scatter data)
- [ ] Manual testing completed:
  - Small grid search (few combinations)
  - Large grid search (many combinations)
  - Error cases (invalid params, network errors)
- [ ] Code follows existing patterns and conventions:
  - Function imports using `importlib.util` (like simulation endpoint)
  - Progress tracking using thread-safe dictionary (like simulation)
  - Chart.js rendering (like simulation page)

## Post-Sprint Tasks

- [ ] Document API endpoints in API documentation
- [ ] Add tooltips/help text for parameters (if needed)
- [ ] Consider enhancements:
  - Interactive Chart.js heatmaps (Plotly.js integration)
  - Grid search history/comparison
  - Export results as CSV/JSON
  - Cancel running grid search

## References

- **Analysis Document**: `cursor-files/analysis/2026-01-11-grid-search-webapp-page/grid_search_webapp_page_analysis.md`
- **Grid Search Script**: `scripts/trade/grid_search_hyperparameters.py`
- **Visualization Script**: `scripts/trade/analyze_grid_search_results.py`
- **Simulation Page Reference**: `webapp/static/templates/simulation.html`
- **Simulation API Reference**: `webapp/api/endpoints/simulation.py`
- **Simulation JS Reference**: `webapp/static/js/simulation.js`

