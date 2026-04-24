import client from './client';
import type { LoginRequest, TokenResponse, User } from '../types';

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await client.post<TokenResponse>('/auth/login', data);
  return response.data;
}

export async function getMe(): Promise<User> {
  const response = await client.get<User>('/auth/me');
  return response.data;
}
