# GKE Auto-Heal Agent

An intelligent, semi-autonomous AIOps solution for Google Kubernetes Engine that automates incident response by correlating synthetic test failures with backend telemetry data and proposing precise remediation actions through human-in-the-loop approval workflows.

## Architecture: Google Cloud First

This project follows a **Google Cloud First** architecture, leveraging official MCP (Model Context Protocol) servers from Google Cloud Platform and Microsoft, with minimal custom development for specialized functionality.

## Key Components

### Official MCP Servers (Google Cloud First)
- **Gemini Cloud Assist MCP**: Official Google Cloud server for GCP operations and AI analysis
- **GKE MCP**: Official Google Cloud server for Kubernetes operations
- **Playwright MCP**: Official Microsoft server for browser automation
- **Kubernetes MCP**: Community server for kubectl operations

### Custom Components
- **GCP Observability MCP**: Specialized server for Online Boutique observability patterns
- **Agents**: Root Cause Analysis, Remediation, and Approval agents
- **Playwright Tests**: Synthetic monitoring for Online Boutique user journeys

## High-Level Architecture Overview

This section describes the overall architecture of the GKE Auto-Heal Agent system, including its main components and data flow.

### Core Components
- **Agents** (Python, in `agents/`):
  - **Orchestrator Agent**: Coordinates health monitoring, receives Playwright failure notifications, manages incident response, and orchestrates RCA (Root Cause Analysis) and Remediation agents via A2A (Agent-to-Agent) communication.
  - **RCA Agent**: Discovers microservice topology from distributed traces/logs, analyzes failures, identifies critical paths and bottlenecks.
  - **Remediation Agent**: Executes automated remediation actions.
  - **Approval Agent**: Handles approval workflows for remediation.
  - **Audit Agent**: Tracks compliance, logs events, and provides audit trails.

- **A2A Services**: Each agent exposes a FastAPI-based REST service for inter-agent communication and external integration.

- **MCP Servers** (`mcp-servers/`):
  - **Official MCPs**: Integrate with Google Cloud and Microsoft servers for GCP operations, Kubernetes, and browser automation.
  - **Custom MCPs**: Specialized for observability and Online Boutique patterns.

- **Synthetic Monitoring** (`playwright-tests/`):
  - **Playwright Tests**: Simulate user journeys for Online Boutique, trigger incident workflows on failures.
  - **Custom Reporter**: Sends test results to the orchestrator via webhook.

- **Infrastructure** (`terraform/`):
  - **Terraform Modules**: Networking, GKE cluster, IAM, monitoring, security policies.
  - **Sentinel Policies**: Enforce compliance and security.

- **Observability Stack**:
  - **OpenTelemetry, Jaeger, Google Cloud Trace**: Distributed tracing.
  - **Fluent Bit, Cloud Logging**: Log aggregation.
  - **Prometheus**: Metrics collection.

- **Web Dashboard** (`web-dashboard/`):
  - Visualizes incidents, agent actions, and system health.

