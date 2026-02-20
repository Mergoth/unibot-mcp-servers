import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add the server directory to path to allow importing 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp-servers/google-calendar')))

import main
import mcp.types as types

@pytest.mark.asyncio
async def test_list_tools():
    """Verify that all tools are correctly listed."""
    tools = await main.handle_list_tools()
    tool_names = [t.name for t in tools]
    assert "list_calendars" in tool_names
    assert "list_events" in tool_names
    assert "create_event" in tool_names

@pytest.mark.asyncio
@patch('main.get_calendar_service')
async def test_list_calendars(mock_get_service):
    """Test list_calendars tool with mocked Google API."""
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    mock_service.calendarList().list().execute.return_value = {
        'items': [
            {'summary': 'Work', 'id': 'work_id'},
            {'summary': 'Personal', 'id': 'personal_id'}
        ]
    }
    
    result = await main.handle_call_tool("list_calendars", {})
    
    assert len(result) == 1
    assert "Work (ID: work_id)" in result[0].text
    assert "Personal (ID: personal_id)" in result[0].text

@pytest.mark.asyncio
@patch('main.get_calendar_service')
async def test_list_events(mock_get_service):
    """Test list_events tool with mocked Google API."""
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    mock_service.events().list().execute.return_value = {
        'items': [
            {
                'summary': 'Meeting', 
                'id': 'evt1',
                'start': {'dateTime': '2024-05-20T10:00:00Z'}
            }
        ]
    }
    
    result = await main.handle_call_tool("list_events", {"calendar_id": "primary"})
    
    assert len(result) == 1
    assert "Meeting" in result[0].text
    assert "2024-05-20T10:00:00Z" in result[0].text

@pytest.mark.asyncio
@patch('main.get_calendar_service')
async def test_create_event(mock_get_service):
    """Test create_event tool with mocked Google API."""
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    mock_service.events().insert().execute.return_value = {
        'summary': 'New Event',
        'htmlLink': 'http://calendar.google.com/event'
    }
    
    arguments = {
        "summary": "New Event",
        "start_time": "2024-05-20T10:00:00Z",
        "end_time": "2024-05-20T11:00:00Z"
    }
    
    result = await main.handle_call_tool("create_event", arguments)
    
    assert len(result) == 1
    assert "Successfully created event: New Event" in result[0].text
    assert "http://calendar.google.com/event" in result[0].text
