from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harnessprobe.cli import main
from harnessprobe.comment import BugFinding, Findings, load_findings, render_pr_comment
from harnessprobe.report import FileSubsetReport, SubsetReport, SubsetTotals, UncoveredSample

FINDINGS = [
    BugFinding(
        bug_class="tool call dropped",
        title="Tool call silently dropped on partial stream",
        evidence="https://github.com/10xdev4u-alt/harnessprobe/issues/101",
        location="browser_use/agent/service.py:412",
    ),
    BugFinding(
        bug_class="secret leaked in saved history",
        title="API key written into saved history file",
        evidence="docs/research/03-bug-classes.md",
        location="browser_use/agent/message_manager/service.py:88",
    ),
    BugFinding(
        bug_class="tool call dropped",
        title="Second tool call in one message ignored",
        evidence="https://github.com/10xdev4u-alt/harnessprobe/issues/102",
    ),
]

MINI_FILES = [
    FileSubsetReport(
        path="mini_repo/agent.py",
        scope_lines=3,
        not_measured=0,
        executed=2,
        covered_pct=66.67,
        branches_full=0,
        branches_partial=1,
        branches_missing=0,
        samples=[
            UncoveredSample(
                path="mini_repo/agent.py",
                line=21,
                text="return response.choices[0].message.content",
            ),
            UncoveredSample(path="mini_repo/agent.py", line=34, text=None),
        ],
    ),
    FileSubsetReport(
        path="mini_repo/parsing.py",
        scope_lines=6,
        not_measured=0,
        executed=5,
        covered_pct=83.33,
        branches_full=0,
        branches_partial=0,
        branches_missing=1,
        samples=[UncoveredSample(path="mini_repo/parsing.py", line=6, text="if not tool_calls:")],
    ),
    FileSubsetReport(
        path="mini_repo/dispatch.py",
        scope_lines=2,
        not_measured=0,
        executed=2,
        covered_pct=100.0,
        branches_full=1,
        branches_partial=0,
        branches_missing=0,
        samples=[],
    ),
]


def make_report(
    *, covered_pct: float | None = 81.82, files: list[FileSubsetReport] | None = None
) -> SubsetReport:
    return SubsetReport(
        schema="harnessprobe.report/v1",
        totals=SubsetTotals(
            scope_lines=11,
            not_measured=8,
            executed=9,
            covered_pct=covered_pct,
            branches_full=1,
            branches_partial=1,
            branches_missing=1,
        ),
        files=MINI_FILES if files is None else files,
    )


def file_report(path: str, samples: list[UncoveredSample]) -> FileSubsetReport:
    return FileSubsetReport(
        path=path,
        scope_lines=len(samples),
        not_measured=0,
        executed=0,
        covered_pct=0.0,
        branches_full=0,
        branches_partial=0,
        branches_missing=0,
        samples=samples,
    )


