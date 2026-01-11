/**
 * Filter and sort management module.
 * 
 * Design Pattern: Observer Pattern for filter changes
 * Algorithm: Event-driven filter updates
 * Big O: O(1) for filter operations
 */

async function loadTeamOptions() {
    const teamFilter = document.getElementById('teamFilter');
    if (!teamFilter) return;
    
    try {
        const response = await fetch('/api/games/teams');
        if (!response.ok) throw new Error('Failed to fetch teams');
        const data = await response.json();
        
        // Store current value before clearing
        const currentValue = teamFilter.value;
        
        // Clear existing options except "All Teams"
        teamFilter.innerHTML = '<option value="">All Teams</option>';
        
        // Add team options
        data.teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team;
            option.textContent = team;
            teamFilter.appendChild(option);
        });
        
        // Restore previous value if it exists
        if (currentValue) {
            teamFilter.value = currentValue;
        }
        
        return true;
    } catch (error) {
        console.error('Error loading team options:', error);
        // Fallback to empty dropdown with just "All Teams"
        return false;
    }
}

function setupFilters() {
    const sortBy = document.getElementById('sortBy');
    const sortOrder = document.getElementById('sortOrder');
    const teamFilter = document.getElementById('teamFilter');
    const dateFrom = document.getElementById('dateFrom');
    const dateTo = document.getElementById('dateTo');
    const clearFilters = document.getElementById('clearFilters');
    
    if (!sortBy || !sortOrder || !teamFilter || !dateFrom || !dateTo || !clearFilters) {
        return;
    }
    
    // Initialize filter values from state
    const filters = getFilters();
    sortBy.value = filters.sort_by || 'date';
    sortOrder.value = filters.sort_order || 'desc';
    dateFrom.value = filters.date_from || '';
    dateTo.value = filters.date_to || '';
    
    // Load team options and set value after loading
    loadTeamOptions().then(() => {
        teamFilter.value = filters.team_filter || '';
    });
    
    // Filter change handler
    function applyFilters() {
        const newFilters = {
            sort_by: sortBy.value,
            sort_order: sortOrder.value,
            has_kalshi: null, // Always null - filter removed
            team_filter: teamFilter.value || null,
            date_from: dateFrom.value || null,
            date_to: dateTo.value || null,
        };
        
        setFilters(newFilters);
        initializeGamesList(); // Reload games with new filters
    }
    
    // Attach event listeners
    sortBy.addEventListener('change', applyFilters);
    sortOrder.addEventListener('change', applyFilters);
    teamFilter.addEventListener('change', applyFilters);
    dateFrom.addEventListener('change', applyFilters);
    dateTo.addEventListener('change', applyFilters);
    
    // Clear filters
    clearFilters.addEventListener('click', () => {
        sortBy.value = 'date';
        sortOrder.value = 'desc';
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

