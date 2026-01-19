# Pre-Game Odds Model Integration: Analysis

**Date**: Tue Jan 13 15:09:44 PST 2026  
**Purpose**: Analyze how to integrate pre-game sportsbook opening odds into win-probability models to improve prediction accuracy and grid search results  
**Status**: Draft  
**Author**: AI Assistant  
**Reviewers**: dta (data scientist), Adam  
**Version**: v1.0  

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (code refs, commands + verbatim output, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers analyzed
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: Use PostgreSQL via `DATABASE_URL`

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings

- **Finding 1**: Opening odds are now available in `derived.snapshot_features_v1` via columns `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, and `opening_total` (migration 039). These represent pre-game market expectations but are currently unused in models.

- **Finding 2**: Current models use in-game features only: `point_differential`, `time_remaining`, `espn_home_prob`, and interaction terms. Opening odds represent pre-game market consensus but lose informational value as game progresses (especially in final minutes).

- **Finding 3**: Data scientist (dta) recommends adding opening odds as features with **time-weighted interaction terms** because odds become less informative as time runs out. CatBoost should be used instead of Logistic Regression, as it can automatically discover interactions. **Critical Fixes**: (1) Raw implied probabilities (`1 / decimal_odds`) include vig/overround and must be de-vigged to fair probabilities before use. (2) Decay weights must **decrease** as time approaches 0 (e.g., `w = time_remaining / 2880`), not divide by time_remaining (which increases impact late game - backwards).

### Critical Issues Identified

- **Issue 1**: Opening odds not integrated - Models currently ignore opening odds despite their availability in canonical dataset. This represents wasted signal from market consensus.
- **Issue 2**: Missing interaction terms - Opening odds should interact with time remaining because their information value decays over the course of the game. Current models don't capture this relationship.
- **Issue 3**: Model architecture limitation - Logistic Regression requires explicit feature engineering for interactions. CatBoost can discover interactions automatically, making it better suited for odds integration.

### Recommended Actions

- **Action 1**: **Priority: High** - Add opening odds features to `build_design_matrix()` and model training scripts. Convert decimal odds to **fair probabilities** (de-vigged) to remove overround bias. Use missingness indicator flags for CatBoost (no imputation).
- **Action 2**: **Priority: High** - For CatBoost, start with direct features and let it discover interactions automatically. If manual interactions needed (e.g., for Logistic Regression), use decay weights that **decrease** as time approaches 0 (e.g., `w = time_remaining / 2880`), not division by time_remaining.
- **Action 3**: **Priority: Medium** - **After parity validation** (see "Training Data Source Parity Validation" section), update canonical dataset query in training scripts to include opening odds columns. Ensure data loading handles NULL values correctly (CatBoost: keep NaNs + missingness flags; Logistic Regression: impute with training-set means).

### Success Metrics

- **Model Performance**: Improved prediction accuracy (Brier score, log-loss) on test set with opening odds features vs. baseline
- **Time-Bucketed Performance**: Improved Brier score / log-loss in early-game buckets (2880-2400s, 2400-1800s) where opening odds are most informative
- **Grid Search Performance**: Improved expected value or win rate in grid search results when using models trained with opening odds
- **Feature Importance**: Opening odds features show meaningful contribution in CatBoost feature importance analysis
- **Coverage**: Opening odds available for 80%+ of games in training/test sets (2017-2025 seasons)
- **Population Parity**: Training data source (ESPN-direct vs `snapshot_features_v1`) shows equivalent game/snapshot counts before switching

---

## Problem Statement

### Current Situation

We have successfully integrated opening odds data into the database and canonical snapshot dataset (`derived.snapshot_features_v1`). The following columns are available:
- `opening_moneyline_home` (decimal odds, e.g., 1.85)
- `opening_moneyline_away` (decimal odds, e.g., 2.10)
- `opening_spread` (line value, e.g., -5.5)
- `opening_total` (line value, e.g., 220.5)

**Current Model State**:
- Models (`train_winprob_logreg.py`, `train_winprob_catboost.py`) query ESPN data directly (bypass canonical dataset)
- Features used: `point_differential`, `time_remaining_regulation`, `possession`, plus optional interaction terms (`score_diff_div_sqrt_time_remaining`, `espn_home_prob`, lagged features, period)
- **Opening odds are NOT used** in model training or prediction

**Data Scientist Feedback (dta)**:
- "add the odds data as a parameter" - Add opening odds as features to the model
- "we may need interaction terms bc we're really interested in the relation between the terms" - Opening odds should interact with time/score
- "like the odds mean very little with 2 minutes in the game" - Opening odds information value decays over time
- "just use catboost" - CatBoost can discover interactions automatically
- "drop the logistic there's no real point in running it until we add interaction terms" - Logistic Regression requires explicit interaction engineering
- "something like odds divided by time or score divided by time" - Suggested interaction terms

### Pain Points

- **Pain Point 1**: Wasted signal - Opening odds represent pre-game market consensus (sportsbooks' best estimate before the game starts), but this information is currently ignored by models
- **Pain Point 2**: Missing temporal context - Opening odds should be more informative early in the game (when game state hasn't diverged much from pre-game expectations) and less informative late in the game (when current score/time dominates). Current models don't capture this.
- **Pain Point 3**: Manual feature engineering required - Logistic Regression requires explicit interaction term design (e.g., decay-weighted features like `p_home_fair * w` where `w = time_remaining / 2880`), whereas CatBoost can discover these relationships automatically

### Business Impact

- **Model Performance Impact**: Models may be missing valuable pre-game signal that could improve win probability predictions, especially early in games
- **Grid Search Impact**: Trading strategies using model probabilities may perform better if models incorporate opening odds, leading to better entry/exit threshold selection
- **Signal Improvement Impact**: Cannot evaluate whether opening odds improve predictions vs. ESPN-only models without integration

### Success Criteria

- **Criterion 1**: Opening odds features added to model training pipeline (`build_design_matrix()`, training scripts)
- **Criterion 2**: Models trained with opening odds show improved performance metrics (Brier score, log-loss) on held-out test set
- **Criterion 3**: Grid search results show improved expected value or win rate when using models with opening odds features
- **Criterion 4**: CatBoost feature importance shows opening odds features have meaningful contribution

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**:
  - Modify: `scripts/lib/_winprob_lib.py` (`build_design_matrix()` function to accept opening odds parameters)
  - Modify: `scripts/model/train_winprob_catboost.py` (load opening odds from canonical dataset, pass to `build_design_matrix()`)
  - Modify: `scripts/model/train_winprob_logreg.py` (same, if keeping Logistic Regression)
  - Modify: `scripts/model/precompute_model_probabilities.py` (include opening odds when scoring snapshots)
  - Optional: Modify: `derived.snapshot_features_v1` query (if training scripts switch to canonical dataset instead of ESPN tables directly)
- **Estimated Effort**: 8-12 hours
  - Feature engineering design: 1-2 hours
  - Code changes (`build_design_matrix()`, training scripts): 3-4 hours
  - Testing and validation: 2-3 hours
  - Grid search testing: 2-3 hours
- **Technical Complexity**: Medium (feature engineering, model integration, data handling)
- **Risk Level**: Low-Medium (backward compatibility with existing models, NULL handling for games without opening odds)

**Sprint Scope Recommendation**: Single Sprint (1 week)
- **Rationale**: Straightforward feature addition to existing models, focused on CatBoost implementation
- **Recommended Approach**:
  - Day 1-2: Design feature engineering approach (implied probabilities, interaction terms)
  - Day 3-4: Implement code changes (CatBoost training script, `build_design_matrix()`)
  - Day 5: Testing and validation (model training, performance comparison)
  - Day 6-7: Grid search testing and results analysis

**Dependency Analysis**:
- **Prerequisites**:
  - Opening odds data loaded in `external.sportsbook_odds_snapshots` (✅ completed)
  - Opening odds columns in `derived.snapshot_features_v1` (✅ completed via migration 039)
  - CatBoost models trained and saved (✅ existing functionality)
- **Parallel Work**: Can design feature engineering while reviewing data scientist feedback
- **Risk Mitigation**: Test on sample games first, ensure backward compatibility (existing models still work without opening odds)

---

## Current State Analysis

### Model Architecture

**Evidence**: Code inspection of `scripts/lib/_winprob_lib.py` and training scripts

**Current Model Features** (from `build_design_matrix()`):

```183:210:scripts/lib/_winprob_lib.py
def build_design_matrix(
    *,
    point_differential: np.ndarray,
    time_remaining_regulation: np.ndarray,
    possession: Iterable[str],
    preprocess: PreprocessParams,
    # Optional interaction terms (for extended model)
    score_diff_div_sqrt_time_remaining: np.ndarray | None = None,
    espn_home_prob: np.ndarray | None = None,
    espn_home_prob_lag_1: np.ndarray | None = None,
    espn_home_prob_delta_1: np.ndarray | None = None,
    period: Iterable[int] | None = None,
) -> np.ndarray:
    """
    Build design matrix with optional interaction terms.
    
    Base features (always included):
    - point_differential_scaled
    - time_remaining_regulation_scaled
    - possession_home, possession_away, possession_unknown
    
    Extended features (if provided):
    - score_diff_div_sqrt_time_remaining_scaled
    - espn_home_prob_scaled
    - espn_home_prob_lag_1_scaled
    - espn_home_prob_delta_1_scaled
    - period_1, period_2, period_3, period_4 (one-hot encoded)
    """
```

**Model Types**:
1. **Logistic Regression** (`train_winprob_logreg.py`): L2-regularized logistic regression with IRLS fitting. Requires explicit feature engineering for interactions.
2. **CatBoost** (`train_winprob_catboost.py`): Gradient boosting with categorical feature support. Can automatically discover interactions.

**Current Training Data Source**:
- Models query ESPN tables directly (`espn.probabilities_raw_items`, `espn.prob_event_state`, `espn.scoreboard_games`)
- **NOT using canonical dataset** (`derived.snapshot_features_v1`) for training (only used for simulation/grid search)
- Rationale: Training doesn't need Kalshi data, ESPN has historical data back to 2017

### Opening Odds Data Availability

**Evidence**: Migration 039 and canonical dataset structure

**Opening Odds Columns in `derived.snapshot_features_v1`**:
- `opening_moneyline_home` (NUMERIC, decimal odds, e.g., 1.85) - NULL if not available
- `opening_moneyline_away` (NUMERIC, decimal odds, e.g., 2.10) - NULL if not available
- `opening_spread` (NUMERIC, line value, e.g., -5.5) - NULL if not available
- `opening_total` (NUMERIC, line value, e.g., 220.5) - NULL if not available

**Data Source**: `external.sportsbook_odds_snapshots` table (filtered for `is_opening_line = TRUE`)

**Coverage** (TODO: Run verification queries in Command Appendix):
- Historical data: 2017-18 season onwards (from `nba_2008-2025.csv`) - TODO: Verify with Q2
- Recent data: 2025-26 season (from `nba_main_lines.csv`, Pinnacle) - TODO: Verify with Q2
- Not all games have opening odds (depends on data source coverage) - TODO: Verify with Q2

### Current Training Pipeline

**Evidence**: Code inspection of `scripts/model/train_winprob_catboost.py`

**Training Data Loading** (`_load_training_data()` function):

```90:112:scripts/model/train_winprob_logreg.py
def _load_training_data(conn, train_season_start_max: int, test_season_start: int, calib_season_start: int | None, use_interaction_terms: bool = True) -> pd.DataFrame:
    """
    Load training data directly from ESPN tables (bypasses canonical dataset).
    
    **Why ESPN tables directly?**
    - Training doesn't need Kalshi data (only needed for simulation)
    - ESPN has historical data back to 2017, Kalshi only has 2025-26
    - Canonical dataset is optimized for simulation (ESPN + Kalshi join)
    
    Maps ESPN columns to model features:
    - score_diff -> point_differential
    - time_remaining -> time_remaining_regulation
    - possession -> 'unknown' (not reliably available)
    - final_winning_team (from scoreboard_games join)
    - season_label -> season_start (extract year from "2025-26" -> 2025)
    
    If use_interaction_terms=True, also calculates:
    - score_diff_div_sqrt_time_remaining
    - espn_home_prob (normalized to 0-1)
    - espn_home_prob_lag_1 (using window function)
    - espn_home_prob_delta_1 (current - lag_1)
    - period (calculated from time_remaining)
    """
```

**Key Observation**: Training scripts query ESPN tables directly, **NOT** canonical dataset. To use opening odds, we have two options:
1. **Option A**: Modify training scripts to query canonical dataset instead (includes opening odds)
2. **Option B**: Modify training scripts to join ESPN tables with `external.sportsbook_odds_snapshots` (more complex, but preserves current approach)

**Recommendation**: Option A (query canonical dataset) is simpler and more consistent with simulation/grid search pipeline.

**CRITICAL PREREQUISITE**: Before switching to canonical dataset, must verify population parity (see "Training Data Source Parity Validation" section below).

### Database Schema and Example Data

**Evidence**: Direct database queries showing actual schema and data

#### Table: `derived.snapshot_features_v1` (Materialized View)

**Schema** (key columns relevant to opening odds integration):

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `season_label` | TEXT | NOT NULL | Season identifier (e.g., "2025-26") |
| `game_id` | TEXT | NOT NULL | ESPN game identifier |
| `sequence_number` | INTEGER | NOT NULL | Snapshot sequence within game |
| `snapshot_ts` | TIMESTAMPTZ | NOT NULL | Timestamp of snapshot |
| `espn_home_prob` | DOUBLE PRECISION | | ESPN home win probability (0-1) |
| `espn_away_prob` | DOUBLE PRECISION | | ESPN away win probability (0-1) |
| `score_diff` | INTEGER | | Point differential (home - away) |
| `time_remaining` | INTEGER | | Seconds remaining in regulation |
| `period` | INTEGER | | Quarter (1-4) |
| `score_diff_div_sqrt_time_remaining` | NUMERIC | | Interaction term: score_diff / sqrt(time_remaining + 1) |
| `espn_home_prob_lag_1` | DOUBLE PRECISION | | Previous snapshot's ESPN home prob |
| `espn_home_prob_delta_1` | DOUBLE PRECISION | | Change in ESPN home prob (current - lag_1) |
| `opening_moneyline_home` | NUMERIC | **NULLABLE** | Opening moneyline odds (decimal) for home team |
| `opening_moneyline_away` | NUMERIC | **NULLABLE** | Opening moneyline odds (decimal) for away team |
| `opening_spread` | NUMERIC | **NULLABLE** | Opening spread line (home team perspective) |
| `opening_total` | NUMERIC | **NULLABLE** | Opening total points line |

**Indexes**:
- `ux_snapshot_features_v1_pkey` UNIQUE: `(season_label, game_id, sequence_number, snapshot_ts)`
- `idx_snapshot_features_v1_game`: `(game_id, sequence_number)`
- `idx_snapshot_features_v1_season_game`: `(season_label, game_id)`

**Data Coverage** (TODO: Run verification queries in Command Appendix):
- **Total rows**: TODO - Run Q1 from Command Appendix
- **Rows with opening odds**: TODO - Run Q1 from Command Appendix
- **Rows without opening odds**: TODO - Run Q1 from Command Appendix
- **Coverage by season**: TODO - Run Q2 from Command Appendix

**Example Rows** (game with opening odds):

```
season_label |  game_id  | sequence_number |      snapshot_ts       | espn_home_prob | score_diff | time_remaining | period | opening_moneyline_home | opening_moneyline_away | opening_spread | opening_total 
--------------+-----------+-----------------+------------------------+----------------+------------+----------------+--------+------------------------+------------------------+----------------+---------------
 2025-26      | 401809235 |               4 | 2025-10-22 21:48:00-07 |          0.526 |          0 |           2880 |      1 |                  1.694 |                    2.3 |           -2.5 |         223.5
 2025-26      | 401809235 |               7 | 2025-10-22 21:49:00-07 |          0.545 |          0 |           2868 |      1 |                  1.694 |                    2.3 |           -2.5 |         223.5
 2025-26      | 401809235 |               9 | 2025-10-22 21:49:00-07 |           0.53 |          0 |           2864 |      1 |                  1.694 |                    2.3 |           -2.5 |         223.5
 2025-26      | 401809235 |              10 | 2025-10-22 21:49:00-07 |          0.545 |          0 |           2862 |      1 |                  1.694 |                    2.3 |           -2.5 |         223.5
 2025-26      | 401809235 |              11 | 2025-10-22 21:49:00-07 |          0.574 |          2 |           2859 |      1 |                  1.694 |                    2.3 |           -2.5 |         223.5
```

**Key Observations**:
- Opening odds are **constant across all snapshots** for a given game (same values repeated for each snapshot)
- Opening odds are in **decimal format** (e.g., 1.694 = implied probability of 1/1.694 = 0.590 or 59.0%)
- Opening spread is **negative** for home team favored (e.g., -2.5 means home team favored by 2.5 points)
- Opening total is in **points** (e.g., 223.5 total points expected)

**Example Rows** (game with opening odds, later in game):

```
season_label |  game_id  | sequence_number |      snapshot_ts       | espn_home_prob | score_diff | time_remaining | opening_moneyline_home | opening_moneyline_away | opening_spread | opening_total 
--------------+-----------+-----------------+------------------------+----------------+------------+----------------+------------------------+------------------------+----------------+---------------
 2025-26      | 401810272 |             373 | 2025-12-23 21:56:00-08 |          0.494 |          1 |           1227 |                   3.07 |                  1.425 |              7 |           233
 2025-26      | 401810272 |             385 | 2025-12-23 21:57:00-08 |          0.566 |          2 |           1189 |                   3.07 |                  1.425 |              7 |           233
 2025-26      | 401810272 |             393 | 2025-12-23 21:59:00-08 |          0.359 |         -2 |           1147 |                   3.07 |                  1.425 |              7 |           233
```

**Key Observations**:
- Opening odds remain constant even as game progresses (time_remaining decreases from 1227 to 1147 seconds)
- ESPN probabilities change dynamically (0.494 → 0.566 → 0.359) based on current game state
- This demonstrates why opening odds need time-weighted interactions (they become less informative as game progresses)

#### Table: `external.sportsbook_odds_snapshots` (Source Table)

**Schema**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `snapshot_id` | BIGINT | NOT NULL | `nextval(...)` | Primary key (auto-increment) |
| `espn_game_id` | TEXT | NULLABLE | | ESPN game identifier (NULL if not mapped) |
| `bookmaker` | TEXT | NOT NULL | | Sportsbook name (e.g., "pinnacle", "unknown") |
| `market_type` | TEXT | NOT NULL | | Market type: "moneyline", "spread", "total" |
| `side` | TEXT | NULLABLE | | Side: "home", "away", "over", "under" |
| `line_value` | NUMERIC | NULLABLE | | Spread or total line value (NULL for moneyline) |
| `odds_american` | INTEGER | NULLABLE | | American odds format (e.g., -110, +150) |
| `odds_decimal` | NUMERIC | NULLABLE | | Decimal odds format (e.g., 1.91, 2.50) |
| `implied_prob` | NUMERIC | NULLABLE | | Implied probability (1 / odds_decimal) |
| `snapshot_timestamp` | TIMESTAMPTZ | NULLABLE | | When odds were recorded (NULL for historical single-date data) |
| `is_closing_line` | BOOLEAN | | FALSE | True if this is closing line |
| `is_opening_line` | BOOLEAN | | FALSE | True if this is opening line |
| `source_dataset` | TEXT | NOT NULL | | Source: "nba_2008_2025", "nba_main_lines", etc. |
| `raw_data` | JSONB | NULLABLE | | Original row data for reprocessing |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | Record creation timestamp |

**Indexes**:
- `sportsbook_odds_snapshots_pkey` PRIMARY KEY: `(snapshot_id)`
- `idx_sportsbook_odds_opening`: `(espn_game_id, is_opening_line)` WHERE `is_opening_line = TRUE`
- `idx_sportsbook_odds_snapshots_book`: `(bookmaker, market_type)`
- `idx_sportsbook_odds_snapshots_game`: `(espn_game_id, snapshot_timestamp)`
- `sportsbook_odds_snapshots_espn_game_id_bookmaker_market_typ_key` UNIQUE: `(espn_game_id, bookmaker, market_type, side, snapshot_timestamp, source_dataset)`

**Example Rows** (opening lines from historical data, `nba_2008_2025`):

```
 espn_game_id | bookmaker | market_type | side | line_value |   odds_decimal   |   implied_prob    | is_opening_line | source_dataset 
--------------+-----------+-------------+------+------------+------------------+-------------------+-----------------+----------------
 400974437    | unknown   | moneyline   | away |        NaN |             2.66 |  0.37593984962406 | t               | nba_2008_2025
 400974437    | unknown   | moneyline   | home |        NaN | 1.51282051282051 | 0.661016949152542 | t               | nba_2008_2025
 400974437    | unknown   | spread      | home |        4.5 |                  |                   | t               | nba_2008_2025
 400974437    | unknown   | total       | over |        216 |                  |                   | t               | nba_2008_2025
 400974438    | unknown   | moneyline   | away |        NaN |             4.64 |  0.21551724137931 | t               | nba_2008_2025
 400974438    | unknown   | moneyline   | home |        NaN | 1.21276595744681 | 0.824561403508772 | t               | nba_2008_2025
 400974438    | unknown   | spread      | home |          9 |                  |                   | t               | nba_2008_2025
 400974438    | unknown   | total       | over |      231.5 |                  |                   | t               | nba_2008_2025
```

**Key Observations**:
- Historical data (`nba_2008_2025`) has `bookmaker = "unknown"` (source not specified)
- `snapshot_timestamp` is NULL for historical data (single date per game)
- `implied_prob` is pre-calculated (1 / odds_decimal)
- Multiple rows per game (one per market type: moneyline home, moneyline away, spread, total)

**Example Rows** (opening lines from recent data, `nba_main_lines` - Pinnacle):

```
 espn_game_id | bookmaker | market_type | side  | line_value | odds_american | odds_decimal |   implied_prob    |   snapshot_timestamp   | is_opening_line | source_dataset 
--------------+-----------+-------------+-------+------------+---------------+--------------+-------------------+------------------------+-----------------+----------------
              | pinnacle  | moneyline   | away  |        NaN |           206 |         3.06 | 0.326797385620915 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
              | pinnacle  | moneyline   | home  |        NaN |          -255 |        1.392 | 0.718390804597701 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
              | pinnacle  | spread      | away  |        6.5 |          -109 |        1.917 | 0.521648408972353 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
              | pinnacle  | spread      | home  |       -6.5 |          -107 |        1.934 | 0.517063081695967 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
              | pinnacle  | total       | over  |        226 |          -109 |        1.917 | 0.521648408972353 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
              | pinnacle  | total       | under |        226 |          -107 |        1.934 | 0.517063081695967 | 2025-09-10 16:14:26-07 | t               | nba_main_lines
```

**Key Observations**:
- Recent data (`nba_main_lines`) has `bookmaker = "pinnacle"` (Pinnacle Sports)
- `snapshot_timestamp` is populated (time-series data with multiple timestamps per game)
- `espn_game_id` may be NULL if game not yet mapped to ESPN games
- Both American and decimal odds formats available
- Spread is represented as positive/negative values (e.g., -6.5 for home team favored by 6.5 points)

**Data Transformation Notes**:
- The canonical dataset (`derived.snapshot_features_v1`) joins `external.sportsbook_odds_snapshots` to extract opening lines
- Only rows with `is_opening_line = TRUE` are used
- Multiple markets per game are aggregated into single columns:
  - `opening_moneyline_home`: From `market_type = 'moneyline' AND side = 'home'`
  - `opening_moneyline_away`: From `market_type = 'moneyline' AND side = 'away'`
  - `opening_spread`: From `market_type = 'spread' AND side = 'home'` (line_value)
  - `opening_total`: From `market_type = 'total' AND side = 'over'` (line_value)

---

## CatBoost Model Training Logic

**Evidence**: Code inspection of `scripts/model/train_winprob_catboost.py`

### Overview

The CatBoost training pipeline follows a leak-proof, game-level split policy to train win-probability models. The process involves data loading, feature engineering, model training, calibration, and artifact saving.

### Step-by-Step Training Process

#### Step 1: Data Loading (`_load_training_data()`)

**Source**: ESPN tables directly (not canonical dataset currently)

**Query Structure**:
- **Base Query**: Joins `espn.probabilities_raw_items` with `espn.prob_event_state` and `espn.scoreboard_games`
- **Window Functions**: Uses `LAG()` to compute lagged features (`espn_home_prob_lag_1`)
- **Feature Calculation**: Computes interaction terms (`score_diff_div_sqrt_time_remaining`, `espn_home_prob_delta_1`)
- **Period Calculation**: Derives period (1-4) from `time_remaining`:
  - Q1: > 2160 seconds
  - Q2: 1440-2160 seconds
  - Q3: 720-1440 seconds
  - Q4: 0-720 seconds

**Key Columns Loaded**:
- `point_differential` (from `point_differential` in `prob_event_state`)
- `time_remaining_regulation` (from `time_remaining` in `prob_event_state`)
- `possession` (defaults to 'unknown' - not reliably available)
- `final_winning_team` (from `scoreboard_games`: 0 = home won, 1 = away won)
- `season_start` (extracted from `season_label` via regex: `SUBSTRING(season_label FROM '^([0-9]{4})')`)

**If Interaction Terms Enabled**:
- `score_diff_div_sqrt_time_remaining` = `score_diff / sqrt(time_remaining + 1)`
- `espn_home_prob` (normalized to 0-1 if stored as 0-100)
- `espn_home_prob_lag_1` (previous snapshot's probability)
- `espn_home_prob_delta_1` = `espn_home_prob - espn_home_prob_lag_1`
- `period` (1-4, calculated from time_remaining)

**Filtering**:
- Only rows with `time_remaining IS NOT NULL` and `point_differential IS NOT NULL`
- Only rows with `final_winning_team IS NOT NULL` (after join)
- Season filtering based on `season_start`:
  - Training: `season_start <= train_season_start_max` (default: 2022)
  - Calibration: `season_start == calib_season_start` (default: 2023, optional)
  - Test: `season_start == test_season_start` (default: 2024, not used in training)

#### Step 2: Train/Calibration/Test Split

**Split Policy**: Game-level, leak-proof (no data leakage between splits)

**Split Logic**:
```python
season = df["season_start"].astype(int).to_numpy()
train_mask = season <= train_season_start_max  # e.g., <= 2022
test_mask = season == test_season_start         # e.g., == 2024
calib_mask = season == calib_season_start       # e.g., == 2023 (optional)
```

**Key Points**:
- **Leak-proof**: Splits by season, not by random rows (prevents future data from leaking into training)
- **Game-level**: All snapshots from a game stay in the same split
- **Calibration set**: Optional, used only for probability calibration (Platt/Isotonic scaling)
- **Test set**: Held out completely, not used in training or calibration

#### Step 3: Feature Preprocessing

**Normalization Parameters** (computed from **training set only**):

```python
# Base features
pd_mean = mean(point_differential[train_mask])
pd_std = std(point_differential[train_mask])
tr_mean = mean(time_remaining_regulation[train_mask])
tr_std = std(time_remaining_regulation[train_mask])

# Interaction terms (if enabled)
score_diff_div_sqrt_time_rem_mean = mean(score_diff_div_sqrt_time_remaining[train_mask])
score_diff_div_sqrt_time_rem_std = std(score_diff_div_sqrt_time_remaining[train_mask])
espn_home_prob_mean = mean(espn_home_prob[train_mask])
espn_home_prob_std = std(espn_home_prob[train_mask])
# ... similar for lag_1 and delta_1
```

**PreprocessParams Object**:
- Stores all normalization parameters (mean/std for each feature)
- Used by `build_design_matrix()` to scale features consistently
- **Critical**: Parameters computed from training set only (prevents data leakage)

#### Step 4: Design Matrix Construction (`build_design_matrix()`)

**Function**: `scripts/lib/_winprob_lib.py:build_design_matrix()`

**Base Features** (always included):
1. `point_differential_scaled` = `(point_differential - pd_mean) / pd_std`
2. `time_remaining_regulation_scaled` = `(time_remaining_regulation - tr_mean) / tr_std`
3. `possession_home` (one-hot: 1 if possession == "home", else 0)
4. `possession_away` (one-hot: 1 if possession == "away", else 0)
5. `possession_unknown` (one-hot: 1 if possession == "unknown", else 0)

**Extended Features** (if interaction terms enabled):
6. `score_diff_div_sqrt_time_remaining_scaled` = `(score_diff_div_sqrt_time_remaining - mean) / std`
7. `espn_home_prob_scaled` = `(espn_home_prob - mean) / std`
8. `espn_home_prob_lag_1_scaled` = `(espn_home_prob_lag_1 - mean) / std`
9. `espn_home_prob_delta_1_scaled` = `(espn_home_prob_delta_1 - mean) / std`
10. `period_1`, `period_2`, `period_3`, `period_4` (one-hot encoded)

**Output**: `X_train` (numpy array, shape: `[n_samples, n_features]`)

#### Step 5: Label Construction

**Label**: `y_home_win` (binary: 1 if home won, 0 if away won)

```python
y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)
y_train = y[train_mask]
```

**Key Points**:
- `final_winning_team = 0` means home won → `y_home_win = 1`
- `final_winning_team = 1` means away won → `y_home_win = 0`

#### Step 6: CatBoost Model Training

**Model Configuration**:
```python
model = CatBoostClassifier(
    iterations=1000,           # Number of boosting iterations
    depth=6,                    # Tree depth
    learning_rate=0.1,          # Learning rate
    loss_function='Logloss',    # Binary cross-entropy loss
    eval_metric='AUC',          # Evaluation metric (Area Under Curve)
    verbose=100,                # Print progress every 100 iterations
    random_seed=42,             # For reproducibility
    allow_writing_files=False,  # Don't write temp files
)
```

**Training Process**:
1. **Fit model** on training set: `model.fit(X_train, y_train, eval_set=eval_set)`
2. **Eval Set** (optional): If calibration season exists, uses calibration set for early stopping/evaluation
3. **Automatic Feature Interactions**: CatBoost discovers interactions automatically (no manual engineering needed)
4. **Handles Missing Values**: CatBoost natively handles NULL/missing values (important for opening odds)

**Model Output**: Trained CatBoost model (ensemble of decision trees)

#### Step 7: Model Saving

**CatBoost Model File**: Saved as `.cbm` file (CatBoost binary format)
```python
catboost_model_path = out_path.with_suffix(".cbm")
model.save_model(str(catboost_model_path))
```

**Relative Path**: Stored in artifact as filename only (assumes same directory as artifact JSON)

#### Step 8: Probability Calibration (Optional)

**Purpose**: Calibrate raw model probabilities to better match true probabilities

**Calibration Set**: Uses calibration season data (e.g., 2023 season)

**Methods**:
1. **Platt Scaling** (default): Logistic regression on model probabilities
   - Formula: `p_calibrated = 1 / (1 + exp(-(alpha * logit(p_raw) + beta)))`
   - Fits `alpha` and `beta` parameters on calibration set
2. **Isotonic Regression**: Non-parametric monotonic transformation
   - More flexible than Platt, but can overfit on small calibration sets

**Calibration Process**:
```python
# Get base model probabilities on calibration set
p_base = model.predict_proba(X_calib)[:, 1]  # Probability of class 1 (home win)

