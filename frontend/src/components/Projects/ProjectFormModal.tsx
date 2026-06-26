import { useEffect, useState } from 'react';
import { Form, Input, Modal, Select, message } from 'antd';
import { createProject, updateProject } from '../../api/projects';
import type { Project, ProjectCreate, ProjectUpdate } from '../../types';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  project?: Project | null;
}

export default function ProjectFormModal({ open, onClose, onSuccess, project }: Props) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && project) {
      form.setFieldsValue({
        name: project.name,
        description: project.description ?? '',
        status: project.status,
      });
    } else if (open) {
      form.resetFields();
      form.setFieldsValue({ status: 'active' });
    }
  }, [open, project, form]);

  const handleSave = async (values: ProjectCreate) => {
    setLoading(true);
    try {
      if (project) {
        const upd: ProjectUpdate = {
          name: values.name,
          description: values.description || null,
          status: values.status,
        };
        await updateProject(project.id, upd);
        message.success('Проект обновлён');
      } else {
        await createProject({
          name: values.name,
          description: values.description || null,
          status: values.status ?? 'active',
        });
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
        <Form.Item name="status" label="Статус" initialValue="active">
          <Select
            options={[
              { value: 'active', label: 'В работе' },
              { value: 'closed', label: 'Закрытый' },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
