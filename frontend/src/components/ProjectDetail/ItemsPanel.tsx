import { useState } from 'react';
import {
  Button,
  Modal,
  Table,
  Typography,
  Spin,
  Empty,
  Divider,
  List,
  Upload,
  Space,
  message,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  DownloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import type { RcFile } from 'antd/es/upload';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listItems,
  deleteItem,
  downloadItemsTemplate,
  importItems,
  type ImportResult,
} from '../../api/projectItems';
import { getProjectSummary } from '../../api/projects';
import { useAuth } from '../../contexts/AuthContext';
import ItemFormModal from './ItemFormModal';
import ItemDetailDrawer from './ItemDetailDrawer';
import type { ProjectItem, CurrencySummary } from '../../types';
import { fmt } from '../../utils/format';

const { Text } = Typography;

function SummaryRow({ summary, isAdmin }: { summary: CurrencySummary; isAdmin: boolean }) {
  return (
    <div style={{ padding: '4px 0' }}>
      <div>
        <Text strong style={{ marginRight: 8 }}>
          {summary.currency}:
        </Text>
        <Text>Итого: {fmt(summary.total, summary.currency)}</Text>
        <Text type="secondary" style={{ margin: '0 8px' }}>·</Text>
        <Text>Оплачено: {fmt(summary.paid, summary.currency)}</Text>
        <Text type="secondary" style={{ margin: '0 8px' }}>·</Text>
        <Text type={parseFloat(summary.remaining) > 0 ? 'danger' : 'success'}>
          Остаток: {fmt(summary.remaining, summary.currency)}
        </Text>
      </div>
      {(summary.commission != null || (isAdmin && summary.profit != null)) && (
        <div style={{ paddingLeft: 0, marginTop: 2 }}>
          {summary.commission != null && (
            <Text type="secondary" style={{ fontSize: 12, marginRight: 12 }}>
              Комиссия: {fmt(summary.commission, summary.currency)}
            </Text>
          )}
          {isAdmin && summary.profit != null && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Прибыль:{' '}
              <Text type="success" style={{ fontSize: 12 }}>
                {fmt(summary.profit, summary.currency)}
              </Text>
            </Text>
          )}
        </div>
      )}
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

  const columns = [
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ProjectItem) => (
        <Button
          type="link"
          style={{ padding: 0, height: 'auto', textAlign: 'left' }}
          onClick={() => setSelectedItem(record)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: 'Кол-во',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 80,
      render: (v: string) => parseFloat(v).toLocaleString('ru-RU'),
    },
    ...(isAdmin
      ? [
          {
            title: '',
            key: 'actions',
            width: 48,
            render: (_: unknown, record: ProjectItem) => (
              <Popconfirm
                title="Удалить позицию?"
                okText="Да"
                cancelText="Отмена"
                onConfirm={() => handleDelete(record.id)}
              >
                <Button size="small" type="text" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            ),
          },
        ]
      : []),
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
        {isAdmin && (
          <Space size="small" wrap>
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
            <Button
              size="small"
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setShowCreate(true)}
            >
              Добавить
            </Button>
          </Space>
        )}
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
          scroll={{ x: 'max-content' }}
        />
      )}

      {/* Финансовые расчёты */}
      {summary && summary.currencies.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <div>
            {summary.currencies.map((s) => (
              <SummaryRow key={s.currency} summary={s} isAdmin={isAdmin} />
            ))}
          </div>
        </>
      )}

      {isAdmin && showCreate && (
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
          item={selectedItem}
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
