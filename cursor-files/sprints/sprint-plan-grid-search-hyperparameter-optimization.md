# Sprint Plan: Grid Search Hyperparameter Optimization

**Date**: 2025-01-27  
**Sprint Duration**: 5-7 days (40-56 hours total)  
**Sprint Goal**: Implement reproducible grid search for entry/exit threshold optimization with train/valid/test splits, performance visualization, and pattern detection to identify optimal trading strategy parameters  
**Current Status**: Trading simulation exists with default thresholds (entry=0.05, exit=0.02). Strategy shows edge but insufficient profitability after costs. No systematic hyperparameter optimization exists.  
**Target Status**: Grid search script tests all valid threshold combinations across train/valid/test splits, generates visualizations (heatmaps, marginal effects, tradeoff plots), and outputs pattern detection summary with optimal parameter selection.  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/grid_search_hyperparameter_optimization_analysis.md`
- **Current Implementation**: 
  - `scripts/simulate_trading_strategy.py` - Trading simulation logic
  - `webapp/api/endpoints/simulation.py` - Simulation API endpoint
  - `webapp/api/utils/trade_candles.py` - Trade aggregation utilities

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified]
- **QC Results**: [To be verified]
- **Code Coverage**: [To be verified]
- **Build Status**: [To be verified]

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database data** - no INSERT, UPDATE, TRUNCATE, DELETE unless part of sprint plan or tests
- **DO NOT modify database users** - no user management or system changes
- **Read-only database access** - grid search reads game data and runs simulations (no schema changes needed)

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git branching, rebasing, or force-push operations. Commits are allowed when explicitly stated in the sprint plan (e.g., for new features). The intent is to prevent destructive git operations while allowing normal development workflow.

## Sprint Overview

### Business Context
- **Business Driver**: Current trading strategy shows statistical edge but insufficient profitability after accounting for trading costs. Need systematic hyperparameter optimization to find optimal entry/exit thresholds that maximize net profit. Data scientist guidance: "do a hyperparam grid search on the entry/exit, then graph the performance to detect patterns" (not just pick best cell).
- **Success Criteria**: 
  - Grid search script tests all valid threshold combinations with reproducible train/valid/test splits
  - Visualizations (heatmaps, marginal effects, tradeoff plots) clearly show optimal regions and patterns
  - Pattern detection summary identifies robust parameter regions
  - Final selection uses train for ranking, valid for selection, test for reporting only
- **Stakeholders**: Data scientist (providing guidance), trading strategy developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - Trading simulation exists in `scripts/simulate_trading_strategy.py`
  - Default thresholds: entry=0.05, exit=0.02
  - Simulation supports configurable entry/exit thresholds via CLI/API
  - No systematic hyperparameter optimization exists
- **Target System State**: 
  - `scripts/grid_search_hyperparameters.py` - CLI-based grid search runner
  - `scripts/analyze_grid_search_results.py` - Visualization and pattern detection
  - Reproducible train/valid/test splits by game ID (70/15/15)
  - CSV/JSON results per split with comprehensive metrics
  - PNG visualizations (heatmaps, marginal effects, tradeoff scatter, secondary heatmap)
  - Pattern detection summary printed to console
  - `final_selection.json` with chosen parameters and metrics
- **Architecture Impact**: Adds two new scripts, no changes to existing simulation logic
- **Integration Points**: Existing `simulate_trading_strategy.py`, existing database connection utilities

### Sprint Scope
- **In Scope**: 
  - Grid search script with CLI args, deterministic splits, parallel execution
  - Results storage (CSV/JSON per split)
  - Visualization script with required plots
  - Pattern detection summary
  - Documentation (README section or GRID_SEARCH.md)
- **Out of Scope**: 
  - UI preset implementation (deferred to future sprint)
  - Multiple comparisons correction (FDR) - can be added later if needed
  - Web UI for grid search (CLI-only for now)
  - Signal refinement (separate long-term work)
- **Assumptions**: 
  - Simulation logic is correct and tested
  - Sufficient game data exists for train/valid/test splits
  - Default cost settings (enable_fees=True, slippage_rate=0.0) are appropriate
- **Constraints**: 
  - Must ensure no data leakage (deterministic splits by game ID)
  - Must compute combination count dynamically (not hardcode)
  - Must use probability units consistently (1 cent = 0.01)
  - Must write split lists to disk for reproducibility

## Sprint Phases

### Phase 1: Grid Search Infrastructure (Duration: 16-20 hours)
**Objective**: Implement `scripts/grid_search_hyperparameters.py` with CLI args, deterministic splits, parallel execution, and results storage
**Dependencies**: `simulate_trading_strategy.py` exists, database connection configured
**Deliverables**: 
- Working grid search script with all CLI arguments
- Deterministic train/valid/test splits by game ID
- Parallel execution with ThreadPoolExecutor
- CSV/JSON results per split
- `final_selection.json` with selection logic
- Split lists written to disk

### Phase 2: Visualization and Pattern Detection (Duration: 12-16 hours)
**Objective**: Implement `scripts/analyze_grid_search_results.py` with required visualizations and pattern detection summary
**Dependencies**: Phase 1 complete, grid search results available
**Deliverables**: 
- Profit heatmaps for TRAIN and VALID (separate PNGs)
- Marginal effect plots with error bars
- Tradeoff scatter plot
- Secondary heatmap (profit_factor or max_drawdown)
- Pattern detection summary printed to console

### Phase 3: Testing and Validation (Duration: 6-8 hours)
**Objective**: Test grid search on sample data, validate splits, verify visualizations, check pattern detection
**Dependencies**: Phase 1 and 2 complete
**Deliverables**: 
- Test run on 50-100 games
- Validation of train/valid/test splits (no overlap)
- Verification of all visualizations generate correctly
- Pattern detection summary accuracy check

### Phase 4: Documentation and Sprint Quality Assurance (Duration: 6-8 hours) [MANDATORY]
**Objective**: Add documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: 
- README section or GRID_SEARCH.md with exact commands
- Updated analysis document if needed
- 100% passing quality gates
- Sprint archive

## Sprint Backlog

### Epic 1: Grid Search Runner Script

**Priority**: Critical (foundational for all other work)
**Estimated Time**: 16-20 hours
**Dependencies**: `simulate_trading_strategy.py`, database connection
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: CLI Argument Parsing and Grid Generation

- **ID**: S1-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3-4 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Create**: 
  - `scripts/grid_search_hyperparameters.py` (new file)

- **Acceptance Criteria**:
  - [ ] Script accepts all required CLI arguments:
    - `--season` OR `--game-list` (mutually exclusive)
    - `--entry-min`, `--entry-max`, `--entry-step` (defaults: 0.02, 0.10, 0.01)
    - `--exit-min`, `--exit-max`, `--exit-step` (defaults: 0.00, 0.05, 0.005)
    - `--workers` (default: 8)
    - `--seed` (default: 42)
    - `--enable-fees` (default: True)
    - `--slippage-rate` (default: 0.0)
    - `--min-trade-count` (default: 200)
    - `--output-dir` (default: "grid_search_results/")
    - `--train-ratio`, `--valid-ratio`, `--test-ratio` (defaults: 0.70, 0.15, 0.15)
    - `--top-n` (default: 10)
  - [ ] Grid generation applies constraints:
    - `entry > 0`
    - `exit >= 0`
    - `exit < entry`
  - [ ] Actual combination count computed dynamically and reported in metadata
  - [ ] Invalid combinations skipped (not included in grid)

- **Tasks**:
  - [ ] T1.1.1: Set up argparse with all CLI arguments and defaults
  - [ ] T1.1.2: Implement grid generation function with constraint checking
  - [ ] T1.1.3: Add validation for mutually exclusive arguments (season vs game-list)
  - [ ] T1.1.4: Test grid generation with various parameter ranges
  - [ ] T1.1.5: Verify combination count matches expected after constraints

- **Test Cases**:
  - [ ] Test with default parameters (should generate valid grid)
  - [ ] Test with custom ranges (verify constraints applied)
  - [ ] Test with invalid ranges (should handle gracefully)
  - [ ] Test season vs game-list mutual exclusivity

#### Story 1.2: Deterministic Game ID Splitting

- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.1 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py`

