# Grid Search Hyperparameter Optimization Analysis

**Date**: 2025-01-27  
**Context**: Data scientist feedback on trading simulation results  
**Status**: Analysis & Recommendations

## Executive Summary

The current trading strategy shows **statistical edge** but **insufficient profitability** after accounting for trading costs (fees, slippage, bid-ask spread). The data scientist recommends two parallel paths forward:

1. **Signal Refinement**: Improve the ESPN probability model/calibration (long-term)
2. **Hyperparameter Optimization**: Grid search on entry/exit thresholds (short-term)

**Updated Guidance**: "do a hyperparam grid search on the entry/exit, then graph the performance to detect patterns"

This analysis focuses on the **grid search approach** with emphasis on:
- **Systematic Parameter Exploration**: Test all valid combinations of entry/exit thresholds (count depends on ranges and constraints)
- **Performance Visualization**: Generate heatmaps, contour plots, and marginal effect charts
- **Pattern Detection**: Identify optimal regions, parameter sensitivity, trade-offs, and interactions
- **Statistical Validation**: Apply multiple comparisons correction (FDR) to avoid false discoveries

The goal is to **graph performance and detect patterns** to find robust optimal thresholds, not just identify a single best point.

---

## Current State Analysis

### Current Strategy Parameters

**Entry/Exit Thresholds** (from `simulate_trading_strategy.py`):
- **Entry Threshold**: 0.05 (5 cents) - default
- **Exit Threshold**: 0.02 (2 cents) - default
- **Note**: Thresholds are in probability units (0-1 range), where 1 cent = 0.01 probability units

**Trading Costs** (from `calculate_trade_pnl`):
- **Kalshi Fees**: 7% × (price × (1 - price)) × bet_amount
  - Highest at 50% probability (~1.75% of bet)
  - Decreases toward extremes
- **Bid-Ask Spread**: Embedded in execution prices (not double-counted)
- **Slippage**: Optional, configurable (default: 0.0)

**Current Performance**:
- Strategy shows **edge** (positive expected value before costs)
- **Net profit insufficient** to overcome fees
- Need to either:
  - Increase edge per trade (better signal)
  - Reduce trading frequency (more selective entries)
  - Optimize entry/exit thresholds (grid search)

---

## Data Scientist Feedback Translation

### Key Points from Feedback

1. **"it makes sense, close to what i expect, but there is some edge it seems, just not enough to overcome fees"**
   - **Translation**: Strategy logic is sound, shows predictive edge, but trading costs erode profits
   - **Implication**: Need to increase edge per trade OR reduce trade frequency

2. **"so the next step would be refining the signal, improving the calibration, possibly adding new parameters"**
   - **Translation**: Long-term solution: Improve ESPN probability model quality
   - **Implication**: Better signal = higher edge per trade = more profitable after costs

3. **"we can also try changing the entry conditions to be more selective"**
   - **Translation**: Short-term solution: Increase entry threshold to reduce trade frequency
   - **Implication**: Fewer trades = lower total fees = potentially better net profit

4. **"well we need to actually work on our signal lol, like we're using espn rn"**
   - **Translation**: ESPN probabilities are a proxy signal, not optimized for trading
   - **Implication**: ESPN model may be miscalibrated or missing features

5. **"if you don't want to do that, you can try grid search on the espn odds"**
   - **Translation**: Alternative to signal refinement: Optimize hyperparameters (entry/exit thresholds)
   - **Implication**: Find optimal thresholds that maximize net profit after costs

6. **"grid search for hyperparams, like altering the entry/exit thresholds"**
   - **Translation**: Systematically test different entry/exit threshold combinations
   - **Implication**: Current default thresholds may not be optimal

7. **"and see if there's any pattern, obv u need to correct for multiple comparisons"**
   - **Translation**: Look for patterns in results, but account for multiple hypothesis testing
   - **Implication**: Use Bonferroni correction or similar to avoid false discoveries

8. **"but the pattern is important"**
   - **Translation**: Even with correction, finding patterns is valuable for understanding
   - **Implication**: Patterns reveal optimal parameter regions, not just single best values

---

## Grid Search Design

### Hyperparameter Space

**Entry Threshold Range**:
- **Current**: 5 cents (0.05)
- **Suggested Range**: 2 cents to 10 cents (0.02 to 0.10)
- **Step Size**: 1 cent (0.01) = 9 values
- **Rationale**: 
  - Lower thresholds = more trades = more fees
  - Higher thresholds = fewer trades = less fees but may miss opportunities

**Exit Threshold Range**:
- **Current**: 2 cents (0.01)
- **Suggested Range**: 0 cents to 5 cents (0.00 to 0.05)
- **Step Size**: 0.5 cents (0.005) = 11 values
- **Rationale**:
  - Lower thresholds = hold longer = more time for convergence
  - Higher thresholds = exit sooner = capture profits faster

**Total Combinations**: 9 × 11 = **99 parameter combinations**

### Grid Search Algorithm

**Design Pattern**: Exhaustive Grid Search  
**Algorithm**: Brute Force Parameter Optimization  
**Big O Complexity**: O(n × m × k) where:
- n = number of games
- m = average aligned data points per game
- k = number of parameter combinations (99)

**Pros**:
- Exhaustive: Tests all combinations in search space
- Simple: Easy to implement and understand
- Deterministic: Same results every run
- Pattern Discovery: Reveals parameter sensitivity and optimal regions

