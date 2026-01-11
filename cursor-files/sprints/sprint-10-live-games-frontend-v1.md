# Sprint 10 - Live Games Frontend Implementation

**Date**: 2025-01-28  
**Sprint Duration**: 2-3 days (15-20 hours total)  
**Sprint Goal**: Implement frontend live games page with real-time chart updates, WebSocket client integration, and state management for multiple live games.  
**Current Status**: Not Started  
**Target Status**: Frontend can display live games, connect to WebSocket, and update charts in real-time.  
**Team Size**: 1  
**Sprint Lead**: Adam Voliva  

## Sprint Standards Reference

This sprint follows `cursor-files/templates/SPRINT_STANDARDS.md` and `cursor-files/templates/SPRINT_TEMPLATE.md`.

## Pre-Sprint Code Quality Baseline

### Backend Dependencies (Evidence)
- **Command**: `curl http://localhost:8000/api/live/games | jq '.'`
- **Expected Output**: JSON with `games` array (may be empty if no live games)
- **Prerequisite**: Sprint 09 (backend infrastructure) must be complete

### WebSocket Endpoint Test (Evidence)
- **Command**: `python -c "import asyncio; import websockets; asyncio.run(websockets.connect('ws://localhost:8000/ws/live/0022400196').__aenter__())"`
- **Expected Output**: Connection established (no error)
- **Prerequisite**: Sprint 09 WebSocket endpoint must be working

### Current Frontend Structure (Evidence)
- **File**: `webapp/static/index.html` - Main HTML page
- **File**: `webapp/static/js/routing.js` - Hash-based routing
- **File**: `webapp/static/js/chart.js` - Lightweight Charts integration
- **File**: `webapp/static/js/state.js` - Application state management
- **File**: `webapp/static/js/templates.js` - Template loading system

## Database Evidence Template

This sprint does not directly interact with the database. All data comes via WebSocket from backend.

## Git Usage Restrictions

This sprint does not use git commands.

## Sprint Overview

### Business Context
- **Business Driver**: Provide users with real-time visualization of live NBA games with ESPN win probabilities and Kalshi market prices, enabling live engagement and decision-making.
- **Success Criteria**: 
  - Users can view list of currently live games
  - Users can select a live game and see real-time chart updates
  - Charts update smoothly as new data arrives
  - Multiple live games can be viewed (switching between games)
  - WebSocket connections are managed properly (cleanup on navigation)

### Technical Context

#### Current System State (Evidence-backed)
- **Frontend Architecture**: Vanilla JavaScript with modular files
  - **File**: `webapp/static/index.html:39-49` - Module loading
  - **Pattern**: Modular JavaScript Pattern
  - **Routing**: Hash-based client-side routing
  - **File**: `webapp/static/js/routing.js:9-19` - Route parsing
  - **Pattern**: Router Pattern for client-side navigation
  - **Algorithm**: Hash-based routing
  - **Big O**: O(1) for route operations
- **Chart Library**: TradingView Lightweight Charts v4.1.0
  - **File**: `webapp/static/js/chart.js:43-137` - Chart creation
  - **Pattern**: Factory Pattern for chart creation
  - **Algorithm**: Lightweight Charts initialization
  - **Big O**: O(n) where n = number of data points (initial render)
  - **Note**: Currently only supports static data (full redraw)
- **State Management**: Simple object-based singleton
  - **File**: `webapp/static/js/state.js:9-26` - AppState object
  - **Pattern**: Singleton Pattern for global state
  - **Algorithm**: Simple object-based state storage
  - **Big O**: O(1) for state access
- **Template System**: Dynamic template loading
  - **File**: `webapp/static/js/templates.js:9-66` - Template loader
  - **Pattern**: Template Method Pattern
  - **Algorithm**: Async template loading and DOM insertion
  - **Big O**: O(1) per template load

#### Target System State
- **Live Games Page**: New view at `#/live` route
- **Live Game Detail**: View at `#/live/{game_id}` route
- **WebSocket Client**: Connection management and message handling
- **Incremental Chart Updates**: Real-time chart updates without full redraw
- **State Management**: Live game state tracking and cleanup

### Sprint Scope
- **In Scope**:
  - Create live games list page (`#/live` route)
  - Create live game detail page (`#/live/{game_id}` route)
  - Implement WebSocket client for live data
  - Implement incremental chart updates (no full redraw)
  - Add live game state management
  - Handle WebSocket connection lifecycle (connect, disconnect, reconnect)
  - Add UI indicators for connection status
  - Handle navigation between live games (cleanup old connections)
