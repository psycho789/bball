# Sprint 12 - Win Probability Model Webapp Integration

**Date**: 2025-01-28  
**Sprint Duration**: 3-4 days (20-25 hours total)  
**Sprint Goal**: Integrate the trained win probability model into the webapp with model comparison visualization, divergence alerts, and calibration dashboard.  
**Current Status**: Not Started  
**Target Status**: Users can view ESPN, Kalshi, and our model predictions side-by-side, see divergence alerts, and view calibration metrics.  
**Team Size**: 1  
**Sprint Lead**: Adam Voliva  

## Sprint Standards Reference

This sprint follows `cursor-files/templates/SPRINT_STANDARDS.md` and `cursor-files/templates/SPRINT_TEMPLATE.md`.

## Pre-Sprint Code Quality Baseline

### Model Artifact Exists (Evidence)
- **File**: `artifacts/winprob_logreg_v1.json`
- **Command**: `cd /Users/adamvoliva/Code/bball && test -f artifacts/winprob_logreg_v1.json && echo OK`
- **Expected Output**: `OK`
- **Prerequisite**: Sprint 08 (model training) must be complete

### Model Already in Webapp (Evidence)
- **File**: `webapp/api/models/winprob_logreg_v1.json`
- **Command**: `cd /Users/adamvoliva/Code/bball && test -f webapp/api/models/winprob_logreg_v1.json && echo OK`
- **Expected Output**: `OK`
- **Note**: Model file already exists in webapp directory

### Webapp API Running (Evidence)
- **Command**: `curl http://localhost:8000/api/games?limit=1 | jq '.games | length'`
- **Expected Output**: `1` (or `0` if no games)
- **Prerequisite**: Webapp must be running (`cd webapp && uvicorn api.main:app --reload --port 8000`)

### Database Contains Game State Data (Evidence)
- **Command**: `cd /Users/adamvoliva/Code/bball && set -a && source .env && set +a && psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM derived.pbp_event_state LIMIT 1;" -t`
- **Expected Output**: Integer count > 0
- **Prerequisite**: Database migrations complete, game state materialized

## Database Evidence Template

This sprint uses PostgreSQL via `DATABASE_URL` for:
- Reading game state data (`derived.pbp_event_state`)
- Reading ESPN probabilities (`espn.probabilities_raw_items`)
- Reading game metadata (`espn.scoreboard_games`)
- No database writes required

## Git Usage Restrictions

This sprint does not use git commands.

## Sprint Overview

### Business Context
- **Business Driver**: Provide users with a transparent, independent win probability model to compare against ESPN's proprietary model and Kalshi market prices, enabling better decision-making and model validation.
- **Success Criteria**: 
  - Users can view all three models (ESPN, Kalshi, our model) on the same chart
  - Users see divergence alerts when models disagree significantly
  - Users can view calibration metrics and understand model reliability
  - Model predictions are computed in real-time from game state data

### Technical Context

#### Current System State (Evidence-backed)
- **Model Artifact**: Logistic regression model trained on 2022, calibrated on 2023, evaluated on 2024
  - **File**: `artifacts/winprob_logreg_v1.json`
  - **Features**: `point_differential_scaled`, `time_remaining_regulation_scaled`, `possession_home`, `possession_away`, `possession_unknown`
  - **Calibration**: Platt scaling with `alpha=-0.05174414585551251`, `beta=1.0006731118820542`
  - **Performance**: ECE=0.013, AUC=0.819, LogLoss=0.509 (on 2024 test set)
- **Webapp Architecture**: FastAPI backend with vanilla JavaScript frontend
  - **File**: `webapp/api/main.py:59-88` - FastAPI app with routers
  - **Pattern**: Modular Router Pattern
  - **Frontend**: `webapp/static/js/` - Modular JavaScript files
  - **Chart Library**: TradingView Lightweight Charts v4.1.0
  - **File**: `webapp/static/js/chart.js:43-137` - Chart creation
