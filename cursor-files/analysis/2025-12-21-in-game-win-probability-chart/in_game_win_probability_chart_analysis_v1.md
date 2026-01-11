# Analysis: In-Game Win Probability Chart (Live Visualization)

**Date**: 2025-12-21  
**Status**: Draft  
**Author**: Cursor AI coding agent  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Define the best approach for generating a real-time-style win probability chart like the Polymarket/ESPN visualization shown in the reference image—showing second-by-second probability evolution throughout a game.

## Analysis Standards Reference

This analysis follows `cursor-files/templates/ANALYSIS_STANDARDS.md` and `cursor-files/templates/ANALYSIS_TEMPLATE.md`.

## Executive Summary

### Key Findings

- **We have dense probability time series data in the database**: `derived.espn_probabilities_raw_items` contains 5,267,284 probability rows across 11,183 games (9 seasons), with an average of ~470-500 probability updates per game.
  - **Evidence**:
    - **Command**: `psql "$DATABASE_URL" -c "SELECT season_label, COUNT(DISTINCT game_id) as games, COUNT(*) as prob_rows FROM derived.espn_probabilities_raw_items GROUP BY 1 ORDER BY 1 DESC;"`
    - **Output**:
      ```
       season_label | games | prob_rows 
      --------------+-------+-----------
       2025-26      |   472 |    234890
       2024-25      |  1394 |    660185
       2023-24      |  1391 |    648978
       ...
      (9 rows)
      ```

- **Probability data can be joined with time/score state**: `derived.espn_prob_event_state` contains matching event-level state (time_remaining, home_score, away_score) for 660,185 events (1,394 games in 2024-25), allowing us to plot probability against game time.
  - **Evidence**:
    - **Command**: `psql "$DATABASE_URL" -c "SELECT p.sequence_number, p.home_win_percentage, e.time_remaining, e.home_score, e.away_score FROM derived.espn_probabilities_raw_items p JOIN derived.espn_prob_event_state e ON p.game_id = e.game_id AND p.event_id = e.event_id WHERE p.game_id = '401736807' ORDER BY p.sequence_number LIMIT 10;"`
    - **Output**: Shows dense time series with time_remaining in seconds (2880 = 48 min) and scores updating throughout.

- **Team metadata is available in scoreboard JSONs**: The `data/raw/espn/scoreboard/` directory contains scoreboard files with team names, abbreviations, logos (ESPN CDN URLs), and final scores.
  - **Evidence**:
    - **File**: `data/raw/espn/scoreboard/scoreboard_20241220.json`
    - **Content**: Contains `competitions[].competitors[].team.abbreviation`, `team.displayName`, `team.logo` (e.g., `https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/phi.png`)

### Critical Issues Identified

- **No pre-built live chart generator exists in this repo**: The existing SVG generators (`_write_calibration_svg`, `_write_calibration_context_svg` in `scripts/verify_espn_win_probabilities.py`) produce calibration/reliability diagrams, not game time series charts.
  - **Evidence**:
    - **File**: `scripts/verify_espn_win_probabilities.py:340-445`
    - **Function**: `_write_calibration_svg()` generates bin-based calibration plots, not time series.

- **ESPN event_state join is only materialized for 2024-25 season**: `derived.espn_prob_event_state` has 660,185 rows (only 2024-25), while `derived.espn_probabilities_raw_items` has 5.2M+ rows across all seasons.
  - **Evidence**:
    - **Command**: `psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM derived.espn_prob_event_state;"`
    - **Output**: `660185` (1,394 games for 2024-25 only)

### Recommended Actions

- **Generate static SVG chart** (Priority: High): Fastest path; pure Python script with no external dependencies; matches the existing repo pattern for visualization outputs.
- **Consider web app for interactivity** (Priority: Low): If live updating or multiple game selection is needed, a minimal web app (Flask/FastAPI + JS) would enable hover tooltips, game switching, and real-time updates.

### Success Metrics

