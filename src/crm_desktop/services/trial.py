"""Ограничение пробного периода.

Логика двойная — дата первого запуска хранится в БД (app_settings)
и в скрытом файле в AppData пользователя. Сработает любая из двух.
Дата сохраняется в обфусцированном виде (XOR + base64).
"""
from __future__ import annotations

import base64
import sqlite3
from datetime import date, timedelta
from pathlib import Path

# ── Конфигурация ───────────────────────────────────────────────────
_TRIAL_DAYS = 7
_DB_KEY      = "cfg_ui_ts_v1"          # имя ключа в app_settings
_FILE_NAME   = ".crm_cfg_v1"           # имя файла в AppData
_XOR_KEY     = 0x5A                    # байт для XOR-обфускации
# ──────────────────────────────────────────────────────────────────


def _encode(s: str) -> str:
    return base64.b64encode(bytes(b ^ _XOR_KEY for b in s.encode())).decode()


def _decode(s: str) -> str:
    return bytes(b ^ _XOR_KEY for b in base64.b64decode(s)).decode()


def _appdata_file() -> Path:
    import os
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / _FILE_NAME


def _today_iso() -> str:
    return date.today().isoformat()


def _read_start_from_db(conn: sqlite3.Connection) -> date | None:
    try:
        r = conn.execute(
            "SELECT value FROM app_settings WHERE key=?", (_DB_KEY,)
        ).fetchone()
        if r:
            return date.fromisoformat(_decode(r[0]))
    except Exception:  # noqa: BLE001
        pass
    return None


def _write_start_to_db(conn: sqlite3.Connection, d: date) -> None:
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
            (_DB_KEY, _encode(d.isoformat())),
        )
        conn.commit()
    except Exception:  # noqa: BLE001
        pass


def _read_start_from_file() -> date | None:
    try:
        f = _appdata_file()
        if f.exists():
            return date.fromisoformat(_decode(f.read_text(encoding="utf-8").strip()))
    except Exception:  # noqa: BLE001
        pass
    return None


def _write_start_to_file(d: date) -> None:
    try:
        _appdata_file().write_text(_encode(d.isoformat()), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def check_trial(conn: sqlite3.Connection) -> tuple[bool, int]:
    """Проверить пробный период.

    Возвращает (ok, days_left):
        ok=True  — можно работать
        ok=False — срок истёк
    """
    today = date.today()

    db_start   = _read_start_from_db(conn)
    file_start = _read_start_from_file()

    # Берём самую раннюю из двух дат (защита от сброса одного источника)
    candidates = [d for d in (db_start, file_start) if d is not None]
    if candidates:
        start = min(candidates)
    else:
        # Первый запуск — фиксируем дату
        start = today
        _write_start_to_db(conn, start)
        _write_start_to_file(start)

    # Синхронизируем оба хранилища (если одно было сброшено)
    if db_start != start:
        _write_start_to_db(conn, start)
    if file_start != start:
        _write_start_to_file(start)

    elapsed    = (today - start).days
    days_left  = _TRIAL_DAYS - elapsed
    return (days_left > 0, max(days_left, 0))
