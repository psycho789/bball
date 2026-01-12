# Standardized Output Directory - Complete ✅

## What Was Done

Standardized grid search output to use `data/grid_search/{cache_key}/` instead of `/tmp` or scattered locations.

## Changes Made

### 1. CLI Script (`scripts/trade/grid_search_hyperparameters.py`)
- **Default output**: Now uses `data/grid_search/{cache_key}/` when cache key is available
- **Fallback**: Uses `grid_search_results/` if no cache key (backward compatible)
- **Override**: Still supports `--output-dir` to specify custom location
- **Cache key**: Generated early to determine output directory

### 2. API Endpoint (`webapp/api/endpoints/grid_search.py`)
- **File check**: Checks `data/grid_search/{cache_key}/` for existing results before running
- **File reading**: Loads JSON files if found (instant return, no re-computation)
- **File writing**: Saves results to `data/grid_search/{cache_key}/` after completion
- **Format conversion**: Converts file format to API format (computes `pattern_detection` and `visualization_data`)

### 3. `.gitignore`
- Added `data/grid_search/` (though `data/` is already ignored)

## Directory Structure

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

## Benefits

1. **Persistent**: In project directory, not `/tmp` (survives reboots)
2. **Organized**: One directory per parameter set (cache key)
3. **Discoverable**: Easy to find results
4. **Shareable**: CLI and API both read/write same location
5. **Fast**: API can return instant results if CLI already ran

## Usage

### CLI (Automatic)
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --model-name logreg_platt \
  ...
# Automatically creates: data/grid_search/grid_search_abc123.../
```

### CLI (Override)
```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --output-dir /custom/path \
  ...
# Uses custom location
```

### API (Automatic)
- Checks `data/grid_search/{cache_key}/` first
- Returns instant results if files exist
- Runs grid search if files not found
- Saves results to same location after completion

## Workflow

1. **Run via CLI**: Creates `data/grid_search/{cache_key}/` with results
2. **Run via API**: Finds existing files, returns instantly (no re-computation)
3. **Both share**: Same location, same format, no duplication

## Backward Compatibility

- Old `grid_search_results/` directory still works (fallback)
- `--output-dir` override still works
- Existing files in `/tmp` or other locations are not affected

