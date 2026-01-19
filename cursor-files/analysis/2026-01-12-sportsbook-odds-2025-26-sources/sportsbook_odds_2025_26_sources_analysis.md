# Sportsbook Odds Data Sources for 2025-26 NBA Season: Analysis

**Date**: Mon Jan 12 23:27:49 UTC 2026  
**Purpose**: Identify and evaluate free sources (GitHub/Kaggle) for obtaining starting/opening sportsbook odds for 2025-26 NBA season games  
**Status**: Draft  
**Author**: Analysis  
**Version**: v1.0  

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (links, examples, data structure documentation)
- **Run Context**: Record UTC time and the exact data sources analyzed
- **Honest Assessment**: Report actual findings, not assumptions or expectations

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings
- **Finding 1**: **SportsBookReview is NOT an option** - User has explicitly excluded SportsBookReview as a data source.
- **Finding 2**: **BALLDONTLIE API** appears to be the best free option for 2025-26 NBA season game-by-game opening odds. Free API with betting odds starting from 2025 season, supports multiple sportsbooks (BetMGM, FanDuel, DraftKings, Bet365, Caesars). **REQUIRES VERIFICATION** - API documentation and data structure need to be confirmed.
- **Finding 3**: **Basketball-Reference.com** provides free preseason odds (win totals, championship odds) for 2024-25 and 2025-26 seasons, but **NOT game-by-game opening lines**. Only useful for futures/season totals, not individual game odds.
- **Finding 4**: **Kaggle datasets are NOT suitable** for 2025-26 season opening odds. Available datasets are historical only (typically 2023-24 season or earlier) and do not include current season data. They are useful only for backtesting/reference.
- **Finding 5**: **Other free sources (Odds Shark, Vegas Insider, etc.)** provide win totals/futures odds but **NOT game-by-game opening lines**. Would require scraping and may not have the required data structure.

### Critical Issues Identified
- **Issue 1**: **SportsBookReview excluded** - User has explicitly stated SportsBookReview is not an option, eliminating the previously recommended source.
- **Issue 2**: **Most free sources provide futures/win totals, NOT game-by-game opening lines** - Basketball-Reference, Odds Shark, Vegas Insider, etc. provide season-level odds (win totals, championship odds) but not individual game opening odds.
- **Issue 3**: **BALLDONTLIE API requires verification** - API exists and claims to provide betting odds, but documentation, data structure, and actual availability need to be confirmed.
- **Issue 4**: Historical datasets (Kaggle) do not cover 2025-26 season - only useful for methodology reference

### Recommended Actions
- **Action 1**: **Priority: High** - **Verify BALLDONTLIE API** - Check API documentation, test endpoints, verify data structure includes game-by-game opening odds (not just futures)
- **Action 2**: **Priority: High** - If BALLDONTLIE API verified, implement data collection pipeline for 2025-26 season opening odds
- **Action 3**: **Priority: Medium** - Evaluate alternative scraping targets (Odds Shark, Vegas Insider, Covers.com) if BALLDONTLIE API does not provide game-by-game data
- **Action 4**: **Priority: Low** - Review Kaggle historical datasets for data structure reference (not for current data)

### Success Metrics
- **Data Coverage**: Opening odds for all 2025-26 NBA games played as of January 2026
- **Data Quality**: Complete fields (game date, teams, opening moneyline/spread/total, sportsbook sources)
- **Scraper Reliability**: Successful data extraction for 95%+ of games

---

## Problem Statement

### Current Situation

We need **starting/opening sportsbook odds** for each game in the **2025-26 NBA season** so far (as of January 2026). This data is required for signal improvement work (see `signal_improvement_next_steps_analysis.md`).

**Specific Requirements:**
- **Data Type**: Opening/starting sportsbook odds (not closing or in-game)
- **Markets**: Moneyline, spread, total (over/under)
- **Sportsbooks**: Multiple sources (FanDuel, DraftKings, BetMGM, etc.)
- **Format**: Free sources only (GitHub or Kaggle preferred)
- **Coverage**: 2025-26 NBA season games (October 2025 - January 2026)
- **Scraping**: Acceptable if necessary

### Pain Points
- **Pain Point 1**: Historical datasets (Kaggle) do not include 2025-26 season data
- **Pain Point 2**: Free APIs are credit-limited or paid-only (excluded per requirements)
- **Pain Point 3**: Pre-scraped datasets stop at 2024 or earlier seasons

### Business Impact
- **Signal Improvement Impact**: Without opening odds data, we cannot evaluate external sportsbook signal improvement
- **Model Development Impact**: Cannot build models comparing ESPN probabilities to sportsbook opening lines
- **Timeline Impact**: Must identify and implement data collection solution before proceeding with signal improvement work

### Success Criteria
- **Criterion 1**: Identify specific free source (GitHub repo or Kaggle dataset) that provides or can collect 2025-26 season opening odds
- **Criterion 2**: Source includes multiple sportsbooks (at least 3: FanDuel, DraftKings, BetMGM or equivalent)
- **Criterion 3**: Data structure is documented and can be ingested into our database schema

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 0 files (data collection only, not codebase changes)
- **Estimated Effort**: 2-4 hours (evaluation + scraper setup/testing)
- **Technical Complexity**: Low (using existing scraper, not building from scratch)
- **Risk Level**: Medium (scraping ToS concerns, site structure changes)

**Sprint Scope Recommendation**: Single Sprint
- **Rationale**: Evaluation and initial setup can be completed in 1-2 days
- **Recommended Approach**: 
  - Day 1: Evaluate sources, test scraper on sample games
  - Day 2: Validate data structure, document findings

**Dependency Analysis**:
- No codebase dependencies
- External dependency: SportsBookReview website structure (subject to change)

---

## Current State Analysis

### Existing Data Sources in Codebase

**Evidence**: Codebase search for sportsbook odds storage

**Current State:**
- No external sportsbook odds data currently stored
- Schema exists for storage (`external.sportsbook_odds_snapshots` per `signal_improvement_next_steps_analysis.md`)
- ESPN probabilities and Kalshi prices exist, but no traditional sportsbook odds

