# Trading Costs Analysis: Incorporating Fees, Slippage, and Spreads into Kalshi-ESPN Backtest

**Date**: December 28, 2025  
**Purpose**: Analyze how to incorporate real-world trading costs (fees, slippage, bid-ask spreads) into the ESPN-Kalshi divergence trading simulation to produce realistic profitability estimates.

---

## Executive Summary

The current simulation assumes zero execution costs, which significantly overstates profitability. This analysis provides:

1. **Kalshi Fee Structure**: How fees are calculated (approximately 7% of potential upside × probability)
2. **Slippage Estimation**: Methods to estimate execution slippage in low-liquidity prediction markets
3. **Bid-Ask Spread Analysis**: How to account for the cost of trading at bid vs ask prices
4. **Simulation Adjustments**: Conceptual framework for subtracting costs from each trade
5. **Metric Recalculation**: How to adjust Sharpe ratio, ROI, max win/loss with costs included
6. **Diagnostic Statistics**: Key metrics to evaluate real-world strategy viability

**Key Finding**: Trading costs can easily consume 10-30% of gross profits in prediction markets, especially for high-frequency strategies with many small trades.

---

## 1. Kalshi Fee Structure

### 1.1 Current Fee Model

Based on research, Kalshi charges fees calculated as:

**Fee Formula**:
```
Fee = 7% × (Contract Price × (1 - Contract Price))
```

Or alternatively described as:
```
Fee = 7% × (Potential Upside × Market Probability)
```

### 1.2 Fee Characteristics

**Fee Structure Table**:

| Contract Price | Fee Rate | Example Fee (on $20 bet) | Notes |
|----------------|----------|-------------------------|-------|
| $0.10 (10%) | ~0.63% | $0.13 | Low probability, low fee |
| $0.25 (25%) | ~1.31% | $0.26 | Moderate probability |
| **$0.50 (50%)** | **~1.75%** | **$0.35** | **Maximum fee (peak)** |
| $0.75 (75%) | ~1.31% | $0.26 | High probability |
| $0.90 (90%) | ~0.63% | $0.13 | Very high probability, low fee |

**Key Observations**:
- Fees are **highest at 50/50 odds** (around $0.50 contract price)
- Fees **decrease symmetrically** as prices approach $0.00 or $1.00
- Fee structure is **non-linear** and **probability-dependent**

### 1.3 Maker vs Taker Fees

**Current Status**: Research indicates Kalshi may not have separate maker/taker fee structures like traditional exchanges. The 7% fee appears to apply uniformly to all trades.

**Implication**: No fee advantage from providing liquidity (market making) vs taking liquidity (market taking).

### 1.4 Fee Calculation Examples

**Example 1: Long Position (Buying "Yes" contract)**
- Entry: Buy contract at $0.60 (60% implied probability)
- Fee on entry: 7% × ($0.60 × $0.40) = 7% × $0.24 = **$0.0168 per $1 contract**
- On $20 bet: $20 × $0.0168 = **$0.336 entry fee**
- Exit: Sell contract at $0.70 (if probability increases)
- Fee on exit: 7% × ($0.70 × $0.30) = 7% × $0.21 = **$0.0147 per $1 contract**
- On $20 bet: $20 × $0.0147 = **$0.294 exit fee**
- **Total fees: $0.336 + $0.294 = $0.63 per trade**

**Example 2: Short Position (Selling "Yes" contract)**
- Entry: Sell contract at $0.80 (80% implied probability)
- Fee on entry: 7% × ($0.80 × $0.20) = 7% × $0.16 = **$0.0112 per $1 contract**
- On $20 bet: $20 × $0.0112 = **$0.224 entry fee**
- Exit: Buy back contract at $0.65 (if probability decreases)
- Fee on exit: 7% × ($0.65 × $0.35) = 7% × $0.2275 = **$0.0159 per $1 contract**
- On $20 bet: $20 × $0.0159 = **$0.318 exit fee**
- **Total fees: $0.224 + $0.318 = $0.542 per trade**

**Key Insight**: Fees vary based on the contract price at entry AND exit, making them dynamic and position-dependent.

---

## 2. Bid-Ask Spread Estimation

### 2.1 Understanding Spreads in Prediction Markets

**Bid-Ask Spread** = Ask Price - Bid Price

This represents the cost of "round-trip" trading (buying at ask, selling at bid).

### 2.2 Current Data Availability

The simulation currently has access to:
- `yes_bid_close`: Best bid price
- `yes_ask_close`: Best ask price
- `price_close`: Mid-price or last trade price

**Problem**: The simulation may be using `price_close` (mid-price) instead of actual execution prices (bid/ask).

### 2.3 Typical Spread Magnitudes

**Spread Estimation Table**:

| Market Condition | Typical Spread | Example (50% contract) | Cost per $20 Trade |
|------------------|----------------|------------------------|---------------------|
| **High Liquidity** | 0.1-0.5% | $0.50 bid, $0.505 ask | $0.01 - $0.05 |
| **Medium Liquidity** | 0.5-1.0% | $0.50 bid, $0.505 ask | $0.10 - $0.20 |
| **Low Liquidity** | 1.0-3.0% | $0.50 bid, $0.515 ask | $0.20 - $0.60 |
| **Very Low Liquidity** | 3.0-5.0%+ | $0.50 bid, $0.525 ask | $0.60 - $1.00+ |

**Factors Affecting Spreads**:
1. **Time to Event**: Spreads widen as game approaches (uncertainty increases)
2. **Market Size**: Larger markets (popular games) have tighter spreads
3. **Volatility**: Rapid probability changes widen spreads temporarily
4. **Time of Day**: Off-hours trading has wider spreads

### 2.4 Spread Calculation Method

**For Long Positions**:
- Entry cost: Buy at **ask price** (higher)
- Exit cost: Sell at **bid price** (lower)
- Spread cost = (Ask_entry - Bid_exit) - (Mid_entry - Mid_exit)

**For Short Positions**:
- Entry cost: Sell at **bid price** (lower)
- Exit cost: Buy at **ask price** (higher)
- Spread cost = (Ask_exit - Bid_entry) - (Mid_exit - Mid_entry)

**Example**:
- Long entry: Buy at $0.605 (ask), mid-price $0.600
- Long exit: Sell at $0.595 (bid), mid-price $0.600
- Spread cost: ($0.605 - $0.595) = **$0.01 per contract** = **$0.20 on $20 bet**

---

## 3. Slippage Estimation

### 3.1 What is Slippage?

**Slippage** = Difference between expected execution price and actual execution price.

Causes:
- **Market Impact**: Your trade moves the market price
- **Latency**: Price changes between decision and execution
- **Order Size**: Large orders can't all execute at best bid/ask
- **Liquidity**: Thin order books cause price movement

### 3.2 Slippage in Prediction Markets

**Key Differences from Stock Markets**:
- Prediction markets have **discrete outcomes** (binary: win/lose)
- **Lower liquidity** than major stock exchanges
- **Time-sensitive**: Markets close at event completion
- **Retail-focused**: Smaller average trade sizes

### 3.3 Slippage Estimation Methods

#### Method 1: Historical Spread Analysis
```
Slippage = (Historical Average Spread) × Slippage Multiplier
```
- **Conservative**: 0.5× spread (assumes good execution)
- **Realistic**: 1.0× spread (assumes mid-spread execution)
- **Pessimistic**: 1.5× spread (assumes poor execution or market impact)

#### Method 2: Volume-Weighted Analysis
```
Slippage = Base Slippage × (1 + Volume_Penalty)
Volume_Penalty = max(0, (Trade_Size - Average_Volume) / Average_Volume)
```
- If trading $20 and average volume is $100: minimal penalty
- If trading $20 and average volume is $5: significant penalty

#### Method 3: Time-Based Slippage
```
Slippage = Base Slippage × Time_Multiplier
Time_Multiplier increases as game approaches (e.g., 1.0 → 1.5 → 2.0)
```

### 3.4 Typical Slippage Magnitudes

**Slippage Estimation Table**:

| Trade Size | Market Liquidity | Typical Slippage | Example (50% contract) |
|------------|------------------|------------------|------------------------|
| Small ($10-20) | High | 0.1-0.3% | $0.02 - $0.06 per trade |
| Small ($10-20) | Medium | 0.3-0.8% | $0.06 - $0.16 per trade |
| Small ($10-20) | Low | 0.8-2.0% | $0.16 - $0.40 per trade |
| Medium ($50-100) | High | 0.3-0.8% | $0.15 - $0.40 per trade |
| Medium ($50-100) | Low | 1.0-3.0% | $0.50 - $1.50 per trade |

**Conservative Estimate for $20 Trades**:
- **High liquidity**: 0.2% = $0.04 per trade
- **Medium liquidity**: 0.5% = $0.10 per trade
- **Low liquidity**: 1.0% = $0.20 per trade

---

## 4. Simulation Adjustment Framework

### 4.1 Current Profit Calculation

**Current Method** (simplified):
```
Gross Profit = (Exit Price - Entry Price) × Position Size × Direction
```

Where:
- Long: Profit if exit > entry
- Short: Profit if exit < entry

