# UniBot MCP Servers

This repository contains a collection of Model Context Protocol (MCP) servers for the UniBot project.

## Project Structure

- `src/unibot_mcp_servers/servers/`: Contains the individual MCP server implementations.
- `tests/`: Unit and integration tests for the servers.

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Poetry**

### Installation

```bash
cd ~/work/unibot-mcp-servers
poetry install
```

### Running a Server

You can run a server using the `stdio` transport, which is compatible with most MCP clients (like Claude Desktop or UniBot).

```bash
poetry run python -m unibot_mcp_servers.servers.echo_server
```

## Available Servers

### 1. Echo Server (`echo_server.py`)
A simple server that provides an `echo` tool and an `echo://` resource. Useful for testing connectivity.

### 2. Google Calendar Server (Standalone)
A native MCP server for Google Calendar using Service Account authentication. Located in `mcp-servers/google-calendar/`. Suitable for deployment to Cloud Run via SSE.

## Integration with UniBot

To use these servers in UniBot, add them to your `config/env/{ENVIRONMENT}.yaml` (or via the database/json storage if configured):

```yaml
mcp_servers:
  echo:
    command: "poetry"
    args: ["--directory", "/Users/vladislav/work/unibot-mcp-servers", "run", "python", "-m", "unibot_mcp_servers.servers.echo_server"]
    enabled: true
```
