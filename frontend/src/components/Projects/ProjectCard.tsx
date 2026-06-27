import { Card, Tag, Typography, Button, Popconfirm } from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { Project } from '../../types';

const { Text, Title } = Typography;

const STATUS_LABELS: Record<string, string> = {
  active: 'В работе',
  closed: 'Закрытый',
};
const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  closed: 'default',
};

interface Props {
  project: Project;
  onDelete?: (id: number) => void;
  onEdit?: (project: Project) => void;
}

export default function ProjectCard({ project, onDelete, onEdit }: Props) {
  const navigate = useNavigate();

  return (
    <Card
      hoverable
      className="project-card"
      style={{ cursor: 'pointer', width: '100%', height: '100%' }}
      onClick={() => navigate(`/projects/${project.id}`)}
      actions={
        onDelete || onEdit
          ? [
              ...(onEdit
                ? [
                    <Button
                      key="edit"
                      type="text"
                      icon={<EditOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        onEdit(project);
                      }}
                    />,
                  ]
                : []),
              ...(onDelete
                ? [
                    <Popconfirm
                      key="delete"
                      title="Удалить проект?"
                      description="Проект без заявок на оплату будет удалён."
                      okText="Удалить"
                      cancelText="Отмена"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        onDelete(project.id);
                      }}
                      onPopupClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]
                : []),
            ]
          : undefined
      }
    >
      {/* Строка: номер и статус выровнены по центру */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <Text type="secondary" style={{ fontSize: 11 }}>
          №{project.project_number}
        </Text>
        <Tag
          color={STATUS_COLORS[project.status]}
          style={{ flexShrink: 0, margin: 0 }}
        >
          {STATUS_LABELS[project.status] ?? project.status}
        </Tag>
      </div>
      {/* Название с обрезкой длинных строк */}
      <Title
        level={5}
        style={{ margin: '0 0 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        title={project.name}
      >
        {project.name}
      </Title>
      {project.description && (
        <Text
          type="secondary"
          className="project-card__desc"
          style={{ fontSize: 13 }}
          title={project.description}
        >
          {project.description}
        </Text>
      )}
    </Card>
  );
}
