# Opening Odds Format Validation Report

**Date**: 2026-01-15  
**Sprint**: S1-E2-S1  
**Purpose**: Determine if `opening_moneyline_home` and `opening_moneyline_away` are in decimal or American format to ensure correct de-vigging conversion.

## Executive Summary

**Format Determined**: **DECIMAL ODDS**

The opening odds columns store values in **decimal format** (e.g., 1.85, 2.10, 3.57), not American format (e.g., -140, +120).

**Conversion Formula**: `p = 1 / odds` (decimal format)

## Sample Values

**Query**: `SELECT opening_moneyline_home, opening_moneyline_away FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL LIMIT 20;`

**Sample Results**:

| opening_moneyline_home | opening_moneyline_away | opening_spread | opening_total |
|------------------------|------------------------|----------------|---------------|
| 1.335 | 3.57 | -8 | 229 |
| 1.833 | 2.09 | -2 | 221 |
| 1.52 | 2.71 | -5.5 | 228.5 |
| 1.925 | 1.98 | -1 | 240.5 |
| 3.57 | 1.335 | 7.5 | 232 |
| 1.251 | 4.31 | -9.5 | 232.5 |
| 2.54 | 1.581 | 4 | 237 |
| 1.28 | 4.01 | -9 | 246.5 |
| 2.51 | 1.591 | 4 | 234.5 |
| 1.632 | 2.42 | -4 | 234.5 |
| 5.49 | 1.176 | 11.5 | 234 |
| 1.282 | 3.9 | -8.5 | 229 |
| 1.31 | 3.75 | -8 | 236 |
| 4.73 | 1.219 | 9.5 | 227 |
| 2.29 | 1.704 | 3 | 232.5 |
| 1.268 | 4.14 | -9.5 | 241 |
| 2.48 | 1.609 | 4.5 | 240.5 |
| 1.502 | 2.77 | -5.5 | 232.5 |
| 1.198 | 4.92 | -10.5 | 235.5 |
| 1.709 | 2.27 | -2.5 | 225 |

**Analysis**: All values are in the range 1.0-12.68, which is typical for decimal odds. American odds would be in ranges like -200 to +200.

## Value Range Statistics

**Query**: `SELECT MIN(opening_moneyline_home), MAX(opening_moneyline_home), MIN(opening_moneyline_away), MAX(opening_moneyline_away), AVG(opening_moneyline_home), AVG(opening_moneyline_away), COUNT(*) FROM derived.snapshot_features_v1 WHERE opening_moneyline_home IS NOT NULL AND opening_moneyline_away IS NOT NULL;`

**Results**:

| min_home | max_home | min_away | max_away | avg_home | avg_away | sample_size |
|----------|----------|----------|----------|----------|----------|-------------|
| 1.053 | 12.25 | 1.056 | 12.68 | 2.18 | 2.79 | 197,299 |

**Analysis**:
- **Minimum**: 1.053 (very close to 1.0, typical for heavy favorites in decimal format)
- **Maximum**: 12.68 (typical for heavy underdogs in decimal format)
- **Average**: 2.18 (home), 2.79 (away) - reasonable for decimal odds
- **Range**: 1.0-12.68 is characteristic of **decimal odds**
- **American odds** would typically range from -200 to +200 (or even wider)

## Format Determination

**Conclusion**: **DECIMAL ODDS**

**Evidence**:
1. All values are in range 1.0-12.68 (decimal format)
2. No negative values (American odds for favorites are negative, e.g., -140)
3. No values > 100 (American odds for underdogs are positive > 100, e.g., +120)
4. Typical decimal odds range: 1.0-10.0+ (matches observed data)
5. Typical American odds range: -200 to +200 (does not match observed data)

## Conversion Logic

### Decimal Odds Conversion

**Raw Implied Probability**:
```
p_home_raw = 1.0 / opening_moneyline_home
p_away_raw = 1.0 / opening_moneyline_away
```

**Overround (Vig)**:
```
overround = (p_home_raw + p_away_raw) - 1.0
```

**Fair Probability (De-Vigged)**:
```
p_home_fair = p_home_raw / (p_home_raw + p_away_raw)
p_away_fair = p_away_raw / (p_home_raw + p_away_raw)
```

### Example Calculation

**Given**:
- `opening_moneyline_home = 1.833`
- `opening_moneyline_away = 2.09`

**Step 1: Raw Implied Probabilities**:
```
p_home_raw = 1.0 / 1.833 = 0.5455
p_away_raw = 1.0 / 2.09 = 0.4785
```

**Step 2: Overround**:
```
overround = (0.5455 + 0.4785) - 1.0 = 0.0240 (2.4% vig)
```

**Step 3: Fair Probabilities**:
```
den = 0.5455 + 0.4785 = 1.0240
p_home_fair = 0.5455 / 1.0240 = 0.5323 (53.23%)
p_away_fair = 0.4785 / 1.0240 = 0.4677 (46.77%)
```

**Verification**: `p_home_fair + p_away_fair = 1.0` ✓

## Safety Checks

**Required Safety Checks** (to prevent NaNs/inf):
1. Both `opening_moneyline_home` and `opening_moneyline_away` must be present (not NULL)
2. Both values must be > 1.0 (decimal odds should be >= 1.01)
3. Denominator check: `(p_home_raw + p_away_raw) > 0` (should always be true if odds > 1.0)

**Implementation**:
```python
valid_ml = (
    opening_moneyline_home is not None
    and opening_moneyline_away is not None
    and opening_moneyline_home > 1.0
    and opening_moneyline_away > 1.0
)
```

## Implementation Notes

1. **Use decimal conversion**: `p = 1 / odds` (NOT American conversion)
2. **Safety checks**: Only compute de-vigging if both odds present and > 1.0
3. **Missing values**: Return NaNs for missing/invalid odds (CatBoost handles NaNs natively)
4. **Missingness flags**: Create `has_opening_moneyline` flag based on `valid_ml` condition

## Next Steps

1. ✅ Format determined: **DECIMAL ODDS**
2. ✅ Conversion formula documented: `p = 1 / odds`
3. ⏭️ Proceed to Story 2.2: Create shared de-vigging helper function using decimal conversion

---

**Report Generated**: 2026-01-15  
**Validated By**: Sprint Implementation  
**Status**: COMPLETE - Decimal Format Confirmed
