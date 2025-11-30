/**
 * App Providers
 *
 * Wraps the app with necessary providers:
 * - React Query for server state
 * - Zustand is already configured with persist
 * - Session Manager for automatic logout
 */

'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, useState } from 'react';
import { useSessionManager } from '@/lib/hooks/useSessionManager';

/**
 * Session Manager Component
 * Initializes the session management hook globally
 */
function SessionManager() {
  useSessionManager();
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionManager />
      {children}
    </QueryClientProvider>
  );
}