**Cons**:
- Computationally Expensive: 99× more simulations than single run
- Multiple Comparisons Problem: Need statistical correction
- Overfitting Risk: May find spurious patterns in sample
- No Gradient Information: Doesn't use optimization techniques

### Multiple Comparisons Correction

**Problem**: Testing 99 hypotheses increases false discovery rate  
**Solution**: Bonferroni Correction or False Discovery Rate (FDR) control

**Bonferroni Correction**:
- Adjust significance threshold: α_adjusted = α / k
- Example: α = 0.05, k = 99 → α_adjusted = 0.0005
- **Pros**: Simple, conservative, guarantees family-wise error rate
- **Cons**: Very conservative, may miss true patterns

**False Discovery Rate (FDR) - Benjamini-Hochberg**:
- Less conservative than Bonferroni
- Controls expected proportion of false discoveries
- Better for exploratory analysis
- **Pros**: Less conservative, better power
- **Cons**: More complex, doesn't guarantee family-wise error rate

**Recommendation**: Use **FDR (Benjamini-Hochberg)** for pattern discovery, but report both corrected and uncorrected results.

### Evaluation Metrics

**Primary Metric**: **Net Profit After Costs** (dollars)
- Most relevant for trading profitability
- Accounts for all costs (fees, slippage, spread)

**Secondary Metrics**:
- **Win Rate**: Percentage of profitable trades
- **ROI**: Return on invested capital
- **Sharpe Ratio**: Risk-adjusted returns
- **Profit Factor**: Gross profits / Gross losses
- **Max Drawdown**: Maximum peak-to-trough decline
- **Trades per Game**: Trading frequency indicator

**Pattern Analysis**:
- **Parameter Sensitivity**: How much does net profit change with threshold changes?
- **Optimal Regions**: Are there ranges of thresholds that consistently perform well?
- **Trade-off Analysis**: Relationship between trade frequency and profitability

---

## Implementation Plan

### Phase 1: Grid Search Infrastructure

**Task 1.1**: Create grid search runner script
- **File**: `scripts/grid_search_hyperparameters.py`
- **Design Pattern**: Map-Reduce Pattern for parallel execution
- **Algorithm**: Exhaustive Grid Search with Train/Valid/Test Splits
- **Big O**: O(k × n × m / p) where k = parameter combinations (computed dynamically), n = games, m = data points per game, p = workers

**CLI Arguments** (required for reproducibility):
```python
--season: str (e.g., "2025-26") OR --game-list: str (path to JSON file with game IDs)
--entry-min: float (default: 0.02)  # 2 cents in probability units
--entry-max: float (default: 0.10)   # 10 cents in probability units
--entry-step: float (default: 0.01)  # 1 cent step size
--exit-min: float (default: 0.00)    # 0 cents (convergence exit)
--exit-max: float (default: 0.05)    # 5 cents in probability units
--exit-step: float (default: 0.005)  # 0.5 cents step size
--workers: int (default: 8)
--seed: int (default: 42, for deterministic splits)
--enable-fees: bool (default: True)  # CRITICAL: Default to realistic costs
--slippage-rate: float (default: 0.0)  # Default to no slippage
--min-trade-count: int (default: 200)  # Guardrail: flag combos with too few trades
--output-dir: str (default: "grid_search_results/")
--train-ratio: float (default: 0.70)
--valid-ratio: float (default: 0.15)
--test-ratio: float (default: 0.15)
--top-n: int (default: 10)  # Top N train combos to consider for valid selection
```

**Grid Generation Logic**:
- Generate all combinations of (entry_threshold, exit_threshold) from ranges
- **Constraints** (skip invalid combos):
  - `entry > 0` (must be positive)
  - `exit >= 0` (can be zero for convergence exit)
  - `exit < entry` (exit threshold must be less than entry threshold)
- Example: entry_min=0.02, entry_max=0.10, entry_step=0.01 → 9 entry values
- Example: exit_min=0.00, exit_max=0.05, exit_step=0.005 → 11 exit values
- **Total valid combos**: Computed dynamically after applying constraints (entry > 0, exit >= 0, exit < entry)
- **Report actual count** in metadata (do not hardcode)

**Game-Level Splits** (no data leakage):
- **Deterministic splitting by GAME ID** (not by time or other features)
- Use same split for every parameter combination (ensures fair comparison)
- **Stable seed** controls shuffling for reproducibility
- Default: 70% train / 15% valid / 15% test (configurable)
- **Write split lists to disk** (e.g., `train_games.json`, `valid_games.json`, `test_games.json`) for reproducibility
- **Implementation**: 
  ```python
  # Shuffle game IDs with seed, then split deterministically
  game_ids = sorted(set(all_game_ids))  # Deterministic order
  random.Random(seed).shuffle(game_ids)
  train_end = int(len(game_ids) * train_ratio)
  valid_end = train_end + int(len(game_ids) * valid_ratio)
  train_games = game_ids[:train_end]
  valid_games = game_ids[train_end:valid_end]
  test_games = game_ids[valid_end:]
  # Write to disk for reproducibility
  ```

**Task 1.2**: Parallel execution
- **Implementation**: Use `ThreadPoolExecutor` pattern from `simulation.py`
- Each worker processes one parameter combination across all games in split
- Aggregate metrics per combination per split (train/valid/test)

