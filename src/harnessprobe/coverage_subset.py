"""Subset coverage.py JSON output to a heuristic LDH scope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from harnessprobe.report import FileSubsetReport, SubsetReport, SubsetTotals, UncoveredSample
from harnessprobe.scope import FileScope, Scope


@dataclass(frozen=True)
class _FileCoverage:
    executed_lines: frozenset[int]
    missing_lines: frozenset[int]
    executed_branches: tuple[tuple[int, int], ...]
    missing_branches: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _FileStats:
    path: str
    scope_lines: int
    not_measured: int
    executed: int
    covered_pct: float | None
    branches_full: int
    branches_partial: int
    branches_missing: int
    uncovered: tuple[int, ...]


def subset_coverage(
    coverage_json: Mapping[str, object],
    scope: Scope,
    *,
    repo_root: Path | None = None,
    sample_limit: int = 10,
) -> SubsetReport:
    """Subset coverage data to the scope and build the report."""
    coverage = _parse_coverage(coverage_json)
    stats = [_file_stats(file_scope, coverage.get(file_scope.path)) for file_scope in scope.files]
    selected = _select_samples(stats, sample_limit)
    source_cache: dict[str, list[str]] = {}
    file_reports = [
        FileSubsetReport(
            path=file_stat.path,
            scope_lines=file_stat.scope_lines,
            not_measured=file_stat.not_measured,
            executed=file_stat.executed,
            covered_pct=file_stat.covered_pct,
            branches_full=file_stat.branches_full,
            branches_partial=file_stat.branches_partial,
            branches_missing=file_stat.branches_missing,
            samples=[
                UncoveredSample(
                    path=file_stat.path,
                    line=line,
                    text=_source_line(repo_root, file_stat.path, line, source_cache),
                )
                for line in selected[file_stat.path]
            ],
        )
        for file_stat in stats
    ]
    return SubsetReport(
        schema="harnessprobe.report/v1",
        totals=_totals(stats),
        files=file_reports,
    )


def _parse_coverage(coverage_json: Mapping[str, object]) -> dict[str, _FileCoverage]:
    files = coverage_json.get("files")
    if not isinstance(files, Mapping):
        raise ValueError("coverage json must contain a 'files' mapping")
    parsed: dict[str, _FileCoverage] = {}
    for path, raw in files.items():
        if not isinstance(path, str) or not isinstance(raw, Mapping):
            raise ValueError("coverage json 'files' entries must map paths to objects")
        parsed[path] = _FileCoverage(
            executed_lines=_line_set(raw.get("executed_lines"), path, "executed_lines"),
            missing_lines=_line_set(raw.get("missing_lines"), path, "missing_lines"),
            executed_branches=_arc_tuples(raw.get("executed_branches"), path, "executed_branches"),
            missing_branches=_arc_tuples(raw.get("missing_branches"), path, "missing_branches"),
        )
    return parsed


def _line_set(value: object, path: str, key: str) -> frozenset[int]:
    if value is None:
        return frozenset()
    if not isinstance(value, list):
        raise ValueError(f"coverage json {path}: {key} must be a list")
    return frozenset(_as_int(item, path, key) for item in value)


def _arc_tuples(value: object, path: str, key: str) -> tuple[tuple[int, int], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"coverage json {path}: {key} must be a list")
    arcs: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError(f"coverage json {path}: {key} must contain [from, to] pairs")
        arcs.append((_as_int(item[0], path, key), _as_int(item[1], path, key)))
    return tuple(arcs)


def _as_int(item: object, path: str, key: str) -> int:
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"coverage json {path}: {key} must contain integers")
    return item


def _file_stats(file_scope: FileScope, entry: _FileCoverage | None) -> _FileStats:
    scope_lines = set(file_scope.lines)
    if entry is None:
        executed: set[int] = set()
        missing: set[int] = set()
    else:
        executed = scope_lines & entry.executed_lines
        missing = scope_lines & entry.missing_lines
    measured = executed | missing
    scope_count = len(measured)
    covered_pct = round(100.0 * len(executed) / scope_count, 2) if scope_count else None
    full, partial, absent = _classify_branches(entry, scope_lines)
    return _FileStats(
        path=file_scope.path,
        scope_lines=scope_count,
        not_measured=len(scope_lines - measured),
        executed=len(executed),
        covered_pct=covered_pct,
        branches_full=full,
        branches_partial=partial,
        branches_missing=absent,
        uncovered=tuple(sorted(missing)),
    )


def _classify_branches(entry: _FileCoverage | None, scope_lines: set[int]) -> tuple[int, int, int]:
    if entry is None:
        return 0, 0, 0
    executed_arcs = set(entry.executed_branches)
    by_source: dict[int, list[tuple[int, int]]] = {}
    for arc in (*entry.executed_branches, *entry.missing_branches):
        if arc[0] in scope_lines:
            by_source.setdefault(arc[0], []).append(arc)
    full = partial = absent = 0
    for arcs in by_source.values():
        executed_count = sum(1 for arc in arcs if arc in executed_arcs)
        if executed_count == len(arcs):
            full += 1
        elif executed_count == 0:
            absent += 1
        else:
            partial += 1
    return full, partial, absent


def _select_samples(stats: list[_FileStats], sample_limit: int) -> dict[str, list[int]]:
    selected: dict[str, list[int]] = {file_stat.path: [] for file_stat in stats}
    remaining = {file_stat.path: list(file_stat.uncovered) for file_stat in stats}
    total = 0
    index = 0
    while total < sample_limit:
        progressed = False
        for file_stat in stats:
            lines = remaining[file_stat.path]
            if index < len(lines):
                selected[file_stat.path].append(lines[index])
                total += 1
                progressed = True
                if total >= sample_limit:
                    break
        if not progressed:
            break
        index += 1
    return selected


def _source_line(
    repo_root: Path | None,
    rel: str,
    line: int,
    cache: dict[str, list[str]],
) -> str | None:
    if repo_root is None:
        return None
    if rel not in cache:
        try:
            text = (repo_root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            cache[rel] = []
        else:
            cache[rel] = text.splitlines()
    lines = cache[rel]
    if not 0 < line <= len(lines):
        return None
    return lines[line - 1].strip()


def _totals(stats: list[_FileStats]) -> SubsetTotals:
    scope_lines = sum(file_stat.scope_lines for file_stat in stats)
    executed = sum(file_stat.executed for file_stat in stats)
    return SubsetTotals(
        scope_lines=scope_lines,
        not_measured=sum(file_stat.not_measured for file_stat in stats),
        executed=executed,
        covered_pct=round(100.0 * executed / scope_lines, 2) if scope_lines else None,
        branches_full=sum(file_stat.branches_full for file_stat in stats),
        branches_partial=sum(file_stat.branches_partial for file_stat in stats),
        branches_missing=sum(file_stat.branches_missing for file_stat in stats),
    )
