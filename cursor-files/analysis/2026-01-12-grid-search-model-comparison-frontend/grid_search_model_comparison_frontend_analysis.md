# Analysis: Grid Search Model Comparison Frontend

**Date**: Mon Jan 12 06:47:59 PST 2026  
**Status**: Draft  
**Author**: System Analysis  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Comprehensive analysis and design plan for a frontend page that compares multiple grid search results (ESPN + 4 ML models) side-by-side with visualizations, metrics, and export functionality

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (code refs, file structure, existing patterns)
- **Run Context**: Based on existing grid search results in `data/grid_search/` and comparison data in `data/grid_search/model_comparison.json`
- **File Verification**: All referenced files verified and examined
- **Design Patterns**: Document design patterns used in existing codebase

## Executive Summary

### Key Findings
- **Existing Infrastructure**: Grid search page (`grid-search.html`) shows individual results with heatmaps, charts, and tables
- **Export System**: HTML export via `/api/export/html` saves to `docs/` for GitHub Pages; image export uses `html2canvas`
- **Comparison Data**: `scripts/trade/compare_grid_search_models.py` generates `data/grid_search/model_comparison.json` with all metrics
- **Pattern Consistency**: Model comparison page (`model-comparison.html`) provides pattern for side-by-side comparisons

### Critical Issues Identified
- **No Multi-Model Grid Search View**: Currently only individual grid search results can be viewed
- **No Unified Comparison**: Users must manually compare results across different grid search runs
- **Missing Visual Comparison**: Heatmaps and charts cannot be compared side-by-side

### Recommended Actions
- **[Action 1]**: [Priority: High] - Create new route and template for grid search model comparison page
- **[Action 2]**: [Priority: High] - Build API endpoint to serve comparison data and visualization data
- **[Action 3]**: [Priority: Medium] - Implement side-by-side heatmap comparison UI
- **[Action 4]**: [Priority: Medium] - Add export HTML and export image functionality
- **[Action 5]**: [Priority: Low] - Add interactive filtering and sorting capabilities

### Success Metrics
- **User Experience**: Users can compare all 5 models (ESPN + 4 ML) in a single view
- **Visualization Quality**: Heatmaps and charts render correctly side-by-side
- **Export Functionality**: HTML and image exports work correctly
- **Performance**: Page loads and renders within 2 seconds

## Problem Statement

### Current Situation

**Existing Grid Search Page** (`webapp/static/templates/grid-search.html`):
- Shows results for a **single** grid search run
- Displays:
  - Final selection summary (entry/exit thresholds, profits)
  - Pattern detection summary
  - Visualizations:
    - Profit heatmap (training set)
    - Profit heatmap (validation set)
    - Profit factor heatmap (validation set)
    - Marginal effects chart
    - Tradeoff scatter plot (trade frequency vs profitability)
  - Results tables (training results top N)
- Export functionality: Export image button (uses `html2canvas`)

**Comparison Script** (`scripts/trade/compare_grid_search_models.py`):
- Generates `data/grid_search/model_comparison.json` with:
  - Model names
  - Test/valid/train metrics for each model
  - Chosen parameters (entry/exit thresholds)
  - Timestamps
- Provides console output with comparison tables
- **No frontend integration**

**Model Comparison Page** (`webapp/static/templates/model-comparison.html`):
- Shows win probability model comparison (2×2 matrix)
- Displays metrics table and calibration chart
- Has export HTML and export image buttons
- **Different use case** (win probability models, not grid search results)

### Pain Points
- **No Unified View**: Users must run 5 separate grid searches and manually compare results
- **No Visual Comparison**: Cannot see heatmaps side-by-side to identify patterns
- **No Metrics Comparison**: Must manually extract metrics from individual result pages
- **No Export**: Cannot export comparison view for sharing or documentation
- **Inefficient Workflow**: Requires multiple page navigations to compare models

### Business Impact
- **User Experience Impact**: Difficult to identify best performing model and optimal thresholds
- **Decision Making Impact**: Cannot easily compare trade-offs between models
- **Documentation Impact**: No way to create shareable comparison reports
- **Time Impact**: Manual comparison is time-consuming and error-prone

