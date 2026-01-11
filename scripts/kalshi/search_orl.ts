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
  
  console.log('=== Searching for ORL games ===');
  const { data } = await marketApi.getMarkets(undefined, 100, undefined, 'KXNBAGAME');
  
  const orlGames = data.markets?.filter(m => m.ticker?.includes('ORL'));
  console.log(`ORL games in first page: ${orlGames?.length || 0}`);
  orlGames?.forEach(m => console.log(`  ${m.ticker} - ${m.status}`));
  
  console.log('\n=== Searching for MIN games ===');
  const minGames = data.markets?.filter(m => m.ticker?.includes('MIN'));
  console.log(`MIN games in first page: ${minGames?.length || 0}`);
  minGames?.forEach(m => console.log(`  ${m.ticker} - ${m.status}`));
  
  // Try direct lookup of the ticker
  console.log('\n=== Direct lookup of KXNBAGAME-25DEC19ORLMIN-MIN ===');
  try {
    const { data: marketData } = await marketApi.getMarket('KXNBAGAME-25DEC19ORLMIN-MIN');
    console.log('FOUND!', marketData.market?.status);
  } catch (e: any) {
    console.log(`Not found: ${e.response?.status}`);
  }
  
  // Try alternative tickers
  const alts = [
    'KXNBAGAME-25DEC19MINORL-MIN',
    'KXNBAGAME-25DEC19MINORL-ORL',
    'KXNBAGAME-25DEC20ORLMIN-MIN',
    'KXNBAGAME-25DEC20ORLMIN-ORL',
  ];
  
  for (const t of alts) {
    try {
      const { data: marketData } = await marketApi.getMarket(t);
      console.log(`${t} - FOUND! ${marketData.market?.status}`);
    } catch (e: any) {
      console.log(`${t} - not found`);
    }
  }
}

main().catch(console.error);
