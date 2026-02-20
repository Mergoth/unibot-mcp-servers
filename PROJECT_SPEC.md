# Project Specification: UniBot MCP Servers

## Overview
A centralized repository for hosting custom Model Context Protocol (MCP) servers used by UniBot and other compatible clients.

## Technology Stack
- **Language**: Python 3.12
- **Package Manager**: Poetry
- **Framework**: `mcp` (Python SDK)
- **Transport**: Stdio (Primary)

## Directory Structure
- `src/unibot_mcp_servers/`: Core package.
  - `servers/`: Individual server implementations.
- `tests/`: Project tests.
- `pyproject.toml`: Dependencies and project metadata.

## Standards
1. **Server Naming**: Servers should follow the naming convention `unibot-<name>-server`.
2. **Exposed Functions**: For unit testing, logic handlers (list_resources, call_tool, etc.) must be decorated but also exported as standalone async functions.
3. **Pydantic**: Use Pydantic models for input validation in tools.
4. **Error Handling**: Use standard MCP error types and clear error messages.
