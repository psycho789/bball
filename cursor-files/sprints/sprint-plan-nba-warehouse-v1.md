## Sprint Plan — NBA Raw Data Warehouse v1 (PostgreSQL)

This sprint plan is derived from **validated data sources** documented in:
- `cursor-files/analysis/nba_data_sources_analysis_v2.md`

### Scope
- **In scope**: historical game discovery, raw file archival, ingestion into PostgreSQL, and odds snapshot ingestion, with strong provenance and idempotency.
- **Not in scope**: feature engineering, modeling/ML, betting execution, or downstream analytics marts.

### Verified endpoints (must use these exact forms)
- **PBP**: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json`
- **Boxscore**: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`
- **Today’s NBA scoreboard**: `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json` (today only)
- **Schedule (current season as served)**: `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`
- **Odds (today only)**: `https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json`

#### Endpoint validation rules (so fetchers don’t “false fail”)
These endpoints are not uniform in their `meta` block:
- **PBP + boxscore**: include `meta.code`; treat `meta.code == 200` as a required success indicator.
- **Scoreboard**: includes `meta.code`; treat `meta.code == 200` as required.
- **ScheduleLeagueV2**: has `meta` but does **not** include `meta.code` in the observed payload; validate by JSON parse + presence of `leagueSchedule.gameDates`.
- **Odds todaysGames**: observed payload has **no `meta`**; validate by JSON parse + presence of top-level `games`.

### Data-source strategy (high level)
- **Historical game IDs**: use `nba_api` (`stats.nba.com`) to enumerate `gameId`s season-by-season.
- **Raw game data**: fetch **PBP + boxscore** from the NBA CDN using `gameId`.
- **Odds**: ingest as a **time-stamped snapshot** feed from the CDN odds endpoint.

### Design patterns & algorithms (so the implementation is deterministic) [[memory:8239723]]
- **Pattern**: *Hub-and-spoke* warehouse (fact tables for event streams/snapshots + dimensions + provenance/run tracking).
- **Algorithm**: *Upsert/merge* (`INSERT ... ON CONFLICT DO UPDATE`) for idempotency.
- **Ordering**: event replay order is `ORDER BY (game_id, order_number)`.
- **Complexity**:
  - Game discovery per season: \(O(R)\) where \(R\) is rows returned (team-game rows; ~2× unique games).
  - Per game ingest: \(O(A + Q + F)\) where \(A\)=actions, \(Q\)=qualifiers, \(F\)=personIdsFilter rows.
  - Odds snapshot ingest: \(O(G + M + B + O)\) where \(G\)=games, \(M\)=markets, \(B\)=books, \(O\)=outcomes.

---

## Sprint 00 — Repository bootstrap (1–2 days)

### Story 0.1 — Standardize runtime + dependencies

#### What to build
- `.venv/` local workflow (Python), with pinned dependencies:
  - `requirements.txt` or `pyproject.toml` (uv/poetry ok)
  - include `nba_api` for game discovery
- `docker-compose.yml` for a local Postgres instance (pin a major version, e.g. 16)
- `.env.example` with `DATABASE_URL=...`

#### Pros / cons [[memory:8239723]]
- **Pros**: reproducible onboarding; deterministic backfills; fewer environment bugs.
- **Cons**: Docker requirement; some orgs prefer managed DB even for dev.

#### Acceptance criteria
- **AC1**: On a fresh clone, an engineer can run a documented command sequence to:
  - start Postgres
  - create venv
  - install deps
  - connect to DB
- **AC2**: `nba_api` is importable inside the venv and can run a basic endpoint call in a smoke test.

---

## Sprint 01 — Database schema v1 + provenance (2–4 days)

### Story 1.1 — Migrations framework (SQL-first)

#### What to build
- `db/migrations/` ordered SQL migrations
- `scripts/migrate.py` migration runner
- `schema_migrations` table

#### Acceptance criteria
- **AC1**: Migrations apply in lexicographic order; recorded in `schema_migrations`.
- **AC2**: Re-running migrations is a no-op and succeeds.

### Story 1.2 — Create Schema v1 (core + operational tables)

