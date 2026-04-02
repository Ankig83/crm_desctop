from __future__ import annotations

import os
import sqlite3

_ENV = {
    "smtp_host": "CRM_SMTP_HOST",
    "smtp_port": "CRM_SMTP_PORT",
    "smtp_user": "CRM_SMTP_USER",
    "smtp_password": "CRM_SMTP_PASSWORD",
    "smtp_from": "CRM_SMTP_FROM",
    "smtp_use_tls": "CRM_SMTP_USE_TLS",
}


def get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    ek = _ENV.get(key)
    if ek:
        v = os.environ.get(ek)
        if v is not None and v != "":
            return v
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row[0]
    return default


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
