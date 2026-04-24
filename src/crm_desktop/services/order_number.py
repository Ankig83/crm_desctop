"""Генерация номеров заказов.

Формат: {ИНИЦИАЛЫ}-{СЧЁТЧИК:06d}
Пример: СОИ-000001  (Сергеев Олег Игоревич, первый заказ)

Счётчик хранится в app_settings с ключом вида: order_cnt_СОИ
Каждый менеджер нумерует свои заказы независимо.
"""
from __future__ import annotations

import re
import sqlite3

from crm_desktop.repositories import settings as settings_repo


def get_initials(name: str) -> str:
    """Извлечь инициалы из имени пользователя.

    «Сергеев Олег Игоревич» → «СОИ»
    «Иван Петров»            → «ИП»
    «Администратор»          → «АДМ»
    «»                       → «МГР»
    """
    name = name.strip()
    if not name:
        return "МГР"
    parts = name.split()
    if len(parts) >= 2:
        return "".join(p[0].upper() for p in parts[:3])
    # Одно слово — первые 3 буквы
    return re.sub(r"[^А-ЯA-Z]", "", name.upper())[:3] or "МГР"


def _counter_key(initials: str) -> str:
    return f"order_cnt_{initials}"


def next_order_number(conn: sqlite3.Connection, user_name: str) -> str:
    """Вернуть следующий номер заказа (НЕ инкрементируя счётчик).

    Вызвать confirm_order_number() после успешного сохранения.
    """
    initials = get_initials(user_name)
    key = _counter_key(initials)
    cnt_str = settings_repo.get(conn, key, "1") or "1"
    try:
        cnt = int(cnt_str)
    except ValueError:
        cnt = 1
    return f"{initials}-{cnt:06d}"


def confirm_order_number(conn: sqlite3.Connection, user_name: str) -> None:
    """Инкрементировать счётчик после успешного создания заказа."""
    initials = get_initials(user_name)
    key = _counter_key(initials)
    cnt_str = settings_repo.get(conn, key, "1") or "1"
    try:
        cnt = int(cnt_str)
    except ValueError:
        cnt = 1
    settings_repo.set_value(conn, key, str(cnt + 1))


def parse_order_number(order_no: str) -> tuple[str, int]:
    """Разобрать номер заказа на (инициалы, номер).

    «СОИ-000001» → («СОИ», 1)
    """
    parts = order_no.split("-", 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass
    return ("", 0)
