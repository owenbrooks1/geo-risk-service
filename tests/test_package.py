from pathlib import Path

import geo_risk_service

REPO_SRC = Path(__file__).resolve().parents[1] / "src"


def test_package_imports():
    """Harness check. Proves that `make verify` runs real tests against the
    installed package. It does not cover any AC or INV rule."""
    package_file = Path(geo_risk_service.__file__).resolve()
    assert package_file.is_relative_to(REPO_SRC)
