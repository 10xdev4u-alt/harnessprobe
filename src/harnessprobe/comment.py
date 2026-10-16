"""Bug findings model and bug-class-first PR comment rendering."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from harnessprobe.report import SubsetReport, UncoveredSample

SAMPLE_CAP = 8
NO_FINDINGS_LINE = (
    "No findings were attached to this run. HarnessProbe v1 ships LDH coverage "
    "subsetting; differential bug detection lands in later phases."
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BugFinding(_StrictModel):
    """One caught bug with an evidence link and an optional file:line."""

    bug_class: str
    title: str
    evidence: str
    location: str | None = None


with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "schema"', category=UserWarning)

    class Findings(_StrictModel):
        """Versioned container of bug findings."""

        schema: Literal["harnessprobe.findings/v1"]
        findings: list[BugFinding]

        def to_json(self, indent: int = 2) -> str:
            """Serialize the findings to JSON."""
            return self.model_dump_json(indent=indent)

        @classmethod
        def from_json(cls, s: str) -> Findings:
            """Parse findings from a JSON string."""
            return cls.model_validate_json(s)


def load_findings(path: Path) -> list[BugFinding]:
    """Read and parse a findings file, raising ValueError on bad input."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read findings file {path}: {exc}") from exc
    try:
        return Findings.from_json(text).findings
    except ValueError as exc:
        raise ValueError(f"invalid findings file {path}: {exc}") from exc


def render_pr_comment(
    report: SubsetReport,
    *,
    findings: Sequence[BugFinding] = (),
    previous: SubsetReport | None = None,
) -> str:
    """Render the bug-class-first PR comment for a coverage report."""
    blocks = [_findings_section(findings), _coverage_section(report, previous)]
    details = _details_section(report)
    if details is not None:
        blocks.append(details)
    blocks.append(f"_harnessprobe · report {report.schema}_")
    return "\n\n".join(blocks) + "\n"


def _findings_section(findings: Sequence[BugFinding]) -> str:
    if not findings:
        return f"### HarnessProbe: no bug classes caught\n\n{NO_FINDINGS_LINE}"
    grouped: dict[str, list[BugFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.bug_class, []).append(finding)
    ordered = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    heading = (
        f"### HarnessProbe: {_plural(len(grouped), 'bug class', 'bug classes')} caught "
        f"({_plural(len(findings), 'finding', 'findings')})"
    )
    lines = [heading, ""]
    for bug_class, class_findings in ordered:
        lines.append(f"- **{bug_class}** ({len(class_findings)})")
        lines.extend(f"  - {_finding_line(finding)}" for finding in class_findings)
    return "\n".join(lines)


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _finding_line(finding: BugFinding) -> str:
    if finding.location is None:
        return f"{finding.title} — [evidence]({finding.evidence})"
    return f"{finding.title} — ({finding.location}) [evidence]({finding.evidence})"


def _coverage_section(report: SubsetReport, previous: SubsetReport | None) -> str:
    totals = report.totals
    pct = "n/a" if totals.covered_pct is None else f"{totals.covered_pct:.2f}%"
    line = (
        f"`{pct}` of LDH scope lines covered "
        f"({totals.executed}/{totals.scope_lines}; {totals.not_measured} not measured)"
    )
    if previous is not None:
        delta = _delta(totals.covered_pct, previous.totals.covered_pct)
        line += f" — **{delta}** vs previous report"
    branches = (
        f"Branches: {totals.branches_full} full / {totals.branches_partial} partial "
        f"/ {totals.branches_missing} missing"
    )
    return f"### LDH coverage\n\n{line}\n{branches}"


def _delta(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "no comparable previous value"
    delta = current - previous
    if abs(delta) < 0.005:
        return "no change"
    return f"{delta:+.2f}pp"


def _details_section(report: SubsetReport) -> str | None:
    files = sorted(
        report.files, key=lambda file_report: (-len(file_report.samples), file_report.path)
    )
    bullets: list[str] = []
    for file_report in files:
        for sample in file_report.samples:
            if len(bullets) >= SAMPLE_CAP:
                break
            bullets.append(_sample_line(sample))
        if len(bullets) >= SAMPLE_CAP:
            break
    if not bullets:
        return None
    return "\n".join(
        ["<details><summary>Top uncovered LDH lines</summary>", "", *bullets, "", "</details>"]
    )


def _sample_line(sample: UncoveredSample) -> str:
    if sample.text is None:
        return f"- `{sample.path}:{sample.line}`"
    return f"- `{sample.path}:{sample.line}` — `{sample.text}`"
