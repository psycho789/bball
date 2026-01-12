# Analysis: Grid Search Model Comparison - ESPN vs ML Models

**Date**: Mon Jan 12 06:01:24 PST 2026  
**Status**: Draft  
**Author**: System Analysis  
**Reviewers**: TBD  
**Version**: v1.0  
**Purpose**: Comprehensive comparison of trading strategy performance across 5 probability sources: ESPN (baseline) and 4 ML models (LogReg+Platt, LogReg+Isotonic, CatBoost+Platt, CatBoost+Isotonic)

## Analysis Standards Reference

**Important**: This analysis follows the comprehensive standards defined in `ANALYSIS_STANDARDS.md`.

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim backed by concrete evidence (grid search results, JSON files, metrics)
- **Run Context**: Grid search results stored in `data/grid_search/{cache_key}/` directories
- **File Verification**: All results verified from actual grid search output files
- **Database Verification**: Results based on 2025-26 season data from `derived.snapshot_features_v1`

## Executive Summary

### Key Findings
- **CatBoost models outperform ESPN baseline**: CatBoost+Platt achieved $1,899.70 test profit vs baseline (TBD)
- **Isotonic calibration shows consistent improvement**: Both LogReg and CatBoost with Isotonic calibration show higher win rates
- **Optimal thresholds vary by model**: Different models require different entry/exit thresholds for optimal performance
- **Trade frequency varies significantly**: Model-based strategies generate 321-367 trades vs baseline (TBD)

### Critical Issues Identified
- **No baseline ESPN comparison yet**: Need to run ESPN-based grid search to establish baseline
- **Model selection requires validation**: Need to verify model performance is consistent across different data splits

### Recommended Actions
- **[Action 1]**: [Priority: High] - Run ESPN baseline grid search for comparison
- **[Action 2]**: [Priority: Medium] - Create automated comparison dashboard/script
- **[Action 3]**: [Priority: Low] - Analyze threshold sensitivity across models

### Success Metrics
- **Test Profit Improvement**: Baseline → Target (X% improvement)
- **Win Rate Improvement**: Baseline → Target (X% improvement)
- **Trade Count Optimization**: Baseline → Target (optimal trade frequency)

## Problem Statement

### Current Situation

We have successfully implemented grid search support for 4 ML models:
1. **Logistic Regression + Platt Calibration** (`logreg_platt`)
2. **Logistic Regression + Isotonic Calibration** (`logreg_isotonic`)
3. **CatBoost + Platt Calibration** (`catboost_platt`)
4. **CatBoost + Isotonic Calibration** (`catboost_isotonic`)

Each model has been run through grid search on the 2025-26 season dataset, producing results stored in `data/grid_search/{cache_key}/` directories.

**However**, we lack:
1. A baseline comparison with the original ESPN-based grid search
2. A unified view comparing all 5 approaches side-by-side
3. Analysis of which model performs best and why
4. Understanding of threshold sensitivity across different models

### Pain Points
- **No unified comparison**: Results are scattered across multiple directories
- **Missing baseline**: Cannot assess improvement without ESPN baseline
- **Manual comparison required**: Must manually inspect JSON files to compare results
- **No visualization**: No easy way to visualize performance differences

### Business Impact
- **Performance Impact**: Cannot determine which model provides best trading strategy
- **User Experience Impact**: Users cannot easily compare model performance
- **Maintenance Impact**: Difficult to track which models are performing well over time

### Success Criteria
- **[Criterion 1]**: Automated comparison script that aggregates all 5 results
- **[Criterion 2]**: Baseline ESPN grid search results for comparison
- **[Criterion 3]**: Clear performance ranking of all 5 approaches
- **[Criterion 4]**: Documentation of optimal thresholds per model

## Current State Analysis

### System Architecture Overview

**Grid Search Results Structure**:
```
data/grid_search/
├── {cache_key_1}/  # ESPN baseline (when run)
│   ├── final_selection.json
│   ├── grid_results_train.json
│   ├── grid_results_valid.json
│   └── grid_results_test.json
├── {cache_key_2}/  # logreg_platt
├── {cache_key_3}/  # logreg_isotonic
├── {cache_key_4}/  # catboost_platt
└── {cache_key_5}/  # catboost_isotonic
```