### 4.2 Adjusted Profit Calculation

**New Method** (with costs):
```
Net Profit = Gross Profit - Entry Fee - Exit Fee - Spread Cost - Slippage Cost
```

**Step-by-Step Adjustment**:

1. **Calculate Gross Profit** (current method)
   ```
   Gross Profit = (Exit_Price - Entry_Price) × Bet_Amount × Direction_Multiplier
   ```

2. **Calculate Entry Fee**
   ```
   Entry_Fee = 7% × (Entry_Price × (1 - Entry_Price)) × Bet_Amount
   ```

3. **Calculate Exit Fee**
   ```
   Exit_Fee = 7% × (Exit_Price × (1 - Exit_Price)) × Bet_Amount
   ```

4. **Calculate Spread Cost**
   ```
   If Long:
     Spread_Cost = (Ask_Entry - Bid_Exit) - (Mid_Entry - Mid_Exit)
   If Short:
     Spread_Cost = (Ask_Exit - Bid_Entry) - (Mid_Exit - Mid_Entry)
   Spread_Cost = Spread_Cost × Bet_Amount
   ```

5. **Estimate Slippage Cost**
   ```
   Slippage_Cost = Slippage_Rate × Bet_Amount
   Where Slippage_Rate = 0.2% to 1.0% (depending on liquidity)
   ```

6. **Calculate Net Profit**
   ```
   Net_Profit = Gross_Profit - Entry_Fee - Exit_Fee - Spread_Cost - Slippage_Cost
   ```

### 4.3 Example: Full Cost Calculation

**Scenario**: Long position, $20 bet
- Entry: Buy at $0.60 (mid), ask = $0.605, bid = $0.595
- Exit: Sell at $0.70 (mid), ask = $0.705, bid = $0.695
- Market liquidity: Medium

**Calculations**:

1. **Gross Profit**: ($0.70 - $0.60) × $20 = **$2.00**

2. **Entry Fee**: 7% × ($0.60 × $0.40) × $20 = 7% × $0.24 × $20 = **$0.336**

3. **Exit Fee**: 7% × ($0.70 × $0.30) × $20 = 7% × $0.21 × $20 = **$0.294**

4. **Spread Cost**: ($0.605 - $0.695) - ($0.60 - $0.70) = (-$0.09) - (-$0.10) = **$0.01** × $20 = **$0.20**

5. **Slippage Cost**: 0.5% × $20 = **$0.10**

6. **Total Costs**: $0.336 + $0.294 + $0.20 + $0.10 = **$0.93**

7. **Net Profit**: $2.00 - $0.93 = **$1.07**

**Cost Impact**: Costs reduced profit by **46.5%** ($0.93 / $2.00)

### 4.4 Cost Impact by Trade Size

**Cost Breakdown Table** (per $20 trade, medium liquidity):

| Component | Typical Cost | % of Gross Profit (if $2 profit) |
|-----------|---------------|----------------------------------|
| Entry Fee | $0.20 - $0.35 | 10% - 17.5% |
| Exit Fee | $0.20 - $0.35 | 10% - 17.5% |
| Spread Cost | $0.10 - $0.30 | 5% - 15% |
| Slippage | $0.10 - $0.20 | 5% - 10% |
| **Total** | **$0.60 - $1.20** | **30% - 60%** |

**Key Insight**: For small profitable trades ($1-3 profit), costs can consume 30-60% of gross profit. This explains why many strategies appear profitable in backtests but fail in live trading.

---

## 5. Metric Recalculation

### 5.1 Max Win / Max Loss Adjustment

**Current Issue**: Max loss appears suspiciously small (1% of max win).

**Root Cause Analysis**:
1. **Exit Bias**: Strategy may exit winners quickly but hold losers
2. **Fee Asymmetry**: Fees may be calculated incorrectly for losses
3. **Data Issues**: Losses may not be fully captured

**Adjustment Method**:

1. **Recalculate Max Win** (with costs):
   ```
   Max_Win_Adjusted = Max_Win_Gross - Max_Costs_For_Winning_Trade
   ```

2. **Recalculate Max Loss** (with costs):
   ```
   Max_Loss_Adjusted = Max_Loss_Gross + Max_Costs_For_Losing_Trade
   ```
   Note: Costs ADD to losses (make them worse)

3. **Verify Ratio**:
   ```
   Win_Loss_Ratio = Max_Win_Adjusted / |Max_Loss_Adjusted|
   ```
   Realistic ratios: 1:1 to 3:1 (not 100:1)

**Example**:
- Current: Max Win = $2,000, Max Loss = $20 (100:1 ratio) ❌
- Adjusted: Max Win = $1,800, Max Loss = $40 (45:1 ratio) ⚠️
- **Still suspicious** - suggests exit bias or data issues

### 5.2 Sharpe Ratio Adjustment

**Current Formula**:
```
Sharpe = (Average Return - Risk_Free_Rate) / Std_Dev_Returns
```

**Adjusted Formula**:
```
Sharpe_Adjusted = (Average_Net_Return - Risk_Free_Rate) / Std_Dev_Net_Returns
```

**Key Changes**:
1. Use **net returns** (after costs) instead of gross returns
2. Recalculate **standard deviation** using net returns
3. Costs reduce average return AND may increase volatility

**Impact**: Sharpe ratio typically **decreases** by 20-40% when costs are included.

**Example**:
- Current: Sharpe = 1.2 (gross returns)
- Adjusted: Sharpe = 0.8 (net returns)
- **Interpretation**: Strategy is less attractive on risk-adjusted basis

### 5.3 ROI Adjustment

**Current Formula**:
```
ROI = (Total_Profit / Total_Capital_Deployed) × 100%
```

**Adjusted Formula**:
```
ROI_Adjusted = (Total_Net_Profit / Total_Capital_Deployed) × 100%
```

**Additional Consideration**:
```
ROI_After_Costs = ROI_Gross - Total_Cost_Rate
Where Total_Cost_Rate = Total_Costs / Total_Capital_Deployed
```

**Example** (from your simulation):
- Current: ROI = 32.71% (gross)
- Estimated costs: ~15-25% of gross profit
- Adjusted: ROI = 32.71% × (1 - 0.20) = **26.17%**
- Or: ROI = 32.71% - 6.54% = **26.17%**

**Cost Impact**: ROI reduced by **~20%** (from 32.71% to ~26%)

### 5.4 Win Rate Adjustment

**Current**: Win rate may be calculated on gross profits

**Adjusted**: Recalculate win rate using net profits
```
Winning_Trades_Net = Count(Trades where Net_Profit > 0)
Win_Rate_Adjusted = Winning_Trades_Net / Total_Trades
```

**Impact**: Win rate typically **decreases** by 2-5 percentage points.

**Example**:
- Current: Win Rate = 51.3% (gross)
- Adjusted: Win Rate = 48.5% (net)
- **Some marginal winners become losers** after costs

### 5.5 Pitfalls to Avoid

1. **Double-Counting Costs**: Don't subtract fees AND spreads if using bid/ask prices (spreads already account for execution difference)

2. **Asymmetric Cost Application**: Apply costs to BOTH winners and losers (costs always reduce net profit)

3. **Ignoring Small Trades**: Small profitable trades may become unprofitable after costs - this is realistic

4. **Static Cost Assumptions**: Costs vary by market conditions - use dynamic estimates

5. **Ignoring Opportunity Cost**: Consider that capital could be deployed elsewhere (though this is more advanced)

---

## 6. Diagnostic Statistics

### 6.1 Per-Game Distribution Analysis

**Purpose**: Identify if profitability is concentrated in a few games or distributed evenly.

**Metrics to Calculate**:

1. **Profit Distribution**:
   ```
   - Games with profit > $100
   - Games with profit $0-$100
   - Games with loss $0-$100
   - Games with loss > $100
   ```

2. **Concentration Metrics**:
   ```
   - Top 10% of games: % of total profit
   - Bottom 10% of games: % of total loss
   - Gini coefficient of profit distribution
   ```

3. **Interpretation**:
   - **Good**: Profit distributed across many games (diversified)
   - **Bad**: Profit concentrated in 5-10 games (overfitting risk)

### 6.2 Worst Decile Analysis

**Purpose**: Understand tail risk (worst-case scenarios).

**Metrics**:

1. **Worst 10% of Games**:
   ```
   - Average loss per game
   - Total loss from worst decile
   - % of total losses from worst decile
   ```

2. **Worst 10% of Trades**:
   ```
   - Average loss per trade
   - Total loss from worst decile
   - Frequency of large losses
   ```

3. **Interpretation**:
   - If worst 10% accounts for >50% of losses: **high tail risk**
   - If worst trades are manageable: **acceptable risk**

### 6.3 Cost Efficiency Metrics

**Purpose**: Measure how efficiently the strategy uses capital after costs.

**Metrics**:

1. **Cost-to-Profit Ratio**:
   ```
   Cost_Ratio = Total_Costs / Total_Gross_Profit
   ```
   - Good: < 20%
   - Warning: 20-40%
   - Bad: > 40%

