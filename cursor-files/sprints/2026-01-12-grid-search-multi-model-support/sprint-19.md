# Sprint 19: Grid Search Multi-Model Support

**Date**: Mon Jan 12 02:25:23 PST 2026  
**Sprint Duration**: 1 day (12-16 hours total)  
**Sprint Goal**: Enable grid search to support all 4 win probability models (Logistic Regression × CatBoost × Platt × Isotonic calibration) by adding model selection parameter and integrating model-based probability generation into the grid search pipeline  
**Current Status**: Grid search uses ESPN probabilities directly from `derived.snapshot_features_v1` materialized view. No model selection capability exists.  
**Target Status**: Grid search accepts model selection parameter, generates probabilities using selected model, and correctly caches results per model. All 4 models can be tested independently.  
**Team Size**: 1 developer  
**Sprint Lead**: TBD  

## Sprint Standards Reference

**Important**: This sprint follows the comprehensive standards defined in `SPRINT_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based**: Every claim backed by concrete evidence (commands + verbatim output, code refs, DB queries)
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and exact artifacts analyzed
- **File Verification**: Verify file contents directly before making claims
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`)
- **Document Placement**: Sprint plan in `cursor-files/sprints/2026-01-12-grid-search-multi-model-support/sprint-19.md`

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline

- **Test Results**: N/A (no existing tests for grid search model integration)
- **QC Results**: N/A (no data quality checks for model scoring)
- **Code Coverage**: N/A (grid search script not covered by tests)
- **Build Status**: ✅ Current codebase builds successfully

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

## Sprint Overview

### Business Context
- **Business Driver**: Users need to compare trading strategy performance across different win probability models to identify which model produces the best trading results. Currently, grid search only uses ESPN raw probabilities, preventing model comparison.
- **Success Criteria**: 
  - Users can select any of 4 models in grid search UI
  - Grid search completes successfully with each model
  - Results are correctly cached and distinguished by model
  - Backward compatibility maintained (no model = ESPN probabilities)
- **Stakeholders**: Trading strategy researchers, model developers
- **Timeline Constraints**: None

### Technical Context
- **Current System State**: 
  - Grid search script: `scripts/trade/grid_search_hyperparameters.py` - no model parameter
  - Simulation function: `scripts/trade/simulate_trading_strategy.py::get_aligned_data()` - queries ESPN probabilities directly
  - API endpoint: `webapp/api/endpoints/grid_search.py` - no model parameter
  - Frontend: `webapp/static/templates/grid-search.html` - no model selector
  - Models exist: All 4 models in `data/models/` (verified)
- **Target System State**: 
  - Grid search accepts `model_name` parameter (optional, None = ESPN)
  - `get_aligned_data()` accepts optional `model_artifact` parameter
  - When model provided, generates probabilities using model instead of ESPN
  - Cache keys include model identifier
  - Frontend has model selector dropdown
- **Architecture Impact**: Extends existing grid search pipeline with optional model scoring layer
- **Integration Points**: 
  - Model loading: `scripts/lib/_winprob_lib.py::load_artifact()`
  - Model scoring: `scripts/lib/_winprob_lib.py::predict_proba()`
  - Feature building: `scripts/lib/_winprob_lib.py::build_design_matrix()`
  - Canonical dataset: `derived.snapshot_features_v1` (provides game state features)

### Sprint Scope
- **In Scope**: 
  - Add model selection to grid search backend (Python script)
  - Add model selection to grid search API endpoint
  - Add model selection to grid search frontend UI
  - Integrate model scoring into `get_aligned_data()`
  - Update cache key generation to include model
  - Test all 4 models individually
- **Out of Scope**: 
  - Model training or evaluation (models already exist)
  - Performance optimization (model caching can be added later)
  - Batch scoring optimization (can be added later)
- **Assumptions**: 
  - All 4 model files exist in `data/models/` (verified)
  - Models are compatible with canonical dataset features (verified)
  - Model infrastructure (`load_artifact`, `predict_proba`) works correctly (verified)
- **Constraints**: 
  - Must maintain backward compatibility (no model = ESPN probabilities)
  - Must not break existing grid searches
  - Performance overhead acceptable (5-10% slower with model scoring)

## Sprint Phases

### Phase 1: Backend Model Integration (Duration: 6-8 hours)
**Objective**: Add model selection support to grid search backend, integrate model scoring into data alignment function
**Dependencies**: Model files must exist in `data/models/`, canonical dataset must be available
**Deliverables**: 
- `GridSearchConfig` with `model_name` field
- Model loading helper function
- `get_aligned_data()` with optional model scoring
- Cache key includes model identifier

### Phase 2: API and Frontend Updates (Duration: 4-5 hours)
**Objective**: Add model selection to API endpoint and frontend UI
**Dependencies**: Must complete Phase 1
**Deliverables**: 
- API endpoint accepts and validates model parameter
- Frontend has model selector dropdown
- Model parameter passed through to backend

