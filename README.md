# Skillz MCP Server

**Status: experimental proof of concept – untested and unsafe for production use.**

This repository hosts `skillz.py`, a single-file MCP server that exposes
Anthropic-style Skills stored on disk to Model Context Protocol clients. It
discovers folders containing a `SKILL.md` file with YAML front matter, registers
each skill as both a prompt and a tool, and lazily loads content when the client
requests it. Scripts bundled with a skill run inside a temporary workspace so
the original files remain untouched.

## Prerequisites

- Python 3.12 or newer (managed automatically when using `uv`)
- `uv` package manager (the script metadata declares runtime dependencies)

## Quick Start

1. Populate a directory with skills following Anthropic’s format
   (`SKILL.md` + optional resources).
2. Run the server with the directory path:

   ```bash
   uv run skillz.py /path/to/skills --verbose
   ```

   By default the server listens over `stdio`. Pass `--transport http` or
   `--transport sse` with `--host`, `--port`, and `--path` if your client needs a
   network transport.
3. Use `--list-skills` to validate parsing without starting the transport:

   ```bash
   uv run skillz.py /path/to/skills --list-skills
   ```

## Tool Actions

Each discovered skill registers a tool named simply by its slug (for example
`algorithmic-art`). The tool
description is populated from the skill metadata (name, summary, license,
allowed tools, available resources). When invoked it:

1. Requires a `task` string describing what the client wants to accomplish.
2. Automatically calls `ctx.sample` with the skill’s `SKILL.md` body so the
   model can ground its response in the published instructions.
3. Optionally runs a bundled script when `script` is provided alongside a
   `script_payload` mapping (keys: `args`, `env`, `files`, `stdin`, `workdir`).
   Execution happens inside a temporary copy of the skill directory and the
   result (command, stdout/stderr, return code, duration) is returned to the
   caller.

The tool response contains the sampled plan plus the script result if one ran.

## Security & Safety Notice

- This code is **experimental**, **untested**, and should be treated as unsafe.
- Script execution happens outside any sandbox besides a temporary directory.
  Use only with trusted skill content and within controlled environments.
- Review and harden before exposing to real users or sensitive workflows.

## License

Released under the MIT License (see `LICENSE`).
