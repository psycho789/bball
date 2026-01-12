# Sprint 19 Testing Checklist

**Date**: January 12, 2026  
**Purpose**: Comprehensive testing of grid search multi-model support  
**Estimated Time**: 2-3 hours

## Prerequisites

Before starting, verify:
- [ ] Database is running and accessible (`DATABASE_URL` set)
- [ ] All 4 model files exist:
  ```bash
  ls -la data/models/winprob_*.json data/models/winprob_*.cbm
  ```
- [ ] Webapp server can be started (for API testing)
- [ ] Season "2025-26" has game data (for testing)

## Test Environment Setup

### 1. Verify Model Files Exist
```bash
# Check all model files are present
ls -la data/models/winprob_logreg_platt_2017-2023.json
ls -la data/models/winprob_logreg_isotonic_2017-2023.json
ls -la data/models/winprob_catboost_platt_2017-2023.json
ls -la data/models/winprob_catboost_platt_2017-2023.cbm
ls -la data/models/winprob_catboost_isotonic_2017-2023.json
ls -la data/models/winprob_catboost_isotonic_2017-2023.cbm
```

**Expected**: All 6 files exist (4 JSON + 2 CBM)

### 2. Verify Database Connection
```bash
# Test database connection
python3 -c "from scripts.lib._db_lib import get_dsn, connect; conn = connect(get_dsn()); print('✅ Database connected'); conn.close()"
```

**Expected**: "✅ Database connected" printed

### 3. Verify Season Has Data
```bash
# Check if season has games
python3 -c "
from scripts.lib._db_lib import get_dsn, connect
from scripts.trade.grid_search_hyperparameters import get_game_ids_from_season
conn = connect(get_dsn())
game_ids = get_game_ids_from_season(conn, '2025-26')
print(f'✅ Found {len(game_ids)} games for season 2025-26')
conn.close()
"
```

**Expected**: At least 10 games found (for testing)

---

## Phase 1: CLI Testing (Command Line)

### Test 1.1: Help Command Shows Model Option
```bash
python3 scripts/trade/grid_search_hyperparameters.py --help | grep -A 2 "model-name"
```

**Expected**: Shows `--model-name` option with description

**Status**: [ ] Pass [ ] Fail

---

### Test 1.2: Backward Compatibility - No Model (ESPN Default)
```bash
# Run grid search without model parameter (should use ESPN)
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 5 \
  --max-combinations 3 \
  --workers 2 \
  --output-dir /tmp/grid_search_test_espn
```

**Check**:
- [ ] Command completes without errors
- [ ] Output directory created: `/tmp/grid_search_test_espn`
- [ ] Results files exist:
  - [ ] `/tmp/grid_search_test_espn/grid_results_train.json`
  - [ ] `/tmp/grid_search_test_espn/grid_results_valid.json`
  - [ ] `/tmp/grid_search_test_espn/grid_results_test.json`
  - [ ] `/tmp/grid_search_test_espn/final_selection.json`
- [ ] Logs show "ESPN probabilities" or no model-related errors
- [ ] Results contain valid metrics (net_profit_dollars, num_trades, etc.)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 1.3: Logistic Regression + Platt
```bash
# Run grid search with logreg_platt model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 5 \
  --max-combinations 3 \
  --workers 2 \
  --output-dir /tmp/grid_search_test_logreg_platt
```

**Check**:
- [ ] Command completes without errors
- [ ] No "Model file not found" errors
- [ ] No "Unknown model name" errors
- [ ] Logs show model loading (check for model-related messages)
- [ ] Results files created:
  - [ ] `/tmp/grid_search_test_logreg_platt/grid_results_train.json`
  - [ ] `/tmp/grid_search_test_logreg_platt/final_selection.json`
