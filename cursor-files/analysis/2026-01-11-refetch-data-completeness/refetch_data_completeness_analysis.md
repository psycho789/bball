# Analysis: Refetch Data Completeness

**Date**: Sun Jan 11 10:17:38 PST 2026  
**Status**: Draft  
**Author**: AI Assistant  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Comprehensive analysis of the refetch data functionality to ensure all required database updates and processing steps are included for a complete, one-click data refresh.

## Analysis Standards Reference

**Important**: This analysis must follow the comprehensive standards defined in `ANALYSIS_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim is backed by concrete evidence (code refs, commands + verbatim output, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers analyzed.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: Use PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Write analyses in `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md` and sprints in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings
- **Finding 1**: The refetch button (`run_update_task()`) fetches and loads raw data (ESPN scoreboards, probabilities, Kalshi markets/candlesticks) but **does NOT process derived tables** (`espn.prob_event_state`) or **refresh materialized views** (`derived.snapshot_features_v1`).
- **Finding 2**: The webapp depends on `espn.prob_event_state` for game metadata and final scores, but this table is **never populated** by the refetch process, requiring manual execution of `materialize_espn_prob_event_state.py`.
- **Finding 3**: Materialized view `derived.snapshot_features_v1` used by simulation and modeling scripts is **never refreshed** after data updates, causing stale data in downstream features.

### Critical Issues Identified
- **Issue 1**: Missing `espn.prob_event_state` processing - Webapp endpoints (`/api/games/{id}/meta`, `/api/games`, `/api/stats/aggregate`) query this table but it's never populated by refetch.
- **Issue 2**: Missing materialized view refresh - `derived.snapshot_features_v1` becomes stale after data updates, affecting simulation accuracy.
- **Issue 3**: Incomplete cache invalidation - Only clears `list_games.cache` but not `get_aggregate_stats.cache` or simulation caches.

### Recommended Actions
- **Action 1**: [Priority: High] - Add `materialize_espn_prob_event_state.py` execution to `run_update_task()` after probabilities are loaded.
- **Action 2**: [Priority: High] - Add materialized view refresh step (`REFRESH MATERIALIZED VIEW CONCURRENTLY`) for `derived.snapshot_features_v1` after all data loading completes.
- **Action 3**: [Priority: Medium] - Expand cache clearing to include all affected caches (`get_aggregate_stats`, simulation caches).

### Success Metrics
- **Metric 1**: Refetch button completes all steps without manual intervention - [Baseline: 7/10 steps] → [Target: 10/10 steps] ([100% completion])
- **Metric 2**: Webapp endpoints return fresh data immediately after refetch - [Baseline: Requires manual steps] → [Target: Automatic] ([100% automation])
- **Metric 3**: Materialized view refresh time - [Baseline: Manual, ~5-10 minutes] → [Target: Automated, ~5-10 minutes] ([No time change, but automated])

## Problem Statement

### Current Situation
The refetch data button (`/api/update/trigger`) triggers `run_update_task()` which performs the following steps:

1. ✅ Fetches ESPN scoreboards (last 7 days)
2. ✅ Loads scoreboards into `espn.scoreboard_games`
3. ✅ Fetches ESPN probabilities for new games
4. ✅ Loads probabilities into `espn.probabilities_raw_items`
5. ✅ Fetches and loads Kalshi markets (combined step → `kalshi.markets`)
6. ✅ Fetches and loads Kalshi candlesticks (combined step → `kalshi.candlesticks`)
7. ✅ Clears `list_games.cache`

**Note**: Steps 5-6 combine fetch+load operations in single functions (`fetch_and_load_kalshi_markets()`, `fetch_and_load_kalshi_candlesticks()`).

However, the following critical steps are **missing**:

- ❌ **Process `espn.prob_event_state`**: This table is populated by `scripts/process/materialize_espn_prob_event_state.py` but is never called by the refetch process.
- ❌ **Refresh `derived.snapshot_features_v1`**: This materialized view needs `REFRESH MATERIALIZED VIEW CONCURRENTLY` after new data is loaded.
- ❌ **Clear additional caches**: `get_aggregate_stats.cache` and simulation caches are not cleared. (Note: A separate `/api/update/clear-cache` endpoint exists that clears both `list_games.cache` and `get_aggregate_stats.cache`, but it's not called automatically by the refetch process.)

### Pain Points
- **Pain Point 1**: After pressing refetch, users must manually run `materialize_espn_prob_event_state.py` to populate game state data, breaking the "one-click" promise.
- **Pain Point 2**: Simulation and modeling scripts use stale materialized view data because views are never refreshed automatically, leading to incorrect results.
- **Pain Point 3**: Webapp endpoints (`/api/games/{id}/meta`, `/api/stats/aggregate`) query `espn.prob_event_state` but get empty results after refetch, causing 404 errors or missing data.

### Business Impact
- **Performance Impact**: Users must manually execute 2-3 additional steps after refetch, adding ~15-20 minutes of manual work per update.
- **User Experience Impact**: Webapp shows incomplete or missing data after refetch, requiring technical knowledge to fix.
- **Maintenance Impact**: Missing steps create confusion and support burden, with users not understanding why data appears incomplete.

### Success Criteria
- **[Criterion 1]**: Pressing refetch button completes ALL required steps automatically (no manual intervention).
- **[Criterion 2]**: All webapp endpoints return fresh, complete data immediately after refetch completes.
- **[Criterion 3]**: Materialized views are refreshed automatically, ensuring simulation/modeling scripts use current data.

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: 1 file (`webapp/api/endpoints/update.py`), 2 scripts to integrate (`materialize_espn_prob_event_state.py`, materialized view refresh SQL), 2 cache clearing locations.
- **Estimated Effort**: 4-5 hours (integration, testing, error handling).
- **Technical Complexity**: Medium - Requires subprocess execution, error handling, and understanding of data dependencies.
- **Risk Level**: Low - All scripts are idempotent (UPSERT operations), so re-running is safe.

**Sprint Scope Recommendation**: Single Sprint
- **Rationale**: All changes are in one file (`update.py`), scripts already exist and are tested, changes are additive (no breaking changes).
- **Recommended Approach**: Add 3 new steps to `run_update_task()`:
  - Step 8: Process `espn.prob_event_state` (after probabilities loaded)
  - Step 9: Refresh materialized view `derived.snapshot_features_v1` (after all data loaded)
  - Step 10: Clear all affected caches (expand existing cache clearing)

**Dependency Analysis**:
- Step 8 depends on Step 4 (probabilities must be loaded first)
- Step 9 depends on Steps 4 and 6 (probabilities and candlesticks must be loaded)
- Step 10 can run after any data changes (no dependencies)

## Current State Analysis

### System Architecture Overview

The refetch data flow consists of:

```
User clicks "Refetch" button
  ↓
