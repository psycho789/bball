# Quick Grid Search Logging Test

## Test Command (Fast - ~30 seconds)

This runs a minimal grid search to verify logging works:

```bash
python -u scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache \
  --max-games 5 \
  --max-combinations 2 \
  --entry-min 0.05 \
  --entry-max 0.10 \
  --entry-step 0.05 \
  --exit-min 0.01 \
  --exit-max 0.02 \
  --exit-step 0.01 \
  --verbose \
  2>&1 | tee test_logging_$(date +%Y%m%d_%H%M%S).log
```

**What this does:**
- `--max-games 5` - Only uses 5 games (super fast)
- `--max-combinations 2` - Only tests 2 threshold combinations
- `--entry-min/max/step` - Small grid (2 entry values: 0.05, 0.10)
- `--exit-min/max/step` - Small grid (2 exit values: 0.01, 0.02)
- `--verbose` - Shows detailed logs
- `python -u` - Unbuffered output (logs appear immediately)
- `tee` - Captures output to file AND terminal

**Expected output:**
- You should see logs appearing in real-time in terminal
- Log file should be created: `test_logging_YYYYMMDD_HHMMSS.log`
- Automatic log file: `data/grid_search/{cache_key}/grid_search.log`

**Check if it worked:**
1. Watch terminal - logs should appear immediately
2. Check log file: `ls -lh test_logging_*.log`
3. Check auto log: `ls -lh data/grid_search/*/grid_search.log`

---

## Even Faster Test (Just 1 combination)

```bash
python -u scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_odds_isotonic_v2 \
  --dsn "$DATABASE_URL" \
  --no-cache \
  --max-games 3 \
  --max-combinations 1 \
  --entry-min 0.05 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.01 \
  --exit-max 0.01 \
  --exit-step 0.01 \
  --verbose \
  2>&1 | tee test_logging_$(date +%Y%m%d_%H%M%S).log
```

This tests just 1 combination on 3 games - should complete in ~10-15 seconds.
