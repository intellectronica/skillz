"""Tests for skill usage logger functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from skillz._skill_usage_logger import (
    SkillUsageLogConfig,
    SkillUsageLogger,
    get_usage_logger,
)


class TestSkillUsageLogConfig:
    """Tests for SkillUsageLogConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SkillUsageLogConfig()
        assert config.enabled is True
        assert config.level == "info"
        assert config.output == "file"
        assert config.file_path is None
        assert config.events["skill_invoked"] is True
        assert config.events["skill_read"] is True
        assert config.events["resource_fetched"] is True

    def test_from_dict_empty(self):
        """Test creating config from empty dict uses defaults."""
        config = SkillUsageLogConfig.from_dict({})
        assert config.enabled is True
        assert config.level == "info"

    def test_from_dict_disabled(self):
        """Test creating disabled config."""
        config = SkillUsageLogConfig.from_dict({
            "logging": {"enabled": False}
        })
        assert config.enabled is False

    def test_from_dict_custom_events(self):
        """Test custom event filtering."""
        config = SkillUsageLogConfig.from_dict({
            "logging": {
                "events": {
                    "skill_invoked": True,
                    "skill_read": False,
                    "resource_fetched": False,
                }
            }
        })
        assert config.events["skill_invoked"] is True
        assert config.events["skill_read"] is False
        assert config.events["resource_fetched"] is False

    def test_from_dict_file_path_expansion(self):
        """Test that file paths are expanded."""
        config = SkillUsageLogConfig.from_dict({
            "logging": {"file_path": "~/logs/test.jsonl"}
        })
        assert config.file_path is not None
        assert "~" not in str(config.file_path)

    def test_should_log_event_when_disabled(self):
        """Test that no events are logged when disabled."""
        config = SkillUsageLogConfig(enabled=False)
        assert config.should_log_event("skill_invoked") is False
        assert config.should_log_event("skill_read") is False

    def test_should_log_event_when_level_off(self):
        """Test that no events are logged when level is off."""
        config = SkillUsageLogConfig(enabled=True, level="off")
        assert config.should_log_event("skill_invoked") is False

    def test_should_log_event_filters_by_event_type(self):
        """Test that events are filtered by type."""
        config = SkillUsageLogConfig(
            enabled=True,
            events={
                "skill_invoked": True,
                "skill_read": False,
                "resource_fetched": True,
            }
        )
        assert config.should_log_event("skill_invoked") is True
        assert config.should_log_event("skill_read") is False
        assert config.should_log_event("resource_fetched") is True