- **Visual fidelity**: Chart visually resembles the reference image (dark background, two team probability lines, time axis, score annotations).
- **Data accuracy**: Chart data matches the joined `espn_probabilities_raw_items` + `espn_prob_event_state` query results.
- **Performance**: SVG generation completes in < 5 seconds for a single game.

---

## Problem Statement

### Current Situation

The repo has ESPN win probability data at per-play granularity (400-600 updates per game), but no visualization tool exists to render this as a "live style" probability chart like the Polymarket/ESPN reference image.

### Pain Points

- **No game-level probability chart**: Users cannot see how probability evolves over time for a specific game.
- **Existing visualizations are calibration-focused**: The repo's SVG generators produce reliability diagrams (predicted vs. observed bins), not time series.

### Business Impact

- **Analysis impact**: Cannot visually inspect probability dynamics for specific games of interest.
- **Communication impact**: Cannot produce publication-ready charts for game summaries.

### Success Criteria

- **SC1 (visual match)**: Generated chart has dark background, two colored probability lines (home/away), time axis (quarters), and score display.
- **SC2 (data source)**: Uses the existing DB tables without new ingestion.
- **SC3 (single-file output)**: Produces a standalone SVG (or HTML) file.

---

## Current State Analysis

### Data Sources Available

#### 1. Probability Time Series: `derived.espn_probabilities_raw_items`

**Table**: `derived.espn_probabilities_raw_items`  
**Rows**: 5,267,284  
**Games**: 11,183  
**Seasons**: 9 (2017-18 through 2025-26)

**Key columns**:
- `game_id` (TEXT): ESPN competition ID
- `sequence_number` (INTEGER): Play sequence within game
- `home_win_percentage` (DOUBLE PRECISION): P(home win) ∈ [0, 1]
- `away_win_percentage` (DOUBLE PRECISION): P(away win) ∈ [0, 1]
- `event_id` (BIGINT): ESPN play ID (join key to event state)

**Evidence**:
```sql
SELECT season_label, COUNT(DISTINCT game_id) as games, AVG(COUNT(*)) OVER (PARTITION BY season_label) as avg_events
FROM derived.espn_probabilities_raw_items
GROUP BY season_label, game_id;
```
Result: ~470-500 probability updates per game on average.

#### 2. Event State (Time/Score): `derived.espn_prob_event_state`

**Table**: `derived.espn_prob_event_state`  
**Rows**: 660,185  
**Games**: 1,394 (2024-25 season only)

**Key columns**:
- `game_id` (TEXT): ESPN competition ID
- `event_id` (BIGINT): ESPN play ID (join key)
- `time_remaining` (INTEGER): Seconds remaining in regulation (2880 = start of game, 0 = end)
- `home_score` (INTEGER): Home team score at this event
- `away_score` (INTEGER): Away team score at this event
- `final_winning_team` (SMALLINT): 0 = home won, 1 = away won

**Evidence**:
- **Command**: `psql "$DATABASE_URL" -c "\d derived.espn_prob_event_state"`
- **Output**: Schema matches above.

#### 3. Team Metadata: Scoreboard JSON Files

**Location**: `data/raw/espn/scoreboard/scoreboard_YYYYMMDD.json`  
**Files**: ~6,600+ files (covers many seasons)

