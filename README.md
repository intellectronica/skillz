# Skillz

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

[![PyPI version](https://img.shields.io/pypi/v/skillz.svg)](https://pypi.org/project/skillz/)
[![PyPI downloads](https://img.shields.io/pypi/dm/skillz.svg)](https://pypi.org/project/skillz/)
[![Install in VS Code](https://img.shields.io/badge/Use_Skillz_in-VS_Code-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/Use_Skillz_in-VS_Code_Insiders-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D&quality=insiders)
[![Install in Cursor](https://img.shields.io/badge/Use_Skillz_in-Cursor-000000?style=flat-square&logoColor=white)](https://cursor.com/en/install-mcp?name=Skillz&config=eyJuYW1lIjoiU2tpbGx6IiwiY29tbWFuZCI6InV2eCIsImFyZ3MiOlsic2tpbGx6Il0sImVudiI6e319)

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
