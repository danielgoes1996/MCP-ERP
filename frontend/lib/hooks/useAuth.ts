/**
 * useAuth Hook
 *
 * Custom hook for authentication operations
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { authApi } from '@/lib/api/auth';
import type { LoginCredentials, RegisterData } from '@/types/auth';

export function useAuth() {
  const router = useRouter();
  const {
    setUser,
    setTenant,
    setTokens,
    setError,
    setLoading,
    logout: logoutStore,
    user,
    tenant,
    isAuthenticated,
    error,
    isLoading,
  } = useAuthStore();

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onMutate: () => {
      setLoading(true);
      setError(null);
    },
    onSuccess: (data) => {
      setUser(data.user);
      setTenant(data.tenant);
      setTokens(data.access_token, data.refresh_token);

      // Store tokens in localStorage for API client
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      setLoading(false);
      router.push('/dashboard');
    },
    onError: (error: any) => {
      const errorMessage = error.response?.data?.detail || 'Error al iniciar sesión';
      setError(errorMessage);
      setLoading(false);
    },
  });

  // Register mutation
  const registerMutation = useMutation({
    mutationFn: authApi.register,
    onMutate: () => {
      setLoading(true);
      setError(null);
    },
    onSuccess: (data) => {
      setUser(data.user);
      setTenant(data.tenant);
      setTokens(data.access_token, data.refresh_token);

      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      setLoading(false);
      router.push('/dashboard');
    },
    onError: (error: any) => {
      const errorMessage = error.response?.data?.detail || 'Error al registrarse';
      setError(errorMessage);
      setLoading(false);
    },
  });

  // Logout function
  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Error logging out:', error);
    } finally {
      logoutStore();
      router.push('/login');
    }
  };

  // Login function
  const login = (credentials: LoginCredentials) => {
    loginMutation.mutate(credentials);
  };

  // Register function
  const register = (data: RegisterData) => {
    registerMutation.mutate(data);
  };

  return {
    user,
    tenant,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
  };
}

// Hook to get tenants
export function useTenants(email?: string) {
  return useQuery({
    queryKey: ['tenants', email],
    queryFn: () => authApi.getTenants(email),
    enabled: !!email || email === undefined,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
