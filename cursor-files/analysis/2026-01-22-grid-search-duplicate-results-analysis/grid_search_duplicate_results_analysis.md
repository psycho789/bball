# Grid Search Duplicate Results Analysis

**Date**: 2026-01-22  
**Issue**: Duplicate entries for sprint models in grid search comparison with vastly different performance metrics  
**Status**: ✅ **ROOT CAUSE IDENTIFIED**

## Executive Summary

The `compare_grid_search_models.py` script is displaying **duplicate entries** for `catboost_baseline_sprint1` and `catboost_odds_sprint1` because grid searches were run on **two different seasons**:

1. **2025-26 season** (505 games total, 353 train games) → **Good results** ($1,400-$1,800 profit)
2. **2024-25 season** (84 games total, 58 train games) → **Poor results** ($86-$105 profit)

The comparison script correctly loads all results but doesn't filter by season, causing both sets to appear in the comparison table.

## Complete Results Inventory

### All Models by Season

**2025-26 Season (505 games, 353 train games):**
- ✅ ESPN (default): $1,942.84 profit, 332 trades
- ✅ catboost_platt: $1,899.70 profit, 367 trades
- ✅ catboost_isotonic: $1,826.54 profit, 321 trades
- ✅ catboost_baseline_sprint1: $1,787.42 profit, 350 trades
- ✅ catboost_odds_sprint1: $1,439.01 profit, 316 trades
- ✅ logreg_platt: $1,411.99 profit, 327 trades
- ✅ logreg_isotonic: $1,220.86 profit, 331 trades

**2024-25 Season (84 games, 58 train games):**
- ⚠️ catboost_baseline_sprint1: $86.42 profit, 32 trades
- ⚠️ catboost_odds_sprint1: $104.86 profit, 60 trades
- ⚠️ ESPN (default): $0.00 profit, 0 trades (no valid results)

### Evidence

### Sprint Model Results Comparison

#### catboost_baseline_sprint1

**Result 1 (2025-26 season - GOOD):**
- Season: `2025-26`
- Test Profit: **$1,787.42**
- Test Trades: **350**
- Train Trades: **1,599**
- Games: train=353, valid=75, test=77
- Timestamp: 2026-01-22T14:20:43
- Cache Key: `6807fe4cbb0a77737f53acdab26f0aa6fc81d9171c406947d520d7bbbe3ef9c6`

**Result 2 (2024-25 season - POOR):**
- Season: `2024-25`
- Test Profit: **$86.42**
- Test Trades: **32**
- Train Trades: **197**
- Games: train=58, valid=12, test=14
- Timestamp: 2026-01-22T13:31:47
- Cache Key: `a3153b42bad684a2f54c253dcc8a9a5811579287f312ab47859f4995a3ce78ba`

#### catboost_odds_sprint1

**Result 1 (2025-26 season - GOOD):**
- Season: `2025-26`
- Test Profit: **$1,439.01**
- Test Trades: **316**
- Train Trades: **1,383**
- Games: train=353, valid=75, test=77
- Timestamp: 2026-01-22T14:43:08
- Cache Key: `1e4d2c9303224bf96b3de1c22f0fbedffd689b6b02e68f1a9e432288cdb8da15`

**Result 2 (2024-25 season - POOR):**
- Season: `unknown` (metadata shows 58 train games, consistent with 2024-25)
- Test Profit: **$104.86**
- Test Trades: **60**
- Train Trades: **354**
- Games: train=58, valid=12, test=14
- Timestamp: 2026-01-22T13:44:14
- **Note**: Season not explicitly set in metadata, but game counts match 2024-25 pattern

### Data Volume Comparison

| Season | Total Games | Train Games | Train Trades (Baseline) | Train Trades (Odds) | Test Profit (Baseline) | Test Profit (Odds) |
|--------|-------------|-------------|-------------------------|---------------------|------------------------|---------------------|
| **2025-26** | 505 | 353 | 1,599 | 1,383 | **$1,787.42** | **$1,439.01** |
| **2024-25** | 84 | 58 | 197 | 354 | **$86.42** | **$104.86** |
| **Ratio** | 6.0x | 6.1x | 8.1x | 3.9x | 20.7x | 13.7x |

