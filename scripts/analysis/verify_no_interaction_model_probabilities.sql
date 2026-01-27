-- Verify that the 4 new no-interaction model probability columns exist and are populated
-- Run this after precompute_model_probabilities.py completes

-- 1. Check if columns exist
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'derived'
  AND table_name = 'model_probabilities_v1'
  AND column_name LIKE '%no_interaction%'
ORDER BY column_name;

-- 2. Count total records and non-NULL values for each model probability column
SELECT 
    COUNT(*) as total_records,
    COUNT(catboost_baseline_no_interaction_platt_prob) as baseline_no_int_platt_populated,
    COUNT(catboost_baseline_no_interaction_isotonic_prob) as baseline_no_int_isotonic_populated,
    COUNT(catboost_odds_no_interaction_platt_prob) as odds_no_int_platt_populated,
    COUNT(catboost_odds_no_interaction_isotonic_prob) as odds_no_int_isotonic_populated,
    -- Compare with existing models
    COUNT(catboost_baseline_platt_prob) as baseline_platt_populated,
    COUNT(catboost_baseline_isotonic_prob) as baseline_isotonic_populated,
    COUNT(catboost_odds_platt_prob) as odds_platt_populated,
    COUNT(catboost_odds_isotonic_prob) as odds_isotonic_populated
FROM derived.model_probabilities_v1;

-- 3. Check percentage populated per column
SELECT 
    ROUND(100.0 * COUNT(catboost_baseline_no_interaction_platt_prob) / COUNT(*), 2) as baseline_no_int_platt_pct,
    ROUND(100.0 * COUNT(catboost_baseline_no_interaction_isotonic_prob) / COUNT(*), 2) as baseline_no_int_isotonic_pct,
    ROUND(100.0 * COUNT(catboost_odds_no_interaction_platt_prob) / COUNT(*), 2) as odds_no_int_platt_pct,
    ROUND(100.0 * COUNT(catboost_odds_no_interaction_isotonic_prob) / COUNT(*), 2) as odds_no_int_isotonic_pct,
    ROUND(100.0 * COUNT(catboost_baseline_platt_prob) / COUNT(*), 2) as baseline_platt_pct,
    ROUND(100.0 * COUNT(catboost_baseline_isotonic_prob) / COUNT(*), 2) as baseline_isotonic_pct,
    ROUND(100.0 * COUNT(catboost_odds_platt_prob) / COUNT(*), 2) as odds_platt_pct,
    ROUND(100.0 * COUNT(catboost_odds_isotonic_prob) / COUNT(*), 2) as odds_isotonic_pct
FROM derived.model_probabilities_v1;

-- 4. Sample records to verify values are reasonable (should be between 0 and 1)
SELECT 
    season_label,
    game_id,
    sequence_number,
    catboost_baseline_no_interaction_platt_prob,
    catboost_baseline_no_interaction_isotonic_prob,
    catboost_odds_no_interaction_platt_prob,
    catboost_odds_no_interaction_isotonic_prob,
    -- Compare with existing models
    catboost_baseline_platt_prob,
    catboost_odds_platt_prob
FROM derived.model_probabilities_v1
WHERE catboost_baseline_no_interaction_platt_prob IS NOT NULL
LIMIT 10;

-- 5. Check for any NULL values where they shouldn't be (all models should have same NULL pattern)
SELECT 
    COUNT(*) FILTER (WHERE catboost_baseline_platt_prob IS NULL AND catboost_baseline_no_interaction_platt_prob IS NOT NULL) as baseline_platt_null_but_no_int_not_null,
    COUNT(*) FILTER (WHERE catboost_baseline_platt_prob IS NOT NULL AND catboost_baseline_no_interaction_platt_prob IS NULL) as baseline_platt_not_null_but_no_int_null,
    COUNT(*) FILTER (WHERE catboost_odds_platt_prob IS NULL AND catboost_odds_no_interaction_platt_prob IS NOT NULL) as odds_platt_null_but_no_int_not_null,
    COUNT(*) FILTER (WHERE catboost_odds_platt_prob IS NOT NULL AND catboost_odds_no_interaction_platt_prob IS NULL) as odds_platt_not_null_but_no_int_null
FROM derived.model_probabilities_v1;

-- 6. Check value ranges (should all be between 0 and 1)
SELECT 
    MIN(catboost_baseline_no_interaction_platt_prob) as baseline_no_int_platt_min,
    MAX(catboost_baseline_no_interaction_platt_prob) as baseline_no_int_platt_max,
    MIN(catboost_baseline_no_interaction_isotonic_prob) as baseline_no_int_isotonic_min,
    MAX(catboost_baseline_no_interaction_isotonic_prob) as baseline_no_int_isotonic_max,
    MIN(catboost_odds_no_interaction_platt_prob) as odds_no_int_platt_min,
    MAX(catboost_odds_no_interaction_platt_prob) as odds_no_int_platt_max,
    MIN(catboost_odds_no_interaction_isotonic_prob) as odds_no_int_isotonic_min,
    MAX(catboost_odds_no_interaction_isotonic_prob) as odds_no_int_isotonic_max
FROM derived.model_probabilities_v1
WHERE catboost_baseline_no_interaction_platt_prob IS NOT NULL;

-- 7. Count by season to see distribution
SELECT 
    season_label,
    COUNT(*) as total_snapshots,
    COUNT(catboost_baseline_no_interaction_platt_prob) as baseline_no_int_platt_count,
    COUNT(catboost_odds_no_interaction_platt_prob) as odds_no_int_platt_count
FROM derived.model_probabilities_v1
GROUP BY season_label
ORDER BY season_label;
