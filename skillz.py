# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastmcp>=2.2.5",
#     "pyyaml>=6.0",
# ]
# ///
"""Skillz MCP server exposing local Anthropic-style skills via FastMCP.

Usage examples::

    uv run skillz.py /path/to/skills --verbose
    uv run skillz.py tmp/examples --list-skills

Manual smoke tests rely on the sample fixture in ``tmp/examples`` created by the
project checklist. The ``--list-skills`` flag validates discovery without
starting the transport, while additional sanity checks can be run with a short
script that invokes the generated tool functions directly.

Security note: referenced scripts execute from copies of the skill directory in
fresh temporary folders with a restricted environment (only ``PATH``/locale
variables plus any explicit overrides), which helps contain side effects.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import logging
import mimetypes
import os
import re
import shlex
import shutil
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Literal,
    Mapping,
    MutableMapping,
    Optional,
)

import yaml
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError


LOGGER = logging.getLogger("skillz")
FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
SKILL_MARKDOWN = "SKILL.md"
DEFAULT_TIMEOUT = 60.0
SERVER_NAME = "Skillz MCP Server"
SERVER_VERSION = "0.1.0"


class SkillError(Exception):
    """Base exception for skill-related failures."""

    def __init__(self, message: str, *, code: str = "skill_error") -> None:
        super().__init__(message)
        self.code = code


class SkillValidationError(SkillError):
    """Raised when a skill fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")


