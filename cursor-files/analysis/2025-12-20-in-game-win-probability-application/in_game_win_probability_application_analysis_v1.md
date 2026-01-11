## Analysis: In-Game Win Probability Application (Data Contract → Model → Live Scoring)

**Date**: 2025-12-20  
**Status**: Draft  
**Author**: Cursor AI coding agent  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Define a leak-proof, reproducible, and deployable in-game win probability pipeline in `bball`: dataset contract, season-based train/test split, snapshot sampling, training + calibration, evaluation, live scoring interface, and paper-trading auditability.

## Analysis Standards Reference

This analysis follows `cursor-files/templates/ANALYSIS_STANDARDS.md` and `cursor-files/templates/ANALYSIS_TEMPLATE.md`.

## Executive Summary

### Key Findings
- **`derived.pbp_event_state` already contains the v1 feature set** (`point_differential`, `possession_side`) and label (`final_winning_team`) needed for a baseline in-game win model; regulation-safe time is sourced from `derived.game_state_by_event.seconds_remaining_regulation`.
  - **Evidence**:
    - **File**: `scripts/materialize_pbp_event_state.py:1-30`
    - **File**: `db/migrations/014_pbp_event_state_possession_side_0_home_1_away.sql:1-41`
- **Prediction-time possession is materially incomplete**: `possession_side` is NULL for **2,798,576 / 7,349,599 rows (38.0779%)**, so the modeling contract must encode an explicit `"unknown"` possession state.
  - **Evidence**:
    - **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "WITH base AS (SELECT s.*, (2000 + substring(s.game_id from 4 for 2)::int) AS season_start FROM derived.pbp_event_state s) SELECT COUNT(*) AS rows_total, COUNT(DISTINCT game_id) AS games_total, MIN(season_start) AS min_season_start, MAX(season_start) AS max_season_start, COUNT(*) FILTER (WHERE possession_side IS NULL) AS rows_null_possession, ROUND(100.0*COUNT(*) FILTER (WHERE possession_side IS NULL)/NULLIF(COUNT(*),0), 4) AS pct_null_possession, COUNT(*) FILTER (WHERE final_winning_team IS NULL) AS rows_null_label FROM base;"`
    - **Output**:
      ```
       rows_total | games_total | min_season_start | max_season_start | rows_null_possession | pct_null_possession | rows_null_label
      ------------+-------------+------------------+------------------+----------------------+---------------------+-----------------
          7349599 |       14167 |             2015 |             2025 |              2798576 |             38.0779 |               0
      (1 row)
      ```
- **A leak-proof season split is definable from `game_id` alone**: `season_start = 2000 + substring(game_id from 4 for 2)::int`, with **test = season_start 2024 (2024–25)** and **train = seasons < 2024**, leaving **season_start 2025 (2025–26 partial)** as a forward-time drift set.
  - **Evidence**:
    - **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "WITH games_by_season AS (SELECT (2000 + substring(game_id from 4 for 2)::int) AS season_start, COUNT(DISTINCT game_id) AS games, COUNT(*) AS rows FROM derived.pbp_event_state GROUP BY 1) SELECT * FROM games_by_season ORDER BY season_start;"`
    - **Output**:
      ```
       season_start | games |  rows
      --------------+-------+--------
               2015 |  1427 | 661042
               2016 |  1413 | 653156
               2017 |  1392 | 636683
               2018 |  1394 | 662382
               2019 |  1258 | 670374
               2020 |  1221 | 685726
               2021 |  1393 | 783109
               2022 |  1395 | 769737
               2023 |  1396 | 765044
               2024 |  1400 | 780269
               2025 |   478 | 282077
      (11 rows)
      ```
- **The NBA odds endpoint is “today-only”** (`odds_todaysGames.json`), so historical odds backtests require building your own time series via continuous snapshot capture; “NBA-provided historical odds” is not available in this repo’s data model.
  - **Evidence**:
    - **File**: `scripts/fetch_odds_today.py:1-89`
    - **File**: `db/migrations/001_schema_v1.sql:136-145` (explicit “today-only feed” comment + snapshot tables)

