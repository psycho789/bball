"""
Metadata endpoint - get team metadata for a game.

Design Pattern: Repository Pattern for data access
Algorithm: SQL aggregation with joins
Big O: O(1) for single game lookup
"""

import time
from typing import Any
from fastapi import APIRouter, HTTPException

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger
from ..constants import NBA_TEAM_COLORS
from .utils import get_cache_ttl_for_game

router = APIRouter()
logger = get_logger(__name__)


@router.get("/games/{game_id}/meta")
@cached(ttl_seconds=86400 * 365, dynamic_ttl=lambda result: get_cache_ttl_for_game(result))
def get_game_metadata(game_id: str) -> dict[str, Any]:
    """
    Get team metadata for a game.
    
    Returns team names, abbreviations, colors, final score, and Kalshi market info.
    
    Data sources:
      - espn.prob_event_state: Final score, winner
      - espn.scoreboard_games: Team names, abbreviations, game date
      - kalshi.markets: Market tickers if available
    """
    request_start = time.time()
    logger.debug(f"[TIMING] get_game_metadata({game_id}) - START")
    
    with get_db_connection() as conn:
        db_conn_time = time.time() - request_start
        logger.debug(f"[TIMING] get_game_metadata({game_id}) - DB connection: {db_conn_time:.3f}s")
        
        # Get game info from ESPN tables
        # Try prob_event_state first, fallback to scoreboard_games if not found
        query_start = time.time()
        sql = """
        SELECT 
            MAX(e.home_score) as final_home,
            MAX(e.away_score) as final_away,
            MAX(e.final_winning_team) as winner,
            sg.home_team_abbrev,
            sg.away_team_abbrev,
            sg.home_team_display_name,
            sg.away_team_display_name,
            sg.event_date,
            MIN(p.last_modified_utc) as game_start_timestamp
        FROM espn.prob_event_state e
        LEFT JOIN espn.scoreboard_games sg ON e.game_id = sg.event_id
        LEFT JOIN espn.probabilities_raw_items p ON e.game_id = p.game_id
        WHERE e.game_id = %s
        AND p.season_label = '2025-26'
        GROUP BY sg.home_team_abbrev, sg.away_team_abbrev, 
                 sg.home_team_display_name, sg.away_team_display_name,
                 sg.event_date
        """
        logger.debug(f"Executing metadata query for game_id={game_id}")
        row = conn.execute(sql, (game_id,)).fetchone()
        query_time = time.time() - query_start
        logger.debug(f"[TIMING] get_game_metadata({game_id}) - Main query: {query_time:.3f}s ({1 if row else 0} rows)")
        
        # Fallback: if prob_event_state doesn't have the game, try scoreboard_games directly
        # Only do this if the initial query returned no rows at all (not just NULL scores)
        if not row:
            logger.debug(f"Game not found in prob_event_state, trying scoreboard_games directly")
            fallback_start = time.time()
            fallback_sql = """
            SELECT 
                sg.home_score as final_home,
                sg.away_score as final_away,
                CASE WHEN sg.home_score > sg.away_score THEN 0
                     WHEN sg.away_score > sg.home_score THEN 1
                     ELSE NULL END as winner,
                sg.home_team_abbrev,
                sg.away_team_abbrev,
                sg.home_team_display_name,
                sg.away_team_display_name,
                sg.event_date,
                (SELECT MIN(last_modified_utc) FROM espn.probabilities_raw_items WHERE game_id = sg.event_id LIMIT 1) as game_start_timestamp
            FROM espn.scoreboard_games sg
            WHERE sg.event_id = %s
            LIMIT 1
            """
            row = conn.execute(fallback_sql, (game_id,)).fetchone()
            fallback_time = time.time() - fallback_start
            logger.debug(f"[TIMING] get_game_metadata({game_id}) - Fallback query: {fallback_time:.3f}s ({1 if row else 0} rows)")
        
        if not row or row[0] is None:
            logger.warning(f"No metadata found for game {game_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"No metadata for game {game_id}"
            )
        
        logger.debug(f"Processing metadata row for game {game_id}")
        
        final_home = int(row[0])
        final_away = int(row[1])
        home_won = row[2] == 0 if row[2] is not None else final_home > final_away
        
        home_abbr = row[3] or "HOME"
        away_abbr = row[4] or "AWAY"
        home_name = row[5] or "Home Team"
        away_name = row[6] or "Away Team"
        game_date = row[7]
        game_start_timestamp = int(row[8].timestamp()) if row[8] else None
        
        # Check for Kalshi market data
        kalshi_start = time.time()
        kalshi_sql = """
        SELECT DISTINCT ON (event_ticker)
            ticker,
            event_ticker,
            yes_sub_title,
            last_price,
            result
        FROM kalshi.markets
        WHERE espn_event_id = %s
        ORDER BY event_ticker, snapshot_id DESC
        """
        logger.debug(f"Executing Kalshi markets query for game_id={game_id}")
        kalshi_rows = conn.execute(kalshi_sql, (game_id,)).fetchall()
        kalshi_time = time.time() - kalshi_start
        logger.debug(f"[TIMING] get_game_metadata({game_id}) - Kalshi query: {kalshi_time:.3f}s ({len(kalshi_rows)} rows)")
        
        kalshi_markets = []
        kalshi_url = None
        for kr in kalshi_rows:
            event_ticker = kr[1]
            kalshi_markets.append({
                "ticker": kr[0],
                "event_ticker": event_ticker,
                "team": kr[2],
                "last_price": kr[3],
                "result": kr[4],
            })
            # Construct Kalshi URL from event_ticker
            # Format: https://kalshi.com/markets/{series_ticker}/nba-game/{event_ticker}
            # event_ticker format: KXNBAGAME-25DEC25MINDEN
            if event_ticker and not kalshi_url:
                # Extract series ticker (everything before the date)
                # KXNBAGAME-25DEC25MINDEN -> kxnbagame
                series_ticker = event_ticker.split('-')[0].lower() if '-' in event_ticker else event_ticker.lower()
                kalshi_url = f"https://kalshi.com/markets/{series_ticker}/nba-game/{event_ticker.lower()}"
    
    result = {
        "game_id": game_id,
        "home_team_abbr": home_abbr,
        "away_team_abbr": away_abbr,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "home_color": NBA_TEAM_COLORS.get(home_abbr, "#1f77b4"),
        "away_color": "#888888",
        "final_home_score": final_home,
        "final_away_score": final_away,
        "home_won": home_won,
        "game_date": game_date.isoformat() if game_date else None,
        "game_start_timestamp": game_start_timestamp,  # Unix timestamp from first ESPN probability record
        "kalshi_markets": kalshi_markets,
        "kalshi_url": kalshi_url,
    }
    
    total_time = time.time() - request_start
    logger.info(f"[TIMING] get_game_metadata({game_id}) - TOTAL: {total_time:.3f}s - "
                f"home={result['home_team_abbr']} vs away={result['away_team_abbr']}, "
                f"kalshi_markets={len(kalshi_markets)}")
    return result

