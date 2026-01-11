## Plan: Linear classifier to predict game win/loss from in-game state

Last updated: 2025-12-20

### Goal (what we’re building)
Train a **linear classification model** that outputs a probability of **home vs away winning** given an in-game snapshot.

- **Target**: `final_winning_team` (0=home won, 1=away won, NULL=tied/unknown) from `derived.pbp_event_state`.
- **Predictors (v1)**: `point_differential`, `time_remaining`, `possession_side`.
- **Primary use case**: in-game betting / decisioning *after the game has started*—consume live game state and estimate who is likely to win.

Non-goals (for v1, intentionally):
- No team-strength priors, injuries, lineups, pace, or market odds features.
- No sequence model / deep model; keep it interpretable + fast.
- No “should we bet?” policy yet (that requires integrating odds and defining an edge/ROI objective).

### Data source and modeling dataset (what rows mean)
We will use `derived.pbp_event_state`, which is already materialized from `derived.game_state_by_event` and includes the needed columns:

- `point_differential`: integer **HOME − AWAY** at that event.
- `time_remaining`: integer seconds remaining in the **game**.
- `possession_side`: **0=home, 1=away, NULL=unknown**.
- `final_winning_team`: constant per `game_id` (0/1/NULL).

We must also attach a **game date** for splitting:
- Join to `games` on `game_id` and use `games.game_time_utc` as the canonical date/time.

### Reality check (what’s actually in the DB right now)
These are **observed** facts from `bball_warehouse` (read-only inspection):

- **Size**: `derived.pbp_event_state` has **7,329,986 rows** across **14,134 games**.
- **Date coverage** (from `games.game_time_utc` for games present in `derived.pbp_event_state`):
  - min: **2015-10-02**
  - max: **2025-12-14**
- **Seasons present** (derived from `games.game_time_utc`, using NBA season boundary month=Oct):
  - 2015–16 through 2024–25 are present
  - 2025–26 is present but **partial** (through 2025-12-14)
- **Predictor missingness**:
  - `possession_side` is NULL in **38.18%** of rows (we must encode “unknown” explicitly; dropping would throw away too much data).
  - `time_remaining` NULL rows: **0**
- **Target availability**:
  - `final_winning_team` NULL rows: **0**
  - Class balance at game level is modestly imbalanced (home wins more often than away).

Honesty check / caveats:
- `final_winning_team` can be NULL (ties/unknown); we should **drop those games** from training/evaluation in v1.
- `possession_side` can be NULL; we should represent it explicitly as “unknown” so the model can learn its effect instead of dropping rows.

### Leakage and “do not mix games” constraints
Key rule: **all events from a single `game_id` must go entirely to train or entirely to test**.

Reason (leakage):
- If we split by event rows, the model would see early events of a game during training and later events of that same game during testing. Since all rows share the same label (`final_winning_team`), this would artificially inflate performance.

Implementation pattern:
- **Group split by `game_id`**, where the group assignment is determined by the game’s date/season.

### Train/test split policy (what you requested)
We will do a **time-based split at the game level** and **never split a game across train/test**:

- **Test set**: the **last season** (most recent *complete* season in the data).
- **Train set**: all seasons **before** that season.

How we’ll determine “season” (we’ll use **date-based**, not `game_id` prefixes):
- Compute `season_start_year` from `games.game_time_utc` with the standard NBA convention: if month >= 10 then `year`, else `year - 1`.

Optional secondary split (for realism, later):
- A rolling “last 3 months” evaluation window (still game-level grouped), to simulate continuous deployment.

**Concretely for your current DB contents**:
- The most recent season in the data is **2025–26 (partial)**.
- Therefore **“last season” = 2024–25** (season_start_year = **2024**) is the correct held-out **test** season.
- We should **exclude** the partial 2025–26 season from train/test when reporting test metrics, because it is *after* the test period.
  - You can still use 2025–26 as a **“live scoring / smoke test”** set once the model is trained (this matches your betting use case).

### Modeling rows: avoid overweighting games with more events
`derived.pbp_event_state` is **per event**, so one game can contribute hundreds of rows. That can bias training/evaluation toward games with more events or more granular feeds.

Two viable approaches (choose one for v1):

1) **Snapshot sampling (recommended)**: create a fixed set of time buckets and choose one row per game per bucket.
   - Example buckets: every 60 seconds of `time_remaining`, or a curated set like `[2880, 2400, 1800, 1200, 900, 600, 300, 120, 60, 30]`.
   - For each game and bucket, select the event whose `time_remaining` is closest (or the latest event at/after that time).
   - Pros: each game contributes roughly equally; evaluation is easier to interpret (“accuracy at 5 minutes remaining”).
   - Cons: requires a little preprocessing logic.

2) **All events + per-game weighting**: keep all event rows but use sample weights.
   - Weight each row by \(1 / n\_\text{events in that game}\), so each game contributes total weight ~1.
   - Pros: simplest data prep.
   - Cons: calibration/metrics can still look “too good” if neighboring events are near-duplicates; snapshot sampling usually yields cleaner insight.

