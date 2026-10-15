"""HarnessProbe: heuristic LDH scope extraction and coverage subsetting."""

from harnessprobe.coverage_subset import subset_coverage
from harnessprobe.report import FileSubsetReport, SubsetReport, SubsetTotals, UncoveredSample
from harnessprobe.scope import FileScope, Scope, derive_scope

__version__ = "0.1.0"

__all__ = [
    "FileScope",
    "FileSubsetReport",
    "Scope",
    "SubsetReport",
    "SubsetTotals",
    "UncoveredSample",
    "__version__",
    "derive_scope",
    "subset_coverage",
]
