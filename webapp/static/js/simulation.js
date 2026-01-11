/**
 * Trading simulation module.
 * 
 * Design Pattern: Module Pattern for simulation UI
 * Algorithm: API calls and result rendering
 * Big O: O(1) for API calls, O(n) for rendering where n = number of trades
 */

/**
 * Run bulk simulation for multiple games with given parameters.
 */
async function runBulkSimulation(numGames, entryThreshold, exitThreshold, excludeFirst, excludeLast, betAmount, useTradeData, enableFees, requestId) {
    const params = new URLSearchParams({
        num_games: numGames.toString(),
        entry_threshold: (entryThreshold / 100).toFixed(3), // Convert cents to probability
        exit_threshold: (exitThreshold / 100).toFixed(3), // 0 = when they converge (same)
        exclude_first_seconds: excludeFirst.toString(),
        exclude_last_seconds: excludeLast.toString(),
        bet_amount: betAmount.toString(),
        use_trade_data: useTradeData.toString(),
        enable_fees: enableFees.toString(),
    });
    
    if (requestId) {
        params.append('request_id', requestId);
    }
    
    const url = `/api/simulation/bulk?${params.toString()}`;
    
    try {
        const response = await fetch(url);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error running bulk simulation:', error);
        throw error;
    }
}

/**
 * Connect to WebSocket for simulation progress updates.
 * 
 * Design Pattern: WebSocket Handler Pattern
 * Algorithm: O(1) connection, O(1) per update
 * Big O: O(1) for connection operations, O(1) for message handling
 * 
 * @param {string} requestId - Simulation request ID
 * @param {Function} onProgress - Callback function called with progress updates
 * @returns {WebSocket} WebSocket connection (can be used to disconnect)
 */
