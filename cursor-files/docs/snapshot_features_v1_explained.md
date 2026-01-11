# What is `derived.snapshot_features_v1`?

## Simple Explanation

**`derived.snapshot_features_v1`** is a **materialized view** (acts like a table) that combines all the data you need for modeling and simulation into **one place**.

Think of it as a **pre-made dataset** where every row represents **one moment in time** during a game, with all the relevant information already calculated and joined together.

---

## What Problem Does It Solve?

### Before (The Problem)

To get features for modeling, you had to:

1. **Query ESPN probabilities** from `espn.probabilities_raw_items`
2. **Query game state** from `espn.prob_event_state` 
3. **Query Kalshi market data** from `kalshi.candlesticks`
4. **Join them together** (complex timestamp alignment)
5. **Calculate features** (interaction terms, lagged values, etc.)
6. **Repeat this** every time you need data

**Problems**:
- ❌ Same joins/calculations repeated everywhere
- ❌ Risk of logic drift (different code calculates things differently)
- ❌ Slow queries (complex joins every time)
- ❌ Hard to maintain (change logic in multiple places)

### After (The Solution)

**`derived.snapshot_features_v1`** does all of this **once** and stores the result:

✅ **One query** gets everything you need  
✅ **Pre-computed** features (fast queries)  
✅ **Consistent** logic (same calculations everywhere)  
✅ **Single source of truth** (one place to maintain)

---

## What's In Each Row?

Each row represents **one snapshot in time** during a game. Here's what's included:

### 1. **Identity** (What game, what moment)
- `season_label`: "2025-26"
- `game_id`: "401810095" (ESPN game ID)
- `sequence_number`: 10 (which snapshot in the game)
- `snapshot_ts`: 2025-11-16 20:12:00-08 (timestamp)

### 2. **ESPN Probabilities** (What ESPN thinks)
- `espn_home_prob`: 0.407 (40.7% chance home wins)
- `espn_away_prob`: 0.593 (59.3% chance away wins)

### 3. **Game State** (What's happening in the game)
- `score_diff`: 2 (home team up by 2 points)
- `time_remaining`: 3444 (seconds left in game)
- `period`: 1 (which quarter: 1, 2, 3, or 4)
- `home_score`: 2
- `away_score`: 0

### 4. **Interaction Term** (Pre-calculated feature)
- `score_diff_div_sqrt_time_remaining`: 0.034
  - Formula: `score_diff / sqrt(time_remaining + 1)`
  - Captures: Score matters more as time runs out

