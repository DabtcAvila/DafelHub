/**
 * DAFEL TECHNOLOGIES - THEME MANAGER
 * Runtime theming and design system utilities
 */

class DafelThemeManager {
  constructor() {
    this.themes = {
      light: {
        background: 'var(--color-neutral-50)',
        foreground: 'var(--color-neutral-950)',
        muted: 'var(--color-neutral-100)',
        'muted-foreground': 'var(--color-neutral-500)',
        popover: 'var(--color-neutral-50)',
        'popover-foreground': 'var(--color-neutral-950)',
        card: 'var(--color-neutral-50)',
        'card-foreground': 'var(--color-neutral-950)',
        border: 'var(--color-neutral-200)',
        input: 'var(--color-neutral-200)',
        primary: 'var(--color-primary-600)',
        'primary-foreground': 'var(--color-neutral-50)',
        secondary: 'var(--color-secondary-100)',
        'secondary-foreground': 'var(--color-secondary-900)',
        accent: 'var(--color-accent-500)',
        'accent-foreground': 'var(--color-neutral-50)',
        destructive: 'var(--color-error-600)',
        'destructive-foreground': 'var(--color-neutral-50)',
        ring: 'var(--color-primary-600)',
      },
      dark: {
        background: 'var(--color-neutral-950)',
        foreground: 'var(--color-neutral-50)',
        muted: 'var(--color-neutral-900)',
        'muted-foreground': 'var(--color-neutral-400)',
        popover: 'var(--color-neutral-950)',
        'popover-foreground': 'var(--color-neutral-50)',
        card: 'var(--color-neutral-950)',
        'card-foreground': 'var(--color-neutral-50)',
        border: 'var(--color-neutral-800)',
        input: 'var(--color-neutral-800)',
        primary: 'var(--color-primary-500)',
        'primary-foreground': 'var(--color-neutral-950)',
        secondary: 'var(--color-secondary-800)',
        'secondary-foreground': 'var(--color-secondary-50)',
        accent: 'var(--color-accent-500)',
        'accent-foreground': 'var(--color-neutral-950)',
        destructive: 'var(--color-error-500)',
        'destructive-foreground': 'var(--color-neutral-50)',
        ring: 'var(--color-primary-500)',
      }
    };
    
    this.customThemes = new Map();
    this.observers = new Set();
    this.currentTheme = this.getSystemTheme();
    
    this.init();
  }
  
  /**
   * Initialize the theme manager
   */
  init() {
    // Check for saved theme preference
    const savedTheme = this.getSavedTheme();
    if (savedTheme) {
      this.setTheme(savedTheme);
    } else {
      this.setTheme(this.getSystemTheme());
    }
    
    // Listen for system theme changes
    this.setupSystemThemeListener();
    
    // Setup keyboard shortcuts
    this.setupKeyboardShortcuts();
  }
  
