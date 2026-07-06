"""
E2E smoke tests for the Save Lead MCP server.

Locally (auto-starts server):
  poetry run pytest tests/test_smoke_save_lead.py -v

Against a deployed server:
  MCP_SERVER_URL=https://...run.app/sse poetry run pytest tests/test_smoke_save_lead.py -v
"""

import os
import json
import pytest
import socket
import subprocess
import time
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

PROJECT_ROOT = Path(__file__).parent.parent
LOCAL_PORT = 8091


def _wait_for_port(host: str, port: int, timeout: float = 20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"Server did not become available on {host}:{port} within {timeout}s")


@pytest.fixture(scope="session")
def save_lead_server_url():
    """Return the Save Lead MCP SSE endpoint URL."""
    url = os.getenv("MCP_SERVER_URL")
    if url and "google-calendar" not in url:
        yield url
        return

    # Start local uvicorn server
    proc = subprocess.Popen(
        [
            "poetry", "run", "python", "mcp-servers/save-lead/main.py"
        ],
        env={**os.environ, "PORT": str(LOCAL_PORT)},
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port("localhost", LOCAL_PORT)
        yield f"http://localhost:{LOCAL_PORT}/sse"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.mark.asyncio
async def test_tools_are_registered(save_lead_server_url):
    # Strip /sse for streamable_http_client
    base_url = save_lead_server_url.replace("/sse", "")
    async with streamable_http_client(base_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert "save_lead" in names, "Tool 'save_lead' not registered"


@pytest.mark.asyncio
async def test_call_tool_validation_error(save_lead_server_url):
    # Strip /sse for streamable_http_client
    base_url = save_lead_server_url.replace("/sse", "")
    async with streamable_http_client(base_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("save_lead", {"contact": "invalid-contact"})
            assert len(result.content) == 1
            data = json.loads(result.content[0].text)
            assert data["status"] == "needs_contact"
