/**
 * SCR-01: Sign In Screen (Table 5.3, FR-01, NFR-02, NFR-07).
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { AppError } from "../api/client";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { login, verifyMfa, getRoleHome, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mfaData, setMfaData] = useState<{ mfa_token: string; email: string } | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  // If already logged in, redirect to home
  if (isAuthenticated && user) {
    if (user.must_change_password) {
      navigate("/change-password", { replace: true });
    } else {
      const fromPath = (location.state as { from?: { pathname: string } })?.from?.pathname;
      navigate(fromPath || getRoleHome(user.role), { replace: true });
    }
  }

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      setErrorMessage(null);
      setIsSubmitting(true);
      const result = await login(data);

      if ("requires_mfa" in result && result.requires_mfa) {
        setMfaData({ mfa_token: result.mfa_token, email: result.email });
        return;
      }

      if (result.must_change_password) {
        navigate("/change-password", { replace: true });
      } else {
        const fromPath = (location.state as { from?: { pathname: string } })?.from?.pathname;
        navigate(fromPath || getRoleHome(result.role), { replace: true });
      }
    } catch (err) {
      if (err instanceof AppError) {
        if (err.statusCode === 429) {
          setErrorMessage(err.message || "Too many failed attempts. Please wait before trying again.");
        } else {
          setErrorMessage(err.message || "Invalid email or password.");
        }
      } else {
        setErrorMessage("Network error: Unable to reach the server. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaData || !mfaCode.trim()) return;

    try {
      setErrorMessage(null);
      setIsSubmitting(true);
      const authenticatedUser = await verifyMfa({
        mfa_token: mfaData.mfa_token,
        code: mfaCode.trim(),
      });

      if (authenticatedUser.must_change_password) {
        navigate("/change-password", { replace: true });
      } else {
        const fromPath = (location.state as { from?: { pathname: string } })?.from?.pathname;
        navigate(fromPath || getRoleHome(authenticatedUser.role), { replace: true });
      }
    } catch (err) {
      if (err instanceof AppError) {
        setErrorMessage(err.message || "Invalid authenticator code or backup code.");
      } else {
        setErrorMessage("Failed to verify code. Please check your network and try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-page-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-tag-pill">
            <span className="auth-tag-dot" aria-hidden="true" />
            SPU RESIDENCE OPERATIONS
          </div>
          <h1 className="auth-title">Moroka Hall Maintenance</h1>
          <p className="auth-subtitle">Sol Plaatje University &bull; Sign in with your university account</p>
        </div>

        {errorMessage && (
          <div className="alert alert-error" role="alert" aria-live="assertive">
            <span className="alert-icon" aria-hidden="true">&times;</span>
            <span className="alert-message">{errorMessage}</span>
          </div>
        )}

        {mfaData ? (
          <form onSubmit={handleMfaSubmit} className="auth-form" noValidate>
            <div style={{ marginBottom: "1rem" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.35rem 0.75rem", borderRadius: "9999px", background: "rgba(185, 28, 28, 0.1)", color: "#b91c1c", fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                <span>Two-Factor Authentication</span>
              </div>
              <p style={{ fontSize: "0.875rem", color: "var(--color-text-secondary, #64748b)" }}>
                Enter the 6-digit verification code from your authenticator app for <strong>{mfaData.email}</strong>, or enter an 8-character backup code.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="mfa-code-input" className="form-label">
                Security Code / Backup Code
              </label>
              <input
                id="mfa-code-input"
                type="text"
                autoComplete="one-time-code"
                autoFocus
                className="form-input"
                placeholder="e.g. 123456 or A1B2C3D4"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                maxLength={10}
                required
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !mfaCode.trim()}
              className="btn btn-primary btn-block"
              aria-busy={isSubmitting}
            >
              {isSubmitting ? "Verifying..." : "Verify Code"}
            </button>

            <button
              type="button"
              onClick={() => {
                setMfaData(null);
                setMfaCode("");
                setErrorMessage(null);
              }}
              style={{
                marginTop: "0.75rem",
                background: "transparent",
                border: "none",
                color: "var(--color-text-secondary, #64748b)",
                fontSize: "0.875rem",
                cursor: "pointer",
                width: "100%",
                textAlign: "center",
                textDecoration: "underline",
              }}
            >
              Back to email sign-in
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="auth-form" noValidate>
            <div className="form-group">
              <label htmlFor="email-input" className="form-label">
                University Email Address
              </label>
              <input
                id="email-input"
                type="email"
                autoComplete="email"
                autoFocus
                className={`form-input ${errors.email ? "input-error" : ""}`}
                placeholder="e.g. 202311455@spu.ac.za"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? "email-error" : undefined}
                {...register("email")}
              />
              {errors.email && (
                <p id="email-error" className="field-error" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="password-input" className="form-label">
                Password
              </label>
              <input
                id="password-input"
                type="password"
                autoComplete="current-password"
                className={`form-input ${errors.password ? "input-error" : ""}`}
                placeholder="Enter your password"
                aria-invalid={Boolean(errors.password)}
                aria-describedby={errors.password ? "password-error" : undefined}
                {...register("password")}
              />
              {errors.password && (
                <p id="password-error" className="field-error" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn btn-primary btn-block"
              aria-busy={isSubmitting}
            >
              {isSubmitting ? "Signing in..." : "Sign In"}
            </button>
          </form>
        )}

        <div className="auth-footer-notes">
          <p>
            Residents, Supervisors, Technicians, Wardens, and Administrators sign in with their university accounts.
          </p>
        </div>
      </div>
    </main>
  );
}
