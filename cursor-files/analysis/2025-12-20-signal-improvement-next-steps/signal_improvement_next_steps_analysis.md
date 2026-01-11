# Signal Improvement: Next Steps Analysis

**Date**: 2025-12-30  
**Purpose**: Document what we've learned, what we haven't addressed, and the path forward for signal improvement  
**Status**: Planning Phase

---

## Executive Summary

**What We've Learned:**
- ✅ Grid search confirms: **Fewer trades = better** (due to fees)
- ✅ Higher entry thresholds (more selective) reduce fee drag
- ✅ Current ESPN signal has some edge, but fees eat profits

**What We Haven't Addressed:**
- ⚠️ **Signal quality improvement** - Still using raw ESPN probabilities
- ⚠️ **Multiple comparisons correction** - Statistical validation pending
- ⚠️ **Market microstructure data** - Need better alignment of Kalshi bid/ask/spread with ESPN timestamps

**Next Steps (From Data Scientist):**
1. **Improve the actual signal** (not just thresholds) - Start with "truth model" (predict outcomes), then "edge model" (predict trading value)
2. **Store market prices + line history** - Kalshi market microstructure (bid/ask/spread) + external sportsbook odds (future)
3. **Model options**: Autoregressive model, interaction terms, or CatBoost
4. **Build canonical snapshot dataset** - Single source of truth for all modeling + simulation

---

## Part 1: What We've Learned from Grid Search

### Finding 1: Fewer Trades = Better (Due to Fees)

**Evidence:**
- Grid search tests entry thresholds from 2% to 10%
- Higher entry thresholds = fewer trades = less fee drag
- Tradeoff scatter plots show frequency vs. profitability relationship

**Implication:**
- Being more selective (higher entry threshold) helps overcome fee costs
- Current strategy needs refinement, not just threshold tuning

**What This Means:**
- ✅ **Threshold optimization is working** - We can systematically find better entry/exit points
- ⚠️ **But signal quality is the bottleneck** - Even optimal thresholds struggle with fees

---

## Part 2: What We Haven't Addressed (From Previous Analysis)

### Issue 1: Signal Refinement (Improving ESPN Model)

**Status**: ⚠️ **NOT ADDRESSED** - Identified as separate long-term project

**Signal Improvement Objective:**

We have two distinct objectives, tackled in sequence:

**Objective 1: Truth Model (First Priority)**
- **Goal**: Predict realized outcome probability accurately
- **Optimize**: Logloss, Brier score, calibration (ECE)
- **Why First**: Easier to validate and debug (ground truth = actual game outcomes)
- **Success Criteria**: Lower logloss/Brier, better calibration curve

**Objective 2: Edge Model (Later)**
- **Goal**: Predict (true_prob − market_prob) / expected value for trading
- **Optimize**: Trading metrics (net profit, Sharpe ratio) after applying trading policy
- **Why Later**: Requires truth model as foundation, plus trading policy assumptions
- **Success Criteria**: Higher net profit, better risk-adjusted returns

**Current State:**
- Use raw ESPN probabilities directly from `espn.probabilities_raw_items`
- No calibration, no feature engineering, no model improvement
- Grid search finds best thresholds for whatever signal we have (even if imperfect)

**What's Missing:**
- **Calibration**: ESPN probabilities may be miscalibrated (overconfident/underconfident)
- **Feature Engineering**: No use of game state (score diff, time remaining, etc.)
- **Model Improvement**: No autoregressive components, no interaction terms
- **Alternative Models**: No CatBoost or other ML approaches

**Why It Matters:**
- Even with optimal thresholds, poor signal quality limits profitability
- Better signal = better divergence detection = more profitable trades
- We start with Objective 1 (truth model) because it's easier to validate and debug

---

### Issue 2: Multiple Comparisons Correction

**Status**: ⚠️ **NOT ADDRESSED** - Deferred to focus on pattern detection first

**What We Currently Do:**
- Pattern detection identifies regions/trends (less prone to false positives)
- No statistical tests with FDR/Bonferroni correction

**What's Missing:**
- Statistical validation of "best" parameters
- False discovery rate control when testing many combinations
- Confidence intervals on performance metrics

**Why It Matters:**
- Testing 99+ combinations increases chance of false positives
- Need statistical rigor to validate findings

**Note**: Pattern detection (regions vs. single points) is less prone to false positives, but statistical validation would strengthen conclusions.

---

## Part 3: Data Scientist's New Guidance

### Guidance Summary

> "ok so we've learned that we want fewer trades which is good bc of less fees. next step is prob working on the actual signal. idk how we want to improve the signal, we can do autoregressive model, add some interaction terms like score_diff/sqrt(time_remaining), or switching to catboost. catboost will need to be platt scaled. we also need to store odds data, not just probabilities or trade data."

**Key Points:**
1. ✅ **Fewer trades confirmed** - Grid search validated this
2. 🎯 **Next step: Improve signal** - Not just thresholds
3. 🤔 **Options to consider**:
   - Autoregressive model
   - Interaction terms (e.g., `score_diff/sqrt(time_remaining)`)
   - CatBoost (with Platt scaling)
4. 📊 **Data requirement**: Store odds data (not just probabilities)

---

## Part 4: Current Data State vs. Requirements

### What We Currently Store

#### ESPN Data (`espn.probabilities_raw_items`)

**Current Schema:**
```sql
CREATE TABLE espn.probabilities_raw_items (
  season_label           TEXT NOT NULL,
  game_id                TEXT NOT NULL,
  event_id               BIGINT,
  sequence_number        INTEGER,
  last_modified_utc      TIMESTAMPTZ,
  home_win_percentage    DOUBLE PRECISION,  -- 0-100 format
  away_win_percentage    DOUBLE PRECISION,  -- 0-100 format
  tie_percentage         DOUBLE PRECISION,
  spread_cover_prob_home DOUBLE PRECISION,
  spread_push_prob       DOUBLE PRECISION,
  total_over_prob        DOUBLE PRECISION,
  play_ref               TEXT,
  home_team_ref          TEXT,
  away_team_ref          TEXT,
  competition_ref        TEXT,
  source_ref             TEXT,
  raw_item               JSONB NOT NULL,  -- Full JSON payload
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (season_label, game_id, sequence_number, event_id)
);
```

**What We Have:**
- ✅ Probabilities (home_win_percentage, away_win_percentage)
- ✅ Timestamps (last_modified_utc)
- ✅ Raw JSONB (full payload preserved)
- ✅ Spread/total probabilities (spread_cover_prob_home, total_over_prob)

**What We're Missing:**
- ❌ **Market microstructure** (bid/ask/spread aligned with ESPN timestamps - partially available but not aligned)
- ❌ **Feature engineering** (interaction terms, derived features)

---

#### Game State Data

