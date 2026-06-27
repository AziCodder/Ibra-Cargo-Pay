import client from './client';
import type { ProjectNote, ProjectNoteCreate, ProjectNoteUpdate } from '../types';

export async function listProjectNotes(projectId: number): Promise<ProjectNote[]> {
  const res = await client.get<ProjectNote[]>(`/projects/${projectId}/notes`);
  return res.data;
}

export async function createProjectNote(
  projectId: number,
  data: ProjectNoteCreate,
): Promise<ProjectNote> {
  const res = await client.post<ProjectNote>(`/projects/${projectId}/notes`, data);
  return res.data;
}

export async function updateProjectNote(
  projectId: number,
  noteId: number,
  data: ProjectNoteUpdate,
): Promise<ProjectNote> {
  const res = await client.put<ProjectNote>(
    `/projects/${projectId}/notes/${noteId}`,
    data,
  );
  return res.data;
}

export async function deleteProjectNote(projectId: number, noteId: number): Promise<void> {
  await client.delete(`/projects/${projectId}/notes/${noteId}`);
}
