"""
HTML Export endpoint - save HTML exports to docs/ directory for GitHub Pages.

Design Pattern: RESTful API Pattern
Algorithm: File write operation
Big O: O(n) where n is HTML content size
"""

from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


class HTMLExportRequest(BaseModel):
    """Request model for HTML export."""
    html_content: str


@router.post("/export/html")
def export_html(request: HTMLExportRequest) -> dict[str, Any]:
    """
    Save HTML content to docs/aggregate-stats.html for GitHub Pages deployment.
    
    Args:
        request: JSON body containing html_content field
        
    Returns:
        Success response with file path, or error response
        
    Raises:
        HTTPException: If file write fails
    """
    try:
        # Get repository root (assuming we're in webapp/api/endpoints/)
        # Go up 3 levels: endpoints -> api -> webapp -> repo root
        repo_root = Path(__file__).parent.parent.parent.parent
        docs_dir = repo_root / "docs"
        
        # Create docs/ directory if it doesn't exist
        docs_dir.mkdir(exist_ok=True)
        
        # Save HTML content to docs/aggregate-stats.html
        output_file = docs_dir / "aggregate-stats.html"
        output_file.write_text(request.html_content, encoding="utf-8")
        
        logger.info(f"HTML export saved successfully to {output_file}")
        
        return {
            "success": True,
            "file_path": str(output_file.relative_to(repo_root)),
            "message": f"HTML exported successfully to {output_file.relative_to(repo_root)}"
        }
        
    except PermissionError as e:
        logger.error(f"Permission denied when saving HTML export: {e}")
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: Unable to write to docs/ directory. {str(e)}"
        )
    except OSError as e:
        logger.error(f"OS error when saving HTML export: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"File system error: Unable to save HTML export. {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error when saving HTML export: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