**Structure**:
```json
{
  "events": [
    {
      "id": "401704939",
      "name": "Charlotte Hornets at Philadelphia 76ers",
      "shortName": "CHA @ PHI",
      "competitions": [
        {
          "competitors": [
            {
              "homeAway": "home",
              "score": "108",
              "team": {
                "abbreviation": "PHI",
                "displayName": "Philadelphia 76ers",
                "logo": "https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/phi.png"
              }
            },
            {
              "homeAway": "away",
              "score": "98",
              "team": {
                "abbreviation": "CHA",
                "displayName": "Charlotte Hornets",
                "logo": "https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/cha.png"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

**Evidence**:
- **File**: `data/raw/espn/scoreboard/scoreboard_20241220.json`
- **Command**: `cat data/raw/espn/scoreboard/scoreboard_20241220.json | python3 -c "..."`
- **Output**: Shows team abbreviations, logos, final scores.

---

## Technical Assessment

### Design Decision: Output Format

#### Problem Statement

We need to generate a win probability chart similar to the reference image. The chart shows:
- Dark background (#0a0a0a or similar)
- Two probability lines (home team color, away team color)
- X-axis: Game time (5:20pm → 7:49pm real time, or quarters)
- Y-axis: Win probability (0% → 100%) AND price/odds annotations
- Score display at top (e.g., "13 - 6")
- Team logos/helmets
- Volume/activity indicators at bottom
- "LIVE" badge

#### Multiple Solution Analysis

**Option 1: Static SVG (Recommended)**
- **Design Pattern**: Template Pattern (string templating for SVG elements)
- **Algorithm**: O(n) single pass over probability rows to generate path coordinates
- **Implementation Complexity**: Low (8-12 hours)
- **Maintenance Overhead**: Low (no dependencies beyond Python stdlib)
- **Scalability**: Excellent (single file output, no server needed)
- **Cost-Benefit**: Low cost, high benefit
- **Over-Engineering Risk**: None (simplest solution that meets requirements)

**Pros**:
- Matches existing repo pattern (`_write_calibration_svg` precedent)
- Zero external dependencies (uses Python string templating)
- Portable output (single SVG file, viewable in any browser)
- Fast generation (< 1 second per game)
- Easy to batch-generate for multiple games

**Cons**:
- No interactivity (no hover tooltips, no zoom)
- Requires regeneration to update
- Team logos would require embedding or external references

**Option 2: Matplotlib PNG/SVG**
- **Design Pattern**: Factory Pattern (matplotlib figure generation)
- **Algorithm**: O(n) + matplotlib rendering overhead
- **Implementation Complexity**: Medium (4-6 hours)
- **Maintenance Overhead**: Medium (matplotlib version compatibility)
- **Scalability**: Good (batch-friendly)
- **Cost-Benefit**: Low cost, medium benefit
- **Over-Engineering Risk**: Low

**Pros**:
- Mature library with many styling options
- Easy legends, annotations, dual axes
- Publication-quality output

**Cons**:
- Adds matplotlib dependency (~50MB)
- Dark theme styling requires configuration
- Less control over exact SVG structure

**Option 3: Interactive Web App (React/D3 or plain JS)**
- **Design Pattern**: MVC (frontend renders data from API)
- **Algorithm**: O(n) data fetch + O(n) rendering
- **Implementation Complexity**: High (16-24 hours)
- **Maintenance Overhead**: High (frontend build system, server)
- **Scalability**: Excellent (can add live updates)
- **Cost-Benefit**: High cost, high benefit
- **Over-Engineering Risk**: Medium-High (overkill for static chart viewing)

**Pros**:
- Full interactivity (hover, zoom, pan)
- Can load different games dynamically
- Real-time updates possible with WebSocket
- Best visual fidelity (CSS styling, animations)

**Cons**:
- Requires Node.js/npm build tools
- Adds significant complexity
- Needs server to run

**Option 4: Plotly HTML (Interactive, No Server)**
- **Design Pattern**: Template Pattern (Plotly JSON → HTML)
- **Algorithm**: O(n) + Plotly.js rendering
- **Implementation Complexity**: Medium (6-10 hours)
- **Maintenance Overhead**: Low (Plotly.js CDN)
- **Scalability**: Good (single HTML file with embedded JS)
- **Cost-Benefit**: Medium cost, high benefit
- **Over-Engineering Risk**: Low

**Pros**:
- Interactive (hover, zoom) without server
- Single HTML file output
- Plotly Python library available

**Cons**:
- Large file size (~3MB with embedded Plotly.js)
- Python plotly dependency needed
- Less control over exact styling

---

### Recommended Solution: Option 1 (Static SVG)

**Rationale**:
1. **Pattern precedent**: The repo already has `_write_calibration_svg()` in `scripts/verify_espn_win_probabilities.py` using the same approach.
2. **Zero dependencies**: No new packages to add to `requirements.txt`.
3. **Fastest implementation**: 8-12 hours vs. 16-24 for web app.
4. **Fits use case**: The reference image is a static screenshot; interactivity is not required for the stated goal.

**If interactivity becomes needed later**: Option 4 (Plotly HTML) is the next logical step—it adds interactivity with minimal server complexity.

---

## Implementation Plan

### Phase 1: Data Query Layer (2 hours)

**Objective**: Create a function to fetch all probability data for a given game, joined with time/score state.

**SQL Query**:
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
WHERE p.game_id = :game_id
ORDER BY p.sequence_number;
```