function connectSimulationProgress(requestId, onProgress) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/simulation/${requestId}`;
    
    console.log(`Connecting to simulation progress WebSocket: ${url}`);
    
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
        console.log(`Simulation progress WebSocket connected: requestId=${requestId}`);
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'progress') {
                onProgress(data.progress);
                
                // Connection will close automatically when simulation completes
                if (data.progress.status === 'complete' || data.progress.status === 'error') {
                    console.log(`Simulation ${requestId} finished with status: ${data.progress.status}`);
                }
            } else if (data.type === 'error') {
                console.error('Simulation progress WebSocket error:', data.message);
                onProgress({ status: 'error', message: data.message });
            } else if (data.type === 'pong') {
                // Connection health check response
                // No action needed
            }
        } catch (error) {
            console.error('Error parsing simulation progress WebSocket message:', error, event.data);
        }
    };
    
    ws.onerror = (error) => {
        console.error(`Simulation progress WebSocket error for ${requestId}:`, error);
        // Fallback: try HTTP endpoint once
        fetch(`/api/simulation/progress/${requestId}`)
            .then(response => response.json())
            .then(progress => onProgress(progress))
            .catch(err => console.error('Fallback HTTP request also failed:', err));
    };
    
    ws.onclose = (event) => {
        console.log(`Simulation progress WebSocket closed for ${requestId}:`, event.code, event.reason);
        // Connection closed - simulation likely completed or errored
        // onProgress callback should have been called with final status
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
    
    return ws;
}

/**
 * Format currency value.
 */
function formatCurrency(cents) {
    const dollars = cents / 100;
    return dollars >= 0 
        ? `$${dollars.toFixed(2)}` 
        : `-$${Math.abs(dollars).toFixed(2)}`;
}

/**
 * Format percentage.
 */
function formatPercent(value) {
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * View state management
 */
let currentViewMode = 'simplified'; // 'advanced' or 'simplified'

/**
 * Toggle between simplified and advanced views
 */
function toggleSimulationView() {
    const simplifiedView = document.getElementById('simplifiedView');
    const advancedView = document.getElementById('advancedView');
    const toggleBtn = document.getElementById('viewToggleBtn');
    const toggleText = document.getElementById('viewToggleText');
    
    if (!simplifiedView || !advancedView || !toggleBtn || !toggleText) {
        console.error('View toggle elements not found');
        return;
    }
    
    if (currentViewMode === 'advanced') {
        // Switch to simplified view
        simplifiedView.style.display = 'block';
        advancedView.style.display = 'none';
        currentViewMode = 'simplified';
        toggleText.textContent = 'Advanced View';
    } else {
        // Switch to advanced view
        simplifiedView.style.display = 'none';
        advancedView.style.display = 'block';
        currentViewMode = 'advanced';
        toggleText.textContent = 'Simplified View';
    }
}

/**
 * Render simplified simulation results (summary stats only, no charts).
 */
function renderSimplifiedResults(results) {
    // Entry/Exit Conditions
    const entryThresholdEl = document.getElementById('simplifiedEntryThreshold');
    const exitThresholdEl = document.getElementById('simplifiedExitThreshold');
    if (entryThresholdEl && results.entry_threshold !== undefined) {
        // Convert from probability (0.05) to cents (5)
        const entryThresholdCents = Math.round(results.entry_threshold * 100);
        entryThresholdEl.textContent = `${entryThresholdCents} cents`;
    }
    if (exitThresholdEl && results.exit_threshold !== undefined) {
        // Convert from probability (0.01) to cents (1)
        const exitThresholdCents = Math.round(results.exit_threshold * 100);
        exitThresholdEl.textContent = `${exitThresholdCents} cents`;
    }
    
    // Summary Stats
    const totalProfitEl = document.getElementById('simplifiedTotalProfit');
    const roiEl = document.getElementById('simplifiedRoiPercentage');
    const numGamesEl = document.getElementById('simplifiedNumGames');
    const numTradesEl = document.getElementById('simplifiedNumTrades');
    const winRateEl = document.getElementById('simplifiedWinRate');
    const avgProfitEl = document.getElementById('simplifiedAvgProfit');
    const medianProfitEl = document.getElementById('simplifiedMedianProfit');
    
    if (totalProfitEl) {
        totalProfitEl.textContent = formatCurrency(results.total_profit_cents);
        totalProfitEl.className = 'summary-value ' + (results.total_profit_cents >= 0 ? 'positive' : 'negative');
    }
    if (roiEl) {
        const roi = results.roi_percentage || 0;
        roiEl.textContent = `${roi.toFixed(2)}%`;
        roiEl.className = 'summary-value ' + (roi >= 0 ? 'positive' : 'negative');
    }
    if (numGamesEl) {
        const numGames = results.num_games || 0;
        const numGamesRequested = results.num_games_requested || 0;
        numGamesEl.textContent = `${numGames} / ${numGamesRequested}`;
    }
    if (numTradesEl) numTradesEl.textContent = results.num_trades.toString();
    if (winRateEl) {
        winRateEl.textContent = formatPercent(results.win_rate);
        winRateEl.className = 'summary-value ' + (results.win_rate >= 0.5 ? 'positive' : 'negative');
    }
    if (avgProfitEl) {
        avgProfitEl.textContent = formatCurrency(results.avg_profit_per_trade_cents);
        avgProfitEl.className = 'summary-value ' + (results.avg_profit_per_trade_cents >= 0 ? 'positive' : 'negative');
    }
    if (medianProfitEl) {
        medianProfitEl.textContent = formatCurrency(results.median_profit_cents || 0);
        medianProfitEl.className = 'summary-value ' + ((results.median_profit_cents || 0) >= 0 ? 'positive' : 'negative');
    }
    
    // Position Breakdown
    if (results.position_breakdown) {
        const pb = results.position_breakdown;
        const longEl = document.getElementById('simplifiedLongCount');
        const longProfitEl = document.getElementById('simplifiedLongProfit');
        const longWinRateEl = document.getElementById('simplifiedLongWinRate');
        const longAvgProfitEl = document.getElementById('simplifiedLongAvgProfit');
        const shortEl = document.getElementById('simplifiedShortCount');
        const shortProfitEl = document.getElementById('simplifiedShortProfit');
        const shortWinRateEl = document.getElementById('simplifiedShortWinRate');
        const shortAvgProfitEl = document.getElementById('simplifiedShortAvgProfit');
        
        if (longEl) longEl.textContent = pb.long?.count || 0;
        if (longProfitEl) {
            longProfitEl.textContent = `$${(pb.long?.profit_dollars || 0).toFixed(2)}`;
            longProfitEl.className = 'stat-value ' + ((pb.long?.profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        if (longWinRateEl) {
            longWinRateEl.textContent = formatPercent(pb.long?.win_rate || 0);
            longWinRateEl.className = 'stat-value ' + ((pb.long?.win_rate || 0) >= 0.5 ? 'positive' : 'negative');
        }
        if (longAvgProfitEl) {
            longAvgProfitEl.textContent = `$${(pb.long?.avg_profit_dollars || 0).toFixed(2)}`;
            longAvgProfitEl.className = 'stat-value ' + ((pb.long?.avg_profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        
        if (shortEl) shortEl.textContent = pb.short?.count || 0;
        if (shortProfitEl) {
            shortProfitEl.textContent = `$${(pb.short?.profit_dollars || 0).toFixed(2)}`;
            shortProfitEl.className = 'stat-value ' + ((pb.short?.profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        if (shortWinRateEl) {
            shortWinRateEl.textContent = formatPercent(pb.short?.win_rate || 0);
            shortWinRateEl.className = 'stat-value ' + ((pb.short?.win_rate || 0) >= 0.5 ? 'positive' : 'negative');
        }
        if (shortAvgProfitEl) {
            shortAvgProfitEl.textContent = `$${(pb.short?.avg_profit_dollars || 0).toFixed(2)}`;
            shortAvgProfitEl.className = 'stat-value ' + ((pb.short?.avg_profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
    }
    
    // Performance Metrics
    const expectancyEl = document.getElementById('simplifiedExpectancy');
    const profitFactorEl = document.getElementById('simplifiedProfitFactor');
    const maxLossEl = document.getElementById('simplifiedMaxLoss');
    const maxWinEl = document.getElementById('simplifiedMaxWin');
    
    if (expectancyEl && results.expectancy_dollars !== undefined) {
        expectancyEl.textContent = formatCurrency(results.expectancy_dollars * 100); // Convert to cents
        expectancyEl.className = 'risk-value ' + ((results.expectancy_dollars || 0) >= 0 ? 'positive' : 'negative');
    }
    if (profitFactorEl && results.profit_factor !== undefined) {
        profitFactorEl.textContent = (results.profit_factor || 0).toFixed(2);
        profitFactorEl.className = 'risk-value ' + ((results.profit_factor || 0) > 1 ? 'positive' : 'negative');
    }
    if (maxLossEl && results.risk_metrics) {
        maxLossEl.textContent = `$${Math.abs(results.risk_metrics.max_loss_dollars || 0).toFixed(2)}`;
        maxLossEl.className = 'risk-value negative';
    }
    if (maxWinEl && results.risk_metrics) {
        maxWinEl.textContent = `$${(results.risk_metrics.max_win_dollars || 0).toFixed(2)}`;
        maxWinEl.className = 'risk-value positive';
    }
    
    // Risk Metrics
    const maxDrawdownDollarsEl = document.getElementById('simplifiedMaxDrawdownDollars');
    const maxDrawdownPercentEl = document.getElementById('simplifiedMaxDrawdownPercent');
    const stdDevEl = document.getElementById('simplifiedStdDev');
    const sharpeEl = document.getElementById('simplifiedSharpeRatio');
    
    if (maxDrawdownDollarsEl && results.max_drawdown_dollars !== undefined) {
        maxDrawdownDollarsEl.textContent = formatCurrency(Math.abs(results.max_drawdown_dollars) * 100); // Convert to cents
        maxDrawdownDollarsEl.className = 'risk-value negative';
    }
    if (maxDrawdownPercentEl && results.max_drawdown_percent !== undefined) {
        maxDrawdownPercentEl.textContent = `${(results.max_drawdown_percent || 0).toFixed(2)}%`;
        maxDrawdownPercentEl.className = 'risk-value negative';
    }
    if (stdDevEl && results.risk_metrics) {
        stdDevEl.textContent = `$${(results.risk_metrics.std_dev_dollars || 0).toFixed(2)}`;
    }
    if (sharpeEl) {
        sharpeEl.textContent = (results.sharpe_ratio || 0).toFixed(2);
        sharpeEl.className = 'risk-value ' + ((results.sharpe_ratio || 0) > 1 ? 'positive' : (results.sharpe_ratio || 0) > 0 ? '' : 'negative');
    }
}

/**
 * Render simulation results.
 */
function renderSimulationResults(results) {
    const resultsDiv = document.getElementById('simulationResults');
    const errorDiv = document.getElementById('simulationError');
    const loadingDiv = document.getElementById('simulationLoading');
    
    // Hide loading and error
    if (loadingDiv) loadingDiv.style.display = 'none';
    if (errorDiv) errorDiv.style.display = 'none';
    
    if (!resultsDiv) {
        console.error('simulationResults element not found');
        return;
    }
    
    // Show results
    resultsDiv.style.display = 'block';
    
    // Show export button
    const exportButtons = document.getElementById('simulationExportButtons');
    if (exportButtons) {
        exportButtons.style.display = 'flex';
    }
    
    // Update summary cards
    const totalProfitEl = document.getElementById('totalProfit');
    const roiEl = document.getElementById('roiPercentage');
    const numGamesEl = document.getElementById('numGamesResult');
    const numTradesEl = document.getElementById('numTrades');
    const winRateEl = document.getElementById('winRate');
    const avgProfitEl = document.getElementById('avgProfit');
    const medianProfitEl = document.getElementById('medianProfit');
    
    if (totalProfitEl) {
        totalProfitEl.textContent = formatCurrency(results.total_profit_cents);
        totalProfitEl.className = 'summary-value ' + (results.total_profit_cents >= 0 ? 'positive' : 'negative');
    }
    if (roiEl) {
        const roi = results.roi_percentage || 0;
        roiEl.textContent = `${roi.toFixed(2)}%`;
        roiEl.className = 'summary-value ' + (roi >= 0 ? 'positive' : 'negative');
    }
    if (numGamesEl) {
        const numGames = results.num_games || 0;
        const numGamesRequested = results.num_games_requested || 0;
        numGamesEl.textContent = `${numGames} / ${numGamesRequested}`;
    }
    if (numTradesEl) numTradesEl.textContent = results.num_trades.toString();
    if (winRateEl) {
        winRateEl.textContent = formatPercent(results.win_rate);
        winRateEl.className = 'summary-value ' + (results.win_rate >= 0.5 ? 'positive' : 'negative');
    }
    if (avgProfitEl) {
        avgProfitEl.textContent = formatCurrency(results.avg_profit_per_trade_cents);
        avgProfitEl.className = 'summary-value ' + (results.avg_profit_per_trade_cents >= 0 ? 'positive' : 'negative');
    }
    if (medianProfitEl) {
        medianProfitEl.textContent = formatCurrency(results.median_profit_cents || 0);
        medianProfitEl.className = 'summary-value ' + ((results.median_profit_cents || 0) >= 0 ? 'positive' : 'negative');
    }
    // Sample size indicator (in equity curve section)
    const sampleSizeEl = document.getElementById('sampleSizeText');
    if (sampleSizeEl && results.sample_size_n !== undefined) {
        const n = results.sample_size_n || 0;
        sampleSizeEl.textContent = `n = ${n} trade${n !== 1 ? 's' : ''}`;
        if (n < 30) {
            sampleSizeEl.parentElement.style.color = 'var(--accent-away)';
            sampleSizeEl.textContent += ' (Low statistical power - small sample)';
        }
    }
    
    // Sample size badge (near headline)
    const sampleSizeBadge = document.getElementById('sampleSizeBadge');
    const sampleSizeBadgeText = document.getElementById('sampleSizeBadgeText');
    if (sampleSizeBadge && sampleSizeBadgeText && results.sample_size_n !== undefined) {
        const n = results.sample_size_n || 0;
        if (n > 0) {
            sampleSizeBadge.style.display = 'block';
            if (n < 30) {
                sampleSizeBadgeText.textContent = `n = ${n} trades (small sample)`;
                sampleSizeBadgeText.style.color = 'var(--accent-away)';
            } else {
                sampleSizeBadgeText.textContent = `n = ${n} trades`;
            }
        }
    }
    
    // Position breakdown
    if (results.position_breakdown) {
        const pb = results.position_breakdown;
        const longEl = document.getElementById('longCount');
        const longProfitEl = document.getElementById('longProfit');
        const longWinRateEl = document.getElementById('longWinRate');
        const longAvgProfitEl = document.getElementById('longAvgProfit');
        const shortEl = document.getElementById('shortCount');
        const shortProfitEl = document.getElementById('shortProfit');
        const shortWinRateEl = document.getElementById('shortWinRate');
        const shortAvgProfitEl = document.getElementById('shortAvgProfit');
        
        if (longEl) longEl.textContent = pb.long?.count || 0;
        if (longProfitEl) {
            longProfitEl.textContent = `$${(pb.long?.profit_dollars || 0).toFixed(2)}`;
            longProfitEl.className = 'stat-value ' + ((pb.long?.profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        if (longWinRateEl) {
            longWinRateEl.textContent = formatPercent(pb.long?.win_rate || 0);
            longWinRateEl.className = 'stat-value ' + ((pb.long?.win_rate || 0) >= 0.5 ? 'positive' : 'negative');
        }
        if (longAvgProfitEl) {
            longAvgProfitEl.textContent = `$${(pb.long?.avg_profit_dollars || 0).toFixed(2)}`;
            longAvgProfitEl.className = 'stat-value ' + ((pb.long?.avg_profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        
        if (shortEl) shortEl.textContent = pb.short?.count || 0;
        if (shortProfitEl) {
            shortProfitEl.textContent = `$${(pb.short?.profit_dollars || 0).toFixed(2)}`;
            shortProfitEl.className = 'stat-value ' + ((pb.short?.profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
        if (shortWinRateEl) {
            shortWinRateEl.textContent = formatPercent(pb.short?.win_rate || 0);
            shortWinRateEl.className = 'stat-value ' + ((pb.short?.win_rate || 0) >= 0.5 ? 'positive' : 'negative');
        }
        if (shortAvgProfitEl) {
            shortAvgProfitEl.textContent = `$${(pb.short?.avg_profit_dollars || 0).toFixed(2)}`;
            shortAvgProfitEl.className = 'stat-value ' + ((pb.short?.avg_profit_dollars || 0) >= 0 ? 'positive' : 'negative');
        }
    }
    
    // Risk metrics
    if (results.risk_metrics) {
        const rm = results.risk_metrics;
        const maxLossEl = document.getElementById('maxLoss');
        const maxWinEl = document.getElementById('maxWin');
        const stdDevEl = document.getElementById('stdDev');
        const sharpeEl = document.getElementById('sharpeRatio');
        
        if (maxLossEl) {
            maxLossEl.textContent = `$${Math.abs(rm.max_loss_dollars || 0).toFixed(2)}`;
            maxLossEl.className = 'risk-value negative';
        }
        if (maxWinEl) {
            maxWinEl.textContent = `$${(rm.max_win_dollars || 0).toFixed(2)}`;
            maxWinEl.className = 'risk-value positive';
        }
        if (stdDevEl) {
            stdDevEl.textContent = `$${(rm.std_dev_dollars || 0).toFixed(2)}`;
        }
        if (sharpeEl) {
            sharpeEl.textContent = (results.sharpe_ratio || 0).toFixed(2);
            sharpeEl.className = 'risk-value ' + ((results.sharpe_ratio || 0) > 1 ? 'positive' : (results.sharpe_ratio || 0) > 0 ? '' : 'negative');
        }
    }
    
    // Performance metrics
    const expectancyEl = document.getElementById('expectancy');
    const profitFactorEl = document.getElementById('profitFactor');
    if (expectancyEl && results.expectancy_dollars !== undefined) {
        expectancyEl.textContent = formatCurrency(results.expectancy_dollars * 100); // Convert to cents
        expectancyEl.className = 'risk-value ' + ((results.expectancy_dollars || 0) >= 0 ? 'positive' : 'negative');
    }
    if (profitFactorEl && results.profit_factor !== undefined) {
        profitFactorEl.textContent = (results.profit_factor || 0).toFixed(2);
        profitFactorEl.className = 'risk-value ' + ((results.profit_factor || 0) > 1 ? 'positive' : 'negative');
    }
    
    // Max Drawdown
    const maxDrawdownDollarsEl = document.getElementById('maxDrawdownDollars');
    const maxDrawdownPercentEl = document.getElementById('maxDrawdownPercent');
    if (maxDrawdownDollarsEl && results.max_drawdown_dollars !== undefined) {
        maxDrawdownDollarsEl.textContent = formatCurrency(Math.abs(results.max_drawdown_dollars) * 100); // Convert to cents
        maxDrawdownDollarsEl.className = 'risk-value negative';
    }
    if (maxDrawdownPercentEl && results.max_drawdown_percent !== undefined) {
        maxDrawdownPercentEl.textContent = `${(results.max_drawdown_percent || 0).toFixed(2)}%`;
        maxDrawdownPercentEl.className = 'risk-value negative';
    }
    
    // Trade characteristics
    if (results.avg_trade_duration_minutes !== undefined) {
        const durationEl = document.getElementById('avgTradeDuration');
        if (durationEl) {
            const minutes = Math.floor(results.avg_trade_duration_minutes || 0);
            const seconds = Math.round(((results.avg_trade_duration_minutes || 0) - minutes) * 60);
            durationEl.textContent = minutes > 0 ? `${minutes} min ${seconds} sec` : `${seconds} sec`;
        }
    }
    if (results.divergence_metrics) {
        const dm = results.divergence_metrics;
        const entryDivEl = document.getElementById('avgEntryDivergence');
        const exitDivEl = document.getElementById('avgExitDivergence');
        if (entryDivEl) entryDivEl.textContent = `${(dm.avg_entry_divergence_cents || 0).toFixed(1)} cents`;
        if (exitDivEl) exitDivEl.textContent = `${(dm.avg_exit_divergence_cents || 0).toFixed(1)} cents`;
    }
    
    // Distribution quartiles chart
    if (results.distribution_quartiles && typeof Chart !== 'undefined') {
        renderQuartilesChart(results.distribution_quartiles);
    }
    
    // Equity curve chart
    if (results.equity_curve && typeof Chart !== 'undefined') {
        renderEquityCurveChart(results.equity_curve);
    }
    
    // Per-game summary table
    if (results.per_game_summary) {
        renderPerGameTable(results.per_game_summary);
    }
    
    // Render trades list
    const tradesListEl = document.getElementById('tradesList');
    if (tradesListEl) {
        if (results.trades && results.trades.length > 0) {
            // Limit display to first 100 trades to avoid performance issues
            const displayTrades = results.trades.slice(0, 100);
            const hasMore = results.trades.length > 100;
            
            tradesListEl.innerHTML = displayTrades.map((trade, index) => {
                const profitClass = (trade.profit_cents || 0) >= 0 ? 'positive' : 'negative';
                const positionType = trade.position_type === 'long_espn' ? 'Long ESPN' : 'Short ESPN';
                const entryTime = new Date(trade.entry_time * 1000).toLocaleTimeString();
                const exitTime = trade.exit_time ? new Date(trade.exit_time * 1000).toLocaleTimeString() : 'N/A';
                
                // Format game date
                let gameDateDisplay = '';
                let gameLink = '';
                if (trade.game_id) {
                    const gameIdShort = trade.game_id.substring(trade.game_id.length - 6);
                    gameLink = `<a href="#/game/${trade.game_id}" class="game-link">Game: ${gameIdShort}</a>`;
                    
                    // Format game date if available
                    if (trade.game_date) {
                        try {
                            // Handle different date formats
                            let gameDate;
                            if (typeof trade.game_date === 'string') {
                                // Try parsing as YYYYMMDD format first
                                if (trade.game_date.match(/^\d{8}$/)) {
                                    const year = trade.game_date.substring(0, 4);
                                    const month = trade.game_date.substring(4, 6);
                                    const day = trade.game_date.substring(6, 8);
                                    gameDate = new Date(`${year}-${month}-${day}`);
                                } else {
                                    gameDate = new Date(trade.game_date);
                                }
                            } else {
                                gameDate = new Date(trade.game_date);
                            }
                            
                            if (!isNaN(gameDate.getTime())) {
                                gameDateDisplay = gameDate.toLocaleDateString('en-US', { 
                                    year: 'numeric', 
                                    month: 'short', 
                                    day: 'numeric' 
                                });
                            }
                        } catch (e) {
                            // If date parsing fails, just use the raw value
                            gameDateDisplay = trade.game_date;
                        }
                    }
                }
                
                return `
                    <div class="trade-item">
                        <div class="trade-header">
                            <span class="trade-number">Trade ${index + 1}${gameLink ? ` - ${gameLink}` : ''}</span>
                            <span class="trade-type ${trade.position_type}">${positionType}</span>
                            <span class="trade-profit ${profitClass}">${formatCurrency(trade.profit_cents || 0)}</span>
                        </div>
                        <div class="trade-details">
                            ${gameDateDisplay ? `
                            <div class="trade-detail-row">
                                <span class="detail-label">Game Date:</span>
                                <span class="detail-value">${gameDateDisplay}</span>
                            </div>
                            ` : ''}
                            <div class="trade-detail-row">
                                <span class="detail-label">Entry:</span>
                                <span class="detail-value">ESPN: ${(trade.entry_espn_prob * 100).toFixed(1)}% | Kalshi: ${(trade.entry_kalshi_price * 100).toFixed(1)}%</span>
                            </div>
                            <div class="trade-detail-row">
                                <span class="detail-label">Time:</span>
                                <span class="detail-value">${entryTime} → ${exitTime}</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('') + (hasMore ? `<p class="no-trades">Showing first 100 of ${results.trades.length} total trades</p>` : '');
        } else {
            tradesListEl.innerHTML = '<p class="no-trades">No trades executed for this simulation.</p>';
        }
    }
    
    // Render metadata
    const metadataEl = document.getElementById('simulationMetadata');
    if (metadataEl) {
        metadataEl.innerHTML = `
            <div class="metadata-item">
                <span class="metadata-label">Games Simulated:</span>
                <span class="metadata-value">${results.num_games || 0} / ${results.num_games_requested || 0}</span>
            </div>
            ${results.failed_games && results.failed_games.length > 0 ? `
            <div class="metadata-item">
                <span class="metadata-label">Failed Games:</span>
                <span class="metadata-value">${results.failed_games.length}</span>
            </div>
            ` : ''}
            <div class="metadata-item">
                <span class="metadata-label">Bet Amount:</span>
                <span class="metadata-value">$${results.bet_amount_dollars?.toFixed(2) || '20.00'}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Entry Threshold:</span>
                <span class="metadata-value">${(results.entry_threshold * 100).toFixed(1)} cents</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Exit Threshold:</span>
                <span class="metadata-value">${(results.exit_threshold * 100).toFixed(1)} cents</span>
            </div>
            ${results.exclude_first_seconds > 0 || results.exclude_last_seconds > 0 ? `
            <div class="metadata-item">
                <span class="metadata-label">Time Filtering:</span>
                <span class="metadata-value">Excluded first ${results.exclude_first_seconds}s, last ${results.exclude_last_seconds}s</span>
            </div>
            ` : ''}
        `;
    }
}