- **Out of Scope**:
  - Backend implementation (Sprint 09)
  - Historical game viewing (already exists)
  - Authentication/authorization (not needed)
  - Mobile responsiveness improvements (future)
- **Constraints**:
  - Must work with existing routing system
  - Must use existing chart library (Lightweight Charts)
  - Must follow existing code patterns and structure
  - Must handle connection drops gracefully

## Design Decisions

### Design Decision 1: Chart Update Strategy

**Problem Statement**: Charts must update in real-time as new data arrives, updates must be efficient to avoid UI lag, and must handle high-frequency updates (potentially multiple per second).

**Chosen Solution**: Incremental updates using `series.updateData()`

**Design Pattern**: Incremental Update Pattern  
**Algorithm**: O(1) per update (append single point)  
**Implementation Complexity**: Medium (3-4 hours)  
**Maintenance Overhead**: Low  
**Scalability**: Excellent (constant time per update)  

**Pros**:
- Performance: O(1) updates, no UI lag
- Efficiency: Only updates new data, not entire chart
- Scalability: Works with thousands of data points
- Supported by Lightweight Charts API

**Cons**:
- Complexity: Must manage incremental state
- Edge Cases: Handle out-of-order updates, duplicate timestamps

**Rejected Alternatives**:
- **Full Chart Redraw**: Too slow, causes UI lag (O(n) complexity)

**Implementation Details**:
- Use `series.updateData()` method from Lightweight Charts
- Append new data points to existing series
- Throttle updates to max 10 updates/second
- Batch multiple points if they arrive quickly
- Handle duplicate timestamps (keep latest)

### Design Decision 2: WebSocket Client Architecture

**Problem Statement**: Need to manage WebSocket connections, handle reconnection, and integrate with existing state management.

**Chosen Solution**: WebSocket client module with connection manager

**Design Pattern**: Connection Manager Pattern + Observer Pattern  
**Algorithm**: O(1) for connection operations, O(1) for message handling  
**Implementation Complexity**: Medium (4-5 hours)  
**Maintenance Overhead**: Medium (connection lifecycle)  

**Architecture**:
- Single `WebSocketClient` class managing connections
- Per-game connection instances
- Automatic reconnection with exponential backoff
- Event-based message handling (callbacks)
- Integration with AppState for connection status

**Pros**:
- Clean separation of concerns
- Reusable connection management
- Easy to add new features (message types, error handling)
- Integrates well with existing state management

**Cons**:
- More complex than simple WebSocket usage
- Must handle cleanup properly

**Implementation Details**:
- **File**: `webapp/static/js/websocket.js` (new)
- **Class**: `WebSocketClient`
- **Methods**:
  - `connect(gameId)` - Connect to live game
  - `disconnect()` - Disconnect and cleanup
  - `onMessage(callback)` - Register message handler
  - `onError(callback)` - Register error handler
  - `onReconnect(callback)` - Register reconnection handler
- **State**: Track connection status, reconnection attempts, last message time

### Design Decision 3: Live Game State Management

**Problem Statement**: Need to track live game state, manage multiple games, and handle cleanup when navigating away.

**Chosen Solution**: Extend AppState with live game state

**Design Pattern**: Singleton Pattern (extend existing)  
**Algorithm**: O(1) for state access and updates  
**Implementation Complexity**: Low (1-2 hours)  
**Maintenance Overhead**: Low  

**Pros**:
- Consistent with existing state management
- Simple to implement
- Easy to access from any module

**Cons**:
- Global state (but acceptable for this use case)

**Implementation Details**:
- Add `liveGames` object to `AppState`
- Structure: `{gameId: {websocket, chartData, lastUpdate, connectionStatus}}`
- Cleanup function to remove game state
- Connection status tracking (connecting, connected, disconnected, reconnecting)

## Sprint Phases

### Phase 1: Live Games List Page (Duration: 4-5 hours)
**Objective**: Create page to display list of currently live games with ability to navigate to game detail.  
**Dependencies**: Backend `/api/live/games` endpoint (Sprint 09)  
**Deliverables**:
- Live games list template
- Live games list JavaScript module
- Routing integration

#### Tasks

**Task 1.1: Create Live Games List Template**
- **Files**: `webapp/static/templates/live-games-list.html` (new)
- **Effort**: 1-2 hours
- **Prerequisites**: None
- **Steps**:
  1. Create HTML template for live games list
  2. Include container for games list
  3. Add loading indicator
  4. Add empty state message
  5. Add refresh button (manual refresh)
  6. Style to match existing templates