**Task 1.3**: Metrics to store per combination
- **Primary Metrics** (for plotting + pattern detection):
  - `net_profit_dollars` (fees included if enable_fees=True)
  - `num_trades` (total trades across games in split)
  - `win_rate` (percentage of profitable trades)
  - `avg_net_profit_per_trade` (net_profit_dollars / num_trades)
  - `profit_factor` (gross_profit / abs(gross_loss))
  - `max_drawdown` (maximum peak-to-trough decline)
  - `total_fees` (sum of all trading fees)
  - `avg_hold_time` (optional: average position duration in seconds)
- **Guardrails**:
  - Flag combos where `num_trades < min_trade_count` (still record but mark as invalid)
  - Invalid combos excluded from "best params" selection but kept in results

**Task 1.4**: Results storage
- **CSV Files** (one per split):
  - `grid_results_train.csv`
  - `grid_results_valid.csv`
  - `grid_results_test.csv` (final reporting only; do NOT tune on it)
- **CSV Columns**:
  ```
  entry_threshold, exit_threshold, net_profit_dollars, num_trades, win_rate, 
  avg_net_profit_per_trade, profit_factor, max_drawdown, total_fees, 
  avg_hold_time (optional), is_valid (bool)
  ```
- **is_valid flag**: `False` when `num_trades < min_trade_count` (still recorded but flagged)
- **JSON Files** (with metadata):
  - `grid_results_train.json`
  - `grid_results_valid.json`
  - `grid_results_test.json`
  - Structure:
  ```json
  {
    "metadata": {
      "args": {...},  # All CLI arguments
      "timestamp": "2025-01-27T12:00:00Z",
      "git_hash": "abc123..." (if available),
      "num_games": {"train": 70, "valid": 15, "test": 15},
      "num_combinations": <computed>,  # Actual count after applying constraints
      "search_space": {
        "entry_range": [0.02, 0.10, 0.01],
        "exit_range": [0.00, 0.05, 0.005]
      }
    },
    "results": [
      {
        "entry_threshold": 0.05,
        "exit_threshold": 0.01,
        "net_profit_dollars": 123.45,
        "num_trades": 456,
        "win_rate": 0.52,
        ...
      }
    ]
  }
  ```

**Task 1.5**: Selection logic (for "best params")
- **Use TRAIN for broad ranking**: Identify top N combinations (configurable via `--top-n`, default 10)
- **Use VALIDATION to pick final candidate**: Among top N from train, select best on validation
- **TEST is for one-time final report only**: Do NOT use test for selection (evaluate once after selection)
- **Output**: `final_selection.json`:
  ```json
  {
    "chosen_params": {
      "entry_threshold": 0.06,
      "exit_threshold": 0.02
    },
    "train_metrics": {
      "net_profit_dollars": 150.00,
      "num_trades": 500,
      "win_rate": 0.52,
      "profit_factor": 1.15,
      "max_drawdown": -25.00,
      "total_fees": 45.00,
      ...
    },
    "valid_metrics": {
      "net_profit_dollars": 145.00,
      "num_trades": 480,
      "win_rate": 0.51,
      "profit_factor": 1.14,
      "max_drawdown": -23.00,
      "total_fees": 43.00,
      ...
    },
    "test_metrics": {
      "net_profit_dollars": 148.00,
      "num_trades": 490,
      "win_rate": 0.52,
      "profit_factor": 1.15,
      "max_drawdown": -24.00,
      "total_fees": 44.00,
      ...
    },
    "selection_method": "best_on_valid_among_top_N_train",
    "top_n": 10
  }
  ```

**Task 1.6**: Cost realism defaults and caching
- **CRITICAL**: Grid search defaults to `enable_fees=True`, `slippage_rate=0.0` (realistic costs)
- **Caching keys must include** (to prevent mixing results):
  - `entry_threshold`, `exit_threshold`
  - `enable_fees`, `slippage_rate`
  - `season` (or game list hash if using game list input)
  - `split_seed`
- **Rationale**: Prevents mixing results from different cost assumptions or data splits

### Phase 2: Statistical Analysis

**Task 2.1**: Multiple comparisons correction
- **Implementation**: Benjamini-Hochberg FDR correction
- **Library**: `statsmodels.stats.multitest` or manual implementation
- **Output**: Corrected p-values and significance flags

**Task 2.2**: Performance visualization and pattern detection
- **File**: `scripts/analyze_grid_search_results.py`
- **Input**: Results directory from grid search (contains CSV/JSON files)
- **Output**: PNG plots saved to `output_dir/plots/`
- **Design Pattern**: Visualization Strategy Pattern
- **Algorithm**: 2D visualization of performance surface
- **Big O**: O(k) where k = number of parameter combinations (computed dynamically)
- **Tool**: matplotlib (keep it simple and dependable)

**Required Visualizations** (matplotlib is fine; keep it simple and dependable):

**A) Profit Heatmap** (CORE - Required)
- **Generate separate heatmaps for TRAIN and VALID** (separate PNGs)
- **X-axis**: Entry threshold values
- **Y-axis**: Exit threshold values
- **Color**: `net_profit_dollars`
- **Annotation**: Marker/annotation for chosen params (from `final_selection.json`)
- **Purpose**: Identify optimal regions at a glance
- **Implementation**: `matplotlib.pyplot.imshow()` or `seaborn.heatmap()`
- **Files**: `plots/profit_heatmap_train.png`, `plots/profit_heatmap_valid.png`

**B) Contour Plot** (Optional but helpful)
- **X-axis**: Entry threshold
- **Y-axis**: Exit threshold
- **Contour Lines**: Iso-profit lines (same profit level)
- **Purpose**: Makes "regions" obvious (not just single best point)
- **Implementation**: `matplotlib.pyplot.contour()` or `contourf()`
- **File**: `plots/profit_contour.png` (optional)

