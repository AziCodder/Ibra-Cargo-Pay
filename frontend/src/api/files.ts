import client from './client';

export async function getFileDownloadUrl(key: string): Promise<string> {
  const res = await client.get<{ url: string }>('/files/download-url', { params: { key } });
  return res.data.url;
}