- [ ] Results contain valid metrics

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_logreg_platt/grid_results_train.json
{
  "metadata": {
    "args": {
      "season": "2025-26",
      "game_list": null,
      "entry_min": 0.02,
      "entry_max": 0.05,
      "entry_step": 0.01,
      "exit_min": 0.0,
      "exit_max": 0.02,
      "exit_step": 0.005,
      "workers": 2,
      "seed": 42,
      "enable_fees": true,
      "slippage_rate": 0.0,
      "min_trade_count": 200,
      "output_dir": "/tmp/grid_search_test_logreg_platt",
      "train_ratio": 0.7,
      "verbose": false,
      "valid_ratio": 0.15,
      "test_ratio": 0.15,
      "top_n": 10,
      "bet_amount": 20.0,
      "dsn": null,
      "use_trade_data": true,
      "exclude_first_seconds": 60,
      "exclude_last_seconds": 60,
      "max_games": 5,
      "max_combinations": 3,
      "no_cache": true,
      "model_name": "logreg_platt"
    },
    "timestamp": "2026-01-12T11:23:02.613691+00:00",
    "git_hash": "1e88616530ce78ccdfb35ab3251b3359490e205f",
    "num_games": {
      "train": 3,
      "valid": 0,
      "test": 2
    },
    "num_combinations": 3,
    "search_space": {
      "entry_range": [
        0.02,
        0.05,
        0.01
      ],
      "exit_range": [
        0.0,
        0.02,
        0.005
      ]
    },
    "season_or_list": "2025-26"
  },
  "results": [
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.0,
      "net_profit_dollars": 15.137611396551724,
      "num_trades": 3,
      "win_rate": 0.6666666666666666,
      "avg_net_profit_per_trade": 5.0458704655172415,
      "profit_factor": 1.8387931034482758,
      "max_drawdown": 20.36414,
      "total_fees": 1.6382506724137942,
      "avg_hold_time": 9640.0,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.005,
      "net_profit_dollars": -2.814813020423035,
      "num_trades": 33,
      "win_rate": 0.42424242424242425,
      "avg_net_profit_per_trade": -0.08529736425524348,
      "profit_factor": 1.1624719328493662,
      "max_drawdown": 65.07152621346306,
      "total_fees": 17.57123279504905,
      "avg_hold_time": 818.1818181818181,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.01,
      "net_profit_dollars": 11.944089056875994,
      "num_trades": 41,
      "win_rate": 0.4146341463414634,
      "avg_net_profit_per_trade": 0.29131924528965836,
      "profit_factor": 1.2819449552046212,
      "max_drawdown": 83.62726333333333,
      "total_fees": 22.258729279120804,
      "avg_hold_time": 654.1463414634146,
      "is_valid": false
    }
  ]
}%                                                                                                      
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_logreg_platt/final_selection.json 
{
  "chosen_params": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0
  },
  "train_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 15.137611396551724,
    "num_trades": 3,
    "win_rate": 0.6666666666666666,
    "avg_net_profit_per_trade": 5.0458704655172415,
    "profit_factor": 1.8387931034482758,
    "max_drawdown": 20.36414,
    "total_fees": 1.6382506724137942,
    "avg_hold_time": 9640.0,
    "is_valid": false
  },
  "valid_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 0.0,
    "num_trades": 0,
    "win_rate": 0.0,
    "avg_net_profit_per_trade": 0.0,
    "profit_factor": 0.0,
    "max_drawdown": 0.0,
    "total_fees": 0.0,
    "avg_hold_time": 0.0,
    "is_valid": false
  },
  "test_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 22.918654330816743,
    "num_trades": 2,
    "win_rate": 1.0,
    "avg_net_profit_per_trade": 11.459327165408371,
    "profit_factor": 24.090597117364446,
    "max_drawdown": 0.0,
    "total_fees": 1.171942786547703,
    "avg_hold_time": 9300.0,
    "is_valid": false
  },
  "selection_method": "best_on_valid_among_top_10_train",
  "top_n": 10
}%                                                                                                      

```

---

### Test 1.4: Logistic Regression + Isotonic
```bash
# Run grid search with logreg_isotonic model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_isotonic \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 5 \
  --max-combinations 3 \
  --workers 2 \
  --output-dir cat
