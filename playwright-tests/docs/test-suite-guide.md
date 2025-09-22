# Online Boutique Test Suite Guide

This guide covers the comprehensive Playwright test suite for Online Boutique with Auto-Heal Agent integration, including trace context propagation and failure reporting.

## Overview

The test suite is designed for synthetic monitoring of the Online Boutique microservices application with the following key features:

- **Trace Context Propagation**: W3C Trace Context headers for distributed tracing correlation
- **Custom Failure Reporter**: Automatic webhook notifications to the Auto-Heal Agent
- **Comprehensive Coverage**: Critical user journeys and edge cases
- **Retry Logic**: Robust retry mechanisms with exponential backoff
- **Artifact Management**: Video recordings and trace files for failure analysis

## Test Structure

```
tests/
├── online-boutique/           # Core application tests
│   ├── homepage.spec.ts       # Homepage and navigation
│   ├── product-browsing.spec.ts  # Product catalog and search
│   ├── shopping-cart.spec.ts  # Cart operations
│   └── checkout-flow.spec.ts  # Checkout process
├── critical-path/             # End-to-end critical flows
│   ├── checkout-flow.spec.ts  # Complete checkout scenarios
│   └── complete-user-journey.spec.ts  # Full e-commerce flows
└── utils/                     # Test utilities and helpers
```

## Test Categories

### 1. Homepage Tests (`online-boutique/homepage.spec.ts`)

Tests the main landing page functionality:

- **Homepage Load**: Verifies page loads with product catalog
- **Product Display**: Validates product cards and information
- **Navigation**: Tests product detail navigation
- **Search Functionality**: Tests search if available

**Key Features**:
- Trace ID injection for correlation
- Product count validation
- Essential element verification
- Graceful handling of missing features

### 2. Product Browsing Tests (`online-boutique/product-browsing.spec.ts`)

Comprehensive product discovery and browsing:

- **Product Catalog Browsing**: Navigate through product listings
- **Product Details Navigation**: Access individual product pages
- **Search Functionality**: Product search and filtering
- **Category Navigation**: Browse by product categories
- **Product Recommendations**: Related product suggestions

**Key Features**:
- Multiple selector strategies for robustness
- Dynamic product information extraction
- Search result validation
- Category-based navigation testing

### 3. Shopping Cart Tests (`online-boutique/shopping-cart.spec.ts`)

Complete shopping cart functionality:

- **Add to Cart**: Product addition with verification
- **View Cart Contents**: Cart page and item display
- **Update Quantities**: Modify item quantities
- **Remove Items**: Delete items from cart
- **Cart Totals**: Price calculation verification
- **Cart Persistence**: Cross-page cart state maintenance

**Key Features**:
- Cart indicator monitoring
- Quantity manipulation testing
- Total calculation verification
- Session persistence validation

### 4. Checkout Flow Tests (`online-boutique/checkout-flow.spec.ts`)

End-to-end checkout process:

- **Checkout Initiation**: Navigate from cart to checkout
- **Shipping Information**: Address form completion
- **Payment Information**: Credit card form filling
- **Order Summary**: Review order details
- **Field Validation**: Required field validation
- **Payment Processing**: Order submission handling
- **Order Confirmation**: Success page verification

**Key Features**:
- Form field auto-completion
- Validation error handling
- Payment processing simulation
- Confirmation page verification

### 5. Critical Path Tests (`critical-path/`)

Complete user journey scenarios:

- **Complete E-commerce Journey**: Full flow from browse to purchase
- **Multiple Products**: Cart with multiple items
- **Search-based Journey**: Product discovery via search
- **Cart Abandonment**: Cart persistence across sessions

**Key Features**:
- End-to-end flow validation
- Multi-product scenarios
- Abandonment and recovery testing
- Cross-session state management

## Trace Context Integration

### Automatic Trace Injection

Every test automatically injects W3C Trace Context:

```typescript
const traceId = await TestHelpers.setupPageWithTracing(page, 'test-name');
```

This creates:
- **Trace ID**: 32-character hex string for correlation
- **HTTP Headers**: `traceparent` and `tracestate` headers
- **Browser Context**: JavaScript variables for client-side correlation
- **Console Logging**: Trace ID logged for extraction

### Trace Context Format

```
traceparent: 00-{trace-id}-{parent-id}-01
tracestate: auto-heal=synthetic-test,journey={test-name}
x-cloud-trace-context: {trace-id}/1;o=1
```

### Correlation with Backend

The trace context enables correlation between:
- Playwright test execution
- Frontend HTTP requests
- Backend service calls
- Distributed trace spans
- Application logs

## Custom Failure Reporter

### Failure Detection

The custom reporter automatically detects:
- Test failures (`status: 'failed'`)
- Test timeouts (`status: 'timedOut'`)
- Assertion failures
- Network timeouts
- Browser crashes

