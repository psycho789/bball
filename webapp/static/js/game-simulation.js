/**
 * Game detail page simulation module.
 * 
 * Design Pattern: Module Pattern for simulation functionality
 * Algorithm: API calls and DOM manipulation
 * Big O: O(1) for UI operations, O(n) for data processing
 */

let currentGameId = null;

/**
 * Initialize simulation functionality on game detail page.
 */
function initializeGameSimulation(gameId) {
    currentGameId = gameId;
    
    const simSection = document.getElementById('simulationSection');
    const simRunBtn = document.getElementById('simRunBtn');
    
    if (!simSection || !simRunBtn) return;
    
    // Update scenario description when inputs change
    const inputs = ['simBetAmount', 'simEntryThreshold', 'simExitThreshold', 'simExcludeFirst', 'simExcludeLast'];
    inputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('input', updateScenarioDescription);
            input.addEventListener('change', updateScenarioDescription);
        }
    });
    
    // Initial scenario description update
    updateScenarioDescription();
    
    // Run simulation
    simRunBtn.addEventListener('click', async () => {
        await runGameSimulation();
    });
}

/**
 * Update scenario description based on current inputs.
 */
function updateScenarioDescription() {
    const entryThreshold = parseFloat(document.getElementById('simEntryThreshold')?.value || '5');
    const exitThreshold = parseFloat(document.getElementById('simExitThreshold')?.value || '0');
    const excludeFirst = parseInt(document.getElementById('simExcludeFirst')?.value || '0');
    const excludeLast = parseInt(document.getElementById('simExcludeLast')?.value || '0');
    
    const entryDisplay = document.getElementById('simEntryDisplay');
    const exitDisplay = document.getElementById('simExitDisplay');
    const timeFilterDisplay = document.getElementById('simTimeFilterDisplay');
    
    if (entryDisplay) {
        entryDisplay.textContent = entryThreshold.toString();
    }
    
    if (exitDisplay) {
        if (exitThreshold === 0) {
            exitDisplay.textContent = 'the same';
        } else {
            exitDisplay.textContent = `within ${exitThreshold} cents`;
        }
    }
    
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
 * Run simulation for current game.
 */
async function runGameSimulation() {
    if (!currentGameId) {
        console.error('No game ID available for simulation');
        return;
    }
    
    const simRunBtn = document.getElementById('simRunBtn');
    const resultsDiv = document.getElementById('simulationResultsCompact');
    
    if (!simRunBtn || !resultsDiv) return;
    
    const betAmount = parseFloat(document.getElementById('simBetAmount')?.value || '20');
    const entryThreshold = parseFloat(document.getElementById('simEntryThreshold')?.value || '5') / 100;
    const exitThreshold = parseFloat(document.getElementById('simExitThreshold')?.value || '0') / 100;
    const excludeFirst = parseInt(document.getElementById('simExcludeFirst')?.value || '0');
    const excludeLast = parseInt(document.getElementById('simExcludeLast')?.value || '0');
    const useTradeData = document.getElementById('simUseTradeData')?.checked ?? true;
    const enableFees = document.getElementById('simEnableFees')?.checked ?? false;
    
    // Show loading
    simRunBtn.disabled = true;
    simRunBtn.textContent = 'Running...';
    resultsDiv.style.display = 'none';
    
    try {
        // Call simulation API
        const params = new URLSearchParams({
            entry_threshold: entryThreshold.toString(),
            exit_threshold: exitThreshold.toString(),
            exclude_first_seconds: excludeFirst.toString(),
            exclude_last_seconds: excludeLast.toString(),
            bet_amount: betAmount.toString(),
            use_trade_data: useTradeData.toString(),
            enable_fees: enableFees.toString(),
        });
        
        const response = await fetch(`/api/games/${currentGameId}/simulation?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const results = await response.json();
        
        // Display results
        displaySimulationResults(results);
        
    } catch (error) {
        console.error('Error running simulation:', error);
        resultsDiv.innerHTML = `<div style="color: var(--accent-away); padding: 12px;">Error: ${error.message || 'Failed to run simulation'}</div>`;
        resultsDiv.style.display = 'block';
    } finally {
        simRunBtn.disabled = false;
        simRunBtn.textContent = 'Run';
    }
}

/**
 * Display simulation results in compact format.
 */
function displaySimulationResults(results) {
    const resultsDiv = document.getElementById('simulationResultsCompact');
    const totalProfitEl = document.getElementById('simTotalProfitCompact');
    const numTradesEl = document.getElementById('simNumTradesCompact');
    const winRateEl = document.getElementById('simWinRateCompact');
    const avgProfitEl = document.getElementById('simAvgProfitCompact');
    
    if (!resultsDiv) return;
    
    const profit = results.total_profit_dollars || 0;
    const numTrades = results.num_trades || 0;
    const winRate = (results.win_rate || 0) * 100;
    const avgProfit = results.avg_profit_per_trade_dollars || 0;
    
    if (totalProfitEl) {
        totalProfitEl.textContent = `$${profit.toFixed(2)}`;
        totalProfitEl.style.color = profit >= 0 ? 'var(--accent-home)' : 'var(--accent-away)';
    }
    if (numTradesEl) numTradesEl.textContent = numTrades.toString();
    if (winRateEl) {
        winRateEl.textContent = `${winRate.toFixed(1)}%`;
        winRateEl.style.color = winRate >= 50 ? 'var(--accent-home)' : 'var(--accent-away)';
    }
    if (avgProfitEl) {
        avgProfitEl.textContent = `$${avgProfit.toFixed(2)}`;
        avgProfitEl.style.color = avgProfit >= 0 ? 'var(--accent-home)' : 'var(--accent-away)';
    }
    
    resultsDiv.style.display = 'block';
}

// Export to global scope for app.js
window.initializeGameSimulation = initializeGameSimulation;