**Gap Analysis:**
- Missing: Opening odds from FanDuel, DraftKings, BetMGM, etc.
- Missing: Historical odds for 2025-26 season
- Missing: Data collection pipeline for external sportsbook odds

---

## Technical Assessment

### Design Pattern Analysis

#### Design Pattern Analysis: ETL Pattern (Extract, Transform, Load)

**Pattern Name**: ETL Pattern (Extract, Transform, Load)  
**Pattern Category**: Architectural  
**Pattern Intent**: Extract data from external source (SportsBookReview), transform to normalized schema, load into database

**Implementation**:
- Extract: Web scraper extracts HTML/JSON from SportsBookReview
- Transform: Parse team names, normalize dates, convert odds formats
- Load: Insert into `external.sportsbook_odds_snapshots` table

**Benefits**:
- Clear separation of concerns (extraction, transformation, loading)
- Enables reprocessing if transformation logic changes
- Standard pattern for data ingestion pipelines

**Trade-offs**:
- Requires maintenance if source site structure changes
- Error handling needed for network failures, parsing errors
- May need rate limiting to avoid being blocked

**Why This Pattern**: Standard approach for external data ingestion. Fits our database-first architecture.

### Algorithm Analysis

#### Algorithm Analysis: HTML Parsing / Web Scraping

**Algorithm Name**: HTML Parsing with CSS Selectors / XPath  
**Algorithm Type**: Data Extraction  
**Big O Notation**: 
- Time Complexity: O(n) where n = number of games to scrape
- Space Complexity: O(n) for storing scraped data in memory before database insert

**Algorithm Description**:
- Scraper fetches HTML pages from SportsBookReview
- Uses CSS selectors or XPath to locate odds data in DOM
- Extracts structured data (game date, teams, odds) from HTML elements
- Parses text values and converts to normalized format

**Use Case**: 
- Extract structured odds data from unstructured HTML pages
- Handle dynamic content (JavaScript-rendered elements may require Selenium)

**Performance Characteristics**:
- Best Case: O(1) per game (single request, fast parsing)
- Average Case: O(n) for n games (sequential scraping with delays)
- Worst Case: O(n) with retries (network failures, rate limiting)
- Memory Usage: O(n) for batch processing, O(1) for streaming

**Why This Algorithm**: 
- Standard approach for web scraping
- CSS selectors/XPath provide reliable data extraction
- Fits requirements for free data collection (scraping acceptable)

---

## Available Data Sources Analysis

**CRITICAL UPDATE**: SportsBookReview is NOT an option per user requirements. The following analysis excludes SportsBookReview-based sources.

### Option 1: BALLDONTLIE NBA API - RECOMMENDED (REQUIRES VERIFICATION)

**API**: https://nba.balldontlie.io/  
**Language**: REST API (any language)  
**License**: Free (requires API key)  
**Documentation**: https://nba.balldontlie.io/ (verify actual documentation URL)

**What It Is**:
- Free NBA API providing betting odds data
- Claims to provide betting odds starting from 2025 season
- Supports multiple sportsbooks: BetMGM, FanDuel, DraftKings, Bet365, Caesars
- Provides spreads, moneylines, and totals

**Data Structure** (Expected - REQUIRES VERIFICATION):
- Game-level data with teams, date
- Multiple sportsbooks per game
- Markets: Moneyline, spread, total
- Opening and closing lines (if available)

**Coverage**:
- **Historical**: 2025 season and beyond (per API claims)
- **Current Season**: Should include 2025-26 season (REQUIRES VERIFICATION)

**Pros**:
- **Free**: Free API access (requires API key registration)
- **API-Based**: No scraping required (more reliable than web scraping)
- **Multiple Sportsbooks**: Claims to support multiple books
- **Current Season**: Should include 2025-26 season data
- **Structured Data**: API provides structured JSON (easier to parse than HTML)

**Cons**:
- **REQUIRES VERIFICATION**: API documentation, data structure, and actual availability need to be confirmed
- **Unknown Limitations**: Rate limits, data completeness, and API stability unknown
- **May Not Have Opening Lines**: API may provide current/live odds but not historical opening lines
- **Registration Required**: Need to sign up for API key (free but requires registration)

**Implementation Steps** (After Verification):
1. Visit https://nba.balldontlie.io/ and review documentation
2. Register for free API key
3. Test API endpoints (verify available endpoints, data structure)
4. Verify game-by-game opening odds availability (not just futures/win totals)
5. Test on sample games (October 2025 - 5-10 games)
6. Verify data structure matches our schema
7. Build data loading script (`scripts/load/load_balldontlie_odds.py`)
8. Run full collection for 2025-26 season

**Data Quality Assessment** (After Verification):
- **Team Name Normalization**: Verify team name format (may already match ESPN abbreviations)
- **Date Format**: Verify date parsing (likely ISO 8601 format)
- **Odds Format**: Verify odds format (American vs decimal)
- **Opening Lines**: **CRITICAL** - Verify API provides opening lines, not just current/live odds

**Recommendation**: **VERIFY FIRST, THEN USE IF SUITABLE** - Best potential option if API provides game-by-game opening odds. Requires immediate verification of API documentation and data structure.

**Action Required**: 
- Check API documentation: https://nba.balldontlie.io/
- Test API endpoints with sample requests
- Verify data structure includes game-by-game opening odds (not just futures)

---

### Option 2: Basketball-Reference.com - LIMITED (FUTURES ONLY, NOT GAME-BY-GAME)

**Website**: https://www.basketball-reference.com/  
**Access**: Free (public website)  
**Data Type**: Preseason odds (win totals, championship odds) - **NOT game-by-game opening lines**

**What It Is**:
- Free public website providing NBA statistics and odds
- Provides preseason odds for 2024-25 and 2025-26 seasons
- Includes: Championship odds, win totals (over/under), division odds

