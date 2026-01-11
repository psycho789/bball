/**
 * Fetch candlestick data from Kalshi API for all market tickers in our database
 * that don't already have candlestick data.
 */

import { MarketApi, Configuration } from 'kalshi-typescript';
import { Client } from 'pg';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');

const OUTPUT_DIR = path.join(rootDir, 'data/raw/kalshi/candlesticks');

interface TickerInfo {
  ticker: string;
  expected_expiration_time: Date;
}

async function getTickersNeedingCandles(pgClient: Client, specificTickers?: string[]): Promise<TickerInfo[]> {
  let query: string;
  let params: any[];
  
  if (specificTickers && specificTickers.length > 0) {
    // Fetch specific tickers (even if they already have candlesticks - for re-fetching raw files)
    query = `
      SELECT DISTINCT 
        km.ticker,
        km.expected_expiration_time
      FROM kalshi.markets km
      WHERE km.ticker = ANY($1)
        AND km.expected_expiration_time IS NOT NULL
      ORDER BY km.expected_expiration_time DESC
    `;
    params = [specificTickers];
  } else {
    // Fetch tickers that:
    // 1. Don't have candlesticks yet, OR
    // 2. Have games scheduled in the next 3 days (to get latest data for upcoming games), OR
    // 3. Have incomplete candlestick data (latest candlestick is before the game date)
    query = `
      SELECT DISTINCT 
        km.ticker,
        km.expected_expiration_time
      FROM kalshi.markets km
      LEFT JOIN kalshi.markets_with_games kmw ON km.ticker = kmw.ticker
      LEFT JOIN espn.scoreboard_games sg ON kmw.espn_event_id = sg.event_id
      LEFT JOIN LATERAL (
        SELECT MAX(period_ts) as latest_candle_ts
        FROM kalshi.candlesticks c
        WHERE c.ticker = km.ticker
          AND (c.price_close IS NOT NULL OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL))
      ) latest_candle ON true
      WHERE km.expected_expiration_time IS NOT NULL
        AND (
          -- Tickers that don't have candlesticks yet
          latest_candle.latest_candle_ts IS NULL
          OR
          -- Tickers for games scheduled in the next 3 days (to refresh data)
          (sg.event_date IS NOT NULL 
           AND sg.event_date >= CURRENT_DATE 
           AND sg.event_date <= CURRENT_DATE + INTERVAL '3 days')
          OR
          -- Tickers with incomplete data: latest candlestick is before the game date
          (sg.event_date IS NOT NULL 
           AND latest_candle.latest_candle_ts IS NOT NULL
           AND latest_candle.latest_candle_ts < sg.event_date)
        )
      ORDER BY km.expected_expiration_time DESC
    `;
    params = [];
  }
  
  const result = await pgClient.query(query, params);
  
  return result.rows.map(row => ({
    ticker: row.ticker,
    expected_expiration_time: new Date(row.expected_expiration_time)
  }));
}