- **Acceptance Criteria**:
  - [ ] Deterministic split by GAME ID using seed
  - [ ] Same split used for every hyperparameter combination
  - [ ] Split lists written to disk (`train_games.json`, `valid_games.json`, `test_games.json`)
  - [ ] Split ratios match specified ratios (within rounding)
  - [ ] No overlap between splits (verify programmatically)

- **Tasks**:
  - [ ] T1.2.1: Implement game ID fetching (from season or game list file)
  - [ ] T1.2.2: Implement deterministic shuffle with seed
  - [ ] T1.2.3: Implement split logic (train/valid/test)
  - [ ] T1.2.4: Write split lists to JSON files
  - [ ] T1.2.5: Add validation to ensure no overlap

- **Test Cases**:
  - [ ] Test with same seed produces same splits
  - [ ] Test with different seed produces different splits
  - [ ] Test split ratios are correct
  - [ ] Test no overlap between splits
  - [ ] Test split files written correctly

#### Story 1.3: Parallel Simulation Execution

- **ID**: S1-E1-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4-5 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.2 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py`
- **Dependencies**: `simulate_trading_strategy.py`, `get_aligned_data`, `simulate_trading_strategy`

- **Acceptance Criteria**:
  - [ ] Each parameter combination runs simulation on train/valid/test separately
  - [ ] Parallel execution using ThreadPoolExecutor
  - [ ] Worker count configurable via CLI
  - [ ] Progress logging for long-running operations
  - [ ] Error handling for individual combination failures

- **Tasks**:
  - [ ] T1.3.1: Import simulation functions from `simulate_trading_strategy.py`
  - [ ] T1.3.2: Implement worker function for single combination
  - [ ] T1.3.3: Implement parallel execution with ThreadPoolExecutor
  - [ ] T1.3.4: Add progress logging
  - [ ] T1.3.5: Add error handling and retry logic if needed

- **Test Cases**:
  - [ ] Test single combination execution
  - [ ] Test parallel execution with multiple workers
  - [ ] Test error handling for failed combinations
  - [ ] Test progress logging works correctly

#### Story 1.4: Metrics Aggregation and Storage

- **ID**: S1-E1-S4
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4-5 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.3 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py`