```

**Check**:
- [ ] Command completes without errors
- [ ] Results file created
- [ ] Results differ from logreg_platt (compare net_profit values)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_logreg_isotonic/grid_results_train.json 
{
  "metadata": {
    "args": {
      "season": "2025-26",
      "game_list": null,
      "entry_min": 0.02,
      "entry_max": 0.05,
      "entry_step": 0.01,
      "exit_min": 0.0,
      "exit_max": 0.02,
      "exit_step": 0.005,
      "workers": 2,
      "seed": 42,
      "enable_fees": true,
      "slippage_rate": 0.0,
      "min_trade_count": 200,
      "output_dir": "/tmp/grid_search_test_logreg_isotonic",
      "train_ratio": 0.7,
      "verbose": false,
      "valid_ratio": 0.15,
      "test_ratio": 0.15,
      "top_n": 10,
      "bet_amount": 20.0,
      "dsn": null,
      "use_trade_data": true,
      "exclude_first_seconds": 60,
      "exclude_last_seconds": 60,
      "max_games": 5,
      "max_combinations": 3,
      "no_cache": false,
      "model_name": "logreg_isotonic"
    },
    "timestamp": "2026-01-12T11:25:16.575830+00:00",
    "git_hash": "1e88616530ce78ccdfb35ab3251b3359490e205f",
    "num_games": {
      "train": 3,
      "valid": 0,
      "test": 2
    },
    "num_combinations": 3,
    "search_space": {
      "entry_range": [
        0.02,
        0.05,
        0.01
      ],
      "exit_range": [
        0.0,
        0.02,
        0.005
      ]
    },
    "season_or_list": "2025-26"
  },
  "results": [
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.005,
      "net_profit_dollars": 16.424983553632334,
      "num_trades": 28,
      "win_rate": 0.5,
      "avg_net_profit_per_trade": 0.586606555486869,
      "profit_factor": 1.2783537531157152,
      "max_drawdown": 74.7671357913351,
      "total_fees": 14.700825808048613,
      "avg_hold_time": 968.5714285714286,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.0,
      "net_profit_dollars": 52.38400793501326,
      "num_trades": 3,
      "win_rate": 1.0,
      "avg_net_profit_per_trade": 17.461335978337754,
      "profit_factor": 54.08355437665782,
      "max_drawdown": 0.0,
      "total_fees": 1.6995464416445656,
      "avg_hold_time": 9640.0,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.01,
      "net_profit_dollars": -0.0639616630137823,
      "num_trades": 39,
      "win_rate": 0.38461538461538464,
      "avg_net_profit_per_trade": -0.0016400426413790332,
      "profit_factor": 1.1882044822962006,
      "max_drawdown": 78.09959920056409,
      "total_fees": 22.11753794942647,
      "avg_hold_time": 678.4615384615385,
      "is_valid": false
    }
  ]
}%                                                                                                      
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_logreg_isotonic/final_selection.json
{
  "chosen_params": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0
  },
  "train_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 52.38400793501326,
    "num_trades": 3,
    "win_rate": 1.0,
    "avg_net_profit_per_trade": 17.461335978337754,
    "profit_factor": 54.08355437665782,
    "max_drawdown": 0.0,
    "total_fees": 1.6995464416445656,
    "avg_hold_time": 9640.0,
    "is_valid": false
  },
  "valid_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 0.0,
    "num_trades": 0,
    "win_rate": 0.0,
    "avg_net_profit_per_trade": 0.0,
    "profit_factor": 0.0,
    "max_drawdown": 0.0,
    "total_fees": 0.0,
    "avg_hold_time": 0.0,
    "is_valid": false
  },
  "test_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.0,
    "net_profit_dollars": 6.821990310965625,
    "num_trades": 2,
    "win_rate": 0.5,
    "avg_net_profit_per_trade": 3.4109951554828126,
    "profit_factor": 1.7350096711798835,
    "max_drawdown": 12.223396923076926,
    "total_fees": 1.470426492089473,
    "avg_hold_time": 9270.0,
    "is_valid": false
  },
  "selection_method": "best_on_valid_among_top_10_train",
  "top_n": 10
}%                                                                                                      
```

---

### Test 1.5: CatBoost + Platt
```bash
# Run grid search with catboost_platt model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_platt \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 5 \
  --max-combinations 3 \
  --workers 2 \
  --output-dir /tmp/grid_search_test_catboost_platt
```

