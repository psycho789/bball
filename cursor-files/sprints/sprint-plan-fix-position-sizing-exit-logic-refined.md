# Sprint Plan: Fix Position Sizing, Exit Logic, and Simulation Realism

**Date**: 2025-12-28  
**Sprint Duration**: 2-3 days (16-24 hours total)  
**Sprint Goal**: Fix critical correctness issues (short position sizing, exit logic asymmetry, end-of-game forced close) and add realism filters (minimum holding period, hysteresis, direction confirmation, game phase stratification) to produce accurate, realistic trading simulation results  
**Current Status**: Short positions use incorrect contract count formula causing risk understatement (most severe at 0.8-0.9 entry prices), exits allow optimistic fallback to mid-price for subset of trades, end-of-game closes ignore liquidity collapse, and missing realism filters allow noise trading  
**Target Status**: Risk-neutral position sizing for shorts, symmetric exit requirements with slippage penalty for fallback, realistic end-of-game closes with forced slippage, and realism filters to reduce noise trading  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

## Pre-Sprint Code Quality Baseline
- **Test Results**: N/A (no test suite for simulation logic)
- **QC Results**: N/A
- **Code Coverage**: N/A
- **Build Status**: Application runs successfully, but simulation has correctness issues that introduce systematic bias

## Database Evidence Template
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). No database schema changes required for this sprint.

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

## Sprint Overview

### Business Context
- **Business Driver**: Current simulation has correctness issues that introduce systematic bias and understate risk. Short positions show inflated profit relative to assumed risk due to incorrect contract sizing (most severe at high entry prices 0.8-0.9). Exit logic allows optimistic fallback to mid-price for trades where bid/ask unavailable. End-of-game forced closes ignore liquidity collapse for trades that remain open at game end. Missing realism filters allow noise trading that inflates trade counts.
- **Success Criteria**: 
  - Short position sizing uses risk-neutral formula (`bet_amount / (1 - entry_price)`)
  - Exit logic applies slippage penalty when using mid-price fallback
  - End-of-game forced closes apply forced slippage penalty
  - Minimum holding period enforced (30-60 seconds, configurable)
  - Hysteresis exit logic prevents churn when hovering near threshold
  - ESPN direction confirmation filters noise entries (only enter when divergence widening)
  - Game phase stratification provides strategic insights (Q1, Q2-Q3, Q4 breakdown)
  - Divergence variables renamed for clarity (`divergence_prob`)
  - All cached results invalidated (old results contain systematic bias)
- **Stakeholders**: Data scientists and traders evaluating strategy viability
- **Timeline Constraints**: None (but critical fixes - should be prioritized)

### Technical Context
- **Current System State**: 
  - Short position sizing: `bet_amount / entry_price` (INCORRECT - causes risk understatement)
  - Exit logic: Allows fallback to mid-price without slippage penalty (optimistic for subset of trades)
  - End-of-game close: Uses market price without accounting for liquidity collapse (optimistic for trades open at game end)
  - No minimum holding period (allows noise trading)
  - No hysteresis exit (allows churn when hovering near threshold)
  - No direction confirmation (allows noise entries)
  - No game phase stratification
  - Divergence variables use ambiguous names (unit confusion risk)
- **Target System State**: 
  - Short position sizing: `bet_amount / (1 - entry_price)` (risk-neutral, matches maximum risk assumption)
  - Exit logic: Applies slippage penalty (1-2 cents) when using mid-price fallback
  - End-of-game close: Applies forced slippage penalty (2 cents) for all end-of-game closes
  - Minimum holding period: 30-60 seconds (configurable, default 30)
  - Hysteresis exit: Only exit when divergence crosses from outside threshold to inside
  - Direction confirmation: Only enter when divergence is widening (not shrinking)
  - Game phase stratification: Q1, Q2-Q3, Q4 breakdown in results
  - Divergence variables: Renamed to `divergence_prob` for clarity
- **Architecture Impact**: Core simulation logic changes (breaking change to P&L calculation for shorts)
- **Integration Points**: 
  - Cached simulation results become invalid (need cache invalidation)
  - Frontend may need updates for new parameters (minimum holding period)

### Sprint Scope
- **In Scope**: 
  - Fix short position sizing (risk-neutral formula)
  - Fix exit logic asymmetry (apply slippage penalty for fallback)
  - Fix end-of-game forced close (apply forced slippage penalty)
  - Add minimum holding period filter
  - Add hysteresis exit logic
  - Add ESPN direction confirmation
  - Add game phase stratification
  - Rename divergence variables for clarity (`divergence_prob`)
  - Invalidate cached results
- **Out of Scope**: 
  - Changes to data alignment algorithm
  - Changes to entry/exit threshold logic (except direction confirmation)
  - Changes to parallel processing architecture
  - Frontend UI changes (unless required for new parameters)
- **Assumptions**: 
  - Minimum holding period: 30-60 seconds (configurable, default 30)
  - Forced slippage for end-of-game: 2 cents (conservative estimate)
  - Exit fallback slippage: 1.5 cents (conservative estimate)
  - All cached results should be invalidated (old results contain systematic bias)
