"""Pydantic v2 report models for coverage subsetting."""

from __future__ import annotations

import warnings
from typing import Literal

from pydantic import BaseModel, ConfigDict

TOP_SAMPLE_CAP = 10
TABLE_HEADER = (
    "| File | Scope lines | Executed | Covered | Not measured | Branches F/P/M | Samples |"
)
TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- | --- |"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UncoveredSample(_StrictModel):
    """One uncovered scope line with optional source text."""

    path: str
    line: int
    text: str | None


class FileSubsetReport(_StrictModel):
    """Coverage subset metrics and uncovered samples for one scoped file."""

    path: str
    scope_lines: int
    not_measured: int
    executed: int
    covered_pct: float | None
    branches_full: int
    branches_partial: int
    branches_missing: int
    samples: list[UncoveredSample]


class SubsetTotals(_StrictModel):
    """Aggregated coverage subset metrics across all scoped files."""

    scope_lines: int
    not_measured: int
    executed: int
    covered_pct: float | None
    branches_full: int
    branches_partial: int
    branches_missing: int


with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "schema"', category=UserWarning)

    class SubsetReport(_StrictModel):
        """Coverage subset report with JSON and Markdown rendering."""

        schema: Literal["harnessprobe.report/v1"]
        generated_by: str = "harnessprobe"
        totals: SubsetTotals
        files: list[FileSubsetReport]

        def to_json(self, indent: int = 2) -> str:
            """Serialize the report to JSON."""
            return self.model_dump_json(indent=indent)

        @classmethod
        def from_json(cls, s: str) -> SubsetReport:
            """Parse a report from a JSON string."""
            return cls.model_validate_json(s)

        def render_markdown(self) -> str:
            """Render the report as a Markdown summary."""
            blocks = [
                "# HarnessProbe LDH scope coverage",
                "",
                self._totals_line(),
                "",
                TABLE_HEADER,
                TABLE_SEPARATOR,
                *[self._file_row(file_report) for file_report in self._ordered_files()],
                "",
                "## Top uncovered scope lines",
            ]
            lines = self._top_uncovered_lines()
            if lines:
                blocks.append("")
                blocks.extend(lines)
            return "\n".join(blocks) + "\n"

        def _ordered_files(self) -> list[FileSubsetReport]:
            return sorted(
                self.files, key=lambda file_report: (-len(file_report.samples), file_report.path)
            )

        def _totals_line(self) -> str:
            totals = self.totals
            pct = "n/a" if totals.covered_pct is None else f"{totals.covered_pct:.2f}%"
            return (
                f"Totals: {totals.executed}/{totals.scope_lines} scope lines covered ({pct}), "
                f"{totals.not_measured} not measured; branches {totals.branches_full} full, "
                f"{totals.branches_partial} partial, {totals.branches_missing} missing."
            )

        def _file_row(self, file_report: FileSubsetReport) -> str:
            pct = "n/a" if file_report.covered_pct is None else f"{file_report.covered_pct:.2f}%"
            branches = (
                f"{file_report.branches_full}/{file_report.branches_partial}"
                f"/{file_report.branches_missing}"
            )
            return (
                f"| {file_report.path} | {file_report.scope_lines} | {file_report.executed} "
                f"| {pct} | {file_report.not_measured} | {branches} "
                f"| {len(file_report.samples)} |"
            )

        def _top_uncovered_lines(self) -> list[str]:
            lines: list[str] = []
            for file_report in self._ordered_files():
                for sample in file_report.samples:
                    if len(lines) >= TOP_SAMPLE_CAP:
                        return lines
                    if sample.text is None:
                        lines.append(f"- {sample.path}:{sample.line}")
                    else:
                        lines.append(f"- {sample.path}:{sample.line}: {sample.text}")
            return lines
