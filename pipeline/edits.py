"""Edit + origin tracking (PLAN_v2.md M2 gate data — do not skip).

Every final field value records its origin, and every manual edit the
seller makes is written here: field, model value, her value, origin,
timestamp.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone


def record_edit(
    conn: sqlite3.Connection,
    item_id: str,
    field_name: str,
    model_value: str | None,
    edited_value: str | None,
    origin: str,
) -> str:
    edit_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO edits (edit_id, item_id, field_name, model_value, edited_value, origin, edited_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (edit_id, item_id, field_name, model_value, edited_value, origin, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return edit_id


def get_edits_for_item(conn: sqlite3.Connection, item_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM edits WHERE item_id = ? ORDER BY edited_at", (item_id,)
    ).fetchall()
