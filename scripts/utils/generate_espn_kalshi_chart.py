#!/usr/bin/env python3
"""
Generate SVG chart comparing ESPN win probabilities vs Kalshi prediction market bid-ask ranges.

Creates a multi-panel visualization showing:
- ESPN probability line (blue)
- Kalshi bid-ask band (gray shaded area)
- Points outside the band highlighted in red

Design pattern: SVG template-based generation
Big O: O(n) where n = total sample comparisons across all games
"""

import json
from pathlib import Path
from typing import Any


def parse_range(range_str: str) -> tuple[float, float]:
    """Parse '44-45' into (44.0, 45.0)"""
    parts = range_str.split('-')
    return float(parts[0]), float(parts[1])


def generate_game_panel(
    game: dict[str, Any],
    panel_idx: int,
    panel_width: float,
    panel_height: float,
    x_offset: float,
    y_offset: float
) -> str:
    """Generate SVG elements for a single game panel."""
    
    samples = game.get('sample_comparisons', [])
    if not samples:
        return ''
    
    # Game info
    home = game['home_team']
    away = game['away_team']
    result = 'HOME' if game['kalshi_result'] == 'yes' else 'AWAY'
    outside_pct = game['outside_bid_ask_pct']
    avg_dev = game['avg_deviation']
    
    # Chart dimensions within panel
    chart_margin_left = 45
    chart_margin_right = 10
    chart_margin_top = 35
    chart_margin_bottom = 25
    chart_width = panel_width - chart_margin_left - chart_margin_right
    chart_height = panel_height - chart_margin_top - chart_margin_bottom
    
    # Data bounds - probabilities are 0-100
    y_min, y_max = 0, 100
    x_min = 0
    x_max = len(samples) - 1 if len(samples) > 1 else 1
    
    def scale_x(i: int) -> float:
        return x_offset + chart_margin_left + (i / max(x_max, 1)) * chart_width
    
    def scale_y(val: float) -> float:
        return y_offset + chart_margin_top + (1 - (val - y_min) / (y_max - y_min)) * chart_height
    
    elements = []
    
    # Panel background
    elements.append(f'''
    <rect x="{x_offset}" y="{y_offset}" width="{panel_width}" height="{panel_height}" 
          fill="#1a1a2e" stroke="#2a2a4e" stroke-width="1" rx="4"/>
    ''')
    
    # Title
    title = f"{away} @ {home}"
    subtitle = f"Winner: {result} | {outside_pct:.1f}% outside | Avg dev: {avg_dev:.1f}¢"
    elements.append(f'''
    <text x="{x_offset + panel_width/2}" y="{y_offset + 15}" 
          text-anchor="middle" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="12" font-weight="600">
        {title}
    </text>
    <text x="{x_offset + panel_width/2}" y="{y_offset + 28}" 
          text-anchor="middle" fill="#888" font-family="Inter, sans-serif" font-size="9">
        {subtitle}
    </text>
    ''')
    
    # Y-axis labels
    for y_val in [0, 25, 50, 75, 100]:
        y_pos = scale_y(y_val)
        elements.append(f'''
        <text x="{x_offset + chart_margin_left - 5}" y="{y_pos + 3}" 
              text-anchor="end" fill="#666" font-family="Inter, sans-serif" font-size="8">
            {y_val}%
        </text>
        <line x1="{x_offset + chart_margin_left}" y1="{y_pos}" 
              x2="{x_offset + panel_width - chart_margin_right}" y2="{y_pos}" 
              stroke="#2a2a4e" stroke-width="0.5" stroke-dasharray="2,2"/>
        ''')
    
    # Build Kalshi band path (bid low to ask high)
    band_points_top = []  # Ask high
    band_points_bottom = []  # Bid low
    
    for i, s in enumerate(samples):
        bid_low, bid_high = parse_range(s['kalshi_bid_range'])
        ask_low, ask_high = parse_range(s['kalshi_ask_range'])
        
        x = scale_x(i)
        band_points_top.append(f"{x},{scale_y(ask_high)}")
        band_points_bottom.append(f"{x},{scale_y(bid_low)}")
    
    # Create closed polygon for band
    band_path = ' '.join(band_points_top) + ' ' + ' '.join(reversed(band_points_bottom))
    elements.append(f'''
    <polygon points="{band_path}" fill="rgba(100, 149, 237, 0.2)" stroke="none"/>
    ''')
    
    # Kalshi mid-line (average of bid and ask)
    mid_points = []
    for i, s in enumerate(samples):
        bid_low, bid_high = parse_range(s['kalshi_bid_range'])
        ask_low, ask_high = parse_range(s['kalshi_ask_range'])
        mid = (bid_low + ask_high) / 2
        mid_points.append(f"{scale_x(i)},{scale_y(mid)}")
    
    elements.append(f'''
    <polyline points="{' '.join(mid_points)}" 
              fill="none" stroke="rgba(100, 149, 237, 0.6)" stroke-width="1" stroke-dasharray="3,3"/>
    ''')
    
    # ESPN probability line
    espn_points = []
    for i, s in enumerate(samples):
        espn_points.append(f"{scale_x(i)},{scale_y(s['espn_prob'])}")
    
    elements.append(f'''
    <polyline points="{' '.join(espn_points)}" 
              fill="none" stroke="#4ade80" stroke-width="1.5"/>
    ''')
    
    # Highlight points outside range
    for i, s in enumerate(samples):
        if not s['within_range']:
            x = scale_x(i)
            y = scale_y(s['espn_prob'])
            elements.append(f'''
            <circle cx="{x}" cy="{y}" r="2" fill="#ef4444" opacity="0.7"/>
            ''')
    
    return '\n'.join(elements)


