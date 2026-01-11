# Trade Data for 1-Second Candlesticks: Analysis and Enhancement Opportunities

## Executive Summary

This analysis evaluates using Kalshi trade data to create sub-minute candlesticks and enhance existing 1-minute candlestick visualizations. Trade data provides microsecond-precision timestamps and individual trade records, enabling execution-based price movement analysis at finer granularity than the current 1-minute candlestick data.

**Key Finding**: 
- ✅ **Trade data can produce sub-minute "last-trade" candlesticks** (execution-based OHLC) + volume/VWAP metrics
- ❌ **Trade data cannot reconstruct historical bid/ask evolution, spread, or quote-driven movement** at sub-minute resolution
- ⚠️ **The official 1-minute candlestick endpoint contains yes_bid/yes_ask OHLC** that cannot be recreated from trades after-the-fact

Trade-derived candlesticks are execution-only (last-trade price), while official candlesticks include quote data (bid/ask) that requires live orderbook capture.

---

## Limitations

**Critical Constraints**:

1. **Execution-Only Data**: Trade-derived candlesticks represent **last-trade prices only**. They do not contain bid/ask quotes or orderbook depth information.

2. **No Historical Quote Replay**: Historical sub-minute bid/ask spread evolution **cannot be reconstructed** from trade data. The official 1-minute candlestick endpoint provides `yes_bid` and `yes_ask` OHLC that trades do not capture.

3. **Sparse Coverage**: Many seconds will have **zero trades** (especially earlier in games). Seconds with no trades contain no observed information; any forward-fill or interpolation is a display choice, not ground truth.

4. **Bursty Activity**: Trade timestamps are highly clustered (bursty). "Average trades/second" metrics can be misleading—activity often spikes late in games or near settlement, with long quiet periods.

5. **Future Quote Data**: True sub-minute spread/quote charts require **live WebSocket orderbook channels** going forward. Historical trade data cannot provide this.

**What Trade Data Can Do**:
- ✅ Sub-minute execution-based OHLC (last-trade prices)
- ✅ Volume aggregation and VWAP calculation
- ✅ Trade intensity/heatmap visualization
- ✅ Execution timing for simulations

**What Trade Data Cannot Do**:
- ❌ Reconstruct historical bid/ask quotes
- ❌ Show spread evolution at sub-minute resolution
- ❌ Provide orderbook depth information
- ❌ Fill gaps with meaningful quote data

---

## 1. Current State Analysis

### 1.1 Existing Candlestick Data Structure

**Source**: Kalshi API `/series/{series}/markets/{ticker}/candlesticks` endpoint
**Current Interval**: 1-minute (`period_interval=1`)
**Storage**: `kalshi.candlesticks` table

**Schema** (`db/migrations/025_kalshi_tables.sql`):
```sql
CREATE TABLE kalshi.candlesticks (
  ticker              TEXT NOT NULL,
  period_ts           TIMESTAMPTZ NOT NULL,      -- End of candle period
  period_interval_min INTEGER NOT NULL,         -- Currently 1 minute
  price_open          INTEGER,                  -- Cents (e.g., 47 = $0.47)
  price_high          INTEGER,
  price_low           INTEGER,
  price_close         INTEGER,
  price_mean          INTEGER,
  yes_bid_open/high/low/close INTEGER,
  yes_ask_open/high/low/close INTEGER,
  volume              BIGINT,
  open_interest       BIGINT
)
```

**Data Characteristics**:
- OHLC (Open, High, Low, Close) for last traded price
- OHLC for yes bid and yes ask
- Volume aggregated per minute
- ~170 minutes per game (typical NBA game duration)
- ~170 data points per game per market

### 1.2 Trade Data Structure

**Source**: Kalshi API `/markets/trades` endpoint (individual trade records)
**Storage**: `kalshi.trades` table

**Schema** (`db/migrations/031_kalshi_trades.sql`):
```sql
CREATE TABLE kalshi.trades (
  trade_id            TEXT PRIMARY KEY,
  ticker              TEXT NOT NULL,
  created_time        TIMESTAMPTZ NOT NULL,     -- Microsecond precision
  count               INTEGER NOT NULL,         -- Trade quantity
  price                NUMERIC(18,6),           -- Trade price (0-1 range)
  yes_price           INTEGER,                 -- Yes price in cents
  no_price            INTEGER,                  -- No price in cents
  taker_side          TEXT NOT NULL,           -- "yes" or "no"
  yes_price_dollars   TEXT,
  no_price_dollars    TEXT
)
```

