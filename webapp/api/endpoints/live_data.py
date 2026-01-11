"""
Live data WebSocket endpoint for streaming real-time probability data.

Design Pattern: WebSocket Handler Pattern
Algorithm: O(1) per message send
Big O: O(1) for connection handling, O(n) for data aggregation where n = data points
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from datetime import datetime, timezone

from ..db import get_db_connection
from ..websocket_manager import get_websocket_manager
from ..logging_config import get_logger
from ..data_sources.espn_live import start_espn_fetcher, stop_espn_fetcher
from ..data_sources.kalshi_live import start_kalshi_fetcher, stop_kalshi_fetcher

router = APIRouter()
logger = get_logger(__name__)


def _is_game_live(game_id: str) -> bool:
    """
    Check if a game is currently live.
    
    This is a simple check - in production, you might want to check
    the live games endpoint or database.
    """
    # For now, we'll accept any game_id and let the data sources handle it
    # In the future, we could check the live_games endpoint
    return True


@router.websocket("/ws/live/{game_id}")
async def websocket_live_data(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint for streaming live probability data for a game.
    
    Args:
        websocket: WebSocket connection
        game_id: Game identifier (ESPN competition_id)
    
    Message format sent to client:
        {
            "type": "data",
            "espn": [...],  # ESPN probability data points
            "kalshi": [...],  # Kalshi market data points
            "timestamp": "2025-01-28T12:34:56Z"
        }
    
    Error message format:
        {
            "type": "error",
            "message": "Error description",
            "timestamp": "2025-01-28T12:34:56Z"
        }
    """
    # Get client IP for rate limiting
    client_ip = None
    if websocket.client:
        client_ip = websocket.client.host
    
    # Validate game_id exists in database and get event_id
    event_id = None
    try:
        with get_db_connection() as conn:
            check_sql = "SELECT event_id FROM espn.scoreboard_games WHERE event_id = %s LIMIT 1"
            result = conn.execute(check_sql, (game_id,)).fetchone()
            if not result:
                await websocket.close(code=1008, reason=f"Game {game_id} not found")
                logger.warning(f"WebSocket connection rejected: game_id={game_id} not found")
                return
            event_id = result[0]
    except Exception as e:
        logger.error(f"Error checking game_id {game_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")
        return
    
    # Accept WebSocket connection
    await websocket.accept()
    logger.info(f"WebSocket connection accepted: game_id={game_id}, client_ip={client_ip}")
    
    manager = get_websocket_manager()
    
    # Register connection
    connection_accepted = await manager.connect(game_id, websocket, client_ip)
    if not connection_accepted:
        await websocket.close(code=1008, reason="Connection limit exceeded")
        logger.warning(f"WebSocket connection rejected: rate limit exceeded for IP {client_ip}")
        return
    
    # Start data sources if this is the first connection for this game
    connection_count = manager.get_connection_count(game_id)
    if connection_count == 1:
        # First connection - start data sources
        logger.info(f"First connection for game_id={game_id}, starting data sources")
        if event_id:
            await start_espn_fetcher(game_id, event_id, game_id)
        # Try to start Kalshi fetcher (may not exist for all games)
        await start_kalshi_fetcher(game_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "game_id": game_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Keep connection alive and handle incoming messages (if any)
        while True:
            try:
                # Wait for messages from client (with timeout)
                # Client can send ping messages to keep connection alive
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                
                # Handle client messages (ping/pong, etc.)
                try:
                    import json
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                except json.JSONDecodeError:
                    logger.debug(f"Received non-JSON message from client: {message}")
            except asyncio.TimeoutError:
                # No message received, connection is still alive
                # This is normal - we're just waiting for data to broadcast
                continue
            except WebSocketDisconnect:
                # Client disconnected normally
                logger.info(f"WebSocket client disconnected: game_id={game_id}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: game_id={game_id}")
    except Exception as e:
        logger.error(f"WebSocket error for game_id={game_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass  # Connection may already be closed
    finally:
        # Cleanup: unregister connection
        await manager.disconnect(game_id, websocket, client_ip)
        
        # Stop data sources if this was the last connection for this game
        connection_count = manager.get_connection_count(game_id)
        if connection_count == 0:
            logger.info(f"Last connection closed for game_id={game_id}, stopping data sources")
            await stop_espn_fetcher(game_id)
            await stop_kalshi_fetcher(game_id)
        
        logger.info(f"WebSocket connection cleaned up: game_id={game_id}")


import asyncio  # For asyncio.wait_for