- **Constraints**: 
  - Must maintain backward compatibility for API response structure
  - Must preserve existing trade data structure (add fields, don't remove)
  - Must handle cases where bid/ask data is missing (apply slippage, don't fail)
  - Prioritize correctness over extensibility in v1

## Sprint Phases

### Phase 1: Fix Critical Position Sizing (Duration: 2-3 hours)
**Objective**: Fix short position sizing to use risk-neutral formula
**Dependencies**: None
**Deliverables**: Updated `calculate_trade_pnl()` with correct short sizing

### Phase 2: Fix Exit Logic Asymmetry (Duration: 2-3 hours)
**Objective**: Apply slippage penalty when using mid-price fallback for exits
**Dependencies**: Phase 1 complete
**Deliverables**: Updated exit logic with slippage penalty

### Phase 3: Fix End-of-Game Forced Close (Duration: 1-2 hours)
**Objective**: Apply forced slippage penalty for end-of-game closes
**Dependencies**: Phase 2 complete
**Deliverables**: Updated end-of-game close logic with forced slippage

### Phase 4: Add Realism Filters (Duration: 4-6 hours)
**Objective**: Add minimum holding period, hysteresis, direction confirmation, and game phase stratification
**Dependencies**: Phase 3 complete
**Deliverables**: Realism filters implemented and integrated

### Phase 5: Code Clarity and Cache Invalidation (Duration: 2-3 hours)
**Objective**: Rename divergence variables for clarity, invalidate cache, update documentation
**Dependencies**: Phase 4 complete
**Deliverables**: Clear variable names, cache cleared, documentation updated

## Sprint Backlog

### Epic 1: Fix Short Position Sizing
**Priority**: Critical (fixes fundamental bias affecting all short positions)
**Estimated Time**: 2-3 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Fix Short Position Sizing Formula
- **ID**: S2-E1-S1
- **Type**: Bug Fix
- **Priority**: Critical
- **Estimate**: 2-3 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `calculate_trade_pnl()` - short position sizing)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Short position sizing uses `bet_amount_dollars / (1 - entry_price)` instead of `bet_amount_dollars / entry_price`
  - [ ] Long position sizing unchanged (`bet_amount_dollars / entry_price`)
  - [ ] Both long and short positions have same maximum risk (`bet_amount_dollars`)
  - [ ] Unit test verifies short sizing at entry_price = 0.80 (should be 100 contracts for $20 bet)
  - [ ] Unit test verifies short sizing at entry_price = 0.50 (should be 40 contracts for $20 bet)
  - [ ] Unit test verifies short sizing at entry_price = 0.90 (should be 200 contracts for $20 bet)
  - [ ] Unit test verifies long sizing unchanged (should be 40 contracts for $20 bet at 0.50)
  - [ ] Maximum loss calculation correct for shorts (max loss = bet_amount when price goes to $1.00)

- **Technical Context**:
  - **Current State**: 
    ```python
    # Short position sizing (INCORRECT - causes risk understatement)
    num_contracts = bet_amount_dollars / entry_price  # Same as long (WRONG)
    ```
  - **Required Changes**: 
    ```python
    # Short position sizing (CORRECT - risk-neutral)
    num_contracts = bet_amount_dollars / (1 - entry_price)  # Risk-neutral sizing
    ```
  - **Integration Points**: 
    - `calculate_trade_pnl()` function
    - Affects all short trade P&L calculations
  - **Data Structures**: No changes needed
  - **API Contracts**: No API changes (internal calculation)

- **Implementation Steps**:
  1. Read `calculate_trade_pnl()` function for short positions
  2. Change `num_contracts = bet_amount_dollars / entry_price` to `num_contracts = bet_amount_dollars / (1 - entry_price)`
  3. Update comment to explain risk-neutral sizing rationale
  4. Add unit tests for short sizing at various entry prices (0.1, 0.5, 0.8, 0.9)
  5. Verify maximum loss calculation is correct (equals bet_amount)

- **Validation Steps**:
  ```python
  # Test short sizing at 0.80
  entry_price = 0.80
  bet_amount = 20.0
  num_contracts = bet_amount / (1 - entry_price)
  assert num_contracts == 100.0  # Should be 100 contracts
  
  # Test maximum loss (price goes to 1.00)
  exit_price = 1.00
  entry_premium = num_contracts * entry_price  # 100 * 0.80 = 80
  exit_cost = num_contracts * exit_price      # 100 * 1.00 = 100
  max_loss = exit_cost - entry_premium  # 100 - 80 = 20
  assert max_loss == bet_amount  # Should equal bet amount
  ```

- **Definition of Done**: 
  - Short position sizing uses risk-neutral formula
  - Maximum loss equals bet_amount for shorts
  - Unit tests pass
  - Manual verification shows correct sizing

- **Rollback Plan**: 
  - Revert to `bet_amount_dollars / entry_price` for shorts
  - No database changes to rollback

- **Risk Assessment**: 
  - **Risk**: Breaking change - all short trade P&L will change
  - **Mitigation**: Clear cache, document change, verify with unit tests

- **Success Metrics**:
  - **Functionality**: Short sizing correct for 100% of test cases
  - **Quality**: Maximum loss equals bet_amount for shorts
  - **Performance**: No performance degradation (same O(1) complexity)

---

### Epic 2: Fix Exit Logic Asymmetry
**Priority**: High (fixes optimistic execution assumption for subset of trades)
**Estimated Time**: 2-3 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Apply Slippage Penalty for Fallback Exits
- **ID**: S2-E2-S1
- **Type**: Bug Fix
- **Priority**: High
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: S2-E1-S1 (Story 1.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - exit logic)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Exit logic applies slippage penalty when using mid-price fallback
  - [ ] Slippage penalty: 1.5 cents (configurable, conservative estimate)
  - [ ] Long exits: Subtract slippage from exit_bid when using fallback
  - [ ] Short exits: Add slippage to exit_ask when using fallback
  - [ ] Log warning when fallback slippage applied
  - [ ] Unit tests verify slippage penalty applied correctly
  - [ ] Exit P&L reflects slippage penalty

- **Technical Context**:
  - **Current State**: 
    ```python
    # Exit logic (optimistic fallback)
    exit_kalshi_bid = kalshi_bid
    exit_kalshi_ask = kalshi_ask
    if exit_kalshi_bid is None:
        exit_kalshi_bid = kalshi_price  # Fallback (no penalty)
    ```
  - **Required Changes**: 
    ```python
    # Exit logic (realistic fallback with slippage)
    exit_kalshi_bid = kalshi_bid
    exit_kalshi_ask = kalshi_ask
    fallback_slippage_cents = 1.5  # Conservative estimate
    
    if exit_kalshi_bid is None:
        exit_kalshi_bid = kalshi_price - (fallback_slippage_cents / 100.0)  # Penalty for long exit
        logger.warning(f"[EXIT] Using fallback bid with {fallback_slippage_cents} cent slippage penalty")
    if exit_kalshi_ask is None:
        exit_kalshi_ask = kalshi_price + (fallback_slippage_cents / 100.0)  # Penalty for short exit
        logger.warning(f"[EXIT] Using fallback ask with {fallback_slippage_cents} cent slippage penalty")
    ```
  - **Integration Points**: 
    - Exit logic in `simulate_trading_strategy()`
    - P&L calculation in `calculate_trade_pnl()`
  - **Data Structures**: No changes needed
  - **API Contracts**: No API changes (internal calculation)

- **Implementation Steps**:
  1. Update exit logic to apply slippage penalty when using fallback
  2. Add configurable fallback slippage parameter (default 1.5 cents)
  3. Apply penalty: subtract from bid (long exit), add to ask (short exit)
  4. Add logging when fallback slippage applied
  5. Add unit tests for fallback exit with slippage
  6. Verify P&L reflects slippage penalty

- **Validation Steps**:
  - Verify slippage penalty applied when bid/ask unavailable
  - Verify long exit P&L reduced by slippage
  - Verify short exit P&L reduced by slippage
  - Verify logging shows fallback slippage warnings

- **Definition of Done**: Exit logic applies slippage penalty for fallback
- **Rollback Plan**: Remove slippage penalty, restore optimistic fallback
- **Risk Assessment**: Low risk (additive change, improves realism)
- **Success Metrics**: Slippage penalty applied for 100% of fallback exits

---

### Epic 3: Fix End-of-Game Forced Close
**Priority**: High (fixes optimistic late-game execution for trades open at game end)
**Estimated Time**: 1-2 hours
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Apply Forced Slippage for End-of-Game Closes
- **ID**: S2-E3-S1
- **Type**: Bug Fix
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: S2-E2-S1 (Story 2.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - end-of-game logic)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] End-of-game forced close applies slippage penalty
  - [ ] Forced slippage: 2 cents (conservative estimate for late-game liquidity collapse)
  - [ ] Long positions: Subtract slippage from final_bid (even if bid available)
  - [ ] Short positions: Add slippage to final_ask (even if ask available)
  - [ ] Log warning when forced close with slippage applied
  - [ ] Unit tests verify forced slippage applied correctly
  - [ ] End-of-game trade P&L reflects slippage penalty

