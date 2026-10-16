from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from harnessprobe.ci import CommandResult
from harnessprobe.cli import main
from harnessprobe.comment import render_pr_comment
from harnessprobe.report import SubsetReport
from harnessprobe.scopefile import ScopeFile

VERSION_PATTERN = r"harnessprobe \d+\.\d+\.\d+\n"


def write_report(path: Path, report: SubsetReport) -> Path:
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path


def write_findings(path: Path) -> Path:
    path.write_text(
        '{"schema": "harnessprobe.findings/v1", "findings": ['
        '{"bug_class": "tool call dropped", "title": "t", "evidence": "e"}]}',
        encoding="utf-8",
    )
    return path


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
    assert scope_file.schema == "harnessprobe.scope/v2"
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
    entries = {entry.path: entry for entry in scope_file.files}
    assert entries["cli.py"].scope_kind == "whole-file"
    assert entries["cli.py"].lines is None
    assert entries["agent.py"].scope_kind == "pinned-lines"


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


def test_gate_pass_exit_0(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    code = main(["gate", "--report", str(report_path), "--min-coverage", "80"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe gate: passed\n"
    assert captured.err == ""


def test_gate_fail_exit_1_with_reasons(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    findings_path = write_findings(tmp_path / "findings.json")
    code = main(
        [
            "gate",
            "--report",
            str(report_path),
            "--findings",
            str(findings_path),
            "--min-coverage",
            "95",
            "--fail-on-findings",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == (
        "harnessprobe gate: failed\n"
        "- LDH coverage 81.82% is below min-coverage 95.00%\n"
        "- 1 bug findings attached (fail-on-findings)\n"
    )
    assert captured.err == ""


def test_gate_max_uncovered_failure_exits_1(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    code = main(["gate", "--report", str(report_path), "--max-uncovered", "1"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == (
        "harnessprobe gate: failed\n- 2 uncovered LDH lines exceed max-uncovered 1\n"
    )
    assert captured.err == ""


def test_gate_bad_report_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["gate", "--report", str(tmp_path / "nope.json")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_gate_bad_findings_exits_2(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    findings_path = tmp_path / "findings.json"
    findings_path.write_text("{}", encoding="utf-8")
    code = main(["gate", "--report", str(report_path), "--findings", str(findings_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")


@pytest.mark.parametrize("value", ["-5", "101"])
def test_gate_min_coverage_out_of_range_exits_2(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    code = main(["gate", "--report", str(report_path), "--min-coverage", value])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "error: --min-coverage must be between 0 and 100\n"


def test_gate_max_uncovered_out_of_range_exits_2(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    code = main(["gate", "--report", str(report_path), "--max-uncovered", "-1"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "error: --max-uncovered must be >= 0\n"


def test_gate_writes_summary_and_outputs(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    summary_out = tmp_path / "nested" / "summary.md"
    outputs = tmp_path / "outputs.txt"
    outputs.write_text("seed=1\n", encoding="utf-8")
    code = main(
        [
            "gate",
            "--report",
            str(report_path),
            "--min-coverage",
            "95",
            "--summary-out",
            str(summary_out),
            "--outputs",
            str(outputs),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == (
        "harnessprobe gate: failed\n"
        "- LDH coverage 81.82% is below min-coverage 95.00%\n"
    )
    assert captured.err == ""
    assert summary_out.read_text(encoding="utf-8") == (
        "## HarnessProbe gate: failed\n"
        "\n"
        "- LDH coverage: 81.82% (9/11 measured lines)\n"
        "- Uncovered LDH lines: 2\n"
        "- Findings attached: 0\n"
        "- Thresholds: min-coverage 95.00%\n"
        "\n"
        "### Failures\n"
        "\n"
        "- LDH coverage 81.82% is below min-coverage 95.00%\n"
    )
    assert outputs.read_text(encoding="utf-8") == (
        "seed=1\n"
        "covered-pct=81.82\n"
        "scope-lines=11\n"
        "executed=9\n"
        "uncovered=2\n"
        "not-measured=8\n"
        "findings-count=0\n"
        "gate-passed=false\n"
        "gate-reasons=LDH coverage 81.82% is below min-coverage 95.00%\n"
    )


def test_gate_summary_write_failure_exits_2(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    summary_out = tmp_path / "as_dir"
    summary_out.mkdir()
    code = main(["gate", "--report", str(report_path), "--summary-out", str(summary_out)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: cannot write ")
    assert str(summary_out) in captured.err


def test_gate_outputs_write_failure_exits_2(
    mini_report: SubsetReport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    outputs_dir = tmp_path / "outs"
    outputs_dir.mkdir()
    code = main(["gate", "--report", str(report_path), "--outputs", str(outputs_dir)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: cannot write ")


def test_post_dry_run_prints_and_skips_gh(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)

    def explode(argv: Sequence[str]) -> CommandResult:
        raise AssertionError("dry-run must not call gh")

    monkeypatch.setattr("harnessprobe.ci._run_gh", explode)
    code = main(
        ["post", "--report", str(report_path), "--pr", "12", "--repo", "o/r", "--dry-run"]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: dry-run (would post to o/r#12)\n"
    assert captured.err == ""


def test_post_dry_run_writes_comment_out(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    comment_out = tmp_path / "comment.md"

    def explode(argv: Sequence[str]) -> CommandResult:
        raise AssertionError("dry-run must not call gh")

    monkeypatch.setattr("harnessprobe.ci._run_gh", explode)
    code = main(
        [
            "post",
            "--report",
            str(report_path),
            "--pr",
            "12",
            "--repo",
            "o/r",
            "--comment-out",
            str(comment_out),
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: dry-run (would post to o/r#12)\n"
    assert comment_out.read_text(encoding="utf-8") == render_pr_comment(mini_report)


def test_post_dry_run_uses_environment_repo(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    monkeypatch.setenv("GITHUB_REPOSITORY", "env/repo")
    code = main(["post", "--report", str(report_path), "--pr", "9", "--dry-run"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: dry-run (would post to env/repo#9)\n"
    assert captured.err == ""


def test_post_creates_comment_via_gh(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    findings_path = write_findings(tmp_path / "findings.json")
    previous_path = write_report(tmp_path / "previous.json", mini_report)
    calls: list[list[str]] = []

    def fake_run(argv: Sequence[str]) -> CommandResult:
        calls.append(list(argv))
        if len(calls) == 1:
            return CommandResult(0, "[]", "")
        return CommandResult(0, '{"id": 4, "html_url": "https://example.test/c/4"}', "")

    monkeypatch.setattr("harnessprobe.ci._run_gh", fake_run)
    code = main(
        [
            "post",
            "--report",
            str(report_path),
            "--findings",
            str(findings_path),
            "--previous",
            str(previous_path),
            "--pr",
            "12",
            "--repo",
            "o/r",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: created comment https://example.test/c/4\n"
    assert captured.err == ""
    assert calls[0] == ["gh", "api", "--paginate", "repos/o/r/issues/12/comments?per_page=100"]
    assert calls[1][:3] == ["gh", "api", "repos/o/r/issues/12/comments"]
    assert calls[1][3] == "-F"
    assert calls[1][4].startswith("body=@")


def test_post_updates_comment_and_prints_without_url(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    page = json.dumps(
        [
            {
                "id": 8,
                "body": "_harnessprobe · report harnessprobe.report/v1_",
                "user": {"login": "github-actions[bot]"},
            }
        ]
    )

    def fake_run(argv: Sequence[str]) -> CommandResult:
        if argv[2] == "--paginate":
            return CommandResult(0, page, "")
        return CommandResult(0, "{}", "")

    monkeypatch.setattr("harnessprobe.ci._run_gh", fake_run)
    code = main(["post", "--report", str(report_path), "--pr", "12", "--repo", "o/r"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: updated comment\n"
    assert captured.err == ""


def test_post_comment_author_flag_selects_comment(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    page = json.dumps(
        [
            {
                "id": 21,
                "body": "_harnessprobe · report harnessprobe.report/v1_",
                "user": {"login": "ci-bot"},
            }
        ]
    )

    def fake_run(argv: Sequence[str]) -> CommandResult:
        if argv[2] == "--paginate":
            return CommandResult(0, page, "")
        return CommandResult(0, "{}", "")

    monkeypatch.setattr("harnessprobe.ci._run_gh", fake_run)
    code = main(
        [
            "post",
            "--report",
            str(report_path),
            "--pr",
            "12",
            "--repo",
            "o/r",
            "--comment-author",
            "ci-bot",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "harnessprobe post: updated comment\n"


def test_post_gh_failure_exits_1(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)

    def fake_run(argv: Sequence[str]) -> CommandResult:
        return CommandResult(1, "", "boom")

    monkeypatch.setattr("harnessprobe.ci._run_gh", fake_run)
    code = main(["post", "--report", str(report_path), "--pr", "12", "--repo", "o/r"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == "error: gh failed: boom\n"


def test_post_missing_repo_exits_1(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    code = main(["post", "--report", str(report_path), "--pr", "12"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == "error: no repository given (use --repo or GITHUB_REPOSITORY)\n"


def test_post_bad_report_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    code = main(["post", "--report", str(tmp_path / "nope.json"), "--pr", "12"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_post_comment_out_write_failure_exits_1(
    mini_report: SubsetReport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = write_report(tmp_path / "report.json", mini_report)
    comment_out = tmp_path / "as_dir"
    comment_out.mkdir()

    def explode(argv: Sequence[str]) -> CommandResult:
        raise AssertionError("dry-run must not call gh")

    monkeypatch.setattr("harnessprobe.ci._run_gh", explode)
    code = main(
        [
            "post",
            "--report",
            str(report_path),
            "--pr",
            "12",
            "--repo",
            "o/r",
            "--comment-out",
            str(comment_out),
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: cannot write ")
