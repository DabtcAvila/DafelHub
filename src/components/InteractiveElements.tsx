'use client';

import React from 'react';
import { motion, HTMLMotionProps, useMotionValue, useSpring, useTransform, AnimatePresence } from 'framer-motion';

// === UTILITY FUNCTIONS ===
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// === ANIMATION PRESETS ===
const springs = {
  gentle: {
    type: 'spring' as const,
    stiffness: 300,
    damping: 30,
  },
  bouncy: {
    type: 'spring' as const,
    stiffness: 400,
    damping: 20,
  },
  snappy: {
    type: 'spring' as const,
    stiffness: 500,
    damping: 25,
  },
  soft: {
    type: 'spring' as const,
    stiffness: 200,
    damping: 25,
  },
};

const easings = {
  gentle: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number],
  smooth: [0.4, 0, 0.2, 1] as [number, number, number, number],
  bounce: [0.68, -0.55, 0.265, 1.55] as [number, number, number, number],
  elastic: [0.68, -0.6, 0.32, 1.6] as [number, number, number, number],
};

// === MAGNETIC BUTTON ===
export interface MagneticButtonProps extends HTMLMotionProps<'button'> {
  strength?: number;
  children?: React.ReactNode;
  magneticRange?: number;
}

export const MagneticButton: React.FC<MagneticButtonProps> = ({
  strength = 0.4,
  magneticRange = 100,
  className,
  children,
  ...props
}) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 300, damping: 30 });
  const springY = useSpring(y, { stiffness: 300, damping: 30 });
  
  const buttonRef = React.useRef<HTMLButtonElement>(null);

  const handleMouseMove = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (!buttonRef.current) return;
    
    const rect = buttonRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    const distance = Math.sqrt(
      Math.pow(event.clientX - centerX, 2) + Math.pow(event.clientY - centerY, 2)
    );
    
    if (distance < magneticRange) {
      const deltaX = (event.clientX - centerX) * strength;
      const deltaY = (event.clientY - centerY) * strength;
      
      x.set(deltaX);
      y.set(deltaY);
    }
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.button
      ref={buttonRef}
      className={cn(
        'relative px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-xl',
        'shadow-lg hover:shadow-xl transition-shadow duration-300',
        'transform-gpu will-change-transform',
        className
      )}
      style={{ x: springX, y: springY }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      whileHover={{ 
        scale: 1.05,
        boxShadow: '0 20px 40px rgba(59, 130, 246, 0.3)',
      }}
      whileTap={{ scale: 0.95 }}
      transition={springs.gentle}
      {...props}
    >
      <motion.div
        className="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-400 to-purple-400 opacity-0"
        whileHover={{ opacity: 0.2 }}
        transition={{ duration: 0.3 }}
      />
      <span className="relative z-10">{children}</span>
    </motion.button>
  );
};

// === TILT CARD ===
export interface TiltCardProps extends HTMLMotionProps<'div'> {
  intensity?: number;
  perspective?: number;
  children?: React.ReactNode;
}

