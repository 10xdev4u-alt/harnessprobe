from __future__ import annotations

from pathlib import Path

import pytest

from harnessprobe import (
    FileScope,
    Scope,
    SubsetReport,
    UncoveredSample,
    derive_scope,
    subset_coverage,
)

MINI_FILE_METRICS = {
    "mini_repo/agent.py": (3, 2, 0, 66.67, 0, 1, 0),
    "mini_repo/dispatch.py": (2, 2, 0, 100.0, 1, 0, 0),
    "mini_repo/parsing.py": (6, 5, 0, 83.33, 0, 0, 1),
    "mini_repo/text_tools.py": (0, 0, 5, None, 0, 0, 0),
    "mini_repo/unrelated.py": (0, 0, 3, None, 0, 0, 0),
}


def test_mini_totals(mini_report: SubsetReport) -> None:
    totals = mini_report.totals
    observed = (
        totals.scope_lines,
        totals.executed,
        totals.not_measured,
        totals.covered_pct,
        totals.branches_full,
        totals.branches_partial,
        totals.branches_missing,
    )
    assert observed == (11, 9, 8, 81.82, 1, 1, 1)


def test_mini_file_metrics(mini_report: SubsetReport) -> None:
    observed = {
        file_report.path: (
            file_report.scope_lines,
            file_report.executed,
            file_report.not_measured,
            file_report.covered_pct,
            file_report.branches_full,
            file_report.branches_partial,
            file_report.branches_missing,
        )
        for file_report in mini_report.files
    }
    assert observed == MINI_FILE_METRICS


def test_mini_files_ordered_by_path(mini_report: SubsetReport) -> None:
    paths = [file_report.path for file_report in mini_report.files]
    assert paths == sorted(paths)


def test_mini_samples_with_source_text(mini_report: SubsetReport) -> None:
    observed = [
        (sample.path, sample.line, sample.text)
        for file_report in mini_report.files
        for sample in file_report.samples
    ]
    assert observed == [
        ("mini_repo/agent.py", 21, "return response.choices[0].message.content"),
        ("mini_repo/parsing.py", 6, "if not tool_calls:"),
    ]


def test_samples_grouped_under_their_file(mini_report: SubsetReport) -> None:
    by_path = {file_report.path: file_report.samples for file_report in mini_report.files}
    assert by_path["mini_repo/agent.py"] == [
        UncoveredSample(
            path="mini_repo/agent.py",
            line=21,
            text="return response.choices[0].message.content",
        )
    ]
    assert by_path["mini_repo/text_tools.py"] == []


def test_samples_without_repo_root_have_no_text(
    fixtures_root: Path, mini_coverage_json: dict[str, object]
) -> None:
    report = subset_coverage(mini_coverage_json, derive_scope(fixtures_root))
    samples = [sample for file_report in report.files for sample in file_report.samples]
    assert samples
    assert all(sample.text is None for sample in samples)


def test_samples_spread_across_files() -> None:
    scope = Scope(
        files=(
            FileScope(path="a.py", lines=(1, 2, 3), reasons=("heuristic:tier-a",)),
            FileScope(path="b.py", lines=(10, 11, 12), reasons=("heuristic:tier-a",)),
        ),
        warnings=(),
    )
    coverage = {
        "files": {
            "a.py": {"executed_lines": [], "missing_lines": [1, 2, 3]},
            "b.py": {"executed_lines": [], "missing_lines": [10, 11, 12]},
        }
    }
    report = subset_coverage(coverage, scope, sample_limit=4)
    observed = [
        (sample.path, sample.line) for file_report in report.files for sample in file_report.samples
    ]
    assert observed == [("a.py", 1), ("a.py", 2), ("b.py", 10), ("b.py", 11)]


def test_sample_limit_caps_total(
    fixtures_root: Path, mini_coverage_json: dict[str, object]
) -> None:
    report = subset_coverage(mini_coverage_json, derive_scope(fixtures_root), sample_limit=1)
    samples = [sample for file_report in report.files for sample in file_report.samples]
    assert [(sample.path, sample.line) for sample in samples] == [("mini_repo/agent.py", 21)]


def test_sample_text_none_when_source_unreadable(tmp_path: Path) -> None:
    scope = Scope(
        files=(FileScope(path="gone.py", lines=(5,), reasons=("heuristic:tier-a",)),),
        warnings=(),
    )
    coverage = {"files": {"gone.py": {"executed_lines": [], "missing_lines": [5]}}}
    report = subset_coverage(coverage, scope, repo_root=tmp_path)
    assert report.files[0].samples == [UncoveredSample(path="gone.py", line=5, text=None)]


def test_sample_text_none_when_line_out_of_range(tmp_path: Path) -> None:
    (tmp_path / "short.py").write_text("x = 1\n", encoding="utf-8")
    scope = Scope(
        files=(FileScope(path="short.py", lines=(99,), reasons=("heuristic:tier-a",)),),
        warnings=(),
    )
    coverage = {"files": {"short.py": {"executed_lines": [], "missing_lines": [99]}}}
    report = subset_coverage(coverage, scope, repo_root=tmp_path)
    assert report.files[0].samples == [UncoveredSample(path="short.py", line=99, text=None)]


def test_coverage_json_without_files_key_raises() -> None:
    with pytest.raises(ValueError):
        subset_coverage({}, Scope(files=(), warnings=()))


def test_non_integer_line_raises() -> None:
    coverage = {"files": {"a.py": {"executed_lines": [1, "x"], "missing_lines": []}}}
    scope = Scope(
        files=(FileScope(path="a.py", lines=(1,), reasons=("heuristic:tier-a",)),),
        warnings=(),
    )
    with pytest.raises(ValueError):
        subset_coverage(coverage, scope)


def test_malformed_branch_pair_raises() -> None:
    coverage = {
        "files": {"a.py": {"executed_lines": [1], "missing_lines": [], "executed_branches": [[1]]}}
    }
    scope = Scope(
        files=(FileScope(path="a.py", lines=(1,), reasons=("heuristic:tier-a",)),),
        warnings=(),
    )
    with pytest.raises(ValueError):
        subset_coverage(coverage, scope)
