import { ConfigProvider, App as AntdApp } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { getThemeConfig } from './theme/tokens';
import './theme/global.css';
import ProtectedRoute from './components/Auth/ProtectedRoute';
import AdminRoute from './components/Auth/AdminRoute';
import LoginPage from './pages/LoginPage';
import MainPage from './pages/MainPage';
import DashboardPage from './pages/DashboardPage';
import DatabasePage from './pages/DatabasePage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import NotFoundPage from './pages/NotFoundPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

/** На корневой путь: admin → дашборд, client → проекты */
function RootRedirect() {
  const { user } = useAuth();
  if (user?.role === 'admin') return <DashboardPage />;
  return <Navigate to="/projects" replace />;
}

/** Обёртка: берёт текущую тему из контекста и передаёт в ConfigProvider */
function ThemedApp() {
  const { mode } = useTheme();
  return (
    <ConfigProvider locale={ruRU} theme={getThemeConfig(mode)}>
      <AntdApp>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              {/* Все защищённые маршруты */}
              <Route element={<ProtectedRoute />}>
                {/* Маршруты с боковой панелью */}
                <Route element={<MainPage />}>
                  {/* База данных — только для администратора */}
                  <Route element={<AdminRoute />}>
                    <Route path="/database" element={<DatabasePage />} />
                    <Route path="/database/users" element={<DatabasePage />} />
                    <Route path="/database/suppliers" element={<DatabasePage />} />
                    <Route path="/database/audit" element={<DatabasePage />} />
                    <Route path="/database/backups" element={<DatabasePage />} />
                    <Route path="/database/status" element={<DatabasePage />} />
                  </Route>

                  {/* Проекты — для всех авторизованных */}
                  <Route path="/projects" element={<ProjectsPage />} />

                  {/* Корень: admin → дашборд, client → проекты */}
                  <Route path="/" element={<RootRedirect />} />
                </Route>

                {/* Детальная страница проекта — без боковой панели */}
                <Route path="/projects/:id" element={<ProjectDetailPage />} />
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ThemedApp />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