- **Technical Context**:
  - **Current State**: 
    ```python
    # End-of-game close (optimistic)
    final_kalshi_bid = last_point.get("kalshi_bid")
    if final_kalshi_bid is None:
        final_kalshi_bid = last_point["kalshi_price"]  # Fallback (no penalty)
    ```
  - **Required Changes**: 
    ```python
    # End-of-game close (realistic with forced slippage)
    forced_slippage_cents = 2.0  # Conservative estimate for late-game liquidity collapse
    final_kalshi_bid = last_point.get("kalshi_bid")
    final_kalshi_ask = last_point.get("kalshi_ask")
    
    if final_kalshi_bid is None:
        final_kalshi_bid = last_point["kalshi_price"] - (forced_slippage_cents / 100.0)
    if final_kalshi_ask is None:
        final_kalshi_ask = last_point["kalshi_price"] + (forced_slippage_cents / 100.0)
    
    # Apply forced slippage even if bid/ask available (late-game liquidity collapse)
    if position_type == "long_espn":
        final_kalshi_bid = final_kalshi_bid - (forced_slippage_cents / 100.0)
    else:  # short
        final_kalshi_ask = final_kalshi_ask + (forced_slippage_cents / 100.0)
    
    logger.warning(f"[END_OF_GAME] Forced close with {forced_slippage_cents} cent slippage penalty")
    ```
  - **Integration Points**: End-of-game handling in `simulate_trading_strategy()`
  - **Data Structures**: No changes needed
  - **API Contracts**: No API changes (internal calculation)