/**
 * Show error message.
 */
function showSimulationError(message) {
    const errorDiv = document.getElementById('simulationError');
    const resultsDiv = document.getElementById('simulationResults');
    const loadingDiv = document.getElementById('simulationLoading');
    const exportButtons = document.getElementById('simulationExportButtons');
    
    if (loadingDiv) loadingDiv.style.display = 'none';
    if (resultsDiv) resultsDiv.style.display = 'none';
    if (exportButtons) exportButtons.style.display = 'none';
    
    if (errorDiv) {
        errorDiv.textContent = `Error: ${message}`;
        errorDiv.style.display = 'block';
    }
}



/**
 * Update scenario description based on current parameter values.
 */
function updateScenarioDescription() {
    const entryThreshold = parseFloat(document.getElementById('entryThreshold')?.value || '5');
    const exitThreshold = parseFloat(document.getElementById('exitThreshold')?.value || '2');
    const excludeFirst = parseInt(document.getElementById('excludeFirst')?.value || '60');
    const excludeLast = parseInt(document.getElementById('excludeLast')?.value || '60');
    const numGames = parseInt(document.getElementById('numGames')?.value || '500');
    
    const entryDisplay = document.getElementById('entryThresholdDisplay');
    const exitDisplay = document.getElementById('exitThresholdDisplay');
    const timeFilterDisplay = document.getElementById('timeFilterDisplay');
    const numGamesDisplay = document.getElementById('numGamesDisplay');
    
    // Update entry threshold
    if (entryDisplay) {
        entryDisplay.textContent = entryThreshold.toString();
    }
    
    // Update exit threshold
    if (exitDisplay) {
        if (exitThreshold === 0) {
            exitDisplay.textContent = 'the same';
        } else {
            exitDisplay.textContent = exitThreshold.toString();
        }
    }
    
    // Update number of games
    if (numGamesDisplay) {
        if (numGames === 1) {
            numGamesDisplay.textContent = '1 game';
        } else {
            numGamesDisplay.textContent = `the last ${numGames} games`;
        }
    }
    
    // Update time filtering description
    if (timeFilterDisplay) {
        const timeFilters = [];
        if (excludeFirst > 0) {
            const minutes = Math.floor(excludeFirst / 60);
            timeFilters.push(`excluding the first ${minutes} minute${minutes !== 1 ? 's' : ''}`);
        }
        if (excludeLast > 0) {
            const minutes = Math.floor(excludeLast / 60);
            timeFilters.push(`excluding the last ${minutes} minute${minutes !== 1 ? 's' : ''}`);
        }
        
        if (timeFilters.length > 0) {
            timeFilterDisplay.textContent = ` (${timeFilters.join(' and ')})`;
        } else {
            timeFilterDisplay.textContent = '';
        }
    }
}