### Payload Structure

```json
{
  "testTitle": "should complete full purchase journey",
  "status": "failed",
  "error": {
    "message": "Timeout waiting for checkout button",
    "stack": "Error: Timeout waiting for checkout button\n    at ...",
    "type": "TimeoutError"
  },
  "retries": 2,
  "traceID": "a1b2c3d4e5f6789012345678901234567890abcd",
  "videoUrl": "https://artifacts.example.com/videos/test-video.webm",
  "traceUrl": "https://artifacts.example.com/traces/test-trace.zip",
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

### Webhook Delivery

- **Secure Transmission**: HMAC-SHA256 signature verification
- **Retry Logic**: Exponential backoff with jitter
- **Error Handling**: Graceful failure handling
- **Timeout Management**: Configurable request timeouts

## Configuration

### Environment Variables

```bash
# Required
ONLINE_BOUTIQUE_URL="http://your-online-boutique-url"
AUTO_HEAL_WEBHOOK_URL="https://your-auto-heal-agent/webhook/failure"

# Optional
AUTO_HEAL_WEBHOOK_SECRET="your-webhook-secret"
ARTIFACT_BASE_URL="https://your-artifact-storage"
NODE_ENV="development|staging|production"
```

### Test Configuration

Multiple configurations available:

1. **Default Config** (`playwright.config.ts`): General purpose testing
2. **Online Boutique Config** (`configs/online-boutique.config.ts`): Optimized for Online Boutique
3. **Project-Specific**: Different browser and device configurations

### Projects

- **online-boutique-chrome**: Standard Chrome testing
- **critical-path-chrome**: Critical path with aggressive timeouts
- **mobile-simulation**: Mobile device simulation
- **firefox-compatibility**: Firefox compatibility testing

## Running Tests

### Basic Commands

```bash
# All tests with default config
npm test

# Online Boutique specific tests
npm run test:online-boutique

# Critical path tests only
npm run test:critical-path

# Mobile simulation
npm run test:mobile

# Debug mode
npm run test:online-boutique:debug
```

### Advanced Usage

```bash
# Specific test file
npx playwright test tests/online-boutique/checkout-flow.spec.ts

# Specific project
npx playwright test --project=critical-path-chrome

# With custom config
npx playwright test --config=configs/online-boutique.config.ts

# Headed mode for debugging
npx playwright test --headed --project=online-boutique-chrome
```

### Continuous Monitoring

```bash
# Single run
npx playwright test

# Continuous monitoring (5 minute intervals)
while true; do npx playwright test; sleep 300; done

# Critical path only
npx playwright test --project=critical-path-chrome

# Custom configuration
npx playwright test \
  --config=configs/online-boutique.config.ts \
  --project=critical-path-chrome
```

## Test Utilities

### TestHelpers Class

Provides common functionality:

```typescript
// Trace context setup
const traceId = await TestHelpers.setupPageWithTracing(page, 'test-name');

// Navigation helpers
await TestHelpers.waitForHomepage(page);
await TestHelpers.navigateToProduct(page, 0);
await TestHelpers.addToCart(page);
await TestHelpers.navigateToCart(page);
await TestHelpers.proceedToCheckout(page);

// Form helpers
await TestHelpers.fillCheckoutForm(page);
await TestHelpers.completeCheckout(page);

// Debugging helpers
await TestHelpers.capturePageState(page, 'context');
await TestHelpers.waitForNetworkIdle(page);
const hasError = await TestHelpers.handleCommonErrors(page);
```

### Trace Context Extractor

Extracts trace IDs from multiple sources:

```typescript
// From test annotations
const traceId = this.extractFromAnnotations(test);

// From network logs
const traceId = await this.extractFromNetworkLogs(result);

// From console logs
const traceId = this.extractFromConsoleLogs(result);

// From test attachments
const traceId = this.extractFromAttachments(result);

// Generate synthetic ID
const traceId = this.generateSyntheticTraceId(test);
```

### Webhook Client

Secure webhook delivery:

```typescript
// Send failure payload
await this.webhookClient.sendPayload(payload);

// With retry logic
const client = new WebhookClient({
  url: webhookUrl,
  secret: webhookSecret,
  maxRetries: 3,
  retryDelay: 1000,
});
```

## Debugging and Troubleshooting

### Test Failures

1. **Check Test Output**: Review console logs and error messages
2. **View Screenshots**: Examine failure screenshots in `test-results/`
3. **Watch Videos**: Review video recordings of failed tests
4. **Trace Analysis**: Use Playwright trace viewer for detailed analysis
5. **Network Logs**: Check network requests and responses

### Trace Correlation Issues

1. **Verify Headers**: Check that trace headers are being sent
2. **Backend Logs**: Confirm backend services are receiving trace context
3. **Trace ID Format**: Validate trace ID format (32-character hex)
4. **Propagation**: Ensure trace context propagates across service calls

### Webhook Delivery Issues

1. **Network Connectivity**: Test webhook endpoint accessibility
2. **Authentication**: Verify webhook secret configuration
3. **Payload Format**: Check payload structure and content
4. **Retry Logic**: Review retry attempts and backoff behavior

### Common Issues

```bash
# Test timeouts
# Solution: Increase timeout values or check application performance

