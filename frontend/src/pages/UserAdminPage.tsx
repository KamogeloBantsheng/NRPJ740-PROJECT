/**
 * SCR-11: User Administration Screen (FR-03, BR-07, TC-06, SCR-11).
 * Enables System Administrators to manage user accounts, assign roles,
 * create users with temporary passwords, reset passwords, and toggle active status
 * with enforcement of BR-07 account guards.
 */

import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { usersApi, type UserFilters } from "../api/users";
import { AppError } from "../api/client";
import type {
  AdminUserItem,
  CreateUserPayload,
  Role,
  UpdateUserPayload,
} from "../types/users";

export function UserAdminPage() {
  const queryClient = useQueryClient();

  // Search & Filter state
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>(""); // "", "true", "false"

  // Action / Feedback state
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUserItem | null>(null);
  const [deactivatingUser, setDeactivatingUser] = useState<AdminUserItem | null>(null);
  const [resettingUser, setResettingUser] = useState<AdminUserItem | null>(null);
  const [tempCredentialsModal, setTempCredentialsModal] = useState<{
    title: string;
    email: string;
    fullName: string;
    temporaryPassword: string;
    isReset?: boolean;
  } | null>(null);
  const [copiedNotice, setCopiedNotice] = useState(false);

  // Filters passed to query
  const queryFilters: UserFilters = useMemo(() => {
    const f: UserFilters = {};
    if (searchTerm.trim()) f.search = searchTerm.trim();
    if (selectedRole) f.role = selectedRole;
    if (selectedStatus === "true") f.is_active = true;
    if (selectedStatus === "false") f.is_active = false;
    return f;
  }, [searchTerm, selectedRole, selectedStatus]);

  // Query: Users list
  const {
    data: users = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["admin-users", queryFilters],
    queryFn: () => usersApi.getUsers(queryFilters),
  });

  // Mutation: Create user
  const createUserMutation = useMutation({
    mutationFn: (payload: CreateUserPayload) => usersApi.createUser(payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setIsCreateModalOpen(false);
      setActionSuccess(`User ${data.email} created successfully.`);
      setActionError(null);
      // Display temporary credentials modal
      setTempCredentialsModal({
        title: "Account Created Successfully",
        email: data.email,
        fullName: data.full_name,
        temporaryPassword: data.temporary_password,
        isReset: false,
      });
    },
    onError: (err) => {
      if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while creating the user.");
      }
    },
  });

  // Mutation: Update user (Role, active, name)
  const updateUserMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UpdateUserPayload }) =>
      usersApi.updateUser(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setEditingUser(null);
      setDeactivatingUser(null);
      setActionSuccess(`User ${data.email} updated successfully.`);
      setActionError(null);
    },
    onError: (err) => {
      if (err instanceof AppError && err.statusCode === 409) {
        setActionError(`Guard Violation (BR-07): ${err.message}`);
      } else if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while updating the user.");
      }
    },
  });

  // Mutation: Reset password
  const resetPasswordMutation = useMutation({
    mutationFn: (id: number) => usersApi.resetPassword(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setResettingUser(null);
      setActionSuccess(`Password reset successfully for ${data.email}.`);
      setActionError(null);
      setTempCredentialsModal({
        title: "Password Reset Completed",
        email: data.email,
        fullName: users.find((u) => u.id === data.id)?.full_name || data.email,
        temporaryPassword: data.temporary_password,
        isReset: true,
      });
    },
    onError: (err) => {
      if (err instanceof AppError) {
        setActionError(err.message);
      } else {
        setActionError("An unexpected error occurred while resetting password.");
      }
    },
  });

  const handleCopyPassword = (pwd: string) => {
    navigator.clipboard.writeText(pwd).then(() => {
      setCopiedNotice(true);
      setTimeout(() => setCopiedNotice(false), 2500);
    });
  };

  return (
    <main className="user-admin-page-container triage-page-container" id="main-content">
      {/* Page Header */}
      <div className="page-header">
        <div className="header-text-group">
          <div className="header-breadcrumbs">
            <span className="crumb-app">Administration</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-page">Users & Access</span>
          </div>
          <h1 className="page-title">User Administration</h1>
          <p className="page-subtitle">
            Manage system users, assign roles, enforce account status guards (BR-07), and reset passwords.
          </p>
        </div>

        <div className="page-header-actions">
          <Link to="/users/import" className="btn btn-secondary">
            <span className="btn-icon">📁</span>
            Import Residents (CSV)
          </Link>
          <button
            type="button"
            onClick={() => {
              setActionError(null);
              setIsCreateModalOpen(true);
            }}
            className="btn btn-primary"
            id="create-user-btn"
          >
            <span className="btn-icon">+</span>
            Create User
          </button>
        </div>
      </div>

      {/* Global Banners */}
      {actionSuccess && (
        <div className="alert-banner alert-success" role="status" aria-live="polite">
          <span className="alert-icon">✓</span>
          <div className="alert-text">{actionSuccess}</div>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            className="alert-dismiss-btn"
            aria-label="Dismiss alert"
          >
            ×
          </button>
        </div>
      )}

      {actionError && (
        <div className="alert-banner alert-danger" role="alert">
          <span className="alert-icon">⚠</span>
          <div className="alert-text">{actionError}</div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="alert-dismiss-btn"
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Control Card: Filters & Search */}
      <section className="card triage-control-card" aria-label="User search and filters">
        <div className="control-filters-grid">
          {/* Search Box */}
          <div className="filter-group">
            <label htmlFor="user-search" className="filter-label">
              Search Users
            </label>
            <input
              id="user-search"
              type="search"
              placeholder="Filter by name, email, or student #..."
              className="filter-select search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* Role Filter */}
          <div className="filter-group">
            <label htmlFor="role-filter" className="filter-label">
              Role
            </label>
            <select
              id="role-filter"
              className="filter-select"
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
            >
              <option value="">All Roles</option>
              <option value="RESIDENT">Resident</option>
              <option value="TECHNICIAN">Technician</option>
              <option value="SUPERVISOR">Supervisor</option>
              <option value="WARDEN">Warden</option>
              <option value="ADMIN">Administrator</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="filter-group">
            <label htmlFor="status-filter" className="filter-label">
              Status
            </label>
            <select
              id="status-filter"
              className="filter-select"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Deactivated Only</option>
            </select>
          </div>

          {/* Refresh Action */}
          <div className="filter-group filter-actions-group">
            <span className="filter-label">&nbsp;</span>
            <button
              type="button"
              onClick={() => refetch()}
              className="btn btn-secondary btn-refresh"
              title="Refresh users list"
            >
              ↻ Refresh
            </button>
          </div>
        </div>
      </section>

      {/* Users Table Card */}
      <div className="card triage-table-card">
        <div className="table-header-row">
          <div className="table-title-group">
            <h2 className="table-title">System Users</h2>
            <span className="queue-count-badge">
              {users.length} {users.length === 1 ? "user" : "users"}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="loading-state" role="status" aria-live="polite">
            <div className="spinner" aria-hidden="true" />
            <p className="loading-text">Loading user directory...</p>
          </div>
        ) : isError ? (
          <div className="error-state" role="alert">
            <p className="error-title">Failed to load user directory.</p>
            <p className="error-subtitle">
              Unable to reach the backend service. Check your connection or retry.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="btn btn-secondary"
            >
              Retry
            </button>
          </div>
        ) : users.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">👥</div>
            <p className="empty-title">No users found</p>
            <p className="empty-subtitle">
              No accounts match the selected search criteria or filters.
            </p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="triage-table" aria-label="System Users Directory">
              <thead>
                <tr>
                  <th scope="col">User</th>
                  <th scope="col">Role</th>
                  <th scope="col">Student / Residence</th>
                  <th scope="col">Status</th>
                  <th scope="col">Active Work</th>
                  <th scope="col">Created</th>
                  <th scope="col" className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className={!u.is_active ? "row-deactivated" : ""}>
                    {/* User Info */}
                    <td>
                      <div className="user-table-cell">
                        <span className="user-name-cell">{u.full_name}</span>
                        <span className="user-email-cell">{u.email}</span>
                      </div>
                    </td>

                    {/* Role */}
                    <td>
                      <span className={`role-badge role-${u.role.toLowerCase()}`}>
                        {u.role}
                      </span>
                    </td>

                    {/* Student Number or Residence */}
                    <td>
                      {u.student_number ? (
                        <span className="mono-code">{u.student_number}</span>
                      ) : u.residence_name ? (
                        <span className="residence-cell">{u.residence_name}</span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Status */}
                    <td>
                      {u.is_active ? (
                        <span className="badge badge-success-subtle">Active</span>
                      ) : (
                        <span className="badge badge-danger-subtle">Deactivated</span>
                      )}
                    </td>

                    {/* Active Work Orders */}
                    <td>
                      {u.role === "TECHNICIAN" ? (
                        u.active_work_orders_count > 0 ? (
                          <span
                            className="badge badge-warning-subtle"
                            title={`${u.active_work_orders_count} open work orders assigned`}
                          >
                            {u.active_work_orders_count} active
                          </span>
                        ) : (
                          <span className="badge badge-neutral-subtle">0 active</span>
                        )
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Created At */}
                    <td className="text-muted font-sm">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>

                    {/* Actions */}
                    <td className="text-right">
                      <div className="action-buttons-cell">
                        {/* Edit Role Button */}
                        <button
                          type="button"
                          onClick={() => {
                            setActionError(null);
                            setEditingUser(u);
                          }}
                          className="btn btn-sm btn-secondary"
                          title="Change user role"
                        >
                          Role
                        </button>

                        {/* Reset Password Button */}
                        <button
                          type="button"
                          onClick={() => {
                            setActionError(null);
                            setResettingUser(u);
                          }}
                          className="btn btn-sm btn-secondary"
                          title="Reset temporary password"
                        >
                          Reset Pwd
                        </button>

                        {/* Deactivate / Reactivate Button */}
                        {u.is_active ? (
                          <button
                            type="button"
                            onClick={() => {
                              setActionError(null);
                              setDeactivatingUser(u);
                            }}
                            className="btn btn-sm btn-danger-outline"
                            title="Deactivate account"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setActionError(null);
                              updateUserMutation.mutate({
                                id: u.id,
                                payload: { is_active: true },
                              });
                            }}
                            className="btn btn-sm btn-success-outline"
                            title="Reactivate account"
                          >
                            Reactivate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal 1: Create User Modal */}
      {isCreateModalOpen && (
        <CreateUserModal
          onClose={() => setIsCreateModalOpen(false)}
          onSubmit={(payload) => createUserMutation.mutate(payload)}
          isSubmitting={createUserMutation.isPending}
          errorMessage={actionError}
        />
      )}

      {/* Modal 2: Edit Role / User Modal */}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSubmit={(payload) =>
            updateUserMutation.mutate({ id: editingUser.id, payload })
          }
          isSubmitting={updateUserMutation.isPending}
          errorMessage={actionError}
        />
      )}

      {/* Modal 3: Deactivate Confirmation Modal */}
      {deactivatingUser && (
        <DeactivateConfirmModal
          user={deactivatingUser}
          onClose={() => setDeactivatingUser(null)}
          onConfirm={() =>
            updateUserMutation.mutate({
              id: deactivatingUser.id,
              payload: { is_active: false },
            })
          }
          isSubmitting={updateUserMutation.isPending}
          errorMessage={actionError}
        />
      )}

      {/* Modal 4: Reset Password Confirmation Modal */}
      {resettingUser && (
        <ResetPasswordConfirmModal
          user={resettingUser}
          onClose={() => setResettingUser(null)}
          onConfirm={() => resetPasswordMutation.mutate(resettingUser.id)}
          isSubmitting={resetPasswordMutation.isPending}
          errorMessage={actionError}
        />
      )}

      {/* Modal 5: Temporary Credentials Display Modal */}
      {tempCredentialsModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="creds-modal-title">
          <div className="modal-content modal-dialog-sm">
            <div className="modal-header">
              <h2 id="creds-modal-title" className="modal-title">
                {tempCredentialsModal.title}
              </h2>
              <button
                type="button"
                onClick={() => setTempCredentialsModal(null)}
                className="modal-close-btn"
                aria-label="Close credentials dialog"
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="alert-banner alert-warning-subtle" style={{ margin: 0 }}>
                <span className="alert-icon">🔒</span>
                <div className="alert-text">
                  <strong>One-Time Temporary Password:</strong> The user is required to change this password on initial login (NFR-02). Securely share these credentials now.
                </div>
              </div>

              <div className="modal-context-box">
                <div>
                  <strong>User:</strong> {tempCredentialsModal.fullName}
                </div>
                <div>
                  <strong>Email:</strong> {tempCredentialsModal.email}
                </div>
              </div>

              <div className="credential-display-group">
                <label className="filter-label" htmlFor="temp-pwd-input">
                  Generated Temporary Password:
                </label>
                <div className="credential-input-row">
                  <input
                    id="temp-pwd-input"
                    type="text"
                    readOnly
                    value={tempCredentialsModal.temporaryPassword}
                    className="credential-password-field"
                  />
                  <button
                    type="button"
                    onClick={() => handleCopyPassword(tempCredentialsModal.temporaryPassword)}
                    className="btn btn-secondary btn-copy"
                    id="copy-pwd-btn"
                  >
                    {copiedNotice ? "Copied! ✓" : "Copy"}
                  </button>
                </div>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  onClick={() => setTempCredentialsModal(null)}
                  className="btn btn-primary"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

// -----------------------------------------------------------------------------
// Sub-components: Modals
// -----------------------------------------------------------------------------

interface CreateUserModalProps {
  onClose: () => void;
  onSubmit: (payload: CreateUserPayload) => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

function CreateUserModal({
  onClose,
  onSubmit,
  isSubmitting,
  errorMessage,
}: CreateUserModalProps) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("RESIDENT");
  const [studentNumber, setStudentNumber] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!email.trim() || !email.includes("@")) {
      setLocalError("A valid email address is required.");
      return;
    }
    if (!fullName.trim() || fullName.trim().length < 2) {
      setLocalError("Full name must be at least 2 characters.");
      return;
    }
    if (role === "RESIDENT" && !studentNumber.trim()) {
      setLocalError("Student number is required for Resident accounts.");
      return;
    }

    onSubmit({
      email: email.trim().toLowerCase(),
      full_name: fullName.trim(),
      role,
      student_number: role === "RESIDENT" ? studentNumber.trim() : undefined,
    });
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="create-modal-title">
      <div className="modal-content modal-dialog-md">
        <div className="modal-header">
          <h2 id="create-modal-title" className="modal-title">
            Create System User
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="modal-close-btn"
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {(errorMessage || localError) && (
            <div className="alert-banner alert-danger" role="alert">
              <span className="alert-icon">⚠</span>
              <div className="alert-text">{localError || errorMessage}</div>
            </div>
          )}

          <div className="filter-group">
            <label htmlFor="create-email" className="filter-label">
              Email Address <span className="text-danger">*</span>
            </label>
            <input
              id="create-email"
              type="email"
              required
              placeholder="e.g. resident@spu.ac.za"
              className="filter-select"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label htmlFor="create-name" className="filter-label">
              Full Name <span className="text-danger">*</span>
            </label>
            <input
              id="create-name"
              type="text"
              required
              placeholder="e.g. Lerato Khumalo"
              className="filter-select"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label htmlFor="create-role" className="filter-label">
              Assigned Role <span className="text-danger">*</span>
            </label>
            <select
              id="create-role"
              className="filter-select"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              <option value="RESIDENT">Resident (Can report and track faults)</option>
              <option value="TECHNICIAN">Technician (Fulfills maintenance work orders)</option>
              <option value="SUPERVISOR">Supervisor (Triages, dispatches, verifies)</option>
              <option value="WARDEN">Warden (Residence oversight dashboard)</option>
              <option value="ADMIN">Administrator (Full user and system management)</option>
            </select>
          </div>

          {role === "RESIDENT" && (
            <div className="filter-group">
              <label htmlFor="create-student-number" className="filter-label">
                Student Number <span className="text-danger">*</span>
              </label>
              <input
                id="create-student-number"
                type="text"
                required
                placeholder="e.g. ST2024001"
                className="filter-select"
                value={studentNumber}
                onChange={(e) => setStudentNumber(e.target.value)}
              />
            </div>
          )}

          <p className="modal-info-text">
            A secure temporary password will be generated automatically. The user will be required to choose a new password upon first login (NFR-02).
          </p>

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              id="submit-create-user-btn"
            >
              {isSubmitting ? "Creating..." : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface EditUserModalProps {
  user: AdminUserItem;
  onClose: () => void;
  onSubmit: (payload: UpdateUserPayload) => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

function EditUserModal({
  user,
  onClose,
  onSubmit,
  isSubmitting,
  errorMessage,
}: EditUserModalProps) {
  const [role, setRole] = useState<Role>(user.role);
  const [fullName, setFullName] = useState(user.full_name);
  const [studentNumber, setStudentNumber] = useState(user.student_number || "");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (role === "RESIDENT" && !studentNumber.trim()) {
      setLocalError("Student number is required for Resident role.");
      return;
    }

    onSubmit({
      role,
      full_name: fullName.trim(),
      student_number: role === "RESIDENT" ? studentNumber.trim() : undefined,
    });
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title">
      <div className="modal-content modal-dialog-md">
        <div className="modal-header">
          <h2 id="edit-modal-title" className="modal-title">
            Edit User Role & Profile
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="modal-close-btn"
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {(errorMessage || localError) && (
            <div className="alert-banner alert-danger" role="alert">
              <span className="alert-icon">⚠</span>
              <div className="alert-text">{localError || errorMessage}</div>
            </div>
          )}

          <div className="modal-context-box">
            <div><strong>Email:</strong> {user.email}</div>
            <div><strong>Current Role:</strong> {user.role}</div>
            {user.role === "TECHNICIAN" && user.active_work_orders_count > 0 && (
              <div className="text-warning">
                ⚠ Technician currently has {user.active_work_orders_count} active work orders. Role changes are blocked until orders are closed or reassigned.
              </div>
            )}
          </div>

          <div className="filter-group">
            <label htmlFor="edit-name" className="filter-label">
              Full Name
            </label>
            <input
              id="edit-name"
              type="text"
              required
              className="filter-select"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label htmlFor="edit-role" className="filter-label">
              New Role
            </label>
            <select
              id="edit-role"
              className="filter-select"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              <option value="RESIDENT">Resident</option>
              <option value="TECHNICIAN">Technician</option>
              <option value="SUPERVISOR">Supervisor</option>
              <option value="WARDEN">Warden</option>
              <option value="ADMIN">Administrator</option>
            </select>
          </div>

          {role === "RESIDENT" && (
            <div className="filter-group">
              <label htmlFor="edit-student-number" className="filter-label">
                Student Number <span className="text-danger">*</span>
              </label>
              <input
                id="edit-student-number"
                type="text"
                required
                className="filter-select"
                value={studentNumber}
                onChange={(e) => setStudentNumber(e.target.value)}
              />
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              id="submit-edit-role-btn"
            >
              {isSubmitting ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface DeactivateConfirmModalProps {
  user: AdminUserItem;
  onClose: () => void;
  onConfirm: () => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

function DeactivateConfirmModal({
  user,
  onClose,
  onConfirm,
  isSubmitting,
  errorMessage,
}: DeactivateConfirmModalProps) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="deact-modal-title">
      <div className="modal-content modal-dialog-sm">
        <div className="modal-header">
          <h2 id="deact-modal-title" className="modal-title">
            Deactivate User Account
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="modal-close-btn"
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {errorMessage && (
            <div className="alert-banner alert-danger" role="alert">
              <span className="alert-icon">⚠</span>
              <div className="alert-text">{errorMessage}</div>
            </div>
          )}

          <div className="modal-context-box">
            <div><strong>User:</strong> {user.full_name}</div>
            <div><strong>Email:</strong> {user.email}</div>
            <div><strong>Role:</strong> {user.role}</div>
          </div>

          <p className="modal-info-text text-danger">
            <strong>Warning (BR-07):</strong> Deactivating this user will terminate all their active sessions immediately. If this is the last active Administrator or a Technician with open work orders, this action will be strictly rejected.
          </p>

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="btn btn-danger"
              disabled={isSubmitting}
              id="confirm-deactivate-btn"
            >
              {isSubmitting ? "Deactivating..." : "Deactivate Account"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ResetPasswordConfirmModalProps {
  user: AdminUserItem;
  onClose: () => void;
  onConfirm: () => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

function ResetPasswordConfirmModal({
  user,
  onClose,
  onConfirm,
  isSubmitting,
  errorMessage,
}: ResetPasswordConfirmModalProps) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="reset-modal-title">
      <div className="modal-content modal-dialog-sm">
        <div className="modal-header">
          <h2 id="reset-modal-title" className="modal-title">
            Reset User Password
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="modal-close-btn"
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {errorMessage && (
            <div className="alert-banner alert-danger" role="alert">
              <span className="alert-icon">⚠</span>
              <div className="alert-text">{errorMessage}</div>
            </div>
          )}

          <div className="modal-context-box">
            <div><strong>User:</strong> {user.full_name}</div>
            <div><strong>Email:</strong> {user.email}</div>
            <div><strong>Role:</strong> {user.role}</div>
          </div>

          <p className="modal-info-text">
            Resetting the password will terminate all active sessions for this account, generate a new high-entropy temporary password, and flag the account to require a password change on next login.
          </p>

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="btn btn-primary"
              disabled={isSubmitting}
              id="confirm-reset-pwd-btn"
            >
              {isSubmitting ? "Resetting..." : "Reset Password"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
