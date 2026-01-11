## Summary of work (NBA raw warehouse + baseline derived timeline)

Last updated: 2025-12-16 (local repo state)

### What this repository now contains (high-level)
- **Bootstrap/dev environment (Sprint 00)**: Dockerized Postgres, `.env` template, pinned Python deps, and onboarding docs.
- **SQL-first Postgres warehouse (Sprint 01)**: migrations under `db/migrations/` + a migration runner `scripts/migrate.py`.
- **Game discovery (Sprint 02)**: season-by-season `game_id` discovery via `nba_api` with archival + manifests.
- **Raw archival fetchers (Sprint 03)**: CDN fetchers for PBP/boxscore/odds/schedule with atomic writes + manifests + retries + total runtime deadline.
- **Loaders (Sprint 04)**:
  - **Implemented**: PBP loader (`scripts/load_pbp.py`) and odds snapshot loader (`scripts/load_odds_snapshot.py`).
  - **Not implemented**: a boxscore loader (boxscore is archived by the backfill, but not loaded).
- **Orchestration + QC (Sprint 05)**: backfill orchestrator + QC reporting and a robust shell wrapper for long runs.
- **Derived baseline dataset (Sprint 07)**: derived time functions + `derived.game_state_by_event` view + a CSV export script.

### Key files (entry points)
- **Docs / onboarding**
  - `README.md` (quickstart)
  - `env.example`
  - `docker-compose.yml` (Postgres 16 on host port **5432**)
  - `scripts/psql.sh` (connect helper)
- **Migrations**
  - `db/migrations/001_schema_v1.sql`
  - `db/migrations/002_optional_raw_payload_tables.sql`
  - `db/migrations/003_odds_games_raw_team_ids.sql`
  - `db/migrations/004_derived_time_functions.sql`
  - `db/migrations/005_derived_game_state_view.sql`
  - `db/migrations/006_fix_parse_clock_seconds_regex.sql`
- **Fetchers / discovery**
  - `scripts/discover_game_ids.py`
  - `scripts/fetch_pbp.py`
  - `scripts/fetch_boxscore.py`
  - `scripts/fetch_odds_today.py`
  - `scripts/fetch_scheduleLeagueV2.py`
  - `scripts/_fetch_lib.py` (retries/backoff, atomic writes, manifest generation, hard deadline)
- **Loaders**
  - `scripts/load_pbp.py`
  - `scripts/load_odds_snapshot.py`
  - `scripts/_db_lib.py` (DSN loading, provenance helpers)
- **Orchestration / QA**
  - `scripts/backfill_seasons.py` (discover → fetch → load)
  - `scripts/run_backfill.sh` (unbuffered logs + PID + DONE marker)
  - `scripts/qc_report.py`
- **Derived export**
  - `scripts/export_game_state.py`

### “Don’t hang” / robustness guarantees that were implemented
- **Hard cap on fetch runtime**: fetchers use `--deadline-seconds` (propagated into `HttpRetry.deadline_seconds`) to bound total time across retries/backoff.
- **Retries with exponential backoff + jitter**: in `scripts/_fetch_lib.py` for transient HTTP/network failures.
- **Atomic writes**: write to `*.tmp` then rename, so partial files aren’t left behind.
- **Sidecar manifests**: `*.manifest.json` with checksum, byte size, fetched time, URL, and key headers (`etag`, `last-modified`).
- **Long-run visibility**: `scripts/run_backfill.sh` runs Python unbuffered, writes a `.pid`, `.log`, `.jsonl` report, and a `.done` file with `exit_code`.

### Data layout on disk (as of current repo state)
Note: `.gitignore` ignores `data/` entirely, so these are local artifacts.
- **Discovered game IDs**: `data/discovery/game_ids_2023-24.csv`, `..._2024-25.csv`, `..._2025-26.csv`
- **Raw archives**:
  - `data/raw/pbp/*.json` (+ manifests)
  - `data/raw/boxscore/*.json` (+ manifests)
  - `data/raw/odds/*.json` (+ manifests)
  - `data/raw/schedule/*.json` (+ manifests)
  - `data/raw/nba_api/leaguegamefinder/...` (+ manifests)
