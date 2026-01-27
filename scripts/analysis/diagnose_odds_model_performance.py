#!/usr/bin/env python3
"""
Diagnose why catboost_odds_platt model has poor performance.

This script checks:
1. How many snapshots have opening odds data
2. How many snapshots have precomputed probabilities for odds models
3. Whether the model was trained correctly
4. Whether precomputation worked correctly
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg
from psycopg.rows import dict_row
from scripts.lib._db_lib import get_dsn


def main():
    dsn = get_dsn(None)  # Will use DATABASE_URL env var if None
    
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        print("=" * 80)
        print("DIAGNOSING catboost_odds_platt MODEL PERFORMANCE")
        print("=" * 80)
        print()
        
        # 1. Check total snapshots vs odds model coverage
        print("1. DATA COVERAGE FOR 2025-26 SEASON")
        print("-" * 80)
        query1 = """
        SELECT 
            COUNT(*) as total_snapshots,
            COUNT(catboost_odds_platt_prob) as odds_platt_populated,
            COUNT(catboost_baseline_platt_prob) as baseline_platt_populated,
            COUNT(catboost_platt_prob) as catboost_platt_populated,
            ROUND(100.0 * COUNT(catboost_odds_platt_prob) / COUNT(*), 2) as odds_platt_pct,
            ROUND(100.0 * COUNT(catboost_baseline_platt_prob) / COUNT(*), 2) as baseline_platt_pct
        FROM derived.model_probabilities_v1
        WHERE season_label = '2025-26'
        """
        row = conn.execute(query1).fetchone()
        print(f"Total snapshots: {row['total_snapshots']:,}")
        print(f"catboost_odds_platt populated: {row['odds_platt_populated']:,} ({row['odds_platt_pct']}%)")
        print(f"catboost_baseline_platt populated: {row['baseline_platt_populated']:,} ({row['baseline_platt_pct']}%)")
        print(f"catboost_platt populated: {row['catboost_platt_populated']:,}")
        print()
        
        # 2. Check opening odds availability
        print("2. OPENING ODDS DATA AVAILABILITY")
        print("-" * 80)
        query2 = """
        SELECT 
            COUNT(*) as total_snapshots,
            COUNT(opening_moneyline_home) as has_opening_moneyline,
            COUNT(opening_spread) as has_opening_spread,
            COUNT(opening_total) as has_opening_total,
            ROUND(100.0 * COUNT(opening_moneyline_home) / COUNT(*), 2) as moneyline_pct,
            ROUND(100.0 * COUNT(opening_spread) / COUNT(*), 2) as spread_pct,
            ROUND(100.0 * COUNT(opening_total) / COUNT(*), 2) as total_pct
        FROM derived.snapshot_features_v1
        WHERE season_label = '2025-26'
        """
        row = conn.execute(query2).fetchone()
        print(f"Total snapshots: {row['total_snapshots']:,}")
        print(f"Has opening moneyline: {row['has_opening_moneyline']:,} ({row['moneyline_pct']}%)")
        print(f"Has opening spread: {row['has_opening_spread']:,} ({row['spread_pct']}%)")
        print(f"Has opening total: {row['has_opening_total']:,} ({row['total_pct']}%)")
        print()
        
        # 3. Check correlation: opening odds available but model prob NULL
        print("3. MISSING MODEL PROBABILITIES WHERE OPENING ODDS EXIST")
        print("-" * 80)
        query3 = """
        SELECT 
            COUNT(*) as total_snapshots,
            COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL THEN 1 END) as has_opening_odds,
            COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL AND mp.catboost_odds_platt_prob IS NULL THEN 1 END) as has_odds_but_null_prob,
            COUNT(CASE WHEN sf.opening_moneyline_home IS NULL AND mp.catboost_odds_platt_prob IS NOT NULL THEN 1 END) as no_odds_but_has_prob,
            ROUND(100.0 * COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL AND mp.catboost_odds_platt_prob IS NULL THEN 1 END) / 
                  NULLIF(COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL THEN 1 END), 0), 2) as pct_missing
        FROM derived.snapshot_features_v1 sf
        LEFT JOIN derived.model_probabilities_v1 mp
            ON sf.season_label = mp.season_label
            AND sf.game_id = mp.game_id
            AND sf.sequence_number = mp.sequence_number
            AND sf.snapshot_ts = mp.snapshot_ts
        WHERE sf.season_label = '2025-26'
        """
        row = conn.execute(query3).fetchone()
        print(f"Snapshots with opening odds: {row['has_opening_odds']:,}")
        print(f"Opening odds available but prob NULL: {row['has_odds_but_null_prob']:,} ({row['pct_missing']}%)")
        print(f"No opening odds but prob exists: {row['no_odds_but_has_prob']:,}")
        print()
        
        # 4. Check games coverage
        print("4. GAME-LEVEL COVERAGE")
        print("-" * 80)
        query4 = """
        SELECT 
            COUNT(DISTINCT sf.game_id) as total_games,
            COUNT(DISTINCT CASE WHEN mp.catboost_odds_platt_prob IS NOT NULL THEN sf.game_id END) as games_with_odds_platt,
            COUNT(DISTINCT CASE WHEN mp.catboost_baseline_platt_prob IS NOT NULL THEN sf.game_id END) as games_with_baseline_platt
        FROM derived.snapshot_features_v1 sf
        LEFT JOIN derived.model_probabilities_v1 mp
            ON sf.season_label = mp.season_label
            AND sf.game_id = mp.game_id
            AND sf.sequence_number = mp.sequence_number
            AND sf.snapshot_ts = mp.snapshot_ts
        WHERE sf.season_label = '2025-26'
        """
        row = conn.execute(query4).fetchone()
        print(f"Total games: {row['total_games']}")
        print(f"Games with catboost_odds_platt probs: {row['games_with_odds_platt']}")
        print(f"Games with catboost_baseline_platt probs: {row['games_with_baseline_platt']}")
        print()
        
        # 5. Sample games that have opening odds but no probabilities
        print("5. SAMPLE GAMES WITH OPENING ODDS BUT NO PROBABILITIES")
        print("-" * 80)
        query5 = """
        SELECT 
            sf.game_id,
            COUNT(*) as total_snapshots,
            COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL THEN 1 END) as snapshots_with_odds,
            COUNT(mp.catboost_odds_platt_prob) as snapshots_with_prob
        FROM derived.snapshot_features_v1 sf
        LEFT JOIN derived.model_probabilities_v1 mp
            ON sf.season_label = mp.season_label
            AND sf.game_id = mp.game_id
            AND sf.sequence_number = mp.sequence_number
            AND sf.snapshot_ts = mp.snapshot_ts
        WHERE sf.season_label = '2025-26'
          AND sf.opening_moneyline_home IS NOT NULL
        GROUP BY sf.game_id
        HAVING COUNT(mp.catboost_odds_platt_prob) = 0
        LIMIT 5
        """
        rows = conn.execute(query5).fetchall()
        if rows:
            print("Found games with opening odds but no probabilities:")
            for r in rows:
                print(f"  Game {r['game_id']}: {r['snapshots_with_odds']} snapshots with odds, 0 with probabilities")
        else:
            print("No games found with opening odds but missing probabilities")
        print()
        
        # 6. Check probability value ranges
        print("6. PROBABILITY VALUE RANGES")
        print("-" * 80)
        query6 = """
        SELECT 
            'baseline_platt' as model,
            COUNT(*) as count,
            MIN(catboost_baseline_platt_prob) as min_prob,
            MAX(catboost_baseline_platt_prob) as max_prob,
            AVG(catboost_baseline_platt_prob) as avg_prob
        FROM derived.model_probabilities_v1
        WHERE season_label = '2025-26'
          AND catboost_baseline_platt_prob IS NOT NULL
        UNION ALL
        SELECT 
            'odds_platt' as model,
            COUNT(*) as count,
            MIN(catboost_odds_platt_prob) as min_prob,
            MAX(catboost_odds_platt_prob) as max_prob,
            AVG(catboost_odds_platt_prob) as avg_prob
        FROM derived.model_probabilities_v1
        WHERE season_label = '2025-26'
          AND catboost_odds_platt_prob IS NOT NULL
        """
        rows = conn.execute(query6).fetchall()
        for r in rows:
            print(f"{r['model']}:")
            print(f"  Count: {r['count']:,}")
            print(f"  Min: {r['min_prob']:.6f}")
            print(f"  Max: {r['max_prob']:.6f}")
            print(f"  Avg: {r['avg_prob']:.6f}")
        print()
        
        print("=" * 80)
        print("DIAGNOSIS COMPLETE")
        print("=" * 80)
        print()
        print("KEY INSIGHTS:")
        print("- If odds_platt_pct is much lower than baseline_platt_pct, precomputation may have failed")
        print("- If has_odds_but_null_prob is high, the model may not be loading correctly")
        print("- If games_with_odds_platt is much lower than total_games, many games lack opening odds")


if __name__ == "__main__":
    main()
