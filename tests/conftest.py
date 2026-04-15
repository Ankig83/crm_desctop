"""Общие pytest-фикстуры для всего тестового набора."""
from __future__ import annotations

import sqlite3

import pytest

from crm_desktop.db.database import init_db


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite с полной схемой и row_factory."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c
