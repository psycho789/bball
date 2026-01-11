/**
 * Compare ESPN win probabilities with Kalshi prediction market candlestick data.
 * 
 * Strategy: For each ESPN game, fetch the full day's Kalshi candlesticks 
 * and compare ESPN probabilities with the Kalshi bid-ask ranges during 
 * the heavy trading period (when volume is high).
 */

import { MarketApi, Configuration } from 'kalshi-typescript';
import { Client } from 'pg';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');

// ESPN team ID to tricode mapping
const ESPN_TEAM_MAP: Record<string, string> = {
  '1': 'ATL', '2': 'BOS', '3': 'BKN', '4': 'CHA', '5': 'CHI',
  '6': 'CLE', '7': 'DAL', '8': 'DEN', '9': 'DET', '10': 'GSW',
  '11': 'HOU', '12': 'IND', '13': 'LAC', '14': 'MIA', '15': 'MIL',
  '16': 'MIN', '17': 'NOP', '18': 'NYK', '19': 'OKC', '20': 'PHI',
  '21': 'PHX', '22': 'POR', '23': 'SAC', '24': 'SAS', '25': 'ORL',
  '26': 'UTA', '27': 'WAS', '28': 'TOR', '29': 'MEM', '30': 'LAL'
};

function espnTeamIdToTricode(espnTeamId: string): string {
  return ESPN_TEAM_MAP[espnTeamId] || 'UNK';
}

function extractTeamIdFromRef(ref: string): string | null {
  const match = ref.match(/\/teams\/(\d+)/);
  return match ? match[1] : null;
}

function formatDateForKalshi(date: Date): string {
  // Convert UTC to US Eastern (subtract 5 hours for EST)
  const eastDate = new Date(date.getTime() - 5 * 60 * 60 * 1000);
  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 
                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const yy = eastDate.getFullYear().toString().slice(-2);
  const mmm = months[eastDate.getMonth()];
  const dd = eastDate.getDate().toString().padStart(2, '0');
  return `${yy}${mmm}${dd}`;
}

function buildKalshiTicker(homeTricode: string, awayTricode: string, gameDate: Date): string {
  const dateStr = formatDateForKalshi(gameDate);
  return `KXNBAGAME-${dateStr}${awayTricode}${homeTricode}`;
}

interface ESPNGame {
  game_id: string;
  home_team_id: string;
  away_team_id: string;
  first_ts: Date;
  last_ts: Date;
  home_tricode: string;
  away_tricode: string;
}

interface ESPNProbability {
  timestamp: Date;           // wallclock (precise) OR last_modified_utc (fallback)
  home_win_percentage: number;
  sequence_number: number;
  has_precise_timestamp: boolean;  // true if from wallclock, false if proportional
}

interface Candlestick {
  endTs: number;
  yesBidLow: number;
  yesBidHigh: number;
  yesAskLow: number;
  yesAskHigh: number;
  yesBidClose: number;
  yesAskClose: number;
  volume: number;
}

interface ComparisonResult {
  game_id: string;
  home_team: string;
  away_team: string;
  kalshi_ticker: string;
  kalshi_result: string;
  total_espn_events: number;
  candlesticks_found: number;
  trading_candles: number;  // candles with volume > 0
  matched_events: number;
  outside_bid_ask_count: number;
  outside_bid_ask_pct: number;
  avg_deviation: number;
  max_deviation: number;
  timestamp_mode: 'precise' | 'proportional';  // How timestamps were matched
  sample_comparisons: Array<{
    espn_seq: number;
    espn_prob: number;
    espn_timestamp: string;  // ISO timestamp
    kalshi_bid_range: string;
    kalshi_ask_range: string;
    within_range: boolean;
    deviation: number;
  }>;
}

