# Live Games Feature Analysis v1

**Date**: 2025-01-27  
**Last Updated**: 2025-01-28  
**Status**: Draft  
**Author**: AI Assistant  
**Version**: v1.2  
**Purpose**: Comprehensive analysis of implementing a live games page with real-time ESPN and Kalshi data integration

**Recent Updates (v1.2)**:
- Added note about `DATABASE_URL` environment variable configuration (set in `.zshrc`)
- Updated frontend module list to include `templates.js` for dynamic template loading
- Added note about export functionality (HTML and image export for aggregate stats)
- Updated frontend architecture to reflect template-based view system

**Recent Updates (v1.1)**:
- Updated to reflect new stats/metrics capabilities (reliability curves, decision-weighted metrics, time-sliced correlations)
- Added note about decision-weighted metrics requiring bid/ask data for live games
- Updated database schema references to include `derived.game_stats` table

## Executive Summary

### Key Findings
- **Live Games Page**: New page to display all currently live NBA games with real-time updates
- **Real-time Data Sources**: ESPN data via HTTP polling, Kalshi data via WebSocket connection
- **Chart Updates**: Continuous chart updates using the same Lightweight Charts library as historical games
- **Architecture**: Requires new backend endpoints, WebSocket handling, and frontend real-time state management

### Critical Issues Identified
- **ESPN Live Data Source**: Need to identify the exact endpoint for live ESPN win probability data (may differ from historical data loading)
- **Kalshi WebSocket API**: Need to verify Kalshi WebSocket connection details, authentication, and message format
- **Real-time Performance**: Chart updates must be efficient to avoid UI lag with high-frequency data
- **State Management**: Frontend must handle multiple live games simultaneously with proper cleanup

### Recommended Actions
- **Action 1**: [Priority: High] - Research and document ESPN live probability endpoint
- **Action 2**: [Priority: High] - Research and document Kalshi WebSocket API specifications
- **Action 3**: [Priority: Medium] - Design backend architecture for live data aggregation
- **Action 4**: [Priority: Medium] - Design frontend state management for real-time updates

### Success Metrics
- **Latency**: Chart updates within 1 second of data arrival
- **Concurrent Games**: Support 10+ live games simultaneously
- **Uptime**: 99%+ connection reliability for live data streams

## Problem Statement

### Current Situation
The application currently displays historical games with pre-loaded data from the database. Users can:
- Browse completed games from the database
- View win probability charts for past games
- See comprehensive statistics and comparisons between ESPN and Kalshi data:
  - Calibration metrics (Brier score, log loss with probability clipping to 0.01-0.99)
  - Time-sliced metrics (Q1, Halftime, Start of Q4, Final 2 minutes) for both ESPN and Kalshi
  - Reliability curves for Kalshi (calibration across 10 probability bins: 0-10%, 10-20%, etc.)
  - Decision-weighted metrics (time-weighted Brier when market is active, distance-weighted MAE, EV-positive disagreements)
  - Divergence metrics (Mean Absolute Difference - measures disagreement, not accuracy; sign flips; correlation by game phase)

**Current Architecture**:
- Backend: FastAPI serving static data from PostgreSQL
- Frontend: Single-page app with client-side routing
- Data Flow: Database → API → Frontend (one-time fetch per game)
- Chart Library: TradingView Lightweight Charts (static data rendering)

### Pain Points
- **No Live Game Support**: Users cannot watch games as they happen
- **Static Data Only**: All data must be pre-loaded into database
- **No Real-time Updates**: Charts are static snapshots, not live streams
- **Limited Engagement**: Users must wait for games to complete before viewing

### Business Impact
- **User Experience**: Missing real-time engagement opportunity
- **Competitive Advantage**: Live tracking is a key differentiator
- **Data Science Value**: Real-time data enables live model validation and trading decisions

### Success Criteria
- **Live Game Detection**: Automatically identify and display currently live games
- **Real-time Chart Updates**: Charts update continuously as new data arrives
- **Multi-game Support**: Users can switch between multiple live games
- **Data Accuracy**: Live data matches historical data quality and format
- **Performance**: Smooth updates without UI freezing or lag
- **Real-time Stats**: Calculate and display stats as game progresses (decision-weighted metrics, time-sliced Brier scores)
- **Market-Aware Metrics**: Only calculate decision-weighted metrics when Kalshi bid/ask data is available (market is active)

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 
  - Backend: New endpoint files (`endpoints/live_games.py`, `endpoints/live_data.py`)
  - Frontend: New page (`js/live.js`), routing updates, chart update logic
  - Infrastructure: WebSocket server setup, connection management
- **Estimated Effort**: 40-60 hours
  - Backend: 20-25 hours (endpoints, WebSocket handling, data aggregation)
  - Frontend: 15-20 hours (live page, chart updates, state management)
  - Testing & Integration: 5-15 hours
- **Technical Complexity**: High
  - Real-time data synchronization
  - WebSocket connection management
  - Efficient chart updates
  - Multi-game state management