- **Success Criteria**:
  - Template loads without errors
  - Matches design of existing game list template
  - Includes all necessary UI elements

**Task 1.2: Create Live Games List JavaScript Module**
- **Files**: `webapp/static/js/live.js` (new)
- **Effort**: 2-3 hours
- **Prerequisites**: Task 1.1, backend endpoint available
- **Design Pattern**: Module Pattern
- **Algorithm**: HTTP polling with configurable interval
- **Big O**: O(n) where n = number of live games
- **Steps**:
  1. Create `live.js` module
  2. Implement `loadLiveGames()` function to fetch from `/api/live/games`
  3. Implement `renderLiveGamesList(games)` function
  4. Implement auto-refresh (poll every 30 seconds)
  5. Add click handlers to navigate to game detail
  6. Handle empty state (no live games)
  7. Handle errors gracefully
- **Success Criteria**:
  - Live games list loads and displays correctly
  - Auto-refresh works (updates every 30 seconds)
  - Navigation to game detail works
  - Errors are handled gracefully

**Task 1.3: Add Routing for Live Games**
- **Files**: `webapp/static/js/routing.js` (update)
- **Effort**: 1 hour
- **Prerequisites**: Tasks 1.1 and 1.2
- **Steps**:
  1. Add `#/live` route to `getRoute()` function
  2. Add `showLiveGamesListView()` function
  3. Add `navigateToLiveGamesList()` function
  4. Update hash change handler
  5. Add link in header/navigation (if applicable)
- **Success Criteria**:
  - `#/live` route works correctly
  - Navigation from other pages works
  - Browser back/forward buttons work

### Phase 2: WebSocket Client Implementation (Duration: 4-5 hours)
**Objective**: Create WebSocket client module with connection management, reconnection logic, and message handling.  
**Dependencies**: Backend WebSocket endpoint (Sprint 09)  
**Deliverables**:
- WebSocket client class
- Connection lifecycle management
- Automatic reconnection

#### Tasks

**Task 2.1: Create WebSocket Client Class**
- **Files**: `webapp/static/js/websocket.js` (new)
- **Effort**: 4-5 hours
- **Prerequisites**: Backend WebSocket endpoint available
- **Design Pattern**: Connection Manager Pattern + Observer Pattern
- **Algorithm**: O(1) for connection operations, O(1) for message handling
- **Big O**: 
  - Connection: O(1)
  - Message handling: O(1)
  - Reconnection: O(1) per attempt
- **Steps**:
  1. Create `WebSocketClient` class
  2. Implement `connect(gameId)` method
  3. Implement `disconnect()` method
  4. Implement message handling (parse JSON, emit events)
  5. Implement error handling
  6. Implement connection status tracking
  7. Add logging for debugging
- **Success Criteria**:
  - Can connect to WebSocket endpoint
  - Receives and parses messages correctly
  - Connection status is tracked
  - Errors are handled gracefully

**Task 2.2: Implement Automatic Reconnection**
- **Files**: `webapp/static/js/websocket.js` (update)
- **Effort**: Included in Task 2.1
- **Prerequisites**: Task 2.1
- **Design Pattern**: Exponential Backoff Pattern
- **Algorithm**: Exponential backoff with max retries
- **Big O**: O(1) per reconnection attempt
- **Steps**:
  1. Implement exponential backoff algorithm (1s, 2s, 4s, 8s, max 30s)
  2. Track reconnection attempts
  3. Implement max retry limit (10 attempts)
  4. Emit reconnection events
  5. Update connection status during reconnection
- **Success Criteria**:
  - Reconnection attempts use exponential backoff
  - Max retries enforced
  - Reconnection events are emitted
  - Connection status updates correctly

**Implementation Notes**:
- WebSocket URL: `ws://localhost:8000/ws/live/{gameId}` (use `window.location.host` for production)
- Message format: JSON with `{espn: [...], kalshi: [...], timestamp: ...}` or `{type: "error", message: "..."}`
- Connection events: `onopen`, `onmessage`, `onerror`, `onclose`
- Reconnection: Attempt on `onclose` if not intentional disconnect

### Phase 3: Incremental Chart Updates (Duration: 4-5 hours)
**Objective**: Implement incremental chart updates so charts update in real-time without full redraw.  
**Dependencies**: Phase 2 (WebSocket client), existing chart.js  
**Deliverables**:
- Incremental update functions in chart.js
- Integration with WebSocket client
- Throttling and batching logic

