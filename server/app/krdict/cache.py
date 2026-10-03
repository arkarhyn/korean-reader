"""SQLite cache of raw krdict responses, keyed by query string."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class KrdictCache:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS krdict_cache ("
            " query TEXT PRIMARY KEY, xml TEXT NOT NULL, fetched_at TEXT NOT NULL)"
        )

    def get(self, query: str) -> str | None:
        row = self._conn.execute("SELECT xml FROM krdict_cache WHERE query = ?", (query,)).fetchone()
        return row[0] if row else None

    def put(self, query: str, xml: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO krdict_cache (query, xml, fetched_at) VALUES (?, ?, ?)",
            (query, xml, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
