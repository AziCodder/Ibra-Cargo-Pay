import { useEffect, useState } from 'react';
import { Form, Input, InputNumber, Modal, Select, message } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { createItem, updateItem } from '../../api/projectItems';
import { listSuppliers } from '../../api/suppliers';
import type { ProjectItem, ProjectItemCreate, ProjectItemUpdate } from '../../types';

interface Props {
  open: boolean;
  projectId: number;
  item?: ProjectItem | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ItemFormModal({ open, projectId, item, onClose, onSuccess }: Props) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const { data: suppliersData } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => listSuppliers(1, 200),
  });

  const supplierOptions = [
    { value: null, label: '— Без поставщика —' },
    ...(suppliersData?.items.map((s) => ({ value: s.id, label: s.full_name })) ?? []),
  ];

  useEffect(() => {
    if (open && item) {
      form.setFieldsValue({
        name: item.name,
        details: item.details ?? '',
        quantity: parseFloat(item.quantity),
        supplier_id: item.supplier_id ?? null,
        price: parseFloat(item.price),
        cost_price: item.cost_price ? parseFloat(item.cost_price) : 0,
        currency: item.currency,
        commission: parseFloat(item.commission),
      });
    } else if (open) {
      form.resetFields();
      form.setFieldsValue({ currency: 'CNY', commission: 0 });
    }
  }, [open, item, form]);

  const handleSave = async (values: ProjectItemCreate) => {
    setLoading(true);
    try {
      if (item) {
        const upd: ProjectItemUpdate = { ...values };
        await updateItem(projectId, item.id, upd);
        message.success('Позиция обновлена');
      } else {
        await createItem(projectId, values);
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
        <Form.Item
          name="cost_price"
          label="Себестоимость"
          rules={[{ required: true, message: 'Введите себестоимость' }]}
        >
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="commission" label="Комиссия (%)">
          <InputNumber min={0} max={100} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
