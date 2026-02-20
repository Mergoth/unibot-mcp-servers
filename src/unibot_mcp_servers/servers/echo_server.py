import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types
from pydantic import AnyUrl

# Create a server instance
server = Server("unibot-echo-server")

async def list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri=AnyUrl("echo://hello"),
            name="Echo Resource",
            description="A simple echo resource",
            mimeType="text/plain",
        )
    ]

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return await list_resources()

async def read_resource(uri: AnyUrl) -> str:
    """Read a resource."""
    if uri.scheme != "echo":
        raise ValueError(f"Unsupported scheme: {uri.scheme}")
    return f"Echoing from {uri}"

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    return await read_resource(uri)

async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="echo",
            description="Echoes the input string",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
                "required": ["message"],
            },
        )
    ]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return await list_tools()

async def call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    if name == "echo":
        message = arguments.get("message", "") if arguments else ""
        return [types.TextContent(type="text", text=f"Echo: {message}")]
    raise ValueError(f"Unknown tool: {name}")

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    return await call_tool(name, arguments)

async def main():
    # In a real scenario, you'd use stdio or other transport
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                serverName="unibot-echo-server",
                serverVersion="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