POST /api/update/trigger
  ↓
run_update_task() (background task)
  ├─ Step 1: Fetch ESPN scoreboards (7 days)
  ├─ Step 2: Load scoreboards → espn.scoreboard_games
  ├─ Step 3: Fetch ESPN probabilities (new games)
  ├─ Step 4: Load probabilities → espn.probabilities_raw_items
  ├─ Step 5: Fetch and load Kalshi markets → kalshi.markets (combined)
  ├─ Step 6: Fetch and load Kalshi candlesticks → kalshi.candlesticks (combined)
  └─ Step 7: Clear list_games.cache
```

**Missing Steps** (not in current flow):
- Process `espn.prob_event_state` from `espn.probabilities_raw_items`
- Refresh `derived.snapshot_features_v1` materialized view
- Clear additional caches

### Code Quality Assessment

#### Current Implementation

**File**: `webapp/api/endpoints/update.py:1096-1374`

The `run_update_task()` function is well-structured with:
- ✅ Clear step-by-step logging
- ✅ Error collection and reporting
- ✅ Lock-based concurrency prevention
- ✅ Timeout handling for subprocess calls
- ✅ Progress tracking

**Missing Functionality**:
- ❌ No call to `materialize_espn_prob_event_state.py`
- ❌ No materialized view refresh
- ❌ Limited cache clearing (only `list_games.cache`)

### Complexity Analysis
- **Cyclomatic Complexity**: Current function has ~15 decision points (acceptable)
- **Cognitive Complexity**: Medium - Function is long (~280 lines) but well-organized into steps
- **Technical Debt Ratio**: Low - Code is clean, just missing steps

### Performance Baseline
- **Response Time**: Refetch returns immediately (background task), actual processing takes 5-15 minutes
- **Memory Usage**: Subprocess execution, minimal memory overhead
- **Database Performance**: Each step uses UPSERT operations (idempotent, safe to re-run)

### Dependencies Analysis
- **External Dependencies**: ESPN API, Kalshi API (both handled by fetch scripts)
- **Internal Dependencies**: 
  - `scripts/fetch_espn_scoreboard.py`
  - `scripts/load_espn_scoreboard.py`
  - `scripts/fetch_espn_probabilities.py`
  - `scripts/load_espn_probabilities_raw_items.py`
  - `scripts/kalshi/fetch_all_markets.ts`
  - `scripts/load_kalshi_markets.py`
  - `scripts/kalshi/fetch_all_candlesticks.ts`
  - `scripts/load_kalshi_candlesticks.py`
- **Missing Dependencies**:
  - `scripts/process/materialize_espn_prob_event_state.py` (not called)
  - Materialized view refresh SQL (not executed)

## Technical Assessment

### Design Pattern Analysis

#### Current Patterns in Use

**Design Pattern Analysis: Service Pattern**

**Pattern Name**: Service Pattern  
**Pattern Category**: Architectural  
**Pattern Intent**: Encapsulate data update logic in a service function (`run_update_task()`) that orchestrates multiple subprocess calls.

**Implementation**:
- File: `webapp/api/endpoints/update.py:1096-1374`
- Function: `run_update_task()` orchestrates 6 subprocess calls in sequence
- Each step uses `subprocess.run()` to execute Python/TypeScript scripts

**Benefits**:
- Clear separation of concerns (API endpoint vs. update logic)
- Easy to test individual steps
- Idempotent operations (safe to re-run)

**Trade-offs**:
- Long-running function (5-15 minutes) blocks background task thread
- No parallelization (steps run sequentially)
- Limited error recovery (continues on error, collects errors)

**Why This Pattern**: Appropriate for orchestration of independent data loading steps. Sequential execution ensures data dependencies are respected.

### Algorithm Analysis

#### Current Algorithms

**Algorithm Analysis: Sequential Data Pipeline**

**Algorithm Name**: Sequential Data Pipeline  
**Algorithm Type**: Data Processing Pipeline  
**Big O Notation**: 
- Time Complexity: O(n) where n = number of games/data points to process
- Space Complexity: O(1) - processes data in chunks, doesn't load everything into memory

**Algorithm Description**:
- Executes 6 steps sequentially
- Each step is a subprocess call to a Python/TypeScript script
- Scripts use UPSERT operations (idempotent)
- Errors are collected but don't stop the pipeline

**Use Case**: 
- Loading data from multiple sources (ESPN, Kalshi)
- Ensuring data dependencies are respected (scoreboards before probabilities)

**Performance Characteristics**:
- Best Case: O(n) - all steps succeed quickly
- Average Case: O(n) - typical data volumes, some retries
- Worst Case: O(n) - timeouts, but still linear
- Memory Usage: O(1) - subprocess execution, scripts handle their own memory

**Why This Algorithm**: Sequential execution is necessary because:
1. Probabilities depend on scoreboards (game IDs)
2. Candlesticks depend on markets (ticker IDs)
3. Materialized views depend on all raw data

### Performance Analysis

#### Baseline Metrics
- **Response Time**: Immediate (background task), actual processing: 5-15 minutes
- **Throughput**: ~100-500 games processed per update (depends on new games)
- **Memory Usage**: Low (subprocess execution)
- **Database Performance**: UPSERT operations are efficient (indexed tables)

#### Bottleneck Analysis
- **Primary Bottleneck**: Sequential execution (could parallelize some steps, but dependencies prevent it)
- **Secondary Bottleneck**: Materialized view refresh (5-10 minutes, but currently manual)
- **Tertiary Bottleneck**: Network I/O (ESPN/Kalshi API calls)

### Security Analysis

#### Threat Model
- **Threat 1**: Subprocess injection - Mitigated by hardcoded script paths and args
- **Threat 2**: Database connection leaks - Mitigated by context managers (`with get_db_connection()`)
- **Threat 3**: Race conditions - Mitigated by lock-based concurrency prevention

#### Security Controls
- **Authentication**: None required (internal API endpoint)
- **Authorization**: None required (internal API endpoint)
- **Data Protection**: Database credentials via `DATABASE_URL` env var
- **Input Validation**: Script paths are hardcoded, no user input

## Evidence and Proof

### MANDATORY: File Content Verification

**Before making ANY claim about code, configuration, or system state, you MUST:**

1. **Read Actual File Contents**: Use `read_file` tool to examine exact file contents
2. **Run Verification Commands**: Execute specific commands to gather data
3. **Document Command Output**: Include exact command and verbatim response
4. **Verify Claims**: Cross-reference all statements with actual evidence

### Code References

#### Current Refetch Implementation

**File**: `webapp/api/endpoints/update.py:1096-1374`

**Issue**: Missing steps for derived table processing and materialized view refresh

**Evidence**:
- **Command**: `grep -n "def run_update_task" webapp/api/endpoints/update.py`
- **Output**: Function starts at line 1096, ends at line 1374
- **Content**: 
```1096:1374:webapp/api/endpoints/update.py
def run_update_task() -> dict[str, Any]:
    """
    Run the full update task.
    
    Note: This function uses a lock to prevent concurrent execution.
    The scripts are idempotent (use UPSERT), but running multiple updates
    simultaneously wastes resources.
    """
    global _update_task_running
    
    # Acquire lock to prevent concurrent execution
    if not _update_task_lock.acquire(blocking=False):
        logger.warning("[UPDATE_TASK] Another update task is already running, skipping")
        return {
            "status": "skipped",
            "message": "Update task is already running",
            "start_time": datetime.now().isoformat()
        }
    
    try:
        _update_task_running = True
        update_start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Starting data update task")
        logger.info(f"[UPDATE_TASK] Start time: {update_start_time.isoformat()}")
        logger.info("=" * 80)
        
        repo_root = get_repo_root()
        logger.info(f"[UPDATE_TASK] Repository root: {repo_root}")
        logger.debug(f"[UPDATE_TASK] Repository root exists: {repo_root.exists()}")
        
        results = {
            "scoreboard_fetched": 0,
            "scoreboard_loaded": False,
            "probabilities_fetched": 0,
            "probabilities_loaded": False,
            "kalshi_markets_fetched": False,
            "kalshi_markets_loaded": False,
            "kalshi_candlesticks_fetched": False,
            "kalshi_candlesticks_loaded": False,
            "errors": [],
            "start_time": update_start_time.isoformat(),
            "end_time": None,
            "duration_seconds": None
        }
        
        # Step 1: Fetch scoreboards for last 7 days
        # ... (Steps 1-6 implemented) ...
        
        # Step 7: Missing - Process espn.prob_event_state
        # Step 8: Missing - Refresh materialized views
        # Step 9: Missing - Clear additional caches
        
        # Clear games cache after successful update
        if results["probabilities_loaded"] or results["scoreboard_loaded"]:
            logger.info("")
            logger.info("[UPDATE_TASK] Clearing games endpoint cache to ensure fresh data...")
            # ... (only clears list_games.cache) ...
