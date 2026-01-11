#!/usr/bin/env python3
"""
Backfill orchestrator: discover game IDs via nba_api, fetch CDN files (PBP + boxscore),
then load PBP into Postgres.

Design goals:
- resumable (skip games already in game_ingestion_state unless --force)
- bounded runtime (fetchers have hard deadlines)
- machine-readable report (JSON Lines)

Note:
- This orchestrator uses the existing fetch/load scripts as subprocesses so behavior stays consistent.
- Boxscore is fetched/archived but not loaded (loader is optional and not implemented in Sprint 04).

Usage:
  python scripts/backfill_seasons.py --from 2023-24 --to 2023-24 --dsn "$DATABASE_URL" --workers 2

  # Or: backfill the previous N seasons before an end season (exclusive by default)
  python scripts/backfill_seasons.py --end-season 2025-26 --seasons-back 10 --exclude 2023-24 --exclude 2024-25 --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psycopg


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill NBA seasons: discover -> fetch -> load.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    # Season selection mode A (explicit range)
    p.add_argument("--from", dest="from_season", default="", help="Start season, e.g. 2018-19")
    p.add_argument("--to", dest="to_season", default="", help="End season, e.g. 2023-24")
    # Season selection mode B (lookback)
    p.add_argument("--end-season", default="", help="End season for lookback selection, e.g. 2025-26")
    p.add_argument("--seasons-back", type=int, default=0, help="Number of seasons before --end-season to include (0 disables).")
    p.add_argument(
        "--include-end-season",
        action="store_true",
        help="If set, include --end-season itself in the lookback selection (default: exclude end season).",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude a season (repeatable), e.g. --exclude 2023-24 --exclude 2024-25",
    )
    p.add_argument("--workers", type=int, default=2, help="Max concurrent game workers.")
    p.add_argument("--force", action="store_true", help="Reprocess games even if already ingested.")
    p.add_argument("--refetch", action="store_true", help="Refetch files even if already present.")
    p.add_argument(
        "--skip-boxscore",
        action="store_true",
        help="Do not fetch boxscore files (PBP load will still run). Useful when older games 403 on the boxscore CDN.",
    )
    p.add_argument(
        "--require-boxscore",
        action="store_true",
        help="If set, fail the game when boxscore fetch fails. Default behavior is best-effort boxscore (warn + continue).",
    )
    p.add_argument("--limit-games", type=int, default=0, help="Limit number of games processed (0 = no limit).")
    p.add_argument("--report-out", default="", help="Write JSONL run report to this path (default: data/reports/backfill_<ts>.jsonl).")
    # discovery tuning
    p.add_argument("--discover-throttle-seconds", type=float, default=0.75)
    p.add_argument("--discover-deadline-seconds", type=float, default=300.0)
    # fetch tuning (bounded)
    p.add_argument("--fetch-timeout-seconds", type=float, default=30.0)
    p.add_argument("--fetch-max-attempts", type=int, default=3)
    p.add_argument("--fetch-deadline-seconds", type=float, default=120.0)
    return p.parse_args()


def parse_season_start_year(season: str) -> int:
    """
    Parse season string like '2018-19' -> 2018.
    """
    s = season.strip()
    if len(s) < 7 or s[4] != "-" or not s[:4].isdigit():
        raise ValueError(f"Invalid season '{season}'. Expected format like 2018-19.")
    return int(s[:4])


def format_season(start_year: int) -> str:
    return f"{start_year}-{str((start_year + 1) % 100).zfill(2)}"


def season_range(start: str, end: str) -> list[str]:
    """
    Supports seasons like '2018-19'. Generates inclusive list.
    """
    a = parse_season_start_year(start)
    b = parse_season_start_year(end)
    if b < a:
        raise ValueError("--to must be >= --from")
    seasons: list[str] = []
    for y in range(a, b + 1):
        seasons.append(format_season(y))
    # sanity: end matches expected format
    if seasons[-1] != end:
        # allow if user passed same-year string; otherwise be strict
        raise ValueError(f"end season '{end}' does not match expected '{seasons[-1]}' from start year math")
    return seasons


def seasons_back_from_end(*, end_season: str, seasons_back: int, include_end: bool) -> list[str]:
    """
    Generate a list of seasons relative to an end season.

    Example:
      end_season=2025-26, seasons_back=10, include_end=False => 2015-16..2024-25 (10 seasons)
      end_season=2025-26, seasons_back=10, include_end=True  => 2016-17..2025-26 (10 seasons)
    """
    if seasons_back <= 0:
        raise ValueError("--seasons-back must be > 0 when using --end-season.")
    end_year = parse_season_start_year(end_season)
    if include_end:
        start_year = end_year - seasons_back + 1
        end_year_inclusive = end_year
    else:
        start_year = end_year - seasons_back
        end_year_inclusive = end_year - 1
    if end_year_inclusive < start_year:
        return []
    return [format_season(y) for y in range(start_year, end_year_inclusive + 1)]


def compute_seasons(args: argparse.Namespace) -> list[str]:
    # Mode A: explicit range
    if args.from_season and args.to_season:
        seasons = season_range(args.from_season, args.to_season)
    # Mode B: lookback
    elif args.end_season and args.seasons_back:
        seasons = seasons_back_from_end(
            end_season=args.end_season,
            seasons_back=args.seasons_back,
            include_end=bool(args.include_end_season),
        )
    else:
        raise SystemExit(
            "Season selection required. Use either (--from SEASON --to SEASON) or (--end-season SEASON --seasons-back N)."
        )

    excludes = {s.strip() for s in (args.exclude or []) if s and s.strip()}
    if excludes:
        seasons = [s for s in seasons if s not in excludes]
    if not seasons:
        raise SystemExit("No seasons selected after applying exclusions.")
    return seasons


def run_cmd(argv: list[str], *, cwd: str, timeout_seconds: float | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return p.returncode, p.stdout, p.stderr


def discover_game_ids(repo_root: str, season: str, throttle: float, deadline: float) -> Path:
    out_dir = Path(repo_root) / "data" / "discovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"game_ids_{season}.csv"
    argv = [
        sys.executable,
        "scripts/discover_game_ids.py",
        "--season",
        season,
        "--out",
        str(out_csv),
        "--throttle-seconds",
        str(throttle),
        "--deadline-seconds",
        str(deadline),
    ]
    code, out, err = run_cmd(argv, cwd=repo_root, timeout_seconds=deadline + 60)
    if code != 0:
        raise RuntimeError(f"discover_game_ids failed for {season}: {err or out}")
    return out_csv


def read_game_ids(csv_path: Path) -> list[str]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids: list[str] = []
    for r in rows:
        gid = (r.get("game_id") or "").strip()
        if gid:
            ids.append(gid)
    # Deterministic
    ids = sorted(set(ids))
    return ids


def already_ingested(conn: psycopg.Connection, game_id: str) -> bool:
    row = conn.execute(
        "SELECT last_success_at, last_seen_action_count FROM game_ingestion_state WHERE game_id=%s",
        (game_id,),
    ).fetchone()
    if not row:
        return False
    last_success_at, last_seen_action_count = row
    return last_success_at is not None and last_seen_action_count is not None


@dataclass
class GameResult:
    game_id: str
    season: str
    status: str  # succeeded/failed/skipped
    step: str
    elapsed_ms: int
    error: str | None = None


def process_one_game(
    *,
    repo_root: str,
    dsn: str,
    season: str,
    game_id: str,
    force: bool,
    refetch: bool,
    skip_boxscore: bool,
    require_boxscore: bool,
    fetch_timeout: float,
    fetch_attempts: int,
    fetch_deadline: float,
) -> GameResult:
    t0 = time.monotonic()
    try:
        with psycopg.connect(dsn) as conn:
            if (not force) and already_ingested(conn, game_id):
                return GameResult(game_id=game_id, season=season, status="skipped", step="check_state", elapsed_ms=int((time.monotonic() - t0) * 1000))

        pbp_out = Path(repo_root) / "data" / "raw" / "pbp" / f"{game_id}.json"
        box_out = Path(repo_root) / "data" / "raw" / "boxscore" / f"{game_id}.json"

        # Fetch PBP
        if refetch or (not pbp_out.exists()) or (not pbp_out.with_suffix(pbp_out.suffix + ".manifest.json").exists()):
            argv = [
                sys.executable,
                "scripts/fetch_pbp.py",
                "--game-id",
                game_id,
                "--out",
                str(pbp_out),
                "--timeout-seconds",
                str(fetch_timeout),
                "--max-attempts",
                str(fetch_attempts),
                "--deadline-seconds",
                str(fetch_deadline),
            ]
            code, out, err = run_cmd(argv, cwd=repo_root, timeout_seconds=fetch_deadline + 30)
            if code != 0:
                raise RuntimeError(f"fetch_pbp failed: {err or out}")

        # Fetch boxscore (archive-only)
        if (not skip_boxscore) and (refetch or (not box_out.exists()) or (not box_out.with_suffix(box_out.suffix + ".manifest.json").exists())):
            argv = [
                sys.executable,
                "scripts/fetch_boxscore.py",
                "--game-id",
                game_id,
                "--out",
                str(box_out),
                "--timeout-seconds",
                str(fetch_timeout),
                "--max-attempts",
                str(fetch_attempts),
                "--deadline-seconds",
                str(fetch_deadline),
            ]
            code, out, err = run_cmd(argv, cwd=repo_root, timeout_seconds=fetch_deadline + 30)
            if code != 0:
                msg = f"fetch_boxscore failed (continuing): {err or out}"
                if require_boxscore:
                    raise RuntimeError(msg.replace("(continuing)", "(required)"))
                print(f"WARN game_id={game_id} season={season} {msg}", flush=True)

        # Load PBP
        argv = [
            sys.executable,
            "scripts/load_pbp.py",
            "--dsn",
            dsn,
            "--pbp-file",
            str(pbp_out),
            "--manifest-file",
            str(pbp_out.with_suffix(pbp_out.suffix + ".manifest.json")),
        ]
        code, out, err = run_cmd(argv, cwd=repo_root, timeout_seconds=300)
        if code != 0:
            raise RuntimeError(f"load_pbp failed: {err or out}")

        return GameResult(game_id=game_id, season=season, status="succeeded", step="load_pbp", elapsed_ms=int((time.monotonic() - t0) * 1000))
    except Exception as e:
        return GameResult(game_id=game_id, season=season, status="failed", step="error", elapsed_ms=int((time.monotonic() - t0) * 1000), error=str(e))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    if not args.dsn:
        raise SystemExit("Missing --dsn and DATABASE_URL is not set.")

    repo_root = str(Path(__file__).resolve().parents[1])
    ts = utc_now_iso()
    report_path = Path(args.report_out) if args.report_out else Path(repo_root) / "data" / "reports" / f"backfill_{ts}.jsonl"

    seasons = compute_seasons(args)

    # Discover all games to process (season-by-season)
    season_to_games: dict[str, list[str]] = {}
    for s in seasons:
        csv_path = discover_game_ids(repo_root, s, args.discover_throttle_seconds, args.discover_deadline_seconds)
        gids = read_game_ids(csv_path)
        season_to_games[s] = gids

    # Flatten into tasks
    tasks: list[tuple[str, str]] = []
    for s in seasons:
        for gid in season_to_games[s]:
            tasks.append((s, gid))
    if args.limit_games and args.limit_games > 0:
        tasks = tasks[: args.limit_games]

    print(f"Processing games: {len(tasks)} across seasons={seasons} workers={args.workers}", flush=True)
    write_jsonl(report_path, [{"type": "start", "ts": ts, "seasons": seasons, "workers": args.workers, "count": len(tasks)}])

    results: list[GameResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [
            ex.submit(
                process_one_game,
                repo_root=repo_root,
                dsn=args.dsn,
                season=s,
                game_id=gid,
                force=args.force,
                refetch=args.refetch,
                skip_boxscore=bool(args.skip_boxscore),
                require_boxscore=bool(args.require_boxscore),
                fetch_timeout=args.fetch_timeout_seconds,
                fetch_attempts=args.fetch_max_attempts,
                fetch_deadline=args.fetch_deadline_seconds,
            )
            for s, gid in tasks
        ]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            write_jsonl(
                report_path,
                [
                    {
                        "type": "game",
                        "season": r.season,
                        "game_id": r.game_id,
                        "status": r.status,
                        "step": r.step,
                        "elapsed_ms": r.elapsed_ms,
                        "error": r.error,
                    }
                ],
            )
            print(
                f"{r.status.upper():9} game_id={r.game_id} season={r.season} elapsed_ms={r.elapsed_ms}"
                + (f" err={r.error}" if r.error else ""),
                flush=True,
            )

    # Summary
    succeeded = sum(1 for r in results if r.status == "succeeded")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    write_jsonl(report_path, [{"type": "summary", "ts": utc_now_iso(), "succeeded": succeeded, "skipped": skipped, "failed": failed}])

    print(f"Done. succeeded={succeeded} skipped={skipped} failed={failed}", flush=True)
    print(f"Report: {report_path}", flush=True)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


