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
    model_type: Optional[str] = Query(None, description="Model type filter: 'platt' or 'no_platt' or None for all"),
) -> dict[str, Any]:
    """
    Get model evaluation results including calibration charts.
    
    Looks for evaluation report JSON files in data/models/evaluations/ directory.
    Supports multiple naming formats:
    - winprob_eval_{season_start}.json (simple format)
    - winprob_eval_*_calib_*_on_{season_start}.json (detailed format with Platt)
    - winprob_eval_*_no_platt_on_{season_start}.json (detailed format without Platt)
    
    Returns calibration data suitable for Chart.js rendering with model labels.
    """
    # Resolve repo root: webapp/api/endpoints/model_evaluation.py -> repo root
    repo_root = Path(__file__).parent.parent.parent.parent.resolve()
    reports_dir = repo_root / "data" / "models" / "evaluations"
    
    # Helper function to determine model type and calibration from filename
    def get_model_info_from_filename(filename: str) -> tuple[str, str]:
        """
        Determine model type (logreg/catboost) and calibration method (platt/isotonic/no_platt) from filename.
        
        Returns:
            (model_type, calibration_method) tuple
        """
        # Detect model type
        if "catboost" in filename.lower():
            model_type = "catboost"
        else:
            model_type = "logreg"  # Default to logistic regression
        
        # Detect calibration method
        if "no_platt" in filename:
            calibration = "no_platt"
        elif "isotonic" in filename.lower():
            calibration = "isotonic"
        elif "calib" in filename or "platt" in filename.lower():
            calibration = "platt"
        else:
            # Default to platt if not specified (most models have it)
            calibration = "platt"
        
        return (model_type, calibration)
    
    # Backward compatibility wrapper
    def get_model_type_from_filename(filename: str) -> str:
        """Determine if model has Platt calibration from filename (backward compatibility)."""
        _, calibration = get_model_info_from_filename(filename)
        return calibration
    
    # Helper function to get model label
    def get_model_label(filename: str, artifact_meta: dict) -> str:
        """Get human-readable label for the model."""
        model_type, calibration = get_model_info_from_filename(filename)
        
        # Get training data range
        if "2017-2023" in filename or "2017_2023" in filename:
            train_data = "2017-2023"
        else:
            train_data = artifact_meta.get("train_season_start_max", "unknown")
        
        # Build label based on model type and calibration
        model_name = "Logistic Regression" if model_type == "logreg" else "CatBoost"
        
        if calibration == "platt":
            return f"{model_name} + Platt (Training: {train_data})"
        elif calibration == "isotonic":
            return f"{model_name} + Isotonic (Training: {train_data})"
        else:
            return f"{model_name} (No Calibration, Training: {train_data})"
    
    # If all_seasons=True, aggregate all evaluation reports
    if all_seasons or season_start is None:
        eval_files = list(reports_dir.glob("winprob_eval_*.json"))
        # Filter out smoke test files
        eval_files = [f for f in eval_files if "smoke" not in f.name]
        
        # Filter by model_type if specified
        if model_type:
            if model_type == "platt":
                eval_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "platt"]
            elif model_type == "no_platt":
                eval_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "no_platt"]
        
        if not eval_files:
            raise HTTPException(
                status_code=404,
                detail=f"No evaluation reports found in {reports_dir} matching criteria. Run evaluation script first."
            )
        
        # Group by model type and calibration to return separate datasets
        # Create 4 groups: logreg+platt, logreg+isotonic, catboost+platt, catboost+isotonic
        model_groups = {
            "logreg_platt": [],
            "logreg_isotonic": [],
            "catboost_platt": [],
            "catboost_isotonic": [],
        }
        
        for f in eval_files:
            mtype, calibration = get_model_info_from_filename(f.name)
            if calibration in ["platt", "isotonic"]:
                key = f"{mtype}_{calibration}"
                if key in model_groups:
                    model_groups[key].append(f)
        
        # Also maintain backward compatibility with old grouping
        platt_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "platt"]
        no_platt_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "no_platt"]
        
        def aggregate_calibration(files: list[Path], label: str) -> dict[str, Any]:
            """Aggregate calibration data from a list of evaluation files."""
            all_calibration_points = []
            all_calibration_bins = []
            total_n = 0
            artifact_paths = set()
            artifact_metas = []
            
            for eval_file in sorted(files):
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
                return None
            
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
                "label": label,
                "artifact_path": ", ".join(sorted(artifact_paths)) if artifact_paths else "",
                "artifact_meta": artifact_metas[0] if artifact_metas else {},
                "eval": {
                    "season_start": None,  # All seasons
                    "overall": {"n": total_n},
                    "calibration_bins": all_calibration_bins,
                    "calibration_points": aggregated_points,
                },
            }
        
        # Aggregate all model types separately
        results = {}
        
        # Aggregate new 4-model structure
        for key, files in model_groups.items():
            if files:
                mtype, calibration = key.split("_")
                model_name = "Logistic Regression" if mtype == "logreg" else "CatBoost"
                calib_name = "Platt" if calibration == "platt" else "Isotonic"
                label = f"{model_name} + {calib_name} (Training: 2017-2023)"
                data = aggregate_calibration(files, label)
                if data:
                    results[key] = data
        
        # Also maintain backward compatibility with old 2-model structure
        if platt_files and "logreg_platt" not in results:
            platt_data = aggregate_calibration(platt_files, "Platt Calibrated (Training: 2017-2023)")
            if platt_data:
                results["platt"] = platt_data
        
        if no_platt_files:
            no_platt_data = aggregate_calibration(no_platt_files, "Non-Platt (Training: 2017-2023)")
            if no_platt_data:
                results["no_platt"] = no_platt_data
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail="No calibration data found in evaluation reports."
            )
        
        # If only one model type, return it directly (backward compatibility)
        if len(results) == 1:
            return list(results.values())[0]
        
        # Otherwise return both datasets with labels
        return {
            "models": results,
            "model_types": list(results.keys()),
        }
    
    # Single season evaluation
    eval_report_path = None
    
    # First, try simple format
    simple_path = reports_dir / f"winprob_eval_{season_start}.json"
    if simple_path.exists():
        eval_report_path = simple_path
    else:
        # Try detailed format patterns - support all 4 model types
        # Check for specific model_type requests first
        if model_type == "logreg_platt":
            # Try logreg + platt (exact match)
            platt_files = list(reports_dir.glob(f"winprob_eval_logreg_platt*_on_{season_start}.json"))
            if not platt_files:
                platt_files = list(reports_dir.glob(f"winprob_eval_*logreg*platt*_on_{season_start}.json"))
            if platt_files:
                eval_report_path = sorted(platt_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        elif model_type == "logreg_isotonic":
            # Try logreg + isotonic (exact match)
            isotonic_files = list(reports_dir.glob(f"winprob_eval_logreg_isotonic*_on_{season_start}.json"))
            if not isotonic_files:
                isotonic_files = list(reports_dir.glob(f"winprob_eval_*logreg*isotonic*_on_{season_start}.json"))
            if isotonic_files:
                eval_report_path = sorted(isotonic_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        elif model_type == "catboost_platt":
            # Try catboost + platt (exact match)
            catboost_platt_files = list(reports_dir.glob(f"winprob_eval_catboost_platt*_on_{season_start}.json"))
            if not catboost_platt_files:
                catboost_platt_files = list(reports_dir.glob(f"winprob_eval_*catboost*platt*_on_{season_start}.json"))
            if catboost_platt_files:
                eval_report_path = sorted(catboost_platt_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        elif model_type == "catboost_isotonic":
            # Try catboost + isotonic (exact match)
            catboost_isotonic_files = list(reports_dir.glob(f"winprob_eval_catboost_isotonic*_on_{season_start}.json"))
            if not catboost_isotonic_files:
                catboost_isotonic_files = list(reports_dir.glob(f"winprob_eval_*catboost*isotonic*_on_{season_start}.json"))
            if catboost_isotonic_files:
                eval_report_path = sorted(catboost_isotonic_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        elif model_type is None or model_type in ["platt"]:
            # Try any platt model (backward compatibility)
            platt_files = list(reports_dir.glob(f"winprob_eval_*_calib_*_on_{season_start}.json"))
            if not platt_files:
                platt_files = list(reports_dir.glob(f"winprob_eval_*platt*_on_{season_start}.json"))
            if platt_files:
                eval_report_path = sorted(platt_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        elif model_type == "isotonic":
            # Try any isotonic model
            isotonic_files = list(reports_dir.glob(f"winprob_eval_*isotonic*_on_{season_start}.json"))
            if isotonic_files:
                eval_report_path = sorted(isotonic_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        if eval_report_path is None and (model_type == "no_platt" or model_type is None):
            no_platt_files = list(reports_dir.glob(f"winprob_eval_*_no_platt_on_{season_start}.json"))
            if no_platt_files:
                eval_report_path = sorted(no_platt_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        
        # If still not found and model_type not specified, try any pattern
        if eval_report_path is None and model_type is None:
            any_files = list(reports_dir.glob(f"winprob_eval_*_{season_start}*.json"))
            if any_files:
                eval_report_path = sorted(any_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    
    if eval_report_path is None or not eval_report_path.exists():
        # Try to find any evaluation report for this season
        if reports_dir.exists():
            eval_files = list(reports_dir.glob(f"*{season_start}*.json"))
            eval_files = [f for f in eval_files if "smoke" not in f.name and "winprob_eval" in f.name]
            if eval_files:
                # Filter by model_type if specified
                if model_type:
                    if model_type == "platt":
                        eval_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "platt"]
                    elif model_type == "no_platt":
                        eval_files = [f for f in eval_files if get_model_type_from_filename(f.name) == "no_platt"]
                
                if eval_files:
                    eval_report_path = sorted(eval_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
                    logger.info(f"Using evaluation report: {eval_report_path.name}")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No evaluation reports found for season {season_start} with model_type={model_type} in {reports_dir}."
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Evaluation report not found for season {season_start} in {reports_dir}. Run evaluation script first."
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation reports directory does not exist: {reports_dir}"
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
    
    # Determine model label and type info
    model_label = get_model_label(eval_report_path.name, eval_data.get("artifact_meta", {}))
    model_type, calibration = get_model_info_from_filename(eval_report_path.name)
    
    return {
        "artifact_path": str(eval_data.get("artifact_path", "")),
        "artifact_meta": eval_data.get("artifact_meta", {}),
        "model_label": model_label,
        "model_type": calibration,  # Backward compatibility
        "model_type_full": f"{model_type}_{calibration}",  # New: full model type
        "base_model_type": model_type,  # New: just the base model (logreg/catboost)
        "calibration_method": calibration,  # New: just the calibration (platt/isotonic/no_platt)
        "eval": {
            "season_start": eval_data.get("eval", {}).get("season_start"),
            "overall": eval_data.get("eval", {}).get("overall", {}),
            "calibration_bins": calibration_bins,
            "calibration_points": calibration_points,  # For Chart.js
        },
    }


@router.get("/stats/model-evaluation/plot")
def get_model_evaluation_plot(
    report_name: str = Query(..., description="Evaluation report name (without .json extension)"),
    plot_type: str = Query(..., description="Plot type: 'calibration' or 'calibration_context'"),
    format: str = Query("svg", description="File format: 'svg' or 'jpg'"),
) -> Any:
    """
    Serve plot files (SVG or JPEG) for model evaluation reports.
    
    Args:
        report_name: Name of the evaluation report (e.g., "winprob_eval_2017-2023_calib_2023_on_2024")
        plot_type: Type of plot ("calibration" or "calibration_context")
        format: File format ("svg" or "jpg")
    
    Returns:
        File content with appropriate Content-Type header
    """
    from fastapi.responses import FileResponse, Response
    
    # Resolve repo root
    repo_root = Path(__file__).parent.parent.parent.parent.resolve()
    reports_dir = repo_root / "data" / "models" / "evaluations"
    
    # Validate format
    if format not in ["svg", "jpg"]:
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}. Must be 'svg' or 'jpg'")
    
    # Validate plot_type
    if plot_type not in ["calibration", "calibration_context"]:
        raise HTTPException(status_code=400, detail=f"Invalid plot_type: {plot_type}. Must be 'calibration' or 'calibration_context'")
    
    # Construct file path
    file_extension = "svg" if format == "svg" else "jpg"
    plot_path = reports_dir / f"{report_name}.{plot_type}.{file_extension}"
    
    if not plot_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Plot file not found: {plot_path.name}. Make sure the evaluation was run with --plot-calibration flag."
        )
    
    # Determine Content-Type
    if format == "svg":
        media_type = "image/svg+xml"
    else:
        media_type = "image/jpeg"
    
    return FileResponse(
        path=str(plot_path),
        media_type=media_type,
        filename=plot_path.name,
    )

