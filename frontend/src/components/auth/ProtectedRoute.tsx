/**
 * ProtectedRoute Component
 *
 * HOC que protege rutas requiriendo autenticación
 * Redirige a login si el usuario no está autenticado
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  redirectTo?: string;
}

export function ProtectedRoute({
  children,
  redirectTo = '/auth/login',
}: ProtectedRouteProps) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    // Si no está autenticado y no está cargando, redirigir
    if (!isAuthenticated && !isLoading) {
      router.push(redirectTo);
    }
  }, [isAuthenticated, isLoading, router, redirectTo]);

  // Mientras verifica autenticación, mostrar loader
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Verificando autenticación...</p>
        </div>
      </div>
    );
  }

  // Si no está autenticado, no renderizar nada (el useEffect redirigirá)
  if (!isAuthenticated) {
    return null;
  }

  // Si está autenticado, renderizar children
  return <>{children}</>;
}

/**
 * withProtectedRoute HOC
 *
 * Función helper para envolver componentes de página con ProtectedRoute
 */
export function withProtectedRoute<P extends object>(
  Component: React.ComponentType<P>,
  redirectTo?: string
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute redirectTo={redirectTo}>
        <Component {...props} />
      </ProtectedRoute>
    );
  };
}
