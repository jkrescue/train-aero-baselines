from pathlib import Path

import pytest

SAMPLE_CASE = Path(__file__).resolve().parents[1] / "data/sample/nose_k080_ap00_yaw06/domain.pdmsh"


@pytest.fixture(scope="session")
def sample_case() -> Path:
    if not SAMPLE_CASE.exists():
        pytest.skip("sample case not present")
    return SAMPLE_CASE