**Key Insight**: The 2025-26 season has **6x more games** and **8x more train trades**, leading to **13-20x better test profits**.

## Root Cause Analysis

### Why Duplicates Exist

1. **Initial Grid Searches (2024-25 season)**
   - Sprint models were initially evaluated on `2024-25` season
   - This season has limited data: only 84 games with Kalshi data
   - Results were poor due to insufficient training data (58 train games, ~200-350 train trades)

2. **Updated Grid Searches (2025-26 season)**
   - After identifying the season discrepancy, grid searches were re-run on `2025-26` season
   - This season has much more data: 505 games with Kalshi data
   - Results are significantly better (353 train games, ~1,400-1,600 train trades)

3. **Comparison Script Behavior**
   - `compare_grid_search_models.py` scans **all** directories in `data/grid_search/`
   - It doesn't filter by season or deduplicate by model_name
   - Both sets of results appear in the comparison table

### Why Results Differ So Much

**2024-25 Season Issues:**
- **Insufficient training data**: Only 58 train games (vs 353 for 2025-26)
- **Fewer trades**: ~200-350 train trades (vs ~1,400-1,600 for 2025-26)
- **Limited test data**: Only 14 test games (vs 77 for 2025-26)
- **Higher variance**: Small sample sizes lead to unstable metrics

**2025-26 Season Advantages:**
- **Adequate training data**: 353 train games (6x more)
- **More trades**: ~1,400-1,600 train trades (4-8x more)
- **Better test coverage**: 77 test games (5.5x more)
- **More stable metrics**: Larger sample sizes reduce variance

## Impact Assessment

### Current State

- ✅ **Good results exist**: 2025-26 season results show competitive performance
- ⚠️ **Confusion in comparison**: Duplicate entries make it unclear which results to trust
- ⚠️ **Misleading metrics**: Poor 2024-25 results drag down average/ranking

### Comparison Table Issues

The comparison table shows:
1. Sprint models appear twice (once for each season)
2. The 2024-25 results are ranked lower (lines 729-730)
3. The 2025-26 results are ranked higher (lines 725-726)
4. No indication which season each result represents

## Recommendations

### Immediate Actions

1. **Filter to 2025-26 Season Only** (RECOMMENDED)
   - Update `compare_grid_search_models.py` to filter results by season
   - Only show results from `2025-26` season (or most recent season)
   - This ensures fair comparison across all models

2. **Add Season Column to Comparison Table**
   - Update `compare_grid_search_models.py` to display season in the comparison table
   - This makes it clear which results are from which season
   - Allows users to see both sets if needed

3. **Archive or Exclude 2024-25 Results**
   - Option A: Move 2024-25 season results to an archive directory
   - Option B: Add `--season-filter` argument to comparison script
   - Option C: Filter to most recent results per model (by timestamp)

### Implementation Example

```python
# In compare_grid_search_models.py, add season filtering:

def load_result_data(result_dir: Path, season_filter: Optional[str] = None) -> Optional[dict[str, Any]]:
    # ... existing code ...
    
    # Extract season from metadata
    args = metadata.get('args', {})
    season = args.get('season')
    
    # Filter by season if specified
    if season_filter and season != season_filter:
        return None
    
    # ... rest of function ...
```

Or add season column to table:

```python
def print_comparison_table(results: list[dict[str, Any]]) -> None:
    print(f"{'Model':<25} {'Season':<10} {'Test Profit':<15} {'Trades':<10} ...")
    # ... rest of function ...
```

### Long-Term Improvements

1. **Standardize Evaluation Season**
   - Document which season should be used for grid searches
   - Update `FRONTEND_SETUP_COMMANDS.md` to specify season explicitly

2. **Add Validation to Comparison Script**
   - Warn if duplicate model_name entries are found
   - Suggest filtering by season or timestamp

3. **Improve Metadata**
   - Ensure all grid search results include season in metadata
   - Add validation to prevent running grid searches on wrong season

## Code References

