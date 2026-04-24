import client from './client';
import type {
  Attachment,
  PaymentRequest,
  PaymentRequestCreate,
  PaymentRequestList,
  PaymentRequestUpdate,
} from '../types';

export async function listPaymentRequests(projectId: number): Promise<PaymentRequestList[]> {
  const res = await client.get<PaymentRequestList[]>(
    `/projects/${projectId}/payment-requests`,
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
