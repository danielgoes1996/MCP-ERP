/**
 * Authentication Service
 *
 * Servicio para interactuar con los endpoints de autenticación del backend:
 * - Login
 * - Register
 * - Refresh token
 * - Get current user
 */

import apiClient from '@/lib/api/client';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
  company_name?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: number;
    username: string;
    email: string;
    full_name: string;
    role: string;
    tenant_id: number;
    employee_id: number | null;
    is_active: boolean;
  };
  tenant: {
    id: number;
    name: string;
    description: string | null;
  };
}

export const authService = {
  /**
   * Login de usuario
   */
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    // El backend usa OAuth2 form data, no JSON
    const formData = new URLSearchParams();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);
    formData.append('tenant_id', '2'); // TODO: Get from tenant selection

    const response = await apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  /**
   * Registro de nuevo usuario
   */
  register: async (data: RegisterData): Promise<AuthResponse> => {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
  },

  /**
   * Refresh del token
   */
  refreshToken: async (refreshToken: string): Promise<AuthResponse> => {
    const response = await apiClient.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  /**
   * Obtener usuario actual
   */
  getCurrentUser: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  /**
   * Logout
   */
  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  /**
   * Request password reset
   */
  requestPasswordReset: async (email: string): Promise<void> => {
    await apiClient.post('/auth/forgot-password', { email });
  },

  /**
   * Reset password
   */
  resetPassword: async (token: string, newPassword: string): Promise<void> => {
    await apiClient.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
  },
};
