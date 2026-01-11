# Sprint 09 - Live Games Backend Infrastructure

**Date**: 2025-01-28  
**Sprint Duration**: 3-4 days (20-25 hours total)  
**Sprint Goal**: Implement backend infrastructure for live games feature including live games detection, WebSocket endpoints, connection management, and real-time data aggregation from ESPN and Kalshi sources.  
**Current Status**: Not Started  
**Target Status**: Backend endpoints and WebSocket infrastructure ready for frontend integration.  
**Team Size**: 1  
**Sprint Lead**: Adam Voliva  

## Sprint Standards Reference

This sprint follows `cursor-files/templates/SPRINT_STANDARDS.md` and `cursor-files/templates/SPRINT_TEMPLATE.md`.

## Pre-Sprint Code Quality Baseline

### Database Connection Test (Evidence)
- **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && ./.venv/bin/python -c "from webapp.api.db import get_db_connection; conn = get_db_connection().__enter__(); print('DB connection OK'); conn.close()"`
- **Expected Output**: `DB connection OK`

### FastAPI Server Health Check (Evidence)
- **Command**: `cd /Users/adamvoliva/Code/bball/webapp && uvicorn api.main:app --reload --port 8000 &` (background)
- **Test**: `curl http://localhost:8000/api/games?limit=1`
- **Expected**: JSON response with games array

### Current Endpoint Verification (Evidence)
- **Command**: `curl http://localhost:8000/api/games/0022400196/probs | jq '.espn | length'`
- **Expected**: Number > 0 (ESPN data points exist)

## Database Evidence Template

This sprint uses PostgreSQL via `DATABASE_URL` for:
- Reading game metadata from `espn.scoreboard_games`
- Reading historical probability data for comparison
- **No database writes** (live data is streamed, not stored)

## Git Usage Restrictions

This sprint does not use git commands.

## Sprint Overview

### Business Context
- **Business Driver**: Enable real-time tracking of live NBA games with ESPN win probabilities and Kalshi market prices, providing users with live engagement and real-time decision-making capabilities.
- **Success Criteria**: 
  - Backend can detect currently live games
  - WebSocket endpoint accepts connections and streams live data
  - Connection manager handles multiple concurrent connections
  - Data aggregation combines ESPN and Kalshi sources in real-time
  - System handles connection drops and reconnection gracefully

### Technical Context

#### Current System State (Evidence-backed)
- **Backend**: FastAPI application with modular router pattern
  - **File**: `webapp/api/main.py:58-83` - Router registration
  - **Pattern**: Modular Router Pattern
  - **Algorithm**: FastAPI router composition
  - **Big O**: O(1) for route registration
- **Database Connection**: Context manager pattern with `DATABASE_URL` env var
  - **File**: `webapp/api/db.py:19-47` - Connection factory
  - **Pattern**: Factory Pattern for database connections
  - **Algorithm**: Connection pooling via psycopg
  - **Big O**: O(1) for connection creation
- **Caching System**: In-memory cache with file persistence
  - **File**: `webapp/api/cache.py` - Caching decorator
  - **Pattern**: Decorator Pattern
  - **Note**: Not suitable for live data (would cache stale data)
- **Historical Data Endpoints**: RESTful GET endpoints
  - **File**: `webapp/api/endpoints/games.py` - Games list
  - **File**: `webapp/api/endpoints/probabilities.py` - Probability time series
  - **Pattern**: RESTful API Pattern
  - **Algorithm**: SQL queries with pagination
  - **Big O**: O(n) where n = number of games/points returned

#### Target System State
- **Live Games Endpoint**: `GET /api/live/games` - Returns currently live games
- **WebSocket Endpoint**: `WS /ws/live/{game_id}` - Streams live probability data
- **WebSocket Manager**: Connection pooling and state management
- **Data Aggregation**: Real-time combination of ESPN and Kalshi data sources
- **Connection Resilience**: Automatic reconnection with exponential backoff

