/**
 * Authentication API endpoints (Section 6.3, FR-01, FR-02).
 */

import { apiClient } from "./client";
import type {
  ChangePasswordPayload,
  LoginPayload,
  LoginResult,
  MessageResponse,
  MfaDisablePayload,
  MfaEnablePayload,
  MfaEnableResponse,
  MfaSetupResponse,
  MfaVerifyPayload,
  User,
} from "../types/auth";

export const authApi = {
  login: async (payload: LoginPayload): Promise<LoginResult> => {
    return apiClient<LoginResult>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  verifyMfa: async (payload: MfaVerifyPayload): Promise<User> => {
    return apiClient<User>("/api/auth/mfa/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  setupMfa: async (): Promise<MfaSetupResponse> => {
    return apiClient<MfaSetupResponse>("/api/auth/mfa/setup", {
      method: "POST",
    });
  },

  enableMfa: async (payload: MfaEnablePayload): Promise<MfaEnableResponse> => {
    return apiClient<MfaEnableResponse>("/api/auth/mfa/enable", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  disableMfa: async (payload: MfaDisablePayload): Promise<MessageResponse> => {
    return apiClient<MessageResponse>("/api/auth/mfa/disable", {
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