export const TiltCard: React.FC<TiltCardProps> = ({
  intensity = 15,
  perspective = 1000,
  className,
  children,
  ...props
}) => {
  const rotateX = useMotionValue(0);
  const rotateY = useMotionValue(0);
  const springRotateX = useSpring(rotateX, springs.soft);
  const springRotateY = useSpring(rotateY, springs.soft);

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const deltaX = (event.clientX - centerX) / rect.width;
    const deltaY = (event.clientY - centerY) / rect.height;
    
    rotateX.set(-deltaY * intensity);
    rotateY.set(deltaX * intensity);
  };

  const handleMouseLeave = () => {
    rotateX.set(0);
    rotateY.set(0);
  };

  return (
    <div style={{ perspective: `${perspective}px` }}>
      <motion.div
        className={cn(
          'relative bg-white/10 backdrop-blur-lg rounded-2xl border border-white/20',
          'shadow-xl hover:shadow-2xl transition-shadow duration-500',
          'transform-gpu will-change-transform',
          className
        )}
        style={{ 
          rotateX: springRotateX, 
          rotateY: springRotateY,
          transformStyle: 'preserve-3d',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        whileHover={{ scale: 1.02 }}
        transition={springs.gentle}
        {...props}
      >
        <div className="relative z-10 p-6">
          {children}
        </div>
        
        {/* Shine effect */}
        <motion.div
          className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/20 via-transparent to-transparent opacity-0 pointer-events-none"
          whileHover={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        />
      </motion.div>
    </div>
  );
};

// === RIPPLE BUTTON ===
export interface RippleButtonProps extends HTMLMotionProps<'button'> {
  rippleColor?: string;
  children?: React.ReactNode;
}

export const RippleButton: React.FC<RippleButtonProps> = ({
  rippleColor = 'rgba(255, 255, 255, 0.4)',
  className,
  children,
  onClick,
  ...props
}) => {
  const [ripples, setRipples] = React.useState<Array<{
    id: number;
    x: number;
    y: number;
    size: number;
  }>>([]);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const size = Math.max(rect.width, rect.height) * 2.5;
    
    const newRipple = {
      id: Date.now() + Math.random(),
      x,
      y,
      size,
    };
    
    setRipples(prev => [...prev, newRipple]);
    
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id));
    }, 800);
    
    onClick?.(event);
  };

  return (
    <motion.button
      className={cn(
        'relative px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white font-semibold rounded-xl',
        'shadow-lg hover:shadow-xl transition-shadow duration-300 overflow-hidden',
        'transform-gpu will-change-transform',
        className
      )}
      onClick={handleClick}
      whileHover={{ 
        scale: 1.05,
        boxShadow: '0 20px 40px rgba(79, 70, 229, 0.3)',
      }}
      whileTap={{ scale: 0.95 }}
      transition={springs.gentle}
      {...props}
    >
      <span className="relative z-10">{children}</span>
      
      {ripples.map(ripple => (
        <motion.span
          key={ripple.id}
          className="absolute pointer-events-none rounded-full"
          style={{
            left: ripple.x - ripple.size / 2,
            top: ripple.y - ripple.size / 2,
            width: ripple.size,
            height: ripple.size,
            backgroundColor: rippleColor,
          }}
          initial={{ scale: 0, opacity: 1 }}
          animate={{ scale: 1, opacity: 0 }}
          transition={{ duration: 0.8, ease: easings.gentle }}
        />
      ))}
    </motion.button>
  );
};

// === GLOW CARD ===
export interface GlowCardProps extends HTMLMotionProps<'div'> {
  glowColor?: string;
  glowIntensity?: number;
  children?: React.ReactNode;
}

export const GlowCard: React.FC<GlowCardProps> = ({
  glowColor = '#3B82F6',
  glowIntensity = 0.3,
  className,
  children,
  ...props
}) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const [isHovered, setIsHovered] = React.useState(false);

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    x.set(event.clientX - rect.left);
    y.set(event.clientY - rect.top);
  };

  const glowX = useTransform(x, value => `${value}px`);
  const glowY = useTransform(y, value => `${value}px`);

  return (
    <motion.div
      className={cn(
        'relative bg-white/5 backdrop-blur-lg rounded-2xl border border-white/10',
        'shadow-xl hover:shadow-2xl transition-all duration-500 group overflow-hidden',
        'transform-gpu will-change-transform',
        className
      )}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ scale: 1.02 }}
      transition={springs.gentle}
      {...props}
    >
      {/* Dynamic glow following mouse */}
      <motion.div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-2xl"
        style={{
          background: isHovered 
            ? `radial-gradient(circle 120px at ${glowX} ${glowY}, ${glowColor}${Math.floor(glowIntensity * 255).toString(16).padStart(2, '0')}, transparent)`
            : 'transparent',
        }}
      />
      
      {/* Border glow */}
      <motion.div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-50 pointer-events-none"
        style={{
          boxShadow: `inset 0 0 20px ${glowColor}40, 0 0 20px ${glowColor}20`,
        }}
        initial={{ opacity: 0 }}
        whileHover={{ opacity: 0.5 }}
        transition={{ duration: 0.3 }}
      />
      
      <div className="relative z-10 p-6">
        {children}
      </div>
    </motion.div>
  );
};