async function getESPNGames(pgClient: Client, seasonLabel: string = '2025-26', limit: number = 500): Promise<ESPNGame[]> {
  // Query games that have BOTH plays (wallclock) and probabilities data
  // This ensures we can do precise timestamp matching
  const result = await pgClient.query(`
    SELECT 
      p.game_id,
      p.home_team_ref,
      p.away_team_ref,
      MIN(ep.wallclock) as first_ts,
      MAX(ep.wallclock) as last_ts,
      COUNT(DISTINCT p.sequence_number) as num_events
      FROM espn.probabilities_raw_items p
      INNER JOIN espn.plays ep
      ON p.game_id = ep.game_id 
      AND p.event_id = ep.play_id
    WHERE ep.season_label = $1
      AND ep.wallclock IS NOT NULL
    GROUP BY p.game_id, p.home_team_ref, p.away_team_ref
    HAVING COUNT(DISTINCT p.sequence_number) > 100
    ORDER BY MIN(ep.wallclock) DESC
    LIMIT $2
  `, [seasonLabel, limit]);
  
  return result.rows.map(row => {
    const homeTeamId = extractTeamIdFromRef(row.home_team_ref);
    const awayTeamId = extractTeamIdFromRef(row.away_team_ref);
    return {
      game_id: row.game_id,
      home_team_id: homeTeamId || 'UNK',
      away_team_id: awayTeamId || 'UNK',
      first_ts: new Date(row.first_ts),
      last_ts: new Date(row.last_ts),
      home_tricode: homeTeamId ? espnTeamIdToTricode(homeTeamId) : 'UNK',
      away_tricode: awayTeamId ? espnTeamIdToTricode(awayTeamId) : 'UNK'
    };
  });
}

async function getESPNProbabilities(pgClient: Client, gameId: string): Promise<ESPNProbability[]> {
  // First try to get precise wallclock timestamps from espn_plays
  const wallclockResult = await pgClient.query(`
    SELECT 
      p.sequence_number,
      p.home_win_percentage,
      ep.wallclock as timestamp
      FROM espn.probabilities_raw_items p
      INNER JOIN espn.plays ep
      ON p.game_id = ep.game_id 
      AND p.event_id = ep.play_id
    WHERE p.game_id = $1
      AND p.home_win_percentage IS NOT NULL
      AND ep.wallclock IS NOT NULL
    ORDER BY ep.wallclock, p.sequence_number
  `, [gameId]);
  
  // If we have wallclock data, use it (precise timestamps)
  if (wallclockResult.rows.length > 0) {
    return wallclockResult.rows.map(row => ({
      timestamp: new Date(row.timestamp),
      home_win_percentage: row.home_win_percentage,
      sequence_number: row.sequence_number,
      has_precise_timestamp: true
    }));
  }
  
  // Fallback: use last_modified_utc (less precise, minute-level)
  const fallbackResult = await pgClient.query(`
    SELECT 
      sequence_number,
      home_win_percentage,
      last_modified_utc as timestamp
    FROM espn.probabilities_raw_items
    WHERE game_id = $1
      AND home_win_percentage IS NOT NULL
      AND last_modified_utc IS NOT NULL
    ORDER BY sequence_number
  `, [gameId]);
  
  return fallbackResult.rows.map(row => ({
    timestamp: new Date(row.timestamp),
    home_win_percentage: row.home_win_percentage,
    sequence_number: row.sequence_number,
    has_precise_timestamp: false
  }));
}

async function findKalshiMarket(marketApi: MarketApi, tickerBase: string, homeTricode: string): Promise<{ticker: string, result: string} | null> {
  const homeTickerFull = `${tickerBase}-${homeTricode}`;
  try {
    const { data } = await marketApi.getMarket(homeTickerFull);
    if (data.market) {
      return { ticker: homeTickerFull, result: data.market.result || 'pending' };
    }
  } catch (e) {}
  return null;
}

async function getKalshiCandlesticks(marketApi: MarketApi, ticker: string, gameDate: Date): Promise<Candlestick[]> {
  // Get candlesticks for 2 days around the game date
  const dayStart = new Date(gameDate);
  dayStart.setUTCHours(0, 0, 0, 0);
  dayStart.setDate(dayStart.getDate() - 1);
  
  const dayEnd = new Date(gameDate);
  dayEnd.setUTCHours(23, 59, 59, 999);
  dayEnd.setDate(dayEnd.getDate() + 1);
  
  const startTs = Math.floor(dayStart.getTime() / 1000);
  const endTs = Math.floor(dayEnd.getTime() / 1000);
  
  try {
    const { data } = await marketApi.getMarketCandlesticks(
      'KXNBAGAME', ticker, startTs, endTs, 1  // 1 minute intervals for accurate spreads
    );
    
    return (data.candlesticks || []).map((c: any) => ({
      endTs: c.end_period_ts,
      yesBidLow: c.yes_bid?.low ?? 0,
      yesBidHigh: c.yes_bid?.high ?? 0,
      yesAskLow: c.yes_ask?.low ?? 100,
      yesAskHigh: c.yes_ask?.high ?? 100,
      yesBidClose: c.yes_bid?.close ?? 0,
      yesAskClose: c.yes_ask?.close ?? 100,
      volume: c.volume || 0
    }));
  } catch (e) {
    return [];
  }
}

