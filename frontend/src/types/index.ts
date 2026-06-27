// ── Общие типы ────────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'client';
export type ProjectStatus = 'active' | 'closed';
export type Currency = 'CNY' | 'USD' | 'RUB';
export type PaymentRequestPriority = 'urgent' | 'normal' | 'deferred';
export type AuditAction = 'created' | 'updated' | 'deleted';
export type PaymentStatus = 'pending' | 'confirmed' | 'rejected';

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  login: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

// ── Пользователи ──────────────────────────────────────────────────────────────

export interface User {
  id: number;
  login: string;
  full_name: string;
  role: UserRole;
  description?: string | null;
  telegram_chat_id?: number | null;
  created_at: string;
}

export interface UserCreate {
  full_name: string;
  login: string;
  password: string;
  role: UserRole;
  description?: string | null;
}

export interface UserUpdate {
  full_name?: string;
  login?: string;
  password?: string;
  role?: UserRole;
  description?: string | null;
  telegram_chat_id?: number | null;
}

export interface UserListOut {
  items: User[];
  total: number;
}

export interface UserBrief {
  id: number;
  full_name: string;
  login: string;
}

// ── Поставщики ────────────────────────────────────────────────────────────────

export interface Supplier {
  id: number;
  full_name: string;
  phone: string;
  wechat_id: string;
  document_1?: string | null;
  document_2?: string | null;
  document_3?: string | null;
  description?: string | null;
  created_at: string;
}

export interface SupplierCreate {
  full_name: string;
  phone: string;
  wechat_id: string;
  document_1?: string | null;
  document_2?: string | null;
  document_3?: string | null;
  description?: string | null;
}

export interface SupplierUpdate {
  full_name?: string;
  phone?: string;
  wechat_id?: string;
  document_1?: string | null;
  document_2?: string | null;
  document_3?: string | null;
  description?: string | null;
}

export interface SupplierListOut {
  items: Supplier[];
  total: number;
}

export interface SupplierBrief {
  id: number;
  full_name: string;
}

// ── Проекты ───────────────────────────────────────────────────────────────────

export interface Project {
  id: number;
  project_number: number;
  name: string;
  description?: string | null;
  client_id?: number | null;
  client?: UserBrief | null;
  status: ProjectStatus;
  created_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
  status?: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
  status?: ProjectStatus;
}

export interface ProjectListOut {
  items: Project[];
  total: number;
}

export interface CurrencySummary {
  currency: Currency;
  total: string;
  invoiced: string;
  paid: string;
  remaining: string;
  commission?: string | null;
}

export interface ProjectSummary {
  currencies: CurrencySummary[];
}

export type NoteVisibility = 'private' | 'shared';

export interface ProjectNote {
  id: number;
  project_id: number;
  content: string;
  visibility: NoteVisibility;
  created_by: number;
  author_name: string;
  created_at: string;
  updated_at: string;
  can_edit: boolean;
}

export interface ProjectNoteCreate {
  content: string;
  visibility?: NoteVisibility;
}

export interface ProjectNoteUpdate {
  content?: string;
  visibility?: NoteVisibility;
}

// ── Позиции номенклатуры ──────────────────────────────────────────────────────

export interface Requirement {
  id: number;
  text: string;
  created_at: string;
}

export interface ProjectItem {
  id: number;
  project_id: number;
  name: string;
  details?: string | null;
  quantity: string;
  supplier_id?: number | null;
  supplier?: SupplierBrief | null;
  price: string;
  cost_price?: string;
  currency: Currency;
  commission: string;
  created_by: number;
  shared_access: boolean;
  sort_order: number;
  can_edit?: boolean;
  invoiced_amount: string;
  paid_amount: string;
  requirements: Requirement[];
  created_at: string;
  updated_at?: string;
}

export interface ProjectItemCreate {
  name: string;
  details?: string | null;
  quantity: number;
  supplier_id?: number | null;
  price: number;
  cost_price?: number;
  currency: Currency;
  commission?: number;
}