### Success Criteria
- **[Criterion 1]**: Single page showing all 5 models (ESPN + 4 ML) side-by-side
- **[Criterion 2]**: Side-by-side heatmap comparison (all models on same scale)
- **[Criterion 3]**: Unified metrics table with improvement percentages
- **[Criterion 4]**: Export HTML functionality (saves to `docs/grid-search-comparison.html`)
- **[Criterion 5]**: Export image functionality (captures entire comparison view)
- **[Criterion 6]**: Page loads comparison data from API endpoint
- **[Criterion 7]**: Visualizations render correctly for all models

## Current State Analysis

### System Architecture Overview

**File Structure**:
```
webapp/
├── static/
│   ├── templates/
│   │   ├── grid-search.html          # Individual grid search results
│   │   └── model-comparison.html     # Win probability model comparison
│   ├── js/
│   │   ├── grid-search.js            # Grid search page logic
│   │   ├── model-comparison.js       # Model comparison page logic
│   │   └── export-utils.js          # Shared export utilities
│   └── css/
│       └── styles.css                # Shared styles
├── api/
│   └── endpoints/
│       ├── grid_search.py            # Grid search API endpoints
│       └── export.py                 # HTML export endpoint
data/
└── grid_search/
    ├── {cache_key_1}/                # ESPN results
    ├── {cache_key_2}/                # logreg_platt results
    ├── {cache_key_3}/                # logreg_isotonic results
    ├── {cache_key_4}/                # catboost_platt results
    ├── {cache_key_5}/                # catboost_isotonic results
    └── model_comparison.json          # Comparison data (generated by script)
```

**Data Flow**:
1. Grid search runs → Results saved to `data/grid_search/{cache_key}/`
2. Comparison script runs → Generates `model_comparison.json`
3. Frontend loads → Fetches comparison data from API
4. Frontend renders → Displays side-by-side comparisons
5. User exports → HTML saved to `docs/`, image downloaded

### Code Quality Assessment

**Existing Grid Search Page** (`grid-search.js`):
- **Lines of Code**: ~1,136 lines
- **Key Functions**:
  - `renderGridSearchResults()`: Renders single result set
  - `renderVisualizations()`: Renders heatmaps and charts
  - `renderProfitHeatmap()`: Custom canvas-based heatmap rendering
  - `exportGridSearchToImage()`: Image export using html2canvas
- **Visualization Libraries**: Custom canvas rendering (no Chart.js for heatmaps)
- **Export**: Image export only (no HTML export)

**Model Comparison Page** (`model-comparison.js`):
- **Lines of Code**: ~475 lines
- **Key Functions**:
  - `loadModelComparison()`: Fetches data from `/api/stats/model-comparison`
  - `renderModelComparison()`: Renders metrics table and chart
  - `exportComparisonToHTML()`: HTML export with embedded data
  - `exportComparisonToImage()`: Image export using html2canvas
- **Visualization Libraries**: Chart.js for calibration scatter plot
- **Export**: Both HTML and image export

**Export System** (`export.py`):
- **Endpoint**: `POST /api/export/html`
- **Input**: `{ html_content: string, filename: string }`
- **Output**: Saves to `docs/{filename}`
- **Error Handling**: Comprehensive error handling with HTTP exceptions

### Performance Baseline

**Current Grid Search Page**:
- **Load Time**: < 1 second (single result set)
- **Render Time**: < 500ms (heatmaps render on canvas)
- **Export Time**: 2-5 seconds (html2canvas processing)

**Model Comparison Page**:
- **Load Time**: < 1 second (API fetch + render)
- **Render Time**: < 500ms (Chart.js initialization)
- **Export Time**: 2-5 seconds (html2canvas processing)

**Expected Performance for Comparison Page**:
- **Load Time**: 1-2 seconds (fetch comparison data + 5 model visualization data)
- **Render Time**: 1-2 seconds (5 heatmaps + charts)
- **Export Time**: 5-10 seconds (larger canvas area with 5 models)

## Technical Assessment

### Design Pattern Analysis

**Pattern 1: Template Method Pattern** (Existing)
- **Used In**: `templates.js` - template loading and rendering
- **Application**: Load template HTML, render into container
- **Reuse**: Can use same pattern for new comparison page

**Pattern 2: Facade Pattern** (Existing)
- **Used In**: `export-utils.js` - unified export interface
- **Application**: `generateExportHeader()`, `generateExportHeaderCSS()` provide unified export header
- **Reuse**: Can use same functions for comparison page export

