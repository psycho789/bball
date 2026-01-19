#!/usr/bin/env python3
"""
Load sportsbook odds data from CSV files into PostgreSQL.

Design Pattern: ETL Pattern (Extract, Transform, Load)
Algorithm: CSV parsing → team name normalization → odds conversion → 
           opening line identification → ESPN game mapping → database insert
Big O: O(n) where n = number of odds records

Supports two data sources:
1. nba_2008-2025.csv: Historical odds (American odds, abbreviations, 1 row per game)
2. nba_main_lines.csv: 2025-26 season odds (decimal odds, full names, time-series)

Usage:
  python scripts/load/load_sportsbook_odds.py \\
    --source nba_2008_2025 \\
    --csv data/stats-csv/nba_2008-2025.csv \\
    --dsn "$DATABASE_URL"
  
  python scripts/load/load_sportsbook_odds.py \\
    --source nba_main_lines \\
    --csv data/stats-csv/nba_main_lines.csv \\
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib.team_name_mapping import normalize_team_name
from scripts.lib.odds_conversion import (
    american_to_decimal,
    decimal_to_american,
    calculate_implied_prob,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-serializable formats.
    
    Converts:
    - pandas Timestamp -> ISO format string
    - datetime objects -> ISO format string
    - date objects -> ISO format string
    - numpy types -> native Python types
    - NaN/NaT -> None
    
    Design Pattern: Visitor Pattern for type conversion
    Algorithm: Recursive type checking and conversion
    Big O: O(n) where n = number of values in nested structure
    """
    if pd.isna(obj) or obj is None:
        return None
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, pd.Timedelta):
        return str(obj)
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, (pd.Int64Dtype, pd.Float64Dtype)):
        # Handle pandas nullable integer/float types
        return None if pd.isna(obj) else obj
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    else:
        # Try to convert numpy types
        try:
            import numpy as np
            if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                              np.int16, np.int32, np.int64, np.uint8, np.uint16,
                              np.uint32, np.uint64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float16, np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.bool_, np.bool)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        
        # Fallback: convert to string
        return str(obj)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load sportsbook odds CSV into Postgres.")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--source", required=True, choices=["nba_2008_2025", "nba_main_lines"],
                   help="Data source identifier")
    p.add_argument("--csv", required=True, help="Path to CSV file")
    p.add_argument("--dry-run", action="store_true", help="Process but don't insert into database")
    p.add_argument("--limit", type=int, help="Limit number of rows to process (for testing)")
    return p.parse_args()


def get_dsn(dsn: str | None) -> str:
    """Get database DSN from argument or environment."""
    if dsn:
        return dsn
    env_dsn = os.environ.get("DATABASE_URL")
    if not env_dsn:
        raise ValueError("Must provide --dsn or set DATABASE_URL environment variable")
    return env_dsn


def load_csv_file(csv_path: Path) -> pd.DataFrame:
    """Load CSV file into pandas DataFrame."""
    logger.info(f"Loading CSV file: {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} rows from CSV")
    return df


