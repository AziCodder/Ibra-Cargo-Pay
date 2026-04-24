import client from './client';
import type { AuditLogListOut } from '../types';

export async function listAuditLogs(params?: {
  entity_type?: string;
  user_id?: number;
  entity_id?: number;
  page?: number;
  pageSize?: number;
}): Promise<AuditLogListOut> {
  const res = await client.get<AuditLogListOut>('/audit', {
    params: {
      entity_type: params?.entity_type,
      user_id: params?.user_id,
      entity_id: params?.entity_id,
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 50,
    },
  });
  return res.data;
}
