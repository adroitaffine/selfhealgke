import { Page, expect } from '@playwright/test';
import { TraceContextExtractor } from './trace-context-extractor';

/**
 * Test helper utilities for Online Boutique testing with trace context
 */
export class TestHelpers {
  
  /**
   * Sets up a page with trace context injection for distributed tracing
   */
  static async setupPageWithTracing(page: Page, testName: string): Promise<string> {
    // Generate or use existing trace ID
    const traceId = await TraceContextExtractor.injectTraceContext(page);
    
    // Add test metadata to page context
    await page.addInitScript(`
      window.__TEST_METADATA__ = {
        testName: '${testName}',
        traceId: '${traceId}',
        startTime: Date.now()
      };
      
      // Log trace ID to console for extraction
      console.log('Test Trace ID:', '${traceId}');
    `);
    
    return traceId;
  }
  
  /**
   * Waits for Online Boutique homepage to load completely
   */
  static async waitForHomepage(page: Page): Promise<void> {
    await page.waitForLoadState('networkidle');
    
    // Wait for essential elements
    await expect(page.locator('header, .header, [data-cy="header"]')).toBeVisible();
    
    // Wait for product grid to load
    await page.waitForSelector('[data-cy="product-card"], .product-card, .product', { 
      timeout: 15000 
    });
  }
  
  /**
   * Navigates to a product and waits for it to load
   */
  static async navigateToProduct(page: Page, productIndex: number = 0): Promise<void> {
    // Click on the first available product
    const productCards = page.locator('[data-cy="product-card"], .product-card, .product');
    await productCards.nth(productIndex).click();
    
    // Wait for product page to load
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[data-cy="product-name"], .product-name, h1')).toBeVisible();
  }
  
  /**
   * Adds a product to cart and verifies the action
   */
  static async addToCart(page: Page): Promise<void> {
    // Look for add to cart button with various selectors
    const addToCartButton = page.locator(
      '[data-cy="add-to-cart"], button:has-text("Add to Cart"), button:has-text("ADD TO CART")'
    ).first();
    
    await expect(addToCartButton).toBeVisible();
    await addToCartButton.click();
    
    // Wait for cart update confirmation
    await page.waitForTimeout(1000); // Brief wait for cart update
    
    // Verify cart icon shows items or success message appears
    const cartIndicator = page.locator(
      '[data-cy="cart-count"], .cart-count, .cart-items-count'
    );
    
    // Check if cart indicator is visible and has content
    if (await cartIndicator.isVisible()) {
      await expect(cartIndicator).not.toHaveText('0');
    }
  }
  
  /**
   * Navigates to cart page
   */
  static async navigateToCart(page: Page): Promise<void> {
    const cartButton = page.locator(
      '[data-cy="cart-button"], .cart-button, a:has-text("Cart"), button:has-text("Cart")'
    ).first();
    
    await expect(cartButton).toBeVisible();
    await cartButton.click();
    
    await page.waitForLoadState('networkidle');
    
    // Verify we're on the cart page
    await expect(page.locator(
      '[data-cy="cart-page"], .cart-page, h1:has-text("Cart"), h2:has-text("Cart")'
    )).toBeVisible();
  }
  
  /**
   * Proceeds to checkout
   */
  static async proceedToCheckout(page: Page): Promise<void> {
    const checkoutButton = page.locator(
      '[data-cy="checkout-button"], button:has-text("Checkout"), button:has-text("CHECKOUT")'
    ).first();
    
    await expect(checkoutButton).toBeVisible();
    await checkoutButton.click();
    
    await page.waitForLoadState('networkidle');
  }
  
  /**
   * Fills checkout form with test data
   */
  static async fillCheckoutForm(page: Page): Promise<void> {
    // Fill email
    const emailField = page.locator('[data-cy="email"], input[type="email"], input[name="email"]').first();
    if (await emailField.isVisible()) {
      await emailField.fill('test@example.com');
    }
    
    // Fill shipping address
    const addressFields = {
      street: page.locator('[data-cy="street-address"], input[name*="street"], input[name*="address"]').first(),
      city: page.locator('[data-cy="city"], input[name*="city"]').first(),
      state: page.locator('[data-cy="state"], input[name*="state"], select[name*="state"]').first(),
      zip: page.locator('[data-cy="zip"], input[name*="zip"], input[name*="postal"]').first(),
      country: page.locator('[data-cy="country"], select[name*="country"]').first(),
    };
    
    if (await addressFields.street.isVisible()) {
      await addressFields.street.fill('123 Test Street');
    }
    if (await addressFields.city.isVisible()) {
      await addressFields.city.fill('Test City');
    }
    if (await addressFields.state.isVisible()) {
      await addressFields.state.fill('CA');
    }
    if (await addressFields.zip.isVisible()) {
      await addressFields.zip.fill('12345');
    }
    if (await addressFields.country.isVisible()) {
      await addressFields.country.selectOption('US');
    }
    
    // Fill credit card information
    const cardFields = {
      number: page.locator('[data-cy="card-number"], input[name*="card"], input[placeholder*="card"]').first(),
      expiry: page.locator('[data-cy="expiry"], input[name*="expiry"], input[placeholder*="expiry"]').first(),
      cvv: page.locator('[data-cy="cvv"], input[name*="cvv"], input[name*="cvc"]').first(),
    };
    
    if (await cardFields.number.isVisible()) {
      await cardFields.number.fill('4111111111111111');
    }
    if (await cardFields.expiry.isVisible()) {
      await cardFields.expiry.fill('12/25');
    }
    if (await cardFields.cvv.isVisible()) {
      await cardFields.cvv.fill('123');
    }
  }
  
  /**
   * Completes the checkout process
   */
  static async completeCheckout(page: Page): Promise<void> {
    const placeOrderButton = page.locator(
      '[data-cy="place-order"], button:has-text("Place Order"), button:has-text("PLACE ORDER"), button:has-text("Complete Order")'
    ).first();
    
    await expect(placeOrderButton).toBeVisible();
    await placeOrderButton.click();
    
    // Wait for order confirmation
    await page.waitForLoadState('networkidle');
    
    // Verify order confirmation
    await expect(page.locator(
      '[data-cy="order-confirmation"], .order-confirmation, h1:has-text("Thank"), h2:has-text("Order")'
    )).toBeVisible({ timeout: 30000 });
  }
  
  /**
   * Captures current page state for debugging
   */
  static async capturePageState(page: Page, context: string): Promise<void> {
    console.log(`[${context}] Current URL: ${page.url()}`);
    console.log(`[${context}] Page title: ${await page.title()}`);
    
    // Log any console errors
    const logs = await page.evaluate(() => {
      return (globalThis as any).console.logs || [];
    });
    
    if (logs.length > 0) {
      console.log(`[${context}] Console logs:`, logs);
    }
  }
  
  /**
   * Waits for network requests to complete
   */
  static async waitForNetworkIdle(page: Page, timeout: number = 5000): Promise<void> {
    await page.waitForLoadState('networkidle', { timeout });
  }
  
  /**
   * Handles common error scenarios
   */
  static async handleCommonErrors(page: Page): Promise<boolean> {
    // Check for common error messages
    const errorSelectors = [
      '.error-message',
      '.alert-error',
      '[data-cy="error"]',
      '.notification.error',
      '.toast.error'
    ];
    
    for (const selector of errorSelectors) {
      const errorElement = page.locator(selector);
      if (await errorElement.isVisible()) {
        const errorText = await errorElement.textContent();
        console.log(`[Error Handler] Found error message: ${errorText}`);
        return true;
      }
    }
    
    return false;
  }
}