- **Acceptance Criteria**:
  - [ ] Aggregate metrics per combination per split:
    - `net_profit_dollars`
    - `num_trades`
    - `win_rate`
    - `avg_net_profit_per_trade`
    - `profit_factor`
    - `max_drawdown`
    - `total_fees`
    - `avg_hold_time` (optional)
    - `is_valid` flag (False when num_trades < min_trade_count)
  - [ ] Write CSV files per split (`grid_results_train.csv`, etc.)
  - [ ] Write JSON files per split with metadata
  - [ ] Metadata includes: args, timestamp, git hash (if available), num_combinations, search_space

- **Tasks**:
  - [ ] T1.4.1: Implement metrics aggregation from simulation results
  - [ ] T1.4.2: Implement CSV writing (pandas or csv module)
  - [ ] T1.4.3: Implement JSON writing with metadata
  - [ ] T1.4.4: Add is_valid flag logic
  - [ ] T1.4.5: Add git hash detection (optional, graceful fallback)

- **Test Cases**:
  - [ ] Test metrics aggregation from sample simulation results
  - [ ] Test CSV output format matches specification
  - [ ] Test JSON output includes all metadata
  - [ ] Test is_valid flag set correctly

#### Story 1.5: Selection Logic and Final Output

- **ID**: S1-E1-S5
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3-4 hours
- **Phase**: Phase 1
- **Prerequisites**: Story 1.4 complete
- **Files to Modify**: 
  - `scripts/grid_search_hyperparameters.py`

- **Acceptance Criteria**:
  - [ ] Rank combinations on TRAIN (top N configurable)
  - [ ] Select final candidate using VALID among top N train combos
  - [ ] Evaluate selected combo once on TEST (do not use for selection)
  - [ ] Output `final_selection.json` with:
    - Chosen parameters (entry, exit)
    - Metrics for all splits (train, valid, test)
    - Selection method description

