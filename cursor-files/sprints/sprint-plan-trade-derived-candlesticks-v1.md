# Sprint Plan: Trade-Derived Candlesticks for Enhanced Chart Visualization

**Date**: 2025-12-28  
**Sprint Duration**: 3-4 days (24-32 hours total)  
**Sprint Goal**: Implement query-time aggregation endpoint for trade-derived candlesticks (1-second/10-second) and add resolution selector to chart UI, enabling users to view sub-minute execution-based price movements  
**Current Status**: Trade data exists in `kalshi.trades` table with 7M+ records. Charts currently display only 1-minute official candlesticks from `kalshi.candlesticks` table.  
**Target Status**: Users can select 1-second/10-second resolution on game detail charts, viewing trade-derived execution-based candlesticks with volume overlays.  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/trade-data-candlestick-enhancement-analysis.md`
- **Current Implementation**: 
  - `webapp/api/endpoints/probabilities.py` - Serves candlestick data
  - `webapp/static/js/chart.js` - Chart rendering
  - `webapp/static/templates/game-detail.html` - Chart UI
  - `db/migrations/031_kalshi_trades.sql` - Trade table schema
  - `db/migrations/025_kalshi_tables.sql` - Candlestick table schema

## Pre-Sprint Code Quality Baseline

- **Test Results**: [To be verified]
- **QC Results**: [To be verified]
- **Code Coverage**: [To be verified]
- **Build Status**: [To be verified]

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database data** - no INSERT, UPDATE, TRUNCATE, DELETE unless part of sprint plan or tests
- **DO NOT modify database users** - no user management or system changes
- **Index-only schema changes allowed**: CREATE INDEX CONCURRENTLY statements via migration are permitted *if and only if* EXPLAIN ANALYZE proves a scan/missing index. Index creation will be validated in Phase 1 and implemented in Phase 3 only if needed.

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git branching, rebasing, or force-push operations. Commits are allowed when explicitly stated in the sprint plan (e.g., for migrations, new features). The intent is to prevent destructive git operations while allowing normal development workflow.

## Sprint Overview

### Business Context
- **Business Driver**: Users need finer-grained view of market execution activity. Current 1-minute candlesticks miss rapid price movements during high-activity periods. Trade data provides microsecond-precision timestamps enabling sub-minute analysis.
- **Success Criteria**: 
  - Users can view 1-second/10-second trade-derived candlesticks on game detail charts
  - Volume overlays show trade activity patterns
  - Query-time aggregation performs acceptably (<500ms for typical game)
- **Stakeholders**: End users viewing game detail charts, trading strategy developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - `kalshi.trades` table contains 7M+ trade records with microsecond-precision timestamps
  - `kalshi.candlesticks` table contains 1-minute official candlesticks (includes bid/ask OHLC)
  - Chart UI displays 1-minute candlesticks only
  - API endpoint `/api/probabilities/{game_id}` serves candlestick data
- **Target System State**: 
  - New API endpoint `/api/probabilities/{game_id}/kalshi-candles` supports `interval_seconds` parameter (1, 10, 60) and `ticker` parameter
  - Query-time aggregation generates trade-derived candles from `kalshi.trades` on-demand with **bounded time windows** (required or derived from game window)
  - Performance guardrails enforce max data points for 1-second resolution
  - Chart UI includes resolution selector (1-minute, 10-second, 1-second) with zoom/window limits
  - Volume overlay toggle available
- **Architecture Impact**: Adds query-time aggregation layer, optional index-only schema changes if performance requires
- **Integration Points**: Existing `kalshi.trades` table, existing chart rendering (Lightweight Charts)

### Sprint Scope
- **In Scope**: 
  - Query-time aggregation endpoint for trade-derived candles
  - Chart UI resolution selector
  - Volume overlay visualization
  - Caching layer for frequently-accessed games
- **Out of Scope**: 
  - Materialized views (future optimization)
  - Bid/ask spread visualization at sub-minute level (not available from trades)
  - Live WebSocket orderbook capture (future enhancement)
- **Assumptions**: 
  - Trade data is already loaded in `kalshi.trades` table
  - Query performance acceptable for on-demand aggregation
  - Users understand trade-derived candles are execution-only (not bid/ask)
- **Constraints**: 
  - Must use integer cents (`yes_price`) for all calculations
  - Must handle sparse data (many seconds have no trades)
  - Must not mutate existing `kalshi.candlesticks` table

## Sprint Phases

### Phase 1: Backend API Endpoint (Duration: 8-10 hours)
**Objective**: Implement query-time aggregation endpoint that generates trade-derived candlesticks from `kalshi.trades` table with bounded time windows and performance guardrails
**Dependencies**: `kalshi.trades` table exists with data, PostgreSQL connection configured
**Deliverables**: 
- Working API endpoint that returns trade-derived candlesticks at multiple resolutions
- Index verification evidence (EXPLAIN ANALYZE output saved)
- Split aggregation functions (fetch_trades DB layer + aggregate_trades pure layer)
- Performance guardrails (max_points limit for 1-second resolution)

### Phase 2: Frontend Chart Enhancements (Duration: 6-8 hours)
**Objective**: Add resolution selector and volume overlay to chart UI
**Dependencies**: Phase 1 complete, API endpoint tested
**Deliverables**: Chart UI with resolution selector and volume overlay toggle

### Phase 3: Caching and Performance (Duration: 4-6 hours)
**Objective**: Add caching layer for frequently-accessed games and optimize query performance (index creation if needed)
**Dependencies**: Phase 1 and 2 complete
**Deliverables**: 
- Caching implementation with performance benchmarks
- Optional index migration (only if Phase 1 evidence showed need)
- Query performance optimization

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Backend Trade-Derived Candlestick API

**Priority**: Critical (foundational for all other work)
**Estimated Time**: 8-10 hours
**Dependencies**: `kalshi.trades` table, PostgreSQL connection
**Status**: Not Started
**Phase Assignment**: Phase 1

#### Story 1.1: Implement Trade-Derived Candlestick Aggregation Function

- **ID**: S1-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 4-5 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `webapp/api/endpoints/probabilities.py` (add new function)
- **Files to Create**: 
  - `webapp/api/utils/trade_candles.py` (new utility module)
- **Dependencies**: `psycopg`, `kalshi.trades` table, existing database connection utilities

- **Acceptance Criteria**:
  - [ ] Function `fetch_trades(conn, ticker, start_ts, end_ts)` exists (DB layer)
  - [ ] Function `aggregate_trades(trade_rows, interval_seconds)` exists (pure aggregation layer)
  - [ ] `fetch_trades()` accepts `ticker`, `start_ts`, `end_ts` parameters (all required, no "all trades" default)
  - [ ] `aggregate_trades()` accepts list of trade rows and `interval_seconds`, returns list of candlestick dicts
  - [ ] Functions return list of candlestick dicts with correct OHLC fields (integer cents)
  - [ ] Functions handle sparse data (only returns intervals with trades)
  - [ ] Functions use integer cents (`yes_price`) for all calculations (no float math)
  - [ ] `aggregate_trades()` sorts trades by `created_time` within each interval
  - [ ] `aggregate_trades()` calculates VWAP correctly using integer division (SUM(price * count) // SUM(count))
  - [ ] Unit tests pass for `aggregate_trades()` with in-memory fixtures (no DB required)
  - [ ] EXPLAIN ANALYZE run on `fetch_trades()` query verifies index usage on `(ticker, created_time)`

- **Technical Context**:
  - **Current State**: No trade-derived candlestick generation exists
  - **Required Changes**: 
    ```python
    # DB layer: fetch trades
    def fetch_trades(
        conn: Connection,
        ticker: str,
        start_ts: int,  # REQUIRED - no default
        end_ts: int     # REQUIRED - no default
    ) -> List[Dict[str, Any]]:
        """
        Fetch trades from kalshi.trades table for given ticker and time window.
        
        Returns list of trade rows (dicts with created_time, yes_price, count, etc.)
        """
    
    # Pure aggregation layer: convert trades to candles
    def aggregate_trades(
        trade_rows: List[Dict[str, Any]],
        interval_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        Aggregate trade rows into candlesticks.
        
        Pure function (no DB dependency) for testability.
        Returns sparse series (only intervals with trades).
        Uses integer cents (yes_price) for all calculations.
        """
    ```
  - **Integration Points**: Uses existing database connection from `webapp/api/db.py`
  - **Data Structures**: 
    - `fetch_trades()` returns list of trade dicts: `[{"created_time": ..., "yes_price": ..., "count": ..., ...}]`
    - `aggregate_trades()` returns list of candlestick dicts: `[{"period_ts": ..., "interval_seconds": ..., "price_open_cents": ..., ...}]`
  - **API Contracts**: Internal functions, no external API contract

- **Implementation Steps**:
  1. Create `webapp/api/utils/trade_candles.py`
  2. Implement `fetch_trades()` with bounded WHERE clause (ticker, start_ts, end_ts)
  3. Run EXPLAIN ANALYZE on query to verify index usage on `(ticker, created_time)`
  4. Document index verification results (save EXPLAIN ANALYZE output)
  5. Implement `aggregate_trades()` pure function (no DB dependency)
  6. Implement OHLC calculation using integer cents
  7. Implement VWAP calculation with integer division: `SUM(price * count) // SUM(count)`
  8. Add error handling for edge cases (no trades, invalid intervals)
  9. Write unit tests for `aggregate_trades()` with in-memory fixtures

- **Validation Steps**:
  ```bash
  # 1. Verify index exists
  psql $DATABASE_URL -c "SELECT indexname FROM pg_indexes WHERE tablename = 'trades' AND schemaname = 'kalshi' AND indexname LIKE '%ticker%time%';"
  
  # 2. Run EXPLAIN ANALYZE on query
  psql $DATABASE_URL -c "
  EXPLAIN (ANALYZE, BUFFERS) 
  SELECT created_time, yes_price, count 
  FROM kalshi.trades 
  WHERE ticker = 'KXNBAGAME-25NOV30OKCPOR-POR' 
    AND created_time >= '2025-11-30 22:45:00'::timestamptz
    AND created_time < '2025-12-01 01:35:00'::timestamptz
  ORDER BY created_time;
  "
  # Verify: Index Scan on idx_kalshi_trades_ticker_time (not Seq Scan)
  
  # 3. Test pure aggregation function (no DB)
  python -c "
  from webapp.api.utils.trade_candles import aggregate_trades
  test_trades = [
      {'created_time': '2025-11-30T23:00:00Z', 'yes_price': 50, 'count': 100},
      {'created_time': '2025-11-30T23:00:01Z', 'yes_price': 51, 'count': 200},
  ]
  candles = aggregate_trades(test_trades, 1)
  print(f'Generated {len(candles)} candles')
  "
  ```

- **Definition of Done**: Function generates correct OHLC data from trades, handles edge cases, passes unit tests
- **Rollback Plan**: Delete `webapp/api/utils/trade_candles.py` if issues arise
- **Risk Assessment**: 
  - **Risk**: Query performance on large datasets
  - **Mitigation**: Add indexes verification, use query-time aggregation with LIMIT if needed
- **Success Metrics**: 
  - Function executes in <500ms for typical bounded window (~10k trades in 1-hour window)
  - Correct OHLC values verified against manual calculation
  - EXPLAIN ANALYZE evidence saved showing index usage (or documenting missing index)

#### Story 1.2: Add API Endpoint for Trade-Derived Candles

- **ID**: S1-E1-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 3-4 hours
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1
- **Files to Modify**: 
  - `webapp/api/endpoints/probabilities.py` (add new endpoint)
- **Files to Create**: None
- **Dependencies**: Story 1.1 function, FastAPI router

- **Acceptance Criteria**:
  - [ ] Endpoint `GET /api/probabilities/{game_id}/kalshi-candles` exists
  - [ ] Endpoint accepts `interval_seconds` query parameter (1, 10, 60)
  - [ ] Endpoint accepts `source` query parameter ("official" or "trades")
  - [ ] Endpoint accepts `ticker` query parameter (optional, for multi-ticker games)
  - [ ] Endpoint accepts optional `start_ts` and `end_ts` query parameters
  - [ ] **If `start_ts`/`end_ts` omitted for trade-derived candles**: Derives from game window (event_date + duration from ESPN data)
  - [ ] **Performance guardrail**: For 1-second resolution, enforces max_points limit (e.g., 3600 = 1 hour) or returns 400 error with message
  - [ ] Endpoint returns JSON with candlestick array (or `markets: [{ticker, candles}]` if multiple tickers)
  - [ ] Endpoint uses official candlesticks when `interval_seconds=60` and `source=official`
  - [ ] Endpoint uses trade-derived candles when `interval_seconds=1` or `10` and `source=trades`
  - [ ] Endpoint handles errors gracefully (invalid game_id, no trades, window too large, etc.)
  - [ ] Endpoint response time <500ms for typical bounded window

- **Technical Context**:
  - **Current State**: Only 1-minute official candlesticks available via existing endpoints
  - **Required Changes**:
    ```python
    @router.get("/probabilities/{game_id}/kalshi-candles")
    def get_kalshi_candles(
        game_id: str,
        interval_seconds: int = 60,
        source: str = "auto",
        ticker: Optional[str] = None,  # Optional: if None, use primary market or return all
        start_ts: Optional[int] = None,  # Optional: if None, derive from game window
        end_ts: Optional[int] = None     # Optional: if None, derive from game window
    ) -> dict[str, Any]:
        """
        Get Kalshi candlesticks for a game.
        
        - interval_seconds=60, source="official": 1-minute candles from kalshi.candlesticks
        - interval_seconds=1, source="trades": 1-second trade-derived candles (requires bounded window)
        - interval_seconds=10, source="trades": 10-second trade-derived candles (requires bounded window)
        
        Performance guardrails:
        - For 1-second resolution: max_points=3600 (1 hour) enforced
        - If window too large: returns 400 with message "Zoom in to use 1-second view"
        - If start_ts/end_ts omitted: derives from game window (event_date + duration)
        
        Multi-ticker support:
        - If ticker provided: returns {"candles": [...], "ticker": "..."}
        - If ticker omitted: returns {"markets": [{"ticker": "...", "candles": [...]}, ...]}
        - Primary market selection: first ticker by snapshot_id DESC (most recent)
        """
    ```
  - **Integration Points**: Uses existing game_id lookup, database connection, ESPN game window derivation
  - **API Contracts**: 
    - Single ticker: `{"candles": [...], "ticker": "...", "interval_seconds": 1, "source": "trades"}`
    - Multiple tickers: `{"markets": [{"ticker": "...", "candles": [...]}], "interval_seconds": 1, "source": "trades"}`
    - Error: `{"error": "Window too large for 1-second resolution. Zoom in or use 10-second/1-minute view.", "max_points": 3600}`

- **Implementation Steps**:
  1. Add endpoint to `webapp/api/endpoints/probabilities.py`
  2. Implement game_id to ticker(s) lookup (from `kalshi.markets` joined with `espn.scoreboard_games`)
  3. If `ticker` param provided: use that ticker; else: use primary market (most recent snapshot) or return all markets
  4. If `start_ts`/`end_ts` omitted for trade-derived: derive from game window (event_date + duration from ESPN probabilities)
  5. **Add performance guardrail**: Calculate max_points = (end_ts - start_ts) / interval_seconds; if interval_seconds=1 and max_points > 3600, return 400 error
  6. Route to appropriate data source (official vs. trade-derived)
  7. For trade-derived: call `fetch_trades()` then `aggregate_trades()` with bounded window
  8. Format response JSON (single ticker vs. multiple markets)
  9. Add error handling (invalid game_id, no trades, window too large, etc.)
  10. Add API documentation

- **Validation Steps**:
  ```bash
  # Test endpoint with bounded window
  curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&start_ts=1733011200&end_ts=1733014800" | jq '.candles | length'
  
  # Test endpoint without window (should derive from game)
  curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades" | jq '.candles | length'
  
  # Test window too large (should return 400)
  curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&start_ts=1733011200&end_ts=1733097600" | jq '.error'
  
  # Test official candles (no window required)
  curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=60&source=official" | jq '.candles | length'
  
  # Test ticker parameter
  curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&ticker=KXNBAGAME-25NOV30OKCPOR-POR&start_ts=1733011200&end_ts=1733014800" | jq '.ticker'
  ```

- **Definition of Done**: Endpoint returns correct data for all parameter combinations, handles errors, documented
- **Rollback Plan**: Remove endpoint from router if issues arise
- **Risk Assessment**: 
  - **Risk**: Performance issues with large datasets
  - **Mitigation**: Add caching (Phase 3), optimize queries
- **Success Metrics**: 
  - Endpoint response time <500ms for bounded windows
  - Correct data returned for all parameter combinations
  - 400 error returned appropriately for oversized windows
  - Game window derivation works when start_ts/end_ts omitted

#### Story 1.3: Add Unit Tests for Trade-Derived Candlestick Functions

- **ID**: S1-E1-S3
- **Type**: Testing
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 1
- **Prerequisites**: S1-E1-S1, S1-E1-S2
- **Files to Create**: 
  - `tests/test_trade_candles.py` (new test file)
- **Dependencies**: pytest, test database or fixtures

- **Acceptance Criteria**:
  - [ ] Unit tests exist for `aggregate_trades()` pure function (no DB dependency)
  - [ ] Tests use in-memory fixtures (no database required)
  - [ ] Tests cover edge cases:
    - [ ] No trades (empty list)
    - [ ] Single trade
    - [ ] Multiple trades per second (verify open=first, close=last ordering)
    - [ ] Duplicate timestamps (multiple trades with same created_time)
    - [ ] Big block trade (large count value) - verify VWAP uses SUM(count), not COUNT(*)
    - [ ] Sparse intervals (gaps between intervals with trades)
  - [ ] Tests verify integer cents calculations (no float math)
  - [ ] Tests verify VWAP calculation: `SUM(price * count) // SUM(count)`
  - [ ] Tests verify OHLC ordering (open=first trade, close=last trade within interval)
  - [ ] Optional DB integration test exists behind `RUN_DB_TESTS=1` env flag
  - [ ] All unit tests pass without database

- **Technical Context**:
  - **Current State**: No tests for trade-derived candlestick functions
  - **Required Changes**: Create comprehensive test suite

- **Implementation Steps**:
  1. Create `tests/test_trade_candles.py`
  2. Add in-memory fixtures for sample trade data (no DB connection)
  3. Write unit tests for `aggregate_trades()` covering all edge cases
  4. Add optional DB integration test (gated by `RUN_DB_TESTS=1` env var)
  5. Verify test coverage >80% for `aggregate_trades()` function

- **Validation Steps**:
  ```bash
  pytest tests/test_trade_candles.py -v
  ```

- **Definition of Done**: All tests pass, coverage >80%
- **Rollback Plan**: Remove test file if needed
- **Risk Assessment**: Low risk
- **Success Metrics**: 100% test pass rate, >80% code coverage

### Epic 2: Frontend Chart Enhancements

**Priority**: High (user-facing feature)
**Estimated Time**: 6-8 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

#### Story 2.1: Add Resolution Selector to Chart UI

- **ID**: S1-E2-S1
- **Type**: Feature
- **Priority**: High
- **Estimate**: 3-4 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E1-S2 (API endpoint complete)
- **Files to Modify**: 
  - `webapp/static/templates/game-detail.html` (add selector UI)
  - `webapp/static/js/chart.js` (add resolution change handler)
  - `webapp/static/js/ui.js` (update chart loading logic)
- **Files to Create**: None
- **Dependencies**: Lightweight Charts library, existing chart infrastructure

- **Acceptance Criteria**:
  - [ ] Resolution selector dropdown exists in chart controls
  - [ ] Options: "1 Minute" (60), "10 Seconds" (10), "1 Second" (1)
  - [ ] Default selection is "1 Minute" (backward compatible)
  - [ ] **UI labels clarify source**: "1 Minute (Official)" and "10 Seconds / 1 Second (Trade-Derived)"
  - [ ] **Guardrail**: 1-second resolution requires zoom/window (not full game by default)
  - [ ] Changing resolution fetches new data from API endpoint with appropriate window
  - [ ] Chart updates with new resolution data
  - [ ] Loading indicator shows during data fetch
  - [ ] **Error handling**: If backend returns 400 "window too large", show user-friendly message: "Zoom in to use 1-second view"
  - [ ] Error handling displays user-friendly message for other failures

- **Technical Context**:
  - **Current State**: Chart always displays 1-minute candlesticks
  - **Required Changes**:
    ```html
    <!-- Add to game-detail.html -->
    <div class="chart-controls">
      <select id="candlestickResolution">
        <option value="60">1 Minute</option>
        <option value="10">10 Seconds</option>
        <option value="1">1 Second</option>
      </select>
    </div>
    ```
    ```javascript
    // Add to chart.js
    async function updateCandlestickResolution(resolution) {
      const source = resolution === 60 ? 'official' : 'trades';
      // For 1-second resolution, use zoom window if available, else show error
      const windowParams = getZoomWindow(); // Returns {start_ts, end_ts} if zoomed, else null
      
      let url = `/api/probabilities/${gameId}/kalshi-candles?interval_seconds=${resolution}&source=${source}`;
      if (windowParams) {
        url += `&start_ts=${windowParams.start_ts}&end_ts=${windowParams.end_ts}`;
      }
      
      try {
        const response = await fetch(url);
        if (response.status === 400) {
          const error = await response.json();
          if (error.error && error.error.includes('window too large')) {
            showUserMessage('Zoom in to use 1-second view');
            return;
          }
        }
        const data = await response.json();
        updateChart(data.candles || data.markets[0].candles);
      } catch (error) {
        showUserMessage('Failed to load candlestick data');
      }
    }
    ```

- **Implementation Steps**:
  1. Add resolution selector HTML to `game-detail.html` with source labels
  2. Add event listener for resolution change
  3. Implement `updateCandlestickResolution()` function with window handling
  4. Implement `getZoomWindow()` helper to detect if chart is zoomed
  5. Update chart data loading logic to pass window params for 1-second resolution
  6. Add loading/error states
  7. Add user-friendly error message display for "window too large" errors
  8. Test with different resolutions and zoom states

- **Validation Steps**:
  ```bash
  # Manual testing in browser
  # 1. Load game detail page
  # 2. Change resolution selector
  # 3. Verify chart updates with new data
  # 4. Verify API calls use correct parameters
  ```

- **Definition of Done**: Resolution selector works, chart updates correctly, backward compatible
- **Rollback Plan**: Remove selector HTML and JS if issues arise
- **Risk Assessment**: 
  - **Risk**: Performance issues with 1-second data (many data points)
  - **Mitigation**: Add data point limit, use sampling for very large datasets
- **Success Metrics**: 
  - Selector works for all resolutions
  - Chart renders correctly with <2s load time
  - User-friendly error messages displayed for window too large
  - Source labels clearly indicate Official vs. Trade-Derived

#### Story 2.2: Add Volume Overlay Visualization

- **ID**: S1-E2-S2
- **Type**: Feature
- **Priority**: Medium
- **Estimate**: 2-3 hours
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1
- **Files to Modify**: 
  - `webapp/static/templates/game-detail.html` (add volume toggle)
  - `webapp/static/js/chart.js` (add volume series)
- **Files to Create**: None
- **Dependencies**: Lightweight Charts histogram/bar series support

- **Acceptance Criteria**:
  - [ ] Volume overlay toggle checkbox exists in chart controls
  - [ ] Toggle shows/hides volume bars
  - [ ] Volume bars display correctly aligned with candlesticks
  - [ ] Volume uses SUM(count) from trades, not COUNT(trades)
  - [ ] Volume bars scale appropriately (not overlapping candlesticks)
  - [ ] Toggle state persists during session

- **Technical Context**:
  - **Current State**: No volume visualization
  - **Required Changes**: Add histogram series to Lightweight Charts, overlay on candlestick chart

- **Implementation Steps**:
  1. Add volume toggle checkbox to HTML
  2. Add histogram series to chart
  3. Fetch volume data from API (or extract from candlestick data)
  4. Render volume bars aligned with time axis
  5. Add toggle event handler
  6. Style volume bars appropriately

- **Validation Steps**:
  ```bash
  # Manual testing
  # 1. Toggle volume overlay on/off
  # 2. Verify bars align with candlesticks
  # 3. Verify volume values match expected (SUM(count))
  ```

- **Definition of Done**: Volume overlay works, toggleable, correctly displays trade volume
- **Rollback Plan**: Remove volume toggle and series if issues arise
- **Risk Assessment**: Low risk
- **Success Metrics**: Volume overlay displays correctly, performance acceptable

#### Story 2.3: Update Chart Legend and Tooltips

- **ID**: S1-E2-S3
- **Type**: Enhancement
- **Priority**: Low
- **Estimate**: 1 hour
- **Phase**: Phase 2
- **Prerequisites**: S1-E2-S1, S1-E2-S2
- **Files to Modify**: 
  - `webapp/static/js/chart.js` (update legend)
  - `webapp/static/js/ui.js` (update tooltip formatting)
- **Files to Create**: None

- **Acceptance Criteria**:
  - [ ] Chart legend indicates current resolution (1m/10s/1s)
  - [ ] Legend indicates data source (Official vs. Trade-Derived)
  - [ ] Tooltips show correct values for selected resolution
  - [ ] Tooltips indicate if data is sparse (gaps)

- **Implementation Steps**:
  1. Update legend rendering function
  2. Add resolution indicator to legend
  3. Update tooltip formatter
  4. Add sparse data indicator

- **Definition of Done**: Legend and tooltips accurate and informative
- **Rollback Plan**: Revert legend changes if needed
- **Risk Assessment**: Low risk

### Epic 3: Caching and Performance Optimization

**Priority**: Medium (performance optimization)
**Estimated Time**: 4-6 hours
**Dependencies**: Epic 1 and 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

#### Story 3.1: Implement Caching Layer for Trade-Derived Candles

- **ID**: S1-E3-S1
- **Type**: Performance
- **Priority**: Medium
- **Estimate**: 3-4 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E1-S2 (API endpoint)
- **Files to Modify**: 
  - `webapp/api/endpoints/probabilities.py` (add caching)
  - `webapp/api/cache.py` (if exists, or create)
- **Files to Create**: 
  - `webapp/api/cache.py` (if doesn't exist)
- **Dependencies**: Python caching library (functools.lru_cache or redis)

- **Acceptance Criteria**:
  - [ ] Caching layer implemented for trade-derived candle queries
  - [ ] **Cache strategy**: In-memory TTL cache with max size limit
  - [ ] **Cache key includes**: `source` + `ticker` + `interval_seconds` + `start_ts` + `end_ts` (all parameters that affect result)
  - [ ] **Cache TTL**: Default 1 hour, configurable
  - [ ] **Cache max size**: 256 keys (LRU eviction when full)
  - [ ] **Documentation**: Cache is per-worker (if multiple workers, hit-rate expectations must account for this)
  - [ ] Cache hit rate >50% for repeated queries (within same worker)
  - [ ] Cache doesn't interfere with official candlestick queries
  - [ ] Cache invalidation on new trade data (optional, future enhancement)

- **Technical Context**:
  - **Current State**: No caching for trade-derived candles
  - **Required Changes**: 
    ```python
    from functools import lru_cache
    from datetime import datetime, timedelta
    
    # In-memory cache with TTL and max size
    cache = {}
    cache_ttl = timedelta(hours=1)
    cache_max_size = 256
    
    def get_cache_key(source: str, ticker: str, interval_seconds: int, start_ts: int, end_ts: int) -> str:
        return f"{source}:{ticker}:{interval_seconds}:{start_ts}:{end_ts}"
    
    def get_cached_or_compute(cache_key: str, compute_fn):
        # Check cache, return if valid, else compute and cache
        # Implement LRU eviction when cache_max_size reached
        pass
    ```

- **Implementation Steps**:
  1. Implement in-memory TTL cache with max size (256 keys)
  2. Implement cache key generation: `f"{source}:{ticker}:{interval_seconds}:{start_ts}:{end_ts}"`
  3. Implement LRU eviction when cache_max_size reached
  4. Add caching decorator/wrapper to API endpoint
  5. Add cache statistics/logging (hits, misses, evictions)
  6. Document per-worker limitation in code comments
  7. Test cache hit/miss behavior

- **Validation Steps**:
  ```bash
  # Test cache behavior with all parameters
  # 1. First request (cache miss)
  time curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&ticker=KXNBAGAME-25NOV30OKCPOR-POR&start_ts=1733011200&end_ts=1733014800"
  # 2. Second request with same params (cache hit, should be faster)
  time curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&ticker=KXNBAGAME-25NOV30OKCPOR-POR&start_ts=1733011200&end_ts=1733014800"
  # 3. Different window (cache miss)
  time curl "http://localhost:8000/api/probabilities/401810160/kalshi-candles?interval_seconds=1&source=trades&ticker=KXNBAGAME-25NOV30OKCPOR-POR&start_ts=1733014800&end_ts=1733018400"
  # Verify cache key includes all params (check logs)
  ```

- **Definition of Done**: Caching works, improves performance, configurable
- **Rollback Plan**: Remove caching decorator if issues arise
- **Risk Assessment**: 
  - **Risk**: Memory usage with large cache
  - **Mitigation**: Set reasonable TTL, limit cache size
- **Success Metrics**: 
  - Cache hit rate >50% for repeated queries (within same worker)
  - Response time improvement >30% on cache hits
  - Cache max size enforced (LRU eviction working)
  - Cache key includes all relevant parameters

#### Story 3.2: Optimize Trade Query Performance

- **ID**: S1-E3-S2
- **Type**: Performance
- **Priority**: Medium
- **Estimate**: 1-2 hours
- **Phase**: Phase 3
- **Prerequisites**: S1-E1-S1 (aggregation function)
- **Files to Modify**: 
  - `webapp/api/utils/trade_candles.py` (optimize SQL query)
- **Files to Create**: None

- **Acceptance Criteria**:
  - [ ] **Index verification completed in Phase 1** (EXPLAIN ANALYZE evidence saved)
  - [ ] If index missing or unused: Create migration with `CREATE INDEX CONCURRENTLY` (only if Phase 1 evidence shows need)
  - [ ] SQL query uses appropriate indexes (`idx_kalshi_trades_ticker_time`)
  - [ ] Query execution time <500ms for typical bounded window
  - [ ] Query plan verified (EXPLAIN ANALYZE) - no full table scans
  - [ ] Migration file created: `db/migrations/032_add_trade_candles_index.sql` (if needed)

- **Technical Context**:
  - **Current State**: Query may not be optimized
  - **Required Changes**: Optimize SQL, verify indexes

- **Implementation Steps**:
  1. Review Phase 1 EXPLAIN ANALYZE evidence
  2. **If index missing or unused**: Create migration file `db/migrations/032_add_trade_candles_index.sql`
  3. Migration uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS` (non-blocking)
  4. Verify index creation: `SELECT indexname FROM pg_indexes WHERE ...`
  5. Re-run EXPLAIN ANALYZE to confirm index usage
  6. Optimize query structure if needed
  7. Add query timing logs

- **Validation Steps**:
  ```bash
  # Only run if Phase 1 evidence showed missing/unused index
  # 1. Run migration
  python scripts/migrate.py --dsn "$DATABASE_URL"
  
  # 2. Verify index exists
  psql $DATABASE_URL -c "SELECT indexname FROM pg_indexes WHERE tablename = 'trades' AND schemaname = 'kalshi' AND indexname LIKE '%ticker%time%';"
  
  # 3. Re-check query plan (should show Index Scan)
  psql $DATABASE_URL -c "EXPLAIN (ANALYZE, BUFFERS) SELECT created_time, yes_price, count FROM kalshi.trades WHERE ticker = 'KXNBAGAME-25NOV30OKCPOR-POR' AND created_time >= '2025-11-30 22:45:00'::timestamptz AND created_time < '2025-12-01 01:35:00'::timestamptz ORDER BY created_time;"
  ```

- **Definition of Done**: 
  - If index needed: Migration created and applied
  - Query optimized, uses indexes, <500ms execution time for bounded windows
  - EXPLAIN ANALYZE confirms Index Scan (not Seq Scan)
- **Rollback Plan**: Drop index if issues: `DROP INDEX CONCURRENTLY IF EXISTS kalshi.idx_trade_candles_ticker_time;`
- **Risk Assessment**: Low risk (index creation is non-blocking with CONCURRENTLY)
- **Success Metrics**: 
  - Query execution time <500ms for bounded windows
  - Index Scan confirmed in query plan

### Epic 4: Documentation and Quality Assurance

**Priority**: Critical (sprint completion requirement)
**Estimated Time**: 3-4 hours
**Dependencies**: All other epics complete
**Status**: Not Started
**Phase Assignment**: Phase 4

#### Story 4.1: Documentation Update

- **ID**: S1-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] API endpoint documented in code (docstrings)
  - [ ] README updated with new endpoint usage
  - [ ] Chart UI changes documented
  - [ ] Trade-derived candle limitations documented (execution-only, sparse data)

- **Implementation Steps**:
  1. Update API endpoint docstrings
  2. Update README with endpoint examples
  3. Add inline comments for complex logic
  4. Document limitations and edge cases

- **Definition of Done**: All documentation updated and accurate

#### Story 4.2: Quality Gate Validation

- **ID**: S1-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All tests pass (100% pass rate required)
  - [ ] Build process completes without errors
  - [ ] Code quality maintained or improved
  - [ ] All previous story acceptance criteria verified
  - [ ] API endpoint tested manually
  - [ ] Chart UI tested in browser

- **Implementation Steps**:
  1. Run linting: `pylint webapp/api/endpoints/probabilities.py webapp/api/utils/trade_candles.py`
  2. Run tests: `pytest tests/test_trade_candles.py -v`
  3. Test API endpoint manually
  4. Test chart UI in browser
  5. Verify all acceptance criteria met

- **Definition of Done**: All quality gates pass, all acceptance criteria verified

#### Story 4.3: Sprint Completion and Archive

- **ID**: S1-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] Sprint completion report created
  - [ ] All files organized
  - [ ] Sprint marked as completed

- **Implementation Steps**:
  1. Create sprint completion report
  2. Document lessons learned
  3. Archive sprint files
  4. Update sprint status

- **Definition of Done**: Sprint completed and archived

## Technical Decisions

### Design Pattern: Query-Time Aggregation Pattern with Bounded Windows

- **Category**: Architectural
- **Intent**: Generate trade-derived candlesticks on-demand without materialization to avoid storage overhead, with performance guardrails
- **Implementation**: 
  - Split into two layers: `fetch_trades()` (DB) and `aggregate_trades()` (pure)
  - SQL queries executed per request with bounded time windows (required or derived)
  - Results cached with TTL and max size limits
  - Performance guardrails enforce max_points for 1-second resolution
- **Benefits**: 
  - No storage overhead
  - Always up-to-date (uses latest trades)
  - Flexible (supports multiple resolutions)
  - Performance-safe (bounded queries, guardrails)
  - Testable (pure aggregation function)
- **Trade-offs**: 
  - Computation overhead on each request (mitigated by caching)
  - Requires trade data to be loaded
  - Requires time window bounds (no "all trades" queries)
- **Rationale**: Chosen over materialized views to avoid storage bloat and refresh complexity. Bounded windows ensure performance with 7M+ trades.

### Algorithm: Sliding Window OHLC Aggregation (Split Architecture)

- **Type**: Time-Series Aggregation
- **Complexity**: 
  - `fetch_trades()`: O(log n + k) with index, where k = trades in window
  - `aggregate_trades()`: O(n) if trades sorted, O(n log n) if needs sorting, Space O(m) where m = unique intervals
- **Description**: 
  - Layer 1: Fetch trades from DB with bounded window (ticker + time range)
  - Layer 2: Pure function aggregates trades into candlesticks by interval
- **Use Case**: Converting individual trades into candlestick format with testable pure aggregation
- **Performance**: 
  - Bounded queries prevent full table scans
  - Index on (ticker, created_time) enables efficient range queries
  - Pure aggregation function enables unit testing without DB

### Design Decision: Integer Cents for Price Calculations

- **Problem**: Floating-point precision issues in financial calculations
- **Context**: Trade prices stored as integer cents (`yes_price`, `no_price`)
- **Selected**: Use integer cents end-to-end, convert to dollars only for display
- **Rationale**: Avoids floating-point rounding errors, matches Kalshi API format

### Design Decision: Bounded Time Windows (Performance Safety)

- **Problem**: With 7M+ trades, unbounded queries would be slow and memory-intensive
- **Context**: Trade-derived candles must be performant and safe
- **Selected**: Require bounded time windows (start_ts/end_ts) or derive from game window. Enforce max_points limit for 1-second resolution (3600 = 1 hour).
- **Rationale**: Prevents performance issues, ensures queries complete in <500ms, protects against accidental full-game queries

### Design Decision: Split Aggregation Functions (Testability)

- **Problem**: Testing DB-dependent functions requires database setup
- **Context**: Need comprehensive unit tests for aggregation logic
- **Selected**: Split into `fetch_trades()` (DB layer) and `aggregate_trades()` (pure function)
- **Rationale**: Pure function enables unit testing with in-memory fixtures, no DB required for most tests

### Design Decision: Multi-Ticker Support

- **Problem**: Games can have multiple markets/tickers (home/away)
- **Context**: Endpoint needs to handle single or multiple tickers
- **Selected**: Support `ticker` query parameter (optional). If omitted, return primary market (most recent snapshot) or all markets in response.
- **Rationale**: Flexible API supports both single-ticker and multi-ticker use cases

### Design Decision: Sparse Storage (No Forward-Fill)

- **Problem**: Many seconds have zero trades, creating gaps
- **Context**: Trade-derived candles should represent actual observed data
- **Selected**: Store only intervals with trades, no forward-fill in database
- **Rationale**: Maintains data integrity, forward-fill is visualization-only choice

## Testing Strategy

- **Unit Tests**: Test trade aggregation function with sample data, edge cases
- **Integration Tests**: Test API endpoint with real database queries
- **E2E Tests**: Test chart UI with different resolutions
- **Performance Tests**: Measure query execution time, cache hit rates

## Deployment Plan

- **Pre-Deployment**: 
  - Verify database indexes exist
  - Verify trade data loaded
  - Run all tests
- **Deployment Steps**: 
  - Deploy backend API changes
  - Deploy frontend UI changes
  - Verify API endpoint accessible
- **Post-Deployment**: 
  - Monitor API response times
  - Monitor cache hit rates
  - Verify chart UI works in production
- **Rollback Plan**: 
  - Remove API endpoint if issues
  - Revert frontend changes if needed

## Risk Assessment

- **Technical Risks**: 
  - Query performance on large datasets → Mitigation: Indexes, caching, query optimization
  - Frontend performance with many data points → Mitigation: Data point limits, sampling
- **Business Risks**: 
  - User confusion about execution-only data → Mitigation: Clear documentation, UI labels
- **Resource Risks**: 
  - Time overrun → Mitigation: Phased approach, can defer caching to future sprint

## Success Metrics

- **Technical**: 
  - API endpoint response time <500ms
  - Cache hit rate >50%
  - Test coverage >80%
  - Zero linting errors
- **Business**: 
  - Users can view sub-minute candlesticks
  - Chart UI responsive and intuitive
- **Sprint**: 
  - All stories completed
  - Quality gates pass
  - Documentation updated

## Sprint Completion Checklist

- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)
- [ ] API endpoint tested and working
- [ ] Chart UI tested and working
- [ ] Performance benchmarks met

### Post-Sprint Quality Comparison

- **Test Results**: [To be filled]
- **Linting Results**: [To be filled]
- **Code Coverage**: [To be filled]
- **Build Status**: [To be filled]
- **Overall Assessment**: [To be filled]

### Documentation and Closure

- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation

**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

