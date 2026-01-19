#!/usr/bin/env python3
"""
Odds format conversion library for sportsbook odds data.

Converts between American odds and decimal odds formats, and calculates implied probabilities.
Used by ETL pipeline to normalize odds formats for unified storage.

Design Pattern: Utility Functions
Algorithm: O(1) for all conversions
"""

from __future__ import annotations


def american_to_decimal(american: int | float) -> float:
    """
    Convert American odds to decimal odds.
    
    Args:
        american: American odds (e.g., -110, +150)
    
    Returns:
        Decimal odds (e.g., 1.909, 2.50)
    
    Examples:
        >>> round(american_to_decimal(-110), 3)
        1.909
        >>> american_to_decimal(150)
        2.5
        >>> american_to_decimal(-450)
        1.222
    """
    am = float(american)
    
    if am > 0:
        # Positive American odds: decimal = (american / 100) + 1
        decimal = (am / 100.0) + 1.0
    else:
        # Negative American odds: decimal = (100 / abs(american)) + 1
        decimal = (100.0 / abs(am)) + 1.0
    
    return decimal


def decimal_to_american(decimal: float) -> int:
    """
    Convert decimal odds to American odds.
    
    Args:
        decimal: Decimal odds (e.g., 1.91, 2.50)
    
    Returns:
        American odds (e.g., -110, +150)
    
    Examples:
        >>> decimal_to_american(1.91)
        -110
        >>> decimal_to_american(2.5)
        150
        >>> decimal_to_american(1.222)
        -450
    """
    if decimal < 1.0:
        raise ValueError(f"Decimal odds must be >= 1.0, got {decimal}")
    
    if decimal >= 2.0:
        # Decimal >= 2.0: american = (decimal - 1) * 100
        american = int((decimal - 1.0) * 100.0)
    else:
        # Decimal < 2.0: american = -100 / (decimal - 1)
        american = int(-100.0 / (decimal - 1.0))
    
    return american


def calculate_implied_prob(decimal_odds: float) -> float:
    """
    Calculate implied probability from decimal odds.
    
    Args:
        decimal_odds: Decimal odds (e.g., 1.91, 2.50)
    
    Returns:
        Implied probability (0.0 to 1.0)
    
    Examples:
        >>> round(calculate_implied_prob(2.0), 2)
        0.5
        >>> round(calculate_implied_prob(1.91), 3)
        0.524
        >>> round(calculate_implied_prob(3.0), 3)
        0.333
    """
    if decimal_odds <= 0:
        raise ValueError(f"Decimal odds must be > 0, got {decimal_odds}")
    
    implied_prob = 1.0 / decimal_odds
    return implied_prob


def american_to_implied_prob(american: int | float) -> float:
    """
    Calculate implied probability directly from American odds.
    
    Args:
        american: American odds (e.g., -110, +150)
    
    Returns:
        Implied probability (0.0 to 1.0)
    
    Examples:
        >>> round(american_to_implied_prob(-110), 3)
        0.524
        >>> round(american_to_implied_prob(150), 3)
        0.4
    """
    decimal = american_to_decimal(american)
    return calculate_implied_prob(decimal)


if __name__ == "__main__":
    # Test the conversion functions
    test_cases = [
        # (american, expected_decimal, expected_implied_prob)
        (-110, 1.909, 0.524),
        (150, 2.5, 0.4),
        (-450, 1.222, 0.818),
        (100, 2.0, 0.5),
        (-200, 1.5, 0.667),
    ]
    
    print("Testing odds conversion:")
    for american, expected_decimal, expected_implied_prob in test_cases:
        decimal = american_to_decimal(american)
        implied_prob = american_to_implied_prob(american)
        american_back = decimal_to_american(decimal)
        
        decimal_ok = abs(decimal - expected_decimal) < 0.01
        prob_ok = abs(implied_prob - expected_implied_prob) < 0.01
        roundtrip_ok = abs(american_back - american) <= 1  # Allow 1 unit difference due to rounding
        
        status = "✓" if (decimal_ok and prob_ok and roundtrip_ok) else "✗"
        print(f"{status} American {american:4d} -> Decimal {decimal:.3f} (expected {expected_decimal:.3f}), "
              f"Implied Prob {implied_prob:.3f} (expected {expected_implied_prob:.3f}), "
              f"Roundtrip {american_back} (expected {american})")

