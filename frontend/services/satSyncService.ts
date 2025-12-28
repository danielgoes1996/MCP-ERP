/**
 * SAT Sync Configuration Service
 *
 * Handles API calls for SAT auto-sync configuration
 */

import { useAuthStore } from '@/stores/auth/useAuthStore';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get auth token from Zustand store
 */
function getAuthToken(): string | null {
  return useAuthStore.getState().token;
}

// Types
export interface SATSyncConfig {
  id: number;
  company_id: number;
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  day_of_week: number | null;  // 0=Monday, 6=Sunday
  time: string;  // "HH:MM" format
  lookback_days: number;
  auto_classify: boolean;
  notify_email: boolean;
  notify_threshold: number;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_count: number;
  last_sync_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SATSyncConfigCreate {
  company_id: number;
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  day_of_week?: number | null;
  time: string;
  lookback_days: number;
  auto_classify: boolean;
  notify_email: boolean;
  notify_threshold: number;
}

export interface SyncHistory {
  sync_at: string | null;
  status: string | null;
  count: number;
  error: string | null;
}

export interface ScheduledJob {
  id: string;
  name: string;
  next_run: string | null;
  trigger: string;
}

/**
 * Get SAT sync configuration for a company
 */
export async function getSATSyncConfig(companyId: number): Promise<SATSyncConfig> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/config/${companyId}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Configuration not found');
    }
    throw new Error(`Failed to fetch SAT sync config: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create or update SAT sync configuration
 */
export async function saveSATSyncConfig(config: SATSyncConfigCreate): Promise<SATSyncConfig> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/config`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to save SAT sync config: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Trigger manual sync for a company
 */
export async function triggerManualSync(companyId: number): Promise<{ success: boolean; message: string }> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/manual-sync`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ company_id: companyId }),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to trigger manual sync: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get sync history for a company
 */
export async function getSyncHistory(companyId: number): Promise<{ company_id: number; history: SyncHistory[] }> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/sync-history/${companyId}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch sync history: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get scheduled jobs from the scheduler
 */
export async function getScheduledJobs(): Promise<{ success: boolean; scheduler_running: boolean; jobs: ScheduledJob[] }> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/scheduled-jobs`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch scheduled jobs: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Reload scheduler manually
 */
export async function reloadScheduler(): Promise<{ success: boolean; message: string }> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_BASE_URL}/sat/sync-config/reload-scheduler`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to reload scheduler: ${response.statusText}`);
  }

  return response.json();
}
