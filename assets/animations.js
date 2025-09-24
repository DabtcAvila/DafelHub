/**
 * DAFEL HUB - PREMIUM ANIMATION SYSTEM
 * Enterprise-grade animation presets and utilities for GitHub Pages
 * Sophisticated animation library with magnetic interactions and 3D transforms
 */

// === EASING FUNCTIONS ===
export const easings = {
  // Standard easings
  linear: 'linear',
  ease: 'ease',
  easeIn: 'ease-in',
  easeOut: 'ease-out',
  easeInOut: 'ease-in-out',
  
  // Premium custom cubic-bezier easings
  sharp: 'cubic-bezier(0.4, 0, 0.6, 1)',
  bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  elastic: 'cubic-bezier(0.68, -0.6, 0.32, 1.6)',
  
  // Micro-interactions
  gentle: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
  crisp: 'cubic-bezier(0.2, 0, 0, 1)',
  magnetic: 'cubic-bezier(0.2, 0, 0.38, 0.9)',
  morphing: 'cubic-bezier(0.4, 0, 0.2, 1)',
};

// === DURATION PRESETS ===
export const durations = {
  instant: 0,
  fast: 150,
  normal: 250,
  slow: 350,
  slower: 500,
  slowest: 750,
  magnetic: 200,
  morphing: 400,
};

// === SPRING PHYSICS CONFIGURATIONS ===
export const springPhysics = {
  // Gentle spring for cards and buttons
  gentle: {
    stiffness: 300,
    damping: 30,
    mass: 1,
  },
  
  // Bouncy spring for playful interactions
  bouncy: {
    stiffness: 400,
    damping: 20,
    mass: 1,
  },
  
  // Magnetic spring for magnetic interactions
  magnetic: {
    stiffness: 200,
    damping: 15,
    mass: 0.8,
  },
  
  // Stiff spring for quick snappy animations
  snappy: {
    stiffness: 500,
    damping: 25,
    mass: 1,
  },
  
  // Soft spring for smooth transitions
  soft: {
    stiffness: 200,
    damping: 25,
    mass: 1,
  },
};

// === ANIMATION UTILITY CLASS ===
class AnimationEngine {
  constructor() {
    this.activeAnimations = new Map();
    this.magneticElements = new Set();
    this.mousePosition = { x: 0, y: 0 };
    this.init();
  }

  init() {
    // Track mouse position for magnetic effects
    document.addEventListener('mousemove', (e) => {
      this.mousePosition = { x: e.clientX, y: e.clientY };
      this.updateMagneticElements();
    });

    // Add CSS for animations
    this.injectAnimationStyles();
  }

  // === ENTRANCE ANIMATIONS ===
  fadeIn(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      ...options
    };

