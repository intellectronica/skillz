# Skillz

## 👌 **Use _skills_ in any agent** _(Codex, Copilot, Cursor, etc...)_

[![PyPI version](https://img.shields.io/pypi/v/skillz.svg)](https://pypi.org/project/skillz/)
[![PyPI downloads](https://img.shields.io/pypi/dm/skillz.svg)](https://pypi.org/project/skillz/)

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

**Skillz** is an MCP server that turns [Claude-style skills](https://github.com/anthropics/skills)_(`SKILL.md` plus optional resources)_ into callable tools for any MCP client. It discovers each skill, exposes the authored instructions and resources, and can run bundled helper scripts.

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

## Usage

Skillz looks for skills inside the root directory you provide (defaults to
`~/.skillz`). Each skill lives in its own folder or zip archive that includes a
`SKILL.md` file with YAML front matter describing the skill. Any other files in
the skill become downloadable resources for your agent (scripts, datasets,
examples, etc.).

An example directory might look like this:

```text
~/.skillz/
├── summarize-docs/
│   ├── SKILL.md
│   ├── summarize.py
│   └── prompts/example.txt
├── translate.zip
└── web-search/
    └── SKILL.md
```

When packaging skills as zips, include the `SKILL.md` either at the root of the
archive or inside a single top-level directory:

```text
translate.zip
├── SKILL.md
└── helpers/
    └── translate.js
```

```text
data-cleaner.zip
└── data-cleaner/
    ├── SKILL.md
    └── clean.py
```

You can use `skillz --list-skills` (optionally pointing at another skills root)
to verify which skills the server will expose before connecting it to your
agent.

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
| `--log` | Mirror verbose logs to `/tmp/skillz.log`. |

---

> Made with 🫶 by [`@intellectronica`](https://intellectronica.net)
