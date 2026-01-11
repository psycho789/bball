## NBA Data Sources Analysis v2 (PBP + schedule + boxscore + odds + nba_api)

This document updates our prior approach based on newly validated endpoints and the decision to incorporate **odds** into the dataset.

### Scope
- **In scope**: reliable historical game discovery, raw PBP ingestion, supporting game/team/player metadata, and **daily odds snapshots**.
- **Not in scope**: ML feature engineering, master feature tables, betting execution, or “prediction models.”

---

## 1) Verified NBA endpoints (we actually hit them)

### 1.1 LiveData: Play-by-play (PBP)
- **Endpoint pattern**: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json`
- Verified with example gameId `0022400196`:
  - Returns JSON with `meta.code=200` and `game.actions[]`.

Example:
- [PBP example](https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022400196.json)

### 1.2 LiveData: Boxscore
- **Endpoint pattern**: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`
- Verified with example gameId `0022400196`:
  - Returns JSON with `meta.code=200` and `game` payload.

Why it matters:
- Boxscore can fill in **game-level** metadata not present in PBP (lineups, player/team context, etc.) while still staying within NBA-hosted sources.

### 1.3 LiveData: Today’s scoreboard (NBA leagueId=00)
- **Endpoint**: `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`
- Verified:
  - Returns `scoreboard.gameDate` + `scoreboard.games[]` with home/away team objects.

Example:
- [Today’s scoreboard (NBA)](https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json)

**Important limitation**
- This endpoint is “today only.” We tested a plausible historical-date URL pattern and received HTTP 403.
- Conclusion: **do not depend on scoreboard for historical backfill** unless you find and validate a historical endpoint.

### 1.4 StaticData: ScheduleLeagueV2 (season schedule)
- **Endpoint**: `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`
- Verified:
  - Returns `leagueSchedule.seasonYear`, `leagueSchedule.leagueId`, and `leagueSchedule.gameDates[]` with `games[]` containing `gameId`, teams, venue, broadcasters, etc.

Example:
- [ScheduleLeagueV2](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json)

**Honest limitations**
- The verified URL returns the schedule for a specific season (`seasonYear: 2025-26` in the current response).
- We have **not yet validated** how to retrieve **past seasons** via this staticData host (if available).
  - Therefore, do not assume this endpoint alone can backfill multiple historical seasons.

### 1.5 LiveData: Odds (today’s games)
- **Endpoint**: `https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json`
- Verified:
  - Returns JSON with a top-level `games[]`.
  - Each game has `gameId`, `homeTeamId`, `awayTeamId`, and `markets[]`.
  - Each market includes:
    - `name` (example: `2way`)
    - `group_name` (example: `regular`)
    - `odds_type_id` (integer)
    - `books[]` (multiple books/providers)
  - Each book includes:
    - `id` (string, e.g. `sr:book:818`)
    - `name`
    - `url`
    - `outcomes[]`
  - Each outcome includes:
    - `type` (example: `home` / `away`)
    - `odds` (string numeric)
    - `opening_odds` (string numeric)
    - `odds_trend` (example: `up`)
    - `odds_field_id` (integer)

Example:
- [Odds: today’s games](https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json)

**Critical limitation**
- This endpoint appears to be **today-only** (based on name and observed payload).
- We have **not validated** any historical odds URL pattern or query parameters.

Practical implication:
- If you want a historical odds dataset, you should treat this as a **daily snapshot feed**:
  - fetch it every day and archive it (or multiple times per day if you want intraday drift).

---

## 2) Using `nba_api` for historical game discovery (verified)

`nba_api` is a Python client for `stats.nba.com` endpoints (not the CDN endpoints).

