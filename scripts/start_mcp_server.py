#!/usr/bin/env python
"""
Start MCP Judge Server.

Entry point for running the MCP server with judge tools.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import run_server
from config import server_config


def main():
    """Run MCP Judge Server."""
    print("=" * 60)
    print("AgentBeats MCP Judge Server")
    print("=" * 60)
    print(f"Host: {server_config.mcp_server_host}")
    print(f"Port: {server_config.mcp_server_port}")
    print()
    print("Available endpoints:")
    print("  POST /judge/semantic_equivalence")
    print("  POST /judge/numeric_tolerance")
    print("  POST /judge/contradiction")
    print("  GET  /health")
    print("  GET  /version")
    print("  GET  /mcp/tools")
    print("=" * 60)
    
    run_server()


if __name__ == "__main__":
    main()
