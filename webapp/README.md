# NBA Win Probability & Trading Analysis Web App

A comprehensive web application for analyzing NBA game win probabilities, comparing ESPN's live probability data with Kalshi prediction market prices, and simulating trading strategies based on probability divergences.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Application Sections](#application-sections)
- [Database Schema](#database-schema)
- [Data Sources](#data-sources)
- [Raw Data Folder](#raw-data-folder)
- [Caching System](#caching-system)
- [API Endpoints](#api-endpoints)
- [Setup & Installation](#setup--installation)
- [Development](#development)

---

## Overview

This web application provides:

1. **Win Probability Visualization**: Interactive charts comparing ESPN's live win probability with Kalshi prediction market prices
2. **Game Analytics**: Statistical analysis of probability movements, volatility, and game outcomes
3. **Trading Simulation**: Backtest trading strategies based on ESPN-Kalshi probability divergences
4. **Live Data Updates**: Real-time data ingestion from ESPN and Kalshi APIs
5. **Aggregate Statistics**: Season-wide analysis of probability patterns and trading opportunities

**Data Sources**: This webapp exclusively uses **Kalshi and ESPN data** for all functionality. NBA data exists in the database but is not used by the webapp and can be ignored.

**Design Pattern**: Modular Router Pattern with Repository Pattern for data access  
**Algorithm**: Time-series alignment and aggregation  
**Big O Complexity**: O(n + m) for time-series alignment where n = ESPN points, m = Kalshi candles

---

## Architecture

```
webapp/
├── api/
│   ├── main.py                 # FastAPI application entry point
│   ├── cache.py                 # Caching utilities with file persistence
│   ├── db.py                    # Database connection management
│   ├── endpoints/               # API route handlers
│   │   ├── games.py            # Game listing and metadata
│   │   ├── probabilities.py   # Probability time series data
│   │   ├── stats.py            # Game-level statistics
│   │   ├── aggregate_stats.py # Season-wide aggregate statistics
│   │   ├── live_games.py       # Live game monitoring
│   │   ├── live_data.py        # WebSocket live data streaming
│   │   ├── simulation.py       # Trading strategy simulation
│   │   └── update.py           # Data update triggers
│   ├── data_sources/           # External API clients
│   │   ├── espn_live.py        # ESPN live API client
│   │   └── kalshi_live.py      # Kalshi API client
│   └── websocket_manager.py    # WebSocket connection management
├── static/                      # Frontend assets
│   ├── index.html              # Main SPA entry point
│   ├── css/styles.css          # Styling
│   ├── js/                     # Frontend JavaScript modules
│   │   ├── app.js             # Main application logic
│   │   ├── routing.js         # Client-side routing
│   │   ├── chart.js           # TradingView chart integration
│   │   ├── simulation.js      # Simulation UI logic
│   │   └── websocket.js       # WebSocket client
│   └── templates/             # HTML templates
└── requirements.txt            # Python dependencies
```

**Tech Stack**:
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Vanilla JavaScript + TradingView Lightweight Charts
- **Database**: PostgreSQL 16
- **Caching**: In-memory with file persistence
- **Real-time**: WebSocket for live updates

---

## Application Sections

### 1. Game List View (`/games`)

**Purpose**: Browse and filter games with probability data

**Features**:
- Pagination (default 50 games per page)
- Filtering by season, team, date range, Kalshi availability
- Sorting by date, volatility, standard deviation, range, or score
- Display of game metadata (teams, scores, probability stats)

**Design Pattern**: Repository Pattern  
**Algorithm**: SQL aggregation with pagination  
**Big O**: O(n) where n = number of games returned

### 2. Game Detail View (`/games/{id}`)

**Purpose**: Detailed probability chart for a single game

**Features**:
- Interactive TradingView chart with zoom/pan
- ESPN probability time series (home/away)
- Kalshi market price overlay (when available)
- Score progression and quarter markers
- Crosshair showing exact values at any point

**Design Pattern**: Service Pattern for data alignment  
**Algorithm**: Time-series alignment (O(n + m))  
**Big O**: O(n + m) where n = ESPN points, m = Kalshi candles

### 3. Live Games View (`/live`)

**Purpose**: Monitor games currently in progress

**Features**:
- Real-time updates via WebSocket
- Auto-refresh of probability data
- Visual indicators for active games
- Quick navigation to game detail

**Design Pattern**: Observer Pattern (WebSocket)  
**Algorithm**: Event-driven updates  
**Big O**: O(1) per update event

### 4. Simulation View (`/simulation`)

**Purpose**: Backtest trading strategies based on probability divergences

**Features**:
- Configurable entry/exit thresholds
- Bet amount configuration
- Time exclusion (first/last N seconds)
- Detailed trade-by-trade analysis
- Profit/loss calculation
- Win rate statistics

**Design Pattern**: Strategy Pattern  
**Algorithm**: Divergence Threshold Trading Simulation  
**Big O**: O(n) where n = aligned data points per game

**Trading Strategy**:
- **Long ESPN**: Buy when ESPN probability > Kalshi price + entry_threshold
- **Short ESPN**: Sell when ESPN probability < Kalshi price - entry_threshold
- **Exit**: Close position when divergence converges to < exit_threshold

---

## Trading Simulation Logic

The trading simulation (`scripts/trade/simulate_trading_strategy.py`) implements a **trading model** (not a betting model) that profits from price movements in prediction markets. Understanding this logic is essential for interpreting simulation results.

### Core Concept: Trading vs Betting

**Critical Distinction**: This is a **trading simulator**, not a betting simulator.

- **Trading Model**: P&L is calculated from **price movements** (entry price vs exit price), NOT final game outcome
- **Betting Model**: P&L would be calculated from binary outcome (win/loss)

**Why This Matters**: You can profit even if you're "wrong" about the outcome, as long as the market price moves in your favor. Conversely, you can lose even if you're "right" about the outcome if the market price moves against you.

**Example**:
- Enter LONG at 45 cents (ESPN says 50%, Kalshi says 45%)
- Exit at 48 cents (divergence converged)
- Profit: 3 cents per contract (regardless of final game outcome)

### Entry Logic

**State Machine Pattern**: The simulation uses a state machine to track open positions and manage entry/exit decisions.

#### Long Position Entry

**Condition**: `ESPN_probability > Kalshi_price + entry_threshold`

**Example**: If ESPN = 55%, Kalshi = 48%, entry_threshold = 5 cents (0.05)
- Divergence = 55% - 48% = 7 cents
- 7 cents > 5 cents → **ENTER LONG**

**Direction Confirmation (Hysteresis)**: To prevent noise trading, entry only occurs when divergence is **widening** (not shrinking):
- Current divergence must be greater than previous divergence
- This prevents entering on temporary spikes that immediately reverse

**Execution**: Buy at **ask price** (you pay the ask to enter long position)

#### Short Position Entry

**Condition**: `ESPN_probability < Kalshi_price - entry_threshold`

**Example**: If ESPN = 45%, Kalshi = 52%, entry_threshold = 5 cents (0.05)
- Divergence = 45% - 52% = -7 cents
- |-7 cents| > 5 cents → **ENTER SHORT**

**Direction Confirmation**: Divergence must be **widening** (becoming more negative)

**Execution**: Sell at **bid price** (you receive the bid to enter short position)

### Exit Logic

**Condition**: `|ESPN_probability - Kalshi_price| < exit_threshold`

**Example**: If ESPN = 50%, Kalshi = 50.5%, exit_threshold = 1 cent (0.01)
- Divergence = |50% - 50.5%| = 0.5 cents
- 0.5 cents < 1 cent → **EXIT**

**Hysteresis Exit**: Exit only occurs when divergence **crosses from outside to inside** the exit threshold:
- Previous divergence must have been >= exit_threshold
- Current divergence must be < exit_threshold
- This prevents churn (exiting and immediately re-entering)

**Minimum Holding Period**: Positions must be held for at least `min_hold_seconds` (default: 30 seconds) before allowing exit. This prevents noise trading on rapid price fluctuations.

**Execution**:
- **Long exit**: Sell at **bid price** (you receive the bid to exit)
- **Short exit**: Buy at **ask price** (you pay the ask to exit)

### Position Sizing (Risk-Neutral)

**Goal**: Both long and short positions have the **same maximum risk** (`bet_amount_dollars`).

#### Long Position Sizing

**Formula**: `num_contracts = bet_amount / entry_price`

**Rationale**: Maximum loss per contract = entry_price (if price goes to 0)
- If entry_price = 45 cents, max loss = 45 cents per contract
- To risk $20: `num_contracts = $20 / $0.45 = 44.44 contracts`

#### Short Position Sizing

**Formula**: `num_contracts = bet_amount / (1 - entry_price)`

**Rationale**: Maximum loss per contract = (1 - entry_price) (if price goes to 1.0)
- If entry_price = 55 cents, max loss = 45 cents per contract
- To risk $20: `num_contracts = $20 / $0.45 = 44.44 contracts`

**Result**: Both positions have identical maximum risk for the same `bet_amount`.

### Profit & Loss Calculation

**Trading Model**: P&L is calculated from **price movements**, not binary outcomes.

#### Long Position P&L

**Gross Profit**: `num_contracts × (exit_price - entry_price)`

**Example**:
- Entry: 45 cents (ask), Exit: 48 cents (bid)
- Position size: 44.44 contracts
- Gross profit: 44.44 × (0.48 - 0.45) = $1.33

#### Short Position P&L

**Gross Profit**: `(num_contracts × entry_price) - (num_contracts × exit_price)`

**Example**:
- Entry: 55 cents (bid), Exit: 52 cents (ask)
- Position size: 44.44 contracts
- Gross profit: (44.44 × 0.55) - (44.44 × 0.52) = $1.33

### Trading Costs

**Spread Cost**: Already embedded in bid/ask execution prices (NOT double-counted)
- Long: Pay ask (higher), sell bid (lower) → spread cost is implicit
- Short: Sell bid (lower), buy ask (higher) → spread cost is implicit

**Kalshi Fees**: Calculated using formula: `7% × (price × (1 - price)) × bet_amount`
- Fees are highest at 50% probability (1.75% of bet amount)
- Fees decrease toward extremes (0% or 100%)
- Applied on both entry and exit

**Slippage** (optional): Configurable execution cost beyond bid-ask spread
- Represents market impact, execution delays, etc.
- Applied as: `slippage_rate × bet_amount` per trade leg (entry + exit)
- Default: 0.0 (disabled)

**Net Profit**: `Gross Profit - Entry Fee - Exit Fee - Entry Slippage - Exit Slippage`

### End-of-Game Handling

**Forced Close**: Any open positions at game end are closed using final market prices.

**Liquidity Collapse Penalty**: End-of-game closes apply an additional slippage penalty (2 cents) to account for:
- Reduced liquidity as game approaches end
- Market makers pulling quotes
- Execution difficulty in final moments

**Settlement**: Uses **market prices** (bid/ask), NOT binary settlement (0 or 100 cents). This maintains the trading model consistency.

### Data Alignment

Before simulation, ESPN and Kalshi data are aligned to the same game timeline (see [Time Alignment](#time-alignment-espn-and-kalshi-data-synchronization) section).

**Matching**: For each ESPN timestamp, find the closest Kalshi timestamp within 60 seconds.

**Time Filtering**: Optional exclusion of first/last N seconds to avoid:
- Pre-game noise
- End-of-game liquidity collapse

### Algorithm Summary

**Design Pattern**: State Machine Pattern  
**Algorithm**: Divergence Threshold Trading Simulation with Hysteresis  
**Big O Complexity**: O(n) where n = aligned data points per game

**Key Features**:
1. **Direction Confirmation**: Only enter when divergence is widening
2. **Hysteresis Exit**: Only exit when divergence crosses threshold (prevents churn)
3. **Minimum Holding Period**: Prevents noise trading
4. **Risk-Neutral Sizing**: Same max risk for long/short positions
5. **Trading Costs**: Fees + optional slippage included in net P&L

**Pros**:
- Realistic trading model (not betting)
- Accounts for bid/ask spread and fees
- Prevents noise trading with hysteresis
- Risk-neutral position sizing

**Cons**:
- Requires bid/ask data (falls back to mid-price with penalty if unavailable)
- End-of-game liquidity collapse is estimated (not precise)
- Slippage is configurable estimate (not precise market impact model)

### 5. Aggregate Stats View (`/stats`)

**Purpose**: Season-wide analysis of probability patterns

**Features**:
- Overall statistics across all games
- Distribution analysis
- Trading opportunity identification
- Performance metrics

**Design Pattern**: Aggregation Pattern  
**Algorithm**: SQL aggregation with grouping  
**Big O**: O(n) where n = total games in season

---

## Database Schema

The application uses PostgreSQL with multiple schemas for organization:

### Core Schemas

#### `nba.*` - NBA Raw Data Warehouse

**Core Dimensions**:
- `nba.teams`: Team information (team_id, tricode, city, name)
- `nba.players`: Player information (person_id, display_name)
- `nba.games`: Game metadata (game_id, season, home/away teams, game_time_utc)
- `nba.officials`: Referee information

**Play-by-Play (PBP)**:
- `nba.pbp_events`: Individual game events with full JSONB raw data
- `nba.pbp_event_qualifiers`: Event qualifiers (many-to-many)
- `nba.pbp_event_people_filter`: People associated with events (many-to-many)

**Provenance**:
- `source_files`: Raw file archival with SHA256 hashing
- `ingestion_runs`: Run-level tracking for idempotency
- `game_ingestion_state`: Per-game ingestion state tracking

**Odds Snapshots**:
- `odds_snapshots`: Time-stamped odds snapshots
- `odds_games`: Games in each snapshot
- `odds_markets`: Markets per game (deterministic market_key)
- `odds_books`: Sportsbooks offering odds
- `odds_outcomes`: Individual outcome odds

**Raw Payloads**:
- `game_boxscores`: Full boxscore JSONB payloads
- `schedule_snapshots`: Schedule snapshot JSONB payloads

#### `derived.*` - Derived/Analytical Tables

**PBP Event State**:
- `derived.pbp_event_state`: Compact game state per event (point differential, time remaining)

**ESPN Data**:
- `derived.espn_probabilities_raw_items`: Raw ESPN probability items
- `derived.espn_probabilities`: Normalized ESPN probabilities
- `derived.espn_prob_event_state`: ESPN probability aligned with game state
- `derived.espn_scoreboard_games`: Scoreboard game metadata
- `derived.espn_plays`: Play-by-play events from ESPN

**Kalshi Data**:
- `kalshi.kalshi_market_snapshots`: Full Kalshi market snapshot JSONB
- `kalshi.kalshi_markets`: Denormalized market data per snapshot
- `kalshi.kalshi_candlesticks`: OHLC time-series data for markets
- `kalshi.kalshi_event_game_mapping`: Mapping between Kalshi events and NBA games

**Analytics**:
- `derived.game_stats`: Pre-computed game statistics (volatility, divergence, etc.)

### Key Relationships

```
nba.games (game_id)
  ├── nba.pbp_events (game_id)
  │   └── derived.pbp_event_state (event_id)
  ├── espn.scoreboard_games (event_id) [via date + teams matching]
  │   ├── espn.probabilities_raw_items (game_id)
  │   └── espn.prob_event_state (game_id)
  └── kalshi.markets (game_id or espn_event_id)
      └── kalshi.candlesticks (ticker)
```

**Design Pattern**: Star Schema with fact tables (pbp_events, probabilities) and dimension tables (games, teams, players)  
**Algorithm**: B-tree indexing for O(log n) lookups  
**Big O**: O(log n) for indexed queries, O(n) for full table scans

---

## Data Sources

**Important Note**: This webapp **only uses Kalshi and ESPN data** for all analysis, visualizations, and trading simulations. The NBA data (stored in the `nba.*` schema) exists in the database but is **not used** by the webapp. You can safely ignore NBA data when working with this application - all functionality relies exclusively on ESPN win probabilities and Kalshi prediction market prices.

### 1. NBA Data (Raw Warehouse)

**Note**: NBA data is stored in the database but **not used by this webapp**. It exists for historical/archival purposes only.

**Source**: NBA CDN (`cdn.nba.com`)

**Endpoints**:
- **PBP**: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json`
- **Boxscore**: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`
- **Schedule**: `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`
- **Odds**: `https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json`

**Fetch Scripts**:
- `scripts/fetch_pbp.py`: Fetch play-by-play data (auto-fallback to nba_api for older games)
- `scripts/fetch_boxscore.py`: Fetch boxscore data
- `scripts/fetch_scheduleLeagueV2.py`: Fetch schedule snapshots
- `scripts/fetch_odds_today.py`: Fetch daily odds snapshots

**Load Scripts**:
- `scripts/load_pbp.py`: Load PBP events into database
- `scripts/load_odds_snapshot.py`: Load odds snapshots

**Design Pattern**: ETL Pattern (Extract → Transform → Load)  
**Algorithm**: Batch processing with idempotency checks  
**Big O**: O(n) where n = number of games/events

### 2. ESPN Data

**Source**: ESPN Live API (`site.api.espn.com`)

**Endpoints**:
- **Scoreboard**: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- **Win Probabilities**: Embedded in game detail endpoints
- **Plays**: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard/{eventId}`

**Fetch Scripts**:
- `scripts/fetch_espn_scoreboard.py`: Fetch scoreboard with game metadata
- `scripts/fetch_espn_probabilities.py`: Fetch win probability time series
- `scripts/backfill_espn_probabilities_season.py`: Backfill historical seasons

**Load Scripts**:
- `scripts/load_espn_scoreboard.py`: Load scoreboard games
- `scripts/load_espn_probabilities_raw_items.py`: Load raw probability items
- `scripts/materialize_espn_probabilities.py`: Materialize normalized probabilities
- `scripts/materialize_espn_prob_event_state.py`: Create aligned event state

**Update Frequency**: 
- Live games: Every 30 seconds (via `/api/update/trigger-update`)
- Historical: Batch backfill by season

**Design Pattern**: Temporal Snapshot Pattern  
**Algorithm**: Incremental updates with deduplication  
**Big O**: O(n) where n = number of probability updates

### 3. Kalshi Data

**Source**: Kalshi API (`api.calendar.kalshi.com`)

**Endpoints**:
- **Markets**: `GET /trade-api/v2/portfolios/markets/{series_ticker}`
- **Candlesticks**: `GET /trade-api/v2/portfolios/markets/{ticker}/candlesticks`
- **Trades**: `GET /trade-api/v2/portfolios/markets/{ticker}/trades`

**Authentication**: RSA-signed requests with API key pair

**Fetch Scripts**:
- `scripts/load_kalshi_markets.py`: Fetch and load market metadata
- `scripts/fetch_kalshi_trades.py`: Fetch trade history for markets
- `scripts/load_kalshi_candlesticks.py`: Load candlestick OHLC data

**Update Frequency**:
- Markets: Daily snapshot
- Candlesticks: Hourly or on-demand
- Trades: Historical backfill

**Design Pattern**: Temporal Snapshot Pattern + Time-Series Tables  
**Algorithm**: Pagination with rate limiting  
**Big O**: O(n) where n = number of markets/candlesticks

**Matching to NBA Games**:
- Direct match via `espn_event_id` (when available)
- Fallback: Match by date + team tricodes (via migration `028_kalshi_espn_join.sql`)

---

## Time Alignment: ESPN and Kalshi Data Synchronization

This webapp aligns ESPN win probabilities and Kalshi prediction market prices to the same game timeline, even though they use different timestamp systems. Understanding this alignment is critical for interpreting the data correctly.

### The Challenge

- **ESPN `last_modified_utc`**: Wall-clock timestamp when ESPN recorded/updated the probability (e.g., 5:02 PM PT, 5:05 PM PT). This represents when ESPN updated their system, not game clock time.
- **Kalshi `period_ts`**: Wall-clock timestamp for each candlestick period (e.g., 5:01 PM PT, 5:04 PM PT). This represents actual market trading times.
- **Game Start (`event_date`)**: Scheduled game start time from ESPN scoreboard (e.g., 5:00 PM PT).

These timestamps don't naturally align because:
1. ESPN may start recording probabilities before the game starts
2. ESPN updates occur at irregular intervals (not synchronized with game clock)
3. Kalshi candlesticks are time-bucketed trading periods (not game-time aligned)

### ESPN Data Alignment

**Field**: `espn.probabilities_raw_items.last_modified_utc`

**Process** (implemented in `probabilities.py` and `simulate_trading_strategy.py`):

1. **Get game start time**: Retrieve `event_date` from `espn.scoreboard_games` (scheduled game start)
2. **Find first ESPN record**: Identify the earliest `last_modified_utc` timestamp
3. **Calculate relative timing**: For each ESPN record:
   - Compute elapsed time from first ESPN record: `elapsed_from_first = espn_recording_timestamp - first_espn_timestamp`
   - Map to game timeline: `aligned_timestamp = game_start_timestamp + elapsed_from_first`

**Example**:
```
Game scheduled: 5:00 PM PT (event_date)
First ESPN update: 5:02 PM PT (last_modified_utc) → Aligned to: 5:00 PM PT
Second ESPN update: 5:05 PM PT (last_modified_utc) → Aligned to: 5:03 PM PT
Third ESPN update: 5:08 PM PT (last_modified_utc) → Aligned to: 5:06 PM PT
```

**Key Insight**: ESPN timestamps preserve their relative spacing (3 minutes apart) but are shifted to align with game start. This ensures ESPN probability updates map to the correct game moments.

**Design Pattern**: Temporal Alignment with Relative Time Preservation  
**Algorithm**: Linear time mapping (O(n) where n = ESPN points)  
**Big O**: O(n) for alignment transformation

### Kalshi Data Filtering

**Field**: `kalshi.candlesticks.period_ts`

**Process** (implemented in `probabilities.py`):

1. **Use game start**: `event_date` from `espn.scoreboard_games` as game start time
2. **Calculate game duration**: `MAX(last_modified_utc) - MIN(last_modified_utc)` from ESPN data
   - This represents how long ESPN was recording probabilities (typically 2-3 hours for a full game)
3. **Filter candlesticks**: Include only Kalshi candlesticks where:
   ```sql
   period_ts >= game_start 
   AND period_ts <= (game_start + duration)
   ```

**Example**:
```
Game start: 5:00 PM PT (event_date)
ESPN duration: 2h 28m (from first to last ESPN record)
Kalshi window: 5:00 PM PT to 7:28 PM PT
Only candlesticks with period_ts in [5:00 PM, 7:28 PM] are included
```

**Key Insight**: Kalshi timestamps are already in wall-clock time and don't need shifting. They're filtered to the game window and used directly.

**Design Pattern**: Temporal Window Filtering  
**Algorithm**: Range query filtering (O(m) where m = Kalshi candles)  
**Big O**: O(m) for filtering operation

### Final Alignment for Trading Simulation

**Process** (implemented in `simulate_trading_strategy.py`):

After both datasets are aligned to the game timeline:

1. **Find closest match**: For each aligned ESPN timestamp, find the closest Kalshi timestamp using a nearest-neighbor search
2. **Match threshold**: Only pair data points if timestamps are within 60 seconds
3. **Result**: Paired ESPN probability and Kalshi price representing approximately the same game moment

**Example**:
```
ESPN aligned timestamp: 5:03 PM PT (home_prob = 0.55)
Closest Kalshi timestamp: 5:03:15 PM PT (price = 52 cents)
Time difference: 15 seconds (< 60s threshold) → MATCHED
```

**Design Pattern**: Nearest-Neighbor Matching  
**Algorithm**: Linear scan with early termination (O(n + m) where n = ESPN points, m = Kalshi candles)  
**Big O**: O(n + m) for matching operation

### Why This Matters

This alignment ensures that:
- **Trading simulations** compare ESPN probabilities and Kalshi prices from the same game moments
- **Visualizations** show synchronized probability movements over game time
- **Analytics** measure divergence between ESPN and Kalshi at corresponding game states

Without this alignment, comparisons would be meaningless because ESPN and Kalshi data would represent different moments in the game.

### Summary

| Data Source | Timestamp Field | Alignment Method | Result |
|------------|----------------|------------------|--------|
| **ESPN** | `last_modified_utc` | Shifted to align with `event_date` while preserving relative timing | Aligned to game timeline |
| **Kalshi** | `period_ts` | Filtered to game window `[event_date, event_date + duration]` | Filtered to game window |
| **Final Match** | Both aligned timestamps | Nearest-neighbor matching within 60 seconds | Paired data points |

**Overall Complexity**: O(n + m) where n = ESPN points, m = Kalshi candles

---

## Raw Data Folder

The `data/raw/` directory stores all fetched raw JSON files before database ingestion. This provides:

1. **Reproducibility**: Full historical data for replay/reprocessing
2. **Provenance**: SHA256 hashing ensures data integrity
3. **Debugging**: Raw files available for inspection
4. **Idempotency**: Avoid re-fetching identical data

### Structure

```
data/raw/
├── pbp/                          # NBA play-by-play JSON files
│   └── {gameId}.json
├── boxscore/                      # NBA boxscore JSON files
│   └── {gameId}.json
├── schedule/                      # Schedule snapshots
│   └── scheduleLeagueV2_{timestamp}.json
├── odds/                          # Odds snapshots
│   └── odds_todaysGames_{timestamp}.json
├── espn/
│   ├── scoreboard/                # ESPN scoreboard snapshots
│   │   └── {date}_{timestamp}.json
│   ├── probabilities/             # ESPN probability time series
│   │   └── {season}/
│   │       └── {gameId}_{timestamp}.json
│   └── plays/                     # ESPN play-by-play
│       └── {season}/
│           └── {gameId}_{timestamp}.json
├── kalshi/
│   ├── markets/                   # Kalshi market snapshots
│   │   ├── fetch_{timestamp}/
│   │   │   └── {series_ticker}.json
│   │   └── {series_ticker}_latest.json
│   ├── candlesticks/              # Kalshi candlestick data
│   │   └── fetch_{timestamp}/
│   │       └── candlesticks_{ticker}.json
│   └── trades/                    # Kalshi trade history
│       └── fetch_{timestamp}/
│           └── trades_{ticker}.json
└── nba_api/                       # NBA API responses (fallback)
    └── leaguegamefinder/
        └── season={season}/
            └── page_{page}.json
```

### Manifest Files

Each raw file has an accompanying `.manifest.json` file containing:
- `source_type`: Data source identifier
- `source_key`: Unique identifier (game_id, ticker, etc.)
- `fetched_at`: ISO 8601 timestamp
- `http_status`: HTTP response code
- `etag`: ETag header (if available)
- `sha256_hex`: SHA256 hash of file contents
- `byte_size`: File size in bytes

**Design Pattern**: Immutable Data Pattern  
**Algorithm**: Content-addressable storage via SHA256  
**Big O**: O(1) for file lookup by hash

### Provenance Tracking

Raw files are tracked in `source_files` table:
- Links raw files to database records
- Enables replay of ingestion runs
- Supports data lineage queries

---

## Caching System

The application uses a multi-layer caching strategy to optimize performance:

### 1. In-Memory Cache (`SimpleCache`)

**Location**: `api/cache.py`

**Features**:
- TTL-based expiration (configurable per endpoint)
- File persistence (survives server reloads)
- Thread-safe operations
- Data version checking for cache invalidation
- Background refresh for expensive calculations

**Storage**: `.cache/` directory in webapp folder

**Cache Files**:
- `get_aggregate_stats.cache`: Aggregate statistics (24h TTL)
- `list_games.cache`: Game list queries (1h TTL)
- `get_game_stats.cache`: Individual game stats (varies by game state)
- `simulation_results.cache`: Simulation results (1 year for completed games)

**Design Pattern**: Decorator Pattern + Persistence Layer  
**Algorithm**: Dictionary-based cache with timestamp expiration + pickle serialization  
**Big O**: O(1) for get/set operations, O(n) for save/load where n = cache size

### 2. Background Refresh

**Purpose**: Return stale cache immediately while refreshing in background

**Use Cases**:
- Expensive calculations (aggregate stats)
- Acceptable stale data (completed games)

**Implementation**:
- Thread-safe locks prevent duplicate refreshes
- Session-based tracking prevents refresh loops
- Automatic cache update after refresh completes

**Design Pattern**: Stale-While-Revalidate Pattern  
**Algorithm**: Background thread with lock coordination  
**Big O**: O(1) for cache return, O(n) for background calculation

### 3. Dynamic TTL

**Purpose**: Cache completed games longer than in-progress games

**Logic**:
- Completed games: 24 hours (or longer)
- In-progress games: 5 minutes
- Determined by `dynamic_ttl` callback function

**Design Pattern**: Strategy Pattern  
**Algorithm**: Conditional TTL assignment  
**Big O**: O(1) for TTL lookup

### 4. Database-Level Caching

**Materialized Views**: Pre-computed aggregations (e.g., `derived.game_stats`)

**Indexes**: Optimized for common query patterns

**Design Pattern**: Materialized View Pattern  
**Algorithm**: Periodic refresh via scripts  
**Big O**: O(n log n) for refresh, O(log n) for queries

---

## API Endpoints

### Games

#### `GET /api/games`

List games with pagination and filtering.

**Query Parameters**:
- `season` (string): Season label, e.g., "2025-26" (default)
- `limit` (int): Max games to return, 1-200 (default: 50)
- `offset` (int): Pagination offset (default: 0)
- `has_kalshi` (bool): Filter by Kalshi availability (default: true)
- `sort_by` (string): Sort field - `date`, `volatility`, `std_dev`, `range`, `score` (default: `date`)
- `sort_order` (string): `asc` or `desc` (default: `desc`)
- `team_filter` (string): Filter by team abbreviation
- `date_from` (string): Filter from date (YYYY-MM-DD)
- `date_to` (string): Filter to date (YYYY-MM-DD)

**Response**:
```json
{
  "games": [
    {
      "game_id": "401736807",
      "season": "2025-26",
      "prob_count": 1250,
      "final_home_score": 112,
      "final_away_score": 108,
      "home_won": true,
      "home_team_abbr": "MIN",
      "away_team_abbr": "BOS",
      "home_team_name": "Minnesota Timberwolves",
      "away_team_name": "Boston Celtics",
      "game_date": "2025-12-25T00:00:00",
      "has_kalshi": true,
      "stats": {
        "min_probability": 0.15,
        "max_probability": 0.85,
        "mean_probability": 0.52,
        "standard_deviation": 0.12,
        "probability_range": 0.70
      }
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

**Cache**: 1 hour TTL

#### `GET /api/games/{game_id}/meta`

Get game metadata (teams, scores, dates).

**Response**:
```json
{
  "game_id": "401736807",
  "home_team": {
    "abbrev": "MIN",
    "display_name": "Minnesota Timberwolves"
  },
  "away_team": {
    "abbrev": "BOS",
    "display_name": "Boston Celtics"
  },
  "game_date": "2025-12-25T00:00:00",
  "final_home_score": 112,
  "final_away_score": 108,
  "home_won": true
}
```

### Probabilities

#### `GET /api/games/{game_id}/probs`

Get probability time series for a game.

**Query Parameters**:
- `include_kalshi` (bool): Include Kalshi data (default: true)

**Response**:
```json
{
  "espn": [
    {
      "time": 0,
      "home_prob": 0.50,
      "away_prob": 0.50,
      "home_score": 0,
      "away_score": 0
    }
  ],
  "kalshi": {
    "KXNBAGAME-25DEC25MINBOS-MIN": {
      "team": "Minnesota Timberwolves",
      "data": [
        {
          "time": 0,
          "price": 45,
          "bid": 44,
          "ask": 46,
          "volume": 1234
        }
      ]
    }
  }
}
```

**Cache**: Dynamic TTL (5 min for in-progress, 24h for completed)

### Statistics

#### `GET /api/games/{game_id}/stats`

Get detailed statistics for a game.

**Response**:
```json
{
  "game_id": "401736807",
  "espn_stats": {
    "volatility": 0.15,
    "lead_changes": 8,
    "max_lead": 12
  },
  "kalshi_stats": {
    "avg_price": 48,
    "price_range": 35
  },
  "divergence_stats": {
    "mean_divergence": 0.02,
    "max_divergence": 0.08
  }
}
```

**Cache**: Dynamic TTL

#### `GET /api/aggregate-stats`

Get season-wide aggregate statistics.

**Query Parameters**:
- `season` (string): Season label (default: "2025-26")

**Response**:
```json
{
  "season": "2025-26",
  "games_with_stats": 150,
  "overall_stats": {
    "avg_volatility": 0.12,
    "avg_lead_changes": 6.5
  },
  "distribution": {
    "volatility": [0.05, 0.10, 0.15, 0.20]
  }
}
```

**Cache**: 24 hours TTL with background refresh

### Simulation

#### `GET /api/games/{game_id}/simulation`

Simulate trading strategy for a game.

**Query Parameters**:
- `entry_threshold` (float): Divergence to enter position (default: 0.05)
- `exit_threshold` (float): Divergence to exit position (default: 0.01)
- `exclude_first_seconds` (int): Exclude first N seconds (default: 0)
- `exclude_last_seconds` (int): Exclude last N seconds (default: 0)
- `bet_amount` (float): Bet amount per trade in dollars (default: 20.0)

**Response**:
```json
{
  "game_id": "401736807",
  "total_profit": 45.50,
  "total_trades": 8,
  "winning_trades": 5,
  "losing_trades": 3,
  "win_rate": 0.625,
  "trades": [
    {
      "entry_time": 120,
      "exit_time": 180,
      "entry_divergence": 0.06,
      "exit_divergence": 0.008,
      "profit": 5.20,
      "type": "long_espn"
    }
  ]
}
```

**Cache**: 1 year for completed games, 5 minutes for in-progress

### Live Data

#### `GET /api/live/games`

Get list of games currently in progress.

**Response**:
```json
{
  "games": [
    {
      "game_id": "401810151",
      "home_team": "MIN",
      "away_team": "BOS",
      "status": "in_progress",
      "current_score": "MIN 85 - BOS 82"
    }
  ]
}
```

#### `WebSocket /ws/live/{game_id}`

Real-time probability updates for a live game.

**Message Format**:
```json
{
  "type": "probability_update",
  "game_id": "401810151",
  "data": {
    "time": 1200,
    "home_prob": 0.55,
    "away_prob": 0.45
  }
}
```

### Updates

#### `GET /api/update/status`

Check if update task is running.

**Response**:
```json
{
  "is_running": false,
  "message": "No update running"
}
```

#### `POST /api/update/trigger-update`

Trigger data update (fetches new ESPN/Kalshi data).

**Response**:
```json
{
  "status": "started",
  "message": "Update task started in background"
}
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+ (3.13 works)
- PostgreSQL 16
- Docker + Docker Compose (recommended for local Postgres)

### 1. Database Setup

Start PostgreSQL via Docker:

```bash
docker compose up -d db
docker compose ps
```

This starts a Postgres 16 instance with:
- Database: `bball_warehouse`
- User: `adamvoliva`
- Password: `bball`
- Port: `5432`

### 2. Environment Configuration

Copy the example env file:

```bash
cp env.example .env
```

Edit `.env` if needed to override `DATABASE_URL`.

### 3. Python Environment

Create virtual environment and install dependencies:

```bash
cd webapp
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Database Migrations

Run migrations from the repo root:

```bash
source .env
python scripts/utils/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations
```

### 5. Start the Server

```bash
cd webapp
source ../.env  # Load DATABASE_URL
uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### 6. Access the Application

- **Web UI**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`

---

## Development

### Running in Development Mode

```bash
# Enable debug logging
DEBUG=true uvicorn api.main:app --reload --port 8000

# Skip cache preload (faster startup during development)
PRELOAD_CACHE=false uvicorn api.main:app --reload --port 8000
```

### Cache Management

**Clear cache**:
```python
from api.cache import SimpleCache
cache = SimpleCache(cache_file="get_aggregate_stats.cache")
cache.clear()
```

**Invalidate specific keys**:
```python
cache.invalidate("game_401736807_*")
```

**Cache location**: `.cache/` directory in webapp folder

### Database Connection

The app uses `psycopg` for database connections. Connection string format:

```
postgresql://user:password@host:port/database
```

Default (from `.env`):
```
postgresql://adamvoliva:bball@127.0.0.1:5432/bball_warehouse
```

### Logging

Logs are written to:
- **Console**: Standard output (with DEBUG mode for verbose logging)
- **File**: `webapp/logs/winprob_api.log` (if configured)

**Log Levels**:
- `DEBUG`: Verbose logging (enabled with `DEBUG=true`)
- `INFO`: Normal operation logs
- `WARNING`: Warnings and non-critical errors
- `ERROR`: Errors and exceptions

### Testing

```bash
# Run API tests (if available)
pytest tests/

# Test specific endpoint
curl http://localhost:8000/api/games?season=2025-26&limit=5
```

### Code Style

The codebase follows:
- **Type hints**: All functions have type annotations
- **Docstrings**: Functions include docstrings with design patterns and Big O complexity
- **Linting**: Code is linted with no errors or warnings (per project standards)

---

## Design Decisions & Patterns

### Why TradingView Lightweight Charts?

1. **Purpose-built**: Designed for financial/trading time series
2. **Performance**: Tiny bundle (~40KB), fast rendering
3. **Dark theme**: Native support matches trading terminal aesthetic
4. **No framework dependency**: Works with vanilla JavaScript
5. **Visual consistency**: Matches Kalshi/Polymarket style

### Why File-Based Cache Persistence?

1. **Development workflow**: Cache survives server reloads
2. **Fast startup**: Preloads cache on server start
3. **Simplicity**: No external dependencies (Redis, etc.)
4. **Debugging**: Cache files can be inspected manually

**Trade-offs**:
- **Pros**: Simple, no external dependencies, survives reloads
- **Cons**: Not shared across multiple server instances, file I/O overhead

### Why Separate Schemas (nba.*, espn.*, kalshi.*)?

1. **Organization**: Clear separation of data sources
2. **Maintainability**: Easier to understand data lineage
3. **Flexibility**: Can grant different permissions per schema
4. **Scalability**: Easier to move schemas to different databases if needed

**Trade-offs**:
- **Pros**: Clear organization, easier maintenance
- **Cons**: More complex joins, requires schema qualification in queries

### Why Raw Folder + Database?

1. **Reproducibility**: Full historical data available for replay
2. **Provenance**: SHA256 hashing ensures data integrity
3. **Debugging**: Raw files available for inspection
4. **Idempotency**: Avoid re-fetching identical data

**Trade-offs**:
- **Pros**: Full audit trail, data integrity, replay capability
- **Cons**: Storage overhead, requires cleanup strategy

---

## Performance Considerations

### Query Optimization

- **Indexes**: All foreign keys and common query fields are indexed
- **Materialized views**: Expensive aggregations pre-computed
- **Pagination**: Large result sets paginated to limit memory usage

### Caching Strategy

- **Completed games**: 24+ hour TTL (data doesn't change)
- **In-progress games**: 5 minute TTL (data updates frequently)
- **Aggregate stats**: 24 hour TTL with background refresh

### Database Connection Pooling

- Connections managed via `psycopg` connection pool
- Context managers ensure proper cleanup
- Connection reuse reduces overhead

---

## Troubleshooting

### Cache Not Updating

- Check cache TTL settings
- Verify data version checking is working
- Manually clear cache if needed

### Database Connection Errors

- Verify `DATABASE_URL` is set correctly
- Check PostgreSQL is running: `docker compose ps`
- Test connection: `./scripts/psql.sh`

### Missing Data

- Check raw folder for fetched files
- Verify ingestion runs completed successfully
- Check `ingestion_runs` table for errors

### WebSocket Not Connecting

- Verify WebSocket manager is initialized
- Check browser console for connection errors
- Ensure server supports WebSocket (not all hosting providers do)

---

## Future Enhancements

Potential improvements:

1. **Redis Cache**: Replace file-based cache for multi-instance deployments
2. **GraphQL API**: More flexible querying for complex data needs
3. **Real-time Alerts**: Notify users of trading opportunities
4. **Advanced Analytics**: Machine learning models for probability prediction
5. **Mobile App**: Native mobile client for live game monitoring

---

## License

[Add license information here]

---

## Contributing

[Add contribution guidelines here]
