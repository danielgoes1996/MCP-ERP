/**
 * Projects Service
 *
 * API client for project management endpoints
 */

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

export interface Project {
  id: number;
  name: string;
  description?: string;
  budget_mxn?: number;
  company_id?: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

/**
 * Get all projects
 */
export async function getProjects(): Promise<Project[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/projects`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      console.error('Error fetching projects:', response.statusText);
      return [];
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching projects:', error);
    return [];
  }
}

/**
 * Get project by ID
 */
export async function getProject(id: number): Promise<Project | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/projects/${id}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      console.error('Error fetching project:', response.statusText);
      return null;
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching project:', error);
    return null;
  }
}

/**
 * Create a new project
 */
export async function createProject(data: Partial<Project>): Promise<Project> {
  const response = await fetch(`${API_BASE_URL}/api/v1/projects`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Error creating project: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update an existing project
 */
export async function updateProject(id: number, data: Partial<Project>): Promise<Project> {
  const response = await fetch(`${API_BASE_URL}/api/v1/projects/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Error updating project: ${response.statusText}`);
  }

  return response.json();
}