2. **Break-Even Analysis**:
   ```
   Break_Even_Win_Rate = Total_Costs / (Avg_Win - Avg_Loss)
   ```
   - If break-even win rate > actual win rate: **strategy unprofitable**

3. **Cost per Trade**:
   ```
   Avg_Cost_Per_Trade = Total_Costs / Total_Trades
   ```
   - Compare to average profit per trade
   - If costs > 30% of avg profit: **marginal viability**

### 6.4 Liquidity Analysis

**Purpose**: Identify if strategy works in low-liquidity conditions.

**Metrics**:

1. **Profit by Liquidity Tier**:
   ```
   - High liquidity games: avg profit
   - Medium liquidity games: avg profit
   - Low liquidity games: avg profit
   ```

2. **Spread Impact**:
   ```
   - Games with tight spreads (<1%): performance
   - Games with wide spreads (>2%): performance
   ```

3. **Interpretation**:
   - If low-liquidity games are unprofitable: **strategy not viable**
   - If performance consistent across liquidity: **more robust**

### 6.5 Time-Based Analysis

**Purpose**: Identify if strategy performance varies by game timing.

**Metrics**:

1. **Profit by Game Time**:
   ```
   - Early game (0-25%): avg profit
   - Mid game (25-75%): avg profit
   - Late game (75-100%): avg profit
   ```

2. **Entry Timing**:
   ```
   - Trades entered early: win rate
   - Trades entered late: win rate
   ```

3. **Interpretation**:
   - If late-game trades are unprofitable: **execution risk**
   - If early-game trades are best: **information advantage**

### 6.6 Recommended Diagnostic Dashboard

**Summary Table** (to calculate after cost adjustment):

| Metric | Current (Gross) | Adjusted (Net) | Change | Interpretation |
|--------|-----------------|---------------|--------|----------------|
| Total Profit | $56,953.80 | ~$45,000-50,000 | -12-21% | Significant but acceptable |
| ROI | 32.71% | ~26-28% | -15-20% | Still positive |
| Win Rate | 51.3% | ~48-50% | -2-3% | Slight decrease |
| Sharpe Ratio | ? | ? | -20-40% | Needs calculation |
| Max Win | $2,000 | ~$1,800 | -10% | Still large |
| Max Loss | $20 | ~$40 | +100% | **Suspicious - investigate** |
| Avg Profit/Trade | $6.54 | ~$5.20 | -20% | Reduced but positive |
| Cost Ratio | 0% | ~15-25% | +15-25% | **High but manageable** |

### 6.7 Red Flags to Watch For

1. **Max Loss Too Small**: If max loss < 2× avg loss → **exit bias or data issue**

2. **Cost Ratio > 40%**: If costs consume >40% of gross profit → **marginal viability**

3. **Win Rate Drops Below 45%**: After costs, if win rate < 45% → **questionable strategy**

4. **Profit Concentration**: If >50% of profit from <10% of games → **overfitting risk**

5. **Negative Sharpe**: If Sharpe < 0 after costs → **strategy destroys value**

6. **Break-Even Win Rate > Actual**: If break-even win rate > actual win rate → **unprofitable**

---

## 7. Implementation Recommendations

### 7.1 Phase 1: Fee Integration

**Priority**: High  
**Complexity**: Low  
**Impact**: High

1. Add fee calculation to each trade entry/exit
2. Subtract fees from gross profit
3. Recalculate all metrics

**Expected Impact**: Reduce ROI by 10-15%

### 7.2 Phase 2: Bid-Ask Spread Integration

**Priority**: High  
**Complexity**: Medium  
**Impact**: Medium-High

1. Use actual bid/ask prices instead of mid-prices
2. Calculate spread cost per trade
3. Subtract from gross profit

**Expected Impact**: Reduce ROI by additional 5-10%

### 7.3 Phase 3: Slippage Estimation

**Priority**: Medium  
**Complexity**: Medium  
**Impact**: Medium

1. Implement liquidity-based slippage model
2. Apply slippage cost per trade
3. Use conservative estimates initially

**Expected Impact**: Reduce ROI by additional 3-5%

### 7.4 Phase 4: Diagnostic Analysis

**Priority**: High  
**Complexity**: Low  
**Impact**: High (for decision-making)

1. Calculate all diagnostic metrics
2. Create dashboard/report
3. Identify red flags

**Expected Impact**: Better understanding of strategy viability

---

## 8. Conclusion

### 8.1 Key Takeaways

1. **Trading costs are significant**: Expect 15-25% reduction in gross profits

2. **Fee structure is non-linear**: Highest at 50/50 odds, decreases toward extremes

3. **Bid-ask spreads matter**: Using mid-prices overstates profitability

4. **Slippage varies**: Estimate 0.2-1.0% depending on liquidity

5. **Max loss ratio is suspicious**: 1% ratio suggests exit bias or data issues

6. **Diagnostic stats are critical**: Need to understand distribution, not just averages

### 8.2 Realistic Expectations

