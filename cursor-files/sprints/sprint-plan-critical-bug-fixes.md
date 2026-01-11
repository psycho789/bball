# Sprint Plan: Critical Bug Fixes for Trading Simulation

**Sprint Goal:** Fix critical bugs causing crashes, incorrect P&L calculations, and data corruption

**Reference:** `cursor-files/analysis/suggested-fixes-analysis.md`

**Estimated Duration:** 2-3 hours

---

## Sprint Scope

### MUST FIX (Critical/High Impact)
| Story | Issue | Impact | Est. Time |
|-------|-------|--------|-----------|
| 1.1 | time_held calculation | Runtime crash | 10 min |
| 1.2 | Away bid/ask inversion with swap | Incorrect P&L | 20 min |
| 1.3 | f-string format spec parsing | Debug log crash | 15 min |
| 1.4 | Cache mutation safety | Data corruption | 15 min |
| 1.5 | Trade ordering for equity curve | Wrong metrics | 15 min |

### SHOULD FIX (Medium)
| Story | Issue | Impact | Est. Time |
|-------|-------|--------|-----------|
| 2.1 | Duplicate SQL cleanup | Code clarity | 10 min |
| 2.2 | Import guard | Clearer errors | 10 min |

### OPTIONAL (Low)
| Story | Issue | Impact | Est. Time |
|-------|-------|--------|-----------|
| 3.1 | Away market fallback logging | Observability | 5 min |
| 3.2 | Optional cache refresh parameter | Performance | 15 min |

---

## Phase 1: Critical Fixes

### Story 1.1: Fix time_held Calculation

**File:** `scripts/simulate_trading_strategy.py`
**Location:** Line ~758

**Problem:**
`timestamp` and `state.entry_timestamp` are both integers (Unix seconds), but `.total_seconds()` is called on an integer, causing `AttributeError`.

**Current Code:**
```python
time_held = (timestamp - state.entry_timestamp).total_seconds() if state.entry_timestamp else 0
```

**Fixed Code:**
```python
time_held = (timestamp - state.entry_timestamp) if state.entry_timestamp else 0
```

**Acceptance Criteria:**
- [ ] No `AttributeError` when exiting positions
- [ ] Minimum holding period check works correctly
- [ ] Simulation completes without crashes

**Validation:**
```bash
# Run simulation and verify no crashes on exit
python -c "from scripts.simulate_trading_strategy import simulate_trading_strategy; print('Import OK')"
```

---

### Story 1.2: Fix Away-Market Bid/Ask Inversion

**File:** `scripts/simulate_trading_strategy.py`
**Location:** Lines ~330-348

**Problem:**
When using away market data, `home_prob` is correctly converted (`1 - away_prob`), but bid/ask are stored without conversion AND without swap. In complement markets, bid/ask must be swapped.

**Mathematical Proof:**
- Away market: `bid=0.65, ask=0.75` (away team 70% probability)
- Home probability: `1 - 0.70 = 0.30`
- **Correct conversion with swap:**
  - `home_bid = 1 - away_ask = 1 - 0.75 = 0.25`
  - `home_ask = 1 - away_bid = 1 - 0.65 = 0.35`
- Spread preserved: `0.35 - 0.25 = 0.10` (same as `0.75 - 0.65`)

**Current Code:**
```python
# Convert to home win probability
if team_side == 'home':
    home_prob = display_price
else:  # away
    home_prob = 1.0 - display_price

# ... later ...
kalshi_by_side[team_side].append({
    "timestamp": timestamp,
    "home_prob": home_prob,
    "price_close": price_close / 100.0 if price_close else None,
    "yes_bid": yes_bid_close / 100.0 if yes_bid_close else None,
    "yes_ask": yes_ask_close / 100.0 if yes_ask_close else None,
})
```

