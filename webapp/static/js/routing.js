/**
 * URL routing module.
 * 
 * Design Pattern: Router Pattern for client-side navigation
 * Algorithm: Hash-based routing
 * Big O: O(1) for route operations
 */

function getRoute() {
    const hash = window.location.hash.slice(1); // Remove #
    if (hash.startsWith('/live/')) {
        const parts = hash.split('/live/');
        if (parts.length > 1 && parts[1]) {
            return { view: 'live-detail', gameId: parts[1] };
        }
        return { view: 'live-list', gameId: null };
    }
    if (hash === '/live') {
        return { view: 'live-list', gameId: null };
    }
    if (hash.startsWith('/game/')) {
        const gameId = hash.split('/game/')[1];
        return { view: 'detail', gameId };
    }
    if (hash === '/stats' || hash.startsWith('/stats')) {
        return { view: 'stats', gameId: null };
    }
    if (hash === '/simulation' || hash.startsWith('/simulation')) {
        return { view: 'simulation', gameId: null };
    }
    return { view: 'list', gameId: null };
}

function navigateToGameList() {
    window.location.hash = '';
    showGameListView();
}

function navigateToGameDetail(gameId) {
    if (!gameId) {
        console.error('navigateToGameDetail called with invalid gameId:', gameId);
        return;
    }
    
    // Validate gameId format (should be numeric string)
    if (typeof gameId !== 'string' || !/^\d+$/.test(gameId)) {
        console.error('Invalid gameId format:', gameId);
        return;
    }
    
    try {
        window.location.hash = `/game/${gameId}`;
        showGameDetailView(gameId);
    } catch (error) {
        console.error('Error in navigateToGameDetail:', error, gameId);
    }
}

function navigateToStatsPage() {
    window.location.hash = '/stats';
    showStatsPageView();
}

function navigateToSimulationPage() {
    window.location.hash = '/simulation';
    showSimulationPageView();
}

function navigateToLiveGamesList() {
    window.location.hash = '/live';
    showLiveGamesListView();
}

function navigateToLiveGameDetail(gameId) {
    window.location.hash = `/live/${gameId}`;
    showLiveGameDetailView(gameId);
}

async function showGameListView() {
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('game-list', viewsContainer);
    
    // Show the view (template might have display: none)
    const gameListView = document.getElementById('gameListView');
    if (gameListView) {
        gameListView.style.display = 'block';
        console.log('Game list view shown');
    } else {
        console.error('gameListView element not found after template render');
    }
    
    AppState.selectedGameId = null;
    
    // Wait a moment for DOM to be ready, then initialize
    await new Promise(resolve => {
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Re-initialize filters after template loads
                if (typeof setupFilters === 'function') {
                    setupFilters();
                }
                // Load games list (this will hit the games endpoint)
                if (typeof initializeGamesList === 'function') {
                    initializeGamesList();
                }
                resolve();
            }, 10);
        });
    });
}

async function showGameDetailView(gameId) {
    const viewsContainer = document.getElementById('app-views');
    await renderTemplate('game-detail', viewsContainer);
    
    // Show the view (template might have display: none)
    const gameDetailView = document.getElementById('gameDetailView');
    if (gameDetailView) {
        gameDetailView.style.display = 'block';
    }
    
    // Show loading indicator immediately
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
    
    // Wait for DOM to be ready and ensure elements exist
    await new Promise(resolve => {
        // Use requestAnimationFrame to ensure DOM is fully rendered
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Verify critical elements exist before proceeding
                const chartEl = document.getElementById('chart');
                if (chartEl) {
                    selectGame(gameId);
                } else {
                    console.error('Chart element not found after template load');
                    // Hide loading indicator if chart element not found
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'none';
                    }
                }
                resolve();
            }, 10);
        });
    });
}

async function showStatsPageView() {
    const viewsContainer = document.getElementById('app-views');
    await renderTemplate('aggregate-stats', viewsContainer);
    
    // Show the view (template might have display: none)
    const statsPageView = document.getElementById('statsPageView');
    if (statsPageView) {
        statsPageView.style.display = 'block';
    }
    
    // Wait for DOM to be ready and ensure elements exist
    await new Promise(resolve => {
        // Use requestAnimationFrame to ensure DOM is fully rendered
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Verify container exists before proceeding
                const container = document.getElementById('aggregateStatsContainer');
                if (container) {
                    loadAggregateStats();
                } else {
                    console.error('Aggregate stats container not found after template load');
                }
                resolve();
            }, 10);
        });
    });
}

