# Script Audit Results

**Date**: 2026-01-09  
**Sprint**: Sprint 1 - Codebase Cleanup and Restructuring  
**Purpose**: Categorize all scripts in `scripts/` directory as active/obsolete/archived

## Summary

- **Total Scripts**: 55 scripts (Python and shell scripts)
- **Active**: 51 scripts
- **Potentially Obsolete**: 4 scripts (require review)
- **Archived**: 0 scripts

## Script Categorization

### Core Libraries (ACTIVE)
These are foundational libraries used by other scripts and the webapp.

- **`lib/_db_lib.py`**: Database utilities (connections, ingestion runs, source files) - **ACTIVE**
  - Used by: Multiple scripts, webapp
  - Status: Critical infrastructure

- **`lib/_fetch_lib.py`**: HTTP fetching with retry logic, manifest generation - **ACTIVE**
  - Used by: All fetch scripts
  - Status: Critical infrastructure

- **`lib/_winprob_lib.py`**: Win probability model (IRLS, Platt scaling, metrics) - **ACTIVE**
  - Used by: Training, evaluation, scoring scripts
  - Status: Critical infrastructure

### Data Fetching Scripts (ACTIVE)
All fetch scripts are actively used for data ingestion.

- `fetch_espn_probabilities.py` - **ACTIVE**
- `fetch_espn_scoreboard.py` - **ACTIVE**
- `fetch_kalshi_trades.py` - **ACTIVE**
- `fetch_pbp.py` - **ACTIVE**
- `fetch_boxscore.py` - **ACTIVE**
- `fetch_odds_today.py` - **ACTIVE**
- `fetch_scheduleLeagueV2.py` - **ACTIVE**

### Data Loading Scripts (ACTIVE)
All load scripts are actively used for loading data into database.

- `load_espn_probabilities_raw_items.py` - **ACTIVE**
- `load_espn_scoreboard.py` - **ACTIVE**
- `load_kalshi_trades.py` - **ACTIVE**
- `load_kalshi_markets.py` - **ACTIVE**
- `load_kalshi_candlesticks.py` - **ACTIVE**
- `load_pbp.py` - **ACTIVE**
- `load_odds_snapshot.py` - **ACTIVE**
- `load_espn_plays.py` - **ACTIVE**

### Data Processing Scripts (ACTIVE)
All processing scripts are actively used for data transformation.

- `materialize_espn_prob_event_state.py` - **ACTIVE**
- `materialize_pbp_event_state.py` - **ACTIVE**
- `build_winprob_snapshots_parquet.py` - **ACTIVE**

### Modeling Scripts (ACTIVE)
All modeling scripts are actively used for model training and evaluation.

- `train_winprob_logreg.py` - **ACTIVE**
- `evaluate_winprob_model.py` - **ACTIVE**
- `score_winprob_snapshot.py` - **ACTIVE**

### Trading Scripts (ACTIVE)
Trading simulation scripts are actively used by webapp and grid search.

- `trade/simulate_trading_strategy.py` - **ACTIVE**
  - Used by: `webapp/api/endpoints/simulation.py`, `scripts/trade/grid_search_hyperparameters.py`
  - Status: Critical - used by webapp API

- `trade/grid_search_hyperparameters.py` - **ACTIVE**
  - Used by: Manual execution for parameter optimization
  - Status: Active tool

- `trade/analyze_grid_search_results.py` - **ACTIVE**
  - Used by: Manual execution for analyzing grid search results
  - Status: Active tool

### Backfill Scripts (ACTIVE)
All backfill scripts are actively used for data backfilling.

- `backfill/backfill_seasons.py` - **ACTIVE**
- `backfill/backfill_espn_probabilities_range.py` - **ACTIVE**
- `backfill/backfill_espn_probabilities_season.py` - **ACTIVE**
- `backfill/backfill_games_final_result_from_pbp.py` - **ACTIVE**
- `backfill/backfill_games_from_boxscore_archive.py` - **ACTIVE**
- `backfill/backfill_games_from_leaguegamefinder_archive.py` - **ACTIVE**
- `backfill/backfill_games_from_scheduleleaguev2.py` - **ACTIVE**

### Export Scripts (MIXED - Some Potentially Obsolete)
Export scripts - some may be superseded by Parquet versions.

