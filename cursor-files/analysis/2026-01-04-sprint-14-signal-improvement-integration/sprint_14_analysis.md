# Sprint 14 Analysis: Signal Improvement Integration

**Date**: Sun Jan  4 20:12:34 PST 2026  
**Status**: Planning Phase  
**Purpose**: Analyze requirements for integrating canonical dataset into modeling/simulation and implementing interaction terms model  
**Prerequisites**: Sprint 13 complete (canonical dataset `derived.snapshot_features_v1` exists)

---

## Executive Summary

### Key Findings

**Current State**:
- ✅ Canonical dataset `derived.snapshot_features_v1` exists with all required features
- ❌ **Canonical dataset is NOT being used** - existing scripts still use raw tables
- ❌ Modeling script (`train_winprob_logreg.py`) uses Parquet files, not database
- ❌ Simulation script (`simulate_trading_strategy.py`) manually joins ESPN + Kalshi

**Impact**:
- **Duplicate logic**: ESPN/Kalshi alignment logic exists in multiple places
- **Risk of inconsistency**: Different code paths may calculate features differently
- **Performance**: Manual joins are slower than pre-computed materialized view
- **Maintenance burden**: Changes require updates in multiple places

### Critical Issues Identified

1. **Canonical Dataset Not Integrated** (Severity: High)
   - Impact: Duplicate logic, inconsistency risk, maintenance burden
   - Files affected: `train_winprob_logreg.py`, `simulate_trading_strategy.py`

2. **No Signal Improvement Model** (Severity: High)
   - Impact: Still using raw ESPN probabilities, missing interaction terms
   - Missing: `score_diff_div_sqrt_time_remaining` feature not used in modeling

3. **Parquet-Based Training Pipeline** (Severity: Medium)
   - Impact: Training uses Parquet files instead of canonical dataset
   - Missing: Direct database integration for feature access

### Recommended Actions

1. **Integrate Canonical Dataset into Simulation** (Priority: High)
   - Update `simulate_trading_strategy.py` to use `derived.snapshot_features_v1`
   - Remove duplicate ESPN/Kalshi alignment logic
   - Estimated effort: 8-12 hours

2. **Integrate Canonical Dataset into Modeling** (Priority: High)
   - Update `train_winprob_logreg.py` to query canonical dataset
   - Replace Parquet-based pipeline with database queries
   - Estimated effort: 12-16 hours

3. **Implement Interaction Terms Model** (Priority: High)
   - Train model using `score_diff_div_sqrt_time_remaining` feature
   - Compare performance vs baseline (raw ESPN probabilities)
   - Estimated effort: 16-20 hours

4. **Validate Improved Signal** (Priority: High)
   - Run grid search with improved signal
   - Compare metrics: logloss, Brier score, net profit
   - Estimated effort: 8-12 hours

### Success Metrics

- **Code Integration**: 
  - Baseline: 0% of scripts use canonical dataset
  - Target: 100% of modeling/simulation scripts use canonical dataset
  
- **Signal Quality**:
  - Baseline: Raw ESPN probabilities (logloss/Brier TBD)
  - Target: Improved logloss/Brier with interaction terms model
  
- **Performance**:
  - Baseline: Manual joins in simulation (slow)
  - Target: Single query to canonical dataset (< 100ms per game)
  
- **Code Maintainability**:
  - Baseline: Duplicate alignment logic in 2+ places
  - Target: Single source of truth (canonical dataset)

---

## Problem Statement

### Current Situation

**Sprint 13 Accomplishments**:
- ✅ Created `derived.snapshot_features_v1` materialized view
- ✅ Includes all required features: ESPN probs, game state, interactions, lags, Kalshi data
- ✅ Properly aligned (60-second timestamp window)
- ✅ Indexed for performance

**Current Usage**:
- ❌ `scripts/train_winprob_logreg.py`: Reads from Parquet files (`build_winprob_snapshots_parquet.py`)
- ❌ `scripts/simulate_trading_strategy.py`: Manually joins `espn.probabilities_raw_items` + `kalshi.candlesticks`
- ❌ No scripts use `derived.snapshot_features_v1` yet

