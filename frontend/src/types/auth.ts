/**
 * Authentication and User domain types (Table 5.5, 5.7, FR-01, FR-02).
 */

export type Role = "RESIDENT" | "TECHNICIAN" | "SUPERVISOR" | "WARDEN" | "ADMIN";

export interface User {
  id: number;
  email: string;
  full_name: string;
  student_number: string | null;
  role: Role;
  residence: number | null;
  residence_name: string | null;
  assigned_location?: number | null;
  assigned_location_name?: string | null;
  must_change_password: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  fields?: Record<string, string[]>;
  current_status?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface ChangePasswordPayload {
  current_password?: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}
