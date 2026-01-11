# Kalshi WebSocket API Research

**Date**: 2025-01-28  
**Status**: In Progress  
**Researcher**: AI Assistant  
**Sprint**: Sprint 09 - Live Games Backend Infrastructure

## Objective

Research and document the Kalshi WebSocket API for real-time market data streaming to enable live game probability updates.

## Current Knowledge

### Historical Data (Known)

**REST API Endpoints**:
- Base URL: `https://api.elections.kalshi.com/trade-api/v2/`
- Markets: `GET /markets?series_ticker=KXNBAGAME&limit=100`
- Market Details: `GET /markets/{ticker}`
- Candlesticks: `GET /series/{series_ticker}/markets/{ticker}/candlesticks?start_ts={}&end_ts={}&period_interval=1`
- **Authentication**: Required (API key + private key)
- **File**: `scripts/kalshi/test-api.ts` - Example REST API usage

**Data Format**:
- Ticker format: `KXNBAGAME-{YYMMDD}{AWAY}{HOME}-{TEAM}` (e.g., `KXNBAGAME-25DEC19SASATL-ATL`)
- Candlestick fields: `end_period_ts`, `price.close`, `yes_bid.close`, `yes_ask.close`, `volume`
- Database table: `kalshi.candlesticks`

### WebSocket API (To Be Researched)

**Known from Web Search**:
- WebSocket endpoint: `wss://api.elections.kalshi.com`
- Authentication: API key required during handshake
- Documentation: https://docs.kalshi.com/websockets/websocket-connection
- SDKs available: Python SDK, TypeScript SDK

## Research Questions

1. ⏳ What is the exact WebSocket endpoint URL?
2. ⏳ What authentication mechanism is used (API key in headers, query params, or initial message)?
3. ⏳ What is the message format (JSON, binary, etc.)?
4. ⏳ How do we subscribe to specific markets?
5. ⏳ What message types are available (market updates, trades, orderbook)?
6. ⏳ What is the message frequency?
7. ⏳ How do we handle reconnection?
8. ⏳ Are there connection limits?

## Testing Plan

### Test 1: WebSocket Connection
- **Endpoint**: `wss://api.elections.kalshi.com`
- **Purpose**: Verify connection can be established
- **Authentication**: Test with API key
- **Expected**: Connection established, authentication successful

### Test 2: Market Subscription
- **Purpose**: Subscribe to a specific NBA market ticker
- **Method**: Send subscription message after authentication
- **Expected**: Receive market update messages

### Test 3: Message Format
- **Purpose**: Understand message structure
- **Method**: Capture and analyze incoming messages
- **Expected**: JSON format with market data fields

### Test 4: Update Frequency
- **Purpose**: Measure how often updates arrive
- **Method**: Monitor messages during active market
- **Expected**: Updates every few seconds (to be determined)

## Test Results

### Test 1: WebSocket Connection

**Status**: ⏳ Not yet tested

**Planned Test**:
```python
import asyncio
import websockets
import json

async def test_connection():
    uri = "wss://api.elections.kalshi.com"
    # Need to add authentication
    async with websockets.connect(uri) as websocket:
        # Send authentication message
        # Wait for confirmation
        pass
```

**Findings**:
- [To be documented]

### Test 2: Market Subscription

**Status**: ⏳ Not yet tested

**Findings**:
- [To be documented]

### Test 3: Message Format

**Status**: ⏳ Not yet tested

**Findings**:
- [To be documented]

### Test 4: Update Frequency

**Status**: ⏳ Not yet tested (requires live market)

**Findings**:
- [To be documented]

## Implementation Notes

### Authentication

**Expected Approach** (based on REST API):
- API key ID and private key required
- May need to sign messages or use token-based auth
- Check Kalshi documentation for WebSocket-specific auth

### Subscription Mechanism

**Expected Format**:
```json
{
  "type": "subscribe",
  "channel": "market",
  "ticker": "KXNBAGAME-25DEC19SASATL-ATL"
}
```

### Message Format (Expected)

**Market Update Message**:
```json
{
  "type": "market_update",
  "ticker": "KXNBAGAME-25DEC19SASATL-ATL",
  "timestamp": 1234567890,
  "price": {
    "close": 65,  // cents (0-100)
    "bid": 64,
    "ask": 66
  },
  "yes_bid": 64,
  "yes_ask": 66,
  "volume": 1234
}
```

