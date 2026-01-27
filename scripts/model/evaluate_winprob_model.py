#!/usr/bin/env python3
"""
Evaluate a saved win-probability pipeline artifact on a held-out season.

This script:
- loads the artifact JSON
- scores snapshot rows from ESPN tables
- reports overall metrics and per-bucket metrics
- writes a JSON report (and optionally a calibration SVG without external plotting libs)

For detailed usage instructions, see: cursor-files/docs/evaluate_winprob_model_guide.md

Usage:
  ./.venv/bin/python scripts/model/evaluate_winprob_model.py \
    --artifact artifacts/winprob_logreg_v1.json \
    --season-start 2024 \
    --out data/reports/winprob_eval_2024.json \
    --plot-calibration \
    --verbose \
    --workers 4
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
import warnings
from pathlib import Path
from typing import Any

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False

import numpy as np
import pandas as pd

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, connect
from scripts.lib._winprob_lib import (
    brier,
    build_design_matrix,
    ece_binned,
    load_artifact,
    logloss,
    predict_proba,
    roc_auc,
    utc_now_iso_compact,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate win-prob model artifact on a season_start split.",
        epilog="For detailed usage instructions, see: cursor-files/docs/evaluate_winprob_model_guide.md"
    )
    p.add_argument("--artifact", required=True, help="Artifact JSON path.")
    p.add_argument("--dsn", help="Database connection string (or use DATABASE_URL env var)")
    p.add_argument("--season-start", type=int, required=True, help="Season_start to evaluate (e.g. 2024).")
    p.add_argument("--out", required=True, help="Output JSON report path.")
    p.add_argument("--bins", type=int, default=20, help="Bins for ECE/reliability (default: 20).")
    p.add_argument("--plot-calibration", action="store_true", help="Write an SVG reliability diagram next to the JSON report.")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging with detailed progress information.")
    p.add_argument("--workers", type=int, default=8, help="Number of parallel workers for per-bucket metrics (default: 1, no parallelization). NOTE: Currently not implemented due to artifact pickling limitations.")
    p.add_argument("--disable-calibration", action="store_true", help="Evaluate model without Platt calibration (for comparison).")
    return p.parse_args()


def _write_calibration_svg(*, rows: list[dict[str, Any]], out_path: Path, title: str) -> None:
    # Minimal SVG reliability plot (mirrors scripts/verify_espn_win_probabilities.py style).
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

    ns = [int(r.get("n") or 0) for r in rows]
    n_max = max(ns) if ns else 1

    def r_px(n: int) -> float:
        if n <= 0:
            return 0.0
        return 3.0 + 7.0 * ((n / n_max) ** 0.5)

    pts = []
    for r in sorted(rows, key=lambda rr: float(rr.get("avg_p") or 0.0)):
        pts.append((float(r["avg_p"]), float(r["obs_rate"]), int(r["n"])))

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    parts.append(
        f'<text x="{w/2:.1f}" y="28" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="18" fill="#111">{esc(title)}</text>'
    )
    parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#111" stroke-width="1"/>')
    for i in range(0, 11):
        t = i / 10.0
        xx = x_px(t)
        yy = y_px(t)
        parts.append(f'<line x1="{xx:.2f}" y1="{pad_t}" x2="{xx:.2f}" y2="{pad_t+plot_h}" stroke="#eee" stroke-width="1"/>')
        parts.append(f'<line x1="{pad_l}" y1="{yy:.2f}" x2="{pad_l+plot_w}" y2="{yy:.2f}" stroke="#eee" stroke-width="1"/>')
        parts.append(f'<text x="{xx:.2f}" y="{pad_t+plot_h+22}" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">{t:.1f}</text>')
        parts.append(f'<text x="{pad_l-10}" y="{yy+4:.2f}" text-anchor="end" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="#333">{t:.1f}</text>')
    parts.append(f'<text x="{pad_l + plot_w/2:.1f}" y="{h-22}" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">Predicted P(home win)</text>')
    parts.append(
        f'<text x="18" y="{pad_t + plot_h/2:.1f}" transform="rotate(-90 18 {pad_t + plot_h/2:.1f})" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">Observed home win rate</text>'
    )
    parts.append(f'<line x1="{x_px(0):.2f}" y1="{y_px(0):.2f}" x2="{x_px(1):.2f}" y2="{y_px(1):.2f}" stroke="#888" stroke-width="2" stroke-dasharray="6,6"/>')
    if len(pts) >= 2:
        d = "M " + " L ".join(f"{x_px(px):.2f} {y_px(oy):.2f}" for px, oy, _n in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="#1f77b4" stroke-width="2.5" opacity="0.85"/>')
    for px, oy, n in pts:
        rr = r_px(n)
        parts.append(
            f'<circle cx="{x_px(px):.2f}" cy="{y_px(oy):.2f}" r="{rr:.2f}" fill="#1f77b4" opacity="0.75" stroke="#0b3d66" stroke-width="1">'
            f"<title>avg_p={px:.4f}, obs={oy:.4f}, n={n}</title></circle>"
        )
    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _convert_svg_to_jpeg(svg_path: Path, jpeg_path: Path, quality: int = 90) -> None:
    """
    Convert SVG file to JPEG using cairosvg.
    
    Args:
        svg_path: Path to input SVG file
        jpeg_path: Path to output JPEG file
        quality: JPEG quality (1-100, default: 90)
    """
    if not CAIROSVG_AVAILABLE:
        raise ImportError("cairosvg is required for JPEG generation. Install with: pip install cairosvg")
    
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    
    # Read SVG content
    svg_content = svg_path.read_text(encoding="utf-8")
    
    # Convert SVG to PNG first (cairosvg doesn't directly support JPEG)
    # Then convert PNG to JPEG using PIL
    from io import BytesIO
    from PIL import Image
    
    # Convert SVG to PNG bytes
    png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
    
    # Convert PNG to JPEG
    img = Image.open(BytesIO(png_bytes))
    # Convert RGBA to RGB if needed
    if img.mode == "RGBA":
        # Create white background
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = rgb_img
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    # Save as JPEG
    img.save(jpeg_path, "JPEG", quality=quality, optimize=True)


def _write_calibration_context_svg(
    *,
    calibration_rows: list[dict[str, Any]],
    out_path: Path,
    title: str,
    summary_lines: list[str],
) -> None:
    """
    Write a "context" SVG: reliability plot + right-hand panel containing
    key metrics and a compact per-bin table.

    The canvas height is sized dynamically to avoid any clipping.
    """
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
    max_table_rows = 30
    if len(rows_sorted) > max_table_rows:
        head_n = max_table_rows // 2
        tail_n = max_table_rows - head_n - 1
        rows_table = rows_sorted[:head_n] + [{"_ellipsis": True}] + rows_sorted[-tail_n:]
    else:
        rows_table = rows_sorted

    summary_n = len(summary_lines)
    table_n = len(rows_table)
    required_panel_h = (
        24  # "Summary"
        + 18
        + (summary_n * 16)
        + 10
        + 18  # "Calibration bins"
        + 18  # header
        + 14  # divider + gap
        + (table_n * 14)
        + 40
    )
    plot_h = max(520, required_panel_h)
    h = pad_t + plot_h + pad_b

    pts = []
    for r in sorted(calibration_rows, key=lambda rr: float(rr.get("avg_p") or 0.0)):
        pts.append((float(r.get("avg_p") or 0.0), float(r.get("obs_rate") or 0.0), int(r.get("n") or 0)))

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

    # Connect points
    if len(pts) >= 2:
        d = "M " + " L ".join(f"{x_px(px):.2f} {y_px(oy):.2f}" for px, oy, _n in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="#1f77b4" stroke-width="2.5" opacity="0.85"/>')
    for px, oy, n in pts:
        rr = r_px(n)
        parts.append(
            f'<circle cx="{x_px(px):.2f}" cy="{y_px(oy):.2f}" r="{rr:.2f}" fill="#1f77b4" opacity="0.75" '
            f'stroke="#0b3d66" stroke-width="1"><title>avg_p={px:.4f}, obs={oy:.4f}, n={n}</title></circle>'
        )

    # Right panel
    parts.append(f'<rect x="{panel_x}" y="{pad_t}" width="{panel_w}" height="{plot_h}" fill="#fafafa" stroke="#ddd" stroke-width="1"/>')
    tx = panel_x + 14
    ty = pad_t + 24
    parts.append(
        f'<text x="{tx}" y="{ty}" text-anchor="start" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">Summary</text>'
    )
    ty += 18
    for line in summary_lines:
        parts.append(
            f'<text x="{tx}" y="{ty}" text-anchor="start" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="11" fill="#222">'
            f"{esc(line)}</text>"
        )
        ty += 16

    ty += 10
    parts.append(
        f'<text x="{tx}" y="{ty}" text-anchor="start" '
        'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#111">Calibration bins</text>'
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
            ap = float(r.get("avg_p") or 0.0)
            ob = float(r.get("obs_rate") or 0.0)
            gap = float(r.get("gap") or (ob - ap))
            line = f"{b:>3d}  [{lo:0.2f},{hi:0.2f}) {n:>6d}  {ap:0.4f}  {ob:0.4f}  {gap:+0.4f}"
        parts.append(
            f'<text x="{tx}" y="{ty}" text-anchor="start" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="10.5" fill="#222">'
            f"{esc(line)}</text>"
        )
        ty += 14

    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _load_evaluation_data(conn, season_start: int, artifact) -> pd.DataFrame:
    """
    Load evaluation data from ESPN tables for a specific season.
    
    Determines if interaction terms and opening odds are needed based on artifact feature_names.
    """
    use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in artifact.feature_names)
    use_opening_odds = any("opening" in fn.lower() for fn in artifact.feature_names)
    
    # Base query: ESPN probabilities + game state
    # Add opening odds CTE if needed
    opening_odds_cte = ""
    opening_odds_join = ""
    opening_odds_select = ""
    
    if use_opening_odds:
        opening_odds_cte = """
        opening_odds AS (
            -- Pivot opening odds by market_type and side
            SELECT 
                espn_game_id,
                MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'home') AS opening_moneyline_home,
                MAX(odds_decimal) FILTER (WHERE market_type = 'moneyline' AND side = 'away') AS opening_moneyline_away,
                MAX(line_value) FILTER (WHERE market_type = 'spread' AND side = 'home') AS opening_spread,
                MAX(line_value) FILTER (WHERE market_type = 'total' AND side = 'over') AS opening_total
            FROM external.sportsbook_odds_snapshots
            WHERE is_opening_line = TRUE
                AND espn_game_id IS NOT NULL
            GROUP BY espn_game_id
        ),
        """
        opening_odds_join = """
            LEFT JOIN opening_odds oo
                ON e.game_id = oo.espn_game_id
        """
        opening_odds_select = """
        ,
        oo.opening_moneyline_home,
        oo.opening_moneyline_away,
        oo.opening_spread,
        oo.opening_total
        """
    
    base_query = f"""
    WITH {opening_odds_cte}
    espn_base AS (
        SELECT 
            p.season_label,
            p.game_id,
            p.sequence_number,
            -- Normalize probabilities to 0-1 format
            CASE 
                WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0
                ELSE p.home_win_percentage
            END AS espn_home_prob,
            -- Game state from prob_event_state
            e.point_differential AS score_diff,
            e.time_remaining,
            e.home_score,
            e.away_score,
            -- Calculate period from time_remaining
            CASE 
                WHEN e.time_remaining IS NULL THEN NULL
                WHEN e.time_remaining > 2160 THEN 1  -- Q1: 2160-2880 seconds
                WHEN e.time_remaining > 1440 THEN 2  -- Q2: 1440-2160 seconds
                WHEN e.time_remaining > 720 THEN 3   -- Q3: 720-1440 seconds
                ELSE 4                               -- Q4: 0-720 seconds
            END AS period
        FROM espn.probabilities_raw_items p
        LEFT JOIN espn.prob_event_state e 
            ON p.game_id = e.game_id 
            AND p.event_id = e.event_id
        WHERE e.time_remaining IS NOT NULL
            AND e.point_differential IS NOT NULL
            AND CAST(SUBSTRING(p.season_label FROM '^([0-9]{{4}})') AS INTEGER) = %s
    ),
    espn_with_features AS (
        SELECT 
            *,
            -- Interaction term: score_diff / sqrt(time_remaining + 1)
            CASE 
                WHEN time_remaining IS NOT NULL AND time_remaining > 0 THEN
                    score_diff::NUMERIC / SQRT(time_remaining::NUMERIC + 1.0)
                ELSE NULL
            END AS score_diff_div_sqrt_time_remaining,
            -- Lagged probabilities using window functions
            LAG(espn_home_prob) OVER (
                PARTITION BY season_label, game_id 
                ORDER BY sequence_number
            ) AS espn_home_prob_lag_1,
            -- Delta (current - lag_1)
            espn_home_prob - LAG(espn_home_prob) OVER (
                PARTITION BY season_label, game_id 
                ORDER BY sequence_number
            ) AS espn_home_prob_delta_1
        FROM espn_base
    )
    SELECT DISTINCT ON (e.season_label, e.game_id, e.sequence_number)
        e.season_label,
        e.game_id,
        e.sequence_number,
        e.score_diff AS point_differential,
        e.time_remaining AS time_remaining_regulation,
        e.home_score,
        e.away_score,
        'unknown' AS possession,
        CASE 
            WHEN sg.home_score > sg.away_score THEN 0
            WHEN sg.away_score > sg.home_score THEN 1
            ELSE NULL
        END AS final_winning_team,
        CAST(SUBSTRING(e.season_label FROM '^([0-9]{{4}})') AS INTEGER) AS season_start,
        -- Calculate bucket_seconds_remaining (round down to nearest 60 seconds for grouping)
        CASE 
            WHEN e.time_remaining IS NOT NULL THEN
                (FLOOR(e.time_remaining / 60.0) * 60)::INTEGER
            ELSE NULL
        END AS bucket_seconds_remaining{opening_odds_select}
    """
    
    # Add interaction terms if needed
    if use_interaction_terms:
        interaction_select = """
        ,
        e.score_diff_div_sqrt_time_remaining,
        e.espn_home_prob,
        e.espn_home_prob_lag_1,
        e.espn_home_prob_delta_1,
        e.period
        """
    else:
        interaction_select = ""
    
    query = base_query + interaction_select + f"""
    FROM espn_with_features e
    LEFT JOIN espn.scoreboard_games sg 
        ON e.game_id = sg.event_id{opening_odds_join}
    ORDER BY e.season_label, e.game_id, e.sequence_number
    """
    
    # Suppress pandas warning about psycopg connection
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy.*")
        df = pd.read_sql(query, conn, params=(season_start,))
    
    # Compute opening odds engineered features if needed
    if use_opening_odds and len(df) > 0:
        from scripts.lib._winprob_lib import compute_opening_odds_features
        
        odds_features = compute_opening_odds_features(
            opening_moneyline_home=df['opening_moneyline_home'].to_numpy() if 'opening_moneyline_home' in df.columns else None,
            opening_moneyline_away=df['opening_moneyline_away'].to_numpy() if 'opening_moneyline_away' in df.columns else None,
            opening_spread=df['opening_spread'].to_numpy() if 'opening_spread' in df.columns else None,
            opening_total=df['opening_total'].to_numpy() if 'opening_total' in df.columns else None,
        )
        
        # Add engineered features to dataframe
        df['opening_prob_home_fair'] = odds_features['opening_prob_home_fair']
        df['opening_overround'] = odds_features['opening_overround']
    
    return df


def _setup_logging(verbose: bool) -> None:
    """Configure logging based on verbose flag."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )




def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dsn = get_dsn(args.dsn)
    
    _setup_logging(bool(args.verbose))
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info(f"Starting evaluation: artifact={artifact_path}, season_start={args.season_start}")

    art = load_artifact(artifact_path)
    logger.debug(f"Loaded artifact: version={art.version}, created_at={art.created_at_utc}")
    
    # Handle disable-calibration flag
    if bool(args.disable_calibration):
        logger.info("Disabling Platt calibration (evaluating base model only)")
        from scripts.lib._winprob_lib import WinProbArtifact
        art = WinProbArtifact(
            created_at_utc=art.created_at_utc,
            version=art.version,
            train_season_start_max=art.train_season_start_max,
            calib_season_start=art.calib_season_start,
            test_season_start=art.test_season_start,
            buckets_seconds_remaining=art.buckets_seconds_remaining,
            preprocess=art.preprocess,
            feature_names=art.feature_names,
            model=art.model,
            platt=None,  # Disable calibration
        )

    # Load evaluation data from database
    ss = int(args.season_start)
    logger.info(f"Loading evaluation data for season_start={ss}")
    load_start = time.time()
    with connect(dsn) as conn:
        df = _load_evaluation_data(conn, ss, art)
    logger.debug(f"Loaded {len(df)} rows from database in {time.time() - load_start:.2f}s")

    df = df[df["final_winning_team"].notna()].copy()
    logger.debug(f"After filtering for final_winning_team: {len(df)} rows")
    if len(df) == 0:
        raise SystemExit(f"No rows found for season_start={ss}")

    y = (df["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)
    logger.debug(f"Labels: {np.sum(y)} home wins, {len(y) - np.sum(y)} away wins")
    
    # Build design matrix with optional interaction terms
    logger.info("Building design matrix")
    matrix_start = time.time()
    build_matrix_kwargs = {
        "point_differential": df["point_differential"].to_numpy(),
        "time_remaining_regulation": df["time_remaining_regulation"].to_numpy(),
        "possession": df["possession"].astype(str).tolist(),
        "preprocess": art.preprocess,
    }
    
    # Add interaction terms if present in artifact
    use_interaction_terms = any("scaled" in fn and ("score_diff_div_sqrt" in fn or "espn_home_prob" in fn or "period" in fn) for fn in art.feature_names)
    logger.debug(f"Using interaction terms: {use_interaction_terms}")
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
    
    # Add opening odds features if present in artifact
    # Note: opening_prob_home_fair, opening_spread, opening_total are NOT features - they're baseline inputs
    use_opening_odds = any("opening" in fn.lower() for fn in art.feature_names)
    logger.debug(f"Using opening odds features: {use_opening_odds}")
    if use_opening_odds:
        if "opening_overround" in df.columns:
            build_matrix_kwargs["opening_overround"] = df["opening_overround"].astype(float).to_numpy()
        # Pass odds_nan_policy="keep" for CatBoost models
        build_matrix_kwargs["odds_nan_policy"] = "keep"
    
    X = build_design_matrix(**build_matrix_kwargs)
    logger.debug(f"Design matrix shape: {X.shape}, built in {time.time() - matrix_start:.2f}s")
    
    logger.info("Making predictions")
    predict_start = time.time()
    # Check if model uses baseline using the artifact flag
    uses_baseline = getattr(art, 'uses_opening_odds_baseline', None)
    if uses_baseline is None:
        # Fallback heuristic for older artifacts
        has_opening_odds_features = any("opening" in fn.lower() or "overround" in fn.lower() for fn in art.feature_names)
        opening_prob_not_a_feature = "opening_prob_home_fair" not in art.feature_names
        uses_baseline = has_opening_odds_features and opening_prob_not_a_feature
    
    if uses_baseline and "opening_prob_home_fair" in df.columns:
        p = predict_proba(
            art, 
            X=X,
            opening_prob_home_fair=df["opening_prob_home_fair"].astype(float).to_numpy(),
        )
    else:
        p = predict_proba(art, X=X)
    logger.debug(f"Predictions completed in {time.time() - predict_start:.2f}s")
    logger.debug(f"Prediction stats: mean={np.mean(p):.4f}, std={np.std(p):.4f}, min={np.min(p):.4f}, max={np.max(p):.4f}")

    # Overall metrics
    logger.info("Calculating overall metrics")
    metrics_start = time.time()
    overall = {
        "n": int(len(df)),
        "logloss": logloss(p, y),
        "brier": brier(p, y),
        "roc_auc": roc_auc(p, y),
        "ece_binned": ece_binned(p, y, bins=int(args.bins)),
        "prevalence_home_win": float(np.mean(y)),
    }
    logger.debug(f"Overall metrics calculated in {time.time() - metrics_start:.2f}s")
    logger.info(f"Overall metrics: logloss={overall['logloss']:.6f}, brier={overall['brier']:.6f}, ece={overall['ece_binned']:.6f}, auc={overall['roc_auc']:.6f}")

    # Calibration bins
    logger.info(f"Calculating calibration bins (bins={args.bins})")
    bins = max(1, int(args.bins))
    idx = np.minimum(bins - 1, np.maximum(0, np.floor(p * bins).astype(np.int32)))
    calib_rows: list[dict[str, Any]] = []
    for b in range(bins):
        mask = idx == b
        nb = int(np.sum(mask))
        if nb <= 0:
            continue
        avg_p = float(np.mean(p[mask]))
        obs = float(np.mean(y[mask]))
        lo = b / bins
        hi = (b + 1) / bins
        calib_rows.append({"bin": int(b), "range": [float(lo), float(hi)], "n": int(nb), "avg_p": avg_p, "obs_rate": obs, "gap": float(obs - avg_p)})
    logger.debug(f"Created {len(calib_rows)} calibration bins")

    # Per-bucket metrics (bucket_seconds_remaining)
    logger.info("Calculating per-bucket metrics")
    bucket_start = time.time()
    unique_buckets = sorted(df["bucket_seconds_remaining"].astype(int).unique().tolist(), reverse=True)
    logger.debug(f"Found {len(unique_buckets)} unique time buckets")
    
    per_bucket: list[dict[str, Any]] = []
    workers = max(1, int(args.workers))
    
    if workers > 1:
        logger.warning(f"--workers={workers} specified but parallel processing not yet implemented (artifact pickling limitations). Using sequential processing.")
    
    for i, b in enumerate(unique_buckets):
        if (i + 1) % 10 == 0:
            logger.debug(f"Processing bucket {i+1}/{len(unique_buckets)}: {b} seconds remaining")
        sub = df[df["bucket_seconds_remaining"].astype(int) == int(b)]
        yb = (sub["final_winning_team"].astype(int) == 0).astype(int).to_numpy(dtype=np.float64)
        
        # Build design matrix with optional interaction terms
        build_matrix_kwargs_b = {
            "point_differential": sub["point_differential"].to_numpy(),
            "time_remaining_regulation": sub["time_remaining_regulation"].to_numpy(),
            "possession": sub["possession"].astype(str).tolist(),
            "preprocess": art.preprocess,
        }
        
        if use_interaction_terms:
            if "score_diff_div_sqrt_time_remaining" in sub.columns:
                build_matrix_kwargs_b["score_diff_div_sqrt_time_remaining"] = sub["score_diff_div_sqrt_time_remaining"].astype(float).to_numpy()
            if "espn_home_prob" in sub.columns:
                build_matrix_kwargs_b["espn_home_prob"] = sub["espn_home_prob"].astype(float).to_numpy()
            if "espn_home_prob_lag_1" in sub.columns:
                build_matrix_kwargs_b["espn_home_prob_lag_1"] = sub["espn_home_prob_lag_1"].astype(float).to_numpy()
            if "espn_home_prob_delta_1" in sub.columns:
                build_matrix_kwargs_b["espn_home_prob_delta_1"] = sub["espn_home_prob_delta_1"].astype(float).to_numpy()
            if "period" in sub.columns:
                build_matrix_kwargs_b["period"] = sub["period"].astype(int).tolist()
        
        # Add opening odds features if present in artifact (same as overall metrics)
        # Note: opening_prob_home_fair, opening_spread, opening_total are NOT features - they're baseline inputs
        if use_opening_odds:
            if "opening_overround" in sub.columns:
                build_matrix_kwargs_b["opening_overround"] = sub["opening_overround"].astype(float).to_numpy()
            # Pass odds_nan_policy="keep" for CatBoost models
            build_matrix_kwargs_b["odds_nan_policy"] = "keep"
        
        Xb = build_design_matrix(**build_matrix_kwargs_b)
        # Check if model uses baseline using the artifact flag
        uses_baseline = getattr(art, 'uses_opening_odds_baseline', None)
        if uses_baseline is None:
            # Fallback heuristic for older artifacts
            has_opening_odds_features = any("opening" in fn.lower() or "overround" in fn.lower() for fn in art.feature_names)
            opening_prob_not_a_feature = "opening_prob_home_fair" not in art.feature_names
            uses_baseline = has_opening_odds_features and opening_prob_not_a_feature
        
        if uses_baseline and "opening_prob_home_fair" in sub.columns:
            pb = predict_proba(
                art, 
                X=Xb,
                opening_prob_home_fair=sub["opening_prob_home_fair"].astype(float).to_numpy(),
            )
        else:
            pb = predict_proba(art, X=Xb)
        per_bucket.append(
            {
                "bucket_seconds_remaining": int(b),
                "n": int(len(sub)),
                "logloss": logloss(pb, yb),
                "brier": brier(pb, yb),
                "roc_auc": roc_auc(pb, yb),
                "ece_binned": ece_binned(pb, yb, bins=bins),
                "prevalence_home_win": float(np.mean(yb)),
            }
        )
    
    logger.debug(f"Per-bucket metrics calculated in {time.time() - bucket_start:.2f}s")

    report = {
        "created_at_utc": utc_now_iso_compact(),
        "artifact_path": str(artifact_path),
        "artifact_meta": {
            "version": art.version,
            "created_at_utc": art.created_at_utc,
            "train_season_start_max": art.train_season_start_max,
            "calib_season_start": art.calib_season_start,
            "test_season_start": art.test_season_start,
            "buckets_seconds_remaining": art.buckets_seconds_remaining,
            "model_type": art.model_type,
            "catboost_model_path": art.catboost_model_path,
        },
        "eval": {
            "season_start": ss,
            "overall": overall,
            "calibration_bins": calib_rows,
            "per_bucket_seconds_remaining": per_bucket,
        },
    }
    logger.info("Writing JSON report")
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"overall logloss={overall['logloss']} brier={overall['brier']} ece={overall['ece_binned']} auc={overall['roc_auc']}")
    logger.info(f"Evaluation completed in {time.time() - start_time:.2f}s")

    if bool(args.plot_calibration):
        logger.info("Generating calibration plots")
        svg_path = out_path.with_suffix(".calibration.svg")
        _write_calibration_svg(rows=calib_rows, out_path=svg_path, title=f"WinProb Calibration — season_start={ss} n={overall['n']}")
        print(f"Wrote {svg_path}")
        
        # Generate JPEG version
        if CAIROSVG_AVAILABLE:
            jpeg_path = out_path.with_suffix(".calibration.jpg")
            try:
                _convert_svg_to_jpeg(svg_path, jpeg_path)
                print(f"Wrote {jpeg_path}")
            except Exception as e:
                logger.warning(f"Failed to generate JPEG: {e}")

        # Also write a context-rich SVG so the plot is self-contained for analysis.
        ctx_path = out_path.with_suffix(".calibration_context.svg")
        calibration_info = "none"
        if art.platt is not None:
            calibration_info = f"Platt: alpha={art.platt.alpha:.6f} beta={art.platt.beta:.6f}"
        elif art.isotonic is not None:
            calibration_info = "Isotonic: fitted"
        summary_lines = [
            f"season_start={ss}",
            f"n={overall['n']}",
            f"logloss={overall['logloss']}",
            f"brier={overall['brier']}",
            f"ece={overall['ece_binned']}",
            f"auc={overall['roc_auc']}",
            f"prevalence_home_win={overall['prevalence_home_win']}",
            f"bins={bins}",
            f"artifact_version={art.version}",
            f"artifact_created_at_utc={art.created_at_utc}",
            f"train_season_start_max={art.train_season_start_max}",
            f"calib_season_start={art.calib_season_start}",
            f"calibration={calibration_info}",
        ]
        _write_calibration_context_svg(
            calibration_rows=calib_rows,
            out_path=ctx_path,
            title=f"WinProb Calibration (with context) — season_start={ss}",
            summary_lines=summary_lines,
        )
        print(f"Wrote {ctx_path}")
        
        # Generate JPEG version of context plot
        if CAIROSVG_AVAILABLE:
            ctx_jpeg_path = out_path.with_suffix(".calibration_context.jpg")
            try:
                _convert_svg_to_jpeg(ctx_path, ctx_jpeg_path)
                print(f"Wrote {ctx_jpeg_path}")
            except Exception as e:
                logger.warning(f"Failed to generate context JPEG: {e}")
        
        logger.debug("Calibration plots generated")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


