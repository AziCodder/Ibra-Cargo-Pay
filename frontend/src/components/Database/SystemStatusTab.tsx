import { Alert, Button, Card, Col, Row, Space, Tag, Typography, theme } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  getSystemStatus,
  type ComponentHealthStatus,
  type SystemComponent,
} from '../../api/systemStatus';

const { Text } = Typography;
const { useToken } = theme;

const STATUS_COLOR: Record<ComponentHealthStatus, string> = {
  ok: 'success',
  degraded: 'warning',
  down: 'error',
  not_configured: 'default',
};

const STATUS_LABEL: Record<ComponentHealthStatus, string> = {
  ok: 'Работает',
  degraded: 'Есть проблемы',
  down: 'Недоступен',
  not_configured: 'Не настроен',
};

function ComponentCard({ c }: { c: SystemComponent }) {
  const { token } = useToken();
  return (
    <Col xs={24} sm={12} md={8}>
      <Card size="small">
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Text strong>{c.label}</Text>
            <Tag color={STATUS_COLOR[c.status]}>{STATUS_LABEL[c.status]}</Tag>
          </Space>
          <Text type="secondary" style={{ fontSize: 12, wordBreak: 'break-word' }}>
            {c.detail}
            {c.latency_ms !== undefined && (
              <span style={{ color: token.colorTextTertiary }}> · {c.latency_ms} мс</span>
            )}
          </Text>
        </Space>
      </Card>
    </Col>
  );
}

export default function SystemStatusTab() {
  const { data, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ['system-status'],
    queryFn: getSystemStatus,
    refetchInterval: 15_000,
  });

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isFetching}>
          Обновить
        </Button>
        {data && (
          <Tag color={STATUS_COLOR[data.overall_status]} style={{ fontSize: 13, padding: '2px 10px' }}>
            Общий статус: {STATUS_LABEL[data.overall_status]}
          </Tag>
        )}
        {data && <Tag>Роль этого сервера: {data.node_role}</Tag>}
      </Space>

      {error && (
        <Alert
          type="error"
          showIcon
          message="Не удалось получить статус системы"
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        {(data?.components ?? []).map((c) => (
          <ComponentCard key={c.key} c={c} />
        ))}
      </Row>

      {!isLoading && data?.components.length === 0 && (
        <Text type="secondary">Нет данных о компонентах.</Text>
      )}
    </div>
  );
}
