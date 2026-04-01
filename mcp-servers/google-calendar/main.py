import os
import datetime
import logging
import base64
import json
from contextvars import ContextVar
from typing import Optional

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_request

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unibot-google-calendar")
SCOPES = ['https://www.googleapis.com/auth/calendar']

_google_service: ContextVar = ContextVar('google_service', default=None)


class GoogleAuthMiddleware(Middleware):
    """
    Strict API Key Auth: Requires the Unibot Agent to pass a Base64-encoded
    Service Account JSON payload in the X-Service-Account-Key header.
    """
    async def __call__(self, context: MiddlewareContext, call_next):
        if context.method == "tools/call":
            try:
                request = get_http_request()
                sa_key_b64 = request.headers.get("X-Service-Account-Key")
            except RuntimeError:
                raise Exception("Unauthorized: Missing Request Context.")

            if not sa_key_b64:
                raise Exception("Unauthorized: Missing X-Service-Account-Key header.")

            try:
                sa_key_json = base64.b64decode(sa_key_b64).decode('utf-8')
                sa_info = json.loads(sa_key_json)
                creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
                token = _google_service.set(build('calendar', 'v3', credentials=creds))
            except Exception as e:
                logger.error(f"Failed to parse or authenticate Service Account: {e}")
                raise Exception(f"Unauthorized: Invalid X-Service-Account-Key payload ({e})")

            try:
                return await call_next(context)
            finally:
                _google_service.reset(token)

        return await call_next(context)


# Initialize FastMCP
mcp = FastMCP("GoogleCalendar", middleware=[GoogleAuthMiddleware()])


@mcp.tool
def list_calendars(ctx: Context) -> str:
    """List calendars the injected Service Account has access to."""
    service = _google_service.get()
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
def create_calendar(ctx: Context, summary: str) -> str:
    """Create a new calendar owned by the service account. Returns its calendar ID."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    try:
        calendar = service.calendars().insert(body={'summary': summary}).execute()
        return f"Successfully created calendar: {calendar.get('summary')}\nID: {calendar.get('id')}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def delete_calendar(ctx: Context, calendar_id: str) -> str:
    """Permanently delete a calendar owned by the service account."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    try:
        service.calendars().delete(calendarId=calendar_id).execute()
        return f"Successfully deleted calendar: {calendar_id}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def add_calendar(ctx: Context, calendar_id: str) -> str:
    """Add a calendar to the service account's calendar list by its ID (e.g. user@gmail.com).
    Must be called once per calendar after the calendar has been shared with this service account."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    try:
        calendar = service.calendarList().insert(body={'id': calendar_id}).execute()
        return f"Successfully added calendar: {calendar.get('summary')} (ID: {calendar.get('id')})"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def list_events(ctx: Context, calendar_id: str = "primary", time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 20) -> str:
    """List events from a specific calendar. Defaults to past 7 days and next 30 days.
    time_min and time_max are RFC3339 (e.g. 2024-01-01T00:00:00Z) and override the defaults."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    now = datetime.datetime.utcnow()
    if not time_min:
        time_min = (now - datetime.timedelta(days=7)).isoformat() + 'Z'
    if not time_max:
        time_max = (now + datetime.timedelta(days=30)).isoformat() + 'Z'

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

        lines = [f"Events for {calendar_id}:"]
        for event in events:
            raw_start = event['start'].get('dateTime', event['start'].get('date'))
            # Format: "Mon 01 Jan 2024 10:00" for datetime, "Mon 01 Jan 2024" for all-day
            try:
                if 'T' in raw_start:
                    dt = datetime.datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
                    start = dt.strftime('%a %d %b %Y %H:%M')
                else:
                    dt = datetime.date.fromisoformat(raw_start)
                    start = dt.strftime('%a %d %b %Y') + ' (all day)'
            except ValueError:
                start = raw_start
            lines.append(f"- {start}: {event.get('summary', 'No Title')}")
        return "\n".join(lines)
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def create_event(ctx: Context, summary: str, start_time: str, end_time: str, description: str = "", calendar_id: str = "primary") -> str:
    """Create a new event in a calendar. Start/end times in RFC3339 format (e.g., 2024-05-20T10:00:00Z)."""
    service = _google_service.get()
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
        return f"Successfully created event: {event.get('summary')}\nID: {event.get('id')}\nLink: {event.get('htmlLink')}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def update_event(
    ctx: Context,
    event_id: str,
    calendar_id: str = "primary",
    summary: Optional[str] = None,
    description: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    reminder_minutes: Optional[list[int]] = None,
) -> str:
    """Update an existing calendar event. Only provided fields are changed.
    attendees: list of email addresses to invite.
    reminder_minutes: list of minutes before the event to send a popup reminder (e.g. [10, 30]).
    Times are RFC3339 (e.g. 2024-05-20T10:00:00Z)."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    patch: dict = {}
    if summary is not None:
        patch['summary'] = summary
    if description is not None:
        patch['description'] = description
    if start_time is not None:
        patch['start'] = {'dateTime': start_time}
    if end_time is not None:
        patch['end'] = {'dateTime': end_time}
    if attendees is not None:
        patch['attendees'] = [{'email': email} for email in attendees]
    if reminder_minutes is not None:
        patch['reminders'] = {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': m} for m in reminder_minutes],
        }

    if not patch:
        return "Nothing to update — no fields provided."

    try:
        event = service.events().patch(
            calendarId=calendar_id, eventId=event_id, body=patch
        ).execute()
        return f"Successfully updated event: {event.get('summary')}\nID: {event.get('id')}\nLink: {event.get('htmlLink')}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


@mcp.tool
def delete_event(ctx: Context, event_id: str, calendar_id: str = "primary") -> str:
    """Delete an event by its ID from a calendar."""
    service = _google_service.get()
    if not service:
        return "Failed to initialize Google Calendar service."

    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"Successfully deleted event: {event_id}"
    except HttpError as e:
        return f"Google API Error: {str(e)}"


# Entrypoint for poetry local running
if __name__ == "__main__":
    mcp.run()
