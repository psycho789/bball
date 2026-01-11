"""
WebSocket connection manager for live game data streaming.

Design Pattern: Singleton Pattern + Connection Pool Pattern + Observer Pattern
Algorithm: O(1) for connection operations, O(n) for broadcasting where n = connected clients
Big O: 
  - Connection registration: O(1)
  - Broadcast: O(n) where n = subscribers per game
  - State transitions: O(1)
"""

import asyncio
import time
from typing import Dict, Set, Optional, Any
from collections import defaultdict
from datetime import datetime, timezone
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from .logging_config import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for live game data streaming.
    
    Singleton pattern - one instance manages all connections.
    Connection pool pattern - groups connections by game_id.
    Observer pattern - broadcasts data to all subscribers for a game.
    """
    
    _instance: Optional['WebSocketManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the WebSocket manager (only once)."""
        if self._initialized:
            return
        
        # Connection registry: game_id -> set of WebSocket connections
        # Using weakref to avoid memory leaks if connections aren't properly closed
        self._connections: Dict[str, Set[weakref.ref]] = defaultdict(set)
        
        # Connection metadata: track last activity, IP, etc.
        self._connection_metadata: Dict[weakref.ref, Dict[str, Any]] = {}
        
        # Data source tracking: which games have active data sources
        self._active_data_sources: Dict[str, Set[str]] = defaultdict(set)  # game_id -> set of source types
        
        # Connection health monitoring
        self._last_ping: Dict[weakref.ref, float] = {}
        self._ping_interval = 30.0  # Send ping every 30 seconds
        self._connection_timeout = 300.0  # Close idle connections after 5 minutes
        
        # Connection limits
        self._max_connections_per_ip = 10
        self._ip_connection_count: Dict[str, int] = defaultdict(int)
        
        self._initialized = True
        logger.info("WebSocketManager initialized")
    
    async def connect(self, game_id: str, websocket: WebSocket, client_ip: Optional[str] = None) -> bool:
        """
        Register a WebSocket connection for a game.
        
        Args:
            game_id: Game identifier
            websocket: WebSocket connection
            client_ip: Client IP address (for rate limiting)
        
        Returns:
            True if connection accepted, False if rejected (rate limit)
        """
        # Check connection limits per IP
        if client_ip:
            if self._ip_connection_count[client_ip] >= self._max_connections_per_ip:
                logger.warning(f"Connection rejected: IP {client_ip} has reached max connections ({self._max_connections_per_ip})")
                return False
            self._ip_connection_count[client_ip] += 1
        
        # Create weak reference to avoid memory leaks
        ws_ref = weakref.ref(websocket, lambda ref: self._on_connection_garbage_collected(game_id, ref, client_ip))
        
        async with self._lock:
            self._connections[game_id].add(ws_ref)
            self._connection_metadata[ws_ref] = {
                "game_id": game_id,
                "connected_at": time.time(),
                "last_activity": time.time(),
                "client_ip": client_ip,
            }
            self._last_ping[ws_ref] = time.time()
        
        logger.info(f"WebSocket connected: game_id={game_id}, total_connections={len(self._connections[game_id])}, client_ip={client_ip}")
        return True
    
    async def disconnect(self, game_id: str, websocket: WebSocket, client_ip: Optional[str] = None) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            game_id: Game identifier
            websocket: WebSocket connection to disconnect
            client_ip: Client IP address (for cleanup)
        """
        # Find the weakref for this websocket
        ws_ref = None
        async with self._lock:
            for ref in list(self._connections[game_id]):
                ws = ref()
                if ws is websocket:
                    ws_ref = ref
                    break
        
        if ws_ref:
            await self._remove_connection(game_id, ws_ref, client_ip)
            logger.info(f"WebSocket disconnected: game_id={game_id}, remaining_connections={len(self._connections[game_id])}")
        else:
            logger.warning(f"WebSocket disconnect: connection not found for game_id={game_id}")
    
    def _on_connection_garbage_collected(self, game_id: str, ws_ref: weakref.ref, client_ip: Optional[str] = None) -> None:
        """Handle connection cleanup when weakref is garbage collected."""
        # This runs in a different context, so we can't use async
        # Schedule cleanup in event loop if available
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._remove_connection(game_id, ws_ref, client_ip))
        except RuntimeError:
            # No event loop, connection already cleaned up
            pass
    
    async def _remove_connection(self, game_id: str, ws_ref: weakref.ref, client_ip: Optional[str] = None) -> None:
        """Remove connection from registry and cleanup metadata."""
        async with self._lock:
            if game_id in self._connections:
                self._connections[game_id].discard(ws_ref)
                if not self._connections[game_id]:
                    # No more connections for this game, clean up
                    del self._connections[game_id]
            
            # Clean up metadata
            if ws_ref in self._connection_metadata:
                metadata = self._connection_metadata.pop(ws_ref)
                client_ip = client_ip or metadata.get("client_ip")
            
            if ws_ref in self._last_ping:
                del self._last_ping[ws_ref]
        
        # Update IP connection count
        if client_ip:
            self._ip_connection_count[client_ip] = max(0, self._ip_connection_count[client_ip] - 1)
            if self._ip_connection_count[client_ip] == 0:
                del self._ip_connection_count[client_ip]
    
    async def broadcast(self, game_id: str, data: Dict[str, Any]) -> int:
        """
        Broadcast data to all connected clients for a game.
        
        Args:
            game_id: Game identifier
            data: Data to broadcast (must be JSON-serializable)
        
        Returns:
            Number of clients that received the message
        """
        if game_id not in self._connections:
            return 0
        
        # Get current connections (weakrefs may have been garbage collected)
        active_connections = []
        dead_refs = []
        
        async with self._lock:
            for ws_ref in list(self._connections[game_id]):
                ws = ws_ref()
                if ws is None:
                    dead_refs.append(ws_ref)
                else:
                    active_connections.append(ws)
                    # Update last activity
                    if ws_ref in self._connection_metadata:
                        self._connection_metadata[ws_ref]["last_activity"] = time.time()
        
        # Clean up dead references
        if dead_refs:
            async with self._lock:
                for ref in dead_refs:
                    self._connections[game_id].discard(ref)
                    if ref in self._connection_metadata:
                        del self._connection_metadata[ref]
                    if ref in self._last_ping:
                        del self._last_ping[ref]
        
        # Broadcast to active connections
        sent_count = 0
        import json
        
        for ws in active_connections:
            try:
                await ws.send_json(data)
                sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to send message to WebSocket (connection may be closed): {e}")
                # Connection is dead, will be cleaned up on next broadcast or ping
        
        if sent_count > 0:
            logger.debug(f"Broadcast to {sent_count} clients for game_id={game_id}")
        
        return sent_count
    
    async def send_error(self, game_id: str, error_message: str) -> None:
        """Send error message to all clients for a game."""
        error_data = {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(game_id, error_data)
    
    def start_data_source(self, game_id: str, source_type: str) -> None:
        """Mark that a data source is active for a game."""
        self._active_data_sources[game_id].add(source_type)
        logger.debug(f"Data source started: game_id={game_id}, source_type={source_type}")
    
    def stop_data_source(self, game_id: str, source_type: str) -> None:
        """Mark that a data source has stopped for a game."""
        if game_id in self._active_data_sources:
            self._active_data_sources[game_id].discard(source_type)
            if not self._active_data_sources[game_id]:
                del self._active_data_sources[game_id]
        logger.debug(f"Data source stopped: game_id={game_id}, source_type={source_type}")
    
    def has_data_source(self, game_id: str, source_type: str) -> bool:
        """Check if a data source is active for a game."""
        return source_type in self._active_data_sources.get(game_id, set())
    
    async def ping_connections(self) -> None:
        """Send ping to all connections to check health."""
        current_time = time.time()
        dead_refs = []
        
        async with self._lock:
            for game_id, connections in list(self._connections.items()):
                for ws_ref in list(connections):
                    ws = ws_ref()
                    if ws is None:
                        dead_refs.append((game_id, ws_ref))
                        continue
                    
                    last_ping = self._last_ping.get(ws_ref, 0)
                    if current_time - last_ping >= self._ping_interval:
                        try:
                            await ws.send_json({"type": "ping", "timestamp": current_time})
                            self._last_ping[ws_ref] = current_time
                        except Exception:
                            dead_refs.append((game_id, ws_ref))
        
        # Clean up dead connections
        for game_id, ws_ref in dead_refs:
            metadata = self._connection_metadata.get(ws_ref, {})
            client_ip = metadata.get("client_ip")
            await self._remove_connection(game_id, ws_ref, client_ip)
    
    async def cleanup_idle_connections(self) -> None:
        """Close connections that have been idle for too long."""
        current_time = time.time()
        idle_refs = []
        
        async with self._lock:
            for game_id, connections in list(self._connections.items()):
                for ws_ref in list(connections):
                    metadata = self._connection_metadata.get(ws_ref, {})
                    last_activity = metadata.get("last_activity", 0)
                    
                    if current_time - last_activity > self._connection_timeout:
                        idle_refs.append((game_id, ws_ref, metadata.get("client_ip")))
        
        # Close idle connections
        for game_id, ws_ref, client_ip in idle_refs:
            ws = ws_ref()
            if ws:
                try:
                    await ws.close(code=1000, reason="Idle timeout")
                except Exception:
                    pass
            await self._remove_connection(game_id, ws_ref, client_ip)
            logger.info(f"Closed idle connection: game_id={game_id}")
    
    def get_connection_count(self, game_id: Optional[str] = None) -> int:
        """Get total number of connections (optionally for a specific game)."""
        if game_id:
            return len([ref for ref in self._connections.get(game_id, []) if ref() is not None])
        return sum(len([ref for ref in conns if ref() is not None]) for conns in self._connections.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_connections": self.get_connection_count(),
            "games_with_connections": len(self._connections),
            "active_data_sources": {
                game_id: list(sources) 
                for game_id, sources in self._active_data_sources.items()
            },
            "connections_per_game": {
                game_id: len([ref for ref in conns if ref() is not None])
                for game_id, conns in self._connections.items()
            },
        }


# Global singleton instance
_manager_instance: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WebSocketManager()
    return _manager_instance

