#!/usr/bin/env python
"""
Start Green Agent Server with embedded MCP Judge Server.

Runs both services in a single process/container:
- MCP Judge Server on port 8001 (internal, localhost only)
- Green Agent on configurable port (default 8002, exposed)

Usage:
    python scripts/start_green_agent.py --host 0.0.0.0 --port 8002 --card-url http://...
"""
import argparse
import multiprocessing
import os
import signal
import socket
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_mcp_server(host: str, port: int):
    """Run MCP Judge Server in a subprocess."""
    import uvicorn
    from mcp_server.server import app

    print(f"[MCP Server] Starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_green_agent(host: str, port: int, card_url: str = None):
    """Run Green Agent server."""
    import uvicorn
    from green_agent.agent import app

    if card_url:
        app.state.card_url = card_url

    print(f"[Green Agent] Starting on {host}:{port}")
    if card_url:
        print(f"[Green Agent] Advertised URL: {card_url}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def wait_for_server(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for a server to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Green Agent with embedded MCP Judge Server"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind Green Agent to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port for Green Agent"
    )
    parser.add_argument(
        "--card-url",
        dest="card_url",
        help="Advertised agent URL for A2A card"
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8001,
        help="Internal port for MCP Judge Server (localhost only)"
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run Green Agent without embedded MCP server (for local dev)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("AgentJustice Green Agent (A2A Server)")
    print("=" * 60)

    mcp_process = None

    if not args.standalone:
        # Set environment variable for MCP server URL (localhost since same container)
        os.environ["MCP_SERVER_URL"] = f"http://127.0.0.1:{args.mcp_port}"

        # Start MCP server in a subprocess
        mcp_process = multiprocessing.Process(
            target=run_mcp_server,
            args=("127.0.0.1", args.mcp_port),
            daemon=True
        )
        mcp_process.start()

        # Wait for MCP server to be ready
        print(f"[Startup] Waiting for MCP server on port {args.mcp_port}...")
        if not wait_for_server("127.0.0.1", args.mcp_port, timeout=30):
            print("[Startup] ERROR: MCP server failed to start")
            mcp_process.terminate()
            sys.exit(1)

        print(f"[Startup] MCP server ready on 127.0.0.1:{args.mcp_port}")
    else:
        print("[Startup] Standalone mode - MCP server must be running separately")

    print(f"[Startup] Green Agent will listen on {args.host}:{args.port}")
    print()
    print("A2A endpoints:")
    print("  GET  /a2a/card")
    print("  GET  /a2a/status")
    print("  POST /a2a/evaluate")
    print("  POST /a2a/run")
    print("  GET  /health")
    print("=" * 60)

    # Handle graceful shutdown
    def shutdown_handler(signum, frame):
        print("\n[Shutdown] Stopping services...")
        if mcp_process:
            mcp_process.terminate()
            mcp_process.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Run Green Agent in main process
    try:
        run_green_agent(args.host, args.port, args.card_url)
    finally:
        if mcp_process:
            mcp_process.terminate()
            mcp_process.join(timeout=5)


if __name__ == "__main__":
    main()
