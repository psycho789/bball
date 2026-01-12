from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.isotonic import IsotonicRegression


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

    def apply(self, p: np.ndarray) -> np.ndarray:
        x = logit(p)
        return sigmoid(self.alpha + self.beta * x)


@dataclass(frozen=True)
class IsotonicCalibrator:
    iso_reg: IsotonicRegression

    def apply(self, p: np.ndarray) -> np.ndarray:
        """Apply isotonic regression calibration to probabilities."""
        # IsotonicRegression expects 1D array
        p_1d = np.asarray(p).flatten()
        calibrated = self.iso_reg.transform(p_1d)
        # Clip to [0, 1] to ensure valid probabilities
        calibrated = np.clip(calibrated, 0.0, 1.0)
        # Return in same shape as input
        return calibrated.reshape(p.shape)


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


def encode_possession(pos: str) -> np.ndarray:
    p = (pos or "").strip().lower()
    if p not in ("home", "away"):
        p = "unknown"
    if p == "home":
        return np.array([1.0, 0.0, 0.0], dtype=np.float64)
    if p == "away":
        return np.array([0.0, 1.0, 0.0], dtype=np.float64)
    return np.array([0.0, 0.0, 1.0], dtype=np.float64)


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
) -> np.ndarray:
    """
    Build design matrix with optional interaction terms.
    
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
    """
    pd_scaled = (point_differential.astype(np.float64) - preprocess.point_diff_mean) / preprocess.point_diff_std
    tr_scaled = (time_remaining_regulation.astype(np.float64) - preprocess.time_rem_mean) / preprocess.time_rem_std
    poss_rows = np.vstack([encode_possession(p) for p in possession])
    
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
        period_array = np.array([int(p) if p is not None and not np.isnan(p) else 0 for p in period], dtype=np.int32)
        period_1 = (period_array == 1).astype(np.float64)
        period_2 = (period_array == 2).astype(np.float64)
        period_3 = (period_array == 3).astype(np.float64)
        period_4 = (period_array == 4).astype(np.float64)
        features.append(np.column_stack([period_1, period_2, period_3, period_4]))
    
    return np.column_stack(features)


def predict_proba(artifact: WinProbArtifact, *, X: np.ndarray) -> np.ndarray:
    """Predict probabilities using either logistic regression or CatBoost model."""
    if artifact.model_type == "catboost" and artifact.catboost_model_path is not None:
        # Use CatBoost model
        from catboost import CatBoostClassifier
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
        model = CatBoostClassifier()
        model.load_model(str(model_path))
        # CatBoost returns probabilities for both classes, we want class 1 (home win)
        p = model.predict_proba(X)[:, 1].astype(np.float64)
    else:
        # Use logistic regression (default)
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
    
    # Fit isotonic regression
    iso_reg = IsotonicRegression(out_of_bounds='clip')
    iso_reg.fit(p_base_1d, y_1d)
    
    return IsotonicCalibrator(iso_reg=iso_reg)


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
                # Serialize isotonic regression: store X_min, X_max, and the piecewise constant function
                "X_min": float(artifact.isotonic.iso_reg.X_min_),
                "X_max": float(artifact.isotonic.iso_reg.X_max_),
                # Store the piecewise constant function as (X_thresholds, y_thresholds)
                "X_thresholds": [float(x) for x in artifact.isotonic.iso_reg.X_thresholds_],
                "y_thresholds": [float(y) for y in artifact.isotonic.iso_reg.y_thresholds_],
                "out_of_bounds": str(artifact.isotonic.iso_reg.out_of_bounds),
            }
        ),
        "model_type": artifact.model_type,
        "catboost_model_path": artifact.catboost_model_path,
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
        # Reconstruct IsotonicRegression from serialized parameters
        out_of_bounds = isotonic_obj.get("out_of_bounds", "clip")
        iso_reg = IsotonicRegression(out_of_bounds=out_of_bounds)
        # Reconstruct by fitting with the stored X_thresholds and y_thresholds
        # This will recreate the piecewise constant function
        X_thresholds = np.array([float(x) for x in isotonic_obj["X_thresholds"]])
        y_thresholds = np.array([float(y) for y in isotonic_obj["y_thresholds"]])
        # Fit with the threshold points to reconstruct the model
        iso_reg.fit(X_thresholds, y_thresholds)
        isotonic = IsotonicCalibrator(iso_reg=iso_reg)
    
    model_type = obj.get("model_type", "logreg")  # Default to logreg for backward compatibility
    catboost_model_path = obj.get("catboost_model_path")
    
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
    )


