from backend.app.db import models  # noqa: F401
from backend.app.db.base import Base


def test_database_tables_are_registered() -> None:
    expected = {
        "corporate_action",
        "mst_edge",
        "mst_node",
        "mst_run",
        "pipeline_run",
        "price_daily_adjusted",
        "price_daily_raw",
        "security",
        "security_alias",
        "sector_divergence_issue",
        "sector_divergence_run",
        "sector_divergence_score",
        "signal_l1",
        "trading_calendar",
        "universe",
        "universe_membership",
    }

    assert set(Base.metadata.tables) == expected
