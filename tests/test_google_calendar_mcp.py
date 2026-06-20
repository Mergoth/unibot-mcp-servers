import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp-servers/google-calendar')))

# Remove any previously cached 'main' module to prevent namespace clashing in pytest
sys.modules.pop("main", None)

import main


@pytest.mark.asyncio
async def test_list_tools():
    tools = await main.mcp.list_tools()
    names = [t.name for t in tools]
    for tool in ("list_calendars", "list_events", "create_event",
                 "update_event", "delete_event", "create_calendar", "delete_calendar"):
        assert tool in names


@pytest.mark.asyncio
async def test_list_calendars():
    mock_service = MagicMock()
    mock_service.calendarList().list().execute.return_value = {
        'items': [
            {'id': 'work_id', 'summary': 'Work'},
            {'id': 'personal_id', 'summary': 'Personal'},
        ]
    }
    token = main._google_service.set(mock_service)
    try:
        result = main.list_calendars(ctx=None)
    finally:
        main._google_service.reset(token)

    assert len(result) == 2
    assert result[0].id == 'work_id'
    assert result[0].summary == 'Work'


@pytest.mark.asyncio
async def test_list_events():
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        'items': [{
            'id': 'evt1',
            'summary': 'Meeting',
            'start': {'dateTime': '2024-05-20T10:00:00Z'},
            'end': {'dateTime': '2024-05-20T11:00:00Z'},
        }]
    }
    token = main._google_service.set(mock_service)
    try:
        result = main.list_events(ctx=None, calendar_id="primary")
    finally:
        main._google_service.reset(token)

    assert len(result) == 1
    assert result[0].id == 'evt1'
    assert result[0].summary == 'Meeting'
    assert result[0].start == '2024-05-20T10:00:00Z'
    assert result[0].calendar_id == 'primary'


@pytest.mark.asyncio
async def test_create_event():
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        'id': 'evt1',
        'summary': 'New Event',
        'start': {'dateTime': '2024-05-20T10:00:00Z'},
        'end': {'dateTime': '2024-05-20T11:00:00Z'},
        'htmlLink': 'http://calendar.google.com/event',
    }
    token = main._google_service.set(mock_service)
    try:
        result = main.create_event(
            ctx=None,
            summary="New Event",
            start_time="2024-05-20T10:00:00Z",
            end_time="2024-05-20T11:00:00Z",
        )
    finally:
        main._google_service.reset(token)

    assert result.id == 'evt1'
    assert result.summary == 'New Event'
    assert result.html_link == 'http://calendar.google.com/event'


@pytest.mark.asyncio
async def test_update_event():
    mock_service = MagicMock()
    mock_service.events().patch().execute.return_value = {
        'id': 'evt1',
        'summary': 'Updated Event',
        'start': {'dateTime': '2024-05-20T10:00:00Z'},
        'end': {'dateTime': '2024-05-20T11:00:00Z'},
        'attendees': [{'email': 'alice@example.com'}],
    }
    token = main._google_service.set(mock_service)
    try:
        result = main.update_event(
            ctx=None,
            event_id="evt1",
            summary="Updated Event",
            attendees=["alice@example.com"],
            reminder_minutes=[10, 30],
        )
    finally:
        main._google_service.reset(token)

    assert result.summary == 'Updated Event'
    assert result.attendees == ['alice@example.com']

    call_kwargs = mock_service.events().patch.call_args.kwargs
    body = call_kwargs['body']
    assert body['attendees'] == [{'email': 'alice@example.com'}]
    assert {'method': 'popup', 'minutes': 10} in body['reminders']['overrides']


@pytest.mark.asyncio
async def test_delete_event():
    mock_service = MagicMock()
    mock_service.events().delete().execute.return_value = None
    token = main._google_service.set(mock_service)
    try:
        result = main.delete_event(ctx=None, event_id="evt1", calendar_id="primary")
    finally:
        main._google_service.reset(token)

    assert result == {"deleted": "evt1", "calendar_id": "primary"}