# Fit calibrator
if calibration_method == "isotonic":
    isotonic = fit_isotonic_calibrator_on_probs(p_base=p_base, y=y_calib)
else:  # default to platt
    platt = fit_platt_calibrator_on_probs(p_base=p_base, y=y_calib)
```

**Calibration Parameters**: Stored in artifact (`platt` or `isotonic` field)

#### Step 9: Artifact Creation and Saving

**Artifact Structure** (`WinProbArtifact`):
- `created_at_utc`: Timestamp
- `version`: Version string (e.g., "v1")
- `train_season_start_max`: Max season used for training
- `calib_season_start`: Season used for calibration (optional)
- `test_season_start`: Held-out test season
- `buckets_seconds_remaining`: Time buckets for metadata (e.g., [2880, 2820, 2760, ...])
- `preprocess`: `PreprocessParams` object (normalization parameters)
- `feature_names`: List of feature names (for interpretability)
- `model`: `ModelParams` object (dummy for CatBoost, not used for prediction)
- `platt`: `PlattCalibrator` object (optional)
- `isotonic`: `IsotonicCalibrator` object (optional)
- `model_type`: "catboost"
- `catboost_model_path`: Relative path to `.cbm` file

**Saving**:
- Artifact saved as JSON file (e.g., `artifacts/winprob_catboost_v1.json`)
- CatBoost model saved as `.cbm` file (e.g., `artifacts/winprob_catboost_v1.cbm`)
- Roundtrip validation: Loads artifact back to verify it's valid

### Key Design Decisions

1. **Why ESPN Tables Directly?**
   - Training doesn't need Kalshi data (only needed for simulation)
   - ESPN has historical data back to 2017, Kalshi only has 2025-26
   - Canonical dataset is optimized for simulation (ESPN + Kalshi join)

2. **Why Game-Level Splits?**
   - Prevents data leakage (all snapshots from a game stay together)
   - More realistic evaluation (model performance on unseen games)

3. **Why Calibration?**
   - Raw model probabilities may not be well-calibrated (e.g., 60% predictions may only win 55% of the time)
   - Calibration improves probability estimates for trading decisions

4. **Why CatBoost?**
   - Can discover feature interactions automatically
   - Handles missing values natively (important for opening odds)
   - Robust to outliers and non-linear relationships

---

## Grid Search Logic

**Evidence**: Code inspection of `scripts/trade/grid_search_hyperparameters.py` and `scripts/trade/simulate_trading_strategy.py`

### Overview

Grid search systematically tests entry/exit threshold combinations across train/valid/test splits to identify optimal trading strategy parameters. The process involves game selection, parameter grid generation, parallel simulation execution, and results aggregation.

### Step-by-Step Grid Search Process

#### Step 1: Game Selection

**Source**: Games with both ESPN and Kalshi data for a given season

**Query** (`get_game_ids_from_season()`):
```sql
WITH kalshi_games AS MATERIALIZED (
    SELECT DISTINCT km.espn_event_id
    FROM kalshi.markets km
    WHERE km.espn_event_id IS NOT NULL
)
SELECT DISTINCT p.game_id
FROM espn.probabilities_raw_items p
JOIN kalshi_games kg ON kg.espn_event_id = p.game_id
WHERE p.season_label = %s
GROUP BY p.game_id
HAVING COUNT(*) > 100  -- At least 100 snapshots per game
ORDER BY p.game_id
```

**Key Points**:
- Only games with both ESPN probabilities and Kalshi market data
- Minimum 100 snapshots per game (ensures sufficient data for simulation)
- Can also load from JSON file (`--game-list` option)

#### Step 2: Train/Valid/Test Split

**Split Function**: `split_games()`

**Split Logic**:
```python
# Sort for deterministic order
sorted_game_ids = sorted(set(game_ids))