def generate_summary_bar_chart(
    games: list[dict[str, Any]],
    width: float,
    height: float,
    y_offset: float
) -> str:
    """Generate a bar chart showing outside % for each game."""
    
    elements = []
    margin_left = 80
    margin_right = 20
    margin_top = 30
    margin_bottom = 20
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    
    bar_width = chart_width / len(games) * 0.7
    bar_gap = chart_width / len(games) * 0.3
    
    # Background
    elements.append(f'''
    <rect x="0" y="{y_offset}" width="{width}" height="{height}" 
          fill="#0f0f1a" stroke="none"/>
    ''')
    
    # Title
    elements.append(f'''
    <text x="{width/2}" y="{y_offset + 20}" 
          text-anchor="middle" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="14" font-weight="600">
        ESPN Probability Outside Kalshi Bid-Ask Range (%)
    </text>
    ''')
    
    # Bars
    max_pct = 100
    for i, game in enumerate(games):
        pct = game['outside_bid_ask_pct']
        bar_height = (pct / max_pct) * chart_height
        x = margin_left + i * (bar_width + bar_gap) + bar_gap / 2
        y = y_offset + margin_top + chart_height - bar_height
        
        # Gradient color based on percentage
        if pct > 90:
            color = "#ef4444"  # Red
        elif pct > 80:
            color = "#f97316"  # Orange
        else:
            color = "#4ade80"  # Green
        
        label = f"{game['away_team']}@{game['home_team']}"
        
        elements.append(f'''
        <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" 
              fill="{color}" rx="2" opacity="0.8"/>
        <text x="{x + bar_width/2}" y="{y - 5}" 
              text-anchor="middle" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="10">
            {pct:.0f}%
        </text>
        <text x="{x + bar_width/2}" y="{y_offset + margin_top + chart_height + 12}" 
              text-anchor="middle" fill="#888" font-family="Inter, sans-serif" font-size="9" 
              transform="rotate(-30 {x + bar_width/2} {y_offset + margin_top + chart_height + 12})">
            {label}
        </text>
        ''')
    
    return '\n'.join(elements)