**C) Marginal Effects** (Required)
- **Plot 1**: Entry threshold vs. mean profit (averaged across all exit thresholds)
- **Plot 2**: Exit threshold vs. mean profit (averaged across all entry thresholds)
- **Error Bars**: Include std error bars (std across the other axis) if easy
- **Purpose**: Understand which parameter has more impact
- **Implementation**: `matplotlib.pyplot.plot()` with error bars
- **File**: `plots/marginal_effects.png`

**D) Tradeoff Scatter** (Required)
- **X-axis**: `num_trades`
- **Y-axis**: `net_profit_dollars`
- **Color**: Entry threshold (or exit threshold) - shows frequency/threshold relationship
- **Purpose**: Visualize trade-off between trade frequency and profitability
- **Implementation**: `matplotlib.pyplot.scatter()` with color mapping
- **File**: `plots/tradeoff_scatter.png`

**E) Secondary Heatmap** (Required - choose one)
- **Prefer VALID split** for secondary heatmap (more relevant for selection)
- **Option 1**: Profit Factor Heatmap (preferred)
  - X: Entry threshold, Y: Exit threshold, Color: `profit_factor`
  - Helps detect "profit is high but risk is insane" regions
- **Option 2**: Max Drawdown Heatmap
  - X: Entry threshold, Y: Exit threshold, Color: `max_drawdown`
  - Shows risk-adjusted performance
- **File**: `plots/profit_factor_heatmap_valid.png` OR `plots/max_drawdown_heatmap_valid.png`

**Task 2.3**: Pattern detection helpers (lightweight, not over-engineered)
- **Location**: In `analyze_grid_search_results.py`, print a short "pattern summary" to console
- **Design Pattern**: Pattern Recognition / Exploratory Data Analysis
- **Algorithm**: Simple statistical summaries and comparisons
- **Big O**: O(k) where k = number of combinations

**Pattern Summary Output** (printed to console):
```
=== Pattern Detection Summary ===

1. Profit-Positive Region Boundary (roughly):
   - Entry thresholds with profit > 0: [X, Y, Z] (probability units)
   - Exit thresholds with profit > 0: [A, B, C] (probability units)
   - Boundary shape: [convex/concave/irregular]

2. Monotonicity (using marginal curves):
   - Entry threshold: [monotonic increasing/decreasing/non-monotonic]
   - Exit threshold: [monotonic increasing/decreasing/non-monotonic]

3. Robustness Assessment:
   - Broad plateaus (robust regions): Entry=[X-Y], Exit=[A-B] (region within 10% of best on VALID)
   - Sharp peaks (fragile): Entry=[X], Exit=[A] (narrow optimal region)
   - Plateau size: [large/medium/small]

4. Stability Check (Train vs Valid):
   - Top 5 combos on TRAIN:
     1. Entry=X, Exit=Y → Profit=$Z (Train), $W (Valid) [stable/unstable]
     2. Entry=X2, Exit=Y2 → Profit=$Z2 (Train), $W2 (Valid) [stable/unstable]
     3. ...
   - Rank correlation (Train vs Valid): [correlation coefficient]

5. Optimal Region:
   - Best combo: Entry=[X], Exit=[Y]
   - Profit: $Z (Train), $W (Valid), $V (Test)
   - Robust region: Entry=[X1-X2], Exit=[Y1-Y2] (all combos within 10% of best on VALID)
```

**Implementation Details**:
- **Profit-positive boundary**: Find contour where profit = 0 (roughly), describe shape
- **Monotonicity**: Check if profit increases/decreases monotonically with each parameter using marginal effect curves (averaged across other parameter)
- **Robustness**: Identify regions where profit is within 10% of maximum on VALID (plateaus) vs. sharp peaks
- **Stability**: Show top 5 train combos and their valid profits, calculate rank correlation (train vs valid)
- **Optimal region**: Identify all combos within 10% of best on VALID

**Task 2.3**: Statistical tests
- **Pairwise Comparisons**: Compare each combination to baseline (current defaults)
- **Optimality Test**: Is best combination significantly better than baseline?
- **Robustness Check**: Cross-validation or bootstrap confidence intervals

### Phase 3: Results Interpretation

**Task 3.1**: Identify optimal parameters
- **Criteria**: Maximum net profit after costs
- **Constraints**: Minimum sample size (e.g., ≥50 trades)
- **Robustness**: Check if optimal is stable across different game subsets

**Task 3.2**: Pattern analysis and interpretation
- **Goal**: Detect meaningful patterns in grid search results beyond just finding the best point
- **Design Pattern**: Pattern Recognition / Exploratory Data Analysis
- **Algorithm**: Statistical pattern detection on 2D performance surface
- **Big O**: O(k) for pattern analysis where k = number of combinations

**Key Patterns to Detect**:

1. **Optimal Region Pattern**
   - **Question**: Is there a single peak or a plateau of good performance?
   - **Detection**: Look for clusters of high-profit combinations in heatmap
   - **Interpretation**: 
     - Single peak = one optimal strategy
     - Plateau = multiple viable strategies (more robust)
     - Multiple peaks = different strategies for different contexts

2. **Parameter Sensitivity Pattern**
   - **Question**: Which parameter (entry vs. exit) has more impact on performance?
   - **Detection**: Compare marginal effect plots - steeper slope = more sensitive
   - **Interpretation**:
     - Entry threshold more sensitive = selectivity matters most
     - Exit threshold more sensitive = exit timing matters most
     - Both sensitive = need to optimize both carefully

