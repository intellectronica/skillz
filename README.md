# Skillz MCP Server

---

> ⚠️ **Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code and run in sandboxes/containers. Use at your own risk.**

---

`skillz` is a Python package and CLI that exposes [Anthropic‑style skills](https://github.com/anthropics/skills) (directories with a `SKILL.md` that starts with YAML front‑matter) to any MCP client using [FastMCP](https://pypi.org/project/fastmcp/). It recursively discovers skills, registers one tool per skill, returns the authored instructions and resource paths, and can optionally run helper scripts inside a temporary workspace. The package is published on PyPI, so you can launch it anywhere with `uvx skillz`.

## Features

- Recursively discovers every `SKILL.md` beneath the provided skills root (default: `~/.skillz`) and creates one MCP tool per skill slug (derived from the skill `name`).
- Tool calls return the skill instructions, metadata, and resource metadata (absolute paths, relative paths, deterministic `resource://skillz/...` URIs, and a `runnable` flag) so clients can fetch supporting files directly or via `ctx.read_resource` and easily spot helper scripts.
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

## Installation

### Quick Install

Click one of the buttons below to install the MCP server in your preferred IDE:

[![Install in VS Code](https://img.shields.io/badge/Use_Skillz_in-VS_Code-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/Use_Skillz_in-VS_Code_Insiders-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D&quality=insiders)
[![Install in Visual Studio](https://img.shields.io/badge/Use_Skillz_in-Visual_Studio-C16FDE?style=flat-square&logo=visualstudio&logoColor=white)](https://vs-open.link/mcp-install?%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D)
[![Install in Cursor](https://img.shields.io/badge/Use_Skillz_in-Cursor-000000?style=flat-square&logoColor=white)](https://cursor.com/en/install-mcp?name=Skillz&config=eyJuYW1lIjoiU2tpbGx6IiwiY29tbWFuZCI6InV2eCIsImFyZ3MiOlsic2tpbGx6Il0sImVudiI6e319)
[![Install in Goose](https://block.github.io/goose/img/extension-install-dark.svg)](https://block.github.io/goose/extension?cmd=uvx&arg=skillz&id=Skillz&name=Skillz&description=MCP%20Server%20for%20Skillz)
[![Add MCP Server Skillz to LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=Skillz&config=eyJuYW1lIjoiU2tpbGx6IiwiY29tbWFuZCI6InV2eCIsImFyZ3MiOlsic2tpbGx6Il0sImVudiI6e319)

### Manual Installation

**Standard config** works in most tools:

```js
{
  "servers": {
    "Skillz": {
      "command": "uvx",
      "args": [
        "skillz"
      ],
      "env": {}
    }
  }
}
```

<details>
<summary>VS Code</summary>

#### Click the button to install:

[![Install in VS Code](https://img.shields.io/badge/Use_Skillz_in-VS_Code-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D)

#### Or install manually:

Follow the MCP install [guide](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server), use the standard config above. You can also install the Skillz MCP server using the VS Code CLI:

```bash
code --add-mcp '{\"name\":\"Skillz\",\"command\":\"uvx\",\"args\":[\"skillz\"],\"env\":{}}'
```

After installation, the Skillz MCP server will be available for use with your GitHub Copilot agent in VS Code.
</details>

<details>
<summary>VS Code Insiders</summary>

#### Click the button to install:

[![Install in VS Code Insiders](https://img.shields.io/badge/Use_Skillz_in-VS_Code_Insiders-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Skillz&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D&quality=insiders)

#### Or install manually:

Follow the MCP install [guide](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server), use the standard config above. You can also install the Skillz MCP server using the VS Code Insiders CLI:

```bash
code-insiders --add-mcp '{\"name\":\"Skillz\",\"command\":\"uvx\",\"args\":[\"skillz\"],\"env\":{}}'
```

After installation, the Skillz MCP server will be available for use with your GitHub Copilot agent in VS Code Insiders.
</details>

<details>
<summary>Visual Studio</summary>

#### Click the button to install:

[![Install in Visual Studio](https://img.shields.io/badge/Use_Skillz_in-Visual_Studio-C16FDE?style=flat-square&logo=visualstudio&logoColor=white)](https://vs-open.link/mcp-install?%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22skillz%22%5D%2C%22env%22%3A%7B%7D%7D)

#### Or install manually:

1. Open Visual Studio
2. Navigate to the GitHub Copilot Chat window
3. Click the tools icon (🛠️) in the chat toolbar
4. Click the + "Add Server" button to open the "Configure MCP server" dialog
5. Fill in the configuration:
   - **Server ID**: `Skillz`
   - **Type**: Select `stdio` from the dropdown
   - **Command**: `uvx`
   - **Arguments**: `skillz`
6. Click "Save" to add the server

For detailed instructions, see the [Visual Studio MCP documentation](https://learn.microsoft.com/visualstudio/ide/mcp-servers).
</details>

<details>
<summary>Cursor</summary>

#### Click the button to install:

[![Install in Cursor](https://img.shields.io/badge/Use_Skillz_in-Cursor-000000?style=flat-square&logoColor=white)](https://cursor.com/en/install-mcp?name=Skillz&config=eyJuYW1lIjoiU2tpbGx6IiwiY29tbWFuZCI6InV2eCIsImFyZ3MiOlsic2tpbGx6Il0sImVudiI6e319)

#### Or install manually:

Go to `Cursor Settings` -> `MCP` -> `Add new MCP Server`. Name to your liking, use `command` type with the command from the standard config above. You can also verify config or add command like arguments via clicking `Edit`.
</details>

<details>
<summary>Goose</summary>

#### Click the button to install:

[![Install in Goose](https://block.github.io/goose/img/extension-install-dark.svg)](https://block.github.io/goose/extension?cmd=uvx&arg=skillz&id=Skillz&name=Skillz&description=MCP%20Server%20for%20Skillz)

#### Or install manually:

Go to `Advanced settings` -> `Extensions` -> `Add custom extension`. Name to your liking, use type `STDIO`, and set the `command` from the standard config above. Click "Add Extension".
</details>

<details>
<summary>LM Studio</summary>

#### Click the button to install:

[![Add MCP Server Skillz to LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=Skillz&config=eyJuYW1lIjoiU2tpbGx6IiwiY29tbWFuZCI6InV2eCIsImFyZ3MiOlsic2tpbGx6Il0sImVudiI6e319)

#### Or install manually:

Go to `Program` in the right sidebar -> `Install` -> `Edit mcp.json`. Use the standard config above.
</details>

<details>
<summary>Amp</summary>

Add via the Amp VS Code extension settings screen or by updating your settings.json file:

```json
"amp.mcpServers": 
  "Skillz": {
    "command": "uvx",
    "args": [
      "skillz"
    ],
    "env": {}
  }

```

**Amp CLI Setup:**

Add via the `amp mcp add` command below:

```bash
amp mcp add Skillz -- uvx skillz
```
</details>

<details>
<summary>Codex</summary>

Create or edit the configuration file `~/.codex/config.toml` and add:

```toml
[mcp_servers.Skillz]
command = "uvx"
args = ["skillz"]
```

For more information, see the [Codex MCP documentation](https://github.com/openai/codex/blob/main/codex-rs/config.md#mcp_servers).
</details>

<details>
<summary>Gemini CLI</summary>

Follow the MCP install [guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md#configure-the-mcp-server-in-settingsjson), use the standard config above.
</details>

<details>
<summary>OpenCode</summary>

Follow the MCP Servers [documentation](https://opencode.ai/docs/mcp-servers/). For example in `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "Skillz": {
      "type": "local",
      "command": [
        "uvx",
        "skillz"
      ],
      "enabled": true
    }
  }
}
```
</details>

<details>
<summary>Warp</summary>

Go to `Settings` -> `AI` -> `Manage MCP Servers` -> `+ Add` to [add an MCP Server](https://docs.warp.dev/knowledge-and-collaboration/mcp#adding-an-mcp-server). Use the standard config above.

Alternatively, use the slash command `/add-mcp` in the Warp prompt and paste the standard config from above.
</details>

<details>
<summary>Windsurf</summary>

Follow Windsurf MCP [documentation](https://docs.windsurf.com/windsurf/cascade/mcp). Use the standard config above.
</details>

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
- `resources`: metadata entries describing every file shipped with the skill. Each entry includes the absolute `path`, a `relative_path` within the skill directory, a deterministic `resource://skillz/{slug}/…` `uri` that can be fetched via `ctx.read_resource`, and a boolean `runnable` hint that marks which assets can be executed.
- `instructions`: the Markdown body from `SKILL.md`.
- `usage`: a convenience block containing a suggested MCP prompt, integration guidance, and script execution instructions. The `script_execution.available_scripts` list calls out runnable helpers (relative paths, absolute paths, and URIs) while `script_execution.available_resources` continues to return all URIs followed by absolute paths for backwards compatibility.

Script invocations reject non-runnable files with a helpful error that points back to the corresponding `ctx.read_resource` URI so agents learn to read those resources instead of treating them like executables.

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

_Note: Skillz responds with deterministic `resource://skillz/...` URIs and absolute paths for every resource. FastMCP clients can call `ctx.read_resource` with the URI to stream the file contents or read them directly from disk when running locally._

## Security & Safety Notice

- This code is **experimental**, **untested**, and should be treated as unsafe.
- Script execution runs outside any hardened sandbox besides a temporary
  directory with a pared-down environment. Use only with trusted skill content
  and within controlled environments.
- Review and harden before exposing to real users or sensitive workflows.

## License

Released under the MIT License (see `LICENSE`).
