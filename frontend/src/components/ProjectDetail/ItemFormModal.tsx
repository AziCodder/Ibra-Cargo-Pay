import { useEffect, useState } from 'react';
import { Form, Input, InputNumber, Modal, Select, Switch, message } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { createItem, updateItem } from '../../api/projectItems';
import { listSuppliersBrief } from '../../api/suppliers';
import { useAuth } from '../../contexts/AuthContext';
import type { ProjectItem, ProjectItemCreate, ProjectItemUpdate } from '../../types';

interface Props {
  open: boolean;
  projectId: number;
  item?: ProjectItem | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ItemFormModal({ open, projectId, item, onClose, onSuccess }: Props) {
  const { isAdmin } = useAuth();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const { data: suppliers = [] } = useQuery({
    queryKey: ['suppliers-brief'],
    queryFn: listSuppliersBrief,
    enabled: open,
  });

  const supplierOptions = [
    { value: null, label: '— Без поставщика —' },
    ...suppliers.map((s) => ({ value: s.id, label: s.full_name })),
  ];

  useEffect(() => {
    if (open && item) {
      form.setFieldsValue({
        name: item.name,
        details: item.details ?? '',
        quantity: parseFloat(item.quantity),
        supplier_id: item.supplier_id ?? null,
        price: parseFloat(item.price),
        cost_price: item.cost_price ? parseFloat(item.cost_price) : undefined,
        currency: item.currency,
        commission: parseFloat(item.commission),
        shared_access: item.shared_access,
      });
    } else if (open) {
      form.resetFields();
      form.setFieldsValue({ currency: 'CNY', commission: 0 });
    }
  }, [open, item, form]);

  const handleSave = async (values: ProjectItemCreate & { shared_access?: boolean }) => {
    setLoading(true);
    try {
      if (item) {
        const upd: ProjectItemUpdate = {
          name: values.name,
          details: values.details || null,
          quantity: values.quantity,
          supplier_id: values.supplier_id,
          price: values.price,
          currency: values.currency,
          commission: values.commission,
        };
        if (isAdmin) {
          upd.cost_price = values.cost_price;
          upd.shared_access = values.shared_access;
        }
        await updateItem(projectId, item.id, upd);
        message.success('Позиция обновлена');
      } else {
        const payload: ProjectItemCreate = {
          name: values.name,
          details: values.details || null,
          quantity: values.quantity,
          supplier_id: values.supplier_id,
          price: values.price,
          currency: values.currency,
          commission: values.commission,
        };
        if (isAdmin && values.cost_price != null) {
          payload.cost_price = values.cost_price;
        }
        await createItem(projectId, payload);
        message.success('Позиция добавлена');
      }
      onSuccess();
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
      title={item ? 'Редактировать позицию' : 'Новая позиция'}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Сохранить"
      cancelText="Отмена"
      confirmLoading={loading}
      width="min(560px, 94vw)"
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item
          name="name"
          label="Наименование"
          rules={[{ required: true, message: 'Введите наименование' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="details" label="Описание / детали">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item
          name="quantity"
          label="Количество"
          rules={[{ required: true, message: 'Введите количество' }]}
        >
          <InputNumber min={0.01} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="supplier_id" label="Поставщик">
          <Select options={supplierOptions} allowClear placeholder="Выберите поставщика" />
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
        <Form.Item
          name="price"
          label="Цена"
          rules={[{ required: true, message: 'Введите цену' }]}
        >
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>
        {isAdmin && (
          <Form.Item name="cost_price" label="Себестоимость">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        )}
        <Form.Item name="commission" label="Комиссия (%)">
          <InputNumber min={0} max={100} style={{ width: '100%' }} />
        </Form.Item>
        {isAdmin && item && (
          <Form.Item
            name="shared_access"
            label="Общий доступ (client может редактировать)"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
