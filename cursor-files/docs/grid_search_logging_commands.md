# Grid Search Logging Commands

## Option 1: Using `tee` (Recommended - No Code Changes)

Run your grid search with `tee` to capture all output to a file:

```bash
python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache \
  2>&1 | tee grid_search_$(date +%Y%m%d_%H%M%S).log
```

**What this does:**
- `2>&1` - Redirects stderr to stdout (captures all output)
- `tee` - Writes to both terminal and file
- `grid_search_$(date +%Y%m%d_%H%M%S).log` - Creates timestamped log file

**Example output file:** `grid_search_20260126_143022.log`

---

## Option 2: Modify Script to Auto-Log to File

If you want the script to automatically log to a file in the output directory, I can modify the script to add a file handler. The log file would be saved alongside the grid search results in `data/grid_search/{cache_key}/grid_search.log`.

Would you like me to implement this?

---

## Option 3: Verbose Mode with File Logging

For more detailed logs (including all the warnings), use `--verbose` flag:

```bash
python scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache \
  --verbose \
  2>&1 | tee grid_search_verbose_$(date +%Y%m%d_%H%M%S).log
```

This will capture:
- All `[END_OF_GAME]` warnings
- All `[ALIGN_DATA]` warnings  
- Debug information
- Progress updates
