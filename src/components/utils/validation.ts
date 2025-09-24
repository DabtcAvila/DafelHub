'use client';

// Validation utilities for DafelHub forms and data

// Types
export interface ValidationRule {
  required?: boolean;
  min?: number;
  max?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: RegExp;
  email?: boolean;
  url?: boolean;
  phone?: boolean;
  strongPassword?: boolean;
  custom?: (value: any) => string | null;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  values: Record<string, any>;
}

// Common validation patterns
export const VALIDATION_PATTERNS = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PHONE: /^[\+]?[1-9][\d]{0,15}$/,
  URL: /^https?:\/\/.+\..+/,
  USERNAME: /^[a-zA-Z0-9_-]{3,20}$/,
  PASSWORD_STRONG: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
  ALPHANUMERIC: /^[a-zA-Z0-9]+$/,
  ALPHA: /^[a-zA-Z]+$/,
  NUMERIC: /^[0-9]+$/,
  SLUG: /^[a-z0-9-]+$/,
  HEX_COLOR: /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/,
  IPV4: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
  JWT_TOKEN: /^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]*$/,
};

// Error messages
export const ERROR_MESSAGES = {
  REQUIRED: 'This field is required',
  EMAIL: 'Please enter a valid email address',
  PHONE: 'Please enter a valid phone number',
  URL: 'Please enter a valid URL',
  USERNAME: 'Username must be 3-20 characters long and contain only letters, numbers, underscore, or dash',
  PASSWORD_WEAK: 'Password must contain at least 8 characters, including uppercase, lowercase, number, and special character',
  TOO_SHORT: (min: number) => `Must be at least ${min} characters long`,
  TOO_LONG: (max: number) => `Must be no more than ${max} characters long`,
  TOO_SMALL: (min: number) => `Must be at least ${min}`,
  TOO_LARGE: (max: number) => `Must be no more than ${max}`,
  INVALID_FORMAT: 'Invalid format',
  PASSWORDS_DONT_MATCH: 'Passwords do not match',
  TERMS_REQUIRED: 'You must agree to the terms and conditions',
};

// Single field validator
export const validateField = (
  value: any,
  rules: ValidationRule,
  fieldName: string = 'field'
): ValidationError | null => {
  const stringValue = String(value || '').trim();

  // Required validation
  if (rules.required && (!value || stringValue === '')) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.REQUIRED,
      code: 'REQUIRED',
    };
  }

  // Skip other validations if value is empty and not required
  if (!value || stringValue === '') {
    return null;
  }

  // Min/Max for numbers
  if (typeof value === 'number') {
    if (rules.min !== undefined && value < rules.min) {
      return {
        field: fieldName,
        message: ERROR_MESSAGES.TOO_SMALL(rules.min),
        code: 'TOO_SMALL',
      };
    }
    if (rules.max !== undefined && value > rules.max) {
      return {
        field: fieldName,
        message: ERROR_MESSAGES.TOO_LARGE(rules.max),
        code: 'TOO_LARGE',
      };
    }
  }

  // Length validation for strings
  if (typeof value === 'string') {
    if (rules.minLength !== undefined && stringValue.length < rules.minLength) {
      return {
        field: fieldName,
        message: ERROR_MESSAGES.TOO_SHORT(rules.minLength),
        code: 'TOO_SHORT',
      };
    }
    if (rules.maxLength !== undefined && stringValue.length > rules.maxLength) {
      return {
        field: fieldName,
        message: ERROR_MESSAGES.TOO_LONG(rules.maxLength),
        code: 'TOO_LONG',
      };
    }
  }

  // Email validation
  if (rules.email && !VALIDATION_PATTERNS.EMAIL.test(stringValue)) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.EMAIL,
      code: 'INVALID_EMAIL',
    };
  }

  // URL validation
  if (rules.url && !VALIDATION_PATTERNS.URL.test(stringValue)) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.URL,
      code: 'INVALID_URL',
    };
  }

  // Phone validation
  if (rules.phone && !VALIDATION_PATTERNS.PHONE.test(stringValue)) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.PHONE,
      code: 'INVALID_PHONE',
    };
  }

  // Strong password validation
  if (rules.strongPassword && !VALIDATION_PATTERNS.PASSWORD_STRONG.test(stringValue)) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.PASSWORD_WEAK,
      code: 'WEAK_PASSWORD',
    };
  }

  // Pattern validation
  if (rules.pattern && !rules.pattern.test(stringValue)) {
    return {
      field: fieldName,
      message: ERROR_MESSAGES.INVALID_FORMAT,
      code: 'INVALID_FORMAT',
    };
  }

  // Custom validation
  if (rules.custom) {
    const customError = rules.custom(value);
    if (customError) {
      return {
        field: fieldName,
        message: customError,
        code: 'CUSTOM_ERROR',
      };
    }
  }

  return null;
};

