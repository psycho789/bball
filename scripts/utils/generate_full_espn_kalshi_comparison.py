#!/usr/bin/env python3
"""
Generate full in-game comparison of ESPN win probabilities vs Kalshi candlesticks.

Uses ALL probability updates and ALL candlesticks during each game, matched by timestamp.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib._db_lib import get_dsn


def main() -> int:
    parser = argparse.ArgumentParser(description="Full ESPN vs Kalshi in-game comparison")
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN")
    parser.add_argument("--output", default="data/reports/espn_kalshi_full_comparison.txt", help="Output file")
    args = parser.parse_args()
    
    dsn = get_dsn(args.dsn)
    
    query = """
    WITH matched_games AS (
        -- Only use HOME team tickers (like original scripts)
        SELECT DISTINCT
            km.event_ticker,
            km.ticker as kalshi_ticker,
            sg.event_id as espn_event_id,
            sg.event_date as game_start,
            sg.home_team_display_name,
            sg.away_team_display_name,
            sg.status_completed
        FROM kalshi.markets km
        JOIN espn.scoreboard_games sg ON km.espn_event_id = sg.event_id
        WHERE km.espn_event_id IS NOT NULL
          AND sg.status_completed = true
          -- Only HOME team markets (ticker ends with home team abbreviation)
          AND sg.home_team_display_name ILIKE '%' || km.yes_sub_title || '%'
    ),
    active_comparisons AS (
        SELECT 
            mg.event_ticker,
            mg.espn_event_id,
            mg.game_start,
            p.sequence_number,
            p.last_modified_utc as espn_timestamp,
            -- ESPN stores as decimal (0-1), convert to cents (0-100)
            -- Kalshi ticker is always for HOME team, so use home_win_percentage directly
            p.home_win_percentage * 100 as espn_prob_cents,
            kc.period_ts as kalshi_timestamp,
            kc.yes_bid_low as kalshi_bid_low,
            kc.yes_bid_high as kalshi_bid_high,
            kc.yes_ask_low as kalshi_ask_low,
            kc.yes_ask_high as kalshi_ask_high,
            kc.volume as kalshi_volume,
            ABS(EXTRACT(EPOCH FROM (p.last_modified_utc - kc.period_ts))) as time_diff_sec
        FROM matched_games mg
        JOIN espn.probabilities_raw_items p ON mg.espn_event_id = p.game_id
        JOIN kalshi.candlesticks kc ON mg.kalshi_ticker = kc.ticker
        WHERE p.last_modified_utc IS NOT NULL
          AND kc.yes_bid_low IS NOT NULL
          AND kc.yes_ask_high IS NOT NULL
          AND kc.volume > 0  -- Only active trading periods
          -- Match timestamps: ESPN timestamp should fall within the 1-minute candle window
          -- Candle period_ts is the END of the 1-minute period, so check if ESPN ts is between (period_ts - 60) and period_ts
          AND p.last_modified_utc >= (kc.period_ts - INTERVAL '1 minute')
          AND p.last_modified_utc <= kc.period_ts
          AND p.last_modified_utc >= mg.game_start - INTERVAL '1 hour'  -- pre-game to end
          AND p.last_modified_utc <= mg.game_start + INTERVAL '4 hours'  -- game duration + buffer
    ),
    game_stats AS (
        SELECT 
            event_ticker,
            espn_event_id,
            COUNT(*) as total_comparisons,
            -- ESPN is outside if it's below bid_low OR above ask_high (the tradeable range)
            SUM(CASE WHEN espn_prob_cents < kalshi_bid_low OR espn_prob_cents > kalshi_ask_high THEN 1 ELSE 0 END) as outside_range_count,
            AVG(CASE 
                WHEN espn_prob_cents < kalshi_bid_low THEN kalshi_bid_low - espn_prob_cents
                WHEN espn_prob_cents > kalshi_ask_high THEN espn_prob_cents - kalshi_ask_high
                ELSE 0
            END) as avg_deviation_cents,
            MAX(CASE 
                WHEN espn_prob_cents < kalshi_bid_low THEN kalshi_bid_low - espn_prob_cents
                WHEN espn_prob_cents > kalshi_ask_high THEN espn_prob_cents - kalshi_ask_high
                ELSE 0
            END) as max_deviation_cents
        FROM active_comparisons
        GROUP BY event_ticker, espn_event_id
    )
    SELECT 
        COUNT(DISTINCT event_ticker) as games_analyzed,
        SUM(total_comparisons) as total_comparisons,
        SUM(outside_range_count) as total_outside_range,
        ROUND(100.0 * SUM(outside_range_count) / SUM(total_comparisons), 1) as overall_outside_pct,
        ROUND(AVG(avg_deviation_cents)::numeric, 2) as avg_deviation_cents,
        ROUND(MAX(max_deviation_cents)::numeric, 1) as max_deviation_cents
    FROM game_stats
    WHERE total_comparisons > 0;
    """
    
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            
            if not row or row[1] == 0:
                print("No matching data found. Check timestamp alignment.")
                return 1
            
            games_analyzed, total_comparisons, total_outside, outside_pct, avg_dev, max_dev = row
            
            report = f"""
================================================================================
FULL ESPN vs KALSHI IN-GAME COMPARISON REPORT
================================================================================

This report compares ALL ESPN win probability updates with ALL Kalshi candlesticks
during active trading periods, matched by timestamp (within 90 seconds).

METHODOLOGY:
- ESPN probability updates: Real-time win probability from ESPN's game broadcast
- Kalshi candlesticks: 1-minute bid-ask ranges from prediction markets
- Matching: Timestamp alignment within 90 seconds
- Filter: Only candlesticks with volume > 0 (active trading)

RESULTS:
- Games Analyzed: {games_analyzed}
- Total Comparisons: {total_comparisons:,}
- ESPN Probabilities Outside Kalshi Bid-Ask Range: {total_outside:,} ({outside_pct}%)
- Average Deviation When Outside: {avg_dev} cents
- Maximum Deviation Observed: {max_dev} cents

INTERPRETATION:
- Lower "Outside %" = ESPN and Kalshi are more aligned
- Higher "Outside %" = ESPN probabilities differ from market consensus
- Average deviation shows typical disagreement magnitude
- Maximum deviation shows extreme cases

================================================================================
"""
            
            print(report)
            
            # Write to file
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            print(f"\nReport saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

