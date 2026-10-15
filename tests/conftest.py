import json
from pathlib import Path

import pytest

from harnessprobe import SubsetReport, derive_scope, subset_coverage

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return FIXTURES_ROOT


@pytest.fixture(scope="session")
def mini_coverage_json() -> dict[str, object]:
    return json.loads((FIXTURES_ROOT / "mini_coverage.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def mini_report(fixtures_root: Path, mini_coverage_json: dict[str, object]) -> SubsetReport:
    return subset_coverage(mini_coverage_json, derive_scope(fixtures_root), repo_root=fixtures_root)
