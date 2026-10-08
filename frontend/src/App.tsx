import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/useAuth";
import { Navbar } from "./components/Navbar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import {
  ForbiddenPage,
  NotFoundPage,
  RoleHomeView,
  UnauthorizedPage,
} from "./pages/ErrorPages";

const queryClient = new QueryClient();

function RootRedirect() {
  const { user, isAuthenticated, isLoading, getRoleHome } = useAuth();

  if (isLoading) {
    return (
      <div className="loading-container" role="status" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <p className="loading-text">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  return <Navigate to={getRoleHome(user.role)} replace />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <div className="app-shell">
            <Navbar />
            <div className="content-container">
              <Routes>
                <Route path="/" element={<RootRedirect />} />
                <Route path="/login" element={<LoginPage />} />

                {/* Password Management */}
                <Route
                  path="/change-password"
                  element={
                    <ProtectedRoute>
                      <ChangePasswordPage />
                    </ProtectedRoute>
                  }
                />

                {/* Role-Specific Workspaces (SCR-03 through SCR-13 placeholders) */}
                <Route
                  path="/requests"
                  element={
                    <ProtectedRoute allowedRoles={["RESIDENT"]}>
                      <RoleHomeView
                        title="My Maintenance Requests"
                        roleDescription="Residents report faults within Moroka Hall, view tracking status timelines, and respond to supervisor clarification queries."
                        nextSliceName="Slice 2: Report & Track (SCR-03, SCR-04)"
                      />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/triage"
                  element={
                    <ProtectedRoute allowedRoles={["SUPERVISOR"]}>
                      <RoleHomeView
                        title="Supervisor Triage & Dispatch Queue"
                        roleDescription="Supervisors evaluate incoming requests, assign priority, assign/reassign technicians, and verify completed repairs."
                        nextSliceName="Slice 3: Triage (SCR-06) & Slice 4: Assign (SCR-07)"
                      />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/work"
                  element={
                    <ProtectedRoute allowedRoles={["TECHNICIAN"]}>
                      <RoleHomeView
                        title="Technician Work Queue"
                        roleDescription="Technicians review assigned work orders without resident identities, start work, and record mandatory completion notes."
                        nextSliceName="Slice 5: Technician Work (SCR-09)"
                      />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute allowedRoles={["WARDEN", "SUPERVISOR"]}>
                      <RoleHomeView
                        title="Residence Oversight Dashboard"
                        roleDescription="Wardens and Supervisors monitor residence maintenance aggregates and status distributions read-only."
                        nextSliceName="Slice 8: Dashboard & Audit Review (SCR-10)"
                      />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/users"
                  element={
                    <ProtectedRoute allowedRoles={["ADMIN"]}>
                      <RoleHomeView
                        title="User Administration & CSV Import"
                        roleDescription="System administrators manage user accounts, assign roles, deactivate accounts, and execute all-or-nothing CSV imports."
                        nextSliceName="Slice 7: User Administration (SCR-11, SCR-12)"
                      />
                    </ProtectedRoute>
                  }
                />

                {/* Error Pages */}
                <Route path="/401" element={<UnauthorizedPage />} />
                <Route path="/403" element={<ForbiddenPage />} />
                <Route path="/404" element={<NotFoundPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </div>
          </div>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
