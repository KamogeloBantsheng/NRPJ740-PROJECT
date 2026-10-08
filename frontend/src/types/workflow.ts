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

export interface FaultCategoryItem {
  id: number;
  name: string;
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
  created_at: string;
  closed_at: string | null;
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
  };
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
  timeline: TimelineEvent[];
}

export interface SubmitRequestPayload {
  location_id: number;
  category_id: number;
  description: string;
  client_token?: string;
}