**Data Characteristics** (from sample analysis):
- **Granularity**: Microsecond-precision timestamps
- **Volume**: ~10,567 trades per game (sample: KXNBAGAME-25NOV30OKCPOR-POR)
- **Time Distribution** (sample game):
  - ~5,126 unique seconds with trades (out of ~10,200 possible seconds in ~170 minutes)
  - **~50% of seconds have zero trades** (sparse coverage, especially early in games)
  - Average 2.06 trades per second (misleading—activity is bursty/clustered)
  - Max 15 trades in a single second (peak activity)
  - ~170 unique minutes with trades
  - Average 62.16 trades per minute
  - Max 252 trades in a single minute
- **Activity Pattern**: Trade timestamps are highly clustered (bursty). Activity often spikes late in games or near settlement, with long quiet periods. Median spacing between trades varies significantly.
- **Coverage**: Trades span entire game duration (~170 minutes), but distribution is non-uniform

### 1.3 Current Usage of Candlesticks

**Location**: `webapp/static/templates/game-detail.html` and `webapp/static/js/chart.js`

**Visualization**:
- Lightweight Charts library for rendering
- Line series for ESPN probabilities (home/away win %)
- Kalshi candlestick series overlay
- Toggle controls for ESPN/Kalshi visibility
- Quarter markers (Q1-Q4) based on elapsed game time

**API Endpoints**:
- `webapp/api/endpoints/probabilities.py`: Serves candlestick data for charts
- `webapp/api/endpoints/simulation.py`: Uses candlesticks for trading strategy simulation
- `webapp/api/endpoints/aggregate_stats.py`: Uses candlesticks for statistical analysis

**Current Limitations**:
1. **1-minute resolution** misses rapid execution price movements
2. **Aggregated volume** loses individual trade details
3. **No bid/ask spread visualization** at sub-minute level (requires live orderbook data)
4. **Limited granularity** for high-frequency trading analysis

---

## 2. Feasibility Analysis: 1-Second Candlesticks from Trade Data

### 2.1 Data Availability

**Pros**:
- ✅ Trade data has microsecond precision (`created_time` TIMESTAMPTZ)
- ✅ Sufficient trade volume: ~2 trades/second average, up to 15/second peak
- ✅ Complete coverage: Trades span entire game duration
- ✅ All required fields present: price, volume (count), yes/no prices, timestamps

**Cons**:
- ⚠️ **Many seconds have zero trades** (especially earlier in games)—sparse periods contain no observed information
- ⚠️ **Bursty activity**: Trade density varies significantly; "average trades/second" is misleading
- ⚠️ **Execution-only**: Cannot reconstruct bid/ask quotes or spread evolution
- ⚠️ Requires aggregation logic (OHLC calculation per second)
- ⚠️ Storage overhead: ~5,126 seconds × 2 markets = ~10,252 rows per game vs. ~340 rows currently (if materialized)

### 2.2 Algorithm Design

**Design Pattern**: Time-Window Aggregation Pattern
**Algorithm**: Sliding Window OHLC Aggregation
**Big O Complexity**: O(n) where n = number of trades per game

**Implementation Approach**:

