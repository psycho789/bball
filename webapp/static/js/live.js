/**
 * Live games module - handles live games list and detail views.
 * 
 * Design Pattern: Module Pattern
 * Algorithm: HTTP polling with configurable interval
 * Big O: O(n) where n = number of live games
 */

let liveGamesRefreshInterval = null;
let liveGamesLastUpdate = null;

/**
 * Load live games from API and render them.
 */
async function loadLiveGames() {
    const container = document.getElementById('liveGamesContainer');
    const loadingEl = document.getElementById('liveGamesLoading');
    const emptyStateEl = document.getElementById('liveGamesEmptyState');
    const errorStateEl = document.getElementById('liveGamesErrorState');
    const errorMessageEl = document.getElementById('liveGamesErrorMessage');
    
    if (!container || !loadingEl || !emptyStateEl || !errorStateEl) {
        console.error('Live games DOM elements not found');
        return;
    }
    
    // Show loading
    loadingEl.style.display = 'block';
    emptyStateEl.style.display = 'none';
    errorStateEl.style.display = 'none';
    container.innerHTML = '';
    
    try {
        const response = await fetch('/api/live/games');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        liveGamesLastUpdate = new Date(data.timestamp);
        
        loadingEl.style.display = 'none';
        
        if (!data.games || data.games.length === 0) {
            // No live games
            emptyStateEl.style.display = 'block';
            container.innerHTML = '';
        } else {
            // Render live games
            emptyStateEl.style.display = 'none';
            renderLiveGamesList(data.games);
        }
    } catch (error) {
        console.error('Error loading live games:', error);
        loadingEl.style.display = 'none';
        emptyStateEl.style.display = 'none';
        errorStateEl.style.display = 'block';
        if (errorMessageEl) {
            errorMessageEl.textContent = error.message || 'Unable to fetch live games';
        }
    }
}

/**
 * Render list of live games.
 */
function renderLiveGamesList(games) {
    const container = document.getElementById('liveGamesContainer');
    if (!container) return;
    
    container.innerHTML = games.map(game => renderLiveGameCard(game)).join('');
    
    // Add click handlers
    container.querySelectorAll('.live-game-card').forEach(card => {
        const gameId = card.dataset.gameId;
        card.addEventListener('click', () => {
            navigateToLiveGameDetail(gameId);
        });
    });
}

/**
 * Render a single live game card.
 */
function renderLiveGameCard(game) {
    const statusClass = game.status === 'STATUS_IN_PROGRESS' ? 'status-live' : 
                       game.status === 'STATUS_HALFTIME' ? 'status-halftime' : 
                       'status-other';
    
    const statusText = game.status === 'STATUS_IN_PROGRESS' ? 'LIVE' :
                      game.status === 'STATUS_HALFTIME' ? 'HALFTIME' :
                      game.status === 'STATUS_DELAYED' ? 'DELAYED' :
                      game.status || 'LIVE';
    
    const homeScore = game.home_score !== null && game.home_score !== undefined ? game.home_score : '—';
    const awayScore = game.away_score !== null && game.away_score !== undefined ? game.away_score : '—';
    
    return `
        <div class="live-game-card ${statusClass}" data-game-id="${game.game_id}">
            <div class="live-game-status">
                <span class="status-indicator"></span>
                <span class="status-text">${statusText}</span>
            </div>
            <div class="live-game-teams">
                <div class="live-game-team away">
                    <span class="team-abbr">${game.away_team_abbrev || game.away_team || 'AWAY'}</span>
                    <span class="team-score">${awayScore}</span>
                </div>
                <div class="live-game-vs">@</div>
                <div class="live-game-team home">
                    <span class="team-score">${homeScore}</span>
                    <span class="team-abbr">${game.home_team_abbrev || game.home_team || 'HOME'}</span>
                </div>
            </div>
            <div class="live-game-meta">
                <span class="game-id">Game ID: ${game.game_id}</span>
            </div>
        </div>
    `;
}

