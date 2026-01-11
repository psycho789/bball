# Betting Odds Simulation and Calibration Analysis v1

**Date**: 2025-01-28  
**Status**: Draft  
**Author**: AI Assistant  
**Version**: v1.0  
**Purpose**: Comprehensive analysis for implementing betting odds simulation (arbitrage detection) and Kalshi betting odds calibration analysis

## Executive Summary

### Key Findings
- **Betting Odds Data Source**: Kalshi candlesticks table contains `price_close`, `yes_bid_close`, `yes_ask_close` in cents (0-100)
- **ESPN Odds Data Source**: ESPN probabilities table contains `home_win_percentage` (0-100)
- **Simulation Strategy**: Track divergence between ESPN and Kalshi odds, simulate trades when divergence exceeds threshold (e.g., 5 cents), close when convergence occurs
- **Calibration Analysis**: Apply same calibration metrics (Brier score, reliability curves) to Kalshi betting odds as currently done for ESPN odds
- **Outlier Analysis**: Filter first/last 5 minutes of games to check robustness of findings

### Critical Questions to Answer
1. **Data Alignment**: How to align ESPN probabilities with Kalshi bid/ask prices for accurate divergence calculation?
2. **Trade Simulation**: What constitutes a "trade" - buying when ESPN > Kalshi+5, selling when ESPN < Kalshi-5?
3. **Profit Calculation**: How to calculate profit/loss using bid-ask spread and actual game outcomes?
4. **Calibration Metrics**: Which existing calibration functions can be reused for Kalshi odds?

### Recommended Actions
- **Action 1**: [Priority: High] - Design simulation algorithm for arbitrage detection
- **Action 2**: [Priority: High] - Implement Kalshi calibration analysis (reuse ESPN calibration functions)
- **Action 3**: [Priority: Medium] - Add time-based filtering (exclude first/last 5 minutes)
- **Action 4**: [Priority: Medium] - Create visualization for calibration curves and simulation results

## Problem Statement

### Current Situation

**Existing ESPN Calibration Analysis**:
- **File**: `webapp/api/endpoints/stats.py` - Individual game statistics
- **File**: `webapp/api/endpoints/aggregate_stats.py` - Aggregate statistics across all games
- **Metrics Calculated**:
  - Brier score (mean squared error of probabilities)
  - Log loss (with probability clipping to 0.01-0.99)
  - Reliability curves (calibration across 10 probability bins: 0-10%, 10-20%, etc.)
  - Time-sliced Brier scores (Q1, Halftime, Start of Q4, Final 2 minutes)
  - Phase-based Brier scores (Early, Mid, Late, Clutch)
  - Decision-weighted metrics (time-weighted Brier, distance-weighted MAE)

**Current Data Sources**:
- **ESPN Probabilities**: `espn.probabilities_raw_items` table
  - `home_win_percentage`: Float (0-100)
  - `away_win_percentage`: Float (0-100)
  - `last_modified_utc`: Timestamp
  - `game_id`: String
- **Kalshi Betting Odds**: `kalshi.candlesticks` table
  - `price_close`: Integer (cents, 0-100) - resolved price
  - `yes_bid_close`: Integer (cents) - bid price
  - `yes_ask_close`: Integer (cents) - ask price
  - `period_ts`: Timestamp
  - `ticker`: String (market identifier)
- **Game Matching**: `kalshi.markets_with_games` table links Kalshi markets to ESPN games via `espn_event_id`

**Current Data Alignment**:
- **File**: `webapp/api/endpoints/probabilities.py` - Aligns ESPN and Kalshi data by wall-clock time
- **Algorithm**: Time alignment (same as historical data)
- **Big O**: O(n + m) where n = ESPN points, m = Kalshi candles
- **Time Window**: Matches timestamps within 60 seconds

### Pain Points
- **No Trading Simulation**: Cannot answer "would I make money if I traded on ESPN-Kalshi divergence?"
- **No Kalshi Calibration**: Kalshi odds calibration not calculated (only ESPN calibration exists)
- **No Outlier Filtering**: No analysis of how excluding first/last 5 minutes affects results
- **Limited Profit Analysis**: No calculation of actual profit/loss from simulated trades

### Business Impact
- **Trading Strategy Validation**: Understand if ESPN-Kalshi divergence represents profitable opportunities
- **Market Efficiency Analysis**: Determine if betting markets are well-calibrated
- **Risk Assessment**: Identify time periods where divergence is most/least reliable

### Success Criteria
- **Simulation Accuracy**: Correctly simulate trades based on divergence thresholds
- **Profit Calculation**: Accurate profit/loss calculation using bid-ask spreads
- **Calibration Completeness**: Full calibration analysis for Kalshi odds (matching ESPN analysis)
- **Outlier Robustness**: Analysis with and without first/last 5 minutes of games

