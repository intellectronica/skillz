# Skillz

## 👌 **Use _skills_ in any agent** _(Codex, Copilot, Cursor, etc...)_

[![PyPI version](https://img.shields.io/pypi/v/skillz.svg)](https://pypi.org/project/skillz/)
[![PyPI downloads](https://img.shields.io/pypi/dm/skillz.svg)](https://pypi.org/project/skillz/)

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

**Skillz** is an MCP server that turns [Claude-style skills](https://github.com/anthropics/skills) _(`SKILL.md` plus optional resources)_ into callable tools for any MCP client. It discovers each skill, exposes the authored instructions and resources, and can run bundled helper scripts.

> 💡 You can find skills to install at the **[Skills Supermarket](http://skills.intellectronica.net/)** directory.

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

or Docker

You can run Skillz using Docker for isolation. The image is available on Docker Hub at `intellectronica/skillz`.

To run the Skillz MCP server with your skills directory mounted using Docker, configure your agent as follows: 

Replace `/path/to/skills` with the path to your actual skills directory. Any arguments after `intellectronica/skillz` in the array are passed directly to the Skillz CLI.

```json
{
  "skillz": {
    "command": "docker",
    "args": [
      "run",
      "-i",
      "--rm",
      "-v",
      "/path/to/skills:/skillz",
      "intellectronica/skillz",
      "/skillz"
    ]
  }
}
```

## Gemini CLI Extension

A Gemini CLI extension is available at [intellectronica/gemini-cli-skillz](https://github.com/intellectronica/gemini-cli-skillz).

Install it with:

```bash
gemini extensions install https://github.com/intellectronica/gemini-cli-skillz
```

This extension enables Anthropic-style Agent Skills in Gemini CLI using the skillz MCP server.

## Usage

Skillz looks for skills inside the root directory you provide (defaults to
`~/.skillz`). Each skill lives in its own folder or zip archive (`.zip` or `.skill`)
that includes a `SKILL.md` file with YAML front matter describing the skill. Any
other files in the skill become downloadable resources for your agent (scripts,
datasets, examples, etc.).

An example directory might look like this:

```text
~/.skillz/
├── summarize-docs/
│   ├── SKILL.md
│   ├── summarize.py
│   └── prompts/example.txt
├── translate.zip
├── analyzer.skill
└── web-search/
    └── SKILL.md
```

When packaging skills as zip archives (`.zip` or `.skill`), include the `SKILL.md`
either at the root of the archive or inside a single top-level directory:

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

### Directory Structure: Skillz vs Claude Code

Skillz supports a more flexible skills directory than Claude Code. In addition to a flat layout, you can organize skills in nested subdirectories and include skills packaged as `.zip` or `.skill` files (as shown in the examples above).

Claude Code, on the other hand, expects a flat skills directory: every immediate subdirectory is a single skill. Nested directories are not discovered, and `.zip` or `.skill` files are not supported.

If you want your skills directory to be compatible with Claude Code (for example, so you can symlink one skills directory between the two tools), you must use the flat layout.

**Claude Code–compatible layout:**

```text
skills/
├── hello-world/
│   ├── SKILL.md
│   └── run.sh
└── summarize-text/
    ├── SKILL.md
    └── run.py
```

**Skillz-only layout examples** (not compatible with Claude Code):

```text
skills/
├── text-tools/
│   └── summarize-text/
│       ├── SKILL.md
│       └── run.py
├── image-processing.zip
└── data-analyzer.skill
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
