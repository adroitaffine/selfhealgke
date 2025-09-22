# Kubernetes Manifests

Kubernetes deployment manifests for the GKE Auto-Heal Agent and supporting infrastructure.

## Structure

```
kubernetes/
├── namespace.yaml          # Dedicated namespace
├── agents/                 # Agent deployments
├── mcp-servers/           # MCP server deployments  
├── online-boutique/       # Online Boutique application
├── monitoring/            # Observability stack
├── secrets/               # Secret management
└── rbac/                  # RBAC configurations
```

## Deployment Order

1. **Namespace and RBAC** - Create namespace and service accounts
2. **Secrets** - Deploy API keys and credentials
3. **Online Boutique** - Deploy target application
4. **MCP Servers** - Deploy tool integration servers
5. **Agents** - Deploy core agents
6. **Monitoring** - Deploy observability components

## Key Components

### Agents (`agents/`)
- `orchestrator-agent.yaml` - Main workflow coordinator
- `rca-agent.yaml` - Root cause analysis agent
- `remediation-agent.yaml` - Remediation execution agent
- `chatbot-agent.yaml` - Human approval interface
- `audit-agent.yaml` - Audit trail management

### MCP Servers (`mcp-servers/`)
- `gcp-observability-server.yaml` - Cloud APIs integration
- `kubernetes-ops-server.yaml` - GKE operations
- `vertex-ai-server.yaml` - Gemini LLM integration
- `playwright-server.yaml` - Test execution
- `chatbot-server.yaml` - Web UI server

### Online Boutique (`online-boutique/`)
- Complete microservices deployment
- Service mesh configuration
- Observability instrumentation
- Load balancer and ingress

## Security Configuration

### Service Accounts
- Dedicated service accounts per component
- Workload Identity integration
- Minimal RBAC permissions

### Network Policies
- Ingress/egress traffic restrictions
- Service-to-service communication rules
- External API access controls

### Pod Security
- Security contexts and constraints
- Resource limits and requests
- Health checks and probes

## Deployment

```bash
# Deploy everything
kubectl apply -f kubernetes/

# Deploy specific components
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/rbac/
kubectl apply -f kubernetes/secrets/
kubectl apply -f kubernetes/online-boutique/
kubectl apply -f kubernetes/mcp-servers/
kubectl apply -f kubernetes/agents/
kubectl apply -f kubernetes/monitoring/
```

## Monitoring

- Prometheus metrics collection
- Grafana dashboards
- Alert manager configuration
- Log aggregation and analysis

## Dependencies

- Kubernetes 1.28+
- Istio service mesh (optional)
- Prometheus operator
- Grafana operator