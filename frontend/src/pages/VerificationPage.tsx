/**
 * SCR-08: Supervisor Verification & Closure Screen (FR-12, BR-02, BR-06, BR-10, SCR-08).
 * Enables maintenance supervisors to inspect completed repairs, review technician notes,
 * record closure confirmation notes (T10 VERIFY_CLOSE), or reopen requests with mandatory
 * feedback (T11 REOPEN).
 */

import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { AppError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import type { MaintenanceRequestSummary, RequestStatus, TransitionPayload } from "../types/workflow";

type VerificationTab = "AWAITING_VERIFICATION" | "REOPENED" | "CLOSED" | "ALL";

export function VerificationPage() {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<VerificationTab>("AWAITING_VERIFICATION");
  const [selectedCategory, setSelectedCategory] = useState<number>(0);
  const [selectedLocation, setSelectedLocation] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modal action state
  const [activeModal, setActiveModal] = useState<{
    request: MaintenanceRequestSummary;
    mode: "VERIFY_CLOSE" | "REOPEN";
  } | null>(null);

  const [actionNote, setActionNote] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Status param based on active tab
  const statusParam = useMemo(() => {
    switch (activeTab) {
      case "AWAITING_VERIFICATION":
        return "WORK_COMPLETED";
      case "REOPENED":
        return "REOPENED";
      case "CLOSED":
        return "VERIFIED_CLOSED";
      case "ALL":
      default:
        return "WORK_COMPLETED,REOPENED,VERIFIED_CLOSED";
    }
  }, [activeTab]);

  const {
    data: requests = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["verification-requests", statusParam],
    queryFn: () => workflowApi.getRequests(statusParam),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => workflowApi.getCategories(),
  });

  const { data: locations = [] } = useQuery({
    queryKey: ["locations"],
    queryFn: () => workflowApi.getLocations(),
  });

  const transitionMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TransitionPayload }) =>
      workflowApi.transitionRequest(id, payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["verification-requests"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["supervisor-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dispatch-requests"] });
      const mode = activeModal?.mode;
      closeModal();
      if (mode === "VERIFY_CLOSE") {
        setActionSuccess(
          `Request ${updated.tracking_number} has been verified and permanently CLOSED (T10). Active work order completed.`
        );
      } else {
        setActionSuccess(
          `Request ${updated.tracking_number} has been REOPENED with feedback (T11). Technician assignment retained.`
        );
      }
    },
    onError: (err) => {
      if (err instanceof AppError && err.statusCode === 409) {
        setActionError(
          `State Conflict Detected: The request status changed to "${err.current_status || "a different state"}". The queue has been refreshed.`
        );
        queryClient.invalidateQueries({ queryKey: ["verification-requests"] });
      } else if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while processing the verification action.");
      }
    },
  });

  const openVerifyModal = (req: MaintenanceRequestSummary) => {
    setActionError(null);
    setActionSuccess(null);
    setActionNote("");
    setActiveModal({ request: req, mode: "VERIFY_CLOSE" });
  };

  const openReopenModal = (req: MaintenanceRequestSummary) => {
    setActionError(null);
    setActionSuccess(null);
    setActionNote("");
    setActiveModal({ request: req, mode: "REOPEN" });
  };

  const closeModal = () => {
    setActiveModal(null);
    setActionNote("");
    setActionError(null);
  };

  const handleSubmitAction = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeModal) return;

    setActionError(null);
    const trimmed = actionNote.trim();

    if (activeModal.mode === "REOPEN") {
      if (trimmed.length < 10) {
        setActionError("Reopening feedback reason must be at least 10 characters long (BR-02).");
        return;
      }
      transitionMutation.mutate({
        id: activeModal.request.id,
        payload: {
          action: "REOPEN",
          expected_status: activeModal.request.status,
          note: trimmed,
        },
      });
    } else {
      transitionMutation.mutate({
        id: activeModal.request.id,
        payload: {
          action: "VERIFY_CLOSE",
          expected_status: activeModal.request.status,
          note: trimmed || undefined,
        },
      });
    }
  };

  // Filter requests
  const filteredRequests = useMemo(() => {
    return requests.filter((req) => {
      if (selectedCategory > 0) {
        const cat = categories.find((c) => c.id === selectedCategory);
        if (cat && req.category_name !== cat.name) return false;
      }
      if (selectedLocation > 0) {
        const loc = locations.find((l) => l.id === selectedLocation);
        if (loc && req.location_label !== loc.label) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const tracking = req.tracking_number.toLowerCase();
        const desc = req.description_snippet.toLowerCase();
        const loc = req.location_label.toLowerCase();
        const tech = (req.assigned_technician_name || "").toLowerCase();
        return tracking.includes(q) || desc.includes(q) || loc.includes(q) || tech.includes(q);
      }
      return true;
    });
  }, [requests, selectedCategory, selectedLocation, searchQuery, categories, locations]);

  // Counts
  const awaitingCount = useMemo(
    () => requests.filter((r) => r.status === "WORK_COMPLETED").length,
    [requests]
  );
  const reopenedCount = useMemo(
    () => requests.filter((r) => r.status === "REOPENED").length,
    [requests]
  );
  const closedCount = useMemo(
    () => requests.filter((r) => r.status === "VERIFIED_CLOSED").length,
    [requests]
  );

  return (
    <div className="page-container verification-page-container">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Supervisor Verification & Quality Review</h1>
          <p className="page-subtitle">
            Moroka Hall Residence &bull; Inspect completed repairs, verify technician quality, record closure notes (T10), or reopen tasks (T11) (FR-12, SCR-08)
          </p>
        </div>
      </div>

      {/* Global Alerts */}
      {actionSuccess && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="check" size={16} /></span>
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && !activeModal && (
        <div className="alert alert-error mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
          <span>{actionError}</span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="card metric-card">
          <div className="metric-label">Awaiting Verification</div>
          <div className="metric-value metric-warning">{awaitingCount}</div>
          <div className="metric-hint">Completed repairs pending supervisor inspection (T10/T11)</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Reopened Tasks</div>
          <div className="metric-value metric-info">{reopenedCount}</div>
          <div className="metric-hint">Returned to technician for additional corrective work</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Verified & Closed</div>
          <div className="metric-value metric-success">{closedCount}</div>
          <div className="metric-hint">Permanently closed requests with completed work orders</div>
        </div>
      </div>

      {/* Filter and Tab Toolbar */}
      <div className="card filter-toolbar-card">
        {/* Tabs */}
        <div className="status-tab-group" role="tablist" aria-label="Verification queue tabs">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "AWAITING_VERIFICATION"}
            className={`status-tab ${activeTab === "AWAITING_VERIFICATION" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("AWAITING_VERIFICATION")}
          >
            Awaiting Verification ({awaitingCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "REOPENED"}
            className={`status-tab ${activeTab === "REOPENED" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("REOPENED")}
          >
            Reopened ({reopenedCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "CLOSED"}
            className={`status-tab ${activeTab === "CLOSED" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("CLOSED")}
          >
            Verified & Closed ({closedCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ALL"}
            className={`status-tab ${activeTab === "ALL" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ALL")}
          >
            All Review History
          </button>
        </div>

        {/* Filters */}
        <div className="filters-row">
          <div className="filter-item search-filter">
            <label htmlFor="verify-search" className="filter-label">
              Search
            </label>
            <input
              id="verify-search"
              type="text"
              placeholder="Search by tracking #, location, technician, description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="filter-item">
            <label htmlFor="verify-category" className="filter-label">
              Fault Category
            </label>
            <select
              id="verify-category"
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
            <label htmlFor="verify-location" className="filter-label">
              Location in Moroka Hall
            </label>
            <select
              id="verify-location"
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

          {(selectedCategory > 0 || selectedLocation > 0 || searchQuery.trim()) && (
            <div className="filter-item reset-filter-item">
              <label className="filter-label">&nbsp;</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSelectedCategory(0);
                  setSelectedLocation(0);
                  setSearchQuery("");
                }}
              >
                Clear Filters
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Task List / Content */}
      {isLoading ? (
        <div className="loading-container" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="loading-text">Loading verification requests...</p>
        </div>
      ) : isError ? (
        <div className="card empty-card" role="alert">
          <div className="empty-icon"><AppIcon name="alert" size={40} color="#d97706" /></div>
          <h2 className="empty-title">Failed to load verification queue</h2>
          <p className="empty-text">There was an error communicating with the server.</p>
          <button type="button" onClick={() => refetch()} className="btn btn-primary">
            Retry Loading
          </button>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="card empty-card">
          <div className="empty-icon"><AppIcon name="check-circle" size={40} color="#10b981" /></div>
          <h2 className="empty-title">Queue is clear!</h2>
          <p className="empty-text">
            {activeTab === "AWAITING_VERIFICATION"
              ? "There are currently no maintenance requests awaiting supervisor verification in Moroka Hall."
              : "No maintenance requests match the selected filters."}
          </p>
        </div>
      ) : (
        <div className="card table-card">
          <div className="table-responsive">
            <table className="triage-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Tracking #</th>
                  <th>Status</th>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Technician</th>
                  <th>Fault Description</th>
                  <th>Reported Date</th>
                  <th className="action-col">Verification Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRequests.map((req) => (
                  <tr key={req.id} className="triage-table-row">
                    <td>
                      {req.priority ? (
                        <span className={`priority-badge priority-${req.priority.toLowerCase()}`}>
                          {req.priority}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="tracking-cell">
                      <Link to={`/requests/${req.id}`} className="tracking-link">
                        {req.tracking_number}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge status={req.status as RequestStatus} />
                    </td>
                    <td>
                      <span className="location-tag">
                        {req.location_label} ({req.location_kind === "ROOM" ? `Fl ${req.location_floor}` : "Common"})
                      </span>
                    </td>
                    <td>
                      <span className="category-pill">{req.category_name}</span>
                    </td>
                    <td>
                      {req.assigned_technician_name ? (
                        <span className="assigned-tech-name">
                          {req.assigned_technician_name}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
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
                      {req.status === "WORK_COMPLETED" ? (
                        <div className="action-buttons-cell">
                          <button
                            type="button"
                            className="btn btn-success btn-sm"
                            onClick={() => openVerifyModal(req)}
                            title="Verify work and permanently close request (T10)"
                          >
                            Verify & Close
                          </button>
                          <button
                            type="button"
                            className="btn btn-outline-warning btn-sm ml-1"
                            onClick={() => openReopenModal(req)}
                            title="Reopen request with feedback for technician (T11)"
                          >
                            Reopen
                          </button>
                        </div>
                      ) : (
                        <Link to={`/requests/${req.id}`} className="btn btn-secondary btn-sm">
                          View Details &rarr;
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Action Modal (T10 Verify & Close or T11 Reopen) */}
      {activeModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">
                {activeModal.mode === "VERIFY_CLOSE"
                  ? `Verify & Close: ${activeModal.request.tracking_number} (T10)`
                  : `Reopen Request: ${activeModal.request.tracking_number} (T11)`}
              </h2>
              <button
                type="button"
                className="modal-close-btn"
                onClick={closeModal}
                aria-label="Close dialog"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmitAction} className="modal-body">
              {actionError && (
                <div className="alert alert-error mb-3" role="alert">
                  <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
                  <span>{actionError}</span>
                </div>
              )}

              {/* Context Summary */}
              <div className="modal-context-box">
                <div>
                  <strong>Location:</strong> {activeModal.request.location_label} &bull; Block {activeModal.request.location_block}
                </div>
                <div>
                  <strong>Category:</strong> {activeModal.request.category_name}
                </div>
                <div>
                  <strong>Assigned Technician:</strong>{" "}
                  <span className="highlight-tech">
                    {activeModal.request.assigned_technician_name || "Unassigned"}
                  </span>
                </div>
                <div>
                  <strong>Current Status:</strong>{" "}
                  <span className="highlight-status">{activeModal.request.status}</span>
                </div>
              </div>

              {activeModal.mode === "VERIFY_CLOSE" ? (
                <>
                  <p className="modal-info-text">
                    Closing this request is permanent and terminal (BR-06). The active work order will end as <strong>COMPLETED</strong>, and the completion timestamp will be recorded.
                  </p>
                  <div className="form-group">
                    <label htmlFor="verify-note" className="form-label">
                      Supervisor Closure Confirmation Note <span className="text-muted">(Optional)</span>
                    </label>
                    <textarea
                      id="verify-note"
                      rows={3}
                      value={actionNote}
                      onChange={(e) => setActionNote(e.target.value)}
                      placeholder="Optional notes confirming on-site inspection (e.g. 'Inspected room, valve repaired and tested dry under pressure')..."
                      className="textarea-input"
                    />
                  </div>
                </>
              ) : (
                <>
                  <p className="modal-info-text text-warning">
                    Reopening will return the request status to <strong>REOPENED</strong> so the assigned technician can perform additional corrective work. Mandatory feedback of at least 10 characters is required (BR-02).
                  </p>
                  <div className="form-group">
                    <div className="label-row">
                      <label htmlFor="reopen-note" className="form-label">
                        Reopening Feedback & Instructions <span className="required">*</span>
                      </label>
                      <span
                        className={`char-counter ${
                          actionNote.trim().length >= 10 ? "counter-valid" : "counter-low"
                        }`}
                      >
                        {actionNote.trim().length} chars (min 10)
                      </span>
                    </div>
                    <textarea
                      id="reopen-note"
                      rows={4}
                      value={actionNote}
                      onChange={(e) => setActionNote(e.target.value)}
                      placeholder="Explain what was unsatisfactory or what further work is required (e.g. 'Valve still leaks when hot tap turned on. Please replace entire valve seat.')..."
                      className="textarea-input"
                      required
                    />
                    <span className="field-hint">
                      This feedback will be recorded in the audit log and displayed to the technician.
                    </span>
                  </div>
                </>
              )}

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={closeModal}
                  disabled={transitionMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${activeModal.mode === "VERIFY_CLOSE" ? "btn-success" : "btn-warning"}`}
                  disabled={
                    transitionMutation.isPending ||
                    (activeModal.mode === "REOPEN" && actionNote.trim().length < 10)
                  }
                >
                  {transitionMutation.isPending
                    ? "Processing..."
                    : activeModal.mode === "VERIFY_CLOSE"
                    ? "Confirm & Close Request (T10)"
                    : "Reopen Request (T11)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
