"""
ESPN live data fetching for real-time probability updates.

Design Pattern: Polling Pattern with async/await
Algorithm: HTTP polling with configurable interval
Big O: O(1) per poll request
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone

from ..websocket_manager import get_websocket_manager
from ..logging_config import get_logger

# Import fetch utilities from scripts directory
import sys
from pathlib import Path
scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))
from lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes

logger = get_logger(__name__)


class ESPNLiveDataFetcher:
    """
    Fetches live ESPN probability data and broadcasts to WebSocket clients.
    
    Polls ESPN probabilities endpoint and tracks sequence numbers to detect new data.
    """
    
    def __init__(self, game_id: str, event_id: str, competition_id: str, poll_interval: float = 5.0):
        """
        Initialize ESPN live data fetcher.
        
        Args:
            game_id: Game identifier (competition_id)
            event_id: ESPN event ID
            competition_id: ESPN competition ID
            poll_interval: Polling interval in seconds (default: 5 seconds)
        """
        self.game_id = game_id
        self.event_id = event_id
        self.competition_id = competition_id
        self.poll_interval = poll_interval
        self.last_sequence = 0
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.manager = get_websocket_manager()
    
    async def start(self) -> None:
        """Start polling ESPN endpoint."""
        if self.running:
            logger.warning(f"ESPN fetcher already running for game_id={self.game_id}")
            return
        
        self.running = True
        self.manager.start_data_source(self.game_id, "espn")
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"ESPN live data fetcher started: game_id={self.game_id}, poll_interval={self.poll_interval}s")
    
    async def stop(self) -> None:
        """Stop polling ESPN endpoint."""
        self.running = False
        self.manager.stop_data_source(self.game_id, "espn")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"ESPN live data fetcher stopped: game_id={self.game_id}")
    
    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self.running:
            try:
                await self._fetch_and_broadcast()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ESPN polling loop for game_id={self.game_id}: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(self.poll_interval)
    
    async def _fetch_and_broadcast(self) -> None:
        """Fetch new data from ESPN and broadcast to clients."""
        url = (
            f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
            f"/events/{self.event_id}/competitions/{self.competition_id}/probabilities?limit=1000"
        )
        
        retry = HttpRetry(
            max_attempts=3,
            timeout_seconds=20.0,
            base_backoff_seconds=1.0,
            max_backoff_seconds=10.0,
            jitter_seconds=0.25,
            deadline_seconds=60.0,
        )
        
        try:
            status, headers, body = http_get_bytes(url, retry=retry)
            if status != 200:
                logger.warning(f"ESPN API returned HTTP {status} for game_id={self.game_id}")
                return
            
            data = parse_json_bytes(body)
            items = data.get("items", [])
            
            if not items:
                return
            
            # Find new items (sequence > last_sequence)
            new_items = []
            max_sequence = self.last_sequence
            
            for item in items:
                seq = item.get("sequenceNumber", 0)
                if seq > self.last_sequence:
                    new_items.append(item)
                    max_sequence = max(max_sequence, seq)
            
            if not new_items:
                return  # No new data
            
            # Update last sequence
            self.last_sequence = max_sequence
            
            # Transform to our format
            espn_data = []
            for item in new_items:
                last_modified_str = item.get("lastModified", "")
                # Parse timestamp (format: "2025-01-29T03:35Z")
                try:
                    if last_modified_str.endswith("Z"):
                        last_modified_str = last_modified_str[:-1] + "+00:00"
                    timestamp = datetime.fromisoformat(last_modified_str)
                    timestamp_unix = int(timestamp.timestamp())
                except Exception:
                    logger.warning(f"Failed to parse timestamp: {last_modified_str}")
                    continue
                
                home_win_pct = item.get("homeWinPercentage", 0)
                away_win_pct = item.get("awayWinPercentage", 0)
                
                espn_data.append({
                    "time": timestamp_unix,
                    "home_prob": home_win_pct / 100.0,  # Convert 0-100 to 0-1
                    "away_prob": away_win_pct / 100.0,
                })
            
            if espn_data:
                # Broadcast to WebSocket clients
                broadcast_data = {
                    "type": "data",
                    "espn": espn_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                sent_count = await self.manager.broadcast(self.game_id, broadcast_data)
                logger.debug(f"Broadcast {len(espn_data)} ESPN data points to {sent_count} clients for game_id={self.game_id}")
        
        except Exception as e:
            logger.error(f"Error fetching ESPN data for game_id={self.game_id}: {e}", exc_info=True)
            # Send error to clients (but don't stop the fetcher - it will retry)
            await self.manager.send_error(self.game_id, f"ESPN data fetch error: {str(e)}")
            # Continue running - will retry on next poll


# Global registry of active fetchers
_active_fetchers: Dict[str, ESPNLiveDataFetcher] = {}


async def start_espn_fetcher(game_id: str, event_id: str, competition_id: Optional[str] = None) -> None:
    """
    Start ESPN live data fetcher for a game.
    
    Args:
        game_id: Game identifier
        event_id: ESPN event ID
        competition_id: ESPN competition ID (defaults to event_id if not provided)
    """
    if competition_id is None:
        competition_id = event_id
    
    if game_id in _active_fetchers:
        logger.warning(f"ESPN fetcher already exists for game_id={game_id}")
        return
    
    fetcher = ESPNLiveDataFetcher(game_id, event_id, competition_id)
    _active_fetchers[game_id] = fetcher
    await fetcher.start()


async def stop_espn_fetcher(game_id: str) -> None:
    """Stop ESPN live data fetcher for a game."""
    if game_id in _active_fetchers:
        fetcher = _active_fetchers.pop(game_id)
        await fetcher.stop()

