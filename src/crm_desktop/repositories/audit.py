from __future__ import annotations

import sqlite3

from crm_desktop.repositories._util import ts_now


def log(conn: sqlite3.Connection, action: str, entity: str | None = None, details: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log(ts, action, entity, details) VALUES (?,?,?,?)",
        (ts_now(), action, entity, details),
    )
    conn.commit()
