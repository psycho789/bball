#!/usr/bin/env python3
"""
Check if games marked as missing opening odds actually have odds data in CSV files.

This script:
1. Parses the games_missing_opening_odds.md file to extract game IDs
2. Queries the database to get team names and dates for those games
3. Checks CSV files for matching team names and dates
4. Reports any discrepancies (games with odds in CSV but missing in database)
"""

import re
import csv
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

# Try to import psycopg, but make it optional
try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False
    print("Warning: psycopg not available. Will use matchup info from markdown file only.")

# Team name mapping from abbreviations to full names (for CSV matching)
TEAM_ABBREV_TO_FULL_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GS": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NO": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "NY": "New York Knicks",  # Alternative
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SA": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTAH": "Utah Jazz",
    "WAS": "Washington Wizards",
    "WSH": "Washington Wizards",  # Alternative
}

# Reverse mapping: full name -> abbreviation (for CSV lookup)
FULL_NAME_TO_ABBREV = {v: k for k, v in TEAM_ABBREV_TO_FULL_NAME.items()}


def parse_markdown_file(md_path: Path) -> List[Dict[str, str]]:
    """Parse the markdown file to extract game information."""
    games = []
    
    with open(md_path, 'r') as f:
        content = f.read()
    
    # Find the table section
    # Table format: | Game ID | Season | Date | Matchup | ...
    lines = content.split('\n')
    
    in_table = False
    for line in lines:
        # Skip header rows
        if '| Game ID |' in line or '|--------|' in line:
            in_table = True
            continue
        
        if not in_table:
            continue
        
        # Parse table rows
        if line.startswith('|') and '|' in line[1:]:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                game_id = parts[1]
                season = parts[2]
                date_str = parts[3]
                matchup = parts[4]
                
                # Skip empty rows
                if not game_id or game_id == 'Game ID':
                    continue
                
                # Parse matchup to extract team abbreviations
                # Format: "AWAY @ HOME" or "HOME vs AWAY"
                away_team = None
                home_team = None
                
                if ' @ ' in matchup:
                    parts_matchup = matchup.split(' @ ')
                    if len(parts_matchup) == 2:
                        away_team = parts_matchup[0].strip()
                        home_team = parts_matchup[1].strip()
                elif ' vs ' in matchup:
                    parts_matchup = matchup.split(' vs ')
                    if len(parts_matchup) == 2:
                        # First team is typically home in "vs" format
                        home_team = parts_matchup[0].strip()
                        away_team = parts_matchup[1].strip()
                
                games.append({
                    'game_id': game_id,
                    'season': season,
                    'date': date_str,
                    'matchup': matchup,
                    'away_team': away_team,
                    'home_team': home_team,
                })
    
    return games


def get_game_info_from_db(conn, game_ids: List[str]) -> Dict[str, Dict]:
    """Query database to get team names and dates for game IDs."""
    if not HAS_PSYCOPG or not game_ids:
        return {}
    
    # Build query with game IDs
    placeholders = ','.join(['%s'] * len(game_ids))
    
    query = f"""
    SELECT 
        event_id as game_id,
        DATE(event_date) as game_date,
        home_team_abbrev,
        away_team_abbrev,
        home_team_display_name,
        away_team_display_name
    FROM espn.scoreboard_games
    WHERE event_id IN ({placeholders})
    """
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, game_ids)
        results = cur.fetchall()
    
    # Convert to dictionary keyed by game_id
    game_info = {}
    for row in results:
        game_info[row['game_id']] = {
            'game_date': row['game_date'],
            'home_abbrev': row['home_team_abbrev'],
            'away_abbrev': row['away_team_abbrev'],
            'home_name': row['home_team_display_name'],
            'away_name': row['away_team_display_name'],
        }
    
    return game_info


def load_csv_odds(csv_path: Path) -> Set[Tuple[str, str, str]]:
    """
    Load odds data from CSV file.
    
    Returns: Set of (date, team1_abbrev, team2_abbrev) tuples where team names are normalized to ESPN abbreviations.
    """
    odds_games = set()
    
    if not csv_path.exists():
        return odds_games
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # nba_main_lines.csv has: team1, team2, timestamp
            if 'team1' in row and 'team2' in row and 'timestamp' in row:
                team1 = row['team1'].strip()
                team2 = row['team2'].strip()
                timestamp_str = row['timestamp'].strip()
                
                try:
                    # Parse timestamp to get date
                    dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    game_date = dt.strftime('%Y-%m-%d')
                    
                    # Normalize team names from CSV (full names) to ESPN abbreviations
                    team1_abbrev = normalize_team_name_for_csv(team1)
                    team2_abbrev = normalize_team_name_for_csv(team2)
                    
                    if team1_abbrev and team2_abbrev:
                        # Store both orderings (team1/team2 and team2/team1)
                        # This handles cases where CSV might have teams in different order
                        odds_games.add((game_date, team1_abbrev, team2_abbrev))
                        odds_games.add((game_date, team2_abbrev, team1_abbrev))
                except ValueError as e:
                    # Skip invalid dates
                    continue
    
    return odds_games