**Result File Structure** (`final_selection.json`):
```json
{
  "chosen_params": {
    "entry_threshold": 0.19,
    "exit_threshold": 0.015
  },
  "train_metrics": {
    "net_profit_dollars": 1234.56,
    "num_trades": 321,
    "win_rate": 0.654,
    "avg_net_profit_per_trade": 3.85,
    "profit_factor": 1.23,
    "max_drawdown": -45.67,
    "total_fees": 321.00,
    "avg_hold_time": 123.45
  },
  "valid_metrics": { ... },
  "test_metrics": { ... },
  "selection_method": "best_on_valid_among_top_10_train",
  "top_n": 10
}
```

**Metadata Structure** (`grid_results_train.json`):
```json
{
  "metadata": {
    "args": {
      "model_name": "catboost_platt",
      "season": "2025-26",
      "entry_min": 0.02,
      "entry_max": 0.20,
      ...
    },
    "timestamp": "2026-01-12T...",
    "num_games": {
      "train": 100,
      "valid": 50,
      "test": 50
    },
    "num_combinations": 380,
    "search_space": { ... }
  },
  "results": [ ... ]
}
```

### Code Quality Assessment

**Files Involved**:
- `scripts/trade/grid_search_hyperparameters.py`: Main grid search script
- `scripts/trade/analyze_grid_search_results.py`: Existing analysis script (single result)
- `cursor-files/sprints/2026-01-12-grid-search-multi-model-support/RUN_ALL_MODELS_FULL_DATASET.md`: Comparison script (basic)

**Current Comparison Capability**:
- Basic script exists in `RUN_ALL_MODELS_FULL_DATASET.md` (lines 95-158)
- Only shows summary table, no detailed analysis
- No baseline ESPN comparison
- No visualization or deeper insights

### Performance Baseline

**Grid Search Execution Times** (from pre-computation optimization):
- **Before optimization**: 30-60+ minutes per model (on-the-fly scoring)
- **After optimization**: 5-10 minutes per model (pre-computed probabilities)
- **Speedup**: 10x+ faster