### Feature handling (v1)
Features:
- **`point_differential`**: numeric (int); keep as is, optionally standardize.
- **`time_remaining`**: numeric (int seconds); consider scaling (standardize) for numerical stability.
- **`possession_side`**: categorical with 3 states (home/away/unknown).

Encoding strategy:
- Use a scikit-learn `ColumnTransformer`:
  - Numeric: `StandardScaler(with_mean=True, with_std=True)`.
  - Categorical: `OneHotEncoder(handle_unknown="ignore")` after imputing NULL → `"unknown"`.

### Model choice (linear classifier)
Baseline: **Logistic Regression** (binary classification).

- **Algorithm**: L2-regularized logistic regression, optimizer typically **LBFGS** (scikit-learn default for many settings).
- **Why**: fast, stable, interpretable coefficients, good calibration baseline, easy to deploy.

Dependency note (honest):
- `scikit-learn` is **not currently pinned** in `requirements.txt`. When you’re ready to implement training in-repo, we’ll add a pinned version (or use `statsmodels` if you prefer fewer deps).

Alternative linear options (later, only if needed):
- Linear SVM (good separation, but probabilities need calibration).
- SGDClassifier (online-ish training; useful if dataset gets huge).

### Evaluation (what “good” means for in-game betting)
We’ll evaluate at two levels: overall and by time remaining.

Metrics:
- **Log loss** (primary; measures probabilistic quality).
- **ROC AUC** (secondary; ranking quality).
- **Brier score** + **calibration curve** (important for turning probabilities into decisions).
- **Accuracy** (easy to understand but can be misleading early in games).

By-time evaluation (high value for your use case):
- Compute metrics in buckets of `time_remaining` (e.g., 48–36, 36–24, 24–12, 12–6, 6–3, 3–1, last minute).
- This tells you where the model becomes “confident enough” for actionable edges.

Leakage checks (must-do):
- Confirm that **no `game_id` appears in both train and test**.
- Confirm that features are strictly in-game state at time t; do **not** include anything computed from the final score beyond the label.

### Training workflow (concrete, reproducible steps)
1) **Confirm the modeling table is current**
   - (No DB writes in this step.) Verify rowcounts/dates look sane and that `games.game_time_utc` is populated for games in `derived.pbp_event_state`.
   - When you later *choose* to refresh derived data, you’d run `scripts/materialize_pbp_event_state.py` (but this plan doc does not do it automatically).

2) **Build a modeling dataset**
   - Preferred input: `data/exports/pbp_event_state_all.parquet` (already supported by `scripts/export_pbp_event_state_parquet.py`).
   - Join game date from DB (`games.game_time_utc`) at dataset build time, and compute `season_start_year`.
   - Canonical extract (conceptually):
     - `SELECT s.game_id, s.event_id, s.point_differential, s.time_remaining, s.possession_side, s.final_winning_team, g.game_time_utc FROM derived.pbp_event_state s JOIN games g USING (game_id)`

3) **Create train/test splits**
   - Compute season from `game_time_utc`.
   - Assign `game_id` to train vs test based on season:
     - test: season_start_year = 2024 (2024–25)
     - train: season_start_year <= 2023
     - (optional) exclude 2025–26 from metrics; use it for “live scoring” only
   - Materialize two Parquet/CSV outputs for transparency and debugging (train/test game_id lists and snapshot rows).

4) **Train the logistic regression**
   - Fit preprocessing + model pipeline on train.
   - Tune only a small set of hyperparameters initially (e.g., `C` over a log grid).
   - Keep a single validation scheme initially (either train-only CV by game_id, or hold out the most recent pre-test season as validation).

5) **Evaluate on last-season test set**
   - Report overall + bucketed metrics.
   - Save artifacts: model, feature schema, metrics JSON, plots (calibration curve), and the exact split definition.

### “Live game” usage (how this becomes a betting input)
At inference time, for a live game we need:
- Latest `(point_differential, time_remaining, possession_side)` at “now”.
- Apply the same preprocessing and output \(P(\text{home wins})\) (and \(P(\text{away wins}) = 1 - P\)).

Decisioning (future step, but design for it now):
- Combine model probability with market odds to compute implied probabilities and “edge”.
- Only bet if edge exceeds a threshold and calibration is good in the relevant time bucket.

### Risks / limitations (honest)
- **This model will be strongly driven by score and time**. That’s not a bug; it’s the baseline. But it may add limited value vs a simple heuristic unless possession adds signal.
- **Per-event correlation** means naïve row-level metrics can look inflated; we address this with game-level splits and snapshot sampling/weights.
- **Data quality**: missing/incorrect `games.game_time_utc` or team ids can break season splits; we should validate.
- **Concept drift**: rules/pace/strategy changes by season; using last-season test helps quantify drift.

### Deliverables (what “done” looks like)
- A reproducible dataset build that:
  - Uses `derived.pbp_event_state` (+ `games.game_time_utc`)
  - Produces train/test splits with **no mixed games**
  - Uses features: `point_differential`, `time_remaining`, `possession_side`
  - Target: `final_winning_team`
- A trained logistic regression pipeline saved to disk.
- A metrics report (overall + time-bucketed) on the **last-season** test set.