- **Risk Level**: Medium-High
  - External API dependencies (ESPN, Kalshi)
  - WebSocket reliability
  - Performance under load

**Sprint Scope Recommendation**: Multiple Sprints (2-3 sprints)
- **Rationale**: Complex feature requiring backend infrastructure, frontend real-time updates, and integration testing
- **Recommended Approach**:
  - Sprint 1: Backend live data endpoints and WebSocket infrastructure (20-25 hours)
  - Sprint 2: Frontend live games page and chart updates (15-20 hours)
  - Sprint 3: Integration, testing, and performance optimization (5-15 hours)

**Dependency Analysis**:
- ESPN live API endpoint discovery and validation
- Kalshi WebSocket API documentation and authentication
- WebSocket library selection (Python backend, JavaScript frontend)
- Chart library update API understanding

## Current State Analysis

### System Architecture Overview

**Backend (FastAPI)**:
- **File**: `webapp/api/main.py`
  - FastAPI application setup
  - CORS middleware
  - Router registration
  - Static file serving
- **Endpoints**:
  - `/api/games` - List games (historical, from database)
  - `/api/games/{game_id}/probs` - Get probability time series (historical)
  - `/api/games/{game_id}/meta` - Get game metadata
  - `/api/games/{game_id}/stats` - Get game statistics (includes calibration metrics, time-sliced Brier scores, reliability curves, decision-weighted metrics)
  - `/api/stats/aggregate` - Aggregate statistics across all games (includes Kalshi calibration, sign flips, correlation by game phase)
  - `/api/stats/aggregate/refresh-status` - Check background refresh status for aggregate stats
- **Database**: PostgreSQL with `espn.*`, `kalshi.*`, and `derived.*` schemas
  - **Connection**: Uses `DATABASE_URL` environment variable (default: `postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse`)
  - **Note**: `DATABASE_URL` is configured in `.zshrc` for local development
  - **File**: `webapp/api/db.py` - Database connection utilities
- **Caching**: In-memory cache with file persistence (`.cache/` directory)
  - **File**: `webapp/api/cache.py` - Caching system with background refresh support

**Frontend (Vanilla JavaScript)**:
- **File**: `webapp/static/index.html`
  - Single-page application
  - Client-side routing using hash (`#/game/{game_id}`, `#/stats`)
  - Template-based view system (views loaded dynamically)
- **Modules**:
  - `js/state.js` - Application state management
  - `js/api.js` - API client functions
  - `js/chart.js` - Chart rendering (Lightweight Charts)
  - `js/routing.js` - URL routing
  - `js/ui.js` - UI rendering
  - `js/filters.js` - Game filtering
  - `js/stats.js` - Aggregate stats page (includes HTML/image export functionality)
  - `js/templates.js` - Dynamic template loading system
  - `js/utils.js` - Utility functions
  - `js/app.js` - Application initialization
- **Templates**: HTML templates in `webapp/static/templates/` directory
  - `game-list.html` - Games list view
  - `game-detail.html` - Individual game detail view
  - `aggregate-stats.html` - Aggregate statistics page (with export buttons)
- **Chart Library**: TradingView Lightweight Charts v4.1.0
- **Export Features**: 
  - HTML export: Standalone HTML file with embedded charts (as base64 images)
  - Image export: PNG export with chart tooltips as visible text (using html2canvas)

**Data Flow (Current)**:
```
Database (PostgreSQL)
  ↓
Backend API (FastAPI)
  ↓
Frontend (JavaScript)
  ↓
Chart Rendering (Lightweight Charts)
```

### Current Data Sources

**ESPN Data**:
- **Historical Loading**: `scripts/load_espn_probabilities_raw_items.py`
  - Loads from JSON files: `data/raw/espn/probabilities/{season}/event_{id}_comp_{id}.json`
  - Stores in: `espn.probabilities_raw_items` table
- **API Endpoint**: Unknown for live data (needs research)
- **Data Format**: 
  - `last_modified_utc`: Timestamp
  - `home_win_percentage`: Float (0-100)
  - `away_win_percentage`: Float (0-100)
  - `game_id`: String

**Kalshi Data**:
- **Historical Loading**: Database tables `kalshi.markets_with_games`, `kalshi.candlesticks`
- **WebSocket API**: Unknown (needs research)
- **Data Format**:
  - `period_ts`: Timestamp
  - `price_close`: Integer (cents, 0-100)
  - `yes_bid_close`: Integer (cents)
  - `yes_ask_close`: Integer (cents)
  - `ticker`: String (market identifier)

### Code Quality Assessment

**Current Implementation Strengths**:
- Modular frontend architecture (separate JS files)
- Caching system in place
- Clean separation of concerns
- Type-safe database queries

**Gaps for Live Features**:
- No WebSocket infrastructure
- No real-time state management
- No connection pooling for live data
- No error recovery for dropped connections
- Stats calculated on-the-fly for in-progress games (not stored in database)
- Decision-weighted metrics require bid/ask data (available in Kalshi candlesticks)

## Technical Assessment

### Design Pattern Analysis

#### Current Patterns

