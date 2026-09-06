import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"
