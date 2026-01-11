import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

const BASE_URL = 'https://api.elections.kalshi.com/trade-api/v2';

function signRequest(privateKeyPem: string, timestamp: string, method: string, path: string): string {
  const message = `${timestamp}${method}${path}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(message);
  return sign.sign(privateKeyPem, 'base64');
}

async function checkSeries() {
  const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
  const privateKey = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-private.txt'), 'utf-8');
  
  // Search for NBA-related series
  const searchTerms = ['NBA', 'basketball', 'preseason'];
  
  for (const term of searchTerms) {
    const timestamp = Date.now().toString();
    const endpoint = `/series?search=${encodeURIComponent(term)}`;
    const urlPath = `/trade-api/v2${endpoint}`;
    const signature = signRequest(privateKey, timestamp, 'GET', urlPath);
    
    console.log(`\nSearching for: "${term}"`);
    
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'KALSHI-ACCESS-KEY': apiKeyId,
        'KALSHI-ACCESS-SIGNATURE': signature,
        'KALSHI-ACCESS-TIMESTAMP': timestamp,
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log(`Found ${data.series?.length || 0} series:`);
      data.series?.forEach((s: any) => {
        console.log(`  - ${s.ticker}: ${s.title}`);
      });
    } else {
      console.log(`Error: ${response.status}`);
    }
    
    await new Promise(r => setTimeout(r, 500));
  }
}

checkSeries().catch(console.error);
