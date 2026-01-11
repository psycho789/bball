/**
 * Chart management module.
 * 
 * Design Pattern: Factory Pattern for chart creation
 * Algorithm: Lightweight Charts initialization and data management
 * Big O: O(n) where n = number of data points
 */

function setupChartToggles() {
    const espnToggle = document.getElementById('toggleESPN');
    const kalshiToggle = document.getElementById('toggleKalshi');
    const volumeToggle = document.getElementById('toggleVolume');
    
    if (!espnToggle || !kalshiToggle) return;
    
    // Remove existing listeners to avoid duplicates
    const newEspnToggle = espnToggle.cloneNode(true);
    const newKalshiToggle = kalshiToggle.cloneNode(true);
    espnToggle.parentNode.replaceChild(newEspnToggle, espnToggle);
    kalshiToggle.parentNode.replaceChild(newKalshiToggle, kalshiToggle);
    
    // ESPN toggle
    newEspnToggle.addEventListener('change', (e) => {
        const isVisible = e.target.checked;
        if (AppState.homeSeries) {
            AppState.homeSeries.applyOptions({ visible: isVisible });
        }
        if (AppState.awaySeries) {
            AppState.awaySeries.applyOptions({ visible: isVisible });
        }
    });
    
    // Kalshi toggle
    newKalshiToggle.addEventListener('change', (e) => {
        const isVisible = e.target.checked;
        AppState.kalshiSeries.forEach(({ series }) => {
            if (series) {
                series.applyOptions({ visible: isVisible });
            }
        });
    });
    
    // Volume toggle
    if (volumeToggle) {
        const newVolumeToggle = volumeToggle.cloneNode(true);
        volumeToggle.parentNode.replaceChild(newVolumeToggle, volumeToggle);
        newVolumeToggle.addEventListener('change', (e) => {
            const isVisible = e.target.checked;
            if (AppState.volumeSeries) {
                AppState.volumeSeries.forEach(series => {
                    if (series) {
                        series.applyOptions({ visible: isVisible });
                    }
                });
            }
        });
    }
}

function setupResolutionSelector(gameId) {
    const resolutionSelector = document.getElementById('candlestickResolution');
    if (!resolutionSelector) return;
    
    // Remove existing listener to avoid duplicates
    const newSelector = resolutionSelector.cloneNode(true);
    resolutionSelector.parentNode.replaceChild(newSelector, resolutionSelector);
    
    newSelector.addEventListener('change', async (e) => {
        const resolution = parseInt(e.target.value);
        await updateCandlestickResolution(gameId, resolution);
    });
}

