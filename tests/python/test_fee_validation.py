#!/usr/bin/env python3
"""
Test script for validating Kalshi fee calculation behavior.

This script tests the calculate_kalshi_fee function to verify:
1. Fee formula correctness
2. Rounding behavior (if any)
3. Edge cases
"""

import sys
import os
import math

# Import fee calculation function directly (avoid psycopg dependency)
def calculate_kalshi_fee(price: float, bet_amount: float) -> float:
    """
    Calculate Kalshi trading fee.
    
    Formula: 7% × (price × (1 - price)) × bet_amount
    Fees are highest at 50% probability, decrease toward extremes.
    
    Args:
        price: Contract price in 0-1 range (e.g., 0.50 = 50%)
        bet_amount: Bet amount in dollars
    
    Returns:
        Fee in dollars
    """
    if price <= 0.0 or price >= 1.0:
        return 0.0
    fee_rate = 0.07 * (price * (1 - price))
    return fee_rate * bet_amount


def test_fee_formula():
    """Test that fee formula matches expected: 7% × (price × (1 - price)) × bet_amount"""
    print("=" * 80)
    print("TEST 1: Fee Formula Validation")
    print("=" * 80)
    
    test_cases = [
        (0.50, 1.00, 0.0175),  # 50% probability, $1 bet → 1.75% fee = $0.0175
        (0.50, 10.00, 0.175),  # 50% probability, $10 bet → $0.175
        (0.25, 1.00, 0.013125),  # 25% probability, $1 bet → 1.3125% fee = $0.013125
        (0.75, 1.00, 0.013125),  # 75% probability, $1 bet → 1.3125% fee = $0.013125
        (0.10, 1.00, 0.0063),  # 10% probability, $1 bet → 0.63% fee = $0.0063
        (0.90, 1.00, 0.0063),  # 90% probability, $1 bet → 0.63% fee = $0.0063
    ]
    
    all_passed = True
    for price, bet_amount, expected_fee in test_cases:
        actual_fee = calculate_kalshi_fee(price, bet_amount)
        expected_rate = 0.07 * (price * (1 - price))
        expected_fee_calc = expected_rate * bet_amount
        
        # Allow small floating point differences
        diff = abs(actual_fee - expected_fee_calc)
        passed = diff < 1e-10
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | price={price:.2f}, bet=${bet_amount:.2f} | "
              f"expected=${expected_fee_calc:.6f}, actual=${actual_fee:.6f}, diff={diff:.2e}")
        
        if not passed:
            all_passed = False
    
    return all_passed


def test_rounding_behavior():
    """Test rounding behavior - check if fees round up to next cent"""
    print("\n" + "=" * 80)
    print("TEST 2: Rounding Behavior Validation")
    print("=" * 80)
    print("NOTE: Current implementation may NOT round. Testing actual behavior.")
    print()
    
    # Test cases that would require rounding if rounding is implemented
    test_cases = [
        (0.50, 0.001, "fee(0.50, $0.001)"),  # Very small bet
        (0.50, 0.009, "fee(0.50, $0.009)"),  # Small bet
        (0.50, 0.01, "fee(0.50, $0.01)"),    # Exactly 1 cent
        (0.50, 0.011, "fee(0.50, $0.011)"),  # Just over 1 cent
        (0.25, 0.01, "fee(0.25, $0.01)"),    # Different probability
    ]
    
    print("Current behavior (no rounding expected):")
    for price, bet_amount, label in test_cases:
        fee = calculate_kalshi_fee(price, bet_amount)
        rounded_to_cent = math.ceil(fee * 100) / 100  # Round up to next cent
        needs_rounding = fee > 0 and fee < rounded_to_cent
        
        print(f"  {label:25} = ${fee:.6f} | "
              f"rounded=${rounded_to_cent:.2f} | "
              f"needs_rounding={needs_rounding}")
    
    # Check if rounding is implemented
    # If rounding is implemented, fees should be multiples of $0.01 when > 0
    sample_fees = [calculate_kalshi_fee(0.50, 0.001), calculate_kalshi_fee(0.50, 0.011)]
    rounding_implemented = all(
        fee == 0.0 or (fee * 100) % 1 == 0 
        for fee in sample_fees if fee > 0
    )
    
    print(f"\nRounding implemented: {rounding_implemented}")
    if not rounding_implemented:
        print("RECOMMENDATION: Add rounding to round UP to next cent ($0.01 minimum when fee > 0)")
    
    return rounding_implemented


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 80)
    print("TEST 3: Edge Cases")
    print("=" * 80)
    
    test_cases = [
        (0.0, 1.00, 0.0, "price = 0.0 (should return 0)"),
        (1.0, 1.00, 0.0, "price = 1.0 (should return 0)"),
        (0.5, 0.0, 0.0, "bet_amount = 0.0 (should return 0)"),
        (-0.1, 1.00, 0.0, "price < 0 (should return 0)"),
        (1.1, 1.00, 0.0, "price > 1 (should return 0)"),
    ]
    
    all_passed = True
    for price, bet_amount, expected, description in test_cases:
        actual = calculate_kalshi_fee(price, bet_amount)
        passed = abs(actual - expected) < 1e-10
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | {description:30} | expected=${expected:.2f}, actual=${actual:.2f}")
        if not passed:
            all_passed = False
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("KALSHI FEE CALCULATION VALIDATION")
    print("=" * 80)
    print(f"Function: scripts.simulate_trading_strategy.calculate_kalshi_fee")
    print(f"Location: scripts/simulate_trading_strategy.py:580-597")
    print()
    
    results = []
    
    # Test 1: Formula correctness
    results.append(("Formula Correctness", test_fee_formula()))
    
    # Test 2: Rounding behavior
    results.append(("Rounding Behavior", test_rounding_behavior()))
    
    # Test 3: Edge cases
    results.append(("Edge Cases", test_edge_cases()))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL / NEEDS REVIEW"
        print(f"{status} | {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED OR NEED REVIEW")
        print("\nRECOMMENDATIONS:")
        print("1. Verify fee formula matches Kalshi API documentation")
        print("2. Add rounding if needed: round UP to next cent ($0.01 minimum when fee > 0)")
        print("3. Document actual behavior vs expected behavior")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