def normalize_team_name_for_csv(team_name: str) -> Optional[str]:
    """Normalize team name from CSV to ESPN abbreviation."""
    if not team_name:
        return None
    
    team_name = team_name.strip()
    
    # Check if it's already a full name in our mapping
    if team_name in FULL_NAME_TO_ABBREV:
        return FULL_NAME_TO_ABBREV[team_name]
    
    # Try direct lookup in reverse mapping (case-insensitive)
    team_lower = team_name.lower()
    for full_name, abbrev in FULL_NAME_TO_ABBREV.items():
        if team_lower == full_name.lower():
            return abbrev
    
    # Try partial matching (e.g., "Lakers" -> "LAL", "Golden State" -> "GS")
    for full_name, abbrev in FULL_NAME_TO_ABBREV.items():
        full_lower = full_name.lower()
        # Check if team name is contained in full name or vice versa
        if team_lower in full_lower or full_lower in team_lower:
            # Make sure it's a reasonable match (at least 3 characters)
            if len(team_lower) >= 3:
                return abbrev
    
    # Try matching just the city or team name part
    # Split on spaces and try matching individual words
    words = team_lower.split()
    for word in words:
        for full_name, abbrev in FULL_NAME_TO_ABBREV.items():
            if word in full_name.lower().split():
                return abbrev
    
    return None


def check_games_in_csvs(
    games: List[Dict],
    game_info: Dict[str, Dict],
    csv_dir: Path
) -> List[Dict]:
    """Check which games from the markdown file have odds data in CSV files."""
    discrepancies = []
    
    # Load odds data from CSV files
    main_lines_csv = csv_dir / 'nba_main_lines.csv'
    csv_odds = load_csv_odds(main_lines_csv)
    
    print(f"Loaded {len(csv_odds)} unique game-date-team combinations from CSV")
    
    # Check each game
    for game in games:
        game_id = game['game_id']
        game_date = game['date']
        
        # Get team info - prefer database if available, otherwise use markdown
        if game_id in game_info:
            info = game_info[game_id]
            home_abbrev = info['home_abbrev']
            away_abbrev = info['away_abbrev']
            home_name = info['home_name']
            away_name = info['away_name']
        else:
            # Use matchup from markdown file
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            
            if not home_team or not away_team:
                # Can't check without team info
                continue
            
            # Map abbreviations to full names for CSV lookup
            home_abbrev = home_team
            away_abbrev = away_team
            
            # Try to get full names from mapping
            home_name = TEAM_ABBREV_TO_FULL_NAME.get(home_abbrev, home_abbrev)
            away_name = TEAM_ABBREV_TO_FULL_NAME.get(away_abbrev, away_abbrev)
        
        # Check if this game exists in CSV
        found_in_csv = False
        
        # Check both team orderings
        if (game_date, home_abbrev, away_abbrev) in csv_odds:
            found_in_csv = True
        elif (game_date, away_abbrev, home_abbrev) in csv_odds:
            found_in_csv = True
        
        if found_in_csv:
            discrepancies.append({
                'game_id': game_id,
                'date': game_date,
                'matchup': game['matchup'],
                'season': game['season'],
                'home_team': home_name,
                'away_team': away_name,
            })
    
    return discrepancies


def main():
    """Main function."""
    import sys
    
    # Get paths
    repo_root = Path(__file__).parent.parent.parent
    md_path = repo_root / 'cursor-files' / 'analysis' / '2026-01-22-games-missing-opening-odds' / 'games_missing_opening_odds.md'
    csv_dir = repo_root / 'data' / 'stats-csv'
    
    print("Parsing markdown file...")
    games = parse_markdown_file(md_path)
    print(f"Found {len(games)} games in markdown file")
    
    # Try to get game info from database if available
    game_info = {}
    if HAS_PSYCOPG:
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # Extract game IDs
            game_ids = [g['game_id'] for g in games]
            print(f"Extracting info for {len(game_ids)} game IDs from database...")
            
            try:
                # Query database
                with psycopg.connect(database_url) as conn:
                    game_info = get_game_info_from_db(conn, game_ids)
                    print(f"Found info for {len(game_info)} games in database")
            except Exception as e:
                print(f"Warning: Could not query database: {e}")
                print("Will use matchup info from markdown file instead")
        else:
            print("DATABASE_URL not set, using matchup info from markdown file")
    else:
        print("psycopg not available, using matchup info from markdown file")
    
    # Check CSV files
    print("Checking CSV files for odds data...")
    discrepancies = check_games_in_csvs(games, game_info, csv_dir)
    
    # Report results
    print(f"\n{'='*80}")
    print(f"RESULTS: Found {len(discrepancies)} games with odds in CSV but missing in database")
    print(f"{'='*80}\n")
    
    if discrepancies:
        print("Games with odds data in CSV but missing opening odds in database:\n")
        for disc in discrepancies[:50]:  # Show first 50
            print(f"  Game ID: {disc['game_id']}")
            print(f"    Date: {disc['date']}")
            print(f"    Matchup: {disc['matchup']}")
            print(f"    Season: {disc['season']}")
            print(f"    Teams: {disc['away_team']} @ {disc['home_team']}")
            print()
        
        if len(discrepancies) > 50:
            print(f"  ... and {len(discrepancies) - 50} more games\n")
        
        # Summary by season
        print("\nSummary by season:")
        season_counts = {}
        for disc in discrepancies:
            season = disc['season']
            season_counts[season] = season_counts.get(season, 0) + 1
        
        for season in sorted(season_counts.keys()):
            print(f"  {season}: {season_counts[season]} games")
    else:
        print("No discrepancies found. All games marked as missing opening odds are also missing in CSV files.")
    
    return 0


if __name__ == '__main__':
    exit(main())