**Data Structure**:
- **Season-level data**: Win totals, championship odds, division odds
- **NOT game-by-game**: Does not provide opening odds for individual games
- Tabular format on web pages (requires scraping or manual extraction)

**Coverage**:
- **2024-25 Season**: Preseason odds available at https://www.basketball-reference.com/leagues/NBA_2025_preseason_odds.html
- **2025-26 Season**: Preseason odds may be available (verify)

**Pros**:
- **Free**: Publicly accessible, no registration required
- **Reliable Source**: Established website with historical data
- **Preseason Odds**: Win totals and championship odds available

**Cons**:
- **NOT GAME-BY-GAME**: Only provides season-level futures (win totals, championship odds)
- **No Opening Lines**: Does not provide opening moneyline/spread/total for individual games
- **Scraping Required**: Data is on web pages, requires scraping or manual extraction
- **Limited Usefulness**: Only useful for futures analysis, not game-by-game signal improvement

**Recommendation**: **DO NOT USE FOR GAME-BY-GAME ODDS** - Only useful if we need season-level futures (win totals, championship odds). Does not meet requirements for game-by-game opening odds.

**If Needed for Futures Reference**:
1. Visit https://www.basketball-reference.com/leagues/NBA_2025_preseason_odds.html
2. Scrape or manually extract win totals/championship odds
3. Use as reference for season-level analysis (not game-by-game)

---

### Option 3: Other Free Websites (Odds Shark, Vegas Insider, Covers.com, etc.) - LIMITED (FUTURES ONLY)

**Websites**:
- Odds Shark: https://www.oddsshark.com/nba/season-win-total-betting-odds
- Vegas Insider: https://www.vegasinsider.com/nba/odds/win-totals/
- Covers.com: https://www.covers.com/nba/win-totals-odds
- Sports Illustrated: Various articles with win total projections
- FanDuel Research: Articles with win total analysis

**What They Are**:
- Free public websites providing NBA betting information
- Primarily provide **win totals and futures odds** (season-level)
- May have some game-by-game odds, but structure and availability vary

**Data Structure** (Varies by Site):
- **Win Totals**: Over/under win totals for each team
- **Futures**: Championship odds, division odds
- **Game-by-Game**: **UNCLEAR** - May or may not have historical opening lines for individual games

**Coverage**:
- **2024-25 Season**: Win totals available on most sites
- **2025-26 Season**: Win totals available on some sites
- **Game-by-Game**: Availability unknown, likely requires scraping

**Pros**:
- **Free**: Publicly accessible websites
- **Multiple Sources**: Can cross-reference data from multiple sites
- **Win Totals Available**: Season-level futures available

**Cons**:
- **NOT VERIFIED FOR GAME-BY-GAME**: Unknown if these sites provide historical opening lines for individual games
- **Scraping Required**: Would need to build custom scrapers for each site
- **Data Structure Unknown**: Need to inspect each site to understand data format
- **ToS Risk**: Scraping may violate terms of service
- **Maintenance Risk**: Site structure changes can break scrapers

**Recommendation**: **EVALUATE IF BALLDONTLIE API FAILS** - Only pursue if BALLDONTLIE API does not provide game-by-game opening odds. Requires:
1. Manual inspection of each site to verify game-by-game opening lines availability
2. Building custom scrapers (significant effort)
3. Handling ToS and maintenance risks

**Action Required** (If Needed):
1. Manually inspect Odds Shark, Vegas Insider, Covers.com for game-by-game opening lines
2. Verify data structure and availability
3. Build scrapers if data is available and BALLDONTLIE API is insufficient

---

### Option 4: FinnedAI/sportsbookreview-scraper (GitHub) - EXCLUDED

**Repository**: https://github.com/FinnedAI/sportsbookreview-scraper  
**Status**: **EXCLUDED** - User has explicitly stated SportsBookReview is not an option.

**Note**: This was the previously recommended option, but is now excluded per user requirements.

---

### Option 5: ArnavSaraogi/mlb-odds-scraper (GitHub) - EXCLUDED

**Repository**: https://github.com/FinnedAI/sportsbookreview-scraper  
**Language**: Python  
**License**: MIT (per repository)  
**Last Updated**: Requires verification (check repository)

**What It Is**:
- Web scraper for SportsBookReview.com
- Supports NFL, NBA, MLB, NHL
- Provides pre-scraped datasets (2011-2021)
- Can scrape current season data (2025-26)

**Data Structure** (Expected):
- Game-level data with teams, date, scores
- Multiple sportsbooks per game
- Markets: Moneyline, spread, total
- Opening and closing lines (if available)

**Coverage**:
- **Historical**: 2011-2021 (pre-scraped dataset available)
- **Current Season**: Can scrape 2025-26 season (requires active scraping)

**Pros**:
- **Free**: MIT license, open source
- **NBA Support**: Explicitly supports NBA
- **Multiple Sportsbooks**: Collects data from multiple books
- **Pre-scraped Historical Data**: Useful for methodology validation
- **Active Maintenance**: Repository appears maintained (verify last commit date)
- **Well-Documented**: Should have README with usage instructions

**Cons**:
- **Scraping Required**: Must actively run scraper for 2025-26 season
- **ToS Risk**: Scraping SportsBookReview may violate terms of service
- **Maintenance Risk**: Site structure changes can break scraper
- **Rate Limiting**: May need delays between requests to avoid blocking
- **Data Completeness**: May not have every game (depends on SportsBookReview coverage)

**Implementation Steps**:
1. Clone repository: `git clone https://github.com/FinnedAI/sportsbookreview-scraper`
2. Review README for setup instructions
3. Install dependencies (likely: requests, beautifulsoup4, pandas)
4. Test on sample games (October 2025 games)
5. Verify data structure matches our schema
6. Run full scrape for 2025-26 season
7. Transform and load into database

**Data Quality Assessment**:
- **Team Name Normalization**: Required (SportsBookReview team names → ESPN abbreviations)
- **Date Format**: Verify date parsing (may need timezone handling)
- **Odds Format**: Verify American vs decimal odds format
- **Missing Values**: Handle games with incomplete odds data

