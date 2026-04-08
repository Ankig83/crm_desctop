import sqlite3

from crm_desktop.db.database import init_db
from crm_desktop.repositories import calculation_sessions


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def test_create_and_read_session() -> None:
    conn = _conn()
    sid = calculation_sessions.create(
        conn,
        quote_date_iso="2026-04-07",
        client_id=None,
        total=123.45,
        details={"source": "test"},
        lines=[
            calculation_sessions.SessionLine(
                product_id=None,
                product_external_id="P-1",
                product_name="Тестовый товар",
                qty=2,
                base_price=70,
                discount_percent=10,
                line_total=126,
            )
        ],
    )

    recent = calculation_sessions.list_recent(conn, limit=10)
    assert recent
    assert recent[0].id == sid
    assert recent[0].total == 123.45
    lines = calculation_sessions.list_lines(conn, sid)
    assert len(lines) == 1
    assert lines[0].product_external_id == "P-1"
