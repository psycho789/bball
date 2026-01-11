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
  
  console.log('=== Fetching NBA Game markets from Kalshi (first page) ===\n');
  
  // Just get first 100 without pagination
  const { data } = await marketApi.getMarkets(
    undefined,   // cursor
    100,         // limit
    undefined,   // event_ticker
    'KXNBAGAME'  // series_ticker - NBA Game series
  );
  
  console.log(`Found ${data.markets?.length || 0} NBA Game markets in first page`);
  console.log(`Has more (cursor): ${data.cursor ? 'YES' : 'NO'}`);
  
  if (data.markets && data.markets.length > 0) {
    // Group by date
    const byDate: { [key: string]: any[] } = {};
    const byStatus: { [key: string]: number } = {};
    
    for (const m of data.markets) {
      const match = m.ticker?.match(/KXNBAGAME-(\d{2}[A-Z]{3}\d{2})/);
      const date = match ? match[1] : 'unknown';
      if (!byDate[date]) byDate[date] = [];
      byDate[date].push(m);
      
      byStatus[m.status] = (byStatus[m.status] || 0) + 1;
    }
    
    console.log('\nMarkets by status:');
    for (const [status, count] of Object.entries(byStatus)) {
      console.log(`  ${status}: ${count}`);
    }
    
    const dates = Object.keys(byDate).sort();
    console.log(`\nDate range: ${dates[0]} to ${dates[dates.length-1]}`);
    
    console.log('\nSample tickers:');
    for (const m of data.markets.slice(0, 20)) {
      console.log(`  ${m.ticker} - ${m.status} - result: ${m.result || 'pending'}`);
    }
  }
}

main().catch(console.error);
