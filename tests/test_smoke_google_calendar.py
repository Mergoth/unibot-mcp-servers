"""
E2E smoke tests for the Google Calendar MCP server.

Locally (auto-starts server):
  poetry run pytest tests/test_smoke_google_calendar.py -v

Against a deployed server:
  MCP_SERVER_URL=https://...run.app/sse poetry run pytest tests/test_smoke_google_calendar.py -v

Requires SA_KEY_B64 in .env or environment (Base64-encoded Service Account JSON).
"""

import os
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


def _parse_field(text: str, field: str) -> str:
    """Extract 'Field: value' from a multi-line tool response."""
    for line in text.splitlines():
        if line.startswith(f"{field}: "):
            return line.split(f"{field}: ", 1)[1].strip()
    raise ValueError(f"Field '{field}' not found in:\n{text}")


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
    text = result.content[0].text
    assert "error" not in text.lower(), f"Unexpected error: {text}"


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
        cal_result = await client.call_tool("create_calendar", {"summary": cal_name})
        cal_text = cal_result.content[0].text
        assert "Successfully created calendar" in cal_text, f"Calendar create failed: {cal_text}"
        calendar_id = _parse_field(cal_text, "ID")

        try:
            # --- Create event ---
            create_result = await client.call_tool("create_event", {
                "summary": event_summary,
                "start_time": start,
                "end_time": end,
                "calendar_id": calendar_id,
            })
            create_text = create_result.content[0].text
            assert "Successfully created" in create_text, f"Event create failed: {create_text}"
            event_id = _parse_field(create_text, "ID")

            # --- Update event ---
            updated_summary = event_summary + "-updated"
            update_result = await client.call_tool("update_event", {
                "event_id": event_id,
                "calendar_id": calendar_id,
                "summary": updated_summary,
                "attendees": [],
                "reminder_minutes": [10],
            })
            update_text = update_result.content[0].text
            assert "Successfully updated" in update_text, f"Event update failed: {update_text}"

            # --- Verify updated event appears in list ---
            list_result = await client.call_tool("list_events", {
                "calendar_id": calendar_id,
                "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            list_text = list_result.content[0].text
            assert updated_summary in list_text, f"Updated event not found in list: {list_text}"

            # --- Delete event ---
            delete_result = await client.call_tool("delete_event", {
                "event_id": event_id,
                "calendar_id": calendar_id,
            })
            delete_text = delete_result.content[0].text
            assert "Successfully deleted" in delete_text, f"Event delete failed: {delete_text}"

            # --- Verify event is gone ---
            list_after = await client.call_tool("list_events", {
                "calendar_id": calendar_id,
                "time_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_max": (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            assert updated_summary not in list_after.content[0].text, "Deleted event still appears"

        finally:
            # --- Always delete the scratch calendar ---
            await client.call_tool("delete_calendar", {"calendar_id": calendar_id})
