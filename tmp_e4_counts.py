from sqlalchemy import inspect, text

from backend.app.db.session import SessionLocal

with SessionLocal() as session:
    names = sorted(inspect(session.bind).get_table_names())
    for name in names:
        count = session.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
        print(f"{name}={count}")
