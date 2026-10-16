"""Tests for the harnessprobe pytest plugin."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import coverage
import pytest

import harnessprobe
from harnessprobe.coverage_subset import subset_coverage
from harnessprobe.pytest_plugin import (
    NO_COVERAGE_MESSAGE,
    REPORT_DISABLED_MESSAGE,
    _write_lines,
    coverage_dict_from_data,
    load_scope,
    pytest_addoption,
    pytest_configure,
    pytest_sessionfinish,
    resolve_scope_path,
    summary_lines,
)
from harnessprobe.report import SubsetReport, SubsetTotals
from harnessprobe.scope import FileScope, Scope, derive_scope
from harnessprobe.scopefile import build_scope_file, write_scope_file

MODULE_SOURCE = """\
class _Response:
    def __init__(self, flag, content):
        self.flag = flag
        self.content = content


class _Completions:
    def create(self, **kwargs):
        return _Response(flag=True, content="hello")


class _Chat:
    completions = _Completions()


class _Client:
    chat = _Chat()


client = _Client()


def call_model(flag):  # harness:llm-source
    response = client.chat.completions.create(flag=flag)
    if response.flag:
        return response.content
    return None
"""

TEST_SOURCE = """\
from mod import call_model


def test_true_path():
    assert call_model(True) == "hello"
"""

INNER_SOURCE = """\
def choose(flag):
    if flag:
        return 1
    return 0
