# Sprint Plan: Polling to WebSocket Migration

**Date**: Sun Jan 11 10:35:06 PST 2026  
**Sprint Duration**: 3-4 days (16-24 hours total)  
**Sprint Goal**: Migrate high-impact polling implementations (simulation progress, grid search progress, and update status) to WebSocket-based real-time updates, reducing server load by 60-80% and improving update latency from 0-500ms to <50ms.  
**Current Status**: Application uses HTTP polling for progress tracking (simulation: 500ms, grid search: 500ms, update status: 2s). WebSocket infrastructure exists and is proven with live game data streaming.  
**Target Status**: All high-impact polling replaced with WebSocket push notifications. Progress updates delivered in real-time (<50ms latency). 60-80% reduction in HTTP requests for progress tracking.  
**Team Size**: 1 developer  
**Sprint Lead**: AI Assistant

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `cursor-files/templates/SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`.

**See `cursor-files/templates/SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline

- **Test Results**: No formal test suite exists; manual testing only
- **QC Results**: No automated QC checks; manual validation
- **Code Coverage**: Not measured
- **Build Status**: Application runs successfully; FastAPI server starts without errors

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
- **NO git status, git log, or git diff** unless explicitly mentioned in sprint plan

**Exception**: Git usage is only allowed when:
1. Explicitly mentioned in the analysis document
2. Explicitly mentioned in the sprint plan
3. Explicitly mentioned in the prompt by the prompter that git can be used

## Sprint Overview

### Business Context
- **Business Driver**: Reduce server load and improve user experience with real-time progress updates. High-frequency polling (500ms intervals) creates unnecessary HTTP overhead and introduces latency.
- **Success Criteria**: 
  - 60-80% reduction in HTTP requests for progress tracking
  - <50ms latency for progress updates (from 0-500ms polling delay)
  - Zero polling-related errors
  - Consistent WebSocket pattern across all real-time features
- **Stakeholders**: End users (better UX), server infrastructure (reduced load), developers (consistent architecture)
- **Timeline Constraints**: No hard deadlines; can be done incrementally

### Technical Context
- **Current System State**: 
  - Simulation progress: HTTP polling every 500ms (`webapp/static/js/simulation.js:46-76`)
  - Grid search progress: HTTP polling every 500ms (`webapp/static/js/grid-search.js:185-233`)
  - Update status: HTTP polling every 2s (`webapp/static/js/ui.js:333-431`)
  - Live games list: HTTP polling every 30s (`webapp/static/js/live.js:125-156`) - optional
  - WebSocket infrastructure exists (`webapp/api/websocket_manager.py`, `webapp/api/endpoints/live_data.py`)
- **Target System State**: 
  - All high-impact polling replaced with WebSocket endpoints
  - Progress updates pushed immediately when state changes
  - HTTP endpoints maintained for initial status/backward compatibility
  - Consistent WebSocket pattern across all real-time features
- **Architecture Impact**: 
  - Adds WebSocket endpoints for progress tracking
  - Reuses existing WebSocketManager infrastructure
  - No database schema changes required
  - Maintains backward compatibility with HTTP endpoints
- **Integration Points**: 
  - Existing progress tracking dictionaries (`_simulation_progress`, `_grid_search_progress`, `_update_task_running`)
  - Existing WebSocketManager for connection management
  - Frontend WebSocketClient pattern (`webapp/static/js/websocket.js`)

### Sprint Scope
- **In Scope**: 
  - Migrate simulation progress polling to WebSocket
  - Migrate grid search progress polling to WebSocket
  - Migrate update status polling to WebSocket
  - Remove polling code after migration
  - Update documentation
- **Out of Scope**: 
  - Migrating live games list refresh (low priority, 30s interval)
  - Database schema changes
  - Changes to progress tracking logic (only communication method changes)
- **Assumptions**: 
  - WebSocket infrastructure is stable and proven
  - Progress tracking dictionaries remain thread-safe
  - Frontend can handle WebSocket connections reliably
- **Constraints**: 
  - Must maintain backward compatibility with HTTP endpoints
  - Must not break existing functionality
  - Must follow existing WebSocket patterns

## Sprint Phases

### Phase 1: High-Impact Migrations - Simulation Progress (Duration: 4-6 hours)
**Objective**: Migrate simulation progress polling to WebSocket, reducing HTTP requests by 80% and improving latency to <50ms
**Dependencies**: Existing WebSocket infrastructure, understanding of simulation progress tracking
**Deliverables**: WebSocket endpoint `/ws/simulation/{request_id}` and updated frontend client

### Tasks
- **[Task 1.1]**: Create WebSocket endpoint for simulation progress
  - **Files**: `webapp/api/endpoints/simulation.py`
  - **Effort**: 2-3 hours
  - **Prerequisites**: Understanding of existing progress tracking (`_simulation_progress` dictionary)
  - **Validation**: 
    - WebSocket endpoint accepts connections at `/ws/simulation/{request_id}`
    - Server pushes progress updates when `_simulation_progress[request_id]` changes
    - Connection closes when simulation completes or errors

- **[Task 1.2]**: Migrate simulation.js to use WebSocket
  - **Files**: `webapp/static/js/simulation.js`
  - **Effort**: 2-3 hours
  - **Prerequisites**: WebSocket endpoint complete (Task 1.1)
  - **Validation**: 
    - Frontend connects to WebSocket when simulation starts
    - Progress updates received in real-time (<50ms latency)
    - Connection closes when simulation completes
    - Polling code removed

### Phase 2: High-Impact Migrations - Grid Search Progress (Duration: 4-6 hours)
**Objective**: Migrate grid search progress polling to WebSocket, reducing HTTP requests by 80% and improving latency to <50ms
**Dependencies**: Phase 1 complete (for pattern reference), understanding of grid search progress tracking
**Deliverables**: WebSocket endpoint `/ws/grid-search/{request_id}` and updated frontend client

### Tasks
- **[Task 2.1]**: Create WebSocket endpoint for grid search progress
  - **Files**: `webapp/api/endpoints/grid_search.py`
  - **Effort**: 2-3 hours
  - **Prerequisites**: Understanding of existing progress tracking (`_grid_search_progress` dictionary)
  - **Validation**: 
    - WebSocket endpoint accepts connections at `/ws/grid-search/{request_id}`
    - Server pushes progress updates when `_grid_search_progress[request_id]` changes
    - Connection closes when grid search completes or errors

- **[Task 2.2]**: Migrate grid-search.js to use WebSocket
  - **Files**: `webapp/static/js/grid-search.js`
  - **Effort**: 2-3 hours
  - **Prerequisites**: WebSocket endpoint complete (Task 2.1)
  - **Validation**: 
    - Frontend connects to WebSocket when grid search starts
    - Progress updates received in real-time (<50ms latency)
    - Connection closes when grid search completes
    - Polling code removed

### Phase 3: Medium-Impact Migration - Update Status (Duration: 3-4 hours)
**Objective**: Migrate update status polling to WebSocket, reducing HTTP requests by 70% and providing real-time status updates
**Dependencies**: Phase 2 complete (for pattern reference), understanding of update status tracking
**Deliverables**: WebSocket endpoint `/ws/update/status` and updated frontend client

### Tasks
- **[Task 3.1]**: Create WebSocket endpoint for update status
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1-2 hours
  - **Prerequisites**: Understanding of existing status tracking (`_update_task_running` flag)
  - **Validation**: 
    - WebSocket endpoint accepts connections at `/ws/update/status`
    - Server pushes status changes when `_update_task_running` changes
    - Connection can be maintained or closed after update completes

- **[Task 3.2]**: Migrate ui.js to use WebSocket
  - **Files**: `webapp/static/js/ui.js`
  - **Effort**: 2 hours
  - **Prerequisites**: WebSocket endpoint complete (Task 3.1)
  - **Validation**: 
    - Frontend connects to WebSocket when update is triggered
    - Status updates received in real-time
    - Connection closes when update completes
    - Polling code removed

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, remove polling code, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, removed polling code, and sprint archive

## Sprint Backlog

### Epic 1: Simulation Progress WebSocket Migration
**Priority**: Critical (High business impact - 2 requests/second per user)
**Estimated Time**: 4-6 hours (2-3 hours backend + 2-3 hours frontend)
**Dependencies**: Existing WebSocket infrastructure (`webapp/api/websocket_manager.py`), simulation progress tracking (`_simulation_progress` dictionary)
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Create Simulation Progress WebSocket Endpoint
- **ID**: S21-E1-S1
- **Type**: Feature
- **Priority**: Critical (High impact - 500ms polling interval)
- **Estimate**: 2-3 hours (1 hour endpoint creation + 1-2 hours testing/integration)
- **Phase**: Phase 1
- **Prerequisites**: None (first story)
- **Files to Modify**: `webapp/api/endpoints/simulation.py`
- **Files to Create**: None (adds to existing file)
- **Dependencies**: FastAPI WebSocket support, existing `_simulation_progress` dictionary, WebSocketManager pattern

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] WebSocket endpoint exists at `/ws/simulation/{request_id}` in `webapp/api/endpoints/simulation.py`
  - [ ] Endpoint accepts WebSocket connections and sends initial progress state
  - [ ] Server pushes progress updates when `_simulation_progress[request_id]` changes
  - [ ] Connection closes gracefully when simulation completes or errors
  - [ ] Endpoint handles connection errors and disconnections properly
  - [ ] Endpoint validates `request_id` exists in progress tracking
  - [ ] Message format matches existing WebSocket patterns: `{"type": "progress", "progress": {...}}`

- **Technical Context**:
  - **Current State**: 
    ```python
    # webapp/api/endpoints/simulation.py:813-822
    @router.get("/simulation/progress/{request_id}")
    def get_simulation_progress(request_id: str) -> dict[str, Any]:
        with _progress_lock:
            if request_id not in _simulation_progress:
                return {"status": "not_found", "current": 0, "total": 0}
            return _simulation_progress[request_id].copy()
    ```
  - **Required Changes**: 
    ```python
    # After implementation
    @router.websocket("/ws/simulation/{request_id}")
    async def websocket_simulation_progress(websocket: WebSocket, request_id: str):
        await websocket.accept()
        # Send initial state
        # Monitor _simulation_progress[request_id] for changes
        # Push updates when state changes
        # Close when complete/error
    ```
  - **Integration Points**: 
    - Uses existing `_simulation_progress` dictionary (thread-safe with `_progress_lock`)
    - Follows pattern from `webapp/api/endpoints/live_data.py:35-162`
    - Reuses WebSocketManager if needed for connection management
  - **Data Structures**: 
    - Progress dictionary: `{"status": str, "current": int, "total": int, ...}`
    - WebSocket message: `{"type": "progress", "progress": {...}}`
  - **API Contracts**: 
    - WebSocket endpoint: `/ws/simulation/{request_id}`
    - Message format: JSON with `type` and `progress` fields
    - Connection lifecycle: Accept → Send initial → Push updates → Close on completion

- **Implementation Steps**: 
  1. Add WebSocket import: `from fastapi import WebSocket, WebSocketDisconnect`
  2. Create `websocket_simulation_progress` function with `@router.websocket("/ws/simulation/{request_id}")`
  3. Accept connection and validate `request_id` exists
  4. Send initial progress state
  5. Monitor `_simulation_progress[request_id]` for changes (poll every 100-200ms)
  6. Push updates when state changes
  7. Close connection when status is "complete" or "error"
  8. Handle disconnections and errors gracefully

- **Validation Steps**: 
  - Start simulation, verify WebSocket connection established
  - Verify initial progress message received
  - Verify progress updates pushed when state changes
  - Verify connection closes when simulation completes
  - Verify error handling works correctly

- **Definition of Done**: 
  - WebSocket endpoint functional and tested
  - Handles all edge cases (invalid request_id, disconnections, errors)
  - Follows existing WebSocket patterns
  - HTTP endpoint still works for backward compatibility

- **Rollback Plan**: 
  - Keep HTTP endpoint unchanged
  - If WebSocket fails, frontend can fall back to HTTP polling
  - Remove WebSocket endpoint if critical issues arise

- **Risk Assessment**: 
  - **Low risk**: Pattern already proven with live game data
  - **Mitigation**: Reuse existing WebSocket patterns, thorough testing
  - **Contingency**: Maintain HTTP endpoint as fallback

- **Success Metrics**: 
  - **Performance**: 80% reduction in HTTP requests (from 2/sec to 0.4/sec per user)
  - **Quality**: Zero connection errors, proper error handling
  - **Functionality**: Real-time progress updates (<50ms latency)

### Story 1.2: Migrate Simulation Frontend to WebSocket
- **ID**: S21-E1-S2
- **Type**: Refactor
- **Priority**: Critical (Completes simulation migration)
- **Estimate**: 2-3 hours (1-2 hours implementation + 1 hour testing)
- **Phase**: Phase 1
- **Prerequisites**: S21-E1-S1 (WebSocket endpoint must be complete)
- **Files to Modify**: `webapp/static/js/simulation.js`
- **Files to Create**: None
- **Dependencies**: WebSocket endpoint (S21-E1-S1), WebSocketClient pattern (`webapp/static/js/websocket.js`)

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `pollSimulationProgress` function replaced with WebSocket client
  - [ ] WebSocket connection established when simulation starts
  - [ ] Progress updates received in real-time (<50ms latency)
  - [ ] Connection closes when simulation completes
  - [ ] Polling code (`pollSimulationProgress` function) removed
  - [ ] Error handling for WebSocket connection failures
  - [ ] Fallback to HTTP endpoint if WebSocket unavailable

- **Technical Context**:
  - **Current State**: 
    ```javascript
    // webapp/static/js/simulation.js:46-76
    async function pollSimulationProgress(requestId, onProgress) {
        const pollInterval = 500; // Poll every 500ms
        const poll = async () => {
            const response = await fetch(`/api/simulation/progress/${requestId}`);
            const progress = await response.json();
            onProgress(progress);
            if (progress.status === 'complete' || progress.status === 'error') {
                return; // Stop polling
            }
            setTimeout(poll, pollInterval);
        };
        poll();
    }
    ```
  - **Required Changes**: 
    ```javascript
    // After implementation
    function connectSimulationProgress(requestId, onProgress) {
        const ws = new WebSocketClient(`simulation-${requestId}`);
        ws.onMessage((data) => {
            if (data.type === 'progress') {
                onProgress(data.progress);
                if (data.progress.status === 'complete' || data.progress.status === 'error') {
                    ws.disconnect();
                }
            }
        });
        ws.connect();
        return ws;
    }
    ```
  - **Integration Points**: 
    - Uses existing WebSocketClient pattern (`webapp/static/js/websocket.js`)
    - Integrates with existing `runBulkSimulation` function
    - Maintains same `onProgress` callback interface
  - **Data Structures**: 
    - WebSocket message: `{"type": "progress", "progress": {...}}`
    - Progress object: `{status: str, current: int, total: int, ...}`
  - **API Contracts**: 
    - WebSocket URL: `ws://host/ws/simulation/{request_id}`
    - Message handling: Parse JSON, call `onProgress` callback

