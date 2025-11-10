/**
 * Expenses Hook
 *
 * Hook personalizado para gestionar gastos con React Query
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import expensesService, {
  type ExpenseFilters,
  type CreateExpenseData,
  type UpdateExpenseData,
} from '@/services/expenses/expensesService';

export function useExpenses(filters?: ExpenseFilters) {
  return useQuery({
    queryKey: ['expenses', filters],
    queryFn: () => expensesService.getExpenses(filters),
    staleTime: 1000 * 60 * 2, // 2 minutos
  });
}

export function useExpense(id: number) {
  return useQuery({
    queryKey: ['expenses', id],
    queryFn: () => expensesService.getExpenseById(id),
    enabled: !!id,
  });
}

export function useExpenseStats() {
  return useQuery({
    queryKey: ['expenses', 'stats'],
    queryFn: expensesService.getStats,
    staleTime: 1000 * 60 * 5, // 5 minutos
  });
}

export function useCreateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateExpenseData) => expensesService.createExpense(data),
    onSuccess: () => {
      // Invalidar queries relacionadas
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useUpdateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateExpenseData }) =>
      expensesService.updateExpense(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expenses', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useDeleteExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => expensesService.deleteExpense(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useApproveExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => expensesService.approveExpense(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expenses', id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useRejectExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      expensesService.rejectExpense(id, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expenses', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