```python
# Pseudocode for 1-second candlestick generation
from decimal import Decimal
from collections import defaultdict

def create_1s_candlesticks(trades: List[Trade], ticker: str) -> List[Candlestick]:
    """
    Aggregate trades into 1-second candlesticks.
    
    Algorithm: Group trades by second, calculate OHLC per group
    Time Complexity: O(n) if trades are processed in created_time order; otherwise O(n log n) due to sorting
    Space Complexity: O(m) where m = number of unique seconds
    
    CRITICAL: Use integer cents end-to-end, do NOT use float math for prices.
    Trade-derived candles exist only for intervals containing ≥1 trade (sparse series).
    """
    # Group trades by second (truncate microsecond precision)
    trades_by_second = defaultdict(list)
    for trade in trades:
        second_key = trade.created_time.replace(microsecond=0)
        trades_by_second[second_key].append(trade)
    
    candlesticks = []
    for second_ts, second_trades in sorted(trades_by_second.items()):
        if not second_trades:
            continue  # Skip seconds with no trades (sparse storage)
        
        # CRITICAL: Sort trades by created_time within each second
        # Do NOT assume list order
        second_trades_sorted = sorted(second_trades, key=lambda t: t.created_time)
        
        # Use yes_price (integer cents) as canonical price source
        # Do NOT use float price field for calculations
        yes_prices_cents = [t.yes_price for t in second_trades_sorted]
        volumes = [t.count for t in second_trades_sorted]
        
        # Calculate OHLC using integer cents
        price_open_cents = yes_prices_cents[0]  # First trade in second
        price_close_cents = yes_prices_cents[-1]  # Last trade in second
        price_high_cents = max(yes_prices_cents)
        price_low_cents = min(yes_prices_cents)
        
        # Calculate VWAP in cents (volume-weighted average)
        # Use integer division for cents VWAP (floors); if you want rounding, add + total_volume/2 before //
        total_price_volume = sum(price * vol for price, vol in zip(yes_prices_cents, volumes))
        total_volume = sum(volumes)
        price_mean_cents = total_price_volume // total_volume if total_volume > 0 else price_close_cents
        
        candlestick = {
            'ticker': ticker,
            'period_ts': second_ts + timedelta(seconds=1),  # End of period
            'interval_seconds': 1,  # Use integer seconds, NOT fractional minutes
            'price_open_cents': price_open_cents,
            'price_high_cents': price_high_cents,
            'price_low_cents': price_low_cents,
            'price_close_cents': price_close_cents,
            'price_mean_cents': price_mean_cents,
            'volume': total_volume,
            # Yes/No prices from last trade (for reference only)
            'yes_price_close_cents': second_trades_sorted[-1].yes_price,
            'no_price_close_cents': second_trades_sorted[-1].no_price,
            'is_filled': False,  # Mark actual vs. filled data
        }
        candlesticks.append(candlestick)
    
    return candlesticks
```

**Handling Sparse Periods**:

**For Simulations/Backtests**: 
- ❌ **Do NOT forward-fill missing seconds**. Missing seconds contain no observed information.
- Store only seconds that actually have trades (sparse storage).

**For Charts**:
- **Option 1**: Plot points only at trade timestamps (line/scatter chart)
- **Option 2**: If creating filled candles for continuity, mark them explicitly (`is_filled=true`) and keep "actual vs filled" separate
- **Do NOT treat filled/interpolated data as ground truth**—it's visualization-only

### 2.3 Storage Considerations

**Current Storage** (1-minute candlesticks):
- ~340 rows per game (170 minutes × 2 markets)
- ~68 KB per game (assuming ~200 bytes per row)

**Proposed Storage** (1-second trade-derived candlesticks):
- **Sparse storage**: Only seconds with trades are stored (~5,126 seconds × 2 markets = ~10,252 rows per game in sample)
- ~2 MB per game if materialized (assuming ~200 bytes per row)
- **Actual multiplier depends on trade density**: Games with sparse trading will have fewer rows; high-activity games will have more
- **Trade-derived candles exist only for intervals containing ≥1 trade** (sparse series by default)

**Mitigation Strategies**:
1. **Sparse storage**: Store only seconds that actually have trades (not all seconds)
2. **On-demand generation**: Generate 1-second candles from trades without persisting per-second rows
3. **Per-ticker materialization**: If materializing, do so per ticker/game with caching, not globally
4. **Query-time aggregation**: Use indexed trades table with query-time grouping (no materialization)

**Recommendation**: Start with **on-demand query-time aggregation** (no materialization) to avoid storage bloat. If performance requires it, consider per-game/ticker materialization with explicit refresh strategy.

**Chart Gap Handling**: UI may optionally render a continuous line by carrying last trade forward, but stored data remains sparse and flagged if filled (`is_filled=true`). Gaps represent periods with no observed trades.

---

## 3. Enhancement Opportunities

### 3.1 Graph Detail Page Enhancements

**Current State** (`webapp/static/js/chart.js`):
- Displays 1-minute Kalshi candlesticks as overlay on ESPN probability lines
- Basic OHLC visualization
- Toggle between ESPN and Kalshi data

**Proposed Enhancements**:

#### A. Multi-Resolution Candlestick Display
- **1-minute view** (default): Current behavior, fast loading
- **1-second view** (zoom): Show detailed price movements during selected periods
- **Interactive zoom**: Click/drag to zoom into specific time ranges with 1-second resolution
- **Algorithm**: Lazy loading - fetch 1-second candles only when zoomed

