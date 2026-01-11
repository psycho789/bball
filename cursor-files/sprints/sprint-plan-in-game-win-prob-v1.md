## Sprint Plan — In-game win probability (linear baseline) → betting decision support

Last updated: 2025-12-20

### Goal (product definition)
Build an end-to-end baseline that, given a live NBA game’s current state, outputs a calibrated probability:
- \(P(\text{home wins})\), \(P(\text{away wins})\)

This is a foundation for *in-game betting* (later), not an execution engine on day 1.

### Hard constraints (must not violate)
- **No data leakage**: never split a game across train/test; no “future” features.
- **Time-based evaluation**: hold out the last complete season as a true test.
- **No database mutation unless explicitly requested**: read-only inspection and extraction are allowed; any materialization/backfill/migrations require explicit user approval.

### Inputs (source of truth)
Modeling rows come from `derived.pbp_event_state` joined to `games`:
- **Features (v1)**: `point_differential`, `time_remaining`, `possession_side`
- **Target**: `final_winning_team` (0=home, 1=away)
- **Split key**: `games.game_time_utc` → derived `season_start_year` (month >= 10 ⇒ year else year-1)

Observed (current DB, read-only checks):
- `derived.pbp_event_state`: **7,329,986 rows**, **14,134 games**
- Date range (via `games.game_time_utc` for included games): **2015-10-02 → 2025-12-14**
- Most recent season present is **2025–26 (partial)** ⇒ last *complete* season is **2024–25**
- `possession_side` missingness: **38.18%** of rows (must encode “unknown”)

### Core modeling decision: “per event” vs “snapshots”
`derived.pbp_event_state` is per-event; games contribute many highly-correlated rows.

Recommendation (v1): **snapshot sampling** [[memory:8239723]]
- Choose fixed time buckets (e.g., every 60 seconds, or curated late-game buckets).
- For each `(game_id, bucket)` select the closest event row.
- This prevents games with more events from dominating training and makes evaluation interpretable (“at 5:00 remaining…”).

Alternative: all events + per-game weights (acceptable later if we need more data density).

---

## Sprint 00 — Modeling “contract” + leakage-proof split (0.5–1 day)

### Story 0.1 — Define dataset contract (schema, semantics)
**What to write down (doc + code comments later):**
- Feature semantics and allowed transformations
- Target semantics (constant per game)
- Season computation from `game_time_utc`
- Null handling policy (`possession_side` → categorical with explicit `unknown`)

**Acceptance criteria**
- **AC1**: A single “dataset contract” section exists and is consistent across the codebase and docs.
- **AC2**: A reviewer can answer “what is one row?” and “what is known at prediction time?” without guessing.

### Story 0.2 — Define and freeze the train/test split policy
**Policy (requested):**
- **Test**: last complete season = **2024–25** (season_start_year=2024)
- **Train**: seasons **<= 2023**
- **Exclude from metrics**: partial 2025–26; optionally use as “live smoke test”

**Acceptance criteria**
- **AC1**: Split is defined only at `game_id` level (no row-level split).
- **AC2**: A reproducible `train_game_ids` / `test_game_ids` artifact is produced (file output).
- **AC3**: Automated check asserts `intersection(train_game_ids, test_game_ids) == ∅`.

---

## Sprint 01 — Read-only extraction + split artifacts (1–2 days)

### Story 1.1 — Extraction query + data export (read-only)
**What to build**
- A script (or notebook) that extracts only the needed columns:
  - `s.game_id, s.event_id, s.point_differential, s.time_remaining, s.possession_side, s.final_winning_team`
  - plus `g.game_time_utc` and computed `season_start_year`
- Output in Parquet for speed and type stability.

**Notes**
- Prefer exporting from DB via chunking (like `scripts/export_pbp_event_state_parquet.py`) to avoid memory blowups.
- Keep exports immutable and timestamped (or content-hashed) to make experiments reproducible.

**Acceptance criteria**
- **AC1**: Export completes end-to-end without DB writes.
- **AC2**: Export includes a manifest (row counts, distinct games, min/max dates).
- **AC3**: Export can be regenerated deterministically from the same DB state (same ordering + same schema).

### Story 1.2 — Snapshot sampling implementation
**What to build**
- A transform step that produces the modeling table used for training:
  - Either one row per bucket per game, or one row per game per fixed set of buckets.
- Emit the selected bucket times and the “closest row” logic used.

**Pros / cons** [[memory:8239723]]
- **Pros**: reduces within-game correlation; avoids overweighting; gives clean “by time” evaluation.
- **Cons**: choices of buckets affect metrics; need to document selection logic.

**Acceptance criteria**
- **AC1**: Snapshot dataset has bounded rows per game (≈ number of buckets).
- **AC2**: Snapshot selection is deterministic (same input → same selected event_id).

