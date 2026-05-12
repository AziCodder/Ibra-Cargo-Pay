import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  DatePicker,
  Descriptions,
  Divider,
  Form,
  Grid,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Table,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import type { RcFile } from 'antd/es/upload';
import { isPaymentFileSizeValid } from '../../utils/file';
import {
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  PaperClipOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteAttachment,
  deletePaymentRequest,
  getPaymentRequest,
  updatePaymentRequest,
} from '../../api/paymentRequests';
import { listItems } from '../../api/projectItems';
import {
  addPayment,
  confirmPayment,
  deletePayment,
  downloadPaymentsZip,
  rejectPayment,
} from '../../api/payments';
import { getFileDownloadUrl } from '../../api/files';
import {
  addComment,
  deleteComment,
  listComments,
} from '../../api/paymentRequestComments';
import { useAuth } from '../../contexts/AuthContext';
import type { Currency, PaymentRequestPriority, PaymentStatus } from '../../types';
import { fmt } from '../../utils/format';
import dayjs, { type Dayjs } from 'dayjs';

/** Извлекает читаемое сообщение из ошибки axios / FastAPI (string или array detail). */
function _extractErrorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: unknown } } };
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    return first.msg ?? fallback;
  }
  return fallback;
}

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

const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: 'Ожидает подтверждения',
  confirmed: 'Подтверждён',
  rejected: 'Отклонён',
};
const PAYMENT_STATUS_COLOR: Record<PaymentStatus, string> = {
  pending: 'orange',
  confirmed: 'green',
  rejected: 'red',
};

const { Text, Paragraph } = Typography;
const { useBreakpoint } = Grid;

interface Props {
  open: boolean;
  projectId: number;
  reqId: number;
  onClose: () => void;
  onChanged: () => void;
}

