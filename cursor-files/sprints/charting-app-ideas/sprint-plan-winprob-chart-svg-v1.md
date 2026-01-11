# Sprint Plan: Win Probability Chart SVG Generator

**Date**: 2025-12-21  
**Sprint Duration**: 2 days (12 hours total)  
**Sprint Goal**: Create a Python script that generates static SVG win probability charts for NBA games, matching the Polymarket-style visualization.  
**Current Status**: ESPN probability data exists in DB (`derived.espn_probabilities_raw_items` + `derived.espn_prob_event_state`); no chart generator exists.  
**Target Status**: CLI script generates publication-ready SVG charts for any game in 2024-25 season.  
**Team Size**: 1 developer  
**Sprint Lead**: TBD  

## Sprint Standards Reference

**Important**: This sprint follows `cursor-files/templates/SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence
- **Run Context**: Record UTC time and database state
- **File Verification**: Verify file contents directly
- **Database Verification**: PostgreSQL via `DATABASE_URL`
- **Document Placement**: Sprint plans live in `cursor-files/sprints/`

## Analysis Reference

This sprint implements the recommendations from:
- `cursor-files/analysis/in_game_win_probability_chart_analysis_v1.md`

## Git Usage Restrictions

**NO git commands** unless explicitly mentioned in this sprint plan.

---

## Sprint Overview

### Business Context

- **Business Driver**: Users need to visualize how win probability evolves throughout a game, similar to ESPN/Polymarket live charts.
- **Success Criteria**: Script generates an SVG that renders correctly in browsers and matches the dark-theme style of the reference image.
- **Stakeholders**: Data analysts, sports bettors reviewing game dynamics
- **Timeline Constraints**: None; this is a new feature.

### Technical Context

- **Current System State**:
  - `derived.espn_probabilities_raw_items`: 5.2M+ rows, 11,183 games, 9 seasons
  - `derived.espn_prob_event_state`: 660,185 rows (2024-25 season only)
  - `data/raw/espn/scoreboard/*.json`: Team metadata (names, logos)
  - No chart generation script exists

- **Target System State**:
  - New script: `scripts/generate_winprob_chart.py`
  - New output folder: `data/charts/`
  - Team colors mapping in script or config

- **Architecture Impact**: Minimal; adds one new script with no DB writes
- **Integration Points**: Reads from DB (read-only) and scoreboard JSON files

### Sprint Scope

- **In Scope**:
  - SVG chart generator for single-game probability time series
  - Dark theme styling (matching reference image)
  - Team colors for home/away lines
  - Score and final probability annotations
  - CLI interface with `--game-id` and `--out` options

- **Out of Scope**:
  - Interactive charts (hover, zoom)
  - Web app / server
  - Real-time updates
  - Overtime handling (v1 assumes regulation games)
  - Team logo embedding (v1 uses text abbreviations)

- **Assumptions**:
  - Target games are in 2024-25 season (where `espn_prob_event_state` is materialized)
  - ESPN scoreboard JSON exists for the game date

- **Constraints**:
  - Zero new Python dependencies (pure stdlib + psycopg)
  - Output must be standalone SVG (no external resources required)

---

## Sprint Phases

### Phase 1: Data Layer (Duration: 2 hours)

**Objective**: Create functions to fetch game probability data and team metadata.

**Dependencies**: PostgreSQL running, `.env` configured

**Deliverables**:
- `_fetch_game_probabilities(conn, game_id)` function
- `_fetch_game_metadata(game_id)` function

#### Tasks

- **Task 1.1**: Create probability query function
  - **Files**: `scripts/generate_winprob_chart.py` (new)
  - **Effort**: 1 hour
  - **Prerequisites**: None
  - **Validation**: Query returns 400-600 rows for test game `401736807`

- **Task 1.2**: Create metadata lookup function
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1.1
  - **Validation**: Returns team names, abbreviations, final score for test game

---

### Phase 2: SVG Generator Core (Duration: 4 hours)

**Objective**: Implement SVG generation with path rendering and styling.

**Dependencies**: Phase 1 complete

**Deliverables**:
- `_write_win_probability_chart_svg()` function
- Dark theme canvas with grid lines
- Two probability paths (home/away)

#### Tasks

- **Task 2.1**: Create SVG canvas and layout
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: None
  - **Validation**: Generates valid SVG with dark background

- **Task 2.2**: Implement probability path generation
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1.5 hours
  - **Prerequisites**: Task 2.1
  - **Validation**: SVG shows two colored lines from 0 to 100%

- **Task 2.3**: Add axes, grid lines, and labels
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1.5 hours
  - **Prerequisites**: Task 2.2
  - **Validation**: X-axis shows quarters (Q1, Q2, Q3, Q4); Y-axis shows 0%, 25%, 50%, 75%, 100%

---

### Phase 3: Styling and Annotations (Duration: 3 hours)

**Objective**: Add team colors, score header, and final probability annotations.

**Dependencies**: Phase 2 complete

**Deliverables**:
- NBA team color mapping
- Score header ("BOS 120 - 98 CHA")
- Final probability annotations ("92%", "8%")

#### Tasks

- **Task 3.1**: Create NBA team color mapping
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: None
  - **Validation**: All 30 NBA teams have primary color defined

- **Task 3.2**: Add score header and team names
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 3.1
  - **Validation**: Header shows "AWAY @ HOME" and final score

- **Task 3.3**: Add final probability annotations
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 3.2
  - **Validation**: Large text shows final probabilities at line endpoints

---

### Phase 4: CLI and Testing (Duration: 3 hours)

**Objective**: Create CLI interface and generate test charts.

**Dependencies**: Phase 3 complete

**Deliverables**:
- CLI with `--game-id`, `--out`, `--dsn` options
- `data/charts/` directory created
- 3 test SVG files generated

#### Tasks

- **Task 4.1**: Implement CLI with argparse
  - **Files**: `scripts/generate_winprob_chart.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Phase 3 complete
  - **Validation**: `python scripts/generate_winprob_chart.py --help` shows usage

- **Task 4.2**: Create output directory and generate test charts
  - **Files**: `data/charts/` (new directory)
  - **Effort**: 1 hour
  - **Prerequisites**: Task 4.1
  - **Validation**: 3 SVG files generated and viewable in browser

- **Task 4.3**: Documentation and cleanup
  - **Files**: `scripts/generate_winprob_chart.py` (docstrings)
  - **Effort**: 1 hour
  - **Prerequisites**: Task 4.2
  - **Validation**: Script has module docstring and `--help` is descriptive

---

## Sprint Backlog

### Epic 1: Win Probability Chart Generator

**Priority**: High  
**Estimated Time**: 12 hours  
**Dependencies**: PostgreSQL, ESPN probability data  
**Status**: Not Started  
**Phase Assignment**: Phases 1-4  

---

### Story 1.1: Data Query Layer

- **ID**: S1-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2 hours
- **Phase**: 1
- **Prerequisites**: None
- **Files to Create**: `scripts/generate_winprob_chart.py`
- **Dependencies**: `psycopg`, `_db_lib.py`

- **Acceptance Criteria**:
  - [ ] `_fetch_game_probabilities()` returns list of dicts with keys: `sequence_number`, `home_win_percentage`, `away_win_percentage`, `time_remaining`, `home_score`, `away_score`
  - [ ] `_fetch_game_metadata()` returns dict with keys: `home_team`, `away_team`, `home_abbr`, `away_abbr`, `final_home_score`, `final_away_score`
  - [ ] Query for game `401736807` returns ~449 probability rows

- **Technical Context**:
  - **SQL Query**:
    ```sql
    SELECT 
        p.sequence_number,
        p.home_win_percentage,
        p.away_win_percentage,
        e.time_remaining,
        e.home_score,
        e.away_score
    FROM derived.espn_probabilities_raw_items p
    JOIN derived.espn_prob_event_state e 
        ON p.game_id = e.game_id AND p.event_id = e.event_id
    WHERE p.game_id = %(game_id)s
    ORDER BY p.sequence_number;
    ```

- **Validation Steps**:
  1. `python -c "from scripts.generate_winprob_chart import _fetch_game_probabilities; ..."`
  2. Verify row count matches expected (~449 for test game)

---

### Story 1.2: SVG Canvas and Paths

- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4 hours
- **Phase**: 2
- **Prerequisites**: S1-E1-S1
- **Files to Modify**: `scripts/generate_winprob_chart.py`

- **Acceptance Criteria**:
  - [ ] SVG has dark background (`#0a0a0a`)
  - [ ] SVG canvas is 960 × 540 px
  - [ ] Two probability lines (home = team color, away = gray/white)
  - [ ] X-axis spans 0 to 2880 seconds (48 minutes)
  - [ ] Y-axis spans 0% to 100%

- **Technical Context**:
  - **Layout Constants**:
    ```python
    CANVAS_W = 960
    CANVAS_H = 540
    PAD_L = 60
    PAD_R = 80
    PAD_T = 80
    PAD_B = 50
    PLOT_W = CANVAS_W - PAD_L - PAD_R  # 820
    PLOT_H = CANVAS_H - PAD_T - PAD_B  # 410
    ```

- **Validation Steps**:
  1. Generate SVG for test game
  2. Open in browser; verify dark background and two lines

---

### Story 1.3: Team Colors and Header

- **ID**: S1-E1-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3 hours
- **Phase**: 3
- **Prerequisites**: S1-E1-S2
- **Files to Modify**: `scripts/generate_winprob_chart.py`

- **Acceptance Criteria**:
  - [ ] NBA_TEAM_COLORS dict contains all 30 teams
  - [ ] Header shows team abbreviations and final score
  - [ ] Final probability percentages displayed at line endpoints
  - [ ] Home team line uses team's primary color
  - [ ] Away team line uses white/light gray

- **Technical Context**:
  - **Team Colors** (sample):
    ```python
    NBA_TEAM_COLORS = {
        "ATL": "#E03A3E",  # Hawks red
        "BOS": "#007A33",  # Celtics green
        "BKN": "#000000",  # Nets black
        "CHA": "#1D1160",  # Hornets purple
        "CHI": "#CE1141",  # Bulls red
        # ... all 30 teams
    }
    ```

- **Validation Steps**:
  1. Generate SVG for BOS vs CHA game
  2. Verify BOS line is green, CHA line is light gray
  3. Verify header shows "CHA @ BOS  98 - 120"

---

### Story 1.4: CLI Interface

- **ID**: S1-E1-S4
- **Type**: Feature
- **Priority**: High
- **Estimate**: 2 hours
- **Phase**: 4
- **Prerequisites**: S1-E1-S3
- **Files to Modify**: `scripts/generate_winprob_chart.py`

- **Acceptance Criteria**:
  - [ ] CLI accepts `--game-id`, `--out`, `--dsn` arguments
  - [ ] `--dsn` defaults to `DATABASE_URL` env var
  - [ ] Script creates output directory if needed
  - [ ] Exit code 0 on success, non-zero on error

- **Technical Context**:
  - **Usage**:
    ```bash
    python scripts/generate_winprob_chart.py \
        --game-id 401736807 \
        --out data/charts/winprob_game_401736807.svg
    ```

- **Validation Steps**:
  1. `python scripts/generate_winprob_chart.py --help`
  2. Generate chart with default DSN
  3. Verify SVG file created at specified path

---

### Story 1.5: Test Chart Generation

- **ID**: S1-E1-S5
- **Type**: Testing
- **Priority**: High
- **Estimate**: 1 hour
- **Phase**: 4
- **Prerequisites**: S1-E1-S4
- **Files to Create**: `data/charts/` directory, 3 SVG files

- **Acceptance Criteria**:
  - [ ] `data/charts/` directory exists
  - [ ] `winprob_game_401736807.svg` generated (home blowout)
  - [ ] `winprob_game_401736809.svg` generated (close game)
  - [ ] `winprob_game_401736808.svg` generated (high-scoring)
  - [ ] All 3 SVGs render correctly in browser

- **Validation Steps**:
  ```bash
  mkdir -p data/charts
  python scripts/generate_winprob_chart.py --game-id 401736807 --out data/charts/winprob_game_401736807.svg
  python scripts/generate_winprob_chart.py --game-id 401736809 --out data/charts/winprob_game_401736809.svg
  python scripts/generate_winprob_chart.py --game-id 401736808 --out data/charts/winprob_game_401736808.svg
  ls -la data/charts/
  ```

---

## Technical Decisions

### Design Pattern: Template Pattern

- **Category**: Structural
- **Intent**: Generate SVG by concatenating templated string parts
- **Implementation**: List of SVG element strings joined at end
- **Benefits**: No external dependencies, full control over output
- **Trade-offs**: More verbose than using a library
- **Rationale**: Matches existing pattern in `scripts/verify_espn_win_probabilities.py`

### Algorithm: Linear Path Generation

- **Type**: Transformation
- **Complexity**: O(n) time, O(n) space for path string
- **Description**: Single pass over probability rows to generate SVG path `d` attribute
- **Use Case**: Convert (time_remaining, probability) pairs to (x, y) pixel coordinates
- **Performance**: < 1ms for 500 rows

---

## Risk Assessment

### Technical Risks

- **Risk 1**: Game not in `espn_prob_event_state` (non-2024-25 season)
  - **Probability**: High for historical games
  - **Impact**: Script fails with no data
  - **Mitigation**: Validate game exists before querying; show clear error message

- **Risk 2**: Scoreboard JSON not found for game date
  - **Probability**: Low (6,600+ scoreboard files exist)
  - **Impact**: Missing team names in header
  - **Mitigation**: Fall back to team IDs or "HOME" / "AWAY" labels

### Business Risks

- **Risk 1**: Chart doesn't match reference fidelity
  - **Probability**: Medium
  - **Impact**: Low (functional chart is acceptable)
  - **Mitigation**: Iterate on styling post-sprint

---

## Success Metrics

- **Technical**:
  - Script runs without errors for test games
  - SVG file size < 100KB per game
  - Generation time < 2 seconds per game

- **Quality**:
  - SVG renders correctly in Chrome, Firefox, Safari
  - No lint errors in script
  - Type hints for all functions

---

## Sprint Completion Checklist

- [ ] `scripts/generate_winprob_chart.py` created and documented
- [ ] `data/charts/` directory created
- [ ] 3 test SVG files generated and verified
- [ ] Script has `--help` documentation
- [ ] All acceptance criteria met for stories S1-E1-S1 through S1-E1-S5

---

## Appendix: Reference SQL Queries

### Fetch game probability time series

```sql
SELECT 
    p.sequence_number,
    p.home_win_percentage,
    p.away_win_percentage,
    e.time_remaining,
    e.home_score,
    e.away_score
FROM derived.espn_probabilities_raw_items p
JOIN derived.espn_prob_event_state e 
    ON p.game_id = e.game_id AND p.event_id = e.event_id
WHERE p.game_id = %(game_id)s
ORDER BY p.sequence_number;
```

### Find recent games with data

```sql
SELECT 
    p.game_id,
    MAX(e.home_score) FILTER (WHERE e.time_remaining <= 0) as final_home,
    MAX(e.away_score) FILTER (WHERE e.time_remaining <= 0) as final_away,
    COUNT(*) as prob_count
FROM derived.espn_probabilities_raw_items p
JOIN derived.espn_prob_event_state e ON p.game_id = e.game_id AND p.event_id = e.event_id
WHERE p.season_label = '2024-25'
GROUP BY p.game_id
HAVING MAX(e.home_score) > 80
ORDER BY MAX(p.created_at) DESC
LIMIT 10;
```

---

## Document Validation

**Checklist**:
- [x] Sprint goal is specific and measurable
- [x] All stories have acceptance criteria
- [x] Technical context includes code examples
- [x] Validation steps are executable commands
- [x] Risk assessment included
- [x] No git commands unless explicitly needed (none in this sprint)