**Implementation**:
```javascript
// Add resolution selector
<select id="candlestickResolution">
  <option value="60">1 Minute</option>
  <option value="1">1 Second</option>
</select>

// On resolution change, fetch appropriate data
async function updateCandlestickResolution(resolution) {
  if (resolution === 1) {
    // Fetch 1-second trade-derived candlesticks from trades
    const candles = await fetch(`/api/probabilities/${gameId}/kalshi-candles?interval_seconds=1&source=trades`);
    updateChart(candles);
  } else {
    // Use existing 1-minute official candlesticks
    const candles = await fetch(`/api/probabilities/${gameId}/kalshi-candles?interval_seconds=60&source=official`);
    updateChart(candles);
  }
}
```

#### B. Volume Visualization
- **Trade volume bars**: Show volume per second/minute as bar chart overlay
- **Volume-weighted average price (VWAP)**: Calculate and display VWAP line
- **Algorithm**: Aggregate `count` field from trades per time period

#### C. Bid/Ask Spread Visualization (Historical Limitations)
- **1-minute spread**: Can visualize bid-ask spread using official 1-minute candlesticks (`yes_bid`/`yes_ask` OHLC)
- **Sub-minute spread**: **NOT available from trade data**. Historical sub-minute spread evolution cannot be reconstructed from trades
- **Future requirement**: True sub-minute spread visualization requires **live WebSocket orderbook channels** going forward (cannot be replayed historically)
- **Algorithm**: Use `yes_bid` and `yes_ask` from official 1-minute candlesticks only
- **Rule**: **Never mix trade-derived candles with inferred sub-minute spreads**; only show spread at 1-minute using official candles

#### D. Trade Activity Heatmap
- **Trade frequency overlay**: Color-code chart background by trade frequency
- **High-activity periods**: Highlight seconds/minutes with above-average trade volume
- **Algorithm**: Count trades per second, apply color gradient

### 3.2 Multi-Resolution Trade-Derived Candles (Alternative to Interpolation)

**Current Problem**: 1-minute candles may miss rapid execution price movements within the minute

**Solution**: Provide multi-resolution trade-derived candles (10s/1s) on zoom, rather than interpolating between 1-minute candles

**Approach**: Generate trade-derived candles at multiple resolutions (10-second, 1-second) from actual trade data when zooming, without interpolation

**Algorithm**: Multi-Resolution Aggregation
```python
def create_trade_candles(trades: List[Trade], 
                        ticker: str, 
                        interval_seconds: int) -> List[Candlestick]:
    """
    Create trade-derived candlesticks at specified interval.
    
    interval_seconds: 1, 10, 60, etc.
    Only creates candles for intervals that have trades (sparse).
    """
    # Group trades by interval
    trades_by_interval = defaultdict(list)
    for trade in trades:
        # Truncate to interval boundary
        interval_ts = truncate_to_interval(trade.created_time, interval_seconds)
        trades_by_interval[interval_ts].append(trade)
    
    candles = []
    for interval_ts, interval_trades in sorted(trades_by_interval.items()):
        # Sort trades by time within interval
        interval_trades_sorted = sorted(interval_trades, key=lambda t: t.created_time)
        
        # Calculate OHLC from yes_price (integer cents)
        yes_prices_cents = [t.yes_price for t in interval_trades_sorted]
        # ... OHLC calculation (same as 1-second algorithm)
        
        candles.append({
            'ticker': ticker,
            'period_ts': interval_ts + timedelta(seconds=interval_seconds),
            'interval_seconds': interval_seconds,
            # ... OHLC fields
            'is_filled': False,
        })
    
    return candles
```

**Why Not Interpolate**:
- ❌ **Interpolating between minute candles creates pretty-but-fake paths**
- ❌ **No observed information exists for seconds without trades**
- ✅ **Better approach**: Provide actual trade-derived candles at multiple resolutions (10s/1s) on zoom
- ✅ **If any interpolation remains for UI smoothing**, label it as visualization-only and **never use it in simulations**

**Pros**:
- ✅ Uses actual trade data (no fake interpolation)
- ✅ Can be computed on-demand
- ✅ Maintains data integrity

**Cons**:
- ⚠️ Sparse coverage (many intervals have no trades)
- ⚠️ Requires trade data to be loaded/joined

