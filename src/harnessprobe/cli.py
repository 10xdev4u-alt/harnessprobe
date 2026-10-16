"""Command-line interface for HarnessProbe."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from harnessprobe import __version__
from harnessprobe.comment import load_findings, render_pr_comment
from harnessprobe.report import SubsetReport
from harnessprobe.scope import derive_scope
from harnessprobe.scopefile import CONFIDENCE_ORDER, ScopeFile, build_scope_file, write_scope_file


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    args = _build_parser().parse_args(argv)
    if args.command == "comment":
        return _run_comment(args)
    return _run_init(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harnessprobe",
        description="Extract the LLM-dependent harness scope of a repository.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser(
        "init", help="Write a heuristic scope file for a repository."
    )
    init_parser.add_argument("path", nargs="?", default=".", help="Repository root (default: .)")
    init_parser.add_argument(
        "--allowlist",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern of files to scope whole; repeatable.",
    )
    init_parser.add_argument(
        "--no-tier-b", action="store_true", help="Disable tier B reachability."
    )
    init_parser.add_argument(
        "--out", type=Path, default=None, metavar="PATH", help="Scope file path."
    )
    comment_parser = subparsers.add_parser(
        "comment", help="Render a bug-class-first PR comment from a report."
    )
    comment_parser.add_argument(
        "--report", type=Path, required=True, metavar="PATH", help="Coverage subset report JSON."
    )
    comment_parser.add_argument(
        "--findings",
        type=Path,
        default=None,
        metavar="PATH",
        help="Findings JSON attached to this run.",
    )
    comment_parser.add_argument(
        "--previous",
        type=Path,
        default=None,
        metavar="PATH",
        help="Previous coverage subset report JSON for the trend.",
    )
    comment_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write the comment here instead of stdout.",
    )
    return parser


def _run_comment(args: argparse.Namespace) -> int:
    try:
        report = _load_report(args.report, "report")
        findings = load_findings(args.findings) if args.findings is not None else []
        previous = (
            _load_report(args.previous, "previous report") if args.previous is not None else None
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    comment = render_pr_comment(report, findings=findings, previous=previous)
    if args.out is None:
        sys.stdout.write(comment)
        return 0
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(comment, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    return 0


def _load_report(path: Path, label: str) -> SubsetReport:
    try:
        text = path.read_text(encoding="utf-8")
        return SubsetReport.from_json(text)
    except OSError as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"invalid {label} {path}: {exc}") from exc


def _run_init(args: argparse.Namespace) -> int:
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"error: path does not exist: {path}", file=sys.stderr)
        return 1
    if not path.is_dir():
        print(f"error: not a directory: {path}", file=sys.stderr)
        return 1
    include_tier_b = not args.no_tier_b
    scope = derive_scope(path, allowlist=args.allowlist, include_tier_b=include_tier_b)
    for warning in scope.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    scope_file = build_scope_file(
        scope,
        allowlist=args.allowlist,
        include_tier_b=include_tier_b,
        generated_by="harnessprobe",
    )
    out = Path(args.out).resolve() if args.out is not None else path / "harnessprobe.scope.json"
    try:
        write_scope_file(scope_file, out)
    except OSError as exc:
        print(f"error: cannot write {out}: {exc}", file=sys.stderr)
        return 1
    _print_summary(scope_file, path=path, out=out)
    return 0


def _print_summary(scope_file: ScopeFile, *, path: Path, out: Path) -> None:
    model_calls = sum(1 for source in scope_file.sources if source.kind == "model_call")
    annotations = len(scope_file.sources) - model_calls
    counts = dict.fromkeys(CONFIDENCE_ORDER, 0)
    for entry in scope_file.files:
        counts[entry.confidence] += 1
    tier_b = "on" if scope_file.include_tier_b else "off"
    lines = sum(entry.ldh_lines for entry in scope_file.files)
    confidence_line = ", ".join(
        f"{confidence}={counts[confidence]}" for confidence in CONFIDENCE_ORDER
    )
    print(f"HarnessProbe scope for {path} (tier B: {tier_b})")
    print(f"sources: {model_calls} model-call sites, {annotations} annotation sites")
    print(f"candidates: {len(scope_file.files)} files, {lines} lines")
    print(f"confidence: {confidence_line}")
    for note in scope_file.confidence_notes:
        print(f"note: {note}")
    print(f"wrote {out}")
