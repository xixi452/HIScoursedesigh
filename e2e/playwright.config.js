// @ts-check
const { defineConfig } = require('@playwright/test')

module.exports = defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.js',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:8002',
    extraHTTPHeaders: { 'Content-Type': 'application/json' },
  },
  webServer: {
    command: 'python run_backend.py',
    url: 'http://127.0.0.1:8002/health',
    reuseExistingServer: false,
    timeout: 30000,
    cwd: __dirname,
  },
  reporter: [['list']],
})
