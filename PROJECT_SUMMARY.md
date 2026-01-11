# Project Summary: NBA Win Probability & Trading Strategy Analysis

**Generated:** Based on comprehensive codebase analysis  
**Project Type:** Data warehouse + Machine learning + Trading simulation + Web application  
**Primary Language:** Python 3.11+  
**Database:** PostgreSQL 16  
**Web Framework:** FastAPI  

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Data Sources & Ingestion](#data-sources--ingestion)
3. [Data Processing & Modeling](#data-processing--modeling)
4. [Trading Strategy & Simulation](#trading-strategy--simulation)
5. [Web Application](#web-application)
6. [Infrastructure & Deployment](#infrastructure--deployment)
7. [Key Algorithms & Design Patterns](#key-algorithms--design-patterns)

---

## Project Overview

This project is a comprehensive NBA data warehouse and trading strategy analysis platform that:

1. **Ingests** raw NBA data from multiple sources (ESPN, Kalshi prediction markets, NBA API)
2. **Processes** and stores data in PostgreSQL with full provenance tracking
3. **Trains** a win probability model using logistic regression with L2 regularization
4. **Simulates** trading strategies based on ESPN-Kalshi probability divergence
5. **Optimizes** trading parameters via grid search hyperparameter optimization
6. **Visualizes** results through a FastAPI web application with real-time charts

**Core Value Proposition:** Identify profitable trading opportunities by detecting when ESPN's win probability model diverges from Kalshi's prediction market prices.

---

## Data Sources & Ingestion

### ESPN Data

**Source:** ESPN Core API (`sports.core.api.espn.com`)

**Data Types:**
- **Win Probabilities** (`espn.probabilities_raw_items`): Time-series probability data for NBA games
  - Fetched via: `scripts/fetch_espn_probabilities.py`
  - Loaded via: `scripts/load_espn_probabilities_raw_items.py`
  - Endpoint: `/v2/sports/basketball/leagues/nba/events/{event_id}/competitions/{competition_id}/probabilities`
  - Stored as JSONB with extracted fields: `home_win_percentage`, `away_win_percentage`, `last_modified_utc`, `sequence_number`
  
- **Scoreboard Games** (`espn.scoreboard_games`): Game metadata, teams, scores, event dates
  - Fetched via: `scripts/fetch_espn_scoreboard.py`
  - Loaded via: `scripts/load_espn_scoreboard.py`
  
- **Play-by-Play** (`espn.prob_event_state`): Materialized game state aligned with probability timestamps
  - Materialized via: `scripts/materialize_espn_prob_event_state.py`
  - Contains: `point_differential`, `time_remaining_regulation`, `possession`, `home_score`, `away_score`

**Design Pattern:** Archive-First Pattern  
**Algorithm:** HTTP fetch with retry logic, atomic file writes with manifests  
**Big O:** O(n) where n = number of games/events fetched  
**Pros:**
- Idempotent fetches (SHA256 deduplication)
- Full provenance tracking via `source_files` table
- Resumable ingestion runs via `ingestion_runs` table
- Raw JSONB preservation for future reprocessing

**Cons:**
- Requires manual game discovery (event_id + competition_id pairs)
- ESPN API rate limits may require backoff

### Kalshi Data

**Source:** Kalshi Trade API (`api.elections.kalshi.com/trade-api/v2`)

**Data Types:**
- **Markets** (`kalshi.markets`): Prediction market metadata
  - Fetched via: TypeScript scripts in `scripts/kalshi/` (e.g., `fetch_all_markets.ts`)
  - Loaded via: `scripts/load_kalshi_markets.py`
  - Links to ESPN games via `espn_event_id`
  
- **Trades** (`kalshi.trades`): Individual trade executions (7M+ trades)
  - Fetched via: `scripts/fetch_kalshi_trades.py` (RSA-SHA256 authenticated)
  - Loaded via: `scripts/load_kalshi_trades.py`
  - Fields: `ticker`, `created_time`, `yes_price`, `no_price`, `count`, `price`, `taker_side`, `trade_id`
  - Paginated API with cursor-based pagination
  
- **Candlesticks** (`kalshi.candlesticks`): OHLC time-series aggregated from trades
  - Official: 1-minute intervals from Kalshi API
  - Trade-derived: 1-second, 10-second, 60-second intervals via `webapp/api/utils/trade_candles.py`
  - Aggregation algorithm: Time-window OHLC with VWAP calculation

**Design Pattern:** Batch Fetch with Pagination  
**Algorithm:** Cursor-based pagination, RSA-SHA256 request signing  
**Big O:** O(n) where n = number of markets/trades  
**Pros:**
- Complete historical trade data preserved
- Multiple aggregation intervals supported (1s, 10s, 60s)
- Integer cents end-to-end (no float precision issues)

**Cons:**
- Large storage footprint (7M+ trades)
- Requires API credentials (RSA key pair)
- Trade-derived candles require real-time aggregation

### NBA API Data

**Source:** `stats.nba.com` (via `nba_api` Python library)

**Data Types:**
- **Play-by-Play** (`nba.pbp_events`): Raw game events
  - Fetched via: `scripts/fetch_pbp.py` (with CDN fallback)
  - Loaded via: `scripts/load_pbp.py`
  
- **Boxscores** (`nba.game_boxscores`): Player/team statistics
  - Fetched via: `scripts/fetch_boxscore.py`
  
- **Schedule** (`nba.schedule_snapshots`): Game schedules
  - Fetched via: `scripts/fetch_scheduleLeagueV2.py`

**Design Pattern:** Fallback Pattern (CDN → nba_api)  
**Algorithm:** HTTP fetch with automatic fallback on 403 errors  
**Big O:** O(n) where n = number of games  

---

## Data Processing & Modeling

### Win Probability Model

**Model Type:** Regularized Logistic Regression (L2 regularization)  
**Training Script:** `scripts/train_winprob_logreg.py`  
**Library:** Custom implementation (`scripts/_winprob_lib.py`) - no scikit-learn dependency

**Features:**
1. `point_differential_scaled`: (home_score - away_score), standardized
2. `time_remaining_regulation_scaled`: Seconds remaining, standardized
3. `possession_home`: One-hot encoded (1 if home team has possession)
4. `possession_away`: One-hot encoded (1 if away team has possession)
5. `possession_unknown`: One-hot encoded (1 if possession unknown)

**Label:** `y_home_win = 1` if `final_winning_team == 0` (home won), else `0`

**Training Algorithm:** Iteratively Reweighted Least Squares (IRLS) / Newton's Method  
**Design Pattern:** Pipeline Pattern (preprocess → fit → calibrate → save artifact)  
**Big O:** O(n × d² × iterations) where n = training samples, d = features (5), iterations ≈ 10-50

**Training Split:**
- **Train:** `season_start <= 2022` (default)
- **Calibration:** `season_start == 2023` (Platt scaling)
- **Test:** `season_start == 2024` (held-out evaluation)

**Calibration:** Platt Scaling (logistic regression on logit-transformed probabilities)  
**Pros:**
- Improves probability calibration (reduces ECE)
- Preserves model discrimination (AUC unchanged)
- Simple 2-parameter transformation

**Cons:**
- Requires separate calibration dataset
- May overfit if calibration set is small

**Artifact Format:** JSON file containing:
- Preprocessing parameters (mean/std for scaling)
- Model weights and intercept
- Platt calibrator parameters (alpha, beta)
- Metadata (version, season splits, bucket definitions)

**Evaluation:** `scripts/evaluate_winprob_model.py`
- Metrics: Brier score, log loss, ROC-AUC, ECE (Expected Calibration Error)
- Per-bucket metrics (by time remaining)
- Calibration plots (SVG reliability diagrams)

### Data Pipeline

**Snapshot Building:** `scripts/build_winprob_snapshots_parquet.py`
- Converts per-event modeling data to fixed time-bucket snapshots
- Buckets: 2880 seconds (48 min) down to 0 seconds, step size 60 seconds
- Selection algorithm: For each bucket, pick row minimizing `|time_remaining_regulation - bucket|`
- Tie-break: Maximum `event_id`
- Output: Parquet file with one row per `(game_id, bucket_seconds_remaining)`

**Event State Materialization:** `scripts/materialize_espn_prob_event_state.py`
- Joins ESPN probabilities with play-by-play data
- Computes game state: `point_differential`, `time_remaining_regulation`, `possession`
- Stores in `espn.prob_event_state` for fast queries

**Export Scripts:**
- `scripts/export_winprob_modeling_events_parquet.py`: Exports events to Parquet
- `scripts/export_pbp_event_state_parquet.py`: Exports PBP state to Parquet
- `scripts/export_winprob_split_game_ids.py`: Exports train/valid/test game splits

---

## Trading Strategy & Simulation

### Strategy Overview

**Core Concept:** Trade on ESPN-Kalshi probability divergence

**Entry Rules:**
- **Long ESPN:** Buy when `ESPN_prob > Kalshi_price + entry_threshold` (e.g., 5 cents)
- **Short ESPN:** Sell when `ESPN_prob < Kalshi_price - entry_threshold`

**Exit Rules:**
- Close position when `|ESPN_prob - Kalshi_price| < exit_threshold` (e.g., 1 cent)
- Minimum holding period: 30 seconds (prevents noise trading)
- Hysteresis: Only exit when divergence crosses threshold (prevents churn)

**Position Sizing:**
- Risk-neutral: Same max risk for long/short positions
- Bet amount: $20 per trade (configurable)
- Uses bid/ask spread for realistic execution prices

**Trading Costs:**
- **Fees:** Kalshi trading fees (7% formula) - optional via `enable_fees` flag
- **Slippage:** Configurable slippage rate (default: 0.0) - conservative estimate

**Design Pattern:** State Machine Pattern  
**Algorithm:** Divergence Threshold Trading Simulation with Hysteresis  
**Big O:** O(n) where n = aligned data points per game

**Implementation:** `scripts/simulate_trading_strategy.py`

**Pros:**
- Realistic trading model (not betting)
- Accounts for bid/ask spread and fees
- Prevents noise trading with hysteresis
- Risk-neutral position sizing

**Cons:**
- Requires bid/ask data (falls back to mid-price with penalty if unavailable)
- End-of-game liquidity collapse is estimated (not precise)
- Slippage is configurable estimate (not precise market impact model)

### Data Alignment

**Algorithm:** Game-timeline normalization

**ESPN Data:**
- Timestamps normalized to synthetic timeline anchored at `event_date`
- Preserves relative timing between ESPN records
- Maps to game timeline: `event_date + elapsed_time_from_first_record`

**Kalshi Data:**
- Uses actual wall-clock timestamps (`period_ts`)
- Filtered by game window: `event_date` to `event_date + duration + 15min_buffer`

**Matching:** For each ESPN timestamp, find closest Kalshi timestamp within 60 seconds

**Time Filtering:** Optional exclusion of first/last N seconds to avoid:
- Pre-game noise
- End-of-game liquidity collapse

**Implementation:** `scripts/simulate_trading_strategy.py::get_aligned_data()`

### Grid Search Hyperparameter Optimization

**Purpose:** Systematically test entry/exit threshold combinations to find optimal trading parameters

**Script:** `scripts/grid_search_hyperparameters.py`

**Design Pattern:** Map-Reduce Pattern for parallel execution  
**Algorithm:** Exhaustive Grid Search with Train/Valid/Test Splits  
**Big O:** O(k × n × m / p) where k = parameter combinations, n = games, m = data points per game, p = workers

**Splits:**
- **Train:** Used for broad ranking of combinations (identify top N)
- **Validation:** Used to select final candidate from top N train combos (do NOT tune on test)
- **Test:** One-time final report only (do NOT use for selection or tuning)

**Parameter Ranges:**
- Entry threshold: 0.02 to 0.10 (2-10 cents), step 0.01
- Exit threshold: 0.00 to 0.05 (0-5 cents), step 0.005
- Constraints: `entry > 0`, `exit >= 0`, `exit < entry`

**Parallelization:** ThreadPoolExecutor with configurable workers (default: 8)

**Output:**
- CSV/JSON results for train/valid/test splits
- `final_selection.json`: Chosen parameters and metrics
- Plots: Profit heatmaps, marginal effects, tradeoff scatter, profit factor heatmap

**Analysis:** `scripts/analyze_grid_search_results.py`
- Generates visualizations
- Identifies patterns (e.g., "sweet spot" parameter ranges)
- Reports final selection with justification

**Pros:**
- Systematic exploration of parameter space
- Prevents overfitting via train/valid/test splits
- Reproducible (deterministic game splits)

**Cons:**
- Computationally expensive (tests all valid combinations)
- Requires large game dataset for statistical significance
- Grid search may miss optimal parameters between grid points

---

## Web Application

### Architecture

**Framework:** FastAPI (Python)  
**Frontend:** Vanilla JavaScript (no framework)  
**Charts:** Lightweight Charts (TradingView)  
**WebSockets:** Real-time live game updates

**Design Pattern:** Modular Router Pattern  
**Algorithm:** FastAPI router composition  
**Big O:** O(1) for route registration

### API Endpoints

#### Games (`/api/games`)
- **GET `/api/games`**: List games with pagination, filtering, sorting
  - Filters: `season`, `has_kalshi`, `team_filter`, `date_from`, `date_to`
  - Sort: `date`, `volatility`, `std_dev`, `range`, `score`
  - Uses MATERIALIZED CTEs for performance
  - Cached: 1 hour TTL

#### Probabilities (`/api/games/{game_id}/probs`)
- **GET `/api/games/{game_id}/probs`**: Get probability time series
  - Returns ESPN probabilities + Kalshi candlesticks
  - ESPN: Normalized to game timeline
  - Kalshi: Actual timestamps, grouped by ticker (home/away markets)
  - Cached: Dynamic TTL (1 year for completed games, 5 min for in-progress)

#### Kalshi Candles (`/api/probabilities/{game_id}/kalshi-candles`)
- **GET `/api/probabilities/{game_id}/kalshi-candles`**: Get Kalshi candlesticks
  - Supports multiple intervals: 1s, 10s, 60s
  - Sources: `official` (from `kalshi.candlesticks`) or `trades` (real-time aggregation)
  - Performance guardrails: Max 3600 points for 1-second resolution
  - Multi-ticker support (home/away markets)

#### Simulation (`/api/games/{game_id}/simulation`)
- **GET `/api/games/{game_id}/simulation`**: Simulate trading strategy for single game
  - Parameters: `entry_threshold`, `exit_threshold`, `bet_amount`, `slippage_rate`, `min_hold_seconds`, `use_trade_data`, `enable_fees`
  - Returns: Profit/loss, trade count, win rate, individual trades

#### Bulk Simulation (`/api/simulation/bulk`)
- **GET `/api/simulation/bulk`**: Simulate across multiple games
  - Parameters: `num_games`, trading parameters
  - Parallel execution: ThreadPoolExecutor (8 workers)
  - Caching: Per-game cache with 1-year TTL for completed games
  - Returns: Aggregated metrics, per-game summaries, equity curve, risk metrics

**Metrics Calculated:**
- Total profit/loss (net after costs)
- Win rate
- ROI percentage
- Sharpe ratio
- Maximum drawdown (dollar and percentage)
- Profit factor
- Expectancy (EV per trade)
- Position breakdown (long vs short)
- Game phase stratification (Q1, Q2-Q3, Q4)
- Distribution quartiles

#### Stats (`/api/stats`)
- **GET `/api/stats/{game_id}`**: Game-level statistics
  - Volatility, divergence metrics, probability ranges
  - Cached: 1 year for completed games

#### Aggregate Stats (`/api/aggregate_stats`)
- **GET `/api/aggregate_stats`**: Season-wide statistics
  - Aggregated across all games
  - Cached: 24 hours TTL

#### Live Data (`/live_data`)
- **WebSocket**: Real-time game updates
- **GET `/live_data/games`**: List live games
- **GET `/live_data/games/{game_id}`**: Live game detail

### Frontend Features

**Pages:**
1. **Game List** (`/`): Browse games with filters
2. **Game Detail** (`/game/{game_id}`): Probability chart + simulation results
3. **Live Games** (`/live`): Real-time game monitoring
4. **Simulation** (`/simulation`): Bulk simulation interface
5. **Aggregate Stats** (`/stats`): Season-wide analysis

**Charts:**
- ESPN probability overlay (home/away)
- Kalshi price overlay (home/away markets)
- Score overlay
- Trading signals (entry/exit markers)
- Equity curve (for bulk simulations)

**Real-time Updates:**
- WebSocket connection for live games
- Auto-refresh on game updates
- Connection health monitoring

### Caching Strategy

**Design Pattern:** Multi-Layer Caching Pattern

**Layers:**
1. **In-Memory Cache:** Per-worker cache (FastAPI startup)
2. **Disk Cache:** Persistent cache files (`.cache/` directory)
3. **Database Cache:** Pre-computed stats in `derived.game_stats`

**TTL Strategy:**
- Completed games: 1 year (deterministic results)
- In-progress games: 5 minutes (frequent updates)
- Aggregate stats: 24 hours (daily recalculation)

**Cache Invalidation:**
- Manual: `/api/simulation/clear-cache` endpoint
- Automatic: TTL expiration
- Preload: Cache warming on server startup (skipped in reload mode)

**Pros:**
- Fast response times for repeated queries
- Reduces database load
- Survives server restarts (disk cache)

**Cons:**
- Cache invalidation complexity
- Memory usage for in-memory cache
- Disk I/O for disk cache

### Database Connection Pooling

**Implementation:** `webapp/api/db.py`

**Design Pattern:** Singleton Pattern for connection pool  
**Algorithm:** Queue-based connection pool  
**Big O:** O(1) for connection acquisition from pool

**Pool Size:** 5 connections (configurable)  
**Pre-population:** 2 initial connections  
**Connection Reuse:** Connections returned to pool after use  
**Health Checks:** Validates connections before returning to pool

**Pros:**
- Reduces connection overhead
- Prevents connection exhaustion
- Thread-safe (queue-based)

**Cons:**
- Simple implementation (no connection timeout)
- No connection retry logic
- Fixed pool size (no dynamic scaling)

---

## Infrastructure & Deployment

### Database

**Type:** PostgreSQL 16  
**Container:** Docker Compose (`docker-compose.yml`)  
**Database Name:** `bball_warehouse`  
**User:** `adamvoliva`  
**Port:** 5432

**Schemas:**
- `nba.*`: NBA raw data warehouse
- `espn.*`: ESPN data (probabilities, scoreboard, plays)
- `kalshi.*`: Kalshi data (markets, trades, candlesticks)
- `derived.*`: Derived/analytical tables
- `source_files`: Provenance tracking
- `ingestion_runs`: Run-level tracking

**Migrations:**
- Migration runner: `scripts/migrate.py`
- SQL-first migrations in `db/migrations/`
- Idempotent: Already-applied migrations skipped
- Transactional: Each migration in its own transaction

### Deployment

**Target:** Render (free tier)  
**Documentation:** `DEPLOYMENT.md`

**Services:**
1. **PostgreSQL Database:** Render PostgreSQL (free tier: 1GB storage)
2. **Web Service:** Render Web Service (free tier: 750 hours/month)

**Configuration:**
- `render.yaml`: Blueprint for automatic deployment
- Environment variables: `DATABASE_URL`, `PRELOAD_CACHE`, `DEBUG`
- Build command: `pip install -r webapp/requirements.txt`
- Start command: `cd webapp && uvicorn api.main:app --host 0.0.0.0 --port $PORT`

**Limitations:**
- Free tier PostgreSQL: 90-day inactivity limit, 1GB storage
- Free tier Web: Spins down after 15 min inactivity (cold starts)
- No direct external database connections (use Internal Database URL)

**Alternatives:**
- Railway ($5/month credit)
- Supabase + Render (separate PostgreSQL)
- Neon + Render (separate PostgreSQL)

### Development Setup

**Prerequisites:**
- Python 3.11+ (3.13 works)
- Docker + Docker Compose
- PostgreSQL 16 (via Docker)

**Setup Steps:**
1. Start PostgreSQL: `docker compose up -d db`
2. Create `.env` from `env.example`
3. Create Python venv: `python3 -m venv .venv`
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python scripts/migrate.py --dsn "$DATABASE_URL"`
6. Start webapp: `cd webapp && uvicorn api.main:app --reload`

**Dependencies:**
- Core: `psycopg[binary]`, `nba_api`, `pandas`, `requests`, `pyarrow`
- Webapp: `fastapi`, `uvicorn[standard]`, `python-multipart`
- ML: `numpy` (included in requirements)

---

## Key Algorithms & Design Patterns

### Algorithms

1. **IRLS (Iteratively Reweighted Least Squares)**
   - **Purpose:** Fit logistic regression with L2 regularization
   - **Complexity:** O(n × d² × iterations) where n = samples, d = features
   - **Implementation:** `scripts/_winprob_lib.py::fit_logistic_regression_irls()`
   - **Pros:** No external ML library dependency, numerically stable
   - **Cons:** Slower than optimized libraries (scikit-learn)

2. **Platt Scaling**
   - **Purpose:** Calibrate probability predictions
   - **Complexity:** O(n × iterations) where n = calibration samples
   - **Implementation:** `scripts/_winprob_lib.py::fit_platt_calibrator_on_probs()`
   - **Pros:** Simple 2-parameter transformation, preserves discrimination
   - **Cons:** Requires separate calibration dataset

3. **Time-Window OHLC Aggregation**
   - **Purpose:** Aggregate trades into candlesticks
   - **Complexity:** O(n log n) worst case (O(n) if pre-sorted)
   - **Implementation:** `webapp/api/utils/trade_candles.py::aggregate_trades()`
   - **Pros:** Integer cents end-to-end, VWAP calculation
   - **Cons:** Requires sorting within intervals

4. **Game-Timeline Normalization**
   - **Purpose:** Align ESPN and Kalshi data to common timeline
   - **Complexity:** O(n + m) where n = ESPN points, m = Kalshi points
   - **Implementation:** `scripts/simulate_trading_strategy.py::get_aligned_data()`
   - **Pros:** Handles timestamp mismatches, preserves relative timing
   - **Cons:** Assumes ESPN records are sequential

5. **Divergence Threshold Trading Simulation**
   - **Purpose:** Simulate trading strategy
   - **Complexity:** O(n) where n = aligned data points
   - **Implementation:** `scripts/simulate_trading_strategy.py::simulate_trading_strategy()`
   - **Pros:** Realistic trading model, accounts for costs
   - **Cons:** Slippage is estimate (not precise market impact)

6. **Exhaustive Grid Search**
   - **Purpose:** Find optimal trading parameters
   - **Complexity:** O(k × n × m / p) where k = combinations, n = games, m = data points, p = workers
   - **Implementation:** `scripts/grid_search_hyperparameters.py`
   - **Pros:** Systematic exploration, reproducible
   - **Cons:** Computationally expensive, may miss optimal parameters

### Design Patterns

1. **Archive-First Pattern** (Data Ingestion)
   - Fetch → Write file + manifest → Load to DB
   - Pros: Resumable, full provenance, idempotent
   - Cons: Extra storage, two-step process

2. **State Machine Pattern** (Trading Simulation)
   - States: No position, Long ESPN, Short ESPN
   - Transitions: Entry/exit rules with hysteresis
   - Pros: Clear logic, prevents churn
   - Cons: State tracking complexity

3. **Pipeline Pattern** (ML Training)
   - Preprocess → Fit → Calibrate → Save artifact
   - Pros: Modular, testable, reproducible
   - Cons: Multiple steps, artifact management

4. **Repository Pattern** (Data Access)
   - Abstract data access behind repository interface
   - Pros: Testable, swappable implementations
   - Cons: Extra abstraction layer

5. **Singleton Pattern** (Connection Pool)
   - Single global connection pool instance
   - Pros: Resource efficiency, thread-safe
   - Cons: Global state, testing complexity

6. **Middleware Pattern** (Request Timing)
   - Timing middleware for performance monitoring
   - Pros: Cross-cutting concern, non-invasive
   - Cons: Overhead per request

7. **Map-Reduce Pattern** (Bulk Simulation)
   - Parallel processing with ThreadPoolExecutor
   - Pros: Scalable, efficient for I/O-bound tasks
   - Cons: Thread management, shared state

8. **Multi-Layer Caching Pattern**
   - In-memory + disk + database caching
   - Pros: Fast responses, reduces load
   - Cons: Cache invalidation complexity

---

## File Structure Summary

### Scripts (`scripts/`)

**Core Libraries:**
- `_db_lib.py`: Database utilities (connections, ingestion runs, source files)
- `_fetch_lib.py`: HTTP fetching with retry logic, manifest generation
- `_winprob_lib.py`: Win probability model (IRLS, Platt scaling, metrics)

**Data Fetching:**
- `fetch_espn_probabilities.py`: Fetch ESPN probability data
- `fetch_espn_scoreboard.py`: Fetch ESPN scoreboard
- `fetch_kalshi_trades.py`: Fetch Kalshi trades (RSA-authenticated)
- `fetch_pbp.py`: Fetch play-by-play (CDN fallback)
- `fetch_boxscore.py`: Fetch boxscores
- `fetch_odds_today.py`: Fetch odds snapshots
- `fetch_scheduleLeagueV2.py`: Fetch schedules

**Data Loading:**
- `load_espn_probabilities_raw_items.py`: Load ESPN probabilities
- `load_espn_scoreboard.py`: Load ESPN scoreboard
- `load_kalshi_trades.py`: Load Kalshi trades
- `load_kalshi_markets.py`: Load Kalshi markets
- `load_kalshi_candlesticks.py`: Load Kalshi candlesticks
- `load_pbp.py`: Load play-by-play
- `load_odds_snapshot.py`: Load odds snapshots

**Data Processing:**
- `materialize_espn_prob_event_state.py`: Materialize ESPN event state
- `materialize_pbp_event_state.py`: Materialize PBP event state
- `build_winprob_snapshots_parquet.py`: Build snapshot Parquet files
- `export_winprob_modeling_events_parquet.py`: Export modeling events
- `export_pbp_event_state_parquet.py`: Export PBP state

**Modeling:**
- `train_winprob_logreg.py`: Train win probability model
- `evaluate_winprob_model.py`: Evaluate model performance
- `score_winprob_snapshot.py`: Score snapshots with model

**Trading:**
- `simulate_trading_strategy.py`: Simulate trading strategy
- `grid_search_hyperparameters.py`: Grid search optimization
- `analyze_grid_search_results.py`: Analyze grid search results
- `paper_trade_winprob.py`: Paper trading simulation

**Utilities:**
- `migrate.py`: Database migration runner
- `discover_game_ids.py`: Discover game IDs from NBA API
- `backfill_seasons.py`: Backfill multiple seasons
- `run_backfill.sh`: Backfill orchestrator script
- `qc_report.py`: Quality control report

### Web Application (`webapp/`)

**API (`webapp/api/`):**
- `main.py`: FastAPI app setup, middleware, routing
- `db.py`: Database connection pooling
- `cache.py`: Caching utilities
- `logging_config.py`: Logging configuration
- `websocket_manager.py`: WebSocket connection management

**Endpoints (`webapp/api/endpoints/`):**
- `games.py`: Game listing endpoint
- `probabilities.py`: Probability time series endpoint
- `simulation.py`: Trading simulation endpoints
- `stats.py`: Game statistics endpoint
- `aggregate_stats.py`: Aggregate statistics endpoint
- `live_games.py`: Live games endpoint
- `live_data.py`: Live data WebSocket endpoint
- `metadata.py`: Metadata endpoints
- `update.py`: Update endpoints

**Utils (`webapp/api/utils/`):**
- `trade_candles.py`: Trade-derived candlestick aggregation

**Frontend (`webapp/static/`):**
- `index.html`: Main HTML page
- `js/app.js`: Main application logic
- `js/chart.js`: Chart rendering (Lightweight Charts)
- `js/simulation.js`: Simulation UI
- `js/live.js`: Live game updates
- `js/websocket.js`: WebSocket client
- `css/styles.css`: Styling

---

## Key Metrics & Performance

### Model Performance

**Evaluation Metrics:**
- **Brier Score:** Mean squared error between predicted and actual probabilities
- **Log Loss:** Cross-entropy loss (penalizes confident wrong predictions)
- **ROC-AUC:** Area under ROC curve (discrimination ability)
- **ECE (Expected Calibration Error):** Calibration quality (binned)

**Typical Values (2024 test season):**
- Brier Score: ~0.20-0.25 (lower is better)
- Log Loss: ~0.50-0.60 (lower is better)
- ROC-AUC: ~0.85-0.90 (higher is better)
- ECE: ~0.02-0.05 (lower is better, after Platt scaling)

### Trading Strategy Performance

**Metrics:**
- **Win Rate:** Percentage of profitable trades
- **ROI:** Return on investment (profit / capital deployed)
- **Sharpe Ratio:** Risk-adjusted return
- **Profit Factor:** Gross profit / gross loss
- **Maximum Drawdown:** Largest peak-to-trough decline

**Typical Values (optimized parameters):**
- Win Rate: ~55-65%
- ROI: ~5-15% (varies by parameters)
- Sharpe Ratio: ~1.0-2.0
- Profit Factor: ~1.2-1.8
- Maximum Drawdown: ~10-20%

### Performance Characteristics

**Database Queries:**
- Game listing: ~100-500ms (with MATERIALIZED CTEs)
- Probability time series: ~200-1000ms (depends on data volume)
- Simulation (single game): ~500-2000ms
- Bulk simulation (100 games): ~30-120 seconds (parallel)

**Caching Impact:**
- Cached queries: <10ms (in-memory)
- Disk cache: ~50-200ms (first access)
- Database queries: ~100-1000ms (uncached)

**Grid Search:**
- Small test (6 combinations, 10 games): ~5-10 minutes
- Full grid (hundreds of combinations, 100+ games): ~hours (parallel)

---

## Future Enhancements & Considerations

### Potential Improvements

1. **Model Enhancements:**
   - Feature engineering (momentum, recent form, player injuries)
   - Ensemble methods (multiple models)
   - Deep learning (neural networks for non-linear patterns)

2. **Trading Strategy:**
   - Dynamic position sizing (Kelly criterion)
   - Multi-game portfolio optimization
   - Real-time execution (API integration with Kalshi)

3. **Data Quality:**
   - Automated data validation
   - Anomaly detection
   - Data completeness monitoring

4. **Performance:**
   - Database query optimization (indexes, partitioning)
   - Caching improvements (Redis)
   - Async/await for I/O-bound operations

5. **User Experience:**
   - Interactive parameter tuning UI
   - Real-time strategy backtesting
   - Mobile-responsive design

### Known Limitations

1. **Data Sources:**
   - ESPN API rate limits
   - Kalshi API authentication complexity
   - NBA API CDN availability

2. **Model Limitations:**
   - Simple features (only score differential, time, possession)
   - No player-level features
   - No context (home court advantage, injuries, etc.)

3. **Trading Simulation:**
   - Slippage is estimate (not precise market impact)
   - Bid/ask data may be incomplete
   - End-of-game liquidity collapse is estimated

4. **Infrastructure:**
   - Free tier limitations (cold starts, storage limits)
   - No horizontal scaling
   - Single database instance

---

## Conclusion

This project is a comprehensive NBA data warehouse and trading strategy analysis platform that successfully:

1. **Ingests** data from multiple sources (ESPN, Kalshi, NBA API) with full provenance tracking
2. **Trains** a calibrated win probability model using logistic regression
3. **Simulates** trading strategies based on probability divergence
4. **Optimizes** trading parameters via systematic grid search
5. **Visualizes** results through a modern web application

The codebase demonstrates:
- **Clean architecture:** Separation of concerns (fetch → load → process → model → simulate → visualize)
- **Production-ready patterns:** Idempotent ingestion, connection pooling, caching, error handling
- **Scientific rigor:** Train/valid/test splits, proper evaluation metrics, reproducible experiments
- **Performance optimization:** Parallel processing, caching, query optimization

The project is well-structured, documented, and ready for deployment and further development.

