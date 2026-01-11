/**
 * ESPN vs Kalshi Comparison - V2 (Optimized)
 * 
 * Uses REAL Kalshi tickers from stored markets data
 * Batch loads ESPN data for efficiency
 * Logs all API responses to files
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';
import { Client } from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

const BASE_URL = 'https://api.elections.kalshi.com/trade-api/v2';
const MARKETS_FILE = path.join(rootDir, 'data/raw/kalshi/markets/KXNBAGAME_latest.json');

// Create output directories
const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15) + 'Z';
const OUTPUT_DIR = path.join(rootDir, 'data/raw/kalshi/candlesticks', `fetch_${timestamp}`);
const REPORTS_DIR = path.join(rootDir, 'data/reports');

// Team ID to tricode mapping (reverse lookup)
const TEAM_ID_TO_TRICODE: { [key: string]: string } = {
  '1': 'ATL', '2': 'BOS', '17': 'BKN', '30': 'CHA', '4': 'CHI',
  '5': 'CLE', '6': 'DAL', '7': 'DEN', '8': 'DET', '9': 'GSW',
  '10': 'HOU', '11': 'IND', '12': 'LAC', '13': 'LAL', '29': 'MEM',
  '14': 'MIA', '15': 'MIL', '16': 'MIN', '3': 'NOP', '18': 'NYK',
  '25': 'OKC', '19': 'ORL', '20': 'PHI', '21': 'PHX', '22': 'POR',
  '23': 'SAC', '24': 'SAS', '28': 'TOR', '26': 'UTA', '27': 'WAS'
};

interface KalshiGame {
  event_ticker: string;
  ticker_home: string;
  date: Date;
  away_tricode: string;
  home_tricode: string;
  result: string;
  status: string;
  volume: number;
  espn_event_id?: string;  // Added for direct matching
}

interface ESPNGame {
  game_id: string;
  home_tricode: string;
  away_tricode: string;
  game_date: string;  // YYYY-MM-DD in Eastern time
  first_ts: Date;
  last_ts: Date;
  event_count: number;
}

// Auth helpers
function signRequest(privateKeyPem: string, timestamp: string, method: string, path: string): string {
  const message = `${timestamp}${method}${path}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(message);
  return sign.sign(privateKeyPem, 'base64');
}

async function fetchWithAuth(endpoint: string, apiKeyId: string, privateKey: string): Promise<any> {
  const ts = Date.now().toString();
  const method = 'GET';
  const urlPath = `/trade-api/v2${endpoint}`;
  const signature = signRequest(privateKey, ts, method, urlPath);
  
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'KALSHI-ACCESS-KEY': apiKeyId,
      'KALSHI-ACCESS-SIGNATURE': signature,
      'KALSHI-ACCESS-TIMESTAMP': ts,
    }
  });
  
  const data = await response.json();
  return { status: response.status, data };
}

// Parse Kalshi ticker
function parseKalshiTicker(eventTicker: string): { date: Date, dateStr: string, away: string, home: string } | null {
  const months: { [key: string]: number } = {
    JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5,
    JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11
  };
  
  const match = eventTicker.match(/KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})/);
  if (!match) return null;
  
  const year = 2000 + parseInt(match[1]);
  const month = months[match[2]];
  const day = parseInt(match[3]);
  
  return { 
    date: new Date(year, month, day), 
    dateStr: `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
    away: match[4], 
    home: match[5] 
  };
}

// Load Kalshi markets from DATABASE (all matched games)
async function loadKalshiMarkets(pgClient: Client): Promise<KalshiGame[]> {
  console.log('  Loading Kalshi markets from database...');
  
  const result = await pgClient.query(`
    SELECT DISTINCT
      km.event_ticker,
      km.ticker as ticker_home,
      km.game_date as date,
      km.result,
      km.status,
      km.volume,
      sg.event_id as espn_event_id,
      sg.home_team_abbrev as home_tricode,
      sg.away_team_abbrev as away_tricode
    FROM kalshi.markets km
    JOIN espn.scoreboard_games sg ON km.espn_event_id = sg.event_id
    WHERE km.espn_event_id IS NOT NULL
      AND sg.status_completed = true
      -- Only HOME team markets (matches ESPN's home_win_percentage)
      AND sg.home_team_display_name ILIKE '%' || km.yes_sub_title || '%'
      -- Only games with candlestick data
      AND EXISTS (SELECT 1 FROM kalshi.candlesticks kc WHERE kc.ticker = km.ticker)
    ORDER BY km.game_date DESC
  `);
  
  const games: KalshiGame[] = result.rows.map(row => ({
    event_ticker: row.event_ticker,
    ticker_home: row.ticker_home,
    date: new Date(row.date),
    away_tricode: row.away_tricode,
    home_tricode: row.home_tricode,
    result: row.result || '',
    status: row.status || 'finalized',
    volume: parseInt(row.volume) || 0,
    espn_event_id: row.espn_event_id
  }));
  
  return games;
}

// BATCH LOAD all ESPN games at once
async function loadAllESPNGames(pgClient: Client): Promise<Map<string, ESPNGame>> {
  console.log('  Loading all ESPN games from database (single query)...');
  
  const result = await pgClient.query(`
    WITH game_data AS (
      SELECT 
        ep.game_id,
        -- Extract team IDs from refs
        SUBSTRING(p.home_team_ref FROM '/teams/([0-9]+)') as home_id,
        SUBSTRING(p.away_team_ref FROM '/teams/([0-9]+)') as away_id,
        -- Convert UTC to Eastern (subtract 5 hours) for date matching
        (MIN(ep.wallclock) AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')::date as game_date_eastern,
        MIN(ep.wallclock) as first_ts,
        MAX(ep.wallclock) as last_ts,
        COUNT(DISTINCT p.sequence_number) as event_count
      FROM espn.plays ep
      INNER JOIN espn.probabilities_raw_items p 
        ON ep.game_id = p.game_id AND ep.play_id = p.event_id
      WHERE ep.wallclock IS NOT NULL
        AND p.home_win_percentage IS NOT NULL
      GROUP BY ep.game_id, p.home_team_ref, p.away_team_ref
    )
    SELECT * FROM game_data WHERE event_count > 100
  `);
  
  // Build lookup map: "AWAY@HOME_YYYY-MM-DD" -> ESPNGame
  const gameMap = new Map<string, ESPNGame>();
  
  for (const row of result.rows) {
    const homeTricode = TEAM_ID_TO_TRICODE[row.home_id] || 'UNK';
    const awayTricode = TEAM_ID_TO_TRICODE[row.away_id] || 'UNK';
    const dateStr = row.game_date_eastern.toISOString().slice(0, 10);
    
    const key = `${awayTricode}@${homeTricode}_${dateStr}`;
    
    gameMap.set(key, {
      game_id: row.game_id,
      home_tricode: homeTricode,
      away_tricode: awayTricode,
      game_date: dateStr,
      first_ts: new Date(row.first_ts),
      last_ts: new Date(row.last_ts),
      event_count: parseInt(row.event_count)
    });
  }
  
  console.log(`  Loaded ${gameMap.size} ESPN games\n`);
  return gameMap;
}

// Get ESPN probabilities for a game (still individual query, but fast)
async function getESPNProbabilities(pgClient: Client, gameId: string): Promise<Array<{
  timestamp: Date;
  home_win_pct: number;
  seq: number;
}>> {
  const result = await pgClient.query(`
    SELECT 
      ep.wallclock as timestamp,
      p.home_win_percentage,
      p.sequence_number
    FROM espn.probabilities_raw_items p
    INNER JOIN espn.plays ep 
      ON p.game_id = ep.game_id AND p.event_id = ep.play_id
    WHERE p.game_id = $1
      AND p.home_win_percentage IS NOT NULL
      AND ep.wallclock IS NOT NULL
    ORDER BY ep.wallclock
  `, [gameId]);
  
  return result.rows.map(r => ({
    timestamp: new Date(r.timestamp),
    home_win_pct: r.home_win_percentage,
    seq: r.sequence_number
  }));
}

// Load candlesticks from DATABASE (much faster than API)
async function loadCandlesticksFromDB(
  pgClient: Client,
  ticker: string,
  startTs: number,
  endTs: number
): Promise<any[]> {
  const result = await pgClient.query(`
    SELECT 
      EXTRACT(EPOCH FROM period_ts)::bigint as end_period_ts,
      yes_bid_low as "yes_bid.low",
      yes_bid_high as "yes_bid.high",
      yes_ask_low as "yes_ask.low",
      yes_ask_high as "yes_ask.high",
      volume
    FROM kalshi.candlesticks
    WHERE ticker = $1
      AND period_ts >= to_timestamp($2)
      AND period_ts <= to_timestamp($3)
      AND period_interval_min = 1
    ORDER BY period_ts
  `, [ticker, startTs, endTs]);
  
  return result.rows.map(row => ({
    end_period_ts: row.end_period_ts,
    yes_bid: { low: row['yes_bid.low'], high: row['yes_bid.high'] },
    yes_ask: { low: row['yes_ask.low'], high: row['yes_ask.high'] },
    volume: row.volume
  }));
}

// Fetch and save candlesticks (fallback to API if needed)
async function fetchCandlesticks(
  ticker: string,
  startTs: number,
  endTs: number,
  apiKeyId: string,
  privateKey: string,
  gameDir: string,
  pgClient: Client
): Promise<any[]> {
  // Try database first
  const dbCandles = await loadCandlesticksFromDB(pgClient, ticker, startTs, endTs);
  if (dbCandles.length > 0) {
    return dbCandles;
  }
  
  // Fallback to API if not in database
  const endpoint = `/series/KXNBAGAME/markets/${ticker}/candlesticks?start_ts=${startTs}&end_ts=${endTs}&period_interval=1`;
  const { status, data } = await fetchWithAuth(endpoint, apiKeyId, privateKey);
  
  // Save raw response
  const filename = `candlesticks_${ticker.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
  fs.writeFileSync(path.join(gameDir, filename), JSON.stringify({
    request: { endpoint, ticker, start_ts: startTs, end_ts: endTs, period_interval: 1 },
    response: { status, data }
  }, null, 2));
  
  return data.candlesticks || [];
}

// Compare ESPN probabilities with Kalshi candlesticks
function compareData(
  espnProbs: Array<{ timestamp: Date; home_win_pct: number; seq: number }>,
  candlesticks: any[]
): {
  matched: number;
  outside: number;
  outsidePct: number;
  avgDeviation: number;
  maxDeviation: number;
  comparisons: any[];
} {
  const candleByMinute = new Map<number, any>();
  for (const c of candlesticks) {
    if (c.volume > 0) {
      const minute = Math.floor(c.end_period_ts / 60) * 60;
      candleByMinute.set(minute, c);
    }
  }
  
  let matched = 0, outside = 0, totalDeviation = 0, maxDeviation = 0;
  const comparisons: any[] = [];
  
  for (const prob of espnProbs) {
    const minute = Math.floor(prob.timestamp.getTime() / 1000 / 60) * 60;
    const candle = candleByMinute.get(minute);
    if (!candle) continue;
    
    matched++;
    // ESPN stores as decimal (0-1), Kalshi uses cents (0-100)
    // If ESPN value < 1, it's decimal format - convert to cents
    const espnPct = prob.home_win_pct < 1 ? prob.home_win_pct * 100 : prob.home_win_pct;
    const bidLow = candle.yes_bid?.low ?? 0;
    const askHigh = candle.yes_ask?.high ?? 100;
    
    let deviation = 0, isOutside = false;
    if (espnPct < bidLow) { deviation = bidLow - espnPct; isOutside = true; }
    else if (espnPct > askHigh) { deviation = espnPct - askHigh; isOutside = true; }
    
    if (isOutside) { outside++; totalDeviation += deviation; maxDeviation = Math.max(maxDeviation, deviation); }
    
    comparisons.push({
      seq: prob.seq,
      timestamp: prob.timestamp.toISOString(),
      espn_pct: espnPct,
      kalshi_bid: `${candle.yes_bid?.low}-${candle.yes_bid?.high}`,
      kalshi_ask: `${candle.yes_ask?.low}-${candle.yes_ask?.high}`,
      within: !isOutside,
      deviation
    });
  }
  
  return {
    matched, outside,
    outsidePct: matched > 0 ? (outside / matched) * 100 : 0,
    avgDeviation: outside > 0 ? totalDeviation / outside : 0,
    maxDeviation,
    comparisons
  };
}

async function main() {
  const args = process.argv.slice(2);
  const limit = parseInt(args.find(a => a.startsWith('--limit='))?.split('=')[1] || '100');
  
  console.log('=== ESPN vs Kalshi Comparison V2 (Optimized) ===');
  console.log(`Using Kalshi tickers from: ${MARKETS_FILE}`);
  console.log(`Output: ${OUTPUT_DIR}`);
  console.log(`Limit: ${limit} games\n`);
  
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  
  const apiKeyId = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-public.txt'), 'utf-8').trim();
  const privateKey = fs.readFileSync(path.join(rootDir, 'kalshi-api-key-private.txt'), 'utf-8');
  
  const pgClient = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse'
  });
  await pgClient.connect();
  
  // BATCH LOAD ESPN data first
  console.log('Step 1: Loading ESPN data...');
  const espnGames = await loadAllESPNGames(pgClient);
  
  // Load Kalshi markets from DATABASE
  console.log('Step 2: Loading Kalshi markets from database...');
  const allKalshiGames = await loadKalshiMarkets(pgClient);
  console.log(`  Loaded ${allKalshiGames.length} Kalshi games from database\n`);
  
  // Match using espn_event_id directly (already matched in database)
  console.log('Step 3: Matching Kalshi to ESPN...');
  const matched: Array<{ kalshi: KalshiGame; espn: ESPNGame }> = [];
  
  for (const kalshi of allKalshiGames) {
    if (kalshi.status !== 'finalized') continue;
    
    // Use espn_event_id if available, otherwise fall back to key matching
    let espn: ESPNGame | undefined;
    
    if (kalshi.espn_event_id) {
      // Find ESPN game by event_id
      for (const [key, game] of espnGames.entries()) {
        if (game.game_id === kalshi.espn_event_id) {
          espn = game;
          break;
        }
      }
    }
    
    // Fallback to key matching if espn_event_id didn't work
    if (!espn) {
      const parsed = parseKalshiTicker(kalshi.event_ticker);
      if (!parsed) continue;
      const dateStr = `${parsed.date.getFullYear()}-${String(parsed.date.getMonth() + 1).padStart(2, '0')}-${String(parsed.date.getDate()).padStart(2, '0')}`;
      const key = `${kalshi.away_tricode}@${kalshi.home_tricode}_${dateStr}`;
      espn = espnGames.get(key);
    }
    
    if (espn) {
      matched.push({ kalshi, espn });
    }
  }
  
  console.log(`  Matched ${matched.length} games\n`);
  
  // Sort by date (most recent first)
  matched.sort((a, b) => b.kalshi.date.getTime() - a.kalshi.date.getTime());
  // Process all matched games (or limit if specified)
  const toProcess = limit > 0 ? matched.slice(0, limit) : matched;
  
  console.log(`Step 4: Processing ${toProcess.length} games (limit=${limit > 0 ? limit : 'ALL'})...\n`);
  
  const results: any[] = [];
  
  for (let i = 0; i < toProcess.length; i++) {
    const { kalshi, espn } = toProcess[i];
    const label = `[${i + 1}/${toProcess.length}] ${kalshi.away_tricode}@${kalshi.home_tricode}`;
    
    process.stdout.write(`${label}...`);
    
    // Create game directory
    const gameDir = path.join(OUTPUT_DIR, `${kalshi.event_ticker}_${espn.game_id}`);
    fs.mkdirSync(gameDir, { recursive: true });
    
    // Get ESPN probabilities
    const espnProbs = await getESPNProbabilities(pgClient, espn.game_id);
    
    // Save ESPN data
    fs.writeFileSync(path.join(gameDir, 'espn_probabilities.json'), JSON.stringify({
      game_id: espn.game_id, home: espn.home_tricode, away: espn.away_tricode,
      first_ts: espn.first_ts.toISOString(), last_ts: espn.last_ts.toISOString(),
      probabilities: espnProbs.map(p => ({ ...p, timestamp: p.timestamp.toISOString() }))
    }, null, 2));
    
    // Fetch candlesticks (from database, fallback to API)
    const startTs = Math.floor(espn.first_ts.getTime() / 1000) - 3600;
    const endTs = Math.floor(espn.last_ts.getTime() / 1000) + 3600;
    const candlesticks = await fetchCandlesticks(kalshi.ticker_home, startTs, endTs, apiKeyId, privateKey, gameDir, pgClient);
    
    // Compare
    const comparison = compareData(espnProbs, candlesticks);
    
    console.log(` ESPN:${espnProbs.length} Kalshi:${candlesticks.length} Outside:${comparison.outsidePct.toFixed(0)}%`);
    
    // Save comparison
    const result = {
      kalshi: { ticker: kalshi.ticker_home, date: kalshi.date.toISOString(), result: kalshi.result, volume: kalshi.volume },
      espn: { game_id: espn.game_id, events: espnProbs.length },
      comparison: { matched: comparison.matched, outside: comparison.outside, outside_pct: comparison.outsidePct, avg_dev: comparison.avgDeviation, max_dev: comparison.maxDeviation },
      sample_comparisons: comparison.comparisons
    };
    
    fs.writeFileSync(path.join(gameDir, 'comparison.json'), JSON.stringify(result, null, 2));
    results.push(result);
    
    // Rate limit for API
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  
  await pgClient.end();
  
  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('SUMMARY');
  console.log('='.repeat(60));
  console.log(`Kalshi games available: ${allKalshiGames.length}`);
  console.log(`Matched to ESPN: ${matched.length}`);
  console.log(`Processed: ${results.length}`);
  
  if (results.length > 0) {
    const totalMatched = results.reduce((s, r) => s + r.comparison.matched, 0);
    const totalOutside = results.reduce((s, r) => s + r.comparison.outside, 0);
    const overallPct = totalMatched > 0 ? (totalOutside / totalMatched) * 100 : 0;
    
    console.log(`\nTotal events compared: ${totalMatched}`);
    console.log(`Outside Kalshi range: ${totalOutside} (${overallPct.toFixed(1)}%)`);
  }
  
  // Save combined results
  const combinedFile = path.join(REPORTS_DIR, 'espn_kalshi_comparison_v2.json');
  fs.writeFileSync(combinedFile, JSON.stringify({
    generated: new Date().toISOString(),
    kalshi_source: MARKETS_FILE,
    total_kalshi_games: allKalshiGames.length,
    matched_to_espn: matched.length,
    processed: results.length,
    results
  }, null, 2));
  console.log(`\nSaved: ${combinedFile}`);
  console.log(`Raw data: ${OUTPUT_DIR}`);
}

main().catch(console.error);