## Data Source Analysis

### Data Source 1: ESPN Probabilities

**Source**: `espn.probabilities_raw_items` table  
**File Reference**: `webapp/api/endpoints/probabilities.py:150-200`

**Data Structure**:
```sql
SELECT 
    game_id,
    last_modified_utc,
    home_win_percentage,  -- Float 0-100
    away_win_percentage   -- Float 0-100
FROM espn.probabilities_raw_items
WHERE game_id = ?
ORDER BY last_modified_utc
```

**Data Characteristics**:
- **Format**: Home win percentage (0-100), converted to 0-1 probability for calculations
- **Frequency**: Variable (depends on game events)
- **Coverage**: All games with ESPN data
- **Time Alignment**: Uses `last_modified_utc` timestamp

**Usage in Simulation**:
- **Primary Signal**: ESPN probability represents "model prediction"
- **Comparison Point**: Compare ESPN probability to Kalshi market price
- **Divergence Calculation**: `abs(espn_prob - kalshi_price)` in probability space (0-1)

### Data Source 2: Kalshi Betting Odds

**Source**: `kalshi.candlesticks` table  
**File Reference**: `webapp/api/endpoints/probabilities.py:180-195`

**Data Structure**:
```sql
SELECT 
    c.period_ts,
    c.price_close,        -- Integer cents (0-100)
    c.yes_bid_close,      -- Integer cents (0-100)
    c.yes_ask_close,      -- Integer cents (0-100)
    m.team_side           -- 'home' or 'away'
FROM kalshi.candlesticks c
JOIN kalshi.markets_with_games m ON c.ticker = m.ticker
WHERE m.espn_event_id = ?
ORDER BY c.period_ts
```

**Data Characteristics**:
- **Format**: Prices in cents (0-100), converted to 0-1 probability for calculations
- **Price Selection Logic** (from `probabilities.py:290-294`):
  - Primary: Use `price_close` if available (resolved price)
  - Fallback: Use mid-price `(yes_bid_close + yes_ask_close) / 2.0` if `price_close` is NULL
- **Bid-Ask Spread**: Available for profit calculation (`yes_bid_close`, `yes_ask_close`)
- **Frequency**: Candlestick intervals (typically 1-minute or 5-minute candles)
- **Coverage**: Games with Kalshi markets

**Usage in Simulation**:
- **Market Price**: `price_close` or mid-price represents "market consensus"
- **Trade Execution**: Use bid/ask prices for realistic trade simulation
  - **Buy "Yes"**: Pay `yes_ask_close` (ask price)
  - **Sell "Yes"**: Receive `yes_bid_close` (bid price)
- **Profit Calculation**: 
  - If home wins: Profit = `(100 - yes_ask_close)` - `yes_bid_close` (if sold before end)
  - If home loses: Loss = `yes_ask_close` (if bought, contract expires worthless)

### Data Source 3: Game Outcomes

**Source**: `espn.prob_event_state` table  
**File Reference**: `webapp/api/endpoints/aggregate_stats.py:88-96`

**Data Structure**:
```sql
SELECT 
    game_id,
    MAX(home_score) as final_home_score,
    MAX(away_score) as final_away_score,
    MAX(final_winning_team) as winner
FROM espn.prob_event_state
GROUP BY game_id
```

**Data Characteristics**:
- **Outcome**: Binary (home won = 1, away won = 0)
- **Usage**: Required for:
  - Brier score calculation (actual outcome vs. predicted probability)
  - Profit/loss calculation (did the bet win or lose?)
  - Calibration analysis (how well do probabilities match outcomes?)

### Data Source 4: Game Timing

**Source**: `espn.scoreboard_games` table  
**File Reference**: `webapp/api/endpoints/probabilities.py:100-120`

**Data Structure**:
```sql
SELECT 
    event_id as game_id,
    event_date as game_start_time
FROM espn.scoreboard_games
WHERE event_id = ?
```

**Data Characteristics**:
- **Game Start**: `event_date` timestamp
- **Usage**: 
  - Time alignment (convert timestamps to game-relative time)
  - Outlier filtering (exclude first 5 minutes, last 5 minutes)
  - Game duration calculation

## Simulation Algorithm Design

### Algorithm 1: Divergence-Based Trading Simulation

**Algorithm Name**: Divergence Threshold Trading Simulation  
**Algorithm Type**: Event-driven state machine  
**Big O Notation**: 
- Time Complexity: O(n) where n = aligned data points
- Space Complexity: O(1) for state tracking, O(k) where k = number of open positions

**Problem Statement**:
Simulate trading strategy: "If I bought/sold when ESPN odds were more than 5 cents outside betting odds and closed when they converged, would I make money?"

