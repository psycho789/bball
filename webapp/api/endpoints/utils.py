"""
Utility functions for endpoints.

Design Pattern: Utility Module Pattern
Algorithm: Helper functions for common operations
Big O: O(1) for most operations
"""

from typing import Any


def is_game_completed(result: dict[str, Any]) -> bool:
    """
    Check if a game is completed based on the API result.
    
    Games are considered completed if they have final scores or a winner.
    """
    # Check for final_winning_team in result
    if "home_won" in result and result["home_won"] is not None:
        return True
    
    # Check for final scores
    if "final_score" in result:
        final_score = result["final_score"]
        if final_score and final_score.get("home") is not None and final_score.get("away") is not None:
            return True
    
    # Check for final_home_score/final_away_score
    if "final_home_score" in result and "final_away_score" in result:
        if result["final_home_score"] is not None and result["final_away_score"] is not None:
            return True
    
    return False


def get_cache_ttl_for_game(result: dict[str, Any], completed_ttl: int = 86400 * 365, in_progress_ttl: int = 300) -> int:
    """
    Get appropriate cache TTL based on game completion status.
    
    Args:
        result: The API result dictionary
        completed_ttl: TTL for completed games (default: 1 year)
        in_progress_ttl: TTL for in-progress games (default: 5 minutes)
    
    Returns:
        TTL in seconds
    """
    if is_game_completed(result):
        return completed_ttl
    return in_progress_ttl

