import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.core.config import Settings


def test_database_url_normalizes_driver_ssl_and_reserved_password_characters() -> None:
    settings = Settings(
        database_url=("postgresql://postgres.project:secret@6969@pooler.supabase.com:5432/postgres")
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "secret%406969" in settings.database_url
    assert "@pooler.supabase.com:5432" in settings.database_url
    assert "sslmode=require" in settings.database_url


def test_database_url_does_not_double_encode_password() -> None:
    settings = Settings(
        database_url=(
            "postgresql+psycopg://postgres.project:secret%406969@"
            "pooler.supabase.com:5432/postgres?sslmode=require"
        )
    )

    assert "secret%406969" in settings.database_url
    assert "%2540" not in settings.database_url


def test_project_env_is_loaded_when_started_from_backend(tmp_path: Path) -> None:
    # Reproduce the actual package depth with a disposable .env, without using local secrets.
    config_path = tmp_path / "backend" / "app" / "core" / "config.py"
    config_path.parent.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2] / "backend" / "app" / "core" / "config.py"
    shutil.copyfile(source, config_path)
    (tmp_path / ".env").write_text(
        "PRISM_DATABASE_URL=postgresql://test:test@localhost:5432/prism?sslmode=disable\n",
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PRISM_") and key != "PYTHONPATH"
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; "
            "settings = runpy.run_path(sys.argv[1])['settings']; "
            "assert settings.database_url == "
            "'postgresql+psycopg://test:test@localhost:5432/prism?sslmode=disable'",
            str(config_path),
        ],
        cwd=tmp_path / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
def test_production_rejects_wildcard_and_local_cors() -> None:
    with pytest.raises(ValueError, match="explicit origins"):
        Settings(database_url="postgresql://u:p@db.example.com/prism", cors_origins=["*"])

    with pytest.raises(ValueError, match="Supabase authentication"):
        Settings(
            database_url="postgresql://u:p@db.example.com/prism",
            environment="production",
            local_auth_enabled=False,
            cors_origins=["https://prism.example.com"],
            trusted_hosts=["prism.example.com"],
        )


def test_production_rejects_local_auth_bypass() -> None:
    with pytest.raises(ValueError, match="Local authentication bypass"):
        Settings(
            database_url="postgresql://u:p@db.example.com/prism",
            environment="production",
            local_auth_enabled=True,
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="public-key",
            cors_origins=["https://prism.example.com"],
            trusted_hosts=["prism.example.com"],
        )
