/**
 * 🎨 MCP-Server Unified Theme Manager
 * Handles dark/light modes, corporate themes, and UI consistency
 */

class ThemeManager {
    constructor() {
        this.themes = {
            light: {
                primary: '#667eea',
                secondary: '#764ba2',
                background: '#ffffff',
                surface: '#f8f9fa',
                text: '#2d3436',
                textSecondary: '#636e72',
                success: '#00b894',
                warning: '#fdcb6e',
                error: '#e17055',
                border: '#e9ecef'
            },
            dark: {
                primary: '#667eea',
                secondary: '#764ba2',
                background: '#1a1a1a',
                surface: '#2d2d2d',
                text: '#ffffff',
                textSecondary: '#b2bec3',
                success: '#00b894',
                warning: '#fdcb6e',
                error: '#e17055',
                border: '#404040'
            },
            corporate: {
                primary: '#2d3436',
                secondary: '#636e72',
                background: '#ffffff',
                surface: '#f8f9fa',
                text: '#2d3436',
                textSecondary: '#636e72',
                success: '#00b894',
                warning: '#f39c12',
                error: '#e74c3c',
                border: '#ddd'
            }
        };

        this.currentTheme = this.getStoredTheme() || 'light';
        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);
        this.setupEventListeners();
        this.injectThemeToggle();
    }

    applyTheme(themeName) {
        const theme = this.themes[themeName];
        if (!theme) return;

        const root = document.documentElement;

        // Apply CSS custom properties
        Object.entries(theme).forEach(([key, value]) => {
            root.style.setProperty(`--color-${key}`, value);
        });

        // Update body classes
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        document.body.classList.add(`theme-${themeName}`);

        // Store preference
        localStorage.setItem('mcp-theme', themeName);
        this.currentTheme = themeName;

        // Dispatch theme change event
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: themeName, colors: theme }
        }));
    }

    getStoredTheme() {
        return localStorage.getItem('mcp-theme');
    }

    toggleTheme() {
        const themes = Object.keys(this.themes);
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % themes.length;
        this.applyTheme(themes[nextIndex]);
    }

    setTheme(themeName) {
        if (this.themes[themeName]) {
            this.applyTheme(themeName);
        }
    }

    setupEventListeners() {
        // Listen for system preference changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            if (!this.getStoredTheme()) {
                this.applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    injectThemeToggle() {
        // Create theme toggle button
        const toggle = document.createElement('button');
        toggle.innerHTML = '🎨';
        toggle.className = 'theme-toggle';
        toggle.title = 'Toggle Theme';
        toggle.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            padding: 10px;
            border: none;
            border-radius: 50%;
            background: var(--color-primary);
            color: white;
            cursor: pointer;
            font-size: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        `;

        toggle.addEventListener('click', () => this.toggleTheme());
        toggle.addEventListener('mouseenter', () => {
            toggle.style.transform = 'scale(1.1)';
        });
        toggle.addEventListener('mouseleave', () => {
            toggle.style.transform = 'scale(1)';
        });

        document.body.appendChild(toggle);
    }

    // Utility methods for components
    getColor(colorName) {
        return this.themes[this.currentTheme][colorName];
    }

    isDark() {
        return this.currentTheme === 'dark';
    }

    // Component styling helpers
    getButtonStyles(variant = 'primary') {
        const base = {
            padding: '8px 16px',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: '500',
            transition: 'all 0.2s ease'
        };

        const variants = {
            primary: {
                background: this.getColor('primary'),
                color: 'white'
            },
            secondary: {
                background: this.getColor('surface'),
                color: this.getColor('text'),
                border: `1px solid ${this.getColor('border')}`
            },
            success: {
                background: this.getColor('success'),
                color: 'white'
            },
            warning: {
                background: this.getColor('warning'),
                color: 'white'
            },
            error: {
                background: this.getColor('error'),
                color: 'white'
            }
        };

        return { ...base, ...variants[variant] };
    }

    getCardStyles() {
        return {
            background: this.getColor('surface'),
            color: this.getColor('text'),
            border: `1px solid ${this.getColor('border')}`,
            borderRadius: '8px',
            padding: '16px',
            boxShadow: this.isDark()
                ? '0 2px 8px rgba(0,0,0,0.3)'
                : '0 2px 8px rgba(0,0,0,0.1)'
        };
    }
}

// Initialize theme manager
window.themeManager = new ThemeManager();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}