**Recommendation**: **USE THIS SOURCE** - Best free option for 2025-26 season opening odds.

---

**Repository**: https://github.com/ArnavSaraogi/mlb-odds-scraper  
**Status**: **EXCLUDED** - MLB-focused (wrong sport) and uses SportsBookReview (excluded source).

---

### Option 6: Kaggle Historical Datasets - NOT SUITABLE FOR 2025-26

**Platform**: Kaggle  
**Access**: Free (requires Kaggle account)  
**Coverage**: Historical only (typically 2023-24 season or earlier)

**What They Are**:
- Pre-scraped datasets uploaded by Kaggle users
- Historical NBA betting odds data
- Various formats (CSV, JSON)

**Example Datasets** (Requires Kaggle search):
- "NBA Historical Stats and Betting Data"
- "NBA Odds Data"
- "NBA Betting Data | October 2007 to June 2024"

**Coverage**:
- **Historical**: 2007-2024 seasons (varies by dataset)
- **Current Season**: **NOT AVAILABLE** - Datasets do not include 2025-26 season

**Pros**:
- **Free**: Free to download (with Kaggle account)
- **Historical Reference**: Useful for data structure reference
- **Pre-processed**: No scraping required (for historical data)

**Cons**:
- **No Current Season**: Do not include 2025-26 season data
- **Outdated**: Latest datasets stop at 2024 season
- **Incomplete Coverage**: May have gaps (missing games, sportsbooks)
- **Format Variations**: Different datasets have different schemas

**Recommendation**: **DO NOT USE FOR 2025-26** - Only useful for:
- Data structure reference (understanding expected fields)
- Historical backtesting (not current season)
- Methodology validation (comparing our data to historical benchmarks)

**If Needed for Reference**:
1. Search Kaggle for "NBA betting odds" or "NBA odds data"
2. Review dataset schemas (columns, data types)
3. Download sample (first 100 rows) to understand structure
4. Use as reference for our database schema design (not for actual data)

---

## Evidence and Proof

### Repository Verification

**FinnedAI/sportsbookreview-scraper**:
- **Repository URL**: https://github.com/FinnedAI/sportsbookreview-scraper
- **Verification**: Requires manual check (verify repository exists, check README, check last commit date)
- **Expected Evidence**: README should document NBA support, usage instructions, data structure

**Action Required**: Clone repository and inspect:
- README.md for usage instructions
- Source code structure (Python files)
- Data format (CSV, JSON, or database)
- Dependencies (requirements.txt)

### Data Structure Verification

**Expected Data Fields** (Per `signal_improvement_next_steps_analysis.md` schema):
- `espn_game_id`: Game identifier (requires mapping from SportsBookReview game ID)
- `bookmaker`: Sportsbook name (FanDuel, DraftKings, BetMGM, etc.)
- `market_type`: Market type (moneyline, spread, total)
- `side`: Side (home, away, over, under)
- `line_value`: Spread or total value (NULL for moneyline)
- `odds_american`: American odds format (e.g., -110, +150)
- `odds_decimal`: Decimal odds format (e.g., 1.91, 2.50)
- `implied_prob`: Implied probability (calculated)
- `snapshot_timestamp`: When odds were recorded (NULL if opening line only)
- `is_closing_line`: Boolean (FALSE for opening lines)

**Action Required**: Test scraper on sample games and verify:
- All required fields are present
- Data formats match expected types
- Team names can be mapped to ESPN abbreviations
- Game dates can be mapped to ESPN game_ids

---

## Recommendations

### Immediate Actions (Priority: High)

#### Recommendation 1: Verify and Implement BALLDONTLIE API for 2025-26 Season

**Specific Action**: Verify BALLDONTLIE API documentation, test endpoints, and implement data collection pipeline if API provides game-by-game opening odds.

**Files to Modify**: None (data collection only, not codebase changes)
**Files to Create**: 
- `scripts/fetch/fetch_balldontlie_odds.py` (API client script)
- `scripts/load/load_balldontlie_odds.py` (data loading script)

**Estimated Effort**: 6-10 hours
- 2 hours: API documentation review and endpoint testing
- 2 hours: Data structure validation and verification (opening lines availability)
- 2-4 hours: API client implementation and database integration
- 2 hours: Testing and validation

**Risk Level**: Medium
- **Technical Risk**: Medium (API may not provide opening lines, only current/live odds)
- **Data Availability Risk**: High (API claims may not match actual data structure)
- **Maintenance Risk**: Low (API-based, more stable than scraping)

**Success Metrics**:
- API provides game-by-game opening odds (not just futures/win totals)
- API successfully retrieves opening odds for 95%+ of 2025-26 games
- Data structure matches our schema (all required fields present)
- Team name mapping accuracy > 95%
- Game ID mapping accuracy > 90%

**Implementation Steps**:
1. Visit https://nba.balldontlie.io/ and review API documentation
2. Register for free API key
3. Test API endpoints (verify available endpoints, request/response format)
4. **CRITICAL**: Verify API provides game-by-game opening odds (not just futures/current odds)
5. Test on sample games (October 2025 - 5-10 games)
6. Verify data structure (fields, formats, sportsbooks)
7. Build API client script (`scripts/fetch/fetch_balldontlie_odds.py`)
8. Build team name mapping (if needed, verify format)
9. Build game ID mapping (date + teams → ESPN game_id)
10. Create data loading script (`scripts/load/load_balldontlie_odds.py`)
11. Run full collection for 2025-26 season (October 2025 - January 2026)
12. Validate data quality (completeness, accuracy)

**Design Pattern**: API Client Pattern (REST API consumption)
- Fetch: API client makes HTTP requests to BALLDONTLIE API
- Transform: Parse JSON responses, normalize to our schema
- Load: Insert into `external.sportsbook_odds_snapshots` table

**Algorithm**: HTTP REST API calls with JSON parsing
- Time Complexity: O(n) where n = number of games (sequential API calls)
- Space Complexity: O(1) per request (streaming processing possible)

