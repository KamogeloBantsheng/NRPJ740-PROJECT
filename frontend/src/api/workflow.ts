/**
 * Workflow API client functions for locations, categories, and maintenance requests.
 */

import { apiClient } from "./client";
import type {
  FaultCategoryItem,
  LocationItem,
  MaintenanceRequestDetail,
  PagedRequests,
  ResidenceItem,
  SubmitRequestPayload,
  TechnicianItem,
  TimelineEvent,
  TransitionPayload,
} from "../types/workflow";

export interface RequestFilters {
  status?: string;
  category_id?: number;
  location_id?: number;
  residence_id?: number;
  search?: string;
  mine?: boolean;
  offset?: number;
}

function requestListUrl(path: string, filters: RequestFilters = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.append(key, String(value));
  }
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export const workflowApi = {
  getLocations: async (): Promise<LocationItem[]> => {
    return apiClient<LocationItem[]>("/api/locations/");
  },

  getCategories: async (): Promise<FaultCategoryItem[]> => {
    return apiClient<FaultCategoryItem[]>("/api/categories/");
  },

  getResidences: async (): Promise<ResidenceItem[]> => {
    return apiClient<ResidenceItem[]>("/api/residences/");
  },

  getRequests: async (filters?: RequestFilters): Promise<PagedRequests> => {
    return apiClient<PagedRequests>(requestListUrl("/api/requests/", filters));
  },

  getTriageQueue: async (filters?: RequestFilters): Promise<PagedRequests> => {
    return apiClient<PagedRequests>(requestListUrl("/api/triage-queue/", filters));
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

  getTechnicians: async (): Promise<TechnicianItem[]> => {
    return apiClient<TechnicianItem[]>("/api/technicians/");
  },

  getWorkQueue: async (filters?: RequestFilters): Promise<PagedRequests> => {
    return apiClient<PagedRequests>(requestListUrl("/api/work-queue/", filters));
  },
};