#### What to build
Create production-grade tables that support:
- strict event ordering/uniqueness,
- raw payload archival linkage,
- run-level auditing and replayability.

#### Tables (required)
**Core domain**
- `teams`
- `players`
- `games`
- `officials` (optional but recommended)

**Raw archive + runs**
- `source_files`
- `ingestion_runs`
- `game_ingestion_state`

**PBP**
- `pbp_events`
- `pbp_event_qualifiers`
- `pbp_event_people_filter`

**Odds (snapshots)**
- `odds_snapshots`
- `odds_games`
- `odds_markets`
- `odds_books`
- `odds_outcomes`

**Raw JSON retention (future-proofing)**
- `pbp_events.raw_action JSONB NOT NULL` (per-event raw object, not just per-file)
- `odds_snapshots.raw_snapshot JSONB NOT NULL` (entire odds file payload)
- Strongly recommended:
  - `game_boxscores (game_id, source_file_id, raw_boxscore JSONB NOT NULL)` to preserve the full boxscore payload even if you don’t normalize it yet.
  - `schedule_snapshots (snapshot_id, source_file_id, raw_schedule JSONB NOT NULL)` if you plan to archive scheduleLeagueV2 over time.

#### Critical keys / constraints
**PBP correctness**
- `UNIQUE (game_id, order_number)` on `pbp_events`
- `UNIQUE (game_id, action_number)` on `pbp_events`

**Provenance**
- `pbp_events.source_file_id` NOT NULL → `source_files`
- `pbp_events.last_ingest_run_id` NOT NULL → `ingestion_runs`

**Odds time series**
- `odds_snapshots.snapshot_id` as the anchor key
- Uniqueness should be scoped to snapshot:
  - e.g. `odds_games`: `UNIQUE (snapshot_id, game_id)`
  - `odds_outcomes`: `UNIQUE (snapshot_id, game_id, market_key, book_id, outcome_type, odds_field_id)`

**Define `market_key` (required)**
The odds payload does not provide a single stable market primary key at the market level. Define a deterministic key:
- `market_key = concat_ws(':', odds_type_id, group_name, name)`

This is stable across books within the snapshot and avoids relying on array ordering.

**Odds datatypes (must be explicit)**
Odds values arrive as strings (e.g. `"1.360"`). Store:
- `odds` NUMERIC(18,6) NULL
- `opening_odds` NUMERIC(18,6) NULL
- and optionally keep the raw strings as `odds_raw TEXT`, `opening_odds_raw TEXT` for exact replay/debugging.

#### Sentinel vs NULL decision (must pick and encode)
PBP contains `personId=0` and `possession=0` on administrative events.
- Option A: store NULL in FKs
- Option B: sentinel rows (`players.person_id=0`, `teams.team_id=0`)

#### Pros / cons [[memory:8239723]]
- **Pros**: integrity enforcement + auditability + forward compatibility (store raw JSONB).
- **Cons**: more upfront DDL; slightly heavier ingestion (run tracking + source registration).

#### Acceptance criteria
- **AC1**: All tables created with correct PKs/FKs, check constraints, and indexes.
- **AC2**: Attempted duplicate insert into `pbp_events` with same `(game_id, order_number)` fails.
- **AC3**: Attempted duplicate insert into `pbp_events` with same `(game_id, action_number)` fails.
- **AC4**: Every ingested `pbp_events` row must have non-null `source_file_id` and `last_ingest_run_id`.
- **AC5**: Odds uniqueness constraints prevent duplicate outcomes within a snapshot.
- **AC6**: Schema includes raw JSONB retention columns (`pbp_events.raw_action`, `odds_snapshots.raw_snapshot`) and they are populated by loaders.

---

## Sprint 02 — Game discovery (historical) via `nba_api` (2–5 days)

### Story 2.1 — Implement `nba_api` gameId discovery script (season-by-season)

#### What to build
Script that outputs a deterministic list of NBA game IDs for a season:
- `scripts/discover_game_ids.py --season 2023-24 --out data/discovery/game_ids_2023-24.csv`

Output should include at minimum:
- `game_id`
- `game_date` (if available)
- `season`
- optional: matchup/team IDs

