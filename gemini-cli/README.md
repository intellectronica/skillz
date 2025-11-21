# Gemini CLI Skills Extension

Run Anthropic-style Agent Skills in Gemini CLI using the [skillz MCP server](https://github.com/intellectronica/skillz).

## Installation

```bash
gemini extensions install https://github.com/intellectronica/skillz/gemini-cli
```

During installation, you'll be prompted to specify a skills directory. Press Enter to use the default (`~/.skillz`) or provide a custom path.

## Setup

1. **Create skills directory** (if using default):
   ```bash
   mkdir -p ~/.skillz
   ```

2. **Add skills** to the directory. Each skill is a folder with a SKILL.md file.

3. **Restart Gemini CLI** to load the skills.

## Example: Installing Anthropic Skills

```bash
cd ~/.skillz

# Clone specific skills from Anthropic's repository
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/anthropics/skills.git temp
cd temp
git sparse-checkout set document-skills/pdf
mv document-skills/pdf ../
cd ..
rm -rf temp
```

## Using Skills

Skills are invoked automatically based on your task. Example:

```
> Extract form fields from this PDF
[Gemini invokes the pdf skill automatically]
```

## Configuration

The extension defaults to `~/.skillz` for skills location.

### Changing Skills Directory

Edit `~/.gemini/extensions/skillz/.env`:
```bash
SKILLS_PATH=/path/to/your/skills
```

Then restart Gemini CLI.

## Requirements

- **uvx** — Installed automatically with uv package manager
- **Gemini CLI** — Latest version recommended

## Troubleshooting

**Skills not loading**:
- Check your skills directory exists (default: `~/.skillz`)
- Verify SKILL.md files have valid YAML frontmatter
- Run `/mcp list` to see if skillz server connected

**Skills not recognized**:
- Restart Gemini CLI after adding skills
- Check skillz server logs with Gemini CLI debug mode

**uvx command not found**:
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Change skills directory after installation**:
- Edit `~/.gemini/extensions/skillz/.env`
- Set `SKILLS_PATH=/your/path`
- Restart Gemini CLI

## About

This extension packages the [skillz MCP server](https://github.com/intellectronica/skillz) for Gemini CLI, enabling the same Agent Skills format used in Claude.ai and Claude Code.

Skills are loaded from PyPI via `uvx skillz@latest`, ensuring you always have the latest version.

## License

Same as skillz — see repository LICENSE file.