#### Data Source Research Status
- **ESPN Live Endpoint**: ⚠️ **REQUIRES RESEARCH** (see Phase 1)
  - Historical data format known: `espn.probabilities_raw_items` table
  - Live endpoint URL: Unknown
  - Update mechanism: Unknown (HTTP polling vs WebSocket)
- **Kalshi WebSocket API**: ⚠️ **REQUIRES RESEARCH** (see Phase 1)
  - Historical data format known: `kalshi.candlesticks` table
  - WebSocket endpoint: Unknown
  - Authentication: Unknown
  - Message format: Unknown

### Sprint Scope
- **In Scope**:
  - Research ESPN live data endpoint and document findings
  - Research Kalshi WebSocket API and document findings
  - Create `GET /api/live/games` endpoint to list currently live games
  - Create `WS /ws/live/{game_id}` WebSocket endpoint for live data streaming
  - Implement WebSocket connection manager with:
    - Connection pooling for multiple clients
    - Automatic reconnection logic
    - Message queue with backpressure handling
  - Implement real-time data aggregation combining ESPN and Kalshi sources
  - Add connection health monitoring and error handling
- **Out of Scope**:
  - Frontend implementation (separate sprint)
  - Database writes for live data (streaming only)
  - Historical data storage of live streams
  - Authentication/authorization (public data)
- **Constraints**:
  - Must work with existing FastAPI application structure
  - Must use `DATABASE_URL` environment variable for database access
  - Must handle connection drops gracefully
  - Must support multiple concurrent WebSocket connections

## Design Decisions

### Design Decision 1: WebSocket vs. Server-Sent Events (SSE) vs. Polling

**Problem Statement**: Need to push live data from backend to frontend with multiple data sources (ESPN, Kalshi) and different update frequencies.

**Chosen Solution**: WebSocket with FastAPI native support

**Design Pattern**: Publisher-Subscriber Pattern  
**Algorithm**: O(1) per message (bidirectional)  
**Implementation Complexity**: High (8-10 hours)  
**Maintenance Overhead**: Medium (connection management)  
**Scalability**: Excellent (efficient bidirectional, low overhead)  

**Pros**:
- Real-time updates with minimal latency (< 100ms)
- Bidirectional communication, low overhead
- Supports many concurrent connections efficiently
- Can implement automatic reconnection and error recovery
- Industry standard for real-time applications

**Cons**:
- More complex than polling (connection management, state handling)
- Learning curve for WebSocket lifecycle
- Persistent connections consume server resources (but less than polling)

**Risk Assessment**:
- **Risk 1**: Connection drops during network issues
  - **Mitigation**: Automatic reconnection with exponential backoff
- **Risk 2**: Message queue overflow with high-frequency updates
  - **Mitigation**: Throttle updates, drop old messages, implement backpressure
- **Risk 3**: WebSocket library compatibility issues
  - **Mitigation**: Use FastAPI native WebSocket support (well-maintained)

**Rejected Alternatives**:
- **HTTP Polling**: Too inefficient, high latency, high server load
- **Server-Sent Events (SSE)**: One-way only, cannot handle bidirectional communication if needed

### Design Decision 2: Connection Manager Architecture

**Problem Statement**: Need to manage multiple WebSocket connections efficiently, handle reconnections, and aggregate data from multiple sources.

**Chosen Solution**: Centralized WebSocket manager with per-game connection pools

**Design Pattern**: Connection Pool Pattern + Observer Pattern  
**Algorithm**: O(1) for connection operations, O(n) for broadcasting where n = connected clients  
**Implementation Complexity**: Medium-High (6-8 hours)  
**Maintenance Overhead**: Medium (connection lifecycle management)  

**Architecture**:
- Single `WebSocketManager` class managing all connections
- Per-game connection pools (multiple clients can subscribe to same game)
- Publisher-subscriber pattern: ESPN/Kalshi data sources publish to manager, manager broadcasts to subscribers
- Automatic reconnection with exponential backoff
- Message queue with size limits and backpressure

