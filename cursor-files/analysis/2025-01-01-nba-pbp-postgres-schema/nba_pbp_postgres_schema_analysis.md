## NBA Play-by-Play (PBP) JSON → PostgreSQL Raw Warehouse Design

This document focuses **only** on storing and structuring the NBA’s unofficial PBP JSON (and minimal supporting lookups) in PostgreSQL for **robust, efficient, historical warehousing**.

Primary example sources:
- **PBP JSON**: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022400196.json`
- **Scoreboard JSON**: `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`

---

## 1) Raw Data Source Analysis (Fields + Structure)

### 1.1 Top-level structure (PBP)

The PBP endpoint returns two top-level objects:
- **`meta`**: request/version/timestamp + response code
  - Observed keys: `version`, `code`, `request`, `time`
- **`game`**: the actual payload
  - Observed keys: `gameId`, `actions`

The high-frequency portion is **`game.actions[]`**, a sequence of event objects.

### 1.2 `game.actions[]` (core event fields)

From a representative game sample, these fields are essentially always present:
- **Ordering / identity**
  - `actionNumber` (int): per-game event number (unique in sample)
  - `orderNumber` (int): per-game sortable ordering key (unique in sample, looks like increments of 10k)
- **Time**
  - `period` (int)
  - `periodType` (string): e.g. `REGULAR`
  - `clock` (string): ISO-8601-ish duration string like `PT10M53.00S`
  - `timeActual` (string timestamp): e.g. `2024-11-09T03:12:36.0Z`
- **Classification**
  - `actionType` (string): e.g. `2pt`, `3pt`, `rebound`, `foul`, `turnover`, `substitution`, `timeout`, `period`, `jumpball`, …
  - `subType` (string): e.g. `Jump Shot`, `defensive`, `personal`, `out`, `full`, `start`
  - `descriptor` (string, sparse): extra shot/turnover descriptor
- **Narration**
  - `description` (string): human-readable line
  - `edited` (string timestamp): last edit time for the action record
- **Score / possession**
  - `scoreHome` / `scoreAway` (strings containing integers)
  - `possession` (int): **teamId** that has possession (or `0` for some admin events)
- **Primary actor**
  - `personId` (int): primary person involved; `0` for some admin events (period start)
  - `playerName` / `playerNameI` (strings, sparse; often absent when `personId = 0`)
  - `personIdsFilter` (array[int]): a list of relevant people for the event (often includes shooter + assister, etc.)
- **Team**
  - `teamId` (int, sparse for non-team events like “period start/end”)
  - `teamTricode` (string, sparse)
- **Shot location**
  - `x`, `y` (float, nullable): modern coordinate system (present on made/missed FGs)
  - `xLegacy`, `yLegacy` (int, nullable): legacy coordinate system
  - `side` (string nullable): e.g. `right`
- **Flags**
  - `isFieldGoal` (int): 0/1
  - `isTargetScoreLastPeriod` (bool): observed always present
- **Qualifiers**
  - `qualifiers` (array[string]): usually empty; otherwise small tokens like `fastbreak`, `2ndchance`, `fromturnover`, `2freethrow`, `team`, `mandatory`, etc.

### 1.3 `game.actions[]` (sparse, event-type-specific fields)

Common sparse fields by category:

#### Field goal / shot events (`2pt`, `3pt`, some `freethrow`)
- `area` (string): e.g. `Above the Break 3`, `Mid-Range`
- `areaDetail` (string): e.g. `24+ Center`
- `shotDistance` (float)
- `shotResult` (string): `Made` / `Missed`
- `pointsTotal` (int): total points for the player after the event (on scoring events)

#### 1:1 “secondary participant” cases
These show up as separate fields (not arrays), suggesting a 1:1 relationship to the event:
- Assists: `assistPersonId`, `assistPlayerNameInitial`, `assistTotal`
- Blocks: `blockPersonId`, `blockPlayerName`
- Steals: `stealPersonId`, `stealPlayerName`
- Fouls drawn: `foulDrawnPersonId`, `foulDrawnPlayerName`
- Officials: `officialId`

#### Counters / links
- Rebounds: `reboundOffensiveTotal`, `reboundDefensiveTotal`, `reboundTotal`
- Turnovers: `turnoverTotal`
- `shotActionNumber`: links a rebound to the shot event’s `actionNumber`

#### Jump ball event participants
Jump balls contain multiple participant IDs:
- `jumpBallWonPersonId`, `jumpBallWonPlayerName`
  `jumpBallLostPersonId`, `jumpBallLostPlayerName`
  `jumpBallRecoverdPersonId`, `jumpBallRecoveredName`

### 1.4 Scoreboard JSON (game + team metadata)

The scoreboard endpoint is a daily list of games:
- `scoreboard.gameDate`, `leagueId`, `leagueName`
- `scoreboard.games[]` includes:
  - Game identity/time: `gameId`, `gameCode`, `gameTimeUTC`, `gameEt`
  - Status: `gameStatus`, `gameStatusText`, `period`, `gameClock`
  - Labels: `gameLabel`, `gameSubLabel`, `gameSubtype`
  - Home/Away team objects: `teamId`, `teamTricode`, `teamName`, `teamCity`, `wins`, `losses`, `score`, plus per-period scoring breakdown
  - `isNeutral`, `seriesText`, etc.
  - Note: it also includes `pbOdds` in the sample, but this document ignores odds as requested.

**Key takeaway**: scoreboard is useful as a **game + team identity source** (and for validating home/away mapping), but PBP is the authoritative source for the event stream.

---

## 2) PostgreSQL Schema Suggestion (Normalized)

### 2.1 Design goals

- **Correctness & reproducibility**: store the raw stream with stable ordering and allow exact replays of the event list.
- **Normalized lookups** for static entities (teams, players, officials, games).
- **Avoid “wide sparse tables”** where 70% of columns are null for most events.
- **Keep ingestion simple**: allow idempotent upserts by natural uniqueness constraints.

### 2.2 Recommended normalization level (and why)

#### Why not store everything as JSONB only?
- **Pros**: fastest to ingest; schema-flexible; resilient to upstream changes.
- **Cons**: slower to query at scale; harder to index critical fields; harder to enforce integrity/order uniqueness.

#### Why not fully 3NF every event-type detail into separate tables?
- **Pros**: minimal nulls; clear typing; very clean domain modeling.
- **Cons**: too many joins for common queries; slower ingestion; lots of small tables; harder to evolve with upstream field additions.

#### Recommended approach: “Normalized core + typed columns + narrow child tables”
**Pattern**: *Anchor table* (`pbp_events`) + *dimension tables* (games/teams/players) + *bridge tables* only where needed (qualifiers and multi-actor roles).
- **Pros**: good query performance; enforceable integrity; flexible to field drift; reduces repeated strings.
- **Cons**: still some nulls (inevitable); schema updates needed if NBA adds major new fields you want typed.

This is essentially a **hub-and-spoke** design: `pbp_events` is the hub, dimensions are spokes, and a few bridge tables capture repeating values.

### 2.3 Core tables

#### `games`
Stores game identity and minimal metadata.
- **Primary key**: `game_id` (text) — NBA’s gameId strings include leading zeros, so store as text.
- **Columns**
  - `game_id` TEXT PRIMARY KEY
  - `game_code` TEXT NULL
  - `game_time_utc` TIMESTAMPTZ NULL
  - `season` SMALLINT NULL (optional; can be derived from game_id but safer to store explicitly once you define parsing rules)
  - `season_type` TEXT NULL (REGULAR/PLAYOFF/… if you have a source)
  - `home_team_id` BIGINT NULL REFERENCES teams(team_id)
  - `away_team_id` BIGINT NULL REFERENCES teams(team_id)
  - `is_neutral` BOOLEAN NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Notes:
- Scoreboard provides home/away mapping; PBP events have `teamId` but do not declare home/away directly in `game`.

#### `teams`
- **Primary key**: `team_id` BIGINT (NBA team IDs fit in BIGINT)
- **Columns**
  - `team_id` BIGINT PRIMARY KEY
  - `team_tricode` CHAR(3) NOT NULL
  - `team_city` TEXT NULL
  - `team_name` TEXT NULL
  - `active_from` DATE NULL
  - `active_to` DATE NULL

Notes:
- `team_tricode` changes occasionally historically; if you care about deep history, consider a `team_identifiers` history table keyed by `(team_id, valid_from)`.

#### `players`
Players are referenced by `personId`. Names are present but inconsistent/sparse, so treat names as attributes, not identifiers.
- **Primary key**: `person_id` BIGINT
- **Columns**
  - `person_id` BIGINT PRIMARY KEY
  - `display_last_name` TEXT NULL   -- (from `playerName`)
  - `display_name_initial` TEXT NULL -- (from `playerNameI`)
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Notes:
- You will eventually want a richer player dimension (full name, position, etc.) from another NBA endpoint, but for *raw PBP warehousing* this is enough.

#### `officials`
Referenced by `officialId` on some events.
- **Primary key**: `official_id` BIGINT
- **Columns**
  - `official_id` BIGINT PRIMARY KEY
  - `display_name` TEXT NULL

### 2.4 `pbp_events` (main fact table)

This table stores the **canonical event stream** for each game.

**Primary key recommendation**:
- Use a surrogate `event_id` BIGSERIAL for internal referencing,
- And enforce natural uniqueness with `(game_id, order_number)` and/or `(game_id, action_number)`.

**Columns (recommended typed subset)**:
- Identity / ordering
  - `event_id` BIGSERIAL PRIMARY KEY
  - `game_id` TEXT NOT NULL REFERENCES games(game_id)
  - `action_number` INTEGER NOT NULL
  - `order_number` INTEGER NOT NULL
- Time
  - `period` SMALLINT NOT NULL
  - `period_type` TEXT NOT NULL
  - `clock` TEXT NOT NULL               -- store raw `PT..` string
  - `time_actual` TIMESTAMPTZ NULL      -- parse from `timeActual` if present
- Classification / narration
  - `action_type` TEXT NOT NULL
  - `sub_type` TEXT NOT NULL
  - `descriptor` TEXT NULL
  - `description` TEXT NOT NULL
  - `edited_at` TIMESTAMPTZ NULL        -- parse from `edited`
- Actors
  - `team_id` BIGINT NULL REFERENCES teams(team_id)
  - `person_id` BIGINT NOT NULL REFERENCES players(person_id)  -- note: `0` occurs; handle via a “sentinel” player or allow NULL (see below)
  - `possession_team_id` BIGINT NOT NULL REFERENCES teams(team_id) -- note: `0` occurs; same consideration
- Score snapshot
  - `score_home` INTEGER NOT NULL
  - `score_away` INTEGER NOT NULL
- Flags
  - `is_field_goal` BOOLEAN NOT NULL
  - `is_target_score_last_period` BOOLEAN NOT NULL
- Shot/location-ish
  - `x` DOUBLE PRECISION NULL
  - `y` DOUBLE PRECISION NULL
  - `x_legacy` INTEGER NULL
  - `y_legacy` INTEGER NULL
  - `side` TEXT NULL
- Optional raw payload
  - `raw_action` JSONB NOT NULL         -- store the full action object as received for forward compatibility

**Important sentinel decision** (practical ingestion detail):
- Some events have `personId = 0` and/or `teamId` missing.
- You have two good options:
  1) allow `person_id` to be NULL (and skip `players` FK for those rows), and allow `possession_team_id` to be NULL when `0`.
  2) create sentinel rows:
     - `players(person_id=0, display_name='SYSTEM')`
     - `teams(team_id=0, team_tricode='NA0')`
  Option (1) is more semantically honest; option (2) is simpler operationally if you want strict NOT NULL + FK everywhere.

**Constraints / indexes (critical)**:
- Uniqueness/order:
  - `UNIQUE (game_id, order_number)`
  - `UNIQUE (game_id, action_number)`
- Query acceleration:
  - `INDEX (game_id, order_number)` (often enough; also helps streaming reads)
  - `INDEX (game_id, period, clock)` (optional)
  - `INDEX (action_type)` (optional)
  - `GIN (raw_action)` only if you actively query deep JSON paths; otherwise skip

### 2.5 Child/bridge tables (recommended)

#### `pbp_event_qualifiers`
Because `qualifiers` is an array and can have 0..N values per event.
- `event_id` BIGINT NOT NULL REFERENCES pbp_events(event_id) ON DELETE CASCADE
- `qualifier` TEXT NOT NULL
- PRIMARY KEY (`event_id`, `qualifier`)

Optional normalization: if qualifiers are stable and small, you can store them as `TEXT[]` in `pbp_events` instead; but the bridge table is easier to index and filter efficiently.

#### `pbp_event_people_filter`
Because `personIdsFilter` is a list of relevant people.
- `event_id` BIGINT NOT NULL REFERENCES pbp_events(event_id) ON DELETE CASCADE
- `person_id` BIGINT NOT NULL REFERENCES players(person_id)
- PRIMARY KEY (`event_id`, `person_id`)

This table makes it easy to answer “show all events involving player X” without parsing JSON.

### 2.6 “Typed detail columns vs separate detail table”

For 1:1 fields (assist/block/steal/foul-drawn/jumpball participants), you have two reasonable options:

#### Option A (recommended): Keep typed columns in `pbp_events` for 1:1 relationships
Add nullable columns to `pbp_events`:
- `assist_person_id` BIGINT NULL REFERENCES players(person_id)
- `block_person_id` BIGINT NULL REFERENCES players(person_id)
- `steal_person_id` BIGINT NULL REFERENCES players(person_id)
- `foul_drawn_person_id` BIGINT NULL REFERENCES players(person_id)
- `official_id` BIGINT NULL REFERENCES officials(official_id)
- Jump ball:
  - `jump_won_person_id` BIGINT NULL
  - `jump_lost_person_id` BIGINT NULL
  - `jump_recovered_person_id` BIGINT NULL

And typed stat/counter fields:
- `points_total` INTEGER NULL
- `assist_total` INTEGER NULL
- `turnover_total` INTEGER NULL
- `rebound_offensive_total` INTEGER NULL
- `rebound_defensive_total` INTEGER NULL
- `rebound_total` INTEGER NULL
- `shot_distance` DOUBLE PRECISION NULL
- `shot_result` TEXT NULL
- `area` TEXT NULL
- `area_detail` TEXT NULL
- `shot_action_number` INTEGER NULL  -- link to another actionNumber inside game

**Pros**
- **Fast reads** for common event analytics (no extra joins for assist/block/steal)
- **Simple ingestion**: one row per action, mostly direct field mapping
- Keeps the “event stream” self-contained

**Cons**
- Some nulls are unavoidable (many event types don’t use these columns)
- If the upstream JSON adds many new per-event fields, you may update the table periodically

#### Option B: Move per-event details to a separate 1:1 table (more normalized)
`pbp_event_details` keyed by `(event_id)` containing all sparse columns.

**Pros**
- Keeps `pbp_events` narrower
- Lets you physically separate hot vs cold columns (some storage/cache benefits)

**Cons**
- Extra join in most queries that need those details
- Slightly more complex ingestion/upsert logic

For most warehouses, **Option A** is the best balance.

---

## 2.7 Suggested DDL (reference)

This is a reference sketch; adapt naming/nullable decisions to your ingestion strategy.

```sql
CREATE TABLE teams (
  team_id        BIGINT PRIMARY KEY,
  team_tricode   CHAR(3) NOT NULL,
  team_city      TEXT,
  team_name      TEXT,
  active_from    DATE,
  active_to      DATE
);

