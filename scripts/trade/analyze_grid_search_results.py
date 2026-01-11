#!/usr/bin/env python3
"""
Analyze grid search results and generate visualizations with pattern detection.

Design Pattern: Visualization Strategy Pattern
Algorithm: 2D visualization of performance surface with pattern analysis
Big O: O(k) where k = number of parameter combinations

This script reads grid search results and generates visualizations plus pattern detection summary.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300


def load_results(results_dir: Path, split: str) -> pd.DataFrame:
    """Load results CSV for a split."""
    csv_path = results_dir / f'grid_results_{split}.csv'
    if not csv_path.exists():
        raise FileNotFoundError(f"Results file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    return df


def load_final_selection(results_dir: Path) -> dict[str, Any]:
    """Load final selection JSON."""
    selection_path = results_dir / 'final_selection.json'
    if not selection_path.exists():
        return None
    
    with open(selection_path, 'r') as f:
        return json.load(f)


def create_heatmap(
    df: pd.DataFrame,
    value_col: str,
    title: str,
    output_path: Path,
    chosen_params: dict[str, Any] = None
):
    """
    Create a heatmap from grid search results.
    
    Args:
        df: DataFrame with entry_threshold, exit_threshold, and value_col
        value_col: Column name to use for color mapping
        title: Plot title
        output_path: Path to save PNG
        chosen_params: Optional dict with 'entry_threshold' and 'exit_threshold' to mark
    """
    # Pivot data for heatmap
    pivot = df.pivot(index='exit_threshold', columns='entry_threshold', values=value_col)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Create heatmap
    im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
    
    # Set ticks and labels
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f'{x:.3f}' for x in pivot.columns], rotation=45, ha='right')
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f'{y:.3f}' for y in pivot.index])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(value_col.replace('_', ' ').title(), rotation=270, labelpad=20)
    
    # Mark chosen params if provided
    if chosen_params:
        entry = chosen_params.get('entry_threshold')
        exit_val = chosen_params.get('exit_threshold')
        if entry is not None and exit_val is not None:
            # Find indices
            try:
                entry_idx = list(pivot.columns).index(entry)
                exit_idx = list(pivot.index).index(exit_val)
                # Mark with a star
                ax.plot(entry_idx, exit_idx, 'k*', markersize=20, markeredgewidth=2, markeredgecolor='white')
            except ValueError:
                pass  # Chosen params not in grid
    
    ax.set_xlabel('Entry Threshold')
    ax.set_ylabel('Exit Threshold')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Saved {output_path}")


def create_marginal_effects(df: pd.DataFrame, output_path: Path):
    """
    Create marginal effect plots for entry and exit thresholds.
    
    Args:
        df: DataFrame with results
        output_path: Path to save PNG
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Entry threshold marginal effect
    entry_marginal = df.groupby('entry_threshold')['net_profit_dollars'].agg(['mean', 'std']).reset_index()
    ax1.plot(entry_marginal['entry_threshold'], entry_marginal['mean'], 'o-', linewidth=2, markersize=6)
    ax1.fill_between(
        entry_marginal['entry_threshold'],
        entry_marginal['mean'] - entry_marginal['std'],
        entry_marginal['mean'] + entry_marginal['std'],
        alpha=0.3
    )
    ax1.set_xlabel('Entry Threshold')
    ax1.set_ylabel('Mean Net Profit (Dollars)')
    ax1.set_title('Marginal Effect: Entry Threshold')
    ax1.grid(True, alpha=0.3)
    
    # Exit threshold marginal effect
    exit_marginal = df.groupby('exit_threshold')['net_profit_dollars'].agg(['mean', 'std']).reset_index()
    ax2.plot(exit_marginal['exit_threshold'], exit_marginal['mean'], 'o-', linewidth=2, markersize=6, color='orange')
    ax2.fill_between(
        exit_marginal['exit_threshold'],
        exit_marginal['mean'] - exit_marginal['std'],
        exit_marginal['mean'] + exit_marginal['std'],
        alpha=0.3,
        color='orange'
    )
    ax2.set_xlabel('Exit Threshold')
    ax2.set_ylabel('Mean Net Profit (Dollars)')
    ax2.set_title('Marginal Effect: Exit Threshold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Saved {output_path}")


def create_tradeoff_scatter(df: pd.DataFrame, output_path: Path):
    """
    Create tradeoff scatter plot: num_trades vs net_profit_dollars, colored by entry threshold.
    
    Args:
        df: DataFrame with results
        output_path: Path to save PNG
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    scatter = ax.scatter(
        df['num_trades'],
        df['net_profit_dollars'],
        c=df['entry_threshold'],
        cmap='viridis',
        s=50,
        alpha=0.6,
        edgecolors='black',
        linewidth=0.5
    )
    
    ax.set_xlabel('Number of Trades')
    ax.set_ylabel('Net Profit (Dollars)')
    ax.set_title('Tradeoff: Trade Frequency vs. Profitability')
    ax.grid(True, alpha=0.3)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Entry Threshold', rotation=270, labelpad=20)
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Saved {output_path}")


def detect_patterns(df_train: pd.DataFrame, df_valid: pd.DataFrame) -> dict[str, Any]:
    """
    Detect patterns in grid search results.
    
    Args:
        df_train: Training results DataFrame
        df_valid: Validation results DataFrame
    
    Returns:
        Dictionary with pattern detection results
    """
    patterns = {}
    
    # 1. Profit-positive region boundary (roughly)
    valid_profitable = df_valid[df_valid['net_profit_dollars'] > 0]
    if len(valid_profitable) > 0:
        entry_profitable = sorted(valid_profitable['entry_threshold'].unique())
        exit_profitable = sorted(valid_profitable['exit_threshold'].unique())
        patterns['profit_positive_boundary'] = {
            'entry_thresholds': entry_profitable,
            'exit_thresholds': exit_profitable,
            'shape': 'convex' if len(entry_profitable) > 1 and len(exit_profitable) > 1 else 'irregular'
        }
    else:
        patterns['profit_positive_boundary'] = {
            'entry_thresholds': [],
            'exit_thresholds': [],
            'shape': 'none'
        }
    
    # 2. Monotonicity (using marginal curves)
    entry_marginal = df_valid.groupby('entry_threshold')['net_profit_dollars'].mean().reset_index()
    exit_marginal = df_valid.groupby('exit_threshold')['net_profit_dollars'].mean().reset_index()
    
    entry_diff = entry_marginal['net_profit_dollars'].diff().dropna()
    exit_diff = exit_marginal['net_profit_dollars'].diff().dropna()
    
    entry_monotonic = 'non-monotonic'
    if len(entry_diff) > 0:
        if all(entry_diff >= 0):
            entry_monotonic = 'monotonic increasing'
        elif all(entry_diff <= 0):
            entry_monotonic = 'monotonic decreasing'
    
    exit_monotonic = 'non-monotonic'
    if len(exit_diff) > 0:
        if all(exit_diff >= 0):
            exit_monotonic = 'monotonic increasing'
        elif all(exit_diff <= 0):
            exit_monotonic = 'monotonic decreasing'
    
    patterns['monotonicity'] = {
        'entry_threshold': entry_monotonic,
        'exit_threshold': exit_monotonic
    }
    
    # 3. Robust plateau vs sharp peak (region within 10% of best on VALID)
    best_valid = df_valid.loc[df_valid['net_profit_dollars'].idxmax()]
    best_profit = best_valid['net_profit_dollars']
    threshold_10pct = best_profit * 0.9
    
    robust_region = df_valid[df_valid['net_profit_dollars'] >= threshold_10pct]
    
    if len(robust_region) > 1:
        entry_range = (robust_region['entry_threshold'].min(), robust_region['entry_threshold'].max())
        exit_range = (robust_region['exit_threshold'].min(), robust_region['exit_threshold'].max())
        patterns['robustness'] = {
            'type': 'broad_plateau',
            'entry_range': entry_range,
            'exit_range': exit_range,
            'size': len(robust_region),
            'size_category': 'large' if len(robust_region) > 10 else 'medium' if len(robust_region) > 5 else 'small'
        }
    else:
        patterns['robustness'] = {
            'type': 'sharp_peak',
            'entry_range': (best_valid['entry_threshold'], best_valid['entry_threshold']),
            'exit_range': (best_valid['exit_threshold'], best_valid['exit_threshold']),
            'size': 1,
            'size_category': 'small'
        }
    
    # 4. Stability: top 5 train combos and their valid profits + rank correlation
    top_5_train = df_train.nlargest(5, 'net_profit_dollars')[['entry_threshold', 'exit_threshold', 'net_profit_dollars']]
    
    stability_data = []
    for _, row in top_5_train.iterrows():
        entry = row['entry_threshold']
        exit_val = row['exit_threshold']
        train_profit = row['net_profit_dollars']
        
        # Find matching valid result
        valid_match = df_valid[
            (df_valid['entry_threshold'] == entry) &
            (df_valid['exit_threshold'] == exit_val)
        ]
        
        if len(valid_match) > 0:
            valid_profit = valid_match.iloc[0]['net_profit_dollars']
            stability_data.append({
                'entry': entry,
                'exit': exit_val,
                'train_profit': train_profit,
                'valid_profit': valid_profit,
                'stable': abs(train_profit - valid_profit) < abs(train_profit) * 0.2  # Within 20%
            })
    
    # Rank correlation
    train_ranks = df_train.nlargest(len(df_train), 'net_profit_dollars').reset_index(drop=True)
    train_ranks['train_rank'] = range(len(train_ranks))
    
    # Merge with valid to get valid ranks
    merged = train_ranks.merge(
        df_valid[['entry_threshold', 'exit_threshold', 'net_profit_dollars']],
        on=['entry_threshold', 'exit_threshold'],
        how='inner',
        suffixes=('_train', '_valid')
    )
    merged = merged.sort_values('net_profit_dollars_valid', ascending=False).reset_index(drop=True)
    merged['valid_rank'] = range(len(merged))
    
    if len(merged) > 1:
        rank_correlation, _ = stats.spearmanr(merged['train_rank'], merged['valid_rank'])
    else:
        rank_correlation = 0.0
    
    patterns['stability'] = {
        'top_5_train': stability_data,
        'rank_correlation': rank_correlation
    }
    
    # 5. Optimal region
    best_entry = best_valid['entry_threshold']
    best_exit = best_valid['exit_threshold']
    
    patterns['optimal_region'] = {
        'best_combo': {
            'entry_threshold': best_entry,
            'exit_threshold': best_exit
        },
        'robust_region': {
            'entry_range': patterns['robustness']['entry_range'],
            'exit_range': patterns['robustness']['exit_range']
        }
    }
    
    return patterns


def print_pattern_summary(patterns: dict[str, Any], final_selection: dict[str, Any] = None):
    """Print pattern detection summary to console."""
    print("\n" + "=" * 70)
    print("PATTERN DETECTION SUMMARY")
    print("=" * 70)
    
    # 1. Profit-positive region boundary
    boundary = patterns['profit_positive_boundary']
    print(f"\n1. Profit-Positive Region Boundary (roughly):")
    if boundary['entry_thresholds']:
        print(f"   - Entry thresholds with profit > 0: {boundary['entry_thresholds']}")
        print(f"   - Exit thresholds with profit > 0: {boundary['exit_thresholds']}")
        print(f"   - Boundary shape: {boundary['shape']}")
    else:
        print("   - No profitable region found")
    
    # 2. Monotonicity
    monotonicity = patterns['monotonicity']
    print(f"\n2. Monotonicity (using marginal curves):")
    print(f"   - Entry threshold: {monotonicity['entry_threshold']}")
    print(f"   - Exit threshold: {monotonicity['exit_threshold']}")
    
    # 3. Robustness
    robustness = patterns['robustness']
    print(f"\n3. Robustness Assessment:")
    print(f"   - Type: {robustness['type']}")
    print(f"   - Entry range: {robustness['entry_range']}")
    print(f"   - Exit range: {robustness['exit_range']}")
    print(f"   - Plateau size: {robustness['size']} combinations ({robustness['size_category']})")
    
    # 4. Stability
    stability = patterns['stability']
    print(f"\n4. Stability Check (Train vs Valid):")
    print(f"   - Top 5 combos on TRAIN:")
    for i, combo in enumerate(stability['top_5_train'], 1):
        stable_str = "stable" if combo['stable'] else "unstable"
        print(f"     {i}. Entry={combo['entry']:.3f}, Exit={combo['exit']:.3f} → "
              f"Profit=${combo['train_profit']:.2f} (Train), ${combo['valid_profit']:.2f} (Valid) [{stable_str}]")
    print(f"   - Rank correlation (Train vs Valid): {stability['rank_correlation']:.3f}")
    
    # 5. Optimal region
    optimal = patterns['optimal_region']
    print(f"\n5. Optimal Region:")
    print(f"   - Best combo: Entry={optimal['best_combo']['entry_threshold']:.3f}, Exit={optimal['best_combo']['exit_threshold']:.3f}")
    if final_selection:
        train_metrics = final_selection.get('train_metrics', {})
        valid_metrics = final_selection.get('valid_metrics', {})
        test_metrics = final_selection.get('test_metrics', {})
        print(f"   - Profit: ${train_metrics.get('net_profit_dollars', 0):.2f} (Train), "
              f"${valid_metrics.get('net_profit_dollars', 0):.2f} (Valid), "
              f"${test_metrics.get('net_profit_dollars', 0):.2f} (Test)")
    print(f"   - Robust region: Entry={optimal['robust_region']['entry_range']}, Exit={optimal['robust_region']['exit_range']}")
    
    print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze grid search results and generate visualizations"
    )
    parser.add_argument(
        '--results-dir',
        type=str,
        required=True,
        help='Directory containing grid search results'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for plots (default: same as results-dir)'
    )
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        return 1
    
    output_dir = Path(args.output_dir) if args.output_dir else results_dir
    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    # Load results
    print("Loading results...")
    df_train = load_results(results_dir, 'train')
    df_valid = load_results(results_dir, 'valid')
    
    # Load final selection
    final_selection = load_final_selection(results_dir)
    chosen_params = final_selection['chosen_params'] if final_selection else None
    
    # Generate visualizations
    print("\nGenerating visualizations...")
    
    # A) Profit heatmaps
    create_heatmap(
        df_train,
        'net_profit_dollars',
        'Profit Heatmap (TRAIN)',
        plots_dir / 'profit_heatmap_train.png',
        chosen_params
    )
    
    create_heatmap(
        df_valid,
        'net_profit_dollars',
        'Profit Heatmap (VALID)',
        plots_dir / 'profit_heatmap_valid.png',
        chosen_params
    )
    
    # B) Marginal effects
    create_marginal_effects(df_valid, plots_dir / 'marginal_effects.png')
    
    # C) Tradeoff scatter
    create_tradeoff_scatter(df_valid, plots_dir / 'tradeoff_scatter.png')
    
    # D) Secondary heatmap (profit_factor)
    create_heatmap(
        df_valid,
        'profit_factor',
        'Profit Factor Heatmap (VALID)',
        plots_dir / 'profit_factor_heatmap_valid.png',
        chosen_params
    )
    
    # Pattern detection
    print("\nDetecting patterns...")
    patterns = detect_patterns(df_train, df_valid)
    
    # Print summary
    print_pattern_summary(patterns, final_selection)
    
    print(f"\nAll visualizations saved to {plots_dir}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

