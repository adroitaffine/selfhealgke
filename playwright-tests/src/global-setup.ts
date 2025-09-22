import { chromium, FullConfig } from '@playwright/test';

/**
 * Global setup for Playwright tests
 * Initializes test environment and validates Online Boutique availability
 */
async function globalSetup(config: FullConfig) {
  console.log('[Global Setup] Starting Playwright test environment setup...');
  
  const baseURL = process.env.ONLINE_BOUTIQUE_URL || 'http://localhost:8080';
  
  // Validate that Online Boutique is accessible
  try {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    
    console.log(`[Global Setup] Checking Online Boutique availability at ${baseURL}`);
    
    // Try to access the homepage with a reasonable timeout
    await page.goto(baseURL, { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    
    // Verify the page loaded correctly
    const title = await page.title();
    console.log(`[Global Setup] Online Boutique is accessible. Page title: ${title}`);
    
    // Check for essential elements
    const hasProducts = await page.locator('[data-cy="product-card"], .product-card, .product').count() > 0;
    if (hasProducts) {
      console.log('[Global Setup] Product catalog is loaded and accessible');
    } else {
      console.warn('[Global Setup] Warning: No products found on homepage');
    }
    
    await browser.close();
    
  } catch (error) {
    console.error(`[Global Setup] Failed to connect to Online Boutique at ${baseURL}:`, error);
    console.error('[Global Setup] Please ensure Online Boutique is running and accessible');
    throw new Error(`Online Boutique is not accessible at ${baseURL}`);
  }
  
  // Validate webhook configuration
  const webhookUrl = process.env.AUTO_HEAL_WEBHOOK_URL;
  if (!webhookUrl) {
    console.warn('[Global Setup] Warning: AUTO_HEAL_WEBHOOK_URL not set. Failure notifications will be sent to default URL.');
  } else {
    console.log(`[Global Setup] Auto-Heal webhook configured: ${webhookUrl}`);
  }
  
  const webhookSecret = process.env.AUTO_HEAL_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.warn('[Global Setup] Warning: AUTO_HEAL_WEBHOOK_SECRET not set. Webhook signatures will not be generated.');
  } else {
    console.log('[Global Setup] Webhook secret is configured for secure communication');
  }
  
  console.log('[Global Setup] Environment setup completed successfully');
}

export default globalSetup;