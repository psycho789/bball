#!/usr/bin/env python3
"""
Generate a win probability chart as SVG for a single NBA game.

Data sources:
  - derived.espn_probabilities_raw_items: probability time series
  - derived.espn_prob_event_state: time_remaining, scores (joined by event_id)
  - data/raw/espn/scoreboard/*.json: team metadata (names, logos)

Output:
  - Static SVG file with dark theme, matching Polymarket-style visualization

Usage:
  python scripts/generate_winprob_chart.py --game-id 401736807 --out data/charts/winprob_game_401736807.svg
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


# =============================================================================
# NBA Team Colors (primary colors for each team)
# =============================================================================

NBA_TEAM_COLORS: dict[str, str] = {
    # Atlantic Division
    "BOS": "#007A33",  # Celtics green
    "BKN": "#000000",  # Nets black
    "NYK": "#F58426",  # Knicks orange
    "PHI": "#006BB6",  # 76ers blue
    "TOR": "#CE1141",  # Raptors red
    # Central Division
    "CHI": "#CE1141",  # Bulls red
    "CLE": "#860038",  # Cavaliers wine
    "DET": "#C8102E",  # Pistons red
    "IND": "#002D62",  # Pacers blue
    "MIL": "#00471B",  # Bucks green
    # Southeast Division
    "ATL": "#E03A3E",  # Hawks red
    "CHA": "#1D1160",  # Hornets purple
    "MIA": "#98002E",  # Heat red
    "ORL": "#0077C0",  # Magic blue
    "WAS": "#002B5C",  # Wizards blue
    # Northwest Division
    "DEN": "#0E2240",  # Nuggets blue
    "MIN": "#0C2340",  # Timberwolves blue
    "OKC": "#007AC1",  # Thunder blue
    "POR": "#E03A3E",  # Trail Blazers red
    "UTA": "#002B5C",  # Jazz blue
    "UTAH": "#002B5C",  # Jazz blue (alternate abbrev)
    # Pacific Division
    "GS": "#1D428A",   # Warriors blue
    "GSW": "#1D428A",  # Warriors blue (alternate)
    "LAC": "#C8102E",  # Clippers red
    "LAL": "#552583",  # Lakers purple
    "PHX": "#1D1160",  # Suns purple
    "SAC": "#5A2D81",  # Kings purple
    # Southwest Division
    "DAL": "#00538C",  # Mavericks blue
    "HOU": "#CE1141",  # Rockets red
    "MEM": "#5D76A9",  # Grizzlies blue
    "NO": "#0C2340",   # Pelicans blue
    "NOP": "#0C2340",  # Pelicans (alternate)
    "SA": "#C4CED4",   # Spurs silver
    "SAS": "#C4CED4",  # Spurs (alternate)
}

# Away team uses a lighter gray color
AWAY_LINE_COLOR = "#888888"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProbabilityPoint:
    """Single point in the probability time series."""
    sequence_number: int
    time_remaining: int  # seconds remaining in regulation (2880 = start, 0 = end)
    home_win_pct: float
    away_win_pct: float
    home_score: int
    away_score: int


@dataclass
class GameMetadata:
    """Team and score information for a game."""
    game_id: str
    home_team_abbr: str
    away_team_abbr: str
    home_team_name: str
    away_team_name: str
    final_home_score: int
    final_away_score: int
    home_won: bool


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_game_probabilities(conn: psycopg.Connection, game_id: str) -> list[ProbabilityPoint]:
    """
    Fetch probability time series for a game, joined with event state.
    
    Returns list of ProbabilityPoint ordered by sequence_number.
    """
    sql = """
    SELECT 
        p.sequence_number,
        e.time_remaining,
        p.home_win_percentage,
        p.away_win_percentage,
        e.home_score,
        e.away_score
    FROM derived.espn_probabilities_raw_items p
    JOIN derived.espn_prob_event_state e 
        ON p.game_id = e.game_id AND p.event_id = e.event_id
    WHERE p.game_id = %s
    ORDER BY p.sequence_number
    """
    rows = conn.execute(sql, (game_id,)).fetchall()
    
    if not rows:
        raise ValueError(f"No probability data found for game_id={game_id}")
    
    return [
        ProbabilityPoint(
            sequence_number=int(r[0]),
            time_remaining=int(r[1]) if r[1] is not None else 0,
            home_win_pct=float(r[2]) if r[2] is not None else 0.5,
            away_win_pct=float(r[3]) if r[3] is not None else 0.5,
            home_score=int(r[4]) if r[4] is not None else 0,
            away_score=int(r[5]) if r[5] is not None else 0,
        )
        for r in rows
    ]


def fetch_game_metadata_from_db(conn: psycopg.Connection, game_id: str) -> GameMetadata | None:
    """
    Try to fetch game metadata from espn_prob_event_state (final outcome).
    Returns None if not found (caller should try scoreboard JSON).
    """
    sql = """
    SELECT 
        e.final_winning_team,
        MAX(e.home_score) as final_home,
        MAX(e.away_score) as final_away
    FROM derived.espn_prob_event_state e
    WHERE e.game_id = %s
    GROUP BY e.final_winning_team
    """
    row = conn.execute(sql, (game_id,)).fetchone()
    if not row:
        return None
    
    final_winning_team = row[0]
    final_home = int(row[1]) if row[1] else 0
    final_away = int(row[2]) if row[2] else 0
    home_won = (final_winning_team == 0)
    
    # We don't have team names in DB, return partial
    return GameMetadata(
        game_id=game_id,
        home_team_abbr="HOME",
        away_team_abbr="AWAY",
        home_team_name="Home Team",
        away_team_name="Away Team",
        final_home_score=final_home,
        final_away_score=final_away,
        home_won=home_won,
    )


def find_scoreboard_for_game(game_id: str, scoreboard_dir: Path) -> dict[str, Any] | None:
    """
    Search scoreboard JSON files to find metadata for a game.
    Returns the event dict if found, None otherwise.
    """
    # Search through scoreboard files (this is slow but works)
    pattern = str(scoreboard_dir / "scoreboard_*.json")
    for fpath in glob.glob(pattern):
        if ".manifest" in fpath:
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            events = data.get("events", [])
            for event in events:
                if str(event.get("id")) == str(game_id):
                    return event
        except Exception:
            continue
    return None


def parse_scoreboard_event(event: dict[str, Any], game_id: str) -> GameMetadata:
    """Parse a scoreboard event dict into GameMetadata."""
    competitions = event.get("competitions", [{}])
    comp = competitions[0] if competitions else {}
    competitors = comp.get("competitors", [])
    
    home_team: dict[str, Any] = {}
    away_team: dict[str, Any] = {}
    for c in competitors:
        if c.get("homeAway") == "home":
            home_team = c
        elif c.get("homeAway") == "away":
            away_team = c
    
    home_abbr = home_team.get("team", {}).get("abbreviation", "HOME")
    away_abbr = away_team.get("team", {}).get("abbreviation", "AWAY")
    home_name = home_team.get("team", {}).get("displayName", "Home Team")
    away_name = away_team.get("team", {}).get("displayName", "Away Team")
    
    try:
        home_score = int(home_team.get("score", 0))
    except (ValueError, TypeError):
        home_score = 0
    try:
        away_score = int(away_team.get("score", 0))
    except (ValueError, TypeError):
        away_score = 0
    
    home_won = home_score > away_score
    
    return GameMetadata(
        game_id=game_id,
        home_team_abbr=home_abbr,
        away_team_abbr=away_abbr,
        home_team_name=home_name,
        away_team_name=away_name,
        final_home_score=home_score,
        final_away_score=away_score,
        home_won=home_won,
    )


def fetch_game_metadata(
    conn: psycopg.Connection,
    game_id: str,
    scoreboard_dir: Path,
) -> GameMetadata:
    """
    Fetch game metadata, trying scoreboard JSON first, then DB fallback.
    """
    # Try scoreboard JSON for full team info
    event = find_scoreboard_for_game(game_id, scoreboard_dir)
    if event:
        return parse_scoreboard_event(event, game_id)
    
    # Fall back to DB (partial info)
    db_meta = fetch_game_metadata_from_db(conn, game_id)
    if db_meta:
        return db_meta
    
    # Last resort: minimal metadata
    return GameMetadata(
        game_id=game_id,
        home_team_abbr="HOME",
        away_team_abbr="AWAY",
        home_team_name="Home Team",
        away_team_name="Away Team",
        final_home_score=0,
        final_away_score=0,
        home_won=True,
    )


# =============================================================================
# SVG Generation
# =============================================================================

def _esc(s: str) -> str:
    """Escape string for SVG XML."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _format_time(seconds_remaining: int) -> str:
    """Format time remaining as quarter + clock."""
    if seconds_remaining <= 0:
        return "Final"
    
    # 2880 = 48 minutes = 4 quarters of 12 min each
    elapsed = 2880 - seconds_remaining
    quarter = (elapsed // 720) + 1
    if quarter > 4:
        # Overtime
        ot_period = quarter - 4
        return f"OT{ot_period}"
    
    seconds_in_quarter = elapsed % 720
    minutes_left = 12 - (seconds_in_quarter // 60)
    secs_left = 60 - (seconds_in_quarter % 60)
    if secs_left == 60:
        secs_left = 0
        minutes_left -= 1
    
    return f"Q{quarter}"


def write_win_probability_chart_svg(
    points: list[ProbabilityPoint],
    metadata: GameMetadata,
    out_path: Path,
) -> None:
    """
    Generate and write an SVG win probability chart.
    
    Layout:
    - Canvas: 960 x 540 px
    - Dark background (#0a0a0a)
    - Header with team names and score
    - Two probability lines (home team color, away gray)
    - X-axis: game time (Q1, Q2, Q3, Q4)
    - Y-axis: 0% to 100%
    - Final probability annotations
    """
    # Canvas dimensions
    W = 960
    H = 540
    PAD_L = 60
    PAD_R = 100
    PAD_T = 90
    PAD_B = 50
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B
    
    # Colors
    BG_COLOR = "#0a0a0a"
    GRID_COLOR = "#1a1a1a"
    TEXT_COLOR = "#d1d4dc"
    AXIS_COLOR = "#333333"
    
    # Team colors
    home_color = NBA_TEAM_COLORS.get(metadata.home_team_abbr, "#1f77b4")
    away_color = AWAY_LINE_COLOR
    
    # Coordinate transforms
    def x_px(time_remaining: float) -> float:
        """Convert time_remaining (2880 → 0) to x pixel (left → right)."""
        elapsed = 2880 - time_remaining
        # Clamp to regulation (0-2880)
        elapsed = max(0, min(2880, elapsed))
        return PAD_L + (elapsed / 2880) * PLOT_W
    
    def y_px(prob: float) -> float:
        """Convert probability (0 → 1) to y pixel (bottom → top)."""
        prob = max(0, min(1, prob))
        return PAD_T + (1 - prob) * PLOT_H
    
    # Build SVG parts
    parts: list[str] = []
    
    # SVG header
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    
    # Background
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG_COLOR}"/>')
    
    # Header: Team names and score
    header_y = 35
    # Away team (left)
    parts.append(
        f'<text x="{W/2 - 120}" y="{header_y}" text-anchor="end" '
        f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="24" font-weight="bold" fill="{away_color}">'
        f'{_esc(metadata.away_team_abbr)}</text>'
    )
    # Score
    score_text = f"{metadata.final_away_score}  -  {metadata.final_home_score}"
    parts.append(
        f'<text x="{W/2}" y="{header_y}" text-anchor="middle" '
        f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="28" font-weight="bold" fill="{TEXT_COLOR}">'
        f'{_esc(score_text)}</text>'
    )
    # Home team (right)
    parts.append(
        f'<text x="{W/2 + 120}" y="{header_y}" text-anchor="start" '
        f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="24" font-weight="bold" fill="{home_color}">'
        f'{_esc(metadata.home_team_abbr)}</text>'
    )
    
    # Subtitle: team full names
    subtitle_y = 58
    parts.append(
        f'<text x="{W/2}" y="{subtitle_y}" text-anchor="middle" '
        f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="14" fill="#666666">'
        f'{_esc(metadata.away_team_name)} @ {_esc(metadata.home_team_name)}</text>'
    )
    
    # Plot area background
    parts.append(f'<rect x="{PAD_L}" y="{PAD_T}" width="{PLOT_W}" height="{PLOT_H}" fill="{BG_COLOR}" stroke="{AXIS_COLOR}" stroke-width="1"/>')
    
    # Grid lines (horizontal - probability levels)
    for pct in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yy = y_px(pct)
        parts.append(f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{PAD_L + PLOT_W}" y2="{yy:.1f}" stroke="{GRID_COLOR}" stroke-width="1"/>')
        # Y-axis labels (right side)
        label = f"{int(pct * 100)}%"
        parts.append(
            f'<text x="{PAD_L + PLOT_W + 10}" y="{yy + 4:.1f}" text-anchor="start" '
            f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="{TEXT_COLOR}">'
            f'{label}</text>'
        )
    
    # Grid lines (vertical - quarter boundaries)
    for q in range(5):  # 0=start, 1=end Q1, 2=end Q2, 3=end Q3, 4=end Q4
        time_remaining = 2880 - (q * 720)
        xx = x_px(time_remaining)
        parts.append(f'<line x1="{xx:.1f}" y1="{PAD_T}" x2="{xx:.1f}" y2="{PAD_T + PLOT_H}" stroke="{GRID_COLOR}" stroke-width="1"/>')
        # X-axis labels
        if q == 0:
            label = "Start"
        elif q == 4:
            label = "End"
        else:
            label = f"Q{q}"
        parts.append(
            f'<text x="{xx:.1f}" y="{PAD_T + PLOT_H + 20}" text-anchor="middle" '
            f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="12" fill="{TEXT_COLOR}">'
            f'{label}</text>'
        )
    
    # 50% reference line (dashed)
    y50 = y_px(0.5)
    parts.append(f'<line x1="{PAD_L}" y1="{y50:.1f}" x2="{PAD_L + PLOT_W}" y2="{y50:.1f}" stroke="#444444" stroke-width="1" stroke-dasharray="4,4"/>')
    
    # Build probability paths
    home_path_points: list[str] = []
    away_path_points: list[str] = []
    
    for pt in points:
        xx = x_px(pt.time_remaining)
        home_yy = y_px(pt.home_win_pct)
        away_yy = y_px(pt.away_win_pct)
        home_path_points.append(f"{xx:.1f} {home_yy:.1f}")
        away_path_points.append(f"{xx:.1f} {away_yy:.1f}")
    
    # Draw away line first (behind home line)
    if away_path_points:
        away_d = "M " + " L ".join(away_path_points)
        parts.append(f'<path d="{away_d}" fill="none" stroke="{away_color}" stroke-width="2.5" opacity="0.9"/>')
    
    # Draw home line
    if home_path_points:
        home_d = "M " + " L ".join(home_path_points)
        parts.append(f'<path d="{home_d}" fill="none" stroke="{home_color}" stroke-width="2.5" opacity="0.9"/>')
    
    # Final probability annotations
    if points:
        last_pt = points[-1]
        home_final_pct = int(round(last_pt.home_win_pct * 100))
        away_final_pct = int(round(last_pt.away_win_pct * 100))
        
        # Position at right edge of chart
        final_x = PAD_L + PLOT_W + 15
        
        # Home probability (upper or lower based on who won)
        home_final_y = y_px(last_pt.home_win_pct) + 5
        parts.append(
            f'<text x="{final_x}" y="{home_final_y:.1f}" text-anchor="start" '
            f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="32" font-weight="bold" fill="{home_color}">'
            f'{home_final_pct}%</text>'
        )
        
        # Away probability
        away_final_y = y_px(last_pt.away_win_pct) + 5
        parts.append(
            f'<text x="{final_x}" y="{away_final_y:.1f}" text-anchor="start" '
            f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="32" font-weight="bold" fill="{away_color}">'
            f'{away_final_pct}%</text>'
        )
    
    # Footer: data source note
    parts.append(
        f'<text x="{PAD_L}" y="{H - 10}" text-anchor="start" '
        f'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="10" fill="#444444">'
        f'Data: ESPN Win Probability | Game ID: {_esc(metadata.game_id)}</text>'
    )
    
    # Close SVG
    parts.append("</svg>")
    
    # Write file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a win probability chart SVG for an NBA game.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_winprob_chart.py --game-id 401736807 --out data/charts/winprob_game_401736807.svg
  python scripts/generate_winprob_chart.py --game-id 401736809 --out data/charts/winprob_game_401736809.svg
        """,
    )
    p.add_argument("--game-id", required=True, help="ESPN game/competition ID (e.g., 401736807)")
    p.add_argument("--out", required=True, help="Output SVG file path")
    p.add_argument("--dsn", default=None, help="Database connection string (default: $DATABASE_URL)")
    p.add_argument(
        "--scoreboard-dir",
        default="data/raw/espn/scoreboard",
        help="Directory containing scoreboard JSON files (default: data/raw/espn/scoreboard)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    
    dsn = get_dsn(args.dsn)
    out_path = Path(args.out)
    scoreboard_dir = Path(args.scoreboard_dir)
    
    print(f"[generate_winprob_chart] game_id={args.game_id}")
    print(f"[generate_winprob_chart] output={out_path}")
    
    with psycopg.connect(dsn) as conn:
        # Fetch probability data
        print(f"[generate_winprob_chart] Fetching probability data...")
        points = fetch_game_probabilities(conn, args.game_id)
        print(f"[generate_winprob_chart] Found {len(points)} probability points")
        
        # Fetch metadata
        print(f"[generate_winprob_chart] Fetching game metadata...")
        metadata = fetch_game_metadata(conn, args.game_id, scoreboard_dir)
        print(f"[generate_winprob_chart] {metadata.away_team_abbr} @ {metadata.home_team_abbr}: {metadata.final_away_score} - {metadata.final_home_score}")
        
        # Generate SVG
        print(f"[generate_winprob_chart] Generating SVG...")
        write_win_probability_chart_svg(points, metadata, out_path)
        
    print(f"[generate_winprob_chart] Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







