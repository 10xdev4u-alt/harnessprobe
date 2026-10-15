#!/usr/bin/env python3
"""Shared LDH-scope extractor + coverage-subset analyzer (spikes R3b/R3c, same algorithm as R3).

LDH = LLM-dependent harness logic: code that consumes model/tool output.

Tier A = statement lines of functions whose body contains either
  (a) a call matching  chat\\.completions\\.create | litellm\\.(a)?completion | \\.invoke\\( | \\.ainvoke\\( | \\.generate\\(
      where the call target is an attribute chain (matched against `ast.unparse(func) + "("`), or
  (b) an attribute/subscript read whose attr name or leftmost base identifier matches
      ^(parsed|action|tool_call|model_output|response|completion|tool_calls|function_call)  (case-insensitive).
      Either direction matches (R3 semantics: `response.content` and `x.action` both count).

Tier B = statement lines of functions that call a Tier-A function defined in the same file, by
bare name (1 hop); Tier A wins when a function qualifies for both (R3 semantics).

Simplifications (documented for cross-repo comparability):
  - Detection walks the whole function subtree including nested defs, so a match inside a
    nested function marks all enclosing functions Tier A (R3 semantics).
  - Statement lines of a function exclude statements of nested functions/classes (the nested
    `def`/`class` line itself is included), because nested functions are scoped on their own.
  - Tier B name matching is textual per file; shadowed names can over-match.

Usage:
  ldh_scope.py extract <repo_root> <package_dir> <out_scope.json> [--rel-prefix P]
  ldh_scope.py analyze <scope.json> <coverage.json> <repo_root> <out_stats.json> [--samples N]
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

CALL_RE = re.compile(r"chat\.completions\.create|litellm\.a?completion|\.invoke\(|\.ainvoke\(|\.generate\(")
BASE_RE = re.compile(r"^(parsed|action|tool_call|model_output|response|completion|tool_calls|function_call)", re.I)


def is_ldh_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    try:
        text = ast.unparse(node.func)
    except Exception:
        return False
    return bool(CALL_RE.search(text + "("))


def _root_read_base(node: ast.AST) -> ast.Name | None:
    cur = node
    while isinstance(cur, (ast.Attribute, ast.Subscript)):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur
    return None


def is_ldh_read(node: ast.AST) -> bool:
    if not isinstance(node, (ast.Attribute, ast.Subscript)):
        return False
    if isinstance(node, ast.Attribute) and BASE_RE.match(node.attr):
        return True
    base = _root_read_base(node.value)
    return base is not None and bool(BASE_RE.match(base.id))


def func_stmt_lines(fn: ast.AST) -> set[int]:
    lines: set[int] = set()

    def rec(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lines.add(child.lineno)
                continue
            if isinstance(child, ast.stmt):
                lines.add(child.lineno)
            rec(child)

    rec(fn)
    return lines


class Scanner(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[ast.AST] = []
        self.tier_a: set[ast.AST] = set()
        self.calls: dict[ast.AST, set[str]] = {}

    def _visit_func(self, node: ast.AST) -> None:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_Call(self, node: ast.Call) -> None:
        if self.stack:
            if is_ldh_call(node):
                self.tier_a.update(self.stack)
            if isinstance(node.func, ast.Name):
                self.calls.setdefault(self.stack[-1], set()).add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                self.calls.setdefault(self.stack[-1], set()).add("." + node.func.attr)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.stack and is_ldh_read(node):
            self.tier_a.update(self.stack)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self.stack and is_ldh_read(node):
            self.tier_a.update(self.stack)
        self.generic_visit(node)


def extract(repo_root: Path, package: str, out_path: Path) -> dict:
    pkg_dir = repo_root / package
    files: dict[str, dict] = {}
    for py in sorted(pkg_dir.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        rel = str(py.relative_to(repo_root))
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        scanner = Scanner()
        scanner.visit(tree)
        if not scanner.tier_a:
            continue
        tier_a_names = {n.name for n in scanner.tier_a if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        tier_b: set[ast.AST] = set()
        for fn, call_names in scanner.calls.items():
            if fn in scanner.tier_a:
                continue
            if call_names & tier_a_names:
                tier_b.add(fn)
        a_lines: set[int] = set()
        for fn in scanner.tier_a:
            a_lines |= func_stmt_lines(fn)
        b_lines: set[int] = set()
        for fn in tier_b:
            b_lines |= func_stmt_lines(fn)
        files[rel] = {
            "tierA_functions": sorted(
                f"{n.name}:{n.lineno}" for n in scanner.tier_a if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            "tierB_functions": sorted(
                f"{n.name}:{n.lineno}" for n in tier_b if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            "tierA_lines": sorted(a_lines),
            "tierB_lines": sorted(b_lines),
        }
    out = {"package": package, "files": files}
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def analyze(scope_path: Path, cov_path: Path, repo_root: Path, out_path: Path, samples: int) -> dict:
    scope = json.loads(scope_path.read_text())
    cov = json.loads(cov_path.read_text())
    cov_files = {}
    for f, data in cov["files"].items():
        p = Path(f)
        if not p.is_absolute():
            p = repo_root / p
        cov_files[p.resolve()] = data

    def file_entry(rel: str):
        p = (repo_root / rel).resolve()
        return cov_files.get(p)

    def tier_stats(lines_attr: str) -> dict:
        ast_lines = 0
        measured = 0
        covered = 0
        branch_full = branch_partial = branch_missing = 0
        samples_out = []
        for rel, fdata in scope["files"].items():
            lines = set(fdata[lines_attr])
            ast_lines += len(lines)
            entry = file_entry(rel)
            if entry is None:
                continue
            ex = set(entry.get("executed_lines", []))
            mi = set(entry.get("missing_lines", []))
            meas = lines & (ex | mi)
            measured += len(meas)
            covd = meas & ex
            covered += len(covd)
            eb = entry.get("executed_branches", [])
            mb = entry.get("missing_branches", [])
            ex_arcs: dict[int, int] = {}
            mi_arcs: dict[int, int] = {}
            for src, _dst in eb:
                ex_arcs[src] = ex_arcs.get(src, 0) + 1
            for src, _dst in mb:
                mi_arcs[src] = mi_arcs.get(src, 0) + 1
            for ln in sorted(lines):
                e, m = ex_arcs.get(ln, 0), mi_arcs.get(ln, 0)
                if e == 0 and m == 0:
                    continue
                if m == 0:
                    branch_full += 1
                elif e == 0:
                    branch_missing += 1
                else:
                    branch_partial += 1
            per_file = sum(1 for s in samples_out if s["file"] == rel)
            for ln in sorted(lines & mi):
                if len(samples_out) < samples and per_file < 2:
                    text = ""
                    try:
                        src_lines = (repo_root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
                        if 0 < ln <= len(src_lines):
                            text = src_lines[ln - 1].strip()[:120]
                    except Exception:
                        pass
                    samples_out.append({"file": rel, "line": ln, "text": text})
                    per_file += 1
        pct = (100.0 * covered / measured) if measured else 0.0
        return {
            "ast_statement_lines": ast_lines,
            "measured_lines": measured,
            "executed": covered,
            "percent": round(pct, 2),
            "branch_full": branch_full,
            "branch_partial": branch_partial,
            "branch_missing": branch_missing,
            "uncovered_samples": samples_out,
        }

    totals = cov.get("totals", {})
    out = {
        "tierA": tier_stats("tierA_lines"),
        "tierB": tier_stats("tierB_lines"),
        "whole_repo": {
            "covered_lines": totals.get("covered_lines"),
            "num_statements": totals.get("num_statements"),
            "percent_covered": totals.get("percent_covered"),
            "covered_branches": totals.get("covered_branches"),
            "num_branches": totals.get("num_branches"),
            "percent_covered_display": totals.get("percent_covered_display"),
        },
    }
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    return out


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    cmd = args[0]
    if cmd == "extract":
        repo_root, package, out = Path(args[1]), args[2], Path(args[3])
        res = extract(repo_root, package, out)
        n_files = len(res["files"])
        n_a = sum(len(f["tierA_lines"]) for f in res["files"].values())
        n_b = sum(len(f["tierB_lines"]) for f in res["files"].values())
        print(f"scope: {n_files} files, tierA {n_a} stmt lines, tierB {n_b} stmt lines -> {out}")
    elif cmd == "analyze":
        scope, cov, repo_root, out = Path(args[1]), Path(args[2]), Path(args[3]), Path(args[4])
        samp = 10
        if "--samples" in args:
            samp = int(args[args.index("--samples") + 1])
        res = analyze(scope, cov, repo_root, out, samp)
        for tier in ("tierA", "tierB"):
            t = res[tier]
            print(
                f"{tier}: {t['executed']}/{t['measured_lines']} measured lines ({t['percent']}%) "
                f"of {t['ast_statement_lines']} ast lines; branches full/partial/missing = "
                f"{t['branch_full']}/{t['branch_partial']}/{t['branch_missing']}"
            )
        w = res["whole_repo"]
        print(f"whole repo: {w['covered_lines']}/{w['num_statements']} ({w['percent_covered_display']}%)")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