**Fixed Code:**
```python
# Convert to home win probability and bid/ask
if team_side == 'home':
    home_prob = display_price
    home_bid = yes_bid_close / 100.0 if yes_bid_close else None
    home_ask = yes_ask_close / 100.0 if yes_ask_close else None
else:  # away - convert AND swap bid/ask
    home_prob = 1.0 - display_price
    # When converting from away to home, bid/ask must be swapped:
    # home_bid = 1 - away_ask (best buy price for home = complement of best sell for away)
    # home_ask = 1 - away_bid (best sell price for home = complement of best buy for away)
    home_bid = (1.0 - (yes_ask_close / 100.0)) if yes_ask_close else None
    home_ask = (1.0 - (yes_bid_close / 100.0)) if yes_bid_close else None

# ... later ...
kalshi_by_side[team_side].append({
    "timestamp": timestamp,
    "home_prob": home_prob,
    "price_close": price_close / 100.0 if price_close else None,
    "yes_bid": home_bid,  # Now in home-market space
    "yes_ask": home_ask,  # Now in home-market space
})
```

**Acceptance Criteria:**
- [ ] When using away market, bid/ask are converted to home space
- [ ] Bid/ask are swapped (not just complemented)
- [ ] Spread is preserved after conversion
- [ ] P&L calculations use consistent home-space values

**Validation:**
- Run simulation on game with only away market data
- Verify bid < ask in aligned output
- Verify spread is reasonable (not inverted)

---

### Story 1.3: Fix f-string Format Specifier Parsing

**File:** `scripts/simulate_trading_strategy.py`
**Locations:** Lines ~713, ~736, ~764

**Problem:**
The ternary `if ... else ...` is being parsed as part of the format specifier, causing `ValueError: Invalid format specifier`.

**Current Code (3 locations):**
```python
# Line ~713 (LONG entry)
logger.debug(f"[ENTRY] Entry blocked (LONG) - divergence is shrinking (prev: {state.prev_divergence_prob*100:.2f if state.prev_divergence_prob else None} cents, current: {divergence_prob*100:.2f} cents)")

# Line ~736 (SHORT entry)
logger.debug(f"[ENTRY] Entry blocked (SHORT) - divergence is shrinking (prev: {state.prev_divergence_prob*100:.2f if state.prev_divergence_prob else None} cents, current: {divergence_prob*100:.2f} cents)")

# Line ~764 (EXIT)
logger.debug(f"[EXIT] Exit blocked - divergence did not cross from outside threshold (prev: {state.prev_abs_divergence_prob*100:.2f if state.prev_abs_divergence_prob else None} cents, current: {abs_divergence_prob*100:.2f} cents)")
```

**Fixed Code:**
```python
# Line ~713 (LONG entry) - precompute string
prev_div_str = f"{state.prev_divergence_prob*100:.2f}" if state.prev_divergence_prob is not None else "None"
logger.debug(f"[ENTRY] Entry blocked (LONG) - divergence is shrinking (prev: {prev_div_str} cents, current: {divergence_prob*100:.2f} cents)")

# Line ~736 (SHORT entry) - precompute string
prev_div_str = f"{state.prev_divergence_prob*100:.2f}" if state.prev_divergence_prob is not None else "None"
logger.debug(f"[ENTRY] Entry blocked (SHORT) - divergence is shrinking (prev: {prev_div_str} cents, current: {divergence_prob*100:.2f} cents)")

# Line ~764 (EXIT) - precompute string
prev_abs_div_str = f"{state.prev_abs_divergence_prob*100:.2f}" if state.prev_abs_divergence_prob is not None else "None"
logger.debug(f"[EXIT] Exit blocked - divergence did not cross from outside threshold (prev: {prev_abs_div_str} cents, current: {abs_divergence_prob*100:.2f} cents)")
```

**Acceptance Criteria:**
- [ ] No `ValueError` when debug logging executes
- [ ] Logs show "None" when previous divergence is not set
- [ ] Logs show formatted number when previous divergence exists

**Validation:**
```bash
# Run simulation with DEBUG logging enabled
# Verify no crashes on first data point (when prev_divergence is None)
```

---

### Story 1.4: Fix Cache Mutation Safety

**File:** `webapp/api/endpoints/simulation.py`
**Location:** Lines ~262-272

**Problem:**
`_simulation_cache.get()` returns a reference to the cached object. Mutating it directly corrupts the cache for future requests.

