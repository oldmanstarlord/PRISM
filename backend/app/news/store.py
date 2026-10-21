"""Durable, local news cache and transactional collection budget.

Public news is separate from the portfolio database; no portfolio data is stored here.
All API workers must share this file. Multi-host deployment needs a shared store.
"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


class RefreshBlocked(RuntimeError):
    pass


class NewsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    url TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
                    checked_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, credits INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def state(self) -> dict[str, Any]:
        with closing(self.connect()) as db:
            return {
                row["key"]: json.loads(row["value"])
                for row in db.execute("SELECT key, value FROM state")
            }

    def begin(self, interval_minutes: int) -> str:
        now = datetime.now(UTC)
        token = str(uuid4())
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            state = {
                row["key"]: json.loads(row["value"])
                for row in db.execute("SELECT key, value FROM state")
            }
            started = state.get("started_at")
            if started:
                age = now - datetime.fromisoformat(started)
                if state.get("running") and age < timedelta(minutes=30):
                    raise RefreshBlocked("A news refresh is already running")
                if age < timedelta(minutes=interval_minutes):
                    raise RefreshBlocked(f"Refresh is available every {interval_minutes} minutes")
            for key, value in {
                "started_at": now.isoformat(),
                "running": True,
                "run_token": token,
                "error": None,
            }.items():
                db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, json.dumps(value)))
        return token

    def finish(self, token: str, error: str | None, warnings: list[str], added: int) -> None:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM state WHERE key='run_token'").fetchone()
            if not row or json.loads(row[0]) != token:
                return
            values: dict[str, Any] = {
                "running": False,
                "error": error,
                "warnings": warnings,
                "last_added": added,
                "finished_at": datetime.now(UTC).isoformat(),
            }
            if error is None:
                values["last_success_at"] = datetime.now(UTC).isoformat()
            for key, value in values.items():
                db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, json.dumps(value)))

    def reserve(self, credits: int, budget: int) -> None:
        # Reserve before HTTP, including unsuccessful requests: conservative local accounting.
        day = datetime.now(UTC).date().isoformat()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT credits FROM usage WHERE day=?", (day,)).fetchone()
            used = row[0] if row else 0
            if used + credits > budget:
                raise RefreshBlocked(
                    "Daily Firecrawl collection budget reached (resets at UTC midnight)"
                )
            db.execute("INSERT OR REPLACE INTO usage VALUES (?, ?)", (day, used + credits))

    def used_today(self) -> int:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT credits FROM usage WHERE day=?", (datetime.now(UTC).date().isoformat(),)
            ).fetchone()
            return int(row[0]) if row else 0

    def articles(self, days: int = 7) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with closing(self.connect()) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM articles WHERE checked_at >= ? ORDER BY checked_at DESC",
                    (cutoff,),
                )
            ]

    def recent(self, url: str, model: str) -> bool:
        cutoff = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT payload FROM articles WHERE url=? AND checked_at>=?", (url, cutoff)
            ).fetchone()
            return bool(row and json.loads(row[0]).get("sentiment", {}).get("model") == model)

    def save(self, article: dict[str, Any]) -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO articles VALUES (?, ?, ?, ?)",
                (
                    article["url"],
                    article["content_hash"],
                    article["retrieved_at"],
                    json.dumps(article),
                ),
            )
            # Keep bounded history; budget/state survive content expiry.
            cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
            db.execute("DELETE FROM articles WHERE checked_at < ?", (cutoff,))
