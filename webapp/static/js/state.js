/**
 * Application state management.
 * 
 * Design Pattern: Singleton Pattern for global state
 * Algorithm: Simple object-based state storage
 * Big O: O(1) for state access
 */

const AppState = {
    chart: null,
    homeSeries: null,
    awaySeries: null,
    kalshiSeries: [],  // Can have multiple Kalshi markets
    selectedGameId: null,
    chartBaseTimestamp: null,
    // Filter and sort state
    filters: {
        season: '2025-26',
        has_kalshi: true, // true = only with kalshi, false = only without, null = all
        sort_by: 'date',
        sort_order: 'desc',
        team_filter: null,
        date_from: null,
        date_to: null,
    },
    // Live games state
    liveGames: {}, // {gameId: {websocket, chartData, lastUpdate, connectionStatus}}
};

/**
 * Get live game state.
 */
function getLiveGameState(gameId) {
    return AppState.liveGames[gameId] || null;
}

/**
 * Set live game state.
 */
function setLiveGameState(gameId, state) {
    AppState.liveGames[gameId] = { ...AppState.liveGames[gameId], ...state };
}

/**
 * Clear live game state.
 */
function clearLiveGameState(gameId) {
    delete AppState.liveGames[gameId];
}

