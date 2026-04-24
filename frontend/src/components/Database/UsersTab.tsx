import { useState } from 'react';
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, LinkOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listUsers, createUser, updateUser, deleteUser, generateTelegramLink } from '../../api/users';
import type { User, UserCreate, UserUpdate } from '../../types';

const { Text } = Typography;

const ROLE_LABELS: Record<string, string> = { admin: 'Администратор', client: 'Клиент' };
const ROLE_COLORS: Record<string, string> = { admin: 'blue', client: 'green' };

export default function UsersTab() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [tgToken, setTgToken] = useState<string | null>(null);
  const [tgModalOpen, setTgModalOpen] = useState(false);
  const [tgLoading, setTgLoading] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (user: User) => {
    setEditing(user);
    form.setFieldsValue({
      full_name: user.full_name,
      login: user.login,
      role: user.role,
      description: user.description ?? '',
      password: '',
    });
    setModalOpen(true);
  };

  const handleSave = async (values: UserCreate & { password?: string }) => {
    setLoading(true);
    try {
      if (editing) {
        const upd: UserUpdate = {
          full_name: values.full_name,
          login: values.login,
          role: values.role,
          description: values.description || null,
        };
        if (values.password) upd.password = values.password;
        await updateUser(editing.id, upd);
        message.success('Пользователь обновлён');
      } else {
        await createUser(values as UserCreate);
        message.success('Пользователь создан');
      }
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setModalOpen(false);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка сохранения');
    } finally {
      setLoading(false);
    }
  };

  const handleTelegramLink = async (userId: number) => {
    setTgLoading(userId);
    try {
      const { token } = await generateTelegramLink(userId);
      setTgToken(token);
      setTgModalOpen(true);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка генерации токена');
    } finally {
      setTgLoading(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteUser(id);
      queryClient.invalidateQueries({ queryKey: ['users'] });
      message.success('Пользователь удалён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  const columns = [
    { title: 'ФИО', dataIndex: 'full_name', key: 'full_name', width: 200, ellipsis: true },
    { title: 'Логин', dataIndex: 'login', key: 'login', width: 140, ellipsis: true },
    {
      title: 'Роль',
      dataIndex: 'role',
      key: 'role',
      width: 140,
      render: (role: string) => (
        <Tag color={ROLE_COLORS[role]}>{ROLE_LABELS[role] ?? role}</Tag>
      ),
    },
    { title: 'Описание', dataIndex: 'description', key: 'description', width: 240, ellipsis: true },
    {
      title: 'Действия',
      key: 'actions',
      width: 160,
      fixed: 'right' as const,
      render: (_: unknown, record: User) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          />
          <Button
            size="small"
            icon={<LinkOutlined />}
            loading={tgLoading === record.id}
            onClick={() => handleTelegramLink(record.id)}
            title="Сгенерировать токен Telegram"
          />
          <Popconfirm
            title="Удалить пользователя?"
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
          Добавить пользователя
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

      {/* Модальное окно токена привязки Telegram */}
      <Modal
        open={tgModalOpen}
        title="Привязка Telegram"
        onCancel={() => { setTgModalOpen(false); setTgToken(null); }}
        footer={
          <Button onClick={() => { setTgModalOpen(false); setTgToken(null); }}>
            Закрыть
          </Button>
        }
      >
        <p>Передайте пользователю следующую инструкцию:</p>
        <p>Откройте бота и отправьте команду:</p>
        <Text code copyable style={{ fontSize: 13 }}>
          /start {tgToken ?? ''}
        </Text>
        <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
          Токен действителен 24 часа.
        </Text>
      </Modal>

      <Modal
        open={modalOpen}
        title={editing ? 'Редактировать пользователя' : 'Новый пользователь'}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="Сохранить"
        cancelText="Отмена"
        confirmLoading={loading}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="full_name"
            label="ФИО"
            rules={[{ required: true, message: 'Введите ФИО' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="login"
            label="Логин"
            rules={[{ required: true, message: 'Введите логин' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label={editing ? 'Новый пароль (оставьте пустым, чтобы не менять)' : 'Пароль'}
            rules={editing ? [] : [{ required: true, message: 'Введите пароль' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="role"
            label="Роль"
            rules={[{ required: true, message: 'Выберите роль' }]}
          >
            <Select
              options={[
                { value: 'admin', label: 'Администратор' },
                { value: 'client', label: 'Клиент' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