**Pros**:
- Efficient resource usage (single manager instance)
- Supports multiple clients per game
- Centralized error handling and reconnection logic
- Easy to add new data sources

**Cons**:
- Single point of failure (mitigated by graceful degradation)
- More complex than simple per-connection handling

**Implementation Details**:
- **File**: `webapp/api/websocket_manager.py`
- **Class**: `WebSocketManager` (singleton pattern)
- **Methods**:
  - `connect(game_id, websocket)` - Register client connection
  - `disconnect(game_id, websocket)` - Unregister client connection
  - `broadcast(game_id, data)` - Send data to all clients for a game
  - `start_data_source(game_id, source_type)` - Start fetching data for a game
  - `stop_data_source(game_id, source_type)` - Stop fetching data for a game

## Sprint Phases

### Phase 1: Data Source Research and Documentation (Duration: 8-12 hours)
**Objective**: Research and document ESPN live endpoint and Kalshi WebSocket API specifications.  
**Dependencies**: None  
**Deliverables**:
- ESPN live endpoint documentation (URL, format, authentication, rate limits)
- Kalshi WebSocket API documentation (endpoint, auth, message format, subscription)
- Research notes in `cursor-files/research/` directory

#### Tasks

**Task 1.1: Research ESPN Live Probability Endpoint**
- **Files**: `cursor-files/research/espn_live_endpoint.md` (new)
- **Effort**: 4-6 hours
- **Prerequisites**: None
- **Steps**:
  1. Inspect ESPN website network traffic during live game
  2. Identify probability data endpoint URL
  3. Document request format (headers, parameters, authentication)
  4. Test endpoint with sample live game
  5. Document response format and update frequency
  6. Document rate limits and best practices
- **Success Criteria**: 
  - Documented endpoint URL that returns live probability data
  - Working Python code snippet to fetch live data
  - Known update frequency and rate limits

**Task 1.2: Research Kalshi WebSocket API**
- **Files**: `cursor-files/research/kalshi_websocket_api.md` (new)
- **Effort**: 4-6 hours
- **Prerequisites**: None
- **Steps**:
  1. Check Kalshi API documentation (if available)
  2. Inspect Kalshi website WebSocket connections during live market
  3. Document WebSocket endpoint URL
  4. Document authentication mechanism
  5. Document message format (JSON structure)
  6. Document subscription mechanism (how to subscribe to specific markets)
  7. Test WebSocket connection with sample code
  8. Document reconnection behavior and error handling
- **Success Criteria**:
  - Documented WebSocket endpoint URL
  - Working Python code snippet to connect and receive messages
  - Known message format and subscription mechanism
  - Documented authentication requirements

### Phase 2: Live Games Detection Endpoint (Duration: 4-5 hours)
**Objective**: Create endpoint to detect and list currently live NBA games.  
**Dependencies**: Phase 1 (ESPN endpoint research)  
**Deliverables**:
- `GET /api/live/games` endpoint
- Live game detection logic

#### Tasks

**Task 2.1: Create Live Games Endpoint**
- **Files**: `webapp/api/endpoints/live_games.py` (new)
- **Effort**: 4-5 hours
- **Prerequisites**: Phase 1 Task 1.1 (ESPN endpoint research)
- **Design Pattern**: Repository Pattern for data access
- **Algorithm**: HTTP polling ESPN endpoint + database lookup
- **Big O**: O(n) where n = number of live games
- **Steps**:
  1. Create new router file `webapp/api/endpoints/live_games.py`
  2. Implement `GET /api/live/games` endpoint
  3. Query ESPN live games endpoint (from research)
  4. Match ESPN game IDs to database `espn.scoreboard_games` for metadata
  5. Filter to only NBA games
  6. Return list with game metadata (teams, scores, status)
  7. Register router in `webapp/api/main.py`
