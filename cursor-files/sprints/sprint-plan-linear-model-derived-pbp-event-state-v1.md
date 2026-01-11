## Sprint Plan — Train + calibrate + evaluate a linear in-game win model from `derived.pbp_event_state`

### Audience
This document is written so that **someone with zero context of this repo** can execute each story end-to-end without outside help.

### Product goal (what “success” means)
Build a baseline that, given an in-game snapshot, outputs a **calibrated** probability:
- \(P(\text{away wins})\) where **away=1** per `final_winning_team`
- \(P(\text{home wins}) = 1 - P(\text{away wins})\)

The immediate goal is **model training + evaluation + calibration**. A later sprint can turn that into a betting policy.

### Hard constraints (must not violate)
- **No database mutations unless explicitly approved**: this sprint is read-only on Postgres (SELECTs only).
- **No game leakage**: a `game_id` must never appear in both train and test.
- **Time-respecting evaluation**: hold out the **last complete season** as the test set.

---

## Context: what data we’re using

### Source table
We model from `derived.pbp_event_state`, which contains one row per play-by-play event, with these columns:
- **Identifiers**: `game_id`, `event_id`
- **Features (v1)**: `point_differential`, `time_remaining`, `possession_side`
- **Label**: `final_winning_team`

Encoding rules (important):
- `point_differential` is **home − away**
- `time_remaining` is **seconds remaining in the game**, including overtime in some games
- `possession_side`: **0=home, 1=away, NULL=unknown**
- `final_winning_team`: **0=home won, 1=away won**, and is **constant per `game_id`**

### Known data caveats (observed)
- `possession_side` is NULL for a large fraction of rows (~38% in current DB state). We must decide a null-handling policy.
- `games.season` is not populated; and `games.game_time_utc` is missing for many older games. Therefore, **season splitting must be derived from `game_id`**, unless you explicitly choose to do a separate “backfill dates” project.

### Season derivation (authoritative for this sprint)
Define:
- `season_start = 2000 + substring(game_id from 4 for 2)::int`

Example:
- `0022400196` → `season_start = 2024` (the 2024–25 season)

“Last season” policy for this sprint:
- **Test set = season_start 2024** (2024–25)
- **Train set = all other seasons < 2024**
- **Exclude from model metrics**: partial 2025–26 (`season_start=2025`) unless explicitly requested as an additional forward-time report

---

## Epic 0 — Setup + reproducibility conventions (0.5 day)

### Story 0.1 — Confirm local environment + read-only DB connectivity
**Objective**
- Ensure you can connect to the warehouse and run SELECT queries safely.

**Steps**
- Start Postgres (if needed):

```bash
docker compose up -d db
```

- Create venv and install base deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

- Export `DATABASE_URL` (or set in `.env` and source it):

```bash
source .env
echo "$DATABASE_URL"
```

- Smoke-test read-only access (example query):

```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM derived.pbp_event_state;"
```

**Acceptance criteria**
- **AC1**: You can run a SELECT query via `psql` without errors.
- **AC2**: You understand and can state “no DB writes are allowed in this sprint”.

### Story 0.2 — Decide ML dependency strategy (scikit-learn vs statsmodels)
**Objective**
- Choose the training library and pin it so future results are reproducible.

**Decision options**
- **Option A: scikit-learn (recommended)**
  - Pros: mature pipelines (preprocessing + model + calibration), great metrics tooling, easiest packaging.
  - Cons: new dependency not currently in `requirements.txt`.
- **Option B: statsmodels**
  - Pros: fewer “ML infra” concepts; strong classical regression tooling.
  - Cons: calibration tooling and pipeline ergonomics are less turnkey.

**Acceptance criteria**
- **AC1**: A decision is recorded (in the experiment report) with the exact package version to use.
- **AC2**: The project has a single canonical command to install ML deps (e.g., an added `requirements-ml.txt`) *when you choose to implement code*.

---

## Epic 1 — Data inventory + extraction artifacts (read-only) (1 day)

### Story 1.1 — Produce a “dataset manifest” from read-only SQL
**Objective**
- Record the dataset’s shape, coverage, and missingness so results can be interpreted honestly.

**Example SQL (copy/paste)**

```sql
-- Basic coverage + missingness
WITH base AS (
  SELECT
    s.*,
    (2000 + substring(s.game_id from 4 for 2)::int) AS season_start
  FROM derived.pbp_event_state s
)
SELECT
  COUNT(*) AS rows_total,
  COUNT(DISTINCT game_id) AS games_total,
  MIN(season_start) AS min_season_start,
  MAX(season_start) AS max_season_start,
  COUNT(*) FILTER (WHERE possession_side IS NULL) AS rows_null_possession,
  COUNT(*) FILTER (WHERE final_winning_team IS NULL) AS rows_null_label
FROM base;
```

