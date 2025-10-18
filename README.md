# Skillz MCP Server

Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.

`skillz.py` is a single‑file MCP server that exposes Anthropic‑style skills (directories with a `SKILL.md` that starts with YAML front‑matter) to any MCP client. It recursively discovers skills, registers one tool per skill, returns authored instructions and absolute file paths, and can optionally run a helper script from the skill in a temporary workspace.

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

## Discovery and tool registration

- Recursively walks the skills root and loads every `SKILL.md` (nesting supported).
- One MCP tool is registered per skill. Tool name = the slug of `name` (e.g., `algorithmic-art`).
- Tool description = the `description` from front‑matter (no extra metadata included).

## Tool API (instruction‑first)

Call a skill tool with a `task`. Skillz returns authored instructions and absolute paths to all assets so your client can drive its own model call (no model‑side sampling required). Optionally ask Skillz to run a helper script.

Arguments
- `task` (string, required)
- `script` (string, optional): relative path to a helper script inside the skill
- `script_payload` (object, optional):
  - `args` (list[str])
  - `env` (object[str->str])
  - `files` (list[{path, content, encoding}])
  - `stdin` (string or {content, encoding})
  - `workdir` (string)
- `script_timeout` (float, optional)

Response (selected fields)
- `instructions` (string): Markdown body of `SKILL.md`
- `resources` (list[string]): absolute paths to every file in the skill (including `SKILL.md`)
- `usage` (object): suggested prompt + guidance
- `script_execution` (object when a script ran): `{command, cwd, returncode, stdout, stderr, duration_seconds}`; `stdout`/`stderr` are `{encoding, content}`

Note: Skillz returns absolute paths but does not register MCP resources for file reads. Clients should read files directly from disk or provide their own file‑access flow.

## Security & Safety Notice

- This code is **experimental**, **untested**, and should be treated as unsafe.
- Script execution happens outside any sandbox besides a temporary directory.
  Use only with trusted skill content and within controlled environments.
- Review and harden before exposing to real users or sensitive workflows.

## License

Released under the MIT License (see `LICENSE`).
