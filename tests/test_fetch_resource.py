"""Test the fetch_resource tool for clients without MCP resource support."""

import base64
from pathlib import Path

import pytest

from skillz import SkillRegistry, build_server


def write_skill_with_resources(
    directory: Path, name: str = "TestSkill"
) -> Path:
    """Create a test skill with text and binary resources."""
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

    # Create binary file (with invalid UTF-8 sequences)
    (skill_dir / "data.bin").write_bytes(b"\xff\xfe\x00\x01\x80\x90")

    return skill_dir


@pytest.mark.asyncio
async def test_fetch_text_resource(tmp_path: Path) -> None:
    """Test fetching a text resource returns UTF-8 encoded content."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)

    # Get the fetch_resource tool
    tools = await server.get_tools()
    assert "fetch_resource" in tools

    fetch_tool = tools["fetch_resource"]

    # Fetch a text resource
    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/script.py"
    )

    # Verify response structure
    assert "uri" in result
    assert "name" in result
    assert "mime_type" in result
    assert "content" in result
    assert "encoding" in result

    # Verify content
    assert result["uri"] == "resource://skillz/testskill/script.py"
    assert result["name"] == "testskill/script.py"
    assert result["mime_type"] == "text/x-python"
    assert result["encoding"] == "utf-8"
    assert result["content"] == "print('hello')"


@pytest.mark.asyncio
async def test_fetch_binary_resource(tmp_path: Path) -> None:
    """Test fetching a binary resource returns base64 encoded content."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Fetch a binary resource
    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/data.bin"
    )

    # Verify encoding
    assert result["encoding"] == "base64"

    # Verify content can be decoded
    decoded = base64.b64decode(result["content"])
    assert decoded == b"\xff\xfe\x00\x01\x80\x90"

    # Verify other fields
    assert result["uri"] == "resource://skillz/testskill/data.bin"
    assert result["name"] == "testskill/data.bin"


@pytest.mark.asyncio
async def test_fetch_resource_invalid_prefix(tmp_path: Path) -> None:
    """Test that invalid URI prefix returns error resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try to fetch with invalid prefix
    result = await fetch_tool.fn(resource_uri="file:///etc/passwd")

    # Should return error resource
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("Error:")
    assert "unsupported URI prefix" in result["content"]
    assert result["uri"] == "file:///etc/passwd"


@pytest.mark.asyncio
async def test_fetch_resource_missing_slug(tmp_path: Path) -> None:
    """Test that missing slug in URI returns error resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try to fetch with no slug
    result = await fetch_tool.fn(resource_uri="resource://skillz/")

    # Should return error resource
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("Error:")
    assert "invalid resource URI format" in result["content"]


@pytest.mark.asyncio
async def test_fetch_resource_nonexistent_skill(tmp_path: Path) -> None:
    """Test that nonexistent skill returns error resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try to fetch from nonexistent skill
    result = await fetch_tool.fn(
        resource_uri="resource://skillz/nope/some.txt"
    )

    # Should return error resource
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("Error:")
    assert "skill not found: nope" in result["content"]


@pytest.mark.asyncio
async def test_fetch_resource_nonexistent_file(tmp_path: Path) -> None:
    """Test that nonexistent file in valid skill returns error resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try to fetch nonexistent file from valid skill
    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/missing.txt"
    )

    # Should return error resource
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("Error:")
    assert "resource not found: missing.txt" in result["content"]


@pytest.mark.asyncio
async def test_fetch_resource_empty_uri(tmp_path: Path) -> None:
    """Test that empty URI returns error resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try to fetch with empty URI
    result = await fetch_tool.fn(resource_uri="")

    # Should return error resource
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("Error:")
    assert "resource_uri is required" in result["content"]


@pytest.mark.asyncio
async def test_skill_usage_mentions_fetch_resource(tmp_path: Path) -> None:
    """Test that skill tool usage text mentions fetch_resource."""
    write_skill_with_resources(tmp_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()

    # Get the skill tool
    assert "testskill" in tools
    skill_tool = tools["testskill"]

    # Invoke the skill tool
    result = await skill_tool.fn(task="test task")

    # Check that usage mentions fetch_resource
    assert "usage" in result
    assert "fetch_resource" in result["usage"]
    assert "resource_uri" in result["usage"]
