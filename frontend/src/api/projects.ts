import client from './client';
import type {
  Project,
  ProjectCreate,
  ProjectListOut,
  ProjectSummary,
  ProjectUpdate,
} from '../types';

export type ProjectSortBy = 'name' | 'created_at';
export type ProjectSortOrder = 'asc' | 'desc';

export async function listProjects(params?: {
  status?: string;
  page?: number;
  pageSize?: number;
  sortBy?: ProjectSortBy;
  sortOrder?: ProjectSortOrder;
}): Promise<ProjectListOut> {
  const res = await client.get<ProjectListOut>('/projects', {
    params: {
      status: params?.status,
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 50,
      sort_by: params?.sortBy,
      sort_order: params?.sortOrder,
    },
  });
  return res.data;
}

export async function getProject(id: number): Promise<Project> {
  const res = await client.get<Project>(`/projects/${id}`);
  return res.data;
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  const res = await client.post<Project>('/projects', data);
  return res.data;
}

export async function updateProject(id: number, data: ProjectUpdate): Promise<Project> {
  const res = await client.put<Project>(`/projects/${id}`, data);
  return res.data;
}

export async function deleteProject(id: number): Promise<void> {
  await client.delete(`/projects/${id}`);
}

export async function getProjectSummary(id: number): Promise<ProjectSummary> {
  const res = await client.get<ProjectSummary>(`/projects/${id}/summary`);
  return res.data;
}

export async function downloadProjectExport(
  id: number,
  projectNumber: number
): Promise<void> {
  const res = await client.get(`/projects/${id}/export`, {
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `project_${projectNumber}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
