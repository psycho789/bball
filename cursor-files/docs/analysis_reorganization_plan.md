# Analysis File Reorganization Plan

**Date**: 2026-01-09  
**Sprint**: Sprint 1 - Codebase Cleanup and Restructuring  
**Purpose**: Move flat analysis files to date-based folders following standard structure

## Files to Reorganize

### Grid Search Related Files (2025-01-27)
- `grid_search_hyperparameter_optimization_analysis.md` → `2025-01-27-grid-search-hyperparameter-optimization/`
- `grid_search_command_summary.md` → `2025-01-27-grid-search-command-summary/`
- `grid_search_friend_concerns_breakdown.md` → `2025-01-27-grid-search-friend-concerns/`
- `grid_search_output_guide.md` → `2025-01-27-grid-search-output-guide/`
- `grid_search_sql_queries.md` → `2025-01-27-grid-search-sql-queries/`

### Win Probability Application Files (2025-12-20 to 2025-12-21)
- `in_game_win_probability_application_analysis_v1.md` → `2025-12-20-in-game-win-probability-application/`
- `in_game_win_probability_chart_analysis_v1.md` → `2025-12-21-in-game-win-probability-chart/`

### Live Games Feature (2025-01-27)
- `live_games_feature_analysis_v1.md` → `2025-01-27-live-games-feature/`

### Betting/Trading Simulation Files (2025-01-28)
- `betting_odds_simulation_analysis_v1.md` → `2025-01-28-betting-odds-simulation/`
- `simulation-betting-vs-trading-analysis.md` → `2025-01-28-simulation-betting-vs-trading/`
- `simulation-position-sizing-and-exit-logic-analysis.md` → `2025-01-28-simulation-position-sizing-exit-logic/`
- `simulation-simplified-view-analysis.md` → `2025-01-28-simulation-simplified-view/`
- `trading-costs-simulation-analysis.md` → `2025-01-28-trading-costs-simulation/`
- `trading-simulation-deep-dive-audit-v1.md` → `2025-01-28-trading-simulation-deep-dive-audit/`

### Signal Improvement (Date TBD - use 2025-12-20 as fallback)
- `signal_improvement_next_steps_analysis.md` → `2025-12-20-signal-improvement-next-steps/`

### Data Sources and Schema (Date TBD - use 2025-01-01 as fallback)
- `nba_data_sources_analysis_v2.md` → `2025-01-01-nba-data-sources/`
- `nba_pbp_postgres_schema_analysis.md` → `2025-01-01-nba-pbp-postgres-schema/`

### Other Analysis Files (Date TBD - use 2025-01-01 as fallback)
- `suggested-fixes-analysis.md` → `2025-01-01-suggested-fixes/`
- `trade-data-candlestick-enhancement-analysis.md` → `2025-01-01-trade-data-candlestick-enhancement/`
- `why_exit_affects_trade_count.md` → `2025-01-01-why-exit-affects-trade-count/`

### JSON File
- `playbyplay_0022400196.json` → `2025-01-01-playbyplay-sample/` (if exists)

## Implementation Steps

1. Create date-based folders for each group
2. Move files to appropriate folders
3. Verify all files moved
4. Update any references if needed

## Notes

- Files without clear dates grouped by topic and assigned reasonable dates
- Date format: `YYYY-MM-DD-[description]`
- All files maintain their original names within new folder structure

