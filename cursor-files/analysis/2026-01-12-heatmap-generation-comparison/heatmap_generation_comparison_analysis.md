# Heatmap Generation Comparison Analysis

**Date**: 2026-01-12  
**Purpose**: Compare heatmap generation between `analyze_grid_search_results.py` and the webapp endpoint to identify differences in data processing, color scaling, and visualization.

## Executive Summary

This analysis compares two methods of generating heatmaps for grid search results:
1. **Analysis Script** (`scripts/trade/analyze_grid_search_results.py`) - Generates PNG heatmaps using matplotlib
2. **Webapp Endpoint** (`webapp/api/endpoints/grid_search.py` + `webapp/static/js/grid-search.js`) - Generates interactive canvas heatmaps

**Key Finding**: After the recent fix removing `reindex()`, both methods now use the same pivot structure. However, there are still differences in:
- Color normalization logic (diverging vs linear)
- Y-axis orientation (frontend flips Y-axis)
- Missing value handling (matplotlib vs canvas rendering)

## Data Source Comparison

### Analysis Script
- **File**: `scripts/trade/analyze_grid_search_results.py`
- **Data Source**: CSV files (`grid_results_train.csv`, `grid_results_valid.csv`)
- **Loading Method**: `pd.read_csv(csv_path)` (line 36)

### Webapp Endpoint
- **File**: `webapp/api/endpoints/grid_search.py`
- **Data Source**: JSON files (`grid_results_train.json`, `grid_results_valid.json`)
- **Loading Method**: `json.load()` then `pd.DataFrame(results)` (lines 1101-1102)

**Evidence**: Both load the same underlying data (183 rows confirmed for train set). The CSV and JSON files contain identical result counts.

## Pivot Table Generation

### Analysis Script Method
```python
# Line 68: scripts/trade/analyze_grid_search_results.py
pivot = df.pivot(index='exit_threshold', columns='entry_threshold', values=value_col)
# Uses pivot.values directly in imshow (line 74)
im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
```

**Characteristics**:
- No explicit sorting of index/columns
- Uses pandas natural ordering from pivot
- Direct use of `pivot.values` (numpy array)

### Webapp Endpoint Method (After Fix)
```python
# Lines 895-906: webapp/api/endpoints/grid_search.py
pivot = df.pivot(index='exit_threshold', columns='entry_threshold', values=value_col)
pivot = pivot.sort_index(axis=0).sort_index(axis=1)  # Sort in-place
entry_thresholds = list(pivot.columns)
exit_thresholds = list(pivot.index)
matrix = [[None if pd.isna(val) else float(val) for val in row] for row in pivot.values]
```

**Characteristics**:
- Explicitly sorts index and columns using `sort_index()`
- Converts NaN to None for JSON serialization
- Converts to nested Python list (not numpy array)

**Difference**: The endpoint sorts the pivot, but this doesn't change the data values - only the ordering. Both methods produce the same matrix values.

## Matrix Value Comparison

### Raw Data Structure

**Analysis Script**:
- Matrix type: `numpy.ndarray` (from `pivot.values`)
- NaN handling: Preserved as `numpy.nan`
- Shape: `(num_exit_thresholds, num_entry_thresholds)`

**Webapp Endpoint**:
- Matrix type: `list[list[float|None]]` (nested Python lists)
- NaN handling: Converted to `None` (becomes `null` in JSON)
- Shape: `(num_exit_thresholds, num_entry_thresholds)` (same)

**Evidence**: Both methods use the same pivot structure after sorting. The only difference is:
- Analysis: `pivot.values` → numpy array with NaN
- Endpoint: `pivot.values` → Python list with None

The actual numeric values are identical.

## Color Scaling Comparison

### Analysis Script (Matplotlib)
```python
# Line 74: scripts/trade/analyze_grid_search_results.py
im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
```

**Matplotlib `imshow` behavior**:
- Automatically calculates min/max from the data array
- Excludes NaN values from min/max calculation
- Uses **linear normalization**: `normalized = (value - min) / (max - min)`
- Applies RdYlGn colormap to normalized values
- RdYlGn is a diverging colormap but matplotlib applies it linearly (not centered at zero)

**Color Scale**:
- Min value → Red (dark red for very low)
- Max value → Green (dark green for very high)
- Middle → Yellow
- Normalization: Linear from min to max

