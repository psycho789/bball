#!/usr/bin/env python3
"""
Test script for ESPN live API endpoints.

Tests:
1. Scoreboard endpoint for live games detection
2. Probabilities endpoint structure
3. Update frequency (if live game available)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from _fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes


def test_scoreboard(date: str):
    """Test scoreboard endpoint for a given date."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}&limit=1000"
    
    print(f"\n=== Testing Scoreboard Endpoint ===")
    print(f"URL: {url}")
    
    try:
        retry = HttpRetry(timeout_seconds=20.0, max_attempts=3)
        status, headers, body = http_get_bytes(url, retry=retry)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        data = parse_json_bytes(body)
        
        events = data.get("events", [])
        print(f"Total events: {len(events)}")
        
        # Categorize by status
        status_counts = {}
        live_games = []
        
        for event in events:
            status = event.get("status", {})
            status_type = status.get("type", {})
            status_name = status_type.get("name", "UNKNOWN")
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            # Check if live
            if status_name in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_DELAYED"]:
                competitions = event.get("competitions", [])
                if competitions:
                    comp = competitions[0]
                    competitors = comp.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
                    
                    live_games.append({
                        "event_id": event.get("id"),
                        "competition_id": comp.get("id"),
                        "name": event.get("name"),
                        "status": status_name,
                        "home_team": home.get("team", {}).get("displayName"),
                        "away_team": away.get("team", {}).get("displayName"),
                        "home_score": home.get("score"),
                        "away_score": away.get("score"),
                    })
        
        print(f"\nStatus breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        if live_games:
            print(f"\nLive games ({len(live_games)}):")
            for game in live_games:
                print(f"  Event ID: {game['event_id']}, Competition ID: {game['competition_id']}")
                print(f"    {game['away_team']} @ {game['home_team']}")
                print(f"    Score: {game['away_score']} - {game['home_score']}")
                print(f"    Status: {game['status']}")
        else:
            print(f"\nNo live games found for date {date}")
        
        return live_games
            
    except Exception as e:
        print(f"Error: {e}")
        return []


def test_probabilities(event_id: str, competition_id: str):
    """Test probabilities endpoint for a specific game."""
    url = (
        f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
        f"/events/{event_id}/competitions/{competition_id}/probabilities?limit=1000"
    )
    
    print(f"\n=== Testing Probabilities Endpoint ===")
    print(f"URL: {url}")
    print(f"Event ID: {event_id}, Competition ID: {competition_id}")
    
    try:
        retry = HttpRetry(timeout_seconds=20.0, max_attempts=3)
        status, headers, body = http_get_bytes(url, retry=retry)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        data = parse_json_bytes(body)
        
        items = data.get("items", [])
        print(f"Total items: {len(items)}")
        
        if items:
            # Show first and last items
            first = items[0]
            last = items[-1]
            
            print(f"\nFirst item:")
            print(f"  Sequence: {first.get('sequenceNumber')}")
            print(f"  Last Modified: {first.get('lastModified')}")
            print(f"  Home Win %: {first.get('homeWinPercentage')}")
            print(f"  Away Win %: {first.get('awayWinPercentage')}")
            
            print(f"\nLast item:")
            print(f"  Sequence: {last.get('sequenceNumber')}")
            print(f"  Last Modified: {last.get('lastModified')}")
            print(f"  Home Win %: {last.get('homeWinPercentage')}")
            print(f"  Away Win %: {last.get('awayWinPercentage')}")
            
            # Check sequence numbers
            sequences = [item.get("sequenceNumber", 0) for item in items]
            print(f"\nSequence range: {min(sequences)} to {max(sequences)}")
            print(f"Sequence count: {len(set(sequences))} unique")
        
        return items
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_update_frequency(event_id: str, competition_id: str, duration_seconds: int = 60):
    """Test update frequency by polling probabilities endpoint."""
    print(f"\n=== Testing Update Frequency ===")
    print(f"Polling for {duration_seconds} seconds...")
    
    last_sequence = None
    last_count = 0
    updates_seen = 0
    
    start_time = time.time()
    poll_count = 0
    
    while (time.time() - start_time) < duration_seconds:
        items = test_probabilities(event_id, competition_id)
        poll_count += 1
        
        if items:
            current_count = len(items)
            current_sequence = max(item.get("sequenceNumber", 0) for item in items)
            
            if last_sequence is not None:
                if current_sequence > last_sequence:
                    updates_seen += 1
                    print(f"  Poll #{poll_count}: New items detected! Sequence: {last_sequence} -> {current_sequence}")
                elif current_count > last_count:
                    updates_seen += 1
                    print(f"  Poll #{poll_count}: Item count increased! {last_count} -> {current_count}")
            
            last_sequence = current_sequence
            last_count = current_count
        else:
            print(f"  Poll #{poll_count}: No items returned")
        
        time.sleep(5)  # Poll every 5 seconds
    
    print(f"\nUpdate frequency test complete:")
    print(f"  Total polls: {poll_count}")
    print(f"  Updates detected: {updates_seen}")
    if poll_count > 0:
        print(f"  Average time between polls: {duration_seconds / poll_count:.1f} seconds")


def main():
    if len(sys.argv) < 2:
        # Use today's date
        today = datetime.now().strftime("%Y%m%d")
        print(f"Using today's date: {today}")
    else:
        today = sys.argv[1]
    
    # Test 1: Scoreboard
    live_games = test_scoreboard(today)
    
    # Test 2: Probabilities (use first live game, or first game if no live games)
    if live_games:
        game = live_games[0]
        print(f"\nUsing live game: {game['name']}")
        items = test_probabilities(game["event_id"], game["competition_id"])
        
        # Test 3: Update frequency (only if game is live)
        if game["status"] == "STATUS_IN_PROGRESS":
            test_update_frequency(game["event_id"], game["competition_id"], duration_seconds=60)
    else:
        # Test with a known game (from scoreboard)
        print(f"\nNo live games, testing with first available game...")
        # Would need to fetch scoreboard again to get event/competition IDs
        print("Skipping probabilities test (no live game available)")


if __name__ == "__main__":
    main()

