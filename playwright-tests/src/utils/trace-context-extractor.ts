import { TestCase, TestResult } from '@playwright/test/reporter';
import crypto from 'crypto';

/**
 * Extracts W3C Trace Context from browser sessions and Playwright test context
 * Implements W3C Trace Context specification for distributed tracing
 */
export class TraceContextExtractor {
  private static readonly TRACE_PARENT_HEADER = 'traceparent';
  private static readonly TRACE_STATE_HEADER = 'tracestate';

  /**
   * Extracts trace ID from test case and result
   * Attempts multiple extraction methods in order of preference
   */
  async extractTraceId(test: TestCase, result: TestResult): Promise<string> {
    // Method 1: Try to extract from test annotations or metadata
    const annotationTraceId = this.extractFromAnnotations(test);
    if (annotationTraceId) {
      return annotationTraceId;
    }

    // Method 2: Try to extract from browser network logs
    const networkTraceId = await this.extractFromNetworkLogs(result);
    if (networkTraceId) {
      return networkTraceId;
    }

    // Method 3: Try to extract from browser console logs
    const consoleTraceId = this.extractFromConsoleLogs(result);
    if (consoleTraceId) {
      return consoleTraceId;
    }

    // Method 4: Try to extract from test attachments
    const attachmentTraceId = this.extractFromAttachments(result);
    if (attachmentTraceId) {
      return attachmentTraceId;
    }

    // Method 5: Generate a synthetic trace ID for correlation
    return this.generateSyntheticTraceId(test);
  }

  /**
   * Extracts trace ID from test annotations
   */
  private extractFromAnnotations(test: TestCase): string | null {
    // Look for trace ID in test annotations
    for (const annotation of test.annotations) {
      if (annotation.type === 'trace-id' || annotation.type === 'traceId') {
        return annotation.description || null;
      }
    }

    // Look for trace ID in test title or location
    const traceIdMatch = test.title.match(/trace[_-]?id[:\s]+([a-f0-9]{32})/i);
    if (traceIdMatch) {
      return traceIdMatch[1];
    }

    return null;
  }

  /**
   * Extracts trace ID from browser network logs
   * This would require access to browser network activity
   */
  private async extractFromNetworkLogs(result: TestResult): Promise<string | null> {
    // In a real implementation, this would parse network logs from the browser
    // For now, we'll look for trace information in test attachments
    
    const networkLogAttachment = result.attachments.find(
      attachment => attachment.name === 'network-log' || attachment.name === 'har'
    );

    if (networkLogAttachment && networkLogAttachment.body) {
      try {
        const logContent = networkLogAttachment.body.toString();
        
        // Look for W3C traceparent header in network logs
        const traceparentMatch = logContent.match(/traceparent["\s:]+([0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2})/i);
        if (traceparentMatch) {
          return this.parseTraceParent(traceparentMatch[1]);
        }

        // Look for Google Cloud Trace format
        const gcpTraceMatch = logContent.match(/x-cloud-trace-context["\s:]+([0-9a-f]{32})/i);
        if (gcpTraceMatch) {
          return gcpTraceMatch[1];
        }
      } catch (error) {
        console.warn('[TraceContextExtractor] Failed to parse network logs:', error);
      }
    }

    return null;
  }

  /**
   * Extracts trace ID from browser console logs
   */
  private extractFromConsoleLogs(result: TestResult): string | null {
    const consoleLogAttachment = result.attachments.find(
      attachment => attachment.name === 'console-log' || attachment.name === 'stdout'
    );

    if (consoleLogAttachment && consoleLogAttachment.body) {
      try {
        const logContent = consoleLogAttachment.body.toString();
        
        // Look for trace ID patterns in console output
        const patterns = [
          /trace[_-]?id[:\s]+([a-f0-9]{32})/i,
          /tracing[_-]?id[:\s]+([a-f0-9]{32})/i,
          /request[_-]?id[:\s]+([a-f0-9]{32})/i,
        ];

        for (const pattern of patterns) {
          const match = logContent.match(pattern);
          if (match) {
            return match[1];
          }
        }
      } catch (error) {
        console.warn('[TraceContextExtractor] Failed to parse console logs:', error);
      }
    }

    return null;
  }

  /**
   * Extracts trace ID from test result attachments
   */
  private extractFromAttachments(result: TestResult): string | null {
    // Look through all attachments for trace information
    for (const attachment of result.attachments) {
      if (attachment.body) {
        try {
          const content = attachment.body.toString();
          
          // Look for JSON with trace information
          if (attachment.contentType === 'application/json') {
            const jsonData = JSON.parse(content);
            
            // Common trace ID field names
            const traceFields = ['traceId', 'trace_id', 'tracing_id', 'requestId', 'request_id'];
            for (const field of traceFields) {
              if (jsonData[field] && typeof jsonData[field] === 'string') {
                return jsonData[field];
              }
            }
          }
        } catch (error) {
          // Ignore parsing errors for non-JSON attachments
        }
      }
    }

    return null;
  }

  /**
   * Generates a synthetic trace ID for correlation when no trace ID is found
   */
  private generateSyntheticTraceId(test: TestCase): string {
    // Create a deterministic trace ID based on test information
    const testInfo = `${test.location.file}:${test.location.line}:${test.title}:${Date.now()}`;
    const hash = crypto.createHash('md5').update(testInfo).digest('hex');
    
    // Format as a 32-character hex string (similar to Google Cloud Trace format)
    return hash;
  }

  /**
   * Parses W3C traceparent header to extract trace ID
   * Format: version-trace_id-parent_id-trace_flags
   */
  private parseTraceParent(traceparent: string): string | null {
    const parts = traceparent.split('-');
    if (parts.length === 4) {
      // Return the trace_id part (32 hex characters)
      const traceId = parts[1];
      if (traceId && traceId.length === 32 && /^[0-9a-f]+$/i.test(traceId)) {
        return traceId;
      }
    }
    return null;
  }

  /**
   * Injects trace context into browser page for correlation
   * This method can be called from test setup to ensure trace propagation
   */
  static async injectTraceContext(page: any, traceId?: string): Promise<string> {
    const actualTraceId = traceId || crypto.randomBytes(16).toString('hex');
    const parentId = crypto.randomBytes(8).toString('hex');
    const flags = '01'; // Sampled
    
    const traceparent = `00-${actualTraceId}-${parentId}-${flags}`;
    
    // Inject trace context into page headers for outgoing requests
    await page.setExtraHTTPHeaders({
      'traceparent': traceparent,
      'x-cloud-trace-context': `${actualTraceId}/1;o=1`
    });

    // Inject trace context into page JavaScript context
    await page.addInitScript(`
      window.__TRACE_CONTEXT__ = {
        traceId: '${actualTraceId}',
        parentId: '${parentId}',
        traceparent: '${traceparent}'
      };
      
      // Override fetch to include trace headers
      const originalFetch = window.fetch;
      window.fetch = function(...args) {
        const [url, options = {}] = args;
        const headers = new Headers(options.headers);
        
        if (!headers.has('traceparent')) {
          headers.set('traceparent', '${traceparent}');
        }
        if (!headers.has('x-cloud-trace-context')) {
          headers.set('x-cloud-trace-context', '${actualTraceId}/1;o=1');
        }
        
        return originalFetch(url, { ...options, headers });
      };
    `);

    return actualTraceId;
  }

  /**
   * Validates trace ID format
   */
  static isValidTraceId(traceId: string): boolean {
    return /^[0-9a-f]{32}$/i.test(traceId);
  }
}