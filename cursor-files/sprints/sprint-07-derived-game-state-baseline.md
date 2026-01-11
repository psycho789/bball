## Sprint 07 — Derived game state timeline (baseline: score differential + time remaining)

### Goal
Produce a **reproducible, queryable** “game state over time” dataset for baseline win-prob modeling:
- **score differential** (home/away and/or perspective-adjusted)
- **seconds remaining in game**

This sprint intentionally builds this dataset as a **derived view/materialized view** on top of the raw PBP warehouse, not as a new “raw ingestion source.”

### Why this matters
This baseline is:
- strong enough to be useful immediately,
- simple to validate (monotonic time, correct score progression),
- and a stable foundation for later modeling improvements.

---

## Decision: same repo vs separate app?

### Recommendation: keep it in the **same repo**, but as a separate “derived” module and DB schema
**Pattern**: “one repo, two subsystems” (raw ingestion + derived datasets).

#### Pros / cons [[memory:8239723]]
- **Same repo (recommended now)**
  - Pros: reuses DB connection/migrations/run tracking; easier end-to-end testing; fewer deployment surfaces.
  - Cons: repo grows; need discipline to keep `raw` vs `derived` boundaries clean.
- **Separate app/service**
  - Pros: independent deploy cadence; clearer separation of concerns at org scale.
  - Cons: duplicated infra (config, CI, secrets); more overhead before you’ve proven requirements.

**Rule of thumb**: keep it together until you have multiple independent derived pipelines with different owners/SLOs.

---

## Deliverable definition (what “derived game state timeline” means)

### Output dataset (minimum columns)
One row per `(game_id, order_number)` in `pbp_events`:
- **Identity**
  - `game_id` (TEXT)
  - `order_number` (INT)
  - `event_id` (BIGINT) optional passthrough
- **Time**
  - `period` (SMALLINT)
  - `period_type` (TEXT)
  - `clock` (TEXT, raw)
  - `seconds_remaining_period` (INT)
  - `seconds_elapsed_game` (INT)
  - `seconds_remaining_game` (INT)
- **Score**
  - `score_home` (INT)
  - `score_away` (INT)
  - `score_diff_home` (INT) = `score_home - score_away`

### Output dataset (recommended additional columns)
These are not required for the baseline model but improve usability:
- `is_overtime` (BOOL)
- `is_game_end` (BOOL) derived from last period end / final event marker (optional)
- `home_team_id`, `away_team_id` (from `games` table when available)
- `possession_team_id` (already in PBP; optional for later)

---

## Story 7.1 — Define time normalization rules (seconds remaining)

### What to build
A precise, testable definition of `seconds_remaining_game`.

#### Rules (v1)
- Regulation: 4 periods × 12:00 each = **48:00**
- Overtime: each OT period length = **5:00**
- `clock` is ISO-8601-ish duration string like `PT06M38.00S`

#### Algorithm [[memory:8239723]]
- **Parse** `clock` into `seconds_remaining_period`
  - \(seconds = minutes * 60 + seconds\) from the duration string
- Compute **elapsed regulation seconds before current period**:
  - if `period` ∈ {1..4}: \((period-1) * 12*60\)
  - if `period` > 4: \(48*60 + (period-5) * 5*60\)
- `seconds_elapsed_game = elapsed_before_period + (period_length_seconds - seconds_remaining_period)`
- `seconds_remaining_game = total_game_length_seconds - seconds_elapsed_game`

**Important**: for live games, “total_game_length_seconds” is not known if OT will occur.
- For baseline modeling, define:
  - `seconds_remaining_regulation` (time remaining until end of regulation) always well-defined
  - `seconds_remaining_game` can be defined as “remaining within current realized game length” for historical games (including OT).

**Recommendation**
- Store both:
  - `seconds_remaining_regulation` (always defined)
  - `seconds_remaining_game` (defined after game is over; includes OT)

#### Pros / cons [[memory:8239723]]
- **Using `seconds_remaining_regulation` for baseline**
  - Pros: consistent for in-progress prediction; avoids “unknown OT length” problem.
  - Cons: compresses OT time into negative/undefined unless handled explicitly.
- **Using `seconds_remaining_game` (including OT)**
  - Pros: correct for historical analysis; clean “countdown to end.”
  - Cons: not available as a true real-time feature pre-OT without assumptions.

### Acceptance criteria
- **AC1**: A spec exists (in this doc or a code comment) defining all fields and edge cases.
- **AC2**: Given sample inputs (period + clock), the computed seconds match expected values.
- **AC3**: Both regulation and overtime periods are handled without exceptions.

---

## Story 7.2 — Add SQL functions for clock parsing (PostgreSQL)

### What to build
Postgres functions (in migrations) to parse PBP `clock` strings into seconds.

#### Implementation approach
- Create `derived` schema
- Create immutable function like:
  - `derived.parse_clock_seconds(clock TEXT) RETURNS INT`

#### Pros / cons [[memory:8239723]]
- Pros: compute in DB; enables views/materialized views efficiently; reusable.
- Cons: parsing logic in SQL is less ergonomic than Python; must be well-tested.

### Acceptance criteria
- **AC1**: Function returns correct seconds for representative strings:
  - `PT12M00.00S` → 720
  - `PT00M00.00S` → 0
  - `PT06M38.00S` → 398
- **AC2**: Invalid formats return NULL (or throw a controlled exception; pick one and document).

---

## Story 7.3 — Create `derived.game_state_by_event` view

### What to build
SQL view:
- `derived.game_state_by_event`

Derived from:
- `pbp_events` (ordering, clock, score)
- optionally `games` (home/away IDs)

#### Performance
Index dependency:
- uses `pbp_events(game_id, order_number)` index already present.

### Acceptance criteria
- **AC1**: `SELECT * FROM derived.game_state_by_event WHERE game_id = ... ORDER BY order_number` returns the full timeline.
- **AC2**: `seconds_remaining_regulation` is monotonic non-increasing within each period (allowing ties).
- **AC3**: `score_diff_home` equals `score_home - score_away` for all rows.

---

## Story 7.4 — Materialized view for model extraction (optional but recommended)

### What to build
Materialized view:
- `derived.mv_game_state_by_event`

Refresh strategy:
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requires unique index)

#### Pros / cons [[memory:8239723]]
- Pros: fast extraction for training; reduces repeated compute.
- Cons: refresh management complexity; storage overhead.

### Acceptance criteria
- **AC1**: MV refresh completes successfully.
- **AC2**: MV row counts match the base view.

---

## Story 7.5 — QC: game-state invariants

### What to build
Extend `scripts/qc_report.py` (or new script) to validate:
- rowcount equals `len(actions)` for sampled games
- no duplicate `(game_id, order_number)` (already guaranteed)
- time parsing not NULL for >99% of events (excluding known admin events if any)

### Acceptance criteria
- **AC1**: QC fails non-zero if any invariant breaks.
- **AC2**: QC report includes counts of null time fields and example bad rows.

---

## Story 7.6 — Dataset export for modeling (minimal)

### What to build
Script to export training rows:
- `scripts/export_game_state.py --dsn ... --out data/exports/game_state_2023-24.parquet --season 2023-24`

Even for a baseline model, you want a repeatable export step.

### Acceptance criteria
- **AC1**: export includes required columns and is stable across reruns (same DB state → same output).
- **AC2**: export supports filtering by season (via `games.season`) once populated.


