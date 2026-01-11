"""
Data update endpoint - check for new games and trigger data ingestion.

Design Pattern: Service Pattern for data updates
Algorithm: Compare ESPN scoreboard with database, trigger ingestion scripts
Big O: O(n) where n = number of games in scoreboard
"""

from typing import Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime, timedelta, date, timezone
import subprocess
import os
import json
import threading
import re
from pathlib import Path

from ..db import get_db_connection
from ..logging_config import get_logger
from ..cache import SimpleCache
from . import games

# Lock to prevent concurrent update task execution
_update_task_lock = threading.Lock()
_update_task_running = False

router = APIRouter()
logger = get_logger(__name__)

# Lock to prevent concurrent update task execution
_update_task_lock = threading.Lock()
_update_task_running = False


@router.get("/update/status")
def get_update_status() -> dict[str, Any]:
    """
    Check if an update task is currently running.
    
    Returns:
        - is_running: True if update is in progress
        - message: Status message
    """
    global _update_task_running
    
    is_running = _update_task_running or _update_task_lock.locked()
    
    return {
        "is_running": is_running,
        "message": "Update in progress" if is_running else "No update running"
    }


@router.get("/update/check-new-games")
def check_new_games() -> dict[str, Any]:
    """
    Check if there are Kalshi markets that need candlestick data fetched/loaded.
    
    This checks the last step of the update process (Step 6):
    - Are there Kalshi markets that don't have candlestick data?
    
    Note: Kalshi markets are fetched independently (Step 5) and don't require
    ESPN probability data. The matching to ESPN games happens via migration 028.
    
    Returns:
        - new_kalshi_candlesticks: Number of Kalshi markets without candlestick data
        - has_new_data: True if new_kalshi_candlesticks > 0
    """
    logger.info("[CHECK_NEW_GAMES] Checking for Kalshi markets needing candlestick data")
    
    try:
        with get_db_connection() as conn:
            # Check for Kalshi markets that don't have candlestick data
            # Focus on recent markets (last 7 days) to keep the check fast
            # Exclude future games (game_date > CURRENT_DATE) as they may not have candlestick data yet
            # This is the last step of the update process (Step 6)
            new_candlesticks = conn.execute(
                """
                SELECT COUNT(DISTINCT km.ticker)
                FROM kalshi.markets km
                LEFT JOIN kalshi.candlesticks kc ON km.ticker = kc.ticker
                WHERE km.game_date >= CURRENT_DATE - INTERVAL '7 days'
                  AND km.game_date <= CURRENT_DATE
                  AND kc.ticker IS NULL
                """
            ).fetchone()[0]
            
            logger.info(f"[CHECK_NEW_GAMES] Found {new_candlesticks} Kalshi markets needing candlestick data")
            
            return {
                "new_kalshi_candlesticks": new_candlesticks,
                "has_new_data": new_candlesticks > 0
            }
            
    except Exception as e:
        logger.error(f"[CHECK_NEW_GAMES] Error checking new games: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking new games: {str(e)}")