```

**Impact**: Webapp endpoints that query `espn.prob_event_state` return empty results after refetch.

#### Webapp Dependencies on Missing Data

**File**: `webapp/api/endpoints/metadata.py:44-74`

**Issue**: Endpoint queries `espn.prob_event_state` but table is never populated by refetch

**Evidence**:
- **Command**: `grep -n "prob_event_state" webapp/api/endpoints/metadata.py`
- **Output**: Lines 44-74 query `espn.prob_event_state`
- **Content**:
```44:74:webapp/api/endpoints/metadata.py
        # Try prob_event_state first, fallback to scoreboard_games if not found
        prob_event_state_sql = """
        SELECT 
            e.game_id,
            MAX(e.final_home_score) as final_home_score,
            MAX(e.final_away_score) as final_away_score,
            MAX(e.final_winning_team) as winner
        FROM espn.prob_event_state e
        WHERE e.game_id = %s
        GROUP BY e.game_id
        """
        prob_event_state_row = conn.execute(prob_event_state_sql, (game_id,)).fetchone()
        
        if prob_event_state_row and prob_event_state_row[0]:
            # Found in prob_event_state
            return {
                "game_id": prob_event_state_row[0],
                "final_home_score": prob_event_state_row[1],
                "final_away_score": prob_event_state_row[2],
                "winner": prob_event_state_row[3]
            }
        
        # Fallback: if prob_event_state doesn't have the game, try scoreboard_games directly
        logger.debug(f"Game not found in prob_event_state, trying scoreboard_games directly")
