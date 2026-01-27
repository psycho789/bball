#!/usr/bin/env python3
"""
Investigate ALIGN_DATA warning for game 401809981.

This script queries the database to understand why home + away prices sum to ~1.0,
which suggests the away price might not be converted to home probability space.
"""

import os
import sys

# Add project root to path to import from scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._db_lib import get_dsn, connect

def investigate_game(conn, game_id: str):
    """Investigate a specific game's Kalshi price data."""
    
    print(f"\n{'='*80}")
    print(f"Investigating Game: {game_id}")
    print(f"{'='*80}\n")
    
    # Query the canonical view
    query = """
    SELECT 
        sequence_number,
        snapshot_ts,
        kalshi_home_mid_price,
        kalshi_home_bid,
        kalshi_home_ask,
        kalshi_away_mid_price,
        kalshi_away_bid,
        kalshi_away_ask,
        espn_home_prob,
        espn_away_prob
    FROM derived.snapshot_features_v1
    WHERE game_id = %s 
      AND season_label = '2025-26'
      AND (kalshi_home_mid_price IS NOT NULL OR kalshi_away_mid_price IS NOT NULL)
    ORDER BY sequence_number
    LIMIT 50
    """
    
    rows = conn.execute(query, (game_id,)).fetchall()
    
    if not rows:
        print(f"❌ No data found for game {game_id}")
        return
    
    print(f"Found {len(rows)} snapshots with Kalshi data\n")
    
    # Analyze the data
    warning_count = 0
    total_count = 0
    
    print("Sample snapshots (first 10):")
    print("-" * 120)
    print(f"{'Seq':<5} {'Home Mid':<10} {'Away Mid':<10} {'Sum':<10} {'Diff':<10} {'Home≈Away?':<12} {'Sum≈1.0?':<12}")
    print("-" * 120)
    
    for row in rows[:10]:
        seq, ts, home_mid, home_bid, home_ask, away_mid, away_bid, away_ask, espn_home, espn_away = row
        
        if home_mid is not None and away_mid is not None:
            total_count += 1
            
            # Normalize (handle 0-100 format)
            home_norm = float(home_mid) if float(home_mid) <= 1.0 else float(home_mid) / 100.0
            away_norm = float(away_mid) if float(away_mid) <= 1.0 else float(away_mid) / 100.0
            
            diff_check = abs(home_norm - away_norm)
            sum_check = abs((home_norm + away_norm) - 1.0)
            
            home_equals_away = "✓" if diff_check < 0.05 else "✗"
            sum_equals_one = "⚠️ WARNING" if sum_check < 0.05 else "✓"
            
            if sum_check < 0.05:
                warning_count += 1
            
            print(f"{seq:<5} {home_norm:<10.4f} {away_norm:<10.4f} {home_norm+away_norm:<10.4f} {diff_check:<10.4f} {home_equals_away:<12} {sum_equals_one:<12}")
    
    print("-" * 120)
    print(f"\nSummary:")
    print(f"  - Total snapshots with both home and away prices: {total_count}")
    print(f"  - Snapshots where home + away ≈ 1.0 (WARNING): {warning_count}")
    print(f"  - Percentage with warning: {warning_count/total_count*100:.1f}%" if total_count > 0 else "  - N/A")
    
    # Check raw Kalshi data
    print(f"\n{'='*80}")
    print("Checking raw Kalshi candlestick data...")
    print(f"{'='*80}\n")
    
    # Query raw Kalshi data to see what's actually stored
    raw_query = """
    SELECT DISTINCT
        c.market_ticker,
        c.yes_bid_close,
        c.yes_ask_close,
        (c.yes_bid_close::NUMERIC + c.yes_ask_close::NUMERIC) / 200.0 AS raw_mid_price,
        CASE 
            WHEN c.market_ticker LIKE '%HOME%' OR c.market_ticker LIKE '%home%' THEN 'HOME'
            WHEN c.market_ticker LIKE '%AWAY%' OR c.market_ticker LIKE '%away%' THEN 'AWAY'
            ELSE 'UNKNOWN'
        END AS market_type
    FROM kalshi.candlesticks c
    WHERE c.game_id = %s
    ORDER BY c.market_ticker, c.timestamp_utc
    LIMIT 20
    """
    
    raw_rows = conn.execute(raw_query, (game_id,)).fetchall()
    
    if raw_rows:
        print("Raw Kalshi candlestick data:")
        print("-" * 100)
        print(f"{'Ticker':<40} {'Type':<10} {'Yes Bid':<10} {'Yes Ask':<10} {'Raw Mid':<10}")
        print("-" * 100)
        for row in raw_rows:
            ticker, yes_bid, yes_ask, raw_mid, market_type = row
            print(f"{ticker:<40} {market_type:<10} {yes_bid:<10} {yes_ask:<10} {raw_mid:<10.4f}")
        print("-" * 100)
    else:
        print("❌ No raw Kalshi candlestick data found")
    
    # Check the view's conversion logic
    print(f"\n{'='*80}")
    print("Expected conversion logic:")
    print(f"{'='*80}\n")
    print("According to the SQL view definition:")
    print("  - Away market raw: 'Will away team win?' (0-100)")
    print("  - Conversion: kalshi_away_mid_price = 1.0 - ((yes_bid + yes_ask) / 200.0)")
    print("  - Expected result: home_mid ≈ away_mid (both in home probability space)")
    print("\nIf home + away ≈ 1.0, it suggests:")
    print("  - The away price is NOT being converted (still in raw away space)")
    print("  - OR there's a bug in the view definition")

def main():
    """Main entry point."""
    try:
        conn = connect()
        
        # Investigate the specific game from the warning
        investigate_game(conn, "401809981")
        
        # Also check if this pattern appears in other games
        print(f"\n{'='*80}")
        print("Checking for other games with similar pattern...")
        print(f"{'='*80}\n")
        
        pattern_query = """
        SELECT 
            game_id,
            COUNT(*) as snapshot_count,
            COUNT(CASE 
                WHEN kalshi_home_mid_price IS NOT NULL 
                 AND kalshi_away_mid_price IS NOT NULL
                 AND ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
                THEN 1 
            END) as warning_count
        FROM derived.snapshot_features_v1
        WHERE season_label = '2025-26'
          AND kalshi_home_mid_price IS NOT NULL
          AND kalshi_away_mid_price IS NOT NULL
        GROUP BY game_id
        HAVING COUNT(CASE 
            WHEN ABS((kalshi_home_mid_price + kalshi_away_mid_price) - 1.0) < 0.05
            THEN 1 
        END) > 0
        ORDER BY warning_count DESC
        LIMIT 10
        """
        
        pattern_rows = conn.execute(pattern_query).fetchall()
        
        if pattern_rows:
            print(f"Found {len(pattern_rows)} games with home+away≈1.0 pattern:")
            print("-" * 60)
            print(f"{'Game ID':<15} {'Total Snaps':<15} {'Warning Count':<15} {'%':<10}")
            print("-" * 60)
            for game_id, total, warnings in pattern_rows:
                pct = (warnings / total * 100) if total > 0 else 0
                print(f"{game_id:<15} {total:<15} {warnings:<15} {pct:<10.1f}%")
            print("-" * 60)
        else:
            print("✅ No other games found with this pattern")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
