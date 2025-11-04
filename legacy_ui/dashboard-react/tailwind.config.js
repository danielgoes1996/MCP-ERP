/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#ecf2f9',
          100: '#d6e3f3',
          200: '#acc7e6',
          300: '#7fa7d4',
          400: '#4f85bf',
          500: '#11446e',
          600: '#0f3c61',
          700: '#0c314f',
          800: '#0a263d',
        },
        accent: {
          500: '#60b97b',
          600: '#3d8a5d',
        },
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
        },
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#3b82f6',
        audit: {
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          info: '#3b82f6',
        },
        coherence: {
          high: '#10b981',
          medium: '#f59e0b',
          low: '#ef4444',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
      },
      boxShadow: {
        'card-sm': '0 1px 2px rgba(0, 0, 0, 0.06)',
        'card-md': '0 4px 12px rgba(0, 0, 0, 0.08)',
        'card-lg': '0 10px 24px rgba(0, 0, 0, 0.12)',
        'audit-card': '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
        'spof-critical': '0 0 15px rgba(239, 68, 68, 0.3)',
      },
      backgroundImage: {
        'grad-brand-accent': 'linear-gradient(90deg, #11446e, #3d8a5d)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms')
  ],
}
