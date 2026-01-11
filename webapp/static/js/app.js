/**
 * Main application logic - game selection and data loading.
 * 
 * Design Pattern: Controller Pattern for coordinating modules
 * Algorithm: Async data loading and chart rendering
 * Big O: O(n + m) where n = ESPN points, m = Kalshi candles
 */

// Initialize game selector dropdown
let gameSelectorLoading = false;
async function initializeGameSelector(currentGameId = null) {
    const gameSelector = document.getElementById('gameSelector');
    if (!gameSelector) return;
    
    // Prevent concurrent loads
    if (gameSelectorLoading) return;
    
    try {
        gameSelectorLoading = true;
        
        // Load games list
        const gamesData = await loadGames(0, 200, { 
            season: '2025-26',
            has_kalshi: true,
            sort_by: 'date',
            sort_order: 'desc'
        });
        
        // Clear existing options
        gameSelector.innerHTML = '';
        
        // Add games to dropdown
        if (gamesData.games && gamesData.games.length > 0) {
            gamesData.games.forEach(game => {
                const option = document.createElement('option');
                option.value = game.game_id;
                
                // Format: "Away @ Home (Date)"
                // API returns: home_team_abbr, away_team_abbr, game_date
                const awayTeam = game.away_team_abbr || 'AWAY';
                const homeTeam = game.home_team_abbr || 'HOME';
                const date = game.game_date ? new Date(game.game_date).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric'
                }) : '';
                const label = `${awayTeam} @ ${homeTeam}${date ? ` (${date})` : ''}`;
                option.textContent = label;
                
                // Select current game if provided
                if (currentGameId && game.game_id === currentGameId) {
                    option.selected = true;
                }
                
                gameSelector.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No games available';
            gameSelector.appendChild(option);
        }
        
        // Handle selection change (add listener each time since element is recreated)
        gameSelector.addEventListener('change', (e) => {
            const selectedGameId = e.target.value;
            if (selectedGameId) {
                navigateToGameDetail(selectedGameId);
            }
        });
    } catch (error) {
        console.error('Error loading games for selector:', error);
        gameSelector.innerHTML = '<option value="">Error loading games</option>';
    } finally {
        gameSelectorLoading = false;
    }
}

