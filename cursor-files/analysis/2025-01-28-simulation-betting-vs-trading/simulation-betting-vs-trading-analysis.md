# Critical Analysis: Betting vs Trading Simulation

**Date**: December 28, 2025  
**Issue**: The current simulation incorrectly models binary betting P&L instead of realistic trading P&L  
**Severity**: **CRITICAL** - Invalidates all performance metrics and risk analysis  
**Impact**: Results are misleading and cannot be used for real trading decisions

---

## Executive Summary

The current simulation has a **fundamental conceptual flaw**: it calculates profit/loss based on the final game outcome (home team won/lost) rather than the entry/exit price difference. This makes it a **betting simulator**, not a **trading simulator**.

**Key Problem**: A trade that exits at a profit (e.g., buy at $0.60, exit at $0.70) should show profit regardless of whether the home team ultimately wins or loses. The current implementation ignores exit prices and only considers final outcome.

**Consequence**: All performance metrics (Sharpe ratio, ROI, max drawdown, etc.) are **meaningless** because they reflect betting performance, not trading performance. The simulation cannot be used to evaluate real trading strategies.

---

## 1. Why the Current Simulator is Betting, Not Trading

### 1.1 Current P&L Calculation Logic

**Current Implementation** (`calculate_trade_pnl()`):

```python
if trade.position_type == "long_espn":
    entry_price_dollars = trade.entry_kalshi_ask  # e.g., $0.60
    num_contracts = bet_amount_dollars / entry_price_dollars
    entry_cost = bet_amount_dollars  # $20
    
    if actual_outcome == 1:  # Home won
        payout = num_contracts * 1.0  # $33.33
        profit = payout - entry_cost  # $13.33
    else:  # Home lost
        profit = -entry_cost  # -$20.00 (LOSS)
```

**What's Wrong**:
- **Ignores exit price**: The function receives `exit_kalshi_price` but **never uses it**
- **Only considers final outcome**: Profit is determined solely by `actual_outcome` (1 = home won, 0 = home lost)
- **No price movement consideration**: A trade that exits at $0.70 (profit) but home team loses still shows a loss

### 1.2 Example: Why This is Wrong

**Scenario**: 
- Entry: Buy "Yes" contracts at $0.60 (ESPN says 70%, Kalshi says 60%)
- Exit: Divergence converges, exit at $0.70 (ESPN and Kalshi both at 70%)
- Final Outcome: Home team loses

**Current (WRONG) Calculation**:
```
Entry: $0.60, Exit: $0.70 (ignored!)
Final: Home lost → Profit = -$20.00 (LOSS)
```

**Correct Trading Calculation**:
```
Entry: $0.60, Exit: $0.70
Price movement: +$0.10 per contract
Contracts: $20 / $0.60 = 33.33 contracts
Profit: 33.33 × $0.10 = +$3.33 (PROFIT)
```

**The Problem**: In real trading, you **close your position** at the exit price. Whether the home team ultimately wins or loses is **irrelevant** because you're no longer holding the position.

### 1.3 Hindsight Bias Introduction

**Current Model**:
- Trades that exit before game ends still depend on final outcome
- This introduces **hindsight bias**: We know the final outcome when calculating P&L
- In reality, traders don't know the outcome when they exit

**Example**:
- Trade exits at minute 30 of a 48-minute game
- Current model: Wait until game ends, check final score, calculate P&L
- Real trading: Calculate P&L immediately at exit based on exit price

**Impact**: This makes the simulation **unrealistic** and **unusable** for evaluating trading strategies.

### 1.4 Risk Characteristics Distortion

**Current Model Risk Profile**:
- **Max Loss**: Limited to bet amount (e.g., -$20 per trade)
- **Max Win**: Unlimited (can be 2-5× bet amount if home wins)
- **Risk/Reward**: Asymmetric, favors winning outcomes

**Real Trading Risk Profile**:
- **Max Loss**: Based on price movement, not outcome
- **Max Win**: Based on price movement, not outcome
- **Risk/Reward**: Symmetric (depends on entry/exit prices)

**Why This Matters**: The current model **understates risk** because losses are capped at bet amount, while wins can be multiples of bet amount. Real trading doesn't work this way.

---

## 2. Correct Conceptual Model for Trading Simulator

### 2.1 Fundamental Principle

**Trading P&L = (Exit Price - Entry Price) × Position Size × Direction**

