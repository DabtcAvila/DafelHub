/**
 * DAFELHUB - PREMIUM INTERACTIVE COMPONENTS
 * Enterprise-grade component library with sophisticated interactions
 * Connected to 23+ real API endpoints with JWT authentication
 */

// === INTERACTIVE COMPONENTS ===
export {
  MagneticButton,
  TiltCard,
  RippleButton,
  GlowCard,
  FloatingActionButton,
  SlidingPanel,
  MorphingButton,
  InteractiveDemoCard,
  PremiumActionButton,
  GlassmorphismCard,
  glassmorphismStyles,
} from './InteractiveElements';

// === AUTHENTICATION COMPONENTS ===
export {
  LoginForm,
  RegisterForm,
  MFASetup,
  AuthContainer,
} from './AuthComponents';

// === ADMIN PANEL COMPONENTS ===
export {
  AdminPanel,
} from './AdminPanel';

// === DASHBOARD COMPONENTS ===
export {
  DashboardComponents,
} from './DashboardComponents';

// === STUDIO COMPONENTS ===
export {
  DafelStudio,
  Canvas,
  DataSourcesManager,
  AnalyticsDashboard,
  TestingInterface,
  AIModelsManager,
  SettingsPanel,
} from './studio';

// === HOOKS ===
export {
  useAuth,
  AuthProvider,
  withAuth,
} from './hooks/useAuth';

export {
  useAPI,
  useAPIResource,
  useAPIList,
  useAPIMutation,
  API_ENDPOINTS,
} from './hooks/useAPI';

export {
  useWebSocket,
  useRealTimeNotifications,
  useRealTimeMetrics,
  useRealTimeActivity,
  useUserPresence,
} from './hooks/useRealTime';

// === UTILITIES ===
export {
  tokenUtils,
  cacheUtils,
  debugUtils,
  createAPIClient,
  handleAPIError,
  buildURL,
  uploadFile,
  downloadFile,
} from './utils/api';

export {
  validateField,
  validateForm,
  createValidator,
  checkPasswordStrength,
  getFieldError,
  hasFieldError,
  sanitizeInput,
  validateFile,
  VALIDATION_PATTERNS,
  ERROR_MESSAGES,
  VALIDATION_SCHEMAS,
} from './utils/validation';

// === COMPONENT TYPES ===
export type {
  MagneticButtonProps,
  TiltCardProps,
  RippleButtonProps,
  GlowCardProps,
  FloatingActionButtonProps,
  SlidingPanelProps,
  MorphingButtonProps,
} from './InteractiveElements';

// === ANIMATION UTILITIES ===
export {
  springs,
  easings,
  durations,
  entranceAnimations,
  hoverAnimations,
  tapAnimations,
  staggerAnimations,
  pageTransitions,
  loadingAnimations,
  presetCombinations,
  particleAnimations,
  backgroundAnimations,
  createStaggeredAnimation,
  combineAnimations,
  createResponsiveAnimation,
  createDelayedAnimation,
} from '../lib/animations';

// === UTILITY FUNCTIONS ===
export const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// === PRESET CONFIGURATIONS ===
export const componentPresets = {
  // Button presets
  buttons: {
    primary: 'bg-gradient-to-r from-blue-600 to-purple-600 text-white',
    secondary: 'bg-gradient-to-r from-gray-600 to-gray-700 text-white',
    accent: 'bg-gradient-to-r from-purple-600 to-pink-600 text-white',
    success: 'bg-gradient-to-r from-green-600 to-emerald-600 text-white',
    warning: 'bg-gradient-to-r from-yellow-600 to-orange-600 text-white',
    danger: 'bg-gradient-to-r from-red-600 to-rose-600 text-white',
  },
  
  // Card presets
  cards: {
    glass: 'bg-white/10 backdrop-blur-lg border border-white/20',
    solid: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700',
    gradient: 'bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-lg border border-white/20',
    premium: 'bg-gradient-to-br from-purple-500/10 via-blue-500/10 to-cyan-500/10 backdrop-blur-xl border border-white/20',
  },
  
  // Glow colors
  glowColors: {
    blue: '#3B82F6',
    purple: '#8B5CF6',
    pink: '#EC4899',
    green: '#10B981',
    yellow: '#F59E0B',
    red: '#EF4444',
    cyan: '#06B6D4',
    indigo: '#6366F1',
  },
  
  // Shadow presets
  shadows: {
    soft: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    medium: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    large: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    glow: '0 0 20px rgba(59, 130, 246, 0.3)',
    premium: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  },
};

// === THEME CONFIGURATION ===
export const themeConfig = {
  colors: {
    primary: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
    },
    secondary: {
      50: '#f8fafc',
      100: '#f1f5f9',
      200: '#e2e8f0',
      300: '#cbd5e1',
      400: '#94a3b8',
      500: '#64748b',
      600: '#475569',
      700: '#334155',
      800: '#1e293b',
      900: '#0f172a',
    },
    accent: {
      50: '#faf5ff',
      100: '#f3e8ff',
      200: '#e9d5ff',
      300: '#d8b4fe',
      400: '#c084fc',
      500: '#a855f7',
      600: '#9333ea',
      700: '#7c3aed',
      800: '#6b21a8',
      900: '#581c87',
    },
  },
  
  animation: {
    duration: {
      fast: '150ms',
      normal: '300ms',
      slow: '500ms',
    },
    
    easing: {
      ease: 'cubic-bezier(0.4, 0, 0.2, 1)',
      bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
      elastic: 'cubic-bezier(0.68, -0.6, 0.32, 1.6)',
    },
  },
  
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },
};

