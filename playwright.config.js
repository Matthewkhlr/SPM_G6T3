import { defineConfig, devices } from '@playwright/test'
import dotenv from 'dotenv'

dotenv.config({ path: '.env', quiet: true })

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'python3 scripts/dev-backend.py',
      url: 'http://127.0.0.1:8001/health',
      timeout: 120_000,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev --prefix frontend -- --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: true,
    },
  ],
})
