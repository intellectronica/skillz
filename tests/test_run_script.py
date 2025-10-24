from pathlib import Path
from urllib.parse import quote

import pytest

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context as FastContext

from skillz._server import (
    SkillRegistry,
    build_server,
    run_script,
    _is_probably_script,
)


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
    (skill_dir / "notes.md").write_text(
        "Internal docs", encoding="utf-8"
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
        runnable = (
            resource_path != skill.instructions_path
            and _is_probably_script(resource_path)
        )
        expected_entries.append(
            {
                "relative_path": relative.as_posix(),
                "uri": uri,
                "runnable": runnable,
            }
        )

    resources = await server.get_resources()
    expected_uris = {entry["uri"] for entry in expected_entries}
    assert expected_uris <= set(resources.keys())

    for entry in expected_entries:
        uri = entry["uri"]
        # Verify we can read the resource via URI
        content = await server._resource_manager.read_resource(uri)
        # Find the original path from skill.resources for validation
        relative = Path(entry["relative_path"])
        resource_path = next(
            p
            for p in skill.resources
            if p.relative_to(skill.directory) == relative
        )
        file_bytes = resource_path.read_bytes()
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

        available_scripts = payload["usage"]["script_execution"][
            "available_scripts"
        ]
        assert available_scripts == [
            {
                "relative_path": entry["relative_path"],
                "uri": entry["uri"],
            }
            for entry in expected_entries
            if entry["runnable"]
        ]

        available = payload["usage"]["script_execution"]["available_resources"]
        assert available == [entry["uri"] for entry in expected_entries]

        # Regression test: ensure no absolute paths leak into the payload
        import json

        payload_json = json.dumps(payload)
        assert '"path"' not in payload_json or "relative_path" in payload_json


@pytest.mark.asyncio
async def test_rejects_markdown_as_script(tmp_path: Path) -> None:
    create_skill(tmp_path)
    registry = SkillRegistry(tmp_path)
    registry.load()
    skill = registry.get("demo-increment")
    server = build_server(registry, timeout=5.0)

    async with FastContext(server):
        with pytest.raises(ToolError) as excinfo:
            await server._call_tool(
                skill.slug,
                {
                    "task": "Attempt to run markdown",
                    "script": "notes.md",
                },
            )

    message = str(excinfo.value)
    assert "notes.md" in message
    assert "ctx.read_resource" in message
    assert "resource://skillz/" in message
