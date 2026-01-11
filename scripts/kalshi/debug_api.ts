import { MarketApi, Configuration } from 'kalshi-typescript';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import axios from 'axios';

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
  
  // Test 1: Try a market that EXISTS
  console.log('=== TEST 1: Market that EXISTS ===');
  console.log('Ticker: KXNBAGAME-25DEC19SASATL-ATL\n');
  try {
    const { data } = await marketApi.getMarket('KXNBAGAME-25DEC19SASATL-ATL');
    console.log('Response:', JSON.stringify(data, null, 2));
  } catch (e: any) {
    console.log('Error:', e.response?.status, e.response?.data);
  }
  
  // Test 2: Try a market that DOESN'T exist
  console.log('\n\n=== TEST 2: Market that DOES NOT exist ===');
  console.log('Ticker: KXNBAGAME-25DEC19ORLMIN-MIN\n');
  try {
    const { data } = await marketApi.getMarket('KXNBAGAME-25DEC19ORLMIN-MIN');
    console.log('Response:', JSON.stringify(data, null, 2));
  } catch (e: any) {
    console.log('HTTP Status:', e.response?.status);
    console.log('Response Data:', JSON.stringify(e.response?.data, null, 2));
  }
  
  // Test 3: Try another non-existent market
  console.log('\n\n=== TEST 3: Another non-existent market ===');
  console.log('Ticker: KXNBAGAME-25DEC18LALPHX-LAL\n');
  try {
    const { data } = await marketApi.getMarket('KXNBAGAME-25DEC18LALPHX-LAL');
    console.log('Response:', JSON.stringify(data, null, 2));
  } catch (e: any) {
    console.log('HTTP Status:', e.response?.status);
    console.log('Response Data:', JSON.stringify(e.response?.data, null, 2));
  }
  
  // Test 4: Try a completely invalid ticker format
  console.log('\n\n=== TEST 4: Invalid ticker format ===');
  console.log('Ticker: INVALID-TICKER-12345\n');
  try {
    const { data } = await marketApi.getMarket('INVALID-TICKER-12345');
    console.log('Response:', JSON.stringify(data, null, 2));
  } catch (e: any) {
    console.log('HTTP Status:', e.response?.status);
    console.log('Response Data:', JSON.stringify(e.response?.data, null, 2));
  }
}

main().catch(console.error);
