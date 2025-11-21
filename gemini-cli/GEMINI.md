# Agent Skills for Gemini CLI

This extension enables Anthropic-style Agent Skills in Gemini CLI via the skillz MCP server.

## How It Works

Skills are directories containing SKILL.md files with YAML frontmatter. The skillz MCP server:
- Discovers all SKILL.md files in your skills directory
- Registers each skill as an MCP tool
- Returns skill instructions and absolute paths when invoked
- Enables progressive disclosure (load only what's needed)

## Using Skills

Skills are invoked automatically when relevant to your task. You don't need to explicitly call them.

When a skill is invoked:
1. You receive the full SKILL.md content
2. Absolute paths to the skill's base directory are provided
3. Follow the instructions in the skill
4. Load additional resource files only when referenced

## Skills Directory

Skills are loaded from the directory configured during extension installation (default: `~/.skillz`).

To change the directory, edit `~/.gemini/extensions/skillz/.env` and set `SKILLS_PATH=/your/path`.

## Skill Format

Each skill is a directory containing:
- **SKILL.md** — Entry point with YAML frontmatter and markdown instructions
- **resources/** — Optional supporting files
- **scripts/** — Optional executable code

Example SKILL.md:
```markdown
---
name: my-skill
description: What this skill does
---

# Skill Instructions

When invoked, do X, Y, Z...
```

## Finding Skills

- Anthropic skills repository: https://github.com/anthropics/skills
- Community skills: Search GitHub for "claude skills" or "SKILL.md"

## MCP Commands

- `/mcp list` — See all available skills
- `/mcp` — View MCP server status

## More Information

- skillz MCP server: https://github.com/intellectronica/skillz
- Anthropic Skills docs: https://docs.claude.com/en/docs/agents-and-tools/agent-skills
