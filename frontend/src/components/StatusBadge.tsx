/**
 * Reusable StatusBadge component displaying semantic styling for RequestStatus.
 */

import React from "react";
import type { RequestStatus } from "../types/workflow";

interface StatusBadgeProps {
  status: RequestStatus;
  size?: "sm" | "md" | "lg";
}

const STATUS_CONFIG: Record<
  RequestStatus,
  { label: string; className: string }
> = {
  SUBMITTED: {
    label: "Submitted",
    className: "badge-status-submitted",
  },
  NEEDS_CLARIFICATION: {
    label: "Needs Clarification",
    className: "badge-status-clarification",
  },
  APPROVED: {
    label: "Approved",
    className: "badge-status-approved",
  },
  ASSIGNED: {
    label: "Assigned",
    className: "badge-status-assigned",
  },
  IN_PROGRESS: {
    label: "In Progress",
    className: "badge-status-in-progress",
  },
  WORK_COMPLETED: {
    label: "Work Completed",
    className: "badge-status-completed",
  },
  REOPENED: {
    label: "Reopened",
    className: "badge-status-reopened",
  },
  VERIFIED_CLOSED: {
    label: "Verified Closed",
    className: "badge-status-closed",
  },
  REJECTED: {
    label: "Rejected",
    className: "badge-status-rejected",
  },
};

export function StatusBadge({ status, size = "md" }: StatusBadgeProps): React.JSX.Element {
  const config = STATUS_CONFIG[status] || {
    label: status,
    className: "badge-status-default",
  };

  return (
    <span className={`status-badge ${config.className} badge-${size}`}>
      {config.label}
    </span>
  );
}