- **Existing Probabilities Endpoint**: Returns ESPN and Kalshi data
  - **File**: `webapp/api/endpoints/probabilities.py:21-333`
  - **Endpoint**: `GET /api/games/{game_id}/probs`
  - **Returns**: `{espn: [...], kalshi: {...}}`
- **Game State Available**: `derived.pbp_event_state` contains required features
  - **Fields**: `point_differential`, `time_remaining_regulation`, `possession_side`
  - **File**: `db/migrations/007_derived_pbp_event_state_table.sql`
  - **Note**: Must align timestamps with ESPN/Kalshi data

#### Target System State
- **Model Inference Service**: Load model at startup, provide inference function
- **Enhanced Probabilities Endpoint**: Include our model predictions aligned with ESPN/Kalshi
- **Model Comparison Page**: Visual overlay of all three models
- **Divergence Alerts**: Highlight significant disagreements between models
- **Calibration Dashboard**: Aggregate metrics showing model reliability over time

### Sprint Scope
- **In Scope**:
  - Create model inference service (`winprob_service.py`)
  - Enhance `/api/games/{id}/probs` to include our model predictions
  - Create model comparison visualization (frontend)
  - Add divergence detection and alerts
  - Create calibration dashboard endpoint and frontend
  - Load model at webapp startup
- **Out of Scope**:
  - Retraining the model
  - Real-time model updates during live games (future enhancement)
  - Model versioning UI (model is already versioned in artifact)
  - Historical model performance tracking database (use reports for now)
- **Constraints**:
  - Must work with existing chart library (Lightweight Charts)
  - Must align model predictions with ESPN/Kalshi timestamps
  - Model inference must be fast (< 100ms per prediction)
  - Must handle missing game state data gracefully

## Design Decisions

### Design Decision 1: Model Inference Service Architecture

**Problem Statement**: Need to load model artifact, perform inference on game state data, and integrate with existing webapp architecture. Model must be loaded once at startup for performance.

**Chosen Solution**: Singleton service class with lazy loading

**Design Pattern**: Service Pattern + Singleton Pattern  
**Algorithm**: O(1) model loading (once at startup), O(1) per inference  
**Implementation Complexity**: Medium (3-4 hours)  
**Maintenance Overhead**: Low  
**Scalability**: Excellent (model loaded once, inference is fast)

**Pros**:
- Performance: Model loaded once at startup, not per request
- Clean separation: Inference logic isolated from endpoints
- Reusable: Can be used by multiple endpoints
- Testable: Easy to unit test inference logic
- Memory efficient: Single model instance in memory

**Cons**:
- Startup time: Model loading adds ~100-200ms to startup
- Memory: Model stays in memory (acceptable for small logistic regression)

**Rejected Alternatives**:
- **Load model per request**: Too slow, unacceptable latency
- **Separate microservice**: Overkill for single model, adds complexity

**Implementation Details**:
- **File**: `webapp/api/services/winprob_service.py` (new)
- **Class**: `WinProbService`
- **Methods**:
  - `load_model(artifact_path)` - Load model from JSON (called at startup)
  - `predict(game_state)` - Run inference on single game state
  - `predict_batch(game_states)` - Run inference on multiple states (for efficiency)
- **Model Loading**: Called in `main.py` startup event
- **Error Handling**: Graceful degradation if model fails to load

### Design Decision 2: Game State Alignment Strategy

**Problem Statement**: Model requires `point_differential`, `time_remaining_regulation`, and `possession_side` at specific timestamps. Must align these with ESPN/Kalshi timestamps for comparison.

**Chosen Solution**: Query game state for each ESPN timestamp, interpolate if needed

**Design Pattern**: Data Alignment Pattern  
**Algorithm**: O(n) where n = number of ESPN timestamps per game  
**Implementation Complexity**: Medium (4-5 hours)  
**Maintenance Overhead**: Medium (alignment logic)

**Pros**:
- Accurate: Uses actual game state at each timestamp
- Flexible: Can handle missing data gracefully
- Transparent: Clear mapping between timestamps and predictions

**Cons**:
- Database queries: Requires querying `derived.pbp_event_state` for each game
- Complexity: Must handle edge cases (missing data, overtime, etc.)

