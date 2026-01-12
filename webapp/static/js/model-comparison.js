/**
 * Model Comparison Page - JavaScript
 * 
 * Design Pattern: Module Pattern for page-specific functionality
 * Algorithm: Data fetching, rendering, and export
 * Big O: O(n) where n is calibration points (typically < 100)
 */

let comparisonData = null;

/**
 * Load model comparison data from backend
 */
async function loadModelComparison() {
    const container = document.getElementById('modelComparisonContainer');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading model comparison...</div>';
        
        const response = await fetch('/api/stats/model-comparison');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        comparisonData = data;
        
        renderModelComparison(data);
    } catch (error) {
        console.error('Error loading model comparison:', error);
        container.innerHTML = `
            <div class="error-message">
                <p>Error loading model comparison data: ${error.message}</p>
                <button onclick="loadModelComparison()">Retry</button>
            </div>
        `;
    }
}

/**
 * Render model comparison page with metrics table and calibration chart
 */
function renderModelComparison(data) {
    const container = document.getElementById('modelComparisonContainer');
    if (!container || !data) return;
    
    const { models, best_models } = data;
    
    // Build metrics table HTML
    let metricsHtml = `
        <div class="model-comparison-section">
            <h3>Overall Metrics Comparison</h3>
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Model</th>
                        <th style="text-align: right;">Log Loss</th>
                        <th style="text-align: right;">Brier Score</th>
                        <th style="text-align: right;">ECE</th>
                        <th style="text-align: right;">AUC</th>
                        <th style="text-align: right;">N</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    for (const model of models) {
        const isBestLogLoss = model.model_label === best_models.logloss;
        const isBestBrier = model.model_label === best_models.brier;
        const isBestEce = model.model_label === best_models.ece;
        const isBestAuc = model.model_label === best_models.auc;
        const isBestAny = isBestLogLoss || isBestBrier || isBestEce || isBestAuc;
        
        const rowClass = isBestAny ? 'best-model-row' : '';
        
        metricsHtml += `
            <tr class="${rowClass}">
                <td><strong>${model.model_label}</strong></td>
                <td style="text-align: right; ${isBestLogLoss ? 'font-weight: bold; color: var(--accent);' : ''}">${model.metrics.logloss.toFixed(6)}</td>
                <td style="text-align: right; ${isBestBrier ? 'font-weight: bold; color: var(--accent);' : ''}">${model.metrics.brier.toFixed(6)}</td>
                <td style="text-align: right; ${isBestEce ? 'font-weight: bold; color: var(--accent);' : ''}">${model.metrics.ece.toFixed(6)}</td>
                <td style="text-align: right; ${isBestAuc ? 'font-weight: bold; color: var(--accent);' : ''}">${model.metrics.auc.toFixed(6)}</td>
                <td style="text-align: right;">${model.metrics.n.toLocaleString()}</td>
            </tr>
        `;
    }
    
    metricsHtml += `
                </tbody>
            </table>
        </div>
    `;
    
    // Build best models summary
    let bestModelsHtml = `
        <div class="best-models-summary">
            <h4>Best Models by Metric</h4>
            <ul>
                <li><strong>Log Loss</strong> (lower is better): ${best_models.logloss}</li>
                <li><strong>Brier Score</strong> (lower is better): ${best_models.brier}</li>
                <li><strong>ECE</strong> (lower is better): ${best_models.ece}</li>
                <li><strong>AUC</strong> (higher is better): ${best_models.auc}</li>
            </ul>
        </div>
    `;
    
    // Build calibration chart container
    let chartHtml = `
        <div class="model-comparison-section">
            <h3>Calibration Comparison</h3>
            <p class="section-description">All 4 models plotted together. Points closer to the diagonal line (y=x) indicate better calibration.</p>
            <div class="chart-wrapper" style="height: 600px;">
                <canvas id="modelComparisonCalibrationChart"></canvas>
            </div>
        </div>
    `;
    
    container.innerHTML = metricsHtml + bestModelsHtml + chartHtml;
    
    // Render Chart.js calibration plot
    renderCalibrationChart(models);
}

/**
 * Render Chart.js calibration plot with all 4 models
 */
function renderCalibrationChart(models) {
    const canvas = document.getElementById('modelComparisonCalibrationChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Build datasets for all models - dots only, no lines
    const datasets = models.map(model => ({
        label: model.model_label,
        data: model.calibration_points.map(p => ({
            x: p.x,
            y: p.y,
            n: p.n
        })),
        backgroundColor: model.model_color + '40', // More transparent (40 = ~25% opacity)
        borderColor: model.model_color,
        pointRadius: model.calibration_points.map(p => {
            const n = p.n || 0;
            return Math.max(4, Math.min(12, 4 + (n / 10000)));
        }),
        pointHoverRadius: 10,
        fill: false,
        showLine: false, // No lines, just dots
        tension: 0
    }));
    
    // Add perfect calibration line
    datasets.push({
        label: 'Perfect Calibration (y = x)',
        data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
        type: 'line',
        borderColor: 'rgba(255, 255, 255, 0.5)',
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
        tension: 0
    });
    
    new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Predicted Probability',
                        color: '#888899'
                    },
                    min: 0,
                    max: 1,
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Observed Win Rate',
                        color: '#888899'
                    },
                    min: 0,
                    max: 1,
                    ticks: { color: '#888899' },
                    grid: { color: '#2a2a40' }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label === 'Perfect Calibration (y = x)') {
                                return context.dataset.label;
                            }
                            const point = context.raw;
                            const gap = point.y - point.x;
                            const gapText = gap > 0 ? `+${(gap * 100).toFixed(2)}%` : `${(gap * 100).toFixed(2)}%`;
                            return [
                                `Model: ${context.dataset.label}`,
                                `Predicted: ${(point.x * 100).toFixed(1)}%`,
                                `Actual: ${(point.y * 100).toFixed(1)}%`,
                                `Gap: ${gapText}`,
                                `Samples: ${point.n || 0}`
                            ];
                        }
                    }
                },
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#888899',
                        filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                    }
                }
            }
        }
    });
}

/**
 * Export model comparison to HTML file
 * Critical: Embeds comparison data in <script> tag for standalone rendering
 */
async function exportComparisonToHTML() {
    if (!comparisonData) {
        alert('No comparison data available. Please wait for the page to load.');
        return;
    }
    
    try {
        const container = document.getElementById('modelComparisonContainer');
        if (!container) {
            throw new Error('Container not found');
        }
        
        // Fetch CSS content
        const cssResponse = await fetch('/static/css/styles.css');
        const cssContent = await cssResponse.text();
        
        // Get container HTML
        const containerHtml = container.innerHTML;
        
        // Build Chart.js initialization code with embedded data
        const chartInitCode = `
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
            <script>
                // Embedded comparison data
                const comparisonData = ${JSON.stringify(comparisonData, null, 2)};
                
                // Initialize chart when page loads
                window.addEventListener('load', function() {
                    const canvas = document.getElementById('modelComparisonCalibrationChart');
                    if (!canvas) return;
                    
                    const ctx = canvas.getContext('2d');
                    const { models } = comparisonData;
                    
                    // Build datasets for all models - dots only, no lines
                    const datasets = models.map(model => ({
                        label: model.model_label,
                        data: model.calibration_points.map(p => ({
                            x: p.x,
                            y: p.y,
                            n: p.n
                        })),
                        backgroundColor: model.model_color + '40', // More transparent
                        borderColor: model.model_color,
                        pointRadius: model.calibration_points.map(p => {
                            const n = p.n || 0;
                            return Math.max(4, Math.min(12, 4 + (n / 10000)));
                        }),
                        pointHoverRadius: 10,
                        fill: false,
                        showLine: false, // No lines, just dots
                        tension: 0
                    }));
                    
                    // Add perfect calibration line
                    datasets.push({
                        label: 'Perfect Calibration (y = x)',
                        data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    });
                    
                    new Chart(ctx, {
                        type: 'scatter',
                        data: { datasets },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                x: {
                                    type: 'linear',
                                    position: 'bottom',
                                    title: {
                                        display: true,
                                        text: 'Predicted Probability',
                                        color: '#888899'
                                    },
                                    min: 0,
                                    max: 1,
                                    ticks: { color: '#888899' },
                                    grid: { color: '#2a2a40' }
                                },
                                y: {
                                    type: 'linear',
                                    position: 'left',
                                    title: {
                                        display: true,
                                        text: 'Observed Win Rate',
                                        color: '#888899'
                                    },
                                    min: 0,
                                    max: 1,
                                    ticks: { color: '#888899' },
                                    grid: { color: '#2a2a40' }
                                }
                            },
                            plugins: {
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            if (context.dataset.label === 'Perfect Calibration (y = x)') {
                                                return context.dataset.label;
                                            }
                                            const point = context.raw;
                                            const gap = point.y - point.x;
                                            const gapText = gap > 0 ? \`+\${(gap * 100).toFixed(2)}%\` : \`\${(gap * 100).toFixed(2)}%\`;
                                            return [
                                                \`Model: \${context.dataset.label}\`,
                                                \`Predicted: \${(point.x * 100).toFixed(1)}%\`,
                                                \`Actual: \${(point.y * 100).toFixed(1)}%\`,
                                                \`Gap: \${gapText}\`,
                                                \`Samples: \${point.n || 0}\`
                                            ];
                                        }
                                    }
                                },
                                legend: {
                                    display: true,
                                    position: 'top',
                                    labels: {
                                        color: '#888899',
                                        filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                                    }
                                }
                            }
                        }
                    });
                });
            </script>
        `;
        
        // Build complete HTML
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Comparison - 2×2 Matrix</title>
    <style>${cssContent}</style>
    ${chartInitCode}
</head>
<body>
    <div class="stats-page-view" style="display: block;">
        <div class="page-header">
            <div>
                <h2>Model Comparison</h2>
                <p class="page-header-subtitle">2×2 Matrix: Logistic Regression vs CatBoost × Platt vs Isotonic Calibration</p>
            </div>
        </div>
        <div class="model-comparison-container" id="modelComparisonContainer">
            ${containerHtml}
        </div>
    </div>
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
                filename: 'model-comparison.html'
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to export HTML');
        }
        
        // Success - no alert (as per user request)
        console.log('HTML exported successfully to docs/model-comparison.html');
    } catch (error) {
        console.error('Error exporting HTML:', error);
        alert(`Error exporting HTML: ${error.message}`);
    }
}

/**
 * Export model comparison to image (PNG)
 */
async function exportComparisonToImage() {
    const container = document.getElementById('modelComparisonContainer');
    if (!container) {
        alert('Container not found');
        return;
    }
    
    try {
        // Use html2canvas to capture the container
        const canvas = await html2canvas(container, {
            backgroundColor: '#0a0a0f',
            scale: 2,
            logging: false
        });
        
        // Convert to blob and download
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const dateStr = new Date().toISOString().split('T')[0];
            a.href = url;
            a.download = `model-comparison-${dateStr}.png`;
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

