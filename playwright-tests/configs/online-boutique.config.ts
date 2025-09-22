import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration specifically for Online Boutique testing
 * Optimized for synthetic monitoring and auto-heal integration
 */
export default defineConfig({
  testDir: '../tests',
  
  /* Test matching patterns for Online Boutique */
  testMatch: [
    '**/online-boutique/**/*.spec.ts',
    '**/critical-path/**/*.spec.ts'
  ],
  
  /* Run tests in files in parallel */
  fullyParallel: false, // Sequential for better trace correlation
  
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  
  /* Retry configuration - important for synthetic monitoring */
  retries: process.env.CI ? 3 : 2,
  
  /* Workers configuration */
  workers: process.env.CI ? 1 : 2,
  
  /* Timeout configuration */
  timeout: 90000, // 90 seconds per test
  globalTimeout: 1800000, // 30 minutes total
  expect: {
    timeout: 15000, // 15 seconds for assertions
  },
  
  /* Reporter configuration with custom failure reporter */
  reporter: [
    ['html', { 
      outputFolder: 'playwright-report',
      open: process.env.CI ? 'never' : 'on-failure'
    }],
    ['json', { 
      outputFile: 'test-results/online-boutique-results.json' 
    }],
    ['junit', { 
      outputFile: 'test-results/online-boutique-junit.xml' 
    }],
    ['../src/reporters/custom-failure-reporter.ts', {
      webhookUrl: process.env.AUTO_HEAL_WEBHOOK_URL || 'http://localhost:8080/webhook/failure',
      webhookSecret: process.env.AUTO_HEAL_WEBHOOK_SECRET,
      maxRetries: 3,
      retryDelay: 1000,
    }],
  ],
  
  /* Shared settings optimized for Online Boutique */
  use: {
    /* Base URL for Online Boutique */
    baseURL: process.env.ONLINE_BOUTIQUE_URL || 'http://localhost:8080',
    
    /* Trace and video settings for failure analysis */
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    
    /* Browser context settings */
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    
    /* Timeout settings */
    navigationTimeout: 45000, // 45 seconds for navigation
    actionTimeout: 15000, // 15 seconds for actions
    
    /* Additional headers for trace correlation */
    extraHTTPHeaders: {
      'User-Agent': 'Playwright-Auto-Heal-Synthetic-Test/1.0',
      'X-Test-Environment': 'auto-heal-synthetic',
    },
  },

  /* Projects for different test scenarios */
  projects: [
    {
      name: 'online-boutique-chrome',
      use: { 
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--enable-logging',
            '--log-level=0',
            '--enable-network-service-logging',
            '--disable-web-security', // For CORS in development
          ],
        },
      },
      testMatch: '**/online-boutique/**/*.spec.ts',
    },

    {
      name: 'critical-path-chrome',
      use: { 
        ...devices['Desktop Chrome'],
        // More aggressive timeouts for critical path
        actionTimeout: 10000,
        navigationTimeout: 30000,
        launchOptions: {
          args: [
            '--enable-logging',
            '--log-level=0',
          ],
        },
      },
      testMatch: '**/critical-path/**/*.spec.ts',
    },

    {
      name: 'mobile-simulation',
      use: { 
        ...devices['Pixel 5'],
        // Mobile-specific settings
        actionTimeout: 20000, // Slower on mobile
        navigationTimeout: 60000,
      },
      testMatch: [
        '**/online-boutique/homepage.spec.ts',
        '**/online-boutique/product-browsing.spec.ts',
        '**/critical-path/complete-user-journey.spec.ts'
      ],
    },

    {
      name: 'firefox-compatibility',
      use: { 
        ...devices['Desktop Firefox'],
      },
      testMatch: '**/critical-path/**/*.spec.ts',
    },
  ],

  /* Output directories */
  outputDir: 'test-results/',
  
  /* Global setup and teardown */
  globalSetup: require.resolve('../src/global-setup.ts'),
  globalTeardown: require.resolve('../src/global-teardown.ts'),

  /* Metadata for test runs */
  metadata: {
    application: 'Online Boutique',
    version: '1.0.0',
    environment: process.env.NODE_ENV || 'development',
    autoHealEnabled: true,
  },
});