**Current Code:**
```python
cached_result = _simulation_cache.get(cache_key)
if cached_result is not None:
    logger.info(f"  [Game {game_index}] Game {game_id}: Using cached result")
    # Add game metadata (cache doesn't store this)
    cached_result["game_id"] = game_id
    cached_result["game_date"] = game_date_str
    # Add game_id to each trade
    for trade in cached_result.get("trades", []):
        trade["game_id"] = game_id
        trade["game_date"] = game_date_str
    return cached_result, None
```

**Fixed Code:**
```python
import copy  # Add at top of file if not present

cached_result = _simulation_cache.get(cache_key)
if cached_result is not None:
    logger.info(f"  [Game {game_index}] Game {game_id}: Using cached result")
    # Deep copy to avoid mutating the cached object
    cached_result = copy.deepcopy(cached_result)
    # Add game metadata (cache doesn't store this)
    cached_result["game_id"] = game_id
    cached_result["game_date"] = game_date_str
    # Add game_id to each trade
    for trade in cached_result.get("trades", []):
        trade["game_id"] = game_id
        trade["game_date"] = game_date_str
    return cached_result, None
```

**Acceptance Criteria:**
- [ ] Cached objects are not mutated
- [ ] Subsequent cache hits return clean data
- [ ] Game IDs/dates are correct for each request

**Validation:**
- Run bulk simulation twice for same games
- Verify second run returns correct game IDs (not accumulated)

---

### Story 1.5: Fix Trade Ordering for Equity Curve

**File:** `webapp/api/endpoints/simulation.py`
**Location:** Lines ~384-396 (before equity curve calculation at ~520)

**Problem:**
Trades are collected from parallel threads in non-deterministic order. Equity curve and drawdown calculations require chronological order.

**Current Code:**
```python
for results in game_results:
    # Aggregate stats (total_profit_cents is already net profit after costs)
    total_profit_cents += results.get("total_profit_cents", 0.0)
    total_trades += results.get("num_trades", 0)
    
    # Collect all trades
    for trade in results.get("trades", []):
        all_trades.append(trade)

# ... later, equity curve calculated without sorting ...
```

**Fixed Code:**
```python
for results in game_results:
    # Aggregate stats (total_profit_cents is already net profit after costs)
    total_profit_cents += results.get("total_profit_cents", 0.0)
    total_trades += results.get("num_trades", 0)
    
    # Collect all trades
    for trade in results.get("trades", []):
        all_trades.append(trade)

# Sort trades chronologically before computing metrics that depend on order
# This ensures deterministic equity curve and accurate drawdown calculation
all_trades.sort(key=lambda t: (
    t.get("game_date", "") or "",
    t.get("exit_time") or t.get("entry_time") or 0
))
```

**Acceptance Criteria:**
- [ ] Trades sorted by game_date, then exit_time
- [ ] Equity curve shows chronological progression
- [ ] Drawdown calculation is deterministic
- [ ] Results are consistent across multiple runs

**Validation:**
- Run bulk simulation 3 times
- Compare equity_curve arrays - should be identical
- Compare max_drawdown values - should be identical

---

## Phase 2: Medium Priority Fixes

### Story 2.1: Remove Duplicate SQL Definition

**File:** `scripts/simulate_trading_strategy.py`
**Location:** Lines ~185-222

**Problem:**
Two `kalshi_sql` definitions exist back-to-back. The first has a syntax error (duplicate `FROM` clause at line ~220). Python uses the last assignment, so the first is dead code.

**Action:**
Delete lines ~185-222 (the first `kalshi_sql` definition with the syntax error).

**Keep:**
Lines ~226-264 (the second, correct `kalshi_sql` definition).

**Acceptance Criteria:**
- [ ] Only one `kalshi_sql` definition exists
- [ ] No SQL syntax errors
- [ ] Simulation continues to work

---

### Story 2.2: Add Import Guard for Dynamic Module Loading

**File:** `webapp/api/endpoints/simulation.py`
**Location:** Lines ~20-23