**NOT**: Trading P&L = Final Outcome × Position Size

**Key Insight**: In trading, you **close your position** at the exit price. The final game outcome is **irrelevant** because you're no longer holding the contract.

### 2.2 Long Position P&L (Correct Model)

**Entry**: Buy contracts at ask price (e.g., $0.60)  
**Exit**: Sell contracts at bid price (e.g., $0.70)  
**P&L**: Based on price difference, not final outcome

**Formula**:
```
Entry Price: entry_kalshi_ask (e.g., $0.60)
Exit Price: exit_kalshi_bid (e.g., $0.70)
Price Movement: exit_price - entry_price = +$0.10

Position Size: bet_amount / entry_price = $20 / $0.60 = 33.33 contracts
Profit: position_size × price_movement = 33.33 × $0.10 = +$3.33
```

**Key Points**:
- **Entry**: Buy at ask (higher price)
- **Exit**: Sell at bid (lower price)
- **P&L**: Based on bid-ask spread and price movement
- **Final Outcome**: **NOT USED** (position is closed)

### 2.3 Short Position P&L (Correct Model)

**Entry**: Sell contracts at bid price (e.g., $0.80)  
**Exit**: Buy back contracts at ask price (e.g., $0.65)  
**P&L**: Based on price difference, not final outcome

**Formula**:
```
Entry Price: entry_kalshi_bid (e.g., $0.80)
Exit Price: exit_kalshi_ask (e.g., $0.65)
Price Movement: entry_price - exit_price = +$0.15 (profit when price falls)

Position Size: bet_amount / (1 - entry_price) = $20 / (1 - $0.80) = 100 contracts
Premium Received: position_size × entry_price = 100 × $0.80 = $80.00
Cost to Close: position_size × exit_price = 100 × $0.65 = $65.00
Profit: premium_received - cost_to_close = $80.00 - $65.00 = +$15.00
```

**Key Points**:
- **Entry**: Sell at bid (lower price)
- **Exit**: Buy at ask (higher price)
- **P&L**: Based on price movement (profit when price falls)
- **Final Outcome**: **NOT USED** (position is closed)

### 2.4 Binary Settlement is Irrelevant

**Current (WRONG) Model**:
- Contracts settle at $1.00 if home wins, $0.00 if home loses
- P&L calculated based on settlement

**Correct Trading Model**:
- Contracts are **closed** at exit price (bid/ask)
- Settlement only matters if you **hold until expiration**
- Since we exit before game ends, settlement is **irrelevant**

**Example**:
- Trade: Buy at $0.60, exit at $0.70
- Current model: Wait for game to end, check if home won
- Correct model: Calculate P&L immediately: ($0.70 - $0.60) × contracts = profit

---

## 3. Exact Conceptual Changes Required

### 3.1 Contract Sizing

**Current (WRONG)**:
```python
# Long: Buy enough contracts to risk bet_amount
num_contracts = bet_amount / entry_price
entry_cost = bet_amount  # Fixed cost
```

**Correct Trading Model**:
```python
# Long: Buy contracts at entry price, sell at exit price
entry_price = entry_kalshi_ask  # Buy at ask
exit_price = exit_kalshi_bid    # Sell at bid
num_contracts = bet_amount / entry_price
entry_cost = num_contracts × entry_price  # Actual cost
exit_proceeds = num_contracts × exit_price  # Actual proceeds
profit = exit_proceeds - entry_cost
```

**Key Change**: Use **actual entry/exit prices** (bid/ask), not fixed bet amount.

### 3.2 Long Position P&L Calculation

**Current (WRONG)**:
```python
if actual_outcome == 1:  # Home won
    payout = num_contracts * 1.0
    profit = payout - entry_cost
else:  # Home lost
    profit = -entry_cost
```

**Correct**:
```python
# P&L based on price movement, not outcome
entry_price = trade.entry_kalshi_ask  # Buy at ask
exit_price = trade.exit_kalshi_bid    # Sell at bid
price_movement = exit_price - entry_price

num_contracts = bet_amount / entry_price
profit = num_contracts × price_movement

# No reference to actual_outcome!
```

**Key Change**: Remove all `actual_outcome` logic. P&L is purely price-based.

### 3.3 Short Position P&L Calculation

