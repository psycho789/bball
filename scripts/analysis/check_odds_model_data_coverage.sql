-- Check data coverage for catboost_odds_platt model
-- This will help diagnose why it has so few trades

-- 1. Count total snapshots vs snapshots with odds model probabilities
SELECT 
    COUNT(*) as total_snapshots,
    COUNT(catboost_odds_platt_prob) as odds_platt_populated,
    COUNT(catboost_baseline_platt_prob) as baseline_platt_populated,
    COUNT(catboost_platt_prob) as catboost_platt_populated,
    ROUND(100.0 * COUNT(catboost_odds_platt_prob) / COUNT(*), 2) as odds_platt_pct,
    ROUND(100.0 * COUNT(catboost_baseline_platt_prob) / COUNT(*), 2) as baseline_platt_pct
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26';

-- 2. Check if odds model probabilities are NULL when opening odds data exists
SELECT 
    COUNT(*) as total_snapshots,
    COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL THEN 1 END) as has_opening_odds,
    COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL AND mp.catboost_odds_platt_prob IS NULL THEN 1 END) as has_odds_but_null_prob,
    COUNT(CASE WHEN sf.opening_moneyline_home IS NULL AND mp.catboost_odds_platt_prob IS NOT NULL THEN 1 END) as no_odds_but_has_prob
FROM derived.snapshot_features_v1 sf
LEFT JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
WHERE sf.season_label = '2025-26';

-- 3. Check games that have opening odds but model probabilities are NULL
SELECT 
    sf.game_id,
    COUNT(*) as total_snapshots,
    COUNT(CASE WHEN sf.opening_moneyline_home IS NOT NULL THEN 1 END) as snapshots_with_odds,
    COUNT(mp.catboost_odds_platt_prob) as snapshots_with_prob
FROM derived.snapshot_features_v1 sf
LEFT JOIN derived.model_probabilities_v1 mp
    ON sf.season_label = mp.season_label
    AND sf.game_id = mp.game_id
    AND sf.sequence_number = mp.sequence_number
    AND sf.snapshot_ts = mp.snapshot_ts
WHERE sf.season_label = '2025-26'
  AND sf.opening_moneyline_home IS NOT NULL
GROUP BY sf.game_id
HAVING COUNT(mp.catboost_odds_platt_prob) = 0
LIMIT 10;

-- 4. Compare distribution of probabilities between models
SELECT 
    'baseline_platt' as model,
    COUNT(*) as count,
    MIN(catboost_baseline_platt_prob) as min_prob,
    MAX(catboost_baseline_platt_prob) as max_prob,
    AVG(catboost_baseline_platt_prob) as avg_prob
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND catboost_baseline_platt_prob IS NOT NULL
UNION ALL
SELECT 
    'odds_platt' as model,
    COUNT(*) as count,
    MIN(catboost_odds_platt_prob) as min_prob,
    MAX(catboost_odds_platt_prob) as max_prob,
    AVG(catboost_odds_platt_prob) as avg_prob
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND catboost_odds_platt_prob IS NOT NULL;

-- 5. Check if the model was trained correctly (verify artifact exists and has correct features)
-- This would need to be checked via Python, but we can verify the precomputation worked
SELECT 
    COUNT(DISTINCT game_id) as games_with_odds_platt_probs
FROM derived.model_probabilities_v1
WHERE season_label = '2025-26'
  AND catboost_odds_platt_prob IS NOT NULL;