3. **Trade-off Pattern**
   - **Question**: Is there a clear relationship between trade frequency and profitability?
   - **Detection**: Plot net profit vs. number of trades (scatter plot)
   - **Interpretation**:
     - Positive correlation = more trades = more profit (fees not dominant)
     - Negative correlation = fewer trades = more profit (fees dominant)
     - No correlation = trade frequency doesn't predict profit
     - **Pareto Frontier**: Points where you can't improve profit without more trades

4. **Interaction Pattern**
   - **Question**: Do entry and exit thresholds interact (non-additive effects)?
   - **Detection**: Check if contour lines are diagonal (interaction) vs. horizontal/vertical (independent)
   - **Interpretation**:
     - Diagonal contours = thresholds interact (e.g., high entry needs high exit)
     - Horizontal/vertical = thresholds independent (can optimize separately)
   - **Statistical Test**: Two-way ANOVA with interaction term

5. **Robustness Pattern**
   - **Question**: How stable is performance around optimal thresholds?
   - **Detection**: Check contour density - tight contours = sensitive, wide contours = robust
   - **Interpretation**:
     - Robust region = small changes don't hurt much (practical)
     - Sensitive region = need precise thresholds (risky)

6. **Boundary Pattern**
   - **Question**: Where do profitable regions end?
   - **Detection**: Identify profit = 0 contour line in heatmap
   - **Interpretation**: 
     - Clear boundary = well-defined risk zones
     - Fuzzy boundary = uncertainty in optimal thresholds

7. **Baseline Comparison Pattern**
   - **Question**: How much better is optimal vs. current default baseline?
   - **Detection**: Highlight baseline point on heatmap, calculate improvement %
   - **Interpretation**:
     - Large improvement = current thresholds suboptimal
     - Small improvement = current thresholds near-optimal
     - Baseline in optimal region = already well-tuned

8. **Multi-Metric Consistency Pattern**
   - **Question**: Do different metrics (profit, win rate, ROI) agree on optimal?
   - **Detection**: Compare heatmaps for different metrics
   - **Interpretation**:
     - Aligned optima = robust optimal strategy
     - Different optima = need to choose primary metric

**Pattern Detection Workflow**:

1. **Generate Visualizations** (Task 2.2)
   - Create all required plots (heatmap, marginal effects, trade-offs, etc.)

2. **Visual Inspection**
   - Look for obvious patterns (peaks, plateaus, gradients, boundaries)
   - Note any surprising or counter-intuitive results

3. **Quantitative Analysis**
   - Calculate correlation coefficients (entry vs. profit, exit vs. profit)
   - Test for interactions (ANOVA with interaction term)
   - Identify Pareto frontier (efficient trade-off points)

4. **Statistical Validation**
   - Apply FDR correction to identify significant improvements
   - Bootstrap confidence intervals around optimal thresholds
   - Cross-validation to check robustness

5. **Interpretation**
   - Translate patterns into actionable insights
   - Identify optimal threshold ranges (not just single point)
   - Note any caveats or limitations

**Task 3.3**: Recommendations
- **Optimal Thresholds**: Best entry/exit combination
- **Confidence Intervals**: Uncertainty around optimal values
- **Practical Considerations**: Balance between optimality and robustness

### Phase 4: UI/UX Enhancement - Pre-built Threshold Presets (Future Work)

**Note**: UI preset implementation deferred. Focus on grid search + graphs + pattern visibility first.

**Status**: Future enhancement after grid search results are available

**Task 4.1**: Design preset strategy categories
- **Purpose**: Provide users with pre-configured threshold combinations based on trading strategies
- **Design Pattern**: Strategy Pattern (different preset strategies)
- **Algorithm**: Simple value mapping (preset selection → threshold values)
- **Big O**: O(1) for preset selection

**Proposed Preset Strategies**:

1. **Conservative (Low Frequency, High Selectivity)**
   - Entry: 8 cents (0.08)
   - Exit: 1 cent (0.01)
   - **Rationale**: Fewer trades, higher edge per trade, lower total fees
   - **Use Case**: Capital preservation, lower risk tolerance

2. **Balanced (Current Default)**
   - Entry: 5 cents (0.05)
   - Exit: 2 cents (0.02)
   - **Rationale**: Current baseline, moderate trade frequency
   - **Use Case**: General purpose, balanced risk/reward

3. **Aggressive (High Frequency, Lower Selectivity)**
   - Entry: 3 cents (0.03)
   - Exit: 1 cent (0.01)
   - **Rationale**: More trades, capture smaller divergences, higher fees
   - **Use Case**: Maximize trade opportunities, higher risk tolerance

4. **Quick Profit (Fast Exits)**
   - Entry: 5 cents (0.05)
   - Exit: 0 cents (0.00) - exit on convergence
   - **Rationale**: Exit immediately when ESPN/Kalshi converge
   - **Use Case**: Capture quick profits, minimize holding time

5. **Hold Longer (Patient Strategy)**
   - Entry: 6 cents (0.06)
   - Exit: 3 cents (0.03)
   - **Rationale**: Hold positions longer, wait for larger convergence
   - **Use Case**: Patient trading, allow more time for edge to play out

6. **Grid Search Optimal** (after Phase 3 completes)
   - Entry: [TBD from grid search results]
   - Exit: [TBD from grid search results]
   - **Rationale**: Data-driven optimal thresholds from grid search
   - **Use Case**: Maximum profitability based on historical data

