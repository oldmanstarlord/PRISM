"""Exercise startup in fresh processes so pytest's pythonpath cannot mask import errors."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("directory", "app_path"),
    [(PROJECT_ROOT, "backend.app.main:app"), (PROJECT_ROOT / "backend", "app.main:app")],
)
def test_uvicorn_loads_from_root_and_backend(directory: Path, app_path: str) -> None:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["PRISM_DATABASE_URL"] = (
        "postgresql+psycopg://prism:prism@localhost:5432/prism?sslmode=disable"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, uvicorn; "
            "from fastapi.testclient import TestClient; "
            "config = uvicorn.Config(sys.argv[1]); config.load(); "
            "response = TestClient(config.loaded_app).get('/health'); "
            "assert response.status_code == 200; "
            "assert response.json() == {'status': 'ok', 'service': 'prism-api'}",
            app_path,
        ],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
