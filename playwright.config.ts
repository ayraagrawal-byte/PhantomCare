import { defineConfig, devices } from "@playwright/test";

// The suite needs the FastAPI backend (published offline artifacts, live AI off)
// and the Next.js dashboard. Already-running servers are reused.
const python = process.env.PHANTOMCARE_E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "./dashboard/e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `${python} -m uvicorn api.app:app --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        PHANTOMCARE_ANALYSIS_DIR: "data/runtime",
        PHANTOMCARE_AGENT_LIVE_ENABLED: "false",
        PHANTOMCARE_DASHBOARD_ORIGIN: "http://localhost:3000",
      },
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" } },
  ],
});
