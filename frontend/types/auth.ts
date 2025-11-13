/**
 * Authentication Types
 *
 * Type definitions for authentication, users, and tenants
 */

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: number;
  employee_id: number | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Tenant {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  tenant_id: number;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  full_name: string;
  tenant_id: number;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  tenant: Tenant;
}

export interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