- **Implementation Steps**:
  1. Update end-of-game close logic to apply forced slippage
  2. Apply slippage to both bid and ask (even if available)
  3. Add logging when forced slippage applied
  4. Add unit tests for forced close with slippage
  5. Verify end-of-game trade P&L reflects slippage

- **Validation Steps**:
  - Verify forced slippage applied to all end-of-game closes
  - Verify long exit P&L reduced by slippage
  - Verify short exit P&L reduced by slippage
  - Verify logging shows forced slippage warnings

- **Definition of Done**: End-of-game close applies forced slippage penalty
- **Rollback Plan**: Remove forced slippage, restore optimistic close
- **Risk Assessment**: Low risk (additive change, improves realism)
- **Success Metrics**: Forced slippage applied for 100% of end-of-game closes

---

### Epic 4: Add Realism Filters
**Priority**: Medium-High (improves realism, reduces noise trading)
**Estimated Time**: 4-6 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Add Minimum Holding Period
- **ID**: S2-E4-S1
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: S2-E3-S1 (Story 3.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - exit logic)
  - `webapp/api/endpoints/simulation.py` (add min_hold_seconds parameter)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Minimum holding period enforced (configurable, default 30 seconds)
  - [ ] Exit only allowed if `exit_time - entry_time >= min_hold_seconds`
  - [ ] API accepts `min_hold_seconds` parameter (default: 30)
  - [ ] Log warning when exit blocked by minimum holding period
  - [ ] Unit tests verify minimum holding period enforcement
  - [ ] Reduces noise trading (fewer micro-trades)

- **Technical Context**:
  - **Current State**: No minimum holding period (allows immediate exits)
  - **Required Changes**: 
    ```python
    # Exit logic with minimum holding period
    min_hold_seconds = 30  # Configurable, default 30
    time_held = timestamp - state.entry_timestamp
    
    if abs_divergence < exit_threshold and time_held >= min_hold_seconds:
        # Exit allowed
    elif abs_divergence < exit_threshold and time_held < min_hold_seconds:
        # Exit blocked by minimum holding period
        logger.debug(f"[EXIT] Exit blocked - minimum holding period not met ({time_held}s < {min_hold_seconds}s)")
    ```
  - **Integration Points**: 
    - Exit logic in `simulate_trading_strategy()`
    - API parameter in `simulation.py`
  - **Data Structures**: No changes needed
  - **API Contracts**: Add `min_hold_seconds` parameter (optional, default 30)

- **Implementation Steps**:
  1. Add `min_hold_seconds` parameter to `simulate_trading_strategy()`
  2. Calculate `time_held = exit_time - entry_time`
  3. Check `time_held >= min_hold_seconds` before allowing exit
  4. Add API parameter `min_hold_seconds` (default: 30)
  5. Add logging when exit blocked
  6. Add unit tests

- **Validation Steps**:
  - Verify exit blocked when time_held < min_hold_seconds
  - Verify exit allowed when time_held >= min_hold_seconds
  - Verify API accepts min_hold_seconds parameter
  - Verify fewer trades (reduced noise trading)

- **Definition of Done**: Minimum holding period enforced
- **Rollback Plan**: Remove minimum holding period check
- **Risk Assessment**: Low risk (additive feature, improves realism)
- **Success Metrics**: Minimum holding period enforced for 100% of exits

### Story 4.2: Add Hysteresis Exit Logic
- **ID**: S2-E4-S2
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: S2-E4-S1 (Story 4.1)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - exit logic)
- **Files to Create**: None
- **Dependencies**: Track previous divergence value

- **Acceptance Criteria**:
  - [ ] Exit only allowed if divergence crossed FROM outside threshold TO inside threshold
  - [ ] Track `prev_abs_divergence_prob` in simulation state
  - [ ] Exit condition: `abs_divergence_prob < exit_threshold AND prev_abs_divergence_prob >= exit_threshold`
  - [ ] Prevents churn when hovering near threshold
  - [ ] Unit tests verify hysteresis logic
  - [ ] Reduces fee churn

