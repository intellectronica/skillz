"""Skill usage logger for tracking skill invocations and reads.

Logs skill usage events to JSONL files for observability and debugging.
Supports configurable log levels and output destinations.

Configuration is loaded from a JSON file in the skills root directory:
  {skills_root}/.skillz-config.json

Or from the MCP client-provided config in the skill invocation.

Example config:
{
  "logging": {
    "enabled": true,
    "level": "info",  // "debug", "info", "warn", "error", "off"
    "output": "file", // "file", "stderr", "both"
    "file_path": null, // null = auto-detect, or explicit path
    "events": {
      "skill_invoked": true,
      "skill_read": true,
      "resource_fetched": true
    }
  }
}
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger("skillz.usage")


@dataclass
class SkillUsageLogConfig:
    """Configuration for skill usage logging."""

    enabled: bool = True
    level: str = "info"  # debug, info, warn, error, off
    output: str = "file"  # file, stderr, both
    file_path: Optional[Path] = None
    events: Dict[str, bool] = field(default_factory=lambda: {
        "skill_invoked": True,
        "skill_read": True,
        "resource_fetched": True,
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillUsageLogConfig":
        """Create config from dictionary."""
        logging_config = data.get("logging", {})

        events = logging_config.get("events", {})
        default_events = {
            "skill_invoked": True,
            "skill_read": True,
            "resource_fetched": True,
        }
        merged_events = {**default_events, **events}

        file_path = logging_config.get("file_path")
        if file_path:
            file_path = Path(file_path).expanduser()

        return cls(
            enabled=logging_config.get("enabled", True),
            level=logging_config.get("level", "info"),
            output=logging_config.get("output", "file"),
            file_path=file_path,
            events=merged_events,
        )

    def should_log_event(self, event_type: str) -> bool:
        """Check if an event type should be logged."""
        if not self.enabled:
            return False
        if self.level == "off":
            return False
        return self.events.get(event_type, False)


class SkillUsageLogger:
    """Logger for tracking skill usage events."""

    _instance: Optional["SkillUsageLogger"] = None
    _config: SkillUsageLogConfig
    _skills_root: Optional[Path]
    _log_file: Optional[Path]

    def __init__(
        self,
        config: SkillUsageLogConfig,
        skills_root: Optional[Path] = None
    ):
        self._config = config
        self._skills_root = skills_root
        self._log_file = self._resolve_log_file()

    @classmethod
    def initialize(
        cls,
        skills_root: Path,
        config_override: Optional[Dict[str, Any]] = None
    ) -> "SkillUsageLogger":
        """Initialize the global logger instance.

        Args:
            skills_root: Path to the skills directory
            config_override: Optional config dict to override file config
        """
        config = cls._load_config(skills_root, config_override)
        cls._instance = cls(config, skills_root)

        if config.enabled and config.level != "off":
            LOGGER.info(
                "Skill usage logging initialized: level=%s, output=%s",
                config.level,
                config.output
            )

        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional["SkillUsageLogger"]:
        """Get the global logger instance."""
        return cls._instance

    @classmethod
    def _load_config(
        cls,
        skills_root: Path,
        config_override: Optional[Dict[str, Any]] = None
    ) -> SkillUsageLogConfig:
        """Load configuration from file or use defaults."""
        if config_override:
            return SkillUsageLogConfig.from_dict(config_override)

        # Try to load from .skillz-config.json in skills root
        config_file = skills_root / ".skillz-config.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                return SkillUsageLogConfig.from_dict(data)
            except (json.JSONDecodeError, OSError) as e:
                LOGGER.warning(
                    "Failed to load config from %s: %s",
                    config_file, e
                )

        # Try environment variable for config path
        env_config = os.environ.get("SKILLZ_CONFIG")
        if env_config:
            config_path = Path(env_config).expanduser()
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text())
                    return SkillUsageLogConfig.from_dict(data)
                except (json.JSONDecodeError, OSError) as e:
                    LOGGER.warning(
                        "Failed to load config from SKILLZ_CONFIG=%s: %s",
                        env_config, e
                    )

        # Return defaults
        return SkillUsageLogConfig()

    def _resolve_log_file(self) -> Optional[Path]:
        """Resolve the log file path."""
        if self._config.output not in ("file", "both"):
            return None

        if self._config.file_path:
            log_file = self._config.file_path
        elif self._skills_root:
            # Default to logs directory in skills root
            logs_dir = self._skills_root.parent / "logs"
            log_file = logs_dir / "skill_usage.jsonl"
        else:
            # Fallback to temp directory
            log_file = Path("/tmp/skillz_usage.jsonl")

        # Ensure parent directory exists
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            LOGGER.warning(
                "Failed to create log directory %s: %s",
                log_file.parent, e
            )
            return None

        return log_file

    def _write_log_entry(self, entry: Dict[str, Any]) -> None:
        """Write a log entry to configured outputs."""
        json_line = json.dumps(entry)

        if self._config.output in ("file", "both") and self._log_file:
            try:
                with open(self._log_file, "a") as f:
                    f.write(json_line + "\n")
            except OSError as e:
                LOGGER.warning("Failed to write to log file: %s", e)

        if self._config.output in ("stderr", "both"):
            print(json_line, file=sys.stderr)

    def log_skill_invoked(
        self,
        skill_slug: str,
        task: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log a skill invocation event.

        Returns a session_id for correlating subsequent events.
        """
        if not self._config.should_log_event("skill_invoked"):
            return secrets.token_hex(8)

        session_id = secrets.token_hex(8)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event": "skill_invoked",
            "skill": skill_slug,
            "task": self._sanitize_string(task),
            "metadata": metadata or {},
        }
        self._write_log_entry(entry)
        return session_id

    def log_skill_read(
        self,
        skill_slug: str,
        reader: str = "unknown",
        session_id: Optional[str] = None
    ) -> None:
        """Log when a skill's instructions are read."""
        if not self._config.should_log_event("skill_read"):
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or secrets.token_hex(8),
            "event": "skill_read",
            "skill": skill_slug,
            "reader": reader,
        }
        self._write_log_entry(entry)

    def log_resource_fetched(
        self,
        skill_slug: str,
        resource_uri: str,
        session_id: Optional[str] = None
    ) -> None:
        """Log when a skill resource is fetched."""
        if not self._config.should_log_event("resource_fetched"):
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or secrets.token_hex(8),
            "event": "resource_fetched",
            "skill": skill_slug,
            "resource_uri": resource_uri,
        }
        self._write_log_entry(entry)

    def log_skill_complete(
        self,
        session_id: str,
        skill_slug: str,
        status: str,
        duration_ms: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log skill invocation completion."""
        if not self._config.should_log_event("skill_invoked"):
            return

        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event": "skill_complete",
            "skill": skill_slug,
            "status": status,
        }
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if result:
            entry["result"] = result

        self._write_log_entry(entry)

    @staticmethod
    def _sanitize_string(value: str, max_len: int = 200) -> str:
        """Sanitize a string value for logging."""
        if len(value) > max_len:
            return value[:max_len - 3] + "..."
        return value


def get_usage_logger() -> Optional[SkillUsageLogger]:
    """Get the global skill usage logger instance."""
    return SkillUsageLogger.get_instance()
