'use client';

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from './useAuth';

// Types
interface APIResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  error?: string;
  status?: number;
}

interface PaginationInfo {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

interface PaginatedResponse<T> extends APIResponse<T[]> {
  pagination?: PaginationInfo;
}

interface APIState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  lastFetch: Date | null;
}

interface APIListState<T> {
  items: T[];
  pagination: PaginationInfo | null;
  isLoading: boolean;
  error: string | null;
  lastFetch: Date | null;
}

interface UseAPIOptions {
  immediate?: boolean;
  refreshInterval?: number;
  onSuccess?: (data: any) => void;
  onError?: (error: string) => void;
}

// API configuration
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// API endpoints mapping
export const API_ENDPOINTS = {
  // Auth endpoints
  AUTH: {
    LOGIN: '/auth/login',
    REGISTER: '/auth/register',
    LOGOUT: '/auth/logout',
    REFRESH: '/auth/refresh',
    ME: '/auth/me',
  },
  
  // Admin endpoints
  ADMIN: {
    USERS: '/admin/users',
    USER_BY_ID: (id: string) => `/admin/users/${id}`,
    USER_ROLE: (id: string) => `/admin/users/${id}/role`,
    AUDIT: '/admin/audit',
  },
  
  // Projects endpoints (from routes/projects.py)
  PROJECTS: {
    LIST: '/projects',
    CREATE: '/projects',
    BY_ID: (id: string) => `/projects/${id}`,
    DELETE: (id: string) => `/projects/${id}`,
    DEPLOY: (id: string) => `/projects/${id}/deploy`,
    STATUS: (id: string) => `/projects/${id}/status`,
  },
  
  // Studio endpoints (from routes/studio.py)
  STUDIO: {
    TEMPLATES: '/studio/templates',
    CREATE_PROJECT: '/studio/projects',
    BUILDER: '/studio/builder',
    PREVIEW: '/studio/preview',
    EXPORT: '/studio/export',
  },
  
  // Connections endpoints (from routes/connections.py)
  CONNECTIONS: {
    LIST: '/connections',
    CREATE: '/connections',
    BY_ID: (id: string) => `/connections/${id}`,
    TEST: (id: string) => `/connections/${id}/test`,
    DELETE: (id: string) => `/connections/${id}`,
  },
  
  // Health endpoint
  HEALTH: '/health',
};

// Main useAPI hook
export const useAPI = () => {
  const { isAuthenticated, user } = useAuth();

  // Get authorization token
  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('dafelhub_access_token');
  }, []);

  // Base API call function
  const apiCall = useCallback(async <T = any>(
    endpoint: string,
    options: RequestInit & { params?: Record<string, any> } = {}
  ): Promise<APIResponse<T>> => {
    try {
      const { params, ...fetchOptions } = options;
      let url = `${API_BASE}${endpoint}`;

      // Add query parameters
      if (params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
          if (value !== null && value !== undefined) {
            searchParams.append(key, String(value));
          }
        });
        if (searchParams.toString()) {
          url += `?${searchParams.toString()}`;
        }
      }

      const token = getToken();
      
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...(token && isAuthenticated && { Authorization: `Bearer ${token}` }),
          ...fetchOptions.headers,
        },
      });

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
          message: data?.detail || data?.message || 'Request failed',
          error: data?.detail || data?.message || `HTTP ${response.status}`,
          status: response.status,
        };
      }

      return {
        success: true,
        message: data?.message || 'Success',
        data: data,
        status: response.status,
      };
      
    } catch (error) {
      console.error('API call error:', error);
      return {
        success: false,
        message: 'Network error',
        error: error instanceof Error ? error.message : 'Unknown error',
        status: 0,
      };
    }
  }, [getToken, isAuthenticated]);

  // GET request
  const get = useCallback(async <T = any>(
    endpoint: string,
    params?: Record<string, any>
  ): Promise<APIResponse<T>> => {
    return apiCall<T>(endpoint, { method: 'GET', params });
  }, [apiCall]);

  // POST request
  const post = useCallback(async <T = any>(
    endpoint: string,
    data?: any,
    params?: Record<string, any>
  ): Promise<APIResponse<T>> => {
    return apiCall<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
      params,
    });
  }, [apiCall]);

  // PUT request
  const put = useCallback(async <T = any>(
    endpoint: string,
    data?: any,
    params?: Record<string, any>
  ): Promise<APIResponse<T>> => {
    return apiCall<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
      params,
    });
  }, [apiCall]);

  // DELETE request
  const del = useCallback(async <T = any>(
    endpoint: string,
    params?: Record<string, any>
  ): Promise<APIResponse<T>> => {
    return apiCall<T>(endpoint, { method: 'DELETE', params });
  }, [apiCall]);

  return {
    get,
    post,
    put,
    delete: del,
    apiCall,
    isAuthenticated,
    user,
  };
};