- **Technical Context**:
  - **Current State**: 
    ```python
    # Exit logic (allows churn)
    if abs_divergence < exit_threshold:
        # Exit immediately (even if hovering near threshold)
    ```
  - **Required Changes**: 
    ```python
    # Exit logic with hysteresis (prevents churn)
    if abs_divergence_prob < exit_threshold and prev_abs_divergence_prob >= exit_threshold:
        # Exit (divergence crossed from outside to inside threshold)
    ```
  - **Integration Points**: Exit logic in `simulate_trading_strategy()`
  - **Data Structures**: Add `prev_abs_divergence_prob` to `SimulationState`
  - **API Contracts**: No API changes (internal logic)

- **Implementation Steps**:
  1. Add `prev_abs_divergence_prob` to `SimulationState` dataclass
  2. Update exit logic to check `prev_abs_divergence_prob >= exit_threshold`
  3. Update `prev_abs_divergence_prob` after each data point
  4. Add unit tests for hysteresis logic
  5. Verify churn reduction

- **Validation Steps**:
  - Verify exit only when divergence crosses from outside to inside
  - Verify no exit when hovering near threshold
  - Verify fewer trades (reduced churn)

- **Definition of Done**: Hysteresis exit logic implemented
- **Rollback Plan**: Remove hysteresis check, restore immediate exit
- **Risk Assessment**: Low risk (additive feature, improves realism)
- **Success Metrics**: Hysteresis prevents churn for 100% of threshold hovers

### Story 4.3: Add ESPN Direction Confirmation
- **ID**: S2-E4-S3
- **Type**: Feature
- **Priority**: Medium-High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: S2-E4-S2 (Story 4.2)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (function: `simulate_trading_strategy()` - entry logic)
- **Files to Create**: None
- **Dependencies**: Track previous divergence value

- **Acceptance Criteria**:
  - [ ] Entry only allowed if divergence is widening (not shrinking)
  - [ ] Long entry: `divergence_prob > entry_threshold AND divergence_prob > prev_divergence_prob`
  - [ ] Short entry: `divergence_prob < -entry_threshold AND divergence_prob < prev_divergence_prob`
  - [ ] Prevents noise entries (only enter on signal, not noise)
  - [ ] Unit tests verify direction confirmation
  - [ ] Dramatically improves trade quality

- **Technical Context**:
  - **Current State**: 
    ```python
    # Entry logic (allows noise)
    if divergence > entry_threshold:
        # Enter long (even if divergence is shrinking)
    ```
  - **Required Changes**: 
    ```python
    # Entry logic with direction confirmation (filters noise)
    if divergence_prob > entry_threshold and divergence_prob > prev_divergence_prob:
        # Enter long (divergence is widening, not shrinking)
    elif divergence_prob < -entry_threshold and divergence_prob < prev_divergence_prob:
        # Enter short (divergence is widening, not shrinking)
    ```
  - **Integration Points**: Entry logic in `simulate_trading_strategy()`
  - **Data Structures**: Use `prev_divergence_prob` from `SimulationState` (already added for hysteresis)
  - **API Contracts**: No API changes (internal logic)

- **Implementation Steps**:
  1. Update entry logic to check `divergence_prob > prev_divergence_prob` (long) or `divergence_prob < prev_divergence_prob` (short)
  2. Track `prev_divergence_prob` in simulation state (already added for hysteresis)
  3. Add unit tests for direction confirmation
  4. Verify trade quality improvement

- **Validation Steps**:
  - Verify entry only when divergence widening
  - Verify no entry when divergence shrinking
  - Verify fewer trades (reduced noise entries)
  - Verify improved win rate

- **Definition of Done**: Direction confirmation implemented
- **Rollback Plan**: Remove direction check, restore immediate entry
- **Risk Assessment**: Low risk (additive feature, improves realism)
- **Success Metrics**: Direction confirmation filters noise for 100% of entries

### Story 4.4: Add Game Phase Stratification
- **ID**: S2-E4-S4
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: S2-E4-S3 (Story 4.3)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (add phase calculation to Trade)
  - `webapp/api/endpoints/simulation.py` (add phase aggregation)
- **Files to Create**: None
- **Dependencies**: Game start time and duration available

- **Acceptance Criteria**:
  - [ ] Trade objects include `game_phase` field ("Q1", "Q2-Q3", "Q4")
  - [ ] Phase calculated as: `phase_ratio = (trade_time - game_start) / game_duration`
  - [ ] Q1: phase_ratio < 0.25
  - [ ] Q2-Q3: 0.25 <= phase_ratio < 0.75
  - [ ] Q4: phase_ratio >= 0.75
  - [ ] API response includes phase breakdown (profit, trades, win rate by phase)
  - [ ] Unit tests verify phase calculation

