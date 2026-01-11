# Sprint Plan: Fix Trading Simulation P&L Calculation

**Date**: 2025-12-28  
**Sprint Duration**: 2-3 days (16-24 hours total)  
**Sprint Goal**: Convert simulation from betting model (outcome-based P&L) to trading model (price-based P&L) and integrate trading costs (fees, spreads, slippage) to produce realistic, actionable trading performance metrics  
**Current Status**: Simulation calculates P&L based on final game outcome (betting model). Fees, spreads, and slippage are completely ignored. All performance metrics are invalid for trading strategy evaluation.  
**Target Status**: Simulation calculates P&L based on entry/exit price differences (trading model). All costs are included per trade. Performance metrics accurately reflect real trading performance.  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

## Pre-Sprint Code Quality Baseline
- **Test Results**: N/A (no test suite for simulation logic)
- **QC Results**: N/A
- **Code Coverage**: N/A
- **Build Status**: Application runs successfully, but simulation produces invalid results

## Database Evidence Template
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). No database schema changes required for this sprint.

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

## Sprint Overview

### Business Context
- **Business Driver**: Current simulation produces invalid results that cannot be used for trading strategy evaluation. P&L is calculated based on final game outcomes (betting) rather than entry/exit prices (trading), making all performance metrics meaningless. Trading costs (fees, spreads, slippage) are completely ignored, overstating profitability by 15-30%.
- **Success Criteria**: 
  - P&L calculated from entry/exit price differences (not outcomes)
  - All trading costs included per trade (fees, spreads, slippage)
  - Performance metrics recalculated and validated
  - End-of-game positions closed using market prices (not binary settlement)
  - All metrics become meaningful for trading strategy evaluation
- **Stakeholders**: Data scientists and traders evaluating strategy viability
- **Timeline Constraints**: None (but critical fix - should be prioritized)

### Technical Context
- **Current System State**: 
  - P&L calculation: `scripts/simulate_trading_strategy.py::calculate_trade_pnl()` uses `actual_outcome` parameter
  - Entry/exit prices captured but not used for P&L
  - No cost calculations (fees, spreads, slippage ignored)
  - End-of-game positions settled using binary outcome ($1.00 or $0.00)
  - Metrics calculated using invalid P&L data
- **Target System State**: 
  - P&L calculated from `(exit_price - entry_price) × position_size`
  - `actual_outcome` parameter removed from P&L calculation
  - Fees calculated using Kalshi fee formula (7% × price × (1-price))
  - Bid-ask spreads applied using actual bid/ask prices
  - Slippage estimated and applied per trade
  - End-of-game positions closed using final market prices
  - All metrics recalculated using corrected P&L
- **Architecture Impact**: Core simulation logic changes (breaking change to P&L calculation)
- **Integration Points**: 
  - Frontend may need updates if it displays P&L differently
  - Cached simulation results become invalid (need cache invalidation)

### Sprint Scope
- **In Scope**: 
  - Fix P&L calculation to use entry/exit prices (bid/ask)
  - Remove outcome-based logic from P&L
  - Implement fee calculation (Kalshi 7% formula)
  - Implement optional slippage (configurable assumption, can be disabled)
  - **Spread cost NOT included** (already embedded in bid/ask execution prices)
  - Fix end-of-game position handling
  - Recalculate all performance metrics
  - Update cache invalidation strategy
- **Out of Scope**: 
  - Changes to data alignment algorithm
  - Changes to entry/exit threshold logic
  - Changes to parallel processing architecture
  - Frontend UI changes (unless required for corrected metrics)
- **Assumptions**: 
  - Entry/exit prices (bid/ask) are available in trade data
  - Kalshi fee formula is accurate (7% × price × (1-price))
  - Slippage is a configurable conservative assumption (can be disabled or set very low)
  - Spread cost is already embedded in bid/ask execution prices (NOT double-counted)
  - All cached results should be invalidated (old results are wrong)
- **Constraints**: 
  - Must maintain backward compatibility for API response structure
  - Must preserve existing trade data structure (add fields, don't remove)
  - Must handle cases where bid/ask data is missing (fallback to mid-price)
  - Must NOT double-count spread cost (already in bid/ask prices)
  - Prioritize correctness over extensibility in v1

## Sprint Phases

### Phase 1: Fix Core P&L Calculation (Duration: 4-6 hours)
**Objective**: Replace outcome-based P&L with price-based P&L calculation
**Dependencies**: None
**Deliverables**: Updated `calculate_trade_pnl()` function using entry/exit prices

### Phase 2: Implement Trading Costs (Duration: 3-4 hours)
**Objective**: Add fee calculations and optional slippage (configurable assumption) to each trade
**Dependencies**: Phase 1 complete
**Deliverables**: Fee calculation function, optional slippage function, and integration into P&L

### Phase 3: Fix End-of-Game Position Handling (Duration: 2-3 hours)
**Objective**: Close end-of-game positions using market prices instead of binary settlement
**Dependencies**: Phase 1 complete
**Deliverables**: Updated end-of-game position closing logic

### Phase 4: Recalculate Metrics and Validate (Duration: 4-6 hours)
**Objective**: Recalculate all performance metrics using corrected P&L and validate results
**Dependencies**: Phases 1-3 complete
**Deliverables**: Updated metric calculations, validation tests, corrected results

### Phase 5: Cache Invalidation and Quality Assurance (Duration: 2-3 hours)
**Objective**: Invalidate old cached results and ensure quality standards
**Dependencies**: Phase 4 complete
**Deliverables**: Cache clearing, quality validation, documentation updates

## Sprint Backlog

### Epic 1: Core P&L Calculation Fix
**Priority**: Critical (blocks all other work)
**Estimated Time**: 4-6 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Remove Outcome-Based P&L Logic
- **ID**: S1-E1-S1
- **Type**: Bug Fix / Refactor
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `calculate_trade_pnl()`)
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - remove `actual_outcome` dependency)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `calculate_trade_pnl()` function no longer uses `actual_outcome` parameter
  - [ ] Long position P&L calculated as: `(exit_kalshi_bid - entry_kalshi_ask) × position_size`
  - [ ] Short position P&L calculated as: `(entry_kalshi_bid - exit_kalshi_ask) × position_size`
  - [ ] Function signature updated to remove `actual_outcome` parameter (or make it optional/unused)
  - [ ] All calls to `calculate_trade_pnl()` updated to remove `actual_outcome` argument
  - [ ] Unit test verifies P&L calculation for long position with price movement
  - [ ] Unit test verifies P&L calculation for short position with price movement
  - [ ] P&L is positive when exit price > entry price (long) or exit price < entry price (short), regardless of outcome

