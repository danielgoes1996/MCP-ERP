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
  updateAccessToken: (accessToken: string) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  clearError: () => void;
  // Multi-role helpers
  hasRole: (roleName: string) => boolean;
  hasAnyRole: (roleNames: string[]) => boolean;
  hasAllRoles: (roleNames: string[]) => boolean;
  getUserRoles: () => string[];
  isAdmin: () => boolean;
  isContador: () => boolean;
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

      updateAccessToken: (accessToken) =>
        set({
          token: accessToken,
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

      // Multi-role helpers
      hasRole: (roleName) => {
        const state = useAuthStore.getState();
        if (!state.user) return false;
        // Check both legacy role and new roles array
        if (state.user.role === roleName) return true;
        return state.user.roles?.includes(roleName) ?? false;
      },

      hasAnyRole: (roleNames) => {
        const state = useAuthStore.getState();
        if (!state.user) return false;
        // Check legacy role
        if (roleNames.includes(state.user.role)) return true;
        // Check roles array
        return state.user.roles?.some(role => roleNames.includes(role)) ?? false;
      },

      hasAllRoles: (roleNames) => {
        const state = useAuthStore.getState();
        if (!state.user) return false;
        const userRoles = state.user.roles ?? [state.user.role];
        return roleNames.every(role => userRoles.includes(role));
      },

      getUserRoles: () => {
        const state = useAuthStore.getState();
        if (!state.user) return [];
        // Return roles array if available, otherwise return legacy role
        return state.user.roles ?? [state.user.role];
      },

      isAdmin: () => {
        const state = useAuthStore.getState();
        if (!state.user) return false;
        return state.user.role === 'admin' || state.user.roles?.includes('admin') || false;
      },

      isContador: () => {
        const state = useAuthStore.getState();
        if (!state.user) return false;
        return state.user.role === 'contador' || state.user.roles?.includes('contador') || false;
      },
    }),
    {
      name: 'auth-storage',
      version: 2,  // Increment version for multi-role support
      // Only persist these fields
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
      // Migration function for version changes
      migrate: (persistedState: unknown, version: number): any => {
        const state = persistedState as any;
        // If migrating from version < 2, ensure roles array exists
        if (version < 2 && state?.user) {
          state.user.roles = state.user.roles || [state.user.role];
        }
        return state;
      },
    }
  )
);
