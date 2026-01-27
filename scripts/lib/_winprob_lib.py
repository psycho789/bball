from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.isotonic import IsotonicRegression

# Module-level cache for CatBoost models (keyed by absolute model path)
_catboost_model_cache: dict[str, Any] = {}


def utc_now_iso_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sigmoid(x: np.ndarray) -> np.ndarray:
    # Stable sigmoid for vector input.
    out = np.empty_like(x, dtype=np.float64)
    pos = x >= 0
    neg = ~pos
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ex = np.exp(x[neg])
    out[neg] = ex / (1.0 + ex)
    return out


def clamp01(p: np.ndarray, eps: float = 1e-15) -> np.ndarray:
    return np.clip(p, eps, 1.0 - eps)


def logit(p: np.ndarray, eps: float = 1e-15) -> np.ndarray:
    pp = clamp01(p, eps=eps)
    return np.log(pp / (1.0 - pp))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def logloss(p: np.ndarray, y: np.ndarray) -> float:
    pp = clamp01(p)
    return float(-np.mean(y * np.log(pp) + (1.0 - y) * np.log(1.0 - pp)))


def roc_auc(p: np.ndarray, y: np.ndarray) -> float | None:
    """
    AUC using rank statistics.
    Returns None if y has only one class.
    """
    y0 = (y == 0)
    y1 = (y == 1)
    n0 = int(np.sum(y0))
    n1 = int(np.sum(y1))
    if n0 == 0 or n1 == 0:
        return None

    # Rank by p ascending; tie-handled by average ranks.
    order = np.argsort(p, kind="mergesort")
    ps = p[order]
    ys = y[order]

    ranks = np.empty_like(ps, dtype=np.float64)
    i = 0
    r = 1.0
    while i < len(ps):
        j = i + 1
        while j < len(ps) and ps[j] == ps[i]:
            j += 1
        # average rank for ties in [i, j)
        avg = (r + (r + (j - i) - 1.0)) / 2.0
        ranks[i:j] = avg
        r += (j - i)
        i = j

    sum_ranks_pos = float(np.sum(ranks[ys == 1]))
    # Mann–Whitney U for positives
    u1 = sum_ranks_pos - (n1 * (n1 + 1) / 2.0)
    return float(u1 / (n0 * n1))


def ece_binned(p: np.ndarray, y: np.ndarray, *, bins: int) -> float | None:
    if bins <= 0 or len(p) == 0:
        return None
    bins = int(bins)
    idx = np.minimum(bins - 1, np.maximum(0, np.floor(p * bins).astype(np.int32)))
    ece = 0.0
    n = float(len(p))
    for b in range(bins):
        mask = idx == b
        nb = int(np.sum(mask))
        if nb <= 0:
            continue
        pb = float(np.mean(p[mask]))
        yb = float(np.mean(y[mask]))
        ece += (nb / n) * abs(yb - pb)
    return float(ece)


@dataclass(frozen=True)
class PreprocessParams:
    point_diff_mean: float
    point_diff_std: float
    time_rem_mean: float
    time_rem_std: float
    # Interaction terms normalization (optional, for extended model)
    score_diff_div_sqrt_time_rem_mean: float | None = None
    score_diff_div_sqrt_time_rem_std: float | None = None
    espn_home_prob_mean: float | None = None
    espn_home_prob_std: float | None = None
    espn_home_prob_lag_1_mean: float | None = None
    espn_home_prob_lag_1_std: float | None = None
    espn_home_prob_delta_1_mean: float | None = None
    espn_home_prob_delta_1_std: float | None = None
    # REMOVED: opening_prob_home_fair_time_weighted normalization params (feature removed to prevent double-feeding)
    # encoder categories are fixed by contract
    possession_categories: tuple[str, str, str] = ("home", "away", "unknown")


@dataclass(frozen=True)
class ModelParams:
    # weights correspond to feature_names in artifact metadata
    weights: list[float]
    intercept: float
    l2_lambda: float
    max_iter: int
    tol: float


@dataclass(frozen=True)
class PlattCalibrator:
    alpha: float
    beta: float

    def apply_on_logits(self, logits: np.ndarray) -> np.ndarray:
        """Apply Platt scaling to logits directly.
        
        Use this when you fit on logits (e.g., CatBoost raw margins or total_logits).
        """
        return sigmoid(self.alpha + self.beta * logits)

    def apply(self, p: np.ndarray) -> np.ndarray:
        """Apply Platt scaling to probabilities.
        
        Converts probabilities to logits internally, then applies scaling.
        Equivalent to apply_on_logits(logit(p)).
        """
        return self.apply_on_logits(logit(p))