def transform_nba_2008_2025(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform nba_2008-2025.csv data for database insertion.
    
    This file has:
    - American odds (moneyline_away, moneyline_home)
    - Team abbreviations (away, home)
    - Single row per game (all are opening lines)
    - Single date per game
    
    Only processes games from 2017-18 season onwards (Oct 2017+) since
    ESPN data is only available from 2017.
    """
    logger.info("Transforming nba_2008-2025 data")
    
    # Filter to 2017-18 season and later (NBA season starts in October)
    # 2017-18 season starts October 2017
    min_date = pd.to_datetime('2017-10-01').date()
    
    # Parse dates and filter early
    original_count = len(df)
    df = df.copy()
    df['parsed_date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df[df['parsed_date'].notna()]
    df['game_date_obj'] = df['parsed_date'].dt.date
    df = df[df['game_date_obj'] >= min_date]
    
    if len(df) == 0:
        logger.warning("No games found after filtering to 2017-18 season and later")
        return pd.DataFrame()
    
    logger.info(f"Filtered to {len(df)} games from 2017-18 season onwards (from {original_count} total)")
    
    records = []
    
    for _, row in df.iterrows():
        # Normalize team names
        away_team_espn = normalize_team_name(str(row['away']))
        home_team_espn = normalize_team_name(str(row['home']))
        
        if not away_team_espn or not home_team_espn:
            logger.warning(f"Skipping row: unable to normalize teams (away={row['away']}, home={row['home']})")
            continue
        
        # Use already parsed date
        game_date = row['game_date_obj']
        
        # Parse odds (American format)
        try:
            moneyline_away_american = int(row['moneyline_away']) if pd.notna(row['moneyline_away']) else None
            moneyline_home_american = int(row['moneyline_home']) if pd.notna(row['moneyline_home']) else None
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping row: invalid moneyline values: {e}")
            continue
        
        # Convert American odds to decimal
        if moneyline_away_american:
            moneyline_away_decimal = american_to_decimal(moneyline_away_american)
            moneyline_away_implied_prob = calculate_implied_prob(moneyline_away_decimal)
        else:
            moneyline_away_decimal = None
            moneyline_away_implied_prob = None
        
        if moneyline_home_american:
            moneyline_home_decimal = american_to_decimal(moneyline_home_american)
            moneyline_home_implied_prob = calculate_implied_prob(moneyline_home_decimal)
        else:
            moneyline_home_decimal = None
            moneyline_home_implied_prob = None
        
        # Parse spread and total
        spread = float(row['spread']) if pd.notna(row['spread']) else None
        total = float(row['total']) if pd.notna(row['total']) else None
        
        # Create records for each market type
        # Moneyline - Away
        if moneyline_away_american:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'unknown',  # Source doesn't specify bookmaker
                'market_type': 'moneyline',
                'side': 'away',
                'line_value': None,
                'odds_american': moneyline_away_american,
                'odds_decimal': moneyline_away_decimal,
                'implied_prob': moneyline_away_implied_prob,
                'snapshot_timestamp': None,  # Single date per game
                'is_opening_line': True,  # All rows are opening lines
                'source_dataset': 'nba_2008_2025',
                'raw_data': row.to_dict(),
            })
        
        # Moneyline - Home
        if moneyline_home_american:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'unknown',
                'market_type': 'moneyline',
                'side': 'home',
                'line_value': None,
                'odds_american': moneyline_home_american,
                'odds_decimal': moneyline_home_decimal,
                'implied_prob': moneyline_home_implied_prob,
                'snapshot_timestamp': None,
                'is_opening_line': True,
                'source_dataset': 'nba_2008_2025',
                'raw_data': row.to_dict(),
            })
        
        # Spread - Home perspective (spread is from home team's perspective)
        if spread is not None:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'unknown',
                'market_type': 'spread',
                'side': 'home',
                'line_value': spread,
                'odds_american': None,  # Spread odds not provided in this file
                'odds_decimal': None,
                'implied_prob': None,
                'snapshot_timestamp': None,
                'is_opening_line': True,
                'source_dataset': 'nba_2008_2025',
                'raw_data': row.to_dict(),
            })
        
        # Total - Over
        if total is not None:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'unknown',
                'market_type': 'total',
                'side': 'over',
                'line_value': total,
                'odds_american': None,  # Total odds not provided in this file
                'odds_decimal': None,
                'implied_prob': None,
                'snapshot_timestamp': None,
                'is_opening_line': True,
                'source_dataset': 'nba_2008_2025',
                'raw_data': row.to_dict(),
            })
    
    result_df = pd.DataFrame(records)
    logger.info(f"Transformed {len(result_df)} records from {len(df)} games")
    return result_df


def transform_nba_main_lines(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform nba_main_lines.csv data for database insertion.
    
    This file has:
    - Decimal odds (team1_moneyline, team2_moneyline, spread_odds, total_odds)
    - Full team names (team1, team2)
    - Multiple rows per game (time-series)
    - Timestamps for each row
    """
    logger.info("Transforming nba_main_lines data")
    
    records = []
    
    for _, row in df.iterrows():
        # Normalize team names
        team1_espn = normalize_team_name(str(row['team1']))
        team2_espn = normalize_team_name(str(row['team2']))
        
        if not team1_espn or not team2_espn:
            logger.warning(f"Skipping row: unable to normalize teams (team1={row['team1']}, team2={row['team2']})")
            continue
        
        # Parse timestamp
        try:
            snapshot_timestamp = pd.to_datetime(row['timestamp']).tz_localize(None)
            if snapshot_timestamp.tzinfo is None:
                snapshot_timestamp = snapshot_timestamp.replace(tzinfo=timezone.utc)
            game_date = snapshot_timestamp.date()
        except Exception as e:
            logger.warning(f"Skipping row: invalid timestamp {row['timestamp']}: {e}")
            continue
        
        # Parse odds (decimal format)
        try:
            team1_moneyline_decimal = float(row['team1_moneyline']) if pd.notna(row['team1_moneyline']) else None
            team2_moneyline_decimal = float(row['team2_moneyline']) if pd.notna(row['team2_moneyline']) else None
            team1_spread = float(row['team1_spread']) if pd.notna(row['team1_spread']) else None
            team1_spread_odds_decimal = float(row['team1_spread_odds']) if pd.notna(row['team1_spread_odds']) else None
            team2_spread = float(row['team2_spread']) if pd.notna(row['team2_spread']) else None
            team2_spread_odds_decimal = float(row['team2_spread_odds']) if pd.notna(row['team2_spread_odds']) else None
            over_total = float(row['over_total']) if pd.notna(row['over_total']) else None
            over_total_odds_decimal = float(row['over_total_odds']) if pd.notna(row['over_total_odds']) else None
            under_total = float(row['under_total']) if pd.notna(row['under_total']) else None
            under_total_odds_decimal = float(row['under_total_odds']) if pd.notna(row['under_total_odds']) else None
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping row: invalid odds values: {e}")
            continue
        
        # Convert decimal odds to American (for storage)
        if team1_moneyline_decimal:
            team1_moneyline_american = decimal_to_american(team1_moneyline_decimal)
            team1_moneyline_implied_prob = calculate_implied_prob(team1_moneyline_decimal)
        else:
            team1_moneyline_american = None
            team1_moneyline_implied_prob = None
        
        if team2_moneyline_decimal:
            team2_moneyline_american = decimal_to_american(team2_moneyline_decimal)
            team2_moneyline_implied_prob = calculate_implied_prob(team2_moneyline_decimal)
        else:
            team2_moneyline_american = None
            team2_moneyline_implied_prob = None
        
        # Determine home/away (we'll need to match with ESPN games to know for sure)
        # For now, assume team1 is away and team2 is home (common convention)
        away_team_espn = team1_espn
        home_team_espn = team2_espn
        
        # Moneyline - Team1 (Away)
        if team1_moneyline_decimal:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',  # From Pinnacle based on game_link
                'market_type': 'moneyline',
                'side': 'away',
                'line_value': None,
                'odds_american': team1_moneyline_american,
                'odds_decimal': team1_moneyline_decimal,
                'implied_prob': team1_moneyline_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,  # Will be set later based on earliest timestamp
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
        
        # Moneyline - Team2 (Home)
        if team2_moneyline_decimal:
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',
                'market_type': 'moneyline',
                'side': 'home',
                'line_value': None,
                'odds_american': team2_moneyline_american,
                'odds_decimal': team2_moneyline_decimal,
                'implied_prob': team2_moneyline_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
        
        # Spread - Team1 (Away)
        if team1_spread is not None:
            spread_american = decimal_to_american(team1_spread_odds_decimal) if team1_spread_odds_decimal else None
            spread_implied_prob = calculate_implied_prob(team1_spread_odds_decimal) if team1_spread_odds_decimal else None
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',
                'market_type': 'spread',
                'side': 'away',
                'line_value': team1_spread,
                'odds_american': spread_american,
                'odds_decimal': team1_spread_odds_decimal,
                'implied_prob': spread_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
        
        # Spread - Team2 (Home)
        if team2_spread is not None:
            spread_american = decimal_to_american(team2_spread_odds_decimal) if team2_spread_odds_decimal else None
            spread_implied_prob = calculate_implied_prob(team2_spread_odds_decimal) if team2_spread_odds_decimal else None
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',
                'market_type': 'spread',
                'side': 'home',
                'line_value': team2_spread,
                'odds_american': spread_american,
                'odds_decimal': team2_spread_odds_decimal,
                'implied_prob': spread_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
        
        # Total - Over
        if over_total is not None:
            over_american = decimal_to_american(over_total_odds_decimal) if over_total_odds_decimal else None
            over_implied_prob = calculate_implied_prob(over_total_odds_decimal) if over_total_odds_decimal else None
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',
                'market_type': 'total',
                'side': 'over',
                'line_value': over_total,
                'odds_american': over_american,
                'odds_decimal': over_total_odds_decimal,
                'implied_prob': over_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
        
        # Total - Under
        if under_total is not None:
            under_american = decimal_to_american(under_total_odds_decimal) if under_total_odds_decimal else None
            under_implied_prob = calculate_implied_prob(under_total_odds_decimal) if under_total_odds_decimal else None
            records.append({
                'game_date': game_date,
                'away_team_espn': away_team_espn,
                'home_team_espn': home_team_espn,
                'bookmaker': 'pinnacle',
                'market_type': 'total',
                'side': 'under',
                'line_value': under_total,
                'odds_american': under_american,
                'odds_decimal': under_total_odds_decimal,
                'implied_prob': under_implied_prob,
                'snapshot_timestamp': snapshot_timestamp,
                'is_opening_line': False,
                'source_dataset': 'nba_main_lines',
                'raw_data': row.to_dict(),
            })
    
    result_df = pd.DataFrame(records)
    logger.info(f"Transformed {len(result_df)} records from {len(df)} rows")
    return result_df


def identify_opening_lines(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify opening lines by selecting earliest timestamp per game.
    
    For nba_main_lines.csv, multiple rows per game exist. Opening line is
    the earliest timestamp per (game_date, away_team_espn, home_team_espn, market_type, side).
    """
    logger.info("Identifying opening lines")
    
    # Group by game and market to find earliest timestamp
    df = df.copy()
    
    # For records with snapshot_timestamp, find earliest per game+market
    if 'snapshot_timestamp' in df.columns:
        # Create a key for grouping
        df['game_market_key'] = (
            df['game_date'].astype(str) + '_' +
            df['away_team_espn'] + '_' +
            df['home_team_espn'] + '_' +
            df['market_type'] + '_' +
            df['side'].astype(str)
        )
        
        # Find earliest timestamp per game+market
        earliest_timestamps = df.groupby('game_market_key')['snapshot_timestamp'].min()
        
        # Mark opening lines
        df['is_opening_line'] = df.apply(
            lambda row: (
                row['is_opening_line'] if pd.isna(row['snapshot_timestamp']) else
                (row['snapshot_timestamp'] == earliest_timestamps[row['game_market_key']])
            ),
            axis=1
        )
        
        # Drop temporary column
        df = df.drop(columns=['game_market_key'])
    else:
        # No timestamps, all are opening lines (nba_2008-2025 case)
        df['is_opening_line'] = True
    
    opening_count = df['is_opening_line'].sum()
    logger.info(f"Identified {opening_count} opening line records out of {len(df)} total")
    
    return df


def map_to_espn_game_ids_batch(
    conn: Any,
    games: list[tuple[Any, str, str]],
) -> dict[tuple[Any, str, str], str | None]:
    """
    Batch map games (date + teams) to ESPN game_ids.
    
    Design Pattern: Batch Processing
    Algorithm: Single SQL query with VALUES clause for all games
    Big O: O(n) where n = number of games (single query vs n queries)
    
    Uses fuzzy date matching (±1 day) to handle timezone differences.
    
    Returns: dict mapping (game_date, home_team, away_team) -> espn_game_id
    """
    if not games:
        return {}
    
    # Build VALUES clause for batch query using psycopg %s placeholders
    values_clauses = []
    params = []
    
    for game_date, home_team, away_team in games:
        # Each game needs 3 parameters: date, home_team, away_team
        values_clauses.append("(%s::date, %s, %s)")
        params.extend([game_date, home_team, away_team])
    
    sql = f"""
    WITH game_lookups AS (
        SELECT * FROM (VALUES {', '.join(values_clauses)}) AS t(game_date, home_team, away_team)
    )
    SELECT DISTINCT ON (gl.game_date, gl.home_team, gl.away_team)
        gl.game_date,
        gl.home_team,
        gl.away_team,
        sg.event_id
    FROM game_lookups gl
    LEFT JOIN LATERAL (
        SELECT event_id
        FROM espn.scoreboard_games
        WHERE DATE(event_date) BETWEEN gl.game_date - INTERVAL '1 day' AND gl.game_date + INTERVAL '1 day'
          AND (
            (home_team_abbrev = gl.home_team AND away_team_abbrev = gl.away_team)
            OR (home_team_abbrev = gl.away_team AND away_team_abbrev = gl.home_team)
          )
        ORDER BY ABS(EXTRACT(EPOCH FROM (event_date - gl.game_date)))
        LIMIT 1
    ) sg ON true
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            
            # Build result dict
            result = {}
            for game_date, home_team, away_team, event_id in rows:
                result[(game_date, home_team, away_team)] = event_id
            
            # Add None for games that didn't match
            for game_date, home_team, away_team in games:
                if (game_date, home_team, away_team) not in result:
                    result[(game_date, home_team, away_team)] = None
            
            return result
    except Exception as e:
        logger.error(f"Error in batch mapping games: {e}")
        # Fallback: return None for all games
        return {(game_date, home_team, away_team): None for game_date, home_team, away_team in games}


def insert_odds_records(conn: Any, df: pd.DataFrame, dry_run: bool = False) -> int:
    """
    Insert odds records into database.
    
    Returns number of records inserted.
    """
    if dry_run:
        logger.info(f"DRY RUN: Would insert {len(df)} records")
        return len(df)
    
    logger.info(f"Inserting {len(df)} records into database")
    
    sql = """
    INSERT INTO external.sportsbook_odds_snapshots (
        espn_game_id, bookmaker, market_type, side, line_value,
        odds_american, odds_decimal, implied_prob,
        snapshot_timestamp, is_opening_line, source_dataset, raw_data
    )
    VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s
    )
    ON CONFLICT (espn_game_id, bookmaker, market_type, side, snapshot_timestamp, source_dataset)
    DO UPDATE SET
        odds_american = EXCLUDED.odds_american,
        odds_decimal = EXCLUDED.odds_decimal,
        implied_prob = EXCLUDED.implied_prob,
        line_value = EXCLUDED.line_value,
        is_opening_line = EXCLUDED.is_opening_line,
        raw_data = EXCLUDED.raw_data
    """
    
    inserted_count = 0
    batch_size = 1000
    total_records = len(df)
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        batch_records = []
        
        for _, row in batch.iterrows():
            # Convert raw_data dict to JSON-serializable format, then to JSONB
            raw_data_serializable = make_json_serializable(row['raw_data']) if row['raw_data'] else None
            raw_data_json = Jsonb(raw_data_serializable) if raw_data_serializable else None
            
            batch_records.append((
                row.get('espn_game_id'),  # Will be set by ESPN mapping
                row['bookmaker'],
                row['market_type'],
                row['side'],
                row.get('line_value'),
                int(row['odds_american']) if pd.notna(row.get('odds_american')) else None,
                float(row['odds_decimal']) if pd.notna(row.get('odds_decimal')) else None,
                float(row['implied_prob']) if pd.notna(row.get('implied_prob')) else None,
                row.get('snapshot_timestamp'),
                bool(row['is_opening_line']),
                row['source_dataset'],
                raw_data_json,
            ))
        
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, batch_records)
            conn.commit()
            inserted_count += len(batch_records)
            progress_pct = (inserted_count / total_records * 100) if total_records > 0 else 0
            logger.info(f"Inserted batch {i//batch_size + 1}: {inserted_count}/{total_records} records ({progress_pct:.1f}%)")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
            raise
    
    logger.info(f"Successfully inserted {inserted_count} records")
    return inserted_count


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return 1
    
    # Load CSV
    df = load_csv_file(csv_path)
    
    # Apply limit if specified (for testing)
    if args.limit:
        df = df.head(args.limit)
        logger.info(f"Limited to {len(df)} rows for testing")
    
    # Transform based on source
    if args.source == "nba_2008_2025":
        transformed_df = transform_nba_2008_2025(df)
    elif args.source == "nba_main_lines":
        transformed_df = transform_nba_main_lines(df)
        # Identify opening lines (earliest timestamp per game)
        transformed_df = identify_opening_lines(transformed_df)
    else:
        logger.error(f"Unknown source: {args.source}")
        return 1
    
    if len(transformed_df) == 0:
        logger.warning("No records to insert after transformation")
        return 0
    
    # Map to ESPN games (batch processing for performance)
    logger.info("Mapping to ESPN games (batch processing)...")
    with psycopg.connect(dsn) as conn:
        # Get unique games (date + teams) to avoid duplicate queries
        # Group by game_date, home_team, away_team since multiple records per game (moneyline/spread/total)
        unique_games = transformed_df[['game_date', 'home_team_espn', 'away_team_espn']].drop_duplicates()
        unique_games_list = [
            (row['game_date'], row['home_team_espn'], row['away_team_espn'])
            for _, row in unique_games.iterrows()
        ]
        
        logger.info(f"Mapping {len(unique_games_list)} unique games to ESPN game_ids...")
        
        # Batch map all games at once
        game_id_map = map_to_espn_game_ids_batch(conn, unique_games_list)
        
        # Apply mapping to all records
        mapped_count = 0
        for idx, row in transformed_df.iterrows():
            key = (row['game_date'], row['home_team_espn'], row['away_team_espn'])
            espn_game_id = game_id_map.get(key)
            transformed_df.at[idx, 'espn_game_id'] = espn_game_id
            if espn_game_id:
                mapped_count += 1
        
        logger.info(f"Mapped {mapped_count} out of {len(transformed_df)} records to ESPN games ({mapped_count/len(transformed_df)*100:.1f}%)")
        
        # Insert into database
        inserted_count = insert_odds_records(conn, transformed_df, dry_run=args.dry_run)
        
        if not args.dry_run:
            logger.info(f"Successfully loaded {inserted_count} records into database")
        else:
            logger.info(f"DRY RUN: Would load {inserted_count} records")
    
    return 0


if __name__ == "__main__":
    exit(main())

