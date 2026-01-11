# Analysis: Simulation Simplified View for Data Scientists

**Date**: 2025-12-25  
**Status**: Draft  
**Author**: AI Assistant  
**Version**: v1.0  
**Purpose**: Analyze current simulation implementation and design a simplified view based on data scientist feedback

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

## Executive Summary

### Key Findings
- **Current Implementation**: The simulation page displays comprehensive metrics including charts (equity curve, quartiles), per-game breakdowns, and individual trade details
- **Feedback Gap**: Data scientist feedback indicates need for simplified view focusing on entry/exit conditions, summary stats, and ESPN percentages only
- **Sample Size Limitation**: Current maximum is 100 games; feedback requests 500 games for statistical validity

### Critical Issues Identified
- **Entry/Exit Conditions Not Prominent**: Entry/exit thresholds are buried in collapsible "Simulation Parameters" section
- **Visual Clutter**: Charts and individual game details distract from core statistical analysis
- **Sample Size Constraint**: 100 game limit insufficient for robust statistical analysis

### Recommended Actions
- **Priority: High** - Create simplified view toggle alongside existing advanced view
- **Priority: High** - Increase maximum games from 100 to 500
- **Priority: Medium** - Prominently display entry/exit conditions at top of results
- **Priority: Medium** - Remove charts from simplified view, focus on summary statistics

### Success Metrics
- **Clarity**: Entry/exit conditions visible without scrolling or expanding sections
- **Sample Size**: Support for 500 games (5x increase)
- **Focus**: Simplified view shows only ESPN percentages and summary stats

## Problem Statement

### Current Situation

The trading simulation page (`webapp/static/templates/simulation.html`) provides a comprehensive view with:

**Current Features**:
- Entry/exit thresholds: Entry threshold (default 5 cents), Exit threshold (default 0 cents = convergence)
- Summary cards: Total Profit/Loss, ROI, Number of Games, Number of Trades, Win Rate, Avg Profit/Trade, Median Profit/Trade
- Position breakdown: Long ESPN vs Short ESPN statistics
- Performance metrics: Expectancy, Profit Factor, Max Loss, Max Win
- Risk metrics: Max Drawdown ($ and %), Std Dev, Sharpe Ratio
- Charts: Equity Curve (line chart), Distribution Quartiles (bar chart)
- Per-game summary: Table showing trades, profit, win rate per game
- Trade details: Individual trade list with entry/exit times and probabilities
- Simulation parameters: Collapsible section showing all input parameters

**Current Limitations**:
- Entry/exit conditions are in collapsible "Simulation Parameters" section (lines 300-305 in simulation.html)
- Maximum games limited to 100 (line 109 in simulation.py: `le=100`)
- Charts may distract from core statistical analysis
- Individual game and trade details add visual clutter

**Entry/Exit Condition Logic** (from `scripts/simulate_trading_strategy.py:6-8`):
- **Long ESPN**: Buy when `ESPN probability > Kalshi price + entry_threshold` (e.g., ESPN 55%, Kalshi 50%, threshold 5% = enter)
- **Short ESPN**: Sell when `ESPN probability < Kalshi price - entry_threshold` (e.g., ESPN 45%, Kalshi 50%, threshold 5% = enter)
- **Exit**: Close position when `|ESPN probability - Kalshi price| < exit_threshold` (default 0 = when they converge/same)

### Pain Points

**From Data Scientist Feedback**:
1. **Entry/Exit Conditions Not Clear**: "what are the entry/exit conditions" - currently buried in collapsible section
2. **Sample Size Too Small**: "expand the sample to 500 games" - current max is 100
3. **Visual Clutter**: "stop making graphs for individual games lol" - charts distract from core analysis
4. **Focus on Numbers**: "just use numbers, summary stats" - need tabular/statistical view
5. **ESPN Focus**: "remember we're just looking at the espn %s at this point" - emphasize ESPN percentages

### Business Impact

- **Data Scientist Productivity**: Current view requires scrolling/expanding to find key information
- **Statistical Validity**: 100 game limit insufficient for robust analysis; 500 games needed
- **Analysis Clarity**: Charts and individual details obscure core statistical insights

