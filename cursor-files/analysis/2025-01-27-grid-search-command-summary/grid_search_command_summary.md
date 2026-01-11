# Grid Search Command Summary

## Command Run:
```bash
python scripts/grid_search_hyperparameters.py \
     --season "2025-26" \             
     --verbose \                   
     --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
     --workers 8 \
     --seed 42 \
     --enable-fees \
     --slippage-rate 0.0 \
     --min-trade-count 200 \
     --output-dir grid_search_results/
```

## What This Does (In Plain English):

### **Data Selection:**
- **Season:** Testing on all games from the 2025-26 NBA season
- **Verbose logging:** Enabled (shows detailed debug information during execution)

### **Parameter Grid Search:**
We're testing different combinations of entry and exit thresholds:

- **Entry Threshold Range:** 0.02 to 0.10 (2% to 10% probability divergence)
  - **Step size:** 0.01 (testing every 1% increment)
  - **Total entry values:** 9 values (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10)

- **Exit Threshold Range:** 0.00 to 0.05 (0% to 5% probability divergence)
  - **Step size:** 0.005 (testing every 0.5% increment)
  - **Total exit values:** 11 values (0.000, 0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.035, 0.040, 0.045, 0.050)

- **Total Combinations:** 9 × 11 = **99 parameter combinations** (minus invalid ones where exit >= entry)

### **Execution Settings:**
- **Parallel Workers:** 8 threads running simulations simultaneously
- **Random Seed:** 42 (ensures reproducible, deterministic game splits)

### **Trading Costs:**
- **Fees:** Enabled (Kalshi trading fees are included in P&L calculations)
- **Slippage:** 0.0% (no slippage cost applied)

### **Validation Criteria:**
- **Minimum Trades:** A parameter combination must generate at least 200 trades to be considered valid

### **Output:**
- **Results Directory:** `grid_search_results/`
  - Contains CSV/JSON files with results for train/valid/test splits
  - Includes final parameter selection and metadata

---

## What Gets Tested:

For each of the ~99 parameter combinations:
1. **Train Set (70% of games):** Used to rank combinations by profit
2. **Validation Set (15% of games):** Used to select final parameters from top train performers
3. **Test Set (15% of games):** Used for final evaluation only (no tuning)

Each combination runs the full trading simulation across all games in each split, calculating:
- Net profit (with fees)
- Number of trades
- Win rate
- Profit factor
- Max drawdown
- Average hold time
- And more...

---

## Expected Runtime:

With 8 workers and ~99 combinations, and assuming:
- ~100-200 games per season
- ~1-10 seconds per game (depending on database query performance)
- 3 splits per combination (train/valid/test)

**Estimated time:** 2-4 hours (depending on database performance and number of games)

---

## What to Do After:

1. **Wait for completion** - The script will output results to `grid_search_results/`
2. **Generate visualizations:**
   ```bash
   python scripts/analyze_grid_search_results.py \
       --results-dir grid_search_results/ \
       --output-dir grid_search_results/
   ```
3. **Review the plots** - Heatmaps, marginal effects, tradeoff scatter plots
4. **Check `final_selection.json`** - See which parameters were selected and their performance

