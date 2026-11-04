/**
 * SCR-10: Operational Dashboard Screen (FR-16, BR-04, NFR-06, SCR-10).
 * Provides read-only aggregates, status distributions, fault category breakdowns,
 * and closure velocity metrics scoped to residence (Warden) or system-wide (Supervisor).
 */

import { useState } from "react";
import { AppIcon } from "../components/AppIcon";
import { useQuery } from "@tanstack/react-query";
import { reportingApi } from "../api/reporting";
import { useAuth } from "../context/useAuth";

export function DashboardPage() {
  const { user } = useAuth();
  const [selectedResidenceId, setSelectedResidenceId] = useState<number | null>(null);

  const {
    data: metrics,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["dashboard-metrics", selectedResidenceId],
    queryFn: () => reportingApi.getDashboardMetrics(selectedResidenceId),
  });

  const isSupervisor = user?.role === "SUPERVISOR";

  return (
    <main className="dashboard-page-container triage-page-container" id="main-content">
      {/* Header */}
      <div className="page-header">
        <div className="header-text-group">
          <div className="header-breadcrumbs">
            <span className="crumb-app">Oversight</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-page">Operational Dashboard</span>
          </div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            Where the work stands, how old it is and how long repairs take.
          </p>
        </div>

        <div className="page-header-actions">
          {/* Supervisor Residence Selector */}
          {isSupervisor && metrics?.scope?.available_residences && (
            <div className="residence-filter-group">
              <label htmlFor="residence-select" className="sr-only">
                Filter by Residence
              </label>
              <select
                id="residence-select"
                className="filter-select residence-selector"
                value={selectedResidenceId ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedResidenceId(val ? Number(val) : null);
                }}
              >
                <option value="">All Residences</option>
                {metrics.scope.available_residences.map((res) => (
                  <option key={res.id} value={res.id}>
                    {res.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Warden Scoped Badge */}
          {!isSupervisor && metrics?.scope && (
            <div className="warden-scope-badge">
              <span className="scope-label">Residence Scope:</span>
              <strong className="scope-name">{metrics.scope.residence_name}</strong>
            </div>
          )}

          <button
            type="button"
            onClick={() => refetch()}
            className="btn btn-secondary btn-refresh"
            disabled={isFetching}
            title="Refresh dashboard metrics"
          >
            {isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-state" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="loading-text">Loading operational aggregates...</p>
        </div>
      ) : isError || !metrics ? (
        <div className="card error-state" role="alert">
          <p className="error-title">Failed to load dashboard metrics.</p>
          <p className="error-subtitle">
            Could not retrieve residence aggregates from the reporting service.
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="btn btn-secondary"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          {/* Top Metric KPI Cards */}
          <section className="dashboard-kpi-grid" aria-label="Key Performance Indicators">
            {/* KPI 1: Open Requests */}
            <div className="card kpi-card border-top-primary">
              <div className="kpi-header">
                <span className="kpi-label">Open Backlog</span>
                <span className="kpi-icon"><AppIcon name="activity" size={20} color="var(--color-primary)" /></span>
              </div>
              <div className="kpi-value">{metrics.summary.open_requests}</div>
              <div className="kpi-subtext">
                {metrics.summary.active_work_orders}{" "}
                {metrics.summary.active_work_orders === 1 ? "order" : "orders"} currently dispatched
              </div>
            </div>

            {/* KPI 2: Closed Requests */}
            <div className="card kpi-card border-top-success">
              <div className="kpi-header">
                <span className="kpi-label">Resolved Requests</span>
                <span className="kpi-icon"><AppIcon name="check-circle" size={20} color="#10b981" /></span>
              </div>
              <div className="kpi-value">{metrics.summary.closed_requests}</div>
              <div className="kpi-subtext">
                {metrics.summary.total_requests > 0
                  ? `${Math.round(
                      (metrics.summary.closed_requests / metrics.summary.total_requests) * 100
                    )}% resolution rate (${metrics.summary.total_requests} total)`
                  : "0 total requests recorded"}
              </div>
            </div>

            {/* KPI 3: Mean Time to Closure (MTTC) */}
            <div className="card kpi-card border-top-info">
              <div className="kpi-header">
                <span className="kpi-label">Mean Time to Closure</span>
                <span className="kpi-icon"><AppIcon name="clock" size={20} color="#f59e0b" /></span>
              </div>
              <div className="kpi-value">
                {metrics.summary.mean_time_to_closure_hours > 0
                  ? `${metrics.summary.mean_time_to_closure_hours} hrs`
                  : "—"}
              </div>
              <div className="kpi-subtext">
                {metrics.summary.mean_time_to_closure_days > 0
                  ? `~${metrics.summary.mean_time_to_closure_days} days from report to closure`
                  : "Insufficient closed requests"}
              </div>
            </div>

            {/* KPI 4: Average Open Request Age */}
            <div className="card kpi-card border-top-warning">
              <div className="kpi-header">
                <span className="kpi-label">Avg Open Backlog Age</span>
                <span className="kpi-icon"><AppIcon name="clock" size={20} color="#ea580c" /></span>
              </div>
              <div className="kpi-value">
                {metrics.summary.average_open_age_hours > 0
                  ? `${metrics.summary.average_open_age_hours} hrs`
                  : "0.0 hrs"}
              </div>
              <div className="kpi-subtext">Average age of open requests</div>
            </div>
          </section>

          {/* Grid: Status Distribution & Requests by priority */}
          <div className="dashboard-visual-grid">
            {/* Panel 1: Lifecycle Status Breakdown */}
            <section className="card dashboard-panel-card" aria-label="Status Distribution">
              <div className="panel-header">
                <h2 className="panel-title">Requests by status</h2>
                <span className="panel-badge">{metrics.summary.total_requests} total</span>
              </div>
              <div className="status-bars-list">
                {Object.entries(metrics.status_counts).map(([statusKey, count]) => {
                  const pct =
                    metrics.summary.total_requests > 0
                      ? Math.round((count / metrics.summary.total_requests) * 100)
                      : 0;
                  return (
                    <div key={statusKey} className="status-bar-row">
                      <div className="status-bar-meta">
                        <span className={`status-pill status-${statusKey.toLowerCase().replace(/_/g, "-")}`}>
                          {statusKey.replace(/_/g, " ")}
                        </span>
                        <span className="status-count-pct">
                          <strong>{count}</strong> ({pct}%)
                        </span>
                      </div>
                      <div className="progress-track">
                        <div
                          className={`progress-fill fill-${statusKey.toLowerCase().replace(/_/g, "-")}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Panel 2: Requests by priority */}
            <section className="card dashboard-panel-card" aria-label="Priority Distribution">
              <div className="panel-header">
                <h2 className="panel-title">Requests by priority</h2>
                <span className="panel-badge">Triage Classification</span>
              </div>
              <div className="priority-bars-list">
                {["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNASSIGNED"].map((pKey) => {
                  const count = metrics.priority_counts[pKey] || 0;
                  const pct =
                    metrics.summary.total_requests > 0
                      ? Math.round((count / metrics.summary.total_requests) * 100)
                      : 0;
                  return (
                    <div key={pKey} className="priority-bar-row">
                      <div className="status-bar-meta">
                        <span className={`priority-tag priority-${pKey.toLowerCase()}`}>
                          {pKey}
                        </span>
                        <span className="status-count-pct">
                          <strong>{count}</strong> ({pct}%)
                        </span>
                      </div>
                      <div className="progress-track">
                        <div
                          className={`progress-fill fill-prio-${pKey.toLowerCase()}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          {/* Grid: Category Breakdown & Open Request Aging */}
          <div className="dashboard-visual-grid mt-4">
            {/* Panel 3: Fault Categories */}
            <section className="card dashboard-panel-card" aria-label="Fault Category Distribution">
              <div className="panel-header">
                <h2 className="panel-title">Fault Categories</h2>
                <span className="panel-badge">Infrastructure Domains</span>
              </div>
              <div className="category-counts-list">
                {metrics.category_counts.map((cat) => {
                  const pct =
                    metrics.summary.total_requests > 0
                      ? Math.round((cat.count / metrics.summary.total_requests) * 100)
                      : 0;
                  return (
                    <div key={cat.id} className="category-item-row">
                      <div className="category-label-group">
                        <span className="category-name">{cat.name}</span>
                        <span className="category-count">
                          {cat.count} {cat.count === 1 ? "fault" : "faults"} ({pct}%)
                        </span>
                      </div>
                      <div className="progress-track">
                        <div
                          className="progress-fill fill-category"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Panel 4: Backlog Aging Slices */}
            <section className="card dashboard-panel-card" aria-label="Open Request Aging">
              <div className="panel-header">
                <h2 className="panel-title">Backlog Aging Distribution</h2>
                <span className="panel-badge">{metrics.summary.open_requests} active</span>
              </div>
              <p className="panel-subtext">
                Turnaround latency brackets for active open maintenance requests.
              </p>
              <div className="aging-grid">
                <div className="aging-bracket-card bracket-fresh">
                  <span className="bracket-title">&lt; 24 Hours</span>
                  <span className="bracket-value">{metrics.aging_distribution.under_24h}</span>
                  <span className="bracket-desc">Freshly reported</span>
                </div>
                <div className="aging-bracket-card bracket-standard">
                  <span className="bracket-title">1 – 3 Days</span>
                  <span className="bracket-value">{metrics.aging_distribution["1_to_3_days"]}</span>
                  <span className="bracket-desc">In triage / dispatch</span>
                </div>
                <div className="aging-bracket-card bracket-attention">
                  <span className="bracket-title">3 – 7 Days</span>
                  <span className="bracket-value">{metrics.aging_distribution["3_to_7_days"]}</span>
                  <span className="bracket-desc">Needs attention</span>
                </div>
                <div className="aging-bracket-card bracket-overdue">
                  <span className="bracket-title">&gt; 7 Days</span>
                  <span className="bracket-value">{metrics.aging_distribution.over_7_days}</span>
                  <span className="bracket-desc">Overdue escalation</span>
                </div>
              </div>
            </section>
          </div>

          {/* Privacy & Scope Disclaimer Notice (BR-04, TC-36) */}
          <div className="dashboard-privacy-notice card">
            <span className="notice-icon"><AppIcon name="shield" size={22} color="var(--color-primary)" /></span>
            <div className="notice-text">
              <strong>Totals only.</strong> This dashboard never shows who reported a fault.
            </div>
          </div>
        </>
      )}
    </main>
  );
}
