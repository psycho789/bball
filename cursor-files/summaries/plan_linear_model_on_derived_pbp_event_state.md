## Plan: linear in-game win classifier from `derived.pbp_event_state` (train/test split by season, no game leakage)

### Goal (what we’re building first)
Train a **linear classifier** that, at any event during a game, outputs a calibrated probability that the **away team wins** (per the table’s encoding), using only:
- **predictors**: `point_differential`, `time_remaining`, `possession_side`
- **target**: `final_winning_team` (0=home won, 1=away won)

This is the first building block toward **in-game betting** decisions (predicting the likely winner after a game has started).

### Constraints / non-goals (explicit)
- **No database writes**: extraction queries are **read-only**; no inserts/updates/deletes, no schema changes.
- **No train/test leakage across games**: **all rows for a given `game_id` must live in exactly one split**.
- **Primary split**: **test = last season**, **train = everything else** (as requested).
- **Model class**: linear (start with logistic regression); we’ll add calibration.

---

### What we know about the data (from read-only inspection)
Current `derived.pbp_event_state` columns (9 total):
- `game_id`, `event_id`, `point_differential`, `time_remaining`, `possession_side`, `home_score`, `away_score`, `current_winning_team`, `final_winning_team`

Scale / coverage:
- **~7,349,599 rows** across **~14,167 games**
- Seasons present (derived from `game_id`): **2015 → 2025**
- `time_remaining` range: **0 → 4080** seconds (includes regulation + overtime)

Missingness relevant to the requested feature set:
- `final_winning_team`: **0 NULL rows** (fully populated)
- `time_remaining`: **0 NULL rows**
- `possession_side`: **2,798,576 NULL rows** (~38% of events). When known it is roughly balanced:
  - `possession_side=0`: 2,275,720 rows
  - `possession_side=1`: 2,275,303 rows

Label balance (event-weighted, and game-weighted):
- `final_winning_team=0` (home win): **4,150,609 rows**, **8,026 games**
- `final_winning_team=1` (away win): **3,198,990 rows**, **6,141 games**

Important operational note:
- `games.season` is currently **NULL for all rows**, so **season splitting must not rely on `games.season`**.

---

### Split strategy (the “no mixed games” requirement)
We will split strictly by `game_id`, using a deterministic season identifier derived from `game_id`:
- `season_start = 2000 + substring(game_id from 4 for 2)::int`
  - Example: `0022400196` → `season_start = 2024` (i.e., 2024–25 season)

#### Primary split (as requested)
- **Test set**: `season_start = 2024` (the last complete season in this dataset)
- **Train set**: `season_start != 2024` (i.e., 2015–2023 plus the partial 2025 season if included)

#### Recommended evaluation hygiene (honest caveat)
Including the **partial current season (2025)** in training can be fine for producing a “best available” model, but it can also complicate interpretability of a “train on past, test on future” story.
So we’ll run both:
- **A (strict)**: train = 2015–2023, test = 2024
- **B (production-ish)**: train = 2015–2023 + 2025-to-date, test = 2024

#### Optional narrower scope (if you want “regular season only” first)
`game_id` prefixes suggest game types (e.g., many rows are prefix `002`, plus `001/004/...`).
If you want a cleaner first pass aligned to typical in-game betting markets:
- Filter to **`left(game_id, 3) = '002'`** (regular season games) for both train and test.
We’ll document which scope we used in results.

---

### Feature set & preprocessing
Requested predictors:
- `point_differential` (integer, home − away)
- `time_remaining` (seconds remaining in game)
- `possession_side` (0=home, 1=away, NULL=unknown)

#### Handling `possession_side` NULLs (must be decided up front)
We will compare two approaches (report both):
- **Drop NULL possession rows**:
  - Pros: simplest; no imputation assumptions.
  - Cons: discards ~38% of events; may bias toward certain game phases/event types.
