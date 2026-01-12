# Verify Pre-Computed Model Probabilities

## Check if Pre-Computation Worked

```bash
python3 << 'EOF'
import psycopg
import os
from scripts.lib._db_lib import get_dsn, connect

dsn = get_dsn(None)
with connect(dsn) as conn:
    # Check row count
    count = conn.execute("SELECT COUNT(*) FROM derived.model_probabilities_v1").fetchone()[0]
    print(f"Total snapshots with pre-computed probabilities: {count:,}")
    
    # Check coverage by model
    models = ['logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic']
    print("\nCoverage by model:")
    for model in models:
        col = f"{model}_prob"
        non_null = conn.execute(
            f"SELECT COUNT(*) FROM derived.model_probabilities_v1 WHERE {col} IS NOT NULL"
        ).fetchone()[0]
        pct = (non_null / count * 100) if count > 0 else 0
        print(f"  {model}: {non_null:,} ({pct:.1f}%)")
    
    # Sample a few rows
    print("\nSample rows:")
    rows = conn.execute("""
        SELECT 
            game_id, sequence_number,
            logreg_platt_prob, logreg_isotonic_prob,
            catboost_platt_prob, catboost_isotonic_prob
        FROM derived.model_probabilities_v1
        WHERE logreg_platt_prob IS NOT NULL
        LIMIT 5
    """).fetchall()
    
    for row in rows:
        print(f"  Game {row[0]}, snapshot {row[1]}:")
        print(f"    LogReg+Platt: {row[2]:.3f}")
        print(f"    LogReg+Isotonic: {row[3]:.3f}")
        print(f"    CatBoost+Platt: {row[4]:.3f}")
        print(f"    CatBoost+Isotonic: {row[5]:.3f}")
EOF
```

## Run Grid Search (Current - Still Uses On-the-Fly Scoring)

**Note**: The code currently still scores on-the-fly. To use pre-computed probabilities, we need to update `get_aligned_data()` first.

For now, you can still run grid search (it will be slower until we update the code):

```bash
# Logistic Regression + Platt
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
  --output-dir /tmp/grid_search_logreg_platt_full
```

## Next Step: Update Code to Use Pre-Computed Probabilities

We need to modify `get_aligned_data()` in `scripts/trade/simulate_trading_strategy.py` to:
1. Check if `model_name` is provided
2. Query `derived.model_probabilities_v1` for pre-computed probability
3. Only fall back to on-the-fly scoring if pre-computed value is missing

This will make grid search 10x+ faster.

