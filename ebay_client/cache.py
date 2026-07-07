"""SQLite-backed cache for Taxonomy API responses (7-day TTL by default)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

DEFAULT_TTL = timedelta(days=7)


def get_cached(conn: sqlite3.Connection, cache_key: str, ttl: timedelta = DEFAULT_TTL) -> Optional[Any]:
    row = conn.execute(
        "SELECT response_json, fetched_at FROM taxonomy_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    if datetime.now(timezone.utc) - fetched_at > ttl:
        return None
    return json.loads(row["response_json"])


def set_cached(conn: sqlite3.Connection, cache_key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO taxonomy_cache (cache_key, response_json, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            response_json = excluded.response_json,
            fetched_at = excluded.fetched_at
        """,
        (cache_key, json.dumps(value), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
