"""Pydantic v2 scope file model and builder."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from harnessprobe.scope import FileScope, Scope, SourceSite, statement_lines

Confidence = Literal["authoritative", "allowlisted", "heuristic-high", "heuristic-low"]
SourceKind = Literal["model_call", "annotation"]
ScopeKind = Literal["whole-file", "pinned-lines"]

CONFIDENCE_ORDER: tuple[Confidence, ...] = (
    "authoritative",
    "allowlisted",
    "heuristic-high",
    "heuristic-low",
)

CONFIDENCE_NOTES: dict[Confidence, str] = {
    "authoritative": "annotations are user-declared; treated as authoritative",
    "allowlisted": "allowlisted files are scoped whole by user declaration",
    "heuristic-high": "tier A: model-call and same-function consumer statements (heuristic)",
    "heuristic-low": "tier B: one-hop calls into tier-A functions; expect false positives",
}

TIER_B_DISABLED_NOTE = "tier B reachability disabled (--no-tier-b)"

REASON_CONFIDENCE: tuple[tuple[str, Confidence], ...] = (
    ("annotation", "authoritative"),
    ("allowlist", "allowlisted"),
    ("heuristic:tier-a", "heuristic-high"),
    ("heuristic:tier-b", "heuristic-low"),
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeSource(_StrictModel):
    """One model-call or annotation source site."""

    kind: SourceKind
    path: str
    line: int


class ScopeFileEntry(_StrictModel):
    """Scoped line inventory, confidence, and reasons for one file.

    A whole-file entry carries no pinned lines: the file is scoped whole by
    declaration, so its lines resolve from the source at load time. A
    pinned-lines entry is a generation-time snapshot.
    """

    path: str
    scope_kind: ScopeKind
    ldh_lines: int
    lines: list[int] | None
    confidence: Confidence
    reasons: list[str]

    @model_validator(mode="after")
    def _require_lines_for_pinned_kind(self) -> ScopeFileEntry:
        if self.scope_kind == "whole-file":
            if self.lines is not None:
                raise ValueError("whole-file scope must not store pinned lines")
            return self
        if not self.lines:
            raise ValueError("pinned-lines scope requires at least one line")
        if len(self.lines) != self.ldh_lines:
            raise ValueError("pinned-lines scope requires ldh_lines to match lines")
        return self


with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "schema"', category=UserWarning)

    class ScopeFile(_StrictModel):
        """Versioned scope file: sources, heuristic candidates, confidence notes."""

        schema: Literal["harnessprobe.scope/v2"]
        generated_by: str
        allowlist: list[str]
        include_tier_b: bool
        sources: list[ScopeSource]
        files: list[ScopeFileEntry]
        confidence_notes: list[str]
        warnings: list[str]

        def to_json(self, indent: int = 2) -> str:
            """Serialize the scope file to JSON."""
            return self.model_dump_json(indent=indent)

        @classmethod
        def from_json(cls, s: str) -> ScopeFile:
            """Parse a scope file from a JSON string."""
            return cls.model_validate_json(s)


def build_scope_file(
    scope: Scope,
    *,
    allowlist: Sequence[str],
    include_tier_b: bool,
    generated_by: str,
) -> ScopeFile:
    """Build the serializable scope file from a derived scope."""
    entries = [_entry_for(file_scope) for file_scope in scope.files]
    present = {entry.confidence for entry in entries}
    notes = [
        CONFIDENCE_NOTES[confidence] for confidence in CONFIDENCE_ORDER if confidence in present
    ]
    if not include_tier_b:
        notes.append(TIER_B_DISABLED_NOTE)
    return ScopeFile(
        schema="harnessprobe.scope/v2",
        generated_by=generated_by,
        allowlist=list(allowlist),
        include_tier_b=include_tier_b,
        sources=[
            ScopeSource(kind=site.kind, path=site.path, line=site.line) for site in scope.sources
        ],
        files=entries,
        confidence_notes=notes,
        warnings=list(scope.warnings),
    )


def scope_from_file(scope_file: ScopeFile, *, repo_root: Path | None = None) -> Scope:
    """Reconstruct the derived scope from a parsed scope file.

    Pinned-lines entries keep their recorded lines. Whole-file entries resolve
    against the current sources under repo_root, so edits that move lines
    cannot drop them; an entry whose file no longer parses is skipped with a
    warning. Without repo_root a scope file that holds whole-file entries
    cannot be reconstructed, and the call raises ValueError.
    """
    warnings_out = list(scope_file.warnings)
    files: list[FileScope] = []
    for entry in scope_file.files:
        if entry.scope_kind == "whole-file":
            resolved = _resolve_whole_file(entry, repo_root=repo_root, warnings_out=warnings_out)
            if resolved is None:
                continue
            lines = resolved
        else:
            lines = tuple(entry.lines or ())
        files.append(FileScope(path=entry.path, lines=lines, reasons=tuple(entry.reasons)))
    return Scope(
        files=tuple(files),
        warnings=tuple(warnings_out),
        sources=tuple(
            SourceSite(kind=source.kind, path=source.path, line=source.line)
            for source in scope_file.sources
        ),
    )


def _entry_for(file_scope: FileScope) -> ScopeFileEntry:
    whole_file = "allowlist" in file_scope.reasons
    return ScopeFileEntry(
        path=file_scope.path,
        scope_kind="whole-file" if whole_file else "pinned-lines",
        ldh_lines=len(file_scope.lines),
        lines=None if whole_file else list(file_scope.lines),
        confidence=_confidence_for(file_scope.reasons),
        reasons=list(file_scope.reasons),
    )


def _resolve_whole_file(
    entry: ScopeFileEntry, *, repo_root: Path | None, warnings_out: list[str]
) -> tuple[int, ...] | None:
    if repo_root is None:
        raise ValueError(
            f"scope file entry {entry.path!r} is whole-file; "
            "repo_root is required to resolve it"
        )
    try:
        source = (repo_root / entry.path).read_text(encoding="utf-8", errors="replace")
        lines = statement_lines(source)
    except (OSError, SyntaxError) as exc:
        warnings_out.append(f"skipped {entry.path}: whole-file scope not resolvable ({exc})")
        return None
    if not lines:
        warnings_out.append(f"skipped {entry.path}: whole-file scope has no statements")
        return None
    return tuple(sorted(lines))


def write_scope_file(scope_file: ScopeFile, path: Path) -> Path:
    """Write the scope file as indented JSON and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scope_file.to_json() + "\n", encoding="utf-8")
    return path


def _confidence_for(reasons: Sequence[str]) -> Confidence:
    for reason, confidence in REASON_CONFIDENCE:
        if reason in reasons:
            return confidence
    raise ValueError(f"file has no confidence reason: {list(reasons)!r}")