# Element not found
# Solution: Update selectors or add wait conditions

# Network errors
# Solution: Check application availability and network connectivity

# Trace extraction failures
# Solution: Verify trace context injection and propagation
```

## Performance Considerations

### Test Execution

- **Parallel Execution**: Disabled for better trace correlation
- **Retry Strategy**: 2-3 retries with exponential backoff
- **Timeout Management**: Aggressive timeouts for critical paths
- **Resource Cleanup**: Automatic cleanup of artifacts and resources

### Artifact Management

- **Video Recording**: Only on failure to reduce storage
- **Screenshots**: Only on failure for debugging
- **Trace Files**: Retained for failure analysis
- **Log Files**: Structured logging with correlation IDs

### Monitoring Impact

- **Minimal Overhead**: Reporter only activates on failures
- **Efficient Extraction**: Multiple fallback methods for trace IDs
- **Async Operations**: Non-blocking webhook transmission
- **Resource Limits**: Configurable limits for artifacts and logs

## Integration with Auto-Heal Agent

### Workflow Integration

1. **Test Execution**: Playwright runs synthetic tests
2. **Failure Detection**: Custom reporter detects failures
3. **Trace Correlation**: Trace ID extracted and included
4. **Webhook Delivery**: Failure payload sent to Auto-Heal Agent
5. **Root Cause Analysis**: Agent correlates with backend telemetry
6. **Remediation**: Agent proposes and executes fixes
7. **Verification**: Tests re-run to confirm resolution

### Data Flow

```
Playwright Test → Custom Reporter → Webhook → Auto-Heal Agent
     ↓                ↓              ↓            ↓
Trace Context → Failure Payload → HTTP POST → RCA Engine
     ↓                ↓              ↓            ↓
HTTP Headers → Trace ID → Correlation → Telemetry Query
```

### Monitoring Dashboard

The test suite provides data for monitoring:

- **Test Success Rate**: Percentage of passing tests
- **Failure Categories**: Types of failures detected
- **Response Times**: Application performance metrics
- **Trace Correlation**: Success rate of trace correlation
- **Webhook Delivery**: Success rate of failure notifications

## Best Practices

### Test Design

1. **Robust Selectors**: Use multiple selector strategies
2. **Wait Strategies**: Implement proper wait conditions
3. **Error Handling**: Graceful handling of missing elements
4. **Trace Injection**: Always inject trace context
5. **State Verification**: Verify application state at each step

### Maintenance

1. **Regular Updates**: Keep selectors and expectations current
2. **Performance Monitoring**: Monitor test execution times
3. **Artifact Cleanup**: Regular cleanup of old artifacts
4. **Configuration Review**: Periodic review of test configuration
5. **Dependency Updates**: Keep Playwright and dependencies updated

### Monitoring

1. **Continuous Execution**: Run tests at regular intervals
2. **Alert Thresholds**: Set appropriate failure rate thresholds
3. **Trend Analysis**: Monitor failure trends over time
4. **Correlation Analysis**: Analyze trace correlation success
5. **Performance Baselines**: Establish performance baselines

## Troubleshooting Guide

### Test Environment Issues

```bash
# Check Online Boutique availability
curl -I $ONLINE_BOUTIQUE_URL

# Verify webhook endpoint
curl -X POST $AUTO_HEAL_WEBHOOK_URL -d '{"test": "connectivity"}'

# Test trace context injection
npx playwright test --debug tests/online-boutique/homepage.spec.ts
```

### Configuration Issues

```bash
# Validate configuration
npx playwright test --list --config=configs/online-boutique.config.ts

# Check environment variables
env | grep -E "(ONLINE_BOUTIQUE|AUTO_HEAL)"

# Verify project setup
npm run build && npm test -- --dry-run
```

### Debugging Commands

```bash
# Run single test with full output
npx playwright test tests/online-boutique/homepage.spec.ts --headed --debug

# Generate trace for analysis
npx playwright test --trace=on tests/critical-path/complete-user-journey.spec.ts

# View test report
npx playwright show-report

# Analyze trace file
npx playwright show-trace test-results/trace.zip
```

This comprehensive test suite provides robust synthetic monitoring for Online Boutique with seamless integration into the Auto-Heal Agent workflow, enabling automated incident detection and response.