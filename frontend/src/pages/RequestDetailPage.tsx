/**
 * SCR-05: Request Detail, History Timeline & Triage Actions Page (FR-06, FR-07, FR-09, FR-18, SCR-05).
 * Displays full maintenance request details, interactive clarification response (T3),
 * supervisor triage controls (T2, T4, T5), and chronological audit timeline.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { AppError } from "../api/client";
import { useAuth } from "../context/useAuth";
import { StatusBadge } from "../components/StatusBadge";
import { AppIcon } from "../components/AppIcon";
import { LifecycleTrack } from "../components/LifecycleTrack";
import type { Priority, RequestStatus, TransitionPayload } from "../types/workflow";

type TriageMode =
  | "NONE"
  | "APPROVE"
  | "CLARIFY"
  | "REJECT"
  | "ASSIGN"
  | "REASSIGN"
  | "COMPLETE_WORK"
  | "VERIFY_CLOSE"
  | "REOPEN";

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const successMessage = location.state?.message;

  // Triage form state
  const [triageMode, setTriageMode] = useState<TriageMode>("NONE");
  const [priority, setPriority] = useState<Priority>("MEDIUM");
  const [selectedTechId, setSelectedTechId] = useState<number | "">("");
  const [actionNote, setActionNote] = useState<string>("");
  const [residentResponse, setResidentResponse] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const {
    data: req,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["requests", "detail", id],
    queryFn: () => workflowApi.getRequestDetail(id!),
    enabled: Boolean(id),
  });

  const { data: technicians = [] } = useQuery({
    queryKey: ["technicians"],
    queryFn: () => workflowApi.getTechnicians(),
    enabled: Boolean(user?.role === "SUPERVISOR"),
  });

  const transitionMutation = useMutation({
    mutationFn: (payload: TransitionPayload) => workflowApi.transitionRequest(id!, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["requests", "detail", id], updated);
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["supervisor-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dispatch-requests"] });
      queryClient.invalidateQueries({ queryKey: ["verification-requests"] });
      queryClient.invalidateQueries({ queryKey: ["technicians"] });
      queryClient.invalidateQueries({ queryKey: ["tech-work-queue"] });
      setTriageMode("NONE");
      setSelectedTechId("");
      setActionNote("");
      setResidentResponse("");
      setActionError(null);
      if (updated.status === "VERIFIED_CLOSED") {
        setActionSuccess(`Request ${updated.tracking_number} has been verified and permanently CLOSED.`);
      } else if (updated.status === "REOPENED") {
        setActionSuccess(`Request ${updated.tracking_number} has been REOPENED with feedback. Technician assignment retained.`);
      } else {
        setActionSuccess("Request status updated successfully.");
      }
    },
    onError: (err) => {
      if (err instanceof AppError && err.statusCode === 409) {
        setActionError(
          `State Conflict Detected: The request status changed to "${err.current_status || "a different state"}". The view has been refreshed.`
        );
        queryClient.invalidateQueries({ queryKey: ["requests", "detail", id] });
      } else if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while executing the transition.");
      }
    },
  });

  if (isLoading) {
    return (
      <div className="page-container">
        <div className="card loading-card">
          <div className="spinner" />
          <p>Loading request details...</p>
        </div>
      </div>
    );
  }

  if (isError || !req) {
    return (
      <div className="page-container">
        <div className="card error-card">
          <h2>Request Not Found</h2>
          <p>
            {error instanceof Error
              ? error.message
              : "This maintenance request was not found or is outside your authorization scope."}
          </p>
          <div className="mt-3">
            <Link
              to={
                user?.role === "SUPERVISOR"
                  ? "/triage"
                  : user?.role === "TECHNICIAN"
                  ? "/work"
                  : "/requests"
              }
              className="btn btn-secondary"
            >
              &larr; Back to{" "}
              {user?.role === "SUPERVISOR"
                ? "Triage Queue"
                : user?.role === "TECHNICIAN"
                ? "My Work Queue"
                : "My Requests"}
            </Link>
            <button onClick={() => refetch()} className="btn btn-primary ml-2">
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isSupervisor = user?.role === "SUPERVISOR";
  const isTechnician = user?.role === "TECHNICIAN";
  const isOwner = req.is_owner;
  const isAssignedTech =
    isTechnician && req.active_work_order?.technician_id === user?.id;

  const getSupervisorBackTarget = (status?: string) => {
    if (status === "WORK_COMPLETED" || status === "VERIFIED_CLOSED") {
      return { to: "/verification", label: "Verification Queue" };
    }
    if (status === "APPROVED" || status === "ASSIGNED") {
      return { to: "/dispatch", label: "Dispatch Queue" };
    }
    return { to: "/triage", label: "Triage Queue" };
  };

  const supervisorBack = getSupervisorBackTarget(req.status);
  const backTo = isSupervisor
    ? supervisorBack.to
    : isTechnician
    ? "/work"
    : "/requests";
  const backLabel = isSupervisor
    ? supervisorBack.label
    : isTechnician
    ? "My Work Queue"
    : "My Requests";

  // Latest clarification requested audit event if any
  const latestClarification = [...req.timeline]
    .reverse()
    .find((e) => e.action === "CLARIFICATION_REQUESTED");

  // Latest completion audit event if any
  const latestCompletion = [...req.timeline]
    .reverse()
    .find((e) => e.action === "WORK_COMPLETED");

  const handleClarificationSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);
    const trimmed = residentResponse.trim();
    if (trimmed.length < 10) {
      setActionError("Your clarification response must be at least 10 characters long.");
      return;
    }
    transitionMutation.mutate({
      action: "PROVIDE_CLARIFICATION",
      expected_status: req.status,
      note: trimmed,
    });
  };

  const handleTriageExecute = (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);
    const trimmed = actionNote.trim();

    if (triageMode === "APPROVE") {
      transitionMutation.mutate({
        action: "APPROVE",
        expected_status: req.status,
        priority: priority,
        note: trimmed || undefined,
      });
    } else if (triageMode === "CLARIFY") {
      if (trimmed.length < 10) {
        setActionError("Clarification question must be at least 10 characters long.");
        return;
      }
      transitionMutation.mutate({
        action: "REQUEST_CLARIFICATION",
        expected_status: req.status,
        note: trimmed,
      });
    } else if (triageMode === "ASSIGN") {
      if (!selectedTechId) {
        setActionError("Please select an active technician for assignment.");
        return;
      }
      transitionMutation.mutate({
        action: "ASSIGN",
        expected_status: req.status,
        technician_id: Number(selectedTechId),
        note: trimmed || undefined,
      });
    } else if (triageMode === "REASSIGN") {
      if (!selectedTechId) {
        setActionError("Please select a new technician for reassignment.");
        return;
      }
      if (trimmed.length < 10) {
        setActionError("Reassignment reason must be at least 10 characters long.");
        return;
      }
      const selectedTech = technicians.find((t) => t.id === Number(selectedTechId));
      if (
        selectedTech &&
        req.active_work_order &&
        selectedTech.id === req.active_work_order.technician_id
      ) {
        setActionError("Cannot reassign to the same technician. Please select a different technician.");
        return;
      }
      transitionMutation.mutate({
        action: "REASSIGN",
        expected_status: req.status,
        technician_id: Number(selectedTechId),
        note: trimmed,
      });
    } else if (triageMode === "COMPLETE_WORK") {
      if (trimmed.length < 20) {
        setActionError("Work completion notes must be at least 20 characters long.");
        return;
      }
      transitionMutation.mutate({
        action: "COMPLETE_WORK",
        expected_status: req.status,
        note: trimmed,
      });
    } else if (triageMode === "VERIFY_CLOSE") {
      transitionMutation.mutate({
        action: "VERIFY_CLOSE",
        expected_status: req.status,
        note: trimmed || undefined,
      });
    } else if (triageMode === "REOPEN") {
      if (trimmed.length < 10) {
        setActionError("Reopening feedback reason must be at least 10 characters long.");
        return;
      }
      transitionMutation.mutate({
        action: "REOPEN",
        expected_status: req.status,
        note: trimmed,
      });
    } else if (triageMode === "REJECT") {
      if (trimmed.length < 10) {
        setActionError("Rejection reason must be at least 10 characters long.");
        return;
      }
      transitionMutation.mutate({
        action: "REJECT",
        expected_status: req.status,
        note: trimmed,
      });
    }
  };

  const handleStartWork = () => {
    setActionError(null);
    setActionSuccess(null);
    transitionMutation.mutate({
      action: "START_WORK",
      expected_status: req.status,
    });
  };

  return (
    <div className="page-container detail-page-container">
      {/* Navigation Breadcrumb */}
      <div className="breadcrumb-nav">
        <Link to={backTo} className="back-link">
          &larr; Back to {backLabel}
        </Link>
      </div>

      {/* Global Alerts */}
      {successMessage && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="check" size={16} /></span>
          <span>{successMessage}</span>
        </div>
      )}
      {actionSuccess && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="check" size={16} /></span>
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="alert alert-error mb-3" role="alert">
          <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
          <span>{actionError}</span>
        </div>
      )}

      {/* Main Request Card */}
      <div className="card detail-card">
        {/* Header Bar */}
        <div className="detail-header-row">
          <div>
            <div className="tracking-title-row">
              <h1 className="detail-tracking-number">{req.tracking_number}</h1>
              <StatusBadge status={req.status as RequestStatus} size="lg" />
              {req.priority && (
                <span className={`priority-badge priority-${req.priority.toLowerCase()}`}>
                  {req.priority} Priority
                </span>
              )}
            </div>
            <p className="detail-subtitle">
              Reported on{" "}
              {new Date(req.created_at).toLocaleString("en-ZA", {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>

          <div className="detail-id-badge">ID #{req.id}</div>
        </div>

        {/* Metadata Grid */}
        <LifecycleTrack status={req.status} />

        <div className="detail-meta-grid">
          <div className="meta-item">
            <span className="meta-label">Fault Category</span>
            <span className="meta-value category-value">{req.category.name}</span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Location</span>
            <span className="meta-value">
              {req.location.residence_name} &bull; Block {req.location.block}, Fl {req.location.floor} ({req.location.label})
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Location Type</span>
            <span className="meta-value">
              {req.location.kind === "ROOM" ? "Resident Room" : "Common Area"}
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Reporter</span>
            <span className="meta-value">
              {req.resident ? (
                <>
                  {req.resident.full_name}{" "}
                  {req.resident.student_number && `(${req.resident.student_number})`}
                </>
              ) : (
                <span className="text-muted">Hidden to protect resident privacy</span>
              )}
            </span>
          </div>
        </div>

        {/* Description Section */}
        <div className="detail-description-section">
          <h2 className="section-title">Fault Description</h2>
          <div className="description-box">{req.description}</div>
        </div>
      </div>

      {/* FR-10, FR-11: Work Order Assignment Banner */}
      {req.active_work_order && (
        <div className="card work-order-card">
          <div className="work-order-header">
            <span className="work-order-icon"><AppIcon name="wrench" size={24} color="#be123c" /></span>
            <div>
              <h2 className="work-order-title">Active Work Order Assignment</h2>
              <p className="work-order-subtitle">
                The Technician currently responsible for this repair
              </p>
            </div>
          </div>

          <div className="work-order-grid">
            <div className="meta-item">
              <span className="meta-label">Assigned Technician</span>
              <span className="meta-value tech-highlight">
                {req.active_work_order.technician_name}
                {req.active_work_order.technician_email && ` (${req.active_work_order.technician_email})`}
              </span>
            </div>

            <div className="meta-item">
              <span className="meta-label">Assigned By</span>
              <span className="meta-value">{req.active_work_order.assigned_by_name}</span>
            </div>

            <div className="meta-item">
              <span className="meta-label">Assigned Timestamp</span>
              <span className="meta-value">
                {new Date(req.active_work_order.assigned_at).toLocaleString("en-ZA", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Prior Work Orders (Reassignment Audit Trail) */}
      {req.work_orders && req.work_orders.filter((wo) => !wo.is_active).length > 0 && (
        <div className="card prior-work-orders-card">
          <h3 className="prior-orders-title">
            Work Order History ({req.work_orders.filter((wo) => !wo.is_active).length} prior)
          </h3>
          <div className="prior-orders-list">
            {req.work_orders
              .filter((wo) => !wo.is_active)
              .map((wo) => (
                <div key={wo.id} className="prior-order-item">
                  <div>
                    <strong>{wo.technician_name}</strong>
                    {wo.technician_email && ` (${wo.technician_email})`}
                  </div>
                  <div className="prior-order-meta">
                    <span className="end-reason-tag">Status: {wo.end_reason}</span>
                    <span className="text-muted">
                      Ended:{" "}
                      {wo.ended_at
                        ? new Date(wo.ended_at).toLocaleString("en-ZA", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* FR-07: Interactive Clarification Box for Resident Owner */}
      {req.status === "NEEDS_CLARIFICATION" && isOwner && (
        <div className="card clarification-card">
          <div className="clarification-header">
            <span className="clarification-icon"><AppIcon name="info" size={24} color="#d97706" /></span>
            <div>
              <h2 className="clarification-title">Supervisor Clarification Needed</h2>
              <p className="clarification-subtitle">
                The maintenance supervisor requested additional information before dispatching this repair.
              </p>
            </div>
          </div>

          {latestClarification?.note && (
            <div className="supervisor-question-box">
              <span className="question-label">Supervisor's Question:</span>
              <p className="question-text">"{latestClarification.note}"</p>
            </div>
          )}

          <form onSubmit={handleClarificationSubmit} className="clarification-form">
            <div className="form-group">
              <div className="label-row">
                <label htmlFor="resident-response" className="form-label">
                  Your Clarification Response <span className="required">*</span>
                </label>
                <span
                  className={`char-counter ${
                    residentResponse.trim().length >= 10 ? "counter-valid" : "counter-low"
                  }`}
                >
                  {residentResponse.trim().length} chars (min 10)
                </span>
              </div>
              <textarea
                id="resident-response"
                rows={4}
                value={residentResponse}
                onChange={(e) => setResidentResponse(e.target.value)}
                placeholder="Provide specific details (e.g., 'It is the cold water tap valve leaking, not hot water')..."
                className="textarea-input"
                disabled={transitionMutation.isPending}
                required
              />
              <span className="field-hint">
                Once submitted, your response will return this request to the supervisor's active triage queue.
              </span>
            </div>

            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={transitionMutation.isPending || residentResponse.trim().length < 10}
              >
                {transitionMutation.isPending
                  ? "Submitting Response..."
                  : "Submit Clarification to Supervisor"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Clarification Alert if status is NEEDS_CLARIFICATION and viewer is NOT the owner */}
      {req.status === "NEEDS_CLARIFICATION" && !isOwner && (
        <div className="alert alert-warning mb-3">
          <span className="alert-icon"><AppIcon name="info" size={16} /></span>
          <div>
            <strong>Awaiting Resident Clarification:</strong>
            <p className="mt-1">
              A clarification question was sent to the resident: &ldquo;{latestClarification?.note || "Awaiting details"}&rdquo;.
              This request will return to the active triage queue once answered.
            </p>
          </div>
        </div>
      )}

      {/* FR-09, FR-10, FR-11: Supervisor Triage & Dispatch Actions Card (SCR-06, SCR-07, SCR-05) */}
      {isSupervisor &&
        ["SUBMITTED", "APPROVED", "ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(req.status) && (
          <div className="card triage-control-card">
            <div className="triage-control-header">
              <div>
                <h2 className="section-title">
                  {req.status === "SUBMITTED"
                    ? "Supervisor Triage Actions"
                    : req.status === "APPROVED"
                    ? "Supervisor Dispatch Actions"
                    : "Supervisor Reassignment Controls"}
                </h2>
                <p className="section-subtitle">
                  {req.status === "SUBMITTED"
                    ? "Evaluate this fault report, assign priority for technician dispatch, request clarification, or reject."
                    : req.status === "APPROVED"
                    ? "Assign this approved fault to a qualified active technician."
                    : "Reassign this active work order to another technician with mandatory reason."}
                </p>
              </div>
              {req.status === "APPROVED" && (
                <span className="status-note">
                  Request Approved. Ready for technician dispatch.
                </span>
              )}
              {["ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(req.status) && req.active_work_order && (
                <span className="status-note">
                  Assigned to {req.active_work_order.technician_name}
                </span>
              )}
            </div>

            {/* Action Button Row */}
            <div className="triage-buttons-row">
              {req.status === "SUBMITTED" && (
                <>
                  <button
                    type="button"
                    className={`btn ${triageMode === "APPROVE" ? "btn-primary" : "btn-outline-primary"}`}
                    onClick={() => setTriageMode(triageMode === "APPROVE" ? "NONE" : "APPROVE")}
                  >
                    Approve Fault
                  </button>
                  <button
                    type="button"
                    className={`btn ${triageMode === "CLARIFY" ? "btn-warning" : "btn-outline-warning"}`}
                    onClick={() => setTriageMode(triageMode === "CLARIFY" ? "NONE" : "CLARIFY")}
                  >
                    Request Clarification
                  </button>
                  <button
                    type="button"
                    className={`btn ${triageMode === "REJECT" ? "btn-danger" : "btn-outline-danger"}`}
                    onClick={() => setTriageMode(triageMode === "REJECT" ? "NONE" : "REJECT")}
                  >
                    Reject Request
                  </button>
                </>
              )}

              {req.status === "APPROVED" && (
                <>
                  <button
                    type="button"
                    className={`btn ${triageMode === "ASSIGN" ? "btn-primary" : "btn-outline-primary"}`}
                    onClick={() => {
                      if (triageMode !== "ASSIGN") {
                        setSelectedTechId(technicians.length > 0 ? technicians[0].id : "");
                        setActionNote("");
                      }
                      setTriageMode(triageMode === "ASSIGN" ? "NONE" : "ASSIGN");
                    }}
                    disabled={technicians.length === 0}
                    title={
                      technicians.length === 0
                        ? "No active technicians available"
                        : "Assign to active technician"
                    }
                  >
                    Assign Technician
                  </button>
                  <button
                    type="button"
                    className={`btn ${triageMode === "REJECT" ? "btn-danger" : "btn-outline-danger"}`}
                    onClick={() => setTriageMode(triageMode === "REJECT" ? "NONE" : "REJECT")}
                  >
                    Reject Request
                  </button>
                </>
              )}

              {["ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(req.status) && (
                <button
                  type="button"
                  className={`btn ${triageMode === "REASSIGN" ? "btn-warning" : "btn-outline-warning"}`}
                  onClick={() => {
                    if (triageMode !== "REASSIGN") {
                      const otherTech = technicians.find(
                        (t) => t.id !== req.active_work_order?.technician_id
                      );
                      setSelectedTechId(otherTech ? otherTech.id : "");
                      setActionNote("");
                    }
                    setTriageMode(triageMode === "REASSIGN" ? "NONE" : "REASSIGN");
                  }}
                  disabled={technicians.length < 2}
                  title={
                    technicians.length < 2
                      ? "Requires at least 2 active technicians to reassign"
                      : "Reassign work order to another technician"
                  }
                >
                  Reassign Technician
                </button>
              )}
            </div>

            {/* Expandable Action Drawer */}
            {triageMode !== "NONE" && (
              <div className="triage-drawer">
                <form onSubmit={handleTriageExecute} className="triage-form">
                  {triageMode === "APPROVE" && (
                    <div className="drawer-section">
                      <h3 className="drawer-title">Approve Maintenance Request</h3>
                      <p className="drawer-desc">
                        Assigning a priority is mandatory. Once approved, this request can be dispatched to an active technician.
                      </p>

                      <div className="form-group">
                        <label htmlFor="triage-priority" className="form-label">
                          Dispatch Priority <span className="required">*</span>
                        </label>
                        <select
                          id="triage-priority"
                          value={priority}
                          onChange={(e) => setPriority(e.target.value as Priority)}
                          className="select-input"
                          required
                        >
                          <option value="LOW">LOW &bull; Routine maintenance</option>
                          <option value="MEDIUM">MEDIUM &bull; Normal resident request</option>
                          <option value="HIGH">HIGH &bull; Urgent repair needed</option>
                          <option value="CRITICAL">CRITICAL &bull; Emergency / safety concern</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor="approve-note" className="form-label">
                          Approval Notes (Optional)
                        </label>
                        <textarea
                          id="approve-note"
                          rows={3}
                          value={actionNote}
                          onChange={(e) => setActionNote(e.target.value)}
                          placeholder="Optional internal supervisor dispatch notes..."
                          className="textarea-input"
                        />
                      </div>

                      <div className="drawer-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setTriageMode("NONE")}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-primary"
                          disabled={transitionMutation.isPending}
                        >
                          {transitionMutation.isPending ? "Approving..." : "Confirm Approval"}
                        </button>
                      </div>
                    </div>
                  )}

                  {triageMode === "ASSIGN" && (
                    <div className="drawer-section">
                      <h3 className="drawer-title">Assign Technician</h3>
                      <p className="drawer-desc">
                        Choose the Technician who will do this repair.
                      </p>

                      <div className="form-group">
                        <label htmlFor="triage-tech" className="form-label">
                          Qualified Technician <span className="required">*</span>
                        </label>
                        <select
                          id="triage-tech"
                          value={selectedTechId}
                          onChange={(e) => setSelectedTechId(Number(e.target.value))}
                          className="select-input"
                          required
                        >
                          <option value="" disabled>
                            -- Select active technician --
                          </option>
                          {technicians.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.full_name} ({t.email}) &mdash; {t.active_tasks_count} active{" "}
                              {t.active_tasks_count === 1 ? "task" : "tasks"}
                            </option>
                          ))}
                        </select>
                        <span className="field-hint">
                          Technician workloads are dynamically calculated from active work orders.
                        </span>
                      </div>

                      <div className="form-group">
                        <label htmlFor="assign-note" className="form-label">
                          Dispatch Notes (Optional)
                        </label>
                        <textarea
                          id="assign-note"
                          rows={3}
                          value={actionNote}
                          onChange={(e) => setActionNote(e.target.value)}
                          placeholder="Optional instructions or parts guidance..."
                          className="textarea-input"
                        />
                      </div>

                      <div className="drawer-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setTriageMode("NONE")}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-primary"
                          disabled={transitionMutation.isPending || !selectedTechId}
                        >
                          {transitionMutation.isPending ? "Assigning..." : "Confirm Assignment"}
                        </button>
                      </div>
                    </div>
                  )}

                  {triageMode === "REASSIGN" && (
                    <div className="drawer-section">
                      <h3 className="drawer-title">Reassign Technician</h3>
                      <p className="drawer-desc">
                        Reassign this active repair to a different technician. The previous work order will be closed with reason <span className="highlight-status">REASSIGNED</span>.
                      </p>

                      <div className="form-group">
                        <label htmlFor="reassign-tech" className="form-label">
                          New Technician <span className="required">*</span>
                        </label>
                        <select
                          id="reassign-tech"
                          value={selectedTechId}
                          onChange={(e) => setSelectedTechId(Number(e.target.value))}
                          className="select-input"
                          required
                        >
                          <option value="" disabled>
                            -- Select a different active technician --
                          </option>
                          {technicians.map((t) => {
                            const isCurrent = t.id === req.active_work_order?.technician_id;
                            return (
                              <option key={t.id} value={t.id} disabled={isCurrent}>
                                {t.full_name} ({t.email}) &mdash; {t.active_tasks_count} active{" "}
                                {t.active_tasks_count === 1 ? "task" : "tasks"}
                                {isCurrent ? " (Current Technician)" : ""}
                              </option>
                            );
                          })}
                        </select>
                      </div>

                      <div className="form-group">
                        <div className="label-row">
                          <label htmlFor="reassign-note" className="form-label">
                            Mandatory Reassignment Reason <span className="required">*</span>
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
                          id="reassign-note"
                          rows={3}
                          value={actionNote}
                          onChange={(e) => setActionNote(e.target.value)}
                          placeholder="State the reason for reassignment (e.g. 'Technician reassigned to high-priority emergency pipe burst in Block A')..."
                          className="textarea-input"
                          required
                        />
                      </div>

                      <div className="drawer-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setTriageMode("NONE")}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-warning"
                          disabled={
                            transitionMutation.isPending ||
                            !selectedTechId ||
                            actionNote.trim().length < 10
                          }
                        >
                          {transitionMutation.isPending ? "Reassigning..." : "Confirm Reassignment"}
                        </button>
                      </div>
                    </div>
                  )}

                  {triageMode === "CLARIFY" && (
                    <div className="drawer-section">
                      <h3 className="drawer-title">Request Clarification from Resident</h3>
                      <p className="drawer-desc">
                        Moves request to <span className="highlight-status">NEEDS_CLARIFICATION</span>. The resident will be prompted to answer before the request can proceed.
                      </p>

                      <div className="form-group">
                        <div className="label-row">
                          <label htmlFor="clarify-note" className="form-label">
                            Question / Details Needed <span className="required">*</span>
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
                          id="clarify-note"
                          rows={3}
                          value={actionNote}
                          onChange={(e) => setActionNote(e.target.value)}
                          placeholder="State what information is missing (e.g. 'Is the water supply leaking from under the sink or from the main wall tap?')..."
                          className="textarea-input"
                          required
                        />
                      </div>

                      <div className="drawer-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setTriageMode("NONE")}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-warning"
                          disabled={transitionMutation.isPending || actionNote.trim().length < 10}
                        >
                          {transitionMutation.isPending ? "Sending Question..." : "Send Question to Resident"}
                        </button>
                      </div>
                    </div>
                  )}

                  {triageMode === "REJECT" && (
                    <div className="drawer-section">
                      <h3 className="drawer-title">Reject Maintenance Request</h3>
                      <p className="drawer-desc text-danger">
                        Rejection is final and terminal. A mandatory explanation of at least 10 characters is required for audit recording.
                      </p>

                      <div className="form-group">
                        <div className="label-row">
                          <label htmlFor="reject-note" className="form-label">
                            Mandatory Rejection Reason <span className="required">*</span>
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
                          id="reject-note"
                          rows={3}
                          value={actionNote}
                          onChange={(e) => setActionNote(e.target.value)}
                          placeholder="Explain why this request is rejected (e.g. 'Duplicate report already logged as MR-000104' or 'Non-university personal appliance')..."
                          className="textarea-input"
                          required
                        />
                      </div>

                      <div className="drawer-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setTriageMode("NONE")}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-danger"
                          disabled={transitionMutation.isPending || actionNote.trim().length < 10}
                        >
                          {transitionMutation.isPending ? "Rejecting..." : "Confirm Rejection (Terminal)"}
                        </button>
                      </div>
                    </div>
                  )}
                </form>
              </div>
            )}
          </div>
        )}

      {/* FR-12: Supervisor Quality Verification Review Card (SCR-08, SCR-05) */}
      {isSupervisor && req.status === "WORK_COMPLETED" && (
        <div className="card triage-control-card verification-control-card">
          <div className="triage-control-header">
            <div>
              <h2 className="section-title">Supervisor Quality Verification Review</h2>
              <p className="section-subtitle">
                Review completed technician repairs on site. Confirm and close request or return to technician with feedback.
              </p>
            </div>
            <span className="status-note status-awaiting-verify-note">
              Awaiting Supervisor Verification
            </span>
          </div>

          {/* Technician Completion Notes Callout */}
          {latestCompletion && (
            <div className="technician-notes-callout">
              <div className="callout-header">
                <strong>Technician Completion Notes:</strong>
                <span className="callout-meta">
                  Submitted by {latestCompletion.actor_name} &bull;{" "}
                  {new Date(latestCompletion.occurred_at).toLocaleString("en-ZA", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <p className="callout-content">{latestCompletion.note}</p>
            </div>
          )}

          <div className="triage-buttons-row">
            <button
              type="button"
              className={`btn ${triageMode === "VERIFY_CLOSE" ? "btn-success" : "btn-outline-success"}`}
              onClick={() => {
                if (triageMode !== "VERIFY_CLOSE") {
                  setActionNote("");
                }
                setTriageMode(triageMode === "VERIFY_CLOSE" ? "NONE" : "VERIFY_CLOSE");
              }}
            >
              Verify & Close Request
            </button>
            <button
              type="button"
              className={`btn ${triageMode === "REOPEN" ? "btn-warning" : "btn-outline-warning"}`}
              onClick={() => {
                if (triageMode !== "REOPEN") {
                  setActionNote("");
                }
                setTriageMode(triageMode === "REOPEN" ? "NONE" : "REOPEN");
              }}
            >
              Reopen with Feedback
            </button>
          </div>

          {/* Verification Drawer */}
          {triageMode === "VERIFY_CLOSE" && (
            <div className="triage-drawer">
              <form onSubmit={handleTriageExecute} className="triage-form">
                <div className="drawer-section">
                  <h3 className="drawer-title">Confirm & Close Maintenance Request</h3>
                  <p className="drawer-desc">
                    Closing this request is permanent and terminal. The active work order will end as <strong>COMPLETED</strong>, and the completion timestamp will be recorded.
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

                  <div className="drawer-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setTriageMode("NONE")}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-success"
                      disabled={transitionMutation.isPending}
                    >
                      {transitionMutation.isPending ? "Closing..." : "Confirm & Close Request"}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          )}

          {/* Reopen Drawer */}
          {triageMode === "REOPEN" && (
            <div className="triage-drawer">
              <form onSubmit={handleTriageExecute} className="triage-form">
                <div className="drawer-section">
                  <h3 className="drawer-title">Reopen Maintenance Request with Feedback</h3>
                  <p className="drawer-desc text-warning">
                    Reopening requires mandatory feedback of at least 10 characters explaining what needs correction. The request will return to <strong>REOPENED</strong> while retaining the assigned technician.
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
                      This feedback will be recorded in the audit log and displayed to the technician in their work queue.
                    </span>
                  </div>

                  <div className="drawer-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setTriageMode("NONE")}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-warning"
                      disabled={transitionMutation.isPending || actionNote.trim().length < 10}
                    >
                      {transitionMutation.isPending ? "Reopening..." : "Reopen Request"}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* FR-14, FR-15: Technician Repair Actions Card (SCR-09, SCR-05) */}
      {isAssignedTech && ["ASSIGNED", "IN_PROGRESS", "REOPENED"].includes(req.status) && (
        <div className="card triage-control-card technician-control-card">
          <div className="triage-control-header">
            <div>
              <h2 className="section-title">Technician Repair Actions</h2>
              <p className="section-subtitle">
                {["ASSIGNED", "REOPENED"].includes(req.status)
                  ? "Start repair work to update the request status to IN PROGRESS."
                  : "Submit mandatory repair completion notes for supervisor verification review."}
              </p>
            </div>
            {req.status === "IN_PROGRESS" && (
              <span className="status-note status-in-progress-note">
                Repair Work In Progress
              </span>
            )}
          </div>

          <div className="triage-buttons-row">
            {["ASSIGNED", "REOPENED"].includes(req.status) && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartWork}
                disabled={transitionMutation.isPending}
              >
                {transitionMutation.isPending ? "Starting Work..." : "Start Work"}
              </button>
            )}

            {req.status === "IN_PROGRESS" && (
              <button
                type="button"
                className={`btn ${triageMode === "COMPLETE_WORK" ? "btn-success" : "btn-outline-success"}`}
                onClick={() => {
                  if (triageMode !== "COMPLETE_WORK") {
                    setActionNote("");
                  }
                  setTriageMode(triageMode === "COMPLETE_WORK" ? "NONE" : "COMPLETE_WORK");
                }}
              >
                Complete Work
              </button>
            )}
          </div>

          {/* Complete Work Drawer */}
          {triageMode === "COMPLETE_WORK" && (
            <div className="triage-drawer">
              <form onSubmit={handleTriageExecute} className="triage-form">
                <div className="drawer-section">
                  <h3 className="drawer-title">Submit Repair Completion</h3>
                  <p className="drawer-desc">
                    Detailed notes of at least 20 characters are required for supervisor verification review.
                  </p>

                  <div className="form-group">
                    <div className="label-row">
                      <label htmlFor="tech-completion-note" className="form-label">
                        Repair Completion Notes <span className="required">*</span>
                      </label>
                      <span
                        className={`char-counter ${
                          actionNote.trim().length >= 20 ? "counter-valid" : "counter-low"
                        }`}
                      >
                        {actionNote.trim().length} chars (min 20)
                      </span>
                    </div>
                    <textarea
                      id="tech-completion-note"
                      rows={4}
                      value={actionNote}
                      onChange={(e) => setActionNote(e.target.value)}
                      placeholder="Describe what was repaired or replaced, and confirm tests passed (e.g. 'Replaced 15mm copper pipe valve, repressurized system, confirmed dry')..."
                      className="textarea-input"
                      required
                    />
                  </div>

                  <div className="drawer-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setTriageMode("NONE")}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-success"
                      disabled={transitionMutation.isPending || actionNote.trim().length < 20}
                    >
                      {transitionMutation.isPending ? "Submitting..." : "Confirm Work Completed"}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* Chronological Audit Timeline Section (FR-18, SCR-05) */}
      <div className="card timeline-card">
        <h2 className="timeline-title">Request Lifecycle & Audit Timeline</h2>
        <p className="timeline-subtitle">
          Append-only chronological record of all lifecycle transitions and actors.
        </p>

        {req.timeline.length === 0 ? (
          <p className="timeline-empty">No timeline events recorded yet.</p>
        ) : (
          <div className="timeline-container">
            {req.timeline.map((event, index) => {
              const isFirst = index === 0;
              const formattedTime = new Date(event.occurred_at).toLocaleString("en-ZA", {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div key={event.id} className="timeline-item">
                  <div className={`timeline-marker ${isFirst ? "marker-active" : ""}`} />
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className="timeline-action">{event.action.replace(/_/g, " ")}</span>
                      <span className="timeline-date">{formattedTime}</span>
                    </div>

                    <div className="timeline-meta-row">
                      <span className="actor-badge">
                        By: {event.actor_name} ({event.actor_role})
                      </span>
                      {event.to_status && (
                        <span className="transition-pill">
                          Status: <strong>{event.to_status}</strong>
                        </span>
                      )}
                    </div>

                    {event.note && (
                      <div className="timeline-note-box">
                        <strong>Note:</strong> {event.note}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