async function updateCandlestickResolution(gameId, resolution) {
    if (!gameId || !AppState.kalshiSeries || AppState.kalshiSeries.length === 0) {
        return;
    }
    
    try {
        // Determine source based on resolution
        const source = resolution === 60 ? 'official' : 'trades';
        
        // Get zoom window if available (for 1-second resolution)
        const zoomWindow = getZoomWindow();
        
        let url = `/api/probabilities/${gameId}/kalshi-candles?interval_seconds=${resolution}&source=${source}`;
        if (zoomWindow && resolution === 1) {
            url += `&start_ts=${zoomWindow.start_ts}&end_ts=${zoomWindow.end_ts}`;
        }
        
        const response = await fetch(url);
        
        if (response.status === 400) {
            const error = await response.json().catch(() => ({}));
            if (error.error && error.error.includes('window too large')) {
                showUserMessage('Zoom in to use 1-second view');
                // Reset selector to previous value
                const selector = document.getElementById('candlestickResolution');
                if (selector) {
                    selector.value = '60'; // Default to 1 minute
                }
                return;
            }
        }
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Handle both single-ticker and multi-ticker responses
        let marketsData = [];
        if (data.candles && data.ticker) {
            // Single ticker response: {candles: [...], ticker: "...", team_side: "..."}
            marketsData = [{ 
                ticker: data.ticker, 
                candles: data.candles,
                team_side: data.team_side 
            }];
        } else if (data.markets && Array.isArray(data.markets)) {
            // Multi-ticker response: {markets: [{ticker: "...", team_side: "...", candles: [...]}, ...]}
            marketsData = data.markets;
        }
        
        if (marketsData.length === 0) {
            console.warn('No market data received from API');
            return;
        }
        
        console.log(`Updating ${marketsData.length} markets for resolution ${resolution}s`);
        
        // Update all Kalshi series with matching ticker data
        let volumeCandles = null;
        
        // Match markets to series by ticker or team_side
        for (const marketData of marketsData) {
            const ticker = marketData.ticker;
            const teamSide = marketData.team_side; // 'home' or 'away' from API
            const candles = marketData.candles || [];
            
            if (!candles || candles.length === 0) {
                continue;
            }
            
            // Find matching series by ticker (preferred, most reliable)
            let seriesInfo = AppState.kalshiSeries.find(s => s.ticker === ticker);
            
            // Fallback: match by team_side if ticker not found
            if (!seriesInfo || !seriesInfo.series) {
                if (teamSide) {
                    const isHomeTeam = teamSide === 'home';
                    seriesInfo = AppState.kalshiSeries.find(s => 
                        s.isHomeTeam === isHomeTeam && (!s.ticker || s.ticker !== ticker)
                    );
                }
            }
            
            // Last resort: match by position if we have same number of markets and series
            if (!seriesInfo || !seriesInfo.series) {
                if (AppState.kalshiSeries.length === marketsData.length) {
                    const marketIndex = marketsData.indexOf(marketData);
                    if (marketIndex < AppState.kalshiSeries.length) {
                        seriesInfo = AppState.kalshiSeries[marketIndex];
                    }
                }
            }
            
            if (!seriesInfo || !seriesInfo.series) {
                console.warn(`Could not find matching series for ticker ${ticker}, team_side ${teamSide}`);
                continue;
            }
            
            // Store ticker and team_side in series metadata if not already stored
            if (!seriesInfo.ticker) {
                seriesInfo.ticker = ticker;
            }
            if (teamSide && !seriesInfo.teamSide) {
                seriesInfo.teamSide = teamSide;
            }
            
            // Convert candles to chart format
            // Trade-derived candles use price_close_cents (integer 0-100, representing percentage)
            // Official candles use price_close (float 0-100)
            const chartData = candles.map(candle => {
                const time = candle.period_ts || candle.time;
                let value = 0;
                
                if (candle.price_close_cents !== undefined && candle.price_close_cents !== null) {
                    // Trade-derived: price_close_cents is already in 0-100 range (not 0-10000)
                    // It represents percentage directly (e.g., 80 = 80%)
                    value = candle.price_close_cents;
                } else if (candle.price_close !== undefined && candle.price_close !== null) {
                    // Official: already in 0-100 format
                    value = candle.price_close;
                }
                
                return { time, value };
            }).filter(d => d.time && d.value !== undefined && d.value !== null && !isNaN(d.value));
            
            // Sort chart data by time to ensure proper rendering
            chartData.sort((a, b) => a.time - b.time);
            
            // Remove duplicates by time (keep last value for same timestamp)
            const deduplicatedData = [];
            const timeMap = new Map();
            for (const point of chartData) {
                timeMap.set(point.time, point);
            }
            deduplicatedData.push(...Array.from(timeMap.values()).sort((a, b) => a.time - b.time));
            
            if (deduplicatedData.length > 0) {
                // Set data - Lightweight Charts handles updates efficiently
                seriesInfo.series.setData(deduplicatedData);
                console.log(`Updated ${ticker} (${teamSide}) with ${deduplicatedData.length} points`);
            } else {
                // Clear data if no new data available
                seriesInfo.series.setData([]);
                console.warn(`No data for ${ticker} (${teamSide})`);
            }
            
            // Collect candles for volume overlay (use first market's candles)
            if (!volumeCandles) {
                volumeCandles = candles;
            }
        }
        
        // Update volume overlay (function checks toggle internally)
        if (volumeCandles) {
            updateVolumeOverlay(volumeCandles);
        }
        
        // Fit content after a brief delay to ensure all data is set
        if (AppState.chart) {
            // Use requestAnimationFrame for smoother updates
            requestAnimationFrame(() => {
                if (AppState.chart) {
                    AppState.chart.timeScale().fitContent();
                }
            });
        }
    } catch (error) {
        console.error('Failed to update candlestick resolution:', error);
        showUserMessage('Failed to load candlestick data');
    }
}

function updateVolumeOverlay(candles) {
    if (!AppState.chart || !candles || candles.length === 0) {
        return;
    }
    
    // Check if volume toggle is enabled before creating/updating volume series
    const volumeToggle = document.getElementById('toggleVolume');
    if (!volumeToggle || !volumeToggle.checked) {
        // Don't create or update volume if toggle is off
        if (AppState.volumeSeries && AppState.volumeSeries.length > 0) {
            AppState.volumeSeries.forEach(series => {
                if (series) {
                    series.setData([]);
                }
            });
        }
        return;
    }
    
    // Create or update volume series
    if (!AppState.volumeSeries || AppState.volumeSeries.length === 0) {
        // Create histogram series for volume
        const volumeSeries = AppState.chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'volume',
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });
        
        AppState.volumeSeries = [volumeSeries];
        
        // Create separate price scale for volume
        AppState.chart.priceScale('volume').applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });
    }
    
    // Convert candles to volume format
    const volumeData = candles.map(candle => ({
        time: candle.period_ts || candle.time,
        value: candle.volume || 0,
        color: '#26a69a',
    }));
    
    if (AppState.volumeSeries[0]) {
        AppState.volumeSeries[0].setData(volumeData);
    }
}