# Shuffle with seed for reproducibility
rng = random.Random(config.seed)  # Default seed: 42
shuffled = sorted_game_ids.copy()
rng.shuffle(shuffled)

# Calculate split indices
total = len(shuffled)
train_end = int(total * config.train_ratio)      # Default: 70%
valid_end = train_end + int(total * config.valid_ratio)  # Default: 15%
# test_end = total (remaining 15%)

train_games = shuffled[:train_end]
valid_games = shuffled[train_end:valid_end]
test_games = shuffled[valid_end:]
```

**Key Points**:
- **Deterministic**: Same seed always produces same split
- **Game-level**: All snapshots from a game stay in the same split
- **Reproducible**: Split lists saved to disk (`train_games.json`, `valid_games.json`, `test_games.json`)
- **Default Ratios**: 70% train / 15% valid / 15% test

#### Step 3: Parameter Grid Generation

**Grid Function**: `generate_grid()`

**Constraints**:
- `entry_threshold > 0` (must be positive)
- `exit_threshold >= 0` (can be zero)
- `exit_threshold < entry_threshold` (exit must be less than entry)

**Grid Generation**:
```python
# Generate entry thresholds
entry_values = []
entry = config.entry_min  # Default: 0.02
while entry <= config.entry_max:  # Default: 0.20
    if entry > 0:
        entry_values.append(entry)
    entry += config.entry_step  # Default: 0.01

# Generate exit thresholds
exit_values = []
exit = config.exit_min  # Default: 0.00
while exit <= config.exit_max:  # Default: 0.05
    if exit >= 0:
        exit_values.append(exit)
    exit += config.exit_step  # Default: 0.005

# Generate combinations with constraint: exit < entry
combinations = []
for entry_threshold in entry_values:
    for exit_threshold in exit_values:
        if exit_threshold < entry_threshold:
            combinations.append((entry_threshold, exit_threshold))
