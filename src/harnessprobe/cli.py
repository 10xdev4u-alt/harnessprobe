"""Command-line interface for HarnessProbe."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from harnessprobe import __version__
from harnessprobe.ci import (
    DEFAULT_COMMENT_AUTHOR,
    GateThresholds,
    evaluate_gate,
    post_sticky_comment,
    write_outputs,
)
from harnessprobe.comment import load_findings, render_pr_comment
from harnessprobe.report import SubsetReport
from harnessprobe.scope import derive_scope
from harnessprobe.scopefile import CONFIDENCE_ORDER, ScopeFile, build_scope_file, write_scope_file


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    args = _build_parser().parse_args(argv)
    if args.command == "comment":
        return _run_comment(args)
    if args.command == "gate":
        return _run_gate(args)
    if args.command == "post":
        return _run_post(args)
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
    gate_parser = subparsers.add_parser(
        "gate", help="Evaluate CI gate thresholds against a report and findings."
    )
    gate_parser.add_argument(
        "--report", type=Path, required=True, metavar="PATH", help="Coverage subset report JSON."
    )
    gate_parser.add_argument(
        "--findings",
        type=Path,
        default=None,
        metavar="PATH",
        help="Findings JSON attached to this run.",
    )
    gate_parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Minimum LDH coverage percent required (0 to 100).",
    )
    gate_parser.add_argument(
        "--max-uncovered",
        type=int,
        default=None,
        metavar="INT",
        help="Maximum uncovered LDH scope lines allowed.",
    )
    gate_parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Fail the gate when any findings are attached.",
    )
    gate_parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write the Markdown gate summary here.",
    )
    gate_parser.add_argument(
        "--outputs",
        type=Path,
        default=None,
        metavar="PATH",
        help="Append GitHub outputs in GITHUB_OUTPUT format here.",
    )
    post_parser = subparsers.add_parser(
        "post", help="Render and post the sticky PR comment through gh."
    )
    post_parser.add_argument(
        "--report", type=Path, required=True, metavar="PATH", help="Coverage subset report JSON."
    )
    post_parser.add_argument(
        "--findings",
        type=Path,
        default=None,
        metavar="PATH",
        help="Findings JSON attached to this run.",
    )
    post_parser.add_argument(
        "--previous",
        type=Path,
        default=None,
        metavar="PATH",
        help="Previous coverage subset report JSON for the trend.",
    )
    post_parser.add_argument(
        "--pr", type=int, required=True, metavar="INT", help="Pull request number."
    )
    post_parser.add_argument(
        "--repo",
        default=None,
        metavar="OWNER/REPO",
        help="Repository slug (default: GITHUB_REPOSITORY environment variable).",
    )
    post_parser.add_argument(
        "--comment-out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Also write the rendered comment body here.",
    )
    post_parser.add_argument("--dry-run", action="store_true", help="Render without calling gh.")
    post_parser.add_argument(
        "--comment-author",
        default=DEFAULT_COMMENT_AUTHOR,
        metavar="LOGIN",
        help="Author whose existing comment is updated (default: github-actions[bot]).",
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


def _run_gate(args: argparse.Namespace) -> int:
    try:
        report = _load_report(args.report, "report")
        findings_count = len(load_findings(args.findings)) if args.findings is not None else 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.min_coverage is not None and not 0 <= args.min_coverage <= 100:
        print("error: --min-coverage must be between 0 and 100", file=sys.stderr)
        return 2
    if args.max_uncovered is not None and args.max_uncovered < 0:
        print("error: --max-uncovered must be >= 0", file=sys.stderr)
        return 2
    result = evaluate_gate(
        report,
        findings_count=findings_count,
        thresholds=GateThresholds(
            min_coverage=args.min_coverage,
            max_uncovered=args.max_uncovered,
            fail_on_findings=args.fail_on_findings,
        ),
    )
    if args.summary_out is not None:
        try:
            args.summary_out.parent.mkdir(parents=True, exist_ok=True)
            args.summary_out.write_text(result.summary, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.summary_out}: {exc}", file=sys.stderr)
            return 2
    if args.outputs is not None:
        try:
            write_outputs(args.outputs, result.outputs)
        except OSError as exc:
            print(f"error: cannot write {args.outputs}: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if result.passed:
        print("harnessprobe gate: passed")
        return 0
    print("harnessprobe gate: failed")
    for reason in result.reasons:
        print(f"- {reason}")
    return 1


def _run_post(args: argparse.Namespace) -> int:
    repo = args.repo if args.repo is not None else os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("error: no repository given (use --repo or GITHUB_REPOSITORY)", file=sys.stderr)
        return 1
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
    if args.comment_out is not None:
        try:
            args.comment_out.parent.mkdir(parents=True, exist_ok=True)
            args.comment_out.write_text(comment, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.comment_out}: {exc}", file=sys.stderr)
            return 1
    if args.dry_run:
        print(f"harnessprobe post: dry-run (would post to {repo}#{args.pr})")
        return 0
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            body_path = Path(tmp_dir) / "comment.md"
            body_path.write_text(comment, encoding="utf-8")
            outcome = post_sticky_comment(
                repo=repo,
                pr_number=args.pr,
                body_path=body_path,
                dry_run=False,
                author=args.comment_author,
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if outcome.url:
        print(f"harnessprobe post: {outcome.action} comment {outcome.url}")
    else:
        print(f"harnessprobe post: {outcome.action} comment")
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