def generate_legend(width: float, y_offset: float) -> str:
    """Generate chart legend with comprehensive key."""
    return f'''
    <g transform="translate(20, {y_offset})">
        <!-- Legend box -->
        <rect x="0" y="0" width="{width - 40}" height="70" fill="#1a1a2e" rx="6" stroke="#2a2a4e" stroke-width="1"/>
        
        <!-- Title -->
        <text x="{(width-40)/2}" y="16" text-anchor="middle" fill="#ffffff" font-family="Inter, sans-serif" font-size="11" font-weight="600">CHART KEY</text>
        
        <!-- Row 1: 4 items evenly spaced -->
        <!-- Item 1: ESPN line -->
        <line x1="25" y1="35" x2="55" y2="35" stroke="#4ade80" stroke-width="2.5"/>
        <text x="62" y="38" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="10">ESPN Prob</text>
        
        <!-- Item 2: Kalshi band -->
        <rect x="160" y="28" width="30" height="14" fill="rgba(100, 149, 237, 0.3)" stroke="rgba(100, 149, 237, 0.6)" stroke-width="1"/>
        <text x="197" y="38" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="10">Kalshi Bid-Ask</text>
        
        <!-- Item 3: Kalshi mid -->
        <line x1="320" y1="35" x2="350" y2="35" stroke="rgba(100, 149, 237, 0.8)" stroke-width="1.5" stroke-dasharray="4,3"/>
        <text x="357" y="38" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="10">Kalshi Mid</text>
        
        <!-- Item 4: Outside point -->
        <circle cx="475" cy="35" r="4" fill="#ef4444"/>
        <text x="485" y="38" fill="#e0e0e0" font-family="Inter, sans-serif" font-size="10">Outside Range</text>
        
        <!-- Row 2: Bar chart explanation -->
        <text x="630" y="38" fill="#888" font-family="Inter, sans-serif" font-size="9">Bottom bars:</text>
        <rect x="700" y="29" width="14" height="12" fill="#4ade80" rx="2"/>
        <text x="718" y="38" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="9">&lt;30%</text>
        <rect x="760" y="29" width="14" height="12" fill="#f97316" rx="2"/>
        <text x="778" y="38" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="9">30-80%</text>
        <rect x="830" y="29" width="14" height="12" fill="#ef4444" rx="2"/>
        <text x="848" y="38" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="9">&gt;80%</text>
        
        <!-- Row 2: Description -->
        <text x="{(width-40)/2}" y="58" text-anchor="middle" fill="#666" font-family="Inter, sans-serif" font-size="9">
            Green line = ESPN home win probability | Blue band = Kalshi market range | Red dots = ESPN outside market range
        </text>
    </g>
    '''


def generate_svg(games: list[dict[str, Any]], output_path: Path) -> None:
    """Generate the complete SVG visualization."""
    
    # Layout constants
    svg_width = 1000
    panel_width = 480
    panel_height = 180
    panels_per_row = 2
    summary_height = 120
    legend_height = 85  # Compact legend
    padding = 20
    
    # Calculate grid
    num_games = len(games)
    num_rows = (num_games + panels_per_row - 1) // panels_per_row
    panels_height = num_rows * (panel_height + padding)
    total_height = legend_height + summary_height + panels_height + padding * 3
    
    svg_parts = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {total_height}" 
     width="{svg_width}" height="{total_height}">
    
    <!-- Background -->
    <rect width="100%" height="100%" fill="#0a0a14"/>
    
    <!-- Title -->
    <text x="{svg_width/2}" y="30" text-anchor="middle" fill="#ffffff" 
          font-family="Inter, sans-serif" font-size="18" font-weight="700">
        ESPN Win Probability vs Kalshi Prediction Market
    </text>
    <text x="{svg_width/2}" y="50" text-anchor="middle" fill="#888" 
          font-family="Inter, sans-serif" font-size="12">
        Comparing model probabilities to market bid-ask spreads during NBA games
    </text>
    ''']
    
    # Legend
    svg_parts.append(generate_legend(svg_width, 55))
    
    # Game panels
    for i, game in enumerate(games):
        row = i // panels_per_row
        col = i % panels_per_row
        x_offset = padding + col * (panel_width + padding)
        y_offset = legend_height + padding + row * (panel_height + padding)
        
        svg_parts.append(generate_game_panel(
            game, i, panel_width, panel_height, x_offset, y_offset
        ))
    
    # Summary bar chart
    summary_y = legend_height + panels_height + padding * 2
    svg_parts.append(generate_summary_bar_chart(games, svg_width, summary_height, summary_y))
    
    svg_parts.append('</svg>')
    
    svg_content = '\n'.join(svg_parts)
    output_path.write_text(svg_content)
    print(f"Generated: {output_path}")


def main() -> None:
    # Load comparison data
    data_path = Path(__file__).parent.parent / 'data' / 'reports' / 'espn_kalshi_comparison.json'
    
    with open(data_path) as f:
        games = json.load(f)
    
    # Filter to games with sample comparisons
    games_with_data = [g for g in games if g.get('sample_comparisons')]
    
    print(f"Loaded {len(games_with_data)} games with comparison data")
    
    # Generate SVG
    output_path = data_path.parent / 'espn_kalshi_comparison.svg'
    generate_svg(games_with_data, output_path)


if __name__ == '__main__':
    main()