@dataclass(frozen=True)
class IsotonicCalibrator:
    """Isotonic calibration using piecewise linear interpolation.
    
    Stores the calibration function as threshold arrays for correct serialization.
    Uses np.interp() instead of sklearn for roundtrip-safe apply().
    """
    X_thresholds: np.ndarray  # Input probability thresholds (sorted ascending)
    y_thresholds: np.ndarray  # Output calibrated values at thresholds
    X_min: float  # Minimum X value seen during fit
    X_max: float  # Maximum X value seen during fit
    out_of_bounds: str = "clip"  # How to handle values outside [X_min, X_max]

    def apply(self, p: np.ndarray) -> np.ndarray:
        """Apply isotonic regression calibration to probabilities.
        
        Uses piecewise linear interpolation (np.interp) for correct roundtrip behavior.
        """
        p_1d = np.asarray(p, dtype=np.float64).flatten()
        
        # Handle out-of-bounds values
        if self.out_of_bounds == "clip":
            p_clipped = np.clip(p_1d, self.X_min, self.X_max)
        elif self.out_of_bounds == "nan":
            p_clipped = p_1d.copy()
            p_clipped[(p_1d < self.X_min) | (p_1d > self.X_max)] = np.nan
        else:  # "raise" or unknown - use clip as safe default
            p_clipped = np.clip(p_1d, self.X_min, self.X_max)
        
        # Piecewise linear interpolation (same as sklearn's transform internally)
        calibrated = np.interp(p_clipped, self.X_thresholds, self.y_thresholds)
        
        # Clip to [0, 1] to ensure valid probabilities
        calibrated = np.clip(calibrated, 0.0, 1.0)
        
        # Return in same shape as input
        return calibrated.reshape(p.shape)
    
    @classmethod
    def from_sklearn(cls, iso_reg: IsotonicRegression) -> "IsotonicCalibrator":
        """Create from a fitted sklearn IsotonicRegression."""
        return cls(
            X_thresholds=np.asarray(iso_reg.X_thresholds_, dtype=np.float64),
            y_thresholds=np.asarray(iso_reg.y_thresholds_, dtype=np.float64),
            X_min=float(iso_reg.X_min_),
            X_max=float(iso_reg.X_max_),
            out_of_bounds=str(iso_reg.out_of_bounds),
        )


@dataclass(frozen=True)
class WinProbArtifact:
    created_at_utc: str
    version: str
    train_season_start_max: int
    calib_season_start: int | None
    test_season_start: int
    buckets_seconds_remaining: list[int]
    preprocess: PreprocessParams
    feature_names: list[str]
    model: ModelParams  # For logistic regression
    platt: PlattCalibrator | None
    isotonic: IsotonicCalibrator | None
    model_type: str = "logreg"  # "logreg" or "catboost"
    catboost_model_path: str | None = None  # Path to CatBoost .cbm file relative to artifact directory
    uses_opening_odds_baseline: bool | None = None  # Explicit flag for CatBoost baseline usage (None = old artifact, use heuristic)


# Raw odds fields loaded from database (for data pipeline use)
ODDS_RAW_FIELDS = [
    'opening_prob_home_fair',  # Used as CatBoost baseline, not a feature
    'opening_overround',
    'opening_spread',  # Removed from model features (redundant)
    'opening_total',  # Removed from model features (redundant)
    'has_opening_moneyline',
    'has_opening_spread',
    'has_opening_total',
]

# Model feature names for opening odds (what's actually in X)
# NOTE: opening_prob_home_fair used as CatBoost baseline (not in X)
# NOTE: opening_spread and opening_total removed (redundant with moneyline)
ODDS_MODEL_FEATURES = [
    'opening_overround',
]

# Legacy alias for backward compatibility
ODDS_FEATURES = ODDS_RAW_FIELDS


def encode_possession(pos: str) -> np.ndarray:
    """Encode single possession value to one-hot array [home, away, unknown]."""
    p = (pos or "").strip().lower()
    if p not in ("home", "away"):
        p = "unknown"
    if p == "home":
        return np.array([1.0, 0.0, 0.0], dtype=np.float64)
    if p == "away":
        return np.array([0.0, 1.0, 0.0], dtype=np.float64)
    return np.array([0.0, 0.0, 1.0], dtype=np.float64)


def encode_possession_vectorized(possession: Iterable[str]) -> np.ndarray:
    """Vectorized possession encoding - much faster than per-row loop.
    
    Args:
        possession: Iterable of possession strings ("home", "away", or other/None)
        
    Returns:
        np.ndarray of shape (n, 3) with one-hot encoded [home, away, unknown]
    """
    # Convert to numpy array of strings
    pos = np.asarray(list(possession) if not isinstance(possession, np.ndarray) else possession, dtype="U")
    
    # Normalize: strip whitespace, lowercase, map invalid to "unknown"
    pos = np.char.strip(pos)
    pos = np.char.lower(pos)
    
    # Map anything not "home" or "away" to "unknown"
    valid_mask = (pos == "home") | (pos == "away")
    pos = np.where(valid_mask, pos, "unknown")
    
    # Create one-hot encoding
    n = len(pos)
    poss_rows = np.zeros((n, 3), dtype=np.float64)
    poss_rows[:, 0] = (pos == "home").astype(np.float64)
    poss_rows[:, 1] = (pos == "away").astype(np.float64)
    poss_rows[:, 2] = (pos == "unknown").astype(np.float64)
    
    return poss_rows


def _safe_int_or_zero(x) -> int:
    """Safely convert value to int, returning 0 for None, NaN, or invalid values.
    
    Handles: None, numpy ints, python ints, floats, and float NaN.
    """
    if x is None:
        return 0
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0
    if np.isnan(xf):
        return 0
    return int(xf)