- **Tasks**:
  - [ ] T1.5.1: Implement ranking logic (sort by net_profit_dollars on train)
  - [ ] T1.5.2: Implement selection logic (best on valid among top N train)
  - [ ] T1.5.3: Implement test evaluation (run once on selected combo)
  - [ ] T1.5.4: Generate final_selection.json
  - [ ] T1.5.5: Add validation that test was not used for selection

- **Test Cases**:
  - [ ] Test ranking produces correct top N
  - [ ] Test selection picks best on valid from top N train
  - [ ] Test test evaluation runs correctly
  - [ ] Test final_selection.json format matches specification

### Epic 2: Visualization and Pattern Detection

**Priority**: Critical (required for pattern detection)
**Estimated Time**: 12-16 hours
**Dependencies**: Epic 1 complete, grid search results available
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Profit Heatmaps

- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3-4 hours
- **Phase**: Phase 2
- **Prerequisites**: Epic 1 complete
- **Files to Create**: 
  - `scripts/analyze_grid_search_results.py` (new file)
- **Dependencies**: `matplotlib`, `pandas`, `numpy`

- **Acceptance Criteria**:
  - [ ] Generate separate heatmaps for TRAIN and VALID (separate PNGs)
  - [ ] X-axis: Entry threshold values
  - [ ] Y-axis: Exit threshold values
  - [ ] Color: net_profit_dollars
  - [ ] Annotation: Marker for chosen params (from final_selection.json)
  - [ ] Files: `plots/profit_heatmap_train.png`, `plots/profit_heatmap_valid.png`

- **Tasks**:
  - [ ] T2.1.1: Read CSV results for train and valid splits
  - [ ] T2.1.2: Reshape data into 2D grid (entry × exit)
  - [ ] T2.1.3: Generate heatmap using matplotlib/seaborn
  - [ ] T2.1.4: Add chosen params marker from final_selection.json
  - [ ] T2.1.5: Save separate PNGs for train and valid

- **Test Cases**:
  - [ ] Test heatmap generation with sample data
  - [ ] Test chosen params marker appears correctly
  - [ ] Test both train and valid heatmaps generated

#### Story 2.2: Marginal Effect Plots

- **ID**: S1-E2-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.1 complete
- **Files to Modify**: 
  - `scripts/analyze_grid_search_results.py`

- **Acceptance Criteria**:
  - [ ] Plot 1: Entry threshold vs. mean profit (averaged across all exit thresholds)
  - [ ] Plot 2: Exit threshold vs. mean profit (averaged across all entry thresholds)
  - [ ] Error bars: std error bars (std across the other axis) if easy
  - [ ] File: `plots/marginal_effects.png`

- **Tasks**:
  - [ ] T2.2.1: Calculate mean profit per entry threshold (average across exits)
  - [ ] T2.2.2: Calculate mean profit per exit threshold (average across entries)
  - [ ] T2.2.3: Calculate std errors for error bars
  - [ ] T2.2.4: Generate plot with error bars
  - [ ] T2.2.5: Save to PNG

- **Test Cases**:
  - [ ] Test marginal effect calculation correct
  - [ ] Test error bars display correctly
  - [ ] Test plot saves correctly

#### Story 2.3: Tradeoff Scatter Plot

- **ID**: S1-E2-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.2 complete
- **Files to Modify**: 
  - `scripts/analyze_grid_search_results.py`

- **Acceptance Criteria**:
  - [ ] X-axis: num_trades
  - [ ] Y-axis: net_profit_dollars
  - [ ] Color: Entry threshold (or exit threshold)
  - [ ] File: `plots/tradeoff_scatter.png`

- **Tasks**:
  - [ ] T2.3.1: Read num_trades and net_profit_dollars from results
  - [ ] T2.3.2: Map entry threshold to color
  - [ ] T2.3.3: Generate scatter plot with color mapping
  - [ ] T2.3.4: Add axis labels and legend
  - [ ] T2.3.5: Save to PNG

