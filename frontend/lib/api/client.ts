/**
 * API Client Configuration
 *
 * Configures axios instance for all API calls to the backend
 * Handles authentication, error handling, and request/response interceptors
 * Includes automatic token refresh logic
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Token refresh state
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

/**
 * Process queue of failed requests after token refresh
 */
const processQueue = (error: AxiosError | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

/**
 * Refresh the access token using refresh token
 */
const refreshAccessToken = async (): Promise<string> => {
  const refreshToken = typeof window !== 'undefined'
    ? localStorage.getItem('refresh_token')
    : null;

  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });

    const { access_token } = response.data;

    // Update token in localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', access_token);

      // Sync with Zustand store
      try {
        const { useAuthStore } = await import('@/stores/auth/useAuthStore');
        useAuthStore.getState().updateAccessToken(access_token);
      } catch (error) {
        // Store import failed, continue with localStorage only
        console.warn('Could not sync token with auth store:', error);
      }
    }

    return access_token;
  } catch (error) {
    // Refresh token also expired or invalid
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
    }
    throw error;
  }
};

// Request interceptor - Add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('auth_token')
      : null;

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If error is not 401 or no config, reject immediately
    if (error.response?.status !== 401 || !originalRequest) {
      return Promise.reject(error);
    }

    // Don't retry login, register, or refresh endpoints
    const isAuthEndpoint = originalRequest.url?.includes('/auth/login') ||
                          originalRequest.url?.includes('/auth/register') ||
                          originalRequest.url?.includes('/auth/refresh');

    if (isAuthEndpoint) {
      return Promise.reject(error);
    }

    // If already retried, logout and redirect
    if (originalRequest._retry) {
      // Refresh failed, logout user
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');

        // Use Zustand store to logout properly
        const { useAuthStore } = await import('@/stores/auth/useAuthStore');
        useAuthStore.getState().logout();

        window.location.href = '/login';
      }
      return Promise.reject(error);
    }

    // Mark request as retried
    originalRequest._retry = true;

    if (isRefreshing) {
      // If already refreshing, queue this request
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return apiClient(originalRequest);
        })
        .catch((err) => {
          return Promise.reject(err);
        });
    }

    // Start refresh process
    isRefreshing = true;

    try {
      const newToken = await refreshAccessToken();

      // Update authorization header
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
      }

      // Process queued requests
      processQueue(null, newToken);

      // Retry original request
      return apiClient(originalRequest);
    } catch (refreshError) {
      // Refresh failed
      processQueue(refreshError as AxiosError, null);

      // Logout user
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');

        // Use Zustand store to logout properly
        const { useAuthStore } = await import('@/stores/auth/useAuthStore');
        useAuthStore.getState().logout();

        window.location.href = '/login';
      }

      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default apiClient;
