from backend.app.gnn.schemas import GnnPortfolioRequest
from backend.app.main import app


def test_gnn_routes_are_registered_and_request_symbols_are_normalized() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/gnn/status" in paths
    assert "/api/v1/gnn/portfolio-drift" in paths
    assert "/api/v1/gnn/companies/{symbol}" in paths
    assert "/api/v1/gnn/market-history" in paths
    assert GnnPortfolioRequest(symbols=[" ril ", "RIL", "tcs"]).symbols == ["RIL", "TCS"]