- **Technical Context**:
  - **Current State**: No phase information in trades
  - **Required Changes**: 
    ```python
    # Add phase to Trade dataclass
    game_phase: Optional[str]  # "Q1", "Q2-Q3", "Q4"
    
    # Calculate phase in simulate_trading_strategy()
    game_duration = game_end_time - game_start_time
    trade_time = trade.entry_time - game_start_time
    phase_ratio = trade_time / game_duration
    
    if phase_ratio < 0.25:
        trade.game_phase = "Q1"
    elif phase_ratio < 0.75:
        trade.game_phase = "Q2-Q3"
    else:
        trade.game_phase = "Q4"
    ```
  - **Integration Points**: 
    - Trade creation in `simulate_trading_strategy()`
    - Aggregation in `simulation.py`
  - **Data Structures**: Add `game_phase` to `Trade` dataclass
  - **API Contracts**: Add phase breakdown to API response

- **Implementation Steps**:
  1. Add `game_phase` field to `Trade` dataclass
  2. Calculate phase ratio in `simulate_trading_strategy()`
  3. Assign phase to each trade
  4. Aggregate results by phase in `simulation.py`
  5. Add phase breakdown to API response
  6. Add unit tests

- **Validation Steps**:
  - Verify phase calculated correctly for each trade
  - Verify phase breakdown in API response
  - Verify phase aggregation correct

- **Definition of Done**: Game phase stratification implemented
- **Rollback Plan**: Remove phase field, restore without phase breakdown
- **Risk Assessment**: Low risk (additive feature, provides insights)
- **Success Metrics**: Phase calculated for 100% of trades

---

### Epic 5: Code Clarity and Cache Invalidation
**Priority**: Medium (improves maintainability)
**Estimated Time**: 2-3 hours
**Dependencies**: Epic 4 complete
**Status**: Not Started
**Phase Assignment**: Phase 5

### Story 5.1: Rename Divergence Variables for Clarity
- **ID**: S2-E5-S1
- **Type**: Refactor
- **Priority**: Medium
- **Estimate**: 1 hour
- **Phase**: Phase 5
- **Prerequisites**: S2-E4-S4 (Story 4.4)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (rename divergence variables)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Rename `divergence` to `divergence_prob` (explicit: probability units)
  - [ ] Rename `abs_divergence` to `abs_divergence_prob`
  - [ ] Update all references throughout code
  - [ ] Logs still display in cents (conversion: `divergence_prob * 100`)
  - [ ] Code is clearer (units explicit in variable names)
  - [ ] No functional changes (rename only)

- **Technical Context**:
  - **Current State**: 
    ```python
    divergence = espn_prob - kalshi_price  # Unclear units
    abs_divergence = abs(divergence)
    ```
  - **Required Changes**: 
    ```python
    divergence_prob = espn_prob - kalshi_price  # Explicit: probability units (0-1)
    abs_divergence_prob = abs(divergence_prob)
    # Logs still show cents: logger.info(f"Divergence: {divergence_prob*100:.2f} cents")
    ```
  - **Integration Points**: All divergence calculations in `simulate_trading_strategy()`
  - **Data Structures**: No changes needed
  - **API Contracts**: No API changes (internal rename)

- **Implementation Steps**:
  1. Find all occurrences of `divergence` and `abs_divergence`
  2. Rename to `divergence_prob` and `abs_divergence_prob`
  3. Update all references
  4. Verify logs still display in cents
  5. Run tests to verify no functional changes

- **Validation Steps**:
  - Verify all variables renamed
  - Verify logs still display correctly
  - Verify no functional changes (same results)

- **Definition of Done**: Divergence variables renamed for clarity
- **Rollback Plan**: Revert rename, restore original names
- **Risk Assessment**: Low risk (rename only, no functional changes)
- **Success Metrics**: All variables renamed, code clearer

### Story 5.2: Invalidate Cached Results
- **ID**: S2-E5-S2
- **Type**: Configuration / Maintenance
- **Priority**: High
- **Estimate**: 0.5 hours
- **Phase**: Phase 5
- **Prerequisites**: S2-E5-S1 (Story 5.1)
- **Files to Modify**: 
  - `webapp/api/endpoints/simulation.py` (add cache version check or clear cache)
- **Files to Create**: None
- **Dependencies**: Cache clearing mechanism

- **Acceptance Criteria**:
  - [ ] Old cached results cleared (or marked as invalid)
  - [ ] Cache versioning implemented (optional but recommended)
  - [ ] New results cached with corrected P&L
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

### Story 5.3: Update Documentation
- **ID**: S2-E5-S3
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 1 hour
- **Phase**: Phase 5
- **Prerequisites**: S2-E5-S2 (Story 5.2)
- **Files to Modify**: 
  - `scripts/simulate_trading_strategy.py` (docstrings)
  - `webapp/api/endpoints/simulation.py` (docstrings)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Function docstrings updated to reflect risk-neutral sizing
  - [ ] Exit logic with slippage documented
  - [ ] End-of-game forced close with slippage documented
  - [ ] Realism filters documented (minimum holding period, hysteresis, direction confirmation)
  - [ ] Game phase stratification documented
  - [ ] API documentation updated if needed

- **Technical Context**:
  - **Current State**: Documentation may not reflect new logic
  - **Required Changes**: Update all documentation to reflect fixes and improvements

- **Implementation Steps**:
  1. Update function docstrings
  2. Update API documentation
  3. Add comments explaining realism filters
  4. Document phase calculation

