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
import type { Priority, RequestStatus, TransitionPayload } from "../types/workflow";

type TriageMode = "NONE" | "APPROVE" | "CLARIFY" | "REJECT";

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const successMessage = location.state?.message;

  // Triage form state
  const [triageMode, setTriageMode] = useState<TriageMode>("NONE");
  const [priority, setPriority] = useState<Priority>("MEDIUM");
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

  const transitionMutation = useMutation({
    mutationFn: (payload: TransitionPayload) => workflowApi.transitionRequest(id!, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["requests", "detail", id], updated);
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["supervisor-requests"] });
      setTriageMode("NONE");
      setActionNote("");
      setResidentResponse("");
      setActionError(null);
      setActionSuccess("Request status updated successfully.");
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
            <Link to={user?.role === "SUPERVISOR" ? "/triage" : "/requests"} className="btn btn-secondary">
              &larr; Back to {user?.role === "SUPERVISOR" ? "Triage Queue" : "My Requests"}
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
  const isResidentOwner = user?.role === "RESIDENT" && req.resident?.id === user.id;

  // Latest clarification requested audit event if any
  const latestClarification = [...req.timeline]
    .reverse()
    .find((e) => e.action === "CLARIFICATION_REQUESTED");

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

  return (
    <div className="page-container detail-page-container">
      {/* Navigation Breadcrumb */}
      <div className="breadcrumb-nav">
        <Link
          to={isSupervisor ? "/triage" : "/requests"}
          className="back-link"
        >
          &larr; Back to {isSupervisor ? "Triage Queue" : "My Requests"}
        </Link>
      </div>

      {/* Global Alerts */}
      {successMessage && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon">✓</span>
          <span>{successMessage}</span>
        </div>
      )}
      {actionSuccess && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon">✓</span>
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="alert alert-error mb-3" role="alert">
          <span className="alert-icon">⚠️</span>
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
                <span className="text-muted">Protected under BR-04 privacy</span>
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

      {/* FR-07: Interactive Clarification Box for Resident Owner */}
      {req.status === "NEEDS_CLARIFICATION" && isResidentOwner && (
        <div className="card clarification-card">
          <div className="clarification-header">
            <span className="clarification-icon">❓</span>
            <div>
              <h2 className="clarification-title">Supervisor Clarification Needed</h2>
              <p className="clarification-subtitle">
                The maintenance supervisor requested additional information before dispatching this repair (FR-07).
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
      {req.status === "NEEDS_CLARIFICATION" && !isResidentOwner && (
        <div className="alert alert-warning mb-3">
          <span className="alert-icon">ℹ️</span>
          <div>
            <strong>Awaiting Resident Clarification:</strong>
            <p className="mt-1">
              A clarification question was sent to the resident: &ldquo;{latestClarification?.note || "Awaiting details"}&rdquo;.
              This request will return to the active triage queue once answered.
            </p>
          </div>
        </div>
      )}

      {/* FR-09: Supervisor Triage Actions Card (SCR-06, SCR-05) */}
      {isSupervisor && (req.status === "SUBMITTED" || req.status === "APPROVED") && (
        <div className="card triage-control-card">
          <div className="triage-control-header">
            <div>
              <h2 className="section-title">Supervisor Triage Actions (FR-09)</h2>
              <p className="section-subtitle">
                Evaluate this fault report, assign priority for technician dispatch, request clarification, or reject.
              </p>
            </div>
            {req.status === "APPROVED" && (
              <span className="status-note">
                ✓ Request Approved. Ready for dispatch in Slice 4.
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
                  ✓ Approve Fault (T4)
                </button>
                <button
                  type="button"
                  className={`btn ${triageMode === "CLARIFY" ? "btn-warning" : "btn-outline-warning"}`}
                  onClick={() => setTriageMode(triageMode === "CLARIFY" ? "NONE" : "CLARIFY")}
                >
                  ❓ Request Clarification (T2)
                </button>
              </>
            )}
            <button
              type="button"
              className={`btn ${triageMode === "REJECT" ? "btn-danger" : "btn-outline-danger"}`}
              onClick={() => setTriageMode(triageMode === "REJECT" ? "NONE" : "REJECT")}
            >
              ✕ Reject Request (T5)
            </button>
          </div>

          {/* Expandable Action Drawer */}
          {triageMode !== "NONE" && (
            <div className="triage-drawer">
              <form onSubmit={handleTriageExecute} className="triage-form">
                {triageMode === "APPROVE" && (
                  <div className="drawer-section">
                    <h3 className="drawer-title">Approve Maintenance Request (T4)</h3>
                    <p className="drawer-desc">
                      Assigning a priority is mandatory (BR-08). Once approved, this request can be dispatched to an active technician.
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

                {triageMode === "CLARIFY" && (
                  <div className="drawer-section">
                    <h3 className="drawer-title">Request Clarification from Resident (T2)</h3>
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
                    <h3 className="drawer-title">Reject Maintenance Request (T5)</h3>
                    <p className="drawer-desc text-danger">
                      Rejection is final and terminal (BR-06). A mandatory explanation of at least 10 characters is required for audit recording.
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

      {/* Chronological Audit Timeline Section (FR-18, SCR-05) */}
      <div className="card timeline-card">
        <h2 className="timeline-title">Request Lifecycle & Audit Timeline</h2>
        <p className="timeline-subtitle">
          Append-only chronological record of all lifecycle transitions and actors (FR-18).
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
