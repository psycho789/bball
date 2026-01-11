"""
Kalshi live data fetching for real-time market price updates.

Design Pattern: Polling Pattern with async/await (REST API)
Algorithm: HTTP polling with configurable interval
Big O: O(1) per poll request

Note: Using REST API polling instead of WebSocket for initial implementation.
WebSocket can be added later if needed.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from ..websocket_manager import get_websocket_manager
from ..db import get_db_connection
from ..logging_config import get_logger

logger = get_logger(__name__)


class KalshiLiveDataFetcher:
    """
    Fetches live Kalshi market data and broadcasts to WebSocket clients.
    
    Polls Kalshi candlesticks endpoint and tracks timestamps to detect new data.
    Uses REST API polling (WebSocket can be added later).
    """
    
    def __init__(self, game_id: str, ticker: str, poll_interval: float = 10.0):
        """
        Initialize Kalshi live data fetcher.
        
        Args:
            game_id: Game identifier (ESPN event_id)
            ticker: Kalshi market ticker (e.g., "KXNBAGAME-25DEC19SASATL-ATL")
            poll_interval: Polling interval in seconds (default: 10 seconds)
        """
        self.game_id = game_id
        self.ticker = ticker
        self.poll_interval = poll_interval
        self.last_timestamp = 0
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.manager = get_websocket_manager()
    
    async def start(self) -> None:
        """Start polling Kalshi endpoint."""
        if self.running:
            logger.warning(f"Kalshi fetcher already running for game_id={self.game_id}")
            return
        
        self.running = True
        self.manager.start_data_source(self.game_id, "kalshi")
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Kalshi live data fetcher started: game_id={self.game_id}, ticker={self.ticker}, poll_interval={self.poll_interval}s")
    
    async def stop(self) -> None:
        """Stop polling Kalshi endpoint."""
        self.running = False
        self.manager.stop_data_source(self.game_id, "kalshi")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Kalshi live data fetcher stopped: game_id={self.game_id}")
    
    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self.running:
            try:
                await self._fetch_and_broadcast()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Kalshi polling loop for game_id={self.game_id}: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(self.poll_interval)
    
    async def _fetch_and_broadcast(self) -> None:
        """Fetch new data from Kalshi database and broadcast to clients."""
        # For now, we'll query the database for recent candlesticks
        # In the future, this could call the Kalshi REST API directly
        
        try:
            with get_db_connection() as conn:
                # Get recent candlesticks (last 5 minutes)
                current_time = int(time.time())
                start_time = current_time - 300  # Last 5 minutes
                
                sql = """
                    SELECT 
                        period_ts,
                        price_close,
                        yes_bid_close,
                        yes_ask_close,
                        volume
                    FROM kalshi.candlesticks
                    WHERE ticker = %s
                      AND period_ts >= to_timestamp(%s)
                      AND period_ts > to_timestamp(%s)
                    ORDER BY period_ts ASC
                """
                
                rows = conn.execute(sql, (self.ticker, start_time, self.last_timestamp)).fetchall()
                
                if not rows:
                    return  # No new data
                
                # Transform to our format
                kalshi_data = []
                max_timestamp = self.last_timestamp
                
                for row in rows:
                    period_ts = row[0]
                    if isinstance(period_ts, datetime):
                        timestamp_unix = int(period_ts.timestamp())
                    else:
                        timestamp_unix = int(period_ts)
                    
                    price_close = row[1]  # Already in cents (0-100)
                    yes_bid = row[2] if row[2] is not None else price_close
                    yes_ask = row[3] if row[3] is not None else price_close
                    
                    kalshi_data.append({
                        "time": timestamp_unix,
                        "price": price_close / 100.0,  # Convert cents to 0-1
                        "yes_bid": yes_bid / 100.0,
                        "yes_ask": yes_ask / 100.0,
                    })
                    
                    max_timestamp = max(max_timestamp, timestamp_unix)
                
                if kalshi_data:
                    # Update last timestamp
                    self.last_timestamp = max_timestamp
                    
                    # Broadcast to WebSocket clients
                    broadcast_data = {
                        "type": "data",
                        "kalshi": kalshi_data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    sent_count = await self.manager.broadcast(self.game_id, broadcast_data)
                    logger.debug(f"Broadcast {len(kalshi_data)} Kalshi data points to {sent_count} clients for game_id={self.game_id}")
        
        except Exception as e:
            logger.error(f"Error fetching Kalshi data for game_id={self.game_id}: {e}", exc_info=True)
            # Send error to clients
            await self.manager.send_error(self.game_id, f"Kalshi data fetch error: {str(e)}")


def _get_kalshi_ticker_for_game(game_id: str) -> Optional[str]:
    """
    Get Kalshi ticker for a game from database.
    
    Returns the first matching ticker, or None if no market exists.
    """
    try:
        with get_db_connection() as conn:
            sql = """
                SELECT ticker
                FROM kalshi.markets_with_games
                WHERE espn_event_id = %s
                LIMIT 1
            """
            result = conn.execute(sql, (game_id,)).fetchone()
            if result:
                return result[0]
    except Exception as e:
        logger.warning(f"Error getting Kalshi ticker for game_id={game_id}: {e}")
    return None


# Global registry of active fetchers
_active_fetchers: Dict[str, KalshiLiveDataFetcher] = {}


async def start_kalshi_fetcher(game_id: str) -> bool:
    """
    Start Kalshi live data fetcher for a game.
    
    Args:
        game_id: Game identifier (ESPN event_id)
    
    Returns:
        True if fetcher started, False if no Kalshi market exists
    """
    if game_id in _active_fetchers:
        logger.warning(f"Kalshi fetcher already exists for game_id={game_id}")
        return True
    
    ticker = _get_kalshi_ticker_for_game(game_id)
    if not ticker:
        logger.debug(f"No Kalshi market found for game_id={game_id}")
        return False
    
    fetcher = KalshiLiveDataFetcher(game_id, ticker)
    _active_fetchers[game_id] = fetcher
    await fetcher.start()
    return True


async def stop_kalshi_fetcher(game_id: str) -> None:
    """Stop Kalshi live data fetcher for a game."""
    if game_id in _active_fetchers:
        fetcher = _active_fetchers.pop(game_id)
        await fetcher.stop()

