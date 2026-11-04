/**
 * Native fetch API client with CSRF protection and standardized error mapping.
 * Plain browser fetch, no Axios.
 */

import type { ApiErrorPayload } from "../types/auth";

export const NETWORK_FAILED_EVENT = "app:network-failed";
export const NETWORK_RESTORED_EVENT = "app:network-restored";

export class AppError extends Error {
  code: string;
  fields?: Record<string, string[]>;
  current_status?: string;
  statusCode: number;

  constructor(statusCode: number, payload: ApiErrorPayload) {
    super(payload.message || "An error occurred.");
    this.name = "AppError";
    this.statusCode = statusCode;
    this.code = payload.code || "UNKNOWN_ERROR";
    this.fields = payload.fields;
    this.current_status = payload.current_status;
  }
}

export function getCsrfToken(): string | null {
  const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export async function ensureCsrfToken(): Promise<string | null> {
  let token = getCsrfToken();
  if (!token) {
    try {
      await fetch("/api/auth/csrf", { credentials: "same-origin" });
      token = getCsrfToken();
    } catch {
      // Best-effort CSRF retrieval
    }
  }
  return token;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Include CSRF token on mutation methods
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    let csrf = getCsrfToken();
    if (!csrf) {
      csrf = await ensureCsrfToken();
    }
    if (csrf) {
      headers.set("X-CSRFToken", csrf);
    }
  }

  let response: Response;
  try {
    response = await fetch(endpoint, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch {
    window.dispatchEvent(new Event(NETWORK_FAILED_EVENT));
    throw new AppError(0, {
      code: "NETWORK_ERROR",
      message: "The server cannot be reached. Check your connection and try again.",
    });
  }
  window.dispatchEvent(new Event(NETWORK_RESTORED_EVENT));

  if (!response.ok) {
    let errorPayload: ApiErrorPayload;
    try {
      errorPayload = await response.json();
    } catch {
      errorPayload = {
        code: response.status === 401 ? "UNAUTHENTICATED" : "HTTP_ERROR",
        message: response.statusText || "Request failed",
      };
    }
    throw new AppError(response.status, errorPayload);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