function getZoomWindow() {
    // Get current zoom window from chart if available
    if (!AppState.chart) {
        return null;
    }
    
    try {
        const timeScale = AppState.chart.timeScale();
        const visibleRange = timeScale.getVisibleRange();
        
        if (visibleRange && visibleRange.from && visibleRange.to) {
            return {
                start_ts: Math.floor(visibleRange.from),
                end_ts: Math.floor(visibleRange.to),
            };
        }
    } catch (e) {
        // Chart not ready or no visible range
    }
    
    return null;
}

function showUserMessage(message) {
    // Simple user message display (can be enhanced with toast/notification)
    const messageEl = document.getElementById('userMessage');
    if (messageEl) {
        messageEl.textContent = message;
        messageEl.style.display = 'block';
        setTimeout(() => {
            messageEl.style.display = 'none';
        }, 5000);
    } else {
        // Fallback: use alert
        alert(message);
    }
}

function createChart(homeColor, baseTimestamp = null) {
    const container = document.getElementById('chart');
    container.innerHTML = '';
    
    // Clear previous Kalshi series references
    AppState.kalshiSeries = [];
    AppState.volumeSeries = [];
    
    // Store base timestamp for tick formatting
    AppState.chartBaseTimestamp = baseTimestamp;
    
    AppState.chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 500,
        layout: {
            background: { type: 'solid', color: '#0a0a0f' },
            textColor: '#888899',
        },
        grid: {
            vertLines: { color: '#1a1a2e' },
            horzLines: { color: '#1a1a2e' },
        },
        rightPriceScale: {
            borderColor: '#2a2a40',
            scaleMargins: {
                top: 0.05,
                bottom: 0.05,
            },
            autoScale: false,
        },
        timeScale: {
            borderColor: '#2a2a40',
            timeVisible: false,
            secondsVisible: false,
            rightOffset: 0,
            barSpacing: 0,
            fixLeftEdge: true,
            fixRightEdge: true,
            lockVisibleTimeRangeOnResize: true,
            allowShiftVisibleRangeOnWhitespaceClick: false,
            allowBoldLabels: false,
            tickMarkFormatter: (time, tickMarkType, locale) => {
                // time is a Unix timestamp, convert to elapsed seconds for display
                if (AppState.chartBaseTimestamp !== null) {
                    const elapsed = time - AppState.chartBaseTimestamp;
                    const quarter = Math.floor(elapsed / 720) + 1;
                    if (elapsed % 720 === 0 && quarter <= 4) {
                        return `Q${quarter}`;
                    }
                }
                return '';
            },
        },
        handleScroll: {
            mouseWheel: false,
            pressedMouseMove: false,
            horzTouchDrag: false,
            vertTouchDrag: false,
        },
        handleScale: {
            axisPressedMouseMove: false,
            axisDoubleClickReset: false,
            axisTouchDrag: false,
            mouseWheel: false,
            pinch: false,
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: '#7c3aed',
                labelBackgroundColor: '#7c3aed',
            },
            horzLine: {
                color: '#7c3aed',
                labelBackgroundColor: '#7c3aed',
            },
        },
    });
    
    // ESPN Home team line (primary)
    AppState.homeSeries = AppState.chart.addLineSeries({
        color: homeColor,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 6,
        crosshairMarkerBackgroundColor: homeColor,
    });
    
    // ESPN Away team line (secondary)
    AppState.awaySeries = AppState.chart.addLineSeries({
        color: '#ff6b6b',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 6,
        crosshairMarkerBackgroundColor: '#ff6b6b',
    });
    
    // Set price scale to auto-scale (Lightweight Charts doesn't support minValue/maxValue directly)
    // The scale will auto-fit to the data, with margins ensuring 0-100 range is visible
    AppState.chart.priceScale('right').applyOptions({
        autoScale: true,
        scaleMargins: {
            top: 0.05,
            bottom: 0.05,
        },
    });
    
    // Handle resize
    window.addEventListener('resize', () => {
        if (AppState.chart) {
            AppState.chart.resize(container.clientWidth, 500);
        }
    });
    
    return { homeSeries: AppState.homeSeries, awaySeries: AppState.awaySeries };
}

