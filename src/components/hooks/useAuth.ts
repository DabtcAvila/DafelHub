'use client';

import { useState, useEffect, useCallback, useContext, createContext } from 'react';
import { useRouter } from 'next/navigation';

// Types
interface User {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  company?: string;
  phone?: string;
  avatar_url?: string;
  is_active: boolean;
  is_verified: boolean;
  mfa_enabled: boolean;
  last_login?: string;
  created_at: string;
  updated_at: string;
}

interface LoginCredentials {
  username: string;
  password: string;
  mfa_code?: string;
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
  full_name: string;
  company?: string;
  phone?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  requiresMfa: boolean;
  mfaMethods: string[];
}

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<boolean>;
  register: (data: RegisterData) => Promise<boolean>;
  logout: (allDevices?: boolean) => Promise<void>;
  refreshToken: () => Promise<boolean>;
  clearError: () => void;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
  isAdmin: () => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

// API endpoints
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_ENDPOINTS = {
  LOGIN: `${API_BASE}/auth/login`,
  REGISTER: `${API_BASE}/auth/register`,
  LOGOUT: `${API_BASE}/auth/logout`,
  REFRESH: `${API_BASE}/auth/refresh`,
  ME: `${API_BASE}/auth/me`,
};

// Token management
const TOKEN_STORAGE_KEY = 'dafelhub_access_token';
const REFRESH_TOKEN_STORAGE_KEY = 'dafelhub_refresh_token';

const getStoredToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

const getStoredRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
};

const setTokens = (accessToken: string, refreshToken: string) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
};

const clearTokens = () => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
};

