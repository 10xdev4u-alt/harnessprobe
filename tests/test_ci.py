from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from harnessprobe.ci import (
    STICKY_MARKER,
    CommandResult,
    GateThresholds,
    GhRunner,
    PostOutcome,
    _run_gh,
    evaluate_gate,
    is_sticky_body,
    post_sticky_comment,
    write_outputs,
)
from harnessprobe.report import SubsetReport, SubsetTotals

STICKY_BODY = "_harnessprobe · report harnessprobe.report/v1_"


def empty_scope_report() -> SubsetReport:
    return SubsetReport(
        schema="harnessprobe.report/v1",
        totals=SubsetTotals(
            scope_lines=0,
            not_measured=5,
            executed=0,
            covered_pct=None,
            branches_full=0,
            branches_partial=0,
            branches_missing=0,
        ),
        files=[],
    )


def make_runner(results: list[CommandResult]) -> tuple[list[list[str]], GhRunner]:
    calls: list[list[str]] = []

    def run(argv: Sequence[str]) -> CommandResult:
        calls.append(list(argv))
        return results.pop(0)

    return calls, run


def body_file(tmp_path: Path) -> Path:
    body_path = tmp_path / "body.md"
    body_path.write_text("body\n", encoding="utf-8")
    return body_path


def test_sticky_marker_matches_renderer_footer() -> None:
    assert STICKY_MARKER == "_harnessprobe · report "


def test_gate_passes_without_thresholds(mini_report: SubsetReport) -> None:
    result = evaluate_gate(mini_report, findings_count=0, thresholds=GateThresholds())
    assert result.passed is True
    assert result.reasons == ()
    assert result.outputs == {
        "covered-pct": "81.82",
        "scope-lines": "11",
        "executed": "9",
        "uncovered": "2",
        "not-measured": "8",
        "findings-count": "0",
        "gate-passed": "true",
        "gate-reasons": "",
    }
    assert result.summary == (
        "## HarnessProbe gate: passed\n"
        "\n"
        "- LDH coverage: 81.82% (9/11 measured lines)\n"
        "- Uncovered LDH lines: 2\n"
        "- Findings attached: 0\n"
        "- Thresholds: none configured\n"
    )
    assert not result.summary.endswith("\n\n")


def test_gate_fails_min_coverage_without_measured_lines() -> None:
    result = evaluate_gate(
        empty_scope_report(), findings_count=0, thresholds=GateThresholds(min_coverage=80.0)
    )
    assert result.passed is False
    assert result.reasons == ("no measured LDH scope lines; min-coverage cannot be checked",)
    assert result.outputs["covered-pct"] == ""
    assert "- LDH coverage: n/a (0/0 measured lines)\n" in result.summary


def test_gate_min_coverage_below_fails(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=0, thresholds=GateThresholds(min_coverage=95.0)
    )
    assert result.passed is False
    assert result.reasons == ("LDH coverage 81.82% is below min-coverage 95.00%",)


def test_gate_min_coverage_boundary_passes(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=0, thresholds=GateThresholds(min_coverage=81.82)
    )
    assert result.passed is True


def test_gate_max_uncovered_boundary_passes(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=0, thresholds=GateThresholds(max_uncovered=2)
    )
    assert result.passed is True


def test_gate_max_uncovered_one_over_fails(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=0, thresholds=GateThresholds(max_uncovered=1)
    )
    assert result.passed is False
    assert result.reasons == ("2 uncovered LDH lines exceed max-uncovered 1",)


def test_gate_fail_on_findings_zero_passes(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=0, thresholds=GateThresholds(fail_on_findings=True)
    )
    assert result.passed is True


def test_gate_fail_on_findings_fails(mini_report: SubsetReport) -> None:
    result = evaluate_gate(
        mini_report, findings_count=1, thresholds=GateThresholds(fail_on_findings=True)
    )
    assert result.passed is False
    assert result.reasons == ("1 bug findings attached (fail-on-findings)",)


def test_gate_reasons_accumulate_in_fixed_order(mini_report: SubsetReport) -> None:
    thresholds = GateThresholds(min_coverage=95.0, max_uncovered=1, fail_on_findings=True)
    result = evaluate_gate(mini_report, findings_count=2, thresholds=thresholds)
    assert result.passed is False
    assert result.reasons == (
        "LDH coverage 81.82% is below min-coverage 95.00%",
        "2 uncovered LDH lines exceed max-uncovered 1",
        "2 bug findings attached (fail-on-findings)",
    )