function addKalshiSeries(teamName, isHomeTeam, homeColor, ticker = null) {
    // Kalshi uses different colors for home vs away teams
    // Home team: orange/yellow, Away team: orange with different shade or style
    const kalshiHomeColor = '#f7931a';  // Orange
    const kalshiAwayColor = '#ffa500';  // Slightly different orange/yellow
    
    const color = isHomeTeam ? kalshiHomeColor : kalshiAwayColor;
    const series = AppState.chart.addLineSeries({
        color: color,
        lineWidth: 2,
        lineStyle: isHomeTeam ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 4,
        crosshairMarkerBackgroundColor: color,
    });
    
    AppState.kalshiSeries.push({ series, teamName, isHomeTeam, color, ticker });
    return { series, color };
}

/**
 * Update chart data incrementally for live updates.
 * 
 * Design Pattern: Incremental Update Pattern
 * Algorithm: O(1) per update (append single point)
 * Big O: O(1) per data point append
 */
let lastUpdateTimes = {
    espn: { home: null, away: null },
    kalshi: {}
};

/**
 * Update ESPN data incrementally.
 */
function updateESPNData(espnData) {
    if (!AppState.homeSeries || !AppState.awaySeries) {
        console.warn('Chart series not initialized, cannot update ESPN data');
        return;
    }
    
    if (!espnData || !Array.isArray(espnData) || espnData.length === 0) {
        return;
    }
    
    // Process and filter new data points
    const newHomePoints = [];
    const newAwayPoints = [];
    
    for (const point of espnData) {
        if (!point.time || point.home_prob === undefined || point.away_prob === undefined) {
            continue;
        }
        
        const time = point.time;
        const homeValue = point.home_prob * 100;
        const awayValue = point.away_prob * 100;
        
        // Skip duplicates (same timestamp as last update)
        if (time === lastUpdateTimes.espn.home || time === lastUpdateTimes.espn.away) {
            continue;
        }
        
        newHomePoints.push({ time, value: homeValue });
        newAwayPoints.push({ time, value: awayValue });
        
        // Update last update time
        lastUpdateTimes.espn.home = time;
        lastUpdateTimes.espn.away = time;
    }
    
    // Update series with new points (incremental update)
    if (newHomePoints.length > 0) {
        AppState.homeSeries.updateData(newHomePoints);
    }
    if (newAwayPoints.length > 0) {
        AppState.awaySeries.updateData(newAwayPoints);
    }
    
    // Auto-fit content if needed (optional, can be throttled)
    if (newHomePoints.length > 0 || newAwayPoints.length > 0) {
        // Throttle fitContent to avoid excessive calls
        if (!AppState.fitContentThrottle) {
            AppState.fitContentThrottle = setTimeout(() => {
                if (AppState.chart) {
                    AppState.chart.timeScale().fitContent();
                }
                AppState.fitContentThrottle = null;
            }, 1000); // Fit content at most once per second
        }
    }
}

/**
 * Update Kalshi data incrementally.
 */
function updateKalshiData(kalshiData) {
    if (!AppState.kalshiSeries || AppState.kalshiSeries.length === 0) {
        // No Kalshi series yet, skip
        return;
    }
    
    if (!kalshiData || typeof kalshiData !== 'object') {
        return;
    }
    
    // Process each Kalshi ticker/market
    for (const ticker in kalshiData) {
        const market = kalshiData[ticker];
        const data = market.data || [];
        
        if (!Array.isArray(data) || data.length === 0) {
            continue;
        }
        
        // Find corresponding series (by team name or side)
        const teamSide = market.team_side; // 'home' or 'away'
        const seriesInfo = AppState.kalshiSeries.find(s => {
            // Match by team_side if available, otherwise by team name
            if (teamSide) {
                return (teamSide === 'home' && s.isHomeTeam) || (teamSide === 'away' && !s.isHomeTeam);
            }
            return s.teamName === market.team;
        });
        
        if (!seriesInfo || !seriesInfo.series) {
            // Series not found, skip
            continue;
        }
        
        // Process new data points
        const newPoints = [];
        const lastTimeKey = `kalshi_${ticker}`;
        let lastTime = lastUpdateTimes.kalshi[lastTimeKey] || null;
        
        for (const point of data) {
            if (!point.time || point.price === undefined) {
                continue;
            }
            
            const time = point.time;
            const value = point.price;
            
            // Skip duplicates
            if (time === lastTime) {
                continue;
            }
            
            newPoints.push({ time, value });
            lastTime = time;
        }
        
        // Update last update time
        if (newPoints.length > 0) {
            lastUpdateTimes.kalshi[lastTimeKey] = lastTime;
            seriesInfo.series.updateData(newPoints);
        }
    }
    
    // Auto-fit content if needed (throttled)
    if (Object.keys(kalshiData).length > 0) {
        if (!AppState.fitContentThrottle) {
            AppState.fitContentThrottle = setTimeout(() => {
                if (AppState.chart) {
                    AppState.chart.timeScale().fitContent();
                }
                AppState.fitContentThrottle = null;
            }, 1000);
        }
    }
}

