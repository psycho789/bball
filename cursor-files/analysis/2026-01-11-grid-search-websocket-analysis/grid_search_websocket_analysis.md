# Analysis: Grid Search WebSocket Implementation

**Date**: Sat Jan 11 2026  
**Status**: Complete  
**Author**: AI Assistant  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Comprehensive analysis of the WebSocket implementation for grid search progress tracking, covering both backend and frontend components

## Executive Summary

### Key Findings
- **Architecture**: Server-sent progress updates via WebSocket with in-memory shared state
- **Backend Pattern**: WebSocket Handler Pattern + Observer Pattern with thread-safe progress tracking
- **Frontend Pattern**: Event-driven WebSocket client with automatic UI updates
- **Synchronization**: Thread-safe dictionary with locks for concurrent access
- **Update Frequency**: 100ms polling interval on server, push-based updates to client
- **Message Format**: JSON with structured progress data

### Critical Components
- **Backend**: `webapp/api/endpoints/grid_search.py` - WebSocket endpoint `/ws/grid-search/{request_id}`
- **Frontend**: `webapp/static/js/grid-search.js` - `connectGridSearchProgress()` function
- **Shared State**: `_grid_search_progress` dictionary with thread-safe locks
- **Background Task**: `_run_grid_search_background()` updates progress state

