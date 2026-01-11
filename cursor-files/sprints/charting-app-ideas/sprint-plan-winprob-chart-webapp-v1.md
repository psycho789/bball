# Sprint Plan: Win Probability Chart Interactive Web App

**Date**: 2025-12-21  
**Sprint Duration**: 5 days (40 hours total)  
**Sprint Goal**: Create an interactive web application that displays Polymarket-style win probability charts for NBA games with real-time-like visualization, game selection, and hover tooltips.  
**Current Status**: ESPN probability data exists in DB; static SVG sprint planned separately; no web app exists.  
**Target Status**: Single-page web app with FastAPI backend + JavaScript frontend displaying interactive probability charts.  
**Team Size**: 1 developer  
**Sprint Lead**: TBD  

## Sprint Standards Reference

**Important**: This sprint follows `cursor-files/templates/SPRINT_STANDARDS.md`.

## Analysis Reference

This sprint implements the interactive Option 3/4 from:
- `cursor-files/analysis/in_game_win_probability_chart_analysis_v1.md`

## Git Usage Restrictions

**NO git commands** unless explicitly mentioned in this sprint plan.

---

## Executive Summary

### Why a Web App?

The reference image (Polymarket-style chart) has these interactive features that SVG alone cannot provide:
- **Hover tooltips** showing exact values at any point
- **Game selection dropdown** to switch between games
- **Real-time updates** (or simulated playback)
- **Responsive design** that adapts to screen size
- **Smooth animations** on data transitions

### Recommended Library: Lightweight Charts (TradingView)

After evaluating options, **TradingView's Lightweight Charts** is the best fit:

| Library | Pros | Cons | Fit |
|---------|------|------|-----|
| **Lightweight Charts** | Purpose-built for financial charts, dark theme native, ~40KB, excellent performance | Limited chart types (line/area/candlestick only) | ✅ **Best** |
| D3.js | Maximum flexibility, huge ecosystem | Steep learning curve, verbose code | Good |
| Chart.js | Easy to use, popular | Less suited for trading-style charts | OK |
| Recharts (React) | Nice React integration | Requires React, heavier | OK |
| Plotly.js | Interactive out of box | Large bundle (~3MB), opinionated | OK |

**Why Lightweight Charts?**
1. **Built for exactly this use case** - financial/trading time series with dark themes
2. **Native dark theme** - matches reference image aesthetics
3. **Tiny bundle** - ~40KB minified vs. 200KB+ for alternatives
4. **No framework dependency** - works with vanilla JS or any framework
5. **Polymarket likely uses this or similar** - the visual style matches perfectly

---

## Technical Architecture

### Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  index.html                                              ││
│  │  ├── Game selector dropdown                             ││
│  │  ├── Lightweight Charts container                        ││
│  │  │   ├── Home team line (team color)                    ││
│  │  │   └── Away team line (white/gray)                    ││
│  │  ├── Score header (team logos, score, status)           ││
│  │  └── Final probability annotations                      ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           │ fetch('/api/games/{id}/probs')   │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  GET /api/games                    → List recent games   ││
│  │  GET /api/games/{game_id}/probs   → Probability series  ││
│  │  GET /api/games/{game_id}/meta    → Team info, score    ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           │ psycopg                          │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  PostgreSQL                                              ││
│  │  ├── derived.espn_probabilities_raw_items               ││
│  │  └── derived.espn_prob_event_state                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### File Structure (New)

```
bball/
├── webapp/                              # NEW: Web application
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                      # FastAPI app
│   ├── static/
│   │   ├── index.html                   # Single-page app
│   │   ├── app.js                       # Chart logic
│   │   └── style.css                    # Dark theme styles
│   └── README.md                        # Setup instructions
└── requirements.txt                     # Add: fastapi, uvicorn
```

---

## Library Details

### Lightweight Charts (TradingView)

**NPM Package**: `lightweight-charts`  
**CDN**: `https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js`  
**Size**: ~40KB minified  
**License**: Apache 2.0  
**Docs**: https://tradingview.github.io/lightweight-charts/

**Key Features**:
- `createChart()` - Create chart instance
- `chart.addLineSeries()` - Add probability line
- `chart.addAreaSeries()` - Add filled area (optional)
- `series.setData()` - Set time series data
- `chart.subscribeCrosshairMove()` - Hover events
- Built-in dark theme via `layout.background.color`