// Auth Provider Component
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
    requiresMfa: false,
    mfaMethods: [],
  });

  // API call helper with automatic token refresh
  const apiCall = useCallback(async (
    url: string, 
    options: RequestInit = {}
  ): Promise<Response> => {
    const token = getStoredToken();
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    // If token expired, try to refresh
    if (response.status === 401 && token) {
      const refreshResult = await refreshTokenInternal();
      if (refreshResult) {
        // Retry original request with new token
        const newToken = getStoredToken();
        return fetch(url, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...(newToken && { Authorization: `Bearer ${newToken}` }),
            ...options.headers,
          },
        });
      } else {
        // Refresh failed, logout user
        await logoutInternal();
        router.push('/login');
        throw new Error('Authentication expired');
      }
    }

    return response;
  }, [router]);

  // Internal refresh token function
  const refreshTokenInternal = useCallback(async (): Promise<boolean> => {
    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await fetch(API_ENDPOINTS.REFRESH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        clearTokens();
        return false;
      }

      const data = await response.json();
      if (data.success && data.access_token) {
        setTokens(data.access_token, refreshToken);
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearTokens();
      return false;
    }
  }, []);

  // Load user profile
  const loadUserProfile = useCallback(async (): Promise<boolean> => {
    try {
      const response = await apiCall(API_ENDPOINTS.ME);
      
      if (!response.ok) {
        return false;
      }

      const user: User = await response.json();
      
      setAuthState(prev => ({
        ...prev,
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      }));
      
      return true;
    } catch (error) {
      console.error('Failed to load user profile:', error);
      setAuthState(prev => ({
        ...prev,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Failed to load user profile',
      }));
      return false;
    }
  }, [apiCall]);

  // Login function
  const login = useCallback(async (credentials: LoginCredentials): Promise<boolean> => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(API_ENDPOINTS.LOGIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      });

      const data = await response.json();

      if (!response.ok) {
        setAuthState(prev => ({
          ...prev,
          isLoading: false,
          error: data.detail || 'Login failed',
        }));
        return false;
      }

      if (data.requires_mfa && !credentials.mfa_code) {
        setAuthState(prev => ({
          ...prev,
          requiresMfa: true,
          mfaMethods: data.mfa_methods || [],
          user: data.user,
          isLoading: false,
        }));
        return false; // Need MFA code
      }

      // Successful login
      if (data.access_token && data.refresh_token) {
        setTokens(data.access_token, data.refresh_token);
        
        setAuthState(prev => ({
          ...prev,
          user: data.user,
          isAuthenticated: true,
          isLoading: false,
          requiresMfa: false,
          mfaMethods: [],
          error: null,
        }));
        
        return true;
      }

      return false;
    } catch (error) {
      console.error('Login error:', error);
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: 'Network error during login',
      }));
      return false;
    }
  }, []);

  // Register function
  const register = useCallback(async (data: RegisterData): Promise<boolean> => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(API_ENDPOINTS.REGISTER, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (!response.ok) {
        setAuthState(prev => ({
          ...prev,
          isLoading: false,
          error: result.detail || 'Registration failed',
        }));
        return false;
      }

      // Successful registration
      if (result.access_token && result.refresh_token) {
        setTokens(result.access_token, result.refresh_token);
        
        setAuthState(prev => ({
          ...prev,
          user: result.user,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        }));
        
        return true;
      }

      return false;
    } catch (error) {
      console.error('Registration error:', error);
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: 'Network error during registration',
      }));
      return false;
    }
  }, []);

  // Internal logout function
  const logoutInternal = useCallback(async () => {
    clearTokens();
    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      requiresMfa: false,
      mfaMethods: [],
    });
  }, []);

  // Logout function
  const logout = useCallback(async (allDevices: boolean = false) => {
    try {
      const token = getStoredToken();
      if (token) {
        await apiCall(API_ENDPOINTS.LOGOUT, {
          method: 'POST',
          body: JSON.stringify({ all_devices: allDevices }),
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      await logoutInternal();
    }
  }, [apiCall, logoutInternal]);

  // Refresh token function
  const refreshToken = useCallback(async (): Promise<boolean> => {
    return await refreshTokenInternal();
  }, [refreshTokenInternal]);

  // Clear error function
  const clearError = useCallback(() => {
    setAuthState(prev => ({ ...prev, error: null }));
  }, []);

  // Permission and role helpers
  const hasPermission = useCallback((permission: string): boolean => {
    return authState.user?.permissions?.includes(permission) || false;
  }, [authState.user]);

  const hasRole = useCallback((role: string): boolean => {
    return authState.user?.roles?.includes(role) || false;
  }, [authState.user]);

  const isAdmin = useCallback((): boolean => {
    return hasRole('admin') || hasRole('super_admin');
  }, [hasRole]);

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = getStoredToken();
      if (!token) {
        setAuthState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      // Try to load user profile
      const success = await loadUserProfile();
      if (!success) {
        // Token might be expired, try refresh
        const refreshed = await refreshTokenInternal();
        if (refreshed) {
          await loadUserProfile();
        } else {
          clearTokens();
          setAuthState(prev => ({ 
            ...prev, 
            isLoading: false,
            isAuthenticated: false,
            user: null 
          }));
        }
      }
    };

    initAuth();
  }, [loadUserProfile, refreshTokenInternal]);

  // Auto refresh token before expiry
  useEffect(() => {
    if (!authState.isAuthenticated) return;

    const refreshInterval = setInterval(() => {
      refreshTokenInternal();
    }, 14 * 60 * 1000); // Refresh every 14 minutes (tokens expire in 15 minutes)

    return () => clearInterval(refreshInterval);
  }, [authState.isAuthenticated, refreshTokenInternal]);

  const contextValue: AuthContextType = {
    ...authState,
    login,
    register,
    logout,
    refreshToken,
    clearError,
    hasPermission,
    hasRole,
    isAdmin,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

// useAuth hook
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Higher-order component for protected routes
export const withAuth = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredPermissions?: string[],
  requiredRoles?: string[]
) => {
  const WithAuthComponent: React.FC<P> = (props) => {
    const { isAuthenticated, isLoading, user, hasPermission, hasRole } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (isLoading) return;

      if (!isAuthenticated) {
        router.push('/login');
        return;
      }

      // Check required permissions
      if (requiredPermissions && requiredPermissions.length > 0) {
        const hasRequiredPermissions = requiredPermissions.every(permission => 
          hasPermission(permission)
        );
        if (!hasRequiredPermissions) {
          router.push('/unauthorized');
          return;
        }
      }

      // Check required roles
      if (requiredRoles && requiredRoles.length > 0) {
        const hasRequiredRole = requiredRoles.some(role => hasRole(role));
        if (!hasRequiredRole) {
          router.push('/unauthorized');
          return;
        }
      }
    }, [isAuthenticated, isLoading, hasPermission, hasRole, router]);

    if (isLoading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    if (!isAuthenticated) {
      return null;
    }

    return <WrappedComponent {...props} />;
  };

  WithAuthComponent.displayName = `withAuth(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithAuthComponent;
};

export default useAuth;