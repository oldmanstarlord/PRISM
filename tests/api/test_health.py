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


def test_ml_and_portfolio_news_require_authentication() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/ml/status").status_code == 401
    response = client.post("/api/v1/news/portfolio", json={"holdings": [{"symbol": "TCS"}]})
    assert response.status_code == 401


def test_security_headers_are_present() -> None:
    response = TestClient(app).get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
