# Free Hosting Deployment Guide

This guide covers deploying the webapp and database to **Render** (100% free tier).

## Quick Start: Render (Recommended)

### Why Render?
- ✅ **100% Free** for both web service and PostgreSQL
- ✅ Automatic HTTPS
- ✅ Easy GitHub integration
- ✅ Environment variable management
- ⚠️ Service spins down after 15 min inactivity (wakes on request)
- ⚠️ 750 hours/month free tier limit

### Prerequisites
1. GitHub account
2. Render account (sign up at https://render.com)
3. Your code pushed to a GitHub repository

### Step 1: Prepare Database Schema

Since you mentioned you don't need the NBA schema, you'll want to:

1. **Export only the schemas you need** (espn, kalshi, derived):
```bash
# Connect to your local database
psql -h localhost -p 5432 -U adamvoliva -d bball_warehouse

# Export only the schemas you need
pg_dump -h localhost -p 5432 -U adamvoliva -d bball_warehouse \
  --schema=espn --schema=kalshi --schema=derived \
  --no-owner --no-acl > webapp_schema.sql
```

2. **Or create a minimal schema** with just the tables your webapp uses:
   - `espn.probabilities_raw_items`
   - `espn.prob_event_state`
   - `espn.scoreboard_games`
   - `kalshi.candlesticks`
   - `kalshi.markets`
   - `derived.game_stats` (if used)

### Step 2: Deploy to Render

#### Option A: Using render.yaml (Automatic)

1. **Push your code to GitHub** (if not already)

2. **Go to Render Dashboard** → New → Blueprint

3. **Connect your GitHub repository**

4. **Render will detect `render.yaml`** and create both services automatically

5. **Wait for deployment** (first deploy takes ~5-10 minutes)

#### Option B: Manual Setup

1. **Create PostgreSQL Database:**
   - Render Dashboard → New → PostgreSQL
   - Name: `bball-db`
   - Plan: Free
   - Database: `bball_warehouse`
   - User: `adamvoliva`
   - Note the **Internal Database URL** (starts with `postgresql://`)

2. **Create Web Service:**
   - Render Dashboard → New → Web Service
   - Connect your GitHub repository
   - Settings:
     - **Name**: `bball-webapp`
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r webapp/requirements.txt`
     - **Start Command**: `cd webapp && uvicorn api.main:app --host 0.0.0.0 --port $PORT`
     - **Root Directory**: Leave empty (or set to `.` if needed)

3. **Set Environment Variables:**
   - `DATABASE_URL`: Use the Internal Database URL from step 1
   - `PRELOAD_CACHE`: `true` (optional, for faster first load)
   - `DEBUG`: `false`

4. **Deploy**

### Step 3: Load Your Data

After deployment, you need to load your data into Render's PostgreSQL:

1. **Get your Render database connection string:**
   - Render Dashboard → Your Database → Info tab
   - Copy the **Internal Database URL**

2. **Load your schema and data:**
```bash
# Load schema
psql "YOUR_RENDER_DATABASE_URL" < webapp_schema.sql

# Or if you have a data dump:
psql "YOUR_RENDER_DATABASE_URL" < your_data_dump.sql
```

**Note**: Render's free tier PostgreSQL has:
- 90-day inactivity limit (can be extended)
- 1GB storage limit
- No direct external connections (use Internal Database URL from web service)

### Step 4: Access Your App

Your app will be available at:
```
https://bball-webapp.onrender.com
```

(Replace `bball-webapp` with your service name)

---

## Alternative Options

### Railway ($5/month credit - often free for small apps)

1. Sign up at https://railway.app
2. New Project → Deploy from GitHub
3. Add PostgreSQL service
4. Set `DATABASE_URL` environment variable
5. Deploy

**Pros**: No cold starts, easier database access
**Cons**: Not 100% free (but $5 credit usually covers small apps)

### Supabase (PostgreSQL) + Render (Web Service)

1. **Supabase** (free PostgreSQL):
   - Sign up at https://supabase.com
   - Create new project
   - Get connection string from Settings → Database

2. **Render** (web service):
   - Deploy as above
   - Use Supabase connection string for `DATABASE_URL`

**Pros**: Better PostgreSQL tier (500MB, 2GB bandwidth)
**Cons**: Two services to manage

### Neon (PostgreSQL) + Render (Web Service)

1. **Neon** (free PostgreSQL):
   - Sign up at https://neon.tech
   - Create project
   - Get connection string

2. **Render** (web service):
   - Deploy as above
   - Use Neon connection string for `DATABASE_URL`

**Pros**: Branching for dev/staging, 0.5GB storage
**Cons**: Two services to manage

---

## Troubleshooting

### Service won't start
- Check logs in Render dashboard
- Verify `DATABASE_URL` is set correctly
- Ensure `requirements.txt` is in `webapp/` directory

### Database connection errors
- Use **Internal Database URL** (not External)
- Verify database is running (Render Dashboard)
- Check firewall rules (shouldn't be needed for Internal URL)

### Cold starts are slow
- Normal for free tier (15 min inactivity timeout)
- Consider upgrading to paid tier if needed
- Or use Railway (no cold starts, but $5/month credit)

### WebSocket issues
- Render free tier supports WebSockets
- Check that your WebSocket endpoint is properly configured
- Verify CORS settings in `main.py`

---

## Cost Summary

| Service | Free Tier Limits | Cost |
|---------|-----------------|------|
| **Render Web** | 750 hours/month, spins down after 15 min | $0 |
| **Render PostgreSQL** | 1GB storage, 90-day inactivity limit | $0 |
| **Railway** | $5 credit/month | ~$0 (if under limit) |
| **Supabase** | 500MB storage, 2GB bandwidth | $0 |
| **Neon** | 0.5GB storage | $0 |

---

## Next Steps

1. Deploy using Render (recommended for 100% free)
2. Load your data (only espn, kalshi, derived schemas)
3. Test your endpoints
4. Share your app URL!

