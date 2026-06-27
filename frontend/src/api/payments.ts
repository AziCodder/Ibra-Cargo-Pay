import client from './client';
import type { Payment } from '../types';

export async function listPayments(reqId: number): Promise<Payment[]> {
  const res = await client.get<Payment[]>(`/payment-requests/${reqId}/payments`);
  return res.data;
}

export async function addPayment(
  reqId: number,
  data: { amount: number; currency: string; note?: string | null; payment_date?: string | null; file?: File | null },
): Promise<Payment> {
  const formData = new FormData();
  formData.append('amount', String(data.amount));
  formData.append('currency', data.currency);
  if (data.note) formData.append('note', data.note);
  if (data.payment_date) formData.append('payment_date', data.payment_date);
  if (data.file) formData.append('file', data.file);
  const res = await client.post<Payment>(`/payment-requests/${reqId}/payments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function deletePayment(reqId: number, payId: number): Promise<void> {
  await client.delete(`/payment-requests/${reqId}/payments/${payId}`);
}

export async function updatePayment(
  reqId: number,
  payId: number,
  data: { payment_date?: string | null },
): Promise<Payment> {
  const res = await client.patch<Payment>(
    `/payment-requests/${reqId}/payments/${payId}`,
    data,
  );
  return res.data;
}

export async function downloadPaymentsZip(reqId: number): Promise<void> {
  const res = await client.get(`/payment-requests/${reqId}/payments/download-zip`, {
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([res.data as BlobPart]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `payments_${reqId}.zip`);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export async function downloadAllProjectPaymentsZip(projectId: number): Promise<void> {
  const res = await client.get(`/projects/${projectId}/payments/download-all-zip`, {
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([res.data as BlobPart]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `payments_project_${projectId}.zip`);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
}
