/**
 * Logging page module - real-time log display using WebSockets.
 * 
 * Design Pattern: Observer Pattern with WebSocket streaming
 * Algorithm: WebSocket connection with file monitoring on server side
 * Big O: O(1) for connection operations, O(n) for displaying log lines where n = number of lines
 */

let logWebSocket = null;
let isAutoRefreshEnabled = true;
let logLinesCount = 500;
let allLogLines = []; // Store all log lines for filtering
let activeFilters = new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']); // All levels active by default

/**
 * Initialize the logging page.
 */
function initializeLoggingPage() {
    console.log('Initializing logging page...');
    
    // Setup event listeners
    const refreshBtn = document.getElementById('refreshLogsBtn');
    const toggleBtn = document.getElementById('toggleAutoRefreshBtn');
    const clearBtn = document.getElementById('clearLogsDisplayBtn');
    const logLinesInput = document.getElementById('logLines');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            // Refresh by reconnecting WebSocket
            reconnectWebSocket();
        });
    }
    
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            toggleAutoRefresh();
        });
    }
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearLogsDisplay();
        });
    }
    
    if (logLinesInput) {
        logLinesInput.addEventListener('change', (e) => {
            logLinesCount = parseInt(e.target.value) || 500;
            // Reconnect to get new line count
            reconnectWebSocket();
        });
    }
    
    // Setup log level filter buttons
    setupLogLevelFilters();
    
    // Connect WebSocket
    connectWebSocket();
}

/**
 * Setup log level filter buttons.
 * 
 * Design Pattern: Event Delegation Pattern
 * Algorithm: O(1) for filter toggle, O(n) for re-rendering where n = number of log lines
 * Big O: O(n) for filtering and rendering
 */
function setupLogLevelFilters() {
    const filterButtons = document.querySelectorAll('.log-level-filter-btn');
    
    // Initialize button styles based on their data-active attribute
    filterButtons.forEach(button => {
        const isActive = button.getAttribute('data-active') === 'true';
        updateFilterButtonStyle(button, isActive);
    });
    
    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            const level = button.getAttribute('data-level');
            const isActive = button.getAttribute('data-active') === 'true';
            
            if (level === 'all') {
                // Toggle all filters
                const allActive = Array.from(filterButtons).slice(1).every(btn => btn.getAttribute('data-active') === 'true');
                const newState = !allActive;
                
                filterButtons.forEach(btn => {
                    if (btn.getAttribute('data-level') !== 'all') {
                        btn.setAttribute('data-active', newState.toString());
                        updateFilterButtonStyle(btn, newState);
                        const btnLevel = btn.getAttribute('data-level');
                        if (newState) {
                            activeFilters.add(btnLevel);
                        } else {
                            activeFilters.delete(btnLevel);
                        }
                    }
                });
                
                // Update "All" button style
                updateFilterButtonStyle(button, newState);
                button.setAttribute('data-active', newState.toString());
            } else {
                // Toggle individual filter
                const newState = !isActive;
                button.setAttribute('data-active', newState.toString());
                updateFilterButtonStyle(button, newState);
                
                if (newState) {
                    activeFilters.add(level);
                } else {
                    activeFilters.delete(level);
                }
                
                // Update "All" button state
                updateAllButtonState();
            }
            
            // Re-render filtered logs
            renderFilteredLogs();
        });
    });
}

/**
 * Update filter button style based on active state.
 */
function updateFilterButtonStyle(button, isActive) {
    if (isActive) {
        button.style.background = 'var(--accent-kalshi)';
        button.style.color = 'white';
        button.style.fontWeight = '500';
        button.style.opacity = '1';
    } else {
        button.style.background = 'var(--card-bg)';
        button.style.color = 'var(--text-primary)';
        button.style.fontWeight = 'normal';
        button.style.opacity = '0.5';
    }
}

/**
 * Update "All" button state based on individual filter states.
 */