```

**Example Grid** (default parameters):
- Entry range: 0.02 to 0.20, step 0.01 → 19 values
- Exit range: 0.00 to 0.05, step 0.005 → 11 values
- Valid combinations: ~99 (19 × 11 minus invalid ones where exit >= entry)

#### Step 4: Model Loading (Optional)

**Model Selection**: If `model_name` provided, loads model artifact

**Supported Models**:
- `logreg_platt`: Logistic Regression with Platt calibration
- `logreg_isotonic`: Logistic Regression with Isotonic calibration
- `catboost_platt`: CatBoost with Platt calibration
- `catboost_isotonic`: CatBoost with Isotonic calibration
- `None`: Uses ESPN probabilities directly (no model)

**Model Loading**:
```python
model_artifact = load_model_artifact(config.model_name) if config.model_name else None
```

**Key Points**:
- Model loaded once per combination (not per game)
- Model used to generate probabilities instead of ESPN probabilities
- Pre-computed probabilities preferred (from `derived.model_probabilities_v1`)

#### Step 5: Parallel Execution

**Design Pattern**: Map-Reduce Pattern

**Execution**:
- **Workers**: Default 8 parallel workers (configurable via `--workers`)
- **Task Distribution**: Each worker processes one parameter combination across all splits
- **Implementation**: `ThreadPoolExecutor` with `process_combination()` function

**Process Combination Flow**:
```python
def process_combination(combination, game_splits, config, dsn):
    entry_threshold, exit_threshold = combination
    
    # Load model once per combination
    model_artifact = load_model_artifact(config.model_name) if config.model_name else None
    
    results = {
        'entry_threshold': entry_threshold,
        'exit_threshold': exit_threshold,
    }
    
    # Run simulation for each split
    with connect(dsn) as conn:
        for split_name in ['train', 'valid', 'test']:
            game_ids = game_splits[split_name]
            split_results = run_simulation_for_games(
                conn, game_ids, entry_threshold, exit_threshold,
                config, model_artifact=model_artifact
            )
            results[split_name] = split_results
    
    return results
```

#### Step 6: Simulation for Each Game

**Simulation Function**: `run_simulation_for_games()`

**Process**:
1. **For each game** in the split:
   - Load aligned data (`get_aligned_data()`)
   - Run trading simulation (`simulate_trading_strategy()`)
   - Aggregate trades and metrics

2. **Aligned Data Loading** (`get_aligned_data()`):
   - Queries `derived.snapshot_features_v1` canonical dataset
   - Gets ESPN probabilities (or model probabilities if model provided)
   - Gets Kalshi market prices (bid/ask/mid)
   - Applies time filtering (`exclude_first_seconds`, `exclude_last_seconds`)
   - Returns list of snapshots with aligned timestamps

3. **Trading Simulation** (`simulate_trading_strategy()`):
   - **Entry Logic**: 
     - Long ESPN: Buy when `espn_prob > kalshi_price + entry_threshold`
     - Short ESPN: Sell when `espn_prob < kalshi_price - entry_threshold`
   - **Exit Logic**: 
     - Close position when `abs(espn_prob - kalshi_price) < exit_threshold`
   - **P&L Calculation**:
     - Gross profit: Price difference × bet_amount
     - Fees: Kalshi trading fees (7% × price × (1 - price) × bet_amount)
     - Net profit: Gross profit - Fees - Slippage

4. **Metrics Aggregation**:
   - `num_trades`: Total number of trades
   - `net_profit_dollars`: Sum of net profit across all trades
   - `win_rate`: Percentage of profitable trades
   - `avg_net_profit_per_trade`: Average net profit per trade
   - `profit_factor`: Gross profits / abs(gross losses)
   - `max_drawdown`: Maximum peak-to-trough decline
   - `total_fees`: Sum of all trading fees
   - `avg_hold_time`: Average position duration in seconds
   - `is_valid`: True if `num_trades >= min_trade_count` (default: 200)

#### Step 7: Results Aggregation

**Per Combination Results**:
```python
{
    'entry_threshold': 0.05,
    'exit_threshold': 0.02,
    'train': {
        'net_profit_dollars': 1234.56,
        'num_trades': 500,
        'win_rate': 0.55,
        # ... other metrics
    },
    'valid': {
        # ... same structure
    },
    'test': {
        # ... same structure
    }
}
```

**Results Storage**:
- **CSV Files**: One per split (`grid_results_train.csv`, `grid_results_valid.csv`, `grid_results_test.csv`)
- **JSON Files**: One per split with metadata (`grid_results_train.json`, etc.)
- **Final Selection**: `final_selection.json` (best parameters based on validation set)

#### Step 8: Best Parameter Selection

**Selection Logic**:
1. **Filter Valid Combinations**: Only combinations with `num_trades >= min_trade_count` (default: 200)
2. **Sort by Performance**: Sort train set results by `net_profit_dollars` (descending)
3. **Top N Selection**: Take top N combinations from train set (default: 10)
4. **Validation Check**: Evaluate top N on validation set
5. **Final Selection**: Choose combination with best validation performance

**Selection Criteria**:
- Primary: `net_profit_dollars` (maximize profit)
- Secondary: `win_rate`, `profit_factor`, `max_drawdown` (for tie-breaking)

#### Step 9: Caching (Optional)

**Cache Key**: Generated from all grid search parameters (season, thresholds, fees, etc.)

**Cache Check**: Before running grid search, checks cache for existing results

**Cache Hit**: If found, loads results from cache (skips simulation)

**Cache Miss**: Runs grid search normally, saves results to cache

**Cache TTL**: 30 days (configurable)

### Key Design Decisions

1. **Why Game-Level Splits?**
   - Prevents data leakage (all snapshots from a game stay together)
   - More realistic evaluation (performance on unseen games)

2. **Why Parallel Execution?**
   - Grid search is computationally expensive (99 combinations × 3 splits × N games)
   - Parallel execution reduces total time (linear speedup with workers)

3. **Why Train/Valid/Test Splits?**
   - **Train**: Used for parameter selection (top N combinations)
   - **Valid**: Used for final selection (best combination from top N)
   - **Test**: Used for final reporting only (not used in selection, prevents overfitting)

4. **Why Minimum Trade Count?**
   - Ensures statistical significance (combinations with few trades may have unreliable metrics)
   - Prevents overfitting to small sample sizes

5. **Why Caching?**
   - Grid search is expensive (can take hours)
   - Same parameters produce same results (deterministic)
   - Caching enables quick iteration on analysis/visualization

### Trading Strategy Logic

**Entry Conditions**:
- **Long ESPN** (buy Kalshi home market): When `espn_prob > kalshi_price + entry_threshold`
  - Example: ESPN says 60%, Kalshi says 55%, entry_threshold = 0.05 → Enter long
- **Short ESPN** (sell Kalshi home market): When `espn_prob < kalshi_price - entry_threshold`
  - Example: ESPN says 50%, Kalshi says 55%, entry_threshold = 0.05 → Enter short

**Exit Conditions**:
- Close position when `abs(espn_prob - kalshi_price) < exit_threshold`
  - Example: Position entered at 0.05 divergence, exit when divergence < 0.02

**P&L Calculation**:
- **Gross Profit**: Price difference × bet_amount
- **Fees**: Kalshi trading fees = 7% × price × (1 - price) × bet_amount
- **Slippage**: Optional slippage cost (default: 0%)
- **Net Profit**: Gross profit - Fees - Slippage

**Key Points**:
- Uses bid/ask prices for execution (not mid price)
- Long positions: Buy at ask, sell at bid
- Short positions: Sell at bid, buy back at ask
- Fees applied on both entry and exit

---

## Training Data Source Parity Validation (Required)

**Evidence**: Must be verified before switching training data source

**Purpose**: Before modifying training scripts to use `derived.snapshot_features_v1` instead of ESPN tables directly, we must prove that the canonical dataset contains the same universe of games and snapshots as the ESPN-direct query.

**Why This Matters**:
- `snapshot_features_v1` filters to games with Kalshi data (for simulation purposes)
- Training doesn't need Kalshi data, so switching may exclude games
- If parity fails, we must either:
  - Keep ESPN-direct and join odds by `game_id` (Option B)
  - Build a training-specific dataset/materialized view that includes odds without Kalshi constraints

### Validation Queries

**Q1: Game and Snapshot Count Comparison by Season**

```sql
-- ESPN-direct training query game/snapshot counts (what current training uses)
WITH espn_base AS (
    SELECT 
        p.game_id,
        p.event_id,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start
    FROM espn.probabilities_raw_items p
    INNER JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
)
SELECT 
    season_start,
    COUNT(DISTINCT game_id) AS game_count,
    COUNT(DISTINCT (game_id, event_id)) AS unique_snapshot_count,
    COUNT(*) AS snapshot_count
FROM espn_base
GROUP BY season_start
ORDER BY season_start;
```

**Expected Output to Paste Here**:
```
season_start | game_count | snapshot_count
-------------+------------+----------------
[Paste results here]
```

**Q2: Canonical Dataset Game and Snapshot Count Comparison**

```sql
-- snapshot_features_v1 game/snapshot counts (what we'd switch to)
SELECT 
    CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
    COUNT(DISTINCT game_id) AS game_count,
    COUNT(DISTINCT (season_label, game_id, sequence_number, snapshot_ts)) AS unique_snapshot_count,
    COUNT(*) AS snapshot_count
FROM derived.snapshot_features_v1
GROUP BY season_start
ORDER BY season_start;
```

**Expected Output to Paste Here**:
```
season_start | game_count | unique_snapshot_count | snapshot_count
-------------+------------+----------------------+----------------
[Paste results here]
```

**Note**: `unique_snapshot_count` uses the canonical dataset's unique key `(season_label, game_id, sequence_number, snapshot_ts)`. It should equal `snapshot_count` if the materialized view has no duplicates.

**Q3: Distribution Comparison (Time Remaining Buckets)**

```sql
-- ESPN-direct time_remaining distribution
WITH espn_data AS (
    SELECT 
        e.time_remaining,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start
    FROM espn.probabilities_raw_items p
    LEFT JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
        AND CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) <= 2022
)
SELECT 
    CASE 
        WHEN time_remaining > 2400 THEN '2880-2400'
        WHEN time_remaining > 1800 THEN '2400-1800'
        WHEN time_remaining > 1200 THEN '1800-1200'
        WHEN time_remaining > 600 THEN '1200-600'
        WHEN time_remaining > 120 THEN '600-120'
        ELSE '120-0'
    END AS time_bucket,
    COUNT(*) AS snapshot_count
FROM espn_data
GROUP BY time_bucket
ORDER BY time_bucket DESC;
```

**Expected Output to Paste Here**:
```
time_bucket | snapshot_count
------------+----------------
[Paste results here]
```

```sql
-- snapshot_features_v1 time_remaining distribution
SELECT 
    CASE 
        WHEN time_remaining > 2400 THEN '2880-2400'
        WHEN time_remaining > 1800 THEN '2400-1800'
        WHEN time_remaining > 1200 THEN '1800-1200'
        WHEN time_remaining > 600 THEN '1200-600'
        WHEN time_remaining > 120 THEN '600-120'
        ELSE '120-0'
    END AS time_bucket,
    COUNT(*) AS snapshot_count
