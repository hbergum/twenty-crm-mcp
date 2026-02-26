# twenty-crm-mcp

MCP server for [Twenty CRM](https://twenty.com) — the open-source CRM.

Built with [FastMCP](https://github.com/jlowin/fastmcp) (Python) for use with Claude Code, Claude Desktop, or any MCP-compatible client.

## Why?

Existing Twenty CRM MCP servers have issues with Twenty's REST API:

- **Search is broken** — the `?search=` query parameter is ignored in Twenty v1.18.x, returning all records instead of filtered results
- **Pagination loops** — cursor-based pagination returns the same page repeatedly in some implementations
- **No note/task linking** — cannot link notes or tasks to people/companies via noteTargets/taskTargets

This server solves all three by using `searchVector[like]` for full-text search, proper cursor pagination with `starting_after`, and automatic noteTarget/taskTarget creation when creating notes and tasks.

## Tools (15)

| Category | Tools |
|---|---|
| **People** | `search_people`, `get_person`, `create_person`, `update_person` |
| **Companies** | `search_companies`, `get_company`, `create_company`, `update_company` |
| **Notes** | `create_note` (with person/company linking), `list_notes`, `get_note` |
| **Tasks** | `create_task` (with person/company linking), `list_tasks`, `get_task` |
| **Utility** | `search_records` (cross-type search) |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/hbergum/twenty-crm-mcp.git
cd twenty-crm-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your Twenty CRM API key and base URL:

```
TWENTY_API_KEY=your-api-key-here
TWENTY_BASE_URL=http://localhost:3000
```

To get an API key: Twenty CRM → Settings → Accounts → API Keys → Create.

### 3. Register with Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "twenty": {
      "type": "stdio",
      "command": "/path/to/twenty-crm-mcp/.venv/bin/python",
      "args": ["/path/to/twenty-crm-mcp/server.py"],
      "env": {}
    }
  }
}
```

Restart Claude Code to load the MCP server.

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "twenty": {
      "command": "/path/to/twenty-crm-mcp/.venv/bin/python",
      "args": ["/path/to/twenty-crm-mcp/server.py"]
    }
  }
}
```

## Usage examples

Once connected, you can ask Claude:

- "Search for John in CRM" → calls `search_people("John")`
- "Create a meeting note for today's visit with John" → calls `create_note(title="Meeting John Smith 26.02.26", body="...", personIds=["..."])`
- "What tasks are open?" → calls `list_tasks(status="TODO")`
- "Search for anything related to microscope" → calls `search_records("microscope")`

## Tested with

- Twenty CRM v1.18.1 (Docker self-hosted)
- Python 3.12
- FastMCP 3.0.2

## License

MIT
