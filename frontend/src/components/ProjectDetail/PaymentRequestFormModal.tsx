import { useEffect, useState } from 'react';
import {
  Button,
  DatePicker,
  Form,
  InputNumber,
  Modal,
  Select,
  Table,
  Input,
  Upload,
  Typography,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { RcFile } from 'antd/es/upload';
import { isFileSizeValid } from '../../utils/file';
import { useQuery } from '@tanstack/react-query';
import { listItems } from '../../api/projectItems';
import { createPaymentRequest, uploadAttachment } from '../../api/paymentRequests';
import type { Currency, PaymentRequestPriority, ProjectItem } from '../../types';
import dayjs, { type Dayjs } from 'dayjs';

const { Text } = Typography;

interface ItemRow {
  project_item_id: number;
  name: string;
  currency: Currency;
  amount: number | null;
}

interface Props {
  open: boolean;
  projectId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export default function PaymentRequestFormModal({
  open,
  projectId,
  onClose,
  onSuccess,
}: Props) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [selectedRows, setSelectedRows] = useState<ItemRow[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const { data: items = [] } = useQuery({
    queryKey: ['project-items', projectId],
    queryFn: () => listItems(projectId),
  });

  useEffect(() => {
    if (open) {
      form.resetFields();
      setSelectedRows([]);
      setFileList([]);
    }
  }, [open, form]);

  const tableData: ItemRow[] = items.map((item: ProjectItem) => ({
    project_item_id: item.id,
    name: item.name,
    currency: item.currency,
    amount: null,
  }));

  const handleAmountChange = (projectItemId: number, value: number | null) => {
    setSelectedRows((prev) => {
      const updated = prev.map((r) =>
        r.project_item_id === projectItemId ? { ...r, amount: value } : r,
      );
      const total = updated.reduce((sum, r) => sum + (r.amount ?? 0), 0);
      form.setFieldValue('total_amount', total > 0 ? total : null);

      const currencies = [...new Set(updated.map((r) => r.currency))];
      if (currencies.length === 1) {
        form.setFieldValue('currency', currencies[0]);
      }

      return updated;
    });
  };

  const handleSave = async (values: {
    total_amount: number;
    currency: Currency;
    requisites?: string;
    payment_details?: string;
    due_date?: Dayjs | null;
    priority?: PaymentRequestPriority;
  }) => {
    const validItems = selectedRows.filter((r) => r.amount && r.amount > 0);
    if (validItems.length === 0) {
      message.warning('Выберите хотя бы одну позицию с суммой');
      return;
    }

    setLoading(true);
    try {
      const newReq = await createPaymentRequest(projectId, {
        items: validItems.map((r) => ({
          project_item_id: r.project_item_id,
          amount: r.amount!,
        })),
        total_amount: values.total_amount,
        currency: values.currency,
        requisites: values.requisites || null,
        payment_details: values.payment_details || null,
        due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : null,
        priority: values.priority ?? 'normal',
      });

      // Загружаем прикреплённые файлы
      for (const f of fileList) {
        if (f.originFileObj) {
          try {
            await uploadAttachment(projectId, newReq.id, f.originFileObj);
          } catch {
            message.warning(`Файл «${f.name}» не был загружен`);
          }
        }
      }

      message.success('Заявка создана');
      onSuccess();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: 'Позиция', dataIndex: 'name', key: 'name' },
    { title: 'Валюта', dataIndex: 'currency', key: 'currency', width: 80 },
    {
      title: 'Сумма',
      key: 'amount',
      width: 140,
      render: (_: unknown, record: ItemRow) => {
        const row = selectedRows.find((r) => r.project_item_id === record.project_item_id);
        return row ? (
          <InputNumber
            min={0.01}
            style={{ width: '100%' }}
            value={row.amount ?? undefined}
            onChange={(v) => handleAmountChange(record.project_item_id, v)}
          />
        ) : (
          <Text type="secondary">—</Text>
        );
      },
    },
  ];

  const rowSelection = {
    selectedRowKeys: selectedRows.map((r) => r.project_item_id),
    onChange: (_: unknown, rows: ItemRow[]) => {
      setSelectedRows(
        rows.map((r) => ({
          ...r,
          amount:
            selectedRows.find((s) => s.project_item_id === r.project_item_id)?.amount ??
            null,
        })),
      );
    },
  };

  return (
    <Modal
      open={open}
      title="Новая заявка на оплату"
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Создать"
      cancelText="Отмена"
      confirmLoading={loading}
      width="min(680px, 94vw)"
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">Выберите позиции и укажите суммы по каждой:</Text>
        <Table
          rowKey="project_item_id"
          size="small"
          columns={columns}
          dataSource={tableData}
          rowSelection={rowSelection}
          pagination={false}
          style={{ marginTop: 8 }}
        />
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{ priority: 'normal' }}
      >
        <Form.Item
          name="total_amount"
          label="Итоговая сумма"
          rules={[{ required: true, message: 'Укажите сумму' }]}
        >
          <InputNumber min={0.01} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          name="currency"
          label="Валюта"
          rules={[{ required: true, message: 'Выберите валюту' }]}
        >
          <Select
            options={[
              { value: 'CNY', label: 'CNY (юань)' },
              { value: 'USD', label: 'USD (доллар)' },
              { value: 'RUB', label: 'RUB (рубль)' },
            ]}
          />
        </Form.Item>
        <Form.Item name="priority" label="Приоритет">
          <Select
            options={[
              { value: 'urgent', label: 'Срочно' },
              { value: 'normal', label: 'Обычно' },
              { value: 'deferred', label: 'Отложено' },
            ]}
          />
        </Form.Item>
        <Form.Item name="due_date" label="Дедлайн">
          <DatePicker
            style={{ width: '100%' }}
            format="DD.MM.YYYY"
            placeholder="Выберите дату"
            disabledDate={(d) => d && d.isBefore(dayjs().startOf('day'))}
          />
        </Form.Item>
        <Form.Item name="requisites" label="Реквизиты">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="payment_details" label="Детали платежа">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item
          label={`Вложения (до 3 файлов, максимум 10 МБ каждый)`}
        >
          <Upload
            beforeUpload={(file: RcFile) => {
              if (!isFileSizeValid(file)) return Upload.LIST_IGNORE;
              return false;
            }}
            fileList={fileList}
            onChange={({ fileList: newList }) => setFileList(newList.slice(0, 3))}
            maxCount={3}
            multiple
          >
            {fileList.length < 3 && (
              <Button icon={<UploadOutlined />}>Выбрать файл</Button>
            )}
          </Upload>
        </Form.Item>
      </Form>
    </Modal>
  );
}
