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
import { Pagination } from "../components/Pagination";
import { useAuth } from "../context/useAuth";
import { usePageOffset } from "../hooks/usePageOffset";
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
  const { user } = useAuth();
  const isWarden = user?.role === "WARDEN";
  const [offset, setOffset] = usePageOffset(statusFilter);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["requests", "my", statusFilter, offset],
    queryFn: () => workflowApi.getRequests({ status: statusFilter, mine: true, offset }),
  });
  const requests = data?.results ?? [];
  const totalCount = data?.total_count ?? 0;

  // FR-06: requests waiting for this person's answer
  const { data: awaitingAnswer } = useQuery({
    queryKey: ["requests", "my", "action-required"],
    queryFn: () => workflowApi.getRequests({ status: "NEEDS_CLARIFICATION", mine: true }),
  });
  const actionRequired = awaitingAnswer?.results ?? [];

  return (
    <div className="page-container">
      {/* Header Bar */}
      <div className="page-header-row">
        <div>
          <h1 className="page-title">{isWarden ? "My Reports" : "My Maintenance Requests"}</h1>
          <p className="page-subtitle">
            {isWarden
              ? "Faults you reported for residents who could not reach their accounts."
              : "Track and report faults for Moroka Hall of Residence."}
          </p>
        </div>
        <Link to="/requests/new" className="btn btn-primary">
          <span className="btn-icon">+</span> Report a Fault
        </Link>
      </div>

      {/* Action Required (FR-06) */}
      {actionRequired.length > 0 && (
        <section className="card action-required-card" aria-labelledby="action-required-title">
          <h2 id="action-required-title" className="action-required-title">
            Action required ({awaitingAnswer?.total_count})
          </h2>
          <p className="action-required-hint">The Supervisor needs more information before these can continue.</p>
          <ul className="action-required-list">
            {actionRequired.map((req) => (
              <li key={req.id}>
                <Link to={`/requests/${req.id}`} className="action-required-link">
                  <span className="tracking-badge">{req.tracking_number}</span>
                  <span>{req.description_snippet}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

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
            Showing <strong>{requests.length}</strong> {totalCount === 1 ? "request" : "requests"}
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

      <Pagination total={totalCount} limit={data?.limit ?? 50} offset={offset} onChange={setOffset} />
    </div>
  );
}
