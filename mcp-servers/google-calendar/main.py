import datetime
import logging
import base64
import json
from contextvars import ContextVar
from typing import Optional

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_request
from pydantic import BaseModel

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unibot-google-calendar")
SCOPES = ['https://www.googleapis.com/auth/calendar']

_google_service: ContextVar = ContextVar('google_service', default=None)


# --- Response models ---

class CalendarInfo(BaseModel):
    id: str
    summary: str


class EventReminder(BaseModel):
    method: str
    minutes: int


class EventInfo(BaseModel):
    id: str
    summary: str
    start: str
    end: str
    calendar_id: str
    description: str = ""
    attendees: list[str] = []
    reminders: list[EventReminder] = []
    location: str = ""
    status: str = ""
    html_link: str = ""


# --- Helpers ---

def _get_service():
    service = _google_service.get()
    if not service:
        raise RuntimeError("Google Calendar service not initialized.")
    return service


def _parse_event(event: dict, calendar_id: str) -> EventInfo:
    raw_reminders = event.get('reminders', {}).get('overrides', [])
    return EventInfo(
        id=event['id'],
        summary=event.get('summary', ''),
        start=event['start'].get('dateTime', event['start'].get('date', '')),
        end=event['end'].get('dateTime', event['end'].get('date', '')),
        calendar_id=calendar_id,
        description=event.get('description', ''),
        attendees=[a['email'] for a in event.get('attendees', [])],
        reminders=[EventReminder(method=r['method'], minutes=r['minutes']) for r in raw_reminders],
        location=event.get('location', ''),
        status=event.get('status', ''),
        html_link=event.get('htmlLink', ''),
    )


# --- Auth middleware ---

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


mcp = FastMCP("GoogleCalendar", middleware=[GoogleAuthMiddleware()])


# --- Calendar tools ---

@mcp.tool
def list_calendars(ctx: Context) -> list[CalendarInfo]:
    """List all calendars the service account has access to."""
    service = _get_service()
    try:
        result = service.calendarList().list().execute()
        return [CalendarInfo(id=c['id'], summary=c.get('summary', '')) for c in result.get('items', [])]
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def create_calendar(ctx: Context, summary: str) -> CalendarInfo:
    """Create a new calendar owned by the service account."""
    service = _get_service()
    try:
        cal = service.calendars().insert(body={'summary': summary}).execute()
        return CalendarInfo(id=cal['id'], summary=cal.get('summary', ''))
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def delete_calendar(ctx: Context, calendar_id: str) -> dict:
    """Permanently delete a calendar owned by the service account."""
    service = _get_service()
    try:
        service.calendars().delete(calendarId=calendar_id).execute()
        return {"deleted": calendar_id}
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def add_calendar(ctx: Context, calendar_id: str) -> CalendarInfo:
    """Subscribe the service account to a calendar that has been shared with it.
    Must be called once after sharing a calendar with this service account."""
    service = _get_service()
    try:
        cal = service.calendarList().insert(body={'id': calendar_id}).execute()
        return CalendarInfo(id=cal['id'], summary=cal.get('summary', ''))
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


# --- Event tools ---

@mcp.tool
def get_event(ctx: Context, event_id: str, calendar_id: str = "primary") -> EventInfo:
    """Get all details of a single event by its ID."""
    service = _get_service()
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return _parse_event(event, calendar_id)
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def list_events(
    ctx: Context,
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 20,
) -> list[EventInfo]:
    """List events from a calendar. Defaults to past 7 days and next 30 days.
    time_min / time_max are RFC3339 (e.g. 2024-01-01T00:00:00Z)."""
    service = _get_service()
    now = datetime.datetime.now(datetime.UTC)
    if not time_min:
        time_min = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not time_max:
        time_max = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        return [_parse_event(e, calendar_id) for e in result.get('items', [])]
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def create_event(
    ctx: Context,
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    calendar_id: str = "primary",
) -> EventInfo:
    """Create a new event. Times are RFC3339 (e.g. 2024-05-20T10:00:00Z)."""
    service = _get_service()
    body = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time},
        'end': {'dateTime': end_time},
    }
    try:
        event = service.events().insert(calendarId=calendar_id, body=body).execute()
        return _parse_event(event, calendar_id)
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


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
) -> EventInfo:
    """Update an existing event. Only provided fields are changed.
    attendees: list of email addresses to invite.
    reminder_minutes: list of minutes before the event for a popup reminder (e.g. [10, 30])."""
    service = _get_service()
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
        patch['attendees'] = [{'email': e} for e in attendees]
    if reminder_minutes is not None:
        patch['reminders'] = {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': m} for m in reminder_minutes],
        }
    if not patch:
        raise ValueError("Nothing to update — no fields provided.")

    try:
        event = service.events().patch(
            calendarId=calendar_id, eventId=event_id, body=patch
        ).execute()
        return _parse_event(event, calendar_id)
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


@mcp.tool
def delete_event(ctx: Context, event_id: str, calendar_id: str = "primary") -> dict:
    """Delete an event by its ID."""
    service = _get_service()
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"deleted": event_id, "calendar_id": calendar_id}
    except HttpError as e:
        raise RuntimeError(f"Google API Error: {e}")


if __name__ == "__main__":
    mcp.run()
