# Run All 4 Models - Full Dataset

Commands to run grid search for all 4 win probability models on the full 2025-26 season dataset.

## Prerequisites

Make sure you're in the project directory:
```bash
cd /Users/adamvoliva/Code/bball
```

## Commands

**Note**: Output files are automatically saved to `data/grid_search/{cache_key}/` based on parameters. No need to specify `--output-dir`.

### Logistic Regression + Platt
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8
```

### Logistic Regression + Isotonic
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_isotonic \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8
```

### CatBoost + Platt
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_platt \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8
```

### CatBoost + Isotonic
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_isotonic \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8
```

## Run All 4 Models Sequentially

Copy and paste this to run all 4 models one after another:

```bash
# LogReg + Platt
python3 scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name logreg_platt --entry-min 0.02 --entry-max 0.20 --entry-step 0.01 --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 --workers 8

# LogReg + Isotonic
python3 scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name logreg_isotonic --entry-min 0.02 --entry-max 0.20 --entry-step 0.01 --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 --workers 8

# CatBoost + Platt
python3 scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name catboost_platt --entry-min 0.02 --entry-max 0.20 --entry-step 0.01 --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 --workers 8

# CatBoost + Isotonic
python3 scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name catboost_isotonic --entry-min 0.02 --entry-max 0.20 --entry-step 0.01 --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 --workers 8
```

## Compare Results

After all 4 models complete, compare results:

```bash
python3 << 'EOF'
import json
from pathlib import Path

base_dir = Path("data/grid_search")
print("\n=== All Grid Search Results ===")
print(f"{'Directory':<50} {'Model':<20} {'Test Profit':<15} {'Trades':<10} {'Win Rate':<10}")
print("-" * 105)

# Find all result directories
for result_dir in sorted(base_dir.glob("*/")):
    final_selection = result_dir / "final_selection.json"
    train_json = result_dir / "grid_results_train.json"
    
    if final_selection.exists() and train_json.exists():
        try:
            with open(final_selection) as f:
                final_data = json.load(f)
            
            with open(train_json) as f:
                train_data = json.load(f)
                metadata = train_data.get('metadata', {})
            
            # Get model name from metadata (check both direct and in args)
            model_name = metadata.get('model_name') or metadata.get('args', {}).get('model_name', 'ESPN (default)')
            
            # Get test metrics
            test_metrics = final_data.get('test_metrics', {})
            profit = test_metrics.get('net_profit_dollars', 'N/A')
            if isinstance(profit, (int, float)):
                profit = f"${profit:,.2f}"
            elif profit != 'N/A':
                profit = f"${profit}"
            trades = test_metrics.get('num_trades', 'N/A')
            win_rate = test_metrics.get('win_rate', 'N/A')
            if isinstance(win_rate, (int, float)):
                win_rate = f"{win_rate:.1%}"
            
            dir_name = result_dir.name[:48]  # Truncate long names
            print(f"{dir_name:<50} {model_name:<20} {profit:<15} {trades:<10} {win_rate:<10}")
        except Exception as e:
            print(f"{result_dir.name:<50} {'Error':<20} {str(e)[:50]}")
            continue

print("\n=== Entry/Exit Thresholds ===")
for result_dir in sorted(base_dir.glob("*/")):
    final_selection = result_dir / "final_selection.json"
    train_json = result_dir / "grid_results_train.json"
    
    if final_selection.exists() and train_json.exists():
        try:
            with open(final_selection) as f:
                final_data = json.load(f)
            
            with open(train_json) as f:
                train_data = json.load(f)
                metadata = train_data.get('metadata', {})
            
            model_name = metadata.get('model_name') or metadata.get('args', {}).get('model_name', 'ESPN (default)')
            params = final_data.get('chosen_params', {})
            entry = params.get('entry_threshold', 'N/A')
            exit_thresh = params.get('exit_threshold', 'N/A')
            
            # Format floating point numbers to avoid precision issues
            if isinstance(entry, float):
                entry = f"{entry:.3f}".rstrip('0').rstrip('.')
            if isinstance(exit_thresh, float):
                exit_thresh = f"{exit_thresh:.3f}".rstrip('0').rstrip('.')
            
            dir_name = result_dir.name[:48]
            print(f"{dir_name:<50} {model_name:<20} Entry: {entry}, Exit: {exit_thresh}")
        except Exception as e:
            continue
EOF
```

**Quick View** - List all result directories:

```bash
# List all grid search result directories
ls -la data/grid_search/

# View results for the most recent directory
python3 << 'EOF'
import json
from pathlib import Path
import os

base_dir = Path("data/grid_search")
result_dirs = [d for d in base_dir.glob("*/") if (d / "final_selection.json").exists()]

if result_dirs:
    # Get most recently modified
    latest = max(result_dirs, key=lambda d: os.path.getmtime(d / "final_selection.json"))
    print(f"Latest results: {latest.name}\n")
    
    with open(latest / "final_selection.json") as f:
        data = json.load(f)
        print(json.dumps(data, indent=2))
else:
    print("No results found in data/grid_search/")
EOF
```

## Notes

- **No `--max-games`**: Runs on full 2025-26 season dataset
- **No `--no-cache`**: Uses cache if available (faster re-runs)
- **No `--output-dir`**: Results automatically saved to `data/grid_search/{cache_key}/` (standardized location)
- **Workers**: Set to 8 (adjust based on your CPU)
- **Output directories**: Results saved to `data/grid_search/{cache_key}/` where `{cache_key}` is auto-generated from parameters
- **Time estimate**: Each model may take 30-60+ minutes depending on dataset size and grid size (or 5-10 minutes if pre-computed probabilities are used)

## ⚡ Speed Optimization: Pre-Compute Model Probabilities

**Current bottleneck**: Grid search with models is slow because it scores each snapshot on-the-fly.

**Solution**: Pre-compute all model probabilities once, then grid search queries them directly (10x+ faster).

### Step 1: Pre-Compute Probabilities (One-Time, ~10-30 minutes)

```bash
python3 scripts/model/precompute_model_probabilities.py --refresh
```

This creates `derived.model_probabilities_v1` table with pre-computed probabilities for all 4 models.

### Step 2: Code Already Updated ✅

**Status**: The code has been updated to automatically use pre-computed probabilities when available. No manual changes needed!

**Performance Impact**:
- **Before**: 30-60+ minutes per model
- **After**: 5-10 minutes per model (same speed as ESPN-based grid search)

**When to refresh**: Run pre-computation script again when:
- New games/snapshots added to materialized view
- Models are retrained
- Model features change

## Optional: Run with Cache Disabled

If you want to force fresh runs (ignore cache), add `--no-cache`:

```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8 \
  --no-cache
```

## Find Your Results

Results are saved to `data/grid_search/{cache_key}/` where `{cache_key}` is automatically generated from your parameters.

To find your results:
```bash
# List all result directories
ls -la data/grid_search/

# View a specific result
cat data/grid_search/grid_search_*/final_selection.json | jq .
```

**Tip**: The cache key is based on all parameters, so identical parameter sets will use the same directory (and share results between CLI and API).

