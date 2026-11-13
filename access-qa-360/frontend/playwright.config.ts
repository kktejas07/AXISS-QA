import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests for the whole app: `npm run e2e`.
 * They start the real API (on a throwaway SQLite database) and a production build of the web app.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://localhost:5183", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: "./e2e/serve-backend.sh", url: "http://localhost:8010/health", reuseExistingServer: !process.env.CI, timeout: 60_000 },
    {
      command: "VITE_API_URL=http://localhost:8010/api/v1 npx vite build --outDir dist-e2e && npx vite preview --outDir dist-e2e --port 5183 --strictPort",
      url: "http://localhost:5183", reuseExistingServer: !process.env.CI, timeout: 120_000,
    },
  ],
});