### 5. **Lagged Features** (Previous snapshot's values)
- `espn_home_prob_lag_1`: 0.389 (previous snapshot's home prob)
- `espn_away_prob_lag_1`: 0.611 (previous snapshot's away prob)
- `espn_home_prob_delta_1`: 0.018 (change from previous: 0.407 - 0.389)

### 6. **Kalshi Market Data** (What the market thinks)
- `kalshi_home_mid_price`: 0.775 (market thinks 77.5% home wins)
- `kalshi_home_bid`: 0.760 (best buy price)
- `kalshi_home_ask`: 0.790 (best sell price)
- `kalshi_home_spread`: 0.030 (bid-ask spread)
- `kalshi_away_*`: Same for away market (if available)

---

## Example: One Row

```sql
SELECT * FROM derived.snapshot_features_v1 
WHERE game_id = '401810095' AND sequence_number = 10;
```

**Returns**:
```
season_label: 2025-26
game_id: 401810095
sequence_number: 10
snapshot_ts: 2025-11-16 20:12:00-08

espn_home_prob: 0.407          ← ESPN thinks 40.7% home wins
espn_away_prob: 0.593          ← ESPN thinks 59.3% away wins

score_diff: 2                  ← Home team up by 2 points
time_remaining: 3444           ← 57 minutes 24 seconds left
period: 1                      ← First quarter
home_score: 2
away_score: 0

score_diff_div_sqrt_time_remaining: 0.034  ← Pre-calculated feature

espn_home_prob_lag_1: 0.389    ← Previous snapshot: 38.9%
espn_home_prob_delta_1: 0.018  ← Increased by 1.8% since last snapshot

kalshi_home_mid_price: 0.775   ← Market thinks 77.5% home wins
kalshi_home_bid: 0.760         ← Best buy price
kalshi_home_ask: 0.790         ← Best sell price
kalshi_home_spread: 0.030      ← 3 cent spread
```

**What this tells you**:
- ESPN thinks home has 40.7% chance
- Market thinks home has 77.5% chance
- **Divergence**: ESPN is much lower than market (-36.8%)
- Home team is up by 2 points early in Q1
- ESPN probability increased 1.8% since last snapshot (momentum)

---

## How Is It Different From Raw Tables?

### Raw Tables (What We Had Before)

**`espn.probabilities_raw_items`**:
- Just probabilities
- No game state
- No Kalshi data
- Need to join with other tables

**`espn.prob_event_state`**:
- Just game state (scores, time)
- No probabilities
- No Kalshi data
- Need to join with other tables

**`kalshi.candlesticks`**:
- Just market data
- Different timestamps
- Need complex alignment logic
- Need to join with other tables

### Canonical Dataset (What We Have Now)

**`derived.snapshot_features_v1`**:
- ✅ **Everything in one place**
- ✅ **Already joined** (ESPN + game state + Kalshi)
- ✅ **Already aligned** (timestamps matched within 60 seconds)
- ✅ **Features pre-calculated** (interactions, lags, etc.)
- ✅ **Fast queries** (materialized = pre-computed)

---

## Real-World Analogy

Think of it like a **restaurant menu**:

**Before**: You had to:
1. Go to the farm (get ESPN data)
2. Go to the butcher (get game state)
3. Go to the market (get Kalshi data)
4. Cook everything yourself (join and calculate)
5. Serve (use in model)

**Now**: The restaurant (canonical dataset) has:
- ✅ Everything already prepared
- ✅ All ingredients combined
- ✅ Ready to serve (just query it)

---

## How Do You Use It?

### Example 1: Get All Features for One Game

```sql
SELECT *
FROM derived.snapshot_features_v1
WHERE season_label = '2025-26'
  AND game_id = '401810095'
ORDER BY sequence_number;
```

**Use**: Load into pandas for modeling, or use in simulation.

### Example 2: Get Features for Modeling

```python
import pandas as pd
import psycopg

conn = psycopg.connect(os.environ["DATABASE_URL"])

# Get all features for a game - ONE QUERY, everything included
df = pd.read_sql("""
    SELECT 
        espn_home_prob,
        score_diff,
        time_remaining,
        score_diff_div_sqrt_time_remaining,
        espn_home_prob_lag_1,
        espn_home_prob_delta_1,
        kalshi_home_mid_price
    FROM derived.snapshot_features_v1
    WHERE season_label = '2025-26'
      AND game_id = '401810095'
    ORDER BY sequence_number
""", conn)

# Now df has all features ready for model training!
```

**Before**: Would need 3+ queries and manual joins.

### Example 3: Find Divergence Opportunities

```sql
SELECT 
    game_id,
    sequence_number,
    espn_home_prob,
    kalshi_home_mid_price,
    espn_home_prob - kalshi_home_mid_price AS divergence
FROM derived.snapshot_features_v1
WHERE season_label = '2025-26'
  AND kalshi_home_mid_price IS NOT NULL
  AND ABS(espn_home_prob - kalshi_home_mid_price) > 0.10  -- Big divergence
ORDER BY ABS(espn_home_prob - kalshi_home_mid_price) DESC;
```

**Use**: Find trading opportunities where ESPN and market disagree.

---

## Key Benefits

### 1. **Single Source of Truth**
- One place for all features
- No duplicate logic
- Easy to maintain

### 2. **Fast Queries**
- Materialized = pre-computed
- Indexes make queries fast
- No complex joins every time

### 3. **Consistent Features**
- Same calculations everywhere
- No logic drift between modeling and simulation
- Easy to reproduce results

### 4. **Complete Data**
- ESPN probabilities ✅
- Game state ✅
- Kalshi market data ✅
- Interaction terms ✅
- Lagged features ✅
- All in one place ✅

---

## Technical Details

### It's a Materialized View (Not a Regular Table)

**Materialized View** = Pre-computed query result stored as a table

- **Regular View**: Computes on-the-fly (slow, recalculates every time)
- **Materialized View**: Pre-computed (fast, stored like a table)

**Trade-off**:
- ✅ Fast queries (pre-computed)
- ⚠️ Needs refresh when source data changes

### Refresh Strategy

When new data is added (new games, new snapshots):

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY derived.snapshot_features_v1;
```

This rebuilds the materialized view with new data. Takes 5-10 minutes.

---

## Summary

**`derived.snapshot_features_v1`** is:
- ✅ A **pre-computed dataset** with all features in one place
- ✅ **Fast to query** (materialized view with indexes)
- ✅ **Consistent** (same logic everywhere)
- ✅ **Complete** (ESPN + game state + Kalshi + calculated features)

**Use it for**:
- Model training (load features directly)
- Simulation (no need to join ESPN + Kalshi separately)
- Analysis (everything in one query)

**Think of it as**: A ready-to-use dataset instead of having to build it from scratch every time.

