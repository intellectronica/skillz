"""Skillz MCP server exposing local Anthropic-style skills via FastMCP.

Usage examples::

    uv run python -m skillz /path/to/skills --verbose
    uv run python -m skillz tmp/examples --list-skills

Manual smoke tests rely on the sample fixture in ``tmp/examples`` created
by the project checklist. The ``--list-skills`` flag validates discovery
without starting the transport, while additional sanity checks can be run
with a short script that invokes the generated tool functions directly.

Skills provide instructions and resources via MCP. Clients are responsible
for reading resources (including any scripts) and executing them if needed.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Mapping,
    Optional,
    TypedDict,
)
from urllib.parse import quote

import yaml
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ._version import __version__


LOGGER = logging.getLogger("skillz")
FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
SKILL_MARKDOWN = "SKILL.md"
DEFAULT_SKILLS_ROOT = Path("~/.skillz")
SERVER_NAME = "Skillz MCP Server"
SERVER_VERSION = __version__


class SkillError(Exception):
    """Base exception for skill-related failures."""

    def __init__(self, message: str, *, code: str = "skill_error") -> None:
        super().__init__(message)
        self.code = code


class SkillValidationError(SkillError):
    """Raised when a skill fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")




@dataclass(slots=True)
class SkillMetadata:
    """Structured metadata extracted from a skill front matter block."""

    name: str
    description: str
    license: Optional[str] = None
    allowed_tools: tuple[str, ...] = ()
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Skill:
    """Runtime representation of a skill directory."""

    slug: str
    directory: Path
    instructions_path: Path
    metadata: SkillMetadata
    resources: tuple[Path, ...]

    def read_body(self) -> str:
        """Return the Markdown body of the skill."""

        LOGGER.debug("Reading body for skill %s", self.slug)
        text = self.instructions_path.read_text(encoding="utf-8")
        match = FRONT_MATTER_PATTERN.match(text)
        if match:
            return match.group(2).lstrip()
        raise SkillValidationError(
            f"Skill {self.slug} is missing YAML front matter "
            "and cannot be served."
        )


class SkillResourceMetadata(TypedDict):
    """Metadata describing a registered skill resource."""

    relative_path: str
    uri: str


def slugify(value: str) -> str:
    """Convert names into stable slug identifiers."""

    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "skill"


def parse_skill_md(path: Path) -> tuple[SkillMetadata, str]:
    """Parse SKILL.md front matter and body."""

    raw = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(raw)
    if not match:
        raise SkillValidationError(
            f"{path} must begin with YAML front matter delimited by '---'."
        )

    front_matter, body = match.groups()
    try:
        data = yaml.safe_load(front_matter) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise SkillValidationError(
            f"Unable to parse YAML in {path}: {exc}"
        ) from exc

    if not isinstance(data, Mapping):
        raise SkillValidationError(
            f"Front matter in {path} must define a mapping, "
            f"not {type(data).__name__}."
        )

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name:
        raise SkillValidationError(
            f"Front matter in {path} is missing 'name'."
        )
    if not description:
        raise SkillValidationError(
            f"Front matter in {path} is missing 'description'."
        )

    allowed = data.get("allowed-tools") or data.get("allowed_tools") or []
    if isinstance(allowed, str):
        allowed_list = tuple(
            part.strip() for part in allowed.split(",") if part.strip()
        )
    elif isinstance(allowed, Iterable):
        allowed_list = tuple(
            str(item).strip() for item in allowed if str(item).strip()
        )
    else:
        allowed_list = ()

    extra = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "name",
            "description",
            "license",
            "allowed-tools",
            "allowed_tools",
        }
    }

    metadata = SkillMetadata(
        name=name,
        description=description,
        license=(
            str(data["license"]).strip() if data.get("license") else None
        ),
        allowed_tools=allowed_list,
        extra=extra,
    )
    return metadata, body.lstrip()


