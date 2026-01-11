# Grid Search Output Guide: What You Get and What To Do With It

**Date**: 2025-01-27  
**Purpose**: Explain what the grid search CLI produces and how to use the results

---

## What Happens When You Run Grid Search

### Step 1: Run the Grid Search CLI

```bash
python scripts/grid_search_hyperparameters.py \
  --season "2025-26" \
  --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
  --workers 8 \
  --seed 42 \
  --enable-fees \
  --output-dir grid_search_results/
```

**What happens**:
- Tests ~99 combinations of entry/exit thresholds
- Runs simulation on each combination across train/valid/test splits
- Takes 1-3 hours (depending on number of games)
- Shows progress: "Completed 10/99 combinations", etc.

---

## What You Get: Output Files

### 1. CSV Files (Easy to Open in Excel/Google Sheets)

**`grid_results_train.csv`** - Results on training set
- One row per threshold combination
- Columns: `entry_threshold`, `exit_threshold`, `net_profit_dollars`, `num_trades`, `win_rate`, `profit_factor`, `max_drawdown`, `total_fees`, `is_valid`

**Example row**:
```
entry_threshold,exit_threshold,net_profit_dollars,num_trades,win_rate,profit_factor,max_drawdown,total_fees,is_valid
0.05,0.02,123.45,456,0.52,1.15,-25.00,45.00,True
0.06,0.02,145.67,389,0.54,1.18,-22.00,38.00,True
0.07,0.01,98.23,312,0.51,1.12,-30.00,31.00,True
```

**`grid_results_valid.csv`** - Results on validation set (for selection)
**`grid_results_test.csv`** - Results on test set (final report only)

### 2. JSON Files (With Metadata)

**`grid_results_train.json`** - Same data as CSV, plus metadata:
```json
{
  "metadata": {
    "args": {...},  // All CLI arguments you used
    "timestamp": "2025-01-27T12:00:00Z",
    "git_hash": "abc123...",
    "num_games": {"train": 70, "valid": 15, "test": 15},
    "num_combinations": 99,
    "search_space": {
      "entry_range": [0.02, 0.10, 0.01],
      "exit_range": [0.00, 0.05, 0.005]
    }
  },
  "results": [
    {
      "entry_threshold": 0.05,
      "exit_threshold": 0.02,
      "net_profit_dollars": 123.45,
      "num_trades": 456,
      "win_rate": 0.52,
      ...
    }
  ]
}
```

### 3. Split Lists (For Reproducibility)

**`train_games.json`** - List of game IDs used for training
**`valid_games.json`** - List of game IDs used for validation  
**`test_games.json`** - List of game IDs used for testing

**Why this matters**: Same games = same results (reproducible)

### 4. Final Selection

**`final_selection.json`** - The "winner" combination:
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
    ...
  },
  "valid_metrics": {
    "net_profit_dollars": 145.00,
    "num_trades": 480,
    "win_rate": 0.51,
    ...
  },
  "test_metrics": {
    "net_profit_dollars": 148.00,
    "num_trades": 490,
    "win_rate": 0.52,
    ...
  },
  "selection_method": "best_on_valid_among_top_10_train"
}
```

**What this tells you**: The optimal thresholds found by the grid search

---

## Step 2: Generate Visualizations

```bash
python scripts/analyze_grid_search_results.py \
  --results-dir grid_search_results/ \
  --output-dir grid_search_results/
```

### What You Get: PNG Images

**`plots/profit_heatmap_train.png`** - Heatmap showing profit for each combination (TRAIN)
- **X-axis**: Entry threshold (2c to 10c)
- **Y-axis**: Exit threshold (0c to 5c)
- **Color**: Net profit (green = high profit, red = losses)
- **Star marker**: Chosen optimal parameters

**`plots/profit_heatmap_valid.png`** - Same but for VALIDATION set

**`plots/marginal_effects.png`** - Two plots:
- Left: Entry threshold vs. average profit (shows if higher entry = better)
- Right: Exit threshold vs. average profit (shows if higher exit = better)
- **Error bars**: Show uncertainty

**`plots/tradeoff_scatter.png`** - Scatter plot:
- **X-axis**: Number of trades (frequency)
- **Y-axis**: Net profit (dollars)
- **Color**: Entry threshold
- **Shows**: Trade-off between trading frequency and profitability

**`plots/profit_factor_heatmap_valid.png`** - Risk-adjusted performance
- Shows profit factor (gross profit / gross loss)
- Helps identify "high profit but risky" regions

### What You Get: Pattern Summary (Printed to Console)

```
======================================================================
PATTERN DETECTION SUMMARY
======================================================================