**Pattern 1: RESTful API Pattern**
- **Pattern Category**: Architectural
- **Pattern Intent**: Standard HTTP request/response for data retrieval
- **Implementation**: FastAPI routers with GET endpoints
- **Benefits**: Simple, stateless, cacheable
- **Trade-offs**: Not suitable for real-time updates (requires polling)

**Pattern 2: Client-Side Routing**
- **Pattern Category**: Behavioral
- **Pattern Intent**: Single-page app navigation without full page reloads
- **Implementation**: Hash-based routing (`window.location.hash`)
- **Benefits**: Fast navigation, maintainable state
- **Trade-offs**: Browser history management complexity

**Pattern 3: Decorator Pattern (Caching)**
- **Pattern Category**: Structural
- **Pattern Intent**: Add caching behavior to functions without modifying them
- **Implementation**: `@cached` decorator in `webapp/api/cache.py`
- **Benefits**: Transparent caching, easy to apply
- **Trade-offs**: Not suitable for live data (would cache stale data)

#### Missing Patterns for Live Features

**Pattern 1: Observer Pattern**
- **Why Needed**: Frontend must react to incoming WebSocket messages
- **Implementation**: Event-driven updates to chart and UI components
- **Complexity**: Medium

**Pattern 2: Publisher-Subscriber Pattern**
- **Why Needed**: Backend must broadcast live data to multiple connected clients
- **Implementation**: WebSocket connection manager with topic subscriptions
- **Complexity**: High

**Pattern 3: Connection Pool Pattern**
- **Why Needed**: Manage multiple WebSocket connections (ESPN, Kalshi) efficiently
- **Implementation**: Connection pool with automatic reconnection
- **Complexity**: Medium

### Algorithm Analysis

#### Current Algorithms

**Algorithm 1: Time Alignment**
- **Algorithm Name**: Wall-clock time alignment
- **Algorithm Type**: Data transformation
- **Big O Notation**: 
  - Time Complexity: O(n + m) where n = ESPN points, m = Kalshi candles
  - Space Complexity: O(n + m)
- **Description**: Aligns ESPN and Kalshi timestamps to game timeline
- **Use Case**: Historical game data visualization
- **Performance**: Efficient for static data
- **Why This Algorithm**: Preserves relative timing while aligning to game start

**Algorithm 2: Data Deduplication**
- **Algorithm Name**: Timestamp-based deduplication
- **Algorithm Type**: Data cleaning
- **Big O Notation**:
  - Time Complexity: O(n log n) for sorting + O(n) for deduplication
  - Space Complexity: O(n)
- **Description**: Removes duplicate timestamps, keeping latest value
- **Use Case**: Chart data preparation
- **Performance**: Efficient for historical data
- **Why This Algorithm**: Lightweight Charts requires strictly ascending timestamps

#### New Algorithms Needed

**Algorithm 1: Incremental Chart Updates**
- **Algorithm Name**: Streaming data merge
- **Algorithm Type**: Data structure (merge)
- **Big O Notation**:
  - Time Complexity: O(1) per update (append to sorted array)
  - Space Complexity: O(n) where n = total data points
- **Description**: Efficiently append new data points to existing chart data
- **Use Case**: Real-time chart updates
- **Performance**: Must be O(1) to avoid UI lag
- **Why This Algorithm**: Chart library supports incremental updates via `series.updateData()`

**Algorithm 2: Connection State Management**
- **Algorithm Name**: State machine for WebSocket connections
- **Algorithm Type**: State management
- **Big O Notation**:
  - Time Complexity: O(1) for state transitions
  - Space Complexity: O(1) per connection
- **Description**: Manage connection lifecycle (connecting, connected, reconnecting, disconnected)
- **Use Case**: Robust WebSocket handling
- **Performance**: Constant time operations
- **Why This Algorithm**: Ensures reliable connections with automatic recovery

### Performance Analysis

#### Baseline Metrics (Current System)
- **Response Time**: 50-200ms for historical game data (cached)
- **Throughput**: ~100 requests/second (estimated)
- **Memory Usage**: ~50-100MB (backend), ~20-30MB (frontend)
- **Database Performance**: Sub-100ms queries (indexed tables)

#### Performance Requirements for Live Features
- **Chart Update Latency**: < 1 second from data arrival to visual update
- **WebSocket Message Processing**: < 100ms per message
- **Concurrent Connections**: Support 50+ simultaneous users
- **Memory Growth**: Bounded (limit historical data points in memory)

#### Bottleneck Analysis

**Primary Bottleneck**: Chart Rendering
- **Issue**: Lightweight Charts may lag with frequent updates
- **Mitigation**: Throttle updates (max 10 updates/second), batch multiple data points
- **File**: `webapp/static/js/chart.js`

**Secondary Bottleneck**: WebSocket Message Queue
- **Issue**: Messages may arrive faster than processing
- **Mitigation**: Message queue with backpressure, drop old messages if queue full
- **File**: New `webapp/api/endpoints/live_data.py`

