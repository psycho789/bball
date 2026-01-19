# Sprint 1: Sportsbook Odds Database Integration

**Date**: Tue Jan 13 02:35:01 PST 2026  
**Sprint Duration**: 10 days (16-24 hours total)  
**Sprint Goal**: Load sportsbook odds data from CSV files (`nba_2008-2025.csv` and `nba_main_lines.csv`) into database, connect to ESPN games, and enable model/grid search integration with opening odds  
**Current Status**: Odds data exists in CSV files but not in database. Schema `external.sportsbook_odds_snapshots` exists but requires extension. No connection to ESPN games. Opening odds not accessible for models/grid searches.  
**Target Status**: Opening odds loaded into `external.sportsbook_odds_snapshots` for 2017-2025 seasons, 90%+ mapped to ESPN game_ids, opening odds accessible in canonical snapshot dataset (`derived.snapshot_features_v1`) for model/grid search use  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence (commands + verbatim output, code refs, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`)
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/2026-01-13-sportsbook-odds-database-integration/sportsbook_odds_database_integration_analysis.md`
- **Current Implementation**:
  - `external.sportsbook_odds_snapshots` - Schema exists (per `signal_improvement_next_steps_analysis.md`)
  - `espn.scoreboard_games` - ESPN games table for mapping
  - `scripts/load/load_kalshi_markets.py` - Reference for ESPN game mapping pattern
  - `data/stats-csv/nba_2008-2025.csv` - Historical odds data (23,120 games)
  - `data/stats-csv/nba_main_lines.csv` - 2025-26 season odds data (5,134 rows)

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified]
- **QC Results**: [To be verified]
- **Code Coverage**: [To be verified]
- **Build Status**: [To be verified]

**Purpose**: This baseline ensures we maintain or improve code quality throughout the sprint and provides historical reference for quality metrics.

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database** - no INSERT, UPDATE, ALTER, TRUNCATE, DELETE unless part of sprint plan
- **DO NOT modify database users** - no user management or system changes

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

**Git Usage Rules**:
- **NO git commands** unless explicitly mentioned in sprint plan
- **NO git operations** unless explicitly mentioned in analysis
- **NO version control** unless explicitly mentioned in prompt by prompter
- **NO commits, pushes, pulls, or branches** unless explicitly directed

**Exception**: Git usage is only allowed when explicitly mentioned in the analysis document, sprint plan, or prompt by the prompter.

## Sprint Overview

### Business Context
- **Business Driver**: Enable signal improvement by incorporating external sportsbook opening odds into models and grid searches. Opening odds provide market-implied probabilities that can improve ESPN probability predictions.
- **Success Criteria**: 
  - Opening odds loaded for 95%+ of games in 2017-2025 range
  - 90%+ of odds records mapped to ESPN game_ids
  - Opening odds accessible in canonical snapshot dataset for grid search/model training
- **Stakeholders**: Data science team, model developers, grid search users
- **Timeline Constraints**: None (no hard deadlines)

### Technical Context
- **Current System State**: 
  - CSV files contain odds data: `nba_2008-2025.csv` (historical, American odds, abbreviations) and `nba_main_lines.csv` (2025-26, decimal odds, full names, time-series)
  - Schema `external.sportsbook_odds_snapshots` exists but missing `is_opening_line` column
  - No ETL pipeline to load CSV data
  - No ESPN game mapping logic
  - Opening odds not in canonical snapshot dataset
- **Target System State**: 
  - Schema extended with `is_opening_line` column
  - ETL pipeline loads both CSV files with transformations (odds conversion, team normalization, opening line identification)
  - ESPN game mapping connects odds to games
  - Opening odds available in `derived.snapshot_features_v1` view
- **Architecture Impact**: Adds new ETL pipeline, extends schema, creates canonical dataset view
- **Integration Points**: ESPN games table, canonical snapshot dataset, grid search/model training

### Sprint Scope
- **In Scope**: 
  - Schema extension (add `is_opening_line` column)
  - Team name normalization library
  - Odds format conversion library
  - ETL pipeline for both CSV files
  - ESPN game mapping
  - Opening line identification
  - Canonical dataset integration
- **Out of Scope**: 
  - Closing line identification (only opening lines)
  - In-game line movements (only pre-game opening lines)
  - Additional data sources (only the two CSV files)
  - Real-time odds updates (only historical data loading)
- **Assumptions**: 
  - CSV files are complete and accurate
  - ESPN games table has sufficient coverage for mapping
  - Team name variations can be normalized with dictionary + fuzzy matching
- **Constraints**: 
  - Must handle both American and decimal odds formats
  - Must handle both abbreviations and full team names
  - Must identify opening lines from time-series data

## Sprint Phases

### Phase 1: Schema Extension (Duration: 2 hours)
**Objective**: Extend `external.sportsbook_odds_snapshots` schema to support opening lines and source tracking
**Dependencies**: Database access, migration system (`scripts/migrate.py`)
**Deliverables**: 
- Migration file: `db/migrations/XXX_external_sportsbook_odds_schema_extend.sql`
- Schema supports `is_opening_line` flag and handles NULL timestamps
- Index created for opening lines queries

### Phase 2: Team Name Normalization (Duration: 2-3 hours)
**Objective**: Build team name mapping dictionary and normalization functions
**Dependencies**: Phase 1 complete
**Deliverables**:
- `scripts/lib/team_name_mapping.py` with mapping dictionary and normalization functions
- Handles abbreviations (ny, cle) and full names (New York Knicks, Cleveland Cavaliers)
- Tested on sample data from both CSV files

### Phase 3: Odds Format Conversion (Duration: 1-2 hours)
**Objective**: Build odds format conversion functions (American ↔ Decimal)
**Dependencies**: Phase 2 complete
**Deliverables**:
- `scripts/lib/odds_conversion.py` with conversion functions
- Handles both American and decimal odds formats
- Tested for conversion accuracy

### Phase 4: ETL Pipeline Development (Duration: 8-12 hours)
**Objective**: Build ETL pipeline to load both CSV files into database
**Dependencies**: Phases 1-3 complete
**Deliverables**:
- `scripts/load/load_sportsbook_odds.py` - Main ETL script
- Handles both `nba_2008-2025.csv` and `nba_main_lines.csv`
- Transforms data, normalizes team names, converts odds formats, identifies opening lines
- Error handling and logging

### Phase 5: ESPN Game Mapping (Duration: 2-3 hours)
**Objective**: Map odds records to ESPN game_ids
**Dependencies**: Phase 4 complete
**Deliverables**:
- ESPN game mapping logic in ETL pipeline
- 90%+ mapping accuracy
- Validation report

