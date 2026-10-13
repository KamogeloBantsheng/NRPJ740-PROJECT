/**
 * Operational Reporting and Dashboard Domain Types (SCR-10, FR-16, BR-04, NFR-06).
 */

import type { Role } from "./auth";

export interface DashboardScope {
  role: Role;
  is_scoped_to_residence: boolean;
  residence_id: number | null;
  residence_name: string;
  available_residences: Array<{ id: number; name: string }>;
}

export interface DashboardSummary {
  total_requests: number;
  open_requests: number;
  closed_requests: number;
  active_work_orders: number;
  average_open_age_hours: number;
  mean_time_to_closure_hours: number;
  mean_time_to_closure_days: number;
}

export interface CategoryCountItem {
  id: number;
  name: string;
  count: number;
}

export interface AgingDistribution {
  under_24h: number;
  "1_to_3_days": number;
  "3_to_7_days": number;
  over_7_days: number;
}

export interface DashboardMetrics {
  scope: DashboardScope;
  summary: DashboardSummary;
  status_counts: Record<string, number>;
  priority_counts: Record<string, number>;
  category_counts: CategoryCountItem[];
  aging_distribution: AgingDistribution;
}