**Pattern 3: Strategy Pattern** (Proposed)
- **Application**: Different visualization strategies for different chart types
- **Implementation**: Separate functions for heatmap, scatter, marginal effects
- **Benefit**: Easy to add new visualization types

**Pattern 4: Observer Pattern** (Existing)
- **Used In**: Chart.js event handlers, html2canvas callbacks
- **Application**: React to user interactions, export completion
- **Reuse**: Standard JavaScript event handling

### Algorithm Analysis

**Comparison Data Loading**:
- **Algorithm**: O(n) where n = number of models (5)
- **Complexity**: Simple JSON fetch and parse
- **Performance**: < 100ms for 5 models

**Heatmap Rendering**:
- **Algorithm**: O(w × h) where w = entry thresholds, h = exit thresholds
- **Current Implementation**: Custom canvas rendering with color mapping
- **Performance**: ~50-100ms per heatmap (800×600 canvas)
- **Total for 5 Models**: ~250-500ms

**Chart Rendering**:
- **Algorithm**: O(d) where d = data points
- **Current Implementation**: Chart.js for scatter plots
- **Performance**: ~50-100ms per chart
- **Total for 5 Models**: ~250-500ms

**Export HTML Generation**:
- **Algorithm**: O(c) where c = HTML content size
- **Complexity**: String concatenation with embedded data
- **Performance**: < 100ms for typical page

**Export Image Generation**:
- **Algorithm**: O(p) where p = pixels in viewport
- **Complexity**: html2canvas DOM to canvas conversion
- **Performance**: 2-10 seconds depending on viewport size

### UX/UI Design Research

**Best Practices for Multi-Dataset Comparison**:

1. **Side-by-Side Layout**:
   - **Pattern**: Grid layout with consistent sizing
   - **Benefit**: Easy visual comparison
   - **Implementation**: CSS Grid with 5 columns (or responsive 2-3 columns on mobile)

2. **Synchronized Scales**:
   - **Pattern**: All heatmaps use same color scale (min/max across all models)
   - **Benefit**: Fair comparison, no visual bias
   - **Implementation**: Calculate global min/max before rendering

3. **Unified Metrics Table**:
   - **Pattern**: Single table with all models as rows
   - **Benefit**: Easy to scan and compare numbers
   - **Implementation**: HTML table with sortable columns

4. **Progressive Disclosure**:
   - **Pattern**: Summary view with expandable details
   - **Benefit**: Reduces cognitive load
   - **Implementation**: Collapsible sections for detailed metrics

5. **Visual Hierarchy**:
   - **Pattern**: Most important metrics at top, details below
   - **Benefit**: Users see key information first
   - **Implementation**: Summary cards → Metrics table → Visualizations

6. **Color Coding**:
   - **Pattern**: Consistent colors for each model across all visualizations
   - **Benefit**: Easy to track model across different views
   - **Implementation**: Color palette assigned per model

### Implementation Approach

**Option 1: New Dedicated Page** (RECOMMENDED)
- **Route**: `#/grid-search-comparison`
- **Template**: `grid-search-comparison.html`
- **JavaScript**: `grid-search-comparison.js`
- **API Endpoint**: `GET /api/grid-search/comparison`
- **Pros**:
  - Clean separation of concerns
  - Easy to maintain
  - Follows existing pattern (model-comparison page)
- **Cons**:
  - Requires new route and template
- **Complexity**: Medium (4-6 hours)
- **Selected**: ✅ Best approach, follows existing patterns

**Option 2: Tab/Section in Existing Grid Search Page**
- **Pros**: All grid search functionality in one place
- **Cons**: Clutters existing page, harder to maintain
- **Complexity**: Medium-High (6-8 hours)
- **Rejected**: ❌ Violates single responsibility, harder to maintain

**Option 3: Modal/Overlay**
- **Pros**: No new page needed
- **Cons**: Limited space for 5 models, poor UX
- **Complexity**: Low-Medium (3-4 hours)
- **Rejected**: ❌ Insufficient space, poor user experience

## Recommendations

### Immediate Actions (Priority: High)