- **Success Criteria**:
  - Endpoint returns list of currently live games
  - Response includes game_id, teams, scores, status
  - Endpoint handles errors gracefully (no live games, ESPN API down)

**Implementation Notes**:
- Use ESPN endpoint from research to get live game IDs
- Join with `espn.scoreboard_games` for team names and metadata
- Consider caching live games list for 10-30 seconds to reduce ESPN API calls
- Return format: `{games: [{game_id, home_team, away_team, home_score, away_score, status, start_time}], timestamp}`

### Phase 3: WebSocket Manager Implementation (Duration: 6-8 hours)
**Objective**: Create WebSocket connection manager with connection pooling, reconnection logic, and message broadcasting.  
**Dependencies**: None (can start in parallel with Phase 2)  
**Deliverables**:
- `WebSocketManager` class
- Connection lifecycle management
- Automatic reconnection with exponential backoff

#### Tasks

**Task 3.1: Create WebSocket Manager Class**
- **Files**: `webapp/api/websocket_manager.py` (new)
- **Effort**: 6-8 hours
- **Prerequisites**: None
- **Design Pattern**: Singleton Pattern + Connection Pool Pattern + Observer Pattern
- **Algorithm**: O(1) for connection operations, O(n) for broadcasting where n = connected clients
- **Big O**: 
  - Connection registration: O(1)
  - Broadcast: O(n) where n = subscribers per game
  - State transitions: O(1)
- **Steps**:
  1. Create `WebSocketManager` class (singleton)
  2. Implement connection registry (dict mapping game_id -> set of WebSocket connections)
  3. Implement `connect(game_id, websocket)` method
  4. Implement `disconnect(game_id, websocket)` method
  5. Implement `broadcast(game_id, data)` method
  6. Implement connection health monitoring (ping/pong)
  7. Implement automatic cleanup of dead connections
  8. Add logging for connection events
- **Success Criteria**:
  - Manager can handle multiple connections per game
  - Manager broadcasts messages to all subscribers
  - Manager cleans up dead connections automatically
  - Connection events are logged

**Task 3.2: Implement Reconnection Logic**
- **Files**: `webapp/api/websocket_manager.py` (update)
- **Effort**: Included in Task 3.1
- **Prerequisites**: Task 3.1
- **Steps**:
  1. Implement exponential backoff algorithm for reconnection
  2. Track connection state (connecting, connected, reconnecting, disconnected)
  3. Implement max retry limit with graceful degradation
  4. Add reconnection status to connection metadata
- **Success Criteria**:
  - Reconnection attempts use exponential backoff (1s, 2s, 4s, 8s, max 30s)
  - Max retries: 10 attempts before giving up
  - Connection state is tracked and logged

**Implementation Notes**:
- Use `asyncio` for async WebSocket operations
- Store connections in `Dict[str, Set[WebSocket]]` where key is game_id
- Use `weakref` if needed to avoid memory leaks
- Implement connection timeout (close idle connections after 5 minutes)
- Add connection limits per IP (max 10 connections per IP address)

### Phase 4: Live Data WebSocket Endpoint (Duration: 6-8 hours)
**Objective**: Create WebSocket endpoint that streams live probability data for a specific game.  
**Dependencies**: Phase 3 (WebSocket manager), Phase 1 (data source research)  
**Deliverables**:
- `WS /ws/live/{game_id}` endpoint
- Real-time data aggregation from ESPN and Kalshi

#### Tasks

**Task 4.1: Create WebSocket Endpoint**
- **Files**: `webapp/api/endpoints/live_data.py` (new)
- **Effort**: 3-4 hours
- **Prerequisites**: Phase 3 (WebSocket manager)
- **Design Pattern**: WebSocket Handler Pattern
- **Algorithm**: O(1) per message send
- **Big O**: O(1) for connection handling, O(n) for data aggregation where n = data points
- **Steps**:
  1. Create new router file `webapp/api/endpoints/live_data.py`
  2. Implement `WS /ws/live/{game_id}` endpoint using FastAPI WebSocket
  3. Validate game_id exists and game is live
  4. Register connection with WebSocketManager
  5. Send initial data snapshot (if available)
  6. Handle WebSocket disconnect cleanup
  7. Register router in `webapp/api/main.py`
