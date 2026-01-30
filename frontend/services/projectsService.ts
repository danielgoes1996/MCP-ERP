import api from './api';

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

export async function getProjects(): Promise<Project[]> {
  try {
    const response = await api.get('/api/v1/projects');
    return response.data;
  } catch (error) {
    console.error('Error fetching projects:', error);
    return [];
  }
}

export async function getProject(id: number): Promise<Project | null> {
  try {
    const response = await api.get(`/api/v1/projects/${id}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching project:', error);
    return null;
  }
}

export async function createProject(data: Partial<Project>): Promise<Project> {
  const response = await api.post('/api/v1/projects', data);
  return response.data;
}

export async function updateProject(id: number, data: Partial<Project>): Promise<Project> {
  const response = await api.put(`/api/v1/projects/${id}`, data);
  return response.data;
}