def test_gate_failed_outputs_and_summary(mini_report: SubsetReport) -> None:
    thresholds = GateThresholds(min_coverage=90.0, fail_on_findings=True)
    result = evaluate_gate(mini_report, findings_count=1, thresholds=thresholds)
    assert result.passed is False
    assert result.outputs == {
        "covered-pct": "81.82",
        "scope-lines": "11",
        "executed": "9",
        "uncovered": "2",
        "not-measured": "8",
        "findings-count": "1",
        "gate-passed": "false",
        "gate-reasons": (
            "LDH coverage 81.82% is below min-coverage 90.00%; "
            "1 bug findings attached (fail-on-findings)"
        ),
    }
    assert result.summary == (
        "## HarnessProbe gate: failed\n"
        "\n"
        "- LDH coverage: 81.82% (9/11 measured lines)\n"
        "- Uncovered LDH lines: 2\n"
        "- Findings attached: 1\n"
        "- Thresholds: min-coverage 90.00%, fail-on-findings on\n"
        "\n"
        "### Failures\n"
        "\n"
        "- LDH coverage 81.82% is below min-coverage 90.00%\n"
        "- 1 bug findings attached (fail-on-findings)\n"
    )


def test_gate_summary_lists_each_configured_threshold(mini_report: SubsetReport) -> None:
    thresholds = GateThresholds(min_coverage=50.0, max_uncovered=5)
    result = evaluate_gate(mini_report, findings_count=0, thresholds=thresholds)
    assert result.passed is True
    assert "- Thresholds: min-coverage 50.00%, max-uncovered 5\n" in result.summary


def test_write_outputs_appends_preserving_existing(tmp_path: Path) -> None:
    path = tmp_path / "outputs.txt"
    path.write_text("existing=1\n", encoding="utf-8")
    write_outputs(path, {"a": "1", "b": "2"})
    assert path.read_text(encoding="utf-8") == "existing=1\na=1\nb=2\n"


def test_write_outputs_preserves_mapping_order(tmp_path: Path) -> None:
    path = tmp_path / "outputs.txt"
    write_outputs(path, {"z": "1", "a": "2", "m": "3"})
    assert path.read_text(encoding="utf-8") == "z=1\na=2\nm=3\n"


@pytest.mark.parametrize(
    ("outputs", "message"),
    [
        ({"": "v"}, "empty"),
        ({"bad=key": "v"}, "'='"),
        ({"bad\nkey": "v"}, "newline"),
        ({"key": "bad\nvalue"}, "newline"),
    ],
)
def test_write_outputs_rejects_invalid_entries(
    tmp_path: Path, outputs: dict[str, str], message: str
) -> None:
    path = tmp_path / "outputs.txt"
    with pytest.raises(ValueError, match=message):
        write_outputs(path, outputs)
    assert not path.exists()


def test_is_sticky_body_accepts_renderer_footer() -> None:
    assert is_sticky_body(f"hello\n\n{STICKY_BODY}\n") is True


def test_is_sticky_body_rejects_unrelated_body() -> None:
    assert is_sticky_body("### HarnessProbe: no bug classes caught\n") is False


def test_is_sticky_body_rejects_prefix_only() -> None:
    assert is_sticky_body("_harnessprobe · ") is False


def test_post_sticky_comment_creates_when_missing(tmp_path: Path) -> None:
    body_path = body_file(tmp_path)
    calls, runner = make_runner(
        [
            CommandResult(0, "[]", ""),
            CommandResult(0, '{"id": 7, "html_url": "https://example.test/c/7"}', ""),
        ]
    )
    outcome = post_sticky_comment(repo="o/r", pr_number=5, body_path=body_path, runner=runner)
    assert calls == [
        ["gh", "api", "--paginate", "repos/o/r/issues/5/comments?per_page=100"],
        ["gh", "api", "repos/o/r/issues/5/comments", "-F", f"body=@{body_path}"],
    ]
    assert outcome == PostOutcome("created", 7, "https://example.test/c/7")


