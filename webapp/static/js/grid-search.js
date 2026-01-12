/**
 * Grid Search Hyperparameter Optimization Page
 * 
 * Handles grid search form submission, progress tracking, and results rendering.
 */

// Form validation
function validateGridSearchForm() {
    const entryMin = parseFloat(document.getElementById('entryMin').value);
    const entryMax = parseFloat(document.getElementById('entryMax').value);
    const entryStep = parseFloat(document.getElementById('entryStep').value);
    const exitMin = parseFloat(document.getElementById('exitMin').value);
    const exitMax = parseFloat(document.getElementById('exitMax').value);
    const exitStep = parseFloat(document.getElementById('exitStep').value);
    const trainRatio = parseFloat(document.getElementById('trainRatio').value);
    const validRatio = parseFloat(document.getElementById('validRatio').value);
    const testRatio = parseFloat(document.getElementById('testRatio').value);
    
    let isValid = true;
    const errors = [];
    
    // Validate split ratios sum to 1.0
    const ratioSum = trainRatio + validRatio + testRatio;
    if (Math.abs(ratioSum - 1.0) > 0.001) {
        isValid = false;
        const errorEl = document.getElementById('splitRatioError');
        errorEl.textContent = `Split ratios must sum to 1.0 (currently ${ratioSum.toFixed(2)})`;
        errorEl.style.display = 'block';
    } else {
        document.getElementById('splitRatioError').style.display = 'none';
    }
    
    // Validate grid ranges
    if (entryMin <= 0) {
        isValid = false;
        errors.push('Entry min must be > 0');
    }
    if (entryMin >= entryMax) {
        isValid = false;
        errors.push('Entry min must be < entry max');
    }
    if (entryStep <= 0) {
        isValid = false;
        errors.push('Entry step must be > 0');
    }
    if (exitMin < 0) {
        isValid = false;
        errors.push('Exit min must be >= 0');
    }
    if (exitMin >= exitMax) {
        isValid = false;
        errors.push('Exit min must be < exit max');
    }
    if (exitStep <= 0) {
        isValid = false;
        errors.push('Exit step must be > 0');
    }
    
    // Validate thresholds are in valid range (0-1)
    if (entryMin < 0 || entryMax > 1 || exitMin < 0 || exitMax > 1) {
        isValid = false;
        errors.push('Thresholds must be between 0 and 1');
    }
    
    if (!isValid && errors.length > 0) {
        alert('Validation errors:\n' + errors.join('\n'));
    }
    
    return isValid;
}

// Initialize season selector
async function initializeSeasonSelector() {
    console.log('[GridSearch] Initializing season selector...');
    try {
        console.log('[GridSearch] Fetching /api/games/seasons');
        const response = await fetch('/api/games/seasons');
        console.log('[GridSearch] Response status:', response.status, response.ok);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        console.log('[GridSearch] Seasons data:', data);
        const seasons = data.seasons || [];
        console.log('[GridSearch] Found seasons:', seasons);
        
        const seasonSelect = document.getElementById('season');
        if (!seasonSelect) {
            console.error('[GridSearch] Season select element not found');
            return;
        }
        console.log('[GridSearch] Season select element found');
        
        seasonSelect.innerHTML = '';
        
        if (seasons.length === 0) {
            console.warn('[GridSearch] No seasons available');
            seasonSelect.innerHTML = '<option value="">No seasons available</option>';
            return;
        }
        
        seasons.forEach(season => {
            const option = document.createElement('option');
            option.value = season;
            option.textContent = season;
            seasonSelect.appendChild(option);
        });
        
        // Set default to most recent season
        if (seasons.length > 0) {
            seasonSelect.value = seasons[0];
            console.log('[GridSearch] Set default season to:', seasons[0]);
        }
        
        // Enable submit button now that seasons are loaded
        const submitBtn = document.getElementById('runGridSearchBtn');
        if (submitBtn) {
            submitBtn.disabled = false;
            console.log('[GridSearch] Submit button enabled');
        }
    } catch (error) {
        console.error('[GridSearch] Error initializing season selector:', error);
        const seasonSelect = document.getElementById('season');
        if (seasonSelect) {
            seasonSelect.innerHTML = '<option value="">Error loading seasons</option>';
        }
        const errorEl = document.getElementById('seasonError');
        if (errorEl) {
            errorEl.textContent = 'Failed to load seasons. Please refresh the page.';
            errorEl.style.display = 'block';
        }
        // Keep submit button disabled on error
        const submitBtn = document.getElementById('runGridSearchBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
        }
    }
}