**Check**:
- [ ] Command completes without errors
- [ ] CatBoost model file (.cbm) loads correctly
- [ ] Results file created
- [ ] Results differ from logreg models

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_catboost_platt/grid_results_train.json
{
  "metadata": {
    "args": {
      "season": "2025-26",
      "game_list": null,
      "entry_min": 0.02,
      "entry_max": 0.05,
      "entry_step": 0.01,
      "exit_min": 0.0,
      "exit_max": 0.02,
      "exit_step": 0.005,
      "workers": 2,
      "seed": 42,
      "enable_fees": true,
      "slippage_rate": 0.0,
      "min_trade_count": 200,
      "output_dir": "/tmp/grid_search_test_catboost_platt",
      "train_ratio": 0.7,
      "verbose": false,
      "valid_ratio": 0.15,
      "test_ratio": 0.15,
      "top_n": 10,
      "bet_amount": 20.0,
      "dsn": null,
      "use_trade_data": true,
      "exclude_first_seconds": 60,
      "exclude_last_seconds": 60,
      "max_games": 5,
      "max_combinations": 3,
      "no_cache": false,
      "model_name": "catboost_platt"
    },
    "timestamp": "2026-01-12T11:27:33.207844+00:00",
    "git_hash": "1e88616530ce78ccdfb35ab3251b3359490e205f",
    "num_games": {
      "train": 3,
      "valid": 0,
      "test": 2
    },
    "num_combinations": 3,
    "search_space": {
      "entry_range": [
        0.02,
        0.05,
        0.01
      ],
      "exit_range": [
        0.0,
        0.02,
        0.005
      ]
    },
    "season_or_list": "2025-26"
  },
  "results": [
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.0,
      "net_profit_dollars": 15.137611396551724,
      "num_trades": 3,
      "win_rate": 0.6666666666666666,
      "avg_net_profit_per_trade": 5.0458704655172415,
      "profit_factor": 1.8387931034482758,
      "max_drawdown": 20.36414,
      "total_fees": 1.6382506724137942,
      "avg_hold_time": 9640.0,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.005,
      "net_profit_dollars": 127.6197102080366,
      "num_trades": 33,
      "win_rate": 0.6363636363636364,
      "avg_net_profit_per_trade": 3.8672639456980784,
      "profit_factor": 6.679341835395057,
      "max_drawdown": 10.648930407013978,
      "total_fees": 19.98466433323846,
      "avg_hold_time": 805.4545454545455,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.01,
      "net_profit_dollars": 86.612636205357,
      "num_trades": 49,
      "win_rate": 0.42857142857142855,
      "avg_net_profit_per_trade": 1.76760482051749,
      "profit_factor": 3.416759523988255,
      "max_drawdown": 16.047061241699325,
      "total_fees": 29.083555830719398,
      "avg_hold_time": 532.6530612244898,
      "is_valid": false
    }
  ]
}%                                                                                                      
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_catboost_platt/final_selection.json
{
  "chosen_params": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005
  },
  "train_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 127.6197102080366,
    "num_trades": 33,
    "win_rate": 0.6363636363636364,
    "avg_net_profit_per_trade": 3.8672639456980784,
    "profit_factor": 6.679341835395057,
    "max_drawdown": 10.648930407013978,
    "total_fees": 19.98466433323846,
    "avg_hold_time": 805.4545454545455,
    "is_valid": false
  },
  "valid_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 0.0,
    "num_trades": 0,
    "win_rate": 0.0,
    "avg_net_profit_per_trade": 0.0,
    "profit_factor": 0.0,
    "max_drawdown": 0.0,
    "total_fees": 0.0,
    "avg_hold_time": 0.0,
    "is_valid": false
  },
  "test_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 0.7297789338771702,
    "num_trades": 14,
    "win_rate": 0.35714285714285715,
    "avg_net_profit_per_trade": 0.052127066705512155,
    "profit_factor": 1.4653564701984514,
    "max_drawdown": 15.173385526868273,
    "total_fees": 9.896360799271877,
    "avg_hold_time": 1281.4285714285713,
    "is_valid": false
  },
  "selection_method": "best_on_valid_among_top_10_train",
  "top_n": 10
}
```

---

### Test 1.6: CatBoost + Isotonic
```bash
# Run grid search with catboost_isotonic model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_isotonic \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 5 \
  --max-combinations 3 \
  --workers 2 \
  --output-dir /tmp/grid_search_test_catboost_isotonic
```

**Check**:
- [ ] Command completes without errors
- [ ] Results file created
- [ ] Results differ from other models

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_catboost_isotonic/grid_results_tr
ain.json 
{
  "metadata": {
    "args": {
      "season": "2025-26",
      "game_list": null,
      "entry_min": 0.02,
      "entry_max": 0.05,
      "entry_step": 0.01,
      "exit_min": 0.0,
      "exit_max": 0.02,
      "exit_step": 0.005,
      "workers": 2,
      "seed": 42,
      "enable_fees": true,
      "slippage_rate": 0.0,
      "min_trade_count": 200,
      "output_dir": "/tmp/grid_search_test_catboost_isotonic",
      "train_ratio": 0.7,
      "verbose": false,
      "valid_ratio": 0.15,
      "test_ratio": 0.15,
      "top_n": 10,
      "bet_amount": 20.0,
      "dsn": null,
      "use_trade_data": true,
      "exclude_first_seconds": 60,
      "exclude_last_seconds": 60,
      "max_games": 5,
      "max_combinations": 3,
      "no_cache": false,
      "model_name": "catboost_isotonic"
    },
    "timestamp": "2026-01-12T11:31:14.005263+00:00",
    "git_hash": "1e88616530ce78ccdfb35ab3251b3359490e205f",
    "num_games": {
      "train": 3,
      "valid": 0,
      "test": 2
    },
    "num_combinations": 3,
    "search_space": {
      "entry_range": [
        0.02,
        0.05,
        0.01
      ],
      "exit_range": [
        0.0,
        0.02,
        0.005
      ]
    },
    "season_or_list": "2025-26"
  },
  "results": [
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.005,
      "net_profit_dollars": 54.73143348634985,
      "num_trades": 24,
      "win_rate": 0.625,
      "avg_net_profit_per_trade": 2.2804763952645772,
      "profit_factor": 3.2948005682027968,
      "max_drawdown": 16.96148921323623,
      "total_fees": 14.34769199926462,
      "avg_hold_time": 1147.5,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.0,
      "net_profit_dollars": 15.137611396551724,
      "num_trades": 3,
      "win_rate": 0.6666666666666666,
      "avg_net_profit_per_trade": 5.0458704655172415,
      "profit_factor": 1.8387931034482758,
      "max_drawdown": 20.36414,
      "total_fees": 1.6382506724137942,
      "avg_hold_time": 9640.0,
      "is_valid": false
    },
    {
      "entry_threshold": 0.02,
      "exit_threshold": 0.01,
      "net_profit_dollars": 31.897356300755938,
      "num_trades": 39,
      "win_rate": 0.46153846153846156,
      "avg_net_profit_per_trade": 0.8178809307886138,
      "profit_factor": 1.981474995477209,
      "max_drawdown": 24.749305736095753,
      "total_fees": 22.22250067125778,
      "avg_hold_time": 686.1538461538462,
      "is_valid": false
    }
  ]
}%                                                                                                      
(.venv) adamvoliva@Adams-MacBook-Air bball % cat /tmp/grid_search_test_catboost_isotonic/final_selection.json
{
  "chosen_params": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005
  },
  "train_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 54.73143348634985,
    "num_trades": 24,
    "win_rate": 0.625,
    "avg_net_profit_per_trade": 2.2804763952645772,
    "profit_factor": 3.2948005682027968,
    "max_drawdown": 16.96148921323623,
    "total_fees": 14.34769199926462,
    "avg_hold_time": 1147.5,
    "is_valid": false
  },
  "valid_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 0.0,
    "num_trades": 0,
    "win_rate": 0.0,
    "avg_net_profit_per_trade": 0.0,
    "profit_factor": 0.0,
    "max_drawdown": 0.0,
    "total_fees": 0.0,
    "avg_hold_time": 0.0,
    "is_valid": false
  },
  "test_metrics": {
    "entry_threshold": 0.02,
    "exit_threshold": 0.005,
    "net_profit_dollars": 16.268932159510317,
    "num_trades": 14,
    "win_rate": 0.42857142857142855,
    "avg_net_profit_per_trade": 1.1620665828221655,
    "profit_factor": 2.3679359952699577,
    "max_drawdown": 13.759973061224489,
    "total_fees": 11.922787330389044,
    "avg_hold_time": 1285.7142857142858,
    "is_valid": false
  },
  "selection_method": "best_on_valid_among_top_10_train",
  "top_n": 10
}%                            
```

