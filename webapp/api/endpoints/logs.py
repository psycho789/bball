"""
Logs endpoint - read application logs.

Design Pattern: Repository Pattern for file access + WebSocket Pattern for streaming
Algorithm: File reading with tailing support (last N lines) + File monitoring for WebSocket streaming
Big O: O(n) where n = number of lines to read
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Set
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..logging_config import LOG_DIR, get_logger

router = APIRouter()
logger = get_logger(__name__)

# Log file path
LOG_FILE = LOG_DIR / "winprob_api.log"

# Track active WebSocket connections for log streaming
_active_log_connections: Set[WebSocket] = set()


@router.get("/api/logs/health")
def logs_health() -> dict[str, str]:
    """Health check endpoint to verify logs router is working."""
    return {"status": "ok", "router": "logs", "websocket_route": "/ws/logs"}


@router.get("/api/logs")
def get_logs(
    lines: Optional[int] = Query(default=500, ge=1, le=10000, description="Number of lines to return (from end of file)"),
    tail: Optional[bool] = Query(default=False, description="Stream logs in real-time (SSE)")
) -> dict[str, str | int]:
    """
    Get application logs.
    
    Args:
        lines: Number of lines to return from the end of the file (default: 500, max: 10000)
        tail: If True, stream logs in real-time using Server-Sent Events (not implemented yet)
    
    Returns:
        Dictionary with log content and metadata
    
    Raises:
        HTTPException: If log file doesn't exist or can't be read
    """
    if not LOG_FILE.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found: {LOG_FILE}")
    
    try:
        # Read the entire file
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get last N lines
        total_lines = len(all_lines)
        start_line = max(0, total_lines - lines)
        log_lines = all_lines[start_line:]
        
        # Join lines and return
        log_content = ''.join(log_lines)
        
        return {
            "content": log_content,
            "total_lines": total_lines,
            "returned_lines": len(log_lines),
            "start_line": start_line + 1,  # 1-indexed for display
            "end_line": total_lines
        }
    except Exception as e:
        logger.error(f"Error reading log file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


@router.get("/logs/stream")
def stream_logs():
    """
    Stream logs in real-time using Server-Sent Events (SSE).
    
    This endpoint streams new log lines as they are written to the file.
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    import asyncio
    import time
    
    async def generate():
        """Generate SSE events for new log lines."""
        if not LOG_FILE.exists():
            yield f"data: {__import__('json').dumps({'error': 'Log file not found'})}\n\n"
            return
        
        # Get initial file size
        last_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        
        # Send initial message
        yield f"data: {json.dumps({'status': 'connected', 'file': str(LOG_FILE)})}\n\n"
        
        # Read existing content first
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                f.seek(0, 2)  # Seek to end
                initial_pos = f.tell()
                f.seek(max(0, initial_pos - 10000))  # Read last 10KB
                initial_content = f.read()
                if initial_content:
                    yield f"data: {json.dumps({'type': 'initial', 'content': initial_content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        # Monitor file for changes
        while True:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms
                
                if not LOG_FILE.exists():
                    continue
                
                current_size = LOG_FILE.stat().st_size
                
                if current_size > last_size:
                    # File has grown, read new content
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        f.seek(last_size)
                        new_content = f.read()
                        
                        if new_content:
                            yield f"data: {json.dumps({'type': 'update', 'content': new_content})}\n\n"
                        
                        last_size = current_size
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(1)  # Wait before retrying
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket endpoint for streaming application logs in real-time.
    
    Design Pattern: WebSocket Handler Pattern + Observer Pattern
    Algorithm: File monitoring with polling + broadcast to connected clients
    Big O: O(1) per connection, O(n) for broadcasting where n = number of connected clients
    
    Message format sent to client:
        {
            "type": "initial" | "update" | "error",
            "content": "log lines...",
            "timestamp": "2025-01-28T12:34:56Z"
        }
    """
    client_ip = None
    if websocket.client:
        client_ip = websocket.client.host
    
    logger.info(f"WebSocket log connection attempt from {client_ip}")
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket log connection accepted from {client_ip}")
    except Exception as e:
        logger.error(f"Error accepting WebSocket connection from {client_ip}: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except Exception:
            pass
        return
    
    # Add to active connections
    _active_log_connections.add(websocket)
    
    try:
        # Send initial log content (last 500 lines)
        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    # Get last 500 lines
                    start_line = max(0, len(all_lines) - 500)
                    initial_content = ''.join(all_lines[start_line:])
                    
                    await websocket.send_json({
                        "type": "initial",
                        "content": initial_content,
                        "total_lines": len(all_lines),
                        "returned_lines": len(all_lines) - start_line
                    })
            else:
                await websocket.send_json({
                    "type": "initial",
                    "content": "Log file not found.",
                    "total_lines": 0,
                    "returned_lines": 0
                })
        except Exception as e:
            logger.error(f"Error sending initial logs: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": f"Error reading log file: {str(e)}"
            })
        
        # Monitor log file for changes
        try:
            last_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        except Exception as e:
            logger.error(f"Error getting initial log file size: {e}", exc_info=True)
            last_size = 0
        
        while True:
            try:
                # Check for new log content every 500ms
                await asyncio.sleep(0.5)
                
                if not LOG_FILE.exists():
                    continue
                
                current_size = LOG_FILE.stat().st_size
                
                if current_size > last_size:
                    # File has grown, read new content
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        f.seek(last_size)
                        new_content = f.read()
                        
                        if new_content:
                            await websocket.send_json({
                                "type": "update",
                                "content": new_content
                            })
                        
                        last_size = current_size
                
                # Handle incoming messages (ping/pong for connection health)
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    try:
                        data = json.loads(message)
                        if data.get("type") == "ping":
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": asyncio.get_event_loop().time()
                            })
                    except json.JSONDecodeError:
                        pass
                except asyncio.TimeoutError:
                    # No message received, continue monitoring
                    continue
                    
            except WebSocketDisconnect:
                logger.info("WebSocket log connection disconnected")
                break
            except Exception as e:
                logger.error(f"Error in log WebSocket: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                })
                await asyncio.sleep(1)  # Wait before retrying
    
    except WebSocketDisconnect:
        logger.info("WebSocket log connection closed normally")
    except Exception as e:
        logger.error(f"WebSocket log error: {e}", exc_info=True)
    finally:
        # Remove from active connections
        _active_log_connections.discard(websocket)
        logger.info(f"WebSocket log connection cleaned up. Active connections: {len(_active_log_connections)}")