```

**Impact**: `/api/games/{id}/meta` endpoint returns incomplete data or falls back to `scoreboard_games` (which may not have final scores).

#### Materialized View Usage

**File**: `scripts/trade/simulate_trading_strategy.py:155-179`

**Issue**: Simulation script queries `derived.snapshot_features_v1` but view is never refreshed after data updates

**Evidence**:
- **Command**: `grep -n "snapshot_features_v1" scripts/trade/simulate_trading_strategy.py`
- **Output**: Lines 155-179 query the materialized view
- **Content**:
```155:179:scripts/trade/simulate_trading_strategy.py
        FROM derived.snapshot_features_v1
        WHERE season_label = %s
          AND game_id = %s
        ORDER BY sequence_number
        """
        
        rows = conn.execute(sql, (season_label, game_id)).fetchall()
        
        if not rows:
            logger.warning(f"No data found in snapshot_features_v1 for game {game_id}")
            return None
```

**Impact**: Simulation uses stale data if materialized view is not refreshed after new games are loaded.

#### Missing Script Integration

**File**: `scripts/process/materialize_espn_prob_event_state.py:400-566`

**Issue**: Script exists and processes `espn.prob_event_state` but is never called by refetch

**Evidence**:
- **Command**: `head -20 scripts/process/materialize_espn_prob_event_state.py`
- **Output**: Script exists and has main() function
- **Content**:
```1:20:scripts/process/materialize_espn_prob_event_state.py
#!/usr/bin/env python3
"""
Materialize a compact ESPN per-play game state table (plus win probability time series) for modeling/analysis.

