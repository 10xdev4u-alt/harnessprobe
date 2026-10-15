from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return FIXTURES_ROOT
