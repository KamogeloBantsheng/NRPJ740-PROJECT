/**
 * SCR-03: Resident Requests List Page (FR-06, SCR-03).
 * Displays role-scoped maintenance requests submitted by the logged-in resident.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import type { RequestStatus } from "../types/workflow";

const STATUS_FILTERS: { label: string; value: string }[] = [
  { label: "All Requests", value: "" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Needs Clarification", value: "NEEDS_CLARIFICATION" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Work Completed", value: "WORK_COMPLETED" },
  { label: "Verified Closed", value: "VERIFIED_CLOSED" },
  { label: "Rejected", value: "REJECTED" },
];

export function ResidentRequestsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const navigate = useNavigate();

  const {
    data: requests = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["requests", "my", statusFilter],
    queryFn: () => workflowApi.getRequests(statusFilter || undefined),
  });

  return (
    <div className="page-container">
      {/* Header Bar */}
      <div className="page-header-row">
        <div>
          <h1 className="page-title">My Maintenance Requests</h1>
          <p className="page-subtitle">
            Track and report faults for Moroka Hall of Residence (FR-06, SCR-03).
          </p>
        </div>
        <Link to="/requests/new" className="btn btn-primary">
          <span className="btn-icon">+</span> Report a Fault
        </Link>
      </div>

      {/* Filters and Search Bar */}
      <div className="card filter-card">
        <div className="filter-row">
          <div className="filter-group">
            <label htmlFor="status-filter" className="filter-label">
              Filter by Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="select-input"
            >
              {STATUS_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-stats">
            Showing <strong>{requests.length}</strong> {requests.length === 1 ? "request" : "requests"}
          </div>
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <div className="card loading-card">
          <div className="spinner" />
          <p>Loading your maintenance requests...</p>
        </div>
      ) : isError ? (
        <div className="card error-card">
          <h3>Unable to load requests</h3>
          <p>{error instanceof Error ? error.message : "A connection error occurred."}</p>
          <button onClick={() => refetch()} className="btn btn-secondary mt-2">
            Try Again
          </button>
        </div>
      ) : requests.length === 0 ? (
        <div className="card empty-card">
          <div className="empty-icon"><AppIcon name="clipboard" size={44} color="var(--color-primary)" /></div>
          <h2 className="empty-title">No maintenance requests found</h2>
          <p className="empty-description">
            {statusFilter
              ? "No requests match the selected status filter."
              : "You have not submitted any maintenance fault reports yet."}
          </p>
          {!statusFilter && (
            <Link to="/requests/new" className="btn btn-primary mt-3">
              Submit Your First Request
            </Link>
          )}
        </div>
      ) : (
        <div className="request-grid">
          {requests.map((req) => (
            <div
              key={req.id}
              className="card request-card"
              onClick={() => navigate(`/requests/${req.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  navigate(`/requests/${req.id}`);
                }
              }}
            >
              <div className="request-card-header">
                <span className="tracking-badge">{req.tracking_number}</span>
                <StatusBadge status={req.status as RequestStatus} size="sm" />
              </div>

              <div className="request-card-meta">
                <span className="category-pill">{req.category_name}</span>
                <span className="location-pill">
                  Block {req.location_block}, Fl {req.location_floor} - {req.location_label}
                </span>
              </div>

              <p className="request-card-snippet">{req.description_snippet}</p>

              <div className="request-card-footer">
                <span className="date-text">
                  Submitted {new Date(req.created_at).toLocaleDateString("en-ZA", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <span className="view-link">View Details &rarr;</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
