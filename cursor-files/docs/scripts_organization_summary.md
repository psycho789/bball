# Scripts Organization Summary

## Overview
All scripts have been organized into category-based subdirectories for better maintainability and discoverability.

## Directory Structure

### Core Libraries (`scripts/lib/`)
Foundational libraries used by other scripts:
- `_db_lib.py` - Database utilities
- `_fetch_lib.py` - HTTP fetching with retry logic
- `_winprob_lib.py` - Win probability model utilities

### Data Fetching (`scripts/fetch/`)
Scripts for fetching data from external APIs:
- `fetch_espn_probabilities.py`
- `fetch_espn_scoreboard.py`
- `fetch_kalshi_trades.py`
- `fetch_pbp.py`
- `fetch_boxscore.py`
- `fetch_odds_today.py`
- `fetch_scheduleLeagueV2.py`

### Data Loading (`scripts/load/`)
Scripts for loading fetched data into the database:
- `load_espn_probabilities_raw_items.py`
- `load_espn_scoreboard.py`
- `load_kalshi_trades.py`
- `load_kalshi_markets.py`
- `load_kalshi_candlesticks.py`
- `load_pbp.py`
- `load_odds_snapshot.py`
- `load_espn_plays.py`

### Data Processing (`scripts/process/`)
Scripts for transforming and materializing data:
- `materialize_espn_prob_event_state.py`
- `materialize_pbp_event_state.py`
- `build_winprob_snapshots_parquet.py`

### Modeling (`scripts/model/`)
Scripts for model training and evaluation:
- `train_winprob_logreg.py`
- `evaluate_winprob_model.py`
- `score_winprob_snapshot.py`

### Trading (`scripts/trade/`)
Scripts for trading simulation and strategy analysis:
- `simulate_trading_strategy.py`
- `grid_search_hyperparameters.py`
- `analyze_grid_search_results.py`
- `paper_trade_winprob.py`
- `join_winprob_to_odds_snapshot.py`

### Export (`scripts/export/`)
Scripts for exporting data:
- `export_pbp_event_state_parquet.py`
- `export_winprob_modeling_events_parquet.py`
- `export_winprob_split_game_ids.py`
- `export_pbp_event_state.py`
- `export_game_state.py`

### Backfill (`scripts/backfill/`)
Scripts for backfilling historical data:
- `backfill_seasons.py`
- `backfill_espn_probabilities_range.py`
- `backfill_espn_probabilities_season.py`
- `backfill_games_final_result_from_pbp.py`
- `backfill_games_from_boxscore_archive.py`
- `backfill_games_from_leaguegamefinder_archive.py`
- `backfill_games_from_scheduleleaguev2.py`

### Utilities (`scripts/utils/`)
Utility and helper scripts:
- `migrate.py` - Database migration runner
- `psql.sh` - PostgreSQL helper script
- `discover_game_ids.py`
- `qc_report.py`
- `check_espn_probabilities_completeness.py`
- `verify_espn_win_probabilities.py`
- `audit_espn_probabilities_support.py`
- `inspect_espn_odds.py`
- `generate_winprob_chart.py`
- `generate_espn_kalshi_chart.py`
- `generate_full_espn_kalshi_comparison.py`
- `run_backfill.sh`
- `run_espn_probabilities_backfill.sh`

## Import Updates

All scripts have been updated to use the new import paths:
- `from scripts.lib._db_lib import ...`
- `from scripts.lib._fetch_lib import ...`
- `from scripts.lib._winprob_lib import ...`
- `from scripts.trade.simulate_trading_strategy import ...`

Scripts add the project root to `sys.path` to enable these imports:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
```

## Webapp Integration

The webapp has been updated to reference the new script location:
- `webapp/api/endpoints/simulation.py` now imports from `scripts/trade/simulate_trading_strategy.py`

## Date Completed
2026-01-09
