/**
 * Fetch all Kalshi NBA Game markets and store raw responses locally
 * 
 * Uses direct HTTP calls to avoid SDK pagination bug
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

const OUTPUT_DIR = path.join(rootDir, 'data/raw/kalshi/markets');
const BASE_URL = 'https://api.elections.kalshi.com/trade-api/v2';

function signRequest(privateKeyPem: string, timestamp: string, method: string, path: string): string {
  const message = `${timestamp}${method}${path}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(message);
  return sign.sign(privateKeyPem, 'base64');
}

async function fetchWithAuth(endpoint: string, apiKeyId: string, privateKey: string): Promise<any> {
  const timestamp = Date.now().toString();
  const method = 'GET';
  const urlPath = `/trade-api/v2${endpoint}`;
  
  const signature = signRequest(privateKey, timestamp, method, urlPath);
  
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'KALSHI-ACCESS-KEY': apiKeyId,
      'KALSHI-ACCESS-SIGNATURE': signature,
      'KALSHI-ACCESS-TIMESTAMP': timestamp,
    }
  });
  
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  
  return response.json();
}

async function fetchAllMarkets() {
  const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
  const privateKey = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-private.txt'), 'utf-8');
  
  console.log('=== Fetching ALL Kalshi NBA Game Markets ===\n');
  
  const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15) + 'Z';
  const sessionDir = path.join(OUTPUT_DIR, `fetch_${timestamp}`);
  fs.mkdirSync(sessionDir, { recursive: true });
  
  let allMarkets: any[] = [];
  let cursor: string | null = null;
  let pageNum = 0;
  
  do {
    pageNum++;
    console.log(`Fetching page ${pageNum}...`);
    
    try {
      let endpoint = `/markets?series_ticker=KXNBAGAME&limit=200`;
      if (cursor) {
        endpoint += `&cursor=${encodeURIComponent(cursor)}`;
      }
      
      const data = await fetchWithAuth(endpoint, apiKeyId, privateKey);
      
      // Save raw response for this page
      const pageFile = path.join(sessionDir, `page_${pageNum.toString().padStart(3, '0')}.json`);
      fs.writeFileSync(pageFile, JSON.stringify(data, null, 2));
      console.log(`  Saved: ${pageFile}`);
      console.log(`  Markets in page: ${data.markets?.length || 0}`);
      
      if (data.markets) {
        allMarkets = allMarkets.concat(data.markets);
      }
      
      cursor = data.cursor || null;
      console.log(`  Has more: ${cursor ? 'YES' : 'NO'}`);
      
      // Rate limiting
      await new Promise(resolve => setTimeout(resolve, 300));
      
    } catch (e: any) {
      console.error(`Error fetching page ${pageNum}:`, e.message);
      break;
    }
    
  } while (cursor);
  
  console.log(`\n=== COMPLETE ===`);
  console.log(`Total pages: ${pageNum}`);
  console.log(`Total markets: ${allMarkets.length}`);
  
  // Save combined markets file
  const combinedFile = path.join(sessionDir, 'all_markets.json');
  fs.writeFileSync(combinedFile, JSON.stringify({
    fetch_timestamp: timestamp,
    series_ticker: 'KXNBAGAME',
    total_markets: allMarkets.length,
    markets: allMarkets
  }, null, 2));
  console.log(`\nSaved combined: ${combinedFile}`);
  
  // Also save to a "latest" file
  const latestFile = path.join(OUTPUT_DIR, 'KXNBAGAME_latest.json');
  fs.writeFileSync(latestFile, JSON.stringify({
    fetch_timestamp: timestamp,
    series_ticker: 'KXNBAGAME',
    total_markets: allMarkets.length,
    markets: allMarkets
  }, null, 2));
  console.log(`Saved latest: ${latestFile}`);
  
  // Summary stats
  console.log('\n=== SUMMARY ===');
  
  // Group by status
  const byStatus: { [key: string]: number } = {};
  allMarkets.forEach(m => {
    byStatus[m.status] = (byStatus[m.status] || 0) + 1;
  });
  console.log('\nBy status:');
  Object.entries(byStatus).forEach(([status, count]) => {
    console.log(`  ${status}: ${count}`);
  });
  
  // Group by date (unique games)
  const uniqueEvents = new Set(allMarkets.map(m => m.event_ticker));
  console.log(`\nUnique games (events): ${uniqueEvents.size}`);
  
  // Date range
  const dates = Array.from(uniqueEvents).map(t => {
    const match = (t as string).match(/KXNBAGAME-(\d{2}[A-Z]{3}\d{2})/);
    return match ? match[1] : null;
  }).filter(Boolean).sort();
  
  if (dates.length > 0) {
    console.log(`Date range: ${dates[0]} to ${dates[dates.length - 1]}`);
  }
  
  return allMarkets;
}

fetchAllMarkets().catch(console.error);