### Design Decisions
- **Pros**: Real-time updates, reduced HTTP overhead, efficient resource usage, scalable
- **Cons**: Requires persistent connection, more complex error handling, potential connection issues
- **Algorithm**: Change detection with sentinel values for reliable first update
- **Big O Complexity**: O(1) per connection, O(1) per progress update, O(n) for background processing where n = combinations × games

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Backend Implementation](#backend-implementation)
3. [Frontend Implementation](#frontend-implementation)
4. [Message Flow and Lifecycle](#message-flow-and-lifecycle)
5. [Progress Tracking Mechanism](#progress-tracking-mechanism)
6. [Thread Safety and Synchronization](#thread-safety-and-synchronization)
7. [Error Handling](#error-handling)
8. [Design Patterns](#design-patterns)
9. [Performance Characteristics](#performance-characteristics)
10. [Code References](#code-references)

---

## Architecture Overview

### System Components

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Frontend      │         │   Backend API    │         │  Background     │
│   (Browser)     │◄───────►│   (FastAPI)      │◄───────►│  Task Thread    │
│                 │ WebSocket│                 │         │                 │
│  grid-search.js │         │ grid_search.py  │         │ _run_grid_      │
│                 │         │                  │         │ search_background│
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                      │
                                      │ Reads/Writes
                                      ▼
                            ┌──────────────────┐
                            │ Shared State     │
                            │ _grid_search_    │
                            │ progress dict    │
                            │ (thread-safe)    │
                            └──────────────────┘
```

### Communication Flow

1. **User initiates grid search** → Frontend calls `/api/grid-search/run`
2. **Backend starts background task** → Creates entry in `_grid_search_progress`
3. **Frontend connects WebSocket** → `/ws/grid-search/{request_id}`
4. **Background task updates progress** → Writes to `_grid_search_progress`
5. **WebSocket monitors changes** → Polls every 100ms, sends updates on change
6. **Frontend receives updates** → Updates UI in real-time
7. **Task completes** → WebSocket closes, frontend fetches results

---

## Backend Implementation

### WebSocket Endpoint

**Location**: `webapp/api/endpoints/grid_search.py:543-724`

**Endpoint**: `@router.websocket("/ws/grid-search/{request_id}")`

**Function**: `websocket_grid_search_progress(websocket: WebSocket, request_id: str)`

### Key Implementation Details

#### 1. Connection Initialization

```python
# Validate request_id exists or will exist soon
with _grid_search_lock:
    if request_id not in _grid_search_progress:
        # Request might not exist yet if grid search just started
        initial_status = {
            "status": "not_found",
            "current": 0,
            "total": 0,
            "current_combo": ""
        }
    else:
        progress = _grid_search_progress[request_id].copy()
        initial_status = {
            "status": progress.get("status", "unknown"),
            "current": progress.get("current", 0),
            "total": progress.get("total", 0),
            "current_combo": progress.get("current_combo", "")
        }

await websocket.accept()
await websocket.send_json({
    "type": "progress",
    "progress": initial_status
})
```

**Design Decision**: Allows connection before task starts, sends initial state immediately
- **Pros**: Handles race conditions, provides immediate feedback
- **Cons**: May send "not_found" status initially

#### 2. Change Detection Mechanism

**Algorithm**: Sentinel Value Pattern + Field Comparison

```python
# Initialize with sentinel values to ensure first update is always sent
last_progress = {
    "status": None,      # Sentinel: None
    "current": -1,       # Sentinel: -1
    "total": -1,         # Sentinel: -1
    "current_combo": None
}

# Monitor loop (every 100ms)
while True:
    await asyncio.sleep(0.1)
    
    # Read current progress (thread-safe)
    with _grid_search_lock:
        progress = _grid_search_progress[request_id].copy()
        current_progress = {
            "status": progress.get("status", "unknown"),
            "current": progress.get("current", 0),
            "total": progress.get("total", 0),
            "current_combo": current_combo_str
        }
    
    # Compare individual fields
    has_changed = (current_val != last_val or 
                  current_total != last_total or 
                  current_status != last_status or 
                  current_combo != last_combo)
    
    # Force update if sentinel values detected (first check)
    if last_val == -1 or last_total == -1 or last_status is None:
        has_changed = True
```

**Design Decision**: Sentinel values ensure first update is always sent
- **Pros**: Guarantees initial state is sent, handles edge cases
- **Cons**: Slightly more complex comparison logic

**Big O**: O(1) per comparison, O(1) per update send

#### 3. Message Format

**Outgoing Messages** (Server → Client):

```json
{
    "type": "progress",
    "progress": {
        "status": "running" | "complete" | "error" | "not_found",
        "current": 150,
        "total": 1000,
        "current_combo": "entry=0.050, exit=0.010"
    }
}
```

**Incoming Messages** (Client → Server):

```json
{
    "type": "ping"
}
```

**Response**:

```json
{
    "type": "pong",
    "timestamp": 1234567890.123
}
```

#### 4. Connection Lifecycle

1. **Accept**: `await websocket.accept()`
2. **Send Initial State**: Immediate progress snapshot
3. **Monitor Loop**: Check for changes every 100ms
4. **Send Updates**: On detected changes
5. **Handle Ping/Pong**: Connection health checks
6. **Close on Completion**: When status is "complete" or "error"

**Close Codes**:
- `1000`: Normal closure (task completed)
- `1011`: Server error

---

## Frontend Implementation

### WebSocket Client

**Location**: `webapp/static/js/grid-search.js:214-320`

**Function**: `connectGridSearchProgress(requestId)`

### Key Implementation Details

#### 1. Connection Establishment

```javascript
function connectGridSearchProgress(requestId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/grid-search/${requestId}`;
    
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
        console.log(`Grid search progress WebSocket connected: requestId=${requestId}`);
    };
    // ... event handlers
}
```

**Design Decision**: Automatic protocol detection (ws/wss)
- **Pros**: Works in both HTTP and HTTPS environments
- **Cons**: Requires correct protocol detection

#### 2. Message Handling

```javascript
ws.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'progress') {
        const progress = data.progress;
        
        // Update UI
        const current = progress.current || 0;
        const total = progress.total || 1;
        const percent = total > 0 ? Math.round((current / total) * 100) : 0;
        const currentCombo = progress.current_combo || '';
        
        const loadingProgressText = document.getElementById('loadingProgressText');
        if (loadingProgressText) {
            loadingProgressText.textContent = 
                `Processing: ${current}/${total} combinations (${percent}%) ${currentCombo ? '- ' + currentCombo : ''}`;
        }
        
        // Handle completion
        if (progress.status === 'complete') {
            await fetchAndRenderResults(requestId);
        } else if (progress.status === 'error') {
            // Show error, reset UI
        }
    }
};
```

**Design Decision**: Event-driven UI updates
- **Pros**: Reactive, real-time updates, clean separation of concerns
- **Cons**: Requires proper error handling for missing DOM elements

#### 3. Error Handling and Fallback

```javascript
ws.onerror = (error) => {
    console.error(`Grid search progress WebSocket error for ${requestId}:`, error);
    // Fallback: try HTTP endpoint once
    fetch(`/api/grid-search/progress/${requestId}`)
        .then(response => response.json())
        .then(progress => {
            // Update UI with progress
        })
        .catch(err => console.error('Fallback HTTP request also failed:', err));
};
```

**Design Decision**: HTTP fallback on WebSocket error
- **Pros**: Graceful degradation, maintains functionality
- **Cons**: One-time fallback, doesn't retry WebSocket

#### 4. Connection Health

```javascript
// Send ping every 30 seconds to keep connection alive
const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
    } else {
        clearInterval(pingInterval);
    }
}, 30000);

// Clean up ping interval when connection closes
ws.addEventListener('close', () => {
    clearInterval(pingInterval);
});
```

**Design Decision**: Periodic ping to maintain connection
- **Pros**: Keeps connection alive, detects dead connections
- **Cons**: Additional network traffic (minimal)

---

## Message Flow and Lifecycle

### Complete Flow Diagram

```
┌─────────────┐
│   User      │
│  Clicks Run │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Frontend: runGridSearch()          │
│ 1. POST /api/grid-search/run       │
│ 2. Receive request_id              │
│ 3. Call connectGridSearchProgress()│
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Backend: POST /api/grid-search/run │
│ 1. Generate request_id              │
│ 2. Start background thread         │
│ 3. Initialize _grid_search_progress │
│ 4. Return request_id               │
└──────┬──────────────────────────────┘
       │
       ├──────────────────────────────┐
       │                              │
       ▼                              ▼
┌─────────────────────┐    ┌──────────────────────────┐
│ Background Task     │    │ WebSocket Connection     │
│ Thread Starts       │    │ Established              │
│                     │    │                          │
│ 1. Calculate total  │    │ 1. Accept connection    │
│ 2. Update progress  │    │ 2. Send initial state   │
│    dict (thread-    │    │ 3. Start monitoring loop│
│    safe)            │    │    (every 100ms)        │
│ 3. Process combos   │    │                          │
│ 4. Update current   │    │                          │
│    as work done     │    │                          │
└──────┬──────────────┘    └──────┬───────────────────┘
       │                          │
       │                          │ Reads progress
       │                          │ (thread-safe)
       │                          │
       │                          ▼
       │                  ┌──────────────────────┐
       │                  │ Change Detection     │
       │                  │ Compare fields       │
       │                  │ If changed → send    │
       │                  └──────┬───────────────┘
       │                          │
       │                          ▼
       │                  ┌──────────────────────┐
       │                  │ Send JSON Message    │
       │                  │ {type: "progress",   │
       │                  │  progress: {...}}    │
       │                  └──────┬───────────────┘
       │                          │
       │                          ▼
       │                  ┌──────────────────────┐
       │                  │ Frontend Receives    │
       │                  │ Updates UI           │
       │                  └──────────────────────┘
       │
       │ (Task completes)
       │
       ▼
┌─────────────────────┐
│ Update status to    │
│ "complete"          │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ WebSocket detects   │
│ completion          │
│ Closes connection   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Frontend detects     │
│ completion           │
│ Fetches results      │
└─────────────────────┘
```

### Timing Sequence

```
Time    Backend                    Frontend                  Background Task
─────────────────────────────────────────────────────────────────────────────
T+0ms   POST /api/grid-search/run
T+10ms  Start background thread    Receive request_id
T+20ms                              Connect WebSocket        Initialize progress
T+30ms  Accept WebSocket           Receive initial state    Calculate total
T+40ms  Send initial state         Update UI (0%)           Update total in dict
T+50ms                              Display "0/1000"          Start processing
T+100ms Monitor loop (1st check)                           Process combo 1
T+150ms                             Receive update           Update current=50
T+200ms Detect change → send        Update UI (5%)           Process combo 2
T+250ms                             Receive update           Update current=100
...     (continues every 100ms)    (updates as received)    (continues)
T+10s   Task completes             Receive completion       Set status="complete"
T+10.1s Close WebSocket            Fetch results             Store results
T+10.2s                            Render results
```

---

## Progress Tracking Mechanism

### Shared State Structure

**Location**: `webapp/api/endpoints/grid_search.py:110-111`

```python
_grid_search_progress: dict[str, dict] = {}
_grid_search_lock = threading.Lock()
```

**Dictionary Structure**:

```python
_grid_search_progress[request_id] = {
    "status": "running" | "complete" | "error",
    "current": 150,                    # Number of games processed
    "total": 1000,                     # Total games to process
    "current_combo": "entry=0.050, exit=0.010",  # Current parameter combination
    "error": None,                     # Error message if status="error"
    "final_selection": {...},         # Results when complete
    "training_results": [...],
    "validation_results": [...],
    "test_results": [...],
    # ... other result fields
}
```

### Progress Update Logic

**Location**: `webapp/api/endpoints/grid_search.py:208-234`

```python
def process_with_progress(combo):
    entry, exit_val = combo
    
    # Process combination (runs simulation for all games)
    result = process_combination(combo, game_splits, config, dsn, ...)
    
    # Increment by number of games processed
    games_processed = total_games_per_combo  # train + valid + test
    
    with completed_lock:
        completed_counter[0] += games_processed
        current_completed = completed_counter[0]
    
    # Update progress under main lock (thread-safe)
    with _grid_search_lock:
        if request_id in _grid_search_progress:
            _grid_search_progress[request_id]["current"] = current_completed
            _grid_search_progress[request_id]["current_combo"] = f"entry={entry:.3f}, exit={exit_val:.3f}"
    
    return result
```

**Design Decision**: Increment by games per combination, not by combinations
- **Pros**: More granular progress, better user feedback
- **Cons**: Requires calculating total_games_per_combo

**Algorithm**: Thread-safe counter with lock
- **Big O**: O(1) per update

### Initialization Sequence

1. **Background task starts** (`_run_grid_search_background`)
   ```python
   _grid_search_progress[request_id] = {
       "status": "running",
       "current": 0,
       "total": 0,  # Set later
       "current_combo": None
   }
   ```

2. **Calculate total work**
   ```python
   total_work = len(combinations) * total_games_per_combo
   _grid_search_progress[request_id]["total"] = total_work
   ```

3. **Start processing**
   - Each combination processes train + valid + test games
   - Progress increments by `total_games_per_combo` per combination

---

## Thread Safety and Synchronization

### Locking Strategy

**Primary Lock**: `_grid_search_lock` (threading.Lock)

**Usage Pattern**:

```python
# Write operations (background task)
with _grid_search_lock:
    _grid_search_progress[request_id]["current"] = value
    _grid_search_progress[request_id]["total"] = value

# Read operations (WebSocket endpoint)
with _grid_search_lock:
    progress = _grid_search_progress[request_id].copy()  # Copy to avoid holding lock
# Use copied data outside lock
```

**Design Decision**: Copy data outside lock
- **Pros**: Minimizes lock contention, allows concurrent reads
- **Cons**: Slight memory overhead for copying

### Nested Lock Pattern

**Location**: `webapp/api/endpoints/grid_search.py:205-227`

```python
completed_lock = threading.Lock()  # Local lock for counter
completed_counter = [0]  # List to allow modification in nested function

def process_with_progress(combo):
    # ... process combination ...
    
    with completed_lock:  # Inner lock
        completed_counter[0] += games_processed
        current_completed = completed_counter[0]
    
    with _grid_search_lock:  # Outer lock
        _grid_search_progress[request_id]["current"] = current_completed
```

**Design Decision**: Separate locks for different concerns
- **Pros**: Reduces lock contention, allows parallel progress tracking
- **Cons**: More complex locking logic

**Potential Issue**: Lock ordering - always acquire `completed_lock` before `_grid_search_lock` to avoid deadlock

### Race Condition Handling

**Scenario**: WebSocket connects before background task starts

**Solution**:
```python
if request_id not in _grid_search_progress:
    # Allow connection, send "not_found" status
    # Monitoring loop will detect when task starts
    initial_status = {"status": "not_found", ...}
```

**Scenario**: Background task completes before WebSocket connects

**Solution**:
```python
else:
    # Task already exists, send current state
    progress = _grid_search_progress[request_id].copy()
    initial_status = {...}  # Includes final status
```

---

## Error Handling

### Backend Error Handling

#### Connection Errors

```python
try:
    await websocket.accept()
    # ... monitoring loop ...
except WebSocketDisconnect:
    logger.info(f"WebSocket disconnected: {request_id}")
    break
except Exception as e:
    logger.error(f"Error in WebSocket: {e}", exc_info=True)
    try:
        await websocket.send_json({
            "type": "error",
            "message": f"Error: {str(e)}"
        })
    except Exception:
        pass
    await asyncio.sleep(1)  # Wait before retrying
```

**Design Decision**: Log and continue, send error message to client
- **Pros**: Graceful error handling, client receives feedback
- **Cons**: May continue in error state

#### Background Task Errors

```python
try:
    # ... grid search execution ...
except Exception as e:
    logger.error(f"Grid search {request_id} failed: {e}", exc_info=True)
    with _grid_search_lock:
        if request_id in _grid_search_progress:
            _grid_search_progress[request_id]["status"] = "error"
            _grid_search_progress[request_id]["error"] = str(e)
```

**Design Decision**: Update status to "error", preserve error message
- **Pros**: WebSocket will detect and notify client
- **Cons**: Error details may be lost if not properly serialized

### Frontend Error Handling

#### WebSocket Connection Errors

```javascript
ws.onerror = (error) => {
    console.error(`Grid search progress WebSocket error:`, error);
    // Fallback to HTTP endpoint
    fetch(`/api/grid-search/progress/${requestId}`)
        .then(response => response.json())
        .then(progress => {
            // Update UI
        })
        .catch(err => console.error('Fallback also failed:', err));
};
```

**Design Decision**: HTTP fallback on WebSocket error
- **Pros**: Graceful degradation
- **Cons**: One-time fallback, no retry logic

#### Message Parsing Errors

```javascript
ws.onmessage = async (event) => {
    try {
        const data = JSON.parse(event.data);
        // ... handle message ...
    } catch (error) {
        console.error('Error parsing WebSocket message:', error, event.data);
    }
};
```

**Design Decision**: Try-catch around JSON parsing
- **Pros**: Prevents crashes on malformed messages
- **Cons**: Silent failure, may miss important updates

---

## Design Patterns

### 1. WebSocket Handler Pattern

**Implementation**: Dedicated async function handles WebSocket lifecycle

**Benefits**:
- Clean separation of concerns
- Easy to test and maintain
- Standard FastAPI pattern

**Code Reference**: `webapp/api/endpoints/grid_search.py:543-724`

### 2. Observer Pattern

**Implementation**: WebSocket monitors shared state, sends updates on changes

**Benefits**:
- Decouples background task from client communication
- Multiple clients can observe same progress
- Scalable architecture

**Code Reference**: Monitoring loop in `websocket_grid_search_progress()`

### 3. Sentinel Value Pattern

**Implementation**: Initialize `last_progress` with sentinel values (-1, None)

**Benefits**:
- Guarantees first update is always sent
- Handles edge cases reliably
- Simplifies comparison logic

**Code Reference**: `webapp/api/endpoints/grid_search.py:603-609`

### 4. Thread-Safe Singleton Pattern

**Implementation**: Shared dictionary with locks for concurrent access

**Benefits**:
- Single source of truth
- Thread-safe operations
- Efficient memory usage

**Code Reference**: `_grid_search_progress` dictionary with `_grid_search_lock`

### 5. Event-Driven Pattern (Frontend)

**Implementation**: WebSocket events trigger UI updates

**Benefits**:
- Reactive UI updates
- Clean separation of data and presentation
- Easy to extend

**Code Reference**: `webapp/static/js/grid-search.js:227-276`

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| WebSocket connection | O(1) | Single connection establishment |
| Progress update detection | O(1) | Field comparison, constant time |
| Progress update send | O(1) | JSON serialization, network send |
| Background task progress update | O(1) | Dictionary write with lock |
| Change detection loop | O(1) per iteration | Runs every 100ms |
| Frontend message handling | O(1) | DOM update, constant time |

### Space Complexity

| Component | Complexity | Notes |
|-----------|------------|-------|
| `_grid_search_progress` dict | O(n) | n = number of active grid searches |
| Per-request progress entry | O(1) | Fixed-size dictionary |
| WebSocket connection | O(1) | Single connection per client |
| Frontend WebSocket object | O(1) | Single object per connection |

### Resource Usage

**Backend**:
- **CPU**: Minimal - 100ms polling interval, lightweight comparisons
- **Memory**: O(n) where n = active grid searches
- **Network**: ~100 bytes per update message, sent only on changes

**Frontend**:
- **CPU**: Minimal - event-driven updates
- **Memory**: O(1) - single WebSocket object
- **Network**: ~30 bytes ping every 30 seconds

### Scalability Considerations

**Current Limitations**:
- One WebSocket connection per request_id
- In-memory storage (lost on server restart)
- No connection pooling or multiplexing

**Potential Improvements**:
- Redis-backed progress storage for persistence
- WebSocket connection pooling
- Message batching for high-frequency updates
- Compression for large result sets

---

## Code References

### Backend Files

**Main WebSocket Endpoint**:
```543:724:webapp/api/endpoints/grid_search.py
@router.websocket("/ws/grid-search/{request_id}")
async def websocket_grid_search_progress(websocket: WebSocket, request_id: str):
    # ... WebSocket implementation ...
```

**Progress Tracking State**:
```108:111:webapp/api/endpoints/grid_search.py
# In-memory progress tracking (thread-safe)
_grid_search_progress: dict[str, dict] = {}
_grid_search_lock = threading.Lock()
```

**Background Task Progress Updates**:
```208:234:webapp/api/endpoints/grid_search.py
def process_with_progress(combo):
    # ... process combination ...
    with _grid_search_lock:
        _grid_search_progress[request_id]["current"] = current_completed
        _grid_search_progress[request_id]["current_combo"] = f"entry={entry:.3f}, exit={exit_val:.3f}"
```

**Initialization**:
```140:198:webapp/api/endpoints/grid_search.py
def _run_grid_search_background(...):
    with _grid_search_lock:
        _grid_search_progress[request_id] = {
            "status": "running",
            "current": 0,
            "total": 0,
            ...
        }
    # ... calculate total ...
    with _grid_search_lock:
        _grid_search_progress[request_id]["total"] = total_work
```

### Frontend Files

**WebSocket Client Function**:
```214:320:webapp/static/js/grid-search.js
function connectGridSearchProgress(requestId) {
    const ws = new WebSocket(url);
    ws.onmessage = async (event) => {
        // ... handle progress updates ...
    };
    // ... error handling, ping/pong ...
}
```

**Grid Search Initiation**:
```148:202:webapp/static/js/grid-search.js
async function runGridSearch() {
    // ... collect parameters ...
    const response = await fetch(`/api/grid-search/run?${queryParams.toString()}`, {
        method: 'POST'
    });
    const data = await response.json();
    const requestId = data.request_id;
    
    // Connect to WebSocket for real-time progress updates
    const progressWebSocket = connectGridSearchProgress(requestId);
}
```

---

## Summary

### Architecture Strengths

1. **Real-time Updates**: WebSocket provides instant progress feedback
2. **Thread Safety**: Proper locking ensures data consistency
3. **Error Resilience**: Multiple error handling layers
4. **Scalable Design**: Observer pattern allows multiple clients
5. **Clean Separation**: Backend and frontend are well-decoupled

### Areas for Improvement

1. **Persistence**: Add Redis/database storage for progress state
2. **Reconnection Logic**: Implement automatic reconnection on frontend
3. **Message Batching**: Batch updates for high-frequency scenarios
4. **Connection Pooling**: Support multiple WebSocket connections efficiently
5. **Compression**: Compress large result sets before sending

### Recommendations

1. **Monitoring**: Add metrics for WebSocket connections, message rates
2. **Testing**: Add unit tests for change detection logic
3. **Documentation**: Document message formats in OpenAPI schema
4. **Error Recovery**: Implement retry logic for failed connections
5. **Performance**: Consider reducing polling interval for faster updates

---

**End of Analysis**

