import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
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
  Tag,
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
  max_amount: number; // price × qty − invoiced_amount
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

  const tableData: ItemRow[] = useMemo(
    () =>
      items.map((item: ProjectItem) => {
        const price = parseFloat(item.price);
        const qty = parseFloat(item.quantity);
        const invoiced = parseFloat(item.invoiced_amount ?? '0');
        const raw = price * qty - invoiced;
        return {
          project_item_id: item.id,
          name: item.name,
          currency: item.currency,
          amount: null,
          max_amount: Math.max(0, Math.round(raw * 100) / 100),
        };
      }),
    [items],
  );

  // Derived state
  const selectedCurrencies = useMemo(
    () => [...new Set(selectedRows.map((r) => r.currency))],
    [selectedRows],
  );
  const hasMixedCurrencies = selectedCurrencies.length > 1;
  const detectedCurrency = selectedCurrencies.length === 1 ? selectedCurrencies[0] : null;
  const computedTotal = selectedRows.reduce((sum, r) => sum + (r.amount ?? 0), 0);
  const validItems = selectedRows.filter((r) => r.amount && r.amount > 0);

  const handleAmountChange = (projectItemId: number, value: number | null) => {
    setSelectedRows((prev) =>
      prev.map((r) =>
        r.project_item_id === projectItemId ? { ...r, amount: value } : r,
      ),
    );
  };

  const handleSave = async (values: {
    requisites?: string;
    payment_details?: string;
    due_date?: Dayjs | null;
    priority?: PaymentRequestPriority;
  }) => {
    if (validItems.length === 0) {
      message.warning('Выберите хотя бы одну позицию с суммой');
      return;
    }
    if (hasMixedCurrencies) {
      message.error('Нельзя объединять позиции с разными валютами в одной заявке');
      return;
    }
    if (!detectedCurrency) {
      message.error('Выберите позиции для заявки');
      return;
    }

    // Проверяем лимиты по каждой позиции
    for (const row of validItems) {
      const tableRow = tableData.find((t) => t.project_item_id === row.project_item_id);
      if (tableRow && row.amount! > tableRow.max_amount + 0.005) {
        message.error(
          `Сумма по позиции «${tableRow.name}» превышает допустимый остаток (${tableRow.max_amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })})`,
        );
        return;
      }
    }

    setLoading(true);
    try {
      const newReq = await createPaymentRequest(projectId, {
        items: validItems.map((r) => ({
          project_item_id: r.project_item_id,
          amount: r.amount!,
        })),
        total_amount: computedTotal,
        currency: detectedCurrency,
        requisites: values.requisites || null,
        payment_details: values.payment_details || null,
        due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : null,
        priority: values.priority ?? 'normal',
      });

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
    {
      title: 'Позиция',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Валюта',
      dataIndex: 'currency',
      key: 'currency',
      width: 70,
    },
    {
      title: 'Доступно',
      key: 'max_amount',
      width: 110,
      render: (_: unknown, record: ItemRow) => {
        const tableRow = tableData.find((t) => t.project_item_id === record.project_item_id);
        if (!tableRow) return '—';
        return (
          <Text
            type={tableRow.max_amount <= 0 ? 'danger' : 'secondary'}
            style={{ fontSize: 12 }}
          >
            {tableRow.max_amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
          </Text>
        );
      },
    },
    {
      title: 'Сумма',
      key: 'amount',
      width: 140,
      render: (_: unknown, record: ItemRow) => {
        const row = selectedRows.find((r) => r.project_item_id === record.project_item_id);
        const tableRow = tableData.find((t) => t.project_item_id === record.project_item_id);
        if (!row) return <Text type="secondary">—</Text>;
        const exceeds = row.amount !== null && tableRow && row.amount > tableRow.max_amount + 0.005;
        return (
          <InputNumber
            min={0.01}
            max={tableRow && tableRow.max_amount > 0 ? tableRow.max_amount : undefined}
            style={{ width: '100%' }}
            status={exceeds ? 'error' : undefined}
            value={row.amount ?? undefined}
            onChange={(v) => handleAmountChange(record.project_item_id, v)}
          />
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
    getCheckboxProps: (record: ItemRow) => {
      const tableRow = tableData.find((t) => t.project_item_id === record.project_item_id);
      return {
        disabled: tableRow ? tableRow.max_amount <= 0 : false,
      };
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
      width="min(700px, 94vw)"
      destroyOnClose
    >
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">Выберите позиции и укажите суммы по каждой:</Text>
        {hasMixedCurrencies && (
          <Alert
            style={{ marginTop: 8 }}
            type="error"
            showIcon
            message="В одну заявку можно включать только позиции с одинаковой валютой"
          />
        )}
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

      {/* Итог и валюта — вычисляются автоматически */}
      <div
        style={{
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          padding: '10px 12px',
          marginBottom: 16,
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Итоговая сумма
          </Text>
          <div>
            <Text strong style={{ fontSize: 16 }}>
              {computedTotal > 0
                ? computedTotal.toLocaleString('ru-RU', { minimumFractionDigits: 2 })
                : '—'}
            </Text>
          </div>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Валюта
          </Text>
          <div>
            {hasMixedCurrencies ? (
              <Tag color="error">Смешанные валюты!</Tag>
            ) : detectedCurrency ? (
              <Tag color={detectedCurrency === 'CNY' ? 'orange' : detectedCurrency === 'USD' ? 'blue' : 'purple'}>
                {detectedCurrency}
              </Tag>
            ) : (
              <Text type="secondary">—</Text>
            )}
          </div>
        </div>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{ priority: 'normal' }}
      >
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
        <Form.Item label="Вложения (до 3 файлов, максимум 10 МБ каждый)">
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