/**
 * Render quartiles chart using Chart.js
 */
function renderQuartilesChart(quartiles) {
    const canvas = document.getElementById('quartilesChart');
    if (!canvas || typeof Chart === 'undefined') {
        console.warn('Chart.js not available or canvas not found');
        return;
    }
    
    // Destroy existing chart if it exists and is a valid Chart instance
    if (window.quartilesChart && typeof window.quartilesChart.destroy === 'function') {
        try {
            window.quartilesChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing chart:', e);
        }
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Could not get 2d context from canvas');
        return;
    }
    
    const data = [
        quartiles.min_dollars || 0,
        quartiles.q1_dollars || 0,
        quartiles.q2_dollars || 0,  // median
        quartiles.q3_dollars || 0,
        quartiles.max_dollars || 0,
    ];
    
    try {
        window.quartilesChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Min', 'Q1 (25%)', 'Q2 (Median)', 'Q3 (75%)', 'Max'],
                datasets: [{
                    label: 'Profit Distribution ($)',
                    data: data,
                    // Colorblind-safe colors: teal for positive, orange-red for negative
                    backgroundColor: data.map(val => val >= 0 ? 'rgba(0, 212, 170, 0.6)' : 'rgba(255, 140, 0, 0.6)'),
                    borderColor: data.map(val => val >= 0 ? '#00d4aa' : '#ff8c00'),
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `$${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error creating quartiles chart:', error);
        window.quartilesChart = null;
    }
}

/**
 * Render equity curve chart showing cumulative P&L over trades
 */
function renderEquityCurveChart(equityCurve) {
    const canvas = document.getElementById('equityCurveChart');
    if (!canvas || typeof Chart === 'undefined') {
        console.warn('Chart.js not available or canvas not found');
        return;
    }
    
    // Destroy existing chart if it exists
    if (window.equityCurveChart && typeof window.equityCurveChart.destroy === 'function') {
        try {
            window.equityCurveChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing equity curve chart:', e);
        }
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Could not get 2d context from canvas');
        return;
    }
    
    const tradeNumbers = equityCurve.map(d => d.trade_number);
    const cumulativeProfits = equityCurve.map(d => d.cumulative_profit_dollars);
    
    try {
        window.equityCurveChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tradeNumbers.map(n => `Trade ${n}`),
                datasets: [{
                    label: 'Cumulative P&L ($)',
                    data: cumulativeProfits,
                    // Colorblind-safe colors: teal for positive, orange-red for negative
                    borderColor: cumulativeProfits[cumulativeProfits.length - 1] >= 0 ? '#00d4aa' : '#ff8c00',
                    backgroundColor: cumulativeProfits[cumulativeProfits.length - 1] >= 0 ? 'rgba(0, 212, 170, 0.1)' : 'rgba(255, 140, 0, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `$${context.parsed.y.toFixed(2)}`;
                            },
                            title: function(context) {
                                return `Trade ${tradeNumbers[context[0].dataIndex]}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Trade Number'
                        }
                    },
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Cumulative P&L ($)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error creating equity curve chart:', error);
        window.equityCurveChart = null;
    }
}

