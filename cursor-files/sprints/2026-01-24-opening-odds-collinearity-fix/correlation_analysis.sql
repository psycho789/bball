-- Correlation Analysis Query for Opening Odds Features
-- This query computes engineered features in SQL (replicating Python logic) for correlation analysis
-- Run on training data (2017-2022 seasons)

WITH training_data AS (
    SELECT 
        opening_moneyline_home,
        opening_moneyline_away,
        opening_spread,
        opening_total,
        -- Compute opening_overround (replicating Python logic)
        CASE 
            WHEN opening_moneyline_home IS NOT NULL 
                 AND opening_moneyline_away IS NOT NULL
                 AND opening_moneyline_home > 1.0 
                 AND opening_moneyline_away > 1.0
            THEN (1.0 / opening_moneyline_home + 1.0 / opening_moneyline_away) - 1.0
            ELSE NULL
        END AS opening_overround,
        -- Compute has_opening_moneyline (replicating Python logic)
        CASE 
            WHEN opening_moneyline_home IS NOT NULL 
                 AND opening_moneyline_away IS NOT NULL
                 AND opening_moneyline_home > 1.0 
                 AND opening_moneyline_away > 1.0
            THEN 1.0
            ELSE 0.0
        END AS has_opening_moneyline,
        -- Compute has_opening_spread
        CASE WHEN opening_spread IS NOT NULL THEN 1.0 ELSE 0.0 END AS has_opening_spread,
        -- Compute has_opening_total
        CASE WHEN opening_total IS NOT NULL THEN 1.0 ELSE 0.0 END AS has_opening_total
    FROM derived.snapshot_features_v1
    WHERE season_label LIKE '2017-%' 
       OR season_label LIKE '2018-%'
       OR season_label LIKE '2019-%'
       OR season_label LIKE '2020-%'
       OR season_label LIKE '2021-%'
       OR season_label LIKE '2022-%'
    LIMIT 100000  -- Sample for performance
)
SELECT 
    -- Correlation: has_opening_moneyline vs opening_overround
    -- Expected: Perfect correlation (1.0) since both derived from same condition
    CORR(
        CASE WHEN opening_overround IS NOT NULL THEN 1.0 ELSE 0.0 END,
        has_opening_moneyline
    ) AS corr_overround_has_ml,
    
    -- Correlation: has_opening_moneyline vs has_opening_spread
    CORR(has_opening_moneyline, has_opening_spread) AS corr_ml_spread,
    
    -- Correlation: has_opening_moneyline vs has_opening_total
    CORR(has_opening_moneyline, has_opening_total) AS corr_ml_total,
    
    -- Correlation: has_opening_spread vs has_opening_total
    CORR(has_opening_spread, has_opening_total) AS corr_spread_total,
    
    -- Count patterns to verify redundancy
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_spread = 1 AND has_opening_total = 1) AS all_three,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_spread = 0) AS ml_without_spread,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1 AND has_opening_total = 0) AS ml_without_total,
    -- These should be 0 if redundancy is perfect
    COUNT(*) FILTER (WHERE opening_overround IS NOT NULL AND has_opening_moneyline = 0) AS overround_without_flag,
    COUNT(*) FILTER (WHERE opening_overround IS NULL AND has_opening_moneyline = 1) AS flag_without_overround,
    -- Total counts
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE has_opening_moneyline = 1) AS rows_with_moneyline,
    COUNT(*) FILTER (WHERE opening_overround IS NOT NULL) AS rows_with_overround
FROM training_data;