**Data Format**:
```javascript
// Lightweight Charts expects {time, value} objects
const data = [
  { time: 0, value: 0.71 },      // Game start
  { time: 100, value: 0.68 },    // After 100 seconds
  { time: 200, value: 0.75 },
  // ...
  { time: 2880, value: 1.0 }     // Game end (48 min)
];
series.setData(data);
```

### FastAPI Backend

**Why FastAPI?**
- Already familiar pattern in Python ecosystem
- Automatic OpenAPI docs
- Async support for DB queries
- Zero config CORS

**Endpoints**:
```python
@app.get("/api/games")
async def list_games(season: str = "2024-25", limit: int = 20):
    """Return recent games with probability data."""

@app.get("/api/games/{game_id}/probs")
async def get_game_probabilities(game_id: str):
    """Return probability time series for chart."""

@app.get("/api/games/{game_id}/meta")
async def get_game_metadata(game_id: str):
    """Return team names, colors, final score."""
```

---

## Sprint Phases

### Phase 1: Backend API (Duration: 8 hours)

**Objective**: Create FastAPI endpoints serving game data from PostgreSQL.

**Dependencies**: PostgreSQL, fastapi, uvicorn, psycopg

**Deliverables**:
- `webapp/api/main.py` with 3 endpoints
- API returns JSON matching Lightweight Charts format

#### Tasks

- **Task 1.1**: Set up FastAPI project structure
  - **Files**: `webapp/api/__init__.py`, `webapp/api/main.py`
  - **Effort**: 2 hours
  - **Prerequisites**: None
  - **Validation**: `uvicorn webapp.api.main:app --reload` starts server

- **Task 1.2**: Implement `/api/games` endpoint
  - **Files**: `webapp/api/main.py`
  - **Effort**: 2 hours
  - **Prerequisites**: Task 1.1
  - **Validation**: `curl localhost:8000/api/games` returns JSON list

- **Task 1.3**: Implement `/api/games/{game_id}/probs` endpoint
  - **Files**: `webapp/api/main.py`
  - **Effort**: 2 hours
  - **Prerequisites**: Task 1.2
  - **Validation**: Returns ~450 data points for test game

- **Task 1.4**: Implement `/api/games/{game_id}/meta` endpoint
  - **Files**: `webapp/api/main.py`
  - **Effort**: 2 hours
  - **Prerequisites**: Task 1.3
  - **Validation**: Returns team names, colors, final score

---

### Phase 2: Frontend Chart (Duration: 12 hours)

**Objective**: Create interactive chart using Lightweight Charts.

**Dependencies**: Phase 1 complete, Lightweight Charts CDN

**Deliverables**:
- `webapp/static/index.html` with chart container
- `webapp/static/app.js` with chart initialization
- Two probability lines (home/away) rendering correctly

#### Tasks

- **Task 2.1**: Create HTML scaffold and load Lightweight Charts
  - **Files**: `webapp/static/index.html`
  - **Effort**: 2 hours
  - **Prerequisites**: None
  - **Validation**: Page loads, chart container visible

- **Task 2.2**: Initialize chart with dark theme
  - **Files**: `webapp/static/app.js`
  - **Effort**: 3 hours
  - **Prerequisites**: Task 2.1
  - **Validation**: Empty dark chart renders

- **Task 2.3**: Fetch and render probability data
  - **Files**: `webapp/static/app.js`
  - **Effort**: 4 hours
  - **Prerequisites**: Task 2.2, Phase 1
  - **Validation**: Two lines show probability over time

- **Task 2.4**: Add hover crosshair and tooltip
  - **Files**: `webapp/static/app.js`
  - **Effort**: 3 hours
  - **Prerequisites**: Task 2.3
  - **Validation**: Hovering shows exact values

---

### Phase 3: Styling and Polish (Duration: 12 hours)

**Objective**: Match Polymarket visual style with score header, team colors, annotations.

**Dependencies**: Phase 2 complete

**Deliverables**:
- Score header with team names and score
- Team-colored lines
- Final probability percentage annotations
- Game selector dropdown

#### Tasks

- **Task 3.1**: Create CSS dark theme styles
  - **Files**: `webapp/static/style.css`
  - **Effort**: 3 hours
  - **Prerequisites**: None
  - **Validation**: Dark background `#0a0a0a`, white text

- **Task 3.2**: Add score header component
  - **Files**: `webapp/static/index.html`, `webapp/static/app.js`
  - **Effort**: 3 hours
  - **Prerequisites**: Task 3.1
  - **Validation**: Header shows "CHA @ BOS  98 - 120"