#### Tasks

**Task 3.1: Add Incremental Update Functions to Chart Module**
- **Files**: `webapp/static/js/chart.js` (update)
- **Effort**: 3-4 hours
- **Prerequisites**: Existing chart.js, Phase 2
- **Design Pattern**: Incremental Update Pattern
- **Algorithm**: O(1) per update (append single point)
- **Big O**: O(1) per data point append
- **Steps**:
  1. Add `updateChartData(espnData, kalshiData)` function
  2. Implement ESPN series updates using `series.updateData()`
  3. Implement Kalshi series updates using `series.updateData()`
  4. Handle duplicate timestamps (keep latest)
  5. Handle out-of-order updates (sort before appending)
  6. Track last update timestamp to avoid duplicates
  7. Add error handling for invalid data
- **Success Criteria**:
  - Chart updates incrementally (no full redraw)
  - Duplicate timestamps handled correctly
  - Out-of-order updates handled correctly
  - No UI lag with frequent updates

**Task 3.2: Implement Update Throttling and Batching**
- **Files**: `webapp/static/js/chart.js` (update)
- **Effort**: 1 hour
- **Prerequisites**: Task 3.1
- **Design Pattern**: Throttle Pattern
- **Algorithm**: O(1) per throttled update
- **Big O**: O(1) for throttling check
- **Steps**:
  1. Implement throttle function (max 10 updates/second)
  2. Batch multiple data points if they arrive quickly
  3. Update chart with batched data
  4. Add configuration for throttle rate
- **Success Criteria**:
  - Updates are throttled to max 10/second
  - Multiple points are batched correctly
  - Chart updates smoothly without overwhelming UI

**Implementation Notes**:
- Use `requestAnimationFrame` for smooth updates
- Throttle using timestamp comparison (last update time)
- Batch points that arrive within 100ms
- Lightweight Charts `updateData()` accepts array of points: `[{time, value}, ...]`
- For ESPN: Update both home and away series
- For Kalshi: Update all Kalshi series (may have multiple markets)

### Phase 4: Live Game Detail Page (Duration: 4-5 hours)
**Objective**: Create live game detail page with real-time chart updates and connection status indicators.  
**Dependencies**: Phases 2 and 3  
**Deliverables**:
- Live game detail template
- Live game detail JavaScript integration
- Connection status UI

#### Tasks

**Task 4.1: Create Live Game Detail Template**
- **Files**: `webapp/static/templates/live-game-detail.html` (new)
- **Effort**: 1-2 hours
- **Prerequisites**: None
- **Steps**:
  1. Create HTML template for live game detail
  2. Include chart container (reuse from game-detail.html)
  3. Add connection status indicator
  4. Add game metadata (teams, scores, time)
  5. Add back button to live games list
  6. Style to match existing game detail template
- **Success Criteria**:
  - Template loads without errors
  - Matches design of existing game detail template
  - Includes connection status indicator

**Task 4.2: Implement Live Game Detail Logic**
- **Files**: `webapp/static/js/live.js` (update)
- **Effort**: 2-3 hours
- **Prerequisites**: Tasks 4.1, 2.1, 3.1
- **Design Pattern**: Module Pattern
- **Algorithm**: O(1) for initialization, O(1) per update
- **Steps**:
  1. Implement `showLiveGameDetail(gameId)` function
  2. Load game metadata from `/api/games/{gameId}/meta`
  3. Initialize chart (reuse existing `createChart()` function)
  4. Connect WebSocket client for game
  5. Set up message handlers to update chart
  6. Update connection status UI
  7. Handle WebSocket errors and reconnection
  8. Clean up on navigation away
- **Success Criteria**:
  - Live game detail page loads correctly
  - Chart initializes and displays
  - WebSocket connects and receives data
  - Chart updates in real-time
  - Connection status updates correctly
  - Cleanup works when navigating away

**Task 4.3: Add Routing for Live Game Detail**
- **Files**: `webapp/static/js/routing.js` (update)
- **Effort**: 1 hour
- **Prerequisites**: Tasks 4.1 and 4.2
- **Steps**:
  1. Add `#/live/{gameId}` route to `getRoute()` function
  2. Add `showLiveGameDetailView(gameId)` function
  3. Add `navigateToLiveGameDetail(gameId)` function
  4. Update hash change handler
