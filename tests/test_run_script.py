from pathlib import Path
from urllib.parse import quote

import pytest

from fastmcp.server.context import Context as FastContext

from skillz._server import SkillRegistry, build_server, run_script


def create_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "demo-increment"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: Demo Increment
description: Adds numbers
---
Body
""",
        encoding="utf-8",
    )
    (skill_dir / "adder.py").write_text(
        """import sys

if __name__ == \"__main__\":
    total = sum(int(part) for part in sys.argv[1:])
    print(total)
""",
        encoding="utf-8",
    )
    return skill_dir


@pytest.mark.asyncio
async def test_run_script_executes(tmp_path: Path) -> None:
    create_skill(tmp_path)
    registry = SkillRegistry(tmp_path)
    registry.load()
    skill = registry.get("demo-increment")

    result = await run_script(
        skill,
        "adder.py",
        {"args": ["1", "2", "3"]},
        timeout=5.0,
    )

    assert result["returncode"] == 0
    assert result["stdout"]["content"].strip() == "6"
    assert result["stderr"]["content"].strip() == ""


@pytest.mark.asyncio
async def test_registers_skill_resources(tmp_path: Path) -> None:
    create_skill(tmp_path)
    registry = SkillRegistry(tmp_path)
    registry.load()
    skill = registry.get("demo-increment")

    server = build_server(registry, timeout=5.0)

    expected_entries = []
    for resource_path in skill.resources:
        relative = resource_path.relative_to(skill.directory)
        encoded_slug = quote(skill.slug, safe="")
        encoded_parts = [quote(part, safe="") for part in relative.parts]
        suffix = "/".join(encoded_parts)
        uri = (
            f"resource://skillz/{encoded_slug}/{suffix}"
            if suffix
            else f"resource://skillz/{encoded_slug}"
        )
        expected_entries.append(
            {
                "path": str(resource_path),
                "relative_path": relative.as_posix(),
                "uri": uri,
            }
        )

    resources = await server.get_resources()
    expected_uris = {entry["uri"] for entry in expected_entries}
    assert expected_uris <= set(resources.keys())

    for entry in expected_entries:
        uri = entry["uri"]
        path = Path(entry["path"])
        content = await server._resource_manager.read_resource(uri)
        file_bytes = path.read_bytes()
        try:
            file_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            assert isinstance(content, bytes)
            assert content == file_bytes
        else:
            assert isinstance(content, str)
            assert content == file_text

    async with FastContext(server):
        result = await server._call_tool(
            skill.slug, {"task": "Inspect registered resources"}
        )
        payload = result.structured_content
        assert isinstance(payload, dict)
        assert payload["resources"] == expected_entries

        available = payload["usage"]["script_execution"]["available_resources"]
        assert available[: len(expected_entries)] == [
            entry["uri"] for entry in expected_entries
        ]
        assert available[len(expected_entries) :] == [
            entry["path"] for entry in expected_entries
        ]
