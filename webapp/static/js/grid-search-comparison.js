/**
 * Grid Search Model Comparison Page
 * 
 * Design Pattern: Module Pattern for page-specific functionality
 * Algorithm: O(n × m) where n = models (5), m = visualization data per model
 * Big O: O(n × w × h) for heatmap rendering where w = entry thresholds, h = exit thresholds
 */

let gridSearchComparisonData = null;

/**
 * Load grid search comparison data from backend
 */
async function loadGridSearchComparison() {
    const view = document.getElementById('gridSearchComparisonView');
    const loading = document.getElementById('comparisonLoading');
    const summary = document.getElementById('comparisonSummary');
    const heatmaps = document.getElementById('comparisonHeatmaps');
    const detailed = document.getElementById('detailedMetrics');
    const charts = document.getElementById('comparisonCharts');
    
    if (!view) return;
    
    try {
        // Show loading indicator
        if (loading) loading.style.display = 'flex';
        if (summary) summary.style.display = 'none';
        const parameters = document.getElementById('gridSearchParameters');
        if (heatmaps) heatmaps.style.display = 'none';
        if (detailed) detailed.style.display = 'none';
        if (charts) charts.style.display = 'none';
        if (parameters) parameters.style.display = 'none';
        
        const response = await fetch('/api/grid-search/comparison');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        gridSearchComparisonData = data;
        
        // Hide loading, show sections
        if (loading) loading.style.display = 'none';
        
        // Render all sections
        renderComparisonSummary(data);
        renderGridSearchParameters(data);
        renderComparisonHeatmaps(data);
        renderComparisonCharts(data);
        renderDetailedMetrics(data);
        
    } catch (error) {
        console.error('Error loading grid search comparison:', error);
        if (loading) loading.style.display = 'none';
        
        const errorHtml = `
            <div class="error-message" style="padding: 2rem; text-align: center;">
                <p style="color: var(--text-error); margin-bottom: 1rem;">Error loading comparison data: ${error.message}</p>
                <button class="btn-primary" onclick="loadGridSearchComparison()">Retry</button>
                <p style="margin-top: 1rem; color: var(--text-secondary); font-size: 0.875rem;">
                    Make sure you've run the comparison script:<br>
                    <code>python3 scripts/trade/compare_grid_search_models.py</code>
                </p>
            </div>
        `;
        if (summary) {
            summary.innerHTML = errorHtml;
            summary.style.display = 'block';
        }
    }
}

/**
 * Render comparison summary table
 */
function renderComparisonSummary(data) {
    const container = document.getElementById('summaryTable');
    if (!container || !data.models) return;
    
    const models = data.models;
    
    // Find baseline (ESPN model)
    const baseline = models.find(m => m.model_name === 'ESPN (default)');
    const baselineProfit = baseline?.test_metrics?.net_profit_dollars;
    
    // Build table HTML
    let html = `
        <table class="results-table" style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: var(--bg-secondary);">
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: left;">Model</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Test Profit</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Improvement</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Trades</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Win Rate</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Entry</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Exit</th>
                    <th style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">Profit/Trade</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    // Sort by test profit (descending)
    const sortedModels = [...models].sort((a, b) => {
        const profitA = a.test_metrics?.net_profit_dollars || 0;
        const profitB = b.test_metrics?.net_profit_dollars || 0;
        return profitB - profitA;
    });
    
    sortedModels.forEach(model => {
        const testMetrics = model.test_metrics || {};
        const chosenParams = model.chosen_params || {};
        
        const profit = testMetrics.net_profit_dollars;
        const trades = testMetrics.num_trades;
        const winRate = testMetrics.win_rate;
        const profitPerTrade = testMetrics.avg_net_profit_per_trade;
        const entry = chosenParams.entry_threshold;
        const exit = chosenParams.exit_threshold;
        
        // Calculate improvement
        let improvement = '';
        if (baselineProfit && baselineProfit !== 0 && model.model_name !== 'ESPN (default)') {
            const improvementPct = ((profit - baselineProfit) / Math.abs(baselineProfit)) * 100;
            improvement = `${improvementPct >= 0 ? '+' : ''}${improvementPct.toFixed(1)}%`;
        } else if (model.model_name === 'ESPN (default)') {
            improvement = '(baseline)';
        }
        
        // Format values
        const profitStr = profit !== undefined ? `$${profit.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}` : 'N/A';
        const winRateStr = winRate !== undefined ? `${(winRate * 100).toFixed(1)}%` : 'N/A';
        const entryStr = entry !== undefined ? entry.toFixed(3).replace(/\.?0+$/, '') : 'N/A';
        const exitStr = exit !== undefined ? exit.toFixed(3).replace(/\.?0+$/, '') : 'N/A';
        const profitPerTradeStr = profitPerTrade !== undefined ? `$${profitPerTrade.toFixed(2)}` : 'N/A';
        
        // Highlight best profit
        const isBest = sortedModels[0] === model;
        const rowStyle = isBest ? 'background: rgba(124, 58, 237, 0.1);' : '';
        
        html += `
            <tr style="${rowStyle}">
                <td style="padding: 0.75rem; border: 1px solid var(--border-color);"><strong>${model.model_name}</strong></td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${profitStr}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right; color: ${improvement.startsWith('+') ? 'var(--success)' : improvement.startsWith('-') ? 'var(--error)' : 'var(--text-secondary)'};">${improvement}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${trades !== undefined ? trades : 'N/A'}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${winRateStr}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${entryStr}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${exitStr}</td>
                <td style="padding: 0.75rem; border: 1px solid var(--border-color); text-align: right;">${profitPerTradeStr}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
    document.getElementById('comparisonSummary').style.display = 'block';
}

