/**
 * Auth Store (Zustand)
 *
 * Global authentication state management
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, Tenant, AuthState } from '@/types/auth';

interface AuthActions {
  setUser: (user: User) => void;
  setTenant: (tenant: Tenant) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  clearError: () => void;
}

type AuthStore = AuthState & AuthActions;

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      tenant: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      setUser: (user) =>
        set({
          user,
          isAuthenticated: true,
          error: null,
        }),

      setTenant: (tenant) =>
        set({ tenant }),

      setTokens: (accessToken, refreshToken) =>
        set({
          token: accessToken,
          refreshToken,
          isAuthenticated: true
        }),

      setError: (error) =>
        set({ error, isLoading: false }),

      setLoading: (loading) =>
        set({ isLoading: loading }),

      logout: () => {
        // Clear localStorage tokens
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
        }

        set({
          user: null,
          tenant: null,
          token: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
          isLoading: false,
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      version: 1,
      // Only persist these fields
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
