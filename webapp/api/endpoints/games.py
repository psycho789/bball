"""
Games endpoint - list games with pagination support.

Design Pattern: Repository Pattern for data access
Algorithm: SQL aggregation with pagination
Big O: O(n) where n = number of games returned
"""

import time
from typing import Any, Optional
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/games")
@cached(ttl_seconds=3600)  # Cache for 1 hour (reduced from 24h to allow faster updates)
def list_games(
    season: str = Query("2025-26", description="Season label (e.g., '2025-26')"),
    limit: int = Query(50, ge=1, le=200, description="Max games to return"),
    offset: int = Query(0, ge=0, description="Number of games to skip (for pagination)"),
    has_kalshi: Optional[bool] = Query(True, description="Filter by Kalshi data availability. Note: query only returns games with Kalshi data, so False will return empty results."),
    sort_by: str = Query("date", description="Sort field: date, volatility, std_dev, range, score"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    team_filter: Optional[str] = Query(None, description="Filter by team abbreviation (home or away)"),
    date_from: Optional[str] = Query(None, description="Filter games from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter games to date (YYYY-MM-DD)"),
) -> dict[str, Any]:
    """
    List recent games with probability data from ESPN that have Kalshi candlestick data.
    
    Only returns games that have both ESPN probability data and Kalshi market candlestick data.
    Uses MATERIALIZED CTEs for optimized query performance.
    
    Returns games ordered by most recent first.
    
    Design Decision: Use espn.scoreboard_games for team metadata instead of JSON files
    Pros: Single source of truth, faster queries, no filesystem access needed
    Cons: Requires scoreboard data to be ingested first
    
    Design Decision: Filter to only games with Kalshi data at query level
    Pros: Better performance with MATERIALIZED CTEs, simpler query logic
    Cons: Cannot return games without Kalshi data (has_kalshi=False will return empty)
    """
    # Convert Query objects to their actual values if needed (when called directly, not via FastAPI)
    def extract_value(param, default_value):
        """Extract actual value from Query object or return the value itself."""
        if hasattr(param, 'default'):
            # It's a Query object, get the default
            return param.default if param.default is not None else default_value
        return param if param is not None else default_value
    
    season = str(extract_value(season, "2025-26"))
    limit = int(extract_value(limit, 50))
    offset = int(extract_value(offset, 0))
    has_kalshi = extract_value(has_kalshi, None)
    sort_by = str(extract_value(sort_by, "date"))
    sort_order = str(extract_value(sort_order, "desc"))
    team_filter = extract_value(team_filter, None)
    date_from = extract_value(date_from, None)
    date_to = extract_value(date_to, None)
    
    request_start = time.time()
    logger.debug(f"[TIMING] list_games - START - season={season}, limit={limit}, offset={offset}, "
                 f"has_kalshi={has_kalshi}, sort_by={sort_by}, sort_order={sort_order}, "
                 f"team_filter={team_filter}, date_from={date_from}, date_to={date_to}")
    
    with get_db_connection() as conn:
        db_conn_time = time.time() - request_start
        logger.debug(f"[TIMING] list_games - DB connection: {db_conn_time:.3f}s")
        
        query_start = time.time()
        # Optimized query using MATERIALIZED CTEs for better performance
        # Only returns games that have Kalshi market data
        sql = """
        WITH kalshi_games AS MATERIALIZED (
          SELECT DISTINCT km.espn_event_id
          FROM kalshi.markets km
          WHERE km.espn_event_id IS NOT NULL
        ),
        game_stats AS MATERIALIZED (
          SELECT
              p.game_id,
              p.season_label,
              COUNT(*) as prob_count,
              MAX(p.created_at) as last_updated,
              MIN(p.home_win_percentage) as min_prob,
              MAX(p.home_win_percentage) as max_prob,
              AVG(p.home_win_percentage) as mean_prob,
              STDDEV(p.home_win_percentage) as std_dev,
              MAX(p.home_win_percentage) - MIN(p.home_win_percentage) as prob_range
          FROM espn.probabilities_raw_items p
          JOIN kalshi_games kg
            ON kg.espn_event_id = p.game_id
          WHERE p.season_label = %s
          GROUP BY p.game_id, p.season_label
          HAVING COUNT(*) > 100
        ),
        game_outcomes AS MATERIALIZED (
          -- Prefer prob_event_state for final scores/winner; fallback to scoreboard_games.
          SELECT
              COALESCE(pe.game_id, sg.event_id) AS game_id,
              COALESCE(pe.final_home_score, sg.home_score) AS final_home_score,
              COALESCE(pe.final_away_score, sg.away_score) AS final_away_score,
              COALESCE(
                pe.winner,
                CASE
                  WHEN sg.home_score > sg.away_score THEN 1
                  WHEN sg.away_score > sg.home_score THEN 0
                  ELSE NULL
                END
              ) AS winner
          FROM (
              SELECT
                  e.game_id,
                  MAX(e.home_score) AS final_home_score,
                  MAX(e.away_score) AS final_away_score,
                  MAX(e.final_winning_team) AS winner
              FROM espn.prob_event_state e
              GROUP BY e.game_id
          ) pe
          FULL OUTER JOIN espn.scoreboard_games sg
            ON pe.game_id = sg.event_id
        )
        SELECT
            g.game_id,
            g.season_label,
            g.prob_count,
            g.last_updated,
            o.final_home_score,
            o.final_away_score,
            o.winner,
            sg.home_team_abbrev,
            sg.away_team_abbrev,
            sg.home_team_display_name,
            sg.away_team_display_name,
            sg.event_date,
            true AS has_kalshi,
            g.min_prob,
            g.max_prob,
            g.mean_prob,
            g.std_dev,
            g.prob_range
        FROM game_stats g
        LEFT JOIN game_outcomes o
          ON g.game_id = o.game_id
        LEFT JOIN espn.scoreboard_games sg
          ON g.game_id = sg.event_id
        WHERE 1=1
          AND (
            (o.final_home_score IS NOT NULL
             AND (o.final_home_score > 0 OR o.final_away_score > 0))
            OR sg.event_id IS NOT NULL
          )
        """
        
        params: list[Any] = [season]
        
        # Note: has_kalshi filter is no longer needed since query only returns games with Kalshi data
        # If has_kalshi=False is requested, we should return empty result or handle differently
        if has_kalshi is False:
            logger.warning("has_kalshi=False requested but query only returns games with Kalshi data. Returning empty result.")
            sql += " AND 1=0"  # Force empty result
        
        logger.debug(f"Final SQL WHERE clause: {sql.split('WHERE')[1] if 'WHERE' in sql else 'N/A'}")
        
        if team_filter:
            team_filter_str = str(team_filter).upper() if team_filter else None
            if team_filter_str:
                sql += " AND (sg.home_team_abbrev = %s OR sg.away_team_abbrev = %s)"
                params.append(team_filter_str)
                params.append(team_filter_str)
        
        if date_from:
            try:
                date_from_str = str(date_from).strip() if date_from else None
                if date_from_str and date_from_str.lower() not in ['none', 'null', '']:
                    date_from_obj = datetime.strptime(date_from_str, "%Y-%m-%d")
                    sql += " AND sg.event_date >= %s"
                    params.append(date_from_obj)
            except (ValueError, TypeError) as e:
                # Only raise error if it's actually a string that failed to parse
                if isinstance(date_from, str):
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
                # Otherwise, it's likely a Query object with no value, so skip it
        
        if date_to:
            try:
                date_to_str = str(date_to).strip() if date_to else None
                if date_to_str and date_to_str.lower() not in ['none', 'null', '']:
                    date_to_obj = datetime.strptime(date_to_str, "%Y-%m-%d")
                    sql += " AND sg.event_date <= %s"
                    params.append(date_to_obj)
            except (ValueError, TypeError) as e:
                # Only raise error if it's actually a string that failed to parse
                if isinstance(date_to, str):
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
                # Otherwise, it's likely a Query object with no value, so skip it
        
        # Get total count for pagination (before LIMIT/OFFSET)
        count_sql = f"SELECT COUNT(*) FROM ({sql}) as total"
        logger.debug(f"Executing count query with {len(params)} parameters")
        count_start = time.time()
        total_count = conn.execute(count_sql, params).fetchone()[0]
        count_time = time.time() - count_start
        logger.debug(f"[TIMING] list_games - Count query: {count_time:.3f}s ({total_count} total games)")
        
        # Build ORDER BY clause
        sort_order_upper = str(sort_order).upper() if sort_order else "DESC"
        if sort_order_upper not in ["ASC", "DESC"]:
            sort_order_upper = "DESC"
        
        sort_field_map = {
            "date": "sg.event_date",
            "volatility": "g.std_dev",  # Using std_dev as proxy for volatility
            "std_dev": "g.std_dev",
            "range": "g.prob_range",
            "score": "(o.final_home_score + o.final_away_score)",  # Total points
        }
        
        sort_by_str = str(sort_by).lower() if sort_by else "date"
        sort_field = sort_field_map.get(sort_by_str, "sg.event_date")
        sql += f" ORDER BY {sort_field} {sort_order_upper} NULLS LAST LIMIT %s OFFSET %s"
        params.append(limit)
        params.append(offset)
        
        logger.debug(f"Executing main query with {len(params)} parameters (limit={limit}, offset={offset})")
        main_query_start = time.time()
        rows = conn.execute(sql, params).fetchall()
        main_query_time = time.time() - main_query_start
        logger.debug(f"[TIMING] list_games - Main query: {main_query_time:.3f}s ({len(rows)} rows)")
    
    games = []
    logger.debug(f"Processing {len(rows)} game rows...")
    for idx, row in enumerate(rows, 1):
        logger.debug(f"Processing game {idx}/{len(rows)}: game_id={row[0] if row else 'N/A'}")
        game_data = {
            "game_id": str(row[0]),
            "season": row[1],
            "prob_count": row[2],
            "last_updated": row[3].isoformat() if row[3] else None,
            "final_home_score": row[4],
            "final_away_score": row[5],
            "home_won": row[6] == 0 if row[6] is not None else None,
            "home_team_abbr": row[7] or "HOME",
            "away_team_abbr": row[8] or "AWAY",
            "home_team_name": row[9] or "Home Team",
            "away_team_name": row[10] or "Away Team",
            "game_date": row[11].isoformat() if row[11] else None,
            "has_kalshi": row[12],
            # Lightweight stats (calculated efficiently in SQL)
            "stats": {
                "min_probability": float(row[13]) if row[13] is not None else None,
                "max_probability": float(row[14]) if row[14] is not None else None,
                "mean_probability": float(row[15]) if row[15] is not None else None,
                "standard_deviation": float(row[16]) if row[16] is not None else None,
                "probability_range": float(row[17]) if row[17] is not None else None,
            } if len(row) > 13 else None,
        }
        games.append(game_data)
    
    result = {
        "games": games,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(games) < total_count,
    }
    
    total_time = time.time() - request_start
    logger.info(f"[TIMING] list_games - TOTAL: {total_time:.3f}s - "
                f"returning {len(games)} games (total={total_count}, has_more={result['has_more']})")
    return result

