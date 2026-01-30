# Skillz Standards Compliance Report

_Date:_ 2026-01-30

## Scope

This report evaluates Skillz against publicly documented skill standards and
reference implementations. It focuses on compatibility with Agent Skills
conventions, OpenCode, and Codex.

### Sources Reviewed

- Agent Skills documentation on https://agentskills.io/ **(not accessible in
  this sandbox; see note below)**
- OpenCode “Agent Skills” documentation:
  https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/skills.mdx
- Codex sample skill (OpenAI Codex):
  https://github.com/openai/codex/blob/main/codex-rs/core/src/skills/assets/samples/skill-creator/SKILL.md

> **Note:** The `agentskills.io` site was not reachable from this environment
> (HTTP fetch failed). The remaining sections reflect OpenCode and Codex
> standards. Once access to Agent Skills documentation is restored, review any
> additional requirements and compare to the gaps listed below.

---

## Current Skillz Behavior (Summary)

Skillz is an MCP server that:

- Discovers skills rooted at a user-specified directory (default `~/.skillz`).
- Accepts **`SKILL.md`** with YAML front matter that must contain `name` and
  `description`. Optional fields include `license`, `allowed-tools` /
  `allowed_tools`, plus arbitrary extra fields captured in metadata.
- Generates a unique slug from the skill name (slugify).
- Exposes **one MCP tool per skill**. Each tool returns instructions and
  resource URIs.
- Supports nested directories and packaged `.zip` / `.skill` archives.
- Exposes each file in a skill as an MCP resource:
  `resource://skillz/{skill-slug}/{path}`.

---

## OpenCode / Codex Compatibility Findings

### 1) Skill Discovery Paths

**OpenCode** scans these locations (project + global):
`.opencode/skills/<name>/SKILL.md`, `~/.config/opencode/skills/<name>/SKILL.md`,
`.claude/skills/<name>/SKILL.md`, `~/.claude/skills/<name>/SKILL.md`.

**Codex** uses skills alongside its own conventions (no explicit path list in
the sample, but expects flat `<skill-name>/SKILL.md` directories).

**Skillz today:** Uses a single root directory (`~/.skillz` or CLI argument)
and recursively discovers nested directories. This is **more flexible** but
not aligned with OpenCode/Codex default paths.

**Compliance gap:** No built-in support for OpenCode/Codex default locations,
and no “flat-only” mode.

### 2) Front Matter Fields

**OpenCode expects only**:

- `name` (required)
- `description` (required)
- `license` (optional)
- `compatibility` (optional)
- `metadata` (optional string-to-string map)

**Codex sample**: uses `name`, `description`, and `metadata`.

**Skillz today:** accepts `name`, `description`, `license`, and `allowed-tools`
plus arbitrary extra fields. Extra fields are surfaced as `metadata.extra`.

**Compliance gap:** Skillz accepts non-standard front matter fields and does
not explicitly support `compatibility` or a dedicated `metadata` map in the
tool response. This can confuse strict parsers or tooling that expects
OpenCode/Codex front matter.

### 3) Naming Rules / Validation

**OpenCode requirements**:

- `name` must be 1–64 chars.
- Hyphen-separated lowercase alphanumeric (regex:
  `^[a-z0-9]+(-[a-z0-9]+)*$`).
- Directory name must match `name`.

**Skillz today:** Validates only that `name` and `description` are non-empty,
and slugifies names when generating tool identifiers. Directory names are not
validated.

**Compliance gap:** Skillz does not enforce naming constraints or ensure the
folder name matches `name`.

### 4) Description Length Rules

**OpenCode** limits description to 1–1024 characters.

**Skillz today:** Only enforces non-empty description.

**Compliance gap:** Missing length validation.

### 5) Skill Tool Model

**OpenCode** uses a **single** `skill` tool which returns available skills and
loads skill content by name.

**Skillz today:** Registers **one tool per skill**, each returning instructions.

**Compliance gap:** Tooling shape differs. Clients expecting OpenCode behavior
will not find a generic `skill` tool.

### 6) Permissions / Access Controls

**OpenCode** supports `opencode.json` permission rules to allow/deny/ask for
skills by name pattern.

**Skillz today:** No permission model.

**Compliance gap:** Missing allow/deny/ask policy layer for skills.

### 7) Packaging and Zip Support

**OpenCode/Codex** describe uncompressed skill directories; packaging is a
separate workflow for Codex (creating `.skill` zip files).

**Skillz today:** Supports `.zip` and `.skill` archives directly.

**Compatibility note:** Archive support is a superset. However, strict tools
may expect unzipped directory structure.

---

## Recommendations to Improve Standards Compliance

### A. Add Optional “Standards-Compatible Mode”

Provide a CLI flag (or config) to enable **OpenCode/Codex compatibility**:

1. **Default discovery paths** (in priority order):
   - `.opencode/skills`, `~/.config/opencode/skills`
   - `.claude/skills`, `~/.claude/skills`
2. **Flat-only discovery**:
   - Only accept immediate subdirectories containing `SKILL.md`.
3. **Name validation**:
   - Enforce OpenCode regex, 1–64 char length.
   - Require directory name == `name`.
4. **Description length validation**:
   - Enforce 1–1024 chars.

### B. Standardize Front Matter Handling

1. **Recognize `compatibility`** field and expose it in metadata.
2. **Respect `metadata` map** (string-to-string map) and avoid mixing in
   non-standard fields.
3. **Ignore unknown fields** by default to avoid breaking stricter consumers,
   but allow an opt-in `--strict` mode to error on unknown fields.

### C. Provide a Single `skill` Tool (Optional)

For OpenCode/Codex clients, add a compatibility mode that:

- Registers a single MCP tool named `skill`.
- Returns `<available_skills>` in the tool description (OpenCode convention).
- Accepts `{ name: string }` and returns skill instructions and resources.

Retain existing per-skill tools in non-compatibility mode so current Skillz
users are not impacted.

### D. Introduce Skill Permission Rules

Add a JSON or YAML config with allow/deny/ask semantics (pattern matching as in
OpenCode). Apply permissions in both list-skills and tool invocation paths.

### E. Map Metadata to OpenCode/Codex-Friendly Shapes

Use a predictable response format:

```json
{
  "name": "skill-name",
  "description": "…",
  "license": "MIT",
  "compatibility": "opencode",
  "metadata": { "audience": "maintainers" },
  "resources": [ ... ],
  "instructions": "…"
}
```

This aligns with the documented expectations of OpenCode and Codex.

---

## Suggested Implementation Order

1. **Discovery & validation** (paths, flat mode, name/description constraints).
2. **Front matter normalization** (`compatibility`, `metadata` fields).
3. **Compatibility `skill` tool** (optional, behind a flag).
4. **Permission rules** with allow/deny/ask.
5. **Documentation updates** (README + examples).

---

## Open Questions / Follow-ups

- **Agent Skills standard (agentskills.io):** Confirm the official schema once
  the site is accessible and verify required fields or directory structure.
- **Codex compatibility:** Determine whether Codex expects the single-tool model
  or accepts per-skill tools when used via MCP.

---

## Appendix: Notes on Current Skillz Strengths

- Supports `.skill` and `.zip` packages natively.
- Exposes resources via MCP with typed MIME detection.
- Provides rich server instructions for agents.

These are valuable features; consider keeping them even when introducing
strict-compatibility modes.
