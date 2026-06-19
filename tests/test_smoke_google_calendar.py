"""
E2E smoke tests for the Google Calendar MCP server.

Locally (auto-starts server):
  poetry run pytest tests/test_smoke_google_calendar.py -v

Against a deployed server:
  MCP_SERVER_URL=https://...run.app/sse poetry run pytest tests/test_smoke_google_calendar.py -v

Requires SA_KEY_B64 in .env or environment (Base64-encoded Service Account JSON).
"""

import os
import json
import datetime
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


def _data(result) -> dict | list:
    """Extract structured data from a tool result."""
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_tools_are_registered(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        names = [t.name for t in await client.list_tools()]
    for tool in ("list_calendars", "list_events", "create_event",
                 "update_event", "delete_event", "create_calendar", "delete_calendar"):
        assert tool in names, f"Tool '{tool}' not registered"


@pytest.mark.asyncio
async def test_list_calendars_returns_result(mcp_server_url):
    async with make_client(mcp_server_url) as client:
        result = await client.call_tool("list_calendars", {})
    calendars = _data(result)
    assert isinstance(calendars, list)


@pytest.mark.asyncio
async def test_full_calendar_and_event_lifecycle(mcp_server_url):
    """Creates a scratch calendar, runs full event CRUD inside it, then deletes the calendar."""
    now = datetime.datetime.utcnow()
    cal_name = f"[smoke-test] {now.strftime('%Y%m%d%H%M%S')}"
    start = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    event_summary = f"smoke-event-{now.strftime('%H%M%S')}"

    async with make_client(mcp_server_url) as client:
        # --- Create calendar ---
        cal = _data(await client.call_tool("create_calendar", {"summary": cal_name}))
        calendar_id = cal["id"]
        assert cal["summary"] == cal_name

        try:
            # --- Create event ---
            event = _data(await client.call_tool("create_event", {
                "summary": event_summary,
                "start_time": start,
                "end_time": end,
                "calendar_id": calendar_id,
            }))
            event_id = event["id"]
            assert event["summary"] == event_summary
            assert event["start"] == start
            assert event["end"] == end

            # --- Update event ---
            updated_summary = event_summary + "-updated"
            updated = _data(await client.call_tool("update_event", {
                "event_id": event_id,
                "calendar_id": calendar_id,
                "summary": updated_summary,
                "reminder_minutes": [10],
            }))
            assert updated["summary"] == updated_summary
            assert updated["id"] == event_id

            # --- Verify updated event appears in list ---
            events = _data(await client.call_tool("list_events", {
                "calendar_id": calendar_id,
                "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }))
            assert any(e["id"] == event_id and e["summary"] == updated_summary for e in events)

            # --- Delete event ---
            deleted = _data(await client.call_tool("delete_event", {
                "event_id": event_id,
                "calendar_id": calendar_id,
            }))
            assert deleted["deleted"] == event_id

            # --- Verify event is gone ---
            events_after = _data(await client.call_tool("list_events", {
                "calendar_id": calendar_id,
                "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }))
            assert not any(e["id"] == event_id for e in events_after)

        finally:
            # --- Always delete the scratch calendar ---
            await client.call_tool("delete_calendar", {"calendar_id": calendar_id})
