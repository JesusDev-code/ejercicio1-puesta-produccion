import { defineConfig, devices } from '@playwright/test';

import { PUERTOS } from './e2e/datos.mjs';

/**
 * E2E de punta a punta: navegador real → front compilado (con la CSP de nginx) → API real →
 * emulador de Firebase Auth. Todo lo levanta e2e/entorno.mjs; nada toca producción.
 *
 * Un solo worker: las pruebas comparten la BD sembrada y el emulador.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env['CI'] ? 1 : 0,
  forbidOnly: !!process.env['CI'],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: process.env['CI'] ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PUERTOS.web}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node e2e/entorno.mjs',
    url: `http://127.0.0.1:${PUERTOS.web}/api/salud`,
    timeout: 240_000,
    reuseExistingServer: !process.env['CI'],
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
