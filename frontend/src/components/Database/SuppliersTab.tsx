import { useState } from 'react';
import {
  Button,
  Descriptions,
  Divider,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  UploadOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { isFileSizeValid } from '../../utils/file';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listSuppliers,
  createSupplier,
  updateSupplier,
  deleteSupplier,
  uploadSupplierDocument,
  deleteSupplierDocument,
} from '../../api/suppliers';
import { getFileDownloadUrl } from '../../api/files';
import type { Supplier, SupplierCreate, SupplierUpdate } from '../../types';

const { Text } = Typography;

// Парсит поле документа формата "s3key|original_filename"
function parseDocField(value: string | null | undefined): { key: string; name: string } | null {
  if (!value) return null;
  const idx = value.indexOf('|');
  if (idx === -1) return { key: value, name: value };
  return { key: value.slice(0, idx), name: value.slice(idx + 1) };
}

// ── Слот документа поставщика ─────────────────────────────────────────────────

function DocumentSlot({
  label,
  slot,
  supplierId,
  rawValue,
  onUpdated,
}: {
  label: string;
  slot: number;
  supplierId: number;
  rawValue: string | null | undefined;
  onUpdated: (updated: Supplier) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const parsed = parseDocField(rawValue);

  const handleDownload = async () => {
    if (!parsed) return;
    try {
      const url = await getFileDownloadUrl(parsed.key);
      window.open(url, '_blank');
    } catch {
      message.error('Не удалось получить ссылку для скачивания');
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const updated = await deleteSupplierDocument(supplierId, slot);
      onUpdated(updated);
      message.success('Файл удалён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 32 }}>
      <Text type="secondary" style={{ width: 80, flexShrink: 0 }}>
        {label}:
      </Text>
      {parsed ? (
        <Space>
          <Text
            style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={parsed.name}
          >
            {parsed.name}
          </Text>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
            title="Скачать"
          />
          <Popconfirm
            title="Удалить файл?"
            okText="Да"
            cancelText="Отмена"
            onConfirm={handleDelete}
          >
            <Button size="small" danger icon={<DeleteOutlined />} loading={deleting} />
          </Popconfirm>
        </Space>
      ) : (
        <Upload
          showUploadList={false}
          beforeUpload={() => false}
          onChange={async ({ file }: { file: unknown }) => {
            if (file instanceof File || (file as { originFileObj?: File }).originFileObj) {
              const f = (file as { originFileObj?: File }).originFileObj ?? (file as unknown as File);
              if (!isFileSizeValid(f)) return;
              setUploading(true);
              try {
                const updated = await uploadSupplierDocument(supplierId, slot, f);
                onUpdated(updated);
                message.success('Файл загружен');
              } catch (err: unknown) {
                const e = err as { response?: { data?: { detail?: string } } };
                message.error(e.response?.data?.detail ?? 'Ошибка загрузки');
              } finally {
                setUploading(false);
              }
            }
          }}
        >
          <Button size="small" icon={<UploadOutlined />} loading={uploading}>
            Загрузить
          </Button>
        </Upload>
      )}
    </div>
  );
}

// ── Drawer детального просмотра ───────────────────────────────────────────────

function SupplierDetailDrawer({
  supplier,
  onClose,
  onEdit,
  onSupplierUpdated,
}: {
  supplier: Supplier | null;
  onClose: () => void;
  onEdit: (s: Supplier) => void;
  onSupplierUpdated: (updated: Supplier) => void;
}) {
  if (!supplier) return null;

  return (
    <Drawer
      open={!!supplier}
      onClose={onClose}
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{supplier.full_name}</span>
          <Button size="small" icon={<EditOutlined />} onClick={() => onEdit(supplier)}>
            Редактировать
          </Button>
        </div>
      }
      width="min(500px, 94vw)"
    >
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="ID">{supplier.id}</Descriptions.Item>
        <Descriptions.Item label="Наименование">{supplier.full_name}</Descriptions.Item>
        <Descriptions.Item label="Телефон">{supplier.phone}</Descriptions.Item>
        <Descriptions.Item label="WeChat ID">{supplier.wechat_id}</Descriptions.Item>
        <Descriptions.Item label="Описание">
          {supplier.description || <Text type="secondary">—</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="Добавлен">
          {new Date(supplier.created_at).toLocaleDateString('ru-RU')}
        </Descriptions.Item>
      </Descriptions>

      <Divider style={{ margin: '16px 0 12px' }}>Документы</Divider>
      <Space direction="vertical" style={{ width: '100%' }} size={10}>
        {([1, 2, 3] as const).map((slot) => (
          <DocumentSlot
            key={slot}
            label={`Документ ${slot}`}
            slot={slot}
            supplierId={supplier.id}
            rawValue={supplier[`document_${slot}` as 'document_1' | 'document_2' | 'document_3']}
            onUpdated={onSupplierUpdated}
          />
        ))}
      </Space>
    </Drawer>
  );
}

// ── Форма создания / редактирования ──────────────────────────────────────────

interface FormValues {
  full_name: string;
  phone: string;
  wechat_id: string;
  description?: string;
}

function SupplierFormModal({
  open,
  editing,
  onClose,
  onSaved,
}: {
  open: boolean;
  editing: Supplier | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const [loading, setLoading] = useState(false);

  const handleAfterOpen = (visible: boolean) => {
    if (!visible) return;
    if (editing) {
      form.setFieldsValue({
        full_name: editing.full_name,
        phone: editing.phone,
        wechat_id: editing.wechat_id,
        description: editing.description ?? '',
      });
    } else {
      form.resetFields();
    }
  };

  const handleSave = async (values: FormValues) => {
    setLoading(true);
    try {
      if (editing) {
        const upd: SupplierUpdate = {
          full_name: values.full_name,
          phone: values.phone,
          wechat_id: values.wechat_id,
          description: values.description || null,
        };
        await updateSupplier(editing.id, upd);
        message.success('Поставщик обновлён');
      } else {
        const create: SupplierCreate = {
          full_name: values.full_name,
          phone: values.phone,
          wechat_id: values.wechat_id,
          description: values.description || null,
        };
        await createSupplier(create);
        message.success('Поставщик добавлен');
      }
      onSaved();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка сохранения');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      title={editing ? 'Редактировать поставщика' : 'Новый поставщик'}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Сохранить"
      cancelText="Отмена"
      confirmLoading={loading}
      afterOpenChange={handleAfterOpen}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item
          name="full_name"
          label="Наименование"
          rules={[{ required: true, message: 'Введите наименование' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="phone"
          label="Телефон"
          rules={[{ required: true, message: 'Введите телефон' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="wechat_id"
          label="WeChat ID"
          rules={[{ required: true, message: 'Введите WeChat ID' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="description" label="Описание">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Основной компонент таблицы ────────────────────────────────────────────────

export default function SuppliersTab() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [detailSupplier, setDetailSupplier] = useState<Supplier | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => listSuppliers(),
  });

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };

  const openEdit = (supplier: Supplier) => {
    setDetailSupplier(null);
    setEditing(supplier);
    setModalOpen(true);
  };

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['suppliers'] });
    setModalOpen(false);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteSupplier(id);
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      message.success('Поставщик удалён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  // Обновляем поставщика в drawer после загрузки/удаления документа
  const handleSupplierUpdated = (updated: Supplier) => {
    setDetailSupplier(updated);
    queryClient.invalidateQueries({ queryKey: ['suppliers'] });
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: 'Наименование',
      dataIndex: 'full_name',
      key: 'full_name',
      width: 220,
      ellipsis: true,
      render: (name: string, record: Supplier) => (
        <Button
          type="link"
          style={{ padding: 0, height: 'auto' }}
          onClick={() => setDetailSupplier(record)}
        >
          {name}
        </Button>
      ),
    },
    { title: 'Телефон', dataIndex: 'phone', key: 'phone', width: 160, ellipsis: true },
    { title: 'WeChat ID', dataIndex: 'wechat_id', key: 'wechat_id', width: 160, ellipsis: true },
    {
      title: 'Действия',
      key: 'actions',
      width: 140,
      fixed: 'right' as const,
      render: (_: unknown, record: Supplier) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => setDetailSupplier(record)} />
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title="Удалить поставщика?"
            description="Поставщик будет отвязан от всех позиций."
            okText="Да"
            cancelText="Отмена"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить поставщика
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data?.items ?? []}
        loading={isLoading}
        pagination={{ pageSize: 20, showTotal: (t) => `Всего: ${t}` }}
        scroll={{ x: 'max-content' }}
      />

      <SupplierFormModal
        open={modalOpen}
        editing={editing}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />

      <SupplierDetailDrawer
        supplier={detailSupplier}
        onClose={() => setDetailSupplier(null)}
        onEdit={openEdit}
        onSupplierUpdated={handleSupplierUpdated}
      />
    </>
  );
}
