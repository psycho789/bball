# Grid Search Log Analysis (v2 - With New Warnings)

**Date**: 2026-01-26  
**Log File**: `grid_search_b99560333ea59d5f71737ddca9750964bfc53293f46bfa54ccb86fc290d718e1/grid_search.log`  
**Model**: `catboost_baseline_no_interaction_platt_v2`  
**Total Log Lines**: 58,903  
**Run Duration**: ~6.6 minutes (13:29:11 to 13:35:46)

---

## Executive Summary

**Status**: ✅ **Grid search completed successfully.** No critical issues with the model, grid search, or data.

**Key Findings**:
1. ✅ **No errors** — Grid search completed without exceptions.
2. ✅ **No overfitting** — The `[SELECTION]` “train/valid discrepancy” warning was a **false positive**. Train has 70% of games, valid 15%; we compare **raw total profit** ($). Train naturally has ~4.67× more games, so higher total $ is expected. Not indicative of overfitting.
3. ⚠️ **Warning logic bug** — The `[SELECTION]` check compares raw $ across splits with different N. It should use **profit-per-game** (or similar) or be removed. Code fix needed; not a data/model issue.
4. ⚠️ **PERF** — Run was 2.3× slower than the rough time estimate. Operational only; doesn’t affect correctness.
5. ⚠️ **ALIGN_DATA** — One game (401812696) has “home + away ≈ 1.0” format. Data quirk; worth a look, limited impact.

### Key Metrics

| Metric | Value |
|--------|-------|
| Total log lines | 58,903 |
| Total warnings | 58,873 |
| Errors | 0 ✅ |
| Games processed | 92,415 (0 skipped) |
| Data points | 44,648,157 |
| Split | 70% train / 15% valid / 15% test |

**Warning breakdown**:
- `[END_OF_GAME]` forced closes: 55,367 — **expected**
- `[ALIGN_DATA]` format (game 401812696): ~3,500 — **one-game quirk**
- `[PERF]` slow run: 1 — **operational**
- `[SELECTION]` train/valid: 1 — **false positive** (flawed check)

---

## 1. Why the “Overfitting” Warning Was Wrong

### 1.1 What the Warning Said

```
[SELECTION] Large train/valid discrepancy: Train=$8135.56, Valid=$1950.18 (diff=$6185.38). Possible overfitting.
```

### 1.2 What’s Actually Going On

- **Splits**: 70% train, 15% valid, 15% test (default in `grid_search_hyperparameters.py`).
- **Metric**: We compare **total net profit in dollars** per split.
- **Sample size**: Train has **~4.67× more games** than valid (70/15).

Total profit = profit per game × number of games. So we **expect** train total $ to be much larger than valid’s even if performance per game is identical. That’s sample size, not overfitting.

### 1.3 Sanity Check

- Valid profit: $1,950 on 15% of games.
- If profit-per-game were equal, train (70%) would be ≈ 70/15 × $1,950 ≈ **$9,100**.
- Actual train: **$8,135**.

Train is *below* that scaled expectation. On a per-game basis, the strategy is **slightly worse** on train than valid — the opposite of overfitting.

### 1.4 Conclusion

- **No overfitting** suggested by these numbers.
- The **`[SELECTION]` train/valid check is flawed**: it uses raw $ and ignores split sizes.
- **Fix**: Use **profit-per-game** (or profit per trade) for train/valid/test comparisons, or remove the check. See recommendations below.

---

## 2. New Warning System Analysis

### 2.1 Performance Warning

**Logged**:
```
[PERF] Grid search took much longer than expected: 6.6 min actual vs 2.9 min expected. This may indicate performance issues.
```

- **Assessment**: Correctly flags that the run was slower than the rough estimate (2.3×).
- **Impact**: Operational only. Results are still valid.
- **Possible causes**: DB load, model inference, system load, etc.

**Recommendation**: Optional profiling of DB and model inference if you want to speed up runs.

---

### 2.2 Selection “Overfitting” Warning

- **Assessment**: **False positive** (see §1). The logic is wrong, not the data.
- **Action**: Fix or remove the `[SELECTION]` train/valid discrepancy check; do not treat it as evidence of overfitting.

---

### 2.3 Grid / Split / Results / Consistency

- **No `[GRID]` warnings** — Grid generated successfully (183 combinations).
- **No `[SPLIT]` warnings** — Split sizes OK.
- **No `[RESULTS]` warnings** — No suspicious totals, win rates, etc.
- **No `[CONSISTENCY]` warnings** — Result counts match across splits.

---

## 3. Data Quality

### 3.1 ALIGN_DATA (Game 401812696)

