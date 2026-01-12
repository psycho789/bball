# Sprint 20: Model Comparison Visualization Webapp Integration

**Date**: Mon Jan 12 02:11:17 PST 2026  
**Sprint Duration**: 1-2 days (9-11 hours total)  
**Sprint Goal**: Integrate the model comparison visualization into the webapp with full routing, dark theme styling, HTML/Image export functionality, and GitHub Pages deployment support  
**Current Status**: Model comparison visualization exists as standalone HTML file (`data/models/evaluations/model_comparison.html`) with light theme. Not accessible via webapp. No export functionality.  
**Target Status**: Model comparison page accessible at `/model-comparison` route with dark theme styling matching aggregate stats page, HTML export saves to `docs/model-comparison.html`, Image export available, GitHub Pages documentation updated  
**Team Size**: 1 developer  
**Sprint Lead**: Developer  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Reference Documents

- **Analysis**: `cursor-files/analysis/2026-01-12-model-comparison-webapp-integration/model_comparison_webapp_integration_analysis_v1.md`
- **Standalone Visualization**: `data/models/evaluations/model_comparison.html` (28KB, created Jan 12 01:48)
- **Visualization Generator**: `scripts/utils/visualize_model_comparison.py`
- **Reference Implementation**: `webapp/static/js/stats.js`, `webapp/static/templates/aggregate-stats.html`

## Pre-Sprint Code Quality Baseline

- **Test Results**: N/A (manual testing for webapp)
- **QC Results**: N/A
- **Code Coverage**: N/A
- **Build Status**: Application builds and runs successfully

**Purpose**: This baseline ensures we maintain or improve code quality throughout the sprint and provides historical reference for quality metrics.

## Database Evidence Template

**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database** - no INSERT, UPDATE, ALTER, TRUNCATE, DELETE unless part of sprint plan
- **DO NOT modify database users** - no user management or system changes

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

**Git Usage Rules**:
- **NO git commands** unless explicitly mentioned in sprint plan
- **NO git operations** unless explicitly mentioned in analysis
- **NO version control** unless explicitly mentioned in prompt by prompter
- **NO commits, pushes, pulls, or branches** unless explicitly directed
- **NO git status, git log, or git diff** unless explicitly mentioned in sprint plan

**Exception**: Git usage is only allowed when:
1. Explicitly mentioned in the analysis document
2. Explicitly mentioned in the sprint plan
3. Explicitly mentioned in the prompt by the prompter that git can be used

## Sprint Overview

### Business Context
- **Business Driver**: Model comparison visualization exists as standalone HTML file but is not accessible through webapp interface. Users must navigate file system to access it. Need to integrate into webapp for unified user experience and enable GitHub Pages deployment.
- **Success Criteria**: 
  - Model comparison page accessible via webapp navigation at `/model-comparison` route
  - Page styling matches webapp dark theme (100% consistency with aggregate stats page)
  - HTML export functionality saves to `docs/model-comparison.html` for GitHub Pages
  - Image export functionality available (for consistency with aggregate stats)
  - GitHub Pages documentation updated with model comparison export instructions
- **Stakeholders**: Data science team, users accessing model comparison visualization
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - Standalone HTML file: `data/models/evaluations/model_comparison.html` (light theme, not integrated)
  - Visualization generator: `scripts/utils/visualize_model_comparison.py` (generates standalone HTML)
  - Evaluation JSON files: 4 files in `data/models/evaluations/` for all 4 models
  - Aggregate stats page: `webapp/static/templates/aggregate-stats.html`, `webapp/static/js/stats.js` (reference implementation)
  - Export endpoint: `webapp/api/endpoints/export.py` (hardcodes filename to "aggregate-stats.html")
  - Routing: `webapp/static/js/routing.js` (hash-based routing pattern)
- **Target System State**: 
  - Backend endpoint: `GET /api/stats/model-comparison` returns comparison data JSON
  - Frontend template: `webapp/static/templates/model-comparison.html` (dark theme, matches aggregate stats)
  - Frontend JavaScript: `webapp/static/js/model-comparison.js` (data loading, rendering, export)
  - Route: `/model-comparison` accessible via navigation
  - Export: HTML export saves to `docs/model-comparison.html`, Image export available
  - Documentation: `docs/GITHUB_PAGES_DEPLOYMENT.md` updated with model comparison instructions
- **Architecture Impact**: Adds new endpoint, template, and JavaScript file following existing patterns
- **Integration Points**: FastAPI backend, frontend routing, export endpoint, GitHub Pages

### Sprint Scope
- **In Scope**: 
  - Backend endpoint for model comparison data
  - Frontend template and JavaScript for model comparison page
  - Routing and navigation integration
  - HTML export functionality (with data embedding)
  - Image export functionality (for consistency)
  - Export endpoint extension (optional filename parameter)
  - GitHub Pages documentation update
- **Out of Scope**: 
  - Model retraining or evaluation (already complete)
  - Standalone HTML file modification (will be replaced by webapp integration)
  - Database changes (no database operations needed)
- **Assumptions**: 
  - All 4 evaluation JSON files exist and are valid
  - Chart.js is already loaded in webapp (verified: `webapp/static/index.html:20`)
  - Export endpoint pattern from aggregate stats can be reused
  - html2canvas library available for image export (already used in aggregate stats)