- **Implementation Steps**: 
  1. Import or create WebSocketClient instance
  2. Replace `pollSimulationProgress` calls with WebSocket connection
  3. Handle WebSocket messages and call `onProgress` callback
  4. Close connection when simulation completes
  5. Add error handling and reconnection logic
  6. Remove `pollSimulationProgress` function
  7. Update all call sites to use new WebSocket function

- **Validation Steps**: 
  - Start simulation, verify WebSocket connection
  - Verify progress updates appear in real-time
  - Verify connection closes on completion
  - Verify error handling works
  - Verify no polling requests in network tab

- **Definition of Done**: 
  - WebSocket client functional and tested
  - Polling code completely removed
  - Error handling implemented
  - No HTTP polling requests in network logs

- **Rollback Plan**: 
  - Keep `pollSimulationProgress` function commented out
  - Can revert to polling if WebSocket fails
  - HTTP endpoint still available

- **Risk Assessment**: 
  - **Low risk**: WebSocketClient pattern already exists
  - **Mitigation**: Thorough testing, maintain HTTP fallback
  - **Contingency**: Revert to polling if critical issues

- **Success Metrics**: 
  - **Performance**: 80% reduction in HTTP requests
  - **Quality**: Zero WebSocket errors, proper error handling
  - **Functionality**: Real-time updates, no polling code remaining