- **Task 3.3**: Implement game selector dropdown
  - **Files**: `webapp/static/index.html`, `webapp/static/app.js`
  - **Effort**: 3 hours
  - **Prerequisites**: Task 3.2
  - **Validation**: Dropdown lists games, selecting loads new chart

- **Task 3.4**: Add final probability annotations
  - **Files**: `webapp/static/app.js`, `webapp/static/style.css`
  - **Effort**: 3 hours
  - **Prerequisites**: Task 3.3
  - **Validation**: Large "92%" / "8%" text at line endpoints

---

### Phase 4: Testing and Documentation (Duration: 8 hours)

**Objective**: Test across browsers, document setup, create demo.

**Dependencies**: Phase 3 complete

**Deliverables**:
- `webapp/README.md` with setup instructions
- Test results for Chrome, Firefox, Safari
- 3 demo screenshots

#### Tasks

- **Task 4.1**: Cross-browser testing
  - **Files**: None (testing)
  - **Effort**: 3 hours
  - **Prerequisites**: Phase 3 complete
  - **Validation**: Chart works in Chrome, Firefox, Safari

- **Task 4.2**: Write README documentation
  - **Files**: `webapp/README.md`
  - **Effort**: 2 hours
  - **Prerequisites**: Task 4.1
  - **Validation**: README covers setup, running, API docs

- **Task 4.3**: Performance testing
  - **Files**: None (testing)
  - **Effort**: 2 hours
  - **Prerequisites**: Task 4.1
  - **Validation**: Chart renders in < 500ms for 500 data points

- **Task 4.4**: Generate demo screenshots
  - **Files**: `webapp/static/demo/` (screenshots)
  - **Effort**: 1 hour
  - **Prerequisites**: Task 4.1
  - **Validation**: 3 screenshots showing different games

---

## Sprint Backlog

### Epic 1: Win Probability Chart Web App

**Priority**: High  
**Estimated Time**: 40 hours  
**Dependencies**: PostgreSQL, ESPN probability data, fastapi, uvicorn  
**Status**: Not Started  

---

### Story 1.1: FastAPI Backend

- **ID**: S1-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 8 hours
- **Phase**: 1
- **Prerequisites**: None
- **Files to Create**: 
  - `webapp/api/__init__.py`
  - `webapp/api/main.py`
- **Dependencies**: fastapi, uvicorn, psycopg

- **Acceptance Criteria**:
  - [ ] `GET /api/games` returns list of recent games with `game_id`, `home_team`, `away_team`, `final_score`
  - [ ] `GET /api/games/{game_id}/probs` returns array of `{time, home_prob, away_prob, home_score, away_score}`
  - [ ] `GET /api/games/{game_id}/meta` returns `{home_team, away_team, home_color, away_color, final_home_score, final_away_score}`
  - [ ] CORS enabled for local development
  - [ ] Automatic OpenAPI docs at `/docs`

- **Technical Context**:
  ```python
  # webapp/api/main.py
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  from fastapi.staticfiles import StaticFiles
  import psycopg
  import os

  app = FastAPI(title="Win Probability Chart API")

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_methods=["GET"],
  )

  def get_db():
      return psycopg.connect(os.environ["DATABASE_URL"])

  @app.get("/api/games")
  def list_games(season: str = "2024-25", limit: int = 20):
      # Query derived.espn_probabilities_raw_items for distinct games
      ...

  @app.get("/api/games/{game_id}/probs")
  def get_probabilities(game_id: str):
      # Join espn_probabilities_raw_items with espn_prob_event_state
      ...
  ```

- **Validation Steps**:
  ```bash
  cd webapp && uvicorn api.main:app --reload
  curl http://localhost:8000/api/games
  curl http://localhost:8000/api/games/401736807/probs
  curl http://localhost:8000/api/games/401736807/meta
  ```

---

### Story 1.2: Lightweight Charts Integration

- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 12 hours
- **Phase**: 2
- **Prerequisites**: S1-E1-S1
- **Files to Create**:
  - `webapp/static/index.html`
  - `webapp/static/app.js`
- **Dependencies**: Lightweight Charts CDN