FROM derived.snapshot_features_v1
WHERE CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) <= 2022
GROUP BY time_bucket
ORDER BY time_bucket DESC;
```

**Expected Output to Paste Here**:
```
time_bucket | snapshot_count
------------+----------------
[Paste results here]
```

### Validation Criteria

**Pass Criteria** (all must be true):
1. **Game Count Parity**: `snapshot_features_v1` game counts per season are within 5% of ESPN-direct counts
2. **Snapshot Count Parity**: `snapshot_features_v1` snapshot counts per season are within 5% of ESPN-direct counts
3. **Distribution Similarity**: Time bucket distributions are similar (no major shifts)

**If Parity Fails**:
- **Option 1**: Keep ESPN-direct query, join with `external.sportsbook_odds_snapshots` by `game_id` and date
- **Option 2**: Create training-specific materialized view that includes opening odds without Kalshi filter:
  ```sql
  CREATE MATERIALIZED VIEW derived.training_features_v1 AS
  SELECT 
      -- ESPN features (from prob_event_state, probabilities_raw_items)
      -- Opening odds (from external.sportsbook_odds_snapshots)
      -- NO Kalshi filter
  FROM espn.probabilities_raw_items p
  LEFT JOIN espn.prob_event_state e ON ...
  LEFT JOIN external.sportsbook_odds_snapshots o ON ...
  WHERE e.time_remaining IS NOT NULL
    AND e.point_differential IS NOT NULL;
  ```

**Decision Point**: Cannot proceed with Option A (canonical dataset) until parity is validated.

---

## Technical Assessment

### Design Pattern Analysis

#### Design Pattern Analysis: Feature Engineering Pattern

**Pattern Name**: Feature Engineering Pattern  
**Pattern Category**: Data Processing  
**Pattern Intent**: Transform raw data (opening odds) into model-ready features (implied probabilities, interaction terms)

**Implementation**:
- **Raw Data**: Opening odds (decimal format: 1.85, 2.10)
- **Transformation 1**: Convert to raw implied probabilities (`p_home_raw = 1 / opening_moneyline_home`, `p_away_raw = 1 / opening_moneyline_away`)
- **Transformation 2**: Calculate overround (`overround = (p_home_raw + p_away_raw) - 1`)
- **Transformation 3**: De-vig to fair probabilities (`p_home_fair = p_home_raw / (p_home_raw + p_away_raw)`)
- **Transformation 4**: Create decay-weighted interactions (if needed): `p_home_fair * w` where `w = time_remaining / 2880` (decay weight decreases as time approaches 0)
- **Output**: Features ready for `build_design_matrix()`

**Benefits**:
- Converts odds to probability space (consistent with model output)
- Captures information decay via time-weighted interactions
- Maintains interpretability (implied probabilities are intuitive)

**Trade-offs**:
- Requires domain knowledge (understanding how odds relate to probabilities)
- Interaction term design requires experimentation (which interaction works best?)
- NULL handling needed (not all games have opening odds)

**Why This Pattern**: Standard approach in sports analytics - convert market odds to probabilities and create context-aware features.

### Algorithm Analysis

#### Algorithm Analysis: CatBoost Gradient Boosting

**Algorithm Name**: CatBoost (Categorical Boosting)  
**Algorithm Type**: Gradient Boosting (ensemble learning)  
**Big O Notation**: 
- Training: O(n × m × d × iterations) where n = samples, m = features, d = tree depth
- Prediction: O(iterations × d) per sample

**Algorithm Description**:
- Ensemble of decision trees trained sequentially
- Each tree corrects errors of previous trees
- Handles categorical features natively
- **Can automatically discover feature interactions** without explicit engineering

**Use Case**: 
- Win probability prediction from game state + opening odds
- Handles non-linear relationships and interactions
- Robust to outliers and missing values (can handle NULL opening odds)

**Performance Characteristics**:
- Best Case: O(n × m × d × iterations) - Linear in dataset size
- Average Case: Same as best case (deterministic algorithm)
- Worst Case: Same as best case
- Memory Usage: O(iterations × nodes_per_tree) - Stores ensemble of trees

**Why This Algorithm**: 
- Data scientist recommendation: "just use catboost"
- Can discover interaction terms automatically (no manual feature engineering needed)
- Handles missing values (opening odds may be NULL for some games)
- Better suited for complex feature interactions than Logistic Regression

#### Algorithm Analysis: Feature Engineering (Logistic Regression Approach)

**Algorithm Name**: Manual Feature Engineering for Logistic Regression  
**Algorithm Type**: Feature Transformation  
**Big O Notation**: 
- Feature computation: O(n × m) where n = samples, m = features
- Model training: O(n × m² × iterations) for IRLS

**Algorithm Description**:
- Explicitly compute interaction terms (e.g., `opening_odds / time_remaining`)
- Scale features (mean normalization, standard deviation scaling)
- One-hot encode categorical features (period, possession)
- Pass to Logistic Regression model

**Use Case**: 
- Creating time-weighted interaction terms for opening odds
- Required for Logistic Regression (cannot discover interactions automatically)

**Performance Characteristics**:
- Feature computation: O(n) - Linear in dataset size
- Scalability: Good (simple arithmetic operations)

**Why This Algorithm**: 
- Required if using Logistic Regression
- Data scientist recommendation: "drop the logistic there's no real point in running it until we add interaction terms"
- **Recommendation**: Focus on CatBoost first, add Logistic Regression later if needed

### Data Scientist Recommendations Analysis

**Source**: Discord conversation with dta (data scientist)

**Recommendation 1**: "add the odds data as a parameter"
- **Interpretation**: Add opening odds as features to the model
- **Implementation**: Include `opening_moneyline_home`, `opening_moneyline_away` (and possibly `opening_spread`, `opening_total`) as features
- **Rationale**: Opening odds represent pre-game market consensus, valuable signal for prediction

**Recommendation 2**: "we may need interaction terms bc we're really interested in the relation between the terms"
- **Interpretation**: Opening odds should interact with other features (especially time)
- **Implementation**: For CatBoost, let it discover interactions automatically. For Logistic Regression, create decay-weighted interactions (e.g., `p_home_fair * w` where `w = time_remaining / 2880` decreases as time → 0)
- **Rationale**: The relationship between opening odds and win probability depends on game context (time remaining, current score). CatBoost can discover these automatically.

**Recommendation 3**: "like the odds mean very little with 2 minutes in the game"
- **Interpretation**: Opening odds information value **decays over time** - more informative early in game, less informative late
- **Implementation**: Use decay weights that **decrease** as time approaches 0 (e.g., `w = time_remaining / 2880`), then multiply: `opening_prob * w`
- **Rationale**: Late in the game, current score/time dominates; opening odds become irrelevant
- **Critical Fix**: Original interpretation suggested `opening_odds / time_remaining`, which **increases** impact late game (backwards). Correct approach: multiply by decay weight that shrinks toward 0.

**Recommendation 4**: "just use catboost"
- **Interpretation**: Use CatBoost instead of Logistic Regression
- **Implementation**: Focus on `train_winprob_catboost.py`, can defer `train_winprob_logreg.py`
- **Rationale**: CatBoost can discover interactions automatically, Logistic Regression requires explicit engineering

**Recommendation 5**: "drop the logistic there's no real point in running it until we add interaction terms"
- **Interpretation**: Don't add opening odds to Logistic Regression until interaction terms are properly engineered
- **Implementation**: Focus on CatBoost first, add Logistic Regression later if needed
- **Rationale**: Logistic Regression without interactions may not benefit from opening odds; CatBoost can discover interactions automatically

**Recommendation 6**: "something like odds divided by time or score divided by time"
- **Interpretation**: Suggested interaction term formulas (data scientist's shorthand)
- **Corrected Implementation** (for information decay):
  - Decay weight: `w = time_remaining / 2880` (or `sqrt(time_remaining / 2880)`, or `log1p(time_remaining) / log1p(2880)`)
  - Weighted feature: `opening_prob_home_fair * w` (weight decreases as time → 0)
  - Note: `score_diff / time_remaining` already exists as `score_diff_div_sqrt_time_remaining` (different formula, but captures similar concept)
- **Rationale**: Decay weights capture information decay (odds matter more early, less late)
- **For CatBoost**: Start with direct features (`opening_prob_home_fair`, `time_remaining`) and let it discover interactions automatically

---

## Recommended Feature Engineering Approach

### Option 1: Simple Direct Features with De-Vigging (Baseline)

**Canonical Feature Names**:
- `opening_prob_home_fair` (de-vigged fair probability, main feature)
- `opening_overround` (vig amount, may be informative)
- `opening_spread` (direct value)
- `opening_total` (direct value)
- `has_opening_moneyline` (missingness indicator flag)
- `has_opening_spread` (missingness indicator flag)
- `has_opening_total` (missingness indicator flag)

**Note**: Do NOT include `opening_prob_away_fair` (redundant with `opening_prob_home_fair` since they sum to 1.0). Keep it optional only if later proven to help.

**Pros**:
- Simple to implement
- Fair probabilities sum to 1.0 (no overround bias)
- Interpretable (probabilities in 0-1 range)
- CatBoost can discover interactions automatically
- Missingness flags help CatBoost learn when odds are available

**Cons**:
- Doesn't explicitly capture information decay over time (CatBoost can learn this)
- May not be optimal for Logistic Regression (no interactions)

**Use Case**: Baseline implementation for CatBoost (let it discover interactions)

**Critical**: Must use fair probabilities (`opening_prob_home_fair`), not raw implied probabilities, to avoid calibration distortion from vig.

### Option 2: Decay-Weighted Interaction Terms (For Logistic Regression Only)

**Features**:
- `opening_prob_home_fair` (direct, de-vigged)
- `opening_overround` (direct)
- Decay weight: `w = time_remaining / 2880` (or `sqrt(time_remaining / 2880)`, or `log1p(time_remaining) / log1p(2880)`)
- `opening_prob_home_fair * w` (decay-weighted interaction - weight decreases as time → 0)
- `opening_spread * w` (decay-weighted spread)
- `opening_total * w` (decay-weighted total)
- `opening_spread` (direct)
- `opening_total` (direct)
- Missingness indicators: `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`

**Pros**:
- Explicitly captures information decay (odds matter more early in game, less late)
- Works well for Logistic Regression (which can't discover interactions automatically)
- Decay weight shrinks toward 0 as time approaches 0 (correct behavior)

**Cons**:
- More complex (multiple features)
- Requires scaling/normalization (interaction terms may have different scales)
- Only needed if using Logistic Regression (CatBoost can discover interactions automatically)

**Use Case**: Only if using Logistic Regression. For CatBoost, use Option 1 and let it discover interactions.

**Critical Fix**: Original formula (`opening_odds / time_remaining`) was backwards - it increases impact late game. Correct formula multiplies by decay weight that decreases.

### Option 3: CatBoost-Only (Automatic Interaction Discovery) - RECOMMENDED

**Features**:
- `opening_prob_home_fair` (de-vigged fair probability)
- `opening_overround` (vig amount, may be informative)
- `opening_spread` (direct value)
- `opening_total` (direct value)
- `time_remaining` (already exists in model)
- Missingness indicators: `has_opening_moneyline`, `has_opening_spread`, `has_opening_total`
- Let CatBoost discover interactions automatically

**Pros**:
- Simplest implementation (no manual interaction terms)
- CatBoost can find optimal interactions (may be better than manual engineering)
- Less risk of over-engineering
- Missingness flags help CatBoost learn when odds are available vs. missing

**Cons**:
- Less control over feature engineering
- May miss important interactions if data is limited
- Less interpretable (harder to understand which interactions matter)

**Use Case**: **Recommended initial approach for CatBoost** (data scientist's preference: "just use catboost", "catboost will still improve once we add interaction terms but it can figure some of it out")

---

## Implementation Recommendations

### Immediate Actions (Priority: High)

#### Recommendation 1: Add Opening Odds to CatBoost Model

**Specific Action**: Modify `train_winprob_catboost.py` to load opening odds from canonical dataset and pass to `build_design_matrix()`

**Files to Modify**:
- `scripts/lib/_winprob_lib.py`: Add opening odds parameters to `build_design_matrix()` function
- `scripts/model/train_winprob_catboost.py`: Modify `_load_training_data()` to query canonical dataset (or join with opening odds), convert odds to implied probabilities, pass to `build_design_matrix()`
- `scripts/model/precompute_model_probabilities.py`: Include opening odds when scoring snapshots (for grid search compatibility)

**Estimated Effort**: 4-6 hours
- Feature engineering design: 1 hour
- Code changes: 2-3 hours
- Testing: 1-2 hours

**Risk Level**: Low
- Backward compatible (opening odds can be NULL, models work without them)
- CatBoost handles missing values natively (keep NaNs, don't impute)
- Missingness indicators help CatBoost learn when odds are available

**Success Metrics**:
- Model trains successfully with opening odds features
- Feature importance shows opening odds contribute meaningfully
- Model performance improves on test set (Brier score, log-loss)

**Implementation Steps**:

1. **Modify `build_design_matrix()` to accept opening odds parameters**:
   ```python
   def build_design_matrix(
       *,
       point_differential: np.ndarray,
       time_remaining_regulation: np.ndarray,
       possession: Iterable[str],
       preprocess: PreprocessParams,
       # Existing interaction terms...
       # NEW: Opening odds features (canonical naming)
       opening_prob_home_fair: np.ndarray | None = None,
       opening_overround: np.ndarray | None = None,
       opening_spread: np.ndarray | None = None,
       opening_total: np.ndarray | None = None,
       has_opening_moneyline: np.ndarray | None = None,
       has_opening_spread: np.ndarray | None = None,
       has_opening_total: np.ndarray | None = None,
   ) -> np.ndarray:
   ```

2. **Convert decimal odds to fair probabilities (de-vig) in training script with safety checks**:
   ```python
   # In _load_training_data() or training script
   import numpy as np
   
   # Initialize features with NaNs
   df['opening_prob_home_fair'] = np.nan
   df['opening_overround'] = np.nan
   
   # Safety check: Only compute de-vigging if both odds present and valid (> 1.0)
   # Decimal odds should be >= 1.01 realistically (no negative or zero odds)
   valid_ml = (
       df['opening_moneyline_home'].notna()
       & df['opening_moneyline_away'].notna()
       & (df['opening_moneyline_home'] > 1.0)
       & (df['opening_moneyline_away'] > 1.0)
   )
   
   # Step 1: Raw implied probabilities (only for valid odds)
   p_home_raw = 1.0 / df.loc[valid_ml, 'opening_moneyline_home']
   p_away_raw = 1.0 / df.loc[valid_ml, 'opening_moneyline_away']
   den = p_home_raw + p_away_raw
   
   # Step 2: Calculate overround (vig) and de-vig to fair probabilities
   df.loc[valid_ml, 'opening_overround'] = den - 1.0
   df.loc[valid_ml, 'opening_prob_home_fair'] = p_home_raw / den
   
   # Missingness indicators (for CatBoost - keep NaNs, don't impute)
   # has_opening_moneyline should match valid_ml (both sides present and >1.0)
   df['has_opening_moneyline'] = valid_ml.astype(int)
   df['has_opening_spread'] = df['opening_spread'].notna().astype(int)
   df['has_opening_total'] = df['opening_total'].notna().astype(int)
   
   # For CatBoost: Keep NaNs (handles missing natively)
   # For Logistic Regression: Would impute with training-set means (not constants)
   ```

3. **Pass opening odds to `build_design_matrix()`**:
   ```python
   # For CatBoost: Pass NaNs directly (no imputation)
   X_train = build_design_matrix(
       point_differential=df.loc[train_mask, 'point_differential'].to_numpy(),
       time_remaining_regulation=df.loc[train_mask, 'time_remaining_regulation'].to_numpy(),
       # ... existing parameters ...
       opening_prob_home_fair=df.loc[train_mask, 'opening_prob_home_fair'].to_numpy(),  # May contain NaNs
       opening_overround=df.loc[train_mask, 'opening_overround'].to_numpy(),  # May contain NaNs
       opening_spread=df.loc[train_mask, 'opening_spread'].to_numpy(),  # May contain NaNs
       opening_total=df.loc[train_mask, 'opening_total'].to_numpy(),  # May contain NaNs
       has_opening_moneyline=df.loc[train_mask, 'has_opening_moneyline'].to_numpy(),
       has_opening_spread=df.loc[train_mask, 'has_opening_spread'].to_numpy(),
       has_opening_total=df.loc[train_mask, 'has_opening_total'].to_numpy(),
   )
   ```

**Design Pattern**: Feature Engineering Pattern  
**Algorithm**: Direct feature addition (O(n) where n = number of samples)  
**Big O Complexity**: O(n) - Linear in dataset size

#### Recommendation 2: Use Canonical Dataset for Training

**Specific Action**: Modify training scripts to query `derived.snapshot_features_v1` instead of ESPN tables directly

**Rationale**: 
- Opening odds are already in canonical dataset
- Consistent with simulation/grid search pipeline
- Simpler than joining ESPN tables with `external.sportsbook_odds_snapshots`

**Files to Modify**:
- `scripts/model/train_winprob_catboost.py`: Modify `_load_training_data()` to query canonical dataset
- `scripts/model/train_winprob_logreg.py`: Same (if keeping Logistic Regression)

**Estimated Effort**: 2-3 hours
- Query modification: 1 hour
- Testing: 1-2 hours

**Risk Level**: Low
- Canonical dataset has all ESPN data (just pre-joined)
- Performance should be similar (materialized view with indexes)

**Success Metrics**:
- Training scripts successfully load data from canonical dataset
- Training time similar to current approach
- Model performance unchanged (baseline comparison)

### Short-term Improvements (Priority: Medium)

#### Recommendation 3: Add Decay-Weighted Interaction Terms (For Logistic Regression Only)

**Specific Action**: Create decay-weighted interaction terms for Logistic Regression (e.g., `opening_prob_home_fair * w` where `w = time_remaining / 2880`)

**Rationale**: Data scientist recommends explicit interactions for Logistic Regression. **Critical**: Use decay weights that decrease as time → 0, not division by time_remaining (which increases impact late game).

**Files to Modify**:
- `scripts/lib/_winprob_lib.py`: Add interaction term computation in `build_design_matrix()`
- `scripts/model/train_winprob_logreg.py`: Include interaction terms (if keeping Logistic Regression)

**Estimated Effort**: 2-3 hours
- Interaction term design: 1 hour
- Code changes: 1 hour
- Testing: 1 hour

**Risk Level**: Low
- Optional enhancement (CatBoost can discover interactions automatically)
- Can be deferred if focusing on CatBoost only

**Success Metrics**:
- Interaction terms computed correctly
- Logistic Regression benefits from interaction terms (if implemented)

#### Recommendation 4: Evaluate Model Performance with Opening Odds (Time-Bucketed)

**Specific Action**: Train models with and without opening odds, compare performance on test set with **time-bucketed evaluation**

**Metrics to Compare**:
- **Global Metrics**:
  - **Brier Score**: Lower is better (measures probability calibration)
  - **Log-Loss**: Lower is better (measures prediction accuracy)
- **Time-Bucketed Metrics** (REQUIRED):
  - Brier score by time bucket: [2880-2400s, 2400-1800s, 1800-1200s, 1200-600s, 600-120s, 120-0s]
  - Log-loss by time bucket (same buckets)
  - Expected improvement in early-game buckets (where opening odds are most informative)
- **Feature Importance** (CatBoost): Which features contribute most?
- **Grid Search Results**: Do models with opening odds perform better in trading simulations?

**Estimated Effort**: 3-4 hours
- Model training (with/without odds): 1-2 hours
- Performance analysis: 1 hour
- Time-bucketed evaluation: 1 hour

**Risk Level**: None (evaluation only)

**Success Metrics**:
- Models with opening odds show improved Brier score / log-loss globally
- **Early-game buckets (2880-2400s, 2400-1800s) show larger improvements** (opening odds most informative)
- Opening odds features have meaningful feature importance
- Grid search results show improved expected value

**Rationale**: Global metrics can hide benefits (opening odds help most early game). Time-bucketed evaluation reveals where odds add value.

#### Time-Bucketed Evaluation Procedure

**Purpose**: Reproducible procedure to compute Brier score and log-loss overall and per time bucket for baseline vs odds-enabled models.

**Prerequisites**:
- Trained baseline model (without opening odds)
- Trained odds-enabled model (with opening odds)
- Test set predictions from both models
- Test set labels (actual outcomes: 1 = home win, 0 = away win)

**Step 1: Load Test Set Predictions and Labels**

```python
import numpy as np
import pandas as pd

