import { useState } from 'react';
import {
  Button,
  Descriptions,
  Drawer,
  Input,
  List,
  Popconfirm,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import { addRequirement, deleteItem, deleteRequirement } from '../../api/projectItems';
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

  const currency = item.currency;
  const price = parseFloat(item.price);
  const quantity = parseFloat(item.quantity);
  const commission = parseFloat(item.commission);
  const costPrice = item.cost_price ? parseFloat(item.cost_price) : null;
  const effectivePrice = price * (1 + commission / 100);
  const totalAmount = price * quantity;                          // цена × кол-во (без комиссии)
  const invoicedAmount = parseFloat(item.invoiced_amount ?? '0');
  const remainingAmount = totalAmount - invoicedAmount;
  const commissionAmount = price * quantity * (commission / 100);
  const profitAmount = costPrice !== null ? (price - costPrice) * quantity : null;

  return (
    <>
      <Drawer
        open={open}
        onClose={onClose}
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{item.name}</span>
            {isAdmin && (
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
        <Descriptions column={1} size="small" bordered>
          {item.details && (
            <Descriptions.Item label="Описание">{item.details}</Descriptions.Item>
          )}
          <Descriptions.Item label="Количество">
            {parseFloat(item.quantity).toLocaleString('ru-RU')}
          </Descriptions.Item>
          <Descriptions.Item label="Поставщик">
            {item.supplier?.full_name ?? <Text type="secondary">—</Text>}
          </Descriptions.Item>
          <Descriptions.Item label="Валюта">
            <Tag>{currency}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Цена">
            {price.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
          </Descriptions.Item>
          <Descriptions.Item label="Комиссия">{commission}%</Descriptions.Item>
          {isAdmin && (
            <Descriptions.Item label="Эффективная цена">
              <Text>
                {effectivePrice.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
              </Text>
            </Descriptions.Item>
          )}
          {isAdmin && costPrice !== null && (
            <Descriptions.Item label="Себестоимость">
              {costPrice.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
            </Descriptions.Item>
          )}

          {/* ── Финансовые расчёты ── */}
          <Descriptions.Item label="Итого к оплате">
            <Text strong>
              {totalAmount.toLocaleString('ru-RU', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              {currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Выставлено счетов">
            <Text>
              {invoicedAmount.toLocaleString('ru-RU', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              {currency}
            </Text>
            {invoicedAmount === 0 && (
              <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                (заявок нет)
              </Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Остаток к оплате">
            <Text strong type={remainingAmount > 0 ? 'danger' : 'success'}>
              {remainingAmount.toLocaleString('ru-RU', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              {currency}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Комиссия">
            <Text>
              {commissionAmount.toLocaleString('ru-RU', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              {currency}
            </Text>
          </Descriptions.Item>
          {isAdmin && profitAmount !== null && (
            <Descriptions.Item label="Прибыль">
              <Text type="success" strong>
                {profitAmount.toLocaleString('ru-RU', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {currency}
              </Text>
            </Descriptions.Item>
          )}
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
                  isAdmin
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

          {isAdmin && item.requirements.length < 5 && (
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
