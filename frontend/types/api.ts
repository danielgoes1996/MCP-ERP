/**
 * API Response Types
 *
 * Standard response types from the backend API
 */

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}