1. **Create API Endpoint for Comparison Data**
   - **File**: `webapp/api/endpoints/grid_search.py`
   - **Endpoint**: `GET /api/grid-search/comparison`
   - **Functionality**:
     - Read `data/grid_search/model_comparison.json`
     - For each model, load visualization data from `grid_results_train.json` and `grid_results_valid.json`
     - Transform data into unified format for frontend
     - Return JSON with:
       - Model metadata (names, timestamps)
       - Metrics (test/valid/train for all models)
       - Visualization data (heatmap matrices, scatter data, marginal effects)
   - **Estimated Effort**: 2-3 hours
   - **Risk Level**: Low
   - **Success Metrics**: Endpoint returns complete comparison data in < 500ms

2. **Create Frontend Template**
   - **File**: `webapp/static/templates/grid-search-comparison.html`
   - **Structure**:
     - Page header with title and export buttons
     - Summary section (key metrics comparison table)
     - Visualizations section (5 heatmaps side-by-side)
     - Detailed metrics section (expandable per model)
     - Charts section (marginal effects, tradeoff scatter for all models)
   - **Estimated Effort**: 2-3 hours
   - **Risk Level**: Low
   - **Success Metrics**: Template renders correctly, matches existing design patterns

3. **Create Frontend JavaScript**
   - **File**: `webapp/static/js/grid-search-comparison.js`
   - **Functions**:
     - `loadGridSearchComparison()`: Fetch data from API
     - `renderComparisonSummary()`: Render metrics table
     - `renderComparisonHeatmaps()`: Render 5 heatmaps side-by-side
     - `renderComparisonCharts()`: Render charts for all models
     - `exportComparisonToHTML()`: Export HTML to `docs/grid-search-comparison.html`
     - `exportComparisonToImage()`: Export image using html2canvas
   - **Estimated Effort**: 4-6 hours
   - **Risk Level**: Medium
   - **Success Metrics**: All visualizations render correctly, exports work

4. **Add Routing**
   - **File**: `webapp/static/js/routing.js`
   - **Changes**:
     - Add route handler for `#/grid-search-comparison`
     - Add navigation link in `index.html`
   - **Estimated Effort**: 30 minutes
   - **Risk Level**: Low
   - **Success Metrics**: Navigation works, page loads correctly

### Short-term Improvements (Priority: Medium)

1. **Synchronized Heatmap Scales**
   - Calculate global min/max across all models
   - Apply same color scale to all heatmaps
   - **Estimated Effort**: 1-2 hours

2. **Interactive Filtering**
   - Filter by model type (ESPN, LogReg, CatBoost)
   - Filter by calibration method (Platt, Isotonic)
   - **Estimated Effort**: 2-3 hours

3. **Sortable Metrics Table**
   - Click column headers to sort
   - Highlight best/worst values
   - **Estimated Effort**: 1-2 hours

### Long-term Enhancements (Priority: Low)

1. **Threshold Sensitivity Analysis**
   - Show how performance changes with threshold variations
   - **Estimated Effort**: 4-6 hours

2. **Model Performance Over Time**
   - Track performance across different seasons
   - **Estimated Effort**: 6-8 hours

3. **Export PDF**
   - Generate PDF report with all comparisons
   - **Estimated Effort**: 3-4 hours

## Implementation Plan

### Phase 1: API Endpoint (2-3 hours)

**Objective**: Create API endpoint that serves comparison data

**Tasks**:
1. **Add comparison endpoint to `grid_search.py`**
   - **File**: `webapp/api/endpoints/grid_search.py`
   - **Function**: `get_grid_search_comparison() -> dict[str, Any]`
   - **Logic**:
     - Read `data/grid_search/model_comparison.json`
     - For each model in comparison data:
       - Load `grid_results_train.json` and `grid_results_valid.json` from model's result directory
       - Extract visualization data (heatmap matrices, scatter data)
     - Transform into unified format
     - Return JSON response
   - **Error Handling**: Handle missing files, invalid JSON

2. **Add route registration**
   - **File**: `webapp/api/endpoints/grid_search.py`
   - **Route**: `@router.get("/api/grid-search/comparison")`
   - **Response**: JSON with comparison data

**Deliverables**:
- API endpoint returns comparison data
- Response time < 500ms
- Error handling for missing data

### Phase 2: Frontend Template (2-3 hours)

