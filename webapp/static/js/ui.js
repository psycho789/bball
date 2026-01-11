/**
 * UI rendering and interaction module.
 * 
 * Design Pattern: View Pattern for UI updates
 * Algorithm: DOM manipulation and event handling
 * Big O: O(n) where n = number of games/items rendered
 */

let currentOffset = 0;
let isLoading = false;
let hasMoreGames = true;

// Filter and sort state (synced with AppState.filters)
function getFilters() {
    return { ...AppState.filters };
}

function setFilters(newFilters) {
    AppState.filters = { ...AppState.filters, ...newFilters };
    // Reset pagination when filters change
    currentOffset = 0;
    hasMoreGames = true;
}

function renderGameCard(game, stats = null) {
    let statsHtml = '';
    // Use stats from game object if available (from games endpoint), otherwise use passed stats
    const gameStats = game.stats || (stats && stats.espn ? stats.espn : null);
    
    if (gameStats) {
        statsHtml = `
            <div class="game-card-stats">
                ${gameStats.standard_deviation !== null && gameStats.standard_deviation !== undefined ? `
                <div class="stat-item">
                    <span class="stat-label">Std Dev</span>
                    <span class="stat-value">${(gameStats.standard_deviation * 100).toFixed(1)}%</span>
                </div>
                ` : ''}
                ${gameStats.probability_range !== null && gameStats.probability_range !== undefined ? `
                <div class="stat-item">
                    <span class="stat-label">Range</span>
                    <span class="stat-value">${(gameStats.probability_range * 100).toFixed(1)}%</span>
                </div>
                ` : ''}
                ${gameStats.volatility !== null && gameStats.volatility !== undefined ? `
                <div class="stat-item">
                    <span class="stat-label">Volatility</span>
                    <span class="stat-value">${(gameStats.volatility * 100).toFixed(1)}%</span>
                </div>
                ` : ''}
                ${gameStats.lead_changes !== null && gameStats.lead_changes !== undefined ? `
                <div class="stat-item">
                    <span class="stat-label">Lead Changes</span>
                    <span class="stat-value">${gameStats.lead_changes || 0}</span>
                </div>
                ` : ''}
                ${gameStats.time_averaged_in_game_brier_error !== null && gameStats.time_averaged_in_game_brier_error !== undefined ? `
                <div class="stat-item">
                    <span class="stat-label">Time-Averaged In-Game Brier Error</span>
                    <span class="stat-value">${gameStats.time_averaged_in_game_brier_error.toFixed(3)}</span>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    // Format game date
    let gameDateHtml = '';
    if (game.game_date) {
        try {
            const date = new Date(game.game_date);
            const formattedDate = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric' 
            });
            const formattedTime = date.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
            gameDateHtml = `
                <div class="game-date">
                    <span class="game-date-text">${formattedDate}</span>
                    <span class="game-time-text">${formattedTime}</span>
                </div>
            `;
        } catch (e) {
            // If date parsing fails, skip it
        }
    }
    
    return `
        <div class="game-card" data-game-id="${game.game_id}" data-has-kalshi="${game.has_kalshi}">
            <div class="game-card-header">
                <div class="game-teams">
                    ${game.home_won ? '<span class="winner-indicator"></span>' : ''}
                    <span>${game.home_team_abbr}</span>
                    <span class="game-vs">vs</span>
                    <span>${game.away_team_abbr}</span>
                    ${!game.home_won ? '<span class="winner-indicator"></span>' : ''}
                </div>
            </div>
            ${gameDateHtml}
            <div class="game-score">
                <span class="${game.home_won ? 'score-winner' : ''}">${game.final_home_score}</span>
                <span class="score-separator"> - </span>
                <span class="${!game.home_won ? 'score-winner' : ''}">${game.final_away_score}</span>
            </div>
            ${statsHtml}
        </div>
    `;
}