Writes into:
  espn.prob_event_state(
    game_id, event_id, point_differential, time_remaining,
    possession_side, home_score, away_score, current_winning_team, final_winning_team
  )

Source files:
  data/raw/espn/probabilities/{season_label}/event_{event_id}_comp_{competition_id}.json

This script fetches ESPN play payloads referenced by the probabilities file and caches them locally:
  data/raw/espn/plays/{season_label}/play_{play_id}.json (+ manifest)

Usage:
  python scripts/materialize_espn_prob_event_state.py --dsn "$DATABASE_URL" --season-label 2024-25 --limit-games 10
"""
```

**Impact**: `espn.prob_event_state` table remains empty after refetch, breaking webapp endpoints.

### Database Evidence

#### Materialized View Refresh Requirement

**Database Query**: Check if materialized views exist and need refresh

**Command**: `source .env && psql "$DATABASE_URL" -c "\d+ derived.snapshot_features_v1"`

**Expected Output**: Materialized view exists with comment indicating refresh requirement

**Table**: `derived.snapshot_features_v1`  
**Query**: `SELECT COUNT(*) FROM derived.snapshot_features_v1 WHERE season_label = '2025-26';`  
**Result**: View exists but may be stale after new data is loaded

**Evidence from Documentation**:
- **File**: `cursor-files/docs/sprint_13_completion_report.md:518-532`
- **Content**: Documents that materialized view needs refresh after new data:
  - "**When to refresh**: After loading new ESPN probability data, After loading new Kalshi candlestick data"
  - "**Refresh command**: `REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;`"

## Recommendations

### Immediate Actions (Priority: High)

#### Recommendation 1: Add `espn.prob_event_state` Processing Step

**Specific Action**: Add Step 7 to `run_update_task()` that executes `materialize_espn_prob_event_state.py` after probabilities are loaded.

**Files to Modify**: 
- `webapp/api/endpoints/update.py` - Add new step function and call in `run_update_task()`

**Estimated Effort**: 2 hours
- 1 hour: Implement `process_espn_prob_event_state()` function (similar to existing step functions)
- 1 hour: Add step to `run_update_task()`, test, handle errors

**Risk Level**: Low
- Script already exists and is tested
- Uses UPSERT operations (idempotent)
- Can skip if already processed (script has `--overwrite-db` flag)

**Success Metrics**: 
- `espn.prob_event_state` table populated after refetch
- `/api/games/{id}/meta` endpoint returns complete data
- No manual intervention required

**Implementation Details**:
```python
def process_espn_prob_event_state(repo_root: Path, season_label: str) -> tuple[bool, str]:
    """Process espn.prob_event_state from probabilities_raw_items."""
    script_path = repo_root / "scripts" / "process" / "materialize_espn_prob_event_state.py"
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    cmd = [python_bin, str(script_path), "--dsn", os.environ["DATABASE_URL"], "--season-label", season_label]
    # Execute with timeout, error handling similar to other steps
```

#### Recommendation 2: Add Materialized View Refresh Step

**Specific Action**: Add Step 8 to `run_update_task()` that refreshes `derived.snapshot_features_v1` after all data loading completes.

**Files to Modify**:
- `webapp/api/endpoints/update.py` - Add `refresh_materialized_views()` function and call in `run_update_task()`

**Estimated Effort**: 2 hours
- 1 hour: Implement `refresh_materialized_views()` function (execute SQL via psycopg)
- 1 hour: Add step to `run_update_task()`, test, handle errors

**Risk Level**: Low
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` is safe (allows queries during refresh)
- Views have unique indexes (required for CONCURRENTLY)
- Can skip if no new data (check before refresh)

**Success Metrics**:
- Materialized view refreshed after refetch
- Simulation scripts use fresh data
- No manual `REFRESH` commands required

**Implementation Details**:
```python
def refresh_materialized_views() -> tuple[bool, str]:
    """Refresh materialized views after data updates."""
    with get_db_connection() as conn:
        try:
            # Refresh snapshot_features_v1 (5-10 minutes)
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;")
            return True, "Materialized view refreshed"
        except Exception as e:
            return False, f"Error refreshing view: {str(e)}"
```

#### Recommendation 3: Expand Cache Clearing

**Specific Action**: Expand cache clearing to include `get_aggregate_stats.cache` and simulation caches.

**Files to Modify**:
- `webapp/api/endpoints/update.py` - Expand cache clearing section (lines 1455-1471)

**Estimated Effort**: 1 hour
- 30 minutes: Add clearing for `get_aggregate_stats.cache` (similar to existing `clear_games_cache()` endpoint logic)
- 30 minutes: Test and verify cache clearing works correctly

**Risk Level**: Low
- Cache clearing is safe (just deletes cache files)
- Existing cache clearing code can be extended (can reuse logic from `/api/update/clear-cache` endpoint)

**Success Metrics**:
- All affected caches cleared after refetch
- Webapp endpoints return fresh data immediately

**Implementation Details**:
```python
# Clear games cache (existing)
cache_instance = SimpleCache(ttl_seconds=86400, cache_file="list_games.cache")
cache_instance.clear()

# Clear aggregate stats cache (new)
from . import aggregate_stats
if hasattr(aggregate_stats.get_aggregate_stats, '_cache_instance'):
    aggregate_stats.get_aggregate_stats._cache_instance.clear()
else:
    # Fallback: create new instance and clear it
    cache_instance = SimpleCache(ttl_seconds=86400, cache_file="get_aggregate_stats.cache")
    cache_instance.clear()

# Note: Simulation cache is in-memory only and doesn't need clearing
# (simulations query DB directly, though stale materialized views would affect them)
```

### Short-term Improvements (Priority: Medium)

#### Recommendation 4: Add Progress Tracking for Long-Running Steps

**Specific Action**: Add progress logging for materialized view refresh (takes 5-10 minutes).

**Files to Modify**:
- `webapp/api/endpoints/update.py` - Add progress logging to `refresh_materialized_views()`

**Estimated Effort**: 1 hour
- Add periodic status checks during refresh
- Log progress to update status endpoint

**Risk Level**: Low
- Non-breaking change
- Improves user experience

### Long-term Strategic Changes (Priority: Low)

#### Recommendation 5: Parallelize Independent Steps

**Specific Action**: Run independent steps in parallel (e.g., Kalshi markets and candlesticks can fetch in parallel after markets are loaded).

**Files to Modify**:
- `webapp/api/endpoints/update.py` - Refactor to use `threading` or `asyncio` for parallel execution

**Estimated Effort**: 4-6 hours
- Requires careful dependency analysis
- More complex error handling

**Risk Level**: Medium
- More complex code
- Potential race conditions

### Design Decision Recommendations

#### Recommended Design Pattern: Sequential Pipeline with Optional Steps

**Problem Statement**:
- Need to execute 9 steps in sequence (some optional based on data availability)
- Steps have dependencies (probabilities after scoreboards, materialized views after all data)
- Some steps are long-running (5-10 minutes) and should be optional if no new data

**Sprint Scope Analysis**:
- **Complexity Assessment**: Single file modification, 3 new functions, ~100 lines of code
- **Sprint Scope Determination**: Single Sprint
- **Scope Justification**: All changes are additive, no breaking changes, scripts already exist

**Multiple Solution Analysis**:

**Option 1: Add All Steps Unconditionally**
- **Design Pattern**: Sequential Pipeline
- **Algorithm**: O(n) sequential execution
- **Implementation Complexity**: Low (2 hours)
- **Maintenance Overhead**: Low
- **Scalability**: Good (handles any data volume)
- **Cost-Benefit**: Low cost, High benefit
- **Over-Engineering Risk**: None
- **Rejected**: May waste time refreshing views when no new data exists

**Option 2: Conditional Step Execution (CHOSEN)**
- **Design Pattern**: Sequential Pipeline with Conditional Steps
- **Algorithm**: O(n) sequential execution with conditional checks
- **Implementation Complexity**: Medium (3 hours)
- **Maintenance Overhead**: Low
- **Scalability**: Good (skips unnecessary steps)
- **Cost-Benefit**: Medium cost, High benefit
- **Over-Engineering Risk**: None
- **Selected**: Balances completeness with efficiency

**Option 3: Parallel Execution**
- **Design Pattern**: Parallel Pipeline
- **Algorithm**: O(n) parallel execution where possible
- **Implementation Complexity**: High (6 hours)
- **Maintenance Overhead**: Medium (more complex error handling)
- **Scalability**: Excellent
- **Cost-Benefit**: High cost, Medium benefit (only saves ~2-3 minutes)
- **Over-Engineering Risk**: Medium (complexity not justified by time savings)
- **Rejected**: Over-engineering for minimal time savings

**Chosen Solution**: Option 2 - Conditional Step Execution

**Implementation**:
- Check if new data exists before processing `espn.prob_event_state`
- Check if materialized views need refresh (compare latest data timestamps)
- Skip steps if no new data (efficiency)

**Pros and Cons Analysis**:

**Pros**:
- **Completeness**: All required steps executed automatically
- **Efficiency**: Skips unnecessary steps when no new data
- **Reliability**: One-click operation, no manual steps

**Cons**:
- **Complexity**: More conditional logic to maintain
- **Testing**: Need to test both "new data" and "no new data" scenarios

**Risk Assessment**:
- **Risk 1**: Materialized view refresh fails - Mitigated by error handling and logging
- **Risk 2**: Long refresh time blocks update task - Mitigated by `CONCURRENTLY` option (allows queries during refresh)

## Implementation Plan

### Phase 1: Add `espn.prob_event_state` Processing (Duration: 2 hours)
**Objective**: Integrate `materialize_espn_prob_event_state.py` into refetch process

**Dependencies**: None (script already exists)

**Deliverables**: 
- `process_espn_prob_event_state()` function in `update.py`
- Step 7 added to `run_update_task()`
- Error handling and logging

#### Tasks
- **[Task 1]**: Implement `process_espn_prob_event_state()` function
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Review `materialize_espn_prob_event_state.py` usage

- **[Task 2]**: Add Step 7 to `run_update_task()`
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1 complete

### Phase 2: Add Materialized View Refresh (Duration: 2 hours)
**Objective**: Add automatic refresh of materialized views after data updates

**Dependencies**: Phase 1 (should run after all data loading)

**Deliverables**:
- `refresh_materialized_views()` function in `update.py`
- Step 8 added to `run_update_task()`
- Error handling and logging

#### Tasks
- **[Task 1]**: Implement `refresh_materialized_views()` function
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Understand materialized view refresh SQL syntax

- **[Task 2]**: Add Step 8 to `run_update_task()`
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Task 1 complete

### Phase 3: Expand Cache Clearing (Duration: 1 hour)
**Objective**: Clear all affected caches after data updates

**Dependencies**: None (can run independently)

**Deliverables**:
- Expanded cache clearing in `run_update_task()`
- Clear `get_aggregate_stats.cache`
- Clear simulation caches (if applicable)

#### Tasks
- **[Task 1]**: Expand cache clearing section
  - **Files**: `webapp/api/endpoints/update.py`
  - **Effort**: 1 hour
  - **Prerequisites**: Identify all cache locations

### Phase 4: Testing and Validation (Duration: 1 hour)
**Objective**: Test complete refetch flow end-to-end

**Dependencies**: Phases 1-3 complete

**Deliverables**:
- Test refetch with new data
- Test refetch with no new data (should skip unnecessary steps)
- Verify webapp endpoints return fresh data
- Verify materialized views are refreshed

#### Tasks
- **[Task 1]**: Run end-to-end test
  - **Files**: Test script or manual testing
  - **Effort**: 1 hour
  - **Prerequisites**: Phases 1-3 complete

## Risk Assessment

### Technical Risks
- **Risk 1**: Materialized view refresh (`derived.snapshot_features_v1`) takes 10+ minutes, blocking update task
  - **Probability**: Medium
  - **Impact**: Medium (update task appears hung)
  - **Mitigation**: Use `CONCURRENTLY` option (allows queries during refresh), add progress logging
  - **Contingency**: Add timeout, log progress, allow cancellation

- **Risk 2**: `materialize_espn_prob_event_state.py` script fails for some games
  - **Probability**: Low
  - **Impact**: Low (script has error handling, continues on errors)
  - **Mitigation**: Script already has error handling, collect errors in results
  - **Contingency**: Log errors, continue with other steps

- **Risk 3**: Database connection timeout during long-running refresh
  - **Probability**: Low
  - **Impact**: Medium (refresh fails, needs retry)
  - **Mitigation**: Use connection pooling, increase timeout
  - **Contingency**: Retry logic, error reporting

### Business Risks
- **Risk 1**: Refetch takes longer (adds 5-10 minutes for materialized view refresh)
  - **Probability**: High
  - **Impact**: Low (users expect long-running operation)
  - **Mitigation**: Add progress logging, set expectations in UI
  - **Contingency**: Make refresh optional (flag to skip)

### Resource Risks
- **Risk 1**: Database load during materialized view refresh
  - **Probability**: Medium
  - **Impact**: Low (CONCURRENTLY option minimizes impact)
  - **Mitigation**: Use `CONCURRENTLY` option, schedule during low-traffic periods
  - **Contingency**: Make refresh optional, run during off-hours

## Success Metrics and Monitoring

### Performance Metrics
- **Response Time**: Refetch completes in 10-20 minutes (up from 5-15 minutes) ([+33% time, but complete])
- **Throughput**: All 10 steps complete successfully ([Baseline: 7/10] → [Target: 10/10] ([+43% completion])
- **Error Rate**: < 5% failure rate for new steps ([Target: < 5%])

### Quality Metrics
- **Completeness**: All webapp endpoints return fresh data after refetch ([Target: 100%])
- **Automation**: No manual steps required after refetch ([Target: 0 manual steps])

### Business Metrics
- **User Satisfaction**: Users can trust one-click refetch ([Target: 100% satisfaction])
- **Support Burden**: Reduced support requests about missing data ([Target: -50% requests])

### Monitoring Strategy
- **Real-time Monitoring**: Log each step completion in `run_update_task()`
- **Alert Thresholds**: Alert if materialized view refresh takes > 15 minutes (unusual, should be 5-10 minutes)
- **Reporting**: Include step completion status in update status endpoint response

## Appendices

### Appendix A: Code Samples

#### Current Step Function Pattern

```python
def load_espn_scoreboard(repo_root: Path, min_date: date | None = None) -> tuple[bool, str]:
    """Load ESPN scoreboard files into database."""
    script_path = repo_root / "scripts" / "load_espn_scoreboard.py"
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    cmd = [python_bin, str(script_path), "--scoreboard-dir", str(scoreboard_dir)]
    # ... execute with subprocess.run(), handle errors ...
    return success, message
```

#### Proposed New Step Functions

```python
def process_espn_prob_event_state(repo_root: Path, season_label: str) -> tuple[bool, str]:
    """Process espn.prob_event_state from probabilities_raw_items."""
    script_path = repo_root / "scripts" / "process" / "materialize_espn_prob_event_state.py"
    if not script_path.exists():
        return False, f"Script not found: {script_path}"
    
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    cmd = [
        python_bin, str(script_path),
        "--dsn", os.environ["DATABASE_URL"],
        "--season-label", season_label
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes
            env=os.environ.copy()
        )
        if result.returncode == 0:
            return True, "Processed prob_event_state"
        else:
            return False, f"Error processing prob_event_state: {result.stderr}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

def refresh_materialized_views() -> tuple[bool, str]:
    """Refresh materialized views after data updates."""
    try:
        with get_db_connection() as conn:
            logger.info("[REFRESH_VIEWS] Refreshing derived.snapshot_features_v1...")
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;")
            logger.info("[REFRESH_VIEWS] ✓ Refreshed snapshot_features_v1")
            return True, "Materialized view refreshed"
    except Exception as e:
        return False, f"Error refreshing view: {str(e)}"
```

### Appendix B: Database Schema References

#### Tables Used by Webapp

1. **`espn.scoreboard_games`** - ✅ Loaded by Step 2
2. **`espn.probabilities_raw_items`** - ✅ Loaded by Step 4
3. **`espn.prob_event_state`** - ❌ NOT processed (needs Step 7)
4. **`kalshi.markets`** - ✅ Loaded by Step 6
5. **`kalshi.candlesticks`** - ✅ Loaded by Step 8

#### Materialized Views Used by Scripts

1. **`derived.snapshot_features_v1`** - ❌ NOT refreshed (needs Step 8)

### Appendix C: Reference Materials

- **Update Endpoint**: `webapp/api/endpoints/update.py`
- **Materialize Script**: `scripts/process/materialize_espn_prob_event_state.py`
- **Materialized View Docs**: `cursor-files/docs/sprint_13_completion_report.md`
- **Webapp Dependencies**: `webapp/api/endpoints/metadata.py`, `webapp/api/endpoints/games.py`

### Appendix D: Glossary

- **Materialized View**: Pre-computed query result stored as a table, needs refresh when source data changes
- **CONCURRENTLY**: PostgreSQL option for materialized view refresh that allows queries during refresh
- **UPSERT**: Database operation that inserts or updates (idempotent)
- **prob_event_state**: Derived table containing per-play game state (scores, time remaining) aligned with probabilities

---

## Document Validation

**IMPORTANT**: Use the comprehensive validation checklist in `ANALYSIS_STANDARDS.md` to ensure this analysis meets all quality standards.

