from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harnessprobe import SubsetReport, SubsetTotals

EMPTY_MARKDOWN = (
    "# HarnessProbe LDH scope coverage\n"
    "\n"
    "Totals: 0/0 scope lines covered (n/a), 0 not measured; "
    "branches 0 full, 0 partial, 0 missing.\n"
    "\n"
    "| File | Scope lines | Executed | Covered | Not measured | Branches F/P/M | Samples |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
    "\n"
    "## Top uncovered scope lines\n"
)


def test_json_round_trip(mini_report: SubsetReport) -> None:
    assert SubsetReport.from_json(mini_report.to_json(indent=2)) == mini_report


def test_json_serialization_shape(mini_report: SubsetReport) -> None:
    payload = mini_report.to_json(indent=2)
    assert '\n  "schema": "harnessprobe.report/v1"' in payload
    assert '\n  "generated_by": "harnessprobe"' in payload


def test_extra_fields_forbidden(mini_report: SubsetReport) -> None:
    top_level = json.loads(mini_report.to_json())
    top_level["unexpected"] = True
    with pytest.raises(ValidationError):
        SubsetReport.from_json(json.dumps(top_level))
    nested = json.loads(mini_report.to_json())
    nested["totals"]["unexpected"] = True
    with pytest.raises(ValidationError):
        SubsetReport.from_json(json.dumps(nested))


def test_golden_markdown_matches_fixture(mini_report: SubsetReport, fixtures_root: Path) -> None:
    expected = (fixtures_root / "expected_report.md").read_text(encoding="utf-8")
    assert mini_report.render_markdown() == expected


def test_render_markdown_empty_report() -> None:
    report = SubsetReport(
        schema="harnessprobe.report/v1",
        totals=SubsetTotals(
            scope_lines=0,
            not_measured=0,
            executed=0,
            covered_pct=None,
            branches_full=0,
            branches_partial=0,
            branches_missing=0,
        ),
        files=[],
    )
    assert report.render_markdown() == EMPTY_MARKDOWN