// === COMPONENT BUILDER UTILITIES ===
export const createComponent = {
  magneticButton: (props: Partial<any> = {}) => ({
    component: 'MagneticButton',
    defaultProps: {
      strength: 0.4,
      magneticRange: 100,
      className: componentPresets.buttons.primary,
      ...props,
    },
  }),
  
  tiltCard: (props: Partial<any> = {}) => ({
    component: 'TiltCard',
    defaultProps: {
      intensity: 15,
      perspective: 1000,
      className: componentPresets.cards.glass,
      ...props,
    },
  }),
  
  rippleButton: (props: Partial<any> = {}) => ({
    component: 'RippleButton',
    defaultProps: {
      rippleColor: 'rgba(255, 255, 255, 0.4)',
      className: componentPresets.buttons.primary,
      ...props,
    },
  }),
  
  glowCard: (props: Partial<any> = {}) => ({
    component: 'GlowCard',
    defaultProps: {
      glowColor: componentPresets.glowColors.blue,
      glowIntensity: 0.3,
      className: componentPresets.cards.premium,
      ...props,
    },
  }),
};

// === PERFORMANCE OPTIMIZATION UTILITIES ===
export const optimizationUtils = {
  // Preload animations for better performance
  preloadAnimations: () => {
    if (typeof window !== 'undefined') {
      // Warm up the animation engine
      const dummy = document.createElement('div');
      dummy.style.transform = 'translateZ(0)';
      dummy.style.willChange = 'transform';
      document.body.appendChild(dummy);
      requestAnimationFrame(() => {
        document.body.removeChild(dummy);
      });
    }
  },
  
  // Enable hardware acceleration
  enableHardwareAcceleration: (element: HTMLElement) => {
    element.style.transform = 'translateZ(0)';
    element.style.willChange = 'transform';
  },
  
  // Disable hardware acceleration
  disableHardwareAcceleration: (element: HTMLElement) => {
    element.style.transform = '';
    element.style.willChange = '';
  },
  
  // Optimize for touch devices
  optimizeForTouch: () => {
    if (typeof window !== 'undefined') {
      document.documentElement.style.setProperty('--touch-action', 'manipulation');
    }
  },
};

// === ACCESSIBILITY UTILITIES ===
export const a11yUtils = {
  // Respect reduced motion preferences
  respectReducedMotion: () => {
    if (typeof window !== 'undefined') {
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (prefersReducedMotion) {
        document.documentElement.style.setProperty('--animation-duration', '0.01ms');
        document.documentElement.style.setProperty('--animation-delay', '0.01ms');
      }
    }
  },
  
  // Enhanced focus handling
  enhancedFocus: {
    className: 'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-100',
    tabIndex: 0,
  },
  
  // Screen reader friendly animations
  screenReaderSafe: {
    'aria-hidden': 'true',
    role: 'presentation',
  },
};

// === COMPONENT REGISTRY ===
export const componentRegistry = {
  MagneticButton: {
    name: 'Magnetic Button',
    description: 'Button that follows mouse movement with spring physics',
    category: 'Interactive',
    complexity: 'Advanced',
    performance: 'High',
  },
  
  TiltCard: {
    name: 'Tilt Card',
    description: '3D tilt effect card with preserve-3d transforms',
    category: 'Interactive',
    complexity: 'Advanced',
    performance: 'Medium',
  },
  
  RippleButton: {
    name: 'Ripple Button',
    description: 'Material Design inspired ripple effect button',
    category: 'Interactive',
    complexity: 'Medium',
    performance: 'Medium',
  },
  
  GlowCard: {
    name: 'Glow Card',
    description: 'Card with dynamic glow effect following mouse cursor',
    category: 'Interactive',
    complexity: 'Advanced',
    performance: 'Medium',
  },
  
  FloatingActionButton: {
    name: 'Floating Action Button',
    description: 'Premium FAB with bounce animations and positioning',
    category: 'Navigation',
    complexity: 'Medium',
    performance: 'High',
  },
  
  SlidingPanel: {
    name: 'Sliding Panel',
    description: 'Smooth sliding panel with backdrop blur effects',
    category: 'Layout',
    complexity: 'Medium',
    performance: 'High',
  },
  
  MorphingButton: {
    name: 'Morphing Button',
    description: 'Button that morphs between different states smoothly',
    category: 'Interactive',
    complexity: 'Advanced',
    performance: 'High',
  },
};

// === VERSION INFO ===
export const version = '1.0.0';
export const buildDate = new Date().toISOString();
export const author = 'DafelHub Team';
export const license = 'MIT';