- **Constraints**: 
  - Must match aggregate stats page styling exactly
  - Must maintain backward compatibility with existing export endpoint
  - Must follow existing routing and templating patterns

## Sprint Phases

### Phase 1: Backend Endpoint (Duration: 1-2 hours)
**Objective**: Create endpoint to serve model comparison data from evaluation JSON files
**Dependencies**: Evaluation JSON files exist in `data/models/evaluations/`
**Deliverables**: Working endpoint at `/api/stats/model-comparison` that returns structured JSON

### Tasks
- **[Task 1.1]**: Create `webapp/api/endpoints/model_comparison.py`
  - **Files**: New file `webapp/api/endpoints/model_comparison.py`
  - **Effort**: 1-1.5 hours
  - **Prerequisites**: None
  - **Validation**: 
    - Endpoint exists at `/api/stats/model-comparison`
    - Returns JSON with `models` array (4 models)
    - Each model has `model_label`, `model_color`, `metrics`, `calibration_points`
    - Returns `best_models` object with best model for each metric
    - Test: `curl http://localhost:8000/api/stats/model-comparison | jq '.models | length'` returns `4`
- **[Task 1.2]**: Register router in `webapp/api/main.py`
  - **Files**: `webapp/api/main.py` (modify)
  - **Effort**: 15 minutes
  - **Prerequisites**: Task 1.1 complete
  - **Validation**: 
    - Router imported: `from .endpoints import ..., model_comparison`
    - Router registered: `app.include_router(model_comparison.router, prefix="/api", tags=["model_comparison"])`
    - Endpoint accessible and returns data

### Phase 2: Frontend Template and Rendering (Duration: 3-4 hours)
**Objective**: Create template and JavaScript to render comparison page with dark theme
**Dependencies**: Phase 1 complete, backend endpoint accessible
**Deliverables**: Working page with metrics table and calibration chart matching aggregate stats styling

### Tasks
- **[Task 2.1]**: Create `webapp/static/templates/model-comparison.html`
  - **Files**: New file `webapp/static/templates/model-comparison.html`
  - **Effort**: 30 minutes
  - **Prerequisites**: None
  - **Validation**: 
    - Template matches aggregate stats structure (page-header, export-buttons, container)
    - Uses same CSS classes as aggregate stats
    - Template loads via `renderTemplate('model-comparison', container)`
