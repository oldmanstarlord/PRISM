"""Evaluate freshness and all configured explainable alert rules."""

from backend.app.db.session import SessionLocal
from backend.app.operations.service import evaluate_configured_alerts, evaluate_freshness


def main() -> None:
    with SessionLocal() as session:
        freshness = evaluate_freshness(session)
        alerts = evaluate_configured_alerts(session)
    created = sum(1 for _, is_new in alerts if is_new)
    print(f"Freshness sources={len(freshness)}; alerts created={created}; evaluated={len(alerts)}")


if __name__ == "__main__":
    main()
