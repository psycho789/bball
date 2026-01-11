/**
 * Generate comprehensive statistics report comparing ESPN and Kalshi data
 * 
 * For each game, calculates:
 * - Outside range (count and percentage)
 * - Average deviation (all matched points)
 * - Max deviation
 * - Median deviation
 * - 95th percentile deviation
 * 
 * Includes full game metadata: home, away, winner, date, scores, etc.
 * 
 * Design Pattern: Batch processing with statistical aggregation
 * Algorithm: Time-series alignment with percentile calculation
 * Big O: O(n*m) where n = games, m = matched points per game
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { Client } from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

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

interface GameMetadata {
  espn_event_id: string;
  kalshi_ticker: string;
  kalshi_event_ticker: string;
  game_date: Date;
  home_tricode: string;
  away_tricode: string;
  home_score: number | null;
  away_score: number | null;
  home_winner: boolean | null;
  away_winner: boolean | null;
  status_completed: boolean;
  venue_name: string | null;
  venue_city: string | null;
  season_year: number | null;
  season_type: number | null;
  kalshi_result: string | null;
  kalshi_volume: number | null;
}

interface ComparisonStats {
  matched: number;
  outside: number;
  outsidePct: number;
  avgDeviation: number;
  maxDeviation: number;
  medianDeviation: number;
  percentile95Deviation: number;
  allDeviations: number[];
}

// Load all matched games for 2025-26 season
async function loadMatchedGames(pgClient: Client): Promise<GameMetadata[]> {
  console.log('Loading matched games from database...');
  
  const result = await pgClient.query(`
    SELECT DISTINCT
      sg.event_id as espn_event_id,
      km.ticker as kalshi_ticker,
      km.event_ticker as kalshi_event_ticker,
      km.game_date,
      sg.home_team_abbrev as home_tricode,
      sg.away_team_abbrev as away_tricode,
      sg.home_score,
      sg.away_score,
      sg.home_winner,
      sg.away_winner,
      sg.status_completed,
      sg.venue_name,
      sg.venue_city,
      sg.season_year,
      sg.season_type,
      km.result as kalshi_result,
      km.volume as kalshi_volume
    FROM kalshi.markets km
    JOIN espn.scoreboard_games sg ON km.espn_event_id = sg.event_id
    WHERE km.espn_event_id IS NOT NULL
      AND sg.status_completed = true
      AND sg.season_year = 2025
      -- Only HOME team markets (matches ESPN's home_win_percentage)
      AND sg.home_team_display_name ILIKE '%' || km.yes_sub_title || '%'
      -- Only games with candlestick data
      AND EXISTS (SELECT 1 FROM kalshi.candlesticks kc WHERE kc.ticker = km.ticker)
    ORDER BY km.game_date DESC, sg.event_id
  `);
  
  const games: GameMetadata[] = result.rows.map(row => ({
    espn_event_id: row.espn_event_id,
    kalshi_ticker: row.kalshi_ticker,
    kalshi_event_ticker: row.kalshi_event_ticker,
    game_date: new Date(row.game_date),
    home_tricode: row.home_tricode || 'UNK',
    away_tricode: row.away_tricode || 'UNK',
    home_score: row.home_score,
    away_score: row.away_score,
    home_winner: row.home_winner,
    away_winner: row.away_winner,
    status_completed: row.status_completed,
    venue_name: row.venue_name,
    venue_city: row.venue_city,
    season_year: row.season_year,
    season_type: row.season_type,
    kalshi_result: row.kalshi_result,
    kalshi_volume: row.kalshi_volume ? parseInt(row.kalshi_volume) : null
  }));
  
  console.log(`  Loaded ${games.length} matched games\n`);
  return games;
}

// Get ESPN probabilities for a game
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

// Load candlesticks from database
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

// Calculate percentile from sorted array
function calculatePercentile(sortedArray: number[], p: number): number {
  if (sortedArray.length === 0) return 0;
  const index = Math.ceil((p / 100) * sortedArray.length) - 1;
  return sortedArray[Math.max(0, Math.min(index, sortedArray.length - 1))];
}

// Compare ESPN probabilities with Kalshi candlesticks and calculate all statistics
function compareData(
  espnProbs: Array<{ timestamp: Date; home_win_pct: number; seq: number }>,
  candlesticks: any[]
): ComparisonStats {
  const candleByMinute = new Map<number, any>();
  for (const c of candlesticks) {
    if (c.volume > 0) {
      const minute = Math.floor(c.end_period_ts / 60) * 60;
      candleByMinute.set(minute, c);
    }
  }
  
  let matched = 0, outside = 0;
  const allDeviations: number[] = [];
  
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
    
    // Calculate deviation: distance to nearest bound (0 if within range)
    let deviation = 0;
    let isOutside = false;
    
    if (espnPct < bidLow) {
      deviation = bidLow - espnPct;
      isOutside = true;
    } else if (espnPct > askHigh) {
      deviation = espnPct - askHigh;
      isOutside = true;
    }
    // If within range, deviation is 0
    
    if (isOutside) {
      outside++;
    }
    
    allDeviations.push(deviation);
  }
  
  // Sort deviations for percentile calculation
  const sortedDeviations = [...allDeviations].sort((a, b) => a - b);
  
  const avgDeviation = allDeviations.length > 0
    ? allDeviations.reduce((sum, d) => sum + d, 0) / allDeviations.length
    : 0;
  
  const maxDeviation = sortedDeviations.length > 0
    ? sortedDeviations[sortedDeviations.length - 1]
    : 0;
  
  const medianDeviation = calculatePercentile(sortedDeviations, 50);
  const percentile95Deviation = calculatePercentile(sortedDeviations, 95);
  
  return {
    matched,
    outside,
    outsidePct: matched > 0 ? (outside / matched) * 100 : 0,
    avgDeviation,
    maxDeviation,
    medianDeviation,
    percentile95Deviation,
    allDeviations
  };
}

// Format game metadata for display
function formatGameMetadata(game: GameMetadata, stats: ComparisonStats): string {
  const dateStr = game.game_date.toISOString().split('T')[0];
  const winner = game.home_winner 
    ? game.home_tricode 
    : game.away_winner 
      ? game.away_tricode 
      : 'TBD';
  
  const scoreStr = (game.home_score !== null && game.away_score !== null)
    ? `${game.away_tricode} ${game.away_score}, ${game.home_tricode} ${game.home_score}`
    : 'Score not available';
  
  const venueStr = game.venue_city && game.venue_name
    ? `${game.venue_name}, ${game.venue_city}`
    : game.venue_name || game.venue_city || 'Venue not available';
  
  const seasonTypeStr = game.season_type === 1 ? 'Preseason'
    : game.season_type === 2 ? 'Regular Season'
    : game.season_type === 3 ? 'Postseason'
    : 'Unknown';
  
  return `## ${game.away_tricode} @ ${game.home_tricode}

- **Date**: ${dateStr}
- **ESPN Game ID**: ${game.espn_event_id}
- **Kalshi Event Ticker**: ${game.kalshi_event_ticker}
- **Kalshi Market Ticker**: ${game.kalshi_ticker}
- **Winner**: ${winner}
- **Final Score**: ${scoreStr}
- **Venue**: ${venueStr}
- **Season**: ${game.season_year || 'N/A'} ${seasonTypeStr}
- **Kalshi Result**: ${game.kalshi_result || 'N/A'}
- **Kalshi Volume**: ${game.kalshi_volume?.toLocaleString() || 'N/A'}

**Statistics:**

- **Total Matched**: ${stats.matched}
- **Outside Range**: ${stats.outside} (${stats.outsidePct.toFixed(2)}%)
- **Average Deviation**: ${stats.avgDeviation.toFixed(2)} cents
- **Max Deviation**: ${stats.maxDeviation.toFixed(2)} cents
- **Median Deviation**: ${stats.medianDeviation.toFixed(2)} cents
- **95th Percentile Deviation**: ${stats.percentile95Deviation.toFixed(2)} cents

---`;
}

async function main() {
  console.log('=== ESPN vs Kalshi Statistics Report Generator ===\n');
  
  const pgClient = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse'
  });
  await pgClient.connect();
  
  try {
    // Load all matched games
    const games = await loadMatchedGames(pgClient);
    
    if (games.length === 0) {
      console.log('No matched games found. Exiting.');
      return;
    }
    
    console.log(`Processing ${games.length} games...\n`);
    
    const reportSections: string[] = [];
    const summary: Array<{ game: GameMetadata; stats: ComparisonStats }> = [];
    
    // Process each game
    for (let i = 0; i < games.length; i++) {
      const game = games[i];
      const label = `[${i + 1}/${games.length}] ${game.away_tricode}@${game.home_tricode}`;
      
      process.stdout.write(`${label}...`);
      
      try {
        // Get ESPN probabilities
        const espnProbs = await getESPNProbabilities(pgClient, game.espn_event_id);
        
        if (espnProbs.length === 0) {
          console.log(' No ESPN data');
          continue;
        }
        
        // Get time range
        const firstTs = Math.min(...espnProbs.map(p => p.timestamp.getTime()));
        const lastTs = Math.max(...espnProbs.map(p => p.timestamp.getTime()));
        const startTs = Math.floor(firstTs / 1000) - 3600;
        const endTs = Math.floor(lastTs / 1000) + 3600;
        
        // Load candlesticks
        const candlesticks = await loadCandlesticksFromDB(
          pgClient,
          game.kalshi_ticker,
          startTs,
          endTs
        );
        
        if (candlesticks.length === 0) {
          console.log(' No Kalshi data');
          continue;
        }
        
        // Compare and calculate statistics
        const stats = compareData(espnProbs, candlesticks);
        
        if (stats.matched === 0) {
          console.log(' No matched points');
          continue;
        }
        
        console.log(` Matched:${stats.matched} Outside:${stats.outsidePct.toFixed(1)}%`);
        
        // Generate report section
        const section = formatGameMetadata(game, stats);
        reportSections.push(section);
        summary.push({ game, stats });
        
      } catch (error) {
        console.log(` Error: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    
    // Generate full report
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const report = `# ESPN vs Kalshi Comparison - Comprehensive Statistics Report

**Generated**: ${timestamp}

**Total Games**: ${summary.length}

---

${reportSections.join('\n\n')}

---

## Summary Statistics

**Overall Metrics:**

- **Total Games Analyzed**: ${summary.length}
- **Total Matched Points**: ${summary.reduce((sum, s) => sum + s.stats.matched, 0).toLocaleString()}
- **Total Outside Range**: ${summary.reduce((sum, s) => sum + s.stats.outside, 0).toLocaleString()}
- **Overall Outside Percentage**: ${(summary.reduce((sum, s) => sum + s.stats.outside, 0) / summary.reduce((sum, s) => sum + s.stats.matched, 0) * 100 || 0).toFixed(2)}%

**Deviation Statistics (across all games):**

- **Average Deviation**: ${(summary.reduce((sum, s) => sum + s.stats.avgDeviation * s.stats.matched, 0) / summary.reduce((sum, s) => sum + s.stats.matched, 0) || 0).toFixed(2)} cents
- **Max Deviation**: ${Math.max(...summary.map(s => s.stats.maxDeviation)).toFixed(2)} cents
- **Median Deviation (across games)**: ${calculatePercentile(summary.map(s => s.stats.medianDeviation).sort((a, b) => a - b), 50).toFixed(2)} cents
- **95th Percentile Deviation (across games)**: ${calculatePercentile(summary.map(s => s.stats.percentile95Deviation).sort((a, b) => a - b), 95).toFixed(2)} cents
`;

    // Save report
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
    const reportPath = path.join(REPORTS_DIR, 'espn_kalshi_comprehensive_statistics_report.md');
    fs.writeFileSync(reportPath, report);
    
    console.log(`\n\nReport saved to: ${reportPath}`);
    console.log(`\nProcessed ${summary.length} games successfully.`);
    
  } finally {
    await pgClient.end();
  }
}

main().catch(console.error);

