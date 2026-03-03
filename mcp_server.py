#!/usr/bin/env python
"""Entry point for the MCP server.

Sets up Django before starting the MCP HTTP server (SSE transport).

Usage:
    python mcp_server.py                # default port 8001
    python mcp_server.py --port 9000    # custom port

The server exposes 3 tools:
    - run_media_audit(account_id, date_start, date_end)
    - get_audit_status(run_id)
    - get_scorecard(run_id)
"""

import os
import sys


def main():
    # Django setup (must happen before importing any models)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

    import django
    django.setup()

    # Parse port from args
    port = 8001
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    # Import the MCP server (after Django setup)
    from engine.mcp.server import mcp

    # Override host/port on the server instance
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port

    print(f"Starting MCP server on http://0.0.0.0:{port}/")
    print("Tools available:")
    print("  - run_media_audit(account_id, date_start, date_end)")
    print("  - get_audit_status(run_id)")
    print("  - get_scorecard(run_id)")
    print()

    # Run with HTTP/SSE transport
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