**Tertiary Bottleneck**: Database Writes (if storing live data)
- **Issue**: Writing every update could be slow
- **Mitigation**: Batch writes, async writes, or skip writes for live-only data
- **File**: New `webapp/api/endpoints/live_data.py`

### Security Analysis

#### Threat Model

**Threat 1: WebSocket DoS Attack**
- **Description**: Malicious client opens many WebSocket connections
- **Severity**: Medium
- **Mitigation**: Connection limits per IP, rate limiting

**Threat 2: Data Injection via WebSocket**
- **Description**: Malicious data sent through WebSocket could corrupt frontend state
- **Severity**: Low-Medium
- **Mitigation**: Input validation, sanitization, type checking

**Threat 3: Unauthorized Access to Live Data**
- **Description**: Users access live data for games they shouldn't see
- **Severity**: Low (public data, but still should validate)
- **Mitigation**: Game ID validation, check game exists and is live

#### Security Controls

**Authentication**: None required (public data)
**Authorization**: None required (public data)
**Data Protection**: Input validation on WebSocket messages
**Input Validation**: Validate game IDs, timestamps, probability values

## Data Source Research Requirements

### ESPN Live Data Source

**Research Questions**:
1. What is the exact endpoint URL for live ESPN win probability data?
2. Is it a REST API or WebSocket?
3. What authentication is required (if any)?
4. What is the data format?
5. What is the update frequency?
6. Are there rate limits?
7. How do we identify which games are currently live?

**Current Knowledge**:
- Historical data loaded from JSON files
- Database table: `espn.probabilities_raw_items`
- Fields: `last_modified_utc`, `home_win_percentage`, `away_win_percentage`
- **Unknown**: Live endpoint URL, update mechanism

**Recommended Research Approach**:
1. Check ESPN API documentation (if available)
2. Inspect network traffic from ESPN website during live game
3. Test known live game endpoints
4. Document endpoint, format, and rate limits

### Kalshi WebSocket API

**Research Questions**:
1. What is the WebSocket endpoint URL?
2. What authentication is required?
3. What is the message format (JSON, binary, etc.)?
4. How do we subscribe to specific markets?
5. What is the message frequency?
6. How do we handle reconnection?
7. Are there connection limits?

**Current Knowledge**:
- Historical data in database: `kalshi.candlesticks`
- Market matching via `kalshi.markets_with_games`
- Ticker format: `KXNBAGAME-{date}{teams}-{team_side}`
- **Unknown**: WebSocket endpoint, authentication, message format

**Recommended Research Approach**:
1. Check Kalshi API documentation
2. Inspect network traffic from Kalshi website during live market
3. Test WebSocket connection with sample code
4. Document connection flow, authentication, and message format

## Recommendations

### Immediate Actions (Priority: High)

**Recommendation 1: Research ESPN Live Data Endpoint**
- **Files to Modify**: None (research only)
- **Estimated Effort**: 4-6 hours
- **Risk Level**: Low
- **Success Metrics**: Documented endpoint URL, data format, and update mechanism
- **Steps**:
  1. Inspect ESPN website network traffic during live game
  2. Identify probability data endpoint
  3. Test endpoint with sample game
  4. Document format and rate limits

**Recommendation 2: Research Kalshi WebSocket API**
- **Files to Modify**: None (research only)
- **Estimated Effort**: 4-6 hours
- **Risk Level**: Low
- **Success Metrics**: Documented WebSocket endpoint, authentication, and message format
- **Steps**:
  1. Check Kalshi API documentation
  2. Inspect Kalshi website WebSocket connections
  3. Test WebSocket connection
  4. Document connection flow and message format

**Recommendation 3: Design Backend Architecture**
- **Files to Create**: 
  - `webapp/api/endpoints/live_games.py` - List live games endpoint
  - `webapp/api/endpoints/live_data.py` - WebSocket handler for live data
  - `webapp/api/websocket_manager.py` - WebSocket connection management
- **Estimated Effort**: 8-10 hours
- **Risk Level**: Medium
- **Success Metrics**: Architecture document, API specifications

### Short-term Improvements (Priority: Medium)

**Recommendation 4: Implement Backend Live Data Infrastructure**
- **Files to Modify/Create**:
  - `webapp/api/endpoints/live_games.py` - GET `/api/live/games`
  - `webapp/api/endpoints/live_data.py` - WebSocket `/ws/live/{game_id}`
  - `webapp/api/websocket_manager.py` - Connection pooling, reconnection logic
  - `webapp/api/main.py` - Register new routers
- **Estimated Effort**: 20-25 hours
- **Risk Level**: Medium-High
- **Success Metrics**: Working endpoints, WebSocket connections, data aggregation

**Recommendation 5: Implement Frontend Live Games Page**
- **Files to Create/Modify**:
  - `webapp/static/js/live.js` - Live games page logic
  - `webapp/static/index.html` - Add live games view HTML
  - `webapp/static/js/routing.js` - Add `#/live` route
  - `webapp/static/js/chart.js` - Add incremental update functions
  - `webapp/static/js/state.js` - Add live game state management