**What We Have:**
- ✅ `espn.prob_event_state`: **Per-snapshot game state aligned with probabilities**
  - `home_score`, `away_score` (per snapshot, not just final)
  - `point_differential` (home_score - away_score)
  - `time_remaining` (seconds remaining in game)
  - `home_win_percentage`, `away_win_percentage` (probabilities)
  - `last_modified_utc` (timestamp)
- ✅ `espn.scoreboard_games`: Final scores, game metadata
- ✅ `derived.pbp_event_state`: Play-by-play event state

**What We're Missing:**
- ❌ **Using aligned game state** - Simulation doesn't use `prob_event_state` per-snapshot scores (only uses final scores)
- ❌ **Real-time features** - No `score_diff/sqrt(time_remaining)` calculated (data exists, just need to calculate)
- ❌ **Historical features** - No autoregressive features (lagged probabilities)

---

#### Kalshi Data

**What We Have:**
- `kalshi.candlesticks`: OHLC data (price_close, yes_bid_close, yes_ask_close)
- `kalshi.trades`: Trade execution data
- `kalshi.markets_with_games`: Market metadata

**What We Have:**
- ✅ Prices (can derive probabilities from prices)
- ✅ Bid/ask spreads
- ✅ Trade execution data

**What We're Missing:**
- ⚠️ **Market microstructure alignment** - Bid/ask/spread exist but not always aligned with ESPN probability timestamps
- ❌ **External sportsbook odds** - Only Kalshi, no other sportsbooks (separate data source)

---

### What We Need to Store (Per Data Scientist)

#### 1. Store Market Prices + Line History (Multi-Source)

**Clarification: What "Odds Data" Actually Means:**

**Kalshi Market Data (Prediction Market, NOT Sportsbook Odds):**
- Kalshi is a **prediction market**, not a sportsbook
- Kalshi prices (0-100 cents) are **prediction market prices**, not sportsbook odds
- **DO NOT convert Kalshi prices to odds format** - that would be misleading (Kalshi ≠ sportsbook)
- The **new information** worth storing from Kalshi is **market microstructure**:
  - Bid, ask, mid, spread (already partially available in `kalshi.candlesticks`)
  - Volume (trade count, liquidity)
  - Open interest (when available from Kalshi API)
  - Timestamp alignment with ESPN probabilities
- Kalshi provides a different signal (crowd-sourced prediction market) vs. sportsbook odds (bookmaker lines)

**External Sportsbook Line History (New Data Source - What We Actually Want):**
- We want **true sportsbook odds** from traditional sportsbooks (FanDuel, DraftKings, BetMGM, etc.)
- These are **different from Kalshi** - sportsbooks set lines and odds, prediction markets trade contracts
- Sportsbook odds provide:
  - Line movements over time (opening lines, closing lines, in-game movements)
  - Multiple book comparison (arbitrage opportunities, line shopping)
  - Standardized markets (moneyline, spread, total) across multiple books
- This requires adding external sportsbook data sources (separate from ESPN/Kalshi)

**Current State:**
- We store ESPN **probabilities** (0-100% format)
- We store Kalshi **prices** (0-100 cents format) - these are already implied probabilities
- We partially store **market microstructure** (bid/ask in candlesticks, but not always aligned)

**What to Store:**

**Kalshi Market Microstructure (Enhance Existing):**
- Ensure bid/ask/spread are aligned with ESPN probability timestamps
- Add volume metrics (if not already captured)
- Store mid-price calculation: `(bid + ask) / 2` for reference

**External Sportsbook Odds (New Data Source - Future):**
- We want **actual sportsbook odds** from traditional sportsbooks (FanDuel, DraftKings, etc.)
- **DO NOT** derive odds from Kalshi data - Kalshi is a prediction market, not a sportsbook
- If ESPN API provides sportsbook odds, inspect `raw_item` JSONB and scoreboard endpoints
- If not available, add external sportsbook APIs (The Odds API, The Rundown, etc.) - see Section 1.5 for options

**Storage Requirements:**
- **Kalshi**: Enhance `kalshi.candlesticks` alignment with ESPN timestamps
- **ESPN**: Inspect raw JSONB for odds fields (if present)
- **External**: Separate table `external.odds_line_history` (future work)

---

#### 1.5. Real Sportsbook Odds Data: Where to Get It (Free Options Only)

**Critical Constraints**: 
- **Paid APIs are NOT an option** - only free options will be considered
- We want **sportsbook odds** from traditional sportsbooks (FanDuel, DraftKings, BetMGM, etc.), NOT odds derived from Kalshi. Kalshi is a prediction market, not a sportsbook. Converting Kalshi prices to odds format would be misleading and does not provide true sportsbook line history.

**Blunt Summary:**

For **2025-26 in-season line history**, there is effectively **no truly-free, unlimited, reliable API** for sportsbook odds. "Free tier" APIs usually have credits/request caps (not free for our data volume needs) and are therefore excluded. For **past seasons**, there ARE free downloadable datasets (Kaggle/GitHub), but they're typically (a) closing lines only or (b) limited time coverage and (c) often not per-minute movement.

**Decision Framework**: Since paid APIs are NOT an option, our choices are limited to:
1. Free historical datasets (Kaggle/GitHub) - good for backtesting/research
2. Free scraping-based datasets (GitHub) - ToS/legal risk concerns
3. Defer - focus on ESPN/Kalshi signal improvement first

**A) TRULY FREE (Downloadable Datasets; Best for Backfill/Research)**

#### A1. Kaggle Datasets (Recommended for Initial Implementation)

**Dataset 1: "NBA Historical Stats and Betting Data"**
- **Access**: Search Kaggle for "NBA Historical Stats and Betting Data"
- **Format**: CSV files
- **Coverage**: Historical games with moneyline odds
- **Fields Expected**: Game date, teams, moneyline odds (may include spread/total)
- **Use Case**: Backtesting baseline, proof of concept for ingestion pipeline
- **Implementation Steps**:
  1. Download dataset from Kaggle (requires free Kaggle account)
  2. Inspect CSV structure (columns, data types, date formats)
  3. Map team names to ESPN team abbreviations (normalization required)
  4. Map game dates/times to ESPN game_ids (may require fuzzy matching)
  5. Load into `external.sportsbook_odds_snapshots` table

**Dataset 2: "NBA Odds Data"**
- **Access**: Search Kaggle for "NBA Odds Data"
- **Format**: CSV files
- **Coverage**: Moneyline/spreads/totals for 2008-2023 seasons
- **Fields Expected**: Date, teams, moneyline odds, spread, total, multiple sportsbooks
- **Use Case**: More comprehensive than Dataset 1, includes multiple markets
- **Implementation Steps**:
  1. Download dataset from Kaggle
  2. Inspect structure (verify multiple sportsbooks, markets)
  3. Build team name normalization mapping (CSV → ESPN abbreviations)
  4. Build game_id mapping logic (date + teams → ESPN game_id)
  5. Parse multiple sportsbooks into normalized schema
  6. Load into database with proper bookmaker attribution

**Dataset 3: "NBA Odds and Scores"**
- **Access**: Search Kaggle for "NBA Odds and Scores"
- **Format**: CSV files
- **Coverage**: Multiple sportsbooks + major markets
- **Fields Expected**: Multiple bookmakers, moneyline/spread/total markets
- **Use Case**: Verify coverage and data quality before committing
- **Implementation Steps**:
  1. Download and inspect sample (first 100 rows)
  2. Verify sportsbook coverage (FanDuel, DraftKings, BetMGM, etc.)
  3. Verify market coverage (moneyline, spread, total)
  4. Check timestamp coverage (closing lines only vs. line movement)
  5. If suitable, proceed with full ingestion

**Dataset 4: "NBA Betting Data | October 2007 to June 2024"**
- **Access**: Search Kaggle for "NBA Betting Data"
- **Format**: CSV files
- **Coverage**: Broad coverage (2007-2024), may have dataset-specific gaps
- **Fields Expected**: Historical odds across multiple seasons
- **Use Case**: Long-term historical analysis, backtesting
- **Implementation Steps**:
  1. Download dataset
  2. Verify date range coverage
  3. Identify gaps (missing seasons, teams, or dates)
  4. Document gaps for future reference
  5. Load into database with gap markers

**Kaggle Implementation Details:**

**Prerequisites:**
- Free Kaggle account (sign up at kaggle.com)
- Kaggle API credentials (download `kaggle.json` from account settings)
- Python package: `kaggle` (`pip install kaggle`)

**Download Process:**
```bash
# Set up Kaggle API
export KAGGLE_USERNAME=your_username
export KAGGLE_KEY=your_api_key
# Or place kaggle.json in ~/.kaggle/

# Download dataset
kaggle datasets download -d dataset-name -p data/raw/kaggle/

# Extract CSV files
unzip data/raw/kaggle/dataset-name.zip -d data/raw/kaggle/nba_odds/
```

**Data Quality Checks:**
- Verify date formats (YYYY-MM-DD vs MM/DD/YYYY)
- Check team name variations (e.g., "Lakers" vs "Los Angeles Lakers" vs "LAL")
- Verify odds formats (American vs decimal vs fractional)
- Check for missing values (NULL handling)
- Verify sportsbook names (normalization needed)

**Team Name Mapping Challenge:**
- Kaggle datasets use various team name formats
- ESPN uses abbreviations (LAL, BOS, etc.)
- Need robust mapping: full name → abbreviation, city → abbreviation, etc.
- Consider fuzzy matching for edge cases

#### A2. GitHub Scraper Repositories (Use with Caution)

**Repository: sportsbookreview-scraper**
- **Access**: Search GitHub for "sportsbookreview scraper" or "sportsbook scraper NBA"
- **Format**: CSV/JSON files, may include scraper code
- **Coverage**: Claims "complete 10Y games+odds data"
- **Fields Expected**: Historical odds data, may include line movement
- **WARNING**: 
  - Data provenance/accuracy varies (not officially maintained)
  - Scraping-based sources can be **ToS/legal risk** for production use
  - Good for research only unless we confirm usage rights
  - May violate sportsbook terms of service
- **Implementation Steps** (Research Only):
  1. Clone repository: `git clone https://github.com/username/sportsbookreview-scraper`
  2. Inspect data files (CSV/JSON structure)
  3. Verify data quality (spot-check against known games)
  4. Review repository license and ToS compliance
  5. **Decision Gate**: Only proceed if legal/ToS concerns resolved
  6. If approved, follow similar ingestion process as Kaggle datasets

**GitHub Implementation Details:**

**Finding Repositories:**
- Search GitHub: "NBA odds scraper", "sportsbook scraper", "betting odds scraper"
- Check repository stars, forks, last updated date (indicates maintenance)
- Review README for data coverage and format
- Check license (MIT, Apache, etc. - some may restrict commercial use)

**Data Quality Assessment:**
- Download sample data (if available)
- Spot-check against known games (verify accuracy)
- Check data completeness (missing games, dates, sportsbooks)
- Verify timestamp accuracy (if line movement data exists)

**Legal/ToS Review:**
- Review repository license
- Review sportsbook terms of service (if scraper targets specific books)
- Document legal concerns
- **Recommendation**: Treat as research-only unless legal clearance obtained

**B) "FREE" BUT NOT FREE FOR OUR NEEDS (Credits/Limits; Explicitly Disqualified)**

- **The Odds API**
  - Free plan is **credits-based**; historical odds access is shown as **paid**
  - Not suitable for full-season high-frequency collection
  - Note: Can still be useful if we decide to pay or for tiny prototypes, but does not satisfy "free"
  
- **API-SPORTS**
  - Advertises free plan and many endpoints, but must verify what odds history is truly accessible and at what limits
  - Treat as "likely limited; not free at our scale"
  
- **Any similar "free plan" odds providers that cap requests**
  - Should be listed here as "not free at our scale"

**C) PAID/COMMERCIAL (NOT AN OPTION - Excluded from Consideration)**

**Note**: Paid APIs are explicitly excluded from consideration. This section is included for completeness/reference only.

- **The Rundown**
  - Historical access marketed as part of paid plans
  - **NOT AN OPTION** - Paid APIs excluded
  
- **balldontlie betting odds**
  - Betting odds are not in the free tier (paid tier)
  - **NOT AN OPTION** - Paid APIs excluded
  
- **Most legit per-minute/per-snapshot line-history feeds are paid**
  - **NOT AN OPTION** - Paid APIs excluded

**What We Actually Need:**

**Important Distinction**: We want **sportsbook odds** (from FanDuel, DraftKings, etc.), NOT odds derived from Kalshi data. Kalshi is a prediction market, not a sportsbook. Converting Kalshi prices to odds format would be misleading and not provide true sportsbook line history.

Required fields: `event_id`/`game_id` mapping, `bookmaker` (FanDuel, DraftKings, BetMGM, etc.), `market` (moneyline/spread/total), `odds`/`line`, `timestamp`, and ideally `open`/`close` + updates through the day. American/decimal conversion is display; the value is line movement + source diversity from actual sportsbooks.

**Recommended Approach (Free Options Only - Paid APIs NOT an Option):**

- **For immediate experimentation**: Use free historical datasets (Kaggle/GitHub) to build ingestion + mapping + modeling evaluation pipelines
  
- **For 2025-26**: Explicitly, the only practical FREE choices are:
  - **(a)** Use Kaggle historical datasets (free, but closing lines only, limited coverage), OR
  - **(b)** Use GitHub scraper datasets (free, but ToS/legal risk, data provenance concerns), OR
  - **(c)** Defer (focus on ESPN/Kalshi signal improvement first, add external odds later if needed)
  
- **Clear statement**: "Paid APIs are NOT an option. For 2025-26, if we need external sportsbook odds, the only free option is scraping-based datasets, which we should treat as risky (ToS/legal concerns). Alternatively, we can defer and focus on ESPN/Kalshi signal improvement first."