### 3.3 Simulation Strategy Enhancements

**Current Usage** (`webapp/api/endpoints/simulation.py`):
- Uses 1-minute candlesticks for entry/exit signal detection
- Calculates profit based on price movements between minutes

**Enhancement Opportunities**:

#### A. Sub-Minute Entry/Exit Timing
- **Problem**: Entry/exit signals may occur mid-minute, but simulation only checks at minute boundaries
- **Solution**: Use trade data to detect exact entry/exit times within minutes
- **Algorithm**: Scan trades chronologically, trigger entry/exit when threshold crossed

#### B. Volume-Weighted Entry Prices
- **Current**: Uses candle open/close prices
- **Enhanced**: Calculate VWAP for entry/exit using actual trade volumes
- **Algorithm**: `VWAP = Σ(price × volume) / Σ(volume)` for trades in period

#### C. Slippage Modeling (Limited by Trade Data)
- **Current**: Assumes execution at exact candle price
- **Enhanced**: Model slippage using actual trade execution prices (from trades)
- **Limitation**: Cannot model bid/ask spread slippage from trade data alone (requires orderbook data)
- **Algorithm**: Use actual trade prices from `kalshi.trades` to estimate execution price, but note that bid/ask spread information is not available from trades

---

## 4. Implementation Recommendations

### 4.1 Phase 1: On-Demand Trade-Derived Candlestick Generation

**Approach**: Query-time aggregation or per-ticker materialization that generates trade-derived candles from trades on-demand

**Schema Design**: Keep `kalshi.candlesticks` as "official API candles" (minute/hour/day). Do NOT mutate it to support fractional minutes.

**Option A: Separate View/Table** (Recommended):
```sql
-- Separate table for trade-derived candles
CREATE TABLE IF NOT EXISTS kalshi.trade_candles (
  trade_candle_id     BIGSERIAL PRIMARY KEY,
  ticker              TEXT NOT NULL,
  period_ts           TIMESTAMPTZ NOT NULL,
  interval_seconds    INTEGER NOT NULL,  -- 1, 10, 60, etc. (NOT fractional minutes)
  price_open_cents    INTEGER NOT NULL,
  price_high_cents    INTEGER NOT NULL,
  price_low_cents     INTEGER NOT NULL,
  price_close_cents   INTEGER NOT NULL,
  price_mean_cents    INTEGER,
  volume              BIGINT NOT NULL,
  yes_price_close_cents INTEGER,
  no_price_close_cents  INTEGER,
  is_filled           BOOLEAN NOT NULL DEFAULT false,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ux_trade_candles_ticker_period_interval 
    UNIQUE (ticker, period_ts, interval_seconds)
);

CREATE INDEX idx_trade_candles_ticker_ts 
ON kalshi.trade_candles(ticker, period_ts DESC, interval_seconds);
```

**Option B: Query-Time Aggregation** (No Persistence):
```sql
-- View or query-time aggregation (no materialization)
-- Generate on-demand from kalshi.trades with indexed lookups
SELECT 
  ticker,
  date_trunc('second', created_time) + INTERVAL '1 second' as period_ts,
  1 as interval_seconds,  -- Integer seconds, NOT fractional minutes
  (array_agg(yes_price ORDER BY created_time))[1] as price_open_cents,
  MAX(yes_price) as price_high_cents,
  MIN(yes_price) as price_low_cents,
  (array_agg(yes_price ORDER BY created_time DESC))[1] as price_close_cents,
  -- VWAP calculation
  SUM(yes_price * count) / NULLIF(SUM(count), 0) as price_mean_cents,
  SUM(count) as volume,
  (array_agg(yes_price ORDER BY created_time DESC))[1] as yes_price_close_cents,
  (array_agg(no_price ORDER BY created_time DESC))[1] as no_price_close_cents
FROM kalshi.trades
WHERE ticker = $1 
  AND created_time >= $2 
  AND created_time < $3
GROUP BY ticker, date_trunc('second', created_time)
ORDER BY period_ts;
```

**Materialized View Strategy** (If Needed):
- ⚠️ **A global materialized view over all trades is costly to refresh**
- ✅ **Prefer**: Parameterized query aggregation per ticker/time window
- ✅ **Alternative**: Per-game/ticker materialization on-demand with caching
- ✅ **Best**: Normal view + indexed underlying trades with query-time grouping
- **If using matview**: Note refresh strategy and scope (per ticker/game) to avoid full refresh

