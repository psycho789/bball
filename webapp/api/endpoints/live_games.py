"""
Live games endpoint - detect and list currently live NBA games.

Design Pattern: Repository Pattern for data access + External API integration
Algorithm: HTTP polling ESPN endpoint + database lookup
Big O: O(n) where n = number of live games
"""

from typing import Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import json

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger

# Import fetch utilities from scripts directory
import sys
from pathlib import Path
scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))
from lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes

router = APIRouter()
logger = get_logger(__name__)


def _get_today_date_str() -> str:
    """Get today's date in YYYYMMDD format."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _fetch_espn_scoreboard(date: str) -> dict[str, Any]:
    """
    Fetch ESPN scoreboard for a given date.
    
    Returns the full scoreboard JSON response.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}&limit=1000"
    
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
            raise RuntimeError(f"ESPN API returned HTTP {status}")
        
        data = parse_json_bytes(body)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch ESPN scoreboard: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch live games from ESPN: {str(e)}"
        )


def _is_live_status(status_name: str) -> bool:
    """Check if a game status indicates the game is currently live."""
    live_statuses = [
        "STATUS_IN_PROGRESS",
        "STATUS_HALFTIME",
        "STATUS_DELAYED",
        "STATUS_END_PERIOD",
    ]
    return status_name in live_statuses


@router.get("/live/games")
@cached(ttl_seconds=30)  # Cache for 30 seconds (short TTL since games can start/end)
def get_live_games() -> dict[str, Any]:
    """
    Get list of currently live NBA games.
    
    Fetches from ESPN scoreboard API and matches to database for metadata.
    Returns games that are currently in progress.
    
    Returns:
        {
            "games": [
                {
                    "game_id": "401705226",
                    "event_id": "401705226",
                    "competition_id": "401705226",
                    "home_team": "Philadelphia 76ers",
                    "away_team": "Los Angeles Lakers",
                    "home_team_abbrev": "PHI",
                    "away_team_abbrev": "LAL",
                    "home_score": 105,
                    "away_score": 98,
                    "status": "STATUS_IN_PROGRESS",
                    "start_time": "2025-01-28T00:00:00Z"
                }
            ],
            "timestamp": "2025-01-28T12:34:56Z",
            "count": 2
        }
    """
    today = _get_today_date_str()
    logger.debug(f"Fetching live games for date: {today}")
    
    try:
        # Fetch ESPN scoreboard
        scoreboard_data = _fetch_espn_scoreboard(today)
        events = scoreboard_data.get("events", [])
        
        if not isinstance(events, list):
            logger.warning("ESPN scoreboard returned invalid events array")
            return {
                "games": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": 0
            }
        
        # Filter to live games
        live_events = []
        for event in events:
            status = event.get("status", {})
            status_type = status.get("type", {})
            status_name = status_type.get("name", "")
            
            if _is_live_status(status_name):
                live_events.append(event)
        
        logger.debug(f"Found {len(live_events)} live games out of {len(events)} total events")
        
        # Match to database for metadata and build response
        live_games = []
        
        with get_db_connection() as conn:
            for event in live_events:
                event_id = event.get("id")
                if not event_id:
                    continue
                
                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                
                comp = competitions[0]
                competition_id = comp.get("id", event_id)
                
                # Get team info from event
                competitors = comp.get("competitors", [])
                home_competitor = next((c for c in competitors if c.get("homeAway") == "home"), {})
                away_competitor = next((c for c in competitors if c.get("homeAway") == "away"), {})
                
                home_team_obj = home_competitor.get("team", {})
                away_team_obj = away_competitor.get("team", {})
                
                home_team_name = home_team_obj.get("displayName", "")
                away_team_name = away_team_obj.get("displayName", "")
                home_team_abbrev = home_team_obj.get("abbreviation", "")
                away_team_abbrev = away_team_obj.get("abbreviation", "")
                
                home_score = home_competitor.get("score")
                away_score = away_competitor.get("score")
                
                # Get game start time from database if available
                game_start_time = None
                db_team_info = None
                
                try:
                    db_query = """
                        SELECT 
                            event_date,
                            home_team_abbrev,
                            away_team_abbrev,
                            home_team_display_name,
                            away_team_display_name
                        FROM espn.scoreboard_games
                        WHERE event_id = %s
                        LIMIT 1
                    """
                    db_row = conn.execute(db_query, (str(event_id),)).fetchone()
                    
                    if db_row:
                        game_start_time = db_row[0]
                        # Prefer database team info if available (more consistent)
                        db_team_info = {
                            "home_abbrev": db_row[1],
                            "away_abbrev": db_row[2],
                            "home_name": db_row[3],
                            "away_name": db_row[4],
                        }
                except Exception as e:
                    logger.debug(f"Could not fetch database info for game {event_id}: {e}")
                
                # Use database team info if available, otherwise use ESPN API data
                if db_team_info:
                    home_team_abbrev = db_team_info["home_abbrev"] or home_team_abbrev
                    away_team_abbrev = db_team_info["away_abbrev"] or away_team_abbrev
                    home_team_name = db_team_info["home_name"] or home_team_name
                    away_team_name = db_team_info["away_name"] or away_team_name
                
                # Format start time
                start_time_str = None
                if game_start_time:
                    if isinstance(game_start_time, datetime):
                        start_time_str = game_start_time.isoformat()
                    else:
                        start_time_str = str(game_start_time)
                
                live_games.append({
                    "game_id": str(competition_id),  # Use competition_id as game_id
                    "event_id": str(event_id),
                    "competition_id": str(competition_id),
                    "home_team": home_team_name,
                    "away_team": away_team_name,
                    "home_team_abbrev": home_team_abbrev,
                    "away_team_abbrev": away_team_abbrev,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": status_name,
                    "start_time": start_time_str,
                })
        
        return {
            "games": live_games,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(live_games)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching live games: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error fetching live games: {str(e)}"
        )

