/**
 * SCR-02: Change Password Screen (Table 5.3, FR-02, BR-07, NFR-02).
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { authApi } from "../api/auth";
import { AppError } from "../api/client";

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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      </div>
    </main>
  );
}
