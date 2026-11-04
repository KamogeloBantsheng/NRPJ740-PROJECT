/**
 * SCR-06: Supervisor Triage & Dispatch Queue (FR-08, BR-05, SCR-06).
 * Enables supervisors to evaluate incoming maintenance requests, filter by category/location,
 * and navigate to detailed triage action controls.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import { Pagination } from "../components/Pagination";
import { usePageOffset } from "../hooks/usePageOffset";
import type { RequestStatus } from "../types/workflow";

type StatusTab = "TRIAGE_ALL" | "SUBMITTED" | "NEEDS_CLARIFICATION" | "ALL";

export function SupervisorTriagePage() {
  const [activeTab, setActiveTab] = useState<StatusTab>("TRIAGE_ALL");
  const [selectedCategory, setSelectedCategory] = useState<number>(0);
  const [selectedLocation, setSelectedLocation] = useState<number>(0);
  const [selectedResidence, setSelectedResidence] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Determine query status parameter based on active tab
  const statusParam = useMemo(() => {
    switch (activeTab) {
      case "TRIAGE_ALL":
        return "SUBMITTED,NEEDS_CLARIFICATION";
      case "SUBMITTED":
        return "SUBMITTED";
      case "NEEDS_CLARIFICATION":
        return "NEEDS_CLARIFICATION";
      case "ALL":
      default:
        return "SUBMITTED,NEEDS_CLARIFICATION,REJECTED,APPROVED,ASSIGNED,IN_PROGRESS,WORK_COMPLETED,REOPENED,VERIFIED_CLOSED";
    }
  }, [activeTab]);

  const filters = {
    status: statusParam,
    category_id: selectedCategory,
    location_id: selectedLocation,
    residence_id: selectedResidence,
    search: searchQuery.trim(),
  };
  const [offset, setOffset] = usePageOffset(JSON.stringify(filters));

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["supervisor-requests", filters, offset],
    queryFn: () => workflowApi.getTriageQueue({ ...filters, offset }),
  });
  const requests = data?.results ?? [];
  const totalCount = data?.total_count ?? 0;

  const { data: residences = [] } = useQuery({
    queryKey: ["residences"],
    queryFn: () => workflowApi.getResidences(),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => workflowApi.getCategories(),
  });

  const { data: locations = [] } = useQuery({
    queryKey: ["locations"],
    queryFn: () => workflowApi.getLocations(),
  });

  // Metric counts across every page
  const submittedCount = data?.status_totals.SUBMITTED ?? 0;
  const needsClarificationCount = data?.status_totals.NEEDS_CLARIFICATION ?? 0;

  return (
    <div className="page-container triage-page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Triage queue</h1>
          <p className="page-subtitle">
            Oldest first. Approve with a priority, ask a question, or reject with a reason.
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="card metric-card">
          <div className="metric-label">New Submissions Awaiting Triage</div>
          <div className="metric-value metric-accent">{submittedCount}</div>
          <div className="metric-hint">Require initial priority assessment or clarification</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Awaiting Resident Clarification</div>
          <div className="metric-value metric-warning">{needsClarificationCount}</div>
          <div className="metric-hint">Clarification question sent to resident</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Total in View</div>
          <div className="metric-value">{totalCount}</div>
          <div className="metric-hint">Matching current filters</div>
        </div>
      </div>

      {/* Triage Filter Toolbar */}
      <div className="card filter-toolbar-card">
        {/* Status Tabs */}
        <div className="status-tab-group" role="tablist" aria-label="Triage status filters">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "TRIAGE_ALL"}
            className={`status-tab ${activeTab === "TRIAGE_ALL" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("TRIAGE_ALL")}
          >
            Active Triage Queue ({submittedCount + needsClarificationCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "SUBMITTED"}
            className={`status-tab ${activeTab === "SUBMITTED" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("SUBMITTED")}
          >
            New Submissions ({submittedCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "NEEDS_CLARIFICATION"}
            className={`status-tab ${activeTab === "NEEDS_CLARIFICATION" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("NEEDS_CLARIFICATION")}
          >
            Clarification Pending ({needsClarificationCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ALL"}
            className={`status-tab ${activeTab === "ALL" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ALL")}
          >
            All Residence Requests
          </button>
        </div>

        {/* Dropdowns & Search */}
        <div className="filters-row">
          <div className="filter-item search-filter">
            <label htmlFor="search-input" className="filter-label">
              Search
            </label>
            <input
              id="search-input"
              type="text"
              placeholder="Search by tracking #, resident, location, or keyword..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="filter-item">
            <label htmlFor="residence-select" className="filter-label">
              Residence
            </label>
            <select
              id="residence-select"
              value={selectedResidence}
              onChange={(e) => setSelectedResidence(Number(e.target.value))}
              className="select-input"
            >
              <option value="0">All Residences</option>
              {residences.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-item">
            <label htmlFor="category-select" className="filter-label">
              Fault Category
            </label>
            <select
              id="category-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(Number(e.target.value))}
              className="select-input"
            >
              <option value="0">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-item">
            <label htmlFor="location-select" className="filter-label">
              Location in Moroka Hall
            </label>
            <select
              id="location-select"
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(Number(e.target.value))}
              className="select-input"
            >
              <option value="0">All Locations</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.display_name}
                </option>
              ))}
            </select>
          </div>

          {(selectedCategory > 0 || selectedLocation > 0 || selectedResidence > 0 || searchQuery.trim()) && (
            <div className="filter-item reset-filter-item">
              <label className="filter-label">&nbsp;</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSelectedCategory(0);
                  setSelectedLocation(0);
                  setSelectedResidence(0);
                  setSearchQuery("");
                }}
              >
                Clear Filters
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Request Table / List Content */}
      {isLoading ? (
        <div className="loading-container" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="loading-text">Loading maintenance queue...</p>
        </div>
      ) : isError ? (
        <div className="card empty-card" role="alert">
          <div className="empty-icon"><AppIcon name="alert" size={40} color="#d97706" /></div>
          <h2 className="empty-title">Failed to load maintenance queue</h2>
          <p className="empty-text">There was an error communicating with the server.</p>
          <button type="button" onClick={() => refetch()} className="btn btn-primary">
            Retry Loading
          </button>
        </div>
      ) : requests.length === 0 ? (
        <div className="card empty-card">
          <div className="empty-icon"><AppIcon name="check-circle" size={40} color="#10b981" /></div>
          <h2 className="empty-title">Queue is clear!</h2>
          <p className="empty-text">
            {activeTab === "TRIAGE_ALL"
              ? "There are currently no maintenance requests awaiting triage in Moroka Hall."
              : "No maintenance requests match the selected filters."}
          </p>
        </div>
      ) : (
        <div className="card table-card">
          <div className="table-responsive">
            <table className="triage-table">
              <thead>
                <tr>
                  <th>Tracking #</th>
                  <th>Status</th>
                  <th>Resident</th>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Fault Description</th>
                  <th>Reported</th>
                  <th className="action-col">Action</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((req) => (
                  <tr key={req.id} className="triage-table-row">
                    <td className="tracking-cell">
                      <Link to={`/requests/${req.id}`} className="tracking-link">
                        {req.tracking_number}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge status={req.status as RequestStatus} />
                    </td>
                    <td className="resident-cell">
                      <span className="resident-name">{req.resident_name || "Resident"}</span>
                    </td>
                    <td>
                      <span className="location-tag">
                        {req.location_label} ({req.location_kind === "ROOM" ? `Fl ${req.location_floor}` : "Common"})
                      </span>
                    </td>
                    <td>
                      <span className="category-pill">{req.category_name}</span>
                    </td>
                    <td className="description-cell">
                      <p className="description-text" title={req.description_snippet}>
                        {req.description_snippet}
                      </p>
                    </td>
                    <td className="date-cell">
                      {new Date(req.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="action-cell">
                      <Link to={`/requests/${req.id}`} className="btn btn-secondary btn-sm triage-btn">
                        Review & Triage &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={totalCount} limit={data?.limit ?? 50} offset={offset} onChange={setOffset} />
        </div>
      )}
    </div>
  );
}