### Phase 6: Testing and Validation (Duration: 2-3 hours)
**Objective**: Test ETL pipeline on sample data and validate results
**Dependencies**: Phase 5 complete
**Deliverables**:
- ETL pipeline tested on sample games
- Data quality report (mapping accuracy, completeness)

### Phase 7: Canonical Dataset Integration (Duration: 2-3 hours)
**Objective**: Add opening odds to canonical snapshot dataset for model/grid search use
**Dependencies**: Phase 6 complete
**Deliverables**:
- Updated `derived.snapshot_features_v1` view (or create if not exists)
- Opening odds accessible for model training and grid search

### Phase 8: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 7 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Schema Extension
**Priority**: Critical (business justification: Required foundation for all odds data storage)
**Estimated Time**: 2 hours
**Dependencies**: Database access, migration system
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Extend Sportsbook Odds Schema
- **ID**: S1-E1-S1
- **Type**: Configuration
- **Priority**: Critical (required for opening line tracking)
- **Estimate**: 2 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Create**: 
  - `db/migrations/XXX_external_sportsbook_odds_schema_extend.sql` (where XXX is next migration number)
- **Files to Modify**: None
- **Dependencies**: PostgreSQL database, `scripts/migrate.py`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Migration file exists at `db/migrations/XXX_external_sportsbook_odds_schema_extend.sql`
  - [ ] Migration adds `is_opening_line BOOLEAN DEFAULT FALSE` column to `external.sportsbook_odds_snapshots`
  - [ ] Migration ensures `snapshot_timestamp` allows NULL (for historical single-date data)
  - [ ] Migration creates index `idx_sportsbook_odds_opening` on `(espn_game_id, is_opening_line)` with `WHERE is_opening_line = TRUE`
  - [ ] Migration runs successfully: `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run` shows no errors
  - [ ] Migration applies successfully: `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations` completes without errors
  - [ ] Column exists: `psql "$DATABASE_URL" -c "\d external.sportsbook_odds_snapshots"` shows `is_opening_line` column
  - [ ] Index exists: `psql "$DATABASE_URL" -c "\di external.idx_sportsbook_odds_opening"` shows index

- **Technical Context**:
  - **Current State**: Schema `external.sportsbook_odds_snapshots` exists (per `signal_improvement_next_steps_analysis.md`) but missing `is_opening_line` column. `snapshot_timestamp` may or may not allow NULL.
  - **Required Changes**: Add `is_opening_line` column, ensure `snapshot_timestamp` allows NULL, create index for opening lines queries
  - **Integration Points**: Schema used by ETL pipeline in Phase 4
  - **Data Structures**: PostgreSQL table schema
  - **API Contracts**: N/A (database schema only)

- **Implementation Steps**:
  1. **Determine next migration number**: Check `db/migrations/` directory for highest numbered migration file
  2. **Create migration file**: Create `db/migrations/XXX_external_sportsbook_odds_schema_extend.sql` where XXX is next number
  3. **Add column**: Include `ALTER TABLE external.sportsbook_odds_snapshots ADD COLUMN IF NOT EXISTS is_opening_line BOOLEAN DEFAULT FALSE;`
  4. **Allow NULL timestamp**: Include `ALTER TABLE external.sportsbook_odds_snapshots ALTER COLUMN snapshot_timestamp DROP NOT NULL;` (if needed)
  5. **Create index**: Include `CREATE INDEX IF NOT EXISTS idx_sportsbook_odds_opening ON external.sportsbook_odds_snapshots(espn_game_id, is_opening_line) WHERE is_opening_line = TRUE;`
  6. **Test migration**: Run `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run`
  7. **Apply migration**: Run `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations`

- **Validation Steps**:
  1. **Verify column exists**: `source .env && psql "$DATABASE_URL" -c "\d external.sportsbook_odds_snapshots" | grep is_opening_line`
     - Expected Output: `is_opening_line | boolean | default false`
  2. **Verify index exists**: `source .env && psql "$DATABASE_URL" -c "\di external.idx_sportsbook_odds_opening"`
     - Expected Output: Index listing showing `idx_sportsbook_odds_opening`
  3. **Verify NULL allowed**: `source .env && psql "$DATABASE_URL" -c "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema = 'external' AND table_name = 'sportsbook_odds_snapshots' AND column_name = 'snapshot_timestamp';"`
     - Expected Output: `snapshot_timestamp | YES` (or `snapshot_timestamp | NO` if already allows NULL)

- **Definition of Done**: 
  - [ ] Migration file created with correct SQL
  - [ ] Migration runs in dry-run mode without errors
  - [ ] Migration applies successfully
  - [ ] `is_opening_line` column exists in table
  - [ ] Index `idx_sportsbook_odds_opening` exists
  - [ ] `snapshot_timestamp` allows NULL

- **Rollback Plan**: 
  - Drop index: `DROP INDEX IF EXISTS external.idx_sportsbook_odds_opening;`
  - Drop column: `ALTER TABLE external.sportsbook_odds_snapshots DROP COLUMN IF EXISTS is_opening_line;`
  - Restore NOT NULL if needed: `ALTER TABLE external.sportsbook_odds_snapshots ALTER COLUMN snapshot_timestamp SET NOT NULL;` (only if it was NOT NULL before)

- **Risk Assessment**: 
  - **Risk**: Migration fails due to existing data conflicts
  - **Mitigation**: Use `IF NOT EXISTS` and `DROP NOT NULL` (safe operations)
  - **Risk**: Index creation is slow on large table
  - **Mitigation**: Index creation is O(n) but acceptable for one-time operation

- **Success Metrics**: 
  - **Functionality**: Schema supports opening line tracking
  - **Performance**: Index enables efficient opening line queries
  - **Quality**: Migration is idempotent and safe to re-run

---

### Epic 2: Team Name Normalization
**Priority**: High (business justification: Required for ESPN game mapping)
**Estimated Time**: 2-3 hours
**Dependencies**: Phase 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Create Team Name Mapping Library
- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: High (required for ESPN game mapping)
- **Estimate**: 2-3 hours (1h mapping dictionary, 1h normalization function, 30min testing)
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S1 (Schema Extension)
- **Files to Create**: 
  - `scripts/lib/team_name_mapping.py` (team normalization library)
- **Files to Modify**: None
- **Dependencies**: Python 3.x, `fuzzywuzzy` library (optional, for fuzzy matching)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] File exists at `scripts/lib/team_name_mapping.py`
  - [ ] File contains `TEAM_NAME_MAPPING` dictionary with all 30 NBA teams (full names → ESPN abbreviations)
  - [ ] File contains `normalize_team_name(name: str) -> str | None` function
  - [ ] Function handles exact matches (e.g., "Los Angeles Lakers" → "LAL")
  - [ ] Function handles abbreviations (e.g., "ny" → "NYK", "cle" → "CLE")
  - [ ] Function handles fuzzy matching (optional, if exact match fails)
  - [ ] Function returns `None` if no match found
  - [ ] Test script validates normalization on sample data from both CSV files
  - [ ] All 30 NBA teams can be normalized to ESPN abbreviations

