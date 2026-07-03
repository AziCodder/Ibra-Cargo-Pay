import client from './client';

export type ComponentHealthStatus = 'ok' | 'degraded' | 'down' | 'not_configured';

export interface SystemComponent {
  key: string;
  label: string;
  status: ComponentHealthStatus;
  detail: string;
  latency_ms?: number;
}

export interface SystemStatusResponse {
  node_role: string;
  overall_status: ComponentHealthStatus;
  components: SystemComponent[];
}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
  const res = await client.get<SystemStatusResponse>('/system/status');
  return res.data;
}