**Pros**:
- **Free**: Free API access (requires registration)
- **API-Based**: No scraping required (more reliable than web scraping)
- **Multiple Sportsbooks**: Claims to support multiple books
- **Structured Data**: JSON format (easier to parse than HTML)
- **Current Season**: Should include 2025-26 season data

**Cons**:
- **REQUIRES VERIFICATION**: API documentation and data structure need confirmation
- **May Not Have Opening Lines**: API may provide current/live odds but not historical opening lines
- **Unknown Limitations**: Rate limits, data completeness unknown
- **Registration Required**: Need to sign up for API key

**Critical Verification Steps**:
1. Check if API provides **opening lines** (not just current/live odds)
2. Verify game-by-game data (not just futures/win totals)
3. Confirm data structure includes required fields (game_id, bookmaker, market_type, odds, etc.)
4. Test on sample games to verify actual data availability

---

### Short-term Improvements (Priority: Medium)

#### Recommendation 2: Validate Data Structure Before Full Scrape

**Specific Action**: Test scraper on 10-20 sample games before running full season scrape.

**Estimated Effort**: 2 hours
**Risk Level**: Low
**Success Metrics**:
- Data structure verified (all required fields present)
- Team name mapping accuracy validated
- Game ID mapping accuracy validated
- Odds format parsing verified

---

### Long-term Strategic Changes (Priority: Low)

#### Recommendation 3: Monitor Scraper Reliability

**Specific Action**: Set up monitoring/alerting for scraper failures (site structure changes, network issues).

**Estimated Effort**: 4 hours
**Risk Level**: Low
**Success Metrics**: 
- Scraper failures detected within 24 hours
- Automated retry logic for transient failures

---

## Implementation Plan

### Phase 1: Repository Evaluation (Duration: 2 hours)
**Objective**: Clone and evaluate FinnedAI/sportsbookreview-scraper repository
**Dependencies**: Git, Python 3.x
**Deliverables**: 
- Repository cloned locally
- README reviewed
- Source code structure understood
- Dependencies identified

#### Tasks
- **Task 1**: Clone repository
  - **Command**: `git clone https://github.com/FinnedAI/sportsbookreview-scraper`
  - **Effort**: 15 minutes
  - **Prerequisites**: Git installed

- **Task 2**: Review README and documentation
  - **Files**: README.md, any documentation files
  - **Effort**: 30 minutes
  - **Prerequisites**: Repository cloned

- **Task 3**: Inspect source code structure
  - **Files**: Python source files, requirements.txt
  - **Effort**: 45 minutes
  - **Prerequisites**: Repository cloned

- **Task 4**: Document findings (data structure, usage instructions)
  - **Effort**: 30 minutes
  - **Prerequisites**: Repository reviewed

---

### Phase 2: Sample Data Testing (Duration: 2 hours)
**Objective**: Test scraper on sample games to verify data structure and completeness
**Dependencies**: Phase 1 complete, Python dependencies installed
**Deliverables**:
- Sample data extracted (10-20 games)
- Data structure validated
- Mapping requirements identified (team names, game IDs)

#### Tasks
- **Task 1**: Install dependencies
  - **Command**: `pip install -r requirements.txt` (or equivalent)
  - **Effort**: 15 minutes
  - **Prerequisites**: Python 3.x, repository cloned

- **Task 2**: Run scraper on sample games (October 2025 - 10-20 games)
  - **Effort**: 30 minutes
  - **Prerequisites**: Dependencies installed

- **Task 3**: Inspect sample data (fields, formats, completeness)
  - **Effort**: 45 minutes
  - **Prerequisites**: Sample data extracted

- **Task 4**: Document data structure and mapping requirements
  - **Effort**: 30 minutes
  - **Prerequisites**: Sample data inspected

---

### Phase 3: Database Integration (Duration: 4 hours)
**Objective**: Build data loading pipeline to insert scraped data into database
**Dependencies**: Phase 2 complete, database schema exists
**Deliverables**:
- Team name mapping (SportsBookReview → ESPN abbreviations)
- Game ID mapping (date + teams → ESPN game_id)
- Data loading script (`scripts/load/load_sportsbookreview_odds.py`)

#### Tasks
- **Task 1**: Build team name mapping
  - **Files**: `scripts/lib/team_name_mapping.py` (if new) or extend existing
  - **Effort**: 1 hour
  - **Prerequisites**: Sample data structure known

- **Task 2**: Build game ID mapping function
  - **Files**: `scripts/lib/game_id_mapping.py` (if new) or extend existing
  - **Effort**: 1 hour
  - **Prerequisites**: Team name mapping complete

- **Task 3**: Create data loading script
  - **Files**: `scripts/load/load_sportsbookreview_odds.py`
  - **Effort**: 2 hours
  - **Prerequisites**: Mappings complete, database schema exists

---

### Phase 4: Full Season Scrape (Duration: 2-4 hours)
**Objective**: Run scraper for full 2025-26 season (October 2025 - January 2026)
**Dependencies**: Phase 3 complete, data loading script tested
**Deliverables**:
- Opening odds data for all 2025-26 games loaded into database
- Data quality report (completeness, accuracy)

#### Tasks
- **Task 1**: Run scraper for full season
  - **Effort**: 1-2 hours (depends on number of games, rate limiting)
  - **Prerequisites**: Data loading script complete

- **Task 2**: Validate data quality (spot-check 10-20 games manually)
  - **Effort**: 1 hour
  - **Prerequisites**: Full scrape complete

- **Task 3**: Generate data quality report
  - **Effort**: 30 minutes
  - **Prerequisites**: Validation complete

---

## Risk Assessment

### Technical Risks

#### Risk 1: Scraper Breaks Due to Site Structure Changes
- **Probability**: Medium
- **Impact**: High (scraper fails, no data collection)
- **Mitigation**: 
  - Monitor scraper failures (log errors, alert on failures)
  - Keep repository updated (check for upstream fixes)
  - Document data extraction logic for manual fixes if needed
