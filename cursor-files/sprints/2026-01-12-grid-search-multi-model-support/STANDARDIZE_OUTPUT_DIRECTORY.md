# Standardize Grid Search Output Directory

## Current State

- **CLI**: Default is `grid_search_results` (relative to current directory)
- **API**: Uses `/tmp` (hardcoded, not used)
- **Problem**: No standardized location, files scattered, not persistent

## Proposed Solution

### Standard Location: `data/grid_search/`

Create a standardized directory structure:

```
data/grid_search/
├── {cache_key}/                    # One directory per unique parameter set
│   ├── final_selection.json
│   ├── grid_results_train.json
│   ├── grid_results_valid.json
│   ├── grid_results_test.json
│   ├── grid_results_train.csv
│   ├── grid_results_valid.csv
│   ├── grid_results_test.csv
│   ├── train_games.json
│   ├── valid_games.json
│   ├── test_games.json
│   └── plots/
│       └── ...
```

### Benefits

1. **Persistent**: In project directory, not `/tmp`
2. **Organized**: One directory per parameter set (cache key)
3. **Discoverable**: Easy to find results
4. **Shareable**: CLI and API can both read/write same location
5. **Version Controlled**: Can add to `.gitignore` if needed

### Implementation

1. **CLI Changes**:
   - Default: `data/grid_search/{cache_key}/`
   - Still allow `--output-dir` override
   - Create directory if doesn't exist

2. **API Changes**:
   - Check `data/grid_search/{cache_key}/` for existing results
   - Read files if found (instant return)
   - Write results to same location after completion
   - Fall back to running grid search if files not found

3. **Cache Key as Directory Name**:
   - Use same cache key generation logic
   - Creates unique directory per parameter combination
   - Easy to match CLI and API requests

### Migration

- **Existing files**: Leave in current locations (`grid_search_results/`, `/tmp/`)
- **New runs**: Use `data/grid_search/{cache_key}/`
- **Backward compatible**: Still support `--output-dir` override

### Example

```bash
# CLI run
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  ...
# Creates: data/grid_search/grid_search_abc123.../

# API request with same parameters
# Finds: data/grid_search/grid_search_abc123.../
# Returns: Instant results (no re-computation)
```

