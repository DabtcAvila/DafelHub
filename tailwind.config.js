/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './docs/**/*.{html,js,ts,jsx,tsx,md}',
    './src/**/*.{html,js,ts,jsx,tsx,py}',
    './*.html',
    './assets/**/*.{html,js,ts,jsx,tsx}'
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // Colors - Using our design system tokens
      colors: {
        // Primary palette
        primary: {
          50: 'rgb(var(--color-primary-50))',
          100: 'rgb(var(--color-primary-100))',
          200: 'rgb(var(--color-primary-200))',
          300: 'rgb(var(--color-primary-300))',
          400: 'rgb(var(--color-primary-400))',
          500: 'rgb(var(--color-primary-500))',
          600: 'rgb(var(--color-primary-600))',
          700: 'rgb(var(--color-primary-700))',
          800: 'rgb(var(--color-primary-800))',
          900: 'rgb(var(--color-primary-900))',
          950: 'rgb(var(--color-primary-950))',
          DEFAULT: 'var(--primary)',
          foreground: 'var(--primary-foreground)'
        },
        // Secondary palette
        secondary: {
          50: 'rgb(var(--color-secondary-50))',
          100: 'rgb(var(--color-secondary-100))',
          200: 'rgb(var(--color-secondary-200))',
          300: 'rgb(var(--color-secondary-300))',
          400: 'rgb(var(--color-secondary-400))',
          500: 'rgb(var(--color-secondary-500))',
          600: 'rgb(var(--color-secondary-600))',
          700: 'rgb(var(--color-secondary-700))',
          800: 'rgb(var(--color-secondary-800))',
          900: 'rgb(var(--color-secondary-900))',
          950: 'rgb(var(--color-secondary-950))',
          DEFAULT: 'var(--secondary)',
          foreground: 'var(--secondary-foreground)'
        },
        // Accent palette
        accent: {
          50: 'rgb(var(--color-accent-50))',
          100: 'rgb(var(--color-accent-100))',
          200: 'rgb(var(--color-accent-200))',
          300: 'rgb(var(--color-accent-300))',
          400: 'rgb(var(--color-accent-400))',
          500: 'rgb(var(--color-accent-500))',
          600: 'rgb(var(--color-accent-600))',
          700: 'rgb(var(--color-accent-700))',
          800: 'rgb(var(--color-accent-800))',
          900: 'rgb(var(--color-accent-900))',
          950: 'rgb(var(--color-accent-950))',
          DEFAULT: 'var(--accent)',
          foreground: 'var(--accent-foreground)'
        },
        // Warning palette
        warning: {
          50: 'rgb(var(--color-warning-50))',
          100: 'rgb(var(--color-warning-100))',
          200: 'rgb(var(--color-warning-200))',
          300: 'rgb(var(--color-warning-300))',
          400: 'rgb(var(--color-warning-400))',
          500: 'rgb(var(--color-warning-500))',
          600: 'rgb(var(--color-warning-600))',
          700: 'rgb(var(--color-warning-700))',
          800: 'rgb(var(--color-warning-800))',
          900: 'rgb(var(--color-warning-900))',
          950: 'rgb(var(--color-warning-950))',
        },
        // Error palette
        error: {
          50: 'rgb(var(--color-error-50))',
          100: 'rgb(var(--color-error-100))',
          200: 'rgb(var(--color-error-200))',
          300: 'rgb(var(--color-error-300))',
          400: 'rgb(var(--color-error-400))',
          500: 'rgb(var(--color-error-500))',
          600: 'rgb(var(--color-error-600))',
          700: 'rgb(var(--color-error-700))',
          800: 'rgb(var(--color-error-800))',
          900: 'rgb(var(--color-error-900))',
          950: 'rgb(var(--color-error-950))',
        },
        // Neutral palette
        neutral: {
          50: 'rgb(var(--color-neutral-50))',
          100: 'rgb(var(--color-neutral-100))',
          200: 'rgb(var(--color-neutral-200))',
          300: 'rgb(var(--color-neutral-300))',
          400: 'rgb(var(--color-neutral-400))',
          500: 'rgb(var(--color-neutral-500))',
          600: 'rgb(var(--color-neutral-600))',
          700: 'rgb(var(--color-neutral-700))',
          800: 'rgb(var(--color-neutral-800))',
          900: 'rgb(var(--color-neutral-900))',
          950: 'rgb(var(--color-neutral-950))',
        },
        // Semantic colors
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        muted: {
          DEFAULT: 'var(--muted)',
          foreground: 'var(--muted-foreground)',
        },
        popover: {
          DEFAULT: 'var(--popover)',
          foreground: 'var(--popover-foreground)',
        },
        card: {
          DEFAULT: 'var(--card)',
          foreground: 'var(--card-foreground)',
        },
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',
        destructive: {
          DEFAULT: 'var(--destructive)',
          foreground: 'var(--destructive-foreground)',
        },
      },
      // Typography
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
        display: 'var(--font-display)',
      },
      fontSize: {
        xs: ['var(--text-xs)', { lineHeight: 'var(--leading-normal)' }],
        sm: ['var(--text-sm)', { lineHeight: 'var(--leading-normal)' }],
        base: ['var(--text-base)', { lineHeight: 'var(--leading-normal)' }],
        lg: ['var(--text-lg)', { lineHeight: 'var(--leading-normal)' }],
        xl: ['var(--text-xl)', { lineHeight: 'var(--leading-tight)' }],
        '2xl': ['var(--text-2xl)', { lineHeight: 'var(--leading-tight)' }],
        '3xl': ['var(--text-3xl)', { lineHeight: 'var(--leading-tight)' }],
        '4xl': ['var(--text-4xl)', { lineHeight: 'var(--leading-tight)' }],
        '5xl': ['var(--text-5xl)', { lineHeight: 'var(--leading-none)' }],
        '6xl': ['var(--text-6xl)', { lineHeight: 'var(--leading-none)' }],
        '7xl': ['var(--text-7xl)', { lineHeight: 'var(--leading-none)' }],
        '8xl': ['var(--text-8xl)', { lineHeight: 'var(--leading-none)' }],
        '9xl': ['var(--text-9xl)', { lineHeight: 'var(--leading-none)' }],
      },
      fontWeight: {
        thin: 'var(--font-weight-thin)',
        extralight: 'var(--font-weight-extralight)',
        light: 'var(--font-weight-light)',
        normal: 'var(--font-weight-normal)',
        medium: 'var(--font-weight-medium)',
        semibold: 'var(--font-weight-semibold)',
        bold: 'var(--font-weight-bold)',
        extrabold: 'var(--font-weight-extrabold)',
        black: 'var(--font-weight-black)',
      },
      lineHeight: {
        none: 'var(--leading-none)',
        tight: 'var(--leading-tight)',
        snug: 'var(--leading-snug)',
        normal: 'var(--leading-normal)',
        relaxed: 'var(--leading-relaxed)',
        loose: 'var(--leading-loose)',
      },
      letterSpacing: {
        tighter: 'var(--tracking-tighter)',
        tight: 'var(--tracking-tight)',
        normal: 'var(--tracking-normal)',
        wide: 'var(--tracking-wide)',
        wider: 'var(--tracking-wider)',
        widest: 'var(--tracking-widest)',
      },
      // Spacing
      spacing: {
        0: 'var(--space-0)',
        px: 'var(--space-px)',
        0.5: 'var(--space-0-5)',
        1: 'var(--space-1)',
        1.5: 'var(--space-1-5)',
        2: 'var(--space-2)',
        2.5: 'var(--space-2-5)',
        3: 'var(--space-3)',
        3.5: 'var(--space-3-5)',
        4: 'var(--space-4)',
        5: 'var(--space-5)',
        6: 'var(--space-6)',
        7: 'var(--space-7)',
        8: 'var(--space-8)',
        9: 'var(--space-9)',
        10: 'var(--space-10)',
        11: 'var(--space-11)',
        12: 'var(--space-12)',
        14: 'var(--space-14)',
        16: 'var(--space-16)',
        20: 'var(--space-20)',
        24: 'var(--space-24)',
        28: 'var(--space-28)',
        32: 'var(--space-32)',
        36: 'var(--space-36)',
        40: 'var(--space-40)',
        44: 'var(--space-44)',
        48: 'var(--space-48)',
        52: 'var(--space-52)',
        56: 'var(--space-56)',
        60: 'var(--space-60)',
        64: 'var(--space-64)',
        72: 'var(--space-72)',
        80: 'var(--space-80)',
        96: 'var(--space-96)',
      },
      // Border radius
      borderRadius: {
        none: 'var(--radius-none)',
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-base)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        '3xl': 'var(--radius-3xl)',
        full: 'var(--radius-full)',
      },
      // Box shadows
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-base)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        '2xl': 'var(--shadow-2xl)',
        inner: 'var(--shadow-inner)',
        none: 'none',
      },
      // Animation durations
      transitionDuration: {
        75: 'var(--duration-75)',
        100: 'var(--duration-100)',
        150: 'var(--duration-150)',
        200: 'var(--duration-200)',
        300: 'var(--duration-300)',
        500: 'var(--duration-500)',
        700: 'var(--duration-700)',
        1000: 'var(--duration-1000)',
      },
      // Animation timing functions
      transitionTimingFunction: {
        linear: 'var(--ease-linear)',
        in: 'var(--ease-in)',
        out: 'var(--ease-out)',
        'in-out': 'var(--ease-in-out)',
        sharp: 'var(--ease-sharp)',
        bounce: 'var(--ease-bounce)',
      },
      // Z-index
      zIndex: {
        0: 'var(--z-0)',
        10: 'var(--z-10)',
        20: 'var(--z-20)',
        30: 'var(--z-30)',
        40: 'var(--z-40)',
        50: 'var(--z-50)',
        auto: 'var(--z-auto)',
        dropdown: 'var(--z-dropdown)',
        sticky: 'var(--z-sticky)',
        fixed: 'var(--z-fixed)',
        'modal-backdrop': 'var(--z-modal-backdrop)',
        modal: 'var(--z-modal)',
        popover: 'var(--z-popover)',
        tooltip: 'var(--z-tooltip)',
        toast: 'var(--z-toast)',
        max: 'var(--z-max)',
      },
      // Breakpoints
      screens: {
        xs: 'var(--breakpoint-xs)',
        sm: 'var(--breakpoint-sm)',
        md: 'var(--breakpoint-md)',
        lg: 'var(--breakpoint-lg)',
        xl: 'var(--breakpoint-xl)',
        '2xl': 'var(--breakpoint-2xl)',
      },
      // Component-specific extensions
      height: {
        'button-sm': 'var(--button-height-sm)',
        'button-md': 'var(--button-height-md)',
        'button-lg': 'var(--button-height-lg)',
        'button-xl': 'var(--button-height-xl)',
        'input-sm': 'var(--input-height-sm)',
        'input-md': 'var(--input-height-md)',
        'input-lg': 'var(--input-height-lg)',
      },
      padding: {
        'card-sm': 'var(--card-padding-sm)',
        'card-md': 'var(--card-padding-md)',
        'card-lg': 'var(--card-padding-lg)',
      },
    },
  },
  plugins: [
    // Custom plugin for design system utilities
    function({ addUtilities, theme }) {
      addUtilities({
        // Typography utilities
        '.text-gradient': {
          'background': 'linear-gradient(135deg, var(--primary), var(--accent))',
          '-webkit-background-clip': 'text',
          '-webkit-text-fill-color': 'transparent',
          'background-clip': 'text',
        },
        '.text-gradient-primary': {
          'background': 'linear-gradient(135deg, var(--color-primary-500), var(--color-primary-700))',
          '-webkit-background-clip': 'text',
          '-webkit-text-fill-color': 'transparent',
          'background-clip': 'text',
        },
        '.text-gradient-accent': {
          'background': 'linear-gradient(135deg, var(--color-accent-500), var(--color-accent-700))',
          '-webkit-background-clip': 'text',
          '-webkit-text-fill-color': 'transparent',
          'background-clip': 'text',
        },
        // Glass morphism utilities
        '.glass': {
          'background': 'rgba(255, 255, 255, 0.1)',
          'backdrop-filter': 'blur(10px)',
          '-webkit-backdrop-filter': 'blur(10px)',
          'border': '1px solid rgba(255, 255, 255, 0.2)',
        },
        '.glass-dark': {
          'background': 'rgba(0, 0, 0, 0.1)',
          'backdrop-filter': 'blur(10px)',
          '-webkit-backdrop-filter': 'blur(10px)',
          'border': '1px solid rgba(255, 255, 255, 0.1)',
        },
        // Animation utilities
        '.animate-fade-in': {
          'animation': 'fade-in var(--duration-300) var(--ease-out)',
        },
        '.animate-slide-up': {
          'animation': 'slide-up var(--duration-500) var(--ease-out)',
        },
        '.animate-scale-in': {
          'animation': 'scale-in var(--duration-200) var(--ease-bounce)',
        },
      })
      
      // Add keyframes
      addUtilities({
        '@keyframes fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        '@keyframes slide-up': {
          '0%': { 
            opacity: '0',
            transform: 'translateY(20px)',
          },
          '100%': { 
            opacity: '1',
            transform: 'translateY(0)',
          },
        },
        '@keyframes scale-in': {
          '0%': { 
            opacity: '0',
            transform: 'scale(0.9)',
          },
          '100%': { 
            opacity: '1',
            transform: 'scale(1)',
          },
        },
      })
    },
  ],
}