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
  
  // Search for specific team games - check different date patterns
  const testCases = [
    'KXNBAGAME-25DEC18LALPHX',  // LAL - should exist for Dec 18
    'KXNBAGAME-25DEC19OKLMIN',  // Try OKC as OKL?
    'KXNBAGAME-25DEC18GSWBKN',  // GSW 
    'KXNBAGAME-25DEC18DENCLEV', // Try CLEV instead of CLE
  ];
  
  for (const baseTickr of testCases) {
    console.log(`\nSearching for: ${baseTickr}*`);
    
    // Try home team variant
    for (const suffix of ['-LAL', '-PHX', '-MIN', '-OKC', '-BKN', '-GSW', '-DEN', '-CLE', '-CLEV']) {
      const ticker = baseTickr + suffix;
      try {
        const { data } = await marketApi.getMarket(ticker);
        if (data.market) {
          console.log(`  FOUND: ${ticker} - ${data.market.status}`);
        }
      } catch (e: any) {
        if (e.response?.status !== 404) {
          console.log(`  Error for ${ticker}: ${e.response?.status}`);
        }
      }
    }
  }
  
  // Also search broadly for LAL games
  console.log('\n\n=== Searching for any LAL games ===');
  const { data } = await marketApi.getMarkets(undefined, 100, undefined, 'KXNBAGAME');
  const lalGames = data.markets?.filter(m => m.ticker?.includes('LAL'));
  console.log(`LAL games found: ${lalGames?.length || 0}`);
  lalGames?.forEach(m => console.log(`  ${m.ticker}`));
  
  // Search for OKC
  console.log('\n=== Searching for any OKC games ===');
  const okcGames = data.markets?.filter(m => m.ticker?.includes('OKC'));
  console.log(`OKC games found: ${okcGames?.length || 0}`);
  okcGames?.forEach(m => console.log(`  ${m.ticker}`));
}

main().catch(console.error);