- **Technical Context**:
  - **Current State**: No team name normalization library exists. CSV files use different formats: `nba_2008-2025.csv` uses abbreviations (ny, cle), `nba_main_lines.csv` uses full names (Houston Rockets).
  - **Required Changes**: Create mapping dictionary and normalization function that handles both formats and maps to ESPN abbreviations (LAL, BOS, etc.)
  - **Integration Points**: Used by ETL pipeline in Phase 4 for team name normalization
  - **Data Structures**: Dictionary mapping team names to ESPN abbreviations
  - **API Contracts**: Function signature: `normalize_team_name(name: str) -> str | None`

- **Implementation Steps**:
  1. **Create file**: Create `scripts/lib/team_name_mapping.py`
  2. **Add mapping dictionary**: Create `TEAM_NAME_MAPPING` with all 30 NBA teams (full names → ESPN abbreviations)
     - Include common variations (e.g., "Los Angeles Lakers", "L.A. Lakers", "Lakers" → "LAL")
     - Include abbreviations if known (e.g., "ny" → "NYK", "cle" → "CLE")
  3. **Implement normalization function**: Create `normalize_team_name(name: str) -> str | None`
     - Try exact match first (case-insensitive)
     - Try abbreviation match if exact match fails
     - Try fuzzy matching if both fail (optional, using `fuzzywuzzy` if available)
     - Return `None` if no match found
  4. **Add docstring**: Document function behavior and examples
  5. **Test on sample data**: Extract sample team names from both CSV files and test normalization

- **Validation Steps**:
  1. **Verify file exists**: `test -f scripts/lib/team_name_mapping.py && echo "File exists"`
     - Expected Output: `File exists`
  2. **Test exact match**: `python3 -c "from scripts.lib.team_name_mapping import normalize_team_name; print(normalize_team_name('Los Angeles Lakers'))"`
     - Expected Output: `LAL`
  3. **Test abbreviation**: `python3 -c "from scripts.lib.team_name_mapping import normalize_team_name; print(normalize_team_name('ny'))"`
     - Expected Output: `NYK` (or appropriate ESPN abbreviation)
  4. **Test no match**: `python3 -c "from scripts.lib.team_name_mapping import normalize_team_name; print(normalize_team_name('Invalid Team'))"`
     - Expected Output: `None`

- **Definition of Done**: 
  - [ ] File created with mapping dictionary and normalization function
  - [ ] Function handles exact matches, abbreviations, and fuzzy matching (if implemented)
  - [ ] Function tested on sample data from both CSV files
  - [ ] All 30 NBA teams can be normalized

- **Rollback Plan**: 
  - Delete file: `rm scripts/lib/team_name_mapping.py`
  - No database changes, so no rollback needed

- **Risk Assessment**: 
  - **Risk**: Team name variations not covered in mapping dictionary
  - **Mitigation**: Use fuzzy matching as fallback, log unmapped teams for manual review
  - **Risk**: Abbreviations in historical data don't match ESPN format
  - **Mitigation**: Verify sample data, add abbreviation mappings as needed

- **Success Metrics**: 
  - **Functionality**: 95%+ of team names from CSV files can be normalized
  - **Quality**: Normalization is accurate (verified by spot-checks)

---

### Epic 3: Odds Format Conversion
**Priority**: High (business justification: Required for unified odds storage)
**Estimated Time**: 1-2 hours
**Dependencies**: Phase 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Create Odds Conversion Library
- **ID**: S1-E3-S1
- **Type**: Feature
- **Priority**: High (required for odds format normalization)
- **Estimate**: 1-2 hours (1h conversion functions, 30min testing)
- **Phase**: Phase 3
- **Prerequisites**: S1-E2-S1 (Team Name Normalization)
- **Files to Create**: 
  - `scripts/lib/odds_conversion.py` (odds format conversion library)
- **Files to Modify**: None
- **Dependencies**: Python 3.x, `decimal` module (optional, for precision)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] File exists at `scripts/lib/odds_conversion.py`
  - [ ] File contains `american_to_decimal(american: int) -> float` function
  - [ ] File contains `decimal_to_american(decimal: float) -> int` function
  - [ ] File contains `calculate_implied_prob(decimal_odds: float) -> float` function
  - [ ] `american_to_decimal(-110)` returns `1.909...` (approximately 1.91)
  - [ ] `american_to_decimal(+150)` returns `2.5`
  - [ ] `decimal_to_american(1.91)` returns `-110` (approximately)
  - [ ] `decimal_to_american(2.5)` returns `150`
  - [ ] `calculate_implied_prob(2.0)` returns `0.5`
  - [ ] Conversion accuracy tested with spot-checks

- **Technical Context**:
  - **Current State**: No odds format conversion library exists. CSV files use different formats: `nba_2008-2025.csv` uses American odds (-450, +355), `nba_main_lines.csv` uses decimal odds (3.06, 1.392).
  - **Required Changes**: Create conversion functions to normalize odds formats for unified storage
  - **Integration Points**: Used by ETL pipeline in Phase 4 for odds format conversion
  - **Data Structures**: Functions for odds conversion
  - **API Contracts**: 
    - `american_to_decimal(american: int) -> float`
    - `decimal_to_american(decimal: float) -> int`
    - `calculate_implied_prob(decimal_odds: float) -> float`

- **Implementation Steps**:
  1. **Create file**: Create `scripts/lib/odds_conversion.py`
  2. **Implement American to Decimal**: Create `american_to_decimal(american: int) -> float`
     - Positive: `decimal = (american / 100) + 1`
     - Negative: `decimal = (100 / abs(american)) + 1`
  3. **Implement Decimal to American**: Create `decimal_to_american(decimal: float) -> int`
     - If decimal >= 2.0: `american = int((decimal - 1) * 100)`
     - If decimal < 2.0: `american = int(-100 / (decimal - 1))`
  4. **Implement Implied Probability**: Create `calculate_implied_prob(decimal_odds: float) -> float`
     - `implied_prob = 1 / decimal_odds`
  5. **Add docstring**: Document formulas and examples
  6. **Test conversions**: Test with known values (e.g., -110 → 1.909, +150 → 2.5)

