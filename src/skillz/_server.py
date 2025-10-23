"""Skillz MCP server exposing local Anthropic-style skills via FastMCP.

Usage examples::

    uv run python -m skillz /path/to/skills --verbose
    uv run python -m skillz tmp/examples --list-skills

Manual smoke tests rely on the sample fixture in ``tmp/examples`` created
by the project checklist. The ``--list-skills`` flag validates discovery
without starting the transport, while additional sanity checks can be run
with a short script that invokes the generated tool functions directly.

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
    Mapping,
    MutableMapping,
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
DEFAULT_TIMEOUT = 60.0
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
            f"Skill {self.slug} is missing YAML front matter "
            "and cannot be served."
        )


class SkillResourceMetadata(TypedDict):
    """Metadata describing a registered skill resource."""

    path: str
    relative_path: str
    uri: str
    runnable: bool


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


def resolve_within(base: Path, relative: str) -> Path:
    """Resolve a relative path within base, preventing path traversal."""

    base_resolved = base.resolve()
    candidate = (base_resolved / relative).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise SkillError(
            f"Path '{relative}' escapes skill directory {base}."
        ) from exc
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
        return {
            "encoding": "base64",
            "content": base64.b64encode(data).decode("ascii"),
        }
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
        f"Cannot determine interpreter for {script_path}. "
        "Add a shebang or known extension."
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
            raise SkillExecutionError(
                "'args' must be a sequence of argument strings."
            )
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
            stdin_data = decode_payload_content(
                str(stdin_content),
                str(stdin_encoding),
            )
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
            env={
                key: value
                for key, value in env.items()
                if isinstance(value, str)
            },
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
                "Execution timed out after "
                f"{timeout} seconds for {relative_path}."
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


def _build_resource_uri(skill: Skill, relative_path: Path) -> str:
    encoded_slug = quote(skill.slug, safe="")
    encoded_parts = [quote(part, safe="") for part in relative_path.parts]
    path_suffix = "/".join(encoded_parts)
    if path_suffix:
        return f"resource://skillz/{encoded_slug}/{path_suffix}"
    return f"resource://skillz/{encoded_slug}"


def _is_probably_script(path: Path) -> bool:
    """Return True when a resource looks executable."""

    try:
        resolve_command(path)
    except (OSError, SkillExecutionError, SkillError):
        return False
    return True


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
        is_instructions_file = resource_path == skill.instructions_path
        runnable = False
        if not is_instructions_file:
            runnable = _is_probably_script(resource_path)

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
                "path": str(resource_path),
                "relative_path": relative_display,
                "uri": uri,
                "runnable": runnable,
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
    timeout: float,
    resources: tuple[SkillResourceMetadata, ...],
) -> Callable[..., Awaitable[Mapping[str, Any]]]:
    tool_name = skill.slug
    description = _format_tool_description(skill)
    bound_skill = skill
    bound_timeout = timeout
    bound_resources = resources

    @mcp.tool(name=tool_name, description=description)
    async def _skill_tool(  # type: ignore[unused-ignore]
        task: str,
        script: Optional[str] = None,
        script_payload: Optional[Mapping[str, Any]] = None,
        script_timeout: Optional[float] = None,
        ctx: Optional[Context] = None,
    ) -> Mapping[str, Any]:
        start = asyncio.get_running_loop().time()
        LOGGER.info(
            "Skill %s tool invoked task=%s script=%s",
            bound_skill.slug,
            task,
            script,
        )

        try:
            if not task.strip():
                raise SkillError(
                    "The 'task' parameter must be a non-empty string."
                )

            instructions = bound_skill.read_body()
            resource_entries = [
                {
                    "path": entry["path"],
                    "relative_path": entry["relative_path"],
                    "uri": entry["uri"],
                    "runnable": entry["runnable"],
                }
                for entry in bound_resources
            ]
            resource_uris = [entry["uri"] for entry in resource_entries]
            legacy_paths = [entry["path"] for entry in resource_entries]
            script_entries = [
                {
                    "path": entry["path"],
                    "relative_path": entry["relative_path"],
                    "uri": entry["uri"],
                }
                for entry in resource_entries
                if entry["runnable"]
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
                "usage": {
                    "suggested_prompt": textwrap.dedent(
                        f"""
                        You are using the skill '{bound_skill.metadata.name}'.

                        Task:
                        {task}

                        Follow the published skill instructions exactly:

                        {instructions}
                        """
                    ).strip(),
                    "guidance": textwrap.dedent(
                        """\
