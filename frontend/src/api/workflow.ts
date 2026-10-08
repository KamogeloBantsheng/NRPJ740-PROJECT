/**
 * Workflow API client functions for locations, categories, and maintenance requests.
 */

import { apiClient } from "./client";
import type {
  FaultCategoryItem,
  LocationItem,
  MaintenanceRequestDetail,
  MaintenanceRequestSummary,
  SubmitRequestPayload,
  TimelineEvent,
} from "../types/workflow";

export const workflowApi = {
  getLocations: async (): Promise<LocationItem[]> => {
    return apiClient<LocationItem[]>("/api/locations/");
  },

  getCategories: async (): Promise<FaultCategoryItem[]> => {
    return apiClient<FaultCategoryItem[]>("/api/categories/");
  },

  getRequests: async (statusFilter?: string): Promise<MaintenanceRequestSummary[]> => {
    const url = statusFilter ? `/api/requests/?status=${encodeURIComponent(statusFilter)}` : "/api/requests/";
    return apiClient<MaintenanceRequestSummary[]>(url);
  },

  getRequestDetail: async (id: number | string): Promise<MaintenanceRequestDetail> => {
    return apiClient<MaintenanceRequestDetail>(`/api/requests/${id}/`);
  },

  getRequestTimeline: async (id: number | string): Promise<TimelineEvent[]> => {
    return apiClient<TimelineEvent[]>(`/api/requests/${id}/timeline/`);
  },

  submitRequest: async (payload: SubmitRequestPayload): Promise<MaintenanceRequestDetail> => {
    return apiClient<MaintenanceRequestDetail>("/api/requests/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