// Run grid search
async function runGridSearch() {
    // Validate form
    if (!validateGridSearchForm()) {
        return;
    }
    
    // Collect parameters
    const params = {
        season: document.getElementById('season').value,
        entry_min: parseFloat(document.getElementById('entryMin').value),
        entry_max: parseFloat(document.getElementById('entryMax').value),
        entry_step: parseFloat(document.getElementById('entryStep').value),
        exit_min: parseFloat(document.getElementById('exitMin').value),
        exit_max: parseFloat(document.getElementById('exitMax').value),
        exit_step: parseFloat(document.getElementById('exitStep').value),
        bet_amount: parseFloat(document.getElementById('betAmount').value),
        enable_fees: document.getElementById('enableFees').checked,
        slippage_rate: parseFloat(document.getElementById('slippageRate').value),
        exclude_first_seconds: parseInt(document.getElementById('excludeFirstSeconds').value),
        exclude_last_seconds: parseInt(document.getElementById('excludeLastSeconds').value),
        use_trade_data: document.getElementById('useTradeData').checked,
        train_ratio: parseFloat(document.getElementById('trainRatio').value),
        valid_ratio: parseFloat(document.getElementById('validRatio').value),
        test_ratio: parseFloat(document.getElementById('testRatio').value),
        top_n: parseInt(document.getElementById('topN').value),
        min_trade_count: parseInt(document.getElementById('minTradeCount').value)
    };
    
    // Add max_games if provided (optional parameter)
    const maxGamesInput = document.getElementById('maxGames').value;
    if (maxGamesInput && maxGamesInput.trim() !== '') {
        params.max_games = parseInt(maxGamesInput);
    }
    
    // Store parameters for export
    gridSearchParams = params;
    
    // Show loading indicator
    document.getElementById('gridSearchLoading').style.display = 'flex';
    document.getElementById('runGridSearchBtn').disabled = true;
    document.getElementById('gridSearchResults').style.display = 'none';
    
    try {
        // Build query string (skip undefined/null values for optional parameters)
        const queryParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                queryParams.append(key, value.toString());
            }
        });
        
        // Start grid search
        const response = await fetch(`/api/grid-search/run?${queryParams.toString()}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        const requestId = data.request_id;
        
        // Connect to WebSocket for real-time progress updates
        const progressWebSocket = connectGridSearchProgress(requestId);
    } catch (error) {
        console.error('Error running grid search:', error);
        alert('Error starting grid search: ' + error.message);
        document.getElementById('gridSearchLoading').style.display = 'none';
        document.getElementById('runGridSearchBtn').disabled = false;
    }
}

/**
 * Connect to WebSocket for grid search progress updates.
 * 
 * Design Pattern: WebSocket Handler Pattern
 * Algorithm: O(1) connection, O(1) per update
 * Big O: O(1) for connection operations, O(1) for message handling
 * 
 * @param {string} requestId - Grid search request ID
 * @returns {WebSocket} WebSocket connection (can be used to disconnect)
 */
function connectGridSearchProgress(requestId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/grid-search/${requestId}`;
    
    console.log(`Connecting to grid search progress WebSocket: ${url}`);
    
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
        console.log(`Grid search progress WebSocket connected: requestId=${requestId}`);
    };
    
    ws.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Grid search WebSocket message received:', data);
            
            if (data.type === 'progress') {
                const progress = data.progress;
                console.log('Grid search progress:', progress);
                
                // Update progress indicator
                const current = progress.current || 0;
                const total = progress.total || 1;
                const percent = total > 0 ? Math.round((current / total) * 100) : 0;
                const currentCombo = progress.current_combo || '';
                
                console.log(`Grid search progress update: ${current}/${total} (${percent}%), status=${progress.status}`);
                
                const loadingProgressText = document.getElementById('loadingProgressText');
                if (loadingProgressText) {
                    loadingProgressText.textContent = 
                        `Processing: ${current}/${total} combinations (${percent}%) ${currentCombo ? '- ' + currentCombo : ''}`;
                }
                
                if (progress.status === 'complete') {
                    // Fetch results
                    await fetchAndRenderResults(requestId);
                    // Connection will close automatically
                } else if (progress.status === 'error') {
                    alert('Grid search failed: ' + (progress.error || 'Unknown error'));
                    const loadingDiv = document.getElementById('gridSearchLoading');
                    const runBtn = document.getElementById('runGridSearchBtn');
                    if (loadingDiv) loadingDiv.style.display = 'none';
                    if (runBtn) runBtn.disabled = false;
                    // Connection will close automatically
                }
            } else if (data.type === 'error') {
                console.error('Grid search progress WebSocket error:', data.message);
                alert('Grid search error: ' + data.message);
                const loadingDiv = document.getElementById('gridSearchLoading');
                const runBtn = document.getElementById('runGridSearchBtn');
                if (loadingDiv) loadingDiv.style.display = 'none';
                if (runBtn) runBtn.disabled = false;
            } else if (data.type === 'pong') {
                // Connection health check response
                // No action needed
            }
        } catch (error) {
            console.error('Error parsing grid search progress WebSocket message:', error, event.data);
        }
    };
    
    ws.onerror = (error) => {
        console.error(`Grid search progress WebSocket error for ${requestId}:`, error);
        // Fallback: try HTTP endpoint once
        fetch(`/api/grid-search/progress/${requestId}`)
            .then(response => response.json())
            .then(progress => {
                // Update UI with progress
                const current = progress.current || 0;
                const total = progress.total || 1;
                const percent = total > 0 ? Math.round((current / total) * 100) : 0;
                const currentCombo = progress.current_combo || '';
                const loadingProgressText = document.getElementById('loadingProgressText');
                if (loadingProgressText) {
                    loadingProgressText.textContent = 
                        `Processing: ${current}/${total} combinations (${percent}%) ${currentCombo ? '- ' + currentCombo : ''}`;
                }
            })
            .catch(err => console.error('Fallback HTTP request also failed:', err));
    };
    
    ws.onclose = (event) => {
        console.log(`Grid search progress WebSocket closed for ${requestId}:`, event.code, event.reason);
        // Connection closed - grid search likely completed or errored
        // UI should have been updated by onmessage handler
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

// Fetch and render results
async function fetchAndRenderResults(requestId) {
    try {
        const response = await fetch(`/api/grid-search/results/${requestId}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        const results = await response.json();
        
        // Hide loading indicator
        document.getElementById('gridSearchLoading').style.display = 'none';
        document.getElementById('runGridSearchBtn').disabled = false;
        
        // Show results section
        document.getElementById('gridSearchResults').style.display = 'block';
        
        // Show export buttons
        const exportButtons = document.getElementById('gridSearchExportButtons');
        if (exportButtons) {
            exportButtons.style.display = 'flex';
        }
        
        // Render results
        renderGridSearchResults(results);
    } catch (error) {
        console.error('Error fetching results:', error);
        alert('Error fetching results: ' + error.message);
        document.getElementById('gridSearchLoading').style.display = 'none';
        document.getElementById('runGridSearchBtn').disabled = false;
    }
}

// Render grid search results
// Store grid search parameters for export
let gridSearchParams = null;

/**
 * Export grid search results as an image
 */
async function exportGridSearchToImage() {
    const container = document.getElementById('gridSearchResults');
    if (!container) {
        alert('Grid search results not found.');
        return;
    }
    
    // Check if results are visible
    if (container.style.display === 'none') {
        alert('No grid search results to export. Please run a grid search first.');
        return;
    }
    
    try {
        // Wait for charts/canvases to be fully rendered
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Collect current parameters from form (or use stored params)
        const params = gridSearchParams || {
            season: document.getElementById('season')?.value || 'N/A',
            entry_min: parseFloat(document.getElementById('entryMin')?.value) || 0,
            entry_max: parseFloat(document.getElementById('entryMax')?.value) || 0,
            entry_step: parseFloat(document.getElementById('entryStep')?.value) || 0,
            exit_min: parseFloat(document.getElementById('exitMin')?.value) || 0,
            exit_max: parseFloat(document.getElementById('exitMax')?.value) || 0,
            exit_step: parseFloat(document.getElementById('exitStep')?.value) || 0,
            bet_amount: parseFloat(document.getElementById('betAmount')?.value) || 0,
            enable_fees: document.getElementById('enableFees')?.checked || false,
            slippage_rate: parseFloat(document.getElementById('slippageRate')?.value) || 0,
            exclude_first_seconds: parseInt(document.getElementById('excludeFirstSeconds')?.value) || 0,
            exclude_last_seconds: parseInt(document.getElementById('excludeLastSeconds')?.value) || 0,
            use_trade_data: document.getElementById('useTradeData')?.checked || false,
            train_ratio: parseFloat(document.getElementById('trainRatio')?.value) || 0,
            valid_ratio: parseFloat(document.getElementById('validRatio')?.value) || 0,
            test_ratio: parseFloat(document.getElementById('testRatio')?.value) || 0,
            top_n: parseInt(document.getElementById('topN')?.value) || 0,
            min_trade_count: parseInt(document.getElementById('minTradeCount')?.value) || 0
        };
        
        const maxGamesInput = document.getElementById('maxGames')?.value;
        if (maxGamesInput && maxGamesInput.trim() !== '') {
            params.max_games = parseInt(maxGamesInput);
        }
        
        // Use html2canvas to capture
        if (typeof html2canvas === 'undefined') {
            alert('Image export library not loaded. Please refresh the page.');
            return;
        }
        
        const canvas = await html2canvas(container, {
            backgroundColor: '#0a0a0f',
            scale: 2,
            useCORS: true,
            logging: false,
            width: container.scrollWidth,
            height: container.scrollHeight,
            allowTaint: true,
            // Ensure canvas elements are visible in cloned document and add parameters
            onclone: function(clonedDoc) {
                const clonedContainer = clonedDoc.querySelector('#gridSearchResults');
                if (clonedContainer) {
                    // Force visibility of all canvas elements
                    const canvases = clonedContainer.querySelectorAll('canvas');
                    canvases.forEach(canvas => {
                        canvas.style.display = 'block';
                        canvas.style.visibility = 'visible';
                    });
                    
                    // Create parameters info box at the top
                    const paramsBox = clonedDoc.createElement('div');
                    paramsBox.id = 'exportParamsBox';
                    paramsBox.style.cssText = `
                        background: #1a1a2e;
                        border: 2px solid #2a2a40;
                        border-radius: 8px;
                        padding: 1rem;
                        margin-bottom: 1.5rem;
                        color: #e8e8f0;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 11px;
                        line-height: 1.6;
                    `;
                    
                    // Format parameters text
                    const paramsText = `
                        <div style="font-weight: bold; margin-bottom: 0.5rem; font-size: 12px; color: #00d4aa;">
                            Grid Search Parameters
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;">
                            <div><strong>Season:</strong> ${params.season}</div>
                            <div><strong>Entry Range:</strong> ${params.entry_min.toFixed(3)} - ${params.entry_max.toFixed(3)} (step: ${params.entry_step.toFixed(3)})</div>
                            <div><strong>Exit Range:</strong> ${params.exit_min.toFixed(3)} - ${params.exit_max.toFixed(3)} (step: ${params.exit_step.toFixed(3)})</div>
                            <div><strong>Bet Amount:</strong> $${params.bet_amount.toFixed(2)}</div>
                            <div><strong>Fees:</strong> ${params.enable_fees ? 'Enabled' : 'Disabled'}</div>
                            <div><strong>Slippage Rate:</strong> ${(params.slippage_rate * 100).toFixed(2)}%</div>
                            <div><strong>Exclude First:</strong> ${params.exclude_first_seconds}s</div>
                            <div><strong>Exclude Last:</strong> ${params.exclude_last_seconds}s</div>
                            <div><strong>Data Source:</strong> ${params.use_trade_data ? 'Trade Data' : 'Candlesticks'}</div>
                            <div><strong>Train/Valid/Test:</strong> ${(params.train_ratio * 100).toFixed(0)}% / ${(params.valid_ratio * 100).toFixed(0)}% / ${(params.test_ratio * 100).toFixed(0)}%</div>
                            <div><strong>Top N:</strong> ${params.top_n}</div>
                            <div><strong>Min Trade Count:</strong> ${params.min_trade_count}</div>
                            ${params.max_games ? `<div><strong>Max Games:</strong> ${params.max_games}</div>` : ''}
                        </div>
                    `;
                    paramsBox.innerHTML = paramsText;
                    
                    // Insert at the top of the container
                    const firstChild = clonedContainer.firstChild;
                    if (firstChild) {
                        clonedContainer.insertBefore(paramsBox, firstChild);
                    } else {
                        clonedContainer.appendChild(paramsBox);
                    }
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
            a.download = `grid-search-results-${new Date().toISOString().split('T')[0]}.png`;
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

function renderGridSearchResults(results) {
    // Render final selection
    if (results.final_selection) {
        const fs = results.final_selection;
        document.getElementById('finalSelection').style.display = 'block';
        document.getElementById('finalEntryThreshold').textContent = fs.chosen_params.entry_threshold.toFixed(3);
        document.getElementById('finalExitThreshold').textContent = fs.chosen_params.exit_threshold.toFixed(3);
        
        if (fs.train_metrics) {
            document.getElementById('finalTrainProfit').textContent = 
                '$' + fs.train_metrics.net_profit_dollars.toFixed(2);
        }
        if (fs.valid_metrics) {
            document.getElementById('finalValidProfit').textContent = 
                '$' + fs.valid_metrics.net_profit_dollars.toFixed(2);
        }
        if (fs.test_metrics) {
            document.getElementById('finalTestProfit').textContent = 
                '$' + fs.test_metrics.net_profit_dollars.toFixed(2);
        }
    }
    
    // Render pattern detection
    if (results.pattern_detection) {
        renderPatternSummary(results.pattern_detection);
    }
    
    // Render visualizations
    if (results.visualization_data) {
        renderVisualizations(results.visualization_data);
    }
    
    // Render tables
    if (results.training_results) {
        renderResultsTable('trainingResultsTable', results.training_results, 'Training Results (Top N)');
        // Show export button
        const exportBtn = document.getElementById('exportCsvBtn');
        if (exportBtn) {
            exportBtn.style.display = 'block';
            exportBtn.onclick = () => exportResultsToCsv(results);
        }
    }
}

// Render pattern summary
function renderPatternSummary(patterns) {
    const container = document.getElementById('patternDetectionContent');
    container.innerHTML = '';
    
    if (patterns.error) {
        container.innerHTML = `<p style="color: var(--text-secondary);">Pattern detection error: ${patterns.error}</p>`;
        return;
    }
    
    let html = '<div style="display: grid; gap: 1rem;">';
    
    // Profit-positive region
    if (patterns.profit_positive_boundary) {
        const ppb = patterns.profit_positive_boundary;
        html += `<div class="summary-card" style="padding: 1rem;">
            <strong>Profit-Positive Region:</strong> ${ppb.shape !== 'none' ? 
                `${ppb.entry_thresholds.length} entry thresholds, ${ppb.exit_thresholds.length} exit thresholds (${ppb.shape})` : 
                'None found'}
        </div>`;
    }
    
    // Monotonicity
    if (patterns.monotonicity) {
        const mon = patterns.monotonicity;
        html += `<div class="summary-card" style="padding: 1rem;">
            <strong>Monotonicity:</strong> Entry threshold: ${mon.entry_threshold}, Exit threshold: ${mon.exit_threshold}
        </div>`;
    }
    
    // Robustness
    if (patterns.robustness) {
        const rob = patterns.robustness;
        html += `<div class="summary-card" style="padding: 1rem;">
            <strong>Robustness:</strong> ${rob.type} (${rob.size_category}, ${rob.size} combinations)
        </div>`;
    }
    
    // Stability
    if (patterns.stability) {
        const stab = patterns.stability;
        html += `<div class="summary-card" style="padding: 1rem;">
            <strong>Stability:</strong> Rank correlation: ${stab.rank_correlation ? stab.rank_correlation.toFixed(3) : 'N/A'}
            ${stab.is_stable === false ? '<span style="color: red;"> (UNSTABLE)</span>' : ''}
        </div>`;
    }
    
    html += '</div>';
    container.innerHTML = html;
    document.getElementById('patternDetection').style.display = 'block';
}

// Render visualizations
function renderVisualizations(vizData) {
    console.log('[GridSearch] Rendering visualizations, data keys:', Object.keys(vizData));
    
    // Profit heatmap (TRAIN)
    if (vizData.profit_heatmap_train) {
        console.log('[GridSearch] Rendering TRAIN profit heatmap, sample value:', 
            vizData.profit_heatmap_train.matrix?.[0]?.[0]);
        renderProfitHeatmap(vizData.profit_heatmap_train, 'profitHeatmapTrainCanvas');
    } else {
        console.warn('[GridSearch] Missing profit_heatmap_train data');
    }
    
    // Profit heatmap (VALID)
    if (vizData.profit_heatmap_valid) {
        console.log('[GridSearch] Rendering VALID profit heatmap, sample value:', 
            vizData.profit_heatmap_valid.matrix?.[0]?.[0]);
        renderProfitHeatmap(vizData.profit_heatmap_valid, 'profitHeatmapValidCanvas');
    } else {
        console.warn('[GridSearch] Missing profit_heatmap_valid data');
    }
    
    // Profit factor heatmap (VALID)
    if (vizData.profit_factor_heatmap_valid) {
        console.log('[GridSearch] Rendering VALID profit_factor heatmap, sample value:', 
            vizData.profit_factor_heatmap_valid.matrix?.[0]?.[0]);
        renderProfitHeatmap(vizData.profit_factor_heatmap_valid, 'profitFactorHeatmapCanvas');
    } else {
        console.warn('[GridSearch] Missing profit_factor_heatmap_valid data');
    }
    
    // Marginal effects
    if (vizData.marginal_effects) {
        renderMarginalEffects(vizData.marginal_effects);
    }
    
    // Tradeoff scatter
    if (vizData.tradeoff_scatter) {
        renderTradeoffScatter(vizData.tradeoff_scatter);
    }
}

// Render profit heatmap using custom canvas
function renderProfitHeatmap(data, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data.matrix || !data.entry_thresholds || !data.exit_thresholds) return;
    
    // Set canvas size
    canvas.width = 800;
    canvas.height = 600;
    
    const ctx = canvas.getContext('2d');
    const matrix = data.matrix;
    const entryThresh = data.entry_thresholds;
    const exitThresh = data.exit_thresholds;
    
    if (matrix.length === 0 || entryThresh.length === 0 || exitThresh.length === 0) return;
    
    // Find min/max for color scaling
    let minVal = Infinity;
    let maxVal = -Infinity;
    matrix.forEach(row => {
        row.forEach(val => {
            if (val !== null && val !== undefined) {
                minVal = Math.min(minVal, val);
                maxVal = Math.max(maxVal, val);
            }
        });
    });
    
    // Use a diverging colormap centered at zero (like matplotlib's RdYlGn)
    // This provides better contrast: dark red (low) -> yellow (zero) -> dark green (high)
    function getRdYlGnColor(value, minVal, maxVal) {
        // For diverging colormap, center around zero if we have both positive and negative values
        // Otherwise, use full range but with better color distribution
        const range = maxVal - minVal;
        const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal));
        
        let normalized;
        if (minVal < 0 && maxVal > 0) {
            // Center around zero for diverging colormap
            normalized = (value + absMax) / (2 * absMax);
        } else {
            // All positive or all negative - use standard normalization
            normalized = (value - minVal) / range;
        }
        
        // Clamp to [0, 1]
        normalized = Math.max(0, Math.min(1, normalized));
        
        // RdYlGn colormap approximation (Red-Yellow-Green diverging)
        // Dark Red: RGB(165, 0, 38) for very low values
        // Red: RGB(215, 48, 39) 
        // Yellow: RGB(255, 255, 191) for middle values  
        // Light Green: RGB(145, 207, 96)
        // Dark Green: RGB(26, 152, 80) for high values
        
        let r, g, b;
        
        if (normalized < 0.25) {
            // Dark Red to Red
            const t = normalized / 0.25;
            r = Math.round(165 + (215 - 165) * t);
            g = Math.round(0 + (48 - 0) * t);
            b = Math.round(38 + (39 - 38) * t);
        } else if (normalized < 0.5) {
            // Red to Yellow
            const t = (normalized - 0.25) / 0.25;
            r = Math.round(215 + (255 - 215) * t);
            g = Math.round(48 + (255 - 48) * t);
            b = Math.round(39 + (191 - 39) * t);
        } else if (normalized < 0.75) {
            // Yellow to Light Green
            const t = (normalized - 0.5) / 0.25;
            r = Math.round(255 - (255 - 145) * t);
            g = Math.round(255 - (255 - 207) * t);
            b = Math.round(191 + (96 - 191) * t);
        } else {
            // Light Green to Dark Green
            const t = (normalized - 0.75) / 0.25;
            r = Math.round(145 - (145 - 26) * t);
            g = Math.round(207 - (207 - 152) * t);
            b = Math.round(96 + (80 - 96) * t);
        }
        
        return `rgb(${r}, ${g}, ${b})`;
    }
    
    const cellWidth = canvas.width / entryThresh.length;
    const cellHeight = canvas.height / exitThresh.length;
    
    // Draw heatmap
    matrix.forEach((row, exitIdx) => {
        row.forEach((val, entryIdx) => {
            if (val === null || val === undefined) {
                ctx.fillStyle = '#f0f0f0';
            } else {
                ctx.fillStyle = getRdYlGnColor(val, minVal, maxVal);
            }
            ctx.fillRect(entryIdx * cellWidth, (exitThresh.length - 1 - exitIdx) * cellHeight, cellWidth, cellHeight);
        });
    });
    
    // Mark chosen parameters
    if (data.chosen_entry !== undefined && data.chosen_exit !== undefined) {
        const entryIdx = entryThresh.indexOf(data.chosen_entry);
        const exitIdx = exitThresh.indexOf(data.chosen_exit);
        if (entryIdx >= 0 && exitIdx >= 0) {
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 3;
            ctx.strokeRect(
                entryIdx * cellWidth + 2,
                (exitThresh.length - 1 - exitIdx) * cellHeight + 2,
                cellWidth - 4,
                cellHeight - 4
            );
        }
    }
    
    // Add axis labels
    ctx.fillStyle = '#333';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    entryThresh.forEach((val, idx) => {
        if (idx % Math.ceil(entryThresh.length / 10) === 0) {
            ctx.fillText(val.toFixed(3), idx * cellWidth + cellWidth / 2, canvas.height - 5);
        }
    });
    
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    exitThresh.forEach((val, idx) => {
        if (idx % Math.ceil(exitThresh.length / 10) === 0) {
            ctx.fillText(val.toFixed(3), 0, -idx * cellHeight - cellHeight / 2);
        }
    });
    ctx.restore();
}

// Render marginal effects using Chart.js
function renderMarginalEffects(data) {
    const canvas = document.getElementById('marginalEffectsCanvas');
    if (!canvas || typeof Chart === 'undefined' || !data.entry || !data.exit) return;
    
    // Destroy existing chart if it exists
    if (window.marginalEffectsChart && typeof window.marginalEffectsChart.destroy === 'function') {
        try {
            window.marginalEffectsChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing marginal effects chart:', e);
        }
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Create datasets for entry and exit marginal effects
    const entryData = data.entry.thresholds.map((thresh, idx) => ({
        x: thresh,
        y: data.entry.mean[idx],
        yMin: data.entry.mean[idx] - (data.entry.std[idx] || 0),
        yMax: data.entry.mean[idx] + (data.entry.std[idx] || 0)
    }));
    
    const exitData = data.exit.thresholds.map((thresh, idx) => ({
        x: thresh,
        y: data.exit.mean[idx],
        yMin: data.exit.mean[idx] - (data.exit.std[idx] || 0),
        yMax: data.exit.mean[idx] + (data.exit.std[idx] || 0)
    }));
    
    try {
        window.marginalEffectsChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Entry Threshold Effect',
                        data: entryData.map(d => ({ x: d.x, y: d.y })),
                        borderColor: '#00d4aa',
                        backgroundColor: 'rgba(0, 212, 170, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Exit Threshold Effect',
                        data: exitData.map(d => ({ x: d.x, y: d.y })),
                        borderColor: '#7c3aed',
                        backgroundColor: 'rgba(124, 58, 237, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#e8e8f0'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: 'Threshold',
                            color: '#888899'
                        },
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Mean Profit ($)',
                            color: '#888899'
                        },
                        ticks: {
                            color: '#888899',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: { color: '#2a2a40' }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error rendering marginal effects chart:', error);
    }
}

// Render tradeoff scatter using Chart.js
function renderTradeoffScatter(data) {
    const canvas = document.getElementById('tradeoffScatterCanvas');
    if (!canvas || typeof Chart === 'undefined' || !data.num_trades || !data.net_profit) return;
    
    // Destroy existing chart if it exists
    if (window.tradeoffScatterChart && typeof window.tradeoffScatterChart.destroy === 'function') {
        try {
            window.tradeoffScatterChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing tradeoff scatter chart:', e);
        }
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Create scatter data with color coding by entry threshold
    const scatterData = data.num_trades.map((trades, idx) => ({
        x: trades,
        y: data.net_profit[idx],
        entry: data.entry_threshold[idx]
    }));
    
    // Group by entry threshold for color coding
    const entryGroups = {};
    scatterData.forEach(point => {
        const entry = point.entry.toFixed(3);
        if (!entryGroups[entry]) {
            entryGroups[entry] = [];
        }
        entryGroups[entry].push(point);
    });
    
    const datasets = Object.entries(entryGroups).map(([entry, points]) => ({
        label: `Entry: ${entry}`,
        data: points,
        backgroundColor: `hsl(${(parseFloat(entry) * 360) % 360}, 70%, 50%)`,
        borderColor: `hsl(${(parseFloat(entry) * 360) % 360}, 70%, 50%)`,
        pointRadius: 4,
        pointHoverRadius: 6
    }));
    
    try {
        window.tradeoffScatterChart = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#e8e8f0'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                return `Trades: ${point.x}, Profit: $${point.y.toFixed(2)}, Entry: ${point.entry.toFixed(3)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: 'Number of Trades',
                            color: '#888899'
                        },
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Net Profit ($)',
                            color: '#888899'
                        },
                        ticks: {
                            color: '#888899',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: { color: '#2a2a40' }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error rendering tradeoff scatter chart:', error);
    }
}

// Render results table
function renderResultsTable(containerId, results, title) {
    const container = document.getElementById(containerId);
    if (!container || !results || results.length === 0) return;
    
    // Create table
    let html = '<table class="results-table" style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr>';
    
    // Get columns from first result
    const columns = Object.keys(results[0]);
    columns.forEach(col => {
        html += `<th style="padding: 0.5rem; border: 1px solid var(--border-color); text-align: left;">${col.replace(/_/g, ' ')}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Add rows
    results.forEach(result => {
        html += '<tr>';
        columns.forEach(col => {
            const value = result[col];
            const displayValue = typeof value === 'number' ? 
                (col.includes('profit') || col.includes('amount') ? '$' + value.toFixed(2) : 
                 col.includes('rate') || col.includes('ratio') ? (value * 100).toFixed(2) + '%' :
                 value.toFixed(3)) : 
                value;
            html += `<td style="padding: 0.5rem; border: 1px solid var(--border-color);">${displayValue}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// Export results to CSV
function exportResultsToCsv(results) {
    try {
        // Collect all data to export
        const csvRows = [];
        
        // Add final selection summary
        if (results.final_selection) {
            csvRows.push(['=== Final Selection ===']);
            csvRows.push(['Metric', 'Value']);
            const fs = results.final_selection;
            csvRows.push(['Entry Threshold', fs.chosen_params.entry_threshold]);
            csvRows.push(['Exit Threshold', fs.chosen_params.exit_threshold]);
            if (fs.train_metrics) {
                csvRows.push(['Train Profit ($)', fs.train_metrics.net_profit_dollars]);
            }
            if (fs.valid_metrics) {
                csvRows.push(['Valid Profit ($)', fs.valid_metrics.net_profit_dollars]);
            }
            if (fs.test_metrics) {
                csvRows.push(['Test Profit ($)', fs.test_metrics.net_profit_dollars]);
            }
            csvRows.push([]); // Empty row
        }
        
        // Add training results
        if (results.training_results && results.training_results.length > 0) {
            csvRows.push(['=== Training Results ===']);
            const columns = Object.keys(results.training_results[0]);
            csvRows.push(columns); // Header row
            
            results.training_results.forEach(result => {
                const row = columns.map(col => {
                    const value = result[col];
                    return value !== null && value !== undefined ? value : '';
                });
                csvRows.push(row);
            });
            csvRows.push([]); // Empty row
        }
        
        // Add validation results (if user wants them later)
        if (results.validation_results && results.validation_results.length > 0) {
            csvRows.push(['=== Validation Results ===']);
            const columns = Object.keys(results.validation_results[0]);
            csvRows.push(columns); // Header row
            
            results.validation_results.forEach(result => {
                const row = columns.map(col => {
                    const value = result[col];
                    return value !== null && value !== undefined ? value : '';
                });
                csvRows.push(row);
            });
            csvRows.push([]); // Empty row
        }
        
        // Add test results (if user wants them later)
        if (results.test_results && results.test_results.length > 0) {
            csvRows.push(['=== Test Results ===']);
            const columns = Object.keys(results.test_results[0]);
            csvRows.push(columns); // Header row
            
            results.test_results.forEach(result => {
                const row = columns.map(col => {
                    const value = result[col];
                    return value !== null && value !== undefined ? value : '';
                });
                csvRows.push(row);
            });
        }
        
        // Convert to CSV string
        const csvContent = csvRows.map(row => {
            return row.map(cell => {
                // Escape quotes and wrap in quotes if contains comma, quote, or newline
                const cellStr = String(cell);
                if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
                    return '"' + cellStr.replace(/"/g, '""') + '"';
                }
                return cellStr;
            }).join(',');
        }).join('\n');
        
        // Create download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `grid_search_results_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error exporting to CSV:', error);
        alert('Error exporting to CSV: ' + error.message);
    }
}

// Initialize grid search page
function initializeGridSearchPage() {
    console.log('[GridSearch] Initializing grid search page...');
    
    // Disable submit button until seasons are loaded
    const submitBtn = document.getElementById('runGridSearchBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        console.log('[GridSearch] Submit button disabled until seasons load');
    }
    
    // Check if elements exist
    const seasonSelect = document.getElementById('season');
    const form = document.getElementById('gridSearchForm');
    console.log('[GridSearch] Season select exists:', !!seasonSelect);
    console.log('[GridSearch] Form exists:', !!form);
    
    // Initialize season selector
    if (seasonSelect) {
        initializeSeasonSelector();
    } else {
        console.error('[GridSearch] Season select element not found, retrying in 100ms...');
        setTimeout(() => {
            const retrySelect = document.getElementById('season');
            if (retrySelect) {
                console.log('[GridSearch] Season select found on retry');
                initializeSeasonSelector();
            } else {
                console.error('[GridSearch] Season select still not found after retry');
            }
        }, 100);
    }
    
    // Set up form submission
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            runGridSearch();
        });
    }
    
    // Set up validation on input change for split ratios
    ['trainRatio', 'validRatio', 'testRatio'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', validateGridSearchForm);
        }
    });
}

// Export for use by routing
if (typeof window !== 'undefined') {
    window.initializeGridSearchPage = initializeGridSearchPage;
    window.exportGridSearchToImage = exportGridSearchToImage;
}

