# GKE Auto-Heal Agent MCP Servers

This directory contains the MCP (Model Context Protocol) server configuration and custom implementations for the GKE Auto-Heal Agent project.

## Architecture Overview

The project follows a **Google Cloud First** architecture, leveraging official MCP servers from Google Cloud Platform and Microsoft, with minimal custom development for specialized functionality.

## MCP Server Configuration

### Official MCP Servers

1. **Gemini Cloud Assist MCP** (Google Cloud Official)
   - **Purpose**: GCP operations, AI analysis, and investigation management
   - **Installation**: `npx -y https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp`
   - **Key Tools**: `create_investigation`, `search_and_analyze_gcp_resources`

2. **GKE MCP** (Google Cloud Official)
   - **Purpose**: Google Kubernetes Engine operations and management
   - **Installation**: Binary installation via `curl -sSL https://raw.githubusercontent.com/GoogleCloudPlatform/gke-mcp/main/install.sh | bash`
   - **Key Tools**: `list_clusters`, `get_cluster`, `query_logs`

3. **Playwright MCP** (Microsoft Official)
   - **Purpose**: Browser automation and web interface testing
   - **Installation**: `npx @playwright/mcp@latest`
   - **Key Tools**: `browser_navigate`, `browser_click`, `browser_snapshot`

4. **Kubernetes MCP** (Community)
   - **Purpose**: General Kubernetes operations and kubectl functionality
   - **Installation**: `npx mcp-server-kubernetes`
   - **Key Tools**: `kubectl_get`, `kubectl_describe`, `kubectl_logs`

### Custom MCP Server

5. **GCP Observability MCP** (Custom - Specialized)
   - **Purpose**: Online Boutique specific observability patterns and microservice analysis
   - **File**: `gcp_observability_server.py`
   - **Key Tools**: `correlate_telemetry`, `build_failure_timeline`, `analyze_microservice_patterns`, `detect_cascade_failures`

## Authentication Setup

### Google Cloud Authentication
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Set up Application Default Credentials
gcloud auth application-default login

# Set project
gcloud config set project cogent-spirit-469200-q3
```

### Environment Configuration
All MCP servers are configured with proper PATH variables to include:
- Node.js (nvm): `/Users/abhitalluri/.nvm/versions/node/v22.14.0/bin`
- Google Cloud SDK: `/Users/abhitalluri/google-cloud-sdk/bin`
- System paths: `/usr/local/bin:/usr/bin:/bin`

## Benefits of Google Cloud First Architecture

1. **Reduced Maintenance**: Official servers are maintained by platform teams
2. **Better Reliability**: Thoroughly tested and supported by Google Cloud and Microsoft
3. **More Features**: Full feature sets from the platform experts
4. **Automatic Updates**: Official servers receive regular updates and improvements
5. **Focused Development**: Custom development only for specialized Online Boutique patterns

## Current Status

- ✅ **Gemini Cloud Assist**: Configured and working with ADC
- ✅ **GKE MCP**: Installed and configured with gcloud CLI
- ✅ **Playwright MCP**: Configured with official Microsoft package
- ✅ **Kubernetes MCP**: Configured with community server
- ⚠️ **GCP Observability**: Custom server (disabled pending MCP Python SDK)

## Next Steps

1. Complete agent development using these MCP servers
2. Implement communication between agents
3. Deploy agents alongside Online Boutique on GKE
4. Enable custom GCP Observability server when MCP Python SDK is available
5. Discover and record registered tools

### Discovering registered tools (recommended)

1. Start the MCP servers listed in `mcp.json` so they are reachable.
2. Run the discovery helper script to attempt programmatic discovery:

```bash
cd mcp-servers
python3 -c "
import json
import requests
# Manual tool discovery - replace with your MCP server endpoints
servers = json.load(open('mcp.json'))['mcpServers']
tools = {}
for name, config in servers.items():
    if not config.get('disabled', False):
        # Query each MCP server for available tools
        # This is a placeholder - implement based on your MCP server APIs
        tools[name] = {'tools': []}
with open('registered_tools.json', 'w') as f:
    json.dump(tools, f, indent=2)
"
```

3. Inspect `registered_tools.json`. If automatic discovery failed for any server, manually query the running server or consult that server's documentation and add the tools to `registered_tools.json`.

4. Commit `registered_tools.json` into the repository as the canonical list of available MCP tools. Agents must only reference tools listed there.

References:
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP tools concepts: https://modelcontextprotocol.io/docs/concepts/tools