import client from './client';
import type { Supplier, SupplierBrief, SupplierCreate, SupplierListOut, SupplierUpdate } from '../types';

export async function listSuppliersBrief(): Promise<SupplierBrief[]> {
  const res = await client.get<SupplierBrief[]>('/suppliers/brief');
  return res.data;
}

export async function listSuppliers(page = 1, pageSize = 50): Promise<SupplierListOut> {
  const res = await client.get<SupplierListOut>('/suppliers', {
    params: { page, page_size: pageSize },
  });
  return res.data;
}

export async function getSupplier(id: number): Promise<Supplier> {
  const res = await client.get<Supplier>(`/suppliers/${id}`);
  return res.data;
}

export async function createSupplier(data: SupplierCreate): Promise<Supplier> {
  const res = await client.post<Supplier>('/suppliers', data);
  return res.data;
}

export async function updateSupplier(id: number, data: SupplierUpdate): Promise<Supplier> {
  const res = await client.put<Supplier>(`/suppliers/${id}`, data);
  return res.data;
}

export async function deleteSupplier(id: number): Promise<void> {
  await client.delete(`/suppliers/${id}`);
}

export async function uploadSupplierDocument(
  supplierId: number,
  slot: number,
  file: File,
): Promise<Supplier> {
  const formData = new FormData();
  formData.append('slot', String(slot));
  formData.append('file', file);
  const res = await client.post<Supplier>(`/suppliers/${supplierId}/documents`, formData);
  return res.data;
}

export async function deleteSupplierDocument(
  supplierId: number,
  slot: number,
): Promise<Supplier> {
  const res = await client.delete<Supplier>(`/suppliers/${supplierId}/documents/${slot}`);
  return res.data;
}
