"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const test_1 = require("@playwright/test");
const test_helpers_1 = require("../../src/utils/test-helpers");
test_1.test.describe('Online Boutique Homepage', () => {
    (0, test_1.test)('should load homepage successfully', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'homepage-load');
        // Navigate to homepage
        await page.goto('/');
        // Wait for homepage to load completely
        await test_helpers_1.TestHelpers.waitForHomepage(page);
        // Verify essential elements are present
        await (0, test_1.expect)(page.locator('header, .header, [data-cy="header"]')).toBeVisible();
        await (0, test_1.expect)(page.locator('[data-cy="product-card"], .product-card, .product')).toHaveCount({ min: 1 });
        console.log(`Homepage test completed with trace ID: ${traceId}`);
    });
    (0, test_1.test)('should display product catalog', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'product-catalog');
        await page.goto('/');
        await test_helpers_1.TestHelpers.waitForHomepage(page);
        // Verify products are displayed
        const productCards = page.locator('[data-cy="product-card"], .product-card, .product');
        const productCount = await productCards.count();
        (0, test_1.expect)(productCount).toBeGreaterThan(0);
        // Verify each product has essential information
        for (let i = 0; i < Math.min(productCount, 3); i++) {
            const product = productCards.nth(i);
            await (0, test_1.expect)(product).toBeVisible();
            // Check for product name and price
            const hasName = await product.locator('h3, .product-name, [data-cy="product-name"]').isVisible();
            const hasPrice = await product.locator('.price, [data-cy="price"]').isVisible();
            (0, test_1.expect)(hasName || hasPrice).toBeTruthy();
        }
        console.log(`Product catalog test completed with trace ID: ${traceId}`);
    });
    (0, test_1.test)('should navigate to product details', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'product-navigation');
        await page.goto('/');
        await test_helpers_1.TestHelpers.waitForHomepage(page);
        // Navigate to first product
        await test_helpers_1.TestHelpers.navigateToProduct(page, 0);
        // Verify product details page
        await (0, test_1.expect)(page.locator('[data-cy="product-name"], .product-name, h1')).toBeVisible();
        await (0, test_1.expect)(page.locator('[data-cy="product-price"], .product-price, .price')).toBeVisible();
        await (0, test_1.expect)(page.locator('[data-cy="add-to-cart"], button:has-text("Add to Cart")')).toBeVisible();
        console.log(`Product navigation test completed with trace ID: ${traceId}`);
    });
    // This test is designed to potentially fail to demonstrate the custom reporter
    (0, test_1.test)('should handle search functionality', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'search-functionality');
        await page.goto('/');
        await test_helpers_1.TestHelpers.waitForHomepage(page);
        // Look for search functionality
        const searchInput = page.locator('[data-cy="search"], input[type="search"], input[placeholder*="search" i]');
        if (await searchInput.isVisible()) {
            await searchInput.fill('test product');
            await searchInput.press('Enter');
            await page.waitForLoadState('networkidle');
            // Verify search results or no results message
            const hasResults = await page.locator('[data-cy="product-card"], .product-card, .product').count() > 0;
            const hasNoResultsMessage = await page.locator('.no-results, [data-cy="no-results"]').isVisible();
            (0, test_1.expect)(hasResults || hasNoResultsMessage).toBeTruthy();
        }
        else {
            // If no search functionality is found, this test will be skipped
            test_1.test.skip('Search functionality not available');
        }
        console.log(`Search test completed with trace ID: ${traceId}`);
    });
});
//# sourceMappingURL=homepage.spec.js.map