- **Validation Steps**:
  1. **Verify file exists**: `test -f scripts/lib/odds_conversion.py && echo "File exists"`
     - Expected Output: `File exists`
  2. **Test American to Decimal**: `python3 -c "from scripts.lib.odds_conversion import american_to_decimal; print(round(american_to_decimal(-110), 2))"`
     - Expected Output: `1.91`
  3. **Test Decimal to American**: `python3 -c "from scripts.lib.odds_conversion import decimal_to_american; print(decimal_to_american(2.5))"`
     - Expected Output: `150`
  4. **Test Implied Probability**: `python3 -c "from scripts.lib.odds_conversion import calculate_implied_prob; print(calculate_implied_prob(2.0))"`
     - Expected Output: `0.5`

- **Definition of Done**: 
  - [ ] File created with all three conversion functions
  - [ ] Functions handle positive and negative American odds
  - [ ] Functions handle decimal odds >= 2.0 and < 2.0
  - [ ] Conversion accuracy verified with spot-checks

- **Rollback Plan**: 
  - Delete file: `rm scripts/lib/odds_conversion.py`
  - No database changes, so no rollback needed

- **Risk Assessment**: 
  - **Risk**: Rounding errors in conversion
  - **Mitigation**: Use appropriate precision, test with known values
  - **Risk**: Edge cases (e.g., odds = 0, very large odds)
  - **Mitigation**: Add input validation, handle edge cases

- **Success Metrics**: 
  - **Functionality**: Conversion functions work correctly for all test cases
  - **Quality**: Conversion accuracy > 99% (verified by spot-checks)

---

### Epic 4: ETL Pipeline Development
**Priority**: Critical (business justification: Core functionality for loading odds data)
**Estimated Time**: 8-12 hours
**Dependencies**: Phases 1-3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Build ETL Pipeline for Sportsbook Odds
- **ID**: S1-E4-S1
- **Type**: Feature
- **Priority**: Critical (core functionality)
- **Estimate**: 8-12 hours (2h structure, 1h CSV reading, 3-4h transformation, 1h opening line identification, 1-2h database insert, 1h error handling)
- **Phase**: Phase 4
- **Prerequisites**: S1-E1-S1 (Schema Extension), S1-E2-S1 (Team Name Normalization), S1-E3-S1 (Odds Conversion)
- **Files to Create**: 
  - `scripts/load/load_sportsbook_odds.py` (main ETL script)
- **Files to Modify**: None
- **Dependencies**: Python 3.x, `pandas`, `psycopg`, `scripts/lib/team_name_mapping.py`, `scripts/lib/odds_conversion.py`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] File exists at `scripts/load/load_sportsbook_odds.py`
  - [ ] Script can be run: `python scripts/load/load_sportsbook_odds.py --help` shows usage
  - [ ] Script reads `nba_2008-2025.csv`: `python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv --dry-run` completes without errors
  - [ ] Script reads `nba_main_lines.csv`: `python scripts/load/load_sportsbook_odds.py --source nba_main_lines --csv data/stats-csv/nba_main_lines.csv --dry-run` completes without errors
  - [ ] Script transforms data (odds conversion, team normalization)
  - [ ] Script identifies opening lines (earliest timestamp per game for Pinnacle data)
  - [ ] Script inserts into database: `python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv` inserts records
  - [ ] Records inserted have correct format (American and decimal odds, normalized team names, opening line flag)
  - [ ] Error handling logs errors and continues processing
  - [ ] Script supports `--dry-run` flag for testing

- **Technical Context**:
  - **Current State**: No ETL pipeline exists for loading sportsbook odds. CSV files contain raw data that needs transformation.
  - **Required Changes**: Create ETL pipeline that reads CSV files, transforms data (odds conversion, team normalization), identifies opening lines, and inserts into database
  - **Integration Points**: Uses team name mapping library, odds conversion library, database schema
  - **Data Structures**: 
    - Input: CSV files (`nba_2008-2025.csv`, `nba_main_lines.csv`)
    - Output: Database records in `external.sportsbook_odds_snapshots`
  - **API Contracts**: Command-line interface with flags: `--source`, `--csv`, `--dry-run`, `--dsn`

- **Implementation Steps**:
  1. **Create file**: Create `scripts/load/load_sportsbook_odds.py`
  2. **Add imports**: Import `pandas`, `psycopg`, `argparse`, `logging`, team mapping, odds conversion
  3. **Add argument parsing**: Parse `--source`, `--csv`, `--dry-run`, `--dsn` flags
  4. **Implement CSV reading**: Create `load_csv_file(csv_path: str) -> pd.DataFrame` function
  5. **Implement transformation for nba_2008_2025**: Create `transform_nba_2008_2025(df: pd.DataFrame) -> pd.DataFrame`
     - Normalize team names (abbreviations → ESPN abbreviations)
     - Convert American odds to decimal
     - Calculate implied probability
     - Set `is_opening_line = TRUE` (all rows are opening lines)
     - Set `snapshot_timestamp = NULL` (single date per game)
  6. **Implement transformation for nba_main_lines**: Create `transform_nba_main_lines(df: pd.DataFrame) -> pd.DataFrame`
     - Normalize team names (full names → ESPN abbreviations)
     - Convert decimal odds to American (if needed)
     - Calculate implied probability
     - Identify opening lines (earliest timestamp per game)
     - Set `is_opening_line = TRUE` for opening lines only
  7. **Implement opening line identification**: Create `identify_opening_lines(df: pd.DataFrame) -> pd.DataFrame`
     - Group by game (team1, team2, game_date)
     - Select earliest timestamp per game
     - Mark as opening line
  8. **Implement database insert**: Create `insert_odds_records(conn, df: pd.DataFrame) -> int`
     - Batch insert for performance
     - Handle duplicates (use `ON CONFLICT` if needed)
  9. **Add error handling**: Log errors, continue processing, report summary
  10. **Add main function**: Orchestrate CSV reading, transformation, opening line identification, database insert

- **Validation Steps**:
  1. **Verify file exists**: `test -f scripts/load/load_sportsbook_odds.py && echo "File exists"`
     - Expected Output: `File exists`
  2. **Test help**: `python scripts/load/load_sportsbook_odds.py --help`
     - Expected Output: Usage information
  3. **Test dry-run**: `source .env && python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv --dry-run`
     - Expected Output: Processing summary without database insert
  4. **Test actual load**: `source .env && python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv`
     - Expected Output: Records inserted, summary report
  5. **Verify records**: `source .env && psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM external.sportsbook_odds_snapshots WHERE source_dataset = 'nba_2008_2025';"`
     - Expected Output: Count of inserted records

- **Definition of Done**: 
  - [ ] File created with ETL pipeline
  - [ ] Script reads both CSV files
  - [ ] Script transforms data (odds conversion, team normalization)
  - [ ] Script identifies opening lines
  - [ ] Script inserts into database
  - [ ] Error handling implemented
  - [ ] Script tested on sample data

