from __future__ import annotations

from pathlib import Path

from harnessprobe.scope import SourceSite, derive_scope

MINI_LINE_MAP = {
    "mini_repo/agent.py": {14, 18, 21},
    "mini_repo/dispatch.py": {7, 13},
    "mini_repo/parsing.py": {5, 6, 8, 12, 13, 14},
    "mini_repo/text_tools.py": {5, 6, 7, 12, 13},
    "mini_repo/unrelated.py": {10, 15, 16},
}

MINI_REASONS = {
    "mini_repo/agent.py": ("heuristic:tier-a",),
    "mini_repo/dispatch.py": ("heuristic:tier-a", "heuristic:tier-b"),
    "mini_repo/parsing.py": ("heuristic:tier-a",),
    "mini_repo/text_tools.py": ("annotation", "heuristic:tier-a"),
    "mini_repo/unrelated.py": ("annotation",),
}


def test_mini_repo_line_map_is_exact(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    assert scope.line_map() == MINI_LINE_MAP


def test_mini_repo_reasons_are_exact(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    reasons = {file_scope.path: file_scope.reasons for file_scope in scope.files}
    assert reasons == MINI_REASONS


def test_mini_repo_total_lines_and_warnings(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    assert scope.total_lines == 19
    assert scope.warnings == ()


MINI_SOURCES = (
    SourceSite(kind="model_call", path="mini_repo/agent.py", line=14),
    SourceSite(kind="annotation", path="mini_repo/text_tools.py", line=11),
    SourceSite(kind="annotation", path="mini_repo/unrelated.py", line=10),
    SourceSite(kind="annotation", path="mini_repo/unrelated.py", line=14),
)


def test_mini_repo_sources_are_exact(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    assert scope.sources == MINI_SOURCES


def test_mini_repo_sources_sorted_by_path_line_kind(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    keys = [(site.path, site.line, site.kind) for site in scope.sources]
    assert keys == sorted(keys)


def test_sources_empty_when_no_calls_or_annotations(tmp_path: Path) -> None:
    (tmp_path / "plain.py").write_text("def f(x):\n    return x + 1\n")
    scope = derive_scope(tmp_path)
    assert scope.sources == ()
    assert scope.files == ()


def test_module_level_model_call_is_a_source(tmp_path: Path) -> None:
    (tmp_path / "top.py").write_text(
        "MODEL = llm.invoke\nclient.chat.completions.create(model='m')\n"
    )
    scope = derive_scope(tmp_path)
    assert scope.sources == (SourceSite(kind="model_call", path="top.py", line=2),)


def test_allowlisted_file_sources_are_still_collected(tmp_path: Path) -> None:
    (tmp_path / "w.py").write_text("def ask(c):\n    return c.chat.completions.create(model='m')\n")
    scope = derive_scope(tmp_path, allowlist=["w.py"])
    assert scope.sources == (SourceSite(kind="model_call", path="w.py", line=2),)


def test_no_tier_b_leaves_sources_unchanged(fixtures_root: Path) -> None:
    assert derive_scope(fixtures_root, include_tier_b=False).sources == MINI_SOURCES


def test_paths_lines_and_reasons_are_sorted(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    paths = [file_scope.path for file_scope in scope.files]
    assert paths == sorted(paths)
    for file_scope in scope.files:
        assert list(file_scope.lines) == sorted(set(file_scope.lines))
        assert list(file_scope.reasons) == sorted(set(file_scope.reasons))


def test_cli_file_with_negative_names_is_out_of_scope(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    assert "mini_repo/cli.py" not in scope.line_map()


def test_tier_b_can_be_disabled(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root, include_tier_b=False)
    assert scope.line_map()["mini_repo/dispatch.py"] == {7}
    reasons = {file_scope.path: file_scope.reasons for file_scope in scope.files}
    assert reasons["mini_repo/dispatch.py"] == ("heuristic:tier-a",)
    assert scope.total_lines == 18


def test_tier_b_caller_scoped_by_attribute_call(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    dispatch = scope.line_map()["mini_repo/dispatch.py"]
    assert dispatch == {7, 13}
    assert 12 not in dispatch
    assert 14 not in dispatch


def test_narrowing_drops_logging_only_statements(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    agent = scope.line_map()["mini_repo/agent.py"]
    assert 13 not in agent
    assert 20 not in agent
    assert agent == {14, 18, 21}


def test_narrowing_drops_non_consumer_branches(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    assert 7 not in scope.line_map()["mini_repo/parsing.py"]
    assert 19 not in scope.line_map()["mini_repo/agent.py"]


def test_model_call_variants_are_detected(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "def a(prompt):\n"
        "    return llm.ainvoke(prompt)\n"
        "\n"
        "\n"
        "def b(text):\n"
        "    out = model.generate(text)\n"
        "    return out\n"
    )
    scope = derive_scope(tmp_path)
    assert scope.line_map() == {"m.py": {2, 6}}


def test_def_annotation_covers_whole_body(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    text_tools = scope.line_map()["mini_repo/text_tools.py"]
    assert {12, 13} <= text_tools
    assert 11 not in text_tools


def test_statement_annotation_covers_one_line(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    unrelated = scope.line_map()["mini_repo/unrelated.py"]
    assert 10 in unrelated
    assert 11 not in unrelated


def test_annotated_function_is_not_double_counted(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root)
    reasons = {file_scope.path: file_scope.reasons for file_scope in scope.files}
    assert reasons["mini_repo/unrelated.py"] == ("annotation",)


def test_allowlist_puts_file_fully_in_scope(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root, allowlist=["mini_repo/cli.py"])
    by_path = {file_scope.path: file_scope for file_scope in scope.files}
    assert by_path["mini_repo/cli.py"].lines == (1, 2, 5, 6, 7, 8, 11, 12, 13)
    assert by_path["mini_repo/cli.py"].reasons == ("allowlist",)


def test_allowlist_replaces_heuristic_reasons(fixtures_root: Path) -> None:
    scope = derive_scope(fixtures_root, allowlist=["mini_repo/parsing.py"])
    by_path = {file_scope.path: file_scope for file_scope in scope.files}
    assert by_path["mini_repo/parsing.py"].lines == (1, 4, 5, 6, 7, 8, 11, 12, 13, 14)
    assert by_path["mini_repo/parsing.py"].reasons == ("allowlist",)


def test_default_skips_test_dirs_and_files(tmp_path: Path) -> None:
    body = (
        "def ask(client):\n"
        "    response = client.chat.completions.create(model='m')\n"
        "    return response.content\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "helper.py").write_text(body)
    (tmp_path / "test_widget.py").write_text(body)
    (tmp_path / "widget_test.py").write_text(body)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text(body)
    assert derive_scope(tmp_path).files == ()


def test_allowlist_overrides_skip_rules(tmp_path: Path) -> None:
    body = (
        "def ask(client):\n"
        "    response = client.chat.completions.create(model='m')\n"
        "    return response.content\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "helper.py").write_text(body)
    scope = derive_scope(tmp_path, allowlist=["tests/helper.py"])
    assert scope.line_map() == {"tests/helper.py": {1, 2, 3}}


def test_syntax_error_warns_and_skips_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def f(:\n")
    scope = derive_scope(tmp_path)
    assert scope.files == ()
    assert len(scope.warnings) == 1
    assert "broken.py" in scope.warnings[0]


def test_tier_b_bare_name_call(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(
        "def consume(payload):\n"
        "    if payload.response:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "\n"
        "def run(payload):\n"
        "    print('go')\n"
        "    return consume(payload)\n"
    )
    scope = derive_scope(tmp_path)
    assert scope.line_map() == {"a.py": {2, 9}}


def test_completion_root_scoped_without_shell_import(tmp_path: Path) -> None:
    (tmp_path / "w.py").write_text(
        "def f(completion):\n    text = completion.strip()\n    return text\n"
    )
    assert derive_scope(tmp_path).line_map() == {"w.py": {2}}


def test_completion_root_excluded_with_click_import(tmp_path: Path) -> None:
    (tmp_path / "c.py").write_text(
        "import click\n\ndef f(completion):\n    text = completion.strip()\n    return text\n"
    )
    assert derive_scope(tmp_path).files == ()


def test_parsed_args_negative(tmp_path: Path) -> None:
    (tmp_path / "p.py").write_text("def f(args):\n    parsed_args = args\n    return parsed_args\n")
    assert derive_scope(tmp_path).files == ()
