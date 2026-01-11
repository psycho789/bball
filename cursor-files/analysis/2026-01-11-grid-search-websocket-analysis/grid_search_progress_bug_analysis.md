# Analysis: Grid Search Progress Always Shows 0% - Root Cause Investigation

**Date**: Sat Jan 11 2026  
**Status**: Critical Bug Analysis  
**Author**: AI Assistant  
**Version**: v1.0  
**Purpose**: Identify why grid search progress always shows 0% despite code appearing correct

## Problem Statement

The grid search progress indicator consistently shows 0% even though:
1. The background task is running (confirmed in logs)
2. Progress updates are being written to `_grid_search_progress` dictionary
3. WebSocket connection is established
4. Change detection logic appears correct

## Code Flow Analysis

### Step 1: Background Task Initialization

**Location**: `webapp/api/endpoints/grid_search.py:140-198`

```python
# Step 1.1: Create initial progress entry
with _grid_search_lock:
    _grid_search_progress[request_id] = {
        "status": "running",
        "current": 0,
        "total": 0,  # ⚠️ INITIALLY 0
        "current_combo": None,
        "error": None
    }

# Step 1.2: Calculate total work (takes time - DB queries, game splitting, etc.)
game_ids = get_game_ids_from_season(conn, season)
train_games, valid_games, test_games = split_games(game_ids, config)
combinations = generate_grid(config)
total_games_per_combo = len(train_games) + len(valid_games) + len(test_games)
total_work = len(combinations) * total_games_per_combo

# Step 1.3: Update total (AFTER calculation)
with _grid_search_lock:
    _grid_search_progress[request_id]["total"] = total_work  # ✅ NOW SET TO REAL VALUE
    _grid_search_progress[request_id]["current"] = 0
```

**Timing Issue**: There's a window between Step 1.1 and Step 1.3 where `total: 0`. If WebSocket connects during this window, it will see `total: 0`.

### Step 2: WebSocket Connection

**Location**: `webapp/api/endpoints/grid_search.py:573-600`

```python
# Step 2.1: Check if request_id exists
with _grid_search_lock:
    if request_id not in _grid_search_progress:
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
            "total": progress.get("total", 0),  # ⚠️ MIGHT BE 0 IF CONNECTED TOO EARLY
            "current_combo": progress.get("current_combo", "")
        }

# Step 2.2: Send initial status
await websocket.send_json({
    "type": "progress",
    "progress": initial_status
})

# Step 2.3: Initialize last_progress with SENTINEL VALUES
last_progress = {
    "status": None,   # Sentinel
    "current": -1,    # Sentinel
    "total": -1,      # Sentinel
    "current_combo": None
}
```

**Critical Issue**: After sending `initial_status`, we set `last_progress` to sentinel values. This means the FIRST monitoring loop check will compare:
- `current_progress` = initial_status (e.g., `current: 0, total: 0` or `current: 0, total: 1000`)
- `last_progress` = sentinel values (`current: -1, total: -1`)

The sentinel check should force an update, but...

### Step 3: Monitoring Loop - First Check

**Location**: `webapp/api/endpoints/grid_search.py:635-654`

```python
# Read current progress
with _grid_search_lock:
    progress = _grid_search_progress[request_id].copy()
    current_progress = {
        "status": progress.get("status", "unknown"),
        "current": progress.get("current", 0),
        "total": progress.get("total", 0),
        "current_combo": current_combo_str
    }

# Extract values for comparison
current_val = current_progress.get("current", 0) or 0  # ✅ 0
last_val = last_progress.get("current") if last_progress.get("current") is not None else -1  # ✅ -1

current_total = current_progress.get("total", 0) or 0  # ✅ Could be 0 or actual value
last_total = last_progress.get("total") if last_progress.get("total") is not None else -1  # ✅ -1

# Check for change
has_changed = (current_val != last_val or 
              current_total != last_total or 
              current_status != last_status or 
              current_combo != last_combo)

# Force update if sentinel values detected
if last_val == -1 or last_total == -1 or last_status is None:
    has_changed = True  # ✅ SHOULD BE TRUE
```

**This should work!** The sentinel check should force `has_changed = True` on the first check.