### Phase 3: Testing and Validation (Duration: 2-3 hours)
**Objective**: Verify all 4 models work correctly, test backward compatibility
**Dependencies**: Must complete Phase 2
**Deliverables**: 
- All 4 models tested successfully
- Backward compatibility verified
- Cache correctness verified

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: Backend Model Integration
**Priority**: Critical - Core functionality required for sprint goal
**Estimated Time**: 6-8 hours
**Dependencies**: Model files in `data/models/`, canonical dataset `derived.snapshot_features_v1`
**Status**: Not Started
**Phase Assignment**: Phase 1

### Story 1.1: Add Model Selection to GridSearchConfig
- **ID**: S19-E1-S1
- **Type**: Feature
- **Priority**: Critical - Required for all other stories
- **Estimate**: 1 hour
- **Phase**: 1
- **Prerequisites**: None
- **Files to Modify**: 
  - `scripts/trade/grid_search_hyperparameters.py` (add `model_name` field to `GridSearchConfig` dataclass, add CLI argument)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `GridSearchConfig` dataclass has `model_name: Optional[str] = None` field
  - [ ] CLI argument `--model-name` added to argument parser
  - [ ] `--model-name` accepts values: `"logreg_platt"`, `"logreg_isotonic"`, `"catboost_platt"`, `"catboost_isotonic"`, or `None` (default)
  - [ ] Config creation in `main()` includes `model_name` from args
  - [ ] Command `python scripts/trade/grid_search_hyperparameters.py --help` shows `--model-name` option

- **Technical Context**:
  - **Current State**: 
    ```python
    @dataclass
    class GridSearchConfig:
        entry_min: float
        # ... other fields ...
        exclude_last_seconds: int = 60
    ```
  - **Target State**: 
    ```python
    @dataclass
    class GridSearchConfig:
        entry_min: float
        # ... other fields ...
        exclude_last_seconds: int = 60
        model_name: Optional[str] = None  # New field
    ```
  - **Implementation**: Add field to dataclass, add CLI argument, update config creation

- **Pros and Cons**:
  - **Pros**: Simple addition, minimal code changes, maintains backward compatibility (default None)
  - **Cons**: None significant

### Story 1.2: Create Model Loading Helper Function and Update Pipeline
- **ID**: S19-E1-S2
- **Type**: Feature
- **Priority**: Critical - Required for model scoring
- **Estimate**: 1-2 hours
- **Phase**: 1
- **Prerequisites**: S19-E1-S1
- **Files to Modify**: 
  - `scripts/trade/grid_search_hyperparameters.py` (add helper function, update `process_combination()` and `run_simulation_for_games()`)
- **Files to Create**: None
- **Dependencies**: `scripts/lib/_winprob_lib.py::load_artifact()`

- **Acceptance Criteria**:
  - [ ] Function `load_model_artifact(model_name: Optional[str]) -> Optional[WinProbArtifact]` exists
  - [ ] Function returns `None` when `model_name` is `None`
  - [ ] Function loads correct model file for each model name:
    - `"logreg_platt"` → `data/models/winprob_logreg_platt_2017-2023.json`
    - `"logreg_isotonic"` → `data/models/winprob_logreg_isotonic_2017-2023.json`
    - `"catboost_platt"` → `data/models/winprob_catboost_platt_2017-2023.json`
    - `"catboost_isotonic"` → `data/models/winprob_catboost_isotonic_2017-2023.json`
  - [ ] Function raises clear error if model file not found
  - [ ] Function returns `WinProbArtifact` object when model loads successfully
  - [ ] `process_combination()` function loads model artifact using `load_model_artifact(config.model_name)` at start of function
  - [ ] `process_combination()` passes loaded `model_artifact` to `run_simulation_for_games()` calls
  - [ ] `run_simulation_for_games()` function signature includes `model_artifact: Optional[WinProbArtifact] = None` parameter
  - [ ] `run_simulation_for_games()` passes `model_artifact` to `get_aligned_data()` call (line 272)
  - [ ] Command `python -c "from scripts.trade.grid_search_hyperparameters import load_model_artifact; print(load_model_artifact('logreg_platt'))"` executes successfully