CREATE TABLE players (
  person_id              BIGINT PRIMARY KEY,
  display_last_name      TEXT,
  display_name_initial   TEXT,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE officials (
  official_id    BIGINT PRIMARY KEY,
  display_name   TEXT
);

CREATE TABLE games (
  game_id        TEXT PRIMARY KEY,
  game_code      TEXT,
  game_time_utc  TIMESTAMPTZ,
  season         SMALLINT,
  season_type    TEXT,
  home_team_id   BIGINT REFERENCES teams(team_id),
  away_team_id   BIGINT REFERENCES teams(team_id),
  is_neutral     BOOLEAN,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pbp_events (
  event_id                     BIGSERIAL PRIMARY KEY,
  game_id                      TEXT NOT NULL REFERENCES games(game_id),
  action_number                INTEGER NOT NULL,
  order_number                 INTEGER NOT NULL,
  period                       SMALLINT NOT NULL,
  period_type                  TEXT NOT NULL,
  clock                        TEXT NOT NULL,
  time_actual                  TIMESTAMPTZ,
  action_type                  TEXT NOT NULL,
  sub_type                     TEXT NOT NULL,
  descriptor                   TEXT,
  description                  TEXT NOT NULL,
  edited_at                    TIMESTAMPTZ,
  team_id                      BIGINT REFERENCES teams(team_id),
  possession_team_id           BIGINT REFERENCES teams(team_id),
  person_id                    BIGINT REFERENCES players(person_id),
  score_home                   INTEGER NOT NULL,
  score_away                   INTEGER NOT NULL,
  is_field_goal                BOOLEAN NOT NULL,
  is_target_score_last_period  BOOLEAN NOT NULL,
  x                            DOUBLE PRECISION,
  y                            DOUBLE PRECISION,
  x_legacy                     INTEGER,
  y_legacy                     INTEGER,
  side                         TEXT,

  -- common sparse details
  area                         TEXT,
  area_detail                  TEXT,
  shot_distance                DOUBLE PRECISION,
  shot_result                  TEXT,
  points_total                 INTEGER,
  assist_person_id             BIGINT REFERENCES players(person_id),
  assist_total                 INTEGER,
  block_person_id              BIGINT REFERENCES players(person_id),
  steal_person_id              BIGINT REFERENCES players(person_id),
  foul_drawn_person_id         BIGINT REFERENCES players(person_id),
  official_id                  BIGINT REFERENCES officials(official_id),
  rebound_offensive_total      INTEGER,
  rebound_defensive_total      INTEGER,
  rebound_total                INTEGER,
  turnover_total               INTEGER,
  shot_action_number           INTEGER,

  -- jump ball participants
  jump_won_person_id           BIGINT REFERENCES players(person_id),
  jump_lost_person_id          BIGINT REFERENCES players(person_id),
  jump_recovered_person_id     BIGINT REFERENCES players(person_id),

  raw_action                   JSONB NOT NULL
);

CREATE UNIQUE INDEX ux_pbp_events_game_order
  ON pbp_events (game_id, order_number);

CREATE UNIQUE INDEX ux_pbp_events_game_action
  ON pbp_events (game_id, action_number);

CREATE INDEX ix_pbp_events_game_order
  ON pbp_events (game_id, order_number);

CREATE TABLE pbp_event_qualifiers (
  event_id   BIGINT NOT NULL REFERENCES pbp_events(event_id) ON DELETE CASCADE,
  qualifier  TEXT NOT NULL,
  PRIMARY KEY (event_id, qualifier)
);

CREATE TABLE pbp_event_people_filter (
  event_id   BIGINT NOT NULL REFERENCES pbp_events(event_id) ON DELETE CASCADE,
  person_id  BIGINT NOT NULL REFERENCES players(person_id),
  PRIMARY KEY (event_id, person_id)
);
```

---

## 3) Dataset Scale and Collection Strategy (Raw Warehouse Perspective)

You asked about “how far back to go” and “minimum viable dataset size.” Even though this document is about raw storage (not feature engineering), the data collection horizon has *direct warehouse implications* (partitioning, backfills, late corrections, schema drift).

### 3.1 How far back should you collect?

**Recommendation**: target **3–5 seasons minimum** for an initial “serious” historical warehouse, and ideally **10+ seasons** if you’re optimizing for long-term reuse.

**Why 1 season is usually not enough (for reliability, not modeling tricks)**
- **Rule changes & style drift**: event mix changes season-to-season.
- **Roster churn**: player IDs persist, but player involvement and context vary.
- **Data quality variance**: occasional upstream quirks are better detected with more history.

**Pros / cons**
- **1 season (~1,230 games)**:
  - Pros: fast to build, cheaper storage, simplest backfill.
  - Cons: brittle benchmarks; fewer edge cases; harder to detect ingestion anomalies.
- **3–5 seasons (~3,700–6,150 games)**:
  - Pros: much better coverage of rare event types and ingestion edge cases; more stable warehouse expectations.
  - Cons: bigger backfill; more schema drift to handle.
- **10+ seasons**:
  - Pros: best long-term asset; robust QA baselines; supports many downstream use cases.
  - Cons: operationally heavier (reprocessing, storage, and long-running backfills).

### 3.2 Minimum viable dataset size (practical guidance)

If the goal is “trust the results” of an initial time-series model, the honest answer is: **it depends heavily on the target and evaluation design**. From a warehousing standpoint, a pragmatic minimum that usually avoids fooling yourself operationally is:
- **MVP**: ~**1,000–2,000 games** (≈ 1–2 seasons) to validate ingestion correctness + basic downstream reproducibility.
- **More reliable**: ~**3,000–6,000 games** (≈ 3–5 seasons) to reduce season-specific bias and cover more edge cases.

If you only build 1 season first, treat it explicitly as a **pipeline shakeout**, not a final “trusted” dataset.

### 3.3 Data integrity: the critical ordering/uniqueness key

Within a single game, the most critical columns to guarantee correct event ordering and uniqueness are:

- **`(game_id, order_number)`**: recommended as the **primary natural ordering key**
  - In the sample, `orderNumber` is unique and strictly orders the stream.
- Also enforce **`(game_id, action_number)`** as a secondary uniqueness check.

**Why not use `(period, clock)`?**
- Multiple events can occur at the same clock timestamp.
- The clock is a string and not guaranteed unique; it’s not a stable ordering key by itself.

**Best practice**
- Store both `order_number` and `action_number`
- Enforce uniqueness on both pairs, and always sort by `order_number` for replay.

---

## 4) Operational Notes (optional but recommended)

### 4.1 Partitioning
When you reach multiple seasons, consider partitioning `pbp_events` by:
- **`game_id` hash partitioning** (even distribution; great for parallel loads), or
- **season** (range partitioning) if you store `season` on `games` and denormalize `season` into `pbp_events` for easy partition pruning.

### 4.2 Idempotent ingestion
Implement upserts like:
- Upsert `games`, `teams`, `players` first.
- Upsert `pbp_events` by unique `(game_id, order_number)` (or `(game_id, action_number)`).
- Replace child table rows (`qualifiers`, `people_filter`) per event_id on re-ingest.

### 4.3 Keep the raw JSON
Even with typed columns, keep `raw_action JSONB` so you can:
- Backfill new typed columns later
- Handle upstream field drift without re-scraping



