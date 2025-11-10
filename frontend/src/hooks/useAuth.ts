/**
 * useAuth Hook
 *
 * Hook personalizado que combina el store de Zustand con la lógica de autenticación
 * y React Query para las llamadas a la API
 */

'use client';

import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { authService, type LoginCredentials, type RegisterData } from '@/services/auth/authService';
import { toast } from '@/lib/utils/toast';

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, setUser, setTenant, setToken, setError, logout: logoutStore } = useAuthStore();

  /**
   * Mutation de Login
   */
  const loginMutation = useMutation({
    mutationFn: (credentials: LoginCredentials) => authService.login(credentials),
    onSuccess: (data) => {
      // Guardar usuario, tenant y token
      setUser(data.user);
      setTenant(data.tenant);
      setToken(data.access_token);

      // Guardar token en localStorage
      localStorage.setItem('auth_token', data.access_token);

      // Redirect a módulo de gastos
      router.push('/expenses');

      toast.success(`¡Bienvenido de vuelta, ${data.user.full_name}!`);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || error.response?.data?.message || 'Error al iniciar sesión';
      setError(message);
      toast.error(message);
    },
  });

  /**
   * Mutation de Register
   */
  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => authService.register(data),
    onSuccess: (data) => {
      // Guardar usuario, tenant y token
      setUser(data.user);
      setTenant(data.tenant);
      setToken(data.access_token);

      // Guardar token en localStorage
      localStorage.setItem('auth_token', data.access_token);

      // Redirect a módulo de gastos
      router.push('/expenses');

      toast.success('¡Cuenta creada exitosamente!');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || error.response?.data?.message || 'Error al crear cuenta';
      setError(message);
      toast.error(message);
    },
  });

  /**
   * Función de Logout
   */
  const logout = async () => {
    try {
      await authService.logout();
    } catch (error) {
      console.error('Error durante logout:', error);
    } finally {
      logoutStore();
      router.push('/auth/login');
      toast.info('Sesión cerrada');
    }
  };

  return {
    // Estado
    user,
    isAuthenticated,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,

    // Funciones
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout,
  };
}