def write_json(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def golden(fixtures_root: Path, name: str) -> str:
    return (fixtures_root / "comment" / name).read_text(encoding="utf-8")


def test_comment_with_findings_matches_golden(fixtures_root: Path) -> None:
    comment = render_pr_comment(
        make_report(), findings=FINDINGS, previous=make_report(covered_pct=79.72)
    )
    assert comment == golden(fixtures_root, "expected_comment_full.md")


def test_comment_report_only_matches_golden(fixtures_root: Path) -> None:
    assert render_pr_comment(make_report()) == golden(
        fixtures_root, "expected_comment_report_only.md"
    )


def test_bug_classes_lead_coverage() -> None:
    comment = render_pr_comment(make_report(), findings=FINDINGS)
    assert comment.index("### HarnessProbe: 2 bug classes caught (3 findings)") < comment.index(
        "### LDH coverage"
    )
    assert comment.index("### LDH coverage") < comment.index("<details>")


def test_single_finding_heading_is_singular() -> None:
    comment = render_pr_comment(make_report(), findings=[FINDINGS[0]])
    assert "### HarnessProbe: 1 bug class caught (1 finding)" in comment


def test_no_findings_uses_honest_placeholder() -> None:
    comment = render_pr_comment(make_report())
    assert "### HarnessProbe: no bug classes caught" in comment
    assert (
        "No findings were attached to this run. HarnessProbe v1 ships LDH coverage "
        "subsetting; differential bug detection lands in later phases." in comment
    )


@pytest.mark.parametrize(
    ("current_pct", "previous_pct", "rendered"),
    [
        (81.82, 79.72, "+2.10pp"),
        (81.82, 83.92, "-2.10pp"),
        (81.824, 81.82, "no change"),
        (81.82, None, "no comparable previous value"),
        (None, 81.82, "no comparable previous value"),
    ],
)
def test_delta_rendering(
    current_pct: float | None, previous_pct: float | None, rendered: str
) -> None:
    comment = render_pr_comment(
        make_report(covered_pct=current_pct), previous=make_report(covered_pct=previous_pct)
    )
    assert f" — **{rendered}** vs previous report\n" in comment


def test_no_previous_omits_delta() -> None:
    assert "vs previous report" not in render_pr_comment(make_report())


def test_classes_ordered_by_count_then_name() -> None:
    findings = [
        BugFinding(bug_class="b class", title="b one", evidence="e-b"),
        BugFinding(bug_class="a class", title="a one", evidence="e-a"),
        BugFinding(bug_class="c class", title="c one", evidence="e-c"),
        BugFinding(bug_class="c class", title="c two", evidence="e-c"),
    ]
    comment = render_pr_comment(make_report(), findings=findings)
    assert comment.index("- **c class** (2)") < comment.index("- **a class** (1)")
    assert comment.index("- **a class** (1)") < comment.index("- **b class** (1)")


def test_findings_keep_input_order_within_class() -> None:
    findings = [
        BugFinding(bug_class="tool call dropped", title="zebra drop", evidence="e1"),
        BugFinding(bug_class="tool call dropped", title="apple drop", evidence="e2"),
    ]
    comment = render_pr_comment(make_report(), findings=findings)
    assert comment.index("zebra drop") < comment.index("apple drop")


def test_details_block_omitted_without_samples() -> None:
    comment = render_pr_comment(make_report(files=[]))
    assert "<details>" not in comment
    assert "</details>" not in comment


def test_details_block_caps_at_eight_samples() -> None:
    samples = [
        UncoveredSample(path="mini_repo/agent.py", line=line, text=None) for line in range(1, 13)
    ]
    comment = render_pr_comment(make_report(files=[file_report("mini_repo/agent.py", samples)]))
    assert comment.count("- `mini_repo/agent.py:") == 8


def test_comment_is_deterministic_and_tidy() -> None:
    args = (make_report(),)
    kwargs = {"findings": FINDINGS, "previous": make_report(covered_pct=79.72)}
    first = render_pr_comment(*args, **kwargs)
    assert render_pr_comment(*args, **kwargs) == first
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert first.endswith("_harnessprobe · report harnessprobe.report/v1_\n")
    assert all(not line.endswith(" ") for line in first.splitlines())


def test_findings_json_round_trip() -> None:
    findings = Findings(schema="harnessprobe.findings/v1", findings=FINDINGS)
    assert Findings.from_json(findings.to_json(indent=2)) == findings


def test_findings_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Findings.from_json('{"schema": "harnessprobe.findings/v1", "findings": [], "extra": 1}')
    with pytest.raises(ValidationError):
        BugFinding(bug_class="x", title="t", evidence="e", unexpected=True)


def test_load_findings_reads_file(tmp_path: Path) -> None:
    payload = Findings(schema="harnessprobe.findings/v1", findings=FINDINGS).to_json(indent=2)
    path = write_json(tmp_path / "findings.json", payload + "\n")
    assert load_findings(path) == FINDINGS


def test_load_findings_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot read findings file"):
        load_findings(tmp_path / "nope.json")


def test_load_findings_bad_json_raises(tmp_path: Path) -> None:
    path = write_json(tmp_path / "findings.json", "{nope")
    with pytest.raises(ValueError, match="invalid findings file"):
        load_findings(path)


def test_load_findings_wrong_schema_raises(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "findings.json", '{"schema": "harnessprobe.findings/v2", "findings": []}'
    )
    with pytest.raises(ValueError, match="invalid findings file"):
        load_findings(path)


def test_comment_cli_prints_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    code = main(["comment", "--report", str(report_path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == render_pr_comment(make_report())
    assert captured.err == ""


def test_comment_cli_writes_out_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    out = tmp_path / "comment.md"
    code = main(["comment", "--report", str(report_path), "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert out.read_text(encoding="utf-8") == render_pr_comment(make_report())


def test_comment_cli_wires_findings_and_previous(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    findings_path = write_json(
        tmp_path / "findings.json",
        Findings(schema="harnessprobe.findings/v1", findings=FINDINGS).to_json() + "\n",
    )
    previous_path = write_json(tmp_path / "previous.json", make_report(covered_pct=79.72).to_json())
    code = main(
        [
            "comment",
            "--report",
            str(report_path),
            "--findings",
            str(findings_path),
            "--previous",
            str(previous_path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "### HarnessProbe: 2 bug classes caught (3 findings)" in captured.out
    assert "**+2.10pp** vs previous report" in captured.out


def test_comment_cli_missing_report_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["comment", "--report", str(tmp_path / "nope.json")])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_comment_cli_bad_findings_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    findings_path = write_json(tmp_path / "findings.json", "{}")
    code = main(["comment", "--report", str(report_path), "--findings", str(findings_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_comment_cli_invalid_previous_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    previous_path = write_json(tmp_path / "previous.json", "not json")
    code = main(["comment", "--report", str(report_path), "--previous", str(previous_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_comment_cli_write_failure_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = write_json(tmp_path / "report.json", make_report().to_json() + "\n")
    out_dir = tmp_path / "as_dir"
    out_dir.mkdir()
    code = main(["comment", "--report", str(report_path), "--out", str(out_dir)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")