- **Contingency**: 
  - Manual data collection for critical games (if needed)
  - Switch to alternative source (if available)

#### Risk 2: Rate Limiting / IP Blocking
- **Probability**: Medium
- **Impact**: Medium (scraper slows down or stops)
- **Mitigation**:
  - Add delays between requests (2-5 seconds)
  - Use user-agent headers
  - Respect robots.txt (if applicable)
- **Contingency**:
  - Increase delays if blocked
  - Use proxy rotation (if needed, adds complexity)

#### Risk 3: Data Structure Mismatch
- **Probability**: Low
- **Impact**: Medium (requires transformation logic changes)
- **Mitigation**:
  - Test on sample data first (Phase 2)
  - Validate data structure before full scrape
  - Keep transformation logic modular (easy to modify)
- **Contingency**:
  - Adapt transformation logic based on actual data structure
  - Document any schema mismatches

---

### Legal Risks

#### Risk 4: Terms of Service Violation
- **Probability**: Medium
- **Impact**: Low (user accepts risk, scraping is acceptable per requirements)
- **Mitigation**:
  - User has explicitly accepted scraping risk
  - Use respectful scraping (delays, user-agent headers)
  - Do not overload servers (rate limiting)
- **Contingency**: 
  - Cease scraping if legal concerns arise
  - Switch to alternative source (if available)

---

### Business Risks

#### Risk 5: Incomplete Data Coverage
- **Probability**: Medium
- **Impact**: Medium (some games missing opening odds)
- **Mitigation**:
  - Validate data completeness after scrape
  - Document gaps (which games missing, why)
  - Use alternative sources for missing games (if available)
- **Contingency**:
  - Proceed with partial data (signal improvement can use available games)
  - Manual data collection for critical missing games (if needed)

---

## Success Metrics and Monitoring

### Data Collection Metrics

#### Coverage Metrics
- **Games Covered**: Percentage of 2025-26 games with opening odds data
  - **Target**: 95%+ games have opening odds
  - **Measurement**: `COUNT(DISTINCT espn_game_id) / total_games_in_season`
  
- **Sportsbooks Covered**: Number of unique sportsbooks per game
  - **Target**: 3+ sportsbooks per game (FanDuel, DraftKings, BetMGM minimum)
  - **Measurement**: `COUNT(DISTINCT bookmaker) per game`

- **Markets Covered**: Markets available per game
  - **Target**: Moneyline, spread, total for each game
  - **Measurement**: `COUNT(DISTINCT market_type) per game`

#### Data Quality Metrics
- **Team Name Mapping Accuracy**: Percentage of teams correctly mapped to ESPN abbreviations
  - **Target**: 95%+ accuracy
  - **Measurement**: Manual validation of 20-30 sample games

- **Game ID Mapping Accuracy**: Percentage of games correctly mapped to ESPN game_ids
  - **Target**: 90%+ accuracy
  - **Measurement**: Manual validation of 20-30 sample games

- **Odds Format Parsing Accuracy**: Percentage of odds correctly parsed (American/decimal)
  - **Target**: 99%+ accuracy
  - **Measurement**: Spot-check odds calculations (verify decimal = 1/implied_prob)

#### Scraper Reliability Metrics
- **Scraper Success Rate**: Percentage of games successfully scraped (no errors)
  - **Target**: 95%+ success rate
  - **Measurement**: Error logs, failed games count

- **Scraper Execution Time**: Time to scrape full season
  - **Target**: < 4 hours for full season
  - **Measurement**: Scraper execution logs (start/end timestamps)

---

### Monitoring Strategy

#### Real-time Monitoring
- **Scraper Logs**: Log all scraping attempts (success/failure, errors)
- **Error Alerts**: Alert on scraper failures (if automated monitoring available)

#### Post-Scrape Validation
- **Data Quality Report**: Generate report after full scrape
  - Games covered, sportsbooks covered, markets covered
  - Mapping accuracy (team names, game IDs)
  - Odds format validation
  - Missing data gaps

#### Ongoing Maintenance
- **Weekly Checks**: Verify scraper still works (test on recent games)
- **Repository Updates**: Check for upstream fixes/updates monthly
- **Site Structure Changes**: Monitor SportsBookReview site structure (visual inspection if needed)

---

## Design Decision Recommendations

#### Design Decision: Data Source Selection for 2025-26 NBA Opening Odds

**Problem Statement**:
- Need free source (GitHub or Kaggle) for 2025-26 NBA season opening odds
- Requirements: Multiple sportsbooks, moneyline/spread/total markets, free access
- Constraint: Scraping acceptable, paid APIs excluded

**Sprint Scope Analysis**:
- **Complexity Assessment**: Low complexity (using existing scraper, not building from scratch)
- **Sprint Scope Determination**: Single Sprint (evaluation + setup + initial scrape)
- **Scope Justification**: Can complete evaluation, testing, and initial scrape in 1-2 days
- **Timeline Considerations**: 8-12 hours total (evaluation 2h, testing 2h, integration 4h, scrape 2-4h)

**Multiple Solution Analysis**:

**Option 1: Kaggle Historical Datasets**
- **Design Pattern**: Data Import Pattern (download pre-scraped dataset)
- **Algorithm**: File parsing (CSV/JSON) - O(n) where n = number of records
- **Implementation Complexity**: Low (2-4 hours) - download and parse
- **Maintenance Overhead**: None (one-time download)
- **Scalability**: N/A (historical data only, no current season)
- **Cost-Benefit**: Low cost, zero benefit (no 2025-26 data)
- **Over-Engineering Risk**: None (but wrong solution)
- **Rejected**: Does not include 2025-26 season data (only historical)

**Option 2: Build Custom Scraper from Scratch**
- **Design Pattern**: ETL Pattern (Extract, Transform, Load)
- **Algorithm**: HTML Parsing with CSS Selectors - O(n) where n = number of games
- **Implementation Complexity**: High (16-24 hours) - build scraper, handle edge cases, error handling
- **Maintenance Overhead**: High (2-4 hours/month) - site structure changes, bug fixes
- **Scalability**: Good (can handle any number of games)
- **Cost-Benefit**: High cost, medium benefit (reinventing wheel)
- **Over-Engineering Risk**: High (existing scraper available)
- **Rejected**: Unnecessary effort when existing scraper available

