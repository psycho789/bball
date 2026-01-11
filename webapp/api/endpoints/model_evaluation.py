"""
Model evaluation endpoint - serve calibration charts and evaluation metrics.

Design Pattern: Service Pattern for model evaluation
Algorithm: Load pre-computed evaluation results
Big O: O(1) - file read operation
"""

import json
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query

from ..logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/stats/model-evaluation")
def get_model_evaluation(
    artifact_path: Optional[str] = Query(None, description="Path to artifact file (relative to repo root)"),
    season_start: Optional[int] = Query(None, description="Season start year to evaluate (None = aggregate all seasons)"),
    all_seasons: bool = Query(False, description="Aggregate calibration data from all available evaluation reports"),
) -> dict[str, Any]:
    """
    Get model evaluation results including calibration charts.
    
    Looks for evaluation report JSON files in data/reports/ directory.
    Format: winprob_eval_{season_start}.json
    
    Returns calibration data suitable for Chart.js rendering.
    """
    # Resolve repo root: webapp/api/endpoints/model_evaluation.py -> repo root
    repo_root = Path(__file__).parent.parent.parent.parent.resolve()
    reports_dir = repo_root / "data" / "reports"
    
    # If all_seasons=True, aggregate all evaluation reports
    if all_seasons or season_start is None:
        eval_files = list(reports_dir.glob("winprob_eval_*.json"))
        # Filter out smoke test files
        eval_files = [f for f in eval_files if "smoke" not in f.name]
        
        if not eval_files:
            raise HTTPException(
                status_code=404,
                detail=f"No evaluation reports found in {reports_dir}. Run evaluation script first."
            )
        
        # Aggregate calibration data from all reports
        all_calibration_points = []
        all_calibration_bins = []
        total_n = 0
        artifact_paths = set()
        artifact_metas = []
        
        for eval_file in sorted(eval_files):
            try:
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                
                artifact_paths.add(eval_data.get("artifact_path", ""))
                artifact_metas.append(eval_data.get("artifact_meta", {}))
                
                bins = eval_data.get("eval", {}).get("calibration_bins", [])
                for bin_data in bins:
                    avg_p = bin_data.get("avg_p", 0)
                    obs_rate = bin_data.get("obs_rate", 0)
                    n = bin_data.get("n", 0)
                    if n > 0:
                        all_calibration_points.append({
                            "x": avg_p,
                            "y": obs_rate,
                            "n": n,
                            "gap": bin_data.get("gap", 0),
                            "season": eval_data.get("eval", {}).get("season_start"),
                        })
                        all_calibration_bins.append(bin_data)
                        total_n += n
            except Exception as e:
                logger.warning(f"Failed to read evaluation report {eval_file}: {e}")
                continue
        
        if not all_calibration_points:
            raise HTTPException(
                status_code=404,
                detail="No calibration data found in evaluation reports."
            )
        
        # Aggregate by bin (average probabilities and observed rates weighted by sample count)
        bin_map = {}
        for point in all_calibration_points:
            # Round to nearest 0.05 to group bins
            bin_key = round(point["x"] * 20) / 20
            if bin_key not in bin_map:
                bin_map[bin_key] = {"x_sum": 0, "y_sum": 0, "n_sum": 0, "gaps": []}
            bin_map[bin_key]["x_sum"] += point["x"] * point["n"]
            bin_map[bin_key]["y_sum"] += point["y"] * point["n"]
            bin_map[bin_key]["n_sum"] += point["n"]
            bin_map[bin_key]["gaps"].append(point["gap"])
        
        # Create aggregated calibration points
        aggregated_points = []
        for bin_key in sorted(bin_map.keys()):
            data = bin_map[bin_key]
            if data["n_sum"] > 0:
                avg_x = data["x_sum"] / data["n_sum"]
                avg_y = data["y_sum"] / data["n_sum"]
                avg_gap = sum(data["gaps"]) / len(data["gaps"]) if data["gaps"] else 0
                aggregated_points.append({
                    "x": avg_x,
                    "y": avg_y,
                    "n": data["n_sum"],
                    "gap": avg_gap,
                })
        
        return {
            "artifact_path": ", ".join(sorted(artifact_paths)) if artifact_paths else "",
            "artifact_meta": artifact_metas[0] if artifact_metas else {},
            "eval": {
                "season_start": None,  # All seasons
                "overall": {"n": total_n},
                "calibration_bins": all_calibration_bins,
                "calibration_points": aggregated_points,
            },
        }
    
    # Single season evaluation
    eval_report_path = reports_dir / f"winprob_eval_{season_start}.json"
    
    if not eval_report_path.exists():
        # Try default artifact path if provided
        if artifact_path:
            # Look for any evaluation report
            reports_dir = repo_root / "data" / "reports"
            if reports_dir.exists():
                eval_files = list(reports_dir.glob("winprob_eval_*.json"))
                if eval_files:
                    eval_report_path = sorted(eval_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
                    logger.info(f"Using most recent evaluation report: {eval_report_path.name}")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No evaluation reports found in {reports_dir}. Run evaluation script first."
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Evaluation report not found at {eval_report_path} and reports directory doesn't exist."
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation report not found at {eval_report_path}. Run: python scripts/evaluate_winprob_model.py --artifact <artifact> --season-start {season_start} --out data/reports/winprob_eval_{season_start}.json --dsn \"$DATABASE_URL\""
            )
    
    try:
        with open(eval_report_path, 'r') as f:
            eval_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read evaluation report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read evaluation report: {e}")
    
    # Extract calibration data for Chart.js
    calibration_bins = eval_data.get("eval", {}).get("calibration_bins", [])
    
    # Format for Chart.js scatter plot
    calibration_points = []
    for bin_data in calibration_bins:
        avg_p = bin_data.get("avg_p", 0)
        obs_rate = bin_data.get("obs_rate", 0)
        n = bin_data.get("n", 0)
        if n > 0:  # Only include bins with data
            calibration_points.append({
                "x": avg_p,
                "y": obs_rate,
                "n": n,
                "gap": bin_data.get("gap", 0),  # obs_rate - avg_p
            })
    
    return {
        "artifact_path": str(eval_data.get("artifact_path", "")),
        "artifact_meta": eval_data.get("artifact_meta", {}),
        "eval": {
            "season_start": eval_data.get("eval", {}).get("season_start"),
            "overall": eval_data.get("eval", {}).get("overall", {}),
            "calibration_bins": calibration_bins,
            "calibration_points": calibration_points,  # For Chart.js
        },
    }

