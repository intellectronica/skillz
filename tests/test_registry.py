from pathlib import Path

from skillz import SkillRegistry


def write_skill(directory: Path, name: str = "Echo") -> Path:
    skill_dir = directory / name.lower()
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: {name}
description: Test skill
---
Body
""".format(name=name),
        encoding="utf-8",
    )
    return skill_dir


def test_registry_discovers_skill(tmp_path: Path) -> None:
    write_skill(tmp_path, name="Echo")

    registry = SkillRegistry(tmp_path)
    registry.load()

    assert len(registry.skills) == 1
    skill = registry.get("echo")
    assert skill.metadata.name == "Echo"
    assert skill.instructions_path.name == "SKILL.md"