# Load test set data with time_remaining
# Columns needed: game_id, sequence_number, time_remaining, y_true (actual outcome)
test_df = load_test_data()  # Your data loading function

# Load predictions from both models
baseline_probs = load_baseline_predictions()  # Shape: (n_samples,)
odds_probs = load_odds_predictions()  # Shape: (n_samples,)

# Ensure alignment
assert len(test_df) == len(baseline_probs) == len(odds_probs)
```

**Step 2: Assign Time Buckets**

```python
def assign_time_bucket(time_remaining: int) -> str:
    """Assign time bucket label based on time_remaining (seconds)."""
    if time_remaining > 2400:
        return '2880-2400'
    elif time_remaining > 1800:
        return '2400-1800'
    elif time_remaining > 1200:
        return '1800-1200'
    elif time_remaining > 600:
        return '1200-600'
    elif time_remaining > 120:
        return '600-120'
    else:
        return '120-0'

test_df['time_bucket'] = test_df['time_remaining'].apply(assign_time_bucket)
```

**Step 3: Compute Overall Metrics**

```python
from sklearn.metrics import brier_score_loss, log_loss

# Overall Brier score (lower is better)
baseline_brier_overall = brier_score_loss(test_df['y_true'], baseline_probs)
odds_brier_overall = brier_score_loss(test_df['y_true'], odds_probs)

# Overall log-loss (lower is better)
baseline_logloss_overall = log_loss(test_df['y_true'], baseline_probs)
odds_logloss_overall = log_loss(test_df['y_true'], odds_probs)

# Improvement percentages
brier_improvement_pct = 100.0 * (baseline_brier_overall - odds_brier_overall) / baseline_brier_overall
logloss_improvement_pct = 100.0 * (baseline_logloss_overall - odds_logloss_overall) / baseline_logloss_overall
```

**Step 4: Compute Per-Bucket Metrics**

```python
results = []

for bucket in ['2880-2400', '2400-1800', '1800-1200', '1200-600', '600-120', '120-0']:
    bucket_mask = test_df['time_bucket'] == bucket
    bucket_y_true = test_df.loc[bucket_mask, 'y_true']
    bucket_baseline_probs = baseline_probs[bucket_mask]
    bucket_odds_probs = odds_probs[bucket_mask]
    
    if len(bucket_y_true) == 0:
        continue
    
    # Brier scores
    baseline_brier = brier_score_loss(bucket_y_true, bucket_baseline_probs)
    odds_brier = brier_score_loss(bucket_y_true, bucket_odds_probs)
    brier_improvement = 100.0 * (baseline_brier - odds_brier) / baseline_brier if baseline_brier > 0 else 0.0
    
    # Log-loss
    baseline_logloss = log_loss(bucket_y_true, bucket_baseline_probs)
    odds_logloss = log_loss(bucket_y_true, bucket_odds_probs)
    logloss_improvement = 100.0 * (baseline_logloss - odds_logloss) / baseline_logloss if baseline_logloss > 0 else 0.0
    
    results.append({
        'time_bucket': bucket,
        'n_samples': len(bucket_y_true),
        'baseline_brier': baseline_brier,
        'odds_brier': odds_brier,
        'brier_improvement_pct': brier_improvement,
        'baseline_logloss': baseline_logloss,
        'odds_logloss': odds_logloss,
        'logloss_improvement_pct': logloss_improvement,
    })

results_df = pd.DataFrame(results)
```

**Step 5: Format Results Table**

**Template Output Table**:

| time_bucket | n_samples | baseline_brier | odds_brier | brier_improvement_pct | baseline_logloss | odds_logloss | logloss_improvement_pct |
|-------------|-----------|----------------|------------|----------------------|------------------|--------------|-------------------------|
| 2880-2400   | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| 2400-1800   | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| 1800-1200   | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| 1200-600    | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| 600-120     | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| 120-0       | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |
| **Overall** | [N]       | [X.XXXX]       | [X.XXXX]   | [±X.XX%]             | [X.XXXX]         | [X.XXXX]     | [±X.XX%]                |

**Expected Pattern**: Early-game buckets (2880-2400, 2400-1800) should show larger improvements than late-game buckets (600-120, 120-0), as opening odds are most informative early in the game.

**Interpretation**:
- **Positive improvement %**: Odds-enabled model performs better (lower Brier/log-loss)
- **Negative improvement %**: Odds-enabled model performs worse (investigate why)
- **Early-game improvements > Late-game improvements**: Expected pattern (odds matter more early)

### Long-term Strategic Changes (Priority: Low)

#### Recommendation 5: Add Opening Odds to Logistic Regression (Deferred)

**Specific Action**: Add opening odds to Logistic Regression training script (after CatBoost implementation)

**Rationale**: Data scientist recommends focusing on CatBoost first, adding Logistic Regression later if needed

**Estimated Effort**: 3-4 hours
- Similar to CatBoost implementation
- Requires explicit interaction term engineering

**Risk Level**: Low
- Can be deferred until CatBoost results are evaluated

---

## Cost-Benefit Analysis

### Implementation Cost

**Development Time**: 6-9 hours
- Feature engineering design: 1-2 hours
- Code changes (CatBoost): 3-4 hours
- Testing and validation: 2-3 hours

**Learning Curve**: Minimal (straightforward feature addition)

**Configuration Effort**: None (uses existing infrastructure)

### Maintenance Cost

**Monitoring**: None (standard model training pipeline)

**Updates**: None (opening odds are pre-computed in canonical dataset)

**Debugging**: Low (straightforward feature addition, CatBoost handles missing values)

### Performance Benefit

**Model Accuracy**: Expected improvement in Brier score / log-loss (to be measured)
- Opening odds represent pre-game market consensus (valuable signal)
- Time-weighted interactions capture information decay
- CatBoost can discover optimal feature relationships

**Grid Search Performance**: Expected improvement in expected value / win rate (to be measured)
- Better model predictions → better trading decisions → better grid search results

### Maintainability Benefit

**Code Quality**: Minimal change (adds features to existing pipeline)

**Developer Productivity**: Standard feature engineering approach (well-understood pattern)

**System Reliability**: No change (backward compatible, handles NULL values)

### Risk Cost

**Risk 1**: Opening odds not available for all games (NULL values)
- **Mitigation**: CatBoost handles missing values natively - keep NaNs (don't impute), add missingness indicator flags (`has_opening_moneyline`, `has_opening_spread`, `has_opening_total`)

**Risk 2**: Model performance doesn't improve
- **Mitigation**: Evaluate with/without opening odds, can revert if no improvement

**Risk 3**: Feature engineering complexity
- **Mitigation**: Start simple (direct features), let CatBoost discover interactions automatically

### Over-Engineering Prevention

**Problem Complexity**: Low-Medium (feature addition to existing models)
**Solution Complexity**: Low (straightforward feature engineering)
**Appropriateness**: Solution complexity matches problem complexity
**Future Growth**: Standard feature engineering approach, scalable to additional features

---

## Implementation Plan

### Phase 1: Feature Engineering Design (Duration: 1-2 hours)
**Objective**: Design opening odds feature engineering approach (implied probabilities, NULL handling)
**Dependencies**: Understanding of opening odds data structure
**Deliverables**: Feature engineering specification document

#### Tasks
- **Task 1**: Design feature transformations (decimal odds → implied probabilities)
  - **Files**: Design document
  - **Effort**: 30 minutes
  - **Prerequisites**: None

- **Task 2**: Design NULL handling strategy (games without opening odds)
  - **Files**: Design document
  - **Effort**: 30 minutes
  - **Prerequisites**: None

- **Task 3**: Design interaction terms (if needed for Logistic Regression)
  - **Files**: Design document
  - **Effort**: 30 minutes
  - **Prerequisites**: None

### Phase 2: Code Implementation (Duration: 3-4 hours)
**Objective**: Implement opening odds features in CatBoost training pipeline
**Dependencies**: Phase 1 complete
**Deliverables**: Modified training scripts with opening odds support

#### Tasks
- **Task 1**: Modify `build_design_matrix()` to accept opening odds parameters
  - **Files**: `scripts/lib/_winprob_lib.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Feature engineering design complete

