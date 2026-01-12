"""
Model Comparison Visualization - Compare all 4 models side-by-side.

Design Pattern: Data Visualization Pattern
Algorithm: Load evaluation reports, extract metrics, generate HTML visualization
Big O: O(n) where n is number of calibration points
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Generate comparison visualization for all 4 models (LogReg/CatBoost × Platt/Isotonic)"
    )
    p.add_argument(
        "--reports-dir",
        type=str,
        default="data/models/evaluations",
        help="Directory containing evaluation JSON reports",
    )
    p.add_argument(
        "--out",
        type=str,
        default="data/models/evaluations/model_comparison.html",
        help="Output HTML file path",
    )
    return p.parse_args()


def get_model_label(filename: str) -> str:
    """Extract model label from filename."""
    if "logreg_platt" in filename:
        return "Logistic Regression + Platt"
    elif "logreg_isotonic" in filename:
        return "Logistic Regression + Isotonic"
    elif "catboost_platt" in filename:
        return "CatBoost + Platt"
    elif "catboost_isotonic" in filename:
        return "CatBoost + Isotonic"
    else:
        return filename


def get_model_color(model_label: str) -> str:
    """Get color for model based on label."""
    if "Logistic Regression + Platt" in model_label:
        return "#7c3aed"  # Purple
    elif "Logistic Regression + Isotonic" in model_label:
        return "#3b82f6"  # Blue
    elif "CatBoost + Platt" in model_label:
        return "#f7931a"  # Orange
    elif "CatBoost + Isotonic" in model_label:
        return "#10b981"  # Green
    else:
        return "#666666"  # Gray


def load_evaluation_reports(reports_dir: Path) -> list[dict[str, Any]]:
    """Load all 4 evaluation reports."""
    model_files = [
        "winprob_eval_logreg_platt_2017-2023_calib_2023_on_2024.json",
        "winprob_eval_logreg_isotonic_2017-2023_calib_2023_on_2024.json",
        "winprob_eval_catboost_platt_2017-2023_calib_2023_on_2024.json",
        "winprob_eval_catboost_isotonic_2017-2023_calib_2023_on_2024.json",
    ]
    
    reports = []
    for filename in model_files:
        filepath = reports_dir / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        model_label = get_model_label(filename)
        data["model_label"] = model_label
        data["model_color"] = get_model_color(model_label)
        data["filename"] = filename
        reports.append(data)
    
    return reports


def extract_metrics(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract metrics from all reports."""
    metrics = []
    for report in reports:
        overall = report["eval"]["overall"]
        metrics.append({
            "model": report["model_label"],
            "logloss": overall["logloss"],
            "brier": overall["brier"],
            "ece": overall["ece_binned"],
            "auc": overall["roc_auc"],
            "n": overall["n"],
            "color": report["model_color"],
        })
    return metrics


def find_best_model(metrics: list[dict[str, Any]]) -> dict[str, str]:
    """Find best model for each metric."""
    best = {}
    
    # Lower is better: logloss, brier, ece
    best["logloss"] = min(metrics, key=lambda m: m["logloss"])["model"]
    best["brier"] = min(metrics, key=lambda m: m["brier"])["model"]
    best["ece"] = min(metrics, key=lambda m: m["ece"])["model"]
    
    # Higher is better: auc
    best["auc"] = max(metrics, key=lambda m: m["auc"])["model"]
    
    return best


