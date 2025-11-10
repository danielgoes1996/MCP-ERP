/**
 * Expenses Service
 *
 * Servicio para gestionar gastos (expenses)
 */

import apiClient from '@/lib/api/client';

// Types
export interface Expense {
  id: number;
  date: string;
  vendor: string;
  concept: string;
  category: string;
  amount: number;
  currency: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
  user_id: number;
  tenant_id: number;
}

export interface ExpenseFilters {
  search?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  category?: string;
  min_amount?: number;
  max_amount?: number;
  page?: number;
  limit?: number;
}

export interface ExpensesResponse {
  expenses: Expense[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface CreateExpenseData {
  date: string;
  vendor: string;
  concept: string;
  category?: string;
  amount: number;
  currency?: string;
  notes?: string;
}

export interface UpdateExpenseData extends Partial<CreateExpenseData> {
  status?: 'pending' | 'approved' | 'rejected';
}

export interface ExpenseStats {
  total_month: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  month_change_percent: number;
}

const expensesService = {
  /**
   * Obtener lista de gastos con filtros
   */
  getExpenses: async (filters?: ExpenseFilters): Promise<ExpensesResponse> => {
    try {
      const response = await apiClient.get('/api/expenses', {
        params: filters,
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching expenses:', error);
      throw error;
    }
  },

  /**
   * Obtener un gasto por ID
   */
  getExpenseById: async (id: number): Promise<Expense> => {
    const response = await apiClient.get(`/api/expenses/${id}`);
    return response.data;
  },

  /**
   * Crear nuevo gasto
   */
  createExpense: async (data: CreateExpenseData): Promise<Expense> => {
    const response = await apiClient.post('/api/expenses', data);
    return response.data;
  },

  /**
   * Actualizar gasto existente
   */
  updateExpense: async (id: number, data: UpdateExpenseData): Promise<Expense> => {
    const response = await apiClient.put(`/api/expenses/${id}`, data);
    return response.data;
  },

  /**
   * Eliminar gasto
   */
  deleteExpense: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/expenses/${id}`);
  },

  /**
   * Aprobar gasto
   */
  approveExpense: async (id: number): Promise<Expense> => {
    const response = await apiClient.post(`/api/expenses/${id}/approve`);
    return response.data;
  },

  /**
   * Rechazar gasto
   */
  rejectExpense: async (id: number, reason?: string): Promise<Expense> => {
    const response = await apiClient.post(`/api/expenses/${id}/reject`, {
      reason,
    });
    return response.data;
  },

  /**
   * Obtener estadísticas de gastos
   */
  getStats: async (): Promise<ExpenseStats> => {
    try {
      const response = await apiClient.get('/api/expenses/stats');
      return response.data;
    } catch (error) {
      console.warn('Expense stats endpoint not available');
      return {
        total_month: 0,
        pending_count: 0,
        approved_count: 0,
        rejected_count: 0,
        month_change_percent: 0,
      };
    }
  },

  /**
   * Importar gastos desde archivo
   */
  importExpenses: async (file: File): Promise<{ imported: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/api/expenses/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * Exportar gastos a CSV/Excel
   */
  exportExpenses: async (filters?: ExpenseFilters, format: 'csv' | 'excel' = 'csv'): Promise<Blob> => {
    const response = await apiClient.get('/api/expenses/export', {
      params: { ...filters, format },
      responseType: 'blob',
    });
    return response.data;
  },
};

export default expensesService;