---

## Sprint 02 — Baseline linear model training (logistic regression) (1–2 days)

### Story 2.1 — Preprocessing pipeline (train-time and inference-time identical)
**What to build**
- A single preprocessing pipeline:
  - Numeric: standardize `point_differential`, `time_remaining`
  - Categorical: one-hot encode `possession_side` after imputing NULL → `"unknown"`

**Acceptance criteria**
- **AC1**: Preprocessing is packaged with the model artifact (no “train-time only” transforms).
- **AC2**: Feature schema is saved (column names, encoder categories).

### Story 2.2 — Train the logistic regression
**Algorithm** [[memory:8239723]]
- L2-regularized logistic regression (scikit-learn), solver LBFGS (default), modest hyperparameter grid over `C`.

**Complexity** [[memory:8239723]]
- Training is roughly \(O(N \cdot d)\) per solver iteration for dense features, where:
  - \(N\) = snapshot rows
  - \(d\) = number of encoded features

**Acceptance criteria**
- **AC1**: Model trains successfully on train seasons and produces probabilities.
- **AC2**: Outputs are stable across reruns given fixed random seeds and fixed data artifacts.

---

## Sprint 03 — Evaluation + calibration (1–2 days)

### Story 3.1 — “Realistic” evaluation report (season-held-out)
**What to build**
- Evaluate on test season 2024–25:
  - Log loss (primary)
  - Brier score
  - ROC AUC
  - Calibration curve (reliability plot)
- Add bucketed metrics by `time_remaining` (the main in-game betting lens).

**Acceptance criteria**
- **AC1**: Report explicitly states the split and confirms no game overlap.
- **AC2**: Metrics are reported overall + by time buckets.
- **AC3**: Artifacts saved: `metrics.json`, plots, and the exact `train/test game_id` lists.

### Story 3.2 — Calibration step (if needed)
If baseline is miscalibrated:
- Add Platt scaling or isotonic regression on a validation set (game-level split, time-respecting).

**Acceptance criteria**
- **AC1**: Calibration is fit only on pre-test data (no peeking at test).
- **AC2**: Calibration improvement is demonstrated on validation; test remains a final holdout.

---

## Sprint 04 — Live inference interface (1–3 days)

### Story 4.1 — Define “live row” input contract
**What to build**
- A tiny interface (function or CLI) that accepts:
  - `point_differential`, `time_remaining`, `possession_side`
  - outputs win probabilities + a confidence summary (e.g., time bucket)

**Acceptance criteria**
- **AC1**: One command can score a single snapshot (useful for manual sanity checks).
- **AC2**: Input validation matches training schema.

### Story 4.2 — “Live scoring” smoke test on partial 2025–26
Use the partial current season as a forward-time check:
- Score all games/events (or snapshots) without training on them.
- Inspect calibration drift.

**Acceptance criteria**
- **AC1**: No errors on unseen season values.
- **AC2**: Drift is quantified (metrics compared to test season) and documented.

---

## Sprint 05 — Betting decision support (paper trading) (2–5 days)

### Story 5.1 — Odds ingestion alignment (if/when available)
**What to build**
- Join model probability time series with odds snapshots (as-of join by timestamp) to compute:
  - market implied probability
  - model edge = model_prob - implied_prob

**Risks (honest)**
- Odds feed is “today-only” and snapshot-based; historical backtests may be limited.
- Timestamp alignment between live state and odds snapshot frequency matters a lot.

**Acceptance criteria**
- **AC1**: A dataset exists with `(game_id, timestamp, model_prob, implied_prob, edge)` for a sample day.
- **AC2**: No leakage: odds at time \(t\) only, game state at time \(t\) only.

### Story 5.2 — Paper trading rules (no money)
**What to build**
- A simple rule-based policy:
  - bet only in certain time buckets
  - require edge threshold and minimum liquidity/market constraints (if available)
  - limit max bets per game/day

**Acceptance criteria**
- **AC1**: Policy is deterministic and produces a trade log.
- **AC2**: Trade log includes enough context to debug each decision.

---

## Sprint 06 — Operationalization + monitoring (optional, ongoing)

### Story 6.1 — Model registry + reproducibility
- Track: dataset artifact id, split definition, model params, metrics, and code version.

### Story 6.2 — Monitoring
- Calibration drift over time buckets
- Feature missingness drift (especially `possession_side`)

---

## Open questions (decide before implementing Sprint 02+)
- **Time feature definition**: `time_remaining` currently includes OT in historical games; for *true live inference*, do we want regulation-only time remaining as the primary feature?
- **Bucket schedule**: do you want uniform 60s buckets, or a curated set emphasizing late game?
- **Dependency choice**: add `scikit-learn` (new pinned dependency) vs use `statsmodels` (less ML infra but different ergonomics).