**Gap Analysis**:
- Canonical dataset exists but is orphaned (not integrated)
- Existing scripts have duplicate logic that canonical dataset replaces
- No signal improvement model implemented (still using raw ESPN probabilities)

### Pain Points

1. **Duplicate Logic**:
   - `simulate_trading_strategy.py` has complex ESPN/Kalshi alignment logic (200+ lines)
   - Canonical dataset already does this alignment
   - Risk: Logic drift if alignment logic changes in one place but not another

2. **Performance**:
   - Manual joins in simulation are slow (complex timestamp matching)
   - Canonical dataset is pre-computed (materialized view) = fast queries
   - Current: Multiple queries + Python-side alignment
   - Target: Single query to canonical dataset

3. **Feature Inconsistency**:
   - Modeling may calculate features differently than simulation
   - No single source of truth for feature definitions
   - Risk: Model trained on different features than simulation uses

4. **Missing Signal Improvement**:
   - Still using raw ESPN probabilities
   - Interaction terms (`score_diff_div_sqrt_time_remaining`) exist in canonical dataset but not used
   - No model improvement (autoregressive, interaction terms, CatBoost)

### Business Impact

**Performance Impact**:
- Simulation queries: Current manual joins take seconds per game
- Target: Single canonical dataset query < 100ms per game
- Grid search: Faster simulation = faster hyperparameter optimization

**Signal Quality Impact**:
- Current: Raw ESPN probabilities (uncalibrated, no context)
- Target: Interaction terms model (captures game context, better predictions)
- Expected: Lower logloss/Brier, better calibration, more profitable trades

**Maintenance Impact**:
- Current: Changes require updates in multiple places
- Target: Single source of truth (canonical dataset)
- Expected: Easier to maintain, less risk of bugs

### Success Criteria

1. **Integration Complete**:
   - [ ] `simulate_trading_strategy.py` uses canonical dataset (no manual joins)
   - [ ] `train_winprob_logreg.py` uses canonical dataset (no Parquet files)
   - [ ] All feature calculations come from canonical dataset

2. **Signal Improvement**:
   - [ ] Interaction terms model trained and validated
   - [ ] Logloss/Brier improved vs baseline
   - [ ] Grid search shows improved profitability

3. **Performance**:
   - [ ] Simulation queries < 100ms per game
   - [ ] Training data loading < 5 seconds for full season

4. **Code Quality**:
   - [ ] No duplicate alignment logic
   - [ ] Single source of truth for features
   - [ ] Tests validate canonical dataset usage

---

## Current State Analysis

### System Architecture Overview

**Canonical Dataset** (`derived.snapshot_features_v1`):
- **Type**: Materialized view (pre-computed)
- **Schema**: 24 columns (keys, ESPN, game state, interactions, lags, Kalshi)
- **Uniqueness**: `(season_label, game_id, sequence_number, snapshot_ts)`
- **Refresh**: Manual (`REFRESH MATERIALIZED VIEW CONCURRENTLY`)
- **Performance**: Indexed, fast queries (< 100ms per game)

**Current Scripts**:

1. **`scripts/train_winprob_logreg.py`**:
   - **Input**: Parquet files from `build_winprob_snapshots_parquet.py`
   - **Features**: `point_differential`, `time_remaining_regulation`, `possession`
   - **Missing**: Interaction terms, lagged features, Kalshi data
   - **Issue**: Not using canonical dataset

2. **`scripts/simulate_trading_strategy.py`**:
   - **Input**: Manual joins of `espn.probabilities_raw_items` + `kalshi.candlesticks`
   - **Alignment**: Complex timestamp matching logic (60-second window)
   - **Features**: ESPN probs, Kalshi prices (bid/ask/mid)
   - **Issue**: Duplicate logic, not using canonical dataset

### Code Quality Assessment