---

### Test 1.7: Invalid Model Name (Error Handling)
```bash
# Test error handling for invalid model name
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name invalid_model \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 1 \
  --max-combinations 1
```

**Check**:
- [ ] Command fails with clear error message
- [ ] Error mentions "Unknown model name" or "invalid_model"
- [ ] Error lists valid options

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 1.8: Compare Results Between Models
```bash
# Compare final selection profit across models
python3 << 'EOF'
import json
import os

models = ['espn', 'logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic']
results = {}

for model in models:
    if model == 'espn':
        path = '/tmp/grid_search_test_espn/final_selection.json'
    else:
        path = f'/tmp/grid_search_test_{model}/final_selection.json'
    
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
            if 'test_metrics' in data:
                results[model] = data['test_metrics'].get('net_profit_dollars', 'N/A')
            else:
                results[model] = 'No test metrics'
    else:
        results[model] = 'File not found'

print("\n=== Model Comparison (Test Set Net Profit) ===")
for model, profit in results.items():
    print(f"{model:20s}: ${profit}")
    
# Check if results differ
profits = [v for v in results.values() if isinstance(v, (int, float))]
if len(set(profits)) > 1:
    print("\n✅ Results differ between models (expected)")
else:
    print("\n⚠️  Results are identical (unexpected - models should produce different results)")
EOF
```

**Check**:
- [ ] All models have results
- [ ] Results differ between models (at least 2 different values)
- [ ] No "File not found" errors

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```

=== Model Comparison (Test Set Net Profit) ===
espn                : $-4.785725677204043
logreg_platt        : $22.918654330816743
logreg_isotonic     : $6.821990310965625
catboost_platt      : $0.7297789338771702
catboost_isotonic   : $16.268932159510317

✅ Results differ between models (expected)
```

---

## Phase 2: API Testing (Webapp Endpoint)

### Test 2.1: Start Webapp Server
```bash
# In a separate terminal, start the webapp
cd /Users/adamvoliva/Code/bball
# Assuming you have a way to start the server (e.g., uvicorn)
# python3 -m uvicorn webapp.main:app --reload --port 8000
# OR however you normally start the server
```

**Check**:
- [ ] Server starts without errors
- [ ] Server accessible at http://localhost:8000 (or your port)

**Status**: [ ] Pass [ ] Fail

---

### Test 2.2: API - Backward Compatibility (No Model)
```bash
# Test API without model_name parameter
curl -X POST "http://localhost:8000/api/grid-search/run?season=2025-26&entry_min=0.02&entry_max=0.05&entry_step=0.01&exit_min=0.00&exit_max=0.02&exit_step=0.005&bet_amount=20.0&enable_fees=true&slippage_rate=0.0&exclude_first_seconds=60&exclude_last_seconds=60&use_trade_data=true&train_ratio=0.7&valid_ratio=0.15&test_ratio=0.15&top_n=10&min_trade_count=200&max_games=5" \
  -H "Content-Type: application/json" \
  -v
```