// Use event delegation for game card clicks (more reliable than attaching to each card)
// Check if handler is already attached using a data attribute on the element
function attachGameCardClickHandler() {
    const selector = document.getElementById('gameSelector');
    if (!selector) {
        return;
    }
    
    // Check if handler is already attached to this element
    if (selector.dataset.clickHandlerAttached === 'true') {
        return;
    }
    
    // Use event delegation - attach one listener to the container
    selector.addEventListener('click', (e) => {
        // Find the closest game-card ancestor
        const card = e.target.closest('.game-card');
        if (!card) {
            return;
        }
        
        const gameId = card.dataset.gameId;
        if (!gameId) {
            console.warn('Game card clicked but no gameId found', card);
            return;
        }
        
        // Prevent navigation if clicking on interactive elements
        if (e.target.closest('a, button, input, select')) {
            return;
        }
        
        try {
            console.log('Navigating to game:', gameId);
            navigateToGameDetail(gameId);
        } catch (error) {
            console.error('Error navigating to game detail:', error, gameId);
        }
    });
    
    // Mark handler as attached on this element
    selector.dataset.clickHandlerAttached = 'true';
}

async function renderGamesList(games, append = false) {
    const selector = document.getElementById('gameSelector');
    if (!selector) {
        console.error('gameSelector container not found');
        return;
    }
    
    if (!append) {
        selector.innerHTML = '';
    }
    
    if (games.length === 0 && !append) {
        selector.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <p>No games with probability data found</p>
            </div>
        `;
        // Still attach handler in case games are added later
        attachGameCardClickHandler();
        return;
    }
    
    // Games endpoint now includes lightweight stats, so we can render immediately
    // For detailed stats, we'll fetch them on-demand or in bulk if needed
    const gamesHTML = games.map(game => renderGameCard(game)).join('');
    
    if (append) {
        selector.innerHTML += gamesHTML;
    } else {
        selector.innerHTML = gamesHTML;
    }
    
    // Attach click handler using event delegation (only once, survives innerHTML changes)
    attachGameCardClickHandler();
}

function updateGameHeader(meta) {
    document.getElementById('homeAbbr').textContent = meta.home_team_abbr;
    document.getElementById('homeName').textContent = meta.home_team_name;
    document.getElementById('homeScore').textContent = meta.final_home_score;
    document.getElementById('awayAbbr').textContent = meta.away_team_abbr;
    document.getElementById('awayName').textContent = meta.away_team_name;
    document.getElementById('awayScore').textContent = meta.final_away_score;
    
    // Style based on winner
    const homeScoreEl = document.getElementById('homeScore');
    const awayScoreEl = document.getElementById('awayScore');
    homeScoreEl.style.color = meta.home_won ? '#00d4aa' : '#888899';
    awayScoreEl.style.color = !meta.home_won ? '#ff6b6b' : '#888899';
    
    // Show/hide Kalshi link
    const kalshiLink = document.getElementById('kalshiLink');
    if (meta.kalshi_url) {
        kalshiLink.href = meta.kalshi_url;
        kalshiLink.style.display = 'block';
        kalshiLink.addEventListener('mouseenter', () => {
            kalshiLink.style.opacity = '1';
        });
        kalshiLink.addEventListener('mouseleave', () => {
            kalshiLink.style.opacity = '0.8';
        });
    } else {
        kalshiLink.style.display = 'none';
    }
    
    // Show/hide simulation section (only if game has Kalshi data)
    const simSection = document.getElementById('simulationSection');
    if (simSection) {
        if (meta.kalshi_url || meta.has_kalshi) {
            simSection.style.display = 'block';
        } else {
            simSection.style.display = 'none';
        }
    }
}

function updateChartLegend(meta, kalshiSeries) {
    const legendHtml = [];
    // ESPN Home team - use actual home color from meta
    legendHtml.push(`
        <div class="legend-item">
            <div class="legend-line" style="background: ${meta.home_color};"></div>
            <span class="legend-text">${meta.home_team_abbr} Win %</span>
            <span class="legend-source">(ESPN)</span>
        </div>
        <div class="legend-item">
            <div class="legend-line" style="background: #ff6b6b;"></div>
            <span class="legend-text">${meta.away_team_abbr} Win %</span>
            <span class="legend-source">(ESPN)</span>
        </div>
    `);
    
    // Add Kalshi series to legend
    kalshiSeries.forEach(({ teamName, isHomeTeam, color }) => {
        const displayName = teamName.length > 15 ? teamName.substring(0, 15) + '...' : teamName;
        const borderStyle = isHomeTeam ? 'none' : '2px dotted';
        legendHtml.push(`
            <div class="legend-item">
                <div class="legend-line" style="background: ${color}; border-bottom: ${borderStyle};"></div>
                <span class="legend-text">${displayName}</span>
                <span class="legend-source">(Kalshi)</span>
            </div>
        `);
    });
    
    document.getElementById('chartLegend').innerHTML = legendHtml.join('');
}

async function loadMoreGames() {
    if (isLoading || !hasMoreGames) return;
    
    isLoading = true;
    const loadingIndicator = document.getElementById('loadingMoreIndicator');
    if (loadingIndicator) {
        loadingIndicator.classList.add('loading');
    }
    
    try {
        const filters = getFilters();
        const response = await loadGames(currentOffset, 50, filters);
        await renderGamesList(response.games, true); // append = true
        currentOffset += response.games.length;
        hasMoreGames = response.has_more;
    } catch (error) {
        console.error('Failed to load more games:', error);
    } finally {
        isLoading = false;
        if (loadingIndicator) {
            loadingIndicator.classList.remove('loading');
        }
    }
}

// Setup infinite scroll
function setupInfiniteScroll() {
    const gameSelector = document.getElementById('gameSelector');
    if (!gameSelector) return;
    
    gameSelector.addEventListener('scroll', () => {
        const { scrollTop, scrollHeight, clientHeight } = gameSelector;
        // Load more when user is 200px from bottom
        if (scrollHeight - scrollTop - clientHeight < 200) {
            loadMoreGames();
        }
    });
}

// Check for new games and update badge
async function checkNewGames() {
    try {
        const response = await fetch('/api/update/check-new-games');
        if (!response.ok) throw new Error('Failed to check new games');
        const data = await response.json();
        
        const badge = document.getElementById('newGamesBadge');
        if (badge) {
            // Use total_new which includes both ESPN games and Kalshi candlesticks
            const count = data.total_new || data.new_kalshi_candlesticks || 0;
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
        
        return data;
    } catch (error) {
        console.error('Error checking new games:', error);
        return { total_new: 0, new_kalshi_candlesticks: 0, has_new_data: false };
    }
}

// WebSocket connection for update status
let updateStatusWebSocket = null;
let updateStatusWasRunning = false; // Track if update was running to detect completion

/**
 * Connect to WebSocket for update status updates.
 * 
 * Design Pattern: WebSocket Handler Pattern
 * Algorithm: O(1) connection, O(1) per update
 * Big O: O(1) for connection operations, O(1) for message handling
 * 
 * @returns {WebSocket} WebSocket connection (can be used to disconnect)
 */
function connectUpdateStatusWebSocket() {
    // Don't create multiple connections
    if (updateStatusWebSocket && updateStatusWebSocket.readyState === WebSocket.OPEN) {
        console.log('Update status WebSocket already connected');
        return updateStatusWebSocket;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/update/status`;
    
    console.log(`Connecting to update status WebSocket: ${url}`);
    
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
        console.log('Update status WebSocket connected');
    };
    
    ws.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'status') {
                handleUpdateStatusChange(data.is_running, data.message);
            } else if (data.type === 'error') {
                console.error('Update status WebSocket error:', data.message);
                // Fallback to HTTP check
                const status = await checkUpdateStatusApi();
                handleUpdateStatusChange(status.is_running, status.message);
            } else if (data.type === 'pong') {
                // Connection health check response
                // No action needed
            }
        } catch (error) {
            console.error('Error parsing update status WebSocket message:', error, event.data);
        }
    };
    
    ws.onerror = async (error) => {
        console.error('Update status WebSocket error:', error);
        // Fallback: try HTTP endpoint once
        try {
            const status = await checkUpdateStatusApi();
            handleUpdateStatusChange(status.is_running, status.message);
        } catch (err) {
            console.error('Fallback HTTP request also failed:', err);
        }
    };
    
    ws.onclose = (event) => {
        console.log('Update status WebSocket closed:', event.code, event.reason);
        updateStatusWebSocket = null;
        // Optionally reconnect if update is still running
        // For now, just log the closure
    };
    
    // Send ping every 30 seconds to keep connection alive
    const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
        } else {
            clearInterval(pingInterval);
        }
    }, 30000);
    
    // Clean up ping interval when connection closes
    ws.addEventListener('close', () => {
        clearInterval(pingInterval);
    });
    
    updateStatusWebSocket = ws;
    return ws;
}

