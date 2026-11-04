/**
 * What happens when the server says a signed-in user's session has ended (Section 6.2: 401).
 */

import type { QueryClient } from "@tanstack/react-query";
import { AppError } from "../api/client";

/** Send a user who was signed in back to sign-in with the session-expired notice. */
export function expireSession(queryClient: QueryClient): void {
  if (!queryClient.getQueryData(["auth", "me"])) return; // A failed sign-in is not an expired session
  queryClient.clear();
  window.location.assign("/login?expired=1");
}

export function handleApiError(error: unknown, queryClient: QueryClient): void {
  if (error instanceof AppError && error.statusCode === 401) {
    expireSession(queryClient);
  }
}