/**
 * Start auto-refresh for live games list.
 */
function startLiveGamesAutoRefresh() {
    // Clear existing interval
    if (liveGamesRefreshInterval) {
        clearInterval(liveGamesRefreshInterval);
    }
    
    // Refresh every 30 seconds
    liveGamesRefreshInterval = setInterval(() => {
        loadLiveGames();
    }, 30000);
    
    // Update indicator
    const indicator = document.getElementById('autoRefreshIndicator');
    if (indicator) {
        indicator.style.display = 'flex';
    }
}

/**
 * Stop auto-refresh for live games list.
 */
function stopLiveGamesAutoRefresh() {
    if (liveGamesRefreshInterval) {
        clearInterval(liveGamesRefreshInterval);
        liveGamesRefreshInterval = null;
    }
    
    const indicator = document.getElementById('autoRefreshIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

/**
 * Initialize live games list view.
 */
function initializeLiveGamesList() {
    // Load initial games
    loadLiveGames();
    
    // Start auto-refresh
    startLiveGamesAutoRefresh();
    
    // Setup refresh button
    const refreshButton = document.getElementById('refreshLiveGames');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            loadLiveGames();
        });
    }
    
    // Setup retry button
    const retryButton = document.getElementById('retryLiveGames');
    if (retryButton) {
        retryButton.addEventListener('click', () => {
            loadLiveGames();
        });
    }
}

/**
 * Navigate to live game detail view.
 */
function navigateToLiveGameDetail(gameId) {
    window.location.hash = `/live/${gameId}`;
    showLiveGameDetailView(gameId);
}

/**
 * Show live game detail view with WebSocket connection.
 */