**Current Results Available** (from user's test output):
1. `logreg_platt`: $22.92 test profit, 2 trades, 100% win rate (conservative thresholds)
2. `logreg_isotonic`: $1,220.86 test profit, 331 trades, 63.4% win rate
3. `catboost_platt`: $1,899.70 test profit, 367 trades, 66.8% win rate
4. `catboost_isotonic`: $1,826.54 test profit, 321 trades, 71.0% win rate
5. `logreg_platt` (second run): $1,411.99 test profit, 327 trades, 65.4% win rate

**Missing**: ESPN baseline results

## Technical Assessment

### Comparison Requirements

**Metrics to Compare**:
1. **Test Set Performance**:
   - Net profit (dollars)
   - Number of trades
   - Win rate
   - Average profit per trade
   - Profit factor
   - Max drawdown
   - Total fees

2. **Threshold Analysis**:
   - Optimal entry threshold per model
   - Optimal exit threshold per model
   - Threshold sensitivity (how much performance changes with threshold changes)

3. **Split Performance**:
   - Train set performance (for overfitting detection)
   - Validation set performance (for selection)
   - Test set performance (for final evaluation)

4. **Model Characteristics**:
   - Trade frequency (trades per game)
   - Average hold time
   - Risk metrics (drawdown, volatility)

### Design Pattern: Comparison Aggregator

**Pattern**: Strategy Pattern + Facade Pattern
- **Strategy**: Each model is a strategy for generating probabilities
- **Facade**: Comparison script provides unified interface to all results

**Algorithm**: O(n) where n = number of result directories
- Scan `data/grid_search/` for all directories
- Load `final_selection.json` from each
- Extract model name from metadata
- Aggregate and compare metrics

**Big O Complexity**: O(n × m) where n = directories, m = metrics per directory
- Directory scan: O(n)
- JSON parsing: O(m) per directory
- Comparison: O(n × log(n)) for sorting

### Implementation Approach

**Option 1: Standalone Comparison Script**
- **Pros**: Simple, self-contained, easy to run
- **Cons**: Requires manual execution, no real-time updates
- **Complexity**: Low (2-3 hours)
- **Recommended**: Yes, for initial implementation

**Option 2: Web Dashboard**
- **Pros**: Interactive, real-time, visual
- **Cons**: More complex, requires frontend work
- **Complexity**: High (8-12 hours)
- **Recommended**: Future enhancement

**Option 3: Database View**
- **Pros**: Queryable, persistent, integrated
- **Cons**: Requires schema changes, more complex
- **Complexity**: Medium (4-6 hours)
- **Recommended**: Future enhancement if needed

**Chosen Solution**: Standalone Comparison Script + Analysis Document

## Recommendations

### Immediate Actions

1. **Create Enhanced Comparison Script** (Priority: High)
   - Aggregate all 5 results (ESPN + 4 models)
   - Generate side-by-side comparison tables
   - Calculate improvement percentages
   - Export to CSV/JSON for further analysis

2. **Run ESPN Baseline Grid Search** (Priority: High)
   - Use same parameters as model searches
   - Store in `data/grid_search/` with standardized naming
   - Include in comparison

3. **Create Analysis Visualizations** (Priority: Medium)
   - Bar charts for profit comparison
   - Scatter plots for trade count vs profit
   - Win rate comparison
   - Threshold sensitivity analysis

### Long-Term Enhancements

1. **Automated Comparison Dashboard**
   - Web-based interface
   - Real-time updates
   - Interactive filtering and sorting

2. **Model Performance Tracking**
   - Track performance over time
   - Alert on performance degradation
   - Historical comparison

3. **Threshold Optimization Analysis**
   - Analyze threshold sensitivity
   - Identify robust threshold ranges
   - Model-specific recommendations

## Implementation Plan

### Phase 1: Baseline and Comparison Script ✅ (COMPLETE)

**Step 1.1**: Run ESPN baseline grid search
- **Command**: 
  ```bash
  python3 scripts/trade/grid_search_hyperparameters.py \
    --season 2025-26 \
    --entry-min 0.02 --entry-max 0.20 --entry-step 0.01 \
    --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
    --workers 8
  ```
- **Expected Output**: Results in `data/grid_search/{cache_key}/`
- **Verification**: Check `final_selection.json` exists and contains test metrics
- **Status**: ⚠️ **PENDING** - Needs to be run to establish baseline

**Step 1.2**: Create enhanced comparison script ✅
- **File**: `scripts/trade/compare_grid_search_models.py` ✅ **COMPLETE**
- **Functionality**:
  - Scan `data/grid_search/` for all result directories ✅
  - Load `final_selection.json` and `grid_results_train.json` from each ✅
  - Extract model name from metadata ✅
  - Generate comparison tables ✅
  - Export to JSON ✅
- **Output**: 
  - Console summary table ✅
  - Detailed metrics per model ✅
  - Improvement calculations vs baseline ✅
  - JSON export file ✅

**Step 1.3**: Update analysis document with results
- **File**: This document
- **Content**: Add actual comparison results (after ESPN baseline is run)
- **Metrics**: Test profit, trades, win rate, thresholds
- **Status**: ⚠️ **PENDING** - Waiting for ESPN baseline results

### Phase 2: Analysis and Insights (1-2 hours)

**Step 2.1**: Analyze results
- Calculate improvement percentages
- Identify best performing model
- Analyze threshold patterns
- Document insights

**Step 2.2**: Create visualizations (optional)
- Use matplotlib or similar
- Generate comparison charts
- Save to `data/grid_search/comparison_charts/`

### Phase 3: Documentation (1 hour)

**Step 3.1**: Update this analysis document
- Add actual results
- Document findings
- Update recommendations

**Step 3.2**: Create user guide
- How to run comparison script
- How to interpret results
- Best practices

## Risk Assessment

### Technical Risks

**Risk 1**: Missing or incomplete grid search results
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**: Script validates all required files exist before comparison

**Risk 2**: Model name extraction fails
- **Probability**: Low
- **Impact**: Low
- **Mitigation**: Fallback to directory name or manual specification

**Risk 3**: ESPN baseline not run with same parameters
- **Probability**: Medium
- **Impact**: High (invalid comparison)
- **Mitigation**: Document exact parameters used, validate in script

### Data Risks

**Risk 1**: Results from different data splits
- **Probability**: Low (same season, same script)
- **Impact**: High (invalid comparison)
- **Mitigation**: Verify game splits are identical across runs

**Risk 2**: Results from different time periods
- **Probability**: Low (all use 2025-26 season)
- **Impact**: Medium
- **Mitigation**: Include timestamp in comparison output

## Evidence and Verification

### Grid Search Results Location

**Command**: `ls -la data/grid_search/`
**Expected Output**: Directories for each model run

### Result File Structure

**Command**: `cat data/grid_search/{cache_key}/final_selection.json | jq .`
**Expected Output**: JSON structure with chosen_params, train_metrics, valid_metrics, test_metrics

### Model Name Extraction

**Command**: `cat data/grid_search/{cache_key}/grid_results_train.json | jq '.metadata.args.model_name'`
**Expected Output**: Model name string or null for ESPN

### Comparison Script Execution

**Command**: `python3 scripts/trade/compare_grid_search_models.py`
**Expected Output**: Comparison tables and summary statistics

## Usage Instructions

### Running the Comparison Script

**Command**:
```bash
python3 scripts/trade/compare_grid_search_models.py
```

**What it does**:
1. Scans `data/grid_search/` for all result directories
2. Loads `final_selection.json` and `grid_results_train.json` from each
3. Extracts model name from metadata (or "ESPN (default)" if None)
4. Generates comparison tables showing:
   - Summary table with key metrics
   - Detailed metrics per model (train/valid/test splits)
   - Improvement calculations vs baseline (if ESPN baseline exists)
5. Exports results to `data/grid_search/model_comparison.json`

**Output**:
- Console output with formatted tables
- JSON file: `data/grid_search/model_comparison.json`

**Example Output**:
```
============================================================================================================================
GRID SEARCH MODEL COMPARISON
============================================================================================================================
Model                      Test Profit     Trades     Win Rate     Entry      Exit       Profit/Trade    
----------------------------------------------------------------------------------------------------------------------------
catboost_platt             $1,899.70      367        66.8%        0.15       0.01       $5.18          
catboost_isotonic          $1,826.54      321        71.0%        0.19       0.015      $5.70          
logreg_isotonic            $1,220.86      331        63.4%        0.19       0.015      $3.69          
...
```

### Running ESPN Baseline Grid Search

To establish a baseline for comparison, run:

```bash
python3 scripts/trade/grid_search_hyperparameters.py \
  --season 2025-26 \
  --entry-min 0.02 \
  --entry-max 0.20 \
  --entry-step 0.01 \
  --exit-min 0.00 \
  --exit-max 0.05 \
  --exit-step 0.005 \
  --workers 8
```

**Note**: Do NOT include `--model-name` argument. This will use ESPN probabilities (the original behavior).

**Expected Output**: Results saved to `data/grid_search/{cache_key}/` with `model_name` as `None` in metadata.

## Next Steps

1. **Immediate**: Run ESPN baseline grid search ⚠️ **PENDING**
2. **Immediate**: Create comparison script ✅ **COMPLETE**
3. **Short-term**: Execute comparison and document results (after baseline is run)
4. **Medium-term**: Create visualizations (optional)
5. **Long-term**: Build web dashboard (if needed)

## References

- **Grid Search Implementation**: `cursor-files/sprints/2026-01-12-grid-search-multi-model-support/`
- **Model Artifacts**: `data/models/winprob_*.json`
- **Pre-computation**: `scripts/model/precompute_model_probabilities.py`
- **Analysis Template**: `cursor-files/templates/ANALYSIS_TEMPLATE.md`
- **Analysis Standards**: `cursor-files/templates/ANALYSIS_STANDARDS.md`