**Task 4.2**: Implement preset selector UI
- **Location**: `webapp/static/templates/simulation.html` and `game-detail.html`
- **UI Component**: Dropdown/select menu or button group
- **Placement**: Above or next to entry/exit threshold inputs
- **Behavior**: 
  - Selecting preset auto-populates entry/exit threshold fields
  - "Custom" option allows manual entry
  - Preset selection clears when user manually edits thresholds

**UI Mockup**:
```html
<div class="sim-input-group">
    <label for="thresholdPreset">Threshold Preset:</label>
    <select id="thresholdPreset">
        <option value="custom">Custom</option>
        <option value="conservative">Conservative (8c/1c)</option>
        <option value="balanced" selected>Balanced (default)</option>
        <option value="aggressive">Aggressive (3c/1c)</option>
        <option value="quick-profit">Quick Profit (5c/0c)</option>
        <option value="hold-longer">Hold Longer (6c/3c)</option>
        <option value="optimal">Grid Search Optimal (TBD)</option>
    </select>
</div>
```

**Task 4.3**: JavaScript implementation
- **File**: `webapp/static/js/simulation.js` and `game-simulation.js`
- **Functionality**:
  - Preset selection handler updates entry/exit threshold inputs
  - Manual threshold editing switches preset to "Custom"
  - Preset values stored in configuration object
  - Preset descriptions shown in tooltip/help text

**Implementation Example**:
```javascript
const THRESHOLD_PRESETS = {
    conservative: { entry: 8, exit: 1, label: "Conservative (8c/1c)" },
    balanced: { entry: 0.05, exit: 0.02, label: "Balanced (default)" },
    aggressive: { entry: 3, exit: 1, label: "Aggressive (3c/1c)" },
    quickProfit: { entry: 5, exit: 0, label: "Quick Profit (5c/0c)" },
    holdLonger: { entry: 6, exit: 3, label: "Hold Longer (6c/3c)" },
    optimal: { entry: null, exit: null, label: "Grid Search Optimal" } // Loaded from API
};

function applyPreset(presetName) {
    const preset = THRESHOLD_PRESETS[presetName];
    if (preset && preset.entry !== null) {
        document.getElementById('entryThreshold').value = preset.entry;
        document.getElementById('exitThreshold').value = preset.exit;
    }
}
```

**Task 4.4**: Dynamic preset updates
- **Source**: Grid search results (after Phase 3)
- **Mechanism**: API endpoint or configuration file stores optimal thresholds
- **Update Frequency**: After each grid search run
- **Fallback**: If optimal not available, show "Optimal (TBD)" or hide option

**API Endpoint** (optional):
- `GET /api/simulation/optimal-thresholds`
- Returns: `{ "entry_threshold": 0.06, "exit_threshold": 0.02, "source": "grid_search_v1", "date": "2025-01-27" }`
- Frontend loads and updates preset on page load

**Pros**:
- **User-Friendly**: Non-technical users can try different strategies easily
- **Exploration**: Encourages experimentation with different threshold combinations
- **Best Practices**: Presets encode common trading strategies
- **Data-Driven**: "Optimal" preset leverages grid search results

**Cons**:
- **Maintenance**: Need to update presets if grid search finds better values
- **Over-Simplification**: May hide nuance of threshold selection
- **Custom Override**: Users can still manually edit, which may confuse preset state

**Recommendation**: Implement presets as **convenience feature**, not replacement for manual entry. Always allow "Custom" option and make it clear when thresholds are manually edited.

---

## Expected Outcomes

### Scenario 1: Clear Optimal Thresholds

**Outcome**: Single combination significantly outperforms others  
**Action**: Update default thresholds to optimal values  
**Confidence**: High if FDR-corrected p-value < 0.05

### Scenario 2: Flat Performance Surface

**Outcome**: Net profit similar across many combinations  
**Implication**: Thresholds not the limiting factor  
**Action**: Focus on signal refinement instead

### Scenario 3: Trade-off Pattern

**Outcome**: Clear trade-off between trade frequency and profitability  
**Example**: Higher entry threshold = fewer trades = better net profit  
**Action**: Choose threshold based on risk tolerance and capital constraints

### Scenario 4: No Significant Improvement

**Outcome**: No combination beats baseline after correction  
**Implication**: Current thresholds already near-optimal OR signal quality is limiting factor  
**Action**: Prioritize signal refinement over hyperparameter tuning

---

## Technical Considerations

### Computational Cost

**Single Simulation**: ~2-5 seconds per game (100 games = 3-8 minutes)  
**Grid Search**: N combinations × 3-8 minutes = **variable time** for 100 games (depends on parameter ranges and constraints)  
**Optimization**: Parallel execution reduces to ~1-2 hours with 8 workers

**Recommendation**: Start with smaller sample (50 games) to validate approach, then scale to 100-500 games.

### Overfitting Risk

**Problem**: Optimizing on same dataset used for evaluation  
**Mitigation**:
- **Train/Test Split**: Use 70% games for optimization, 30% for validation
- **Cross-Validation**: K-fold cross-validation across games
- **Out-of-Sample Testing**: Test optimal parameters on future games

**Recommendation**: Use **train/test split** for initial grid search, then validate on held-out games.

### Baseline Comparison

**Current Baseline**: Entry=5c, Exit=2c  
**Comparison**: All combinations vs. baseline  
**Significance**: Use paired t-test or Wilcoxon signed-rank test  
**Correction**: Apply FDR correction to all comparisons

