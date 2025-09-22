import { test, expect } from '@playwright/test';
import { TestHelpers } from '../../src/utils/test-helpers';

test.describe('Online Boutique Homepage', () => {
  
  test('should load homepage successfully', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'homepage-load');
    
    // Navigate to homepage
    await page.goto('/');
    
    // Wait for homepage to load completely
    await TestHelpers.waitForHomepage(page);
    
    // Verify essential elements are present
    await expect(page.locator('header, .header, [data-cy="header"]')).toBeVisible();
    const productCount = await page.locator('[data-cy="product-card"], .product-card, .product').count();
    expect(productCount).toBeGreaterThanOrEqual(1);
    
    console.log(`Homepage test completed with trace ID: ${traceId}`);
  });
  
  test('should display product catalog', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-catalog');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Verify products are displayed
    const productCards = page.locator('[data-cy="product-card"], .product-card, .product');
    const productCount = await productCards.count();
    
    expect(productCount).toBeGreaterThan(0);
    
    // Verify each product has essential information
    for (let i = 0; i < Math.min(productCount, 3); i++) {
      const product = productCards.nth(i);
      await expect(product).toBeVisible();
      
      // Check for product name and price
      const hasName = await product.locator('h3, .product-name, [data-cy="product-name"]').isVisible();
      const hasPrice = await product.locator('.price, [data-cy="price"]').isVisible();
      
      expect(hasName || hasPrice).toBeTruthy();
    }
    
    console.log(`Product catalog test completed with trace ID: ${traceId}`);
  });
  
  test('should navigate to product details', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-navigation');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Navigate to first product
    await TestHelpers.navigateToProduct(page, 0);
    
    // Verify product details page
    await expect(page.locator('[data-cy="product-name"], .product-name, h1')).toBeVisible();
    await expect(page.locator('[data-cy="product-price"], .product-price, .price')).toBeVisible();
    await expect(page.locator('[data-cy="add-to-cart"], button:has-text("Add to Cart")')).toBeVisible();
    
    console.log(`Product navigation test completed with trace ID: ${traceId}`);
  });
  
  // This test is designed to potentially fail to demonstrate the custom reporter
  test('should handle search functionality', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'search-functionality');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Look for search functionality
    const searchInput = page.locator('[data-cy="search"], input[type="search"], input[placeholder*="search" i]');
    
    if (await searchInput.isVisible()) {
      await searchInput.fill('test product');
      await searchInput.press('Enter');
      
      await page.waitForLoadState('networkidle');
      
      // Verify search results or no results message
      const hasResults = await page.locator('[data-cy="product-card"], .product-card, .product').count() > 0;
      const hasNoResultsMessage = await page.locator('.no-results, [data-cy="no-results"]').isVisible();
      
      expect(hasResults || hasNoResultsMessage).toBeTruthy();
    } else {
      // If no search functionality is found, this test will be skipped
      test.skip();
    }
    
    console.log(`Search test completed with trace ID: ${traceId}`);
  });
});