- **[Task 2.2]**: Create `webapp/static/js/model-comparison.js`
  - **Files**: New file `webapp/static/js/model-comparison.js`
  - **Effort**: 2.5-3 hours
  - **Prerequisites**: Task 2.1 complete
  - **Validation**: 
    - `loadModelComparison()` function fetches from `/api/stats/model-comparison`
    - `renderModelComparison(data)` renders metrics table with best model highlighting
    - `renderModelComparison(data)` renders Chart.js calibration plot with 4 models
    - Chart uses correct colors: Purple (#7c3aed), Blue (#3b82f6), Orange (#f7931a), Green (#10b981)
    - Perfect calibration line (y=x) displayed
    - Dark theme styling matches aggregate stats page
    - Page loads and displays correctly

### Phase 3: Routing and Navigation (Duration: 1 hour)
**Objective**: Add routing and navigation for model comparison page
**Dependencies**: Phase 2 complete
**Deliverables**: Page accessible via navigation link and URL hash

### Tasks
- **[Task 3.1]**: Update `webapp/static/js/routing.js`
  - **Files**: `webapp/static/js/routing.js` (modify)
  - **Effort**: 30 minutes
  - **Prerequisites**: Task 2.2 complete
  - **Validation**: 
    - Route parsing: `if (hash === '/model-comparison' || hash.startsWith('/model-comparison'))` returns `{ view: 'model-comparison', gameId: null }`
    - `showModelComparisonPageView()` function exists and renders template
    - `updateActiveNav()` includes model-comparison route mapping
    - Navigation to `#/model-comparison` works
- **[Task 3.2]**: Update `webapp/static/js/app.js`
  - **Files**: `webapp/static/js/app.js` (modify)
  - **Effort**: 15 minutes
  - **Prerequisites**: Task 3.1 complete
  - **Validation**: 
    - Route handling in DOMContentLoaded includes model-comparison case
    - Page loads correctly on initial navigation
- **[Task 3.3]**: Update `webapp/static/index.html`
  - **Files**: `webapp/static/index.html` (modify)
  - **Effort**: 15 minutes
  - **Prerequisites**: Task 3.1 complete
  - **Validation**: 
    - Navigation link exists: `<a href="#/model-comparison" class="nav-link" data-route="model-comparison">`
    - Link has icon and text (e.g., "📊 Model Comparison")
    - Active state works when on model-comparison page

### Phase 4: Export Functionality and Documentation (Duration: 3.5 hours)
**Objective**: Add HTML and Image export, extend export endpoint, update documentation
**Dependencies**: Phase 3 complete
**Deliverables**: Export functionality working, documentation updated

### Tasks
- **[Task 4.1]**: Extend export endpoint (`webapp/api/endpoints/export.py`)
  - **Files**: `webapp/api/endpoints/export.py` (modify)
  - **Effort**: 30 minutes
  - **Prerequisites**: None
  - **Validation**: 
    - `HTMLExportRequest` includes `filename: Optional[str] = "aggregate-stats.html"`
    - Line 49 changed to: `output_file = docs_dir / request.filename`
    - Backward compatibility: Existing aggregate stats export still works (default filename)
    - Test: Export with `filename: "test.html"` saves to `docs/test.html`
- **[Task 4.2]**: Add HTML export function to `webapp/static/js/model-comparison.js`
  - **Files**: `webapp/static/js/model-comparison.js` (modify)
  - **Effort**: 1.5 hours
  - **Prerequisites**: Task 4.1 complete, Task 2.2 complete
  - **Validation**: 
    - `exportComparisonToHTML()` function exists
    - Fetches CSS content from `/static/css/styles.css`
    - Gets container HTML from `modelComparisonContainer`
    - **Critical**: Embeds comparison data in `<script>` tag: `const comparisonData = ${JSON.stringify(comparisonData, null, 2)};`
    - Builds Chart.js initialization code using embedded `comparisonData`
    - POSTs to `/api/export/html` with `{html_content: ..., filename: "model-comparison.html"}`
    - File saves to `docs/model-comparison.html`
    - Exported HTML renders correctly in browser (standalone, no API calls)
- **[Task 4.3]**: Add Image export function to `webapp/static/js/model-comparison.js`
  - **Files**: `webapp/static/js/model-comparison.js` (modify)
  - **Effort**: 1 hour
  - **Prerequisites**: Task 2.2 complete
  - **Validation**: 
    - `exportComparisonToImage()` function exists
    - Uses `html2canvas` library (already available)
    - Captures `modelComparisonContainer` element
    - Downloads PNG file with appropriate filename
    - Image export works correctly
- **[Task 4.4]**: Update `docs/GITHUB_PAGES_DEPLOYMENT.md`
  - **Files**: `docs/GITHUB_PAGES_DEPLOYMENT.md` (modify)
  - **Effort**: 30 minutes
  - **Prerequisites**: Task 4.2 complete
  - **Validation**: 
    - Documentation includes section on model comparison export
    - Instructions for exporting both aggregate stats and model comparison
    - URL format includes model-comparison.html option
    - Documentation is clear and follows same format as aggregate stats section

## Sprint Backlog

### Epic 1: Backend Infrastructure
**Priority**: Critical (required for core functionality)
**Estimated Time**: 1.5-2 hours
**Dependencies**: None
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Create Model Comparison Endpoint
- **ID**: S20-E1-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 1-1.5 hours
- **Phase**: Phase 1
- **Prerequisites**: None
- **Files to Modify**: None
- **Files to Create**: 
  - `webapp/api/endpoints/model_comparison.py` (new endpoint file)
- **Dependencies**: Evaluation JSON files in `data/models/evaluations/`

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] Endpoint exists at `/api/stats/model-comparison` and accepts GET requests
  - [ ] Endpoint loads all 4 evaluation JSON files:
    - `winprob_eval_logreg_platt_2017-2023_calib_2023_on_2024.json`
    - `winprob_eval_logreg_isotonic_2017-2023_calib_2023_on_2024.json`
    - `winprob_eval_catboost_platt_2017-2023_calib_2023_on_2024.json`
    - `winprob_eval_catboost_isotonic_2017-2023_calib_2023_on_2024.json`
  - [ ] Endpoint extracts metrics from `eval.overall` for each model (logloss, brier, ece_binned, roc_auc, n)
  - [ ] Endpoint extracts calibration points from `eval.calibration_bins` (transforms to `calibration_points` with x, y, n)
  - [ ] Endpoint determines best model for each metric (lower is better: logloss, brier, ece; higher is better: auc)
  - [ ] Endpoint returns structured JSON:
    ```json
    {
      "models": [
        {
          "model_label": "Logistic Regression + Platt",
          "model_color": "#7c3aed",
          "metrics": {...},
          "calibration_points": [...]
        },
        ...
      ],
      "best_models": {
        "logloss": "CatBoost + Platt",
        "brier": "CatBoost + Platt",
        "ece": "CatBoost + Platt",
        "auc": "CatBoost + Platt"
      }
    }
    ```
  - [ ] Test: `curl http://localhost:8000/api/stats/model-comparison | jq '.models | length'` returns `4`
  - [ ] Test: All 4 models have `model_label`, `model_color`, `metrics`, `calibration_points`

- **Technical Context**:
  - **Current State**: No backend endpoint exists for model comparison data
  - **Required Changes**: 
    - Create new FastAPI router
    - Load 4 evaluation JSON files from `data/models/evaluations/`
    - Extract and transform data (calibration_bins → calibration_points)
    - Determine best models
    - Return structured JSON
  - **Integration Points**: FastAPI router registration, file system operations
  - **Data Structures**: 
    - Input: Evaluation JSON files with `eval.overall` and `eval.calibration_bins`
    - Output: Structured JSON with models array and best_models object
  - **API Contracts**: 
    - `GET /api/stats/model-comparison`
    - Response: `{"models": [...], "best_models": {...}}`

- **Implementation Steps**: 
  1. Create `webapp/api/endpoints/model_comparison.py`
  2. Import FastAPI, Path, json, typing
  3. Define model file list (4 files)
  4. Create `get_model_label()` function (extract from filename)
  5. Create `get_model_color()` function (map label to color)
  6. Create `load_evaluation_reports()` function (load all 4 JSON files)
  7. Create `extract_metrics()` function (extract from eval.overall)
  8. Create `extract_calibration_points()` function (transform calibration_bins)
  9. Create `find_best_models()` function (determine best for each metric)
  10. Create `GET /api/stats/model-comparison` endpoint
  11. Combine all functions to return structured JSON

