"""
E2E smoke tests for the Google Calendar MCP server.

Locally (auto-starts server):
  poetry run pytest tests/test_smoke_google_calendar.py -v

Against a deployed server:
  MCP_SERVER_URL=https://...run.app/sse poetry run pytest tests/test_smoke_google_calendar.py -v

Requires SA_KEY_B64 in .env or environment (Base64-encoded Service Account JSON).
"""

import os
import pytest
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import SSETransport

load_dotenv()

SA_KEY_B64 = os.getenv("SA_KEY_B64")

pytestmark = pytest.mark.skipif(
    not SA_KEY_B64,
    reason="SA_KEY_B64 env var required for smoke tests",
)


def make_client(url: str) -> Client:
    return Client(SSETransport(url=url, headers={"X-Service-Account-Key": SA_KEY_B64}))


@pytest.mark.asyncio
async def test_tools_are_registered(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        names = [t.name for t in await client.list_tools()]
    assert "list_calendars" in names
    assert "list_events" in names
    assert "create_event" in names


@pytest.mark.asyncio
async def test_list_calendars_returns_result(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        result = await client.call_tool("list_calendars", {})
    assert result.content, "Expected non-empty response from list_calendars"
    text = result.content[0].text
    assert "error" not in text.lower(), f"Unexpected error: {text}"


@pytest.mark.asyncio
async def test_list_events_returns_result(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        result = await client.call_tool("list_events", {"calendar_id": "primary", "max_results": 5})
    assert result.content, "Expected non-empty response from list_events"
    text = result.content[0].text
    assert "error" not in text.lower(), f"Unexpected error: {text}"
