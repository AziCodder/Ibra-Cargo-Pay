import { useCallback, useEffect, useState } from 'react';
import {
  readPaymentRequestFilters,
  writePaymentRequestFilters,
  type PaymentRequestFiltersState,
} from '../utils/paymentRequestFilters';

/**
 * Состояние фильтров заявок на оплату, общее для панелей номенклатуры и заявок.
 * Хранится в localStorage отдельно для каждого проекта (персонально, у каждого свой выбор).
 */
export function usePaymentRequestFilters(projectId: number) {
  const [filters, setFilters] = useState<PaymentRequestFiltersState>(() =>
    readPaymentRequestFilters(projectId),
  );

  // При переключении проекта подхватываем его сохранённые фильтры.
  useEffect(() => {
    setFilters(readPaymentRequestFilters(projectId));
  }, [projectId]);

  useEffect(() => {
    writePaymentRequestFilters(projectId, filters);
  }, [projectId, filters]);

  const updateFilters = useCallback(
    (patch: Partial<PaymentRequestFiltersState>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
    },
    [],
  );

  return { filters, updateFilters };
}
