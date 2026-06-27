import { useState, useEffect, type CSSProperties } from 'react';
import { Button, Radio, Select, Spin, Empty, message, Row, Col } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { listProjects, deleteProject, reorderProjects } from '../api/projects';
import type { ProjectSortBy, ProjectSortOrder } from '../api/projects';
import ProjectCard from '../components/Projects/ProjectCard';
import ProjectFormModal from '../components/Projects/ProjectFormModal';
import type { Project, ProjectListOut } from '../types';
import {
  readProjectSortFromStorage,
  writeProjectSortToStorage,
} from '../utils/projectSort';

type StatusFilter = 'all' | 'active' | 'closed';

const SORT_OPTIONS = [
  { value: 'created_at:desc', label: 'Дата ↓ (новые)' },
  { value: 'created_at:asc', label: 'Дата ↑ (старые)' },
  { value: 'name:asc', label: 'Имя ↑ (А–Я)' },
  { value: 'name:desc', label: 'Имя ↓ (Я–А)' },
  { value: 'manual:asc', label: 'Вручную (перетаскивание)' },
];

/** Карточка проекта с поддержкой перетаскивания (long-press ~0.5с). */
function SortableProjectCol({
  project,
  onDelete,
  onEdit,
}: {
  project: Project;
  onDelete: (id: number) => void;
  onEdit: (project: Project) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: project.id });

  const style: CSSProperties = {
    transform: isDragging
      ? `${CSS.Transform.toString(transform)} scale(1.03)`
      : CSS.Transform.toString(transform),
    transition,
    touchAction: 'manipulation',
    cursor: 'grab',
    height: '100%',
    width: '100%',
    ...(isDragging ? { opacity: 0.6, zIndex: 999, position: 'relative' } : {}),
  };

  return (
    <Col xs={24} sm={12} lg={8} xl={6} style={{ display: 'flex' }}>
      <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
        <ProjectCard project={project} onDelete={onDelete} onEdit={onEdit} />
      </div>
    </Col>
  );
}

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialStatus = (): StatusFilter => {
    const s = searchParams.get('status');
    if (s === 'active' || s === 'closed') return s;
    if (s === 'all') return 'all';
    return 'active';
  };

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initialStatus);
  const [sort, setSort] = useState(readProjectSortFromStorage);
  const [showCreate, setShowCreate] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);

  useEffect(() => {
    if (!searchParams.get('status')) {
      setSearchParams({ status: 'active' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const sortSelectValue = `${sort.sortBy}:${sort.sortOrder}`;

  const { data, isLoading } = useQuery({
    queryKey: ['projects', statusFilter, sort.sortBy, sort.sortOrder],
    queryFn: () =>
      listProjects({
        status: statusFilter === 'all' ? undefined : statusFilter,
        sortBy: sort.sortBy,
        sortOrder: sort.sortOrder,
      }),
  });

  const handleSortChange = (value: string) => {
    const [sortBy, sortOrder] = value.split(':') as [ProjectSortBy, ProjectSortOrder];
    const next = { sortBy, sortOrder };
    setSort(next);
    writeProjectSortToStorage(next);
  };

  // Перетаскивание доступно только в режиме «Вручную». Активация — удержание ~0.5с.
  const isManual = sort.sortBy === 'manual';
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { delay: 500, tolerance: 8 },
    }),
  );

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const current = data?.items ?? [];
    const oldIndex = current.findIndex((p) => p.id === active.id);
    const newIndex = current.findIndex((p) => p.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const next = arrayMove(current, oldIndex, newIndex);
    const queryKey = ['projects', statusFilter, sort.sortBy, sort.sortOrder];
    const prevData = data;
    queryClient.setQueryData<ProjectListOut>(queryKey, (old) =>
      old ? { ...old, items: next } : old,
    );

    try {
      await reorderProjects(next.map((p) => p.id));
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    } catch (err: unknown) {
      queryClient.setQueryData(queryKey, prevData);
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Не удалось изменить порядок');
    }
  };

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
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setShowCreate(true)}
        >
          Создать проект
        </Button>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 20,
          alignItems: 'center',
        }}
      >
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
          optionType="button"
          buttonStyle="solid"
          options={[
            { label: 'В работе', value: 'active' },
            { label: 'Закрытые', value: 'closed' },
            { label: 'Все', value: 'all' },
          ]}
        />
        <Select
          value={sortSelectValue}
          onChange={handleSortChange}
          options={SORT_OPTIONS}
          style={{ minWidth: 200 }}
          aria-label="Сортировка проектов"
        />
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', paddingTop: 64 }}>
          <Spin size="large" />
        </div>
      ) : !data?.items.length ? (
        <Empty description="Нет проектов" />
      ) : isManual ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={data.items.map((p) => p.id)}
            strategy={rectSortingStrategy}
          >
            <Row gutter={[16, 16]}>
              {data.items.map((project) => (
                <SortableProjectCol
                  key={project.id}
                  project={project}
                  onDelete={handleDelete}
                  onEdit={setEditProject}
                />
              ))}
            </Row>
          </SortableContext>
        </DndContext>
      ) : (
        <Row gutter={[16, 16]}>
          {data.items.map((project) => (
            <Col key={project.id} xs={24} sm={12} lg={8} xl={6} style={{ display: 'flex' }}>
              <ProjectCard
                project={project}
                onDelete={handleDelete}
                onEdit={setEditProject}
              />
            </Col>
          ))}
        </Row>
      )}

      {(showCreate || editProject) && (
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
