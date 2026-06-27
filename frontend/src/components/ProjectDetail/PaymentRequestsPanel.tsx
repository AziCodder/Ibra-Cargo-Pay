import { useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Popconfirm,
  Progress,
  Spin,
  Tag,
  Typography,
  theme,
  message,
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listPaymentRequests, deletePaymentRequest } from '../../api/paymentRequests';
import { useAuth } from '../../contexts/AuthContext';
import PaymentRequestFormModal from './PaymentRequestFormModal';
import PaymentRequestDetailModal from './PaymentRequestDetailModal';
import type { PaymentRequestList, PaymentRequestPriority } from '../../types';
import { fmt } from '../../utils/format';
import dayjs from 'dayjs';

const PRIORITY_LABEL: Record<PaymentRequestPriority, string> = {
  urgent: 'Срочно',
  normal: 'Обычно',
  deferred: 'Отложено',
};
const PRIORITY_COLOR: Record<PaymentRequestPriority, string> = {
  urgent: 'red',
  normal: 'blue',
  deferred: 'default',
};
const PRIORITY_SORT: Record<PaymentRequestPriority, number> = {
  urgent: 0,
  normal: 1,
  deferred: 2,
};

function renderDueDate(due: string | null | undefined): {
  label: string;
  color: string;
} | null {
  if (!due) return null;
  const date = dayjs(due).startOf('day');
  const today = dayjs().startOf('day');
  const diff = date.diff(today, 'day');
  const label = date.format('DD.MM.YYYY');
  if (diff < 0) return { label: `Просрочено: ${label}`, color: 'red' };
  if (diff === 0) return { label: `Сегодня: ${label}`, color: 'orange' };
  if (diff <= 3) return { label: `До ${label}`, color: 'gold' };
  return { label: `До ${label}`, color: 'green' };
}

const { Text } = Typography;
const { useToken } = theme;

interface Props {
  projectId: number;
  initialReqId?: number;
}

export default function PaymentRequestsPanel({ projectId, initialReqId }: Props) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const { token } = useToken();
  const [showCreate, setShowCreate] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(initialReqId ?? null);

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ['payment-requests', projectId],
    queryFn: () => listPaymentRequests(projectId),
  });

  const handleDelete = async (req: PaymentRequestList) => {
    try {
      await deletePaymentRequest(projectId, req.id);
      queryClient.invalidateQueries({ queryKey: ['payment-requests', projectId] });
      queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      message.success('Заявка удалена');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  return (
    <div style={{ padding: '16px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <Text strong style={{ fontSize: 15 }}>
          Заявки на оплату
        </Text>
        <Button
          size="small"
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setShowCreate(true)}
        >
          Создать заявку
        </Button>
      </div>

      {isLoading ? (
        <Spin />
      ) : requests.length === 0 ? (
        <Empty description="Нет заявок на оплату" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[...requests]
            .sort((a, b) => {
              const pa = PRIORITY_SORT[a.priority] ?? 1;
              const pb = PRIORITY_SORT[b.priority] ?? 1;
              if (pa !== pb) return pa - pb;
              if (a.due_date && b.due_date) {
                return dayjs(a.due_date).valueOf() - dayjs(b.due_date).valueOf();
              }
              if (a.due_date && !b.due_date) return -1;
              if (!a.due_date && b.due_date) return 1;
              return dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf();
            })
            .map((req) => {
            const total = parseFloat(req.total_amount);
            const remaining = parseFloat(req.remaining_amount);
            const paid = total - remaining;
            const percent = total > 0 ? Math.round((paid / total) * 100) : 0;
            const isCompleted = remaining <= 0;

            const deadline = renderDueDate(req.due_date);

            return (
              <Card
                key={req.id}
                size="small"
                style={{
                  borderColor: isCompleted ? token.colorSuccess : undefined,
                  cursor: 'pointer',
                }}
                onClick={() => setDetailId(req.id)}
                title={
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Tag color={req.currency === 'CNY' ? 'orange' : req.currency === 'USD' ? 'blue' : 'purple'}>
                      {req.currency}
                    </Tag>
                    <Text ellipsis style={{ flex: 1, maxWidth: 240 }}>
                      {req.items_names || '—'}
                    </Text>
                    {isCompleted && <Tag color="success">Оплачено</Tag>}
                  </div>
                }
                extra={
                  <div
                    style={{ display: 'flex', gap: 4 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {(req.can_edit || isAdmin) && (
                      <Popconfirm
                        title="Удалить заявку?"
                        description="Заявку без платежей можно удалить."
                        okText="Удалить"
                        cancelText="Отмена"
                        onConfirm={() => handleDelete(req)}
                      >
                        <Button size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    )}
                  </div>
                }
              >
                <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
                  <Tag color={PRIORITY_COLOR[req.priority]}>
                    {PRIORITY_LABEL[req.priority]}
                  </Tag>
                  {deadline && <Tag color={deadline.color}>{deadline.label}</Tag>}
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: 6,
                    flexWrap: 'wrap',
                    gap: 8,
                  }}
                >
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      Всего:{' '}
                    </Text>
                    <Text strong>{fmt(req.total_amount, req.currency)}</Text>
                  </div>
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      Фактически оплачено:{' '}
                    </Text>
                    <Text>
                      {fmt(req.paid_amount ?? String(paid), req.currency)}
                    </Text>
                  </div>
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      Остаток:{' '}
                    </Text>
                    <Text type={isCompleted ? 'success' : 'danger'}>
                      {fmt(req.remaining_amount, req.currency)}
                    </Text>
                  </div>
                </div>
                <Progress
                  percent={percent}
                  size="small"
                  status={isCompleted ? 'success' : 'active'}
                  showInfo={false}
                />
              </Card>
            );
          })}
        </div>
      )}

      {showCreate && (
        <PaymentRequestFormModal
          open={showCreate}
          projectId={projectId}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            queryClient.invalidateQueries({ queryKey: ['payment-requests', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
          }}
        />
      )}

      {detailId !== null && (
        <PaymentRequestDetailModal
          open={detailId !== null}
          projectId={projectId}
          reqId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => {
            queryClient.invalidateQueries({ queryKey: ['payment-requests', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
          }}
        />
      )}
    </div>
  );
}
