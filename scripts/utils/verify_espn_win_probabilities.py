#!/usr/bin/env python3
"""
Verify ESPN win probabilities for internal coherence and empirical calibration.

This is NOT "model evaluation vs our model". It's forecast verification vs realized outcomes.

Data sources (two supported modes):
  1) Legacy mode (default):
    - Cached ESPN probabilities JSON:
        data/raw/espn/probabilities/{season_label}/event_{event}_comp_{comp}.json
      (we only use probability numbers and play refs)
    - Derived per-play state table (materialized separately):
        derived.espn_prob_event_state

  2) DB probabilities mode (recommended; avoids derived.espn_prob_event_state):
    - DB probabilities items table:
        derived.espn_probabilities_raw_items
    - Cached ESPN scoreboard JSON (for final outcomes):
        data/raw/espn/scoreboard/scoreboard_{YYYYMMDD}.json

What we check:
  - Hard invariants: 0<=p<=1, sum(p_home,p_away,p_tie)≈1, join coverage.
  - Sampling design (to reduce within-game autocorrelation):
      - anchors (default): choose one play per game nearest to fixed time_remaining anchors
      - random: choose one random play per game
      - all: use all updates (NOT iid; mostly for debugging)
  - Calibration (reliability): in probability bins, observed home-win rate vs predicted p_home.
  - Parametric calibration: logit(Pr(home_win)) = alpha + beta * logit(p_home).
  - Proper scoring rules: Brier score, log loss.
  - Conditional summaries by time remaining bucket and point differential bucket.
  - Cluster bootstrap CIs: resample games with replacement; keep within-game sampling design.

Usage:
  python scripts/verify_espn_win_probabilities.py --dsn "$DATABASE_URL" --season-label 2024-25
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import psycopg
import random

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


PROB_FILE_RE = re.compile(r"^event_(?P<event>\d+)_comp_(?P<comp>\d+)\.json$")


@dataclass(frozen=True)
class ProbItem:
    game_id: str  # ESPN competition id (TEXT)
    play_id: int  # ESPN play id (BIGINT)
    p_home: float | None
    p_away: float | None
    p_tie: float | None
    sequence_number: int | None


@dataclass(frozen=True)
class ObsRow:
    """
    Unit of analysis: one forecast-outcome pair (p_home, y_home_win), plus observable conditioning vars.

    game_id is the clustering unit for inference/bootstrapping.
    """

    game_id: str
    event_id: int
    sequence_number: int | None
    p_home: float
    y_home_win: int
    time_remaining: int | None
    point_differential: int | None
    possession_side: int | None


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_int(x: Any) -> int | None:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return int(x)
        return int(float(x))
    except Exception:
        return None


def _to_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _extract_play_id_from_ref(play_ref: str) -> int | None:
    m = re.search(r"/plays/(\d+)", str(play_ref))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _iter_prob_files(prob_dir: Path) -> list[Path]:
    if not prob_dir.exists():
        return []
    return [p for p in sorted(prob_dir.iterdir()) if p.is_file() and p.name.endswith(".json") and PROB_FILE_RE.match(p.name)]


def _load_prob_items(prob_path: Path) -> list[ProbItem]:
    m = PROB_FILE_RE.match(prob_path.name)
    if not m:
        raise RuntimeError(f"Unexpected probabilities filename: {prob_path.name}")
    game_id = m.group("comp")

    obj = json.loads(prob_path.read_text(encoding="utf-8"))
    items = obj.get("items")
    if not isinstance(items, list):
        return []

    out: list[ProbItem] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        play = it.get("play") or {}
        play_ref = play.get("$ref") if isinstance(play, dict) else None
        if not play_ref:
            continue
        play_id = _extract_play_id_from_ref(str(play_ref))
        if play_id is None:
            continue
        out.append(
            ProbItem(
                game_id=str(game_id),
                play_id=int(play_id),
                p_home=_to_float(it.get("homeWinPercentage")),
                p_away=_to_float(it.get("awayWinPercentage")),
                p_tie=_to_float(it.get("tiePercentage")),
                sequence_number=_to_int(it.get("sequenceNumber")),
            )
        )
    return out


def _bucket_time_remaining(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds <= 60:
        return "0-60"
    if seconds <= 180:
        return "60-180"
    if seconds <= 300:
        return "180-300"
    if seconds <= 600:
        return "300-600"
    if seconds <= 1200:
        return "600-1200"
    if seconds <= 2400:
        return "1200-2400"
    return "2400+"


def _bucket_int(x: int | None, *, width: int) -> int | None:
    if x is None:
        return None
    if width <= 0:
        return int(x)
    # bucket to multiples of width, centered at 0 for negatives
    # e.g. width=2: -1 -> -2, -2 -> -2, 0 -> 0, 1 -> 0, 2 -> 2
    if x >= 0:
        return (x // width) * width
    return -(((-x + width - 1) // width) * width)


def _mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _stddev(xs: list[float]) -> float | None:
    if not xs:
        return None
    if len(xs) == 1:
        return 0.0
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(v)


def _clamp01(p: float, eps: float = 1e-15) -> float:
    if p < eps:
        return eps
    if p > 1.0 - eps:
        return 1.0 - eps
    return p


def _brier(p: float, y: int) -> float:
    return (p - float(y)) ** 2


def _logloss(p: float, y: int) -> float:
    pp = _clamp01(p)
    return -math.log(pp) if y == 1 else -math.log(1.0 - pp)


def _sigmoid(x: float) -> float:
    # numerically stable sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _logit(p: float, eps: float = 1e-15) -> float:
    pp = _clamp01(p, eps=eps)
    return math.log(pp / (1.0 - pp))


def _fit_logit_calibration(xs: list[float], ys: list[int], *, max_iter: int = 50, tol: float = 1e-10) -> tuple[float, float] | None:
    """
    Fit the calibration model:
      logit(Pr(Y=1)) = alpha + beta * x
    where x = logit(p_forecast).

    Uses IRLS for a 2-parameter logistic regression (intercept + slope).
    Returns (alpha, beta) or None if not enough data.
    """
    if len(xs) != len(ys) or len(xs) < 5:
        return None

    # Initialize near identity calibration: alpha=0, beta=1.
    a = 0.0
    b = 1.0

    for _ in range(max_iter):
        # Build weighted normal equations for IRLS:
        #   (X' W X) theta = X' W z
        # with X=[1, x]
        s_w = 0.0
        s_wx = 0.0
        s_wxx = 0.0
        s_wz = 0.0
        s_wxz = 0.0

        for x, y in zip(xs, ys):
            eta = a + b * x
            mu = _sigmoid(eta)
            # w = mu(1-mu) can be tiny; keep strictly positive for stability.
            w = max(1e-12, mu * (1.0 - mu))
            z = eta + (float(y) - mu) / w
            s_w += w
            s_wx += w * x
            s_wxx += w * x * x
            s_wz += w * z
            s_wxz += w * x * z

        # Solve 2x2 system:
        # [s_w   s_wx ] [a] = [s_wz ]
        # [s_wx  s_wxx] [b]   [s_wxz]
        det = s_w * s_wxx - s_wx * s_wx
        if abs(det) < 1e-18:
            return None

        a_new = (s_wz * s_wxx - s_wx * s_wxz) / det
        b_new = (s_w * s_wxz - s_wx * s_wz) / det

        da = a_new - a
        db = b_new - b
        a, b = a_new, b_new
        if (da * da + db * db) ** 0.5 < tol:
            break

    return a, b


def _confusion_at_threshold(ps: list[float], ys: list[int], *, threshold: float) -> dict[str, Any]:
    """
    Binary rule: predict home_win=1 if p_home >= threshold else 0.
    Returns counts + standard rates.
    """
    tp = fp = tn = fn = 0
    for p, y in zip(ps, ys):
        pred = 1 if p >= threshold else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 0:
            tn += 1
        else:
            fn += 1
    n = tp + fp + tn + fn
    pos = tp + fn
    neg = tn + fp
    return {
        "threshold": float(threshold),
        "n": int(n),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "accuracy": (tp + tn) / n if n else None,
        "error_rate": 1.0 - ((tp + tn) / n) if n else None,
        "tpr": tp / pos if pos else None,  # sensitivity / recall
        "fnr": fn / pos if pos else None,
        "tnr": tn / neg if neg else None,  # specificity
        "fpr": fp / neg if neg else None,
        "prevalence_home_win": pos / n if n else None,
        "predicted_home_win_rate": (tp + fp) / n if n else None,
    }


def _threshold_curve(ps: list[float], ys: list[int], *, thresholds: list[float]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in thresholds:
        out.append(_confusion_at_threshold(ps, ys, threshold=t))
    return out


def _write_calibration_svg(
    *,
    calibration_rows: list[dict[str, Any]],
    out_path: Path,
    title: str,
) -> None:
    """
    Write a simple reliability diagram as an SVG (no external plotting deps).

    Expects rows like:
      {"n": int, "avg_p_home": float, "obs_home_win_rate": float, ...}
    """
    # Canvas
    w = 720
    h = 540
    pad_l = 70
    pad_r = 20
    pad_t = 50
    pad_b = 65
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    def x_px(x: float) -> float:
        return pad_l + max(0.0, min(1.0, x)) * plot_w

    def y_px(y: float) -> float:
        # SVG y increases downward
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

    # Point sizing by sqrt(n) for readability.
    ns = [int(r.get("n") or 0) for r in calibration_rows]
    n_max = max(ns) if ns else 1

    def r_px(n: int) -> float:
        if n <= 0:
            return 0.0
        # 3..10 px radius
        return 3.0 + 7.0 * ((n / n_max) ** 0.5)

    # Build SVG
    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    parts.append(f'<text x="{w/2:.1f}" y="28" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="18" fill="#111">{esc(title)}</text>')

    # Grid + axes
    parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#111" stroke-width="1"/>')

    for i in range(0, 11):
        t = i / 10.0
        xx = x_px(t)
        yy = y_px(t)
        # gridlines
        parts.append(f'<line x1="{xx:.2f}" y1="{pad_t}" x2="{xx:.2f}" y2="{pad_t+plot_h}" stroke="#eee" stroke-width="1"/>')
        parts.append(f'<line x1="{pad_l}" y1="{yy:.2f}" x2="{pad_l+plot_w}" y2="{yy:.2f}" stroke="#eee" stroke-width="1"/>')
        # ticks
        parts.append(f'<text x="{xx:.2f}" y="{pad_t+plot_h+22}" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">{t:.1f}</text>')
        parts.append(f'<text x="{pad_l-10}" y="{yy+4:.2f}" text-anchor="end" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">{t:.1f}</text>')

    parts.append(f'<text x="{pad_l + plot_w/2:.1f}" y="{h-22}" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">Predicted P(home win)</text>')
    parts.append(
        f'<text x="18" y="{pad_t + plot_h/2:.1f}" transform="rotate(-90 18 {pad_t + plot_h/2:.1f})" '
        'text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Observed home win rate</text>"
    )

    # Perfect calibration diagonal
    parts.append(f'<line x1="{x_px(0):.2f}" y1="{y_px(0):.2f}" x2="{x_px(1):.2f}" y2="{y_px(1):.2f}" stroke="#888" stroke-width="2" stroke-dasharray="6,6"/>')

    # Connect points (increasing avg_p)
    pts = []
    for r in sorted(calibration_rows, key=lambda rr: float(rr.get("avg_p_home") or 0.0)):
        px = float(r.get("avg_p_home") or 0.0)
        oy = float(r.get("obs_home_win_rate") or 0.0)
        pts.append((px, oy, int(r.get("n") or 0)))
    if len(pts) >= 2:
        d = "M " + " L ".join(f"{x_px(px):.2f} {y_px(oy):.2f}" for px, oy, _n in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="#1f77b4" stroke-width="2.5" opacity="0.85"/>')

    # Points
    for px, oy, n in pts:
        rr = r_px(n)
        parts.append(
            f'<circle cx="{x_px(px):.2f}" cy="{y_px(oy):.2f}" r="{rr:.2f}" fill="#1f77b4" opacity="0.75" stroke="#0b3d66" stroke-width="1">'
            f'<title>avg_p={px:.4f}, obs={oy:.4f}, n={n}</title>'
            "</circle>"
        )

    # Legend / note
    parts.append(
        f'<text x="{pad_l}" y="{pad_t+plot_h+48}" text-anchor="start" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">'
        "Dots are probability bins (size ~ sqrt(n)). Dashed line is perfect calibration.</text>"
    )

    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_calibration_context_svg(
    *,
    calibration_rows: list[dict[str, Any]],
    out_path: Path,
    title: str,
    summary_lines: list[str],
) -> None:
    """
    Write a "context" SVG: the same calibration plot plus a right-hand panel
    with key numeric summaries and a compact per-bin table.

    This is meant to be data-scientist-friendly: it makes the calibration chart
    self-contained with the most important numbers for interpretation.
    """
    # Layout: left plot + right text panel
    # IMPORTANT: we size the canvas dynamically so right-panel text never clips.
    w = 1380
    pad_t = 50
    pad_l = 70
    pad_b = 90
    pad_r = 20

    plot_w = 740
    panel_x = pad_l + plot_w + 30
    panel_w = w - panel_x - pad_r

    def x_px(x: float) -> float:
        return pad_l + max(0.0, min(1.0, x)) * plot_w

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

    # Point sizing by sqrt(n)
    ns = [int(r.get("n") or 0) for r in calibration_rows]
    n_max = max(ns) if ns else 1

    def r_px(n: int) -> float:
        if n <= 0:
            return 0.0
        return 3.0 + 7.0 * ((n / n_max) ** 0.5)

    # Prepare rows for table (sorted by bin)
    rows_sorted = sorted(calibration_rows, key=lambda r: int(r.get("bin") or 0))
    # Cap table rows for readability if bins are huge
    max_table_rows = 30
    if len(rows_sorted) > max_table_rows:
        # Show head+tail with an ellipsis row
        head_n = max_table_rows // 2
        tail_n = max_table_rows - head_n - 1
        rows_table = rows_sorted[:head_n] + [{"_ellipsis": True}] + rows_sorted[-tail_n:]
    else:
        rows_table = rows_sorted

    # Estimate required height for the right panel (and use that for plot height too).
    # This avoids clipping when the summary/table get longer.
    summary_n = len(summary_lines)
    table_n = len(rows_table)
    # Title + "Summary" + summary lines + "Calibration bins" + header + divider + rows + footnote spacing
    required_panel_h = (
        24  # summary header
        + 18  # gap
        + (summary_n * 16)
        + 10
        + 18  # calibration bins header
        + 18  # header line
        + 14  # divider + gap
        + (table_n * 14)
        + 40  # breathing room
    )
    plot_h = max(520, required_panel_h)
    h = pad_t + plot_h + pad_b

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    parts.append(
        f'<text x="{w/2:.1f}" y="28" text-anchor="middle" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="18" fill="#111">'
        f"{esc(title)}</text>"
    )

    # Plot frame
    parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#111" stroke-width="1"/>')

    # Grid + axes ticks
    for i in range(0, 11):
        t = i / 10.0
        xx = x_px(t)
        yy = y_px(t)
        parts.append(f'<line x1="{xx:.2f}" y1="{pad_t}" x2="{xx:.2f}" y2="{pad_t+plot_h}" stroke="#eee" stroke-width="1"/>')
        parts.append(f'<line x1="{pad_l}" y1="{yy:.2f}" x2="{pad_l+plot_w}" y2="{yy:.2f}" stroke="#eee" stroke-width="1"/>')
        parts.append(
            f'<text x="{xx:.2f}" y="{pad_t+plot_h+22}" text-anchor="middle" '
            'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">'
            f"{t:.1f}</text>"
        )
        parts.append(
            f'<text x="{pad_l-10}" y="{yy+4:.2f}" text-anchor="end" '
            'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">'
            f"{t:.1f}</text>"
        )

    parts.append(
        f'<text x="{pad_l + plot_w/2:.1f}" y="{pad_t+plot_h+44}" text-anchor="middle" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Predicted P(home win)</text>"
    )
    parts.append(
        f'<text x="18" y="{pad_t + plot_h/2:.1f}" transform="rotate(-90 18 {pad_t + plot_h/2:.1f})" '
        'text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Observed home win rate</text>"
    )

    # Perfect calibration diagonal
    parts.append(
        f'<line x1="{x_px(0):.2f}" y1="{y_px(0):.2f}" x2="{x_px(1):.2f}" y2="{y_px(1):.2f}" '
        'stroke="#888" stroke-width="2" stroke-dasharray="6,6"/>'
    )

    # Connect points (increasing avg_p)
    pts = []
    for r in sorted(calibration_rows, key=lambda rr: float(rr.get("avg_p_home") or 0.0)):
        px = float(r.get("avg_p_home") or 0.0)
        oy = float(r.get("obs_home_win_rate") or 0.0)
        pts.append((px, oy, int(r.get("n") or 0)))
    if len(pts) >= 2:
        d = "M " + " L ".join(f"{x_px(px):.2f} {y_px(oy):.2f}" for px, oy, _n in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="#1f77b4" stroke-width="2.5" opacity="0.85"/>')
    for px, oy, n in pts:
        rr = r_px(n)
        parts.append(
            f'<circle cx="{x_px(px):.2f}" cy="{y_px(oy):.2f}" r="{rr:.2f}" fill="#1f77b4" opacity="0.75" '
            f'stroke="#0b3d66" stroke-width="1"><title>avg_p={px:.4f}, obs={oy:.4f}, n={n}</title></circle>'
        )

    # Right panel background
    parts.append(f'<rect x="{panel_x}" y="{pad_t}" width="{panel_w}" height="{plot_h}" fill="#fafafa" stroke="#ddd" stroke-width="1"/>')

    # Summary text
    tx = panel_x + 14
    ty = pad_t + 24
    parts.append(
        f'<text x="{tx}" y="{ty}" text-anchor="start" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Summary</text>"
    )
    ty += 18
    for line in summary_lines:
        parts.append(
            f'<text x="{tx}" y="{ty}" text-anchor="start" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="11" fill="#222">'
            f"{esc(line)}</text>"
        )
        ty += 16

    # Table header
    ty += 10
    parts.append(
        f'<text x="{tx}" y="{ty}" text-anchor="start" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">'
        "Calibration bins</text>"
    )
    ty += 18
    header = "bin   range        n      avg_p     obs      gap"
    parts.append(
        f'<text x="{tx}" y="{ty}" text-anchor="start" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="10.5" fill="#111">'
        f"{esc(header)}</text>"
    )
    ty += 14
    parts.append(f'<line x1="{tx}" y1="{ty}" x2="{panel_x+panel_w-14}" y2="{ty}" stroke="#ddd" stroke-width="1"/>')
    ty += 14

    for r in rows_table:
        if r.get("_ellipsis"):
            line = " ...  (bins omitted for brevity) ..."
        else:
            b = int(r.get("bin") or 0)
            rrng = r.get("range") or [None, None]
            lo = float(rrng[0]) if isinstance(rrng, list) and len(rrng) == 2 and rrng[0] is not None else 0.0
            hi = float(rrng[1]) if isinstance(rrng, list) and len(rrng) == 2 and rrng[1] is not None else 0.0
            n = int(r.get("n") or 0)
            ap = float(r.get("avg_p_home") or 0.0)
            ob = float(r.get("obs_home_win_rate") or 0.0)
            gap = float(r.get("gap") or (ob - ap))
            line = f"{b:>3d}  [{lo:0.2f},{hi:0.2f}) {n:>6d}  {ap:0.4f}  {ob:0.4f}  {gap:+0.4f}"
        parts.append(
            f'<text x="{tx}" y="{ty}" text-anchor="start" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="10.5" fill="#222">'
            f"{esc(line)}</text>"
        )
        ty += 14

    # Footnote
    parts.append(
        f'<text x="{pad_l}" y="{pad_t+plot_h+70}" text-anchor="start" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">'
        "Dots are probability bins (size ~ sqrt(n)). Dashed line is perfect calibration.</text>"
    )
    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    if q <= 0:
        return min(xs)
    if q >= 1:
        return max(xs)
    ys = sorted(xs)
    # nearest-rank
    k = int(math.ceil(q * len(ys))) - 1
    k = max(0, min(len(ys) - 1, k))
    return float(ys[k])


def _parse_int_list_csv(s: str) -> list[int]:
    out: list[int] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


SamplingMode = Literal["anchors", "random", "all"]


def _sample_game_rows(
    rows: list[ObsRow],
    *,
    mode: SamplingMode,
    anchors_seconds_remaining: list[int],
    anchor_tolerance_seconds: int,
    rng: random.Random,
) -> list[ObsRow]:
    if not rows:
        return []
    if mode == "all":
        return list(rows)
    if mode == "random":
        return [rows[rng.randrange(0, len(rows))]]
    if mode == "last":
        # Choose the latest (max sequence_number), tie-breaking by event_id.
        def _key(r: ObsRow) -> tuple[int, int]:
            seq = r.sequence_number if r.sequence_number is not None else -1
            return (int(seq), int(r.event_id))

        best = max(rows, key=_key)
        return [best]
    if mode != "anchors":
        raise ValueError(f"unknown sampling mode: {mode}")

    # For each anchor time_remaining, pick the closest observed row within tolerance.
    out: list[ObsRow] = []
    used_event_ids: set[int] = set()
    tol = max(0, int(anchor_tolerance_seconds))

    # Pre-filter candidates with known time_remaining.
    candidates = [r for r in rows if r.time_remaining is not None]
    if not candidates:
        return []

    for a in anchors_seconds_remaining:
        best: tuple[int, int, int] | None = None
        best_row: ObsRow | None = None
        for r in candidates:
            tr = int(r.time_remaining)  # not None
            d = abs(tr - int(a))
            if d > tol:
                continue
            # tie-break: smaller distance, then earlier sequence (if known), then event_id
            seq = r.sequence_number if r.sequence_number is not None else 1_000_000_000
            key = (d, seq, r.event_id)
            if best is None or key < best:
                best = key
                best_row = r
        if best_row is None:
            continue
        if best_row.event_id in used_event_ids:
            continue
        used_event_ids.add(best_row.event_id)
        out.append(best_row)

    # Deterministic ordering by decreasing time_remaining (more readable)
    out.sort(key=lambda r: (-(r.time_remaining or -1), r.event_id))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify ESPN win probabilities for coherence + calibration.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument(
        "--season-label",
        default="2024-25",
        help="Season label (e.g. 2024-25). Use ALL to aggregate across all seasons present in the DB table.",
    )
    p.add_argument(
        "--use-prob-table",
        action="store_true",
        help="Read probabilities from derived.espn_probabilities_raw_items instead of JSON files.",
    )
    p.add_argument(
        "--outcomes",
        choices=["event_state", "scoreboard"],
        default="event_state",
        help=(
            "Where to get realized outcomes. "
            "event_state=derived.espn_prob_event_state (legacy); "
            "scoreboard=use cached ESPN scoreboard JSON (recommended when --use-prob-table)."
        ),
    )
    p.add_argument(
        "--scoreboard-root",
        default="data/raw/espn/scoreboard",
        help="Root dir containing scoreboard_YYYYMMDD.json (used when --outcomes scoreboard).",
    )
    p.add_argument("--probabilities-dir", default="", help="Override probabilities dir.")
    p.add_argument("--limit-games", type=int, default=0, help="Limit number of probability files processed (0=no limit).")
    p.add_argument("--bins", type=int, default=20, help="Number of equal-width bins for calibration (home win prob).")
    p.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=15.0,
        help="Print progress heartbeat at least this often while running. Set 0 to disable.",
    )
    p.add_argument(
        "--plot-calibration",
        action="store_true",
        help="Write an SVG reliability diagram next to the JSON report.",
    )
    p.add_argument(
        "--plot-calibration-context",
        action="store_true",
        help="Write a second SVG with the calibration plot plus numeric context (summary + per-bin table).",
    )
    p.add_argument(
        "--sampling",
        choices=["anchors", "random", "last", "all"],
        default="anchors",
        help=(
            "How to select representative snapshots per game. "
            "anchors=nearest event(s) to fixed time_remaining anchors per game (default; requires --outcomes event_state); "
            "last=use the latest update per game by sequence_number; "
            "random=one random snapshot per game; "
            "all=use all updates (not iid; mainly for debugging)."
        ),
    )
    p.add_argument(
        "--anchors-seconds-remaining",
        default="2400,1800,1200,600,300,180,60,0",
        help="Comma-separated anchor times in seconds remaining (used when --sampling anchors).",
    )
    p.add_argument(
        "--anchor-tolerance-seconds",
        type=int,
        default=30,
        help="Max |time_remaining-anchor| allowed for anchor matching (used when --sampling anchors).",
    )
    p.add_argument("--random-seed", type=int, default=123, help="RNG seed (used when --sampling random or bootstrap).")
    p.add_argument(
        "--bootstrap-iters",
        type=int,
        default=400,
        help="Game-cluster bootstrap iterations for CIs (0 disables).",
    )
    p.add_argument("--min-group-n", type=int, default=200, help="Minimum N for conditional subgroup summaries.")
    p.add_argument("--out", default="", help="Write JSON report to this path (default: data/reports/*).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    def _season_start_end(season_label: str) -> tuple[date, date]:
        # Default NBA season window (good enough for scoreboard outcome lookup)
        # e.g. 2024-25 -> 2024-09-01 through 2025-08-31
        m = re.match(r"^(?P<y1>\d{4})-(?P<y2>\d{2})$", season_label)
        if not m:
            raise ValueError(f"Unexpected season label: {season_label}")
        y1 = int(m.group("y1"))
        y2 = y1 + 1
        return date(y1, 9, 1), date(y2, 8, 31)

    def _iter_dates(d0: date, d1: date) -> list[date]:
        out: list[date] = []
        cur = d0
        while cur <= d1:
            out.append(cur)
            cur = cur + timedelta(days=1)
        return out

    def _load_scoreboard_outcomes(*, season_labels: list[str], scoreboard_root: Path) -> dict[tuple[str, str], int]:
        """
        Return mapping (season_label, game_id) -> y_home_win (1 if home wins, else 0).
        Only includes completed/final games found in cached scoreboard files.
        """
        wanted = set(str(s) for s in season_labels)
        out: dict[tuple[str, str], int] = {}

        for s in season_labels:
            d0, d1 = _season_start_end(str(s))
            for d in _iter_dates(d0, d1):
                path = scoreboard_root / f"scoreboard_{d.strftime('%Y%m%d')}.json"
                if not path.exists():
                    continue
                try:
                    obj = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                leagues = obj.get("leagues")
                if not (isinstance(leagues, list) and leagues):
                    continue
                league0 = leagues[0] if isinstance(leagues[0], dict) else {}
                season_obj = league0.get("season") if isinstance(league0, dict) else None
                season_label = None
                if isinstance(season_obj, dict):
                    season_label = season_obj.get("displayName")
                if not isinstance(season_label, str) or season_label not in wanted:
                    continue

                events = obj.get("events")
                if not isinstance(events, list):
                    continue
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    comps = ev.get("competitions")
                    if not (isinstance(comps, list) and comps):
                        continue
                    comp = comps[0] if isinstance(comps[0], dict) else None
                    if not isinstance(comp, dict):
                        continue

                    status = comp.get("status")
                    completed = False
                    if isinstance(status, dict):
                        st_type = status.get("type")
                        if isinstance(st_type, dict):
                            completed = bool(st_type.get("completed"))
                    if not completed:
                        continue

                    gid = comp.get("id")
                    if not isinstance(gid, str) or not gid:
                        continue

                    competitors = comp.get("competitors")
                    if not isinstance(competitors, list):
                        continue
                    home = away = None
                    for c in competitors:
                        if not isinstance(c, dict):
                            continue
                        ha = c.get("homeAway")
                        if ha == "home":
                            home = c
                        elif ha == "away":
                            away = c
                    if not (isinstance(home, dict) and isinstance(away, dict)):
                        continue

                    home_winner = home.get("winner")
                    away_winner = away.get("winner")
                    if isinstance(home_winner, bool):
                        y = 1 if home_winner else 0
                    elif isinstance(away_winner, bool):
                        y = 0 if away_winner else 1
                    else:
                        continue

                    out[(season_label, gid)] = int(y)
        return out

    season = str(args.season_label)
    use_prob_table = bool(args.use_prob_table)
    outcomes_mode = str(args.outcomes)

    if use_prob_table and outcomes_mode == "event_state":
        print("[verify] NOTE: --use-prob-table typically pairs with --outcomes scoreboard (no derived table required).", flush=True)

    # Determine seasons list
    if season.upper() == "ALL":
        with psycopg.connect(dsn) as conn:
            rows = conn.execute("SELECT DISTINCT season_label FROM derived.espn_probabilities_raw_items ORDER BY 1;").fetchall()
        seasons = [str(r[0]) for r in rows]
        if not seasons:
            raise SystemExit("No seasons found in derived.espn_probabilities_raw_items")
    else:
        seasons = [season]

    # Output naming
    out_tag = "ALL" if season.upper() == "ALL" else season

    out_path = Path(args.out) if args.out else Path("data/reports") / f"espn_win_prob_verify_{out_tag}_{_utc_ts()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[verify] start season={out_tag} seasons={len(seasons)} use_prob_table={use_prob_table} outcomes={outcomes_mode} "
        f"sampling={args.sampling} bins={int(args.bins)} "
        f"bootstrap_itrs={int(args.bootstrap_iters)}",
        flush=True,
    )

    # Accumulators
    total_prob_items = 0
    joined_items = 0
    missing_db_rows = 0

    bounds_violations = 0
    sum_violations = 0
    sum_abs_err_total = 0.0

    # Build a per-game dataset for proper sampling + cluster bootstrap.
    # Keyed by ESPN competition id.
    game_rows: dict[str, list[ObsRow]] = {}

    last_heartbeat = time.monotonic()
    hb = float(args.heartbeat_seconds or 0.0)

    # Outcomes
    outcomes: dict[tuple[str, str], int] = {}
    if outcomes_mode == "scoreboard":
        outcomes = _load_scoreboard_outcomes(season_labels=seasons, scoreboard_root=Path(args.scoreboard_root))
        print(f"[verify] loaded outcomes from scoreboard n_games={len(outcomes)}", flush=True)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if use_prob_table:
                # If user asked for anchors but we don't have time_remaining without derived state, fall back to "last".
                sampling: SamplingMode = str(args.sampling)  # type: ignore[assignment]
                if sampling == "anchors" and outcomes_mode == "scoreboard":
                    print("[verify] NOTE: sampling=anchors requires derived.espn_prob_event_state; using sampling=last instead.", flush=True)
                    sampling = "last"  # type: ignore[assignment]

                if sampling in ("random", "anchors"):
                    # Random/anchors require per-game row collections (anchors also needs time_remaining).
                    # To keep memory bounded, we recommend sampling=last for ALL seasons.
                    print("[verify] NOTE: For --use-prob-table, sampling=last is the fast path; random/all can be heavy.", flush=True)

                if sampling == "last":
                    cur.execute(
                        """
                        SELECT DISTINCT ON (season_label, game_id)
                          season_label,
                          game_id,
                          event_id,
                          sequence_number,
                          home_win_percentage,
                          away_win_percentage,
                          tie_percentage
                        FROM derived.espn_probabilities_raw_items
                        WHERE season_label = ANY(%s)
                        ORDER BY season_label, game_id, sequence_number DESC NULLS LAST, event_id DESC;
                        """,
                        (seasons,),
                    )
                    rows = cur.fetchall()
                    total_prob_items = len(rows)
                    for (slabel, gid, eid, seq, p_home, p_away, p_tie) in rows:
                        probs = [p_home, p_away, p_tie]
                        if any(p is None for p in probs):
                            continue
                        ph = float(p_home)
                        pa = float(p_away)
                        pt = float(p_tie)
                        if any((p < -1e-9 or p > 1.0 + 1e-9) for p in (ph, pa, pt)):
                            bounds_violations += 1
                        ss = ph + pa + pt
                        err = abs(ss - 1.0)
                        sum_abs_err_total += err
                        if err > 1e-3:
                            sum_violations += 1
                        joined_items += 1

                        y = outcomes.get((str(slabel), str(gid))) if outcomes_mode == "scoreboard" else None
                        if y is None:
                            missing_db_rows += 1
                            continue
                        game_rows.setdefault(str(gid), []).append(
                            ObsRow(
                                game_id=str(gid),
                                event_id=int(eid),
                                sequence_number=int(seq) if seq is not None else None,
                                p_home=float(ph),
                                y_home_win=int(y),
                                time_remaining=None,
                                point_differential=None,
                                possession_side=None,
                            )
                        )
                else:
                    # "all" path: stream all rows and group in memory per game (can be large).
                    cur.execute(
                        """
                        SELECT season_label, game_id, event_id, sequence_number,
                               home_win_percentage, away_win_percentage, tie_percentage
                        FROM derived.espn_probabilities_raw_items
                        WHERE season_label = ANY(%s)
                        ORDER BY season_label, game_id, sequence_number NULLS LAST, event_id;
                        """,
                        (seasons,),
                    )
                    while True:
                        batch = cur.fetchmany(50_000)
                        if not batch:
                            break
                        total_prob_items += len(batch)
                        for (slabel, gid, eid, seq, p_home, p_away, p_tie) in batch:
                            probs = [p_home, p_away, p_tie]
                            if any(p is None for p in probs):
                                continue
                            ph = float(p_home)
                            pa = float(p_away)
                            pt = float(p_tie)
                            if any((p < -1e-9 or p > 1.0 + 1e-9) for p in (ph, pa, pt)):
                                bounds_violations += 1
                            ss = ph + pa + pt
                            err = abs(ss - 1.0)
                            sum_abs_err_total += err
                            if err > 1e-3:
                                sum_violations += 1
                            joined_items += 1

                            y = outcomes.get((str(slabel), str(gid))) if outcomes_mode == "scoreboard" else None
                            if y is None:
                                missing_db_rows += 1
                                continue
                            game_rows.setdefault(str(gid), []).append(
                                ObsRow(
                                    game_id=str(gid),
                                    event_id=int(eid),
                                    sequence_number=int(seq) if seq is not None else None,
                                    p_home=float(ph),
                                    y_home_win=int(y),
                                    time_remaining=None,
                                    point_differential=None,
                                    possession_side=None,
                                )
                            )
            else:
                # Legacy JSON+derived-table mode
                prob_dir = Path(args.probabilities_dir) if args.probabilities_dir else Path("data/raw/espn/probabilities") / season
                prob_files = _iter_prob_files(prob_dir)
                if args.limit_games and args.limit_games > 0:
                    prob_files = prob_files[: args.limit_games]
                if not prob_files:
                    raise SystemExit(f"No probabilities files found in {prob_dir}")

                for i, prob_path in enumerate(prob_files, start=1):
                    now = time.monotonic()
                    if hb > 0 and (now - last_heartbeat) >= hb:
                        print(
                            f"[verify] building dataset file={i}/{len(prob_files)} "
                            f"total_prob_items={total_prob_items} joined_items={joined_items} "
                            f"games_with_rows={len(game_rows)} missing_db_rows={missing_db_rows}",
                            flush=True,
                        )
                        last_heartbeat = now

                    prob_items = _load_prob_items(prob_path)
                    if not prob_items:
                        continue
                    total_prob_items += len(prob_items)

                    play_ids = [pi.play_id for pi in prob_items]
                    # Fetch derived state + final outcome.
                    # IMPORTANT: we do NOT treat all per-play updates as independent. We first build per-game rows, then sample.
                    cur.execute(
                        """
                        SELECT game_id, event_id, time_remaining, final_winning_team, point_differential, possession_side
                        FROM derived.espn_prob_event_state
                        WHERE event_id = ANY(%s);
                        """,
                        (play_ids,),
                    )
                    rows = cur.fetchall()
                    by_event: dict[int, tuple[str, int | None, int | None, int | None, int | None]] = {
                        int(eid): (str(gid), tr, fw, pd, ps) for (gid, eid, tr, fw, pd, ps) in rows
                    }

                    for pi in prob_items:
                        # Hard checks on probability numbers
                        probs = [pi.p_home, pi.p_away, pi.p_tie]
                        if any(p is None for p in probs):
                            continue
                        p_home = float(pi.p_home)  # type: ignore[arg-type]
                        p_away = float(pi.p_away)  # type: ignore[arg-type]
                        p_tie = float(pi.p_tie)  # type: ignore[arg-type]

                        if any((p < -1e-9 or p > 1.0 + 1e-9) for p in (p_home, p_away, p_tie)):
                            bounds_violations += 1

                        s = p_home + p_away + p_tie
                        err = abs(s - 1.0)
                        sum_abs_err_total += err
                        if err > 1e-3:
                            sum_violations += 1

                        joined_items += 1
                        st = by_event.get(pi.play_id)
                        if st is None:
                            missing_db_rows += 1
                            continue

                        game_id, time_remaining, final_winner, point_diff, possession_side = st

                        if final_winner not in (0, 1):
                            # skip ties/unknown for scoring (rare)
                            continue
                        y = 1 if int(final_winner) == 0 else 0  # home win outcome

                        ps = int(possession_side) if possession_side in (0, 1) else None
                        game_rows.setdefault(str(game_id), []).append(
                            ObsRow(
                                game_id=str(game_id),
                                event_id=int(pi.play_id),
                                sequence_number=pi.sequence_number,
                                p_home=float(p_home),
                                y_home_win=int(y),
                                time_remaining=time_remaining,
                                point_differential=point_diff,
                                possession_side=ps,
                            )
                        )

    # Sample representative snapshots per game (to reduce within-game autocorrelation).
    print(f"[verify] sampling per game mode={args.sampling} games={len(game_rows)}", flush=True)
    bins = max(1, int(args.bins))
    sampling: SamplingMode = str(args.sampling)  # type: ignore[assignment]
    anchors = _parse_int_list_csv(str(args.anchors_seconds_remaining))
    rng = random.Random(int(args.random_seed))

    sampled_rows: list[ObsRow] = []
    for gid in sorted(game_rows.keys()):
        sampled_rows.extend(
            _sample_game_rows(
                game_rows[gid],
                mode=sampling,
                anchors_seconds_remaining=anchors,
                anchor_tolerance_seconds=int(args.anchor_tolerance_seconds),
                rng=rng,
            )
        )

    # Compute primary verification outputs on the sampled dataset.
    score_n = len(sampled_rows)
    brier_sum = sum(_brier(r.p_home, r.y_home_win) for r in sampled_rows)
    logloss_sum = sum(_logloss(r.p_home, r.y_home_win) for r in sampled_rows)
    ps_all = [r.p_home for r in sampled_rows]
    ys_all = [r.y_home_win for r in sampled_rows]
    # If you force probabilities into a binary pick: pick home if p_home>=0.5 else away.
    pick_rule = "predict home win if p_home >= 0.5 else away win"
    pick_metrics = _confusion_at_threshold(ps_all, ys_all, threshold=0.5) if score_n else None

    # Calibration bins (reliability)
    bin_n = [0] * bins
    bin_p_sum = [0.0] * bins
    bin_y_sum = [0] * bins
    for r in sampled_rows:
        idx = min(bins - 1, max(0, int(math.floor(r.p_home * bins))))
        bin_n[idx] += 1
        bin_p_sum[idx] += float(r.p_home)
        bin_y_sum[idx] += int(r.y_home_win)

    calib: list[dict[str, Any]] = []
    for i in range(bins):
        n = bin_n[i]
        if n <= 0:
            continue
        avg_p = bin_p_sum[i] / n
        obs = bin_y_sum[i] / n
        lo = i / bins
        hi = (i + 1) / bins
        calib.append({"bin": i, "range": [lo, hi], "n": n, "avg_p_home": avg_p, "obs_home_win_rate": obs, "gap": obs - avg_p})

    ece = 0.0
    total_in_bins = sum(bin_n)
    if total_in_bins > 0:
        for row in calib:
            w = row["n"] / total_in_bins
            ece += w * abs(float(row["gap"]))

    # Parametric calibration: logit(y) ~ alpha + beta*logit(p)
    xs = [_logit(r.p_home) for r in sampled_rows]
    ys = [r.y_home_win for r in sampled_rows]
    cal_fit = _fit_logit_calibration(xs, ys)
    cal_alpha = cal_beta = None
    if cal_fit is not None:
        cal_alpha, cal_beta = cal_fit

    # Conditional calibration summaries (time remaining; score margin).
    min_group_n = max(1, int(args.min_group_n))
    cond_by_time: dict[str, dict[str, Any]] = {}
    for tb in ["2400+", "1200-2400", "600-1200", "300-600", "180-300", "60-180", "0-60", "unknown"]:
        sub = [r for r in sampled_rows if _bucket_time_remaining(r.time_remaining) == tb]
        if len(sub) < min_group_n:
            continue
        b = sum(_brier(r.p_home, r.y_home_win) for r in sub) / len(sub)
        ll = sum(_logloss(r.p_home, r.y_home_win) for r in sub) / len(sub)
        ps = [r.p_home for r in sub]
        ys = [r.y_home_win for r in sub]
        cm = _confusion_at_threshold(ps, ys, threshold=0.5)
        cond_by_time[tb] = {
            "n": len(sub),
            "brier": b,
            "logloss": ll,
            "pick_rule": pick_rule,
            "pick_error_rate_p_home_ge_0_5": cm["error_rate"],
            "pick_false_positive_rate_p_home_ge_0_5": cm["fpr"],
            "pick_false_negative_rate_p_home_ge_0_5": cm["fnr"],
            "pick_confusion": {"tp": cm["tp"], "fp": cm["fp"], "tn": cm["tn"], "fn": cm["fn"]},
        }

    # Simple score-margin buckets by point differential (home - away)
    def _pd_bucket(pd: int | None) -> str:
        if pd is None:
            return "unknown"
        if pd <= -15:
            return "<=-15"
        if pd <= -8:
            return "-14..-8"
        if pd <= -4:
            return "-7..-4"
        if pd <= -1:
            return "-3..-1"
        if pd <= 1:
            return "-0..+1"
        if pd <= 3:
            return "+2..+3"
        if pd <= 7:
            return "+4..+7"
        if pd <= 14:
            return "+8..+14"
        return ">=+15"

    cond_by_pd: dict[str, dict[str, Any]] = {}
    for r in sampled_rows:
        k = _pd_bucket(r.point_differential)
        cond_by_pd.setdefault(k, {"rows": []})["rows"].append(r)
    for k, acc in list(cond_by_pd.items()):
        sub = acc["rows"]
        if len(sub) < min_group_n:
            del cond_by_pd[k]
            continue
        b = sum(_brier(r.p_home, r.y_home_win) for r in sub) / len(sub)
        ll = sum(_logloss(r.p_home, r.y_home_win) for r in sub) / len(sub)
        ps = [r.p_home for r in sub]
        ys = [r.y_home_win for r in sub]
        cm = _confusion_at_threshold(ps, ys, threshold=0.5)
        cond_by_pd[k] = {
            "n": len(sub),
            "brier": b,
            "logloss": ll,
            "pick_rule": pick_rule,
            "pick_error_rate_p_home_ge_0_5": cm["error_rate"],
            "pick_false_positive_rate_p_home_ge_0_5": cm["fpr"],
            "pick_false_negative_rate_p_home_ge_0_5": cm["fnr"],
            "pick_confusion": {"tp": cm["tp"], "fp": cm["fp"], "tn": cm["tn"], "fn": cm["fn"]},
        }

    # Game-cluster bootstrap for uncertainty intervals (resample games with replacement).
    boot_iters = max(0, int(args.bootstrap_iters))
    boot: dict[str, Any] = {"iters": boot_iters, "metrics": {}}
    if boot_iters > 0 and game_rows:
        # Bootstrap uses the *same* sampled-per-game design in each replicate,
        # but resamples games (clusters) with replacement.
        gids = list(game_rows.keys())
        rng_boot = random.Random(int(args.random_seed) + 999)

        brier_s: list[float] = []
        logloss_s: list[float] = []
        ece_s: list[float] = []
        alpha_s: list[float] = []
        beta_s: list[float] = []

        for _ in range(boot_iters):
            if hb > 0 and (time.monotonic() - last_heartbeat) >= hb:
                # This is intentionally coarse: tells you we're alive without spamming every iter.
                done = len(brier_s)
                print(f"[verify] bootstrap progress done={done}/{boot_iters}", flush=True)
                last_heartbeat = time.monotonic()

            rep_rows: list[ObsRow] = []
            for _j in range(len(gids)):
                gid = gids[rng_boot.randrange(0, len(gids))]
                # Re-sample within-game deterministically given this replicate RNG.
                rep_rows.extend(
                    _sample_game_rows(
                        game_rows[gid],
                        mode=sampling,
                        anchors_seconds_remaining=anchors,
                        anchor_tolerance_seconds=int(args.anchor_tolerance_seconds),
                        rng=rng_boot,
                    )
                )
            if not rep_rows:
                continue

            n = len(rep_rows)
            brier_s.append(sum(_brier(r.p_home, r.y_home_win) for r in rep_rows) / n)
            logloss_s.append(sum(_logloss(r.p_home, r.y_home_win) for r in rep_rows) / n)

            # ECE for replicate
            bn = [0] * bins
            bp = [0.0] * bins
            by = [0] * bins
            for r in rep_rows:
                idx = min(bins - 1, max(0, int(math.floor(r.p_home * bins))))
                bn[idx] += 1
                bp[idx] += float(r.p_home)
                by[idx] += int(r.y_home_win)
            total = sum(bn)
            if total > 0:
                ee = 0.0
                for i in range(bins):
                    if bn[i] <= 0:
                        continue
                    avg_p = bp[i] / bn[i]
                    obs = by[i] / bn[i]
                    ee += (bn[i] / total) * abs(obs - avg_p)
                ece_s.append(ee)

            fit = _fit_logit_calibration([_logit(r.p_home) for r in rep_rows], [r.y_home_win for r in rep_rows])
            if fit is not None:
                a, b = fit
                alpha_s.append(float(a))
                beta_s.append(float(b))

        boot["metrics"] = {
            "brier_ci95": [_percentile(brier_s, 0.025), _percentile(brier_s, 0.975)],
            "logloss_ci95": [_percentile(logloss_s, 0.025), _percentile(logloss_s, 0.975)],
            "ece_ci95": [_percentile(ece_s, 0.025), _percentile(ece_s, 0.975)],
            "calibration_alpha_ci95": [_percentile(alpha_s, 0.025), _percentile(alpha_s, 0.975)],
            "calibration_beta_ci95": [_percentile(beta_s, 0.025), _percentile(beta_s, 0.975)],
            "notes": "CIs are percentile intervals from a game-cluster bootstrap (resample games; keep within-game sampling design).",
        }

    report = {
        "season": out_tag,
        "seasons": seasons,
        "data_sources": {
            "probabilities": ("derived.espn_probabilities_raw_items" if use_prob_table else "data/raw/espn/probabilities/*.json"),
            "outcomes": ("scoreboard_json" if outcomes_mode == "scoreboard" else "derived.espn_prob_event_state"),
        },
        "files_processed": (None if use_prob_table else len(prob_files)),  # type: ignore[name-defined]
        "total_prob_items": total_prob_items,
        "joined_items_with_probs": joined_items,
        "missing_db_rows": missing_db_rows,
        "probability_bounds_violations": bounds_violations,
        "probability_sum_violations_gt_1e-3": sum_violations,
        "mean_abs_sum_error": (sum_abs_err_total / joined_items) if joined_items else None,
        "sampling": {
            "mode": sampling,
            "anchors_seconds_remaining": anchors,
            "anchor_tolerance_seconds": int(args.anchor_tolerance_seconds),
            "random_seed": int(args.random_seed),
            "notes": "Sampling is applied per game to reduce within-game autocorrelation before calibration/scoring.",
        },
        "games_with_any_rows": len(game_rows),
        "scoring_n": score_n,
        "brier": (brier_sum / score_n) if score_n else None,
        "logloss": (logloss_sum / score_n) if score_n else None,
        "pick_winner": {
            "rule": pick_rule,
            "metrics": pick_metrics,
            "notes": "This is NOT calibration; it is a forced binary decision rule applied to sampled snapshots.",
        },
        "binary_threshold_curve": {
            "definition": "At each threshold t, predict home_win=1 iff p_home >= t. Report confusion + TPR/FPR/etc.",
            "thresholds": [round(i / 20, 3) for i in range(0, 21)],
            "curve": (_threshold_curve(ps_all, ys_all, thresholds=[i / 20 for i in range(0, 21)]) if score_n else []),
        },
        "ece_binned": ece if total_in_bins else None,
        "calibration": calib,
        "calibration_logit_regression": {
            "model": "logit(Pr(home_win)) = alpha + beta * logit(p_home)",
            "alpha": cal_alpha,
            "beta": cal_beta,
            "interpretation_notes": {
                "alpha": "Calibration-in-the-large on log-odds scale: alpha>0 implies realized home-win rate > forecast on average (after logit transform).",
                "beta": "Calibration slope on log-odds scale: beta<1 suggests overconfident/extreme forecasts; beta>1 suggests underconfident/not extreme enough.",
            },
        },
        "conditional_summaries": {
            "min_group_n": min_group_n,
            "by_time_remaining_bucket": cond_by_time,
            "by_point_differential_bucket": cond_by_pd,
        },
        "bootstrap": boot,
    }

    # Optional plot artifacts
    artifacts: dict[str, Any] = {}
    if bool(args.plot_calibration):
        svg_path = out_path.with_suffix(".calibration.svg")
        _write_calibration_svg(
            calibration_rows=calib,
            out_path=svg_path,
            title=f"ESPN Win Prob Calibration — {out_tag} (sampling={sampling}, n={score_n})",
        )
        artifacts["calibration_svg"] = str(svg_path)
        print(f"[verify] wrote {svg_path}", flush=True)
    if bool(args.plot_calibration_context):
        svg_path = out_path.with_suffix(".calibration_context.svg")
        pick = report.get("pick_winner", {}).get("metrics") or {}
        summary_lines = [
            f"season={out_tag} seasons={len(seasons)}",
            f"sampling={sampling} bins={bins}",
            f"scoring_n={score_n} games_with_rows={len(game_rows)}",
            f"missing_outcomes={missing_db_rows}",
            f"brier={report.get('brier')}",
            f"logloss={report.get('logloss')}",
            f"ece={report.get('ece_binned')}",
            f"prevalence_home_win={pick.get('prevalence_home_win')}",
            f"pick_error_rate@0.5={pick.get('error_rate')}",
        ]
        lr = report.get("calibration_logit_regression") or {}
        if lr.get("alpha") is not None or lr.get("beta") is not None:
            summary_lines.append(f"logit_calibration alpha={lr.get('alpha')} beta={lr.get('beta')}")
        _write_calibration_context_svg(
            calibration_rows=calib,
            out_path=svg_path,
            title=f"ESPN Win Prob Calibration (with context) — {out_tag}",
            summary_lines=summary_lines,
        )
        artifacts["calibration_context_svg"] = str(svg_path)
        print(f"[verify] wrote {svg_path}", flush=True)
    if artifacts:
        report["artifacts"] = artifacts

    out_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"[verify] wrote {out_path}")
    print(f"[verify] scoring_n={score_n} brier={report['brier']} logloss={report['logloss']} ece={report['ece_binned']}")
    if report.get("pick_winner", {}).get("metrics"):
        print(f"[verify] pick_error_rate(p_home>=0.5)={report['pick_winner']['metrics']['error_rate']}", flush=True)
    print(f"[verify] bounds_violations={bounds_violations} sum_violations={sum_violations} mean_abs_sum_error={report['mean_abs_sum_error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


