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
    season_start: int = Query(2024, description="Season start year to evaluate"),
) -> dict[str, Any]:
    """
    Get model evaluation results including calibration charts.
    
    Looks for evaluation report JSON files in data/reports/ directory.
    Format: winprob_eval_{season_start}.json
    
    Returns calibration data suitable for Chart.js rendering.
    """
    # Resolve repo root: webapp/api/endpoints/model_evaluation.py -> repo root
    repo_root = Path(__file__).parent.parent.parent.parent.resolve()
    
    # Try to find evaluation report
    eval_report_path = repo_root / "data" / "reports" / f"winprob_eval_{season_start}.json"
    
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

