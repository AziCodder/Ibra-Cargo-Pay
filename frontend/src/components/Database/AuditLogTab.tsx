import { useState } from 'react';
import {
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Empty,
  theme,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { listAuditLogs } from '../../api/audit';
import { listUsers } from '../../api/users';
import type { AuditAction, AuditLog } from '../../types';
import dayjs from 'dayjs';

const { Text } = Typography;
const { useToken } = theme;

const ACTION_LABELS: Record<AuditAction, string> = {
  created: 'Создание',
  updated: 'Изменение',
  deleted: 'Удаление',
};
const ACTION_COLORS: Record<AuditAction, string> = {
  created: 'green',
  updated: 'blue',
  deleted: 'red',
};

const ENTITY_LABELS: Record<string, string> = {
  project: 'Проект',
  payment_request: 'Заявка на оплату',
  payment: 'Платёж',
  project_item: 'Позиция номенклатуры',
  project_item_requirement: 'Требование позиции',
  supplier: 'Поставщик',
  user: 'Пользователь',
  payment_request_comment: 'Комментарий',
};

const ENTITY_OPTIONS = [
  { value: 'project', label: 'Проект' },
  { value: 'payment_request', label: 'Заявка на оплату' },
  { value: 'payment', label: 'Платёж' },
  { value: 'project_item', label: 'Позиция номенклатуры' },
  { value: 'project_item_requirement', label: 'Требование позиции' },
  { value: 'supplier', label: 'Поставщик' },
  { value: 'user', label: 'Пользователь' },
  { value: 'payment_request_comment', label: 'Комментарий' },
];

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v);
  if (typeof v === 'string') return v.length > 80 ? v.slice(0, 80) + '…' : v;
  return String(v);
}

function renderChangesSummary(log: AuditLog): string {
  if (!log.changes) return '';
  const entries = Object.entries(log.changes);
  if (log.action === 'updated') {
    const fields = entries
      .filter(([k]) => k !== 'after' && k !== 'before')
      .map(([k]) => k);
    if (fields.length === 0) return '';
    return fields.slice(0, 4).join(', ') + (fields.length > 4 ? '…' : '');
  }
  if (log.action === 'created' && log.changes.after && typeof log.changes.after === 'object') {
    const after = log.changes.after as Record<string, unknown>;
    const name = (after.name ?? after.full_name ?? after.login ?? after.text) as unknown;
    return name ? formatValue(name) : '';
  }
  if (log.action === 'deleted' && log.changes.before && typeof log.changes.before === 'object') {
    const before = log.changes.before as Record<string, unknown>;
    const name = (before.name ?? before.full_name ?? before.login ?? before.text) as unknown;
    return name ? formatValue(name) : '';
  }
  return '';
}

interface DiffField {
  field: string;
  old: unknown;
  new: unknown;
}

function extractDiff(log: AuditLog): DiffField[] {
  if (!log.changes) return [];
  if (log.action === 'updated') {
    return Object.entries(log.changes)
      .filter(([k]) => k !== 'after' && k !== 'before')
      .map(([field, val]) => {
        if (val && typeof val === 'object' && 'old' in val && 'new' in val) {
          const obj = val as { old: unknown; new: unknown };
          return { field, old: obj.old, new: obj.new };
        }
        return { field, old: undefined, new: val };
      });
  }
  if (log.action === 'created' && log.changes.after) {
    const after = log.changes.after as Record<string, unknown>;
    return Object.entries(after).map(([field, value]) => ({ field, old: undefined, new: value }));
  }
  if (log.action === 'deleted' && log.changes.before) {
    const before = log.changes.before as Record<string, unknown>;
    return Object.entries(before).map(([field, value]) => ({ field, old: value, new: undefined }));
  }
  return [];
}

export default function AuditLogTab() {
  const { token } = useToken();
  const [entityType, setEntityType] = useState<string | undefined>(undefined);
  const [userId, setUserId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', entityType, userId, page],
    queryFn: () =>
      listAuditLogs({
        entity_type: entityType,
        user_id: userId,
        page,
        pageSize,
      }),
  });

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
  });

  const columns: ColumnsType<AuditLog> = [
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => dayjs(v).format('DD.MM.YYYY HH:mm:ss'),
    },
    {
      title: 'Пользователь',
      key: 'user',
      width: 200,
      render: (_: unknown, r: AuditLog) =>
        r.user_full_name ? (
          <div>
            <div>{r.user_full_name}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {r.user_login}
            </Text>
          </div>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: 'Действие',
      dataIndex: 'action',
      key: 'action',
      width: 120,
      render: (a: AuditAction) => <Tag color={ACTION_COLORS[a]}>{ACTION_LABELS[a]}</Tag>,
    },
    {
      title: 'Сущность',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 180,
      render: (v: string, r: AuditLog) => (
        <div>
          <div>{ENTITY_LABELS[v] ?? v}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            ID: {r.entity_id}
          </Text>
        </div>
      ),
    },
    {
      title: 'Изменения',
      key: 'changes',
      render: (_: unknown, r: AuditLog) => (
        <Text ellipsis style={{ maxWidth: 400 }}>
          {renderChangesSummary(r) || '—'}
        </Text>
      ),
    },
  ];

  const userOptions = (usersData?.items ?? []).map((u) => ({
    value: u.id,
    label: `${u.full_name} (${u.login})`,
  }));

  return (
    <div>
      {/* Фильтры */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          placeholder="Тип сущности"
          allowClear
          style={{ width: 220 }}
          value={entityType}
          onChange={(v) => {
            setEntityType(v);
            setPage(1);
          }}
          options={ENTITY_OPTIONS}
        />
        <Select
          placeholder="Пользователь"
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 260 }}
          value={userId}
          onChange={(v) => {
            setUserId(v);
            setPage(1);
          }}
          options={userOptions}
        />
      </Space>

      <Table
        rowKey="id"
        size="small"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        locale={{ emptyText: <Empty description="Нет записей" /> }}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          showSizeChanger: false,
          onChange: (p) => setPage(p),
        }}
        expandable={{
          expandedRowRender: (record: AuditLog) => {
            const diff = extractDiff(record);
            if (diff.length === 0) {
              return (
                <Text type="secondary">Нет детальной информации об изменениях</Text>
              );
            }
            return (
              <div
                style={{
                  background: token.colorFillTertiary,
                  padding: 12,
                  borderRadius: token.borderRadius,
                }}
              >
                <Table
                  size="small"
                  rowKey="field"
                  pagination={false}
                  dataSource={diff}
                  columns={[
                    {
                      title: 'Поле',
                      dataIndex: 'field',
                      key: 'field',
                      width: 200,
                      render: (v: string) => <Text code>{v}</Text>,
                    },
                    {
                      title: 'Было',
                      dataIndex: 'old',
                      key: 'old',
                      render: (v: unknown) => (
                        <Text type="secondary" style={{ fontSize: 13 }}>
                          {formatValue(v)}
                        </Text>
                      ),
                    },
                    {
                      title: 'Стало',
                      dataIndex: 'new',
                      key: 'new',
                      render: (v: unknown) => (
                        <Text style={{ fontSize: 13 }}>{formatValue(v)}</Text>
                      ),
                    },
                  ]}
                />
              </div>
            );
          },
        }}
      />
    </div>
  );
}
