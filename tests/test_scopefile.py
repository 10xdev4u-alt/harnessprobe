from __future__ import annotations

from pathlib import Path

import pytest

from harnessprobe import scope_from_file
from harnessprobe.scope import FileScope, Scope, derive_scope
from harnessprobe.scopefile import (
    ScopeFile,
    ScopeFileEntry,
    ScopeSource,
    build_scope_file,
    write_scope_file,
)

GENERATED_BY = "harnessprobe"

AUTHORITATIVE_NOTE = "annotations are user-declared; treated as authoritative"
ALLOWLISTED_NOTE = "allowlisted files are scoped whole by user declaration"
TIER_A_NOTE = "tier A: model-call and same-function consumer statements (heuristic)"
TIER_B_NOTE = "tier B: one-hop calls into tier-A functions; expect false positives"
TIER_B_DISABLED_NOTE = "tier B reachability disabled (--no-tier-b)"


def build(
    fixtures_root: Path,
    *,
    allowlist: tuple[str, ...] = (),
    echo_allowlist: tuple[str, ...] = (),
    include_tier_b: bool = True,
) -> ScopeFile:
    scope = derive_scope(fixtures_root, allowlist=allowlist, include_tier_b=include_tier_b)
    return build_scope_file(
        scope,
        allowlist=echo_allowlist,
        include_tier_b=include_tier_b,
        generated_by=GENERATED_BY,
    )


def test_schema_and_json_indent_and_round_trip(fixtures_root: Path) -> None:
    scope_file = build(fixtures_root)
    assert scope_file.schema == "harnessprobe.scope/v1"
    text = scope_file.to_json()
    assert text.startswith('{\n  "schema": "harnessprobe.scope/v1",\n  "generated_by":')
    assert ScopeFile.from_json(text) == scope_file


def test_allowlist_echoed_in_order(fixtures_root: Path) -> None:
    scope_file = build(
        fixtures_root,
        allowlist=("mini_repo/cli.py",),
        echo_allowlist=("mini_repo/cli.py", "mini_repo/unrelated.py"),
    )
    assert scope_file.allowlist == ["mini_repo/cli.py", "mini_repo/unrelated.py"]
    assert scope_file.include_tier_b is True


def test_sources_and_entries_map_from_scope(fixtures_root: Path) -> None:
    scope_file = build(fixtures_root)
    assert scope_file.sources == [
        ScopeSource(kind="model_call", path="mini_repo/agent.py", line=14),
        ScopeSource(kind="annotation", path="mini_repo/text_tools.py", line=11),
        ScopeSource(kind="annotation", path="mini_repo/unrelated.py", line=10),
        ScopeSource(kind="annotation", path="mini_repo/unrelated.py", line=14),
    ]
    entries = {entry.path: entry for entry in scope_file.files}
    assert entries["mini_repo/agent.py"] == ScopeFileEntry(
        path="mini_repo/agent.py",
        ldh_lines=3,
        lines=[14, 18, 21],
        confidence="heuristic-high",
        reasons=["heuristic:tier-a"],
    )
    assert entries["mini_repo/text_tools.py"] == ScopeFileEntry(
        path="mini_repo/text_tools.py",
        ldh_lines=5,
        lines=[5, 6, 7, 12, 13],
        confidence="authoritative",
        reasons=["annotation", "heuristic:tier-a"],
    )


def test_confidence_annotation_wins_over_heuristic(fixtures_root: Path) -> None:
    scope_file = build(fixtures_root)
    by_path = {entry.path: entry.confidence for entry in scope_file.files}
    assert by_path["mini_repo/unrelated.py"] == "authoritative"
    assert by_path["mini_repo/text_tools.py"] == "authoritative"
    assert by_path["mini_repo/agent.py"] == "heuristic-high"
    assert by_path["mini_repo/dispatch.py"] == "heuristic-high"
    assert by_path["mini_repo/parsing.py"] == "heuristic-high"


def test_confidence_allowlisted_wins_over_heuristic(fixtures_root: Path) -> None:
    scope_file = build(
        fixtures_root,
        allowlist=("mini_repo/agent.py",),
        echo_allowlist=("mini_repo/agent.py",),
    )
    by_path = {entry.path: entry.confidence for entry in scope_file.files}
    assert by_path["mini_repo/agent.py"] == "allowlisted"


