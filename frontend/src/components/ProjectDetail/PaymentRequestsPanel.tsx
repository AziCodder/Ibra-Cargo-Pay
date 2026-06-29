import { useMemo, useState } from 'react';
import {
  Button,
  Card,
  DatePicker,
  Empty,
  Popconfirm,
  Progress,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  theme,
  message,
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listPaymentRequests, deletePaymentRequest } from '../../api/paymentRequests';
import { listItems } from '../../api/projectItems';
import { useAuth } from '../../contexts/AuthContext';
import PaymentRequestFormModal from './PaymentRequestFormModal';
import PaymentRequestDetailModal from './PaymentRequestDetailModal';
import type { PaymentRequestList, PaymentRequestPriority } from '../../types';
import { fmt } from '../../utils/format';
import {
  toListParams,
  type PaymentRequestFiltersState,
  type PaymentRequestSortBy,
  type PaymentRequestSortOrder,
  type PaymentRequestStatusFilter,
} from '../../utils/paymentRequestFilters';
import dayjs, { type Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

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
  filters: PaymentRequestFiltersState;
  updateFilters: (patch: Partial<PaymentRequestFiltersState>) => void;
}

export default function PaymentRequestsPanel({
  projectId,
  initialReqId,
  filters,
  updateFilters,
}: Props) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const { token } = useToken();
  const [showCreate, setShowCreate] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(initialReqId ?? null);

  const { data: projectItems = [] } = useQuery({
    queryKey: ['project-items', projectId],
    queryFn: () => listItems(projectId),
  });

  const listParams = useMemo(
    () => toListParams(filters, projectItems.map((i) => i.id)),
    [filters, projectItems],
  );

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ['payment-requests', projectId, listParams],
    queryFn: () => listPaymentRequests(projectId, listParams),
  });

  const dateRangeValue: [Dayjs | null, Dayjs | null] | null =
    filters.dateFrom || filters.dateTo
      ? [
          filters.dateFrom ? dayjs(filters.dateFrom) : null,
          filters.dateTo ? dayjs(filters.dateTo) : null,
        ]
      : null;

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

      <Space wrap size={[8, 8]} style={{ marginBottom: 12, width: '100%' }}>
        <RangePicker
          size="small"
          value={dateRangeValue}
          format="DD.MM.YYYY"
          placeholder={['Дата от', 'Дата до']}
          onChange={(range) => {
            updateFilters({
              dateFrom: range?.[0] ? range[0].format('YYYY-MM-DD') : null,
              dateTo: range?.[1] ? range[1].format('YYYY-MM-DD') : null,
            });
          }}
          allowEmpty={[true, true]}
        />
        <Select
          size="small"
          style={{ minWidth: 140 }}
          value={filters.statusFilter}
          onChange={(v: PaymentRequestStatusFilter) => updateFilters({ statusFilter: v })}
          options={[
            { value: 'all', label: 'Все статусы' },
            { value: 'paid', label: 'Оплачено' },
            { value: 'unpaid', label: 'Не оплачено' },
          ]}
        />
        <Select
          size="small"
          style={{ minWidth: 130 }}
          value={filters.sortBy}
          onChange={(v: PaymentRequestSortBy) => updateFilters({ sortBy: v })}
          options={[
            { value: 'created_at', label: 'По дате' },
            { value: 'total_amount', label: 'По сумме' },
            { value: 'item_name', label: 'По номенклатуре' },
          ]}
        />
        <Select
          size="small"
          style={{ width: 110 }}
          value={filters.sortOrder}
          onChange={(v: PaymentRequestSortOrder) => updateFilters({ sortOrder: v })}
          options={[
            { value: 'desc', label: '↓ Убыв.' },
            { value: 'asc', label: '↑ Возр.' },
          ]}
        />
      </Space>

      {isLoading ? (
        <Spin />
      ) : requests.length === 0 ? (
        <Empty description="Нет заявок на оплату" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {requests.map((req) => {
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
                    <Text ellipsis style={{ flex: 1, minWidth: 0 }}>
                      {req.items_names || '—'}
                    </Text>
                  </div>
                }
                extra={
                  <div
                    style={{ display: 'flex', gap: 4, alignItems: 'center' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {isCompleted && <Tag color="success" style={{ marginInlineEnd: 0 }}>Оплачено</Tag>}
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
