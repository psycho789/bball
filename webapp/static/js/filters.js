/**
 * Filter and sort management module.
 * 
 * Design Pattern: Observer Pattern for filter changes
 * Algorithm: Event-driven filter updates
 * Big O: O(1) for filter operations
 */

function setupFilters() {
    const sortBy = document.getElementById('sortBy');
    const sortOrder = document.getElementById('sortOrder');
    const hasKalshi = document.getElementById('hasKalshi');
    const teamFilter = document.getElementById('teamFilter');
    const dateFrom = document.getElementById('dateFrom');
    const dateTo = document.getElementById('dateTo');
    const clearFilters = document.getElementById('clearFilters');
    
    if (!sortBy || !sortOrder || !hasKalshi || !teamFilter || !dateFrom || !dateTo || !clearFilters) {
        return;
    }
    
    // Initialize filter values from state
    const filters = getFilters();
    sortBy.value = filters.sort_by || 'date';
    sortOrder.value = filters.sort_order || 'desc';
    hasKalshi.value = filters.has_kalshi === null ? '' : filters.has_kalshi.toString();
    teamFilter.value = filters.team_filter || '';
    dateFrom.value = filters.date_from || '';
    dateTo.value = filters.date_to || '';
    
    // Filter change handler
    function applyFilters() {
        const newFilters = {
            sort_by: sortBy.value,
            sort_order: sortOrder.value,
            has_kalshi: hasKalshi.value === '' ? null : hasKalshi.value === 'true',
            team_filter: teamFilter.value.trim() || null,
            date_from: dateFrom.value || null,
            date_to: dateTo.value || null,
        };
        
        setFilters(newFilters);
        initializeGamesList(); // Reload games with new filters
    }
    
    // Attach event listeners
    sortBy.addEventListener('change', applyFilters);
    sortOrder.addEventListener('change', applyFilters);
    hasKalshi.addEventListener('change', applyFilters);
    teamFilter.addEventListener('input', debounce(applyFilters, 500)); // Debounce text input
    dateFrom.addEventListener('change', applyFilters);
    dateTo.addEventListener('change', applyFilters);
    
    // Clear filters
    clearFilters.addEventListener('click', () => {
        sortBy.value = 'date';
        sortOrder.value = 'desc';
        hasKalshi.value = '';
        teamFilter.value = '';
        dateFrom.value = '';
        dateTo.value = '';
        applyFilters();
    });
}

// Simple debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