**Pros**:
- ✅ No storage overhead (if query-time)
- ✅ Always up-to-date (uses latest trades)
- ✅ Can be cached for frequently-accessed games
- ✅ Keeps official candlesticks table unchanged

**Cons**:
- ⚠️ Computation overhead on each request (if query-time)
- ⚠️ Requires trade data to be loaded/joined

**API Endpoint**:
```python
@router.get("/probabilities/{game_id}/kalshi-candles")
def get_kalshi_candles(
    game_id: str,
    interval_seconds: int = 60,  # Seconds: 60 = 1 minute, 1 = 1 second, 10 = 10 seconds
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    source: str = "auto"  # "official" (candlesticks table) or "trades" (trade-derived)
):
    """
    Get Kalshi candlesticks for a game.
    
    - interval_seconds=60: Use official 1-minute candles from kalshi.candlesticks (includes bid/ask)
    - interval_seconds=1, 10, etc.: Generate trade-derived candles from kalshi.trades (execution-only)
    
    Trade-derived candles are execution-only (last-trade prices).
    Official candles include bid/ask OHLC that cannot be recreated from trades.
    """
    if interval_seconds == 60 and source != "trades":
        # Use official 1-minute candles (includes bid/ask)
        return get_official_candlesticks_from_db(game_id, start_ts, end_ts)
    else:
        # Generate trade-derived candles from trades
        return generate_trade_candles_from_trades(
            game_id, interval_seconds, start_ts, end_ts
        )
```

### 4.2 Phase 2: Enhanced Chart Visualization

**Frontend Changes** (`webapp/static/js/chart.js`):

1. **Add resolution selector**:
```javascript
<div class="chart-controls">
  <select id="candlestickResolution">
    <option value="60">1 Minute</option>
    <option value="1">1 Second (Detailed)</option>
  </select>
</div>
```

2. **Add volume overlay toggle**:
```javascript
<input type="checkbox" id="showVolume" />
<label for="showVolume">Show Volume</label>
```

3. **Update chart rendering**:
```javascript
async function loadKalshiCandles(gameId, resolution = 60) {
  const source = resolution === 60 ? 'official' : 'trades';
  const response = await fetch(
    `/api/probabilities/${gameId}/kalshi-candles?interval_seconds=${resolution}&source=${source}`
  );
  const candles = await response.json();
  
  // Update chart series with new resolution
  updateCandlestickSeries(candles, resolution);
}
```

### 4.3 Phase 3: Storage Optimization (Optional)

**If 1-second candlesticks prove valuable**, consider:

1. **Selective materialization**: Pre-compute 1-second candles for high-activity games only
2. **Time-based partitioning**: Store 1-second data for recent games, aggregate older games
3. **Compression**: Use columnar storage or compression for historical data

---

## 5. Pros and Cons Analysis

### 5.1 Creating 1-Second Candlesticks

**Pros** [[memory:8239723]]:
- ✅ **Up to 60x more granular**: When using 1-second intervals, capture rapid execution price movements missed by 1-minute candles
- ✅ **Better entry/exit timing**: More precise trading signal detection using actual trade timestamps
- ✅ **Volume granularity**: See trade activity patterns at second-level
- ✅ **Trade intensity visibility**: Identify liquidity/activity spikes (trade clusters) in real-time
- ✅ **Execution volatility visibility**: See rapid last-trade price changes missed by 1-minute candles
- ✅ **Enhanced visualization**: More detailed charts showing actual trade execution patterns

**Cons**:
- ❌ **Storage overhead**: Can be large if materialized; sparse storage only stores seconds with trades; actual multiplier depends on trade density
- ❌ **Computation cost**: Aggregation required (mitigated by query-time aggregation with caching)
- ❌ **Sparse periods**: Many seconds have no trades (gaps). Any fill is visualization-only, not ground truth.
- ❌ **API complexity**: Need to handle multiple resolutions and data sources (official vs. trade-derived)

**Design Pattern**: Time-Series Aggregation Pattern with Query-Time Aggregation
**Algorithm**: Sliding Window OHLC Aggregation (Sparse Storage)
**Big O Complexity**: O(n) for generation if trades are sorted, O(log n + k) for queries with indexes

