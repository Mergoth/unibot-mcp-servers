import os
import datetime
import logging
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from fastapi import FastAPI, Request
from starlette.responses import Response
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport
import mcp.types as types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unibot-google-calendar")

# Configuration
# The path to the Service Account JSON key
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Initializes and returns the Google Calendar API service."""
    if not GOOGLE_APPLICATION_CREDENTIALS:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
    
    if not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
        raise FileNotFoundError(f"Credentials file not found at: {GOOGLE_APPLICATION_CREDENTIALS}")

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=creds)

# MCP Server Initialization
server = Server("unibot-google-calendar")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Google Calendar tools."""
    return [
        types.Tool(
            name="list_calendars",
            description="List calendars the service account has access to.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="list_events",
            description="List events from a specific calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string", 
                        "description": "The ID of the calendar (default 'primary')."
                    },
                    "time_min": {
                        "type": "string", 
                        "description": "Start time in RFC3339 format (e.g., 2024-01-01T00:00:00Z). Defaults to current time."
                    },
                    "time_max": {
                        "type": "string", 
                        "description": "End time in RFC3339 format (e.g., 2024-01-01T23:59:59Z)."
                    },
                    "max_results": {
                        "type": "integer", 
                        "description": "Maximum number of results (default 10)."
                    },
                },
            },
        ),
        types.Tool(
            name="create_event",
            description="Create a new event in a calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string", 
                        "description": "The ID of the calendar (default 'primary')."
                    },
                    "summary": {
                        "type": "string", 
                        "description": "Summary/Title of the event."
                    },
                    "start_time": {
                        "type": "string", 
                        "description": "Start time in RFC3339 format (e.g., 2024-05-20T10:00:00Z)."
                    },
                    "end_time": {
                        "type": "string", 
                        "description": "End time in RFC3339 format (e.g., 2024-05-20T11:00:00Z)."
                    },
                    "description": {
                        "type": "string", 
                        "description": "Description of the event."
                    },
                },
                "required": ["summary", "start_time", "end_time"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    try:
        service = get_calendar_service()
    except Exception as e:
        return [types.TextContent(type="text", text=f"Failed to initialize Google Calendar service: {str(e)}")]

    if name == "list_calendars":
        try:
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            if not calendars:
                return [types.TextContent(type="text", text="No calendars found.")]
            
            lines = ["Available Calendars:"]
            for cal in calendars:
                lines.append(f"- {cal['summary']} (ID: {cal['id']})")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except HttpError as e:
            return [types.TextContent(type="text", text=f"Google API Error: {str(e)}")]

    elif name == "list_events":
        calendar_id = arguments.get("calendar_id", "primary") if arguments else "primary"
        time_min = arguments.get("time_min") if arguments else None
        time_max = arguments.get("time_max") if arguments else None
        max_results = arguments.get("max_results", 10) if arguments else 10
        
        if not time_min:
            time_min = datetime.datetime.utcnow().isoformat() + 'Z'
        
        try:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            if not events:
                return [types.TextContent(type="text", text="No events found.")]
            
            lines = [f"Upcoming events for {calendar_id}:"]
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                lines.append(f"- {start}: {event.get('summary', 'No Title')} (ID: {event['id']})")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except HttpError as e:
            return [types.TextContent(type="text", text=f"Google API Error: {str(e)}")]

    elif name == "create_event":
        if not arguments:
            return [types.TextContent(type="text", text="Missing arguments for create_event")]
            
        calendar_id = arguments.get("calendar_id", "primary")
        summary = arguments.get("summary")
        start_time = arguments.get("start_time")
        end_time = arguments.get("end_time")
        description = arguments.get("description", "")
        
        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time},
            'end': {'dateTime': end_time},
        }
        
        try:
            event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            return [types.TextContent(type="text", text=f"Successfully created event: {event.get('summary')}\nLink: {event.get('htmlLink')}")]
        except HttpError as e:
            return [types.TextContent(type="text", text=f"Google API Error: {str(e)}")]

    raise ValueError(f"Unknown tool: {name}")

# FastAPI and SSE Integration
app = FastAPI(title="Google Calendar MCP Server")
sse = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    """Endpoint for establishing SSE connection."""
    async with sse.connect_sse(request.scope, request.receive, request.send) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                serverName="unibot-google-calendar",
                serverVersion="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

@app.post("/messages")
async def handle_messages(request: Request):
    """Endpoint for handling client messages."""
    await sse.handle_post_message(request.scope, request.receive, request.send)

if __name__ == "__main__":
    import uvicorn
    # Use PORT from environment or default to 8080
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
