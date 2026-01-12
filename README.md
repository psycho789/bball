## bball — NBA raw data warehouse (PostgreSQL)

This repo contains scripts and migrations for building a **raw NBA data warehouse**:
- historical game discovery (`nba_api` → `stats.nba.com`)
- raw archival fetchers (NBA CDN) for PBP/boxscore/odds/schedule
- PostgreSQL schema + migrations

### Prereqs
- Python 3.11+ (3.13 works)
- Docker + Docker Compose (recommended for local Postgres)

### Local setup (macOS / zsh)

#### 1) Start Postgres (Docker)
From the repo root:

```bash
docker compose up -d db
docker compose ps
```

This starts a Postgres 16 instance with:
- db: `bball_warehouse`
- user: `adamvoliva`
- password: `bball`
- port: `5432`

#### 2) Create env file
Copy the example env file:

```bash
cp env.example .env
```

If you need to override the DB connection string:
- edit `DATABASE_URL` in `.env`

Note:
- `.env` is intentionally gitignored (see `.gitignore`).

#### 3) Create Python venv + install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### 4) Run migrations

```bash
source .env
python scripts/utils/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations
```

#### 4.1) Connect to DB quickly (optional)
Make the helper executable once:

```bash
chmod +x scripts/utils/psql.sh
```

Then:

```bash
source .env
./scripts/utils/psql.sh
```

#### 5) Smoke tests

Discover game IDs (season-by-season):

```bash
python scripts/discover_game_ids.py --season 2023-24 --out data/discovery/game_ids_2023-24.csv
```

Fetch one game’s raw PBP + boxscore:

```bash
python scripts/fetch_pbp.py --game-id 0022400196 --out data/raw/pbp/0022400196.json
python scripts/fetch_boxscore.py --game-id 0022400196 --out data/raw/boxscore/0022400196.json
```

Note: `scripts/fetch/fetch_pbp.py` defaults to `--source auto` (try CDN, fall back to `nba_api` for older games that 403 on the CDN). The fallback is converted into the same `game.actions` shape our loader consumes.

Fetch odds + schedule snapshots:

```bash
python scripts/fetch/fetch_odds_today.py --out data/raw/odds/odds_todaysGames_{fetched_at_utc}.json
python scripts/fetch/fetch_scheduleLeagueV2.py --out data/raw/schedule/scheduleLeagueV2_{fetched_at_utc}.json
```

### Notes
- Fetchers are **archive-only** (network → file + manifest). Loaders will register `source_files` and write to DB (Sprint 04).

### Troubleshooting: Postgres “No space left on device” (Docker Desktop)

If you see errors like:
- `could not extend file "base/...": No space left on device`

…and your Mac has plenty of free space, this usually means **Docker Desktop’s VM disk image is full**, not your host disk.

#### Confirm

```bash
docker exec -i bball-postgres bash -lc 'df -h /var/lib/postgresql/data'
```

If it shows `Use% 100%`, you need to give Docker Desktop more disk.

#### Increase Docker Desktop disk image size (preferred; does NOT delete volumes)

- Open **Docker Desktop**
- **Settings** → **Resources** → **Disk image size**
- Increase it (recommend **128GB+** for large backfills)
- Click **Apply & Restart**

After restart, re-check:

```bash
docker exec -i bball-postgres bash -lc 'df -h /var/lib/postgresql/data'
```

Then rerun the loader (or the full backfill runner) that previously failed.

### Backfill multiple seasons

Run the orchestrator via the wrapper (recommended; runs unbuffered with log/report files):

```bash
source .env
./scripts/run_backfill.sh --from 2023-24 --to 2023-24 --workers 2
```

To backfill the **previous 10 seasons before 2025-26**, excluding seasons you already have (2023-24, 2024-25):

```bash
source .env
./scripts/run_backfill.sh \
  --end-season 2025-26 \
  --seasons-back 10 \
  --exclude 2023-24 \
  --exclude 2024-25 \
  --workers 2
```

## Grid Search Hyperparameter Optimization