Share the `suggested_prompt` with your assistant or embed the
`instructions` text directly alongside the task so the model can apply
the skill as authored. If the instructions mention supporting files,
call `ctx.read_resource` with one of the URIs in `available_resources`
before handing data to the model.
"""
                    ).strip(),
                    "script_execution": {
                        "call_instructions": textwrap.dedent(
                            """\
Invoke this tool again with the `script` parameter set to a path
relative to the skill root (choose from `available_scripts`) and
optionally include `script_payload` (keys: args, env, files, stdin,
workdir).
"""
                        ).strip(),
                        "payload_fields": {
                            "args": (
                                "List of strings forwarded as command "
                                "arguments"
                            ),
                            "env": (
                                "Mapping of environment variables "
                                "to merge with the default sandbox"
                            ),
                            "files": (
                                "Mapping of relative file paths to their "
                                "contents (encoding + content)"
                            ),
                            "stdin": (
                                "String or bytes (base64) provided on "
                                "standard input"
                            ),
                            "workdir": (
                                "Optional working directory relative to the "
                                "copied skill root"
                            ),
                        },
                        "available_scripts": script_entries,
                        "available_resources": [
                            *resource_uris,
                            *legacy_paths,
                        ],
                    },
                },
            }

            if script is not None:
                if not script.strip():
                    raise SkillError(
                        "Script path, if provided, must be a non-empty string."
                    )
                normalized_script = script.replace("\\", "/")
                script_path = Path(normalized_script)
                if script_path.is_absolute():
                    raise SkillError(
                        "Script path must be relative to the skill directory."
                    )
                normalized_relative = script_path.as_posix()
                matching_resource = next(
                    (
                        entry
                        for entry in resource_entries
                        if entry["relative_path"] == normalized_relative
                    ),
                    None,
                )
                if matching_resource and not matching_resource["runnable"]:
                    raise SkillError(
                        "'{relative}' is a resource, not an executable. Use "
                        "ctx.read_resource('{uri}') to read it instead."
                        .format(
                            relative=matching_resource["relative_path"],
                            uri=matching_resource["uri"],
                        )
                    )
                script = normalized_relative
                payload_mapping: Mapping[str, Any]
                if script_payload is None:
                    payload_mapping = {}
                elif isinstance(script_payload, Mapping):
                    payload_mapping = dict(script_payload)
                else:
                    raise SkillError(
                        "'script_payload' must be a mapping of script inputs."
                    )

                effective_timeout = bound_timeout
                if script_timeout is not None:
                    effective_timeout = float(script_timeout)

                result = await run_script(
                    bound_skill,
                    script,
                    payload_mapping,
                    timeout=effective_timeout,
                )
                response["script_execution"] = result

            return response
        except SkillError as exc:
            LOGGER.error(
                "Skill %s invocation failed: %s",
                bound_skill.slug,
                exc,
                exc_info=True,
            )
            raise ToolError(str(exc)) from exc
        finally:
            duration = asyncio.get_running_loop().time() - start
            LOGGER.info(
                "Skill %s invocation completed in %.2fs",
                bound_skill.slug,
                duration,
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


def build_server(registry: SkillRegistry, *, timeout: float) -> FastMCP:
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
            timeout=timeout,
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

    server = build_server(registry, timeout=args.timeout)
    run_kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in {"http", "sse"}:
        run_kwargs.update({"host": args.host, "port": args.port})
        if args.transport == "http":
            run_kwargs["path"] = args.path

    server.run(**run_kwargs)


if __name__ == "__main__":
    main()