class SkillExecutionError(SkillError):
    """Raised when a skill tool execution fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="execution_error")


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
            f"Skill {self.slug} is missing YAML front matter and cannot be served."
        )


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
        raise SkillValidationError(f"Unable to parse YAML in {path}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise SkillValidationError(
            f"Front matter in {path} must define a mapping, not {type(data).__name__}."
        )

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name:
        raise SkillValidationError(f"Front matter in {path} is missing 'name'.")
    if not description:
        raise SkillValidationError(f"Front matter in {path} is missing 'description'.")

    allowed = data.get("allowed-tools") or data.get("allowed_tools") or []
    if isinstance(allowed, str):
        allowed_list = tuple(
            part.strip() for part in allowed.split(",") if part.strip()
        )
    elif isinstance(allowed, Iterable):
        allowed_list = tuple(str(item).strip() for item in allowed if str(item).strip())
    else:
        allowed_list = ()

    extra = {
        key: value
        for key, value in data.items()
        if key
        not in {"name", "description", "license", "allowed-tools", "allowed_tools"}
    }

    metadata = SkillMetadata(
        name=name,
        description=description,
        license=(str(data["license"]).strip() if data.get("license") else None),
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
                f"Skills root {self.root} does not exist or is not a directory."
            )

        LOGGER.info("Discovering skills in %s", self.root)
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / SKILL_MARKDOWN
            if not skill_md.is_file():
                continue

            try:
                metadata, _ = parse_skill_md(skill_md)
            except SkillValidationError as exc:
                LOGGER.warning("Skipping invalid skill at %s: %s", child, exc)
                continue

            slug = slugify(metadata.name)
            if slug in self._skills_by_slug:
                LOGGER.error("Duplicate skill slug '%s'; skipping %s", slug, child)
                continue

            if metadata.name in self._skills_by_name:
                LOGGER.warning(
                    "Duplicate skill name '%s' found in %s; only first occurrence is kept",
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
        files = [Path(SKILL_MARKDOWN)]
        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(directory)
            if rel.name == SKILL_MARKDOWN and rel == Path(SKILL_MARKDOWN):
                continue
            files.append(rel)
        return tuple(files)

    def get(self, slug: str) -> Skill:
        try:
            return self._skills_by_slug[slug]
        except KeyError as exc:  # pragma: no cover - defensive
            raise SkillError(f"Unknown skill '{slug}'") from exc


def resolve_within(base: Path, relative: str) -> Path:
    """Resolve a relative path within base, preventing path traversal."""

    base_resolved = base.resolve()
    candidate = (base_resolved / relative).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise SkillError(f"Path '{relative}' escapes skill directory {base}.") from exc
    return candidate


def decode_payload_content(content: str, encoding: str) -> bytes:
    if encoding == "text":
        return content.encode("utf-8")
    if encoding == "base64":
        return base64.b64decode(content)
    raise SkillError(f"Unsupported encoding '{encoding}'.")


def encode_output(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"encoding": "base64", "content": base64.b64encode(data).decode("ascii")}
    return {"encoding": "text", "content": text}


def resolve_command(script_path: Path) -> list[str]:
    with script_path.open("r", encoding="utf-8", errors="ignore") as handle:
        first_line = handle.readline().strip()
    if first_line.startswith("#!"):
        return shlex.split(first_line[2:].strip())

    ext = script_path.suffix.lower()
    if ext == ".py":
        return [sys.executable]
    if ext in {".sh", ".bash"}:
        return ["bash"]
    if ext == ".js":
        return ["node"]
    if ext == ".ps1":
        return ["pwsh" if shutil.which("pwsh") else "powershell"]
    if os.access(script_path, os.X_OK):
        return [str(script_path)]

    raise SkillExecutionError(
        f"Cannot determine interpreter for {script_path}. Add a shebang or known extension."
    )


async def run_script(
    skill: Skill,
    relative_path: str,
    payload: Optional[Mapping[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    payload = payload or {}
    skill_dir = skill.directory
    source_path = resolve_within(skill_dir, relative_path)
    if not source_path.exists():
        raise SkillExecutionError(
            f"Script '{relative_path}' not found for skill {skill.slug}."
        )

    with TemporaryWorkspace(skill_dir) as workspace:
        copied_path = workspace.copy_skill_contents()
        rel_target = resolve_within(copied_path, relative_path)

        files_payload = payload.get("files", [])
        for entry in files_payload:
            rel = entry.get("path")
            content = entry.get("content")
            encoding = entry.get("encoding", "text")
            if not rel or content is None:
                raise SkillExecutionError(
                    "Each file entry must include 'path' and 'content'."
                )
            dest = resolve_within(copied_path, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(decode_payload_content(content, encoding))

        args = payload.get("args", [])
        if isinstance(args, (str, bytes)):
            raise SkillExecutionError("'args' must be a sequence of argument strings.")
        if not isinstance(args, Iterable):
            raise SkillExecutionError("'args' must be an iterable of strings.")
        args_list = [str(item) for item in args]

        stdin_payload = payload.get("stdin")
        stdin_data: Optional[bytes]
        if stdin_payload is None:
            stdin_data = None
        elif isinstance(stdin_payload, str):
            stdin_data = stdin_payload.encode("utf-8")
        elif isinstance(stdin_payload, Mapping):
            stdin_content = stdin_payload.get("content", "")
            stdin_encoding = stdin_payload.get("encoding", "text")
            stdin_data = decode_payload_content(str(stdin_content), str(stdin_encoding))
        else:
            raise SkillExecutionError(
                "'stdin' must be text or {content, encoding} mapping."
            )

        env_payload = payload.get("env", {})
        if not isinstance(env_payload, Mapping):
            raise SkillExecutionError(
                "'env' must be a mapping of environment variables."
            )

        env: MutableMapping[str, str] = {
            "PATH": os.environ.get("PATH", ""),
        }
        for key in ("LANG", "LC_ALL", "PYTHONPATH"):
            if key in os.environ:
                env[key] = os.environ[key]
        for key, value in env_payload.items():
            env[str(key)] = str(value)

        cwd_relative = payload.get("workdir")
        if cwd_relative:
            workdir = resolve_within(copied_path, str(cwd_relative))
        else:
            workdir = rel_target.parent

        command = resolve_command(rel_target)
        if command and command[0] != str(rel_target):
            exec_command = [*command, str(rel_target), *args_list]
        else:
            exec_command = command if command else [str(rel_target)]
            exec_command.extend(args_list)

        proc = await asyncio.create_subprocess_exec(
            *exec_command,
            cwd=str(workdir),
            env={key: value for key, value in env.items() if isinstance(value, str)},
            stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        start_time = asyncio.get_running_loop().time()
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(stdin_data), timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            with contextlib.suppress(asyncio.CancelledError):
                await proc.wait()
            raise SkillExecutionError(
                f"Execution timed out after {timeout} seconds for {relative_path}."
            ) from exc

        duration = asyncio.get_running_loop().time() - start_time

    return {
        "command": exec_command,
        "cwd": str(workdir),
        "returncode": proc.returncode,
        "stdout": encode_output(stdout_data),
        "stderr": encode_output(stderr_data),
        "duration_seconds": duration,
    }


class TemporaryWorkspace:
    """Context manager that copies skill contents into a temp directory."""

    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self._tmpdir: Optional[tempfile.TemporaryDirectory[str]] = None

    def __enter__(self) -> "TemporaryWorkspace":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="skillz-")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
        self._tmpdir = None

    def copy_skill_contents(self) -> Path:
        if self._tmpdir is None:  # pragma: no cover - defensive
            raise RuntimeError("TemporaryWorkspace not entered")

        destination = Path(self._tmpdir.name) / self.source_dir.name
        shutil.copytree(self.source_dir, destination, dirs_exist_ok=True)
        return destination


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


Action = Literal["metadata", "read", "summarize", "run_script"]


def register_skill_tool(
    mcp: FastMCP, skill: Skill, *, timeout: float
) -> Callable[..., Awaitable[Mapping[str, Any]]]:
    tool_name = f"skill_tool::{skill.slug}"

    @mcp.tool(name=tool_name)
    async def _skill_tool(  # type: ignore[unused-ignore]
        action: Action,
        target: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
        summary_prompt: Optional[str] = None,
        sample_options: Optional[Mapping[str, Any]] = None,
        ctx: Optional[Context] = None,
        *,
        _skill: Skill = skill,
        _timeout: float = timeout,
    ) -> Mapping[str, Any]:
        start = asyncio.get_running_loop().time()
        LOGGER.info(
            "Skill %s tool invoked action=%s target=%s", _skill.slug, action, target
        )

        try:
            if action == "metadata":
                return {
                    "name": _skill.metadata.name,
                    "slug": _skill.slug,
                    "description": _skill.metadata.description,
                    "license": _skill.metadata.license,
                    "allowed_tools": list(_skill.metadata.allowed_tools),
                    "extra": _skill.metadata.extra,
                    "resources": [str(path) for path in _skill.resources],
                }

            if action == "read":
                if not target:
                    raise SkillError("'read' action requires 'target' relative path.")
                resource_path = resolve_within(_skill.directory, target)
                if not resource_path.exists() or not resource_path.is_file():
                    raise SkillError(
                        f"Resource '{target}' not found for {_skill.slug}."
                    )
                data = resource_path.read_bytes()
                response = encode_output(data)
                response.update(
                    {
                        "path": target,
                        "mime_type": guess_mime(resource_path),
                    }
                )
                return response

            if action == "summarize":
                if ctx is None:
                    raise SkillError(
                        "Summarize action requires context sampling support."
                    )
                if not target:
                    raise SkillError("'summarize' action requires 'target'.")
                resource_path = resolve_within(_skill.directory, target)
                if not resource_path.is_file():
                    raise SkillError(
                        f"Resource '{target}' not found for {_skill.slug}."
                    )
                content = resource_path.read_text(encoding="utf-8", errors="ignore")
                prompt = summary_prompt or textwrap.dedent(
                    f"""
                    Summarize the following content from the skill '{_skill.metadata.name}'.
                    Focus on actionable steps and key caveats. Return a concise summary.

                    Content:
                    {content}
                    """
                )
                options = dict(sample_options or {})
                response = await ctx.sample(prompt, **options)
                return {
                    "summary": response.text,
                    "target": target,
                }

            if action == "run_script":
                if not target:
                    raise SkillError("'run_script' action requires 'target'.")
                result = await run_script(_skill, target, payload, timeout=_timeout)
                return result

            raise SkillError(f"Unsupported action '{action}'.")
        except SkillError as exc:
            LOGGER.error(
                "Skill %s action %s failed: %s", _skill.slug, action, exc, exc_info=True
            )
            raise ToolError(str(exc)) from exc
        finally:
            duration = asyncio.get_running_loop().time() - start
            LOGGER.info(
                "Skill %s action %s completed in %.2fs", _skill.slug, action, duration
            )

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
            file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem failure is rare
            print(f"Failed to configure log file {log_path}: {exc}", file=sys.stderr)
        else:
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG if (log_to_file or verbose) else logging.INFO,
        handlers=handlers,
        force=True,
    )


def build_server(registry: SkillRegistry, *, timeout: float) -> FastMCP:
    summary = ", ".join(skill.metadata.name for skill in registry.skills) or "No skills"
    mcp = FastMCP(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=f"Loaded skills: {summary}",
    )
    for skill in registry.skills:
        register_skill_tool(mcp, skill, timeout=timeout)
    return mcp


def list_skills(registry: SkillRegistry) -> None:
    if not registry.skills:
        print("No valid skills discovered.")
        return
    for skill in registry.skills:
        print(f"- {skill.metadata.name} (slug: {skill.slug}) -> {skill.directory}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Skillz MCP server.")
    parser.add_argument(
        "skills_root", type=Path, help="Directory containing skill folders"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Script timeout in seconds",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "sse"),
        default="stdio",
        help="Transport to use when running the server",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host for HTTP/SSE transports"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP/SSE transports"
    )
    parser.add_argument("--path", default="/mcp", help="Path for HTTP transport")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
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
    return parser.parse_args(argv)


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

    server = build_server(registry, timeout=args.timeout)
    run_kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in {"http", "sse"}:
        run_kwargs.update({"host": args.host, "port": args.port})
        if args.transport == "http":
            run_kwargs["path"] = args.path

    server.run(**run_kwargs)


if __name__ == "__main__":
    main()
