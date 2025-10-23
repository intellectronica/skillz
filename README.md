# Skillz MCP Server

---

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

---

`skillz` is a Python package and CLI that exposes [Anthropic‑style skills](https://github.com/anthropics/skills) (directories with a `SKILL.md` that starts with YAML front‑matter) to any MCP client. It recursively discovers skills, registers one tool per skill, returns authored instructions and absolute file paths, and can optionally run a helper script from the skill in a temporary workspace. Now that the package is on PyPI you can run it anywhere with `uvx skillz`.

## Prerequisites

- Python 3.12 or newer (managed automatically when using `uv`)
- `uv` package manager (the script metadata declares runtime dependencies)

## Quick Start

1. Populate a directory with skills following Anthropic’s format
   (`SKILL.md` + optional resources).
2. Run the server with the directory path (downloads and caches the latest PyPI release automatically):

   ```bash
   uvx skillz /path/to/skills --verbose
   ```

   By default the server listens over `stdio`. Pass `--transport http` or
   `--transport sse` with `--host`, `--port`, and `--path` if your client needs a
   network transport.
3. Use `--list-skills` to validate parsing without starting the transport:

   ```bash
   uvx skillz /path/to/skills --list-skills
   ```

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

- The repository now ships a `pyproject.toml`, `src/skillz/` package layout, and `uv.lock` for reproducible builds.
- Console entry point `skillz` resolves to `python -m skillz` when installed as a package.
- GitHub Actions workflow `.github/workflows/publish.yml` builds/tests and, on published GitHub Releases, publishes via PyPI trusted publisher once the `pypi` environment is approved in project settings.

## Discovery and tool registration

- Recursively walks the skills root and loads every `SKILL.md` (nesting supported).
- One MCP tool is registered per skill. Tool name = the slug of `name` (e.g., `algorithmic-art`).
- Tool description = the `description` from front‑matter (no extra metadata included).

_Note: Skillz returns absolute paths but does not register MCP resources for file reads. Clients should read files directly from disk or provide their own file‑access flow._

## Security & Safety Notice

- This code is **experimental**, **untested**, and should be treated as unsafe.
- Script execution happens outside any sandbox besides a temporary directory.
  Use only with trusted skill content and within controlled environments.
- Review and harden before exposing to real users or sensitive workflows.

## License

Released under the MIT License (see `LICENSE`).