**Algorithm Design**:

**State Variables**:
- `open_position`: None | "long_espn" | "short_espn"
  - `long_espn`: ESPN probability > Kalshi price + threshold (bet ESPN is right, Kalshi is wrong)
  - `short_espn`: ESPN probability < Kalshi price - threshold (bet ESPN is wrong, Kalshi is right)
- `entry_espn_prob`: Float (ESPN probability at entry)
- `entry_kalshi_price`: Float (Kalshi price at entry)
- `entry_kalshi_bid`: Float (Kalshi bid at entry, for selling)
- `entry_kalshi_ask`: Float (Kalshi ask at entry, for buying)
- `entry_timestamp`: Timestamp
- `total_profit`: Float (cumulative profit/loss)
- `trades`: List of completed trades

**Algorithm Steps**:

1. **Initialize**: 
   - `open_position = None`
   - `total_profit = 0.0`
   - `trades = []`

2. **For each aligned (ESPN, Kalshi) data point**:
   - Calculate divergence: `divergence = espn_prob - kalshi_price`
   - Calculate absolute divergence: `abs_divergence = abs(divergence)`
   
3. **Entry Logic** (if `open_position == None`):
   - **Long ESPN** (buy when ESPN > Kalshi + threshold):
     - If `divergence > threshold` (e.g., 0.05 = 5 cents):
       - `open_position = "long_espn"`
       - `entry_espn_prob = espn_prob`
       - `entry_kalshi_price = kalshi_price`
       - `entry_kalshi_ask = yes_ask_close / 100.0` (buy at ask)
       - `entry_timestamp = timestamp`
       - **Trade Action**: Buy "Yes" contract at `yes_ask_close` cents
   
   - **Short ESPN** (sell when ESPN < Kalshi - threshold):
     - If `divergence < -threshold` (e.g., -0.05 = -5 cents):
       - `open_position = "short_espn"`
       - `entry_espn_prob = espn_prob`
       - `entry_kalshi_price = kalshi_price`
       - `entry_kalshi_bid = yes_bid_close / 100.0` (sell at bid)
       - `entry_timestamp = timestamp`
       - **Trade Action**: Sell "Yes" contract at `yes_bid_close` cents

4. **Exit Logic** (if `open_position != None`):
   - **Convergence Exit**: Close when divergence returns to near-zero
     - If `abs_divergence < exit_threshold` (e.g., 0.01 = 1 cent):
       - Calculate profit/loss based on position type and outcome
       - Close position
       - Add trade to `trades` list
       - Update `total_profit`
   
   - **Forced Exit** (end of game):
     - If game ended and position still open:
       - Close position using final outcome
       - Calculate profit/loss
       - Add trade to `trades` list

5. **Profit Calculation**:
   - **Long ESPN Position** (bought "Yes" contract):
     - **If home wins**: Profit = `(100 - entry_kalshi_ask) - exit_kalshi_bid` (in cents)
       - Bought at ask, can sell at bid (or contract resolves to 100)
     - **If home loses**: Loss = `entry_kalshi_ask` (contract expires worthless)
   
   - **Short ESPN Position** (sold "Yes" contract):
     - **If home wins**: Loss = `(100 - entry_kalshi_bid)` (must buy back at higher price or pay 100)
     - **If home loses**: Profit = `entry_kalshi_bid` (contract expires worthless, keep premium)

**Design Pattern**: State Machine Pattern  
**Implementation Complexity**: Medium (4-6 hours)  
**Maintenance Overhead**: Low (straightforward logic)

**Pros**:
- Realistic simulation using actual bid/ask prices
- Handles both long and short positions
- Tracks entry/exit conditions clearly
- Can analyze profit distribution

**Cons**:
- Assumes perfect execution (no slippage, no latency)
- Does not account for transaction costs (if any)
- May miss optimal exit timing (uses simple convergence threshold)

**Risk Assessment**:
- **Risk 1**: Divergence may never converge (position held until game end)
  - **Mitigation**: Force exit at game end, calculate final P/L
- **Risk 2**: Bid-ask spread may be wide, reducing profitability
  - **Mitigation**: Track spread impact, report separately
- **Risk 3**: Multiple entry/exit cycles in same game
  - **Mitigation**: Allow multiple trades per game, track separately

### Algorithm 2: Time-Based Filtering

**Algorithm Name**: Time Window Filtering  
**Algorithm Type**: Data filtering  
**Big O Notation**: 
- Time Complexity: O(n) where n = data points
- Space Complexity: O(n) for filtered dataset

**Problem Statement**:
Exclude first 5 minutes and last 5 minutes of games to check robustness of findings (outlier analysis).

**Algorithm Design**:

