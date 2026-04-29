"""
db/connection.py
----------------
Provides a thread-safe SQLite connection factory.

Usage (inside a Flask route or standalone script):
    from db.connection import get_db, close_db

    db = get_db()
    db.execute("SELECT * FROM workouts WHERE user_id = ?", (user_id,))
"""

import sqlite3
import os
from pathlib import Path

# Resolve the DB file path relative to this file so the module works
# regardless of the working directory Flask is launched from.
_BASE_DIR = Path(__file__).parent
DB_PATH = os.environ.get("DB_PATH", str(_BASE_DIR / "workout_app.db"))
SCHEMA_PATH = _BASE_DIR / "schema.sql"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Open (or create) the SQLite database and return a connection.

    - row_factory is set to sqlite3.Row so columns are accessible
      by name (row['date']) as well as index (row[0]).
    - Foreign-key enforcement is enabled per connection (SQLite
      requires this pragma on every new connection).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")   # better concurrent read perf
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """
    Create all tables and seed data defined in schema.sql.
    Safe to call multiple times (all statements use IF NOT EXISTS /
    INSERT OR IGNORE).
    """
    schema = SCHEMA_PATH.read_text()
    with get_connection(db_path) as conn:
        conn.executescript(schema)
        # Migrations: add columns introduced after initial schema.
        for col, ddl in [
            ("body_weight_lbs", "ALTER TABLE users ADD COLUMN body_weight_lbs REAL"),
            ("height_in",       "ALTER TABLE users ADD COLUMN height_in REAL"),
        ]:
            existing = conn.execute("PRAGMA table_info(users)").fetchall()
            if not any(row["name"] == col for row in existing):
                conn.execute(ddl)
        conn.commit()
    print(f"[db] Initialized database at: {db_path}")


# ---------------------------------------------------------------------------
# Flask application-context helpers
# ---------------------------------------------------------------------------

def get_db():
    """
    Return the per-request database connection stored on Flask's `g` object.
    Creates a new connection if one does not exist for the current context.
    Reads DB_PATH from Flask app config when inside an app context.
    """
    try:
        from flask import g, current_app
        if "db" not in g:
            path = current_app.config.get("DB_PATH", DB_PATH)
            g.db = get_connection(path)
        return g.db
    except RuntimeError:
        # Outside Flask application context — return a plain connection.
        return get_connection()


def close_db(exception=None):
    """Teardown helper: closes the per-request connection if it exists."""
    try:
        from flask import g
        db = g.pop("db", None)
        if db is not None:
            db.close()
    except RuntimeError:
        pass
