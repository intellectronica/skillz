"""Tests for zip-based skills support."""

import base64
from pathlib import Path
import zipfile

import pytest

from skillz import SkillRegistry, build_server


def create_zip_skill(
    zip_path: Path, name: str = "TestSkill", with_resources: bool = True
) -> None:
    """Create a test skill in a zip file."""
    with zipfile.ZipFile(zip_path, "w") as z:
        # Create SKILL.md
        skill_md_content = f"""---
name: {name}
description: Test skill from zip
---
Test skill instructions from zip file.
"""
        z.writestr("SKILL.md", skill_md_content)

        if with_resources:
            # Create text file
            z.writestr("text/hello.txt", "Hello from zip!")

            # Create binary file
            z.writestr("bin/data.bin", b"\xff\xfe\x00\x01\x80\x90")

            # Create Python script
            z.writestr("scripts/run.py", "print('hello')")


def test_zip_skill_loads_and_parses_skill_md(tmp_path: Path) -> None:
    """Test that a zip with SKILL.md at root is loaded correctly."""
    zip_path = tmp_path / "my-skill.zip"
    create_zip_skill(zip_path, name="MySkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    assert len(registry.skills) == 1
    skill = registry.get("myskill")
    assert skill.metadata.name == "MySkill"
    assert skill.metadata.description == "Test skill from zip"
    assert skill.is_zip
    assert skill.zip_path == zip_path.resolve()


def test_zip_skill_resources_are_discovered(tmp_path: Path) -> None:
    """Test that resources in zip are discovered with correct URIs."""
    zip_path = tmp_path / "my-skill.zip"
    create_zip_skill(zip_path, name="MySkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    skill = registry.get("myskill")

    from fastmcp import FastMCP

    mcp = FastMCP()
    from skillz._server import register_skill_resources

    metadata = register_skill_resources(mcp, skill)

    # Should have 3 resources
    assert len(metadata) == 3

    # Check URIs
    uris = {m["uri"] for m in metadata}
    assert "resource://skillz/myskill/text/hello.txt" in uris
    assert "resource://skillz/myskill/bin/data.bin" in uris
    assert "resource://skillz/myskill/scripts/run.py" in uris

    # Check names
    names = {m["name"] for m in metadata}
    assert "myskill/text/hello.txt" in names
    assert "myskill/bin/data.bin" in names
    assert "myskill/scripts/run.py" in names

    # SKILL.md should NOT be in resources
    for m in metadata:
        assert "SKILL.md" not in m["name"]


@pytest.mark.asyncio
async def test_zip_skill_text_resource_read(tmp_path: Path) -> None:
    """Test reading text resource from zip-based skill."""
    zip_path = tmp_path / "test-skill.zip"
    create_zip_skill(zip_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/text/hello.txt"
    )

    assert result["uri"] == "resource://skillz/testskill/text/hello.txt"
    assert result["name"] == "testskill/text/hello.txt"
    assert result["mime_type"] == "text/plain"
    assert result["encoding"] == "utf-8"
    assert result["content"] == "Hello from zip!"


@pytest.mark.asyncio
async def test_zip_skill_binary_resource_read(tmp_path: Path) -> None:
    """Test reading binary resource from zip-based skill."""
    zip_path = tmp_path / "test-skill.zip"
    create_zip_skill(zip_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/bin/data.bin"
    )

    assert result["uri"] == "resource://skillz/testskill/bin/data.bin"
    assert result["name"] == "testskill/bin/data.bin"
    assert result["encoding"] == "base64"

    # Verify content can be decoded
    decoded = base64.b64decode(result["content"])
    assert decoded == b"\xff\xfe\x00\x01\x80\x90"


def test_zip_missing_skill_md_is_ignored(tmp_path: Path) -> None:
    """Test that zip without SKILL.md at root is ignored."""
    zip_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("README.md", "# Not a skill")
        z.writestr("some/nested/file.txt", "content")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Should not be loaded
    assert len(registry.skills) == 0


def test_corrupt_zip_is_ignored(tmp_path: Path) -> None:
    """Test that corrupt zip file is ignored gracefully."""
    zip_path = tmp_path / "corrupt.zip"
    zip_path.write_bytes(b"This is not a valid zip file at all!")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Should not crash, just ignore the invalid zip
    assert len(registry.skills) == 0


def test_zip_inside_dir_skill_is_ignored(tmp_path: Path) -> None:
    """Test that zip files inside directory skills are ignored."""
    # Create directory skill
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: DirectorySkill
description: A directory-based skill
---
Directory skill content.
""",
        encoding="utf-8",
    )

    # Place a zip file inside the skill directory
    zip_path = skill_dir / "nested.zip"
    create_zip_skill(zip_path, name="NestedSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Only the directory skill should be loaded
    assert len(registry.skills) == 1
    skill = registry.get("directoryskill")
    assert skill.metadata.name == "DirectorySkill"
    assert not skill.is_zip


def test_zips_in_non_skill_subdirectories_are_loaded(tmp_path: Path) -> None:
    """Test that zips in subdirectories without SKILL.md are loaded."""
    # Create subdirectory structure
    packs_a = tmp_path / "packs" / "a"
    packs_a.mkdir(parents=True)
    packs_b = tmp_path / "packs" / "b"
    packs_b.mkdir(parents=True)

    # Create zip skills in subdirectories
    create_zip_skill(packs_a / "skill-a.zip", name="SkillA")
    create_zip_skill(packs_b / "skill-b.zip", name="SkillB")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Both should be loaded
    assert len(registry.skills) == 2
    skill_a = registry.get("skilla")
    skill_b = registry.get("skillb")
    assert skill_a.metadata.name == "SkillA"
    assert skill_b.metadata.name == "SkillB"
    assert skill_a.is_zip
    assert skill_b.is_zip


def test_nested_zip_not_treated_as_skill(tmp_path: Path) -> None:
    """Test that zip files inside zip-based skills are just resources."""
    zip_path = tmp_path / "outer.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        # Create SKILL.md at root
        z.writestr(
            "SKILL.md",
            """---
name: OuterSkill
description: Outer skill
---
Outer skill content.
""",
        )

        # Add a nested zip as a resource
        inner_zip_data = b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00"
        z.writestr("resources/inner.zip", inner_zip_data)

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Only outer skill should be loaded
    assert len(registry.skills) == 1
    skill = registry.get("outerskill")
    assert skill.metadata.name == "OuterSkill"
    assert skill.is_zip

    # The inner.zip should be a resource, not a separate skill
    from fastmcp import FastMCP
    from skillz._server import register_skill_resources

    mcp = FastMCP()
    metadata = register_skill_resources(mcp, skill)

    resource_names = {m["name"] for m in metadata}
    assert "outerskill/resources/inner.zip" in resource_names


def test_skill_name_collision_skips_zip(tmp_path: Path) -> None:
    """Test that zip with duplicate name is skipped."""
    # Create directory skill first
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: Foo
description: Directory skill
---
Content.
""",
        encoding="utf-8",
    )

    # Create zip skill with same name
    zip_path = tmp_path / "foo.zip"
    create_zip_skill(zip_path, name="Foo")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Only directory skill should be loaded
    assert len(registry.skills) == 1
    skill = registry.get("foo")
    assert not skill.is_zip
    assert skill.metadata.name == "Foo"


@pytest.mark.asyncio
async def test_zip_skill_instructions_read_correctly(tmp_path: Path) -> None:
    """Test that skill instructions are read correctly from zip."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(
            "SKILL.md",
            """---
name: TestInstructions
description: Test reading instructions
---
These are the skill instructions.

With multiple lines.
""",
        )

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    skill_tool = tools["testinstructions"]

    result = await skill_tool.fn(task="test task")

    assert "instructions" in result
    assert "These are the skill instructions." in result["instructions"]
    assert "With multiple lines." in result["instructions"]


def test_zip_skill_with_macos_metadata_filtered(tmp_path: Path) -> None:
    """Test that __MACOSX and .DS_Store files are filtered out."""
    zip_path = tmp_path / "mac-skill.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(
            "SKILL.md",
            """---
name: MacSkill
description: Skill with macOS metadata
---
Content.
""",
        )
        z.writestr("script.py", "print('hello')")
        z.writestr("__MACOSX/._script.py", b"\x00\x01\x02")  # macOS metadata
        z.writestr(".DS_Store", b"DS_Store content")  # macOS metadata

    registry = SkillRegistry(tmp_path)
    registry.load()

    skill = registry.get("macskill")

    from fastmcp import FastMCP
    from skillz._server import register_skill_resources

    mcp = FastMCP()
    metadata = register_skill_resources(mcp, skill)

    # Should only have script.py, not macOS metadata files
    assert len(metadata) == 1
    assert metadata[0]["name"] == "macskill/script.py"


@pytest.mark.asyncio
async def test_zip_path_traversal_rejected(tmp_path: Path) -> None:
    """Test that path traversal attempts are rejected."""
    zip_path = tmp_path / "test.zip"
    create_zip_skill(zip_path, name="TestSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    # Try path traversal
    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/../../../etc/passwd"
    )

    # Should return error
    assert "Error" in result["content"]
    assert "path traversal" in result["content"]


def test_mixed_directory_and_zip_skills(tmp_path: Path) -> None:
    """Test that both directory and zip skills can coexist."""
    # Create directory skill
    dir_skill = tmp_path / "dir-skill"
    dir_skill.mkdir()
    (dir_skill / "SKILL.md").write_text(
        """---
name: DirSkill
description: Directory skill
---
Dir content.
""",
        encoding="utf-8",
    )

    # Create zip skill
    zip_path = tmp_path / "zip-skill.zip"
    create_zip_skill(zip_path, name="ZipSkill")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Both should be loaded
    assert len(registry.skills) == 2

    dir_skill_obj = registry.get("dirskill")
    zip_skill_obj = registry.get("zipskill")

    assert not dir_skill_obj.is_zip
    assert zip_skill_obj.is_zip
    assert dir_skill_obj.metadata.name == "DirSkill"
    assert zip_skill_obj.metadata.name == "ZipSkill"


def test_zip_with_top_level_directory(tmp_path: Path) -> None:
    """Test zip with single top-level directory containing SKILL.md."""
    # Create a zip with structure: my-skill.zip/my-skill/SKILL.md
    zip_path = tmp_path / "my-skill.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(
            "my-skill/SKILL.md",
            """---
name: MySkill
description: Test skill in top-level dir
---
Instructions.
""",
        )
        z.writestr("my-skill/resource.txt", "Hello from nested structure!")
        z.writestr("my-skill/scripts/run.py", "print('test')")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Should be loaded
    assert len(registry.skills) == 1
    skill = registry.get("myskill")
    assert skill.metadata.name == "MySkill"
    assert skill.is_zip
    assert skill.zip_root_prefix == "my-skill/"


@pytest.mark.asyncio
async def test_zip_with_top_level_directory_resources(
    tmp_path: Path,
) -> None:
    """Test reading resources from zip with top-level directory."""
    zip_path = tmp_path / "test-skill.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(
            "test-skill/SKILL.md",
            """---
name: TestSkill
description: Test
---
Content.
""",
        )
        z.writestr("test-skill/data.txt", "Test data from nested structure")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskill/data.txt"
    )

    assert result["encoding"] == "utf-8"
    assert result["content"] == "Test data from nested structure"


def test_skill_extension_loads_like_zip(tmp_path: Path) -> None:
    """Test that files with .skill extension are loaded as zip files."""
    skill_path = tmp_path / "my-skill.skill"
    create_zip_skill(skill_path, name="SkillExtension")

    registry = SkillRegistry(tmp_path)
    registry.load()

    assert len(registry.skills) == 1
    skill = registry.get("skillextension")
    assert skill.metadata.name == "SkillExtension"
    assert skill.is_zip
    assert skill.zip_path == skill_path.resolve()


@pytest.mark.asyncio
async def test_skill_extension_resources_readable(tmp_path: Path) -> None:
    """Test that resources in .skill files can be read correctly."""
    skill_path = tmp_path / "test.skill"
    create_zip_skill(skill_path, name="TestSkillExt")

    registry = SkillRegistry(tmp_path)
    registry.load()

    server = build_server(registry)
    tools = await server.get_tools()
    fetch_tool = tools["fetch_resource"]

    result = await fetch_tool.fn(
        resource_uri="resource://skillz/testskillext/text/hello.txt"
    )

    assert result["uri"] == "resource://skillz/testskillext/text/hello.txt"
    assert result["content"] == "Hello from zip!"
    assert result["encoding"] == "utf-8"


def test_mixed_zip_and_skill_extensions(tmp_path: Path) -> None:
    """Test that both .zip and .skill files can coexist."""
    # Create a .zip file
    zip_path = tmp_path / "skill-one.zip"
    create_zip_skill(zip_path, name="SkillOne")

    # Create a .skill file
    skill_path = tmp_path / "skill-two.skill"
    create_zip_skill(skill_path, name="SkillTwo")

    registry = SkillRegistry(tmp_path)
    registry.load()

    # Both should be loaded
    assert len(registry.skills) == 2

    skill_one = registry.get("skillone")
    skill_two = registry.get("skilltwo")

    assert skill_one.metadata.name == "SkillOne"
    assert skill_two.metadata.name == "SkillTwo"
    assert skill_one.is_zip
    assert skill_two.is_zip
    assert skill_one.zip_path == zip_path.resolve()
    assert skill_two.zip_path == skill_path.resolve()