### 5.2 Multi-Resolution Trade-Derived Candles

**Pros**:
- ✅ **Uses actual trade data**: No fake interpolation
- ✅ **On-demand computation**: No storage overhead (if query-time)
- ✅ **Multiple resolutions**: Can provide 10s, 1s, etc. on zoom
- ✅ **Data integrity**: Only shows observed trades

**Cons**:
- ❌ **Sparse coverage**: Many intervals have no trades
- ❌ **Computation overhead**: Requires trade data join on each request
- ❌ **Execution-only**: Cannot show bid/ask or spread

**Design Pattern**: Time-Window Aggregation Pattern
**Algorithm**: Sliding Window OHLC Aggregation with Sparse Storage
**Big O Complexity**: O(n log n) for generation (due to sorting), O(log n + k) for queries with indexes

### 5.3 Enhanced Visualizations

**Trade-Based Enhancements** (Available from trade data):
- ✅ **Volume insights**: See trading activity patterns
- ✅ **VWAP analysis**: Better entry/exit price estimation using actual trade volumes
- ✅ **Activity heatmaps**: Identify high-activity periods and trade clusters
- ✅ **Trade intensity**: Visualize trade frequency over time

**Quote-Based Enhancements** (Historical limitations):
- ⚠️ **1-minute bid/ask spread**: Can visualize using official 1-minute candlesticks only
- ❌ **Sub-minute spread**: NOT available from trade data (requires live orderbook)
- 🔮 **Future**: Capture live orderbook/trade WebSockets to enable true sub-minute spread/quote charts

**Cons**:
- ❌ **UI complexity**: More controls and overlays
- ❌ **Performance**: Rendering more data points
- ❌ **Cognitive load**: More information to process

---

## 6. Recommendations

### 6.1 Immediate Actions (Low Risk, High Value)

1. **Implement query-time aggregation endpoint for trade-derived candles** (Phase 1)
   - Generate 1-second/10-second candles from trades on-demand (no materialization)
   - Add caching layer for frequently-accessed games
   - No schema changes required (uses existing `kalshi.trades` table)
   - Returns sparse series (only intervals with trades)

2. **Add resolution selector to chart UI** (Phase 2)
   - Default to 1-minute (current behavior)
   - Allow users to switch to 1-second/10-second view
   - Lazy load trade-derived data only when requested

3. **Add volume overlay** (Phase 2)
   - Show trade volume as bar chart (use SUM(count), not COUNT(trades))
   - Helps identify high-activity periods and trade clusters

### 6.2 Medium-Term Enhancements

1. **Per-game/ticker materialization** (if query-time performance requires it)
   - Materialize trade-derived candles per ticker/game with explicit refresh strategy
   - NOT global materialized view refresh (too costly)
   - Cache frequently-accessed games

2. **Multi-resolution trade-derived candles** (Phase 3)
   - Provide 10-second and 1-second candles on zoom
   - Use actual trade data (no interpolation)
   - On-demand computation or cached materialization

3. **Enhanced simulation with trade data** (Phase 3)
   - Sub-minute entry/exit timing using actual trade timestamps
   - VWAP-based pricing using trade volumes
   - Execution price modeling (note: bid/ask spread not available from trades)

### 6.3 Long-Term Considerations

1. **Selective materialization** (if 1-second proves valuable)
   - Pre-compute for frequently-accessed games
   - Balance storage vs. computation

2. **Advanced visualizations**
   - Trade activity heatmaps (from trade data)
   - Volume-weighted indicators (from trade data)
   - 1-minute bid/ask spread shading (from official candlesticks only)
   - Live orderbook integration (future: WebSocket capture for sub-minute spread)

---

## 7. Technical Implementation Notes

### 7.1 Database Schema Considerations

**Keep `kalshi.candlesticks` unchanged** (official API candles table). Do NOT mutate it to support fractional minutes.

**Create separate table/view for trade-derived candles**:
```sql
-- Separate table for trade-derived candles (see Phase 1 implementation)
-- Uses integer interval_seconds (1, 10, 60, etc.), NOT fractional minutes
-- Stores only seconds/intervals that have trades (sparse storage)
```

**No schema changes to existing tables required** for Phase 1 (query-time aggregation or separate table).

### 7.2 API Endpoint Design