### Critical Issues Identified
- **Data leakage risk (high severity)**: per-event rows are highly autocorrelated within a game; row-level random splitting violates the “no shared games” constraint and inflates metrics.
  - **Evidence**:
    - **File**: `scripts/verify_espn_win_probabilities.py:23-32` (explicit within-game autocorrelation + game-cluster bootstrap design)
- **Time feature leakage risk (high severity)**: `derived.game_state_by_event.seconds_remaining_game` uses `max_period_in_game` to compute a realized `total_game_length_seconds`, which depends on whether overtime occurs; overtime occurrence is future information at prediction time during regulation.
  - **Evidence**:
    - **File**: `db/migrations/005_derived_game_state_view.sql:5-43` (uses `max(e.period) OVER (...) AS max_period_in_game` and `total_game_length_seconds`)
    - **File**: `scripts/materialize_pbp_event_state.py:14-20` (explicitly maps `derived.pbp_event_state.time_remaining` from `derived.game_state_by_event.seconds_remaining_game`)
- **Undefined “snapshot row” contract (high severity)**: the repo has per-event tables and a verification sampling strategy, but no single authoritative “one row” definition for *training* and *live scoring*.

### Recommended Actions
- **Define dataset contract** (Priority: High): codify “snapshot row” semantics, allowed prediction-time fields, and possession missingness rules.
- **Freeze season split artifacts** (Priority: High): generate and store train/test game lists and enforce zero overlap.
- **Build snapshot sampling transform** (Priority: High): convert per-event rows into fixed time buckets so each game contributes evenly.
- **Train + serialize full pipeline** (Priority: High): regularized logistic regression + preprocessing + (optional) calibration, saved as a single artifact.
- **Implement live scoring interface + forward-time smoke test** (Priority: High): score user-provided `(score diff, time remaining, possession)` and measure drift on the partial 2025–26 season without training on it.
- **Align odds integration to “today-only” reality** (Priority: Medium): compute edge only for days where odds snapshots exist; build an auditable paper-trading log before any real betting.

