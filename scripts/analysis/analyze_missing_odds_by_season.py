#!/usr/bin/env python3
"""
Analyze missing opening odds by season:
1. Percentage of games missing in DB but HAVE data in CSV (per season)
2. Percentage of games missing in BOTH DB and CSV (per season)
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple

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


def load_csv_games(csv_path: Path) -> Set[Tuple[str, str, str]]:
    """
    Load games from CSV file.
    Returns: Set of (date, team1_abbrev, team2_abbrev) tuples
    """
    games = set()
    
    if not csv_path.exists():
        return games
    
    # Team name to abbreviation mapping
    TEAM_NAME_TO_ABBREV = {
        "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
        "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
        "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
        "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
        "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NO",
        "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
        "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
        "Sacramento Kings": "SAC", "San Antonio Spurs": "SA", "Toronto Raptors": "TOR",
        "Utah Jazz": "UTAH", "Washington Wizards": "WAS",
    }
    
    # Abbreviation variations
    ABBREV_MAP = {
        "NY": "NYK", "WSH": "WAS", "UTAH": "UTAH", "UTA": "UTAH",
    }
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # nba_main_lines.csv
            if 'team1' in row and 'team2' in row and 'timestamp' in row:
                team1 = row['team1'].strip()
                team2 = row['team2'].strip()
                timestamp_str = row['timestamp'].strip()
                
                try:
                    dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    date_str = dt.strftime('%Y-%m-%d')
                    
                    # Convert team names to abbreviations
                    team1_abbrev = TEAM_NAME_TO_ABBREV.get(team1, team1)
                    team2_abbrev = TEAM_NAME_TO_ABBREV.get(team2, team2)
                    
                    # Normalize abbreviations
                    team1_abbrev = ABBREV_MAP.get(team1_abbrev, team1_abbrev)
                    team2_abbrev = ABBREV_MAP.get(team2_abbrev, team2_abbrev)
                    
                    if team1_abbrev and team2_abbrev:
                        # Store both orderings
                        games.add((date_str, team1_abbrev, team2_abbrev))
                        games.add((date_str, team2_abbrev, team1_abbrev))
                except:
                    pass
            
            # nba_2008-2025.csv
            elif 'home' in row and 'away' in row and 'date' in row:
                home = row['home'].strip()
                away = row['away'].strip()
                date_str = row['date'].strip()
                
                # Normalize abbreviations
                home_abbrev = ABBREV_MAP.get(home.upper(), home.upper())
                away_abbrev = ABBREV_MAP.get(away.upper(), away.upper())
                
                if home_abbrev and away_abbrev:
                    games.add((date_str, home_abbrev, away_abbrev))
                    games.add((date_str, away_abbrev, home_abbrev))
    
    return games


def normalize_team_abbrev(abbrev: str) -> str:
    """Normalize team abbreviation."""
    ABBREV_MAP = {
        "NY": "NYK", "WSH": "WAS", "UTAH": "UTAH", "UTA": "UTAH",
    }
    abbrev_upper = abbrev.upper()
    return ABBREV_MAP.get(abbrev_upper, abbrev_upper)


def main():
    """Main function."""
    repo_root = Path(__file__).parent.parent.parent
    md_path = repo_root / 'cursor-files' / 'analysis' / '2026-01-22-games-missing-opening-odds' / 'games_missing_opening_odds.md'
    csv_dir = repo_root / 'data' / 'stats-csv'
    
    # Parse markdown file
    print("Parsing markdown file...")
    missing_games = parse_markdown_file(md_path)
    print(f"Found {len(missing_games)} games missing opening odds in DB\n")
    
    # Load CSV games
    print("Loading games from CSV files...")
    csv_games_main = load_csv_games(csv_dir / 'nba_main_lines.csv')
    csv_games_historical = load_csv_games(csv_dir / 'nba_2008-2025.csv')
    csv_games_all = csv_games_main | csv_games_historical
    print(f"Found {len(csv_games_main)} games in nba_main_lines.csv")
    print(f"Found {len(csv_games_historical)} games in nba_2008-2025.csv")
    print(f"Total unique games in CSV: {len(csv_games_all)}\n")
    
    # Analyze by season
    season_stats = defaultdict(lambda: {
        'total_missing': 0,
        'missing_but_in_csv': 0,
        'missing_and_not_in_csv': 0,
    })
    
    for game in missing_games:
        season = game['season']
        date_str = game['date']
        away_team = normalize_team_abbrev(game['away_team'] or '')
        home_team = normalize_team_abbrev(game['home_team'] or '')
        
        season_stats[season]['total_missing'] += 1
        
        # Check if game exists in CSV
        found_in_csv = False
        if away_team and home_team:
            # Check both orderings
            if (date_str, away_team, home_team) in csv_games_all:
                found_in_csv = True
            elif (date_str, home_team, away_team) in csv_games_all:
                found_in_csv = True
        
        if found_in_csv:
            season_stats[season]['missing_but_in_csv'] += 1
        else:
            season_stats[season]['missing_and_not_in_csv'] += 1
    
    # Print results
    print("=" * 100)
    print("MISSING OPENING ODDS ANALYSIS BY SEASON")
    print("=" * 100)
    print()
    print(f"{'Season':<15} {'Total Missing':<15} {'In CSV':<15} {'% In CSV':<12} {'Not in CSV':<15} {'% Not in CSV':<15}")
    print("-" * 100)
    
    total_missing = 0
    total_in_csv = 0
    total_not_in_csv = 0
    
    for season in sorted(season_stats.keys()):
        stats = season_stats[season]
        total = stats['total_missing']
        in_csv = stats['missing_but_in_csv']
        not_in_csv = stats['missing_and_not_in_csv']
        
        pct_in_csv = (in_csv / total * 100) if total > 0 else 0
        pct_not_in_csv = (not_in_csv / total * 100) if total > 0 else 0
        
        print(f"{season:<15} {total:<15} {in_csv:<15} {pct_in_csv:>10.1f}% {not_in_csv:<15} {pct_not_in_csv:>10.1f}%")
        
        total_missing += total
        total_in_csv += in_csv
        total_not_in_csv += not_in_csv
    
    print("-" * 100)
    overall_pct_in_csv = (total_in_csv / total_missing * 100) if total_missing > 0 else 0
    overall_pct_not_in_csv = (total_not_in_csv / total_missing * 100) if total_missing > 0 else 0
    print(f"{'TOTAL':<15} {total_missing:<15} {total_in_csv:<15} {overall_pct_in_csv:>10.1f}% {total_not_in_csv:<15} {overall_pct_not_in_csv:>10.1f}%")
    print()
    
    # Detailed breakdown
    print("=" * 100)
    print("DETAILED BREAKDOWN BY SEASON")
    print("=" * 100)
    print()
    
    for season in sorted(season_stats.keys()):
        stats = season_stats[season]
        total = stats['total_missing']
        in_csv = stats['missing_but_in_csv']
        not_in_csv = stats['missing_and_not_in_csv']
        
        pct_in_csv = (in_csv / total * 100) if total > 0 else 0
        pct_not_in_csv = (not_in_csv / total * 100) if total > 0 else 0
        
        print(f"Season: {season}")
        print(f"  Total games missing opening odds in DB: {total}")
        print(f"  Games with data in CSV: {in_csv} ({pct_in_csv:.1f}%)")
        print(f"  Games missing in BOTH DB and CSV: {not_in_csv} ({pct_not_in_csv:.1f}%)")
        print()
    
    return 0


if __name__ == '__main__':
    exit(main())
