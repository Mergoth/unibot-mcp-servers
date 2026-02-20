import pytest
from unibot_mcp_servers.servers.echo_server import server, call_tool, list_tools
import mcp.types as types

@pytest.mark.asyncio
async def test_echo_tool():
    # Test the echo tool logic directly
    arguments = {"message": "Hello MCP"}
    result = await call_tool("echo", arguments)
    
    assert len(result) == 1
    assert isinstance(result[0], types.TextContent)
    assert result[0].text == "Echo: Hello MCP"

@pytest.mark.asyncio
async def test_list_tools():
    tools = await list_tools()
    assert any(t.name == "echo" for t in tools)