**Objective**: Create HTML template for comparison page

**Tasks**:
1. **Create template file**
   - **File**: `webapp/static/templates/grid-search-comparison.html`
   - **Structure**:
     ```html
     <div id="gridSearchComparisonView">
       <div class="page-header">
         <h2>Grid Search Model Comparison</h2>
         <div class="export-buttons">
           <button onclick="exportComparisonToHTML()">📄 Export HTML</button>
           <button onclick="exportComparisonToImage()">🖼️ Export Image</button>
         </div>
       </div>
       
       <!-- Summary Section -->
       <div id="comparisonSummary" class="results-section">
         <h3>Summary Comparison</h3>
         <div id="summaryTable"></div>
       </div>
       
       <!-- Heatmaps Section -->
       <div id="comparisonHeatmaps" class="results-section">
         <h3>Profit Heatmaps (Validation Set)</h3>
         <div id="heatmapGrid" class="heatmap-grid"></div>
       </div>
       
       <!-- Detailed Metrics Section -->
       <div id="detailedMetrics" class="results-section">
         <h3>Detailed Metrics by Model</h3>
         <div id="detailedMetricsContent"></div>
       </div>
       
       <!-- Charts Section -->
       <div id="comparisonCharts" class="results-section">
         <h3>Additional Visualizations</h3>
         <div id="chartsGrid"></div>
       </div>
     </div>
     ```

2. **Add CSS for grid layout**
   - **File**: `webapp/static/css/styles.css` (or inline in template)
   - **Styles**:
     - `.heatmap-grid`: CSS Grid with 5 columns (responsive)
     - `.model-heatmap-container`: Individual heatmap wrapper
     - Consistent sizing and spacing

**Deliverables**:
- Template file created
- Layout renders correctly
- Responsive design (mobile-friendly)

### Phase 3: Frontend JavaScript (4-6 hours)

**Objective**: Implement comparison page logic

**Tasks**:
1. **Create JavaScript file**
   - **File**: `webapp/static/js/grid-search-comparison.js`
   - **Functions**:
     - `loadGridSearchComparison()`: Fetch and render
     - `renderComparisonSummary()`: Metrics table
     - `renderComparisonHeatmaps()`: 5 heatmaps side-by-side
     - `renderComparisonCharts()`: Charts for all models
     - `exportComparisonToHTML()`: HTML export
     - `exportComparisonToImage()`: Image export

2. **Implement heatmap rendering**
   - **Reuse**: Logic from `grid-search.js` `renderProfitHeatmap()`
   - **Modify**: Calculate global min/max for synchronized scales
   - **Render**: 5 heatmaps in grid layout

3. **Implement chart rendering**
   - **Reuse**: Logic from `grid-search.js` for marginal effects and tradeoff scatter
   - **Modify**: Show all models on same chart (different colors)
   - **Library**: Chart.js for scatter plots

4. **Implement export functions**
   - **HTML Export**: Similar to `model-comparison.js` `exportComparisonToHTML()`
     - Fetch CSS
     - Embed comparison data in script tag
     - Generate complete HTML
     - POST to `/api/export/html` with filename `grid-search-comparison.html`
   - **Image Export**: Similar to `model-comparison.js` `exportComparisonToImage()`
     - Use html2canvas to capture entire comparison view
     - Download as PNG

**Deliverables**:
- JavaScript file with all functions
- Visualizations render correctly
- Exports work correctly

### Phase 4: Routing and Navigation (30 minutes)

**Objective**: Add route and navigation link

**Tasks**:
1. **Update routing.js**
   - **File**: `webapp/static/js/routing.js`
   - **Add**: Route handler for `#/grid-search-comparison`
   - **Add**: Route mapping in `getRoute()` function

2. **Update templates.js** (if needed)
   - **File**: `webapp/static/js/templates.js`
   - **Add**: Template loading for `grid-search-comparison`

3. **Update index.html**
   - **File**: `webapp/static/index.html`
   - **Add**: Navigation link in header nav
   - **Add**: Script tag for `grid-search-comparison.js`

4. **Update app.js** (if needed)
   - **File**: `webapp/static/js/app.js`
   - **Add**: View initialization for comparison page

**Deliverables**:
- Navigation link added
- Route works correctly
- Page loads when navigating

### Phase 5: Testing and Refinement (2-3 hours)