- **Rollback Plan**: 
  - Delete inserted records: `DELETE FROM external.sportsbook_odds_snapshots WHERE source_dataset = 'nba_2008_2025' OR source_dataset = 'nba_main_lines';`
  - Delete file: `rm scripts/load/load_sportsbook_odds.py`

- **Risk Assessment**: 
  - **Risk**: Large CSV files cause memory issues
  - **Mitigation**: Process in chunks, use batch inserts
  - **Risk**: Transformation errors cause data quality issues
  - **Mitigation**: Validate transformations, log errors, spot-check results

- **Success Metrics**: 
  - **Functionality**: Both CSV files can be loaded successfully
  - **Performance**: Load completes in reasonable time (< 30 minutes for full dataset)
  - **Quality**: Data transformations are accurate (verified by spot-checks)

---

### Epic 5: ESPN Game Mapping
**Priority**: High (business justification: Required for connecting odds to ESPN games)
**Estimated Time**: 2-3 hours
**Dependencies**: Phase 4 complete
**Status**: Not Started
**Phase Assignment**: Phase 5

#### Story 5.1: Implement ESPN Game Mapping
- **ID**: S1-E5-S1
- **Type**: Feature
- **Priority**: High (required for ESPN game connection)
- **Estimate**: 2-3 hours (1h mapping function, 1h integration, 1h validation)
- **Phase**: Phase 5
- **Prerequisites**: S1-E4-S1 (ETL Pipeline Development)
- **Files to Modify**: 
  - `scripts/load/load_sportsbook_odds.py` (add ESPN game mapping logic)
- **Files to Create**: None
- **Dependencies**: `espn.scoreboard_games` table, database connection

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] ETL pipeline includes `map_to_espn_game_id(conn, game_date: date, home_team: str, away_team: str) -> str | None` function
  - [ ] Function queries `espn.scoreboard_games` with date ±1 day and team matching
  - [ ] Function handles team name normalization (uses team mapping library)
  - [ ] Function returns `espn_game_id` if match found, `None` otherwise
  - [ ] ETL pipeline calls mapping function for each odds record
  - [ ] Mapping accuracy > 90% (verified by spot-checks)
  - [ ] Unmapped games are logged for manual review

- **Technical Context**:
  - **Current State**: ETL pipeline loads odds data but doesn't map to ESPN games. Odds records have `espn_game_id = NULL`.
  - **Required Changes**: Add ESPN game mapping logic to ETL pipeline. Map odds records to ESPN game_ids using date + team matching.
  - **Integration Points**: Uses `espn.scoreboard_games` table, team name mapping library
  - **Data Structures**: 
    - Input: `game_date`, `home_team`, `away_team` (normalized to ESPN abbreviations)
    - Output: `espn_game_id` (TEXT) or `None`
  - **API Contracts**: Function signature: `map_to_espn_game_id(conn, game_date: date, home_team: str, away_team: str) -> str | None`

- **Implementation Steps**:
  1. **Add mapping function**: Add `map_to_espn_game_id(conn, game_date: date, home_team: str, away_team: str) -> str | None` to ETL pipeline
  2. **Implement SQL query**: Query `espn.scoreboard_games` with date ±1 day and team matching
     - Use `DATE(event_date) BETWEEN game_date - INTERVAL '1 day' AND game_date + INTERVAL '1 day'`
     - Match teams: `(home_team_abbrev = home_team AND away_team_abbrev = away_team) OR (home_team_abbrev = away_team AND away_team_abbrev = home_team)`
  3. **Integrate into ETL pipeline**: Call mapping function for each odds record after team normalization
  4. **Update database insert**: Set `espn_game_id` in database insert
  5. **Add logging**: Log mapped and unmapped games
  6. **Add validation**: Spot-check mapping accuracy (20-30 games)

- **Validation Steps**:
  1. **Test mapping function**: `python3 -c "from scripts.load.load_sportsbook_odds import map_to_espn_game_id; import psycopg; conn = psycopg.connect('$DATABASE_URL'); print(map_to_espn_game_id(conn, '2024-10-22', 'LAL', 'BOS'))"`
     - Expected Output: ESPN game_id or `None`
  2. **Run ETL with mapping**: `source .env && python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv`
     - Expected Output: Mapping summary (X mapped, Y unmapped)
  3. **Verify mapped records**: `source .env && psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM external.sportsbook_odds_snapshots WHERE espn_game_id IS NOT NULL;"`
     - Expected Output: Count of mapped records
  4. **Check mapping accuracy**: Spot-check 20-30 games manually

- **Definition of Done**: 
  - [ ] Mapping function implemented
  - [ ] Mapping integrated into ETL pipeline
  - [ ] Mapping accuracy > 90%
  - [ ] Unmapped games logged for review

- **Rollback Plan**: 
  - Set `espn_game_id = NULL` for mapped records: `UPDATE external.sportsbook_odds_snapshots SET espn_game_id = NULL WHERE espn_game_id IS NOT NULL;`
  - Remove mapping function from ETL pipeline

- **Risk Assessment**: 
  - **Risk**: Low mapping accuracy due to team name mismatches
  - **Mitigation**: Use team name normalization, fuzzy date matching, log unmapped games
  - **Risk**: Multiple matches for same game (date + teams)
  - **Mitigation**: Use `LIMIT 1`, select closest date match

- **Success Metrics**: 
  - **Functionality**: 90%+ of odds records mapped to ESPN game_ids
  - **Quality**: Mapping accuracy verified by spot-checks

---

### Epic 6: Testing and Validation
**Priority**: High (business justification: Ensure data quality)
**Estimated Time**: 2-3 hours
**Dependencies**: Phase 5 complete
**Status**: Not Started
**Phase Assignment**: Phase 6

#### Story 6.1: Test and Validate ETL Pipeline
- **ID**: S1-E6-S1
- **Type**: Quality Assurance
- **Priority**: High (ensure data quality)
- **Estimate**: 2-3 hours (1h sample testing, 1h validation, 30min report)
- **Phase**: Phase 6
- **Prerequisites**: S1-E5-S1 (ESPN Game Mapping)
- **Files to Create**: 
  - `data/reports/sportsbook_odds_quality_report.json` (data quality report, optional)
- **Files to Modify**: None
- **Dependencies**: ETL pipeline, database, sample CSV data

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] ETL pipeline tested on sample games (10-20 games from each source)
  - [ ] Data quality checks pass:
    - [ ] Mapping accuracy > 90%
    - [ ] Odds conversion accuracy > 99% (spot-checked)
    - [ ] Opening line identification correct (spot-checked)
    - [ ] Team name normalization correct (spot-checked)
  - [ ] Data quality report generated (optional)
  - [ ] All validation checks documented

