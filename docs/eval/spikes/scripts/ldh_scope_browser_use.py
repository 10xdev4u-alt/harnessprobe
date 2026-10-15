#!/usr/bin/env python3
"""R3: deterministic AST extractor for LDH scope (Tier A / Tier B) over browser-use source.

Tier A: statement lines in functions whose body (whole subtree, incl. nested defs)
  contains either
  (a) a call whose attribute chain matches
      chat.completions.create | litellm.completion | litellm.acompletion |
      <...>.invoke | <...>.ainvoke | <...>.generate
  (b) an Attribute or Subscript read whose attribute/base identifier starts with
      parsed|action|tool_call|model_output|response|completion|tool_calls|function_call
      (case-insensitive)
Tier B: statement lines in functions that call a Tier-A function by bare name in the
  same file (1 hop).

Line collection for a function: all ast.stmt descendants, descending through control
flow (if/for/while/try/with/match) but NOT into nested FunctionDef/AsyncFunctionDef/
ClassDef bodies (those are scored as their own functions). Tier A wins over Tier B
for a function that qualifies for both.

Usage: ldh_scope.py <repo_root> <source_root> <out_scope.json>
"""
import ast
import json
import re
import sys
from pathlib import Path

CALL_CHAIN = re.compile(r"(chat\.completions\.create$|litellm\.(a)?completion$)")
CALL_SUFFIX = re.compile(r"\.(invoke|ainvoke|generate)$")
READ_RE = re.compile(
    r"^(parsed|action|tool_call|model_output|response|completion|tool_calls|function_call)",
    re.IGNORECASE,
)


def dotted_name(node: ast.AST) -> str | None:
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def root_name(node: ast.AST) -> str | None:
    cur = node
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    while isinstance(cur, ast.Subscript):
        cur = cur.value
    return cur.id if isinstance(cur, ast.Name) else None


def call_matches(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute):
        return False
    name = dotted_name(call.func)
    if not name:
        return False
    return bool(CALL_CHAIN.search(name) or CALL_SUFFIX.search(name))


def read_matches(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        if READ_RE.match(node.attr):
            return True
        root = root_name(node)
        return bool(root and READ_RE.match(root))
    if isinstance(node, ast.Subscript):
        root = root_name(node.value)
        if root and READ_RE.match(root):
            return True
        if isinstance(node.value, ast.Attribute) and READ_RE.match(node.value.attr):
            return True
    return False


def func_matches(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for n in ast.walk(func):
        if isinstance(n, ast.Call) and call_matches(n):
            return True
        if isinstance(n, (ast.Attribute, ast.Subscript)) and read_matches(n):
            return True
    return False


def collect_stmt_lines(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    lines: set[int] = set()
    stack = list(ast.iter_child_nodes(func))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(n, ast.stmt):
            lines.add(n.lineno)
        stack.extend(ast.iter_child_nodes(n))
    return lines


def calls_bare_name(func: ast.FunctionDef | ast.AsyncFunctionDef, names: set[str]) -> bool:
    if not names:
        return False
    for n in ast.walk(func):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names:
            return True
    return False


def analyze_file(path: Path, repo_root: Path) -> tuple[str, dict] | None:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"SKIP {path}: {exc}", file=sys.stderr)
        return None

    funcs = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    tier_a = {f for f in funcs if func_matches(f)}
    tier_a_names = {f.name for f in tier_a}
    tier_a_lines: set[int] = set()
    tier_b_lines: set[int] = set()
    for f in funcs:
        if f in tier_a:
            tier_a_lines |= collect_stmt_lines(f)
        elif calls_bare_name(f, tier_a_names):
            tier_b_lines |= collect_stmt_lines(f)
    tier_b_lines -= tier_a_lines
    if not tier_a_lines and not tier_b_lines:
        return None
    rel = path.relative_to(repo_root).as_posix()
    return rel, {
        "tierA_lines": sorted(tier_a_lines),
        "tierB_lines": sorted(tier_b_lines),
    }


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repo_root = Path(sys.argv[1]).resolve()
    source_root = Path(sys.argv[2]).resolve()
    out_path = Path(sys.argv[3])

    scope: dict[str, dict] = {}
    for path in sorted(source_root.rglob('*.py')):
        rel_parts = path.relative_to(repo_root).parts
        if 'tests' in rel_parts:
            continue
        result = analyze_file(path, repo_root)
        if result:
            scope[result[0]] = result[1]

    out_path.write_text(json.dumps(scope, indent=1, sort_keys=True) + "\n")
    a = sum(len(v["tierA_lines"]) for v in scope.values())
    b = sum(len(v["tierB_lines"]) for v in scope.values())
    print(f"files_in_scope={len(scope)} tierA_lines={a} tierB_lines={b}")


if __name__ == '__main__':
    main()