### Epic 2: Grid Search Progress WebSocket Migration
**Priority**: Critical (High business impact - 2 requests/second per user)
**Estimated Time**: 4-6 hours (2-3 hours backend + 2-3 hours frontend)
**Dependencies**: Epic 1 complete (for pattern reference), grid search progress tracking (`_grid_search_progress` dictionary)
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Create Grid Search Progress WebSocket Endpoint
- **ID**: S21-E2-S1
- **Type**: Feature
- **Priority**: Critical (High impact - 500ms polling interval)
- **Estimate**: 2-3 hours (1 hour endpoint creation + 1-2 hours testing/integration)
- **Phase**: Phase 2
- **Prerequisites**: S21-E1-S1, S21-E1-S2 (Epic 1 complete for pattern reference)
- **Files to Modify**: `webapp/api/endpoints/grid_search.py`
- **Files to Create**: None (adds to existing file)
- **Dependencies**: FastAPI WebSocket support, existing `_grid_search_progress` dictionary, WebSocketManager pattern

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] WebSocket endpoint exists at `/ws/grid-search/{request_id}` in `webapp/api/endpoints/grid_search.py`
  - [ ] Endpoint accepts WebSocket connections and sends initial progress state
  - [ ] Server pushes progress updates when `_grid_search_progress[request_id]` changes
  - [ ] Connection closes gracefully when grid search completes or errors
  - [ ] Endpoint handles connection errors and disconnections properly
  - [ ] Endpoint validates `request_id` exists in progress tracking
  - [ ] Message format matches existing WebSocket patterns: `{"type": "progress", "progress": {...}}`