1. Profit-Positive Region Boundary (roughly):
   - Entry thresholds with profit > 0: [0.05, 0.06, 0.07, 0.08]
   - Exit thresholds with profit > 0: [0.00, 0.01, 0.02]
   - Boundary shape: convex

2. Monotonicity (using marginal curves):
   - Entry threshold: monotonic increasing
   - Exit threshold: non-monotonic

3. Robustness Assessment:
   - Type: broad_plateau
   - Entry range: (0.06, 0.08)
   - Exit range: (0.01, 0.03)
   - Plateau size: 12 combinations (medium)

4. Stability Check (Train vs Valid):
   - Top 5 combos on TRAIN:
     1. Entry=0.07, Exit=0.02 → Profit=$150.00 (Train), $145.00 (Valid) [stable]
     2. Entry=0.06, Exit=0.02 → Profit=$148.00 (Train), $147.00 (Valid) [stable]
     ...
   - Rank correlation (Train vs Valid): 0.85

5. Optimal Region:
   - Best combo: Entry=0.07, Exit=0.02
   - Profit: $150.00 (Train), $145.00 (Valid), $148.00 (Test)
   - Robust region: Entry=(0.06, 0.08), Exit=(0.01, 0.03)
```

---

## How This Helps You

### 1. **Find Optimal Thresholds**
- **Before**: Using default thresholds (entry=5c, exit=2c) - might not be optimal
- **After**: Know the best thresholds (e.g., entry=7c, exit=2c) based on data

### 2. **Understand Trade-offs**
- **Heatmaps**: See entire performance surface - are there multiple good regions?
- **Tradeoff plot**: Does fewer trades (more selective) = better profit?
- **Marginal effects**: Which parameter matters more - entry or exit?

### 3. **Identify Robust Regions**
- **Pattern summary**: Finds stable regions (plateaus) vs fragile peaks
- **Example**: "Entry thresholds 6-8 cents work well" (robust) vs "Entry=7.2 cents is best" (fragile)
- **Why it matters**: Robust regions work even if you're slightly off

### 4. **Validate Strategy**
- **Stability check**: Do top train combos also do well on validation?
- **High rank correlation**: Good sign (strategy is stable)
- **Low rank correlation**: Bad sign (might be overfitting)

### 5. **Account for Fees**
- **All results use `enable_fees=True`**: Realistic trading costs
- **`total_fees` column**: See how much fees cost per combination
- **Net profit**: Only profitable combinations after fees are considered "good"

---

## What To Do After Getting Results

### Immediate Actions

#### 1. **Look at the Visualizations**
- Open `plots/profit_heatmap_valid.png` in an image viewer
- **Look for**: Green regions (profitable), red regions (losses)
- **Check**: Is there a clear optimal region or just random noise?

#### 2. **Read the Pattern Summary**
- **Profit-positive boundary**: Where does it become profitable?
- **Robustness**: Is there a broad plateau (good) or sharp peak (risky)?
- **Stability**: Do train and valid results agree?

#### 3. **Check `final_selection.json`**
- **Chosen parameters**: What thresholds were selected?
- **Metrics on all splits**: How did it perform on train/valid/test?
- **If test profit is much lower**: Might be overfitting (bad sign)

### Decision Making

#### Scenario A: Clear Optimal Region Found
**What you see**:
- Heatmap shows clear green region (e.g., entry 6-8c, exit 1-3c)
- Pattern summary shows "broad_plateau"
- High rank correlation (train vs valid)

**What to do**:
1. ✅ **Update default thresholds** to optimal values from `final_selection.json`
2. ✅ **Use the robust region** - any threshold in that range should work
3. ✅ **Test on new games** - see if it generalizes

#### Scenario B: No Clear Pattern / All Losses
**What you see**:
- Heatmap is mostly red (losses)
- Pattern summary shows "none" for profit-positive boundary
- Low or negative profits across all combinations

**What to do**:
1. ⚠️ **Current thresholds aren't the problem** - signal quality is the issue
2. ⚠️ **Focus on signal refinement** (improving ESPN model) instead
3. ⚠️ **Grid search won't help** if the signal itself is bad

#### Scenario C: Fragile Peak (Sharp Peak, Not Robust)
**What you see**:
- Pattern summary shows "sharp_peak" (only 1-2 combinations work)
- Low rank correlation (train vs valid don't agree)
- Small changes in thresholds cause big drops in profit

**What to do**:
1. ⚠️ **Be cautious** - optimal thresholds might not generalize
2. ⚠️ **Test on more games** - might need larger sample
3. ⚠️ **Consider signal refinement** - fragile peaks suggest signal issues

#### Scenario D: Trade-off Found
**What you see**:
- Tradeoff scatter shows clear relationship (e.g., fewer trades = more profit)
- Marginal effects show entry threshold matters more than exit

**What to do**:
1. ✅ **Use higher entry threshold** (more selective = better)
2. ✅ **Exit threshold less important** - can use simpler exit rule
3. ✅ **Focus optimization on entry threshold** (exit doesn't matter much)

### Next Steps Based on Results

#### If Results Are Good (Profitable, Robust, Stable):
1. **Update simulation defaults**:
   - Change default entry/exit thresholds in `simulate_trading_strategy.py`
   - Update web UI defaults
2. **Add preset to UI** (future work):
   - Create "Grid Search Optimal" preset using `final_selection.json`
3. **Monitor performance**:
   - Run grid search periodically (monthly?) to check if optimal thresholds change
   - Test on new games as they come in

#### If Results Are Bad (Losses, No Pattern):
1. **Signal refinement** (long-term):
   - Improve ESPN probability model
   - Add new features/parameters
   - Re-calibrate predictions
2. **Re-run grid search** after signal improvements
3. **Consider different strategies**:
   - Maybe divergence trading isn't viable with current signal
   - Try other approaches

#### If Results Are Mixed (Some Profit, But Fragile):
1. **Test on larger sample**:
   - Run grid search on more games (200+ instead of 50-100)
   - More data = more reliable results
2. **Be conservative**:
   - Use thresholds from robust region (not sharp peak)
   - Accept slightly lower profit for more stability
3. **Monitor closely**:
   - Check if results hold up on new games
   - Be ready to adjust if performance degrades

---

## Example Workflow

### Step 1: Run Grid Search (1-3 hours)
```bash
python scripts/grid_search_hyperparameters.py \
  --season "2025-26" \
  --enable-fees \
  --output-dir grid_search_results/
