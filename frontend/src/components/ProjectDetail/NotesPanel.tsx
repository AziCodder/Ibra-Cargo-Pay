import { useState } from 'react';
import {
  Button,
  Empty,
  Input,
  Popconfirm,
  Radio,
  Space,
  Spin,
  Tag,
  Typography,
  theme,
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
const { useToken } = theme;

interface Props {
  projectId: number;
}

export default function NotesPanel({ projectId }: Props) {
  const queryClient = useQueryClient();
  const { token } = useToken();
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

  const noteCardStyle: React.CSSProperties = {
    background: token.colorFillQuaternary,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: token.borderRadiusLG,
    padding: '10px 12px',
  };

  return (
    <div style={{ padding: '16px' }}>
      <Text strong style={{ fontSize: 15, display: 'block', marginBottom: 12 }}>
        Заметки
      </Text>

      {/* Поле создания заметки */}
      <div style={{ marginBottom: 16 }}>
        <TextArea
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder="Новая заметка..."
          autoSize={{ minRows: 2, maxRows: 8 }}
          maxLength={8000}
        />
        <div
          style={{
            marginTop: 8,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 8,
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
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

      {/* Список заметок */}
      {isLoading ? (
        <Spin />
      ) : notes.length === 0 ? (
        <Empty
          description="Нет заметок"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ margin: '8px 0' }}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {notes.map((note) =>
            editingId === note.id ? (
              <div key={note.id} style={noteCardStyle}>
                <TextArea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 8 }}
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
              <div key={note.id} style={noteCardStyle}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <Space size={6} wrap style={{ minWidth: 0 }}>
                    <Tag
                      color={note.visibility === 'shared' ? 'blue' : 'default'}
                      style={{ marginInlineEnd: 0 }}
                    >
                      {note.visibility === 'shared' ? 'Общая' : 'Личная'}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {note.author_name} ·{' '}
                      {new Date(note.created_at).toLocaleString('ru-RU')}
                    </Text>
                  </Space>
                  {note.can_edit && (
                    <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => startEdit(note)}
                      />
                      <Popconfirm
                        title="Удалить заметку?"
                        okText="Да"
                        cancelText="Отмена"
                        onConfirm={() => handleDelete(note.id)}
                      >
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </div>
                  )}
                </div>
                <div
                  style={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: 13,
                    lineHeight: 1.5,
                  }}
                >
                  {note.content}
                </div>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}
