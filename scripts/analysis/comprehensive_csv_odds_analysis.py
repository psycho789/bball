#!/usr/bin/env python3
"""
Comprehensive analysis of CSV files for opening odds fields used in CatBoost training.

Fields needed:
- opening_moneyline_home (decimal odds)
- opening_moneyline_away (decimal odds)  
- opening_spread (line value)
- opening_total (line value)

Provides detailed statistics with evidence.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

def analyze_csv_comprehensive(csv_path: Path) -> Dict:
    """Comprehensive analysis of a CSV file."""
    if not csv_path.exists():
        return {'exists': False, 'error': 'File not found'}
    
    results = {
        'exists': True,
        'total_rows': 0,
        'columns': [],
        'field_stats': {},
        'date_range': None,
        'season_range': None,
        'sample_data': [],
    }
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Detect delimiter
            first_line = f.readline()
            f.seek(0)
            delimiter = ',' if ',' in first_line else '\t'
            
            reader = csv.DictReader(f, delimiter=delimiter)
            results['columns'] = reader.fieldnames or []
            
            # Collect all data
            all_rows = []
            dates = []
            seasons = set()
            
            for row in reader:
                all_rows.append(row)
                results['total_rows'] += 1
                
                # Extract dates
                for date_col in ['date', 'timestamp', 'game_date', 'event_date']:
                    if date_col in row and row[date_col]:
                        try:
                            date_str = row[date_col].strip().split()[0]  # Get date part only
                            for fmt in ['%Y-%m-%d', '%m/%d/%Y']:
                                try:
                                    dt = datetime.strptime(date_str, fmt)
                                    dates.append(dt)
                                    year = dt.year
                                    if dt.month >= 10:
                                        seasons.add(f"{year}-{year+1}")
                                    else:
                                        seasons.add(f"{year-1}-{year}")
                                    break
                                except ValueError:
                                    continue
                        except:
                            pass
            
            if dates:
                results['date_range'] = (min(dates).strftime('%Y-%m-%d'), max(dates).strftime('%Y-%m-%d'))
            if seasons:
                results['season_range'] = sorted(list(seasons))
            
            # Analyze specific fields
            field_stats = {}
            
            # Moneyline fields
            ml_fields = ['team1_moneyline', 'team2_moneyline', 'moneyline_home', 'moneyline_away', 
                        'home_moneyline', 'away_moneyline', 'ml_home', 'ml_away']
            ml_found = [f for f in ml_fields if f in results['columns']]
            if ml_found:
                non_null = {f: 0 for f in ml_found}
                numeric = {f: 0 for f in ml_found}
                for row in all_rows:
                    for f in ml_found:
                        val = row.get(f, '').strip()
                        if val:
                            non_null[f] += 1
                            try:
                                float(val)
                                numeric[f] += 1
                            except:
                                pass
                field_stats['moneyline'] = {
                    'fields': ml_found,
                    'non_null': non_null,
                    'numeric': numeric,
                    'pct_non_null': {f: (non_null[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                    for f in ml_found},
                    'pct_numeric': {f: (numeric[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                   for f in ml_found},
                }
            
            # Spread fields
            spread_fields = ['team1_spread', 'team2_spread', 'spread', 'home_spread', 'away_spread', 'line']
            spread_found = [f for f in spread_fields if f in results['columns']]
            if spread_found:
                non_null = {f: 0 for f in spread_found}
                numeric = {f: 0 for f in spread_found}
                for row in all_rows:
                    for f in spread_found:
                        val = row.get(f, '').strip()
                        if val:
                            non_null[f] += 1
                            try:
                                float(val)
                                numeric[f] += 1
                            except:
                                pass
                field_stats['spread'] = {
                    'fields': spread_found,
                    'non_null': non_null,
                    'numeric': numeric,
                    'pct_non_null': {f: (non_null[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                     for f in spread_found},
                    'pct_numeric': {f: (numeric[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                   for f in spread_found},
                }
            
            # Total fields
            total_fields = ['over_total', 'under_total', 'total', 'over_under', 'ou', 'team1_total', 'team2_total']
            total_found = [f for f in total_fields if f in results['columns']]
            if total_found:
                non_null = {f: 0 for f in total_found}
                numeric = {f: 0 for f in total_found}
                for row in all_rows:
                    for f in total_found:
                        val = row.get(f, '').strip()
                        if val:
                            non_null[f] += 1
                            try:
                                float(val)
                                numeric[f] += 1
                            except:
                                pass
                field_stats['total'] = {
                    'fields': total_found,
                    'non_null': non_null,
                    'numeric': numeric,
                    'pct_non_null': {f: (non_null[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                     for f in total_found},
                    'pct_numeric': {f: (numeric[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                   for f in total_found},
                }
            
            # Team fields
            team_fields = ['team1', 'team2', 'home', 'away', 'home_team', 'away_team']
            team_found = [f for f in team_fields if f in results['columns']]
            if team_found:
                non_null = {f: 0 for f in team_found}
                for row in all_rows:
                    for f in team_found:
                        if row.get(f, '').strip():
                            non_null[f] += 1
                field_stats['teams'] = {
                    'fields': team_found,
                    'non_null': non_null,
                    'pct_non_null': {f: (non_null[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                     for f in team_found},
                }
            
            # Date fields
            date_fields = ['date', 'timestamp', 'game_date', 'event_date']
            date_found = [f for f in date_fields if f in results['columns']]
            if date_found:
                non_null = {f: 0 for f in date_found}
                for row in all_rows:
                    for f in date_found:
                        if row.get(f, '').strip():
                            non_null[f] += 1
                field_stats['date'] = {
                    'fields': date_found,
                    'non_null': non_null,
                    'pct_non_null': {f: (non_null[f] / results['total_rows'] * 100) if results['total_rows'] > 0 else 0 
                                     for f in date_found},
                }
            
            results['field_stats'] = field_stats
            results['sample_data'] = all_rows[:3]
            
            # Check if we can identify opening odds (earliest timestamp per game)
            if 'timestamp' in results['columns'] or 'date' in results['columns']:
                games = defaultdict(list)
                date_col = 'timestamp' if 'timestamp' in results['columns'] else 'date'
                team_cols = [f for f in team_found if f in results['columns']]
                
                if team_cols:
                    for row in all_rows:
                        date_val = row.get(date_col, '').strip()
                        if date_val and len(team_cols) >= 2:
                            try:
                                if date_col == 'timestamp':
                                    dt = datetime.strptime(date_val, '%Y-%m-%d %H:%M:%S')
                                else:
                                    dt = datetime.strptime(date_val.split()[0], '%Y-%m-%d')
                                game_key = (row[team_cols[0]], row[team_cols[1]], dt.strftime('%Y-%m-%d'))
                                games[game_key].append((dt, row))
                            except:
                                pass
                    
                    if games:
                        games_with_multiple = sum(1 for v in games.values() if len(v) > 1)
                        results['opening_odds_analysis'] = {
                            'unique_games': len(games),
                            'games_with_multiple_timestamps': games_with_multiple,
                            'can_identify_opening': games_with_multiple > 0,
                        }
            
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
    
    print("=" * 100)
    print("COMPREHENSIVE CSV FILE ANALYSIS FOR OPENING ODDS FIELDS")
    print("=" * 100)
    print("\nFields needed for CatBoost training:")
    print("  - opening_moneyline_home (decimal odds)")
    print("  - opening_moneyline_away (decimal odds)")
    print("  - opening_spread (line value)")
    print("  - opening_total (line value)")
    print("\n" + "=" * 100 + "\n")
    
    all_results = {}
    
    for csv_file in csv_files:
        csv_path = csv_dir / csv_file
        print(f"\n{'='*100}")
        print(f"FILE: {csv_file}")
        print(f"Path: {csv_path}")
        print(f"{'='*100}\n")
        
        results = analyze_csv_comprehensive(csv_path)
        all_results[csv_file] = results
        
        if not results.get('exists'):
            print(f"❌ FILE NOT FOUND")
            continue
        
        if 'error' in results:
            print(f"❌ ERROR: {results['error']}")
            continue
        
        print(f"✓ File exists")
        print(f"  Total rows: {results['total_rows']:,}")
        print(f"  Total columns: {len(results['columns'])}")
        
        if results.get('date_range'):
            print(f"  Date range: {results['date_range'][0]} to {results['date_range'][1]}")
        if results.get('season_range'):
            seasons_str = ', '.join(results['season_range'][:10])
            if len(results['season_range']) > 10:
                seasons_str += f" ... ({len(results['season_range'])} total)"
            print(f"  Seasons: {seasons_str}")
        
        field_stats = results.get('field_stats', {})
        
        if not field_stats:
            print(f"\n  ⚠ No relevant fields found")
        else:
            print(f"\n  FIELD ANALYSIS:")
            
            if 'moneyline' in field_stats:
                stats = field_stats['moneyline']
                print(f"\n    MONEYLINE:")
                for field in stats['fields']:
                    pct = stats['pct_numeric'][field]
                    count = stats['numeric'][field]
                    print(f"      {field:30s} {count:8,} numeric values ({pct:5.1f}%)")
            
            if 'spread' in field_stats:
                stats = field_stats['spread']
                print(f"\n    SPREAD:")
                for field in stats['fields']:
                    pct = stats['pct_numeric'][field]
                    count = stats['numeric'][field]
                    print(f"      {field:30s} {count:8,} numeric values ({pct:5.1f}%)")
            
            if 'total' in field_stats:
                stats = field_stats['total']
                print(f"\n    TOTAL:")
                for field in stats['fields']:
                    pct = stats['pct_numeric'][field]
                    count = stats['numeric'][field]
                    print(f"      {field:30s} {count:8,} numeric values ({pct:5.1f}%)")
            
            if 'teams' in field_stats:
                stats = field_stats['teams']
                print(f"\n    TEAMS:")
                for field in stats['fields']:
                    pct = stats['pct_non_null'][field]
                    count = stats['non_null'][field]
                    print(f"      {field:30s} {count:8,} non-null ({pct:5.1f}%)")
            
            if 'date' in field_stats:
                stats = field_stats['date']
                print(f"\n    DATE:")
                for field in stats['fields']:
                    pct = stats['pct_non_null'][field]
                    count = stats['non_null'][field]
                    print(f"      {field:30s} {count:8,} non-null ({pct:5.1f}%)")
        
        # Opening odds analysis
        if 'opening_odds_analysis' in results:
            oa = results['opening_odds_analysis']
            print(f"\n  OPENING ODDS IDENTIFICATION:")
            print(f"    Unique games: {oa['unique_games']:,}")
            print(f"    Games with multiple timestamps: {oa['games_with_multiple_timestamps']:,}")
            if oa['can_identify_opening']:
                print(f"    ✓ Can identify opening odds (earliest timestamp per game)")
            else:
                print(f"    ⚠ Cannot identify opening odds (only one timestamp per game)")
        
        # Sample data
        if results.get('sample_data'):
            print(f"\n  SAMPLE DATA (first row):")
            row = results['sample_data'][0]
            for key in list(row.keys())[:15]:
                val = row[key][:50] if len(str(row[key])) > 50 else row[key]
                print(f"    {key:30s} {val}")
            if len(row) > 15:
                print(f"    ... ({len(row) - 15} more columns)")
    
    # Final summary
    print(f"\n\n{'='*100}")
    print("FINAL SUMMARY")
    print(f"{'='*100}\n")
    
    print("Files with opening odds fields:\n")
    
    for csv_file, results in all_results.items():
        if not results.get('exists') or 'error' in results:
            continue
        
        field_stats = results.get('field_stats', {})
        has_ml = 'moneyline' in field_stats
        has_spread = 'spread' in field_stats
        has_total = 'total' in field_stats
        
        if has_ml or has_spread or has_total:
            print(f"✓ {csv_file}")
            if has_ml:
                ml_stats = field_stats['moneyline']
                best_field = max(ml_stats['fields'], key=lambda f: ml_stats['pct_numeric'][f])
                best_pct = ml_stats['pct_numeric'][best_field]
                print(f"    Moneyline: {best_field} ({best_pct:.1f}% populated)")
            if has_spread:
                sp_stats = field_stats['spread']
                best_field = max(sp_stats['fields'], key=lambda f: sp_stats['pct_numeric'][f])
                best_pct = sp_stats['pct_numeric'][best_field]
                print(f"    Spread: {best_field} ({best_pct:.1f}% populated)")
            if has_total:
                tot_stats = field_stats['total']
                best_field = max(tot_stats['fields'], key=lambda f: tot_stats['pct_numeric'][f])
                best_pct = tot_stats['pct_numeric'][best_field]
                print(f"    Total: {best_field} ({best_pct:.1f}% populated)")
            
            if 'opening_odds_analysis' in results:
                oa = results['opening_odds_analysis']
                if oa['can_identify_opening']:
                    print(f"    ✓ Can identify opening odds")
                else:
                    print(f"    ⚠ Single row per game (assumed opening odds)")
            print()
    
    # Validation commands
    print(f"\n{'='*100}")
    print("VALIDATION COMMANDS")
    print(f"{'='*100}\n")
    
    for csv_file in csv_files:
        csv_path = csv_dir / csv_file
        print(f"# {csv_file}")
        print(f"head -3 {csv_path}")
        print(f"wc -l {csv_path}")
        print()
    
    return 0


if __name__ == '__main__':
    exit(main())
