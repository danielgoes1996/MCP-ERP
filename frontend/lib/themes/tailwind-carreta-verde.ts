/**
 * Tailwind CSS Theme Extension for Carreta Verde
 *
 * Import this in tailwind.config.ts to extend with Carreta Verde theme.
 *
 * Usage:
 *   import { carretaVerdeTailwind } from './lib/themes/tailwind-carreta-verde';
 *   // Then spread in theme.extend
 */

export const carretaVerdeTailwind = {
  colors: {
    // Primary - PANTONE 5605 C (Verde Bosque)
    // Base: #1E3728 - RGB(30, 55, 40)
    'cv-primary': {
      50: '#f2f5f3',
      100: '#e0e8e3',
      200: '#c1d1c7',
      300: '#96b3a1',
      400: '#6a9179',
      500: '#4a7259',
      600: '#375745',
      700: '#2d4639',
      800: '#1E3728',  // PANTONE 5605 C
      900: '#162920',
      950: '#0d1812',
    },
    // Secondary - PANTONE 7556 C (Mostaza Dorado)
    // Base: #B48C14 - RGB(180, 140, 20)
    'cv-secondary': {
      50: '#fdfaf0',
      100: '#faf3d9',
      200: '#f5e5b0',
      300: '#efd37d',
      400: '#e6bc42',
      500: '#B48C14',  // PANTONE 7556 C
      600: '#9a7610',
      700: '#7d5f0d',
      800: '#654c0f',
      900: '#533f10',
      950: '#2e220a',
    },
    // Neutrals - Warm
    'cv-neutral': {
      50: '#FDFCFA',
      100: '#F8F6F1',
      200: '#EDE9E0',
      300: '#DDD7CB',
      400: '#B8AFA0',
      500: '#8C8275',
      600: '#6B6358',
      700: '#4A453E',
      800: '#2E2A26',
      900: '#1A1816',
      950: '#0D0C0B',
    },
    // Accent - Honey amber
    'cv-honey': {
      light: '#fde68a',
      DEFAULT: '#f59e0b',
      dark: '#b45309',
    },
  },

  fontFamily: {
    'cv-display': ['"Fairprosper"', 'Georgia', 'serif'],
    'cv-body': ['"Galvji"', 'system-ui', '-apple-system', 'sans-serif'],
  },

  boxShadow: {
    'cv-product': '0 8px 30px rgba(0, 0, 0, 0.08)',
    'cv-product-hover': '0 16px 40px rgba(0, 0, 0, 0.12)',
    'cv-glow-primary': '0 0 20px rgba(30, 55, 40, 0.3)',      // PANTONE 5605 C
    'cv-glow-secondary': '0 0 20px rgba(180, 140, 20, 0.3)',  // PANTONE 7556 C
  },

  borderRadius: {
    'cv-sm': '0.5rem',
    'cv-md': '0.75rem',
    'cv-lg': '1rem',
    'cv-xl': '1.5rem',
  },

  backgroundImage: {
    'cv-gradient-hero': 'linear-gradient(135deg, #F8F6F1 0%, #FDFCFA 50%, #fdfaf0 100%)',
    'cv-gradient-cta': 'linear-gradient(135deg, #2d4639 0%, #1E3728 100%)',   // Verde bosque
    'cv-gradient-honey': 'linear-gradient(135deg, #e6bc42 0%, #B48C14 100%)', // Mostaza dorado
  },
};

// CSS Variables for dynamic theming
// PANTONE 5605 C (Verde Bosque) + PANTONE 7556 C (Mostaza Dorado)
export const carretaVerdeCSSVars = `
  --cv-primary: #1E3728;
  --cv-primary-dark: #162920;
  --cv-secondary: #B48C14;
  --cv-secondary-dark: #7d5f0d;
  --cv-background: #FDFCFA;
  --cv-surface: #FFFFFF;
  --cv-text: #2E2A26;
  --cv-text-muted: #6B6358;
`;
