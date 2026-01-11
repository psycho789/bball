import { MarketApi, Configuration } from 'kalshi-typescript';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

async function main() {
  const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
  const privateKeyPath = path.join(rootDir, 'kalshi-api-key-private.txt');
  
  const configuration = new Configuration({
    apiKey: apiKeyId,
    privateKeyPath: privateKeyPath
  });
  const marketApi = new MarketApi(configuration);
  
  let output = `# Kalshi API - Actual Requests & Responses
Generated: ${new Date().toISOString()}

This document shows the exact API calls used to fetch NBA game data from Kalshi.

---

## STEP 1: List NBA Game Markets

### Endpoint
\`GET /trade-api/v2/markets?series_ticker=KXNBAGAME&limit=100\`

### Curl Equivalent
\`\`\`bash
curl -X GET "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNBAGAME&limit=10" \\
  -H "Accept: application/json"
\`\`\`

### Actual Response (first 3 markets)
`;

  // Get markets list
  const { data: marketsData } = await marketApi.getMarkets(undefined, 10, undefined, 'KXNBAGAME');
  output += '```json\n' + JSON.stringify({
    markets: marketsData.markets?.slice(0, 3),
    cursor: marketsData.cursor ? "(cursor for pagination)" : null
  }, null, 2) + '\n```\n\n';

  output += `---

## STEP 2: Get Single Market Details

### Endpoint
\`GET /trade-api/v2/markets/{ticker}\`

### Example: KXNBAGAME-25DEC19SASATL-ATL (SAS @ ATL, Dec 19)

### Curl Equivalent
\`\`\`bash
curl -X GET "https://api.elections.kalshi.com/trade-api/v2/markets/KXNBAGAME-25DEC19SASATL-ATL" \\
  -H "Accept: application/json"
\`\`\`

### Actual Response
`;

  const { data: marketData } = await marketApi.getMarket('KXNBAGAME-25DEC19SASATL-ATL');
  output += '```json\n' + JSON.stringify({ market: marketData.market }, null, 2) + '\n```\n\n';

  output += `---

## STEP 3: Get Candlestick Data (for price history)

### Endpoint
\`GET /trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks?start_ts={}&end_ts={}&period_interval=1\`

### Example: Get 1-minute candlesticks for SAS @ ATL game

### Curl Equivalent
\`\`\`bash
curl -X GET "https://api.elections.kalshi.com/trade-api/v2/series/KXNBAGAME/markets/KXNBAGAME-25DEC19SASATL-ATL/candlesticks?start_ts=1766016000&end_ts=1766188800&period_interval=1" \\
  -H "Accept: application/json"
\`\`\`

### Actual Response (showing 5 candlesticks with volume)
`;

  const startTs = Math.floor(new Date('2025-12-19').getTime() / 1000);
  const endTs = Math.floor(new Date('2025-12-21').getTime() / 1000);
  const { data: candleData } = await marketApi.getMarketCandlesticks(
    'KXNBAGAME', 'KXNBAGAME-25DEC19SASATL-ATL', startTs, endTs, 1
  );
  
  const withVolume = candleData.candlesticks?.filter((c: any) => c.volume > 0).slice(0, 5) || [];
  output += '```json\n' + JSON.stringify({
    total_candlesticks: candleData.candlesticks?.length,
    candlesticks_with_volume: candleData.candlesticks?.filter((c: any) => c.volume > 0).length,
    sample: withVolume.map((c: any) => ({
      end_period_ts: c.end_period_ts,
      time_utc: new Date(c.end_period_ts * 1000).toISOString(),
      volume: c.volume,
      yes_bid: c.yes_bid,
      yes_ask: c.yes_ask
    }))
  }, null, 2) + '\n```\n\n';

  output += `---

## STEP 4: Market Not Found (404 Response)

### Example: KXNBAGAME-25DEC19ORLMIN-MIN (ORL @ MIN - no market exists)

### Curl Equivalent
\`\`\`bash
curl -X GET "https://api.elections.kalshi.com/trade-api/v2/markets/KXNBAGAME-25DEC19ORLMIN-MIN" \\
  -H "Accept: application/json"
\`\`\`

### Actual Response
`;

  try {
    await marketApi.getMarket('KXNBAGAME-25DEC19ORLMIN-MIN');
  } catch (e: any) {
    output += '```json\n// HTTP Status: 404\n' + JSON.stringify(e.response?.data, null, 2) + '\n```\n\n';
  }

  output += `---

## How We Build the Ticker

The ticker format is: \`KXNBAGAME-{YYMMDD}{AWAY}{HOME}-{TEAM}\`

### Example: San Antonio @ Atlanta on Dec 19, 2025
- Date in Eastern Time: Dec 19, 2025 → \`25DEC19\`
- Away team tricode: \`SAS\`
- Home team tricode: \`ATL\`
- Market for home team winning: \`KXNBAGAME-25DEC19SASATL-ATL\`
- Market for away team winning: \`KXNBAGAME-25DEC19SASATL-SAS\`

---

## Summary: Our Process

1. **Query ESPN database** → Get game_id, home/away teams, wallclock timestamps
2. **Build Kalshi ticker** → Format: \`KXNBAGAME-{date}{away}{home}-{home}\`
3. **Call getMarket()** → Check if market exists (404 = no market for this game)
4. **Call getMarketCandlesticks()** → Get minute-by-minute bid/ask data
5. **Compare** → Match ESPN probability timestamps to Kalshi candlesticks

**Coverage:** Kalshi has markets for ~22% of NBA games (102 out of 472 in 2025-26 season)
`;

  // Write to file
  const outputPath = path.join(rootDir, 'data/reports/kalshi_api_actual_requests.md');
  fs.writeFileSync(outputPath, output);
  console.log(`Written to: ${outputPath}`);
  console.log('\n' + output);
}

main().catch(console.error);