- **Technical Context**:
  - **Current State**: 
    ```python
    # webapp/api/endpoints/grid_search.py:462-475
    @router.get("/grid-search/progress/{request_id}")
    def get_grid_search_progress(request_id: str) -> dict[str, Any]:
        with _grid_search_lock:
            if request_id not in _grid_search_progress:
                raise HTTPException(status_code=404, detail="Request ID not found")
            progress = _grid_search_progress[request_id].copy()
            return {
                "status": progress.get("status", "unknown"),
                "current": progress.get("current", 0),
                "total": progress.get("total", 0),
                "current_combo": progress.get("current_combo")
            }
    ```
  - **Required Changes**: Similar to Story 1.1, but for grid search progress
  - **Integration Points**: Uses existing `_grid_search_progress` dictionary (thread-safe with `_grid_search_lock`)
  - **Data Structures**: Progress dictionary with `status`, `current`, `total`, `current_combo` fields
  - **API Contracts**: WebSocket endpoint `/ws/grid-search/{request_id}`, JSON message format

- **Implementation Steps**: Similar to Story 1.1, adapted for grid search
- **Validation Steps**: Similar to Story 1.1, adapted for grid search
- **Definition of Done**: WebSocket endpoint functional, tested, follows patterns
- **Rollback Plan**: Keep HTTP endpoint, fallback available
- **Risk Assessment**: Low risk, proven pattern
- **Success Metrics**: 80% reduction in HTTP requests, <50ms latency