- **Validation Steps**: 
  ```bash
  # Start webapp
  cd webapp && uvicorn api.main:app --reload --port 8000
  
  # Test endpoint
  curl http://localhost:8000/api/stats/model-comparison | jq '.models | length'
  # Expected: 4
  
  # Verify structure
  curl http://localhost:8000/api/stats/model-comparison | jq '.models[0] | keys'
  # Expected: ["model_label", "model_color", "metrics", "calibration_points"]
  
  # Verify best models
  curl http://localhost:8000/api/stats/model-comparison | jq '.best_models'
  # Expected: Object with logloss, brier, ece, auc keys
  ```

- **Definition of Done**: Endpoint returns valid JSON with all 4 models and best_models object
- **Rollback Plan**: Remove endpoint file and router registration if issues arise
- **Risk Assessment**: 
  - File not found: Low risk, handled by error checking
  - Invalid JSON: Low risk, JSON parsing will raise exception
  - Missing fields: Low risk, validation in extraction functions
  - Mitigation: Add try-catch blocks, validate file existence, handle missing fields gracefully

- **Success Metrics**: 
  - **Performance**: Endpoint responds in < 1 second (file I/O only)
  - **Quality**: 100% success rate for valid evaluation files
  - **Functionality**: Returns correct data structure with all 4 models

### Story 1.2: Register Model Comparison Router
- **ID**: S20-E1-S2
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 15 minutes
- **Phase**: Phase 1
- **Prerequisites**: S20-E1-S1
- **Files to Modify**: `webapp/api/main.py`
- **Files to Create**: None
- **Dependencies**: Story 1.1 complete

- **Acceptance Criteria**:
  - [ ] Router imported: `from .endpoints import ..., model_comparison`
  - [ ] Router registered: `app.include_router(model_comparison.router, prefix="/api", tags=["model_comparison"])`
  - [ ] Endpoint accessible at `/api/stats/model-comparison`
  - [ ] Endpoint appears in API documentation (if enabled)

- **Technical Context**:
  - **Current State**: Need to find where routers are registered
  - **Required Changes**: Import and register model_comparison router

- **Implementation Steps**: 
  1. Find router registration section in `webapp/api/main.py` (around line 134-146)
  2. Add `model_comparison` to imports: `from .endpoints import ..., model_comparison`
  3. Add router registration: `app.include_router(model_comparison.router, prefix="/api", tags=["model_comparison"])`

- **Validation Steps**: 
  ```bash
  # Check endpoint is accessible
  curl http://localhost:8000/api/stats/model-comparison
  # Should return JSON (not 404)
  ```

### Epic 2: Frontend Implementation
**Priority**: Critical (required for user-facing functionality)
**Estimated Time**: 3.5-4 hours
**Dependencies**: Epic 1 complete
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Create Model Comparison Template
- **ID**: S20-E2-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 30 minutes
- **Phase**: Phase 2
- **Prerequisites**: None
- **Files to Create**: `webapp/static/templates/model-comparison.html`
- **Files to Modify**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Template file exists at `webapp/static/templates/model-comparison.html`
  - [ ] Template structure matches `aggregate-stats.html`:
    - `<section class="stats-page-view" id="modelComparisonPageView">`
    - `<div class="page-header">` with title and export buttons
    - `<div class="model-comparison-container" id="modelComparisonContainer">` with loading state
  - [ ] Export buttons exist: `exportComparisonHtmlBtn` and `exportComparisonImageBtn`
  - [ ] Template loads via `renderTemplate('model-comparison', container)`

- **Technical Context**:
  - **Current State**: No template exists
  - **Required Changes**: Create template matching aggregate stats structure

- **Implementation Steps**: 
  1. Copy structure from `aggregate-stats.html`
  2. Change IDs and function names to model-comparison variants
  3. Update title and subtitle text

- **Validation Steps**: 
  ```bash
  # Verify template file exists
  test -f webapp/static/templates/model-comparison.html && echo "Template exists"
  
  # Check template structure
  grep -q "modelComparisonPageView" webapp/static/templates/model-comparison.html && echo "Structure correct"
  ```

### Story 2.2: Create Model Comparison JavaScript
- **ID**: S20-E2-S2
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 2.5-3 hours
- **Phase**: Phase 2
- **Prerequisites**: S20-E1-S1, S20-E1-S2, S20-E2-S1
- **Files to Create**: `webapp/static/js/model-comparison.js`
- **Files to Modify**: None
- **Dependencies**: Backend endpoint accessible, template exists

