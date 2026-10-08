/**
 * System and error pages: 401, 403, 404, and role dashboard placeholders (Table 5.3, Section 6.3).
 */

import { Link } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export function UnauthorizedPage() {
  return (
    <main className="error-page-container">
      <div className="error-card">
        <div className="error-code">401</div>
        <h1 className="error-title">Authentication Required</h1>
        <p className="error-description">
          Your session has ended or credentials were not provided. Please sign in to continue.
        </p>
        <Link to="/login" className="btn btn-primary">
          Sign In Again
        </Link>
      </div>
    </main>
  );
}

export function ForbiddenPage() {
  const { user, getRoleHome } = useAuth();
  const homePath = user ? getRoleHome(user.role) : "/login";

  return (
    <main className="error-page-container">
      <div className="error-card">
        <div className="error-code">403</div>
        <h1 className="error-title">Access Denied</h1>
        <p className="error-description">
          Your account role ({user?.role || "GUEST"}) does not have permission to access this function.
        </p>
        <Link to={homePath} className="btn btn-primary">
          Return to My Workspace
        </Link>
      </div>
    </main>
  );
}

export function NotFoundPage() {
  const { user, getRoleHome } = useAuth();
  const homePath = user ? getRoleHome(user.role) : "/login";

  return (
    <main className="error-page-container">
      <div className="error-card">
        <div className="error-code">404</div>
        <h1 className="error-title">Page Not Found</h1>
        <p className="error-description">
          The requested page or resource is absent or outside your operational scope.
        </p>
        <Link to={homePath} className="btn btn-primary">
          Return Home
        </Link>
      </div>
    </main>
  );
}

interface RoleHomeViewProps {
  title: string;
  roleDescription: string;
  nextSliceName: string;
}

export function RoleHomeView({ title, roleDescription, nextSliceName }: RoleHomeViewProps) {
  const { user } = useAuth();

  return (
    <main className="role-workspace-container">
      <div className="workspace-card">
        <div className="workspace-header">
          <span className={`role-badge role-${user?.role.toLowerCase()}`}>
            {user?.role}
          </span>
          <h1 className="workspace-title">{title}</h1>
          <p className="workspace-user-welcome">
            Logged in as <strong>{user?.full_name}</strong> ({user?.email})
          </p>
        </div>

        <div className="workspace-info-box">
          <h2 className="info-title">Role Scope & Authorization</h2>
          <p>{roleDescription}</p>
        </div>

        <div className="workspace-next-slice-box">
          <span className="slice-tag">Active Delivery Pipeline</span>
          <p className="slice-text">
            Authentication and Session Layer (Slice 1) verified active. Operational workflow screens for this role will activate in <strong>{nextSliceName}</strong>.
          </p>
        </div>
      </div>
    </main>
  );
}