Reference:
- [`nba_api` repository](https://github.com/swar/nba_api?utm_source=openai)

### What we verified
We verified that `nba_api` can return **historical NBA game IDs** across multiple seasons using `LeagueGameFinder`:
- 2021-22: 1,394 unique `GAME_ID`
- 2022-23: 1,395 unique `GAME_ID`
- 2023-24: 1,397 unique `GAME_ID`

This is sufficient for **robust historical backfill planning** (discover game IDs first, then fetch PBP/boxscore from the CDN by gameId).

### Pros / cons [[memory:8239723]]
- **Pros**
  - Solves the “how do I enumerate historical gameIds?” problem.
  - Returns normalized tables (pandas frames) that are easy to load into your DB staging.
- **Cons**
  - Different host/system (`stats.nba.com`) than the PBP CDN; behavior is more “anti-bot” than a stable public API.
  - You must implement conservative throttling, retries, and run tracking.

### Rate limiting reality (honest)
`stats.nba.com` does not publish an official numeric limit. Empirically you should:
- throttle (e.g., ~1 request/sec/worker to start),
- keep concurrency low per IP,
- implement exponential backoff on 403/429/5xx,
- archive responses to avoid re-hitting endpoints unnecessarily.

---

## 3) Can `nba_api` provide odds?

**Likely no** for the same structure you found on the CDN:
- We inspected `nba_api.stats.endpoints` and found **no endpoints containing `odds`/`bet`** in their names.

Conclusion:
- If you want the odds payload you discovered, plan on ingesting it from:
  - [Odds: today’s games](https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json)
- And treat it as a snapshot feed you archive.

---

## 4) Recommended data acquisition strategy (serious + future-proof)

### 4.1 Game ID discovery
Use a two-layer strategy:
- **Primary (historical)**: `nba_api` `LeagueGameFinder` to enumerate game IDs season-by-season.
- **Supplemental (current season)**: [ScheduleLeagueV2](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json) to validate and enrich the active season schedule.
- **Operational (today)**: [Today’s scoreboard](https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json) for near-real-time monitoring only.

### 4.2 Raw event data ingestion
For each `gameId`:
- Fetch PBP:
  - [PBP example](https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022400196.json)
- Fetch boxscore:
  - `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json` (validated pattern)

Store both files in your raw archive and link them via `source_files`.

### 4.3 Odds ingestion (daily snapshots)
Fetch and store:
- [Odds: today’s games](https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json)

Recommended cadence:
- **Minimum**: daily
- **Better**: hourly (if you care about line movement)

---

## 5) Odds storage model (raw, normalized enough)

Because odds data is inherently a “snapshot over time,” the ordering key is **when you fetched it**, not just `gameId`.

### Recommended tables (high level)
- `odds_snapshots`
  - One row per fetch execution (timestamped)
  - Links to `source_files`
- `odds_games`
  - One row per `(snapshot_id, game_id)`
  - Stores `home_team_id`, `away_team_id`, plus external ids (`srMatchId`, `sr_id`) if present
- `odds_markets`
  - One row per `(snapshot_id, game_id, odds_type_id, group_name, name)`
- `odds_books`
  - One row per `(snapshot_id, game_id, market_key, book_id)`
- `odds_outcomes`
  - One row per `(snapshot_id, game_id, market_key, book_id, outcome_type)`
  - Stores `odds`, `opening_odds`, `odds_trend`, `odds_field_id`

### Pros / cons [[memory:8239723]]
- **Pros**
  - Preserves time series of odds (snapshots), not just a single “current” value.
  - Normalizes repeated dimensions (books/markets/outcomes) without losing raw payload.
- **Cons**
  - More rows and more joins than stuffing everything into JSONB
  - Requires careful uniqueness constraints keyed by `snapshot_id`

**Best practice**: store the full raw payload JSONB at snapshot level as well, so you can backfill new columns later.

---

## 6) What to update next (after you review)

Once you approve this strategy, the next sprint document should:
- explicitly use `nba_api` for game discovery/backfill planning,
- use CDN PBP/boxscore for raw game ingestion,
- add a daily/hourly odds snapshot ingestion path,
- include conservative `stats.nba.com` throttling defaults + backoff behavior.