- **Acceptance Criteria**:
  - [ ] `loadModelComparison()` function exists and fetches from `/api/stats/model-comparison`
  - [ ] `renderModelComparison(data)` function exists and renders:
    - Metrics table with all 4 models (LogLoss, Brier, ECE, AUC, N)
    - Best model highlighting (bold text, background color)
    - Best models summary section
    - Chart.js calibration plot with 4 datasets (one per model)
    - Perfect calibration line (y=x) as reference
  - [ ] Chart uses correct colors:
    - Logistic Regression + Platt: Purple (#7c3aed)
    - Logistic Regression + Isotonic: Blue (#3b82f6)
    - CatBoost + Platt: Orange (#f7931a)
    - CatBoost + Isotonic: Green (#10b981)
  - [ ] Dark theme styling matches aggregate stats page
  - [ ] Page loads and displays correctly when navigating to `/model-comparison`

- **Technical Context**:
  - **Current State**: No JavaScript exists for model comparison
  - **Required Changes**: 
    - Create data loading function
    - Create rendering function with metrics table and Chart.js plot
    - Use dark theme CSS classes
    - Follow aggregate stats rendering pattern

- **Implementation Steps**: 
  1. Create `webapp/static/js/model-comparison.js`
  2. Implement `loadModelComparison()` function (fetch from API)
  3. Implement `renderModelComparison(data)` function:
     - Render metrics table HTML with best model highlighting
     - Render best models summary
     - Create Chart.js scatter plot with 4 datasets + perfect calibration line
     - Use correct colors for each model
  4. Add error handling
  5. Add loading state management

- **Validation Steps**: 
  1. Navigate to `#/model-comparison` in webapp
  2. Verify page loads and displays metrics table
  3. Verify Chart.js calibration plot renders with all 4 models
  4. Verify colors are correct
  5. Verify best model highlighting works
  6. Verify dark theme styling matches aggregate stats

### Epic 3: Routing and Navigation
**Priority**: Critical (required for accessibility)
**Estimated Time**: 1 hour
**Dependencies**: Epic 2 complete
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Add Model Comparison Route
- **ID**: S20-E3-S1
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 30 minutes
- **Phase**: Phase 3
- **Prerequisites**: S20-E2-S2
- **Files to Modify**: `webapp/static/js/routing.js`
- **Dependencies**: Story 2.2 complete

- **Acceptance Criteria**:
  - [ ] Route parsing: `if (hash === '/model-comparison' || hash.startsWith('/model-comparison'))` returns `{ view: 'model-comparison', gameId: null }`
  - [ ] `showModelComparisonPageView()` function exists
  - [ ] Function renders template: `await renderTemplate('model-comparison', viewsContainer)`
  - [ ] Function calls `loadModelComparison()` after template renders
  - [ ] `updateActiveNav()` includes model-comparison route mapping

- **Implementation Steps**: 
  1. Add route parsing in `getRoute()` function
  2. Add `showModelComparisonPageView()` function
  3. Update `updateActiveNav()` function to handle model-comparison route

- **Validation Steps**: 
  1. Navigate to `#/model-comparison`
  2. Verify page loads correctly
  3. Verify navigation link is active

### Story 3.2: Add Route Handling in App.js
- **ID**: S20-E3-S2
- **Type**: Configuration
- **Priority**: Critical
- **Estimate**: 15 minutes
- **Phase**: Phase 3
- **Prerequisites**: S20-E3-S1
- **Files to Modify**: `webapp/static/js/app.js`
- **Dependencies**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] Route handling in DOMContentLoaded includes model-comparison case
  - [ ] Calls `showModelComparisonPageView()` when route is model-comparison
  - [ ] Page loads correctly on initial navigation

- **Implementation Steps**: 
  1. Find DOMContentLoaded handler in `app.js`
  2. Add `else if (route.view === 'model-comparison')` case
  3. Call `showModelComparisonPageView()`

### Story 3.3: Add Navigation Link
- **ID**: S20-E3-S3
- **Type**: Feature
- **Priority**: Critical
- **Estimate**: 15 minutes
- **Phase**: Phase 3
- **Prerequisites**: S20-E3-S1
- **Files to Modify**: `webapp/static/index.html`
- **Dependencies**: Story 3.1 complete

- **Acceptance Criteria**:
  - [ ] Navigation link exists: `<a href="#/model-comparison" class="nav-link" data-route="model-comparison">`
  - [ ] Link has icon (e.g., "📊") and text (e.g., "Model Comparison")
  - [ ] Active state works when on model-comparison page

- **Implementation Steps**: 
  1. Find navigation section in `index.html` (around line 40-63)
  2. Add new nav link after stats link
  3. Use appropriate icon and text

### Epic 4: Export Functionality
**Priority**: High (required for GitHub Pages deployment)
**Estimated Time**: 3 hours
**Dependencies**: Epic 3 complete
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Extend Export Endpoint
- **ID**: S20-E4-S1
- **Type**: Feature Enhancement
- **Priority**: High
- **Estimate**: 30 minutes
- **Phase**: Phase 4
- **Prerequisites**: None
- **Files to Modify**: `webapp/api/endpoints/export.py`
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `HTMLExportRequest` includes `filename: Optional[str] = "aggregate-stats.html"`
  - [ ] Line 49 changed to: `output_file = docs_dir / request.filename`
  - [ ] `Optional` imported if not present: `from typing import Any, Optional`
  - [ ] Backward compatibility: Existing aggregate stats export still works (default filename)
  - [ ] Test: Export with `filename: "test.html"` saves to `docs/test.html`

- **Technical Context**:
  - **Current State**: 
    ```python
    class HTMLExportRequest(BaseModel):
        html_content: str
    # Line 49: output_file = docs_dir / "aggregate-stats.html"
    ```
  - **Required Changes**: 
    ```python
    from typing import Any, Optional
    
    class HTMLExportRequest(BaseModel):
        html_content: str
        filename: Optional[str] = "aggregate-stats.html"
    # Line 49: output_file = docs_dir / request.filename
    ```

- **Implementation Steps**: 
  1. Add `Optional` to imports if not present
  2. Modify `HTMLExportRequest` to include `filename` parameter
  3. Change line 49 to use `request.filename`
  4. Test backward compatibility (aggregate stats export)

- **Validation Steps**: 
  ```bash
  # Test backward compatibility (no filename = default)
  curl -X POST http://localhost:8000/api/export/html \
    -H "Content-Type: application/json" \
    -d '{"html_content": "<html>test</html>"}'
  # Should save to docs/aggregate-stats.html
  
  # Test with filename
  curl -X POST http://localhost:8000/api/export/html \
    -H "Content-Type: application/json" \
    -d '{"html_content": "<html>test</html>", "filename": "test.html"}'
  # Should save to docs/test.html
  ```

### Story 4.2: Implement HTML Export
- **ID**: S20-E4-S2
- **Type**: Feature
- **Priority**: High
- **Estimate**: 1.5 hours
- **Phase**: Phase 4
- **Prerequisites**: S20-E4-S1, S20-E2-S2
- **Files to Modify**: `webapp/static/js/model-comparison.js`
- **Dependencies**: Export endpoint extended, comparison data available

- **Acceptance Criteria**:
  - [ ] `exportComparisonToHTML()` function exists
  - [ ] Fetches CSS content from `/static/css/styles.css`
  - [ ] Gets container HTML from `modelComparisonContainer`
  - [ ] **Critical**: Embeds comparison data in `<script>` tag:
    ```javascript
    const comparisonData = ${JSON.stringify(comparisonData, null, 2)};
    ```
  - [ ] Builds Chart.js initialization code using embedded `comparisonData`
  - [ ] POSTs to `/api/export/html` with `{html_content: ..., filename: "model-comparison.html"}`
  - [ ] File saves to `docs/model-comparison.html`
  - [ ] Exported HTML renders correctly in browser (standalone, no API calls)
  - [ ] Chart.js renders calibration plot from embedded data

- **Technical Context**:
  - **Current State**: No export function exists
  - **Required Changes**: 
    - Create export function following aggregate stats pattern
    - Embed comparison data in HTML (critical for standalone rendering)
    - Use Chart.js CDN in exported HTML
    - POST with filename parameter

- **Implementation Steps**: 
  1. Create `exportComparisonToHTML()` function
  2. Fetch CSS content
  3. Get container HTML
  4. Get comparison data (from current page state or re-fetch)
  5. Build HTML with embedded data:
     - Include Chart.js CDN
     - Embed `comparisonData` in `<script>` tag
     - Build Chart.js initialization using embedded data
  6. POST to `/api/export/html` with filename
  7. Test exported HTML renders correctly

- **Validation Steps**: 
  1. Click "Export HTML" button
  2. Verify file saves to `docs/model-comparison.html`
  3. Open exported HTML in browser
  4. Verify Chart.js renders calibration plot
  5. Verify no API calls in browser console (standalone HTML)

### Story 4.3: Implement Image Export
- **ID**: S20-E4-S3
- **Type**: Feature
- **Priority**: Medium (for consistency with aggregate stats)
- **Estimate**: 1 hour
- **Phase**: Phase 4
- **Prerequisites**: S20-E2-S2
- **Files to Modify**: `webapp/static/js/model-comparison.js`
- **Dependencies**: html2canvas library available

- **Acceptance Criteria**:
  - [ ] `exportComparisonToImage()` function exists
  - [ ] Uses `html2canvas` library (already available)
  - [ ] Captures `modelComparisonContainer` element
  - [ ] Downloads PNG file with appropriate filename (e.g., `model-comparison-2026-01-12.png`)
  - [ ] Image export works correctly

- **Implementation Steps**: 
  1. Create `exportComparisonToImage()` function
  2. Use `html2canvas` to capture container
  3. Convert to blob and download
  4. Follow aggregate stats image export pattern

- **Validation Steps**: 
  1. Click "Export Image" button
  2. Verify PNG file downloads
  3. Verify image contains all content (metrics table, chart)

### Story 4.4: Update GitHub Pages Documentation
- **ID**: S20-E4-S4
- **Type**: Documentation
- **Priority**: Medium
- **Estimate**: 30 minutes
- **Phase**: Phase 4
- **Prerequisites**: S20-E4-S2
- **Files to Modify**: `docs/GITHUB_PAGES_DEPLOYMENT.md`
- **Dependencies**: Story 4.2 complete

- **Acceptance Criteria**:
  - [ ] Documentation includes section on model comparison export
  - [ ] Instructions for exporting both aggregate stats and model comparison
  - [ ] URL format includes model-comparison.html option
  - [ ] Documentation is clear and follows same format as aggregate stats section

- **Implementation Steps**: 
  1. Add new section to `GITHUB_PAGES_DEPLOYMENT.md`
  2. Include export instructions for model comparison
  3. Update URL examples to include model-comparison.html

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: S20-DOC-UPDATE
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 30 minutes
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**: 
  - [ ] All API endpoints documented
  - [ ] Frontend functions have inline comments
  - [ ] GitHub Pages deployment guide updated
  - [ ] Code follows existing patterns and conventions

- **Technical Context**: Ensure all new code is well-documented
- **Implementation Steps**: Review and update all documentation
- **Validation Steps**: Verify documentation completeness

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: S20-QG-VALIDATION
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] Backend endpoint tested manually and works correctly
  - [ ] Frontend page tested manually and works correctly
  - [ ] Export functionality tested and works correctly
  - [ ] Styling matches aggregate stats page (visual inspection)
  - [ ] All previous story acceptance criteria verified

- **Technical Context**:
  - **Current State**: New code added for model comparison integration
  - **Required Changes**: Run linting, test functionality, verify styling
  - **Quality Gates**: 
    - Python linting (flake8, pylint, or similar)
    - JavaScript linting (ESLint or similar)
    - Manual testing of all functionality
    - Visual inspection of styling

- **Implementation Steps**: 
  1. Run Python linter on `webapp/api/endpoints/model_comparison.py`
  2. Run JavaScript linter on `webapp/static/js/model-comparison.js`
  3. Test all functionality end-to-end
  4. Verify styling consistency
  5. Test export functionality

- **Validation Steps**: 
  ```bash
  # Python linting
  # Test backend endpoint
  curl http://localhost:8000/api/stats/model-comparison | jq '.models | length'
  
  # Test frontend
  # Navigate to #/model-comparison and verify page loads
  
  # Test export
  # Click export buttons and verify files are created
  ```

### Story [FINAL]: Sprint Completion and Archive
- **ID**: S20-COMPLETION
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 30 minutes
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**: 
  - [ ] Sprint completion report created
  - [ ] All files organized in sprint directory
  - [ ] Sprint marked as completed

- **Technical Context**: Create summary of completed work
- **Implementation Steps**: 
  1. Create completion report
  2. Verify all files are in place
  3. Update sprint status

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: Template Pattern
- **Category**: Behavioral
- **Intent**: Define skeleton of page rendering algorithm, allowing pages to share structure
- **Implementation**: Template loading via `templates.js`, page-specific rendering in JS files
- **Benefits**: Consistent page structure, reusable template loading mechanism
- **Trade-offs**: Requires separate JS file for each page
- **Rationale**: Provides consistent structure while allowing page-specific customization

### Design Pattern: Router Pattern
- **Category**: Architectural
- **Intent**: Map URL routes to view functions
- **Implementation**: Hash-based routing in `routing.js`, route parsing and view functions
- **Benefits**: Clean URL-based navigation, easy to add new routes
- **Trade-offs**: Hash-based routing (not true URLs), requires JavaScript
- **Rationale**: Simple, works without server-side routing, supports browser navigation

### Algorithm Analysis

### Algorithm: File I/O and Data Transformation
- **Type**: I/O Operation with Data Transformation
- **Complexity**: Time O(n) where n is total calibration points, Space O(n) for data structures
- **Description**: Load JSON files, extract metrics and calibration points, transform calibration_bins to calibration_points format
- **Use Case**: Serve model comparison data from evaluation JSON files
- **Performance**: File I/O is fast (< 100ms for 4 files), data transformation is O(n) where n is calibration points

### Design Decision Analysis

### Design Decision: Reuse Aggregate Stats Pattern

**Problem Statement**:
- Need to integrate model comparison visualization into webapp
- Must maintain consistency with existing pages
- Must support HTML export for GitHub Pages

**Context and Constraints**:
- Existing aggregate stats page has working pattern
- Dark theme styling established
- Export functionality pattern exists
- Timeline: Single sprint (9-11 hours)

**Project Scope**: Medium-sized feature addition, single developer, expected to be stable feature

**Sprint Scope Analysis**:
- **Complexity Assessment**: 
  - Files affected: 8 files (3 new, 5 modified)
  - Lines of code: ~500-600 new lines
  - Dependencies: None (all infrastructure exists)
  - Team impact: Single developer
- **Sprint Scope Determination**: Single Sprint
- **Scope Justification**: All work is self-contained, follows established patterns, can be completed in 9-11 hours
- **Timeline Considerations**: 9-11 hours total, can be done in 1-2 days, low risk
- **Single Sprint Alternative**: Single sprint is viable - work is straightforward pattern replication

**Multiple Solution Analysis**:

**Option 1: Standalone HTML File (CURRENT STATE)**
- **Design Pattern**: None (static file)
- **Algorithm**: N/A
- **Implementation Complexity**: Low (already exists)
- **Maintenance Overhead**: High (separate from webapp, no integration)
- **Scalability**: Poor (not accessible via webapp)
- **Cost-Benefit**: Low cost, Low benefit
- **Over-Engineering Risk**: None
- **Rejected**: Doesn't integrate with webapp, poor user experience

**Option 2: Full Webapp Integration (CHOSEN)**
- **Design Pattern**: Template Pattern, Router Pattern, Service Pattern
- **Algorithm**: O(n) data loading, O(1) routing
- **Implementation Complexity**: Medium (9-11 hours)
- **Maintenance Overhead**: Low (follows existing patterns)
- **Scalability**: Good (integrated with webapp, easy to extend)
- **Cost-Benefit**: Medium cost, High benefit
- **Over-Engineering Risk**: Low (reusing existing patterns)
- **Selected**: Provides best user experience, maintains consistency, enables export functionality

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 9-11 hours (medium complexity)
- **Learning Curve**: 0 hours (reusing existing patterns)
- **Configuration Effort**: 0 hours (no new configuration needed)

**Maintenance Cost**:
- **Monitoring**: 0 hours (no monitoring needed)
- **Updates**: 1 hour/month (if comparison data changes)
- **Debugging**: 0.5 hours/incident (simple page, follows patterns)

**Performance Benefit**:
- **Response Time**: < 2 seconds (matches aggregate stats)
- **Throughput**: N/A (client-side rendering)
- **Resource Efficiency**: Minimal (reuses existing infrastructure)

**Maintainability Benefit**:
- **Code Quality**: Consistent with existing codebase
- **Developer Productivity**: Easy to understand (follows patterns)
- **System Reliability**: Low risk (reuses tested patterns)

**Risk Cost**:
- **Risk 1**: Styling inconsistency - Low risk, mitigated by reusing CSS classes
- **Risk 2**: Export functionality bugs - Low risk, mitigated by reusing export pattern

**Over-Engineering Prevention**:
- **Problem Complexity**: Medium (integration task)
- **Solution Complexity**: Medium (pattern replication)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Easy to extend (follows established patterns)

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Matches project size
- **Team Capability**: ✅ Single developer can handle
- **Timeline Constraints**: ✅ Fits in single sprint
- **Future Growth**: ✅ Easy to extend
- **Technical Debt**: ✅ No new debt introduced

**Chosen Solution**: Full webapp integration following aggregate stats pattern
- Implementation: Backend endpoint, frontend template/JS, routing, export functionality
- Configuration: No new configuration needed
- Integration: Follows existing webapp architecture

**Pros and Cons Analysis**:

**Pros**:
- **Consistency**: Matches existing webapp pages exactly
- **User Experience**: Integrated navigation, consistent styling
- **Export Functionality**: Enables GitHub Pages deployment
- **Maintainability**: Follows established patterns, easy to maintain
- **Extensibility**: Easy to add features (e.g., filtering, sorting)

**Cons**:
- **Development Time**: 9-11 hours (vs. 1-2 hours for minimal integration)
- **Code Duplication**: Some code duplication with aggregate stats (acceptable for consistency)

**Risk Assessment**: 
- **Risk 1**: Styling inconsistency - Low risk, mitigated by reusing CSS classes
- **Risk 2**: Export functionality bugs - Low risk, mitigated by reusing export pattern
- **Risk 3**: Routing conflicts - Low risk, new route doesn't conflict with existing routes

**Trade-off Analysis**: 
- **Sacrificed**: 6-8 hours of development time (vs. minimal integration)
- **Gained**: Full integration, consistent UX, export functionality, maintainability
- **Net Benefit**: High (better user experience and maintainability worth the extra time)
- **Over-Engineering Risk**: Low (solution complexity matches problem complexity)

## Testing Strategy

### Testing Approach
- **Unit Tests**: N/A (simple file operations, manual testing sufficient)
- **Integration Tests**: Manual testing of export flow (frontend → backend → file system)
- **E2E Tests**: Manual testing: Navigate to page → Verify data loads → Verify charts render → Test export
- **Performance Tests**: N/A (static file read, performance not critical)

## Deployment Plan
- **Pre-Deployment**: 
  - [ ] Backend endpoint tested and working
  - [ ] Frontend page tested and working
  - [ ] Export functionality tested and working
  - [ ] Styling verified to match aggregate stats
- **Deployment Steps**: 
  1. All code changes complete
  2. Manual testing passes
  3. Export functionality verified
  4. Documentation updated
- **Post-Deployment**: 
  - [ ] Verify page accessible at `/model-comparison`
  - [ ] Verify export saves to `docs/model-comparison.html`
  - [ ] Verify exported HTML renders correctly
- **Rollback Plan**: 
  - Remove new files if issues arise
  - Revert router registration
  - Revert export endpoint changes if needed

## Risk Assessment
- **Technical Risks**: 
  - Styling inconsistency: Mitigated by reusing CSS classes
  - Export data embedding: Mitigated by following aggregate stats pattern exactly
  - Chart.js rendering: Mitigated by using same Chart.js setup as aggregate stats
- **Business Risks**: 
  - User confusion: Mitigated by clear navigation label and consistent UX
  - Export failures: Mitigated by fallback to browser download
- **Resource Risks**: 
  - Time overrun: Low risk, simple pattern replication
  - Scope creep: Mitigated by clear sprint scope

## Success Metrics
- **Technical**: 
  - Endpoint responds in < 1 second
  - Page loads in < 2 seconds
  - Export saves correctly 100% of the time
- **Business**: 
  - Users can successfully access model comparison via webapp
  - Users can successfully export HTML for GitHub Pages
  - Page styling matches aggregate stats (100% consistency)
- **Sprint**: 
  - All stories completed within estimated time
  - Quality gates pass
  - Documentation complete

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing (manual testing)
- [ ] All documentation updated
- [ ] All quality gates pass (linting, manual testing, visual inspection)

### Post-Sprint Quality Comparison
- **Test Results**: Manual testing completed successfully
- **Linting Results**: Zero errors and warnings
- **Code Coverage**: N/A (manual testing)
- **Build Status**: Application builds and runs successfully
- **Overall Assessment**: Model comparison integration working correctly, ready for use

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.

