# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_google_calendar_mcp.py

# Run a single test
poetry run pytest tests/test_echo_server.py::test_echo_tool

# Run Google Calendar server locally (SSE)
fastmcp run mcp-servers/google-calendar/main.py:mcp --transport sse

# Run Google Calendar server locally (stdio)
fastmcp run mcp-servers/google-calendar/main.py:mcp --transport stdio
```

## Architecture

This is a Python monorepo (Poetry) containing MCP servers for the UniBot project, managed via a single `pyproject.toml`. Python source lives under `src/unibot_mcp_servers/`, standalone servers live under `mcp-servers/<server-name>/`.

### Two Server Patterns

**Standard MCP SDK (stdio)** — `src/unibot_mcp_servers/servers/echo_server.py`
- Uses the `mcp` Python SDK with stdio transport
- Intended for local/testing use
- Handlers are exported as standalone async functions (`list_resources()`, `call_tool()`, etc.) alongside the decorated versions — this is required for unit testability

**FastMCP (SSE / Cloud Run)** — `mcp-servers/google-calendar/main.py`
- Uses `fastmcp` with SSE transport, deployed to Google Cloud Run on port 8080
- Custom `GoogleAuthMiddleware` validates the `X-Google-Service-Account` HTTP header (Base64-encoded Service Account JSON) per request; returns 401 if missing/invalid
- Tools receive a `ctx` (FastMCP context) from which the per-request Google API client is retrieved
- `mcp.run()` is used as the entrypoint for both local and Cloud Run execution

### Infrastructure

Terraform under `infra/terraform/` deploys Cloud Run services to GCP:
- `infra/terraform/modules/` — reusable `cloudrun` and `iam` modules
- `infra/terraform/envs/test/` and `envs/prod/` — environment-specific configs
- State stored in GCS bucket `unibot-terraform-state-bucket`
- Cloud Run services are publicly accessible; security is enforced by the mandatory auth header

### CI/CD

`.github/workflows/ci.yml`:
- `development` branch → runs tests + deploys to TEST (image tag `dev-<sha>`)
- `main` branch → runs tests + deploys to PROD (image tags `<sha>` and `latest`)
- Deployment: builds Docker image → pushes to GCR → runs `terraform apply`

### Adding a New Server

Per `PROJECT_SPEC.md`:
1. Place the server in `mcp-servers/<server-name>/main.py` with its own `Dockerfile`
2. Follow the `unibot-<name>-server` naming convention for the MCP server name
3. Export logic handlers as standalone async functions for unit testability
4. Use Pydantic models for tool input validation
5. Add a new Terraform environment config and CI/CD step for deployment