**Duplicate Logic**:
- ESPN/Kalshi alignment: Exists in `simulate_trading_strategy.py` (~200 lines)
- Canonical dataset: Already implements this alignment
- Risk: Logic drift, maintenance burden

**Feature Calculation**:
- Current: Ad-hoc calculations in different places
- Target: All features from canonical dataset
- Risk: Inconsistency between modeling and simulation

**Performance**:
- Current: Multiple queries + Python-side processing
- Target: Single query to materialized view
- Expected improvement: 10-100x faster

### Dependency Analysis

**Sprint 13 Dependencies**:
- ✅ Canonical dataset exists (`derived.snapshot_features_v1`)
- ✅ Migration file exists (`db/migrations/032_derived_snapshot_features_v1.sql`)
- ✅ Indexes created
- ✅ Documentation exists

**External Dependencies**:
- Database: PostgreSQL with canonical dataset materialized view
- Python: `psycopg`, `pandas`, `numpy` (already installed)
- No new dependencies required

**Parallel Work Opportunities**:
- Integration work can proceed in parallel:
  - Story 1: Simulation integration (independent)
  - Story 2: Modeling integration (independent)
  - Story 3: Interaction terms model (depends on Story 2)

---

## Requirements Analysis

### Functional Requirements

#### FR1: Integrate Canonical Dataset into Simulation

**Description**: Update `simulate_trading_strategy.py` to use `derived.snapshot_features_v1` instead of manual joins.

**Acceptance Criteria**:
- [ ] `get_aligned_data()` function queries canonical dataset (single query)
- [ ] Removed duplicate ESPN/Kalshi alignment logic
- [ ] Simulation produces identical results (regression test)
- [ ] Query performance < 100ms per game

**Technical Details**:
- Replace `get_aligned_data()` implementation
- Query: `SELECT * FROM derived.snapshot_features_v1 WHERE game_id = %s ORDER BY sequence_number`
- Map canonical dataset columns to simulation data structure
- Handle NULL Kalshi data gracefully (already handled in canonical dataset)

**Estimated Effort**: 8-12 hours

#### FR2: Integrate Canonical Dataset into Modeling

**Description**: Update `train_winprob_logreg.py` to query canonical dataset instead of Parquet files.

**Acceptance Criteria**:
- [ ] Training script queries canonical dataset directly
- [ ] Removed Parquet file dependency (or made optional)
- [ ] Features match canonical dataset schema
- [ ] Training produces identical or better results

**Technical Details**:
- Replace Parquet reading with database query
- Query: `SELECT * FROM derived.snapshot_features_v1 WHERE season_label IN (...) ORDER BY game_id, sequence_number`
- Map canonical dataset columns to model features
- Handle train/validation/test splits (by game, not by snapshot)

**Estimated Effort**: 12-16 hours

#### FR3: Implement Interaction Terms Model

**Description**: Train model using `score_diff_div_sqrt_time_remaining` feature from canonical dataset.

**Acceptance Criteria**:
- [ ] Model uses `score_diff_div_sqrt_time_remaining` as feature
- [ ] Model trained on canonical dataset
- [ ] Logloss/Brier improved vs baseline (raw ESPN probabilities)
- [ ] Model validated on held-out games

**Technical Details**:
- Features: `espn_home_prob`, `score_diff_div_sqrt_time_remaining`, `time_remaining`, `period`
- Model: Logistic regression with interaction terms (or CatBoost)
- Calibration: Platt scaling on validation set
- Validation: Signal metrics (logloss, Brier, ECE) + trading metrics (net profit)

**Estimated Effort**: 16-20 hours

#### FR4: Validate Improved Signal

**Description**: Run grid search with improved signal and compare vs baseline.

**Acceptance Criteria**:
- [ ] Grid search runs with improved signal
- [ ] Signal metrics improved (logloss, Brier, ECE)
- [ ] Trading metrics improved (net profit, win rate)
- [ ] Results documented and compared to baseline

**Technical Details**:
- Run grid search with interaction terms model predictions
- Compare to baseline (raw ESPN probabilities)
- Metrics: Logloss, Brier, ECE, net profit, trade count, win rate
- Document findings

