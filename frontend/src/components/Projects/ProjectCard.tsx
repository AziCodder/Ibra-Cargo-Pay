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
      style={{ cursor: 'pointer' }}
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
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ flex: 1, marginRight: 8 }}>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
            №{project.project_number}
          </Text>
          <Title level={5} style={{ margin: 0 }}>
            {project.name}
          </Title>
        </div>
        <Tag
          color={STATUS_COLORS[project.status]}
          style={{ alignSelf: 'flex-start', flexShrink: 0, marginTop: 2 }}
        >
          {STATUS_LABELS[project.status] ?? project.status}
        </Tag>
      </div>
      {project.description && (
        <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
          {project.description}
        </Text>
      )}
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        Клиент: {project.client.full_name}
      </Text>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
        Создан: {new Date(project.created_at).toLocaleDateString('ru-RU')}
      </Text>
    </Card>
  );
}
