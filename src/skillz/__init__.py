"""Public package interface for the Skillz MCP server."""

from ._version import __version__
from ._server import (
    Skill,
    SkillError,
    SkillExecutionError,
    SkillMetadata,
    SkillRegistry,
    SkillValidationError,
    build_server,
    configure_logging,
    list_skills,
    main,
    parse_args,
)

__all__ = [
    "Skill",
    "SkillError",
    "SkillExecutionError",
    "SkillMetadata",
    "SkillRegistry",
    "SkillValidationError",
    "build_server",
    "configure_logging",
    "list_skills",
    "main",
    "parse_args",
    "__version__",
]
