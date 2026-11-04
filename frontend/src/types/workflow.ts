/**
 * Workflow and maintenance request types (FR-05, FR-06, FR-18).
 */

export type RequestStatus =
  | "SUBMITTED"
  | "NEEDS_CLARIFICATION"
  | "REJECTED"
  | "APPROVED"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "WORK_COMPLETED"
  | "REOPENED"
  | "VERIFIED_CLOSED";

export type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface LocationItem {
  id: number;
  residence_id: number;
  block: string;
  floor: number;
  label: string;
  kind: "ROOM" | "COMMON_AREA";
  display_name: string;
}

export interface ResidenceItem {
  id: number;
  name: string;
}

export interface FaultCategoryItem {
  id: number;
  name: string;
}

export interface TechnicianItem {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  active_tasks_count: number;
}

export interface WorkOrderSummary {
  id: number;
  request_id: number;
  technician_id: number;
  technician_name: string;
  technician_email?: string;
  assigned_by_id: number;
  assigned_by_name: string;
  assigned_at: string;
  ended_at: string | null;
  end_reason: "REASSIGNED" | "COMPLETED" | null;
  is_active: boolean;
}

export interface MaintenanceRequestSummary {
  id: number;
  tracking_number: string;
  status: RequestStatus;
  priority: Priority | null;
  category_name: string;
  location_label: string;
  location_block: string;
  location_floor: number;
  location_kind: "ROOM" | "COMMON_AREA";
  description_snippet: string;
  resident_name?: string | null;
  assigned_technician_name?: string | null;
  created_at: string;
  closed_at: string | null;
}

export interface PagedResult<T> {
  total_count: number;
  limit: number;
  offset: number;
  results: T[];
}

export interface PagedRequests extends PagedResult<MaintenanceRequestSummary> {
  status_totals: Partial<Record<RequestStatus, number>>;
}

export interface TransitionPayload {
  action: string;
  expected_status: RequestStatus;
  note?: string;
  priority?: Priority | null;
  technician_id?: number | null;
}

export interface TimelineEvent {
  id: number;
  occurred_at: string;
  action: string;
  actor_role: string;
  actor_name: string;
  from_status: RequestStatus | null;
  to_status: RequestStatus | null;
  note: string | null;
  details: Record<string, unknown>;
}

export interface MaintenanceRequestDetail {
  is_owner: boolean;
  id: number;
  tracking_number: string;
  status: RequestStatus;
  priority: Priority | null;
  description: string;
  client_token: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  resident: {
    id: number;
    full_name: string;
    email: string;
    student_number: string | null;
  } | null;
  location: {
    id: number;
    residence_name: string;
    block: string;
    floor: number;
    label: string;
    kind: string;
  };
  category: {
    id: number;
    name: string;
  };
  active_work_order?: WorkOrderSummary | null;
  work_orders?: WorkOrderSummary[];
  timeline: TimelineEvent[];
}

export interface SubmitRequestPayload {
  location_id: number;
  category_id: number;
  description: string;
  client_token?: string;
}
