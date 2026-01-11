# ESPN Odds Inspection Results

**Date**: 2025-12-30  
**Sprint**: Sprint 13 - Signal Improvement Foundation  
**Story**: S13-E2-S1 - Inspect Raw JSONB for Odds Fields  
**Table**: `espn.probabilities_raw_items`

## Inspection Commands

### 1. Inspect JSONB Keys
```sql
SELECT DISTINCT jsonb_object_keys(raw_item) as key_name
FROM espn.probabilities_raw_items
LIMIT 50;
```

**Results**:
```
      key_name       
---------------------
 tiePercentage
 spreadPushProb
 play
 sequenceNumber
 awayWinPercentage
 homeTeam
 competition
 $ref
 homeWinPercentage
 totalOverProb
 spreadCoverProbHome
 lastModified
 awayTeam
 source
(14 rows)
```

### 2. Sample Raw Item
```sql
SELECT event_id, last_modified_utc, raw_item::text
FROM espn.probabilities_raw_items
ORDER BY last_modified_utc DESC
LIMIT 1;
```

**Sample JSONB Structure**:
```json
{
  "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401810289/competitions/401810289/probabilities/401810289345?lang=en&region=us",
  "play": {"$ref": "..."},
  "source": {"id": "2", "state": "full", "description": "feed"},
  "awayTeam": {"$ref": "..."},
  "homeTeam": {"$ref": "..."},
  "competition": {"$ref": "..."},
  "lastModified": "2025-12-28T07:26Z",
  "tiePercentage": 0.0,
  "totalOverProb": 0.4807,
  "sequenceNumber": "345",
  "spreadPushProb": 0.0,
  "awayWinPercentage": 0.859,
  "homeWinPercentage": 0.141,
  "spreadCoverProbHome": 0.2042
}
```

### 3. Check Scoreboard Schema
```sql
\d espn.scoreboard_games
```

**Result**: No odds columns found in `espn.scoreboard_games`

## Findings

### ✓ Probabilities Found
The ESPN API provides **probability data**, not odds data:
- `homeWinPercentage`: Home team win probability (0-1)
- `awayWinPercentage`: Away team win probability (0-1)
- `totalOverProb`: Probability of total going over
- `spreadCoverProbHome`: Probability of home team covering spread
- `spreadPushProb`: Probability of spread push
- `tiePercentage`: Probability of tie

### ✗ Odds Data NOT Found
**No odds-related fields found**:
- ❌ No `moneyline` field
- ❌ No `american_odds` field
- ❌ No `decimal_odds` field
- ❌ No `fractional_odds` field
- ❌ No `implied_probability` field (we have raw probabilities instead)
- ❌ No `sportsbook` field
- ❌ No `bookmaker` field
- ❌ No `line` field (we have probabilities, not lines)

### Conclusion

**ESPN API provides probabilities, NOT sportsbook odds.**

The ESPN API gives us:
- Win probabilities (home/away)
- Spread probabilities
- Total probabilities

But it does **NOT** provide:
- Sportsbook odds (moneyline, spread lines, totals)
- Odds formats (American, decimal, fractional)
- Bookmaker information

**Implication**: 
- We cannot get external sportsbook odds from ESPN API
- We need to rely on other sources (Kaggle datasets, GitHub scrapers) for external sportsbook odds
- ESPN probabilities are useful for signal improvement but are not "true odds" from sportsbooks

## Next Steps

1. **Story 2.1**: ✓ COMPLETE - No odds data found in ESPN API
2. **Story 2.2**: ✓ COMPLETE - No odds columns in scoreboard_games
3. **Decision**: Proceed with external odds strategy decision (Epic 4) - ESPN cannot provide sportsbook odds

