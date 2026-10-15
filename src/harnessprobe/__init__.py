"""HarnessProbe: heuristic LDH scope extraction and coverage subsetting."""

from harnessprobe.coverage_subset import subset_coverage
from harnessprobe.report import FileSubsetReport, SubsetReport, SubsetTotals, UncoveredSample
from harnessprobe.scope import FileScope, Scope, SourceSite, derive_scope
from harnessprobe.scopefile import (
    ScopeFile,
    ScopeFileEntry,
    ScopeSource,
    build_scope_file,
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
    "subset_coverage",
    "write_scope_file",
]
