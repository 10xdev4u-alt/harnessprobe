from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harnessprobe.cli import main
from harnessprobe.scopefile import ScopeFile

VERSION_PATTERN = r"harnessprobe \d+\.\d+\.\d+\n"


def test_init_writes_scope_file_and_prints_summary(
    fixtures_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixtures_root / "mini_repo"
    out = tmp_path / "scope.json"
    code = main(["init", str(repo), "--out", str(out)])
    captured = capsys.readouterr()
    expected = (
        f"HarnessProbe scope for {repo.resolve()} (tier B: on)\n"
        "sources: 1 model-call sites, 3 annotation sites\n"
        "candidates: 5 files, 19 lines\n"
        "confidence: authoritative=2, allowlisted=0, heuristic-high=3, heuristic-low=0\n"
        "note: annotations are user-declared; treated as authoritative\n"
        "note: tier A: model-call and same-function consumer statements (heuristic)\n"
        f"wrote {out.resolve()}\n"
    )
    assert code == 0
    assert captured.out == expected
    assert captured.err == ""
    scope_file = ScopeFile.from_json(out.read_text(encoding="utf-8"))
    assert scope_file.schema == "harnessprobe.scope/v1"
    assert scope_file.generated_by == "harnessprobe"
    assert [entry.path for entry in scope_file.files] == [
        "agent.py",
        "dispatch.py",
        "parsing.py",
        "text_tools.py",
        "unrelated.py",
    ]


def test_init_no_tier_b_changes_summary_and_file(
    fixtures_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixtures_root / "mini_repo"
    out = tmp_path / "scope.json"
    code = main(["init", str(repo), "--no-tier-b", "--out", str(out)])
    captured = capsys.readouterr()
    expected = (
        f"HarnessProbe scope for {repo.resolve()} (tier B: off)\n"
        "sources: 1 model-call sites, 3 annotation sites\n"
        "candidates: 5 files, 18 lines\n"
        "confidence: authoritative=2, allowlisted=0, heuristic-high=3, heuristic-low=0\n"
        "note: annotations are user-declared; treated as authoritative\n"
        "note: tier A: model-call and same-function consumer statements (heuristic)\n"
        "note: tier B reachability disabled (--no-tier-b)\n"
        f"wrote {out.resolve()}\n"
    )
    assert code == 0
    assert captured.out == expected
    scope_file = ScopeFile.from_json(out.read_text(encoding="utf-8"))
    assert scope_file.include_tier_b is False
    entries = {entry.path: entry for entry in scope_file.files}
    assert entries["dispatch.py"].lines == [7]


def test_init_default_out_lands_in_repo(
    fixtures_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(fixtures_root / "mini_repo", repo)
    code = main(["init", str(repo)])
    captured = capsys.readouterr()
    out = repo / "harnessprobe.scope.json"
    assert code == 0
    assert captured.out.endswith(f"wrote {out.resolve()}\n")
    assert ScopeFile.from_json(out.read_text(encoding="utf-8")).files


def test_init_allowlist_flags_echo_and_scope(
    fixtures_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixtures_root / "mini_repo"
    out = tmp_path / "scope.json"
    code = main(
        [
            "init",
            str(repo),
            "--allowlist",
            "cli.py",
            "--allowlist",
            "parsing.py",
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "candidates: 6 files, 32 lines\n" in captured.out
    assert "confidence: authoritative=2, allowlisted=2, heuristic-high=2, heuristic-low=0\n" in (
        captured.out
    )
    assert "note: allowlisted files are scoped whole by user declaration\n" in captured.out
    scope_file = ScopeFile.from_json(out.read_text(encoding="utf-8"))
    assert scope_file.allowlist == ["cli.py", "parsing.py"]


def test_init_missing_path_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope"
    code = main(["init", str(missing)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "nope" in captured.err


def test_init_file_path_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "file.py"
    target.write_text("x = 1\n")
    code = main(["init", str(target)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_init_write_failure_errors(
    fixtures_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "as_dir"
    out_dir.mkdir()
    code = main(["init", str(fixtures_root / "mini_repo"), "--out", str(out_dir)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error: ")
    assert str(out_dir) in captured.err


def test_init_syntax_error_warns_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "broken.py").write_text("def f(:\n")
    (repo / "good.py").write_text("def f(x):\n    return x\n")
    out = tmp_path / "scope.json"
    code = main(["init", str(repo), "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err.startswith("warning: ")
    assert "broken.py" in captured.err
    scope_file = ScopeFile.from_json(out.read_text(encoding="utf-8"))
    assert len(scope_file.warnings) == 1


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert re.fullmatch(VERSION_PATTERN, capsys.readouterr().out)


def test_unknown_flag_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["init", "--bogus"])
    assert excinfo.value.code == 2


def test_module_version_via_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "harnessprobe", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert re.fullmatch(VERSION_PATTERN, result.stdout)