function updateAllButtonState() {
    const allButton = document.querySelector('.log-level-filter-btn[data-level="all"]');
    const otherButtons = Array.from(document.querySelectorAll('.log-level-filter-btn')).slice(1);
    const allActive = otherButtons.every(btn => btn.getAttribute('data-active') === 'true');
    
    if (allButton) {
        allButton.setAttribute('data-active', allActive.toString());
        updateFilterButtonStyle(allButton, allActive);
    }
}

/**
 * Parse log level from a log line.
 * 
 * Log format: "2026-01-11 11:00:09 | DEBUG    | winprob_api | ..."
 * Returns the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) or null if not found.
 */
function parseLogLevel(line) {
    // Match log level pattern: " | LEVEL    |" or " | LEVEL |"
    const match = line.match(/\s+\|\s+(\w+)\s+\|/);
    if (match && match[1]) {
        const level = match[1].toUpperCase();
        // Validate it's a known log level
        if (['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].includes(level)) {
            return level;
        }
    }
    return null;
}

/**
 * Filter log lines based on active filters.
 */
function filterLogLines(lines) {
    if (activeFilters.size === 0) {
        return []; // No filters active, show nothing
    }
    
    return lines.filter(line => {
        const level = parseLogLevel(line);
        if (!level) {
            // If we can't parse the level, include it (might be a continuation line or non-standard format)
            return true;
        }
        return activeFilters.has(level);
    });
}

/**
 * Render filtered logs to the display.
 */
function renderFilteredLogs() {
    const logsContent = document.getElementById('logsContent');
    if (!logsContent) {
        return;
    }
    
    const filteredLines = filterLogLines(allLogLines);
    logsContent.textContent = filteredLines.join('\n');
    
    // Auto-scroll if enabled
    const autoScroll = document.getElementById('autoScroll');
    if (autoScroll && autoScroll.checked) {
        const container = document.getElementById('logsContainer');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
    
    // Update status with filter info
    const logStatus = document.getElementById('logStatus');
    if (logStatus) {
        const totalLines = allLogLines.length;
        const filteredCount = filteredLines.length;
        const timestamp = new Date().toLocaleTimeString();
        const filterInfo = activeFilters.size === 5 ? '' : ` | Filtered: ${filteredCount}/${totalLines}`;
        logStatus.textContent = `Connected | Lines: ${filteredCount}${filterInfo} | Updated: ${timestamp}`;
    }
}

/**
 * Add log lines to storage and update display.
 */
function addLogLines(content) {
    if (!content) {
        return;
    }
    
    // Split content into lines and add to storage
    const newLines = content.split('\n').filter(line => line.trim().length > 0);
    allLogLines.push(...newLines);
    
    // Keep only the last N lines (based on logLinesCount)
    if (allLogLines.length > logLinesCount) {
        allLogLines = allLogLines.slice(-logLinesCount);
    }
    
    // Re-render with filters applied
    renderFilteredLogs();
}

/**
 * Replace all log lines (for initial load).
 */
function replaceAllLogLines(content) {
    if (!content) {
        allLogLines = [];
        renderFilteredLogs();
        return;
    }
    
    // Split content into lines
    allLogLines = content.split('\n').filter(line => line.trim().length > 0);
    
    // Keep only the last N lines (based on logLinesCount)
    if (allLogLines.length > logLinesCount) {
        allLogLines = allLogLines.slice(-logLinesCount);
    }
    
    // Re-render with filters applied
    renderFilteredLogs();
}

/**
 * Connect to WebSocket for log streaming.
 */
function connectWebSocket() {
    if (logWebSocket && logWebSocket.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected');
        return;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/logs`;
    
    console.log(`Connecting to log WebSocket: ${url}`);
    
    const logsContent = document.getElementById('logsContent');
    const logStatus = document.getElementById('logStatus');
    
    if (logStatus) {
        logStatus.textContent = 'Connecting...';
    }
    
    try {
        logWebSocket = new WebSocket(url);
        
        logWebSocket.onopen = () => {
            console.log('Log WebSocket connected');
            if (logStatus) {
                logStatus.textContent = 'Connected | Streaming logs...';
                logStatus.style.color = '';
            }
        };
        
        logWebSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error, event.data);
            }
        };
        
        logWebSocket.onerror = (error) => {
            console.error('Log WebSocket error:', error);
            if (logStatus) {
                logStatus.textContent = 'Connection error';
                logStatus.style.color = 'var(--accent-away)';
            }
        };
        
        logWebSocket.onclose = (event) => {
            console.log('Log WebSocket closed:', event.code, event.reason);
            logWebSocket = null;
            
            if (logStatus) {
                logStatus.textContent = 'Disconnected';
                logStatus.style.color = 'var(--text-secondary)';
            }
            
            // Auto-reconnect if auto-refresh is enabled
            if (isAutoRefreshEnabled) {
                console.log('Auto-reconnecting in 2 seconds...');
                setTimeout(() => {
                    if (isAutoRefreshEnabled) {
                        connectWebSocket();
                    }
                }, 2000);
            }
        };
    } catch (error) {
        console.error('Error creating log WebSocket:', error);
        if (logStatus) {
            logStatus.textContent = `Error: ${error.message}`;
            logStatus.style.color = 'var(--accent-away)';
        }
    }
}

/**
 * Handle WebSocket messages.
 */
function handleWebSocketMessage(data) {
    const logsContent = document.getElementById('logsContent');
    const logStatus = document.getElementById('logStatus');
    
    if (!logsContent) {
        return;
    }
    
    switch (data.type) {
        case 'initial':
            // Replace entire content with initial log data
            if (data.content) {
                replaceAllLogLines(data.content);
            }
            
            // Update status
            if (logStatus) {
                const timestamp = new Date().toLocaleTimeString();
                const filteredCount = filterLogLines(allLogLines).length;
                const filterInfo = activeFilters.size === 5 ? '' : ` | Filtered: ${filteredCount}/${allLogLines.length}`;
                logStatus.textContent = `Connected | Lines: ${filteredCount}${filterInfo} | Updated: ${timestamp}`;
            }
            break;
            
        case 'update':
            // Append new content
            if (data.content) {
                addLogLines(data.content);
            }
            
            // Update status is handled by renderFilteredLogs()
            break;
            
        case 'error':
            console.error('Log WebSocket error:', data.message);
            if (logStatus) {
                logStatus.textContent = `Error: ${data.message}`;
                logStatus.style.color = 'var(--accent-away)';
            }
            break;
            
        case 'pong':
            // Connection health check response
            break;
            
        default:
            console.warn('Unknown WebSocket message type:', data.type);
    }
}

/**
 * Reconnect WebSocket.
 */
function reconnectWebSocket() {
    disconnectWebSocket();
    setTimeout(() => {
        connectWebSocket();
    }, 100);
}

/**
 * Disconnect WebSocket.
 */
function disconnectWebSocket() {
    if (logWebSocket) {
        logWebSocket.close();
        logWebSocket = null;
    }
}

/**
 * Toggle auto-refresh on/off.
 */
function toggleAutoRefresh() {
    isAutoRefreshEnabled = !isAutoRefreshEnabled;
    
    const icon = document.getElementById('autoRefreshIcon');
    const text = document.getElementById('autoRefreshText');
    
    if (isAutoRefreshEnabled) {
        // Reconnect if disconnected
        if (!logWebSocket || logWebSocket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
        if (icon) icon.textContent = '⏸️';
        if (text) text.textContent = 'Pause';
    } else {
        // Disconnect WebSocket
        disconnectWebSocket();
        if (icon) icon.textContent = '▶️';
        if (text) text.textContent = 'Resume';
    }
}

/**
 * Clear the logs display (does not delete the log file).
 */
function clearLogsDisplay() {
    allLogLines = [];
    const logsContent = document.getElementById('logsContent');
    if (logsContent) {
        logsContent.textContent = 'Logs display cleared. Reconnecting to reload...';
    }
    reconnectWebSocket();
}

/**
 * Cleanup when leaving the logging page.
 */
function cleanupLoggingPage() {
    disconnectWebSocket();
    isAutoRefreshEnabled = false;
}
