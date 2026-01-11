#!/usr/bin/env python3
"""
Backfill ESPN NBA game probabilities (ESPN core API) across many seasons.

This is a thin orchestrator that runs `scripts/backfill_espn_probabilities_season.py` season-by-season,
using a broad default date window so it also covers atypical seasons (e.g. 2019-20 / 2020-21 timing).

Default window:
  start = Sep 01 of season start year
  end   = Aug 31 of season end year

Typical usage (2015-16..2025-26 inclusive):
  python scripts/backfill_espn_probabilities_range.py --from 2015-16 --to 2025-26

Faster, narrower window (if you only care about typical Oct->Jun games):
  python scripts/backfill_espn_probabilities_range.py --from 2015-16 --to 2025-26 --start-mmdd 1001 --end-mmdd 0630

Resumability:
  - This is safe to re-run; it will skip games where both the JSON file and its `.manifest.json` exist
    (unless you pass --overwrite).

Outputs:
  - Scoreboards (shared across seasons): data/raw/espn/scoreboard/scoreboard_YYYYMMDD.json (+ manifest)
  - Probabilities (season-specific):     data/raw/espn/probabilities/<season>/event_<event>_comp_<comp>.json (+ manifest)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path


def parse_season_start_year(season: str) -> int:
    s = season.strip()
    if len(s) < 7 or s[4] != "-" or not s[:4].isdigit():
        raise ValueError(f"Invalid season '{season}'. Expected format like 2018-19.")
    return int(s[:4])


def format_season(start_year: int) -> str:
    return f"{start_year}-{str((start_year + 1) % 100).zfill(2)}"


def season_range(start: str, end: str) -> list[str]:
    a = parse_season_start_year(start)
    b = parse_season_start_year(end)
    if b < a:
        raise ValueError("--to must be >= --from")
    seasons: list[str] = [format_season(y) for y in range(a, b + 1)]
    if seasons[-1] != end:
        raise ValueError(f"end season '{end}' does not match expected '{seasons[-1]}' from start year math")
    return seasons


def seasons_back_from_end(*, end_season: str, seasons_back: int, include_end: bool) -> list[str]:
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
    if args.from_season and args.to_season:
        seasons = season_range(args.from_season, args.to_season)
    elif args.end_season and args.seasons_back:
        seasons = seasons_back_from_end(
            end_season=args.end_season,
            seasons_back=int(args.seasons_back),
            include_end=bool(args.include_end_season),
        )
    else:
        raise SystemExit("Season selection required. Use either (--from SEASON --to SEASON) or (--end-season SEASON --seasons-back N).")

    excludes = {s.strip() for s in (args.exclude or []) if s and s.strip()}
    if excludes:
        seasons = [s for s in seasons if s not in excludes]
    if not seasons:
        raise SystemExit("No seasons selected after applying exclusions.")
    return seasons


def _parse_mmdd(s: str) -> str:
    t = str(s).strip()
    if len(t) != 4 or (not t.isdigit()):
        raise ValueError("Expected MMDD like 0901 or 0630")
    mm = int(t[:2])
    dd = int(t[2:])
    if mm < 1 or mm > 12:
        raise ValueError("Invalid month in MMDD")
    if dd < 1 or dd > 31:
        raise ValueError("Invalid day in MMDD")
    return t


@dataclass(frozen=True)
class SeasonWindow:
    season: str
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD


def season_window(season: str, *, start_mmdd: str, end_mmdd: str) -> SeasonWindow:
    y = parse_season_start_year(season)
    start_date = f"{y}{start_mmdd}"
    end_date = f"{y + 1}{end_mmdd}"
    return SeasonWindow(season=season, start_date=start_date, end_date=end_date)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill ESPN probabilities across seasons (local JSON archive).")
    # Season selection mode A (explicit range)
    p.add_argument("--from", dest="from_season", default="", help="Start season, e.g. 2015-16")
    p.add_argument("--to", dest="to_season", default="", help="End season, e.g. 2025-26")
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

    p.add_argument("--start-mmdd", default="0901", help="Season window start MMDD (default: 0901).")
    p.add_argument("--end-mmdd", default="0831", help="Season window end MMDD (default: 0831).")

    p.add_argument("--out-root", default="data/raw/espn", help="Root output directory (default: data/raw/espn)")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON files (and manifests).")
    p.add_argument("--workers", type=int, default=12, help="Max concurrent probabilities fetch workers (per season).")
    p.add_argument("--requests-per-second", type=float, default=8.0, help="Global max request rate (per season). Set 0 to disable.")
    p.add_argument("--throttle-seconds", type=float, default=0.2, help="Sleep between HTTP requests (best-effort).")
    p.add_argument("--heartbeat-seconds", type=float, default=15.0, help="Print a progress heartbeat at least this often. Set 0 to disable.")
    p.add_argument("--progress-every", type=int, default=100, help="Print progress every N processed games. 0 disables.")
    p.add_argument("--max-games", type=int, default=0, help="If > 0, limit per-season probabilities writes (debug/smoke test).")
    p.add_argument("--stop-on-error", action="store_true", help="Abort the run on the first probabilities fetch error.")
    p.add_argument("--verbose", action="store_true")

    # Completeness checking (recommended)
    p.add_argument(
        "--run-completeness-check",
        action="store_true",
        help="After each season backfill, run the completeness checker and print a season report (recommended).",
    )
    p.add_argument(
        "--stop-if-incomplete",
        action="store_true",
        help="If set and the completeness checker reports incomplete, stop the overall run with non-zero exit.",
    )
    p.add_argument(
        "--check-show-missing",
        type=int,
        default=25,
        help="When running completeness check, print up to N missing games. 0 disables.",
    )
    p.add_argument(
        "--error-log-template",
        default="data/reports/espn_probabilities_backfill_errors_{season}.jsonl",
        help="Error JSONL path template passed to season backfill (supports {season}).",
    )
    p.add_argument(
        "--check-report-template",
        default="data/reports/espn_probabilities_completeness_{season}.json",
        help="Completeness JSON report output template (supports {season}).",
    )

    # Optional DB load (run only after ALL seasons complete)
    p.add_argument(
        "--load-to-db-after",
        action="store_true",
        help="After all seasons are complete, run migrations and load probabilities items[] into Postgres.",
    )
    p.add_argument(
        "--dsn",
        default="",
        help="Postgres DSN for --load-to-db-after (default: DATABASE_URL env var, via child scripts).",
    )
    return p.parse_args()


def run_one_season(repo_root: Path, sw: SeasonWindow, args: argparse.Namespace) -> int:
    error_log = str(args.error_log_template).format(season=sw.season)
    argv = [
        sys.executable,
        "scripts/backfill_espn_probabilities_season.py",
        "--season-label",
        sw.season,
        "--start-date",
        sw.start_date,
        "--end-date",
        sw.end_date,
        "--out-root",
        str(args.out_root),
        "--workers",
        str(int(args.workers)),
        "--requests-per-second",
        str(float(args.requests_per_second)),
        "--throttle-seconds",
        str(float(args.throttle_seconds)),
        "--heartbeat-seconds",
        str(float(args.heartbeat_seconds)),
        "--progress-every",
        str(int(args.progress_every)),
        "--error-log",
        error_log,
    ]
    if args.overwrite:
        argv.append("--overwrite")
    if args.max_games and int(args.max_games) > 0:
        argv.extend(["--max-games", str(int(args.max_games))])
    if args.stop_on_error:
        argv.append("--stop-on-error")
    if args.verbose:
        argv.append("--verbose")

    p = subprocess.run(argv, cwd=str(repo_root), text=True)
    return int(p.returncode)


def run_completeness_check(repo_root: Path, sw: SeasonWindow, args: argparse.Namespace) -> int:
    error_log = str(args.error_log_template).format(season=sw.season)
    report_out = str(args.check_report_template).format(season=sw.season)
    argv = [
        sys.executable,
        "scripts/check_espn_probabilities_completeness.py",
        "--season-label",
        sw.season,
        "--start-date",
        sw.start_date,
        "--end-date",
        sw.end_date,
        "--out-root",
        str(args.out_root),
        "--error-log",
        error_log,
        "--show-missing",
        str(int(args.check_show_missing)),
        "--out",
        report_out,
    ]
    p = subprocess.run(argv, cwd=str(repo_root), text=True)
    return int(p.returncode)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_db_load(repo_root: Path, args: argparse.Namespace) -> int:
    """
    After backfill+checks succeed, migrate and load raw probability items[] into Postgres.
    This uses existing migrations + loader script:
      - db/migrations/022_derived_espn_probabilities_raw_items_table.sql
      - scripts/load_espn_probabilities_raw_items.py
    """
    ts = _utc_now_iso()
    print(f"[espn_range] db_load start ts={ts}", flush=True)

    env = dict(os.environ)
    if args.dsn:
        env["DATABASE_URL"] = str(args.dsn).strip()
    dsn = str(env.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("[espn_range] db_load FAILED: missing DATABASE_URL (pass --dsn or set env DATABASE_URL)", flush=True)
        return 2

    mig = subprocess.run(
        [sys.executable, "scripts/migrate.py", "--dsn", dsn],
        cwd=str(repo_root),
        text=True,
        env=env,
    )
    if int(mig.returncode) != 0:
        print(f"[espn_range] db_load FAILED migrate exit_code={mig.returncode}", flush=True)
        return int(mig.returncode)

    load = subprocess.run(
        [sys.executable, "scripts/load_espn_probabilities_raw_items.py", "--dsn", dsn],
        cwd=str(repo_root),
        text=True,
        env=env,
    )
    if int(load.returncode) != 0:
        print(f"[espn_range] db_load FAILED loader exit_code={load.returncode}", flush=True)
        return int(load.returncode)

    print(f"[espn_range] db_load done ts={ts}", flush=True)
    return 0


def main() -> int:
    args = parse_args()
    start_mmdd = _parse_mmdd(args.start_mmdd)
    end_mmdd = _parse_mmdd(args.end_mmdd)
    seasons = compute_seasons(args)

    repo_root = Path(__file__).resolve().parents[1]
    windows = [season_window(s, start_mmdd=start_mmdd, end_mmdd=end_mmdd) for s in seasons]

    print(f"[espn_range] seasons={seasons} out_root={args.out_root} start_mmdd={start_mmdd} end_mmdd={end_mmdd}", flush=True)
    for sw in windows:
        print(f"[espn_range] season={sw.season} window={sw.start_date}..{sw.end_date}", flush=True)
        print(
            f"[espn_range] season={sw.season} error_log={str(args.error_log_template).format(season=sw.season)}",
            flush=True,
        )
        code = run_one_season(repo_root, sw, args)
        if code != 0:
            print(f"[espn_range] FAILED season={sw.season} exit_code={code}", flush=True)
            return code

        if args.run_completeness_check:
            check_code = run_completeness_check(repo_root, sw, args)
            complete = (check_code == 0)
            print(
                f"[espn_range] season={sw.season} completeness_exit_code={check_code} COMPLETE={str(complete).lower()} "
                f"report={str(args.check_report_template).format(season=sw.season)}",
                flush=True,
            )
            if (not complete) and args.stop_if_incomplete:
                print(f"[espn_range] STOPPING due to incomplete season={sw.season}", flush=True)
                return check_code

    print("[espn_range] done", flush=True)

    if args.load_to_db_after:
        db_code = run_db_load(repo_root, args)
        if db_code != 0:
            return db_code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