**Estimated Effort**: 8-12 hours

### Non-Functional Requirements

#### NFR1: Performance

**Requirement**: Simulation queries must be < 100ms per game.

**Current**: Manual joins take seconds per game.

**Target**: Single canonical dataset query < 100ms per game.

**Validation**: Measure query time for 10 games, average < 100ms.

#### NFR2: Backward Compatibility

**Requirement**: Simulation must produce identical results (regression test).

**Validation**: Run simulation on 10 games with old vs new code, compare trade results.

#### NFR3: Code Maintainability

**Requirement**: Single source of truth for features (canonical dataset).

**Validation**: No duplicate alignment logic, all features from canonical dataset.

---

## Technical Design

### Integration Strategy

#### Phase 1: Simulation Integration

**Approach**: Replace `get_aligned_data()` function to query canonical dataset.

**Current Implementation** (`simulate_trading_strategy.py:82-400`):
- Manual joins of `espn.probabilities_raw_items` + `kalshi.candlesticks`
- Complex timestamp alignment logic
- Python-side data processing

**New Implementation**:
```python
def get_aligned_data(
    conn: psycopg.Connection,
    game_id: str,
    exclude_first_seconds: int = 0,
    exclude_last_seconds: int = 0,
    use_trade_data: bool = False  # Keep for backward compatibility
) -> tuple[list[dict[str, Any]], Optional[int], Optional[int], Optional[int]]:
    """
    Get aligned ESPN and Kalshi data from canonical dataset.
    
    Args:
        conn: Database connection
        game_id: ESPN game_id
        exclude_first_seconds: Exclude first N seconds of game
        exclude_last_seconds: Exclude last N seconds of game
        use_trade_data: Ignored (canonical dataset uses candlesticks)
    
    Returns:
        (aligned_data, game_start_timestamp, game_duration_seconds, actual_outcome)
    """
    # Query canonical dataset
    query = """
    SELECT 
        sequence_number,
        snapshot_ts,
        espn_home_prob,
        espn_away_prob,
        score_diff,
        time_remaining,
        period,
        kalshi_home_mid_price,
        kalshi_home_bid,
        kalshi_home_ask,
        kalshi_away_mid_price,
        kalshi_away_bid,
        kalshi_away_ask
    FROM derived.snapshot_features_v1
    WHERE season_label = '2025-26'
      AND game_id = %s
    ORDER BY sequence_number
    """
    
    # Execute query and map to simulation data structure
    # ... (implementation details)
```

**Benefits**:
- Single query instead of multiple joins
- Pre-computed alignment (fast)
- Consistent with canonical dataset

**Risks**:
- Need to verify data structure matches simulation expectations
- Need regression test to ensure identical results

#### Phase 2: Modeling Integration

**Approach**: Replace Parquet reading with database query.

**Current Implementation** (`train_winprob_logreg.py:74-100`):
- Reads Parquet file: `build_winprob_snapshots_parquet.py`
- Features: `point_differential`, `time_remaining_regulation`, `possession`
- Missing: Interaction terms, lagged features

**New Implementation**:
```python
def load_training_data(
    conn: psycopg.Connection,
    train_seasons: list[str],
    calib_season: Optional[str],
    test_season: Optional[str]
) -> tuple[pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load training data from canonical dataset.
    
    Args:
        conn: Database connection
        train_seasons: List of season labels for training
        calib_season: Season label for calibration (optional)
        test_season: Season label for testing (optional)
    
    Returns:
        (train_df, calib_df, test_df)
    """
    # Query canonical dataset
    query = """
    SELECT 
        season_label,
        game_id,
        sequence_number,
        snapshot_ts,
        espn_home_prob,
        score_diff,
        time_remaining,
        period,
        score_diff_div_sqrt_time_remaining,
        espn_home_prob_lag_1,
        espn_home_prob_delta_1,
        kalshi_home_mid_price
    FROM derived.snapshot_features_v1
    WHERE season_label = ANY(%s)
    ORDER BY game_id, sequence_number
    """
    
    # Execute query and split by game (not by snapshot)
    # ... (implementation details)
```

