# Skillz: Bring Anthropic‑style Skills to Any MCP Client

Skillz is a tiny, pragmatic MCP server that lets you run Anthropic‑style “skills” from any Model Context Protocol (MCP) client — not just Claude. Point Skillz at a directory of skills and it exposes each skill as a first‑class tool the client can discover and call.

This is a simple proof‑of‑concept. Use with caution, review the skills you load, and prefer running it in a sandboxed environment.

## What it does

- Recursively discovers skills by finding `SKILL.md` files anywhere under a root folder.
- Registers one MCP tool per skill using the skill’s slug (e.g., `algorithmic-art`).
- Surfaces a clean, concise tool description from the skill front‑matter description.
- When a tool is called, returns structured instructions (the body of `SKILL.md`) plus absolute paths to all resources for the skill so clients can read supporting files without guesswork.
- Optionally executes a script from the skill (e.g., `scripts/run.py`) if you pass `script` and `script_payload`; execution runs in a temporary workspace and returns stdout/stderr/exit code.

## Why it’s useful

Claude “Skills” are a great way to package a workflow and its supporting assets. Skillz lets other MCP‑capable clients load and use those same skills without depending on model‑side sampling: the server returns explicit instructions the client can hand to its assistant, along with file paths and an optional script runner.

## Quick start

- Run the server:

```bash
uv run skillz.py /path/to/skills --verbose
```

- Point your MCP client at the server (stdio/HTTP/SSE). The server identifies as “Skillz MCP Server” and registers one tool per skill.

- Call a skill tool with a task to get instructions you can forward to your assistant:

```json
{
  "tool": "algorithmic-art",
  "arguments": {
    "task": "Create a simple generative background image for the homepage"
  }
}
```

The response includes:
- `instructions`: the authored guidance from `SKILL.md` (what your assistant should follow).
- `resources`: absolute paths to every skill asset (including `SKILL.md` and any files under the skill directory).
- `usage`: convenience fields like a suggested prompt and guidance.

- If a skill ships a helper script, you can ask Skillz to run it for you:

```json
{
  "tool": "algorithmic-art",
  "arguments": {
    "task": "Generate a 1920x1080 background",
    "script": "scripts/generate.py",
    "script_payload": {
      "args": ["--width", "1920", "--height", "1080"]
    }
  }
}
```

Execution occurs in a temporary copy of the skill directory. The result returns `returncode`, `stdout`, `stderr`, and the effective `cwd`.

## Authoring skills

A skill is a folder with a `SKILL.md` that starts with YAML front‑matter:

```markdown
---
name: Algorithmic Art
description: Create simple generative backgrounds using prompts and scripts.
---
# Instructions
Write clear, step‑by‑step guidance the assistant should follow.
```

You can add any supporting files next to `SKILL.md` (scripts, templates, datasets). Skillz will expose their absolute paths to clients.

## Safety and limitations

- Proof‑of‑concept: APIs and output formats may change.
- Scripts can be dangerous: treat skills as code, review before running, and isolate execution.
- No guarantees: use at your own risk.

## Links

- Repo: https://github.com/intellectronica/skillz
- MCP: https://modelcontextprotocol.io/

If you try Skillz, feedback and issues are very welcome.
