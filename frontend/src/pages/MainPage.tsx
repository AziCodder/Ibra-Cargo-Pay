import { useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Tooltip, Button, Drawer, Grid, theme } from 'antd';
import {
  DatabaseOutlined,
  FolderOutlined,
  HomeOutlined,
  LogoutOutlined,
  MenuOutlined,
  MoonOutlined,
  SunOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';

const { Sider, Content, Header } = Layout;
const { useToken } = theme;
const { useBreakpoint } = Grid;

export default function MainPage() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, toggle } = useTheme();
  const { token } = useToken();
  const screens = useBreakpoint();
  const isMobile = !screens.lg; // ≤ 991px
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Клиент — сразу редирект на проекты
  if (user?.role === 'client' && location.pathname === '/') {
    return <Navigate to="/projects" replace />;
  }

  const menuItems = [
    ...(isAdmin
      ? [
          {
            key: '/',
            icon: <HomeOutlined />,
            label: 'Главная',
          },
          {
            key: '/database',
            icon: <DatabaseOutlined />,
            label: 'База данных',
          },
        ]
      : []),
    {
      key: '/projects',
      icon: <FolderOutlined />,
      label: 'Проекты',
    },
  ];

  const selectedKey = location.pathname.startsWith('/database')
    ? '/database'
    : location.pathname.startsWith('/projects')
      ? '/projects'
      : '/';

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
    if (isMobile) setDrawerOpen(false);
  };

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  // ── Содержимое сайдбара (используется и в Sider, и в Drawer) ──
  const sidebarContent = (
    <>
      {/* Бренд */}
      <div
        style={{
          padding: '20px 20px 16px',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            fontWeight: 600,
            fontSize: 15,
            color: token.colorText,
            letterSpacing: '-0.01em',
          }}
        >
          Управление проектами
        </div>
        {user?.full_name && (
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: token.colorTextTertiary,
            }}
          >
            {user.full_name}
          </div>
        )}
      </div>

      {/* Меню (занимает всё доступное пространство) */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            borderRight: 0,
            padding: '8px 10px',
            background: 'transparent',
          }}
        />
      </div>

      {/* Низ сайдбара: переключатель темы + выход */}
      <div
        style={{
          padding: '12px',
          borderTop: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <Tooltip
          title={mode === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          placement="top"
        >
          <Button
            icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
            onClick={toggle}
            style={{ flex: 1 }}
          >
            {mode === 'dark' ? 'Светлая' : 'Тёмная'}
          </Button>
        </Tooltip>
        <Tooltip title="Выйти" placement="top">
          <Button
            danger
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            aria-label="Выйти"
          />
        </Tooltip>
      </div>
    </>
  );

  // ── Мобильный режим: top-bar с гамбургером + Drawer ──
  if (isMobile) {
    return (
      <Layout style={{ minHeight: '100vh' }}>
        <Header
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 10,
            padding: '0 12px',
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            height: 56,
            lineHeight: '56px',
          }}
        >
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setDrawerOpen(true)}
            aria-label="Открыть меню"
            style={{ fontSize: 18 }}
          />
          <div
            style={{
              fontWeight: 600,
              fontSize: 15,
              color: token.colorText,
              letterSpacing: '-0.01em',
            }}
          >
            Управление проектами
          </div>
        </Header>

        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={Math.min(280, window.innerWidth - 48)}
          closable={false}
          className="app-mobile-drawer"
          styles={{
            body: {
              padding: 0,
              background: token.colorBgContainer,
              display: 'flex',
              flexDirection: 'column',
            },
            header: { display: 'none' },
          }}
        >
          {sidebarContent}
        </Drawer>

        <Content
          style={{
            background: token.colorBgLayout,
            minHeight: 'calc(100vh - 56px)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    );
  }

  // ── Десктопный режим ──
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        theme={mode === 'dark' ? 'dark' : 'light'}
        width={232}
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
        }}
      >
        {sidebarContent}
      </Sider>
      <Layout>
        <Content
          style={{
            background: token.colorBgLayout,
            minHeight: '100vh',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
