from sqlalchemy import text

from backend.app.db.session import SessionLocal

s = SessionLocal()
rows = s.execute(
    text(
        "SELECT pid, state, wait_event_type, wait_event, query FROM pg_stat_activity WHERE datname "
        "= current_database()"
    )
).fetchall()
for r in rows:
    print(r)