- **Task 2**: Modify `train_winprob_catboost.py` to load opening odds from canonical dataset
  - **Files**: `scripts/model/train_winprob_catboost.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: `build_design_matrix()` updated

- **Task 3**: Update `precompute_model_probabilities.py` to include opening odds
  - **Files**: `scripts/model/precompute_model_probabilities.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Training script updated

### Phase 3: Testing and Validation (Duration: 2-3 hours)
**Objective**: Test model training with opening odds, compare performance
**Dependencies**: Phase 2 complete
**Deliverables**: Trained models, performance comparison results

#### Tasks
- **Task 1**: Train CatBoost model with opening odds features
  - **Files**: Training script output (model artifacts)
  - **Effort**: 1 hour (model training time)
  - **Prerequisites**: Code implementation complete

- **Task 2**: Evaluate model performance (Brier score, log-loss, feature importance)
  - **Files**: Evaluation scripts/results
  - **Effort**: 1 hour
  - **Prerequisites**: Models trained

- **Task 3**: Compare with baseline (models without opening odds)
  - **Files**: Comparison results
  - **Effort**: 30 minutes
  - **Prerequisites**: Baseline models trained, new models trained

### Phase 4: Grid Search Integration (Duration: 2-3 hours)
**Objective**: Test grid search with models trained on opening odds
**Dependencies**: Phase 3 complete
**Deliverables**: Grid search results, performance comparison

#### Tasks
- **Task 1**: Pre-compute model probabilities with opening odds features
  - **Files**: `derived.model_probabilities_v1` table
  - **Effort**: 1 hour (pre-computation time)
  - **Prerequisites**: Models trained with opening odds

- **Task 2**: Run grid search with new models
  - **Files**: Grid search results
  - **Effort**: 1 hour (grid search execution time)
  - **Prerequisites**: Model probabilities pre-computed

- **Task 3**: Compare grid search results (with/without opening odds)
  - **Files**: Comparison results
  - **Effort**: 30 minutes
  - **Prerequisites**: Grid search results available

---

## Risk Assessment

### Technical Risks

