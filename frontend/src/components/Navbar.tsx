/**
 * Application Navigation Bar (SCR-01 through SCR-13).
 */

import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export function Navbar() {
  const { user, isAuthenticated, logout, getRoleHome } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      navigate("/login", { replace: true });
    }
  };

  const homeHref = user ? getRoleHome(user.role) : "/login";

  return (
    <header className="navbar" role="banner">
      <div className="navbar-container">
        <Link to={homeHref} className="navbar-brand" aria-label="Home">
          <div className="brand-mark-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </div>
          <div className="brand-text-block">
            <span className="brand-spu">SPU</span>
            <span className="brand-title">Moroka Hall Maintenance</span>
          </div>
        </Link>

        {isAuthenticated && user && (
          <div className="navbar-user-section">
            <div className="user-profile-meta">
              <span className="user-name">{user.full_name}</span>
              <span className={`role-badge role-${user.role.toLowerCase()}`}>
                {user.role}
              </span>
              {user.residence_name && (
                <span className="residence-badge">{user.residence_name}</span>
              )}
            </div>

            <nav className="navbar-actions" aria-label="Navigation and account actions">
              {user.role === "WARDEN" && (
                <>
                  <Link to="/dashboard" className="nav-link">
                    Dashboard
                  </Link>
                  <Link to="/requests/new" className="nav-link">
                    Report Fault
                  </Link>
                </>
              )}
              {user.role === "SUPERVISOR" && (
                <>
                  <Link to="/dashboard" className="nav-link">
                    Dashboard
                  </Link>
                  <Link to="/triage" className="nav-link">
                    Triage Queue
                  </Link>
                  <Link to="/dispatch" className="nav-link">
                    Dispatch
                  </Link>
                  <Link to="/verification" className="nav-link">
                    Verification
                  </Link>
                </>
              )}
              {user.role === "RESIDENT" && (
                <>
                  <Link to="/requests" className="nav-link">
                    My Requests
                  </Link>
                  <Link to="/requests/new" className="nav-link">
                    Report Fault
                  </Link>
                </>
              )}
              {user.role === "TECHNICIAN" && (
                <Link to="/work" className="nav-link">
                  My Work
                </Link>
              )}
              {user.role === "ADMIN" && (
                <>
                  <Link to="/dashboard" className="nav-link">
                    Dashboard
                  </Link>
                  <Link to="/users" className="nav-link">
                    Users
                  </Link>
                  <Link to="/users/import" className="nav-link">
                    Import Residents
                  </Link>
                  <Link to="/audit-logs" className="nav-link">
                    Audit Trail
                  </Link>
                </>
              )}
              <Link to="/change-password" className="nav-link">
                Security
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="btn-signout"
                aria-label="Sign out of account"
              >
                Sign Out
              </button>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}
