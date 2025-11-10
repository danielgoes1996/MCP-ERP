/**
 * Authentication Store (Zustand)
 *
 * Store global para el estado de autenticación:
 * - Usuario actual
 * - Token JWT
 * - Estado de loading
 * - Funciones de login/logout
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: number;
  employee_id: number | null;
  is_active: boolean;
}

export interface Tenant {
  id: number;
  name: string;
  description: string | null;
}

interface AuthState {
  // Estado
  user: User | null;
  tenant: Tenant | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Acciones
  setUser: (user: User) => void;
  setTenant: (tenant: Tenant) => void;
  setToken: (token: string) => void;
  setError: (error: string | null) => void;
  logout: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      // Estado inicial
      user: null,
      tenant: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Setters
      setUser: (user) =>
        set({
          user,
          isAuthenticated: true,
          error: null,
        }),

      setTenant: (tenant) =>
        set({ tenant }),

      setToken: (token) =>
        set({ token }),

      setError: (error) =>
        set({ error, isLoading: false }),

      logout: () => {
        // Limpiar localStorage
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('auth-storage');
        }

        set({
          user: null,
          tenant: null,
          token: null,
          isAuthenticated: false,
          error: null,
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      version: 2, // Incrementamos la versión para forzar migración
      // Solo persistir ciertos campos
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      // Migración para limpiar datos antiguos
      migrate: (persistedState: any, version: number) => {
        // Si es una versión antigua o el user no tiene full_name, limpiar todo
        if (version < 2 || (persistedState?.user && !persistedState?.user?.full_name)) {
          console.log('🔄 Migrando datos de autenticación antiguos...');
          if (typeof window !== 'undefined') {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('refresh_token');
          }
          return {
            user: null,
            tenant: null,
            token: null,
            isAuthenticated: false,
          };
        }
        return persistedState as any;
      },
    }
  )
);
