"""Pytest plugin that subsets session coverage to the LDH scope at session end."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import coverage
import pytest
from coverage.parser import PythonParser

if TYPE_CHECKING:
    from harnessprobe.report import SubsetReport
    from harnessprobe.scope import Scope

DEFAULT_SCOPE_NAME = "harnessprobe.scope.json"
DEFAULT_REPORT_NAME = "harnessprobe.report.json"
SAMPLE_LIMIT = 10
NO_COVERAGE_MESSAGE = (
    "harnessprobe: no coverage data found; run tests under coverage (coverage run -m pytest)"
)
REPORT_DISABLED_MESSAGE = "harnessprobe: report writing disabled (--harnessprobe-no-report)"


@dataclass(frozen=True)
class _PluginState:
    scope: Scope
    report_path: Path
    write_report: bool


_STATE_KEY = pytest.StashKey[_PluginState]()


def resolve_scope_path(explicit: str | None, ini: str | None, rootpath: Path) -> Path | None:
    """Resolve the scope file path from the CLI option, ini, then rootdir default."""
    configured = _configured_path(explicit, ini, rootpath)
    if configured is not None:
        return configured
    default = rootpath / DEFAULT_SCOPE_NAME
    return default if default.is_file() else None


def load_scope(path: Path) -> Scope:
    """Read and parse a scope file into a scope, raising ValueError when invalid."""
    from harnessprobe.scopefile import ScopeFile, scope_from_file

    try:
        scope_file = ScopeFile.from_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid scope file {path}: {exc}") from exc
    return scope_from_file(scope_file)


def coverage_dict_from_data(
    data: coverage.CoverageData,
    scope: Scope,
    rootpath: Path,
) -> dict[str, object]:
    """Build coverage.py JSON-shaped data keyed by scope-relative paths."""
    measured = {str(Path(path).resolve()): path for path in data.measured_files()}
    files: dict[str, object] = {}
    for file_scope in scope.files:
        abspath = measured.get(str((rootpath / file_scope.path).resolve()))
        if abspath is None:
            continue
        source = _read_source(abspath)
        if source is None:
            continue
        files[file_scope.path] = _file_entry(data, abspath, source)
    return {"files": files}


def summary_lines(report: SubsetReport, report_path: Path | None) -> list[str]:
    """Format the two-line terminal summary for a subset report."""
    totals = report.totals
    pct = "n/a" if totals.covered_pct is None else f"{totals.covered_pct:.2f}%"
    samples = sum(len(file_report.samples) for file_report in report.files)
    coverage_line = (
        f"harnessprobe: LDH scope coverage {totals.executed}/{totals.scope_lines} "
        f"lines ({pct}), {samples} uncovered samples"
    )
    if report_path is None:
        return [coverage_line, REPORT_DISABLED_MESSAGE]
    return [coverage_line, f"harnessprobe: report written to {report_path}"]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the harnessprobe command-line options and ini settings."""
    group = parser.getgroup("harnessprobe")
    group.addoption(
        "--harnessprobe-scope",
        default=None,
        metavar="PATH",
        help="Scope file to subset coverage to.",
    )
    group.addoption(
        "--harnessprobe-report",
        default=None,
        metavar="PATH",
        help="Path of the written subset report.",
    )
    group.addoption(
        "--harnessprobe-no-report",
        action="store_true",
        help="Do not write the subset report file.",
    )
    parser.addini("harnessprobe_scope", "Scope file to subset coverage to.", default=None)
    parser.addini("harnessprobe_report", "Path of the written subset report.", default=None)


def pytest_configure(config: pytest.Config) -> None:
    """Load the scope file and arm session-end reporting, or stay inert."""
    rootpath = Path(config.rootpath)
    explicit_scope = config.getoption("harnessprobe_scope")
    ini_scope = config.getini("harnessprobe_scope")
    scope_path = resolve_scope_path(explicit_scope, ini_scope, rootpath)
    if scope_path is None:
        return
    configured = explicit_scope is not None or ini_scope is not None
    if not scope_path.is_file():
        if configured:
            raise pytest.UsageError(f"harnessprobe: scope file not found: {scope_path}")
        return
    try:
        scope = load_scope(scope_path)
    except ValueError as exc:
        raise pytest.UsageError(f"harnessprobe: {exc}") from exc
    config.stash[_STATE_KEY] = _PluginState(
        scope=scope,
        report_path=_report_path(config, rootpath),
        write_report=not config.getoption("harnessprobe_no_report"),
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write the subset report and print the session summary."""
    state = session.config.stash.get(_STATE_KEY, None)
    if state is None:
        return
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    data = _coverage_data()
    if data is None or not data.measured_files():
        _write_lines(reporter, [NO_COVERAGE_MESSAGE])
        return
    from harnessprobe.coverage_subset import subset_coverage

    rootpath = Path(session.config.rootpath)
    payload = coverage_dict_from_data(data, state.scope, rootpath)
    report = subset_coverage(payload, state.scope, repo_root=rootpath, sample_limit=SAMPLE_LIMIT)
    report_path = state.report_path if state.write_report else None
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.to_json() + "\n", encoding="utf-8")
    _write_lines(reporter, summary_lines(report, report_path))


def _configured_path(explicit: str | None, ini: str | None, rootpath: Path) -> Path | None:
    if explicit is not None:
        return Path(explicit)
    if ini is not None:
        candidate = Path(ini)
        return candidate if candidate.is_absolute() else rootpath / candidate
    return None


def _report_path(config: pytest.Config, rootpath: Path) -> Path:
    configured = _configured_path(
        config.getoption("harnessprobe_report"),
        config.getini("harnessprobe_report"),
        rootpath,
    )
    return configured if configured is not None else rootpath / DEFAULT_REPORT_NAME


def _read_source(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _file_entry(data: coverage.CoverageData, abspath: str, source: str) -> dict[str, object]:
    parser = PythonParser(text=source)
    parser.parse_source()
    executed_lines = sorted(data.lines(abspath) or [])
    arcs = data.arcs(abspath)
    if arcs:
        executed_branches = [list(arc) for arc in arcs]
        missing = set(parser.arcs()) - set(arcs)
        missing_branches = [list(arc) for arc in sorted(missing)]
    else:
        executed_branches = []
        missing_branches = []
    return {
        "executed_lines": executed_lines,
        "missing_lines": sorted(parser.statements - set(executed_lines)),
        "executed_branches": executed_branches,
        "missing_branches": missing_branches,
    }


def _coverage_data() -> coverage.CoverageData | None:
    live = coverage.Coverage.current()
    if live is not None:
        return live.get_data()
    data = coverage.CoverageData()
    data.read()
    return data if data.measured_files() else None


def _write_lines(reporter: pytest.TerminalReporter | None, lines: list[str]) -> None:
    if reporter is None:
        return
    for line in lines:
        reporter.write_line(line)
