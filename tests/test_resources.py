"""Test that resource metadata follows MCP specification."""

from pathlib import Path

from skillz import SkillRegistry
from skillz._server import register_skill_resources


def write_skill_with_resources(
    directory: Path, name: str = "TestSkill"
) -> Path:
    """Create a test skill with multiple resource types."""
    skill_dir = directory / name.lower()
    skill_dir.mkdir()

    # Create SKILL.md
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: Test skill with resources
---
Test skill instructions.
""",
        encoding="utf-8",
    )

    # Create text file
    (skill_dir / "script.py").write_text("print('hello')", encoding="utf-8")

    # Create another text file
    (skill_dir / "README.md").write_text("# README", encoding="utf-8")

    # Create binary file
    (skill_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03")

    return skill_dir


def test_resource_metadata_follows_mcp_spec(tmp_path: Path) -> None:
    """Resources should have uri, name, and mimeType (no description)."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    skill = registry.get("testskill")

    # Get resource metadata
    from fastmcp import FastMCP

    mcp = FastMCP()
    metadata = register_skill_resources(mcp, skill)

    # Should have 3 resources (script.py, README.md, data.bin)
    # SKILL.md is NOT a resource - it's only returned from the tool
    assert len(metadata) == 3

    # Check each resource has required fields
    for resource in metadata:
        # Must have these fields according to MCP spec
        assert "uri" in resource
        assert "name" in resource
        assert "mime_type" in resource

        # Should NOT have these fields
        assert "description" not in resource
        assert "relative_path" not in resource

        # URI should follow MCP format: protocol://host/path
        assert resource["uri"].startswith("resource://skillz/testskill/")

        # Name should be path without protocol
        assert resource["name"].startswith("testskill/")
        assert not resource["name"].startswith("resource://")

        # SKILL.md should NOT be in resources
        assert "SKILL.md" not in resource["name"]


def test_resource_mime_types(tmp_path: Path) -> None:
    """MIME types should be detected correctly."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    skill = registry.get("testskill")

    from fastmcp import FastMCP

    mcp = FastMCP()
    metadata = register_skill_resources(mcp, skill)

    # Create lookup by name
    resources_by_name = {r["name"]: r for r in metadata}

    # SKILL.md should NOT be in resources
    assert "testskill/SKILL.md" not in resources_by_name

    # Check MIME types for actual resources
    assert (
        resources_by_name["testskill/script.py"]["mime_type"]
        == "text/x-python"
    )
    assert (
        resources_by_name["testskill/README.md"]["mime_type"]
        == "text/markdown"
    )
    # Binary files may not have a detected MIME type
    assert resources_by_name["testskill/data.bin"]["mime_type"] in [
        None,
        "application/octet-stream",
    ]


def test_resource_uris_use_resource_protocol(tmp_path: Path) -> None:
    """Resource URIs should use resource:// protocol, not file://."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    skill = registry.get("testskill")

    from fastmcp import FastMCP

    mcp = FastMCP()
    metadata = register_skill_resources(mcp, skill)

    # All URIs should use resource:// protocol
    for resource in metadata:
        assert resource["uri"].startswith("resource://")
        assert not resource["uri"].startswith("file://")
