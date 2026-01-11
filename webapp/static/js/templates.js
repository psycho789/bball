/**
 * Template loader module.
 * 
 * Design Pattern: Template Method Pattern
 * Algorithm: Async template loading and DOM insertion
 * Big O: O(1) per template load (single fetch + DOM insertion)
 */

const templateCache = new Map();

/**
 * Load a template from the templates directory.
 * @param {string} templateName - Name of the template file (without .html extension)
 * @returns {Promise<string>} - HTML content of the template
 */
async function loadTemplate(templateName) {
    // Check cache first
    if (templateCache.has(templateName)) {
        console.log(`Template ${templateName} loaded from cache`);
        return templateCache.get(templateName);
    }
    
    try {
        const url = `/static/templates/${templateName}.html`;
        console.log(`Loading template from: ${url}`);
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to load template: ${templateName} (${response.status} ${response.statusText})`);
        }
        const html = await response.text();
        if (!html || html.trim().length === 0) {
            throw new Error(`Template ${templateName} is empty`);
        }
        console.log(`Template ${templateName} loaded successfully (${html.length} chars)`);
        templateCache.set(templateName, html);
        return html;
    } catch (error) {
        console.error(`Error loading template ${templateName}:`, error);
        throw error;
    }
}

/**
 * Render a template into a container element.
 * @param {string} templateName - Name of the template file
 * @param {HTMLElement|string} container - Container element or selector
 * @returns {Promise<HTMLElement>} - The container element
 */
async function renderTemplate(templateName, container) {
    const html = await loadTemplate(templateName);
    const containerEl = typeof container === 'string' 
        ? document.querySelector(container) 
        : container;
    
    if (!containerEl) {
        throw new Error(`Container not found for template: ${templateName}`);
    }
    
    containerEl.innerHTML = html;
    console.log(`Template ${templateName} rendered into container`, {
        container: containerEl,
        htmlLength: html.length,
        hasContent: html.trim().length > 0
    });
    return containerEl;
}

/**
 * Clear the template cache (useful for development/hot reloading).
 */
function clearTemplateCache() {
    templateCache.clear();
}