// === FLOATING ACTION BUTTON ===
export interface FloatingActionButtonProps extends HTMLMotionProps<'button'> {
  icon?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
  children?: React.ReactNode;
}

const fabSizes = {
  sm: 'w-12 h-12 text-sm',
  md: 'w-16 h-16 text-base',
  lg: 'w-20 h-20 text-lg',
};

const fabPositions = {
  'bottom-right': 'fixed bottom-6 right-6',
  'bottom-left': 'fixed bottom-6 left-6',
  'top-right': 'fixed top-6 right-6',
  'top-left': 'fixed top-6 left-6',
};

export const FloatingActionButton: React.FC<FloatingActionButtonProps> = ({
  icon,
  size = 'md',
  position = 'bottom-right',
  className,
  children,
  ...props
}) => {
  return (
    <motion.button
      className={cn(
        'bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full',
        'shadow-2xl hover:shadow-purple-500/25 transition-shadow duration-300',
        'flex items-center justify-center font-semibold z-50',
        'transform-gpu will-change-transform',
        fabSizes[size],
        fabPositions[position],
        className
      )}
      whileHover={{ 
        scale: 1.1,
        rotate: 5,
        boxShadow: '0 20px 40px rgba(147, 51, 234, 0.4)',
      }}
      whileTap={{ scale: 0.9 }}
      initial={{ scale: 0, rotate: -180 }}
      animate={{ scale: 1, rotate: 0 }}
      transition={springs.bouncy}
      {...props}
    >
      <motion.div
        whileHover={{ scale: 1.1 }}
        transition={springs.gentle}
      >
        {icon || children}
      </motion.div>
      
      {/* Pulse effect */}
      <motion.div
        className="absolute inset-0 rounded-full border-2 border-white/30"
        animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
    </motion.button>
  );
};

// === SLIDING PANEL ===
export interface SlidingPanelProps {
  isOpen: boolean;
  onClose: () => void;
  direction?: 'left' | 'right' | 'top' | 'bottom';
  size?: 'sm' | 'md' | 'lg' | 'full';
  overlay?: boolean;
  blurBackground?: boolean;
  children?: React.ReactNode;
  className?: string;
}

const panelSizes = {
  sm: '320px',
  md: '480px',
  lg: '640px',
  full: '100%',
};

const panelDirections = {
  left: {
    initial: { x: '-100%' },
    animate: { x: 0 },
    exit: { x: '-100%' },
    className: 'left-0 top-0 h-full border-r',
  },
  right: {
    initial: { x: '100%' },
    animate: { x: 0 },
    exit: { x: '100%' },
    className: 'right-0 top-0 h-full border-l',
  },
  top: {
    initial: { y: '-100%' },
    animate: { y: 0 },
    exit: { y: '-100%' },
    className: 'top-0 left-0 w-full border-b',
  },
  bottom: {
    initial: { y: '100%' },
    animate: { y: 0 },
    exit: { y: '100%' },
    className: 'bottom-0 left-0 w-full border-t',
  },
};

