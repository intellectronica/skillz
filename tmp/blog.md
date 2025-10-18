# Skillz: Anthropic‑style Skills for Any MCP Client

Warning: Experimental proof‑of‑concept. Potentially unsafe. Treat skills like untrusted code. Review them, sandbox execution, and use at your own risk.

Skillz is a tiny MCP server that exposes Anthropic‑style skills (folders with `SKILL.md`) as tools for any MCP client, not just Claude. It returns the skill’s instructions and absolute paths to its files, and can optionally run a script bundled with the skill.

What it does
- Recursively finds every `SKILL.md` under a root directory and registers one tool per skill (tool name = skill slug, e.g., `algorithmic-art`).
- Tool description comes from the skill’s front‑matter `description`.
- Calling a tool with a `task` returns: `instructions` (from `SKILL.md`) and `resources` (absolute file paths). Optionally run a helper script via `script` + `script_payload`.

Quick start
- Run: `uv run skillz.py /path/to/skills --verbose`
- Point your MCP client at the server (stdio/HTTP/SSE). Call a skill:

```json
{"tool":"algorithmic-art","arguments":{"task":"Generate a simple 1920x1080 background"}}
```

To execute a script packaged with the skill:

```json
{"tool":"algorithmic-art","arguments":{"task":"generate","script":"scripts/generate.py","script_payload":{"args":["--width","1920","--height","1080"]}}}
```

Safety
- Experimental PoC; APIs and outputs may change.
- Scripts may run arbitrary code. Isolate with containers/VMs; do not run untrusted skills on sensitive machines.

Repo: https://github.com/intellectronica/skillz
