"""Verify the production host preserves API routing and serves the SPA safely."""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text('<html><div id="root">PRISM</div></html>')
    (tmp_path / "assets" / "app-test.js").write_text("console.log('PRISM')")
    monkeypatch.setenv("PRISM_FRONTEND_DIR", str(tmp_path))
    host = importlib.import_module("deploy.app")
    return TestClient(host.ProductionApp(host.api, str(tmp_path)), base_url="http://localhost")


def test_ui_and_deep_link_serve_html_without_api_csp(client):
    for path in ["/", "/portfolio/review"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "PRISM" in response.text
        assert response.headers["cache-control"] == "no-cache"
        assert "default-src 'none'" not in response.headers.get("content-security-policy", "")


def test_assets_are_cached_but_missing_assets_and_api_remain_404(client):
    response = client.get("/assets/app-test.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]
    for path in ["/assets/missing.js", "/missing.js", "/api/v1/missing"]:
        assert client.get(path).status_code == 404


def test_api_health_keeps_api_security_headers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "prism-api"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )


def test_render_defaults_work_for_migrations_before_asgi_import(monkeypatch):
    from backend.app.core.config import Settings

    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "prism-test.onrender.com")
    monkeypatch.delenv("PRISM_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("PRISM_TRUSTED_HOSTS", raising=False)
    config = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://test:test@db/test?sslmode=require",
        supabase_url="https://test.supabase.co",
        supabase_publishable_key="public-test-key",
    )
    assert config.cors_origins == ["https://prism-test.onrender.com"]
    assert config.trusted_hosts == ["prism-test.onrender.com", "localhost", "127.0.0.1"]
