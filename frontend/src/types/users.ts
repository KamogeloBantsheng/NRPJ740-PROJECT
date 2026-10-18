/**
 * User Administration and Batch Import domain types (SCR-11, SCR-12, FR-03, FR-04).
 */

import type { Role } from "./auth";
export type { Role };

export interface AdminUserItem {
  id: number;
  email: string;
  full_name: string;
  student_number: string | null;
  role: Role;
  residence: number | null;
  residence_name: string | null;
  assigned_location?: number | null;
  assigned_location_name?: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login: string | null;
  active_work_orders_count: number;
}

export interface CreateUserPayload {
  email: string;
  full_name: string;
  role: Role;
  student_number?: string;
  residence?: number | null;
  assigned_location_id?: number | null;
}

export interface CreateUserResponse extends AdminUserItem {
  temporary_password: string;
}

export interface UpdateUserPayload {
  full_name?: string;
  role?: Role;
  student_number?: string;
  residence?: number | null;
  assigned_location_id?: number | null;
  is_active?: boolean;
}

export interface ResetPasswordResponse {
  id: number;
  email: string;
  temporary_password: string;
  message: string;
}

export interface CsvImportCredential {
  id: number;
  email: string;
  full_name: string;
  student_number: string;
  temporary_password: string;
}

export interface CsvImportResponse {
  message: string;
  created_count: number;
  credentials: CsvImportCredential[];
}

export interface CsvBadRowError {
  row: number;
  errors: string[];
}