- **Risk 1**: Opening odds not available for all games (NULL values)
- **Probability**: High (coverage depends on data source)
- **Impact**: Low (CatBoost handles missing values natively)
- **Mitigation**: 
  - **For CatBoost**: Keep NaNs (don't impute), add missingness indicator flags (`has_opening_moneyline`, etc.)
  - **For Logistic Regression**: Impute with training-set means (not constants like 0.5/0.0), always include missingness flags
- **Contingency**: Evaluate model performance with/without opening odds, can proceed even with partial coverage

- **Risk 2**: Model performance doesn't improve with opening odds
  - **Probability**: Medium (opening odds may not add signal beyond ESPN probabilities)
  - **Impact**: Low (can revert changes, models still work)
  - **Mitigation**: Compare performance metrics before/after, evaluate feature importance
  - **Contingency**: Document results, can remove opening odds if no improvement

- **Risk 3**: Feature engineering complexity (interaction terms)
  - **Probability**: Low (CatBoost can discover interactions automatically)
  - **Impact**: Low (can start simple, add interactions later)
  - **Mitigation**: Start with direct features, let CatBoost discover interactions
  - **Contingency**: Can add explicit interactions later if needed

### Business Risks

- **Risk 1**: Time investment doesn't yield model improvement
  - **Probability**: Medium (opening odds may not improve predictions)
  - **Impact**: Low (minimal time investment, can revert)
  - **Mitigation**: Evaluate performance before/after, data scientist recommendation suggests it will help
  - **Contingency**: Document learnings, focus on other improvements if opening odds don't help

### Resource Risks

- **Risk 1**: Training time increases with additional features
  - **Probability**: Low (only 4-6 additional features)
  - **Impact**: Low (minimal increase, CatBoost is efficient)
  - **Mitigation**: Monitor training time, optimize if needed
  - **Contingency**: None (expected to be minimal)

---

## Success Metrics and Monitoring

### Performance Metrics

- **Model Accuracy (Brier Score)**: Target: 5-10% improvement vs. baseline globally (to be measured)
- **Model Accuracy (Log-Loss)**: Target: 5-10% improvement vs. baseline globally (to be measured)
- **Time-Bucketed Performance** (REQUIRED):
  - Early-game buckets (2880-2400s, 2400-1800s): Target 10-15% improvement in Brier/log-loss
  - Mid-game buckets (1800-1200s, 1200-600s): Target 5-10% improvement
  - Late-game buckets (600-120s, 120-0s): Target 0-5% improvement (odds less informative)
- **Feature Importance**: Target: Opening odds features in top 50% of feature importance (CatBoost)
- **Grid Search Performance**: Target: 5-10% improvement in expected value or win rate (to be measured)

### Quality Metrics

- **Coverage**: Opening odds available for 80%+ of games in training/test sets
- **NULL Handling**: Models train successfully with NULL opening odds (no errors)
- **Backward Compatibility**: Existing models (without opening odds) still work

### Monitoring Strategy

- **Model Training**: Monitor training time, convergence, feature importance
- **Performance Evaluation**: 
  - Compare global Brier score, log-loss, feature importance before/after
  - **Time-bucketed evaluation**: Compare Brier/log-loss by time bucket (see Q5 in Command Appendix)
- **Grid Search Testing**: Compare expected value, win rate, Sharpe ratio with/without opening odds

---

## Evidence and Proof

### Code References

**Current Model Architecture**:
- **File**: `scripts/lib/_winprob_lib.py:183-210`
  - **Evidence**: `build_design_matrix()` function signature shows current features
  - **Finding**: Opening odds parameters not present in function signature

**Training Data Loading**:
- **File**: `scripts/model/train_winprob_logreg.py:90-112`
  - **Evidence**: `_load_training_data()` queries ESPN tables directly, not canonical dataset
  - **Finding**: Training scripts don't have access to opening odds (query ESPN tables, not canonical dataset)

**Opening Odds Availability**:
- **File**: `db/migrations/039_snapshot_features_v1_add_opening_odds.sql:355-360`
  - **Evidence**: Migration adds `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total` columns
  - **Finding**: Opening odds are available in canonical dataset, but not used in training

### Data Scientist Recommendations

**Source**: Discord conversation with dta (data scientist)

**Recommendations**:
1. "add the odds data as a parameter" - Add opening odds as features
2. "we may need interaction terms bc we're really interested in the relation between the terms" - Create interaction terms
3. "like the odds mean very little with 2 minutes in the game" - Opening odds information decays over time
4. "just use catboost" - Focus on CatBoost, not Logistic Regression
5. "drop the logistic there's no real point in running it until we add interaction terms" - Defer Logistic Regression
6. "something like odds divided by time or score divided by time" - Suggested interaction term formulas

---

## Appendices

### Appendix A: Feature Engineering Formulas

**Decimal Odds to Fair Probability (De-Vigging with Safety Checks)**:

**Canonical Feature Names**:
- `opening_prob_home_fair` (de-vigged fair probability)
- `opening_overround` (vig amount)

**Safety Checks (CRITICAL)**:
- Only compute if both odds present and > 1.0 (decimal odds should be >= 1.01 realistically)
- Else keep NaNs and let missingness flags capture missingness
- Prevents division by zero, negative odds, and invalid calculations

**Implementation**:
```python
import numpy as np

# Initialize features with NaNs
df['opening_prob_home_fair'] = np.nan
df['opening_overround'] = np.nan

# Safety check: Only compute de-vigging if both odds present and valid (> 1.0)
valid_ml = (
    df['opening_moneyline_home'].notna()
    & df['opening_moneyline_away'].notna()
    & (df['opening_moneyline_home'] > 1.0)
    & (df['opening_moneyline_away'] > 1.0)
)

# Step 1: Raw implied probabilities (only for valid odds)
p_home_raw = 1.0 / df.loc[valid_ml, 'opening_moneyline_home']
p_away_raw = 1.0 / df.loc[valid_ml, 'opening_moneyline_away']
den = p_home_raw + p_away_raw

# Step 2: Calculate overround (vig) and de-vig to fair probabilities
df.loc[valid_ml, 'opening_overround'] = den - 1.0
df.loc[valid_ml, 'opening_prob_home_fair'] = p_home_raw / den
```

**Example**:
- `opening_moneyline_home = 1.85`, `opening_moneyline_away = 2.10`
- `p_home_raw = 1 / 1.85 = 0.5405` (54.05%)
- `p_away_raw = 1 / 2.10 = 0.4762` (47.62%)
- `den = 0.5405 + 0.4762 = 1.0167`
- `opening_overround = 1.0167 - 1 = 0.0167` (1.67% vig)
- `opening_prob_home_fair = 0.5405 / 1.0167 = 0.5315` (53.15% - de-vigged)
- Note: `opening_prob_home_fair + (1 - opening_prob_home_fair) = 1.0` (no overround bias)

**Why De-Vig?**: Raw implied probabilities include sportsbook vig (overround), so they don't sum to 1.0. Using raw probabilities distorts calibration. Fair probabilities sum to 1.0 and represent true market expectations.

**Edge Cases Handled**:
- Missing odds (one or both): Features remain NaN
- Invalid odds (≤ 1.0, negative, zero): Features remain NaN
- Missingness flags (`has_opening_moneyline`) capture when odds are available

**Decay-Weighted Interaction Terms** (For Logistic Regression Only):

**Decay Weight Options**:
```
w_linear = time_remaining / 2880  # Linear decay (0 at game end, 1 at start)
w_sqrt = sqrt(time_remaining / 2880)  # Square root decay (smoother)
w_log = log1p(time_remaining) / log1p(2880)  # Logarithmic decay (bounded 0-1)
```

**Weighted Features**:
```
opening_prob_home_fair_weighted = opening_prob_home_fair * w
opening_spread_weighted = opening_spread * w
opening_total_weighted = opening_total * w
```

**Key Point**: Decay weight **decreases** as time approaches 0 (correct behavior for information decay). Original formula (`opening_odds / time_remaining`) was backwards - it increases impact late game.

**NULL Handling** (Games without opening odds):

**For CatBoost**:
- Keep NaNs (CatBoost handles missing natively)
- Add missingness indicator flags:
  - `has_opening_moneyline = valid_ml.astype(int)` (matches valid_ml: both sides present and >1.0)
  - `has_opening_spread = 1 if opening_spread IS NOT NULL else 0`
  - `has_opening_total = 1 if opening_total IS NOT NULL else 0`

**For Logistic Regression**:
- Impute with training-set means (not constants):
  - `opening_prob_home_fair_mean = mean(opening_prob_home_fair[train_mask])` (computed from training set)
  - `opening_overround_mean = mean(opening_overround[train_mask])`
  - `opening_spread_mean = mean(opening_spread[train_mask])`
  - `opening_total_mean = mean(opening_total[train_mask])`
- Always include missingness flags

### Appendix B: Data Scientist Conversation Context

**Full Conversation** (from user query):

```
ADAM — 2:59 PM
so once i have the odds data pulled, i retrain the models and do the grid searches?

dta — 3:00 PM
well you need to add the odds data as a parameter
obviously

ADAM — 3:00 PM
in the model

dta — 3:00 PM
yeah just add a column
we may need interaction terms bc we're really interested in
the relation between the terms
like the odds mean very little with 2 minutes in the game
just use catboost

ADAM — 3:02 PM
ok

dta — 3:05 PM
drop the logistic there's no real point in running it until we add interaction terms
something like odds divided by time
or score divided by time
catboost will still improve once we add interaction terms but it can figure some of it out
```

### Appendix C: Glossary

- **Opening Odds**: Pre-game sportsbook odds (moneyline, spread, total) set before the game starts
- **Raw Implied Probability**: Probability derived from odds (`1 / decimal_odds`) - includes vig/overround
- **Overround (Vig)**: The amount by which raw implied probabilities exceed 1.0 (`(p_home_raw + p_away_raw) - 1`)
- **Fair Probability**: De-vigged probability that sums to 1.0 (`p_home_raw / (p_home_raw + p_away_raw)`)
- **Decay Weight**: Multiplier that decreases as time approaches 0 (e.g., `w = time_remaining / 2880`) - used for information decay
- **Interaction Term**: Feature created by combining two or more features (e.g., `p_home_fair * w` where `w` is decay weight)
- **CatBoost**: Gradient boosting algorithm that can automatically discover feature interactions and handles missing values natively
- **Logistic Regression**: Linear model that requires explicit feature engineering for interactions and imputation for missing values
- **Information Decay**: Concept that opening odds become less informative as the game progresses (current score/time dominate) - captured by decay weights that shrink toward 0

---

## Command Appendix: Verification Queries

**Purpose**: Copy-pastable SQL queries to verify claims and gather evidence for this analysis.

### Q1: Snapshot-Level Odds Coverage

**Purpose**: Verify total snapshots and opening odds coverage in `derived.snapshot_features_v1`.

```sql
-- Q1: Snapshot-level odds coverage
SELECT 
    COUNT(*) AS total_snapshots,
    COUNT(opening_moneyline_home) AS snapshots_with_opening_moneyline,
    COUNT(opening_spread) AS snapshots_with_opening_spread,
    COUNT(opening_total) AS snapshots_with_opening_total,
    ROUND(100.0 * COUNT(opening_moneyline_home) / COUNT(*), 2) AS pct_with_moneyline,
    ROUND(100.0 * COUNT(opening_spread) / COUNT(*), 2) AS pct_with_spread,
    ROUND(100.0 * COUNT(opening_total) / COUNT(*), 2) AS pct_with_total
FROM derived.snapshot_features_v1;
```

**Expected Output to Paste Here**:
```
total_snapshots | snapshots_with_opening_moneyline | snapshots_with_opening_spread | snapshots_with_opening_total | pct_with_moneyline | pct_with_spread | pct_with_total
----------------+----------------------------------+-------------------------------+------------------------------+--------------------+-----------------+----------------
[Paste results here]
```

### Q2: Opening Odds Availability by Season

**Purpose**: Verify opening odds coverage by season (2017-2025).

```sql
-- Q2: Opening odds availability by season
SELECT 
    season_label,
    CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
    COUNT(DISTINCT game_id) AS total_games,
    COUNT(DISTINCT game_id) FILTER (WHERE opening_moneyline_home IS NOT NULL) AS games_with_moneyline,
    COUNT(*) AS total_snapshots,
    COUNT(*) FILTER (WHERE opening_moneyline_home IS NOT NULL) AS snapshots_with_moneyline,
    ROUND(100.0 * COUNT(DISTINCT game_id) FILTER (WHERE opening_moneyline_home IS NOT NULL) / COUNT(DISTINCT game_id), 2) AS pct_games_with_moneyline
FROM derived.snapshot_features_v1
GROUP BY season_label, season_start
ORDER BY season_start;
```

**Expected Output to Paste Here**:
```
season_label | season_start | total_games | games_with_moneyline | total_snapshots | snapshots_with_moneyline | pct_games_with_moneyline
-------------+--------------+-------------+----------------------+------------------+---------------------------+-------------------------
[Paste results here]
```

### Q3: Universe Parity (ESPN-Direct vs snapshot_features_v1)

**Purpose**: Compare game and snapshot counts between ESPN-direct training query and canonical dataset.

**Q3a: ESPN-Direct Game/Snapshot Counts** (what current training uses):

```sql
-- Q3a: ESPN-direct training query game/snapshot counts
WITH espn_base AS (
    SELECT 
        p.game_id,
        p.event_id,
        CAST(SUBSTRING(p.season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start
    FROM espn.probabilities_raw_items p
    INNER JOIN espn.prob_event_state e 
        ON p.game_id = e.game_id 
        AND p.event_id = e.event_id
    WHERE e.time_remaining IS NOT NULL
        AND e.point_differential IS NOT NULL
)
SELECT 
    season_start,
    COUNT(DISTINCT game_id) AS game_count,
    COUNT(DISTINCT (game_id, event_id)) AS unique_snapshot_count,
    COUNT(*) AS snapshot_count
FROM espn_base
GROUP BY season_start
ORDER BY season_start;
```

**Expected Output to Paste Here**:
```
season_start | game_count | unique_snapshot_count | snapshot_count
-------------+------------+----------------------+----------------
[Paste results here]
```

**Note**: `unique_snapshot_count` is a sanity check - it should equal `snapshot_count` if each (game_id, event_id) pair is unique. If they differ, investigate duplicate snapshots.

**Q3b: Canonical Dataset Game/Snapshot Counts** (what we'd switch to):

```sql
-- Q3b: snapshot_features_v1 game/snapshot counts
SELECT 
    CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) AS season_start,
    COUNT(DISTINCT game_id) AS game_count,
    COUNT(DISTINCT (season_label, game_id, sequence_number, snapshot_ts)) AS unique_snapshot_count,
    COUNT(*) AS snapshot_count
FROM derived.snapshot_features_v1
GROUP BY season_start
ORDER BY season_start;
```

**Expected Output to Paste Here**:
```
season_start | game_count | unique_snapshot_count | snapshot_count
-------------+------------+----------------------+----------------
[Paste results here]
```

**Note**: `unique_snapshot_count` uses the canonical dataset's unique key `(season_label, game_id, sequence_number, snapshot_ts)`. It should equal `snapshot_count` if the materialized view has no duplicates.

**Q3c: Parity Check** (compare Q3a vs Q3b):

```sql
-- Q3c: Parity check (run after Q3a and Q3b)
-- Compare game counts and snapshot counts
-- Expected: snapshot_features_v1 counts should be within 5% of ESPN-direct counts
-- If not, parity fails - cannot switch to canonical dataset without modification
```

**Analysis**: Compare outputs from Q3a and Q3b. If `snapshot_features_v1` counts are significantly lower (e.g., >5% difference), parity fails. See "Training Data Source Parity Validation" section for mitigation options.

### Q4: Odds Sanity Checks (Overround Distribution per Game)

**Purpose**: Verify odds data quality - check overround distribution per game and identify outliers.

**Unit**: One row per game (not per odds pair or snapshot).

```sql
-- Q4: Overround distribution per game (vig check)
WITH odds_data AS (
    SELECT DISTINCT
        season_label,
        game_id,
        opening_moneyline_home,
        opening_moneyline_away,
        (1.0 / opening_moneyline_home) AS p_home_raw,
        (1.0 / opening_moneyline_away) AS p_away_raw,
        ((1.0 / opening_moneyline_home) + (1.0 / opening_moneyline_away) - 1.0) AS overround
    FROM derived.snapshot_features_v1
    WHERE opening_moneyline_home IS NOT NULL 
        AND opening_moneyline_away IS NOT NULL
        AND opening_moneyline_home > 1.0 
        AND opening_moneyline_away > 1.0
)
SELECT 
    COUNT(*) AS games_with_valid_odds,
    ROUND(MIN(overround), 4) AS min_overround,
    ROUND(MAX(overround), 4) AS max_overround,
    ROUND(AVG(overround), 4) AS avg_overround,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY overround), 4) AS median_overround,
    ROUND(STDDEV(overround), 4) AS stddev_overround,
    COUNT(*) FILTER (WHERE overround < 0) AS negative_overround_count,
    COUNT(*) FILTER (WHERE overround > 0.10) AS high_overround_count
FROM odds_data;
```

**Expected Output to Paste Here**:
```
games_with_valid_odds | min_overround | max_overround | avg_overround | median_overround | stddev_overround | negative_overround_count | high_overround_count
----------------------+---------------+---------------+---------------+---------------+------------------+-------------------------+-----------------------
[Paste results here]
```

**Expected Ranges**:
- `avg_overround`: Typically 0.02-0.05 (2-5% vig)
- `negative_overround_count`: Should be 0 (negative overround indicates data error)
- `high_overround_count`: Should be small (overround > 10% is unusual)

### Q5: Time Bucket Counts (For Time-Bucketed Evaluation)

**Purpose**: Get snapshot counts by time bucket for time-bucketed evaluation metrics.

```sql
-- Q5: Time bucket counts
SELECT 
    CASE 
        WHEN time_remaining > 2400 THEN '2880-2400'
        WHEN time_remaining > 1800 THEN '2400-1800'
        WHEN time_remaining > 1200 THEN '1800-1200'
        WHEN time_remaining > 600 THEN '1200-600'
        WHEN time_remaining > 120 THEN '600-120'
        ELSE '120-0'
    END AS time_bucket,
    COUNT(*) AS snapshot_count,
    COUNT(*) FILTER (WHERE opening_moneyline_home IS NOT NULL) AS snapshots_with_odds,
    ROUND(100.0 * COUNT(*) FILTER (WHERE opening_moneyline_home IS NOT NULL) / COUNT(*), 2) AS pct_with_odds
FROM derived.snapshot_features_v1
WHERE CAST(SUBSTRING(season_label FROM '^([0-9]{4})') AS INTEGER) = 2024  -- Test season
GROUP BY time_bucket
ORDER BY time_bucket DESC;
```

**Expected Output to Paste Here**:
```
time_bucket | snapshot_count | snapshots_with_odds | pct_with_odds
------------+----------------+---------------------+---------------
[Paste results here]
```

**Usage**: Use these buckets for time-bucketed Brier score and log-loss evaluation (see "Success Metrics" section).

### Q6: Schema Verification

**Purpose**: Verify opening odds columns exist in `derived.snapshot_features_v1`.

```sql
-- Q6: Schema verification
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'derived' 
    AND table_name = 'snapshot_features_v1'
    AND column_name LIKE 'opening%'
ORDER BY ordinal_position;
```

**Expected Output to Paste Here**:
```
column_name | data_type | is_nullable
------------+-----------+-------------
[Paste results here]
```

**Expected Columns**:
- `opening_moneyline_home` (NUMERIC, nullable)
- `opening_moneyline_away` (NUMERIC, nullable)
- `opening_spread` (NUMERIC, nullable)
- `opening_total` (NUMERIC, nullable)

---

## Document Validation

**IMPORTANT**: This analysis follows the comprehensive validation checklist in `ANALYSIS_STANDARDS.md`.

**Validation Checklist**:
- ✅ Evidence-based analysis (code refs, data scientist recommendations)
- ✅ File verification (inspected relevant code files)
- ✅ Database verification (referenced migration 039, canonical dataset structure)
- ✅ Technical assessment (design patterns, algorithms, Big O analysis)
- ✅ Recommendations with pros/cons (following user memory preferences)
- ✅ Implementation plan with effort estimates
- ✅ Risk assessment with mitigation strategies
- ✅ Success metrics defined