```

### Step 2: Generate Visualizations (30 seconds)
```bash
python scripts/analyze_grid_search_results.py \
  --results-dir grid_search_results/
```

### Step 3: Review Results (15 minutes)
1. Open `plots/profit_heatmap_valid.png` - look for green regions
2. Read pattern summary from console output
3. Check `final_selection.json` for chosen thresholds

### Step 4: Make Decision (Based on results)
- **If good**: Update defaults, use optimal thresholds
- **If bad**: Focus on signal refinement
- **If mixed**: Test on more games, be conservative

### Step 5: Implement Changes (If needed)
- Update code defaults
- Test on new games
- Monitor performance

---

## Key Metrics to Watch

### Most Important:
1. **`net_profit_dollars`** (VALID) - After fees, is it profitable?
2. **Robustness** - Is there a stable region or fragile peak?
3. **Stability** - Do train and valid agree?

### Secondary:
4. **`num_trades`** - How many trades? (More = more fees)
5. **`win_rate`** - What % of trades are profitable?
6. **`profit_factor`** - Risk-adjusted metric (gross profit / gross loss)
7. **`max_drawdown`** - Worst losing streak

---

## Common Questions

**Q: What if all combinations lose money?**
A: Thresholds aren't the problem - signal quality is. Focus on improving ESPN model.

**Q: What if there's no clear pattern?**
A: Either need more games (larger sample) or signal isn't predictive enough.

**Q: Should I use train, valid, or test results?**
A: Use VALID for selection (that's what `final_selection.json` does). TEST is for final reporting only.

**Q: How often should I run grid search?**
A: Periodically (monthly?) or when you improve the signal. Not every day.

**Q: Can I trust the results?**
A: Check stability (train vs valid correlation). High correlation = more trustworthy. Also check if test results match valid (good sign).

---

## Summary

**What grid search gives you**:
- ✅ Optimal threshold values (from `final_selection.json`)
- ✅ Visual performance surface (heatmaps)
- ✅ Pattern insights (robust regions, trade-offs)
- ✅ Validation (train/valid/test methodology)

**What to do with it**:
1. **If good**: Update defaults, use optimal thresholds
2. **If bad**: Focus on signal refinement
3. **If mixed**: Test more, be conservative

**Bottom line**: Grid search tells you if thresholds are the problem (fixable) or if signal quality is the problem (needs long-term work).