// Hook for single resource with automatic loading
export const useAPIResource = <T = any>(
  endpoint: string,
  options: UseAPIOptions = {}
) => {
  const { get } = useAPI();
  const { immediate = true, refreshInterval, onSuccess, onError } = options;
  
  const [state, setState] = useState<APIState<T>>({
    data: null,
    isLoading: false,
    error: null,
    lastFetch: null,
  });

  const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await get<T>(endpoint);
      
      if (response.success) {
        setState(prev => ({
          ...prev,
          data: response.data || null,
          isLoading: false,
          error: null,
          lastFetch: new Date(),
        }));
        onSuccess?.(response.data);
      } else {
        setState(prev => ({
          ...prev,
          data: null,
          isLoading: false,
          error: response.error || 'Failed to fetch data',
          lastFetch: new Date(),
        }));
        onError?.(response.error || 'Failed to fetch data');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setState(prev => ({
        ...prev,
        data: null,
        isLoading: false,
        error: errorMessage,
        lastFetch: new Date(),
      }));
      onError?.(errorMessage);
    }
  }, [endpoint, get, onSuccess, onError]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  // Initial fetch
  useEffect(() => {
    if (immediate && endpoint) {
      fetchData();
    }
  }, [immediate, endpoint, fetchData]);

  // Auto refresh
  useEffect(() => {
    if (!refreshInterval || refreshInterval <= 0) return;

    const interval = setInterval(() => {
      if (!state.isLoading) {
        fetchData();
      }
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, state.isLoading, fetchData]);

  return {
    ...state,
    refetch,
    clearError,
  };
};

// Hook for paginated lists
export const useAPIList = <T = any>(
  endpoint: string,
  options: UseAPIOptions & {
    page?: number;
    limit?: number;
    filters?: Record<string, any>;
  } = {}
) => {
  const { get } = useAPI();
  const {
    immediate = true,
    refreshInterval,
    onSuccess,
    onError,
    page = 1,
    limit = 20,
    filters = {}
  } = options;
  
  const [state, setState] = useState<APIListState<T>>({
    items: [],
    pagination: null,
    isLoading: false,
    error: null,
    lastFetch: null,
  });

  const fetchData = useCallback(async (
    currentPage: number = page,
    currentLimit: number = limit,
    currentFilters: Record<string, any> = filters
  ) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const params = {
        page: currentPage,
        limit: currentLimit,
        ...currentFilters,
      };

      const response = await get<PaginatedResponse<T>>(endpoint, params);
      
      if (response.success && response.data) {
        const data = response.data as any;
        const items = data.items || data.users || data.projects || data.connections || [];
        const pagination = data.pagination || null;

        setState(prev => ({
          ...prev,
          items,
          pagination,
          isLoading: false,
          error: null,
          lastFetch: new Date(),
        }));
        onSuccess?.(items);
      } else {
        setState(prev => ({
          ...prev,
          items: [],
          pagination: null,
          isLoading: false,
          error: response.error || 'Failed to fetch list',
          lastFetch: new Date(),
        }));
        onError?.(response.error || 'Failed to fetch list');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setState(prev => ({
        ...prev,
        items: [],
        pagination: null,
        isLoading: false,
        error: errorMessage,
        lastFetch: new Date(),
      }));
      onError?.(errorMessage);
    }
  }, [endpoint, get, page, limit, filters, onSuccess, onError]);

  const refetch = useCallback((
    newPage?: number,
    newLimit?: number,
    newFilters?: Record<string, any>
  ) => {
    fetchData(newPage, newLimit, newFilters);
  }, [fetchData]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  // Initial fetch
  useEffect(() => {
    if (immediate && endpoint) {
      fetchData();
    }
  }, [immediate, endpoint, fetchData]);

  // Auto refresh
  useEffect(() => {
    if (!refreshInterval || refreshInterval <= 0) return;

    const interval = setInterval(() => {
      if (!state.isLoading) {
        fetchData();
      }
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, state.isLoading, fetchData]);

  return {
    ...state,
    refetch,
    clearError,
  };
};

// Hook for mutations (POST, PUT, DELETE)
export const useAPIMutation = <TData = any, TVariables = any>(
  mutationFn: (variables: TVariables) => Promise<APIResponse<TData>>,
  options: {
    onSuccess?: (data: TData) => void;
    onError?: (error: string) => void;
    onSettled?: () => void;
  } = {}
) => {
  const [state, setState] = useState({
    isLoading: false,
    error: null as string | null,
    data: null as TData | null,
  });

  const mutate = useCallback(async (variables: TVariables) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await mutationFn(variables);
      
      if (response.success) {
        setState(prev => ({
          ...prev,
          data: response.data || null,
          isLoading: false,
          error: null,
        }));
        options.onSuccess?.(response.data);
      } else {
        setState(prev => ({
          ...prev,
          data: null,
          isLoading: false,
          error: response.error || 'Mutation failed',
        }));
        options.onError?.(response.error || 'Mutation failed');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setState(prev => ({
        ...prev,
        data: null,
        isLoading: false,
        error: errorMessage,
      }));
      options.onError?.(errorMessage);
    } finally {
      options.onSettled?.();
    }
  }, [mutationFn, options]);

  const reset = useCallback(() => {
    setState({
      isLoading: false,
      error: null,
      data: null,
    });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
};

export default useAPI;