#### Implementation details
- Use `nba_api.stats.endpoints.LeagueGameFinder` for `league_id='00'`.
- Deduplicate from team-game rows into unique `game_id`s.
- Record the raw `nba_api` response to `data/raw/nba_api/...` (archive-first).

**Important correctness note**
`LeagueGameFinder` returns rows at the team-game level (roughly 2× per game). The script must:
- deduplicate by `GAME_ID`
- output one row per unique game_id (with deterministic sort)

**Library pinning (required)**
Pin `nba_api` in dependencies to a known working version (we validated `nba_api==1.10.2` in this workspace).

#### Rate limiting defaults (must be built-in)
Because `stats.nba.com` is not a stable “public API,” implement:
- per-worker throttle (start at ~1 req/sec)
- exponential backoff with jitter for 403/429/5xx
- low concurrency by default (configurable)

#### Pros / cons [[memory:8239723]]
- **Pros**: reliable historical enumeration; avoids “today-only scoreboard” limitation.
- **Cons**: may be throttled/blocked; requires conservative request strategy and good retry logic.

#### Acceptance criteria
- **AC1**: For a known season (e.g. `2023-24`), script outputs a non-empty list of unique `game_id`s.
- **AC2**: Output is stable across reruns (same inputs → same sorted outputs).
- **AC3**: Script archives raw response(s) to disk and writes a small manifest including `sha256_hex`, `byte_size`, and `fetched_at`.
- **AC4**: On transient HTTP failures, script retries with backoff; on persistent failures, it exits with a clear error message.

---

## Sprint 03 — Raw archival fetchers (CDN) for PBP + boxscore + odds (3–6 days)

### Story 3.1 — CDN fetcher: PBP

#### What to build
- `scripts/fetch_pbp.py --game-id 0022400196 --out data/raw/pbp/0022400196.json`

Requirements:
- timeouts + retries
- atomic writes (`.tmp` then rename)
- record HTTP headers you can capture (etag/last-modified if present)
- compute SHA-256 and write a sidecar manifest (so loaders can register the file in `source_files`)

**Decouple network from DB writes (recommended)**
Fetchers should not require DB connectivity. Treat fetchers as “pure archival”:
- Inputs: IDs + output paths
- Outputs: JSON file + manifest (sha256, size, fetched_at, headers)

Pros / cons [[memory:8239723]]
- **Pros**: simpler ops; you can re-run loads from archived files without re-fetching; fewer partial DB states.
- **Cons**: requires a loader step to register source_files/run tracking.

#### Acceptance criteria
- **AC1**: Given a valid game_id, fetcher produces JSON with `game.actions[]`.
- **AC2**: Fetcher never leaves partial files on disk.
- **AC3**: Fetcher writes a manifest containing checksum + size + fetched_at (sufficient for later `source_files` registration).

### Story 3.2 — CDN fetcher: boxscore
- `scripts/fetch_boxscore.py --game-id ... --out data/raw/boxscore/{game_id}.json`

Acceptance criteria mirrors PBP fetcher.

### Story 3.3 — CDN fetcher: odds snapshot (today)
- `scripts/fetch_odds_today.py --out data/raw/odds/odds_todaysGames_{fetched_at_iso}.json`

Requirements:
- fetch the odds feed
- archive as a timestamped snapshot (do not overwrite)
- write a manifest with checksum/size/fetched_at (for later `source_files` registration)

Acceptance criteria
- **AC1**: Each run writes a new file (timestamped) and writes its manifest.
- **AC2**: JSON parses and contains `games[]`.

### Story 3.4 — Optional: schedule snapshot (current season)
- `scripts/fetch_scheduleLeagueV2.py --out data/raw/schedule/scheduleLeagueV2_{fetched_at_iso}.json`

Acceptance criteria:
- **AC1**: JSON parses and contains `leagueSchedule.gameDates[]`.

---

## Sprint 04 — Loaders: PBP + odds into PostgreSQL (4–8 days)

### Story 4.1 — Loader: PBP JSON → relational tables (idempotent)

#### What to build
- `scripts/load_pbp.py --game-id ... --pbp-file ... --dsn ...`