### Success Criteria

- [ ] Entry/exit conditions visible immediately at top of results (no scrolling/expanding)
- [ ] Support for 500 games (increase from 100)
- [ ] Simplified view shows only summary statistics (no charts)
- [ ] ESPN percentages prominently displayed
- [ ] Toggle between simplified/advanced views
- [ ] Current advanced view remains intact

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 
  - `webapp/static/templates/simulation.html` (add simplified view HTML)
  - `webapp/static/js/simulation.js` (add view toggle logic, simplified rendering)
  - `webapp/static/css/styles.css` (add simplified view styles)
  - `webapp/api/endpoints/simulation.py` (increase max games limit)
- **Estimated Effort**: 8-12 hours
- **Technical Complexity**: Medium (UI/UX changes, no backend algorithm changes)
- **Risk Level**: Low (additive changes, existing view preserved)

**Sprint Scope Recommendation**: Single Sprint
- **Rationale**: Well-defined scope, additive changes, low risk
- **Recommended Approach**: Single sprint with 3 phases

## Current State Analysis

### System Architecture Overview

**Frontend Structure**:
- **HTML**: `webapp/static/templates/simulation.html` - Main simulation page structure
- **JavaScript**: `webapp/static/js/simulation.js` - Simulation logic and rendering
- **CSS**: `webapp/static/css/styles.css` - Styling for simulation page

**Backend Structure**:
- **API Endpoint**: `webapp/api/endpoints/simulation.py` - `/api/simulation/bulk` endpoint
- **Simulation Logic**: `scripts/simulate_trading_strategy.py` - Core trading strategy algorithm
- **Data Sources**: ESPN probabilities (`espn.probabilities_raw_items`), Kalshi candlesticks (`kalshi.candlesticks`)

**Current Data Flow**:
1. User inputs: Number of games, entry threshold, exit threshold, bet amount, exclude first/last seconds
2. Frontend calls `/api/simulation/bulk` with parameters
3. Backend fetches games with Kalshi data, runs simulation per game, aggregates results
4. Frontend renders comprehensive results with charts, tables, and trade details

### Code Quality Assessment

**Current Implementation Quality**:
- **Code Organization**: Well-structured with clear separation of concerns
- **Error Handling**: Comprehensive error handling and logging
- **Performance**: Efficient aggregation and caching
- **Maintainability**: Clear function names and comments

**Complexity Analysis**:
- **Cyclomatic Complexity**: Medium (simulation logic has multiple conditional branches)
- **Cognitive Complexity**: Medium (rendering logic handles multiple data structures)
- **Technical Debt**: Low (recently refactored with data scientist feedback)

### Performance Baseline

**Current Performance**:
- **100 Games**: ~30-60 seconds (depends on data availability)
- **Response Size**: ~500KB-2MB JSON (depends on number of trades)
- **Frontend Rendering**: ~1-2 seconds for full results display

**500 Games Projection**:
- **Estimated Time**: ~2.5-5 minutes (5x current)
- **Response Size**: ~2.5-10MB JSON (5x current)
- **Frontend Rendering**: ~5-10 seconds (5x current)

### Design Pattern Analysis

**Current Patterns**:
- **Module Pattern**: JavaScript organized in modules (`simulation.js`)
- **Service Pattern**: Backend API endpoints (`simulation.py`)
- **State Machine Pattern**: Trading simulation logic (`simulate_trading_strategy.py`)

**Pattern for Simplified View**:
- **Strategy Pattern**: Toggle between simplified/advanced rendering strategies
- **Template Method Pattern**: Shared rendering logic with view-specific overrides

### Algorithm Analysis

**Current Algorithm**: Divergence Threshold Trading Simulation
- **Type**: State Machine / Event-Driven Simulation
- **Time Complexity**: O(n * m) where n = number of games, m = average aligned data points per game
- **Space Complexity**: O(n * m) for storing aligned data and trades

**Algorithm Unchanged**: Simplified view only changes presentation, not simulation logic

## Technical Assessment

### Entry/Exit Condition Analysis

**Current Entry/Exit Logic** (from `scripts/simulate_trading_strategy.py:6-8`):

