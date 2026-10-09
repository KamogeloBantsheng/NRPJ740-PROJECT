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
  TransitionPayload,
} from "../types/workflow";

export interface RequestFilters {
  status?: string;
  category_id?: number;
  location_id?: number;
}

export const workflowApi = {
  getLocations: async (): Promise<LocationItem[]> => {
    return apiClient<LocationItem[]>("/api/locations/");
  },

  getCategories: async (): Promise<FaultCategoryItem[]> => {
    return apiClient<FaultCategoryItem[]>("/api/categories/");
  },

  getRequests: async (filters?: string | RequestFilters): Promise<MaintenanceRequestSummary[]> => {
    const params = new URLSearchParams();
    if (typeof filters === "string") {
      if (filters) params.append("status", filters);
    } else if (filters) {
      if (filters.status) params.append("status", filters.status);
      if (filters.category_id) params.append("category_id", String(filters.category_id));
      if (filters.location_id) params.append("location_id", String(filters.location_id));
    }
    const qs = params.toString();
    return apiClient<MaintenanceRequestSummary[]>(qs ? `/api/requests/?${qs}` : "/api/requests/");
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

  transitionRequest: async (
    id: number | string,
    payload: TransitionPayload
  ): Promise<MaintenanceRequestDetail> => {
    return apiClient<MaintenanceRequestDetail>(`/api/requests/${id}/transition/`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