- **Success Criteria**:
  - `#/live/{gameId}` route works correctly
  - Navigation from live games list works
  - Browser back/forward buttons work

**Task 4.4: Add Connection Status UI**
- **Files**: `webapp/static/js/live.js` (update), `webapp/static/css/styles.css` (update)
- **Effort**: 1 hour
- **Prerequisites**: Task 4.2
- **Steps**:
  1. Add connection status element to template
  2. Implement status update function (connecting, connected, disconnected, reconnecting)
  3. Add visual indicators (colors, icons, text)
  4. Update status on WebSocket events
  5. Style connection status indicator
- **Success Criteria**:
  - Connection status displays correctly
  - Status updates in real-time
  - Visual indicators are clear and intuitive

### Phase 5: State Management and Cleanup (Duration: 2-3 hours)
**Objective**: Integrate live game state with AppState and ensure proper cleanup when navigating away.  
**Dependencies**: All previous phases  
**Deliverables**:
- Live game state in AppState
- Cleanup functions
- Memory leak prevention

#### Tasks

**Task 5.1: Extend AppState for Live Games**
- **Files**: `webapp/static/js/state.js` (update)
- **Effort**: 1 hour
- **Prerequisites**: None
- **Steps**:
  1. Add `liveGames` object to `AppState`
  2. Structure: `{gameId: {websocket, chartData, lastUpdate, connectionStatus}}`
  3. Add helper functions: `getLiveGameState(gameId)`, `setLiveGameState(gameId, state)`
  4. Add cleanup function: `clearLiveGameState(gameId)`
- **Success Criteria**:
  - Live game state is tracked in AppState
  - Helper functions work correctly
  - State persists during navigation

**Task 5.2: Implement Cleanup on Navigation**
- **Files**: `webapp/static/js/live.js` (update), `webapp/static/js/routing.js` (update)
- **Effort**: 1-2 hours
- **Prerequisites**: Tasks 5.1, 4.2
- **Steps**:
  1. Add cleanup function to disconnect WebSocket when leaving live game
  2. Call cleanup in routing when navigating away from live game
  3. Clear chart data from memory
  4. Remove live game state from AppState
  5. Test for memory leaks (check WebSocket connections are closed)
- **Success Criteria**:
  - WebSocket disconnects when navigating away
  - Chart data is cleared
  - State is removed from AppState
  - No memory leaks (connections are properly closed)

**Implementation Notes**:
- Cleanup should be called in `routing.js` when route changes
- Check if leaving live game route before cleanup
- Use WebSocket `close()` method to disconnect
- Clear any intervals/timeouts related to live game

## Sprint Backlog

### Epic 1: Live Games List
- [ ] **Task 1.1**: Create live games list template (1-2 hours)
- [ ] **Task 1.2**: Create live games list JavaScript module (2-3 hours)
- [ ] **Task 1.3**: Add routing for live games (1 hour)

### Epic 2: WebSocket Client
- [ ] **Task 2.1**: Create WebSocket client class (4-5 hours)
- [ ] **Task 2.2**: Implement automatic reconnection (included in 2.1)

### Epic 3: Chart Updates
- [ ] **Task 3.1**: Add incremental update functions (3-4 hours)
- [ ] **Task 3.2**: Implement update throttling and batching (1 hour)

### Epic 4: Live Game Detail
- [ ] **Task 4.1**: Create live game detail template (1-2 hours)
- [ ] **Task 4.2**: Implement live game detail logic (2-3 hours)
- [ ] **Task 4.3**: Add routing for live game detail (1 hour)
- [ ] **Task 4.4**: Add connection status UI (1 hour)

### Epic 5: State Management
- [ ] **Task 5.1**: Extend AppState for live games (1 hour)
- [ ] **Task 5.2**: Implement cleanup on navigation (1-2 hours)

## Validation Commands

### Validation 1: Live Games List Page
- **Command**: Open browser to `http://localhost:8000/#/live`
- **Expected Output**: Live games list page displays
- **Success Criteria**: 
  - Page loads without errors
  - If live games exist, they are displayed
  - If no live games, empty state message is shown
  - Auto-refresh works (updates every 30 seconds)

### Validation 2: WebSocket Connection
- **Command**: Open browser console, navigate to live game detail, check console logs
- **Expected Output**: WebSocket connection established
- **Success Criteria**: 
  - Connection log appears in console
  - Connection status shows "connected"
  - No connection errors