  /**
   * Get system theme preference
   */
  getSystemTheme() {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  
  /**
   * Get saved theme from localStorage
   */
  getSavedTheme() {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('dafel-theme');
  }
  
  /**
   * Save theme to localStorage
   */
  saveTheme(theme) {
    if (typeof window === 'undefined') return;
    localStorage.setItem('dafel-theme', theme);
  }
  
  /**
   * Set the current theme
   */
  setTheme(themeName) {
    if (!this.isValidTheme(themeName)) {
      console.warn(`Invalid theme: ${themeName}`);
      return;
    }
    
    const root = document.documentElement;
    
    // Remove existing theme classes
    root.classList.remove('light', 'dark');
    
    // Add new theme class
    root.classList.add(themeName);
    
    // Apply theme variables if custom theme
    if (this.customThemes.has(themeName)) {
      this.applyCustomTheme(themeName);
    }
    
    this.currentTheme = themeName;
    this.saveTheme(themeName);
    this.notifyObservers(themeName);
  }
  
  /**
   * Check if theme is valid
   */
  isValidTheme(themeName) {
    return this.themes.hasOwnProperty(themeName) || this.customThemes.has(themeName);
  }
  
  /**
   * Toggle between light and dark themes
   */
  toggleTheme() {
    const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
    this.setTheme(newTheme);
  }
  
  /**
   * Get current theme
   */
  getCurrentTheme() {
    return this.currentTheme;
  }
  
  /**
   * Create a custom theme
   */
  createCustomTheme(name, themeVariables) {
    this.customThemes.set(name, themeVariables);
  }
  
  /**
   * Apply custom theme variables
   */
  applyCustomTheme(themeName) {
    const theme = this.customThemes.get(themeName);
    if (!theme) return;
    
    const root = document.documentElement;
    Object.entries(theme).forEach(([key, value]) => {
      root.style.setProperty(`--${key}`, value);
    });
  }
  
  /**
   * Get theme colors for a specific theme
   */
  getThemeColors(themeName = null) {
    const theme = themeName || this.currentTheme;
    return this.themes[theme] || this.customThemes.get(theme) || {};
  }
  
  /**
   * Setup system theme change listener
   */
  setupSystemThemeListener() {
    if (typeof window === 'undefined') return;
    
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', (e) => {
      // Only change if no manual theme is saved
      if (!this.getSavedTheme()) {
        const systemTheme = e.matches ? 'dark' : 'light';
        this.setTheme(systemTheme);
      }
    });
  }
  
  /**
   * Setup keyboard shortcuts for theme switching
   */
  setupKeyboardShortcuts() {
    if (typeof window === 'undefined') return;
    
    document.addEventListener('keydown', (e) => {
      // Ctrl/Cmd + Shift + T to toggle theme
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        this.toggleTheme();
      }
    });
  }
  
  /**
   * Add theme change observer
   */
  addObserver(callback) {
    this.observers.add(callback);
  }
  
  /**
   * Remove theme change observer
   */
  removeObserver(callback) {
    this.observers.delete(callback);
  }
  
  /**
   * Notify all observers of theme change
   */
  notifyObservers(theme) {
    this.observers.forEach(callback => {
      try {
        callback(theme);
      } catch (error) {
        console.error('Theme observer error:', error);
      }
    });
  }
  
  /**
   * Generate CSS custom properties for a theme
   */
  generateThemeCSS(themeName) {
    const theme = this.getThemeColors(themeName);
    const cssRules = Object.entries(theme)
      .map(([key, value]) => `  --${key}: ${value};`)
      .join('\n');
    
    return `.${themeName} {\n${cssRules}\n}`;
  }
  
  /**
   * Export theme configuration
   */
  exportTheme(themeName = null) {
    const theme = themeName || this.currentTheme;
    return {
      name: theme,
      variables: this.getThemeColors(theme),
      css: this.generateThemeCSS(theme)
    };
  }
  
  /**
   * Import theme configuration
   */
  importTheme(themeConfig) {
    if (!themeConfig.name || !themeConfig.variables) {
      throw new Error('Invalid theme configuration');
    }
    
    this.createCustomTheme(themeConfig.name, themeConfig.variables);
  }
  
  /**
   * Get theme preference for prefers-color-scheme
   */
  static getSystemPreference() {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  
  /**
   * Create a theme toggle component
   */
  createThemeToggle(options = {}) {
    const {
      className = 'theme-toggle',
      lightIcon = '☀️',
      darkIcon = '🌙',
      position = 'fixed',
      top = '1rem',
      right = '1rem'
    } = options;
    
    const toggle = document.createElement('button');
    toggle.className = `btn btn-secondary ${className}`;
    toggle.style.position = position;
    toggle.style.top = top;
    toggle.style.right = right;
    toggle.style.zIndex = 'var(--z-fixed)';
    toggle.style.width = '2.5rem';
    toggle.style.height = '2.5rem';
    toggle.style.padding = '0';
    toggle.setAttribute('aria-label', 'Toggle theme');
    
    const updateIcon = () => {
      toggle.textContent = this.currentTheme === 'dark' ? lightIcon : darkIcon;
    };
    
    updateIcon();
    
    toggle.addEventListener('click', () => {
      this.toggleTheme();
    });
    
    this.addObserver(() => {
      updateIcon();
    });
    
    return toggle;
  }
  
  /**
   * Initialize with default configuration
   */
  static init(options = {}) {
    const instance = new DafelThemeManager();
    
    // Add theme toggle if requested
    if (options.addToggle) {
      document.addEventListener('DOMContentLoaded', () => {
        const toggle = instance.createThemeToggle(options.toggleOptions);
        document.body.appendChild(toggle);
      });
    }
    
    return instance;
  }
}