**Inputs**:
- `timestamps`: List of timestamps (aligned to game timeline)
- `game_start_timestamp`: Unix timestamp of game start
- `game_duration_seconds`: Total game duration
- `exclude_first_seconds`: Integer (default: 300 = 5 minutes)
- `exclude_last_seconds`: Integer (default: 300 = 5 minutes)

**Algorithm Steps**:

1. **Calculate time windows**:
   - `start_cutoff = game_start_timestamp + exclude_first_seconds`
   - `end_cutoff = game_start_timestamp + game_duration_seconds - exclude_last_seconds`

2. **Filter data points**:
   - Keep points where: `start_cutoff <= timestamp <= end_cutoff`
   - Discard points outside this window

3. **Apply to both ESPN and Kalshi data**:
   - Filter ESPN probabilities
   - Filter Kalshi candlesticks
   - Re-align filtered datasets

**Design Pattern**: Filter Pattern  
**Implementation Complexity**: Low (1-2 hours)  
**Maintenance Overhead**: Low

**Pros**:
- Simple to implement
- Allows sensitivity analysis (how do results change?)
- Identifies if outliers drive results

**Cons**:
- Reduces sample size (fewer data points)
- May miss important early/late game dynamics

## Calibration Analysis Design

### Calibration Metrics for Kalshi Odds

**Reuse Existing Functions**:
- **File**: `webapp/api/endpoints/stats.py`
- **Functions to Reuse**:
  - `calculate_brier_score()` - Lines 24-33
  - `calculate_log_loss()` - Already used for ESPN
  - `calculate_reliability_curve()` - Lines 376-445
  - `calculate_time_sliced_brier_scores()` - Lines 36-118
  - `calculate_phase_brier_scores()` - Lines 121-200

**Implementation Approach**:
1. **Extract Kalshi probabilities** (same as ESPN extraction)
   - Use `price_close` or mid-price from `kalshi.candlesticks`
   - Convert to home win probability (0-1)
   - Align with game outcomes

2. **Calculate calibration metrics** (identical to ESPN):
   - Brier score: `calculate_brier_score(kalshi_probs, actual_outcome)`
   - Log loss: `calculate_log_loss(kalshi_probs, actual_outcome)`
   - Reliability curve: `calculate_reliability_curve(kalshi_probs, actual_outcomes)`
   - Time-sliced Brier: `calculate_time_sliced_brier_scores(kalshi_probs, timestamps, game_start, outcome, duration)`
   - Phase-based Brier: `calculate_phase_brier_scores(kalshi_probs, timestamps, game_start, outcome, duration)`

3. **Aggregate across games** (same as ESPN aggregation):
   - Average Brier scores
   - Aggregate reliability curve (all probabilities across all games)
   - Phase-based averages

**Design Pattern**: Strategy Pattern (reuse existing calculation functions)  
**Algorithm**: Same as ESPN calibration (O(n) per game)  
**Big O**: O(n*m) where n = games, m = data points per game

**Pros**:
- Consistent methodology (same metrics for ESPN and Kalshi)
- Reuses existing, tested code
- Enables direct comparison (ESPN vs. Kalshi calibration)

**Cons**:
- Assumes Kalshi data format matches ESPN (probability format)
- May need adjustments for bid/ask spread (use mid-price or resolved price?)

## Visualization Requirements

### Visualization 1: Calibration Curve (Reliability Curve)

**Purpose**: Show how well Kalshi betting odds are calibrated (predicted probability vs. actual frequency)

**Data Source**: 
- Kalshi probabilities (binned into 10 bins: 0-10%, 10-20%, ..., 90-100%)
- Actual outcomes (home won = 1, away won = 0)

**Chart Type**: Line chart with diagonal reference line

**Axes**:
- **X-axis**: Predicted probability (bin centers: 5%, 15%, 25%, ..., 95%)
- **Y-axis**: Actual frequency (proportion of games where home actually won)

**Reference Line**: Diagonal line (y = x) representing perfect calibration

**Data Points**:
- For each bin: (predicted_prob, actual_freq, calibration_error)
- **Calibration Error**: `predicted_prob - actual_freq` (positive = overconfident, negative = underconfident)

**Visualization Library**: 
- **Frontend**: TradingView Lightweight Charts (if adding to existing charts)
- **Alternative**: Matplotlib/Plotly for analysis scripts
- **File Reference**: `webapp/static/js/stats.js` - Existing aggregate stats visualization

**Similar to**: ESPN reliability curve (already implemented in `aggregate_stats.py:795-800`)

### Visualization 2: Simulation Results Summary

**Purpose**: Show profit/loss distribution from simulated trades

**Data Source**: 
- `trades` list from simulation (each trade has: entry_time, exit_time, profit, position_type)