- **Acceptance Criteria**:
  - [ ] Chart renders with dark background `#0a0a0a`
  - [ ] Home team probability line in team primary color
  - [ ] Away team probability line in white/light gray
  - [ ] X-axis shows game time (0 → 48 minutes or Q1 → Q4)
  - [ ] Y-axis shows 0% → 100%
  - [ ] Crosshair shows on hover with exact values
  - [ ] Tooltip displays time, score, and probabilities

- **Technical Context**:
  ```html
  <!-- webapp/static/index.html -->
  <!DOCTYPE html>
  <html>
  <head>
    <title>Win Probability Chart</title>
    <link rel="stylesheet" href="style.css">
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
  </head>
  <body>
    <div id="header">
      <span id="away-team"></span>
      <span id="score"></span>
      <span id="home-team"></span>
    </div>
    <div id="chart"></div>
    <script src="app.js"></script>
  </body>
  </html>
  ```

  ```javascript
  // webapp/static/app.js
  const chart = LightweightCharts.createChart(document.getElementById('chart'), {
    width: 960,
    height: 500,
    layout: {
      background: { type: 'solid', color: '#0a0a0a' },
      textColor: '#d1d4dc',
    },
    grid: {
      vertLines: { color: '#1a1a1a' },
      horzLines: { color: '#1a1a1a' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    timeScale: {
      timeVisible: false,
      secondsVisible: false,
    },
  });

  const homeSeries = chart.addLineSeries({
    color: '#007A33',  // Team color (dynamic)
    lineWidth: 2,
  });

  const awaySeries = chart.addLineSeries({
    color: '#808080',  // Gray for away
    lineWidth: 2,
  });

  // Fetch and render
  async function loadGame(gameId) {
    const resp = await fetch(`/api/games/${gameId}/probs`);
    const data = await resp.json();
    
    const homeData = data.map(d => ({ time: d.time, value: d.home_prob }));
    const awayData = data.map(d => ({ time: d.time, value: d.away_prob }));
    
    homeSeries.setData(homeData);
    awaySeries.setData(awayData);
  }

  loadGame('401736807');
  ```

- **Validation Steps**:
  1. Open `http://localhost:8000/` in browser
  2. Verify dark chart renders
  3. Verify two lines show probability evolution
  4. Hover over chart to see crosshair + values

---

### Story 1.3: Visual Styling and Annotations

- **ID**: S1-E1-S3
- **Type**: Feature
- **Priority**: High
- **Estimate**: 12 hours
- **Phase**: 3
- **Prerequisites**: S1-E1-S2
- **Files to Create**: `webapp/static/style.css`
- **Files to Modify**: `webapp/static/index.html`, `webapp/static/app.js`

- **Acceptance Criteria**:
  - [ ] Dark theme matches reference image (`#0a0a0a` background)
  - [ ] Score header shows "AWAY @ HOME  XX - XX"
  - [ ] Game selector dropdown lists recent games
  - [ ] Final probability annotations ("92%", "8%") at line endpoints
  - [ ] Team colors applied to lines dynamically

- **Technical Context**:
  ```css
  /* webapp/static/style.css */
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  body {
    background-color: #0a0a0a;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  #header {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    gap: 20px;
  }

  #score {
    font-size: 48px;
    font-weight: bold;
  }

  .team-name {
    font-size: 18px;
    text-transform: uppercase;
  }

  #game-selector {
    background: #1a1a1a;
    color: #fff;
    border: 1px solid #333;
    padding: 8px 16px;
    font-size: 14px;
  }

  .final-prob {
    position: absolute;
    font-size: 36px;
    font-weight: bold;
  }

  .final-prob.home {
    right: 80px;
    color: var(--home-color);
  }

  .final-prob.away {
    right: 80px;
    color: #808080;
  }
  ```

- **Validation Steps**:
  1. Verify dark background throughout
  2. Change game via dropdown
  3. Check header updates with new teams/score
  4. Verify final probabilities show correctly

---

### Story 1.4: Documentation and Testing

- **ID**: S1-E1-S4
- **Type**: Documentation
- **Priority**: High
- **Estimate**: 8 hours
- **Phase**: 4
- **Prerequisites**: S1-E1-S3
- **Files to Create**: `webapp/README.md`

- **Acceptance Criteria**:
  - [ ] README includes setup instructions
  - [ ] README includes API documentation
  - [ ] App works in Chrome, Firefox, Safari
  - [ ] Chart renders in < 500ms
  - [ ] 3 demo screenshots saved

