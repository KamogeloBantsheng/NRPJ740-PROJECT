/**
 * System and error pages: 401, 403 and 404 (Table 5.3, Section 6.3).
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
