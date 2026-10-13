/**
 * Operational Reporting API endpoints (SCR-10, FR-16, BR-04, NFR-06).
 */

import { apiClient } from "./client";
import type { DashboardMetrics } from "../types/reporting";

export const reportingApi = {
  getDashboardMetrics: async (residenceId?: number | null): Promise<DashboardMetrics> => {
    const params = new URLSearchParams();
    if (residenceId) {
      params.append("residence_id", String(residenceId));
    }
    const qs = params.toString();
    return apiClient<DashboardMetrics>(qs ? `/api/dashboard/?${qs}` : "/api/dashboard/");
  },
};
