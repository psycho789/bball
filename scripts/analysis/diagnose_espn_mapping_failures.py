#!/usr/bin/env python3
"""
Diagnose why ESPN game mapping is failing for games that exist in CSV.

Checks:
1. Are games from CSV present in ESPN scoreboard_games table?
2. Are team name mappings correct?
3. Are date matches working?
"""

import csv
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False
    print("Warning: psycopg not available. Will only analyze CSV data.")

from scripts.lib.team_name_mapping import normalize_team_name

def parse_markdown_file(md_path: Path) -> List[Dict[str, str]]:
    """Parse the markdown file to extract game information."""
    games = []
    
    with open(md_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    in_table = False
    
    for line in lines:
        if '| Game ID |' in line or '|--------|' in line:
            in_table = True
            continue
        
        if not in_table:
            continue
        
        if line.startswith('|') and '|' in line[1:]:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                game_id = parts[1]
                season = parts[2]
                date_str = parts[3]
                matchup = parts[4]
                
                if not game_id or game_id == 'Game ID':
                    continue
                
                # Parse matchup
                away_team = None
                home_team = None
                if ' @ ' in matchup:
                    parts_matchup = matchup.split(' @ ')
                    if len(parts_matchup) == 2:
                        away_team = parts_matchup[0].strip()
                        home_team = parts_matchup[1].strip()
                
                games.append({
                    'game_id': game_id,
                    'season': season,
                    'date': date_str,
                    'matchup': matchup,
                    'away_team': away_team,
                    'home_team': home_team,
                })
    
    return games


def check_espn_game_exists(conn, game_id: str) -> Optional[Dict]:
    """Check if ESPN game exists in database."""
    if not HAS_PSYCOPG:
        return None
    
    query = """
    SELECT 
        event_id,
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev,
        home_team_display_name,
        away_team_display_name
    FROM espn.scoreboard_games
    WHERE event_id = %s
    LIMIT 1
    """
    
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (game_id,))
            result = cur.fetchone()
            return result
    except Exception as e:
        print(f"Error checking game {game_id}: {e}")
        return None


def check_espn_games_by_date_teams(conn, game_date: str, home_team: str, away_team: str) -> List[Dict]:
    """Check if ESPN games exist matching date and teams."""
    if not HAS_PSYCOPG:
        return []
    
    query = """
    SELECT 
        event_id,
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev,
        home_team_display_name,
        away_team_display_name
    FROM espn.scoreboard_games
    WHERE DATE(event_date) BETWEEN %s::date - INTERVAL '1 day' AND %s::date + INTERVAL '1 day'
      AND (
        (home_team_abbrev = %s AND away_team_abbrev = %s)
        OR (home_team_abbrev = %s AND away_team_abbrev = %s)
      )
    ORDER BY ABS(EXTRACT(EPOCH FROM (event_date - %s::date)))
    LIMIT 5
    """
    
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (game_date, game_date, home_team, away_team, away_team, home_team, game_date))
            results = cur.fetchall()
            return results
    except Exception as e:
        print(f"Error checking games by date/teams: {e}")
        return []


def check_odds_in_db(conn, espn_game_id: str) -> Dict:
    """Check if opening odds exist in database for this game."""
    if not HAS_PSYCOPG:
        return {'has_opening_odds': False, 'count': 0}
    
    query = """
    SELECT COUNT(*) as count
    FROM external.sportsbook_odds_snapshots
    WHERE espn_game_id = %s
      AND is_opening_line = TRUE
    """
    
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (espn_game_id,))
            result = cur.fetchone()
            count = result['count'] if result else 0
            return {'has_opening_odds': count > 0, 'count': count}
    except Exception as e:
        print(f"Error checking odds in DB: {e}")
        return {'has_opening_odds': False, 'count': 0}