**Rejected Alternatives**:
- **Pre-compute all predictions**: Too much data, not needed for all games
- **Use ESPN timestamps only**: Less accurate, doesn't use actual game state

**Implementation Details**:
- For each ESPN timestamp, query `derived.pbp_event_state` for closest event
- Use `ORDER BY ABS(EXTRACT(EPOCH FROM (event_time - espn_timestamp))) LIMIT 1`
- Handle missing possession data (map NULL to "unknown")
- Cache game state queries per game (avoid repeated queries)

### Design Decision 3: Divergence Detection Algorithm

**Problem Statement**: Need to identify when models disagree significantly, but "significant" depends on context (game time, score, etc.). Must be computationally efficient.

**Chosen Solution**: Absolute difference threshold with time-weighted importance

**Design Pattern**: Threshold Detection Pattern  
**Algorithm**: O(1) per comparison  
**Implementation Complexity**: Low (2-3 hours)  
**Maintenance Overhead**: Low

**Pros**:
- Simple: Easy to understand and tune
- Fast: O(1) per comparison
- Configurable: Threshold can be adjusted per use case

**Cons**:
- Fixed threshold: Doesn't account for prediction uncertainty
- Context-agnostic: Same threshold for all game situations

**Implementation Details**:
- **Threshold**: Default 0.10 (10 percentage points)
- **Comparison**: `abs(our_model - espn) > threshold` OR `abs(our_model - kalshi) > threshold`
- **Time weighting**: Higher weight for late-game divergences (optional enhancement)
- **Alert format**: `{timestamp, type: "espn_divergence"|"kalshi_divergence", magnitude, our_pred, other_pred}`

### Design Decision 4: Calibration Dashboard Aggregation

**Problem Statement**: Need to compute calibration metrics across many games efficiently. Calibration requires binning predictions and comparing to observed outcomes.

**Chosen Solution**: Pre-compute calibration bins per game, aggregate in endpoint

**Design Pattern**: Aggregation Pattern  
**Algorithm**: O(n) where n = number of games  
**Implementation Complexity**: Medium (4-5 hours)  
**Maintenance Overhead**: Medium (calibration computation)

**Pros**:
- Efficient: Can cache calibration data
- Accurate: Uses actual game outcomes
- Flexible: Can filter by season, date range, etc.

**Cons**:
- Requires game outcomes: Only works for completed games
- Computation: Must compute bins for each game

**Implementation Details**:
- **Binning**: 20 bins (0.0-0.05, 0.05-0.10, ..., 0.95-1.0)
- **Metrics**: ECE (Expected Calibration Error), Brier score, LogLoss
- **Aggregation**: Sum bins across games, compute aggregate metrics
- **Caching**: Cache calibration data for completed games (24 hour TTL)

## Sprint Phases

### Phase 1: Model Inference Service (Duration: 4-5 hours)
**Objective**: Create model loading and inference service, integrate with webapp startup.  
**Dependencies**: Model artifact exists in `webapp/api/models/`  
**Deliverables**:
- `webapp/api/services/__init__.py`
- `webapp/api/services/winprob_service.py`
- Model loading in `webapp/api/main.py` startup event

#### Tasks

**Task 1.1: Create Services Directory and WinProb Service**
- **Files**: `webapp/api/services/__init__.py` (new), `webapp/api/services/winprob_service.py` (new)
- **Effort**: 3-4 hours
- **Prerequisites**: None
- **Design Pattern**: Service Pattern + Singleton Pattern
- **Algorithm**: O(1) model loading, O(1) per inference
- **Steps**:
  1. Create `webapp/api/services/` directory
  2. Create `__init__.py` file
  3. Create `WinProbService` class with:
     - `_model` class variable (singleton)
     - `load_model(artifact_path)` method
     - `predict(point_diff, time_rem, possession)` method
     - `predict_batch(states)` method (optional optimization)
  4. Implement model loading from JSON:
     - Load preprocess parameters (mean/std)
     - Load model weights and intercept
     - Load Platt calibration parameters
  5. Implement feature preprocessing:
     - Scale `point_differential` using `point_diff_mean` and `point_diff_std`
     - Scale `time_remaining_regulation` using `time_rem_mean` and `time_rem_std`
     - One-hot encode possession (home/away/unknown)
  6. Implement logistic regression inference:
     - Compute `z = intercept + sum(weights * features)`
     - Apply sigmoid: `p = 1 / (1 + exp(-z))`
  7. Apply Platt calibration:
     - `p_calibrated = 1 / (1 + exp(-(alpha + beta * logit(p))))`
  8. Add error handling for missing model, invalid inputs