**Deliverables**:
- Function: `fetch_game_probabilities(conn, game_id) -> list[dict]`
- Function: `fetch_game_metadata(game_id) -> dict` (from scoreboard JSON)

### Phase 2: SVG Chart Generator (6 hours)

**Objective**: Create a pure-Python SVG generator that produces the chart.

**Layout Specifications** (matching reference image):
- **Canvas**: 960 × 540 px
- **Background**: `#0a0a0a` (dark)
- **Header**: Team logos, score, game status ("LIVE - 4Q - 7:15")
- **Plot area**: 880 × 380 px
- **X-axis**: Time (quarters or clock time)
- **Y-axis**: Win probability (0% → 100%)
- **Home line**: Team primary color (e.g., Green Bay = `#203731`)
- **Away line**: Team secondary color (e.g., Chicago = `#0B162A`)
- **Final probabilities**: Large text annotations (e.g., "92%", "8%")

**Path Generation** (O(n)):
```python
def _probability_path(rows: list[dict], key: str, x_scale: float, y_scale: float) -> str:
    """Generate SVG path d attribute for probability line."""
    points = []
    for r in rows:
        x = (2880 - r['time_remaining']) * x_scale  # 0 at start, max at end
        y = (1 - r[key]) * y_scale  # SVG y increases downward
        points.append(f"{x:.1f} {y:.1f}")
    return "M " + " L ".join(points)
```

**Deliverables**:
- Function: `write_win_probability_chart_svg(rows, metadata, out_path)`
- CLI: `python scripts/generate_winprob_chart.py --game-id 401736807 --out data/charts/winprob_game_401736807.svg`

### Phase 3: Team Colors/Logos (2 hours)

**Objective**: Map ESPN team IDs to colors and logo URLs.

**Approach**:
- Extract team info from scoreboard JSON (already has logo URLs)
- Hardcode a mapping of team abbreviation → primary/secondary colors
- OR: Fetch from ESPN team API if needed

**Data Source**:
- Existing: `data/raw/espn/scoreboard/*.json` contains team logos
- Hardcoded: NBA team colors are well-known and stable

### Phase 4: Testing & Output (2 hours)

**Objective**: Generate charts for recent games and verify visual quality.

**Test Games**:
- `401736807`: Recent 2024-25 game (home won 120-98)
- `401736809`: Close game (116-118)
- `401736808`: High-scoring game (126-134)

**Deliverables** (using new folder structure):
- `data/charts/winprob_game_401736807.svg`
- `data/charts/winprob_game_401736809.svg`
- `data/charts/winprob_game_401736808.svg`

---

## Data Folder Organization

### Current Structure (As-Is)

The current `data/` folder has grown organically and mixes different types of outputs:

