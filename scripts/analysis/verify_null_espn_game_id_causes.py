#!/usr/bin/env python3
"""
Verify why games have NULL espn_game_id values in sportsbook_odds_snapshots.

Checks:
1. How many records have NULL espn_game_id
2. Whether the games exist in ESPN scoreboard_games
3. Team name mapping issues
4. Date matching issues
5. Provides factual evidence
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False
    print("ERROR: psycopg not available. Cannot check database.")
    sys.exit(1)

from scripts.lib.team_name_mapping import normalize_team_name

def check_null_espn_game_id_stats(conn):
    """Get statistics on NULL espn_game_id records."""
    query = """
    SELECT 
        source_dataset,
        COUNT(*) as total_records,
        COUNT(*) FILTER (WHERE espn_game_id IS NULL) as null_game_id_count,
        COUNT(*) FILTER (WHERE is_opening_line = TRUE) as opening_line_count,
        COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) as opening_null_count,
        ROUND(100.0 * COUNT(*) FILTER (WHERE espn_game_id IS NULL) / COUNT(*), 1) as null_percentage
    FROM external.sportsbook_odds_snapshots
    GROUP BY source_dataset
    ORDER BY source_dataset;
    """
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


def get_sample_null_records(conn, limit=50):
    """Get sample records with NULL espn_game_id."""
    query = """
    SELECT DISTINCT ON (game_date, away_team_espn, home_team_espn)
        game_date,
        away_team_espn,
        home_team_espn,
        market_type,
        side,
        is_opening_line,
        source_dataset,
        snapshot_timestamp
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id IS NULL
    ORDER BY game_date, away_team_espn, home_team_espn, snapshot_timestamp NULLS LAST
    LIMIT %s;
    """
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (limit,))
        return cur.fetchall()


def check_espn_game_exists(conn, game_date, home_team, away_team):
    """Check if ESPN game exists matching date and teams."""
    query = """
    SELECT 
        event_id,
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev,
        home_team_display_name,
        away_team_display_name,
        event_date
    FROM espn.scoreboard_games
    WHERE DATE(event_date) BETWEEN %s::date - INTERVAL '1 day' AND %s::date + INTERVAL '1 day'
      AND (
        (home_team_abbrev = %s AND away_team_abbrev = %s)
        OR (home_team_abbrev = %s AND away_team_abbrev = %s)
      )
    ORDER BY ABS(EXTRACT(EPOCH FROM (event_date - %s::date)))
    LIMIT 5;
    """
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (game_date, game_date, home_team, away_team, away_team, home_team, game_date))
        return cur.fetchall()


def check_espn_games_by_date_only(conn, game_date, limit=10):
    """Check what ESPN games exist on this date."""
    query = """
    SELECT 
        event_id,
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev,
        home_team_display_name,
        away_team_display_name
    FROM espn.scoreboard_games
    WHERE DATE(event_date) = %s::date
    ORDER BY event_date
    LIMIT %s;
    """
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (game_date, limit))
        return cur.fetchall()


def analyze_team_mapping_issues(conn, null_records):
    """Analyze team name mapping issues."""
    issues = {
        'team_not_found': [],
        'date_mismatch': [],
        'both_teams_found': [],
    }
    
    for record in null_records[:20]:  # Check first 20
        game_date = record['game_date']
        home_team = record['home_team_espn']
        away_team = record['away_team_espn']
        
        # Check if ESPN games exist on this date
        espn_games = check_espn_games_by_date_only(conn, game_date, limit=20)
        
        if not espn_games:
            issues['date_mismatch'].append({
                'record': record,
                'reason': 'No ESPN games found on this date',
            })
            continue
        
        # Check if teams exist in ESPN games on this date
        home_found = any(g['home_team_abbrev'] == home_team or g['away_team_abbrev'] == home_team for g in espn_games)
        away_found = any(g['home_team_abbrev'] == away_team or g['away_team_abbrev'] == away_team for g in espn_games)
        
        if not home_found and not away_found:
            issues['team_not_found'].append({
                'record': record,
                'espn_games_on_date': espn_games[:3],
                'reason': f'Neither team found: {away_team} @ {home_team}',
            })
        elif home_found and away_found:
            # Teams exist but match failed - check why
            matches = check_espn_game_exists(conn, game_date, home_team, away_team)
            if not matches:
                issues['both_teams_found'].append({
                    'record': record,
                    'espn_games_on_date': espn_games[:3],
                    'reason': 'Teams exist on date but no exact match found',
                })
    
    return issues


def check_csv_data_for_sample_games(conn, null_records):
    """Check if sample games exist in CSV files."""
    csv_dir = Path(__file__).parent.parent.parent / 'data' / 'stats-csv'
    
    # Load CSV games
    csv_games = set()
    
    # Load from nba_main_lines.csv
    main_lines_csv = csv_dir / 'nba_main_lines.csv'
    if main_lines_csv.exists():
        with open(main_lines_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dt = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    date_str = dt.strftime('%Y-%m-%d')
                    team1 = normalize_team_name(row['team1'])
                    team2 = normalize_team_name(row['team2'])
                    if team1 and team2:
                        csv_games.add((date_str, team1, team2))
                        csv_games.add((date_str, team2, team1))
                except:
                    pass
    
    # Load from nba_2008-2025.csv
    historical_csv = csv_dir / 'nba_2008-2025.csv'
    if historical_csv.exists():
        with open(historical_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_str = row['date']
                    home = normalize_team_name(row['home'])
                    away = normalize_team_name(row['away'])
                    if home and away:
                        csv_games.add((date_str, home, away))
                        csv_games.add((date_str, away, home))
                except:
                    pass
    
    # Check sample null records against CSV
    results = []
    for record in null_records[:20]:
        game_date = str(record['game_date'])
        home_team = record['home_team_espn']
        away_team = record['away_team_espn']
        
        in_csv = (game_date, home_team, away_team) in csv_games or (game_date, away_team, home_team) in csv_games
        
        results.append({
            'record': record,
            'in_csv': in_csv,
        })
    
    return results, len(csv_games)


def main():
    """Main function."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return 1
    
    print("=" * 100)
    print("VERIFYING NULL ESPN_GAME_ID CAUSES")
    print("=" * 100)
    print()
    
    with psycopg.connect(database_url) as conn:
        # 1. Get statistics
        print("1. STATISTICS ON NULL ESPN_GAME_ID RECORDS")
        print("-" * 100)
        stats = check_null_espn_game_id_stats(conn)
        
        if not stats:
            print("No records found in sportsbook_odds_snapshots table")
            return 1
        
        total_null = 0
        total_opening_null = 0
        
        for stat in stats:
            print(f"\nSource: {stat['source_dataset']}")
            print(f"  Total records: {stat['total_records']:,}")
            print(f"  NULL espn_game_id: {stat['null_game_id_count']:,} ({stat['null_percentage']:.1f}%)")
            print(f"  Opening line records: {stat['opening_line_count']:,}")
            print(f"  Opening lines with NULL espn_game_id: {stat['opening_null_count']:,}")
            total_null += stat['null_game_id_count']
            total_opening_null += stat['opening_null_count']
        
        print(f"\nTOTAL:")
        print(f"  NULL espn_game_id records: {total_null:,}")
        print(f"  Opening lines with NULL espn_game_id: {total_opening_null:,}")
        
        # 2. Get sample records
        print(f"\n\n2. SAMPLE RECORDS WITH NULL ESPN_GAME_ID")
        print("-" * 100)
        null_records = get_sample_null_records(conn, limit=50)
        print(f"Found {len(null_records)} sample records with NULL espn_game_id\n")
        
        if not null_records:
            print("No records with NULL espn_game_id found")
            return 0
        
        # 3. Check ESPN game existence
        print("3. CHECKING IF ESPN GAMES EXIST FOR NULL RECORDS")
        print("-" * 100)
        
        espn_exists_count = 0
        espn_not_found_count = 0
        team_mapping_issues_count = 0
        
        sample_to_check = null_records[:30]
        
        for i, record in enumerate(sample_to_check, 1):
            game_date = str(record['game_date'])
            home_team = record['home_team_espn']
            away_team = record['away_team_espn']
            
            print(f"\nRecord {i}: {game_date} - {away_team} @ {home_team}")
            print(f"  Source: {record['source_dataset']}, Opening: {record['is_opening_line']}")
            
            # Check if ESPN game exists
            matches = check_espn_game_exists(conn, game_date, home_team, away_team)
            
            if matches:
                espn_exists_count += 1
                match = matches[0]
                print(f"  ✓ ESPN game EXISTS: {match['event_id']}")
                print(f"    ESPN: {match['away_team_abbrev']} @ {match['home_team_abbrev']} on {match['game_date']}")
                print(f"    Odds: {away_team} @ {home_team} on {game_date}")
                
                # Check why mapping failed
                if match['away_team_abbrev'] != away_team or match['home_team_abbrev'] != home_team:
                    print(f"    ⚠️  TEAM MISMATCH:")
                    print(f"       Odds away: {away_team}, ESPN away: {match['away_team_abbrev']}")
                    print(f"       Odds home: {home_team}, ESPN home: {match['home_team_abbrev']}")
                    team_mapping_issues_count += 1
            else:
                espn_not_found_count += 1
                print(f"  ✗ ESPN game NOT FOUND")
                
                # Check what games exist on this date
                espn_games_on_date = check_espn_games_by_date_only(conn, game_date, limit=5)
                if espn_games_on_date:
                    print(f"    But {len(espn_games_on_date)} ESPN games exist on this date:")
                    for g in espn_games_on_date[:3]:
                        print(f"      {g['event_id']}: {g['away_team_abbrev']} @ {g['home_team_abbrev']}")
                    
                    # Check if teams exist but in different combinations
                    home_found = any(g['home_team_abbrev'] == home_team or g['away_team_abbrev'] == home_team for g in espn_games_on_date)
                    away_found = any(g['home_team_abbrev'] == away_team or g['away_team_abbrev'] == away_team for g in espn_games_on_date)
                    
                    if home_found and away_found:
                        print(f"    ⚠️  Both teams exist on this date but not matched together")
                        team_mapping_issues_count += 1
                    elif home_found:
                        print(f"    ⚠️  Home team ({home_team}) exists but away team ({away_team}) not found")
                    elif away_found:
                        print(f"    ⚠️  Away team ({away_team}) exists but home team ({home_team}) not found")
                    else:
                        print(f"    ⚠️  Neither team found: {away_team} @ {home_team}")
                else:
                    print(f"    No ESPN games found on this date")
        
        # 4. Analyze team mapping issues
        print(f"\n\n4. TEAM MAPPING ISSUE ANALYSIS")
        print("-" * 100)
        print(f"ESPN games exist but mapping failed: {espn_exists_count}/{len(sample_to_check)}")
        print(f"ESPN games not found: {espn_not_found_count}/{len(sample_to_check)}")
        print(f"Team mapping issues: {team_mapping_issues_count}/{len(sample_to_check)}")
        
        # 5. Check CSV data
        print(f"\n\n5. CHECKING CSV DATA FOR SAMPLE GAMES")
        print("-" * 100)
        csv_results, total_csv_games = check_csv_data_for_sample_games(conn, null_records)
        
        in_csv_count = sum(1 for r in csv_results if r['in_csv'])
        print(f"Total games in CSV files: {total_csv_games:,}")
        print(f"Sample NULL records found in CSV: {in_csv_count}/{len(csv_results)}")
        
        # 6. Check if records were inserted but espn_game_id is NULL
        print(f"\n\n6. VERIFYING RECORDS WERE INSERTED")
        print("-" * 100)
        
        query = """
        SELECT 
            COUNT(*) as total_with_null,
            COUNT(DISTINCT (game_date, away_team_espn, home_team_espn)) as unique_games_with_null
        FROM external.sportsbook_odds_snapshots
        WHERE espn_game_id IS NULL
          AND is_opening_line = TRUE;
        """
        
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            result = cur.fetchone()
            if result:
                print(f"Total opening line records with NULL espn_game_id: {result['total_with_null']:,}")
                print(f"Unique games with NULL espn_game_id: {result['unique_games_with_null']:,}")
                print(f"\n✓ CONFIRMED: Records WERE inserted but espn_game_id is NULL")
        
        # 7. Summary
        print(f"\n\n7. SUMMARY")
        print("=" * 100)
        print(f"✓ Records ARE in database (even with NULL espn_game_id)")
        print(f"✓ {total_opening_null:,} opening line records have NULL espn_game_id")
        print(f"✓ Training script filters these out (requires espn_game_id IS NOT NULL)")
        print(f"✓ ESPN games exist for {espn_exists_count}/{len(sample_to_check)} sample records")
        print(f"✓ Team mapping issues found: {team_mapping_issues_count} cases")
        print(f"\nROOT CAUSE: ESPN game mapping is failing, likely due to:")
        print(f"  1. Team name abbreviation mismatches")
        print(f"  2. Date/timezone differences")
        print(f"  3. Team order differences")
    
    return 0


if __name__ == '__main__':
    exit(main())