### Story 2.2: Migrate Grid Search Frontend to WebSocket
- **ID**: S21-E2-S2
- **Type**: Refactor
- **Priority**: Critical (Completes grid search migration)
- **Estimate**: 2-3 hours (1-2 hours implementation + 1 hour testing)
- **Phase**: Phase 2
- **Prerequisites**: S21-E2-S1 (WebSocket endpoint must be complete)
- **Files to Modify**: `webapp/static/js/grid-search.js`
- **Files to Create**: None
- **Dependencies**: WebSocket endpoint (S21-E2-S1), WebSocketClient pattern

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `pollGridSearchProgress` function replaced with WebSocket client
  - [ ] WebSocket connection established when grid search starts
  - [ ] Progress updates received in real-time (<50ms latency)
  - [ ] Connection closes when grid search completes
  - [ ] Polling code (`pollGridSearchProgress` function) removed
  - [ ] Error handling for WebSocket connection failures
  - [ ] Progress indicator updates in real-time

- **Technical Context**: Similar to Story 1.2, but for grid search
- **Implementation Steps**: Similar to Story 1.2, adapted for grid search
- **Validation Steps**: Similar to Story 1.2, adapted for grid search
- **Definition of Done**: WebSocket client functional, polling code removed
- **Rollback Plan**: Keep polling function commented, HTTP fallback available
- **Risk Assessment**: Low risk, proven pattern
- **Success Metrics**: 80% reduction in HTTP requests, real-time updates

### Epic 3: Update Status WebSocket Migration
**Priority**: High (Medium business impact - 0.5 requests/second per user)
**Estimated Time**: 3-4 hours (1-2 hours backend + 2 hours frontend)
**Dependencies**: Epic 2 complete (for pattern reference), update status tracking (`_update_task_running` flag)
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Create Update Status WebSocket Endpoint
- **ID**: S21-E3-S1
- **Type**: Feature
- **Priority**: High (Medium impact - 2s polling interval)
- **Estimate**: 1-2 hours (1 hour endpoint creation + 1 hour testing)
- **Phase**: Phase 3
- **Prerequisites**: S21-E2-S1, S21-E2-S2 (Epic 2 complete for pattern reference)
- **Files to Modify**: `webapp/api/endpoints/update.py`
- **Files to Create**: None (adds to existing file)
- **Dependencies**: FastAPI WebSocket support, existing `_update_task_running` flag

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] WebSocket endpoint exists at `/ws/update/status` in `webapp/api/endpoints/update.py`
  - [ ] Endpoint accepts WebSocket connections and sends initial status
  - [ ] Server pushes status changes when `_update_task_running` changes
  - [ ] Connection can be maintained or closed after update completes
  - [ ] Endpoint handles connection errors and disconnections properly
  - [ ] Message format: `{"type": "status", "is_running": bool, "message": str}`

- **Technical Context**:
  - **Current State**: 
    ```python
    # webapp/api/endpoints/update.py:36-52
    @router.get("/update/status")
    def get_update_status() -> dict[str, Any]:
        global _update_task_running
        is_running = _update_task_running or _update_task_lock.locked()
        return {
            "is_running": is_running,
            "message": "Update in progress" if is_running else "No update running"
        }
    ```
  - **Required Changes**: WebSocket endpoint that monitors `_update_task_running` flag
  - **Integration Points**: Uses existing `_update_task_running` global flag
  - **Data Structures**: Status message with `is_running` boolean and `message` string
  - **API Contracts**: WebSocket endpoint `/ws/update/status`, JSON message format

- **Implementation Steps**: 
  1. Add WebSocket import
  2. Create `websocket_update_status` function
  3. Accept connection and send initial status
  4. Monitor `_update_task_running` flag for changes
  5. Push updates when flag changes
  6. Handle disconnections gracefully

- **Validation Steps**: 
  - Connect to WebSocket, verify initial status received
  - Trigger update, verify status change pushed
  - Verify connection handling works correctly

- **Definition of Done**: WebSocket endpoint functional, tested, follows patterns
- **Rollback Plan**: Keep HTTP endpoint, fallback available
- **Risk Assessment**: Low risk, proven pattern
- **Success Metrics**: 70% reduction in HTTP requests, real-time status updates

### Story 3.2: Migrate Update Status Frontend to WebSocket
- **ID**: S21-E3-S2
- **Type**: Refactor
- **Priority**: High (Completes update status migration)
- **Estimate**: 2 hours (1 hour implementation + 1 hour testing)
- **Phase**: Phase 3
- **Prerequisites**: S21-E3-S1 (WebSocket endpoint must be complete)
- **Files to Modify**: `webapp/static/js/ui.js`
- **Files to Create**: None
- **Dependencies**: WebSocket endpoint (S21-E3-S1), WebSocketClient pattern

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] `pollUpdateStatus` and `startUpdateStatusPolling` functions replaced with WebSocket client
  - [ ] WebSocket connection established when update is triggered
  - [ ] Status updates received in real-time
  - [ ] Connection closes when update completes
  - [ ] Polling code (`pollUpdateStatus`, `startUpdateStatusPolling`, `stopUpdateStatusPolling`) removed
  - [ ] Error handling for WebSocket connection failures
  - [ ] UI updates correctly on status changes