Mapping must include (minimum):
- `pbp_events` typed columns (ordering/time/type/score/actor/team)
- `raw_action` JSONB (full action object)
- qualifiers into `pbp_event_qualifiers`
- `personIdsFilter` into `pbp_event_people_filter`

Run tracking requirements:
- create `ingestion_runs` row at start
- register the input file in `source_files` (using its manifest/checksum) and link to `source_file_id`
- update `game_ingestion_state` on success

#### Pros / cons [[memory:8239723]]
- **Pros**: deterministic replay; indexed columns for query performance; raw JSON retained for evolution.
- **Cons**: requires careful conflict targets and child-table reconciliation.

#### Acceptance criteria
- **AC1**: Loading the same PBP file twice yields identical row counts and no duplicates.
- **AC2**: `ORDER BY order_number` reproduces the source sequence.
- **AC3**: Child tables match the JSON exactly after load (no missing/extra qualifiers or people_filter rows).
- **AC4**: All loaded `pbp_events` rows link to correct `source_file_id` and `last_ingest_run_id`.

### Story 4.2 — Loader: boxscore JSON (optional v1 but recommended)
If you decide to ingest boxscore now:
- either store it raw (`game_boxscores` table with JSONB + provenance),
- or normalize key dimensions (players/teams/game metadata).

Acceptance criteria
- **AC1**: Stored boxscore can be linked to `game_id` and `source_file_id`.

### Story 4.3 — Loader: odds snapshot JSON → relational snapshot tables

#### What to build
- `scripts/load_odds_snapshot.py --odds-file ... --dsn ...`

Rules:
- One `odds_snapshots` row per file (with fetched_at from filename or file mtime)
- Load `games → markets → books → outcomes`
- Preserve raw snapshot JSONB (`odds_snapshots.raw_snapshot`) for forward compatibility

**Mapping accuracy note**
The odds payload observed is nested as:
`games[] → markets[] → books[] → outcomes[]`
and does not include a top-level `meta` block. Validate presence of `games` and expected keys during load.

Acceptance criteria
- **AC1**: Loading the same odds file twice is idempotent (no duplicates under that snapshot_id).
- **AC2**: Snapshot ingestion preserves multiple books per market and multiple outcomes per book.
- **AC3**: All odds rows are scoped to the correct `snapshot_id`.

---

## Sprint 05 — Backfill orchestration + QA (5–10 days)

### Story 5.1 — Backfill orchestrator (season range → full ingest)

#### What to build
- `scripts/backfill_seasons.py --from 2018-19 --to 2023-24 --workers 2 --dsn ...`

Pipeline:
1) discover game IDs (nba_api)
2) for each game: fetch PBP + boxscore (CDN)
3) load PBP (+ optionally boxscore)

#### Pros / cons [[memory:8239723]]
- **Pros**: repeatable; supports partial retries; can resume using `game_ingestion_state`.
- **Cons**: long-running; must handle rate limits and partial failures carefully.

#### Acceptance criteria
- **AC1**: Orchestrator can resume after interruption without redoing successful games.
- **AC2**: Produces a machine-readable run report (counts, failures, retry attempts).
- **AC3**: Enforces a configurable max request rate and max concurrency.

### Story 5.2 — Data quality checks (warehouse-level)

Implement a `scripts/qc_report.py` that checks:
- PBP events uniqueness constraints hold
- per-game event count equals source `len(actions)`
- monotonic `order_number` within game
- basic referential integrity (teams/players existence or sentinel/NULL policy compliance)

Acceptance criteria
- **AC1**: QC fails the build/run if any uniqueness/order invariants are violated.
- **AC2**: QC report is stored and linked to `ingestion_runs` (as metadata or file reference).

---

## Sprint 06 — Operations hardening (ongoing)

### Story 6.1 — Logging + metrics
- structured logs with run_id, game_id, source_file_id
- counters for requests, retries, failures, throughput

### Story 6.2 — Scheduling (cron)
- daily odds snapshot fetch+load
- daily “new games” discovery (current season) and ingest

### Acceptance criteria
- **AC1**: Operators can answer “what happened last run?” from `ingestion_runs`.
- **AC2**: Operators can reprocess a specific game by `game_id` deterministically.