### Python Implementation (Planned)

```python
import asyncio
import websockets
import json
from pathlib import Path

async def connect_kalshi_websocket(api_key_id: str, private_key_path: Path):
    """Connect to Kalshi WebSocket and subscribe to market."""
    uri = "wss://api.elections.kalshi.com"
    
    async with websockets.connect(uri) as websocket:
        # Authenticate (format TBD)
        auth_message = {
            "type": "auth",
            "api_key": api_key_id,
            # May need signature or token
        }
        await websocket.send(json.dumps(auth_message))
        
        # Wait for auth confirmation
        response = await websocket.recv()
        auth_result = json.loads(response)
        
        if auth_result.get("status") != "authenticated":
            raise RuntimeError("Authentication failed")
        
        # Subscribe to market
        subscribe_message = {
            "type": "subscribe",
            "channel": "market",
            "ticker": "KXNBAGAME-25DEC19SASATL-ATL"
        }
        await websocket.send(json.dumps(subscribe_message))
        
        # Listen for updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received: {data}")
            # Process market update
```

## Alternative: REST API Polling

**If WebSocket is not available or too complex**:
- Poll candlesticks endpoint every 5-10 seconds
- Use `getMarketCandlesticks()` with recent time range
- Track last seen `end_period_ts` to detect new data
- **Pros**: Simpler, uses existing REST API
- **Cons**: Less efficient, higher latency

## Next Steps

1. ⏳ Review Kalshi WebSocket documentation: https://docs.kalshi.com/websockets/websocket-connection
2. ⏳ Test WebSocket connection with authentication
3. ⏳ Test market subscription
4. ⏳ Document message format
5. ⏳ Test during live market (if available)
6. ⏳ Measure update frequency
7. ⏳ Create working Python code snippet
8. ⏳ Document findings and recommendations

## References

- Kalshi WebSocket Docs: https://docs.kalshi.com/websockets/websocket-connection
- Kalshi TypeScript SDK: `scripts/kalshi/node_modules/kalshi-typescript/`
- Existing REST API usage: `scripts/kalshi/test-api.ts`
- Database schema: `kalshi.candlesticks` table

## Summary

### ✅ Confirmed

1. **WebSocket Endpoint**: `wss://api.elections.kalshi.com` (from web search)
2. **Authentication Required**: API key needed (from web search)
3. **REST API Works**: Confirmed via existing scripts
4. **REST API Endpoints**: Fully functional for historical data

### ⚠️ Requires Testing

1. **WebSocket Connection**: Need to test actual connection (requires live market)
2. **Authentication Method**: Exact format unknown (need to review docs.kalshi.com)
3. **Subscription Format**: Message format unknown
4. **Message Structure**: Data format unknown
5. **Update Frequency**: Unknown

### ✅ Recommended Approach: REST API Polling (Initial Implementation)

**Rationale**:
- REST API is confirmed working
- WebSocket requires live market testing (not available now)
- REST polling is simpler to implement and debug
- Can upgrade to WebSocket later if needed

**Implementation**:
- Use `getMarketCandlesticks()` endpoint
- Poll every 5-10 seconds during live games
- Track last `end_period_ts` to detect new candlesticks
- Transform to match historical data format

**Code Example**:
```python
async def poll_kalshi_market(ticker: str, last_timestamp: int = None):
    """Poll Kalshi market for new candlesticks."""
    end_ts = int(time.time())
    start_ts = end_ts - 300  # Last 5 minutes
    
    # Use existing MarketApi from kalshi-typescript SDK
    # Or implement REST call directly
    response = await market_api.getMarketCandlesticks(
        'KXNBAGAME', ticker, start_ts, end_ts, 1  # 1-minute intervals
    )
    
    new_candles = []
    for candle in response.candlesticks:
        if last_timestamp is None or candle.end_period_ts > last_timestamp:
            new_candles.append({
                "time": candle.end_period_ts,
                "price": candle.price.close / 100.0,  # Convert cents to 0-1
                "yes_bid": candle.yes_bid.close / 100.0,
                "yes_ask": candle.yes_ask.close / 100.0,
            })
    
    return new_candles, max(c.end_period_ts for c in response.candlesticks) if response.candlesticks else last_timestamp
```

### Future Enhancement: WebSocket

Once WebSocket is tested and documented:
- Upgrade from REST polling to WebSocket
- Lower latency, more efficient
- Real-time push updates instead of polling