**Acceptance criteria**
- **AC1**: A saved manifest artifact exists (e.g., `data/reports/modeling_manifest.json`) including row counts, season range, and null rates.
- **AC2**: The manifest explicitly calls out that `possession_side` can be NULL and how frequently.

### Story 1.2 — Export the raw modeling table to Parquet (streaming)
**Objective**
- Create a local, immutable data artifact so training does not repeatedly hit Postgres.

**Use the existing exporter**
- Full export (can be large):

```bash
source .env
./.venv/bin/python scripts/export_pbp_event_state_parquet.py \
  --dsn "$DATABASE_URL" \
  --all \
  --out data/exports/pbp_event_state_all.parquet
```

**Acceptance criteria**
- **AC1**: `data/exports/pbp_event_state_all.parquet` exists and can be read by pandas.
- **AC2**: Export is repeatable and stable (same schema, same column names, deterministic ordering).

---

## Epic 2 — Split definition + leakage tests (0.5–1 day)

### Story 2.1 — Build train/test game lists by season (no mixed games)
**Objective**
- Create explicit `train_game_ids` and `test_game_ids` files so every experiment uses the same split.

**Split rule**
- **test**: `season_start == 2024`
- **train**: `season_start < 2024`

**Example pseudo-code**

```python
# read Parquet
df = read_parquet("data/exports/pbp_event_state_all.parquet")

df["season_start"] = 2000 + df["game_id"].str.slice(3, 5).astype(int)

test_games = sorted(df.loc[df["season_start"] == 2024, "game_id"].unique())
train_games = sorted(df.loc[df["season_start"] < 2024, "game_id"].unique())
```

**Acceptance criteria**
- **AC1**: Train/test are defined at **game level**, not row level.
- **AC2**: `set(train_games) ∩ set(test_games) == ∅` (asserted by code).
- **AC3**: Artifacts saved:
  - `data/exports/train_game_ids_2015_2023.txt`
  - `data/exports/test_game_ids_2024.txt`

### Story 2.2 — Confirm label constancy per game (sanity check)
**Objective**
- Verify that `final_winning_team` does not change within a game (it shouldn’t).

**Example SQL**

```sql
SELECT COUNT(*) AS games_with_inconsistent_label
FROM (
  SELECT game_id
  FROM derived.pbp_event_state
  GROUP BY 1
  HAVING COUNT(DISTINCT final_winning_team) > 1
) x;
```

**Acceptance criteria**
- **AC1**: `games_with_inconsistent_label = 0`
- **AC2**: If non-zero, the sprint stops and you investigate data correctness before modeling.

---

## Epic 3 — Row selection strategy (per-event vs snapshots) (1–2 days)

This is the most important technical choice because rows within a game are highly correlated.

### Story 3.1 — Implement “snapshot sampling” (recommended)
**Objective**
- Create a dataset where each game contributes a controlled number of rows so training/evaluation are interpretable.

**Default bucket proposal**
- Use a curated set emphasizing decision-relevant moments:
  - `[2880, 2400, 1800, 1200, 900, 600, 300, 120, 60, 30, 10, 0]`

**Selection rule**
- For each `(game_id, bucket_seconds)` choose the row whose `time_remaining` is **closest**, breaking ties deterministically (e.g., choose the highest `event_id`).

**Example pseudo-code**

```python
BUCKETS = [2880, 2400, 1800, 1200, 900, 600, 300, 120, 60, 30, 10, 0]

def pick_snapshots(game_df):
    out = []
    for b in BUCKETS:
        # compute absolute distance and pick deterministically
        tmp = game_df.assign(dist=(game_df["time_remaining"] - b).abs())
        row = tmp.sort_values(["dist", "event_id"], ascending=[True, False]).iloc[0]
        out.append(row)
    return pd.DataFrame(out)
```

**Acceptance criteria**
- **AC1**: Snapshot dataset has exactly `len(BUCKETS)` rows per game (unless you explicitly allow missing).
- **AC2**: Snapshot selection is deterministic (same input file ⇒ same output rows).
- **AC3**: You can compute metrics “by bucket” directly, because the dataset is aligned to bucket times.

### Story 3.2 — Decide how to handle `possession_side` NULLs (must be explicit)
**Objective**
- Ensure missing possession is handled consistently across train/test and at inference time.

