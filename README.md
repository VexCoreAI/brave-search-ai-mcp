# Brave Search AI MCP

A local, stdio-based [Model Context Protocol](https://modelcontextprotocol.io/)
server that lets MCP-compatible AI clients search the web with Brave Search AI.
It returns the generated answer, source citations, and suggested follow-up
questions.

This project is independent and is not affiliated with or endorsed by Brave
Software.

## What it does

The server runs a headless Chromium browser locally with Playwright, opens a
Brave Search results page, and extracts the AI answer and citations. It does not
use a Brave Search API key. Search terms are sent to Brave Search, and the
scraping implementation may need updates if Brave changes its website. Use it
in accordance with Brave's terms and applicable rate limits.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Chromium dependencies supported by [Playwright](https://playwright.dev/python/docs/intro)

No Brave account or API key is required by this server.

## Install

Clone the repository and run the setup script:

```sh
git clone https://github.com/VexCoreAI/brave-search-ai-mcp.git
cd brave-search-ai-mcp
./scripts/setup.sh
```

The script creates a project virtual environment, installs locked dependencies,
and downloads Playwright Chromium. On Linux, Playwright may require system
packages; see its [browser installation guide](https://playwright.dev/python/docs/browsers#install-system-dependencies).

To start the server manually:

```sh
./run.sh
```

The process speaks MCP over standard input and output. Do not start it in a
terminal and expect human-readable output. Protocol diagnostics are written to
standard error.

If Playwright Chromium cannot start and Chrome is installed on the machine, set
`BRAVE_BROWSER_CHANNEL=chrome` in the MCP server's environment. The scraper
falls back to bundled Chromium if that channel cannot launch.

## MCP tool

### `brave_search`

Searches the web and returns the Brave Search AI response and source citations.

| Argument | Type | Default | Allowed values |
| --- | --- | ---: | --- |
| `query` | string | required | Non-empty search question or phrase |
| `timeout` | integer | `20` | 5 to 120 seconds per attempt |
| `retries` | integer | `3` | 1 to 5 attempts |

Successful calls return JSON with this shape:

```json
{
  "query": "What is the Model Context Protocol?",
  "has_ai_response": true,
  "answer": "...",
  "citations": [
    { "url": "https://example.com/", "title": "Example", "snippet": "..." }
  ],
  "followups": ["..."],
  "conversation_id": "...",
  "strategy": "SSE Network Interception",
  "error": null
}
```

If the search cannot be completed, the result includes a non-empty `error`.
`has_ai_response` can be false when Brave returns search results without an AI
answer. Citations and follow-up questions may be empty.

## Connect an AI client

This server uses the standard local **stdio** transport, so no hosted endpoint,
account, or API key is needed. First complete the installation above. Replace
`/ABSOLUTE/PATH` below with the actual path to the cloned repository. Some
desktop clients do not inherit your shell `PATH`, so use the full path to
`run.sh` and restart the client after changing its MCP configuration.

### Claude Desktop

Add this entry to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "brave-search-ai": {
      "command": "/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"
    }
  }
}
```

See [Claude Desktop local MCP setup](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).

### Claude Code

```sh
claude mcp add --scope user --transport stdio brave-search-ai -- /ABSOLUTE/PATH/brave-search-ai-mcp/run.sh
```

Check the connection with `claude mcp list`. See the [Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

### OpenCode

Add a local server to the `mcp.servers` section of `opencode.json`:

```json
{
  "mcp": {
    "servers": {
      "brave-search-ai": {
        "type": "local",
        "command": ["/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"],
        "enabled": true
      }
    }
  }
}
```

See the [OpenCode MCP server guide](https://opencode.ai/docs/mcp-servers/).

### Cursor

Add the server to `.cursor/mcp.json` in a project, or to your user-level Cursor
MCP configuration:

```json
{
  "mcpServers": {
    "brave-search-ai": {
      "command": "/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"
    }
  }
}
```

See [Cursor MCP configuration](https://cursor.com/docs/mcp).

### Visual Studio Code with GitHub Copilot

Add this server to `.vscode/mcp.json`:

```json
{
  "servers": {
    "brave-search-ai": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"
    }
  }
}
```

See [VS Code MCP server configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).

### Windsurf

Add this entry to Windsurf's `mcp_config.json`:

```json
{
  "mcpServers": {
    "brave-search-ai": {
      "command": "/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"
    }
  }
}
```

See the [Windsurf MCP guide](https://docs.windsurf.com/windsurf/cascade/mcp).

### Gemini CLI

Add this entry to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "brave-search-ai": {
      "command": "/ABSOLUTE/PATH/brave-search-ai-mcp/run.sh"
    }
  }
}
```

See the [Gemini CLI MCP guide](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html).

### Other MCP clients

Configure a local MCP server using **stdio** and set its command to the
absolute path of `run.sh`. If a client requires separate command and argument
fields, use the script path as the command and leave the argument list empty.
The MCP transport is client-neutral; the configuration file format and MCP
support vary by client.

## Development

```sh
uv sync --locked --all-groups
uv run playwright install chromium
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests use mocked search results and parser fixtures. They do not launch a real
browser or send queries to Brave.

## Attribution and licensing

The scraper is derived from
[`ijuttt/scrape-brave-ai`](https://github.com/ijuttt/scrape-brave-ai) and is
included with permission. See [`NOTICE.md`](NOTICE.md) for attribution. This
repository is distributed under the MIT License in [`LICENSE`](LICENSE), with
permission covering the upstream-derived code. The upstream repository itself
does not provide a license file.

## Limitations

- Brave's website and private response formats can change without notice.
- Brave may rate-limit or block automated browser traffic.
- The server returns Brave's AI answer when available; it is not a general
  purpose browser automation server or a guaranteed search API.
- This implementation uses stdio only. It does not expose a remote HTTP server.
