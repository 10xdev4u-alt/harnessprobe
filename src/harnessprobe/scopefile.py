"""Pydantic v2 scope file model and builder."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from harnessprobe.scope import FileScope, Scope, SourceSite

Confidence = Literal["authoritative", "allowlisted", "heuristic-high", "heuristic-low"]
SourceKind = Literal["model_call", "annotation"]

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
    """Scoped line inventory, confidence, and reasons for one file."""

    path: str
    ldh_lines: int
    lines: list[int]
    confidence: Confidence
    reasons: list[str]


with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "schema"', category=UserWarning)

    class ScopeFile(_StrictModel):
        """Versioned scope file: sources, heuristic candidates, confidence notes."""

        schema: Literal["harnessprobe.scope/v1"]
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
    entries = [
        ScopeFileEntry(
            path=file_scope.path,
            ldh_lines=len(file_scope.lines),
            lines=list(file_scope.lines),
            confidence=_confidence_for(file_scope.reasons),
            reasons=list(file_scope.reasons),
        )
        for file_scope in scope.files
    ]
    present = {entry.confidence for entry in entries}
    notes = [
        CONFIDENCE_NOTES[confidence] for confidence in CONFIDENCE_ORDER if confidence in present
    ]
    if not include_tier_b:
        notes.append(TIER_B_DISABLED_NOTE)
    return ScopeFile(
        schema="harnessprobe.scope/v1",
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


def scope_from_file(scope_file: ScopeFile) -> Scope:
    """Reconstruct the derived scope from a parsed scope file."""
    return Scope(
        files=tuple(
            FileScope(path=entry.path, lines=tuple(entry.lines), reasons=tuple(entry.reasons))
            for entry in scope_file.files
        ),
        warnings=tuple(scope_file.warnings),
        sources=tuple(
            SourceSite(kind=source.kind, path=source.path, line=source.line)
            for source in scope_file.sources
        ),
    )


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