- **Technical Context**:
  - **Current State**: ETL pipeline implemented but not tested on full dataset
  - **Required Changes**: Test on sample data, validate data quality, generate report
  - **Integration Points**: ETL pipeline, database, CSV files
  - **Data Structures**: Data quality report (JSON or text)
  - **API Contracts**: N/A (testing only)

- **Implementation Steps**:
  1. **Extract sample games**: Extract 10-20 games from each CSV file for testing
  2. **Run ETL on samples**: Run ETL pipeline on sample games
  3. **Validate mapping accuracy**: Check ESPN game mapping (spot-check 20-30 games)
  4. **Validate odds conversion**: Spot-check odds conversion accuracy (10-20 conversions)
  5. **Validate opening line identification**: Spot-check opening line identification (10-20 games)
  6. **Validate team normalization**: Spot-check team name normalization (20-30 teams)
  7. **Generate quality report**: Create data quality report with metrics
  8. **Document findings**: Document any issues or improvements needed

- **Validation Steps**:
  1. **Run sample test**: `source .env && python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv --limit 20`
     - Expected Output: 20 games processed, summary report
  2. **Check mapping accuracy**: `source .env && psql "$DATABASE_URL" -c "SELECT COUNT(*) as mapped, COUNT(*) FILTER (WHERE espn_game_id IS NOT NULL) as total FROM external.sportsbook_odds_snapshots WHERE source_dataset = 'nba_2008_2025' LIMIT 20;"`
     - Expected Output: Mapping count and total
  3. **Spot-check odds conversion**: Manually verify 10-20 odds conversions
  4. **Spot-check opening lines**: Manually verify 10-20 opening line identifications

- **Definition of Done**: 
  - [ ] Sample testing complete
  - [ ] All data quality checks pass
  - [ ] Quality report generated (if applicable)
  - [ ] Findings documented

- **Rollback Plan**: 
  - Delete test records: `DELETE FROM external.sportsbook_odds_snapshots WHERE source_dataset = 'nba_2008_2025' OR source_dataset = 'nba_main_lines';`
  - Fix issues and re-test

- **Risk Assessment**: 
  - **Risk**: Data quality issues discovered
  - **Mitigation**: Fix issues before full load, document findings
  - **Risk**: Low mapping accuracy
  - **Mitigation**: Adjust mapping logic, improve team normalization

- **Success Metrics**: 
  - **Functionality**: All data quality checks pass
  - **Quality**: Mapping accuracy > 90%, odds conversion accuracy > 99%

---

### Epic 7: Canonical Dataset Integration
**Priority**: Medium (business justification: Enable model/grid search integration)
**Estimated Time**: 2-3 hours
**Dependencies**: Phase 6 complete
**Status**: Not Started
**Phase Assignment**: Phase 7

#### Story 7.1: Add Opening Odds to Canonical Snapshot Dataset
- **ID**: S1-E7-S1
- **Type**: Feature
- **Priority**: Medium (enables model/grid search integration)
- **Estimate**: 2-3 hours (1-2h view creation/update, 1h testing)
- **Phase**: Phase 7
- **Prerequisites**: S1-E6-S1 (Testing and Validation)
- **Files to Create**: 
  - `db/migrations/XXX_snapshot_features_v1_odds.sql` (or update existing view migration)
- **Files to Modify**: None (or update existing view migration if it exists)
- **Dependencies**: `espn.prob_event_state` view/table, `external.sportsbook_odds_snapshots` table

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Migration file exists (or existing view migration updated)
  - [ ] View `derived.snapshot_features_v1` includes opening odds columns:
    - [ ] `opening_moneyline_home` (decimal odds)
    - [ ] `opening_moneyline_away` (decimal odds)
    - [ ] `opening_spread` (line value)
    - [ ] `opening_total` (line value)
  - [ ] View joins `espn.prob_event_state` with `external.sportsbook_odds_snapshots` (opening lines only)
  - [ ] View query executes successfully: `SELECT * FROM derived.snapshot_features_v1 LIMIT 10;`
  - [ ] Opening odds columns populated for games with opening odds data
  - [ ] Opening odds columns are NULL for games without opening odds data
  - [ ] Query performance acceptable (< 1 second for typical queries)

- **Technical Context**:
  - **Current State**: Canonical snapshot dataset (`derived.snapshot_features_v1`) may or may not exist. Opening odds are not included.
  - **Required Changes**: Create or update view to include opening odds from `external.sportsbook_odds_snapshots` (opening lines only)
  - **Integration Points**: Joins `espn.prob_event_state` with `external.sportsbook_odds_snapshots`
  - **Data Structures**: SQL view with opening odds columns
  - **API Contracts**: View returns rows with opening odds columns

- **Implementation Steps**:
  1. **Check existing view**: Check if `derived.snapshot_features_v1` exists
  2. **Create/update migration**: Create `db/migrations/XXX_snapshot_features_v1_odds.sql` (or update existing)
  3. **Add opening odds joins**: Add LEFT JOINs to `external.sportsbook_odds_snapshots` for:
     - Home moneyline (`market_type = 'moneyline' AND side = 'home' AND is_opening_line = TRUE`)
     - Away moneyline (`market_type = 'moneyline' AND side = 'away' AND is_opening_line = TRUE`)
     - Spread (`market_type = 'spread' AND side = 'home' AND is_opening_line = TRUE`)
     - Total (`market_type = 'total' AND side = 'over' AND is_opening_line = TRUE`)
  4. **Add opening odds columns**: Add columns to SELECT:
     - `opening_moneyline_home` (from home moneyline join)
     - `opening_moneyline_away` (from away moneyline join)
     - `opening_spread` (from spread join)
     - `opening_total` (from total join)
  5. **Test view**: Run migration and test view query
  6. **Verify performance**: Check query performance for typical grid search queries

- **Validation Steps**:
  1. **Verify migration exists**: `test -f db/migrations/XXX_snapshot_features_v1_odds.sql && echo "Migration exists"`
     - Expected Output: `Migration exists`
  2. **Run migration**: `source .env && python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations`
     - Expected Output: Migration applies successfully
  3. **Test view query**: `source .env && psql "$DATABASE_URL" -c "SELECT game_id, opening_moneyline_home, opening_moneyline_away, opening_spread, opening_total FROM derived.snapshot_features_v1 LIMIT 10;"`
     - Expected Output: Rows with opening odds columns (some NULL, some populated)
  4. **Check performance**: `source .env && time psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL;"`
     - Expected Output: Query completes in < 1 second