/**
 * Handle update status change from WebSocket or HTTP.
 * 
 * @param {boolean} isRunning - Whether update is currently running
 * @param {string} message - Status message
 */
async function handleUpdateStatusChange(isRunning, message) {
    const updateBtn = document.getElementById('updateDataBtn');
    const statusEl = document.getElementById('updateStatus');
    const btnText = updateBtn?.querySelector('.nav-text');
    
    if (!updateBtn || !statusEl) {
        return;
    }
    
    if (isRunning) {
        // Update is in progress
        updateBtn.disabled = true;
        updateBtn.classList.add('updating');
        if (btnText) btnText.textContent = 'Updating...';
        statusEl.textContent = message || 'Update in progress. This may take several minutes.';
        statusEl.style.display = 'block';
        updateStatusWasRunning = true;
    } else {
        // Update is complete
        const wasRunning = updateStatusWasRunning;
        updateStatusWasRunning = false;
        
        updateBtn.disabled = false;
        updateBtn.classList.remove('updating');
        if (btnText) btnText.textContent = 'Refetch';
        
        // Refresh data when update completes (if it was running)
        if (wasRunning) {
            // Refresh without starting new polling
            const filters = getFilters();
            const response = await loadGames(0, 50, filters);
            await renderGamesList(response.games, false);
            currentOffset = response.games.length;
            hasMoreGames = response.has_more;
            setupInfiniteScroll();
            await checkNewGames();
        }
        
        statusEl.textContent = 'Update complete.';
        setTimeout(() => {
            statusEl.textContent = '';
            statusEl.style.display = 'none';
        }, 3000);
    }
}

