# DafelHub Interactive Components

> Enterprise-grade interactive component library with sophisticated animations and premium effects

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/DabtcAvila/DafelHub)
[![TypeScript](https://img.shields.io/badge/TypeScript-Ready-blue.svg)](https://www.typescriptlang.org/)
[![Framer Motion](https://img.shields.io/badge/Framer%20Motion-Powered-purple.svg)](https://www.framer.com/motion/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 🚀 Features

- **🧲 Magnetic Interactions**: Buttons that follow cursor movement with spring physics
- **🎭 3D Tilt Effects**: Cards with realistic 3D transforms and preserve-3d
- **💫 Ripple Animations**: Material Design inspired ripple effects
- **✨ Dynamic Glow**: Mouse-following glow effects with customizable colors
- **🎯 Floating Actions**: Premium FAB with bounce animations
- **🎪 Morphing States**: Smooth state transitions with animated icons
- **🎨 Glassmorphism**: Modern backdrop blur and transparency effects
- **⚡ Performance Optimized**: Hardware acceleration and smooth 60fps animations
- **♿ Accessible**: Screen reader friendly with reduced motion support
- **📱 Responsive**: Touch-optimized for mobile devices

## 📦 Installation

```bash
npm install @dafelhub/interactive-components framer-motion
# or
yarn add @dafelhub/interactive-components framer-motion
# or
pnpm add @dafelhub/interactive-components framer-motion
```

## 🎯 Quick Start

```tsx
import React from 'react';
import { 
  MagneticButton, 
  TiltCard, 
  GlowCard 
} from '@dafelhub/interactive-components';

function App() {
  return (
    <div>
      {/* Magnetic Button */}
      <MagneticButton strength={0.4} magneticRange={100}>
        Hover me!
      </MagneticButton>

      {/* 3D Tilt Card */}
      <TiltCard intensity={15}>
        <div className="p-6">
          <h3>Premium Card</h3>
          <p>With 3D tilt effects</p>
        </div>
      </TiltCard>

      {/* Glow Card */}
      <GlowCard glowColor="#8B5CF6" glowIntensity={0.3}>
        <div className="p-6">
          <h3>Dynamic Glow</h3>
          <p>Follows your cursor</p>
        </div>
      </GlowCard>
    </div>
  );
}
```

## 🎨 Components

### MagneticButton

Button that attracts to cursor movement with spring physics.

```tsx
<MagneticButton 
  strength={0.4}          // Magnetic strength (0-1)
  magneticRange={100}     // Attraction radius in pixels
  className="custom-btn"  // Custom styling
>
  Magnetic Button
</MagneticButton>
```

**Props:**
- `strength?: number` - Magnetic attraction strength (default: 0.4)
- `magneticRange?: number` - Attraction radius in pixels (default: 100)
- All standard button props

### TiltCard

3D tilt card with preserve-3d transforms.

```tsx
<TiltCard 
  intensity={15}          // Tilt intensity (0-50)
  perspective={1000}      // 3D perspective value
  className="custom-card"
>
  <div>Card Content</div>
</TiltCard>
```

**Props:**
- `intensity?: number` - Tilt intensity (default: 15)
- `perspective?: number` - CSS perspective value (default: 1000)

### RippleButton

Material Design inspired ripple effect button.

```tsx
<RippleButton 
  rippleColor="rgba(255, 255, 255, 0.4)"  // Ripple color
  onClick={handleClick}
>
  Ripple Button
</RippleButton>
```

**Props:**
- `rippleColor?: string` - Ripple effect color (default: rgba(255, 255, 255, 0.4))
- All standard button props

### GlowCard

Card with dynamic glow effect that follows cursor.

```tsx
<GlowCard 
  glowColor="#3B82F6"     // Glow color (hex)
  glowIntensity={0.3}     // Glow intensity (0-1)
>
  <div>Glowing Content</div>
</GlowCard>
```

**Props:**
- `glowColor?: string` - Glow color in hex format (default: #3B82F6)
- `glowIntensity?: number` - Glow opacity intensity (default: 0.3)

### FloatingActionButton

Premium floating action button with bounce animations.

```tsx
<FloatingActionButton 
  position="bottom-right"  // Position on screen
  size="md"               // Button size
  onClick={handleClick}
>
  +
</FloatingActionButton>
```

**Props:**
- `position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'`
- `size?: 'sm' | 'md' | 'lg'`
- `icon?: React.ReactNode` - Custom icon

### SlidingPanel

Smooth sliding panel with backdrop blur.

```tsx
<SlidingPanel 
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  direction="right"       // Slide direction
  size="md"              // Panel size
  blurBackground={true}   // Enable backdrop blur
>
  <div>Panel Content</div>
</SlidingPanel>
```

**Props:**
- `isOpen: boolean` - Panel visibility
- `onClose: () => void` - Close callback
- `direction?: 'left' | 'right' | 'top' | 'bottom'` - Slide direction
- `size?: 'sm' | 'md' | 'lg' | 'full'` - Panel size
- `blurBackground?: boolean` - Enable backdrop blur

### MorphingButton

Button that morphs between different states.

```tsx
const [state, setState] = useState<'loading' | 'success' | 'error'>();

<MorphingButton 
  morphTo={state}
  onClick={handleClick}
>
  {state ? '' : 'Click Me'}
</MorphingButton>
```

**Props:**
- `morphTo?: 'loading' | 'success' | 'error'` - Current state
- All standard button props

## 🎭 Premium Combinations

Pre-built component combinations for exceptional UX:

```tsx
// Interactive Demo Card (Tilt + Glow)
<InteractiveDemoCard>
  <h3>Premium Content</h3>
  <p>Combined effects</p>
</InteractiveDemoCard>

// Premium Action Button (Magnetic + Ripple)
<PremiumActionButton onClick={handleClick}>
  Premium Action
</PremiumActionButton>

// Glassmorphism Card
<GlassmorphismCard variant="heavy">
  <div>Modern Glass Effect</div>
</GlassmorphismCard>
```

## 🎨 Styling & Customization

### CSS Classes

The library works seamlessly with Tailwind CSS and custom CSS:

```tsx
<MagneticButton className="bg-gradient-to-r from-purple-600 to-blue-600 text-white px-8 py-4 rounded-xl">
  Custom Styled
</MagneticButton>
```

### Glassmorphism Variants

```tsx
import { glassmorphismStyles } from '@dafelhub/interactive-components';

// Available variants
glassmorphismStyles.light   // bg-white/10 backdrop-blur-md
glassmorphismStyles.medium  // bg-white/5 backdrop-blur-lg  
glassmorphismStyles.heavy   // bg-white/15 backdrop-blur-xl
glassmorphismStyles.dark    // bg-black/10 backdrop-blur-md
```

## ⚡ Performance

### Hardware Acceleration

All components use hardware acceleration for smooth 60fps animations:

```tsx
// Automatic GPU acceleration
transform-gpu will-change-transform
```

### Reduced Motion Support

Respects user preferences for reduced motion:

```tsx
import { a11yUtils } from '@dafelhub/interactive-components';

// Initialize reduced motion support
a11yUtils.respectReducedMotion();
```

### Touch Optimization

```tsx
// Optimize for touch devices
a11yUtils.optimizeForTouch();
```

## 🎛️ Animation System

### Spring Physics

```tsx
import { springs } from '@dafelhub/interactive-components';

// Available spring presets
springs.gentle   // Smooth, elegant
springs.bouncy   // Playful, energetic  
springs.snappy   // Quick, responsive
springs.soft     // Subtle, refined
springs.premium  // Ultra-smooth
```

### Entrance Animations

```tsx
import { entranceAnimations } from '@dafelhub/interactive-components';

// Slide animations
entranceAnimations.slideUp
entranceAnimations.slideDown
entranceAnimations.slideLeft
entranceAnimations.slideRight

// Scale animations
entranceAnimations.scaleIn
entranceAnimations.bounceIn

// Advanced animations
entranceAnimations.magneticSlide
entranceAnimations.glowFade
```

### Hover Effects

```tsx
import { hoverAnimations } from '@dafelhub/interactive-components';

// Basic hovers
hoverAnimations.lift
hoverAnimations.scale
hoverAnimations.glow

// Premium hovers
hoverAnimations.magneticPull
hoverAnimations.glowPulse
hoverAnimations.tilt
```

## 🌟 Advanced Usage

### Custom Animations

```tsx
import { motion } from 'framer-motion';
import { springs, easings } from '@dafelhub/interactive-components';

<motion.div
  whileHover={{ scale: 1.05 }}
  transition={springs.premium}
>
  Custom Animation
</motion.div>
```

### Staggered Animations

```tsx
import { staggerAnimations } from '@dafelhub/interactive-components';

<motion.div variants={staggerAnimations.container}>
  {items.map(item => (
    <motion.div key={item.id} variants={entranceAnimations.slideUp}>
      {item.content}
    </motion.div>
  ))}
</motion.div>
```

### Theme Integration

```tsx
import { themeConfig } from '@dafelhub/interactive-components';

// Access color palette
const primaryColor = themeConfig.colors.primary[500];
const accentColor = themeConfig.colors.accent[600];
```

## 📱 Responsive Design

All components are mobile-first and touch-optimized:

```tsx
// Responsive magnetic button
<MagneticButton 
  strength={{ mobile: 0.2, desktop: 0.4 }}
  magneticRange={{ mobile: 60, desktop: 100 }}
>
  Responsive Magnetic
</MagneticButton>
```

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/DabtcAvila/DafelHub.git

# Navigate to components
cd DafelHub/src

# Install dependencies
npm install

# Start development
npm run dev

# Build for production
npm run build
```

## 🧪 Testing

```bash
# Run tests
npm test

# Run with coverage
npm run test:coverage

# Visual regression tests
npm run test:visual
```

## 📚 Examples

Check out the [Interactive Showcase](./components/InteractiveShowcase.tsx) for comprehensive examples and live demos.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](../../CONTRIBUTING.md) for details.

## 📄 License

MIT License - see [LICENSE](../../LICENSE) for details.

## 🎯 Roadmap

- [ ] More 3D effects and transforms
- [ ] Advanced particle systems
- [ ] Voice interaction support
- [ ] AR/VR compatibility
- [ ] Advanced gesture recognition
- [ ] Real-time collaboration features

## 💫 Showcase

Built with ❤️ by the DafelHub team for creating exceptional user experiences.

---

**DafelHub** - Where innovation meets excellence in enterprise software development.