---

## Code Structure

### File Structure

```
scripts/
  grid_search_hyperparameters.py    # Grid search runner (CLI)
  analyze_grid_search_results.py     # Visualization and pattern detection

grid_search_results/                 # Output directory (created by script)
  grid_results_train.csv
  grid_results_train.json
  grid_results_valid.csv
  grid_results_valid.json
  grid_results_test.csv
  grid_results_test.json
  final_selection.json
  plots/
    profit_heatmap.png
    profit_contour.png
    marginal_effects.png
    tradeoff_scatter.png
    profit_factor_heatmap.png (or max_drawdown_heatmap.png)
```

### Dependencies

**Required Python packages**:
- `matplotlib` (for plotting)
- `pandas` (for CSV handling)
- `numpy` (for numerical operations)
- `seaborn` (optional, for nicer heatmaps)

**Existing dependencies** (already in codebase):
- `psycopg` (database connection)
- `simulate_trading_strategy` module (simulation logic)

### API Endpoint (Optional)

**Endpoint**: `POST /api/simulation/grid-search`  
**Purpose**: Run grid search via web interface  
**Parameters**: Same as bulk simulation + parameter ranges  
**Response**: Grid search results + visualizations

**Pros**: Interactive exploration, no command-line needed  
**Cons**: Long-running request, may timeout  
**Recommendation**: Implement as background job with progress tracking

---

## Deliverables

### Required Scripts

1. **`scripts/grid_search_hyperparameters.py`**
   - **CLI args**: season OR game-list path, entry/exit min/max/step, workers, seed, enable_fees, slippage_rate, min_trade_count, output_dir, train/valid/test ratios
   - **Deterministic split by GAME ID** using seed; same split used for every hyperparam combo
   - **Write split lists to disk** (train_games.json, valid_games.json, test_games.json)
   - **For each (entry, exit) combo**: run simulation on train/valid/test separately, aggregate metrics
   - **Output**: grid_results_train.csv/.json, grid_results_valid.csv/.json, grid_results_test.csv/.json (report-only)
   - **Store per combo**: net_profit_dollars, num_trades, win_rate, avg_net_profit_per_trade, profit_factor, max_drawdown, total_fees, optional avg_hold_time, plus is_valid flag when num_trades < min_trade_count
   - **Selection logic**: rank on TRAIN, choose final params using VALID among top N train combos (configurable), then evaluate once on TEST
   - **Output**: final_selection.json with metrics for all splits and selection method

2. **`scripts/analyze_grid_search_results.py`**
   - **Input**: results dir from grid search
   - **Output**: plots to output_dir/plots/
   - **Required plots** (matplotlib is fine):
     - A) Profit heatmap for TRAIN and VALID (separate PNGs), with chosen params marked
     - B) Marginal effect plots (entry→mean profit, exit→mean profit) with std error bars if easy
     - C) Tradeoff scatter (num_trades vs net_profit_dollars), color by entry (or exit)
     - D) One secondary heatmap: profit_factor OR max_drawdown (prefer VALID)
     - (Contour plot optional)
   - **Print pattern summary**:
     - profit-positive region boundary (roughly)
     - monotonicity of profit vs entry/exit (using marginal curves)
     - robust plateau vs sharp peak (e.g., region within 10% of best on VALID)
     - stability: show top 5 train combos and their valid profits + rank correlation (train vs valid)

### Output Files

**CSV/JSON Results** (per split):
- `grid_results_train.csv` / `.json`
- `grid_results_valid.csv` / `.json`
- `grid_results_test.csv` / `.json`

**Selection Output**:
- `final_selection.json` (chosen params + metrics on all splits)

**Visualizations** (PNG files):
- `plots/profit_heatmap.png` (required)
- `plots/profit_contour.png` (optional)
- `plots/marginal_effects.png` (required)
- `plots/tradeoff_scatter.png` (required)
- `plots/profit_factor_heatmap.png` OR `plots/max_drawdown_heatmap.png` (required)

### Documentation

**README Section**: "How to run grid search + generate plots"

Add a small README section or create `GRID_SEARCH.md` with exact commands:

```markdown
## Grid Search Hyperparameter Optimization

### Running Grid Search

1. **Run grid search** (tests all valid parameter combinations):
   ```bash
   python scripts/grid_search_hyperparameters.py \
     --season "2025-26" \
     --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
     --workers 8 \
     --seed 42 \
     --enable-fees \
     --slippage-rate 0.0 \
     --min-trade-count 200 \
     --output-dir grid_search_results/
   ```
   
   Or use a game list file:
   ```bash
   python scripts/grid_search_hyperparameters.py \
     --game-list path/to/game_ids.json \
     --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
     --workers 8 \
     --seed 42 \
     --enable-fees \
     --output-dir grid_search_results/
   ```

2. **Generate plots and pattern summary**:
   ```bash
   python scripts/analyze_grid_search_results.py \
     --results-dir grid_search_results/ \
     --output-dir grid_search_results/
   ```

3. **Check results**:
   - View plots in `grid_search_results/plots/`
   - Check `final_selection.json` for chosen parameters
   - Review pattern summary printed to console

### Interpreting Train/Valid/Test Usage

- **Train split**: Used for broad ranking of combinations (identify top N)
- **Validation split**: Used to select final candidate from top N train combos (do NOT tune on test)
- **Test split**: One-time final report only (do NOT use for selection or tuning)

### Key Output Files

- `grid_results_train.csv` / `.json`: Results on training set (for ranking)
- `grid_results_valid.csv` / `.json`: Results on validation set (for selection)
- `grid_results_test.csv` / `.json`: Results on test set (final reporting only)
- `final_selection.json`: Chosen parameters and metrics on all splits
- `train_games.json`, `valid_games.json`, `test_games.json`: Game ID splits (for reproducibility)
- `plots/profit_heatmap_train.png`, `plots/profit_heatmap_valid.png`: Core visualizations
- `plots/marginal_effects.png`: Parameter sensitivity
- `plots/tradeoff_scatter.png`: Frequency vs. profitability trade-off
- `plots/profit_factor_heatmap_valid.png`: Risk-adjusted performance
```

