'use client';

// API utility functions for DafelHub

// Types
export interface APIError {
  message: string;
  code?: string;
  status?: number;
  details?: any;
}

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: APIError;
  pagination?: {
    total: number;
    page: number;
    limit: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
}

// API Configuration
export const API_CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  TIMEOUT: 30000, // 30 seconds
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 second
};

// Storage keys
export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'dafelhub_access_token',
  REFRESH_TOKEN: 'dafelhub_refresh_token',
  USER_PREFERENCES: 'dafelhub_user_preferences',
  THEME: 'dafelhub_theme',
};

// Token management utilities
export const tokenUtils = {
  get: (key: keyof typeof STORAGE_KEYS): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEYS[key]);
  },

  set: (key: keyof typeof STORAGE_KEYS, value: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEYS[key], value);
  },

  remove: (key: keyof typeof STORAGE_KEYS): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(STORAGE_KEYS[key]);
  },

  clear: (): void => {
    if (typeof window === 'undefined') return;
    Object.values(STORAGE_KEYS).forEach(key => {
      localStorage.removeItem(key);
    });
  },

  isExpired: (token: string): boolean => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 < Date.now();
    } catch {
      return true;
    }
  },

  getTokenData: (token: string): any => {
    try {
      return JSON.parse(atob(token.split('.')[1]));
    } catch {
      return null;
    }
  },
};

// Request interceptor for adding auth headers and handling errors
export const createRequestInterceptor = (getToken: () => string | null) => {
  return async (url: string, options: RequestInit = {}): Promise<Response> => {
    const token = getToken();
    
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    };

    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT);
    
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      throw error;
    }
  };
};

// Response interceptor for handling common response patterns
export const handleAPIResponse = async <T = any>(
  response: Response
): Promise<APIResponse<T>> => {
  try {
    let data;
    const contentType = response.headers.get('Content-Type');
    
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      return {
        success: false,
        error: {
          message: data?.detail || data?.message || `HTTP ${response.status}`,
          status: response.status,
          details: data,
        },
      };
    }

    // Handle different response structures
    if (data && typeof data === 'object') {
      // If response has success field, use it
      if ('success' in data) {
        return data;
      }
      
      // If response has pagination info
      if ('pagination' in data) {
        return {
          success: true,
          data: data.items || data.users || data.projects || data,
          pagination: data.pagination,
          message: data.message || 'Success',
        };
      }
      
      // Standard success response
      return {
        success: true,
        data,
        message: data.message || 'Success',
      };
    }

    // Simple data response
    return {
      success: true,
      data,
      message: 'Success',
    };

  } catch (error) {
    return {
      success: false,
      error: {
        message: error instanceof Error ? error.message : 'Failed to parse response',
        details: error,
      },
    };
  }
};

// Retry logic for failed requests
export const withRetry = async <T>(
  fn: () => Promise<T>,
  attempts: number = API_CONFIG.RETRY_ATTEMPTS,
  delay: number = API_CONFIG.RETRY_DELAY
): Promise<T> => {
  try {
    return await fn();
  } catch (error) {
    if (attempts <= 1) {
      throw error;
    }
    
    // Don't retry client errors (4xx)
    if (error instanceof Error && error.message.includes('HTTP 4')) {
      throw error;
    }
    
    await new Promise(resolve => setTimeout(resolve, delay));
    return withRetry(fn, attempts - 1, delay * 2); // Exponential backoff
  }
};