- **Technical Context**:
  ```markdown
  # Win Probability Chart Web App

  Interactive visualization of NBA win probabilities using TradingView's Lightweight Charts.

  ## Setup

  1. Install dependencies:
     ```bash
     pip install fastapi uvicorn psycopg
     ```

  2. Set database URL:
     ```bash
     export DATABASE_URL="postgresql://..."
     ```

  3. Start server:
     ```bash
     cd webapp
     uvicorn api.main:app --reload
     ```

  4. Open browser:
     ```
     http://localhost:8000/
     ```

  ## API Endpoints

  - `GET /api/games` - List recent games
  - `GET /api/games/{id}/probs` - Probability time series
  - `GET /api/games/{id}/meta` - Team metadata
  ```

---

## Dependencies to Add

### requirements.txt additions

```
fastapi>=0.109.0
uvicorn>=0.27.0
```

Note: `psycopg` is already in requirements.txt.

### CDN Dependencies (loaded in HTML)

```html
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
```

---

## Technical Decisions

### Design Pattern: Single-Page Application (SPA)

- **Category**: Architectural
- **Intent**: Load once, update dynamically via API calls
- **Implementation**: Vanilla JS with Lightweight Charts
- **Benefits**: Fast interactions, no page reloads
- **Trade-offs**: Requires JavaScript enabled
- **Rationale**: Matches modern trading/analytics dashboards

### Algorithm: Time-Series Transformation

- **Type**: Data transformation
- **Complexity**: O(n) time, O(n) space
- **Description**: Convert (time_remaining, probability) to Lightweight Charts format (time_elapsed, value)
- **Use Case**: Lightweight Charts expects ascending time values

```python
# Backend transformation
def transform_for_chart(rows):
    return [
        {
            "time": 2880 - row["time_remaining"],  # Convert to elapsed
            "home_prob": row["home_win_percentage"],
            "away_prob": row["away_win_percentage"],
            "home_score": row["home_score"],
            "away_score": row["away_score"],
        }
        for row in rows
    ]
```

---

## Risk Assessment

### Technical Risks

- **Risk 1**: Lightweight Charts time scale not suited for "game seconds"
  - **Probability**: Medium
  - **Impact**: Medium (chart may show raw numbers instead of quarter labels)
  - **Mitigation**: Use custom tick formatter or map to fake timestamps

- **Risk 2**: CORS issues with API requests
  - **Probability**: Low (FastAPI CORS middleware handles this)
  - **Impact**: High (app won't work)
  - **Mitigation**: CORS middleware configured in Phase 1

- **Risk 3**: Large data payloads slow rendering
  - **Probability**: Low (~500 points per game is small)
  - **Impact**: Low
  - **Mitigation**: Test with largest games (~700 events)

### Business Risks

- **Risk 1**: Visual style doesn't match Polymarket exactly
  - **Probability**: Medium
  - **Impact**: Low (functional > pixel-perfect)
  - **Mitigation**: Iterate on CSS after initial implementation

---

## Success Metrics

- **Technical**:
  - API response time < 200ms
  - Chart render time < 500ms
  - Works in 3 major browsers

- **Quality**:
  - No JavaScript errors in console
  - Responsive layout (desktop + tablet)
  - Clean separation of concerns (API/UI)

- **User Experience**:
  - Game selection takes < 1 second to update chart
  - Hover tooltip updates in real-time
  - Visual style is recognizably "trading chart" / Polymarket-like

---

## Sprint Completion Checklist

- [ ] `webapp/api/main.py` created with 3 endpoints
- [ ] `webapp/static/index.html` created
- [ ] `webapp/static/app.js` created with Lightweight Charts
- [ ] `webapp/static/style.css` created with dark theme
- [ ] `webapp/README.md` created
- [ ] App tested in Chrome, Firefox, Safari
- [ ] 3 demo screenshots saved
- [ ] All acceptance criteria met

---

## Comparison: SVG vs Web App

| Aspect | Static SVG | Web App |
|--------|------------|---------|
| **Implementation Time** | 12 hours | 40 hours |
| **Dependencies** | None | fastapi, uvicorn, CDN |
| **Interactivity** | None | Hover, select, zoom |
| **File Size** | ~50KB per SVG | One app for all games |
| **Real-time Updates** | No | Possible (WebSocket) |
| **Offline Use** | Yes (SVG file) | No (needs server) |
| **Best For** | Reports, exports | Analysis, exploration |

**Recommendation**: Build SVG first (simpler), then web app if interactivity needed.