- **Estimated Effort**: 15-20 hours
- **Risk Level**: Medium
- **Success Metrics**: Live games page, chart updates, state management

### Long-term Strategic Changes (Priority: Low)

**Recommendation 6: Performance Optimization**
- **Files to Modify**: All live data files
- **Estimated Effort**: 5-10 hours
- **Risk Level**: Low
- **Success Metrics**: < 1s update latency, support 50+ concurrent users

**Recommendation 7: Error Recovery and Monitoring**
- **Files to Modify**: WebSocket manager, frontend error handling
- **Estimated Effort**: 5-8 hours
- **Risk Level**: Low
- **Success Metrics**: Automatic reconnection, error logging, connection health monitoring

## Design Decision Recommendations

### Design Decision 1: WebSocket vs. Server-Sent Events (SSE) vs. Polling

**Problem Statement**:
- Need to push live data from backend to frontend
- Multiple data sources (ESPN, Kalshi) with different update frequencies
- Must support multiple concurrent games

**Sprint Scope Analysis**:
- **Complexity Assessment**: Medium complexity, affects both backend and frontend
- **Sprint Scope Determination**: Single Sprint (part of backend infrastructure)
- **Scope Justification**: Core infrastructure decision, affects all subsequent work

**Multiple Solution Analysis**:

**Option 1: HTTP Polling**
- **Design Pattern**: None (standard REST)
- **Algorithm**: O(1) per poll request
- **Implementation Complexity**: Low (2-3 hours)
- **Maintenance Overhead**: Low (standard HTTP)
- **Scalability**: Poor (high server load with many clients)
- **Cost-Benefit**: Low cost, Low benefit (inefficient for real-time)
- **Over-Engineering Risk**: None (too simple)
- **Rejected**: Too inefficient, high latency, high server load

**Option 2: Server-Sent Events (SSE)**
- **Design Pattern**: Observer Pattern (one-way)
- **Algorithm**: O(1) per message push
- **Implementation Complexity**: Medium (4-6 hours)
- **Maintenance Overhead**: Low (standard HTTP)
- **Scalability**: Good (efficient one-way push)
- **Cost-Benefit**: Medium cost, Medium benefit
- **Over-Engineering Risk**: None
- **Rejected**: One-way only, cannot handle bidirectional communication if needed

**Option 3: WebSocket (CHOSEN)**
- **Design Pattern**: Publisher-Subscriber Pattern
- **Algorithm**: O(1) per message (bidirectional)
- **Implementation Complexity**: High (8-10 hours)
- **Maintenance Overhead**: Medium (connection management)
- **Scalability**: Excellent (efficient bidirectional, low overhead)
- **Cost-Benefit**: High cost, High benefit
- **Over-Engineering Risk**: None (appropriate for real-time bidirectional data)
- **Selected**: Best for real-time updates, supports bidirectional communication, industry standard

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 8-10 hours (WebSocket setup, connection management)
- **Learning Curve**: 2-3 hours (WebSocket libraries, FastAPI WebSocket support)
- **Configuration Effort**: 1-2 hours (WebSocket endpoint configuration)

**Maintenance Cost**:
- **Monitoring**: 1 hour/month (connection health, message rates)
- **Updates**: 1 hour/month (library updates, bug fixes)
- **Debugging**: 2-3 hours/incident (connection issues, message parsing)

**Performance Benefit**:
- **Latency**: 90% improvement (real-time vs. polling delay)
- **Throughput**: 10x improvement (efficient push vs. polling)
- **Resource Efficiency**: 80% reduction in HTTP requests

**Maintainability Benefit**:
- **Code Quality**: Clean separation (WebSocket manager module)
- **Developer Productivity**: Reusable connection management
- **System Reliability**: Automatic reconnection, error handling

**Risk Cost**:
- **Risk 1**: Connection drops - Medium risk, mitigated by automatic reconnection
- **Risk 2**: Message queue overflow - Low risk, mitigated by backpressure and message dropping

**Chosen Solution**: WebSocket with FastAPI WebSocket support
- **Implementation**: FastAPI WebSocket endpoints, connection manager class
- **Configuration**: WebSocket route at `/ws/live/{game_id}`
- **Integration**: Integrates with existing FastAPI app, uses same authentication (none) and CORS

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: Real-time updates with minimal latency (< 100ms)
- **Efficiency**: Bidirectional communication, low overhead
- **Scalability**: Supports many concurrent connections efficiently
- **Reliability**: Can implement automatic reconnection and error recovery

**Cons**:
- **Complexity**: More complex than polling (connection management, state handling)
- **Learning Curve**: Team must understand WebSocket lifecycle
- **Resource Usage**: Persistent connections consume server resources (but less than polling)

**Risk Assessment**:
- **Risk 1**: Connection drops during network issues - Mitigation: Automatic reconnection with exponential backoff
- **Risk 2**: Message queue overflow with high-frequency updates - Mitigation: Throttle updates, drop old messages
- **Risk 3**: WebSocket library compatibility issues - Mitigation: Use well-maintained library (FastAPI native support)

