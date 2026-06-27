import { useState } from 'react';
import {
  Button,
  Divider,
  Modal,
  Switch,
  Table,
  Typography,
  Spin,
  Empty,
  List,
  Upload,
  Space,
  message,
  Popconfirm,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  DownloadOutlined,
  UploadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons';
import type { RcFile } from 'antd/es/upload';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listItems,
  deleteItem,
  updateItem,
  moveItemUp,
  moveItemDown,
  downloadItemsTemplate,
  importItems,
  type ImportResult,
} from '../../api/projectItems';
import { getProjectSummary } from '../../api/projects';
import { useAuth } from '../../contexts/AuthContext';
import ItemFormModal from './ItemFormModal';
import ItemDetailDrawer from './ItemDetailDrawer';
import type { ProjectItem, CurrencySummary, Currency } from '../../types';
import { fmt } from '../../utils/format';

const { Text } = Typography;

function itemCanEdit(item: ProjectItem, isAdmin: boolean): boolean {
  return item.can_edit ?? (isAdmin || item.shared_access);
}

function fmtNum(v: string | number | undefined | null, decimals = 2): string {
  const n = parseFloat(String(v ?? '0'));
  return n.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function SummaryRow({ summary }: { summary: CurrencySummary }) {
  const total = parseFloat(summary.total);
  const invoiced = parseFloat(summary.invoiced ?? '0');
  const paid = parseFloat(summary.paid);
  const remaining = total - paid;
  const invoicedRemaining = invoiced - paid;
  const notInvoiced = total - invoiced;
  const currency = summary.currency as Currency;

  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)', marginBottom: 4 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', marginBottom: 2 }}>
        <Text strong style={{ marginRight: 4 }}>{summary.currency}:</Text>
        <Text style={{ fontSize: 13 }}>Итого: <Text strong>{fmt(summary.total, currency)}</Text></Text>
        <Text type="secondary" style={{ fontSize: 12 }}>·</Text>
        <Text style={{ fontSize: 13 }}>Выставлено: <Text>{fmt(String(invoiced), currency)}</Text></Text>
        <Text type="secondary" style={{ fontSize: 12 }}>·</Text>
        <Text style={{ fontSize: 13 }}>Оплачено: <Text type={paid > 0 ? undefined : 'secondary'}>{fmt(String(paid), currency)}</Text></Text>
        <Text type="secondary" style={{ fontSize: 12 }}>·</Text>
        <Text style={{ fontSize: 13 }}>
          Общий остаток:{' '}
          <Text type={remaining > 0 ? 'danger' : 'success'}>{fmt(String(remaining), currency)}</Text>
        </Text>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 16px', paddingLeft: 0 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Остаток по счетам: {fmtNum(invoicedRemaining)} {summary.currency}
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>·</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          К выставлению: {fmtNum(notInvoiced)} {summary.currency}
        </Text>
        {summary.commission != null && (
          <>
            <Text type="secondary" style={{ fontSize: 12 }}>·</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Комиссия: {fmt(summary.commission, currency)}
            </Text>
          </>
        )}
      </div>
    </div>
  );
}

interface Props {
  projectId: number;
}

