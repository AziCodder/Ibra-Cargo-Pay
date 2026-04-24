import { Tabs } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import UsersTab from '../components/Database/UsersTab';
import SuppliersTab from '../components/Database/SuppliersTab';
import AuditLogTab from '../components/Database/AuditLogTab';
import BackupsTab from '../components/Database/BackupsTab';

export default function DatabasePage() {
  const navigate = useNavigate();
  const location = useLocation();

  const activeKey = location.pathname.includes('suppliers')
    ? 'suppliers'
    : location.pathname.includes('audit')
      ? 'audit'
      : location.pathname.includes('backups')
        ? 'backups'
        : 'users';

  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ marginTop: 0, marginBottom: 24 }}>База данных</h2>
      <Tabs
        activeKey={activeKey}
        onChange={(key) => navigate(`/database/${key}`)}
        items={[
          { key: 'users', label: 'Пользователи', children: <UsersTab /> },
          { key: 'suppliers', label: 'Поставщики', children: <SuppliersTab /> },
          { key: 'audit', label: 'Журнал изменений', children: <AuditLogTab /> },
          { key: 'backups', label: 'Бэкапы', children: <BackupsTab /> },
        ]}
      />
    </div>
  );
}