**Objective**: Test functionality and refine UX

**Tasks**:
1. **Test data loading**
   - Verify API endpoint returns correct data
   - Verify frontend handles missing data gracefully

2. **Test visualizations**
   - Verify all 5 heatmaps render correctly
   - Verify charts render correctly
   - Verify synchronized scales work

3. **Test exports**
   - Verify HTML export saves to `docs/grid-search-comparison.html`
   - Verify image export downloads correctly
   - Verify exported HTML renders correctly in browser

4. **Test responsive design**
   - Verify layout works on mobile
   - Verify heatmaps scale correctly

5. **Performance testing**
   - Verify page loads in < 2 seconds
   - Verify visualizations render in < 2 seconds

**Deliverables**:
- All functionality tested
- Performance meets targets
- UX refined based on testing

## Risk Assessment

### Technical Risks

**Risk 1**: Large visualization data causes slow page load
- **Probability**: Medium
- **Impact**: High (poor user experience)
- **Mitigation**: 
  - Lazy load visualizations (render on scroll)
  - Compress visualization data in API response
  - Cache visualization data in browser
- **Contingency**: Show loading indicators, progressive rendering

**Risk 2**: html2canvas fails on large comparison view
- **Probability**: Low
- **Impact**: Medium (export doesn't work)
- **Mitigation**:
  - Test with actual data
  - Use lower scale for export (scale: 1.5 instead of 2)
  - Split export into multiple images if needed
- **Contingency**: Provide alternative export method (screenshot instructions)

**Risk 3**: Heatmap rendering performance issues
- **Probability**: Low
- **Impact**: Medium (slow rendering)
- **Mitigation**:
  - Optimize canvas rendering (use requestAnimationFrame)
  - Reduce canvas size if needed
  - Cache rendered heatmaps
- **Contingency**: Show simplified heatmaps or use Chart.js heatmap plugin

### Data Risks

**Risk 1**: Missing comparison data
- **Probability**: Low (script generates it)
- **Impact**: High (page doesn't work)
- **Mitigation**:
  - Check for `model_comparison.json` existence
  - Show helpful error message with instructions
  - Provide link to run comparison script
- **Contingency**: Graceful error handling, fallback to empty state

**Risk 2**: Inconsistent data formats
- **Probability**: Low (standardized JSON)
- **Impact**: Medium (rendering errors)
- **Mitigation**:
  - Validate data structure in API endpoint
  - Handle missing fields gracefully
  - Log validation errors
- **Contingency**: Show partial data, log errors for debugging

### UX Risks

**Risk 1**: Too much information overwhelms users
- **Probability**: Medium
- **Impact**: Medium (poor user experience)
- **Mitigation**:
  - Use progressive disclosure (collapsible sections)
  - Show summary first, details on demand
  - Use clear visual hierarchy
- **Contingency**: Add filtering options, simplify default view

**Risk 2**: Mobile layout doesn't work well
- **Probability**: Medium
- **Impact**: Low (desktop is primary use case)
- **Mitigation**:
  - Use responsive CSS Grid
  - Stack heatmaps vertically on mobile
  - Test on mobile devices
- **Contingency**: Mobile-specific layout adjustments

## Evidence and Verification

### File Structure Verification

**Command**: `ls -la webapp/static/templates/`
**Expected Output**: 
```
grid-search.html
model-comparison.html
```

**Command**: `ls -la webapp/static/js/`
**Expected Output**:
```
grid-search.js
model-comparison.js
export-utils.js
```

**Command**: `ls -la data/grid_search/`
**Expected Output**:
```
model_comparison.json
grid_search_*/ (multiple directories)
```

### API Endpoint Verification

**Command**: `curl http://localhost:8000/api/grid-search/comparison`
**Expected Output**: JSON with comparison data

### Template Loading Verification

**Command**: Open browser console, navigate to `#/grid-search-comparison`
**Expected Output**: Template loads, no errors

### Export Functionality Verification

**Command**: Click "Export HTML" button
**Expected Output**: 
- Success message
- File created at `docs/grid-search-comparison.html`

**Command**: `ls -la docs/grid-search-comparison.html`
**Expected Output**: File exists

## Design Decisions

### Design Decision: Side-by-Side Heatmap Layout

**Problem Statement**:
- Need to compare 5 heatmaps (ESPN + 4 ML models)
- Must be visually comparable (same scale, same size)
- Must work on desktop and mobile

**Options**:

**Option 1: 5-Column Grid (Desktop) / 2-Column (Mobile)**
- **Design Pattern**: Responsive CSS Grid
- **Algorithm**: O(1) layout calculation
- **Implementation Complexity**: Low (1 hour)
- **Maintenance Overhead**: Low
- **Scalability**: Good (easy to add more models)
- **Cost-Benefit**: Low cost, High benefit
- **Selected**: ✅ Best for desktop viewing, responsive

**Option 2: Tabbed Interface**
- **Design Pattern**: Tab Component Pattern
- **Algorithm**: O(1) tab switching
- **Implementation Complexity**: Medium (2 hours)
- **Maintenance Overhead**: Medium
- **Scalability**: Good
- **Cost-Benefit**: Medium cost, Medium benefit
- **Rejected**: ❌ Doesn't allow side-by-side comparison

**Option 3: Accordion/Collapsible**
- **Design Pattern**: Accordion Pattern
- **Algorithm**: O(1) expand/collapse
- **Implementation Complexity**: Low (1 hour)
- **Maintenance Overhead**: Low
- **Scalability**: Good
- **Cost-Benefit**: Low cost, Low benefit
- **Rejected**: ❌ Doesn't allow side-by-side comparison

**Chosen Solution**: 5-Column Grid (Desktop) / 2-Column (Mobile)

**Implementation**:
```css
.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}

@media (max-width: 1200px) {
  .heatmap-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .heatmap-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

**Pros**:
- Easy visual comparison
- Responsive design
- Simple implementation

**Cons**:
- May be cramped on smaller screens
- Requires scrolling on mobile

### Design Decision: Synchronized Heatmap Scales

**Problem Statement**:
- Each model's heatmap has different profit ranges
- Without synchronization, visual comparison is misleading
- Need fair comparison across all models

**Options**:

**Option 1: Global Min/Max Scale**
- **Algorithm**: O(n × m) where n = models, m = heatmap cells
- **Implementation**: Calculate min/max across all models, apply to all
- **Complexity**: Low (1 hour)
- **Selected**: ✅ Fair comparison, easy to implement

**Option 2: Per-Model Scales**
- **Algorithm**: O(m) per model
- **Implementation**: Each heatmap uses its own min/max
- **Complexity**: Low (already implemented)
- **Rejected**: ❌ Misleading visual comparison

**Option 3: Normalized Scales**
- **Algorithm**: O(n × m)
- **Implementation**: Normalize each model to 0-1, then scale
- **Complexity**: Medium (2 hours)
- **Rejected**: ❌ Loses absolute value information

**Chosen Solution**: Global Min/Max Scale

**Implementation**:
```javascript
function calculateGlobalScale(allHeatmapData) {
  let globalMin = Infinity;
  let globalMax = -Infinity;
  
  allHeatmapData.forEach(modelData => {
    modelData.matrix.forEach(row => {
      row.forEach(val => {
        if (val !== null && val !== undefined) {
          globalMin = Math.min(globalMin, val);
          globalMax = Math.max(globalMax, val);
        }
      });
    });
  });
  
  return { min: globalMin, max: globalMax };
}
```

**Pros**:
- Fair visual comparison
- Preserves absolute values
- Easy to understand

**Cons**:
- Some models may have less color contrast if their range is smaller

## References

- **Grid Search Implementation**: `webapp/static/templates/grid-search.html`, `webapp/static/js/grid-search.js`
- **Model Comparison Implementation**: `webapp/static/templates/model-comparison.html`, `webapp/static/js/model-comparison.js`
- **Export System**: `webapp/api/endpoints/export.py`, `webapp/static/js/export-utils.js`
- **Comparison Script**: `scripts/trade/compare_grid_search_models.py`
- **Comparison Data**: `data/grid_search/model_comparison.json`
- **Analysis Template**: `cursor-files/templates/ANALYSIS_TEMPLATE.md`
- **Analysis Standards**: `cursor-files/templates/ANALYSIS_STANDARDS.md`
- **GitHub Pages Deployment**: `docs/GITHUB_PAGES_DEPLOYMENT.md`