### Success Metrics
- **Leakage**: overlap between train/test `game_id` sets equals **0**.
  - **Evidence**:
    - **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "WITH base AS (SELECT DISTINCT game_id, (2000 + substring(game_id from 4 for 2)::int) AS season_start FROM derived.pbp_event_state), train AS (SELECT game_id FROM base WHERE season_start < 2024), test AS (SELECT game_id FROM base WHERE season_start = 2024) SELECT COUNT(*) AS overlap_games FROM (SELECT game_id FROM train INTERSECT SELECT game_id FROM test) x;"`
    - **Output**:
      ```
       overlap_games
      ---------------
                   0
      (1 row)
      ```
- **Calibration quality**: Brier score and reliability plots per time bucket, with an explicit decision threshold selection performed on pre-test data only.

## Problem Statement

### Current Situation
The repo ingests and derives play-by-play game state (`derived.pbp_event_state`) and separately ingests ESPN win probability streams and verifies their calibration. The repo does not yet define an authoritative training dataset contract and artifact pipeline for an in-house win probability model that is leak-proof, reproducible, and deployable via a live scoring interface.

### Pain Points
- **Row semantics ambiguity**: “one row” is currently “one event” in `derived.pbp_event_state`, but modeling requires **fixed time-bucket snapshots** so each game contributes evenly.
- **Missing possession**: the model input includes `possession_side`, and its missingness is large enough that dropping rows is not a valid default.
- **Odds limitation**: the NBA odds feed in this repo is a snapshot for today’s games only; historical odds are not present by default.

### Business Impact
- **Modeling validity impact**: a non-grouped split produces invalid evaluation numbers and invalid calibration diagnostics.
- **Decision support impact**: uncalibrated probabilities cannot support threshold-based decisions in a defensible way.
- **Backtesting impact**: without stored odds history, “edge” evaluation is limited to days where snapshots are captured and retained.

### Success Criteria
- **SC1 (contract)**: a reviewer can answer “what is one snapshot row?” and “what fields are allowed at prediction time?” from a single documented contract.
- **SC2 (split)**: test season is exactly 2024–25 (season_start 2024), and **no game appears in both train and test**.
- **SC3 (artifacts)**: dataset Parquet export includes a manifest with exact row counts, distinct games, and season coverage.
- **SC4 (deployability)**: one saved artifact can score live inputs without reimplementing preprocessing.

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: this analysis identifies the existing pipeline entry points (`scripts/materialize_pbp_event_state.py`, `scripts/export_pbp_event_state_parquet.py`, `scripts/fetch_odds_today.py`, `scripts/load_odds_snapshot.py`, `scripts/verify_espn_win_probabilities.py`) and proposes adding new training/eval/live-scoring scripts; exact file count is determined by implementation.
- **Estimated Effort**: this analysis does not contain measured implementation time; implementation effort is tracked in `cursor-files/sprints/sprint-plan-in-game-win-prob-v1.md` and `cursor-files/sprints/sprint-plan-linear-model-derived-pbp-event-state-v1.md`.
- **Technical Complexity**: the primary complexity is leakage-proof splitting + snapshot sampling + calibration protocol that never uses test data.
- **Risk Level**: High, because leakage and calibration errors produce invalid decision support.

**Sprint Scope Recommendation**: Multiple Sprints
- **Rationale**: the end-to-end scope spans reproducible data artifacts, modeling, evaluation, calibration, live scoring interface, and audit logging, plus odds integration that is constrained by today-only odds snapshots.

## Current State Analysis

### System Architecture Overview

This repo implements an ingestion + derived-table pattern:
- **Raw ingest to Postgres**: `pbp_events` rows are stored with provenance (`source_files`, `ingestion_runs`).
  - **Evidence**:
    - **File**: `db/migrations/001_schema_v1.sql:41-113`
- **Derived modeling table**: `derived.pbp_event_state` is materialized from `derived.game_state_by_event` and joined to `games` for possession and final outcome fields.
  - **Evidence**:
    - **File**: `scripts/materialize_pbp_event_state.py:1-268`
    - **File**: `db/migrations/014_pbp_event_state_possession_side_0_home_1_away.sql:1-41`
- **Export artifacts**: `scripts/export_pbp_event_state_parquet.py` provides a streaming Parquet export path.
  - **Evidence**:
    - **File**: `scripts/export_pbp_event_state_parquet.py:1-148`
- **Odds snapshots (today-only)**: the repo fetches `odds_todaysGames` and stores snapshots and normalized child tables.
  - **Evidence**:
    - **File**: `scripts/fetch_odds_today.py:1-89`
    - **File**: `db/migrations/001_schema_v1.sql:136-194`

### Code Quality Assessment
The scripts are structured as single-purpose CLI tools with explicit schema comments in SQL migrations. The current model-training pipeline and its reproducible artifacts are not yet implemented as first-class scripts in `scripts/`.

### Dependencies Analysis
The repo currently pins:
- `pandas==2.2.3`
- `pyarrow==18.1.0`
- `psycopg[binary]==3.2.10`
  - **Evidence**:
    - **File**: `requirements.txt:1-6`

## Technical Assessment

### Design Pattern Analysis: ETL Pipeline (Scripted Batch Jobs)

**Pattern Name**: ETL Pipeline  
**Pattern Category**: Architectural  
**Pattern Intent**: Provide reproducible raw ingestion, derived materialization, and export jobs as explicit, composable scripts.

**Implementation**:
- **PBP ingestion schema + provenance tracking**: `db/migrations/001_schema_v1.sql:41-135`
- **Derived modeling table materialization**: `scripts/materialize_pbp_event_state.py:137-263`
- **Streaming export pattern**: `scripts/export_pbp_event_state_parquet.py:90-143`

**Benefits**:
- Deterministic, replayable transformations when inputs are fixed.
- Clear separation between raw, derived, and export steps.

**Trade-offs**:
- Model training/evaluation is not yet represented as a first-class pipeline stage in the same pattern.
- Live scoring contract is not enforced by code-level interfaces yet.

### Algorithm Analysis: Fixed Time-Bucket Snapshot Selection

**Algorithm Name**: Per-Game Nearest-Anchor Snapshot Selection  
**Algorithm Type**: Selection / Nearest Neighbor (1D)  
**Big O Notation**:
- Time Complexity: \(O(G \cdot (E_g + B))\) using a sorted two-pointer scan per game, where \(G\) is games, \(E_g\) is events in a game, and \(B\) is bucket count.
- Space Complexity: \(O(B)\) per game for output rows (streaming).

**Implementation (existing precedent)**:
The repo already uses “anchor” sampling as a statistical design to reduce within-game autocorrelation (for verification of ESPN probabilities).
- **Evidence**:
  - **File**: `scripts/verify_espn_win_probabilities.py:23-32`
  - **File**: `scripts/verify_espn_win_probabilities.py:688-747` (per-game anchor selection logic)

**Why This Algorithm**:
It ensures each game contributes a fixed number of rows, and it enables time-bucketed evaluation that matches decision contexts (“at 5 minutes remaining”).

## Recommendations

### Immediate Actions (Priority: High)

#### 1) Define “snapshot row” contract (prediction-time fields + missing possession)
Define a single authoritative modeling row (for both training and live scoring):
- **Identifiers**: `game_id`, `season_start`, `bucket_seconds_remaining`, `event_id`
- **Allowed prediction-time fields**:
  - `point_differential` (home − away at the event)
  - `time_remaining_regulation` (seconds remaining in regulation at the selected event)
  - `possession` (categorical: `"home"`, `"away"`, `"unknown"`)
- **Disallowed at prediction time**:
  - `final_winning_team` (label)
  - any features computed from *final outcome* beyond the label
  - any features that require knowing whether overtime occurs (for regulation-time prediction)
- **Missing possession handling**:
  - `possession_side IS NULL` maps to `possession="unknown"` for both training and inference.
  - **Evidence**:
    - **File**: `db/migrations/014_pbp_event_state_possession_side_0_home_1_away.sql:1-6` (NULL=unknown definition)

#### 2) Create leak-proof season split at game level (test=2024–25)
Define:
- `season_start = 2000 + substring(game_id from 4 for 2)::int`
- **Train**: `season_start < 2024`
- **Test**: `season_start = 2024`
- **Forward-time smoke test only**: `season_start = 2025` (partial season)

Hard requirement: `INTERSECTION(train_game_ids, test_game_ids) = ∅`.
- **Evidence**: see “Success Metrics → Leakage”.

#### 3) Export a reproducible Parquet dataset without DB mutation
Create a dedicated dataset export that:
- reads from `derived.pbp_event_state` (or an existing exported Parquet),
- outputs only the required columns + manifest JSON including:
  - row count
  - distinct games
  - season range
  - possession missingness rate

Existing exporter precedent:
- **Evidence**:
  - **File**: `scripts/export_pbp_event_state_parquet.py:1-148` (chunked/streaming export)

### Short-term Improvements (Priority: Medium)

#### 4) Build preprocessing + training pipeline and save as an artifact

Define a single preprocessing+model pipeline that supports **training and live scoring** without any feature drift.

**Preprocessing pipeline (identical in train and inference)**:
- **Numeric**:
  - `point_differential`: standardize (mean 0, std 1) using train data statistics only.
  - `time_remaining_regulation`: standardize (mean 0, std 1) using train data statistics only.
- **Categorical**:
  - `possession`: one-hot encode categories `{"home","away","unknown"}` with `handle_unknown="ignore"` at inference to prevent runtime failure.

**Model**:
- **Regularized logistic regression** for \(P(\text{home wins})\), trained on train seasons only.

**Artifact**:
- Save the full pipeline (preprocessing + model + optional calibrator) as a single versioned artifact file.

#### 5) Evaluate on the held-out season with overall + time-bucketed metrics and explicit no-overlap checks

Evaluation protocol:
- **Test set**: season_start 2024 only.
- **Metrics**:
  - log loss
  - Brier score
  - ROC AUC
  - reliability / calibration curves (overall and per time bucket)
- **Time-bucketed reporting**:
  - by `bucket_seconds_remaining` (the snapshot anchor)
  - by `time_remaining_regulation` bucket intervals if anchors are dense
- **Leakage checks**:
  - Assert no overlap in `game_id` between train and test.
  - Assert `final_winning_team` constancy per `game_id`.
    - **Evidence**:
      - **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS games_with_inconsistent_label FROM (SELECT game_id FROM derived.pbp_event_state GROUP BY 1 HAVING COUNT(DISTINCT final_winning_team) > 1) x;"`
      - **Output**:
        ```
         games_with_inconsistent_label
        -------------------------------
                                   0
        (1 row)
        ```