- **Keep NULLs via explicit “unknown” encoding** (recommended):
  - Encode `possession_side` into two numeric inputs:
    - `possession_side_filled`: map NULL → -1 (or 0.5), keep 0/1 as-is
    - `possession_is_known`: 1 if not NULL else 0
  - Pros: preserves rows; lets model learn “unknown possession” behavior.
  - Cons: slightly more feature engineering; choice of fill value should be stable/explicit.

#### Scaling
For logistic regression, we’ll standardize continuous features:
- scale `point_differential` and `time_remaining` (e.g., `StandardScaler`)
- keep `possession_*` as-is

---

### Model choice (linear baseline)
Start with **logistic regression**:
- Regularization: L2 (default) and optionally L1 (sparser; helps interpretability)
- Solver: something stable for large datasets (e.g., `saga`)
- Class weights: start with none; optionally test `class_weight='balanced'` if metrics suggest benefit

Why this baseline fits the objective:
- It’s fast, interpretable, and usually a strong first step for “win probability from score + clock”.

---

### Calibration plan (required)
We need calibrated probabilities because this feeds a betting decision.

#### Don’t calibrate on the test set
Calibration must be fit on **held-out data not used for training weights**.

Recommended calibration split:
- **Train weights**: seasons 2015–2022
- **Calibration set**: season 2023
- **Test**: season 2024

Calibration methods to compare:
- **Platt scaling (sigmoid)**:
  - Pros: stable, low-variance, works well for linear models.
  - Cons: can underfit calibration if miscalibration is non-sigmoidal.
- **Isotonic regression**:
  - Pros: very flexible.
  - Cons: higher overfitting risk; needs lots of calibration data (we have plenty).

We’ll pick the method based on calibration diagnostics on the calibration season (not test):
- reliability diagram / calibration curve
- Brier score (secondary)

---

### Evaluation plan (F1 + ROC-AUC, and how we’ll report it honestly)
Required metrics (computed on **test season 2024**):
- **ROC-AUC** (threshold-free ranking quality)
- **F1** (thresholded; must define how threshold is chosen)

#### Threshold selection for F1
F1 depends on a decision threshold. We will:
- choose threshold that maximizes F1 on the **calibration** season (2023)
- then report F1 on **test** (2024) using that fixed threshold

#### Event-weighted vs game-weighted reporting (important for honesty)
Because each game contributes many events, computing metrics across all events can overweight games with more events/overtimes.
We’ll report:
- **Event-weighted** metrics (all rows)
- **Game-weighted** metrics via one of:
  - sample a fixed number of events per game (e.g., 50 uniformly over time), or
  - evaluate at fixed time buckets per game (e.g., every 60 seconds remaining)

#### “In-game usefulness” slices (recommended)
We’ll break metrics down by `time_remaining` buckets, because betting decisions happen at different phases:
- 0–120s, 120–300s, 300–600s, 600–1200s, 1200–2400s, 2400s+

---

### Data extraction (read-only) shape
We will extract a modeling dataframe with these columns:
- identifiers: `game_id`, `event_id`, `season_start`
- features: `point_differential`, `time_remaining`, `possession_side` (plus derived `possession_is_known` if we keep NULLs)
- label: `final_winning_team`

All splitting will be done **before** any per-row transforms that might leak across splits.

---

### Outputs / deliverables (what you’ll get)
- A repeatable training script/notebook that:
  - loads the dataset (read-only)
  - creates the season-based game-level split
  - trains logistic regression
  - calibrates on the calibration season
  - evaluates F1 + ROC-AUC on the test season
  - writes a small report artifact (metrics + calibration plots)
- A short results note answering:
  - “How good is it overall?”
  - “How good is it early vs late game?”
  - “Does possession help given its missingness?”

---

### Known limitations (so we don’t fool ourselves)
- This baseline ignores team strength, injuries, rest, and pregame priors; score/clock alone will look great late-game and weaker early-game.
- `possession_side` is missing for a large chunk of events; its impact may be smaller than expected unless missingness is handled explicitly.
- Event-level rows are not IID; they’re time-series within games. The split avoids cross-game leakage, but metrics should still be interpreted as “per-event” unless we game-weight them.