- **Technical Context**:
  - **Current State**: 
    ```python
    def calculate_trade_pnl(trade: Trade, actual_outcome: Optional[int], bet_amount_dollars: float) -> float:
        if actual_outcome == 1:  # Home won
            payout = num_contracts * 1.0
            profit = payout - entry_cost
        else:  # Home lost
            profit = -entry_cost
    ```
  - **Required Changes**: 
    ```python
    def calculate_trade_pnl(trade: Trade, bet_amount_dollars: float) -> float:
        # Long: Buy at ask, sell at bid
        if trade.position_type == "long_espn":
            entry_price = trade.entry_kalshi_ask
            exit_price = trade.exit_kalshi_bid
            price_movement = exit_price - entry_price
            num_contracts = bet_amount_dollars / entry_price
            profit = num_contracts × price_movement
        
        # Short: Sell at bid, buy at ask
        elif trade.position_type == "short_espn":
            entry_price = trade.entry_kalshi_bid
            exit_price = trade.exit_kalshi_ask
            price_movement = entry_price - exit_price  # Profit when price falls
            num_contracts = bet_amount_dollars / (1 - entry_price)
            entry_premium = num_contracts × entry_price
            exit_cost = num_contracts × exit_price
            profit = entry_premium - exit_cost
    ```
  - **Integration Points**: 
    - `simulate_trading_strategy()` calls `calculate_trade_pnl()` for each trade
    - Trade objects already contain `entry_kalshi_bid`, `entry_kalshi_ask`, `exit_kalshi_price` fields
    - Need to ensure `exit_kalshi_bid` and `exit_kalshi_ask` are captured at exit time
  - **Data Structures**: 
    - `Trade` dataclass already has required fields
    - May need to add `exit_kalshi_bid` and `exit_kalshi_ask` fields if not present
  - **API Contracts**: No API changes required (internal function)

- **Implementation Steps**:
  1. Read `scripts/simulate_trading_strategy.py` to understand current `calculate_trade_pnl()` implementation
  2. Identify all places where `actual_outcome` is used in P&L calculation
  3. Replace outcome-based logic with price-based logic
  4. Update function signature to remove `actual_outcome` parameter
  5. Update all call sites to remove `actual_outcome` argument
  6. Ensure `exit_kalshi_bid` and `exit_kalshi_ask` are captured at exit time in `simulate_trading_strategy()`
  7. Add fallback logic if bid/ask unavailable (use mid-price with warning)

- **Validation Steps**:
  ```python
  # Test long position with price increase
  trade = Trade(
      position_type="long_espn",
      entry_kalshi_ask=0.60,
      exit_kalshi_bid=0.70,
      ...
  )
  profit = calculate_trade_pnl(trade, bet_amount_dollars=20.0)
  assert profit > 0  # Should be positive (price increased)
  assert abs(profit - (20/0.60 * 0.10)) < 0.01  # Should be ~$3.33
  
  # Test short position with price decrease
  trade = Trade(
      position_type="short_espn",
      entry_kalshi_bid=0.80,
      exit_kalshi_ask=0.65,
      ...
  )
  profit = calculate_trade_pnl(trade, bet_amount_dollars=20.0)
  assert profit > 0  # Should be positive (price decreased)
  ```

- **Definition of Done**: 
  - Function calculates P&L based on price movement only
  - No reference to `actual_outcome` in P&L calculation
  - All tests pass
  - Manual verification shows correct P&L for sample trades

- **Rollback Plan**: 
  - Revert changes to `calculate_trade_pnl()` function
  - Restore `actual_outcome` parameter usage
  - No database changes to rollback

- **Risk Assessment**: 
  - **Risk**: Missing bid/ask data at exit time
  - **Mitigation**: Add fallback to mid-price with logging
  - **Risk**: Position sizing calculation errors
  - **Mitigation**: Add unit tests for edge cases (price = 0, price = 1)

- **Success Metrics**:
  - **Functionality**: P&L calculated correctly for 100% of test cases
  - **Quality**: Zero references to `actual_outcome` in P&L calculation
  - **Performance**: No performance degradation (same O(1) complexity)

### Story 1.2: Update Trade Exit Logic to Capture Bid/Ask Prices
- **ID**: S1-E1-S2
- **Type**: Bug Fix
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1 (Story 1.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - exit logic)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Trade objects include `exit_kalshi_bid` field when exiting short positions
  - [ ] Trade objects include `exit_kalshi_ask` field when exiting long positions
  - [ ] Exit prices captured from aligned data point at exit time
  - [ ] Fallback to mid-price if bid/ask unavailable (with warning log)
  - [ ] End-of-game exits also capture bid/ask prices