export default function ItemsPanel({ projectId }: Props) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedItem, setSelectedItem] = useState<ProjectItem | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const handleDownloadTemplate = async () => {
    try {
      await downloadItemsTemplate(projectId);
    } catch {
      message.error('Не удалось скачать шаблон');
    }
  };

  const handleImport = async (file: RcFile): Promise<boolean> => {
    setImportLoading(true);
    try {
      const result = await importItems(projectId, file);
      setImportResult(result);
      if (result.created > 0) {
        queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
        queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка импорта');
    } finally {
      setImportLoading(false);
    }
    return false;
  };

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['project-items', projectId],
    queryFn: () => listItems(projectId),
  });

  const { data: summary } = useQuery({
    queryKey: ['project-summary', projectId],
    queryFn: () => getProjectSummary(projectId),
  });

  const handleDelete = async (itemId: number) => {
    try {
      await deleteItem(projectId, itemId);
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
      message.success('Позиция удалена');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  const handleToggleAccess = async (item: ProjectItem, shared: boolean) => {
    try {
      await updateItem(projectId, item.id, { shared_access: shared });
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      message.success(shared ? 'Доступ открыт' : 'Доступ закрыт');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleMove = async (itemId: number, direction: 'up' | 'down') => {
    try {
      if (direction === 'up') {
        await moveItemUp(projectId, itemId);
      } else {
        await moveItemDown(projectId, itemId);
      }
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      queryClient.invalidateQueries({ queryKey: ['payment-requests', projectId] });
      message.success('Порядок обновлён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    }
  };

  const columns = [
    {
      title: 'Порядок',
      key: 'order',
      width: 72,
      render: (_: unknown, record: ProjectItem, index: number) =>
        itemCanEdit(record, isAdmin) ? (
          <Space size={2}>
            <Button
              size="small"
              type="text"
              icon={<ArrowUpOutlined />}
              disabled={index === 0}
              onClick={(e) => {
                e.stopPropagation();
                handleMove(record.id, 'up');
              }}
            />
            <Button
              size="small"
              type="text"
              icon={<ArrowDownOutlined />}
              disabled={index === items.length - 1}
              onClick={(e) => {
                e.stopPropagation();
                handleMove(record.id, 'down');
              }}
            />
          </Space>
        ) : null,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      width: '32%',
      ellipsis: { showTitle: false },
      render: (name: string, record: ProjectItem) => (
        <Tooltip title={name} placement="topLeft">
          <Button
            type="link"
            style={{ padding: 0, height: 'auto', textAlign: 'left', maxWidth: '100%' }}
            onClick={() => setSelectedItem(record)}
          >
            <span style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'block',
              maxWidth: '100%',
            }}>
              {name}
            </span>
          </Button>
        </Tooltip>
      ),
    },
    {
      title: 'Кол-во',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 80,
      align: 'right' as const,
      render: (v: string) => parseFloat(v).toLocaleString('ru-RU'),
    },
    {
      title: 'Итого',
      key: 'total',
      width: 140,
      align: 'right' as const,
      render: (_: unknown, record: ProjectItem) => {
        const total = parseFloat(record.price) * parseFloat(record.quantity);
        return (
          <Text style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
            {fmtNum(total)} {record.currency}
          </Text>
        );
      },
    },
    {
      title: 'Выставлено',
      key: 'invoiced',
      width: 140,
      align: 'right' as const,
      render: (_: unknown, record: ProjectItem) => {
        const invoiced = parseFloat(record.invoiced_amount ?? '0');
        return (
          <Text style={{ fontSize: 12, whiteSpace: 'nowrap' }} type={invoiced > 0 ? undefined : 'secondary'}>
            {fmtNum(invoiced)} {record.currency}
          </Text>
        );
      },
    },
    {
      title: 'Остаток',
      key: 'remaining',
      width: 140,
      align: 'right' as const,
      render: (_: unknown, record: ProjectItem) => {
        const total = parseFloat(record.price) * parseFloat(record.quantity);
        const paid = parseFloat(record.paid_amount ?? '0');
        const remaining = total - paid;
        return (
          <Text
            style={{ fontSize: 12, whiteSpace: 'nowrap' }}
            type={remaining > 0.005 ? 'danger' : 'success'}
          >
            {fmtNum(remaining)} {record.currency}
          </Text>
        );
      },
    },
    ...(isAdmin
      ? [
          {
            title: 'Доступ',
            key: 'shared_access',
            width: 72,
            render: (_: unknown, record: ProjectItem) => (
              <Switch
                size="small"
                checked={record.shared_access}
                onClick={(_, e) => e.stopPropagation()}
                onChange={(checked) => handleToggleAccess(record, checked)}
              />
            ),
          },
        ]
      : []),
    {
      title: '',
      key: 'actions',
      width: 40,
      render: (_: unknown, record: ProjectItem) =>
        itemCanEdit(record, isAdmin) ? (
          <Popconfirm
            title="Удалить позицию?"
            okText="Да"
            cancelText="Отмена"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        ) : null,
    },
  ];

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
          Номенклатура
        </Text>
        <Space size="small" wrap>
          {isAdmin && (
            <>
              <Button
                size="small"
                icon={<DownloadOutlined />}
                onClick={handleDownloadTemplate}
              >
                Шаблон
              </Button>
              <Upload
                accept=".xlsx"
                showUploadList={false}
                beforeUpload={handleImport}
              >
                <Button size="small" icon={<UploadOutlined />} loading={importLoading}>
                  Импорт
                </Button>
              </Upload>
            </>
          )}
          <Button
            size="small"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowCreate(true)}
          >
            Добавить
          </Button>
        </Space>
      </div>

      {isLoading ? (
        <Spin />
      ) : items.length === 0 ? (
        <Empty description="Нет позиций" />
      ) : (
        <Table
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={items}
          pagination={false}
          tableLayout="fixed"
        />
      )}

      {/* Финансовая сводка */}
      {summary && summary.currencies.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <div>
            {summary.currencies.map((s) => (
              <SummaryRow key={s.currency} summary={s} />
            ))}
          </div>
        </>
      )}

      {showCreate && (
        <ItemFormModal
          open={showCreate}
          projectId={projectId}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
          }}
        />
      )}

      {selectedItem && (
        <ItemDetailDrawer
          open={!!selectedItem}
          item={items.find((i) => i.id === selectedItem.id) ?? selectedItem}
          projectId={projectId}
          onClose={() => setSelectedItem(null)}
          onChanged={() => {
            queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
            queryClient.invalidateQueries({ queryKey: ['project-summary', projectId] });
          }}
        />
      )}

      <Modal
        open={importResult !== null}
        onCancel={() => setImportResult(null)}
        onOk={() => setImportResult(null)}
        title="Результат импорта"
        okText="Закрыть"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        {importResult && (
          <div>
            <Text>
              Создано позиций: <Text strong>{importResult.created}</Text>
            </Text>
            {importResult.errors.length > 0 && (
              <>
                <Divider style={{ margin: '12px 0' }} />
                <Text type="danger">
                  Ошибки ({importResult.errors.length}):
                </Text>
                <List
                  size="small"
                  dataSource={importResult.errors}
                  renderItem={(err) => (
                    <List.Item>
                      <Text>
                        Строка {err.row}: {err.message}
                      </Text>
                    </List.Item>
                  )}
                />
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
