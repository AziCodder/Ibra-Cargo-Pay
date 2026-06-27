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
  itemIds: number[];
};

const DEFAULT_FILTERS: PaymentRequestFiltersState = {
  sortBy: 'created_at',
  sortOrder: 'desc',
  statusFilter: 'all',
  dateFrom: null,
  dateTo: null,
  itemIds: [],
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
    const itemIds = Array.isArray(parsed.itemIds)
      ? parsed.itemIds.filter((id): id is number => typeof id === 'number')
      : [];
    return {
      sortBy,
      sortOrder,
      statusFilter,
      dateFrom: typeof parsed.dateFrom === 'string' ? parsed.dateFrom : null,
      dateTo: typeof parsed.dateTo === 'string' ? parsed.dateTo : null,
      itemIds,
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

export function toListParams(filters: PaymentRequestFiltersState): PaymentRequestListParams {
  return {
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
    status_filter: filters.statusFilter,
    date_from: filters.dateFrom ?? undefined,
    date_to: filters.dateTo ?? undefined,
    item_ids: filters.itemIds.length > 0 ? filters.itemIds : undefined,
  };
}
