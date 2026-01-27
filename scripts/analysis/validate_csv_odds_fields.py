#!/usr/bin/env python3
"""
Validate CSV files for opening odds fields used in CatBoost training.

Checks all CSV files for:
- opening_moneyline_home (decimal odds)
- opening_moneyline_away (decimal odds)
- opening_spread (line value)
- opening_total (line value)

Provides detailed statistics and evidence for validation.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

def analyze_csv_file(csv_path: Path) -> Dict:
    """Analyze a CSV file and return statistics."""
    if not csv_path.exists():
        return {
            'exists': False,
            'error': 'File not found'
        }
    
    results = {
        'exists': True,
        'total_rows': 0,
        'columns': [],
        'sample_rows': [],
        'field_analysis': {},
        'date_range': None,
        'season_range': None,
    }
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Try to detect delimiter
            first_line = f.readline()
            f.seek(0)
            
            # Try comma first, then tab
            delimiter = ',' if ',' in first_line else '\t'
            
            reader = csv.DictReader(f, delimiter=delimiter)
            results['columns'] = reader.fieldnames or []
            
            # Collect sample rows and analyze
            rows = []
            dates = []
            seasons = set()
            
            for i, row in enumerate(reader):
                if i < 5:
                    rows.append(row)
                results['total_rows'] += 1
                
                # Try to extract date/season if available
                for date_col in ['date', 'timestamp', 'game_date', 'event_date']:
                    if date_col in row and row[date_col]:
                        try:
                            date_str = row[date_col].strip()
                            # Try different date formats
                            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y']:
                                try:
                                    dt = datetime.strptime(date_str.split()[0], fmt)
                                    dates.append(dt)
                                    # Extract season
                                    year = dt.year
                                    if dt.month >= 10:  # NBA season starts in October
                                        season = f"{year}-{year+1}"
                                    else:
                                        season = f"{year-1}-{year}"
                                    seasons.add(season)
                                    break
                                except ValueError:
                                    continue
                        except:
                            pass
                
                if results['total_rows'] >= 10000:  # Limit for performance
                    break
            
            results['sample_rows'] = rows[:5]
            
            if dates:
                results['date_range'] = (min(dates).strftime('%Y-%m-%d'), max(dates).strftime('%Y-%m-%d'))
            if seasons:
                results['season_range'] = sorted(list(seasons))
            
            # Analyze fields relevant to opening odds
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Fields we're looking for
            target_fields = {
                'moneyline': ['moneyline', 'ml', 'team1_moneyline', 'team2_moneyline', 'home_moneyline', 'away_moneyline'],
                'spread': ['spread', 'team1_spread', 'team2_spread', 'home_spread', 'away_spread', 'line'],
                'total': ['total', 'over_under', 'ou', 'over_total', 'under_total', 'team1_total', 'team2_total'],
                'date': ['date', 'timestamp', 'game_date', 'event_date'],
                'teams': ['team1', 'team2', 'home_team', 'away_team', 'home', 'away'],
                'game_id': ['game_id', 'gameid', 'event_id', 'espn_game_id'],
            }
            
            field_stats = {}
            for category, field_names in target_fields.items():
                found_fields = []
                for field in field_names:
                    if field in results['columns']:
                        found_fields.append(field)
                
                if found_fields:
                    # Count non-null values
                    f.seek(0)
                    reader = csv.DictReader(f, delimiter=delimiter)
                    non_null_counts = {field: 0 for field in found_fields}
                    total_checked = 0
                    
                    for row in reader:
                        total_checked += 1
                        for field in found_fields:
                            if row.get(field) and row[field].strip():
                                try:
                                    # Try to parse as number
                                    float(row[field])
                                    non_null_counts[field] += 1
                                except ValueError:
                                    pass
                        if total_checked >= 10000:
                            break
                    
                    field_stats[category] = {
                        'fields_found': found_fields,
                        'non_null_counts': non_null_counts,
                        'total_checked': total_checked,
                        'percentages': {k: (v / total_checked * 100) if total_checked > 0 else 0 
                                       for k, v in non_null_counts.items()}
                    }
            
            results['field_analysis'] = field_stats
            
    except Exception as e:
        results['error'] = str(e)
        import traceback
        results['traceback'] = traceback.format_exc()
    
    return results


def main():
    """Main function."""
    repo_root = Path(__file__).parent.parent.parent
    csv_dir = repo_root / 'data' / 'stats-csv'
    
    csv_files = [
        'advanced.csv',
        'nba_2008-2025.csv',
        'nba_detailed_odds.csv',
        'nba_main_lines.csv',
        'per-game.csv',
        'stats.csv',
    ]
    
    print("=" * 80)
    print("CSV FILE VALIDATION FOR OPENING ODDS FIELDS")
    print("=" * 80)
    print("\nFields needed for CatBoost training:")
    print("  - opening_moneyline_home (decimal odds)")
    print("  - opening_moneyline_away (decimal odds)")
    print("  - opening_spread (line value)")
    print("  - opening_total (line value)")
    print("\n" + "=" * 80 + "\n")
    
    all_results = {}
    
    for csv_file in csv_files:
        csv_path = csv_dir / csv_file
        print(f"\n{'='*80}")
        print(f"Analyzing: {csv_file}")
        print(f"Path: {csv_path}")
        print(f"{'='*80}\n")
        
        results = analyze_csv_file(csv_path)
        all_results[csv_file] = results
        
        if not results.get('exists'):
            print(f"❌ FILE NOT FOUND: {csv_path}")
            continue
        
        if 'error' in results:
            print(f"❌ ERROR: {results['error']}")
            if 'traceback' in results:
                print(results['traceback'])
            continue
        
        print(f"✓ File exists")
        print(f"  Total rows: {results['total_rows']:,}")
        print(f"  Columns ({len(results['columns'])}): {', '.join(results['columns'][:10])}{'...' if len(results['columns']) > 10 else ''}")
        
        if results.get('date_range'):
            print(f"  Date range: {results['date_range'][0]} to {results['date_range'][1]}")
        if results.get('season_range'):
            print(f"  Seasons: {', '.join(results['season_range'][:5])}{'...' if len(results['season_range']) > 5 else ''}")
        
        print(f"\n  Field Analysis:")
        field_analysis = results.get('field_analysis', {})
        
        if not field_analysis:
            print("    No relevant fields found")
        else:
            for category, stats in field_analysis.items():
                print(f"\n    {category.upper()}:")
                for field in stats['fields_found']:
                    count = stats['non_null_counts'].get(field, 0)
                    pct = stats['percentages'].get(field, 0)
                    print(f"      - {field}: {count:,} non-null ({pct:.1f}%)")
        
        # Show sample rows
        if results.get('sample_rows'):
            print(f"\n  Sample rows (first 2):")
            for i, row in enumerate(results['sample_rows'][:2], 1):
                print(f"    Row {i}:")
                for key, value in list(row.items())[:10]:
                    print(f"      {key}: {value}")
                if len(row) > 10:
                    print(f"      ... ({len(row) - 10} more columns)")
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    
    print("Files that contain opening odds relevant fields:\n")
    
    for csv_file, results in all_results.items():
        if not results.get('exists') or 'error' in results:
            continue
        
        field_analysis = results.get('field_analysis', {})
        has_moneyline = 'moneyline' in field_analysis and field_analysis['moneyline']['fields_found']
        has_spread = 'spread' in field_analysis and field_analysis['spread']['fields_found']
        has_total = 'total' in field_analysis and field_analysis['total']['fields_found']
        has_teams = 'teams' in field_analysis and field_analysis['teams']['fields_found']
        has_date = 'date' in field_analysis and field_analysis['date']['fields_found']
        
        if has_moneyline or has_spread or has_total:
            print(f"✓ {csv_file}")
            if has_moneyline:
                ml_fields = field_analysis['moneyline']['fields_found']
                ml_pct = max(field_analysis['moneyline']['percentages'].values()) if field_analysis['moneyline']['percentages'] else 0
                print(f"    - Moneyline fields: {', '.join(ml_fields)} ({ml_pct:.1f}% populated)")
            if has_spread:
                sp_fields = field_analysis['spread']['fields_found']
                sp_pct = max(field_analysis['spread']['percentages'].values()) if field_analysis['spread']['percentages'] else 0
                print(f"    - Spread fields: {', '.join(sp_fields)} ({sp_pct:.1f}% populated)")
            if has_total:
                tot_fields = field_analysis['total']['fields_found']
                tot_pct = max(field_analysis['total']['percentages'].values()) if field_analysis['total']['percentages'] else 0
                print(f"    - Total fields: {', '.join(tot_fields)} ({tot_pct:.1f}% populated)")
            if has_teams:
                print(f"    - Team fields: {', '.join(field_analysis['teams']['fields_found'])}")
            if has_date:
                print(f"    - Date fields: {', '.join(field_analysis['date']['fields_found'])}")
            print()
    
    # Commands for manual validation
    print(f"\n{'='*80}")
    print("COMMANDS FOR MANUAL VALIDATION")
    print(f"{'='*80}\n")
    
    for csv_file in csv_files:
        csv_path = csv_dir / csv_file
        print(f"# Check {csv_file}:")
        print(f"head -5 {csv_path}")
        print(f"wc -l {csv_path}")
        print(f"cut -d',' -f1-5 {csv_path} | head -10")
        print()
    
    return 0


if __name__ == '__main__':
    exit(main())
