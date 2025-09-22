# Online Boutique Deployment Guide

This guide covers the deployment and configuration of Google's Online Boutique microservices demo application with enhanced observability for the GKE Auto-Heal Agent integration.

## Overview

Online Boutique is a cloud-native microservices demo application that consists of 11 microservices written in different languages. For the Auto-Heal Agent integration, we've enhanced it with:

- **Enhanced OpenTelemetry instrumentation** for distributed tracing
- **Structured logging** with correlation IDs
- **Prometheus metrics** with auto-heal specific labels
- **Health check endpoints** for synthetic monitoring
- **Failure injection capabilities** for testing

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Online Boutique Services                     │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Go) ←→ Cart (C#) ←→ Product Catalog (Go)           │
│       ↓              ↓              ↓                          │
│  Checkout (Go) ←→ Payment (Node.js) ←→ Shipping (Go)          │
│       ↓              ↓              ↓                          │
│  Email (Python) ←→ Currency (Node.js) ←→ Recommendation (Py)  │
│       ↓              ↓              ↓                          │
│  Ad Service (Java) ←→ Load Generator (Python/Locust)          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Observability Stack                          │
├─────────────────────────────────────────────────────────────────┤
│  OpenTelemetry Collector → Jaeger + Google Cloud Trace        │
│  Fluent Bit → Google Cloud Logging                            │
│  Prometheus → Metrics Collection                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Auto-Heal Agent Integration                   │
├─────────────────────────────────────────────────────────────────┤
│  Playwright Tests → Custom Reporter → Webhook                 │
│  Trace Correlation → RCA Agent → Remediation                  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (GKE recommended)
- kubectl configured to access the cluster
- kustomize (optional, kubectl has built-in support)
- Sufficient cluster resources (minimum 4 vCPUs, 8GB RAM)

## Quick Deployment

### Option 1: Using kubectl (Recommended)

```bash
# Deploy Online Boutique with auto-heal integration
kubectl apply -k kubernetes/online-boutique/overlays/auto-heal/

# Wait for deployments to be ready
kubectl wait --for=condition=available --timeout=600s deployment --all -n online-boutique

# Verify the deployment
kubectl get pods -n online-boutique

# Check deployment status
kubectl get deployments -n online-boutique
```

### Option 2: Manual Deployment

```bash
# Deploy using kubectl with kustomize
kubectl apply -k kubernetes/online-boutique/overlays/auto-heal/

# Wait for deployments to be ready
kubectl wait --for=condition=available --timeout=600s deployment --all -n online-boutique

# Verify services are running
kubectl get pods -n online-boutique
```

## Configuration Details

### Environment Variables

The deployment includes auto-heal specific environment variables:

```yaml
# Auto-heal configuration
AUTO_HEAL_ENABLED: "true"
TRACE_SAMPLING_RATE: "1.0"  # 100% sampling for synthetic tests
SYNTHETIC_TEST_HEADER: "X-Auto-Heal-Test"

# Service-specific configuration
REDIS_TIMEOUT_SECONDS: "5"  # Cart service
PAYMENT_TIMEOUT_MS: "5000"  # Payment service
CHECKOUT_TIMEOUT_SECONDS: "30"  # Checkout service
```

### OpenTelemetry Configuration

```yaml
# OTEL environment variables
OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector.observability:4317"
OTEL_SERVICE_NAME: "online-boutique-{service-name}"
OTEL_RESOURCE_ATTRIBUTES: "service.namespace=online-boutique,deployment.environment=auto-heal"
```

### Health Check Endpoints

All services are configured with health check endpoints:

- **Liveness Probe**: `GET /health` on port 8080
- **Readiness Probe**: `GET /ready` on port 8080
- **Metrics Endpoint**: `GET /metrics` on port 8080 (if available)

## Accessing the Application

### External Access

After deployment, the application can be accessed via:

1. **LoadBalancer** (if supported by your cluster):
   ```bash
   kubectl get service frontend-external -n online-boutique
   # Access via the EXTERNAL-IP
   ```

2. **Port Forward** (for local development):
   ```bash
   kubectl port-forward -n online-boutique service/frontend-external 8080:80
   # Access via http://localhost:8080
   ```

3. **Ingress** (if configured):
   ```bash
   kubectl get ingress -n online-boutique
   # Access via the configured hostname
   ```

### Internal Access

For synthetic testing and monitoring:

```bash
# Health check service
kubectl port-forward -n online-boutique service/online-boutique-health 8081:8081

# Direct service access
kubectl port-forward -n online-boutique service/frontend 8080:80
```

## Observability Features

### Distributed Tracing

- **Trace Context Propagation**: W3C Trace Context headers are propagated across all services
- **Synthetic Test Correlation**: Playwright tests inject trace IDs for correlation
- **Export Targets**: Jaeger and Google Cloud Trace

Example trace context injection:
```bash
curl -H "traceparent: 00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01" \
     -H "tracestate: auto-heal=synthetic-test" \
     http://localhost:8080/
```

### Metrics Collection

- **Prometheus ServiceMonitor**: Automatic metrics scraping
- **Custom Metrics**: Auto-heal specific metrics with labels
- **Performance Metrics**: Request rates, error rates, latency percentiles

### Structured Logging

- **Fluent Bit Configuration**: Centralized log collection
- **Correlation IDs**: Request tracking across services
- **Auto-heal Labels**: Automatic labeling for log correlation

## Testing Integration

### Playwright Test Configuration

The deployment is optimized for Playwright synthetic testing:

```typescript
// Test configuration for Online Boutique
export default defineConfig({
  use: {
    baseURL: process.env.ONLINE_BOUTIQUE_URL || 'http://localhost:8080',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  reporter: [
    ['./src/reporters/custom-failure-reporter.ts', {
      webhookUrl: process.env.AUTO_HEAL_WEBHOOK_URL,
      webhookSecret: process.env.AUTO_HEAL_WEBHOOK_SECRET,
    }]
  ],
});
```

### Critical User Journeys

The application supports testing of these critical flows:

1. **Homepage Load**: Product catalog display and navigation
2. **Product Browsing**: Search, filtering, product details
3. **Shopping Cart**: Add/remove items, quantity updates
4. **Checkout Flow**: Shipping, payment, order confirmation

### Failure Scenarios

Built-in failure injection for testing:

```yaml
# Environment variables for failure injection
FAILURE_INJECTION_RATE: "0.0"  # 0% by default
CHAOS_MONKEY_ENABLED: "false"  # Disabled by default
```

## Monitoring and Alerting

### Prometheus Rules

The deployment includes PrometheusRules for auto-heal monitoring:

- **Service Availability**: Alert when services are down
- **High Error Rate**: Alert on 5% error rate for 2 minutes
- **High Latency**: Alert on 95th percentile > 2 seconds
- **Service-Specific**: Cart Redis failures, payment timeouts

### Grafana Dashboard

A pre-configured dashboard is available for monitoring:

- Service availability and health
- Request rates and error rates
- Response time percentiles
- Business metrics (conversion rates, cart abandonment)

## Troubleshooting

### Common Issues

1. **Pods Not Starting**:
   ```bash
   kubectl describe pods -n online-boutique
   kubectl logs -l app=frontend -n online-boutique
   ```

2. **Service Discovery Issues**:
   ```bash
   kubectl get endpoints -n online-boutique
   kubectl describe service frontend -n online-boutique
   ```

3. **Observability Data Missing**:
   ```bash
   # Check OTEL configuration
   kubectl get configmap otel-config -n online-boutique -o yaml
   
   # Check ServiceMonitor
   kubectl get servicemonitor -n online-boutique
   
   # Verify metrics endpoints
   kubectl exec -n online-boutique deployment/frontend -- wget -qO- localhost:8080/metrics
   ```

4. **Performance Issues**:
   ```bash
   kubectl top pods -n online-boutique
   kubectl describe hpa -n online-boutique
   ```

### Verification Commands

```bash
# Verify all services are running
kubectl get pods -n online-boutique

# Check service endpoints
kubectl get endpoints -n online-boutique

# Verify observability configuration
kubectl get servicemonitor -n online-boutique

# Test health endpoints
kubectl exec -n online-boutique deployment/frontend -- wget -qO- localhost:8080/health

# Generate test traffic (manual)
curl -H "X-Auto-Heal-Test: true" http://localhost:8080/
```

### Log Analysis

```bash
# View structured logs
kubectl logs -l app=frontend -n online-boutique --tail=100

# Search for auto-heal correlation
kubectl logs -l auto-heal.gke/monitored=true -n online-boutique | grep "auto-heal"

# Check for trace IDs
kubectl logs -l app=frontend -n online-boutique | grep -E "trace[_-]?id"
```

## Cleanup

### Remove Deployment

```bash
# Manual cleanup
kubectl delete -k kubernetes/online-boutique/overlays/auto-heal/
kubectl delete namespace online-boutique
```

### Verify Cleanup

```bash
kubectl get all -n online-boutique
kubectl get namespace online-boutique
```

## Next Steps

After successful deployment:

1. **Configure Playwright Tests**: Update test configuration with the application URL
2. **Set Up Monitoring**: Configure Prometheus and Grafana for observability
3. **Deploy Auto-Heal Agents**: Deploy the MCP servers and agents
4. **Run Synthetic Tests**: Execute Playwright tests to generate failure scenarios
5. **Verify Integration**: Ensure trace correlation and webhook delivery work correctly

## References

- [Online Boutique Repository](https://github.com/GoogleCloudPlatform/microservices-demo)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Playwright Testing](https://playwright.dev/)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)