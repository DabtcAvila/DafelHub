# DafelHub Premium Animation System

A sophisticated animation library for GitHub Pages with enterprise-grade motion design, magnetic interactions, and 3D transforms. This system recreates the exact level of sophistication from the original 358-line DafelTech animations.ts with additional enhancements.

## 🚀 Features

### Core Animation Types
- **Entrance Animations**: fadeIn, slideUp, slideDown, slideLeft, slideRight, scaleIn, bounceIn, flipIn, zoomIn
- **Hover Interactions**: lift, glow, tilt with 3D perspective
- **Magnetic Effects**: Mouse-following interactions with configurable strength and radius
- **Morphing States**: Advanced button state transitions (loading, success, error)
- **3D Transforms**: Perspective, preserve-3d, cube rotations, card flips
- **CSS Keyframes**: Shimmer, glow-pulse, float, breathe, wave, liquid-morph, particle effects

### Advanced Features
- **Spring Physics**: Gentle, bouncy, magnetic, snappy, and soft spring configurations
- **Stagger Animations**: Sequential child element animations with customizable delays
- **Animation Engine**: Centralized management with active animation tracking
- **Auto-initialization**: Automatic setup via data attributes
- **Responsive Design**: Optimized for mobile devices and reduced motion preferences

## 📋 Quick Start

### 1. Include the Files
```html
<link rel="stylesheet" href="assets/animations.css">
<script type="module" src="assets/animations.js"></script>
```

### 2. Basic Usage with Data Attributes
```html
<!-- Entrance animations -->
<div data-animate="fadeIn" data-delay="200">Content</div>
<div data-animate="slideUp" data-delay="400">Content</div>

<!-- Hover effects -->
<div data-hover="lift">Hover me</div>
<div data-hover="glow">Glowing hover</div>

<!-- Magnetic interaction -->
<div data-magnetic data-magnetic-strength="0.3" data-magnetic-radius="100">
  Magnetic element
</div>

<!-- Stagger container -->
<div data-stagger="slideUp" data-stagger-delay="150">
  <div>Child 1</div>
  <div>Child 2</div>
  <div>Child 3</div>
</div>
```

### 3. Programmatic Usage
```javascript
import { 
  animate, 
  hover, 
  magnetic, 
  morph, 
  stagger,
  animationEngine 
} from './assets/animations.js';

// Entrance animations
animate.fadeIn(element, { duration: 300, delay: 100 });
animate.slideUp(element, { distance: 60, easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)' });
animate.bounceIn(element);

// Hover effects
hover.lift(element, { lift: 8, scale: 1.05 });
hover.glow(element, { color: 'rgba(59, 130, 246, 0.4)' });
hover.tilt(element, { rotateX: 15, rotateY: 15 });

// Magnetic interactions
magnetic.add(element, { strength: 0.4, radius: 120 });

// Morphing button states
const button = morph.button(element, {
  idle: { scale: 1, backgroundColor: '#3b82f6' },
  loading: { scale: 0.95, backgroundColor: '#6366f1', borderRadius: '50%' },
  success: { scale: 1.1, backgroundColor: '#10b981' }
});
button.morphTo('loading');

// Stagger animations
stagger.children(container, 'slideUp', { staggerDelay: 200 });
```

## 🎨 CSS Classes

### Entrance Animations
```css
.dafel-fade-in       /* Fade in animation */
.dafel-slide-up      /* Slide up animation */
.dafel-slide-down    /* Slide down animation */
.dafel-scale-in      /* Scale in animation */
.dafel-bounce-in     /* Bounce in animation */
```

### Continuous Effects
```css
.dafel-shimmer       /* Shimmer light effect */
.dafel-glow          /* Pulsing glow effect */
.dafel-rainbow-glow  /* Rainbow color glow */
.dafel-float         /* Gentle floating motion */
.dafel-float-dynamic /* Complex floating with rotation */
.dafel-breathe       /* Subtle scale pulsing */
.dafel-wave          /* Wave motion effect */
```