/**
 * Check update status (HTTP fallback or initial check).
 * 
 * @returns {Promise<Object>} Status object with is_running and message
 */
async function checkUpdateStatus() {
    try {
        const status = await checkUpdateStatusApi();
        await handleUpdateStatusChange(status.is_running, status.message);
        return status;
    } catch (error) {
        console.error('Error checking update status:', error);
        return { is_running: false, message: 'Error checking status' };
    }
}

/**
 * Disconnect update status WebSocket.
 */
function disconnectUpdateStatusWebSocket() {
    if (updateStatusWebSocket) {
        updateStatusWebSocket.close();
        updateStatusWebSocket = null;
    }
}

// Trigger data update
async function triggerDataUpdate() {
    const updateBtn = document.getElementById('updateDataBtn');
    const statusEl = document.getElementById('updateStatus');
    const btnText = updateBtn?.querySelector('.nav-text');
    
    if (!updateBtn || !statusEl) return;
    
    // Disable button and show loading immediately
    updateBtn.disabled = true;
    updateBtn.classList.add('updating');
    if (btnText) btnText.textContent = 'Updating...';
    statusEl.textContent = 'Starting update...';
    statusEl.style.display = 'block';
    
    try {
        const data = await triggerUpdateApi();
        statusEl.textContent = data.message || 'Update started. This may take several minutes.';
        
        // Connect to WebSocket for real-time status updates
        connectUpdateStatusWebSocket();
        
    } catch (error) {
        console.error('Error triggering update:', error);
        statusEl.textContent = 'Error: ' + error.message;
        updateBtn.disabled = false;
        updateBtn.classList.remove('updating');
        if (btnText) btnText.textContent = 'Refetch';
        
        // If it's a 409 (already running), connect to WebSocket
        if (error.message.includes('409') || error.message.includes('already running')) {
            connectUpdateStatusWebSocket();
        }
    }
}

