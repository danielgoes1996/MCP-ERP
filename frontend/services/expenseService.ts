/**
 * Expense Service
 *
 * API client for expense creation and management
 */

import {
  ExpenseCreateRequest,
  ExpenseResponse,
  PaymentAccount,
} from '@/types/expense';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

/**
 * Get auth headers
 */
function getAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

/**
 * Create a new expense
 *
 * POST /expenses
 */
export async function createExpense(
  expense: ExpenseCreateRequest
): Promise<ExpenseResponse> {
  const response = await fetch(`${API_BASE_URL}/expenses`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(expense),
  });

  if (!response.ok) {
    // Try to extract error details from response
    let errorMessage = `Error al crear gasto: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        // Pydantic validation error format
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // Validation errors array
          const errors = errorData.detail
            .map((err: any) => `${err.loc.join('.')}: ${err.msg}`)
            .join(', ');
          errorMessage = `Errores de validación: ${errors}`;
        }
      }
    } catch (e) {
      // If can't parse JSON, use status text
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Get payment accounts for current user
 *
 * GET /payment-accounts
 */
export async function getPaymentAccounts(
  companyId?: string
): Promise<PaymentAccount[]> {
  const url = companyId
    ? `${API_BASE_URL}/payment-accounts/?company_id=${companyId}`
    : `${API_BASE_URL}/payment-accounts/`;

  const response = await fetch(url, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Error al obtener cuentas de pago: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get expense by ID
 *
 * GET /expenses/{id}
 */
export async function getExpense(id: number): Promise<ExpenseResponse> {
  const response = await fetch(`${API_BASE_URL}/expenses/${id}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Error al obtener gasto: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get all expenses (with optional filters)
 *
 * GET /expenses
 */
export async function getExpenses(params?: {
  company_id?: string;
  limit?: number;
  offset?: number;
  fecha_desde?: string;
  fecha_hasta?: string;
}): Promise<ExpenseResponse[]> {
  const searchParams = new URLSearchParams();

  if (params?.company_id) searchParams.append('company_id', params.company_id);
  if (params?.limit) searchParams.append('limit', params.limit.toString());
  if (params?.offset) searchParams.append('offset', params.offset.toString());
  if (params?.fecha_desde) searchParams.append('fecha_desde', params.fecha_desde);
  if (params?.fecha_hasta) searchParams.append('fecha_hasta', params.fecha_hasta);

  const url = `${API_BASE_URL}/expenses${searchParams.toString() ? '?' + searchParams.toString() : ''}`;

  const response = await fetch(url, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Error al obtener gastos: ${response.statusText}`);
  }

  return response.json();
}
