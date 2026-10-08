/**
 * SCR-05: Request Detail & History Timeline Page (FR-06, FR-18, SCR-05).
 * Displays full maintenance request details and chronological audit timeline.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { workflowApi } from "../api/workflow";
import { StatusBadge } from "../components/StatusBadge";
import type { RequestStatus } from "../types/workflow";

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const successMessage = location.state?.message;

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
            <Link to="/requests" className="btn btn-secondary">
              &larr; Return to My Requests
            </Link>
            <button onClick={() => refetch()} className="btn btn-primary ml-2">
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container detail-page-container">
      {/* Navigation */}
      <div className="breadcrumb-nav">
        <Link to="/requests" className="back-link">
          &larr; Back to My Requests
        </Link>
      </div>

      {/* Optional Success Banner */}
      {successMessage && (
        <div className="alert alert-success mb-3" role="alert">
          <span className="alert-icon">✓</span>
          <span>{successMessage}</span>
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
              Submitted on{" "}
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

        {/* Clarification Alert if status is NEEDS_CLARIFICATION */}
        {req.status === "NEEDS_CLARIFICATION" && (
          <div className="alert alert-warning mb-3">
            <span className="alert-icon">ℹ️</span>
            <div>
              <strong>Clarification Requested by Supervisor:</strong>
              <p className="mt-1">
                The maintenance supervisor has requested additional information before dispatching a technician.
                Please check the timeline history below.
              </p>
            </div>
          </div>
        )}

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
              {req.resident.full_name}{" "}
              {req.resident.student_number && `(${req.resident.student_number})`}
            </span>
          </div>
        </div>

        {/* Description Section */}
        <div className="detail-description-section">
          <h2 className="section-title">Fault Description</h2>
          <div className="description-box">{req.description}</div>
        </div>
      </div>

      {/* Chronological Audit Timeline Section (FR-18, SCR-05) */}
      <div className="card timeline-card">
        <h2 className="timeline-title">Request Lifecycle & Audit Timeline</h2>
        <p className="timeline-subtitle">
          Append-only chronological record of all system events and transitions (FR-18).
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