- **Technical Context**:
  - **Current State**: 
    ```javascript
    // webapp/static/js/ui.js:333-431
    let updateStatusPollInterval = null;
    function startUpdateStatusPolling() {
        updateStatusPollInterval = setInterval(() => {
            pollUpdateStatus();
        }, 2000);
    }
    ```
  - **Required Changes**: Replace polling with WebSocket connection
  - **Integration Points**: Integrates with `triggerDataUpdate` function
  - **Data Structures**: Status message with `is_running` and `message` fields
  - **API Contracts**: WebSocket URL `ws://host/ws/update/status`

- **Implementation Steps**: 
  1. Replace `startUpdateStatusPolling` with WebSocket connection
  2. Handle WebSocket messages and update UI
  3. Close connection when update completes
  4. Remove polling functions
  5. Update all call sites

- **Validation Steps**: 
  - Trigger update, verify WebSocket connection
  - Verify status updates in real-time
  - Verify connection closes on completion
  - Verify no polling requests

- **Definition of Done**: WebSocket client functional, polling code removed
- **Rollback Plan**: Keep polling functions commented, HTTP fallback available
- **Risk Assessment**: Low risk, proven pattern
- **Success Metrics**: 70% reduction in HTTP requests, real-time status updates

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: S21-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed (S21-E1-S1, S21-E1-S2, S21-E2-S1, S21-E2-S2, S21-E3-S1, S21-E3-S2)

- **Acceptance Criteria**: 
  - [ ] README.md updated with WebSocket endpoint documentation
  - [ ] Code comments updated in WebSocket endpoints
  - [ ] API documentation updated (if applicable)
  - [ ] Architecture documentation updated to reflect WebSocket pattern

- **Technical Context**: 
  - **Current State**: Documentation may not mention WebSocket endpoints
  - **Required Changes**: Add WebSocket endpoint documentation, update architecture docs

- **Implementation Steps**: 
  1. Update `webapp/README.md` with WebSocket endpoint information
  2. Add docstrings to WebSocket endpoints
  3. Update any API documentation
  4. Update architecture documentation

- **Validation Steps**: 
  - Verify README includes WebSocket endpoints
  - Verify code comments are complete
  - Verify documentation is accurate

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: S21-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All tests pass (100% pass rate required - manual testing if no automated tests)
  - [ ] Build process completes without errors
  - [ ] Code quality maintained or improved
  - [ ] All previous story acceptance criteria verified
  - [ ] No polling code remains in codebase
  - [ ] All WebSocket endpoints functional and tested

- **Technical Context**:
  - **Current State**: Codebase with WebSocket migrations complete
  - **Required Changes**: Fix any linting errors, verify functionality
  - **Quality Gates**: 
    - Linting: `read_lints` tool on all modified files
    - Build: FastAPI server starts without errors
    - Functionality: All WebSocket endpoints work correctly
    - Code cleanup: Polling code removed

- **Implementation Steps**: 
  1. Run linting on all modified files
  2. Fix any linting errors or warnings
  3. Test all WebSocket endpoints manually
  4. Verify no polling code remains
  5. Verify HTTP endpoints still work (backward compatibility)
  6. Test error handling and edge cases

- **Validation Steps**: 
  - Run `read_lints` on modified files, verify zero errors
  - Start FastAPI server, verify no errors
  - Test each WebSocket endpoint, verify functionality
  - Search codebase for polling patterns, verify removed
  - Test HTTP endpoints, verify backward compatibility

### Story [FINAL]: Sprint Completion and Archive
- **ID**: S21-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**: 
  - [ ] Sprint completion report created
  - [ ] All sprint files organized
  - [ ] Sprint marked as completed
  - [ ] Performance metrics documented
  - [ ] Success metrics verified

- **Technical Context**: 
  - **Current Sprint State**: All stories completed, quality gates passed
  - **Archive Tasks**: Create completion report, organize files

- **Implementation Steps**: 
  1. Create sprint completion report with metrics
  2. Document performance improvements (HTTP request reduction)
  3. Verify success metrics met
  4. Organize sprint files
  5. Mark sprint as completed

- **Validation Steps**: 
  - Verify completion report exists
  - Verify metrics documented
  - Verify files organized

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: WebSocket Handler Pattern
- **Category**: Behavioral
- **Intent**: Provide real-time bidirectional communication between client and server
- **Implementation**: 
  - WebSocket endpoints accept connections
  - Server pushes updates when state changes
  - Client processes updates in real-time
  - Connection lifecycle managed (accept → monitor → push → close)
- **Benefits**: 
  - Real-time updates (<50ms latency)
  - Efficient (server pushes only when needed)
  - Scalable (persistent connections)
  - Two-way communication (ping/pong for health checks)