### Design Decision 2: Chart Update Strategy

**Problem Statement**:
- Charts must update in real-time as new data arrives
- Updates must be efficient to avoid UI lag
- Must handle high-frequency updates (potentially multiple per second)

**Sprint Scope Analysis**:
- **Complexity Assessment**: Medium complexity, frontend-only
- **Sprint Scope Determination**: Single Sprint (part of frontend implementation)
- **Scope Justification**: Core chart functionality, affects user experience

**Multiple Solution Analysis**:

**Option 1: Full Chart Redraw**
- **Design Pattern**: None
- **Algorithm**: O(n) where n = total data points
- **Implementation Complexity**: Low (1-2 hours)
- **Maintenance Overhead**: Low
- **Scalability**: Poor (slow with many data points)
- **Cost-Benefit**: Low cost, Low benefit (inefficient)
- **Over-Engineering Risk**: None (too simple)
- **Rejected**: Too slow, causes UI lag

**Option 2: Incremental Updates (CHOSEN)**
- **Design Pattern**: Incremental Update Pattern
- **Algorithm**: O(1) per update (append single point)
- **Implementation Complexity**: Medium (3-4 hours)
- **Maintenance Overhead**: Low
- **Scalability**: Excellent (constant time per update)
- **Cost-Benefit**: Medium cost, High benefit
- **Over-Engineering Risk**: None (appropriate complexity)
- **Selected**: Efficient, supported by Lightweight Charts API

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 3-4 hours (incremental update logic, state management)
- **Learning Curve**: 1 hour (Lightweight Charts update API)
- **Configuration Effort**: Minimal

**Performance Benefit**:
- **Update Latency**: 95% improvement (O(1) vs. O(n))
- **UI Responsiveness**: Smooth updates even with 1000+ data points
- **Memory Efficiency**: Only store new points, not full dataset

**Chosen Solution**: Incremental updates using `series.updateData()`
- **Implementation**: Append new data points to chart series
- **Throttling**: Max 10 updates/second to avoid overwhelming UI
- **Batching**: Collect multiple points and update in single batch if needed

**Pros and Cons**:

**Pros**:
- **Performance**: O(1) updates, no UI lag
- **Efficiency**: Only updates new data, not entire chart
- **Scalability**: Works with thousands of data points

**Cons**:
- **Complexity**: Must manage incremental state
- **Edge Cases**: Handle out-of-order updates, duplicate timestamps

## Implementation Plan

### Phase 1: Research and Design (Duration: 8-12 hours)
**Objective**: Understand data sources and design architecture
**Dependencies**: None
**Deliverables**: 
- ESPN live endpoint documentation
- Kalshi WebSocket API documentation
- Architecture design document

#### Tasks
- **Task 1**: Research ESPN live probability endpoint
  - **Files**: None (research)
  - **Effort**: 4-6 hours
  - **Prerequisites**: None
- **Task 2**: Research Kalshi WebSocket API
  - **Files**: None (research)
  - **Effort**: 4-6 hours
  - **Prerequisites**: None

### Phase 2: Backend Infrastructure (Duration: 20-25 hours)
**Objective**: Implement backend endpoints and WebSocket handling
**Dependencies**: Phase 1 (research complete)
**Deliverables**:
- Live games list endpoint
- WebSocket endpoint for live data
- Connection manager
- Data aggregation logic

#### Tasks
- **Task 1**: Create live games endpoint
  - **Files**: `webapp/api/endpoints/live_games.py`
  - **Effort**: 4-5 hours
  - **Prerequisites**: ESPN endpoint research
- **Task 2**: Create WebSocket manager
  - **Files**: `webapp/api/websocket_manager.py`
  - **Effort**: 6-8 hours
  - **Prerequisites**: Kalshi WebSocket research
- **Task 3**: Create live data WebSocket endpoint
  - **Files**: `webapp/api/endpoints/live_data.py`
  - **Effort**: 6-8 hours
  - **Prerequisites**: WebSocket manager
- **Task 4**: Integrate with main app
  - **Files**: `webapp/api/main.py`
  - **Effort**: 2-3 hours
  - **Prerequisites**: All endpoints created
- **Task 5**: Add ESPN live data fetching
  - **Files**: `webapp/api/endpoints/live_data.py` (update)
  - **Effort**: 2-3 hours
  - **Prerequisites**: ESPN endpoint research

### Phase 3: Frontend Implementation (Duration: 15-20 hours)
**Objective**: Build live games page and real-time chart updates
**Dependencies**: Phase 2 (backend complete)
**Deliverables**:
- Live games list page
- Live game detail page
- Real-time chart updates
- State management

#### Tasks
- **Task 1**: Create live games page
  - **Files**: `webapp/static/js/live.js`, `webapp/static/index.html`
  - **Effort**: 4-5 hours
  - **Prerequisites**: Backend live games endpoint
- **Task 2**: Add WebSocket client
  - **Files**: `webapp/static/js/live.js` (update)
  - **Effort**: 3-4 hours
  - **Prerequisites**: Backend WebSocket endpoint
