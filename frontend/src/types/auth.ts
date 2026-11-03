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
  is_mfa_enabled?: boolean;
  created_at: string;
  last_login: string | null;
}

export interface LoginResponseMfaRequired {
  requires_mfa: true;
  mfa_token: string;
  email: string;
}

export type LoginResult = (User & { requires_mfa?: false }) | LoginResponseMfaRequired;

export interface MfaVerifyPayload {
  mfa_token: string;
  code: string;
}

export interface MfaSetupResponse {
  secret: string;
  provisioning_uri: string;
  setup_token: string;
}

export interface MfaEnablePayload {
  setup_token: string;
  code: string;
}

export interface MfaEnableResponse {
  message: string;
  backup_codes: string[];
}

export interface MfaDisablePayload {
  password: string;
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