async function showLiveGamesListView() {
    // Stop live game WebSocket if active
    if (typeof cleanupLiveGame === 'function') {
        cleanupLiveGame();
    }
    
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('live-games-list', viewsContainer);
    
    // Show the view (template might have display: none)
    const liveGamesListView = document.getElementById('liveGamesListView');
    if (liveGamesListView) {
        liveGamesListView.style.display = 'block';
        console.log('Live games list view shown');
    } else {
        console.error('liveGamesListView element not found after template render');
    }
    
    AppState.selectedGameId = null;
    
    // Wait a moment for DOM to be ready, then initialize
    await new Promise(resolve => {
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Initialize live games list
                if (typeof initializeLiveGamesList === 'function') {
                    initializeLiveGamesList();
                }
                resolve();
            }, 10);
        });
    });
}

async function showSimulationPageView() {
    // Stop any active refresh polling from stats page
    if (typeof stopRefreshPolling === 'function') {
        stopRefreshPolling();
    }
    if (typeof hideRefreshIndicator === 'function') {
        hideRefreshIndicator();
    }
    
    // Stop live game WebSocket if active
    if (typeof cleanupLiveGame === 'function') {
        cleanupLiveGame();
    }
    
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('simulation', viewsContainer);
    
    // Show the view (template might have display: none)
    const simulationView = document.getElementById('simulationView');
    if (simulationView) {
        simulationView.style.display = 'block';
        console.log('Simulation view shown');
    } else {
        console.error('simulationView element not found after template render');
    }
    
    // Wait a moment for DOM to be ready, then initialize
    await new Promise(resolve => {
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Initialize simulation page
                if (typeof initializeSimulationPage === 'function') {
                    initializeSimulationPage();
                }
                resolve();
            }, 10);
        });
    });
}

async function showLiveGameDetailView(gameId) {
    // Stop live games list auto-refresh
    if (typeof stopLiveGamesAutoRefresh === 'function') {
        stopLiveGamesAutoRefresh();
    }
    
    // Cleanup any existing live game (in case switching between live games)
    if (typeof cleanupLiveGame === 'function') {
        cleanupLiveGame();
    }
    
    const viewsContainer = document.getElementById('app-views');
    await renderTemplate('live-game-detail', viewsContainer);
    
    // Show the view (template might have display: none)
    const liveGameDetailView = document.getElementById('liveGameDetailView');
    if (liveGameDetailView) {
        liveGameDetailView.style.display = 'block';
    }
    
    // Wait for DOM to be ready and ensure elements exist
    await new Promise(resolve => {
        requestAnimationFrame(() => {
            setTimeout(() => {
                // Verify critical elements exist before proceeding
                const chartEl = document.getElementById('chart');
                if (chartEl) {
                    if (typeof showLiveGameDetail === 'function') {
                        showLiveGameDetail(gameId);
                    }
                } else {
                    console.error('Chart element not found after template load');
                }
                resolve();
            }, 10);
        });
    });
}

// Track previous route for cleanup
let previousRoute = null;

// Handle browser back/forward buttons
window.addEventListener('hashchange', async () => {
    const route = getRoute();
    
    // Cleanup live game if leaving live game detail
    if (previousRoute && previousRoute.view === 'live-detail' && route.view !== 'live-detail') {
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
    }
    
    if (route.view === 'live-detail' && route.gameId) {
        await showLiveGameDetailView(route.gameId);
    } else if (route.view === 'live-list') {
        await showLiveGamesListView();
    } else if (route.view === 'detail' && route.gameId) {
        // Cleanup live game when navigating to historical game detail
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        await showGameDetailView(route.gameId);
    } else if (route.view === 'stats') {
        // Cleanup live game when navigating to stats
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        await showStatsPageView();
    } else if (route.view === 'simulation') {
        // Cleanup live game when navigating to simulation
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        await showSimulationPageView();
    } else {
        // Cleanup live game when navigating to other views
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        await showGameListView();
    }
    
    previousRoute = route;
});

