/**
 * Shared utilities for HTML export functionality.
 * 
 * Design Pattern: Utility Module Pattern
 * Algorithm: HTML string generation
 * Big O: O(1) - constant time string concatenation
 */

/**
 * Generate shared navigation header for exported HTML pages.
 * @param {string} currentPage - Current page identifier ('aggregate-stats', 'model-comparison', etc.)
 * @returns {string} HTML string for the navigation header
 */
function generateExportHeader(currentPage) {
    const pages = [
        { id: 'index', name: 'Home', url: 'index.html', icon: '🏠' },
        { id: 'aggregate-stats', name: 'Aggregate Stats', url: 'aggregate-stats.html', icon: '📈' },
        { id: 'model-comparison', name: 'Model Comparison', url: 'model-comparison.html', icon: '📊' }
    ];
    
    let navLinks = '';
    pages.forEach(page => {
        const isActive = page.id === currentPage;
        const activeClass = isActive ? 'active' : '';
        navLinks += `
            <a href="${page.url}" class="export-nav-link ${activeClass}">
                <span class="export-nav-icon">${page.icon}</span>
                <span class="export-nav-text">${page.name}</span>
            </a>
        `;
    });
    
    return `
        <header class="export-header">
            <div class="export-header-brand">
                <a href="index.html" class="export-brand-link">
                    <h1 class="export-app-title">Win Probability</h1>
                </a>
                <p class="export-app-subtitle">NBA game probabilities from ESPN and Kalshi</p>
            </div>
            <nav class="export-header-nav">
                ${navLinks}
            </nav>
        </header>
    `;
}

/**
 * Generate CSS for the export header.
 * @returns {string} CSS string for the export header
 */
function generateExportHeaderCSS() {
    return `
        .export-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 32px;
            padding: 20px 0;
            border-bottom: 1px solid var(--border-color);
            gap: 32px;
            flex-wrap: wrap;
        }

        .export-header-brand {
            flex-shrink: 0;
        }

        .export-brand-link {
            text-decoration: none;
            display: block;
        }

        .export-brand-link:hover .export-app-title {
            opacity: 0.8;
            transition: opacity 0.2s ease;
        }

        .export-app-title {
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-home), var(--accent-highlight));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            cursor: pointer;
            transition: opacity 0.2s ease;
        }

        .export-app-subtitle {
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 6px;
            margin-bottom: 0;
        }

        .export-header-nav {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        .export-nav-link {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            text-decoration: none;
            color: var(--text-primary);
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .export-nav-link:hover {
            background: var(--bg-secondary);
            border-color: var(--accent-highlight);
            color: var(--accent-highlight);
            transform: translateY(-2px);
        }

        .export-nav-link.active {
            background: rgba(124, 58, 237, 0.1);
            border-color: var(--accent-highlight);
            color: var(--accent-highlight);
        }

        .export-nav-icon {
            font-size: 1rem;
        }

        .export-nav-text {
            font-size: 0.875rem;
        }

        @media (max-width: 768px) {
            .export-header {
                flex-direction: column;
                align-items: flex-start;
            }

            .export-header-nav {
                width: 100%;
            }

            .export-nav-link {
                flex: 1;
                justify-content: center;
            }
        }
    `;
}

