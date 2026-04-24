import { Alert, Button, Empty, Popconfirm, Space, Table, Tag, Typography, message } from 'antd';
import { CloudDownloadOutlined, CloudUploadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import {
  getBackupDownloadUrl,
  listBackups,
  runBackupNow,
  type BackupItem,
} from '../../api/backups';

const { Text, Paragraph } = Typography;

function formatSize(bytes: number): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} ГБ`;
}

export default function BackupsTab() {
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['backups'],
    queryFn: () => listBackups(100),
  });

  const runMut = useMutation({
    mutationFn: runBackupNow,
    onSuccess: (res) => {
      message.success(
        `Бэкап создан: ${formatSize(res.size_bytes)}` +
          (res.deleted_old_count > 0 ? `, удалено старых: ${res.deleted_old_count}` : ''),
      );
      queryClient.invalidateQueries({ queryKey: ['backups'] });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Не удалось создать бэкап');
    },
  });

  const handleDownload = async (key: string) => {
    try {
      const url = await getBackupDownloadUrl(key);
      window.open(url, '_blank');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Не удалось получить ссылку');
    }
  };

  const columns: ColumnsType<BackupItem> = [
    {
      title: 'Дата создания',
      dataIndex: 'last_modified',
      key: 'last_modified',
      width: 200,
      render: (v: string | null) =>
        v ? dayjs(v).format('DD.MM.YYYY HH:mm:ss') : <Text type="secondary">—</Text>,
    },
    {
      title: 'Файл',
      dataIndex: 'key',
      key: 'key',
      ellipsis: true,
      render: (v: string) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Размер',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 120,
      render: (v: number) => formatSize(v),
    },
    {
      title: '',
      key: 'actions',
      width: 130,
      render: (_: unknown, r: BackupItem) => (
        <Button
          size="small"
          icon={<CloudDownloadOutlined />}
          onClick={() => handleDownload(r.key)}
        >
          Скачать
        </Button>
      ),
    },
  ];

  if (data && !data.configured) {
    return (
      <Alert
        type="warning"
        showIcon
        message="Бэкапы не настроены"
        description={
          <Paragraph style={{ marginBottom: 0 }}>
            Задайте переменные <Text code>S3_*</Text> и <Text code>BACKUP_S3_BUCKET</Text> в{' '}
            <Text code>.env</Text>, затем перезапустите backend.
          </Paragraph>
        }
      />
    );
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Popconfirm
          title="Создать бэкап сейчас?"
          description="Запустится pg_dump и загрузка в S3. Может занять несколько минут."
          okText="Создать"
          cancelText="Отмена"
          onConfirm={() => runMut.mutate()}
        >
          <Button type="primary" icon={<CloudUploadOutlined />} loading={runMut.isPending}>
            Создать бэкап сейчас
          </Button>
        </Popconfirm>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isFetching}>
          Обновить
        </Button>
        {data?.bucket && (
          <Tag color="blue">Бакет: {data.bucket}</Tag>
        )}
        {data?.retention_days !== undefined && (
          <Tag>Хранение: {data.retention_days} дн.</Tag>
        )}
        <Tag color="geekblue">Расписание: ежедневно в 03:00 МСК</Tag>
      </Space>

      <Table
        rowKey="key"
        size="small"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        locale={{ emptyText: <Empty description="Бэкапов пока нет" /> }}
        pagination={{ pageSize: 25, showSizeChanger: false }}
      />
    </div>
  );
}