**Problem:**
If the script path is invalid, `spec` or `spec.loader` can be `None`, causing unclear `AttributeError`.

**Current Code:**
```python
script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/simulate_trading_strategy.py')
spec = importlib.util.spec_from_file_location("simulate_trading_strategy", script_path)
simulate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulate_module)
```

**Fixed Code:**
```python
script_path = os.path.join(os.path.dirname(__file__), '../../../scripts/simulate_trading_strategy.py')
spec = importlib.util.spec_from_file_location("simulate_trading_strategy", script_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load simulation module from {script_path}. Check file exists and is readable.")
simulate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulate_module)
```

**Acceptance Criteria:**
- [ ] Clear error message when script path invalid
- [ ] Application starts normally when path is valid

---

## Phase 3: Optional Enhancements

### Story 3.1: Add Away Market Fallback Logging

**File:** `scripts/simulate_trading_strategy.py`
**Location:** Line ~363

**Current Code:**
```python
kalshi_data = kalshi_by_side.get('home', kalshi_by_side.get('away', []))
```

**Enhanced Code:**
```python
if kalshi_by_side.get('home'):
    kalshi_data = kalshi_by_side['home']
else:
    kalshi_data = kalshi_by_side.get('away', [])
    if kalshi_data:
        logger.info(f"[ALIGN_DATA] Game {game_id}: Using away market fallback; prices/bid/ask inverted to home-prob space")
```

---

### Story 3.2: Add Optional Cache Refresh Parameter

**File:** `webapp/api/endpoints/simulation.py`
**Location:** Lines ~161-172

**Current Behavior:**
Cache is cleared on EVERY bulk request.

**Enhanced Behavior:**
Only clear cache when explicitly requested.

**Add Parameter:**
```python
force_refresh_cache: bool = Query(False, description="Force refresh of games cache (default: False)")
```

**Conditional Clear:**
```python
if force_refresh_cache:
    # Clear the games cache
    if hasattr(games.list_games, '_cache_instance'):
        games.list_games._cache_instance.clear()
        logger.info("Cleared games endpoint cache (force_refresh_cache=True)")
    # Also delete the cache file
    cache_file = Path("webapp/.cache/list_games.cache")
    if cache_file.exists():
        cache_file.unlink()
        logger.info(f"Deleted cache file: {cache_file}")
```

---

## Testing Strategy

### Unit Testing
1. Test `time_held` calculation with integer timestamps
2. Test away market bid/ask conversion with known values
3. Test f-string formatting with None and non-None values
4. Test cache deepcopy doesn't mutate original

### Integration Testing
1. Run full bulk simulation (500 games)
2. Verify no crashes
3. Verify equity curve is deterministic (run 3x, compare)
4. Verify P&L signs are reasonable

### Regression Testing
1. Compare simulation results before/after fixes
2. Note: Results WILL change due to bid/ask fix - this is expected
3. Verify results are now MORE correct (not less)

---

## Deployment Plan

1. **Pre-deployment:**
   - Clear simulation cache (results will be invalid after fix #2)
   - Backup current cache file

2. **Deployment Order:**
   - Phase 1 fixes first (all critical)
   - Test thoroughly
   - Phase 2 fixes
   - Test again
   - Phase 3 optional

3. **Post-deployment:**
   - Run bulk simulation
   - Verify no crashes
   - Spot-check equity curves

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bid/ask fix changes results | High | Expected | Clear cache, document change |
| New bugs introduced | Low | Medium | Thorough testing |
| Performance regression | Low | Low | Deepcopy is fast for small objects |

---

## Success Metrics

- [ ] Zero crashes in bulk simulation (500 games)
- [ ] Equity curve is deterministic (3 runs identical)
- [ ] Cache doesn't show accumulated game IDs
- [ ] Away market games have valid bid/ask spreads
- [ ] Debug logs don't crash with ValueError

---

## Definition of Done

- [ ] All Phase 1 stories completed
- [ ] All Phase 2 stories completed (recommended)
- [ ] No linting errors
- [ ] Manual testing passed
- [ ] Simulation cache cleared
- [ ] Documentation updated (if needed)




