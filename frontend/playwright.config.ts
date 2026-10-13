import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke test: login -> create match -> upload -> play.
 *
 * Playwright starts the API (migrated, seeded, with inline transcoding) and the Vite dev
 * server. It needs Postgres, Redis, FFmpeg and uv on the machine. Environment:
 *   E2E_DATABASE_URL         defaults to the rugby_e2e database on localhost
 *   PLAYWRIGHT_CHROMIUM_PATH optional path to a Chromium binary (otherwise Playwright's own)
 *   PLAYWRIGHT_CHANNEL       'chrome' to use Google Chrome, which can decode H.264
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
// Playwright's open-source Chromium cannot decode H.264. Google Chrome can: install it with
// `npx playwright install chrome` and set PLAYWRIGHT_CHANNEL=chrome to run the playback checks.
const channel = process.env.PLAYWRIGHT_CHANNEL;

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    launchOptions: executablePath ? { executablePath } : {},
    ...(channel ? { channel } : {}),
  },
  projects: [{ name: channel ?? 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'bash e2e/start-api.sh',
      url: 'http://localhost:8000/api/health',
      timeout: 180_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
});
