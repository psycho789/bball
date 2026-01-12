#!/usr/bin/env python3
"""
Visualize comparison between raw ESPN probabilities, model base probabilities, and Platt-calibrated probabilities.

This script:
- Loads evaluation data from ESPN tables
- Extracts raw ESPN probabilities
- Calculates model base probabilities (without Platt calibration)
- Calculates Platt-calibrated probabilities (with Platt calibration)
- Generates reliability diagrams and scatter plots comparing all three sources

Usage:
  ./.venv/bin/python scripts/utils/visualize_probability_comparison.py \
    --artifact artifacts/winprob_logreg_v4_historical.json \
    --season-start 2024 \
    --out data/reports/probability_comparison_2024
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    build_design_matrix,
    ece_binned,
    load_artifact,
    predict_proba,
)
from scripts.model.evaluate_winprob_model import _load_evaluation_data, _write_calibration_svg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualize probability comparison: ESPN vs. model vs. Platt-calibrated")
    p.add_argument("--artifact", required=True, help="Artifact JSON path.")
    p.add_argument("--dsn", help="Database connection string (or use DATABASE_URL env var)")
    p.add_argument("--season-start", type=int, required=True, help="Season_start to evaluate (e.g. 2024).")
    p.add_argument("--out", required=True, help="Output base path (without extension).")
    p.add_argument("--bins", type=int, default=20, help="Bins for ECE/reliability (default: 20).")
    p.add_argument("--sample-size", type=int, default=10000, help="Sample size for scatter plots (default: 10000).")
    return p.parse_args()


def _calculate_calibration_bins(p: np.ndarray, y: np.ndarray, bins: int) -> list[dict]:
    """Calculate calibration bins for reliability diagram."""
    idx = np.minimum(bins - 1, np.maximum(0, np.floor(p * bins).astype(np.int32)))
    calib_rows = []
    for b in range(bins):
        mask = idx == b
        nb = int(np.sum(mask))
        if nb <= 0:
            continue
        avg_p = float(np.mean(p[mask]))
        obs = float(np.mean(y[mask]))
        lo = b / bins
        hi = (b + 1) / bins
        calib_rows.append({
            "bin": int(b),
            "range": [float(lo), float(hi)],
            "n": int(nb),
            "avg_p": avg_p,
            "obs_rate": obs,
            "gap": float(obs - avg_p)
        })
    return calib_rows


def _write_scatter_svg(
    *,
    espn_probs: np.ndarray,
    base_probs: np.ndarray,
    platt_probs: np.ndarray,
    y: np.ndarray,
    out_path: Path,
    title: str,
    sample_size: int = 10000,
) -> None:
    """Write scatter plot comparing ESPN, base, and Platt probabilities."""
    # Sample if too many points
    n = len(espn_probs)
    if n > sample_size:
        indices = np.random.choice(n, size=sample_size, replace=False)
        espn_probs = espn_probs[indices]
        base_probs = base_probs[indices]
        platt_probs = platt_probs[indices]
        y = y[indices]
    
    w = 1200
    h = 400
    pad_l = 70
    pad_r = 20
    pad_t = 50
    pad_b = 65
    plot_w = (w - pad_l - pad_r - 40) / 3  # Three plots with gaps
    plot_h = h - pad_t - pad_b
    
    def x_px(x: float, plot_idx: int) -> float:
        offset = pad_l + plot_idx * (plot_w + 20)
        return offset + max(0.0, min(1.0, x)) * plot_w
    
    def y_px(y: float) -> float:
        return pad_t + (1.0 - max(0.0, min(1.0, y))) * plot_h
    
    def esc(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
    
    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    parts.append(
        f'<text x="{w/2:.1f}" y="28" text-anchor="middle" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="18" fill="#111">'
        f"{esc(title)}</text>"
    )
    
    # Plot frames
    plot_titles = ["Raw ESPN", "Model Base", "Platt-Calibrated"]
    plot_data = [espn_probs, base_probs, platt_probs]
    
    for plot_idx in range(3):
        offset_x = pad_l + plot_idx * (plot_w + 20)
        parts.append(
            f'<rect x="{offset_x}" y="{pad_t}" width="{plot_w}" height="{plot_h}" '
            'fill="#ffffff" stroke="#111" stroke-width="1"/>'
        )
        
        # Grid
        for i in range(0, 11):
            t = i / 10.0
            xx = x_px(t, plot_idx)
            yy = y_px(t)
            parts.append(
                f'<line x1="{xx:.2f}" y1="{pad_t}" x2="{xx:.2f}" y2="{pad_t+plot_h}" '
                'stroke="#eee" stroke-width="1"/>'
            )
            parts.append(
                f'<line x1="{offset_x}" y1="{yy:.2f}" x2="{offset_x+plot_w}" y2="{yy:.2f}" '
                'stroke="#eee" stroke-width="1"/>'
            )
        
        # Perfect calibration diagonal
        parts.append(
            f'<line x1="{x_px(0, plot_idx):.2f}" y1="{y_px(0):.2f}" '
            f'x2="{x_px(1, plot_idx):.2f}" y2="{y_px(1):.2f}" '
            'stroke="#888" stroke-width="2" stroke-dasharray="6,6"/>'
        )
        
        # Scatter points
        probs = plot_data[plot_idx]
        for i in range(len(probs)):
            px = float(probs[i])
            py = float(y[i])
            color = "#1f77b4" if py == 1.0 else "#ff7f0e"
            opacity = 0.3 if py == 1.0 else 0.3
            parts.append(
                f'<circle cx="{x_px(px, plot_idx):.2f}" cy="{y_px(py):.2f}" r="1.5" '
                f'fill="{color}" opacity="{opacity}"/>'
            )
        
        # Title
        parts.append(
            f'<text x="{offset_x + plot_w/2:.1f}" y="{pad_t - 10}" text-anchor="middle" '
            'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
            f"{esc(plot_titles[plot_idx])}</text>"
        )
        
        # X-axis label (only on bottom plot)
        if plot_idx == 1:
            parts.append(
                f'<text x="{w/2:.1f}" y="{h-22}" text-anchor="middle" '
                'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
                "Predicted P(home win)</text>"
            )
    
    # Y-axis label
    parts.append(
        f'<text x="18" y="{pad_t + plot_h/2:.1f}" transform="rotate(-90 18 {pad_t + plot_h/2:.1f})" '
        'text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Actual home win (1=yes, 0=no)</text>"
    )
    
    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact)
    out_base = Path(args.out)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    dsn = get_dsn(args.dsn)
    
    art = load_artifact(artifact_path)
    
    # Load evaluation data
    ss = int(args.season_start)
    with connect(dsn) as conn:
        df = _load_evaluation_data(conn, ss, art)
    
    df = df[df["final_winning_team"].notna()].copy()
    if len(df) == 0:
        raise SystemExit(f"No rows found for season_start={ss}")
    
    y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)
    
    # Extract raw ESPN probabilities
    if "espn_home_prob" not in df.columns:
        raise SystemExit("espn_home_prob column not found in data. Ensure interaction terms are enabled.")
    espn_probs = df["espn_home_prob"].astype(float).to_numpy()
    espn_probs = np.clip(espn_probs, 0.0, 1.0)  # Ensure valid range
    
    # Build design matrix
    build_matrix_kwargs = {
        "point_differential": df["point_differential"].to_numpy(),
        "time_remaining_regulation": df["time_remaining_regulation"].to_numpy(),
        "possession": df["possession"].astype(str).tolist(),
        "preprocess": art.preprocess,
    }
    
    use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in art.feature_names)
    if use_interaction_terms:
        if "score_diff_div_sqrt_time_remaining" in df.columns:
            build_matrix_kwargs["score_diff_div_sqrt_time_remaining"] = df["score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
        if "espn_home_prob" in df.columns:
            build_matrix_kwargs["espn_home_prob"] = df["espn_home_prob"].astype(float).to_numpy()
        if "espn_home_prob_lag_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_lag_1"] = df["espn_home_prob_lag_1"].astype(float).to_numpy()
        if "espn_home_prob_delta_1" in df.columns:
            build_matrix_kwargs["espn_home_prob_delta_1"] = df["espn_home_prob_delta_1"].astype(float).to_numpy()
        if "period" in df.columns:
            build_matrix_kwargs["period"] = df["period"].astype(int).tolist()
    
    X = build_design_matrix(**build_matrix_kwargs)
    
    # Calculate base probabilities (without Platt calibration)
    # Create temporary artifact without Platt calibration
    from scripts.lib._winprob_lib import WinProbArtifact
    art_base = WinProbArtifact(
        created_at_utc=art.created_at_utc,
        version=art.version,
        train_season_start_max=art.train_season_start_max,
        calib_season_start=art.calib_season_start,
        test_season_start=art.test_season_start,
        buckets_seconds_remaining=art.buckets_seconds_remaining,
        preprocess=art.preprocess,
        feature_names=art.feature_names,
        model=art.model,
        platt=None,  # No Platt calibration
    )
    base_probs = predict_proba(art_base, X=X)
    
    # Calculate Platt-calibrated probabilities
    platt_probs = predict_proba(art, X=X)
    
    # Calculate calibration bins for reliability diagrams
    bins = max(1, int(args.bins))
    espn_calib = _calculate_calibration_bins(espn_probs, y, bins)
    base_calib = _calculate_calibration_bins(base_probs, y, bins)
    platt_calib = _calculate_calibration_bins(platt_probs, y, bins)
    
    # Calculate ECE values
    espn_ece = ece_binned(espn_probs, y, bins=bins)
    base_ece = ece_binned(base_probs, y, bins=bins)
    platt_ece = ece_binned(platt_probs, y, bins=bins)
    
    # Write reliability diagrams
    _write_calibration_svg(
        rows=espn_calib,
        out_path=out_base.with_suffix(".espn_reliability.svg"),
        title=f"Raw ESPN Probabilities — season_start={ss} n={len(df)} ECE={espn_ece:.4f}"
    )
    print(f"Wrote {out_base.with_suffix('.espn_reliability.svg')}")
    
    _write_calibration_svg(
        rows=base_calib,
        out_path=out_base.with_suffix(".base_reliability.svg"),
        title=f"Model Base Probabilities — season_start={ss} n={len(df)} ECE={base_ece:.4f}"
    )
    print(f"Wrote {out_base.with_suffix('.base_reliability.svg')}")
    
    _write_calibration_svg(
        rows=platt_calib,
        out_path=out_base.with_suffix(".platt_reliability.svg"),
        title=f"Platt-Calibrated Probabilities — season_start={ss} n={len(df)} ECE={platt_ece:.4f}"
    )
    print(f"Wrote {out_base.with_suffix('.platt_reliability.svg')}")
    
    # Write scatter plot comparison
    _write_scatter_svg(
        espn_probs=espn_probs,
        base_probs=base_probs,
        platt_probs=platt_probs,
        y=y,
        out_path=out_base.with_suffix(".scatter_comparison.svg"),
        title=f"Probability Comparison — season_start={ss} n={len(df)}",
        sample_size=int(args.sample_size),
    )
    print(f"Wrote {out_base.with_suffix('.scatter_comparison.svg')}")
    
    # Print summary statistics
    print(f"\nSummary Statistics (season_start={ss}, n={len(df)}):")
    print(f"  Raw ESPN ECE: {espn_ece:.6f}")
    print(f"  Base Model ECE: {base_ece:.6f}")
    print(f"  Platt-Calibrated ECE: {platt_ece:.6f}")
    print(f"  Raw ESPN Mean: {np.mean(espn_probs):.6f}")
    print(f"  Base Model Mean: {np.mean(base_probs):.6f}")
    print(f"  Platt-Calibrated Mean: {np.mean(platt_probs):.6f}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

