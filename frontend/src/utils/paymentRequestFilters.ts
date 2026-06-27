import type { PaymentRequestListParams } from '../api/paymentRequests';

export type PaymentRequestSortBy = 'created_at' | 'total_amount' | 'item_name';
export type PaymentRequestSortOrder = 'asc' | 'desc';
export type PaymentRequestStatusFilter = 'all' | 'paid' | 'unpaid';

export type PaymentRequestFiltersState = {
  sortBy: PaymentRequestSortBy;
  sortOrder: PaymentRequestSortOrder;
  statusFilter: PaymentRequestStatusFilter;
  dateFrom: string | null;
  dateTo: string | null;
  // Позиции номенклатуры, скрытые из заявок на оплату (тумблер выключен).
  // Пусто = показаны все. Новые позиции по умолчанию видимы.
  hiddenItemIds: number[];
};

const DEFAULT_FILTERS: PaymentRequestFiltersState = {
  sortBy: 'created_at',
  sortOrder: 'desc',
  statusFilter: 'all',
  dateFrom: null,
  dateTo: null,
  hiddenItemIds: [],
};

export function paymentRequestFiltersKey(projectId: number): string {
  return `ibra_pr_filters_${projectId}`;
}

export function readPaymentRequestFilters(projectId: number): PaymentRequestFiltersState {
  try {
    const raw = localStorage.getItem(paymentRequestFiltersKey(projectId));
    if (!raw) return { ...DEFAULT_FILTERS };
    const parsed = JSON.parse(raw) as Partial<PaymentRequestFiltersState>;
    const sortBy =
      parsed.sortBy === 'total_amount' || parsed.sortBy === 'item_name'
        ? parsed.sortBy
        : 'created_at';
    const sortOrder = parsed.sortOrder === 'asc' ? 'asc' : 'desc';
    const statusFilter =
      parsed.statusFilter === 'paid' || parsed.statusFilter === 'unpaid'
        ? parsed.statusFilter
        : 'all';
    const hiddenItemIds = Array.isArray(parsed.hiddenItemIds)
      ? parsed.hiddenItemIds.filter((id): id is number => typeof id === 'number')
      : [];
    return {
      sortBy,
      sortOrder,
      statusFilter,
      dateFrom: typeof parsed.dateFrom === 'string' ? parsed.dateFrom : null,
      dateTo: typeof parsed.dateTo === 'string' ? parsed.dateTo : null,
      hiddenItemIds,
    };
  } catch {
    return { ...DEFAULT_FILTERS };
  }
}

export function writePaymentRequestFilters(
  projectId: number,
  filters: PaymentRequestFiltersState,
): void {
  localStorage.setItem(paymentRequestFiltersKey(projectId), JSON.stringify(filters));
}

export function toListParams(
  filters: PaymentRequestFiltersState,
  allItemIds: number[] = [],
): PaymentRequestListParams {
  // item_ids на бэкенде — список ВКЛЮЧАЕМЫХ позиций. Переводим набор скрытых
  // в набор видимых. Пока позиции не загружены или ничего не скрыто — показываем всё.
  let item_ids: number[] | undefined;
  if (filters.hiddenItemIds.length === 0 || allItemIds.length === 0) {
    item_ids = undefined;
  } else {
    const hidden = new Set(filters.hiddenItemIds);
    const visible = allItemIds.filter((id) => !hidden.has(id));
    // Скрыто всё — отправляем несуществующий id, чтобы вернулся пустой список.
    item_ids = visible.length > 0 ? visible : [0];
  }
  return {
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
    status_filter: filters.statusFilter,
    date_from: filters.dateFrom ?? undefined,
    date_to: filters.dateTo ?? undefined,
    item_ids,
  };
}
