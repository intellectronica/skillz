from pathlib import Path

import pytest

from skillz._server import SkillRegistry, run_script


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