/**
 * Throttle and batch updates for smooth rendering.
 * 
 * Design Pattern: Throttle Pattern
 * Algorithm: O(1) per throttled update
 * Big O: O(1) for throttling check
 */
let updateQueue = {
    espn: [],
    kalshi: {}
};
let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100; // Max 10 updates per second
let updateTimer = null;

/**
 * Throttled update function that batches multiple updates.
 */
function throttledUpdateChartData(espnData, kalshiData) {
    // Add to queue
    if (espnData && Array.isArray(espnData)) {
        updateQueue.espn.push(...espnData);
    }
    if (kalshiData && typeof kalshiData === 'object') {
        for (const ticker in kalshiData) {
            if (!updateQueue.kalshi[ticker]) {
                updateQueue.kalshi[ticker] = [];
            }
            const market = kalshiData[ticker];
            if (market.data && Array.isArray(market.data)) {
                updateQueue.kalshi[ticker].push(...market.data);
            }
        }
    }
    
    // Schedule update
    const now = Date.now();
    const timeSinceLastUpdate = now - lastUpdateTime;
    
    if (timeSinceLastUpdate >= UPDATE_THROTTLE_MS) {
        // Update immediately
        _processUpdateQueue();
    } else {
        // Schedule update after throttle period
        if (!updateTimer) {
            const delay = UPDATE_THROTTLE_MS - timeSinceLastUpdate;
            updateTimer = setTimeout(() => {
                _processUpdateQueue();
                updateTimer = null;
            }, delay);
        }
    }
}

/**
 * Process queued updates.
 */
function _processUpdateQueue() {
    lastUpdateTime = Date.now();
    
    // Process ESPN queue
    if (updateQueue.espn.length > 0) {
        // Deduplicate by timestamp (keep latest)
        const espnMap = new Map();
        for (const point of updateQueue.espn) {
            if (point.time) {
                espnMap.set(point.time, point);
            }
        }
        const deduplicatedEspn = Array.from(espnMap.values()).sort((a, b) => a.time - b.time);
        updateESPNData(deduplicatedEspn);
        updateQueue.espn = [];
    }
    
    // Process Kalshi queue
    for (const ticker in updateQueue.kalshi) {
        const queue = updateQueue.kalshi[ticker];
        if (queue.length > 0) {
            // Deduplicate by timestamp
            const kalshiMap = new Map();
            for (const point of queue) {
                if (point.time) {
                    kalshiMap.set(point.time, point);
                }
            }
            const deduplicatedKalshi = Array.from(kalshiMap.values()).sort((a, b) => a.time - b.time);
            
            // Reconstruct market format
            const marketData = {
                [ticker]: {
                    data: deduplicatedKalshi,
                    team_side: updateQueue.kalshi[ticker + '_team_side'] || null,
                    team: updateQueue.kalshi[ticker + '_team'] || null
                }
            };
            updateKalshiData(marketData);
            updateQueue.kalshi[ticker] = [];
        }
    }
}

/**
 * Update chart with live data (ESPN and/or Kalshi).
 * 
 * This is the main entry point for live updates.
 * Uses throttling and batching for smooth rendering.
 */
function updateChartData(espnData, kalshiData) {
    throttledUpdateChartData(espnData, kalshiData);
}

/**
 * Reset update tracking (call when switching games or initializing).
 */
function resetUpdateTracking() {
    lastUpdateTimes = {
        espn: { home: null, away: null },
        kalshi: {}
    };
    if (AppState.fitContentThrottle) {
        clearTimeout(AppState.fitContentThrottle);
        AppState.fitContentThrottle = null;
    }
    // Clear update queue
    updateQueue = {
        espn: [],
        kalshi: {}
    };
    if (updateTimer) {
        clearTimeout(updateTimer);
        updateTimer = null;
    }
    lastUpdateTime = 0;
}

