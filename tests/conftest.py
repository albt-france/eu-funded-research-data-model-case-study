import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = ROOT / "tests" / "fixtures" / "raw"


@pytest.fixture(scope="session")
def loaded(tmp_path_factory):
    """Run the whole pipeline (stage -> load -> mart -> quality checks) on the SIMULATED fixture files."""
    import load
    tmp = tmp_path_factory.mktemp("pipeline")
    db = tmp / "test.duckdb"
    counts, qa = load.main(["--raw-dir", str(FIXTURES), "--interim", str(tmp / "interim"), "--db", str(db)])
    return {"db": db, "counts": counts, "qa": qa, "interim": tmp / "interim"}
