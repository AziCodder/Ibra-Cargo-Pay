import client from './client';
import type { PaymentRequestComment } from '../types';

export async function listComments(reqId: number): Promise<PaymentRequestComment[]> {
  const res = await client.get<PaymentRequestComment[]>(
    `/payment-requests/${reqId}/comments`,
  );
  return res.data;
}

export async function addComment(
  reqId: number,
  text: string,
): Promise<PaymentRequestComment> {
  const res = await client.post<PaymentRequestComment>(
    `/payment-requests/${reqId}/comments`,
    { text },
  );
  return res.data;
}

export async function deleteComment(reqId: number, commentId: number): Promise<void> {
  await client.delete(`/payment-requests/${reqId}/comments/${commentId}`);
}
