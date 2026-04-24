import client from './client';

export interface BackupItem {
  key: string;
  size_bytes: number;
  last_modified: string | null;
}

export interface BackupListResponse {
  configured: boolean;
  bucket?: string;
  retention_days?: number;
  items: BackupItem[];
}

export interface BackupRunResult {
  key: string;
  size_bytes: number;
  started_at: string;
  finished_at: string;
  deleted_old_count: number;
  bucket: string;
}

export async function listBackups(limit = 50): Promise<BackupListResponse> {
  const res = await client.get<BackupListResponse>('/backups', { params: { limit } });
  return res.data;
}

export async function runBackupNow(): Promise<BackupRunResult> {
  const res = await client.post<BackupRunResult>('/backups/run-admin');
  return res.data;
}

export async function getBackupDownloadUrl(key: string): Promise<string> {
  const res = await client.get<{ url: string }>('/backups/download-url', {
    params: { key },
  });
  return res.data.url;
}
