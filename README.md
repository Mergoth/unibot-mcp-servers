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

### Running Locally (for testing)

While deployed versions use HTTP SSE exclusively, you can run a server locally for testing purposes using the FastMCP CLI.

```bash
fastmcp run mcp-servers/google-calendar/main.py:mcp --transport sse
```

## Available Servers

### 1. Echo Server (`echo_server.py`)
A simple server that provides an `echo` tool and an `echo://` resource. Useful for testing connectivity.

### 2. Google Calendar Server (Standalone)
A native MCP server for Google Calendar located in `mcp-servers/google-calendar/`. It uses **FastMCP** and is built specifically for scalable, secure deployment to Google Cloud Run via Server-Sent Events (SSE). 

#### Universal, Generic Integration (Public + SA Secret)
Because Unibot is a lightweight, universal agent platform, this MCP server is designed to be fully decoupled and completely generic. It is deployed as a **Public Endpoint** on Google Cloud Run (`allow_public_access = true`), meaning *any* Unibot instance can call it across the internet.

To keep it secure and maintain its stateless design without complex OAuth consent screens, it operates using a **Mandatory Secret Injection Policy**:

**1. The Secrets (Google Service Account JSON)**
Instead of dealing with user-facing OAuth flows, Unibot administrators create standard **Google Cloud Service Accounts**, grant those service accounts access to the necessary Google Calendars (via standard Google Calendar sharing), and store their raw JSON key payloads as strings in **GCP Secret Manager** or their own secret store.

**2. The Injected HTTP Header**
When Unibot connects to this MCP server via SSE, it must inject that target user's Service Account JSON payload (Base64 Encoded) directly into the HTTP headers:
```http
X-Google-Service-Account: <BASE64_ENCODED_JSON_STRING>
```

**3. Server Execution (FastMCP Middleware)**
The MCP server intercepts this header instantly. If missing or invalid, it returns `401 Unauthorized`. If valid, it dynamically mounts the Google API client in memory for that exact request lifecycle using those credentials. The agent gets the calendar data natively, and the MCP server remains safely stateless.

## Integration with UniBot (Cloud Run SSE)

To configure Unibot to use this public, secure endpoint, configure the Server-Sent Events (SSE) connection and inject the custom Service Account header.

```yaml
mcp_servers:
  google_calendar:
    # Universal Public URL of your deployed Cloud Run service
    url: "https://google-calendar-mcp-xxxxxxx.a.run.app/sse"
    transport: "sse"
    enabled: true
    # Configure Unibot to fetch the JSON from Secret Manager and encode it:
    headers:
      X-Google-Service-Account: "{{ secret('google_calendar_sa_json') | base64 }}"
```
*Note: The exact syntax (`{{ secret(...) | base64 }}`) depends on your Unibot ADK configuration loader. The requirement is that your HTTP Client successfully passes the base64-encoded Service Account JSON in the `X-Google-Service-Account` header.*
