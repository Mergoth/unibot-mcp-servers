import sys
import os
import pytest
from unittest.mock import MagicMock

# Add the server directory to path to allow importing 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp-servers/google-calendar')))

import main

class MockContext:
    def __init__(self, google_service):
        self.google_service = google_service

@pytest.mark.asyncio
async def test_list_tools():
    """Verify that all tools are registered in FastMCP."""
    tools = await main.mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "list_calendars" in tool_names
    assert "list_events" in tool_names
    assert "create_event" in tool_names

@pytest.mark.asyncio
async def test_list_calendars():
    """Test list_calendars tool with mocked Google API."""
    mock_service = MagicMock()
    mock_service.calendarList().list().execute.return_value = {
        'items': [
            {'summary': 'Work', 'id': 'work_id'},
            {'summary': 'Personal', 'id': 'personal_id'}
        ]
    }
    mock_ctx = MockContext(mock_service)
    
    result = main.list_calendars(ctx=mock_ctx)
    
    assert "Work (ID: work_id)" in result
    assert "Personal (ID: personal_id)" in result

@pytest.mark.asyncio
async def test_list_events():
    """Test list_events tool with mocked Google API."""
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        'items': [
            {
                'summary': 'Meeting', 
                'id': 'evt1',
                'start': {'dateTime': '2024-05-20T10:00:00Z'}
            }
        ]
    }
    mock_ctx = MockContext(mock_service)
    
    result = main.list_events(ctx=mock_ctx, calendar_id="primary")
    
    assert "Meeting" in result
    assert "2024-05-20T10:00:00Z" in result

@pytest.mark.asyncio
async def test_create_event():
    """Test create_event tool with mocked Google API."""
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        'summary': 'New Event',
        'htmlLink': 'http://calendar.google.com/event'
    }
    mock_ctx = MockContext(mock_service)
    
    result = main.create_event(
        ctx=mock_ctx,
        summary="New Event",
        start_time="2024-05-20T10:00:00Z",
        end_time="2024-05-20T11:00:00Z"
    )
    
    assert "Successfully created event: New Event" in result
    assert "http://calendar.google.com/event" in result
