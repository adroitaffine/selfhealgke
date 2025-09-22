import { test, expect } from '@playwright/test';
import { TestHelpers } from '../../src/utils/test-helpers';

test.describe('Online Boutique - Shopping Cart', () => {
  
  test('should add product to cart successfully', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'add-to-cart');
    
    // Navigate to homepage and select a product
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    
    // Get product information before adding to cart
    const productNameSelectors = [
      '[data-cy="product-name"]',
      '.product-name',
      'h1',
      'h2',
      '.product-title'
    ];
    
    let productName = 'Unknown Product';
    for (const selector of productNameSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        productName = await element.first().textContent() || 'Unknown Product';
        break;
      }
    }
    
    // Add product to cart
    await TestHelpers.addToCart(page);
    
    // Verify cart indicator shows items
    const cartIndicatorSelectors = [
      '[data-cy="cart-count"]',
      '.cart-count',
      '.cart-items-count',
      '.cart-badge',
      '.cart-quantity'
    ];
    
    let cartIndicatorFound = false;
    for (const selector of cartIndicatorSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0 && await element.isVisible()) {
        const cartCount = await element.textContent();
        expect(cartCount).not.toBe('0');
        expect(cartCount).not.toBe('');
        cartIndicatorFound = true;
        console.log(`[${traceId}] Cart indicator shows: ${cartCount}`);
        break;
      }
    }
    
    // If no cart indicator found, check for success message
    if (!cartIndicatorFound) {
      const successSelectors = [
        '.success-message',
        '.alert-success',
        ':has-text("Added to cart")',
        ':has-text("Item added")',
        '.notification.success'
      ];
      
      for (const selector of successSelectors) {
        const element = page.locator(selector);
        if (await element.count() > 0) {
          await expect(element.first()).toBeVisible();
          cartIndicatorFound = true;
          break;
        }
      }
    }
    
    expect(cartIndicatorFound).toBeTruthy();
    console.log(`[${traceId}] Successfully added "${productName}" to cart`);
  });
  
  test('should view cart contents', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'view-cart');
    
    // Add a product to cart first
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    await TestHelpers.addToCart(page);
    
    // Navigate to cart
    await TestHelpers.navigateToCart(page);
    
    // Verify cart page elements
    const cartPageSelectors = [
      '[data-cy="cart-page"]',
      '.cart-page',
      'h1:has-text("Cart")',
      'h2:has-text("Cart")',
      'h1:has-text("Shopping Cart")',
      '.shopping-cart'
    ];
    
    let cartPageFound = false;
    for (const selector of cartPageSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        await expect(element.first()).toBeVisible();
        cartPageFound = true;
        break;
      }
    }
    
    expect(cartPageFound).toBeTruthy();
    
    // Verify cart items are displayed
    const cartItemSelectors = [
      '[data-cy="cart-item"]',
      '.cart-item',
      '.line-item',
      '.cart-product',
      '.shopping-cart-item'
    ];
    
    let cartItems = null;
    for (const selector of cartItemSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        cartItems = elements;
        break;
      }
    }
    
    expect(cartItems).toBeTruthy();
    const itemCount = await cartItems!.count();
    expect(itemCount).toBeGreaterThanOrEqual(1);
    
    console.log(`[${traceId}] Cart contains ${itemCount} item(s)`);
    
    // Verify cart item details
    const firstItem = cartItems!.first();
    await expect(firstItem).toBeVisible();
    
    // Check for product name in cart item
    const itemNameSelectors = [
      '.item-name',
      '.product-name',
      '.cart-item-name',
      'h3',
      'h4'
    ];
    
    let itemNameFound = false;
    for (const selector of itemNameSelectors) {
      const element = firstItem.locator(selector);
      if (await element.count() > 0) {
        const itemName = await element.first().textContent();
        expect(itemName).toBeTruthy();
        console.log(`[${traceId}] Cart item: ${itemName}`);
        itemNameFound = true;
        break;
      }
    }
    
    // Check for price in cart item
    const itemPriceSelectors = [
      '.item-price',
      '.price',
      '.cart-item-price',
      '.cost'
    ];
    
    let itemPriceFound = false;
    for (const selector of itemPriceSelectors) {
      const element = firstItem.locator(selector);
      if (await element.count() > 0) {
        const itemPrice = await element.first().textContent();
        expect(itemPrice).toBeTruthy();
        console.log(`[${traceId}] Item price: ${itemPrice}`);
        itemPriceFound = true;
        break;
      }
    }
    
    expect(itemNameFound || itemPriceFound).toBeTruthy();
    console.log(`[${traceId}] Cart contents verified successfully`);
  });
  
  test('should update cart item quantity', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'update-cart-quantity');
    
    // Add a product to cart and navigate to cart
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    await TestHelpers.addToCart(page);
    await TestHelpers.navigateToCart(page);
    
    // Look for quantity input
    const quantitySelectors = [
      '[data-cy="quantity"]',
      'input[type="number"]',
      '.quantity-input',
      '.qty-input',
      'input[name*="quantity"]'
    ];
    
    let quantityInput = null;
    for (const selector of quantitySelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0 && await element.first().isVisible()) {
        quantityInput = element.first();
        break;
      }
    }
    
    if (quantityInput) {
      // Get current quantity
      const currentQuantity = await quantityInput.inputValue();
      console.log(`[${traceId}] Current quantity: ${currentQuantity}`);
      
      // Update quantity to 2
      await quantityInput.fill('2');
      
      // Look for update button or trigger update
      const updateSelectors = [
        'button:has-text("Update")',
        '[data-cy="update-cart"]',
        '.update-cart-button',
        'button[type="submit"]'
      ];
      
      let updateTriggered = false;
      for (const selector of updateSelectors) {
        const element = page.locator(selector);
        if (await element.count() > 0 && await element.isVisible()) {
          await element.click();
          updateTriggered = true;
          break;
        }
      }
      
      // If no update button, try pressing Enter or triggering blur
      if (!updateTriggered) {
        await quantityInput.press('Enter');
        await page.waitForTimeout(1000); // Wait for potential AJAX update
      }
      
      // Wait for cart to update
      await page.waitForLoadState('networkidle');
      
      // Verify quantity was updated (if the input still shows the new value)
      const updatedQuantity = await quantityInput.inputValue();
      expect(updatedQuantity).toBe('2');
      
      console.log(`[${traceId}] Quantity updated to: ${updatedQuantity}`);
    } else {
      console.log(`[${traceId}] Quantity input not found, skipping quantity update test`);
      test.skip();
    }
  });
  
  test('should remove item from cart', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'remove-cart-item');
    
    // Add a product to cart and navigate to cart
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    await TestHelpers.addToCart(page);
    await TestHelpers.navigateToCart(page);
    
    // Get initial cart item count
    const cartItemSelectors = [
      '[data-cy="cart-item"]',
      '.cart-item',
      '.line-item',
      '.cart-product'
    ];
    
    let cartItems = null;
    for (const selector of cartItemSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        cartItems = elements;
        break;
      }
    }
    
    expect(cartItems).toBeTruthy();
    const initialItemCount = await cartItems!.count();
    console.log(`[${traceId}] Initial cart items: ${initialItemCount}`);
    
    // Look for remove button
    const removeSelectors = [
      '[data-cy="remove-item"]',
      'button:has-text("Remove")',
      'button:has-text("Delete")',
      '.remove-button',
      '.delete-button',
      'button[title*="Remove"]',
      'a:has-text("Remove")'
    ];
    
    let removeButton = null;
    for (const selector of removeSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0 && await element.first().isVisible()) {
        removeButton = element.first();
        break;
      }
    }
    
    if (removeButton) {
      // Click remove button
      await removeButton.click();
      
      // Wait for cart to update
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000); // Additional wait for UI update
      
      // Verify item was removed
      const updatedItemCount = await cartItems!.count();
      console.log(`[${traceId}] Updated cart items: ${updatedItemCount}`);
      
      // Item count should be reduced or cart should show empty message
      if (updatedItemCount < initialItemCount) {
        console.log(`[${traceId}] Item successfully removed from cart`);
      } else {
        // Check for empty cart message
        const emptyCartSelectors = [
          '.empty-cart',
          ':has-text("Your cart is empty")',
          ':has-text("No items in cart")',
          '.cart-empty-message'
        ];
        
        let emptyCartFound = false;
        for (const selector of emptyCartSelectors) {
          const element = page.locator(selector);
          if (await element.count() > 0) {
            await expect(element.first()).toBeVisible();
            emptyCartFound = true;
            break;
          }
        }
        
        expect(emptyCartFound || updatedItemCount < initialItemCount).toBeTruthy();
      }
    } else {
      console.log(`[${traceId}] Remove button not found, skipping remove test`);
      test.skip();
    }
  });
  
  test('should display cart total', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'cart-total');
    
    // Add a product to cart and navigate to cart
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    await TestHelpers.addToCart(page);
    await TestHelpers.navigateToCart(page);
    
    // Look for cart total
    const totalSelectors = [
      '[data-cy="cart-total"]',
      '.cart-total',
      '.total-price',
      '.grand-total',
      '.cart-summary-total',
      ':has-text("Total:")',
      ':has-text("Subtotal:")'
    ];
    
    let totalFound = false;
    for (const selector of totalSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        await expect(element.first()).toBeVisible();
        const totalText = await element.first().textContent();
        console.log(`[${traceId}] Cart total: ${totalText}`);
        
        // Verify total contains currency symbol or number
        expect(totalText).toMatch(/[\$€£¥]|\d+/);
        totalFound = true;
        break;
      }
    }
    
    expect(totalFound).toBeTruthy();
    console.log(`[${traceId}] Cart total verification completed`);
  });
  
  test('should persist cart across page navigation', async ({ page }) => {
    const traceId = await TestHelpers.setupPageWithTracing(page, 'cart-persistence');
    
    // Add a product to cart
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    await TestHelpers.navigateToProduct(page, 0);
    await TestHelpers.addToCart(page);
    
    // Navigate back to homepage
    await page.goto('/');
    await TestHelpers.waitForHomepage(page);
    
    // Check if cart indicator still shows items
    const cartIndicatorSelectors = [
      '[data-cy="cart-count"]',
      '.cart-count',
      '.cart-items-count',
      '.cart-badge',
      '.cart-quantity'
    ];
    
    let cartPersisted = false;
    for (const selector of cartIndicatorSelectors) {
      const element = page.locator(selector);
      if (await element.count() > 0 && await element.isVisible()) {
        const cartCount = await element.textContent();
        if (cartCount && cartCount !== '0' && cartCount !== '') {
          console.log(`[${traceId}] Cart persisted with ${cartCount} item(s)`);
          cartPersisted = true;
          break;
        }
      }
    }
    
    // Navigate to cart to double-check
    await TestHelpers.navigateToCart(page);
    
    const cartItemSelectors = [
      '[data-cy="cart-item"]',
      '.cart-item',
      '.line-item',
      '.cart-product'
    ];
    
    let cartItemsFound = false;
    for (const selector of cartItemSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        const itemCount = await elements.count();
        expect(itemCount).toBeGreaterThanOrEqual(1);
        cartItemsFound = true;
        console.log(`[${traceId}] Cart contains ${itemCount} persisted item(s)`);
        break;
      }
    }
    
    expect(cartPersisted || cartItemsFound).toBeTruthy();
    console.log(`[${traceId}] Cart persistence verification completed`);
  });
});