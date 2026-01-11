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
  
  const tickers = [
    'KXNBAGAME-25DEC19SASATL-ATL',   // SAS @ ATL - settled
    'KXNBAGAME-25DEC19MIABOS-BOS',   // MIA @ BOS - settled
    'KXNBAGAME-25DEC25HOULAL-LAL',   // HOU @ LAL - active (Christmas)
  ];
  
  for (const ticker of tickers) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`MARKET: ${ticker}`);
    console.log('='.repeat(80));
    
    try {
      const { data } = await marketApi.getMarket(ticker);
      const m = data.market;
      console.log(JSON.stringify({
        ticker: m.ticker,
        title: m.title,
        status: m.status,
        result: m.result,
        rules_primary: m.rules_primary,
        open_time: m.open_time,
        close_time: m.close_time,
        volume: m.volume,
        open_interest: m.open_interest,
        last_price: m.last_price,
        yes_bid: m.yes_bid,
        yes_ask: m.yes_ask,
        no_bid: m.no_bid,
        no_ask: m.no_ask,
      }, null, 2));
    } catch (e: any) {
      console.log('Error:', e.response?.status, e.response?.data);
    }
  }
  
  // Also show candlestick data for one game
  console.log(`\n${'='.repeat(80)}`);
  console.log('CANDLESTICK DATA: KXNBAGAME-25DEC19SASATL-ATL');
  console.log('='.repeat(80));
  
  const startTs = Math.floor(new Date('2025-12-19').getTime() / 1000);
  const endTs = Math.floor(new Date('2025-12-21').getTime() / 1000);
  
  const { data: candleData } = await marketApi.getMarketCandlesticks(
    'KXNBAGAME', 
    'KXNBAGAME-25DEC19SASATL-ATL',
    startTs,
    endTs,
    1  // 1 minute intervals
  );
  
  console.log(`Total candlesticks: ${candleData.candlesticks?.length || 0}`);
  console.log('\nFirst 5 candlesticks with volume:');
  const withVolume = candleData.candlesticks?.filter((c: any) => c.volume > 0) || [];
  console.log(`Candlesticks with volume: ${withVolume.length}`);
  
  for (const c of withVolume.slice(0, 5)) {
    console.log(JSON.stringify({
      end_period_ts: c.end_period_ts,
      time: new Date(c.end_period_ts * 1000).toISOString(),
      volume: c.volume,
      yes_bid: c.yes_bid,
      yes_ask: c.yes_ask,
      open: c.open,
      close: c.close,
      high: c.high,
      low: c.low,
    }, null, 2));
  }
}

main().catch(console.error);
