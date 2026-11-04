import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, AppError, NETWORK_FAILED_EVENT } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("apiClient", () => {
  it("turns the standard error body into an AppError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: "CONFLICT", message: "Changed", current_status: "APPROVED" }), { status: 409 }),
    ));

    const error: AppError = await apiClient<never>("/api/requests/1/").catch((caught: AppError) => caught);

    expect(error).toBeInstanceOf(AppError);
    expect(error.statusCode).toBe(409);
    expect(error.current_status).toBe("APPROVED");
  });

  it("reports a failed connection as a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const listener = vi.fn();
    window.addEventListener(NETWORK_FAILED_EVENT, listener);

    const error: AppError = await apiClient<never>("/api/me").catch((caught: AppError) => caught);

    expect(error.code).toBe("NETWORK_ERROR");
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(NETWORK_FAILED_EVENT, listener);
  });
});
