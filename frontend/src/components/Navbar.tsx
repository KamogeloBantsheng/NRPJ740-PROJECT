/**
 * Application Navigation Bar (SCR-01 through SCR-13).
 */

import { Link, NavLink, useNavigate } from "react-router-dom";
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
        <Link to={homeHref} className="navbar-brand">
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

        {!isAuthenticated && (
          <p className="navbar-tagline">One record for every fault, from the first report to a verified repair.</p>
        )}

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
                  <NavLink to="/dashboard" end className="nav-link">Dashboard</NavLink>
                  <NavLink to="/requests" end className="nav-link">My Reports</NavLink>
                  <NavLink to="/requests/new" end className="nav-link">Report Fault</NavLink>
                </>
              )}
              {user.role === "SUPERVISOR" && (
                <>
                  <NavLink to="/dashboard" end className="nav-link">Dashboard</NavLink>
                  <NavLink to="/triage" end className="nav-link">Triage Queue</NavLink>
                  <NavLink to="/dispatch" end className="nav-link">Dispatch</NavLink>
                  <NavLink to="/verification" end className="nav-link">Verification</NavLink>
                </>
              )}
              {user.role === "RESIDENT" && (
                <>
                  <NavLink to="/requests" end className="nav-link">My Requests</NavLink>
                  <NavLink to="/requests/new" end className="nav-link">Report Fault</NavLink>
                </>
              )}
              {user.role === "TECHNICIAN" && (
                <NavLink to="/work" end className="nav-link">My Work</NavLink>
              )}
              {user.role === "ADMIN" && (
                <>
                  <NavLink to="/users" end className="nav-link">Users</NavLink>
                  <NavLink to="/users/import" end className="nav-link">Import Users</NavLink>
                  <NavLink to="/audit-logs" end className="nav-link">Audit Trail</NavLink>
                </>
              )}
              <NavLink to="/change-password" end className="nav-link">Security</NavLink>
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
