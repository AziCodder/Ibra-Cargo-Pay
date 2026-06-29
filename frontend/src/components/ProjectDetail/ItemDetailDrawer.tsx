import { useState } from 'react';
import {
  Button,
  Descriptions,
  Divider,
  Drawer,
  Input,
  List,
  Popconfirm,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import { addRequirement, deleteItem, deleteRequirement, updateItem } from '../../api/projectItems';
import { useAuth } from '../../contexts/AuthContext';
import ItemFormModal from './ItemFormModal';
import type { ProjectItem, Requirement } from '../../types';

const { Text } = Typography;

interface Props {
  open: boolean;
  item: ProjectItem;
  projectId: number;
  onClose: () => void;
  onChanged: () => void;
}

export default function ItemDetailDrawer({ open, item, projectId, onClose, onChanged }: Props) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [newReqText, setNewReqText] = useState('');
  const [addingReq, setAddingReq] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const canEdit = item.can_edit ?? (isAdmin || item.shared_access);

  const handleAddReq = async () => {
    if (!newReqText.trim()) return;
    setAddingReq(true);
    try {
      await addRequirement(projectId, item.id, newReqText.trim());
      setNewReqText('');
      onChanged();
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      message.success('Требование добавлено');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    } finally {
      setAddingReq(false);
    }
  };

  const handleDeleteReq = async (req: Requirement) => {
    try {
      await deleteRequirement(projectId, item.id, req.id);
      onChanged();
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      message.success('Требование удалено');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleDeleteItem = async () => {
    try {
      await deleteItem(projectId, item.id);
      message.success('Позиция удалена');
      onClose();
      onChanged();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка удаления');
    }
  };

  const handleToggleAccess = async (shared: boolean) => {
    try {
      await updateItem(projectId, item.id, { shared_access: shared });
      onChanged();
      queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
      message.success(shared ? 'Доступ открыт' : 'Доступ закрыт');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e.response?.data?.detail ?? 'Ошибка');
    }
  };

  const currency = item.currency;
  const price = parseFloat(item.price);
  const quantity = parseFloat(item.quantity);
  const commission = parseFloat(item.commission);
  const costPrice = item.cost_price ? parseFloat(item.cost_price) : null;
  const effectivePrice = price * (1 + commission / 100);
  const totalAmount = price * quantity;
  const invoicedAmount = parseFloat(item.invoiced_amount ?? '0');
  const paidAmount = parseFloat(item.paid_amount ?? '0');
  const invoicedRemaining = invoicedAmount - paidAmount;      // выставлено, но не оплачено
  const notInvoiced = totalAmount - invoicedAmount;           // ещё не выставлено
  const totalRemaining = totalAmount - paidAmount;            // общий остаток
  const commissionAmount = price * quantity * (commission / 100);

  return (
    <>
      <Drawer
        open={open}
        onClose={onClose}
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{item.name}</span>
            {canEdit && (
              <Space size="small">
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => setShowEdit(true)}
                >
                  Редактировать
                </Button>
                <Popconfirm
                  title="Удалить позицию?"
                  okText="Да"
                  cancelText="Отмена"
                  onConfirm={handleDeleteItem}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )}
          </div>
        }
        width="min(480px, 92vw)"
      >
        {item.details && (
          <Descriptions column={1} size="small" bordered style={{ marginBottom: 12 }}>
            <Descriptions.Item label="Описание">{item.details}</Descriptions.Item>
          </Descriptions>
        )}

        {/* ── Основные характеристики + финансы ── */}
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Количество">
            {parseFloat(item.quantity).toLocaleString('ru-RU')}
          </Descriptions.Item>
          <Descriptions.Item label="Поставщик">
            {item.supplier?.full_name ?? <Text type="secondary">—</Text>}
          </Descriptions.Item>
          <Descriptions.Item label="Валюта">
            <Tag>{currency}</Tag>
          </Descriptions.Item>
          {isAdmin && (
            <Descriptions.Item label="Доступ клиенту">
              <Switch
                size="small"
                checked={item.shared_access}
                onChange={handleToggleAccess}
              />
            </Descriptions.Item>
          )}
          <Descriptions.Item label="Цена">
            {price.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
          </Descriptions.Item>
          {isAdmin && (
            <Descriptions.Item label="Себестоимость">
              {costPrice !== null ? (
                costPrice.toLocaleString('ru-RU', { minimumFractionDigits: 2 })
              ) : (
                <Text type="secondary">Не указана (итог по цене)</Text>
              )}
            </Descriptions.Item>
          )}
          <Descriptions.Item label="Итого к оплате">
            <Text strong>
              {totalAmount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Выставлено счетов">
            <Text>
              {invoicedAmount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
            {invoicedAmount === 0 && (
              <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>(заявок нет)</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Фактически оплачено">
            <Text type={paidAmount > 0 ? undefined : 'secondary'}>
              {paidAmount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Остаток по выставленным">
            <Text type={invoicedRemaining > 0 ? 'warning' : 'success'}>
              {invoicedRemaining.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Остаток к выставлению">
            <Text type={notInvoiced > 0 ? 'secondary' : 'success'}>
              {notInvoiced.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Общий остаток">
            <Text strong type={totalRemaining > 0 ? 'danger' : 'success'}>
              {totalRemaining.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
        </Descriptions>

        {/* ── Комиссия / прибыль ── */}
        <Divider orientation="left" orientationMargin={0} style={{ margin: '16px 0 8px', fontSize: 12 }}>
          Комиссия
        </Divider>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Комиссия %">{commission}%</Descriptions.Item>
          <Descriptions.Item label="Эффективная цена">
            <Text>
              {effectivePrice.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Комиссия (сумма)">
            <Text>
              {commissionAmount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}{currency}
            </Text>
          </Descriptions.Item>
        </Descriptions>

        {/* Требования */}
        <div style={{ marginTop: 24 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: 8,
              fontWeight: 600,
            }}
          >
            <span>Требования ({item.requirements.length}/5)</span>
          </div>

          <List
            size="small"
            dataSource={item.requirements}
            locale={{ emptyText: 'Нет требований' }}
            renderItem={(req) => (
              <List.Item
                actions={
                  canEdit
                    ? [
                        <Popconfirm
                          key="del"
                          title="Удалить требование?"
                          okText="Да"
                          cancelText="Отмена"
                          onConfirm={() => handleDeleteReq(req)}
                        >
                          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>,
                      ]
                    : undefined
                }
              >
                {req.text}
              </List.Item>
            )}
          />

          {canEdit && item.requirements.length < 5 && (
            <Space.Compact style={{ width: '100%', marginTop: 8 }}>
              <Input
                placeholder="Новое требование..."
                value={newReqText}
                onChange={(e) => setNewReqText(e.target.value)}
                onPressEnter={handleAddReq}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                loading={addingReq}
                onClick={handleAddReq}
              />
            </Space.Compact>
          )}
        </div>
      </Drawer>

      {showEdit && (
        <ItemFormModal
          open={showEdit}
          projectId={projectId}
          item={item}
          onClose={() => setShowEdit(false)}
          onSuccess={() => {
            setShowEdit(false);
            onChanged();
          }}
        />
      )}
    </>
  );
}
