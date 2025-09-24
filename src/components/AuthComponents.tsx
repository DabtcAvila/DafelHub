'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from './hooks/useAuth';
import { useAPI } from './hooks/useAPI';
import { 
  validateForm, 
  checkPasswordStrength, 
  VALIDATION_SCHEMAS, 
  getFieldError, 
  hasFieldError 
} from './utils/validation';
import { 
  MagneticButton, 
  RippleButton, 
  TiltCard, 
  GlowCard, 
  MorphingButton 
} from './InteractiveElements';

// Types
interface LoginFormData {
  username: string;
  password: string;
  mfa_code?: string;
  remember_me?: boolean;
}

interface RegisterFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  full_name: string;
  company?: string;
  phone?: string;
  terms: boolean;
}

interface MFASetupData {
  phone: string;
  backup_codes: string[];
}

// Utility function
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Animation variants
const formVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 }
};

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0
  }),
  center: {
    zIndex: 1,
    x: 0,
    opacity: 1
  },
  exit: (direction: number) => ({
    zIndex: 0,
    x: direction < 0 ? 300 : -300,
    opacity: 0
  })
};

// Form Input Component
const FormInput: React.FC<{
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
  disabled?: boolean;
  icon?: React.ReactNode;
}> = ({ 
  label, 
  type = 'text', 
  value, 
  onChange, 
  error, 
  placeholder, 
  required, 
  autoComplete,
  disabled,
  icon 
}) => {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <div className="h-5 w-5 text-gray-400">
              {icon}
            </div>
          </div>
        )}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          className={cn(
            'block w-full rounded-lg border-gray-300 shadow-sm transition-all duration-200',
            'focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20',
            'disabled:bg-gray-100 disabled:cursor-not-allowed',
            'dark:bg-gray-800 dark:border-gray-600 dark:text-white',
            'dark:focus:border-blue-400 dark:focus:ring-blue-400/20',
            icon ? 'pl-10' : 'pl-4',
            'pr-4 py-3',
            error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''
          )}
        />
      </div>
      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="text-sm text-red-600 dark:text-red-400"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
};

