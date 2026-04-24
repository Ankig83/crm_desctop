from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from crm_desktop.repositories._util import ts_now


@dataclass
class SessionLine:
    product_id: int | None
    product_external_id: str
    product_name: str
    qty: float
    base_price: float
    discount_percent: float
    line_total: float


@dataclass
class SessionRow:
    id: int
    created_at: str
    quote_date: str
    client_id: int | None
    client_name: str
    total: float
    details_json: str
    order_number: str = ""
    manager_name: str = ""


def create(
    conn: sqlite3.Connection,
    *,
    quote_date_iso: str,
    client_id: int | None,
    total: float,
    details: dict,
    lines: list[SessionLine],
    order_number: str = "",
    manager_name: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO calculation_sessions(
            created_at, quote_date, client_id, total, details_json,
            order_number, manager_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts_now(), quote_date_iso, client_id, float(total),
            json.dumps(details, ensure_ascii=False),
            order_number, manager_name,
        ),
    )
    sid = int(cur.lastrowid)
    for ln in lines:
        conn.execute(
            """
            INSERT INTO calculation_session_lines(
                session_id, product_id, product_external_id, product_name,
                qty, base_price, discount_percent, line_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                ln.product_id,
                ln.product_external_id,
                ln.product_name,
                float(ln.qty),
                float(ln.base_price),
                float(ln.discount_percent),
                float(ln.line_total),
            ),
        )
    conn.commit()
    return sid


def list_recent(conn: sqlite3.Connection, limit: int = 200) -> list[SessionRow]:
    rows = conn.execute(
        """
        SELECT s.id, s.created_at, s.quote_date, s.client_id,
               COALESCE(c.name, ''), s.total, s.details_json,
               COALESCE(s.order_number, ''), COALESCE(s.manager_name, '')
        FROM calculation_sessions s
        LEFT JOIN clients c ON c.id = s.client_id
        ORDER BY s.id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [
        SessionRow(
            id=int(r[0]),
            created_at=r[1] or "",
            quote_date=r[2] or "",
            client_id=int(r[3]) if r[3] is not None else None,
            client_name=r[4] or "",
            total=float(r[5] or 0),
            details_json=r[6] or "",
            order_number=r[7] or "",
            manager_name=r[8] or "",
        )
        for r in rows
    ]


def list_lines(conn: sqlite3.Connection, session_id: int) -> list[SessionLine]:
    rows = conn.execute(
        """
        SELECT product_id, product_external_id, product_name, qty, base_price, discount_percent, line_total
        FROM calculation_session_lines
        WHERE session_id = ?
        ORDER BY id
        """,
        (int(session_id),),
    ).fetchall()
    return [
        SessionLine(
            product_id=int(r[0]) if r[0] is not None else None,
            product_external_id=r[1] or "",
            product_name=r[2] or "",
            qty=float(r[3] or 0),
            base_price=float(r[4] or 0),
            discount_percent=float(r[5] or 0),
            line_total=float(r[6] or 0),
        )
        for r in rows
    ]