async function fetchAndStoreCandlesticks(
  marketApi: MarketApi,
  pgClient: Client,
  ticker: string,
  gameTime: Date,
  sessionDir: string
): Promise<number> {
  // Fetch candlesticks for 3 days around the game (1 day before, game day, 1 day after)
  // This ensures we get data even if the game time shifts or we fetch early
  const dayStart = new Date(gameTime);
  dayStart.setUTCHours(0, 0, 0, 0);
  dayStart.setDate(dayStart.getDate() - 1);
  
  const dayEnd = new Date(gameTime);
  dayEnd.setUTCHours(23, 59, 59, 999);
  dayEnd.setDate(dayEnd.getDate() + 1);
  
  const startTs = Math.floor(dayStart.getTime() / 1000);
  const endTs = Math.floor(dayEnd.getTime() / 1000);
  
  const endpoint = `/series/KXNBAGAME/markets/${ticker}/candlesticks?start_ts=${startTs}&end_ts=${endTs}&period_interval=1`;
  
  try {
    const { data } = await marketApi.getMarketCandlesticks(
      'KXNBAGAME', ticker, startTs, endTs, 1  // 1-minute intervals
    );
    
    const candlesticks = data.candlesticks || [];
    
    // Save raw response before processing
    const filename = `candlesticks_${ticker.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    const filePath = path.join(sessionDir, filename);
    fs.writeFileSync(filePath, JSON.stringify({
      request: {
        endpoint,
        ticker,
        start_ts: startTs,
        end_ts: endTs,
        period_interval: 1
      },
      response: {
        status: 200,
        data
      }
    }, null, 2));
    
    if (candlesticks.length === 0) {
      return 0;
    }
    
    // Insert candlesticks into database
    for (const c of candlesticks) {
      await pgClient.query(`
        INSERT INTO kalshi.candlesticks (
          ticker, period_ts, period_interval_min, open_interest,
          price_close, price_high, price_low, price_open, price_mean,
          volume,
          yes_ask_close, yes_ask_high, yes_ask_low, yes_ask_open,
          yes_bid_close, yes_bid_high, yes_bid_low, yes_bid_open
        ) VALUES ($1, to_timestamp($2), $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        ON CONFLICT (ticker, period_ts, period_interval_min) DO NOTHING
      `, [
        ticker,
        c.end_period_ts,
        1,  // 1-minute intervals
        c.open_interest || null,
        c.price?.close ?? null,
        c.price?.high ?? null,
        c.price?.low ?? null,
        c.price?.open ?? null,
        c.price?.mean ?? null,
        c.volume || 0,
        c.yes_ask?.close ?? null,
        c.yes_ask?.high ?? null,
        c.yes_ask?.low ?? null,
        c.yes_ask?.open ?? null,
        c.yes_bid?.close ?? null,
        c.yes_bid?.high ?? null,
        c.yes_bid?.low ?? null,
        c.yes_bid?.open ?? null
      ]);
    }
    
    return candlesticks.length;
  } catch (e: any) {
    // Save error response if available
    const filename = `candlesticks_${ticker.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    const filePath = path.join(sessionDir, filename);
    try {
      fs.writeFileSync(filePath, JSON.stringify({
        request: {
          endpoint,
          ticker,
          start_ts: startTs,
          end_ts: endTs,
          period_interval: 1
        },
        response: {
          status: e.response?.status || 500,
          error: e.message,
          data: null
        }
      }, null, 2));
    } catch (writeErr) {
      // Ignore write errors if we can't save
    }
    
    if (e.response?.status === 404) {
      return 0; // Market not found
    }
    throw e;
  }
}

async function main() {
  const args = process.argv.slice(2);
  const limit = parseInt(args.find(a => a.startsWith('--limit='))?.split('=')[1] || '0');
  const delay = parseInt(args.find(a => a.startsWith('--delay='))?.split('=')[1] || '200');
  const tickersArg = args.find(a => a.startsWith('--tickers='));
  const specificTickers = tickersArg ? tickersArg.split('=')[1].split(',').map(t => t.trim()) : undefined;
  
  console.log('=== Fetching Kalshi Candlestick Data ===\n');
  
  if (specificTickers) {
    console.log(`Fetching specific tickers: ${specificTickers.join(', ')}\n`);
  }
  
  // Create session directory for raw responses
  const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15) + 'Z';
  const sessionDir = path.join(OUTPUT_DIR, `fetch_${timestamp}`);
  fs.mkdirSync(sessionDir, { recursive: true });
  console.log(`Session directory: ${sessionDir}\n`);
  
  const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
  const privateKeyPath = path.join(rootDir, 'kalshi-api-key-private.txt');
  
  const configuration = new Configuration({
    apiKey: apiKeyId,
    privateKeyPath: privateKeyPath
  });
  const marketApi = new MarketApi(configuration);
  
  const pgClient = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse'
  });
  await pgClient.connect();
  
  try {
    console.log(specificTickers ? 'Fetching specified tickers...' : 'Fetching tickers that need candlestick data...');
    let tickers = await getTickersNeedingCandles(pgClient, specificTickers);
    
    if (limit > 0) {
      tickers = tickers.slice(0, limit);
    }
    
    console.log(`Found ${tickers.length} tickers to process\n`);
    
    let totalCandles = 0;
    let successCount = 0;
    let errorCount = 0;
    
    for (let i = 0; i < tickers.length; i++) {
      const t = tickers[i];
      process.stdout.write(`[${i + 1}/${tickers.length}] ${t.ticker}... `);
      
      try {
        const count = await fetchAndStoreCandlesticks(marketApi, pgClient, t.ticker, t.expected_expiration_time, sessionDir);
        if (count > 0) {
          console.log(`${count} candles`);
          totalCandles += count;
          successCount++;
        } else {
          console.log('no data');
        }
      } catch (e: any) {
        console.log(`ERROR: ${e.message}`);
        errorCount++;
      }
      
      // Rate limiting
      await new Promise(resolve => setTimeout(resolve, delay));
    }
    
    console.log('\n=== Summary ===');
    console.log(`Tickers processed: ${tickers.length}`);
    console.log(`Successful: ${successCount}`);
    console.log(`Errors: ${errorCount}`);
    console.log(`Total candlesticks stored: ${totalCandles}`);
    console.log(`Raw responses saved to: ${sessionDir}`);
    
  } finally {
    await pgClient.end();
  }
}

main().catch(console.error);