/**
 * Render per-game summary table
 */
function renderPerGameTable(perGameSummary) {
    const tbody = document.getElementById('perGameTableBody');
    if (!tbody) return;
    
    if (!perGameSummary || perGameSummary.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-muted);">No game data available</td></tr>';
        return;
    }
    
    tbody.innerHTML = perGameSummary.map(game => {
        const gameId = game.game_id || 'N/A';
        const gameIdShort = gameId.length > 10 ? gameId.substring(gameId.length - 8) : gameId;
        const date = game.game_date ? new Date(game.game_date).toLocaleDateString() : 'N/A';
        const profit = game.profit_dollars || 0;
        const profitClass = profit >= 0 ? 'positive' : 'negative';
        const winRate = (game.win_rate || 0) * 100;
        const winRateClass = winRate >= 50 ? 'positive' : 'negative';
        
        return `
            <tr>
                <td class="mono">${gameIdShort}</td>
                <td>${date}</td>
                <td>${game.num_trades || 0}</td>
                <td class="${profitClass}">$${profit.toFixed(2)}</td>
                <td class="${winRateClass}">${winRate.toFixed(1)}%</td>
            </tr>
        `;
    }).join('');
}

/**
 * Initialize simulation page.
 */
function initializeSimulationPage() {
    const runSimulationBtn = document.getElementById('runSimulationBtn');
    const numGamesInput = document.getElementById('numGames');
    const entryThresholdInput = document.getElementById('entryThreshold');
    const exitThresholdInput = document.getElementById('exitThreshold');
    
    // Update scenario description when any parameter changes
    const excludeFirstInput = document.getElementById('excludeFirst');
    const excludeLastInput = document.getElementById('excludeLast');
    const numGamesInputForScenario = document.getElementById('numGames');
    
    const updateScenario = () => updateScenarioDescription();
    
    if (entryThresholdInput) {
        entryThresholdInput.addEventListener('input', updateScenario);
        entryThresholdInput.addEventListener('change', updateScenario);
    }
    if (exitThresholdInput) {
        exitThresholdInput.addEventListener('input', updateScenario);
        exitThresholdInput.addEventListener('change', updateScenario);
    }
    if (numGamesInputForScenario) {
        numGamesInputForScenario.addEventListener('input', updateScenario);
        numGamesInputForScenario.addEventListener('change', updateScenario);
    }
    if (excludeFirstInput) {
        excludeFirstInput.addEventListener('input', updateScenario);
        excludeFirstInput.addEventListener('change', updateScenario);
    }
    if (excludeLastInput) {
        excludeLastInput.addEventListener('input', updateScenario);
        excludeLastInput.addEventListener('change', updateScenario);
    }
    
    // Initial scenario description update
    updateScenarioDescription();
    
    // Initialize view toggle button
    const toggleBtn = document.getElementById('viewToggleBtn');
    const toggleText = document.getElementById('viewToggleText');
    const simplifiedView = document.getElementById('simplifiedView');
    const advancedView = document.getElementById('advancedView');
    if (toggleBtn && toggleText && simplifiedView && advancedView) {
        // Default to simplified view
        currentViewMode = 'simplified';
        toggleText.textContent = 'Advanced View';
        simplifiedView.style.display = 'block';
        advancedView.style.display = 'none';
    }
    
    // Enable run button (always enabled since we just need a number)
            if (runSimulationBtn) {
        runSimulationBtn.disabled = false;
    }
    
    // Run simulation button
    if (runSimulationBtn) {
        runSimulationBtn.addEventListener('click', async () => {
            const numGames = parseInt(document.getElementById('numGames')?.value || '500');
            const betAmount = parseFloat(document.getElementById('betAmount')?.value || '20');
            const entryThreshold = parseFloat(document.getElementById('entryThreshold')?.value || '5');
            const exitThreshold = parseFloat(document.getElementById('exitThreshold')?.value || '2');
            const excludeFirst = parseInt(document.getElementById('excludeFirst')?.value || '60');
            const excludeLast = parseInt(document.getElementById('excludeLast')?.value || '60');
            const useTradeData = document.getElementById('useTradeData')?.checked ?? true;
            const enableFees = document.getElementById('enableFees')?.checked ?? false;
            
            if (!numGames || numGames < 1) {
                showSimulationError('Please enter a valid number of games (1-500)');
                return;
            }
            
            // Show loading and hide export button
            const loadingDiv = document.getElementById('simulationLoading');
            const loadingProgressText = document.getElementById('loadingProgressText');
            const exportButtons = document.getElementById('simulationExportButtons');
            if (loadingDiv) loadingDiv.style.display = 'flex';
            if (exportButtons) exportButtons.style.display = 'none';
            if (runSimulationBtn) runSimulationBtn.disabled = true;
            
            // Generate request ID for progress tracking
            const requestId = `sim_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            // Connect to WebSocket for real-time progress updates
            const progressWebSocket = connectSimulationProgress(requestId, (progress) => {
                if (loadingProgressText) {
                    if (progress.status === 'running' && progress.total > 0) {
                        loadingProgressText.textContent = `Analyzing games: ${progress.current}/${progress.total}`;
                    } else if (progress.status === 'complete') {
                        loadingProgressText.textContent = 'Finalizing results...';
                    } else if (progress.status === 'error') {
                        loadingProgressText.textContent = 'Simulation error occurred';
                    } else {
                        loadingProgressText.textContent = 'Running simulation...';
                    }
                }
            });
            
            try {
                const results = await runBulkSimulation(numGames, entryThreshold, exitThreshold, excludeFirst, excludeLast, betAmount, useTradeData, enableFees, requestId);
                // Render both views (simplified and advanced)
                renderSimplifiedResults(results);
                renderSimulationResults(results);
                // Show the current view mode (default: advanced)
                const simplifiedView = document.getElementById('simplifiedView');
                const advancedView = document.getElementById('advancedView');
                if (simplifiedView && advancedView) {
                    if (currentViewMode === 'simplified') {
                        simplifiedView.style.display = 'block';
                        advancedView.style.display = 'none';
                    } else {
                        simplifiedView.style.display = 'none';
                        advancedView.style.display = 'block';
                    }
                }
            } catch (error) {
                showSimulationError(error.message || 'Failed to run simulation');
            } finally {
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (runSimulationBtn) runSimulationBtn.disabled = false;
            }
        });
    }
}

/**
 * Export simulation results as an image
 */
async function exportSimulationToImage() {
    const container = document.getElementById('simulationResults');
    if (!container) {
        alert('Simulation results not found.');
        return;
    }
    
    // Check if results are visible
    if (container.style.display === 'none') {
        alert('No simulation results to export. Please run a simulation first.');
        return;
    }
    
    // Determine which view is currently visible
    const simplifiedView = document.getElementById('simplifiedView');
    const advancedView = document.getElementById('advancedView');
    let targetContainer = container; // Default to parent container
    const isAdvancedView = advancedView && advancedView.style.display !== 'none';
    
    if (simplifiedView && simplifiedView.style.display !== 'none') {
        // Export simplified view
        targetContainer = simplifiedView;
    } else if (isAdvancedView) {
        // Export advanced view
        targetContainer = advancedView;
    }
    
    try {
        // For advanced view with charts, wait longer and ensure charts are ready
        if (isAdvancedView) {
            // Wait for Chart.js charts to be fully rendered
            // Check if charts exist and are ready
            let chartsReady = false;
            let waitAttempts = 0;
            const maxWaitAttempts = 20; // 2 seconds max wait
            
            while (!chartsReady && waitAttempts < maxWaitAttempts) {
                // Check if charts are initialized and rendered
                const quartilesChartReady = !window.quartilesChart || 
                    (window.quartilesChart && window.quartilesChart.canvas && window.quartilesChart.canvas.width > 0);
                const equityCurveChartReady = !window.equityCurveChart || 
                    (window.equityCurveChart && window.equityCurveChart.canvas && window.equityCurveChart.canvas.width > 0);
                
                chartsReady = quartilesChartReady && equityCurveChartReady;
                
                if (!chartsReady) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    waitAttempts++;
                }
            }
            
            // Additional wait to ensure canvas is fully painted
            await new Promise(resolve => setTimeout(resolve, 300));
        } else {
            // For simplified view, shorter wait is sufficient
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        // Use html2canvas to capture
        if (typeof html2canvas === 'undefined') {
            alert('Image export library not loaded. Please refresh the page.');
            return;
        }
        
        const canvas = await html2canvas(targetContainer, {
            backgroundColor: '#0a0a0f',
            scale: 2,
            useCORS: true,
            logging: false,
            width: targetContainer.scrollWidth,
            height: targetContainer.scrollHeight,
            allowTaint: true,
            // Additional options for better chart rendering
            onclone: function(clonedDoc) {
                // Ensure charts are visible in cloned document
                const clonedContainer = clonedDoc.querySelector('#' + targetContainer.id);
                if (clonedContainer) {
                    // Force visibility of all canvas elements
                    const canvases = clonedContainer.querySelectorAll('canvas');
                    canvases.forEach(canvas => {
                        canvas.style.display = 'block';
                        canvas.style.visibility = 'visible';
                    });
                }
            }
        });
        
        // Convert to blob and download
        canvas.toBlob(function(blob) {
            if (!blob) {
                alert('Failed to create image.');
                return;
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `simulation-results-${new Date().toISOString().split('T')[0]}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 'image/png');
        
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export image: ' + error.message);
    }
}

/**
 * Clear simulation results cache (hard reset)
 */
async function clearSimulationCache() {
    const btn = document.getElementById('clearSimulationCacheBtn');
    if (!btn) return;
    
    // Disable button during operation
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Clearing...';
    
    try {
        const result = await clearSimulationCacheApi();
        btn.textContent = '✓ Cleared!';
        btn.style.color = 'var(--accent-home)';
        
        // Show success message
        if (result.message) {
            console.log(`[SIMULATION_CACHE] ${result.message}`);
        }
        
        // Reset button after 2 seconds
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '';
            btn.disabled = false;
        }, 2000);
    } catch (error) {
        console.error('[SIMULATION_CACHE] Error clearing cache:', error);
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