async function selectGame(gameId) {
    if (AppState.selectedGameId === gameId && AppState.chart) return;
    AppState.selectedGameId = gameId;
    
    // Show loading indicator and hide chart content
    const loadingIndicator = document.getElementById('gameDetailLoading');
    const chartSection = document.getElementById('chartSection');
    if (loadingIndicator && chartSection) {
        loadingIndicator.style.display = 'flex';
        // Hide chart content while loading
        const scoreHeader = document.getElementById('scoreHeader');
        const chartContainer = document.querySelector('.chart-container');
        const quarterLabels = document.querySelector('.quarter-labels');
        const chartControls = document.querySelector('.chart-controls');
        const chartLegend = document.getElementById('chartLegend');
        if (scoreHeader) scoreHeader.style.display = 'none';
        if (chartContainer) chartContainer.style.display = 'none';
        if (quarterLabels) quarterLabels.style.display = 'none';
        if (chartControls) chartControls.style.display = 'none';
        if (chartLegend) chartLegend.style.display = 'none';
    }
    
    // Initialize game selector with current game
    await initializeGameSelector(gameId);
    
    try {
        // Load metadata, probabilities, and stats in parallel
        const [meta, probsResponse, stats] = await Promise.all([
            getGameMetadata(gameId),
            getGameProbabilities(gameId),
            getGameStats(gameId).catch(() => null), // Don't fail if stats unavailable
        ]);
        
        // Update header
        updateGameHeader(meta);
        
        // Get ESPN data from response
        const espnData = probsResponse.espn || probsResponse;
        const kalshiData = probsResponse.kalshi || {};
        const kalshiValidation = probsResponse.kalshi_validation;
        
        // Log Kalshi matching validation with detailed checks
        if (kalshiValidation) {
            const validationLog = {
                gameId: kalshiValidation.game_id,
                marketsFound: kalshiValidation.markets_found,
                summary: kalshiValidation.summary,
                warnings: kalshiValidation.warnings || [],
                espnHome: meta.home_team_abbr,
                espnAway: meta.away_team_abbr,
            };
            
            console.log('Kalshi matching validation:', validationLog);
            
            // Display warnings prominently if any exist
            if (kalshiValidation.warnings && kalshiValidation.warnings.length > 0) {
                console.warn('⚠️ Kalshi matching warnings:', kalshiValidation.warnings);
            }
            
            // Validate that we have both home and away markets if expected
            if (kalshiValidation.summary) {
                const summary = kalshiValidation.summary;
                if (summary.home_markets === 0 || summary.away_markets === 0) {
                    console.warn(`⚠️ Missing markets: ${summary.home_markets} home, ${summary.away_markets} away`);
                }
                if (!summary.all_name_matches_valid) {
                    console.warn('⚠️ Some team name matches may be incorrect');
                }
            }
        }
        
        // Process ESPN data
        const homeData = deduplicateTimeSeries(
            filterValidDataPoints(espnData.map(p => ({
                time: p.time,
                value: p.home_prob * 100,
            })))
        );
        
        const awayData = deduplicateTimeSeries(
            filterValidDataPoints(espnData.map(p => ({
                time: p.time,
                value: p.away_prob * 100,
            })))
        );
        
        // Calculate time range from actual data for 50% reference line
        const minTime = Math.min(
            homeData.length > 0 ? homeData[0].time : Infinity,
            awayData.length > 0 ? awayData[0].time : Infinity
        );
        const maxTime = Math.max(
            homeData.length > 0 ? homeData[homeData.length - 1].time : -Infinity,
            awayData.length > 0 ? awayData[awayData.length - 1].time : -Infinity
        );
        
        console.log('Timestamp alignment:', {
            game_date: meta.game_date,
            game_start_timestamp: meta.game_start_timestamp,
            minTime: minTime !== Infinity ? minTime : null,
            maxTime: maxTime !== -Infinity ? maxTime : null,
            minTimeDate: minTime !== Infinity ? new Date(minTime * 1000).toISOString() : null,
            maxTimeDate: maxTime !== -Infinity ? new Date(maxTime * 1000).toISOString() : null
        });
        
        // Create/update chart
        const baseTimestamp = minTime !== Infinity ? minTime : (meta.game_start_timestamp || Math.floor(Date.now() / 1000));
        createChart(meta.home_color, baseTimestamp);
        
        // Add 50% reference line with actual data timestamps
        if (minTime !== Infinity && maxTime !== -Infinity) {
            const fiftyLine = AppState.chart.addLineSeries({
                color: 'rgba(255, 255, 255, 0.15)',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
            });
            fiftyLine.setData([
                { time: minTime, value: 50 },
                { time: maxTime, value: 50 },
            ]);
        }
        
        console.log('Chart data:', {
            originalEspnPoints: espnData.length,
            homeDataPoints: homeData.length,
            awayDataPoints: awayData.length,
            sampleHome: homeData[0],
            sampleAway: awayData[0],
            homeDataRange: homeData.length > 0 ? { min: homeData[0].time, max: homeData[homeData.length - 1].time } : null,
            timeRange: { min: minTime !== Infinity ? minTime : null, max: maxTime !== -Infinity ? maxTime : null },
        });
        
        if (homeData.length === 0 || awayData.length === 0) {
            console.error('No valid data points after filtering!', {
                espnDataSample: espnData.slice(0, 5),
                homeDataLength: homeData.length,
                awayDataLength: awayData.length,
            });
        }
        
        AppState.homeSeries.setData(homeData);
        AppState.awaySeries.setData(awayData);
        
        // Process and add Kalshi data
        const kalshiTickers = Object.keys(kalshiData);
        const kalshiSeriesForLegend = [];
        
        if (kalshiTickers.length > 0) {
            for (const ticker of kalshiTickers) {
                const market = kalshiData[ticker];
                const data = market.data || [];
                
                if (data.length > 0) {
                    // Use team_side from backend (more reliable than name matching)
                    const teamName = market.team || '';
                    const teamSide = market.team_side; // 'home' or 'away'
                    const isHomeTeam = teamSide === 'home';
                    
                    // Add Kalshi series to chart (store ticker for resolution updates)
                    const kalshiSeriesInfo = addKalshiSeries(teamName, isHomeTeam, meta.home_color, ticker);
                    kalshiSeriesForLegend.push({
                        teamName,
                        isHomeTeam,
                        color: kalshiSeriesInfo.color,
                    });
                    
                    // Format Kalshi data
                    const kalshiChartData = deduplicateTimeSeries(
                        filterValidDataPoints(data.map(d => ({
                            time: d.time,
                            value: d.price,
                        })))
                    );
                    
                    if (kalshiChartData.length > 0) {
                        kalshiSeriesInfo.series.setData(kalshiChartData);
                    }
                }
            }
        }
        
        // Update legend
        updateChartLegend(meta, kalshiSeriesForLegend);
        
        // Setup toggle handlers
        setupChartToggles();
        
        // Setup resolution selector handler
        setupResolutionSelector(gameId);
        
        // Fit content
        AppState.chart.timeScale().fitContent();
        
        // Display stats if available
        if (stats) {
            renderGameStats(stats);
        }
        
        // Initialize simulation functionality
        if (typeof window.initializeGameSimulation === 'function') {
            window.initializeGameSimulation(gameId);
        }
        
        // Hide loading indicator and show chart content
        if (loadingIndicator && chartSection) {
            loadingIndicator.style.display = 'none';
            const scoreHeader = document.getElementById('scoreHeader');
            const chartContainer = document.querySelector('.chart-container');
            const quarterLabels = document.querySelector('.quarter-labels');
            const chartControls = document.querySelector('.chart-controls');
            const chartLegend = document.getElementById('chartLegend');
            if (scoreHeader) scoreHeader.style.display = '';
            if (chartContainer) chartContainer.style.display = '';
            if (quarterLabels) quarterLabels.style.display = '';
            if (chartControls) chartControls.style.display = '';
            if (chartLegend) chartLegend.style.display = '';
        }
        
    } catch (error) {
        console.error('Failed to load game data:', error);
        // Hide loading indicator even on error
        if (loadingIndicator && chartSection) {
            loadingIndicator.style.display = 'none';
            const scoreHeader = document.getElementById('scoreHeader');
            const chartContainer = document.querySelector('.chart-container');
            const quarterLabels = document.querySelector('.quarter-labels');
            const chartControls = document.querySelector('.chart-controls');
            const chartLegend = document.getElementById('chartLegend');
            if (scoreHeader) scoreHeader.style.display = '';
            if (chartContainer) chartContainer.style.display = '';
            if (quarterLabels) quarterLabels.style.display = '';
            if (chartControls) chartControls.style.display = '';
            if (chartLegend) chartLegend.style.display = '';
        }
    }
}