def test_post_sticky_comment_updates_existing(tmp_path: Path) -> None:
    body_path = body_file(tmp_path)
    page = json.dumps([{"id": 1, "body": "other"}, {"id": 2, "body": STICKY_BODY}])
    calls, runner = make_runner(
        [
            CommandResult(0, page, ""),
            CommandResult(0, '{"id": 2, "html_url": "https://example.test/c/2"}', ""),
        ]
    )
    outcome = post_sticky_comment(repo="o/r", pr_number=5, body_path=body_path, runner=runner)
    assert calls[1] == [
        "gh",
        "api",
        "-X",
        "PATCH",
        "repos/o/r/issues/comments/2",
        "-F",
        f"body=@{body_path}",
    ]
    assert outcome == PostOutcome("updated", 2, "https://example.test/c/2")


def test_post_sticky_comment_updates_latest_match(tmp_path: Path) -> None:
    body_path = body_file(tmp_path)
    page = json.dumps([{"id": 10, "body": STICKY_BODY}, {"id": 11, "body": STICKY_BODY}])
    calls, runner = make_runner([CommandResult(0, page, ""), CommandResult(0, "{}", "")])
    outcome = post_sticky_comment(repo="o/r", pr_number=5, body_path=body_path, runner=runner)
    assert calls[1][4] == "repos/o/r/issues/comments/11"
    assert outcome == PostOutcome("updated", None, None)


def test_post_sticky_comment_parses_concatenated_pages(tmp_path: Path) -> None:
    body_path = body_file(tmp_path)
    page_one = json.dumps([{"id": 1, "body": "other"}])
    page_two = json.dumps([{"id": 2, "body": STICKY_BODY}])
    calls, runner = make_runner(
        [
            CommandResult(0, f"{page_one}\n{page_two}\n", ""),
            CommandResult(0, "{}", ""),
        ]
    )
    outcome = post_sticky_comment(repo="o/r", pr_number=5, body_path=body_path, runner=runner)
    assert calls[1][4] == "repos/o/r/issues/comments/2"
    assert outcome.action == "updated"


def test_post_sticky_comment_parses_missing_response_fields(tmp_path: Path) -> None:
    body_path = body_file(tmp_path)
    _, runner = make_runner([CommandResult(0, "[]", ""), CommandResult(0, "{}", "")])
    outcome = post_sticky_comment(repo="o/r", pr_number=5, body_path=body_path, runner=runner)
    assert outcome == PostOutcome("created", None, None)


def test_post_sticky_comment_raises_on_gh_failure(tmp_path: Path) -> None:
    _, runner = make_runner([CommandResult(1, "", "boom")])
    with pytest.raises(ValueError, match="gh failed: boom"):
        post_sticky_comment(repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner)


def test_post_sticky_comment_raises_on_update_failure(tmp_path: Path) -> None:
    _, runner = make_runner([CommandResult(0, "[]", ""), CommandResult(2, "", "nope")])
    with pytest.raises(ValueError, match="gh failed: nope"):
        post_sticky_comment(repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner)


def test_post_sticky_comment_failure_without_stderr(tmp_path: Path) -> None:
    _, runner = make_runner([CommandResult(1, "", "")])
    with pytest.raises(ValueError, match="gh failed: gh api"):
        post_sticky_comment(repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner)


@pytest.mark.parametrize("stdout", ["not json", "[] [", '{"id": 1, "body": "x"}'])
def test_post_sticky_comment_rejects_malformed_list(tmp_path: Path, stdout: str) -> None:
    _, runner = make_runner([CommandResult(0, stdout, "")])
    with pytest.raises(ValueError, match="cannot parse gh comment list output"):
        post_sticky_comment(repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner)


@pytest.mark.parametrize("stdout", ["nope", "[]"])
def test_post_sticky_comment_rejects_unparsable_response(tmp_path: Path, stdout: str) -> None:
    _, runner = make_runner([CommandResult(0, "[]", ""), CommandResult(0, stdout, "")])
    with pytest.raises(ValueError, match="cannot parse gh comment response"):
        post_sticky_comment(repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner)


def test_post_sticky_comment_dry_run_skips_runner(tmp_path: Path) -> None:
    def runner(argv: Sequence[str]) -> CommandResult:
        raise AssertionError("dry-run must not call gh")

    outcome = post_sticky_comment(
        repo="o/r", pr_number=5, body_path=body_file(tmp_path), runner=runner, dry_run=True
    )
    assert outcome == PostOutcome("dry-run", None, None)


def test_run_gh_captures_process_result() -> None:
    script = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    result = _run_gh([sys.executable, "-c", script])
    assert result.returncode == 3
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