```python
# Strategy:
# - Long ESPN: Buy when ESPN probability > Kalshi price + entry_threshold (e.g., 5 cents)
# - Short ESPN: Sell when ESPN probability < Kalshi price - entry_threshold
# - Exit: Close position when divergence converges to < exit_threshold (e.g., 1 cent)
```

**Entry Conditions**:
- **Long ESPN**: `ESPN_prob > Kalshi_price + entry_threshold`
  - Example: ESPN 55%, Kalshi 50%, threshold 5% → Enter long (ESPN overvalued)
- **Short ESPN**: `ESPN_prob < Kalshi_price - entry_threshold`
  - Example: ESPN 45%, Kalshi 50%, threshold 5% → Enter short (ESPN undervalued)

**Exit Condition**:
- **Exit**: `|ESPN_prob - Kalshi_price| <= exit_threshold`
  - Default exit_threshold = 0 → Exit when ESPN and Kalshi converge (same value)
  - Example: ESPN 50%, Kalshi 50%, threshold 0% → Exit (converged)

**Current Display** (from `simulation.html:300-305`):
- Entry/exit thresholds shown in collapsible "Simulation Parameters" section
- Not prominently displayed at top of results

### Sample Size Analysis

**Current Limit**: 100 games (`simulation.py:109`)
```python
num_games: int = Query(..., ge=1, le=100, description="Number of most recent games to simulate")
```

**Requested Limit**: 500 games
- **Rationale**: Larger sample size improves statistical validity
- **Impact**: 5x increase in processing time and response size
- **Feasibility**: Backend can handle 500 games (estimated 2.5-5 minutes)

### Visualization Analysis

**Current Charts** (from `simulation.html`):
1. **Equity Curve** (lines 241-248): Line chart showing cumulative P&L over trades
2. **Distribution Quartiles** (lines 269-273): Bar chart showing profit distribution quartiles

**Feedback**: "stop making graphs for individual games lol" - Remove charts from simplified view

**Current Tables**:
1. **Per-Game Summary** (lines 276-293): Table showing trades, profit, win rate per game
2. **Trade Details** (lines 295-298): List of individual trades with entry/exit details

**Feedback**: Focus on summary stats, not individual game/trade details

### ESPN Percentage Focus

**Current Display** (from `simulation.js:329`):
- Shows both ESPN and Kalshi percentages: `ESPN: ${(trade.entry_espn_prob * 100).toFixed(1)}% | Kalshi: ${(trade.entry_kalshi_price * 100).toFixed(1)}%`

**Feedback**: "remember we're just looking at the espn %s at this point"
- Simplified view should emphasize ESPN percentages
- Kalshi percentages can be de-emphasized or hidden

## Recommendations

### Immediate Actions (Priority: High)

**Recommendation 1: Create Simplified View Toggle**
- **Files to Modify**: 
  - `webapp/static/templates/simulation.html` (add toggle button, simplified view HTML)
  - `webapp/static/js/simulation.js` (add view toggle logic, simplified rendering function)
  - `webapp/static/css/styles.css` (add simplified view styles)
- **Estimated Effort**: 4-6 hours
- **Risk Level**: Low (additive, existing view preserved)
- **Success Metrics**: Toggle works, simplified view displays correctly

**Recommendation 2: Increase Maximum Games to 500**
- **Files to Modify**: 
  - `webapp/api/endpoints/simulation.py` (change `le=100` to `le=500`)
  - `webapp/static/templates/simulation.html` (update input max attribute)
- **Estimated Effort**: 0.5 hours
- **Risk Level**: Low (simple limit change)
- **Success Metrics**: Can select up to 500 games, simulation completes successfully

**Recommendation 3: Prominently Display Entry/Exit Conditions**
- **Files to Modify**: 
  - `webapp/static/templates/simulation.html` (add entry/exit conditions section at top)
  - `webapp/static/js/simulation.js` (render entry/exit conditions prominently)
- **Estimated Effort**: 1-2 hours
- **Risk Level**: Low (presentation change only)
- **Success Metrics**: Entry/exit conditions visible without scrolling