**Chart Types**:

**2a. Profit Distribution Histogram**:
- **X-axis**: Profit/loss (in cents or dollars)
- **Y-axis**: Number of trades
- **Bins**: 20-50 bins covering profit range
- **Show**: Mean, median, total profit

**2b. Cumulative Profit Over Time**:
- **X-axis**: Game number or timestamp
- **Y-axis**: Cumulative profit
- **Line**: Running total of profit/loss
- **Show**: Final total profit, max drawdown

**2c. Trade Frequency by Game Phase**:
- **X-axis**: Game phase (Early, Mid, Late, Clutch)
- **Y-axis**: Number of trades
- **Chart Type**: Bar chart
- **Show**: Which phases have most trading opportunities

**2d. Win Rate by Position Type**:
- **X-axis**: Position type (Long ESPN, Short ESPN)
- **Y-axis**: Win rate (%)
- **Chart Type**: Bar chart
- **Show**: Which strategy is more profitable

**Visualization Library**: 
- **Analysis Scripts**: Matplotlib/Plotly
- **Frontend** (if adding to UI): D3.js or Chart.js

### Visualization 3: Divergence Time Series

**Purpose**: Show ESPN-Kalshi divergence over time for a game

**Data Source**: 
- Aligned ESPN and Kalshi probabilities
- Divergence: `espn_prob - kalshi_price`

**Chart Type**: Line chart with shaded regions

**Axes**:
- **X-axis**: Game time (seconds from start)
- **Y-axis**: Divergence (probability difference, -1 to +1)

**Features**:
- **Line 1**: ESPN probability (0-1)
- **Line 2**: Kalshi price (0-1)
- **Shaded Region**: Divergence (ESPN - Kalshi)
- **Threshold Lines**: Horizontal lines at +0.05 and -0.05 (entry thresholds)
- **Trade Markers**: Vertical lines showing entry/exit points

**Visualization Library**: 
- **Frontend**: TradingView Lightweight Charts (similar to existing probability charts)
- **File Reference**: `webapp/static/js/chart.js` - Existing chart rendering

### Visualization 4: Comparison: ESPN vs. Kalshi Calibration

**Purpose**: Side-by-side comparison of ESPN and Kalshi calibration

**Chart Type**: Dual reliability curves

**Axes**:
- **X-axis**: Predicted probability (0-1)
- **Y-axis**: Actual frequency (0-1)

**Data Series**:
- **Series 1**: ESPN reliability curve (existing)
- **Series 2**: Kalshi reliability curve (new)
- **Reference**: Diagonal line (perfect calibration)

**Visualization Library**: 
- **Frontend**: TradingView Lightweight Charts or D3.js
- **File Reference**: `webapp/static/js/stats.js` - Aggregate stats page

## Implementation Plan

### Phase 1: Data Extraction and Alignment (Duration: 2-3 hours)

**Objective**: Extract and align ESPN and Kalshi data with time filtering support

**Files to Create/Modify**:
- `webapp/api/endpoints/simulation.py` (new) - Simulation endpoint
- Reuse: `webapp/api/endpoints/probabilities.py` - Data alignment logic

**Tasks**:
1. **Task 1.1**: Extract aligned ESPN-Kalshi data with time filtering
   - **Function**: `get_aligned_data_with_time_filter(game_id, exclude_first_seconds=300, exclude_last_seconds=300)`
   - **Returns**: Aligned (timestamp, espn_prob, kalshi_price, kalshi_bid, kalshi_ask, actual_outcome)
   - **Algorithm**: Time alignment + time window filtering
   - **Big O**: O(n + m) where n = ESPN points, m = Kalshi candles

2. **Task 1.2**: Extract game outcomes
   - **Function**: `get_game_outcome(game_id)`
   - **Returns**: (home_won: bool, final_home_score: int, final_away_score: int)
   - **Algorithm**: SQL query to `espn.prob_event_state`

### Phase 2: Trading Simulation Implementation (Duration: 4-6 hours)

**Objective**: Implement divergence-based trading simulation

**Files to Create/Modify**:
- `webapp/api/endpoints/simulation.py` (update)

**Tasks**:
1. **Task 2.1**: Implement simulation algorithm
   - **Function**: `simulate_trading_strategy(aligned_data, entry_threshold=0.05, exit_threshold=0.01)`
   - **Returns**: `{total_profit, trades, win_rate, avg_profit_per_trade, ...}`
   - **Algorithm**: Divergence Threshold Trading Simulation (Algorithm 1)
   - **Big O**: O(n) where n = aligned data points

2. **Task 2.2**: Calculate profit/loss for each trade
   - **Function**: `calculate_trade_pnl(trade, actual_outcome)`
   - **Returns**: Profit/loss in cents
   - **Algorithm**: Position-based P/L calculation (long vs. short)