"""

UNCOVERED_LINE = MODULE_SOURCE.splitlines().index("    return None") + 1


def _build_project(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(mod=MODULE_SOURCE)
    pytester.makepyfile(test_mod=TEST_SOURCE)
    scope = derive_scope(pytester.path)
    write_scope_file(
        build_scope_file(scope, allowlist=[], include_tier_b=True, generated_by="harnessprobe"),
        pytester.path / "harnessprobe.scope.json",
    )


def _run_inner_module(tmp_path: Path, *, branch: bool) -> coverage.CoverageData:
    module = tmp_path / "target.py"
    module.write_text(INNER_SOURCE, encoding="utf-8")
    cov = coverage.Coverage(
        source=[str(tmp_path)], branch=branch, data_file=str(tmp_path / ".coverage")
    )
    cov.start()
    try:
        spec = importlib.util.spec_from_file_location("hp_inner_target", module)
        assert spec is not None
        assert spec.loader is not None
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        assert loaded.choose(True) == 1
    finally:
        cov.stop()
    return cov.get_data()


def test_resolve_scope_path_explicit_wins(tmp_path: Path) -> None:
    assert resolve_scope_path("cli.json", "ini.json", tmp_path) == Path("cli.json")


def test_resolve_scope_path_uses_ini_relative_to_rootpath(tmp_path: Path) -> None:
    assert resolve_scope_path(None, "ini.json", tmp_path) == tmp_path / "ini.json"


def test_resolve_scope_path_keeps_absolute_ini(tmp_path: Path) -> None:
    absolute = tmp_path / "abs.json"
    assert resolve_scope_path(None, str(absolute), tmp_path) == absolute


def test_resolve_scope_path_finds_rootdir_default(tmp_path: Path) -> None:
    default = tmp_path / "harnessprobe.scope.json"
    default.write_text("{}", encoding="utf-8")
    assert resolve_scope_path(None, None, tmp_path) == default


def test_resolve_scope_path_none_without_candidates(tmp_path: Path) -> None:
    assert resolve_scope_path(None, None, tmp_path) is None


def test_load_scope_round_trips_derived_scope(fixtures_root: Path, tmp_path: Path) -> None:
    scope = derive_scope(fixtures_root)
    path = write_scope_file(
        build_scope_file(scope, allowlist=[], include_tier_b=True, generated_by="harnessprobe"),
        tmp_path / "harnessprobe.scope.json",
    )
    assert load_scope(path) == scope


def test_load_scope_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_scope(path)
    assert str(excinfo.value).startswith(f"invalid scope file {path}")


def test_load_scope_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"schema": "harnessprobe.scope/v3"}', encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_scope(path)
    assert str(excinfo.value).startswith(f"invalid scope file {path}")


def test_load_scope_resolves_whole_file_entries(tmp_path: Path) -> None:
    module = tmp_path / "mod.py"
    module.write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    path = write_scope_file(
        build_scope_file(
            derive_scope(tmp_path, allowlist=("mod.py",)),
            allowlist=["mod.py"],
            include_tier_b=True,
            generated_by="harnessprobe",
        ),
        tmp_path / "harnessprobe.scope.json",
    )
    module.write_text('"""Doc."""\n\n\ndef f(x):\n    return x + 1\n', encoding="utf-8")
    assert load_scope(path, repo_root=tmp_path) == Scope(
        files=(FileScope(path="mod.py", lines=(1, 4, 5), reasons=("allowlist",)),),
        warnings=(),
    )


def test_summary_lines_reports_counts_and_path(tmp_path: Path) -> None:
    report = SubsetReport(
        schema="harnessprobe.report/v1",
        totals=SubsetTotals(
            scope_lines=4,
            not_measured=0,
            executed=3,
            covered_pct=75.0,
            branches_full=2,
            branches_partial=1,
            branches_missing=1,
        ),
        files=[],
    )
    path = tmp_path / "harnessprobe.report.json"
    assert summary_lines(report, path) == [
        "harnessprobe: LDH scope coverage 3/4 lines (75.00%), 0 uncovered samples",
        f"harnessprobe: report written to {path}",
    ]


def test_summary_lines_reports_na_and_disabled() -> None:
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
    assert summary_lines(report, None) == [
        "harnessprobe: LDH scope coverage 0/0 lines (n/a), 0 uncovered samples",
        "harnessprobe: report writing disabled (--harnessprobe-no-report)",
    ]


def _scope_of(*paths: str) -> Scope:
    return Scope(
        files=tuple(
            FileScope(path=path, lines=(1, 2, 3, 4), reasons=("annotation",)) for path in paths
        ),
        warnings=(),
    )


def test_coverage_dict_reports_lines_and_partial_arcs(tmp_path: Path) -> None:
    data = _run_inner_module(tmp_path, branch=True)
    scope = _scope_of("target.py")
    payload = coverage_dict_from_data(data, scope, tmp_path)
    entry = payload["files"]["target.py"]
    assert entry["executed_lines"] == [1, 2, 3]
    assert entry["missing_lines"] == [4]
    assert [2, 3] in entry["executed_branches"]
    assert [2, 4] in entry["missing_branches"]
    report = subset_coverage(payload, scope, repo_root=tmp_path, sample_limit=10)
    assert report.totals.scope_lines == 4
    assert report.totals.executed == 3
    assert report.totals.covered_pct == 75.0
    assert report.totals.branches_partial == 1
    assert report.totals.branches_missing == 1
    assert [(sample.path, sample.line, sample.text) for sample in report.files[0].samples] == [
        ("target.py", 4, "return 0")
    ]
    assert summary_lines(report, None)[0] == (
        "harnessprobe: LDH scope coverage 3/4 lines (75.00%), 1 uncovered samples"
    )


def test_coverage_dict_without_branch_data(tmp_path: Path) -> None:
    data = _run_inner_module(tmp_path, branch=False)
    payload = coverage_dict_from_data(data, _scope_of("target.py"), tmp_path)
    entry = payload["files"]["target.py"]
    assert entry["executed_lines"] == [1, 2, 3]
    assert entry["executed_branches"] == []
    assert entry["missing_branches"] == []


def test_coverage_dict_skips_unmeasured_files(tmp_path: Path) -> None:
    data = _run_inner_module(tmp_path, branch=True)
    assert coverage_dict_from_data(data, _scope_of("other.py"), tmp_path) == {"files": {}}


class _StubReporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        self.lines.append(line)


class _StubPluginManager:
    def __init__(self, reporter: _StubReporter) -> None:
        self.reporter = reporter

    def getplugin(self, name: str) -> _StubReporter | None:
        return self.reporter if name == "terminalreporter" else None


class _StubConfig:
    def __init__(
        self,
        rootpath: Path,
        *,
        report: str | None = None,
        no_report: bool = False,
    ) -> None:
        self.rootpath = rootpath
        self.stash = pytest.Stash()
        self.pluginmanager = _StubPluginManager(_StubReporter())
        self._options: dict[str, object] = {
            "harnessprobe_scope": None,
            "harnessprobe_report": report,
            "harnessprobe_no_report": no_report,
        }
        self._ini: dict[str, str | None] = {
            "harnessprobe_scope": None,
            "harnessprobe_report": None,
        }

    def getoption(self, name: str) -> object:
        return self._options[name]

    def getini(self, name: str) -> str | None:
        return self._ini[name]


class _StubSession:
    def __init__(self, config: _StubConfig) -> None:
        self.config = config


class _StubGroup:
    def __init__(self) -> None:
        self.options: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def addoption(self, *names: str, **kwargs: object) -> None:
        self.options.append((names, kwargs))


class _StubParser:
    def __init__(self) -> None:
        self.group = _StubGroup()
        self.inis: dict[str, object] = {}

    def getgroup(self, name: str) -> _StubGroup:
        assert name == "harnessprobe"
        return self.group

    def addini(self, name: str, help: str, default: object = None) -> None:
        self.inis[name] = default


def _armed_config(
    tmp_path: Path, *, report: str | None = None, no_report: bool = False
) -> _StubConfig:
    (tmp_path / "target.py").write_text(INNER_SOURCE, encoding="utf-8")
    write_scope_file(
        build_scope_file(
            _scope_of("target.py"), allowlist=[], include_tier_b=True, generated_by="harnessprobe"
        ),
        tmp_path / "harnessprobe.scope.json",
    )
    config = _StubConfig(tmp_path, report=report, no_report=no_report)
    pytest_configure(config)
    return config


def _run_module_with_live_coverage(tmp_path: Path, config: _StubConfig) -> None:
    cov = coverage.Coverage(
        source=[str(tmp_path)], branch=True, data_file=str(tmp_path / ".coverage")
    )
    cov.start()
    try:
        spec = importlib.util.spec_from_file_location("hp_hook_target", tmp_path / "target.py")
        assert spec is not None
        assert spec.loader is not None
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        assert loaded.choose(True) == 1
        pytest_sessionfinish(_StubSession(config), 0)
    finally:
        cov.stop()


def _run_module_and_save_coverage(tmp_path: Path, module_name: str) -> None:
    cov = coverage.Coverage(
        source=[str(tmp_path)], branch=True, data_file=str(tmp_path / ".coverage")
    )
    cov.start()
    try:
        spec = importlib.util.spec_from_file_location(module_name, tmp_path / "target.py")
        assert spec is not None
        assert spec.loader is not None
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        assert loaded.choose(True) == 1
    finally:
        cov.stop()
    cov.save()


def _deactivate_live_collector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coverage.Coverage, "current", classmethod(lambda cls: None))
    monkeypatch.chdir(tmp_path)


LIVE_SUMMARY_LINE = "harnessprobe: LDH scope coverage 3/4 lines (75.00%), 1 uncovered samples"
ZERO_SUMMARY_LINE = "harnessprobe: LDH scope coverage 0/0 lines (n/a), 0 uncovered samples"


def test_addoption_registers_cli_options_and_ini() -> None:
    parser = _StubParser()
    pytest_addoption(parser)
    assert [names[0] for names, _ in parser.group.options] == [
        "--harnessprobe-scope",
        "--harnessprobe-report",
        "--harnessprobe-no-report",
    ]
    assert parser.group.options[0][1]["metavar"] == "PATH"
    assert parser.group.options[2][1]["action"] == "store_true"
    assert parser.inis == {"harnessprobe_scope": None, "harnessprobe_report": None}


def test_configure_stays_inert_without_scope(tmp_path: Path) -> None:
    config = _StubConfig(tmp_path)
    pytest_configure(config)
    pytest_sessionfinish(_StubSession(config), 0)
    assert config.pluginmanager.reporter.lines == []
    assert not (tmp_path / "harnessprobe.report.json").exists()


def test_configure_missing_explicit_scope_raises(tmp_path: Path) -> None:
    config = _StubConfig(tmp_path)
    config._options["harnessprobe_scope"] = "missing.scope.json"
    with pytest.raises(pytest.UsageError) as excinfo:
        pytest_configure(config)
    assert str(excinfo.value) == "harnessprobe: scope file not found: missing.scope.json"


def test_configure_invalid_scope_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.scope.json"
    bad.write_text("{not json", encoding="utf-8")
    config = _StubConfig(tmp_path)
    config._options["harnessprobe_scope"] = str(bad)
    with pytest.raises(pytest.UsageError) as excinfo:
        pytest_configure(config)
    assert str(excinfo.value).startswith(f"harnessprobe: invalid scope file {bad}")


def test_sessionfinish_writes_report_from_live_coverage(tmp_path: Path) -> None:
    config = _armed_config(tmp_path)
    _run_module_with_live_coverage(tmp_path, config)
    report_path = tmp_path / "harnessprobe.report.json"
    assert config.pluginmanager.reporter.lines == [
        LIVE_SUMMARY_LINE,
        f"harnessprobe: report written to {report_path}",
    ]
    report = SubsetReport.from_json(report_path.read_text(encoding="utf-8"))
    assert report.totals.scope_lines == 4
    assert report.totals.executed == 3
    assert report.totals.covered_pct == 75.0


def test_sessionfinish_writes_report_to_custom_path(tmp_path: Path) -> None:
    report_path = tmp_path / "nested" / "custom.report.json"
    config = _armed_config(tmp_path, report=str(report_path))
    _run_module_with_live_coverage(tmp_path, config)
    assert config.pluginmanager.reporter.lines == [
        LIVE_SUMMARY_LINE,
        f"harnessprobe: report written to {report_path}",
    ]
    assert report_path.is_file()


def test_sessionfinish_honors_no_report_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _armed_config(tmp_path, no_report=True)
    _run_module_and_save_coverage(tmp_path, "hp_no_report_target")
    _deactivate_live_collector(tmp_path, monkeypatch)
    pytest_sessionfinish(_StubSession(config), 0)
    assert config.pluginmanager.reporter.lines == [LIVE_SUMMARY_LINE, REPORT_DISABLED_MESSAGE]
    assert not (tmp_path / "harnessprobe.report.json").exists()


def test_sessionfinish_warns_without_coverage_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _armed_config(tmp_path)
    _deactivate_live_collector(tmp_path, monkeypatch)
    pytest_sessionfinish(_StubSession(config), 0)
    assert config.pluginmanager.reporter.lines == [NO_COVERAGE_MESSAGE]
    assert not (tmp_path / "harnessprobe.report.json").exists()


def test_sessionfinish_reads_saved_coverage_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _armed_config(tmp_path)
    _run_module_and_save_coverage(tmp_path, "hp_saved_target")
    _deactivate_live_collector(tmp_path, monkeypatch)
    pytest_sessionfinish(_StubSession(config), 0)
    report_path = tmp_path / "harnessprobe.report.json"
    assert config.pluginmanager.reporter.lines == [
        LIVE_SUMMARY_LINE,
        f"harnessprobe: report written to {report_path}",
    ]
    assert report_path.is_file()


def test_sessionfinish_uses_live_collector(tmp_path: Path) -> None:
    if coverage.Coverage.current() is None:
        pytest.skip("requires an active coverage collector")
    config = _armed_config(tmp_path)
    pytest_sessionfinish(_StubSession(config), 0)
    report_path = tmp_path / "harnessprobe.report.json"
    assert config.pluginmanager.reporter.lines == [
        ZERO_SUMMARY_LINE,
        f"harnessprobe: report written to {report_path}",
    ]
    assert report_path.is_file()


def test_sessionfinish_skips_sources_that_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _armed_config(tmp_path)
    _run_module_and_save_coverage(tmp_path, "hp_deleted_target")
    (tmp_path / "target.py").unlink()
    _deactivate_live_collector(tmp_path, monkeypatch)
    pytest_sessionfinish(_StubSession(config), 0)
    assert config.pluginmanager.reporter.lines == [
        ZERO_SUMMARY_LINE,
        f"harnessprobe: report written to {tmp_path / 'harnessprobe.report.json'}",
    ]
    report = SubsetReport.from_json(
        (tmp_path / "harnessprobe.report.json").read_text(encoding="utf-8")
    )
    assert report.totals.not_measured == 4
    assert report.totals.executed == 0


def test_write_lines_without_reporter_is_noop() -> None:
    _write_lines(None, ["ignored"])


def test_package_rejects_unknown_attribute() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'nope'"):
        _ = harnessprobe.nope


def test_entry_point_import_stays_light(pytester: pytest.Pytester) -> None:
    code = (
        "import sys, harnessprobe\n"
        "loaded = sorted(n for n in sys.modules if n.startswith('harnessprobe.'))\n"
        "print(loaded)\n"
        "print(harnessprobe.__version__)\n"
    )
    result = pytester.run("python", "-c", code)
    assert result.ret == 0
    assert result.stdout.str().strip().splitlines() == ["[]", "0.1.0"]


def test_session_end_writes_report_under_coverage(pytester: pytest.Pytester) -> None:
    _build_project(pytester)
    result = pytester.run("python", "-m", "coverage", "run", "--branch", "-m", "pytest", "-q")
    result.assert_outcomes(passed=1)
    stdout = result.stdout.str()
    assert "harnessprobe: LDH scope coverage" in stdout
    assert "harnessprobe: report written to" in stdout
    report_path = pytester.path / "harnessprobe.report.json"
    report = SubsetReport.from_json(report_path.read_text(encoding="utf-8"))
    assert report.schema == "harnessprobe.report/v1"
    assert report.totals.scope_lines == 4
    assert report.totals.executed == 3
    assert report.totals.not_measured == 0
    assert report.totals.covered_pct == 75.0
    assert (
        report.totals.scope_lines - report.totals.executed > 0
        or report.totals.branches_partial + report.totals.branches_missing > 0
    )
    samples = [sample for file_report in report.files for sample in file_report.samples]
    assert [(sample.path, sample.line, sample.text) for sample in samples] == [
        ("mod.py", UNCOVERED_LINE, "return None")
    ]


def test_session_end_warns_without_coverage(pytester: pytest.Pytester) -> None:
    _build_project(pytester)
    result = pytester.run("python", "-m", "pytest", "-q")
    result.assert_outcomes(passed=1)
    assert "harnessprobe: no coverage data found" in result.stdout.str()
    assert not (pytester.path / "harnessprobe.report.json").exists()


def test_missing_explicit_scope_is_usage_error(pytester: pytest.Pytester) -> None:
    result = pytester.run(
        "python", "-m", "pytest", "-q", "--harnessprobe-scope", "does-not-exist.json"
    )
    assert result.ret == 4
    assert "harnessprobe: scope file not found: does-not-exist.json" in result.stderr.str()


def test_malformed_scope_file_is_usage_error(pytester: pytest.Pytester) -> None:
    (pytester.path / "bad.scope.json").write_text("{not json", encoding="utf-8")
    result = pytester.run("python", "-m", "pytest", "-q", "--harnessprobe-scope", "bad.scope.json")
    assert result.ret == 4
    assert "harnessprobe: invalid scope file" in result.stderr.str()


def test_no_report_flag_skips_file(pytester: pytest.Pytester) -> None:
    _build_project(pytester)
    result = pytester.run(
        "python",
        "-m",
        "coverage",
        "run",
        "--branch",
        "-m",
        "pytest",
        "-q",
        "--harnessprobe-no-report",
    )
    result.assert_outcomes(passed=1)
    stdout = result.stdout.str()
    assert "harnessprobe: LDH scope coverage" in stdout
    assert "harnessprobe: report writing disabled (--harnessprobe-no-report)" in stdout
    assert not (pytester.path / "harnessprobe.report.json").exists()


def test_ini_scope_activates_plugin(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nharnessprobe_scope = custom.scope.json\n")
    pytester.makepyfile(test_ok="def test_ok():\n    assert True\n")
    scope = derive_scope(pytester.path)
    write_scope_file(
        build_scope_file(scope, allowlist=[], include_tier_b=True, generated_by="harnessprobe"),
        pytester.path / "custom.scope.json",
    )
    result = pytester.run("python", "-m", "pytest", "-q")
    result.assert_outcomes(passed=1)
    assert "harnessprobe: no coverage data found" in result.stdout.str()
    assert not (pytester.path / "harnessprobe.report.json").exists()
