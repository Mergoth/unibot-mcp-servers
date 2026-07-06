import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
LOCAL_PORT = 8090


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
def mcp_server_url():
    """Return the MCP SSE endpoint URL.

    If MCP_SERVER_URL is set, uses it directly (CI/CD against a deployed server).
    Otherwise, starts a local FastMCP server for the duration of the test session.
    """
    url = os.getenv("MCP_SERVER_URL")
    if url and "save-lead" not in url:
        yield url
        return

    proc = subprocess.Popen(
        [
            "poetry", "run", "fastmcp", "run",
            "mcp-servers/google-calendar/main.py:mcp",
            "--host", "0.0.0.0",
            "--port", str(LOCAL_PORT),
            "--transport", "sse",
        ],
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
