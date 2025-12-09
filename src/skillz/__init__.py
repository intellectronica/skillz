"""Public package interface for the Skillz MCP server."""

from ._version import __version__
from ._server import (
    Skill,
    SkillError,
    SkillMetadata,
    SkillRegistry,
    SkillValidationError,
    build_server,
    configure_logging,
    list_skills,
    main,
    parse_args,
)
from ._skill_usage_logger import (
    SkillUsageLogger,
    SkillUsageLogConfig,
    get_usage_logger,
)

__all__ = [
    "Skill",
    "SkillError",
    "SkillMetadata",
    "SkillRegistry",
    "SkillUsageLogConfig",
    "SkillUsageLogger",
    "SkillValidationError",
    "build_server",
    "configure_logging",
    "get_usage_logger",
    "list_skills",
    "main",
    "parse_args",
    "__version__",
]
