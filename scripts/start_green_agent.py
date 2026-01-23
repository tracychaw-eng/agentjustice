#!/usr/bin/env python
"""
Start Green Agent Server.

Entry point for running the Green Agent A2A server.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from green_agent.agent import run_server
from config import server_config


def main():
    """Run Green Agent Server."""
    print("=" * 60)
    print("AgentBeats Green Agent (A2A Server)")
    print("=" * 60)
    print(f"Host: {server_config.green_agent_host}")
    print(f"Port: {server_config.green_agent_port}")
    print()
    print("A2A endpoints:")
    print("  GET  /a2a/card")
    print("  GET  /a2a/status")
    print("  POST /a2a/evaluate")
    print("  POST /a2a/run")
    print("  GET  /health")
    print("=" * 60)
    
    run_server()


if __name__ == "__main__":
    main()