3. **Task 2.3**: Aggregate simulation results
   - **Function**: `aggregate_simulation_results(all_trades)`
   - **Returns**: Summary statistics (total profit, win rate, avg profit, etc.)

### Phase 3: Kalshi Calibration Analysis (Duration: 3-4 hours)

**Objective**: Calculate calibration metrics for Kalshi odds (reuse ESPN calibration functions)

**Files to Create/Modify**:
- `webapp/api/endpoints/stats.py` (update) - Add Kalshi calibration endpoint
- `webapp/api/endpoints/aggregate_stats.py` (update) - Add Kalshi calibration to aggregate stats

**Tasks**:
1. **Task 3.1**: Extract Kalshi probabilities for calibration
   - **Function**: `get_kalshi_probabilities_for_calibration(game_id)`
   - **Returns**: (probabilities, timestamps, actual_outcome)
   - **Algorithm**: SQL query + time alignment

2. **Task 3.2**: Calculate Kalshi calibration metrics (reuse existing functions)
   - **Function**: `calculate_kalshi_calibration(game_id)`
   - **Returns**: Same structure as ESPN calibration
   - **Algorithm**: Reuse `calculate_brier_score()`, `calculate_reliability_curve()`, etc.

3. **Task 3.3**: Add Kalshi calibration to aggregate stats
   - **File**: `webapp/api/endpoints/aggregate_stats.py`
   - **Update**: Add Kalshi calibration section (similar to ESPN calibration section)

### Phase 4: Outlier Analysis (Duration: 2-3 hours)

**Objective**: Implement time-based filtering and compare results with/without outliers

**Files to Create/Modify**:
- `webapp/api/endpoints/simulation.py` (update)
- `webapp/api/endpoints/stats.py` (update)

**Tasks**:
1. **Task 4.1**: Add time filtering to data extraction
   - **Function**: `filter_by_time_window(timestamps, game_start, duration, exclude_first, exclude_last)`
   - **Returns**: Filtered indices or filtered data
   - **Algorithm**: Time Window Filtering (Algorithm 2)

2. **Task 4.2**: Run simulation with and without time filtering
   - **Function**: `compare_simulation_with_time_filters(game_id, ...)`
   - **Returns**: Comparison of results (with/without first 5 min, with/without last 5 min)

3. **Task 4.3**: Run calibration analysis with time filtering
   - **Function**: `calculate_calibration_with_time_filter(game_id, exclude_first, exclude_last)`
   - **Returns**: Calibration metrics (compare to unfiltered)

### Phase 5: API Endpoints (Duration: 2-3 hours)

**Objective**: Create REST API endpoints for simulation and calibration analysis

**Files to Create/Modify**:
- `webapp/api/endpoints/simulation.py` (update)
- `webapp/api/main.py` (update) - Register simulation router

**Tasks**:
1. **Task 5.1**: Create simulation endpoint
   - **Endpoint**: `GET /api/games/{game_id}/simulation`
   - **Parameters**: `entry_threshold`, `exit_threshold`, `exclude_first_seconds`, `exclude_last_seconds`
   - **Returns**: Simulation results (profit, trades, win rate, etc.)

2. **Task 5.2**: Create aggregate simulation endpoint
   - **Endpoint**: `GET /api/stats/aggregate/simulation`
   - **Parameters**: `season`, `entry_threshold`, `exit_threshold`, `exclude_first_seconds`, `exclude_last_seconds`
   - **Returns**: Aggregate simulation results across all games

3. **Task 5.3**: Create Kalshi calibration endpoint
   - **Endpoint**: `GET /api/games/{game_id}/stats/kalshi-calibration`
   - **Returns**: Kalshi calibration metrics (Brier, reliability curve, etc.)

### Phase 6: Visualization (Duration: 4-6 hours)

**Objective**: Create visualizations for simulation results and calibration curves

**Files to Create/Modify**:
- `webapp/static/js/simulation.js` (new) - Simulation visualization
- `webapp/static/js/stats.js` (update) - Add Kalshi calibration visualization

**Tasks**:
1. **Task 6.1**: Create simulation results visualization
   - **Chart Types**: Profit distribution, cumulative profit, trade frequency
   - **Library**: Chart.js or D3.js
   - **File**: `webapp/static/js/simulation.js`

2. **Task 6.2**: Create Kalshi calibration curve visualization
   - **Chart Type**: Reliability curve (line chart)
   - **Library**: TradingView Lightweight Charts or D3.js
   - **File**: `webapp/static/js/stats.js` (update)

