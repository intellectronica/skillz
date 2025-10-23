# Skillz MCP Server

---

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

---

`skillz` is a Python package and CLI that exposes [Anthropic‑style skills](https://github.com/anthropics/skills) (directories with a `SKILL.md` that starts with YAML front‑matter) to any MCP client using [FastMCP](https://pypi.org/project/fastmcp/). It recursively discovers skills, registers one tool per skill, returns the authored instructions and resource paths, and can optionally run helper scripts inside a temporary workspace. The package is published on PyPI, so you can launch it anywhere with `uvx skillz`.

## Features

- Recursively discovers every `SKILL.md` beneath the provided skills root (default: `~/.skillz`) and creates one MCP tool per skill slug (derived from the skill `name`).
- Tool calls return the skill instructions, metadata, and an absolute path list for every file shipped with the skill so clients can fetch resources directly or via `ctx.read_resource`.
- Optional `script` execution copies the skill to a temp directory, applies file/env/stdin payloads, runs the script with the right interpreter, and returns stdout/stderr/output metadata.
- Supports `stdio`, `http`, and `sse` transports through FastMCP so you can connect the server to a variety of MCP clients.

## Prerequisites

- Python 3.12 or newer (managed automatically when using `uv`)
- `uv` package manager (the script metadata declares runtime dependencies)

## Quick Start

1. Populate a directory with skills following Anthropic’s format
   (`SKILL.md` + optional resources). The CLI looks for `~/.skillz` by
   default, but any directory can be supplied explicitly.
2. Run the server. Supplying a directory path is optional—the CLI defaults to `~/.skillz` when no positional argument is provided (the path is expanded like any shell `~` reference):

   ```bash
   # Use explicit directory
   uvx skillz /path/to/skills

   # Or rely on the default ~/.skillz location
   uvx skillz
   ```

   The server listens over `stdio` by default. Pass `--transport http` or
   `--transport sse` and combine with `--host`, `--port`, and `--path` for
   network transports.
3. Use `--list-skills` to validate parsing without starting the transport:

   ```bash
   uvx skillz /path/to/skills --list-skills
   ```

4. Add `--verbose` for console debug logs or `--log` for
   extremely verbose output written to `/tmp/skillz.log`.

## CLI reference

`skillz` understands the following flags:

| Flag | Description |
| --- | --- |
| positional `skills_root` | Directory of skills (optional, defaults to `~/.skillz`). |
| `--timeout` | Per-script timeout in seconds (default: `60`). |
| `--transport {stdio,http,sse}` | Transport exposed by FastMCP (default: `stdio`). |
| `--host`, `--port`, `--path` | Network settings for HTTP/SSE transports (`--path` applies to HTTP only). |
| `--list-skills` | Print discovered skills and exit. |
| `--verbose` | Emit debug logging to the console. |
| `--log` | Mirror detailed logs to `/tmp/skillz.log`. |

## Tool responses & script execution

Each tool invocation expects a non-empty `task` string and responds with:

- `skill`: the slug derived from the skill `name`.
- `task`: echo of the task that triggered the tool call.
- `metadata`: name, description, license (if provided), allowed tools, and any extra front-matter fields.
- `resources`: absolute paths to the `SKILL.md` and every other file shipped with the skill.
- `instructions`: the Markdown body from `SKILL.md`.
- `usage`: a convenience block containing a suggested MCP prompt, integration guidance, and script execution instructions.

Provide `script` to run a helper program bundled with the skill. The optional
`script_payload` mapping supports:

- `args`: iterable of command-line arguments.
- `env`: mapping of environment variables merged into the sandbox.
- `files`: list of `{path, content, encoding}` entries written relative to the copied skill directory.
- `stdin`: raw text or `{content, encoding}` to feed to the process.
- `workdir`: working directory relative to the copied skill root.

Scripts inherit `PATH` and locale variables, run from a temporary copy of the
skill, honor the configured timeout (overridden by `script_timeout`), and return
`script_execution` metadata containing the executed command, working directory,
exit code, `stdout`, `stderr`, and `duration_seconds`.

## Local development workflow

- Install [uv](https://github.com/astral-sh/uv) and Python 3.12+.
- Sync an isolated environment with all runtime and developer dependencies (only needed when developing locally in the repo):

  ```bash
  uv sync
  ```

- Run the test suite:

  ```bash
  uv run pytest
  ```

- Launch the CLI against your local checkout while iterating:

  ```bash
  uv run python -m skillz /path/to/skills --list-skills
  ```

## Packaging status

- The repository ships a `pyproject.toml`, `src/skillz/` package layout, and `uv.lock` for reproducible builds.
- Console entry point `skillz` resolves to `python -m skillz` when installed as a package.
- GitHub Actions workflows run tests on every push (`.github/workflows/tests.yml`) and publish to PyPI via trusted publisher when a GitHub Release is approved (`.github/workflows/publish.yml`).

## Discovery and tool registration

- Recursively walks the skills root and loads every `SKILL.md` (nesting supported).
- One MCP tool is registered per skill. Tool name = the slug of `name` (e.g., `algorithmic-art`).
- Tool description = the `description` from front‑matter (no extra metadata included).

_Note: Skillz responds with absolute paths for every resource. FastMCP clients can call `ctx.read_resource` to stream the file contents or read them directly from disk when running locally._

## Security & Safety Notice

- This code is **experimental**, **untested**, and should be treated as unsafe.
- Script execution runs outside any hardened sandbox besides a temporary
  directory with a pared-down environment. Use only with trusted skill content
  and within controlled environments.
- Review and harden before exposing to real users or sensitive workflows.

## License

Released under the MIT License (see `LICENSE`).