- **Technical Context**:
  - **Current State**: Trade objects may only have `exit_kalshi_price` (mid-price)
  - **Required Changes**: Capture `exit_kalshi_bid` and `exit_kalshi_ask` from aligned data at exit time
  - **Integration Points**: Exit logic in `simulate_trading_strategy()` function
  - **Data Structures**: `Trade` dataclass needs `exit_kalshi_bid` and `exit_kalshi_ask` fields

- **Implementation Steps**:
  1. Verify `Trade` dataclass has `exit_kalshi_bid` and `exit_kalshi_ask` fields
  2. Update exit logic to capture bid/ask from aligned data point
  3. Add fallback logic if bid/ask unavailable
  4. Update end-of-game position closing to capture final bid/ask

- **Validation Steps**:
  - Verify trade objects contain exit bid/ask prices
  - Verify fallback works when bid/ask unavailable
  - Verify end-of-game positions have exit prices

- **Definition of Done**: All trades have exit bid/ask prices captured
- **Rollback Plan**: Revert to using mid-price only
- **Risk Assessment**: Low risk (additive change)
- **Success Metrics**: 100% of trades have exit bid/ask prices

### Story 1.3: Remove Actual Outcome Dependency from Simulation Flow
- **ID**: S1-E1-S3
- **Type**: Refactor
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1 (Story 1.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - remove `actual_outcome` parameter)
  - `scripts/simulate_trading_strategy.py` (function: `get_aligned_data()` - `actual_outcome` still needed for display, but not P&L)
  - `webapp/api/endpoints/simulation.py` (remove `actual_outcome` from P&L calculation calls)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `simulate_trading_strategy()` no longer passes `actual_outcome` to `calculate_trade_pnl()`
  - [ ] `actual_outcome` still available for display/logging purposes
  - [ ] All P&L calculations use price-based logic only
  - [ ] No breaking changes to API response structure

- **Technical Context**:
  - **Current State**: `actual_outcome` passed to `calculate_trade_pnl()` for P&L calculation
  - **Required Changes**: Remove `actual_outcome` from P&L calculation, keep for display only
  - **Integration Points**: Simulation flow, API endpoints

- **Implementation Steps**:
  1. Update `simulate_trading_strategy()` to not pass `actual_outcome` to `calculate_trade_pnl()`
  2. Keep `actual_outcome` in trade objects for display/logging
  3. Update API endpoint if needed
  4. Verify no breaking changes

- **Validation Steps**:
  - Verify P&L calculated without `actual_outcome`
  - Verify `actual_outcome` still available in trade objects for display
  - Verify API responses unchanged (except P&L values)

- **Definition of Done**: P&L calculation independent of outcome
- **Rollback Plan**: Restore `actual_outcome` parameter usage
- **Risk Assessment**: Low risk (internal refactor)
- **Success Metrics**: Zero dependencies on outcome for P&L

---

### Epic 2: Trading Costs Implementation
**Priority**: Critical (required for realistic results)
**Estimated Time**: 3-4 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2
**Note**: Spread cost is NOT included because it's already embedded in bid/ask execution prices. Only fees and optional slippage are added.

