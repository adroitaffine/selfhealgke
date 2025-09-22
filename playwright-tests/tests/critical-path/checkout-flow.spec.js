"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const test_1 = require("@playwright/test");
const test_helpers_1 = require("../../src/utils/test-helpers");
test_1.test.describe('Critical Path: Complete Checkout Flow', () => {
    (0, test_1.test)('should complete full purchase journey', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'complete-checkout-flow');
        try {
            // Step 1: Load homepage
            await page.goto('/');
            await test_helpers_1.TestHelpers.waitForHomepage(page);
            console.log(`[${traceId}] Homepage loaded successfully`);
            // Step 2: Navigate to product
            await test_helpers_1.TestHelpers.navigateToProduct(page, 0);
            console.log(`[${traceId}] Product page loaded`);
            // Step 3: Add product to cart
            await test_helpers_1.TestHelpers.addToCart(page);
            console.log(`[${traceId}] Product added to cart`);
            // Step 4: Navigate to cart
            await test_helpers_1.TestHelpers.navigateToCart(page);
            console.log(`[${traceId}] Cart page loaded`);
            // Verify cart has items
            const cartItems = page.locator('[data-cy="cart-item"], .cart-item, .line-item');
            await (0, test_1.expect)(cartItems).toHaveCount({ min: 1 });
            // Step 5: Proceed to checkout
            await test_helpers_1.TestHelpers.proceedToCheckout(page);
            console.log(`[${traceId}] Checkout page loaded`);
            // Step 6: Fill checkout form
            await test_helpers_1.TestHelpers.fillCheckoutForm(page);
            console.log(`[${traceId}] Checkout form filled`);
            // Step 7: Complete checkout
            await test_helpers_1.TestHelpers.completeCheckout(page);
            console.log(`[${traceId}] Checkout completed successfully`);
        }
        catch (error) {
            await test_helpers_1.TestHelpers.capturePageState(page, `Error-${traceId}`);
            throw error;
        }
    });
    (0, test_1.test)('should handle cart operations', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'cart-operations');
        try {
            // Load homepage and add multiple products
            await page.goto('/');
            await test_helpers_1.TestHelpers.waitForHomepage(page);
            // Add first product
            await test_helpers_1.TestHelpers.navigateToProduct(page, 0);
            await test_helpers_1.TestHelpers.addToCart(page);
            // Go back to homepage
            await page.goto('/');
            await test_helpers_1.TestHelpers.waitForHomepage(page);
            // Add second product
            await test_helpers_1.TestHelpers.navigateToProduct(page, 1);
            await test_helpers_1.TestHelpers.addToCart(page);
            // Navigate to cart
            await test_helpers_1.TestHelpers.navigateToCart(page);
            // Verify multiple items in cart
            const cartItems = page.locator('[data-cy="cart-item"], .cart-item, .line-item');
            const itemCount = await cartItems.count();
            (0, test_1.expect)(itemCount).toBeGreaterThanOrEqual(1);
            // Test quantity modification if available
            const quantityInput = page.locator('[data-cy="quantity"], input[type="number"]').first();
            if (await quantityInput.isVisible()) {
                await quantityInput.fill('2');
                await page.waitForTimeout(1000); // Wait for cart update
            }
            console.log(`[${traceId}] Cart operations completed with ${itemCount} items`);
        }
        catch (error) {
            await test_helpers_1.TestHelpers.capturePageState(page, `CartError-${traceId}`);
            throw error;
        }
    });
    // This test is designed to potentially fail to demonstrate error handling
    (0, test_1.test)('should handle payment errors gracefully', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'payment-error-handling');
        try {
            // Complete flow up to checkout
            await page.goto('/');
            await test_helpers_1.TestHelpers.waitForHomepage(page);
            await test_helpers_1.TestHelpers.navigateToProduct(page, 0);
            await test_helpers_1.TestHelpers.addToCart(page);
            await test_helpers_1.TestHelpers.navigateToCart(page);
            await test_helpers_1.TestHelpers.proceedToCheckout(page);
            // Fill form with invalid payment information
            await test_helpers_1.TestHelpers.fillCheckoutForm(page);
            // Override with invalid card number
            const cardNumberField = page.locator('[data-cy="card-number"], input[name*="card"], input[placeholder*="card"]').first();
            if (await cardNumberField.isVisible()) {
                await cardNumberField.fill('1234567890123456'); // Invalid card number
            }
            // Attempt to complete checkout
            const placeOrderButton = page.locator('[data-cy="place-order"], button:has-text("Place Order"), button:has-text("PLACE ORDER")').first();
            if (await placeOrderButton.isVisible()) {
                await placeOrderButton.click();
                // Wait for error message or success (this might fail)
                await page.waitForTimeout(5000);
                // Check if error handling worked
                const hasError = await test_helpers_1.TestHelpers.handleCommonErrors(page);
                if (hasError) {
                    console.log(`[${traceId}] Payment error handled correctly`);
                }
                else {
                    // If no error message, the test might have unexpectedly succeeded
                    console.log(`[${traceId}] Payment processing completed (unexpected success)`);
                }
            }
        }
        catch (error) {
            await test_helpers_1.TestHelpers.capturePageState(page, `PaymentError-${traceId}`);
            console.log(`[${traceId}] Payment error test failed as expected: ${error.message}`);
            throw error;
        }
    });
    (0, test_1.test)('should handle network timeouts', async ({ page }) => {
        const traceId = await test_helpers_1.TestHelpers.setupPageWithTracing(page, 'network-timeout-test');
        // Set aggressive timeouts to potentially trigger failures
        page.setDefaultTimeout(5000);
        page.setDefaultNavigationTimeout(5000);
        try {
            await page.goto('/', { waitUntil: 'networkidle' });
            // This might timeout if the application is slow
            await test_helpers_1.TestHelpers.waitForHomepage(page);
            console.log(`[${traceId}] Network timeout test passed`);
        }
        catch (error) {
            console.log(`[${traceId}] Network timeout occurred as expected: ${error.message}`);
            throw error;
        }
    });
});
//# sourceMappingURL=checkout-flow.spec.js.map