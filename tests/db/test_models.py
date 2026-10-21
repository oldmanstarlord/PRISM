from backend.app.db import models  # noqa: F401
from backend.app.db.base import Base


def test_database_tables_are_registered() -> None:
    expected = {
        "audit_event",
        "corporate_action",
        "data_coverage_run",
        "data_quality_result",
        "fundamentals_snapshot",
        "journal_decision",
        "journal_note",
        "market_data_fetch_result",
        "model_prediction",
        "model_run",
        "mst_edge",
        "mst_node",
        "mst_run",
        "news_article",
        "news_entity_match",
        "news_signal",
        "pipeline_run",
        "portfolio",
        "portfolio_risk_history",
        "portfolio_snapshot_holding",
        "portfolio_snapshot",
        "portfolio_transaction",
        "price_daily_adjusted",
        "price_daily_raw",
        "security",
        "security_alias",
        "score_calibration",
        "sector_divergence_issue",
        "sector_divergence_run",
        "sector_divergence_score",
        "signal_l1",
        "stock_metric_daily",
        "trading_calendar",
        "universe",
        "universe_membership",
    }

    assert set(Base.metadata.tables) == expected
