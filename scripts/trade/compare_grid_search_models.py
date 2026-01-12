#!/usr/bin/env python3
"""
Compare grid search results across multiple models (ESPN + 4 ML models).

Design Pattern: Facade Pattern for unified comparison interface
Algorithm: O(n × m) where n = result directories, m = metrics per directory
Big O: O(n × log(n)) for sorting results

This script aggregates and compares grid search results from all models,
providing side-by-side performance metrics and insights.
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def load_result_data(result_dir: Path) -> Optional[dict[str, Any]]:
    """
    Load grid search result data from a directory.
    
    Args:
        result_dir: Path to result directory (e.g., data/grid_search/{cache_key}/)
    
    Returns:
        Dictionary with model_name, final_selection, and metadata, or None if invalid
    """
    final_selection_path = result_dir / "final_selection.json"
    train_json_path = result_dir / "grid_results_train.json"
    
    if not final_selection_path.exists() or not train_json_path.exists():
        return None
    
    try:
        # Load final selection
        with open(final_selection_path) as f:
            final_selection = json.load(f)
        
        # Load metadata from train results
        with open(train_json_path) as f:
            train_data = json.load(f)
            metadata = train_data.get('metadata', {})
        
        # Extract model name from metadata
        args = metadata.get('args', {})
        model_name = args.get('model_name')
        if model_name is None:
            model_name = "ESPN (default)"
        
        return {
            'model_name': model_name,
            'result_dir': result_dir.name,
            'final_selection': final_selection,
            'metadata': metadata,
            'timestamp': metadata.get('timestamp', 'unknown')
        }
    except Exception as e:
        print(f"Error loading {result_dir}: {e}", file=sys.stderr)
        return None


def format_currency(value: Any) -> str:
    """Format a value as currency."""
    if value == 'N/A' or value is None:
        return 'N/A'
    if isinstance(value, (int, float)):
        return f"${value:,.2f}"
    return str(value)


def format_percentage(value: Any) -> str:
    """Format a value as percentage."""
    if value == 'N/A' or value is None:
        return 'N/A'
    if isinstance(value, (int, float)):
        return f"{value:.1%}"
    return str(value)


def format_threshold(value: Any) -> str:
    """Format a threshold value, removing floating point artifacts."""
    if value == 'N/A' or value is None:
        return 'N/A'
    if isinstance(value, float):
        return f"{value:.3f}".rstrip('0').rstrip('.')
    return str(value)


def print_comparison_table(results: list[dict[str, Any]]) -> None:
    """Print a formatted comparison table."""
    print("\n" + "=" * 120)
    print("GRID SEARCH MODEL COMPARISON")
    print("=" * 120)
    print(f"{'Model':<25} {'Test Profit':<15} {'Trades':<10} {'Win Rate':<12} {'Entry':<10} {'Exit':<10} {'Profit/Trade':<15}")
    print("-" * 120)
    
    for result in results:
        model_name = result['model_name']
        final_selection = result['final_selection']
        
        # Extract test metrics
        test_metrics = final_selection.get('test_metrics', {})
        profit = format_currency(test_metrics.get('net_profit_dollars', 'N/A'))
        trades = test_metrics.get('num_trades', 'N/A')
        win_rate = format_percentage(test_metrics.get('win_rate', 'N/A'))
        profit_per_trade = format_currency(test_metrics.get('avg_net_profit_per_trade', 'N/A'))
        
        # Extract thresholds
        chosen_params = final_selection.get('chosen_params', {})
        entry = format_threshold(chosen_params.get('entry_threshold', 'N/A'))
        exit_thresh = format_threshold(chosen_params.get('exit_threshold', 'N/A'))
        
        print(f"{model_name:<25} {profit:<15} {trades:<10} {win_rate:<12} {entry:<10} {exit_thresh:<10} {profit_per_trade:<15}")
    
    print("=" * 120)


def print_detailed_metrics(results: list[dict[str, Any]]) -> None:
    """Print detailed metrics for each model."""
    print("\n" + "=" * 120)
    print("DETAILED METRICS BY MODEL")
    print("=" * 120)
    
    for result in results:
        model_name = result['model_name']
        final_selection = result['final_selection']
        
        print(f"\n{model_name}")
        print("-" * 80)
        
        # Train metrics
        train_metrics = final_selection.get('train_metrics', {})
        print(f"  Train Set:")
        print(f"    Profit:     {format_currency(train_metrics.get('net_profit_dollars', 'N/A'))}")
        print(f"    Trades:     {train_metrics.get('num_trades', 'N/A')}")
        print(f"    Win Rate:   {format_percentage(train_metrics.get('win_rate', 'N/A'))}")
        print(f"    Profit Factor: {train_metrics.get('profit_factor', 'N/A')}")
        
        # Validation metrics
        valid_metrics = final_selection.get('valid_metrics', {})
        print(f"  Validation Set:")
        print(f"    Profit:     {format_currency(valid_metrics.get('net_profit_dollars', 'N/A'))}")
        print(f"    Trades:     {valid_metrics.get('num_trades', 'N/A')}")
        print(f"    Win Rate:   {format_percentage(valid_metrics.get('win_rate', 'N/A'))}")
        
        # Test metrics
        test_metrics = final_selection.get('test_metrics', {})
        print(f"  Test Set:")
        print(f"    Profit:     {format_currency(test_metrics.get('net_profit_dollars', 'N/A'))}")
        print(f"    Trades:     {test_metrics.get('num_trades', 'N/A')}")
        print(f"    Win Rate:   {format_percentage(test_metrics.get('win_rate', 'N/A'))}")
        print(f"    Avg Profit/Trade: {format_currency(test_metrics.get('avg_net_profit_per_trade', 'N/A'))}")
        print(f"    Profit Factor: {test_metrics.get('profit_factor', 'N/A')}")
        print(f"    Max Drawdown: {format_currency(test_metrics.get('max_drawdown', 'N/A'))}")
        print(f"    Total Fees: {format_currency(test_metrics.get('total_fees', 'N/A'))}")
        print(f"    Avg Hold Time: {test_metrics.get('avg_hold_time', 'N/A')} seconds")
        
        # Thresholds
        chosen_params = final_selection.get('chosen_params', {})
        print(f"  Optimal Thresholds:")
        print(f"    Entry: {format_threshold(chosen_params.get('entry_threshold', 'N/A'))}")
        print(f"    Exit:  {format_threshold(chosen_params.get('exit_threshold', 'N/A'))}")


def calculate_improvements(results: list[dict[str, Any]], baseline_model: str = "ESPN (default)") -> None:
    """Calculate and print improvement percentages relative to baseline."""
    # Find baseline
    baseline = None
    for result in results:
        if result['model_name'] == baseline_model:
            baseline = result
            break
    
    if baseline is None:
        print(f"\nWarning: Baseline model '{baseline_model}' not found. Skipping improvement calculations.")
        return
    
    baseline_test = baseline['final_selection'].get('test_metrics', {})
    baseline_profit = baseline_test.get('net_profit_dollars')
    
    if baseline_profit is None or not isinstance(baseline_profit, (int, float)):
        print(f"\nWarning: Baseline profit not available. Skipping improvement calculations.")
        return
    
    print("\n" + "=" * 120)
    print(f"IMPROVEMENT vs BASELINE ({baseline_model})")
    print("=" * 120)
    print(f"{'Model':<25} {'Test Profit':<15} {'Improvement':<15} {'Trades':<10} {'Win Rate':<12}")
    print("-" * 120)
    
    # Show baseline
    baseline_trades = baseline_test.get('num_trades', 'N/A')
    baseline_win_rate = format_percentage(baseline_test.get('win_rate', 'N/A'))
    print(f"{baseline_model:<25} {format_currency(baseline_profit):<15} {'(baseline)':<15} {baseline_trades:<10} {baseline_win_rate:<12}")
    
    # Show improvements
    for result in results:
        if result['model_name'] == baseline_model:
            continue
        
        model_name = result['model_name']
        test_metrics = result['final_selection'].get('test_metrics', {})
        profit = test_metrics.get('net_profit_dollars')
        
        if profit is None or not isinstance(profit, (int, float)):
            continue
        
        improvement = ((profit - baseline_profit) / abs(baseline_profit) * 100) if baseline_profit != 0 else float('inf')
        improvement_str = f"{improvement:+.1f}%"
        
        trades = test_metrics.get('num_trades', 'N/A')
        win_rate = format_percentage(test_metrics.get('win_rate', 'N/A'))
        
        print(f"{model_name:<25} {format_currency(profit):<15} {improvement_str:<15} {trades:<10} {win_rate:<12}")
    
    print("=" * 120)


def export_to_json(results: list[dict[str, Any]], output_path: Path) -> None:
    """Export comparison results to JSON."""
    export_data = {
        'comparison_timestamp': None,  # Will be set by caller if needed
        'models': []
    }
    
    for result in results:
        model_data = {
            'model_name': result['model_name'],
            'result_dir': result['result_dir'],
            'timestamp': result['timestamp'],
            'test_metrics': result['final_selection'].get('test_metrics', {}),
            'valid_metrics': result['final_selection'].get('valid_metrics', {}),
            'train_metrics': result['final_selection'].get('train_metrics', {}),
            'chosen_params': result['final_selection'].get('chosen_params', {}),
            'metadata': result['metadata']
        }
        export_data['models'].append(model_data)
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"\n✓ Exported comparison to {output_path}")


def main():
    """Main comparison function."""
    base_dir = Path("data/grid_search")
    
    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist. Run grid search first.", file=sys.stderr)
        return 1
    
    # Load all results
    results = []
    for result_dir in sorted(base_dir.glob("*/")):
        if not result_dir.is_dir():
            continue
        
        data = load_result_data(result_dir)
        if data is not None:
            results.append(data)
    
    if not results:
        print(f"Error: No valid grid search results found in {base_dir}", file=sys.stderr)
        return 1
    
    # Sort by test profit (descending)
    results.sort(
        key=lambda x: x['final_selection'].get('test_metrics', {}).get('net_profit_dollars', float('-inf')),
        reverse=True
    )
    
    # Print comparison table
    print_comparison_table(results)
    
    # Print detailed metrics
    print_detailed_metrics(results)
    
    # Calculate improvements (if ESPN baseline exists)
    calculate_improvements(results, baseline_model="ESPN (default)")
    
    # Export to JSON
    output_path = base_dir / "model_comparison.json"
    export_to_json(results, output_path)
    
    print(f"\n✓ Comparison complete. Found {len(results)} model results.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

