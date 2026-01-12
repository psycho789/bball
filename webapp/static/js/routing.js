/**
 * URL routing module.
 * 
 * Design Pattern: Router Pattern for client-side navigation
 * Algorithm: Hash-based routing
 * Big O: O(1) for route operations
 */

/**
 * Update active navigation link based on current route
 */
function updateActiveNav() {
    const route = getRoute();
    const navLinks = document.querySelectorAll('.nav-link[data-route]');
    
    navLinks.forEach(link => {
        const linkRoute = link.getAttribute('data-route');
        // Map route views to nav link routes
        let activeRoute = null;
        
        if (route.view === 'list' || route.view === 'detail') {
            activeRoute = 'list';
        } else if (route.view === 'live-list' || route.view === 'live-detail') {
            activeRoute = 'live-list';
        } else if (route.view === 'stats') {
            activeRoute = 'stats';
        } else if (route.view === 'simulation') {
            activeRoute = 'simulation';
        } else if (route.view === 'grid-search') {
            activeRoute = 'grid-search';
        } else if (route.view === 'logging') {
            activeRoute = 'logging';
        } else if (route.view === 'model-comparison') {
            activeRoute = 'model-comparison';
        } else if (route.view === 'grid-search-comparison') {
            activeRoute = 'grid-search-comparison';
        }
        
        if (linkRoute === activeRoute) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

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
    // Check grid-search-comparison BEFORE grid-search (since it starts with /grid-search)
    if (hash === '/grid-search-comparison' || hash.startsWith('/grid-search-comparison')) {
        return { view: 'grid-search-comparison', gameId: null };
    }
    if (hash === '/grid-search' || hash.startsWith('/grid-search')) {
        return { view: 'grid-search', gameId: null };
    }
    if (hash === '/logging' || hash.startsWith('/logging')) {
        return { view: 'logging', gameId: null };
    }
    if (hash === '/model-comparison' || hash.startsWith('/model-comparison')) {
        return { view: 'model-comparison', gameId: null };
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

function navigateToGridSearchPage() {
    window.location.hash = '/grid-search';
    showGridSearchPageView();
}

function navigateToLoggingPage() {
    window.location.hash = '/logging';
    showLoggingPageView();
}

function navigateToModelComparisonPage() {
    window.location.hash = '/model-comparison';
    showModelComparisonPageView();
}

function navigateToGridSearchComparisonPage() {
    window.location.hash = '/grid-search-comparison';
    showGridSearchComparisonPageView();
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
    updateActiveNav();
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
    updateActiveNav();
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
    updateActiveNav();
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

async function showModelComparisonPageView() {
    updateActiveNav();
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('model-comparison', viewsContainer);
    
    // Show the view
    const modelComparisonView = document.getElementById('modelComparisonPageView');
    if (modelComparisonView) {
        modelComparisonView.style.display = 'block';
    }
    
    // Load model comparison data
    if (typeof loadModelComparison === 'function') {
        await loadModelComparison();
    } else {
        console.error('loadModelComparison function not found');
    }
}

async function showGridSearchPageView() {
    updateActiveNav();
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('grid-search', viewsContainer);
    
    // Show the view
    const gridSearchView = document.getElementById('gridSearchView');
    if (gridSearchView) {
        gridSearchView.style.display = 'block';
    }
    
    // Initialize page after template renders
    // Wait for script to load and DOM to be ready
    await new Promise(resolve => {
        // Check if script has loaded and function exists
        const checkFunction = () => {
            if (typeof initializeGridSearchPage === 'function') {
                console.log('[Routing] initializeGridSearchPage function found, calling...');
                initializeGridSearchPage();
                resolve();
            } else {
                console.log('[Routing] initializeGridSearchPage not found yet, retrying...');
                setTimeout(checkFunction, 50);
            }
        };
        
        // Start checking after a short delay to allow script to load
        setTimeout(checkFunction, 100);
        
        // Timeout after 2 seconds if function never appears
        setTimeout(() => {
            if (typeof initializeGridSearchPage !== 'function') {
                console.error('[Routing] initializeGridSearchPage function not found after 2 seconds');
                resolve();
            }
        }, 2000);
    });
}

async function showGridSearchComparisonPageView() {
    const viewsContainer = document.getElementById('app-views');
    if (!viewsContainer) {
        console.error('app-views container not found');
        return;
    }
    
    await renderTemplate('grid-search-comparison', viewsContainer);
    
    // Show the view
    const comparisonView = document.getElementById('gridSearchComparisonView');
    if (comparisonView) {
        comparisonView.style.display = 'block';
    }
    
    // Update navigation highlighting AFTER template is rendered
    updateActiveNav();
    
    // Load comparison data
    if (typeof loadGridSearchComparison === 'function') {
        await loadGridSearchComparison();
    } else {
        console.error('loadGridSearchComparison function not found');
    }
}

async function showSimulationPageView() {
    updateActiveNav();
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
    
    // Stop logging auto-refresh if active
    if (typeof cleanupLoggingPage === 'function') {
        cleanupLoggingPage();
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

async function showLoggingPageView() {
    updateActiveNav();
    
    // Stop any active refresh polling from stats page
    if (typeof stopRefreshPolling === 'function') {
        stopRefreshPolling();
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
    
    await renderTemplate('logging', viewsContainer);
    
    // Show the view
    const loggingView = document.getElementById('loggingView');
    if (loggingView) {
        loggingView.style.display = 'block';
        console.log('Logging view shown');
    } else {
        console.error('loggingView element not found after template render');
    }
    
    // Initialize page after template renders
    await new Promise(resolve => {
        requestAnimationFrame(() => {
            setTimeout(() => {
                if (typeof initializeLoggingPage === 'function') {
                    initializeLoggingPage();
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
        // Cleanup logging when navigating to simulation
        if (typeof cleanupLoggingPage === 'function') {
            cleanupLoggingPage();
        }
        await showSimulationPageView();
    } else if (route.view === 'logging') {
        // Cleanup live game when navigating to logging
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        await showLoggingPageView();
    } else if (route.view === 'grid-search') {
        // Cleanup live game when navigating to grid search
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        // Cleanup logging when navigating to grid search
        if (typeof cleanupLoggingPage === 'function') {
            cleanupLoggingPage();
        }
        await showGridSearchPageView();
    } else if (route.view === 'model-comparison') {
        // Cleanup live game when navigating to model comparison
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        // Cleanup logging when navigating to model comparison
        if (typeof cleanupLoggingPage === 'function') {
            cleanupLoggingPage();
        }
        await showModelComparisonPageView();
    } else if (route.view === 'grid-search-comparison') {
        // Cleanup live game when navigating to grid search comparison
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        // Cleanup logging when navigating to grid search comparison
        if (typeof cleanupLoggingPage === 'function') {
            cleanupLoggingPage();
        }
        await showGridSearchComparisonPageView();
    } else {
        // Cleanup live game when navigating to other views
        if (typeof cleanupLiveGame === 'function') {
            cleanupLiveGame();
        }
        // Cleanup logging when navigating to other views
        if (typeof cleanupLoggingPage === 'function') {
            cleanupLoggingPage();
        }
        await showGameListView();
    }
    
    previousRoute = route;
    updateActiveNav();
});

