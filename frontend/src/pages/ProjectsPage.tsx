import { useState } from 'react';
import { Button, Radio, Spin, Empty, message, Row, Col } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listProjects, deleteProject } from '../api/projects';
import { useAuth } from '../contexts/AuthContext';
import ProjectCard from '../components/Projects/ProjectCard';
import ProjectFormModal from '../components/Projects/ProjectFormModal';
import type { Project } from '../types';

type StatusFilter = 'all' | 'active' | 'closed';

export default function ProjectsPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialStatus = (): StatusFilter => {
    const s = searchParams.get('status');
    if (s === 'active' || s === 'closed') return s;
    return 'all';
  };

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initialStatus);
  const [showCreate, setShowCreate] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['projects', statusFilter],
    queryFn: () =>
      listProjects({ status: statusFilter === 'all' ? undefined : statusFilter }),
  });

  const handleDelete = async (id: number) => {
    try {
      await deleteProject(id);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      message.success('Проект удалён');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  const handleModalSuccess = () => {
    setShowCreate(false);
    setEditProject(null);
    queryClient.invalidateQueries({ queryKey: ['projects'] });
  };

  return (
    <div style={{ padding: 'clamp(16px, 3vw, 24px)' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <h2 style={{ margin: 0, fontSize: 'clamp(18px, 3vw, 22px)' }}>Проекты</h2>
        {isAdmin && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowCreate(true)}
          >
            Создать проект
          </Button>
        )}
      </div>

      <Radio.Group
        value={statusFilter}
        onChange={(e) => {
          const val = e.target.value as StatusFilter;
          setStatusFilter(val);
          if (val === 'all') {
            setSearchParams({});
          } else {
            setSearchParams({ status: val });
          }
        }}
        style={{ marginBottom: 20 }}
        optionType="button"
        buttonStyle="solid"
        options={[
          { label: 'Все', value: 'all' },
          { label: 'В работе', value: 'active' },
          { label: 'Закрытые', value: 'closed' },
        ]}
      />

      {isLoading ? (
        <div style={{ textAlign: 'center', paddingTop: 64 }}>
          <Spin size="large" />
        </div>
      ) : !data?.items.length ? (
        <Empty description="Нет проектов" />
      ) : (
        <Row gutter={[16, 16]}>
          {data.items.map((project) => (
            <Col key={project.id} xs={24} sm={12} lg={8} xl={6} style={{ display: 'flex' }}>
              <ProjectCard
                project={project}
                onDelete={isAdmin ? handleDelete : undefined}
                onEdit={isAdmin ? setEditProject : undefined}
              />
            </Col>
          ))}
        </Row>
      )}

      {isAdmin && (showCreate || editProject) && (
        <ProjectFormModal
          open={showCreate || !!editProject}
          project={editProject}
          onClose={() => {
            setShowCreate(false);
            setEditProject(null);
          }}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
}
