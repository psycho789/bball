"""
Model comparison endpoint - serve comparison data for all 4 models.

Design Pattern: Service Pattern for model comparison
Algorithm: File I/O and data transformation
Big O: O(n) where n is total calibration points across all models
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ..logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
            logger.warning(f"Evaluation file not found: {filepath}, skipping")
            continue
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            model_label = get_model_label(filename)
            data["model_label"] = model_label
            data["model_color"] = get_model_color(model_label)
            data["filename"] = filename
            reports.append(data)
        except Exception as e:
            logger.error(f"Error loading evaluation file {filepath}: {e}", exc_info=True)
            continue
    
    return reports


def extract_metrics(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract metrics from all reports."""
    metrics = []
    for report in reports:
        overall = report.get("eval", {}).get("overall", {})
        metrics.append({
            "model": report["model_label"],
            "logloss": overall.get("logloss", 0.0),
            "brier": overall.get("brier", 0.0),
            "ece": overall.get("ece_binned", 0.0),
            "auc": overall.get("roc_auc", 0.0),
            "n": overall.get("n", 0),
            "color": report["model_color"],
        })
    return metrics


def extract_calibration_points(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform calibration_bins to calibration_points format."""
    calibration_bins = report.get("eval", {}).get("calibration_bins", [])
    points = []
    for bin_data in calibration_bins:
        points.append({
            "x": float(bin_data.get("avg_p", 0.0)),
            "y": float(bin_data.get("obs_rate", 0.0)),
            "n": int(bin_data.get("n", 0)),
        })
    return points


def find_best_models(metrics: list[dict[str, Any]]) -> dict[str, str]:
    """Find best model for each metric."""
    best = {}
    
    # Lower is better: logloss, brier, ece
    if metrics:
        best["logloss"] = min(metrics, key=lambda m: m["logloss"])["model"]
        best["brier"] = min(metrics, key=lambda m: m["brier"])["model"]
        best["ece"] = min(metrics, key=lambda m: m["ece"])["model"]
        
        # Higher is better: auc
        best["auc"] = max(metrics, key=lambda m: m["auc"])["model"]
    
    return best


@router.get("/stats/model-comparison")
def get_model_comparison() -> dict[str, Any]:
    """
    Get model comparison data for all 4 models (LogReg/CatBoost × Platt/Isotonic).
    
    Returns:
        JSON with models array (metrics and calibration_points) and best_models object
    """
    try:
        # Get repository root (webapp/api/endpoints/ -> repo root)
        repo_root = Path(__file__).parent.parent.parent.parent
        reports_dir = repo_root / "data" / "models" / "evaluations"
        
        if not reports_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Evaluations directory not found: {reports_dir}"
            )
        
        # Load all evaluation reports
        reports = load_evaluation_reports(reports_dir)
        
        if len(reports) == 0:
            raise HTTPException(
                status_code=404,
                detail="No evaluation reports found in data/models/evaluations/"
            )
        
        # Extract metrics and calibration points
        metrics = extract_metrics(reports)
        best_models = find_best_models(metrics)
        
        # Build response with models array
        models_data = []
        for report in reports:
            calibration_points = extract_calibration_points(report)
            overall = report.get("eval", {}).get("overall", {})
            
            models_data.append({
                "model_label": report["model_label"],
                "model_color": report["model_color"],
                "metrics": {
                    "logloss": overall.get("logloss", 0.0),
                    "brier": overall.get("brier", 0.0),
                    "ece": overall.get("ece_binned", 0.0),
                    "auc": overall.get("roc_auc", 0.0),
                    "n": overall.get("n", 0),
                },
                "calibration_points": calibration_points,
            })
        
        return {
            "models": models_data,
            "best_models": best_models,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading model comparison data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading model comparison data: {str(e)}"
        )