- **Operational artifacts**:
  - `data/reports/backfill_*.jsonl` (+ logs/pid/done markers for some runs)
  - `data/reports/qc_*.json`
- **Exports**:
  - `data/exports/game_state_0022400196.csv`

### Database state checks that were run (facts, not guesses)
These are from running the DB queries against `pbp_events`:
- **`pbp_events` rowcount**: **1,807,777**
- **`pbp_events.time_actual` NULLs**: **0**
- **Earliest `pbp_events.time_actual`**:
  - `game_id=0012300001`, `action_number=2`, `order_number=20000`, `period=1`, `clock=PT12M00.00S`
  - `time_actual=2023-10-05 16:09:33.1+00`
- **Latest `pbp_events.time_actual`**:
  - `game_id=0022501230`, `action_number=823`, `order_number=7950000`, `period=4`, `clock=PT00M00.00S`
  - `time_actual=2025-12-14 05:01:17.3+00`

### Timestamp semantics (clarified and enforced in usage)
- **`pbp_events.time_actual`**: “real-world event time” from the PBP feed (what you ultimately wanted for “first/last record”).
- **`ingestion_runs.started_at/finished_at`**: operational timestamps (“when we loaded it”), not game/event time.
- **`games.game_time_utc`**: game-level time (when the game took place), not per-event time.

### Bugs/errors encountered and fixes applied (in repo history reflected by current code)
- **Loader crash on sparse text fields**: `subType` can be `""`; loader now treats optional text fields safely.
- **Migration transaction nesting / savepoint error**: fixed by removing `BEGIN/COMMIT` wrappers from SQL migrations so `scripts/migrate.py` owns transactions.
- **zsh healthcheck script issue**: avoided using `status` as a variable name in shell (readonly in zsh).
- **`.env` export propagation**: `scripts/run_backfill.sh` uses `set -a; source .env; set +a` when `DATABASE_URL` isn’t exported.
- **`python` not found**: wrapper chooses venv python or falls back to `python3`.
- **Deadlocks in concurrent loads**: `scripts/load_pbp.py` retries on `DeadlockDetected` / `SerializationFailure`.
- **Derived clock parsing bug**: fixed via `db/migrations/006_fix_parse_clock_seconds_regex.sql`.
- **Querying wrong game date column**: `games` uses `game_time_utc` (not `game_date`).

### What’s still “not done” / optional gaps (honest)
- **Boxscore loading**: boxscores are archived, but there is no implemented loader that writes them into the DB (the orchestrator explicitly notes this).
- **Schedule snapshot loading**: schedule is fetched/archived; loader is not clearly part of the pipeline yet.
- **Odds backfill beyond “today snapshots”**: odds endpoint is “today-only” (by design); historical odds are not currently solvable from that CDN alone.
- **Materialized view**: derived dataset is implemented as a regular view; an MV + refresh strategy is optional.

### Security note (repo hygiene)
The repo root currently contains `kalshi-api-key-private.txt` and `kalshi-api-key-public.txt`. If these are real credentials, they should be **removed/rotated** and added to `.gitignore` (or moved to a secure secret manager).


### Addendum (2025-12-16): Derived `pbp_event_state` table, possession-side, and winner signals (this chat)
This section documents work completed **after** the original baseline derived timeline was in place. It is intentionally appended (not integrated into earlier sections).

#### What was added/changed
- **Derived per-event modeling table**: `derived.pbp_event_state` is a **table** (not a view) materialized from `derived.game_state_by_event`.
- **Possession representation (final form)**:
  - `possession_side` is **0=home, 1=away, NULL=unknown**.
  - `point_differential` remains **home - away** (positive = home leading).
- **Per-event score + winner signals**:
  - `home_score`, `away_score` added to `derived.pbp_event_state` (scoreboard at that event).
  - `current_winning_team` is **0=home leading, 1=away leading, NULL=tied/unknown** (per event).
  - `final_winning_team` is **0=home won, 1=away won, NULL=tied/unknown** and is constant per `game_id`.
