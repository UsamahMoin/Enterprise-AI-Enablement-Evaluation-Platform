import { defineConfig, devices } from "@playwright/test";

const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 3100);
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8100);
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

/**
 * Both servers are started by Playwright so the suite is a single command.
 * The backend runs against a throwaway SQLite file with the stub AI provider,
 * so end-to-end tests need no PostgreSQL and no API key.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "list" : "html",
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // A local .venv is put on PATH when present; on CI the dependencies are
      // installed into the runner's Python, where this prefix is a no-op.
      command:
        'cd ../backend && export PATH="$PWD/.venv/bin:$PATH" && rm -f e2e.db && ' +
        "alembic upgrade head && python -m app.seed && " +
        `uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: {
        DATABASE_URL: "sqlite+aiosqlite:///./e2e.db",
        AI_PROVIDER: "stub",
        JWT_SECRET: "e2e-secret",
        DEMO_PASSWORD: "demo1234",
        APP_ENV: "development",
      },
    },
    {
      command: `npm run build && npx next start -p ${FRONTEND_PORT} -H 127.0.0.1`,
      url: `http://127.0.0.1:${FRONTEND_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { NEXT_PUBLIC_API_URL: BACKEND_URL },
    },
  ],
});