class SkillRegistry:
    """Discover and manage skills found under a root directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._skills_by_slug: dict[str, Skill] = {}
        self._skills_by_name: dict[str, Skill] = {}

    @property
    def skills(self) -> tuple[Skill, ...]:
        return tuple(self._skills_by_slug.values())

    def load(self) -> None:
        if not self.root.exists() or not self.root.is_dir():
            raise SkillError(
                f"Skills root {self.root} does not exist "
                "or is not a directory."
            )

        LOGGER.info("Discovering skills in %s", self.root)
        self._skills_by_slug.clear()
        self._skills_by_name.clear()

        root = self.root.resolve()
        skill_manifests = sorted(
            (path for path in root.rglob(SKILL_MARKDOWN) if path.is_file()),
            key=lambda path: str(path).lower(),
        )

        for skill_md in skill_manifests:
            child = skill_md.parent

            try:
                metadata, _ = parse_skill_md(skill_md)
            except SkillValidationError as exc:
                LOGGER.warning("Skipping invalid skill at %s: %s", child, exc)
                continue

            slug = slugify(metadata.name)
            if slug in self._skills_by_slug:
                LOGGER.error(
                    "Duplicate skill slug '%s'; skipping %s",
                    slug,
                    child,
                )
                continue

            if metadata.name in self._skills_by_name:
                LOGGER.warning(
                    "Duplicate skill name '%s' found in %s; "
                    "only first occurrence is kept",
                    metadata.name,
                    child,
                )
                continue

            resources = self._collect_resources(child)

            skill = Skill(
                slug=slug,
                directory=child.resolve(),
                instructions_path=skill_md.resolve(),
                metadata=metadata,
                resources=resources,
            )

            if child.name != slug:
                LOGGER.debug(
                    "Skill directory name '%s' does not match slug '%s'",
                    child.name,
                    slug,
                )

            self._skills_by_slug[slug] = skill
            self._skills_by_name[metadata.name] = skill

        LOGGER.info("Loaded %d skills", len(self._skills_by_slug))

    def _collect_resources(self, directory: Path) -> tuple[Path, ...]:
        root = directory.resolve()
        files = [root / SKILL_MARKDOWN]
        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path == root / SKILL_MARKDOWN:
                continue
            files.append(file_path)
        return tuple(files)

    def get(self, slug: str) -> Skill:
        try:
            return self._skills_by_slug[slug]
        except KeyError as exc:  # pragma: no cover - defensive
            raise SkillError(f"Unknown skill '{slug}'") from exc




def _build_resource_uri(skill: Skill, relative_path: Path) -> str:
    encoded_slug = quote(skill.slug, safe="")
    encoded_parts = [quote(part, safe="") for part in relative_path.parts]
    path_suffix = "/".join(encoded_parts)
    if path_suffix:
        return f"resource://skillz/{encoded_slug}/{path_suffix}"
    return f"resource://skillz/{encoded_slug}"




def register_skill_resources(
    mcp: FastMCP, skill: Skill
) -> tuple[SkillResourceMetadata, ...]:
    """Register FastMCP resources for each file in a skill."""

    metadata: list[SkillResourceMetadata] = []
    for resource_path in skill.resources:
        try:
            relative_path = resource_path.relative_to(skill.directory)
        except ValueError:  # pragma: no cover - defensive safeguard
            relative_path = Path(resource_path.name)

        relative_display = relative_path.as_posix()
        uri = _build_resource_uri(skill, relative_path)

        def _make_resource_reader(path: Path) -> Callable[[], str | bytes]:
            def _read_resource() -> str | bytes:
                try:
                    data = path.read_bytes()
                except OSError as exc:  # pragma: no cover
                    raise SkillError(
                        f"Failed to read resource '{path}': {exc}"
                    ) from exc

                try:
                    return data.decode("utf-8")
                except UnicodeDecodeError:
                    return data

            return _read_resource

        mcp.resource(uri, name=f"{skill.slug}:{relative_display}")(
            _make_resource_reader(resource_path)
        )

        metadata.append(
            {
                "relative_path": relative_display,
                "uri": uri,
            }
        )

    return tuple(metadata)


def _format_tool_description(skill: Skill) -> str:
    """Return the concise skill description for discovery responses."""

    description = skill.metadata.description.strip()
    if not description:  # pragma: no cover - defensive safeguard
        raise SkillValidationError(
            f"Skill {skill.slug} is missing a description after validation."
        )
    return description


def register_skill_tool(
    mcp: FastMCP,
    skill: Skill,
    *,
    resources: tuple[SkillResourceMetadata, ...],
) -> Callable[..., Awaitable[Mapping[str, Any]]]:
    """Register a tool that returns skill instructions and resource URIs.

    Clients are expected to read the instructions, then use
    ctx.read_resource(uri) to access any resources they need
    (including scripts, which they can then execute themselves if desired).
    """
    tool_name = skill.slug
    description = _format_tool_description(skill)
    bound_skill = skill
    bound_resources = resources

    @mcp.tool(name=tool_name, description=description)
    async def _skill_tool(  # type: ignore[unused-ignore]
        task: str,
        ctx: Optional[Context] = None,
    ) -> Mapping[str, Any]:
        LOGGER.info(
            "Skill %s tool invoked task=%s",
            bound_skill.slug,
            task,
        )

        try:
            if not task.strip():
                raise SkillError(
                    "The 'task' parameter must be a non-empty string."
                )

            instructions = bound_skill.read_body()
            resource_entries = [
                {
                    "relative_path": entry["relative_path"],
                    "uri": entry["uri"],
                }
                for entry in bound_resources
            ]

            response: dict[str, Any] = {
                "skill": bound_skill.slug,
                "task": task,
                "metadata": {
                    "name": bound_skill.metadata.name,
                    "description": bound_skill.metadata.description,
                    "license": bound_skill.metadata.license,
                    "allowed_tools": list(bound_skill.metadata.allowed_tools),
                    "extra": bound_skill.metadata.extra,
                },
                "resources": resource_entries,
                "instructions": instructions,
                "usage": textwrap.dedent(
                    """\
                    Apply the skill instructions to complete the task.

                    All skill resources are available via MCP resources.
                    Use ctx.read_resource(uri) with any URI from the
                    'resources' list to access files, scripts, or other
                    supporting materials.

                    The skill may include executable scripts. If you need
                    to run a script, read it via ctx.read_resource(uri)
                    and execute it yourself using appropriate tooling.
                    """
                ).strip(),
            }

            return response
        except SkillError as exc:
            LOGGER.error(
                "Skill %s invocation failed: %s",
                bound_skill.slug,
                exc,
                exc_info=True,
            )
            raise ToolError(str(exc)) from exc

    return _skill_tool


def configure_logging(verbose: bool, log_to_file: bool) -> None:
    """Set up console logging and optional file logging."""

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    if log_to_file:
        log_path = Path("/tmp/skillz.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                log_path, mode="w", encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - filesystem failure is rare
            print(
                f"Failed to configure log file {log_path}: {exc}",
                file=sys.stderr,
            )
        else:
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG if (log_to_file or verbose) else logging.INFO,
        handlers=handlers,
        force=True,
    )


def build_server(registry: SkillRegistry) -> FastMCP:
    summary = ", ".join(
        skill.metadata.name for skill in registry.skills
    ) or "No skills"
    mcp = FastMCP(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=f"Loaded skills: {summary}",
    )
    for skill in registry.skills:
        resource_metadata = register_skill_resources(mcp, skill)
        register_skill_tool(
            mcp,
            skill,
            resources=resource_metadata,
        )
    return mcp


def list_skills(registry: SkillRegistry) -> None:
    if not registry.skills:
        print("No valid skills discovered.")
        return
    for skill in registry.skills:
        print(
            f"- {skill.metadata.name} (slug: {skill.slug}) -> ",
            skill.directory,
            sep="",
        )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Skillz MCP server.")
    parser.add_argument(
        "skills_root",
        type=Path,
        nargs="?",
        help=(
            "Directory containing skill folders "
            f"(default: {DEFAULT_SKILLS_ROOT})"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "sse"),
        default="stdio",
        help="Transport to use when running the server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP/SSE transports",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP/SSE transports",
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="Path for HTTP transport",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Write very verbose logs to /tmp/skillz.log",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List parsed skills and exit without starting the server",
    )
    args = parser.parse_args(argv)
    skills_root = args.skills_root or DEFAULT_SKILLS_ROOT
    if not isinstance(skills_root, Path):
        skills_root = Path(skills_root)
    args.skills_root = skills_root.expanduser()
    return args


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose, args.log)

    if args.log:
        LOGGER.info("Verbose file logging enabled at /tmp/skillz.log")

    registry = SkillRegistry(args.skills_root)
    registry.load()

    if args.list_skills:
        list_skills(registry)
        return

    server = build_server(registry)
    run_kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in {"http", "sse"}:
        run_kwargs.update({"host": args.host, "port": args.port})
        if args.transport == "http":
            run_kwargs["path"] = args.path

    server.run(**run_kwargs)


if __name__ == "__main__":
    main()
