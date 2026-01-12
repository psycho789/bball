"""
Win Probability Chart Web App - FastAPI Backend

Data Sources:
  - ESPN: espn.probabilities_raw_items, espn.prob_event_state, espn.scoreboard_games
  - Kalshi: kalshi.candlesticks, kalshi.markets (via espn_event_id join)

Endpoints:
  GET /api/games              - List recent games with probability data
  GET /api/games/{id}/probs   - Probability time series (ESPN + Kalshi)
  GET /api/games/{id}/meta    - Team metadata for a game

Usage:
  cd webapp && uvicorn api.main:app --reload --port 8000
  
Debug Mode:
  DEBUG=true uvicorn api.main:app --reload --port 8000

Design Pattern: Modular Router Pattern
Algorithm: FastAPI router composition
Big O: O(1) for route registration
"""

import asyncio
import threading
import signal
import sys
import os
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import setup_logging, get_logger, DEBUG_MODE
from .endpoints import games, probabilities, metadata, stats, aggregate_stats, live_games, live_data, simulation, update, model_evaluation, grid_search, logs, export
from .websocket_manager import get_websocket_manager

# Global flag for graceful shutdown
_shutdown_requested = threading.Event()

# Check if preload should run
# Skip preload if:
# 1. PRELOAD_CACHE env var is set to 'false' or '0'
# 2. Running in reload mode (uvicorn sets RELOADER env var when --reload is used)
# This prevents slow preloads during development when code changes trigger reloads
SHOULD_PRELOAD = (
    os.getenv("PRELOAD_CACHE", "true").lower() not in ("false", "0")
    and os.getenv("RELOADER") is None  # Skip in reload mode (development)
)

# Set up logging (overwrite log file on app restart)
logger = setup_logging(overwrite_log_file=True)

# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Win Probability Chart API",
    description="API for NBA win probability charts using ESPN and Kalshi data",
    version="2.0.0",
)

if DEBUG_MODE:
    logger.info("=" * 60)
    logger.info("DEBUG MODE ENABLED - Verbose logging active")
    logger.info("=" * 60)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Request timing middleware
class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request/response timing for performance debugging.
    
    Design Pattern: Middleware Pattern
    Algorithm: Time measurement before and after request processing
    Big O: O(1) overhead per request
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request start
        logger.debug(f"[TIMING] {request.method} {request.url.path} - START")
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log request completion with timing
            status_code = response.status_code
            if duration > 1.0:
                logger.warning(
                    f"[TIMING] {request.method} {request.url.path} - COMPLETE "
                    f"({duration:.3f}s) - Status: {status_code} - SLOW REQUEST"
                )
            elif duration > 0.5:
                logger.info(
                    f"[TIMING] {request.method} {request.url.path} - COMPLETE "
                    f"({duration:.3f}s) - Status: {status_code}"
                )
            else:
                logger.debug(
                    f"[TIMING] {request.method} {request.url.path} - COMPLETE "
                    f"({duration:.3f}s) - Status: {status_code}"
                )
            
            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"[TIMING] {request.method} {request.url.path} - ERROR "
                f"({duration:.3f}s) - {type(e).__name__}: {e}"
            )
            raise


app.add_middleware(TimingMiddleware)