- **Technical Context**:
  - **Current State**: No model loading in grid search script, `process_combination()` and `run_simulation_for_games()` don't handle models
  - **Target State**: 
    ```python
    def load_model_artifact(model_name: Optional[str]) -> Optional[WinProbArtifact]:
        """Load model artifact by name. Returns None if model_name is None."""
        if model_name is None:
            return None
        
        model_file_map = {
            "logreg_platt": "data/models/winprob_logreg_platt_2017-2023.json",
            "logreg_isotonic": "data/models/winprob_logreg_isotonic_2017-2023.json",
            "catboost_platt": "data/models/winprob_catboost_platt_2017-2023.json",
            "catboost_isotonic": "data/models/winprob_catboost_isotonic_2017-2023.json",
        }
        
        if model_name not in model_file_map:
            raise ValueError(f"Unknown model name: {model_name}. Valid options: {list(model_file_map.keys())}")
        
        model_path = Path(model_file_map[model_name])
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        from scripts.lib._winprob_lib import load_artifact
        return load_artifact(model_path)
    
    def process_combination(
        combination: tuple[float, float],
        game_splits: dict[str, list[str]],
        config: GridSearchConfig,
        dsn: str,
        progress: Optional[Any] = None,
        task_id: Optional[int] = None
    ) -> dict[str, Any]:
        # Load model artifact once per combination
        model_artifact = load_model_artifact(config.model_name) if config.model_name else None
        
        # ... existing code ...
        
        for split_name in ['train', 'valid', 'test']:
            split_results = run_simulation_for_games(
                conn,
                game_ids,
                entry_threshold,
                exit_threshold,
                config,
                model_artifact=model_artifact,  # Pass model artifact
                progress=progress,
                task_id=task_id
            )
    
    def run_simulation_for_games(
        conn: psycopg.Connection,
        game_ids: list[str],
        entry_threshold: float,
        exit_threshold: float,
        config: GridSearchConfig,
        model_artifact: Optional[WinProbArtifact] = None,  # New parameter
        progress: Optional[Any] = None,
        task_id: Optional[int] = None
    ) -> dict[str, Any]:
        # ... existing code ...
        
        aligned_data, game_start, duration, actual_outcome = get_aligned_data(
            conn,
            game_id,
            exclude_first_seconds=config.exclude_first_seconds,
            exclude_last_seconds=config.exclude_last_seconds,
            use_trade_data=config.use_trade_data,
            model_artifact=model_artifact  # Pass model artifact
        )
    ```
  - **Implementation**: 
    1. Create `load_model_artifact()` helper function
    2. Update `process_combination()` to load model at start
    3. Update `process_combination()` to pass model to `run_simulation_for_games()`
    4. Update `run_simulation_for_games()` signature to accept `model_artifact`
    5. Update `run_simulation_for_games()` to pass model to `get_aligned_data()`

- **Pros and Cons**:
  - **Pros**: Centralized model loading, clear error messages, easy to extend
  - **Cons**: Hardcoded file paths (acceptable for now, can be made configurable later)

### Story 1.3: Refactor get_aligned_data() to Support Model Scoring
- **ID**: S19-E1-S3
- **Type**: Feature/Refactor
- **Priority**: Critical - Core functionality for model-based grid search
- **Estimate**: 3-4 hours
- **Phase**: 1
- **Prerequisites**: S19-E1-S2
- **Files to Modify**: 
  - `scripts/trade/simulate_trading_strategy.py` (update `get_aligned_data()` function)
  - `scripts/trade/grid_search_hyperparameters.py` (update `run_simulation_for_games()` to pass model artifact)
- **Files to Create**: None
- **Dependencies**: 
  - `scripts/lib/_winprob_lib.py::build_design_matrix()`
  - `scripts/lib/_winprob_lib.py::predict_proba()`
  - Canonical dataset `derived.snapshot_features_v1`