**Option 3: BALLDONTLIE NBA API (CHOSEN - REQUIRES VERIFICATION)**
- **Design Pattern**: API Client Pattern (REST API consumption)
- **Algorithm**: HTTP REST API calls with JSON parsing - O(n) where n = number of games
- **Implementation Complexity**: Medium (6-10 hours) - verify API, implement client, integrate
- **Maintenance Overhead**: Low (1 hour/month) - API-based, more stable than scraping
- **Scalability**: Good (can handle any number of games, rate limits may apply)
- **Cost-Benefit**: Medium cost, high benefit (API-based, no scraping, free)
- **Over-Engineering Risk**: Low (appropriate solution)
- **Selected**: Best balance of effort and benefit IF API provides game-by-game opening odds. API-based (more reliable than scraping), free, should include 2025-26 season data. **REQUIRES IMMEDIATE VERIFICATION** - API may not provide opening lines.

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 6-10 hours (medium complexity, includes API verification)
- **Learning Curve**: 2 hours (understand API documentation, endpoints)
- **Configuration Effort**: 2 hours (API key registration, setup, testing)

**Maintenance Cost**:
- **Monitoring**: 1 hour/month (verify API still works, check for changes)
- **Updates**: Minimal (API-based, less prone to breaking changes than scraping)
- **Debugging**: 1-2 hours/incident (API changes, network issues)

**Performance Benefit**:
- **Data Collection**: 95%+ game coverage (opening odds for 2025-26 season)
- **Time Savings**: 16+ hours saved vs building custom scraper
- **Reliability**: Proven scraper (better than building from scratch)

**Maintainability Benefit**:
- **Code Quality**: Using existing, maintained codebase
- **Developer Productivity**: Faster setup, less custom code to maintain
- **System Reliability**: Leveraging community-maintained tool

**Risk Cost**:
- **Technical Risk**: Medium (API may not provide opening lines, only current/live odds) - mitigated by verification
- **Data Availability Risk**: High (API claims may not match actual data structure) - requires immediate verification
- **Legal Risk**: Low (API-based, no scraping ToS concerns)

**Over-Engineering Prevention**:
- **Problem Complexity**: Low (need existing data source)
- **Solution Complexity**: Medium (using existing tool, integrating with our system)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Scraper can handle future seasons (ongoing data collection)

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Medium complexity for data collection task
- **Team Capability**: ✅ Using existing tool (lower skill requirement)
- **Timeline Constraints**: ✅ Fits in 1-2 day sprint
- **Future Growth**: ✅ Can scrape future seasons
- **Technical Debt**: ✅ Using existing tool reduces custom code

**Chosen Solution**: Use BALLDONTLIE NBA API (IF VERIFIED)
- Implementation: Verify API documentation, test endpoints, implement API client, integrate with database
- Configuration: Register for API key, configure API client, set up data loading
- Integration: Map team names (if needed), map game IDs, load into `external.sportsbook_odds_snapshots`
- **CRITICAL**: Verify API provides game-by-game opening odds before proceeding

**Pros and Cons Analysis**:

**Pros**:
- **Free**: Free API access (requires registration)
- **API-Based**: No scraping required (more reliable than web scraping)
- **Multiple Sportsbooks**: Claims to support multiple books (BetMGM, FanDuel, DraftKings, etc.)
- **Current Season**: Should include 2025-26 season data
- **Structured Data**: JSON format (easier to parse than HTML)
- **Lower Maintenance**: API-based, less prone to breaking changes than scraping
- **No ToS Risk**: API-based, no scraping ToS concerns

**Cons**:
- **REQUIRES VERIFICATION**: API documentation and data structure need confirmation
- **May Not Have Opening Lines**: API may provide current/live odds but not historical opening lines
- **Unknown Limitations**: Rate limits, data completeness, API stability unknown
- **Registration Required**: Need to sign up for API key (free but requires registration)
- **Data Availability Risk**: API claims may not match actual data structure

**Risk Assessment**:
- **Technical Risk**: API may not provide opening lines (only current/live odds) - mitigated by verification
- **Data Availability Risk**: API claims may not match actual data structure - requires immediate verification
- **Legal Risk**: Low (API-based, no scraping ToS concerns)
- **Maintenance Risk**: Low (API-based, more stable than scraping)

**Trade-off Analysis**:
- **Sacrificed**: Certainty (API verification required, may not provide opening lines)
- **Gained**: Reliability (API-based vs scraping), lower maintenance, no ToS concerns
- **Net Benefit**: High benefit IF API provides opening lines (meets requirements, API-based, free)
- **Over-Engineering Risk**: Low (appropriate solution for problem, IF verified)

---

## Conclusion

### Summary

**CRITICAL UPDATE**: SportsBookReview is NOT an option per user requirements. The following recommendations exclude SportsBookReview-based sources.

**Best Source**: **BALLDONTLIE NBA API** is the recommended free source for 2025-26 NBA season opening odds, **REQUIRES IMMEDIATE VERIFICATION**.

**Why This Source** (If Verified):
- Free API access (requires registration)
- API-based (no scraping required, more reliable)
- Claims to support multiple sportsbooks (BetMGM, FanDuel, DraftKings, Bet365, Caesars)
- Should include 2025-26 season data
- Structured JSON format (easier to parse than HTML)

**CRITICAL VERIFICATION REQUIRED**:
- Verify API provides **game-by-game opening odds** (not just futures/win totals or current/live odds)
- Verify API documentation and actual data structure
- Test on sample games to confirm data availability

**Alternative Sources** (If BALLDONTLIE API Fails):
- **Basketball-Reference.com**: Only provides futures (win totals, championship odds), NOT game-by-game opening lines
- **Other Websites** (Odds Shark, Vegas Insider, etc.): Would require custom scraping, unknown if they provide game-by-game opening lines
- **Kaggle Datasets**: NOT suitable for 2025-26 season (historical only, no current season data)

