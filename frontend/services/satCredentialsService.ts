/**
 * SAT Credentials Service
 *
 * API calls for managing SAT FIEL credentials
 */

import { useAuthStore } from '@/stores/auth/useAuthStore';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get auth token from Zustand store
 */
function getAuthToken(): string | null {
  return useAuthStore.getState().token;
}

export interface SATCredentials {
  id: number;
  company_id: number;
  rfc: string;
  certificate_serial_number: string | null;
  certificate_valid_from: string | null;
  certificate_valid_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface UploadCredentialsRequest {
  rfc: string;
  sat_password: string;
  fiel_password: string;
  cer_file: File;
  key_file: File;
}

/**
 * Upload SAT FIEL credentials
 */
export async function uploadSATCredentials(
  request: UploadCredentialsRequest
): Promise<SATCredentials> {
  const formData = new FormData();
  formData.append('rfc', request.rfc);
  formData.append('sat_password', request.sat_password);
  formData.append('fiel_password', request.fiel_password);
  formData.append('cer_file', request.cer_file);
  formData.append('key_file', request.key_file);

  const token = getAuthToken();

  const response = await fetch(`${API_BASE_URL}/sat/credentials/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload SAT credentials');
  }

  return response.json();
}

/**
 * Get SAT credentials for a company
 */
export async function getSATCredentials(companyId: number): Promise<SATCredentials | null> {
  const token = getAuthToken();

  const response = await fetch(`${API_BASE_URL}/sat/credentials/${companyId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (response.status === 404 || response.status === 204) {
    return null;
  }

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch SAT credentials');
  }

  const data = await response.json();

  // Handle null response (no credentials)
  if (!data) {
    return null;
  }

  return data;
}

/**
 * Delete/deactivate SAT credentials
 */
export async function deleteSATCredentials(companyId: number): Promise<void> {
  const token = getAuthToken();

  const response = await fetch(`${API_BASE_URL}/sat/credentials/${companyId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete SAT credentials');
  }
}