### Comparison Script
- **File**: `scripts/trade/compare_grid_search_models.py`
- **Function**: `load_result_data()` (lines 22-63)
- **Issue**: No filtering by season or deduplication by model_name

### Grid Search Script
- **File**: `scripts/trade/grid_search_hyperparameters.py`
- **Function**: `get_game_ids_from_season()` (lines 211-240)
- **Behavior**: Correctly filters by season, but results are stored separately

### Cache Key Generation
- **File**: `webapp/api/endpoints/grid_search.py`
- **Function**: `_generate_grid_search_cache_key()`
- **Behavior**: Cache key includes season, so results are correctly separated

## SQL Queries for Verification

### Count Games by Season

```sql
-- 2025-26 season games with Kalshi data
WITH kalshi_games AS MATERIALIZED (
    SELECT DISTINCT km.espn_event_id
    FROM kalshi.markets km
    WHERE km.espn_event_id IS NOT NULL
)
SELECT COUNT(DISTINCT p.game_id) AS total_games
FROM espn.probabilities_raw_items p
JOIN kalshi_games kg ON kg.espn_event_id = p.game_id
WHERE p.season_label = '2025-26'
GROUP BY p.game_id
HAVING COUNT(*) > 100;
-- Expected: ~505 games

-- 2024-25 season games with Kalshi data
WITH kalshi_games AS MATERIALIZED (
    SELECT DISTINCT km.espn_event_id
    FROM kalshi.markets km
    WHERE km.espn_event_id IS NOT NULL
)
SELECT COUNT(DISTINCT p.game_id) AS total_games
FROM espn.probabilities_raw_items p
JOIN kalshi_games kg ON kg.espn_event_id = p.game_id
WHERE p.season_label = '2024-25'
GROUP BY p.game_id
HAVING COUNT(*) > 100;
-- Expected: ~84 games
```

## Conclusion

The duplicate entries are **expected behavior** - they represent valid grid search results from different seasons. The comparison script correctly loads all results but doesn't distinguish between seasons, causing confusion.

**The 2025-26 season results are the correct ones to use** for comparison with other models, as they:
1. Use the same evaluation season as older models (2025-26)
2. Have sufficient training data (353 train games)
3. Show competitive performance ($1,400-$1,800 profit)
4. Match the data volume used by other models

**The 2024-25 season results should be ignored** because:
1. Insufficient training data (only 58 train games)
2. Small test set (only 14 test games)
3. Not comparable to other models (which use 2025-26)

## Action Items

### Priority 1: Fix Comparison Script

**Update `scripts/trade/compare_grid_search_models.py`:**

1. **Add season filtering** (recommended):
   ```python
   def load_result_data(result_dir: Path, season_filter: Optional[str] = "2025-26") -> Optional[dict[str, Any]]:
       # ... existing code ...
       season = args.get('season')
       if season_filter and season != season_filter:
           return None  # Skip results from other seasons
   ```

2. **OR add season column to table**:
   ```python
   print(f"{'Model':<25} {'Season':<10} {'Test Profit':<15} ...")
   # In loop:
   season = result['metadata'].get('args', {}).get('season', 'unknown')
   print(f"{model_name:<25} {season:<10} {profit:<15} ...")
   ```

3. **OR deduplicate by model_name + season**:
   ```python
   # Group by (model_name, season) and keep most recent
   seen = {}
   for result in results:
       key = (result['model_name'], result['metadata'].get('args', {}).get('season'))
       if key not in seen or result['timestamp'] > seen[key]['timestamp']:
           seen[key] = result
   ```

### Priority 2: Document Standard Season

Update `FRONTEND_SETUP_COMMANDS.md` to explicitly state:
- Grid searches should be run on **2025-26 season** for fair comparison
- This matches the evaluation season used by all models

### Priority 3: Archive Old Results (Optional)

Move 2024-25 season results to archive:
```bash
mkdir -p data/grid_search/archive_2024-25
# Move directories with 58 train games
```

## Verification

After implementing fixes, verify:
1. ✅ Only one entry per model in comparison table
2. ✅ All results show season = "2025-26"
3. ✅ Sprint models show competitive performance ($1,400-$1,800)
4. ✅ No duplicate model names in output
