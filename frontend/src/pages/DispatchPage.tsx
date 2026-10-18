/**
 * SCR-07: Supervisor Dispatch & Work-Order Assignment Screen (FR-10, FR-11, BR-01, BR-03, SCR-07).
 * Enables supervisors to view approved maintenance requests awaiting assignment (T6),
 * reassign active work orders to different technicians with mandatory justification (T7),
 * and review technician workload counts.
 */

import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { AppError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import type { MaintenanceRequestSummary, RequestStatus, TransitionPayload } from "../types/workflow";

type DispatchTab = "PENDING_ASSIGNMENT" | "ACTIVE_DISPATCHES" | "ALL";

export function DispatchPage() {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<DispatchTab>("PENDING_ASSIGNMENT");
  const [selectedCategory, setSelectedCategory] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Drawer / Modal action state
  const [activeActionModal, setActiveActionModal] = useState<{
    request: MaintenanceRequestSummary;
    mode: "ASSIGN" | "REASSIGN";
  } | null>(null);

  const [selectedTechId, setSelectedTechId] = useState<number | "">("");
  const [actionNote, setActionNote] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Status parameter for request query
  const statusParam = useMemo(() => {
    switch (activeTab) {
      case "PENDING_ASSIGNMENT":
        return "APPROVED";
      case "ACTIVE_DISPATCHES":
        return "ASSIGNED,IN_PROGRESS,REOPENED";
      case "ALL":
      default:
        return "APPROVED,ASSIGNED,IN_PROGRESS,REOPENED";
    }
  }, [activeTab]);

  const {
    data: requests = [],
    isLoading: isRequestsLoading,
    isError: isRequestsError,
    refetch: refetchRequests,
  } = useQuery({
    queryKey: ["dispatch-requests", statusParam],
    queryFn: () => workflowApi.getRequests(statusParam),
  });

  const {
    data: technicians = [],
    isLoading: isTechsLoading,
    refetch: refetchTechnicians,
  } = useQuery({
    queryKey: ["technicians"],
    queryFn: () => workflowApi.getTechnicians(),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => workflowApi.getCategories(),
  });

  const transitionMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TransitionPayload }) =>
      workflowApi.transitionRequest(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dispatch-requests"] });
      queryClient.invalidateQueries({ queryKey: ["technicians"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["supervisor-requests"] });
      const mode = activeActionModal?.mode;
      closeModal();
      setActionSuccess(
        mode === "ASSIGN"
          ? "Work order successfully assigned to technician."
          : "Work order successfully reassigned to new technician."
      );
    },
    onError: (err) => {
      if (err instanceof AppError && err.statusCode === 409) {
        setFormError(
          `State Conflict Detected: The request status changed to "${err.current_status || "a different state"}". The queue has been refreshed.`
        );
        queryClient.invalidateQueries({ queryKey: ["dispatch-requests"] });
        queryClient.invalidateQueries({ queryKey: ["technicians"] });
      } else if (err instanceof AppError) {
        setFormError(err.message);
      } else {
        setFormError("An unexpected error occurred while executing the assignment.");
      }
    },
  });

  const openAssignModal = (req: MaintenanceRequestSummary) => {
    setFormError(null);
    setActionSuccess(null);
    setActionNote("");
    setSelectedTechId(technicians.length > 0 ? technicians[0].id : "");
    setActiveActionModal({ request: req, mode: "ASSIGN" });
  };

  const openReassignModal = (req: MaintenanceRequestSummary) => {
    setFormError(null);
    setActionSuccess(null);
    setActionNote("");
    // Default to first technician who is NOT the currently assigned technician
    const otherTech = technicians.find((t) => t.full_name !== req.assigned_technician_name);
    setSelectedTechId(otherTech ? otherTech.id : "");
    setActiveActionModal({ request: req, mode: "REASSIGN" });
  };

  const closeModal = () => {
    setActiveActionModal(null);
    setSelectedTechId("");
    setActionNote("");
    setFormError(null);
  };

  const handleModalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeActionModal) return;

    setFormError(null);
    if (!selectedTechId) {
      setFormError("Please select a technician.");
      return;
    }

    const targetReq = activeActionModal.request;
    const trimmed = actionNote.trim();

    if (activeActionModal.mode === "ASSIGN") {
      transitionMutation.mutate({
        id: targetReq.id,
        payload: {
          action: "ASSIGN",
          expected_status: targetReq.status,
          technician_id: Number(selectedTechId),
          note: trimmed || undefined,
        },
      });
    } else {
      // Reassign validation
      if (trimmed.length < 10) {
        setFormError("Reassignment reason must be at least 10 characters long (BR-02).");
        return;
      }
      const selectedTech = technicians.find((t) => t.id === Number(selectedTechId));
      if (selectedTech && selectedTech.full_name === targetReq.assigned_technician_name) {
        setFormError("Cannot reassign to the same technician. Please select a different technician (BR-01, BR-03).");
        return;
      }

      transitionMutation.mutate({
        id: targetReq.id,
        payload: {
          action: "REASSIGN",
          expected_status: targetReq.status,
          technician_id: Number(selectedTechId),
          note: trimmed,
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
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const tracking = req.tracking_number.toLowerCase();
        const tech = (req.assigned_technician_name || "").toLowerCase();
        const resident = (req.resident_name || "").toLowerCase();
        const desc = req.description_snippet.toLowerCase();
        const loc = req.location_label.toLowerCase();
        return (
          tracking.includes(q) ||
          tech.includes(q) ||
          resident.includes(q) ||
          desc.includes(q) ||
          loc.includes(q)
        );
      }
      return true;
    });
  }, [requests, selectedCategory, searchQuery, categories]);

  // Counts
  const pendingCount = useMemo(
    () => requests.filter((r) => r.status === "APPROVED").length,
    [requests]
  );
  const activeDispatchesCount = useMemo(
    () =>
      requests.filter((r) => ["ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(r.status)).length,
    [requests]
  );

  return (
    <div className="page-container dispatch-page-container">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Supervisor Dispatch & Work-Order Assignment</h1>
          <p className="page-subtitle">
            Moroka Hall Residence &bull; Assign approved faults to active technicians, manage reassignments, and balance workloads (FR-10, FR-11, SCR-07)
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

      {technicians.length === 0 && !isTechsLoading && (
        <div className="alert alert-warning mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
          <div>
            <strong>No active technicians available:</strong> There are currently no active
            technicians registered in the system. Work orders cannot be assigned until an administrator
            creates or activates technician accounts (SCR-07, BR-07).
          </div>
        </div>
      )}

      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="card metric-card">
          <div className="metric-label">Approved & Awaiting Assignment</div>
          <div className="metric-value metric-accent">{pendingCount}</div>
          <div className="metric-hint">Ready for technician assignment (T6)</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Active Work Dispatches</div>
          <div className="metric-value metric-info">{activeDispatchesCount}</div>
          <div className="metric-hint">Assigned, in progress, or reopened tasks</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Active Technicians</div>
          <div className="metric-value metric-success">{technicians.length}</div>
          <div className="metric-hint">Available for Moroka Hall repairs</div>
        </div>
      </div>

      {/* Filter and Tab Toolbar */}
      <div className="card filter-toolbar-card">
        {/* Tabs */}
        <div className="status-tab-group" role="tablist" aria-label="Dispatch status views">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "PENDING_ASSIGNMENT"}
            className={`status-tab ${activeTab === "PENDING_ASSIGNMENT" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("PENDING_ASSIGNMENT")}
          >
            Pending Assignment ({pendingCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ACTIVE_DISPATCHES"}
            className={`status-tab ${activeTab === "ACTIVE_DISPATCHES" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ACTIVE_DISPATCHES")}
          >
            Active Dispatches ({activeDispatchesCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ALL"}
            className={`status-tab ${activeTab === "ALL" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ALL")}
          >
            All Dispatchable Requests
          </button>
        </div>

        {/* Dropdowns & Search */}
        <div className="filters-row">
          <div className="filter-item search-filter">
            <label htmlFor="dispatch-search" className="filter-label">
              Search
            </label>
            <input
              id="dispatch-search"
              type="text"
              placeholder="Search by tracking #, technician, resident, or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="filter-item">
            <label htmlFor="dispatch-category" className="filter-label">
              Fault Category
            </label>
            <select
              id="dispatch-category"
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

          {(selectedCategory > 0 || searchQuery.trim()) && (
            <div className="filter-item reset-filter-item">
              <label className="filter-label">&nbsp;</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSelectedCategory(0);
                  setSearchQuery("");
                }}
              >
                Clear Filters
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Requests Table / Content */}
      {isRequestsLoading || isTechsLoading ? (
        <div className="loading-container" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="loading-text">Loading dispatch queue & technician workloads...</p>
        </div>
      ) : isRequestsError ? (
        <div className="card empty-card" role="alert">
          <div className="empty-icon"><AppIcon name="alert" size={36} color="#d97706" /></div>
          <h2 className="empty-title">Failed to load dispatch queue</h2>
          <p className="empty-text">There was an error communicating with the server.</p>
          <button
            type="button"
            onClick={() => {
              refetchRequests();
              refetchTechnicians();
            }}
            className="btn btn-primary"
          >
            Retry Loading
          </button>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="card empty-card">
          <div className="empty-icon"><AppIcon name="check-circle" size={36} color="#10b981" /></div>
          <h2 className="empty-title">No requests awaiting dispatch</h2>
          <p className="empty-text">
            {activeTab === "PENDING_ASSIGNMENT"
              ? "All approved requests have already been assigned to technicians."
              : "No maintenance requests match the current dispatch filter criteria."}
          </p>
        </div>
      ) : (
        <div className="card table-card">
          <div className="table-responsive">
            <table className="triage-table">
              <thead>
                <tr>
                  <th>Tracking #</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Assigned Technician</th>
                  <th>Fault Description</th>
                  <th className="action-col">Dispatch Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRequests.map((req) => (
                  <tr key={req.id} className="triage-table-row">
                    <td className="tracking-cell">
                      <Link to={`/requests/${req.id}`} className="tracking-link">
                        {req.tracking_number}
                      </Link>
                    </td>
                    <td>
                      {req.priority ? (
                        <span className={`priority-badge priority-${req.priority.toLowerCase()}`}>
                          {req.priority}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
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
                        <div className="assigned-tech-cell">
                          <span className="assigned-tech-name">
                            {req.assigned_technician_name}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted italic">Unassigned</span>
                      )}
                    </td>
                    <td className="description-cell">
                      <p className="description-text" title={req.description_snippet}>
                        {req.description_snippet}
                      </p>
                    </td>
                    <td className="action-cell">
                      {req.status === "APPROVED" ? (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => openAssignModal(req)}
                          disabled={technicians.length === 0}
                          title={
                            technicians.length === 0
                              ? "No active technicians available"
                              : "Assign work order to technician"
                          }
                        >
                          Assign (T6) &rarr;
                        </button>
                      ) : ["ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(req.status) ? (
                        <button
                          type="button"
                          className="btn btn-warning btn-sm"
                          onClick={() => openReassignModal(req)}
                          disabled={technicians.length < 2}
                          title={
                            technicians.length < 2
                              ? "Requires at least 2 active technicians to reassign"
                              : "Reassign work order to a different technician"
                          }
                        >
                          Reassign (T7) &rarr;
                        </button>
                      ) : (
                        <Link to={`/requests/${req.id}`} className="btn btn-secondary btn-sm">
                          View &rarr;
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

      {/* Modal / Dialog for Assign (T6) or Reassign (T7) */}
      {activeActionModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">
                {activeActionModal.mode === "ASSIGN"
                  ? `Assign Technician to ${activeActionModal.request.tracking_number} (T6)`
                  : `Reassign Technician for ${activeActionModal.request.tracking_number} (T7)`}
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

            <form onSubmit={handleModalSubmit} className="modal-body">
              {formError && (
                <div className="alert alert-error mb-3" role="alert">
                  <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
                  <span>{formError}</span>
                </div>
              )}

              {/* Request Context Summary */}
              <div className="modal-context-box">
                <div>
                  <strong>Location:</strong> {activeActionModal.request.location_label} &bull; Block {activeActionModal.request.location_block}
                </div>
                <div>
                  <strong>Category:</strong> {activeActionModal.request.category_name}
                </div>
                <div>
                  <strong>Priority:</strong> {activeActionModal.request.priority || "MEDIUM"}
                </div>
                {activeActionModal.mode === "REASSIGN" && (
                  <div>
                    <strong>Currently Assigned:</strong>{" "}
                    <span className="highlight-tech">
                      {activeActionModal.request.assigned_technician_name}
                    </span>
                  </div>
                )}
              </div>

              {/* Technician Picker with Workload Counts */}
              <div className="form-group">
                <label htmlFor="tech-select" className="form-label">
                  {activeActionModal.mode === "ASSIGN"
                    ? "Select Qualified Technician"
                    : "Select New Technician (Must be different)"}{" "}
                  <span className="required">*</span>
                </label>
                <select
                  id="tech-select"
                  value={selectedTechId}
                  onChange={(e) => setSelectedTechId(Number(e.target.value))}
                  className="select-input"
                  required
                >
                  <option value="" disabled>
                    -- Select an active technician --
                  </option>
                  {technicians.map((t) => {
                    const isCurrent =
                      activeActionModal.mode === "REASSIGN" &&
                      t.full_name === activeActionModal.request.assigned_technician_name;
                    return (
                      <option key={t.id} value={t.id} disabled={isCurrent}>
                        {t.full_name} ({t.email}) &mdash; {t.active_tasks_count} active{" "}
                        {t.active_tasks_count === 1 ? "task" : "tasks"}
                        {isCurrent ? " (Current Technician)" : ""}
                      </option>
                    );
                  })}
                </select>
                <span className="field-hint">
                  Technicians are displayed with their live active workload in Moroka Hall.
                </span>
              </div>

              {/* Reason / Note Field */}
              <div className="form-group">
                <div className="label-row">
                  <label htmlFor="assign-note" className="form-label">
                    {activeActionModal.mode === "ASSIGN"
                      ? "Assignment Instructions / Notes (Optional)"
                      : "Mandatory Reassignment Reason"}{" "}
                    {activeActionModal.mode === "REASSIGN" && <span className="required">*</span>}
                  </label>
                  {activeActionModal.mode === "REASSIGN" && (
                    <span
                      className={`char-counter ${
                        actionNote.trim().length >= 10 ? "counter-valid" : "counter-low"
                      }`}
                    >
                      {actionNote.trim().length} chars (min 10)
                    </span>
                  )}
                </div>
                <textarea
                  id="assign-note"
                  rows={3}
                  value={actionNote}
                  onChange={(e) => setActionNote(e.target.value)}
                  placeholder={
                    activeActionModal.mode === "ASSIGN"
                      ? "Optional work instructions or materials guidance for the technician..."
                      : "Explain reason for reassigning (e.g., 'Primary technician on leave', 'Specialized plumbing tools required')..."
                  }
                  className="textarea-input"
                  required={activeActionModal.mode === "REASSIGN"}
                />
              </div>

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
                  className="btn btn-primary"
                  disabled={
                    transitionMutation.isPending ||
                    !selectedTechId ||
                    (activeActionModal.mode === "REASSIGN" && actionNote.trim().length < 10)
                  }
                >
                  {transitionMutation.isPending
                    ? "Dispatching..."
                    : activeActionModal.mode === "ASSIGN"
                    ? "Confirm Assignment (T6)"
                    : "Confirm Reassignment (T7)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