**Current (WRONG)**:
```python
if actual_outcome == 1:  # Home won
    payout_owed = num_contracts * 1.0
    profit = entry_premium - payout_owed
else:  # Home lost
    profit = entry_premium
```

**Correct**:
```python
# P&L based on price movement, not outcome
entry_price = trade.entry_kalshi_bid  # Sell at bid
exit_price = trade.exit_kalshi_ask    # Buy at ask
price_movement = entry_price - exit_price  # Profit when price falls

num_contracts = bet_amount / (1 - entry_price)
entry_premium = num_contracts × entry_price  # Premium received
exit_cost = num_contracts × exit_price      # Cost to close
profit = entry_premium - exit_cost

# No reference to actual_outcome!
```

**Key Change**: Calculate P&L from entry premium minus exit cost, not settlement.

### 3.4 Max Win / Max Loss Behavior

**Current (WRONG) Behavior**:
- **Max Loss**: Capped at bet amount (e.g., -$20)
- **Max Win**: Can be 2-5× bet amount (e.g., +$100 if home wins at low entry price)
- **Asymmetric**: Favors winning outcomes

**Correct Trading Behavior**:
- **Max Loss**: Based on worst price movement (e.g., buy at $0.60, exit at $0.40 = -$0.20 per contract)
- **Max Win**: Based on best price movement (e.g., buy at $0.60, exit at $0.80 = +$0.20 per contract)
- **Symmetric**: Depends on price volatility, not outcome

**Example**:
- Current: Max loss = -$20 (fixed), Max win = +$100 (if home wins)
- Correct: Max loss = -$6.67 (buy $0.60, exit $0.40), Max win = +$6.67 (buy $0.60, exit $0.80)

**Key Change**: Max win/loss should reflect **price movement extremes**, not outcome extremes.

### 3.5 End-of-Game Position Handling

**Current (WRONG)**:
- If position still open at game end, close using final outcome
- P&L calculated based on settlement ($1.00 if home won, $0.00 if home lost)

**Correct**:
- If position still open at game end, close using **final market price** (not settlement)
- Use last available bid/ask price before market closes
- P&L calculated based on entry price vs final market price

**Key Change**: Use **market price** at game end, not binary settlement.

---

## 4. Fees, Spreads, and Slippage Application

### 4.1 Why They Must Be Applied Per Trade

**Current Problem**: Fees, spreads, and slippage are **completely ignored**. This makes the simulation **unrealistic** and **overstates profitability**.

**Why It Matters**:
- **Fees**: 0.6-1.8% per trade (entry + exit) = $0.12-$0.36 per $20 trade
- **Bid-Ask Spread**: 0.1-1.0% = $0.02-$0.20 per $20 trade
- **Slippage**: 0.2-1.0% = $0.04-$0.20 per $20 trade
- **Total Cost**: $0.18-$0.76 per trade (0.9-3.8% of bet amount)

**Impact**: For a trade with $2.00 gross profit, costs consume **9-38%** of profit. Ignoring them makes results **meaningless**.

### 4.2 How to Apply Costs Per Trade

**Entry Costs** (apply when entering position):
```
Entry Fee = 7% × (entry_price × (1 - entry_price)) × bet_amount
Entry Spread Cost = (ask_price - bid_price) / 2 × position_size  # If using mid-price
Entry Slippage = slippage_rate × bet_amount
Total Entry Cost = Entry Fee + Entry Spread Cost + Entry Slippage
```

**Exit Costs** (apply when exiting position):
```
Exit Fee = 7% × (exit_price × (1 - exit_price)) × bet_amount
Exit Spread Cost = (ask_price - bid_price) / 2 × position_size
Exit Slippage = slippage_rate × bet_amount
Total Exit Cost = Exit Fee + Exit Spread Cost + Exit Slippage
```

**Net Profit**:
```
Gross Profit = (Exit Price - Entry Price) × Position Size × Direction
Net Profit = Gross Profit - Total Entry Cost - Total Exit Cost
```

### 4.3 Why Ignoring Costs Invalidates Results

**Example Trade**:
- Entry: Buy at $0.60, Exit: Sell at $0.70
- Gross Profit: $3.33 (10 cent movement × 33.33 contracts)
- Costs: $0.63 (fees) + $0.20 (spread) + $0.10 (slippage) = $0.93
- **Net Profit**: $3.33 - $0.93 = **$2.40** (28% reduction)

