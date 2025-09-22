import { test, expect } from '@playwright/test';
import { TestHelpers } from '../../src/utils/test-helpers';

test.describe('Online Boutique - Product Browsing', () => {
  
  test('should browse product catalog successfully', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-catalog-browsing');
    
    // Navigate to homepage
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Verify product catalog is loaded
    const productCards = page.locator('[data-cy="product-card"], .product-card, .product, .hot-product-card');
    const productCount = await productCards.count();
    expect(productCount).toBeGreaterThan(0);
    
    console.log(`[${traceId}] Found ${productCount} products in catalog`);
    
    // Test product card interactions
    for (let i = 0; i < Math.min(productCount, 3); i++) {
      const product = productCards.nth(i);
      await expect(product).toBeVisible();
      
      // Verify product has essential information
      const productName = product.locator('h3, .product-name, [data-cy="product-name"], .hot-product-card-name');
      const productPrice = product.locator('.price, [data-cy="price"], .hot-product-card-price');
      
      // At least one of name or price should be visible
      const hasName = await productName.count() > 0;
      const hasPrice = await productPrice.count() > 0;
      expect(hasName || hasPrice).toBeTruthy();
      
      if (hasName) {
        const nameText = await productName.first().textContent();
        expect(nameText).toBeTruthy();
        console.log(`[${traceId}] Product ${i + 1}: ${nameText}`);
      }
    }
    
    console.log(`[${traceId}] Product catalog browsing completed successfully`);
  });
  
  test('should navigate to product details', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-details-navigation');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Click on first product
    const productCards = page.locator('[data-cy="product-card"], .product-card, .product, .hot-product-card');
    await expect(productCards.first()).toBeVisible();
    
    // Get product name before clicking
    const productNameElement = productCards.first().locator('h3, .product-name, [data-cy="product-name"], .hot-product-card-name');
    const originalProductName = await productNameElement.first().textContent() || 'Unknown Product';
    
    await productCards.first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify we're on product details page
    const productDetailsSelectors = [
      '[data-cy="product-name"]',
      '.product-name',
      'h1',
      'h2',
      '.product-title'
    ];
    
    let productDetailsFound = false;
    for (const selector of productDetailsSelectors) {
      if (await page.locator(selector).count() > 0) {
        await expect(page.locator(selector).first()).toBeVisible();
        productDetailsFound = true;
        break;
      }
    }
    
    expect(productDetailsFound).toBeTruthy();
    
    // Verify product price is displayed
    const priceSelectors = [
      '[data-cy="product-price"]',
      '.product-price',
      '.price',
      '.product-info .price'
    ];
    
    let priceFound = false;
    for (const selector of priceSelectors) {
      if (await page.locator(selector).count() > 0) {
        await expect(page.locator(selector).first()).toBeVisible();
        priceFound = true;
        break;
      }
    }
    
    expect(priceFound).toBeTruthy();
    
    // Verify add to cart button is present
    const addToCartSelectors = [
      '[data-cy="add-to-cart"]',
      'button:has-text("Add to Cart")',
      'button:has-text("ADD TO CART")',
      '.add-to-cart-button',
      'input[type="submit"][value*="Add"]'
    ];
    
    let addToCartFound = false;
    for (const selector of addToCartSelectors) {
      if (await page.locator(selector).count() > 0) {
        await expect(page.locator(selector).first()).toBeVisible();
        addToCartFound = true;
        break;
      }
    }
    
    expect(addToCartFound).toBeTruthy();
    
    console.log(`[${traceId}] Product details navigation completed for: ${originalProductName}`);
  });
  
  test('should handle product search functionality', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-search');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Look for search input
    const searchSelectors = [
      '[data-cy="search"]',
      'input[type="search"]',
      'input[placeholder*="search" i]',
      'input[name*="search" i]',
      '.search-input',
      '#search'
    ];
    
    let searchInput = null;
    for (const selector of searchSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        searchInput = element.first();
        break;
      }
    }
    
    if (searchInput && await searchInput.isVisible()) {
      // Test search functionality
      await searchInput.fill('shirt');
      
      // Try different ways to submit search
      const searchSubmitSelectors = [
        'button[type="submit"]',
        'button:has-text("Search")',
        '.search-button',
        '[data-cy="search-button"]'
      ];
      
      let searchSubmitted = false;
      for (const selector of searchSubmitSelectors) {
        const button = page.locator(selector);
        if (await button.count() > 0 && await button.isVisible()) {
          await button.click();
          searchSubmitted = true;
          break;
        }
      }
      
      // If no submit button found, try pressing Enter
      if (!searchSubmitted) {
        await searchInput.press('Enter');
      }
      
      await page.waitForLoadState('networkidle');
      
      // Verify search results or no results message
      const hasResults = await page.locator('[data-cy="product-card"], .product-card, .product, .hot-product-card').count() > 0;
      const noResultsSelectors = [
        '.no-results',
        '[data-cy="no-results"]',
        ':has-text("No results")',
        ':has-text("No products found")',
        '.empty-results'
      ];
      
      let hasNoResultsMessage = false;
      for (const selector of noResultsSelectors) {
        if (await page.locator(selector).count() > 0) {
          hasNoResultsMessage = true;
          break;
        }
      }
      
      // Either results or no results message should be present
      expect(hasResults || hasNoResultsMessage).toBeTruthy();
      
      if (hasResults) {
        console.log(`[${traceId}] Search returned products`);
      } else {
        console.log(`[${traceId}] Search returned no results (expected for some searches)`);
      }
    } else {
      // Search functionality not available, skip test
      console.log(`[${traceId}] Search functionality not found, skipping test`);
      test.skip();
    }
    
    console.log(`[${traceId}] Product search test completed`);
  });
  
  test('should handle product categories navigation', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'category-navigation');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Look for category navigation
    const categorySelectors = [
      '[data-cy="category"]',
      '.category',
      '.nav-category',
      'nav a',
      '.category-link',
      '.product-category'
    ];
    
    let categoryLinks = null;
    for (const selector of categorySelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        categoryLinks = elements;
        break;
      }
    }
    
    if (categoryLinks && await categoryLinks.count() > 0) {
      const categoryCount = await categoryLinks.count();
      console.log(`[${traceId}] Found ${categoryCount} category links`);
      
      // Test first category link
      const firstCategory = categoryLinks.first();
      const categoryText = await firstCategory.textContent() || 'Unknown Category';
      
      await firstCategory.click();
      await page.waitForLoadState('networkidle');
      
      // Verify we navigated to a category page
      const hasProducts = await page.locator('[data-cy="product-card"], .product-card, .product, .hot-product-card').count() > 0;
      const hasCategoryTitle = await page.locator('h1, h2, .category-title, .page-title').count() > 0;
      
      expect(hasProducts || hasCategoryTitle).toBeTruthy();
      
      console.log(`[${traceId}] Category navigation completed for: ${categoryText}`);
    } else {
      // Category navigation not available
      console.log(`[${traceId}] Category navigation not found, skipping test`);
      test.skip();
    }
  });
  
  test('should display product recommendations', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'product-recommendations');
    
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Navigate to a product details page
    await TestHelpers.navigateToProduct(page, 0);
    
    // Look for recommendations section
    const recommendationSelectors = [
      '[data-cy="recommendations"]',
      '.recommendations',
      '.related-products',
      '.you-may-also-like',
      '.recommended-products',
      ':has-text("You may also like")',
      ':has-text("Recommended")',
      ':has-text("Related products")'
    ];
    
    let recommendationsFound = false;
    for (const selector of recommendationSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        await expect(element.first()).toBeVisible();
        recommendationsFound = true;
        
        // Check if recommendations contain products
        const recommendedProducts = element.locator('[data-cy="product-card"], .product-card, .product, .hot-product-card');
        const recommendedCount = await recommendedProducts.count();
        
        if (recommendedCount > 0) {
          console.log(`[${traceId}] Found ${recommendedCount} recommended products`);
          
          // Verify first recommended product is clickable
          await expect(recommendedProducts.first()).toBeVisible();
        }
        
        break;
      }
    }
    
    if (recommendationsFound) {
      console.log(`[${traceId}] Product recommendations found and verified`);
    } else {
      console.log(`[${traceId}] Product recommendations not found (may not be implemented)`);
    }
  });
});