#### 6) Calibrate probabilities if needed

Calibration requirement:
- Calibrate probabilities only using **pre-test** data.
- Calibration uses a **game-level split** (no shared games) and a **time-respecting split** (calibration season precedes test season).

Calibration protocol (deterministic):
- **Train**: seasons ≤ 2022
- **Calibration/validation**: season 2023
- **Test**: season 2024

Calibration methods:
- **Platt scaling** (sigmoid) or **isotonic regression**, selected by calibration-season log loss and calibration diagnostics.

The pipeline stores the chosen calibrator inside the same serialized artifact as the base classifier.

### Long-term Strategic Changes (Priority: Low)

#### 7) Build a simple live scoring interface

Define a single input contract and produce a stable output:
- **Inputs**: `(point_differential, time_remaining_regulation, possession)` where `possession ∈ {"home","away","unknown"}`
- **Outputs**:
  - `p_home_win`
  - `p_away_win = 1 - p_home_win`
  - model version id / artifact id
  - bucket label used for reporting

This interface is implemented as a CLI and as an importable function.

#### 8) Run a forward-time smoke test on the current partial season (no training on it)

Forward-time smoke test dataset:
- `season_start = 2025` games (partial 2025–26 season in the warehouse)
  - **Evidence**:
    - **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "WITH base AS (SELECT DISTINCT game_id, (2000 + substring(game_id from 4 for 2)::int) AS season_start FROM derived.pbp_event_state) SELECT COUNT(*) FILTER (WHERE season_start = 2025) AS games_season_2025 FROM base;"`
    - **Output**:
      ```
       games_season_2025
      -------------------
                     478
      (1 row)
      ```

Smoke test outputs:
- Overall metrics vs 2024 test season metrics
- Calibration drift by bucket
- Feature missingness drift by bucket (especially `possession="unknown"`)

#### 9) When ready, join model outputs to odds snapshots to compute implied probabilities and edge

Constraint:
- NBA odds feed in this repo is `odds_todaysGames` (today-only), stored as snapshots.
  - **Evidence**:
    - **File**: `scripts/fetch_odds_today.py:3-14` (explicit today-only snapshot feed)
    - **File**: `db/migrations/001_schema_v1.sql:136-145` (odds snapshot model)

Plan:
- Maintain a daily captured odds snapshot archive and/or load them into `odds_*` tables.
- Join model snapshots to odds snapshots by:
  - `game_id`
  - snapshot timestamp alignment rule defined explicitly (as-of join by `fetched_at` <= model scoring time).

Compute:
- **Implied probability** from odds for the selected market (e.g., moneyline), with a documented odds→probability conversion rule.
- **Edge** = `model_prob - implied_prob`.

#### 10) Define a paper-trading rule set and produce an auditable decision log before any real betting

Decision rule set requirements:
- Deterministic, parameterized, and versioned.
- Uses only:
  - model artifact id
  - input snapshot features
  - odds snapshot id and raw odds fields used
  - computed implied probabilities and edge

Decision log requirements:
- Immutable append-only log (JSONL or Parquet) containing:
  - timestamp (UTC)
  - game_id
  - bucket/time_remaining_regulation
  - model version / artifact hash
  - inputs
  - outputs
  - odds snapshot provenance (`source_file_id`, `snapshot_id`)
  - decision outcome (`bet/no_bet`, stake, side)
  - rationale fields (edge threshold, time bucket constraints)

## Implementation Plan

### Phase 0: Run Context and Safety (Read-only DB)

**Objective**: Record exact run context used for this analysis and ensure the work is read-only.

**Evidence (UTC time)**:
- **Command**: `date -u`
- **Output**:
  ```
  Sat Dec 20 23:35:53 UTC 2025
  ```

**Evidence (DB container running)**:
- **Command**: `cd /Users/adamvoliva/Code/bball && docker compose ps`
- **Output**:
  ```
  NAME             IMAGE         COMMAND                  SERVICE   CREATED      STATUS                 PORTS
  bball-postgres   postgres:16   "docker-entrypoint.s…"   db        6 days ago   Up 5 hours (healthy)   0.0.0.0:5433->5432/tcp
  ```

**Evidence (`.env` present; `DATABASE_URL` is available after sourcing without printing it)**:
- **Command**: `ls -la /Users/adamvoliva/Code/bball/env.example /Users/adamvoliva/Code/bball/.env || true`
- **Output**:
  ```
  -rw-r--r--@ 1 adamvoliva  staff  71 Dec 14 10:44 /Users/adamvoliva/Code/bball/.env
  -rw-r--r--@ 1 adamvoliva  staff  71 Dec 14 06:01 /Users/adamvoliva/Code/bball/env.example
  ```
- **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && python3 -c 'import os; print("DATABASE_URL_set_after_source=" + str(bool(os.getenv("DATABASE_URL"))))'`
- **Output**:
  ```
  DATABASE_URL_set_after_source=True
  ```