- `export/export_pbp_event_state_parquet.py` - **ACTIVE** (Parquet format, preferred)
- `export/export_winprob_modeling_events_parquet.py` - **ACTIVE** (Parquet format, preferred)
- `export/export_winprob_split_game_ids.py` - **ACTIVE**
- `export/export_pbp_event_state.py` - **REVIEW NEEDED** (CSV format, may be superseded by Parquet version)
- `export/export_game_state.py` - **REVIEW NEEDED** (CSV format, may be superseded by Parquet version)

### Chart Generation Scripts (POTENTIALLY OBSOLETE)
Chart generation scripts may be superseded by webapp functionality.

- `utils/generate_winprob_chart.py` - **REVIEW NEEDED** (May be superseded by webapp chart functionality)
- `utils/generate_espn_kalshi_chart.py` - **REVIEW NEEDED** (May be superseded by webapp chart functionality)
- `utils/generate_full_espn_kalshi_comparison.py` - **REVIEW NEEDED** (May be superseded by webapp)

### Utility Scripts (ACTIVE)
Utility scripts are actively used.

- `utils/migrate.py` - **ACTIVE** (Database migration runner)
- `discover_game_ids.py` - **ACTIVE**
- `psql.sh` - **ACTIVE** (Database connection helper)
- `qc_report.py` - **ACTIVE** (Quality control reporting)
- `run_backfill.sh` - **ACTIVE** (Backfill orchestrator)
- `run_espn_probabilities_backfill.sh` - **ACTIVE**

### Analysis/Verification Scripts (ACTIVE)
Analysis scripts are actively used for data quality checks.

- `check_espn_probabilities_completeness.py` - **ACTIVE**
- `verify_espn_win_probabilities.py` - **ACTIVE**
- `audit_espn_probabilities_support.py` - **ACTIVE**
- `inspect_espn_odds.py` - **ACTIVE**

### Other Scripts (ACTIVE)
- `paper_trade_winprob.py` - **ACTIVE** (Paper trading simulation)
- `join_winprob_to_odds_snapshot.py` - **ACTIVE** (Join model to odds data)
- `export_webapp_schema.sh` - **ACTIVE** (Export webapp schema)

## Potentially Obsolete Scripts (Require Review)

### 1. `export_pbp_event_state.py`
- **Purpose**: Export PBP event state to CSV
- **Status**: **REVIEW NEEDED**
- **Reason**: May be superseded by `export_pbp_event_state_parquet.py` (Parquet format preferred)
- **Recommendation**: Check if CSV export still needed. If not, archive or remove.

### 2. `export_game_state.py`
- **Purpose**: Export game state to CSV
- **Status**: **REVIEW NEEDED**
- **Reason**: May be superseded by Parquet exports
- **Recommendation**: Check if CSV export still needed. If not, archive or remove.

### 3. `generate_winprob_chart.py`
- **Purpose**: Generate static SVG charts for win probability
- **Status**: **REVIEW NEEDED**
- **Reason**: May be superseded by webapp chart functionality (`webapp/static/js/chart.js`)
- **Recommendation**: Check if static SVG generation still needed. If not, archive or remove.

### 4. `generate_espn_kalshi_chart.py`
- **Purpose**: Generate comparison charts
- **Status**: **REVIEW NEEDED**
- **Reason**: May be superseded by webapp functionality
- **Recommendation**: Check if still needed. If not, archive or remove.

### 5. `generate_full_espn_kalshi_comparison.py`
- **Purpose**: Generate full ESPN-Kalshi comparison
- **Status**: **REVIEW NEEDED**
- **Reason**: May be superseded by webapp functionality
- **Recommendation**: Check if still needed. If not, archive or remove.

## Recommendations

1. **Keep All Active Scripts**: 51 scripts are confirmed active and should remain in `scripts/` directory.

2. **Review Potentially Obsolete Scripts**: 5 scripts require review to determine if they're still needed:
   - `export_pbp_event_state.py`
   - `export_game_state.py`
   - `generate_winprob_chart.py`
   - `generate_espn_kalshi_chart.py`
   - `generate_full_espn_kalshi_comparison.py`

3. **Decision Process**: For each potentially obsolete script:
   - Check if script is referenced in documentation or other scripts
   - Check if functionality is available in webapp
   - If not needed, move to `scripts/archive/` directory
   - Update documentation to reflect archived status

4. **No Immediate Action Required**: All potentially obsolete scripts are low-risk to keep. They can be archived in a future cleanup if confirmed unused.

## Next Steps

1. Review potentially obsolete scripts with project stakeholders
2. Archive confirmed obsolete scripts to `scripts/archive/` if needed
3. Update documentation to reflect archived scripts
4. Consider script reorganization by category in future sprint (deferred from this sprint)