- **Game-level final result fields**:
  - `games.final_score_home`, `games.final_score_away`, `games.winner_team_id` added and backfilled from PBP.

#### New/updated migrations
- `db/migrations/007_derived_pbp_event_state_table.sql`: create initial `derived.pbp_event_state` table.
- `db/migrations/008_derived_game_state_add_possession_columns.sql`: append `possession_team_id` into `derived.game_state_by_event` (important: appended to avoid Postgres `CREATE OR REPLACE VIEW` column-renaming errors).
- `db/migrations/009_derived_pbp_event_state_add_possession_columns.sql`: add possession column(s) to `derived.pbp_event_state` (eventually simplified per user intent).
- `db/migrations/010_team_only_possession_columns.sql`: remove unwanted possession columns (person/team) as requirements narrowed.
- `db/migrations/011_drop_team_id_from_derived_pbp_event_state.sql`: cleanup for an inadvertently-present `team_id` column.
- `db/migrations/013_drop_point_differential_possession.sql`: remove an over-derived, unwanted column.
- `db/migrations/014_pbp_event_state_possession_side_0_home_1_away.sql`: finalize possession representation as `possession_side` and drop prior possession columns.
- `db/migrations/015_games_add_final_score_and_winner.sql`: add final score + winner columns to `games`.
- `db/migrations/016_derived_pbp_event_state_add_scores_and_winning_team.sql`: add event-level scores + initial winner field.
- `db/migrations/017_derived_pbp_event_state_rename_winning_team_add_game_winner.sql`: rename `winning_team` → `current_winning_team`, add constant-per-game winner column.
- `db/migrations/018_derived_pbp_event_state_rename_game_winner_to_final.sql`: rename `game_winning_team` → `final_winning_team`.

#### New/updated scripts
- **Materialization (derived table refresh)**:
  - `scripts/materialize_pbp_event_state.py`
    - Inserts per-event `point_differential`, `time_remaining`, `possession_side`, `home_score`, `away_score`,
      `current_winning_team`, `final_winning_team`.
    - Note: requires `games.home_team_id/away_team_id` to compute `possession_side`.
- **Export**:
  - `scripts/export_pbp_event_state.py` exports CSV with the full current column set.
- **Backfills for `games.home_team_id/away_team_id`**:
  - `scripts/backfill_games_from_boxscore_archive.py`: offline backfill from archived boxscore JSON files.
  - `scripts/backfill_games_from_scheduleleaguev2.py`: online backfill via `nba_api.stats.endpoints.scheduleleaguev2`.
    - Fix: skip placeholder schedule rows where `teamId=0` / missing tricode to avoid `teams.team_tricode NOT NULL` violations.
- **Backfill game result fields from PBP**:
  - `scripts/backfill_games_final_result_from_pbp.py`: sets `games.final_score_home/away` and `games.winner_team_id` from the last `pbp_events` row per game (optionally `--force`).

#### Errors encountered (and what they meant)
- **Postgres view replace error (`cannot change name of view column ...`)**:
  - Cause: `CREATE OR REPLACE VIEW` cannot reorder existing columns; it interprets reordering as renaming.
  - Fix: only **append** new columns to `derived.game_state_by_event`.
- **`psycopg.errors.AmbiguousColumn` in materializer**:
  - Fix: fully qualify columns (e.g., `s.game_id`) when joining.
- **`possession_side` always NULL**:
  - Root cause: `games.home_team_id/away_team_id` were missing; materializer compares `possession_team_id` against those.
  - Fix: backfill home/away team ids via boxscore archive and/or `ScheduleLeagueV2`.
- **Current-season schedule backfill error (`team_tricode` NOT NULL)**:
  - Root cause: schedule endpoint returns some placeholder rows with `teamId=0` and missing tricodes.
  - Fix: skip invalid team ids / avoid inserting incomplete team rows.

#### Operational note (important)
- `derived.pbp_event_state` does **not** update automatically when upstream tables change; you must rerun:
  - `scripts/materialize_pbp_event_state.py --game-id ...` or `--all`
  after updating `games` or ingesting new PBP.

