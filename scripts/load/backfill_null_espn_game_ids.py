#!/usr/bin/env python3
"""
Backfill NULL espn_game_id values for existing records.

This script:
1. Finds records with NULL espn_game_id and is_opening_line = TRUE
2. Extracts team names from raw_data JSONB
3. Re-normalizes team names with fixed team_name_mapping
4. Re-attempts ESPN game mapping
5. Updates espn_game_id where matches found
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import argparse
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.lib._db_lib import get_dsn, connect
from scripts.lib.team_name_mapping import normalize_team_name
from scripts.load.load_sportsbook_odds import map_to_espn_game_ids_batch


def get_null_records(conn: Any, limit: int = None) -> list[dict]:
    """Get records with NULL espn_game_id."""
    query = """
    SELECT DISTINCT ON (DATE(snapshot_timestamp), raw_data->>'team1', raw_data->>'team2', raw_data->>'away', raw_data->>'home')
        snapshot_id,
        DATE(snapshot_timestamp) as game_date,
        raw_data->>'team1' as team1_raw,
        raw_data->>'team2' as team2_raw,
        raw_data->>'away' as away_raw,
        raw_data->>'home' as home_raw,
        source_dataset
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id IS NULL
      AND is_opening_line = TRUE
      AND snapshot_timestamp IS NOT NULL
      AND raw_data IS NOT NULL
    ORDER BY DATE(snapshot_timestamp), raw_data->>'team1', raw_data->>'team2', raw_data->>'away', raw_data->>'home', snapshot_id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


def normalize_teams_from_raw_data(record: dict) -> tuple[str, str] | None:
    """Extract and normalize team names from raw_data."""
    # Try team1/team2 first (nba_main_lines format)
    team1 = record.get('team1_raw')
    team2 = record.get('team2_raw')
    
    if team1 and team2:
        team1_norm = normalize_team_name(team1)
        team2_norm = normalize_team_name(team2)
        if team1_norm and team2_norm:
            # Determine home/away based on source or assume team1=away, team2=home
            # For now, try both orderings in mapping
            return (team1_norm, team2_norm)
    
    # Try away/home format (nba_2008_2025 format)
    away = record.get('away_raw')
    home = record.get('home_raw')
    
    if away and home:
        away_norm = normalize_team_name(away)
        home_norm = normalize_team_name(home)
        if away_norm and home_norm:
            return (away_norm, home_norm)
    
    return None


def backfill_espn_game_ids(conn: Any, dry_run: bool = False, limit: int = None) -> dict:
    """Backfill NULL espn_game_id values."""
    print("=" * 100)
    print("BACKFILLING NULL ESPN_GAME_ID VALUES")
    print("=" * 100)
    print()
    
    # Get NULL records
    print(f"Fetching NULL records...")
    null_records = get_null_records(conn, limit=limit)
    print(f"Found {len(null_records)} unique games with NULL espn_game_id")
    print()
    
    if not null_records:
        print("No NULL records found. Nothing to backfill.")
        return {'processed': 0, 'mapped': 0, 'failed': 0}
    
    # Normalize teams and prepare for mapping
    games_to_map = []
    record_map = {}  # Map (date, home, away) -> list of snapshot_ids
    
    print("Normalizing team names...")
    normalized_count = 0
    failed_normalization = 0
    
    for record in null_records:
        teams = normalize_teams_from_raw_data(record)
        if teams:
            away_norm, home_norm = teams
            game_date = record['game_date']
            key = (game_date, home_norm, away_norm)
            
            if key not in games_to_map:
                games_to_map.append(key)
            
            if key not in record_map:
                record_map[key] = []
            record_map[key].append(record['snapshot_id'])
            
            normalized_count += 1
        else:
            failed_normalization += 1
    
    print(f"  Normalized: {normalized_count} games")
    print(f"  Failed normalization: {failed_normalization} games")
    print()
    
    if not games_to_map:
        print("No games could be normalized. Nothing to map.")
        return {'processed': len(null_records), 'mapped': 0, 'failed': len(null_records)}
    
    # Map to ESPN games
    print(f"Mapping {len(games_to_map)} unique games to ESPN game_ids...")
    game_id_map = map_to_espn_game_ids_batch(conn, games_to_map)
    
    mapped_count = 0
    unmapped_count = 0
    
    # Count how many records will be updated
    for key, espn_game_id in game_id_map.items():
        if espn_game_id:
            mapped_count += len(record_map.get(key, []))
        else:
            unmapped_count += len(record_map.get(key, []))
    
    print(f"  Mapped: {mapped_count} records")
    print(f"  Unmapped: {unmapped_count} records")
    print()
    
    if dry_run:
        print("DRY RUN - No updates performed")
        return {'processed': len(null_records), 'mapped': mapped_count, 'failed': unmapped_count}
    
    # Update records
    print("Updating records...")
    updated_count = 0
    
    for key, espn_game_id in game_id_map.items():
        if espn_game_id and key in record_map:
            snapshot_ids = record_map[key]
            
            # Update all records for this game
            update_query = """
            UPDATE external.sportsbook_odds_snapshots
            SET espn_game_id = %s
            WHERE snapshot_id = ANY(%s)
              AND espn_game_id IS NULL
            """
            
            with conn.cursor() as cur:
                cur.execute(update_query, (espn_game_id, snapshot_ids))
                updated_count += cur.rowcount
    
    conn.commit()
    
    print(f"Updated {updated_count} records")
    print()
    
    return {
        'processed': len(null_records),
        'mapped': mapped_count,
        'updated': updated_count,
        'failed': unmapped_count
    }


def main():
    parser = argparse.ArgumentParser(description='Backfill NULL espn_game_id values')
    parser.add_argument('--dsn', type=str, help='Database connection string')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no updates)')
    parser.add_argument('--limit', type=int, help='Limit number of records to process (for testing)')
    
    args = parser.parse_args()
    
    dsn = get_dsn(args.dsn)
    
    with connect(dsn) as conn:
        results = backfill_espn_game_ids(conn, dry_run=args.dry_run, limit=args.limit)
        
        print("=" * 100)
        print("SUMMARY")
        print("=" * 100)
        print(f"Processed: {results['processed']} unique games")
        print(f"Mapped: {results['mapped']} records")
        if 'updated' in results:
            print(f"Updated: {results['updated']} records")
        print(f"Failed: {results['failed']} records")
        print()
        
        if not args.dry_run:
            print("✓ Backfill complete!")
        else:
            print("ℹ Dry run complete - no changes made")


if __name__ == '__main__':
    main()