### Short-term Improvements (Priority: Medium)

**Recommendation 4: Simplify Simplified View Content**
- **Files to Modify**: 
  - `webapp/static/js/simulation.js` (create `renderSimplifiedResults()` function)
- **Estimated Effort**: 2-3 hours
- **Risk Level**: Low (new function, existing rendering preserved)
- **Success Metrics**: Simplified view shows only summary stats, no charts

**Recommendation 5: Emphasize ESPN Percentages**
- **Files to Modify**: 
  - `webapp/static/js/simulation.js` (update display logic to emphasize ESPN)
- **Estimated Effort**: 1 hour
- **Risk Level**: Low (presentation change)
- **Success Metrics**: ESPN percentages prominently displayed, Kalshi de-emphasized

## Design Decision Recommendations

### Design Decision: View Toggle Implementation

**Problem Statement**:
- Need to support both simplified (data scientist) and advanced (current) views
- Must preserve existing functionality while adding new view
- Toggle should be intuitive and persistent

**Project Scope**: Single sprint, 8-12 hours, low risk

**Sprint Scope Analysis**:
- **Complexity Assessment**: Medium complexity (UI/UX changes, no algorithm changes)
- **Sprint Scope Determination**: Single Sprint
- **Scope Justification**: Well-defined requirements, additive changes, low risk

**Multiple Solution Analysis**:

**Option 1: Separate Pages**
- **Design Pattern**: None (separate routes)
- **Algorithm**: O(1) routing
- **Implementation Complexity**: Medium (4-6 hours)
- **Maintenance Overhead**: Medium (duplicate code)
- **Scalability**: Good
- **Cost-Benefit**: Medium cost, Medium benefit
- **Over-Engineering Risk**: Medium (unnecessary routing complexity)
- **Rejected**: Unnecessary complexity, violates requirement to keep current view

**Option 2: CSS Show/Hide Toggle**
- **Design Pattern**: Strategy Pattern (CSS-based)
- **Algorithm**: O(1) DOM manipulation
- **Implementation Complexity**: Low (2-3 hours)
- **Maintenance Overhead**: Low (single HTML structure)
- **Scalability**: Good
- **Cost-Benefit**: Low cost, High benefit
- **Over-Engineering Risk**: None
- **Selected**: Simple, efficient, maintains single codebase

**Option 3: JavaScript Conditional Rendering**
- **Design Pattern**: Strategy Pattern (JavaScript-based)
- **Algorithm**: O(n) rendering where n = number of elements
- **Implementation Complexity**: Medium (3-4 hours)
- **Maintenance Overhead**: Medium (conditional logic)
- **Scalability**: Good
- **Cost-Benefit**: Medium cost, High benefit
- **Over-Engineering Risk**: Low
- **Rejected**: More complex than CSS toggle, similar benefit

**Chosen Solution**: CSS Show/Hide Toggle (Option 2)
- **Implementation**: Single HTML structure with two view containers, CSS classes control visibility
- **Configuration**: Toggle button switches CSS classes
- **Integration**: Minimal changes to existing code, new simplified view container added

**Pros and Cons Analysis**:

**Pros**:
- **Simplicity**: Single HTML structure, CSS controls visibility
- **Performance**: O(1) toggle operation, no re-rendering
- **Maintainability**: Single source of truth for data, two presentation layers
- **User Experience**: Instant toggle, no page reload

**Cons**:
- **HTML Size**: Slightly larger HTML (both views in DOM)
- **Initial Load**: Both views rendered (but hidden view not visible)

**Risk Assessment**:
- **Risk 1**: CSS conflicts between views - mitigated by namespace classes
- **Risk 2**: Performance with 500 games - mitigated by lazy rendering of hidden view

**Trade-off Analysis**:
- **Sacrificed**: Slightly larger HTML file
- **Gained**: Simple implementation, instant toggle, single codebase
- **Net Benefit**: High (simplicity outweighs minor HTML size increase)

## Implementation Plan

### Phase 1: Backend Changes (Duration: 0.5 hours)
**Objective**: Increase maximum games limit to 500
**Dependencies**: None
**Deliverables**: Updated API endpoint and HTML input max attribute