### High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Online Boutique Microservices
        A[Frontend (Go)] --> B[Cart (C#)]
        B --> C[Product Catalog (Go)]
        C --> D[Checkout (Go)]
        D --> E[Payment (Node.js)]
        E --> F[Shipping (Go)]
        F --> G[Email (Python)]
        G --> H[Currency (Node.js)]
        H --> I[Recommendation (Python)]
        I --> J[Ad Service (Java)]
        J --> K[Load Generator (Python/Locust)]
    end
    Online Boutique Microservices --> ObservabilityStack
    subgraph ObservabilityStack [Observability Stack]
        OT[OpenTelemetry, Jaeger, Cloud Trace]
        FL[Fluent Bit, Cloud Logging]
        PM[Prometheus]
    end
    ObservabilityStack --> AutoHealSystem
    subgraph AutoHealSystem [GKE Auto-Heal Agent System]
        PT[Playwright Tests] --> OA[Orchestrator Agent]
        OA --> RCA[RCA Agent]
        RCA --> RA[Remediation Agent]
        RA --> AA[Approval Agent]
        OA --> AA
        OA --> AU[Audit Agent]
    end
    AutoHealSystem --> MCPServers
    subgraph MCPServers [MCP Servers]
        GCP[Google Cloud MCP]
        K8S[Kubernetes MCP]
        PW[Playwright MCP]
        CustomMCP[Custom Observability MCP]
    end
    MCPServers --> DashboardInfra
    subgraph DashboardInfra [Web Dashboard / Terraform Infra]
        WD[Web Dashboard]
        TF[Terraform Infrastructure]
    end
```

## Development Setup

### 1. Python Virtual Environment & Package Installation

```bash
# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# For development (linting, tests, etc.)
pip install -r requirements-dev.txt
```

### 2. Node.js & Playwright Tests

```bash
# Install Node.js (recommended: use nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 22
nvm use 22

# Install Playwright test dependencies
cd playwright-tests
npm install
```

### 3. Running All Agents & Dashboard

To start all agent services and the web dashboard, run:

```bash
make run-agents
```

This will launch all A2A agent services in the background and the dashboard in the foreground.

## Quick Start

### Prerequisites
- Google Cloud Project with GKE enabled
- Node.js and npm (for MCP servers)
- Python 3.8+ (for agents)
- gcloud CLI installed and authenticated

### Installation

#### 1. Install Required SDKs

**Google Cloud SDK:**
```bash
# Install gcloud CLI and authenticate
curl https://sdk.cloud.google.com | bash
gcloud auth application-default login
gcloud config set project your-project-id

# Install GKE MCP server
curl -sSL https://raw.githubusercontent.com/GoogleCloudPlatform/gke-mcp/main/install.sh | bash
```

**Node.js (for MCP servers):**
```bash
# Install Node.js via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 22
nvm use 22
```

#### 2. Configure MCP Servers
MCP servers are configured in `.kiro/settings/mcp.json`. See [MCP Configuration](#mcp-configuration) for details.

#### 3. Install Project Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Deploy Online Boutique
```bash
# Deploy Online Boutique directly from the official manifest
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml -n online-boutique

# Verify deployment
kubectl get pods -n online-boutique

# Check application health
./check_online_boutique.sh
```

**Online Boutique is pre-deployed** in the development environment at: http://35.224.149.103

### Test Auto-Healing Scenarios
```bash
# Run comprehensive auto-heal testing scenarios
./test_auto_heal.sh

# Or test individual components
kubectl delete pod -l app=frontend -n auto-heal  # Test pod recovery
kubectl scale deployment currencyservice --replicas=0 -n auto-heal  # Test service recovery
```

### Run Synthetic Tests
```bash
# Install dependencies
cd playwright-tests
npm install

# Run tests with custom reporter
npm test
```

## Project Structure

```
├── agents/                           # Agent implementations
├── docs/                             # Documentation
├── kubernetes/                       # K8s manifests and configs
├── mcp-servers/                      # Custom MCP server implementations
├── playwright-tests/                 # Synthetic monitoring tests
├── terraform/                        # Infrastructure as Code
└── web-dashboard/                    # Web-based approval interface
```

## MCP Configuration

MCP servers are configured in `mcp-servers/mcp.json`:

```json
{
  "mcpServers": {
    "gemini-cloud-assist": {
      "command": "npx",
      "args": ["-y", "https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"],
      "env": {
        "GCP_PROJECT_ID": "your-project-id",
        "FASTMCP_LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "autoApprove": ["create_investigation", "search_and_analyze_gcp_resources"]
    }
  }
}
```

## Documentation

- [Official ADK Documentation](https://github.com/google/adk-python) - Agent Development Kit
- [Official A2A Documentation](https://github.com/a2aproject/A2A) - Agent-to-Agent communication
- [MCP Servers](/mcp-servers/README.md) - MCP server configuration and setup

## Troubleshooting

### Common Installation Issues

**MCP Server Issues:**
- Verify Node.js version (16+ required)
- Check Google Cloud authentication: `gcloud auth list`
- Validate project permissions for required APIs

### Debug Commands
For detailed troubleshooting, see:
- [TROUBLESHOOTING.md](/TROUBLESHOOTING.md) - Detailed troubleshooting guide

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.