def run_update_script(script_name: str, args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a script as subprocess and return exit code, stdout, stderr."""
    repo_root = Path(__file__).parent.parent.parent.parent
    script_path = repo_root / "scripts" / script_name
    
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    # Get DATABASE_URL from environment
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        raise ValueError("DATABASE_URL environment variable not set")
    
    cmd = [os.environ.get("PYTHON_BIN", "python3"), str(script_path)] + args
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Script timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def get_repo_root() -> Path:
    """Get the repository root directory."""
    current_file = Path(__file__)
    # Navigate from webapp/api/endpoints/update.py to repo root
    return current_file.parent.parent.parent.parent


def fetch_espn_scoreboard_for_date(date_str: str, repo_root: Path) -> tuple[bool, str]:
    """Fetch ESPN scoreboard for a specific date (YYYYMMDD format)."""
    logger.info(f"[FETCH_SCOREBOARD] Starting fetch for date: {date_str}")
    logger.debug(f"[FETCH_SCOREBOARD] Repo root: {repo_root}")
    
    scoreboard_dir = repo_root / "data" / "raw" / "espn" / "scoreboard"
    logger.debug(f"[FETCH_SCOREBOARD] Scoreboard directory: {scoreboard_dir}")
    scoreboard_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"[FETCH_SCOREBOARD] Scoreboard directory created/verified")
    
    out_file = scoreboard_dir / f"scoreboard_{date_str}.json"
    manifest_file = out_file.with_suffix(out_file.suffix + ".manifest.json")
    logger.debug(f"[FETCH_SCOREBOARD] Output file: {out_file}")
    logger.debug(f"[FETCH_SCOREBOARD] Manifest file: {manifest_file}")
    
    # Check if file already exists
    file_exists = out_file.exists()
    manifest_exists = manifest_file.exists()
    
    if file_exists:
        file_size = out_file.stat().st_size
        logger.info(f"[FETCH_SCOREBOARD] ✓ Found existing file for {date_str}: {out_file.name} ({file_size} bytes)")
    else:
        logger.info(f"[FETCH_SCOREBOARD] ✗ No existing file found for {date_str}: {out_file.name}")
    
    if manifest_exists:
        logger.info(f"[FETCH_SCOREBOARD] ✓ Found manifest file for {date_str}: {manifest_file.name}")
    else:
        logger.info(f"[FETCH_SCOREBOARD] ✗ No manifest file found for {date_str}: {manifest_file.name}")
    
    # Skip if already exists
    if file_exists and manifest_exists:
        logger.info(f"[FETCH_SCOREBOARD] ⏭️  Skipping fetch for {date_str} - file and manifest already exist")
        return True, f"Scoreboard for {date_str} already exists"
    
    logger.info(f"[FETCH_SCOREBOARD] 🔄 Fetching from ESPN API for {date_str}...")
    
    script_path = repo_root / "scripts" / "fetch_espn_scoreboard.py"
    logger.debug(f"[FETCH_SCOREBOARD] Script path: {script_path}")
    if not script_path.exists():
        logger.error(f"[FETCH_SCOREBOARD] Script not found: {script_path}")
        return False, f"Script not found: {script_path}"
    
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    cmd = [python_bin, str(script_path), "--date", date_str, "--out", str(out_file)]
    logger.info(f"[FETCH_SCOREBOARD] Executing command: {' '.join(cmd)}")
    logger.debug(f"[FETCH_SCOREBOARD] Working directory: {repo_root}")
    logger.debug(f"[FETCH_SCOREBOARD] Python binary: {python_bin}")
    
    env = os.environ.copy()
    logger.debug(f"[FETCH_SCOREBOARD] DATABASE_URL set: {'DATABASE_URL' in env}")
    
    try:
        start_time = datetime.now()
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.debug(f"[FETCH_SCOREBOARD] Command completed in {elapsed:.2f} seconds")
        logger.debug(f"[FETCH_SCOREBOARD] Return code: {result.returncode}")
        logger.debug(f"[FETCH_SCOREBOARD] Stdout length: {len(result.stdout)} chars")
        logger.debug(f"[FETCH_SCOREBOARD] Stderr length: {len(result.stderr)} chars")
        
        if result.returncode == 0:
            if out_file.exists():
                file_size = out_file.stat().st_size
                logger.info(f"[FETCH_SCOREBOARD] ✅ Successfully fetched and saved scoreboard for {date_str} ({file_size} bytes) to {out_file.name}")
                logger.debug(f"[FETCH_SCOREBOARD] Output file exists: {out_file.exists()}")
                logger.debug(f"[FETCH_SCOREBOARD] Manifest exists: {manifest_file.exists()}")
            else:
                logger.warning(f"[FETCH_SCOREBOARD] Command succeeded but output file not found: {out_file}")
            return True, f"Fetched scoreboard for {date_str}"
        else:
            logger.error(f"[FETCH_SCOREBOARD] Command failed with return code {result.returncode}")
            logger.error(f"[FETCH_SCOREBOARD] Stderr: {result.stderr}")
            logger.error(f"[FETCH_SCOREBOARD] Stdout: {result.stdout}")
            return False, f"Error fetching scoreboard (code {result.returncode}): {result.stderr}"
    except subprocess.TimeoutExpired as e:
        logger.error(f"[FETCH_SCOREBOARD] Timeout after 180 seconds for {date_str}")
        logger.error(f"[FETCH_SCOREBOARD] Timeout exception: {str(e)}")
        return False, f"Timeout fetching scoreboard for {date_str}"
    except Exception as e:
        logger.error(f"[FETCH_SCOREBOARD] Exception fetching scoreboard for {date_str}: {str(e)}", exc_info=True)
        return False, f"Exception: {str(e)}"


def load_espn_scoreboard(repo_root: Path, min_date: date | None = None) -> tuple[bool, str]:
    """Load ESPN scoreboard files into database."""
    logger.info("[LOAD_SCOREBOARD] Starting scoreboard load into database")
    
    script_path = repo_root / "scripts" / "load_espn_scoreboard.py"
    logger.debug(f"[LOAD_SCOREBOARD] Script path: {script_path}")
    if not script_path.exists():
        logger.error(f"[LOAD_SCOREBOARD] Script not found: {script_path}")
        return False, f"Script not found: {script_path}"
    
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    scoreboard_dir = repo_root / "data" / "raw" / "espn" / "scoreboard"
    logger.debug(f"[LOAD_SCOREBOARD] Scoreboard directory: {scoreboard_dir}")
    logger.debug(f"[LOAD_SCOREBOARD] Scoreboard directory exists: {scoreboard_dir.exists()}")
    
    if scoreboard_dir.exists():
        scoreboard_files = list(scoreboard_dir.glob("scoreboard_*.json"))
        
        # Filter files by date if min_date is provided
        if min_date:
            filtered_files = []
            for f in scoreboard_files:
                # Extract date from filename: scoreboard_YYYYMMDD.json
                try:
                    date_str = f.stem.split('_')[1]  # Get YYYYMMDD part
                    file_date = datetime.strptime(date_str, "%Y%m%d").date()
                    if file_date >= min_date:
                        filtered_files.append(f)
                except (IndexError, ValueError):
                    # If we can't parse the date, include it to be safe
                    filtered_files.append(f)
            scoreboard_files = filtered_files
            logger.info(f"[LOAD_SCOREBOARD] Filtered to {len(scoreboard_files)} files after {min_date} (from {len(list(scoreboard_dir.glob('scoreboard_*.json')))})")
        else:
            logger.info(f"[LOAD_SCOREBOARD] Found {len(scoreboard_files)} scoreboard files to process (no date filter)")
        
        # Skip if no files to process
        if len(scoreboard_files) == 0:
            logger.info(f"[LOAD_SCOREBOARD] No new scoreboard files to process, skipping load")
            return True, "No new files to process"
        
        logger.debug(f"[LOAD_SCOREBOARD] Files: {[f.name for f in scoreboard_files[:5]]}...")
    
    cmd = [python_bin, str(script_path), "--scoreboard-dir", str(scoreboard_dir)]
    if min_date:
        cmd.extend(["--min-date", min_date.strftime("%Y-%m-%d")])
    logger.info(f"[LOAD_SCOREBOARD] Executing command: {' '.join(cmd)}")
    logger.debug(f"[LOAD_SCOREBOARD] Working directory: {repo_root}")
    
    env = os.environ.copy()
    logger.debug(f"[LOAD_SCOREBOARD] DATABASE_URL set: {'DATABASE_URL' in env}")
    
    try:
        start_time = datetime.now()
        logger.info(f"[LOAD_SCOREBOARD] Starting subprocess (processing ~3,300 scoreboard files)...")
        
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[LOAD_SCOREBOARD] Command completed in {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
        logger.debug(f"[LOAD_SCOREBOARD] Return code: {result.returncode}")
        logger.debug(f"[LOAD_SCOREBOARD] Stdout length: {len(result.stdout)} chars")
        logger.debug(f"[LOAD_SCOREBOARD] Stderr length: {len(result.stderr)} chars")
        
        # Log progress from stdout
        if result.stdout:
            stdout_lines = result.stdout.strip().split('\n')
            progress_lines = [line for line in stdout_lines if 'heartbeat' in line.lower() or 'commit' in line.lower() or 'done' in line.lower()]
            if progress_lines:
                logger.info(f"[LOAD_SCOREBOARD] Progress from script:")
                for line in progress_lines[-5:]:  # Last 5 progress lines
                    logger.info(f"[LOAD_SCOREBOARD]   {line}")
        
        if result.returncode == 0:
            logger.info("[LOAD_SCOREBOARD] Successfully loaded scoreboard data")
            if result.stdout:
                logger.debug(f"[LOAD_SCOREBOARD] Output: {result.stdout[-500:]}")  # Last 500 chars
            return True, "Loaded scoreboard data"
        else:
            logger.error(f"[LOAD_SCOREBOARD] Command failed with return code {result.returncode}")
            logger.error(f"[LOAD_SCOREBOARD] Stderr: {result.stderr}")
            logger.error(f"[LOAD_SCOREBOARD] Stdout: {result.stdout}")
            # Check if error is about missing table
            if "does not exist" in result.stdout or "does not exist" in result.stderr:
                logger.error("[LOAD_SCOREBOARD] NOTE: The script may be trying to insert into 'derived.espn_scoreboard_games'")
                logger.error("[LOAD_SCOREBOARD] NOTE: But migration 027 moved this table to 'espn.scoreboard_games'")
                logger.error("[LOAD_SCOREBOARD] NOTE: The script may need to be updated to use the correct table name")
            return False, f"Error loading scoreboard (code {result.returncode}): {result.stderr}"
    except subprocess.TimeoutExpired as e:
        logger.error("[LOAD_SCOREBOARD] Timeout after 300 seconds")
        logger.error(f"[LOAD_SCOREBOARD] Timeout exception: {str(e)}")
        return False, "Timeout loading scoreboard"
    except Exception as e:
        logger.error(f"[LOAD_SCOREBOARD] Exception loading scoreboard: {str(e)}", exc_info=True)
        return False, f"Exception: {str(e)}"


def fetch_espn_probabilities_for_game(event_id: str, competition_id: str, repo_root: Path, season: str = "2025-26", game_date: str | None = None) -> tuple[bool, str]:
    """Fetch ESPN probabilities for a specific game.
    
    Args:
        event_id: ESPN event ID
        competition_id: ESPN competition ID
        repo_root: Repository root path
        season: Season label (e.g., "2025-26")
        game_date: Optional ISO-8601 date string (e.g., "2025-12-28T20:30Z"). If provided and in the future, skip fetching.
    """
    logger.debug(f"[FETCH_PROBABILITIES] Starting fetch for game: event_id={event_id}, competition_id={competition_id}, season={season}, game_date={game_date}")
    
    # Check if game is in the future
    if game_date:
        try:
            # Parse ISO-8601 date string (e.g., "2025-12-28T20:30Z")
            # Convert 'Z' to '+00:00' for fromisoformat compatibility
            if game_date.endswith('Z'):
                game_date_clean = game_date[:-1] + '+00:00'
            elif '+' in game_date or game_date.count('-') >= 3:
                # Already has timezone info or is just a date
                game_date_clean = game_date
            else:
                # Assume UTC if no timezone specified
                game_date_clean = game_date + '+00:00'
            
            game_dt = datetime.fromisoformat(game_date_clean)
            # Ensure timezone-aware
            if game_dt.tzinfo is None:
                game_dt = game_dt.replace(tzinfo=timezone.utc)
            
            now_dt = datetime.now(timezone.utc)
            
            if game_dt > now_dt:
                logger.info(f"[FETCH_PROBABILITIES] ⏭️  Skipping fetch for {event_id} - game is scheduled for {game_date} (future game)")
                return True, f"Game {event_id} is scheduled for the future, skipping fetch"
        except Exception as e:
            logger.debug(f"[FETCH_PROBABILITIES] Could not parse game_date '{game_date}', proceeding with fetch: {e}")
    
    prob_dir = repo_root / "data" / "raw" / "espn" / "probabilities" / season
    logger.debug(f"[FETCH_PROBABILITIES] Probabilities directory: {prob_dir}")
    prob_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"[FETCH_PROBABILITIES] Probabilities directory created/verified")
    
    out_file = prob_dir / f"event_{event_id}_comp_{competition_id}.json"
    manifest_file = out_file.with_suffix(out_file.suffix + ".manifest.json")
    logger.debug(f"[FETCH_PROBABILITIES] Output file: {out_file}")
    logger.debug(f"[FETCH_PROBABILITIES] Manifest file: {manifest_file}")
    
    # Check if file already exists
    file_exists = out_file.exists()
    manifest_exists = manifest_file.exists()
    
    if file_exists:
        file_size = out_file.stat().st_size
        logger.info(f"[FETCH_PROBABILITIES] ✓ Found existing file for {event_id}: {out_file.name} ({file_size} bytes)")
    else:
        logger.info(f"[FETCH_PROBABILITIES] ✗ No existing file found for {event_id}: {out_file.name}")
    
    if manifest_exists:
        logger.info(f"[FETCH_PROBABILITIES] ✓ Found manifest file for {event_id}: {manifest_file.name}")
    else:
        logger.info(f"[FETCH_PROBABILITIES] ✗ No manifest file found for {event_id}: {manifest_file.name}")
    
    # Skip if already exists
    if file_exists and manifest_exists:
        logger.info(f"[FETCH_PROBABILITIES] ⏭️  Skipping fetch for {event_id} - file and manifest already exist")
        return True, f"Probabilities for {event_id} already exist"
    
    logger.info(f"[FETCH_PROBABILITIES] 🔄 Fetching from ESPN API for {event_id} (competition_id={competition_id})...")
    
    script_path = repo_root / "scripts" / "fetch_espn_probabilities.py"
    logger.debug(f"[FETCH_PROBABILITIES] Script path: {script_path}")
    if not script_path.exists():
        logger.error(f"[FETCH_PROBABILITIES] Script not found: {script_path}")
        return False, f"Script not found: {script_path}"
    
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    cmd = [
        python_bin, str(script_path),
        "--event-id", event_id,
        "--competition-id", competition_id,
        "--out", str(out_file)
    ]
    logger.debug(f"[FETCH_PROBABILITIES] Executing command: {' '.join(cmd)}")
    logger.debug(f"[FETCH_PROBABILITIES] Working directory: {repo_root}")
    
    env = os.environ.copy()
    logger.debug(f"[FETCH_PROBABILITIES] DATABASE_URL set: {'DATABASE_URL' in env}")
    
    try:
        start_time = datetime.now()
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.debug(f"[FETCH_PROBABILITIES] Command completed in {elapsed:.2f} seconds for {event_id}")
        logger.debug(f"[FETCH_PROBABILITIES] Return code: {result.returncode}")
        
        if result.returncode == 0:
            if out_file.exists():
                file_size = out_file.stat().st_size
                logger.info(f"[FETCH_PROBABILITIES] ✅ Successfully fetched and saved probabilities for {event_id} ({file_size} bytes) to {out_file.name}")
            else:
                logger.warning(f"[FETCH_PROBABILITIES] Command succeeded but output file not found: {out_file}")
            return True, f"Fetched probabilities for {event_id}"
        else:
            logger.error(f"[FETCH_PROBABILITIES] Command failed for {event_id} with return code {result.returncode}")
            logger.error(f"[FETCH_PROBABILITIES] Stderr: {result.stderr}")
            logger.error(f"[FETCH_PROBABILITIES] Stdout: {result.stdout}")
            return False, f"Error fetching probabilities (code {result.returncode}): {result.stderr}"
    except subprocess.TimeoutExpired as e:
        logger.error(f"[FETCH_PROBABILITIES] Timeout after 60 seconds for {event_id}")
        logger.error(f"[FETCH_PROBABILITIES] Timeout exception: {str(e)}")
        return False, f"Timeout fetching probabilities for {event_id}"
    except Exception as e:
        logger.error(f"[FETCH_PROBABILITIES] Exception fetching probabilities for {event_id}: {str(e)}", exc_info=True)
        return False, f"Exception: {str(e)}"


def get_current_season(date_obj: date = None) -> str:
    """
    Determine the current NBA season label (e.g., '2025-26').
    
    NBA seasons typically start in October and run through June.
    Season label format: YYYY-YY where YYYY is the year the season starts.
    """
    if date_obj is None:
        date_obj = date.today()
    
    year = date_obj.year
    month = date_obj.month
    
    # NBA season starts in October (month 10)
    # If we're in Oct-Dec, we're in the season that started this year
    # If we're in Jan-Sep, we're in the season that started last year
    if month >= 10:
        # Season started this year (e.g., Oct 2025 = 2025-26 season)
        season_start_year = year
    else:
        # Season started last year (e.g., Jan 2025 = 2024-25 season)
        season_start_year = year - 1
    
    # Calculate end year (last two digits)
    season_end_year = (season_start_year + 1) % 100
    return f"{season_start_year}-{season_end_year:02d}"


def get_previous_season(current_season: str) -> str:
    """Get the previous season label."""
    # Parse "2025-26" -> 2025, then subtract 1
    start_year = int(current_season.split('-')[0])
    prev_start = start_year - 1
    prev_end = (prev_start + 1) % 100
    return f"{prev_start}-{prev_end:02d}"


def get_latest_espn_probability_date() -> datetime | None:
    """
    Get the latest last_modified_utc from espn.probabilities_raw_items.
    Returns None if no data exists.
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(
                """
                SELECT MAX(last_modified_utc) as latest_date
                FROM espn.probabilities_raw_items
                """
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None
    except Exception as e:
        logger.warning(f"[GET_LATEST_PROB_DATE] Error getting latest probability date: {e}")
        return None


def get_latest_espn_scoreboard_date() -> date | None:
    """
    Get the latest event_date from espn.scoreboard_games.
    Returns None if no data exists.
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(
                """
                SELECT MAX(event_date::date) as latest_date
                FROM espn.scoreboard_games
                """
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None
    except Exception as e:
        logger.warning(f"[GET_LATEST_SCOREBOARD_DATE] Error getting latest scoreboard date: {e}")
        return None


def get_latest_kalshi_market_date() -> date | None:
    """
    Get the latest game_date from kalshi.markets.
    Returns None if no data exists.
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(
                """
                SELECT MAX(game_date) as latest_date
                FROM kalshi.markets
                """
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None
    except Exception as e:
        logger.warning(f"[GET_LATEST_KALSHI_DATE] Error getting latest Kalshi market date: {e}")
        return None


def get_latest_kalshi_candlestick_date() -> datetime | None:
    """
    Get the latest period_ts from kalshi.candlesticks.
    Returns None if no data exists.
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(
                """
                SELECT MAX(period_ts) as latest_date
                FROM kalshi.candlesticks
                """
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None
    except Exception as e:
        logger.warning(f"[GET_LATEST_KALSHI_CANDLE_DATE] Error getting latest Kalshi candlestick date: {e}")
        return None


def fetch_and_load_kalshi_markets(repo_root: Path) -> tuple[bool, str]:
    """
    Fetch Kalshi markets and load them into the database.
    
    Uses the TypeScript script fetch_all_markets.ts and then load_kalshi_markets.py.
    """
    logger.info("[KALSHI_MARKETS] Starting Kalshi markets fetch and load")
    
    kalshi_scripts_dir = repo_root / "scripts" / "kalshi"
    fetch_script = kalshi_scripts_dir / "fetch_all_markets.ts"
    load_script = repo_root / "scripts" / "load_kalshi_markets.py"
    
    if not fetch_script.exists():
        logger.warning(f"[KALSHI_MARKETS] Fetch script not found: {fetch_script}")
        return False, f"Fetch script not found: {fetch_script}"
    
    if not load_script.exists():
        logger.warning(f"[KALSHI_MARKETS] Load script not found: {load_script}")
        return False, f"Load script not found: {load_script}"
    
    # Step 1: Fetch markets using TypeScript
    logger.info("[KALSHI_MARKETS] Step 1: Fetching markets from Kalshi API")
    try:
        fetch_cmd = ["npx", "tsx", str(fetch_script)]
        fetch_result = subprocess.run(
            fetch_cmd,
            cwd=str(kalshi_scripts_dir),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
            env=os.environ.copy()
        )
        
        if fetch_result.returncode != 0:
            logger.error(f"[KALSHI_MARKETS] Fetch failed with return code {fetch_result.returncode}")
            logger.error(f"[KALSHI_MARKETS] Stderr: {fetch_result.stderr}")
            return False, f"Failed to fetch Kalshi markets: {fetch_result.stderr}"
        
        logger.info("[KALSHI_MARKETS] ✓ Successfully fetched markets")
        
        # Find the most recent fetch directory
        markets_dir = repo_root / "data" / "raw" / "kalshi" / "markets"
        fetch_dirs = sorted([d for d in markets_dir.iterdir() if d.is_dir() and d.name.startswith("fetch_")], reverse=True)
        
        if not fetch_dirs:
            return False, "No fetch directories found after fetching"
        
        latest_fetch_dir = fetch_dirs[0]
        markets_file = latest_fetch_dir / "all_markets.json"
        
        if not markets_file.exists():
            return False, f"Markets file not found: {markets_file}"
        
        logger.info(f"[KALSHI_MARKETS] Found markets file: {markets_file}")
        
    except subprocess.TimeoutExpired:
        return False, "Timeout fetching Kalshi markets"
    except Exception as e:
        logger.error(f"[KALSHI_MARKETS] Exception fetching markets: {e}", exc_info=True)
        return False, f"Exception: {str(e)}"
    
    # Step 2: Load markets into database
    logger.info("[KALSHI_MARKETS] Step 2: Loading markets into database")
    try:
        python_bin = os.environ.get("PYTHON_BIN", "python3")
        load_cmd = [python_bin, str(load_script), "--markets-file", str(markets_file)]
        
        load_result = subprocess.run(
            load_cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=300,
            env=os.environ.copy()
        )
        
        if load_result.returncode != 0:
            logger.error(f"[KALSHI_MARKETS] Load failed with return code {load_result.returncode}")
            logger.error(f"[KALSHI_MARKETS] Stderr: {load_result.stderr}")
            return False, f"Failed to load Kalshi markets: {load_result.stderr}"
        
        logger.info("[KALSHI_MARKETS] ✓ Successfully loaded markets")
        return True, "Kalshi markets fetched and loaded successfully"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout loading Kalshi markets"
    except Exception as e:
        logger.error(f"[KALSHI_MARKETS] Exception loading markets: {e}", exc_info=True)
        return False, f"Exception: {str(e)}"


def fetch_and_load_kalshi_candlesticks(repo_root: Path) -> tuple[bool, str]:
    """
    Fetch Kalshi candlesticks and load them into the database.
    
    Uses the TypeScript script fetch_all_candlesticks.ts and then load_kalshi_candlesticks.py.
    """
    logger.info("[KALSHI_CANDLES] Starting Kalshi candlesticks fetch and load")
    
    kalshi_scripts_dir = repo_root / "scripts" / "kalshi"
    fetch_script = kalshi_scripts_dir / "fetch_all_candlesticks.ts"
    load_script = repo_root / "scripts" / "load_kalshi_candlesticks.py"
    
    if not fetch_script.exists():
        logger.warning(f"[KALSHI_CANDLES] Fetch script not found: {fetch_script}")
        return False, f"Fetch script not found: {fetch_script}"
    
    if not load_script.exists():
        logger.warning(f"[KALSHI_CANDLES] Load script not found: {load_script}")
        return False, f"Load script not found: {load_script}"
    
    # Step 1: Fetch candlesticks using TypeScript
    logger.info("[KALSHI_CANDLES] Step 1: Fetching candlesticks from Kalshi API")
    try:
        fetch_cmd = ["npx", "tsx", str(fetch_script)]
        fetch_result = subprocess.run(
            fetch_cmd,
            cwd=str(kalshi_scripts_dir),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes (candlesticks can take longer)
            env=os.environ.copy()
        )
        
        if fetch_result.returncode != 0:
            logger.error(f"[KALSHI_CANDLES] Fetch failed with return code {fetch_result.returncode}")
            logger.error(f"[KALSHI_CANDLES] Stderr: {fetch_result.stderr}")
            return False, f"Failed to fetch Kalshi candlesticks: {fetch_result.stderr}"
        
        logger.info("[KALSHI_CANDLES] ✓ Successfully fetched candlesticks")
        
        # Find the most recent fetch directory
        candlesticks_dir = repo_root / "data" / "raw" / "kalshi" / "candlesticks"
        fetch_dirs = sorted([d for d in candlesticks_dir.iterdir() if d.is_dir() and d.name.startswith("fetch_")], reverse=True)
        
        if not fetch_dirs:
            return False, "No fetch directories found after fetching"
        
        latest_fetch_dir = fetch_dirs[0]
        logger.info(f"[KALSHI_CANDLES] Found candlesticks directory: {latest_fetch_dir}")
        
    except subprocess.TimeoutExpired:
        return False, "Timeout fetching Kalshi candlesticks"
    except Exception as e:
        logger.error(f"[KALSHI_CANDLES] Exception fetching candlesticks: {e}", exc_info=True)
        return False, f"Exception: {str(e)}"
    
    # Step 2: Load candlesticks into database
    logger.info("[KALSHI_CANDLES] Step 2: Loading candlesticks into database")
    try:
        python_bin = os.environ.get("PYTHON_BIN", "python3")
        load_cmd = [python_bin, str(load_script), "--candlesticks-dir", str(latest_fetch_dir)]
        
        load_result = subprocess.run(
            load_cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy()
        )
        
        if load_result.returncode != 0:
            logger.error(f"[KALSHI_CANDLES] Load failed with return code {load_result.returncode}")
            logger.error(f"[KALSHI_CANDLES] Stderr: {load_result.stderr}")
            return False, f"Failed to load Kalshi candlesticks: {load_result.stderr}"
        
        logger.info("[KALSHI_CANDLES] ✓ Successfully loaded candlesticks")
        return True, "Kalshi candlesticks fetched and loaded successfully"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout loading Kalshi candlesticks"
    except Exception as e:
        logger.error(f"[KALSHI_CANDLES] Exception loading candlesticks: {e}", exc_info=True)
        return False, f"Exception: {str(e)}"


def load_espn_probabilities(repo_root: Path, season_label: str = None, min_date: datetime | None = None) -> tuple[bool, str]:
    """
    Load ESPN probabilities into database.
    
    Args:
        season_label: If provided, only load this season. Otherwise, loads current season.
        min_date: If provided, only process files that might contain data after this date.
                 Note: Probability files don't have dates in filenames, so we filter by
                 file modification time as a proxy.
    """
    logger.info("[LOAD_PROBABILITIES] Starting probabilities load into database")
    
    script_path = repo_root / "scripts" / "load_espn_probabilities_raw_items.py"
    logger.debug(f"[LOAD_PROBABILITIES] Script path: {script_path}")
    if not script_path.exists():
        logger.error(f"[LOAD_PROBABILITIES] Script not found: {script_path}")
        return False, f"Script not found: {script_path}"
    
    python_bin = os.environ.get("PYTHON_BIN", "python3")
    prob_root = repo_root / "data" / "raw" / "espn" / "probabilities"
    logger.debug(f"[LOAD_PROBABILITIES] Probabilities root: {prob_root}")
    logger.debug(f"[LOAD_PROBABILITIES] Probabilities root exists: {prob_root.exists()}")
    
    # Determine which season(s) to load
    if season_label is None:
        season_label = get_current_season()
        logger.info(f"[LOAD_PROBABILITIES] No season specified, using current season: {season_label}")
    
    # Check if season directory exists
    season_dir = prob_root / season_label
    if not season_dir.exists():
        logger.warning(f"[LOAD_PROBABILITIES] Season directory does not exist: {season_dir}")
        # Try previous season as fallback (in case we're at the start of a new season)
        prev_season = get_previous_season(season_label)
        prev_season_dir = prob_root / prev_season
        if prev_season_dir.exists():
            logger.info(f"[LOAD_PROBABILITIES] Falling back to previous season: {prev_season}")
            season_label = prev_season
        else:
            logger.error(f"[LOAD_PROBABILITIES] Neither {season_label} nor {prev_season} directories exist")
            return False, f"Season directory not found: {season_label} or {prev_season}"
    
    # Count files in the season directory
    prob_files = list(season_dir.glob("event_*.json"))
    
    # Filter by file modification time if min_date is provided
    if min_date:
        original_count = len(prob_files)
        prob_files = [
            f for f in prob_files
            if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) >= min_date
        ]
        logger.info(f"[LOAD_PROBABILITIES] Filtered to {len(prob_files)} files modified after {min_date} (from {original_count} total in {season_label})")
    else:
        logger.info(f"[LOAD_PROBABILITIES] Loading season {season_label}: {len(prob_files)} probability files (no date filter)")
    
    # Skip if no files to process
    if len(prob_files) == 0:
        logger.info(f"[LOAD_PROBABILITIES] No new probability files to process for season {season_label}, skipping load")
        return True, "No new files to process"
    
    cmd = [python_bin, str(script_path), "--probabilities-root", str(prob_root), "--season-label", season_label, "--commit-every", "100"]
    if min_date:
        # Format datetime as ISO8601 string for the script
        # Ensure timezone-aware datetime
        if min_date.tzinfo is None:
            min_date = min_date.replace(tzinfo=timezone.utc)
        # Format with timezone offset
        offset = min_date.strftime("%z")
        if offset:
            min_date_str = min_date.strftime("%Y-%m-%dT%H:%M:%S") + offset[:3] + ":" + offset[3:]
        else:
            min_date_str = min_date.strftime("%Y-%m-%dT%H:%M:%S%z")
        cmd.extend(["--min-modified-time", min_date_str])
    logger.info(f"[LOAD_PROBABILITIES] Executing command: {' '.join(cmd)}")
    logger.debug(f"[LOAD_PROBABILITIES] Working directory: {repo_root}")
    logger.debug(f"[LOAD_PROBABILITIES] Timeout: 600 seconds (10 minutes)")
    
    env = os.environ.copy()
    logger.debug(f"[LOAD_PROBABILITIES] DATABASE_URL set: {'DATABASE_URL' in env}")
    
    try:
        start_time = datetime.now()
        logger.info(f"[LOAD_PROBABILITIES] Starting subprocess - processing {len(prob_files):,} probability files from season {season_label}")
        logger.info(f"[LOAD_PROBABILITIES] This may take several minutes. Progress will be logged in real-time.")
        
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env
        )
        
        stdout_lines = []
        stderr_lines = []
        last_progress_log = [datetime.now()]  # Use list to allow modification in nested function
        
        # Use threading to read both stdout and stderr in real-time
        def read_output(pipe, lines_list):
            for line in iter(pipe.readline, ''):
                if line:
                    line = line.strip()
                    lines_list.append(line)
                    
                    # Parse progress messages and log them
                    if '[load_espn_prob_raw]' in line:
                        # Parse heartbeat: "heartbeat file=X/Y total_files=Z total_items=W upserts=U errors=E"
                        if 'heartbeat' in line:
                            # Extract numbers from heartbeat
                            file_match = re.search(r'file=(\d+)/(\d+)', line)
                            total_files_match = re.search(r'total_files=(\d+)', line)
                            total_items_match = re.search(r'total_items=(\d+)', line)
                            upserts_match = re.search(r'upserts=(\d+)', line)
                            errors_match = re.search(r'errors=(\d+)', line)
                            
                            if file_match and total_files_match:
                                current_file = file_match.group(1)
                                total_file_count = file_match.group(2)
                                files_processed = total_files_match.group(1)
                                items = total_items_match.group(1) if total_items_match else "0"
                                upserts = upserts_match.group(1) if upserts_match else "0"
                                errors = errors_match.group(1) if errors_match else "0"
                                
                                # Log progress every 5 seconds
                                now = datetime.now()
                                if (now - last_progress_log[0]).total_seconds() >= 5:
                                    logger.info(f"[LOAD_PROBABILITIES] Progress: {files_processed}/{total_file_count} files processed, {items} items, {upserts} upserts, {errors} errors")
                                    last_progress_log[0] = now
                        
                        # Parse commit messages
                        elif 'commit' in line:
                            commit_match = re.search(r'commit files=(\d+) items=(\d+) upserts=(\d+) errors=(\d+)', line)
                            if commit_match:
                                files = commit_match.group(1)
                                items = commit_match.group(2)
                                upserts = commit_match.group(3)
                                errors = commit_match.group(4)
                                logger.info(f"[LOAD_PROBABILITIES] Committed: {files} files, {items} items, {upserts} upserts, {errors} errors")
                        
                        # Parse done message
                        elif 'done' in line:
                            done_match = re.search(r'done files=(\d+) items=(\d+) upserts=(\d+) errors=(\d+)', line)
                            if done_match:
                                files = done_match.group(1)
                                items = done_match.group(2)
                                upserts = done_match.group(3)
                                errors = done_match.group(4)
                                logger.info(f"[LOAD_PROBABILITIES] ✓ Completed: {files} files, {items} items, {upserts} upserts, {errors} errors")
            pipe.close()
        
        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout_lines))
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr_lines))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process to complete with timeout
        try:
            return_code = process.wait(timeout=600)  # 10 minutes
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait()
            logger.error("[LOAD_PROBABILITIES] Process timed out after 600 seconds")
        
        # Wait for threads to finish reading (with timeout)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"[LOAD_PROBABILITIES] Command completed in {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
        logger.debug(f"[LOAD_PROBABILITIES] Return code: {return_code}")
        logger.debug(f"[LOAD_PROBABILITIES] Stdout lines: {len(stdout_lines)}")
        logger.debug(f"[LOAD_PROBABILITIES] Stderr lines: {len(stderr_lines)}")
        
        # Create result-like object for compatibility
        class Result:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        
        result = Result(return_code, '\n'.join(stdout_lines), '\n'.join(stderr_lines))
        
        if result.returncode == 0:
            logger.info("[LOAD_PROBABILITIES] Successfully loaded probabilities data")
            # Extract and log key progress information from stdout
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')
                # Find heartbeat and commit lines
                progress_lines = [line for line in stdout_lines if any(keyword in line.lower() for keyword in ['heartbeat', 'commit', 'done', 'start'])]
                if progress_lines:
                    logger.info(f"[LOAD_PROBABILITIES] Progress summary from script:")
                    # Show start, some middle heartbeats, and final result
                    if len(progress_lines) > 0:
                        logger.info(f"[LOAD_PROBABILITIES]   {progress_lines[0]}")  # Start
                    if len(progress_lines) > 1:
                        # Show a few middle ones if there are many
                        if len(progress_lines) > 5:
                            for line in progress_lines[1:4]:
                                logger.info(f"[LOAD_PROBABILITIES]   {line}")
                            logger.info(f"[LOAD_PROBABILITIES]   ... (processing continues) ...")
                        # Show last few
                        for line in progress_lines[-3:]:
                            logger.info(f"[LOAD_PROBABILITIES]   {line}")
                else:
                    # Fallback: show last 10 lines
                    logger.debug(f"[LOAD_PROBABILITIES] Last 10 output lines:")
                    for line in stdout_lines[-10:]:
                        logger.debug(f"[LOAD_PROBABILITIES]   {line}")
            return True, "Loaded probabilities data"
        else:
            logger.error(f"[LOAD_PROBABILITIES] Command failed with return code {result.returncode}")
            logger.error(f"[LOAD_PROBABILITIES] Stderr: {result.stderr}")
            logger.error(f"[LOAD_PROBABILITIES] Stdout (last 1000 chars): {result.stdout[-1000:]}")
            return False, f"Error loading probabilities (code {result.returncode}): {result.stderr}"
    except subprocess.TimeoutExpired as e:
        logger.error("[LOAD_PROBABILITIES] Timeout after 600 seconds")
        logger.error(f"[LOAD_PROBABILITIES] Timeout exception: {str(e)}")
        return False, "Timeout loading probabilities"
    except Exception as e:
        logger.error(f"[LOAD_PROBABILITIES] Exception loading probabilities: {str(e)}", exc_info=True)
        return False, f"Exception: {str(e)}"


def get_new_games_from_scoreboard(repo_root: Path, days_back: int = 7) -> list[dict[str, Any]]:
    """Get list of new games from scoreboard files that don't have probabilities yet."""
    logger.info(f"[GET_NEW_GAMES] Starting scan for new games (last {days_back} days)")
    new_games = []
    
    # Get scoreboard files for last N days
    scoreboard_dir = repo_root / "data" / "raw" / "espn" / "scoreboard"
    logger.debug(f"[GET_NEW_GAMES] Scoreboard directory: {scoreboard_dir}")
    if not scoreboard_dir.exists():
        logger.warning(f"[GET_NEW_GAMES] Scoreboard directory does not exist: {scoreboard_dir}")
        return new_games
    
    today = date.today()
    logger.debug(f"[GET_NEW_GAMES] Today's date: {today}")
    scoreboard_files_found = 0
    total_events_checked = 0
    
    for i in range(days_back):
        check_date = today - timedelta(days=i)
        date_str = check_date.strftime("%Y%m%d")
        scoreboard_file = scoreboard_dir / f"scoreboard_{date_str}.json"
        logger.debug(f"[GET_NEW_GAMES] Checking date {date_str}: {scoreboard_file.exists()}")
        
        if not scoreboard_file.exists():
            logger.debug(f"[GET_NEW_GAMES] Scoreboard file not found for {date_str}, skipping")
            continue
        
        scoreboard_files_found += 1
        logger.debug(f"[GET_NEW_GAMES] Processing scoreboard file: {scoreboard_file}")
        file_size = scoreboard_file.stat().st_size
        logger.debug(f"[GET_NEW_GAMES] File size: {file_size} bytes")
        
        try:
            with open(scoreboard_file, 'r') as f:
                scoreboard_data = json.load(f)
            
            events = scoreboard_data.get("events", [])
            logger.debug(f"[GET_NEW_GAMES] Found {len(events)} events in scoreboard for {date_str}")
            total_events_checked += len(events)
            
            for event_idx, event in enumerate(events):
                if not isinstance(event, dict):
                    logger.debug(f"[GET_NEW_GAMES] Event {event_idx} is not a dict, skipping")
                    continue
                
                event_id = str(event.get("id", ""))
                if not event_id:
                    logger.debug(f"[GET_NEW_GAMES] Event {event_idx} has no id, skipping")
                    continue
                
                competitions = event.get("competitions", [])
                logger.debug(f"[GET_NEW_GAMES] Event {event_id} has {len(competitions)} competitions")
                
                for comp_idx, comp in enumerate(competitions):
                    if not isinstance(comp, dict):
                        logger.debug(f"[GET_NEW_GAMES] Competition {comp_idx} for event {event_id} is not a dict, skipping")
                        continue
                    
                    competition_id = str(comp.get("id", ""))
                    if not competition_id:
                        logger.debug(f"[GET_NEW_GAMES] Competition {comp_idx} for event {event_id} has no id, skipping")
                        continue
                    
                    # Check if probabilities file exists (check current season and previous season)
                    current_season = get_current_season()
                    prev_season = get_previous_season(current_season)
                    
                    # Check current season first
                    prob_file = repo_root / "data" / "raw" / "espn" / "probabilities" / current_season / f"event_{event_id}_comp_{competition_id}.json"
                    if not prob_file.exists():
                        # Check previous season (in case we're at the start of a new season)
                        prob_file = repo_root / "data" / "raw" / "espn" / "probabilities" / prev_season / f"event_{event_id}_comp_{competition_id}.json"
                    
                    logger.debug(f"[GET_NEW_GAMES] Checking probabilities file: {prob_file.exists()}")
                    
                    if not prob_file.exists():
                        # Extract game date from event (ISO-8601 format, e.g., "2025-12-28T20:30Z")
                        event_date = event.get("date")
                        logger.info(f"[GET_NEW_GAMES] New game found: event_id={event_id}, competition_id={competition_id}, date={date_str}, event_date={event_date}")
                        new_games.append({
                            "event_id": event_id,
                            "competition_id": competition_id,
                            "date": date_str,
                            "event_date": event_date  # ISO-8601 date string from ESPN
                        })
                    else:
                        logger.debug(f"[GET_NEW_GAMES] Probabilities already exist for event {event_id}")
        except json.JSONDecodeError as e:
            logger.error(f"[GET_NEW_GAMES] JSON decode error reading scoreboard {scoreboard_file}: {e}")
            continue
        except Exception as e:
            logger.error(f"[GET_NEW_GAMES] Error reading scoreboard {scoreboard_file}: {e}", exc_info=True)
            continue
    
    logger.info(f"[GET_NEW_GAMES] Scan complete: {scoreboard_files_found} scoreboard files, {total_events_checked} events checked, {len(new_games)} new games found")
    return new_games


def run_update_task() -> dict[str, Any]:
    """
    Run the full update task.
    
    Note: This function uses a lock to prevent concurrent execution.
    The scripts are idempotent (use UPSERT), but running multiple updates
    simultaneously wastes resources.
    """
    global _update_task_running
    
    # Acquire lock to prevent concurrent execution
    if not _update_task_lock.acquire(blocking=False):
        logger.warning("[UPDATE_TASK] Another update task is already running, skipping")
        return {
            "status": "skipped",
            "message": "Update task is already running",
            "start_time": datetime.now().isoformat()
        }
    
    try:
        _update_task_running = True
        update_start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Starting data update task")
        logger.info(f"[UPDATE_TASK] Start time: {update_start_time.isoformat()}")
        logger.info("=" * 80)
        
        repo_root = get_repo_root()
        logger.info(f"[UPDATE_TASK] Repository root: {repo_root}")
        logger.debug(f"[UPDATE_TASK] Repository root exists: {repo_root.exists()}")
        
        results = {
            "scoreboard_fetched": 0,
            "scoreboard_loaded": False,
            "probabilities_fetched": 0,
            "probabilities_loaded": False,
            "kalshi_markets_fetched": False,
            "kalshi_markets_loaded": False,
            "kalshi_candlesticks_fetched": False,
            "kalshi_candlesticks_loaded": False,
            "errors": [],
            "start_time": update_start_time.isoformat(),
            "end_time": None,
            "duration_seconds": None
        }
        
        # Step 1: Fetch scoreboards for last 7 days
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 1: Fetching ESPN scoreboards for last 7 days")
        logger.info("=" * 80)
        step1_start = datetime.now()
        today = date.today()
        logger.info(f"[UPDATE_TASK] Today's date: {today}")
        
        for i in range(7):
            check_date = today - timedelta(days=i)
            date_str = check_date.strftime("%Y%m%d")
            logger.info(f"[UPDATE_TASK] Processing date {i+1}/7: {date_str} ({check_date})")
            success, message = fetch_espn_scoreboard_for_date(date_str, repo_root)
            if success:
                results["scoreboard_fetched"] += 1
                logger.info(f"[UPDATE_TASK] ✓ Successfully processed scoreboard for {date_str}")
            else:
                results["errors"].append(f"Scoreboard {date_str}: {message}")
                logger.warning(f"[UPDATE_TASK] ✗ Failed to process scoreboard for {date_str}: {message}")
        
        step1_elapsed = (datetime.now() - step1_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 1 completed in {step1_elapsed:.2f} seconds")
        logger.info(f"[UPDATE_TASK] Step 1 results: {results['scoreboard_fetched']}/7 scoreboards fetched")
        
        # Step 2: Load scoreboards into DB
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 2: Loading scoreboards into database")
        logger.info("=" * 80)
        step2_start = datetime.now()
        
        # Get latest scoreboard date to optimize loading
        latest_scoreboard_date = get_latest_espn_scoreboard_date()
        if latest_scoreboard_date:
            # Safety check: if date is in the future, ignore it (data issue)
            today = date.today()
            if latest_scoreboard_date > today:
                logger.warning(f"[UPDATE_TASK] Latest scoreboard date ({latest_scoreboard_date}) is in the future, ignoring and processing all files")
                latest_scoreboard_date = None
            else:
                logger.info(f"[UPDATE_TASK] Latest scoreboard date in DB: {latest_scoreboard_date}")
                logger.info(f"[UPDATE_TASK] Only processing scoreboard files after {latest_scoreboard_date}")
        else:
            logger.info(f"[UPDATE_TASK] No existing scoreboard data, processing all files")
        
        success, message = load_espn_scoreboard(repo_root, min_date=latest_scoreboard_date)
        results["scoreboard_loaded"] = success
        if not success:
            results["errors"].append(f"Load scoreboard: {message}")
            logger.error(f"[UPDATE_TASK] ✗ Step 2 failed: {message}")
        else:
            logger.info(f"[UPDATE_TASK] ✓ Step 2 succeeded: {message}")
        step2_elapsed = (datetime.now() - step2_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 2 completed in {step2_elapsed:.2f} seconds")
        
        # Step 3: Identify new games and fetch probabilities
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 3: Identifying new games and fetching probabilities")
        logger.info("=" * 80)
        step3_start = datetime.now()
        new_games = get_new_games_from_scoreboard(repo_root, days_back=7)
        logger.info(f"[UPDATE_TASK] Found {len(new_games)} new games to fetch")
        
        if new_games:
            logger.info(f"[UPDATE_TASK] New games list:")
            for idx, game in enumerate(new_games, 1):
                logger.info(f"[UPDATE_TASK]   {idx}. Event {game['event_id']}, Competition {game['competition_id']}, Date {game['date']}")
        
        for idx, game in enumerate(new_games, 1):
            logger.info(f"[UPDATE_TASK] Processing probabilities {idx}/{len(new_games)}: event_id={game['event_id']}, competition_id={game['competition_id']}, date={game['date']}")
            success, message = fetch_espn_probabilities_for_game(
                game["event_id"],
                game["competition_id"],
                repo_root,
                game_date=game.get("event_date")  # Pass the ISO-8601 date string from ESPN
            )
            if success:
                results["probabilities_fetched"] += 1
                logger.info(f"[UPDATE_TASK] ✓ Successfully fetched probabilities for {game['event_id']}")
            else:
                results["errors"].append(f"Fetch probabilities {game['event_id']}: {message}")
                logger.warning(f"[UPDATE_TASK] ✗ Failed to fetch probabilities for {game['event_id']}: {message}")
        
        step3_elapsed = (datetime.now() - step3_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 3 completed in {step3_elapsed:.2f} seconds")
        logger.info(f"[UPDATE_TASK] Step 3 results: {results['probabilities_fetched']}/{len(new_games)} probabilities fetched")
        
        # Step 4: Load probabilities into DB
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 4: Loading probabilities into database")
        logger.info("=" * 80)
        step4_start = datetime.now()
        
        # Determine current season to only load recent data (much faster!)
        current_season = get_current_season()
        logger.info(f"[UPDATE_TASK] Loading probabilities for current season only: {current_season}")
        
        # Get latest probability date to optimize loading
        latest_prob_date = get_latest_espn_probability_date()
        if latest_prob_date:
            logger.info(f"[UPDATE_TASK] Latest probability date in DB: {latest_prob_date}")
            logger.info(f"[UPDATE_TASK] Only processing probability files modified after {latest_prob_date}")
        else:
            logger.info(f"[UPDATE_TASK] No existing probability data, processing all files")
        
        logger.info(f"[UPDATE_TASK] This will process only new/modified files (much faster!)")
        
        success, message = load_espn_probabilities(repo_root, season_label=current_season, min_date=latest_prob_date)
        results["probabilities_loaded"] = success
        if not success:
            results["errors"].append(f"Load probabilities: {message}")
            logger.error(f"[UPDATE_TASK] ✗ Step 4 failed: {message}")
        else:
            logger.info(f"[UPDATE_TASK] ✓ Step 4 succeeded: {message}")
        step4_elapsed = (datetime.now() - step4_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 4 completed in {step4_elapsed:.2f} seconds")
        
        # Step 5: Fetch and load Kalshi markets
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 5: Fetching and loading Kalshi markets")
        logger.info("=" * 80)
        step5_start = datetime.now()
        
        # Get latest Kalshi market date to optimize
        latest_kalshi_date = get_latest_kalshi_market_date()
        if latest_kalshi_date:
            logger.info(f"[UPDATE_TASK] Latest Kalshi market date in DB: {latest_kalshi_date}")
        else:
            logger.info(f"[UPDATE_TASK] No existing Kalshi market data")
        
        success, message = fetch_and_load_kalshi_markets(repo_root)
        results["kalshi_markets_fetched"] = success
        results["kalshi_markets_loaded"] = success
        if not success:
            results["errors"].append(f"Kalshi markets: {message}")
            logger.error(f"[UPDATE_TASK] ✗ Step 5 failed: {message}")
        else:
            logger.info(f"[UPDATE_TASK] ✓ Step 5 succeeded: {message}")
        step5_elapsed = (datetime.now() - step5_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 5 completed in {step5_elapsed:.2f} seconds")
        
        # Step 6: Fetch and load Kalshi candlesticks
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Step 6: Fetching and loading Kalshi candlesticks")
        logger.info("=" * 80)
        step6_start = datetime.now()
        
        # Get latest candlestick date to optimize
        latest_candle_date = get_latest_kalshi_candlestick_date()
        if latest_candle_date:
            logger.info(f"[UPDATE_TASK] Latest Kalshi candlestick date in DB: {latest_candle_date}")
        else:
            logger.info(f"[UPDATE_TASK] No existing Kalshi candlestick data")
        
        success, message = fetch_and_load_kalshi_candlesticks(repo_root)
        results["kalshi_candlesticks_fetched"] = success
        results["kalshi_candlesticks_loaded"] = success
        if not success:
            results["errors"].append(f"Kalshi candlesticks: {message}")
            logger.error(f"[UPDATE_TASK] ✗ Step 6 failed: {message}")
        else:
            logger.info(f"[UPDATE_TASK] ✓ Step 6 succeeded: {message}")
        step6_elapsed = (datetime.now() - step6_start).total_seconds()
        logger.info(f"[UPDATE_TASK] Step 6 completed in {step6_elapsed:.2f} seconds")
        
        # Final summary
        update_end_time = datetime.now()
        total_duration = (update_end_time - update_start_time).total_seconds()
        results["end_time"] = update_end_time.isoformat()
        results["duration_seconds"] = total_duration
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("[UPDATE_TASK] Update task completed")
        logger.info("=" * 80)
        logger.info(f"[UPDATE_TASK] Total duration: {total_duration:.2f} seconds ({total_duration/60:.2f} minutes)")
        logger.info(f"[UPDATE_TASK] Results summary:")
        logger.info(f"[UPDATE_TASK]   - Scoreboards fetched: {results['scoreboard_fetched']}/7")
        logger.info(f"[UPDATE_TASK]   - Scoreboards loaded: {results['scoreboard_loaded']}")
        logger.info(f"[UPDATE_TASK]   - Probabilities fetched: {results['probabilities_fetched']}")
        logger.info(f"[UPDATE_TASK]   - Probabilities loaded: {results['probabilities_loaded']}")
        logger.info(f"[UPDATE_TASK]   - Kalshi markets fetched/loaded: {results['kalshi_markets_loaded']}")
        logger.info(f"[UPDATE_TASK]   - Kalshi candlesticks fetched/loaded: {results['kalshi_candlesticks_loaded']}")
        logger.info(f"[UPDATE_TASK]   - Errors: {len(results['errors'])}")
        if results["errors"]:
            logger.warning(f"[UPDATE_TASK] Error details:")
            for error in results["errors"]:
                logger.warning(f"[UPDATE_TASK]   - {error}")
        logger.info("=" * 80)
        
        # Clear games cache after successful update
        if results["probabilities_loaded"] or results["scoreboard_loaded"]:
            logger.info("")
            logger.info("[UPDATE_TASK] Clearing games endpoint cache to ensure fresh data...")
            try:
                cache_dir = Path(__file__).parent.parent.parent / ".cache"
                cache_file = cache_dir / "list_games.cache"
                
                if cache_file.exists():
                    cache_instance = SimpleCache(ttl_seconds=86400, cache_file="list_games.cache")
                    cache_size = len(cache_instance.cache)
                    cache_instance.clear()
                    logger.info(f"[UPDATE_TASK] ✓ Games cache cleared ({cache_size} entries removed)")
                else:
                    logger.debug("[UPDATE_TASK] No cache file to clear")
            except Exception as e:
                logger.warning(f"[UPDATE_TASK] Failed to clear cache: {e}")
        
        return results
        
    except Exception as e:
        update_end_time = datetime.now()
        total_duration = (update_end_time - update_start_time).total_seconds()
        results["end_time"] = update_end_time.isoformat()
        results["duration_seconds"] = total_duration
        
        logger.error("=" * 80)
        logger.error(f"[UPDATE_TASK] Update task failed with exception after {total_duration:.2f} seconds")
        logger.error("=" * 80)
        logger.error(f"[UPDATE_TASK] Exception: {str(e)}", exc_info=True)
        results["errors"].append(f"Update task exception: {str(e)}")
        logger.error("=" * 80)
        return results
    finally:
        # Always release lock and reset flag
        _update_task_running = False
        _update_task_lock.release()
        logger.info("[UPDATE_TASK] Lock released, update task complete")


@router.post("/update/clear-cache")
def clear_games_cache() -> dict[str, Any]:
    """
    Clear the games endpoint cache.
    
    This is useful after running data updates to ensure fresh data is returned.
    Clears both the cache file and forces a reload by deleting the file.
    """
    logger.info("[CLEAR_CACHE] Clearing games endpoint cache")
    
    try:
        # Get cache file path
        cache_dir = Path(__file__).parent.parent.parent / ".cache"
        cache_file = cache_dir / "list_games.cache"
        
        logger.debug(f"[CLEAR_CACHE] Cache directory: {cache_dir}")
        logger.debug(f"[CLEAR_CACHE] Cache file: {cache_file}")
        logger.debug(f"[CLEAR_CACHE] Cache file exists: {cache_file.exists()}")
        
        # Try to access the actual cache instance from the games endpoint function
        # The decorator stores it as _cache_instance on the function
        cache_size_before = 0
        cache_cleared = False
        
        try:
            if hasattr(games.list_games, '_cache_instance'):
                actual_cache = games.list_games._cache_instance
                cache_size_before = len(actual_cache.cache)
                logger.info(f"[CLEAR_CACHE] Found games endpoint cache instance: {cache_size_before} entries")
                actual_cache.clear()
                cache_cleared = True
                logger.info(f"[CLEAR_CACHE] Cleared in-memory cache from games endpoint")
            else:
                logger.warning(f"[CLEAR_CACHE] Games endpoint cache instance not found, creating new instance to clear file")
                # Fallback: create new instance and clear it
                cache_instance = SimpleCache(ttl_seconds=86400, cache_file="list_games.cache")
                cache_size_before = len(cache_instance.cache)
                cache_instance.clear()
        except Exception as e:
            logger.warning(f"[CLEAR_CACHE] Error accessing games cache instance: {e}")
        
        # Also delete the file to force fresh load on next request
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"[CLEAR_CACHE] Cache file deleted: {cache_file}")
        
        return {
            "status": "success",
            "message": f"Games cache cleared ({cache_size_before} entries removed, file deleted)" if cache_cleared else f"Games cache file deleted (in-memory cache may need next request to clear)",
            "cache_file": str(cache_file),
            "entries_removed": cache_size_before,
            "in_memory_cleared": cache_cleared
        }
    except Exception as e:
        logger.error(f"[CLEAR_CACHE] Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@router.post("/update/trigger")
def trigger_update(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """
    Trigger data update: fetch and load new ESPN and Kalshi data.
    
    This runs in the background and may take several minutes.
    
    Note: If an update is already running, this will return an error to prevent
    concurrent execution. The scripts are idempotent (use UPSERT), but running
    multiple updates simultaneously wastes resources.
    """
    global _update_task_running
    
    logger.info("=" * 80)
    logger.info("[TRIGGER_UPDATE] Update endpoint called")
    logger.info(f"[TRIGGER_UPDATE] Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    # Check if update is already running
    if _update_task_running:
        logger.warning("[TRIGGER_UPDATE] Update task is already running, rejecting concurrent request")
        raise HTTPException(
            status_code=409,
            detail="Update task is already running. Please wait for it to complete before triggering another update."
        )
    
    # Run update in background
    logger.info("[TRIGGER_UPDATE] Queuing update task in background")
    background_tasks.add_task(run_update_task)
    logger.info("[TRIGGER_UPDATE] Update task queued successfully")
    
    response = {
        "status": "update_queued",
        "message": "Data update has been queued. This may take several minutes.",
        "note": "The update will: 1) Fetch ESPN scoreboards, 2) Load scoreboards, 3) Fetch new probabilities, 4) Load probabilities",
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"[TRIGGER_UPDATE] Returning response: {response}")
    return response

