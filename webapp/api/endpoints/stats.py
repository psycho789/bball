"""
Statistics endpoint - calculate data science metrics for games.

Design Pattern: Service Pattern for statistical calculations
Algorithm: Various statistical aggregations and metrics
Big O: O(n) where n = number of probability data points
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
import math
import json
import threading

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger
from .utils import get_cache_ttl_for_game

router = APIRouter()
logger = get_logger(__name__)


def calculate_brier_score(probabilities: list[float], actual_outcome: int) -> float:
    """
    Calculate Brier score (mean squared error of probabilities).
    
    Lower is better (0 = perfect, 1 = worst).
    actual_outcome: 1 if home won, 0 if away won
    """
    if not probabilities:
        return None
    return sum((p - actual_outcome) ** 2 for p in probabilities) / len(probabilities)


def calculate_time_sliced_brier_scores(
    probabilities: list[float],
    timestamps: list[int],
    game_start_timestamp: int,
    actual_outcome: int,
    game_duration_seconds: Optional[int] = None
) -> dict[str, Any]:
    """
    Calculate Brier scores for different time slices of the game.
    
    Time slices:
    - Q1: 0 to 720 seconds (first 12 minutes)
    - Halftime: 0 to 1440 seconds (first 24 minutes)
    - Start of Q4: 0 to 2160 seconds (first 36 minutes)
    - Final 2 minutes: last 120 seconds of the game
    
    Args:
        probabilities: List of home win probabilities (0-1)
        timestamps: List of Unix timestamps (aligned to game timeline)
        game_start_timestamp: Unix timestamp of game start
        actual_outcome: 1 if home won, 0 if away won
        game_duration_seconds: Total game duration in seconds (for final 2 minutes calculation)
    
    Returns:
        Dictionary with Brier scores for each time slice
    """
    if not probabilities or not timestamps or len(probabilities) != len(timestamps):
        return {
            "q1": None,
            "halftime": None,
            "start_q4": None,
            "final_2_minutes": None,
        }
    
    # Calculate elapsed seconds from game start for each probability point
    elapsed_seconds = [(ts - game_start_timestamp) for ts in timestamps]
    
    # Q1: 0 to 720 seconds (first 12 minutes)
    q1_probs = [probabilities[i] for i, elapsed in enumerate(elapsed_seconds) if 0 <= elapsed <= 720]
    q1_brier = calculate_brier_score(q1_probs, actual_outcome) if q1_probs else None
    
    # Halftime: 0 to 1440 seconds (first 24 minutes)
    halftime_probs = [probabilities[i] for i, elapsed in enumerate(elapsed_seconds) if 0 <= elapsed <= 1440]
    halftime_brier = calculate_brier_score(halftime_probs, actual_outcome) if halftime_probs else None
    
    # Start of Q4: 0 to 2160 seconds (first 36 minutes)
    start_q4_probs = [probabilities[i] for i, elapsed in enumerate(elapsed_seconds) if 0 <= elapsed <= 2160]
    start_q4_brier = calculate_brier_score(start_q4_probs, actual_outcome) if start_q4_probs else None
    
    # Final 2 minutes: last 120 seconds of the game
    final_2_min_brier = None
    if game_duration_seconds:
        final_2_min_start = game_duration_seconds - 120
        final_2_min_probs = [
            probabilities[i] 
            for i, elapsed in enumerate(elapsed_seconds) 
            if final_2_min_start <= elapsed <= game_duration_seconds
        ]
        final_2_min_brier = calculate_brier_score(final_2_min_probs, actual_outcome) if final_2_min_probs else None
    else:
        # Fallback: use last 120 seconds from available data
        if elapsed_seconds:
            max_elapsed = max(elapsed_seconds)
            final_2_min_start = max(0, max_elapsed - 120)
            final_2_min_probs = [
                probabilities[i] 
                for i, elapsed in enumerate(elapsed_seconds) 
                if final_2_min_start <= elapsed <= max_elapsed
            ]
            final_2_min_brier = calculate_brier_score(final_2_min_probs, actual_outcome) if final_2_min_probs else None
    
    return {
        "q1": q1_brier,
        "halftime": halftime_brier,
        "start_q4": start_q4_brier,
        "final_2_minutes": final_2_min_brier,
        "data_points": {
            "q1": len(q1_probs),
            "halftime": len(halftime_probs),
            "start_q4": len(start_q4_probs),
            "final_2_minutes": len(final_2_min_probs) if game_duration_seconds or elapsed_seconds else 0,
        }
    }


def calculate_phase_brier_scores(
    probabilities: list[float],
    timestamps: list[int],
    game_start_timestamp: int,
    actual_outcome: int,
    game_duration_seconds: int
) -> dict[str, Optional[float]]:
    """
    Calculate Brier scores for game phases: Early, Mid, Late, Clutch.
    
    Story 3.2: Phase-based Brier calculation for time-sliced performance chart.
    
    Phases:
    - Early: 0-25% of game duration
    - Mid: 25-75% of game duration
    - Late: 75-100% of game duration
    - Clutch: last 2 minutes (120 seconds)
    
    Args:
        probabilities: List of predicted probabilities (0-1)
        timestamps: List of Unix timestamps for each probability
        game_start_timestamp: Unix timestamp of game start
        actual_outcome: 1 if home won, 0 if away won
        game_duration_seconds: Total game duration in seconds
    
    Returns:
        Dictionary with phase names as keys and Brier scores as values
    """
    if not probabilities or not timestamps or len(probabilities) != len(timestamps):
        return {"early": None, "mid": None, "late": None, "clutch": None}
    
    if game_duration_seconds <= 0:
        return {"early": None, "mid": None, "late": None, "clutch": None}
    
    # Calculate elapsed seconds for each timestamp
    elapsed_seconds = [(ts - game_start_timestamp) for ts in timestamps]
    
    # Phase boundaries
    early_end = game_duration_seconds * 0.25
    mid_start = game_duration_seconds * 0.25
    mid_end = game_duration_seconds * 0.75
    late_start = game_duration_seconds * 0.75
    clutch_start = max(0, game_duration_seconds - 120)  # Last 2 minutes
    
    # Filter probabilities by phase
    early_probs = [
        probabilities[i] 
        for i, elapsed in enumerate(elapsed_seconds) 
        if 0 <= elapsed <= early_end
    ]
    
    mid_probs = [
        probabilities[i] 
        for i, elapsed in enumerate(elapsed_seconds) 
        if mid_start < elapsed <= mid_end
    ]
    
    late_probs = [
        probabilities[i] 
        for i, elapsed in enumerate(elapsed_seconds) 
        if late_start < elapsed <= game_duration_seconds
    ]
    
    clutch_probs = [
        probabilities[i] 
        for i, elapsed in enumerate(elapsed_seconds) 
        if clutch_start <= elapsed <= game_duration_seconds
    ]
    
    # Calculate Brier scores for each phase
    early_brier = calculate_brier_score(early_probs, actual_outcome) if early_probs else None
    mid_brier = calculate_brier_score(mid_probs, actual_outcome) if mid_probs else None
    late_brier = calculate_brier_score(late_probs, actual_outcome) if late_probs else None
    clutch_brier = calculate_brier_score(clutch_probs, actual_outcome) if clutch_probs else None
    
    return {
        "early": early_brier,
        "mid": mid_brier,
        "late": late_brier,
        "clutch": clutch_brier,
    }


def calculate_log_loss(probabilities: list[float], actual_outcome: int, epsilon: float = 0.01) -> float:
    """
    Calculate log loss (cross-entropy loss).
    
    Lower is better. Clips probabilities to 0.01-0.99 to avoid log(0) and prevent
    extreme penalties for overconfidence. Log loss heavily punishes confident wrong predictions.
    
    actual_outcome: 1 if home won, 0 if away won
    """
    if not probabilities:
        return None
    # Clip to 0.01-0.99 range to prevent extreme penalties and avoid log(0)
    clipped_probs = [max(epsilon, min(1 - epsilon, p)) for p in probabilities]
    return -sum(
        actual_outcome * math.log(p) + (1 - actual_outcome) * math.log(1 - p)
        for p in clipped_probs
    ) / len(clipped_probs)


def calculate_probability_volatility(probabilities: list[float]) -> float:
    """
    Calculate standard deviation of probability changes (volatility).
    
    Higher = more volatile probability swings.
    """
    if len(probabilities) < 2:
        return 0.0
    changes = [abs(probabilities[i] - probabilities[i-1]) for i in range(1, len(probabilities))]
    if not changes:
        return 0.0
    mean_change = sum(changes) / len(changes)
    variance = sum((c - mean_change) ** 2 for c in changes) / len(changes)
    return math.sqrt(variance)


def calculate_max_probability_swing(probabilities: list[float]) -> dict[str, float]:
    """
    Calculate maximum probability swing (biggest change in either direction).
    """
    if not probabilities:
        return {"max_increase": None, "max_decrease": None, "max_swing": None}
    
    max_increase = 0.0
    max_decrease = 0.0
    
    for i in range(1, len(probabilities)):
        change = probabilities[i] - probabilities[i-1]
        if change > 0:
            max_increase = max(max_increase, change)
        else:
            max_decrease = min(max_decrease, change)
    
    return {
        "max_increase": max_increase,
        "max_decrease": abs(max_decrease),
        "max_swing": max(max_increase, abs(max_decrease)),
    }


def calculate_lead_changes(probabilities: list[float]) -> int:
    """
    Count how many times the favorite changed (probability crossed 50%).
    """
    if len(probabilities) < 2:
        return 0
    
    changes = 0
    was_home_favorite = probabilities[0] > 0.5
    
    for prob in probabilities[1:]:
        is_home_favorite = prob > 0.5
        if is_home_favorite != was_home_favorite:
            changes += 1
            was_home_favorite = is_home_favorite
    
    return changes


def calculate_standard_deviation(probabilities: list[float]) -> float:
    """
    Calculate standard deviation of probabilities themselves.
    
    Measures how spread out the probability values are around the mean.
    """
    if len(probabilities) < 2:
        return 0.0
    mean = sum(probabilities) / len(probabilities)
    variance = sum((p - mean) ** 2 for p in probabilities) / len(probabilities)
    return math.sqrt(variance)


def calculate_variance(probabilities: list[float]) -> float:
    """
    Calculate variance of probabilities.
    
    Variance is the square of standard deviation.
    """
    if len(probabilities) < 2:
        return 0.0
    mean = sum(probabilities) / len(probabilities)
    return sum((p - mean) ** 2 for p in probabilities) / len(probabilities)


def calculate_mean_absolute_deviation(probabilities: list[float]) -> float:
    """
    Calculate Mean Absolute Deviation (MAD).
    
    Average of absolute differences from the mean.
    More robust to outliers than standard deviation.
    """
    if not probabilities:
        return 0.0
    mean = sum(probabilities) / len(probabilities)
    return sum(abs(p - mean) for p in probabilities) / len(probabilities)


def calculate_coefficient_of_variation(probabilities: list[float]) -> Optional[float]:
    """
    Calculate Coefficient of Variation (CV).
    
    Standard deviation divided by mean. Measures relative variability.
    Returns None if mean is zero.
    """
    if not probabilities:
        return None
    mean = sum(probabilities) / len(probabilities)
    if mean == 0:
        return None
    std_dev = calculate_standard_deviation(probabilities)
    return std_dev / mean


def calculate_time_weighted_average(probabilities: list[float], timestamps: list[int]) -> float:
    """
    Calculate time-weighted average probability.
    
    Weights later probabilities more heavily (assuming equal time intervals).
    """
    if not probabilities or len(probabilities) != len(timestamps):
        return None
    
    if len(probabilities) == 1:
        return probabilities[0]
    
    # Simple linear weighting (later = higher weight)
    weights = [i / len(probabilities) for i in range(len(probabilities))]
    weighted_sum = sum(p * w for p, w in zip(probabilities, weights))
    weight_sum = sum(weights)
    
    return weighted_sum / weight_sum if weight_sum > 0 else None


def calculate_extreme_probability_rate(probabilities: list[float]) -> Optional[float]:
    """
    Calculate % of timestamps where p >= 0.95 or p <= 0.05.
    
    Story 2.4: Extreme probability rate metric.
    Shows how often each source gets very confident.
    
    Args:
        probabilities: List of probabilities (0-1)
    
    Returns:
        Float between 0 and 1 representing the percentage of extreme probabilities,
        or None if no probabilities provided
    """
    if not probabilities:
        return None
    extreme_count = sum(1 for p in probabilities if p >= 0.95 or p <= 0.05)
    return extreme_count / len(probabilities)


def calculate_reliability_curve(
    probabilities: list[float], 
    actual_outcomes: list[int],
    bins: int = 10
) -> dict[str, Any]:
    """
    Calculate reliability curve (calibration curve) for probability predictions.
    
    Groups predictions into bins (e.g., 0-10%, 10-20%, etc.) and compares
    the average predicted probability in each bin to the actual outcome frequency.
    
    Well-calibrated predictions: predicted probability ≈ actual frequency
    Overconfident: predicted probability > actual frequency
    Underconfident: predicted probability < actual frequency
    
    Args:
        probabilities: List of predicted probabilities (0-1)
        actual_outcomes: List of actual outcomes (1 or 0)
        bins: Number of bins to use (default: 10, so 0-10%, 10-20%, ..., 90-100%)
    
    Returns:
        Dictionary with bin information:
        - bins: List of bin dictionaries with:
          - bin_min, bin_max: Probability range for this bin
          - predicted_prob: Average predicted probability in this bin
          - actual_freq: Actual frequency of positive outcomes in this bin
          - count: Number of predictions in this bin
          - calibration_error: predicted_prob - actual_freq (positive = overconfident)
    """
    if not probabilities or len(probabilities) != len(actual_outcomes):
        return {"bins": []}
    
    # Group predictions into bins
    bin_size = 1.0 / bins
    bin_data: dict[int, list[tuple[float, int]]] = {}
    
    for prob, outcome in zip(probabilities, actual_outcomes):
        # Determine which bin this probability falls into
        bin_idx = min(int(prob / bin_size), bins - 1)  # Handle edge case where prob = 1.0
        if bin_idx not in bin_data:
            bin_data[bin_idx] = []
        bin_data[bin_idx].append((prob, outcome))
    
    # Calculate statistics for each bin
    reliability_bins = []
    for bin_idx in range(bins):
        bin_min = bin_idx * bin_size
        bin_max = (bin_idx + 1) * bin_size if bin_idx < bins - 1 else 1.0
        
        if bin_idx in bin_data:
            probs_in_bin, outcomes_in_bin = zip(*bin_data[bin_idx])
            predicted_prob = sum(probs_in_bin) / len(probs_in_bin)
            actual_freq = sum(outcomes_in_bin) / len(outcomes_in_bin)
            count = len(probs_in_bin)
            calibration_error = predicted_prob - actual_freq
        else:
            predicted_prob = (bin_min + bin_max) / 2.0  # Bin center
            actual_freq = None
            count = 0
            calibration_error = None
        
        reliability_bins.append({
            "bin_min": bin_min,
            "bin_max": bin_max,
            "bin_center": (bin_min + bin_max) / 2.0,
            "predicted_prob": predicted_prob,
            "actual_freq": actual_freq,
            "count": count,
            "calibration_error": calibration_error,
        })
    
    return {"bins": reliability_bins}


def calculate_decision_weighted_metrics(
    espn_probs: list[float],
    kalshi_probs: list[float],
    kalshi_times: list[int],
    kalshi_bid_ask_exists: list[bool],  # Whether bid/ask data exists at each point
    actual_outcome: Optional[int],
    game_start_timestamp: Optional[int] = None,
    game_duration_seconds: Optional[int] = None
) -> dict[str, Any]:
    """
    Calculate decision-weighted metrics that focus on when money is at stake.
    
    These metrics answer: "Who is more accurate when money is at stake?"
    rather than "Who is more accurate over the entire game?"
    
    Metrics:
    1. Time-weighted Brier: Only score when Kalshi bid/ask exists (market is active)
    2. Distance-weighted errors: Weight errors by distance from 0.5 (more weight on uncertain predictions)
    3. EV-positive disagreement events: Track when ESPN and Kalshi disagree and one has positive EV
    
    Args:
        espn_probs: ESPN home win probabilities
        kalshi_probs: Kalshi home win probabilities (aligned with espn_probs)
        kalshi_times: Timestamps for Kalshi data points
        kalshi_bid_ask_exists: Boolean list indicating if bid/ask data exists (market is active)
        actual_outcome: 1 if home won, 0 if away won, None if unknown
        game_start_timestamp: Unix timestamp of game start (for time weighting)
        game_duration_seconds: Total game duration in seconds (for time weighting)
    
    Returns:
        Dictionary with decision-weighted metrics
    """
    if not espn_probs or not kalshi_probs or len(espn_probs) != len(kalshi_probs):
        return {
            "time_weighted_brier_espn": None,
            "time_weighted_brier_kalshi": None,
            "distance_weighted_mae": None,
            "ev_positive_disagreements": None,
        }
    
    # Filter to only points where Kalshi market is active (bid/ask exists)
    active_points = [
        (espn, kalshi, time, has_bid_ask)
        for espn, kalshi, time, has_bid_ask in zip(
            espn_probs, kalshi_probs, kalshi_times, kalshi_bid_ask_exists
        )
        if has_bid_ask
    ]
    
    if not active_points:
        return {
            "time_weighted_brier_espn": None,
            "time_weighted_brier_kalshi": None,
            "distance_weighted_mae": None,
            "ev_positive_disagreements": None,
            "active_points_count": 0,
        }
    
    espn_active, kalshi_active, times_active, _ = zip(*active_points)
    
    # 1. Time-weighted Brier (only when market is active) - Market-actionable variant
    time_weighted_brier_espn = None
    time_weighted_brier_kalshi = None
    
    # 1b. Confidence-weighted Brier (w_t = abs(p_t - 0.5)) - Story 4.1 Variant 1
    confidence_weighted_brier_espn = None
    confidence_weighted_brier_kalshi = None
    
    if actual_outcome is not None:
        # Calculate time weights (later in game = higher weight)
        if game_start_timestamp and game_duration_seconds:
            elapsed_seconds = [(t - game_start_timestamp) for t in times_active]
            # Weight by elapsed time (later = more important)
            time_weights = [elapsed / game_duration_seconds for elapsed in elapsed_seconds]
        else:
            # Equal weights if we don't have game timing
            time_weights = [1.0] * len(espn_active)
        
        # Normalize weights
        weight_sum = sum(time_weights)
        if weight_sum > 0:
            normalized_weights = [w / weight_sum for w in time_weights]
            
            # Time-weighted Brier for ESPN (Market-actionable variant)
            espn_errors = [(p - actual_outcome) ** 2 for p in espn_active]
            time_weighted_brier_espn = sum(e * w for e, w in zip(espn_errors, normalized_weights))
            
            # Time-weighted Brier for Kalshi (Market-actionable variant)
            kalshi_errors = [(p - actual_outcome) ** 2 for p in kalshi_active]
            time_weighted_brier_kalshi = sum(e * w for e, w in zip(kalshi_errors, normalized_weights))
        
        # Confidence-weighted Brier (Variant 1: w_t = abs(p_t - 0.5))
        # More weight on confident predictions (further from 0.5)
        confidence_weights_espn = [abs(p - 0.5) for p in espn_active]
        confidence_weights_kalshi = [abs(p - 0.5) for p in kalshi_active]
        
        weight_sum_espn = sum(confidence_weights_espn)
        weight_sum_kalshi = sum(confidence_weights_kalshi)
        
        if weight_sum_espn > 0:
            normalized_weights_espn = [w / weight_sum_espn for w in confidence_weights_espn]
            espn_errors = [(p - actual_outcome) ** 2 for p in espn_active]
            confidence_weighted_brier_espn = sum(e * w for e, w in zip(espn_errors, normalized_weights_espn))
        
        if weight_sum_kalshi > 0:
            normalized_weights_kalshi = [w / weight_sum_kalshi for w in confidence_weights_kalshi]
            kalshi_errors = [(p - actual_outcome) ** 2 for p in kalshi_active]
            confidence_weighted_brier_kalshi = sum(e * w for e, w in zip(kalshi_errors, normalized_weights_kalshi))
    
    # 2. Distance-weighted MAE (weight errors by distance from 0.5)
    # Predictions near 0.5 are more uncertain, so disagreements matter more
    distance_from_50 = [abs(0.5 - (espn + kalshi) / 2.0) for espn, kalshi in zip(espn_active, kalshi_active)]
    # Weight: closer to 0.5 = higher weight (inverse of distance)
    max_distance = max(distance_from_50) if distance_from_50 else 0.5
    if max_distance > 0:
        # Normalize: weight = 1 - (distance / max_distance)
        # This gives weight 1.0 at 0.5, decreasing to 0 at extremes
        weights = [1.0 - (d / max_distance) for d in distance_from_50]
        weight_sum = sum(weights)
        if weight_sum > 0:
            normalized_weights = [w / weight_sum for w in weights]
            mae_values = [abs(espn - kalshi) for espn, kalshi in zip(espn_active, kalshi_active)]
            distance_weighted_mae = sum(m * w for m, w in zip(mae_values, normalized_weights))
        else:
            distance_weighted_mae = None
    else:
        distance_weighted_mae = None
    
    # 3. EV-positive disagreement events
    # Track when ESPN and Kalshi disagree significantly and one has positive expected value
    ev_positive_count = 0
    ev_positive_details = []
    
    if actual_outcome is not None:
        for espn, kalshi in zip(espn_active, kalshi_active):
            disagreement = abs(espn - kalshi)
            # Significant disagreement threshold: > 10%
            if disagreement > 0.10:
                # Calculate EV for each prediction
                # EV = (probability * payout_if_win) - (1 - probability) * cost
                # Assuming even-money bet (1:1 odds)
                espn_ev = (espn * 1.0) - ((1 - espn) * 1.0)  # Simplified: prob - (1-prob) = 2*prob - 1
                kalshi_ev = (kalshi * 1.0) - ((1 - kalshi) * 1.0)
                
                # Check if one has positive EV and the other doesn't
                espn_positive = espn_ev > 0
                kalshi_positive = kalshi_ev > 0
                
                if espn_positive != kalshi_positive:
                    ev_positive_count += 1
                    ev_positive_details.append({
                        "espn_prob": espn,
                        "kalshi_prob": kalshi,
                        "disagreement": disagreement,
                        "espn_ev": espn_ev,
                        "kalshi_ev": kalshi_ev,
                        "correct_prediction": "espn" if (espn > 0.5) == (actual_outcome == 1) else "kalshi" if (kalshi > 0.5) == (actual_outcome == 1) else "neither",
                    })
    
    return {
        "time_weighted_brier_espn": time_weighted_brier_espn,
        "time_weighted_brier_kalshi": time_weighted_brier_kalshi,
        "confidence_weighted_brier_espn": confidence_weighted_brier_espn,  # Story 4.1 Variant 1
        "confidence_weighted_brier_kalshi": confidence_weighted_brier_kalshi,  # Story 4.1 Variant 1
        "distance_weighted_mae": distance_weighted_mae,
        "ev_positive_disagreements": {
            "count": ev_positive_count,
            "details": ev_positive_details[:10] if ev_positive_details else [],  # Limit to first 10 for size
        } if ev_positive_count > 0 else None,
        "active_points_count": len(active_points),
    }


def calculate_profit_proxy(
    espn_probs: list[float],
    kalshi_probs: list[float],
    outcomes: list[int],
    threshold: float = 0.05
) -> dict[str, Any]:
    """
    Calculate profit proxy metrics (sanity check, not full backtest).
    
    Story 4.2: Optional profit proxy to identify potential betting edges.
    
    Tracks signal events where ESPN and Kalshi disagree significantly (>= threshold),
    and calculates win rates when one has positive expected value.
    
    NOTE: This is a sanity check only, not a full backtest. It doesn't account for:
    - Betting limits
    - Market impact
    - Transaction costs
    - Timing of bets
    
    Args:
        espn_probs: ESPN home win probabilities
        kalshi_probs: Kalshi home win probabilities (aligned with espn_probs)
        outcomes: Actual outcomes (1 if home won, 0 if away won)
        threshold: Minimum disagreement to count as signal event (default: 0.05 = 5%)
    
    Returns:
        Dictionary with profit proxy metrics
    """
    if not espn_probs or not kalshi_probs or len(espn_probs) != len(kalshi_probs):
        return {
            "signal_event_count": 0,
            "win_rate_positive_edge": None,
            "win_rate_negative_edge": None,
        }
    
    if len(outcomes) != len(espn_probs):
        return {
            "signal_event_count": 0,
            "win_rate_positive_edge": None,
            "win_rate_negative_edge": None,
        }
    
    signal_events = []
    for espn, kalshi, outcome in zip(espn_probs, kalshi_probs, outcomes):
        edge = espn - kalshi  # Signed difference
        if abs(edge) >= threshold:
            signal_events.append((edge, outcome))
    
    if not signal_events:
        return {
            "signal_event_count": 0,
            "win_rate_positive_edge": None,
            "win_rate_negative_edge": None,
        }
    
    # Separate by positive vs negative edge
    positive_edge_events = [(e, o) for e, o in signal_events if e > 0]  # ESPN higher than Kalshi
    negative_edge_events = [(e, o) for e, o in signal_events if e < 0]  # ESPN lower than Kalshi
    
    win_rate_positive = None
    if positive_edge_events:
        # When ESPN > Kalshi, we'd bet on home team (assuming ESPN is right)
        wins = sum(o for _, o in positive_edge_events)
        win_rate_positive = wins / len(positive_edge_events)
    
    win_rate_negative = None
    if negative_edge_events:
        # When ESPN < Kalshi, we'd bet on away team (assuming ESPN is right)
        # Outcome is for home team, so we need to flip it
        wins = sum(1 - o for _, o in negative_edge_events)  # Away wins = 1 - home wins
        win_rate_negative = wins / len(negative_edge_events)
    
    return {
        "signal_event_count": len(signal_events),
        "win_rate_positive_edge": win_rate_positive,
        "win_rate_negative_edge": win_rate_negative,
    }


def calculate_correlation(espn_probs: list[float], kalshi_probs: list[float]) -> Optional[float]:
    """
    Calculate Pearson correlation coefficient between two probability series.
    
    Returns None if insufficient data or zero variance.
    """
    if len(espn_probs) != len(kalshi_probs) or len(espn_probs) < 2:
        return None
    
    mean_espn = sum(espn_probs) / len(espn_probs)
    mean_kalshi = sum(kalshi_probs) / len(kalshi_probs)
    
    numerator = sum((e - mean_espn) * (k - mean_kalshi) for e, k in zip(espn_probs, kalshi_probs))
    espn_var = sum((e - mean_espn) ** 2 for e in espn_probs)
    kalshi_var = sum((k - mean_kalshi) ** 2 for k in kalshi_probs)
    
    if espn_var > 0 and kalshi_var > 0:
        return numerator / math.sqrt(espn_var * kalshi_var)
    return None


def calculate_time_sliced_correlations(
    aligned_pairs_with_times: list[tuple[float, float, int]],
    game_start_timestamp: int,
    game_duration_seconds: Optional[int] = None
) -> dict[str, Any]:
    """
    Calculate correlation between ESPN and Kalshi probabilities for different game phases.
    
    Time slices:
    - Q1-Q2: 0 to 1440 seconds (first 24 minutes)
    - Q3: 1440 to 2160 seconds (24-36 minutes)
    - Q4: 2160 to 2880 seconds (36-48 minutes)
    - Final 2 minutes: last 120 seconds of the game
    
    Args:
        aligned_pairs_with_times: List of (espn_prob, kalshi_prob, timestamp) tuples
        game_start_timestamp: Unix timestamp of game start
        game_duration_seconds: Total game duration in seconds (for final 2 minutes calculation)
    
    Returns:
        Dictionary with correlations for each time slice
    """
    if not aligned_pairs_with_times:
        return {
            "q1_q2": None,
            "q3": None,
            "q4": None,
            "final_2_minutes": None,
        }
    
    # Calculate elapsed seconds from game start for each pair
    pairs_with_elapsed = [
        (espn_prob, kalshi_prob, ts - game_start_timestamp)
        for espn_prob, kalshi_prob, ts in aligned_pairs_with_times
    ]
    
    # Q1-Q2: 0 to 1440 seconds (first 24 minutes)
    q1_q2_pairs = [
        (e, k) for e, k, elapsed in pairs_with_elapsed
        if 0 <= elapsed <= 1440
    ]
    q1_q2_correlation = None
    if len(q1_q2_pairs) >= 2:
        espn_q1_q2, kalshi_q1_q2 = zip(*q1_q2_pairs)
        q1_q2_correlation = calculate_correlation(list(espn_q1_q2), list(kalshi_q1_q2))
    
    # Q3: 1440 to 2160 seconds (24-36 minutes)
    q3_pairs = [
        (e, k) for e, k, elapsed in pairs_with_elapsed
        if 1440 < elapsed <= 2160
    ]
    q3_correlation = None
    if len(q3_pairs) >= 2:
        espn_q3, kalshi_q3 = zip(*q3_pairs)
        q3_correlation = calculate_correlation(list(espn_q3), list(kalshi_q3))
    
    # Q4: 2160 to 2880 seconds (36-48 minutes)
    q4_pairs = [
        (e, k) for e, k, elapsed in pairs_with_elapsed
        if 2160 < elapsed <= 2880
    ]
    q4_correlation = None
    if len(q4_pairs) >= 2:
        espn_q4, kalshi_q4 = zip(*q4_pairs)
        q4_correlation = calculate_correlation(list(espn_q4), list(kalshi_q4))
    
    # Final 2 minutes: last 120 seconds of the game
    final_2_min_correlation = None
    if game_duration_seconds:
        final_2_min_start = game_duration_seconds - 120
        final_2_min_pairs = [
            (e, k) for e, k, elapsed in pairs_with_elapsed
            if final_2_min_start <= elapsed <= game_duration_seconds
        ]
        if len(final_2_min_pairs) >= 2:
            espn_final, kalshi_final = zip(*final_2_min_pairs)
            final_2_min_correlation = calculate_correlation(list(espn_final), list(kalshi_final))
    else:
        # Fallback: use last 120 seconds from available data
        if pairs_with_elapsed:
            max_elapsed = max(elapsed for _, _, elapsed in pairs_with_elapsed)
            final_2_min_start = max(0, max_elapsed - 120)
            final_2_min_pairs = [
                (e, k) for e, k, elapsed in pairs_with_elapsed
                if final_2_min_start <= elapsed <= max_elapsed
            ]
            if len(final_2_min_pairs) >= 2:
                espn_final, kalshi_final = zip(*final_2_min_pairs)
                final_2_min_correlation = calculate_correlation(list(espn_final), list(kalshi_final))
    
    return {
        "q1_q2": q1_q2_correlation,
        "q3": q3_correlation,
        "q4": q4_correlation,
        "final_2_minutes": final_2_min_correlation,
        "data_points": {
            "q1_q2": len(q1_q2_pairs),
            "q3": len(q3_pairs),
            "q4": len(q4_pairs),
            "final_2_minutes": len(final_2_min_pairs) if game_duration_seconds or pairs_with_elapsed else 0,
        }
    }


def calculate_espn_kalshi_divergence(
    espn_probs: list[float], 
    kalshi_probs: list[float], 
                                     espn_times: list[int], kalshi_times: list[int],
                                     game_start_timestamp: Optional[int] = None,
                                     game_duration_seconds: Optional[int] = None) -> dict[str, Any]:
    """
    Calculate divergence metrics between ESPN and Kalshi probabilities.
    
    Story 4.3: Alignment Window Logic Documentation
    
    This function aligns ESPN and Kalshi probability data points by matching timestamps.
    The alignment uses a nearest-neighbor matching algorithm with a time window constraint.
    
    Alignment Algorithm:
    1. For each ESPN timestamp, find the nearest Kalshi timestamp
    2. Match only if the time difference is <= 60 seconds (alignment window)
    3. Use a single-pass algorithm that maintains a pointer into the Kalshi array
    4. For each ESPN point, advance the Kalshi pointer until we find the closest match
    
    Alignment Window: 60 seconds (1 minute)
    - This window accounts for:
      * Different update frequencies (ESPN may update every few seconds, Kalshi every minute)
      * Clock synchronization differences
      * Network latency in data collection
    - Points outside this window are not matched (considered misaligned)
    
    Alignment Rate: The percentage of ESPN points that successfully match a Kalshi point
    - Calculated as: aligned_points / total_espn_points
    - Typically 80-95% for games with good data coverage
    - Lower rates may indicate:
      * Sparse Kalshi data
      * Time synchronization issues
      * Different game timelines
    
    Data Points Returned:
    - Returns the count of successfully aligned pairs in the "data_points" field
    - This count is used for data coverage metrics (Story 2.1)
    
    Time-Sliced Calculations:
    - After alignment, timestamps are used to slice data by game phase
    - ESPN timestamps are used as the reference (aligned to game timeline)
    - This ensures phase boundaries are consistent with game clock
    
    Args:
        espn_probs: ESPN home win probabilities
        kalshi_probs: Kalshi home win probabilities
        espn_times: Unix timestamps for ESPN probabilities
        kalshi_times: Unix timestamps for Kalshi probabilities
        game_start_timestamp: Optional Unix timestamp of game start (for time-sliced calculations)
        game_duration_seconds: Optional game duration in seconds (for time-sliced calculations)
    
    Returns:
        Dictionary with divergence metrics including:
        - mean_absolute_difference: Average disagreement between ESPN and Kalshi
        - max_absolute_difference: Maximum disagreement in any aligned pair
        - correlation: Pearson correlation coefficient
        - correlation_time_sliced: Correlations by game phase (Q1-Q2, Q3, Q4, Final 2 min)
        - sign_flips: Count of times ESPN and Kalshi moved in opposite directions
        - data_points: Number of successfully aligned pairs (for alignment rate calculation)
    """
    if not espn_probs or not kalshi_probs:
        return {
            "mean_absolute_difference": None,
            "max_absolute_difference": None,
            "correlation": None,
            "correlation_time_sliced": {
                "q1_q2": None,
                "q3": None,
                "q4": None,
                "final_2_minutes": None,
            },
            "sign_flips": None,
            "data_points": 0,
        }
    
    # Create aligned pairs with timestamps (simple nearest-neighbor matching)
    aligned_pairs_with_times = []
    kalshi_idx = 0
    
    for i, espn_time in enumerate(espn_times):
        # Find closest Kalshi timestamp
        while kalshi_idx < len(kalshi_times) - 1 and abs(kalshi_times[kalshi_idx] - espn_time) > abs(kalshi_times[kalshi_idx + 1] - espn_time):
            kalshi_idx += 1
        
        if kalshi_idx < len(kalshi_times):
            time_diff = abs(kalshi_times[kalshi_idx] - espn_time)
            # Only match if within 60 seconds
            if time_diff <= 60:
                # Use ESPN timestamp for time-sliced calculations (aligned to game timeline)
                aligned_pairs_with_times.append((espn_probs[i], kalshi_probs[kalshi_idx], espn_time))
    
    if not aligned_pairs_with_times:
        return {
            "mean_absolute_difference": None,
            "max_absolute_difference": None,
            "correlation": None,
            "correlation_time_sliced": {
                "q1_q2": None,
                "q3": None,
                "q4": None,
                "final_2_minutes": None,
            },
            "sign_flips": None,
            "data_points": 0,
        }
    
    # Extract pairs for overall calculations
    aligned_pairs = [(e, k) for e, k, _ in aligned_pairs_with_times]
    espn_aligned, kalshi_aligned = zip(*aligned_pairs)
    differences = [abs(e - k) for e, k in aligned_pairs]
    
    # Calculate sign flips (ESPN ↑ while Kalshi ↓ or vice versa)
    # Story 2.3: Use epsilon threshold (0.005 = 0.5 percentage points) to filter noise
    sign_flips = 0
    epsilon = 0.005  # Configurable threshold for noise filtering
    if len(aligned_pairs) > 1:
        for i in range(1, len(aligned_pairs)):
            prev_espn, prev_kalshi = aligned_pairs[i-1]
            curr_espn, curr_kalshi = aligned_pairs[i]
            espn_change = curr_espn - prev_espn
            kalshi_change = curr_kalshi - prev_kalshi
            
            # Only count if both deltas exceed epsilon (filter noise)
            if abs(espn_change) > epsilon and abs(kalshi_change) > epsilon:
                # Sign flip: one goes up while the other goes down
                if (espn_change > 0 and kalshi_change < 0) or (espn_change < 0 and kalshi_change > 0):
                    sign_flips += 1
    
    # Calculate overall correlation
    correlation = calculate_correlation(list(espn_aligned), list(kalshi_aligned))
    
    # Calculate time-sliced correlations
    correlation_time_sliced = {
        "q1_q2": None,
        "q3": None,
        "q4": None,
        "final_2_minutes": None,
    }
    if game_start_timestamp is not None:
        correlation_time_sliced = calculate_time_sliced_correlations(
            aligned_pairs_with_times,
            game_start_timestamp,
            game_duration_seconds
        )
    
    return {
        "mean_absolute_difference": sum(differences) / len(differences),
        "max_absolute_difference": max(differences),
        "correlation": correlation,
        "correlation_time_sliced": correlation_time_sliced,
        "sign_flips": sign_flips,
        "data_points": len(aligned_pairs),
    }


def _is_game_completed(conn, game_id: str) -> bool:
    """Check if a game is completed (has final scores)."""
    check_sql = """
    SELECT MAX(e.home_score) as final_home_score, MAX(e.away_score) as final_away_score
    FROM espn.prob_event_state e
    WHERE e.game_id = %s
    """
    row = conn.execute(check_sql, (game_id,)).fetchone()
    return row and row[0] is not None and row[1] is not None


def _get_stats_from_db(conn, game_id: str) -> Optional[dict[str, Any]]:
    """Retrieve stats from database if they exist."""
    sql = """
    SELECT 
        espn_stats,
        kalshi_stats,
        divergence_stats,
        season_label,
        home_team_abbrev,
        away_team_abbrev,
        final_home_score,
        final_away_score,
        home_won
    FROM derived.game_stats
    WHERE game_id = %s
    """
    row = conn.execute(sql, (game_id,)).fetchone()
    if row:
        logger.debug(f"Found stats in database for game {game_id}")
        return {
            "game_id": game_id,
            "home_won": row[8],
            "final_score": {
                "home": row[6],
                "away": row[7],
            },
            "espn": row[0],
            "kalshi": row[1],
            "divergence": row[2],
        }
    return None


def _save_stats_to_db(conn, game_id: str, stats: dict[str, Any], game_metadata: dict[str, Any]) -> None:
    """Save calculated stats to database (in background thread to avoid blocking)."""
    import json
    import threading
    
    def _save():
        try:
            with get_db_connection() as save_conn:
                # Use advisory lock to prevent duplicate inserts from concurrent requests
                lock_id = hash(f"game_stats_{game_id}") % (2**31)  # PostgreSQL advisory lock range
                save_conn.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
                try:
                    # Check again if stats were inserted by another request
                    existing = save_conn.execute(
                        "SELECT game_id FROM derived.game_stats WHERE game_id = %s",
                        (game_id,)
                    ).fetchone()
                    
                    if existing:
                        logger.debug(f"Stats already exist in DB for game {game_id}, skipping insert")
                        return
                    
                    insert_sql = """
                    INSERT INTO derived.game_stats (
                        game_id, season_label, home_team_abbrev, away_team_abbrev,
                        final_home_score, final_away_score, home_won,
                        espn_stats, kalshi_stats, divergence_stats
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id) DO UPDATE SET
                        espn_stats = EXCLUDED.espn_stats,
                        kalshi_stats = EXCLUDED.kalshi_stats,
                        divergence_stats = EXCLUDED.divergence_stats,
                        calculated_at = now()
                    """
                    save_conn.execute(insert_sql, (
                        game_id,
                        game_metadata.get("season_label"),
                        game_metadata.get("home_team_abbrev"),
                        game_metadata.get("away_team_abbrev"),
                        stats.get("final_score", {}).get("home"),
                        stats.get("final_score", {}).get("away"),
                        stats.get("home_won"),
                        json.dumps(stats.get("espn", {})),
                        json.dumps(stats.get("kalshi")) if stats.get("kalshi") else None,
                        json.dumps(stats.get("divergence")) if stats.get("divergence") else None,
                    ))
                    save_conn.commit()
                    logger.info(f"Saved stats to database for game {game_id}")
                finally:
                    save_conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
        except Exception as e:
            logger.warning(f"Failed to save stats to database for game {game_id}: {e}", exc_info=True)
    
    # Run save in background thread (non-blocking)
    thread = threading.Thread(target=_save, daemon=True)
    thread.start()


@router.get("/games/{game_id}/stats")
@cached(ttl_seconds=86400 * 365, dynamic_ttl=lambda result: get_cache_ttl_for_game(result))
def get_game_stats(game_id: str) -> dict[str, Any]:
    """
    Calculate comprehensive statistics for a game.
    
    For completed games:
    - First checks database for pre-calculated stats
    - If not found, calculates stats and stores in database (background)
    - Subsequent requests read directly from database
    
    For in-progress games:
    - Calculates stats on-the-fly (not stored in database)
    
    Returns metrics useful for data science analysis:
    - Calibration metrics (Brier score, log loss)
    - Probability volatility and swings
    - Lead changes
    - ESPN vs Kalshi divergence
    - Time-weighted averages
    - Maximum/minimum probabilities
    """
    with get_db_connection() as conn:
        # Check if game is completed
        is_completed = _is_game_completed(conn, game_id)
        
        # For completed games, try to get stats from database first
        if is_completed:
            db_stats = _get_stats_from_db(conn, game_id)
            if db_stats:
                logger.debug(f"Returning stats from database for completed game {game_id}")
                return db_stats
            logger.debug(f"No stats in database for game {game_id}, will calculate and store")
        
        # Calculate stats (either game is in-progress, or stats not in DB yet)
        # Get ESPN probability data
        espn_sql = """
        SELECT 
            p.last_modified_utc,
            p.home_win_percentage,
            p.away_win_percentage,
            sg.home_score as final_home_score,
            sg.away_score as final_away_score,
            MAX(e.final_winning_team) as winner
        FROM espn.probabilities_raw_items p
        LEFT JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
        LEFT JOIN espn.prob_event_state e ON p.game_id = e.game_id
        WHERE p.game_id = %s
        AND p.season_label = '2025-26'
        GROUP BY p.last_modified_utc, p.home_win_percentage, p.away_win_percentage, 
                 sg.home_score, sg.away_score
        ORDER BY p.last_modified_utc ASC
        """
        logger.debug(f"Executing ESPN probabilities query for stats: game_id={game_id}")
        espn_rows = conn.execute(espn_sql, (game_id,)).fetchall()
        logger.debug(f"ESPN probabilities query returned: {len(espn_rows)} rows")
        
        if not espn_rows:
            logger.warning(f"No ESPN probability data found for game {game_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No ESPN probability data for game {game_id}"
            )
        
        logger.debug(f"Processing {len(espn_rows)} ESPN probability points for stats calculation")
        
        # Get game outcome
        first_row = espn_rows[0]
        final_home_score = first_row[3]
        final_away_score = first_row[4]
        winner = first_row[5]
        home_won = winner == 0 if winner is not None else (final_home_score > final_away_score if final_home_score and final_away_score else None)
        
        # Get game start time for time-sliced calculations
        game_start_sql = "SELECT event_date FROM espn.scoreboard_games WHERE event_id = %s LIMIT 1"
        game_start_row = conn.execute(game_start_sql, (game_id,)).fetchone()
        game_start_utc = game_start_row[0] if game_start_row and game_start_row[0] else None
        game_start_timestamp = int(game_start_utc.timestamp()) if game_start_utc else None
        
        # Calculate game duration from ESPN data
        if espn_rows:
            first_timestamp = min(int(row[0].timestamp()) for row in espn_rows if row[0] is not None)
            last_timestamp = max(int(row[0].timestamp()) for row in espn_rows if row[0] is not None)
            # Align timestamps to game timeline
            if game_start_timestamp is not None:
                first_espn_timestamp = first_timestamp
                elapsed_from_first = last_timestamp - first_espn_timestamp
                game_end_timestamp = game_start_timestamp + elapsed_from_first
                game_duration_seconds = int(game_end_timestamp - game_start_timestamp)
            else:
                game_duration_seconds = int(last_timestamp - first_timestamp)
        else:
            game_duration_seconds = None
        
        # Extract ESPN probabilities and timestamps (aligned to game timeline)
        espn_home_probs = []
        espn_away_probs = []
        espn_times = []
        first_espn_timestamp = None
        
        for row in espn_rows:
            last_modified_utc = row[0]
            if last_modified_utc is None:
                continue
            
            espn_recording_timestamp = int(last_modified_utc.timestamp())
            if first_espn_timestamp is None:
                first_espn_timestamp = espn_recording_timestamp
            
            # Align to game timeline (same logic as probabilities endpoint)
            if game_start_timestamp is not None and first_espn_timestamp is not None:
                elapsed_from_first = espn_recording_timestamp - first_espn_timestamp
                aligned_timestamp = game_start_timestamp + elapsed_from_first
            else:
                aligned_timestamp = espn_recording_timestamp
            
            if row[1] is not None:
                espn_home_probs.append(float(row[1]))
                espn_times.append(aligned_timestamp)
            if row[2] is not None:
                espn_away_probs.append(float(row[2]))
        
        # Calculate ESPN stats
        espn_stats = {
            "data_points": len(espn_home_probs),
            "min_probability": min(espn_home_probs) if espn_home_probs else None,
            "max_probability": max(espn_home_probs) if espn_home_probs else None,
            "mean_probability": sum(espn_home_probs) / len(espn_home_probs) if espn_home_probs else None,
            "final_probability": espn_home_probs[-1] if espn_home_probs else None,
            "volatility": calculate_probability_volatility(espn_home_probs),
            "max_swing": calculate_max_probability_swing(espn_home_probs),
            "lead_changes": calculate_lead_changes(espn_home_probs),
            "time_weighted_avg": calculate_time_weighted_average(espn_home_probs, espn_times),
            # Deviation metrics
            "standard_deviation": calculate_standard_deviation(espn_home_probs),
            "variance": calculate_variance(espn_home_probs),
            "mean_absolute_deviation": calculate_mean_absolute_deviation(espn_home_probs),
            "coefficient_of_variation": calculate_coefficient_of_variation(espn_home_probs),
        }
        
        # Add calibration metrics if we know the outcome
        if home_won is not None:
            actual_outcome = 1 if home_won else 0
            brier_score = calculate_brier_score(espn_home_probs, actual_outcome)
            espn_stats["time_averaged_in_game_brier_error"] = brier_score
            espn_stats["log_loss"] = calculate_log_loss(espn_home_probs, actual_outcome)
            espn_stats["prediction_correct"] = (espn_home_probs[-1] > 0.5) == home_won if espn_home_probs else None
            
            # Calculate time-sliced Brier scores
            if game_start_timestamp is not None and espn_times:
                espn_stats["brier_score_time_sliced"] = calculate_time_sliced_brier_scores(
                    espn_home_probs,
                    espn_times,
                    game_start_timestamp,
                    actual_outcome,
                    game_duration_seconds
                )
            else:
                espn_stats["brier_score_time_sliced"] = {
                    "q1": None,
                    "halftime": None,
                    "start_q4": None,
                    "final_2_minutes": None,
                }
        
        # Get Kalshi data if available
        kalshi_sql = """
        WITH espn_game_info AS (
            SELECT 
                sg.event_id,
                sg.event_date as game_start,
                EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as espn_duration_seconds
            FROM espn.scoreboard_games sg
            JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
            WHERE sg.event_id = %s
            GROUP BY sg.event_id, sg.event_date
        ),
        game_markets AS (
            SELECT DISTINCT ON (kmw.ticker)
                kmw.ticker,
                kmw.kalshi_team_side,
                egi.game_start,
                egi.espn_duration_seconds
            FROM kalshi.markets_with_games kmw
            CROSS JOIN espn_game_info egi
            WHERE kmw.espn_event_id = %s
              AND kmw.kalshi_team_side IS NOT NULL
            ORDER BY kmw.ticker, kmw.snapshot_id DESC
        )
        SELECT 
            gm.kalshi_team_side,
            c.period_ts,
            c.price_close,
            c.yes_bid_close,
            c.yes_ask_close
        FROM kalshi.candlesticks c
        JOIN game_markets gm ON c.ticker = gm.ticker
        WHERE (
            c.price_close IS NOT NULL 
            OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL)
        )
        AND c.period_ts >= gm.game_start
        AND c.period_ts <= (gm.game_start + (gm.espn_duration_seconds || ' seconds')::INTERVAL)
        ORDER BY gm.kalshi_team_side, c.period_ts
        """
        logger.debug(f"Executing Kalshi data query for stats: game_id={game_id}")
        kalshi_rows = conn.execute(kalshi_sql, (game_id, game_id)).fetchall()
        logger.debug(f"Kalshi data query returned: {len(kalshi_rows)} rows")
        
        kalshi_stats = None
        divergence_stats = None
        kalshi_home_probs = None  # Initialize to avoid UnboundLocalError
        
        if kalshi_rows:
            logger.debug(f"Processing {len(kalshi_rows)} Kalshi rows for stats calculation...")
            # Group by team side
            kalshi_home_data = [(int(row[1].timestamp()), float(row[2] or (row[3] + row[4]) / 2.0)) 
                                for row in kalshi_rows if row[0] == 'home' and row[1] is not None]
            kalshi_away_data = [(int(row[1].timestamp()), float(row[2] or (row[3] + row[4]) / 2.0)) 
                                for row in kalshi_rows if row[0] == 'away' and row[1] is not None]
            
            # Use home team data for stats (convert from cents to probability)
            if kalshi_home_data:
                kalshi_home_times, kalshi_home_prices = zip(*kalshi_home_data)
                kalshi_home_probs = [p / 100.0 for p in kalshi_home_prices]
                
                # Track bid/ask existence for decision-weighted metrics
                kalshi_bid_ask_exists = [
                    (row[3] is not None and row[4] is not None)
                    for row in kalshi_rows 
                    if row[0] == 'home' and row[1] is not None
                ]
                
                kalshi_stats = {
                    "data_points": len(kalshi_home_probs),
                    "min_probability": min(kalshi_home_probs) if kalshi_home_probs else None,
                    "max_probability": max(kalshi_home_probs) if kalshi_home_probs else None,
                    "mean_probability": sum(kalshi_home_probs) / len(kalshi_home_probs) if kalshi_home_probs else None,
                    "final_probability": kalshi_home_probs[-1] if kalshi_home_probs else None,
                    "volatility": calculate_probability_volatility(kalshi_home_probs),
                    "max_swing": calculate_max_probability_swing(kalshi_home_probs),
                    "lead_changes": calculate_lead_changes(kalshi_home_probs),
                    "time_weighted_avg": calculate_time_weighted_average(kalshi_home_probs, list(kalshi_home_times)),
                    # Deviation metrics
                    "standard_deviation": calculate_standard_deviation(kalshi_home_probs),
                    "variance": calculate_variance(kalshi_home_probs),
                    "mean_absolute_deviation": calculate_mean_absolute_deviation(kalshi_home_probs),
                    "coefficient_of_variation": calculate_coefficient_of_variation(kalshi_home_probs),
                }
                
                # Add calibration metrics if we know the outcome
                if home_won is not None:
                    actual_outcome = 1 if home_won else 0
                    kalshi_brier_score = calculate_brier_score(kalshi_home_probs, actual_outcome)
                    kalshi_stats["time_averaged_in_game_brier_error"] = kalshi_brier_score
                    
                    # Add time-sliced Brier scores for Kalshi
                    if game_start_timestamp is not None:
                        kalshi_stats["brier_score_time_sliced"] = calculate_time_sliced_brier_scores(
                            kalshi_home_probs,
                            list(kalshi_home_times),
                            game_start_timestamp,
                            actual_outcome,
                            game_duration_seconds
                        )
                    else:
                        kalshi_stats["brier_score_time_sliced"] = {
                            "q1": None,
                            "halftime": None,
                            "start_q4": None,
                            "final_2_minutes": None,
                        }
                    
                    # Calculate reliability curve (calibration curve)
                    # Need to create a list of outcomes (same length as probabilities)
                    actual_outcomes_list = [actual_outcome] * len(kalshi_home_probs)
                    kalshi_stats["reliability_curve"] = calculate_reliability_curve(
                        kalshi_home_probs,
                        actual_outcomes_list,
                        bins=10
                    )
                else:
                    kalshi_stats["brier_score_time_sliced"] = {
                        "q1": None,
                        "halftime": None,
                        "start_q4": None,
                        "final_2_minutes": None,
                    }
                
                # Calculate divergence (with time-sliced correlations)
                divergence_stats = calculate_espn_kalshi_divergence(
                    espn_home_probs, kalshi_home_probs,
                    espn_times, list(kalshi_home_times),
                    game_start_timestamp,
                    game_duration_seconds
                )
                
                # Calculate decision-weighted metrics
                # Align ESPN and Kalshi data for decision-weighted metrics
                if len(espn_home_probs) > 0 and len(kalshi_home_probs) > 0:
                    # Create aligned pairs for decision-weighted metrics
                    aligned_espn = []
                    aligned_kalshi = []
                    aligned_kalshi_times = []
                    aligned_bid_ask_exists = []
                    
                    kalshi_idx = 0
                    for i, espn_time in enumerate(espn_times):
                        # Find closest Kalshi timestamp
                        while kalshi_idx < len(kalshi_home_times) - 1 and abs(kalshi_home_times[kalshi_idx] - espn_time) > abs(kalshi_home_times[kalshi_idx + 1] - espn_time):
                            kalshi_idx += 1
                        
                        if kalshi_idx < len(kalshi_home_times):
                            time_diff = abs(kalshi_home_times[kalshi_idx] - espn_time)
                            if time_diff <= 60:  # Within 60 seconds
                                aligned_espn.append(espn_home_probs[i])
                                aligned_kalshi.append(kalshi_home_probs[kalshi_idx])
                                aligned_kalshi_times.append(kalshi_home_times[kalshi_idx])
                                aligned_bid_ask_exists.append(kalshi_bid_ask_exists[kalshi_idx] if kalshi_idx < len(kalshi_bid_ask_exists) else False)
                    
                    if aligned_espn and aligned_kalshi:
                        actual_outcome_for_dw = 1 if home_won else 0 if home_won is not None else None
                        decision_weighted = calculate_decision_weighted_metrics(
                            aligned_espn,
                            aligned_kalshi,
                            aligned_kalshi_times,
                            aligned_bid_ask_exists,
                            actual_outcome_for_dw,
                            game_start_timestamp,
                            game_duration_seconds
                        )
                        divergence_stats["decision_weighted"] = decision_weighted
        
        result = {
            "game_id": game_id,
            "home_won": home_won,
            "final_score": {
                "home": final_home_score,
                "away": final_away_score,
            },
            "espn": espn_stats,
            "kalshi": kalshi_stats,
            "divergence": divergence_stats,
        }
        
        # For completed games, save to database in background (non-blocking)
        if is_completed:
            # Get game metadata for storage
            metadata_sql = """
            SELECT 
                p.season_label,
                sg.home_team_abbrev,
                sg.away_team_abbrev
            FROM espn.probabilities_raw_items p
            JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
            WHERE p.game_id = %s
            AND p.season_label = '2025-26'
            LIMIT 1
            """
            metadata_row = conn.execute(metadata_sql, (game_id,)).fetchone()
            game_metadata = {
                "season_label": metadata_row[0] if metadata_row else None,
                "home_team_abbrev": metadata_row[1] if metadata_row else None,
                "away_team_abbrev": metadata_row[2] if metadata_row else None,
            }
            
            # Save to database in background (non-blocking)
            _save_stats_to_db(conn, game_id, result, game_metadata)
        
        logger.info(f"get_game_stats returning stats for game {game_id}: "
                    f"espn_data_points={espn_stats.get('data_points', 0)}, "
                    f"kalshi_data_points={len(kalshi_home_probs) if kalshi_home_probs is not None else 0}, "
                    f"from_db={False}, is_completed={is_completed}")
        return result


@router.get("/games/stats/bulk")
@cached(ttl_seconds=86400 * 365, dynamic_ttl=lambda result: 86400 * 365)  # Long cache for bulk stats
def get_bulk_game_stats(
    game_ids: str = Query(..., description="Comma-separated list of game IDs"),
) -> dict[str, Any]:
    """
    Get stats for multiple games in a single request.
    
    Useful for fetching stats for all games returned by the games endpoint.
    Each game's stats are individually cached with dynamic TTL (long for completed games).
    
    Args:
        game_ids: Comma-separated list of game IDs (e.g., "401810151,401810152")
    
    Returns:
        Dictionary mapping game_id to stats
    """
    game_id_list = [gid.strip() for gid in game_ids.split(",") if gid.strip()]
    
    if not game_id_list:
        return {}
    
    # Fetch stats for each game (they're individually cached via the get_game_stats function)
    # We bypass the router decorator and call the function directly to reuse its cache
    result = {}
    for game_id in game_id_list:
        try:
            # Call the function directly - it will use its own cache decorator
            stats = get_game_stats(game_id)
            result[game_id] = stats
        except HTTPException:
            # Skip games that don't exist or have no data
            continue
    
    return result


@router.get("/games/stats/summary")
@cached(ttl_seconds=86400)  # Cache for 24 hours (once a day)
def get_games_summary_stats(
    season: str = "2025-26",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get summary statistics across multiple games.
    
    Useful for displaying aggregate metrics on the game list page.
    """
    with get_db_connection() as conn:
        # Get games with basic stats
        sql = """
        WITH game_stats AS (
            SELECT 
                p.game_id,
                COUNT(*) as prob_count,
                MIN(p.home_win_percentage) as min_prob,
                MAX(p.home_win_percentage) as max_prob,
                AVG(p.home_win_percentage) as mean_prob,
                MAX(p.last_modified_utc) - MIN(p.last_modified_utc) as duration
            FROM espn.probabilities_raw_items p
            WHERE p.season_label = %s
            GROUP BY p.game_id
            HAVING COUNT(*) > 100
        ),
        game_outcomes AS (
            SELECT 
                e.game_id,
                MAX(e.home_score) as final_home_score,
                MAX(e.away_score) as final_away_score,
                MAX(e.final_winning_team) as winner
            FROM espn.prob_event_state e
            GROUP BY e.game_id
        )
        SELECT 
            g.game_id,
            g.prob_count,
            g.min_prob,
            g.max_prob,
            g.mean_prob,
            EXTRACT(EPOCH FROM g.duration)::INTEGER as duration_seconds,
            o.final_home_score,
            o.final_away_score,
            o.winner
        FROM game_stats g
        LEFT JOIN game_outcomes o ON g.game_id = o.game_id
        WHERE o.final_home_score IS NOT NULL
        ORDER BY g.prob_count DESC
        LIMIT %s
        """
        rows = conn.execute(sql, (season, limit)).fetchall()
        
        if not rows:
            return {
                "total_games": 0,
                "avg_data_points": 0,
                "avg_volatility": 0,
                "avg_brier_score": 0,
            }
        
        # Calculate aggregate stats
        total_games = len(rows)
        total_data_points = sum(row[1] for row in rows)
        avg_data_points = total_data_points / total_games if total_games > 0 else 0
        
        # Calculate volatility for each game (simplified - using range as proxy)
        volatilities = []
        brier_scores = []
        
        for row in rows:
            min_prob = float(row[2]) if row[2] is not None else 0.5
            max_prob = float(row[3]) if row[3] is not None else 0.5
            mean_prob = float(row[4]) if row[4] is not None else 0.5
            home_won = row[8] == 0 if row[8] is not None else None
            
            # Simple volatility proxy (range)
            volatility = max_prob - min_prob
            volatilities.append(volatility)
            
            # Brier score (using mean probability as proxy)
            if home_won is not None:
                brier = (mean_prob - (1 if home_won else 0)) ** 2
                brier_scores.append(brier)
        
        return {
            "total_games": total_games,
            "avg_data_points": avg_data_points,
            "avg_volatility": sum(volatilities) / len(volatilities) if volatilities else 0,
            "avg_brier_score": sum(brier_scores) / len(brier_scores) if brier_scores else None,
        }

