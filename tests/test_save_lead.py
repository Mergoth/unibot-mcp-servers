import sys
import os
import json
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add the server directory to path to allow importing 'main'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp-servers/save-lead')))

# Remove any previously cached 'main' module to prevent namespace clashing in pytest
sys.modules.pop("main", None)

import main
import mcp.types as types

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key_123")
    monkeypatch.setenv("CONTACT_TO_EMAIL", "founder@example.com")
    monkeypatch.setenv("CONTACT_FROM_EMAIL", "bot@verifieddomain.com")

@pytest.mark.asyncio
async def test_list_tools():
    """Verify that the save_lead tool is correctly listed and matches the JSON schema."""
    tools = await main.handle_list_tools()
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "save_lead"
    assert "REQUIRED. Email address or phone number" in tool.inputSchema["properties"]["contact"]["description"]
    assert tool.inputSchema["required"] == ["contact"]

@pytest.mark.asyncio
async def test_validation_invalid_contact():
    """Verify that invalid contact strings are rejected and return needs_contact."""
    invalid_contacts = [
        "",
        "   ",
        "invalid_email",
        "invalid@email",
        "123456",        # Only 6 digits
        "+123456",       # Only 6 digits with leading plus
        "+1234567+",     # plus not at start
        "123-456",       # Only 6 digits with separator
        "abc-def-ghij",  # non-numeric characters for phone
    ]
    for contact in invalid_contacts:
        result = await main.handle_call_tool("save_lead", {"contact": contact})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "needs_contact"
        assert "Contact missing or invalid" in data["message"]

@pytest.mark.asyncio
@patch("main.send_lead_email", new_callable=AsyncMock)
async def test_validation_valid_contact(mock_send_email):
    """Verify that valid emails and phone numbers are accepted and trigger email sending."""
    mock_send_email.return_value = True
    valid_contacts = [
        "test@example.com",
        "test.name+alias@domain.co.uk",
        "1234567",
        "+1234567",
        "+1 (234) 567-8901",
        " 123-4567 ",
        "(123) 456-7890",
    ]
    for contact in valid_contacts:
        mock_send_email.reset_mock()
        result = await main.handle_call_tool("save_lead", {"contact": contact})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "ok"
        mock_send_email.assert_called_once()

@pytest.mark.asyncio
@patch("main.send_lead_email", new_callable=AsyncMock)
async def test_enum_coercion(mock_send_email):
    """Verify that invalid enum values for industry and language are coerced."""
    mock_send_email.return_value = True
    
    # Test invalid industry and language
    arguments = {
        "contact": "test@example.com",
        "industry": "invalid_industry",
        "language": "invalid_lang",
    }
    result = await main.handle_call_tool("save_lead", arguments)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    
    # Check that the coerced values were passed to the email sender
    called_lead = mock_send_email.call_args[0][0]
    assert called_lead.industry == "generic"
    assert called_lead.language == "en"

@pytest.mark.asyncio
@patch("main.send_lead_email", new_callable=AsyncMock)
async def test_valid_enums_not_coerced(mock_send_email):
    """Verify that valid enum values for industry and language are preserved."""
    mock_send_email.return_value = True
    
    arguments = {
        "contact": "test@example.com",
        "industry": "vet_clinic",
        "language": "es",
        "name": "John Doe",
        "business_name": "VetCare",
    }
    result = await main.handle_call_tool("save_lead", arguments)
    assert len(result) == 1
    
    called_lead = mock_send_email.call_args[0][0]
    assert called_lead.industry == "vet_clinic"
    assert called_lead.language == "es"
    assert called_lead.name == "John Doe"
    assert called_lead.business_name == "VetCare"

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_email_success(mock_post):
    """Verify successful email sending using mock HTTPX client."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Success"
    mock_post.return_value = mock_response
    
    lead = main.SaveLeadInput(
        contact="founder@example.com",
        name="Alice",
        business_name="Alice Corp",
        industry="restaurant"
    )
    
    success = await main.send_lead_email(lead)
    assert success is True
    mock_post.assert_called_once()
    
    # Inspect arguments passed to POST
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key_123"
    payload = kwargs["json"]
    assert payload["from"] == "bot@verifieddomain.com"
    assert payload["to"] == ["founder@example.com"]
    assert payload["subject"] == "[Bot Lead] Alice Corp"
    assert "Alice" in payload["text"]
    assert "Alice Corp" in payload["text"]
    assert "restaurant" in payload["text"]

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_email_retry_success(mock_post):
    """Verify that a failed first attempt retries and returns success on the second attempt."""
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_fail.text = "Internal Error"
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.text = "Success"
    
    # First call fails, second call succeeds
    mock_post.side_effect = [mock_response_fail, mock_response_success]
    
    lead = main.SaveLeadInput(
        contact="1234567890",
        industry="generic"
    )
    
    success = await main.send_lead_email(lead)
    assert success is True
    assert mock_post.call_count == 2

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_email_absolute_failure(mock_post):
    """Verify that if all attempts fail, it returns False but does not throw."""
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_fail.text = "Internal Error"
    mock_post.return_value = mock_response_fail
    
    lead = main.SaveLeadInput(
        contact="1234567890",
        industry="generic"
    )
    
    success = await main.send_lead_email(lead)
    assert success is False
    assert mock_post.call_count == 2
