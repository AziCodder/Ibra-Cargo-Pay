import { useState } from 'react';
import {
  Button,
  Empty,
  Input,
  List,
  Popconfirm,
  Radio,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createProjectNote,
  deleteProjectNote,
  listProjectNotes,
  updateProjectNote,
} from '../../api/projectNotes';
import type { NoteVisibility, ProjectNote } from '../../types';

const { Text } = Typography;
const { TextArea } = Input;

interface Props {
  projectId: number;
}

export default function NotesPanel({ projectId }: Props) {
  const queryClient = useQueryClient();
  const [newContent, setNewContent] = useState('');
  const [newVisibility, setNewVisibility] = useState<NoteVisibility>('private');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editVisibility, setEditVisibility] = useState<NoteVisibility>('private');
  const [saving, setSaving] = useState(false);

  const { data: notes = [], isLoading } = useQuery({
    queryKey: ['project-notes', projectId],
    queryFn: () => listProjectNotes(projectId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['project-notes', projectId] });
  };

  const handleCreate = async () => {
    const content = newContent.trim();
    if (!content) {
      message.warning('Введите текст заметки');
      return;
    }
    setCreating(true);
    try {
      await createProjectNote(projectId, { content, visibility: newVisibility });
      setNewContent('');
      setNewVisibility('private');
      invalidate();
      message.success('Заметка добавлена');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (note: ProjectNote) => {
    setEditingId(note.id);
    setEditContent(note.content);
    setEditVisibility(note.visibility);
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const content = editContent.trim();
    if (!content) {
      message.warning('Введите текст заметки');
      return;
    }
    setSaving(true);
    try {
      await updateProjectNote(projectId, editingId, {
        content,
        visibility: editVisibility,
      });
      setEditingId(null);
      invalidate();
      message.success('Заметка обновлена');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noteId: number) => {
    try {
      await deleteProjectNote(projectId, noteId);
      invalidate();
      message.success('Заметка удалена');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    }
  };

  return (
    <div style={{ padding: '16px' }}>
      <Text strong style={{ fontSize: 15, display: 'block', marginBottom: 12 }}>
        Заметки
      </Text>

      <div style={{ marginBottom: 16 }}>
        <TextArea
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder="Новая заметка..."
          rows={3}
          maxLength={8000}
        />
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <Radio.Group
            value={newVisibility}
            onChange={(e) => setNewVisibility(e.target.value)}
            size="small"
          >
            <Radio.Button value="private">Личная</Radio.Button>
            <Radio.Button value="shared">Общая</Radio.Button>
          </Radio.Group>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            loading={creating}
            onClick={handleCreate}
          >
            Добавить
          </Button>
        </div>
      </div>

      {isLoading ? (
        <Spin />
      ) : notes.length === 0 ? (
        <Empty description="Нет заметок" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={notes}
          renderItem={(note) => (
            <List.Item
              actions={
                note.can_edit
                  ? [
                      <Button
                        key="edit"
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => startEdit(note)}
                      />,
                      <Popconfirm
                        key="del"
                        title="Удалить заметку?"
                        okText="Да"
                        cancelText="Отмена"
                        onConfirm={() => handleDelete(note.id)}
                      >
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>,
                    ]
                  : undefined
              }
            >
              {editingId === note.id ? (
                <div style={{ width: '100%' }}>
                  <TextArea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={3}
                    maxLength={8000}
                  />
                  <Space wrap style={{ marginTop: 8 }}>
                    <Radio.Group
                      value={editVisibility}
                      onChange={(e) => setEditVisibility(e.target.value)}
                      size="small"
                    >
                      <Radio.Button value="private">Личная</Radio.Button>
                      <Radio.Button value="shared">Общая</Radio.Button>
                    </Radio.Group>
                    <Button type="primary" size="small" loading={saving} onClick={handleUpdate}>
                      Сохранить
                    </Button>
                    <Button size="small" onClick={() => setEditingId(null)}>
                      Отмена
                    </Button>
                  </Space>
                </div>
              ) : (
                <div style={{ width: '100%' }}>
                  <Space size={8} wrap style={{ marginBottom: 4 }}>
                    <Tag color={note.visibility === 'shared' ? 'blue' : 'default'}>
                      {note.visibility === 'shared' ? 'Общая' : 'Личная'}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {note.author_name} ·{' '}
                      {new Date(note.created_at).toLocaleString('ru-RU')}
                    </Text>
                  </Space>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{note.content}</div>
                </div>
              )}
            </List.Item>
          )}
        />
      )}
    </div>
  );
}