async function initializeGamesList() {
    currentOffset = 0;
    hasMoreGames = true;
    isLoading = false;
    
    try {
        const filters = getFilters();
        const response = await loadGames(0, 50, filters);
        await renderGamesList(response.games, false); // append = false
        currentOffset = response.games.length;
        hasMoreGames = response.has_more;
        setupInfiniteScroll();
        
        // Check for new games
        checkNewGames();
        
        // Check update status once on page load, then connect WebSocket if update is running
        checkUpdateStatus().then((status) => {
            // If update is running, connect to WebSocket for real-time updates
            if (status.is_running) {
                connectUpdateStatusWebSocket();
            }
        });
    } catch (error) {
        console.error('Failed to load games:', error);
        const selector = document.getElementById('gameSelector');
        selector.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>Failed to load games</p>
            </div>
        `;
    }
}

function renderGameStats(stats) {
    const statsGrid = document.getElementById('statsGrid');
    const statsSection = document.getElementById('statsSection');
    
    if (!stats || !statsGrid) return;
    
    statsSection.style.display = 'block';
    
    let html = '';
    
    // ESPN Stats
    if (stats.espn) {
        const e = stats.espn;
        html += `
            <div class="stats-group">
                <div class="stats-group-title">ESPN Metrics</div>
                <div class="stat-row">
                    <span class="stat-row-label">Data Points</span>
                    <span class="stat-row-value">${e.data_points || 0}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Min Probability</span>
                    <span class="stat-row-value">${e.min_probability ? (e.min_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Max Probability</span>
                    <span class="stat-row-value">${e.max_probability ? (e.max_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Mean Probability</span>
                    <span class="stat-row-value">${e.mean_probability ? (e.mean_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Final Probability</span>
                    <span class="stat-row-value">${e.final_probability ? (e.final_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Volatility</span>
                    <span class="stat-row-value">${(e.volatility * 100).toFixed(2)}%</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Lead Changes</span>
                    <span class="stat-row-value">${e.lead_changes || 0}</span>
                </div>
                ${e.max_swing ? `
                <div class="stat-row">
                    <span class="stat-row-label">Max Swing</span>
                    <span class="stat-row-value">${(e.max_swing.max_swing * 100).toFixed(1)}%</span>
                </div>
                ` : ''}
                <div class="stat-row">
                    <span class="stat-row-label">Std Deviation</span>
                    <span class="stat-row-value">${e.standard_deviation ? (e.standard_deviation * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Variance</span>
                    <span class="stat-row-value">${e.variance ? (e.variance * 10000).toFixed(4) : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Mean Abs Dev</span>
                    <span class="stat-row-value">${e.mean_absolute_deviation ? (e.mean_absolute_deviation * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                ${e.coefficient_of_variation !== null && e.coefficient_of_variation !== undefined ? `
                <div class="stat-row">
                    <span class="stat-row-label">Coeff of Variation</span>
                    <span class="stat-row-value">${e.coefficient_of_variation.toFixed(3)}</span>
                </div>
                ` : ''}
                ${e.time_averaged_in_game_brier_error !== null && e.time_averaged_in_game_brier_error !== undefined ? `
                <div class="stat-row">
                    <span class="stat-row-label">Time-Averaged In-Game Brier Error</span>
                    <span class="stat-row-value">${e.time_averaged_in_game_brier_error.toFixed(4)}</span>
                </div>
                ` : ''}
                ${e.log_loss !== null && e.log_loss !== undefined ? `
                <div class="stat-row">
                    <span class="stat-row-label">Log Loss</span>
                    <span class="stat-row-value">${e.log_loss.toFixed(4)}</span>
                </div>
                ` : ''}
                ${e.prediction_correct !== null && e.prediction_correct !== undefined ? `
                <div class="stat-row">
                    <span class="stat-row-label">Prediction Correct</span>
                    <span class="stat-row-value">${e.prediction_correct ? '✓' : '✗'}</span>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    // Kalshi Stats
    if (stats.kalshi) {
        const k = stats.kalshi;
        html += `
            <div class="stats-group">
                <div class="stats-group-title">Kalshi Metrics</div>
                <div class="stat-row">
                    <span class="stat-row-label">Data Points</span>
                    <span class="stat-row-value">${k.data_points || 0}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Min Probability</span>
                    <span class="stat-row-value">${k.min_probability ? (k.min_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Max Probability</span>
                    <span class="stat-row-value">${k.max_probability ? (k.max_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Mean Probability</span>
                    <span class="stat-row-value">${k.mean_probability ? (k.mean_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Final Probability</span>
                    <span class="stat-row-value">${k.final_probability ? (k.final_probability * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Volatility</span>
                    <span class="stat-row-value">${(k.volatility * 100).toFixed(2)}%</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Lead Changes</span>
                    <span class="stat-row-value">${k.lead_changes || 0}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Std Deviation</span>
                    <span class="stat-row-value">${k.standard_deviation ? (k.standard_deviation * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Variance</span>
                    <span class="stat-row-value">${k.variance ? (k.variance * 10000).toFixed(4) : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Mean Abs Dev</span>
                    <span class="stat-row-value">${k.mean_absolute_deviation ? (k.mean_absolute_deviation * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                ${k.coefficient_of_variation !== null && k.coefficient_of_variation !== undefined ? `
                <div class="stat-row">
                    <span class="stat-row-label">Coeff of Variation</span>
                    <span class="stat-row-value">${k.coefficient_of_variation.toFixed(3)}</span>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    // Divergence Stats
    if (stats.divergence && stats.divergence.data_points > 0) {
        const d = stats.divergence;
        html += `
            <div class="stats-group">
                <div class="stats-group-title">ESPN vs Kalshi</div>
                <div class="stat-row">
                    <span class="stat-row-label">Aligned Data Points</span>
                    <span class="stat-row-value">${d.data_points}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Mean Absolute Difference (ESPN vs Kalshi)${typeof createTooltip === 'function' ? createTooltip('Measures disagreement magnitude between sources, not correctness.') : ''}</span>
                    <span class="stat-row-value">${d.mean_absolute_difference ? (d.mean_absolute_difference * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Max Absolute Difference (ESPN vs Kalshi)${typeof createTooltip === 'function' ? createTooltip('Maximum disagreement between ESPN and Kalshi probabilities at any point in the game.') : ''}</span>
                    <span class="stat-row-value">${d.max_absolute_difference ? (d.max_absolute_difference * 100).toFixed(2) + '%' : d.max_absolute_error ? (d.max_absolute_error * 100).toFixed(2) + '%' : 'N/A'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-row-label">Correlation</span>
                    <span class="stat-row-value">${d.correlation ? d.correlation.toFixed(3) : 'N/A'}</span>
                </div>
            </div>
        `;
    }
    
    statsGrid.innerHTML = html;
}

