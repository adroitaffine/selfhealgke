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