export interface ProjectItemUpdate {
  name?: string;
  details?: string | null;
  quantity?: number;
  supplier_id?: number | null;
  price?: number;
  cost_price?: number;
  currency?: Currency;
  commission?: number;
  shared_access?: boolean;
}

// ── Заявки на оплату ──────────────────────────────────────────────────────────

export interface PaymentRequestItemIn {
  project_item_id: number;
  amount: number;
}

export interface PaymentRequestCreate {
  items: PaymentRequestItemIn[];
  total_amount: number;
  currency: Currency;
  requisites?: string | null;
  payment_details?: string | null;
  due_date?: string | null;
  priority?: PaymentRequestPriority;
}

export interface PaymentRequestUpdate {
  items?: PaymentRequestItemIn[];
  requisites?: string | null;
  payment_details?: string | null;
  due_date?: string | null;
  priority?: PaymentRequestPriority;
}

export interface PaymentRequestItemOut {
  id: number;
  project_item_id: number;
  project_item_name: string;
  amount: string;
}

export interface Attachment {
  id: number;
  file_path: string;
  file_name: string;
  created_at: string;
}

export interface PaymentShort {
  id: number;
  amount: string;
  currency: Currency;
  note?: string | null;
  payment_date?: string | null;
  file_path?: string | null;
  file_name?: string | null;
  status: PaymentStatus;
  confirmed_by?: number | null;
  confirmed_at?: string | null;
  rejection_reason?: string | null;
  created_by: number;
  created_at: string;
}

export interface PaymentRequest {
  id: number;
  project_id: number;
  total_amount: string;
  currency: Currency;
  requisites?: string | null;
  payment_details?: string | null;
  due_date?: string | null;
  priority: PaymentRequestPriority;
  remaining_amount: string;
  can_edit?: boolean;
  items: PaymentRequestItemOut[];
  attachments: Attachment[];
  payments: PaymentShort[];
  created_by: number;
  created_at: string;
}

export interface PaymentRequestList {
  id: number;
  project_id: number;
  total_amount: string;
  currency: Currency;
  due_date?: string | null;
  priority: PaymentRequestPriority;
  remaining_amount: string;
  paid_amount?: string;
  can_edit?: boolean;
  items_names: string;
  created_by: number;
  created_at: string;
}

// ── Платежи ───────────────────────────────────────────────────────────────────

export interface Payment {
  id: number;
  payment_request_id: number;
  amount: string;
  currency: Currency;
  note?: string | null;
  payment_date?: string | null;
  file_path?: string | null;
  file_name?: string | null;
  status: PaymentStatus;
  confirmed_by?: number | null;
  confirmed_at?: string | null;
  rejection_reason?: string | null;
  created_by: number;
  created_at: string;
}

export interface PaymentCreate {
  amount: number;
  currency: Currency;
  note?: string | null;
}

export interface PaymentReject {
  reason: string;
}

// ── Журнал изменений ──────────────────────────────────────────────────────────

export interface AuditLog {
  id: number;
  user_id?: number | null;
  user_login?: string | null;
  user_full_name?: string | null;
  action: AuditAction;
  entity_type: string;
  entity_id: number;
  changes?: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListOut {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

// ── Комментарии к заявкам ─────────────────────────────────────────────────────

export interface PaymentRequestComment {
  id: number;
  payment_request_id: number;
  author_id: number;
  author_login: string;
  author_full_name: string;
  text: string;
  created_at: string;
}

export interface CommentCreate {
  text: string;
}

// ── Дашборд ──────────────────────────────────────────────────────────────────

export interface CurrencyBalance {
  currency: Currency;
  total: string;
  paid: string;
  remaining: string;
}

export interface RecentPayment {
  id: number;
  payment_request_id: number;
  project_id: number;
  project_name: string;
  project_number: number;
  amount: string;
  currency: Currency;
  note?: string | null;
  created_by: number;
  created_by_full_name: string;
  created_at: string;
}

export interface DashboardSummary {
  projects_active: number;
  projects_closed: number;
  completed_requests: number;
  remaining_by_currency: CurrencyBalance[];
  recent_payments: RecentPayment[];
}
