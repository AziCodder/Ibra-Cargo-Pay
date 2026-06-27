import client from './client';
import type {
  Attachment,
  PaymentRequest,
  PaymentRequestCreate,
  PaymentRequestList,
  PaymentRequestUpdate,
} from '../types';

export type PaymentRequestSortBy = 'created_at' | 'total_amount' | 'item_name';
export type PaymentRequestSortOrder = 'asc' | 'desc';
export type PaymentRequestStatusFilter = 'all' | 'paid' | 'unpaid';

export interface PaymentRequestListParams {
  sort_by?: PaymentRequestSortBy;
  sort_order?: PaymentRequestSortOrder;
  status_filter?: PaymentRequestStatusFilter;
  date_from?: string;
  date_to?: string;
  item_ids?: number[];
}

export async function listPaymentRequests(
  projectId: number,
  params?: PaymentRequestListParams,
): Promise<PaymentRequestList[]> {
  const query: Record<string, string> = {};
  if (params?.sort_by) query.sort_by = params.sort_by;
  if (params?.sort_order) query.sort_order = params.sort_order;
  if (params?.status_filter) query.status_filter = params.status_filter;
  if (params?.date_from) query.date_from = params.date_from;
  if (params?.date_to) query.date_to = params.date_to;
  if (params?.item_ids?.length) query.item_ids = params.item_ids.join(',');

  const res = await client.get<PaymentRequestList[]>(
    `/projects/${projectId}/payment-requests`,
    { params: query },
  );
  return res.data;
}

export async function getPaymentRequest(
  projectId: number,
  reqId: number,
): Promise<PaymentRequest> {
  const res = await client.get<PaymentRequest>(
    `/projects/${projectId}/payment-requests/${reqId}`,
  );
  return res.data;
}

export async function createPaymentRequest(
  projectId: number,
  data: PaymentRequestCreate,
): Promise<PaymentRequest> {
  const res = await client.post<PaymentRequest>(
    `/projects/${projectId}/payment-requests`,
    data,
  );
  return res.data;
}

export async function updatePaymentRequest(
  projectId: number,
  reqId: number,
  data: PaymentRequestUpdate,
): Promise<PaymentRequest> {
  const res = await client.put<PaymentRequest>(
    `/projects/${projectId}/payment-requests/${reqId}`,
    data,
  );
  return res.data;
}

export async function deletePaymentRequest(
  projectId: number,
  reqId: number,
): Promise<void> {
  await client.delete(`/projects/${projectId}/payment-requests/${reqId}`);
}

export async function uploadAttachment(
  projectId: number,
  reqId: number,
  file: File,
): Promise<Attachment> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await client.post<Attachment>(
    `/projects/${projectId}/payment-requests/${reqId}/attachments`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return res.data;
}

export async function deleteAttachment(
  projectId: number,
  reqId: number,
  attId: number,
): Promise<void> {
  await client.delete(
    `/projects/${projectId}/payment-requests/${reqId}/attachments/${attId}`,
  );
}