- **Success Criteria**:
  - Service can load model from JSON
  - Service can predict on single game state
  - Predictions are in range [0, 1]
  - Predictions sum to 1.0 for home/away (within float precision)

**Task 1.2: Integrate Model Loading in Webapp Startup**
- **Files**: `webapp/api/main.py` (update)
- **Effort**: 1 hour
- **Prerequisites**: Task 1.1
- **Steps**:
  1. Import `WinProbService` in `main.py`
  2. Add model loading to `@app.on_event("startup")` function
  3. Load model from `webapp/api/models/winprob_logreg_v1.json`
  4. Add error handling (log error, continue startup if model fails)
  5. Add logging for successful model load
- **Success Criteria**:
  - Model loads at webapp startup
  - Startup succeeds even if model fails to load (graceful degradation)
  - Logs indicate model load status

**Task 1.3: Add Unit Tests for Inference Service**
- **Files**: `webapp/api/tests/test_winprob_service.py` (new, optional but recommended)
- **Effort**: 1 hour (optional)
- **Prerequisites**: Task 1.1
- **Steps**:
  1. Create test file
  2. Test model loading
  3. Test prediction on known inputs
  4. Test edge cases (missing possession, extreme values)
- **Success Criteria**:
  - Tests pass
  - Edge cases handled correctly

### Phase 2: Enhanced Probabilities Endpoint (Duration: 5-6 hours)
**Objective**: Add our model predictions to existing probabilities endpoint, aligned with ESPN/Kalshi timestamps.  
**Dependencies**: Phase 1 (model service), existing probabilities endpoint  
**Deliverables**:
- Updated `webapp/api/endpoints/probabilities.py`
- Model predictions in `/api/games/{id}/probs` response

#### Tasks

**Task 2.1: Query Game State for ESPN Timestamps**
- **Files**: `webapp/api/endpoints/probabilities.py` (update)
- **Effort**: 3-4 hours
- **Prerequisites**: Phase 1
- **Design Pattern**: Data Alignment Pattern
- **Algorithm**: O(n) where n = ESPN timestamps per game
- **Steps**:
  1. After fetching ESPN data, extract unique timestamps
  2. For each timestamp, query `derived.pbp_event_state`:
     - Find closest event to timestamp (by `event_time` or `order_number`)
     - Get `point_differential`, `time_remaining_regulation`, `possession_side`
  3. Handle missing data:
     - If no event found, skip that timestamp
     - If `possession_side` is NULL, use "unknown"
  4. Cache game state queries (avoid repeated queries for same game)
  5. Optimize query: Use window function or subquery to find closest event
- **Success Criteria**:
  - Game state data retrieved for each ESPN timestamp
  - Missing data handled gracefully
  - Query performance acceptable (< 500ms for typical game)

**Task 2.2: Generate Model Predictions**
- **Files**: `webapp/api/endpoints/probabilities.py` (update)
- **Effort**: 2 hours
- **Prerequisites**: Tasks 2.1, 1.1
- **Steps**:
  1. Import `WinProbService` in probabilities endpoint
  2. For each game state retrieved, call `winprob_service.predict()`
  3. Map `possession_side` (0/1/NULL) to possession string ("home"/"away"/"unknown")
  4. Store predictions with timestamps
  5. Handle service errors gracefully (log, skip prediction)
- **Success Criteria**:
  - Predictions generated for each game state
  - Predictions aligned with ESPN timestamps
  - Errors handled gracefully