**Benefits**:
- Direct database access (no Parquet files)
- Access to all canonical dataset features
- Consistent with simulation

**Risks**:
- Need to handle train/validation/test splits correctly (by game, not by snapshot)
- Need to verify feature mapping matches model expectations

#### Phase 3: Interaction Terms Model

**Approach**: Train model using interaction terms from canonical dataset.

**Model Architecture**:
- **Features**: 
  - `espn_home_prob` (baseline)
  - `score_diff_div_sqrt_time_remaining` (interaction term)
  - `time_remaining` (game state)
  - `period` (game phase)
  - `espn_home_prob_lag_1` (momentum)
  - `espn_home_prob_delta_1` (change)
- **Model**: Logistic regression with L2 regularization (or CatBoost)
- **Calibration**: Platt scaling on validation set
- **Output**: Calibrated probability prediction

**Training Pipeline**:
1. Load data from canonical dataset
2. Split by game (train/validation/test)
3. Train model with interaction terms
4. Apply Platt scaling on validation set
5. Evaluate on test set (signal metrics + trading metrics)

**Validation**:
- Signal metrics: Logloss, Brier, ECE
- Trading metrics: Net profit, trade count, win rate (via simulation)

### Data Flow

**Current Flow**:
```
Parquet Files → train_winprob_logreg.py → Model
Raw Tables → simulate_trading_strategy.py → Simulation
```

**Target Flow**:
```
derived.snapshot_features_v1 → train_winprob_logreg.py → Model
derived.snapshot_features_v1 → simulate_trading_strategy.py → Simulation
```

**Benefits**:
- Single source of truth
- Consistent features
- Fast queries (materialized view)

---

## Risk Analysis

### Technical Risks

1. **Data Structure Mismatch** (Risk: Medium)
   - **Issue**: Canonical dataset structure may not match simulation expectations
   - **Mitigation**: Regression test to verify identical results
   - **Contingency**: Map canonical dataset columns to simulation structure

2. **Performance Regression** (Risk: Low)
   - **Issue**: Query performance may be slower than expected
   - **Mitigation**: Materialized view is pre-computed, should be fast
   - **Contingency**: Add more indexes if needed

3. **Model Training Issues** (Risk: Medium)
   - **Issue**: Interaction terms model may not improve signal
   - **Mitigation**: Validate on held-out games, compare to baseline
   - **Contingency**: Try different interaction terms or model architectures

### Data Risks

1. **Canonical Dataset Refresh** (Risk: Low)
   - **Issue**: Materialized view needs refresh when new data added
   - **Mitigation**: Document refresh strategy, add reminder
   - **Contingency**: Manual refresh command exists

2. **Missing Kalshi Data** (Risk: Low)
   - **Issue**: Some games don't have Kalshi data (NULL in canonical dataset)
   - **Mitigation**: Canonical dataset already handles NULL gracefully
   - **Contingency**: Simulation already handles missing Kalshi data

### Integration Risks

1. **Backward Compatibility** (Risk: Medium)
   - **Issue**: Changes may break existing functionality
   - **Mitigation**: Regression tests, gradual migration
   - **Contingency**: Keep old code path as fallback initially

2. **Feature Mapping** (Risk: Medium)
   - **Issue**: Canonical dataset columns may not map directly to model features
   - **Mitigation**: Create mapping layer, validate feature names
   - **Contingency**: Add feature transformation layer if needed

---

## Implementation Plan

### Sprint 14 Scope

**Epic 1: Integrate Canonical Dataset into Simulation** (Priority: High)
- Story 1.1: Update `get_aligned_data()` to use canonical dataset
- Story 1.2: Remove duplicate alignment logic
- Story 1.3: Regression test (verify identical results)
- Story 1.4: Performance validation (< 100ms per game)

