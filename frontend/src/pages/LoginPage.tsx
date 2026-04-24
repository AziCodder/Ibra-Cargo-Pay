import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, Alert, theme, Tooltip } from 'antd';
import { LockOutlined, UserOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import type { LoginRequest } from '../types';

const { Title, Text } = Typography;
const { useToken } = theme;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { mode, toggle } = useTheme();
  const { token } = useToken();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: LoginRequest) => {
    setError(null);
    setLoading(true);
    try {
      await login(values);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      const detail = axiosError.response?.data?.detail;
      setError(detail ?? 'Ошибка входа. Попробуйте ещё раз.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: token.colorBgLayout,
        position: 'relative',
        padding: 16,
      }}
    >
      {/* Переключатель темы в правом верхнем углу */}
      <Tooltip title={mode === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
        <Button
          type="text"
          shape="circle"
          icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
          onClick={toggle}
          style={{ position: 'absolute', top: 20, right: 20 }}
        />
      </Tooltip>

      <Card
        style={{
          width: 380,
          boxShadow: token.boxShadowSecondary,
          border: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <Title level={3} style={{ margin: 0, letterSpacing: '-0.01em' }}>
            Управление проектами
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Войдите, чтобы продолжить
          </Text>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Form<LoginRequest>
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
          requiredMark={false}
        >
          <Form.Item
            name="login"
            rules={[{ required: true, message: 'Введите логин' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: token.colorTextTertiary }} />}
              placeholder="Логин"
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Введите пароль' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />}
              placeholder="Пароль"
              size="large"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              loading={loading}
              block
            >
              Войти
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