class TestSkillUsageLogger:
    """Tests for SkillUsageLogger."""

    @pytest.fixture
    def temp_skills_root(self):
        """Create a temporary skills root directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_root = Path(tmpdir) / "skills"
            skills_root.mkdir()
            yield skills_root

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file path."""
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False
        ) as f:
            yield Path(f.name)

    def test_initialize_creates_instance(self, temp_skills_root):
        """Test that initialize creates a global instance."""
        # Reset any existing instance
        SkillUsageLogger._instance = None

        logger = SkillUsageLogger.initialize(temp_skills_root)
        assert logger is not None
        assert get_usage_logger() is logger

    def test_log_skill_invoked_returns_session_id(self, temp_skills_root):
        """Test that log_skill_invoked returns a session ID."""
        SkillUsageLogger._instance = None
        logger = SkillUsageLogger.initialize(temp_skills_root)

        session_id = logger.log_skill_invoked(
            skill_slug="test-skill",
            task="Test task"
        )

        assert session_id is not None
        assert len(session_id) == 16  # hex string of 8 bytes

    def test_log_skill_invoked_writes_to_file(self, temp_skills_root):
        """Test that skill invocation is logged to file."""
        SkillUsageLogger._instance = None
        log_file = temp_skills_root.parent / "logs" / "skill_usage.jsonl"

        logger = SkillUsageLogger.initialize(temp_skills_root)
        logger.log_skill_invoked(
            skill_slug="test-skill",
            task="Test task",
            metadata={"test": "value"}
        )

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event"] == "skill_invoked"
        assert entry["skill"] == "test-skill"
        assert entry["task"] == "Test task"
        assert "session_id" in entry
        assert "timestamp" in entry

    def test_log_skill_read(self, temp_skills_root):
        """Test that skill read is logged."""
        SkillUsageLogger._instance = None
        log_file = temp_skills_root.parent / "logs" / "skill_usage.jsonl"

        logger = SkillUsageLogger.initialize(temp_skills_root)
        logger.log_skill_read(
            skill_slug="test-skill",
            reader="test_reader",
            session_id="abc123"
        )

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event"] == "skill_read"
        assert entry["skill"] == "test-skill"
        assert entry["reader"] == "test_reader"
        assert entry["session_id"] == "abc123"

    def test_log_resource_fetched(self, temp_skills_root):
        """Test that resource fetch is logged."""
        SkillUsageLogger._instance = None
        log_file = temp_skills_root.parent / "logs" / "skill_usage.jsonl"

        logger = SkillUsageLogger.initialize(temp_skills_root)
        logger.log_resource_fetched(
            skill_slug="test-skill",
            resource_uri="resource://skillz/test-skill/scripts/test.py"
        )

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event"] == "resource_fetched"
        assert entry["skill"] == "test-skill"
        assert "resource://skillz" in entry["resource_uri"]

    def test_log_skill_complete(self, temp_skills_root):
        """Test that skill completion is logged."""
        SkillUsageLogger._instance = None
        log_file = temp_skills_root.parent / "logs" / "skill_usage.jsonl"

        logger = SkillUsageLogger.initialize(temp_skills_root)
        logger.log_skill_complete(
            session_id="abc123",
            skill_slug="test-skill",
            status="success",
            duration_ms=150,
            result={"key": "value"}
        )

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event"] == "skill_complete"
        assert entry["session_id"] == "abc123"
        assert entry["skill"] == "test-skill"
        assert entry["status"] == "success"
        assert entry["duration_ms"] == 150
        assert entry["result"] == {"key": "value"}

    def test_disabled_logging_skips_writes(self, temp_skills_root):
        """Test that disabled logging doesn't write anything."""
        SkillUsageLogger._instance = None
        log_file = temp_skills_root.parent / "logs" / "skill_usage.jsonl"

        logger = SkillUsageLogger.initialize(
            temp_skills_root,
            config_override={"logging": {"enabled": False}}
        )
        logger.log_skill_invoked(
            skill_slug="test-skill",
            task="Test task"
        )

        # Log file shouldn't exist or be empty
        if log_file.exists():
            assert log_file.read_text() == ""

    def test_sanitize_string_truncates_long_strings(self, temp_skills_root):
        """Test that long strings are truncated."""
        long_string = "x" * 300
        result = SkillUsageLogger._sanitize_string(long_string)
        assert len(result) == 200
        assert result.endswith("...")

    def test_config_from_file(self, temp_skills_root):
        """Test that config is loaded from .skillz-config.json."""
        SkillUsageLogger._instance = None

        config_file = temp_skills_root / ".skillz-config.json"
        config_file.write_text(json.dumps({
            "logging": {
                "enabled": True,
                "level": "debug",
                "output": "both",
            }
        }))

        logger = SkillUsageLogger.initialize(temp_skills_root)
        assert logger._config.enabled is True
        assert logger._config.level == "debug"
        assert logger._config.output == "both"

    def test_config_override_takes_precedence(self, temp_skills_root):
        """Test that config override takes precedence over file."""
        SkillUsageLogger._instance = None

        config_file = temp_skills_root / ".skillz-config.json"
        config_file.write_text(json.dumps({
            "logging": {"enabled": True}
        }))

        logger = SkillUsageLogger.initialize(
            temp_skills_root,
            config_override={"logging": {"enabled": False}}
        )
        assert logger._config.enabled is False
