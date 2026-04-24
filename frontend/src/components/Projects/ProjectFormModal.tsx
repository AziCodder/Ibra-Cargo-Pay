import { useEffect, useState } from 'react';
import { Form, Input, Modal, Select, message } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { createProject, updateProject } from '../../api/projects';
import { listUsers } from '../../api/users';
import type { Project, ProjectCreate, ProjectUpdate } from '../../types';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  project?: Project | null; // если передан — режим редактирования
}

export default function ProjectFormModal({ open, onClose, onSuccess, project }: Props) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(1, 200),
  });

  // Фильтруем только клиентов для выбора
  const clientOptions =
    usersData?.items
      .filter((u) => u.role === 'client')
      .map((u) => ({ value: u.id, label: u.full_name })) ?? [];

  useEffect(() => {
    if (open && project) {
      form.setFieldsValue({
        name: project.name,
        description: project.description ?? '',
        client_id: project.client_id,
        status: project.status,
      });
    } else if (open) {
      form.resetFields();
    }
  }, [open, project, form]);

  const handleSave = async (values: ProjectCreate) => {
    setLoading(true);
    try {
      if (project) {
        const upd: ProjectUpdate = {
          name: values.name,
          description: values.description || null,
          client_id: values.client_id,
          status: values.status,
        };
        await updateProject(project.id, upd);
        message.success('Проект обновлён');
      } else {
        await createProject(values);
        message.success('Проект создан');
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
      title={project ? 'Редактировать проект' : 'Новый проект'}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Сохранить"
      cancelText="Отмена"
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item
          name="name"
          label="Название"
          rules={[{ required: true, message: 'Введите название' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="description" label="Описание">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item
          name="client_id"
          label="Клиент"
          rules={[{ required: true, message: 'Выберите клиента' }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            options={clientOptions}
            placeholder="Выберите клиента"
          />
        </Form.Item>
        {project && (
          <Form.Item name="status" label="Статус">
            <Select
              options={[
                { value: 'active', label: 'В работе' },
                { value: 'closed', label: 'Закрытый' },
              ]}
            />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