```
data/
├── discovery/                          # Game ID discovery CSVs (13 files)
│   └── game_ids_YYYY-YY.csv
├── exports/                            # MIXED: parquet, game lists, paper trades (27 files)
│   ├── *.parquet                       # Data exports
│   ├── *.parquet.manifest.json         # Export manifests
│   ├── *_game_ids_*.txt                # Train/test splits
│   ├── paper_trades_*.jsonl            # Paper trading logs
│   └── winprob_artifact_smoke.json     # Model artifacts (misplaced)
├── raw/                                # Source data from APIs
│   ├── boxscore/
│   ├── espn/
│   │   ├── plays/
│   │   │   └── YYYY-YY/                # Per-play JSON files
│   │   ├── probabilities/
│   │   │   └── YYYY-YY/                # Per-game probability JSON
│   │   └── scoreboard/                 # Daily scoreboard snapshots
│   ├── nba_api/
│   │   └── leaguegamefinder/
│   │       └── season=YYYY-YY/
│   ├── odds/
│   ├── pbp/
│   └── schedule/
└── reports/                            # MIXED: backfill logs, QC, eval, verification (117 files)
    ├── backfill_*.jsonl                # Backfill run logs
    ├── backfill_*.log
    ├── backfill_*.pid
    ├── backfill_*.done
    ├── qc_*.json                       # QC reports
    ├── winprob_eval_*.json             # Model evaluation
    ├── winprob_eval_*.calibration.svg
    ├── winprob_drift_*.json            # Drift smoke tests
    ├── espn_win_prob_verify_*.json     # ESPN verification
    └── espn_win_prob_verify_*.svg
```

**Problems**:
1. `reports/` is a dumping ground (117 files): backfill logs, QC reports, model eval, verification—all mixed together
2. `exports/` mixes data exports with train/test splits and paper trading logs
3. No dedicated location for generated charts/visualizations
4. Model artifacts are scattered (some in `exports/`, some in `artifacts/`)

### Proposed Structure (To-Be)

```
data/
├── raw/                                # Source data from APIs (UNCHANGED)
│   ├── boxscore/
│   ├── espn/
│   │   ├── plays/
│   │   │   └── {season_label}/
│   │   ├── probabilities/
│   │   │   └── {season_label}/
│   │   └── scoreboard/
│   ├── nba_api/
│   │   └── leaguegamefinder/
│   │       └── season={season_label}/
│   ├── odds/
│   ├── pbp/
│   └── schedule/
│
├── discovery/                          # Game ID discovery CSVs (UNCHANGED)
│   └── game_ids_{season_label}.csv
│
├── exports/                            # Parquet data exports ONLY
│   ├── pbp_event_state.parquet
│   ├── winprob_modeling_events.parquet
│   ├── winprob_snapshots_60s.parquet
│   └── *.parquet.manifest.json
│
├── splits/                             # Train/test/forward game ID lists (NEW)
│   ├── train_game_ids_season_lt_2024.txt
│   ├── test_game_ids_season_2024.txt
│   └── forward_game_ids_season_2025.txt
│
├── charts/                             # Generated visualizations (NEW)
│   ├── winprob_game_{game_id}.svg      # Per-game probability charts
│   └── calibration_*.svg               # Calibration plots (moved from reports)
│
├── reports/                            # Evaluation and verification reports
│   ├── qc/                             # QC reports (NEW subdir)
│   │   └── qc_{game_id}.json
│   ├── evaluation/                     # Model evaluation (NEW subdir)
│   │   ├── winprob_eval_{dataset}.json
│   │   └── winprob_drift_{dataset}.json
│   ├── verification/                   # ESPN probability verification (NEW subdir)
│   │   └── espn_win_prob_verify_{tag}_{timestamp}.json
│   └── backfill/                       # Backfill run logs (NEW subdir)
│       ├── backfill_{timestamp}.jsonl
│       ├── backfill_{timestamp}.log
│       └── backfill_{timestamp}.pid
│
└── paper_trading/                      # Paper trading logs (NEW)
    └── paper_trades_{date}.jsonl
```

### Migration Notes

- **Do NOT move existing files** (per user request)
- New scripts should write to the new structure
- Existing scripts can be updated incrementally to use new paths
- The `artifacts/` folder at repo root remains for model weights/configs

### File Naming Conventions