3. **Task 6.3**: Create comparison visualization (ESPN vs. Kalshi)
   - **Chart Type**: Dual reliability curves
   - **Library**: TradingView Lightweight Charts or D3.js
   - **File**: `webapp/static/js/stats.js` (update)

## Data Flow Diagrams

### Data Flow 1: Simulation Endpoint

```
Client Request
  ↓
GET /api/games/{game_id}/simulation?entry_threshold=0.05&exclude_first_seconds=300
  ↓
simulation.py: get_simulation_results()
  ↓
1. Extract aligned ESPN-Kalshi data (with time filtering)
   - Query: espn.probabilities_raw_items
   - Query: kalshi.candlesticks
   - Align by timestamp (within 60 seconds)
   - Filter: exclude first 5 min, last 5 min
  ↓
2. Get game outcome
   - Query: espn.prob_event_state
  ↓
3. Run simulation algorithm
   - simulate_trading_strategy(aligned_data, entry_threshold=0.05)
   - Returns: {total_profit, trades, win_rate, ...}
  ↓
4. Return JSON response
  ↓
Client receives simulation results
```

### Data Flow 2: Kalshi Calibration Endpoint

```
Client Request
  ↓
GET /api/games/{game_id}/stats/kalshi-calibration
  ↓
stats.py: get_kalshi_calibration()
  ↓
1. Extract Kalshi probabilities
   - Query: kalshi.candlesticks
   - Convert: price_close or mid-price → probability (0-1)
  ↓
2. Get game outcome
   - Query: espn.prob_event_state
  ↓
3. Calculate calibration metrics (reuse existing functions)
   - calculate_brier_score(kalshi_probs, outcome)
   - calculate_reliability_curve(kalshi_probs, outcomes)
   - calculate_time_sliced_brier_scores(...)
  ↓
4. Return JSON response
  ↓
Client receives calibration metrics
```

## Design Decisions

### Design Decision 1: Profit Calculation Method

**Problem Statement**: How to calculate profit/loss for simulated trades using Kalshi bid/ask prices?

**Chosen Solution**: Use actual bid/ask prices for entry, assume contract resolution for exit

**Design Pattern**: Realistic Trading Simulation Pattern  
**Algorithm**: Position-based P/L calculation  
**Big O**: O(1) per trade

**Implementation Details**:
- **Long Position** (buy "Yes" at ask):
  - Entry cost: `yes_ask_close` cents
  - If home wins: Profit = `(100 - yes_ask_close)` cents
  - If home loses: Loss = `yes_ask_close` cents (contract expires worthless)
  
- **Short Position** (sell "Yes" at bid):
  - Entry premium: `yes_bid_close` cents (received)
  - If home wins: Loss = `(100 - yes_bid_close)` cents (must pay 100 or buy back)
  - If home loses: Profit = `yes_bid_close` cents (keep premium, contract expires worthless)

**Pros**:
- Realistic (uses actual market prices)
- Accounts for bid-ask spread
- Handles both winning and losing trades

**Cons**:
- Assumes perfect execution (no slippage)
- Does not account for transaction costs (if Kalshi charges fees)
- May not account for early exit (assumes holding until convergence or game end)

**Rejected Alternatives**:
- **Mid-price only**: Too optimistic (ignores bid-ask spread)
- **Fixed spread**: Not realistic (spread varies)

### Design Decision 2: Convergence Exit Threshold

**Problem Statement**: When to exit a position? What constitutes "convergence"?

**Chosen Solution**: Exit when absolute divergence falls below exit threshold (e.g., 0.01 = 1 cent)

**Design Pattern**: Threshold-based Exit Pattern  
**Algorithm**: Simple threshold comparison  
**Big O**: O(1) per data point

**Implementation Details**:
- **Entry Threshold**: 0.05 (5 cents) - divergence must exceed this to enter
- **Exit Threshold**: 0.01 (1 cent) - divergence must fall below this to exit
- **Hysteresis**: Prevents rapid entry/exit cycles (entry threshold > exit threshold)

**Pros**:
- Simple to implement
- Prevents whipsaw (rapid entry/exit)
- Configurable (can adjust thresholds)

**Cons**:
- May miss optimal exit timing
- May hold position until game end if divergence never converges
- Does not account for time value (holding period)

**Rejected Alternatives**:
- **Percentage-based threshold**: Less intuitive (5% of what?)
- **Time-based exit**: Does not capture convergence
- **Profit target**: May exit too early or too late

### Design Decision 3: Time Filtering Strategy

**Problem Statement**: How to exclude first/last 5 minutes for outlier analysis?

**Chosen Solution**: Filter data points by game-relative time (exclude first 300 seconds, last 300 seconds)

**Design Pattern**: Filter Pattern  
**Algorithm**: Time Window Filtering (Algorithm 2)  
**Big O**: O(n) where n = data points