def generate_html(
    reports: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    best: dict[str, str],
    out_path: Path,
) -> None:
    """Generate HTML comparison visualization."""
    
    # Extract calibration points for Chart.js
    calibration_data = []
    for report in reports:
        calib_bins = report["eval"]["calibration_bins"]
        points = []
        for bin_data in calib_bins:
            points.append({
                "x": float(bin_data["avg_p"]),
                "y": float(bin_data["obs_rate"]),
                "n": int(bin_data["n"]),
            })
        calibration_data.append({
            "label": report["model_label"],
            "color": report["model_color"],
            "points": points,
        })
    
    # Generate metrics table HTML
    metrics_html = "<table style='width: 100%; border-collapse: collapse; margin: 20px 0;'>"
    metrics_html += "<thead><tr style='background: #f0f0f0;'>"
    metrics_html += "<th style='padding: 10px; text-align: left; border: 1px solid #ddd;'>Model</th>"
    metrics_html += "<th style='padding: 10px; text-align: right; border: 1px solid #ddd;'>Log Loss</th>"
    metrics_html += "<th style='padding: 10px; text-align: right; border: 1px solid #ddd;'>Brier Score</th>"
    metrics_html += "<th style='padding: 10px; text-align: right; border: 1px solid #ddd;'>ECE</th>"
    metrics_html += "<th style='padding: 10px; text-align: right; border: 1px solid #ddd;'>AUC</th>"
    metrics_html += "<th style='padding: 10px; text-align: right; border: 1px solid #ddd;'>N</th>"
    metrics_html += "</tr></thead><tbody>"
    
    for metric in metrics:
        is_best_logloss = metric["model"] == best["logloss"]
        is_best_brier = metric["model"] == best["brier"]
        is_best_ece = metric["model"] == best["ece"]
        is_best_auc = metric["model"] == best["auc"]
        
        metrics_html += f"<tr style='background: {'#fff9e6' if any([is_best_logloss, is_best_brier, is_best_ece, is_best_auc]) else 'white'};'>"
        metrics_html += f"<td style='padding: 10px; border: 1px solid #ddd;'><strong>{metric['model']}</strong></td>"
        metrics_html += f"<td style='padding: 10px; text-align: right; border: 1px solid #ddd;'>{'<strong>' if is_best_logloss else ''}{metric['logloss']:.6f}{'</strong>' if is_best_logloss else ''}</td>"
        metrics_html += f"<td style='padding: 10px; text-align: right; border: 1px solid #ddd;'>{'<strong>' if is_best_brier else ''}{metric['brier']:.6f}{'</strong>' if is_best_brier else ''}</td>"
        metrics_html += f"<td style='padding: 10px; text-align: right; border: 1px solid #ddd;'>{'<strong>' if is_best_ece else ''}{metric['ece']:.6f}{'</strong>' if is_best_ece else ''}</td>"
        metrics_html += f"<td style='padding: 10px; text-align: right; border: 1px solid #ddd;'>{'<strong>' if is_best_auc else ''}{metric['auc']:.6f}{'</strong>' if is_best_auc else ''}</td>"
        metrics_html += f"<td style='padding: 10px; text-align: right; border: 1px solid #ddd;'>{metric['n']:,}</td>"
        metrics_html += "</tr>"
    
    metrics_html += "</tbody></table>"
    
    # Generate best model summary
    best_html = "<div style='background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;'>"
    best_html += "<h3 style='margin-top: 0;'>Best Models by Metric</h3>"
    best_html += "<ul style='margin: 0;'>"
    best_html += f"<li><strong>Log Loss (lower is better):</strong> {best['logloss']}</li>"
    best_html += f"<li><strong>Brier Score (lower is better):</strong> {best['brier']}</li>"
    best_html += f"<li><strong>ECE (lower is better):</strong> {best['ece']}</li>"
    best_html += f"<li><strong>AUC (higher is better):</strong> {best['auc']}</li>"
    best_html += "</ul></div>"
    
    # Generate Chart.js calibration plot data
    chart_datasets = []
    for calib in calibration_data:
        chart_datasets.append({
            "label": calib["label"],
            "data": calib["points"],
            "backgroundColor": calib["color"].replace(")", ", 0.6)").replace("rgb", "rgba") if calib["color"].startswith("rgb") else calib["color"] + "99",
            "borderColor": calib["color"],
            "pointRadius": [max(3, min(10, 3 + (p["n"] / 10000))) for p in calib["points"]],
            "pointHoverRadius": 8,
        })
    
    # Add perfect calibration line
    chart_datasets.append({
        "label": "Perfect Calibration (y = x)",
        "data": [{"x": 0, "y": 0}, {"x": 1, "y": 1}],
        "type": "line",
        "borderColor": "rgba(128, 128, 128, 0.5)",
        "borderWidth": 2,
        "borderDash": [5, 5],
        "pointRadius": 0,
        "fill": False,
        "tension": 0,
    })
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Comparison - 2×2 Matrix (LogReg/CatBoost × Platt/Isotonic)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}
        h1 {{
            color: #111;
            margin-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 30px;
        }}
        .chart-container {{
            position: relative;
            height: 600px;
            margin: 20px 0;
            background: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <h1>Model Comparison: 2×2 Matrix</h1>
    <p class="subtitle">Logistic Regression vs CatBoost × Platt vs Isotonic Calibration</p>
    
    <h2>Overall Metrics Comparison</h2>
    {metrics_html}
    
    {best_html}
    
    <h2>Calibration Comparison</h2>
    <p>All 4 models plotted together. Points closer to the diagonal line (y=x) indicate better calibration.</p>
    <div class="chart-container">
        <canvas id="calibrationChart"></canvas>
    </div>
    
    <script>
        const calibrationData = {json.dumps(chart_datasets, indent=8)};
        
        const ctx = document.getElementById('calibrationChart').getContext('2d');
        new Chart(ctx, {{
            type: 'scatter',
            data: {{
                datasets: calibrationData
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{
                        title: {{
                            display: true,
                            text: 'Predicted Probability'
                        }},
                        min: 0,
                        max: 1,
                        ticks: {{
                            callback: function(value) {{
                                return (value * 100).toFixed(0) + '%';
                            }}
                        }}
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: 'Actual Win Rate'
                        }},
                        min: 0,
                        max: 1,
                        ticks: {{
                            callback: function(value) {{
                                return (value * 100).toFixed(0) + '%';
                            }}
                        }}
                    }}
                }},
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                if (context.datasetIndex < calibrationData.length - 1) {{
                                    const point = context.raw;
                                    return [
                                        context.dataset.label,
                                        `Predicted: ${{(point.x * 100).toFixed(1)}}%`,
                                        `Actual: ${{(point.y * 100).toFixed(1)}}%`,
                                        `Samples: ${{point.n || 0}}`
                                    ];
                                }}
                                return context.dataset.label;
                            }}
                        }}
                    }},
                    legend: {{
                        display: true,
                        labels: {{
                            filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"Wrote {out_path}")


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    reports_dir = Path(args.reports_dir)
    out_path = Path(args.out)
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        return 1
    
    print(f"Loading evaluation reports from {reports_dir}...")
    reports = load_evaluation_reports(reports_dir)
    
    if len(reports) == 0:
        print("Error: No evaluation reports found")
        return 1
    
    print(f"Loaded {len(reports)} evaluation reports")
    
    print("Extracting metrics...")
    metrics = extract_metrics(reports)
    
    print("Finding best models...")
    best = find_best_model(metrics)
    
    print("Generating HTML visualization...")
    generate_html(reports, metrics, best, out_path)
    
    print("Comparison visualization complete!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

