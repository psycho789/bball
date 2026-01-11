#!/bin/bash
# Quick test to see trade count at entry threshold 0.15

# Test with a small number of games first
python scripts/grid_search_hyperparameters.py \
     --season "2025-26" \
     --entry-min 0.15 --entry-max 0.15 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.01 \
     --workers 4 \
     --seed 42 \
     --enable-fees \
     --slippage-rate 0.0 \
     --min-trade-count 0 \
     --max-games 10 \
     --output-dir test_entry_015/

echo ""
echo "Check the results CSV for num_trades column"
echo "Results saved to: test_entry_015/grid_results_train.csv"

