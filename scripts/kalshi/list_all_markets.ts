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
  
  console.log('=== GET all NBA markets from Kalshi ===\n');
  
  // Get first page
  const { data } = await marketApi.getMarkets(undefined, 100, undefined, 'KXNBAGAME');
  
  console.log(`Total markets in first page: ${data.markets?.length}`);
  console.log(`Has more pages: ${data.cursor ? 'YES' : 'NO'}\n`);
  
  console.log('=== ACTUAL TICKERS FROM KALSHI ===\n');
  
  // Show unique event tickers (game-level, not team-level)
  const eventTickers = new Set<string>();
  data.markets?.forEach(m => {
    if (m.event_ticker) eventTickers.add(m.event_ticker);
  });
  
  console.log('Unique games (event_ticker):');
  Array.from(eventTickers).sort().forEach(t => console.log(`  ${t}`));
  
  console.log(`\n\nTotal unique games: ${eventTickers.size}`);
  console.log('Each game has 2 markets (one for each team winning)\n');
  
  // Parse one ticker to show the structure
  console.log('=== PARSING A TICKER ===\n');
  const sampleTicker = 'KXNBAGAME-25DEC19SASATL';
  const match = sampleTicker.match(/KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})/);
  if (match) {
    console.log(`Ticker: ${sampleTicker}`);
    console.log(`  Year: 20${match[1]}`);
    console.log(`  Month: ${match[2]}`);
    console.log(`  Day: ${match[3]}`);
    console.log(`  Away: ${match[4]}`);
    console.log(`  Home: ${match[5]}`);
  }
}

main().catch(console.error);
