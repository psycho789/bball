# Optimization: Pre-Compute Model Probabilities

## Problem

Currently, grid search with models is slow because:
1. For each game, we query features from the materialized view
2. For each snapshot in each game, we build the design matrix in Python
3. For each snapshot, we score the model (Logistic Regression or CatBoost + calibration)

**Result**: Grid search with models is much slower than ESPN-based grid search (which just reads `espn_home_prob` directly from the materialized view).

## Solution: Pre-Compute Model Probabilities

Pre-compute all 4 model probabilities and store them in a database table. Then grid search can query probabilities directly, just like ESPN probabilities.

### Architecture

1. **New Table**: `derived.model_probabilities_v1`
   - Stores pre-computed probabilities for all 4 models
   - Columns: `season_label`, `game_id`, `sequence_number`, `snapshot_ts`, `logreg_platt_prob`, `logreg_isotonic_prob`, `catboost_platt_prob`, `catboost_isotonic_prob`
   - Indexed on `(season_label, game_id, sequence_number, snapshot_ts)` for fast lookups

2. **Population Script**: `scripts/model/precompute_model_probabilities.py`
   - Loads all 4 model artifacts
   - Queries all snapshots from `derived.snapshot_features_v1`
   - Scores each snapshot with all 4 models
   - Writes results to `derived.model_probabilities_v1`

3. **Updated `get_aligned_data()`**: 
   - If `model_name` is provided, query pre-computed probability from `derived.model_probabilities_v1`
   - No on-the-fly scoring needed

### Performance Impact

**Before (Current)**:
- Grid search with models: ~30-60+ minutes per model (depends on dataset size)
- Each snapshot requires: feature extraction → design matrix → model scoring

**After (Optimized)**:
- Grid search with models: **Same speed as ESPN-based grid search** (~5-10 minutes)
- Each snapshot: Just read pre-computed probability from database

**Trade-offs**:
- ✅ **Pros**: Massive speedup (10x+ faster), consistent with ESPN approach
- ⚠️ **Cons**: Requires one-time pre-computation step (takes ~10-30 minutes), needs refresh when models change

### Implementation Steps

1. Create `derived.model_probabilities_v1` table
2. Create `scripts/model/precompute_model_probabilities.py` script
3. Run pre-computation script to populate table
4. Update `get_aligned_data()` to query pre-computed probabilities
5. Update materialized view refresh process to include model probability refresh

### When to Refresh

Refresh `derived.model_probabilities_v1` when:
- New games/snapshots added to `derived.snapshot_features_v1`
- Models are retrained (new model artifacts)
- Model features change (rare)

**Refresh Command**:
```bash
python3 scripts/model/precompute_model_probabilities.py --refresh
```

## Alternative: Batch Scoring Optimization

If pre-computation is not desired, we can optimize the current approach:

1. **Batch scoring**: Score multiple snapshots at once (vectorized operations)
2. **Cache model artifacts**: Load once per worker, not per game
3. **Parallelize model scoring**: Use numpy vectorization

**Performance**: ~2-3x faster, but still slower than pre-computation.

## Recommendation

**Use pre-computation** (`derived.model_probabilities_v1` table) because:
- Matches the existing architecture (materialized view pattern)
- Provides maximum speedup (10x+)
- Consistent with how ESPN probabilities are handled
- One-time cost for long-term benefit

