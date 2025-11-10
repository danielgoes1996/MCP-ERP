/**
 * Dashboard Service
 *
 * Servicio para obtener métricas y datos del dashboard principal
 */

import apiClient from '@/lib/api/client';

// Types
export interface DashboardMetrics {
  monthly_income: number;
  monthly_expenses: number;
  pending_invoices: number;
  overdue_invoices: number;
  current_balance: number;
  income_change_percent: number;
  expenses_change_percent: number;
}

export interface RecentActivity {
  id: number;
  type: 'expense' | 'income' | 'invoice' | 'reconciliation';
  description: string;
  amount: number;
  date: string;
  status: 'pending' | 'approved' | 'rejected' | 'completed';
}

export interface QuickStats {
  total_expenses_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  average_expense: number;
  most_frequent_category: string | null;
  budget_savings_percent: number;
}

const dashboardService = {
  /**
   * Obtener métricas principales del dashboard
   */
  getMetrics: async (): Promise<DashboardMetrics> => {
    try {
      const response = await apiClient.get('/api/dashboard/metrics');
      return response.data;
    } catch (error) {
      // Si el endpoint no existe, retornar datos vacíos
      console.warn('Dashboard metrics endpoint not available, using default values');
      return {
        monthly_income: 0,
        monthly_expenses: 0,
        pending_invoices: 0,
        overdue_invoices: 0,
        current_balance: 0,
        income_change_percent: 0,
        expenses_change_percent: 0,
      };
    }
  },

  /**
   * Obtener actividad reciente
   */
  getRecentActivity: async (limit: number = 10): Promise<RecentActivity[]> => {
    try {
      const response = await apiClient.get('/api/dashboard/recent-activity', {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      console.warn('Recent activity endpoint not available');
      return [];
    }
  },

  /**
   * Obtener estadísticas rápidas
   */
  getQuickStats: async (): Promise<QuickStats> => {
    try {
      const response = await apiClient.get('/api/dashboard/quick-stats');
      return response.data;
    } catch (error) {
      console.warn('Quick stats endpoint not available');
      return {
        total_expenses_count: 0,
        pending_count: 0,
        approved_count: 0,
        rejected_count: 0,
        average_expense: 0,
        most_frequent_category: null,
        budget_savings_percent: 0,
      };
    }
  },
};

export default dashboardService;