/**
 * Render grid search parameters from metadata
 */
function renderGridSearchParameters(data) {
    const container = document.getElementById('parametersContent');
    if (!container || !data.models || data.models.length === 0) return;
    
    // Get parameters from first model's metadata (all should be the same)
    const firstModel = data.models[0];
    const args = firstModel.metadata?.args;
    
    if (!args) {
        container.innerHTML = '<p style="color: var(--text-secondary);">Parameters not available in metadata.</p>';
        document.getElementById('gridSearchParameters').style.display = 'block';
        return;
    }
    
    // Format parameters - be careful with integers vs floats
    const formatValue = (val) => {
        if (val === null || val === undefined) return 'N/A';
        if (typeof val === 'boolean') return val ? 'Yes' : 'No';
        if (typeof val === 'number') {
            // For integers, return as-is
            if (Number.isInteger(val)) {
                return val.toString();
            }
            // For floats, remove trailing zeros after decimal point only
            return val.toString().replace(/\.0+$/, '');
        }
        return String(val);
    };
    
    const html = `
        <div style="background: var(--bg-card); padding: 1rem 1.5rem; border-radius: 8px; border: 1px solid var(--border-color);">
            <div style="display: flex; flex-wrap: wrap; gap: 1.5rem 2rem; font-size: 0.875rem;">
                <div><span style="color: var(--text-secondary);">Entry:</span> <strong>${formatValue(args.entry_min)} - ${formatValue(args.entry_max)} (step ${formatValue(args.entry_step)})</strong></div>
                <div><span style="color: var(--text-secondary);">Exit:</span> <strong>${formatValue(args.exit_min)} - ${formatValue(args.exit_max)} (step ${formatValue(args.exit_step)})</strong></div>
                <div><span style="color: var(--text-secondary);">Fees:</span> <strong>${formatValue(args.enable_fees)}</strong></div>
                <div><span style="color: var(--text-secondary);">Slippage:</span> <strong>${formatValue(args.slippage_rate)}</strong></div>
                <div><span style="color: var(--text-secondary);">Min Trades:</span> <strong>${formatValue(args.min_trade_count)}</strong></div>
                <div><span style="color: var(--text-secondary);">Split:</span> <strong>${formatValue(args.train_ratio)}/${formatValue(args.valid_ratio)}/${formatValue(args.test_ratio)}</strong></div>
                <div><span style="color: var(--text-secondary);">Exclude:</span> <strong>${formatValue(args.exclude_first_seconds)}s/${formatValue(args.exclude_last_seconds)}s</strong></div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
    document.getElementById('gridSearchParameters').style.display = 'block';
}

/**
 * Calculate global min/max across all models for synchronized heatmap scales
 */
function calculateGlobalScale(allHeatmapData) {
    let globalMin = Infinity;
    let globalMax = -Infinity;
    
    allHeatmapData.forEach(modelData => {
        if (modelData && modelData.matrix) {
            modelData.matrix.forEach(row => {
                row.forEach(val => {
                    if (val !== null && val !== undefined && !isNaN(val)) {
                        globalMin = Math.min(globalMin, val);
                        globalMax = Math.max(globalMax, val);
                    }
                });
            });
        }
    });
    
    // If no valid values found, return default range
    if (globalMin === Infinity || globalMax === -Infinity) {
        return { min: 0, max: 1000 };
    }
    
    return { min: globalMin, max: globalMax };
}

/**
 * Render profit heatmap with synchronized scale
 * Reuses logic from grid-search.js but accepts global scale
 */
function renderProfitHeatmapWithScale(data, canvasId, globalScale) {
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
    
    // Use global scale instead of calculating from this matrix
    const minVal = globalScale.min;
    const maxVal = globalScale.max;
    
    // Color mapping function (same as grid-search.js)
    function getRdYlGnColor(value, minVal, maxVal) {
        const range = maxVal - minVal;
        const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal));
        
        let normalized;
        if (minVal < 0 && maxVal > 0) {
            normalized = (value + absMax) / (2 * absMax);
        } else {
            normalized = (value - minVal) / range;
        }
        
        normalized = Math.max(0, Math.min(1, normalized));
        
        let r, g, b;
        if (normalized < 0.25) {
            const t = normalized / 0.25;
            r = Math.round(165 + (215 - 165) * t);
            g = Math.round(0 + (48 - 0) * t);
            b = Math.round(38 + (39 - 38) * t);
        } else if (normalized < 0.5) {
            const t = (normalized - 0.25) / 0.25;
            r = Math.round(215 + (255 - 215) * t);
            g = Math.round(48 + (255 - 48) * t);
            b = Math.round(39 + (191 - 39) * t);
        } else if (normalized < 0.75) {
            const t = (normalized - 0.5) / 0.25;
            r = Math.round(255 - (255 - 145) * t);
            g = Math.round(255 - (255 - 207) * t);
            b = Math.round(191 + (96 - 191) * t);
        } else {
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
    
    // Add axis labels (simplified for space)
    ctx.fillStyle = '#333';
    ctx.font = '10px Arial';
    ctx.textAlign = 'center';
    const labelStep = Math.max(1, Math.floor(entryThresh.length / 8));
    entryThresh.forEach((val, idx) => {
        if (idx % labelStep === 0) {
            ctx.fillText(val.toFixed(2), idx * cellWidth + cellWidth / 2, canvas.height - 5);
        }
    });
}

/**
 * Render comparison heatmaps side-by-side
 */
function renderComparisonHeatmaps(data) {
    if (!data.models || !data.visualization_data) return;
    
    const models = data.models;
    // visualization_data is an object keyed by model_name
    const vizData = data.visualization_data;
    
    // Render all three heatmap types
    renderHeatmapType(models, vizData, 'profit_heatmap_train', 'heatmapGridTrain', 'Training Set');
    renderHeatmapType(models, vizData, 'profit_heatmap_valid', 'heatmapGridValid', 'Validation Set');
    renderHeatmapType(models, vizData, 'profit_factor_heatmap_valid', 'heatmapGridFactor', 'Profit Factor (Validation Set)');
    
    document.getElementById('comparisonHeatmaps').style.display = 'block';
}

/**
 * Render a specific heatmap type for all models
 */
function renderHeatmapType(models, vizData, heatmapKey, containerId, titleSuffix) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Collect all heatmap data for this type
    const allHeatmapData = [];
    models.forEach(model => {
        const modelViz = vizData[model.model_name];
        if (modelViz && modelViz[heatmapKey]) {
            allHeatmapData.push(modelViz[heatmapKey]);
        }
    });
    
    if (allHeatmapData.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary);">No data available for this heatmap type.</p>';
        return;
    }
    
    // Calculate global scale for this heatmap type
    const globalScale = calculateGlobalScale(allHeatmapData);
    
    // Clear container
    container.innerHTML = '';
    
    // Render heatmap for each model
    models.forEach((model, index) => {
        const modelViz = vizData[model.model_name];
        if (!modelViz || !modelViz[heatmapKey]) {
            console.warn(`No ${heatmapKey} data for model: ${model.model_name}`);
            return;
        }
        
        const heatmapData = modelViz[heatmapKey];
        
        // Create container for this model's heatmap
        const modelContainer = document.createElement('div');
        modelContainer.className = 'model-heatmap-container';
        
        const title = document.createElement('h5');
        title.textContent = model.model_name;
        modelContainer.appendChild(title);
        
        const canvas = document.createElement('canvas');
        const canvasId = `heatmap-${heatmapKey}-${index}-${model.model_name.replace(/\s+/g, '-')}`;
        canvas.id = canvasId;
        
        // Add click handler to open modal
        canvas.addEventListener('click', () => {
            openHeatmapModal(heatmapData, `${model.model_name} - ${titleSuffix}`, globalScale);
        });
        
        // Add "Click to enlarge" hint
        const hint = document.createElement('div');
        hint.className = 'heatmap-hint';
        hint.textContent = 'Click to enlarge';
        hint.style.cssText = 'text-align: center; color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.5rem; font-style: italic;';
        
        modelContainer.appendChild(canvas);
        modelContainer.appendChild(hint);
        container.appendChild(modelContainer);
        
        // Render heatmap with synchronized scale
        renderProfitHeatmapWithScale(heatmapData, canvas.id, globalScale);
    });
}

/**
 * Render detailed metrics for each model
 */
function renderDetailedMetrics(data) {
    const container = document.getElementById('detailedMetricsContent');
    if (!container || !data.models) return;
    
    let html = '<div style="display: grid; gap: 1.5rem;">';
    
    data.models.forEach(model => {
        const testMetrics = model.test_metrics || {};
        const validMetrics = model.valid_metrics || {};
        const trainMetrics = model.train_metrics || {};
        const chosenParams = model.chosen_params || {};
        
        html += `
            <div class="summary-card" style="background: var(--card-bg); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                <h4 style="margin: 0 0 0.75rem 0; font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${model.model_name}</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 1.5rem 2rem; font-size: 0.875rem;">
                    <div><span style="color: var(--text-secondary);">Test Profit:</span> <strong>$${testMetrics.net_profit_dollars?.toFixed(2) || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Test Trades:</span> <strong>${testMetrics.num_trades || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Test Win Rate:</span> <strong>${testMetrics.win_rate ? (testMetrics.win_rate * 100).toFixed(1) + '%' : 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Profit Factor:</span> <strong>${testMetrics.profit_factor?.toFixed(2) || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Max Drawdown:</span> <strong>$${testMetrics.max_drawdown?.toFixed(2) || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Entry:</span> <strong>${chosenParams.entry_threshold?.toFixed(3) || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-secondary);">Exit:</span> <strong>${chosenParams.exit_threshold?.toFixed(3) || 'N/A'}</strong></div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
    document.getElementById('detailedMetrics').style.display = 'block';
}

/**
 * Render comparison charts (marginal effects and tradeoff scatter)
 */
function renderComparisonCharts(data) {
    if (!data.models || !data.visualization_data) return;
    
    const models = data.models;
    const vizData = data.visualization_data;
    
    // Color palette for models
    const modelColors = {
        'ESPN (default)': '#7c3aed',
        'logreg_platt': '#ef4444',
        'logreg_isotonic': '#f59e0b',
        'catboost_platt': '#10b981',
        'catboost_isotonic': '#3b82f6'
    };
    
    // Render marginal effects chart
    if (typeof Chart !== 'undefined') {
        renderMarginalEffectsComparison(models, vizData, modelColors);
        renderTradeoffScatterComparison(models, vizData, modelColors);
    }
    
    document.getElementById('comparisonCharts').style.display = 'block';
}

/**
 * Render marginal effects chart with all models
 */
function renderMarginalEffectsComparison(models, vizData, modelColors) {
    const canvas = document.getElementById('marginalEffectsCanvas');
    if (!canvas) return;
    
    // Destroy existing chart if it exists
    if (window.marginalEffectsComparisonChart && typeof window.marginalEffectsComparisonChart.destroy === 'function') {
        try {
            window.marginalEffectsComparisonChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing marginal effects chart:', e);
        }
    }
    
    const datasets = [];
    
    models.forEach(model => {
        const modelViz = vizData[model.model_name];
        if (!modelViz || !modelViz.marginal_effects) return;
        
        const marginal = modelViz.marginal_effects;
        const color = modelColors[model.model_name] || '#888888';
        
        // Entry threshold marginal effects
        if (marginal.entry && marginal.entry.thresholds && marginal.entry.mean) {
            datasets.push({
                label: `${model.model_name} - Entry`,
                data: marginal.entry.thresholds.map((t, i) => ({
                    x: t,
                    y: marginal.entry.mean[i]
                })),
                borderColor: color,
                backgroundColor: color + '40',
                pointRadius: 4,
                showLine: true,
                tension: 0.1
            });
        }
        
        // Exit threshold marginal effects
        if (marginal.exit && marginal.exit.thresholds && marginal.exit.mean) {
            datasets.push({
                label: `${model.model_name} - Exit`,
                data: marginal.exit.thresholds.map((t, i) => ({
                    x: t,
                    y: marginal.exit.mean[i]
                })),
                borderColor: color,
                backgroundColor: color + '40',
                borderDash: [5, 5],
                pointRadius: 4,
                showLine: true,
                tension: 0.1
            });
        }
    });
    
    if (datasets.length === 0) return;
    
    const ctx = canvas.getContext('2d');
    window.marginalEffectsComparisonChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 2.5,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Threshold Value',
                        color: '#888899'
                    },
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Average Profit ($)',
                        color: '#888899'
                    },
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#888899' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render tradeoff scatter plot with all models
 */
function renderTradeoffScatterComparison(models, vizData, modelColors) {
    const canvas = document.getElementById('tradeoffScatterCanvas');
    if (!canvas) return;
    
    // Destroy existing chart if it exists
    if (window.tradeoffScatterComparisonChart && typeof window.tradeoffScatterComparisonChart.destroy === 'function') {
        try {
            window.tradeoffScatterComparisonChart.destroy();
        } catch (e) {
            console.warn('Error destroying existing tradeoff scatter chart:', e);
        }
    }
    
    const datasets = [];
    
    models.forEach(model => {
        const modelViz = vizData[model.model_name];
        if (!modelViz || !modelViz.tradeoff_scatter) return;
        
        const scatter = modelViz.tradeoff_scatter;
        const color = modelColors[model.model_name] || '#888888';
        
        if (scatter.num_trades && scatter.net_profit) {
            datasets.push({
                label: model.model_name,
                data: scatter.num_trades.map((trades, i) => ({
                    x: trades,
                    y: scatter.net_profit[i]
                })),
                borderColor: color,
                backgroundColor: color + '80',
                pointRadius: 5,
                pointHoverRadius: 7
            });
        }
    });
    
    if (datasets.length === 0) return;
    
    const ctx = canvas.getContext('2d');
    window.tradeoffScatterComparisonChart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 2.5,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Number of Trades',
                        color: '#888899'
                    },
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Net Profit ($)',
                        color: '#888899'
                    },
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#888899' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.x} trades, $${context.parsed.y.toFixed(2)} profit`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Export grid search comparison to HTML file
 */
async function exportGridSearchComparisonToHTML() {
    if (!gridSearchComparisonData) {
        alert('No comparison data available. Please wait for the page to load.');
        return;
    }
    
    try {
        const view = document.getElementById('gridSearchComparisonView');
        if (!view) {
            throw new Error('Comparison view not found');
        }
        
        // Fetch CSS content
        const cssResponse = await fetch('/static/css/styles.css');
        const cssContent = await cssResponse.text();
        
        // Get container HTML (clone to avoid modifying original)
        const viewClone = view.cloneNode(true);
        // Remove loading indicator
        const loading = viewClone.querySelector('#comparisonLoading');
        if (loading) loading.style.display = 'none';
        // Remove export buttons (not needed in exported HTML)
        const exportButtons = viewClone.querySelector('.export-buttons');
        if (exportButtons) exportButtons.remove();
        // Show all sections
        const sections = viewClone.querySelectorAll('.results-section');
        sections.forEach(section => section.style.display = 'block');
        
        // Add export timestamp to page header
        const pageHeader = viewClone.querySelector('.page-header');
        if (pageHeader) {
            const subtitle = pageHeader.querySelector('.page-header-subtitle');
            if (subtitle) {
                // Check if timestamp already exists (avoid duplicates)
                const existingTimestamp = pageHeader.querySelector('.export-timestamp');
                if (!existingTimestamp) {
                    const timestamp = document.createElement('p');
                    timestamp.className = 'export-timestamp';
                    timestamp.style.cssText = 'color: var(--text-muted); font-size: 0.75rem; margin-top: 8px;';
                    timestamp.textContent = `Exported on ${new Date().toLocaleString()}`;
                    subtitle.parentNode.insertBefore(timestamp, subtitle.nextSibling);
                }
            }
        }
        
        // Get modal HTML from template (it's outside the view, so get it separately)
        const modalElement = document.getElementById('heatmapModal');
        const modalHtml = modalElement ? modalElement.outerHTML : '';
        
        // Get modal CSS from template style tag
        const templateStyle = document.querySelector('#gridSearchComparisonView + style, #gridSearchComparisonView ~ style');
        const modalCSS = templateStyle ? templateStyle.textContent : '';
        
        const containerHtml = viewClone.innerHTML + modalHtml;
        
        // Build Chart.js initialization code with embedded data
        // Need to include the full chart rendering functions for standalone HTML
        const chartInitCode = `
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
            <script>
                // Embedded comparison data (use window scope to avoid conflicts with main script)
                window.exportedGridSearchComparisonData = ${JSON.stringify(gridSearchComparisonData, null, 2)};
                // Use exportedGridSearchComparisonData directly to avoid redeclaration
                const comparisonData = window.exportedGridSearchComparisonData;
                
                // Color palette for models
                const modelColors = {
                    'ESPN (default)': '#7c3aed',
                    'logreg_platt': '#ef4444',
                    'logreg_isotonic': '#f59e0b',
                    'catboost_platt': '#10b981',
                    'catboost_isotonic': '#3b82f6'
                };
                
                // Initialize charts when page loads
                window.addEventListener('load', function() {
                    // Render marginal effects chart
                    const marginalCanvas = document.getElementById('marginalEffectsCanvas');
                    if (marginalCanvas && comparisonData.models && comparisonData.visualization_data) {
                        const ctx = marginalCanvas.getContext('2d');
                        const datasets = [];
                        
                        comparisonData.models.forEach(model => {
                            const modelViz = comparisonData.visualization_data[model.model_name];
                            if (!modelViz || !modelViz.marginal_effects) return;
                            
                            const marginal = modelViz.marginal_effects;
                            const color = modelColors[model.model_name] || '#888888';
                            
                            if (marginal.entry && marginal.entry.thresholds && marginal.entry.mean) {
                                datasets.push({
                                    label: model.model_name + ' - Entry',
                                    data: marginal.entry.thresholds.map((t, i) => ({ x: t, y: marginal.entry.mean[i] })),
                                    borderColor: color,
                                    backgroundColor: color + '40',
                                    pointRadius: 4,
                                    showLine: true,
                                    tension: 0.1
                                });
                            }
                            
                            if (marginal.exit && marginal.exit.thresholds && marginal.exit.mean) {
                                datasets.push({
                                    label: model.model_name + ' - Exit',
                                    data: marginal.exit.thresholds.map((t, i) => ({ x: t, y: marginal.exit.mean[i] })),
                                    borderColor: color,
                                    backgroundColor: color + '40',
                                    borderDash: [5, 5],
                                    pointRadius: 4,
                                    showLine: true,
                                    tension: 0.1
                                });
                            }
                        });
                        
                        if (datasets.length > 0) {
                            new Chart(ctx, {
                                type: 'line',
                                data: { datasets },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: true,
                                    aspectRatio: 2.5,
                                    scales: {
                                        x: { type: 'linear', position: 'bottom', title: { display: true, text: 'Threshold Value', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                                        y: { type: 'linear', position: 'left', title: { display: true, text: 'Average Profit ($)', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                                    },
                                    plugins: {
                                        legend: { display: true, position: 'top', labels: { color: '#888899' } },
                                        tooltip: { callbacks: { label: function(context) { return context.dataset.label + ': $' + context.parsed.y.toFixed(2); } } }
                                    }
                                }
                            });
                        }
                    }
                    
                    // Render tradeoff scatter chart
                    const scatterCanvas = document.getElementById('tradeoffScatterCanvas');
                    if (scatterCanvas && comparisonData.models && comparisonData.visualization_data) {
                        const ctx = scatterCanvas.getContext('2d');
                        const datasets = [];
                        
                        comparisonData.models.forEach(model => {
                            const modelViz = comparisonData.visualization_data[model.model_name];
                            if (!modelViz || !modelViz.tradeoff_scatter) return;
                            
                            const scatter = modelViz.tradeoff_scatter;
                            const color = modelColors[model.model_name] || '#888888';
                            
                            if (scatter.num_trades && scatter.net_profit) {
                                datasets.push({
                                    label: model.model_name,
                                    data: scatter.num_trades.map((trades, i) => ({ x: trades, y: scatter.net_profit[i] })),
                                    borderColor: color,
                                    backgroundColor: color + '80',
                                    pointRadius: 5,
                                    pointHoverRadius: 7
                                });
                            }
                        });
                        
                        if (datasets.length > 0) {
                            new Chart(ctx, {
                                type: 'scatter',
                                data: { datasets },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: true,
                                    aspectRatio: 2.5,
                                    scales: {
                                        x: { type: 'linear', position: 'bottom', title: { display: true, text: 'Number of Trades', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                                        y: { type: 'linear', position: 'left', title: { display: true, text: 'Net Profit ($)', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                                    },
                                    plugins: {
                                        legend: { display: true, position: 'top', labels: { color: '#888899' } },
                                        tooltip: { callbacks: { label: function(context) { return context.dataset.label + ': ' + context.parsed.x + ' trades, $' + context.parsed.y.toFixed(2) + ' profit'; } } }
                                    }
                                }
                            });
                        }
                    }
                    
                    // Render heatmaps for all three types
                    // Include helper functions for heatmap rendering
                    function calculateGlobalScale(allHeatmapData) {
                        let globalMin = Infinity;
                        let globalMax = -Infinity;
                        
                        allHeatmapData.forEach(modelData => {
                            if (modelData && modelData.matrix) {
                                modelData.matrix.forEach(row => {
                                    row.forEach(val => {
                                        if (val !== null && val !== undefined && !isNaN(val)) {
                                            globalMin = Math.min(globalMin, val);
                                            globalMax = Math.max(globalMax, val);
                                        }
                                    });
                                });
                            }
                        });
                        
                        return { min: globalMin === Infinity ? 0 : globalMin, max: globalMax === -Infinity ? 0 : globalMax };
                    }
                    
                    function renderProfitHeatmapWithScale(data, canvasId, globalScale, isModal) {
                        const canvas = document.getElementById(canvasId);
                        if (!canvas || !data.matrix || !data.entry_thresholds || !data.exit_thresholds) return;
                        
                        // Use smaller size for grid view, larger for modal
                        if (isModal) {
                            canvas.width = 1200;
                            canvas.height = 900;
                        } else {
                            canvas.width = 400;
                            canvas.height = 300;
                        }
                        
                        const ctx = canvas.getContext('2d');
                        const matrix = data.matrix;
                        const entryThresh = data.entry_thresholds;
                        const exitThresh = data.exit_thresholds;
                        
                        if (matrix.length === 0 || entryThresh.length === 0 || exitThresh.length === 0) return;
                        
                        const minVal = globalScale.min;
                        const maxVal = globalScale.max;
                        
                        function getRdYlGnColor(value, minVal, maxVal) {
                            const range = maxVal - minVal;
                            const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal));
                            
                            let normalized;
                            if (minVal < 0 && maxVal > 0) {
                                normalized = (value + absMax) / (2 * absMax);
                            } else {
                                normalized = (value - minVal) / range;
                            }
                            
                            normalized = Math.max(0, Math.min(1, normalized));
                            
                            let r, g, b;
                            if (normalized < 0.25) {
                                const t = normalized / 0.25;
                                r = Math.round(165 + (215 - 165) * t);
                                g = Math.round(0 + (48 - 0) * t);
                                b = Math.round(38 + (39 - 38) * t);
                            } else if (normalized < 0.5) {
                                const t = (normalized - 0.25) / 0.25;
                                r = Math.round(215 + (255 - 215) * t);
                                g = Math.round(48 + (255 - 48) * t);
                                b = Math.round(39 + (191 - 39) * t);
                            } else if (normalized < 0.75) {
                                const t = (normalized - 0.5) / 0.25;
                                r = Math.round(255 - (255 - 145) * t);
                                g = Math.round(255 - (255 - 207) * t);
                                b = Math.round(191 + (96 - 191) * t);
                            } else {
                                const t = (normalized - 0.75) / 0.25;
                                r = Math.round(145 - (145 - 26) * t);
                                g = Math.round(207 - (207 - 152) * t);
                                b = Math.round(96 + (80 - 96) * t);
                            }
                            
                            return 'rgb(' + r + ', ' + g + ', ' + b + ')';
                        }
                        
                        const cellWidth = canvas.width / entryThresh.length;
                        const cellHeight = canvas.height / exitThresh.length;
                        
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
                        
                        ctx.fillStyle = '#333';
                        ctx.font = '10px Arial';
                        ctx.textAlign = 'center';
                        const labelStep = Math.max(1, Math.floor(entryThresh.length / 8));
                        entryThresh.forEach((val, idx) => {
                            if (idx % labelStep === 0) {
                                ctx.fillText(val.toFixed(2), idx * cellWidth + cellWidth / 2, canvas.height - 5);
                            }
                        });
                    }
                    
                    function renderHeatmapType(models, vizData, heatmapKey, containerId, titleSuffix) {
                        const container = document.getElementById(containerId);
                        if (!container) return;
                        
                        const allHeatmapData = [];
                        models.forEach(model => {
                            const modelViz = vizData[model.model_name];
                            if (modelViz && modelViz[heatmapKey]) {
                                allHeatmapData.push(modelViz[heatmapKey]);
                            }
                        });
                        
                        if (allHeatmapData.length === 0) return;
                        
                        const globalScale = calculateGlobalScale(allHeatmapData);
                        
                        models.forEach((model, index) => {
                            const modelViz = vizData[model.model_name];
                            if (!modelViz || !modelViz[heatmapKey]) return;
                            
                            const heatmapData = modelViz[heatmapKey];
                            const canvasId = 'heatmap-' + heatmapKey + '-' + index + '-' + model.model_name.replace(/\\s+/g, '-');
                            const canvas = document.getElementById(canvasId);
                            if (canvas) {
                                // Add click handler to open modal (remove existing first to avoid duplicates)
                                canvas.style.cursor = 'pointer';
                                // Clone canvas to remove all event listeners, then re-add
                                const newCanvas = canvas.cloneNode(true);
                                // Update the ID to match the original so renderProfitHeatmapWithScale can find it
                                newCanvas.id = canvasId;
                                canvas.parentNode.replaceChild(newCanvas, canvas);
                                
                                // Re-render heatmap on the new canvas (cloning clears the canvas content)
                                renderProfitHeatmapWithScale(heatmapData, canvasId, globalScale, false);
                                
                                // Add click handler to the new canvas
                                newCanvas.addEventListener('click', function() {
                                    openHeatmapModal(heatmapData, model.model_name + ' - ' + titleSuffix, globalScale);
                                });
                                
                                // Add "Click to enlarge" hint - remove any existing hints first to avoid duplicates
                                const container = newCanvas.closest('.model-heatmap-container');
                                if (container) {
                                    // Remove any existing hints (could be .heatmap-hint or .heatmap-click-hint)
                                    const existingHints = container.querySelectorAll('.heatmap-click-hint, .heatmap-hint');
                                    existingHints.forEach(hint => hint.remove());
                                    
                                    // Add new hint
                                    const hint = document.createElement('p');
                                    hint.className = 'heatmap-click-hint';
                                    hint.textContent = 'Click to enlarge';
                                    container.appendChild(hint);
                                }
                            }
                        });
                    }
                    
                    // Modal functions for exported HTML
                    function openHeatmapModal(heatmapData, title, globalScale) {
                        const modal = document.getElementById('heatmapModal');
                        const modalTitle = document.getElementById('modalTitle');
                        const modalCanvas = document.getElementById('modalHeatmapCanvas');
                        
                        if (!modal || !modalTitle || !modalCanvas) return;
                        
                        modalTitle.textContent = title;
                        modal.style.display = 'block';
                        
                        // Render at large size for modal
                        renderProfitHeatmapWithScale(heatmapData, 'modalHeatmapCanvas', globalScale, true);
                        
                        // Close on background click
                        modal.onclick = function(event) {
                            if (event.target === modal) {
                                closeHeatmapModal();
                            }
                        };
                        
                        // Close on Escape key
                        const escapeHandler = function(event) {
                            if (event.key === 'Escape') {
                                closeHeatmapModal();
                                document.removeEventListener('keydown', escapeHandler);
                            }
                        };
                        document.addEventListener('keydown', escapeHandler);
                    }
                    
                    function closeHeatmapModal() {
                        const modal = document.getElementById('heatmapModal');
                        if (modal) {
                            modal.style.display = 'none';
                        }
                    }
                    
                    // Make closeHeatmapModal globally accessible for onclick handlers
                    window.closeHeatmapModal = closeHeatmapModal;
                    
                    // Render all three heatmap types
                    if (comparisonData.models && comparisonData.visualization_data) {
                        renderHeatmapType(comparisonData.models, comparisonData.visualization_data, 'profit_heatmap_train', 'heatmapGridTrain', 'Training Set');
                        renderHeatmapType(comparisonData.models, comparisonData.visualization_data, 'profit_heatmap_valid', 'heatmapGridValid', 'Validation Set');
                        renderHeatmapType(comparisonData.models, comparisonData.visualization_data, 'profit_factor_heatmap_valid', 'heatmapGridFactor', 'Profit Factor (Validation Set)');
                    }
                });
            </script>
        `;
        
        // Generate shared header
        const exportHeader = typeof generateExportHeader === 'function' 
            ? generateExportHeader('grid-search-comparison')
            : '';
        const exportHeaderCSS = typeof generateExportHeaderCSS === 'function'
            ? generateExportHeaderCSS()
            : '';
        
        // Build complete HTML
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grid Search Model Comparison</title>
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
    <style>${cssContent}
${exportHeaderCSS}
/* Heatmap grid and modal styles for exported HTML */
.heatmap-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
}

@media (max-width: 1200px) {
    .heatmap-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}

@media (max-width: 768px) {
    .heatmap-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

.model-heatmap-container {
    background: var(--bg-card);
    padding: 1rem;
    border-radius: 8px;
    border: 1px solid var(--border-color);
}

.model-heatmap-container h5 {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    color: var(--text-primary);
    text-align: center;
}

.model-heatmap-container canvas {
    width: 100%;
    height: auto;
    max-width: 100%;
    cursor: pointer;
    transition: opacity 0.2s;
}

.model-heatmap-container canvas:hover {
    opacity: 0.9;
}

.heatmap-click-hint {
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-top: 0.5rem;
    font-style: italic;
}

/* Modal styles */
.heatmap-modal {
    display: none;
    position: fixed;
    z-index: 10000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.9);
    overflow: auto;
}

.heatmap-modal-content {
    position: relative;
    margin: 2% auto;
    padding: 2rem;
    width: 90%;
    max-width: 1200px;
    background: var(--bg-primary);
    border-radius: 8px;
}

.heatmap-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.heatmap-modal-header h3 {
    margin: 0;
    color: var(--text-primary);
}

.heatmap-modal-close {
    color: var(--text-secondary);
    font-size: 2rem;
    font-weight: bold;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.heatmap-modal-close:hover {
    color: var(--text-primary);
}

.heatmap-modal-canvas {
    width: 100%;
    height: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
}
</style>
    ${chartInitCode}
</head>
<body>
    <div class="container">
        ${exportHeader}
        <div class="simulation-container">
            ${containerHtml}
        </div>
    </div>
    <!-- Note: grid-search-comparison.js is not included in exported HTML to avoid variable conflicts -->
    <!-- Charts are initialized by the embedded script above -->
</body>
</html>`;
        
        // POST to export endpoint
        const response = await fetch('/api/export/html', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                html_content: htmlContent,
                filename: 'grid-search-comparison.html'
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to export HTML');
        }
        
        console.log('HTML exported successfully to docs/grid-search-comparison.html');
    } catch (error) {
        console.error('Error exporting HTML:', error);
        alert(`Error exporting HTML: ${error.message}`);
    }
}

/**
 * Export grid search comparison to image (PNG)
 */
async function exportGridSearchComparisonToImage() {
    const view = document.getElementById('gridSearchComparisonView');
    if (!view) {
        alert('Comparison view not found');
        return;
    }
    
    try {
        // Convert tooltips to visible text for image export (like stats.js)
        const tooltipIcons = view.querySelectorAll('.tooltip-icon');
        const addedTooltipTexts = [];
        
        tooltipIcons.forEach(tooltipIcon => {
            const tooltipText = tooltipIcon.getAttribute('title') || '';
            if (tooltipText) {
                // Find the parent header
                const header = tooltipIcon.closest('h3');
                if (header) {
                    // Create visible tooltip text element
                    const tooltipElement = document.createElement('div');
                    tooltipElement.className = 'chart-tooltip-text';
                    tooltipElement.textContent = tooltipText;
                    tooltipElement.style.cssText = `
                        font-size: 0.7rem;
                        color: var(--text-secondary);
                        margin-top: 4px;
                        margin-bottom: 8px;
                        line-height: 1.4;
                        padding: 6px 8px;
                        background: rgba(0, 0, 0, 0.3);
                        border-radius: 4px;
                        max-width: 100%;
                    `;
                    // Insert after the header
                    header.parentNode.insertBefore(tooltipElement, header.nextSibling);
                    addedTooltipTexts.push(tooltipElement);
                }
            }
        });
        
        // Wait for charts/canvases to be fully rendered
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Use html2canvas to capture the view
        if (typeof html2canvas === 'undefined') {
            alert('Image export library not loaded. Please refresh the page.');
            return;
        }
        
        const canvas = await html2canvas(view, {
            backgroundColor: '#0a0a0f',
            scale: 2,
            logging: false,
            useCORS: true
        });
        
        // Remove added tooltip text elements after capture
        addedTooltipTexts.forEach(el => el.remove());
        
        // Convert to blob and download
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const dateStr = new Date().toISOString().split('T')[0];
            a.href = url;
            a.download = `grid-search-comparison-${dateStr}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 'image/png');
    } catch (error) {
        console.error('Error exporting image:', error);
        alert(`Error exporting image: ${error.message}`);
    }
}

/**
 * Open heatmap in modal for larger view
 */
function openHeatmapModal(heatmapData, title, globalScale) {
    const modal = document.getElementById('heatmapModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalCanvas = document.getElementById('modalHeatmapCanvas');
    
    if (!modal || !modalTitle || !modalCanvas) return;
    
    modalTitle.textContent = title;
    modal.style.display = 'block';
    
    // Set larger canvas size for modal
    modalCanvas.width = 1200;
    modalCanvas.height = 900;
    
    // Render heatmap in modal
    renderProfitHeatmapWithScale(heatmapData, 'modalHeatmapCanvas', globalScale);
    
    // Close on background click
    modal.onclick = function(event) {
        if (event.target === modal) {
            closeHeatmapModal();
        }
    };
    
    // Close on Escape key
    document.addEventListener('keydown', function escapeHandler(event) {
        if (event.key === 'Escape') {
            closeHeatmapModal();
            document.removeEventListener('keydown', escapeHandler);
        }
    });
}

/**
 * Close heatmap modal
 */
function closeHeatmapModal() {
    const modal = document.getElementById('heatmapModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