- **Task 3**: Implement chart incremental updates
  - **Files**: `webapp/static/js/chart.js` (update)
  - **Effort**: 4-5 hours
  - **Prerequisites**: WebSocket client
- **Task 4**: Add routing for live games
  - **Files**: `webapp/static/js/routing.js` (update)
  - **Effort**: 2-3 hours
  - **Prerequisites**: Live games page
- **Task 5**: Add state management for live games
  - **Files**: `webapp/static/js/state.js` (update)
  - **Effort**: 2-3 hours
  - **Prerequisites**: All live features

### Phase 4: Testing and Optimization (Duration: 5-15 hours)
**Objective**: Test, optimize, and polish live features
**Dependencies**: Phase 3 (frontend complete)
**Deliverables**:
- Tested live features
- Performance optimizations
- Error handling
- Documentation

#### Tasks
- **Task 1**: Integration testing
  - **Files**: All
  - **Effort**: 2-4 hours
  - **Prerequisites**: All features complete
- **Task 2**: Performance optimization
  - **Files**: All live files
  - **Effort**: 2-4 hours
  - **Prerequisites**: Integration testing
- **Task 3**: Error handling and recovery
  - **Files**: WebSocket manager, frontend
  - **Effort**: 2-4 hours
  - **Prerequisites**: Integration testing
- **Task 4**: Documentation
  - **Files**: README updates
  - **Effort**: 1-3 hours
  - **Prerequisites**: All features complete

## Risk Assessment

### Technical Risks

**Risk 1: ESPN Live Endpoint Not Available**
- **Probability**: Medium
- **Impact**: High (blocks entire feature)
- **Mitigation**: 
  - Research alternative endpoints
  - Fall back to polling ESPN website if needed
  - Consider scraping as last resort
- **Contingency**: Implement polling-based solution if WebSocket/API unavailable

**Risk 2: Kalshi WebSocket API Changes**
- **Probability**: Low-Medium
- **Impact**: High (breaks live Kalshi data)
- **Mitigation**:
  - Document API thoroughly
  - Implement version detection
  - Add error handling for unexpected messages
- **Contingency**: Fall back to polling Kalshi API if WebSocket breaks

**Risk 3: Performance Issues with High Update Frequency**
- **Probability**: Medium
- **Impact**: Medium (poor user experience)
- **Mitigation**:
  - Throttle updates (max 10/second)
  - Batch multiple points
  - Optimize chart rendering
- **Contingency**: Reduce update frequency, add user control

**Risk 4: WebSocket Connection Reliability**
- **Probability**: Medium
- **Impact**: Medium (users lose live updates)
- **Mitigation**:
  - Automatic reconnection with exponential backoff
  - Connection health monitoring
  - Graceful degradation to polling
- **Contingency**: Fall back to polling if WebSocket consistently fails

### Business Risks

**Risk 1: External API Rate Limits**
- **Probability**: Medium
- **Impact**: Medium (limited functionality)
- **Mitigation**:
  - Respect rate limits
  - Implement request queuing
  - Cache where possible
- **Contingency**: Reduce update frequency, prioritize critical games

**Risk 2: Data Accuracy Issues**
- **Probability**: Low
- **Impact**: High (user trust)
- **Mitigation**:
  - Validate all incoming data
  - Compare with historical data format
  - Add data quality checks
- **Contingency**: Alert on data anomalies, pause updates if suspicious

### Resource Risks

**Risk 1: Development Time Overrun**
- **Probability**: Medium
- **Impact**: Medium (delayed release)
- **Mitigation**:
  - Break into smaller sprints
  - Prioritize core features
  - Regular progress reviews
- **Contingency**: Defer non-essential features, focus on MVP

**Risk 2: Server Resource Constraints**
- **Probability**: Low
- **Impact**: Medium (performance degradation)
- **Mitigation**:
  - Monitor connection counts
  - Implement connection limits
  - Optimize message processing
- **Contingency**: Scale server resources, implement connection queuing

## Success Metrics and Monitoring

### Performance Metrics
- **Chart Update Latency**: Target < 1 second (from data arrival to visual update)
- **WebSocket Message Processing**: Target < 100ms per message
- **Concurrent Connections**: Support 50+ simultaneous users
- **Memory Usage**: Bounded growth (limit historical points in memory)

### Quality Metrics
- **Connection Uptime**: Target 99%+ (automatic reconnection on failures)
- **Data Accuracy**: 100% match with historical data format
- **Error Rate**: < 1% of messages fail to process

### Business Metrics
- **User Engagement**: Track live game page views and time spent
- **Feature Adoption**: % of users who use live games feature
- **User Satisfaction**: Feedback on real-time update quality

### Monitoring Strategy
- **Real-time Monitoring**: 
  - WebSocket connection count
  - Message processing rate
  - Chart update latency
  - Error rates
- **Alert Thresholds**:
  - Connection drop rate > 5%
  - Update latency > 2 seconds
  - Error rate > 1%
- **Reporting**: Daily summary of connection health and performance

