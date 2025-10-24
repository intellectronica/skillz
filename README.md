# Skillz MCP Server

---

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

---

Skillz is an MCP server that turns [Claude-style skills](https://github.com/anthropics/skills)(`SKILL.md` plus optional resources) into callable tools for any MCP client that speaks. It discovers each skill, exposes the authored instructions and resources, and can run bundled helper scripts.

## Quick Start

To run the MCP server in your agent, use the following config (or equivalent):

```json
{
  "skillz": {
    "command": "uvx",
    "args": ["skillz"]
  }
}
```

with the skills residing at `~/.skillz`

or

```json
{
  "skillz": {
    "command": "uvx",
    "args": ["skillz", "/path/to/skills/direcotry"]
  }
}
```

## CLI Reference

`skillz [skills_root] [options]`

| Flag / Option | Description |
| --- | --- |
| positional `skills_root` | Optional skills directory (defaults to `~/.skillz`). |
| `--timeout SECONDS` | Set the per-script timeout (default `60`). |
| `--transport {stdio,http,sse}` | Choose the FastMCP transport (default `stdio`). |
| `--host HOST` | Bind address for HTTP/SSE transports. |
| `--port PORT` | Port for HTTP/SSE transports. |
| `--path PATH` | URL path when using the HTTP transport. |
| `--list-skills` | List discovered skills and exit. |
| `--verbose` | Emit debug logging to the console. |
| `--log` | Mirror verbose logs to `/tmp/skillz.log`. |