### 3D Effects
```css
.dafel-3d            /* Enable 3D transforms */
.dafel-cube-rotation /* 3D cube rotation */
.dafel-card-flip     /* 3D card flip effect */
.dafel-perspective-shift /* Dynamic perspective */
.dafel-liquid        /* Liquid morphing borders */
```

### Interactive Effects
```css
.dafel-hover-lift    /* Lift on hover */
.dafel-hover-glow    /* Glow on hover */
.dafel-hover-tilt    /* 3D tilt on hover */
.dafel-magnetic      /* Magnetic interaction ready */
```

### Loading States
```css
.dafel-spinner       /* Rotating spinner */
.dafel-pulse-loader  /* Pulsing loader */
.dafel-morphing-loader /* Shape-changing loader */
```

### Text Effects
```css
.dafel-gradient-text /* Gradient text color */
.dafel-animated-gradient-text /* Animated gradient text */
.dafel-shimmer-text  /* Shimmering text effect */
.dafel-typing-cursor /* Typing cursor effect */
```

## ⚙️ Configuration Options

### Animation Options
```javascript
{
  duration: 250,        // Animation duration in ms
  easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)', // Easing function
  delay: 0,            // Delay before animation starts
  distance: 40,        // Movement distance for slide animations
  scale: 0.8,          // Scale factor for scale animations
}
```

### Magnetic Options
```javascript
{
  strength: 0.3,       // Magnetic pull strength (0-1)
  radius: 100,         // Activation radius in pixels
  duration: 200,       // Transition duration
  easing: 'cubic-bezier(0.2, 0, 0.38, 0.9)' // Magnetic easing
}
```

### Hover Options
```javascript
{
  lift: 4,             // Lift distance in pixels
  scale: 1.02,         // Scale factor
  rotateX: 10,         // X-axis rotation in degrees
  rotateY: 10,         // Y-axis rotation in degrees
  color: 'rgba(59, 130, 246, 0.4)', // Glow color
  blur: 20,            // Glow blur radius
}
```

### Stagger Options
```javascript
{
  staggerDelay: 100,   // Delay between children
  childDelay: 50,      // Initial delay for first child
}
```

## 🔧 Advanced Features

### Animation Engine Control
```javascript
// Stop specific animation
const { id } = animate.fadeIn(element);
animationEngine.stopAnimation(id);

// Stop all animations
animationEngine.stopAllAnimations();

// Track active animations
console.log(animationEngine.activeAnimations);
```

### 3D Transform Utilities
```javascript
import { transform3d } from './assets/animations.js';

// Setup 3D context
transform3d.setup(element, { perspective: 1000 });

// Apply 3D rotation
transform3d.rotate(element, 45, 30, 15, { duration: 500 });
```

### Custom Spring Physics
```javascript
import { springPhysics } from './assets/animations.js';

// Available spring configurations
springPhysics.gentle    // Smooth, gentle motion
springPhysics.bouncy    // Playful, bouncy motion
springPhysics.magnetic  // Optimized for magnetic interactions
springPhysics.snappy    // Quick, responsive motion
springPhysics.soft      // Soft, flowing motion
```

### Preset Combinations
```javascript
import { presetCombinations } from './assets/animations.js';

// Apply preset animation combinations
presetCombinations.premiumCard(cardElement);
presetCombinations.interactiveButton(buttonElement);
presetCombinations.heroSection(heroContainer);
presetCombinations.fab(floatingActionButton);
presetCombinations.modal(modalElement);
```

## 📱 Responsive Behavior

The animation system automatically adapts for different screen sizes and user preferences:

- **Mobile Devices**: Reduced animation intensities and shorter durations
- **Reduced Motion**: Respects `prefers-reduced-motion` setting
- **Performance**: GPU acceleration and `will-change` optimizations
- **Touch Devices**: Magnetic effects disabled on touch screens