## Live Games Stats Considerations

### Real-time Stats Calculation

**For Live Games**:
- Stats are calculated on-the-fly (not stored in database until game completes)
- Decision-weighted metrics are particularly valuable for live games:
  - **Time-weighted Brier**: Only scores when Kalshi bid/ask exists (market is active)
  - **Distance-weighted MAE**: Focuses on uncertain predictions (near 0.5) where disagreements matter most
  - **EV-positive disagreements**: Identifies betting opportunities in real-time
- Time-sliced metrics update as game progresses (Q1 → Halftime → Q4 → Final 2 minutes)
- Reliability curves can be calculated incrementally as more data arrives

**Implementation Notes**:
- Decision-weighted metrics require `yes_bid_close` and `yes_ask_close` from Kalshi WebSocket messages
- Stats endpoint (`/api/games/{game_id}/stats`) already supports on-the-fly calculation for in-progress games
- For live games, stats should be recalculated periodically (e.g., every 30 seconds) or on-demand
- Consider caching stats for short periods (e.g., 10-30 seconds) to avoid excessive computation during live games

**Performance Considerations**:
- Decision-weighted metrics calculation is O(n) where n = aligned data points
- For live games, n grows over time, but calculation remains efficient
- Recommend calculating stats every 30-60 seconds rather than on every data point update

## Appendices

### Appendix A: Current Code References

**Backend Endpoints**:
- `webapp/api/endpoints/games.py` - Historical games list
- `webapp/api/endpoints/probabilities.py` - Historical probability data
- `webapp/api/endpoints/metadata.py` - Game metadata
- `webapp/api/endpoints/stats.py` - Individual game statistics
- `webapp/api/endpoints/aggregate_stats.py` - Aggregate statistics across all games
- `webapp/api/main.py` - FastAPI app setup
- `webapp/api/db.py` - Database connection utilities (uses `DATABASE_URL` env var)
- `webapp/api/cache.py` - Caching system with file persistence and background refresh

**Frontend Modules**:
- `webapp/static/js/chart.js` - Chart rendering (Lightweight Charts)
- `webapp/static/js/routing.js` - URL routing
- `webapp/static/js/state.js` - State management
- `webapp/static/js/templates.js` - Dynamic template loading
- `webapp/static/js/stats.js` - Aggregate stats page with export functionality
- `webapp/static/js/ui.js` - UI rendering
- `webapp/static/js/api.js` - API client functions
- `webapp/static/index.html` - Main HTML page
- `webapp/static/templates/` - HTML template files for views

**Database Schema**:
- `espn.probabilities_raw_items` - ESPN probability data
- `espn.scoreboard_games` - Game metadata
- `espn.prob_event_state` - ESPN game state data
- `kalshi.candlesticks` - Kalshi market data (includes bid/ask for decision-weighted metrics)
- `kalshi.markets_with_games` - Market-to-game mapping
- `derived.game_stats` - Pre-calculated statistics for completed games (persistent storage)

### Appendix B: Research Checklist

**ESPN Live Data**:
- [ ] Identify endpoint URL
- [ ] Document authentication (if any)
- [ ] Document data format
- [ ] Test with live game
- [ ] Document rate limits
- [ ] Document update frequency

**Kalshi WebSocket**:
- [ ] Identify WebSocket endpoint URL
- [ ] Document authentication
- [ ] Document message format
- [ ] Test connection
- [ ] Document subscription mechanism
- [ ] Document reconnection behavior

### Appendix C: Technology Stack

**Backend**:
- FastAPI (Python web framework)
- WebSocket support (FastAPI native)
- PostgreSQL (database)
- psycopg (database driver)

**Frontend**:
- Vanilla JavaScript (no framework)
- TradingView Lightweight Charts v4.1.0
- Native WebSocket API

**Infrastructure**:
- Python 3.11+
- Node.js (for Kalshi scripts, if needed)
- PostgreSQL 16
- **Environment Variables**:
  - `DATABASE_URL` - PostgreSQL connection string (default: `postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse`)
    - Configured in `.zshrc` for local development
    - Used by `webapp/api/db.py` for all database connections
  - `DEBUG_MODE` - Enable verbose debug logging (optional)
  - `PRELOAD_CACHE` - Control cache preloading on server startup (optional)

### Appendix D: Glossary

- **WebSocket**: Bidirectional communication protocol over TCP
- **SSE (Server-Sent Events)**: One-way server-to-client push protocol
- **Incremental Update**: Adding new data points without redrawing entire chart
- **Connection Pool**: Managing multiple WebSocket connections efficiently
- **Backpressure**: Handling message queue overflow by dropping old messages
- **Throttling**: Limiting update frequency to avoid overwhelming UI

---

## Document Validation

This analysis follows the standards in `ANALYSIS_STANDARDS.md` and provides:
- Evidence-based analysis with code references
- Design pattern and algorithm analysis with Big O notation
- Pros/cons for each design decision
- Comprehensive risk assessment
- Detailed implementation plan
- Success metrics and monitoring strategy