- **Success Criteria**:
  - Endpoint accepts WebSocket connections
  - Connection is registered with manager
  - Disconnect is handled gracefully
  - Invalid game_id returns appropriate error

**Task 4.2: Implement ESPN Live Data Fetching**
- **Files**: `webapp/api/endpoints/live_data.py` (update)
- **Effort**: 2-3 hours
- **Prerequisites**: Phase 1 Task 1.1 (ESPN endpoint research), Task 4.1
- **Design Pattern**: Polling Pattern with async/await
- **Algorithm**: HTTP polling with configurable interval
- **Big O**: O(1) per poll request
- **Steps**:
  1. Implement async function to poll ESPN endpoint (from research)
  2. Parse ESPN response and extract probability data
  3. Transform to match historical data format
  4. Integrate with WebSocketManager to broadcast updates
  5. Handle rate limiting and errors
  6. Implement polling interval (default: 5 seconds, configurable)
- **Success Criteria**:
  - ESPN data is fetched successfully
  - Data format matches historical format
  - Updates are broadcast to WebSocket clients
  - Rate limiting is respected

**Task 4.3: Implement Kalshi WebSocket Data Fetching**
- **Files**: `webapp/api/endpoints/live_data.py` (update)
- **Effort**: 2-3 hours
- **Prerequisites**: Phase 1 Task 1.2 (Kalshi WebSocket research), Task 4.1
- **Design Pattern**: WebSocket Client Pattern
- **Algorithm**: O(1) per message received
- **Big O**: O(1) per message processing
- **Steps**:
  1. Implement async function to connect to Kalshi WebSocket (from research)
  2. Implement subscription to specific market (game_id -> ticker mapping)
  3. Parse incoming WebSocket messages
  4. Transform Kalshi data to match historical format
  5. Integrate with WebSocketManager to broadcast updates
  6. Handle reconnection if Kalshi WebSocket drops
- **Success Criteria**:
  - Kalshi WebSocket connection established
  - Market subscription works correctly
  - Messages are parsed and transformed
  - Updates are broadcast to WebSocket clients
  - Reconnection works if connection drops

**Task 4.4: Implement Data Aggregation**
- **Files**: `webapp/api/endpoints/live_data.py` (update)
- **Effort**: 1-2 hours
- **Prerequisites**: Tasks 4.2 and 4.3
- **Design Pattern**: Data Aggregation Pattern
- **Algorithm**: Time alignment (same as historical data)
- **Big O**: O(n + m) where n = ESPN points, m = Kalshi candles
- **Steps**:
  1. Implement time alignment logic (reuse from `probabilities.py`)
  2. Combine ESPN and Kalshi data into unified format
  3. Handle missing data gracefully (ESPN only, Kalshi only, or both)
  4. Send aggregated data to WebSocket clients
- **Success Criteria**:
  - ESPN and Kalshi data are aligned by timestamp
  - Aggregated format matches historical endpoint format
  - Missing data sources are handled gracefully

**Implementation Notes**:
- WebSocket endpoint should validate game_id before accepting connection
- Use `asyncio.create_task()` to run data fetching in background
- Implement message queue with max size (drop old messages if queue full)
- Throttle updates to max 10 per second to avoid overwhelming clients
- Data format should match `/api/games/{game_id}/probs` response format for consistency

### Phase 5: Integration and Error Handling (Duration: 2-3 hours)
**Objective**: Integrate all components, add comprehensive error handling, and ensure graceful degradation.  
**Dependencies**: Phases 2, 3, 4  
**Deliverables**:
- Integrated system with error handling
- Connection health monitoring
- Graceful degradation when data sources fail

#### Tasks

