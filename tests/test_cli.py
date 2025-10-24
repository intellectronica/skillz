from pathlib import Path

import pytest

from skillz import parse_args


def test_parse_args_defaults_to_home_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = Path("/tmp/fake-home")
    monkeypatch.setenv("HOME", str(fake_home))

    args = parse_args([])

    assert args.skills_root == fake_home / ".skillz"
    assert args.transport == "stdio"
    assert args.list_skills is False


def test_parse_args_custom_root(tmp_path: Path) -> None:
    args = parse_args([str(tmp_path)])

    assert args.skills_root == Path(tmp_path)
    assert args.transport == "stdio"
    assert args.list_skills is False


def test_parse_args_overrides(tmp_path: Path) -> None:
    args = parse_args(
        [
            str(tmp_path),
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--path",
            "/custom",
            "--list-skills",
        ]
    )

    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/custom"
    assert args.list_skills is True