**Pattern**:
```
[ALIGN_DATA] Game 401812696: WARNING - home + away prices sum to ~1.0 (sum_diff: ...) but home ≠ away (diff: ...). 
This suggests canonical dataset may have switched to raw away-space. home=0.53, away=0.43.
```

- **Scope**: One game (401812696); appears multiple times in the log (once per combo that touches it).
- **Meaning**: Possible raw away-space (home + away ≈ 1.0) instead of home-space.
- **Impact**: Could affect that game only; limited. Fallback logic may already handle it.

**Recommendation**: Low priority. Optionally investigate 401812696 in the canonical view and conversion logic.

---

### 3.2 Missing Data / Fallbacks

- **Missing Kalshi data**: 0 reported (or only at DEBUG).
- **Away fallback prices**: 0.
- **Games skipped**: 0.

**Assessment**: ✅ No concerning missing-data or fallback issues.

---

## 4. Operational Warnings

### 4.1 End-of-Game Forced Closes

- **Count**: 55,367.
- **Assessment**: ✅ **Expected.** Positions still open at game end are force-closed with a 2¢ slippage penalty. Normal simulation behavior.

---

## 5. Model

- **No `[MODEL]` warnings** — Model loaded and used successfully.

---

## 6. Results Summary

### 6.1 Selected Setup

- **Parameters**: entry=0.180, exit=0.030.
- **Train**: $8,135.56  
- **Valid**: $1,950.18  
- **Test**: $1,739.60  

### 6.2 Interpretation

- Selection is **by validation** (best valid among top-N train). Valid and test are same size; valid → test is ~11% drop ($210), which is fine.
- Train > valid in **raw $** because train has ~4.67× more games. **Profit-per-game** is consistent (train slightly lower than scaled valid). **No overfitting** indicated.

---

## 7. What Actually Needs Attention

### 7.1 Code: `[SELECTION]` Train/Valid Check (High)

- **Issue**: Compares raw `net_profit_dollars` across train vs valid despite different split sizes.
- **Effect**: False “overfitting” warnings.
- **Fix**: Use **profit-per-game** (or similar) for discrepancy checks, or remove the check.

### 7.2 Data: ALIGN_DATA for Game 401812696 (Low)

- **Issue**: One game with home+away ≈ 1.0 format.
- **Effect**: Possible small impact on that game only.
- **Fix**: Optional DB/code check for that game and conversion logic.

### 7.3 Operations: Run Time (Low)

- **Issue**: Run ~2.3× slower than the coarse estimate.
- **Effect**: Longer grid searches only.
- **Fix**: Optional profiling and optimization.

---

## 8. What’s Fine

- ✅ No errors; grid search completed successfully.
- ✅ No overfitting signal in the reported metrics.
- ✅ No model load or usage issues.
- ✅ Splits, grid, and result counts consistent.
- ✅ No systemic missing-data or fallback issues.
- ✅ 92,415 games processed, 0 skipped, 44.6M data points.

---

## 9. Recommendations

1. **Fix `[SELECTION]` train/valid logic**  
   Use profit-per-game (or remove the check). Treat existing “[SELECTION] large train/valid discrepancy” warnings as false positives until fixed.

2. **Optional**  
   - Investigate ALIGN_DATA for game 401812696.  
   - Profile DB and model inference if you want faster runs.

---

## 10. Conclusion

**Are there any real issues?**

- **Model / strategy / data**: **No.** The run completed successfully, metrics are consistent with split sizes, and there’s no evidence of overfitting.
- **Code**: **Yes.** The `[SELECTION]` train/valid discrepancy check is wrong and should be fixed.
- **Operations**: **Minor.** Run was slower than the rough estimate; optional to optimize.

**Bottom line**: The grid search and its results are fine. The main follow-up is to fix the overfitting warning logic so it doesn’t mislead future analyses.

---

## Appendix: Key Statistics

| Metric | Count | Status |
|--------|-------|--------|
| Total log lines | 58,903 | Normal |
| Total warnings | 58,873 | Mostly expected |
| Errors | 0 | ✅ |
| [END_OF_GAME] | 55,367 | Expected |
| [ALIGN_DATA] (game 401812696) | ~3,500 | One-game quirk |
| [PERF] | 1 | Slower run |
| [SELECTION] train/valid | 1 | False positive (flawed logic) |
| Games processed | 92,415 | ✅ |
| Games skipped | 0 | ✅ |
| Data points | 44,648,157 | ✅ |

---

**Log**: `grid_search_b99560333ea59d5f71737ddca9750964bfc53293f46bfa54ccb86fc290d718e1`  
**Analysis version**: v2 (revised after correcting overfitting false positive)
