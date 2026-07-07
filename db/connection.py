"""SQLite connection helper and schema initialization."""
import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", "./data/resale_assistant.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with the schema applied, creating parent dirs as needed."""
    path = db_path or get_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn
