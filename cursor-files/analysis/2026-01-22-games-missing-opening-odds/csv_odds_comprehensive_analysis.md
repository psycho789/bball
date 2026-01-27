# Comprehensive CSV Opening Odds Analysis

**Date**: 2026-01-22  
**Purpose**: Validate CSV files for opening odds fields used in CatBoost training  
**Fields Required**: `opening_moneyline_home`, `opening_moneyline_away`, `opening_spread`, `opening_total`

## Executive Summary

**Files with Opening Odds Data:**
1. ✅ **nba_main_lines.csv** - DECIMAL odds format, can identify opening odds (earliest timestamp)
2. ✅ **nba_2008-2025.csv** - AMERICAN odds format, one row per game (assumed opening odds)

**Files WITHOUT Opening Odds Data:**
- ❌ advanced.csv (no relevant fields)
- ❌ nba_detailed_odds.csv (different structure, not suitable for direct mapping)
- ❌ per-game.csv (no relevant fields)
- ❌ stats.csv (no relevant fields)

### Missing Opening Odds Recovery Potential

**Overall Statistics:**
- Total games missing opening odds in DB: **1,992**
- Games with data available in CSV: **1,411 (70.8%)**
- Games missing in BOTH DB and CSV: **581 (29.2%)**

**Best Recovery Potential by Season:**
- **2017-18**: 88.9% of missing games have CSV data (169/190 games)
- **2020-21**: 78.3% of missing games have CSV data (177/226 games)
- **2022-23**: 73.3% of missing games have CSV data (178/243 games)

**Worst Recovery Potential:**
- **2025-26**: Only 42.9% have CSV data (57/133 games) - likely due to future games
- **2019-20**: 63.1% have CSV data (137/217 games)

## Detailed Analysis

### 1. nba_main_lines.csv ✅

**Location**: `data/stats-csv/nba_main_lines.csv`

**Statistics:**
- Total rows: **5,132**
- Unique games: **637**
- Games with multiple timestamps: **595** (93.4%)
- Date range: 2025-09-10 to 2026-01-12
- Seasons: 2024-2025 (50 games), 2025-2026 (5,082 games)

**Fields for CatBoost Training:**

| Field | CSV Column | Format | Populated | Percentage |
|-------|------------|--------|-----------|------------|
| opening_moneyline_home | `team1_moneyline` or `team2_moneyline`* | **DECIMAL** (e.g., 3.06, 1.392) | 5,097 rows | **99.3%** |
| opening_moneyline_away | `team1_moneyline` or `team2_moneyline`* | **DECIMAL** (e.g., 3.06, 1.392) | 5,097 rows | **99.3%** |
| opening_spread | `team1_spread` or `team2_spread`* | Line value (e.g., 6.5, -6.5) | 5,097 rows | **99.3%** |
| opening_total | `over_total` | Line value (e.g., 226.0) | 5,097 rows | **99.3%** |

*Note: Need to determine which team is home/away based on game context

**Opening Odds Identification:**
- ✅ **CAN identify opening odds** - Multiple timestamps per game
- Method: Use earliest timestamp per game (team1 + team2 + date)
- 595 out of 637 games have multiple timestamps

**Sample Data:**
```csv
team1,team2,team1_moneyline,team2_moneyline,team1_spread,team2_spread,over_total,timestamp
Houston Rockets,Oklahoma City Thunder,3.06,1.392,6.5,-6.5,226.0,2025-09-10 23:14:26
```

**Validation Commands:**
```bash
head -5 data/stats-csv/nba_main_lines.csv
wc -l data/stats-csv/nba_main_lines.csv
cut -d',' -f1,2,4,5,6,7,10,14 data/stats-csv/nba_main_lines.csv | head -10
```

---

### 2. nba_2008-2025.csv ✅

**Location**: `data/stats-csv/nba_2008-2025.csv`

**Statistics:**
- Total rows: **23,118**
- Unique games: **23,118** (one row per game)
- Date range: 2007-10-30 to 2025-06-22
- Seasons: 2007-2008 through 2024-2025 (18 seasons)

**Fields for CatBoost Training:**

| Field | CSV Column | Format | Populated | Percentage |
|-------|------------|--------|-----------|------------|
| opening_moneyline_home | `moneyline_home` | **AMERICAN** (e.g., -1400, 190) | 19,820 rows | **85.7%** |
| opening_moneyline_away | `moneyline_away` | **AMERICAN** (e.g., 900, -230) | 19,820 rows | **85.7%** |
| opening_spread | `spread` | Line value (e.g., 13, 1, 5) | 23,115 rows | **100.0%** |
| opening_total | `total` | Line value (e.g., 189.5, 212) | 23,118 rows | **100.0%** |

**Opening Odds Identification:**
- ⚠️ **Cannot identify opening odds** - Only one row per game
- Assumption: Single row per game represents opening odds (or closing odds)
- No timestamp field to distinguish opening vs closing

**Sample Data:**
```csv
season,date,away,home,moneyline_home,moneyline_away,spread,total
2008,2007-10-30,por,sa,-1400,900,13,189.5
2008,2007-10-30,utah,gs,-120,100,1,212
```

**Validation Commands:**
```bash
head -5 data/stats-csv/nba_2008-2025.csv
wc -l data/stats-csv/nba_2008-2025.csv
cut -d',' -f1,2,5,6,20,21,22,23 data/stats-csv/nba_2008-2025.csv | head -10
```

**Games per Season:**
- 2007-2008: 1,316 games
- 2008-2009: 1,315 games
- 2009-2010: 1,312 games
- 2010-2011: 1,311 games
- 2011-2012: 1,074 games
- 2012-2013: 1,314 games
- 2013-2014: 1,319 games
- 2014-2015: 1,311 games
- 2015-2016: 1,316 games
- 2016-2017: 1,309 games
- 2017-2018: 1,312 games
- 2018-2019: 1,312 games
- 2019-2020: 1,138 games
- 2020-2021: 1,176 games
- 2021-2022: 1,323 games
- 2022-2023: 1,320 games
- 2023-2024: 1,319 games
- 2024-2025: 1,321 games

---

### 3. nba_detailed_odds.csv ⚠️

**Location**: `data/stats-csv/nba_detailed_odds.csv`

**Statistics:**
- Total rows: **95,602**
- Columns: Market, Selection, Odds, matchup, timestamp
- Date range: 2025-09-10 to 2026-01-12
- Seasons: 2024-2025, 2025-2026

**Structure:**
- Different structure - one row per market/selection combination
- Contains moneyline, spread, and total markets but in separate rows
- Would require pivoting/aggregation to match training format
- **NOT directly usable** for CatBoost training without significant transformation

**Sample Data:**
```csv
Market,Selection,Odds,matchup,timestamp
Money Line – Game,Houston Rockets,3.06,Houston Rockets vs Oklahoma City Thunder,2025-09-10 23:14:26
Total – Game,Over 224,1.781,Houston Rockets vs Oklahoma City Thunder,2025-09-10 23:14:26
```

**Validation Commands:**
```bash
head -10 data/stats-csv/nba_detailed_odds.csv
wc -l data/stats-csv/nba_detailed_odds.csv
```

---

### 4. advanced.csv ❌

**Location**: `data/stats-csv/advanced.csv`

**Statistics:**
- Total rows: **34**
- No relevant fields for opening odds

**Validation Commands:**
```bash
head -5 data/stats-csv/advanced.csv
wc -l data/stats-csv/advanced.csv
```

---

### 5. per-game.csv ❌

**Location**: `data/stats-csv/per-game.csv`

**Statistics:**
- Total rows: **33**
- No relevant fields for opening odds

**Validation Commands:**
```bash
head -5 data/stats-csv/per-game.csv
wc -l data/stats-csv/per-game.csv
```

---

### 6. stats.csv ❌

**Location**: `data/stats-csv/stats.csv`

**Statistics:**
- Total rows: **33**
- No relevant fields for opening odds

**Validation Commands:**
```bash
head -5 data/stats-csv/stats.csv
wc -l data/stats-csv/stats.csv
```

---

## Key Findings

### Field Population Percentages

**nba_main_lines.csv:**
- Moneyline (team1_moneyline): **99.3%** populated
- Moneyline (team2_moneyline): **99.3%** populated
- Spread (team1_spread): **99.3%** populated
- Spread (team2_spread): **99.3%** populated
- Total (over_total): **99.3%** populated
- Total (under_total): **99.3%** populated

**nba_2008-2025.csv:**
- Moneyline (moneyline_home): **85.7%** populated
- Moneyline (moneyline_away): **85.7%** populated
- Spread: **100.0%** populated
- Total: **100.0%** populated

### Odds Format Differences

1. **nba_main_lines.csv**: Uses **DECIMAL** odds format (e.g., 3.06, 1.392)
   - ✅ Directly usable for CatBoost training (model expects decimal odds)
   
2. **nba_2008-2025.csv**: Uses **AMERICAN** odds format (e.g., -1400, 900)
   - ⚠️ Requires conversion to decimal format before training
   - Conversion formula:
     - Positive American odds: `decimal = (american / 100) + 1`
     - Negative American odds: `decimal = (100 / abs(american)) + 1`

### Opening Odds Identification

1. **nba_main_lines.csv**: ✅ Can identify opening odds
   - Multiple timestamps per game (595/637 games)
   - Use earliest timestamp per game as opening odds
   
2. **nba_2008-2025.csv**: ⚠️ Cannot definitively identify opening odds
   - Only one row per game
   - Assumed to be opening odds (or possibly closing odds)

### Season Coverage

**nba_2008-2025.csv:**
- Covers seasons 2007-2008 through 2024-2025 (18 seasons)
- ~1,300 games per season
- **Total: 23,118 games**

**nba_main_lines.csv:**
- Covers seasons 2024-2025 and 2025-2026
- **Total: 637 unique games**
- Mostly 2025-2026 season (5,082 game-date combinations)

## Recommendations

1. **For Training Data:**
   - Use `nba_main_lines.csv` for 2024-2025 and 2025-2026 seasons (decimal format, can identify opening odds)
   - Use `nba_2008-2025.csv` for historical seasons 2007-2024 (requires American-to-decimal conversion)

2. **Data Loading:**
   - Ensure ETL pipeline converts American odds to decimal for `nba_2008-2025.csv`
   - For `nba_main_lines.csv`, use earliest timestamp per game to identify opening odds

3. **Missing Data:**
   - `nba_2008-2025.csv` has 14.3% missing moneyline data (3,298 games)
   - `nba_main_lines.csv` has 0.7% missing data (35 rows out of 5,132)

4. **Validation:**
   - Run the provided validation commands to verify data
   - Check that opening odds extraction logic correctly identifies earliest timestamps

## Validation Commands Summary

```bash
# Check all CSV files
cd /Users/adamvoliva/Code/bball

# nba_main_lines.csv
head -5 data/stats-csv/nba_main_lines.csv
wc -l data/stats-csv/nba_main_lines.csv

# nba_2008-2025.csv  
head -5 data/stats-csv/nba_2008-2025.csv
wc -l data/stats-csv/nba_2008-2025.csv

# Run comprehensive analysis
python3 scripts/analysis/comprehensive_csv_odds_analysis.py
```

## Missing Opening Odds Analysis by Season

### Games Missing in DB but Present in CSV

For the 1,992 games marked as missing opening odds in the database, here's the breakdown by season showing which ones have data available in CSV files:

| Season | Total Missing in DB | Have Data in CSV | % In CSV | Missing in Both DB & CSV | % Missing in Both |
|--------|---------------------|------------------|----------|--------------------------|-------------------|
| 2017-18 | 190 | 169 | **88.9%** | 21 | 11.1% |
| 2018-19 | 239 | 161 | **67.4%** | 78 | 32.6% |
| 2019-20 | 217 | 137 | **63.1%** | 80 | 36.9% |
| 2020-21 | 226 | 177 | **78.3%** | 49 | 21.7% |
| 2021-22 | 231 | 165 | **71.4%** | 66 | 28.6% |
| 2022-23 | 243 | 178 | **73.3%** | 65 | 26.7% |
| 2023-24 | 251 | 178 | **70.9%** | 73 | 29.1% |
| 2024-25 | 262 | 189 | **72.1%** | 73 | 27.9% |
| 2025-26 | 133 | 57 | **42.9%** | 76 | 57.1% |
| **TOTAL** | **1,992** | **1,411** | **70.8%** | **581** | **29.2%** |

### Key Findings

1. **Overall**: 70.8% of games missing opening odds in DB have data available in CSV files
   - This represents **1,411 games** that could potentially be loaded into the database

2. **Best Coverage**: 2017-18 season has 88.9% of missing games available in CSV
   - Only 21 games (11.1%) are truly missing from both sources

3. **Worst Coverage**: 2025-26 season has only 42.9% of missing games available in CSV
   - 76 games (57.1%) are missing from both DB and CSV
   - This is expected as 2025-26 is a future season with incomplete data

4. **Historical Seasons (2017-2024)**: Average 72.1% coverage in CSV
   - Most missing games from these seasons can be recovered from CSV files

5. **Recent Seasons (2020-2024)**: Average 73.2% coverage in CSV
   - Consistent coverage across recent seasons

### Recommendations Based on Season Analysis

1. **Priority 1 - Load CSV Data for Historical Seasons (2017-2024)**:
   - 1,354 games missing in DB but available in CSV (average 72% per season)
   - These can be loaded to significantly improve training data coverage

2. **Priority 2 - Investigate 2025-26 Season**:
   - Only 42.9% coverage suggests many games may not have odds data yet (future games)
   - Or odds scraping may not be capturing all games for this season

3. **Priority 3 - Address Truly Missing Games**:
   - 581 games (29.2%) are missing from both DB and CSV
   - These may require:
     - Additional data sources
     - Manual data entry
     - Or acceptance that some historical games don't have opening odds available

### Validation Commands

```bash
# Run season-by-season analysis
python3 scripts/analysis/analyze_missing_odds_by_season.py

# Check specific season coverage
python3 scripts/analysis/analyze_missing_odds_by_season.py | grep "2024-25"
```

## Evidence

All analysis performed using:
- Script: `scripts/analysis/comprehensive_csv_odds_analysis.py`
- Script: `scripts/analysis/analyze_missing_odds_by_season.py`
- Validation commands provided above
- Direct CSV inspection using Python csv module
- Date/season extraction from timestamp fields

**Analysis Date**: 2026-01-22  
**Files Analyzed**: 6 CSV files  
**Total Rows Analyzed**: ~124,000+ rows across all files  
**Games Missing in DB**: 1,992 games  
**Games Available in CSV**: 1,411 games (70.8%)
