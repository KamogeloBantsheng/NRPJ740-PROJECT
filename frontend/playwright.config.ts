import { defineConfig } from "@playwright/test";

// Runs against the Docker Compose stack, which must already be started.
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    channel: process.env.E2E_CHANNEL,
    screenshot: "only-on-failure",
  },
});