// Design System Utilities
class DafelDesignUtils {
  /**
   * Get CSS custom property value
   */
  static getCSSVar(property, element = document.documentElement) {
    return getComputedStyle(element).getPropertyValue(`--${property}`).trim();
  }
  
  /**
   * Set CSS custom property
   */
  static setCSSVar(property, value, element = document.documentElement) {
    element.style.setProperty(`--${property}`, value);
  }
  
  /**
   * Create a color palette from a base color
   */
  static generateColorPalette(baseColor, steps = 10) {
    // This is a simplified version - in production you'd use a proper color manipulation library
    const palette = {};
    const baseStep = 500;
    
    for (let i = 0; i < steps; i++) {
      const step = (i + 1) * 100;
      const lightness = step < baseStep 
        ? 95 - (step / baseStep) * 45  // Lighter shades
        : 50 - ((step - baseStep) / (1000 - baseStep)) * 45; // Darker shades
      
      palette[step] = `hsl(${this.getHue(baseColor)}, ${this.getSaturation(baseColor)}%, ${lightness}%)`;
    }
    
    return palette;
  }
  
  /**
   * Get hue from color (simplified)
   */
  static getHue(color) {
    // This is a placeholder - implement proper color parsing
    return 220; // Default blue hue
  }
  
  /**
   * Get saturation from color (simplified)
   */
  static getSaturation(color) {
    // This is a placeholder - implement proper color parsing
    return 70; // Default saturation
  }
  
  /**
   * Create a responsive breakpoint helper
   */
  static createBreakpointHelper() {
    const breakpoints = {
      xs: parseInt(this.getCSSVar('breakpoint-xs')),
      sm: parseInt(this.getCSSVar('breakpoint-sm')),
      md: parseInt(this.getCSSVar('breakpoint-md')),
      lg: parseInt(this.getCSSVar('breakpoint-lg')),
      xl: parseInt(this.getCSSVar('breakpoint-xl')),
      '2xl': parseInt(this.getCSSVar('breakpoint-2xl'))
    };
    
    return {
      isAbove: (breakpoint) => window.innerWidth >= breakpoints[breakpoint],
      isBelow: (breakpoint) => window.innerWidth < breakpoints[breakpoint],
      current: () => {
        const width = window.innerWidth;
        if (width >= breakpoints['2xl']) return '2xl';
        if (width >= breakpoints.xl) return 'xl';
        if (width >= breakpoints.lg) return 'lg';
        if (width >= breakpoints.md) return 'md';
        if (width >= breakpoints.sm) return 'sm';
        return 'xs';
      }
    };
  }
  
  /**
   * Add animation classes with proper cleanup
   */
  static animate(element, animationClass, options = {}) {
    const { duration, cleanup = true } = options;
    
    element.classList.add(animationClass);
    
    const handleAnimationEnd = () => {
      if (cleanup) {
        element.classList.remove(animationClass);
      }
      element.removeEventListener('animationend', handleAnimationEnd);
    };
    
    element.addEventListener('animationend', handleAnimationEnd);
    
    if (duration) {
      setTimeout(() => {
        if (cleanup && element.classList.contains(animationClass)) {
          element.classList.remove(animationClass);
        }
      }, duration);
    }
  }
  
  /**
   * Create intersection observer for animations
   */
  static createScrollAnimations(selector = '[data-animate]', options = {}) {
    const defaultOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };
    
    const observerOptions = { ...defaultOptions, ...options };
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const element = entry.target;
          const animationClass = element.dataset.animate || 'animate-fade-in';
          
          this.animate(element, animationClass);
          observer.unobserve(element);
        }
      });
    }, observerOptions);
    
    document.querySelectorAll(selector).forEach(el => {
      observer.observe(el);
    });
    
    return observer;
  }
}

// Auto-initialize if in browser environment
if (typeof window !== 'undefined') {
  window.DafelThemeManager = DafelThemeManager;
  window.DafelDesignUtils = DafelDesignUtils;
  
  // Initialize default theme manager
  window.dafelTheme = DafelThemeManager.init({
    addToggle: false // Set to true to automatically add theme toggle
  });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DafelThemeManager, DafelDesignUtils };
}

if (typeof window !== 'undefined' && window.define && window.define.amd) {
  window.define('dafel-theme', [], () => ({ DafelThemeManager, DafelDesignUtils }));
}