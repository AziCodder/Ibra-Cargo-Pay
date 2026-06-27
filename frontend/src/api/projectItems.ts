import client from './client';
import type { ProjectItem, ProjectItemCreate, ProjectItemUpdate, Requirement } from '../types';

export async function listItems(projectId: number): Promise<ProjectItem[]> {
  const res = await client.get<ProjectItem[]>(`/projects/${projectId}/items`);
  return res.data;
}

export async function getItem(projectId: number, itemId: number): Promise<ProjectItem> {
  const res = await client.get<ProjectItem>(`/projects/${projectId}/items/${itemId}`);
  return res.data;
}

export async function createItem(
  projectId: number,
  data: ProjectItemCreate,
): Promise<ProjectItem> {
  const res = await client.post<ProjectItem>(`/projects/${projectId}/items`, data);
  return res.data;
}

export async function updateItem(
  projectId: number,
  itemId: number,
  data: ProjectItemUpdate,
): Promise<ProjectItem> {
  const res = await client.put<ProjectItem>(`/projects/${projectId}/items/${itemId}`, data);
  return res.data;
}

export async function deleteItem(projectId: number, itemId: number): Promise<void> {
  await client.delete(`/projects/${projectId}/items/${itemId}`);
}

export async function reorderItems(
  projectId: number,
  itemIds: number[],
): Promise<void> {
  await client.post(`/projects/${projectId}/items/reorder`, { item_ids: itemIds });
}

// Требования
export async function listRequirements(
  projectId: number,
  itemId: number,
): Promise<Requirement[]> {
  const res = await client.get<Requirement[]>(
    `/projects/${projectId}/items/${itemId}/requirements`,
  );
  return res.data;
}

export async function addRequirement(
  projectId: number,
  itemId: number,
  text: string,
): Promise<Requirement> {
  const res = await client.post<Requirement>(
    `/projects/${projectId}/items/${itemId}/requirements`,
    { text },
  );
  return res.data;
}

export async function deleteRequirement(
  projectId: number,
  itemId: number,
  reqId: number,
): Promise<void> {
  await client.delete(`/projects/${projectId}/items/${itemId}/requirements/${reqId}`);
}

// Импорт позиций из Excel

export interface ImportResult {
  created: number;
  errors: Array<{ row: number; message: string }>;
}

export async function downloadItemsTemplate(projectId: number): Promise<void> {
  const res = await client.get(`/projects/${projectId}/items/import-template`, {
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'items_template.xlsx');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function importItems(
  projectId: number,
  file: File,
): Promise<ImportResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await client.post<ImportResult>(
    `/projects/${projectId}/items/import`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return res.data;
}