- **Validation Steps**:
  - Verify documentation is accurate
  - Verify all functions have updated docstrings

- **Definition of Done**: Documentation updated and accurate
- **Rollback Plan**: N/A (documentation only)
- **Risk Assessment**: Low risk (documentation only)
- **Success Metrics**: All documentation accurate

### Story 5.4: Quality Gate Validation
- **ID**: S2-E5-S4
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 5
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All code follows type hints (no `Any` types unless necessary)
  - [ ] All functions have docstrings
  - [ ] Short position sizing verified correct for sample trades
  - [ ] Exit slippage verified applied correctly
  - [ ] End-of-game forced slippage verified applied correctly
  - [ ] Realism filters verified working correctly
  - [ ] No breaking changes to API (response structure preserved, new fields added)

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
  - Verify API responses unchanged (except new fields)

- **Definition of Done**: All quality gates pass
- **Rollback Plan**: Fix issues until gates pass
- **Risk Assessment**: Low risk (quality checks)
- **Success Metrics**: 100% quality gate pass rate

---

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: State Machine Pattern (Enhanced)
- **Category**: Behavioral
- **Intent**: Track simulation state including previous divergence for hysteresis and direction confirmation
- **Implementation**: Enhanced `SimulationState` with `prev_divergence_prob` and `prev_abs_divergence_prob`
- **Benefits**: 
  - Enables hysteresis and direction confirmation
  - Clear state tracking
  - Easy to extend
- **Trade-offs**: 
  - Slightly more state to track (minimal overhead)
  - More complex state transitions (acceptable for correctness)

### Algorithm Analysis

### Algorithm: Risk-Neutral Position Sizing
- **Type**: Financial Calculation
- **Complexity**: Time O(1), Space O(1)
- **Description**: Calculate position size to ensure same maximum risk for long and short positions
- **Use Case**: Correct position sizing for binary markets
- **Performance**: Constant time per trade, highly efficient

### Design Decision Analysis

### Design Decision: Short Position Sizing (Risk-Neutral vs Notional)
- **Problem**: Current short sizing causes risk understatement, making short profits appear inflated relative to assumed risk
- **Context**: Need symmetric risk for long and short positions in binary markets
- **Project Scope**: Single developer, 2-3 day sprint, critical fix

**Options**:

**Option 1: Risk-Neutral Sizing (CHOSEN)**
- **Design Pattern**: Risk Parity Model
- **Algorithm**: Long: `bet_amount / entry_price`, Short: `bet_amount / (1 - entry_price)`
- **Implementation Complexity**: Low (simple formula change)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent
- **Cost-Benefit**: Low cost, **HIGH benefit** (fixes fundamental bias)
- **Over-Engineering Risk**: None
- **Selected**: ✅ **CHOSEN** - Correct for binary markets

**Option 2: Keep Current Sizing (WRONG)**
- **Design Pattern**: Notional Sizing Model
- **Algorithm**: Both: `bet_amount / entry_price`
- **Implementation Complexity**: Low (already implemented)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent
- **Cost-Benefit**: Low cost, **ZERO benefit** (maintains bias)
- **Over-Engineering Risk**: None
- **Selected**: ❌ **REJECTED** - Maintains risk understatement

**Chosen Solution**: Risk-neutral sizing for shorts
- **Rationale**: Binary markets have asymmetric maximum loss (long: entry_price, short: 1-entry_price). Risk-neutral sizing ensures both positions have same maximum risk.
- **Implementation**: Change short sizing to `bet_amount / (1 - entry_price)`
- **Documentation**: Clearly document risk-neutral sizing rationale

**Pros and Cons**:

**Pros**:
- **Correctness**: ✅ Fixes fundamental bias
- **Risk Assessment**: ✅ Accurate maximum loss calculation
- **Symmetry**: ✅ Long and short have same risk

**Cons**:
- **Breaking Change**: ⚠️ All short trade P&L will change (mitigated by cache clearing)

**Risk Assessment**: 
- **Low Risk**: Well-understood formula, straightforward implementation
- **Mitigation**: Unit tests, cache clearing, documentation

### Design Decision: Exit Logic (Require Bid/Ask vs Slippage Penalty)
- **Problem**: Entries require bid/ask, but exits allow fallback to mid-price (optimistic for subset of trades)
- **Context**: Need symmetric requirements or realistic penalty for fallback
- **Project Scope**: Single developer, prioritize correctness

**Options**:

**Option 1: Require Bid/Ask for Exit (Strict)**
- **Design Pattern**: Strict Execution Model
- **Algorithm**: Only exit when bid/ask available, mark as unrealized otherwise
- **Implementation Complexity**: Low
- **Maintenance Overhead**: Low
- **Scalability**: Excellent
- **Cost-Benefit**: Low cost, **HIGH benefit** (realistic)
- **Over-Engineering Risk**: None
- **Selected**: ❌ **REJECTED** - Too strict, many trades marked unrealized