**Task 2.3: Add Model Predictions to Response**
- **Files**: `webapp/api/endpoints/probabilities.py` (update)
- **Effort**: 1 hour
- **Prerequisites**: Task 2.2
- **Steps**:
  1. Add `our_model` array to response structure
  2. Format: `{time: timestamp, home_prob: float, away_prob: float}`
  3. Align with ESPN data structure for consistency
  4. Update response documentation
- **Success Criteria**:
  - Response includes `our_model` array
  - Format matches ESPN data structure
  - Timestamps align with ESPN/Kalshi data

### Phase 3: Model Comparison Visualization (Duration: 5-6 hours)
**Objective**: Update frontend chart to display all three models (ESPN, Kalshi, our model) on the same chart.  
**Dependencies**: Phase 2 (model predictions in API), existing chart.js  
**Deliverables**:
- Updated `webapp/static/js/chart.js`
- Chart displays all three models with different colors

#### Tasks

**Task 3.1: Add Our Model Series to Chart**
- **Files**: `webapp/static/js/chart.js` (update)
- **Effort**: 2-3 hours
- **Prerequisites**: Phase 2
- **Design Pattern**: Factory Pattern (extend existing)
- **Algorithm**: O(n) where n = data points
- **Steps**:
  1. Update `createChart()` function to accept `ourModelData` parameter
  2. Add new series for our model predictions:
     - Use `addLineSeries()` with distinct color (e.g., green)
     - Format data: `[{time: timestamp, value: home_prob}]`
  3. Add legend entry for our model
  4. Ensure all three series are visible and distinguishable
  5. Handle missing our model data gracefully (don't break chart)
- **Success Criteria**:
  - Chart displays all three models
  - Models are visually distinct (different colors)
  - Legend includes all models
  - Chart works even if our model data is missing

**Task 3.2: Update API Call to Include Our Model**
- **Files**: `webapp/static/js/api.js` (update), `webapp/static/js/chart.js` (update)
- **Effort**: 1-2 hours
- **Prerequisites**: Task 3.1
- **Steps**:
  1. Update API call in `api.js` (if separate) or `chart.js`
  2. Pass `our_model` data to `createChart()`
  3. Handle API response structure change
  4. Add error handling for missing our model data
- **Success Criteria**:
  - API response includes our model data
  - Chart receives and displays our model data
  - Missing data handled gracefully

**Task 3.3: Add Model Toggle Controls (Optional Enhancement)**
- **Files**: `webapp/static/js/chart.js` (update), `webapp/static/templates/game-detail.html` (update)
- **Effort**: 2 hours (optional)
- **Prerequisites**: Task 3.1
- **Steps**:
  1. Add checkboxes/toggles for each model (ESPN, Kalshi, Our Model)
  2. Implement show/hide functionality using `series.setVisible()`
  3. Persist toggle state in URL or localStorage
  4. Style toggles to match existing UI
- **Success Criteria**:
  - Users can toggle models on/off
  - Toggle state persists
  - UI is intuitive

### Phase 4: Divergence Alerts (Duration: 4-5 hours)
**Objective**: Detect and display alerts when models disagree significantly.  
**Dependencies**: Phase 2 (model predictions), Phase 3 (visualization)  
**Deliverables**:
- Divergence detection in backend endpoint
- Divergence alerts in frontend chart

#### Tasks

**Task 4.1: Implement Divergence Detection in Backend**
- **Files**: `webapp/api/endpoints/probabilities.py` (update)
- **Effort**: 2-3 hours
- **Prerequisites**: Phase 2
- **Design Pattern**: Threshold Detection Pattern
- **Algorithm**: O(n) where n = aligned data points
- **Steps**:
  1. After generating predictions, align our model with ESPN and Kalshi
  2. For each aligned point, compute differences:
     - `diff_espn = abs(our_model - espn_prob)`
     - `diff_kalshi = abs(our_model - kalshi_price)` (if Kalshi data exists)
  3. Identify divergences:
     - If `diff_espn > threshold` (default 0.10), flag as ESPN divergence
     - If `diff_kalshi > threshold`, flag as Kalshi divergence
  4. Create divergence alerts array:
     - Format: `{time: timestamp, type: "espn"|"kalshi", magnitude: float, our_pred: float, other_pred: float}`
  5. Add to response: `divergence_alerts: [...]`
- **Success Criteria**:
  - Divergences detected correctly
  - Alerts include all necessary information
  - Threshold is configurable (query parameter)

**Task 4.2: Display Divergence Alerts in Chart**
- **Files**: `webapp/static/js/chart.js` (update)
- **Effort**: 2 hours
- **Prerequisites**: Task 4.1
- **Steps**:
  1. Add markers or annotations to chart for divergence points
  2. Use Lightweight Charts markers API:
     - `addPriceLine()` or `addPriceArea()` to highlight divergence
     - Or use `markers` on series
  3. Add tooltip showing divergence details (magnitude, predictions)
  4. Style divergences distinctly (e.g., red for large divergences)
  5. Add legend/key explaining divergence indicators
- **Success Criteria**:
  - Divergences visible on chart
  - Tooltips show divergence details
  - Visual indicators are clear

**Task 4.3: Add Divergence Summary Panel (Optional Enhancement)**
- **Files**: `webapp/static/templates/game-detail.html` (update), `webapp/static/js/chart.js` (update)
- **Effort**: 1-2 hours (optional)
- **Prerequisites**: Task 4.2
- **Steps**:
  1. Add summary panel showing:
     - Total divergences count
     - Max divergence magnitude
     - Average divergence
  2. Filter by type (ESPN vs Kalshi)
  3. Style to match existing UI
- **Success Criteria**:
  - Summary panel displays divergence stats
  - Stats are accurate
  - UI is intuitive

### Phase 5: Calibration Dashboard (Duration: 6-7 hours)
**Objective**: Create calibration dashboard showing model reliability metrics across games.  
**Dependencies**: Completed games with outcomes, model predictions  
**Deliverables**:
- `webapp/api/endpoints/calibration.py` (new endpoint)
- `webapp/static/templates/calibration-dashboard.html` (new template)
- `webapp/static/js/calibration.js` (new frontend module)

#### Tasks

**Task 5.1: Create Calibration Endpoint**
- **Files**: `webapp/api/endpoints/calibration.py` (new)
- **Effort**: 4-5 hours
- **Prerequisites**: Phase 2 (model predictions available)
- **Design Pattern**: Aggregation Pattern
- **Algorithm**: O(n * m) where n = games, m = predictions per game
- **Steps**:
  1. Create new endpoint: `GET /api/calibration/stats`
  2. Query parameters: `season`, `start_date`, `end_date`, `min_games`
  3. For each completed game in date range:
     - Get model predictions (from cache or compute)
     - Get actual outcome (`final_winning_team` from `games` table)
     - Bin predictions into 20 bins (0.0-0.05, 0.05-0.10, ..., 0.95-1.0)
     - Compute observed win rate per bin
  4. Aggregate bins across all games:
     - Sum predictions per bin
     - Sum observed wins per bin
     - Compute average predicted probability per bin
     - Compute observed win rate per bin
  5. Compute aggregate metrics:
     - ECE (Expected Calibration Error)
     - Brier score
     - LogLoss
     - ROC AUC
  6. Return response:
     ```json
     {
       "season": "2024-25",
       "games_count": 1234,
       "overall_metrics": {...},
       "calibration_bins": [...],
       "per_bucket_metrics": [...] // Optional: by time remaining
     }
     ```
  7. Add caching (24 hour TTL for completed games)
- **Success Criteria**:
  - Endpoint returns calibration metrics
  - Metrics are accurate (match evaluation report)
  - Caching works correctly
  - Performance acceptable (< 2 seconds for full season)

**Task 5.2: Create Calibration Dashboard Frontend**
- **Files**: `webapp/static/templates/calibration-dashboard.html` (new), `webapp/static/js/calibration.js` (new)
- **Effort**: 2-3 hours
- **Prerequisites**: Task 5.1
- **Steps**:
  1. Create HTML template for calibration dashboard
  2. Include:
     - Overall metrics display (ECE, Brier, LogLoss, AUC)
     - Calibration curve chart (predicted vs observed)
     - Bin table showing per-bin statistics
     - Season/date range filters
  3. Create `calibration.js` module:
     - Fetch calibration data from API
     - Render calibration curve (use existing chart library or simple line chart)
     - Render metrics and bin table
     - Add filters for season/date range
  4. Add routing for calibration dashboard (`#/calibration`)
  5. Style to match existing dashboard pages
- **Success Criteria**:
  - Dashboard displays calibration metrics
  - Calibration curve is accurate
  - Filters work correctly
  - UI is intuitive

**Task 5.3: Add Calibration Comparison (Optional Enhancement)**
- **Files**: `webapp/static/js/calibration.js` (update)
- **Effort**: 1-2 hours (optional)
- **Prerequisites**: Task 5.2
- **Steps**:
  1. Compare our model calibration to ESPN (if ESPN calibration can be inferred)
  2. Show side-by-side calibration curves
  3. Highlight which model is better calibrated
- **Success Criteria**:
  - Comparison visualization works
  - Clear indication of which model is better

## Sprint Backlog

### Epic 1: Model Inference Service
- [ ] **Task 1.1**: Create services directory and WinProb service (3-4 hours)
- [ ] **Task 1.2**: Integrate model loading in webapp startup (1 hour)
- [ ] **Task 1.3**: Add unit tests for inference service (1 hour, optional)

### Epic 2: Enhanced Probabilities Endpoint
- [ ] **Task 2.1**: Query game state for ESPN timestamps (3-4 hours)
- [ ] **Task 2.2**: Generate model predictions (2 hours)
- [ ] **Task 2.3**: Add model predictions to response (1 hour)

### Epic 3: Model Comparison Visualization
- [ ] **Task 3.1**: Add our model series to chart (2-3 hours)
- [ ] **Task 3.2**: Update API call to include our model (1-2 hours)
- [ ] **Task 3.3**: Add model toggle controls (2 hours, optional)

### Epic 4: Divergence Alerts
- [ ] **Task 4.1**: Implement divergence detection in backend (2-3 hours)
- [ ] **Task 4.2**: Display divergence alerts in chart (2 hours)
- [ ] **Task 4.3**: Add divergence summary panel (1-2 hours, optional)

### Epic 5: Calibration Dashboard
- [ ] **Task 5.1**: Create calibration endpoint (4-5 hours)
- [ ] **Task 5.2**: Create calibration dashboard frontend (2-3 hours)
- [ ] **Task 5.3**: Add calibration comparison (1-2 hours, optional)

## Validation Commands

### Validation 1: Model Service Loads Correctly
- **Command**: Start webapp, check logs for model load message
- **Expected Output**: Log message indicating model loaded successfully
- **Success Criteria**: 
  - Model loads without errors
  - Service is available for inference

### Validation 2: Probabilities Endpoint Includes Our Model
- **Command**: `curl http://localhost:8000/api/games/0022400196/probs | jq '.our_model | length'`
- **Expected Output**: Integer > 0 (number of predictions)
- **Success Criteria**: 
  - Response includes `our_model` array
  - Predictions are in valid range [0, 1]
  - Timestamps align with ESPN data

### Validation 3: Model Comparison Chart Displays All Models
- **Command**: Open browser to `http://localhost:8000/#/games/0022400196`
- **Expected Output**: Chart shows ESPN, Kalshi, and our model lines
- **Success Criteria**: 
  - All three models visible on chart
  - Models are visually distinct
  - Legend includes all models

### Validation 4: Divergence Alerts Work
- **Command**: `curl http://localhost:8000/api/games/0022400196/probs | jq '.divergence_alerts | length'`
- **Expected Output**: Integer >= 0 (number of divergences)
- **Success Criteria**: 
  - Divergences detected when models disagree
  - Alerts include correct information
  - Alerts visible on chart (if any)

### Validation 5: Calibration Dashboard Displays Metrics
- **Command**: `curl http://localhost:8000/api/calibration/stats?season=2024-25 | jq '.overall_metrics'`
- **Expected Output**: JSON with ECE, Brier, LogLoss, AUC
- **Success Criteria**: 
  - Metrics are present and valid
  - Calibration bins are accurate
  - Dashboard page loads and displays data

### Validation 6: Model Predictions Are Accurate
- **Command**: `curl http://localhost:8000/api/games/0022400196/probs | jq '.our_model[0]'`
- **Expected Output**: `{"time": ..., "home_prob": 0.XX, "away_prob": 0.YY}` where `home_prob + away_prob ≈ 1.0`
- **Success Criteria**: 
  - Predictions sum to 1.0 (within float precision)
  - Predictions are in range [0, 1]
  - Predictions align with game state

## Success Metrics

### Performance Metrics
- **Model Inference Latency**: < 100ms per prediction
- **Endpoint Response Time**: < 1 second for typical game (with caching)
- **Calibration Dashboard Load Time**: < 2 seconds for full season

### Quality Metrics
- **Prediction Accuracy**: Predictions sum to 1.0 (within 1e-12)
- **Alignment Accuracy**: Model predictions align with ESPN timestamps (±5 seconds)
- **Calibration Accuracy**: ECE matches evaluation report (within 0.001)

### Functional Metrics
- **Model Comparison**: All three models visible on chart
- **Divergence Detection**: Divergences detected when threshold exceeded
- **Calibration Dashboard**: Metrics displayed correctly for completed games

## Risk Mitigation

### Risk 1: Model Inference Performance Issues
- **Probability**: Low
- **Impact**: Medium (slow endpoint responses)
- **Mitigation**:
  - Use batch prediction if multiple states per game
  - Cache game state queries
  - Optimize database queries (indexes on `game_id`, `event_time`)
- **Contingency**: Add response caching, optimize queries further

### Risk 2: Game State Alignment Complexity
- **Probability**: Medium
- **Impact**: Medium (incorrect predictions)
- **Mitigation**:
  - Use window functions for efficient closest-event queries
  - Handle edge cases (overtime, missing data) explicitly
  - Add validation logging
- **Contingency**: Fall back to simpler alignment strategy, add more logging

### Risk 3: Calibration Computation Performance
- **Probability**: Medium
- **Impact**: Medium (slow dashboard)
- **Mitigation**:
  - Cache calibration data for completed games
  - Compute calibration incrementally (per game)
  - Use materialized views if needed
- **Contingency**: Pre-compute calibration data, add pagination

### Risk 4: Missing Game State Data
- **Probability**: Low-Medium
- **Impact**: Low (graceful degradation)
- **Mitigation**:
  - Handle missing data gracefully (skip predictions)
  - Log missing data for monitoring
  - Provide fallback (use last known state)
- **Contingency**: Add data quality checks, alert on high missing rate

## Post-Sprint Artifacts

### Documentation
- `webapp/api/services/winprob_service.py` - Model inference service
- `webapp/api/endpoints/calibration.py` - Calibration endpoint
- `webapp/static/templates/calibration-dashboard.html` - Calibration dashboard template
- `webapp/static/js/calibration.js` - Calibration frontend module
- Updated `webapp/api/endpoints/probabilities.py` - Enhanced with model predictions
- Updated `webapp/static/js/chart.js` - Model comparison visualization

### Code
- All files listed above with full implementation
- Integration with existing webapp architecture
- Error handling and graceful degradation

### Testing
- Validation commands executed and documented
- Manual testing in browser
- Performance testing for inference latency

## Notes

- Model is already in `webapp/api/models/winprob_logreg_v1.json` (moved from `artifacts/`)
- Model inference is fast (logistic regression), so performance should be good
- Calibration dashboard only works for completed games (need outcomes)
- Consider adding model versioning UI in future sprint
- Monitor model performance over time (drift detection)

---

## Document Validation

This sprint plan follows the standards in `SPRINT_STANDARDS.md` and provides:
- Evidence-based analysis with code references
- Design pattern and algorithm analysis with Big O notation
- Pros/cons for each design decision
- Comprehensive risk assessment
- Detailed implementation plan with phases and tasks
- Success metrics and validation commands





