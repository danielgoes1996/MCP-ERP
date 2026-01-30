/**
 * Session Manager Hook
 *
 * Handles automatic session expiry based on:
 * 1. Inactivity timeout (30 minutes default)
 * 2. Token expiration validation
 */

import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter, usePathname } from 'next/navigation';

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/tienda', '/login', '/register', '/forgot-password'];

const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes
const CHECK_INTERVAL = 60 * 1000; // Check every minute

/**
 * Decode JWT and check if expired
 */
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp * 1000; // Convert to milliseconds
    return Date.now() >= exp;
  } catch (error) {
    // Invalid token format
    return true;
  }
}

/**
 * Check if current path is a public route
 */
function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(route => pathname.startsWith(route));
}

/**
 * Hook to manage user session expiry
 */
export function useSessionManager() {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, token, logout } = useAuthStore();
  const inactivityTimerRef = useRef<NodeJS.Timeout>();
  const checkIntervalRef = useRef<NodeJS.Timeout>();

  // Skip session management on public routes
  const isPublic = isPublicRoute(pathname);

  /**
   * Reset inactivity timer
   */
  const resetInactivityTimer = () => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
    }

    inactivityTimerRef.current = setTimeout(() => {
      console.log('Session expired due to inactivity');
      logout();
      router.push('/login?reason=inactivity');
    }, INACTIVITY_TIMEOUT);
  };

  /**
   * Check if token is still valid
   */
  const checkTokenValidity = () => {
    // Don't redirect on public routes
    if (isPublic) return;
    if (!isAuthenticated || !token) return;

    if (isTokenExpired(token)) {
      console.log('Session expired - token no longer valid');
      logout();
      router.push('/login?reason=expired');
    }
  };

  useEffect(() => {
    // Skip session management on public routes
    if (isPublic || !isAuthenticated) {
      // Clean up timers if not authenticated or on public routes
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);
      return;
    }

    // Check token validity on mount
    checkTokenValidity();

    // Set up periodic token validation
    checkIntervalRef.current = setInterval(checkTokenValidity, CHECK_INTERVAL);

    // Set up inactivity tracking
    resetInactivityTimer();

    // Activity events to track
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];

    events.forEach(event => {
      window.addEventListener(event, resetInactivityTimer);
    });

    // Cleanup
    return () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);

      events.forEach(event => {
        window.removeEventListener(event, resetInactivityTimer);
      });
    };
  }, [isAuthenticated, token, isPublic]);

  return {
    resetInactivityTimer,
  };
}