**Option 2: Apply Slippage Penalty for Fallback (CHOSEN)**
- **Design Pattern**: Realistic Execution Model
- **Algorithm**: Apply 1.5 cent slippage penalty when using mid-price fallback
- **Implementation Complexity**: Low
- **Maintenance Overhead**: Low
- **Scalability**: Excellent
- **Cost-Benefit**: Low cost, **HIGH benefit** (realistic, pragmatic)
- **Over-Engineering Risk**: None
- **Selected**: ✅ **CHOSEN** - Realistic and pragmatic

**Chosen Solution**: Apply slippage penalty for fallback exits
- **Rationale**: Allows all trades to close while accounting for execution cost. More pragmatic than strict requirement.
- **Implementation**: Subtract slippage from bid (long exit), add to ask (short exit) when using fallback
- **Documentation**: Clearly document slippage penalty rationale

**Pros and Cons**:

**Pros**:
- **Realism**: ✅ Accounts for execution cost
- **Pragmatism**: ✅ Allows all trades to close
- **Symmetry**: ✅ Accounts for execution difficulty

**Cons**:
- **Estimation**: ⚠️ Requires estimating slippage (conservative estimate acceptable)

**Risk Assessment**: 
- **Low Risk**: Conservative slippage estimate, straightforward implementation
- **Mitigation**: Use conservative estimate (1.5 cents), document as assumption

---

## Testing Strategy

### Testing Approach
- **Unit Tests**: Test position sizing, exit logic, end-of-game close, realism filters
- **Integration Tests**: Test full simulation flow with all fixes
- **E2E Tests**: Run simulation on sample games and verify results
- **Performance Tests**: Verify no performance degradation

### Test Cases Required

1. **Short Position Sizing**:
   - Entry: 0.80 → Should be 100 contracts for $20 bet
   - Entry: 0.50 → Should be 40 contracts for $20 bet
   - Entry: 0.90 → Should be 200 contracts for $20 bet
   - Verify maximum loss equals bet_amount

2. **Exit Logic with Slippage**:
   - Exit with bid/ask → No slippage penalty
   - Exit without bid/ask → Slippage penalty applied
   - Verify P&L reflects slippage

3. **End-of-Game Forced Close**:
   - End-of-game position → Forced slippage applied
   - Verify P&L reflects forced slippage

4. **Minimum Holding Period**:
   - Exit before min_hold → Blocked
   - Exit after min_hold → Allowed
   - Verify fewer trades

5. **Hysteresis Exit**:
   - Hovering near threshold → No exit
   - Crossing from outside to inside → Exit allowed
   - Verify churn reduction

6. **Direction Confirmation**:
   - Divergence widening → Entry allowed
   - Divergence shrinking → Entry blocked
   - Verify trade quality improvement

7. **Game Phase Stratification**:
   - Verify phase calculated correctly
   - Verify phase breakdown in results

---

## Deployment Plan
- **Pre-Deployment**: 
  - Clear simulation cache (old results contain systematic bias)
  - Verify all tests pass
  - Verify corrected results on sample games
- **Deployment Steps**: 
  - Deploy code changes
  - Clear cache (via API or manual)
  - Monitor for errors
- **Post-Deployment**: 
  - Verify new simulations produce corrected results
  - Verify short sizing correct
  - Verify realism filters working
  - Monitor for any issues
- **Rollback Plan**: 
  - Revert code changes
  - Restore old sizing (not recommended - old results contain bias)

---

## Risk Assessment
- **Technical Risks**: 
  - **Risk**: Breaking change - all short trade P&L will change → **Mitigation**: Clear cache, document change, verify with tests
  - **Risk**: Slippage estimation accuracy → **Mitigation**: Use conservative estimates, document as assumption
  - **Risk**: Realism filters may reduce trade count significantly → **Mitigation**: Configurable parameters, document impact
- **Business Risks**: 
  - **Risk**: Results show strategy less profitable after fixes → **Mitigation**: This is correct - honest assessment
  - **Risk**: Fewer trades after realism filters → **Mitigation**: Expected - filters noise, improves quality
- **Resource Risks**: 
  - **Risk**: Time overrun → **Mitigation**: Prioritize critical fixes (sizing, exit logic), defer optional improvements

---

## Success Metrics
- **Technical**: 
  - Short position sizing correct for 100% of trades
  - Exit slippage applied for 100% of fallback exits
  - End-of-game forced slippage applied for 100% of forced closes
  - Realism filters working correctly
  - All quality gates pass
- **Business**: 
  - Results are accurate (no systematic bias)
  - Risk metrics accurate
  - Strategy evaluation reliable
- **Sprint**: 
  - All stories completed
  - All acceptance criteria met
  - Documentation updated

---

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] Short position sizing uses risk-neutral formula
- [ ] Exit logic applies slippage penalty for fallback
- [ ] End-of-game forced close applies slippage penalty
- [ ] Minimum holding period enforced
- [ ] Hysteresis exit logic prevents churn
- [ ] Direction confirmation filters noise
- [ ] Game phase stratification implemented
- [ ] Divergence variables renamed for clarity
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

