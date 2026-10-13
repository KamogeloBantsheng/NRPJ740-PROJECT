import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/useAuth";
import { Navbar } from "./components/Navbar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { ResidentRequestsPage } from "./pages/ResidentRequestsPage";
import { SubmitRequestPage } from "./pages/SubmitRequestPage";
import { RequestDetailPage } from "./pages/RequestDetailPage";
import { SupervisorTriagePage } from "./pages/SupervisorTriagePage";
import { DispatchPage } from "./pages/DispatchPage";
import { TechnicianWorkPage } from "./pages/TechnicianWorkPage";
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

                {/* Slice 2 Resident Workflow Screens (SCR-03, SCR-04, SCR-05) */}
                <Route
                  path="/requests"
                  element={
                    <ProtectedRoute allowedRoles={["RESIDENT"]}>
                      <ResidentRequestsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/requests/new"
                  element={
                    <ProtectedRoute allowedRoles={["RESIDENT"]}>
                      <SubmitRequestPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/requests/:id"
                  element={
                    <ProtectedRoute allowedRoles={["RESIDENT", "SUPERVISOR", "WARDEN", "ADMIN"]}>
                      <RequestDetailPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/triage"
                  element={
                    <ProtectedRoute allowedRoles={["SUPERVISOR"]}>
                      <SupervisorTriagePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dispatch"
                  element={
                    <ProtectedRoute allowedRoles={["SUPERVISOR"]}>
                      <DispatchPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/work"
                  element={
                    <ProtectedRoute allowedRoles={["TECHNICIAN"]}>
                      <TechnicianWorkPage />
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