# Register API routers
app.include_router(games.router, prefix="/api", tags=["games"])
app.include_router(probabilities.router, prefix="/api", tags=["probabilities"])
app.include_router(metadata.router, prefix="/api", tags=["metadata"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(aggregate_stats.router, prefix="/api", tags=["aggregate_stats"])
app.include_router(model_evaluation.router, prefix="/api", tags=["model_evaluation"])
app.include_router(live_games.router, prefix="/api", tags=["live_games"])
app.include_router(live_data.router, tags=["live_data"])  # No prefix - has /ws/live/{game_id} route
app.include_router(simulation.router, tags=["simulation"])  # No prefix - has both /api/simulation/* and /ws/simulation/{request_id} routes
app.include_router(update.router, tags=["update"])  # No prefix - has both /api/update/* and /ws/update/status routes
app.include_router(grid_search.router, tags=["grid_search"])  # No prefix - has both /api/grid-search/* and /ws/grid-search/{request_id} routes
app.include_router(logs.router, tags=["logs"])  # No prefix - has both /api/logs and /ws/logs routes
app.include_router(export.router, prefix="/api", tags=["export"])  # Export endpoint at /api/export/html


# =============================================================================
# Startup Event - Preload Cache
# =============================================================================

async def websocket_health_monitor():
    """Background task to monitor WebSocket connection health."""
    manager = get_websocket_manager()
    while True:
        try:
            await asyncio.sleep(30)  # Run every 30 seconds
            await manager.ping_connections()
            await manager.cleanup_idle_connections()
        except Exception as e:
            logger.error(f"Error in WebSocket health monitor: {e}", exc_info=True)


@app.on_event("startup")
async def preload_cache():
    """
    Preload cache on server startup.
    
    Fetches initial games and their stats to warm up the cache,
    so the first user request is fast.
    
    Skips preload if:
    - PRELOAD_CACHE env var is set to 'false' or '0'
    - Running in reload mode (detected via RELOADER env var)
    
    Note: 
    - Stats for completed games are persisted in the database (derived.game_stats)
    - In-memory cache is persisted to disk (.cache/ directory) and survives reloads
    - Preload is skipped in reload mode to avoid slow startup during development
    
    Design Pattern: Warm-up Pattern for caching
    Algorithm: Background thread for sync operations
    Big O: O(n) where n = number of games preloaded
    """
    # Initialize WebSocket manager
    manager = get_websocket_manager()
    logger.info("WebSocket manager initialized")
    
    # Start background tasks for connection health monitoring
    asyncio.create_task(websocket_health_monitor())
    
    if not SHOULD_PRELOAD:
        logger.info("Skipping cache preload (PRELOAD_CACHE=false or running in reload mode)")
        logger.info("Note: Cache is persisted to disk, so previous cache will be loaded automatically")
        return
    
    def _preload():
        logger.info("Starting cache preload process...")
        try:
            # Check for shutdown signal before starting
            if _shutdown_requested.is_set():
                logger.info("Shutdown requested, skipping preload")
                return
            
            # Preload initial games (first 50)
            logger.debug("Preloading games cache...")
            try:
                logger.debug("Calling games.list_games() with season='2025-26', limit=50, offset=0, sort_by='date', sort_order='desc', has_kalshi=True")
                # Match exact URL: /api/games?season=2025-26&limit=50&offset=0&sort_by=date&sort_order=desc&has_kalshi=true
                games_result = games.list_games(
                    season="2025-26",
                    limit=50,
                    offset=0,
                    sort_by="date",
                    sort_order="desc",
                    has_kalshi=True  # Default to only games with Kalshi data
                )
                logger.debug(f"Games result received: {games_result is not None}, has games key: {'games' in games_result if games_result else False}")
                if games_result:
                    total = games_result.get('total', 0)
                    games_list = games_result.get('games', [])
                    logger.info(f"Games query returned: total={total}, games_in_response={len(games_list)}")
                    if total == 0:
                        logger.warning("No games found for season '2025-26'. This might be normal if:")
                        logger.warning("  - The season hasn't started yet")
                        logger.warning("  - Games haven't been loaded into the database")
                        logger.warning("  - Games don't have final scores yet")
            except Exception as e:
                logger.error(f"Error calling list_games: {e}", exc_info=True)
                games_result = None
            
            # Check for shutdown before continuing
            if _shutdown_requested.is_set():
                logger.info("Shutdown requested during games preload, stopping")
                return
            
            if games_result and games_result.get("games"):
                game_list = games_result["games"]
                logger.info(f"Preloaded {len(game_list)} games into cache")
                
                # Preload stats for first 20 games (to avoid too many requests)
                # Stats are cached individually, so this warms up the cache
                logger.debug("Preloading stats cache for first 20 games...")
                preload_count = 0
                for idx, game in enumerate(game_list[:20], 1):
                    # Check for shutdown before each game
                    if _shutdown_requested.is_set():
                        logger.info(f"Shutdown requested, stopping stats preload at game {idx}/20")
                        break
                    
                    try:
                        game_id = game["game_id"]
                        logger.debug(f"Preloading stats for game {idx}/20: {game_id}")
                        stats.get_game_stats(game_id)
                        preload_count += 1
                    except Exception as e:
                        logger.debug(f"Skipping game {game_id} - stats preload failed: {e}")
                        continue
                
                logger.info(f"Preloaded stats for {preload_count} games")
                
                # Check for shutdown before aggregate stats (this one takes a long time)
                if _shutdown_requested.is_set():
                    logger.info("Shutdown requested, skipping aggregate stats preload")
                    return
                
                # Preload aggregate stats (will use cache if available)
                logger.info("Warming aggregate stats cache (will use existing cache if valid)...")
                try:
                    # This will use cache if it exists and is not expired (24 hour TTL)
                    # If cache is missing/expired, it will calculate fresh
                    result = aggregate_stats.get_aggregate_stats(season="2025-26")
                    if result:
                        games_count = result.get("games_with_stats", 0)
                        logger.info(f"Aggregate stats ready (from cache or fresh calculation): {games_count} games with stats")
                    else:
                        logger.warning("Aggregate stats returned empty result")
                except Exception as e:
                    logger.warning(f"Aggregate stats preload failed: {e}", exc_info=True)
            else:
                logger.warning("No games found to preload")
        except KeyboardInterrupt:
            logger.info("Preload interrupted by user")
        except Exception as e:
            # Don't fail startup if preload fails
            logger.error(f"Cache preload failed: {e}", exc_info=True)
    
    # Run preload in background thread (non-blocking)
    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_requested.set()
    # Give threads a moment to finish, then exit
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


@app.on_event("shutdown")
async def shutdown_tasks():
    """
    Shutdown tasks: save cache and cleanup WebSocket connections.
    
    Ensures cache is persisted even if server is stopped abruptly.
    """
    logger.info("Server shutting down, cache will be saved automatically by cache instances")
    
    # Cleanup WebSocket connections
    manager = get_websocket_manager()
    stats = manager.get_stats()
    logger.info(f"WebSocket manager stats on shutdown: {stats}")

# =============================================================================
# Static Files (serve frontend)
# =============================================================================

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/favicon.ico")
def serve_favicon():
    """Serve the favicon (browsers request this automatically)."""
    favicon_path = static_dir / "favicon.svg"
    if favicon_path.exists():
        # Serve SVG as favicon.ico (browsers will accept it)
        return Response(content=favicon_path.read_bytes(), media_type="image/svg+xml")
    return Response(status_code=404)


@app.get("/")
def serve_index():
    """Serve the main HTML page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Frontend not found"}