- **Definition of Done**: 
  - [ ] View created/updated with opening odds columns
  - [ ] View query executes successfully
  - [ ] Opening odds columns populated for games with data
  - [ ] Query performance acceptable

- **Rollback Plan**: 
  - Drop view: `DROP VIEW IF EXISTS derived.snapshot_features_v1;`
  - Restore previous view definition if it existed

- **Risk Assessment**: 
  - **Risk**: View query performance is slow
  - **Mitigation**: Use indexes, consider materialized view if needed
  - **Risk**: Multiple opening odds records per game (data quality issue)
  - **Mitigation**: Use `DISTINCT ON` or aggregate if needed

- **Success Metrics**: 
  - **Functionality**: Opening odds accessible in canonical dataset
  - **Performance**: Query performance < 1 second for typical queries

---

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: SPRINT-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 8 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] **Backend documentation** updated if backend changes were made (ETL pipeline, libraries)
  - [ ] **API documentation** updated if API changes were made (N/A for this sprint)
  - [ ] **Deployment documentation** updated if deployment/infrastructure changes were made (N/A for this sprint)
  - [ ] **Architecture documentation** updated if architectural changes were made (schema extension, canonical dataset)
  - [ ] **User documentation** updated if user-facing features were changed (N/A for this sprint)
  - [ ] **Coding standards** updated if new patterns or practices were introduced (ETL patterns, odds conversion)

- **Technical Context**:
  - **Current State**: Documentation may not reflect new ETL pipeline, schema changes, or canonical dataset updates
  - **Required Changes**: Update relevant documentation to reflect sprint changes
  - **Integration Points**: README files, architecture docs, code comments

- **Implementation Steps**:
  1. Review all documentation files
  2. Update README if ETL pipeline usage documented
  3. Update architecture docs if schema changes documented
  4. Update code comments if needed
  5. Document ETL pipeline usage and examples

- **Validation Steps**:
  1. **Verify documentation updated**: Check relevant documentation files for updates
  2. **Verify examples work**: Test any code examples in documentation

- **Definition of Done**: 
  - [ ] All relevant documentation updated
  - [ ] Documentation is accurate and complete

---

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: SPRINT-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 8 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (MUST be 100% pass):
  - [ ] **Linting**: All linting checks pass with zero errors and zero warnings
  - [ ] **Type Checking**: All type checking passes with zero errors (if applicable)
  - [ ] **Unit Tests**: All unit tests pass (100% pass rate required) (if applicable)
  - [ ] **Integration Tests**: All integration tests pass (100% pass rate required) (if applicable)
  - [ ] **Build Process**: Build process completes without errors
  - [ ] **Code Formatting**: Code formatting is consistent
  - [ ] **Security**: No security vulnerabilities detected
  - [ ] **All acceptance criteria from previous stories verified as complete**

- **Technical Context**:
  - **Current State**: Code changes made during sprint need quality validation
  - **Required Changes**: Run quality checks, fix any issues
  - **Quality Gates**: Linting, type checking, tests, build, security

- **Implementation Steps**:
  1. Run linting checks on all modified files
  2. Run type checking (if applicable)
  3. Run unit tests (if applicable)
  4. Run integration tests (if applicable)
  5. Run build process
  6. Check code formatting
  7. Run security checks (if applicable)
  8. Fix any issues found
  9. Re-run quality checks until all pass

- **Validation Steps**:
  1. **Run linting**: `python -m pylint scripts/lib/team_name_mapping.py scripts/lib/odds_conversion.py scripts/load/load_sportsbook_odds.py` (or appropriate linter)
     - Expected Output: No errors, no warnings
  2. **Run type checking**: `python -m mypy scripts/lib/team_name_mapping.py scripts/lib/odds_conversion.py scripts/load/load_sportsbook_odds.py` (if mypy configured)
     - Expected Output: No errors
  3. **Run tests**: `python -m pytest tests/` (if tests exist)
     - Expected Output: All tests pass
  4. **Verify build**: Check that application builds/runs successfully

- **Definition of Done**: 
  - [ ] All quality gates pass (100% pass rate)
  - [ ] All previous story acceptance criteria verified

---

### Story [FINAL]: Sprint Completion and Archive
- **ID**: SPRINT-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 8 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] `completion-report.md` created with comprehensive sprint summary
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Sprint marked as completed
  - [ ] Any cross-references updated to point to completed location

- **Technical Context**:
  - **Current State**: Sprint work completed, needs final documentation and archiving
  - **Required Changes**: Create completion report, organize files, mark sprint as completed

- **Implementation Steps**:
  1. Create `completion-report.md` with sprint summary
  2. Document what was accomplished
  3. Document any issues or blockers
  4. Document next steps or follow-up work
  5. Organize sprint files
  6. Mark sprint as completed

- **Validation Steps**:
  1. **Verify completion report**: `test -f cursor-files/sprints/2026-01-13-sportsbook-odds-database-integration/completion-report.md && echo "Report exists"`
     - Expected Output: `Report exists`
  2. **Verify sprint files**: List sprint directory files
     - Expected Output: All sprint files present

- **Definition of Done**: 
  - [ ] Completion report created
  - [ ] Sprint files organized
  - [ ] Sprint marked as completed

---

## Technical Decisions

### Design Pattern Analysis

#### Design Pattern: ETL Pattern (Extract, Transform, Load)
- **Category**: Architectural
- **Intent**: Extract data from CSV files, transform to normalized schema, load into database
- **Implementation**: 
  - Extract: Read CSV files with `pandas.read_csv()`
  - Transform: Odds conversion, team normalization, opening line identification
  - Load: Insert into `external.sportsbook_odds_snapshots` table
- **Benefits**: 
  - Clear separation of concerns
  - Enables reprocessing if transformation logic changes
  - Standard pattern for data ingestion
- **Trade-offs**: 
  - Requires transformation logic for each source
  - May need schema updates for new sources
- **Rationale**: Standard approach for external data ingestion. Matches existing patterns in codebase (see `scripts/load/load_kalshi_markets.py`).

### Algorithm Analysis

#### Algorithm: Team Name Normalization with Fuzzy Matching
- **Type**: String Matching
- **Complexity**: Time O(1) for exact match, O(n) for fuzzy match where n = number of team mappings. Space O(n) for team mapping dictionary.
- **Description**: 
  - Primary: Exact dictionary lookup (team name → ESPN abbreviation)
  - Fallback: Fuzzy string matching (Levenshtein distance) if exact match fails
  - Threshold: 80% similarity for fuzzy match acceptance
- **Use Case**: Normalize team names from various formats (abbreviations, full names) to ESPN abbreviations
- **Performance**: 
  - Best Case: O(1) - exact dictionary match
  - Average Case: O(1) - most teams match exactly
  - Worst Case: O(n) - fuzzy matching required for all teams
  - Memory Usage: O(n) for team mapping dictionary (30 teams = constant space)

