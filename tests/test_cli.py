from pathlib import Path

from skillz import parse_args


def test_parse_args_defaults(tmp_path: Path) -> None:
    args = parse_args([str(tmp_path)])

    assert args.skills_root == Path(tmp_path)
    assert args.timeout == 60.0
    assert args.transport == "stdio"
    assert args.list_skills is False


def test_parse_args_overrides(tmp_path: Path) -> None:
    args = parse_args(
        [
            str(tmp_path),
            "--timeout",
            "5",
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

    assert args.timeout == 5.0
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/custom"
    assert args.list_skills is True
