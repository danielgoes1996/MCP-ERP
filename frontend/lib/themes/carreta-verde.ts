/**
 * CARRETA VERDE - Design System
 *
 * Premium organic honey brand theme.
 *
 * Typography: Fairprosper (display) + Galvji (body)
 * Colors: Military Green + Mustard Yellow
 *
 * TODO: Update hex values when client provides exact brand colors
 */

export const carretaVerdeTheme = {
  // ==========================================================================
  // BRAND INFO
  // ==========================================================================
  brand: {
    name: 'Carreta Verde',
    tagline: 'Miel 100% Pura y Natural',
    description: 'Miel artesanal de la más alta calidad',
  },

  // ==========================================================================
  // COLOR PALETTE
  // ==========================================================================
  colors: {
    // Primary - Verde Militar Oscuro
    // TODO: Replace with exact brand color
    primary: {
      50: '#f4f6f4',
      100: '#e4e9e4',
      200: '#c9d3c9',
      300: '#a3b3a3',
      400: '#768c76',
      500: '#556B2F',  // Main military green (adjust)
      600: '#4a5d29',
      700: '#3d4a22',
      800: '#333d1d',
      900: '#2a3218',
      950: '#151a0c',
    },

    // Secondary - Amarillo Mostaza / Dorado Miel
    // TODO: Replace with exact brand color
    secondary: {
      50: '#fefcf3',
      100: '#fdf8e1',
      200: '#faefc3',
      300: '#f6e19a',
      400: '#f0cd6a',
      500: '#D4A017',  // Main mustard (adjust)
      600: '#c18f0f',
      700: '#a17311',
      800: '#845c15',
      900: '#6d4b16',
      950: '#3e2809',
    },

    // Accent - Tono miel ámbar
    accent: {
      50: '#fffbeb',
      100: '#fef3c7',
      200: '#fde68a',
      300: '#fcd34d',
      400: '#fbbf24',
      500: '#f59e0b',
      600: '#d97706',
      700: '#b45309',
      800: '#92400e',
      900: '#78350f',
    },

    // Neutrals - Tonos cálidos tierra
    neutral: {
      50: '#FDFCFA',   // Cream white
      100: '#F8F6F1',  // Warm white
      200: '#EDE9E0',  // Light cream
      300: '#DDD7CB',  // Warm gray
      400: '#B8AFA0',  // Medium warm
      500: '#8C8275',  // Neutral warm
      600: '#6B6358',  // Dark warm
      700: '#4A453E',  // Brown gray
      800: '#2E2A26',  // Dark brown
      900: '#1A1816',  // Almost black
      950: '#0D0C0B',  // Pure dark
    },

    // Semantic colors
    success: {
      light: '#86efac',
      main: '#22c55e',
      dark: '#15803d',
    },
    error: {
      light: '#fca5a5',
      main: '#ef4444',
      dark: '#b91c1c',
    },
    warning: {
      light: '#fde68a',
      main: '#f59e0b',
      dark: '#b45309',
    },
    info: {
      light: '#93c5fd',
      main: '#3b82f6',
      dark: '#1d4ed8',
    },
  },

  // ==========================================================================
  // TYPOGRAPHY
  // ==========================================================================
  typography: {
    // Font families
    fonts: {
      display: '"Fairprosper", Georgia, serif',      // Títulos, precios
      body: '"Galvji", system-ui, sans-serif',       // Cuerpo, UI
      mono: 'ui-monospace, monospace',               // Código
    },

    // Font sizes with line heights
    sizes: {
      xs: { size: '0.75rem', lineHeight: '1rem' },      // 12px
      sm: { size: '0.875rem', lineHeight: '1.25rem' },  // 14px
      base: { size: '1rem', lineHeight: '1.5rem' },     // 16px
      lg: { size: '1.125rem', lineHeight: '1.75rem' },  // 18px
      xl: { size: '1.25rem', lineHeight: '1.75rem' },   // 20px
      '2xl': { size: '1.5rem', lineHeight: '2rem' },    // 24px
      '3xl': { size: '1.875rem', lineHeight: '2.25rem' }, // 30px
      '4xl': { size: '2.25rem', lineHeight: '2.5rem' }, // 36px
      '5xl': { size: '3rem', lineHeight: '1' },         // 48px
      '6xl': { size: '3.75rem', lineHeight: '1' },      // 60px
    },

    // Font weights
    weights: {
      light: 300,
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  // ==========================================================================
  // SPACING & LAYOUT
  // ==========================================================================
  spacing: {
    container: {
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1440px',
    },
    section: {
      sm: '2rem',    // 32px
      md: '4rem',    // 64px
      lg: '6rem',    // 96px
      xl: '8rem',    // 128px
    },
  },

  // ==========================================================================
  // BORDER RADIUS
  // ==========================================================================
  radius: {
    none: '0',
    sm: '0.25rem',    // 4px
    md: '0.5rem',     // 8px
    lg: '0.75rem',    // 12px
    xl: '1rem',       // 16px
    '2xl': '1.5rem',  // 24px
    full: '9999px',
  },

  // ==========================================================================
  // SHADOWS
  // ==========================================================================
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
    // Brand glow effects
    'glow-primary': '0 0 20px rgba(85, 107, 47, 0.3)',
    'glow-secondary': '0 0 20px rgba(212, 160, 23, 0.3)',
    'product': '0 8px 30px rgba(0, 0, 0, 0.08)',
    'product-hover': '0 16px 40px rgba(0, 0, 0, 0.12)',
  },

  // ==========================================================================
  // TRANSITIONS
  // ==========================================================================
  transitions: {
    fast: '150ms ease',
    normal: '200ms ease',
    slow: '300ms ease',
    spring: '300ms cubic-bezier(0.175, 0.885, 0.32, 1.275)',
  },

  // ==========================================================================
  // Z-INDEX
  // ==========================================================================
  zIndex: {
    dropdown: 1000,
    sticky: 1100,
    modal: 1200,
    popover: 1300,
    toast: 1400,
  },
} as const;

// Type exports
export type CarretaVerdeTheme = typeof carretaVerdeTheme;
export type ThemeColors = typeof carretaVerdeTheme.colors;
export type ThemeTypography = typeof carretaVerdeTheme.typography;
