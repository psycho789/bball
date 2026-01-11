#!/usr/bin/env python3
"""
Inspect ESPN probabilities_raw_items JSONB for odds fields.

This script queries the database to check if ESPN raw JSONB contains
odds-related fields (moneyline, spread, total, etc.).
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect


def inspect_jsonb_keys(conn, limit: int = 100):
    """Inspect all keys in raw_item JSONB column."""
    print("=" * 80)
    print("INSPECTING JSONB KEYS")
    print("=" * 80)
    
    query = """
    SELECT 
        event_id,
        jsonb_object_keys(raw_item) as key_name
    FROM espn.probabilities_raw_items
    LIMIT %s;
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        
        # Count unique keys
        unique_keys = set()
        for row in rows:
            unique_keys.add(row[1])
        
        print(f"\nFound {len(unique_keys)} unique keys in {len(rows)} rows:")
        print("\nAll keys:")
        for key in sorted(unique_keys):
            print(f"  - {key}")
        
        return unique_keys


def search_odds_related_keys(conn):
    """Search for odds-related keys using pattern matching."""
    print("\n" + "=" * 80)
    print("SEARCHING FOR ODDS-RELATED KEYS")
    print("=" * 80)
    
    # Get all unique keys first
    query = """
    SELECT DISTINCT jsonb_object_keys(raw_item) as key_name
    FROM espn.probabilities_raw_items;
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        all_keys = [row[0] for row in cur.fetchall()]
        
        # Search for odds-related patterns
        odds_patterns = [
            'odd', 'moneyline', 'line', 'spread', 'overUnder', 
            'sportsbook', 'bookmaker', 'bet', 'odds', 'american',
            'decimal', 'fractional', 'implied'
        ]
        
        matching_keys = []
        for key in all_keys:
            key_lower = key.lower()
            for pattern in odds_patterns:
                if pattern.lower() in key_lower:
                    matching_keys.append(key)
                    break
        
        if matching_keys:
            print(f"\nFound {len(matching_keys)} odds-related keys:")
            for key in sorted(matching_keys):
                print(f"  ✓ {key}")
        else:
            print("\n✗ No odds-related keys found")
        
        return matching_keys


def sample_raw_items(conn, limit: int = 5):
    """Sample raw_item JSONB to see structure."""
    print("\n" + "=" * 80)
    print("SAMPLE RAW ITEMS (First 5 rows)")
    print("=" * 80)
    
    query = """
    SELECT 
        event_id,
        last_modified_utc,
        raw_item
    FROM espn.probabilities_raw_items
    ORDER BY last_modified_utc DESC
    LIMIT %s;
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        
        for i, (event_id, last_modified, raw_item) in enumerate(rows, 1):
            print(f"\n--- Sample {i} ---")
            print(f"Event ID: {event_id}")
            print(f"Last Modified: {last_modified}")
            print(f"Keys in raw_item: {list(raw_item.keys())}")
            print(f"\nFull JSONB (pretty-printed):")
            print(json.dumps(raw_item, indent=2, default=str))
            print()


def check_scoreboard_schema(conn):
    """Check espn.scoreboard_games schema for odds fields."""
    print("\n" + "=" * 80)
    print("CHECKING SCOREBOARD_GAMES SCHEMA")
    print("=" * 80)
    
    query = """
    SELECT 
        column_name,
        data_type,
        is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'espn'
      AND table_name = 'scoreboard_games'
    ORDER BY ordinal_position;
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        
        print("\nColumns in espn.scoreboard_games:")
        odds_columns = []
        for col_name, data_type, is_nullable in rows:
            print(f"  - {col_name:30} {data_type:20} nullable={is_nullable}")
            if any(term in col_name.lower() for term in ['odd', 'moneyline', 'line', 'spread', 'total']):
                odds_columns.append(col_name)
        
        if odds_columns:
            print(f"\n✓ Found {len(odds_columns)} potential odds columns:")
            for col in odds_columns:
                print(f"  - {col}")
        else:
            print("\n✗ No odds-related columns found in scoreboard_games")
        
        return odds_columns


def main():
    """Run all inspections."""
    print("\n" + "=" * 80)
    print("ESPN ODDS INSPECTION")
    print("=" * 80)
    print("Purpose: Check if ESPN API provides odds data in raw JSONB")
    print("Table: espn.probabilities_raw_items")
    print()
    
    try:
        dsn = get_dsn(None)
        print(f"Connecting to database...")
        
        with connect(dsn) as conn:
            # Inspection 1: All JSONB keys
            unique_keys = inspect_jsonb_keys(conn, limit=100)
            
            # Inspection 2: Search for odds-related keys
            odds_keys = search_odds_related_keys(conn)
            
            # Inspection 3: Sample raw items
            sample_raw_items(conn, limit=5)
            
            # Inspection 4: Check scoreboard schema
            scoreboard_odds = check_scoreboard_schema(conn)
            
            # Summary
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print(f"Total unique keys in raw_item: {len(unique_keys)}")
            print(f"Odds-related keys found: {len(odds_keys)}")
            if odds_keys:
                print(f"  Keys: {', '.join(odds_keys)}")
            print(f"Scoreboard odds columns: {len(scoreboard_odds)}")
            if scoreboard_odds:
                print(f"  Columns: {', '.join(scoreboard_odds)}")
            
            if not odds_keys and not scoreboard_odds:
                print("\n✗ CONCLUSION: No odds data found in ESPN API")
            else:
                print("\n✓ CONCLUSION: Odds data may be present - review samples above")
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