function findTradingPeriod(candlesticks: Candlestick[]): { start: number, end: number } | null {
  // Find the period with trading volume (game time)
  // With 1-min candles, lower threshold for "active" trading
  const tradingCandles = candlesticks.filter(c => c.volume > 10);
  if (tradingCandles.length === 0) {
    // Fall back to any volume
    const anyTrading = candlesticks.filter(c => c.volume > 0);
    if (anyTrading.length === 0) return null;
    return { 
      start: anyTrading[0].endTs - 60,  // 1 minute candles
      end: anyTrading[anyTrading.length - 1].endTs 
    };
  }
  return { 
    start: tradingCandles[0].endTs - 60,  // 1 minute candles
    end: tradingCandles[tradingCandles.length - 1].endTs 
  };
}

async function compareGameData(
  game: ESPNGame,
  espnProbs: ESPNProbability[],
  marketApi: MarketApi
): Promise<ComparisonResult | null> {
  const kalshiTickerBase = buildKalshiTicker(game.home_tricode, game.away_tricode, game.first_ts);
  
  const marketInfo = await findKalshiMarket(marketApi, kalshiTickerBase, game.home_tricode);
  if (!marketInfo) {
    console.log(`  Market not found: ${kalshiTickerBase}-${game.home_tricode}`);
    return null;
  }
  
  const kalshiTicker = marketInfo.ticker;
  console.log(`  Found: ${kalshiTicker} (${marketInfo.result})`);
  
  const candlesticks = await getKalshiCandlesticks(marketApi, kalshiTicker, game.first_ts);
  const tradingCandles = candlesticks.filter(c => c.volume > 0);
  
  console.log(`  Candlesticks: ${candlesticks.length} total, ${tradingCandles.length} with volume`);
  
  if (tradingCandles.length === 0) {
    const hasPrecise = espnProbs.length > 0 && espnProbs[0].has_precise_timestamp;
    return {
      game_id: game.game_id,
      home_team: game.home_tricode,
      away_team: game.away_tricode,
      kalshi_ticker: kalshiTicker,
      kalshi_result: marketInfo.result,
      total_espn_events: espnProbs.length,
      candlesticks_found: candlesticks.length,
      trading_candles: 0,
      matched_events: 0,
      outside_bid_ask_count: 0,
      outside_bid_ask_pct: 0,
      avg_deviation: 0,
      max_deviation: 0,
      timestamp_mode: hasPrecise ? 'precise' : 'proportional',
      sample_comparisons: []
    };
  }
  
  // Find trading period (game time based on Kalshi volume)
  const tradingPeriod = findTradingPeriod(candlesticks);
  
  // Determine timestamp matching mode
  const hasPreciseTimestamps = espnProbs.length > 0 && espnProbs[0].has_precise_timestamp;
  const timestampMode: 'precise' | 'proportional' = hasPreciseTimestamps ? 'precise' : 'proportional';
  
  console.log(`  Timestamp mode: ${timestampMode}`);
  
  let outsideCount = 0;
  let totalDeviation = 0;
  let maxDeviation = 0;
  let matchedCount = 0;
  const sampleComparisons: ComparisonResult['sample_comparisons'] = [];
  const numTradingCandles = tradingCandles.length;
  
  for (let i = 0; i < espnProbs.length; i++) {
    const prob = espnProbs[i];
    const espnProbCents = prob.home_win_percentage * 100;
    
    let candle: Candlestick | undefined;
    
    if (hasPreciseTimestamps) {
      // PRECISE MODE: Direct timestamp matching
      const probTs = Math.floor(prob.timestamp.getTime() / 1000);
      candle = tradingCandles.find(c => {
        const candleStart = c.endTs - 60;  // 1 minute before end (1-min candles)
        return probTs >= candleStart && probTs <= c.endTs;
      });
    } else {
      // PROPORTIONAL MODE: Map sequence to candlestick proportionally
      const candleIdx = Math.min(
        Math.floor((i / espnProbs.length) * numTradingCandles),
        numTradingCandles - 1
      );
      candle = tradingCandles[candleIdx];
    }
    
    if (!candle) continue;
    matchedCount++;
    
    // Check if ESPN prob is outside the full bid-ask range during this candle
    // Use bid LOW and ask HIGH to get the widest possible range
    const bidRange = [candle.yesBidLow, candle.yesBidHigh];
    const askRange = [candle.yesAskLow, candle.yesAskHigh];
    
    // The tradeable range during the candle is [bid_low, ask_high]
    const rangeMin = candle.yesBidLow;
    const rangeMax = candle.yesAskHigh;
    
    const isOutside = espnProbCents < rangeMin || espnProbCents > rangeMax;
    const deviation = isOutside 
      ? Math.min(Math.abs(espnProbCents - rangeMin), Math.abs(espnProbCents - rangeMax))
      : 0;
    
    if (isOutside) outsideCount++;
    totalDeviation += deviation;
    maxDeviation = Math.max(maxDeviation, deviation);
    
    // Save ALL comparisons for accurate charting
    sampleComparisons.push({
      espn_seq: prob.sequence_number,
      espn_prob: Math.round(espnProbCents * 10) / 10,
      espn_timestamp: prob.timestamp.toISOString(),
      kalshi_bid_range: `${bidRange[0]}-${bidRange[1]}`,
      kalshi_ask_range: `${askRange[0]}-${askRange[1]}`,
      within_range: !isOutside,
      deviation: Math.round(deviation * 10) / 10
    });
  }
  
  return {
    game_id: game.game_id,
    home_team: game.home_tricode,
    away_team: game.away_tricode,
    kalshi_ticker: kalshiTicker,
    kalshi_result: marketInfo.result,
    total_espn_events: espnProbs.length,
    candlesticks_found: candlesticks.length,
    trading_candles: tradingCandles.length,
    matched_events: matchedCount,
    outside_bid_ask_count: outsideCount,
    outside_bid_ask_pct: matchedCount > 0 ? (outsideCount / matchedCount) * 100 : 0,
    avg_deviation: matchedCount > 0 ? totalDeviation / matchedCount : 0,
    max_deviation: maxDeviation,
    timestamp_mode: timestampMode,
    sample_comparisons: sampleComparisons
  };
}