**Task 5.1: Integrate Components**
- **Files**: `webapp/api/main.py` (update)
- **Effort**: 1 hour
- **Prerequisites**: Phases 2, 3, 4
- **Steps**:
  1. Register `live_games` router in `main.py`
  2. Register `live_data` router in `main.py`
  3. Initialize WebSocketManager on app startup
  4. Cleanup WebSocketManager on app shutdown
  5. Test all endpoints work together
- **Success Criteria**:
  - All routers registered correctly
  - WebSocketManager initialized on startup
  - Cleanup works on shutdown

**Task 5.2: Add Error Handling and Monitoring**
- **Files**: All live data files
- **Effort**: 1-2 hours
- **Prerequisites**: Task 5.1
- **Steps**:
  1. Add try-catch blocks around all data fetching operations
  2. Log errors with appropriate log levels
  3. Send error messages to WebSocket clients when data source fails
  4. Implement connection health checks (ping/pong)
  5. Add metrics logging (connection count, message rate, error rate)
- **Success Criteria**:
  - Errors are caught and logged
  - Clients receive error notifications
  - Connection health is monitored
  - Metrics are logged for monitoring

**Implementation Notes**:
- Use existing logging system (`webapp/api/logging_config.py`)
- Error messages to clients: `{type: "error", message: "...", timestamp: ...}`
- Health check: Send ping every 30 seconds, expect pong within 5 seconds
- Metrics: Log connection count, messages sent/received, errors per minute

## Sprint Backlog

### Epic 1: Data Source Research
- [ ] **Task 1.1**: Research ESPN live probability endpoint (4-6 hours)
- [ ] **Task 1.2**: Research Kalshi WebSocket API (4-6 hours)

### Epic 2: Live Games Detection
- [ ] **Task 2.1**: Create `GET /api/live/games` endpoint (4-5 hours)

### Epic 3: WebSocket Infrastructure
- [ ] **Task 3.1**: Create WebSocket manager class (6-8 hours)
- [ ] **Task 3.2**: Implement reconnection logic (included in 3.1)

### Epic 4: Live Data Streaming
- [ ] **Task 4.1**: Create WebSocket endpoint (3-4 hours)
- [ ] **Task 4.2**: Implement ESPN live data fetching (2-3 hours)
- [ ] **Task 4.3**: Implement Kalshi WebSocket data fetching (2-3 hours)
- [ ] **Task 4.4**: Implement data aggregation (1-2 hours)

### Epic 5: Integration and Polish
- [ ] **Task 5.1**: Integrate components (1 hour)
- [ ] **Task 5.2**: Add error handling and monitoring (1-2 hours)

## Validation Commands

### Validation 1: Live Games Endpoint
- **Command**: `curl http://localhost:8000/api/live/games | jq '.'`
- **Expected Output**: JSON with `games` array (may be empty if no live games)
- **Success Criteria**: 
  - Endpoint returns 200 status
  - Response has `games` array and `timestamp` field
  - If games exist, each has `game_id`, `home_team`, `away_team`, `status`

### Validation 2: WebSocket Connection
- **Command**: `python -c "import asyncio; import websockets; asyncio.run(websockets.connect('ws://localhost:8000/ws/live/0022400196').__aenter__())"`
- **Expected Output**: Connection established (no error)
- **Success Criteria**: 
  - Connection accepted (no connection refused error)
  - If game_id invalid, receives error message and connection closes

### Validation 3: WebSocket Message Reception
- **Command**: Create test script `test_websocket.py`:
```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/live/0022400196"  # Use actual live game_id
    async with websockets.connect(uri) as websocket:
        # Wait for initial message or updates
        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        data = json.loads(message)
        print(f"Received: {data}")
        assert "espn" in data or "kalshi" in data or "error" in data

asyncio.run(test())
```
- **Expected Output**: Receives JSON message with data or error
- **Success Criteria**: 
  - Receives at least one message within 10 seconds
  - Message is valid JSON
  - Message contains expected fields (espn, kalshi, or error)