def compute_opening_odds_features(
    *,
    opening_moneyline_home: float | np.ndarray | None = None,
    opening_moneyline_away: float | np.ndarray | None = None,
    opening_spread: float | np.ndarray | None = None,
    opening_total: float | np.ndarray | None = None,
) -> dict[str, float | np.ndarray]:
    """
    Compute opening odds engineered features from raw odds values.
    
    Converts decimal odds to fair probabilities using de-vigging (removes overround/vig).
    Uses decimal odds format: p = 1 / odds (NOT American format).
    
    Args:
        opening_moneyline_home: Decimal odds for home team (e.g., 1.85, 2.10)
        opening_moneyline_away: Decimal odds for away team (e.g., 1.85, 2.10)
        opening_spread: Opening spread line (e.g., -5.5, +3.0)
        opening_total: Opening total/over-under line (e.g., 220.5, 235.0)
    
    Returns:
        Dictionary with engineered features:
        - opening_prob_home_fair: De-vigged fair probability for home win (0-1, may be NaN)
        - opening_overround: Overround/vig amount (may be NaN)
    
    NOTE: has_opening_moneyline removed (perfectly redundant with opening_overround - both derived from same valid_ml condition)
    NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
    
    Safety Checks:
        - Only computes de-vigging if both moneyline odds present and > 1.0
        - Returns NaNs for missing/invalid odds (CatBoost handles NaNs natively)
    """
    # Handle scalar vs array inputs
    # Use np.isscalar() to correctly identify scalars (not lists/Series which would fail float())
    is_scalar = np.isscalar(opening_moneyline_home) and opening_moneyline_home is not None
    if is_scalar:
        # Convert scalars to arrays for consistent processing
        opening_moneyline_home = np.array([float(opening_moneyline_home)])
        opening_moneyline_away = np.array([float(opening_moneyline_away)]) if opening_moneyline_away is not None else None
        opening_spread = np.array([float(opening_spread)]) if opening_spread is not None else None
        opening_total = np.array([float(opening_total)]) if opening_total is not None else None
        return_scalar = True
    else:
        # Convert to numpy arrays if not already
        if opening_moneyline_home is not None:
            opening_moneyline_home = np.asarray(opening_moneyline_home, dtype=np.float64)
        if opening_moneyline_away is not None:
            opening_moneyline_away = np.asarray(opening_moneyline_away, dtype=np.float64)
        if opening_spread is not None:
            opening_spread = np.asarray(opening_spread, dtype=np.float64)
        if opening_total is not None:
            opening_total = np.asarray(opening_total, dtype=np.float64)
        return_scalar = False
    
    # Determine array length (use first non-None array)
    n = 1
    for arr in [opening_moneyline_home, opening_moneyline_away, opening_spread, opening_total]:
        if arr is not None:
            n = len(arr)
            break
    
    # Initialize features with NaNs
    opening_prob_home_fair = np.full(n, np.nan, dtype=np.float64)
    opening_overround = np.full(n, np.nan, dtype=np.float64)
    
    # Safety check: Only compute de-vigging if both odds present and valid (> 1.0)
    # Decimal odds should be >= 1.01 (1.0 would imply 100% probability, which is invalid)
    if opening_moneyline_home is not None and opening_moneyline_away is not None:
        # Convert to arrays if needed
        ml_home = np.asarray(opening_moneyline_home, dtype=np.float64)
        ml_away = np.asarray(opening_moneyline_away, dtype=np.float64)
        
        # Check validity: both present (not NaN) and > 1.0
        valid_ml = (
            ~np.isnan(ml_home)
            & ~np.isnan(ml_away)
            & (ml_home > 1.0)
            & (ml_away > 1.0)
        )
        
        if np.any(valid_ml):
            # Step 1: Raw implied probabilities (only for valid odds)
            p_home_raw = 1.0 / ml_home[valid_ml]
            p_away_raw = 1.0 / ml_away[valid_ml]
            den = p_home_raw + p_away_raw
            
            # Step 2: Calculate overround (vig) and de-vig to fair probabilities
            opening_overround[valid_ml] = den - 1.0
            opening_prob_home_fair[valid_ml] = p_home_raw / den
        
        # NOTE: has_opening_moneyline removed - perfectly redundant with opening_overround
        # (both derived from same valid_ml condition, so opening_overround IS NOT NULL == has_opening_moneyline == 1)
    
    # NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
    
    # Return scalars if input was scalar
    if return_scalar:
        return {
            "opening_prob_home_fair": float(opening_prob_home_fair[0]) if not np.isnan(opening_prob_home_fair[0]) else np.nan,
            "opening_overround": float(opening_overround[0]) if not np.isnan(opening_overround[0]) else np.nan,
        }
    else:
        return {
            "opening_prob_home_fair": opening_prob_home_fair,
            "opening_overround": opening_overround,
        }