// URL builder utility
export const buildURL = (
  endpoint: string,
  params?: Record<string, any>,
  baseUrl: string = API_CONFIG.BASE_URL
): string => {
  const url = new URL(endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`);
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        if (Array.isArray(value)) {
          value.forEach(item => url.searchParams.append(key, String(item)));
        } else {
          url.searchParams.append(key, String(value));
        }
      }
    });
  }
  
  return url.toString();
};

// File upload utility
export const uploadFile = async (
  endpoint: string,
  file: File,
  options: {
    onProgress?: (progress: number) => void;
    additionalFields?: Record<string, any>;
    getToken?: () => string | null;
  } = {}
): Promise<APIResponse> => {
  const { onProgress, additionalFields = {}, getToken } = options;
  
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    
    formData.append('file', file);
    Object.entries(additionalFields).forEach(([key, value]) => {
      formData.append(key, String(value));
    });

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = (event.loaded / event.total) * 100;
        onProgress(progress);
      }
    });

    xhr.addEventListener('load', async () => {
      try {
        const response = new Response(xhr.responseText, {
          status: xhr.status,
          statusText: xhr.statusText,
        });
        
        const result = await handleAPIResponse(response);
        resolve(result);
      } catch (error) {
        reject(error);
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload aborted'));
    });

    xhr.open('POST', buildURL(endpoint));
    
    const token = getToken?.();
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    
    xhr.send(formData);
  });
};

// Download file utility
export const downloadFile = async (
  endpoint: string,
  filename?: string,
  options: {
    getToken?: () => string | null;
    params?: Record<string, any>;
  } = {}
): Promise<void> => {
  const { getToken, params } = options;
  
  try {
    const url = buildURL(endpoint, params);
    const token = getToken?.();
    
    const response = await fetch(url, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });

    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`);
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    window.URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    throw new Error(`Download failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
};

// Cache utilities
export const cacheUtils = {
  get: <T = any>(key: string): T | null => {
    if (typeof window === 'undefined') return null;
    
    try {
      const cached = localStorage.getItem(`cache_${key}`);
      if (!cached) return null;
      
      const { data, expires } = JSON.parse(cached);
      if (expires && Date.now() > expires) {
        localStorage.removeItem(`cache_${key}`);
        return null;
      }
      
      return data;
    } catch {
      return null;
    }
  },

  set: <T>(key: string, data: T, ttl?: number): void => {
    if (typeof window === 'undefined') return;
    
    const cached = {
      data,
      expires: ttl ? Date.now() + ttl : undefined,
    };
    
    localStorage.setItem(`cache_${key}`, JSON.stringify(cached));
  },

  remove: (key: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(`cache_${key}`);
  },

  clear: (): void => {
    if (typeof window === 'undefined') return;
    
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('cache_')) {
        localStorage.removeItem(key);
      }
    });
  },
};

// API client factory
export const createAPIClient = (config: {
  baseURL?: string;
  getToken?: () => string | null;
  onUnauthorized?: () => void;
}) => {
  const { baseURL = API_CONFIG.BASE_URL, getToken, onUnauthorized } = config;
  const request = createRequestInterceptor(getToken || (() => null));

  const apiClient = {
    get: async <T = any>(endpoint: string, params?: Record<string, any>): Promise<APIResponse<T>> => {
      const url = buildURL(endpoint, params, baseURL);
      const response = await withRetry(() => request(url));
      
      if (response.status === 401 && onUnauthorized) {
        onUnauthorized();
      }
      
      return handleAPIResponse<T>(response);
    },

    post: async <T = any>(endpoint: string, data?: any, params?: Record<string, any>): Promise<APIResponse<T>> => {
      const url = buildURL(endpoint, params, baseURL);
      const response = await withRetry(() => request(url, {
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
      }));
      
      if (response.status === 401 && onUnauthorized) {
        onUnauthorized();
      }
      
      return handleAPIResponse<T>(response);
    },

    put: async <T = any>(endpoint: string, data?: any, params?: Record<string, any>): Promise<APIResponse<T>> => {
      const url = buildURL(endpoint, params, baseURL);
      const response = await withRetry(() => request(url, {
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
      }));
      
      if (response.status === 401 && onUnauthorized) {
        onUnauthorized();
      }
      
      return handleAPIResponse<T>(response);
    },

    delete: async <T = any>(endpoint: string, params?: Record<string, any>): Promise<APIResponse<T>> => {
      const url = buildURL(endpoint, params, baseURL);
      const response = await withRetry(() => request(url, { method: 'DELETE' }));
      
      if (response.status === 401 && onUnauthorized) {
        onUnauthorized();
      }
      
      return handleAPIResponse<T>(response);
    },

    upload: (endpoint: string, file: File, options?: any) => 
      uploadFile(endpoint, file, { ...options, getToken }),

    download: (endpoint: string, filename?: string, params?: Record<string, any>) =>
      downloadFile(endpoint, filename, { getToken, params }),
  };

  return apiClient;
};

// Error handling utilities
export const handleAPIError = (error: APIError): string => {
  if (error.status === 400) {
    return error.message || 'Invalid request data';
  } else if (error.status === 401) {
    return 'Authentication required';
  } else if (error.status === 403) {
    return 'Access denied';
  } else if (error.status === 404) {
    return 'Resource not found';
  } else if (error.status === 409) {
    return 'Resource conflict';
  } else if (error.status === 422) {
    return 'Validation error';
  } else if (error.status === 429) {
    return 'Too many requests';
  } else if (error.status && error.status >= 500) {
    return 'Server error';
  } else {
    return error.message || 'Network error';
  }
};

// Debug utilities
export const debugUtils = {
  log: (message: string, data?: any) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(`[DafelHub API] ${message}`, data);
    }
  },

  error: (message: string, error?: any) => {
    if (process.env.NODE_ENV === 'development') {
      console.error(`[DafelHub API Error] ${message}`, error);
    }
  },

  time: (label: string) => {
    if (process.env.NODE_ENV === 'development') {
      console.time(`[DafelHub API] ${label}`);
    }
  },

  timeEnd: (label: string) => {
    if (process.env.NODE_ENV === 'development') {
      console.timeEnd(`[DafelHub API] ${label}`);
    }
  },
};

export default {
  tokenUtils,
  cacheUtils,
  debugUtils,
  createAPIClient,
  handleAPIError,
  buildURL,
  uploadFile,
  downloadFile,
};