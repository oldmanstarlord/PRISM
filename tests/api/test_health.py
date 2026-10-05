from fastapi.testclient import TestClient

from backend.app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "prism-api"}


def test_portfolios_require_authentication() -> None:
    response = TestClient(app).get("/api/v1/portfolios")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
