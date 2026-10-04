from sqlalchemy import select

from backend.app.db.models import Universe
from backend.app.db.session import SessionLocal


def seed_nifty_200_universe() -> bool:
    """Create the universe identity if absent; constituent membership is loaded separately."""
    with SessionLocal.begin() as session:
        existing = session.scalar(select(Universe).where(Universe.name == "NIFTY 200"))
        if existing is not None:
            return False
        session.add(
            Universe(
                name="NIFTY 200",
                description="Versioned NIFTY 200 constituent universe for PRISM",
            )
        )
    return True


if __name__ == "__main__":
    created = seed_nifty_200_universe()
    print("NIFTY 200 universe created." if created else "NIFTY 200 universe already exists.")
