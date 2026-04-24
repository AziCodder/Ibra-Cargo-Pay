import {
  Card,
  Col,
  Empty,
  List,
  Row,
  Spin,
  Statistic,
  Tag,
  Typography,
  theme,
} from 'antd';
import {
  CheckCircleOutlined,
  FolderOpenOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { getDashboardSummary } from '../api/dashboard';
import { fmt } from '../utils/format';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { useToken } = theme;

const CURRENCY_COLOR: Record<string, string> = {
  CNY: 'orange',
  USD: 'blue',
  RUB: 'purple',
};

export default function DashboardPage() {
  const { token } = useToken();
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: getDashboardSummary,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          paddingTop: 80,
          minHeight: '100vh',
          background: token.colorBgLayout,
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100vh' }}>
      <Title level={3} style={{ marginTop: 0, marginBottom: 24 }}>
        Главная
      </Title>

      {/* Счётчики */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic
              title="Активные проекты"
              value={data.projects_active}
              prefix={<FolderOpenOutlined style={{ color: token.colorPrimary }} />}
              valueStyle={{ color: token.colorPrimary }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic
              title="Закрытые проекты"
              value={data.projects_closed}
              prefix={<InboxOutlined style={{ color: token.colorTextSecondary }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic
              title="Закрытые заявки"
              value={data.completed_requests}
              prefix={<CheckCircleOutlined style={{ color: token.colorSuccess }} />}
              valueStyle={{ color: token.colorSuccess }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* Остатки по валютам */}
        <Col xs={24} md={10}>
          <Card size="small" title="Остатки по валютам">
            {data.remaining_by_currency.length === 0 ? (
              <Empty description="Нет данных" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {data.remaining_by_currency.map((b) => (
                  <div
                    key={b.currency}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 10px',
                      background: token.colorFillTertiary,
                      borderRadius: token.borderRadius,
                    }}
                  >
                    <Tag color={CURRENCY_COLOR[b.currency]}>{b.currency}</Tag>
                    <div style={{ textAlign: 'right' }}>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Всего:{' '}
                        </Text>
                        <Text strong>{fmt(b.total, b.currency)}</Text>
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Оплачено:{' '}
                        </Text>
                        <Text>{fmt(b.paid, b.currency)}</Text>
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Остаток:{' '}
                        </Text>
                        <Text
                          type={parseFloat(b.remaining) > 0 ? 'danger' : 'success'}
                        >
                          {fmt(b.remaining, b.currency)}
                        </Text>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>

        {/* Последние платежи */}
        <Col xs={24} md={14}>
          <Card size="small" title="Последние платежи">
            {data.recent_payments.length === 0 ? (
              <Empty description="Нет платежей" />
            ) : (
              <List
                size="small"
                dataSource={data.recent_payments}
                renderItem={(p) => (
                  <List.Item
                    key={p.id}
                    style={{ padding: '10px 0', alignItems: 'flex-start' }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          marginBottom: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Tag color={CURRENCY_COLOR[p.currency]}>{p.currency}</Tag>
                        <Text strong>{fmt(p.amount, p.currency)}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {dayjs(p.created_at).format('DD.MM.YYYY HH:mm')}
                        </Text>
                      </div>
                      <div style={{ fontSize: 13 }}>
                        <Text type="secondary">Проект: </Text>
                        <Text>
                          №{p.project_number} · {p.project_name}
                        </Text>
                      </div>
                      <div style={{ fontSize: 12 }}>
                        <Text type="secondary">
                          Добавил: {p.created_by_full_name}
                        </Text>
                        {p.note && (
                          <>
                            <Text type="secondary"> · </Text>
                            <Text type="secondary">{p.note}</Text>
                          </>
                        )}
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