**Implementation Schema:**

**Database Tables (Required for Ingestion):**

```sql
-- Game metadata mapping (Kaggle/ESPN team name normalization)
CREATE TABLE external.sportsbook_odds_games (
  kaggle_game_id        TEXT,  -- Dataset-specific game identifier
  espn_game_id          TEXT REFERENCES espn.scoreboard_games(event_id),
  game_date             DATE NOT NULL,
  home_team_kaggle      TEXT,  -- Team name as it appears in Kaggle dataset
  away_team_kaggle      TEXT,
  home_team_espn        TEXT,  -- ESPN abbreviation (LAL, BOS, etc.)
  away_team_espn        TEXT,
  mapping_confidence    TEXT,  -- 'exact', 'fuzzy', 'manual' - for validation
  source_dataset        TEXT NOT NULL,  -- 'kaggle_nba_odds_data', etc.
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (kaggle_game_id, source_dataset)
);

CREATE INDEX idx_sportsbook_odds_games_espn ON external.sportsbook_odds_games(espn_game_id);
CREATE INDEX idx_sportsbook_odds_games_date ON external.sportsbook_odds_games(game_date);

-- Timestamped odds snapshots
CREATE TABLE external.sportsbook_odds_snapshots (
  snapshot_id           BIGSERIAL PRIMARY KEY,
  espn_game_id          TEXT REFERENCES espn.scoreboard_games(event_id),
  bookmaker             TEXT NOT NULL,  -- 'fanduel', 'draftkings', 'betmgm', etc.
  market_type           TEXT NOT NULL,  -- 'moneyline', 'spread', 'total'
  side                  TEXT,  -- 'home', 'away', 'over', 'under'
  line_value            NUMERIC,  -- Spread or total (NULL for moneyline)
  odds_american         INTEGER,  -- American odds (e.g., -110, +150)
  odds_decimal          NUMERIC,  -- Decimal odds (e.g., 1.91, 2.50)
  implied_prob          NUMERIC,  -- Calculated: 1 / odds_decimal (for favorite)
  snapshot_timestamp    TIMESTAMPTZ,  -- When odds were recorded (NULL if closing line only)
  is_closing_line       BOOLEAN DEFAULT FALSE,  -- True if this is closing line
  source_dataset        TEXT NOT NULL,  -- 'kaggle_nba_odds_data', etc.
  raw_data              JSONB,  -- Original row data for reprocessing
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (espn_game_id, bookmaker, market_type, side, snapshot_timestamp, source_dataset)
);

CREATE INDEX idx_sportsbook_odds_snapshots_game ON external.sportsbook_odds_snapshots(espn_game_id, snapshot_timestamp);
CREATE INDEX idx_sportsbook_odds_snapshots_book ON external.sportsbook_odds_snapshots(bookmaker, market_type);

-- Source/provider metadata
CREATE TABLE external.sportsbook_odds_sources (
  source_id             SERIAL PRIMARY KEY,
  source_name           TEXT NOT NULL UNIQUE,  -- 'kaggle_nba_odds_data', 'github_sportsbookreview_scraper'
  source_type           TEXT NOT NULL,  -- 'kaggle', 'github', 'scraper'
  dataset_url           TEXT,  -- Kaggle dataset URL or GitHub repo URL
  coverage_start_date   DATE,
  coverage_end_date     DATE,
  markets_available     TEXT[],  -- ['moneyline', 'spread', 'total']
  sportsbooks_available TEXT[],  -- ['fanduel', 'draftkings', 'betmgm', ...]
  data_quality_notes    TEXT,  -- Gaps, issues, known problems
  legal_notes           TEXT,  -- ToS concerns, usage restrictions
  last_updated          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Ingestion Script Structure:**

```python
# scripts/load_kaggle_odds.py
"""
Load Kaggle NBA odds dataset into PostgreSQL.

Design Pattern: ETL Pattern (Extract, Transform, Load)
Algorithm: CSV parsing → team name normalization → game_id mapping → database insert
Big O: O(n) where n = number of odds records
"""

# Key functions:
# 1. load_kaggle_csv(csv_path) -> pandas.DataFrame
# 2. normalize_team_names(df) -> DataFrame with espn_abbrev columns
# 3. map_to_espn_game_ids(df) -> DataFrame with espn_game_id
# 4. parse_odds_formats(df) -> normalized odds (american, decimal, implied_prob)
# 5. insert_into_database(df) -> write to external.sportsbook_odds_snapshots
```

**Team Name Normalization Logic:**

```python
# Mapping dictionary for common variations
TEAM_NAME_MAPPING = {
    # Lakers variations
    "Los Angeles Lakers": "LAL",
    "L.A. Lakers": "LAL",
    "Lakers": "LAL",
    # Celtics variations
    "Boston Celtics": "BOS",
    "Celtics": "BOS",
    # ... etc for all 30 teams
}

# Fuzzy matching fallback (if exact match fails)
from fuzzywuzzy import fuzz

def normalize_team_name(name: str) -> str | None:
    # Try exact match first
    if name in TEAM_NAME_MAPPING:
        return TEAM_NAME_MAPPING[name]
    # Try fuzzy match
    best_match = None
    best_score = 0
    for kaggle_name, espn_abbr in TEAM_NAME_MAPPING.items():
        score = fuzz.ratio(name.lower(), kaggle_name.lower())
        if score > best_score and score >= 80:  # 80% similarity threshold
            best_match = espn_abbr
            best_score = score
    return best_match
```

**Game ID Mapping Logic:**

```python
def map_to_espn_game_id(
    conn: psycopg.Connection,
    game_date: date,
    home_team_espn: str,
    away_team_espn: str,
) -> str | None:
    """
    Map Kaggle game (date + teams) to ESPN game_id.
    
    Uses fuzzy date matching (±1 day) to handle timezone differences.
    """
    sql = """
    SELECT event_id
    FROM espn.scoreboard_games
    WHERE DATE(event_date) BETWEEN %s - INTERVAL '1 day' AND %s + INTERVAL '1 day'
      AND home_team_abbrev = %s
      AND away_team_abbrev = %s
    LIMIT 1
    """
    row = conn.execute(sql, (game_date, game_date, home_team_espn, away_team_espn)).fetchone()
    return row[0] if row else None
```

**Odds Format Conversion:**

```python
def parse_american_odds(american: int | str) -> tuple[float, float]:
    """
    Convert American odds to decimal and implied probability.
    
    Returns: (decimal_odds, implied_probability)
    """
    am = int(american)
    if am > 0:
        decimal = (am / 100) + 1
    else:
        decimal = (100 / abs(am)) + 1
    implied_prob = 1 / decimal
    return decimal, implied_prob

def parse_decimal_odds(decimal: float) -> tuple[int, float]:
    """
    Convert decimal odds to American and implied probability.
    
    Returns: (american_odds, implied_probability)
    """
    if decimal >= 2.0:
        american = int((decimal - 1) * 100)
    else:
        american = int(-100 / (decimal - 1))
    implied_prob = 1 / decimal
    return american, implied_prob