### Phase 1: Dataset Contract + Split Artifacts

**Objective**: Produce a single dataset contract and frozen train/test game lists.

**Deliverables**:
- `train_game_ids_season_lt_2024.txt`
- `test_game_ids_season_2024.txt`
- `forward_games_season_2025.txt`
- `dataset_contract.md` section embedded in this analysis (authoritative)

### Phase 2: Reproducible Parquet Export (No DB Mutation)

**Objective**: Export the modeling columns and a manifest with counts and season coverage.

**Deliverables**:
- `data/exports/winprob_modeling_events.parquet`
- `data/exports/winprob_modeling_events.manifest.json`

### Phase 3: Snapshot Sampling (Fixed Time Buckets)

**Objective**: Convert per-event data into fixed time buckets so each game contributes evenly.

**Deliverables**:
- `data/exports/winprob_snapshots.parquet`
- `data/exports/winprob_snapshots.manifest.json`

### Phase 4: Training + Calibration + Artifact

**Objective**: Train regularized logistic regression and save full pipeline artifact.

**Deliverables**:
- `artifacts/winprob_logreg_v1.json` (preprocessing + model weights + optional Platt calibration)

### Phase 5: Evaluation + Drift Smoke Test

**Objective**: Evaluate on 2024–25 and run forward-time drift checks on 2025–26 partial.

