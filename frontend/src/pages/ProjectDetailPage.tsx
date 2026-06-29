import { useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Grid,
  Popconfirm,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  theme,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
} from '@ant-design/icons';
import {
  deleteProject,
  downloadProjectExport,
  getProject,
} from '../api/projects';
import { listItems } from '../api/projectItems';
import { usePaymentRequestFilters } from '../hooks/usePaymentRequestFilters';
import ItemsPanel from '../components/ProjectDetail/ItemsPanel';
import NotesPanel from '../components/ProjectDetail/NotesPanel';
import PaymentRequestsPanel from '../components/ProjectDetail/PaymentRequestsPanel';
import ProjectFormModal from '../components/Projects/ProjectFormModal';

const { Text, Title } = Typography;
const { useToken } = theme;
const { useBreakpoint } = Grid;

const STATUS_LABELS: Record<string, string> = {
  active: 'В работе',
  closed: 'Закрытый',
};
const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  closed: 'default',
};

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialReqId = searchParams.get('req') ? Number(searchParams.get('req')) : undefined;
  const queryClient = useQueryClient();
  const { token } = useToken();
  const screens = useBreakpoint();
  const isMobile = !screens.md; // < 768px
  const [editOpen, setEditOpen] = useState(false);

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: !!projectId,
  });

  // Фильтры заявок на оплату, общие для панели номенклатуры и панели заявок.
  const { filters, updateFilters } = usePaymentRequestFilters(projectId);

  const { data: items = [] } = useQuery({
    queryKey: ['project-items', projectId],
    queryFn: () => listItems(projectId),
    enabled: !!projectId,
  });

  const handleToggleVisible = (itemId: number, visible: boolean) => {
    const hidden = new Set(filters.hiddenItemIds);
    if (visible) hidden.delete(itemId);
    else hidden.add(itemId);
    updateFilters({ hiddenItemIds: [...hidden] });
  };

  const handleSetAllVisible = (visible: boolean) => {
    updateFilters({ hiddenItemIds: visible ? [] : items.map((i) => i.id) });
  };

  const handleDelete = async () => {
    try {
      await deleteProject(projectId);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      message.success('Проект удалён');
      navigate('/projects');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  const handleExport = async () => {
    if (!project) return;
    try {
      await downloadProjectExport(projectId, project.project_number);
      message.success('Файл Excel загружен');
    } catch {
      message.error('Не удалось выгрузить Excel');
    }
  };

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          paddingTop: 80,
          minHeight: '100vh',
          background: token.colorBgLayout,
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (!project) return null;

  // ── Шапка проекта (адаптивная) ──
  const header = (
    <div
      style={{
        background: token.colorBgContainer,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        padding: isMobile ? '12px 16px' : '14px 24px',
        flexShrink: 0,
      }}
    >
      {/* Строка 1: назад + название + статус + действия */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 8,
          flexWrap: 'wrap',
        }}
      >
        <Button
          icon={<ArrowLeftOutlined />}
          type="text"
          onClick={() => navigate('/projects')}
          style={{ flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            №{project.project_number}
          </Text>
          <Title
            level={isMobile ? 5 : 4}
            style={{
              margin: 0,
              letterSpacing: '-0.01em',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {project.name}
          </Title>
        </div>
        <Tag color={STATUS_COLORS[project.status]} style={{ flexShrink: 0 }}>
          {STATUS_LABELS[project.status] ?? project.status}
        </Tag>
        <Space size={4} wrap>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={handleExport}
          >
            {isMobile ? '' : 'Excel'}
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => setEditOpen(true)}
          >
            {isMobile ? '' : 'Редактировать'}
          </Button>
          <Popconfirm
            title="Удалить проект?"
            description="Проект без заявок на оплату будет удалён навсегда."
            okText="Удалить"
            okType="danger"
            cancelText="Отмена"
            onConfirm={handleDelete}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {isMobile ? '' : 'Удалить'}
            </Button>
          </Popconfirm>
        </Space>
      </div>
    </div>
  );

  // ── Мобильная раскладка: табы ──
  if (isMobile) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          background: token.colorBgLayout,
        }}
      >
        {header}
        <div style={{ flex: 1, background: token.colorBgContainer }}>
          <Tabs
            defaultActiveKey="items"
            centered
            destroyInactiveTabPane={false}
            items={[
              {
                key: 'items',
                label: 'Номенклатура',
                children: (
                  <ItemsPanel
                    projectId={projectId}
                    hiddenItemIds={filters.hiddenItemIds}
                    onToggleVisible={handleToggleVisible}
                    onSetAllVisible={handleSetAllVisible}
                  />
                ),
              },
              {
                key: 'payments',
                label: 'Заявки на оплату',
                children: (
                  <div style={{ background: token.colorBgLayout, minHeight: 200 }}>
                    <PaymentRequestsPanel
                      projectId={projectId}
                      initialReqId={initialReqId}
                      filters={filters}
                      updateFilters={updateFilters}
                    />
                  </div>
                ),
              },
              {
                key: 'notes',
                label: 'Заметки',
                children: (
                  <div style={{ background: token.colorBgContainer, minHeight: 200 }}>
                    <NotesPanel projectId={projectId} />
                  </div>
                ),
              },
            ]}
            tabBarStyle={{
              margin: 0,
              padding: '0 12px',
              background: token.colorBgContainer,
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
            }}
          />
        </div>

        <ProjectFormModal
          open={editOpen}
          project={project}
          onClose={() => setEditOpen(false)}
          onSuccess={() => {
            setEditOpen(false);
            queryClient.invalidateQueries({ queryKey: ['project', projectId] });
            queryClient.invalidateQueries({ queryKey: ['projects'] });
          }}
        />
      </div>
    );
  }

  // ── Десктопная раскладка: две панели ──
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: token.colorBgLayout,
      }}
    >
      {header}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Левая панель — номенклатура (шире, чтобы помещались названия) */}
        <div
          style={{
            width: '64%',
            minWidth: 320,
            borderRight: `1px solid ${token.colorBorderSecondary}`,
            overflowY: 'auto',
            background: token.colorBgContainer,
          }}
        >
          <ItemsPanel
            projectId={projectId}
            hiddenItemIds={filters.hiddenItemIds}
            onToggleVisible={handleToggleVisible}
            onSetAllVisible={handleSetAllVisible}
          />
        </div>

        {/* Правая колонка — заявки на оплату, под ними заметки */}
        <div
          style={{
            flex: 1,
            minWidth: 320,
            overflowY: 'auto',
            background: token.colorBgLayout,
          }}
        >
          <PaymentRequestsPanel
            projectId={projectId}
            initialReqId={initialReqId}
            filters={filters}
            updateFilters={updateFilters}
          />

          <div
            style={{
              borderTop: `1px solid ${token.colorBorderSecondary}`,
              background: token.colorBgLayout,
            }}
          >
            <NotesPanel projectId={projectId} />
          </div>
        </div>
      </div>

      <ProjectFormModal
        open={editOpen}
        project={project}
        onClose={() => setEditOpen(false)}
        onSuccess={() => {
          setEditOpen(false);
          queryClient.invalidateQueries({ queryKey: ['project', projectId] });
          queryClient.invalidateQueries({ queryKey: ['projects'] });
        }}
      />
    </div>
  );
}
