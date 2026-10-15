"""Heuristic LDH scope extraction for Python repositories."""

from __future__ import annotations

import ast
import fnmatch
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

MODEL_CALL_RE = re.compile(
    r"chat\.completions\.create|litellm\.a?completion|\.invoke\(|\.ainvoke\(|\.generate\("
)

CONSUMER_PREFIXES = (
    "parsed",
    "action",
    "tool_call",
    "model_output",
    "response",
    "completion",
    "tool_calls",
    "function_call",
    "partial_response",
    "raw_response",
    "response_text",
    "model_text",
)

CONSUMER_NEGATIVES = ("parsed_args", "parser_")
SHELL_COMPLETION_LIBS = frozenset({"argparse", "argcomplete", "click", "typer"})
COMPLETION_LIKE_PREFIXES = ("completion", "completions")
SKIPPED_DIR_NAMES = frozenset(
    {"tests", "test", "testing", ".venv", "venv", "build", "dist", "node_modules"}
)
ANNOTATION_RE = re.compile(r"#\s*harness:llm-source")

HitPredicate = Callable[[ast.AST], bool]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class FileScope:
    """Scoped statement lines and reasons for one repo-relative file."""

    path: str
    lines: tuple[int, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SourceSite:
    """One observed evidence site: a model call or an annotation."""

    kind: str
    path: str
    line: int


@dataclass(frozen=True)
class Scope:
    """Heuristic LDH scope over a repository."""

    files: tuple[FileScope, ...]
    warnings: tuple[str, ...]
    sources: tuple[SourceSite, ...] = ()

    def line_map(self) -> dict[str, set[int]]:
        """Return a path to line-set mapping for every scoped file."""
        return {file_scope.path: set(file_scope.lines) for file_scope in self.files}

    @property
    def total_lines(self) -> int:
        """Count every scoped statement line across all files."""
        return sum(len(file_scope.lines) for file_scope in self.files)


def derive_scope(
    repo_root: Path,
    *,
    allowlist: Sequence[str] = (),
    include_tier_b: bool = True,
) -> Scope:
    """Extract the heuristic LDH scope for every Python file under repo_root."""
    files: list[FileScope] = []
    warnings: list[str] = []
    sources: list[SourceSite] = []
    for path in sorted(repo_root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        allowlisted = any(fnmatch.fnmatchcase(rel, pattern) for pattern in allowlist)
        if not allowlisted and _is_skipped(rel):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            warnings.append(f"skipped {rel}: {exc}")
            continue
        sources.extend(_file_sources(tree, source, rel=rel))
        lines, reasons = _file_scope(
            tree, source, allowlisted=allowlisted, include_tier_b=include_tier_b
        )
        if lines:
            files.append(
                FileScope(path=rel, lines=tuple(sorted(lines)), reasons=tuple(sorted(reasons)))
            )
    sources.sort(key=lambda site: (site.path, site.line, site.kind))
    return Scope(files=tuple(files), warnings=tuple(warnings), sources=tuple(sources))


def _is_skipped(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in SKIPPED_DIR_NAMES for part in parts[:-1]):
        return True
    name = parts[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _file_scope(
    tree: ast.Module,
    source: str,
    *,
    allowlisted: bool,
    include_tier_b: bool,
) -> tuple[set[int], set[str]]:
    lines: set[int] = set()
    reasons: set[str] = set()
    annotation_lines, annotated_defs = _annotation_scope(tree, source)
    if annotation_lines:
        lines |= annotation_lines
        reasons.add("annotation")
    if allowlisted:
        lines |= _all_statement_lines(tree)
        reasons.add("allowlist")
        return lines, reasons
    shell_file = _imports_shell_completion_libs(tree)
    tier_a_fns = _scan_tier_a(tree, shell_file=shell_file)
    tier_a_lines = _tier_a_lines(tier_a_fns, annotated_defs, shell_file=shell_file)
    if tier_a_lines:
        lines |= tier_a_lines
        reasons.add("heuristic:tier-a")
    if include_tier_b:
        tier_b_lines = _tier_b_lines(tree, tier_a_fns, annotated_defs)
        if tier_b_lines:
            lines |= tier_b_lines
            reasons.add("heuristic:tier-b")
    return lines, reasons


def _is_model_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    return bool(MODEL_CALL_RE.search(ast.unparse(node.func) + "("))


def _is_consumer_name(name: str, *, shell_file: bool) -> bool:
    lowered = name.lower()
    if lowered.startswith(CONSUMER_NEGATIVES):
        return False
    if shell_file and lowered.startswith(COMPLETION_LIKE_PREFIXES):
        return False
    return lowered.startswith(CONSUMER_PREFIXES)


def _is_consumer_ref(node: ast.AST, *, shell_file: bool) -> bool:
    if isinstance(node, ast.Name):
        return isinstance(node.ctx, ast.Load) and _is_consumer_name(node.id, shell_file=shell_file)
    if isinstance(node, ast.Attribute):
        return isinstance(node.ctx, ast.Load) and _is_consumer_name(
            node.attr, shell_file=shell_file
        )
    return False


def _statement_hits(node: ast.AST, predicate: HitPredicate) -> bool:
    if predicate(node):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        signature: list[ast.AST] = [*node.decorator_list, node.args]
        if node.returns is not None:
            signature.append(node.returns)
        return any(_statement_hits(part, predicate) for part in signature)
    if isinstance(node, ast.ClassDef):
        parts: list[ast.AST] = [*node.decorator_list, *node.bases, *node.keywords]
        return any(_statement_hits(part, predicate) for part in parts)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if _statement_hits(child, predicate):
            return True
    return False


def _body_statements(parent: ast.AST) -> Iterator[ast.stmt]:
    for child in ast.iter_child_nodes(parent):
        if isinstance(child, ast.stmt):
            yield child
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield from _body_statements(child)
        else:
            yield from _body_statements(child)


def _all_statement_lines(tree: ast.Module) -> set[int]:
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)}


def _all_functions(tree: ast.Module) -> list[FunctionNode]:
    return [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _imports_shell_completion_libs(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in SHELL_COMPLETION_LIBS:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in SHELL_COMPLETION_LIBS:
                return True
    return False


def _file_sources(tree: ast.Module, source: str, *, rel: str) -> list[SourceSite]:
    sites = [
        SourceSite(kind="model_call", path=rel, line=node.lineno)
        for node in ast.walk(tree)
        if _is_model_call(node)
    ]
    sites.extend(
        SourceSite(kind="annotation", path=rel, line=number)
        for number in _marked_annotation_lines(source)
    )
    return sites


def _marked_annotation_lines(source: str) -> set[int]:
    return {
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if ANNOTATION_RE.search(line)
    }


def _annotation_scope(tree: ast.Module, source: str) -> tuple[set[int], set[int]]:
    marked = _marked_annotation_lines(source)
    if not marked:
        return set(), set()
    defs = {
        node.lineno: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    statement_lines = _all_statement_lines(tree)
    lines: set[int] = set()
    annotated_defs: set[int] = set()
    for number in marked:
        node = defs.get(number)
        if node is not None:
            annotated_defs.add(number)
            lines |= {statement.lineno for statement in _body_statements(node)}
        elif number in statement_lines:
            lines.add(number)
    return lines, annotated_defs


class _TierAScanner(ast.NodeVisitor):
    def __init__(self, *, shell_file: bool) -> None:
        self.shell_file = shell_file
        self.stack: list[ast.AST] = []
        self.tier_a: set[ast.AST] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if self.stack and _is_model_call(node):
            self.tier_a.update(self.stack)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self.stack and _is_consumer_ref(node, shell_file=self.shell_file):
            self.tier_a.update(self.stack)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.stack and _is_consumer_ref(node, shell_file=self.shell_file):
            self.tier_a.update(self.stack)
        self.generic_visit(node)


def _scan_tier_a(tree: ast.Module, *, shell_file: bool) -> set[FunctionNode]:
    scanner = _TierAScanner(shell_file=shell_file)
    scanner.visit(tree)
    return {
        node for node in scanner.tier_a if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _tier_a_lines(
    tier_a_fns: set[FunctionNode],
    annotated_defs: set[int],
    *,
    shell_file: bool,
) -> set[int]:
    def predicate(node: ast.AST) -> bool:
        return _is_model_call(node) or _is_consumer_ref(node, shell_file=shell_file)

    lines: set[int] = set()
    for fn in tier_a_fns:
        if fn.lineno in annotated_defs:
            continue
        for statement in _body_statements(fn):
            if _statement_hits(statement, predicate):
                lines.add(statement.lineno)
    return lines


def _tier_b_lines(
    tree: ast.Module,
    tier_a_fns: set[FunctionNode],
    annotated_defs: set[int],
) -> set[int]:
    names = {fn.name for fn in tier_a_fns}
    if not names:
        return set()

    def predicate(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if isinstance(node.func, ast.Name):
            return node.func.id in names
        return isinstance(node.func, ast.Attribute) and node.func.attr in names

    lines: set[int] = set()
    for fn in _all_functions(tree):
        if fn in tier_a_fns or fn.lineno in annotated_defs:
            continue
        for statement in _body_statements(fn):
            if _statement_hits(statement, predicate):
                lines.add(statement.lineno)
    return lines