### Webapp Endpoint (JavaScript)
```javascript
// Lines 673-683: webapp/static/js/grid-search.js
let minVal = Infinity;
let maxVal = -Infinity;
matrix.forEach(row => {
    row.forEach(val => {
        if (val !== null && val !== undefined) {
            minVal = Math.min(minVal, val);
            maxVal = Math.max(maxVal, val);
        }
    });
});

// Lines 687-741: Custom normalization
function getRdYlGnColor(value, minVal, maxVal) {
    const range = maxVal - minVal;
    const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal));
    
    let normalized;
    if (minVal < 0 && maxVal > 0) {
        // Center around zero for diverging colormap
        normalized = (value + absMax) / (2 * absMax);
    } else {
        // All positive or all negative - use standard normalization
        normalized = (value - minVal) / range;
    }
    // ... color mapping
}
```

**JavaScript behavior**:
- Calculates min/max excluding null/undefined (same as matplotlib excludes NaN)
- **Diverging normalization** when values span zero: centers around zero
- **Linear normalization** when all positive or all negative
- Custom RGB interpolation for RdYlGn approximation

**Critical Difference**: 
- **Matplotlib**: Always uses linear normalization (min→max)
- **Frontend**: Uses diverging normalization (centered at zero) when values span zero

**Important**: Both methods use the **same min and max values** from the data:
- **Min**: -849.15 (both use this)
- **Max**: 9366.30 (both use this)
- **Range**: 10215.45 (max - min)

The difference is in the **normalization formula**, not the data range.

**Numeric Example** (using actual train data: min=-849.15, max=9366.30):

For a value of $2000:
- **Matplotlib** (linear): `normalized = (2000 - (-849.15)) / (9366.30 - (-849.15)) = 2849.15 / 10215.45 = 0.279`
- **Frontend** (diverging): `absMax = max(|-849.15|, |9366.30|) = 9366.30`, then `normalized = (2000 + 9366.30) / (2 * 9366.30) = 11366.30 / 18732.60 = 0.607`

For a value of $0:
- **Matplotlib** (linear): `normalized = (0 - (-849.15)) / 10215.45 = 849.15 / 10215.45 = 0.083`
- **Frontend** (diverging): `normalized = (0 + 9366.30) / 18732.60 = 9366.30 / 18732.60 = 0.500` (centered at zero!)

For a value of $5000:
- **Matplotlib** (linear): `normalized = (5000 - (-849.15)) / 10215.45 = 5849.15 / 10215.45 = 0.573`
- **Frontend** (diverging): `normalized = (5000 + 9366.30) / 18732.60 = 14366.30 / 18732.60 = 0.767`

**Key Point**: Both read the same data and calculate the same min/max. The frontend then uses a different normalization formula that centers around zero, causing the same numeric values to map to different colors.

**Result**: The same numeric values get mapped to different normalized values (0-1 range), which then map to different colors in the RdYlGn colormap. This is why the heatmaps look different!

## Y-Axis Orientation

### Analysis Script
```python
# Line 74: scripts/trade/analyze_grid_search_results.py
im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', origin='lower')
```

**Matplotlib `origin='lower'`**:
- First row (index 0) of matrix → Bottom of plot
- Last row (highest index) → Top of plot
- Y-axis: Lowest exit_threshold at bottom, highest at top

### Webapp Endpoint
```javascript
// Line 754: webapp/static/js/grid-search.js
ctx.fillRect(entryIdx * cellWidth, (exitThresh.length - 1 - exitIdx) * cellHeight, cellWidth, cellHeight);
```

**Canvas rendering**:
- `(exitThresh.length - 1 - exitIdx)` flips the Y-axis for canvas coordinates
- Canvas coordinate system: (0,0) is top-left, Y increases downward
- The flip compensates for this, resulting in correct visual orientation
- Y-axis: Lowest exit_threshold at bottom, highest at top (matches matplotlib)

**Result**: Both methods display the same visual orientation. The frontend's Y-axis flip is necessary to compensate for canvas's coordinate system, and the final result matches matplotlib's `origin='lower'` display.

## Missing Value Handling

### Analysis Script
- NaN values in `pivot.values` are handled by matplotlib
- Matplotlib's default behavior: NaN values are rendered as transparent or masked
- No explicit handling needed

### Webapp Endpoint
- NaN values converted to `None` (line 906)
- `None` becomes `null` in JSON
- Frontend renders `null` as gray (`#f0f0f0`) (line 750)

**Difference**: Missing combinations appear as gray cells in frontend, but may be transparent/masked in matplotlib.

## Summary of Differences