## Next Steps

### Immediate Actions

1. **Implement `scripts/grid_search_hyperparameters.py`**
   - CLI argument parsing
   - Grid generation with constraints (entry > 0, exit >= 0, exit < entry)
   - Deterministic train/valid/test splits by game ID
   - Parallel simulation execution
   - CSV/JSON output per split
   - `final_selection.json` generation

2. **Implement `scripts/analyze_grid_search_results.py`**
   - Read CSV/JSON results
   - Generate required visualizations (heatmap, contour, marginal, scatter, secondary)
   - Pattern detection summary (profit boundary, monotonicity, robustness, stability)
   - Save plots to output directory

3. **Run initial grid search** (50-100 games, all valid combinations from parameter ranges)
   - Validate approach
   - Estimate computational cost
   - Check for obvious patterns
   - Verify no data leakage (splits are independent)

4. **Review visualizations and patterns**
   - Identify optimal regions (not just single best point)
   - Check parameter sensitivity
   - Validate robustness and stability

### Follow-up Actions

5. **Update default thresholds** (if significant improvement found)
   - Update `simulation.py` defaults
   - Update web UI defaults (if presets are implemented)

6. **Signal refinement** (parallel track)
   - Improve ESPN probability calibration
   - Add new features/parameters
   - Re-run grid search with improved signal

---

## References

### Current Implementation

- **Simulation Logic**: `scripts/simulate_trading_strategy.py:758-1065`
- **Default Thresholds**: `webapp/api/endpoints/simulation.py:54-55`
- **Cost Calculation**: `scripts/simulate_trading_strategy.py:547-729`

### Statistical Methods

- **Bonferroni Correction**: Controls family-wise error rate
- **Benjamini-Hochberg FDR**: Less conservative, better for exploration
- **Grid Search**: Exhaustive parameter optimization

### Design Patterns

- **Grid Search**: Exhaustive Search Pattern
- **Parallel Execution**: Map-Reduce Pattern (from `simulation.py`)
- **Statistical Analysis**: Strategy Pattern (different correction methods)

---

## Summary

The data scientist's feedback translates to:

1. **Current State**: Strategy shows edge but fees erode profits
2. **Short-term Solution**: Grid search on entry/exit thresholds to find optimal values
3. **Long-term Solution**: Improve ESPN signal quality/calibration
4. **Statistical Rigor**: Correct for multiple comparisons (FDR/Bonferroni)
5. **Pattern Discovery**: Look for optimal parameter regions, not just single best values

**Updated Guidance**: "do a hyperparam grid search on the entry/exit, then graph the performance to detect patterns"

This emphasizes:
- **Grid Search**: Systematic exploration of parameter space (entry × exit thresholds)
- **Performance Graphing**: Visualize results with heatmaps, contour plots, marginal effects
- **Pattern Detection**: Identify optimal regions, parameter sensitivity, trade-offs, and interactions

**Key Insight**: Grid search is a **systematic way to optimize hyperparameters** with **reproducible, honest evaluation** (no data leakage). The goal is to **graph performance and detect patterns** to find robust parameter regions, not just identify a single best point.

**Critical Requirements**:
- **No Data Leakage**: Deterministic train/valid/test splits by game ID (70/15/15)
- **Cost Realism**: Default to `enable_fees=True` (realistic trading costs)
- **Reproducibility**: Seed-controlled splits, git hash in metadata, full CLI args recorded
- **Pattern Detection**: Graph performance to identify regions, gradients, trade-offs (not just "pick best cell")
- **Honest Evaluation**: Use train for ranking, valid for selection, test for final report only

**Visualization is Critical**: Performance graphs are essential for:
- **Identifying optimal regions** (not just single best point) - heatmaps + contour plots
- **Understanding parameter sensitivity** (which thresholds matter most) - marginal effects
- **Detecting trade-offs** (frequency vs. profitability) - scatter plots
- **Finding robust solutions** (stable across parameter variations) - pattern detection summary
- **Validating results** (checking for spurious patterns) - train/valid stability check

**Deliverables**:
1. `scripts/grid_search_hyperparameters.py` - CLI-based grid search runner
2. `scripts/analyze_grid_search_results.py` - Visualization and pattern detection
3. CSV/JSON results per split (train/valid/test)
4. PNG plots (heatmap, contour, marginal, scatter, secondary)
5. Pattern detection summary (printed to console)
6. `final_selection.json` (chosen params + metrics)

**Next Step**: 
1. Implement `scripts/grid_search_hyperparameters.py` with CLI args, splits, and parallel execution
2. Implement `scripts/analyze_grid_search_results.py` with required visualizations
3. Run initial grid search on 50-100 games
4. Generate plots and pattern detection summary
5. Review results and identify optimal threshold regions