async function showLiveGameDetail(gameId) {
    // Cleanup any existing live game connection
    cleanupLiveGame();
    
    // Reset update tracking
    if (typeof resetUpdateTracking === 'function') {
        resetUpdateTracking();
    }
    
    try {
        // Load game metadata
        const meta = await getGameMetadata(gameId);
        
        // Update header
        updateLiveGameHeader(meta);
        
        // Initialize chart with empty data (will be populated by WebSocket)
        const baseTimestamp = meta.game_start_timestamp || Math.floor(Date.now() / 1000);
        createChart(meta.home_color, baseTimestamp);
        
        // Add 50% reference line
        const currentTime = Math.floor(Date.now() / 1000);
        const fiftyLine = AppState.chart.addLineSeries({
            color: 'rgba(255, 255, 255, 0.15)',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        fiftyLine.setData([
            { time: baseTimestamp, value: 50 },
            { time: currentTime, value: 50 },
        ]);
        
        // Initialize empty series (will be updated incrementally)
        AppState.homeSeries.setData([]);
        AppState.awaySeries.setData([]);
        
        // Setup chart toggles
        setupChartToggles();
        
        // Create WebSocket client
        const websocket = new WebSocketClient(gameId);
        
        // Store in AppState
        setLiveGameState(gameId, {
            websocket,
            chartData: { espn: [], kalshi: {} },
            lastUpdate: null,
            connectionStatus: 'connecting'
        });
        
        // Setup message handler
        websocket.onMessage((data) => {
            handleLiveGameMessage(gameId, data);
        });
        
        // Setup error handler
        websocket.onError((error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus('error', 'Connection error');
        });
        
        // Setup reconnection handler
        websocket.onReconnect(() => {
            updateConnectionStatus('connected', 'Connected');
        });
        
        // Update connection status
        updateConnectionStatus('connecting', 'Connecting...');
        
        // Connect WebSocket
        websocket.connect();
        
        // Update connection status periodically
        const statusInterval = setInterval(() => {
            const status = websocket.getStatus();
            if (status === 'connected') {
                updateConnectionStatus('connected', 'Connected');
            } else if (status === 'connecting') {
                updateConnectionStatus('connecting', 'Connecting...');
            } else if (status === 'reconnecting') {
                updateConnectionStatus('reconnecting', `Reconnecting (${websocket.reconnectAttempts}/${websocket.maxReconnectAttempts})...`);
            } else if (status === 'error') {
                updateConnectionStatus('error', 'Connection failed');
            } else {
                updateConnectionStatus('disconnected', 'Disconnected');
            }
        }, 500);
        
        // Store interval for cleanup
        setLiveGameState(gameId, { statusInterval });
        
    } catch (error) {
        console.error('Failed to load live game:', error);
        updateConnectionStatus('error', 'Failed to load game');
    }
}

/**
 * Handle WebSocket message for live game.
 */
function handleLiveGameMessage(gameId, data) {
    const state = getLiveGameState(gameId);
    if (!state) return;
    
    // Update last update time
    setLiveGameState(gameId, { lastUpdate: Date.now() });
    
    // Handle different message types
    if (data.type === 'data') {
        // Live data update
        const espnData = data.espn || [];
        const kalshiData = data.kalshi || {};
        
        // Update chart incrementally
        if (typeof updateChartData === 'function') {
            updateChartData(espnData, kalshiData);
        }
        
        // Update stored data
        if (espnData.length > 0) {
            state.chartData.espn.push(...espnData);
        }
        if (Object.keys(kalshiData).length > 0) {
            Object.assign(state.chartData.kalshi, kalshiData);
        }
    } else if (data.type === 'error') {
        console.error('WebSocket error message:', data.message);
        updateConnectionStatus('error', data.message || 'Connection error');
    } else {
        // Default: treat as data message (backward compatibility)
        const espnData = data.espn || [];
        const kalshiData = data.kalshi || {};
        
        if (typeof updateChartData === 'function') {
            updateChartData(espnData, kalshiData);
        }
    }
}

/**
 * Update live game header with metadata.
 */
function updateLiveGameHeader(meta) {
    const homeAbbr = document.getElementById('homeAbbr');
    const homeName = document.getElementById('homeName');
    const homeScore = document.getElementById('homeScore');
    const awayAbbr = document.getElementById('awayAbbr');
    const awayName = document.getElementById('awayName');
    const awayScore = document.getElementById('awayScore');
    
    if (homeAbbr) homeAbbr.textContent = meta.home_team_abbr || 'HOME';
    if (homeName) homeName.textContent = meta.home_team_name || 'Home Team';
    if (homeScore) homeScore.textContent = meta.final_home_score || '0';
    
    if (awayAbbr) awayAbbr.textContent = meta.away_team_abbr || 'AWAY';
    if (awayName) awayName.textContent = meta.away_team_name || 'Away Team';
    if (awayScore) awayScore.textContent = meta.final_away_score || '0';
    
    // Update legend
    if (typeof updateChartLegend === 'function') {
        updateChartLegend(meta, []);
    }
}

/**
 * Update connection status UI.
 */
function updateConnectionStatus(status, text) {
    const statusIndicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    if (statusIndicator) {
        statusIndicator.className = 'status-indicator';
        if (status === 'connected') {
            statusIndicator.classList.add('status-connected');
        } else if (status === 'connecting' || status === 'reconnecting') {
            statusIndicator.classList.add('status-connecting');
        } else if (status === 'error') {
            statusIndicator.classList.add('status-error');
        } else {
            statusIndicator.classList.add('status-disconnected');
        }
    }
    
    if (statusText) {
        statusText.textContent = text || status;
    }
}

/**
 * Cleanup live game (disconnect WebSocket, clear state).
 */
function cleanupLiveGame() {
    // Get current live game from AppState
    const liveGames = AppState.liveGames;
    for (const gameId in liveGames) {
        const state = liveGames[gameId];
        
        // Disconnect WebSocket
        if (state.websocket) {
            state.websocket.disconnect();
            state.websocket.removeAllHandlers();
        }
        
        // Clear status interval
        if (state.statusInterval) {
            clearInterval(state.statusInterval);
        }
        
        // Clear state
        clearLiveGameState(gameId);
    }
}