async function main() {
  // Parse command line args
  const args = process.argv.slice(2);
  const seasonLabel = args.find(a => a.startsWith('--season='))?.split('=')[1] || '2025-26';
  const limit = parseInt(args.find(a => a.startsWith('--limit='))?.split('=')[1] || '500');
  
  console.log('=== ESPN vs Kalshi Win Probability Comparison ===');
  console.log(`Season: ${seasonLabel} | Max games: ${limit}\n`);
  
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
    console.log('Fetching ESPN games with plays data...');
    const games = await getESPNGames(pgClient, seasonLabel, limit);
    console.log(`Found ${games.length} games with wallclock data\n`);
    
    const results: ComparisonResult[] = [];
    
    for (const game of games) {
      console.log(`\n${game.away_tricode} @ ${game.home_tricode} (ESPN ${game.game_id})`);
      
      const espnProbs = await getESPNProbabilities(pgClient, game.game_id);
      console.log(`  ESPN events: ${espnProbs.length}`);
      
      const result = await compareGameData(game, espnProbs, marketApi);
      if (result) {
        results.push(result);
      }
      
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    // Summary
    console.log('\n\n' + '='.repeat(100));
    console.log('SUMMARY - ESPN Win Probability vs Kalshi Prediction Market Bid-Ask Range');
    console.log('='.repeat(100) + '\n');
    
    console.log('Game                  | Result | ESPN  | Candles | Matched | Outside %  | Avg Dev | Max Dev');
    console.log('-'.repeat(100));
    
    for (const r of results) {
      const gameStr = `${r.away_team}@${r.home_team}`.padEnd(22);
      const resultStr = (r.kalshi_result === 'yes' ? 'HOME' : r.kalshi_result === 'no' ? 'AWAY' : r.kalshi_result).padEnd(6);
      console.log(
        `${gameStr}| ${resultStr} | ${String(r.total_espn_events).padStart(5)} | ${String(r.trading_candles).padStart(7)} | ${String(r.matched_events).padStart(7)} | ${r.outside_bid_ask_pct.toFixed(1).padStart(9)}% | ${r.avg_deviation.toFixed(2).padStart(7)} | ${r.max_deviation.toFixed(1).padStart(7)}`
      );
    }
    
    // Overall stats
    const gamesWithData = results.filter(r => r.matched_events > 0);
    const totalMatched = gamesWithData.reduce((sum, r) => sum + r.matched_events, 0);
    const totalOutside = gamesWithData.reduce((sum, r) => sum + r.outside_bid_ask_count, 0);
    const overallOutsidePct = totalMatched > 0 ? (totalOutside / totalMatched) * 100 : 0;
    const avgDev = gamesWithData.length > 0 
      ? gamesWithData.reduce((sum, r) => sum + r.avg_deviation, 0) / gamesWithData.length 
      : 0;
    
    console.log('-'.repeat(100));
    console.log(`TOTALS                |        | ${String(totalMatched).padStart(5)} |         |         | ${overallOutsidePct.toFixed(1).padStart(9)}% | ${avgDev.toFixed(2).padStart(7)} |`);
    
    // Sample comparisons
    const gamesWithOutside = results.filter(r => r.outside_bid_ask_count > 0);
    if (gamesWithOutside.length > 0) {
      console.log('\n\n' + '='.repeat(100));
      console.log('SAMPLE COMPARISONS - Events Where ESPN Prob Falls Outside Kalshi Bid-Ask Range');
      console.log('='.repeat(100));
      
      for (const r of gamesWithOutside.slice(0, 3)) {
        console.log(`\n--- ${r.away_team} @ ${r.home_team} (${r.outside_bid_ask_count}/${r.matched_events} outside = ${r.outside_bid_ask_pct.toFixed(1)}%) [${r.timestamp_mode}] ---`);
        console.log('Seq # | Timestamp (UTC)       | ESPN%  | Kalshi Bid | Kalshi Ask | Within? | Dev');
        console.log('-'.repeat(95));
        for (const s of r.sample_comparisons.slice(0, 15)) {
          const timestampStr = s.espn_timestamp.replace('T', ' ').slice(0, 19);
          console.log(
            `${String(s.espn_seq).padStart(5)} | ${timestampStr} | ${String(s.espn_prob).padStart(5)}% | ${s.kalshi_bid_range.padEnd(10)} | ${s.kalshi_ask_range.padEnd(10)} | ${s.within_range ? 'YES' : 'NO '.padEnd(7)} | ${String(s.deviation).padStart(4)}`
          );
        }
      }
    }
    
    console.log('\n\n' + '='.repeat(100));
    console.log('INTERPRETATION');
    console.log('='.repeat(100));
    console.log(`
METHODOLOGY:
• ESPN play timestamps (wallclock) are matched to Kalshi 1-minute candlesticks
• Each ESPN probability is compared to the Kalshi bid-ask range at that exact minute
• Uses precise second-level timestamps from ESPN's espn_plays table

METRICS:
• "Outside %" = % of ESPN probability updates that fell outside Kalshi's bid-ask spread
• Lower "Outside %" = ESPN and Kalshi are more aligned
• Higher "Outside %" = ESPN probabilities differ from market consensus
• "Avg Dev" = Average deviation in cents when outside the range
• "Max Dev" = Largest deviation observed

RESULTS:
Games analyzed: ${gamesWithData.length}
Total probability events: ${totalMatched}
Overall outside rate: ${overallOutsidePct.toFixed(1)}%
Average deviation when outside: ${avgDev.toFixed(2)}¢
`);
    
    // Save
    const outputPath = path.join(rootDir, 'data/reports/espn_kalshi_comparison.json');
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
    console.log(`Results saved to: ${outputPath}`);
    
  } finally {
    await pgClient.end();
  }
}

main().catch(console.error);