// Password Strength Indicator
const PasswordStrengthIndicator: React.FC<{ password: string }> = ({ password }) => {
  const strength = checkPasswordStrength(password);
  
  const strengthColors = {
    weak: 'bg-red-500',
    fair: 'bg-orange-500', 
    good: 'bg-yellow-500',
    strong: 'bg-green-500'
  };

  const strengthWidth = {
    weak: '25%',
    fair: '50%',
    good: '75%', 
    strong: '100%'
  };

  if (!password) return null;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-600 dark:text-gray-400">Password strength</span>
        <span className={cn(
          'text-sm font-medium capitalize',
          strength.strength === 'weak' && 'text-red-600',
          strength.strength === 'fair' && 'text-orange-600',
          strength.strength === 'good' && 'text-yellow-600',
          strength.strength === 'strong' && 'text-green-600'
        )}>
          {strength.strength}
        </span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <motion.div
          className={cn('h-2 rounded-full transition-all duration-300', strengthColors[strength.strength])}
          style={{ width: strengthWidth[strength.strength] }}
          initial={{ width: 0 }}
          animate={{ width: strengthWidth[strength.strength] }}
        />
      </div>
      {strength.feedback.length > 0 && (
        <ul className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          {strength.feedback.map((feedback, index) => (
            <li key={index} className="flex items-center space-x-2">
              <span className="w-1 h-1 bg-gray-400 rounded-full"></span>
              <span>{feedback}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

// Login Form Component
export const LoginForm: React.FC<{
  onSuccess?: () => void;
  onSwitchToRegister?: () => void;
}> = ({ onSuccess, onSwitchToRegister }) => {
  const { login, isLoading, error, clearError, requiresMfa, mfaMethods } = useAuth();
  
  const [formData, setFormData] = useState<LoginFormData>({
    username: '',
    password: '',
    mfa_code: '',
    remember_me: false
  });
  
  const [formErrors, setFormErrors] = useState<any>([]);
  const [showMFA, setShowMFA] = useState(false);

  // Clear errors when form data changes
  useEffect(() => {
    if (error) clearError();
    setFormErrors([]);
  }, [formData.username, formData.password, clearError, error]);

  // Handle MFA requirement
  useEffect(() => {
    setShowMFA(requiresMfa);
  }, [requiresMfa]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate form
    const validation = validateForm(formData, VALIDATION_SCHEMAS.LOGIN);
    if (!validation.isValid) {
      setFormErrors(validation.errors);
      return;
    }

    const success = await login({
      username: formData.username,
      password: formData.password,
      mfa_code: formData.mfa_code
    });

    if (success) {
      onSuccess?.();
    }
  };

  const updateField = (field: keyof LoginFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <TiltCard className="max-w-md mx-auto">
      <GlowCard glowColor="#3B82F6">
        <div className="p-8">
          <motion.div
            variants={formVariants}
            initial="hidden"
            animate="visible"
            className="space-y-6"
          >
            <div className="text-center">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
                Welcome Back
              </h2>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Sign in to your DafelHub account
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <FormInput
                label="Username or Email"
                value={formData.username}
                onChange={(value) => updateField('username', value)}
                error={getFieldError(formErrors, 'username')}
                placeholder="Enter your username or email"
                required
                autoComplete="username"
                disabled={isLoading}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                }
              />

              <FormInput
                label="Password"
                type="password"
                value={formData.password}
                onChange={(value) => updateField('password', value)}
                error={getFieldError(formErrors, 'password')}
                placeholder="Enter your password"
                required
                autoComplete="current-password"
                disabled={isLoading}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                }
              />

              <AnimatePresence>
                {showMFA && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <FormInput
                      label="MFA Code"
                      value={formData.mfa_code || ''}
                      onChange={(value) => updateField('mfa_code', value)}
                      error={getFieldError(formErrors, 'mfa_code')}
                      placeholder="Enter 6-digit code"
                      disabled={isLoading}
                      icon={
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      }
                    />
                    {mfaMethods.length > 0 && (
                      <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        Available methods: {mfaMethods.join(', ')}
                      </p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex items-center justify-between">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.remember_me || false}
                    onChange={(e) => updateField('remember_me', e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    disabled={isLoading}
                  />
                  <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                    Remember me
                  </span>
                </label>
                
                <button
                  type="button"
                  className="text-sm text-blue-600 hover:text-blue-500 dark:text-blue-400"
                  disabled={isLoading}
                >
                  Forgot password?
                </button>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
                >
                  <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                </motion.div>
              )}

              <MorphingButton
                type="submit"
                morphTo={isLoading ? 'loading' : undefined}
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              >
                {showMFA ? 'Verify & Sign In' : 'Sign In'}
              </MorphingButton>
            </form>

            <div className="text-center">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Don't have an account?{' '}
                <button
                  onClick={onSwitchToRegister}
                  className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
                  disabled={isLoading}
                >
                  Sign up
                </button>
              </span>
            </div>
          </motion.div>
        </div>
      </GlowCard>
    </TiltCard>
  );
};

// Register Form Component
export const RegisterForm: React.FC<{
  onSuccess?: () => void;
  onSwitchToLogin?: () => void;
}> = ({ onSuccess, onSwitchToLogin }) => {
  const { register, isLoading, error, clearError } = useAuth();
  
  const [formData, setFormData] = useState<RegisterFormData>({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    company: '',
    phone: '',
    terms: false
  });
  
  const [formErrors, setFormErrors] = useState<any>([]);

  // Clear errors when form data changes
  useEffect(() => {
    if (error) clearError();
    setFormErrors([]);
  }, [formData, clearError, error]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate form
    const validation = validateForm(formData, {
      ...VALIDATION_SCHEMAS.REGISTER,
      confirmPassword: {
        required: true,
        custom: (value: string) => {
          if (value !== formData.password) {
            return 'Passwords do not match';
          }
          return null;
        }
      }
    });

    if (!validation.isValid) {
      setFormErrors(validation.errors);
      return;
    }

    const success = await register({
      username: formData.username,
      email: formData.email,
      password: formData.password,
      full_name: formData.full_name,
      company: formData.company,
      phone: formData.phone
    });

    if (success) {
      onSuccess?.();
    }
  };

  const updateField = (field: keyof RegisterFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <TiltCard className="max-w-md mx-auto">
      <GlowCard glowColor="#10B981">
        <div className="p-8">
          <motion.div
            variants={formVariants}
            initial="hidden"
            animate="visible"
            className="space-y-6"
          >
            <div className="text-center">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
                Join DafelHub
              </h2>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Create your account to get started
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <FormInput
                label="Username"
                value={formData.username}
                onChange={(value) => updateField('username', value)}
                error={getFieldError(formErrors, 'username')}
                placeholder="Choose a username"
                required
                autoComplete="username"
                disabled={isLoading}
              />

              <FormInput
                label="Email"
                type="email"
                value={formData.email}
                onChange={(value) => updateField('email', value)}
                error={getFieldError(formErrors, 'email')}
                placeholder="Enter your email"
                required
                autoComplete="email"
                disabled={isLoading}
              />

              <FormInput
                label="Full Name"
                value={formData.full_name}
                onChange={(value) => updateField('full_name', value)}
                error={getFieldError(formErrors, 'full_name')}
                placeholder="Enter your full name"
                required
                autoComplete="name"
                disabled={isLoading}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormInput
                  label="Company"
                  value={formData.company || ''}
                  onChange={(value) => updateField('company', value)}
                  error={getFieldError(formErrors, 'company')}
                  placeholder="Optional"
                  autoComplete="organization"
                  disabled={isLoading}
                />

                <FormInput
                  label="Phone"
                  type="tel"
                  value={formData.phone || ''}
                  onChange={(value) => updateField('phone', value)}
                  error={getFieldError(formErrors, 'phone')}
                  placeholder="Optional"
                  autoComplete="tel"
                  disabled={isLoading}
                />
              </div>

              <FormInput
                label="Password"
                type="password"
                value={formData.password}
                onChange={(value) => updateField('password', value)}
                error={getFieldError(formErrors, 'password')}
                placeholder="Create a strong password"
                required
                autoComplete="new-password"
                disabled={isLoading}
              />

              {formData.password && (
                <PasswordStrengthIndicator password={formData.password} />
              )}

              <FormInput
                label="Confirm Password"
                type="password"
                value={formData.confirmPassword}
                onChange={(value) => updateField('confirmPassword', value)}
                error={getFieldError(formErrors, 'confirmPassword')}
                placeholder="Confirm your password"
                required
                autoComplete="new-password"
                disabled={isLoading}
              />

              <div className="flex items-start">
                <input
                  type="checkbox"
                  checked={formData.terms}
                  onChange={(e) => updateField('terms', e.target.checked)}
                  className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  disabled={isLoading}
                  required
                />
                <div className="ml-3">
                  <label className="text-sm text-gray-700 dark:text-gray-300">
                    I agree to the{' '}
                    <a href="#" className="text-blue-600 hover:text-blue-500 dark:text-blue-400">
                      Terms of Service
                    </a>{' '}
                    and{' '}
                    <a href="#" className="text-blue-600 hover:text-blue-500 dark:text-blue-400">
                      Privacy Policy
                    </a>
                  </label>
                  {hasFieldError(formErrors, 'terms') && (
                    <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                      {getFieldError(formErrors, 'terms')}
                    </p>
                  )}
                </div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
                >
                  <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                </motion.div>
              )}

              <MorphingButton
                type="submit"
                morphTo={isLoading ? 'loading' : undefined}
                disabled={isLoading || !formData.terms}
                className="w-full bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700"
              >
                Create Account
              </MorphingButton>
            </form>

            <div className="text-center">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Already have an account?{' '}
                <button
                  onClick={onSwitchToLogin}
                  className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
                  disabled={isLoading}
                >
                  Sign in
                </button>
              </span>
            </div>
          </motion.div>
        </div>
      </GlowCard>
    </TiltCard>
  );
};

// MFA Setup Component
export const MFASetup: React.FC<{
  onComplete?: () => void;
  onSkip?: () => void;
}> = ({ onComplete, onSkip }) => {
  const { post } = useAPI();
  const [step, setStep] = useState<'phone' | 'qr' | 'verify' | 'backup'>('phone');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [setupData, setSetupData] = useState<{
    phone: string;
    qr_code?: string;
    secret?: string;
    verification_code: string;
    backup_codes: string[];
  }>({
    phone: '',
    verification_code: '',
    backup_codes: []
  });

  const handlePhoneSubmit = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await post('/auth/mfa/setup/phone', { phone: setupData.phone });
      if (response.success) {
        setSetupData(prev => ({ 
          ...prev, 
          qr_code: response.data.qr_code,
          secret: response.data.secret 
        }));
        setStep('qr');
      } else {
        setError(response.error?.message || 'Failed to setup MFA');
      }
    } catch (error) {
      setError('Network error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerification = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await post('/auth/mfa/verify', {
        verification_code: setupData.verification_code
      });
      
      if (response.success) {
        setSetupData(prev => ({ 
          ...prev, 
          backup_codes: response.data.backup_codes 
        }));
        setStep('backup');
      } else {
        setError('Invalid verification code');
      }
    } catch (error) {
      setError('Verification failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleComplete = async () => {
    await post('/auth/mfa/setup/complete');
    onComplete?.();
  };

  const renderStepContent = () => {
    switch (step) {
      case 'phone':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Setup Two-Factor Authentication
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Add an extra layer of security to your account
              </p>
            </div>
            
            <FormInput
              label="Phone Number"
              type="tel"
              value={setupData.phone}
              onChange={(value) => setSetupData(prev => ({ ...prev, phone: value }))}
              placeholder="+1 234 567 8900"
              required
              disabled={isLoading}
            />
            
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}
            
            <div className="flex space-x-3">
              <RippleButton
                onClick={handlePhoneSubmit}
                disabled={isLoading || !setupData.phone}
                className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600"
              >
                {isLoading ? 'Setting up...' : 'Continue'}
              </RippleButton>
              
              <button
                onClick={onSkip}
                className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                disabled={isLoading}
              >
                Skip for now
              </button>
            </div>
          </div>
        );

      case 'qr':
        return (
          <div className="space-y-6 text-center">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Scan QR Code
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Use your authenticator app to scan this QR code
              </p>
            </div>
            
            {setupData.qr_code && (
              <div className="flex justify-center">
                <div className="p-4 bg-white rounded-lg shadow-lg">
                  <img 
                    src={setupData.qr_code} 
                    alt="MFA QR Code" 
                    className="w-48 h-48"
                  />
                </div>
              </div>
            )}
            
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Manual entry key:
              </p>
              <code className="text-xs font-mono bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded">
                {setupData.secret}
              </code>
            </div>
            
            <RippleButton
              onClick={() => setStep('verify')}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
            >
              I've added the account
            </RippleButton>
          </div>
        );

      case 'verify':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Verify Setup
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Enter the 6-digit code from your authenticator app
              </p>
            </div>
            
            <FormInput
              label="Verification Code"
              value={setupData.verification_code}
              onChange={(value) => setSetupData(prev => ({ ...prev, verification_code: value }))}
              placeholder="000000"
              required
              disabled={isLoading}
            />
            
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}
            
            <RippleButton
              onClick={handleVerification}
              disabled={isLoading || setupData.verification_code.length !== 6}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
            >
              {isLoading ? 'Verifying...' : 'Verify'}
            </RippleButton>
          </div>
        );

      case 'backup':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Save Your Backup Codes
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Store these codes in a safe place. You can use them to access your account if you lose your device.
              </p>
            </div>
            
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="grid grid-cols-2 gap-2 text-center">
                {setupData.backup_codes.map((code, index) => (
                  <code 
                    key={index}
                    className="text-sm font-mono bg-white dark:bg-gray-900 px-3 py-2 rounded border"
                  >
                    {code}
                  </code>
                ))}
              </div>
            </div>
            
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <p className="text-sm text-yellow-800 dark:text-yellow-300">
                ⚠️ Keep these codes secure. Each code can only be used once.
              </p>
            </div>
            
            <RippleButton
              onClick={handleComplete}
              className="w-full bg-gradient-to-r from-green-600 to-blue-600"
            >
              Complete Setup
            </RippleButton>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <TiltCard className="max-w-md mx-auto">
      <GlowCard glowColor="#8B5CF6">
        <div className="p-8">
          <motion.div
            variants={formVariants}
            initial="hidden"
            animate="visible"
          >
            {renderStepContent()}
          </motion.div>
        </div>
      </GlowCard>
    </TiltCard>
  );
};

// Combined Auth Component with state management
export const AuthContainer: React.FC = () => {
  const [currentView, setCurrentView] = useState<'login' | 'register' | 'mfa'>('login');
  const [[page, direction], setPage] = useState([0, 0]);

  const paginate = (newPage: number) => {
    setPage([newPage, newPage > page ? 1 : -1]);
  };

  const switchToLogin = () => {
    setCurrentView('login');
    paginate(0);
  };

  const switchToRegister = () => {
    setCurrentView('register'); 
    paginate(1);
  };

  const switchToMFA = () => {
    setCurrentView('mfa');
    paginate(2);
  };

  const handleAuthSuccess = () => {
    // Redirect or handle success
    console.log('Authentication successful!');
  };

  const views = {
    login: (
      <LoginForm
        onSuccess={handleAuthSuccess}
        onSwitchToRegister={switchToRegister}
      />
    ),
    register: (
      <RegisterForm
        onSuccess={switchToMFA}
        onSwitchToLogin={switchToLogin}
      />
    ),
    mfa: (
      <MFASetup
        onComplete={handleAuthSuccess}
        onSkip={handleAuthSuccess}
      />
    ),
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-purple-900 p-4">
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentView}
          custom={direction}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{
            x: { type: "spring", stiffness: 300, damping: 30 },
            opacity: { duration: 0.2 }
          }}
          className="w-full"
        >
          {views[currentView]}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};

export default AuthContainer;