| Aspect | Analysis Script | Webapp Endpoint | Impact |
|--------|----------------|-----------------|--------|
| **Data Source** | CSV files | JSON files | None (same data) |
| **Pivot Sorting** | Natural order | Explicitly sorted | Visual ordering only |
| **Matrix Type** | numpy.ndarray | list[list] | None (same values) |
| **NaN Handling** | Preserved as NaN | Converted to None | Rendering difference |
| **Color Normalization** | Linear (min→max) | Diverging (centered at 0) | **Different colors** |
| **Y-Axis Orientation** | origin='lower' (low at bottom) | Flipped for canvas (low at bottom) | **Same visual result** |
| **Missing Values** | Transparent/masked | Gray (#f0f0f0) | Visual difference |

## Which Normalization is Better?

### For Profit/Loss Data: **Diverging Normalization (Frontend) is Better**

**Reasons**:
1. **Zero is a meaningful threshold**: Break-even is a critical business metric. Diverging normalization centers the colormap at zero, making it easy to distinguish:
   - **Losses** (negative values) → Red colors
   - **Break-even** (zero) → Yellow (middle of colormap)
   - **Profits** (positive values) → Green colors

2. **RdYlGn is designed as a diverging colormap**: The Red-Yellow-Green colormap is specifically designed for data that spans zero. Using it with diverging normalization uses it as intended.

3. **Better visual contrast**: With diverging normalization, small losses vs small profits are visually distinct, even if they're close to zero.

4. **Matches data semantics**: Profit/loss data has inherent meaning at zero - you want to know if a strategy is profitable or not, not just relative performance.

### For Consistency: **Linear Normalization (Matplotlib) Matches Analysis Script**

**Reasons**:
1. **Consistency with analysis script**: If the goal is to match the PNG outputs exactly, linear normalization is required.

2. **Simplicity**: Linear normalization is simpler and more intuitive for general use cases.

3. **Full range utilization**: Linear normalization uses the full colormap range from min to max, which can provide better granularity for very large ranges.

### Recommendation

**Use diverging normalization** for the frontend because:
- It's more appropriate for profit/loss data
- It better utilizes the RdYlGn colormap's design
- It provides clearer visual distinction between losses and profits
- Zero (break-even) is a critical threshold that should be visually emphasized

**However**, if consistency with the analysis script PNG outputs is the primary goal, then use linear normalization to match exactly.

## Recommendations

### Color Normalization: Keep Diverging (No Changes Needed)
**Decision**: Keep the current diverging normalization in the frontend.

**Reasoning**:
- Better for profit/loss data visualization
- Zero (break-even) is visually emphasized
- Better distinction between losses and profits
- RdYlGn colormap is used as intended

**Action Required**: None - current implementation is correct.

### Y-Axis Orientation: Correct (No Changes Needed)
**Decision**: Keep current Y-axis handling.

**Reasoning**:
- The frontend's Y-axis flip compensates for canvas coordinate system
- Final visual result matches matplotlib's `origin='lower'`
- Both display lowest exit_threshold at bottom, highest at top

**Action Required**: None - current implementation is correct.

### Summary
**No frontend changes needed** - the current implementation is appropriate for the data and produces correct visual results.

## Raw Data Statistics

### Train Set
- **Total results**: 183 data points
- **Unique entry thresholds**: 18 values (0.020 to 0.190)
- **Unique exit thresholds**: 11 values (0.000 to 0.050)
- **Expected matrix size**: 11 rows × 18 cols = 198 cells
- **Actual data points**: 183
- **Missing combinations**: 15 (7.6% of grid)

### Valid Set
- **Total results**: 183 data points
- **Unique entry thresholds**: 18 values (0.020 to 0.190)
- **Unique exit thresholds**: 11 values (0.000 to 0.050)
- **Expected matrix size**: 11 rows × 18 cols = 198 cells
- **Actual data points**: 183
- **Missing combinations**: 15 (7.6% of grid)

**Evidence**: Both train and valid sets have identical structure with 15 missing combinations. These missing combinations will appear as NaN in the pivot table, which become None/null in the frontend.

## Evidence Collection

To verify these findings, the following comparisons were made:
1. Code inspection of both methods (lines cited above)
2. Data structure analysis (pivot creation)
3. Color normalization logic comparison (code excerpts provided)
4. Y-axis rendering logic comparison (code excerpts provided)
5. Missing value handling comparison (code excerpts provided)
6. Raw data statistics (extracted from JSON files)

## Conclusion

The heatmaps differ primarily due to:
1. **Color normalization**: Frontend uses diverging (centered at zero), matplotlib uses linear
   - This is intentional and better for profit/loss data
   - No changes needed

2. **Y-axis orientation**: Both display correctly (frontend compensates for canvas coordinates)
   - Visual result matches matplotlib's `origin='lower'`
   - No changes needed

**Final Recommendation**: Keep current frontend implementation. The diverging normalization is better suited for profit/loss visualization, and the Y-axis orientation is correct. The underlying data values are identical after the recent fix removing `reindex()`.

