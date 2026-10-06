import hashlib
import json

from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import get_settings


engine = create_engine(get_settings().database_url)
with engine.connect() as connection:
    tables = sorted(inspect(connection).get_table_names())
    counts = {
        table: connection.execute(text(f'SELECT count(1) FROM "{table}"')).scalar_one()
        for table in tables
        if table != "alembic_version"
    }
    domain = {key: value for key, value in counts.items() if key != "model_config"}
    sources = connection.execute(
        text(
            "SELECT source_key, status, last_success_at FROM data_source "
            "WHERE dataset='news_policy' ORDER BY source_key"
        )
    ).all()
    newest = connection.execute(
        text(
            "SELECT source, max(published_at), count(1) FROM news_item "
            "GROUP BY source ORDER BY source"
        )
    ).all()
    rules = connection.execute(
        text(
            "SELECT count(1), count(1) FILTER (WHERE active), "
            "count(1) FILTER (WHERE upper(reviewer)='UNREVIEWED') FROM policy_rule"
        )
    ).one()
print(
    {
        "model_config": counts.get("model_config"),
        "domain_hash": hashlib.sha256(
            json.dumps(domain, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "table_count": len(domain),
        "news_items": counts.get("news_item"),
        "news_security_links": counts.get("news_security_link"),
        "policy_events": counts.get("policy_event"),
        "sources": [(row[0], row[1], str(row[2])) for row in sources],
        "newest": [(row[0], str(row[1]), row[2]) for row in newest],
        "rules": tuple(rules),
    }
)