def test_confidence_tier_b_only_is_heuristic_low() -> None:
    scope = Scope(
        files=(FileScope(path="caller.py", lines=(2,), reasons=("heuristic:tier-b",)),),
        warnings=(),
    )
    scope_file = build_scope_file(
        scope, allowlist=[], include_tier_b=True, generated_by=GENERATED_BY
    )
    assert scope_file.files == [
        ScopeFileEntry(
            path="caller.py",
            ldh_lines=1,
            lines=[2],
            confidence="heuristic-low",
            reasons=["heuristic:tier-b"],
        )
    ]


def test_reasonless_file_is_rejected() -> None:
    scope = Scope(files=(FileScope(path="x.py", lines=(1,), reasons=()),), warnings=())
    with pytest.raises(ValueError, match="no confidence reason"):
        build_scope_file(scope, allowlist=[], include_tier_b=True, generated_by=GENERATED_BY)


def test_notes_list_only_present_classes_in_fixed_order(fixtures_root: Path) -> None:
    scope_file = build(fixtures_root)
    assert scope_file.confidence_notes == [AUTHORITATIVE_NOTE, TIER_A_NOTE]


def test_notes_cover_all_four_classes_in_fixed_order() -> None:
    scope = Scope(
        files=(
            FileScope(path="a.py", lines=(1,), reasons=("annotation",)),
            FileScope(path="b.py", lines=(1,), reasons=("allowlist",)),
            FileScope(path="c.py", lines=(1,), reasons=("heuristic:tier-a",)),
            FileScope(path="d.py", lines=(1,), reasons=("heuristic:tier-b",)),
        ),
        warnings=(),
    )
    scope_file = build_scope_file(
        scope, allowlist=[], include_tier_b=True, generated_by=GENERATED_BY
    )
    assert [entry.confidence for entry in scope_file.files] == [
        "authoritative",
        "allowlisted",
        "heuristic-high",
        "heuristic-low",
    ]
    assert scope_file.confidence_notes == [
        AUTHORITATIVE_NOTE,
        ALLOWLISTED_NOTE,
        TIER_A_NOTE,
        TIER_B_NOTE,
    ]


def test_notes_append_tier_b_disabled(fixtures_root: Path) -> None:
    scope_file = build(fixtures_root, include_tier_b=False)
    assert scope_file.include_tier_b is False
    assert scope_file.confidence_notes == [
        AUTHORITATIVE_NOTE,
        TIER_A_NOTE,
        TIER_B_DISABLED_NOTE,
    ]


def test_warnings_are_preserved(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def f(:\n")
    scope = derive_scope(tmp_path)
    scope_file = build_scope_file(
        scope, allowlist=[], include_tier_b=True, generated_by=GENERATED_BY
    )
    assert scope_file.warnings == list(scope.warnings)
    assert len(scope_file.warnings) == 1
    assert "broken.py" in scope_file.warnings[0]


def test_entries_and_sources_are_sorted_and_deterministic(fixtures_root: Path) -> None:
    first = build(fixtures_root)
    second = build(fixtures_root)
    assert first.to_json() == second.to_json()
    paths = [entry.path for entry in first.files]
    assert paths == sorted(paths)
    source_keys = [(source.path, source.line, source.kind) for source in first.sources]
    assert source_keys == sorted(source_keys)
    for entry in first.files:
        assert entry.lines == sorted(entry.lines)
        assert entry.ldh_lines == len(entry.lines)


def test_scope_from_file_round_trips_derived_scope(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    scope_file = build_scope_file(
        scope, allowlist=[], include_tier_b=True, generated_by=GENERATED_BY
    )
    restored = scope_from_file(ScopeFile.from_json(scope_file.to_json()))
    assert restored.files == scope.files
    assert restored.warnings == scope.warnings
    assert restored.sources == scope.sources


def test_write_scope_file_writes_json(fixtures_root: Path, tmp_path: Path) -> None:
    scope_file = build(fixtures_root)
    out = tmp_path / "harnessprobe.scope.json"
    written = write_scope_file(scope_file, out)
    assert written == out
    assert ScopeFile.from_json(out.read_text(encoding="utf-8")) == scope_file