- **Test Cases**:
  - [ ] Test scatter plot displays correctly
  - [ ] Test color mapping works
  - [ ] Test plot saves correctly

#### Story 2.4: Secondary Heatmap

- **ID**: S1-E2-S4
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.3 complete
- **Files to Modify**: 
  - `scripts/analyze_grid_search_results.py`

- **Acceptance Criteria**:
  - [ ] Generate profit_factor OR max_drawdown heatmap (prefer VALID split)
  - [ ] X-axis: Entry threshold
  - [ ] Y-axis: Exit threshold
  - [ ] Color: profit_factor or max_drawdown
  - [ ] File: `plots/profit_factor_heatmap_valid.png` OR `plots/max_drawdown_heatmap_valid.png`

- **Tasks**:
  - [ ] T2.4.1: Choose metric (profit_factor preferred)
  - [ ] T2.4.2: Read metric from valid split results
  - [ ] T2.4.3: Reshape into 2D grid
  - [ ] T2.4.4: Generate heatmap
  - [ ] T2.4.5: Save to PNG

- **Test Cases**:
  - [ ] Test secondary heatmap displays correctly
  - [ ] Test uses valid split data
  - [ ] Test plot saves correctly

#### Story 2.5: Pattern Detection Summary

- **ID**: S1-E2-S5
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3-4 hours
- **Phase**: Phase 2
- **Prerequisites**: Story 2.4 complete
- **Files to Modify**: 
  - `scripts/analyze_grid_search_results.py`

- **Acceptance Criteria**:
  - [ ] Print pattern summary to console:
    - Profit-positive region boundary (roughly)
    - Monotonicity of profit vs entry/exit (using marginal curves)
    - Robust plateau vs sharp peak (region within 10% of best on VALID)
    - Stability: show top 5 train combos and their valid profits + rank correlation (train vs valid)
  - [ ] Summary is readable and informative

- **Tasks**:
  - [ ] T2.5.1: Calculate profit-positive boundary (contour where profit = 0)
  - [ ] T2.5.2: Analyze monotonicity from marginal curves
  - [ ] T2.5.3: Identify robust plateau (within 10% of best on VALID)
  - [ ] T2.5.4: Calculate stability metrics (top 5 train combos, rank correlation)
  - [ ] T2.5.5: Format and print summary to console

- **Test Cases**:
  - [ ] Test pattern detection calculations correct
  - [ ] Test summary prints correctly
  - [ ] Test summary is readable

### Epic 3: Testing and Validation

**Priority**: High (ensures correctness)
**Estimated Time**: 6-8 hours
**Dependencies**: Epic 1 and 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Grid Search Test Run

- **ID**: S1-E3-S1
- **Type**: Test
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Epic 1 complete

- **Acceptance Criteria**:
  - [ ] Run grid search on 50-100 games
  - [ ] Verify all combinations execute successfully
  - [ ] Verify results files generated correctly
  - [ ] Verify final_selection.json generated

- **Tasks**:
  - [ ] T3.1.1: Prepare test game list (50-100 games)
  - [ ] T3.1.2: Run grid search with test parameters
  - [ ] T3.1.3: Verify output files exist and are valid
  - [ ] T3.1.4: Check for errors in execution

- **Test Cases**:
  - [ ] Test run completes without errors
  - [ ] All output files generated
  - [ ] Results contain expected data

#### Story 3.2: Split Validation

- **ID**: S1-E3-S2
- **Type**: Test
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] Verify train/valid/test splits have no overlap
  - [ ] Verify split ratios match specified ratios
  - [ ] Verify same seed produces same splits
  - [ ] Verify split files written correctly

- **Tasks**:
  - [ ] T3.2.1: Load split files and verify no overlap
  - [ ] T3.2.2: Verify split ratios
  - [ ] T3.2.3: Test reproducibility with same seed
  - [ ] T3.2.4: Document validation results

- **Test Cases**:
  - [ ] Test no overlap between splits
  - [ ] Test split ratios correct
  - [ ] Test reproducibility

#### Story 3.3: Visualization Validation

- **ID**: S1-E3-S3
- **Type**: Test
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: Epic 2 complete