**Check**:
- [ ] Request returns 200 OK
- [ ] Response contains `request_id`
- [ ] No errors in server logs
- [ ] Grid search completes (check progress endpoint)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 2.3: API - Logistic Regression + Platt
```bash
# Test API with logreg_platt model
curl -X POST "http://localhost:8000/api/grid-search/run?season=2025-26&model_name=logreg_platt&entry_min=0.02&entry_max=0.05&entry_step=0.01&exit_min=0.00&exit_max=0.02&exit_step=0.005&bet_amount=20.0&enable_fees=true&slippage_rate=0.0&exclude_first_seconds=60&exclude_last_seconds=60&use_trade_data=true&train_ratio=0.7&valid_ratio=0.15&test_ratio=0.15&top_n=10&min_trade_count=200&max_games=5" \
  -H "Content-Type: application/json" \
  -v
```

**Check**:
- [ ] Request returns 200 OK
- [ ] Response contains `request_id`
- [ ] Grid search completes successfully
- [ ] Results available via results endpoint

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 2.4: API - All 4 Models
```bash
# Test each model via API
for model in logreg_platt logreg_isotonic catboost_platt catboost_isotonic; do
  echo "Testing model: $model"
  curl -X POST "http://localhost:8000/api/grid-search/run?season=2025-26&model_name=$model&entry_min=0.02&entry_max=0.05&entry_step=0.01&exit_min=0.00&exit_max=0.02&exit_step=0.005&bet_amount=20.0&enable_fees=true&slippage_rate=0.0&exclude_first_seconds=60&exclude_last_seconds=60&use_trade_data=true&train_ratio=0.7&valid_ratio=0.15&test_ratio=0.15&top_n=10&min_trade_count=200&max_games=5" \
    -H "Content-Type: application/json" \
    -s | jq -r '.request_id'
  echo ""
done
```

**Check**:
- [ ] All 4 models return request_id
- [ ] All grid searches complete
- [ ] No errors in server logs

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 2.5: API - Invalid Model Name (Error Handling)
```bash
# Test error handling for invalid model
curl -X POST "http://localhost:8000/api/grid-search/run?season=2025-26&model_name=invalid_model&entry_min=0.02&entry_max=0.05&entry_step=0.01&exit_min=0.00&exit_max=0.02&exit_step=0.005&bet_amount=20.0&enable_fees=true&slippage_rate=0.0&exclude_first_seconds=60&exclude_last_seconds=60&use_trade_data=true&train_ratio=0.7&valid_ratio=0.15&test_ratio=0.15&top_n=10&min_trade_count=200&max_games=5" \
  -H "Content-Type: application/json" \
  -v
```

**Check**:
- [ ] Request returns 400 Bad Request
- [ ] Error message mentions invalid model name
- [ ] Error lists valid options

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 2.6: API - Check Cache Keys Are Different
```bash
# Get cache keys for different models
python3 << 'EOF'
import requests
import json

base_url = "http://localhost:8000/api/grid-search/run"
params_base = {
    "season": "2025-26",
    "entry_min": 0.02,
    "entry_max": 0.05,
    "entry_step": 0.01,
    "exit_min": 0.00,
    "exit_max": 0.02,
    "exit_step": 0.005,
    "bet_amount": 20.0,
    "enable_fees": True,
    "slippage_rate": 0.0,
    "exclude_first_seconds": 60,
    "exclude_last_seconds": 60,
    "use_trade_data": True,
    "train_ratio": 0.7,
    "valid_ratio": 0.15,
    "test_ratio": 0.15,
    "top_n": 10,
    "min_trade_count": 200,
    "max_games": 5
}

# Import cache key function (if accessible)
# Or check server logs for cache keys
print("Note: Check server logs for cache_key values")
print("Cache keys should differ when model_name changes")
EOF
```

**Check**:
- [ ] Different models produce different cache keys
- [ ] Same model + same params = same cache key
- [ ] Cache works correctly (second request with same params returns cached result)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

## Phase 3: Frontend Testing (Browser)

### Test 3.1: Model Selector UI
1. Open webapp in browser: http://localhost:8000
2. Navigate to Grid Search page
3. Check model selector dropdown

**Check**:
- [ ] Model selector dropdown is visible
- [ ] Dropdown has 5 options:
  - [ ] "ESPN Probabilities (Default)" (empty value)
  - [ ] "Logistic Regression + Platt"
  - [ ] "Logistic Regression + Isotonic"
  - [ ] "CatBoost + Platt"
  - [ ] "CatBoost + Isotonic"
- [ ] Default selection is "ESPN Probabilities (Default)"

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 3.2: Frontend - ESPN Default (No Model Selected)
1. Select season "2025-26"
2. Leave model selector as "ESPN Probabilities (Default)"
3. Set small grid (entry: 0.02-0.05, exit: 0.00-0.02)
4. Set max_games to 5 (if available in UI)
5. Click "Run Grid Search"
6. Wait for completion