#### Algorithm: ESPN Game Mapping (Date + Team Matching)
- **Type**: Data Matching
- **Complexity**: Time O(n * log m) where n = odds records, m = ESPN games (with index optimization). Space O(m) for ESPN games lookup table.
- **Description**: 
  - Build lookup table: ESPN games indexed by date + teams
  - For each odds record:
    1. Normalize team names to ESPN abbreviations
    2. Query ESPN games: `WHERE event_date BETWEEN game_date - 1 day AND game_date + 1 day AND (home_team_abbrev, away_team_abbrev) = (team1, team2) OR (team2, team1)`
    3. Select best match (closest date, exact team match)
- **Use Case**: Map odds records to ESPN game_ids for joining with ESPN probabilities
- **Performance**: 
  - Best Case: O(n * log m) - indexed date + team lookup
  - Average Case: O(n * log m) - most games match exactly
  - Worst Case: O(n * m) - no index, full table scan
  - Memory Usage: O(m) for ESPN games lookup (can be optimized with database indexes)

### Design Decision Analysis

#### Design Decision: Unified Schema for Multiple Odds Data Sources
- **Problem**: Two CSV files with different formats (American vs decimal odds, abbreviations vs full names, single row vs time-series). Need unified schema to store both sources.
- **Context**: Must support opening line identification and ESPN game mapping. Must handle both data sources efficiently.
- **Project Scope**: Single sprint (2 weeks), 1 developer, medium complexity
- **Options**: 
  1. Separate tables per data source (rejected - doesn't enable unified querying)
  2. View-based transformation (rejected - query-time overhead)
  3. Unified schema with ETL transformation (CHOSEN - best balance of effort and benefit)
- **Selected**: Unified schema with ETL transformation
  - **Design Pattern**: ETL Pattern (Extract, Transform, Load)
  - **Algorithm**: Load-time transformation - O(n) where n = number of records (one-time cost)
  - **Implementation Complexity**: Medium (8-12 hours)
  - **Maintenance Overhead**: Low (1 hour/month)
  - **Scalability**: Good (can add new sources by extending ETL pipeline)
  - **Cost-Benefit**: Medium cost, high benefit (unified querying, normalized data, reusable pipeline)
  - **Over-Engineering Risk**: Low (appropriate solution for problem complexity)

**Pros**:
- **Unified Querying**: Single table enables efficient queries across all odds sources
- **Data Normalization**: Odds formats normalized at load time (no query-time conversion)
- **Reusable Pipeline**: ETL pipeline can handle additional sources
- **Maintainability**: Single table easier to maintain than multiple tables

**Cons**:
- **Transformation Complexity**: Requires transformation logic for each source
- **Load Time**: One-time transformation cost at load time

**Risk Assessment**: 
- **Data Quality Risk**: Transformation errors, mapping failures - mitigated by validation
- **Schema Evolution Risk**: New sources may require schema changes - mitigated by flexible schema design

---

## Testing Strategy

### Testing Approach
- **Unit Tests**: Test team name normalization and odds conversion functions with known inputs/outputs
- **Integration Tests**: Test ETL pipeline on sample data (10-20 games from each source)
- **E2E Tests**: Test full pipeline from CSV files to database to canonical dataset view
- **Performance Tests**: Verify query performance for canonical dataset view (< 1 second for typical queries)

---

## Deployment Plan
- **Pre-Deployment**: 
  - [ ] Schema migration tested in dry-run mode
  - [ ] ETL pipeline tested on sample data
  - [ ] Data quality validated
- **Deployment Steps**: 
  1. Run schema migration: `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations`
  2. Run ETL pipeline for `nba_2008-2025.csv`: `python scripts/load/load_sportsbook_odds.py --source nba_2008_2025 --csv data/stats-csv/nba_2008-2025.csv`
  3. Run ETL pipeline for `nba_main_lines.csv`: `python scripts/load/load_sportsbook_odds.py --source nba_main_lines --csv data/stats-csv/nba_main_lines.csv`
  4. Run canonical dataset migration: `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations`
- **Post-Deployment**: 
  - [ ] Verify data loaded: `SELECT COUNT(*) FROM external.sportsbook_odds_snapshots;`
  - [ ] Verify mapping accuracy: `SELECT COUNT(*) FROM external.sportsbook_odds_snapshots WHERE espn_game_id IS NOT NULL;`
  - [ ] Verify canonical dataset: `SELECT COUNT(*) FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL;`
- **Rollback Plan**: 
  - Delete odds records: `DELETE FROM external.sportsbook_odds_snapshots WHERE source_dataset = 'nba_2008_2025' OR source_dataset = 'nba_main_lines';`
  - Drop view: `DROP VIEW IF EXISTS derived.snapshot_features_v1;`
  - Revert schema migration if needed

---

## Risk Assessment
- **Technical Risks**: 
  - **ESPN Game Mapping Failures**: Medium probability, high impact - mitigated by fuzzy date matching, team normalization, logging
  - **Opening Line Identification Errors**: Low probability, medium impact - mitigated by earliest timestamp logic, spot-checks
  - **Data Quality Issues**: Medium probability, medium impact - mitigated by validation, spot-checks
- **Business Risks**: 
  - **Incomplete Coverage**: Low probability, low impact - mitigated by documenting gaps, using available data
- **Resource Risks**: 
  - **Time Overruns**: Medium probability, low impact - mitigated by phased approach, clear acceptance criteria

---

## Success Metrics
- **Technical**: 
  - Code quality maintained or improved
  - All quality gates pass (100% pass rate)
  - Query performance < 1 second for canonical dataset
- **Business**: 
  - Opening odds loaded for 95%+ of games in 2017-2025 range
  - 90%+ of odds records mapped to ESPN game_ids
  - Opening odds accessible in canonical snapshot dataset for grid search/model training
- **Sprint**: 
  - All stories completed according to acceptance criteria
  - Sprint completed within estimated time (16-24 hours)

---

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing (if applicable)
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)
- [ ] Schema migration applied successfully
- [ ] ETL pipeline tested on sample data
- [ ] Data quality validated
- [ ] Canonical dataset view created/updated
- [ ] Opening odds accessible for model/grid search use

### Post-Sprint Quality Comparison
- **Test Results**: [To be recorded after sprint completion]
- **Linting Results**: [To be recorded after sprint completion]
- **Code Coverage**: [To be recorded after sprint completion]
- **Build Status**: [To be recorded after sprint completion]
- **Overall Assessment**: [To be recorded after sprint completion]

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

