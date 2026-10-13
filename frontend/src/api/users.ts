/**
 * User Administration and CSV Import API endpoints (SCR-11, SCR-12, FR-03, FR-04, BR-07, NFR-02, NFR-03).
 */

import { apiClient } from "./client";
import type {
  AdminUserItem,
  CreateUserPayload,
  CreateUserResponse,
  CsvImportResponse,
  ResetPasswordResponse,
  UpdateUserPayload,
} from "../types/users";

export interface UserFilters {
  search?: string;
  role?: string;
  is_active?: boolean;
}

export const usersApi = {
  getUsers: async (filters?: UserFilters): Promise<AdminUserItem[]> => {
    const params = new URLSearchParams();
    if (filters?.search?.trim()) {
      params.append("search", filters.search.trim());
    }
    if (filters?.role) {
      params.append("role", filters.role);
    }
    if (filters?.is_active !== undefined) {
      params.append("is_active", String(filters.is_active));
    }
    const qs = params.toString();
    return apiClient<AdminUserItem[]>(qs ? `/api/users/?${qs}` : "/api/users/");
  },

  createUser: async (payload: CreateUserPayload): Promise<CreateUserResponse> => {
    return apiClient<CreateUserResponse>("/api/users/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateUser: async (id: number, payload: UpdateUserPayload): Promise<AdminUserItem> => {
    return apiClient<AdminUserItem>(`/api/users/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  resetPassword: async (id: number): Promise<ResetPasswordResponse> => {
    return apiClient<ResetPasswordResponse>(`/api/users/${id}/reset-password/`, {
      method: "POST",
    });
  },

  importResidentsCsv: async (file: File): Promise<CsvImportResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    return apiClient<CsvImportResponse>("/api/users/import-csv/", {
      method: "POST",
      body: formData,
    });
  },
};