**Check**:
- [ ] Grid search starts
- [ ] Progress updates appear
- [ ] Grid search completes
- [ ] Results displayed
- [ ] Results match CLI ESPN results (approximately)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 3.3: Frontend - Each Model
For each model (logreg_platt, logreg_isotonic, catboost_platt, catboost_isotonic):

1. Select season "2025-26"
2. Select model from dropdown
3. Set same grid parameters as Test 3.2
4. Click "Run Grid Search"
5. Wait for completion

**Check**:
- [ ] Grid search starts
- [ ] Progress updates appear
- [ ] Grid search completes without errors
- [ ] Results displayed
- [ ] Results differ from ESPN results
- [ ] Results differ between models

**Status**: 
- [ ] logreg_platt: [ ] Pass [ ] Fail
- [ ] logreg_isotonic: [ ] Pass [ ] Fail
- [ ] catboost_platt: [ ] Pass [ ] Fail
- [ ] catboost_isotonic: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 3.4: Frontend - Verify Model Parameter Sent
1. Open browser Developer Tools (F12)
2. Go to Network tab
3. Select a model and run grid search
4. Find the POST request to `/api/grid-search/run`
5. Check request URL or payload

**Check**:
- [ ] Request includes `model_name` parameter
- [ ] `model_name` value matches selected model
- [ ] When "ESPN (default)" selected, `model_name` is empty/null or not sent

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

## Phase 4: Integration Testing

### Test 4.1: Model Loading Function
```bash
# Test model loading helper directly
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

from scripts.trade.grid_search_hyperparameters import load_model_artifact
from pathlib import Path

# Test each model
models = ['logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic']

for model_name in models:
    try:
        artifact = load_model_artifact(model_name)
        print(f"✅ {model_name}: Loaded successfully")
        print(f"   Model type: {artifact.model_type}")
        print(f"   Features: {len(artifact.feature_names)} features")
    except Exception as e:
        print(f"❌ {model_name}: Failed - {e}")

# Test None
result = load_model_artifact(None)
print(f"✅ None: Returns {result} (expected None)")
EOF
```

**Check**:
- [ ] All 4 models load successfully
- [ ] Model types are correct (logreg vs catboost)
- [ ] Feature counts are reasonable (>5 features)
- [ ] None returns None

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 4.2: Verify Model Scoring Works
```bash
# Test that model scoring produces probabilities
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
import numpy as np

from scripts.trade.grid_search_hyperparameters import load_model_artifact
from scripts.lib._winprob_lib import build_design_matrix, predict_proba

# Load a model
artifact = load_model_artifact('logreg_platt')
print(f"Loaded model: {artifact.model_type}")

# Create sample features
point_differential = np.array([5.0])  # Home up by 5
time_remaining_regulation = np.array([1800.0])  # 30 minutes left
possession = ['unknown']

# Build design matrix
X = build_design_matrix(
    point_differential=point_differential,
    time_remaining_regulation=time_remaining_regulation,
    possession=possession,
    preprocess=artifact.preprocess,
    score_diff_div_sqrt_time_remaining=np.array([5.0 / np.sqrt(1800.0 + 1)]),
    espn_home_prob=np.array([0.6]),
    espn_home_prob_lag_1=np.array([0.58]),
    espn_home_prob_delta_1=np.array([0.02]),
    period=[2]
)

# Predict
prob = predict_proba(artifact, X=X)
print(f"✅ Model prediction: {prob[0]:.4f} (should be between 0 and 1)")
print(f"   Prediction in range: {0.0 <= prob[0] <= 1.0}")
EOF
```

**Check**:
- [ ] Model loads
- [ ] Design matrix builds without errors
- [ ] Prediction produces value between 0 and 1
- [ ] No errors or warnings

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 4.3: Verify Cache Key Includes Model
```bash
# Test cache key generation
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

from webapp.api.endpoints.grid_search import _generate_grid_search_cache_key

# Same params, different models
params = {
    'season': '2025-26',
    'entry_min': 0.02,
    'entry_max': 0.05,
    'entry_step': 0.01,
    'exit_min': 0.00,
    'exit_max': 0.02,
    'exit_step': 0.005,
    'bet_amount': 20.0,
    'enable_fees': True,
    'slippage_rate': 0.0,
    'exclude_first_seconds': 60,
    'exclude_last_seconds': 60,
    'use_trade_data': True,
    'train_ratio': 0.7,
    'valid_ratio': 0.15,
    'test_ratio': 0.15,
    'top_n': 10,
    'min_trade_count': 200,
    'max_games': None,
    'seed': 42
}

# Generate keys for different models
key_espn = _generate_grid_search_cache_key(model_name=None, **params)
key_logreg_platt = _generate_grid_search_cache_key(model_name='logreg_platt', **params)
key_catboost = _generate_grid_search_cache_key(model_name='catboost_platt', **params)

print(f"ESPN key:        {key_espn[:32]}...")
print(f"LogReg+Platt key: {key_logreg_platt[:32]}...")
print(f"CatBoost key:     {key_catboost[:32]}...")

# Check they're different
if key_espn != key_logreg_platt != key_catboost:
    print("\n✅ Cache keys differ (correct)")
else:
    print("\n❌ Cache keys are identical (incorrect)")

# Check same model + same params = same key
key_logreg_platt2 = _generate_grid_search_cache_key(model_name='logreg_platt', **params)
if key_logreg_platt == key_logreg_platt2:
    print("✅ Same model + params = same key (correct)")
else:
    print("❌ Same model + params = different key (incorrect)")
EOF
```

