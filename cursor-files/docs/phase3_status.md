# Phase 3 Status - Canonical Dataset

## Current Status

**View Created**: ✅ `derived.snapshot_features_v1` exists as a VIEW
**Performance**: ❌ **TOO SLOW** - Queries taking minutes
**Solution**: Convert to MATERIALIZED VIEW

## Commands to Run

See `cursor-files/docs/phase3_quick_commands.sql` for all commands.

### Quick Summary:

1. **Create Materialized View** (takes several minutes, ~5.3M rows):
   ```bash
   cd /Users/adamvoliva/Code/bball
   source .env
   psql "$DATABASE_URL" -f cursor-files/docs/phase3_quick_commands.sql
   ```

2. **Or run SQL directly** - Copy from `phase3_quick_commands.sql`

## What Was Done

- ✅ View created with all required features
- ✅ Schema includes: ESPN probs, game state, interaction terms, lagged features, Kalshi data
- ✅ Kalshi alignment logic implemented (60 second window)
- ✅ Home/away market handling implemented

## What Needs to Be Done

- ⏳ Convert VIEW to MATERIALIZED VIEW (performance fix)
- ⏳ Create indexes after materialized view is built
- ⏳ Validate data quality (uniqueness, sequence_number ordering)
- ⏳ Test query performance
- ⏳ Document refresh strategy

## Performance Issue

The VIEW is slow because:
- Complex CTEs with window functions
- LATERAL joins for Kalshi alignment
- Can't use indexes effectively on views
- Computes everything on-the-fly

**Solution**: Materialized view pre-computes everything, then queries are fast.