### Story 2.1: Implement Kalshi Fee Calculation
- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1 (Story 1.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (add fee calculation function)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Function `calculate_kalshi_fee(price: float, bet_amount: float) -> float` implemented
  - [ ] Fee formula: `7% × (price × (1 - price)) × bet_amount`
  - [ ] Fee calculated for entry price (entry fee)
  - [ ] Fee calculated for exit price (exit fee)
  - [ ] Fees subtracted from gross profit to get net profit
  - [ ] Unit tests verify fee calculation for various prices (0.10, 0.50, 0.90)
  - [ ] Fees highest at 50% probability (verified in tests)

- **Technical Context**:
  - **Current State**: No fee calculation exists
  - **Required Changes**: 
    ```python
    def calculate_kalshi_fee(price: float, bet_amount: float) -> float:
        """
        Calculate Kalshi trading fee.
        Formula: 7% × (price × (1 - price)) × bet_amount
        Fees are highest at 50% probability, decrease toward extremes.
        """
        fee_rate = 0.07 * (price * (1 - price))
        return fee_rate * bet_amount
    ```
  - **Integration Points**: Called for entry and exit in P&L calculation
  - **Data Structures**: Price in 0-1 range, bet_amount in dollars

- **Implementation Steps**:
  1. Create `calculate_kalshi_fee()` function
  2. Add unit tests for fee calculation
  3. Integrate into P&L calculation (entry + exit fees)
  4. Verify fees are highest at 50% probability

- **Validation Steps**:
  ```python
  # Test fee at 50% (should be highest)
  fee_50 = calculate_kalshi_fee(0.50, 20.0)
  assert fee_50 == 0.07 * 0.25 * 20.0  # Should be $0.35
  
  # Test fee at 10% (should be lower)
  fee_10 = calculate_kalshi_fee(0.10, 20.0)
  assert fee_10 == 0.07 * 0.09 * 20.0  # Should be $0.126
  
  # Verify 50% fee > 10% fee
  assert fee_50 > fee_10
  ```

- **Definition of Done**: Fee calculation implemented and integrated
- **Rollback Plan**: Remove fee calculation, restore gross profit only
- **Risk Assessment**: Low risk (additive feature)
- **Success Metrics**: Fees calculated correctly for all price ranges

### Story 2.2: Implement Optional Slippage (Configurable Assumption)
- **ID**: S1-E2-S2
- **Type**: Feature
- **Priority**: Medium (optional, configurable)
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1 (Story 1.1), S1-E2-S1 (Story 2.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (add optional slippage calculation)
  - `webapp/api/endpoints/simulation.py` (add slippage parameter to API)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Function `calculate_slippage_cost(bet_amount: float, slippage_rate: float = 0.0) -> float` implemented
  - [ ] Slippage is **optional** and **configurable** (default: 0.0, can be set to 0.0 to disable)
  - [ ] Slippage clearly labeled as **assumption** in docstrings and comments
  - [ ] Slippage cost = slippage_rate × bet_amount (applied at entry and exit)
  - [ ] API accepts `slippage_rate` parameter (default: 0.0)
  - [ ] Slippage can be turned off (set to 0.0) or set very low (e.g., 0.001 = 0.1%)
  - [ ] Unit tests verify slippage calculation (including 0.0 case)
  - [ ] Slippage cost only subtracted from gross profit if slippage_rate > 0

- **Technical Context**:
  - **Current State**: No slippage calculation
  - **Required Changes**: 
    ```python
    def calculate_slippage_cost(bet_amount: float, slippage_rate: float = 0.0) -> float:
        """
        Calculate slippage cost as a conservative execution penalty.
        
        **ASSUMPTION**: This is a configurable conservative estimate, not a precise model.
        Slippage represents execution cost beyond bid-ask spread (e.g., market impact).
        
        Args:
            bet_amount: Bet amount in dollars
            slippage_rate: Slippage rate as decimal (e.g., 0.001 = 0.1%). Default: 0.0 (disabled)
        
        Returns:
            Slippage cost in dollars (0.0 if slippage_rate is 0.0)
        """
        if slippage_rate <= 0.0:
            return 0.0
        return slippage_rate * bet_amount
    ```
  - **Integration Points**: 
    - Called for entry and exit in P&L calculation (only if slippage_rate > 0)
    - API parameter in `simulation.py` (default: 0.0)
  - **Data Structures**: Bet amount in dollars, slippage_rate as float (0.0 to disable)

- **Implementation Steps**:
  1. Create `calculate_slippage_cost()` function with clear assumption labeling
  2. Add `slippage_rate` parameter to API endpoint (default: 0.0)
  3. Apply slippage at entry and exit only if slippage_rate > 0
  4. Integrate into net P&L calculation (conditional on slippage_rate)
  5. Add unit tests (including 0.0 case to verify it can be disabled)
  6. Add clear documentation that slippage is an assumption, not precise model

- **Validation Steps**:
  - Verify slippage calculated correctly when enabled (slippage_rate > 0)
  - Verify slippage is 0.0 when disabled (slippage_rate = 0.0)
  - Verify slippage applied at both entry and exit (when enabled)
  - Verify slippage scales with bet amount
  - Verify API accepts slippage_rate parameter with default 0.0

- **Definition of Done**: Optional slippage implemented with clear assumption labeling
- **Rollback Plan**: Remove slippage calculation or set default to 0.0
- **Risk Assessment**: Low risk (optional, configurable, clearly labeled as assumption)
- **Success Metrics**: Slippage can be enabled/disabled, clearly documented as assumption

### Story 2.3: Integrate Costs into Net P&L Calculation
- **ID**: S1-E2-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1 (Story 2.1), S1-E2-S2 (Story 2.2)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `calculate_trade_pnl()`)
- **Files to Create**: None
- **Dependencies**: Fee and optional slippage calculation functions

- **Acceptance Criteria**:
  - [ ] Net P&L = Gross P&L - Entry Fee - Exit Fee - Entry Slippage - Exit Slippage
  - [ ] **Spread cost NOT included** (already embedded in bid/ask execution prices)
  - [ ] All costs calculated and subtracted from gross profit
  - [ ] Net profit stored in trade object
  - [ ] Gross profit also stored for comparison
  - [ ] Slippage only applied if slippage_rate > 0
  - [ ] Unit tests verify net P&L calculation with fees and optional slippage

- **Technical Context**:
  - **Current State**: Only gross P&L calculated
  - **Required Changes**: 
    ```python
    def calculate_trade_pnl(trade: Trade, bet_amount_dollars: float, slippage_rate: float = 0.0) -> dict:
        """
        Calculate trade P&L with costs.
        
        Note: Spread cost is NOT included because it's already embedded in bid/ask
        execution prices. Only fees and optional slippage are added.
        """
        # Calculate gross profit (price movement using bid/ask prices)
        # Long: Buy at ask, sell at bid
        # Short: Sell at bid, buy at ask
        gross_profit = calculate_gross_profit(trade, bet_amount_dollars)
        
        # Calculate costs
        entry_fee = calculate_kalshi_fee(trade.entry_kalshi_ask, bet_amount_dollars)
        exit_fee = calculate_kalshi_fee(trade.exit_kalshi_bid, bet_amount_dollars)
        
        # Optional slippage (only if enabled)
        entry_slippage = calculate_slippage_cost(bet_amount_dollars, slippage_rate)
        exit_slippage = calculate_slippage_cost(bet_amount_dollars, slippage_rate)
        
        # Calculate net profit
        total_costs = entry_fee + exit_fee + entry_slippage + exit_slippage
        net_profit = gross_profit - total_costs
        
        return {
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "total_costs": total_costs,
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "slippage_cost": entry_slippage + exit_slippage  # 0.0 if disabled
        }
    ```
  - **Integration Points**: Called for each trade in simulation
  - **Data Structures**: Returns dictionary with breakdown of costs (no spread_cost field)

- **Implementation Steps**:
  1. Update `calculate_trade_pnl()` to calculate fees and optional slippage
  2. **Do NOT add spread cost** (already embedded in bid/ask prices)
  3. Subtract costs from gross profit to get net profit
  4. Store both gross and net profit in trade object
  5. Update simulation to use net profit for metrics
  6. Add unit tests (with and without slippage)

- **Validation Steps**:
  - Verify net profit = gross profit - fees - slippage (if enabled)
  - Verify spread cost is NOT included
  - Verify all costs are positive (costs, not benefits)
  - Verify net profit is less than or equal to gross profit
  - Verify cost breakdown is accurate (fees + optional slippage only)
  - Verify slippage can be disabled (slippage_rate = 0.0)

- **Definition of Done**: Net P&L includes fees and optional slippage (no spread cost)
- **Rollback Plan**: Revert to gross profit only
- **Risk Assessment**: Low risk (additive changes, spread cost correctly excluded)
- **Success Metrics**: All costs included in net P&L (fees + optional slippage, no spread)

---

### Epic 3: End-of-Game Position Handling
**Priority**: High (affects trades that don't exit before game ends)
**Estimated Time**: 2-3 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Fix End-of-Game Position Closing
- **ID**: S1-E3-S1
- **Type**: Bug Fix
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E1-S1 (Story 1.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - end-of-game logic)
- **Files to Create**: None
- **Dependencies**: Final market prices available in aligned data

- **Acceptance Criteria**:
  - [ ] End-of-game positions closed using final market price (bid/ask), not binary settlement
  - [ ] Final market price captured from last aligned data point
  - [ ] P&L calculated using entry price vs final market price
  - [ ] No reference to `actual_outcome` for P&L calculation
  - [ ] Unit tests verify end-of-game position closing

- **Technical Context**:
  - **Current State**: End-of-game positions settled using binary outcome ($1.00 or $0.00)
  - **Required Changes**: Use final bid/ask price from last aligned data point
  - **Integration Points**: End-of-game handling in `simulate_trading_strategy()`
  - **Data Structures**: Last aligned data point contains final market prices

- **Implementation Steps**:
  1. Identify end-of-game position closing logic
  2. Replace binary settlement with final market price
  3. Capture final bid/ask from last aligned data point
  4. Calculate P&L using entry price vs final market price
  5. Update logging to reflect market-price-based closing

- **Validation Steps**:
  - Verify end-of-game positions use final market price
  - Verify P&L calculated correctly for end-of-game positions
  - Verify no binary settlement logic remains

- **Definition of Done**: End-of-game positions closed using market prices
- **Rollback Plan**: Revert to binary settlement (temporary)
- **Risk Assessment**: Medium risk (affects trades that don't exit)
- **Success Metrics**: All end-of-game positions use market prices

---

### Epic 4: Metrics Recalculation and Validation
**Priority**: Critical (all metrics currently invalid)
**Estimated Time**: 4-6 hours
**Dependencies**: Epics 1-3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Recalculate All Performance Metrics
- **ID**: S1-E4-S1
- **Type**: Refactor
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E2-S3 (Story 2.3), S1-E3-S1 (Story 3.1)
- **Files to Modify**: 
  - `webapp/api/endpoints/simulation.py` (function: `get_bulk_simulation_results()` - aggregation logic)
- **Files to Create**: None
- **Dependencies**: Corrected P&L in trade objects

- **Acceptance Criteria**:
  - [ ] All metrics calculated using net profit (not gross profit)
  - [ ] Sharpe ratio recalculated using net returns
  - [ ] Max win/loss recalculated using net profit
  - [ ] ROI recalculated using net profit and costs
  - [ ] Win rate recalculated using net profit (trades with net profit > 0)
  - [ ] All other metrics (expectancy, profit factor, drawdown) recalculated
  - [ ] Metrics now reflect realistic trading performance

- **Technical Context**:
  - **Current State**: Metrics calculated using outcome-based P&L
  - **Required Changes**: Use net profit from corrected P&L calculation
  - **Integration Points**: Aggregation logic in `get_bulk_simulation_results()`
  - **Data Structures**: Trade objects now have `net_profit` field

- **Implementation Steps**:
  1. Update aggregation to use `net_profit` instead of `profit_cents`
  2. Recalculate all metrics using net profit
  3. Update metric calculations to reflect price-based returns
  4. Verify metrics are realistic (e.g., max loss not artificially capped)

- **Validation Steps**:
  - Verify metrics use net profit
  - Verify max loss reflects actual price movements (not capped)
  - Verify ROI includes costs
  - Verify win rate based on net profit

- **Definition of Done**: All metrics recalculated using corrected P&L
- **Rollback Plan**: Revert to outcome-based metrics
- **Risk Assessment**: Low risk (recalculation only)
- **Success Metrics**: All metrics reflect realistic trading performance

### Story 4.2: Validate Corrected Results
- **ID**: S1-E4-S2
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 4
- **Prerequisites**: S1-E4-S1 (Story 4.1)
- **Files to Modify**: None (validation only)
- **Files to Create**: Validation test script (optional)
- **Dependencies**: Corrected simulation results

- **Acceptance Criteria**:
  - [ ] P&L is positive when exit price > entry price (long), regardless of outcome
  - [ ] P&L is negative when exit price < entry price (long), regardless of outcome
  - [ ] Max loss reflects worst price movement (not artificially capped)
  - [ ] Costs are included in all trades
  - [ ] Net profit <= gross profit for all trades
  - [ ] Metrics are realistic (e.g., Sharpe ratio, ROI, drawdown)

- **Technical Context**:
  - **Current State**: Need to validate corrected results
  - **Required Changes**: Create validation tests and manual verification
  - **Integration Points**: Validation of simulation output

- **Implementation Steps**:
  1. Run simulation on sample games
  2. Verify P&L calculated correctly for sample trades
  3. Verify costs included in all trades
  4. Verify metrics are realistic
  5. Compare old vs new results (should show significant differences)

- **Validation Steps**:
  - Manual verification of sample trades
  - Verify costs are reasonable (fees: ~0.6-1.8% of bet amount, slippage: 0% if disabled)
  - Verify spread cost is NOT included (already in bid/ask prices)
  - Verify max loss reflects price movements
  - Verify metrics are meaningful for trading

- **Definition of Done**: Results validated and realistic
- **Rollback Plan**: N/A (validation only)
- **Risk Assessment**: Low risk (validation only)
- **Success Metrics**: 100% of trades have correct P&L and costs

---

### Epic 5: Cache Invalidation and Quality Assurance
**Priority**: High (old cached results are invalid)
**Estimated Time**: 2-3 hours
**Dependencies**: Epics 1-4 complete
**Status**: Not Started
**Phase Assignment**: Phase 5

### Story 5.1: Invalidate Old Cached Results
- **ID**: S1-E5-S1
- **Type**: Configuration / Maintenance
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: Phase 5
- **Prerequisites**: S1-E4-S2 (Story 4.2)
- **Files to Modify**: 
  - `webapp/api/endpoints/simulation.py` (add cache invalidation on startup or version check)
- **Files to Create**: None
- **Dependencies**: Cache clearing mechanism

- **Acceptance Criteria**:
  - [ ] Old cached results cleared (or marked as invalid)
  - [ ] Cache versioning implemented (optional but recommended)
  - [ ] New results cached with correct P&L
  - [ ] Cache clear button works correctly
  - [ ] No stale cached results used

- **Technical Context**:
  - **Current State**: Cached results use old (incorrect) P&L calculation
  - **Required Changes**: Clear cache or add version check
  - **Integration Points**: Cache system in `simulation.py`

- **Implementation Steps**:
  1. Add cache version check (or clear all cached results)
  2. Update cache key generation to include version
  3. Clear existing cache on deployment
  4. Verify new results cached correctly

- **Validation Steps**:
  - Verify old cached results not used
  - Verify new results cached correctly
  - Verify cache clear button works

- **Definition of Done**: Cache invalidated and new results cached
- **Rollback Plan**: Restore old cache (not recommended)
- **Risk Assessment**: Low risk (cache management)
- **Success Metrics**: No stale cached results

### Story 5.2: Update Documentation
- **ID**: S1-E5-S2
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 1 hour
- **Phase**: Phase 5
- **Prerequisites**: S1-E4-S2 (Story 4.2)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (docstrings)
  - `webapp/api/endpoints/simulation.py` (docstrings)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Function docstrings updated to reflect price-based P&L
  - [ ] Cost calculation documented
  - [ ] End-of-game handling documented
  - [ ] API documentation updated if needed

- **Technical Context**:
  - **Current State**: Documentation may reference outcome-based P&L
  - **Required Changes**: Update all documentation to reflect price-based P&L

- **Implementation Steps**:
  1. Update function docstrings
  2. Update API documentation
  3. Add comments explaining cost calculations
  4. Document P&L calculation formula

- **Validation Steps**:
  - Verify documentation is accurate
  - Verify all functions have updated docstrings

- **Definition of Done**: Documentation updated and accurate
- **Rollback Plan**: N/A (documentation only)
- **Risk Assessment**: Low risk (documentation only)
- **Success Metrics**: All documentation accurate

### Story 5.3: Quality Gate Validation
- **ID**: S1-E5-S3
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All code follows type hints (no `Any` types unless necessary)
  - [ ] All functions have docstrings
  - [ ] P&L calculation verified correct for sample trades
  - [ ] Costs included in all trades
  - [ ] Metrics recalculated and validated
  - [ ] No breaking changes to API (response structure preserved)

- **Technical Context**:
  - **Current State**: Need to validate all changes meet quality standards
  - **Required Changes**: Fix any quality issues

- **Implementation Steps**:
  1. Run linting checks
  2. Verify type hints
  3. Verify docstrings
  4. Run manual validation tests
  5. Fix any issues

- **Validation Steps**:
  - Run `pylint` or equivalent
  - Run `mypy` or equivalent
  - Manual verification of sample trades
  - Verify API responses unchanged (except values)

- **Definition of Done**: All quality gates pass
- **Rollback Plan**: Fix issues until gates pass
- **Risk Assessment**: Low risk (quality checks)
- **Success Metrics**: 100% quality gate pass rate

---

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: Strategy Pattern for Cost Calculation
- **Category**: Behavioral
- **Intent**: Separate cost calculation logic from P&L calculation for maintainability
- **Implementation**: Individual functions for each cost type (fees, spreads, slippage)
- **Benefits**: 
  - Easy to modify individual cost calculations
  - Testable in isolation
  - Clear separation of concerns
- **Trade-offs**: 
  - More function calls (minimal performance impact)
  - More code (acceptable for clarity)
- **Rationale**: Cost calculations are complex and may need adjustment. Separating them makes maintenance easier.

### Algorithm Analysis

### Algorithm: Price-Based P&L Calculation
- **Type**: Financial Calculation
- **Complexity**: Time O(1), Space O(1)
- **Description**: Calculate profit/loss based on entry/exit price difference multiplied by position size
- **Use Case**: Core trading simulation logic
- **Performance**: Constant time per trade, highly efficient

### Design Decision Analysis

### Design Decision: Remove Outcome Dependency from P&L
- **Problem**: Current P&L calculation uses final game outcome, making it a betting simulator rather than trading simulator
- **Context**: Need realistic trading performance metrics for strategy evaluation
- **Project Scope**: Single developer, 2-3 day sprint, critical fix

**Options**:

**Option 1: Keep Outcome-Based P&L (CURRENT - WRONG)**
- **Design Pattern**: Betting Model
- **Algorithm**: Binary Outcome Settlement
- **Implementation Complexity**: Low (already implemented)
- **Maintenance Overhead**: Low
- **Scalability**: N/A
- **Cost-Benefit**: Low cost, **ZERO benefit** (invalid results)
- **Over-Engineering Risk**: None
- **Selected**: ❌ **REJECTED** - Produces invalid results

**Option 2: Price-Based P&L Only (CHOSEN)**
- **Design Pattern**: Trading Model
- **Algorithm**: Price Movement Calculation
- **Implementation Complexity**: Medium (2-3 hours)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent (same complexity)
- **Cost-Benefit**: Medium cost, **HIGH benefit** (valid results)
- **Over-Engineering Risk**: None (correct approach)
- **Selected**: ✅ **CHOSEN** - Produces valid trading results

**Option 3: Hybrid Model (Price + Outcome)**
- **Design Pattern**: Mixed Model
- **Algorithm**: Price movement with outcome adjustment
- **Implementation Complexity**: High (4-6 hours)
- **Maintenance Overhead**: High (two calculation paths)
- **Scalability**: Good
- **Cost-Benefit**: High cost, **LOW benefit** (confusing, unrealistic)
- **Over-Engineering Risk**: High (unnecessary complexity)
- **Selected**: ❌ **REJECTED** - Unrealistic and confusing

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 2-3 hours (medium complexity)
- **Learning Curve**: 0 hours (straightforward change)
- **Configuration Effort**: 0 hours (no configuration needed)

**Maintenance Cost**:
- **Monitoring**: 0 hours (no monitoring needed)
- **Updates**: 0 hours (stable calculation)
- **Debugging**: Low (simpler than outcome-based)

**Performance Benefit**:
- **Response Time**: No change (same O(1) complexity)
- **Throughput**: No change
- **Resource Efficiency**: No change

**Correctness Benefit**:
- **Result Validity**: **CRITICAL** - Results become valid for trading evaluation
- **Metric Accuracy**: **CRITICAL** - All metrics become meaningful
- **Risk Assessment**: **CRITICAL** - Risk metrics become accurate

**Risk Cost**:
- **Risk 1**: Missing bid/ask data → Mitigated by fallback to mid-price
- **Risk 2**: Position sizing errors → Mitigated by unit tests

**Over-Engineering Prevention**:
- **Problem Complexity**: Medium (core calculation change)
- **Solution Complexity**: Medium (matches problem complexity)
- **Appropriateness**: ✅ Solution complexity matches problem complexity
- **Future Growth**: Solution accommodates any number of games/trades

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ (single developer, manageable scope)
- **Team Capability**: ✅ (straightforward implementation)
- **Timeline Constraints**: ✅ (2-3 days sufficient)
- **Future Growth**: ✅ (scales to any number of games)
- **Technical Debt**: ✅ (reduces technical debt by fixing core issue)

**Chosen Solution**: Price-based P&L calculation
- Implementation: Calculate P&L from entry/exit price difference
- Configuration: None required
- Integration: Replace outcome-based logic in `calculate_trade_pnl()`

**Pros and Cons Analysis**:

**Pros**:
- **Correctness**: ✅ Produces valid trading results
- **Realism**: ✅ Reflects actual trading performance
- **Metrics**: ✅ All metrics become meaningful
- **Risk**: ✅ Accurate risk assessment

**Cons**:
- **Breaking Change**: ⚠️ Invalidates cached results (mitigated by cache clearing)
- **Complexity**: ⚠️ Slightly more complex (acceptable for correctness)

**Risk Assessment**: 
- **Low Risk**: Well-understood calculation, straightforward implementation
- **Mitigation**: Unit tests, fallback logic for missing data

**Trade-off Analysis**: 
- **Sacrificed**: Outcome-based simplicity (was incorrect anyway)
- **Gained**: Valid trading results, meaningful metrics, accurate risk assessment
- **Net Benefit**: **CRITICAL** - Enables real trading strategy evaluation

### Design Decision: Spread Cost Handling (Bid/Ask vs Mid-Price)
- **Problem**: Need to avoid double-counting spread cost in P&L calculation
- **Context**: P&L can be calculated using bid/ask prices (spread embedded) or mid-prices (spread explicit)
- **Project Scope**: Single developer, prioritize correctness over extensibility

**Options**:

**Option 1: Use Bid/Ask Prices with No Explicit Spread Cost (CHOSEN)**
- **Design Pattern**: Execution Price Model
- **Algorithm**: P&L = (exit_bid - entry_ask) × position_size (long) or (entry_bid - exit_ask) × position_size (short)
- **Implementation Complexity**: Low (already using bid/ask prices)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent
- **Cost-Benefit**: Low cost, **HIGH benefit** (correct, no double-counting)
- **Over-Engineering Risk**: None
- **Selected**: ✅ **CHOSEN** - Spread cost already embedded in execution prices

**Option 2: Use Mid-Prices with Explicit Spread Cost**
- **Design Pattern**: Mid-Price Model with Spread Adjustment
- **Algorithm**: P&L = (exit_mid - entry_mid) × position_size - spread_cost
- **Implementation Complexity**: Medium (need to calculate spread cost separately)
- **Maintenance Overhead**: Medium (two calculation paths)
- **Scalability**: Good
- **Cost-Benefit**: Medium cost, **MEDIUM benefit** (more complex, same result)
- **Over-Engineering Risk**: Medium (unnecessary complexity)
- **Selected**: ❌ **REJECTED** - More complex, same result, risk of double-counting

**Option 3: Use Bid/Ask Prices with Explicit Spread Cost (WRONG)**
- **Design Pattern**: Double-Counting Model
- **Algorithm**: P&L = (exit_bid - entry_ask) × position_size - spread_cost
- **Implementation Complexity**: Medium
- **Maintenance Overhead**: Medium
- **Scalability**: Good
- **Cost-Benefit**: Medium cost, **ZERO benefit** (double-counts spread)
- **Over-Engineering Risk**: High (incorrect approach)
- **Selected**: ❌ **REJECTED** - Double-counts spread cost

**Chosen Solution**: Use bid/ask execution prices with no explicit spread cost
- **Rationale**: Spread cost is already embedded in bid/ask execution prices. Long positions buy at ask (higher) and sell at bid (lower), short positions sell at bid (lower) and buy at ask (higher). The spread cost is naturally included in the price difference.
- **Implementation**: Calculate P&L directly from bid/ask prices, no separate spread cost calculation
- **Documentation**: Clearly document that spread cost is embedded in execution prices

**Pros and Cons**:

**Pros**:
- **Correctness**: ✅ No double-counting of spread cost
- **Simplicity**: ✅ Simpler implementation (no separate spread calculation)
- **Realism**: ✅ Reflects actual execution prices traders face

**Cons**:
- **Transparency**: ⚠️ Spread cost not explicitly visible (but embedded in P&L)
- **Mitigation**: Can add optional spread breakdown for analysis (out of scope for v1)

**Risk Assessment**: 
- **Low Risk**: Well-understood approach, avoids double-counting
- **Mitigation**: Clear documentation that spread is embedded in execution prices

---

## Testing Strategy

### Testing Approach
- **Unit Tests**: Test P&L calculation for various scenarios (long/short, profit/loss, with/without costs)
- **Integration Tests**: Test full simulation flow with corrected P&L
- **E2E Tests**: Run simulation on sample games and verify results
- **Performance Tests**: Verify no performance degradation (same complexity)

### Test Cases Required

1. **Long Position P&L**:
   - Entry: $0.60, Exit: $0.70 → Should be positive
   - Entry: $0.60, Exit: $0.50 → Should be negative
   - Verify independent of outcome

2. **Short Position P&L**:
   - Entry: $0.80, Exit: $0.65 → Should be positive
   - Entry: $0.80, Exit: $0.90 → Should be negative
   - Verify independent of outcome

3. **Cost Calculation**:
   - Verify fees calculated correctly
   - Verify spread cost calculated correctly
   - Verify slippage calculated correctly
   - Verify net profit = gross profit - costs

4. **End-of-Game Positions**:
   - Verify closed using final market price
   - Verify P&L calculated correctly

---

## Deployment Plan
- **Pre-Deployment**: 
  - Clear simulation cache (old results invalid)
  - Verify all tests pass
  - Verify corrected results on sample games
- **Deployment Steps**: 
  - Deploy code changes
  - Clear cache (via API or manual)
  - Monitor for errors
- **Post-Deployment**: 
  - Verify new simulations produce corrected results
  - Verify metrics are realistic
  - Monitor for any issues
- **Rollback Plan**: 
  - Revert code changes
  - Restore old P&L calculation (not recommended - old results invalid)

---

## Risk Assessment
- **Technical Risks**: 
  - **Risk**: Missing bid/ask data → **Mitigation**: Fallback to mid-price with warning
  - **Risk**: Position sizing errors → **Mitigation**: Unit tests for edge cases
  - **Risk**: Cache invalidation issues → **Mitigation**: Clear cache on deployment
- **Business Risks**: 
  - **Risk**: Results show strategy is unprofitable after costs → **Mitigation**: This is correct - strategy may not be viable (honest assessment)
  - **Risk**: Metrics change significantly → **Mitigation**: Expected - old metrics were invalid
- **Resource Risks**: 
  - **Risk**: Time overrun → **Mitigation**: Prioritize critical fixes (P&L, costs), defer optional features

---

## Success Metrics
- **Technical**: 
  - P&L calculated correctly for 100% of trades
  - All costs included in net P&L
  - Zero references to outcome in P&L calculation
  - All quality gates pass
- **Business**: 
  - Results are valid for trading strategy evaluation
  - Metrics accurately reflect trading performance
  - Risk assessment is accurate
- **Sprint**: 
  - All stories completed
  - All acceptance criteria met
  - Documentation updated

---

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] P&L calculation uses entry/exit prices only
- [ ] Fees and optional slippage included in net P&L (spread cost NOT included - already embedded)
- [ ] End-of-game positions use market prices
- [ ] All metrics recalculated using corrected P&L
- [ ] Cache invalidated
- [ ] Documentation updated
- [ ] All quality gates pass (linting, type checking, tests)
- [ ] Results validated on sample games

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