#### Tasks
- **Task 1.1**: Update API endpoint max limit
  - **Files**: `webapp/api/endpoints/simulation.py:109`
  - **Effort**: 0.25 hours
  - **Prerequisites**: None
  - **Validation**: Can select 500 games in UI, API accepts 500 games

- **Task 1.2**: Update HTML input max attribute
  - **Files**: `webapp/static/templates/simulation.html:20`
  - **Effort**: 0.25 hours
  - **Prerequisites**: None
  - **Validation**: Input accepts values up to 500

### Phase 2: Simplified View HTML Structure (Duration: 2-3 hours)
**Objective**: Create simplified view HTML structure with toggle
**Dependencies**: Phase 1 complete
**Deliverables**: Toggle button, simplified view container, entry/exit conditions display

#### Tasks
- **Task 2.1**: Add view toggle button
  - **Files**: `webapp/static/templates/simulation.html` (add after results header)
  - **Effort**: 0.5 hours
  - **Prerequisites**: None
  - **Validation**: Toggle button visible, clickable

- **Task 2.2**: Create simplified view container
  - **Files**: `webapp/static/templates/simulation.html` (add new section)
  - **Effort**: 1-1.5 hours
  - **Prerequisites**: Task 2.1
  - **Validation**: Simplified view container exists, initially hidden

- **Task 2.3**: Add entry/exit conditions display section
  - **Files**: `webapp/static/templates/simulation.html` (at top of simplified view)
  - **Effort**: 0.5-1 hour
  - **Prerequisites**: Task 2.2
  - **Validation**: Entry/exit conditions visible in simplified view

### Phase 3: Simplified View Rendering Logic (Duration: 3-4 hours)
**Objective**: Implement JavaScript rendering for simplified view
**Dependencies**: Phase 2 complete
**Deliverables**: Simplified rendering function, toggle logic, ESPN-focused display

#### Tasks
- **Task 3.1**: Create `renderSimplifiedResults()` function
  - **Files**: `webapp/static/js/simulation.js` (new function)
  - **Effort**: 2-2.5 hours
  - **Prerequisites**: Task 2.2
  - **Validation**: Simplified view renders summary stats correctly

- **Task 3.2**: Implement toggle logic
  - **Files**: `webapp/static/js/simulation.js` (toggle handler)
  - **Effort**: 0.5 hours
  - **Prerequisites**: Task 3.1
  - **Validation**: Toggle switches between views correctly

- **Task 3.3**: Emphasize ESPN percentages
  - **Files**: `webapp/static/js/simulation.js` (update display logic)
  - **Effort**: 0.5-1 hour
  - **Prerequisites**: Task 3.1
  - **Validation**: ESPN percentages prominently displayed

### Phase 4: Styling and Polish (Duration: 1-2 hours)
**Objective**: Style simplified view and ensure consistency
**Dependencies**: Phase 3 complete
**Deliverables**: CSS styles for simplified view, consistent design

#### Tasks
- **Task 4.1**: Add simplified view CSS styles
  - **Files**: `webapp/static/css/styles.css` (new styles)
  - **Effort**: 1-1.5 hours
  - **Prerequisites**: Task 3.1
  - **Validation**: Simplified view styled correctly, matches design system

- **Task 4.2**: Ensure responsive design
  - **Files**: `webapp/static/css/styles.css` (responsive styles)
  - **Effort**: 0.5 hours
  - **Prerequisites**: Task 4.1
  - **Validation**: Simplified view works on mobile/tablet/desktop

## Risk Assessment

### Technical Risks
- **Risk 1**: Performance degradation with 500 games
  - **Probability**: Medium
  - **Impact**: Medium (longer wait times)
  - **Mitigation**: Progress tracking already implemented, consider pagination if needed
  - **Contingency**: Add loading states, optimize backend queries

- **Risk 2**: CSS conflicts between views
  - **Probability**: Low
  - **Impact**: Low (visual only)
  - **Mitigation**: Use namespaced CSS classes (`.simplified-view`, `.advanced-view`)
  - **Contingency**: Review and fix CSS specificity issues