Systematically test entry/exit threshold combinations to find optimal trading strategy parameters.

### Prerequisites

Install additional dependencies for visualization:
```bash
pip install matplotlib seaborn scipy
```

### Running Grid Search

1. **Test with small batch first** (recommended):
   ```bash
   python scripts/trade/grid_search_hyperparameters.py \
     --season "2025-26" \
     --entry-min 0.02 --entry-max 0.05 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.02 --exit-step 0.01 \
     --max-games 10 \
     --max-combinations 6 \
     --workers 4 \
     --seed 42 \
     --enable-fees \
     --output-dir grid_search_test/
   ```
   This tests 6 combinations on 10 games (~5-10 minutes) to verify everything works.

2. **Run full grid search** (tests all valid parameter combinations):
   ```bash
   python scripts/trade/grid_search_hyperparameters.py \
     --season "2025-26" \
     --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
     --workers 8 \
     --seed 42 \
     --enable-fees \
     --slippage-rate 0.0 \
     --min-trade-count 200 \
     --output-dir grid_search_results/
   ```
   
   Or use a game list file:
   ```bash
   python scripts/grid_search_hyperparameters.py \
     --game-list path/to/game_ids.json \
     --entry-min 0.02 --entry-max 0.10 --entry-step 0.01 \
     --exit-min 0.00 --exit-max 0.05 --exit-step 0.005 \
     --workers 8 \
     --seed 42 \
     --enable-fees \
     --output-dir grid_search_results/
   ```

2. **Generate plots and pattern summary**:
   ```bash
   python scripts/trade/analyze_grid_search_results.py \
     --results-dir grid_search_results/ \
     --output-dir grid_search_results/
   ```

3. **Check results**:
   - View plots in `grid_search_results/plots/`
   - Check `final_selection.json` for chosen parameters
   - Review pattern summary printed to console

### Interpreting Train/Valid/Test Usage

- **Train split**: Used for broad ranking of combinations (identify top N)
- **Validation split**: Used to select final candidate from top N train combos (do NOT tune on test)
- **Test split**: One-time final report only (do NOT use for selection or tuning)

### Key Output Files

- `grid_results_train.csv` / `.json`: Results on training set (for ranking)
- `grid_results_valid.csv` / `.json`: Results on validation set (for selection)
- `grid_results_test.csv` / `.json`: Results on test set (final reporting only)
- `final_selection.json`: Chosen parameters and metrics on all splits
- `train_games.json`, `valid_games.json`, `test_games.json`: Game ID splits (for reproducibility)
- `plots/profit_heatmap_train.png`, `plots/profit_heatmap_valid.png`: Core visualizations
- `plots/marginal_effects.png`: Parameter sensitivity
- `plots/tradeoff_scatter.png`: Frequency vs. profitability trade-off
- `plots/profit_factor_heatmap_valid.png`: Risk-adjusted performance

## HTML Export and GitHub Pages Deployment

The webapp includes functionality to export the aggregate statistics dashboard as a standalone HTML file for GitHub Pages deployment.

### Exporting HTML

1. Start the webapp (see webapp documentation)
2. Navigate to the Aggregate Statistics page
3. Click the "Export HTML" button
4. The HTML file will be saved to `docs/aggregate-stats.html`

### Deploying to GitHub Pages

After exporting, you can deploy the dashboard to GitHub Pages for public access:

1. **Commit and push the exported file**:
   ```bash
   git add docs/aggregate-stats.html
   git commit -m "Export aggregate statistics dashboard"
   git push origin main
   ```

2. **Configure GitHub Pages**:
   - Go to repository Settings → Pages
   - Set Source to: Branch `main`, Folder `/docs`
   - Click Save

3. **Access your dashboard**:
   - URL: `https://[username].github.io/[repository-name]/aggregate-stats.html`
   - GitHub Pages will automatically rebuild when you push updates

For detailed instructions, see [docs/GITHUB_PAGES_DEPLOYMENT.md](docs/GITHUB_PAGES_DEPLOYMENT.md).


