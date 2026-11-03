/**
 * SCR-02: Change Password Screen (Table 5.3, FR-02, BR-07, NFR-02).
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/useAuth";
import { authApi } from "../api/auth";
import { AppError } from "../api/client";
import type { MfaSetupResponse } from "../types/auth";

const passwordSchema = z
  .object({
    current_password: z.string().optional(),
    new_password: z
      .string()
      .min(10, "Password must be at least 10 characters long per security policy"),
    confirm_password: z.string().min(1, "Please confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "New password and confirmation do not match",
    path: ["confirm_password"],
  });

type PasswordFormData = z.infer<typeof passwordSchema>;

export function ChangePasswordPage() {
  const { user, getRoleHome } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 2FA Management State
  const [mfaSetupData, setMfaSetupData] = useState<MfaSetupResponse | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaBackupCodes, setMfaBackupCodes] = useState<string[] | null>(null);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaSuccess, setMfaSuccess] = useState<string | null>(null);
  const [isMfaLoading, setIsMfaLoading] = useState(false);
  const [showDisablePrompt, setShowDisablePrompt] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");

  const handleStartMfaSetup = async () => {
    try {
      setMfaError(null);
      setMfaSuccess(null);
      setIsMfaLoading(true);
      const data = await authApi.setupMfa();
      setMfaSetupData(data);
    } catch (err) {
      setMfaError(err instanceof AppError ? err.message : "Failed to initialize 2FA setup.");
    } finally {
      setIsMfaLoading(false);
    }
  };

  const handleConfirmEnableMfa = async () => {
    if (!mfaSetupData || !mfaCode.trim()) return;

    try {
      setMfaError(null);
      setMfaSuccess(null);
      setIsMfaLoading(true);
      const res = await authApi.enableMfa({
        setup_token: mfaSetupData.setup_token,
        code: mfaCode.trim(),
      });
      setMfaBackupCodes(res.backup_codes);
      setMfaSuccess("Two-factor authentication has been enabled successfully.");
      setMfaSetupData(null);
      setMfaCode("");
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    } catch (err) {
      setMfaError(err instanceof AppError ? err.message : "Invalid code. Check your clock and try again.");
    } finally {
      setIsMfaLoading(false);
    }
  };

  const handleDisableMfa = async () => {
    if (!disablePassword) return;

    try {
      setMfaError(null);
      setMfaSuccess(null);
      setIsMfaLoading(true);
      await authApi.disableMfa({ password: disablePassword });
      setMfaSuccess("Two-factor authentication has been disabled.");
      setShowDisablePrompt(false);
      setDisablePassword("");
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    } catch (err) {
      setMfaError(err instanceof AppError ? err.message : "Incorrect password. Could not disable 2FA.");
    } finally {
      setIsMfaLoading(false);
    }
  };

  const isForced = Boolean(user?.must_change_password);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const onSubmit = async (data: PasswordFormData) => {
    try {
      setErrorMessage(null);
      setSuccessMessage(null);
      setIsSubmitting(true);

      await authApi.changePassword({
        current_password: data.current_password || undefined,
        new_password: data.new_password,
      });

      setSuccessMessage("Your password has been changed successfully. Redirecting...");

      setTimeout(() => {
        if (user) {
          navigate(getRoleHome(user.role), { replace: true });
        } else {
          navigate("/login", { replace: true });
        }
      }, 1200);
    } catch (err) {
      if (err instanceof AppError) {
        if (err.fields) {
          if (err.fields.current_password) {
            setError("current_password", {
              type: "server",
              message: err.fields.current_password[0],
            });
          }
          if (err.fields.new_password) {
            setError("new_password", {
              type: "server",
              message: err.fields.new_password[0],
            });
          }
        }
        setErrorMessage(err.message || "Failed to update password.");
      } else {
        setErrorMessage("Network error: Unable to update password.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (user && !isForced) {
      navigate(getRoleHome(user.role));
    }
  };

  return (
    <main className="auth-page-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">
            {isForced ? "Set New Password Required" : "Change Account Password"}
          </h1>
          <p className="auth-subtitle">
            {isForced
              ? "You signed in with a temporary password and must create a permanent password to continue."
              : "Update your login credentials using Argon2id encryption."}
          </p>
        </div>

        {isForced && (
          <div className="alert alert-warning" role="alert">
            <span className="alert-icon" aria-hidden="true">&#9888;</span>
            <span className="alert-message">
              Mandatory Security Notice: Password must be at least 10 characters long.
            </span>
          </div>
        )}

        {errorMessage && (
          <div className="alert alert-error" role="alert" aria-live="assertive">
            <span className="alert-icon" aria-hidden="true">&times;</span>
            <span className="alert-message">{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="alert alert-success" role="status" aria-live="polite">
            <span className="alert-icon" aria-hidden="true">&check;</span>
            <span className="alert-message">{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="auth-form" noValidate>
          {!isForced && (
            <div className="form-group">
              <label htmlFor="current-pw-input" className="form-label">
                Current Password
              </label>
              <input
                id="current-pw-input"
                type="password"
                autoComplete="current-password"
                className={`form-input ${errors.current_password ? "input-error" : ""}`}
                placeholder="Enter current password"
                aria-invalid={Boolean(errors.current_password)}
                aria-describedby={errors.current_password ? "current-pw-error" : undefined}
                {...register("current_password")}
              />
              {errors.current_password && (
                <p id="current-pw-error" className="field-error" role="alert">
                  {errors.current_password.message}
                </p>
              )}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="new-pw-input" className="form-label">
              New Password (minimum 10 characters)
            </label>
            <input
              id="new-pw-input"
              type="password"
              autoComplete="new-password"
              className={`form-input ${errors.new_password ? "input-error" : ""}`}
              placeholder="Enter new password (10+ characters)"
              aria-invalid={Boolean(errors.new_password)}
              aria-describedby={errors.new_password ? "new-pw-error" : undefined}
              {...register("new_password")}
            />
            {errors.new_password && (
              <p id="new-pw-error" className="field-error" role="alert">
                {errors.new_password.message}
              </p>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="confirm-pw-input" className="form-label">
              Confirm New Password
            </label>
            <input
              id="confirm-pw-input"
              type="password"
              autoComplete="new-password"
              className={`form-input ${errors.confirm_password ? "input-error" : ""}`}
              placeholder="Confirm new password"
              aria-invalid={Boolean(errors.confirm_password)}
              aria-describedby={errors.confirm_password ? "confirm-pw-error" : undefined}
              {...register("confirm_password")}
            />
            {errors.confirm_password && (
              <p id="confirm-pw-error" className="field-error" role="alert">
                {errors.confirm_password.message}
              </p>
            )}
          </div>

            <div className="form-actions-row">
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary btn-block"
                aria-busy={isSubmitting}
              >
                {isSubmitting ? "Updating Password..." : "Set New Password"}
              </button>

              {!isForced && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="btn btn-secondary btn-block"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>

          {/* Two-Factor Authentication Section (only available once permanent password is active) */}
          {!isForced && (
            <div style={{ marginTop: "2.5rem", paddingTop: "2rem", borderTop: "1px solid var(--color-border, #e2e8f0)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <div>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, margin: 0, color: "var(--color-text-primary, #0f172a)" }}>
                    Two-Factor Authentication (2FA)
                  </h2>
                  <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.875rem", color: "var(--color-text-secondary, #64748b)" }}>
                    Add an extra layer of security using an authenticator app (TOTP).
                  </p>
                </div>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.375rem",
                    padding: "0.25rem 0.625rem",
                    borderRadius: "9999px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: user?.is_mfa_enabled ? "rgba(22, 101, 52, 0.1)" : "rgba(234, 88, 12, 0.1)",
                    color: user?.is_mfa_enabled ? "#15803d" : "#c2410c",
                  }}
                >
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "currentColor" }} />
                  {user?.is_mfa_enabled ? "Enabled" : "Not Enabled"}
                </span>
              </div>

              {mfaError && (
                <div className="alert alert-error" style={{ marginBottom: "1rem" }} role="alert">
                  <span className="alert-message">{mfaError}</span>
                </div>
              )}

              {mfaSuccess && (
                <div className="alert alert-success" style={{ marginBottom: "1rem" }} role="status">
                  <span className="alert-message">{mfaSuccess}</span>
                </div>
              )}

              {/* Step 3: Backup codes display after successful enablement */}
              {mfaBackupCodes && (
                <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.25rem", marginBottom: "1.5rem" }}>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem", color: "#b91c1c" }}>
                    Emergency Backup Codes
                  </h3>
                  <p style={{ margin: "0 0 1rem 0", fontSize: "0.875rem", color: "#475569" }}>
                    Save these 8 one-time backup codes in a secure location. Each code can be used once to access your account if you lose your phone.
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.5rem", fontFamily: "monospace", fontSize: "0.875rem", fontWeight: 700, background: "#ffffff", padding: "0.75rem", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                    {mfaBackupCodes.map((bc, idx) => (
                      <div key={idx} style={{ textAlign: "center", padding: "0.25rem" }}>{bc}</div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setMfaBackupCodes(null)}
                    className="btn btn-secondary btn-block"
                    style={{ marginTop: "1rem" }}
                  >
                    I Have Saved These Backup Codes
                  </button>
                </div>
              )}

              {/* Step 2: Secret key & code confirmation during setup */}
              {mfaSetupData && !mfaBackupCodes && (
                <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.25rem", marginBottom: "1.5rem" }}>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem", color: "#0f172a" }}>
                    Scan or Enter Key in Authenticator App
                  </h3>
                  <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.875rem", color: "#475569" }}>
                    Enter this secret key in your authenticator app (Google Authenticator, Microsoft Authenticator, etc.):
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
                    <code style={{ background: "#ffffff", padding: "0.5rem 0.75rem", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "1rem", letterSpacing: "0.1em", fontWeight: 700, flex: 1, textAlign: "center" }}>
                      {mfaSetupData.secret}
                    </code>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText(mfaSetupData.secret)}
                      className="btn btn-secondary"
                      style={{ padding: "0.5rem 0.75rem", fontSize: "0.8125rem" }}
                    >
                      Copy
                    </button>
                  </div>

                  <div className="form-group" style={{ marginBottom: "1rem" }}>
                    <label htmlFor="confirm-mfa-code" className="form-label">
                      Enter 6-Digit Code from App
                    </label>
                    <input
                      id="confirm-mfa-code"
                      type="text"
                      className="form-input"
                      placeholder="e.g. 123456"
                      maxLength={6}
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button
                      type="button"
                      disabled={isMfaLoading || mfaCode.trim().length !== 6}
                      onClick={handleConfirmEnableMfa}
                      className="btn btn-primary"
                      style={{ flex: 1 }}
                    >
                      {isMfaLoading ? "Activating..." : "Confirm & Activate 2FA"}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setMfaSetupData(null); setMfaCode(""); }}
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Step 1: Initial state (Enable or Disable buttons) */}
              {!mfaSetupData && !mfaBackupCodes && (
                <div>
                  {user?.is_mfa_enabled ? (
                    <div>
                      {showDisablePrompt ? (
                        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", padding: "1.25rem" }}>
                          <h4 style={{ margin: "0 0 0.5rem 0", color: "#991b1b" }}>Disable Two-Factor Authentication</h4>
                          <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.875rem", color: "#7f1d1d" }}>
                            Confirm your current password to turn off 2FA protection:
                          </p>
                          <input
                            type="password"
                            placeholder="Enter current password"
                            className="form-input"
                            value={disablePassword}
                            onChange={(e) => setDisablePassword(e.target.value)}
                            style={{ marginBottom: "0.75rem" }}
                          />
                          <div style={{ display: "flex", gap: "0.75rem" }}>
                            <button
                              type="button"
                              disabled={isMfaLoading || !disablePassword}
                              onClick={handleDisableMfa}
                              className="btn btn-primary"
                              style={{ background: "#dc2626", borderColor: "#dc2626" }}
                            >
                              {isMfaLoading ? "Disabling..." : "Confirm Deactivation"}
                            </button>
                            <button
                              type="button"
                              onClick={() => { setShowDisablePrompt(false); setDisablePassword(""); }}
                              className="btn btn-secondary"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setShowDisablePrompt(true)}
                          className="btn btn-secondary"
                          style={{ color: "#b91c1c", borderColor: "#fecaca" }}
                        >
                          Disable Two-Factor Authentication
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      disabled={isMfaLoading}
                      onClick={handleStartMfaSetup}
                      className="btn btn-secondary"
                    >
                      {isMfaLoading ? "Loading..." : "Set Up Two-Factor Authentication"}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    );
  }