def build_design_matrix(
    *,
    point_differential: np.ndarray,
    time_remaining_regulation: np.ndarray,
    possession: Iterable[str],
    preprocess: PreprocessParams,
    # Optional interaction terms (for extended model)
    score_diff_div_sqrt_time_remaining: np.ndarray | None = None,
    espn_home_prob: np.ndarray | None = None,
    espn_home_prob_lag_1: np.ndarray | None = None,
    espn_home_prob_delta_1: np.ndarray | None = None,
    period: Iterable[int] | None = None,
    # Opening odds features (canonical naming)
    # NOTE: opening_prob_home_fair removed (used as CatBoost baseline instead)
    # NOTE: opening_spread and opening_total removed (redundant features)
    # NOTE: has_opening_moneyline removed (perfectly redundant with opening_overround)
    # NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
    # NOTE: has_opening_spread and has_opening_total parameters kept for backward compatibility with old model artifacts
    opening_overround: np.ndarray | None = None,
    has_opening_spread: np.ndarray | None = None,  # Backward compatibility only - old models may expect this
    has_opening_total: np.ndarray | None = None,  # Backward compatibility only - old models may expect this
    # NaN handling policy for odds features (default "zero" is safer for logreg)
    odds_nan_policy: str = "zero",  # "zero" for logreg (safe default), "keep" for CatBoost (NaN as signal)
) -> np.ndarray:
    """
    Build design matrix with optional interaction terms and opening odds features.
    
    Base features (always included):
    - point_differential_scaled
    - time_remaining_regulation_scaled
    - possession_home, possession_away, possession_unknown
    
    Extended features (if provided):
    - score_diff_div_sqrt_time_remaining_scaled
    - espn_home_prob_scaled
    - espn_home_prob_lag_1_scaled
    - espn_home_prob_delta_1_scaled
    - period_1, period_2, period_3, period_4 (one-hot encoded)
    
    Opening odds features (if provided):
    - opening_overround (NaN handling depends on odds_nan_policy)
    
    Args:
        odds_nan_policy: How to handle NaNs in opening_overround.
            - "keep": Keep NaNs (for CatBoost, which uses NaN as signal)
            - "zero": Replace NaNs with 0.0 (for logreg, which can't handle NaNs)
    
    NOTE: opening_prob_home_fair is used as CatBoost baseline (not a feature)
    NOTE: opening_spread and opening_total removed (redundant features)
    """
    # Ensure inputs are arrays (handle scalar inputs gracefully)
    point_differential = np.asarray(point_differential, dtype=np.float64)
    time_remaining_regulation = np.asarray(time_remaining_regulation, dtype=np.float64)
    
    pd_scaled = (point_differential - preprocess.point_diff_mean) / preprocess.point_diff_std
    tr_scaled = (time_remaining_regulation - preprocess.time_rem_mean) / preprocess.time_rem_std
    
    # Use vectorized possession encoding (much faster than per-row loop)
    poss_rows = encode_possession_vectorized(possession)
    
    # Base features: point_diff_scaled, time_rem_scaled, pos_home, pos_away, pos_unknown
    features = [pd_scaled, tr_scaled, poss_rows]
    
    # Add interaction terms if provided
    if score_diff_div_sqrt_time_remaining is not None:
        if preprocess.score_diff_div_sqrt_time_rem_mean is None or preprocess.score_diff_div_sqrt_time_rem_std is None:
            raise ValueError("score_diff_div_sqrt_time_remaining provided but normalization params missing")
        std = preprocess.score_diff_div_sqrt_time_rem_std if preprocess.score_diff_div_sqrt_time_rem_std != 0.0 else 1.0
        scaled = (score_diff_div_sqrt_time_remaining.astype(np.float64) - preprocess.score_diff_div_sqrt_time_rem_mean) / std
        # Handle NaN/None values (fill with 0 for missing interaction terms)
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if espn_home_prob is not None:
        if preprocess.espn_home_prob_mean is None or preprocess.espn_home_prob_std is None:
            raise ValueError("espn_home_prob provided but normalization params missing")
        std = preprocess.espn_home_prob_std if preprocess.espn_home_prob_std != 0.0 else 1.0
        scaled = (espn_home_prob.astype(np.float64) - preprocess.espn_home_prob_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if espn_home_prob_lag_1 is not None:
        if preprocess.espn_home_prob_lag_1_mean is None or preprocess.espn_home_prob_lag_1_std is None:
            raise ValueError("espn_home_prob_lag_1 provided but normalization params missing")
        std = preprocess.espn_home_prob_lag_1_std if preprocess.espn_home_prob_lag_1_std != 0.0 else 1.0
        scaled = (espn_home_prob_lag_1.astype(np.float64) - preprocess.espn_home_prob_lag_1_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if espn_home_prob_delta_1 is not None:
        if preprocess.espn_home_prob_delta_1_mean is None or preprocess.espn_home_prob_delta_1_std is None:
            raise ValueError("espn_home_prob_delta_1 provided but normalization params missing")
        std = preprocess.espn_home_prob_delta_1_std if preprocess.espn_home_prob_delta_1_std != 0.0 else 1.0
        scaled = (espn_home_prob_delta_1.astype(np.float64) - preprocess.espn_home_prob_delta_1_mean) / std
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        features.append(scaled.reshape(-1, 1))
    
    if period is not None:
        # One-hot encode period (1, 2, 3, 4)
        # Use _safe_int_or_zero to handle None, NaN, numpy ints, and invalid values robustly
        period_array = np.fromiter((_safe_int_or_zero(p) for p in period), dtype=np.int32)
        period_1 = (period_array == 1).astype(np.float64)
        period_2 = (period_array == 2).astype(np.float64)
        period_3 = (period_array == 3).astype(np.float64)
        period_4 = (period_array == 4).astype(np.float64)
        features.append(np.column_stack([period_1, period_2, period_3, period_4]))
    
    # Add opening odds features if any are provided
    # NOTE: opening_prob_home_fair removed (used as CatBoost baseline instead)
    # NOTE: opening_spread and opening_total removed (redundant features)
    # NOTE: has_opening_moneyline removed (perfectly redundant with opening_overround)
    # NOTE: has_opening_spread and has_opening_total removed - use only opening_overround
    # Backward compatibility: Check if any opening odds features provided (including old binary flags)
    has_any_odds = any([
        opening_overround is not None,
        has_opening_spread is not None,
        has_opening_total is not None,
    ])
    
    # Validate odds_nan_policy
    if odds_nan_policy not in ("keep", "zero"):
        raise ValueError(f"Invalid odds_nan_policy: {odds_nan_policy!r}. Must be 'keep' or 'zero'.")
    
    if has_any_odds:
        n = len(point_differential)
        odds_features_list = []
        
        if opening_overround is not None:
            ov = np.asarray(opening_overround, dtype=np.float64)
            if odds_nan_policy == "zero":
                # Fill NaNs with 0.0 for logreg safety
                ov = np.nan_to_num(ov, nan=0.0, posinf=0.0, neginf=0.0)
            # "keep" policy: leave NaNs intact (CatBoost uses NaN as signal)
            odds_features_list.append(ov.reshape(-1, 1))
        else:
            # No overround provided - use 0.0 (not NaN) as default since no missingness info
            odds_features_list.append(np.zeros((n, 1), dtype=np.float64))
        
        # Backward compatibility: Add binary flags if provided (for old model artifacts)
        # Only add them if explicitly provided (not None) - new models won't provide them
        if has_opening_spread is not None:
            odds_features_list.append(np.asarray(has_opening_spread, dtype=np.float64).reshape(-1, 1))
        
        if has_opening_total is not None:
            odds_features_list.append(np.asarray(has_opening_total, dtype=np.float64).reshape(-1, 1))
        
        # Stack odds features and append to features list
        odds_block = np.column_stack(odds_features_list)
        features.append(odds_block)
    
    # Reshape 1D arrays to 2D for consistent column_stack behavior
    final_features = []
    for f in features:
        if f.ndim == 1:
            final_features.append(f.reshape(-1, 1))
        else:
            final_features.append(f)
    
    return np.column_stack(final_features)


def predict_proba(
    artifact: WinProbArtifact, 
    *, 
    X: np.ndarray,
    opening_prob_home_fair: np.ndarray | None = None,
) -> np.ndarray:
    """Predict probabilities using either logistic regression or CatBoost model.
    
    CatBoost models are cached at module level to avoid reloading from disk on every call.
    
    Args:
        artifact: Model artifact containing model parameters and metadata
        X: Design matrix (features)
        opening_prob_home_fair: Optional array of opening fair probabilities (for CatBoost baseline)
    
    Returns:
        Array of predicted probabilities (home win probability)
    """
    if artifact.model_type == "catboost" and artifact.catboost_model_path is not None:
        # Use CatBoost model
        from catboost import CatBoostClassifier, Pool
        # Resolve model path relative to artifact location
        model_path = Path(artifact.catboost_model_path)
        if not model_path.is_absolute():
            # Try multiple locations: artifact's directory, data/models, artifacts
            # First, try to get artifact directory from the calling context if available
            # Otherwise, try common locations
            possible_paths = [
                Path("data/models") / model_path,
                Path("artifacts") / model_path,
                model_path,  # Current directory
            ]
            # If we have access to the artifact file path, use that
            # For now, try data/models first (where we save models)
            found = False
            for possible_path in possible_paths:
                if possible_path.exists():
                    model_path = possible_path
                    found = True
                    break
            if not found:
                # Last resort: try data/models (most likely location)
                model_path = Path("data/models") / model_path
        
        # Verify path exists before resolving
        if not model_path.exists():
            raise FileNotFoundError(
                f"CatBoost model file not found: {model_path}\n"
                f"Artifact specified: {artifact.catboost_model_path}\n"
                f"Tried locations: data/models, artifacts, current directory"
            )
        
        # Use absolute path as cache key (use resolve with strict=False for safety)
        try:
            model_path_abs = str(model_path.resolve(strict=True))
        except (OSError, RuntimeError):
            # Fallback: use absolute() if resolve fails
            model_path_abs = str(model_path.absolute())
        
        # Check cache first
        if model_path_abs not in _catboost_model_cache:
            # Load model and cache it
            model = CatBoostClassifier()
            model.load_model(str(model_path))
            _catboost_model_cache[model_path_abs] = model
        else:
            # Use cached model
            model = _catboost_model_cache[model_path_abs]
        
        # CRITICAL FIX: Check if model was trained with baseline
        # Use explicit flag if available, fall back to heuristic for backwards compatibility with older artifacts
        uses_baseline = getattr(artifact, 'uses_opening_odds_baseline', None)
        if uses_baseline is None:
            # Fallback heuristic for older artifacts: check if opening odds features exist but opening_prob_home_fair is not a feature
            has_opening_odds_features = any("opening" in fn.lower() or "overround" in fn.lower() for fn in artifact.feature_names)
            opening_prob_not_a_feature = "opening_prob_home_fair" not in artifact.feature_names
            uses_baseline = has_opening_odds_features and opening_prob_not_a_feature
        
        # Compute baseline if needed (model trained with baseline and we have opening odds data)
        baseline = None
        if uses_baseline:
            # CRITICAL: If model was trained with baseline, opening_prob_home_fair is REQUIRED
            # Fail fast rather than silently degrading performance
            if opening_prob_home_fair is None:
                raise ValueError(
                    f"Model was trained with opening odds baseline (uses_opening_odds_baseline=True), "
                    f"but opening_prob_home_fair was not provided. "
                    f"Required: opening_prob_home_fair (can be inferred from NaN pattern). "
                    f"Without baseline, predictions will be degraded."
                )
            
            # Validate length
            p0_arr = np.asarray(opening_prob_home_fair, dtype=np.float64)
            if len(p0_arr) != len(X):
                raise ValueError(
                    f"Length mismatch: opening_prob_home_fair has {len(p0_arr)} elements, "
                    f"but X has {len(X)} rows."
                )
            baseline = np.zeros(len(X), dtype=np.float64)
            p0 = p0_arr
            # Infer has_odds from opening_prob_home_fair (not NaN = has odds)
            has_odds = ~np.isnan(p0)
            baseline[has_odds] = logit(p0[has_odds])
        
        # Use Pool with baseline if available, otherwise direct prediction
        if baseline is not None:
            pool = Pool(X, baseline=baseline)
            p = model.predict_proba(pool)[:, 1].astype(np.float64)
        else:
            # No baseline (model doesn't use it or baseline data not provided)
            p = model.predict_proba(X)[:, 1].astype(np.float64)
    else:
        # Use logistic regression model
        w = np.asarray(artifact.model.weights, dtype=np.float64)
        logits = X @ w + float(artifact.model.intercept)
        p = sigmoid(logits)
    
    # Apply calibration: isotonic takes precedence if both are present (shouldn't happen, but handle gracefully)
    if artifact.isotonic is not None:
        p = artifact.isotonic.apply(p)
    elif artifact.platt is not None:
        p = artifact.platt.apply(p)
    return p


def fit_logistic_regression_irls(
    *,
    X: np.ndarray,
    y: np.ndarray,
    l2_lambda: float,
    max_iter: int,
    tol: float,
) -> tuple[np.ndarray, float]:
    """
    Fit logistic regression with L2 regularization via IRLS/Newton.

    Model: p = sigmoid(intercept + X @ w)
    Penalty: (l2_lambda/2) * ||w||^2 (intercept is not penalized)
    """
    if X.ndim != 2:
        raise ValueError("X must be 2D")
    if y.ndim != 1:
        raise ValueError("y must be 1D")
    if len(X) != len(y):
        raise ValueError("X and y must have same length")
    if len(X) < 5:
        raise ValueError("need at least 5 rows to fit")

    n, d = X.shape
    lam = max(0.0, float(l2_lambda))
    max_iter = int(max_iter)
    tol = float(tol)

    # Augment with intercept column.
    X1 = np.concatenate([np.ones((n, 1), dtype=np.float64), X.astype(np.float64)], axis=1)
    dd = d + 1

    # Initialize at zeros.
    theta = np.zeros(dd, dtype=np.float64)

    # Penalty matrix: do not penalize intercept.
    P = np.zeros((dd, dd), dtype=np.float64)
    for j in range(1, dd):
        P[j, j] = lam

    for _ in range(max_iter):
        eta = X1 @ theta
        p = sigmoid(eta)
        w = np.maximum(1e-12, p * (1.0 - p))
        z = eta + (y - p) / w

        # Weighted least squares step:
        # (X' W X + P) theta_new = X' W z
        # Implement with explicit diag weights for small d.
        WX = X1 * w[:, None]
        A = (X1.T @ WX) + P
        b = X1.T @ (w * z)

        theta_new = np.linalg.solve(A, b)
        step = theta_new - theta
        theta = theta_new
        if float(np.linalg.norm(step)) < tol:
            break

    intercept = float(theta[0])
    weights = theta[1:]
    return weights, intercept


def fit_platt_calibrator_on_probs(
    *,
    p_base: np.ndarray,
    y: np.ndarray,
    max_iter: int = 50,
    tol: float = 1e-10,
) -> PlattCalibrator | None:
    """
    Fit Platt scaling on logit(p_base):
      logit(Pr(Y=1)) = alpha + beta * logit(p_base)
    via IRLS for a 2-parameter model.
    
    NOTE: For CatBoost models, prefer fit_platt_calibrator_on_raw_margins()
    which fits on raw margins (or total logits when baseline is used).
    """
    if len(p_base) != len(y) or len(y) < 5:
        return None
    x = logit(p_base)

    a = 0.0
    b = 1.0
    for _ in range(int(max_iter)):
        eta = a + b * x
        mu = sigmoid(eta)
        w = np.maximum(1e-12, mu * (1.0 - mu))
        z = eta + (y - mu) / w

        # Solve 2x2 normal equations
        s_w = float(np.sum(w))
        s_wx = float(np.sum(w * x))
        s_wxx = float(np.sum(w * x * x))
        s_wz = float(np.sum(w * z))
        s_wxz = float(np.sum(w * x * z))

        det = s_w * s_wxx - s_wx * s_wx
        if abs(det) < 1e-18:
            return None

        a_new = (s_wz * s_wxx - s_wx * s_wxz) / det
        b_new = (s_w * s_wxz - s_wx * s_wz) / det
        da = a_new - a
        db = b_new - b
        a, b = a_new, b_new
        if math.sqrt(da * da + db * db) < float(tol):
            break

    return PlattCalibrator(alpha=float(a), beta=float(b))


def fit_platt_calibrator_on_raw_margins(
    *,
    raw_margins: np.ndarray,
    y: np.ndarray,
    max_iter: int = 50,
    tol: float = 1e-10,
) -> PlattCalibrator | None:
    """
    Fit Platt scaling on logits (raw CatBoost margins or total logits when baseline is used):
      logit(Pr(Y=1)) = alpha + beta * logits
    via IRLS for a 2-parameter model.
    
    When baseline is used: logits = baseline + raw_margin = logit(p_base)
    When baseline is not used: logits = raw_margin
    
    This produces more stable and interpretable parameters than fitting on probabilities.
    The apply() method uses logit(p_base), which equals the logits we fit on.
    """
    if len(raw_margins) != len(y) or len(y) < 5:
        return None
    # raw_margins parameter name is kept for backward compatibility, but it's actually logits
    # When baseline is used: logits = baseline + raw_margin = logit(p_base)
    # When baseline is not used: logits = raw_margin
    logits = raw_margins.astype(np.float64)
    x = logits
    
    a = 0.0
    b = 1.0
    for _ in range(int(max_iter)):
        eta = a + b * x
        mu = sigmoid(eta)
        w = np.maximum(1e-12, mu * (1.0 - mu))
        z = eta + (y - mu) / w

        # Solve 2x2 normal equations
        s_w = float(np.sum(w))
        s_wx = float(np.sum(w * x))
        s_wxx = float(np.sum(w * x * x))
        s_wz = float(np.sum(w * z))
        s_wxz = float(np.sum(w * x * z))

        det = s_w * s_wxx - s_wx * s_wx
        if abs(det) < 1e-18:
            return None

        a_new = (s_wz * s_wxx - s_wx * s_wxz) / det
        b_new = (s_w * s_wxz - s_wx * s_wz) / det
        da = a_new - a
        db = b_new - b
        a, b = a_new, b_new
        if math.sqrt(da * da + db * db) < float(tol):
            break

    return PlattCalibrator(alpha=float(a), beta=float(b))


def fit_isotonic_calibrator_on_probs(
    *,
    p_base: np.ndarray,
    y: np.ndarray,
) -> IsotonicCalibrator | None:
    """
    Fit isotonic regression calibration on base probabilities.
    
    Isotonic regression fits a piecewise constant non-decreasing function
    to map base probabilities to calibrated probabilities.
    
    Args:
        p_base: Base model probabilities (1D array)
        y: True binary labels (1D array)
    
    Returns:
        IsotonicCalibrator instance or None if insufficient data
    """
    if len(p_base) != len(y) or len(y) < 5:
        return None
    
    p_base_1d = np.asarray(p_base).flatten()
    y_1d = np.asarray(y).flatten()
    
    # Fit isotonic regression using sklearn, then extract thresholds for serialization
    iso_reg = IsotonicRegression(out_of_bounds='clip')
    iso_reg.fit(p_base_1d, y_1d)
    
    # Convert to our threshold-based calibrator for correct roundtrip serialization
    return IsotonicCalibrator.from_sklearn(iso_reg)


def save_artifact(path: Path, artifact: WinProbArtifact) -> None:
    obj: dict[str, Any] = {
        "created_at_utc": artifact.created_at_utc,
        "version": artifact.version,
        "train_season_start_max": artifact.train_season_start_max,
        "calib_season_start": artifact.calib_season_start,
        "test_season_start": artifact.test_season_start,
        "buckets_seconds_remaining": artifact.buckets_seconds_remaining,
        "preprocess": {
            "point_diff_mean": artifact.preprocess.point_diff_mean,
            "point_diff_std": artifact.preprocess.point_diff_std,
            "time_rem_mean": artifact.preprocess.time_rem_mean,
            "time_rem_std": artifact.preprocess.time_rem_std,
            "possession_categories": list(artifact.preprocess.possession_categories),
            "score_diff_div_sqrt_time_rem_mean": artifact.preprocess.score_diff_div_sqrt_time_rem_mean,
            "score_diff_div_sqrt_time_rem_std": artifact.preprocess.score_diff_div_sqrt_time_rem_std,
            "espn_home_prob_mean": artifact.preprocess.espn_home_prob_mean,
            "espn_home_prob_std": artifact.preprocess.espn_home_prob_std,
            "espn_home_prob_lag_1_mean": artifact.preprocess.espn_home_prob_lag_1_mean,
            "espn_home_prob_lag_1_std": artifact.preprocess.espn_home_prob_lag_1_std,
            "espn_home_prob_delta_1_mean": artifact.preprocess.espn_home_prob_delta_1_mean,
            "espn_home_prob_delta_1_std": artifact.preprocess.espn_home_prob_delta_1_std,
        },
        "feature_names": artifact.feature_names,
        "model": {
            "weights": artifact.model.weights,
            "intercept": artifact.model.intercept,
            "l2_lambda": artifact.model.l2_lambda,
            "max_iter": artifact.model.max_iter,
            "tol": artifact.model.tol,
        },
        "platt": (None if artifact.platt is None else {"alpha": artifact.platt.alpha, "beta": artifact.platt.beta}),
        "isotonic": (
            None
            if artifact.isotonic is None
            else {
                # Serialize isotonic calibration thresholds for roundtrip-safe loading
                "X_min": float(artifact.isotonic.X_min),
                "X_max": float(artifact.isotonic.X_max),
                "X_thresholds": [float(x) for x in artifact.isotonic.X_thresholds],
                "y_thresholds": [float(y) for y in artifact.isotonic.y_thresholds],
                "out_of_bounds": str(artifact.isotonic.out_of_bounds),
            }
        ),
        "model_type": artifact.model_type,
        "catboost_model_path": artifact.catboost_model_path,
        "uses_opening_odds_baseline": artifact.uses_opening_odds_baseline,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_artifact(path: Path) -> WinProbArtifact:
    obj = json.loads(path.read_text(encoding="utf-8"))
    preprocess_obj = obj["preprocess"]
    preprocess = PreprocessParams(
        point_diff_mean=float(preprocess_obj["point_diff_mean"]),
        point_diff_std=float(preprocess_obj["point_diff_std"]),
        time_rem_mean=float(preprocess_obj["time_rem_mean"]),
        time_rem_std=float(preprocess_obj["time_rem_std"]),
        possession_categories=tuple(preprocess_obj.get("possession_categories") or ("home", "away", "unknown")),  # type: ignore[arg-type]
        score_diff_div_sqrt_time_rem_mean=float(preprocess_obj["score_diff_div_sqrt_time_rem_mean"]) if preprocess_obj.get("score_diff_div_sqrt_time_rem_mean") is not None else None,
        score_diff_div_sqrt_time_rem_std=float(preprocess_obj["score_diff_div_sqrt_time_rem_std"]) if preprocess_obj.get("score_diff_div_sqrt_time_rem_std") is not None else None,
        espn_home_prob_mean=float(preprocess_obj["espn_home_prob_mean"]) if preprocess_obj.get("espn_home_prob_mean") is not None else None,
        espn_home_prob_std=float(preprocess_obj["espn_home_prob_std"]) if preprocess_obj.get("espn_home_prob_std") is not None else None,
        espn_home_prob_lag_1_mean=float(preprocess_obj["espn_home_prob_lag_1_mean"]) if preprocess_obj.get("espn_home_prob_lag_1_mean") is not None else None,
        espn_home_prob_lag_1_std=float(preprocess_obj["espn_home_prob_lag_1_std"]) if preprocess_obj.get("espn_home_prob_lag_1_std") is not None else None,
        espn_home_prob_delta_1_mean=float(preprocess_obj["espn_home_prob_delta_1_mean"]) if preprocess_obj.get("espn_home_prob_delta_1_mean") is not None else None,
        espn_home_prob_delta_1_std=float(preprocess_obj["espn_home_prob_delta_1_std"]) if preprocess_obj.get("espn_home_prob_delta_1_std") is not None else None,
    )
    model_obj = obj["model"]
    model = ModelParams(
        weights=[float(x) for x in model_obj["weights"]],
        intercept=float(model_obj["intercept"]),
        l2_lambda=float(model_obj["l2_lambda"]),
        max_iter=int(model_obj["max_iter"]),
        tol=float(model_obj["tol"]),
    )
    platt_obj = obj.get("platt")
    platt = None
    if isinstance(platt_obj, dict):
        platt = PlattCalibrator(alpha=float(platt_obj["alpha"]), beta=float(platt_obj["beta"]))
    
    isotonic_obj = obj.get("isotonic")
    isotonic = None
    if isinstance(isotonic_obj, dict):
        # Reconstruct IsotonicCalibrator directly from stored thresholds (no re-fitting!)
        # This ensures exact roundtrip: save → load produces identical calibration function
        isotonic = IsotonicCalibrator(
            X_thresholds=np.array([float(x) for x in isotonic_obj["X_thresholds"]], dtype=np.float64),
            y_thresholds=np.array([float(y) for y in isotonic_obj["y_thresholds"]], dtype=np.float64),
            X_min=float(isotonic_obj["X_min"]),
            X_max=float(isotonic_obj["X_max"]),
            out_of_bounds=str(isotonic_obj.get("out_of_bounds", "clip")),
        )
    
    model_type = obj.get("model_type", "logreg")  # Default to logreg for backward compatibility
    catboost_model_path = obj.get("catboost_model_path")
    # Only set if key exists (None for old artifacts triggers heuristic fallback)
    uses_opening_odds_baseline = obj.get("uses_opening_odds_baseline")  # None if key missing (old artifact)
    
    return WinProbArtifact(
        created_at_utc=str(obj["created_at_utc"]),
        version=str(obj["version"]),
        train_season_start_max=int(obj["train_season_start_max"]),
        calib_season_start=(None if obj.get("calib_season_start") is None else int(obj["calib_season_start"])),
        test_season_start=int(obj["test_season_start"]),
        buckets_seconds_remaining=[int(x) for x in obj["buckets_seconds_remaining"]],
        preprocess=preprocess,
        feature_names=[str(x) for x in obj["feature_names"]],
        model=model,
        platt=platt,
        isotonic=isotonic,
        model_type=str(model_type),
        catboost_model_path=(str(catboost_model_path) if catboost_model_path is not None else None),
        uses_opening_odds_baseline=(bool(uses_opening_odds_baseline) if uses_opening_odds_baseline is not None else None),
    )