### Validation 3: Chart Updates
- **Command**: Open live game detail, watch chart for 30 seconds
- **Expected Output**: Chart updates in real-time as data arrives
- **Success Criteria**: 
  - Chart updates without full redraw (smooth updates)
  - Updates occur within 1 second of data arrival
  - No UI lag or freezing
  - Both ESPN and Kalshi lines update (if data available)

### Validation 4: Connection Status
- **Command**: Open live game detail, observe connection status indicator
- **Expected Output**: Status shows "connected" when connected
- **Success Criteria**: 
  - Status updates correctly (connecting → connected)
  - Status shows "reconnecting" if connection drops
  - Status shows "disconnected" if connection fails

### Validation 5: Navigation and Cleanup
- **Command**: Open live game detail, navigate to different page, check browser console
- **Expected Output**: WebSocket disconnects, no errors
- **Success Criteria**: 
  - WebSocket close event fires
  - No memory leaks (check DevTools Memory tab)
  - Can navigate back and reconnect successfully

### Validation 6: Multiple Games
- **Command**: Open multiple live games in different tabs
- **Expected Output**: Each tab maintains separate connection
- **Success Criteria**: 
  - Each tab connects independently
  - Each tab receives updates for its game
  - No interference between tabs

## Success Metrics

### Performance Metrics
- **Chart Update Latency**: < 1 second from data arrival to visual update
- **WebSocket Connection Time**: < 500ms to establish connection
- **UI Responsiveness**: No freezing or lag during updates
- **Memory Usage**: Bounded (no memory leaks from WebSocket connections)

### Quality Metrics
- **Connection Reliability**: 99%+ connection success rate
- **Update Accuracy**: Chart data matches backend data
- **Error Handling**: Graceful handling of connection drops and errors

### Functional Metrics
- **Live Game Detection**: Correctly displays all live games
- **Real-time Updates**: Charts update as data arrives
- **Navigation**: Smooth navigation between pages
- **Cleanup**: Proper cleanup when leaving live games

## Risk Mitigation

### Risk 1: Chart Update Performance Issues
- **Probability**: Medium
- **Impact**: Medium (poor user experience)
- **Mitigation**:
  - Use incremental updates (O(1) complexity)
  - Throttle updates to max 10/second
  - Batch multiple points
- **Contingency**: Reduce update frequency, optimize chart rendering

### Risk 2: WebSocket Connection Issues
- **Probability**: Medium
- **Impact**: High (no live updates)
- **Mitigation**:
  - Automatic reconnection with exponential backoff
  - Connection status indicators
  - Graceful error handling
- **Contingency**: Fall back to polling if WebSocket consistently fails

### Risk 3: Memory Leaks from WebSocket Connections
- **Probability**: Low-Medium
- **Impact**: Medium (browser performance degradation)
- **Mitigation**:
  - Proper cleanup on navigation
  - Close WebSocket connections explicitly
  - Remove event listeners
- **Contingency**: Add connection limits, implement connection pooling

### Risk 4: State Management Complexity
- **Probability**: Low
- **Impact**: Low (code maintainability)
- **Mitigation**:
  - Use existing AppState pattern
  - Keep state structure simple
  - Document state management
- **Contingency**: Refactor if state becomes too complex

## Post-Sprint Artifacts

### Documentation
- `webapp/static/templates/live-games-list.html` - Live games list template
- `webapp/static/templates/live-game-detail.html` - Live game detail template
- `webapp/static/js/live.js` - Live games JavaScript module
- `webapp/static/js/websocket.js` - WebSocket client module
- Updated `webapp/static/js/chart.js` - Incremental update functions
- Updated `webapp/static/js/routing.js` - Live games routes
- Updated `webapp/static/js/state.js` - Live game state management

### Code
- All files listed above with full implementation
- Integration with existing frontend architecture

### Testing
- Validation commands executed and documented
- Manual testing in browser

## Notes

- This sprint depends on Sprint 09 (backend infrastructure) being complete
- Chart updates use incremental approach (no full redraw)
- WebSocket client handles reconnection automatically
- State management follows existing patterns
- Consider adding connection limits in production
- Monitor WebSocket connection count and message rates

---

## Document Validation

This sprint plan follows the standards in `ANALYSIS_STANDARDS.md` and provides:
- Evidence-based analysis with code references
- Design pattern and algorithm analysis with Big O notation
- Pros/cons for each design decision
- Comprehensive risk assessment
- Detailed implementation plan with phases and tasks
- Success metrics and validation commands

