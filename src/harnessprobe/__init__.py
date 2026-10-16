"""HarnessProbe: heuristic LDH scope extraction and coverage subsetting."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harnessprobe.coverage_subset import subset_coverage
    from harnessprobe.report import FileSubsetReport, SubsetReport, SubsetTotals, UncoveredSample
    from harnessprobe.scope import FileScope, Scope, SourceSite, derive_scope
    from harnessprobe.scopefile import (
        ScopeFile,
        ScopeFileEntry,
        ScopeSource,
        build_scope_file,
        scope_from_file,
        write_scope_file,
    )

__version__ = "0.1.0"

__all__ = [
    "FileScope",
    "FileSubsetReport",
    "Scope",
    "ScopeFile",
    "ScopeFileEntry",
    "ScopeSource",
    "SourceSite",
    "SubsetReport",
    "SubsetTotals",
    "UncoveredSample",
    "__version__",
    "build_scope_file",
    "derive_scope",
    "scope_from_file",
    "subset_coverage",
    "write_scope_file",
]

_EXPORTS = {
    "FileScope": "harnessprobe.scope",
    "FileSubsetReport": "harnessprobe.report",
    "Scope": "harnessprobe.scope",
    "ScopeFile": "harnessprobe.scopefile",
    "ScopeFileEntry": "harnessprobe.scopefile",
    "ScopeSource": "harnessprobe.scopefile",
    "SourceSite": "harnessprobe.scope",
    "SubsetReport": "harnessprobe.report",
    "SubsetTotals": "harnessprobe.report",
    "UncoveredSample": "harnessprobe.report",
    "build_scope_file": "harnessprobe.scopefile",
    "derive_scope": "harnessprobe.scope",
    "scope_from_file": "harnessprobe.scopefile",
    "subset_coverage": "harnessprobe.coverage_subset",
    "write_scope_file": "harnessprobe.scopefile",
}


def __getattr__(name: str) -> Any:
    """Import a public name on first use so package import stays light."""
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value
