import crypto from 'crypto';
import https from 'https';
import { FailurePayload } from '../reporters/custom-failure-reporter';

export interface WebhookClientOptions {
  url: string;
  secret: string;
  maxRetries: number;
  retryDelay: number;
  timeout?: number;
}

/**
 * Secure webhook client for payload transmission with retry logic
 * Implements exponential backoff and HMAC signature verification
 */
export class WebhookClient {
  private options: Required<WebhookClientOptions>;

  constructor(options: WebhookClientOptions) {
    this.options = {
      ...options,
      timeout: options.timeout || 10000, // 10 second timeout
    };
  }

  /**
   * Sends a failure payload to the webhook endpoint with retry logic
   */
  async sendPayload(payload: FailurePayload): Promise<void> {
    let lastError: Error | null = null;
    
    for (let attempt = 0; attempt <= this.options.maxRetries; attempt++) {
      try {
        await this.sendRequest(payload);
        return; // Success, exit retry loop
      } catch (error) {
        lastError = error as Error;
        
        if (attempt < this.options.maxRetries) {
          const delay = this.calculateBackoffDelay(attempt);
          console.log(`[WebhookClient] Attempt ${attempt + 1} failed, retrying in ${delay}ms...`);
          await this.sleep(delay);
        }
      }
    }

    throw new Error(`Failed to send webhook after ${this.options.maxRetries + 1} attempts. Last error: ${lastError?.message}`);
  }

  /**
   * Sends a single HTTP request to the webhook endpoint
   */
  private async sendRequest(payload: FailurePayload): Promise<void> {
    return new Promise((resolve, reject) => {
      const payloadJson = JSON.stringify(payload);
      const signature = this.generateSignature(payloadJson);
      
      const url = new URL(this.options.url);
      const requestOptions = {
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname + url.search,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payloadJson),
          'X-Webhook-Signature': signature,
          'X-Webhook-Timestamp': Date.now().toString(),
          'User-Agent': 'Playwright-Auto-Heal-Reporter/1.0',
        },
        timeout: this.options.timeout,
      };

      const req = https.request(requestOptions, (res) => {
        let responseBody = '';
        
        res.on('data', (chunk) => {
          responseBody += chunk;
        });

        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            resolve();
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${responseBody}`));
          }
        });
      });

      req.on('error', (error) => {
        reject(new Error(`Request failed: ${error.message}`));
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timeout after ${this.options.timeout}ms`));
      });

      // Write the payload and end the request
      req.write(payloadJson);
      req.end();
    });
  }

  /**
   * Generates HMAC-SHA256 signature for webhook payload verification
   */
  private generateSignature(payload: string): string {
    if (!this.options.secret) {
      return '';
    }

    const hmac = crypto.createHmac('sha256', this.options.secret);
    hmac.update(payload);
    return `sha256=${hmac.digest('hex')}`;
  }

  /**
   * Calculates exponential backoff delay with jitter
   */
  private calculateBackoffDelay(attempt: number): number {
    const baseDelay = this.options.retryDelay;
    const exponentialDelay = baseDelay * Math.pow(2, attempt);
    
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 0.1 * exponentialDelay;
    
    return Math.min(exponentialDelay + jitter, 30000); // Cap at 30 seconds
  }

  /**
   * Sleep utility for retry delays
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Validates webhook configuration
   */
  static validateConfig(options: WebhookClientOptions): void {
    if (!options.url) {
      throw new Error('Webhook URL is required');
    }

    try {
      new URL(options.url);
    } catch {
      throw new Error('Invalid webhook URL format');
    }

    if (options.maxRetries < 0) {
      throw new Error('maxRetries must be non-negative');
    }

    if (options.retryDelay < 0) {
      throw new Error('retryDelay must be non-negative');
    }
  }
}