def main():
    """Main function."""
    repo_root = Path(__file__).parent.parent.parent
    md_path = repo_root / 'cursor-files' / 'analysis' / '2026-01-22-games-missing-opening-odds' / 'games_missing_opening_odds.md'
    
    print("=" * 100)
    print("DIAGNOSING ESPN GAME MAPPING FAILURES")
    print("=" * 100)
    print()
    
    # Parse markdown file
    print("Parsing markdown file...")
    missing_games = parse_markdown_file(md_path)
    print(f"Found {len(missing_games)} games missing opening odds in DB\n")
    
    # Sample games to diagnose
    sample_games = missing_games[:20]  # Check first 20 games
    
    if not HAS_PSYCOPG:
        print("⚠️  psycopg not available. Cannot check database.")
        print("Sample games from markdown:")
        for game in sample_games[:5]:
            print(f"  {game['game_id']}: {game['date']} - {game['matchup']} ({game['season']})")
        return 0
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("⚠️  DATABASE_URL not set. Cannot check database.")
        return 0
    
    print("Checking ESPN game mapping for sample games...\n")
    
    with psycopg.connect(database_url) as conn:
        results = {
            'espn_game_exists': 0,
            'espn_game_not_found': 0,
            'has_opening_odds': 0,
            'missing_opening_odds': 0,
            'team_mapping_issues': [],
            'date_matching_issues': [],
        }
        
        for game in sample_games:
            game_id = game['game_id']
            game_date = game['date']
            away_team = game['away_team']
            home_team = game['home_team']
            
            # Check if ESPN game exists
            espn_game = check_espn_game_exists(conn, game_id)
            
            if espn_game:
                results['espn_game_exists'] += 1
                
                # Check if opening odds exist
                odds_check = check_odds_in_db(conn, game_id)
                if odds_check['has_opening_odds']:
                    results['has_opening_odds'] += 1
                    print(f"✓ {game_id}: ESPN game exists, opening odds exist ({odds_check['count']} records)")
                else:
                    results['missing_opening_odds'] += 1
                    print(f"⚠ {game_id}: ESPN game exists BUT no opening odds in DB")
                    print(f"    Date: {game_date}, Matchup: {game['matchup']}")
                    
                    # Check if there are ANY odds records (even non-opening)
                    query = """
                    SELECT COUNT(*) as count, 
                           COUNT(*) FILTER (WHERE is_opening_line = TRUE) as opening_count
                    FROM external.sportsbook_odds_snapshots
                    WHERE espn_game_id = %s
                    """
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(query, (game_id,))
                        result = cur.fetchone()
                        if result and result['count'] > 0:
                            print(f"    Has {result['count']} odds records, but {result['opening_count']} marked as opening")
            else:
                results['espn_game_not_found'] += 1
                
                # Try to find by date/teams
                if away_team and home_team:
                    # Normalize team names
                    away_espn = normalize_team_name(away_team)
                    home_espn = normalize_team_name(home_team)
                    
                    if away_espn and home_espn:
                        matches = check_espn_games_by_date_teams(conn, game_date, home_espn, away_espn)
                        if matches:
                            print(f"✗ {game_id}: Not found, but found {len(matches)} matches by date/teams:")
                            for match in matches[:2]:
                                print(f"    {match['event_id']}: {match['away_team_abbrev']} @ {match['home_team_abbrev']} on {match['game_date']}")
                        else:
                            print(f"✗ {game_id}: Not found in ESPN games")
                            print(f"    Date: {game_date}, Teams: {away_team} @ {home_team}")
                            print(f"    Normalized: {away_espn} @ {home_espn}")
                    else:
                        print(f"✗ {game_id}: Team normalization failed")
                        print(f"    Away: {away_team} -> {away_espn}, Home: {home_team} -> {home_espn}")
                else:
                    print(f"✗ {game_id}: Cannot parse matchup: {game['matchup']}")
            
            print()
    
    # Summary
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"ESPN games found: {results['espn_game_exists']}/{len(sample_games)}")
    print(f"ESPN games NOT found: {results['espn_game_not_found']}/{len(sample_games)}")
    print(f"Games with opening odds: {results['has_opening_odds']}/{len(sample_games)}")
    print(f"Games missing opening odds: {results['missing_opening_odds']}/{len(sample_games)}")
    print()
    
    # Check if odds exist but espn_game_id is NULL
    print("Checking for odds records with NULL espn_game_id...")
    if HAS_PSYCOPG and database_url:
        with psycopg.connect(database_url) as conn:
            query = """
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE is_opening_line = TRUE) as opening_count,
                   COUNT(*) FILTER (WHERE espn_game_id IS NULL) as null_game_id_count,
                   COUNT(*) FILTER (WHERE is_opening_line = TRUE AND espn_game_id IS NULL) as opening_null_count
            FROM external.sportsbook_odds_snapshots
            """
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                result = cur.fetchone()
                if result:
                    print(f"  Total odds records: {result['total']:,}")
                    print(f"  Opening line records: {result['opening_count']:,}")
                    print(f"  Records with NULL espn_game_id: {result['null_game_id_count']:,}")
                    print(f"  Opening lines with NULL espn_game_id: {result['opening_null_count']:,}")
                    if result['opening_null_count'] > 0:
                        print(f"\n  ⚠️  PROBLEM: {result['opening_null_count']:,} opening odds records have NULL espn_game_id")
                        print(f"     These won't be found by the training script which requires espn_game_id IS NOT NULL")
    
    return 0


if __name__ == '__main__':
    exit(main())
