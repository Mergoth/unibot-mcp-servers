"""
E2E smoke tests for the Google Calendar MCP server.

Locally (auto-starts server):
  poetry run pytest tests/test_smoke_google_calendar.py -v

Against a deployed server:
  MCP_SERVER_URL=https://...run.app/sse poetry run pytest tests/test_smoke_google_calendar.py -v

Requires SA_KEY_B64 in .env or environment (Base64-encoded Service Account JSON).
Also requires SMOKE_CALENDAR_ID in .env — the calendar ID to run create/delete tests against.
"""

import os
import datetime
import pytest
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import SSETransport

load_dotenv()

SA_KEY_B64 = os.getenv("SA_KEY_B64")
SMOKE_CALENDAR_ID = os.getenv("SMOKE_CALENDAR_ID", "primary")

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
    assert "delete_event" in names


@pytest.mark.asyncio
async def test_list_calendars_returns_result(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        result = await client.call_tool("list_calendars", {})
    assert result.content, "Expected non-empty response from list_calendars"
    text = result.content[0].text
    assert "error" not in text.lower(), f"Unexpected error: {text}"


@pytest.mark.asyncio
async def test_create_list_delete_event(mcp_server_url):
    """Full cycle: create an event, verify it appears in list, then delete it."""
    now = datetime.datetime.utcnow()
    start = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = f"[smoke-test] {now.strftime('%Y%m%d%H%M%S')}"

    async with make_client(mcp_server_url) as client:
        # Create
        create_result = await client.call_tool("create_event", {
            "summary": summary,
            "start_time": start,
            "end_time": end,
            "calendar_id": SMOKE_CALENDAR_ID,
        })
        create_text = create_result.content[0].text
        assert "Successfully created" in create_text, f"Create failed: {create_text}"

        event_id = next(
            (line.split("ID: ")[1].strip() for line in create_text.splitlines() if line.startswith("ID: ")),
            None,
        )
        assert event_id, f"Could not parse event ID from: {create_text}"

        # Verify it appears in list
        list_result = await client.call_tool("list_events", {
            "calendar_id": SMOKE_CALENDAR_ID,
            "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        list_text = list_result.content[0].text
        assert summary in list_text, f"Created event not found in list: {list_text}"

        # Delete
        delete_result = await client.call_tool("delete_event", {
            "event_id": event_id,
            "calendar_id": SMOKE_CALENDAR_ID,
        })
        delete_text = delete_result.content[0].text
        assert "Successfully deleted" in delete_text, f"Delete failed: {delete_text}"

        # Verify it's gone
        list_after = await client.call_tool("list_events", {
            "calendar_id": SMOKE_CALENDAR_ID,
            "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        list_after_text = list_after.content[0].text
        assert summary not in list_after_text, f"Deleted event still appears: {list_after_text}"
