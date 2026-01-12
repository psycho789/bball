# API File Read Optimization

## Current State

- **CLI**: Writes results to JSON files (`final_selection.json`, `grid_results_{split}.json`)
- **API**: Uses in-memory cache (`SimpleCache`) - separate from CLI files
- **Problem**: If you run grid search via CLI, then via API, it re-runs instead of reading the files

## Proposed Solution

Add a check in the API to:
1. Look for CLI output files in common locations (e.g., `/tmp/grid_search_*`)
2. Match files based on parameters (cache key or parameter matching)
3. Read JSON files if found
4. Convert to API format (compute `pattern_detection` and `visualization_data`)
5. Only run grid search if files don't exist

## Format Compatibility

✅ **Compatible**:
- `final_selection.json` → `final_selection` (direct match)
- `grid_results_train.json` → `training_results` (extract `results` array, take top N)
- `grid_results_valid.json` → `validation_results` (extract `results` array)
- `grid_results_test.json` → `test_results` (extract `results` array)
- `metadata` → `metadata` (direct match)

⚠️ **Needs Computation**:
- `pattern_detection` - computed from results (can compute from loaded data)
- `visualization_data` - computed from results (can compute from loaded data)

## Implementation Approach

1. **File Discovery**: Search `/tmp/grid_search_*/` for matching parameters
2. **Parameter Matching**: Compare cache key or check file metadata
3. **File Reading**: Load JSON files and extract results
4. **Data Transformation**: Convert to API format, compute missing fields
5. **Cache Storage**: Store in API cache for future use

## Benefits

- **No Re-computation**: If CLI already ran, API just reads files (instant)
- **Shared Results**: CLI and API can share the same results
- **Backward Compatible**: Falls back to running grid search if files not found

## Challenges

- **File Location**: CLI uses user-specified `--output-dir`, API doesn't know where files are
- **Parameter Matching**: Need to match CLI parameters to API request
- **File Format**: Need to handle both old and new file formats

## Recommendation

**Option 1: Standard Location** (Simpler)
- CLI writes to standard location based on cache key: `/tmp/grid_search_{cache_key}/`
- API checks this location first
- Requires CLI changes to use standard location

**Option 2: Search Common Locations** (More Flexible)
- API searches `/tmp/grid_search_*/` for matching files
- Matches based on metadata in JSON files
- More flexible but slower (file system scan)

**Option 3: Hybrid** (Best)
- Check standard location first (fast path)
- If not found, search common locations (fallback)
- Cache results in API cache for future use