// Initialize app
/**
 * Clear games cache (hard reset)
 */
async function clearGamesCache() {
    const btn = document.getElementById('clearCacheBtn');
    if (!btn) return;
    
    // Disable button during operation
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Clearing...';
    
    try {
        const result = await clearGamesCacheApi();
        btn.textContent = '✓ Cleared!';
        btn.style.color = 'var(--accent-home)';
        
        // Show success message
        if (result.message) {
            console.log(`[CACHE] ${result.message}`);
        }
        
        // Reset button after 2 seconds
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '';
            btn.disabled = false;
        }, 2000);
    } catch (error) {
        console.error('[CACHE] Error clearing cache:', error);
        btn.textContent = '✗ Error';
        btn.style.color = 'var(--accent-away)';
        
        // Reset button after 3 seconds
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '';
            btn.disabled = false;
        }, 3000);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Check initial route and load appropriate template
    const route = getRoute();
    if (route.view === 'live-detail' && route.gameId) {
        // We're on a live game detail page
        await showLiveGameDetailView(route.gameId);
    } else if (route.view === 'live-list') {
        // We're on the live games list page
        await showLiveGamesListView();
    } else if (route.view === 'detail' && route.gameId) {
        // We're on a game detail page, load games first then show the game
        // Note: showGameListView() already calls initializeGamesList() internally
        await showGameListView();
        await showGameDetailView(route.gameId);
    } else if (route.view === 'stats') {
        // We're on the stats page
        await showStatsPageView();
    } else if (route.view === 'simulation') {
        // We're on the simulation page
        await showSimulationPageView();
    } else {
        // We're on the list view
        // Note: showGameListView() already calls initializeGamesList() internally
        await showGameListView();
    }
});