export const SlidingPanel: React.FC<SlidingPanelProps> = ({
  isOpen,
  onClose,
  direction = 'right',
  size = 'md',
  overlay = true,
  blurBackground = true,
  children,
  className,
}) => {
  const panelConfig = panelDirections[direction];
  const isVertical = direction === 'top' || direction === 'bottom';
  const sizeStyle = isVertical 
    ? { height: panelSizes[size] }
    : { width: panelSizes[size] };

  React.useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50">
          {overlay && (
            <motion.div
              className={cn(
                'absolute inset-0 bg-black/50',
                blurBackground && 'backdrop-blur-md'
              )}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
          )}
          
          <motion.div
            className={cn(
              'absolute bg-white/10 backdrop-blur-xl border-white/20 shadow-2xl',
              panelConfig.className,
              className
            )}
            style={sizeStyle}
            variants={panelConfig}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={springs.gentle}
          >
            <div className="h-full overflow-y-auto p-6">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

// === MORPHING BUTTON ===
export interface MorphingButtonProps extends HTMLMotionProps<'button'> {
  morphTo?: 'loading' | 'success' | 'error';
  children?: React.ReactNode;
}

export const MorphingButton: React.FC<MorphingButtonProps> = ({
  morphTo,
  className,
  children,
  ...props
}) => {
  const variants = {
    default: {
      width: 'auto',
      borderRadius: '12px',
      backgroundColor: '#3B82F6',
    },
    loading: {
      width: '48px',
      borderRadius: '50%',
      backgroundColor: '#6366F1',
    },
    success: {
      width: '48px',
      borderRadius: '50%',
      backgroundColor: '#10B981',
    },
    error: {
      width: '48px',
      borderRadius: '50%',
      backgroundColor: '#EF4444',
    },
  };

  const iconVariants = {
    default: { opacity: 0, scale: 0 },
    loading: { opacity: 1, scale: 1 },
    success: { opacity: 1, scale: 1 },
    error: { opacity: 1, scale: 1 },
  };

  const textVariants = {
    default: { opacity: 1, scale: 1 },
    loading: { opacity: 0, scale: 0 },
    success: { opacity: 0, scale: 0 },
    error: { opacity: 0, scale: 0 },
  };

  const renderIcon = () => {
    switch (morphTo) {
      case 'loading':
        return (
          <motion.div
            className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
        );
      case 'success':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <motion.path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={3}
              d="M5 13l4 4L19 7"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.6, ease: easings.gentle }}
            />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <motion.path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={3}
              d="M6 18L18 6M6 6l12 12"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.6, ease: easings.gentle }}
            />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <motion.button
      className={cn(
        'px-8 py-4 text-white font-semibold relative flex items-center justify-center overflow-hidden',
        'shadow-lg hover:shadow-xl transition-shadow duration-300 min-h-[48px]',
        'transform-gpu will-change-transform',
        className
      )}
      variants={variants}
      initial="default"
      animate={morphTo || 'default'}
      transition={springs.gentle}
      whileHover={!morphTo ? { scale: 1.05 } : undefined}
      whileTap={!morphTo ? { scale: 0.95 } : undefined}
      {...props}
    >
      <motion.span
        variants={textVariants}
        initial="default"
        animate={morphTo || 'default'}
        className="flex items-center gap-2"
      >
        {children}
      </motion.span>
      
      <motion.div
        variants={iconVariants}
        initial="default"
        animate={morphTo || 'default'}
        className="absolute inset-0 flex items-center justify-center"
      >
        {renderIcon()}
      </motion.div>
    </motion.button>
  );
};

// === PREMIUM COMPOSITE COMPONENTS ===
export const InteractiveDemoCard: React.FC<{ 
  children: React.ReactNode;
  className?: string;
}> = ({ children, className }) => (
  <TiltCard intensity={12} className={className}>
    <GlowCard glowColor="#8B5CF6" glowIntensity={0.25}>
      {children}
    </GlowCard>
  </TiltCard>
);

export const PremiumActionButton: React.FC<{ 
  children: React.ReactNode; 
  onClick?: () => void;
  className?: string;
}> = ({ children, onClick, className }) => (
  <RippleButton onClick={onClick} className={className}>
    <MagneticButton strength={0.3} magneticRange={80}>
      {children}
    </MagneticButton>
  </RippleButton>
);

// === GLASSMORPHISM UTILITIES ===
export const glassmorphismStyles = {
  light: 'bg-white/10 backdrop-blur-md border border-white/20',
  medium: 'bg-white/5 backdrop-blur-lg border border-white/10',
  heavy: 'bg-white/15 backdrop-blur-xl border border-white/25',
  dark: 'bg-black/10 backdrop-blur-md border border-white/10',
};

export const GlassmorphismCard: React.FC<{
  children: React.ReactNode;
  variant?: keyof typeof glassmorphismStyles;
  className?: string;
}> = ({ children, variant = 'medium', className }) => (
  <div className={cn(
    glassmorphismStyles[variant],
    'rounded-2xl shadow-xl',
    className
  )}>
    {children}
  </div>
);