- **Acceptance Criteria**:
  - [ ] `get_aligned_data()` function signature includes `model_artifact: Optional[WinProbArtifact] = None` parameter
  - [ ] When `model_artifact` is `None`, function behaves exactly as before (uses ESPN probabilities)
  - [ ] When `model_artifact` is provided, SQL query selects additional columns:
    - `score_diff` (required for `point_differential`)
    - `score_diff_div_sqrt_time_remaining` (if in model's `feature_names`)
    - `espn_home_prob_lag_1` (if in model's `feature_names`)
    - `espn_home_prob_delta_1` (if in model's `feature_names`)
    - `period` (if in model's `feature_names`)
  - [ ] For each snapshot when model provided:
    - Extracts `score_diff` → `point_differential`
    - Extracts `time_remaining` → `time_remaining_regulation`
    - Sets `possession` to `'unknown'`
    - Builds design matrix using `build_design_matrix()` with appropriate features
    - Scores using `predict_proba()`, replaces `espn_prob` with model probability
  - [ ] Function returns aligned data with model probabilities when model provided
  - [ ] Function returns aligned data with ESPN probabilities when model is None (backward compatibility)
  - [ ] `run_simulation_for_games()` function updated to accept `model_artifact` parameter and pass it to `get_aligned_data()`
  - [ ] `process_combination()` function (Python script) updated to load model artifact from config and pass it to `run_simulation_for_games()`
  - [ ] `process_combination_with_pool()` function (API wrapper) updated to load model artifact from config and pass it to `run_simulation_for_games()`
  - [ ] Model artifact loaded once per combination (not per game) for efficiency
  - [ ] Both Python script and API wrapper handle model loading correctly
  - [ ] Command `python scripts/trade/simulate_trading_strategy.py --help` still works (if CLI exists)
  - [ ] Existing grid search without model parameter still works (backward compatibility test)

- **Technical Context**:
  - **Current State**: 
    ```python
    canonical_sql = """
    SELECT 
        snapshot_ts,
        espn_home_prob,
        kalshi_home_mid_price,
        # ... other columns ...
        time_remaining
    FROM derived.snapshot_features_v1
    """
    # Uses espn_home_prob directly
    ```
  - **Target State**: 
    ```python
    def get_aligned_data(
        conn: psycopg.Connection,
        game_id: str,
        exclude_first_seconds: int = 0,
        exclude_last_seconds: int = 0,
        use_trade_data: bool = False,
        model_artifact: Optional[WinProbArtifact] = None  # New parameter
    ) -> tuple[list[dict[str, Any]], Optional[int], Optional[int], Optional[int]]:
        # Determine which columns to select based on model
        base_columns = ["snapshot_ts", "espn_home_prob", "kalshi_home_mid_price", ...]
        if model_artifact:
            base_columns.append("score_diff")
            base_columns.append("time_remaining")
            # Add interaction terms if model uses them
            if any("score_diff_div_sqrt" in fn for fn in model_artifact.feature_names):
                base_columns.append("score_diff_div_sqrt_time_remaining")
            # ... check for other interaction terms ...
        
        canonical_sql = f"""
        SELECT {", ".join(base_columns)}
        FROM derived.snapshot_features_v1
        WHERE game_id = %s AND season_label = '2025-26'
        ORDER BY sequence_number, snapshot_ts
        """
        
        # ... query execution ...
        
        # For each row, if model provided:
        if model_artifact:
            # Build design matrix
            X = build_design_matrix(
                point_differential=np.array([score_diff], dtype=np.float64),
                time_remaining_regulation=np.array([time_remaining], dtype=np.float64),
                possession=['unknown'],
                preprocess=model_artifact.preprocess,
                # ... include interaction terms if model uses them ...
            )
            # Score model
            model_prob = predict_proba(model_artifact, X=X)[0]
            # Replace espn_prob with model_prob
            espn_prob = model_prob
        else:
            # Use ESPN probability as before
            espn_prob = row['espn_home_prob']
    ```
  - **Implementation**: 
    1. Add `model_artifact` parameter to `get_aligned_data()`
    2. Dynamically build SQL SELECT based on model's feature requirements
    3. After query, if model provided, score each snapshot
    4. Replace `espn_prob` with model probability
    5. **CRITICAL**: Update `run_simulation_for_games()` to accept `model_artifact: Optional[WinProbArtifact] = None` parameter
    6. **CRITICAL**: Update `run_simulation_for_games()` to pass `model_artifact` to `get_aligned_data()` call (line 272)
    7. **CRITICAL**: Update `process_combination()` to load model artifact from `config.model_name` using `load_model_artifact()` helper
    8. **CRITICAL**: Update `process_combination()` to pass loaded model artifact to `run_simulation_for_games()`

- **Pros and Cons**:
  - **Pros**: Maintains backward compatibility, flexible feature selection, reuses existing model infrastructure
  - **Cons**: More complex SQL query building, per-snapshot scoring overhead (acceptable), model loading per combination (can be optimized later with caching)

  - **Critical Integration Points**:
  - **Model Flow**: `config.model_name` → `process_combination()` or `process_combination_with_pool()` loads artifact → `run_simulation_for_games()` receives artifact → `get_aligned_data()` uses artifact
  - **Model Loading**: 
    - Load model artifact in `process_combination()` (Python script) using `load_model_artifact(config.model_name)` - loads once per combination
    - Load model artifact in `process_combination_with_pool()` (API wrapper) using `load_model_artifact(config.model_name)` - loads once per combination
    - Both functions need to import/use `load_model_artifact()` helper
  - **Model Passing**: Pass `model_artifact` parameter through: 
    - `process_combination()` → `run_simulation_for_games()` → `get_aligned_data()` (Python script path)
    - `process_combination_with_pool()` → `run_simulation_for_games()` → `get_aligned_data()` (API path)
  - **Performance Note**: Model loading happens once per combination, not per game. For 100 combinations, model loads 100 times (once per worker thread). This is acceptable for now; can be optimized with thread-local caching later.

### Story 1.4: Update Cache Key Generation to Include Model
- **ID**: S19-E1-S4
- **Type**: Feature
- **Priority**: Critical - Prevents cache collisions between different models
- **Estimate**: 1 hour
- **Phase**: 1
- **Prerequisites**: S19-E1-S1
- **Files to Modify**: 
  - `webapp/api/endpoints/grid_search.py` (update `_generate_grid_search_cache_key()` function)
  - `scripts/trade/grid_search_hyperparameters.py` (update cache key generation calls)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `_generate_grid_search_cache_key()` function signature includes `model_name: Optional[str] = None` parameter
  - [ ] `model_name` is included in `cache_params` dict (use `None` or `"espn"` for ESPN default)
  - [ ] Cache key changes when model changes (different models produce different keys)
  - [ ] Cache key same for same model (same model produces same key)
  - [ ] All calls to `_generate_grid_search_cache_key()` updated to pass `model_name`
  - [ ] Command `python -c "from webapp.api.endpoints.grid_search import _generate_grid_search_cache_key; k1 = _generate_grid_search_cache_key('2025-26', 0.02, 0.20, 0.01, 0.00, 0.05, 0.005, 20.0, True, 0.0, 60, 60, True, 0.7, 0.15, 0.15, 10, 200, None, 42, model_name='logreg_platt'); k2 = _generate_grid_search_cache_key('2025-26', 0.02, 0.20, 0.01, 0.00, 0.05, 0.005, 20.0, True, 0.0, 60, 60, True, 0.7, 0.15, 0.15, 10, 200, None, 42, model_name='catboost_platt'); print(k1 != k2)"` returns `True`

- **Technical Context**:
  - **Current State**: 
    ```python
    def _generate_grid_search_cache_key(
        season: str,
        # ... other parameters ...
        seed: int = 42
    ) -> str:
        cache_params = {
            "version": GRID_SEARCH_CACHE_VERSION,
            "season": season,
            # ... other params ...
            "seed": seed
        }
    ```
  - **Target State**: 
    ```python
    def _generate_grid_search_cache_key(
        season: str,
        # ... other parameters ...
        seed: int = 42,
        model_name: Optional[str] = None  # New parameter
    ) -> str:
        cache_params = {
            "version": GRID_SEARCH_CACHE_VERSION,
            "season": season,
            # ... other params ...
            "seed": seed,
            "model_name": model_name or "espn"  # Include model in cache key
        }
    ```
  - **Implementation**: Add parameter, include in cache_params, update all call sites

- **Pros and Cons**:
  - **Pros**: Prevents cache collisions, simple addition, maintains cache structure
  - **Cons**: None significant

### Epic 2: API and Frontend Updates
**Priority**: High - Required for user-facing functionality
**Estimated Time**: 4-5 hours
**Dependencies**: Must complete Epic 1
**Status**: Not Started
**Phase Assignment**: Phase 2

### Story 2.1: Update API Endpoint to Accept Model Parameter
- **ID**: S19-E2-S1
- **Type**: Feature
- **Priority**: High - Required for frontend integration
- **Estimate**: 2 hours
- **Phase**: 2
- **Prerequisites**: S19-E1-S1, S19-E1-S4
  - **Files to Modify**: 
  - `webapp/api/endpoints/grid_search.py` (update `run_grid_search()` endpoint, `_run_grid_search_background()` function, `process_combination_with_pool()` wrapper)
- **Files to Create**: None
- **Dependencies**: 
  - Must import `load_model_artifact` from grid search module: `from scripts.trade.grid_search_hyperparameters import load_model_artifact`
  - Or implement model loading in API (prefer importing from Python script for consistency)

- **Acceptance Criteria**:
  - [ ] `run_grid_search()` endpoint accepts `model_name: Optional[str] = Query(None, ...)` parameter
  - [ ] Endpoint validates `model_name` if provided (must be one of: `"logreg_platt"`, `"logreg_isotonic"`, `"catboost_platt"`, `"catboost_isotonic"`)
  - [ ] Endpoint raises `HTTPException` with clear error if invalid model name
  - [ ] `_run_grid_search_background()` function signature includes `model_name: Optional[str] = None` parameter
  - [ ] `model_name` passed to `GridSearchConfig` creation (line 368)
  - [ ] `model_name` included in cache key generation (line 1005)
  - [ ] `model_name` passed to background thread args (line 1043-1066)
  - [ ] `process_combination_with_pool()` wrapper loads model artifact using `load_model_artifact(config.model_name)` at start
  - [ ] `process_combination_with_pool()` passes `model_artifact` to `run_simulation_for_games()` calls (line 193)
  - [ ] Import `load_model_artifact` from grid search module: `load_model_artifact = grid_search_module.load_model_artifact`
  - [ ] API request `POST /api/grid-search/run?season=2025-26&model_name=logreg_platt&...` executes successfully
  - [ ] API request `POST /api/grid-search/run?season=2025-26&model_name=invalid&...` returns 400 error with clear message

- **Technical Context**:
  - **Current State**: 
    ```python
    @router.post("/api/grid-search/run")
    def run_grid_search(
        season: str = Query(...),
        # ... other parameters ...
    ) -> dict[str, Any]:
    ```
  - **Target State**: 
    ```python
    @router.post("/api/grid-search/run")
    def run_grid_search(
        season: str = Query(...),
        # ... other parameters ...
        model_name: Optional[str] = Query(None, description="Model name: 'logreg_platt', 'logreg_isotonic', 'catboost_platt', 'catboost_isotonic', or None for ESPN")
    ) -> dict[str, Any]:
        # Validate model_name if provided
        valid_models = ["logreg_platt", "logreg_isotonic", "catboost_platt", "catboost_isotonic"]
        if model_name is not None and model_name not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model_name: {model_name}. Valid options: {valid_models}")
        
        # Pass to background task
        thread = threading.Thread(
            target=_run_grid_search_background,
            args=(
                request_id,
                season,
                # ... other args ...
                model_name,  # Add model_name to args
                dsn
            ),
            daemon=True
        )
    
    def _run_grid_search_background(
        request_id: str,
        season: str,
        # ... other parameters ...
        model_name: Optional[str] = None,  # New parameter
        dsn: str
    ):
        # Create config with model_name
        config = GridSearchConfig(
            # ... other fields ...
            model_name=model_name  # Include model_name
        )
    ```
  - **Implementation**: 
    1. Add `model_name` parameter to endpoint
    2. Add validation
    3. Add `model_name` to `_run_grid_search_background()` function signature
    4. Add `model_name` to background thread args (line 1043-1066)
    5. Include `model_name` in `GridSearchConfig` creation (line 368)
    6. Import `load_model_artifact` in API: `load_model_artifact = grid_search_module.load_model_artifact`
    7. Update `process_combination_with_pool()` to load and pass model artifact (line 154-202)

  - **Pros and Cons**:
  - **Pros**: Clear validation, type-safe, maintains API structure
  - **Cons**: None significant

- **Critical Integration Note**: 
  - The API uses `process_combination_with_pool()` which directly calls `run_simulation_for_games()`, bypassing `process_combination()` from the Python script
  - Therefore, BOTH functions need model loading:
    - `process_combination()` in Python script (for CLI usage)
    - `process_combination_with_pool()` in API (for webapp usage)
  - Both should load model using `load_model_artifact(config.model_name)` and pass to `run_simulation_for_games()`

### Story 2.2: Add Model Selector to Frontend
- **ID**: S19-E2-S2
- **Type**: Feature
- **Priority**: High - Required for user interaction
- **Estimate**: 2-3 hours
- **Phase**: 2
- **Prerequisites**: S19-E2-S1
- **Files to Modify**: 
  - `webapp/static/templates/grid-search.html` (add model selector dropdown)
  - `webapp/static/js/grid-search.js` (add model_name to form submission)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] HTML form has model selector dropdown with id `modelName`
  - [ ] Dropdown options:
    - `""` (empty, default) - labeled "ESPN (default)"
    - `"logreg_platt"` - labeled "Logistic Regression + Platt"
    - `"logreg_isotonic"` - labeled "Logistic Regression + Isotonic"
    - `"catboost_platt"` - labeled "CatBoost + Platt"
    - `"catboost_isotonic"` - labeled "CatBoost + Isotonic"
  - [ ] Default selection is empty (ESPN)
  - [ ] `runGridSearch()` function in `grid-search.js` includes `model_name` in form submission
  - [ ] `model_name` sent as query parameter (or `null` if empty)
  - [ ] UI displays model selector in appropriate location (Basic Settings or Advanced Settings section)
  - [ ] Browser test: Select model, submit form, verify API receives correct `model_name` parameter

- **Technical Context**:
  - **Current State**: 
    ```html
    <!-- No model selector -->
    <select id="season" required>
        <option value="">Loading seasons...</option>
    </select>
    ```
  - **Target State**: 
    ```html
    <div class="sim-input-group">
        <label for="modelName">Probability Model:</label>
        <select id="modelName">
            <option value="">ESPN (default)</option>
            <option value="logreg_platt">Logistic Regression + Platt</option>
            <option value="logreg_isotonic">Logistic Regression + Isotonic</option>
            <option value="catboost_platt">CatBoost + Platt</option>
            <option value="catboost_isotonic">CatBoost + Isotonic</option>
        </select>
    </div>
    ```
    ```javascript
    const params = {
        season: document.getElementById('season').value,
        model_name: document.getElementById('modelName').value || null,  // New
        // ... other params ...
    };
    ```
  - **Implementation**: Add HTML dropdown, update JavaScript form submission

- **Pros and Cons**:
  - **Pros**: Clear UI, easy to use, maintains form structure
  - **Cons**: None significant

### Epic 3: Testing and Validation
**Priority**: Critical - Ensures functionality works correctly
**Estimated Time**: 2-3 hours
**Dependencies**: Must complete Epic 2
**Status**: Not Started
**Phase Assignment**: Phase 3

### Story 3.1: Test All 4 Models Individually
- **ID**: S19-E3-S1
- **Type**: Testing
- **Priority**: Critical - Validates core functionality
- **Estimate**: 1-2 hours
- **Phase**: 3
- **Prerequisites**: S19-E2-S2
- **Files to Modify**: None
- **Files to Create**: Test results documentation
- **Dependencies**: All 4 model files must exist

- **Acceptance Criteria**:
  - [ ] Grid search completes successfully with `model_name=logreg_platt`
  - [ ] Grid search completes successfully with `model_name=logreg_isotonic`
  - [ ] Grid search completes successfully with `model_name=catboost_platt`
  - [ ] Grid search completes successfully with `model_name=catboost_isotonic`
  - [ ] Results differ between models (verify probabilities are different)
  - [ ] Cache keys are unique per model (verify different models produce different cache keys)
  - [ ] Results files written correctly (CSV and JSON)
  - [ ] Command `python scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name logreg_platt --max-games 10 --max-combinations 5` executes successfully
  - [ ] Command `python scripts/trade/grid_search_hyperparameters.py --season 2025-26 --model-name catboost_isotonic --max-games 10 --max-combinations 5` executes successfully

- **Technical Context**:
  - **Test Procedure**:
    1. Run grid search with each model using `--max-games 10 --max-combinations 5` for quick testing
    2. Verify grid search completes without errors
    3. Check output files contain results
    4. Compare results between models (should differ)
    5. Verify cache keys are different for different models
  - **Validation**: Manual testing with small dataset, verify outputs

- **Pros and Cons**:
  - **Pros**: Validates all models work, catches integration issues early
  - **Cons**: Manual testing (automated tests can be added later)

### Story 3.2: Test Backward Compatibility
- **ID**: S19-E3-S2
- **Type**: Testing
- **Priority**: Critical - Ensures existing functionality still works
- **Estimate**: 1 hour
- **Phase**: 3
- **Prerequisites**: S19-E2-S2
- **Files to Modify**: None
- **Files to Create**: Test results documentation
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] Grid search completes successfully without `--model-name` parameter (uses ESPN probabilities)
  - [ ] Grid search completes successfully with `model_name=None` in API (uses ESPN probabilities)
  - [ ] Frontend form submission without model selection works (uses ESPN probabilities)
  - [ ] Results match previous behavior when no model specified
  - [ ] No errors in logs when model not specified
  - [ ] Command `python scripts/trade/grid_search_hyperparameters.py --season 2025-26 --max-games 10 --max-combinations 5` executes successfully (no model parameter)
  - [ ] API request `POST /api/grid-search/run?season=2025-26&...` (no model_name) executes successfully

- **Technical Context**:
  - **Test Procedure**:
    1. Run grid search without model parameter
    2. Verify it uses ESPN probabilities (check logs or results)
    3. Verify no errors occur
    4. Compare behavior to pre-sprint behavior (should be identical)
  - **Validation**: Manual testing, verify backward compatibility

- **Pros and Cons**:
  - **Pros**: Ensures no breaking changes, maintains user trust
  - **Cons**: None significant

### Epic 4: Sprint Quality Assurance
**Priority**: Critical - Ensures quality and documentation
**Estimated Time**: 3-4 hours
**Dependencies**: Must complete Epic 3
**Status**: Not Started
**Phase Assignment**: Phase 4

### Story 4.1: Update Documentation
- **ID**: S19-E4-S1
- **Type**: Documentation
- **Priority**: High - Required for maintainability
- **Estimate**: 1-2 hours
- **Phase**: 4
- **Prerequisites**: S19-E3-S2
- **Files to Modify**: 
  - `scripts/trade/grid_search_hyperparameters.py` (update docstrings)
  - `webapp/api/endpoints/grid_search.py` (update docstrings)
  - `webapp/static/js/grid-search.js` (update comments if needed)
- **Files to Create**: None
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] `GridSearchConfig` docstring updated to document `model_name` field
  - [ ] `get_aligned_data()` docstring updated to document `model_artifact` parameter
  - [ ] `run_grid_search()` endpoint docstring updated to document `model_name` parameter
  - [ ] `_generate_grid_search_cache_key()` docstring updated to document `model_name` parameter
  - [ ] All function signatures have type hints
  - [ ] Code comments explain model selection logic

- **Technical Context**:
  - **Documentation Updates**: Update docstrings, add examples, document model selection behavior
  - **Implementation**: Review all modified functions, update docstrings

- **Pros and Cons**:
  - **Pros**: Improves maintainability, helps future developers
  - **Cons**: Time investment

### Story 4.2: Final Validation and Quality Gates
- **ID**: S19-E4-S2
- **Type**: Quality Assurance
- **Priority**: Critical - Ensures sprint meets quality standards
- **Estimate**: 2 hours
- **Phase**: 4
- **Prerequisites**: S19-E4-S1
- **Files to Modify**: None
- **Files to Create**: Sprint completion report
- **Dependencies**: None

- **Acceptance Criteria**:
  - [ ] All acceptance criteria from previous stories met
  - [ ] Code follows established patterns (no linting errors)
  - [ ] All functions have proper error handling
  - [ ] Backward compatibility verified
  - [ ] Performance acceptable (grid search completes in reasonable time)
  - [ ] No breaking changes introduced
  - [ ] Sprint completion report created with test results

- **Technical Context**:
  - **Validation Steps**:
    1. Run all acceptance criteria checks
    2. Check for linting errors
    3. Verify error handling
    4. Test performance
    5. Create completion report
  - **Implementation**: Comprehensive testing and validation

- **Pros and Cons**:
  - **Pros**: Ensures quality, catches issues before completion
  - **Cons**: Time investment

## Risk Assessment

### Technical Risks
- **Risk 1**: Model loading performance degradation
  - **Probability**: Medium
  - **Impact**: Medium
  - **Mitigation**: Model loading is one-time per worker thread, acceptable overhead
  - **Contingency**: Implement model caching if performance becomes issue

- **Risk 2**: Breaking existing grid searches
  - **Probability**: Low
  - **Impact**: High
  - **Mitigation**: Maintain backward compatibility (None = ESPN probabilities)
  - **Contingency**: Add feature flag to disable model support if needed

- **Risk 3**: SQL query complexity with dynamic column selection
  - **Probability**: Medium
  - **Impact**: Low
  - **Mitigation**: Test thoroughly, handle missing columns gracefully
  - **Contingency**: Simplify query if issues arise

### Business Risks
- **Risk 1**: User confusion about model selection
  - **Probability**: Medium
  - **Impact**: Low
  - **Mitigation**: Clear UI labels, default to "ESPN (default)", add tooltips if needed
  - **Contingency**: Add help text or documentation

## Success Metrics

### Performance Metrics
- **Response Time**: Grid search with models completes within 2x time of ESPN-based search
- **Model Loading Time**: Model loads in <1 second per worker thread
- **Cache Hit Rate**: Cache correctly distinguishes models (100% accuracy)

### Quality Metrics
- **Model Coverage**: All 4 models can be selected and tested (100%)
- **Backward Compatibility**: Existing grid searches without model parameter work correctly (100%)
- **Error Rate**: Model loading/scoring errors <1%

### Business Metrics
- **User Adoption**: Users can successfully run grid search with different models (100% success rate)
- **Development Velocity**: Implementation completed in single sprint (12-16 hours)

## Sprint Completion Checklist

- [ ] All Phase 1 stories completed
- [ ] All Phase 2 stories completed
- [ ] All Phase 3 stories completed
- [ ] All Phase 4 stories completed
- [ ] Documentation updated
- [ ] All acceptance criteria met
- [ ] Quality gates passed
- [ ] Sprint completion report created
- [ ] No breaking changes introduced
- [ ] Backward compatibility verified

---

## Completeness Verification

### Critical Integration Points Verified

**Model Pipeline Flow** (Verified):
1. ✅ `config.model_name` added to `GridSearchConfig` (Story 1.1)
2. ✅ Model loading helper function created (Story 1.2)
3. ✅ Model artifact loaded in `process_combination()` (Python script) - Story 1.2
4. ✅ Model artifact loaded in `process_combination_with_pool()` (API wrapper) - Story 2.1
5. ✅ Model artifact passed to `run_simulation_for_games()` - Story 1.2
6. ✅ Model artifact passed to `get_aligned_data()` - Story 1.3
7. ✅ `get_aligned_data()` uses model to generate probabilities - Story 1.3

**API Integration** (Verified):
1. ✅ `model_name` parameter added to API endpoint - Story 2.1
2. ✅ `model_name` passed to background task - Story 2.1
3. ✅ `model_name` included in `GridSearchConfig` creation - Story 2.1
4. ✅ `model_name` included in cache key - Story 1.4

**Frontend Integration** (Verified):
1. ✅ Model selector dropdown added - Story 2.2
2. ✅ Model selection sent to API - Story 2.2

**Testing Coverage** (Verified):
1. ✅ All 4 models tested individually - Story 3.1
2. ✅ Backward compatibility tested - Story 3.2

### Missing Items Check

- ✅ Model loading location specified (per combination, in both Python script and API)
- ✅ Model artifact passing through pipeline documented
- ✅ API wrapper function (`process_combination_with_pool`) included
- ✅ SQL query updates for model features documented
- ✅ Cache key updates documented
- ✅ Error handling considerations included
- ✅ Performance notes included

### Ready for Implementation

**All Requirements Covered**: ✅ YES
- Backend model integration
- API endpoint updates
- Frontend UI updates
- Testing and validation
- Documentation updates

**All Technical Details Provided**: ✅ YES
- Function signatures
- Code examples
- Integration points
- File paths
- Line number references

## Document Validation

**IMPORTANT**: This sprint follows the comprehensive validation checklist in `SPRINT_STANDARDS.md`.

**Validation Checklist**:
- ✅ Evidence-based sprint plan with code references
- ✅ Technically specific stories with acceptance criteria
- ✅ File paths and dependencies documented
- ✅ Pros and cons analysis included
- ✅ Risk assessment with mitigation strategies
- ✅ Success metrics defined
- ✅ Quality gates specified
- ✅ Critical integration points documented
- ✅ All pipeline functions identified and updated

