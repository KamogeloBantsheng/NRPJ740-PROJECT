/**
 * System Audit Trail Domain Types (SCR-13, FR-18, NFR-05).
 */

export interface AuditUserMini {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

export interface AuditEventItem {
  id: number;
  occurred_at: string;
  action: string;
  action_label: string;
  actor: AuditUserMini | null;
  target_user: AuditUserMini | null;
  request_id: number | null;
  tracking_number: string | null;
  work_order_id: number | null;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  details: Record<string, unknown>;
}

export interface AvailableActionOption {
  value: string;
  label: string;
}

export interface AuditLogResponse {
  total_count: number;
  limit: number;
  offset: number;
  events: AuditEventItem[];
  available_actions: AvailableActionOption[];
}

export interface AuditLogFilters {
  actor_id?: number;
  action?: string;
  request_id?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}
