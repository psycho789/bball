#!/usr/bin/env python3
"""
Verify specific games that have NULL espn_game_id by checking:
1. What team names are in CSV
2. What normalized team names result
3. What ESPN abbreviations should be used
4. Sample games to check manually
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from scripts.lib.team_name_mapping import normalize_team_name

def check_csv_team_names():
    """Check what team names appear in CSV files."""
    csv_dir = Path(__file__).parent.parent.parent / 'data' / 'stats-csv'
    
    team_names_found = defaultdict(set)
    
    # Check nba_2008-2025.csv
    historical_csv = csv_dir / 'nba_2008-2025.csv'
    if historical_csv.exists():
        print("Checking nba_2008-2025.csv...")
        with open(historical_csv, 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 100:  # Sample first 100 rows
                    break
                home = row.get('home', '').strip()
                away = row.get('away', '').strip()
                if home:
                    team_names_found['home'].add(home)
                if away:
                    team_names_found['away'].add(away)
    
    # Check nba_main_lines.csv
    main_lines_csv = csv_dir / 'nba_main_lines.csv'
    if main_lines_csv.exists():
        print("Checking nba_main_lines.csv...")
        with open(main_lines_csv, 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 100:  # Sample first 100 rows
                    break
                team1 = row.get('team1', '').strip()
                team2 = row.get('team2', '').strip()
                if team1:
                    team_names_found['team1'].add(team1)
                if team2:
                    team_names_found['team2'].add(team2)
    
    return team_names_found


def test_normalization():
    """Test normalization of team names found in CSV."""
    team_names = check_csv_team_names()
    
    print("\n" + "=" * 100)
    print("TEAM NAME NORMALIZATION TEST")
    print("=" * 100)
    
    all_names = set()
    for names_set in team_names.values():
        all_names.update(names_set)
    
    print(f"\nFound {len(all_names)} unique team names in CSV samples")
    print("\nNormalization results:")
    print("-" * 100)
    print(f"{'CSV Name':<30} {'Normalized':<15} {'Status'}")
    print("-" * 100)
    
    failed = []
    for name in sorted(all_names):
        normalized = normalize_team_name(name)
        status = "✓" if normalized else "✗ FAILED"
        if not normalized:
            failed.append(name)
        print(f"{name:<30} {normalized or 'None':<15} {status}")
    
    if failed:
        print(f"\n⚠️  {len(failed)} team names failed normalization:")
        for name in failed:
            print(f"   - {name}")
    
    return failed


def get_sample_games_from_markdown():
    """Get sample games from the markdown file."""
    md_file = Path(__file__).parent.parent.parent / 'cursor-files' / 'analysis' / '2026-01-22-games-missing-opening-odds' / 'games_missing_opening_odds.md'
    
    if not md_file.exists():
        print(f"Markdown file not found: {md_file}")
        return []
    
    games = []
    with open(md_file, 'r') as f:
        for line in f:
            if '|' in line and 'game_id' not in line.lower() and '---' not in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    try:
                        game_id = parts[0]
                        season = parts[1]
                        date = parts[2]
                        matchup = parts[3]
                        
                        # Parse matchup: "AWAY @ HOME"
                        if '@' in matchup:
                            away, home = matchup.split('@')
                            away = away.strip()
                            home = home.strip()
                            
                            games.append({
                                'game_id': game_id,
                                'season': season,
                                'date': date,
                                'away': away,
                                'home': home,
                            })
                    except:
                        pass
    
    return games[:20]  # Return first 20


def analyze_sample_games():
    """Analyze sample games from markdown."""
    games = get_sample_games_from_markdown()
    
    if not games:
        print("No games found in markdown file")
        return
    
    print("\n" + "=" * 100)
    print("SAMPLE GAMES ANALYSIS")
    print("=" * 100)
    
    print(f"\nAnalyzing {len(games)} sample games from markdown...")
    print("\n" + "-" * 100)
    print(f"{'Date':<12} {'Away (CSV)':<15} {'Home (CSV)':<15} {'Away (Norm)':<15} {'Home (Norm)':<15} {'Status'}")
    print("-" * 100)
    
    for game in games:
        away_norm = normalize_team_name(game['away'])
        home_norm = normalize_team_name(game['home'])
        
        status = "✓" if (away_norm and home_norm) else "✗"
        
        print(f"{game['date']:<12} {game['away']:<15} {game['home']:<15} {away_norm or 'None':<15} {home_norm or 'None':<15} {status}")
    
    print("\n" + "=" * 100)
    print("VERIFICATION CHECKLIST")
    print("=" * 100)
    print("\nFor each game above, verify in database:")
    print("1. Does ESPN game exist with these teams on this date?")
    print("2. What ESPN abbreviations are used? (check espn.scoreboard_games)")
    print("3. Do normalized names match ESPN abbreviations?")
    print("4. Is date within ±1 day of ESPN game date?")


if __name__ == '__main__':
    print("=" * 100)
    print("VERIFYING NULL ESPN_GAME_ID - CSV TEAM NAME ANALYSIS")
    print("=" * 100)
    
    # Test normalization
    failed = test_normalization()
    
    # Analyze sample games
    analyze_sample_games()
    
    print("\n" + "=" * 100)
    print("NEXT STEPS")
    print("=" * 100)
    print("\n1. Run SQL queries from: scripts/analysis/sql_queries_to_verify_null_espn_game_id.sql")
    print("2. Compare normalized team names above with ESPN abbreviations in database")
    print("3. Check if ESPN games exist for sample games")
    print("4. Identify patterns in failures (specific teams, dates, etc.)")
