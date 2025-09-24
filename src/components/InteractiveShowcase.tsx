'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
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
} from './InteractiveElements';
import { entranceAnimations, staggerAnimations } from '../lib/animations';

const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// === DEMO SECTION COMPONENT ===
const DemoSection: React.FC<{
  title: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}> = ({ title, description, children, className }) => (
  <motion.section
    className={cn('mb-16', className)}
    variants={entranceAnimations.slideUp}
    initial="initial"
    whileInView="animate"
    viewport={{ once: true, margin: '-100px' }}
  >
    <div className="text-center mb-8">
      <h2 className="text-3xl font-bold text-white mb-4">{title}</h2>
      <p className="text-gray-300 max-w-2xl mx-auto">{description}</p>
    </div>
    {children}
  </motion.section>
);

// === CODE PREVIEW COMPONENT ===
const CodePreview: React.FC<{
  code: string;
  language?: string;
}> = ({ code, language = 'tsx' }) => {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div className="mt-4">
      <button
        onClick={() => setIsVisible(!isVisible)}
        className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
      >
        {isVisible ? 'Hide Code' : 'Show Code'}
      </button>
      
      <AnimatePresence>
        {isVisible && (
          <motion.pre
            className="mt-4 p-4 bg-black/50 rounded-lg overflow-x-auto text-sm"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
          >
            <code className="text-gray-300">{code}</code>
          </motion.pre>
        )}
      </AnimatePresence>
    </div>
  );
};

