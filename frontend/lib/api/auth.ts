/**
 * Auth API Service
 *
 * Handles all authentication-related API calls
 */

import { apiClient } from './client';
import type {
  LoginCredentials,
  RegisterData,
  AuthResponse,
  Tenant
} from '@/types/auth';

export const authApi = {
  /**
   * Login user
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);
    formData.append('tenant_id', credentials.tenant_id.toString());

    const response = await apiClient.post<AuthResponse>(
      '/auth/login',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  /**
   * Register new user
   */
  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>('/auth/register', data);
    return response.data;
  },

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
  },

  /**
   * Get available tenants for a user email
   */
  async getTenants(email?: string): Promise<Tenant[]> {
    const url = email ? `/auth/tenants?email=${encodeURIComponent(email)}` : '/auth/tenants';
    const response = await apiClient.get<Tenant[]>(url);
    return response.data;
  },

  /**
   * Refresh access token
   */
  async refreshToken(refreshToken: string): Promise<{ access_token: string }> {
    const response = await apiClient.post<{ access_token: string }>(
      '/auth/refresh',
      { refresh_token: refreshToken }
    );
    return response.data;
  },

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<AuthResponse> {
    const response = await apiClient.get<AuthResponse>('/auth/me');
    return response.data;
  },
};
