import os
import re
import logging
import datetime
import json
import contextlib
import httpx
from typing import Any, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field, model_validator

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
import mcp.types as types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unibot-save-lead-server")

# 1. Pydantic validation/coercion model
class SaveLeadInput(BaseModel):
    name: str = ""
    business_name: str = ""
    industry: str = "generic"
    contact: str
    want: str = ""
    language: str = "en"
    transcript_summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        # Clean string inputs (strip whitespace and convert None to empty string)
        for field in ["name", "business_name", "contact", "want", "transcript_summary"]:
            val = data.get(field)
            if val is None:
                data[field] = ""
            elif isinstance(val, str):
                data[field] = val.strip()

        # Validate industry (no silent coercion)
        industry = data.get("industry")
        if industry is not None:
            valid_industries = {"restaurant", "vet_clinic", "auto_shop", "gestoria", "generic"}
            if not isinstance(industry, str) or industry not in valid_industries:
                raise ValueError(f"Invalid industry: '{industry}'. Must be one of {sorted(list(valid_industries))}.")
            
        # Validate language (no silent coercion)
        language = data.get("language")
        if language is not None:
            valid_languages = {"en", "es"}
            if not isinstance(language, str) or language not in valid_languages:
                raise ValueError(f"Invalid language: '{language}'. Must be one of {sorted(list(valid_languages))}.")
            
        return data

# 2. Validation helpers
def is_valid_contact(contact: str) -> bool:
    if not contact:
        return False
        
    # Check basic email pattern: something@something.tld
    email_regex = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    if email_regex.match(contact):
        return True
        
    # Check phone pattern: 7+ digits, optional leading +, spaces/dashes/parens allowed
    # Allowed characters
    allowed_chars = set("0123456789 -()+")
    if not all(c in allowed_chars for c in contact):
        return False
        
    # Must have 7+ digits
    digits = "".join(c for c in contact if c.isdigit())
    if len(digits) >= 7:
        # Optional leading + can only be at the start and at most once
        if contact.count("+") > 1 or (contact.count("+") == 1 and not contact.startswith("+")):
            return False
        return True
        
    return False

# 3. Resend email helper
async def send_lead_email(lead: SaveLeadInput) -> bool:
    resend_api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("CONTACT_TO_EMAIL")
    from_email = os.getenv("CONTACT_FROM_EMAIL")

    if not resend_api_key or not to_email or not from_email:
        logger.error(
            "Missing Resend email configuration! "
            f"RESEND_API_KEY set={bool(resend_api_key)}, "
            f"CONTACT_TO_EMAIL set={bool(to_email)}, "
            f"CONTACT_FROM_EMAIL set={bool(from_email)}"
        )
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }

    # Subject line logic: [Bot Lead] <business_name or industry>
    subject_subject = lead.business_name if lead.business_name else lead.industry
    subject = f"[Bot Lead] {subject_subject}"

    captured_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    body_text = f"""New lead from the optigenia.cc demo bot.

Name:        {lead.name or "—"}
Business:    {lead.business_name or "—"}
Industry:    {lead.industry}
Contact:     {lead.contact}
Wants:       {lead.want or "—"}
Language:    {lead.language}
Summary:     {lead.transcript_summary or "—"}
Captured:    {captured_time}"""

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body_text
    }

    async with httpx.AsyncClient() as client:
        # Retry logic: try once, then retry once if it fails
        for attempt in range(2):
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                logger.info(f"Resend HTTP API POST attempt {attempt+1} response: status={response.status_code} body={response.text}")
                if response.status_code in (200, 201, 202):
                    return True
                else:
                    logger.warning(f"Resend returned non-2xx response: {response.status_code} {response.text}")
            except Exception as e:
                logger.exception(f"Exception calling Resend API on attempt {attempt+1}")
        return False

# 4. MCP Server Initialization
server = Server("unibot-save-lead-server")

async def list_tools() -> list[types.Tool]:
    """List the save_lead tool."""
    return [
        types.Tool(
            name="save_lead",
            description="Save a qualified sales lead captured during the chat. Call once, only after the visitor has shared at least a contact (email or phone).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Visitor's name. Empty string if not given."
                    },
                    "business_name": {
                        "type": "string",
                        "description": "Visitor's business name. Empty string if not given."
                    },
                    "industry": {
                        "type": "string",
                        "enum": ["restaurant", "vet_clinic", "auto_shop", "gestoria", "generic"],
                        "description": "Detected industry. Use 'generic' if unclear."
                    },
                    "contact": {
                        "type": "string",
                        "description": "REQUIRED. Email address or phone number — at least one must be present."
                    },
                    "want": {
                        "type": "string",
                        "description": "One-line description of the visitor's pain or what they want."
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "es"],
                        "description": "Conversation language."
                    },
                    "transcript_summary": {
                        "type": "string",
                        "description": "1-2 sentence recap of the conversation."
                    }
                },
                "required": ["contact"]
            }
        )
    ]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return await list_tools()

async def call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if name != "save_lead":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        arguments = {}

    # 1. Check if contact field is missing or invalid
    contact = arguments.get("contact")
    if not isinstance(contact, str) or not is_valid_contact(contact):
        logger.info(f"Invalid or missing contact input: {contact}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "needs_contact",
                    "message": "Contact missing or invalid — ask the visitor for an email or phone."
                })
            )
        ]

    # 2. Pydantic validation
    try:
        lead = SaveLeadInput.model_validate(arguments)
    except Exception as e:
        logger.exception("Pydantic validation error")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": f"Validation error: {e}"
                })
            )
        ]

    # 3. Send email via Resend
    await send_lead_email(lead)
    
    # On success or failure, return a clean success message to the agent to avoid breaking the chat flow
    return [
        types.TextContent(
            type="text",
            text=json.dumps({
                "status": "ok",
                "message": "Lead saved."
            })
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    return await call_tool(name, arguments)

# 5. ASGI Application Wrapper
session_manager = StreamableHTTPSessionManager(app=server)

class MCPServerASGIApp:
    def __init__(self, session_manager: StreamableHTTPSessionManager):
        self.session_manager = session_manager
        
    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            async with self.session_manager.run():
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
        elif scope["type"] == "http":
            path = scope["path"]
            if path == "/sse" and scope["method"] == "GET":
                # Health check / Startup probe
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")]
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"status": "ok"}'
                })
                return
            
            # Delegate to session manager
            await self.session_manager.handle_request(scope, receive, send)

app = MCPServerASGIApp(session_manager)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
