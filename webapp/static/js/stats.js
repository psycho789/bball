/**
 * Aggregate statistics page module.
 * 
 * Design Pattern: View Pattern for statistics display
 * Algorithm: Data aggregation and visualization
 * Big O: O(1) for rendering (data is pre-aggregated)
 */

async function loadAggregateStats() {
    console.log('[FRONTEND] loadAggregateStats() called');
    const container = document.getElementById('aggregateStatsContainer');
    if (!container) {
        console.warn('[FRONTEND] aggregateStatsContainer not found');
        return;
    }
    
    try {
        console.log('[FRONTEND] Fetching aggregate stats...');
        const [stats, modelEval2024, modelEvalAll] = await Promise.allSettled([
            getAggregateStats('2025-26'),
            getModelEvaluation(2024).catch(() => null),  // Don't fail if evaluation not available
            getModelEvaluation(null, true).catch(() => null)  // All seasons
        ]);
        
        const statsData = stats.status === 'fulfilled' ? stats.value : null;
        // Extract evalData - use value directly if fulfilled, otherwise null
        const evalData2024 = modelEval2024.status === 'fulfilled' ? modelEval2024.value : null;
        const evalDataAll = modelEvalAll.status === 'fulfilled' ? modelEvalAll.value : null;
        
        console.log('[FRONTEND] Stats received, rendering...');
        // Pass both 2024 and all-seasons evaluation data
        renderAggregateStats(statsData, evalData2024, evalDataAll);
    } catch (error) {
        console.error('[FRONTEND] Failed to load aggregate stats:', error);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>Failed to load aggregate statistics</p>
            </div>
        `;
    }
}

function formatNumber(value, decimals = 4) {
    if (value === null || value === undefined) return 'N/A';
    return value.toFixed(decimals);
}

function formatPercent(value, decimals = 2) {
    if (value === null || value === undefined) return 'N/A';
    return (value * 100).toFixed(decimals) + '%';
}

function createTooltip(explanation) {
    // HTML-escape the explanation to prevent injection issues
    const escaped = explanation
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    return `
        <span class="tooltip-icon" title="${escaped}">
            ?
            <span class="tooltip-content">
                <strong>What is this?</strong>
                <p>${escaped}</p>
            </span>
        </span>
    `;
}

function createHistogram(data, label, color, bins = 30) {
    if (!data || data.length === 0) return null;
    
    const min = Math.min(...data);
    const max = Math.max(...data);
    const binWidth = (max - min) / bins;
    
    const histogram = new Array(bins).fill(0);
    const binLabels = [];
    
    for (let i = 0; i < bins; i++) {
        binLabels.push((min + (i + 0.5) * binWidth).toFixed(3));
    }
    
    data.forEach(value => {
        const binIndex = Math.min(Math.floor((value - min) / binWidth), bins - 1);
        histogram[binIndex]++;
    });
    
    return {
        labels: binLabels,
        data: histogram,
        label: label,
        color: color
    };
}

function createScatterPlot(data, xLabel, yLabel, xColor, yColor) {
    if (!data || data.length === 0) return null;
    
    return {
        x: data.map(d => d[xLabel]),
        y: data.map(d => d[yLabel]),
        xLabel: xLabel,
        yLabel: yLabel,
        xColor: xColor,
        yColor: yColor
    };
}

function renderChart(canvasId, chartType, chartData, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !chartData) return null;
    
    const ctx = canvas.getContext('2d');
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#e8e8f0'
                }
            }
        },
        scales: chartType === 'bar' || chartType === 'line' ? {
            x: {
                ticks: { color: '#888899' },
                grid: { color: '#2a2a40' }
            },
            y: {
                ticks: { color: '#888899' },
                grid: { color: '#2a2a40' }
            }
        } : {
            x: {
                ticks: { color: '#888899' },
                grid: { color: '#2a2a40' }
            },
            y: {
                ticks: { color: '#888899' },
                grid: { color: '#2a2a40' }
            }
        }
    };
    
    const config = {
        type: chartType,
        data: chartData,
        options: { ...defaultOptions, ...options }
    };
    
    return new Chart(ctx, config);
}

function renderAggregateStats(stats, modelEval2024 = null, modelEvalAll = null) {
    const container = document.getElementById('aggregateStatsContainer');
    if (!container || !stats) return;
    
    let html = `
        <div class="aggregate-stats-summary">
            <div class="summary-card">
                <div class="summary-value">${stats.total_games || 0}</div>
                <div class="summary-label">Total Games${createTooltip('Total number of games in the dataset that have both ESPN and Kalshi data available for comparison.')}</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">${stats.games_with_stats || 0}</div>
                <div class="summary-label">Games with Stats${createTooltip('Number of games that have been successfully processed and have calculated statistics. This should match or be close to Total Games.')}</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">${stats.comparison?.total_aligned_data_points || 0}</div>
                <div class="summary-label">Aligned Data Points${createTooltip('Total number of time-aligned data points where we have both ESPN and Kalshi probabilities at the same moment. More points = better comparison data.')}</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">${Math.round(stats.comparison?.avg_aligned_points_per_game || 0)}</div>
                <div class="summary-label">Avg Points/Game${createTooltip('Average number of aligned data points per game. Higher values mean we have more granular comparison data for each game.')}</div>
            </div>
            ${stats.comparison?.data_coverage ? `
            <div class="summary-card">
                <div class="summary-value">${Math.round(stats.comparison.data_coverage.median_points_per_game || 0)}</div>
                <div class="summary-label">Median Points/Game${createTooltip('Middle value of aligned data points per game. Half of games have more points, half have fewer.')}</div>
            </div>
            ` : ''}
        </div>
    `;
    
    // Charts Section - Most useful for data science
    html += `
        <div class="chart-container">
            <h4>Distribution Charts${createTooltip('These charts show how different metrics are spread across all games. They help us see patterns - like whether most games have similar accuracy, or if there are outliers.')}</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px;">
                <!-- Model Calibration Charts -->
                ${modelEval2024 && modelEval2024.eval && modelEval2024.eval.calibration_points && modelEval2024.eval.calibration_points.length > 0 ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        Win Probability Model Calibration (2024 Season)${createTooltip('Shows how well-calibrated the trained win probability model is on the 2024 season test set. Each point represents a probability bin. X-axis = average predicted probability in that bin, Y-axis = actual win rate. Points on the diagonal line (y=x) = perfectly calibrated.')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="modelCalibrationChart2024"></canvas>
                    </div>
                </div>
                ` : ''}
                ${modelEvalAll && modelEvalAll.eval && modelEvalAll.eval.calibration_points && modelEvalAll.eval.calibration_points.length > 0 ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        Win Probability Model Calibration (All Seasons)${createTooltip('Shows how well-calibrated the trained win probability model is across all available seasons. Each point represents a probability bin aggregated across all evaluation reports. X-axis = average predicted probability in that bin, Y-axis = actual win rate. Points on the diagonal line (y=x) = perfectly calibrated.')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="modelCalibrationChartAll"></canvas>
                    </div>
                </div>
                ` : ''}
                <!-- Story 3.1: Reliability Curves -->
                ${stats.espn?.reliability_curve?.bins && stats.espn.reliability_curve.bins.length > 0 ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        ESPN Reliability Curve (All In-Game Updates)${createTooltip('Shows how well-calibrated ESPN probabilities are. Each point represents a bin (e.g., 0-10%, 10-20%). X-axis = average predicted probability in that bin, Y-axis = actual win rate. Points on the diagonal line (y=x) = perfectly calibrated. Points above the diagonal = underconfident (actual win rate higher than predicted). Points below the diagonal = overconfident (predicted probability higher than actual outcome).')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="espnReliabilityChart"></canvas>
                    </div>
                </div>
                ` : ''}
                ${stats.kalshi?.reliability_curve?.bins && stats.kalshi.reliability_curve.bins.length > 0 ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        Kalshi Reliability Curve (All In-Game Updates)${createTooltip('Shows how well-calibrated Kalshi market probabilities are. Each point represents a bin (e.g., 0-10%, 10-20%). X-axis = average predicted probability in that bin, Y-axis = actual win rate. Points on the diagonal line (y=x) = perfectly calibrated. Points above the diagonal = underconfident (actual win rate higher than predicted). Points below the diagonal = overconfident (predicted probability higher than actual outcome).')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="kalshiReliabilityChart"></canvas>
                    </div>
                </div>
                ` : ''}
                <!-- Story 3.2: Time-Sliced Performance Chart -->
                ${stats.espn?.brier_by_phase?.espn ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        Time-Averaged In-Game Brier Error by Game Phase (ESPN vs Kalshi)${createTooltip('Shows prediction accuracy (Brier score) by game phase. Lower = better. Early = first 25% of game, Mid = 25-75%, Late = 75-100%, Clutch = last 2 minutes. Helps identify when each source is most/least accurate.')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="phaseBrierChart"></canvas>
                    </div>
                </div>
                ` : ''}
                <!-- Story 3.4: Disagreement vs Outcome Chart -->
                ${stats.comparison?.disagreement_vs_outcome && stats.comparison.disagreement_vs_outcome.length > 0 ? `
                <div>
                    <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                        Conditional Home Win Rate vs ESPN–Kalshi Probability Difference${createTooltip('Shows if disagreement between ESPN and Kalshi predicts outcomes. X-axis = signed difference (ESPN - Kalshi). Negative = ESPN lower than Kalshi. Positive = ESPN higher than Kalshi. Y-axis = actual home win rate. If disagreement predicts outcomes, this may indicate systematic bias or suggest one source may be better calibrated in certain regions.')}
                    </h5>
                    <div class="chart-wrapper">
                        <canvas id="disagreementOutcomeChart"></canvas>
                    </div>
                </div>
                ` : ''}
    `;
    
    // Time-Averaged In-Game Brier Error Distribution
    const espnBrierData = stats.espn?.time_averaged_in_game_brier_error;
    if (espnBrierData?.distribution && espnBrierData.distribution.length > 0) {
        html += `
            <div>
                <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                    ESPN Time-Averaged In-Game Brier Error Distribution${createTooltip('Shows how accurate ESPN\'s win probabilities are across all games. Computed by averaging (p_t - outcome)^2 over all probability updates within the game. Range is [0, 1]. Lower is better. A score of 0 means perfect predictions, 1 means completely wrong. Typical error magnitude would be closer to sqrt(Brier), not Brier itself.')}
                </h5>
                <div class="chart-wrapper">
                    <canvas id="brierChart"></canvas>
                </div>
            </div>
        `;
    }
    
    // Correlation Distribution
    if (stats.comparison?.correlation?.distribution && stats.comparison.correlation.distribution.length > 0) {
        html += `
            <div>
                <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                    ESPN/Kalshi Correlation Distribution${createTooltip('Shows how closely ESPN and Kalshi probabilities move together. Correlation measures agreement in movement, not accuracy or betting edge. Values range from -1 to 1. Closer to 1 means they move in sync (when ESPN goes up, Kalshi goes up). Closer to 0 means they\'re independent. This tells us if both sources are reacting to the same game events.')}
                </h5>
                <div class="chart-wrapper">
                    <canvas id="correlationChart"></canvas>
                </div>
            </div>
        `;
    }
    
    // ESPN vs Kalshi Volatility Scatter
    if (stats.comparison?.espn_volatility_vs_kalshi_volatility && stats.comparison.espn_volatility_vs_kalshi_volatility.length > 0) {
        html += `
            <div>
                <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                    ESPN vs Kalshi Volatility${createTooltip('Each point is one game. Shows if games with high ESPN volatility also have high Kalshi volatility. Points along a diagonal line mean they agree on which games are volatile. Scattered points mean they disagree. This helps us understand if both markets react similarly to game dynamics.')}
                </h5>
                <div class="chart-wrapper">
                    <canvas id="volatilityScatterChart"></canvas>
                </div>
            </div>
        `;
    }
    
    // Mean Absolute Difference Distribution
    if (stats.comparison?.mean_absolute_difference?.distribution && stats.comparison.mean_absolute_difference.distribution.length > 0) {
        html += `
            <div>
                <h5 style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 8px;">
                    Absolute Difference Distribution (ESPN vs Kalshi)${createTooltip('Shows how much ESPN and Kalshi probabilities disagree across all games. This measures disagreement, not accuracy - it doesn\'t tell us which predictor is better. Lower values mean they agree more. Higher values mean they disagree more.')}
                </h5>
                <div class="chart-wrapper">
                    <canvas id="maeChart"></canvas>
                </div>
            </div>
        `;
    }
    
    html += `
            </div>
        </div>
    `;
    
    // ESPN Stats Section
    if (stats.espn) {
        const e = stats.espn;
        html += `
            <div class="stats-section">
                <h3>ESPN Aggregate Metrics</h3>
                <div class="stats-grid">
                    <div class="stats-group">
                        <div class="stats-group-title">Calibration${createTooltip('Measures how accurate the predictions are. Lower values = better predictions. These metrics tell us if ESPN\'s probabilities match reality.')}</div>
                        ${(() => {
                            const brierData = e.time_averaged_in_game_brier_error;
                            return brierData ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Time-Averaged In-Game Brier Error (Mean)${createTooltip('Average prediction accuracy across all games. Computed by averaging (p_t - outcome)^2 over all probability updates within the game. Range is [0, 1]. Lower is better. 0 = perfect, 1 = completely wrong. Typical error magnitude would be closer to sqrt(Brier), not Brier itself.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Time-Averaged In-Game Brier Error (Median)${createTooltip('The middle value - half of games have better accuracy, half have worse. Less affected by extreme outliers than the mean. Computed by averaging (p_t - outcome)^2 over all probability updates within the game. Range is [0, 1]. Lower is better.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.median)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Time-Averaged In-Game Brier Error (Std Dev)${createTooltip('How much the time-averaged in-game Brier errors vary between games. High values mean some games have much better/worse predictions than others. Low values mean consistent accuracy.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.std_dev)}</span>
                        </div>
                        ${brierData.p25 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">P25${createTooltip('25th percentile - 25% of games have time-averaged in-game Brier errors below this value. Helps us see the range of prediction quality.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.p25)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">P75${createTooltip('75th percentile - 75% of games have time-averaged in-game Brier errors below this value. The difference between P75 and P25 shows the spread of prediction quality.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.p75)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">P90${createTooltip('90th percentile - 90% of games have better predictions than this. Helps identify the worst-performing games.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.p90)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">P95${createTooltip('95th percentile - 95% of games have better predictions. Shows the extreme outliers where predictions were very poor.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.p95)}</span>
                        </div>
                        ` : ''}
                        ${brierData.skewness !== null && brierData.skewness !== undefined ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Skewness${createTooltip('Shows if the distribution is lopsided. Positive = more games with high scores (bad predictions). Negative = more games with low scores (good predictions). Near 0 = balanced.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.skewness, 3)}</span>
                        </div>
                        ` : ''}
                        ${brierData.kurtosis !== null && brierData.kurtosis !== undefined ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Kurtosis${createTooltip('Measures how "peaked" or "flat" the distribution is. High values = most games cluster around the mean. Low values = more spread out. Helps understand if predictions are consistent or vary widely.')}</span>
                            <span class="stat-row-value">${formatNumber(brierData.kurtosis, 3)}</span>
                        </div>
                        ` : ''}
                        <div class="stat-row">
                            <span class="stat-row-label">Count${createTooltip('Number of games included in this calculation. Only completed games with known outcomes can be measured for accuracy.')}</span>
                            <span class="stat-row-value">${brierData.count || 0}</span>
                        </div>
                        ` : '';
                        })()}
                        ${e.log_loss ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Log Loss (Mean)${createTooltip('Another way to measure prediction accuracy. Penalizes confident wrong predictions MUCH more heavily than Brier score. If ESPN says 99% and is wrong, log loss spikes dramatically. Lower is better. Probabilities are clipped to 0.01-0.99 to prevent infinite penalties.')}</span>
                            <span class="stat-row-value">${formatNumber(e.log_loss.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Log Loss (Median)${createTooltip('Middle value of log loss. Less affected by extreme outliers than the mean.')}</span>
                            <span class="stat-row-value">${formatNumber(e.log_loss.median)}</span>
                        </div>
                        ${e.log_loss.max ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Log Loss (Max)${createTooltip('Highest log loss found. This represents the game where ESPN was most confidently wrong. Log loss heavily punishes overconfidence, so high values indicate ESPN made very confident predictions that turned out wrong.')}</span>
                            <span class="stat-row-value">${formatNumber(e.log_loss.max)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                    </div>
                    
                    <div class="stats-group">
                        <div class="stats-group-title">Volatility & Deviation${createTooltip('Measures how much probabilities swing during games. High volatility = probabilities change dramatically. Low volatility = probabilities stay relatively stable.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility (Mean)${createTooltip('Average amount that probabilities change from one moment to the next. High values mean probabilities swing wildly during games. Low values mean probabilities stay relatively stable.')}</span>
                            <span class="stat-row-value">${formatPercent(e.volatility.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility (Median)${createTooltip('Middle value of volatility. Half of games have more volatility, half have less.')}</span>
                            <span class="stat-row-value">${formatPercent(e.volatility.median)}</span>
                        </div>
                        ${e.volatility.p25 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility P25${createTooltip('25% of games have lower volatility than this. Helps identify the most stable games.')}</span>
                            <span class="stat-row-value">${formatPercent(e.volatility.p25)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility P75${createTooltip('75% of games have lower volatility than this. Helps identify the most chaotic games.')}</span>
                            <span class="stat-row-value">${formatPercent(e.volatility.p75)}</span>
                        </div>
                        ` : ''}
                        <div class="stat-row">
                            <span class="stat-row-label">Std Deviation (Mean)${createTooltip('Average spread of probabilities around the mean. High values mean probabilities vary widely throughout games. Low values mean probabilities stay close to the average.')}</span>
                            <span class="stat-row-value">${formatPercent(e.standard_deviation.mean)}</span>
                        </div>
                    </div>
                    
                    <div class="stats-group">
                        <div class="stats-group-title">Game Dynamics${createTooltip('Measures how often the favorite changes during games. High values mean games are back-and-forth. Low values mean one team stays favored throughout.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Favorite Flips (p crosses 0.5) (Mean)${createTooltip('Average number of times the probability-based favorite changes during a game. Counts probability crossings over 50% (p crosses 0.5), not score-based lead changes. High values = back-and-forth games. Low values = one team dominates.')}</span>
                            <span class="stat-row-value">${formatNumber(e.lead_changes.mean, 1)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Favorite Flips (p crosses 0.5) (Total)${createTooltip('Total number of probability-based favorite flips across all games. Counts probability crossings over 50%, not score-based lead changes. Helps us understand how often games are competitive vs. blowouts.')}</span>
                            <span class="stat-row-value">${e.lead_changes.total || 0}</span>
                        </div>
                        ${e.extreme_probability_rate !== null && e.extreme_probability_rate !== undefined ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Extreme Probability Rate (≥95% or ≤5%)${createTooltip('Point-count-based percentage of probability updates where ESPN probability was >= 95% or <= 5% (very confident). Calculated as: (count of extreme points) / (total points). High values mean ESPN gets very confident often.')}</span>
                            <span class="stat-row-value">${formatPercent(e.extreme_probability_rate)}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    // Kalshi Stats Section
    if (stats.kalshi) {
        const k = stats.kalshi;
        html += `
            <div class="stats-section">
                <h3>Kalshi Aggregate Metrics</h3>
                <div class="stats-grid">
                    <div class="stats-group">
                        <div class="stats-group-title">Volatility & Deviation${createTooltip('Measures how much Kalshi market prices swing during games. High volatility = prices change dramatically as traders react to game events.')}</div>
                        ${k.volatility ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility (Mean)${createTooltip('Average amount that Kalshi prices change from one moment to the next. Shows how reactive the betting market is to game events.')}</span>
                            <span class="stat-row-value">${formatPercent(k.volatility.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility (Median)${createTooltip('Middle value of Kalshi volatility. Half of games have more price swings, half have less.')}</span>
                            <span class="stat-row-value">${formatPercent(k.volatility.median)}</span>
                        </div>
                        ${k.volatility.p25 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility P25${createTooltip('25% of games have lower Kalshi volatility. These are games where market prices stayed relatively stable.')}</span>
                            <span class="stat-row-value">${formatPercent(k.volatility.p25)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Volatility P75${createTooltip('75% of games have lower Kalshi volatility. Games above this had very reactive markets.')}</span>
                            <span class="stat-row-value">${formatPercent(k.volatility.p75)}</span>
                        </div>
                        ` : ''}
                        ${k.extreme_probability_rate !== null && k.extreme_probability_rate !== undefined ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Extreme Probability Rate (≥95% or ≤5%)${createTooltip('Point-count-based percentage of probability updates where Kalshi probability was >= 95% or <= 5% (very confident). Calculated as: (count of extreme points) / (total points). High values mean the betting market gets very confident often.')}</span>
                            <span class="stat-row-value">${formatPercent(k.extreme_probability_rate)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    // Comparison Section
    if (stats.comparison) {
        const c = stats.comparison;
        html += `
            <div class="stats-section">
                <h3>ESPN vs Kalshi Comparison</h3>
                <div class="stats-grid">
                    ${c.correlation ? `
                    <div class="stats-group">
                        <div class="stats-group-title">Correlation${createTooltip('Correlation measures agreement in movement, not accuracy or betting edge. Values range from -1 to 1. Closer to 1 = they move in sync. Closer to 0 = they\'re independent.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Mean Correlation${createTooltip('Average correlation across all games. Correlation measures agreement in movement, not accuracy or betting edge. Values near 1 mean ESPN and Kalshi probabilities move together (when one goes up, the other goes up). Values near 0 mean they move independently. Negative values mean they move in opposite directions.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.mean, 3)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Median Correlation${createTooltip('Middle value of correlation. Less affected by extreme outliers than the mean.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.median, 3)}</span>
                        </div>
                        ${c.correlation.p25 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">P25${createTooltip('25% of games have lower correlation. These are games where ESPN and Kalshi disagreed more.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.p25, 3)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">P75${createTooltip('75% of games have lower correlation. Games above this had very high agreement between ESPN and Kalshi.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.p75, 3)}</span>
                        </div>
                        ` : ''}
                        <div class="stat-row">
                            <span class="stat-row-label">Min${createTooltip('Lowest correlation found. Shows the game where ESPN and Kalshi disagreed the most.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.min, 3)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Max${createTooltip('Highest correlation found. Shows the game where ESPN and Kalshi agreed the most.')}</span>
                            <span class="stat-row-value">${formatNumber(c.correlation.max, 3)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Count${createTooltip('Number of games with both ESPN and Kalshi data available for comparison.')}</span>
                            <span class="stat-row-value">${c.correlation.count || 0}</span>
                        </div>
                    </div>
                    ` : ''}
                    
                    ${c.mean_absolute_difference ? `
                    <div class="stats-group">
                        <div class="stats-group-title">Difference Metrics${createTooltip('Measures how much ESPN and Kalshi probabilities disagree. This does NOT say which is better - it only measures disagreement. Lower values = they agree more. Higher values = they disagree more.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Mean Absolute Difference (ESPN vs Kalshi)${createTooltip('Average difference between ESPN and Kalshi probabilities across all games. If ESPN says 60% and Kalshi says 55%, that\'s a 5% difference. This measures disagreement, not accuracy - it doesn\'t tell us which predictor is better.')}</span>
                            <span class="stat-row-value">${formatPercent(c.mean_absolute_difference.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">MAD (Median)${createTooltip('Middle value of the difference. Half of games have smaller differences, half have larger differences.')}</span>
                            <span class="stat-row-value">${formatPercent(c.mean_absolute_difference.median)}</span>
                        </div>
                        ${c.mean_absolute_difference.p25 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">MAD P25${createTooltip('25% of games have smaller differences than this. These are games where ESPN and Kalshi agreed well.')}</span>
                            <span class="stat-row-value">${formatPercent(c.mean_absolute_difference.p25)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">MAD P75${createTooltip('75% of games have smaller differences than this. Games above this had significant disagreement between ESPN and Kalshi.')}</span>
                            <span class="stat-row-value">${formatPercent(c.mean_absolute_difference.p75)}</span>
                        </div>
                        ` : ''}
                        ${c.max_absolute_difference ? `
                        <div class="stats-group-title">Max Divergence${createTooltip('Maximum absolute difference between ESPN and Kalshi probabilities per game. Shows the worst-case disagreement in each game.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Max Difference (Mean)${createTooltip('Average of the maximum differences across all games.')}</span>
                            <span class="stat-row-value">${formatPercent(c.max_absolute_difference.mean)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Max Difference (Median)${createTooltip('Middle value of maximum differences. Half of games had smaller max differences, half had larger.')}</span>
                            <span class="stat-row-value">${formatPercent(c.max_absolute_difference.median)}</span>
                        </div>
                        ${c.max_absolute_difference.p75 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Max Difference (P75)${createTooltip('75% of games have smaller max differences than this.')}</span>
                            <span class="stat-row-value">${formatPercent(c.max_absolute_difference.p75)}</span>
                        </div>
                        ` : ''}
                        ${c.max_absolute_difference.p90 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Max Difference (P90)${createTooltip('90% of games have smaller max differences than this.')}</span>
                            <span class="stat-row-value">${formatPercent(c.max_absolute_difference.p90)}</span>
                        </div>
                        ` : ''}
                        <div class="stat-row">
                            <span class="stat-row-label">Max Difference (Max)${createTooltip('Largest single difference found between ESPN and Kalshi in any game. Shows the worst-case disagreement.')}</span>
                            <span class="stat-row-value">${formatPercent(c.max_absolute_difference.max)}</span>
                        </div>
                        ` : ''}
                        ${c.sign_flips ? `
                        <div class="stats-group-title">Sign Flips${createTooltip('Count of times ESPN and Kalshi moved in opposite directions (one ↑ while the other ↓). Uses epsilon threshold (0.005) to filter noise. High values indicate fundamental disagreement about game dynamics.')}</div>
                        <div class="stat-row">
                            <span class="stat-row-label">Sign Flips (Total)${createTooltip('Total number of sign flips across all games.')}</span>
                            <span class="stat-row-value">${c.sign_flips.total || 0}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Sign Flips (Mean per Game)${createTooltip('Average number of sign flips per game.')}</span>
                            <span class="stat-row-value">${formatNumber(c.sign_flips.mean, 1)}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-row-label">Sign Flips (Median)${createTooltip('Middle value of sign flips per game.')}</span>
                            <span class="stat-row-value">${formatNumber(c.sign_flips.median, 1)}</span>
                        </div>
                        ${c.sign_flips.p75 ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Sign Flips (P75)${createTooltip('75% of games have fewer sign flips than this.')}</span>
                            <span class="stat-row-value">${formatNumber(c.sign_flips.p75, 1)}</span>
                        </div>
                        ` : ''}
                        <div class="stat-row">
                            <span class="stat-row-label">Sign Flips (Max)${createTooltip('Maximum number of sign flips in a single game.')}</span>
                            <span class="stat-row-value">${c.sign_flips.max || 0}</span>
                        </div>
                        ` : ''}
                        ${c.decision_weighted_brier ? `
                        <div class="stats-group-title">Decision-Weighted Brier${createTooltip('Brier scores weighted by decision-relevance. Confidence-weighted: weights by distance from 0.5 (more weight on confident predictions). Market-actionable: only scores when Kalshi bid/ask exists (market is active). Lower = better.')}</div>
                        ${c.decision_weighted_brier.confidence_weighted ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Confidence-Weighted Brier (ESPN)${createTooltip('Weights each prediction by abs(p - 0.5). More confident predictions (further from 0.5) get more weight. Answers: "How accurate is ESPN when it\'s confident?"')}</span>
                            <span class="stat-row-value">${formatNumber(c.decision_weighted_brier.confidence_weighted.espn)}</span>
                        </div>
                        ${c.decision_weighted_brier.confidence_weighted.kalshi ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Confidence-Weighted Brier (Kalshi)${createTooltip('Weights each prediction by abs(p - 0.5). More confident predictions (further from 0.5) get more weight. Answers: "How accurate is Kalshi when it\'s confident?"')}</span>
                            <span class="stat-row-value">${formatNumber(c.decision_weighted_brier.confidence_weighted.kalshi)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                        ${c.decision_weighted_brier.market_actionable ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Market-Actionable Brier (ESPN)${createTooltip('Only scores when Kalshi bid/ask exists (market is active). Answers: "How accurate is ESPN when money is actually at stake?"')}</span>
                            <span class="stat-row-value">${formatNumber(c.decision_weighted_brier.market_actionable.espn)}</span>
                        </div>
                        ${c.decision_weighted_brier.market_actionable.kalshi ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Market-Actionable Brier (Kalshi)${createTooltip('Only scores when Kalshi bid/ask exists (market is active). Answers: "How accurate is Kalshi when money is actually at stake?"')}</span>
                            <span class="stat-row-value">${formatNumber(c.decision_weighted_brier.market_actionable.kalshi)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                        ` : ''}
                        ${c.distance_weighted_mad ? `
                        <div class="stat-row">
                            <span class="stat-row-label">Distance-Weighted MAD${createTooltip('Mean Absolute Difference weighted by abs(p - 0.5). Confident predictions (farther from 0.5) receive more weight. Answers: "How much do they disagree when predictions are confident?"')}</span>
                            <span class="stat-row-value">${formatPercent(c.distance_weighted_mad.mean)}</span>
                        </div>
                        ` : ''}
                        ${c.ev_positive_disagreements ? `
                        <div class="stat-row">
                            <span class="stat-row-label">EV-Positive Disagreements (Total)${createTooltip('Count of times ESPN and Kalshi disagreed significantly (>10%) and one had positive expected value. May indicate systematic bias or suggest one source may be better calibrated in certain regions.')}</span>
                            <span class="stat-row-value">${c.ev_positive_disagreements.total || 0}</span>
                        </div>
                        ${c.ev_positive_disagreements.mean ? `
                        <div class="stat-row">
                            <span class="stat-row-label">EV-Positive Disagreements (Mean per Game)${createTooltip('Average number of EV-positive disagreement events per game.')}</span>
                            <span class="stat-row-value">${formatNumber(c.ev_positive_disagreements.mean, 1)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // Render charts after HTML is inserted
    setTimeout(() => {
        // Time-Averaged In-Game Brier Error Histogram
        const espnBrierDataForChart = stats.espn?.time_averaged_in_game_brier_error;
        if (espnBrierDataForChart?.distribution && espnBrierDataForChart.distribution.length > 0) {
            const brierHist = createHistogram(espnBrierDataForChart.distribution, 'Time-Averaged In-Game Brier Error', '#00d4aa');
            if (brierHist) {
                renderChart('brierChart', 'bar', {
                    labels: brierHist.labels,
                    datasets: [{
                        label: brierHist.label,
                        data: brierHist.data,
                        backgroundColor: 'rgba(0, 212, 170, 0.3)',
                        borderColor: '#00d4aa',
                        borderWidth: 1
                    }]
                });
            }
        }
        
        // Correlation Histogram
        if (stats.comparison?.correlation?.distribution && stats.comparison.correlation.distribution.length > 0) {
            const corrHist = createHistogram(stats.comparison.correlation.distribution, 'Correlation', '#7c3aed');
            if (corrHist) {
                renderChart('correlationChart', 'bar', {
                    labels: corrHist.labels,
                    datasets: [{
                        label: corrHist.label,
                        data: corrHist.data,
                        backgroundColor: 'rgba(124, 58, 237, 0.3)',
                        borderColor: '#7c3aed',
                        borderWidth: 1
                    }]
                });
            }
        }
        
        // Volatility Scatter Plot
        if (stats.comparison?.espn_volatility_vs_kalshi_volatility && stats.comparison.espn_volatility_vs_kalshi_volatility.length > 0) {
            const scatter = createScatterPlot(stats.comparison.espn_volatility_vs_kalshi_volatility, 'espn', 'kalshi', '#00d4aa', '#f7931a');
            if (scatter) {
                const scatterData = stats.comparison.espn_volatility_vs_kalshi_volatility;
                
                // Find min/max for diagonal line
                const allX = scatter.x;
                const allY = scatter.y;
                const minVal = Math.min(Math.min(...allX), Math.min(...allY));
                const maxVal = Math.max(Math.max(...allX), Math.max(...allY));
                
                // Story 3.3: Group points by margin buckets for color coding
                const marginBuckets = {
                    close: [],      // 0-5 pts
                    moderate: [],   // 6-10 pts
                    comfortable: [], // 11-20 pts
                    blowout: [],    // 21+ pts
                    unknown: []     // null/undefined
                };
                
                scatter.x.forEach((x, i) => {
                    const margin = scatterData[i]?.final_margin;
                    const point = { x: x, y: scatter.y[i], margin: margin };
                    if (margin === null || margin === undefined) {
                        marginBuckets.unknown.push(point);
                    } else if (margin <= 5) {
                        marginBuckets.close.push(point);
                    } else if (margin <= 10) {
                        marginBuckets.moderate.push(point);
                    } else if (margin <= 20) {
                        marginBuckets.comfortable.push(point);
                    } else {
                        marginBuckets.blowout.push(point);
                    }
                });
                
                const datasets = [
                    // Close games (0-5 pts) - Blue
                    {
                        label: 'Close (0-5 pts)',
                        data: marginBuckets.close,
                        backgroundColor: 'rgba(0, 100, 255, 0.6)',
                        borderColor: 'rgba(0, 100, 255, 1)',
                        pointRadius: 3
                    },
                    // Moderate (6-10 pts) - Light blue
                    {
                        label: 'Moderate (6-10 pts)',
                        data: marginBuckets.moderate,
                        backgroundColor: 'rgba(100, 150, 255, 0.6)',
                        borderColor: 'rgba(100, 150, 255, 1)',
                        pointRadius: 3
                    },
                    // Comfortable (11-20 pts) - Orange
                    {
                        label: 'Comfortable (11-20 pts)',
                        data: marginBuckets.comfortable,
                        backgroundColor: 'rgba(255, 150, 100, 0.6)',
                        borderColor: 'rgba(255, 150, 100, 1)',
                        pointRadius: 3
                    },
                    // Blowout (21+ pts) - Red
                    {
                        label: 'Blowout (21+ pts)',
                        data: marginBuckets.blowout,
                        backgroundColor: 'rgba(255, 50, 50, 0.6)',
                        borderColor: 'rgba(255, 50, 50, 1)',
                        pointRadius: 3
                    },
                    // Unknown margin - Dark purple (fallback)
                    ...(marginBuckets.unknown.length > 0 ? [{
                        label: 'Unknown margin',
                        data: marginBuckets.unknown,
                        backgroundColor: 'rgba(124, 58, 237, 0.3)',
                        borderColor: '#7c3aed',
                        pointRadius: 3
                    }] : []),
                    // Diagonal reference line (y = x)
                    {
                        label: 'Reference Line (y = x)',
                        data: [
                            { x: minVal, y: minVal },
                            { x: maxVal, y: maxVal }
                        ],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.3)',
                        borderWidth: 1,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    }
                ];
                
                renderChart('volatilityScatterChart', 'scatter', {
                    datasets: datasets
                }, {
                    scales: {
                        x: {
                            title: { display: true, text: 'ESPN Volatility', color: '#888899' },
                            ticks: { color: '#888899' },
                            grid: { color: '#2a2a40' },
                            min: minVal * 0.95,
                            max: maxVal * 1.05
                        },
                        y: {
                            title: { display: true, text: 'Kalshi Volatility', color: '#888899' },
                            ticks: { color: '#888899' },
                            grid: { color: '#2a2a40' },
                            min: minVal * 0.95,
                            max: maxVal * 1.05
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#888899',
                                filter: (item) => item.text !== 'Reference Line (y = x)'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    const point = context.raw;
                                    let label = `ESPN: ${context.parsed.x.toFixed(4)}, Kalshi: ${context.parsed.y.toFixed(4)}`;
                                    if (point.margin !== null && point.margin !== undefined) {
                                        const margin = point.margin;
                                        let marginCategory = '';
                                        if (margin <= 5) marginCategory = ' (Close game)';
                                        else if (margin <= 10) marginCategory = ' (Moderate)';
                                        else if (margin <= 20) marginCategory = ' (Comfortable)';
                                        else marginCategory = ' (Blowout)';
                                        label += `\nFinal Margin: ${margin} points${marginCategory}`;
                                    }
                                    return label;
                                }
                            }
                        }
                    }
                });
            }
        }
        
        // Mean Absolute Difference Histogram
        if (stats.comparison?.mean_absolute_difference?.distribution && stats.comparison.mean_absolute_difference.distribution.length > 0) {
            const maeHist = createHistogram(stats.comparison.mean_absolute_difference.distribution, 'Mean Absolute Difference (ESPN vs Kalshi)', '#ff6b6b');
            if (maeHist) {
                renderChart('maeChart', 'bar', {
                    labels: maeHist.labels,
                    datasets: [{
                        label: maeHist.label,
                        data: maeHist.data,
                        backgroundColor: 'rgba(255, 107, 107, 0.3)',
                        borderColor: '#ff6b6b',
                        borderWidth: 1
                    }]
                });
            }
        }
        
        // Story 3.1: ESPN Reliability Curve
        if (stats.espn?.reliability_curve?.bins && stats.espn.reliability_curve.bins.length > 0) {
            const bins = stats.espn.reliability_curve.bins;
            const dataPoints = bins.map(bin => ({
                x: bin.predicted_prob,
                y: bin.actual_freq
            }));
            
            // Find min/max for diagonal line
            const allValues = [...dataPoints.map(p => p.x), ...dataPoints.map(p => p.y)];
            const minVal = Math.min(...allValues);
            const maxVal = Math.max(...allValues);
            
            renderChart('espnReliabilityChart', 'scatter', {
                datasets: [
                    {
                        label: 'ESPN Reliability',
                        data: dataPoints,
                        backgroundColor: 'rgba(0, 212, 170, 0.6)',
                        borderColor: '#00d4aa',
                        pointRadius: 6,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Perfect Calibration (y = x)',
                        data: [
                            { x: minVal, y: minVal },
                            { x: maxVal, y: maxVal }
                        ],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    }
                ]
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'Predicted Probability', color: '#888899' },
                        min: 0,
                        max: 1,
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                if (context.datasetIndex === 0) {
                                    const bin = bins[context.dataIndex];
                                    return `Predicted: ${(bin.predicted_prob * 100).toFixed(1)}%, Actual: ${(bin.actual_freq * 100).toFixed(1)}%, Count: ${bin.count}`;
                                }
                                return context.dataset.label;
                            }
                        }
                    }
                }
            });
        }
        
        // Story 3.1: Kalshi Reliability Curve
        if (stats.kalshi?.reliability_curve?.bins && stats.kalshi.reliability_curve.bins.length > 0) {
            const bins = stats.kalshi.reliability_curve.bins;
            const dataPoints = bins.map(bin => ({
                x: bin.predicted_prob,
                y: bin.actual_freq
            }));
            
            // Find min/max for diagonal line
            const allValues = [...dataPoints.map(p => p.x), ...dataPoints.map(p => p.y)];
            const minVal = Math.min(...allValues);
            const maxVal = Math.max(...allValues);
            
            renderChart('kalshiReliabilityChart', 'scatter', {
                datasets: [
                    {
                        label: 'Kalshi Reliability',
                        data: dataPoints,
                        backgroundColor: 'rgba(247, 147, 26, 0.6)',
                        borderColor: '#f7931a',
                        pointRadius: 6,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Perfect Calibration (y = x)',
                        data: [
                            { x: minVal, y: minVal },
                            { x: maxVal, y: maxVal }
                        ],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    }
                ]
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'Predicted Probability', color: '#888899' },
                        min: 0,
                        max: 1,
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                if (context.datasetIndex === 0) {
                                    const bin = bins[context.dataIndex];
                                    return `Predicted: ${(bin.predicted_prob * 100).toFixed(1)}%, Actual: ${(bin.actual_freq * 100).toFixed(1)}%, Count: ${bin.count}`;
                                }
                                return context.dataset.label;
                            }
                        }
                    }
                }
            });
        }
        
        // Model Calibration Chart - 2024 Season
        if (modelEval2024 && modelEval2024.eval && modelEval2024.eval.calibration_points && modelEval2024.eval.calibration_points.length > 0) {
            console.log('[FRONTEND] Rendering model calibration chart (2024) with', modelEval2024.eval.calibration_points.length, 'points');
            const calibrationPoints = modelEval2024.eval.calibration_points;
            const minVal = 0;
            const maxVal = 1;
            
            renderChart('modelCalibrationChart2024', 'scatter', {
                datasets: [
                    {
                        label: 'Model Calibration',
                        data: calibrationPoints.map(p => ({ x: p.x, y: p.y, n: p.n, gap: p.gap })),
                        backgroundColor: 'rgba(124, 58, 237, 0.6)',
                        borderColor: '#7c3aed',
                        pointRadius: calibrationPoints.map(p => {
                            // Size points by sample count
                            const n = p.n || 0;
                            return Math.max(3, Math.min(10, 3 + (n / 10000)));
                        }),
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Perfect Calibration (y = x)',
                        data: [
                            { x: minVal, y: minVal },
                            { x: maxVal, y: maxVal }
                        ],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    }
                ]
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'Predicted Probability', color: '#888899' },
                        min: 0,
                        max: 1,
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                if (context.datasetIndex === 0) {
                                    const point = context.raw;
                                    const gap = point.gap || 0;
                                    const gapText = gap > 0 ? `+${(gap * 100).toFixed(2)}%` : `${(gap * 100).toFixed(2)}%`;
                                    return [
                                        `Predicted: ${(point.x * 100).toFixed(1)}%`,
                                        `Actual: ${(point.y * 100).toFixed(1)}%`,
                                        `Gap: ${gapText}`,
                                        `Samples: ${point.n || 0}`
                                    ];
                                }
                                return context.dataset.label;
                            }
                        }
                    },
                    legend: {
                        display: true,
                        labels: {
                            color: '#888899',
                            filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                        }
                    }
                }
            });
        }
        
        // Model Calibration Chart - All Seasons
        if (modelEvalAll && modelEvalAll.eval && modelEvalAll.eval.calibration_points && modelEvalAll.eval.calibration_points.length > 0) {
            console.log('[FRONTEND] Rendering model calibration chart (all seasons) with', modelEvalAll.eval.calibration_points.length, 'points');
            const calibrationPoints = modelEvalAll.eval.calibration_points;
            const minVal = 0;
            const maxVal = 1;
            
            renderChart('modelCalibrationChartAll', 'scatter', {
                datasets: [
                    {
                        label: 'Model Calibration (All Seasons)',
                        data: calibrationPoints.map(p => ({ x: p.x, y: p.y, n: p.n, gap: p.gap })),
                        backgroundColor: 'rgba(124, 58, 237, 0.6)',
                        borderColor: '#7c3aed',
                        pointRadius: calibrationPoints.map(p => {
                            // Size points by sample count
                            const n = p.n || 0;
                            return Math.max(3, Math.min(10, 3 + (n / 10000)));
                        }),
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Perfect Calibration (y = x)',
                        data: [
                            { x: minVal, y: minVal },
                            { x: maxVal, y: maxVal }
                        ],
                        type: 'line',
                        borderColor: 'rgba(255, 255, 255, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0
                    }
                ]
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'Predicted Probability', color: '#888899' },
                        min: 0,
                        max: 1,
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                if (context.datasetIndex === 0) {
                                    const point = context.raw;
                                    const gap = point.gap || 0;
                                    const gapText = gap > 0 ? `+${(gap * 100).toFixed(2)}%` : `${(gap * 100).toFixed(2)}%`;
                                    return [
                                        `Predicted: ${(point.x * 100).toFixed(1)}%`,
                                        `Actual: ${(point.y * 100).toFixed(1)}%`,
                                        `Gap: ${gapText}`,
                                        `Samples: ${point.n || 0}`
                                    ];
                                }
                                return context.dataset.label;
                            }
                        }
                    },
                    legend: {
                        display: true,
                        labels: {
                            color: '#888899',
                            filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                        }
                    }
                }
            });
        }
        
        // Story 3.2: Phase Brier Chart
        if (stats.espn?.brier_by_phase?.espn) {
            const espnPhases = stats.espn.brier_by_phase.espn;
            const kalshiPhases = stats.espn.brier_by_phase.kalshi;
            const phases = ['Early', 'Mid', 'Late', 'Clutch'];
            
            const datasets = [
                {
                    label: 'ESPN',
                    data: [
                        espnPhases.early,
                        espnPhases.mid,
                        espnPhases.late,
                        espnPhases.clutch
                    ].map(v => v !== null && v !== undefined ? v : null),
                    backgroundColor: 'rgba(0, 212, 170, 0.6)',
                    borderColor: '#00d4aa',
                    borderWidth: 1
                }
            ];
            
            if (kalshiPhases) {
                datasets.push({
                    label: 'Kalshi',
                    data: [
                        kalshiPhases.early,
                        kalshiPhases.mid,
                        kalshiPhases.late,
                        kalshiPhases.clutch
                    ].map(v => v !== null && v !== undefined ? v : null),
                    backgroundColor: 'rgba(247, 147, 26, 0.6)',
                    borderColor: '#f7931a',
                    borderWidth: 1
                });
            }
            
            renderChart('phaseBrierChart', 'bar', {
                labels: phases,
                datasets: datasets
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'Game Phase', color: '#888899' },
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Time-Averaged In-Game Brier Error', color: '#888899' },
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' },
                        beginAtZero: true
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                if (value === null || value === undefined) return context.dataset.label + ': N/A';
                                return context.dataset.label + ': ' + value.toFixed(4);
                            }
                        }
                    }
                }
            });
        }
        
        // Story 3.4: Disagreement vs Outcome Chart
        if (stats.comparison?.disagreement_vs_outcome && stats.comparison.disagreement_vs_outcome.length > 0) {
            const bins = stats.comparison.disagreement_vs_outcome;
            const labels = bins.map(bin => {
                const center = bin.bin_center || ((bin.bin_min + bin.bin_max) / 2);
                return center.toFixed(2);
            });
            const winRates = bins.map(bin => bin.home_win_rate);
            const counts = bins.map(bin => bin.count);
            
            renderChart('disagreementOutcomeChart', 'bar', {
                labels: labels,
                datasets: [{
                    label: 'Home Win Rate',
                    data: winRates,
                    backgroundColor: 'rgba(124, 58, 237, 0.6)',
                    borderColor: '#7c3aed',
                    borderWidth: 1
                }]
            }, {
                scales: {
                    x: {
                        title: { display: true, text: 'ESPN - Kalshi (Signed Difference)', color: '#888899' },
                        ticks: { color: '#888899' },
                        grid: { color: '#2a2a40' }
                    },
                    y: {
                        title: { display: true, text: 'Actual Home Win Rate', color: '#888899' },
                        min: 0,
                        max: 1,
                        ticks: { 
                            color: '#888899',
                            callback: function(value) {
                                return (value * 100).toFixed(0) + '%';
                            }
                        },
                        grid: { color: '#2a2a40' }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const bin = bins[context.dataIndex];
                                return `Win Rate: ${(bin.home_win_rate * 100).toFixed(1)}% (n=${bin.count})`;
                            },
                            afterLabel: function(context) {
                                const bin = bins[context.dataIndex];
                                return `Range: [${bin.bin_min.toFixed(2)}, ${bin.bin_max.toFixed(2)})`;
                            }
                        }
                    }
                }
            });
        }
    }, 100);
}

// Store current stats data for export
let currentStatsData = null;
let currentModelEval2024 = null;
let currentModelEvalAll = null;

// Wrap renderAggregateStats to store data
const originalRenderAggregateStats = renderAggregateStats;
renderAggregateStats = function(stats, modelEval2024, modelEvalAll) {
    currentStatsData = stats;
    currentModelEval2024 = modelEval2024;
    currentModelEvalAll = modelEvalAll;
    return originalRenderAggregateStats(stats, modelEval2024, modelEvalAll);
};

// HTML Export Function
async function exportToHTML() {
    if (!currentStatsData) {
        alert('No data available to export. Please wait for stats to load.');
        return;
    }
    
    try {
        // Fetch CSS content
        const cssResponse = await fetch('/static/css/styles.css');
        const cssContent = await cssResponse.text();
        
        // Get the current HTML content
        const container = document.getElementById('aggregateStatsContainer');
        if (!container) {
            alert('Stats container not found.');
            return;
        }
        
        // Clone the container to avoid modifying the original
        const clonedContainer = container.cloneNode(true);
        
        // Create standalone HTML with embedded data and Chart.js rendering code
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aggregate Statistics Export - ${new Date().toLocaleDateString()}</title>
    <style>
${cssContent}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="stats-page-header">
            <div>
                <h2>Aggregate Statistics</h2>
                <p class="stats-page-subtitle">Data science metrics across all matched ESPN/Kalshi games</p>
                <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 8px;">
                    Exported on ${new Date().toLocaleString()}
                </p>
            </div>
        </div>
        ${clonedContainer.innerHTML}
    </div>
    <script>
        // Embedded data
        const statsData = ${JSON.stringify(currentStatsData, null, 2)};
        const modelEval2024 = ${JSON.stringify(currentModelEval2024, null, 2)};
        const modelEvalAll = ${JSON.stringify(currentModelEvalAll, null, 2)};
        
        // Chart rendering helper functions
        function createHistogram(data, label, color, bins = 30) {
            if (!data || data.length === 0) return null;
            const min = Math.min(...data);
            const max = Math.max(...data);
            const binWidth = (max - min) / bins;
            const histogram = new Array(bins).fill(0);
            const binLabels = [];
            for (let i = 0; i < bins; i++) {
                binLabels.push((min + (i + 0.5) * binWidth).toFixed(3));
            }
            data.forEach(value => {
                const binIndex = Math.min(Math.floor((value - min) / binWidth), bins - 1);
                histogram[binIndex]++;
            });
            return { labels: binLabels, data: histogram, label: label, color: color };
        }
        
        function createScatterPlot(data, xLabel, yLabel, xColor, yColor) {
            if (!data || data.length === 0) return null;
            return {
                x: data.map(d => d[xLabel]),
                y: data.map(d => d[yLabel]),
                xLabel: xLabel,
                yLabel: yLabel,
                xColor: xColor,
                yColor: yColor
            };
        }
        
        function renderChart(canvasId, chartType, chartData, options = {}) {
            const canvas = document.getElementById(canvasId);
            if (!canvas || !chartData) return null;
            const ctx = canvas.getContext('2d');
            const defaultOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#e8e8f0' } }
                },
                scales: {
                    x: { ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                    y: { ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                }
            };
            const config = { type: chartType, data: chartData, options: { ...defaultOptions, ...options } };
            return new Chart(ctx, config);
        }
        
        // Render all charts after page load
        window.addEventListener('load', function() {
            setTimeout(() => {
                const stats = statsData;
                
                // Time-Averaged In-Game Brier Error Histogram
                const espnBrierDataForChart = stats.espn?.time_averaged_in_game_brier_error;
                if (espnBrierDataForChart?.distribution && espnBrierDataForChart.distribution.length > 0) {
                    const brierHist = createHistogram(espnBrierDataForChart.distribution, 'Time-Averaged In-Game Brier Error', '#00d4aa');
                    if (brierHist) {
                        renderChart('brierChart', 'bar', {
                            labels: brierHist.labels,
                            datasets: [{
                                label: brierHist.label,
                                data: brierHist.data,
                                backgroundColor: 'rgba(0, 212, 170, 0.3)',
                                borderColor: '#00d4aa',
                                borderWidth: 1
                            }]
                        });
                    }
                }
                
                // Correlation Histogram
                if (stats.comparison?.correlation?.distribution && stats.comparison.correlation.distribution.length > 0) {
                    const corrHist = createHistogram(stats.comparison.correlation.distribution, 'Correlation', '#7c3aed');
                    if (corrHist) {
                        renderChart('correlationChart', 'bar', {
                            labels: corrHist.labels,
                            datasets: [{
                                label: corrHist.label,
                                data: corrHist.data,
                                backgroundColor: 'rgba(124, 58, 237, 0.3)',
                                borderColor: '#7c3aed',
                                borderWidth: 1
                            }]
                        });
                    }
                }
                
                // Volatility Scatter Plot
                if (stats.comparison?.espn_volatility_vs_kalshi_volatility && stats.comparison.espn_volatility_vs_kalshi_volatility.length > 0) {
                    const scatter = createScatterPlot(stats.comparison.espn_volatility_vs_kalshi_volatility, 'espn', 'kalshi', '#00d4aa', '#f7931a');
                    if (scatter) {
                        const scatterData = stats.comparison.espn_volatility_vs_kalshi_volatility;
                        const allX = scatter.x;
                        const allY = scatter.y;
                        const minVal = Math.min(Math.min(...allX), Math.min(...allY));
                        const maxVal = Math.max(Math.max(...allX), Math.max(...allY));
                        
                        const marginBuckets = { close: [], moderate: [], comfortable: [], blowout: [], unknown: [] };
                        scatter.x.forEach((x, i) => {
                            const margin = scatterData[i]?.final_margin;
                            const point = { x: x, y: scatter.y[i], margin: margin };
                            if (margin === null || margin === undefined) {
                                marginBuckets.unknown.push(point);
                            } else if (margin <= 5) {
                                marginBuckets.close.push(point);
                            } else if (margin <= 10) {
                                marginBuckets.moderate.push(point);
                            } else if (margin <= 20) {
                                marginBuckets.comfortable.push(point);
                            } else {
                                marginBuckets.blowout.push(point);
                            }
                        });
                        
                        const datasets = [
                            { label: 'Close (0-5 pts)', data: marginBuckets.close, backgroundColor: 'rgba(0, 100, 255, 0.6)', borderColor: 'rgba(0, 100, 255, 1)', pointRadius: 3 },
                            { label: 'Moderate (6-10 pts)', data: marginBuckets.moderate, backgroundColor: 'rgba(100, 150, 255, 0.6)', borderColor: 'rgba(100, 150, 255, 1)', pointRadius: 3 },
                            { label: 'Comfortable (11-20 pts)', data: marginBuckets.comfortable, backgroundColor: 'rgba(255, 150, 100, 0.6)', borderColor: 'rgba(255, 150, 100, 1)', pointRadius: 3 },
                            { label: 'Blowout (21+ pts)', data: marginBuckets.blowout, backgroundColor: 'rgba(255, 50, 50, 0.6)', borderColor: 'rgba(255, 50, 50, 1)', pointRadius: 3 },
                            ...(marginBuckets.unknown.length > 0 ? [{ label: 'Unknown margin', data: marginBuckets.unknown, backgroundColor: 'rgba(124, 58, 237, 0.3)', borderColor: '#7c3aed', pointRadius: 3 }] : []),
                            { label: 'Reference Line (y = x)', data: [{ x: minVal, y: minVal }, { x: maxVal, y: maxVal }], type: 'line', borderColor: 'rgba(255, 255, 255, 0.3)', borderWidth: 1, borderDash: [5, 5], pointRadius: 0, fill: false, tension: 0 }
                        ];
                        
                        renderChart('volatilityScatterChart', 'scatter', {
                            datasets: datasets
                        }, {
                            scales: {
                                x: { title: { display: true, text: 'ESPN Volatility', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' }, min: minVal * 0.95, max: maxVal * 1.05 },
                                y: { title: { display: true, text: 'Kalshi Volatility', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' }, min: minVal * 0.95, max: maxVal * 1.05 }
                            },
                            plugins: {
                                legend: { display: true, labels: { color: '#888899', filter: (item) => item.text !== 'Reference Line (y = x)' } },
                                tooltip: {
                                    callbacks: {
                                        label: (context) => {
                                            const point = context.raw;
                                            let label = \`ESPN: \${context.parsed.x.toFixed(4)}, Kalshi: \${context.parsed.y.toFixed(4)}\`;
                                            if (point.margin !== null && point.margin !== undefined) {
                                                const margin = point.margin;
                                                let marginCategory = '';
                                                if (margin <= 5) marginCategory = ' (Close game)';
                                                else if (margin <= 10) marginCategory = ' (Moderate)';
                                                else if (margin <= 20) marginCategory = ' (Comfortable)';
                                                else marginCategory = ' (Blowout)';
                                                label += \`\\nFinal Margin: \${margin} points\${marginCategory}\`;
                                            }
                                            return label;
                                        }
                                    }
                                }
                            }
                        });
                    }
                }
                
                // Mean Absolute Difference Histogram
                if (stats.comparison?.mean_absolute_difference?.distribution && stats.comparison.mean_absolute_difference.distribution.length > 0) {
                    const maeHist = createHistogram(stats.comparison.mean_absolute_difference.distribution, 'Mean Absolute Difference (ESPN vs Kalshi)', '#ff6b6b');
                    if (maeHist) {
                        renderChart('maeChart', 'bar', {
                            labels: maeHist.labels,
                            datasets: [{
                                label: maeHist.label,
                                data: maeHist.data,
                                backgroundColor: 'rgba(255, 107, 107, 0.3)',
                                borderColor: '#ff6b6b',
                                borderWidth: 1
                            }]
                        });
                    }
                }
                
                // ESPN Reliability Curve
                if (stats.espn?.reliability_curve?.bins && stats.espn.reliability_curve.bins.length > 0) {
                    const bins = stats.espn.reliability_curve.bins;
                    const dataPoints = bins.map(bin => ({ x: bin.predicted_prob, y: bin.actual_freq }));
                    const allValues = [...dataPoints.map(p => p.x), ...dataPoints.map(p => p.y)];
                    const minVal = Math.min(...allValues);
                    const maxVal = Math.max(...allValues);
                    
                    renderChart('espnReliabilityChart', 'scatter', {
                        datasets: [
                            { label: 'ESPN Reliability', data: dataPoints, backgroundColor: 'rgba(0, 212, 170, 0.6)', borderColor: '#00d4aa', pointRadius: 6, pointHoverRadius: 8 },
                            { label: 'Perfect Calibration (y = x)', data: [{ x: minVal, y: minVal }, { x: maxVal, y: maxVal }], type: 'line', borderColor: 'rgba(255, 255, 255, 0.5)', borderWidth: 2, borderDash: [5, 5], pointRadius: 0, fill: false, tension: 0 }
                        ]
                    }, {
                        scales: {
                            x: { title: { display: true, text: 'Predicted Probability', color: '#888899' }, min: 0, max: 1, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                            y: { title: { display: true, text: 'Actual Win Rate', color: '#888899' }, min: 0, max: 1, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        if (context.datasetIndex === 0) {
                                            const bin = bins[context.dataIndex];
                                            return \`Predicted: \${(bin.predicted_prob * 100).toFixed(1)}%, Actual: \${(bin.actual_freq * 100).toFixed(1)}%, Count: \${bin.count}\`;
                                        }
                                        return context.dataset.label;
                                    }
                                }
                            }
                        }
                    });
                }
                
                // Kalshi Reliability Curve
                if (stats.kalshi?.reliability_curve?.bins && stats.kalshi.reliability_curve.bins.length > 0) {
                    const bins = stats.kalshi.reliability_curve.bins;
                    const dataPoints = bins.map(bin => ({ x: bin.predicted_prob, y: bin.actual_freq }));
                    const allValues = [...dataPoints.map(p => p.x), ...dataPoints.map(p => p.y)];
                    const minVal = Math.min(...allValues);
                    const maxVal = Math.max(...allValues);
                    
                    renderChart('kalshiReliabilityChart', 'scatter', {
                        datasets: [
                            { label: 'Kalshi Reliability', data: dataPoints, backgroundColor: 'rgba(247, 147, 26, 0.6)', borderColor: '#f7931a', pointRadius: 6, pointHoverRadius: 8 },
                            { label: 'Perfect Calibration (y = x)', data: [{ x: minVal, y: minVal }, { x: maxVal, y: maxVal }], type: 'line', borderColor: 'rgba(255, 255, 255, 0.5)', borderWidth: 2, borderDash: [5, 5], pointRadius: 0, fill: false, tension: 0 }
                        ]
                    }, {
                        scales: {
                            x: { title: { display: true, text: 'Predicted Probability', color: '#888899' }, min: 0, max: 1, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                            y: { title: { display: true, text: 'Actual Win Rate', color: '#888899' }, min: 0, max: 1, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        if (context.datasetIndex === 0) {
                                            const bin = bins[context.dataIndex];
                                            return \`Predicted: \${(bin.predicted_prob * 100).toFixed(1)}%, Actual: \${(bin.actual_freq * 100).toFixed(1)}%, Count: \${bin.count}\`;
                                        }
                                        return context.dataset.label;
                                    }
                                }
                            }
                        }
                    });
                }
                
                // Phase Brier Chart
                if (stats.espn?.brier_by_phase?.espn) {
                    const espnPhases = stats.espn.brier_by_phase.espn;
                    const kalshiPhases = stats.espn.brier_by_phase.kalshi;
                    const phases = ['Early', 'Mid', 'Late', 'Clutch'];
                    
                    const datasets = [{
                        label: 'ESPN',
                        data: [espnPhases.early, espnPhases.mid, espnPhases.late, espnPhases.clutch].map(v => v !== null && v !== undefined ? v : null),
                        backgroundColor: 'rgba(0, 212, 170, 0.6)',
                        borderColor: '#00d4aa',
                        borderWidth: 1
                    }];
                    
                    if (kalshiPhases) {
                        datasets.push({
                            label: 'Kalshi',
                            data: [kalshiPhases.early, kalshiPhases.mid, kalshiPhases.late, kalshiPhases.clutch].map(v => v !== null && v !== undefined ? v : null),
                            backgroundColor: 'rgba(247, 147, 26, 0.6)',
                            borderColor: '#f7931a',
                            borderWidth: 1
                        });
                    }
                    
                    renderChart('phaseBrierChart', 'bar', {
                        labels: phases,
                        datasets: datasets
                    }, {
                        scales: {
                            x: { title: { display: true, text: 'Game Phase', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                            y: { title: { display: true, text: 'Time-Averaged In-Game Brier Error', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' }, beginAtZero: true }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const value = context.parsed.y;
                                        if (value === null || value === undefined) return context.dataset.label + ': N/A';
                                        return context.dataset.label + ': ' + value.toFixed(4);
                                    }
                                }
                            }
                        }
                    });
                }
                
                // Disagreement vs Outcome Chart
                if (stats.comparison?.disagreement_vs_outcome && stats.comparison.disagreement_vs_outcome.length > 0) {
                    const bins = stats.comparison.disagreement_vs_outcome;
                    const labels = bins.map(bin => {
                        const center = bin.bin_center || ((bin.bin_min + bin.bin_max) / 2);
                        return center.toFixed(2);
                    });
                    const winRates = bins.map(bin => bin.home_win_rate);
                    
                    renderChart('disagreementOutcomeChart', 'bar', {
                        labels: labels,
                        datasets: [{
                            label: 'Home Win Rate',
                            data: winRates,
                            backgroundColor: 'rgba(124, 58, 237, 0.6)',
                            borderColor: '#7c3aed',
                            borderWidth: 1
                        }]
                    }, {
                        scales: {
                            x: { title: { display: true, text: 'ESPN - Kalshi (Signed Difference)', color: '#888899' }, ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                            y: { title: { display: true, text: 'Actual Home Win Rate', color: '#888899' }, min: 0, max: 1, ticks: { color: '#888899', callback: function(value) { return (value * 100).toFixed(0) + '%'; } }, grid: { color: '#2a2a40' } }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const bin = bins[context.dataIndex];
                                        return \`Win Rate: \${(bin.home_win_rate * 100).toFixed(1)}% (n=\${bin.count})\`;
                                    },
                                    afterLabel: function(context) {
                                        const bin = bins[context.dataIndex];
                                        return \`Range: [\${bin.bin_min.toFixed(2)}, \${bin.bin_max.toFixed(2)})\`;
                                    }
                                }
                            }
                        }
                    });
                }
                
                // Model Calibration Chart - 2024 Season
                if (modelEval2024 && modelEval2024.eval && modelEval2024.eval.calibration_points && modelEval2024.eval.calibration_points.length > 0) {
                    const calibrationPoints = modelEval2024.eval.calibration_points;
                    const minVal = 0;
                    const maxVal = 1;
                    
                    renderChart('modelCalibrationChart2024', 'scatter', {
                        datasets: [
                            {
                                label: 'Model Calibration',
                                data: calibrationPoints.map(p => ({ x: p.x, y: p.y, n: p.n, gap: p.gap })),
                                backgroundColor: 'rgba(124, 58, 237, 0.6)',
                                borderColor: '#7c3aed',
                                pointRadius: calibrationPoints.map(p => {
                                    const n = p.n || 0;
                                    return Math.max(3, Math.min(10, 3 + (n / 10000)));
                                }),
                                pointHoverRadius: 8
                            },
                            {
                                label: 'Perfect Calibration (y = x)',
                                data: [
                                    { x: minVal, y: minVal },
                                    { x: maxVal, y: maxVal }
                                ],
                                type: 'line',
                                borderColor: 'rgba(255, 255, 255, 0.5)',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                pointRadius: 0,
                                fill: false,
                                tension: 0
                            }
                        ]
                    }, {
                        scales: {
                            x: {
                                title: { display: true, text: 'Predicted Probability', color: '#888899' },
                                min: 0,
                                max: 1,
                                ticks: { color: '#888899' },
                                grid: { color: '#2a2a40' }
                            },
                            y: {
                                title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                        if (context.datasetIndex === 0) {
                                            const point = context.raw;
                                            const gap = point.gap || 0;
                                            const gapText = gap > 0 ? \`+\${(gap * 100).toFixed(2)}%\` : \`\${(gap * 100).toFixed(2)}%\`;
                                            return [
                                                \`Predicted: \${(point.x * 100).toFixed(1)}%\`,
                                                \`Actual: \${(point.y * 100).toFixed(1)}%\`,
                                                \`Gap: \${gapText}\`,
                                                \`Samples: \${point.n || 0}\`
                                            ];
                                        }
                                        return context.dataset.label;
                                    }
                                }
                            },
                            legend: {
                                display: true,
                                labels: {
                                    color: '#888899',
                                    filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                                }
                            }
                        }
                    });
                }
                
                // Model Calibration Chart - All Seasons
                if (modelEvalAll && modelEvalAll.eval && modelEvalAll.eval.calibration_points && modelEvalAll.eval.calibration_points.length > 0) {
                    const calibrationPoints = modelEvalAll.eval.calibration_points;
                    const minVal = 0;
                    const maxVal = 1;
                    
                    renderChart('modelCalibrationChartAll', 'scatter', {
                        datasets: [
                            {
                                label: 'Model Calibration (All Seasons)',
                                data: calibrationPoints.map(p => ({ x: p.x, y: p.y, n: p.n, gap: p.gap })),
                                backgroundColor: 'rgba(124, 58, 237, 0.6)',
                                borderColor: '#7c3aed',
                                pointRadius: calibrationPoints.map(p => {
                                    const n = p.n || 0;
                                    return Math.max(3, Math.min(10, 3 + (n / 10000)));
                                }),
                                pointHoverRadius: 8
                            },
                            {
                                label: 'Perfect Calibration (y = x)',
                                data: [
                                    { x: minVal, y: minVal },
                                    { x: maxVal, y: maxVal }
                                ],
                                type: 'line',
                                borderColor: 'rgba(255, 255, 255, 0.5)',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                pointRadius: 0,
                                fill: false,
                                tension: 0
                            }
                        ]
                    }, {
                        scales: {
                            x: {
                                title: { display: true, text: 'Predicted Probability', color: '#888899' },
                                min: 0,
                                max: 1,
                                ticks: { color: '#888899' },
                                grid: { color: '#2a2a40' }
                            },
                            y: {
                                title: { display: true, text: 'Actual Win Rate', color: '#888899' },
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
                                        if (context.datasetIndex === 0) {
                                            const point = context.raw;
                                            const gap = point.gap || 0;
                                            const gapText = gap > 0 ? \`+\${(gap * 100).toFixed(2)}%\` : \`\${(gap * 100).toFixed(2)}%\`;
                                            return [
                                                \`Predicted: \${(point.x * 100).toFixed(1)}%\`,
                                                \`Actual: \${(point.y * 100).toFixed(1)}%\`,
                                                \`Gap: \${gapText}\`,
                                                \`Samples: \${point.n || 0}\`
                                            ];
                                        }
                                        return context.dataset.label;
                                    }
                                }
                            },
                            legend: {
                                display: true,
                                labels: {
                                    color: '#888899',
                                    filter: (item) => item.text !== 'Perfect Calibration (y = x)'
                                }
                            }
                        }
                    });
                }
            }, 500);
        });
    </script>
</body>
</html>`;
        
        // Download the file
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `aggregate-stats-${new Date().toISOString().split('T')[0]}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export HTML: ' + error.message);
    }
}

// Image Export Function
async function exportToImage() {
    const container = document.getElementById('aggregateStatsContainer');
    if (!container) {
        alert('Stats container not found.');
        return;
    }
    
    try {
        // Remove all non-chart tooltips (individual stat tooltips)
        container.querySelectorAll('.stat-row-label .tooltip-icon, .summary-label .tooltip-icon').forEach(icon => {
            icon.remove();
        });
        
        // Add chart tooltips as visible text below chart titles
        // Find all chart sections by looking for h5 titles with tooltip icons
        const chartTitles = container.querySelectorAll('h5 .tooltip-icon');
        const addedTooltips = [];
        
        chartTitles.forEach(tooltipIcon => {
            const chartTitle = tooltipIcon.closest('h5');
            if (!chartTitle) return;
            
            // Find the chart wrapper (should be a sibling or nearby)
            const section = chartTitle.closest('div');
            if (!section) return;
            
            const chartWrapper = section.querySelector('.chart-wrapper');
            if (!chartWrapper) return;
            
            // Extract tooltip text from title attribute (tooltipIcon is already the icon element)
            if (tooltipIcon) {
                const tooltipText = tooltipIcon.getAttribute('title') || '';
                if (tooltipText) {
                    // Create visible tooltip text element below the chart title (before the chart wrapper)
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
                    chartTitle.parentNode.insertBefore(tooltipElement, chartWrapper);
                    addedTooltips.push(tooltipElement);
                }
            }
        });
        
        // Wait for rendering
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Use html2canvas to capture
        if (typeof html2canvas === 'undefined') {
            // Clean up added tooltips
            addedTooltips.forEach(el => el.remove());
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
            allowTaint: true
        });
        
        // Convert to blob and download
        canvas.toBlob(function(blob) {
            // Clean up added tooltips
            addedTooltips.forEach(el => el.remove());
            
            if (!blob) {
                alert('Failed to create image.');
                return;
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `aggregate-stats-${new Date().toISOString().split('T')[0]}.png`;
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

// Helper function to get chart rendering code for HTML export
function getChartRenderingCode() {
    // Extract the chart rendering code from the setTimeout block
    // This will be embedded in the exported HTML
    return `
        function createHistogram(data, label, color, bins = 30) {
            if (!data || data.length === 0) return null;
            const min = Math.min(...data);
            const max = Math.max(...data);
            const binWidth = (max - min) / bins;
            const histogram = new Array(bins).fill(0);
            const binLabels = [];
            for (let i = 0; i < bins; i++) {
                binLabels.push((min + (i + 0.5) * binWidth).toFixed(3));
            }
            data.forEach(value => {
                const binIndex = Math.min(Math.floor((value - min) / binWidth), bins - 1);
                histogram[binIndex]++;
            });
            return { labels: binLabels, data: histogram, label: label, color: color };
        }
        
        function createScatterPlot(data, xLabel, yLabel, xColor, yColor) {
            if (!data || data.length === 0) return null;
            return {
                x: data.map(d => d[xLabel]),
                y: data.map(d => d[yLabel]),
                xLabel: xLabel,
                yLabel: yLabel,
                xColor: xColor,
                yColor: yColor
            };
        }
        
        function renderChart(canvasId, chartType, chartData, options = {}) {
            const canvas = document.getElementById(canvasId);
            if (!canvas || !chartData) return null;
            const ctx = canvas.getContext('2d');
            const defaultOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#e8e8f0' } }
                },
                scales: {
                    x: { ticks: { color: '#888899' }, grid: { color: '#2a2a40' } },
                    y: { ticks: { color: '#888899' }, grid: { color: '#2a2a40' } }
                }
            };
            const config = { type: chartType, data: chartData, options: { ...defaultOptions, ...options } };
            return new Chart(ctx, config);
        }
        
        function renderAllCharts(stats) {
            // This will be populated with the actual chart rendering code
            // Charts are already rendered in the HTML, so this is mainly for re-rendering if needed
            console.log('Charts rendered in HTML export');
        }
    `;
}