After incorporating costs, expect:
- **ROI reduction**: 15-25% (from 32.71% to ~26-28%)
- **Win rate reduction**: 2-3 percentage points (from 51.3% to ~48-50%)
- **Sharpe ratio reduction**: 20-40% (needs calculation)
- **Max loss increase**: Should be 2-5× current value (investigate why it's so low)

### 8.3 Next Steps

1. **Implement fee calculation** (highest priority, easiest)
2. **Switch to bid/ask prices** (high priority, medium difficulty)
3. **Add slippage estimation** (medium priority, medium difficulty)
4. **Calculate diagnostic metrics** (high priority, low difficulty)
5. **Investigate max loss anomaly** (high priority, may reveal data issues)

### 8.4 Final Assessment

The strategy shows **promising gross returns** but needs cost adjustment to assess **real viability**. The suspicious max loss ratio suggests either:
- Exit bias (exiting winners quickly, holding losers)
- Data quality issues (losses not fully captured)
- Calculation errors (fees not applied to losses)

**Recommendation**: Implement cost adjustments and diagnostic analysis before considering live trading. The strategy may still be profitable after costs, but the margin will be thinner and risk-adjusted returns lower.

---

## Appendix A: Fee Calculation Examples

### A.1 Fee Formula Verification

**Formula**: `Fee = 7% × (Price × (1 - Price))`

**Verification Table**:

| Price | Price × (1-Price) | 7% Fee | Fee % of Price |
|-------|-------------------|--------|-----------------|
| 0.10 | 0.09 | 0.0063 | 6.3% |
| 0.25 | 0.1875 | 0.0131 | 5.24% |
| 0.50 | 0.25 | 0.0175 | 3.5% |
| 0.75 | 0.1875 | 0.0131 | 1.75% |
| 0.90 | 0.09 | 0.0063 | 0.7% |

**Note**: Fee as % of price decreases as price increases, but absolute fee is highest at 50%.

### A.2 Round-Trip Fee Example

**Scenario**: Complete round-trip trade
- Entry: Buy at $0.60
- Exit: Sell at $0.70

**Fees**:
- Entry: 7% × ($0.60 × $0.40) = 1.68% of contract value
- Exit: 7% × ($0.70 × $0.30) = 1.47% of contract value
- **Total**: ~3.15% of contract value

**On $20 bet**: $0.63 total fees

---

## Appendix B: Spread Calculation Examples

### B.1 Long Position Spread Cost

**Entry**:
- Mid-price: $0.60
- Bid: $0.595
- Ask: $0.605
- Buy at ask: $0.605

**Exit**:
- Mid-price: $0.70
- Bid: $0.695
- Ask: $0.705
- Sell at bid: $0.695

**Spread Cost**:
- If used mid-prices: Profit = ($0.70 - $0.60) = $0.10
- Actual execution: Profit = ($0.695 - $0.605) = $0.09
- **Spread cost**: $0.01 per contract = $0.20 on $20 bet

### B.2 Short Position Spread Cost

**Entry**:
- Mid-price: $0.80
- Bid: $0.795
- Ask: $0.805
- Sell at bid: $0.795

**Exit**:
- Mid-price: $0.65
- Bid: $0.645
- Ask: $0.655
- Buy at ask: $0.655

**Spread Cost**:
- If used mid-prices: Profit = ($0.80 - $0.65) = $0.15
- Actual execution: Profit = ($0.795 - $0.655) = $0.14
- **Spread cost**: $0.01 per contract = $0.20 on $20 bet

---

## Appendix C: Slippage Estimation Methods

### C.1 Conservative Approach

**Assumption**: Good execution, minimal market impact

**Formula**:
```
Slippage = 0.2% × Bet_Amount (high liquidity)
Slippage = 0.5% × Bet_Amount (medium liquidity)
Slippage = 1.0% × Bet_Amount (low liquidity)
```

**Example**: $20 bet, medium liquidity
- Slippage = 0.5% × $20 = **$0.10**

### C.2 Realistic Approach

**Assumption**: Average execution, some market impact

**Formula**:
```
Slippage = Spread × 0.5 + Base_Slippage
Base_Slippage = 0.1% × Bet_Amount
```

**Example**: $20 bet, 1% spread, medium liquidity
- Slippage = (1% × $20 × 0.5) + (0.1% × $20) = $0.10 + $0.02 = **$0.12**

### C.3 Pessimistic Approach

**Assumption**: Poor execution, significant market impact

**Formula**:
```
Slippage = Spread × 1.0 + Base_Slippage
Base_Slippage = 0.3% × Bet_Amount
```

**Example**: $20 bet, 1% spread, low liquidity
- Slippage = (1% × $20 × 1.0) + (0.3% × $20) = $0.20 + $0.06 = **$0.26**

**Recommendation**: Start with **realistic approach**, then test **conservative** and **pessimistic** scenarios.

---

## Appendix D: Technical Simulation Architecture

This section provides a detailed technical explanation of how the current simulation system works, including data flow, algorithms, and implementation details.

### D.1 Overall Architecture

**Design Pattern**: Map-Reduce Pattern for bulk simulation  
**Algorithm**: Divergence Threshold Trading Simulation  
**Complexity**: O(n × m) where n = number of games, m = average aligned data points per game  
**Parallelization**: ThreadPoolExecutor with 8 workers for I/O-bound database queries

**System Components**:

1. **API Endpoint** (`/api/simulation/bulk`): Entry point for bulk simulation requests
2. **Game Selection**: Fetches games with both ESPN and Kalshi data
3. **Parallel Processing**: Processes multiple games concurrently using thread pool
4. **Data Alignment**: Aligns ESPN probabilities with Kalshi prices by timestamp
5. **Trade Simulation**: State machine that executes trades based on divergence thresholds
6. **P&L Calculation**: Computes profit/loss for each trade based on actual game outcome
7. **Result Aggregation**: Combines results from all games into summary statistics
8. **Caching**: Caches individual game results for completed games

---

### D.2 Data Flow and Alignment Process

#### Step 1: Game Selection

**Endpoint**: `games.list_games()`  
**Filter**: `has_kalshi=True` (ensures both market records AND candlestick data exist)  
**Sorting**: By date, descending (most recent first)  
**Limit**: User-specified number of games (e.g., 500)

**SQL Query Logic**:
```sql
-- Simplified version of the actual query
SELECT 
    sg.event_id AS game_id,
    sg.event_date AS game_date,
    sg.home_team_abbrev,
    sg.away_team_abbrev
FROM espn.scoreboard_games sg
WHERE EXISTS (
    -- Must have Kalshi market record
    SELECT 1 FROM kalshi.markets km 
    WHERE km.espn_event_id = sg.event_id
)
AND EXISTS (
    -- Must have actual candlestick data
    SELECT 1 FROM kalshi.candlesticks c
    JOIN kalshi.markets_with_games kmw ON c.ticker = kmw.ticker
    WHERE kmw.espn_event_id = sg.event_id
    AND c.price_close IS NOT NULL
)
ORDER BY sg.event_date DESC
LIMIT num_games
```

**Output**: List of game dictionaries with `game_id`, `game_date`, team abbreviations

---

#### Step 2: ESPN Probability Data Retrieval

**Table**: `espn.probabilities_raw_items`  
**Function**: `get_aligned_data()` → ESPN data extraction

**Query**:
```sql
SELECT 
    last_modified_utc,
    home_win_percentage,  -- Stored as 0-100, normalized to 0-1
    away_win_percentage
FROM espn.probabilities_raw_items
WHERE game_id = %s
ORDER BY last_modified_utc
```

**Processing**:
1. **Normalize probabilities**: Convert from 0-100 format to 0-1 range
   ```python
   home_prob = (home_win_percentage / 100.0) if home_win_percentage > 1.0 else home_win_percentage
   ```

2. **Align to game timeline**: Map ESPN recording timestamps to game start time
   ```python
   # Calculate offset from first ESPN record to game start
   elapsed_from_first = espn_recording_timestamp - first_espn_timestamp
   aligned_timestamp = game_start_timestamp + elapsed_from_first
   ```

3. **Extract game metadata**: Get game start time and duration from `espn.scoreboard_games`
   ```sql
   SELECT event_date, 
          EXTRACT(EPOCH FROM (MAX(last_modified_utc) - MIN(last_modified_utc)))::INTEGER as duration_seconds
   FROM espn.scoreboard_games sg
   JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
   WHERE sg.event_id = %s
   ```

**Output**: List of ESPN data points:
```python
{
    "timestamp": aligned_timestamp,  # Unix timestamp (seconds)
    "home_prob": 0.65  # Normalized to 0-1 range
}
```

---

#### Step 3: Kalshi Market Matching

**View**: `kalshi.markets_with_games`  
**Purpose**: Match Kalshi markets to ESPN games and determine team side

**Query**:
```sql
SELECT 
    ticker,
    kalshi_team_side,  -- 'home' or 'away'
    yes_bid_close,
    yes_ask_close
FROM kalshi.markets_with_games
WHERE espn_event_id = %s
AND kalshi_team_side IS NOT NULL  -- Must have valid team match
```

**Team Side Logic**:
- `kalshi_team_side = 'home'`: Market represents home team → `home_prob = kalshi_price`
- `kalshi_team_side = 'away'`: Market represents away team → `home_prob = 1.0 - kalshi_price`

**Output**: List of market tickers with team side information

---

#### Step 4: Kalshi Candlestick Data Retrieval

**Table**: `kalshi.candlesticks`  
**Function**: `get_aligned_data()` → Kalshi data extraction

**Query**:
```sql
SELECT 
    period_ts,
    price_close,        -- Mid-price in cents (0-100)
    yes_bid_close,     -- Bid price in cents (for selling)
    yes_ask_close      -- Ask price in cents (for buying)
FROM kalshi.candlesticks c
JOIN kalshi.markets_with_games kmw ON c.ticker = kmw.ticker
WHERE kmw.espn_event_id = %s
AND c.period_ts >= game_start
AND c.period_ts <= game_end
ORDER BY period_ts
```

**Processing**:
1. **Convert prices**: From cents (0-100) to probability (0-1)
   ```python
   display_price = price_close / 100.0  # Convert cents to 0-1
   ```

2. **Convert to home probability**: Based on team side
   ```python
   if team_side == 'home':
       home_prob = display_price
   else:  # away
       home_prob = 1.0 - display_price
   ```

3. **Store bid/ask**: Preserve for execution price calculation
   ```python
   yes_bid = yes_bid_close / 100.0 if yes_bid_close else None
   yes_ask = yes_ask_close / 100.0 if yes_ask_close else None
   ```

**Output**: List of Kalshi data points:
```python
{
    "timestamp": unix_timestamp,
    "home_prob": 0.60,  # Converted to home win probability
    "yes_bid": 0.595,   # For short positions
    "yes_ask": 0.605    # For long positions
}
```

---

#### Step 5: Data Alignment Algorithm

**Function**: `get_aligned_data()` → Alignment logic  
**Algorithm**: Nearest-neighbor timestamp matching with time window filtering

**Process**:

1. **Initialize**: Start with first Kalshi data point
   ```python
   kalshi_idx = 0
   aligned_data = []
   ```

2. **For each ESPN point**, find closest Kalshi point:
   ```python
   for espn_point in espn_data:
       espn_time = espn_point["timestamp"]
       
       # Find closest Kalshi timestamp using linear search
       # (Kalshi data is sorted by timestamp)
       while (kalshi_idx < len(kalshi_data) - 1 and 
              abs(kalshi_data[kalshi_idx]["timestamp"] - espn_time) > 
              abs(kalshi_data[kalshi_idx + 1]["timestamp"] - espn_time)):
           kalshi_idx += 1
   ```

3. **Time difference check**: Only align if within 60 seconds
   ```python
   time_diff = abs(kalshi_point["timestamp"] - espn_time)
   if time_diff <= 60:  # Within 60 seconds
       # Proceed with alignment
   else:
       filtered_by_time_diff += 1
       continue
   ```

4. **Time window filtering**: Exclude first/last N seconds
   ```python
   elapsed = espn_time - game_start_timestamp
   if elapsed < exclude_first_seconds:
       filtered_by_time_window += 1
       continue
   if elapsed > (duration_seconds - exclude_last_seconds):
       filtered_by_time_window += 1
       continue
   ```

5. **Create aligned point**:
   ```python
   aligned_data.append({
       "timestamp": espn_time,
       "espn_prob": espn_prob,
       "kalshi_price": kalshi_point["home_prob"],
       "kalshi_bid": kalshi_point.get("yes_bid"),
       "kalshi_ask": kalshi_point.get("yes_ask"),
   })
   ```

**Output**: List of aligned data points with both ESPN and Kalshi probabilities

**Filtering Statistics**:
- Points filtered by time difference (>60s): Indicates data gaps or timing issues
- Points filtered by time window: Excluded first/last seconds per user settings
- Final aligned count: Number of valid data points for simulation

---

### D.3 Trade Execution Logic (State Machine)

**Design Pattern**: State Machine Pattern  
**Function**: `simulate_trading_strategy()`  
**State**: `SimulationState` dataclass tracking current position

**State Variables**:
```python
@dataclass
class SimulationState:
    open_position: Optional[str] = None  # None, "long_espn", or "short_espn"
    entry_espn_prob: Optional[float] = None
    entry_kalshi_price: Optional[float] = None
    entry_kalshi_bid: Optional[float] = None
    entry_kalshi_ask: Optional[float] = None
    entry_timestamp: Optional[int] = None
    trades: list[Trade] = []
```

**Algorithm**: Iterate through aligned data points, check entry/exit conditions

#### Entry Logic

**Long Position** (Buy "Yes" contract when ESPN > Kalshi):
```python
if state.open_position is None:
    divergence = espn_prob - kalshi_price
    
    if divergence > entry_threshold:  # e.g., > 0.05 (5 cents)
        if kalshi_ask is not None:  # Must have ask price to buy
            state.open_position = "long_espn"
            state.entry_espn_prob = espn_prob
            state.entry_kalshi_price = kalshi_price
            state.entry_kalshi_ask = kalshi_ask  # Buy at ask price
            state.entry_timestamp = timestamp
            successful_entries += 1
        else:
            entry_failed_bid_ask_long += 1  # Missing ask price
```

**Short Position** (Sell "Yes" contract when ESPN < Kalshi):
```python
elif divergence < -entry_threshold:  # e.g., < -0.05 (-5 cents)
    if kalshi_bid is not None:  # Must have bid price to sell
        state.open_position = "short_espn"
        state.entry_espn_prob = espn_prob
        state.entry_kalshi_price = kalshi_price
        state.entry_kalshi_bid = kalshi_bid  # Sell at bid price
        state.entry_timestamp = timestamp
        successful_entries += 1
    else:
        entry_failed_bid_ask_short += 1  # Missing bid price
```

**Entry Conditions**:
- **Long**: `divergence > entry_threshold` AND `kalshi_ask` exists
- **Short**: `divergence < -entry_threshold` AND `kalshi_bid` exists
- **Failure Reasons**: Insufficient divergence OR missing bid/ask data

#### Exit Logic

**Exit Condition**: Divergence converges below threshold
```python
elif state.open_position is not None:
    abs_divergence = abs(divergence)
    
    if abs_divergence < exit_threshold:  # e.g., < 0.02 (2 cents)
        # Close position and calculate P&L
        trade = Trade(
            entry_time=state.entry_timestamp,
            exit_time=timestamp,
            position_type=state.open_position,
            entry_espn_prob=state.entry_espn_prob,
            entry_kalshi_price=state.entry_kalshi_price,
            entry_kalshi_bid=state.entry_kalshi_bid,
            entry_kalshi_ask=state.entry_kalshi_ask,
            exit_espn_prob=espn_prob,
            exit_kalshi_price=kalshi_price,
            profit_cents=None,  # Calculated after
            actual_outcome=actual_outcome
        )
        trade.profit_cents = calculate_trade_pnl(trade, actual_outcome, bet_amount_dollars) * 100
        state.trades.append(trade)
        
        # Reset state
        state.open_position = None
        # ... clear all entry fields
```

**End-of-Game Handling**: Close any remaining open position
```python
if state.open_position is not None and aligned_data:
    last_point = aligned_data[-1]
    # Create trade with final prices
    trade = Trade(...)
    trade.profit_cents = calculate_trade_pnl(trade, actual_outcome, bet_amount_dollars) * 100
    state.trades.append(trade)
```

**Exit Conditions**:
- **Normal Exit**: `abs(divergence) < exit_threshold` (convergence)
- **End-of-Game**: Position still open at last data point (forced exit)

---

### D.4 Profit/Loss Calculation

**Function**: `calculate_trade_pnl()`  
**Input**: Trade object, actual game outcome, bet amount  
**Output**: Profit in dollars (positive = profit, negative = loss)

#### Long Position P&L

**Entry**: Buy "Yes" contracts at ask price  
**Logic**:
```python
if trade.position_type == "long_espn":
    entry_price_dollars = (trade.entry_kalshi_ask or 0)  # Price per contract (0-1)
    
    # Calculate number of contracts to risk bet_amount
    # Example: $20 bet, 50 cent entry = $20 / $0.50 = 40 contracts
    num_contracts = bet_amount_dollars / entry_price_dollars
    
    entry_cost = bet_amount_dollars  # Total cost = bet amount
    
    if actual_outcome == 1:  # Home won
        payout = num_contracts * 1.0  # Each contract pays $1.00
        profit = payout - entry_cost
    else:  # Home lost
        profit = -entry_cost  # Contracts expire worthless
```

**Example**:
- Entry: Buy at $0.60 (60 cents), bet $20
- Contracts: $20 / $0.60 = 33.33 contracts
- Cost: $20
- If home wins: Payout = 33.33 × $1.00 = $33.33, Profit = $13.33
- If home loses: Profit = -$20.00

#### Short Position P&L

**Entry**: Sell "Yes" contracts at bid price  
**Logic**:
```python
elif trade.position_type == "short_espn":
    entry_price_dollars = (trade.entry_kalshi_bid or 0)  # Price per contract (0-1)
    
    # Calculate number of contracts to risk bet_amount
    # When selling, risk is (1 - entry_price) per contract
    # Example: $20 bet, 80 cent entry = $20 / (1 - $0.80) = $20 / $0.20 = 100 contracts
    num_contracts = bet_amount_dollars / (1.0 - entry_price_dollars)
    
    entry_premium = num_contracts * entry_price_dollars  # Premium received
    
    if actual_outcome == 1:  # Home won
        payout_owed = num_contracts * 1.0  # Must pay $1.00 per contract
        profit = entry_premium - payout_owed
    else:  # Home lost
        profit = entry_premium  # Keep premium, contracts expire worthless
```

**Example**:
- Entry: Sell at $0.80 (80 cents), bet $20
- Contracts: $20 / (1 - $0.80) = $20 / $0.20 = 100 contracts
- Premium received: 100 × $0.80 = $80.00
- If home wins: Payout owed = 100 × $1.00 = $100.00, Profit = $80 - $100 = -$20.00
- If home loses: Profit = $80.00

**Key Insight**: Short positions profit when the event does NOT occur (home loses), and lose when it does occur (home wins).

---

### D.5 Parallel Processing Architecture

**Pattern**: ThreadPoolExecutor with worker pool  
**Workers**: 8 concurrent threads (optimal for I/O-bound database queries)  
**Thread Safety**: Uses `threading.Lock` for shared state (progress tracking, cache)

#### Worker Function

**Function**: `process_game()` (runs in each thread)  
**Isolation**: Each thread gets its own database connection from connection pool

**Process**:
```python
def process_game(game_data: dict, game_index: int) -> tuple[dict | None, dict | None]:
    # 1. Get database connection (thread-safe connection pool)
    with get_db_connection() as conn:
        # 2. Check if game is completed (for caching)
        is_completed = _is_game_completed(conn, game_id)
        
        # 3. Check cache for completed games
        if is_completed:
            cache_key = _generate_cache_key(...)
            cached_result = _simulation_cache.get(cache_key)
            if cached_result:
                return cached_result, None  # Cache hit
        
        # 4. Fetch aligned data
        aligned_data, game_start, duration, actual_outcome = get_aligned_data(
            conn, game_id, exclude_first_seconds, exclude_last_seconds
        )
        
        # 5. Run simulation
        results = simulate_trading_strategy(
            aligned_data, entry_threshold, exit_threshold, 
            actual_outcome, bet_amount_dollars=bet_amount
        )
        
        # 6. Cache result for completed games
        if is_completed:
            _simulation_cache.set(cache_key, results, ttl=86400 * 365)
        
        return results, None
```

#### Parallel Execution

**Implementation**:
```python
max_workers = min(8, len(games_list))  # Up to 8 workers

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit all games to thread pool
    future_to_game = {
        executor.submit(process_game, game_data, idx + 1): (idx + 1, game_data)
        for idx, game_data in enumerate(games_list)
    }
    
    # Process completed futures as they finish
    for future in as_completed(future_to_game):
        game_index, game_data = future_to_game[future]
        completed_count += 1
        
        # Update progress thread-safely
        with _progress_lock:
            _simulation_progress[request_id]["current"] = completed_count
        
        result, error = future.result()
        if result:
            game_results.append(result)
        else:
            failed_games.append(error)
```

**Benefits**:
- **Speed**: 8× faster than sequential processing (for I/O-bound operations)
- **Efficiency**: Database connection pooling handles concurrent connections
- **Progress Tracking**: Real-time updates as games complete
- **Error Isolation**: One game failure doesn't affect others

**Thread Safety**:
- **Progress Updates**: Protected by `_progress_lock`
- **Cache Access**: Protected by `_simulation_cache_lock`
- **Database Connections**: Each thread gets its own connection (no shared state)

---

### D.6 Caching Mechanism

**Cache Type**: `SimpleCache` with file persistence  
**TTL**: 1 year (31,536,000 seconds) for completed games  
**Storage**: In-memory + disk file (`simulation_results.cache`)

#### Cache Key Generation

**Function**: `_generate_cache_key()`  
**Algorithm**: SHA-256 hash of simulation parameters

```python
def _generate_cache_key(game_id, entry_threshold, exit_threshold, 
                        bet_amount, exclude_first, exclude_last) -> str:
    key_data = {
        "game_id": game_id,
        "entry_threshold": entry_threshold,
        "exit_threshold": exit_threshold,
        "bet_amount": bet_amount,
        "exclude_first_seconds": exclude_first,
        "exclude_last_seconds": exclude_last
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]
```

**Key Properties**:
- **Deterministic**: Same parameters → same key
- **Unique**: Different parameters → different key
- **Short**: First 16 characters of hash (sufficient for uniqueness)

#### Cache Lookup Flow

**For Completed Games**:
```python
# 1. Check if game has final scores
is_completed = _is_game_completed(conn, game_id)

# 2. Generate cache key
cache_key = _generate_cache_key(...)

# 3. Check cache
if is_completed:
    cached_result = _simulation_cache.get(cache_key)
    if cached_result:
        # Cache hit - return immediately
        return cached_result, None
```

**Cache Storage**:
```python
# After simulation completes
if is_completed:
    # Store result (without game metadata)
    cache_result = results.copy()
    cache_result.pop("game_id", None)
    cache_result.pop("game_date", None)
    
    # Cache with 1-year TTL
    _simulation_cache.set(cache_key, cache_result, ttl=86400 * 365)
```

**Cache Invalidation**:
- **Manual**: Via `/api/simulation/clear-cache` endpoint
- **Automatic**: TTL expiration (1 year)
- **On Parameter Change**: New parameters → new cache key → cache miss

**Cache Benefits**:
- **Speed**: Instant results for repeated queries
- **Efficiency**: Avoids redundant calculations
- **Consistency**: Same parameters → same results

---

### D.7 Result Aggregation

**Function**: `get_bulk_simulation_results()` → Aggregation logic  
**Pattern**: Map-Reduce (map = per-game simulation, reduce = aggregate statistics)

#### Aggregation Process

**Step 1: Collect All Trades**
```python
all_trades = []
total_profit_cents = 0.0
total_trades = 0

for results in game_results:
    total_profit_cents += results.get("total_profit_cents", 0.0)
    total_trades += results.get("num_trades", 0)
    
    # Collect all trades
    for trade in results.get("trades", []):
        all_trades.append(trade)
```

**Step 2: Calculate Aggregate Metrics**

**Basic Metrics**:
```python
winning_trades = [t for t in all_trades if (t.get("profit_cents") or 0) > 0]
win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
avg_profit_per_trade_cents = total_profit_cents / total_trades if total_trades > 0 else 0.0
```

**ROI Calculation**:
```python
total_capital_deployed = total_trades * bet_amount * 100  # in cents
roi_percentage = (total_profit_cents / total_capital_deployed * 100.0) 
                 if total_capital_deployed > 0 else 0.0
```

**Position Breakdown**:
```python
long_trades = [t for t in all_trades if t.get("position_type") == "long_espn"]
short_trades = [t for t in all_trades if t.get("position_type") == "short_espn"]
long_profit_cents = sum(t.get("profit_cents", 0) or 0 for t in long_trades)
short_profit_cents = sum(t.get("profit_cents", 0) or 0 for t in short_trades)
```

**Risk Metrics**:
```python
trade_profits = [(t.get("profit_cents") or 0) / 100.0 for t in all_trades]
max_loss = min(trade_profits) if trade_profits else 0.0
max_win = max(trade_profits) if trade_profits else 0.0
std_dev = statistics.stdev(trade_profits) if len(trade_profits) > 1 else 0.0
median_profit_cents = statistics.median([t.get("profit_cents") or 0 for t in all_trades])
```

**Advanced Metrics** (Expectancy, Profit Factor, Drawdown, etc.):
- See Section 5 of main document for full list
- All calculated from `all_trades` list after aggregation

**Per-Game Summary**:
```python
per_game_summary = [
    {
        "game_id": gr.get("game_id"),
        "game_date": gr.get("game_date"),
        "num_trades": gr.get("num_trades", 0),
        "profit_dollars": gr.get("total_profit_cents", 0) / 100.0,
        "win_rate": gr.get("win_rate", 0.0),
    }
    for gr in game_results
]
```

**Output**: Comprehensive dictionary with all aggregated metrics and per-game breakdown

---

### D.8 Progress Tracking

**Purpose**: Real-time progress updates for long-running simulations  
**Storage**: In-memory dictionary (`_simulation_progress`)  
**Thread Safety**: Protected by `_progress_lock`

**Progress Structure**:
```python
_simulation_progress[request_id] = {
    "current": completed_count,  # Number of games processed
    "total": len(games_list),     # Total games to process
    "status": "running"           # "running", "complete", or "error"
}
```

**Update Flow**:
```python
# After each game completes
completed_count += 1

with _progress_lock:
    _simulation_progress[request_id]["current"] = completed_count

# Frontend polls: GET /api/simulation/progress/{request_id}
```

**Frontend Integration**:
- Generates unique `request_id` for each simulation run
- Polls progress endpoint every 1-2 seconds
- Displays "Analyzing games: X/Y" to user
- Updates progress bar/percentage

---

### D.9 Error Handling and Edge Cases

#### Data Availability Errors

**No ESPN Data**:
```python
if espn_count == 0:
    raise ValueError(f"No ESPN probability data found for game {game_id}")
```

**No Kalshi Data**:
```python
if not kalshi_data:
    logger.warning(f"No Kalshi data found")
    return [], game_start_timestamp, duration_seconds, actual_outcome
```

**No Aligned Data**:
```python
if not aligned_data:
    logger.warning(f"No aligned data found after alignment process")
    return None, {"game_id": game_id, "reason": "No aligned data"}
```

#### Missing Bid/Ask Data

**Entry Failure**:
- If divergence sufficient but `kalshi_ask` missing → entry fails
- If divergence sufficient but `kalshi_bid` missing → entry fails
- Logged as `entry_failed_bid_ask_long` or `entry_failed_bid_ask_short`

**Fallback**: Uses `price_close` (mid-price) if bid/ask unavailable, but entry still requires bid/ask

#### Game Completion Status

**Check Logic**:
```python
def _is_game_completed(conn, game_id: str) -> bool:
    check_sql = """
    SELECT MAX(e.home_score) as final_home_score, 
           MAX(e.away_score) as final_away_score
    FROM espn.prob_event_state e
    WHERE e.game_id = %s
    """
    row = conn.execute(check_sql, (game_id,)).fetchone()
    return row and row[0] is not None and row[1] is not None
```

**Purpose**: Only cache results for completed games (in-progress games may have different outcomes)

#### Thread Safety Considerations

**Database Connections**: Each thread gets its own connection (no shared state)  
**Progress Updates**: Protected by lock  
**Cache Access**: Protected by lock  
**Result Collection**: Thread-safe list append (CPython GIL ensures atomicity)

---

### D.10 Performance Characteristics

**Time Complexity**:
- **Per Game**: O(m) where m = aligned data points
- **Bulk Simulation**: O(n × m) where n = games, m = avg data points per game
- **Parallelization**: O(n × m / 8) with 8 workers (theoretical)

**Space Complexity**:
- **Per Game**: O(m) for aligned data + O(t) for trades where t = number of trades
- **Bulk Simulation**: O(n × t) for all trades in memory
- **Cache**: O(n) entries (one per game per parameter set)

**Bottlenecks**:
1. **Database Queries**: I/O-bound (mitigated by parallelization)
2. **Data Alignment**: O(m × log m) if using binary search (currently O(m) linear)
3. **Trade Simulation**: O(m) per game (efficient)
4. **Aggregation**: O(t) where t = total trades (efficient)

**Optimization Opportunities**:
- Binary search for alignment (currently linear search)
- Batch database queries (currently per-game queries)
- Streaming aggregation (currently loads all trades into memory)

---

### D.11 Summary: Complete Data Flow

**End-to-End Flow**:

1. **User Request**: POST `/api/simulation/bulk` with parameters
2. **Game Selection**: Query `games.list_games()` → Get N games
3. **Parallel Processing**: Submit all games to ThreadPoolExecutor
4. **Per-Game Processing** (in parallel):
   - Check cache (if completed game)
   - Fetch ESPN probabilities
   - Fetch Kalshi candlesticks
   - Match markets to games
   - Align data by timestamp
   - Run simulation (state machine)
   - Calculate P&L for each trade
   - Cache result (if completed)
5. **Aggregation**: Collect all results, calculate aggregate metrics
6. **Response**: Return comprehensive results dictionary

**Key Design Decisions**:
- **State Machine**: Simple, deterministic trade execution
- **Parallel Processing**: 8 workers for I/O-bound operations
- **Caching**: Per-game, per-parameter caching for completed games
- **Data Alignment**: Nearest-neighbor matching with 60-second window
- **P&L Calculation**: Based on actual game outcome (not exit price)

---

## Appendix E: Database Schema Reference

This section documents the database tables used in the trading simulation. Tables are organized by schema (`espn.*`, `kalshi.*`).

### D.1 ESPN Schema Tables

#### `espn.probabilities_raw_items`

**Purpose**: Stores raw ESPN probability updates ("items") from the probabilities API endpoint.

**Key Fields for Simulation**:
- `game_id` (TEXT): ESPN competition ID (used as primary game identifier)
- `last_modified_utc` (TIMESTAMPTZ): Timestamp when probability was updated
- `home_win_percentage` (DOUBLE PRECISION): Home team win probability (0-100 format)
- `away_win_percentage` (DOUBLE PRECISION): Away team win probability (0-100 format)
- `sequence_number` (INTEGER): Ordering within game
- `event_id` (BIGINT): ESPN play ID (nullable)

**Primary Key**: `(season_label, game_id, sequence_number, event_id)`

**Schema Definition**:
```sql
CREATE TABLE espn.probabilities_raw_items (
  season_label           TEXT NOT NULL,
  game_id                TEXT NOT NULL,     -- ESPN competition id
  event_id               BIGINT,            -- ESPN play id (parsed from play.$ref)
  sequence_number        INTEGER,
  last_modified_utc      TIMESTAMPTZ,
  home_win_percentage    DOUBLE PRECISION,  -- 0-100 format
  away_win_percentage    DOUBLE PRECISION,  -- 0-100 format
  tie_percentage         DOUBLE PRECISION,
  spread_cover_prob_home DOUBLE PRECISION,
  spread_push_prob       DOUBLE PRECISION,
  total_over_prob        DOUBLE PRECISION,
  play_ref               TEXT,
  home_team_ref          TEXT,
  away_team_ref          TEXT,
  competition_ref        TEXT,
  source_ref             TEXT,
  raw_item               JSONB NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (season_label, game_id, sequence_number, event_id)
);
```

**Usage in Simulation**: 
- Primary source for ESPN probability time series
- Used to calculate divergence from Kalshi prices
- `last_modified_utc` used for time alignment with Kalshi candlestick data

---

#### `espn.scoreboard_games`

**Purpose**: Stores ESPN scoreboard data with game metadata, final scores, and team information.

**Key Fields for Simulation**:
- `event_id` (TEXT): ESPN event ID (matches `game_id` from probabilities)
- `event_date` (TIMESTAMPTZ): Scheduled game time
- `home_team_abbrev` (TEXT): Home team abbreviation (e.g., "MIA")
- `away_team_abbrev` (TEXT): Away team abbreviation (e.g., "ATL")
- `home_score` (INTEGER): Final home team score
- `away_score` (INTEGER): Final away team score
- `status_completed` (BOOLEAN): Whether game is completed
- `home_winner` (BOOLEAN): Whether home team won

**Primary Key**: `(event_id, scoreboard_date)`

**Schema Definition**:
```sql
CREATE TABLE espn.scoreboard_games (
  event_id               TEXT NOT NULL,      -- ESPN event id
  scoreboard_date        DATE NOT NULL,      -- Date of scoreboard file
  event_uid              TEXT,
  event_date             TIMESTAMPTZ,        -- Scheduled game time
  event_name             TEXT,
  short_name             TEXT,
  season_year            INTEGER,
  season_type            INTEGER,
  season_slug            TEXT,
  competition_id         TEXT,
  venue_id               TEXT,
  venue_name             TEXT,
  venue_city             TEXT,
  venue_state            TEXT,
  is_neutral_site        BOOLEAN,
  attendance             INTEGER,
  home_team_id           TEXT,               -- ESPN team id
  home_team_abbrev       TEXT,               -- e.g., "MIA"
  home_team_name         TEXT,               -- e.g., "Heat"
  home_team_display_name TEXT,               -- e.g., "Miami Heat"
  home_score             INTEGER,
  home_winner            BOOLEAN,
  away_team_id           TEXT,               -- ESPN team id
  away_team_abbrev       TEXT,               -- e.g., "ATL"
  away_team_name         TEXT,               -- e.g., "Hawks"
  away_team_display_name TEXT,               -- e.g., "Atlanta Hawks"
  away_score             INTEGER,
  away_winner            BOOLEAN,
  status_type_id         TEXT,
  status_name            TEXT,
  status_state           TEXT,
  status_completed       BOOLEAN,
  status_period          INTEGER,
  status_clock           TEXT,
  broadcast              TEXT,
  raw_event              JSONB NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (event_id, scoreboard_date)
);
```

**Usage in Simulation**:
- Provides game start time (`event_date`) for time alignment
- Used to determine game completion status for caching
- Provides team abbreviations for display/logging
- Used to match Kalshi markets to ESPN games

---

#### `espn.prob_event_state`

**Purpose**: Derived table that combines ESPN probability data with game state (scores, time remaining).

**Key Fields for Simulation**:
- `espn_competition_id` (TEXT): ESPN competition ID (matches `game_id`)
- `play_id` (BIGINT): ESPN play ID
- `sequence_number` (INTEGER): Ordering within game
- `home_win_percentage` (DOUBLE PRECISION): Home team win probability
- `away_win_percentage` (DOUBLE PRECISION): Away team win probability
- `home_score` (INTEGER): Home team score at this point
- `away_score` (INTEGER): Away team score at this point
- `last_modified_utc` (TIMESTAMPTZ): Timestamp of probability update

**Primary Key**: `(espn_competition_id, play_id)`

**Schema Definition**:
```sql
CREATE TABLE espn.prob_event_state (
  espn_event_id        TEXT NOT NULL,
  espn_competition_id   TEXT NOT NULL,
  play_id              BIGINT NOT NULL,
  sequence_number      INTEGER NOT NULL,
  point_differential   INTEGER NOT NULL,  -- home_score - away_score
  time_remaining       INTEGER,           -- seconds remaining in game
  home_score           INTEGER,
  away_score           INTEGER,
  current_winning_team SMALLINT,          -- 0=home, 1=away, NULL=tied
  final_winning_team   SMALLINT,          -- 0=home, 1=away, NULL=tied
  possession_side      SMALLINT,          -- 0=home, 1=away, NULL=unknown
  period_number        INTEGER,
  clock_seconds        INTEGER,           -- seconds remaining in current period
  home_win_percentage  DOUBLE PRECISION,
  away_win_percentage  DOUBLE PRECISION,
  tie_percentage       DOUBLE PRECISION,
  spread_cover_prob_home DOUBLE PRECISION,
  spread_push_prob     DOUBLE PRECISION,
  total_over_prob      DOUBLE PRECISION,
  last_modified_utc    TIMESTAMPTZ,
  PRIMARY KEY (espn_competition_id, play_id)
);
```

**Usage in Simulation**:
- Used to check game completion status (via `home_score` and `away_score`)
- Provides final scores for trade P&L calculation
- Less frequently used than `probabilities_raw_items` (prefer raw items for time series)

---

### D.2 Kalshi Schema Tables

#### `kalshi.candlesticks`

**Purpose**: Time-series OHLC (Open, High, Low, Close) data for Kalshi prediction market contracts.

**Key Fields for Simulation**:
- `ticker` (TEXT): Market ticker (e.g., "KXNBAGAME-25DEC25MINDEN-MIN")
- `period_ts` (TIMESTAMPTZ): End timestamp of candlestick period
- `price_close` (INTEGER): Closing price in cents (e.g., 60 = $0.60 = 60% probability)
- `yes_bid_close` (INTEGER): Yes bid price in cents at period close
- `yes_ask_close` (INTEGER): Yes ask price in cents at period close
- `period_interval_min` (INTEGER): Candlestick period in minutes (typically 1 minute)

**Primary Key**: `(ticker, period_ts, period_interval_min)`

**Schema Definition**:
```sql
CREATE TABLE kalshi.candlesticks (
  candlestick_id      BIGSERIAL PRIMARY KEY,
  source_file_id      BIGINT REFERENCES source_files(source_file_id),
  ticker              TEXT NOT NULL,                  -- market ticker
  period_ts           TIMESTAMPTZ NOT NULL,           -- end of candle period
  period_interval_min INTEGER NOT NULL,               -- candle period in minutes
  price_open          INTEGER,                        -- OHLC for last traded price (cents)
  price_high          INTEGER,
  price_low           INTEGER,
  price_close         INTEGER,                        -- Most commonly used
  price_mean          INTEGER,
  price_previous      INTEGER,
  yes_bid_open        INTEGER,                        -- OHLC for yes bid (cents)
  yes_bid_high        INTEGER,
  yes_bid_low         INTEGER,
  yes_bid_close       INTEGER,                        -- Used for exit prices (short)
  yes_ask_open        INTEGER,                        -- OHLC for yes ask (cents)
  yes_ask_high        INTEGER,
  yes_ask_low         INTEGER,
  yes_ask_close       INTEGER,                        -- Used for entry prices (long)
  volume              BIGINT,
  open_interest       BIGINT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ux_kalshi_candlesticks_ticker_period 
    UNIQUE (ticker, period_ts, period_interval_min)
);
```

**Usage in Simulation**:
- **Primary data source** for Kalshi market prices
- `price_close` used as mid-price for divergence calculation
- `yes_bid_close` and `yes_ask_close` used for actual execution prices (when available)
- `period_ts` used for time alignment with ESPN probabilities
- Time range filtered to game window (game_start to game_end)

**Important Notes**:
- Prices stored as **cents** (0-100 range, representing 0-100% probability)
- Must convert to 0-1 range for calculations: `price_close / 100.0`
- Bid/ask prices may be NULL if market has no active orders
- Simulation should use bid/ask when available, fall back to mid-price

---

#### `kalshi.markets`

**Purpose**: Denormalized market records at each snapshot, containing market metadata and current pricing.

**Key Fields for Simulation**:
- `ticker` (TEXT): Market ticker (matches `candlesticks.ticker`)
- `event_ticker` (TEXT): Event-level ticker (e.g., "KXNBAGAME-25DEC25MINDEN")
- `yes_sub_title` (TEXT): Team name for "Yes" outcome
- `no_sub_title` (TEXT): Team name for "No" outcome
- `last_price` (INTEGER): Last traded price in cents
- `yes_bid` (INTEGER): Current Yes bid price in cents
- `yes_ask` (INTEGER): Current Yes ask price in cents
- `status` (TEXT): Market status ("active", "closed", etc.)
- `result` (TEXT): Settlement result if resolved
- `espn_event_id` (TEXT): Linked ESPN event ID (added in migration 028)

**Primary Key**: `(snapshot_id, ticker)`

**Schema Definition**:
```sql
CREATE TABLE kalshi.markets (
  snapshot_id           BIGINT NOT NULL REFERENCES kalshi.market_snapshots(snapshot_id),
  ticker                TEXT NOT NULL,
  event_ticker          TEXT NOT NULL,
  title                 TEXT,
  subtitle              TEXT,
  yes_sub_title         TEXT,                         -- team name for yes outcome
  no_sub_title          TEXT,                         -- team name for no outcome
  market_type           TEXT,                         -- "binary"
  status                TEXT,                         -- "active", "closed", etc.
  result                TEXT,                         -- settlement result
  last_price            INTEGER,                      -- cents (39 = $0.39 = 39%)
  yes_bid               INTEGER,
  yes_ask               INTEGER,
  no_bid                INTEGER,
  no_ask                INTEGER,
  previous_price        INTEGER,
  volume                BIGINT,
  volume_24h            BIGINT,
  open_interest         BIGINT,
  liquidity             BIGINT,                       -- liquidity in cents
  open_time             TIMESTAMPTZ,
  close_time            TIMESTAMPTZ,
  expiration_time       TIMESTAMPTZ,
  expected_expiration_time TIMESTAMPTZ,
  created_time          TIMESTAMPTZ,
  rules_primary         TEXT,
  rules_secondary       TEXT,
  early_close_condition TEXT,
  can_close_early       BOOLEAN,
  notional_value        INTEGER,                      -- typically 100 cents
  tick_size             INTEGER,
  espn_event_id         TEXT,                         -- Added in migration 028
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, ticker)
);
```

**Usage in Simulation**:
- Used to identify which Kalshi markets correspond to which ESPN games (via `espn_event_id`)
- `yes_sub_title` used to determine team side (home/away) via `markets_with_games` view
- Provides metadata for market matching and filtering

---

#### `kalshi.markets_with_games` (VIEW)

**Purpose**: View that joins Kalshi markets with ESPN scoreboard games and NBA games, adding computed `kalshi_team_side` field.

**Key Computed Fields**:
- `kalshi_team_side` (TEXT): Computed field indicating which team the market represents ("home" or "away")
- `espn_event_id` (TEXT): ESPN event ID for joining
- `espn_home_team` (TEXT): ESPN home team abbreviation
- `espn_away_team` (TEXT): ESPN away team abbreviation
- `ticker` (TEXT): Kalshi market ticker

**View Definition** (simplified):
```sql
CREATE OR REPLACE VIEW kalshi.markets_with_games AS
SELECT 
    km.snapshot_id,
    km.ticker,
    km.event_ticker,
    km.yes_sub_title,
    km.no_sub_title,
    km.last_price,
    km.yes_bid,
    km.yes_ask,
    km.espn_event_id,
    sg.event_date AS espn_game_time,
    sg.home_team_abbrev AS espn_home_team,
    sg.away_team_abbrev AS espn_away_team,
    -- Computed: which team does this market represent?
    CASE 
        WHEN (km.yes_sub_title ILIKE '%' || sg.home_team_abbrev || '%' 
              OR sg.home_team_abbrev ILIKE '%' || km.yes_sub_title || '%')
        THEN 'home'
        WHEN (km.yes_sub_title ILIKE '%' || sg.away_team_abbrev || '%'
              OR sg.away_team_abbrev ILIKE '%' || km.yes_sub_title || '%')
        THEN 'away'
        ELSE NULL
    END AS kalshi_team_side
FROM kalshi.markets km
LEFT JOIN espn.scoreboard_games sg ON km.espn_event_id = sg.event_id;
```

**Usage in Simulation**:
- Primary view for matching Kalshi markets to ESPN games
- `kalshi_team_side` used to convert Kalshi prices to home win probability:
  - If `kalshi_team_side = 'home'`: `home_prob = kalshi_price`
  - If `kalshi_team_side = 'away'`: `home_prob = 1.0 - kalshi_price`
- Filters markets to only those with valid ESPN game matches

---

#### `kalshi.market_snapshots`

**Purpose**: Stores full JSON snapshots of Kalshi market data for provenance and replay.

**Key Fields**:
- `snapshot_id` (BIGSERIAL): Primary key, referenced by `kalshi.markets`
- `source_file_id` (BIGINT): Links to `source_files` table
- `series_ticker` (TEXT): Series identifier (e.g., "KXNBAGAME")
- `fetch_timestamp` (TIMESTAMPTZ): When data was fetched
- `raw_snapshot` (JSONB): Full JSON payload

**Schema Definition**:
```sql
CREATE TABLE kalshi.market_snapshots (
  snapshot_id     BIGSERIAL PRIMARY KEY,
  source_file_id  BIGINT NOT NULL REFERENCES source_files(source_file_id),
  series_ticker   TEXT NOT NULL,
  fetch_timestamp TIMESTAMPTZ NOT NULL,
  total_markets   INTEGER NOT NULL,
  raw_snapshot    JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ux_kalshi_market_snapshots_source_file UNIQUE (source_file_id)
);
```

**Usage in Simulation**:
- Not directly used in simulation queries
- Provides provenance tracking for data quality audits
- Enables replay/reprocessing of historical data

---

### D.3 Data Flow in Simulation

**Step 1: Game Selection**
- Query `espn.scoreboard_games` to get list of games
- Filter by `status_completed = true` for caching
- Use `event_id` as primary game identifier

**Step 2: ESPN Probability Data**
- Query `espn.probabilities_raw_items` filtered by `game_id`
- Extract `home_win_percentage` (convert from 0-100 to 0-1 range)
- Use `last_modified_utc` for time alignment
- Align timestamps to game timeline using `espn.scoreboard_games.event_date`

**Step 3: Kalshi Market Matching**
- Query `kalshi.markets_with_games` view filtered by `espn_event_id`
- Extract `kalshi_team_side` to determine which team the market represents
- Get `ticker` for candlestick queries

**Step 4: Kalshi Price Data**
- Query `kalshi.candlesticks` filtered by `ticker` and time range
- Use `period_ts` for time alignment with ESPN data
- Extract `price_close` (mid-price) or `yes_bid_close`/`yes_ask_close` (execution prices)
- Convert prices from cents (0-100) to probability (0-1) range
- Convert to home win probability using `kalshi_team_side`:
  - If `team_side = 'home'`: `home_prob = price / 100.0`
  - If `team_side = 'away'`: `home_prob = 1.0 - (price / 100.0)`

**Step 5: Data Alignment**
- Match ESPN and Kalshi data points by timestamp (within 60-second window)
- Filter by game time window (exclude first/last N seconds)
- Create aligned data points with both ESPN and Kalshi probabilities

**Step 6: Trade Execution**
- Calculate divergence: `divergence = espn_prob - kalshi_prob`
- Enter trades when `abs(divergence) > entry_threshold`
- Exit trades when `abs(divergence) < exit_threshold`
- Calculate P&L using actual outcome from `espn.scoreboard_games` (home_score, away_score)

---

### D.4 Important Data Type Notes

**Price Formats**:
- **Kalshi**: Prices stored as **cents** (0-100), representing 0-100% probability
- **ESPN**: Probabilities stored as **percentage** (0-100) in `probabilities_raw_items`, but should be normalized to 0-1 for calculations
- **Simulation**: All calculations use **0-1 probability range** internally

**Timestamp Handling**:
- All timestamps stored as `TIMESTAMPTZ` (timezone-aware)
- Converted to Unix timestamps (seconds) for alignment calculations
- Game start time from `espn.scoreboard_games.event_date`
- Data points aligned to game timeline (not wall-clock time)

**Team Side Conversion**:
- Kalshi markets can represent either home or away team
- `kalshi_team_side` field indicates which team
- Must convert Kalshi price to home win probability:
  - Home market: `home_prob = kalshi_price`
  - Away market: `home_prob = 1.0 - kalshi_price`

---

**End of Analysis**