### Business Risks
- **Risk 1**: Data scientist feedback not fully addressed
  - **Probability**: Low
  - **Impact**: Medium (rework needed)
  - **Mitigation**: Clear requirements, iterative feedback
  - **Contingency**: Adjust simplified view based on feedback

## Success Metrics and Monitoring

### Performance Metrics
- **Response Time**: < 5 minutes for 500 games (baseline: ~1 minute for 100 games)
- **Frontend Rendering**: < 10 seconds for simplified view (baseline: ~2 seconds for advanced view)
- **Toggle Performance**: < 100ms (instant)

### Quality Metrics
- **Code Coverage**: Maintain current coverage (no new untested code)
- **User Experience**: Toggle works smoothly, simplified view loads quickly
- **Accessibility**: Toggle button accessible via keyboard

### Business Metrics
- **Data Scientist Satisfaction**: Simplified view addresses all feedback points
- **Feature Adoption**: Toggle usage tracked (if analytics added)
- **Time to Insight**: Reduced time to find entry/exit conditions (< 5 seconds)

## Evidence and Proof

### Current Implementation Evidence

**Entry/Exit Logic** (from `scripts/simulate_trading_strategy.py:6-8`):
```python
# Strategy:
# - Long ESPN: Buy when ESPN probability > Kalshi price + entry_threshold (e.g., 5 cents)
# - Short ESPN: Sell when ESPN probability < Kalshi price - entry_threshold
# - Exit: Close position when divergence converges to < exit_threshold (e.g., 1 cent)
```

**Current Max Games Limit** (from `webapp/api/endpoints/simulation.py:109`):
```python
num_games: int = Query(..., ge=1, le=100, description="Number of most recent games to simulate")
```

**Current Entry/Exit Display** (from `webapp/static/templates/simulation.html:300-305`):
```html
<details class="results-metadata">
    <summary class="metadata-summary">
        <h4 style="display: inline;">Simulation Parameters</h4>
    </summary>
    <div id="simulationMetadata" class="metadata-list"></div>
</details>
```

**Current Charts** (from `webapp/static/templates/simulation.html`):
- Equity Curve: Lines 241-248
- Distribution Quartiles: Lines 269-273

## Appendices

### Appendix A: Feedback Summary

**Original Feedback**:
1. "what i would like to do is 1) clearly see the entry/exit conditions and 2) expand the sample to 500 games and see if the pattern holds"
2. "stop making graphs for individual games lol"
3. "just use numbers, summary stats"
4. "also remember we're just looking at the espn %s at this point"
5. "yeah what are the entry/exit conditions"

**Key Requirements Extracted**:
- Entry/exit conditions must be clearly visible (not buried)
- Support 500 games (increase from 100)
- Remove charts from simplified view
- Focus on summary statistics (numbers, not graphs)
- Emphasize ESPN percentages
- Keep current view intact (additive change)

### Appendix B: Current Metrics Displayed

**Summary Cards** (from `simulation.html:64-93`):
- Total Profit/Loss
- ROI
- Number of Games
- Number of Trades
- Win Rate
- Avg Profit/Trade
- Median Profit/Trade

**Position Breakdown** (from `simulation.html:95-141`):
- Long ESPN: Count, Profit, Win Rate, Avg Profit
- Short ESPN: Count, Profit, Win Rate, Avg Profit

**Performance Metrics** (from `simulation.html:143-181`):
- Expectancy (EV per Trade)
- Profit Factor
- Max Loss
- Max Win

**Risk Metrics** (from `simulation.html:183-239`):
- Max Drawdown ($)
- Max Drawdown (%)
- Std Dev (per-trade P&L)
- Sharpe Ratio

**Trade Characteristics** (from `simulation.html:251-267`):
- Avg Trade Duration
- Avg Entry Divergence
- Avg Exit Divergence

**Charts**:
- Equity Curve (cumulative P&L over trades)
- Distribution Quartiles (profit distribution)

**Tables**:
- Per-Game Summary (trades, profit, win rate per game)
- Trade Details (individual trades with entry/exit)

---

## Document Validation

This analysis follows the standards defined in `ANALYSIS_STANDARDS.md`.