**Deliverables**:
- `data/reports/winprob_eval_2024.json`
- `data/reports/winprob_eval_2024.calibration.svg`
- `data/reports/winprob_drift_smoke_2025.json`
- `data/reports/winprob_drift_smoke_2025.calibration.svg`

### Phase 6: Odds Join + Paper Trading Audit Log

**Objective**: Compute implied probabilities and edge for days where odds snapshots exist, and produce an auditable decision log before any real betting.

**Deliverables**:
- `data/exports/winprob_with_odds_20251214.parquet` (day-scoped; only where odds snapshots exist)
- `data/exports/winprob_with_odds_20251214.parquet.manifest.json`
- `data/exports/paper_trades_20251214.jsonl` (append-only)

## Risk Assessment

### Technical Risks
- **Leakage risk**: incorrect split introduces invalid evaluation and calibration; mitigation is mandatory `game_id` overlap checks and season-based `game_id` split artifacts.
- **Possession missingness risk**: possession feature becomes a proxy for data quality; mitigation is explicit `"unknown"` category and reporting missingness drift by bucket.
- **Odds alignment risk**: as-of join errors yield incorrect implied probability comparisons; mitigation is explicit join rule and storing provenance ids.

### Business Risks
- **Decision risk**: uncalibrated probabilities can cause systematic overbetting; mitigation is calibration diagnostics and a paper-trading-only phase.