### Validation 4: Multiple Concurrent Connections
- **Command**: Run 5 concurrent WebSocket connections and verify all receive messages
- **Expected Output**: All 5 connections receive broadcast messages
- **Success Criteria**: 
  - All connections established
  - All receive same broadcast messages
  - No connection drops

### Validation 5: Connection Reconnection
- **Command**: Connect, disconnect, reconnect and verify reconnection works
- **Expected Output**: Reconnection succeeds and data flow resumes
- **Success Criteria**: 
  - Reconnection completes within 30 seconds
  - Data flow resumes after reconnection

## Success Metrics

### Performance Metrics
- **WebSocket Connection Latency**: < 100ms to establish connection
- **Message Broadcast Latency**: < 50ms from data arrival to client delivery
- **Concurrent Connections**: Support 50+ simultaneous connections
- **Memory Usage**: Bounded growth (no memory leaks from connection management)

### Quality Metrics
- **Connection Uptime**: 99%+ (automatic reconnection on failures)
- **Error Rate**: < 1% of messages fail to process
- **Data Accuracy**: Live data format matches historical data format

### Functional Metrics
- **Live Game Detection**: Correctly identifies all currently live games
- **Data Source Integration**: Both ESPN and Kalshi data sources work
- **Graceful Degradation**: System continues working if one data source fails

## Risk Mitigation

### Risk 1: ESPN Live Endpoint Not Available
- **Probability**: Medium
- **Impact**: High (blocks ESPN data)
- **Mitigation**: 
  - Research phase identifies endpoint before implementation
  - Fall back to polling ESPN website if API unavailable
  - System works with Kalshi-only data if ESPN fails
- **Contingency**: Implement polling-based solution if WebSocket/API unavailable

### Risk 2: Kalshi WebSocket API Changes
- **Probability**: Low-Medium
- **Impact**: High (breaks Kalshi data)
- **Mitigation**:
  - Document API thoroughly in research phase
  - Implement version detection
  - Add error handling for unexpected messages
- **Contingency**: Fall back to polling Kalshi API if WebSocket breaks

### Risk 3: Performance Issues with High Update Frequency
- **Probability**: Medium
- **Impact**: Medium (poor user experience)
- **Mitigation**:
  - Throttle updates (max 10/second)
  - Batch multiple points
  - Implement message queue with backpressure
- **Contingency**: Reduce update frequency, add user control

### Risk 4: WebSocket Connection Reliability
- **Probability**: Medium
- **Impact**: Medium (users lose live updates)
- **Mitigation**:
  - Automatic reconnection with exponential backoff
  - Connection health monitoring
  - Graceful degradation to polling (future)
- **Contingency**: Fall back to polling if WebSocket consistently fails

## Post-Sprint Artifacts

### Documentation
- `cursor-files/research/espn_live_endpoint.md` - ESPN endpoint documentation
- `cursor-files/research/kalshi_websocket_api.md` - Kalshi WebSocket documentation
- `webapp/api/endpoints/live_games.py` - Live games endpoint
- `webapp/api/endpoints/live_data.py` - Live data WebSocket endpoint
- `webapp/api/websocket_manager.py` - WebSocket connection manager

### Code
- All files listed above with full implementation
- Integration in `webapp/api/main.py`

### Testing
- Validation commands executed and documented
- Test scripts for WebSocket connections

## Notes

- This sprint focuses on backend infrastructure only
- Frontend implementation will be in a separate sprint
- Database writes are out of scope (streaming only)
- Authentication/authorization not required (public data)
- Consider adding connection limits per IP in production
- Monitor connection count and message rates in production

---

## Document Validation

This sprint plan follows the standards in `ANALYSIS_STANDARDS.md` and provides:
- Evidence-based analysis with code references
- Design pattern and algorithm analysis with Big O notation
- Pros/cons for each design decision
- Comprehensive risk assessment
- Detailed implementation plan with phases and tasks
- Success metrics and validation commands

