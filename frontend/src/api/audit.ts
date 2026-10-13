/**
 * Audit Trail API endpoints (SCR-13, FR-18, NFR-05).
 */

import { apiClient } from "./client";
import type { AuditLogFilters, AuditLogResponse } from "../types/audit";

export const auditApi = {
  getAuditLogs: async (filters?: AuditLogFilters): Promise<AuditLogResponse> => {
    const params = new URLSearchParams();
    if (filters?.actor_id) {
      params.append("actor_id", String(filters.actor_id));
    }
    if (filters?.action) {
      params.append("action", filters.action);
    }
    if (filters?.request_id) {
      params.append("request_id", String(filters.request_id));
    }
    if (filters?.date_from) {
      params.append("date_from", filters.date_from);
    }
    if (filters?.date_to) {
      params.append("date_to", filters.date_to);
    }
    if (filters?.search?.trim()) {
      params.append("search", filters.search.trim());
    }
    if (filters?.limit) {
      params.append("limit", String(filters.limit));
    }
    if (filters?.offset) {
      params.append("offset", String(filters.offset));
    }

    const qs = params.toString();
    return apiClient<AuditLogResponse>(qs ? `/api/audit-logs/?${qs}` : "/api/audit-logs/");
  },
};
