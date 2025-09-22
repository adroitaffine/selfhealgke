# Playwright Tests with Custom Auto-Heal Reporter

This directory contains Playwright end-to-end tests for the Online Boutique application with a custom failure reporter that integrates with the GKE Auto-Heal Agent.

## Features

### Custom Failure Reporter

The custom reporter (`src/reporters/custom-failure-reporter.ts`) provides:

- **Comprehensive Failure Capture**: Captures test title, status, error details, stack traces, and retry counts
- **W3C Trace Context Integration**: Extracts distributed trace IDs from browser sessions for correlation
- **Secure Webhook Transmission**: Sends failure payloads to the Auto-Heal Agent with HMAC signature verification
- **Retry Logic**: Implements exponential backoff for reliable payload delivery
- **Artifact Management**: Captures and links video recordings and trace files

### Trace Context Extraction

The `TraceContextExtractor` class supports multiple methods for extracting trace IDs:

1. **Test Annotations**: From Playwright test metadata
2. **Network Logs**: From browser network activity and HAR files
3. **Console Logs**: From browser console output
4. **Test Attachments**: From JSON attachments and test artifacts
5. **Synthetic Generation**: Creates deterministic trace IDs for correlation

### Test Utilities

The `TestHelpers` class provides:

- **Trace Context Injection**: Automatically injects W3C trace context into browser sessions
- **Online Boutique Navigation**: Helper methods for common user journeys
- **Error Handling**: Graceful handling of common error scenarios
- **State Capture**: Debugging utilities for test failures

## Configuration

### Environment Variables

```bash
# Required: Online Boutique application URL
export ONLINE_BOUTIQUE_URL="http://your-online-boutique-url"

# Required: Auto-Heal Agent webhook endpoint
export AUTO_HEAL_WEBHOOK_URL="https://your-auto-heal-agent/webhook/failure"

# Optional: Webhook secret for HMAC signature verification
export AUTO_HEAL_WEBHOOK_SECRET="your-webhook-secret"

# Optional: Artifact storage base URL
export ARTIFACT_BASE_URL="https://your-artifact-storage"
```

### Playwright Configuration

The reporter is configured in `playwright.config.ts`:

```typescript
reporter: [
  ['html'],
  ['json', { outputFile: 'test-results/results.json' }],
  ['./src/reporters/custom-failure-reporter.ts', { 
    webhookUrl: process.env.AUTO_HEAL_WEBHOOK_URL || 'http://localhost:8080/webhook/failure',
    webhookSecret: process.env.AUTO_HEAL_WEBHOOK_SECRET,
    maxRetries: 3,
    retryDelay: 1000,
  }]
],
```

## Usage

### Installation

```bash
# Install dependencies
npm install

# Install Playwright browsers
npm run install:browsers

# Install system dependencies (Linux only)
npm run install:deps
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests in headed mode
npm run test:headed

# Run tests with debug mode
npm run test:debug

# Run specific test suite
npx playwright test tests/online-boutique/

# Run critical path tests only
npx playwright test tests/critical-path/
```

### Building TypeScript

```bash
# Build TypeScript files
npm run build

# Build with watch mode
npm run build:watch
```

## Test Structure

### Homepage Tests (`tests/online-boutique/homepage.spec.ts`)

- Homepage loading verification
- Product catalog display
- Product navigation
- Search functionality (with potential failures for testing)

### Critical Path Tests (`tests/critical-path/checkout-flow.spec.ts`)

- Complete purchase journey
- Cart operations
- Payment error handling
- Network timeout scenarios

## Failure Payload Format

When a test fails, the custom reporter sends a JSON payload to the webhook:

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

## Integration with Auto-Heal Agent

The custom reporter integrates with the GKE Auto-Heal Agent by:

1. **Failure Detection**: Automatically detects test failures and timeouts
2. **Context Enrichment**: Adds trace IDs and artifact URLs for correlation
3. **Secure Transmission**: Uses HMAC signatures for webhook authentication
4. **Retry Logic**: Ensures reliable delivery with exponential backoff
5. **Artifact Linking**: Provides URLs to video recordings and trace files

## Trace Context Propagation

Tests automatically inject W3C trace context into browser sessions:

```typescript
// Automatic trace context injection
const traceId = await TestHelpers.setupPageWithTracing(page, 'test-name');

// Manual trace context injection
const traceId = await TraceContextExtractor.injectTraceContext(page);
```

This ensures that:
- HTTP requests from the browser include trace headers
- Backend services can correlate test requests with application logs
- The Auto-Heal Agent can query relevant telemetry data

## Debugging

### Viewing Test Results

```bash
# View HTML report
npm run test:report

# View test results JSON
cat test-results/results.json | jq
```

### Trace Files

Trace files are automatically captured on failure and can be viewed with:

```bash
# View trace in Playwright trace viewer
npx playwright show-trace test-results/trace.zip
```

### Video Recordings

Video recordings are captured for failed tests and stored in `test-results/`.

## Development

### Adding New Tests

1. Create test files in appropriate directories (`tests/online-boutique/` or `tests/critical-path/`)
2. Use `TestHelpers.setupPageWithTracing()` to enable trace context
3. Follow the existing patterns for error handling and assertions

### Extending the Reporter

The custom reporter can be extended by:

1. Modifying `FailurePayload` interface for additional data
2. Adding new extraction methods to `TraceContextExtractor`
3. Enhancing webhook security in `WebhookClient`
4. Adding new test utilities to `TestHelpers`

### Testing the Reporter

To test the custom reporter functionality:

1. Set up a webhook endpoint to receive payloads
2. Run tests that are designed to fail
3. Verify that failure payloads are received with correct trace IDs
4. Check that retry logic works for network failures

## Security Considerations

- **Webhook Signatures**: HMAC-SHA256 signatures verify payload authenticity
- **TLS Encryption**: All webhook communications use HTTPS
- **Secret Management**: Webhook secrets are managed via environment variables
- **Input Validation**: All extracted data is validated before transmission

## Performance

- **Minimal Overhead**: Reporter only activates on test failures
- **Efficient Extraction**: Trace ID extraction uses multiple fallback methods
- **Async Operations**: Webhook transmission doesn't block test execution
- **Resource Cleanup**: Temporary files and resources are properly cleaned up