**Check**:
- [ ] Different models produce different cache keys
- [ ] Same model + same params = same cache key
- [ ] ESPN (None) produces different key than models

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

## Phase 5: Error Handling & Edge Cases

### Test 5.1: Missing Model File (Simulated)
```bash
# Temporarily rename a model file to test error handling
mv data/models/winprob_logreg_platt_2017-2023.json data/models/winprob_logreg_platt_2017-2023.json.bak

# Try to use the model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 1 \
  --max-combinations 1

# Restore file
mv data/models/winprob_logreg_platt_2017-2023.json.bak data/models/winprob_logreg_platt_2017-2023.json
```

**Check**:
- [ ] Command fails with clear error
- [ ] Error mentions "Model file not found"
- [ ] Error shows file path

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 5.2: Missing CatBoost Binary File
```bash
# Temporarily rename CatBoost .cbm file
mv data/models/winprob_catboost_platt_2017-2023.cbm data/models/winprob_catboost_platt_2017-2023.cbm.bak

# Try to use the model
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name catboost_platt \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 1 \
  --max-combinations 1

# Restore file
mv data/models/winprob_catboost_platt_2017-2023.cbm.bak data/models/winprob_catboost_platt_2017-2023.cbm
```

**Check**:
- [ ] Command fails with clear error about missing .cbm file
- [ ] Error is helpful (mentions CatBoost binary)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

## Phase 6: Performance & Validation

### Test 6.1: Performance Comparison
```bash
# Time grid search with ESPN vs Model
echo "Testing ESPN (no model)..."
time python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 10 \
  --max-combinations 5 \
  --workers 2 \
  --output-dir /tmp/perf_test_espn > /dev/null 2>&1

echo "Testing with model..."
time python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  --entry-min 0.02 \
  --entry-max 0.05 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.02 \
  --exit-step 0.005 \
  --max-games 10 \
  --max-combinations 5 \
  --workers 2 \
  --output-dir /tmp/perf_test_model > /dev/null 2>&1
```

**Check**:
- [ ] Model version completes (may be slightly slower)
- [ ] Performance overhead is acceptable (<2x slower)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

### Test 6.2: Results Validation
```bash
# Validate results structure
python3 << 'EOF'
import json
import os

# Check results files
output_dir = '/tmp/grid_search_test_logreg_platt'

files_to_check = [
    'grid_results_train.json',
    'grid_results_valid.json',
    'grid_results_test.json',
    'final_selection.json'
]

for filename in files_to_check:
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        print(f"✅ {filename} exists")
        with open(filepath, 'r') as f:
            data = json.load(f)
            if filename == 'final_selection.json':
                if 'test_metrics' in data:
                    metrics = data['test_metrics']
                    if 'net_profit_dollars' in metrics:
                        print(f"   Net profit: ${metrics['net_profit_dollars']:.2f}")
            elif 'results' in data:
                print(f"   Contains {len(data['results'])} results")
    else:
        print(f"❌ {filename} not found")
EOF
```

**Check**:
- [ ] Results file has correct structure
- [ ] All required fields present
- [ ] Metrics are reasonable (not NaN, not extreme values)

**Status**: [ ] Pass [ ] Fail

**Notes**: 
```
```

---

## Test Summary

### Overall Status

**CLI Testing**: [ ] Complete [ ] Partial [ ] Failed  
**API Testing**: [ ] Complete [ ] Partial [ ] Failed  
**Frontend Testing**: [ ] Complete [ ] Partial [ ] Failed  
**Integration Testing**: [ ] Complete [ ] Partial [ ] Failed  
**Error Handling**: [ ] Complete [ ] Partial [ ] Failed  

### Critical Issues Found

1. 
2. 
3. 

### Minor Issues Found

1. 
2. 
3. 

### Test Results Summary

- **Total Tests**: 
- **Passed**: 
- **Failed**: 
- **Skipped**: 

### Final Recommendation

[ ] ✅ Sprint is complete and ready for production  
[ ] ⚠️ Sprint is mostly complete but has minor issues  
[ ] ❌ Sprint has critical issues that must be fixed  

**Notes**:
```