```

**Evaluation Criteria for Dataset Selection:**

1. **Coverage**:
   - Date range (seasons covered)
   - Number of games (complete seasons or gaps?)
   - Sportsbook coverage (how many books? which ones?)
   - Market coverage (moneyline only? spread? total?)

2. **Data Quality**:
   - Team name consistency (easy to normalize?)
   - Date format consistency
   - Odds format consistency (American? decimal? both?)
   - Missing value rate
   - Duplicate detection

3. **Line Movement**:
   - Closing lines only? (most common)
   - Opening lines included?
   - Per-minute/per-hour updates? (rare in free datasets)

4. **Legal/ToS**:
   - License type (CC0, MIT, etc.)
   - Usage restrictions
   - Commercial use allowed?
   - ToS compliance (if scraper-based)

**Recommended Implementation Order:**

1. **Start with Kaggle Dataset 2 ("NBA Odds Data")** - Most comprehensive, includes multiple markets
2. **Build ingestion pipeline** - Team normalization, game_id mapping, odds parsing
3. **Validate on sample** - Test on 10-20 games, verify mapping accuracy
4. **Full ingestion** - Load complete dataset
5. **Evaluate signal value** - Does external odds improve model performance?
6. **If valuable, expand** - Add other Kaggle datasets or GitHub scrapers (with legal review)

---

#### 2. Game State Features (For Interaction Terms)

**Current State:**
- Game state exists in `derived.pbp_event_state` but not aligned with probabilities
- No real-time features calculated per probability snapshot

**What We Need:**
- **Aligned game state** per probability timestamp:
  - `score_diff` (home_score - away_score)
  - `time_remaining` (seconds remaining in regulation)
  - `time_elapsed` (seconds since game start)
  - `quarter` (Q1, Q2, Q3, Q4)
- **Interaction terms**:
  - `score_diff / sqrt(time_remaining)` (as suggested)
  - `score_diff * time_remaining`
  - Other combinations

**Storage Options:**
- **Option A**: Extend `espn.probabilities_raw_items` with game state columns
- **Option B**: Create `espn.probabilities_with_state` view/table
- **Option C**: Calculate on-the-fly during model training

**Recommendation**: Option B (separate table/view) to avoid modifying raw data

---

#### 3. Historical Features (For Autoregressive Model)

**Current State:**
- We store probability time series, but don't extract lagged features
- No autoregressive features (previous probabilities, trends, etc.)

**What We Need:**
- **Lagged probabilities**:
  - `home_win_pct_lag_1` (previous snapshot)
  - `home_win_pct_lag_5` (5 snapshots ago)
  - `home_win_pct_lag_10` (10 snapshots ago)
- **Trend features**:
  - `prob_change_1` (current - lag_1)
  - `prob_change_5` (current - lag_5)
  - `prob_velocity` (rate of change)
- **Rolling statistics**:
  - `prob_mean_5` (5-snapshot rolling mean)
  - `prob_std_5` (5-snapshot rolling std)

**Storage Options:**
- **Option A**: Calculate during feature engineering (not stored)
- **Option B**: Pre-compute and store in feature table
- **Recommendation**: Option A (calculate on-the-fly) - too many combinations to store

---

## Part 5: Signal Improvement Options

### Option 1: Autoregressive Model

**Concept:**
- Use historical probabilities to predict current probability
- Model: `P(t) = f(P(t-1), P(t-2), ..., game_state(t))`
- Captures momentum, mean reversion, trends

**Implementation:**
- **Features**: Lagged probabilities (1, 5, 10 snapshots)
- **Model**: ARIMA, LSTM, or simple linear regression
- **Output**: Calibrated probability prediction

**Pros:**
- Captures temporal patterns
- Relatively simple to implement
- Interpretable

**Cons:**
- Requires aligned time series (may have gaps)
- May overfit to ESPN's own patterns (not market inefficiency)

**Data Requirements:**
- ✅ Probability time series (we have)
- ⚠️ Aligned timestamps (we have, but may need interpolation)
- ❌ Lagged features (need to calculate)

---

### Option 2: Interaction Terms

**Concept:**
- Add game state features that interact with probabilities
- Example: `score_diff / sqrt(time_remaining)` affects probability updates
- Model: `P(t) = f(espn_prob(t), score_diff(t), time_remaining(t), interactions)`

**Implementation:**
- **Features**:
  - `score_diff / sqrt(time_remaining)` (as suggested)
  - `score_diff * time_remaining`
  - `espn_prob * score_diff`
  - Other combinations
- **Model**: Linear regression with interaction terms, or tree-based (CatBoost)

**Pros:**
- Captures game context (clutch situations, blowouts)
- Interpretable (can see which interactions matter)
- Relatively simple

**Cons:**
- Requires aligned game state (not currently available)
- Need domain knowledge to pick good interactions

**Data Requirements:**
- ✅ Probabilities (we have)
- ❌ Game state aligned with probabilities (need to build)
- ❌ Interaction terms (need to calculate)

---

### Option 3: CatBoost (With Score Calibration)

**Concept:**
- Use gradient boosting (CatBoost) to predict probabilities
- Features: ESPN prob, game state, interactions, lagged features
- Output: Raw probability (0-1)
- **Score Calibration**: Calibrate output to match true probabilities

**Why CatBoost:**
- Handles categorical features well
- Good with interactions (automatic feature interactions)
- Robust to overfitting

**Why Score Calibration:**
- ML models often produce uncalibrated probabilities
- **Platt Scaling**: Fit a logistic regression calibration model on model scores (or logits/margins) on a validation set
- **Isotonic Regression**: Consider as a non-parametric calibration alternative
- Choose based on validation calibration curves (which method produces better ECE/reliability)

**Implementation:**
- **Features**: ESPN prob, game state, interactions, lagged features
- **Model**: CatBoost regressor/classifier
- **Calibration**: Platt scaling on validation set
- **Output**: Calibrated probability

**Pros:**
- Powerful (can capture complex patterns)
- Automatic feature interactions
- Calibrated output

**Cons:**
- More complex (requires ML pipeline)
- Needs more data (training/validation splits)
- Less interpretable than linear models

**Data Requirements:**
- ✅ Probabilities (we have)
- ❌ Game state aligned (need to build)
- ❌ Feature engineering (need to build)
- ❌ Training labels (actual outcomes - we have)

---

## Part 6: Implementation Roadmap

### Phase 1: Data Infrastructure (Prerequisites)

**Goal**: Build canonical snapshot dataset and verify fee modeling correctness

**Prerequisites: Fee Modeling Sanity Check**

Before proceeding, verify fee modeling correctness (incorrect fees can shift optimal thresholds materially):

- [ ] **Fee Rounding**: Verify fees round UP to the next cent ($0.01 minimum when raw fee > 0)
- [ ] **Contract vs Dollars**: Verify fee uses number of contracts (or correctly converts dollars→contracts if sim uses dollars)
- [ ] **Maker vs Taker**: Confirm maker vs taker fee rate assumptions (if we're modeling either)
- [ ] **Fee Formula**: Validate Kalshi fee formula (7% structure) matches actual API behavior

**Tasks:**

**Next Step A: Build Canonical Snapshot Dataset (Centerpiece)**

Build a single canonical dataset view/table: `derived.snapshot_features_v1`

**Purpose**: All modeling + simulation should consume this dataset to avoid repeated joins and drifting logic.

**Schema:**
- **Keys**: `(season_label, game_id, sequence_number, snapshot_ts)` where `snapshot_ts = last_modified_utc`
- **Columns (Minimum Viable)**:
  - `espn_home_prob`, `espn_away_prob` (0-1 format)
  - `score_diff` (home_score - away_score)
  - `time_remaining` (seconds remaining in regulation)
  - `period` / `quarter` (Q1, Q2, Q3, Q4)
  - **Interaction**: `score_diff / sqrt(time_remaining + eps)` (eps to avoid division by zero)
  - **Lagged features**: `espn_home_prob_lag_1`, `espn_away_prob_lag_1`
  - **Delta features**: `espn_home_prob_delta_1` (current - lag_1)
  - **Kalshi market data** (if available): `kalshi_mid_price`, `kalshi_bid`, `kalshi_ask`, `kalshi_spread`

**Implementation:**
- [ ] Create view/table joining `espn.prob_event_state` with `kalshi.candlesticks` (aligned by timestamp)
- [ ] Calculate interaction terms and lagged features
- [ ] Handle missing values (forward-fill for lags, NULL for Kalshi if no match)
- [ ] Index on `(game_id, snapshot_ts)` for fast queries

**Estimated Effort**: 1 week

**Additional Tasks:**

1. **Store Market Prices + Line History (Multi-Source)**
   - [ ] **Kalshi Market Data**: Ensure bid/ask/spread alignment with ESPN timestamps (enhance existing `kalshi.candlesticks`)
   - [ ] **ESPN Odds Inspection**: Inspect raw JSONB in `probabilities_raw_items` and scoreboard endpoints for odds fields (if present)
   - [ ] **External Sportsbook Line History**: Defer to future (separate data source)

2. **Feature Engineering Infrastructure**
   - [ ] All features now in canonical snapshot dataset (see Next Step A)
   - [ ] No separate feature table needed (calculate in snapshot view)

**Estimated Total Effort**: 1-2 weeks

---

### Phase 2: Model Development (Choose One Path)

#### Path A: Autoregressive Model

**Tasks:**
1. **Feature Engineering**
   - [ ] Calculate lagged probabilities (1, 5, 10 snapshots)
   - [ ] Calculate trend features (prob_change, prob_velocity)
   - [ ] Handle missing data (interpolation)

2. **Model Training**
   - [ ] Split data (train/valid/test by game, not by snapshot)
   - [ ] Train ARIMA or simple autoregressive model
   - [ ] Validate on validation set

3. **Integration**
   - [ ] Replace raw ESPN probabilities with model predictions
   - [ ] Re-run grid search with improved signal
   - [ ] Compare performance

**Estimated Effort**: 2-3 weeks

---

#### Path B: Interaction Terms Model

**Tasks:**
1. **Feature Engineering**
   - [ ] Calculate `score_diff / sqrt(time_remaining)`
   - [ ] Calculate other interaction terms
   - [ ] Normalize features

2. **Model Training**
   - [ ] Train linear regression with interaction terms
   - [ ] Or train tree-based model (CatBoost) with interactions
   - [ ] Validate on validation set

3. **Integration**
   - [ ] Replace raw ESPN probabilities with model predictions
   - [ ] Re-run grid search
   - [ ] Compare performance

**Estimated Effort**: 2-3 weeks

---

#### Path C: CatBoost with Score Calibration

**Tasks:**
1. **Feature Engineering**
   - [ ] All features from canonical snapshot dataset (interactions, lags)
   - [ ] Categorical features (quarter, team, etc.)

2. **Model Training**
   - [ ] Train CatBoost regressor/classifier
   - [ ] Apply score calibration on validation set:
     - Try Platt scaling (logistic regression on logits/margins)
     - Try isotonic regression (non-parametric alternative)
     - Choose based on validation calibration curves (ECE/reliability)
   - [ ] Validate calibrated probabilities

3. **Integration**
   - [ ] Replace raw ESPN probabilities with CatBoost predictions
   - [ ] Re-run grid search
   - [ ] Compare performance

**Estimated Effort**: 3-4 weeks

---

### Phase 3: Validation & Comparison

**Tasks:**
1. **Compare Models**
   - [ ] Baseline: Raw ESPN probabilities
   - [ ] Model A: Autoregressive
   - [ ] Model B: Interaction terms
   - [ ] Model C: CatBoost + Platt scaling
   - [ ] Run grid search for each model
   - [ ] Compare net profit, trade counts, win rates

2. **Statistical Validation**
   - [ ] Add multiple comparisons correction (FDR/Bonferroni)
   - [ ] Calculate confidence intervals
   - [ ] Validate on held-out test set

3. **Production Integration**
   - [ ] Deploy best model
   - [ ] Update simulation to use improved signal
   - [ ] Monitor performance

**Estimated Effort**: 1-2 weeks

---

## Part 7: Key Decisions Needed

### Decision 1: Which Model Path?

**Options:**
- **Path A**: Autoregressive (simpler, interpretable)
- **Path B**: Interaction terms (medium complexity, interpretable)
- **Path C**: CatBoost (complex, powerful, less interpretable)

**Recommendation**: Start with **Path B** (interaction terms) because:
- Addresses data scientist's specific suggestion (`score_diff/sqrt(time_remaining)`)
- Medium complexity (not too simple, not too complex)
- Can evolve to CatBoost later if needed
- **Prerequisite**: Requires canonical snapshot dataset (Next Step A) which provides all needed features

---

### Decision 2: Store Features or Calculate On-the-Fly?

**Options:**
- **Store**: Pre-compute and store features in database
- **Calculate**: Compute features during model training/inference

**Recommendation**: **Store in canonical snapshot dataset** because:
- Single source of truth prevents repeated joins and drifting logic
- All modeling + simulation consume same features
- Can calculate features once and reuse
- Easier to debug and validate

**Implementation**: Build `derived.snapshot_features_v1` as the canonical dataset (see Phase 1, Next Step A)

---

### Decision 3: Market Data Storage Format?

**Clarification**: Kalshi prices are already implied probabilities; converting to American/decimal odds is just reformatting.

**Options:**
- **Enhance existing**: Improve alignment of `kalshi.candlesticks` with ESPN timestamps
- **Separate table**: `external.odds_line_history` for external sportsbook data (future)
- **View**: Create view that calculates odds from probabilities (if needed for display)

**Recommendation**: **Enhance existing Kalshi data alignment** because:
- Market microstructure (bid/ask/spread) is the valuable new information
- External sportsbook odds are a separate data source (defer to future)
- Odds format conversion is just display logic (not signal improvement)

---

## Part 8: Risks & Challenges

### Risk 1: Data Alignment Already Solved ✅

**Status**: `espn.prob_event_state` already has aligned game state!

**Challenge**: Simulation currently doesn't use it (only uses final scores)

**Mitigation:**
- Switch simulation to use `prob_event_state` instead of `probabilities_raw_items`
- Verify data quality (spot-check a few games)
- Handle any missing values (interpolation if needed)

---

### Risk 2: Overfitting

**Challenge**: Complex models (CatBoost) may overfit to training data

**Mitigation:**
- Use proper train/valid/test splits (by game, not by snapshot)
- Cross-validation
- Regularization (CatBoost has built-in)
- Platt scaling helps with calibration

---

### Risk 3: ESPN API May Not Provide Odds

**Challenge**: ESPN API may not provide odds data (only probabilities)

**Mitigation:**
- Inspect raw JSONB in `probabilities_raw_items` and scoreboard endpoints for odds fields (if present)
- If no odds available, focus on probability improvement only (odds are just reformatting anyway)
- External sportsbook odds are separate data source (defer to future)

---

### Risk 4: Model Complexity vs. Interpretability

**Challenge**: CatBoost is powerful but less interpretable

**Mitigation:**
- Start with simpler models (interaction terms)
- Use feature importance from CatBoost to understand what matters
- Can combine: simple model for interpretability, CatBoost for performance

---

## Part 9: Success Metrics

### Signal Metrics (Pre-Policy)

**Independent from trading threshold policy** - these measure signal quality before applying any trading rules:

- **Logloss**: Cross-entropy loss (lower is better)
- **Brier Score**: Mean squared error between predicted and actual probabilities (lower is better)
- **Calibration Curve / ECE**: Expected Calibration Error (lower is better)
- **Reliability by Buckets**:
  - By time remaining (e.g., Q1, Q2-Q3, Q4)
  - By score differential (e.g., blowout, close game)
- **Edge Capture (Optional)**: Correlation of `(p_model − p_market_mid)` with outcomes

**Purpose**: Validate that improved signal actually predicts outcomes better, independent of trading policy.

### Trading Metrics (Post-Policy)

**Dependent on trading threshold policy** - these measure trading performance after applying entry/exit rules:

- **Net Profit** (after fees) on validation/test set
- **Trade Count** (should decrease with better signal)
- **Win Rate** (should increase)
- **Sharpe Ratio**: Risk-adjusted return
- **Maximum Drawdown**: Largest peak-to-trough decline

**Secondary:**
- **Feature Importance**: Which features matter for prediction?
- **Robustness**: Performance across different game types

---

### Comparison Baseline

**Baseline**: Current grid search results with raw ESPN probabilities
- Entry threshold: ~6-8 cents (from grid search)
- Exit threshold: ~2-3 cents
- Net profit: TBD (waiting for grid search to complete)
- Trade count: TBD

**Target**: Improved signal should:
- Increase net profit (or same profit with fewer trades)
- Reduce optimal entry threshold (better signal = can enter earlier)
- Improve win rate

---

## Part 10: Next Immediate Steps

### Step 1: Build Canonical Snapshot Dataset (Priority)

**Status**: Can proceed in parallel with grid search completion

**Tasks:**
- [ ] Create `derived.snapshot_features_v1` view/table
- [ ] Join `espn.prob_event_state` with `kalshi.candlesticks` (aligned by timestamp)
- [ ] Calculate interaction terms: `score_diff / sqrt(time_remaining + eps)`
- [ ] Calculate lagged features: `espn_home_prob_lag_1`, `espn_away_prob_delta_1`
- [ ] Include Kalshi market data: `kalshi_mid_price`, `kalshi_bid`, `kalshi_ask`, `kalshi_spread` (if available)
- [ ] Index on `(game_id, snapshot_ts)` for performance
- [ ] Verify data quality (spot-check alignment on sample games)

**Timeline**: 1 week (can start immediately)

---

### Step 2: Fee Modeling Sanity Check (Prerequisite)

**Status**: Can proceed in parallel with other work

**Tasks:**
- [ ] Verify fees round UP to the next cent ($0.01 minimum when raw fee > 0)
- [ ] Verify fee uses number of contracts (or correctly converts dollars→contracts if sim uses dollars)
- [ ] Confirm maker vs taker fee rate assumptions (if we're modeling either)
- [ ] Validate Kalshi fee formula matches actual API behavior

**Timeline**: 1-2 days

---

### Step 3: Complete Current Grid Search (Baseline)

**Status**: In progress
- Let current grid search finish
- Analyze results
- Establish baseline performance metrics

**Timeline**: Ongoing (can proceed in parallel with Steps 1-2)

---

### Step 4: Quick ESPN Odds Inspection

**Status**: Can proceed in parallel

**Tasks:**
- [ ] Inspect `raw_item` JSONB in `probabilities_raw_items` for odds fields (if present)
- [ ] Check scoreboard endpoints for odds data (if available)
- [ ] Document findings (odds may not be available, which is fine)

**Timeline**: 1 day

---

### Step 5: Decide 2025-26 Odds Strategy (Decision Gate - Free Options Only)

**Status**: Can proceed in parallel with other work

**Purpose**: Make explicit decision on how to handle external sportsbook odds for 2025-26 season

**Constraint**: **Paid APIs are NOT an option** - only free options will be considered.

**Options (Free Only):**
- **(a) Use Kaggle historical datasets** (free, but closing lines only, limited coverage)
  - Pros: Free, reliable data provenance, good for backtesting
  - Cons: Closing lines only (not per-minute movement), limited coverage, historical only
- **(b) Use GitHub scraper datasets** (free, but ToS/legal risk, data provenance concerns)
  - Pros: Free, may have more complete coverage
  - Cons: ToS/legal risk, data provenance/accuracy varies, scraping may violate terms of service
- **(c) Defer** (focus on ESPN/Kalshi signal improvement first, add external odds later if needed)
  - Pros: No risk, focus on improving existing signal
  - Cons: Missing external sportsbook signal (if valuable)

**Decision Criteria:**
- Do we need external sportsbook odds for signal improvement, or can we proceed with ESPN/Kalshi only?
- What's the risk tolerance for scraping-based datasets (ToS/legal concerns)?
- Can we validate signal improvement using historical Kaggle datasets first?
- **Constraint**: Paid APIs are NOT an option - only free options considered

**Timeline**: 1 day (decision meeting)

---

### Step 6: Backfill Pipeline Using Kaggle Dataset (Proof of Concept)

**Status**: Can proceed after Step 5 decision (if we decide to pursue external odds)

**Purpose**: Build ingestion + mapping + modeling evaluation pipelines using free historical Kaggle data

**Prerequisites:**
- Kaggle account and API credentials (`kaggle.json` in `~/.kaggle/`)
- Python package: `kaggle` (`pip install kaggle`)
- Python package: `fuzzywuzzy` (`pip install fuzzywuzzy python-Levenshtein`) for team name matching

**Tasks:**

**Phase 6.1: Dataset Selection and Download**
- [ ] Research and select best Kaggle dataset (recommend "NBA Odds Data" for multiple markets)
- [ ] Download dataset using Kaggle API: `kaggle datasets download -d dataset-name -p data/raw/kaggle/`
- [ ] Extract CSV files: `unzip data/raw/kaggle/dataset-name.zip -d data/raw/kaggle/nba_odds/`
- [ ] Inspect CSV structure (columns, data types, sample rows)
- [ ] Document dataset metadata (date range, sportsbooks, markets, gaps)

**Phase 6.2: Database Schema Creation**
- [ ] Create migration: `db/migrations/XXX_external_sportsbook_odds_schema.sql`
- [ ] Create tables: `external.sportsbook_odds_games`, `external.sportsbook_odds_snapshots`, `external.sportsbook_odds_sources`
- [ ] Create indexes for performance
- [ ] Run migration: `python scripts/migrate.py --dsn "$DATABASE_URL"`
- [ ] Verify schema created correctly

**Phase 6.3: Team Name Normalization**
- [ ] Build team name mapping dictionary (Kaggle names → ESPN abbreviations)
- [ ] Handle common variations (e.g., "Los Angeles Lakers" → "LAL", "Lakers" → "LAL")
- [ ] Implement fuzzy matching fallback for edge cases
- [ ] Test on sample rows (verify mapping accuracy)
- [ ] Document mapping confidence levels

**Phase 6.4: Game ID Mapping**
- [ ] Implement `map_to_espn_game_id()` function (date + teams → ESPN game_id)
- [ ] Handle date fuzzy matching (±1 day for timezone differences)
- [ ] Test on sample games (verify mapping accuracy)
- [ ] Handle unmapped games (log for manual review)
- [ ] Calculate mapping success rate

**Phase 6.5: Odds Format Parsing**
- [ ] Implement `parse_american_odds()` (American → decimal + implied_prob)
- [ ] Implement `parse_decimal_odds()` (decimal → American + implied_prob)
- [ ] Handle both formats (detect format automatically)
- [ ] Test on sample odds (verify conversion accuracy)
- [ ] Handle edge cases (odds = 0, NULL, invalid formats)

**Phase 6.6: Ingestion Script**
- [ ] Create `scripts/load_kaggle_odds.py`
- [ ] Implement CSV reading (pandas)
- [ ] Implement team normalization pipeline
- [ ] Implement game_id mapping pipeline
- [ ] Implement odds parsing pipeline
- [ ] Implement database insert (batch inserts for performance)
- [ ] Add error handling and logging
- [ ] Add progress reporting

**Phase 6.7: Validation and Testing**
- [ ] Run ingestion on sample (first 100 rows)
- [ ] Verify data quality (spot-check 5-10 games manually)
- [ ] Verify team name mapping accuracy
- [ ] Verify game_id mapping accuracy
- [ ] Verify odds conversion accuracy
- [ ] Calculate completeness metrics (games mapped, odds parsed, etc.)
- [ ] Document data quality report

**Phase 6.8: Full Ingestion**
- [ ] Run full ingestion on complete dataset
- [ ] Monitor for errors (unmapped games, parsing failures)
- [ ] Generate ingestion report (rows processed, success rate, errors)
- [ ] Verify data completeness (compare to source dataset)

**Phase 6.9: Feature Engineering Evaluation**
- [ ] Query canonical dataset with external odds joined
- [ ] Calculate features: `(espn_prob - kalshi_mid)`, `(espn_prob - sportsbook_mid)`
- [ ] Evaluate: Does external odds data add signal?
- [ ] Compare model performance: ESPN/Kalshi vs ESPN/Kalshi/Sportsbook
- [ ] Document findings

**Timeline**: 1-2 weeks (proof of concept)

**Success Criteria:**
- [ ] Ingestion pipeline works end-to-end
- [ ] Team name mapping accuracy > 95%
- [ ] Game_id mapping accuracy > 90%
- [ ] Odds parsing accuracy > 99%
- [ ] Data quality report shows acceptable completeness
- [ ] Feature engineering evaluation shows external odds add value (or documents that they don't)

**Note**: This validates the pipeline using free historical data. If external odds prove valuable, we can consider GitHub scrapers for 2025-26 (with legal review), but paid APIs remain excluded.

---

### Step 7: Implement Interaction Terms Model (After Canonical Dataset)

**Prerequisites**: Canonical snapshot dataset complete (Step 1)

**Tasks:**
- [ ] Use canonical dataset for all features (no separate calculation needed)
- [ ] Train simple linear model or CatBoost with interaction terms
- [ ] Apply score calibration (Platt scaling or isotonic regression)
- [ ] Validate on held-out games using signal metrics (logloss, Brier, calibration)

**Timeline**: 1-2 weeks (after Step 1 complete)

---

## Conclusion

**What We've Accomplished:**
- ✅ Grid search infrastructure (systematic threshold testing)
- ✅ Pattern detection (not just "best point")
- ✅ Fee-aware simulation (realistic costs)

**What We've Learned:**
- ✅ Fewer trades = better (fees are the bottleneck)
- ✅ Higher entry thresholds help (more selective)

**What's Next:**
- 🎯 **Improve the signal** (not just thresholds) - Truth model first, then edge model
- 📊 **Store market prices + line history** - Kalshi microstructure + external sportsbook odds (future)
- 🗄️ **Build canonical snapshot dataset** - Single source of truth (`derived.snapshot_features_v1`)
- 🤖 **Model options**: Autoregressive, interaction terms, or CatBoost

**Recommendation:**
1. **Immediate (Parallel)**: 
   - Build canonical snapshot dataset (`derived.snapshot_features_v1`) - **centerpiece**
   - Fee modeling sanity check
   - Quick ESPN odds inspection
   - Decide 2025-26 odds strategy (free options only: Kaggle datasets, GitHub scrapers, or defer)
   - Let grid search finish (establishes baseline)
2. **Short-term**: 
   - Implement interaction terms model using canonical dataset (`score_diff/sqrt(time_remaining)`)
   - Backfill pipeline using Kaggle dataset (proof of concept for external odds, if pursuing)
3. **Medium-term**: Consider CatBoost if interaction terms show promise
4. **Long-term**: Add multiple comparisons correction, statistical validation

**Key Insight**: Grid search was the right first step - it validated that fees are the problem and that signal quality needs improvement. Now we move from "optimizing thresholds" to "improving the signal itself." The canonical snapshot dataset is the foundation that prevents repeated joins and ensures all downstream work uses consistent features.

