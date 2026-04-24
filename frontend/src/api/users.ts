import client from './client';
import type { User, UserCreate, UserListOut, UserUpdate } from '../types';

export async function listUsers(page = 1, pageSize = 50): Promise<UserListOut> {
  const res = await client.get<UserListOut>('/users', { params: { page, page_size: pageSize } });
  return res.data;
}

export async function getUser(id: number): Promise<User> {
  const res = await client.get<User>(`/users/${id}`);
  return res.data;
}

export async function createUser(data: UserCreate): Promise<User> {
  const res = await client.post<User>('/users', data);
  return res.data;
}

export async function updateUser(id: number, data: UserUpdate): Promise<User> {
  const res = await client.put<User>(`/users/${id}`, data);
  return res.data;
}

export async function deleteUser(id: number): Promise<void> {
  await client.delete(`/users/${id}`);
}

export async function generateTelegramLink(id: number): Promise<{ token: string }> {
  const res = await client.post<{ token: string }>(`/users/${id}/telegram-link`);
  return res.data;
}