```python
@router.get("/probabilities/{game_id}/kalshi-candles")
def get_kalshi_candles(
    game_id: str,
    interval_seconds: int = 60,  # Seconds (60 = 1 minute, 1 = 1 second, 10 = 10 seconds)
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    source: str = "auto"  # "official" or "trades"
) -> dict[str, Any]:
    """
    Get Kalshi candlesticks for a game.
    
    Supports multiple resolutions:
    - interval_seconds=60, source="official": 1-minute candles from kalshi.candlesticks (includes bid/ask)
    - interval_seconds=1, source="trades": 1-second trade-derived candles (execution-only)
    - interval_seconds=10, source="trades": 10-second trade-derived candles (execution-only)
    
    Trade-derived candles are execution-only (last-trade prices).
    Official candles include bid/ask OHLC that cannot be recreated from trades.
    """
```

### 7.3 Frontend Chart Updates

**Lightweight Charts** supports candlestick series natively:
```javascript
const candlestickSeries = chart.addCandlestickSeries({
  upColor: '#00d4aa',
  downColor: '#ff6b6b',
  borderVisible: false,
  wickVisible: true,
  borderUpColor: '#00d4aa',
  borderDownColor: '#ff6b6b',
  wickUpColor: '#00d4aa',
  wickDownColor: '#ff6b6b',
});

// Data format: { time: timestamp, open: number, high: number, low: number, close: number }
candlestickSeries.setData(candles);
```

---

## 8. Conclusion

**Trade data can produce sub-minute execution-based candlesticks** (last-trade OHLC + volume/VWAP) that enhance chart visualizations, but with important limitations:

**What Trade Data Enables**:
1. ✅ Sub-minute execution-based candlesticks (1-second, 10-second, etc.)
2. ✅ Volume aggregation and VWAP calculation
3. ✅ Trade intensity/heatmap visualization
4. ✅ Execution timing for simulations

**What Trade Data Cannot Do**:
1. ❌ Reconstruct historical bid/ask quotes or spread evolution
2. ❌ Provide orderbook depth information
3. ❌ Fill gaps with meaningful quote data

**Recommended Approach**:
1. **Start with query-time aggregation** (no storage overhead, on-demand generation from trades)
2. **Add UI controls** for resolution selection (backward compatible)
3. **Enhance visualizations** with volume overlays and trade intensity heatmaps
4. **Use official 1-minute candlesticks** for bid/ask spread visualization (historical limitation)
5. **Plan for live orderbook capture** (WebSocket) for future sub-minute spread/quote charts
6. **Evaluate usage** before committing to materialization

This approach provides maximum flexibility with minimal risk, while being honest about the limitations of trade-derived data versus official candlestick data.

---

## Appendix: Sample Data Analysis

**Sample Game**: KXNBAGAME-25NOV30OKCPOR-POR
- **Total trades**: 10,567
- **Unique seconds**: 5,126
- **Average trades/second**: 2.06
- **Max trades/second**: 15
- **Unique minutes**: 170
- **Average trades/minute**: 62.16
- **Max trades/minute**: 252

**Conclusion**: Sufficient trade density for meaningful 1-second candlestick generation, but note:
- ~50% of seconds have zero trades (sparse coverage)
- Activity is bursty/clustered (not uniform)
- Many seconds will require sparse storage or visualization choices (forward-fill vs. gaps)
- Trade-derived candles are execution-only (cannot reconstruct bid/ask quotes)

---

## 9. Data Quality / Edge Cases

**Important Considerations**:

1. **Duplicate Timestamps**: Trades can share identical `created_time` values (same microsecond) and appear as multiple trade records. When aggregating, ensure all trades with the same timestamp are included in OHLC calculations.

2. **Large Block Trades**: Individual trades can have large `count` values (block trades). For volume bars and VWAP calculations, use **SUM(count)**, not COUNT(trades). A single trade with `count=1000` represents more volume than 10 trades with `count=1` each.

3. **Quiet Windows**: Markets can have long quiet windows with no trades (especially early in games or during timeouts). Don't assume continuous sampling—gaps are normal and represent periods with no market activity.

4. **Trade Ordering**: When processing trades for OHLC, always sort by `created_time` within each aggregation interval. Do not assume trades arrive in chronological order.

5. **Price Precision**: Use integer cents (`yes_price`, `no_price`) for all calculations. The `price` field (NUMERIC) is for reference but should not be used for OHLC calculations to avoid floating-point precision issues.

