from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def examples() -> Path:
    """Hand-written fixtures with known answers (see evidence/intent.md)."""
    return ROOT / "examples"


@pytest.fixture
def config_dir() -> Path:
    """The real config files in config/."""
    return ROOT / "config"
