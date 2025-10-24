# Skillz

## 👌 **Use _skills_ in any agent** _(Codex, Copilot, Cursor, etc...)_

[![PyPI version](https://img.shields.io/pypi/v/skillz.svg)](https://pypi.org/project/skillz/)
[![PyPI downloads](https://img.shields.io/pypi/dm/skillz.svg)](https://pypi.org/project/skillz/)

> ⚠️ **Experimental proof‑of‑concept. Skills may contain executable code. Review skill contents before use and run in sandboxes/containers when appropriate.**

**Skillz** is an MCP server that turns [Claude-style skills](https://github.com/anthropics/skills)_(`SKILL.md` plus optional resources)_ into callable tools for any MCP client. It discovers each skill and exposes the authored instructions along with all associated resources (markdown, scripts, templates, etc.) as MCP resources. Clients read these resources and decide how to use them—including executing scripts if needed.

## Quick Start

To run the MCP server in your agent, use the following config (or equivalent):

```json
{
  "skillz": {
    "command": "uvx",
    "args": ["skillz@latest"]
  }
}
```

with the skills residing at `~/.skillz`

_or_

```json
{
  "skillz": {
    "command": "uvx",
    "args": ["skillz@latest", "/path/to/skills/direcotry"]
  }
}
```

## CLI Reference

`skillz [skills_root] [options]`

| Flag / Option | Description |
| --- | --- |
| positional `skills_root` | Optional skills directory (defaults to `~/.skillz`). |
| `--transport {stdio,http,sse}` | Choose the FastMCP transport (default `stdio`). |
| `--host HOST` | Bind address for HTTP/SSE transports. |
| `--port PORT` | Port for HTTP/SSE transports. |
| `--path PATH` | URL path when using the HTTP transport. |
| `--list-skills` | List discovered skills and exit. |
| `--verbose` | Emit debug logging to the console. |
|| `--log` | Mirror verbose logs to `/tmp/skillz.log`. |

## How It Works

When you invoke a skill tool, Skillz returns:

1. **Instructions**: The skill's markdown content explaining how to complete the task
2. **Resources**: A list of all files in the skill directory with their MCP resource URIs
3. **Metadata**: Name, description, license, and other skill properties

Clients can then:
- Read the instructions to understand what to do
- Use `ctx.read_resource(uri)` to fetch any supporting files (templates, scripts, data, etc.)
- Execute scripts themselves if needed using appropriate tooling

**Example workflow:**
```python
# 1. Call the skill tool to get instructions and resource URIs
response = await client.call_tool("my-skill", {"task": "Generate a report"})

# 2. Read the instructions
print(response["instructions"])

# 3. Access resources as needed
for resource in response["resources"]:
    if resource["relative_path"] == "templates/report.md":
        content = await ctx.read_resource(resource["uri"])
        # Use the template...
    elif resource["relative_path"] == "scripts/process.py":
        script = await ctx.read_resource(resource["uri"])
        # Execute the script yourself if desired...
```

---

> Made with 🫶 by [`@intellectronica`](https://intellectronica.net)
