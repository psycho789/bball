"""
Database connection utilities.

Design Pattern: Singleton Pattern for connection pool
Algorithm: Connection pooling via psycopg.ConnectionPool
Big O: O(1) for connection acquisition from pool
"""

import os
from contextlib import contextmanager
from typing import Iterator, Optional
import psycopg
import threading
from queue import Queue, Empty

from .logging_config import get_logger, DEBUG_MODE

logger = get_logger(__name__)

# Global connection pool (initialized on first use)
_connection_pool: Optional[Queue[psycopg.Connection]] = None
_pool_lock = threading.Lock()
_pool_dsn: Optional[str] = None
_pool_size = 5  # Maximum number of connections in pool


def _get_connection_pool() -> Queue[psycopg.Connection]:
    """Get or create the global connection pool."""
    global _connection_pool, _pool_dsn
    
    if _connection_pool is None:
        with _pool_lock:
            # Double-check after acquiring lock
            if _connection_pool is None:
                _pool_dsn = os.environ.get(
                    "DATABASE_URL",
                    "postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse"
                )
                
                if DEBUG_MODE:
                    # Mask password in logs
                    safe_dsn = _pool_dsn.split('@')[-1] if '@' in _pool_dsn else _pool_dsn
                    logger.debug(f"Creating connection pool to: ...@{safe_dsn} (max_size={_pool_size})")
                
                # Create queue-based connection pool
                _connection_pool = Queue(maxsize=_pool_size)
                
                # Pre-populate pool with a few connections
                for _ in range(min(2, _pool_size)):
                    try:
                        conn = psycopg.connect(_pool_dsn)
                        _connection_pool.put(conn)
                    except Exception as e:
                        logger.warning(f"Failed to create initial pool connection: {e}")
                
                if DEBUG_MODE:
                    logger.debug(f"Connection pool created with {_connection_pool.qsize()} initial connections")
    
    return _connection_pool


@contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
    """
    Get database connection from connection pool.
    
    Uses a simple queue-based connection pool to reuse connections efficiently.
    Connections are automatically returned to the pool when the context exits.
    
    Default: postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM ...")
    """
    pool = _get_connection_pool()
    conn: Optional[psycopg.Connection] = None
    
    try:
        # Try to get connection from pool (non-blocking)
        try:
            conn = pool.get_nowait()
            if DEBUG_MODE:
                logger.debug("Connection acquired from pool (reused)")
        except Empty:
            # Pool is empty, create new connection
            if DEBUG_MODE:
                logger.debug("Pool empty, creating new connection")
            conn = psycopg.connect(_pool_dsn)
        
        yield conn
    finally:
        # Return connection to pool if it's still valid
        if conn is not None:
            try:
                # Check if connection is still valid
                conn.execute("SELECT 1")
                # Return to pool (non-blocking - if pool is full, just close it)
                try:
                    pool.put_nowait(conn)
                    if DEBUG_MODE:
                        logger.debug("Connection returned to pool")
                except:
                    # Pool is full, close the connection
                    conn.close()
                    if DEBUG_MODE:
                        logger.debug("Pool full, connection closed")
            except Exception:
                # Connection is invalid, close it
                try:
                    conn.close()
                except:
                    pass
                if DEBUG_MODE:
                    logger.debug("Invalid connection closed (not returned to pool)")

