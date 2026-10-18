/**
 * SCR-09: Technician "My Work" Queue & Repair Management Page (FR-13, FR-14, FR-15; BR-02, BR-04, SCR-09).
 * Displays assigned maintenance tasks prioritized by urgency, allowing technicians to start work (T8)
 * and complete work with mandatory &ge; 20-character notes (T9), with strict resident identity protection (BR-04).
 */

import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { AppError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import type { MaintenanceRequestSummary, RequestStatus, TransitionPayload } from "../types/workflow";

type TechTab = "ACTIVE_QUEUE" | "READY_TO_START" | "IN_PROGRESS" | "ALL";

export function TechnicianWorkPage() {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TechTab>("ACTIVE_QUEUE");
  const [selectedCategory, setSelectedCategory] = useState<number>(0);
  const [selectedLocation, setSelectedLocation] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Complete Work modal state
  const [completingRequest, setCompletingRequest] = useState<MaintenanceRequestSummary | null>(null);
  const [completionNotes, setCompletionNotes] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Status param based on active tab
  const statusParam = useMemo(() => {
    switch (activeTab) {
      case "ACTIVE_QUEUE":
        return "ASSIGNED,IN_PROGRESS,REOPENED";
      case "READY_TO_START":
        return "ASSIGNED,REOPENED";
      case "IN_PROGRESS":
        return "IN_PROGRESS";
      case "ALL":
      default:
        return undefined;
    }
  }, [activeTab]);

  const {
    data: requests = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["tech-work-queue", statusParam],
    queryFn: () => workflowApi.getWorkQueue(statusParam),
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
      queryClient.invalidateQueries({ queryKey: ["tech-work-queue"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["supervisor-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dispatch-requests"] });
      closeModal();
      if (updated.status === "IN_PROGRESS") {
        setActionSuccess(`Work started on ${updated.tracking_number}. Status updated to IN PROGRESS.`);
      } else if (updated.status === "WORK_COMPLETED") {
        setActionSuccess(`Work successfully marked as COMPLETED on ${updated.tracking_number}. Ready for supervisor review.`);
      } else {
        setActionSuccess("Request status updated successfully.");
      }
    },
    onError: (err) => {
      if (err instanceof AppError && err.statusCode === 409) {
        setActionError(
          `State Conflict Detected: The request status changed to "${err.current_status || "a different state"}". The queue has been refreshed.`
        );
        queryClient.invalidateQueries({ queryKey: ["tech-work-queue"] });
      } else if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while executing the state transition.");
      }
    },
  });

  const handleStartWork = (req: MaintenanceRequestSummary) => {
    setActionError(null);
    setActionSuccess(null);
    transitionMutation.mutate({
      id: req.id,
      payload: {
        action: "START_WORK",
        expected_status: req.status,
      },
    });
  };

  const openCompleteModal = (req: MaintenanceRequestSummary) => {
    setActionError(null);
    setActionSuccess(null);
    setCompletionNotes("");
    setCompletingRequest(req);
  };

  const closeModal = () => {
    setCompletingRequest(null);
    setCompletionNotes("");
    setActionError(null);
  };

  const handleCompleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!completingRequest) return;

    setActionError(null);
    const trimmed = completionNotes.trim();
    if (trimmed.length < 20) {
      setActionError("Work completion notes must be at least 20 characters long (BR-02).");
      return;
    }

    transitionMutation.mutate({
      id: completingRequest.id,
      payload: {
        action: "COMPLETE_WORK",
        expected_status: completingRequest.status,
        note: trimmed,
      },
    });
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
        return tracking.includes(q) || desc.includes(q) || loc.includes(q);
      }
      return true;
    });
  }, [requests, selectedCategory, selectedLocation, searchQuery, categories, locations]);

  // Counts
  const readyToStartCount = useMemo(
    () => requests.filter((r) => ["ASSIGNED", "REOPENED"].includes(r.status)).length,
    [requests]
  );
  const inProgressCount = useMemo(
    () => requests.filter((r) => r.status === "IN_PROGRESS").length,
    [requests]
  );
  const completedCount = useMemo(
    () => requests.filter((r) => r.status === "WORK_COMPLETED").length,
    [requests]
  );

  return (
    <div className="page-container technician-page-container">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Technician Work Queue & Tasks</h1>
          <p className="page-subtitle">
            Moroka Hall Residence &bull; Review assigned repairs by priority, start work, and record mandatory completion notes (FR-13, FR-14, FR-15, SCR-09)
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
      {actionError && !completingRequest && (
        <div className="alert alert-error mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
          <span>{actionError}</span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="card metric-card">
          <div className="metric-label">Tasks Ready to Start</div>
          <div className="metric-value metric-warning">{readyToStartCount}</div>
          <div className="metric-hint">Assigned or reopened repairs awaiting work (T8)</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Repairs In Progress</div>
          <div className="metric-value metric-accent">{inProgressCount}</div>
          <div className="metric-hint">Currently being addressed in Moroka Hall</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Completed by You</div>
          <div className="metric-value metric-success">{completedCount}</div>
          <div className="metric-hint">Awaiting supervisor verification & close (T10)</div>
        </div>
      </div>

      {/* Filter and Tab Toolbar */}
      <div className="card filter-toolbar-card">
        {/* Tabs */}
        <div className="status-tab-group" role="tablist" aria-label="Technician work queue tabs">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ACTIVE_QUEUE"}
            className={`status-tab ${activeTab === "ACTIVE_QUEUE" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ACTIVE_QUEUE")}
          >
            Active Tasks ({readyToStartCount + inProgressCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "READY_TO_START"}
            className={`status-tab ${activeTab === "READY_TO_START" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("READY_TO_START")}
          >
            Ready to Start ({readyToStartCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "IN_PROGRESS"}
            className={`status-tab ${activeTab === "IN_PROGRESS" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("IN_PROGRESS")}
          >
            In Progress ({inProgressCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ALL"}
            className={`status-tab ${activeTab === "ALL" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("ALL")}
          >
            All Assigned Tasks
          </button>
        </div>

        {/* Dropdowns & Search */}
        <div className="filters-row">
          <div className="filter-item search-filter">
            <label htmlFor="tech-search" className="filter-label">
              Search
            </label>
            <input
              id="tech-search"
              type="text"
              placeholder="Search by tracking #, location, or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="filter-item">
            <label htmlFor="tech-category" className="filter-label">
              Fault Category
            </label>
            <select
              id="tech-category"
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
            <label htmlFor="tech-location" className="filter-label">
              Location in Moroka Hall
            </label>
            <select
              id="tech-location"
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
          <p className="loading-text">Loading assigned maintenance tasks...</p>
        </div>
      ) : isError ? (
        <div className="card empty-card" role="alert">
          <div className="empty-icon"><AppIcon name="alert" size={40} color="#d97706" /></div>
          <h2 className="empty-title">Failed to load work queue</h2>
          <p className="empty-text">There was an error communicating with the server.</p>
          <button type="button" onClick={() => refetch()} className="btn btn-primary">
            Retry Loading
          </button>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="card empty-card">
          <div className="empty-icon"><AppIcon name="check-circle" size={40} color="#10b981" /></div>
          <h2 className="empty-title">Your work queue is clear!</h2>
          <p className="empty-text">
            {activeTab === "ACTIVE_QUEUE"
              ? "You have no active maintenance tasks pending action in Moroka Hall."
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
                  <th>Fault Description</th>
                  <th>Reported Date</th>
                  <th className="action-col">Technician Action</th>
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
                      {["ASSIGNED", "REOPENED"].includes(req.status) ? (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleStartWork(req)}
                          disabled={transitionMutation.isPending}
                          title="Start working on this maintenance request"
                        >
                          Start Work (T8) &rarr;
                        </button>
                      ) : req.status === "IN_PROGRESS" ? (
                        <button
                          type="button"
                          className="btn btn-success btn-sm"
                          onClick={() => openCompleteModal(req)}
                          title="Mark work as completed with mandatory notes"
                        >
                          Complete Work (T9)
                        </button>
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

      {/* Complete Work Modal (T9) */}
      {completingRequest && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">
                Complete Work: {completingRequest.tracking_number} (T9)
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

            <form onSubmit={handleCompleteSubmit} className="modal-body">
              {actionError && (
                <div className="alert alert-error mb-3" role="alert">
                  <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
                  <span>{actionError}</span>
                </div>
              )}

              {/* Task Context Summary */}
              <div className="modal-context-box">
                <div>
                  <strong>Location:</strong> {completingRequest.location_label} &bull; Block {completingRequest.location_block}
                </div>
                <div>
                  <strong>Category:</strong> {completingRequest.category_name}
                </div>
                <div>
                  <strong>Priority:</strong> {completingRequest.priority || "MEDIUM"}
                </div>
                <div>
                  <strong>Current Status:</strong>{" "}
                  <span className="highlight-status">IN PROGRESS</span>
                </div>
              </div>

              {/* Mandatory Completion Notes Textarea (BR-02 >= 20 chars) */}
              <div className="form-group">
                <div className="label-row">
                  <label htmlFor="completion-notes" className="form-label">
                    Repair Completion Notes <span className="required">*</span>
                  </label>
                  <span
                    className={`char-counter ${
                      completionNotes.trim().length >= 20 ? "counter-valid" : "counter-low"
                    }`}
                  >
                    {completionNotes.trim().length} chars (min 20)
                  </span>
                </div>
                <textarea
                  id="completion-notes"
                  rows={4}
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="Describe parts replaced, corrective action taken, and verification checks performed (e.g., 'Replaced 15mm copper pipe elbow joint and confirmed no further leakage under pressure.')..."
                  className="textarea-input"
                  required
                />
                <span className="field-hint">
                  Detailed repair notes are required for supervisor verification review (BR-02).
                </span>
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
                  className="btn btn-success"
                  disabled={transitionMutation.isPending || completionNotes.trim().length < 20}
                >
                  {transitionMutation.isPending
                    ? "Submitting Completion..."
                    : "Confirm Work Completed (T9)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