- **Trade-offs**: 
  - More complex than HTTP polling
  - Requires connection management
  - Need error handling and reconnection logic
- **Rationale**: 
  - Proven pattern (already used for live game data)
  - Significant performance benefits (60-80% request reduction)
  - Better user experience (real-time updates)
  - Consistent architecture across real-time features

### Algorithm Analysis

### Algorithm: WebSocket Push Notification
- **Type**: Network Communication
- **Complexity**: Time O(1) per update, Space O(1) per connection
- **Description**: 
  - Server monitors state changes
  - Pushes updates immediately when state changes
  - Client receives updates in real-time
  - No polling overhead
- **Use Case**: 
  - Real-time progress tracking
  - Status updates
  - Live data streaming
- **Performance**: 
  - Best Case: O(1) - immediate push on state change
  - Average Case: O(1) - push only when needed
  - Worst Case: O(1) - push on every state change (still more efficient than polling)
  - Network Overhead: Low (persistent connection, minimal headers)

### Design Decision Analysis

### Design Decision: WebSocket vs HTTP Polling for Progress Tracking
- **Problem**: High-frequency polling (500ms intervals) creates unnecessary server load and introduces latency
- **Context**: 
  - WebSocket infrastructure already exists and is proven
  - Progress tracking state already thread-safe
  - Frontend WebSocketClient pattern already implemented
  - Need real-time updates without polling overhead
- **Project Scope**: Medium-sized web application, single developer, expected growth, no strict timeline constraints

