"""CI gate evaluation, GitHub outputs, and sticky PR comment posting."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from harnessprobe.report import SubsetReport, SubsetTotals

STICKY_MARKER = "_harnessprobe · report "
DEFAULT_COMMENT_AUTHOR = "github-actions[bot]"


@dataclass(frozen=True)
class GateThresholds:
    """Configured gate thresholds; None disables a check."""

    min_coverage: float | None = None
    max_uncovered: int | None = None
    fail_on_findings: bool = False


@dataclass(frozen=True)
class GateResult:
    """Gate verdict with GitHub outputs and a Markdown summary."""

    passed: bool
    reasons: tuple[str, ...]
    outputs: dict[str, str]
    summary: str


def evaluate_gate(
    report: SubsetReport,
    *,
    findings_count: int,
    thresholds: GateThresholds,
) -> GateResult:
    """Evaluate the CI gate and build outputs and a Markdown summary."""
    totals = report.totals
    uncovered = totals.scope_lines - totals.executed
    reasons = _gate_reasons(
        totals,
        uncovered=uncovered,
        findings_count=findings_count,
        thresholds=thresholds,
    )
    passed = not reasons
    covered = "" if totals.covered_pct is None else f"{totals.covered_pct:.2f}"
    outputs = {
        "covered-pct": covered,
        "scope-lines": str(totals.scope_lines),
        "executed": str(totals.executed),
        "uncovered": str(uncovered),
        "not-measured": str(totals.not_measured),
        "findings-count": str(findings_count),
        "gate-passed": "true" if passed else "false",
        "gate-reasons": "; ".join(reasons),
    }
    summary = _gate_summary(
        totals,
        uncovered=uncovered,
        findings_count=findings_count,
        thresholds=thresholds,
        reasons=reasons,
    )
    return GateResult(passed=passed, reasons=tuple(reasons), outputs=outputs, summary=summary)


def _gate_reasons(
    totals: SubsetTotals,
    *,
    uncovered: int,
    findings_count: int,
    thresholds: GateThresholds,
) -> list[str]:
    """Collect failure reasons in the fixed check order."""
    reasons: list[str] = []
    if thresholds.min_coverage is not None:
        if totals.covered_pct is None:
            reasons.append("no measured LDH scope lines; min-coverage cannot be checked")
        elif totals.covered_pct < thresholds.min_coverage:
            reasons.append(
                f"LDH coverage {totals.covered_pct:.2f}% is below min-coverage "
                f"{thresholds.min_coverage:.2f}%"
            )
    if thresholds.max_uncovered is not None and uncovered > thresholds.max_uncovered:
        reasons.append(
            f"{uncovered} uncovered LDH lines exceed max-uncovered {thresholds.max_uncovered}"
        )
    if thresholds.fail_on_findings and findings_count > 0:
        reasons.append(f"{findings_count} bug findings attached (fail-on-findings)")
    return reasons


def _gate_summary(
    totals: SubsetTotals,
    *,
    uncovered: int,
    findings_count: int,
    thresholds: GateThresholds,
    reasons: Sequence[str],
) -> str:
    """Render the Markdown gate summary."""
    pct = "n/a" if totals.covered_pct is None else f"{totals.covered_pct:.2f}%"
    status = "failed" if reasons else "passed"
    lines = [
        f"## HarnessProbe gate: {status}",
        "",
        f"- LDH coverage: {pct} ({totals.executed}/{totals.scope_lines} measured lines)",
        f"- Uncovered LDH lines: {uncovered}",
        f"- Findings attached: {findings_count}",
        f"- Thresholds: {_thresholds_text(thresholds)}",
    ]
    if reasons:
        lines.extend(["", "### Failures", ""])
        lines.extend(f"- {reason}" for reason in reasons)
    return "\n".join(lines) + "\n"


def _thresholds_text(thresholds: GateThresholds) -> str:
    """Render only the configured thresholds."""
    parts: list[str] = []
    if thresholds.min_coverage is not None:
        parts.append(f"min-coverage {thresholds.min_coverage:.2f}%")
    if thresholds.max_uncovered is not None:
        parts.append(f"max-uncovered {thresholds.max_uncovered}")
    if thresholds.fail_on_findings:
        parts.append("fail-on-findings on")
    return ", ".join(parts) if parts else "none configured"


def write_outputs(path: Path, outputs: Mapping[str, str]) -> None:
    """Append key=value lines for GITHUB_OUTPUT after validating every entry."""
    for key, value in outputs.items():
        if not key:
            raise ValueError("output key must not be empty")
        if "=" in key:
            raise ValueError(f"output key must not contain '=': {key!r}")
        if "\n" in key:
            raise ValueError(f"output key must not contain a newline: {key!r}")
        if "\n" in value:
            raise ValueError(f"output value for {key!r} must not contain a newline")
    text = "".join(f"{key}={value}\n" for key, value in outputs.items())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


@dataclass(frozen=True)
class CommandResult:
    """Captured result of one gh invocation."""

    returncode: int
    stdout: str
    stderr: str


GhRunner = Callable[[Sequence[str]], CommandResult]


def is_sticky_body(body: str) -> bool:
    """Report whether a comment body carries the HarnessProbe sticky marker."""
    return STICKY_MARKER in body


@dataclass(frozen=True)
class PostOutcome:
    """Outcome of a sticky comment post attempt."""

    action: Literal["created", "updated", "dry-run"]
    comment_id: int | None
    url: str | None


def post_sticky_comment(
    *,
    repo: str,
    pr_number: int,
    body_path: Path,
    runner: GhRunner | None = None,
    dry_run: bool = False,
    author: str = DEFAULT_COMMENT_AUTHOR,
) -> PostOutcome:
    """Create or update the sticky PR comment through the gh CLI."""
    if dry_run:
        return PostOutcome("dry-run", None, None)
    run = _run_gh if runner is None else runner
    comment_id = _find_sticky_comment(run, repo=repo, pr_number=pr_number, author=author)
    if comment_id is None:
        argv = [
            "gh",
            "api",
            f"repos/{repo}/issues/{pr_number}/comments",
            "-F",
            f"body=@{body_path}",
        ]
        action: Literal["created", "updated"] = "created"
    else:
        argv = [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"repos/{repo}/issues/comments/{comment_id}",
            "-F",
            f"body=@{body_path}",
        ]
        action = "updated"
    response = run(argv)
    _check_gh(response, argv)
    returned_id, url = _parse_comment_response(response.stdout)
    return PostOutcome(action, returned_id, url)


def _find_sticky_comment(
    run: GhRunner, *, repo: str, pr_number: int, author: str
) -> int | None:
    """Return the id of the latest sticky comment authored by author, if any."""
    argv = [
        "gh",
        "api",
        "--paginate",
        f"repos/{repo}/issues/{pr_number}/comments?per_page=100",
    ]
    result = run(argv)
    _check_gh(result, argv)
    latest: int | None = None
    for page in _parse_comment_pages(result.stdout):
        for item in page:
            if not isinstance(item, Mapping):
                raise ValueError("cannot parse gh comment list output")
            comment_id = item.get("id")
            body = item.get("body")
            if not isinstance(comment_id, int) or isinstance(comment_id, bool):
                continue
            if _comment_author(item) != author:
                continue
            if isinstance(body, str) and is_sticky_body(body):
                latest = comment_id
    return latest


def _comment_author(item: Mapping[object, object]) -> str | None:
    """Return the author login when the comment payload carries one."""
    user = item.get("user")
    if not isinstance(user, Mapping):
        return None
    login = user.get("login")
    return login if isinstance(login, str) else None


def _parse_comment_pages(stdout: str) -> list[list[object]]:
    """Parse concatenated JSON arrays emitted by paginated gh api."""
    decoder = json.JSONDecoder()
    pages: list[list[object]] = []
    index = 0
    length = len(stdout)
    while index < length:
        while index < length and stdout[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            document, index = decoder.raw_decode(stdout, index)
        except ValueError as exc:
            raise ValueError("cannot parse gh comment list output") from exc
        if not isinstance(document, list):
            raise ValueError("cannot parse gh comment list output")
        pages.append(document)
    return pages


def _parse_comment_response(stdout: str) -> tuple[int | None, str | None]:
    """Parse the comment id and html_url from a gh response."""
    try:
        payload = json.loads(stdout)
    except ValueError as exc:
        raise ValueError("cannot parse gh comment response") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("cannot parse gh comment response")
    raw_id = payload.get("id")
    raw_url = payload.get("html_url")
    comment_id = raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) else None
    url = raw_url if isinstance(raw_url, str) else None
    return comment_id, url


def _check_gh(result: CommandResult, argv: Sequence[str]) -> None:
    """Raise when a gh invocation failed."""
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or " ".join(argv)
    raise ValueError(f"gh failed: {detail}")


def _run_gh(argv: Sequence[str]) -> CommandResult:
    """Run gh with captured output and no shell."""
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ValueError(f"gh failed: {exc}") from exc
    return CommandResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
