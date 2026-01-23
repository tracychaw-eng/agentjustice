#!/usr/bin/env python
"""
Start Purple Agent Server.

Entry point for running the Purple Agent A2A server.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from purple_agent.agent import run_server
from config import server_config, purple_agent_config


def main():
    """Run Purple Agent Server."""
    print("=" * 60)
    print("AgentBeats Purple Agent (A2A Server)")
    print("=" * 60)
    print(f"Host: {server_config.purple_agent_host}")
    print(f"Port: {server_config.purple_agent_port}")
    print(f"Mode: {purple_agent_config.mode}")
    print()
    print("Modes:")
    print("  gold       - Returns gold answer (for evaluator testing)")
    print("  llm        - Generates answer using LLM")
    print("  adversarial - Returns pre-set adversarial candidate")
    print()
    print("A2A endpoints:")
    print("  GET  /a2a/card")
    print("  GET  /a2a/status")
    print("  POST /a2a/generate")
    print("  POST /a2a/set_mode")
    print("  GET  /health")
    print("=" * 60)
    
    run_server()


if __name__ == "__main__":
    main()
