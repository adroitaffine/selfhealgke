#!/usr/bin/env python3
"""Discover registered tools from MCP servers listed in mcp-servers/mcp.json

This script attempts to query each MCP server and collect the canonical list of
registered tools (name/type/schema). The exact discovery mechanism depends on
how each MCP server exposes its tool registry (HTTP endpoint, CLI command, or
SDK function). This is a best-effort helper that tries multiple strategies and
writes results to `mcp-servers/registered_tools.json`.

Usage:
  python mcp-servers/scripts/discover_tools.py --mcp-file ../mcp.json --out ../registered_tools.json

Notes:
- Many MCP servers provide an HTTP or CLI-based listing. If a server exposes a
  discovery endpoint, add a custom handler in `discover_handlers` below.
- For programmatic discovery via the MCP Python SDK, install:
  pip install modelcontextprotocol
  (see https://github.com/modelcontextprotocol/python-sdk)
"""

import json
import subprocess
import asyncio
import os
import argparse
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[1]

# Load MCP server config

def load_mcp_config(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def try_sdk_discovery(server_name: str, server_cfg: Dict[str, Any]):
    """Try to use MCP Python SDK to connect and discover tools."""
    try:
        # Try importing MCP SDK
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        import asyncio
        
        async def discover_via_sdk():
            cmd = server_cfg.get('command')
            args = server_cfg.get('args', [])
            env = {**os.environ, **server_cfg.get('env', {})}
            
            if not cmd:
                return {'error': 'No command specified in server config'}
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=cmd,
                args=args,
                env=env
            )
            
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        # Initialize the session
                        await session.initialize()
                        
                        # List tools
                        tools_result = await session.list_tools()
                        tools = []
                        for tool in tools_result.tools:
                            tools.append({
                                'name': tool.name,
                                'description': tool.description,
                                'inputSchema': tool.inputSchema
                            })
                        
                        return {
                            'tools': tools,
                            'discovered_via': 'mcp_python_sdk',
                            'server_name': server_name
                        }
            except Exception as e:
                return {'error': str(e), 'attempted_via': 'mcp_python_sdk'}
        
        # Run the async discovery with timeout
        return asyncio.run(asyncio.wait_for(discover_via_sdk(), timeout=30.0))
        
    except ImportError:
        # MCP SDK not available
        return None
    except Exception as e:
        # Discovery failed
        return {'error': str(e), 'attempted_via': 'mcp_python_sdk'}


def try_cli_discovery(server_name: str, server_cfg: Dict[str, Any]):
    """Try to run the server's configured command with a `--list-tools` flag.
    This is heuristic: many MCP server CLIs support a discover/list command.
    """
    cmd = [server_cfg.get('command')] + server_cfg.get('args', [])
    # Try a few common discovery flags
    attempts = [cmd + ['--list-tools'], cmd + ['tools', 'list'], cmd + ['--tools']]

    for a in attempts:
        try:
            res = subprocess.run(a, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout:
                # Try parse JSON from stdout
                try:
                    parsed = json.loads(res.stdout)
                    return parsed
                except Exception:
                    # Not JSON, skip
                    continue
        except FileNotFoundError:
            # Command not found on PATH
            break
        except Exception:
            continue
    return None


def discover_tools(mcp_cfg: Dict[str, Any]):
    results = {}
    for name, cfg in mcp_cfg.get('mcpServers', {}).items():
        print(f"Discovering tools for MCP server: {name}")
        # Try SDK first
        sdk = try_sdk_discovery(name, cfg)
        if sdk:
            results[name] = sdk
            continue

        # Try CLI-based discovery
        cli = try_cli_discovery(name, cfg)
        if cli:
            results[name] = cli
            continue

        # Fallback: no automatic discovery
        results[name] = {
            'note': 'automatic discovery failed for this server; please query the running server or its docs',
            'config': cfg
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mcp-file', default=str(ROOT / 'mcp.json'))
    parser.add_argument('--out', default=str(ROOT / 'registered_tools.json'))
    args = parser.parse_args()

    mcp_cfg = load_mcp_config(Path(args.mcp_file))
    discovered = discover_tools(mcp_cfg)

    out_path = Path(args.out)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(discovered, f, indent=2)

    print(f"Wrote discovery output to {out_path}")


if __name__ == '__main__':
    main()
