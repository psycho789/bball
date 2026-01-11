/**
 * Utility functions.
 * 
 * Design Pattern: Utility Module Pattern
 * Algorithm: Simple helper functions
 * Big O: O(1) for most operations
 */

function secondsToGameClock(elapsed) {
    const totalSeconds = 2880;
    const remaining = totalSeconds - elapsed;
    
    const quarter = Math.min(4, Math.floor(elapsed / 720) + 1);
    const quarterElapsed = elapsed % 720;
    const quarterRemaining = 720 - quarterElapsed;
    
    const minutes = Math.floor(quarterRemaining / 60);
    const seconds = Math.floor(quarterRemaining % 60);
    
    return `Q${quarter} ${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function deduplicateTimeSeries(data) {
    return data
        .sort((a, b) => a.time - b.time)
        .reduce((acc, curr, idx, arr) => {
            if (idx === 0 || curr.time !== arr[idx - 1].time) {
                acc.push(curr);
            } else {
                // Replace previous point with same timestamp (keep latest value)
                acc[acc.length - 1] = curr;
            }
            return acc;
        }, []);
}

function filterValidDataPoints(data, timeField = 'time', valueField = 'value') {
    return data
        .filter(d => d != null && d[timeField] != null && d[valueField] != null && 
                     !isNaN(d[valueField]) && !isNaN(d[timeField]))
        .map(d => ({
            time: d[timeField],
            value: d[valueField],
        }));
}