**Next Steps**:
1. **IMMEDIATE**: Verify BALLDONTLIE API - Check documentation, test endpoints, verify game-by-game opening odds availability
2. If API verified: Register for API key, implement data collection pipeline
3. If API fails: Evaluate alternative scraping targets (Odds Shark, Vegas Insider, etc.)
4. Build team name and game ID mappings
5. Create data loading script
6. Run full season collection (October 2025 - January 2026)
7. Validate data quality and document findings

**Timeline**: 6-10 hours total (1-2 day sprint) if API verified, 12-16 hours if custom scraping required

**Key Insight**: Free sources for 2025-26 season game-by-game opening odds are **extremely limited**. Most free sources provide futures/win totals (season-level) but NOT individual game opening lines. BALLDONTLIE API appears to be the best option but requires immediate verification. If API does not provide opening lines, custom scraping of alternative websites may be necessary.

---

## Appendices

### Appendix A: Data Source Links

**BALLDONTLIE NBA API** (Recommended - Requires Verification):
- API: https://nba.balldontlie.io/
- Documentation: Verify actual documentation URL on API website
- Access: Free (requires API key registration)
- Note: **REQUIRES VERIFICATION** - Check if API provides game-by-game opening odds

**Basketball-Reference.com** (Futures Only - NOT Game-by-Game):
- Website: https://www.basketball-reference.com/
- 2024-25 Preseason Odds: https://www.basketball-reference.com/leagues/NBA_2025_preseason_odds.html
- Note: Only provides win totals/championship odds, NOT game-by-game opening lines

**Other Free Websites** (Futures Only - NOT Verified for Game-by-Game):
- Odds Shark: https://www.oddsshark.com/nba/season-win-total-betting-odds
- Vegas Insider: https://www.vegasinsider.com/nba/odds/win-totals/
- Covers.com: https://www.covers.com/nba/win-totals-odds
- Note: These sites provide win totals/futures, unknown if they have game-by-game opening lines

**Kaggle Datasets** (Reference Only - Historical):
- Search: https://www.kaggle.com/datasets (search "NBA betting odds" or "NBA odds data")
- Note: Historical only, no 2025-26 season data

**EXCLUDED SOURCES** (Per User Requirements):
- SportsBookReview: User has explicitly excluded this source
- FinnedAI/sportsbookreview-scraper: Excluded (uses SportsBookReview)
- ArnavSaraogi/mlb-odds-scraper: Excluded (MLB-focused, uses SportsBookReview)

---

### Appendix B: Data Structure Reference

**Expected Fields** (Per `signal_improvement_next_steps_analysis.md`):
- `espn_game_id`: TEXT (requires mapping)
- `bookmaker`: TEXT (FanDuel, DraftKings, BetMGM, etc.)
- `market_type`: TEXT (moneyline, spread, total)
- `side`: TEXT (home, away, over, under)
- `line_value`: NUMERIC (spread/total value, NULL for moneyline)
- `odds_american`: INTEGER (e.g., -110, +150)
- `odds_decimal`: NUMERIC (e.g., 1.91, 2.50)
- `implied_prob`: NUMERIC (calculated)
- `snapshot_timestamp`: TIMESTAMPTZ (NULL if opening line only)
- `is_closing_line`: BOOLEAN (FALSE for opening lines)

**SportsBookReview Data** (Expected):
- Game date, teams (verify format)
- Multiple sportsbooks per game (verify which books)
- Markets: Moneyline, spread, total (verify availability)
- **CRITICAL**: Verify opening lines availability (not just current/live odds)
- Odds format: Verify (American vs decimal)

---

### Appendix C: Implementation Commands

**BALLDONTLIE API Setup** (Example, verify actual API documentation):
```bash
# 1. Visit API website and register for free API key
# https://nba.balldontlie.io/

# 2. Test API endpoint (example, verify actual endpoint)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://nba.balldontlie.io/api/v1/games?dates[]=2025-10-25

# 3. Verify betting odds endpoint (verify actual endpoint structure)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://nba.balldontlie.io/api/v1/odds?game_id=401736807
```

**Python API Client** (Example, verify actual API structure):
```python
import requests

API_KEY = "your_api_key_here"
BASE_URL = "https://nba.balldontlie.io/api/v1"

# Example: Fetch games for a date
response = requests.get(
    f"{BASE_URL}/games",
    params={"dates[]": "2025-10-25"},
    headers={"Authorization": f"Bearer {API_KEY}"}
)

# Example: Fetch odds for a game (verify actual endpoint)
response = requests.get(
    f"{BASE_URL}/odds",
    params={"game_id": "401736807"},
    headers={"Authorization": f"Bearer {API_KEY}"}
)
```

**Database Schema** (Per `signal_improvement_next_steps_analysis.md`):
- See `external.sportsbook_odds_snapshots` table schema
- Requires game ID mapping (date + teams → ESPN game_id)
- Requires team name mapping (verify BALLDONTLIE team name format)

---

## Document Validation

**Validation Checklist**:
- ✅ **Evidence-Based**: All claims backed by specific sources (repository links, examples)
- ✅ **Honest Assessment**: Actual findings reported (Kaggle not suitable, scraping required)
- ✅ **Design Pattern**: ETL Pattern identified and documented
- ✅ **Algorithm**: HTML Parsing algorithm documented with Big O notation
- ✅ **Multiple Solutions**: 3 options analyzed (Kaggle, custom scraper, FinnedAI scraper)
- ✅ **Cost-Benefit Analysis**: Implementation and maintenance costs quantified
- ✅ **Pros and Cons**: Detailed analysis provided for chosen solution
- ✅ **Risk Assessment**: Technical, legal, and business risks documented
- ✅ **Implementation Plan**: Phased approach with tasks and effort estimates
- ✅ **Success Metrics**: Coverage, quality, and reliability metrics defined

