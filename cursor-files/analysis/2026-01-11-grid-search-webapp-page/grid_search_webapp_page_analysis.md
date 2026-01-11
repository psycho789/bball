# Analysis: Grid Search Hyperparameter Optimization Webapp Page

**Date**: Sun Jan 11 09:46:58 PST 2026  
**Status**: Draft  
**Author**: AI Assistant  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Analyze requirements and design for creating a webapp page that allows users to run grid search hyperparameter optimization through the UI with all parameters customizable, progress tracking, and results display in app style.

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (code refs, commands + verbatim output, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and exact artifacts analyzed.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`).

## Executive Summary

### Key Findings
- **Finding 1**: Grid search script (`scripts/trade/grid_search_hyperparameters.py`) has 25 total parameters, but only 18 are user-facing and should be exposed in web UI (7 are internal/technical and should be auto-set by server)
- **Finding 2**: Simulation page (`webapp/static/templates/simulation.html`) provides excellent pattern for progress tracking and results display that can be reused
- **Finding 3**: Grid search CLI script writes multiple files (CSV, JSON), but API should return all data in JSON response (no file outputs needed)
- **Finding 4**: Visualization script (`scripts/trade/analyze_grid_search_results.py`) generates 5 professional-quality visualizations (heatmaps, marginal effects, scatter plots) plus pattern detection analysis that should be integrated into webapp results display

### Critical Issues Identified
- **Issue 1**: No web interface for grid search - users must use CLI with complex parameter syntax
- **Issue 2**: No real-time progress visibility - users can't see current status during long-running grid searches
- **Issue 3**: Results are stored in filesystem (CLI only) - API should return data directly in response, not write files
- **Issue 4**: Visualizations require separate script execution - users must manually run `analyze_grid_search_results.py` after grid search completes

### Recommended Actions
- **Action 1**: [Priority: High] - Create new API endpoint `/api/grid-search/run` that accepts 17 user-facing parameters (internal params like workers, seed, output_dir auto-set by server)
- **Action 2**: [Priority: High] - Create new API endpoint `/api/grid-search/progress/{request_id}` for progress tracking (similar to simulation progress)
- **Action 3**: [Priority: High] - Create new webapp page `grid-search.html` with 17 user-facing parameters as form inputs (grouped logically: Input Selection (season dropdown), Grid Range, Trading, Data Filtering, Data Split, Selection Criteria)
- **Action 4**: [Priority: High] - Integrate visualization functions to automatically generate visualizations (stored temporarily, served via URLs)
- **Action 5**: [Priority: High] - Create endpoint to serve visualization PNG images (no permanent file storage, just temporary storage/cache)
- **Action 6**: [Priority: High] - Create JavaScript module `grid-search.js` for UI logic, progress polling, results rendering, and visualization display
- **Action 7**: [Priority: Medium] - Add routing for grid search page in `routing.js`

### Success Metrics
- **Metric 1**: All 17 user-facing grid search parameters accessible via web UI (baseline: 0) → (target: 100%)
- **Metric 2**: Real-time progress updates every 500ms during grid search execution (baseline: none) → (target: <500ms latency)
- **Metric 3**: Results displayed in app style with charts/tables (baseline: file downloads only) → (target: full UI integration)
- **Metric 4**: All 5 visualizations automatically generated and displayed after completion (baseline: manual script execution) → (target: automatic integration)
- **Metric 5**: Pattern detection summary displayed in webapp (baseline: console output only) → (target: formatted UI display)

## Problem Statement

### Current Situation

**Grid Search CLI Tool**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:434-830`
- **Current Access**: Command-line interface only
- **Parameters**: 20+ configurable parameters via argparse
- **Execution**: Synchronous, long-running (1-3 hours for full grid search)
- **Output**: Files written to disk (`grid_search_results/` directory)

**Evidence**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:434-474`
- **Content**: 
  ```python
  parser.add_argument('--season', type=str, help='Season label (e.g., "2025-26")')
  parser.add_argument('--entry-min', type=float, default=0.02, help='Minimum entry threshold')
  parser.add_argument('--entry-max', type=float, default=0.10, help='Maximum entry threshold')
  # ... 18+ more parameters
  ```

**Simulation Page Pattern**:
- **File**: `webapp/static/templates/simulation.html:1-100`
- **Current Implementation**: Form inputs, progress tracking, results display
- **Progress Tracking**: Polls `/api/simulation/progress/{request_id}` every 500ms
- **Results Display**: Simplified and advanced views with charts and tables

**Evidence**:
- **File**: `webapp/static/js/simulation.js:46-76`
- **Content**: 
  ```javascript
  async function pollSimulationProgress(requestId, onProgress) {
      const pollInterval = 500; // Poll every 500ms
      // ... polling logic
  }
  ```

### Pain Points
- **Pain Point 1**: Users must memorize or reference CLI parameter names and syntax to run grid search
- **Pain Point 2**: No visibility into progress during long-running searches (1-3 hours)
- **Pain Point 3**: Results are in filesystem - users must download and open CSV/JSON files manually
- **Pain Point 4**: No integrated visualization of results (heatmaps, charts) in webapp
- **Pain Point 5**: Cannot easily compare multiple grid search runs without manual file management

### Business Impact
- **Performance Impact**: Users waste time learning CLI syntax and managing files
- **User Experience Impact**: Poor discoverability and usability compared to simulation page
- **Maintenance Impact**: Two separate interfaces (CLI and webapp) to maintain

### Success Criteria
- **Criterion 1**: All grid search parameters accessible via web UI form inputs
- **Criterion 2**: Real-time progress indicator showing current/total work units during execution
- **Criterion 3**: Results displayed in webapp with tables, charts, and downloadable files
- **Criterion 4**: Consistent UI/UX with existing simulation page

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 
  - New: `webapp/api/endpoints/grid_search.py` (API endpoint)
  - New: `webapp/static/templates/grid-search.html` (HTML template)
  - New: `webapp/static/js/grid-search.js` (JavaScript logic)
  - Modified: `webapp/static/js/routing.js` (add route)
  - Modified: `webapp/api/__init__.py` or router registration (add endpoint)
- **Estimated Effort**: 16-24 hours
  - API endpoint: 4-6 hours
  - HTML template: 3-4 hours
  - JavaScript logic: 4-6 hours
  - Progress tracking: 2-3 hours
  - Results rendering: 3-5 hours
- **Technical Complexity**: Medium
  - Reuse existing patterns from simulation page
  - Async execution with progress tracking (similar to simulation)
  - Results parsing and display (CSV/JSON handling)
- **Risk Level**: Low-Medium
  - Low: Reusing proven patterns from simulation page
  - Medium: Long-running operations need proper error handling and cancellation

**Sprint Scope Recommendation**: Single Sprint
- **Rationale**: Well-defined scope, clear patterns to follow, isolated feature
- **Recommended Approach**: 
  - Phase 1: API endpoint with async execution and visualization generation (5-7 hours)
  - Phase 2: HTML template with all parameters (3-4 hours)
  - Phase 3: JavaScript logic, progress tracking, and visualization display (5-7 hours)
  - Phase 4: Results display, pattern summary, and styling (3-5 hours)
  - Phase 5: Testing and polish (2-3 hours)

**Dependency Analysis**:
- **Dependencies**: 
  - Grid search script must remain functional (no changes needed)
  - Database connection (already available)
  - Simulation page patterns (reference implementation)
- **Parallel Work Opportunities**: 
  - HTML template can be built in parallel with API endpoint
  - Results rendering can be built after API is functional
- **Risk Mitigation Strategies**:
  - Use same progress tracking pattern as simulation (proven)
  - Test with small grid searches first (--max-combinations)
  - Implement timeout handling for long-running operations

## Current State Analysis

### System Architecture Overview

**Grid Search Script Architecture**:
- **Design Pattern**: Command Pattern (CLI interface)
- **Algorithm**: Exhaustive Grid Search with Train/Valid/Test Splits
- **Big O**: O(k × n × m / p) where k = parameter combinations, n = games, m = data points per game, p = workers
- **Execution**: Synchronous, uses ThreadPoolExecutor for parallelization
- **Output**: Filesystem-based (CSV, JSON files)

**Evidence**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:1-11`
- **Content**:
  ```python
  """
  Design Pattern: Map-Reduce Pattern for parallel execution
  Algorithm: Exhaustive Grid Search with Train/Valid/Test Splits
  Big O: O(k × n × m / p) where k = parameter combinations, n = games, m = data points per game, p = workers
  """
  ```

**Simulation Page Architecture**:
- **Design Pattern**: Service Pattern (API endpoint) + Module Pattern (JavaScript)
- **Algorithm**: API calls and result rendering
- **Big O**: O(1) for API calls, O(n) for rendering where n = number of trades
- **Execution**: Async with progress polling
- **Output**: JSON response with embedded results

**Evidence**:
- **File**: `webapp/static/js/simulation.js:1-7`
- **Content**:
  ```javascript
  /**
   * Design Pattern: Module Pattern for simulation UI
   * Algorithm: API calls and result rendering
   * Big O: O(1) for API calls, O(n) for rendering where n = number of trades
   */
  ```

### Code Quality Assessment

### Complexity Analysis
- **Cyclomatic Complexity**: 
  - Grid search script: Medium (main function has multiple branches for parameter validation)
  - Simulation page JS: Low-Medium (straightforward event handlers and API calls)
- **Cognitive Complexity**: 
  - Grid search script: Medium (complex parameter handling and result aggregation)
  - Simulation page JS: Low (clear separation of concerns)
- **Technical Debt Ratio**: Low (both implementations are relatively clean)

### Maintainability Metrics
- **Code Coverage**: N/A (no tests currently for webapp UI)
- **Test Quality**: N/A (UI testing not implemented)
- **Documentation Coverage**: 
  - Grid search script: Good (docstrings, comments)
  - Simulation page: Good (inline comments, function documentation)

### Performance Baseline
- **Response Time**: 
  - Grid search: N/A (long-running, 1-3 hours)
  - Simulation API: <5s for 500 games (from logs)
- **Memory Usage**: 
  - Grid search: Moderate (loads all results into memory)
  - Simulation: Low (streams results)
- **Database Performance**: 
  - Grid search: Multiple queries per combination (optimized with connection pooling)
  - Simulation: Single query per game

### Dependencies Analysis
- **External Dependencies**: 
  - Grid search: `psycopg`, `rich` (progress bars), `concurrent.futures`
  - Simulation: FastAPI, same database libraries
- **Internal Dependencies**: 
  - Grid search: `scripts.trade.simulate_trading_strategy` (get_aligned_data, simulate_trading_strategy)
  - Simulation: Same simulation functions
- **Infrastructure Dependencies**: 
  - Database: PostgreSQL via `DATABASE_URL`
  - Web server: FastAPI (already running)

## Technical Assessment

### Design Pattern Analysis

### Current Patterns in Use

#### Design Pattern Analysis: Command Pattern (Grid Search CLI)

**Pattern Name**: Command Pattern  
**Pattern Category**: Behavioral  
**Pattern Intent**: Encapsulate request as an object, allowing parameterization and queuing

**Implementation**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:434-476`
- **Content**: argparse-based CLI with 20+ parameters
- **Execution**: Direct function call with parsed arguments

**Benefits**:
- Flexible parameter configuration
- Easy to script and automate
- Clear separation of configuration and execution

**Trade-offs**:
- Requires CLI knowledge
- No real-time feedback
- Results in filesystem only

**Why This Pattern**: Standard Python CLI pattern, works well for batch processing

#### Design Pattern Analysis: Service Pattern (Simulation API)

**Pattern Name**: Service Pattern  
**Pattern Category**: Architectural  
**Pattern Intent**: Encapsulate business logic in service layer accessible via API

**Implementation**:
- **File**: `webapp/api/endpoints/simulation.py:51-138`
- **Content**: FastAPI endpoint that calls simulation functions
- **Execution**: Async HTTP request/response

**Benefits**:
- Accessible from web UI
- Can add progress tracking
- Results returned as JSON

**Trade-offs**:
- Requires HTTP overhead
- Must handle async execution for long operations

**Why This Pattern**: Enables web integration, follows RESTful principles

#### Design Pattern Analysis: Observer Pattern (Progress Polling)

**Pattern Name**: Observer Pattern (via polling)  
**Pattern Category**: Behavioral  
**Pattern Intent**: Notify observers of state changes

**Implementation**:
- **File**: `webapp/static/js/simulation.js:46-76`
- **Content**: Polls `/api/simulation/progress/{request_id}` every 500ms
- **Execution**: JavaScript setTimeout-based polling

**Benefits**:
- Simple to implement
- Works with stateless HTTP
- Real-time updates

**Trade-offs**:
- Polling overhead (500ms intervals)
- Not true push notifications

**Why This Pattern**: Simple, works with existing HTTP infrastructure

### Missing Patterns
- **Missing Pattern 1**: WebSocket Pattern for real-time progress (could replace polling, but adds complexity)
- **Missing Pattern 2**: Repository Pattern for grid search results (currently filesystem-based)

### Algorithm Analysis

### Current Algorithms

#### Algorithm Analysis: Grid Search

**Algorithm Name**: Exhaustive Grid Search  
**Algorithm Type**: Search/Optimization  
**Big O Notation**: 
- Time Complexity: O(k × n × m / p) where k = combinations, n = games, m = data points, p = workers
- Space Complexity: O(k) for storing results

**Algorithm Description**:
- Generates all valid (entry, exit) threshold combinations
- Tests each combination on train/valid/test splits
- Parallelizes across workers using ThreadPoolExecutor
- Selects best combination based on train ranking + valid selection

**Use Case**: 
- Hyperparameter optimization for trading strategy
- Need to test many parameter combinations systematically

**Performance Characteristics**:
- Best Case: O(k × n × m / p) (always exhaustive)
- Average Case: O(k × n × m / p)
- Worst Case: O(k × n × m / p)
- Memory Usage: O(k) for results storage

**Why This Algorithm**: 
- Guarantees finding best combination in search space
- Parallelizable for performance
- Deterministic results

**Evidence**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:94-134`
- **Content**: `generate_grid()` function creates all valid combinations
- **File**: `scripts/trade/grid_search_hyperparameters.py:373-415`
- **Content**: `process_combination()` runs simulation for each combination

### Optimization Opportunities
- **Algorithm 1**: Could use Bayesian Optimization instead of exhaustive search (O(log k) vs O(k)) but adds complexity
- **Algorithm 2**: Current implementation is already optimized with parallelization

### Performance Analysis

### Baseline Metrics
- **Response Time**: 
  - Grid search: 1-3 hours for full search (100+ combinations, 100+ games)
  - Simulation: <5s for 500 games
- **Throughput**: 
  - Grid search: ~2-5 combinations/minute (depends on games and workers)
  - Simulation: ~100 games/second (parallelized)
- **Memory Usage**: 
  - Grid search: Moderate (stores all results in memory before writing)
  - Simulation: Low (streams results)

**Evidence**:
- **File**: `scripts/trade/grid_search_hyperparameters.py:618-640`
- **Content**: Progress tracking shows total work units = combinations × total games
- **File**: Terminal output shows `7172/42420` progress (16.9% complete)

### Bottleneck Analysis
- **Primary Bottleneck**: Database queries per game (mitigated by connection pooling)
- **Secondary Bottleneck**: Simulation computation per combination (mitigated by parallelization)
- **Tertiary Bottleneck**: Result aggregation (minimal, in-memory operations)

## Evidence and Proof

### MANDATORY: File Content Verification

**Grid Search Parameters** (verified from source):
- **File**: `scripts/trade/grid_search_hyperparameters.py:434-474`
- **File**: `scripts/trade/grid_search_hyperparameters.py:69-91` (Config dataclass)

**User-Facing Parameters** (should be exposed in web UI):
1. **Input Selection**:
   - `season` (str) - Season label selector (e.g., "2025-26")
   - Note: `game_list` (file upload) is CLI-only and not appropriate for web UI - removed from user-facing options
2. **Grid Search Range** (core functionality):
   - `entry_min` (float, default: 0.02) - Minimum entry threshold
   - `entry_max` (float, default: 0.10) - Maximum entry threshold
   - `entry_step` (float, default: 0.01) - Entry threshold step size
   - `exit_min` (float, default: 0.00) - Minimum exit threshold
   - `exit_max` (float, default: 0.05) - Maximum exit threshold
   - `exit_step` (float, default: 0.005) - Exit threshold step size
3. **Trading Parameters** (affects results):
   - `bet_amount` (float, default: 20.0) - Bet amount in dollars per trade
   - `enable_fees` (bool, default: True) - Enable Kalshi trading fees
   - `slippage_rate` (float, default: 0.0) - Slippage rate as decimal
4. **Data Filtering** (same as simulation page):
   - `exclude_first_seconds` (int, default: 60) - Exclude first N seconds of game
   - `exclude_last_seconds` (int, default: 60) - Exclude last N seconds of game
   - `use_trade_data` (bool, default: True) - Use trade-derived data vs candlesticks
5. **Data Split** (user control over train/valid/test):
   - `train_ratio` (float, default: 0.70) - Training set ratio
   - `valid_ratio` (float, default: 0.15) - Validation set ratio
   - `test_ratio` (float, default: 0.15) - Test set ratio
   - Note: Must sum to 1.0 (validated in UI)
6. **Selection Criteria** (affects final selection):
   - `top_n` (int, default: 10) - Top N train combos to consider for selection
   - `min_trade_count` (int, default: 200) - Minimum trades required for valid combo

**Internal/Technical Parameters** (should NOT be exposed in web UI):
- `workers` (int) - Number of parallel workers - Auto-set based on system resources
- `seed` (int) - Random seed - Fixed for reproducibility (default: 42)
- `output_dir` (str) - Output directory - NOT NEEDED (no file outputs, data returned in API response)
- `verbose` (bool) - Debug logging - Not relevant for web UI
- `dsn` (str) - Database connection - Uses DATABASE_URL env var (server-side only)
- `max_games` (int) - Limit games for testing - Could be hidden in "Advanced" section if needed
- `max_combinations` (int) - Limit combinations for testing - Could be hidden in "Advanced" section if needed

**Total User-Facing Parameters**: 17 parameters (reduced from 25 by removing internal/technical options and `game_list` file upload)

**Grid Search Outputs** (CLI script outputs - NOT needed for API):
- **File**: `scripts/trade/grid_search_hyperparameters.py:698-818`
- **CLI Output Files** (for reference, but API won't write these):
  1. `train_games.json` - List of game IDs for training split
  2. `valid_games.json` - List of game IDs for validation split
  3. `test_games.json` - List of game IDs for test split
  4. `grid_results_train.csv` - CSV results for training set
  5. `grid_results_valid.csv` - CSV results for validation set
  6. `grid_results_test.csv` - CSV results for test set
  7. `grid_results_train.json` - JSON results with metadata for training set
  8. `grid_results_valid.json` - JSON results with metadata for validation set
  9. `grid_results_test.json` - JSON results with metadata for test set
  10. `final_selection.json` - Best parameter combination with metrics

**API Response Structure** (NO FILE OUTPUTS):
- All data returned in JSON response:
  - `final_selection`: Best combination with metrics
  - `validation_results`: Array of all validation results
  - `test_results`: Array of all test results
  - `training_results`: Array of top N training results only
  - `pattern_detection`: Pattern analysis object
  - `visualizations`: Object with URLs to PNG images
  - `metadata`: Search space, num games, num combinations, timestamp, game splits

**Visualization Script Outputs** (verified from source):
- **File**: `scripts/trade/analyze_grid_search_results.py:396-475`
- **Visualization Files** (generated in `plots/` subdirectory):
  1. `profit_heatmap_train.png` - Profit heatmap for training set
  2. `profit_heatmap_valid.png` - Profit heatmap for validation set
  3. `marginal_effects.png` - Marginal effects of entry/exit thresholds
  4. `tradeoff_scatter.png` - Tradeoff between trade frequency and profitability
  5. `profit_factor_heatmap_valid.png` - Profit factor heatmap for validation set
- **Pattern Detection**: Returns structured data with:
  - Profit-positive region boundary
  - Monotonicity analysis (entry/exit thresholds)
  - Robustness assessment (broad plateau vs sharp peak)
  - Stability check (train vs valid correlation)
  - Optimal region identification

**CSV Columns** (verified from source):
- **File**: `scripts/trade/grid_search_hyperparameters.py:703-707`
- **Columns**: `entry_threshold`, `exit_threshold`, `net_profit_dollars`, `num_trades`, `win_rate`, `avg_net_profit_per_trade`, `profit_factor`, `max_drawdown`, `total_fees`, `avg_hold_time`, `is_valid`

**Simulation Progress Pattern** (verified from source):
- **File**: `webapp/api/endpoints/simulation.py:813-822`
- **Endpoint**: `GET /api/simulation/progress/{request_id}`
- **Response**: `{"status": "running|complete|error", "current": int, "total": int}`
- **File**: `webapp/static/js/simulation.js:46-76`
- **Polling**: Every 500ms, stops on `complete` or `error`

**Simulation Page UI Pattern** (verified from source):
- **File**: `webapp/static/templates/simulation.html:16-65`
- **Structure**: Form inputs, loading indicator, results section
- **File**: `webapp/static/js/simulation.js:894-1015`
- **Initialization**: `initializeSimulationPage()` sets up event handlers

## Recommendations

### Immediate Actions (Priority: High)

#### Recommendation 1: Create Grid Search API Endpoint (Integrated Backend)

**Specific Action**: Create `webapp/api/endpoints/grid_search.py` with integrated backend functions (not script wrappers)

**Files to Modify**: 
- New: `webapp/api/endpoints/grid_search.py` (API endpoint)
- Modified: `webapp/api/__init__.py` or router registration (register endpoint)

**Estimated Effort**: 6-8 hours (increased due to proper integration)

**Risk Level**: Medium
- Risk: Long-running operations need proper async handling
- Mitigation: Use BackgroundTasks or separate worker process, implement timeout
- Risk: Importing functions from scripts (similar to simulation endpoint pattern)
- Mitigation: Follow existing pattern from `simulation.py` endpoint

**Success Metrics**: 
- Endpoint accepts all 17 user-facing parameters (internal params auto-set)
- Returns request_id immediately
- Executes grid search asynchronously using imported functions (not subprocess)
- Returns optimized results (only necessary data, not redundant training set details)
- Automatically generates visualizations using imported functions
- Returns visualization paths and pattern data in completion response
- Clean API design - seamless feature, not script wrapper

**Implementation Approach**:
1. **Import Functions Directly** (like simulation endpoint):
   - Use `importlib.util` to import from `scripts/trade/grid_search_hyperparameters.py`
   - Import key functions: `generate_grid()`, `process_combination()`, `run_simulation_for_games()`, etc.
   - Use `importlib.util` to import from `scripts/trade/analyze_grid_search_results.py`
   - Import: `create_heatmap()`, `create_marginal_effects()`, `create_tradeoff_scatter()`, `detect_patterns()`
   - Reuse `get_aligned_data()` and `simulate_trading_strategy()` from simulation endpoint

2. **Create FastAPI endpoint `/api/grid-search/run` (POST)**:
   - Accept all grid search parameters as query params or JSON body
   - Validate parameters (e.g., split ratios sum to 1.0)
   - Generate unique request_id
   - Auto-set internal parameters:
     - `workers`: Auto-detect CPU count or use default (8)
     - `seed`: Fixed at 42 for reproducibility
     - `output_dir`: NOT NEEDED - No file outputs, data returned in API response

3. **Background Task Execution**:
   - Start background task that calls imported functions directly (not subprocess)
   - Run grid search using imported functions:
     - Generate grid combinations
     - Process combinations in parallel (ThreadPoolExecutor)
     - Aggregate results by split
   - **Filter Training Set Results** (reduce redundancy):
     - Training set is only used for ranking (top N selection)
     - Return only top N training results (not all combinations)
     - Full validation and test results needed (used for selection and evaluation)
   - After grid search completes, prepare data for client-side visualization:
     - Call `detect_patterns()` to get pattern analysis
     - **NO SERVER-SIDE VISUALIZATION GENERATION** - Return raw data for client-side rendering
   - **NO FILE OUTPUTS** - All data returned in API response:
     - Training: Top N results only (for ranking context)
     - Validation: All results (for selection) - includes raw data for visualization
     - Test: All results (for final evaluation)
     - Final selection: Best combination with metrics
     - Pattern detection: Full analysis results
     - Visualization data: Raw data arrays for client-side Chart.js rendering
     - Metadata: Search space, num games, num combinations, timestamp

4. **Progress Tracking**:
   - Store progress in thread-safe dictionary (like simulation progress)
   - Update progress as combinations complete
   - Track: current/total combinations, current combination being processed

5. **Return Optimized Response** (NO FILE OUTPUTS, CLIENT-SIDE RENDERING):
   - Return request_id immediately
   - On completion, return JSON response with:
     - `final_selection`: Best combination with train/valid/test metrics
     - `validation_results`: All combinations (needed for selection and visualization)
     - `test_results`: All combinations (needed for evaluation)
     - `training_results`: Top N only (for context, not full set)
     - `pattern_detection`: Full analysis results
     - `visualization_data`: Raw data arrays for client-side Chart.js rendering:
       - `heatmap_data`: 2D array for profit heatmaps (entry × exit → profit)
       - `marginal_effects_data`: Arrays for entry/exit marginal effects
       - `tradeoff_data`: Arrays for scatter plot (num_trades vs profit)
     - `metadata`: Search space, num games, num combinations, timestamp, etc.
   - **No CSV/JSON files written to disk** - All data in API response
   - **No PNG files generated** - Charts rendered client-side using Chart.js (like simulation page)

**Design Pattern**: Service Pattern + Background Task Pattern + Function Import Pattern
**Algorithm**: Same as grid search script (O(k × n × m / p))
**Big O**: Same as grid search script, but reduced response size (O(top_n) for train vs O(k) for valid/test)

**Key Optimization - Training Set Results**:
- **Problem**: Training set has many combinations (k combinations), but only used for ranking (top N selection)
- **Solution**: Return only top N training results (not all combinations)
- **Rationale**: 
  - Training set is only used to identify top N candidates
  - Full training results are redundant for API response
  - Validation and test results needed in full (for selection and evaluation)
- **Implementation**:
  - After grid search completes, sort training results by `net_profit_dollars` (descending)
  - Return only top N training results (where N = `top_n` parameter, default 10)
  - Return full validation results (needed for selection among top N)
  - Return full test results (needed for final evaluation)
- **Data Reduction**: 
  - If k = 100 combinations and top_n = 10:
    - Training: 10 results (90% reduction)
    - Validation: 100 results (full set)
    - Test: 100 results (full set)
  - Total response: 210 results instead of 300 (30% reduction)

**Pros**:
- Proper backend integration (not script wrapper)
- Reuses existing functions directly (no subprocess overhead)
- Optimized data transfer (filtered training results)
- Seamless feature design
- Follows existing simulation endpoint pattern
- Better error handling (Python exceptions, not subprocess errors)

**Cons**:
- More complex than script wrapper (but better architecture)
- Need to refactor script functions to be importable (may already be done)
- Memory usage for storing progress and results

#### Recommendation 2: Create Progress Tracking Endpoint

**Specific Action**: Create `GET /api/grid-search/progress/{request_id}` endpoint

**Files to Modify**: 
- Modified: `webapp/api/endpoints/grid_search.py` (add progress endpoint)

**Estimated Effort**: 1-2 hours

**Risk Level**: Low
- Risk: Thread-safety for progress updates
- Mitigation: Use same locking pattern as simulation progress

**Success Metrics**: 
- Returns current progress (completed/total work units)
- Thread-safe updates
- Handles missing request_id gracefully

**Implementation Approach**:
1. Store progress in thread-safe dictionary: `_grid_search_progress: dict[str, dict]`
2. Update progress from background task as combinations complete
3. Endpoint returns `{"status": "running|complete|error", "current": int, "total": int, "current_combo": str}`
4. Include current combination being processed for better UX

**Design Pattern**: Observer Pattern (via polling)
**Algorithm**: O(1) lookup
**Big O**: O(1)

**Pros**:
- Simple to implement
- Reuses simulation progress pattern
- Real-time updates

**Cons**:
- Polling overhead (500ms intervals)
- Not true push notifications

#### Recommendation 3: Create Grid Search HTML Template

**Specific Action**: Create `webapp/static/templates/grid-search.html` with all parameters as form inputs

**Files to Modify**: 
- New: `webapp/static/templates/grid-search.html` (HTML template)

**Estimated Effort**: 3-4 hours

**Risk Level**: Low
- Risk: Complex form with many inputs may be overwhelming
- Mitigation: Group inputs logically, use collapsible sections, provide defaults

**Success Metrics**: 
- All 17 user-facing parameters accessible via form inputs
- Logical grouping:
  - **Input Selection**: Season selector dropdown (populated from available seasons in database)
  - **Grid Search Range**: Entry/exit min/max/step (6 inputs)
  - **Trading Parameters**: Bet amount, enable fees, slippage rate (3 inputs)
  - **Data Filtering**: Exclude first/last seconds, use trade data (3 inputs)
  - **Data Split**: Train/valid/test ratios (3 inputs, must sum to 1.0)
  - **Selection Criteria**: Top N, min trade count (2 inputs)
- Consistent styling with simulation page
- Validation feedback (e.g., split ratios sum to 1.0, grid ranges valid)
- Internal parameters (workers, seed, output_dir) auto-set by server

**Implementation Approach**:
1. Create HTML template following simulation page structure
2. Group parameters into sections (matching user-facing parameters above):
   - **Input Selection**: Season selector dropdown (populated via API call to `/api/games` to get available seasons, default: "2025-26")
   - **Grid Search Range**: Entry/exit min/max/step (6 number inputs with labels)
   - **Trading Parameters**: Bet amount, enable fees (checkbox), slippage rate (3 inputs)
   - **Data Filtering**: Exclude first/last seconds, use trade data (checkbox) (3 inputs)
   - **Data Split**: Train/valid/test ratios (3 inputs with validation, must sum to 1.0)
   - **Selection Criteria**: Top N, min trade count (2 inputs)
3. Use same CSS classes as simulation page for consistency (`sim-input-group`, etc.)
4. Add client-side validation:
   - Split ratios must sum to 1.0 (show error if not)
   - Grid ranges valid (min < max, step > 0)
   - Entry/exit thresholds reasonable (0-1 range)
5. Add "Run Grid Search" button with loading indicator (same pattern as simulation page)
6. Hide internal parameters (workers, seed, output_dir) - these are auto-set by server

**Design Pattern**: Template Pattern
**Algorithm**: N/A (static HTML)
**Big O**: N/A

**Pros**:
- Clear parameter organization
- Consistent with existing UI
- Easy to maintain

**Cons**:
- Many inputs may be overwhelming
- Requires good UX design

#### Recommendation 4: Create Grid Search JavaScript Module

**Specific Action**: Create `webapp/static/js/grid-search.js` for UI logic, progress polling, and results rendering

**Files to Modify**: 
- New: `webapp/static/js/grid-search.js` (JavaScript module)

**Estimated Effort**: 5-7 hours (increased due to visualization integration)

**Risk Level**: Medium
- Risk: Complex results rendering (CSV/JSON parsing, visualization display)
- Mitigation: Reuse simulation page rendering patterns, use existing chart libraries, serve PNG images from plots directory

**Success Metrics**: 
- Progress polling works (updates every 500ms)
- Results displayed in tables
- Visualizations displayed as images (PNG files)
- Pattern detection summary displayed
- Downloadable CSV/JSON files
- Error handling and user feedback

**Implementation Approach**:
1. Create `initializeSeasonSelector()` function:
   - Query `/api/games` endpoint to get available seasons (or query database directly)
   - Populate season dropdown with available seasons
   - Set default to most recent season (e.g., "2025-26")
2. Create `runGridSearch()` function that:
   - Collects all form parameters (including selected season)
   - Validates parameters (client-side)
   - Calls `/api/grid-search/run` endpoint
   - Gets request_id
   - Starts progress polling
2. Create `pollGridSearchProgress()` function (similar to simulation):
   - Polls `/api/grid-search/progress/{request_id}` every 500ms
   - Updates progress indicator: "Processing: X/Y combinations (Z%)"
   - Shows current combination being processed
   - Stops on `complete` or `error`
3. Create `renderGridSearchResults()` function:
   - Fetches results from API endpoint (includes visualization paths and pattern data)
   - Parses JSON results
   - Renders tables for train/valid/test results (top N combinations)
   - Renders final selection prominently with metrics
   - Displays visualizations:
     - Profit heatmaps (train and valid) as `<img>` tags pointing to PNG files
     - Marginal effects plot
     - Tradeoff scatter plot
     - Profit factor heatmap
   - Displays pattern detection summary:
     - Profit-positive region boundary
     - Monotonicity analysis
     - Robustness assessment
     - Stability check
     - Optimal region
   - Provides download links for CSV/JSON files
4. Create `renderPatternSummary()` function:
   - Formats pattern detection results as cards/sections
   - Highlights key insights (robust plateau vs sharp peak, stability warnings)
   - Uses app styling (consistent with simulation page)
5. Create `initializeGridSearchPage()` function:
   - Sets up event handlers
   - Validates form inputs
   - Handles form submission

**Design Pattern**: Module Pattern
**Algorithm**: O(n) for rendering where n = number of combinations
**Big O**: O(n) for results rendering

**Pros**:
- Reuses simulation page patterns
- Clear separation of concerns
- Easy to test
- Visualizations provide immediate insights

**Cons**:
- Results rendering may be complex
- No CSV/JSON parsing needed (data already in JSON from API response)
- PNG files served via URLs (stored temporarily in cache, not permanent files)

#### Recommendation 5: Add Routing for Grid Search Page

**Specific Action**: Add route in `webapp/static/js/routing.js` and navigation link

**Files to Modify**: 
- Modified: `webapp/static/js/routing.js` (add route)
- Modified: Navigation HTML (add link to grid search page)

**Estimated Effort**: 1 hour

**Risk Level**: Low
- Risk: None (standard routing addition)
- Mitigation: Follow existing routing pattern

**Success Metrics**: 
- Grid search page accessible via navigation
- Route renders template correctly
- Page initializes properly

**Implementation Approach**:
1. Add `showGridSearchPageView()` function in `routing.js`
2. Follow same pattern as `showSimulationPageView()`
3. Add navigation link in main navigation
4. Call `initializeGridSearchPage()` after template renders

**Design Pattern**: Router Pattern
**Algorithm**: O(1) route lookup
**Big O**: O(1)

**Pros**:
- Consistent with existing routing
- Simple to implement

**Cons**:
- None

### Immediate Actions (Priority: High) - Updated

#### Recommendation 6: Client-Side Visualization Rendering (Chart.js)

**Specific Action**: Return raw data in API response and render visualizations client-side using Chart.js (like simulation page)

**Files to Modify**: 
- Modified: `webapp/api/endpoints/grid_search.py` (import and call visualization functions)
- Modified: `webapp/static/js/grid-search.js` (display visualizations in results section)
- Modified: `webapp/static/templates/grid-search.html` (add visualization containers)

**Estimated Effort**: 3-4 hours

**Risk Level**: Low
- Risk: Chart.js heatmap support (may need plugin or custom rendering)
- Mitigation: Use Chart.js for line/scatter (already used), use Plotly.js or custom canvas for heatmaps
- Risk: Data transformation for client-side rendering
- Mitigation: Transform data in backend before returning (pivot for heatmaps, group for marginal effects)

**Success Metrics**: 
- All visualizations rendered client-side using Chart.js (consistent with simulation page)
- Interactive charts (hover tooltips, responsive)
- All 5 visualization types displayed (heatmaps, marginal effects, scatter, pattern summary)
- Pattern detection results included in API response

**Implementation Approach**:
1. **Backend: Return Raw Data** (in grid_search.py):
   - After grid search completes, call `detect_patterns()` function (import from analyze script)
   - Transform results data for client-side rendering:
     - **Heatmap data**: Pivot validation results to 2D array (entry × exit → profit)
     - **Marginal effects**: Group by entry/exit threshold, calculate mean/std
     - **Tradeoff scatter**: Extract num_trades and net_profit_dollars arrays
   - Return in API response:
     ```json
     {
       "visualization_data": {
         "profit_heatmap_valid": {
           "entry_thresholds": [0.02, 0.03, ...],
           "exit_thresholds": [0.00, 0.005, ...],
           "profit_matrix": [[profit_00, profit_01, ...], [profit_10, ...], ...],
           "chosen_entry": 0.05,
           "chosen_exit": 0.01
         },
         "marginal_effects": {
           "entry": {
             "thresholds": [0.02, 0.03, ...],
             "mean_profit": [100, 150, ...],
             "std_profit": [20, 25, ...]
           },
           "exit": { ... }
         },
         "tradeoff_scatter": {
           "num_trades": [200, 250, ...],
           "net_profit": [100, 150, ...],
           "entry_threshold": [0.02, 0.03, ...]
         }
       },
       "pattern_detection": { ... }
     }
     ```

2. **Frontend: Render Charts** (in grid-search.js):
   - Use Chart.js (already loaded in app) for line and scatter charts
   - **Marginal Effects**: Render as line charts (same pattern as simulation page)
   - **Tradeoff Scatter**: Render as scatter plot (Chart.js scatter type)
   - **Heatmaps**: Use Chart.js with heatmap plugin, or Plotly.js, or custom canvas rendering
   - Create canvas elements in HTML template
   - Render charts after results are received (similar to `renderQuartilesChart()` pattern)

3. **Chart Rendering Functions**:
   ```javascript
   function renderProfitHeatmap(heatmapData) {
     // Use Chart.js heatmap plugin or Plotly.js or custom canvas
     // Highlight chosen params with marker
   }
   
   function renderMarginalEffects(marginalData) {
     // Line charts (Chart.js) - same as simulation page
     // Entry threshold effect
     // Exit threshold effect
   }
   
   function renderTradeoffScatter(scatterData) {
     // Scatter plot (Chart.js) - same as simulation page
   }
   ```

**Design Pattern**: Client-Side Rendering Pattern + Data Transformation Pattern
**Algorithm**: O(k) for data transformation where k = combinations, O(k) for client-side rendering
**Big O**: O(k) for both backend transformation and client-side rendering

**Pros**:
- Consistent with existing webapp visualization style (Chart.js)
- Interactive charts (hover, zoom, responsive)
- No server-side image generation overhead
- Better UX (interactive, responsive)
- No file storage needed
- Pattern detection still provides insights
- Reuses Chart.js already loaded in app

**Cons**:
- Requires Chart.js heatmap plugin or alternative (Plotly.js) for heatmaps
- Data transformation needed in backend (but minimal overhead)
- Client-side rendering adds some JavaScript complexity

**Evidence**:
- **File**: `scripts/trade/analyze_grid_search_results.py:396-475`
- **Content**: Main function that generates all visualizations
- **Visualizations Generated**:
  1. Profit heatmap (train) - `create_heatmap()` with `net_profit_dollars`
  2. Profit heatmap (valid) - `create_heatmap()` with `net_profit_dollars`
  3. Marginal effects - `create_marginal_effects()` (entry/exit threshold effects)
  4. Tradeoff scatter - `create_tradeoff_scatter()` (trades vs profit)
  5. Profit factor heatmap (valid) - `create_heatmap()` with `profit_factor`
- **Pattern Detection**: `detect_patterns()` returns:
  - Profit-positive region boundary
  - Monotonicity analysis
  - Robustness assessment (plateau vs peak)
  - Stability check (train vs valid)
  - Optimal region identification

### Short-term Improvements (Priority: Medium)

#### Recommendation 7: Add Interactive Visualizations (Optional Enhancement)

**Specific Action**: Convert static PNGs to interactive Chart.js visualizations for better UX

**Files to Modify**: 
- Modified: `webapp/static/js/grid-search.js` (add Chart.js rendering)
- Modified: API endpoint (return raw data instead of just PNG paths)

**Estimated Effort**: 4-6 hours

**Risk Level**: Low
- Risk: Chart.js heatmap plugin may not exist
- Mitigation: Use existing PNGs as fallback, or use Plotly.js for heatmaps

**Success Metrics**: 
- Interactive heatmaps with hover tooltips
- Zoomable/pannable charts
- Better mobile experience

**Implementation Approach**:
1. Return raw CSV data from API (already available)
2. Parse data in JavaScript
3. Create Chart.js heatmap using custom plugin or Plotly.js
4. Add interactivity (hover, zoom, pan)

**Design Pattern**: Presentation Pattern
**Algorithm**: O(k) for rendering where k = combinations
**Big O**: O(k)

**Pros**:
- Better user experience
- Interactive exploration
- No server-side image generation needed

**Cons**:
- More complex JavaScript
- May require additional libraries
- Performance concerns for large grids

### Long-term Strategic Changes (Priority: Low)

#### Recommendation 8: Add Grid Search History

**Specific Action**: Store grid search runs in database for comparison

**Files to Modify**: 
- New: Database migration for grid_search_runs table
- Modified: API endpoint (store results in DB)
- Modified: UI (show history of runs)

**Estimated Effort**: 8-12 hours

**Risk Level**: Medium
- Risk: Database schema design
- Mitigation: Store metadata and references to output files

**Success Metrics**: 
- Users can view past grid search runs
- Compare results across runs
- Filter/search runs by parameters

## Implementation Plan

### Phase 1: API Endpoint Foundation (Duration: 5-7 hours)
**Objective**: Create async grid search API endpoint with progress tracking and visualization generation
**Dependencies**: Grid search script (no changes needed), visualization script (no changes needed), database connection
**Deliverables**: Working API endpoint that accepts parameters, returns request_id, generates visualizations, and serves visualization images

#### Tasks
- **[Task 1]**: Create `webapp/api/endpoints/grid_search.py` with integrated backend functions
  - **Files**: New file
  - **Effort**: 4-5 hours (increased due to proper integration)
  - **Prerequisites**: Understanding of grid search script structure and function imports
  - **Details**:
    - Import functions from `grid_search_hyperparameters.py` using `importlib.util` (like simulation endpoint)
    - Import key functions: `generate_grid()`, `process_combination()`, `run_simulation_for_games()`, etc.
    - Import visualization functions from `analyze_grid_search_results.py`
    - Design API to return optimized results (filter training set to top N only)
    - Implement proper error handling and progress tracking
- **[Task 2]**: Implement progress tracking storage
  - **Files**: `webapp/api/endpoints/grid_search.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1 complete
- **[Task 3]**: Integrate visualization script call after grid search completes
  - **Files**: `webapp/api/endpoints/grid_search.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Task 2 complete
  - **Details**: 
    - Call `analyze_grid_search_results.py` script after grid search finishes
    - Store visualization paths and pattern data in results
    - Return visualization paths and pattern JSON in completion response
- **[Task 4]**: Create endpoint to serve visualization images
  - **Files**: `webapp/api/endpoints/grid_search.py`
  - **Effort**: 30 minutes
  - **Prerequisites**: Task 3 complete
  - **Details**: 
    - Create `GET /api/grid-search/results/{request_id}/visualizations/{filename}` endpoint
    - Serves PNG files from `output_dir/plots/` directory
    - Returns image with proper content-type headers

### Phase 2: HTML Template (Duration: 3-4 hours)
**Objective**: Create grid search page HTML template with all parameters
**Dependencies**: None (can be done in parallel with Phase 1)
**Deliverables**: Complete HTML template with form inputs for all parameters

#### Tasks
- **[Task 1]**: Create `webapp/static/templates/grid-search.html`
  - **Files**: New file
  - **Effort**: 2-3 hours
  - **Prerequisites**: Understanding of simulation page structure
- **[Task 2]**: Add form validation and styling
  - **Files**: `webapp/static/templates/grid-search.html`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1 complete

### Phase 3: JavaScript Logic (Duration: 5-7 hours)
**Objective**: Implement UI logic, progress polling, results rendering, and visualization display
**Dependencies**: Phase 1 complete (API endpoint), Phase 2 complete (HTML template)
**Deliverables**: Functional grid search page with progress tracking, results display, and visualizations

#### Tasks
- **[Task 1]**: Create `webapp/static/js/grid-search.js` with API calls
  - **Files**: New file
  - **Effort**: 2 hours
  - **Prerequisites**: Phase 1 complete
- **[Task 2]**: Implement progress polling
  - **Files**: `webapp/static/js/grid-search.js`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1 complete
- **[Task 3]**: Implement results rendering (tables, final selection)
  - **Files**: `webapp/static/js/grid-search.js`
  - **Effort**: 2 hours
  - **Prerequisites**: Task 2 complete
- **[Task 4]**: Implement client-side visualization rendering (Chart.js)
  - **Files**: `webapp/static/js/grid-search.js`, `webapp/static/templates/grid-search.html`
  - **Effort**: 3-4 hours
  - **Prerequisites**: Task 3 complete, visualization data returned in API response
  - **Details**:
    - Add canvas elements in HTML template for each chart type
    - Render profit heatmaps using Chart.js heatmap plugin or Plotly.js or custom canvas
    - Render marginal effects as line charts (Chart.js) - same pattern as simulation page
    - Render tradeoff scatter as scatter plot (Chart.js) - same pattern as simulation page
    - Highlight chosen parameters on heatmaps with markers
    - Use same Chart.js styling as simulation page (consistent theme)
- **[Task 5]**: Implement pattern detection summary display
  - **Files**: `webapp/static/js/grid-search.js`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 4 complete

### Phase 4: Routing and Integration (Duration: 1-2 hours)
**Objective**: Add routing and navigation for grid search page
**Dependencies**: Phase 2 and Phase 3 complete
**Deliverables**: Grid search page accessible via navigation

#### Tasks
- **[Task 1]**: Add route in `routing.js`
  - **Files**: `webapp/static/js/routing.js`
  - **Effort**: 30 minutes
  - **Prerequisites**: Phase 2 complete
- **[Task 2]**: Add navigation link
  - **Files**: Navigation HTML template
  - **Effort**: 30 minutes
  - **Prerequisites**: Task 1 complete
- **[Task 3]**: Test end-to-end flow
  - **Files**: All
  - **Effort**: 1 hour
  - **Prerequisites**: All phases complete

## Risk Assessment

### Technical Risks
- **Risk 1**: Long-running grid searches may timeout or crash
  - **Probability**: Medium
  - **Impact**: High
  - **Mitigation**: Use background worker process, implement proper error handling, add timeout configuration
  - **Contingency**: Allow users to download partial results, implement resume capability

- **Risk 2**: Memory usage for storing all results
  - **Probability**: Medium
  - **Impact**: Medium
  - **Mitigation**: Stream results to files, only store metadata in memory
  - **Contingency**: Implement pagination for results display

- **Risk 3**: Progress tracking accuracy with parallel workers
  - **Probability**: Low
  - **Impact**: Low
  - **Mitigation**: Use thread-safe progress updates, atomic increments
  - **Contingency**: Show approximate progress if exact count unavailable

### Business Risks
- **Risk 1**: Users may run expensive grid searches accidentally
  - **Probability**: Low
  - **Impact**: Medium
  - **Mitigation**: Add confirmation dialog, show estimated time/cost, limit max combinations
  - **Contingency**: Implement cancellation endpoint

- **Risk 2**: UI may be overwhelming with 25 parameters
  - **Probability**: Medium
  - **Impact**: Low
  - **Mitigation**: Group parameters logically, provide sensible defaults, add "Advanced" toggle
  - **Contingency**: Add parameter presets for common use cases

### Resource Risks
- **Risk 1**: Server resources may be exhausted by long-running searches
  - **Probability**: Low
  - **Impact**: High
  - **Mitigation**: Limit concurrent grid searches, implement queue system
  - **Contingency**: Add resource monitoring and alerts

## Success Metrics and Monitoring

### Performance Metrics
- **Response Time**: 
  - API endpoint: <1s to return request_id (target)
  - Progress updates: <500ms latency (target)
- **Throughput**: 
  - Support 1-2 concurrent grid searches (target)
- **Memory Usage**: 
  - <500MB per grid search (target)

### Quality Metrics
- **Parameter Coverage**: 100% of CLI parameters accessible via UI (target)
- **Progress Accuracy**: ±1% accuracy in progress reporting (target)
- **Error Rate**: <1% failed grid searches (target)

### Business Metrics
- **User Adoption**: Users prefer web UI over CLI (target)
- **Time Saved**: 50% reduction in time to run grid search (target)
- **User Satisfaction**: Positive feedback on UI usability (target)

### Monitoring Strategy
- **Real-time Monitoring**: 
  - Track active grid searches
  - Monitor progress update frequency
  - Alert on errors or timeouts
- **Alert Thresholds**: 
  - Grid search running >4 hours (warning)
  - Progress updates stopped >5 minutes (error)
  - Memory usage >1GB per search (warning)
- **Reporting**: 
  - Log all grid search runs with parameters and results
  - Track success/failure rates
  - Monitor average execution time

## Appendices

### Appendix A: Grid Search Parameters Reference

**User-Facing Parameters** (exposed in web UI):

**Input Selection**:
1. `season` (str): Season label selector dropdown (e.g., "2025-26")
   - Populated from available seasons in database
   - Default: "2025-26" (most recent season)
   - Note: `game_list` file upload is CLI-only and not appropriate for web UI

**Grid Search Range**:
3. `entry_min` (float): Minimum entry threshold (default: 0.02)
4. `entry_max` (float): Maximum entry threshold (default: 0.10)
5. `entry_step` (float): Entry threshold step size (default: 0.01)
6. `exit_min` (float): Minimum exit threshold (default: 0.00)
7. `exit_max` (float): Maximum exit threshold (default: 0.05)
8. `exit_step` (float): Exit threshold step size (default: 0.005)

**Trading Parameters**:
9. `bet_amount` (float): Bet amount in dollars per trade (default: 20.0)
10. `enable_fees` (bool): Enable Kalshi trading fees (default: True)
11. `slippage_rate` (float): Slippage rate as decimal (default: 0.0)

**Data Filtering**:
12. `exclude_first_seconds` (int): Exclude first N seconds of game (default: 60)
13. `exclude_last_seconds` (int): Exclude last N seconds of game (default: 60)
14. `use_trade_data` (bool): Use trade-derived data vs candlesticks (default: True)

**Data Split**:
15. `train_ratio` (float): Training set ratio (default: 0.70)
16. `valid_ratio` (float): Validation set ratio (default: 0.15)
17. `test_ratio` (float): Test set ratio (default: 0.15)
Note: Must sum to 1.0 (validated in UI)

**Selection Criteria**:
17. `top_n` (int): Top N train combos to consider for selection (default: 10)
18. `min_trade_count` (int): Minimum trades required for valid combo (default: 200)

**Internal Parameters** (auto-set by server, NOT exposed in UI):
- `workers` (int): Number of parallel workers - Auto-set based on system resources
- `seed` (int): Random seed - Fixed at 42 for reproducibility
- `output_dir` (str): Output directory - Auto-generated with timestamp/request_id
- `verbose` (bool): Debug logging - Not relevant for web UI
- `dsn` (str): Database connection - Uses DATABASE_URL env var (server-side only)
- `max_games` (int, optional): Limit games for testing - Could be hidden in "Advanced" if needed
- `max_combinations` (int, optional): Limit combinations for testing - Could be hidden in "Advanced" if needed

### Appendix B: Grid Search Output Format Reference

**CSV Files** (one per split: train, valid, test):
- Columns: `entry_threshold`, `exit_threshold`, `net_profit_dollars`, `num_trades`, `win_rate`, `avg_net_profit_per_trade`, `profit_factor`, `max_drawdown`, `total_fees`, `avg_hold_time`, `is_valid`

**JSON Files** (one per split: train, valid, test):
```json
{
  "metadata": {
    "args": {...},
    "timestamp": "ISO8601",
    "git_hash": "string",
    "num_games": {"train": int, "valid": int, "test": int},
    "num_combinations": int,
    "search_space": {
      "entry_range": [min, max, step],
      "exit_range": [min, max, step]
    }
  },
  "results": [...]
}
```

**Final Selection JSON**:
```json
{
  "chosen_params": {
    "entry_threshold": float,
    "exit_threshold": float
  },
  "train_metrics": {...},
  "valid_metrics": {...},
  "test_metrics": {...},
  "selection_method": "string",
  "top_n": int
}
```

**Visualizations** (rendered client-side using Chart.js):
- **NO PNG files generated** - Charts rendered directly in browser using Chart.js (same as simulation page)
- Raw data returned in API response for client-side rendering:
  - `heatmap_data`: 2D array (entry_threshold × exit_threshold → profit_value) for heatmaps
  - `marginal_effects_data`: Arrays for entry/exit threshold marginal effects (line charts)
  - `tradeoff_data`: Arrays for scatter plot (num_trades vs net_profit_dollars)
- Chart types:
  - **Heatmaps**: Use Chart.js with heatmap plugin, or custom canvas rendering, or Plotly.js
  - **Marginal Effects**: Line charts (Chart.js `line` type) - same as simulation page
  - **Tradeoff Scatter**: Scatter plot (Chart.js `scatter` type) - same as simulation page
- Benefits:
  - Interactive charts (hover tooltips, zoom, etc.)
  - Consistent with existing webapp visualization style
  - No server-side image generation overhead
  - Better UX (responsive, interactive)

**Pattern Detection Results** (from `detect_patterns()` function):
```json
{
  "profit_positive_boundary": {
    "entry_thresholds": [float, ...],
    "exit_thresholds": [float, ...],
    "shape": "convex|irregular|none"
  },
  "monotonicity": {
    "entry_threshold": "monotonic increasing|monotonic decreasing|non-monotonic",
    "exit_threshold": "monotonic increasing|monotonic decreasing|non-monotonic"
  },
  "robustness": {
    "type": "broad_plateau|sharp_peak",
    "entry_range": [min, max],
    "exit_range": [min, max],
    "size": int,
    "size_category": "large|medium|small"
  },
  "stability": {
    "top_5_train": [
      {
        "entry": float,
        "exit": float,
        "train_profit": float,
        "valid_profit": float,
        "stable": bool
      }
    ],
    "rank_correlation": float
  },
  "optimal_region": {
    "best_combo": {
      "entry_threshold": float,
      "exit_threshold": float
    },
    "robust_region": {
      "entry_range": [min, max],
      "exit_range": [min, max]
    }
  }
}
```

### Appendix C: Simulation Page Pattern Reference

**Progress Polling**:
- Endpoint: `GET /api/simulation/progress/{request_id}`
- Poll interval: 500ms
- Response: `{"status": "running|complete|error", "current": int, "total": int}`

**Results Display**:
- Simplified view: Key metrics only
- Advanced view: Full details with charts
- Export: Image download

**UI Structure**:
- Form inputs section
- Loading indicator (inline with button)
- Results section (hidden until complete)

### Appendix D: Glossary

- **Grid Search**: Exhaustive search over parameter space
- **Train/Valid/Test Split**: Data splitting for model selection and evaluation
- **Work Unit**: One game simulation for one parameter combination
- **Request ID**: Unique identifier for tracking async operations
- **Progress Polling**: Client-side polling of server for status updates

---

## Document Validation

**IMPORTANT**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Validation Checklist**:
- ✅ Evidence-based analysis with code references
- ✅ File content verification completed
- ✅ Design pattern analysis included
- ✅ Algorithm analysis with Big O notation
- ✅ Implementation plan with phases
- ✅ Risk assessment completed
- ✅ Success metrics defined

