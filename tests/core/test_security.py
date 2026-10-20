from fastapi.testclient import TestClient

from backend.app.core.security import SlidingWindowRateLimiter
from backend.app.main import app


def test_sliding_window_rate_limiter_is_deterministic() -> None:
    limiter = SlidingWindowRateLimiter(requests=2, window_seconds=10)

    assert limiter.allow("client", now=100.0) == (True, 0)
    assert limiter.allow("client", now=101.0) == (True, 0)
    allowed, retry_after = limiter.allow("client", now=102.0)
    assert allowed is False
    assert retry_after == 8
    assert limiter.allow("client", now=111.0) == (True, 0)


def test_oversized_request_is_rejected_before_route_processing() -> None:
    response = TestClient(app).post(
        "/api/v1/ml/volatility-forecast",
        content=b"{}",
        headers={"Content-Length": "1048577", "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds the configured size limit"}