// Multiple fields validator
export const validateForm = (
  values: Record<string, any>,
  rules: Record<string, ValidationRule>
): ValidationResult => {
  const errors: ValidationError[] = [];
  const cleanValues: Record<string, any> = {};

  // Validate each field
  Object.entries(rules).forEach(([fieldName, fieldRules]) => {
    const value = values[fieldName];
    const error = validateField(value, fieldRules, fieldName);
    
    if (error) {
      errors.push(error);
    }

    // Clean and store the value
    if (typeof value === 'string') {
      cleanValues[fieldName] = value.trim();
    } else {
      cleanValues[fieldName] = value;
    }
  });

  return {
    isValid: errors.length === 0,
    errors,
    values: cleanValues,
  };
};

// Predefined validation schemas
export const VALIDATION_SCHEMAS = {
  LOGIN: {
    username: {
      required: true,
      minLength: 3,
      maxLength: 50,
    },
    password: {
      required: true,
      minLength: 1,
    },
    mfa_code: {
      pattern: /^[0-9]{6}$/,
    },
  },

  REGISTER: {
    username: {
      required: true,
      pattern: VALIDATION_PATTERNS.USERNAME,
    },
    email: {
      required: true,
      email: true,
    },
    password: {
      required: true,
      strongPassword: true,
    },
    confirmPassword: {
      required: true,
      custom: (value: string, values: Record<string, any>) => {
        if (value !== values?.password) {
          return ERROR_MESSAGES.PASSWORDS_DONT_MATCH;
        }
        return null;
      },
    },
    full_name: {
      required: true,
      minLength: 2,
      maxLength: 100,
    },
    company: {
      maxLength: 100,
    },
    phone: {
      phone: true,
    },
    terms: {
      required: true,
      custom: (value: boolean) => {
        if (!value) {
          return ERROR_MESSAGES.TERMS_REQUIRED;
        }
        return null;
      },
    },
  },

  USER_PROFILE: {
    full_name: {
      required: true,
      minLength: 2,
      maxLength: 100,
    },
    email: {
      required: true,
      email: true,
    },
    phone: {
      phone: true,
    },
    company: {
      maxLength: 100,
    },
    avatar_url: {
      url: true,
    },
  },

  PROJECT: {
    name: {
      required: true,
      minLength: 3,
      maxLength: 100,
    },
    description: {
      maxLength: 500,
    },
    repository_url: {
      url: true,
    },
    framework: {
      required: true,
    },
    deployment_target: {
      required: true,
    },
  },

  CONNECTION: {
    name: {
      required: true,
      minLength: 3,
      maxLength: 100,
    },
    type: {
      required: true,
    },
    host: {
      required: true,
      maxLength: 255,
    },
    port: {
      required: true,
      min: 1,
      max: 65535,
    },
    database: {
      required: true,
      maxLength: 100,
    },
    username: {
      required: true,
      maxLength: 100,
    },
    password: {
      required: true,
    },
  },

  MFA_SETUP: {
    phone: {
      required: true,
      phone: true,
    },
    backup_codes: {
      required: true,
      custom: (value: string[]) => {
        if (!Array.isArray(value) || value.length !== 10) {
          return 'Please save all 10 backup codes';
        }
        return null;
      },
    },
  },
};