**Current Model**:
- Shows $3.33 profit (ignores costs)
- **Overstates profitability by 28%**

**Impact on Metrics**:
- **ROI**: Overstated by 15-25%
- **Sharpe Ratio**: Overstated (higher returns, same volatility)
- **Win Rate**: Overstated (marginal winners become losers after costs)
- **Max Drawdown**: Understated (costs increase losses)

**Conclusion**: **All metrics are invalid** until costs are included.

---

## 5. Performance Metrics: Meaningful Only After Fix

### 5.1 Sharpe Ratio

**Current (MISLEADING)**:
- Calculated using outcome-based returns
- Reflects betting performance, not trading performance
- **Meaningless** because returns don't reflect price movements

**After Fix (MEANINGFUL)**:
- Calculated using price-based returns
- Reflects actual trading performance
- Measures risk-adjusted returns from price movements
- **Only meaningful** when P&L is based on entry/exit prices

**Why Current is Wrong**:
- Sharpe ratio assumes returns come from price movements
- Current model: Returns come from binary outcomes
- This violates the fundamental assumption of Sharpe ratio

### 5.2 Maximum Drawdown

**Current (MISLEADING)**:
- Based on outcome-based P&L
- Understates risk (losses capped at bet amount)
- Doesn't reflect actual trading risk

**After Fix (MEANINGFUL)**:
- Based on price-based P&L
- Reflects actual trading risk (unlimited loss potential)
- Shows true worst-case scenario
- **Only meaningful** when losses reflect price movements

**Why Current is Wrong**:
- Drawdown measures peak-to-trough decline in equity
- Current model: Equity curve is artificial (based on outcomes)
- Real trading: Drawdown reflects price volatility, not outcome probability

### 5.3 ROI (Return on Investment)

**Current (MISLEADING)**:
- Calculated as: (Total Profit / Total Capital) × 100%
- Profit based on outcomes, not price movements
- **Overstated** because it ignores costs and uses wrong P&L

**After Fix (MEANINGFUL)**:
- Calculated as: (Net Profit / Total Capital) × 100%
- Profit based on price movements minus costs
- Reflects actual trading returns
- **Only meaningful** when:
  1. P&L is price-based (not outcome-based)
  2. Costs are included (fees, spreads, slippage)

**Why Current is Wrong**:
- ROI assumes you're trading (buying/selling at prices)
- Current model: You're betting (settling at outcomes)
- These are fundamentally different activities

### 5.4 Win Rate

**Current (MISLEADING)**:
- Based on outcome-based P&L
- Doesn't reflect trading skill (price prediction)
- Reflects betting skill (outcome prediction)

**After Fix (MEANINGFUL)**:
- Based on price-based P&L
- Reflects trading skill (ability to profit from price movements)
- **Only meaningful** when:
  1. P&L is price-based
  2. Costs are included (marginal winners become losers)

**Why Current is Wrong**:
- Win rate measures frequency of profitable trades
- Current model: Trades are profitable based on outcomes, not prices
- Real trading: Win rate measures ability to exit at profit

### 5.5 Expectancy (EV per Trade)

**Current (MISLEADING)**:
- Based on outcome-based P&L
- Doesn't reflect trading edge (price prediction ability)
- Reflects betting edge (outcome prediction ability)

**After Fix (MEANINGFUL)**:
- Based on price-based P&L
- Reflects actual trading edge
- **Only meaningful** when P&L is price-based

**Why Current is Wrong**:
- Expectancy measures expected value per trade
- Current model: Value comes from outcomes, not price movements
- Real trading: Expectancy comes from ability to profit from price movements

### 5.6 Profit Factor

**Current (MISLEADING)**:
- Gross Profits / Gross Losses based on outcomes
- Doesn't reflect trading performance
- **Overstated** (ignores costs, uses wrong P&L)

**After Fix (MEANINGFUL)**:
- Gross Profits / Gross Losses based on price movements
- Reflects actual trading performance
- **Only meaningful** when:
  1. P&L is price-based
  2. Costs are included

**Why Current is Wrong**:
- Profit factor measures risk/reward ratio
- Current model: Risk/reward is artificial (based on outcomes)
- Real trading: Risk/reward reflects price volatility

---

## 6. Risk Interpretation: Why Current Model is Dangerous

### 6.1 Understated Risk