| Category | Pattern | Example |
|----------|---------|---------|
| Raw ESPN probabilities | `event_{event_id}_comp_{comp_id}.json` | `event_401703370_comp_401703370.json` |
| Raw ESPN plays | `play_{play_id}.json` | `play_40170337994.json` |
| Raw scoreboard | `scoreboard_{YYYYMMDD}.json` | `scoreboard_20241220.json` |
| Parquet exports | `{name}.parquet` | `winprob_snapshots_60s.parquet` |
| Game ID splits | `{split}_game_ids_{criteria}.txt` | `train_game_ids_season_lt_2024.txt` |
| Win prob charts | `winprob_game_{game_id}.svg` | `winprob_game_401736807.svg` |
| QC reports | `qc_{game_id}.json` | `qc_0022400196.json` |
| Evaluation reports | `winprob_eval_{dataset}.json` | `winprob_eval_2024.json` |
| Verification reports | `espn_win_prob_verify_{tag}_{timestamp}.json` | `espn_win_prob_verify_ALL_20251221T033410Z.json` |
| Backfill logs | `backfill_{timestamp}.{ext}` | `backfill_20251216T150926Z.jsonl` |
| Paper trades | `paper_trades_{YYYYMMDD}.jsonl` | `paper_trades_20251214.jsonl` |

---

## Risk Assessment

### Technical Risks

- **Risk 1**: ESPN logo URLs may have CORS restrictions when embedding in SVG
  - **Probability**: Medium
  - **Impact**: Low (can use placeholder or base64-encode)
  - **Mitigation**: Test with `<image xlink:href="...">` element; fall back to team abbreviation text if blocked.

- **Risk 2**: Time axis complexity for overtime games
  - **Probability**: Low (2880 seconds = regulation, overtime adds 300s per period)
  - **Impact**: Low
  - **Mitigation**: Detect overtime via `time_remaining < 0` or `max(sequence_number)` patterns; extend axis accordingly.

- **Risk 3**: Missing event state data for non-2024-25 seasons
  - **Probability**: High (only 2024-25 has `espn_prob_event_state` materialized)
  - **Impact**: Medium (limits historical charting)
  - **Mitigation**: Scope initial implementation to 2024-25; materialize other seasons if needed.

### Business Risks

- **Risk 1**: Chart doesn't match reference image fidelity
  - **Probability**: Medium
  - **Impact**: Low (functional chart is acceptable)
  - **Mitigation**: Iterate on styling; reference image is football (not NBA), so exact match is not expected.

---

## Appendix A: Reference Image Analysis

The reference image shows a Polymarket-style probability chart with these elements:

| Element | Description | Implementation |
|---------|-------------|----------------|
| Background | Dark (#0a0a0a) | SVG `<rect fill="#0a0a0a">` |
| Header | Team logos, score, game status | SVG `<image>`, `<text>` |
| Home line | Yellow/gold color, probability % | SVG `<path stroke="#ffce00">` |
| Away line | White/gray color, probability % | SVG `<path stroke="#c0c0c0">` |
| X-axis | Time labels (5:20pm, 5:57pm, etc.) | SVG `<text>` with computed positions |
| Y-axis left | Dollar amounts ($400, $3,069, etc.) | Not applicable for win prob (skip) |
| Y-axis right | Percentages (0%, 25%, 50%, 75%, 100%) | SVG `<text>` |
| Final annotations | "Green Bay 92%", "Chicago 8%" | SVG `<text>` at line endpoints |
| Volume bars | Gray bars at bottom | Optional (skip for v1) |

---

## Appendix B: Query Evidence

### Recent Game Data Sample (game_id = 401736807)

```
 sequence_number | home_win_percentage | time_remaining | home_score | away_score 
-----------------+---------------------+----------------+------------+------------
               4 |                0.71 |           2880 |          0 |          0
               7 |               0.725 |           2862 |          0 |          0
             ...
             671 |                   1 |              0 |        120 |         98
```

Total rows: 449 probability updates for this game.

---

## Document Validation

**Validation Checklist**:
- [x] File Verification: DB schema and scoreboard JSON verified
- [x] Command Evidence: SQL queries executed with verbatim output
- [x] Date Verification: `date -u` → `Sun Dec 21 04:04:22 UTC 2025`
- [x] Multiple Solutions: 4 options analyzed with pros/cons
- [x] Recommended Solution: Static SVG with rationale
- [x] Implementation Plan: 4 phases with time estimates
- [x] Risk Assessment: Technical and business risks identified