// === MAIN SHOWCASE COMPONENT ===
export const InteractiveShowcase: React.FC<{ className?: string }> = ({ className }) => {
  const [panelOpen, setPanelOpen] = useState(false);
  const [morphingState, setMorphingState] = useState<'loading' | 'success' | 'error' | undefined>();

  const handleMorphingDemo = () => {
    setMorphingState('loading');
    setTimeout(() => {
      setMorphingState(Math.random() > 0.5 ? 'success' : 'error');
      setTimeout(() => setMorphingState(undefined), 2000);
    }, 2000);
  };

  return (
    <div className={cn('min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-blue-900 p-8', className)}>
      <motion.div
        className="max-w-7xl mx-auto"
        variants={staggerAnimations.container}
        initial="initial"
        animate="animate"
      >
        {/* Header */}
        <motion.header
          className="text-center mb-16"
          variants={entranceAnimations.fadeIn}
        >
          <h1 className="text-6xl font-bold text-white mb-6 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            Interactive Components
          </h1>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Enterprise-grade interactive component library with sophisticated animations, 
            premium effects, and exceptional user experience.
          </p>
        </motion.header>

        {/* Magnetic Button Demo */}
        <DemoSection
          title="Magnetic Button"
          description="Buttons that follow your cursor with smooth spring physics and magnetic attraction effects."
        >
          <div className="flex flex-wrap gap-6 justify-center">
            <MagneticButton strength={0.3} magneticRange={120}>
              Gentle Magnetic
            </MagneticButton>
            
            <MagneticButton 
              strength={0.6} 
              magneticRange={100}
              className="bg-gradient-to-r from-purple-600 to-pink-600"
            >
              Strong Magnetic
            </MagneticButton>
            
            <MagneticButton 
              strength={0.2} 
              magneticRange={150}
              className="bg-gradient-to-r from-green-600 to-blue-600"
            >
              Subtle Magnetic
            </MagneticButton>
          </div>
          
          <CodePreview code={`<MagneticButton strength={0.3} magneticRange={120}>
  Gentle Magnetic
</MagneticButton>`} />
        </DemoSection>

        {/* Tilt Card Demo */}
        <DemoSection
          title="3D Tilt Cards"
          description="Cards with realistic 3D tilt effects that respond to mouse movement with preserve-3d transforms."
        >
          <div className="grid md:grid-cols-3 gap-8">
            <TiltCard intensity={10} className="p-8 text-center">
              <h3 className="text-xl font-bold text-white mb-4">Subtle Tilt</h3>
              <p className="text-gray-300">Gentle 3D movement with low intensity for elegant interactions.</p>
            </TiltCard>
            
            <TiltCard intensity={20} className="p-8 text-center">
              <h3 className="text-xl font-bold text-white mb-4">Medium Tilt</h3>
              <p className="text-gray-300">Balanced tilt effect perfect for showcasing content cards.</p>
            </TiltCard>
            
            <TiltCard intensity={30} className="p-8 text-center">
              <h3 className="text-xl font-bold text-white mb-4">Strong Tilt</h3>
              <p className="text-gray-300">Dramatic 3D effect for attention-grabbing elements.</p>
            </TiltCard>
          </div>
          
          <CodePreview code={`<TiltCard intensity={20} className="p-8">
  <h3 className="text-xl font-bold">Card Title</h3>
  <p>Card content with 3D tilt effects</p>
</TiltCard>`} />
        </DemoSection>

        {/* Ripple Button Demo */}
        <DemoSection
          title="Ripple Buttons"
          description="Material Design inspired ripple effects with customizable colors and smooth animations."
        >
          <div className="flex flex-wrap gap-6 justify-center">
            <RippleButton>Default Ripple</RippleButton>
            
            <RippleButton 
              rippleColor="rgba(168, 85, 247, 0.4)"
              className="bg-gradient-to-r from-purple-600 to-indigo-600"
            >
              Purple Ripple
            </RippleButton>
            
            <RippleButton 
              rippleColor="rgba(34, 197, 94, 0.4)"
              className="bg-gradient-to-r from-emerald-600 to-green-600"
            >
              Green Ripple
            </RippleButton>
          </div>
          
          <CodePreview code={`<RippleButton rippleColor="rgba(168, 85, 247, 0.4)">
  Purple Ripple
</RippleButton>`} />
        </DemoSection>

        {/* Glow Card Demo */}
        <DemoSection
          title="Dynamic Glow Cards"
          description="Cards with dynamic glow effects that follow your cursor with customizable colors and intensity."
        >
          <div className="grid md:grid-cols-2 gap-8">
            <GlowCard glowColor="#3B82F6" glowIntensity={0.3} className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Blue Glow</h3>
              <p className="text-gray-300">
                Move your cursor over this card to see the dynamic blue glow effect 
                that follows your mouse movement.
              </p>
            </GlowCard>
            
            <GlowCard glowColor="#8B5CF6" glowIntensity={0.4} className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Purple Glow</h3>
              <p className="text-gray-300">
                This card features a more intense purple glow effect with 
                enhanced brightness and saturation.
              </p>
            </GlowCard>
            
            <GlowCard glowColor="#EC4899" glowIntensity={0.25} className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Pink Glow</h3>
              <p className="text-gray-300">
                Elegant pink glow with moderate intensity perfect for 
                premium user interfaces.
              </p>
            </GlowCard>
            
            <GlowCard glowColor="#10B981" glowIntensity={0.35} className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Emerald Glow</h3>
              <p className="text-gray-300">
                Vibrant emerald glow effect that creates an engaging 
                and modern visual experience.
              </p>
            </GlowCard>
          </div>
          
          <CodePreview code={`<GlowCard glowColor="#8B5CF6" glowIntensity={0.4}>
  <h3>Purple Glow</h3>
  <p>Dynamic glow that follows cursor movement</p>
</GlowCard>`} />
        </DemoSection>

        {/* Morphing Button Demo */}
        <DemoSection
          title="Morphing Button"
          description="Buttons that smoothly transform between different states with animated icons and shape changes."
        >
          <div className="text-center">
            <MorphingButton 
              morphTo={morphingState}
              onClick={handleMorphingDemo}
              className="mb-4"
            >
              {morphingState ? '' : 'Start Process'}
            </MorphingButton>
            
            <p className="text-gray-300 text-sm">
              Click the button to see it morph through loading, success, or error states
            </p>
          </div>
          
          <CodePreview code={`const [state, setState] = useState<'loading' | 'success' | 'error'>();

<MorphingButton morphTo={state} onClick={handleClick}>
  Start Process
</MorphingButton>`} />
        </DemoSection>

        {/* Sliding Panel Demo */}
        <DemoSection
          title="Sliding Panel"
          description="Smooth sliding panels with backdrop blur and customizable directions and sizes."
        >
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => setPanelOpen(true)}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Open Panel
            </button>
          </div>
          
          <CodePreview code={`const [isOpen, setIsOpen] = useState(false);

<SlidingPanel 
  isOpen={isOpen} 
  onClose={() => setIsOpen(false)}
  direction="right" 
  size="md"
>
  Panel content here
</SlidingPanel>`} />
        </DemoSection>

        {/* Premium Combinations */}
        <DemoSection
          title="Premium Combinations"
          description="Sophisticated composite components combining multiple effects for exceptional user experiences."
        >
          <div className="grid md:grid-cols-2 gap-8">
            <InteractiveDemoCard className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Interactive Demo Card</h3>
              <p className="text-gray-300 mb-6">
                Combines tilt effects with dynamic glow for a premium interaction experience.
              </p>
              
              <PremiumActionButton>
                Premium Action
              </PremiumActionButton>
            </InteractiveDemoCard>
            
            <GlassmorphismCard variant="heavy" className="p-8">
              <h3 className="text-xl font-bold text-white mb-4">Glassmorphism Card</h3>
              <p className="text-gray-300 mb-6">
                Modern glassmorphism effect with backdrop blur and subtle transparency.
              </p>
              
              <div className="flex gap-3">
                <button className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors">
                  Action 1
                </button>
                <button className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors">
                  Action 2
                </button>
              </div>
            </GlassmorphismCard>
          </div>
          
          <CodePreview code={`<InteractiveDemoCard>
  <h3>Interactive Demo Card</h3>
  <p>Combines tilt + glow effects</p>
  <PremiumActionButton>Action</PremiumActionButton>
</InteractiveDemoCard>`} />
        </DemoSection>

        {/* Floating Action Button */}
        <FloatingActionButton
          position="bottom-right"
          size="lg"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        >
          ↑
        </FloatingActionButton>
      </motion.div>

      {/* Sliding Panel */}
      <SlidingPanel
        isOpen={panelOpen}
        onClose={() => setPanelOpen(false)}
        direction="right"
        size="md"
      >
        <h2 className="text-2xl font-bold text-white mb-6">Sliding Panel</h2>
        <p className="text-gray-300 mb-6">
          This is a sliding panel with smooth animations and backdrop blur effects. 
          It can slide from any direction and has multiple size options.
        </p>
        
        <div className="space-y-4">
          <div className="p-4 bg-white/10 rounded-lg">
            <h3 className="font-semibold text-white mb-2">Feature 1</h3>
            <p className="text-gray-300 text-sm">Smooth sliding animations</p>
          </div>
          
          <div className="p-4 bg-white/10 rounded-lg">
            <h3 className="font-semibold text-white mb-2">Feature 2</h3>
            <p className="text-gray-300 text-sm">Backdrop blur effects</p>
          </div>
          
          <div className="p-4 bg-white/10 rounded-lg">
            <h3 className="font-semibold text-white mb-2">Feature 3</h3>
            <p className="text-gray-300 text-sm">Customizable directions</p>
          </div>
        </div>
        
        <button
          onClick={() => setPanelOpen(false)}
          className="mt-6 w-full py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Close Panel
        </button>
      </SlidingPanel>
    </div>
  );
};