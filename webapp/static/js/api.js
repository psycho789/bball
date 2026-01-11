/**
 * API communication module.
 * 
 * Design Pattern: Service Pattern for API calls
 * Algorithm: Fetch API with error handling
 * Big O: O(1) per API call
 */

async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}

async function loadGames(offset = 0, limit = 50, filters = {}) {
    const params = new URLSearchParams({
        season: filters.season || '2025-26',
        limit: limit.toString(),
        offset: offset.toString(),
    });
    
    // Add optional filters
    if (filters.has_kalshi !== undefined && filters.has_kalshi !== null) {
        params.append('has_kalshi', filters.has_kalshi.toString());
    }
    if (filters.sort_by) {
        params.append('sort_by', filters.sort_by);
    }
    if (filters.sort_order) {
        params.append('sort_order', filters.sort_order);
    }
    if (filters.team_filter) {
        params.append('team_filter', filters.team_filter);
    }
    if (filters.date_from) {
        params.append('date_from', filters.date_from);
    }
    if (filters.date_to) {
        params.append('date_to', filters.date_to);
    }
    
    const response = await fetchJSON(`/api/games?${params.toString()}`);
    return response; // Returns {games, total, limit, offset, has_more}
}

async function getGameMetadata(gameId) {
    return fetchJSON(`/api/games/${gameId}/meta`);
}

async function getGameProbabilities(gameId) {
    return fetchJSON(`/api/games/${gameId}/probs`);
}

async function getKalshiCandles(gameId, intervalSeconds, source = 'auto', ticker = null, startTs = null, endTs = null) {
    const params = new URLSearchParams({
        interval_seconds: intervalSeconds.toString(),
        source: source,
    });
    if (ticker) {
        params.append('ticker', ticker);
    }
    if (startTs) {
        params.append('start_ts', startTs.toString());
    }
    if (endTs) {
        params.append('end_ts', endTs.toString());
    }
    const response = await fetch(`/api/probabilities/${gameId}/kalshi-candles?${params.toString()}`);
    if (!response.ok) {
        if (response.status === 400) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || errorData.detail || 'Window too large for 1-second resolution');
        }
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}

async function getGameStats(gameId) {
    return fetchJSON(`/api/games/${gameId}/stats`);
}

async function getBulkGameStats(gameIds) {
    // gameIds should be an array
    const idsParam = Array.isArray(gameIds) ? gameIds.join(',') : gameIds;
    return fetchJSON(`/api/games/stats/bulk?game_ids=${encodeURIComponent(idsParam)}`);
}

async function getAggregateStats(season = "2025-26") {
    return fetchJSON(`/api/stats/aggregate?season=${encodeURIComponent(season)}`);
}

async function getModelEvaluation(seasonStart = 2024) {
    return fetchJSON(`/api/stats/model-evaluation?season_start=${seasonStart}`);
}

async function runSimulationApi(gameId, entryThreshold, exitThreshold, excludeFirstSeconds, excludeLastSeconds, betAmount) {
    const params = new URLSearchParams({
        entry_threshold: entryThreshold.toString(),
        exit_threshold: exitThreshold.toString(),
        exclude_first_seconds: excludeFirstSeconds.toString(),
        exclude_last_seconds: excludeLastSeconds.toString(),
        bet_amount: betAmount.toString(),
    });
    return fetchJSON(`/api/games/${gameId}/simulation?${params.toString()}`);
}

async function checkNewGamesApi() {
    const response = await fetch('/api/update/check-new-games');
    if (!response.ok) {
        throw new Error(`Check failed: ${response.status}`);
    }
    return response.json();
}

async function triggerUpdateApi() {
    const response = await fetch('/api/update/trigger', {
        method: 'POST'
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Update failed: ${response.status}`);
    }
    return response.json();
}

async function checkUpdateStatusApi() {
    const response = await fetch('/api/update/status');
    if (!response.ok) {
        throw new Error(`Status check failed: ${response.status}`);
    }
    return response.json();
}

async function clearGamesCacheApi() {
    const response = await fetch('/api/update/clear-cache', {
        method: 'POST'
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Clear cache failed: ${response.status}`);
    }
    return response.json();
}

async function clearSimulationCacheApi() {
    const response = await fetch('/api/simulation/clear-cache', {
        method: 'POST'
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Clear simulation cache failed: ${response.status}`);
    }
    return response.json();
}

