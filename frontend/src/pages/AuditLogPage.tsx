/**
 * SCR-13: System Audit Trail & Security Inspection Screen (FR-18, NFR-05, SCR-13, TC-41).
 * Enables System Administrators to query and inspect append-only audit records
 * with filters for actor, action type, request ID, date range, and keyword search.
 */

import { useState, useMemo } from "react";
import { AppIcon } from "../components/AppIcon";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { auditApi } from "../api/audit";
import type { AuditEventItem, AuditLogFilters } from "../types/audit";

export function AuditLogPage() {
  // Filter state
  const [selectedAction, setSelectedAction] = useState<string>("");
  const [requestIdFilter, setRequestIdFilter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const LIMIT = 50;

  // Selected event for inspection modal
  const [inspectEvent, setInspectEvent] = useState<AuditEventItem | null>(null);

  // Compile active query filters
  const activeFilters: AuditLogFilters = useMemo(() => {
    const f: AuditLogFilters = {
      limit: LIMIT,
      offset,
    };
    if (selectedAction) f.action = selectedAction;
    if (requestIdFilter.trim()) {
      const clean = requestIdFilter.trim().replace(/^MR-/i, "");
      if (/^\d+$/.test(clean)) {
        f.request_id = Number(clean);
      } else {
        f.search = requestIdFilter.trim();
      }
    }
    if (dateFrom) f.date_from = dateFrom;
    if (dateTo) f.date_to = dateTo;
    if (searchTerm.trim()) f.search = searchTerm.trim();
    return f;
  }, [selectedAction, requestIdFilter, dateFrom, dateTo, searchTerm, offset]);

  const {
    data: auditResult,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["audit-logs", activeFilters],
    queryFn: () => auditApi.getAuditLogs(activeFilters),
  });

  const events = auditResult?.events ?? [];
  const totalCount = auditResult?.total_count ?? 0;
  const availableActions = auditResult?.available_actions ?? [];

  const handleResetFilters = () => {
    setSelectedAction("");
    setRequestIdFilter("");
    setDateFrom("");
    setDateTo("");
    setSearchTerm("");
    setOffset(0);
  };

  const getActionBadgeClass = (action: string): string => {
    if (action.startsWith("LOGIN_") || action.includes("PASSWORD_")) {
      return "badge-security";
    }
    if (action.startsWith("USER_")) {
      return "badge-user-admin";
    }
    if (action.includes("APPROVED") || action.includes("CLOSED") || action.includes("COMPLETED")) {
      return "badge-success-subtle";
    }
    if (action.includes("REJECTED") || action.includes("REOPENED")) {
      return "badge-danger-subtle";
    }
    return "badge-transition";
  };

  return (
    <main className="audit-log-page-container triage-page-container" id="main-content">
      {/* Header */}
      <div className="page-header">
        <div className="header-text-group">
          <div className="header-breadcrumbs">
            <span className="crumb-app">Administration</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-page">System Audit Trail</span>
          </div>
          <h1 className="page-title">System Audit Trail & Security Log</h1>
          <p className="page-subtitle">
            Searchable append-only audit records of lifecycle transitions, security events, and administrative actions (FR-18, NFR-05).
          </p>
        </div>

        <div className="page-header-actions">
          <button
            type="button"
            onClick={() => refetch()}
            className="btn btn-secondary btn-refresh"
            disabled={isFetching}
            title="Refresh audit events"
          >
            {isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Control Card: Filters */}
      <section className="card triage-control-card" aria-label="Audit log filters">
        <div className="control-filters-grid audit-filters-grid">
          {/* Action Filter */}
          <div className="filter-group">
            <label htmlFor="audit-action-filter" className="filter-label">
              Audit Action
            </label>
            <select
              id="audit-action-filter"
              className="filter-select"
              value={selectedAction}
              onChange={(e) => {
                setSelectedAction(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Actions</option>
              {availableActions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Request Tracking # Filter */}
          <div className="filter-group">
            <label htmlFor="audit-request-filter" className="filter-label">
              Request / Tracking #
            </label>
            <input
              id="audit-request-filter"
              type="text"
              placeholder="e.g. MR-000001 or 1"
              className="filter-select"
              value={requestIdFilter}
              onChange={(e) => {
                setRequestIdFilter(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          {/* Date From */}
          <div className="filter-group">
            <label htmlFor="audit-date-from" className="filter-label">
              From Date
            </label>
            <input
              id="audit-date-from"
              type="date"
              className="filter-select"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          {/* Date To */}
          <div className="filter-group">
            <label htmlFor="audit-date-to" className="filter-label">
              To Date
            </label>
            <input
              id="audit-date-to"
              type="date"
              className="filter-select"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          {/* Search Term */}
          <div className="filter-group">
            <label htmlFor="audit-search" className="filter-label">
              Keyword / Actor Search
            </label>
            <input
              id="audit-search"
              type="search"
              placeholder="Search actor email, name, or note..."
              className="filter-select"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          {/* Reset Action */}
          <div className="filter-group filter-actions-group">
            <span className="filter-label">&nbsp;</span>
            <button
              type="button"
              onClick={handleResetFilters}
              className="btn btn-secondary"
              title="Reset all audit filters"
            >
              Reset
            </button>
          </div>
        </div>
      </section>

      {/* Events Table Card */}
      <div className="card triage-table-card">
        <div className="table-header-row">
          <div className="table-title-group">
            <h2 className="table-title">Audit Events</h2>
            <span className="queue-count-badge">
              {totalCount} {totalCount === 1 ? "event" : "events"} recorded
            </span>
          </div>
          <div className="pagination-info text-muted font-sm">
            Showing {events.length > 0 ? offset + 1 : 0} –{" "}
            {Math.min(offset + events.length, totalCount)} of {totalCount}
          </div>
        </div>

        {isLoading ? (
          <div className="loading-state" role="status" aria-live="polite">
            <div className="spinner" aria-hidden="true" />
            <p className="loading-text">Loading audit trail entries...</p>
          </div>
        ) : isError ? (
          <div className="error-state" role="alert">
            <p className="error-title">Failed to load system audit trail.</p>
            <p className="error-subtitle">
              Unable to reach the audit service. Please check your credentials or connection.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="btn btn-secondary"
            >
              Retry
            </button>
          </div>
        ) : events.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><AppIcon name="file" size={36} color="var(--color-primary)" /></div>
            <p className="empty-title">
              {selectedAction || requestIdFilter || dateFrom || dateTo || searchTerm.trim()
                ? "No audit events match your filters"
                : "Audit trail is empty"}
            </p>
            <p className="empty-subtitle">
              {selectedAction || requestIdFilter || dateFrom || dateTo || searchTerm.trim()
                ? "Try adjusting the date range, action type, or keyword search parameters."
                : "System security events, maintenance transitions, and user activities will be recorded here in real time."}
            </p>
          </div>

        ) : (
          <div className="table-responsive">
            <table className="triage-table audit-table" aria-label="System Audit Trail">
              <thead>
                <tr>
                  <th scope="col" style={{ width: "165px" }}>Timestamp</th>
                  <th scope="col">Action</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Target / Request</th>
                  <th scope="col">State Transition</th>
                  <th scope="col">Notes / Summary</th>
                  <th scope="col" className="text-right">Inspect</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    {/* Timestamp */}
                    <td className="font-sm mono-code text-muted">
                      {new Date(ev.occurred_at).toLocaleString([], {
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </td>

                    {/* Action */}
                    <td>
                      <span className={`badge ${getActionBadgeClass(ev.action)}`}>
                        {ev.action_label || ev.action}
                      </span>
                    </td>

                    {/* Actor */}
                    <td>
                      {ev.actor ? (
                        <div className="audit-actor-cell">
                          <span className="actor-name">{ev.actor.full_name}</span>
                          <span className="actor-email mono-code">{ev.actor.email}</span>
                          <span className={`role-badge role-${ev.actor.role.toLowerCase()} font-xs`}>
                            {ev.actor.role}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted font-sm font-italic">System / Anonymous</span>
                      )}
                    </td>

                    {/* Target / Request */}
                    <td>
                      {ev.request_id ? (
                        <Link
                          to={`/requests/${ev.request_id}`}
                          className="mono-code text-primary font-weight-semibold"
                          title="View Maintenance Request"
                        >
                          {ev.tracking_number || `MR-${ev.request_id}`}
                        </Link>
                      ) : ev.target_user ? (
                        <div className="audit-target-user font-sm">
                          <span className="target-name">{ev.target_user.full_name}</span>
                          <span className="target-email mono-code text-muted">
                            {ev.target_user.email}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* State Transition */}
                    <td>
                      {ev.from_status || ev.to_status ? (
                        <div className="status-transition-cell">
                          {ev.from_status ? (
                            <span className="status-from">{ev.from_status}</span>
                          ) : (
                            <span className="text-muted font-xs">initial</span>
                          )}
                          <span className="transition-arrow">&rarr;</span>
                          <span className="status-to font-weight-bold">{ev.to_status}</span>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Notes / Summary */}
                    <td>
                      {ev.note ? (
                        <span className="audit-note-text" title={ev.note}>
                          {ev.note.length > 55 ? `${ev.note.substring(0, 55)}...` : ev.note}
                        </span>
                      ) : ev.details && Object.keys(ev.details).length > 0 ? (
                        <span className="audit-details-preview mono-code font-xs text-muted">
                          {JSON.stringify(ev.details).substring(0, 45)}...
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Inspect Button */}
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => setInspectEvent(ev)}
                        className="btn btn-sm btn-secondary"
                        title="View event payload details"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalCount > LIMIT && (
          <div className="audit-pagination-bar">
            <button
              type="button"
              onClick={() => setOffset((prev) => Math.max(0, prev - LIMIT))}
              disabled={offset === 0}
              className="btn btn-sm btn-secondary"
            >
              Previous Page
            </button>
            <span className="page-indicator font-sm text-muted">
              Page {Math.floor(offset / LIMIT) + 1} of {Math.ceil(totalCount / LIMIT)}
            </span>
            <button
              type="button"
              onClick={() => setOffset((prev) => prev + LIMIT)}
              disabled={offset + LIMIT >= totalCount}
              className="btn btn-sm btn-secondary"
            >
              Next Page
            </button>
          </div>
        )}
      </div>

      {/* Inspect Event Modal */}
      {inspectEvent && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="audit-modal-title">
          <div className="modal-content modal-dialog-md">
            <div className="modal-header">
              <h2 id="audit-modal-title" className="modal-title">
                Audit Event #{inspectEvent.id}
              </h2>
              <button
                type="button"
                onClick={() => setInspectEvent(null)}
                className="modal-close-btn"
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-context-box">
                <div>
                  <strong>Action:</strong>{" "}
                  <span className={`badge ${getActionBadgeClass(inspectEvent.action)} ml-2`}>
                    {inspectEvent.action_label || inspectEvent.action}
                  </span>
                </div>
                <div>
                  <strong>Timestamp:</strong>{" "}
                  <span className="mono-code">
                    {new Date(inspectEvent.occurred_at).toISOString()}
                  </span>
                </div>
                <div>
                  <strong>Actor:</strong>{" "}
                  {inspectEvent.actor
                    ? `${inspectEvent.actor.full_name} (${inspectEvent.actor.email}) [${inspectEvent.actor.role}]`
                    : "System / Anonymous"}
                </div>
                {inspectEvent.target_user && (
                  <div>
                    <strong>Target User:</strong>{" "}
                    {inspectEvent.target_user.full_name} ({inspectEvent.target_user.email}) [
                    {inspectEvent.target_user.role}]
                  </div>
                )}
                {inspectEvent.request_id && (
                  <div>
                    <strong>Request ID:</strong>{" "}
                    <span className="mono-code">
                      {inspectEvent.tracking_number || `MR-${inspectEvent.request_id}`}
                    </span>
                  </div>
                )}
                {inspectEvent.work_order_id && (
                  <div>
                    <strong>Work Order ID:</strong> #{inspectEvent.work_order_id}
                  </div>
                )}
                {(inspectEvent.from_status || inspectEvent.to_status) && (
                  <div>
                    <strong>Lifecycle Transition:</strong> {inspectEvent.from_status || "None"} &rarr;{" "}
                    {inspectEvent.to_status || "None"}
                  </div>
                )}
                {inspectEvent.note && (
                  <div>
                    <strong>Recorded Note:</strong>
                    <p className="audit-modal-note-box mt-1">{inspectEvent.note}</p>
                  </div>
                )}
              </div>

              <div>
                <label className="filter-label" htmlFor="json-payload-view">
                  Structured Details (JSON Payload):
                </label>
                <pre id="json-payload-view" className="audit-json-box">
                  {JSON.stringify(inspectEvent.details, null, 2)}
                </pre>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  onClick={() => setInspectEvent(null)}
                  className="btn btn-primary"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