## 🎯 Performance Optimizations

- **GPU Acceleration**: Automatic `translateZ(0)` and `will-change` properties
- **Animation Tracking**: Centralized management prevents memory leaks
- **Lazy Loading**: Effects only initialize when needed
- **Batch Updates**: Efficient DOM manipulations
- **Reduced Motion**: Automatic fallbacks for accessibility

## 🛠️ Browser Support

- **Modern Browsers**: Full support for Chrome, Firefox, Safari, Edge
- **Web Animations API**: Required for JavaScript animations
- **CSS Animations**: Fallback support for older browsers
- **3D Transforms**: WebKit and standards support

## 📖 Examples

### Premium Card Component
```html
<div class="card" data-animate="slideUp" data-hover="lift" data-magnetic>
  <h3>Premium Card</h3>
  <p>Interactive card with multiple effects</p>
</div>
```

### Morphing Button
```javascript
const button = document.querySelector('#action-btn');
const morphButton = morph.button(button);

// Handle different states
button.addEventListener('click', async () => {
  morphButton.morphTo('loading');
  
  try {
    await performAction();
    morphButton.morphTo('success');
    setTimeout(() => morphButton.morphTo('idle'), 2000);
  } catch (error) {
    morphButton.morphTo('error');
    setTimeout(() => morphButton.morphTo('idle'), 2000);
  }
});
```

### Staggered List Animation
```javascript
// Animate list items with stagger
const list = document.querySelector('.feature-list');
stagger.children(list, 'slideUp', { 
  staggerDelay: 150,
  childDelay: 100 
});
```

## 🎨 Customization

### Custom Easing Functions
```javascript
import { easings } from './assets/animations.js';

// Use built-in easings
animate.slideUp(element, { easing: easings.bounce });
animate.fadeIn(element, { easing: easings.magnetic });

// Or use custom cubic-bezier
animate.scaleIn(element, { 
  easing: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)' 
});
```

### Custom CSS Keyframes
```css
@keyframes custom-effect {
  0% { transform: scale(1) rotate(0deg); }
  50% { transform: scale(1.2) rotate(180deg); }
  100% { transform: scale(1) rotate(360deg); }
}

.custom-animation {
  animation: custom-effect 2s ease-in-out infinite;
}
```

## 📚 API Reference

### Core Methods
- `animate.fadeIn(element, options)`
- `animate.slideUp(element, options)`
- `animate.slideDown(element, options)`
- `animate.slideLeft(element, options)`
- `animate.slideRight(element, options)`
- `animate.scaleIn(element, options)`
- `animate.bounceIn(element, options)`
- `animate.flipIn(element, options)`
- `animate.zoomIn(element, options)`

### Interaction Methods
- `hover.lift(element, options)`
- `hover.glow(element, options)`
- `hover.tilt(element, options)`
- `magnetic.add(element, options)`
- `morph.button(element, states)`

### Utility Methods
- `stagger.children(container, animationType, options)`
- `transform3d.setup(element, options)`
- `transform3d.rotate(element, x, y, z, options)`
- `loading.spinner(element, options)`
- `loading.pulse(element, options)`

## 🔗 Integration

### With Popular Frameworks
```javascript
// React Component
useEffect(() => {
  animate.slideUp(cardRef.current);
  hover.lift(cardRef.current);
}, []);

// Vue Component
mounted() {
  animate.fadeIn(this.$refs.card);
  magnetic.add(this.$refs.button);
}

// Vanilla JavaScript
document.addEventListener('DOMContentLoaded', () => {
  presetCombinations.heroSection(document.querySelector('.hero'));
});
```

## 📄 License

This animation system is part of the DafelHub project. Built with ❤️ for premium web experiences.

---

**Note**: This animation system is designed to match and exceed the sophistication of the original 358-line animations.ts from DafelTech, providing enterprise-grade motion design for GitHub Pages deployment.