    const animation = element.animate([
      { opacity: 0, transform: 'translateY(0px)' },
      { opacity: 1, transform: 'translateY(0px)' }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  slideUp(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      distance: 40,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: `translateY(${config.distance}px)` 
      },
      { 
        opacity: 1, 
        transform: 'translateY(0px)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  slideDown(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      distance: 40,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: `translateY(-${config.distance}px)` 
      },
      { 
        opacity: 1, 
        transform: 'translateY(0px)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  slideLeft(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      distance: 40,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: `translateX(${config.distance}px)` 
      },
      { 
        opacity: 1, 
        transform: 'translateX(0px)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  slideRight(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      distance: 40,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: `translateX(-${config.distance}px)` 
      },
      { 
        opacity: 1, 
        transform: 'translateX(0px)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  scaleIn(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      scale: 0.8,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: `scale(${config.scale})` 
      },
      { 
        opacity: 1, 
        transform: 'scale(1)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  bounceIn(element, options = {}) {
    const config = {
      duration: 600,
      easing: easings.bounce,
      delay: 0,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: 'scale(0.3)' 
      },
      { 
        opacity: 0.7, 
        transform: 'scale(1.1)' 
      },
      { 
        opacity: 0.9, 
        transform: 'scale(0.9)' 
      },
      { 
        opacity: 1, 
        transform: 'scale(1)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  flipIn(element, options = {}) {
    const config = {
      duration: durations.slow,
      easing: easings.gentle,
      delay: 0,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: 'rotateY(-90deg)' 
      },
      { 
        opacity: 1, 
        transform: 'rotateY(0deg)' 
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  zoomIn(element, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      delay: 0,
      ...options
    };

    const animation = element.animate([
      { 
        opacity: 0, 
        transform: 'scale(0.95)',
        filter: 'blur(4px)'
      },
      { 
        opacity: 1, 
        transform: 'scale(1)',
        filter: 'blur(0px)'
      }
    ], {
      duration: config.duration,
      easing: config.easing,
      delay: config.delay,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  // === HOVER ANIMATIONS ===
  addHoverLift(element, options = {}) {
    const config = {
      lift: 4,
      scale: 1.02,
      duration: durations.fast,
      easing: easings.gentle,
      ...options
    };

    element.addEventListener('mouseenter', () => {
      element.style.transition = `transform ${config.duration}ms ${config.easing}`;
      element.style.transform = `translateY(-${config.lift}px) scale(${config.scale})`;
    });

    element.addEventListener('mouseleave', () => {
      element.style.transform = 'translateY(0px) scale(1)';
    });
  }

  addHoverGlow(element, options = {}) {
    const config = {
      color: 'rgba(59, 130, 246, 0.4)',
      blur: 20,
      scale: 1.02,
      duration: durations.fast,
      easing: easings.gentle,
      ...options
    };

    element.addEventListener('mouseenter', () => {
      element.style.transition = `box-shadow ${config.duration}ms ${config.easing}, transform ${config.duration}ms ${config.easing}`;
      element.style.boxShadow = `0 0 ${config.blur}px ${config.color}`;
      element.style.transform = `scale(${config.scale})`;
    });

    element.addEventListener('mouseleave', () => {
      element.style.boxShadow = 'none';
      element.style.transform = 'scale(1)';
    });
  }

  addHoverTilt(element, options = {}) {
    const config = {
      rotateX: 10,
      rotateY: 10,
      scale: 1.02,
      duration: durations.fast,
      easing: easings.gentle,
      ...options
    };

    element.style.transformStyle = 'preserve-3d';
    element.style.perspective = '1000px';

    element.addEventListener('mouseenter', () => {
      element.style.transition = `transform ${config.duration}ms ${config.easing}`;
      element.style.transform = `rotateX(${config.rotateX}deg) rotateY(${config.rotateY}deg) scale(${config.scale})`;
    });

    element.addEventListener('mouseleave', () => {
      element.style.transform = 'rotateX(0deg) rotateY(0deg) scale(1)';
    });
  }

  // === MAGNETIC INTERACTIONS ===
  addMagneticEffect(element, options = {}) {
    const config = {
      strength: 0.3,
      radius: 100,
      duration: durations.magnetic,
      easing: easings.magnetic,
      ...options
    };

    this.magneticElements.add({ element, config });
    element.dataset.magneticActive = 'true';
  }

  updateMagneticElements() {
    this.magneticElements.forEach(({ element, config }) => {
      const rect = element.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      
      const deltaX = this.mousePosition.x - centerX;
      const deltaY = this.mousePosition.y - centerY;
      const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
      
      if (distance < config.radius) {
        const strength = (config.radius - distance) / config.radius;
        const moveX = deltaX * config.strength * strength;
        const moveY = deltaY * config.strength * strength;
        
        element.style.transition = `transform ${config.duration}ms ${config.easing}`;
        element.style.transform = `translate(${moveX}px, ${moveY}px)`;
      } else {
        element.style.transform = 'translate(0px, 0px)';
      }
    });
  }

  // === MORPHING BUTTON STATES ===
  createMorphingButton(element, states) {
    const buttonStates = {
      idle: { scale: 1, backgroundColor: '#3b82f6', borderRadius: '8px' },
      loading: { scale: 0.95, backgroundColor: '#6366f1', borderRadius: '50%' },
      success: { scale: 1.1, backgroundColor: '#10b981', borderRadius: '8px' },
      error: { scale: 0.9, backgroundColor: '#ef4444', borderRadius: '8px' },
      ...states
    };

    element.morphTo = (stateName) => {
      const targetState = buttonStates[stateName];
      if (!targetState) return;

      const currentState = window.getComputedStyle(element);
      const keyframes = [
        {
          transform: element.style.transform || 'scale(1)',
          backgroundColor: currentState.backgroundColor,
          borderRadius: currentState.borderRadius,
        },
        {
          transform: `scale(${targetState.scale})`,
          backgroundColor: targetState.backgroundColor,
          borderRadius: targetState.borderRadius,
        }
      ];

      return element.animate(keyframes, {
        duration: durations.morphing,
        easing: easings.morphing,
        fill: 'both'
      });
    };

    return element;
  }

  // === STAGGER ANIMATIONS ===
  staggerChildren(container, animationType = 'fadeIn', options = {}) {
    const config = {
      staggerDelay: 100,
      childDelay: 50,
      ...options
    };

    const children = Array.from(container.children);
    
    children.forEach((child, index) => {
      const delay = config.childDelay + (index * config.staggerDelay);
      
      setTimeout(() => {
        this[animationType](child, { delay: 0, ...config });
      }, delay);
    });
  }

  // === 3D TRANSFORM UTILITIES ===
  setup3D(element, options = {}) {
    const config = {
      perspective: 1000,
      preserveStyle: true,
      ...options
    };

    element.style.perspective = `${config.perspective}px`;
    if (config.preserveStyle) {
      element.style.transformStyle = 'preserve-3d';
    }
  }

  rotate3D(element, x = 0, y = 0, z = 0, options = {}) {
    const config = {
      duration: durations.normal,
      easing: easings.gentle,
      ...options
    };

    const animation = element.animate([
      { transform: element.style.transform || 'rotateX(0deg) rotateY(0deg) rotateZ(0deg)' },
      { transform: `rotateX(${x}deg) rotateY(${y}deg) rotateZ(${z}deg)` }
    ], {
      duration: config.duration,
      easing: config.easing,
      fill: 'both'
    });

    return this.trackAnimation(element, animation);
  }

  // === LOADING ANIMATIONS ===
  addSpinner(element, options = {}) {
    const config = {
      duration: 1000,
      iterations: Infinity,
      easing: easings.linear,
      ...options
    };

    const animation = element.animate([
      { transform: 'rotate(0deg)' },
      { transform: 'rotate(360deg)' }
    ], {
      duration: config.duration,
      iterations: config.iterations,
      easing: config.easing
    });

    return this.trackAnimation(element, animation);
  }

  addPulse(element, options = {}) {
    const config = {
      duration: 1500,
      iterations: Infinity,
      easing: easings.easeInOut,
      minScale: 1,
      maxScale: 1.2,
      ...options
    };

    const animation = element.animate([
      { transform: `scale(${config.minScale})` },
      { transform: `scale(${config.maxScale})` },
      { transform: `scale(${config.minScale})` }
    ], {
      duration: config.duration,
      iterations: config.iterations,
      easing: config.easing
    });

    return this.trackAnimation(element, animation);
  }

  // === UTILITY FUNCTIONS ===
  trackAnimation(element, animation) {
    const id = Math.random().toString(36).substr(2, 9);
    this.activeAnimations.set(id, { element, animation });
    
    animation.addEventListener('finish', () => {
      this.activeAnimations.delete(id);
    });

    return { id, animation };
  }

  stopAnimation(id) {
    const animationData = this.activeAnimations.get(id);
    if (animationData) {
      animationData.animation.cancel();
      this.activeAnimations.delete(id);
    }
  }

  stopAllAnimations() {
    this.activeAnimations.forEach((animationData, id) => {
      animationData.animation.cancel();
    });
    this.activeAnimations.clear();
  }

  // === CSS INJECTION FOR KEYFRAMES ===
  injectAnimationStyles() {
    const styles = `
      @keyframes shimmer {
        0% { background-position: -100% 0; }
        100% { background-position: 100% 0; }
      }

      @keyframes glow-pulse {
        0%, 100% { 
          box-shadow: 0 0 5px rgba(59, 130, 246, 0.3);
        }
        50% { 
          box-shadow: 0 0 20px rgba(59, 130, 246, 0.6), 0 0 30px rgba(59, 130, 246, 0.4);
        }
      }

      @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-6px); }
      }

      @keyframes breathe {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
      }

      @keyframes wave {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
      }

      @keyframes elastic-in {
        0% {
          transform: scale(0);
          animation-timing-function: ease-in;
        }
        25% {
          transform: scale(1.25);
        }
        50% {
          transform: scale(0.85);
        }
        75% {
          transform: scale(1.1);
        }
        100% {
          transform: scale(1);
        }
      }

      @keyframes magnetic-pull {
        0% { transform: translate(0, 0) scale(1); }
        100% { transform: translate(var(--magnetic-x, 0), var(--magnetic-y, 0)) scale(1.02); }
      }

      /* Premium effect classes */
      .dafel-shimmer {
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
        background-size: 200% 100%;
        animation: shimmer 2s infinite;
      }

      .dafel-glow {
        animation: glow-pulse 2s ease-in-out infinite;
      }

      .dafel-float {
        animation: float 3s ease-in-out infinite;
      }

      .dafel-breathe {
        animation: breathe 4s ease-in-out infinite;
      }

      .dafel-magnetic {
        transition: transform 200ms cubic-bezier(0.2, 0, 0.38, 0.9);
      }

      .dafel-3d {
        transform-style: preserve-3d;
        perspective: 1000px;
      }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
  }
}

// === PRESET COMBINATIONS ===
export const presetCombinations = {
  // Premium card animation
  premiumCard: (element) => {
    animationEngine.slideUp(element);
    animationEngine.addHoverLift(element);
    animationEngine.addMagneticEffect(element, { strength: 0.2 });
  },
  
  // Interactive button
  interactiveButton: (element) => {
    animationEngine.fadeIn(element);
    animationEngine.addHoverGlow(element);
    animationEngine.createMorphingButton(element);
  },
  
  // Hero section
  heroSection: (container) => {
    animationEngine.staggerChildren(container, 'slideUp', { staggerDelay: 150 });
  },
  
  // Floating action button
  fab: (element) => {
    animationEngine.bounceIn(element);
    animationEngine.addHoverLift(element, { lift: 8, scale: 1.1 });
    animationEngine.addMagneticEffect(element, { strength: 0.4 });
  },
  
  // Modal animation
  modal: (element) => {
    animationEngine.scaleIn(element, { duration: durations.slow });
  },
};

// === GLOBAL INSTANCE ===
export const animationEngine = new AnimationEngine();

// === QUICK ACCESS FUNCTIONS ===
export const animate = {
  fadeIn: (el, opts) => animationEngine.fadeIn(el, opts),
  slideUp: (el, opts) => animationEngine.slideUp(el, opts),
  slideDown: (el, opts) => animationEngine.slideDown(el, opts),
  slideLeft: (el, opts) => animationEngine.slideLeft(el, opts),
  slideRight: (el, opts) => animationEngine.slideRight(el, opts),
  scaleIn: (el, opts) => animationEngine.scaleIn(el, opts),
  bounceIn: (el, opts) => animationEngine.bounceIn(el, opts),
  flipIn: (el, opts) => animationEngine.flipIn(el, opts),
  zoomIn: (el, opts) => animationEngine.zoomIn(el, opts),
};

export const hover = {
  lift: (el, opts) => animationEngine.addHoverLift(el, opts),
  glow: (el, opts) => animationEngine.addHoverGlow(el, opts),
  tilt: (el, opts) => animationEngine.addHoverTilt(el, opts),
};

export const magnetic = {
  add: (el, opts) => animationEngine.addMagneticEffect(el, opts),
};

export const morph = {
  button: (el, states) => animationEngine.createMorphingButton(el, states),
};

export const stagger = {
  children: (container, type, opts) => animationEngine.staggerChildren(container, type, opts),
};

export const transform3d = {
  setup: (el, opts) => animationEngine.setup3D(el, opts),
  rotate: (el, x, y, z, opts) => animationEngine.rotate3D(el, x, y, z, opts),
};

export const loading = {
  spinner: (el, opts) => animationEngine.addSpinner(el, opts),
  pulse: (el, opts) => animationEngine.addPulse(el, opts),
};

// === AUTO-INITIALIZATION ===
if (typeof window !== 'undefined') {
  // Auto-apply animations to elements with data attributes
  document.addEventListener('DOMContentLoaded', () => {
    // Entrance animations
    document.querySelectorAll('[data-animate]').forEach(el => {
      const animationType = el.dataset.animate;
      if (animate[animationType]) {
        const delay = parseInt(el.dataset.delay) || 0;
        setTimeout(() => animate[animationType](el), delay);
      }
    });

    // Hover effects
    document.querySelectorAll('[data-hover]').forEach(el => {
      const hoverType = el.dataset.hover;
      if (hover[hoverType]) {
        hover[hoverType](el);
      }
    });

    // Magnetic effects
    document.querySelectorAll('[data-magnetic]').forEach(el => {
      const strength = parseFloat(el.dataset.magneticStrength) || 0.3;
      const radius = parseInt(el.dataset.magneticRadius) || 100;
      magnetic.add(el, { strength, radius });
    });

    // Stagger containers
    document.querySelectorAll('[data-stagger]').forEach(container => {
      const animationType = container.dataset.stagger || 'fadeIn';
      const delay = parseInt(container.dataset.staggerDelay) || 100;
      stagger.children(container, animationType, { staggerDelay: delay });
    });
  });
}