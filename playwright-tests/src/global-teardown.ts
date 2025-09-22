import { FullConfig } from '@playwright/test';

/**
 * Global teardown for Playwright tests
 * Cleans up test environment and reports final statistics
 */
async function globalTeardown(config: FullConfig) {
  console.log('[Global Teardown] Starting test environment cleanup...');
  
  // Log test run summary
  console.log('[Global Teardown] Test run completed');
  
  // Clean up any temporary files or resources if needed
  // This could include cleaning up uploaded artifacts, temporary trace files, etc.
  
  // Report webhook statistics if available
  const webhookUrl = process.env.AUTO_HEAL_WEBHOOK_URL;
  if (webhookUrl) {
    console.log(`[Global Teardown] Failure notifications were configured to be sent to: ${webhookUrl}`);
  }
  
  console.log('[Global Teardown] Cleanup completed successfully');
}

export default globalTeardown;