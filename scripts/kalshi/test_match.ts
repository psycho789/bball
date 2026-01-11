import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { Client } from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '../..');

const TEAM_TRICODES: { [key: string]: string } = {
  'ATL': '1', 'BOS': '2', 'BKN': '17', 'CHA': '30', 'CHI': '4',
  'CLE': '5', 'DAL': '6', 'DEN': '7', 'DET': '8', 'GSW': '9',
  'HOU': '10', 'IND': '11', 'LAC': '12', 'LAL': '13', 'MEM': '29',
  'MIA': '14', 'MIL': '15', 'MIN': '16', 'NOP': '3', 'NYK': '18',
  'OKC': '25', 'ORL': '19', 'PHI': '20', 'PHX': '21', 'POR': '22',
  'SAC': '23', 'SAS': '24', 'TOR': '28', 'UTA': '26', 'WAS': '27'
};

async function main() {
  const pgClient = new Client({
    connectionString: 'postgresql://adamvoliva@127.0.0.1:5432/bball_warehouse'
  });
  await pgClient.connect();
  
  // Test: SAS @ ATL on Dec 19
  const home = 'ATL';
  const away = 'SAS';
  const date = '2025-12-19';
  const nextDate = '2025-12-20';
  
  console.log(`Looking for ${away}@${home} on ${date}`);
  console.log(`Home team ID: ${TEAM_TRICODES[home]}`);
  console.log(`Away team ID: ${TEAM_TRICODES[away]}`);
  
  const result = await pgClient.query(`
    SELECT DISTINCT
      p.game_id,
      p.home_team_ref,
      p.away_team_ref,
      MIN(ep.wallclock) as first_ts,
      MAX(ep.wallclock) as last_ts,
      COUNT(*) as events
    FROM derived.espn_probabilities_raw_items p
    INNER JOIN derived.espn_plays ep ON p.game_id = ep.game_id
    WHERE p.home_team_ref LIKE $1
      AND p.away_team_ref LIKE $2
      AND ep.wallclock::date BETWEEN $3::date AND $4::date
      AND ep.wallclock IS NOT NULL
    GROUP BY p.game_id, p.home_team_ref, p.away_team_ref
    LIMIT 5
  `, [
    `%/teams/${TEAM_TRICODES[home]}%`,
    `%/teams/${TEAM_TRICODES[away]}%`,
    date,
    nextDate
  ]);
  
  console.log(`\nFound ${result.rows.length} matches:`);
  console.log(JSON.stringify(result.rows, null, 2));
  
  await pgClient.end();
}

main().catch(console.error);