// Real-time validation hook utilities
export const createValidator = (schema: Record<string, ValidationRule>) => {
  return {
    validate: (values: Record<string, any>) => validateForm(values, schema),
    validateField: (fieldName: string, value: any) => 
      validateField(value, schema[fieldName], fieldName),
    schema,
  };
};

// Password strength checker
export const checkPasswordStrength = (password: string): {
  score: number;
  feedback: string[];
  strength: 'weak' | 'fair' | 'good' | 'strong';
} => {
  const feedback: string[] = [];
  let score = 0;

  if (!password) {
    return { score: 0, feedback: ['Password is required'], strength: 'weak' };
  }

  // Length check
  if (password.length >= 8) {
    score += 1;
  } else {
    feedback.push('Use at least 8 characters');
  }

  // Uppercase check
  if (/[A-Z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Add uppercase letters');
  }

  // Lowercase check
  if (/[a-z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Add lowercase letters');
  }

  // Number check
  if (/\d/.test(password)) {
    score += 1;
  } else {
    feedback.push('Add numbers');
  }

  // Special character check
  if (/[@$!%*?&]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Add special characters (!@#$%^&*)');
  }

  // Length bonus
  if (password.length >= 12) {
    score += 1;
  }

  // Common patterns penalty
  if (/(.)\1{2,}/.test(password)) {
    score -= 1;
    feedback.push('Avoid repeating characters');
  }

  if (/123|abc|qwerty/i.test(password)) {
    score -= 1;
    feedback.push('Avoid common patterns');
  }

  // Determine strength
  let strength: 'weak' | 'fair' | 'good' | 'strong';
  if (score < 2) {
    strength = 'weak';
  } else if (score < 4) {
    strength = 'fair';
  } else if (score < 5) {
    strength = 'good';
  } else {
    strength = 'strong';
  }

  return { score: Math.max(0, Math.min(5, score)), feedback, strength };
};

// Form field helpers
export const getFieldError = (
  errors: ValidationError[],
  fieldName: string
): string | null => {
  const error = errors.find(e => e.field === fieldName);
  return error ? error.message : null;
};

export const hasFieldError = (
  errors: ValidationError[],
  fieldName: string
): boolean => {
  return errors.some(e => e.field === fieldName);
};

// Sanitization utilities
export const sanitizeInput = {
  string: (value: string): string => {
    return String(value || '').trim();
  },

  email: (value: string): string => {
    return String(value || '').trim().toLowerCase();
  },

  phone: (value: string): string => {
    return String(value || '').replace(/\D/g, '');
  },

  username: (value: string): string => {
    return String(value || '').trim().toLowerCase();
  },

  slug: (value: string): string => {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  },

  html: (value: string): string => {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  },
};

// File validation utilities
export const validateFile = (
  file: File,
  options: {
    maxSize?: number; // in bytes
    allowedTypes?: string[];
    allowedExtensions?: string[];
  } = {}
): ValidationError | null => {
  const { maxSize, allowedTypes, allowedExtensions } = options;

  // Size validation
  if (maxSize && file.size > maxSize) {
    const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(1);
    return {
      field: 'file',
      message: `File size must be less than ${maxSizeMB}MB`,
      code: 'FILE_TOO_LARGE',
    };
  }

  // Type validation
  if (allowedTypes && !allowedTypes.includes(file.type)) {
    return {
      field: 'file',
      message: `File type not allowed. Allowed types: ${allowedTypes.join(', ')}`,
      code: 'INVALID_FILE_TYPE',
    };
  }

  // Extension validation
  if (allowedExtensions) {
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    if (!fileExtension || !allowedExtensions.includes(fileExtension)) {
      return {
        field: 'file',
        message: `File extension not allowed. Allowed extensions: ${allowedExtensions.join(', ')}`,
        code: 'INVALID_FILE_EXTENSION',
      };
    }
  }

  return null;
};

export default {
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
};