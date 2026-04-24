import client from './client';
import type { DashboardSummary } from '../types';

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = await client.get<DashboardSummary>('/dashboard/summary');
  return res.data;
}
