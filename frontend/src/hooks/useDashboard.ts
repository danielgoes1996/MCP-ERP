/**
 * Dashboard Hook
 *
 * Hook personalizado para gestionar datos del dashboard con React Query
 */

import { useQuery } from '@tanstack/react-query';
import dashboardService from '@/services/dashboard/dashboardService';

export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: dashboardService.getMetrics,
    staleTime: 1000 * 60 * 5, // 5 minutos
    refetchInterval: 1000 * 60 * 5, // Refetch cada 5 minutos
  });
}

export function useRecentActivity(limit: number = 10) {
  return useQuery({
    queryKey: ['dashboard', 'recent-activity', limit],
    queryFn: () => dashboardService.getRecentActivity(limit),
    staleTime: 1000 * 60 * 2, // 2 minutos
  });
}

export function useQuickStats() {
  return useQuery({
    queryKey: ['dashboard', 'quick-stats'],
    queryFn: dashboardService.getQuickStats,
    staleTime: 1000 * 60 * 5, // 5 minutos
  });
}