**Epic 2: Integrate Canonical Dataset into Modeling** (Priority: High)
- Story 2.1: Update `train_winprob_logreg.py` to query canonical dataset
- Story 2.2: Remove Parquet dependency (or make optional)
- Story 2.3: Validate feature mapping
- Story 2.4: Test training pipeline

**Epic 3: Implement Interaction Terms Model** (Priority: High)
- Story 3.1: Train model with interaction terms
- Story 3.2: Apply Platt scaling
- Story 3.3: Validate signal metrics (logloss, Brier, ECE)
- Story 3.4: Compare vs baseline

**Epic 4: Validate Improved Signal** (Priority: High)
- Story 4.1: Run grid search with improved signal
- Story 4.2: Compare trading metrics vs baseline
- Story 4.3: Document findings

### Estimated Effort

**Total**: 44-60 hours

**Breakdown**:
- Epic 1: 8-12 hours
- Epic 2: 12-16 hours
- Epic 3: 16-20 hours
- Epic 4: 8-12 hours

### Dependencies

**Sprint 13 Dependencies**:
- ✅ Canonical dataset exists
- ✅ Migration file exists
- ✅ Documentation exists

**External Dependencies**:
- Database: PostgreSQL with canonical dataset
- Python: `psycopg`, `pandas`, `numpy` (already installed)

**Parallel Work**:
- Epic 1 and Epic 2 can proceed in parallel
- Epic 3 depends on Epic 2
- Epic 4 depends on Epic 3

### Success Criteria

**Integration**:
- [ ] Simulation uses canonical dataset (no manual joins)
- [ ] Modeling uses canonical dataset (no Parquet files)
- [ ] All features from canonical dataset

**Signal Improvement**:
- [ ] Interaction terms model trained
- [ ] Logloss/Brier improved vs baseline
- [ ] Grid search shows improved profitability

**Performance**:
- [ ] Simulation queries < 100ms per game
- [ ] Training data loading < 5 seconds for full season

**Code Quality**:
- [ ] No duplicate alignment logic
- [ ] Single source of truth for features
- [ ] Tests validate canonical dataset usage

---

## Recommendations

### Immediate Actions (Sprint 14)

1. **Start with Simulation Integration** (Epic 1)
   - Lower risk (simpler changes)
   - Immediate performance benefit
   - Validates canonical dataset usage

2. **Then Modeling Integration** (Epic 2)
   - Enables interaction terms model
   - Validates feature mapping
   - Sets foundation for signal improvement

3. **Implement Interaction Terms Model** (Epic 3)
   - Core signal improvement work
   - Validates canonical dataset value
   - Enables comparison vs baseline

4. **Validate Improved Signal** (Epic 4)
   - Confirms signal improvement
   - Documents findings
   - Sets baseline for future work

### Future Enhancements (Post-Sprint 14)

1. **Add More Features**
   - Rolling statistics (mean, std over last N snapshots)
   - Additional interaction terms
   - Time-of-game features (Q1, Q2-Q3, Q4)

2. **CatBoost Model**
   - More powerful than logistic regression
   - Automatic feature interactions
   - Requires more data and tuning

3. **Automated Refresh**
   - Schedule canonical dataset refresh after data ingestion
   - Monitor refresh performance
   - Alert on refresh failures

---

## Conclusion

Sprint 14 focuses on **integrating the canonical dataset** (built in Sprint 13) into existing scripts and **implementing the interaction terms model** to improve signal quality.

**Key Objectives**:
1. Replace duplicate logic with canonical dataset queries
2. Improve signal quality using interaction terms
3. Validate improved signal with grid search

**Expected Outcomes**:
- Faster simulation (single query vs manual joins)
- Better signal quality (interaction terms model)
- Improved profitability (validated with grid search)
- Single source of truth (canonical dataset)

**Success Metrics**:
- 100% of scripts use canonical dataset
- Improved logloss/Brier vs baseline
- Simulation queries < 100ms per game
- No duplicate alignment logic

This sprint builds on Sprint 13's foundation and enables signal improvement work to proceed with a consistent, fast, and maintainable data pipeline.