**Current Model**:
- Max loss per trade: -$20 (fixed)
- Risk is **capped** and **predictable**
- Doesn't reflect real trading risk

**Real Trading**:
- Max loss per trade: Based on price movement (unlimited in theory)
- Risk is **uncapped** and **volatile**
- Reflects actual market risk

**Danger**: Using current model for risk management would **underestimate** actual risk, leading to:
- Over-leveraging
- Insufficient capital reserves
- Unexpected losses in live trading

### 6.2 Asymmetric Risk/Reward

**Current Model**:
- Losses: Capped at -$20
- Wins: Can be 2-5× bet amount
- **Asymmetric**: Favors winning outcomes

**Real Trading**:
- Losses: Based on price movement (can exceed entry cost)
- Wins: Based on price movement (limited by price range)
- **Symmetric**: Depends on price volatility

**Danger**: Current model suggests **favorable risk/reward** that doesn't exist in real trading.

### 6.3 Hindsight Bias

**Current Model**:
- P&L calculated after knowing final outcome
- Introduces **hindsight bias**
- Makes strategy appear better than it is

**Real Trading**:
- P&L calculated at exit (before knowing outcome)
- No hindsight bias
- Reflects actual trading performance

**Danger**: Current model **overstates** strategy performance because it uses information (final outcome) that wasn't available at exit time.

---

## 7. Summary: What Must Change

### 7.1 Core Conceptual Changes

1. **P&L Calculation**: 
   - ❌ Remove: Outcome-based P&L (`actual_outcome`)
   - ✅ Add: Price-based P&L (`exit_price - entry_price`)

2. **Contract Sizing**:
   - ❌ Remove: Fixed bet amount logic
   - ✅ Add: Position size based on entry/exit prices

3. **Exit Handling**:
   - ❌ Remove: Settlement-based exit (wait for game end)
   - ✅ Add: Market-price-based exit (use bid/ask at exit time)

4. **End-of-Game Positions**:
   - ❌ Remove: Binary settlement ($1.00 or $0.00)
   - ✅ Add: Final market price (last bid/ask before close)

### 7.2 Cost Integration

1. **Fees**: Apply 7% fee formula at entry AND exit
2. **Bid-Ask Spread**: Use actual bid/ask prices (not mid-price)
3. **Slippage**: Estimate and subtract per trade
4. **Net P&L**: Gross profit minus all costs

### 7.3 Metric Validity

**Invalid Until Fixed**:
- Sharpe Ratio
- Maximum Drawdown
- ROI
- Win Rate
- Expectancy
- Profit Factor
- All risk metrics

**Why**: They're calculated using outcome-based P&L, which doesn't reflect trading performance.

**Valid After Fix**:
- All metrics become meaningful when:
  1. P&L is price-based (not outcome-based)
  2. Costs are included (fees, spreads, slippage)

---

## 8. Conclusion

### 8.1 The Fundamental Problem

The current simulation is **not a trading simulator**—it's a **betting simulator**. It calculates P&L based on final game outcomes rather than entry/exit price movements. This makes it **unusable** for evaluating real trading strategies.

### 8.2 Why This Matters

**For Strategy Evaluation**:
- Current metrics are **meaningless** for trading
- Cannot assess real trading performance
- Cannot evaluate risk accurately

**For Real Trading**:
- Using current model would lead to **incorrect** risk assessment
- Would **overstate** profitability
- Would **understate** risk

**For Decision Making**:
- Cannot make informed decisions about strategy viability
- Cannot assess whether strategy is profitable after costs
- Cannot evaluate risk-adjusted returns

### 8.3 What Must Happen

**Before Any Further Analysis**:
1. **Fix P&L calculation**: Use entry/exit prices, not outcomes
2. **Add costs**: Include fees, spreads, slippage
3. **Recalculate all metrics**: Using corrected P&L
4. **Re-evaluate strategy**: Based on realistic trading performance

**Until These Changes Are Made**:
- **Do not** use current results for trading decisions
- **Do not** trust current performance metrics
- **Do not** assume strategy is profitable

### 8.4 Final Assessment

The current simulation is **fundamentally broken** from a trading perspective. It models betting, not trading. All results are **invalid** for trading strategy evaluation until the core P&L calculation is fixed and costs are included.

**Recommendation**: **Fix immediately** before any further analysis or strategy evaluation. The current model is misleading and dangerous if used for real trading decisions.

---

**End of Analysis**