export default function PaymentRequestDetailModal({
  open,
  projectId,
  reqId,
  onClose,
  onChanged,
}: Props) {
  const { isAdmin, user } = useAuth();
  const queryClient = useQueryClient();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [editMode, setEditMode] = useState(false);
  const [editForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);
  const [editItems, setEditItems] = useState<Record<number, number | null>>({});
  const [deletingAtt, setDeletingAtt] = useState<number | null>(null);
  const [addPaymentOpen, setAddPaymentOpen] = useState(false);
  const [addPaymentLoading, setAddPaymentLoading] = useState(false);
  const [addPaymentForm] = Form.useForm();
  const [paymentFile, setPaymentFile] = useState<UploadFile[]>([]);
  const [paymentDate, setPaymentDate] = useState<Dayjs | null>(null);
  const [deletingPay, setDeletingPay] = useState<number | null>(null);
  const [confirmingPay, setConfirmingPay] = useState<number | null>(null);
  const [rejectingPay, setRejectingPay] = useState<number | null>(null);
  const [rejectModalPayId, setRejectModalPayId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [commentText, setCommentText] = useState('');
  const [commentLoading, setCommentLoading] = useState(false);
  const [deletingComment, setDeletingComment] = useState<number | null>(null);

  const { data: req, isLoading } = useQuery({
    queryKey: ['payment-request-detail', reqId],
    queryFn: () => getPaymentRequest(projectId, reqId),
    enabled: open,
  });

  const { data: projectItems = [] } = useQuery({
    queryKey: ['project-items', projectId],
    queryFn: () => listItems(projectId),
    enabled: editMode,
  });

  const { data: comments = [] } = useQuery({
    queryKey: ['payment-request-comments', reqId],
    queryFn: () => listComments(reqId),
    enabled: open,
  });

  useEffect(() => {
    if (editMode && req) {
      editForm.setFieldsValue({
        requisites: req.requisites ?? '',
        payment_details: req.payment_details ?? '',
        priority: req.priority,
        due_date: req.due_date ? dayjs(req.due_date) : null,
      });
      // Инициализируем суммы из текущих позиций заявки
      const initial: Record<number, number | null> = {};
      for (const item of req.items) {
        initial[item.project_item_id] = parseFloat(item.amount);
      }
      setEditItems(initial);
    }
  }, [editMode, req, editForm]);

  const isCompleted = req ? parseFloat(req.remaining_amount) <= 0 : false;

  // Вычисляем доступный остаток для каждой позиции в режиме редактирования.
  // invoiced_amount включает ВСЕ заявки, включая текущую. Вычитаем текущую, чтобы получить остаток.
  const getMaxForItem = useMemo(() => (projectItemId: number, originalAmount: number): number => {
    const pi = projectItems.find((p) => p.id === projectItemId);
    if (!pi) return Infinity;
    const invoiced = parseFloat(pi.invoiced_amount ?? '0');
    const maxTotal = parseFloat(String(pi.price)) * parseFloat(String(pi.quantity));
    return Math.max(0, maxTotal - (invoiced - originalAmount));
  }, [projectItems]);

  const computedEditTotal = useMemo(() => {
    if (!req) return 0;
    return req.items.reduce((sum, item) => sum + (editItems[item.project_item_id] ?? 0), 0);
  }, [req, editItems]);

  // ── Скачивание файла ────────────────────────────────────────────────────────

  const handleDownloadFile = async (fileKey: string) => {
    try {
      const url = await getFileDownloadUrl(fileKey);
      window.open(url, '_blank');
    } catch {
      message.error('Не удалось получить ссылку для скачивания');
    }
  };

  // ── Скачивание ZIP архива оплат ─────────────────────────────────────────────

  const handleDownloadZip = async () => {
    try {
      await downloadPaymentsZip(reqId);
    } catch {
      message.error('Не удалось скачать архив');
    }
  };

  // ── Копирование информации ──────────────────────────────────────────────────

  const handleCopyInfo = () => {
    if (!req) return;

    const itemNames = req.items.map((i) => i.project_item_name).join('\n');

    const parts: string[] = [];
    if (itemNames) parts.push(itemNames);
    if (req.payment_details) parts.push(req.payment_details);
    parts.push('');
    parts.push(`Общая сумма - ${fmt(req.total_amount, req.currency)}`);
    if (req.requisites) {
      parts.push('');
      parts.push('Реквизиты:');
      parts.push(req.requisites);
    }

    const text = parts.join('\n');

    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(
        () => message.success('Скопировано в буфер обмена'),
        () => {
          // Fallback
          const el = document.createElement('textarea');
          el.value = text;
          document.body.appendChild(el);
          el.select();
          document.execCommand('copy');
          document.body.removeChild(el);
          message.success('Скопировано в буфер обмена');
        },
      );
    } else {
      const el = document.createElement('textarea');
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      message.success('Скопировано в буфер обмена');
    }
  };

  // ── Удаление заявки ─────────────────────────────────────────────────────────

  const handleDelete = async () => {
    try {
      await deletePaymentRequest(projectId, reqId);
      message.success('Заявка удалена');
      onClose();
      onChanged();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  // ── Редактирование заявки ───────────────────────────────────────────────────

  const handleEdit = async (values: {
    requisites?: string;
    payment_details?: string;
    priority?: PaymentRequestPriority;
    due_date?: Dayjs | null;
  }) => {
    if (!req) return;

    // Валидируем суммы позиций
    for (const item of req.items) {
      const amount = editItems[item.project_item_id];
      if (!amount || amount <= 0) {
        message.error(`Укажите сумму по позиции «${item.project_item_name}»`);
        return;
      }
      const maxAvail = getMaxForItem(item.project_item_id, parseFloat(item.amount));
      if (amount > maxAvail + 0.005) {
        message.error(
          `Сумма по позиции «${item.project_item_name}» (${amount}) превышает допустимый остаток (${maxAvail.toFixed(2)})`,
        );
        return;
      }
    }

    setEditLoading(true);
    try {
      await updatePaymentRequest(projectId, reqId, {
        items: req.items.map((item) => ({
          project_item_id: item.project_item_id,
          amount: editItems[item.project_item_id] ?? parseFloat(item.amount),
        })),
        requisites: values.requisites || null,
        payment_details: values.payment_details || null,
        priority: values.priority ?? 'normal',
        due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : null,
      });
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      onChanged();
      setEditMode(false);
      message.success('Заявка обновлена');
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка'));
    } finally {
      setEditLoading(false);
    }
  };

  // ── Комментарии ─────────────────────────────────────────────────────────────

  const handleAddComment = async () => {
    const text = commentText.trim();
    if (!text) {
      message.warning('Введите текст комментария');
      return;
    }
    setCommentLoading(true);
    try {
      await addComment(reqId, text);
      queryClient.invalidateQueries({ queryKey: ['payment-request-comments', reqId] });
      setCommentText('');
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка'));
    } finally {
      setCommentLoading(false);
    }
  };

  const handleDeleteComment = async (commentId: number) => {
    setDeletingComment(commentId);
    try {
      await deleteComment(reqId, commentId);
      queryClient.invalidateQueries({ queryKey: ['payment-request-comments', reqId] });
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка'));
    } finally {
      setDeletingComment(null);
    }
  };

  // ── Удаление вложения ───────────────────────────────────────────────────────

  const handleDeleteAttachment = async (attId: number) => {
    setDeletingAtt(attId);
    try {
      await deleteAttachment(projectId, reqId, attId);
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      message.success('Файл удалён');
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка'));
    } finally {
      setDeletingAtt(null);
    }
  };

  // ── Добавление платежа ──────────────────────────────────────────────────────

  const handleAddPayment = async (values: {
    amount: number;
    currency: Currency;
    note?: string;
  }) => {
    setAddPaymentLoading(true);
    try {
      const file = paymentFile[0]?.originFileObj ?? null;
      const created = await addPayment(reqId, {
        amount: values.amount,
        currency: values.currency,
        note: values.note || null,
        payment_date: paymentDate ? paymentDate.format('YYYY-MM-DD') : null,
        file,
      });
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      onChanged();
      addPaymentForm.resetFields();
      setPaymentFile([]);
      setPaymentDate(null);
      setAddPaymentOpen(false);
      if (created.status === 'pending') {
        message.success('Платёж отправлен на подтверждение');
      } else {
        message.success('Платёж добавлен');
      }
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка при добавлении платежа'));
    } finally {
      setAddPaymentLoading(false);
    }
  };

  // ── Удаление платежа ────────────────────────────────────────────────────────

  const handleDeletePayment = async (payId: number) => {
    setDeletingPay(payId);
    try {
      await deletePayment(reqId, payId);
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      onChanged();
      message.success('Платёж удалён');
    } catch (err: unknown) {
      message.error(_extractErrorMessage(err, 'Ошибка'));
    } finally {
      setDeletingPay(null);
    }
  };

  // ── Подтверждение платежа (admin) ────────────────────────────────────────────

  const handleConfirmPayment = async (payId: number) => {
    setConfirmingPay(payId);
    try {
      await confirmPayment(reqId, payId);
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      onChanged();
      message.success('Платёж подтверждён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Не удалось выполнить операцию');
    } finally {
      setConfirmingPay(null);
    }
  };

  // ── Отклонение платежа (admin) ───────────────────────────────────────────────

  const openRejectModal = (payId: number) => {
    setRejectReason('');
    setRejectModalPayId(payId);
  };

  const handleRejectPayment = async () => {
    if (rejectModalPayId === null) return;
    const reason = rejectReason.trim();
    if (!reason) {
      message.warning('Укажите причину отклонения');
      return;
    }
    setRejectingPay(rejectModalPayId);
    try {
      await rejectPayment(reqId, rejectModalPayId, reason);
      queryClient.invalidateQueries({ queryKey: ['payment-request-detail', reqId] });
      onChanged();
      message.success('Платёж отклонён');
      setRejectModalPayId(null);
      setRejectReason('');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Не удалось выполнить операцию');
    } finally {
      setRejectingPay(null);
    }
  };

  // ── Заголовок модального окна ───────────────────────────────────────────────

  const hasPaymentFiles = req?.payments.some((p) => p.file_path);

  const actionButtons = (
    <Space size="small" wrap>
      <Tooltip title="Копировать">
        <Button
          size="small"
          icon={<CopyOutlined />}
          onClick={handleCopyInfo}
        >
          {isMobile ? null : 'Копировать'}
        </Button>
      </Tooltip>
      {hasPaymentFiles && (
        <Tooltip title="Скачать все файлы оплат архивом">
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={handleDownloadZip}
          >
            {isMobile ? null : 'Архив'}
          </Button>
        </Tooltip>
      )}
      {isAdmin && !editMode && (
        <>
          <Tooltip title="Редактировать">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => setEditMode(true)}
            >
              {isMobile ? null : 'Редактировать'}
            </Button>
          </Tooltip>
          <Popconfirm
            title="Удалить заявку?"
            description="Заявку без платежей можно удалить."
            okText="Удалить"
            okType="danger"
            cancelText="Отмена"
            onConfirm={handleDelete}
          >
            <Tooltip title="Удалить">
              <Button size="small" danger icon={<DeleteOutlined />}>
                {isMobile ? null : 'Удалить'}
              </Button>
            </Tooltip>
          </Popconfirm>
        </>
      )}
    </Space>
  );

  const modalTitle = isMobile ? (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingRight: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ whiteSpace: 'nowrap' }}>Заявка на оплату #{reqId}</span>
        {isCompleted && <Tag color="success">Оплачено</Tag>}
      </div>
      {actionButtons}
    </div>
  ) : (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingRight: 36 }}>
      <span style={{ whiteSpace: 'nowrap' }}>Заявка на оплату #{reqId}</span>
      {isCompleted && <Tag color="success">Оплачено</Tag>}
      <div style={{ marginLeft: 'auto' }}>{actionButtons}</div>
    </div>
  );

  return (
    <Modal
      open={open}
      onCancel={() => {
        setEditMode(false);
        setAddPaymentOpen(false);
        addPaymentForm.resetFields();
        setPaymentFile([]);
        setPaymentDate(null);
        onClose();
      }}
      footer={null}
      title={modalTitle}
      width="min(640px, 94vw)"
      destroyOnClose
    >
      {isLoading || !req ? (
        <div style={{ textAlign: 'center', padding: 32 }}>Загрузка...</div>
      ) : editMode ? (
        // ── Режим редактирования ──────────────────────────────────────────────
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          {/* Таблица позиций с редактируемыми суммами */}
          {req && (
            <>
              <Table
                size="small"
                rowKey="project_item_id"
                pagination={false}
                style={{ marginBottom: 12 }}
                dataSource={req.items}
                columns={[
                  {
                    title: 'Позиция',
                    dataIndex: 'project_item_name',
                    key: 'name',
                  },
                  {
                    title: 'Доступно',
                    key: 'max',
                    width: 110,
                    render: (_: unknown, item: { project_item_id: number; amount: string }) => {
                      const max = getMaxForItem(item.project_item_id, parseFloat(item.amount));
                      return (
                        <Text type={max <= 0 ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
                          {isFinite(max) ? max.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) : '—'}
                        </Text>
                      );
                    },
                  },
                  {
                    title: 'Сумма',
                    key: 'amount',
                    width: 150,
                    render: (_: unknown, item: { project_item_id: number; amount: string }) => {
                      const max = getMaxForItem(item.project_item_id, parseFloat(item.amount));
                      const val = editItems[item.project_item_id];
                      const exceeds = val !== null && val !== undefined && val > max + 0.005;
                      return (
                        <InputNumber
                          min={0.01}
                          max={isFinite(max) && max > 0 ? max : undefined}
                          value={val ?? undefined}
                          onChange={(v) => setEditItems((prev) => ({ ...prev, [item.project_item_id]: v }))}
                          style={{ width: '100%' }}
                          status={exceeds ? 'error' : undefined}
                        />
                      );
                    },
                  },
                ]}
              />
              {/* Итог (только чтение, вычисляется автоматически) */}
              <div
                style={{
                  display: 'flex',
                  gap: 16,
                  alignItems: 'center',
                  padding: '8px 12px',
                  marginBottom: 16,
                  background: 'rgba(255,255,255,0.04)',
                  borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Итоговая сумма</Text>
                  <div>
                    <Text strong style={{ fontSize: 16 }}>
                      {computedEditTotal > 0
                        ? computedEditTotal.toLocaleString('ru-RU', { minimumFractionDigits: 2 })
                        : '—'}
                    </Text>
                  </div>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Валюта</Text>
                  <div>
                    <Tag color={req.currency === 'CNY' ? 'orange' : req.currency === 'USD' ? 'blue' : 'purple'}>
                      {req.currency}
                    </Tag>
                  </div>
                </div>
              </div>
            </>
          )}
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
            />
          </Form.Item>
          <Form.Item name="requisites" label="Реквизиты">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="payment_details" label="Детали платежа">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit" loading={editLoading}>
                Сохранить
              </Button>
              <Button onClick={() => setEditMode(false)}>Отмена</Button>
            </Space>
          </Form.Item>
        </Form>
      ) : (
        // ── Режим просмотра ───────────────────────────────────────────────────
        <>
          {/* Основные данные */}
          <Descriptions column={isMobile ? 1 : 2} size="small" bordered>
            <Descriptions.Item label="Валюта">
              <Tag>{req.currency}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Итого">
              <Text strong style={{ whiteSpace: 'nowrap' }}>
                {fmt(req.total_amount, req.currency)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Оплачено">
              <span style={{ whiteSpace: 'nowrap' }}>
                {fmt(
                  String(parseFloat(req.total_amount) - parseFloat(req.remaining_amount)),
                  req.currency,
                )}
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="Остаток">
              <Text
                type={isCompleted ? 'success' : 'danger'}
                style={{ whiteSpace: 'nowrap' }}
              >
                {fmt(req.remaining_amount, req.currency)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Приоритет">
              <Tag color={PRIORITY_COLOR[req.priority]}>
                {PRIORITY_LABEL[req.priority]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Дедлайн">
              {req.due_date ? (
                <Text style={{ whiteSpace: 'nowrap' }}>
                  {dayjs(req.due_date).format('DD.MM.YYYY')}
                </Text>
              ) : (
                <Text type="secondary">—</Text>
              )}
            </Descriptions.Item>
            {req.requisites && (
              <Descriptions.Item label="Реквизиты" span={isMobile ? 1 : 2}>
                <Paragraph copyable style={{ margin: 0 }}>
                  {req.requisites}
                </Paragraph>
              </Descriptions.Item>
            )}
            {req.payment_details && (
              <Descriptions.Item label="Детали платежа" span={isMobile ? 1 : 2}>
                {req.payment_details}
              </Descriptions.Item>
            )}
          </Descriptions>

          {/* Позиции */}
          <Divider orientation="left" orientationMargin={0} style={{ margin: '20px 0 12px' }}>Позиции</Divider>
          <List
            size="small"
            dataSource={req.items}
            renderItem={(item) => (
              <List.Item>
                <Text style={{ flex: 1, minWidth: 0 }} ellipsis>
                  {item.project_item_name}
                </Text>
                <Text style={{ marginLeft: 8, whiteSpace: 'nowrap' }}>
                  {fmt(item.amount, req.currency)}
                </Text>
              </List.Item>
            )}
          />

          {/* Вложения */}
          {(req.attachments.length > 0 || isAdmin) && (
            <>
              <Divider orientation="left" orientationMargin={0} style={{ margin: '20px 0 12px' }}>
                Вложения ({req.attachments.length}/3)
              </Divider>
              {req.attachments.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  Нет вложений
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={req.attachments}
                  renderItem={(att) => (
                    <List.Item
                      actions={[
                        <Button
                          key="dl"
                          type="text"
                          size="small"
                          icon={<DownloadOutlined />}
                          onClick={() => handleDownloadFile(att.file_path)}
                          title="Скачать"
                        />,
                        ...(isAdmin
                          ? [
                              <Popconfirm
                                key="del"
                                title="Удалить файл?"
                                okText="Да"
                                cancelText="Отмена"
                                onConfirm={() => handleDeleteAttachment(att.id)}
                              >
                                <Button
                                  type="text"
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                  loading={deletingAtt === att.id}
                                />
                              </Popconfirm>,
                            ]
                          : []),
                      ]}
                    >
                      <Space>
                        <PaperClipOutlined />
                        <Text>{att.file_name}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </>
          )}

          {/* Платежи */}
          <Divider orientation="left" orientationMargin={0} style={{ margin: '20px 0 12px' }}>
            Платежи ({req.payments.length})
          </Divider>
          {req.payments.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 13 }}>
              Нет платежей
            </Text>
          ) : (
            <List
              size="small"
              dataSource={req.payments}
              renderItem={(pay) => {
                const isOwner = pay.created_by === user?.id;
                // admin может удалять любой; client только свои и только не confirmed
                const canDelete =
                  isAdmin || (isOwner && pay.status !== 'confirmed');
                const canConfirmReject = isAdmin && pay.status === 'pending';
                return (
                  <List.Item
                    actions={[
                      ...(pay.file_path
                        ? [
                            <Button
                              key="dl"
                              type="text"
                              size="small"
                              icon={<DownloadOutlined />}
                              onClick={() => pay.file_path && handleDownloadFile(pay.file_path)}
                              title="Скачать файл платежа"
                            />,
                          ]
                        : []),
                      ...(canConfirmReject
                        ? [
                            <Popconfirm
                              key="confirm"
                              title="Подтвердить платёж?"
                              okText="Да"
                              cancelText="Отмена"
                              onConfirm={() => handleConfirmPayment(pay.id)}
                            >
                              <Button
                                type="primary"
                                size="small"
                                loading={confirmingPay === pay.id}
                              >
                                Подтвердить
                              </Button>
                            </Popconfirm>,
                            <Button
                              key="reject"
                              danger
                              size="small"
                              loading={rejectingPay === pay.id}
                              onClick={() => openRejectModal(pay.id)}
                            >
                              Отклонить
                            </Button>,
                          ]
                        : []),
                      ...(canDelete
                        ? [
                            <Popconfirm
                              key="del"
                              title="Удалить платёж?"
                              okText="Да"
                              cancelText="Отмена"
                              onConfirm={() => handleDeletePayment(pay.id)}
                            >
                              <Button
                                type="text"
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                loading={deletingPay === pay.id}
                              />
                            </Popconfirm>,
                          ]
                        : []),
                    ]}
                  >
                    <div style={{ width: '100%' }}>
                      <Space wrap size={[8, 4]}>
                        <Text strong style={{ whiteSpace: 'nowrap' }}>
                          {fmt(pay.amount, pay.currency)}
                        </Text>
                        <Tag color={PAYMENT_STATUS_COLOR[pay.status]}>
                          {PAYMENT_STATUS_LABEL[pay.status]}
                        </Tag>
                        {pay.file_name && (
                          <Text type="secondary" style={{ fontSize: 11 }} title={pay.file_name}>
                            <PaperClipOutlined /> {pay.file_name}
                          </Text>
                        )}
                        {pay.note && <Text type="secondary">{pay.note}</Text>}
                        <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                          {new Date(pay.created_at).toLocaleDateString('ru-RU')}
                        </Text>
                      </Space>
                      {pay.payment_date ? (
                        <div style={{ marginTop: 2 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            Дата оплаты: {dayjs(pay.payment_date).format('DD.MM.YYYY')}
                          </Text>
                        </div>
                      ) : (
                        <div style={{ marginTop: 2 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            Дата оплаты не указана
                          </Text>
                        </div>
                      )}
                      {pay.status === 'rejected' && pay.rejection_reason && (
                        <div style={{ marginTop: 4 }}>
                          <Text type="danger" style={{ fontSize: 12 }}>
                            Причина отклонения: {pay.rejection_reason}
                          </Text>
                        </div>
                      )}
                    </div>
                  </List.Item>
                );
              }}
            />
          )}

          {/* Добавить платёж */}
          {!isCompleted && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              {addPaymentOpen ? (
                <Form
                  form={addPaymentForm}
                  layout="vertical"
                  onFinish={handleAddPayment}
                  initialValues={{ currency: req.currency }}
                >
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Form.Item
                      name="amount"
                      rules={[{ required: true, message: 'Укажите сумму' }]}
                      style={{ marginBottom: 8, flex: '0 0 140px' }}
                    >
                      <InputNumber placeholder="Сумма" min={0.01} style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item name="currency" style={{ marginBottom: 8, flex: '0 0 100px' }}>
                      <Select
                        options={[
                          { value: 'CNY', label: 'CNY' },
                          { value: 'USD', label: 'USD' },
                          { value: 'RUB', label: 'RUB' },
                        ]}
                      />
                    </Form.Item>
                    <Form.Item name="note" style={{ marginBottom: 8, flex: '1 1 180px' }}>
                      <Input placeholder="Примечание (необязательно)" />
                    </Form.Item>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <DatePicker
                      value={paymentDate}
                      onChange={(d) => setPaymentDate(d)}
                      format="DD.MM.YYYY"
                      placeholder="Дата оплаты"
                      style={{ width: '100%' }}
                      allowClear
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Upload
                      showUploadList={false}
                      beforeUpload={(file: RcFile) => {
                        if (!isPaymentFileSizeValid(file)) return Upload.LIST_IGNORE;
                        return false;
                      }}
                      fileList={paymentFile}
                      onChange={({ fileList }) => setPaymentFile(fileList.slice(0, 1))}
                      maxCount={1}
                    >
                      <Button size="small" icon={<UploadOutlined />}>
                        {paymentFile.length ? paymentFile[0].name : 'Прикрепить файл'}
                      </Button>
                    </Upload>
                    {paymentFile.length > 0 && (
                      <Button
                        size="small"
                        type="text"
                        danger
                        onClick={() => setPaymentFile([])}
                      >
                        ✕
                      </Button>
                    )}
                  </div>
                  <Space>
                    <Button
                      type="primary"
                      size="small"
                      loading={addPaymentLoading}
                      onClick={() => addPaymentForm.submit()}
                    >
                      Сохранить
                    </Button>
                    <Button
                      size="small"
                      onClick={() => {
                        addPaymentForm.resetFields();
                        setPaymentFile([]);
                        setPaymentDate(null);
                        setAddPaymentOpen(false);
                      }}
                    >
                      Отмена
                    </Button>
                  </Space>
                </Form>
              ) : (
                <Button
                  icon={<PlusOutlined />}
                  size="small"
                  onClick={() => {
                    addPaymentForm.setFieldValue('currency', req.currency);
                    setAddPaymentOpen(true);
                  }}
                >
                  Добавить платёж
                </Button>
              )}
            </>
          )}

          {/* Комментарии */}
          <Divider orientation="left" orientationMargin={0} style={{ margin: '20px 0 12px' }}>
            Комментарии ({comments.length})
          </Divider>
          {comments.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 13 }}>
              Нет комментариев
            </Text>
          ) : (
            <List
              size="small"
              dataSource={comments}
              renderItem={(c) => {
                const canDelete = isAdmin || c.author_id === user?.id;
                return (
                  <List.Item
                    actions={
                      canDelete
                        ? [
                            <Popconfirm
                              key="del"
                              title="Удалить комментарий?"
                              okText="Да"
                              cancelText="Отмена"
                              onConfirm={() => handleDeleteComment(c.id)}
                            >
                              <Button
                                type="text"
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                loading={deletingComment === c.id}
                              />
                            </Popconfirm>,
                          ]
                        : []
                    }
                  >
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                        <Text strong>{c.author_full_name}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {dayjs(c.created_at).format('DD.MM.YYYY HH:mm')}
                        </Text>
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 2 }}>
                        {c.text}
                      </div>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
          <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <Input.TextArea
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Добавить комментарий..."
              rows={2}
              maxLength={4000}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              loading={commentLoading}
              onClick={handleAddComment}
              disabled={!commentText.trim()}
            >
              Отправить
            </Button>
          </div>
        </>
      )}

      {/* Модалка отклонения платежа */}
      <Modal
        open={rejectModalPayId !== null}
        title="Отклонить платёж"
        okText="Отклонить"
        cancelText="Отмена"
        okButtonProps={{ danger: true, loading: rejectingPay !== null }}
        onOk={handleRejectPayment}
        onCancel={() => {
          setRejectModalPayId(null);
          setRejectReason('');
        }}
        destroyOnClose
      >
        <Paragraph>
          Укажите причину отклонения — клиент получит уведомление с этим сообщением.
        </Paragraph>
        <Input.TextArea
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="Причина отклонения"
          rows={3}
          maxLength={1000}
          autoFocus
        />
      </Modal>
    </Modal>
  );
}
