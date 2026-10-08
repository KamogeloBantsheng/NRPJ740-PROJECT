/**
 * Authentication API endpoints (Section 6.3, FR-01, FR-02).
 */

import { apiClient } from "./client";
import type {
  ChangePasswordPayload,
  LoginPayload,
  MessageResponse,
  User,
} from "../types/auth";

export const authApi = {
  login: async (payload: LoginPayload): Promise<User> => {
    return apiClient<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  logout: async (): Promise<MessageResponse> => {
    return apiClient<MessageResponse>("/api/auth/logout", {
      method: "POST",
    });
  },

  changePassword: async (payload: ChangePasswordPayload): Promise<MessageResponse> => {
    return apiClient<MessageResponse>("/api/auth/password", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getMe: async (): Promise<User> => {
    return apiClient<User>("/api/me", {
      method: "GET",
    });
  },
};
