# Quick Test Commands - Sprint 19

Quick reference for testing grid search multi-model support.

## Prerequisites Check
```bash
# Verify model files
ls -la data/models/winprob_*.json data/models/winprob_*.cbm

# Verify database
python3 -c "from scripts.lib._db_lib import get_dsn, connect; conn = connect(get_dsn()); print('✅ DB OK'); conn.close()"
```

## CLI Tests (Quick - 5 games, 3 combinations)

### ESPN (Backward Compatibility)
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 5 --max-combinations 3 --workers 2 \
  --output-dir /tmp/test_espn
```

### All 4 Models
```bash
# LogReg + Platt
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 --model-name logreg_platt \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 5 --max-combinations 3 --workers 2 \
  --output-dir /tmp/test_logreg_platt

# LogReg + Isotonic
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 --model-name logreg_isotonic \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 5 --max-combinations 3 --workers 2 \
  --output-dir /tmp/test_logreg_isotonic

# CatBoost + Platt
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 --model-name catboost_platt \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 5 --max-combinations 3 --workers 2 \
  --output-dir /tmp/test_catboost_platt

# CatBoost + Isotonic
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 --model-name catboost_isotonic \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 5 --max-combinations 3 --workers 2 \
  --output-dir /tmp/test_catboost_isotonic
```

### Error Handling
```bash
# Invalid model name
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 --model-name invalid_model \
  --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
  --exit-min 0.00 --exit-max 0.02 --exit-step 0.005 \
  --max-games 1 --max-combinations 1
```

## Compare Results
```bash
python3 << 'EOF'
import json
import os

models = ['espn', 'logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic']
for model in models:
    path = f'/tmp/test_{model}/final_selection.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            profit = data.get('test_metrics', {}).get('net_profit_dollars', 'N/A')
            print(f"{model:20s}: ${profit}")
EOF
```

## API Tests

### Base URL
```bash
BASE="http://localhost:8000/api/grid-search/run"
PARAMS="season=2025-26&entry_min=0.02&entry_max=0.05&entry_step=0.01&exit_min=0.00&exit_max=0.02&exit_step=0.005&bet_amount=20.0&enable_fees=true&slippage_rate=0.0&exclude_first_seconds=60&exclude_last_seconds=60&use_trade_data=true&train_ratio=0.7&valid_ratio=0.15&test_ratio=0.15&top_n=10&min_trade_count=200&max_games=5"
```

### Test Each Model
```bash
# ESPN (no model)
curl -X POST "$BASE?$PARAMS" -H "Content-Type: application/json"

# LogReg + Platt
curl -X POST "$BASE?$PARAMS&model_name=logreg_platt" -H "Content-Type: application/json"

# LogReg + Isotonic
curl -X POST "$BASE?$PARAMS&model_name=logreg_isotonic" -H "Content-Type: application/json"

# CatBoost + Platt
curl -X POST "$BASE?$PARAMS&model_name=catboost_platt" -H "Content-Type: application/json"

# CatBoost + Isotonic
curl -X POST "$BASE?$PARAMS&model_name=catboost_isotonic" -H "Content-Type: application/json"

# Invalid model (should return 400)
curl -X POST "$BASE?$PARAMS&model_name=invalid" -H "Content-Type: application/json"
```

## Model Loading Test
```bash
python3 << 'EOF'
from scripts.trade.grid_search_hyperparameters import load_model_artifact

for model in ['logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic']:
    try:
        artifact = load_model_artifact(model)
        print(f"✅ {model}: {artifact.model_type}, {len(artifact.feature_names)} features")
    except Exception as e:
        print(f"❌ {model}: {e}")
EOF
```

## Cache Key Test
```bash
python3 << 'EOF'
from webapp.api.endpoints.grid_search import _generate_grid_search_cache_key

params = {
    'season': '2025-26', 'entry_min': 0.02, 'entry_max': 0.05, 'entry_step': 0.01,
    'exit_min': 0.00, 'exit_max': 0.02, 'exit_step': 0.005, 'bet_amount': 20.0,
    'enable_fees': True, 'slippage_rate': 0.0, 'exclude_first_seconds': 60,
    'exclude_last_seconds': 60, 'use_trade_data': True, 'train_ratio': 0.7,
    'valid_ratio': 0.15, 'test_ratio': 0.15, 'top_n': 10, 'min_trade_count': 200,
    'max_games': None, 'seed': 42
}

k1 = _generate_grid_search_cache_key(model_name=None, **params)
k2 = _generate_grid_search_cache_key(model_name='logreg_platt', **params)
k3 = _generate_grid_search_cache_key(model_name='catboost_platt', **params)

print(f"ESPN:        {k1[:32]}...")
print(f"LogReg+Platt: {k2[:32]}...")
print(f"CatBoost:     {k3[:32]}...")
print(f"\nKeys differ: {k1 != k2 != k3}")
EOF
```

## Frontend Test Checklist

1. Open http://localhost:8000 → Grid Search page
2. Verify model selector dropdown has 5 options
3. Test each model:
   - Select model from dropdown
   - Set small grid (entry: 0.02-0.05, exit: 0.00-0.02)
   - Set max_games to 5 (if available)
   - Click "Run Grid Search"
   - Verify completion and results
4. Test ESPN default (no model selected)
5. Check browser DevTools → Network tab → verify `model_name` parameter sent

## Expected Results

✅ All CLI commands complete without errors  
✅ All API requests return 200 OK (except invalid model = 400)  
✅ Results differ between models  
✅ Cache keys differ between models  
✅ Frontend model selector works  
✅ Backward compatibility maintained (ESPN still works)

