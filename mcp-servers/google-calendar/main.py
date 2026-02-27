import os
import datetime
import logging
import base64
import json
from typing import Optional

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unibot-google-calendar")
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleAuthMiddleware(Middleware):
    """
    Strict API Key Auth: Requires the Unibot Agent to pass a Base64-encoded
    Service Account JSON payload in the X-Google-Service-Account header.
    """
    async def __call__(self, context: MiddlewareContext, call_next):
        if context.method == "tools/call":
            ctx = context.fastmcp_context
            if ctx.request_context and ctx.request_context.request:
                sa_key_b64 = ctx.request_context.request.headers.get("X-Google-Service-Account")
                
                if not sa_key_b64:
                    raise Exception("Unauthorized: Missing X-Google-Service-Account header.")
                
                try:
                    sa_key_json = base64.b64decode(sa_key_b64).decode('utf-8')
                    sa_info = json.loads(sa_key_json)
                    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
                    ctx.google_service = build('calendar', 'v3', credentials=creds)
                except Exception as e:
                    logger.error(f"Failed to parse or authenticate Service Account: {e}")
                    raise Exception(f"Unauthorized: Invalid X-Google-Service-Account payload ({e})")
            else:
                 raise Exception("Unauthorized: Missing Request Context.")

        return await call_next(context)

# Initialize FastMCP
mcp = FastMCP("GoogleCalendar", middleware=[GoogleAuthMiddleware()])

@mcp.tool
def list_calendars(ctx: Context) -> str:
    """List calendars the injected Service Account has access to."""
    service = getattr(ctx, "google_service", None)
    if not service:
        return "Failed to initialize Google Calendar service."

    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        if not calendars:
            return "No calendars found."
        
        lines = ["Available Calendars:"]
        for cal in calendars:
            lines.append(f"- {cal['summary']} (ID: {cal['id']})")
        return "\n".join(lines)
    except HttpError as e:
        return f"Google API Error: {str(e)}"

@mcp.tool
def list_events(ctx: Context, calendar_id: str = "primary", time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10) -> str:
    """List events from a specific calendar. Start time time_min is in RFC3339 format (e.g., 2024-01-01T00:00:00Z). Defaults to current time."""
    service = getattr(ctx, "google_service", None)
    if not service:
        return "Failed to initialize Google Calendar service."

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
            return "No events found."
        
        lines = [f"Upcoming events for {calendar_id}:"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            lines.append(f"- {start}: {event.get('summary', 'No Title')} (ID: {event['id']})")
        return "\n".join(lines)
    except HttpError as e:
        return f"Google API Error: {str(e)}"

@mcp.tool
def create_event(ctx: Context, summary: str, start_time: str, end_time: str, description: str = "", calendar_id: str = "primary") -> str:
    """Create a new event in a calendar. Start/end times in RFC3339 format (e.g., 2024-05-20T10:00:00Z)."""
    service = getattr(ctx, "google_service", None)
    if not service:
        return "Failed to initialize Google Calendar service."

    event_body = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time},
        'end': {'dateTime': end_time},
    }
    
    try:
        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return f"Successfully created event: {event.get('summary')}\nLink: {event.get('htmlLink')}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"

# Entrypoint for poetry local running
if __name__ == "__main__":
    mcp.run()