**Option A: treat `possession_side` as categorical with “unknown”**
- Convert to strings: `"home"`, `"away"`, `"unknown"`.

**Option B: numeric with an “is_known” flag**
- `possession_side_filled`: map NULL → -1
- `possession_is_known`: 0/1

**Acceptance criteria**
- **AC1**: The chosen policy is recorded in the experiment report.
- **AC2**: The preprocessing pipeline enforces the same behavior in training and inference.

---

## Epic 4 — Baseline linear model training (1–2 days)

### Story 4.1 — Build a single training pipeline (preprocess + model)
**Objective**
- Ensure “train-time transforms” and “inference-time transforms” are identical.

**If using scikit-learn, recommended structure**
- `ColumnTransformer`:
  - numeric: `StandardScaler()` on `point_differential`, `time_remaining`
  - categorical: `OneHotEncoder(handle_unknown="ignore")` on `possession_side` (after filling NULL → `"unknown"`)
- classifier: `LogisticRegression(...)`

**Acceptance criteria**
- **AC1**: One serialized artifact can score raw inputs without additional code-level transforms.
- **AC2**: Feature schema is saved (names, encoder categories, expected dtypes).

### Story 4.2 — Train with group-safe validation
**Objective**
- Avoid within-game leakage during hyperparameter selection.

**Validation approach**
- Use `GroupKFold` with `groups=game_id` on the **train seasons**.

**Acceptance criteria**
- **AC1**: All CV splits respect `game_id` grouping.
- **AC2**: Hyperparameters are selected without touching test season 2024.

---

## Epic 5 — Calibration + thresholding + evaluation (1–2 days)

### Story 5.1 — Define calibration protocol (no peeking)
**Objective**
- Calibrate probabilities without leaking test information.

**Recommended split**
- train weights: seasons ≤ 2022
- calibrate: season 2023
- test: season 2024

If you do not have enough data in 2023 in your current export, adjust (but keep the rule: calibration must be pre-test).

**Acceptance criteria**
- **AC1**: Calibration fit uses only pre-test seasons.
- **AC2**: The calibration method and its parameters are saved alongside the model.

### Story 5.2 — Compute required metrics (ROC-AUC, F1) + calibration diagnostics
**Objective**
- Produce the exact metrics you requested, plus calibration views needed for betting use.

**Metrics**
- ROC-AUC on test season 2024
- F1 on test season 2024, using a threshold chosen on the calibration season (not test)
- Also report: log loss and Brier score (because calibration is a requirement)

**Time-bucket reporting**
- Report metrics by `time_remaining` bucket (because “late-game” will be much easier than “early-game”).

**Acceptance criteria**
- **AC1**: A single report artifact exists (markdown + JSON) containing:
  - split definition, counts, and leakage checks
  - ROC-AUC and F1
  - calibration curve and Brier score
  - per-bucket metrics table
- **AC2**: The report is reproducible from the same exported parquet + same code commit.

---

## Epic 6 — Inference interface (CLI) + forward-time smoke test (0.5–1.5 days)

### Story 6.1 — CLI to score a single snapshot
**Objective**
- Make it easy to use the model on live game state.

**Example CLI behavior**
- Input:
  - `point_differential`, `time_remaining`, `possession_side`
- Output:
  - `p_away_win`, `p_home_win`, bucket label, model version

**Acceptance criteria**
- **AC1**: You can score a single row from the terminal.
- **AC2**: The CLI validates inputs and handles unknown/missing `possession_side`.

### Story 6.2 — Forward-time smoke test on partial season 2025 (optional)
**Objective**
- Score `season_start=2025` games as a “future” check without training on them.

**Acceptance criteria**
- **AC1**: Scoring succeeds and produces probabilities.
- **AC2**: Any calibration drift is documented (even if we don’t fix it yet).

---

## Epic 7 (later) — Betting decision support (not in this sprint, but design for it)
We are not placing bets in this sprint, but we should structure artifacts to enable it:
- keep timestamped/seasoned evaluation
- keep calibrated probabilities
- keep time-bucket performance

---

## Deliverables checklist (“Definition of Done”)
- **D1**: Exported Parquet dataset for `derived.pbp_event_state` (read-only extraction).
- **D2**: Saved `train_game_ids` and `test_game_ids` split artifacts (no overlap).
- **D3**: Snapshot dataset (or explicit weighting strategy) with documented rationale.
- **D4**: Trained linear model artifact + preprocessing + calibration (if used).
- **D5**: Test report for season 2024 with ROC-AUC, F1, and calibration diagnostics.
- **D6**: CLI scorer for a single in-game snapshot.