**Implementation Details**:
- **Exclude First**: 300 seconds (5 minutes) from game start
- **Exclude Last**: 300 seconds (5 minutes) before game end
- **Apply to**: Both ESPN and Kalshi data before alignment
- **Re-align**: After filtering, re-align filtered datasets

**Pros**:
- Simple to implement
- Allows sensitivity analysis (how do results change?)
- Identifies if outliers drive results

**Cons**:
- Reduces sample size
- May miss important early/late game dynamics
- Requires game duration calculation (may be inaccurate for some games)

**Rejected Alternatives**:
- **Percentage-based filtering**: Less intuitive (what % of game?)
- **Event-based filtering**: Complex (what events to exclude?)
- **Statistical outlier detection**: May exclude valid data points

## Success Metrics

### Simulation Metrics
- **Total Profit**: Sum of all trade profits/losses (in cents or dollars)
- **Win Rate**: Percentage of profitable trades
- **Average Profit per Trade**: Mean profit/loss across all trades
- **Sharpe Ratio**: Risk-adjusted return (if multiple games)
- **Max Drawdown**: Largest peak-to-trough decline in cumulative profit

### Calibration Metrics
- **Brier Score**: Mean squared error (lower is better, 0 = perfect)
- **Log Loss**: Logarithmic loss (lower is better)
- **Reliability Curve**: Calibration across probability bins
- **Calibration Error**: Average `predicted_prob - actual_freq` per bin

### Robustness Metrics
- **Sensitivity to Time Filtering**: How much do results change when excluding first/last 5 minutes?
- **Sample Size Impact**: How many data points remain after filtering?

## Risk Assessment

### Risk 1: Data Alignment Issues

**Probability**: Medium  
**Impact**: High (incorrect divergence calculation)

**Mitigation**:
- Use existing time alignment logic (proven in `probabilities.py`)
- Validate alignment (check timestamp differences)
- Handle missing data gracefully

**Contingency**: Fall back to simpler alignment (exact timestamp match only)

### Risk 2: Bid-Ask Spread Impact

**Probability**: High  
**Impact**: Medium (reduces profitability)

**Mitigation**:
- Track spread separately in results
- Report spread impact on profitability
- Consider mid-price simulation as alternative

**Contingency**: Use mid-price for optimistic scenario, bid/ask for realistic scenario

### Risk 3: Simulation Assumptions

**Probability**: Medium  
**Impact**: Medium (results may not reflect real trading)

**Mitigation**:
- Document all assumptions clearly
- Provide sensitivity analysis (vary thresholds)
- Compare to actual market behavior (if data available)

**Contingency**: Add more realistic constraints (transaction costs, slippage, position limits)

### Risk 4: Sample Size Reduction from Time Filtering

**Probability**: Medium  
**Impact**: Low-Medium (fewer data points, less statistical power)

**Mitigation**:
- Report sample size before/after filtering
- Use aggregate analysis across many games
- Consider shorter exclusion windows (e.g., 2 minutes instead of 5)

**Contingency**: Reduce exclusion window or skip filtering for some analyses

## Post-Implementation Artifacts

### Documentation
- `cursor-files/analysis/betting_odds_simulation_analysis_v1.md` - This document
- API documentation for simulation endpoints
- Visualization documentation

### Code
- `webapp/api/endpoints/simulation.py` - Simulation endpoint
- `webapp/api/endpoints/stats.py` - Updated with Kalshi calibration
- `webapp/api/endpoints/aggregate_stats.py` - Updated with Kalshi calibration
- `webapp/static/js/simulation.js` - Simulation visualization
- `webapp/static/js/stats.js` - Updated with Kalshi calibration visualization

### Testing
- Unit tests for simulation algorithm
- Integration tests for endpoints
- Validation scripts for profit calculation

## Notes

- **Betting Odds Definition**: Kalshi `price_close` or mid-price (`(yes_bid_close + yes_ask_close) / 2`) represents the market's implied probability
- **Simulation Scope**: This analysis focuses on historical backtesting, not live trading
- **Transaction Costs**: Kalshi may charge fees - not accounted for in initial simulation (can be added later)
- **Position Sizing**: Simulation assumes fixed position size (1 contract) - can be extended to variable sizing
- **Multiple Games**: Aggregate simulation across all games to get overall profitability

---

## Document Validation

This analysis follows the standards in `ANALYSIS_STANDARDS.md` and provides:
- Evidence-based analysis with code references
- Design pattern and algorithm analysis with Big O notation
- Pros/cons for each design decision
- Comprehensive risk assessment
- Detailed implementation plan with phases and tasks
- Data source identification and data flow diagrams
- Visualization requirements and specifications

