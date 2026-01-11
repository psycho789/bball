import { Client } from 'pg';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

const TEAM_ID_TO_TRICODE: { [key: string]: string } = {
  '1': 'ATL', '2': 'BOS', '17': 'BKN', '30': 'CHA', '4': 'CHI',
  '5': 'CLE', '6': 'DAL', '7': 'DEN', '8': 'DET', '9': 'GSW',
  '10': 'HOU', '11': 'IND', '12': 'LAC', '13': 'LAL', '29': 'MEM',
  '14': 'MIA', '15': 'MIL', '16': 'MIN', '3': 'NOP', '18': 'NYK',
  '25': 'OKC', '19': 'ORL', '20': 'PHI', '21': 'PHX', '22': 'POR',
  '23': 'SAC', '24': 'SAS', '28': 'TOR', '26': 'UTA', '27': 'WAS'
};

const months: { [key: string]: number } = {
  JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11
};

async function main() {
  // Load Kalshi keys
  const kalshiData = JSON.parse(fs.readFileSync(path.join(rootDir, 'data/raw/kalshi/markets/KXNBAGAME_latest.json'), 'utf-8'));
  const kalshiKeys = new Set<string>();
  const uniqueEvents = [...new Set(kalshiData.markets.map((m: any) => m.event_ticker))] as string[];
  
  for (const t of uniqueEvents) {
    const m = t.match(/KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})/);
    if (!m) continue;
    const year = 2000 + parseInt(m[1]);
    const month = months[m[2]];
    const day = parseInt(m[3]);
    const away = m[4];
    const home = m[5];
    const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    kalshiKeys.add(`${away}@${home}_${dateStr}`);
  }
  
  console.log('Kalshi games:', kalshiKeys.size);
  
  // Load ESPN keys from database
  const client = new Client({ connectionString: 'postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse' });
  await client.connect();
  
  const result = await client.query(`
    WITH game_data AS (
      SELECT 
        ep.game_id,
        SUBSTRING(p.home_team_ref FROM '/teams/([0-9]+)') as home_id,
        SUBSTRING(p.away_team_ref FROM '/teams/([0-9]+)') as away_id,
        (MIN(ep.wallclock) AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')::date as game_date_eastern
      FROM derived.espn_plays ep
      INNER JOIN derived.espn_probabilities_raw_items p 
        ON ep.game_id = p.game_id AND ep.play_id = p.event_id
      WHERE ep.wallclock IS NOT NULL
        AND p.home_win_percentage IS NOT NULL
      GROUP BY ep.game_id, p.home_team_ref, p.away_team_ref
      HAVING COUNT(*) > 100
    )
    SELECT DISTINCT home_id, away_id, game_date_eastern::text as game_date FROM game_data
  `);
  
  await client.end();
  
  const espnKeys = new Set<string>();
  for (const row of result.rows) {
    const home = TEAM_ID_TO_TRICODE[row.home_id] || 'UNK';
    const away = TEAM_ID_TO_TRICODE[row.away_id] || 'UNK';
    espnKeys.add(`${away}@${home}_${row.game_date}`);
  }
  
  console.log('ESPN games:', espnKeys.size);
  
  // Find overlap
  const overlap = [...kalshiKeys].filter(k => espnKeys.has(k));
  console.log('Overlap:', overlap.length);
  
  // Sample matches
  console.log('\nSample matches:');
  overlap.slice(0, 15).forEach(k => console.log('  ' + k));
  
  // Sample Kalshi without ESPN (for dates before Dec 20)
  const noEspn = [...kalshiKeys]
    .filter(k => !espnKeys.has(k))
    .filter(k => k < 'ZZZ_2025-12-20')  // Before ESPN cutoff
    .slice(0, 10);
  console.log('\nKalshi games without ESPN match (before Dec 20):');
  noEspn.forEach(k => console.log('  ' + k));
}

main().catch(console.error);