### Step 4: Progress Updates from Background Task

**Location**: `webapp/api/endpoints/grid_search.py:208-234`

```python
def process_with_progress(combo):
    # ⚠️ THIS IS A BLOCKING CALL - CAN TAKE MINUTES PER COMBINATION
    result = process_combination(combo, game_splits, config, dsn, ...)
    
    # Only updates AFTER combination completes
    with completed_lock:
        completed_counter[0] += games_processed
        current_completed = completed_counter[0]
    
    with _grid_search_lock:
        if request_id in _grid_search_progress:
            _grid_search_progress[request_id]["current"] = current_completed
            _grid_search_progress[request_id]["current_combo"] = f"entry={entry:.3f}, exit={exit_val:.3f}"
```

**Critical Finding**: Progress only updates AFTER each `process_combination()` completes. This function:
1. Processes train split (all games)
2. Processes valid split (all games)  
3. Processes test split (all games)

Each combination can take minutes to complete. So if there are 100 combinations and each takes 1 minute, progress won't update for the first minute.

**BUT** - this should still work eventually. The real issue must be elsewhere.

## Root Cause Hypothesis

After careful code analysis, I believe the issue is one of these:

### Hypothesis 1: WebSocket Not Receiving Updates

**Evidence Needed**: Check browser console logs for `Grid search WebSocket message received:` messages.

**Possible Causes**:
- WebSocket connection failing silently
- Messages being sent but not received
- Frontend not processing messages correctly

### Hypothesis 2: Change Detection Not Working

**Evidence Needed**: Check server logs for `Grid search {request_id} progress update:` messages.

**Possible Causes**:
- Comparison logic failing silently
- `has_changed` being False when it should be True
- Update being sent but with wrong values

### Hypothesis 3: Timing Issue - Total Never Gets Set

**Evidence Needed**: Check if `total` is ever set to non-zero value in `_grid_search_progress`.

**Possible Causes**:
- Background task failing before setting total
- Exception in calculation phase
- Lock contention preventing update

### Hypothesis 4: Frontend Not Updating UI

**Evidence Needed**: Check if WebSocket messages are received but UI not updated.

**Possible Causes**:
- DOM element not found (`loadingProgressText`)
- JavaScript error preventing update
- Percent calculation returning 0

## Most Likely Root Cause

Based on code analysis, I believe **Hypothesis 4** is most likely:

**The frontend is receiving updates with `total: 0` or `current: 0`, and the percent calculation results in 0%:**

```javascript
const current = progress.current || 0;  // ✅ 0
const total = progress.total || 1;       // ⚠️ If total is 0, becomes 1, but...
const percent = total > 0 ? Math.round((current / total) * 100) : 0;  // ✅ 0/1 = 0%
```

**OR** the WebSocket is connecting before `total` is set, receiving `total: 0`, and then when `total` gets updated, the change detection isn't working properly.

## Debugging Steps

1. **Add logging to verify progress updates are being written:**
   ```python
   logger.info(f"Grid search {request_id} WRITING progress: current={current_completed}, total={_grid_search_progress[request_id].get('total')}")
   ```

2. **Add logging to verify WebSocket is detecting changes:**
   ```python
   logger.info(f"Grid search {request_id} CHANGE CHECK: current={current_val}/{current_total}, last={last_val}/{last_total}, has_changed={has_changed}")
   ```

3. **Add logging to verify messages are being sent:**
   ```python
   logger.info(f"Grid search {request_id} SENDING: {current_progress}")
   ```

4. **Check browser console for received messages:**
   - Look for `Grid search WebSocket message received:` logs
   - Verify `progress.total` is not 0
   - Verify `progress.current` is incrementing

5. **Check if `total` is being set correctly:**
   - Add log after line 197: `logger.info(f"Set total to {total_work}")`
   - Verify this log appears before WebSocket connects

## Recommended Fix

Based on analysis, the most likely fix is to ensure `total` is set BEFORE the background task is considered "started", and to add better logging to identify where the issue occurs.

**Immediate Action**: Add comprehensive logging to trace the exact flow and identify where progress updates are being lost.

---

**End of Analysis**