- **Acceptance Criteria**:
  - [ ] All required visualizations generate correctly
  - [ ] Visualizations are readable and informative
  - [ ] Chosen params marker appears correctly
  - [ ] Pattern detection summary is accurate

- **Tasks**:
  - [ ] T3.3.1: Run visualization script on test results
  - [ ] T3.3.2: Verify all PNG files generated
  - [ ] T3.3.3: Visually inspect plots for correctness
  - [ ] T3.3.4: Verify pattern detection summary accuracy

- **Test Cases**:
  - [ ] Test all plots generate
  - [ ] Test plots are readable
  - [ ] Test pattern detection summary accurate

### Epic 4: Documentation

**Priority**: High (required for usability)
**Estimated Time**: 4-6 hours
**Dependencies**: Epic 1, 2, 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: README Documentation

- **ID**: S1-E4-S1
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: Epic 3 complete

- **Acceptance Criteria**:
  - [ ] README section or GRID_SEARCH.md created
  - [ ] Exact commands for running grid search
  - [ ] Exact commands for generating plots
  - [ ] Interpretation guide for train/valid/test usage
  - [ ] List of output files

- **Tasks**:
  - [ ] T4.1.1: Create GRID_SEARCH.md or add to README.md
  - [ ] T4.1.2: Document grid search command with all options
  - [ ] T4.1.3: Document visualization command
  - [ ] T4.1.4: Document train/valid/test interpretation
  - [ ] T4.1.5: List all output files and their purposes

- **Test Cases**:
  - [ ] Test documentation is complete
  - [ ] Test commands work as documented
  - [ ] Test documentation is clear

#### Story 4.2: Code Documentation

- **ID**: S1-E4-S2
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: Story 4.1 complete

- **Acceptance Criteria**:
  - [ ] All functions have docstrings
  - [ ] CLI arguments documented
  - [ ] Key algorithms explained
  - [ ] Examples provided where helpful

- **Tasks**:
  - [ ] T4.2.1: Add docstrings to all functions
  - [ ] T4.2.2: Document CLI arguments
  - [ ] T4.2.3: Add algorithm explanations
  - [ ] T4.2.4: Add usage examples

- **Test Cases**:
  - [ ] Test docstrings are complete
  - [ ] Test documentation is accurate

## Risk Management

### Technical Risks

1. **Risk**: Grid search takes too long to run
   - **Mitigation**: Use parallel execution, test on smaller sample first, add progress logging
   - **Contingency**: Add checkpoint/resume functionality if needed

2. **Risk**: Memory issues with large result sets
   - **Mitigation**: Stream results to CSV/JSON, don't keep all in memory
   - **Contingency**: Add batching if needed

3. **Risk**: Visualization generation fails
   - **Mitigation**: Add error handling, test with sample data first
   - **Contingency**: Provide fallback visualization options

### Data Risks

1. **Risk**: Insufficient game data for splits
   - **Mitigation**: Check data availability before running, provide clear error messages
   - **Contingency**: Allow smaller test/valid ratios if needed

2. **Risk**: Split overlap or non-deterministic splits
   - **Mitigation**: Add validation checks, use stable seed
   - **Contingency**: Re-run with different seed if issues found

## Success Metrics

- [ ] Grid search script runs successfully on 50-100 games
- [ ] All visualizations generate correctly
- [ ] Pattern detection summary provides actionable insights
- [ ] Final selection uses proper train/valid/test methodology
- [ ] Documentation is complete and accurate
- [ ] No data leakage (splits verified)
- [ ] Results are reproducible (same seed = same splits)

## Definition of Done

- [ ] All stories completed and tested
- [ ] Grid search script produces correct results
- [ ] Visualization script generates all required plots
- [ ] Pattern detection summary is accurate
- [ ] Documentation is complete
- [ ] Code follows project standards
- [ ] All tests pass
- [ ] Sprint review completed

## Post-Sprint Follow-up

- Run full grid search on complete dataset (if test run successful)
- Review pattern detection results with data scientist
- Consider implementing UI presets based on optimal thresholds (future sprint)
- Consider adding FDR correction if multiple comparisons become concern

