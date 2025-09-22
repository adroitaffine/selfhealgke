import { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
import { WebhookClient } from '../utils/webhook-client';
import { TraceContextExtractor } from '../utils/trace-context-extractor';

export interface FailurePayload {
  testTitle: string;
  status: 'failed' | 'timedOut';
  error: {
    message: string;
    stack: string;
    type: string;
  };
  retries: number;
  traceID: string;
  videoUrl?: string;
  traceUrl?: string;
  timestamp: string;
}

export interface ReporterOptions {
  webhookUrl: string;
  webhookSecret?: string;
  maxRetries?: number;
  retryDelay?: number;
}

/**
 * Custom Playwright reporter that captures comprehensive failure data
 * and sends it to the Auto-Heal Agent webhook endpoint
 */
export class CustomFailureReporter implements Reporter {
  private webhookClient: WebhookClient;
  private traceExtractor: TraceContextExtractor;
  private options: Required<ReporterOptions>;

  constructor(options: ReporterOptions) {
    this.options = {
      webhookUrl: options.webhookUrl,
      webhookSecret: options.webhookSecret || process.env.WEBHOOK_SECRET || '',
      maxRetries: options.maxRetries || 3,
      retryDelay: options.retryDelay || 1000,
    };

    this.webhookClient = new WebhookClient({
      url: this.options.webhookUrl,
      secret: this.options.webhookSecret,
      maxRetries: this.options.maxRetries,
      retryDelay: this.options.retryDelay,
    });

    this.traceExtractor = new TraceContextExtractor();
  }

  /**
   * Called when a test ends (passes, fails, or times out)
   */
  async onTestEnd(test: TestCase, result: TestResult): Promise<void> {
    // Only process failed or timed out tests
    if (result.status !== 'failed' && result.status !== 'timedOut') {
      return;
    }

    try {
      const payload = await this.createFailurePayload(test, result);
      await this.webhookClient.sendPayload(payload);
      
      console.log(`[CustomFailureReporter] Sent failure payload for test: ${test.title}`);
    } catch (error) {
      console.error(`[CustomFailureReporter] Failed to send payload for test: ${test.title}`, error);
    }
  }

  /**
   * Creates a comprehensive failure payload from test case and result
   */
  private async createFailurePayload(test: TestCase, result: TestResult): Promise<FailurePayload> {
    // Extract trace ID from the test context or browser session
    const traceID = await this.traceExtractor.extractTraceId(test, result);
    
    // Get error details
    const error = result.error || { message: 'Unknown error', stack: '', name: 'UnknownError' };
    
    // Construct URLs for video and trace artifacts
    const videoUrl = this.getVideoUrl(result);
    const traceUrl = this.getTraceUrl(result);

    const payload: FailurePayload = {
      testTitle: test.title,
      status: result.status as 'failed' | 'timedOut',
      error: {
        message: error.message || 'Unknown error',
        stack: error.stack || '',
        type: (error as any).name || 'UnknownError',
      },
      retries: result.retry,
      traceID,
      videoUrl,
      traceUrl,
      timestamp: new Date().toISOString(),
    };

    return payload;
  }

  /**
   * Extracts video URL from test result attachments
   */
  private getVideoUrl(result: TestResult): string | undefined {
    const videoAttachment = result.attachments.find(
      attachment => attachment.name === 'video' && attachment.path
    );
    
    if (videoAttachment?.path) {
      // Convert local path to accessible URL (this would be configured based on your storage setup)
      return this.convertPathToUrl(videoAttachment.path, 'video');
    }
    
    return undefined;
  }

  /**
   * Extracts trace URL from test result attachments
   */
  private getTraceUrl(result: TestResult): string | undefined {
    const traceAttachment = result.attachments.find(
      attachment => attachment.name === 'trace' && attachment.path
    );
    
    if (traceAttachment?.path) {
      // Convert local path to accessible URL
      return this.convertPathToUrl(traceAttachment.path, 'trace');
    }
    
    return undefined;
  }

  /**
   * Converts local file paths to accessible URLs
   * This would be implemented based on your artifact storage strategy
   */
  private convertPathToUrl(filePath: string, type: 'video' | 'trace'): string {
    // In a real implementation, this would upload to GCS or similar and return the public URL
    // For now, return a placeholder URL structure
    const filename = filePath.split('/').pop();
    const baseUrl = process.env.ARTIFACT_BASE_URL || 'https://artifacts.example.com';
    return `${baseUrl}/${type}s/${filename}`;
  }

  /**
   * Called when all tests have finished running
   */
  async onEnd(result: FullResult): Promise<void> {
    console.log(`[CustomFailureReporter] Test run completed with status: ${result.status}`);
  }
}

export default CustomFailureReporter;