**Option 1: Keep HTTP Polling (REJECTED)**
- **Design Pattern**: Polling Pattern
- **Algorithm**: O(n) HTTP requests where n = duration/poll_interval
- **Implementation Complexity**: Low (already implemented)
- **Maintenance Overhead**: Medium (scattered polling logic)
- **Scalability**: Poor (doesn't scale with concurrent users)
- **Cost-Benefit**: Low cost, Low benefit
- **Rejected**: High server load, latency issues, poor scalability

**Option 2: Server-Sent Events (SSE) (REJECTED)**
- **Design Pattern**: Publisher-Subscriber Pattern
- **Algorithm**: O(1) server pushes, one-way communication
- **Implementation Complexity**: Medium (new infrastructure needed)
- **Maintenance Overhead**: Medium (SSE connection management)
- **Scalability**: Good (better than polling, but one-way only)
- **Cost-Benefit**: Medium cost, Medium benefit
- **Rejected**: One-way only, less flexible than WebSocket

**Option 3: WebSocket Push (CHOSEN)**
- **Design Pattern**: WebSocket Handler Pattern + Observer Pattern
- **Algorithm**: O(1) server pushes when state changes
- **Implementation Complexity**: Medium (4-6 hours per feature)
- **Maintenance Overhead**: Low (reuse existing infrastructure)
- **Scalability**: Excellent (persistent connections, efficient)
- **Cost-Benefit**: Medium cost, High benefit
- **Selected**: 
  - Infrastructure already exists
  - Proven pattern (used for live game data)
  - Two-way communication (ping/pong for health checks)
  - Best performance characteristics
  - Consistent with existing architecture

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 16-24 hours (Medium complexity)
- **Learning Curve**: 0 hours (pattern already understood)
- **Configuration Effort**: 0 hours (infrastructure exists)

**Maintenance Cost**:
- **Monitoring**: 1 hour/month (connection health monitoring)
- **Updates**: 2 hours/month (bug fixes, improvements)
- **Debugging**: 2 hours/incident (connection issues)

**Performance Benefit**:
- **Response Time**: 80% improvement (500ms polling → <50ms push)
- **Throughput**: 60% reduction in HTTP requests
- **Resource Efficiency**: 70% reduction in bandwidth usage

**Maintainability Benefit**:
- **Code Quality**: Centralized WebSocket pattern, consistent architecture
- **Developer Productivity**: Reusable pattern, easier to add new real-time features
- **System Reliability**: Better error handling, connection management

**Risk Cost**:
- **Connection Management**: Low risk, mitigated by existing WebSocketManager
- **State Synchronization**: Low risk, mitigated by existing progress tracking
- **Backward Compatibility**: Low risk, HTTP endpoints remain for initial status

**Over-Engineering Prevention**:
- **Problem Complexity**: Medium (real-time updates needed)
- **Solution Complexity**: Medium (WebSocket endpoints)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: WebSocket pattern supports adding more real-time features

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Medium-sized project, appropriate solution
- **Team Capability**: ✅ Single developer, manageable complexity
- **Timeline Constraints**: ✅ No strict constraints, can be done incrementally
- **Future Growth**: ✅ Supports adding more real-time features
- **Technical Debt**: ✅ Reduces technical debt by consolidating patterns

**Chosen Solution**: WebSocket Push Pattern
- **Implementation**: 
  - Create WebSocket endpoints for each polling use case
  - Server pushes updates when state changes
  - Frontend uses WebSocketClient pattern (reuse existing)
  - Maintain HTTP endpoints for initial status/backward compatibility
- **Configuration**: 
  - Reuse existing WebSocketManager
  - Add progress update broadcasting logic
  - Configure connection timeouts and cleanup
- **Integration**: 
  - Integrates with existing progress tracking dictionaries
  - Uses existing WebSocket infrastructure
  - Maintains backward compatibility

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: 60-80% reduction in HTTP requests, <50ms update latency
- **Maintainability**: Centralized WebSocket pattern, consistent architecture
- **Scalability**: Better resource usage, supports more concurrent users
- **Reliability**: Better error handling, connection health monitoring

**Cons**:
- **Complexity**: Slightly more complex than polling (but infrastructure exists)
- **Learning Curve**: None (pattern already understood)
- **Migration Effort**: 16-24 hours to migrate all polling implementations
- **Resource Usage**: Persistent connections (but more efficient than polling)

**Risk Assessment**:
- **Connection Management**: Low risk - existing WebSocketManager handles this
- **State Synchronization**: Low risk - progress tracking already thread-safe
- **Backward Compatibility**: Low risk - HTTP endpoints remain for initial status

**Trade-off Analysis**:
- **Sacrificed**: Simplicity of polling (but WebSocket pattern is proven)
- **Gained**: Performance, scalability, real-time updates, consistency
- **Net Benefit**: High - significant performance improvement with manageable complexity
- **Over-Engineering Risk**: None - solution complexity matches problem complexity

## Testing Strategy

### Testing Approach
- **Unit Tests**: Manual testing of WebSocket endpoints (no automated test suite exists)
- **Integration Tests**: Manual testing of WebSocket client-server communication
- **E2E Tests**: Manual testing of complete user flows (start simulation/grid search, verify progress updates)
- **Performance Tests**: 
  - Measure HTTP request reduction (before/after comparison)
  - Measure update latency (<50ms target)
  - Monitor server load reduction

### Test Scenarios
1. **Simulation Progress WebSocket**:
   - Start simulation, verify WebSocket connection
   - Verify progress updates received in real-time
   - Verify connection closes on completion
   - Verify error handling

2. **Grid Search Progress WebSocket**:
   - Start grid search, verify WebSocket connection
   - Verify progress updates received in real-time
   - Verify connection closes on completion
   - Verify error handling

3. **Update Status WebSocket**:
   - Trigger update, verify WebSocket connection
   - Verify status updates received in real-time
   - Verify connection closes on completion
   - Verify error handling

4. **Backward Compatibility**:
   - Verify HTTP endpoints still work
   - Verify initial status can be fetched via HTTP
   - Verify fallback works if WebSocket unavailable

## Deployment Plan
- **Pre-Deployment**: 
  - Verify all WebSocket endpoints functional
  - Verify no polling code remains
  - Verify backward compatibility maintained
- **Deployment Steps**: 
  - Deploy backend with WebSocket endpoints
  - Deploy frontend with WebSocket clients
  - Monitor for connection issues
- **Post-Deployment**: 
  - Monitor WebSocket connection counts
  - Monitor HTTP request reduction
  - Monitor update latency
  - Verify user experience improvements
- **Rollback Plan**: 
  - Keep HTTP endpoints as fallback
  - Can revert to polling if critical issues
  - Frontend can fall back to HTTP if WebSocket fails

## Risk Assessment
- **Technical Risks**: 
  - **Connection Management**: Low risk, mitigated by existing WebSocketManager
  - **State Synchronization**: Low risk, mitigated by thread-safe progress tracking
  - **Backward Compatibility**: Low risk, HTTP endpoints remain
- **Business Risks**: 
  - **Migration Introduces Bugs**: Low risk, mitigated by incremental migration and testing
- **Resource Risks**: 
  - **Underestimated Time**: Medium risk, mitigated by conservative estimates and incremental approach

## Success Metrics
- **Technical**: 
  - 60-80% reduction in HTTP requests for progress tracking
  - <50ms latency for progress updates (from 0-500ms)
  - Zero polling-related errors
  - All WebSocket endpoints functional
- **Business**: 
  - Improved user experience (real-time updates)
  - Reduced server load
  - Better scalability
- **Sprint**: 
  - All stories completed according to acceptance criteria
  - Quality gates passed
  - Documentation updated

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All WebSocket endpoints tested and functional
- [ ] All polling code removed
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)
- [ ] HTTP endpoints still work (backward compatibility)
- [ ] Performance metrics documented

### Post-Sprint Quality Comparison
- **Test Results**: All WebSocket endpoints functional, no regressions
- **Linting Results**: Zero errors and warnings
- **Code Coverage**: Maintained (no reduction)
- **Build Status**: Build succeeds, server starts without errors
- **Overall Assessment**: Code quality maintained or improved, consistent WebSocket pattern established

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created with performance metrics
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed
- [ ] Success metrics verified and documented

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

